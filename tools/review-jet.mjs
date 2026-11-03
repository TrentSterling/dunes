// Same camera and lighting for before/after geometry review. No owner browser input.
import {chromium} from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
const root=process.cwd(),out=path.join(root,'artifacts/vehicles/kestrel/revision-02');
fs.mkdirSync(out,{recursive:true});
// The original committed GLB makes this comparison reproducible in a fresh clone.
const baseline=execFileSync('git',['show','ee211b6:assets/kestrel/kestrel.glb'],{maxBuffer:16*1024*1024});
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--ignore-gpu-blocklist']});
try {
  for(const revision of ['before','after']) {
    const page=await browser.newPage({viewport:{width:1600,height:1000}});
    if(revision==='before') await page.route('**/assets/kestrel/kestrel.glb*',route=>route.fulfill({
      contentType:'model/gltf-binary',body:baseline}));
    await page.goto('http://127.0.0.1:5189/jet.html');
    await page.waitForFunction(()=>window.__jetViewer?.frames>5);
    for(const [name,pos,aim] of [
      ['low',[-13,3.1,-16],[0,2,-.2]],['side',[-25,2.4,0],[0,2.4,0]],
      ['hero',[10.5,8,-16.2],[0,1.6,0]],['under',[9,-5,-14],[0,1.5,-1]]]) {
      await page.evaluate(({pos,aim})=>{
        const v=window.__jetViewer;v.camera.position.fromArray(pos);v.camera.lookAt(...aim);
        if(pos[1]<0) v.scene.traverse(o=>{if(o.geometry?.type==='PlaneGeometry'&&o.geometry.parameters.width>100)o.visible=false;});
      },{pos,aim});
      await page.waitForTimeout(250);
      await page.locator('.stage').screenshot({path:path.join(out,`${revision}-${name}.png`)});
    }
    await page.close();
  }
} finally {await browser.close();}
