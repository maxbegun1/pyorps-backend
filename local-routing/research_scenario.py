"""Research-only quarterly competing-risk scenario scoring for saved candidates."""
from pathlib import Path
import argparse
import json
import joblib
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent

def score(region, technology, capacity_mw, age_quarters=1):
    if region not in ('MISO','NYISO'):
        raise ValueError('Region must be MISO or NYISO')
    if technology not in ('Solar','Wind','Gas','Battery','Solar+Battery','Other'):
        raise ValueError('Technology must match one of the listed categories')
    if not np.isfinite(capacity_mw) or capacity_mw <= 0 or age_quarters < 1:
        raise ValueError('Capacity and age must be positive')
    bundle = joblib.load(HERE / f'{region.lower()}-quarterly-research.joblib')
    model = bundle['model']
    remaining, withdrawal, event = 1.0, 0.0, 0.0
    rows = []
    for q in range(1,21):
        x = pd.DataFrame({'age':[age_quarters+q-1], 'mw':[np.log1p(capacity_mw)], 'tech':[technology]})
        p = model.predict_proba(x)[0]
        hazards = np.zeros(3)
        hazards[model[-1].classes_.astype(int)] = p
        withdrawal += remaining*hazards[1]
        event += remaining*hazards[2]
        remaining *= hazards[0]
        rows.append({'quarter':q, 'unresolved':remaining, 'withdrawal':withdrawal, 'event':event})
    return {'region':region, 'model':bundle['model_name'], 'training_last_quarter_start':bundle['cutoff'],
            'outcome':'IA' if region=='MISO' else 'IA or operation', 'research_only':True,
            'limitations':'Not validated for deployment; historical feature vintages and censoring remain uncertain.',
            'scenario':{'technology':technology,'capacity_mw':capacity_mw,'age_quarters':age_quarters},'quarters':rows}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--region',choices=['MISO','NYISO'],required=True)
    p.add_argument('--technology',choices=['Solar','Wind','Gas','Battery','Solar+Battery','Other'],required=True)
    p.add_argument('--mw',type=float,required=True);p.add_argument('--age-quarters',type=int,default=1)
    a=p.parse_args();print(json.dumps(score(a.region,a.technology,a.mw,a.age_quarters),indent=2))
