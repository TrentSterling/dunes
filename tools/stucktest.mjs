// Drive the player car for a few minutes with a human-like input pattern and
// report whether it ever stops responding (no speed under full throttle, NaN, buried wheels).
import fs from 'fs';
import * as THREE from 'three';
import { TerrainData } from '../public/js/terrain-data.js';
import { SandrailPhysics } from '../public/js/vehicle-physics.js';
const base = new URL('../public/data/', import.meta.url).pathname;
const meta = JSON.parse(fs.readFileSync(base + 'terrain.json'));
const td = new TerrainData(meta, new Uint16Array(fs.readFileSync(base + 'height_fine.u16').buffer.slice(0)), new Uint16Array(fs.readFileSync(base + 'height_coarse.u16').buffer.slice(0)));
const c = new SandrailPhysics(td); c.reset(940, -800, 0);
let seed = +(process.argv[2] || 1); const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
let phase = 0, phaseT = 0, thr = 0, steer = 0, brk = 0;
const dt = 1 / 60;
for (let t = 0; t < +(process.argv[3] || 240); t += dt) {
  phaseT -= dt;
  if (phaseT <= 0) { phase = Math.floor(rnd() * 5); phaseT = 1 + rnd() * 4; steer = phase === 1 ? 1 : phase === 2 ? -1 : (rnd() - 0.5) * 0.4; thr = phase === 3 ? 0 : phase === 4 ? 0.5 : 1; brk = phase === 3 && rnd() < 0.5 ? 1 : 0; }
  Object.assign(c.input, { throttle: thr, steer, brake: brk, handbrake: false });
  c.update(dt);
  if (Math.round(t / dt) % 300 === 0) {
    const up = new THREE.Vector3(0, 1, 0).applyQuaternion(c.quat).y;
    console.log(`t${t.toFixed(0)} v${(c.forwardSpeed * 2.237).toFixed(0)}mph thr${thr} g${c.gear} rpm${c.rpm.toFixed(0)} up${up.toFixed(2)} sink ${c.wheels.map(w => w.sink.toFixed(2)).join(',')} comp ${c.wheels.map(w => w.comp.toFixed(2)).join(',')} gnd ${c.wheels.map(w => w.onGround ? 1 : 0).join('')} hull ${c.hullContact.toFixed(2)} steer ${c.steerAngle.toFixed(2)} pos ${c.pos.x.toFixed(0)},${c.pos.z.toFixed(0)}`);
  }
  if (!isFinite(c.pos.x)) { console.log('NaN at', t); break; }
}
