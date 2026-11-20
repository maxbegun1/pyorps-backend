(function(root){
'use strict';
function hazards(model, scenario){
 const {age,capacityMw,technology}=scenario;
 if(!Number.isFinite(age)||age<1||!Number.isInteger(age)||!Number.isFinite(capacityMw)||capacityMw<=0||!model.categories.includes(technology))throw new Error('Choose a supported technology and enter a positive project capacity.');
 const x=[(age-model.mean[0])/model.scale[0],(Math.log1p(capacityMw)-model.mean[1])/model.scale[1],...model.categories.map(c=>Number(c===technology))];
 const raw=model.baseline.slice();
 for(const iteration of model.trees)for(let k=0;k<iteration.length;k++){
  const nodes=iteration[k];let i=0;
  while(!nodes[i][0]){const n=nodes[i],v=x[n[2]];i=Number.isNaN(v)?(n[6]?n[4]:n[5]):(v<=n[3]?n[4]:n[5]);}
  raw[k]+=nodes[i][1];
 }
 const max=Math.max(...raw),exps=raw.map(v=>Math.exp(v-max)),den=exps.reduce((a,b)=>a+b,0),result=[0,0,0];
 for(let i=0;i<model.classes.length;i++)result[model.classes[i]]=exps[i]/den;
 return result;
}
function curve(model,scenario,quarters=20){let stay=1,event=0,withdrawal=0,rows=[{quarter:0,event,withdrawal,stay}];for(let i=0;i<quarters;i++){const [s,w,e]=hazards(model,{...scenario,age:scenario.age+i});event+=stay*e;withdrawal+=stay*w;stay*=s;rows.push({quarter:i+1,event,withdrawal,stay})}return rows}
const api={hazards,curve};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ScenarioModels=api;
})(typeof globalThis==='undefined'?this:globalThis);
