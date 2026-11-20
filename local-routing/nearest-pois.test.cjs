const {test}=require('node:test');const assert=require('node:assert/strict');const {nearestPois}=require('./nearest-pois.js');
test('nearest POIs use geographic distance and ignore invalid locations',()=>{const r=nearestPois([{name:'far',latitude:41,longitude:-89},{name:'near',latitude:40.16454,longitude:-89.38829},{name:'invalid',latitude:null,longitude:0}],-89.3978373,40.1681863);assert.equal(r[0].name,'near');assert.ok(Math.abs(r[0].distance_miles-.564)<.002);assert.equal(r.length,2)});
test('invalid project locations are rejected',()=>assert.throws(()=>nearestPois([],181,40)));
