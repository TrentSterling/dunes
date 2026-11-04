import {chromium} from 'playwright-core';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const base=(process.env.DUNES_URL||'http://127.0.0.1:5189').replace(/\/$/,'');
const out=process.env.DUNES_OUTPUT||'artifacts/dust-rider/dust';fs.mkdirSync(out,{recursive:true});
const report={url:base,checks:[],errors:[]};const pass=t=>{report.checks.push(t);console.log('PASS',t);};
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--ignore-gpu-blocklist']});
const p=await browser.newPage({viewport:{width:3840,height:2160},deviceScaleFactor:1});p.on('pageerror',e=>report.errors.push(e.message));
try{
 await p.addInitScript(()=>{localStorage.setItem('glamis-settings-v1',JSON.stringify({quality:'ultra',car:'pro',proCarV:1,aiCount:0,radarGpuV:1}));window.__raf=requestAnimationFrame.bind(window);window.requestAnimationFrame=callback=>window.__pauseFrames?0:window.__raf(callback);});
 await p.goto(base+'/?room=dust-qa-'+Date.now());await p.waitForFunction(()=>window.__frames>30,null,{timeout:180000});
 report.targets=await p.evaluate(()=>__game.dustRenderer.stats);assert.equal(report.targets.width,3840);assert.equal(report.targets.height,2160);assert.equal(report.targets.dustWidth,960);assert.equal(report.targets.dustHeight,540);pass('4K world and HUD use a 960 x 540 soft-dust target');
 report.clearColor=await p.evaluate(()=>{
  const g=__game,gl=g.renderer.getContext(),pixels=[];g.particles.dust.geo.instanceCount=0;g.particles.grains.geo.instanceCount=0;
  for(const enabled of [false,true]){g.dustRenderer.enabled=enabled;g.dustRenderer.render(g.scene,g.camera);const a=[];for(let y=200;y<2160;y+=300)for(let x=200;x<3840;x+=300){const v=new Uint8Array(4);gl.readPixels(x,y,1,1,gl.RGBA,gl.UNSIGNED_BYTE,v);a.push(...v.slice(0,3));}pixels.push(a);}
  return {meanDelta:pixels[0].reduce((s,v,i)=>s+Math.abs(v-pixels[1][i]),0)/pixels[0].length,maxDelta:Math.max(...pixels[0].map((v,i)=>Math.abs(v-pixels[1][i])))};
 });assert.ok(report.clearColor.meanDelta<3,JSON.stringify(report.clearColor));pass('Clear-scene colors remain within 3/255 average of the original renderer');
 await p.evaluate(()=>{
  const g=__game,P=g.particles;g.car.update=()=>{};g.car.vel.set(0,0,0);P.emitWheel=()=>{};g.weather.update=()=>{};
  const d=P.dust;d.count=0;let seed=1234;const rand=()=>((seed=Math.imul(seed,1664525)+1013904223|0)>>>0)/4294967296;
  for(let i=0;i<400;i++){const pos=g.car.pos.clone().set((rand()-.5)*10,(rand()-.5)*5,-(2+rand()*16)).applyMatrix4(g.camera.matrixWorld);d.spawn(pos.x,pos.y,pos.z,0,0,0,100,5+rand()*5,0,.9,-10000,.045);d.life[i]=1;}
  P.update(0,g.camera);P.update=()=>{};
  const gl=g.renderer.getContext(),ext=gl.getExtension('EXT_disjoint_timer_query_webgl2');if(!ext)throw Error('GPU timer queries unavailable');
  const original=g.dustRenderer.render.bind(g.dustRenderer);window.__measure={active:false,queries:[],ext};
  g.dustRenderer.render=(...args)=>{const m=__measure;if(m.active){const q=gl.createQuery();gl.beginQuery(ext.TIME_ELAPSED_EXT,q);original(...args);gl.endQuery(ext.TIME_ELAPSED_EXT);m.queries.push(q);if(m.queries.length>=24)m.active=false;}else original(...args);};
 });
 await p.evaluate(async()=>{window.__pauseFrames=true;await new Promise(__raf);await new Promise(__raf);});
 for(const [name,enabled]of [['full',false],['reduced',true]]){
  await p.evaluate(enabled=>{const g=__game,gl=g.renderer.getContext();g.dustRenderer.enabled=enabled;for(let i=0;i<5;i++)g.dustRenderer.render(g.scene,g.camera);gl.finish();__measure.queries=[];__measure.active=true;for(let i=0;i<24;i++){g.dustRenderer.render(g.scene,g.camera);gl.finish();}},enabled);
  await p.waitForFunction(()=>{const gl=__game.renderer.getContext();return __measure.queries.every(q=>gl.getQueryParameter(q,gl.QUERY_RESULT_AVAILABLE));},null,{polling:100});
  report[name]=await p.evaluate(()=>{const gl=__game.renderer.getContext(),m=__measure;if(gl.getParameter(m.ext.GPU_DISJOINT_EXT))throw Error('Disjoint GPU timing');const ms=m.queries.map(q=>{const t=gl.getQueryParameter(q,gl.QUERY_RESULT)/1e6;gl.deleteQuery(q);return t;}).sort((a,b)=>a-b);return {median:ms[ms.length>>1],max:ms.at(-1),samples:ms};});
  await p.screenshot({path:out+'/'+name+'-4k.png'});
 }
 report.speedup=report.full.median/report.reduced.median;assert.ok(report.speedup>1.5,JSON.stringify({full:report.full.median,reduced:report.reduced.median}));pass('Identical 400-puff trail is at least 1.5x faster including world render and compositing');
 // A hard foreground object must occlude every part of the dust behind it.
 report.occlusion=await p.evaluate(async()=>{
  const THREE=await import('three'),g=__game,c=g.camera,gl=g.renderer.getContext();const mesh=new THREE.Mesh(new THREE.PlaneGeometry(.7,.9),new THREE.MeshBasicMaterial({color:0x2255ff}));
  mesh.position.set(0,0,-1.5).applyMatrix4(c.matrixWorld);mesh.quaternion.copy(c.quaternion);g.scene.add(mesh);
  const edge=new THREE.Vector3(.35,0,-1.5).applyMatrix4(c.matrixWorld).project(c);const right=Math.floor((edge.x*.5+.5)*3840),points=[1920,right-2,right-5,right-10];
  const values=[];for(const count of [0,400]){g.particles.dust.geo.instanceCount=count;g.dustRenderer.render(g.scene,c);values.push(points.map(x=>{const px=new Uint8Array(4);gl.readPixels(x,1080,1,1,gl.RGBA,gl.UNSIGNED_BYTE,px);return [...px];}));}
  window.__occluder=mesh;return {points,without:values[0],with:values[1]};
 });assert.deepEqual(report.occlusion.with,report.occlusion.without);pass('Foreground geometry occludes dust at its center and within two pixels of its edge');
 await p.screenshot({path:out+'/occlusion-4k.png'});await p.evaluate(()=>{__game.scene.remove(__occluder);__occluder.geometry.dispose();__occluder.material.dispose();});
 await p.setViewportSize({width:1440,height:900});await p.waitForFunction(()=>__game.renderer.domElement.width===1440,null,{polling:100});await p.evaluate(()=>__game.dustRenderer.render(__game.scene,__game.camera));report.resized=await p.evaluate(()=>__game.dustRenderer.stats);assert.equal(report.resized.dustWidth,720);pass('Dust targets resize with the viewport');
 assert.deepEqual(report.errors,[]);report.passed=true;
}catch(e){report.passed=false;report.failure=e.stack;process.exitCode=1;await p.screenshot({path:out+'/failure.png'}).catch(()=>{});}
finally{report.verifiedUtc=new Date().toISOString();fs.writeFileSync(out+'/dust.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));await browser.close();}
