import {chromium} from 'playwright-core';import assert from 'node:assert/strict';import fs from 'node:fs';
const base=(process.env.DUNES_URL||'http://127.0.0.1:5189').replace(/\/$/,'');const out=process.env.DUNES_OUTPUT||'artifacts/dust-rider/rider';fs.mkdirSync(out,{recursive:true});
const report={checks:[],errors:[]};const browser=await chromium.launch({channel:'chrome',headless:true,args:['--ignore-gpu-blocklist']});const p=await browser.newPage({viewport:{width:1440,height:900}});p.on('pageerror',e=>report.errors.push(e.message));
async function frames(n=4){await p.evaluate(async n=>{for(let i=0;i<n;i++)await new Promise(requestAnimationFrame);},n);}
try{
 await p.addInitScript(()=>localStorage.setItem('glamis-settings-v1',JSON.stringify({quality:'low',car:'pro',proCarV:1,aiCount:2,radarGpuV:1})));
 await p.goto(base+'/?room=rider-qa-'+Date.now());await p.waitForFunction(()=>window.__frames>20,null,{timeout:180000});
 report.riders=await p.evaluate(()=>{const g=__game;return [g.model,...g.bots.map(b=>b.model)].map(m=>({hasRider:!!m.rider,bones:Object.keys(m.rider?.bones||{}).length,head:m.rider?.bones.Head.uuid}));});assert.ok(report.riders.every(r=>r.hasRider&&r.bones>=60));assert.equal(new Set(report.riders.map(r=>r.head)).size,3);report.checks.push('Player and bots have independently cloned humanoid riders');
 await p.evaluate(()=>{const g=__game;g.car.update=()=>{};g.car.vel.set(0,0,0);g.setCam(0);g.setOrbit(Math.PI+.45,.12,.52);});await frames();await p.screenshot({path:out+'/front.png'});
 await p.evaluate(()=>__game.setOrbit(Math.PI/2,.08,.48));await frames();await p.screenshot({path:out+'/side.png'});
 report.pose=await p.evaluate(()=>{const g=__game,r=g.model.rider,inv=g.model.body.matrixWorld.clone().invert();return {eye:g.model.eye,bones:Object.fromEntries(['Head','pelvis','hand_l','hand_r','foot_l','foot_r'].map(n=>[n,r.point(n).applyMatrix4(inv).toArray()])),handError:r.handTargets.map((t,i)=>r.point(i?'hand_r':'hand_l').distanceTo(t))};});
 await p.evaluate(()=>{const g=__game;g.model.model.visible=false;g.model.lights.group.visible=false;});await frames();await p.screenshot({path:out+'/rider-isolated.png'});
 await p.evaluate(()=>{__game.model.model.visible=true;__game.model.lights.group.visible=true;__game.setSetting('driverArms',true);__game.setCam(2);});await frames();
 assert.ok(await p.evaluate(()=>!__game.camera.layers.isEnabled(4)&&__game.model.live.mirrors.every(m=>m.pieces.every(p=>p.cam.layers.isEnabled(4)))));await p.screenshot({path:out+'/cockpit.png'});report.checks.push('First-person view hides the full rider while rear-view mirror cameras retain it');
 report.steering=await p.evaluate(()=>{const r=__game.model.rider,before=r.point('hand_l');r.update(.35);return {movement:before.distanceTo(r.point('hand_l')),error:r.handTargets.map((t,i)=>r.point(i?'hand_r':'hand_l').distanceTo(t))};});assert.ok(report.steering.movement>.04);assert.ok(Math.max(...report.pose.handError,...report.steering.error)<.12);report.checks.push('Seated arms follow the wheel with bounded reach error');
 await p.evaluate(()=>{__game.setCam(0);__game.car.steerAngle=.35;__game.setOrbit(Math.PI+.45,.04,.42);});await frames();await p.screenshot({path:out+'/steering.png'});
 await p.evaluate(()=>__game.setSetting('night',true));await frames(20);await p.screenshot({path:out+'/night.png'});
 assert.deepEqual(report.errors,[]);report.passed=true;
}catch(e){report.passed=false;report.failure=e.stack;process.exitCode=1;await p.screenshot({path:out+'/failure.png'}).catch(()=>{});}
finally{fs.writeFileSync(out+'/rider.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));await browser.close();}
