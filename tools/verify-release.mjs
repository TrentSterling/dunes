// Verify the published bytes against this checkout's committed release.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const base=(process.env.DUNES_URL||'https://tront.xyz/dunes').replace(/\/$/,'');
const out=process.env.DUNES_OUTPUT||'artifacts/polish/live';fs.mkdirSync(out,{recursive:true});
const commit=execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim();
const pkg=JSON.parse(fs.readFileSync('package.json','utf8'));
const report={url:base,checks:[],hashes:{}};
try{
  const home=await fetch(base);assert.equal(home.status,200);assert.equal(home.url,base+'/');assert.match(await home.text(),/<title>Dunes<\/title>/);
  report.checks.push('HTTPS route redirects to the game');
  const release=await fetch(base+'/release.json').then(r=>r.json());assert.equal(release.commit,commit);assert.equal(release.version,pkg.version);assert.equal(release.mode,'trystero-p2p');report.release=release;
  report.checks.push('Live release version and commit match HEAD');
  const config=await fetch(base+'/js/runtime-config.js').then(r=>r.text());assert.match(config,/STATIC_HOSTING = true/);
  const files=['public/index.html','public/js/main.js','public/js/menu.js','public/js/gpu-ui.js','public/js/game-ui.js','public/js/cockpit-display.js','public/js/gltf-sandrail.js','public/js/net-peer.js','public/js/radar.js','public/js/ai-driver.js','public/js/vehicle-physics.js','public/js/settings.js','public/js/controls.js','public/vendor/trystero.js','assets/fonts/barlow-sdf.png','assets/fonts/barlow-sdf.json','assets/fonts/OFL.txt'];
  const hash=b=>createHash('sha256').update(b).digest('hex');
  for(const file of files){const route=file.replace(/^public\//,'');const response=await fetch(base+'/'+route);assert.equal(response.status,200,route);
    const bytes=Buffer.from(await response.arrayBuffer()),expected=execFileSync('git',['show',`HEAD:${file}`],{maxBuffer:8*1024*1024});
    assert.equal(hash(bytes),hash(expected),route);report.hashes[route]=hash(bytes);
  }
  report.checks.push('Live game, network, GPU UI/radar, bot physics and font assets match Git blobs');report.passed=true;
}catch(error){report.passed=false;report.failure=error.stack;process.exitCode=1;}
report.verifiedUtc=new Date().toISOString();fs.writeFileSync(path.join(out,'release.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
