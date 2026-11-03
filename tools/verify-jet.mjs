import { chromium } from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const out=path.join(root,'artifacts/vehicles/kestrel/viewer');fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--ignore-gpu-blocklist']});
const report={checks:[],errors:[],warnings:[],failedRequests:[],screenshots:[]};
try {
  const context=await browser.newContext({viewport:{width:1600,height:1000}});
  const page=await context.newPage();
  page.on('pageerror',e=>report.errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text());if(m.type()==='warning')report.warnings.push(m.text());});
  page.on('response',r=>{if(r.status()>=400)report.failedRequests.push(`${r.status()} ${r.url()}`);});
  page.on('requestfailed',r=>report.failedRequests.push(r.url()));
  await page.goto('http://127.0.0.1:5189/jet.html',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__jetViewer?.ready&&window.__jetViewer.frames>5,null,{timeout:90000});
  const shot=async name=>{await page.screenshot({path:path.join(out,name+'.png')});report.screenshots.push(name+'.png');};
  const settle=async()=>page.waitForTimeout(850);
  report.runtime=await page.evaluate(()=>{
    const v=window.__jetViewer,gl=v.renderer.getContext(),ext=gl.getExtension('WEBGL_debug_renderer_info');
    return {triangles:v.metadata.triangles,nodes:[...v.nodes.keys()],
      renderer:ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),
      drawCalls:v.renderer.info.render.calls,dimensions:v.metadata.dimensions};
  });
  assert.ok(report.runtime.nodes.includes('Canopy'));
  assert.ok(report.runtime.nodes.includes('GearMain_L'));
  assert.ok(report.runtime.nodes.includes('Flaperon_R'));
  assert.ok(report.runtime.triangles>10000);
  report.airframeShellTopology=await page.evaluate(()=>window.__jetViewer.metadata.airframeShellTopology);
  assert.deepEqual(report.airframeShellTopology,{boundaryEdges:0,nonManifoldEdges:0});
  report.checks.push('GLB loads with the complete aircraft and named articulated nodes');
  await settle();await shot('hero');
  for(const view of ['top','side','front','rear','cockpit']) {
    await page.locator(`[data-view="${view}"]`).click();await settle();await shot(view);
  }
  report.checks.push('All six camera presets render, including the exported pilot-eye view');
  await page.locator('[data-view="hero"]').click();
  const pose=async name=>page.evaluate(n=>{
    const node=window.__jetViewer.nodes.get(n);return {q:node.quaternion.toArray(),p:node.position.toArray()};
  },name);
  const move=async(id,value)=>{
    await page.locator('#'+id).evaluate((el,v)=>{el.value=String(v);el.dispatchEvent(new Event('input',{bubbles:true}));},value);
    await settle();
  };
  for(const [id,value,node] of [['canopy',1,'Canopy'],['gear',0,'GearMain_L'],['pitch',1,'Stabilator_L'],['roll',1,'Flaperon_R'],['yaw',1,'Rudder'],['burner',1,'NozzlePetal_00']]) {
    const before=await pose(node);await move(id,value);const after=await pose(node);
    assert.ok(after.q.some((v,i)=>Math.abs(v-before.q[i])>.02),`${id} changes ${node}`);
    report.checks.push(`${id} UI slider moves the exported ${node} pivot`);
  }
  await shot('articulated');
  report.stowedGearBounds=await page.evaluate(async()=>{
    const THREE=await import('/vendor/three.module.js');
    return Object.fromEntries(['GearMain_L','GearMain_R','GearNose'].map(name=>{
      const box=new THREE.Box3().setFromObject(window.__jetViewer.nodes.get(name),true);
      return [name,{min:box.min.toArray(),max:box.max.toArray()}];
    }));
  });
  for(const [name,box] of Object.entries(report.stowedGearBounds)) {
    assert.ok(box.min[1]>1.25,`${name} retracts above the ventral skin rather than only rotating`);
  }
  report.checks.push('Stowed landing gear clears 1.25m above the ground');
  await page.locator('#reset').click();await settle();
  const before=await pose('Wing_R');await move('explode',1);const after=await pose('Wing_R');
  assert.ok(Math.hypot(...after.p.map((v,i)=>v-before.p[i]))>1);
  await shot('assembly');report.checks.push('Assembly spread separates original subsystems');
  await page.locator('#reset').click();await settle();
  for(const mode of ['clay','wire','paint']) {
    await page.locator(`[data-material="${mode}"]`).click();
    assert.equal(await page.evaluate(()=>window.__jetViewer.mode),mode);
    await settle();if(mode!=='paint')await shot(mode);
  }
  report.checks.push('Livery, clay and wireframe modes work');
  const start=await page.evaluate(()=>window.__jetViewer.camera.position.toArray());
  await page.locator('#rotate').check();await page.waitForTimeout(1000);await page.locator('#rotate').uncheck();
  const end=await page.evaluate(()=>window.__jetViewer.camera.position.toArray());
  assert.ok(Math.hypot(...start.map((v,i)=>v-end[i]))>.5);
  await page.locator('#grid').check();report.checks.push('Turntable changes the camera and grid control responds');
  await page.locator('#reset').click();await settle();
  const canvas=await page.locator('#viewport').boundingBox();
  const cameraBefore=await page.evaluate(()=>window.__jetViewer.camera.position.toArray());
  await page.mouse.move(canvas.x+canvas.width*.5,canvas.y+canvas.height*.5);
  await page.mouse.down();await page.mouse.move(canvas.x+canvas.width*.6,canvas.y+canvas.height*.53,{steps:10});await page.mouse.up();
  const cameraAfter=await page.evaluate(()=>window.__jetViewer.camera.position.toArray());
  assert.ok(cameraAfter.some((v,i)=>Math.abs(v-cameraBefore[i])>.1));
  report.checks.push('Pointer dragging orbits the model');
  await page.locator('#reset').click();await settle();
  const downloadPromise=page.waitForEvent('download');await page.locator('.download').click();const download=await downloadPromise;
  assert.equal(download.suggestedFilename(),'kestrel-01.glb');
  const dest=path.join(out,'download-check.glb');await download.saveAs(dest);
  assert.equal(fs.statSync(dest).size,fs.statSync(path.join(root,'assets/kestrel/kestrel.glb')).size);
  const hash=file=>createHash('sha256').update(fs.readFileSync(file)).digest('hex');
  report.glbSha256=hash(dest);
  assert.equal(report.glbSha256,hash(path.join(root,'assets/kestrel/kestrel.glb')));
  report.checks.push('Download returns the complete generated GLB');
  await page.setViewportSize({width:390,height:844});await settle();await shot('mobile');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  report.checks.push('390px mobile layout has no horizontal overflow');
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.failedRequests,[]);
  report.passed=true;
} catch(error) {report.passed=false;report.failure=error.stack;process.exitCode=1;}
finally {
  report.verifiedUtc=new Date().toISOString();
  fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report,null,2));await browser.close();
}
