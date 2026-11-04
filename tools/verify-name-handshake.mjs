// Hold one hello handler while real WebRTC traffic continues, then rename.
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const base=(process.env.DUNES_URL||'http://127.0.0.1:5189').replace(/\/$/,'');
const out=process.env.DUNES_OUTPUT||'artifacts/polish/handshake';fs.mkdirSync(out,{recursive:true});
const room='name-handshake-'+Date.now(),report={url:base,room};
const browser=await chromium.launch({channel:'chrome',headless:true});
try{
  async function client(name,hold){
    const context=await browser.newContext(),page=await context.newPage();
    await page.goto(base+'/js/runtime-config.js');
    await page.evaluate(async({base,room,name,hold})=>{
      history.replaceState(null,'','?room='+room);
      const {PeerClient}=await import(base+'/js/net-peer.js');
      window.peer=new PeerClient({});window.hellos=[];
      const receive=peer.onControl.bind(peer);
      peer.onControl=(message,id)=>{if(hold&&message.t==='hello')hellos.push([message,id]);else receive(message,id);};
      window.acceptHello=()=>{for(const [message,id]of hellos)receive(message,id);};
      peer.connect(name,'pro');
    },{base,room,name,hold});return page;
  }
  const a=await client('Before rename',true),b=await client('Observer',false);
  await a.waitForFunction(()=>hellos.length>0,null,{timeout:60000});
  await b.waitForFunction(()=>peer.connected,null,{timeout:60000});
  assert.equal(await a.evaluate(()=>peer.connected),false);
  await a.evaluate(()=>{peer.setName('During handshake');acceptHello();});
  await b.waitForFunction(()=>[...peer.peers.values()].some(p=>p.name==='During handshake'),null,{timeout:6000});
  report.passed=true;report.checks=['Rename sent while hello handling is pending reaches the real connected peer'];
}catch(error){report.passed=false;report.failure=error.stack;process.exitCode=1;}
finally{report.verifiedUtc=new Date().toISOString();fs.writeFileSync(out+'/handshake.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));await browser.close();}
