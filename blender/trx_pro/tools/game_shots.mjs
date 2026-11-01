// In-game screenshots of the GLX pro sandrail (three.js, the real game renderer).
//
//   node tools/game_shots.mjs <outdir> [tag] [--glb path/to/sandcar.glb] [--views a,b,c] [--q low|high]
//
// Needs the game server on localhost:8080 (node server.js 8080 in the game folder).
// --glb serves that file in place of assets/pro_sandrail/sandcar.glb (and the .physics.json next
// to it), so a build can be checked in the game without installing it.
// Views: chase_f3q chase_side chase_r3q chase_front chase_rear cockpit cockpit_steer drive_chase drive_cockpit
// Writes <outdir>/<tag>game_<view>.png and prints page errors and car stats as JSON.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';

const argv = process.argv.slice(2);
const opt = (k, d) => { const i = argv.indexOf(k); if (i < 0) return d; const v = argv[i + 1]; argv.splice(i, 2); return v; };
const glb = opt('--glb', null);
const q = opt('--q', 'low');
const views = opt('--views', 'chase_f3q,chase_side,chase_r3q,chase_front,cockpit,cockpit_steer,drive_chase,drive_cockpit').split(',');
const outdir = argv[0] || '.';
const tag = argv[1] || '';
fs.mkdirSync(outdir, { recursive: true });

const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const ctx = await b.newContext({ viewport: { width: 1280, height: 720 } });
// start in the pro car with the help panel hidden
await ctx.addInitScript(() => {
  try {
    const k = 'glamis-settings-v1';
    const s = JSON.parse(localStorage.getItem(k) || '{}');
    Object.assign(s, { car: 'pro', proCarV: 1, showHelp: false, camMode: 0 });
    localStorage.setItem(k, JSON.stringify(s));
  } catch (e) {}
});
const p = await ctx.newPage();
if (glb) {
  const phys = glb.replace(/\.glb$/, '.physics.json');
  await p.route('**/assets/pro_sandrail/sandcar.glb', r => r.fulfill({ path: path.resolve(glb), contentType: 'model/gltf-binary' }));
  if (fs.existsSync(phys)) await p.route('**/assets/pro_sandrail/sandcar.physics.json', r => r.fulfill({ path: path.resolve(phys), contentType: 'application/json' }));
}
const logs = [];
p.on('pageerror', e => logs.push('pageerror: ' + e.message));
p.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') logs.push(m.type() + ': ' + m.text()); });
await p.goto(`http://localhost:8080/?q=${q}&shot&tod=15`);
await p.waitForFunction(() => (window.__frames || 0) > 3, null, { timeout: 400000 });
const wait = async (n) => { const f = await p.evaluate(() => window.__frames); await p.waitForFunction((m) => window.__frames > m, f + n, { timeout: 400000 }); };
const info = await p.evaluate(() => {
  const g = window.__game; let tris = 0, meshes = 0;
  g.model.root.traverse(o => { if (o.isMesh) { meshes++; const gi = o.geometry.index; tris += (gi ? gi.count : o.geometry.attributes.position.count) / 3; } });
  return { car: g.settings.car, meshes, tris: Math.round(tris), uprights: g.model.uprights?.length, segs: g.model.segs?.length, eye: g.model.eye && [g.model.eye.x, g.model.eye.y, g.model.eye.z].map(v => +v.toFixed(3)), ownBar: g.model.lights?.ownBar };
});
await p.evaluate(() => { const g = window.__game; g.setSetting('showHelp', false); g.setSetting('aiCount', 0); for (const t of document.querySelectorAll('.tag')) t.style.display = 'none'; });
const shot = async (v) => { await p.screenshot({ path: path.join(outdir, `${tag}game_${v}.png`) }); };
const ORBIT = { chase_f3q: [Math.PI * 0.78, 0.12, 0.62], chase_side: [Math.PI * 0.5, 0.05, 0.62], chase_r3q: [Math.PI * 0.2, 0.12, 0.62], chase_front: [Math.PI, 0.05, 0.62], chase_rear: [0, 0.1, 0.62] };
for (const v of views) {
  if (ORBIT[v]) {
    await p.evaluate((o) => { const g = window.__game; g.setSetting('camMode', 0); g.setOrbit(...o); }, ORBIT[v]);
    await wait(6); await shot(v);
  } else if (v === 'cockpit') {
    await p.evaluate(() => { window.__game.setSetting('camMode', 2); window.__game.setOrbit(0, 0, 1); });
    await wait(6); await shot(v);
  } else if (v === 'cockpit_steer') {
    await p.evaluate(() => window.__game.setSetting('camMode', 2));
    await p.keyboard.down('KeyA'); await wait(8); await shot(v); await p.keyboard.up('KeyA'); await wait(4);
  } else if (v === 'drive_chase' || v === 'drive_cockpit') {
    await p.evaluate((c) => { const g = window.__game; g.setSetting('camMode', c); g.setOrbit(0, 0.1, 1); }, v === 'drive_chase' ? 0 : 2);
    await p.keyboard.down('KeyW'); await wait(40); await shot(v); await p.keyboard.up('KeyW');
  }
}
console.log(JSON.stringify(info));
if (logs.length) console.log(logs.slice(0, 30).join('\n'));
await b.close();
