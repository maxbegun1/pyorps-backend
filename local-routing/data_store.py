"""Access local GIS data or lazily cache files from a configured HTTPS source."""
import os
import shutil
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

BASE=os.environ.get('PYORPS_DATA_BASE_URL','').rstrip('/')
ROOT=Path(os.environ.get('PYORPS_DATA_DIR', str(Path(tempfile.gettempdir())/'pyorps-gis' if BASE else Path.home()/'Downloads'/'PYORPS_MISO_NYISO_Data')))

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
    url=BASE+'/'+urllib.parse.quote(relative,safe='/')
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
        temporary.replace(target)
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)
    return target
