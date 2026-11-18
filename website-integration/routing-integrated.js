(() => {
  'use strict';
  const map = document.getElementById('map');
  const toolbar = document.querySelector('.toolbar');
  const button = document.createElement('button');
  button.textContent = 'Route a line';
  button.setAttribute('aria-expanded', 'false');
  toolbar.append(button);
  const panel = document.createElement('aside');
  panel.className = 'route-inline-panel';
  panel.hidden = true;
  panel.innerHTML = `<h2>Transmission routing</h2><p>Click a start point, then a destination on this map. Drag to move the map.</p><p id="route-points">No points selected.</p><label>Line voltage <select id="route-voltage"><option value="69">69 kV</option><option value="115">115 kV</option><option value="138">138 kV</option><option value="230">230 kV</option><option value="345" selected>345 kV</option></select></label><div class="route-actions"><button id="route-calculate" disabled>Calculate</button><button id="route-clear">Clear</button></div><p id="route-status" role="status" aria-live="polite"></p><p class="route-note">Planning estimate only. Land weights and costs are assumptions; verify siting and interconnection. <a href="/routing">Open detailed routing and nearest POIs</a></p>`;
  document.getElementById('map-frame').append(panel);
  const get = id => panel.querySelector('#' + id);
  const layer = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  layer.setAttribute('pointer-events', 'none');
  map.append(layer);
  const points = [];
  let busy = false, down = null;
  const project = (lon, lat) => { const p = Math.max(-85.05112878, Math.min(85.05112878, lat)) * Math.PI / 180; return [(lon + 180) / 360 * 4096, (1 - Math.log(Math.tan(p) + 1 / Math.cos(p)) / Math.PI) / 2 * 4096]; };
  const unproject = (x, y) => [x / 4096 * 360 - 180, Math.atan(Math.sinh(Math.PI * (1 - 2 * y / 4096))) * 180 / Math.PI];
  function marker(point, color) { const [x,y] = project(...point); const c = document.createElementNS('http://www.w3.org/2000/svg','circle'); c.setAttribute('cx',x); c.setAttribute('cy',y); c.setAttribute('r', Number(map.viewBox.baseVal.width) * .008); c.setAttribute('fill',color); c.setAttribute('stroke','white'); c.setAttribute('stroke-width','2'); c.setAttribute('vector-effect','non-scaling-stroke'); c.dataset.routeMarker = '1'; layer.append(c); }
  function markers() { layer.querySelectorAll('[data-route-marker]').forEach(c => c.remove()); points.forEach((p,i)=>marker(p,i?'#e66e36':'#00b574')); }
  function update() { get('route-points').textContent = points.length ? points.map((p,i)=>`${i?'End':'Start'}: ${p[1].toFixed(5)}, ${p[0].toFixed(5)}`).join(' • ') : 'No points selected.'; get('route-calculate').disabled = busy || points.length !== 2; get('route-clear').disabled = busy; get('route-voltage').disabled = busy; markers(); }
  button.onclick = () => { panel.hidden = !panel.hidden; button.setAttribute('aria-expanded',String(!panel.hidden)); };
  get('route-clear').onclick = () => { points.length = 0; layer.replaceChildren(); get('route-status').textContent = ''; update(); };
  map.addEventListener('pointerdown', e => { down = [e.clientX,e.clientY]; }, true);
  map.addEventListener('click', e => { if (panel.hidden || busy || !down || Math.hypot(e.clientX-down[0],e.clientY-down[1]) > 4) return; const matrix=map.getScreenCTM(); if (!matrix) return; e.stopImmediatePropagation(); const p=map.createSVGPoint(); p.x=e.clientX; p.y=e.clientY; const position=p.matrixTransform(matrix.inverse()); if(points.length===2){points.length=0;layer.replaceChildren();} points.push(unproject(position.x,position.y)); get('route-status').textContent = points.length===1 ? 'Click the destination.' : 'Ready to calculate.'; update(); }, true);
  new MutationObserver(() => { for(const c of layer.querySelectorAll('[data-route-marker]')) c.setAttribute('r',Number(map.viewBox.baseVal.width)*.008); }).observe(map,{attributes:true,attributeFilter:['viewBox']});
  get('route-calculate').onclick = async () => { if(points.length!==2 || busy)return; busy=true; update(); get('route-status').textContent='Calculating route. The first request can take a little longer.'; try { const response=await fetch('https://pyorps-backend.onrender.com/route',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({start:points[0],end:points[1],voltage_kv:Number(get('route-voltage').value)})}); const data=await response.json(); if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:'Route calculation failed'); layer.replaceChildren(); for(const f of data.features) { if(f.geometry.type!=='LineString') continue; const path=document.createElementNS('http://www.w3.org/2000/svg','path'); path.setAttribute('d',f.geometry.coordinates.map((p,i)=>{const [x,y]=project(...p);return `${i?'L':'M'}${x},${y}`;}).join('')); path.setAttribute('fill','none'); path.setAttribute('stroke','#f8a820'); path.setAttribute('stroke-width','4'); path.setAttribute('vector-effect','non-scaling-stroke'); layer.append(path); } const estimate=data.estimate; const cost=estimate.line_cost_usd == null?'cost unavailable':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(estimate.line_cost_usd); get('route-status').textContent=`${estimate.line_voltage_kv} kV · ${estimate.route_miles.toFixed(3)} miles · ${cost} estimated line cost`; } catch(error) { get('route-status').textContent=error.message || 'Could not reach the routing service.'; } finally { busy=false; update(); } };
})();
