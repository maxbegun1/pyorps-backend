"""Access local GIS data or lazily cache files from a configured HTTPS source."""
import os
import hashlib
import json
import shutil
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

BASE=os.environ.get('PYORPS_DATA_BASE_URL','').rstrip('/')
ROOT=Path(os.environ.get('PYORPS_DATA_DIR', str(Path(tempfile.gettempdir())/'pyorps-gis' if BASE else Path.home()/'Downloads'/'PYORPS_MISO_NYISO_Data')))
MANIFEST_PATH=Path(__file__).with_name('gis_release_manifest.json')
MANIFEST=json.loads(MANIFEST_PATH.read_text(encoding='utf-8')) if BASE and MANIFEST_PATH.is_file() else None
CACHE_LIMIT=int(os.environ.get('PYORPS_CACHE_MAX_BYTES',str(1536*1024*1024)))

class CacheLimitError(RuntimeError):
    pass

def get_file(relative):
    relative=str(relative).replace('\\','/')
    parts=PurePosixPath(relative)
    if parts.is_absolute() or any(x in ('..','.') for x in parts.parts):
        raise ValueError('Invalid GIS data path')
    target=ROOT.joinpath(*parts.parts)
    if target.is_file(): return target
    if not BASE: raise FileNotFoundError(f'GIS file is missing: {relative}')
    parsed=urllib.parse.urlparse(BASE)
    if parsed.scheme!='https' and not (os.environ.get('PYORPS_ALLOW_LOCAL_HTTP')=='1' and parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost')):
        raise ValueError('PYORPS_DATA_BASE_URL must use HTTPS')
    asset=MANIFEST['files'].get(relative) if MANIFEST else None
    if MANIFEST and not asset: raise FileNotFoundError(f'GIS file absent from release manifest: {relative}')
    if asset:
        # Archives are ZIP_STORED, so reserve space for both archive and extraction.
        # Never remove pre-existing files; Render's ephemeral filesystem resets on restart.
        used=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()) if ROOT.exists() else 0
        if used+2*MANIFEST['assets'][asset]['bytes']>CACHE_LIMIT:
            raise CacheLimitError('Temporary GIS cache limit reached; retry after service restart.')
    url=BASE+'/'+urllib.parse.quote(asset or relative,safe='/')
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with urllib.request.urlopen(url,timeout=60) as response:
            expected=response.headers.get('Content-Length')
            with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as tmp:
                temporary=Path(tmp.name)
                shutil.copyfileobj(response,tmp,length=1024*1024)
        if not temporary.stat().st_size or (expected is not None and temporary.stat().st_size!=int(expected)):
            raise IOError(f'Incomplete GIS download: {relative}')
        if asset:
            info=MANIFEST['assets'][asset]
            digest=hashlib.sha256()
            with temporary.open('rb') as f:
                for block in iter(lambda:f.read(1024*1024),b''): digest.update(block)
            if temporary.stat().st_size!=info['bytes'] or digest.hexdigest()!=info['sha256']:
                raise IOError(f'GIS archive checksum failed: {asset}')
            with zipfile.ZipFile(temporary) as archive:
                members=[x for x in archive.infolist() if not x.is_dir()]
                if not members or any(MANIFEST['files'].get(m.filename)!=asset for m in members):
                    raise ValueError('Unexpected GIS archive contents')
                for member in members:
                    parts=PurePosixPath(member.filename)
                    if parts.is_absolute() or '..' in parts.parts: raise ValueError('Invalid GIS archive path')
                    output=ROOT.joinpath(*parts.parts);output.parent.mkdir(parents=True,exist_ok=True)
                    with archive.open(member) as src, tempfile.NamedTemporaryFile(dir=output.parent,delete=False) as dst:
                        extracted=Path(dst.name)
                        try: shutil.copyfileobj(src,dst,length=1024*1024)
                        except BaseException:
                            dst.close();extracted.unlink(missing_ok=True);raise
                    extracted.replace(output)
            if not target.is_file(): raise FileNotFoundError(relative)
        else:
            temporary.replace(target)
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)
    return target
