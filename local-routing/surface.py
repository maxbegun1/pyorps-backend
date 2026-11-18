"""Read full regional tiled datasets into a bounded request-specific surface."""
import csv
import json
import math
from pathlib import Path
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
from data_store import ROOT as DATA, get_file

INDEX = list(csv.DictReader(get_file('tile_index.csv').open(encoding='utf-8')))
STATE = gpd.read_file('zip://' + str(get_file('source/cb_2025_us_state_20m.zip'))).to_crs(5070)
FOOTPRINTS = {region: gpd.read_file(get_file(f'boundaries/{region.lower()}_footprint.gpkg')).to_crs(5070).geometry.union_all() for region in ('MISO','NYISO')}

def build(start, end, output, region):
    weights=json.loads((Path(__file__).parent/'weights.json').read_text(encoding='utf-8'))
    keys=['ordinary','developed_open','forest','low_development','wetland','medium_high_development','open_water','protected','slope_add']
    if any(type(weights.get(k)) is not int or not 0 <= weights[k] <= 10000 for k in keys) or weights['ordinary'] < 1 or not 0 < weights.get('slope_threshold',0) <= 10:
        raise ValueError('Invalid routing weights configuration')
    # Resource limit keeps interactive requests manageable. Long routes are coarser.
    pad = 3000.0
    extent = [min(start[0],end[0])-pad, min(start[1],end[1])-pad,
              max(start[0],end[0])+pad, max(start[1],end[1])+pad]
    res = max(30, int(math.ceil(math.sqrt((extent[2]-extent[0])*(extent[3]-extent[1])/350000)/30))*30)
    if res > 600:
        raise ValueError('Route area is too large for this local test; choose closer points.')
    left,bottom = [math.floor(x/res)*res for x in extent[:2]]
    right,top = [math.ceil(x/res)*res for x in extent[2:]]
    width,height = round((right-left)/res),round((top-bottom)/res)
    tr = from_origin(left,top,res,res)
    layers = {}
    for name, dtype, nodata, sampling in [('NLCD_2024_landcover','uint8',255,Resampling.nearest),('NWI_class','uint8',255,Resampling.nearest),('3DEP_elevation','float32',-9999,Resampling.bilinear)]:
        dst = np.full((height,width),nodata,dtype=dtype)
        tiles = [r for r in INDEX if r['region']==region and r['layer']==name and float(r['xmin'])<right and float(r['xmax'])>left and float(r['ymin'])<top and float(r['ymax'])>bottom]
        for r in tiles:
            with rasterio.open(get_file(r['relative_path'])) as src:
                reproject(source=rasterio.band(src,1),destination=dst,src_transform=src.transform,src_crs=src.crs,src_nodata=src.nodata,dst_transform=tr,dst_crs='EPSG:5070',dst_nodata=nodata,resampling=sampling,init_dest_nodata=False,num_threads=1)
        layers[name] = dst
    land,nwi,elev = [layers[x] for x in ('NLCD_2024_landcover','NWI_class','3DEP_elevation')]
    inside = rasterize([(FOOTPRINTS[region],1)],out_shape=(height,width),transform=tr,fill=0,dtype='uint8').astype(bool)
    valid = inside & (land!=255) & (nwi!=255) & (elev!=-9999)
    cost=np.full((height,width),weights['ordinary'],dtype='uint16')
    for classes,value in [([41,42,43],weights['forest']),([21],weights['developed_open']),([22],weights['low_development']),([23,24],weights['medium_high_development']),([90,95],weights['wetland']),([11],weights['open_water'])]:
        cost[np.isin(land,classes)]=value
    land_map=cost.copy()
    # The source NWI codes identify different mapped water/wetland classes. Treat all
    # nonzero classes as a screening penalty without asserting a specific wetland type.
    cost[(nwi>0)&(nwi<255)] = np.maximum(cost[(nwi>0)&(nwi<255)],weights['wetland'])
    # Elevation gradient is approximate at the selected cell size, not an engineering survey.
    safe_elev=np.where(elev!=-9999,elev,np.nan)
    gy,gx=np.gradient(safe_elev,res)
    slope=np.hypot(gx,gy)
    cost[np.isfinite(slope)&(slope>=weights['slope_threshold'])] += weights['slope_add']
    protected=gpd.read_file(get_file(f'vectors/{region.lower()}_padus_protected_areas.gpkg'),bbox=(left,bottom,right,top))
    if len(protected):
        invalid=~protected.geometry.is_valid
        if invalid.any(): protected.loc[invalid,'geometry']=protected.loc[invalid,'geometry'].make_valid()
        pmask=rasterize(((g,1) for g in protected.geometry if g is not None and not g.is_empty),out_shape=(height,width),transform=tr,fill=0,dtype='uint8').astype(bool)
        cost[pmask]=np.maximum(cost[pmask],weights['protected'])
    else: pmask=np.zeros((height,width),dtype=bool)
    cost[~valid]=65535
    land_map[~valid]=65535
    nwi_map=np.where(valid,np.where((nwi>0)&(nwi<255),400,100),65535).astype('uint16')
    slope_map=np.where(valid & np.isfinite(slope),np.where(slope>=weights['slope_threshold'],600,100),65535).astype('uint16')
    protected_map=np.where(valid,np.where(pmask,1000,100),65535).astype('uint16')
    with rasterio.open(output,'w',driver='GTiff',height=height,width=width,count=1,dtype='uint16',crs='EPSG:5070',transform=tr,nodata=65535,compress='deflate') as dst: dst.write(cost,1)
    identify={'land':land,'nwi':nwi,'slope':slope,'protected':pmask,'valid':valid,'cost':cost,'transform':tr,'threshold':weights['slope_threshold']}
    return {'region':region,'resolution_m':res,'width':width,'height':height,'valid_cells':int(valid.sum()),'footprint_cells':int(inside.sum()),'protected_cells':int((pmask & valid).sum()),'nwi_nonzero_cells':int(((nwi>0)&(nwi<255)&valid).sum()),'weights':weights}, {'land_cover':land_map,'nwi_nonzero':nwi_map,'slope':slope_map,'padus':protected_map}, identify
