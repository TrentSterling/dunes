import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const base=(process.env.DUNES_URL||'http://127.0.0.1:5189').replace(/\/$/,'');
const out=process.env.DUNES_OUTPUT||'artifacts/radar-bots/local';fs.mkdirSync(out,{recursive:true});
const room='radar-bots-'+Date.now(),report={url:base,room,checks:[],errors:[],failedRequests:[],relayWarnings:[]};
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--ignore-gpu-blocklist']});
const pages=[];const pass=s=>{report.checks.push(s);console.log('PASS',s);};
async function frames(p,n=5){const goal=await p.evaluate(n=>window.__frames+n,n);await p.waitForFunction(n=>window.__frames>=n,goal);}
async function shot(p,name,clip){await p.screenshot({path:out+'/'+name+'.png',...(clip?{clip}:{})});}
async function hit(p,id){await p.waitForFunction(id=>window.__game.ui.hits.some(h=>h.id===id),id);const h=await p.evaluate(id=>{const h=window.__game.ui.hits.find(h=>h.id===id);return {x:h.x+h.w/2,y:h.y+h.h/2};},id);await p.mouse.click(h.x,h.y);await frames(p);}
async function client(name){
  const context=await browser.newContext({viewport:{width:1440,height:900}});
  await context.addInitScript(name=>{
    if(!localStorage.getItem('glamis-settings-v1'))localStorage.setItem('glamis-settings-v1',JSON.stringify({quality:'low',car:'pro',proCarV:1,aiCount:4,radar:false,radarCockpit:'dash',showHelp:false}));
    localStorage.setItem('glamis-name',name);window.__twoD=[];window.__textCalls=0;
    const get=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type,...args){if(type==='2d')window.__twoD.push(new Error().stack);return get.call(this,type,...args);};
    for(const method of ['fillText','strokeText']){const original=CanvasRenderingContext2D.prototype[method];CanvasRenderingContext2D.prototype[method]=function(...args){window.__textCalls++;return original.apply(this,args);};}
  },name);
  const p=await context.newPage();pages.push(p);
  p.on('pageerror',e=>report.errors.push(e.message));
  p.on('console',m=>{if(m.type()==='error')(/WebSocket connection.*wss:\/\//.test(m.text())?report.relayWarnings:report.errors).push(m.text());});
  p.on('requestfailed',r=>report.failedRequests.push(r.url()+' '+r.failure()?.errorText));
  p.on('response',r=>{if(r.status()>=400)report.failedRequests.push(`${r.status()} ${r.url()}`);});
  await p.goto(`${base}/?room=${room}`,{waitUntil:'domcontentloaded'});
  await p.waitForFunction(()=>window.__frames>20&&window.__game?.radar?.drawCount>0,null,{timeout:120000});return p;
}
try{
  const a=await client('Radar QA A');
  assert.ok(await a.evaluate(()=>window.__game.settings.radar&&window.__game.settings.radarCockpit==='hud'&&window.__game.ui.radarBounds));
  pass('Old hidden or dash-only settings restore the replacement HUD radar once');
  report.gpu=await a.evaluate(()=>{
    const g=window.__game,r=g.radar,pixels=new Uint8Array(512*512*4);g.renderer.readRenderTargetPixels(r.target,0,0,512,512,pixels);
    let min=255,max=0,opaque=0;for(let y=100;y<410;y+=5)for(let x=100;x<410;x+=5){const i=(y*512+x)*4;min=Math.min(min,pixels[i]);max=Math.max(max,pixels[i]);if(pixels[i+3]>200)opaque++;}
    return {target:r.target.isWebGLRenderTarget,draws:r.drawCount,glyphs:r.overlay.glyphCount,min,max,opaque,canvas:r.cv!==undefined,radarCanvasCalls:window.__twoD.filter(s=>s.includes('/radar.js')).length,textCalls:window.__textCalls};
  });
  assert.ok(report.gpu.target&&report.gpu.draws>0&&report.gpu.glyphs>=4&&report.gpu.max-report.gpu.min>45&&report.gpu.opaque>2500);
  assert.equal(report.gpu.radarCanvasCalls,0);assert.equal(report.gpu.canvas,false);assert.equal(report.gpu.textCalls,0);
  pass('Terrain, compass and markers render into a nonblank GPU target without radar Canvas2D work');
  report.orientation=await a.evaluate(()=>{
    const g=window.__game,r=g.radar,draw=r.draw;r.draw=()=>{};
    const blips=[{x:0,z:-200,kind:'bot'},{x:200,z:0,kind:'player'},{x:0,z:200,kind:'bot'},{x:-5000,z:0,kind:'player'}];
    function probe(fx,fz){draw.call(r,{x:0,z:0,fx,fz},blips);const pixels=new Uint8Array(512*512*4);g.renderer.readRenderTargetPixels(r.target,0,0,512,512,pixels);
      return r.markers.map(p=>{let colored=0;for(let y=Math.round(p.y*2)-4;y<=p.y*2+4;y++)for(let x=Math.round(p.x*2)-4;x<=p.x*2+4;x++){
        const i=(y*512+x)*4,R=pixels[i],G=pixels[i+1],B=pixels[i+2];if(p.kind==='bot'?R>220&&G>120&&G<210&&B<140:B>200&&G>170&&R<160)colored++;
      }return {...p,colored};});
    }
    const north=probe(0,-1),east=probe(1,0);r.draw=draw;return {north,east};
  });
  assert.ok(report.orientation.north[0].y<128&&report.orientation.north[1].x>128&&report.orientation.north[3].edge);
  assert.ok(report.orientation.east[0].x<128&&report.orientation.east[1].y<128);
  assert.ok(report.orientation.north.every(p=>p.colored>0)&&report.orientation.east.every(p=>p.colored>0));
  pass('GPU pixel samples place bots, peer diamonds and edge arrows correctly as heading rotates');
  await frames(a);await shot(a,'radar-hud');const bounds=await a.evaluate(()=>window.__game.ui.radarBounds);await shot(a,'radar-detail',{x:bounds.x-10,y:bounds.y-36,width:bounds.w+20,height:bounds.h+78});
  await hit(a,'radar-out');assert.equal(await a.evaluate(()=>window.__game.radar.range),1200);
  await hit(a,'radar-out');assert.equal(await a.evaluate(()=>window.__game.radar.range),2500);
  for(let i=0;i<3;i++)await hit(a,'radar-in');assert.equal(await a.evaluate(()=>window.__game.radar.range),300);
  await hit(a,'radar-out');
  await a.keyboard.press('KeyB');await frames(a);assert.equal(await a.evaluate(()=>window.__game.settings.radar),false);
  await hit(a,'show-radar');assert.equal(await a.evaluate(()=>window.__game.settings.radar),true);
  pass('HUD range controls and B/show-radar controls work without opening settings');
  report.preservation=await a.evaluate(()=>{
    const g=window.__game,before=g.bots.map(b=>({bot:b,car:b.car,p:b.car.pos.clone()}));
    g.setSetting('car','blue');const carSwitch=before.every((v,i)=>v.bot===g.bots[i]&&v.car===g.bots[i].car&&v.p.equals(v.car.pos));
    g.teleport('olds');const teleport=before.every((v,i)=>v.bot===g.bots[i]&&v.p.equals(v.car.pos));
    return {carSwitch,teleport,count:before.length};
  });
  assert.ok(report.preservation.count===4&&report.preservation.carSwitch&&report.preservation.teleport);
  pass('Changing the player car and teleporting preserve existing bot objects and positions');
  const b=await client('Radar QA B');
  await a.waitForFunction(()=>window.__game.net.connected&&window.__game.radar.counts.players>=1,null,{timeout:90000});
  await a.waitForFunction(()=>window.__game.radar.markers.some(p=>p.kind==='player'));
  pass('A real Trystero peer appears in the GPU radar alongside four local bots');
  await a.evaluate(()=>{
    const g=window.__game;window.__botWatch={frames:0,resets:0,maxStep:0,jumps:[],active:true};
    for(const b of g.bots){const reset=b.car.reset.bind(b.car);b.car.reset=(...args)=>{window.__botWatch.resets++;return reset(...args);};}
    const last=g.bots.map(b=>b.car.pos.clone());
    function watch(){const w=window.__botWatch;if(!w.active)return;w.frames++;
      g.bots.forEach((b,i)=>{const d=last[i].distanceTo(b.car.pos);w.maxStep=Math.max(w.maxStep,d);if(d>Math.max(2,b.car.speed*.05+1))w.jumps.push({bot:i,d,speed:b.car.speed});last[i].copy(b.car.pos);});requestAnimationFrame(watch);
    }requestAnimationFrame(watch);
  });
  await frames(a,360);
  report.botWatch=await a.evaluate(()=>{window.__botWatch.active=false;return window.__botWatch;});
  assert.equal(report.botWatch.resets,0);assert.deepEqual(report.botWatch.jumps,[]);
  pass('Four bots drive through 360 rendered frames with no reset calls or position discontinuities');
  await a.evaluate(()=>{window.__game.setSetting('car','pro');window.__game.setSetting('camMode',2);});
  await frames(a,20);assert.ok(await a.evaluate(()=>window.__game.radar.navDrawCount>0&&window.__game.model.live.screens.lowrance.surface.renderCount>0));
  await shot(a,'cockpit-radar');pass('The cockpit navigator uses the GPU terrain map and peer markers');
  await a.evaluate(()=>window.__game.setSetting('renderScale',2));await frames(a,5);
  assert.ok(await a.evaluate(()=>window.__game.ui.radarBounds.w===214&&window.__game.radar.target.width===512));
  await a.evaluate(()=>window.__game.setSetting('renderScale',1));await a.setViewportSize({width:390,height:844});await frames(a);await shot(a,'compact-radar');
  assert.ok(await a.evaluate(()=>{const r=window.__game.ui.radarBounds;return r.x>=0&&r.y>=0&&r.x+r.w<=innerWidth&&r.y+r.h<=innerHeight;}));
  pass('Radar survives render-scale changes and fits the compact viewport');
  await a.keyboard.press('KeyB');await a.reload({waitUntil:'domcontentloaded'});
  await a.waitForFunction(()=>window.__frames>15&&window.__game?.settings.radarGpuV===1,null,{timeout:120000});
  assert.equal(await a.evaluate(()=>window.__game.settings.radar),false);await hit(a,'show-radar');
  pass('After the one-time restoration, an explicit radar preference persists across reloads');
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.failedRequests,[]);report.passed=true;
}catch(error){report.passed=false;report.failure=error.stack;process.exitCode=1;for(const [i,p]of pages.entries())await shot(p,'failure-'+i).catch(()=>{});}
finally{report.verifiedUtc=new Date().toISOString();fs.writeFileSync(out+'/radar-bots.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({passed:report.passed,checks:report.checks.length,failure:report.failure,errors:report.errors,failedRequests:report.failedRequests,receipt:out+'/radar-bots.json'},null,2));await browser.close();}
