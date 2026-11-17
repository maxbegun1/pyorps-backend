import json
from pathlib import Path
import geopandas as gpd
from surface import DATA, STATE, FOOTPRINTS

result={'footprints':{},'protected':{},'state_counts':{},'notes':[]}
for region,shape in FOOTPRINTS.items():
    path=DATA/f'boundaries/{region.lower()}_footprint.gpkg'
    frame=gpd.read_file(path)
    overlaps=STATE[STATE.geometry.intersects(shape)].copy()
    overlaps['fraction']=overlaps.geometry.intersection(shape).area/overlaps.geometry.area
    result['footprints'][region]={'features':len(frame),'crs':str(frame.crs),'valid_features':int(frame.is_valid.sum()),'geometry_types':frame.geom_type.value_counts().to_dict(),'intersecting_states':{str(r.STUSPS):round(float(r.fraction),3) for _,r in overlaps.iterrows() if r.fraction > .001}}
    path=DATA/f'vectors/{region.lower()}_padus_protected_areas.gpkg'
    # Read all geometries, not only attributes, to verify validity and spatial coverage.
    f=gpd.read_file(path)
    result['protected'][region]={'features':len(f),'crs':str(f.crs),'valid_geometries':int(f.is_valid.sum()),'empty_geometries':int(f.geometry.is_empty.sum()),'missing_geometries':int(f.geometry.isna().sum()),'categories':{str(k):int(v) for k,v in f.Category.fillna('missing').value_counts().items()},'gap_status':{str(k):int(v) for k,v in f.GAP_Sts.fillna('missing').value_counts().items()},'note':'Feature counts are not counts of unique legal boundaries; records can overlap or describe different designations.'}
result['state_counts']={'census_features':len(STATE),'us_states_and_territories':[str(x) for x in sorted(STATE.STUSPS)],'crs':'EPSG:5070','source':'2025 Census 1:20m generalized state boundaries'}
result['notes']=['MISO footprint is a 2021 public service territory polygon, not a legal franchise, land ownership, or all actual project geography.','NYISO footprint is the Census New York state shape, an approximation rather than a validated operational footprint.','PAD-US is a protected-areas database; the polygons include a variety of designations, ownership and management types and may overlap.','No parcel, tribal, floodplain, cultural or legal property easements boundary datasets are included.']
out=Path(__file__).parent/'boundary_audit.json'
out.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
