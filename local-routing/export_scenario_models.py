"""Export trusted sklearn histogram models and independently generated inference fixtures."""
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
models={};fixtures=[]
for region in ['MISO','NYISO']:
 bundle=joblib.load(HERE/f'{region.lower()}-quarterly-research.joblib');pipeline=bundle['model'];prep,model=pipeline[0],pipeline[1]
 numeric=prep.named_transformers_['num']; cats=prep.named_transformers_['tech'].categories_[0].tolist()
 trees=[]
 for iteration in model._predictors:
  group=[]
  for tree in iteration:
   nodes=[]
   for n in tree.nodes:
    if int(n['is_categorical']):raise ValueError('Categorical tree split is not supported')
    nodes.append([int(n['is_leaf']),float(n['value']),int(n['feature_idx']),float(n['num_threshold']),int(n['left']),int(n['right']),int(n['missing_go_to_left'])])
   group.append(nodes)
  trees.append(group)
 models[region]={'model_name':bundle['model_name'],'training_last_quarter_start':bundle['cutoff'],'data_through':'2025-12-31','outcome':'IA' if region=='MISO' else 'IA or operation','mean':numeric[1].mean_.tolist(),'scale':numeric[1].scale_.tolist(),'categories':cats,'baseline':model._baseline_prediction[0].tolist(),'classes':model.classes_.tolist(),'trees':trees}
 for age in [1,4,8,16,32]:
  for technology in ['Solar','Wind','Gas','Battery','Solar+Battery','Wind+Battery','Other']:
   for mw in [10,50,100,200,500]:
    X=pd.DataFrame({'age':[age],'mw':[np.log1p(mw)],'tech':[technology]})
    fixtures.append({'region':region,'age':age,'technology':technology,'mw':mw,'expected':pipeline.predict_proba(X)[0].tolist()})
(HERE/'scenario-models.json').write_text(json.dumps(models,separators=(',',':')),encoding='utf-8')
(HERE/'scenario-model-fixtures.json').write_text(json.dumps(fixtures,separators=(',',':')),encoding='utf-8')
print('Exported',len(fixtures),'quarterly fixtures and',len(models),'models')
