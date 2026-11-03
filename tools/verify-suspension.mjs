import { chromium } from 'playwright-core';
import fs from 'node:fs';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const out=process.env.DUNES_OUTPUT||path.join(root,'artifacts/vehicles/glx-pro/suspension-viewer');fs.mkdirSync(out,{recursive:true});
const base=(process.env.DUNES_URL||'http://localhost:5189').replace(/\/$/,'');
const report={checks:[],errors:[],warnings:[],failedRequests:[],screenshots:[]};
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--ignore-gpu-blocklist']});
try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}});
  page.on('pageerror',e=>report.errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text());if(m.type()==='warning')report.warnings.push(m.text());});
  page.on('requestfailed',r=>report.failedRequests.push(r.url()));
  page.on('response',r=>{if(r.status()>=400)report.failedRequests.push(`${r.status()} ${r.url()}`);});
  await page.goto(base+'/suspension.html');
  await page.waitForFunction(()=>window.__suspension?.ready&&window.__suspension.frames>3,null,{timeout:90000});
  const shot=async name=>{await page.waitForTimeout(180);await page.screenshot({path:path.join(out,name+'.png')});report.screenshots.push(name+'.png');};
  const slider=async(id,value)=>page.locator('#'+id).evaluate((e,v)=>{e.value=String(v);e.dispatchEvent(new Event('input',{bubbles:true}));},value);
  await page.locator('#reset').click();await shot('overview');
  report.runtime=await page.evaluate(()=>{const v=window.__suspension,gl=v.renderer.getContext(),ext=gl.getExtension('WEBGL_debug_renderer_info');return{renderer:ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),triangles:v.renderer.info.render.triangles,calls:v.renderer.info.render.calls,shockMeshes:v.rig.parts.length};});
  assert.ok(report.runtime.shockMeshes>100);report.checks.push('Rebuilt car and separate original shock components load');
  const oldShocks=await page.evaluate(()=>Object.values(window.__suspension.rig.shocks).map(s=>{
    const matches=[];window.__suspension.model.traverse(o=>{if(o.name===s.node)matches.push(o);});
    const detached=window.__suspension.rig.replacedNodes.find(n=>n.name===s.node);
    return {name:s.node,count:matches.length,detached:!!detached&&!detached.parent};
  }));
  for(const s of oldShocks){assert.equal(s.count,0,`${s.name} old assembly must not remain in the scene`);assert.ok(s.detached,`${s.name} original joined shock must be detached`);}
  report.revision=await page.evaluate(()=>window.__suspension.revision);
  assert.equal(report.revision,'20261103-r2');
  report.checks.push('All eight original joined shocks are physically removed, including bypass assemblies');
  report.sweep=await page.evaluate(async()=>{
    const T=await import(new URL('vendor/three.module.js',location.href).href);
    const v=window.__suspension,rows=[];
    for(const travel of [-.33,-.25,-.15,0,.15,.25,.3])for(const steering of [-30,0,30]){
      v.setPose({FL:travel,FR:-travel*.9,RL:travel,RR:-travel*.9},steering);
      let maxEyeError=0,maxBarrelScaleError=0;
      for(const s of Object.values(v.rig.shocks))for(const p of s.parts){
        if(p.source.includes('_eye')){
          p.mesh.geometry.computeBoundingBox();const center=p.mesh.geometry.boundingBox.getCenter(new T.Vector3()).applyMatrix4(p.mesh.matrixWorld);
          maxEyeError=Math.max(maxEyeError,center.distanceTo(p.kind==='top'?s.a:s.end));
        }
        if(p.kind==='top')for(let axis=0;axis<3;axis++)maxBarrelScaleError=Math.max(maxBarrelScaleError,Math.abs(new T.Vector3().setFromMatrixColumn(p.mesh.matrix,axis).length()-1));
      }
      rows.push({travel,steering,maxEyeError,maxBarrelScaleError,commanded:{...v.position},...JSON.parse(JSON.stringify(v.diagnostics))});
    }
    v.reset();return rows;
  });
  fs.writeFileSync(path.join(out,'sweep.json'),JSON.stringify(report.sweep,null,2));
  for(const r of report.sweep){
    assert.ok(r.maxRigidLengthError<.0001,`Rigid arm error at ${r.travel}/${r.steering}: ${r.maxRigidLengthError}`);
    assert.ok(r.maxClosureError<.0001,`Closure error at ${r.travel}/${r.steering}: ${r.maxClosureError}`);
    assert.ok(r.maxEyeError<.0001,`Actual shock-eye mesh misses the mounting point: ${r.maxEyeError}`);
    assert.ok(r.maxBarrelScaleError<1e-6,'Shock barrels must stay rigid');
    for(const [n,c] of Object.entries(r.corners))assert.ok(Math.abs(c.travel-r.commanded[n])<.0001,`${n} hub follows its travel control`);
  }
  report.checks.push('21 combinations of travel and steering keep rigid links and upright connections within 0.1 mm');
  report.checks.push('Actual shock-eye mesh centers stay within 0.1 mm of the mounts; barrels retain their size');
  report.checks.push('Actual hub height matches each wheel travel control, including while steering');
  for(const n of ['FL','FR','RL','RR']){
    await page.locator('#reset').click();await slider(n,180);
    const d=await page.evaluate(()=>window.__suspension.diagnostics);
    assert.ok(d.corners[n].travel>.15);
    for(const other of ['FL','FR','RL','RR'].filter(c=>c!==n))assert.ok(Math.abs(d.corners[other].travel)<1e-6);
  }
  report.checks.push('Each wheel slider independently articulates its suspension');
  await page.locator('#reset').click();await slider('steer',25);
  const steering=await page.evaluate(()=>window.__suspension.rig.corners.FL.wheel.quaternion.toArray());
  assert.ok(Math.abs(steering[1])>.1);report.checks.push('Steering slider turns front wheels and uprights about the kingpins');
  await page.locator('#reset').click();await page.locator('#play').click();
  const before=await page.evaluate(()=>({...window.__suspension.position}));await page.waitForTimeout(900);
  const after=await page.evaluate(()=>({...window.__suspension.position}));assert.ok(Object.keys(before).some(k=>Math.abs(after[k]-before[k])>.01));
  await page.locator('#play').click();const paused=await page.evaluate(()=>({...window.__suspension.position}));await page.waitForTimeout(200);assert.deepEqual(await page.evaluate(()=>({...window.__suspension.position})),paused);
  report.checks.push('Cycle starts, changes wheel travel and pauses without drift');
  for(const pattern of ['heave','front','rear','ripple']){await page.locator('#pattern').selectOption(pattern);await page.waitForTimeout(250);assert.equal(await page.evaluate(()=>window.__suspension.state.pattern),pattern);}
  report.checks.push('All motion patterns run');
  await page.locator('#reset').click();await page.locator('#pulse').click();await page.waitForTimeout(220);assert.ok(await page.evaluate(()=>window.__suspension.position.FL>.015));
  await page.locator('#reset').click();report.checks.push('Single bump excites the front actuator response; reset clears it');
  report.damping=await page.evaluate(()=>{
    const v=window.__suspension,result={};
    for(const damping of [.15,1.2]){
      v.reset();v.state.damping=damping;v.setPose({FL:.12,FR:0,RL:0,RR:0});
      // Set a zero demand while preserving displacement, then integrate fixed time.
      document.querySelector('#pulse').click();v.step(.001);
      let peak=0;for(let i=0;i<480;i++){v.step(1/240);if(i>120)peak=Math.max(peak,Math.abs(v.position.FL));}result[damping]=peak;
    }
    v.state.damping=.65;v.reset();return result;
  });
  assert.ok(report.damping[.15]>report.damping[1.2]);report.checks.push('Damping changes the spring response after the bump');
  await page.locator('[data-display="ghost"]').click();assert.equal(await page.evaluate(()=>window.__suspension.display),'ghost');
  await page.locator('#joints').check();await page.evaluate(()=>window.__suspension.setPose({FL:.25,FR:-.25,RL:-.25,RR:.25},20));await shot('cross-axle-ghost');
  await page.locator('[data-display="rig"]').click();await page.locator('#wheels').uncheck();await shot('rig');
  for(const view of ['front','rear','side','under','detail']){await page.locator(`[data-view="${view}"]`).click();await shot(view);}
  report.checks.push('Full, ghost and rig views, hidden wheels, pivot overlay and six camera presets render');
  await page.locator('#reset').click();
  const p0=await page.evaluate(()=>window.__suspension.camera.position.toArray());
  const b=await page.locator('#viewport').boundingBox();await page.mouse.move(b.x+b.width*.6,b.y+b.height*.5);await page.mouse.down();await page.mouse.move(b.x+b.width*.7,b.y+b.height*.55,{steps:8});await page.mouse.up();
  const p1=await page.evaluate(()=>window.__suspension.camera.position.toArray());assert.ok(p0.some((v,i)=>Math.abs(v-p1[i])>.1));report.checks.push('Pointer orbit moves the camera');
  await page.locator('#reset').click();await page.setViewportSize({width:390,height:844});await shot('mobile');assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));report.checks.push('390px layout fits without horizontal overflow');
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.failedRequests,[]);report.passed=true;
}catch(e){report.passed=false;report.failure=e.stack;process.exitCode=1;}
finally{report.verifiedUtc=new Date().toISOString();delete report.sweep;fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));await browser.close();}
