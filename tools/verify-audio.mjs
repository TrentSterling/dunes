import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const base=(process.env.DUNES_URL||'http://127.0.0.1:5189').replace(/\/$/,'');
const out=process.env.DUNES_OUTPUT||'artifacts/audio/local';fs.mkdirSync(out,{recursive:true});
const report={url:base,checks:[],errors:[]},pass=s=>{report.checks.push(s);console.log('PASS',s);};
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--ignore-gpu-blocklist']});
const p=await browser.newPage({viewport:{width:1440,height:900}});p.on('pageerror',e=>report.errors.push(e.message));
async function frames(n=4){await p.evaluate(async n=>{for(let i=0;i<n;i++)await new Promise(requestAnimationFrame);},n);}
async function hit(id){await p.waitForFunction(id=>__game.ui.hits.some(h=>h.id===id),id);const pos=await p.evaluate(id=>{const h=__game.ui.hits.find(h=>h.id===id);return [h.x+h.w/2,h.y+h.h/2];},id);await p.mouse.click(...pos);await frames();}
async function peak(){return p.evaluate(async()=>{const a=__audio.player,an=a.ctx.createAnalyser();an.fftSize=2048;a.output.connect(an);const data=new Float32Array(2048);let peak=0;await new Promise(r=>setTimeout(r,150));for(let i=0;i<8;i++){await new Promise(requestAnimationFrame);an.getFloatTimeDomainData(data);for(const v of data)peak=Math.max(peak,Math.abs(v));}a.output.disconnect(an);return {peak,gain:a.output.gain.value,player:a.debug(),bot:__audio.bot.debug()};});}
try{
 await p.addInitScript(()=>{if(!localStorage.getItem('audio-qa-init')){localStorage.setItem('glamis-settings-v1',JSON.stringify({quality:'low',car:'pro',proCarV:1,aiCount:1,volume:.65}));localStorage.setItem('audio-qa-init','1');}window.__textCalls=0;for(const key of ['fillText','strokeText']){const old=CanvasRenderingContext2D.prototype[key];CanvasRenderingContext2D.prototype[key]=function(...args){__textCalls++;return old.apply(this,args);};}});
 await p.goto(base+'/?room=audio-qa-'+Date.now());await p.waitForFunction(()=>window.__frames>20,null,{timeout:180000});
 assert.ok(await p.evaluate(()=>__game.ui.hits.some(h=>h.id==='mute-audio')));await p.screenshot({path:out+'/hud.png'});
 await p.keyboard.press('KeyW');await p.waitForFunction(()=>__audio.player.enabled&&__audio.bot.enabled);
 report.audible=await peak();assert.ok(report.audible.peak>.0001);assert.ok(Math.abs(report.audible.gain-.65)<.00001);
 assert.ok(await p.evaluate(()=>__audio.player.output===__audio.bot.output));pass('Player and nearby engine voices share an audible master output');
 await hit('mute-audio');report.muted=await peak();assert.equal(report.muted.peak,0);assert.equal(report.muted.gain,0);assert.equal(await p.evaluate(()=>__game.settings.volume),.65);pass('Visible HUD mute produces zero output samples and preserves the chosen volume');
 await p.reload();await p.waitForFunction(()=>window.__frames>20,null,{timeout:180000});assert.equal(await p.evaluate(()=>__game.settings.muted),true);
 await p.keyboard.press('KeyW');report.reloadMuted=await peak();assert.equal(report.reloadMuted.peak,0);assert.equal(report.reloadMuted.gain,0);pass('Reload and the first audio-start gesture retain mute');
 await p.keyboard.press('KeyU');report.unmuted=await peak();assert.ok(report.unmuted.peak>.0001);assert.ok(Math.abs(report.unmuted.gain-.65)<.00001);pass('U restores audio at the saved volume');
 await hit('open-menu');await hit('tab-1');assert.equal(await p.evaluate(()=>__game.menu.tabs[__game.menu.tab]),'Audio');await p.screenshot({path:out+'/audio-menu.png'});
 const slider=await p.evaluate(()=>{const h=__game.ui.hits.find(h=>h.id==='volume');return {x:h.x,y:h.y,w:h.w,h:h.h};});
 await p.mouse.click(slider.x+8+(slider.w-16)*.3,slider.y+slider.h/2);await frames();await p.waitForTimeout(80);assert.ok(Math.abs(await p.evaluate(()=>__audio.player.output.gain.value)-.3)<.001);
 await p.keyboard.press('KeyU');assert.equal(await p.evaluate(()=>__game.settings.muted),true);await hit('muted-false');await p.waitForTimeout(60);assert.ok(Math.abs(await p.evaluate(()=>__audio.player.output.gain.value)-.3)<.001);pass('Dedicated Audio tab controls master volume and mute; U also works inside the menu');
 await hit('resume');await p.keyboard.press('KeyP');const before=await p.evaluate(()=>__game.settings.muted);await p.keyboard.press('KeyU');assert.equal(await p.evaluate(()=>__game.settings.muted),before);await p.keyboard.press('Escape');pass('Typing a name does not trigger the mute shortcut');
 await p.setViewportSize({width:390,height:844});await frames();await hit('mute-audio');await p.screenshot({path:out+'/compact-muted.png'});await hit('open-menu');await p.screenshot({path:out+'/compact-audio.png'});assert.ok(await p.evaluate(()=>__game.ui.hits.some(h=>h.id==='volume')&&__game.ui.hits.some(h=>h.id==='muted-false')));pass('Mute and Audio controls remain reachable on a compact screen');
 assert.equal(await p.evaluate(()=>window.__textCalls),0);assert.equal(await p.locator('input,textarea,select').count(),0);assert.deepEqual(report.errors,[]);pass('Audio controls render with GPU glyphs and no DOM form fields');report.passed=true;
}catch(e){report.passed=false;report.failure=e.stack;process.exitCode=1;await p.screenshot({path:out+'/failure.png'}).catch(()=>{});}
finally{report.verifiedUtc=new Date().toISOString();fs.writeFileSync(out+'/audio.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));await browser.close();}
