"""Build full-resolution GIS release assets and a file-to-archive manifest."""
import csv, hashlib, json, re, zipfile
from collections import defaultdict
from pathlib import Path

ROOT=Path.home()/'Downloads'/'PYORPS_MISO_NYISO_Data'
OUT=Path(__file__).resolve().parent.parent.parent/'tmp'/'pyorps-release-assets'
OUT.mkdir(parents=True,exist_ok=True)
groups=defaultdict(list)
with (ROOT/'tile_index.csv').open(encoding='utf-8',newline='') as f:
    for row in csv.DictReader(f):
        tile=Path(row['relative_path']).stem
        safe=re.sub('[^a-zA-Z0-9_-]','_',tile.replace('+','p'))
        groups[f"{row['region'].lower()}_{safe}.zip"].append(row['relative_path'])
groups['gis_core.zip']=['tile_index.csv','README.txt','validation_report.txt','source/cb_2025_us_state_20m.zip','boundaries/miso_footprint.gpkg','boundaries/nyiso_footprint.gpkg']
for region in ['miso','nyiso']:
    groups[f'{region}_protected.zip']=[f'vectors/{region}_padus_protected_areas.gpkg']
manifest={'version':1,'files':{},'assets':{}}
for i,(asset,files) in enumerate(sorted(groups.items()),1):
    dest=OUT/asset
    with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
        for name in files:
            p=ROOT/name
            if not p.is_file(): raise FileNotFoundError(p)
            z.write(p,arcname=name)
            manifest['files'][name]=asset
    digest=hashlib.sha256()
    with dest.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)
    manifest['assets'][asset]={'sha256':digest.hexdigest(),'bytes':dest.stat().st_size}
    if i%25==0 or i==len(groups): print(f'{i}/{len(groups)} {asset}',flush=True)
dest=Path(__file__).resolve().parent/'gis_release_manifest.json'
dest.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('assets',len(groups),'files',len(manifest['files']),'bytes',sum(x['bytes'] for x in manifest['assets'].values()),flush=True)
