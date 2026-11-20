(function(root){
'use strict';
function nearestPois(pois,lon,lat,limit=5){
 if(!Number.isFinite(lon)||!Number.isFinite(lat)||Math.abs(lon)>180||Math.abs(lat)>90)throw new Error('Enter a valid project location.');
 const rad=Math.PI/180, a=lat*rad;
 return pois.filter(p=>Number.isFinite(p.latitude)&&Number.isFinite(p.longitude)).map(p=>{const b=p.latitude*rad,dy=b-a,dx=(p.longitude-lon)*rad,h=Math.sin(dy/2)**2+Math.cos(a)*Math.cos(b)*Math.sin(dx/2)**2;return {...p,distance_miles:Math.round(3958.7613*2*Math.asin(Math.min(1,Math.sqrt(h)))*1000)/1000}}).sort((x,y)=>x.distance_miles-y.distance_miles).slice(0,limit);
}
if(typeof module!=='undefined'&&module.exports)module.exports={nearestPois};else root.nearestPois=nearestPois;
})(typeof globalThis==='undefined'?this:globalThis);
