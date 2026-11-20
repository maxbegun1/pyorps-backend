import json, csv
from pathlib import Path
here=Path(__file__).resolve().parent
out=here/'dashboard-deployment'
out.mkdir(exist_ok=True)
assets={}
for path,name,mime in [('/','routing-map.html','text/html; charset=utf-8'),('/routing-map.js','routing-map.js','text/javascript; charset=utf-8'),('/routing-map.css','routing-map.css','text/css; charset=utf-8'),('/routing-config.js','routing-config.js','text/javascript; charset=utf-8'),('/prediction.js','prediction.js','text/javascript; charset=utf-8'),('/scenario-model.js','scenario-model.js','text/javascript; charset=utf-8'),('/scenario-models.json','scenario-models.json','application/json; charset=utf-8'),('/nearest-pois.js','nearest-pois.js','text/javascript; charset=utf-8'),('/baseline-hazards.json','baseline-hazards.json','application/json; charset=utf-8')]:
    assets[path]=[mime,(here/name).read_text(encoding='utf-8-sig')]
with (here/'poi_coordinates_clean.csv').open(encoding='utf-8-sig',newline='') as f:
    pois=[{'name':r['queue_poi_name_exact'] or r['map_poi_name'] or r['bus_name'] or 'Unnamed POI','voltage_kv':r['voltage_kv'],'latitude':float(r['latitude']),'longitude':float(r['longitude'])} for r in csv.DictReader(f)]
assets['/pois']=['application/json; charset=utf-8',json.dumps({'pois':pois},separators=(',',':'))]
with (here/'miso_week13_forecasts.csv').open(encoding='utf-8-sig',newline='') as f:
    forecasts={}
    for r in csv.DictReader(f):
        key=r['project_id'].strip().casefold()
        if key not in forecasts or r['panel_quarter']>forecasts[key]['snapshot_quarter']:
            forecasts[key]={'project_id':r['project_id'],'snapshot_quarter':r['panel_quarter'],'age_quarters':int(r['age_quarters']),'horizon_quarters':int(r['forecast_horizon_quarters']),'operational_probability':float(r['predicted_overall_operational_probability']),'withdrawal_probability':float(r['predicted_overall_withdrawal_probability'])}
code='const FORECASTS='+json.dumps(forecasts,separators=(',',':'))+';\nconst ASSETS='+json.dumps(assets,separators=(',',':'))+'''\nexport default {async fetch(request){const url=new URL(request.url);const match=url.pathname.match(/^\\/forecast\\/miso\\/([^/]+)$/);if(request.method==='GET'&&match){const value=FORECASTS[decodeURIComponent(match[1]).trim().toLowerCase()];return Response.json(value||{detail:'No historical snapshot found for this project.'},{status:value?200:404})}const asset=ASSETS[url.pathname];if(asset && (request.method==='GET'||request.method==='HEAD'))return new Response(request.method==='HEAD'?null:asset[1],{headers:{'content-type':asset[0],'x-content-type-options':'nosniff','cache-control':'no-store'}});const allowed=(request.method==='GET'&&(/^(\\/pois(?:\\/nearest)?|\\/map\\/(?:states|footprints)|\\/identify|\\/forecast\\/miso\\/[^/]+)$/.test(url.pathname)))||(request.method==='POST'&&url.pathname==='/route');if(!allowed)return new Response('Not found',{status:404});const upstream=new URL(url.pathname+url.search,'https://pyorps-backend.onrender.com');try{return await fetch(new Request(upstream,request))}catch{return new Response(JSON.stringify({detail:'Routing service unavailable'}),{status:503,headers:{'content-type':'application/json'}})}}};\n'''
(out/'worker.mjs').write_text(code,encoding='utf-8')
(out/'cloudflare.config.ts').write_text("export default { worker: { name: 'energy-platform-predictor-preview', entrypoint: './worker.mjs', compatibilityDate: '2026-11-18' } };\n",encoding='utf-8')
root=out/'.cloudflare'/'output'/'v0'; worker=root/'workers'/'default'; (worker/'bundle').mkdir(parents=True,exist_ok=True)
(worker/'bundle'/'worker.mjs').write_text(code,encoding='utf-8')
(root/'config.json').write_text(json.dumps({'buildContext':{'isPreview':False}}),encoding='utf-8')
(worker/'worker.config.json').write_text(json.dumps({'name':'energy-platform-predictor-preview','compatibilityDate':'2026-11-18','manifest':{'type':'complete','mainModule':'worker.mjs','modules':{'worker.mjs':{'type':'esm'}}}}),encoding='utf-8')
print('Prepared preview with same-origin routing proxy')
