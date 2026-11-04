// Deterministic scenarios run the actual bot and 1000 Hz vehicle physics.
import {chromium} from 'playwright-core';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const base=(process.env.DUNES_URL||'http://127.0.0.1:5189').replace(/\/$/,'');
const out=process.env.DUNES_OUTPUT||'artifacts/radar-bots/local';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true});
const report={url:base,checks:[]};
try{
  const page=await browser.newPage();
  await page.route(base+'/',route=>route.fulfill({contentType:'text/html',body:`<script type="importmap">{"imports":{"three":"${base}/vendor/three.module.js"}}</script>`}));
  await page.goto(base+'/');
  report.scenarios=await page.evaluate(async base=>{
    const THREE=await import('three'),{AIDriver}=await import(base+'/js/ai-driver.js');
    let seed=321;Math.random=()=>((seed=Math.imul(1664525,seed)+1013904223|0)>>>0)/4294967296;
    const terrain={height:()=>0,sample:()=>({h:0,dx:0,dz:0}),normal:(x,z,out)=>out.set(0,1,0)};
    const player={pos:new THREE.Vector3(0,0,100),quat:new THREE.Quaternion()};
    const make=()=>{const b=new AIDriver(terrain,0);b.car.reset(0,0,0);b.target.set(0,0,500);b.car.reset=()=>{throw Error('Unexpected running-bot reset');};return b;};
    const result={};
    let bot=make();player.pos.x=3500;const before=bot.car.pos.clone();bot.update(1/60,player);
    result.leash={step:before.distanceTo(bot.car.pos),target:bot.target.toArray()};
    bot=make();bot.mode='reverse';bot.modeT=3.6;bot.car.gear=-1;const stuck=bot.car.pos.clone();bot.update(1/60,player);
    result.stuck={step:stuck.distanceTo(bot.car.pos),mode:bot.mode};
    player.pos.set(0,0,100);bot=make();bot.car.quat.setFromAxisAngle(new THREE.Vector3(0,0,1),Math.PI);bot.car.pos.y=1.5;
    let recovered=false,entered=false,maxStep=0,maxTurn=0,elapsed=0;
    const samples=[];
    for(let i=0;i<1800;i++){
      const pos=bot.car.pos.clone(),q=bot.car.quat.clone();bot.update(1/60,player);elapsed=(i+1)/60;
      maxStep=Math.max(maxStep,pos.distanceTo(bot.car.pos));maxTurn=Math.max(maxTurn,q.angleTo(bot.car.quat));
      entered ||= bot.mode==='recover';
      const up=new THREE.Vector3(0,1,0).applyQuaternion(bot.car.quat).y;
      if(i%60===0)samples.push({time:elapsed,mode:bot.mode,up,speed:bot.car.speed});
      if(entered&&bot.mode==='drive'&&up>.85){recovered=true;break;}
    }
    result.rollover={entered,recovered,elapsed,maxStep,maxTurn,samples};
    bot=make();player.pos.set(2000,0,2000);maxStep=0;const start=bot.car.pos.clone();
    for(let i=0;i<3600;i++){const pos=bot.car.pos.clone();bot.update(1/60,player);maxStep=Math.max(maxStep,pos.distanceTo(bot.car.pos));if(!bot.car.pos.toArray().every(Number.isFinite))throw Error('Invalid pose');}
    result.longDrive={simulatedSeconds:60,maxStep,distance:start.distanceTo(bot.car.pos),position:bot.car.pos.toArray()};
    return result;
  },base);
  assert.ok(report.scenarios.leash.step<1);report.checks.push('A bot 3.5 km away drives back without respawning');
  assert.ok(report.scenarios.stuck.step<1);report.checks.push('Failed reverse recovery chooses another line without a pose reset');
  const roll=report.scenarios.rollover;assert.ok(roll.entered&&roll.recovered,'Rollover must recover through physics');
  assert.ok(roll.maxStep<1&&roll.maxTurn<.3);report.checks.push('An inverted bot rolls upright with continuous position and rotation');
  assert.ok(report.scenarios.longDrive.distance>20&&report.scenarios.longDrive.maxStep<2);report.checks.push('A seeded 60-second drive remains finite and continuous without any reset calls');
  report.passed=true;
}catch(error){report.passed=false;report.failure=error.stack;process.exitCode=1;}
finally{report.verifiedUtc=new Date().toISOString();fs.writeFileSync(out+'/bot-recovery.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));await browser.close();}
