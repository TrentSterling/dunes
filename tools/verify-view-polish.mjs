import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const base=(process.env.DUNES_URL||'http://127.0.0.1:5189').replace(/\/$/,'');
const out=process.env.DUNES_OUTPUT||'artifacts/labels-performance/verified';fs.mkdirSync(out,{recursive:true});
const report={url:base,checks:[],samples:[],errors:[],failedRequests:[]};
const pass=text=>{report.checks.push(text);console.log('PASS',text);};
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--ignore-gpu-blocklist']});
const page=await browser.newPage({viewport:{width:1440,height:900}});
page.on('pageerror',e=>report.errors.push(e.message));
page.on('requestfailed',r=>{if(!r.url().startsWith('wss:'))report.failedRequests.push(r.url());});
async function frames(n=5){await page.evaluate(async n=>{for(let i=0;i<n;i++)await new Promise(requestAnimationFrame);},n);}
async function sample(key,value,n=50){
  const result=await page.evaluate(async({key,value,n})=>{
    const g=__game,compiles=__compiles,version=g.terrain.material.version,captures=g.lightingStats.captures;
    const start=performance.now();g.setSetting(key,value);const setter=performance.now()-start;
    const times=[];let last=start;
    for(let i=0;i<n;i++){await new Promise(requestAnimationFrame);const now=performance.now();times.push(now-last);last=now;}
    return {key,value,setter,max:Math.max(...times),median:[...times].sort((a,b)=>a-b)[n>>1],compiles:__compiles-compiles,captures:g.lightingStats.captures-captures,terrainVersions:g.terrain.material.version-version};
  },{key,value,n});report.samples.push(result);return result;
}
try{
  await page.addInitScript(()=>{
    localStorage.setItem('glamis-settings-v1',JSON.stringify({quality:'ultra',car:'pro',proCarV:1,aiCount:4,radarGpuV:1,showHelp:false}));
    window.__compiles=0;window.__lateCompiles=[];const compile=WebGL2RenderingContext.prototype.compileShader;
    WebGL2RenderingContext.prototype.compileShader=function(...args){window.__compiles++;if(window.__game?.warmup.ready)window.__lateCompiles.push({frame:window.__frames||0,source:this.getShaderSource(args[0])});return compile.apply(this,args);};
  });
  await page.goto(`${base}/?room=view-polish-${Date.now()}`,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__game?.warmup.ready&&window.__frames>40,null,{timeout:180000});
  report.gpu=await page.evaluate(()=>{const gl=__game.renderer.getContext(),ext=gl.getExtension('WEBGL_debug_renderer_info');return {renderer:ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):'',warmup:__game.warmup,reversed:__game.renderer.capabilities.reversedDepthBuffer};});
  assert.equal(report.gpu.warmup.cameras,5);assert.ok(report.gpu.warmup.mirrors>=3);
  report.lateCompiles=await page.evaluate(()=>window.__lateCompiles);assert.equal(report.lateCompiles.length,0,'Unexpected shader compilation after loading');
  pass('All five camera modes and mirror targets are prepared before driving starts');
  for(const mode of [1,2,3,4,0,2]){
    const s=await sample('camMode',mode);assert.equal(s.compiles,0,JSON.stringify(s));assert.ok(s.max<100,JSON.stringify(s));
  }
  pass('First and repeated camera changes compile no shaders and stay below a 100 ms frame gap');
  for(const hour of [8,12,18,8]){
    const s=await sample('tod',hour);assert.equal(s.captures,1);assert.equal(s.terrainVersions,0);assert.ok(s.max<100,JSON.stringify(s));
  }
  for(const night of [true,false]){const s=await sample('night',night);assert.ok(s.max<100,JSON.stringify(s));}
  pass('Daylight and night changes refresh lighting without rebuilding terrain materials or a 100 ms stall');
  report.coalescing=await page.evaluate(async()=>{const g=__game,before=g.lightingStats.captures;for(let i=0;i<12;i++)g.setSetting('tod',8+i*.1);for(let i=0;i<30;i++)await new Promise(requestAnimationFrame);return {captures:g.lightingStats.captures-before,hour:g.settings.tod};});
  assert.equal(report.coalescing.captures,1);assert.ok(Math.abs(report.coalescing.hour-9.1)<.0001);
  pass('A rapid burst of time changes captures only the latest lighting state');
  // The exported production projector is tested with both depth conventions.
  report.projection=await page.evaluate(async()=>{
    const THREE=await import('three'),{placeDriverLabel}=await import('./js/driver-label.js');const result=[];
    for(const reversed of [false,true]){
      const c=new THREE.PerspectiveCamera(62,1,.15,1000);c._reversedDepth=reversed;c.updateProjectionMatrix();c.updateMatrixWorld();
      if(c.reversedDepth!==reversed)throw Error('Depth test configuration failed');
      for(const [name,x,y,z,expected]of [['front',0,0,-20,true],['behind',0,0,20,false],['near',0,0,-.01,false],['far',0,0,-1001,false],['left',-200,0,-20,false],['right',200,0,-20,false],['above',0,200,-20,false],['below',0,-200,-20,false]]){
        const label={};placeDriverLabel(label,new THREE.Vector3(x,y-2.2,z),c,true,name,1000,1000);result.push({reversed,name,expected,...label});
      }
      c.rotation.y=Math.PI;c.updateMatrixWorld();const label={};placeDriverLabel(label,new THREE.Vector3(0,-2.2,20),c,true,'turned',1000,1000);result.push({reversed,name:'turned',expected:true,...label});
    }return result;
  });
  for(const p of report.projection){assert.equal(p.visible,p.expected,JSON.stringify(p));if(p.visible){assert.ok(Math.abs(p.x-500)<.001);assert.ok(Math.abs(p.y-500)<.001);}}
  pass('Front/behind, near/far, viewport edges and a turned camera project correctly with both depth conventions');
  // Freeze two QA bots around the current view, then rotate every frame.
  await page.evaluate(()=>{const g=__game;g.setSetting('camMode',0);for(const b of g.bots)b.update=()=>{};g.car.update=()=>{};g.car.vel.set(0,0,0);});await frames();
  await page.evaluate(()=>{const g=__game,c=g.camera;const front=g.car.pos.clone().set(0,0,-35).applyMatrix4(c.matrixWorld);front.y-=2.2;const back=g.car.pos.clone().set(0,0,35).applyMatrix4(c.matrixWorld);back.y-=2.2;g.bots[0].car.pos.copy(front);g.bots[1].car.pos.copy(back);g.bots[0].name='FRONT QA';g.bots[1].name='BEHIND QA';for(const b of g.bots.slice(2))b.car.pos.addScalar(5000);});await frames();
  assert.ok(await page.evaluate(()=>{const g=__game;return g.bots[0].label.visible&&!g.bots[1].label.visible&&g.ui.frameText.filter(t=>t.startsWith('FRONT QA')).length===1&&!g.ui.frameText.some(t=>t.startsWith('BEHIND QA'));}));
  await page.screenshot({path:out+'/tags-front.png'});
  report.tracking=await page.evaluate(async()=>{
    const g=__game;let visible=0,maxError=0,behind=0;
    for(let i=0;i<40;i++){
      g.setOrbit(Math.sin(i*.25)*2,0,1);await new Promise(requestAnimationFrame);
      for(const b of g.bots){if(!b.label.visible)continue;visible++;const p=b.car.pos.clone();p.y+=2.2;const v=p.clone().applyMatrix4(g.camera.matrixWorldInverse);if(v.z>=0)behind++;p.project(g.camera);maxError=Math.max(maxError,Math.hypot(b.label.x-(p.x*.5+.5)*innerWidth,b.label.y-(-p.y*.5+.5)*innerHeight));}
    }return {visible,maxError,behind};
  });
  assert.ok(report.tracking.visible>5);assert.equal(report.tracking.behind,0);assert.ok(report.tracking.maxError<.01,JSON.stringify(report.tracking));
  pass('Actual bot tags draw once, reject the car behind the camera and track the same frame during orbit');
  await page.evaluate(()=>{__game.setOrbit(0,0,1);__game.setSetting('labels',false);});await frames();
  assert.ok(await page.evaluate(()=>[...__game.ui.labels].every(l=>!l.visible)));await page.evaluate(()=>__game.setSetting('labels',true));await frames();
  await page.keyboard.press('KeyH');await frames();assert.ok(await page.evaluate(()=>!__game.ui.frameText.some(t=>t.includes('FRONT QA'))));await page.keyboard.press('KeyH');
  pass('Name-tag and HUD visibility controls still hide the GPU labels');
  await page.setViewportSize({width:390,height:844});await frames();await page.screenshot({path:out+'/tags-compact.png'});
  await page.setViewportSize({width:1440,height:900});await page.evaluate(()=>__game.setSetting('camMode',2));await frames();await page.screenshot({path:out+'/cockpit.png'});
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.failedRequests,[]);report.passed=true;
}catch(e){report.passed=false;report.failure=e.stack;report.lateCompiles=await page.evaluate(()=>window.__lateCompiles).catch(()=>[]);process.exitCode=1;await page.screenshot({path:out+'/failure.png'}).catch(()=>{});}
finally{report.verifiedUtc=new Date().toISOString();fs.writeFileSync(out+'/view-polish.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({passed:report.passed,checks:report.checks.length,maxFrame:Math.max(...report.samples.map(s=>s.max)),failure:report.failure,errors:report.errors,receipt:out+'/view-polish.json'},null,2));await browser.close();}
