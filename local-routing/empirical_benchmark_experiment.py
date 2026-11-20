from pathlib import Path
import sys,json,warnings
import numpy as np,pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
import joblib
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss
warnings.filterwarnings('ignore')
base=Path(r'C:\Users\mbbeg\OneDrive\Desktop\Energy\miso-prediction-fix\regional_models')
sys.path.insert(0,str(base/'MISO'/'dynamic_ia'))
import train as miso
out=[]
scenario_changes=[]
MODELS=["empirical_age"]
def prep(region):
 if region=='MISO':
  d,_=miso.prepare(base/'MISO'/'data'/'MISO_panel_operational_ready.csv');d=d[d.observed].copy(); d['y']=d.target
 else:
  d=pd.read_csv(base/'NYISO'/'data'/'NYISO_panel_model_ready.csv',low_memory=False);d=d[d.model_eligible.astype(str).str.lower().eq('true')].copy(); d['quarter_start']=pd.to_datetime(d.quarter_start);d['y']=d.transition_outcome.map({'stay':0,'withdraw':1,'IA/operational':2});d=d[d.y.notna()].copy()
 d['q_date']=pd.to_datetime(d.q_date,errors='coerce');d['quarter_start']=pd.to_datetime(d.quarter_start);d['age_quarters']=pd.to_numeric(d.age_quarters,errors='coerce');d['project_mw']=pd.to_numeric(d.project_mw,errors='coerce');d['type_clean']=d.type_clean.fillna('Unknown').astype(str);d=d.dropna(subset=['q_date','quarter_start','age_quarters']);d=d.sort_values(['project_id','quarter_start']).drop_duplicates(['project_id','quarter_start']);return d

def features(d):
 x=pd.DataFrame(index=d.index); x['age']=pd.to_numeric(d.age_quarters);x['mw']=np.log1p(pd.to_numeric(d.project_mw,errors='coerce').clip(lower=0));x['tech']=d.type_clean.fillna('Unknown').astype(str);return x

class Empirical:
 def __init__(self,d,region):
  self.classes_=np.array([0,1,2]);self.region=region
  if region=='MISO':
   d=d[d.quarter_start>=pd.Timestamp('2013-01-01')]; self.limits=[4,8,16,32];self.side='right'; bucket=np.searchsorted(self.limits,d.age_quarters.to_numpy(),side=self.side);y=d.y.astype(int).to_numpy();global_counts=np.bincount(y,minlength=3);base=(global_counts+1)/(global_counts.sum()+3); self.rates=np.array([(np.bincount(y[bucket==i],minlength=3)+20*base)/(sum(bucket==i)+20) for i in range(5)])
  else:
   self.limits=[1,2,3,4,8,12,20];self.side='left';bucket=np.searchsorted(self.limits,d.age_quarters.to_numpy(),side=self.side);y=d.y.astype(int).to_numpy();self.rates=np.array([(np.bincount(y[bucket==i],minlength=3)+np.array([1,.5,.5]))/(sum(bucket==i)+2) for i in range(8)])
 def __getitem__(self,i):return self
 def predict_proba(self,x):return self.rates[np.searchsorted(self.limits,x.age.to_numpy(),side=self.side)]
def fit(d,kind):
 if kind=='empirical_age':return Empirical(d,ACTIVE_REGION)
 cols=['age'] if kind=='age_logit' else ['age','mw']; transformers=[('num',make_pipeline(SimpleImputer(strategy='median'),StandardScaler()),cols)]
 if kind!='age_logit':transformers.append(('tech',OneHotEncoder(handle_unknown='ignore',sparse_output=False),['tech']))
 if kind=='age_logit': estimator=LogisticRegression(max_iter=500,C=.1)
 elif kind.startswith('logit_'): estimator=LogisticRegression(max_iter=500,C={'logit_c001':.01,'logit_c01':.1,'logit_c1':1.0}[kind])
 elif kind.startswith('forest_'): estimator=RandomForestClassifier(n_estimators=120,min_samples_leaf=20 if kind=='forest_leaf20' else 50,max_features=.8,n_jobs=1,random_state=42)
 else:
  configs={'tree_shallow':(5,150,20),'tree_regular':(7,100,10),'tree_deep':(15,100,10),'tree_leaf50':(7,50,10)}
  leaves,minleaf,reg=configs[kind];estimator=HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=leaves,min_samples_leaf=minleaf,l2_regularization=reg,random_state=42)
 m=make_pipeline(ColumnTransformer(transformers),estimator);m.fit(features(d),d.y.astype(int));return m

def predict(m,landmark):
 n=len(landmark);surv=np.ones(n);inc=np.zeros((n,2));allrows={}; x=landmark.copy()
 for q in range(1,21):
  p=m.predict_proba(features(x));classes=m[-1].classes_; a=np.zeros((n,3));a[:,classes]=p;inc+=surv[:,None]*a[:,1:3];surv*=a[:,0];
  if q in (4,8,12,20):allrows[q]=np.column_stack([surv,inc]);
  x['age_quarters']+=1
 return allrows

def evaluate(region,d,year):
 start=pd.Timestamp(year,1,1);stop=pd.Timestamp(year+1,1,1);train=d[d.quarter_start<start]; x=d[d.quarter_start.eq(start)].drop_duplicates('project_id').copy();
 if len(x)<30 or len(train)<300:return
 ev=d[d.y.isin([1,2])].drop_duplicates('project_id').set_index('project_id'); last=d.groupby('project_id').quarter_start.max();x['eventq']=x.project_id.map(ev.quarter_start);x['event']=x.project_id.map(ev.y);x['lastq']=x.project_id.map(last)
 for kind in MODELS:
  m=fit(train,kind); pred=predict(m,x)
  if year==2020 and kind!='age_logit':
   solar=x[x.type_clean.str.contains('solar',case=False)].head(1)
   if not solar.empty:
    for tech,mw in [('Solar',50),('Solar',100),('Solar',200),('Wind',100)]:
     scenario=solar.copy();scenario['type_clean']=tech;scenario['project_mw']=mw; scenarios=predict(m,scenario)
     scenario_changes.append({'region':region,'origin':year,'model':kind,'technology':tech,'mw':mw,'probabilities':{str(q):{'unresolved':float(probs[0,0]),'withdrawal':float(probs[0,1]),'event':float(probs[0,2])} for q,probs in scenarios.items()}})
  for q,p in pred.items():
   end=x.quarter_start+pd.DateOffset(months=3*q);occur=x.eventq.notna() & (x.eventq<end);eligible=occur | (x.lastq>=end-pd.DateOffset(months=3)); y=np.where(occur,x.event.fillna(0),0).astype(int); mask=(eligible & (end <= d.quarter_start.max())).to_numpy();
   for group,gm in [('all',np.ones(len(x),bool)),('solar',x.type_clean.str.contains('solar',case=False).to_numpy()),('wind',x.type_clean.str.contains('wind',case=False).to_numpy()),('small <=100 MW',(x.project_mw<=100).to_numpy()),('large >100 MW',(x.project_mw>100).to_numpy())]:
    take=mask & gm
    if take.sum()<20:continue
    yt=y[take];pt=p[take]; row={'region':region,'origin':year,'landmark':'queued at start of quarter','model':kind,'horizon_years':q/4,'group':group,'n':int(take.sum()),'events':int((yt==2).sum()),'withdrawals':int((yt==1).sum()),'multiclass_brier':float(np.mean(np.sum((np.eye(3)[yt]-pt)**2,axis=1))),'log_loss':float(log_loss(yt,pt,labels=[0,1,2]))}
    for code,name in [(1,'withdrawal'),(2,'event')]:
     yy=yt==code;row[name+'_observed']=float(np.mean(yy));row[name+'_predicted']=float(np.mean(pt[:,code]));row[name+'_brier']=float(brier_score_loss(yy,pt[:,code]));row[name+'_auc']=float(roc_auc_score(yy,pt[:,code])) if 0<sum(yy)<len(yy) else None
    out.append(row)

for region in ['MISO','NYISO']:
 ACTIVE_REGION=region; d=prep(region)
 for year in [2016,2018,2020,2022,2023]: evaluate(region,d,year)
Path('empirical-benchmark-evaluation.json').write_text(json.dumps({'results':out},indent=2),encoding='utf-8')
print('baseline rows',len(out))
