"""Local Illinois routing test using the user's tiled GIS data."""
import json, logging, math, os, tempfile, io, base64, secrets, time, csv
from collections import OrderedDict
from html import escape
from pathlib import Path
from threading import Lock
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('NUMBA_NUM_THREADS','1')
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform, transform_geom, calculate_default_transform, reproject, Resampling, transform_bounds
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal
from pyorps import PathFinder
from shapely.geometry import Point
from PIL import Image, ImageDraw
from surface import build, STATE, FOOTPRINTS
from data_store import CacheLimitError

app=FastAPI(title='MISO and NYISO 345-kV local routing test')
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in os.environ.get('CORS_ORIGINS','http://127.0.0.1:8772,http://localhost:8772').split(',') if x.strip()], allow_methods=['GET','POST'], allow_headers=['Content-Type'])
lock=Lock()
cache_lock=Lock()
identify_cache=OrderedDict()
LAND_NAMES={11:'Open water',12:'Perennial ice or snow',21:'Developed open space',22:'Low-intensity development',23:'Medium-intensity development',24:'High-intensity development',31:'Barren land',41:'Deciduous forest',42:'Evergreen forest',43:'Mixed forest',52:'Shrub or scrub',71:'Grassland or herbaceous',81:'Pasture or hay',82:'Cultivated crops',90:'Woody wetlands',95:'Emergent herbaceous wetlands'}

@app.get('/identify')
def identify(token:str,lon:float,lat:float):
    if not (math.isfinite(lon) and math.isfinite(lat) and -180<=lon<=180 and -90<=lat<=90):
        raise HTTPException(422,'Invalid coordinates')
    with cache_lock:
        entry=identify_cache.get(token)
        if entry is None or time.monotonic()-entry[0]>1800:
            identify_cache.pop(token,None)
            raise HTTPException(410,'Route data expired. Calculate the route again.')
        data=entry[1]
    x,y=transform('EPSG:4326','EPSG:5070',[lon],[lat]); col,row=(~data['transform'])*(x[0],y[0]); row,col=math.floor(row),math.floor(col)
    height,width=data['valid'].shape
    if not (0<=row<height and 0<=col<width): return {'available':False,'message':'Outside the calculated area'}
    if not data['valid'][row,col]: return {'available':False,'message':'No usable data at this location'}
    land=int(data['land'][row,col]);nwi=int(data['nwi'][row,col]);slope=float(data['slope'][row,col])
    return {'available':True,'land_cover':LAND_NAMES.get(land,f'Land-cover class {land}'),'land_code':land,'nwi_class':nwi,'nwi_note':'Mapped NWI class; type not verified' if nwi else 'No nonzero NWI class mapped','protected':bool(data['protected'][row,col]),'slope_percent':round(slope*100,1) if math.isfinite(slope) else None,'slope_threshold_percent':data['threshold']*100,'preference':int(data['cost'][row,col])}
class Request(BaseModel):
    start: tuple[float,float]
    end: tuple[float,float]
    cost_per_mile: float | None=Field(default=None,gt=0,le=1000000000)
    voltage_kv: Literal[69,115,138,230,345]=345

# MISO MTEP24 Table 4.1-1, $million/mile, new single-circuit lines, 2024 USD.
VOLTAGES=[69,115,138,230,345]
RATES={'AR':[1.7,1.9,2.0,2.2,3.5],'IL':[1.8,2.0,2.0,2.2,3.6],'IN':[1.7,1.9,2.0,2.1,3.4],'IA':[1.7,1.9,2.0,2.2,3.5],'KY':[1.8,2.0,2.1,2.3,3.7],'LA':[2.0,2.2,2.3,2.6,4.1],'MI':[1.8,2.0,2.1,2.3,3.7],'MN':[1.8,2.0,2.1,2.3,3.6],'MS':[2.0,2.2,2.3,2.6,4.1],'MO':[1.7,1.9,2.0,2.2,3.5],'MT':[1.6,1.8,1.9,2.0,3.2],'ND':[1.6,1.8,1.9,2.0,3.3],'SD':[1.6,1.8,1.9,2.0,3.3],'TX':[1.9,2.2,2.3,2.5,4.0],'WI':[1.8,2.0,2.1,2.3,3.7]}

def load_pois():
    with (Path(__file__).parent/'poi_coordinates_clean.csv').open(encoding='utf-8-sig',newline='') as f:
        return [dict(row,latitude=float(row['latitude']),longitude=float(row['longitude'])) for row in csv.DictReader(f)]
POIS=load_pois()

@app.get('/pois/nearest')
def nearest_pois(lon:float,lat:float):
    if not (math.isfinite(lon) and math.isfinite(lat) and -180<=lon<=180 and -90<=lat<=90): raise HTTPException(422,'Invalid coordinates')
    def distance(p):
        a,b=math.radians(lat),math.radians(p['latitude']);da=b-a;dl=math.radians(p['longitude']-lon)
        x=math.sin(da/2)**2+math.cos(a)*math.cos(b)*math.sin(dl/2)**2
        return 3958.7613*2*math.asin(min(1,math.sqrt(x)))
    nearest=sorted(POIS,key=distance)[:5]
    return {'method':'nearest by straight-line great-circle distance; no electrical compatibility check','pois':[{'name':p['queue_poi_name_exact'] or p['map_poi_name'] or p['bus_name'],'map_poi_name':p['map_poi_name'],'queue_poi_name':p['queue_poi_name_exact'],'bus_number':p['bus_number'],'voltage_kv':p['voltage_kv'],'latitude':p['latitude'],'longitude':p['longitude'],'coordinate_status':p['coordinate_status'],'source':p['source'],'distance_miles':round(distance(p),3)} for p in nearest]}

def draw_map(a, src, routes):
    # Colours represent combined relative costs, not independent GIS layers.
    rgb=np.full((*a.shape,3),[217,217,217],dtype=np.uint8)
    for lo,hi,color in [(1,159,(214,235,192)),(160,249,(115,171,108)),(250,399,(244,190,88)),(400,599,(89,165,214)),(600,899,(226,106,80)),(900,999,(35,83,137)),(1000,65534,(128,84,154))]:
        rgb[(a>=lo)&(a<=hi)]=color
    im=Image.fromarray(rgb); draw=ImageDraw.Draw(im)
    for geom in routes.geometry:
        points=[(~src.transform)*(x,y) for x,y in geom.coords]
        if len(points)>1: draw.line(points,fill=(0,0,0),width=max(1,int(max(im.size)/500)*2))
    im.thumbnail((1000,700),Image.Resampling.NEAREST)
    stream=io.BytesIO(); im.save(stream,format='PNG',optimize=True)
    return base64.b64encode(stream.getvalue()).decode('ascii')

def map_overlay(a, src):
    tr,w,h=calculate_default_transform(src.crs,'EPSG:3857',src.width,src.height,*src.bounds)
    out=np.full((h,w),65535,dtype=np.uint16)
    reproject(a,out,src_transform=src.transform,src_crs=src.crs,src_nodata=65535,dst_transform=tr,dst_crs='EPSG:3857',dst_nodata=65535,resampling=Resampling.nearest)
    rgba=np.zeros((h,w,4),dtype=np.uint8)
    for lo,hi,color in [(1,159,(168,216,150)),(160,249,(89,163,89)),(250,399,(242,174,60)),(400,599,(42,139,211)),(600,899,(226,68,57)),(900,999,(19,54,132)),(1000,65534,(127,51,150))]:
        rgba[(out>=lo)&(out<=hi)]=(*color,150)
    image=Image.fromarray(rgba); image.thumbnail((1400,1400),Image.Resampling.NEAREST)
    buf=io.BytesIO();image.save(buf,format='PNG',optimize=True)
    from rasterio.transform import array_bounds
    bounds=transform_bounds('EPSG:3857','EPSG:4326',*array_bounds(h,w,tr))
    return {'image':base64.b64encode(buf.getvalue()).decode(),'bounds':bounds}

@app.get('/map/states')
def map_states():
    state=STATE.to_crs(4326)
    result=[]
    for idx,row in STATE.iterrows():
        if any(row.geometry.intersects(f) and row.geometry.intersection(f).area/row.geometry.area>0.001 for f in FOOTPRINTS.values()):
            s=state.loc[idx]
            result.append({'code':row.STUSPS,'name':row.NAME,'bounds':list(s.geometry.bounds),'geometry':s.geometry.__geo_interface__})
    return sorted(result,key=lambda x:x['name'])

@app.get('/map/footprints')
def map_footprints():
    return {name:gpd.GeoSeries([shape],crs=5070).to_crs(4326).iloc[0].__geo_interface__ for name,shape in FOOTPRINTS.items()}

@app.get('/routing-map.js')
def routing_js(): return FileResponse(Path(__file__).parent/'routing-map.js',media_type='application/javascript')

@app.get('/routing-map.css')
def routing_css(): return FileResponse(Path(__file__).parent/'routing-map.css',media_type='text/css')

@app.get('/routing-config.js')
def routing_config(): return FileResponse(Path(__file__).parent/'routing-config.js',media_type='application/javascript')

@app.get('/health')
def health(): return {'status':'ok','mode':'local MISO and NYISO GIS test'}

@app.post('/route')
def route(req:Request):
    if any(not math.isfinite(v) for v in (*req.start,*req.end)):
        raise HTTPException(422,'Coordinates must be finite longitude and latitude.')
    if any(not (-180<=p[0]<=180 and -90<=p[1]<=90) for p in (req.start,req.end)):
        raise HTTPException(422,'Coordinates must be [longitude, latitude].')
    try:
        x,y=transform('EPSG:4326','EPSG:5070',[req.start[0],req.end[0]],[req.start[1],req.end[1]])
        coords=list(zip(x,y))
        regions=[name for name,shape in FOOTPRINTS.items() if all(shape.covers(Point(p)) for p in coords)]
        if not regions: raise HTTPException(422,'Both endpoints must be inside the same supplied MISO or NYISO footprint.')
        region=regions[0]
        if math.dist(*coords)<30: raise HTTPException(422,'Choose points at least 30 meters apart.')
        with lock, tempfile.TemporaryDirectory() as tmp:
            tif=str(Path(tmp)/'cost.tif')
            metadata,layers,identify_data=build(*coords,tif,region)
            with rasterio.open(tif) as src:
                a=src.read(1)
                for name,p in zip(('start','end'),coords):
                    row,col=src.index(*p)
                    if not (0<=row<src.height and 0<=col<src.width) or a[row,col]==65535:
                        raise HTTPException(422,f'{name} has no usable data in the supplied {region} GIS footprint.')
            finder=PathFinder(dataset_source=tif,source_coords=coords[0],target_coords=coords[1],search_space_buffer_m=3000)
            finder.find_route()
            gpkg=str(Path(tmp)/'path.gpkg')
            finder.save_paths(gpkg)
            routes=gpd.read_file(gpkg)
            if routes.empty or routes.crs is None: raise ValueError('PYORPS returned no usable route.')
            projected=routes.to_crs(5070)
            with rasterio.open(tif) as src:
                touched=rasterize(((g,1) for g in projected.geometry),out_shape=a.shape,transform=src.transform,all_touched=True).astype(bool)
                if np.any(touched & (a==65535)):
                    raise HTTPException(422,'The calculated route crosses missing data or leaves the supplied footprint. Try closer points or another area.')
                map_png=draw_map(a,src,projected)
                layer_maps={key:draw_map(array,src,projected) for key,array in layers.items()}
                map_layers={key:map_overlay(array,src) for key,array in {'combined':a,**layers}.items()}
            length=float(projected.length.sum())/1000
            result=json.loads(routes.to_crs(4326).to_json())
            line=projected.geometry.union_all()
            segments=[]
            for _,state in STATE.iterrows():
                distance=line.intersection(state.geometry).length
                if distance>0.01:
                    rate=req.cost_per_mile if req.cost_per_mile is not None else (RATES[state.STUSPS][VOLTAGES.index(req.voltage_kv)]*1e6 if state.STUSPS in RATES else None)
                    segments.append({'state':state.STUSPS,'miles':round(distance/1609.344,5),'rate_usd_per_mile':rate,'line_cost_usd':round(distance/1609.344*rate) if rate else None})
            priced=sum(x['miles'] for x in segments)
            complete=all(x['line_cost_usd'] is not None for x in segments) and abs(priced-length/1.609344)<0.002
            estimate={'route_miles':round(length/1.609344,4),'line_voltage_kv':req.voltage_kv,'circuit':'single','state_segments':segments,'line_cost_usd':sum(x['line_cost_usd'] for x in segments) if complete and segments else None,'basis':'MISO MTEP24 new single-circuit state rates, 2024 dollars; includes contingency and AFUDC. No default rate for New York. User override applies across the route. Excludes separate substations. Routing weights are the same for all voltages.'}
            token=secrets.token_urlsafe(16)
            with cache_lock:
                identify_cache[token]=(time.monotonic(),identify_data)
                while len(identify_cache)>6: identify_cache.popitem(last=False)
            result.update(route_length_km=round(length,6),estimate=estimate,data=metadata,identify_token=token,screening_map_png_base64=map_png,layer_maps_png_base64=layer_maps,map_layers=map_layers,warning='Screening only. Colours are combined preference indices, not dollar costs. 3 km search buffer and coarser long-route grid can miss alternatives; source coverage is incomplete.')
            return result
    except HTTPException: raise
    except CacheLimitError as e:
        raise HTTPException(503,str(e)) from e
    except ValueError as e:
        logging.exception('Route failed')
        raise HTTPException(422,'Could not calculate a route through the available data; try closer points or a different location.') from e
    except Exception as e:
        logging.exception('Route failed')
        raise HTTPException(500,'Route calculation failed; see local server log.') from e

FORM='''<!doctype html><html><head><meta charset="utf-8"><title>Illinois routing test</title><style>body{font:17px system-ui;max-width:800px;margin:40px auto;padding:0 20px;color:#202a30}label{display:block;margin:15px 0}input{font:inherit;padding:8px;width:190px}button{font:inherit;background:#17684f;color:white;border:0;border-radius:5px;padding:12px 20px}small{color:#555}code{overflow-wrap:anywhere}svg{width:100%;max-width:600px;background:#eff5f2;border:1px solid #aaa}</style></head><body><h1>Illinois 345-kV routing test</h1><p>Enter longitude and latitude for two locations in Illinois. Data coverage is limited to the supplied MISO footprint.</p><form action="/view"><label>Start longitude <input name="start_lon" type="number" step="any" value="-89.3978373267" required> latitude <input name="start_lat" type="number" step="any" value="40.1681863304" required></label><label>End longitude <input name="end_lon" type="number" step="any" value="-89.3882661485" required> latitude <input name="end_lat" type="number" step="any" value="40.1676841043" required></label><label>Line cost per mile ($) <input name="cost" type="number" step="any" min="1" value="3600000" required></label><button>Calculate route</button></form><p><small>The default rate is the MISO MTEP24 Illinois exploratory benchmark in 2024 dollars. It includes contingency and AFUDC. This is a screening test, not a siting study.</small></p>'''
@app.get('/',response_class=HTMLResponse)
def home(): return FileResponse(Path(__file__).parent/'routing-map.html',media_type='text/html')

def page_form():
    return (FORM.replace('Illinois 345-kV routing test','MISO and NYISO 345-kV routing test')
        .replace('two locations in Illinois. Data coverage is limited to the supplied MISO footprint.','two locations in the same supplied MISO or NYISO footprint.')
        .replace('Line cost per mile ($)','Optional rate override ($/mile)')
        .replace('value="3600000" required','placeholder="MISO state rate"')
        .replace('The default rate is the MISO MTEP24 Illinois exploratory benchmark in 2024 dollars.','The default rates are MISO MTEP24 state exploratory benchmarks in 2024 dollars. New York has no default rate.'))

@app.get('/view',response_class=HTMLResponse)
def view(start_lon:float,start_lat:float,end_lon:float,end_lat:float,cost:str=''):
    try: result=route(Request(start=(start_lon,start_lat),end=(end_lon,end_lat),cost_per_mile=float(cost) if cost.strip() else None))
    except Exception as e:
        message=e.detail if isinstance(e,HTTPException) else str(e)
        return page_form()+'<p><b>Could not calculate:</b> '+escape(str(message))+'</p></body></html>'
    coordinates=result['features'][0]['geometry']['coordinates']
    xs=[p[0] for p in coordinates]; ys=[p[1] for p in coordinates]
    dx=max(max(xs)-min(xs),1e-8);dy=max(max(ys)-min(ys),1e-8)
    scale=min(540/dx,240/dy)
    pts=' '.join(f'{30+(x-min(xs))*scale:.1f},{270-(y-min(ys))*scale:.1f}' for x,y in coordinates)
    est=result['estimate']; data=result['data']
    amount=f"${est['line_cost_usd']:,.0f}" if est['line_cost_usd'] is not None else 'Unavailable: no MISO rate for at least one state; enter a rate override.'
    state_text=', '.join(f"{escape(x['state'])}: {x['miles']:.3f} miles" for x in est['state_segments'])
    extra=''.join(f"<h3>{label}</h3><p>{desc}</p><img style='max-width:100%;image-rendering:pixelated' alt='{label}' src='data:image/png;base64,{result['layer_maps_png_base64'][key]}'>" for key,label,desc in [('land_cover','Land cover','Colours use the combined map legend; NLCD classes are grouped by the routing weights.'),('nwi_nonzero','NWI thematic classes','Blue means a nonzero NWI value. The bundle does not document each value; absence of blue does not prove dry land.'),('slope','Elevation gradient',f"Red indicates estimated slope of at least {data['weights']['slope_threshold']*100:g}%; pale green is below that threshold; gray is unavailable."),('padus','PAD-US areas','Purple marks mapped PAD-US features. Different ownership and management types have different rules.')])
    return page_form()+f"<h2>Result</h2><p>Route length: {est['route_miles']:.3f} miles<br>Estimated line cost: {amount}<br>State segments: {state_text}<br>Routing grid: {data['resolution_m']} meters per cell</p><img style='max-width:100%;image-rendering:pixelated' alt='Combined screening weights and black route' src='data:image/png;base64,{result['screening_map_png_base64']}'><p>Combined preference colours: pale green 100–159; green 160–249; orange 250–399; blue 400–599; red 600–899; dark blue 900–999; purple 1000+; gray missing; black line is the route. Values are relative preferences, not dollar costs. Overlapping constraints combine or take priority.</p>"+extra+"<p>Maps have no basemap; they cover the calculation area and use a 3 km search buffer. Verify all locations and constraints independently.</p><p><a href='/docs'>API documentation</a></p></body></html>"
