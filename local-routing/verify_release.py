"""Verify GitHub release asset metadata against the local data manifest.

Pipe newline-delimited JSON asset objects from the paginated GitHub API.
"""
import json, sys
from pathlib import Path

manifest=json.loads(Path(__file__).with_name('gis_release_manifest.json').read_text(encoding='utf-8'))
expected=manifest['assets']; found={};bad=[]
for line in sys.stdin:
    asset=json.loads(line)
    if asset['state']!='uploaded': continue
    name=asset['name']; found[name]=asset
    if name not in expected or asset['size']!=expected[name]['bytes'] or asset.get('digest')!='sha256:'+expected[name]['sha256']:
        bad.append(name)
missing=set(expected)-set(found)
print(f'Verified {len(found)-len(bad)} of {len(expected)}; missing {len(missing)}; incorrect {len(bad)}')
if bad: print('Incorrect:',', '.join(bad))
if missing or bad: sys.exit(1)
