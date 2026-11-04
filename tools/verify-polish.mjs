// Exercise the shipped canvas UI using real pointer/keyboard input and live peers.
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const base=(process.env.DUNES_URL||'http://127.0.0.1:5189').replace(/\/$/,'');
const out=path.resolve(process.env.DUNES_OUTPUT||'artifacts/polish/local');
fs.mkdirSync(out,{recursive:true});
const report={url:base,checks:[],errors:[],failedRequests:[],relayWarnings:[]};
const check=s=>{report.checks.push(s);console.log('PASS',s);};
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--ignore-gpu-blocklist']});
const pages=[];
async function client(name){
  const context=await browser.newContext({viewport:{width:1440,height:900}});
  await context.addInitScript(name=>{
    if(!localStorage.getItem('glamis-name'))localStorage.setItem('glamis-name',name);
    localStorage.setItem('glamis-settings-v1',JSON.stringify({quality:'low',car:'pro',proCarV:1,aiCount:0,showHelp:false,camMode:0}));
    window.__canvasTextCalls=0;
    for(const method of ['fillText','strokeText']){
      const original=CanvasRenderingContext2D.prototype[method];
      CanvasRenderingContext2D.prototype[method]=function(...args){window.__canvasTextCalls++;return original.apply(this,args);};
    }
  },name);
  const page=await context.newPage();pages.push(page);
  page.on('pageerror',e=>report.errors.push(e.message));
  page.on('dialog',async d=>{report.errors.push(`Native dialog: ${d.type()}`);await d.dismiss();});
  page.on('console',m=>{if(m.type()==='error')(/WebSocket connection.*wss:\/\//.test(m.text())?report.relayWarnings:report.errors).push(m.text());});
  page.on('requestfailed',r=>report.failedRequests.push(r.url()+' '+r.failure()?.errorText));
  page.on('response',r=>{if(r.status()>=400)report.failedRequests.push(`${r.status()} ${r.url()}`);});
  await page.goto(base+'/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__frames>15&&window.__game?.ui,null,{timeout:120000});
  return page;
}
async function hit(page,id){
  await page.waitForFunction(id=>window.__game.ui.hits.some(h=>h.id===id),id);
  const h=await page.evaluate(id=>{const h=window.__game.ui.hits.find(h=>h.id===id);return {x:h.x+h.w/2,y:h.y+h.h/2};},id);
  await page.mouse.click(h.x,h.y);await frames(page,2);
}
async function frames(page,n=5){const next=await page.evaluate(n=>window.__frames+n,n);await page.waitForFunction(n=>window.__frames>=n,next);}
async function screenshot(page,name){await page.screenshot({path:path.join(out,name+'.png')});}
try{
  const a=await client('Dunes polish A'),b=await client('Dunes polish B');
  const aid=await a.evaluate(()=>window.__game.net.id),bid=await b.evaluate(()=>window.__game.net.id);
  await Promise.all([[a,bid],[b,aid]].map(([p,id])=>p.waitForFunction(id=>window.__game.net.peers.get(id)?.ready&&window.__game.remotes.has(id),id,{timeout:90000})));
  assert.equal(await a.evaluate(()=>window.__game.net.roomId),'global');
  assert.equal(new URL(a.url()).search,'');
  assert.equal(await b.evaluate(()=>window.__game.net.roomId),'global');
  check('Normal URLs automatically join the same global room without any clicks');
  await a.waitForFunction(()=>window.__game.net.metrics.statesReceived>10);
  report.network=await a.evaluate(()=>window.__game.net.diagnostics());
  check('Live Trystero discovery establishes bidirectional vehicle traffic');
  report.mirrors=await a.evaluate(async()=>{
    const {GLTFLoader}=await import('three/addons/loaders/GLTFLoader.js');
    const raw=(await new GLTFLoader().loadAsync('assets/pro_sandrail/sandcar.glb')).scene;
    const rows=[];window.__game.model.model.traverse(o=>{
      if(!o.isMesh||!o.material?.name?.toLowerCase().includes('mirror'))return;
      const p=o.geometry.attributes.position,original=raw.getObjectByName(o.name)?.geometry?.attributes.position;
      let maxDelta=0;const sides={left:0,right:0};
      if(!original||p.count!==original.count)throw Error('Mirror source mismatch');
      for(let i=0;i<p.count;i++){
        maxDelta=Math.max(maxDelta,Math.hypot(p.getX(i)-original.getX(i),p.getY(i)-original.getY(i),p.getZ(i)-original.getZ(i)));
        sides[original.getX(i)<0?'left':'right']++;
      }rows.push({name:o.name,material:o.material.name,vertices:p.count,maxDelta,sides});
    });return rows;
  });
  assert.ok(report.mirrors.length>=2);assert.ok(report.mirrors.every(m=>m.maxDelta===0));
  const side=report.mirrors.find(m=>m.material.toLowerCase().includes('side'));
  assert.ok(side.sides.left>0&&side.sides.right>0);
  check('Both startup side mirrors retain their exact source GLB vertex positions');
  await a.evaluate(()=>{window.__sameCar=window.__game.car;window.__sameModel=window.__game.model;window.__sameNet=window.__game.net;});
  const timeOrigin=await a.evaluate(()=>performance.timeOrigin);
  await a.keyboard.press('KeyP');await a.keyboard.type('Trent WASD');await frames(a);
  assert.equal(await a.evaluate(()=>window.__game.input.throttle),0);
  await screenshot(a,'name-editor');await a.keyboard.press('Enter');
  await b.waitForFunction(id=>window.__game.net.peers.get(id)?.name==='Trent WASD'&&window.__game.remotes.get(id)?.name==='Trent WASD'&&window.__game.ui.playerNames.includes('Trent WASD'),aid);
  assert.equal(await a.evaluate(()=>performance.timeOrigin),timeOrigin);
  assert.ok(await a.evaluate(()=>window.__sameCar===window.__game.car&&window.__sameModel===window.__game.model&&window.__sameNet===window.__game.net));
  assert.equal(await a.evaluate(()=>window.__game.net.id),aid);
  assert.equal(await a.evaluate(()=>localStorage.getItem('glamis-name')),'Trent WASD');
  check('Typing a name does not drive; saving updates the peer without reload, respawn or reconnect');
  await a.keyboard.press('KeyP');await a.keyboard.press('Backspace');await a.keyboard.press('Enter');
  assert.equal(await a.evaluate(()=>window.__game.menu.editor.error),'ENTER A DRIVER NAME');
  await a.keyboard.type('Cancelled');await a.keyboard.press('Escape');
  assert.equal(await a.evaluate(()=>window.__game.net.name),'Trent WASD');
  await a.keyboard.press('KeyP');await a.keyboard.type('Trent DuneX');await a.keyboard.press('Backspace');await a.keyboard.type('s');
  await a.keyboard.press('Home');await a.keyboard.press('ArrowRight');await a.keyboard.press('End');await a.keyboard.press('Enter');
  await b.waitForFunction(id=>window.__game.net.peers.get(id)?.name==='Trent Dunes',aid);
  check('Name validation, selection replacement, caret edits and cancellation preserve expected state');
  await hit(a,'open-menu');await screenshot(a,'driver-menu');await hit(a,'tab-1');
  await hit(a,'autoTrans-false');assert.equal(await a.evaluate(()=>window.__game.settings.autoTrans),false);
  await hit(a,'autoTrans-true');
  const slider=await a.evaluate(()=>{const h=window.__game.ui.hits.find(h=>h.id==='steerSens');return {x:h.x,y:h.y,w:h.w,h:h.h};});
  await a.mouse.move(slider.x+slider.w*.7,slider.y+slider.h/2);await a.mouse.down();await a.mouse.move(slider.x+slider.w*.8,slider.y+slider.h/2);await a.mouse.up();
  const sensitivity=await a.evaluate(()=>window.__game.settings.steerSens);assert.ok(sensitivity>1.2);
  await a.keyboard.press('ArrowLeft');assert.ok(await a.evaluate(s=>window.__game.settings.steerSens<s,sensitivity));
  await a.keyboard.press('Tab');assert.ok(await a.evaluate(()=>window.__game.ui.focusId!=='steerSens'));
  await a.mouse.wheel(0,500);await frames(a);assert.ok(await a.evaluate(()=>window.__game.menu.scroll>0));
  await a.keyboard.press('KeyW');await frames(a);assert.equal(await a.evaluate(()=>window.__game.input.throttle),0);
  check('GPU choices, pointer sliders, keyboard adjustment, focus and scrolling work without driving input');
  await hit(a,'tab-2');await hit(a,'bind-throttle-keys-0');await a.keyboard.press('KeyI');
  assert.equal(await a.evaluate(()=>window.__game.menu.bindings.throttle.keys[0]),'KeyI');
  await hit(a,'bind-throttle-keys-0');await a.keyboard.press('KeyW');
  await hit(a,'tab-5');await screenshot(a,'teleport-menu');
  const teleportId=await a.evaluate(()=>window.__game.ui.hits.find(h=>h.id.startsWith('tp-')).id);
  const before=await a.evaluate(()=>window.__game.car.pos.toArray());await hit(a,teleportId);
  const after=await a.evaluate(()=>window.__game.car.pos.toArray());assert.ok(Math.hypot(...after.map((v,i)=>v-before[i]))>10);
  check('GPU key rebinding and teleport actions retain gameplay behavior');
  if(await a.evaluate(()=>window.__game.menu.open))await a.keyboard.press('Escape');
  await a.keyboard.press('KeyC');await a.keyboard.press('KeyC');await frames(a,20);await screenshot(a,'cockpit');
  const screens=await a.evaluate(()=>Object.fromEntries(Object.entries(window.__game.model.live.screens).map(([k,v])=>[k,{draws:v.surface.renderCount,glyphs:v.surface.glyphCount}])));
  assert.ok(screens.dash.draws>0&&screens.lowrance.draws>0&&screens.dash.glyphs>0);report.screens=screens;
  check('Cockpit instruments and navigator draw GPU glyphs into live render targets');
  await a.setViewportSize({width:390,height:844});await frames(a);await hit(a,'open-menu');
  for(let i=0;i<5;i++)await hit(a,'previous-tab');
  await screenshot(a,'mobile-menu');await hit(a,'edit-name');await hit(a,'name-keyboard');
  await hit(a,'letter-D');await hit(a,'letter-U');await hit(a,'letter-N');await hit(a,'letter-E');await hit(a,'letter-S');await screenshot(a,'mobile-keyboard');
  const bounded=await a.evaluate(()=>window.__game.ui.hits.every(h=>h.x>=0&&h.y>=0&&h.x+h.w<=innerWidth&&h.y+h.h<=innerHeight));assert.ok(bounded);
  await hit(a,'name-save');await b.waitForFunction(id=>window.__game.net.peers.get(id)?.name==='DUNES',aid);
  check('Compact menu and GPU on-screen keyboard support a 390-pixel viewport');
  report.ui=await Promise.all(pages.map(p=>p.evaluate(()=>({domText:document.body.innerText,forms:document.querySelectorAll('input,textarea,select,button,dialog,[contenteditable]').length,canvases:document.querySelectorAll('canvas').length,canvasTextCalls:window.__canvasTextCalls,glyphs:window.__game.ui.glyphCount}))));
  for(const ui of report.ui){assert.equal(ui.domText,'');assert.equal(ui.forms,0);assert.equal(ui.canvases,1);assert.equal(ui.canvasTextCalls,0);assert.ok(ui.glyphs>0);}
  check('The game has no DOM text/controls and makes zero Canvas2D text calls');
  await a.setViewportSize({width:1440,height:900});await a.reload({waitUntil:'domcontentloaded'});
  await a.waitForFunction(()=>window.__frames>15&&window.__game?.net.name==='DUNES',null,{timeout:120000});
  await b.waitForFunction(()=>[...window.__game.net.peers.values()].some(p=>p.name==='DUNES'&&p.ready),null,{timeout:90000});
  await screenshot(a,'hud');check('Saved name survives a later page reload and rejoins the global room');
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.failedRequests,[]);
  report.passed=true;
}catch(error){report.passed=false;report.failure=error.stack;process.exitCode=1;
  for(const [i,p]of pages.entries())if(!p.isClosed())await screenshot(p,'failure-'+i).catch(()=>{});
}finally{
  report.verifiedUtc=new Date().toISOString();fs.writeFileSync(path.join(out,'polish.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({passed:report.passed,checks:report.checks.length,errors:report.errors,failedRequests:report.failedRequests,failure:report.failure,receipt:path.join(out,'polish.json')},null,2));
  await browser.close();
}
