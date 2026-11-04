// Computer-driven sandrails. Each bot runs the same 1000 Hz physics as the
// player and drives it through the normal inputs (throttle, brake, steer),
// wandering between waypoints in the dunes near the player.
import * as THREE from 'three';
import { SandrailPhysics } from './vehicle-physics.js';

const NAMES = ['Dusty', 'Paddle Pete', 'Big Mike', 'Sand Shark', 'Roostmaster', 'Gecko', 'Olds Hill', 'Dune Goon',
  'Sidewinder', 'Mad Max', 'Hot Sauce', 'Wheelie Will', 'Cactus Jack', 'Brawley Boy'];
const TINTS = [0x1450c8, 0xf0a000, 0x15913a, 0x6a1bb0, 0xe8e8e8, 0x101010, 0xff5a00, 0x00a6b8, 0xd8197a, 0x8a6a3a, 0x2f3f9f, 0xc8c800];
const FINE_HALF = 7800;

const _v = new THREE.Vector3(), _q = new THREE.Quaternion();
const _up = new THREE.Vector3(), _ground = new THREE.Vector3(), _axis = new THREE.Vector3();

export class AIDriver {
  constructor(terrain, index, spec) {
    this.terrain = terrain;
    this.car = spec ? new SandrailPhysics(terrain, spec) : new SandrailPhysics(terrain);
    this.name = NAMES[index % NAMES.length];
    this.tint = TINTS[index % TINTS.length];
    // personality
    this.cruise = 16 + Math.random() * 16;     // m/s on the flats (36..72 mph)
    this.aggro = 0.4 + Math.random() * 0.6;     // throttle eagerness
    this.target = new THREE.Vector3();
    this.mode = 'drive';
    this.modeT = 0;
    this.stuckT = 0;
    this.flipT = 0;
    this.revSteer = 0;
    this.launchT = 0;
    this.recoveryStableT = 0;
    this.recoverySign = index % 2 ? 1 : -1;
    this.skill = 1; // 0.75 cruising .. 1.3 aggressive
  }

  spawnNear(px, pz, minR, maxR, awayFrom) {
    for (let tries = 0; tries < 20; tries++) {
      let a = Math.random() * Math.PI * 2;
      if (awayFrom) a = Math.atan2(awayFrom.x, awayFrom.z) + Math.PI + (Math.random() - 0.5) * 2.2;
      const r = minR + Math.random() * (maxR - minR);
      const x = clamp(px + Math.sin(a) * r, -FINE_HALF, FINE_HALF), z = clamp(pz + Math.cos(a) * r, -FINE_HALF, FINE_HALF);
      const n = this.terrain.normal(x, z, _v);
      if (n.y < 0.9) continue; // flat enough to start on
      this.car.reset(x, z, Math.random() * Math.PI * 2);
      this.pickTarget(px, pz);
      return;
    }
    this.car.reset(px + minR, pz, 0);
    this.pickTarget(px, pz);
  }

  pickTarget(px, pz) {
    const c = this.car;
    const f = _v.set(0, 0, 1).applyQuaternion(c.quat);
    const hdg = Math.atan2(f.x, f.z);
    let x, z;
    if (Math.random() < 0.35) {
      // come play near the player
      const a = Math.random() * Math.PI * 2, r = 40 + Math.random() * 160;
      x = px + Math.sin(a) * r; z = pz + Math.cos(a) * r;
    } else {
      const a = hdg + (Math.random() - 0.5) * 2.4, r = 150 + Math.random() * 400;
      x = c.pos.x + Math.sin(a) * r; z = c.pos.z + Math.cos(a) * r;
      // stay inside the play area around the player
      const dx = x - px, dz = z - pz, d = Math.hypot(dx, dz);
      if (d > 900) { x = px + dx / d * 600; z = pz + dz / d * 600; }
    }
    this.target.set(clamp(x, -FINE_HALF, FINE_HALF), 0, clamp(z, -FINE_HALF, FINE_HALF));
  }

  update(dt, player) {
    const c = this.car, inp = c.input, T = this.terrain;
    const fwd = _v.set(0, 0, 1).applyQuaternion(c.quat);
    const fx = fwd.x, fz = fwd.z;
    const upY = _up.set(0, 1, 0).applyQuaternion(c.quat).y;
    const v = c.forwardSpeed;
    this.modeT += dt;
    c.recoveryTorqueB.set(0, 0, 0);

    // Return by driving. Never relocate a running bot, even after a player teleport.
    const pdx = c.pos.x - player.pos.x, pdz = c.pos.z - player.pos.z;
    if (pdx * pdx + pdz * pdz > 1000 * 1000)
      this.target.set(clamp(player.pos.x, -FINE_HALF, FINE_HALF), 0, clamp(player.pos.z, -FINE_HALF, FINE_HALF));

    // A settled rollover gets a bounded rolling torque, not a pose reset.
    const touching = c.hullContact > 0 || c.wheels.some(w => w.onGround);
    if (upY < 0.35 && c.speed < 5 && touching) this.flipT += dt; else this.flipT = 0;
    if (this.flipT > 2.5 && this.mode !== 'recover') {
      this.mode = 'recover'; this.modeT = 0; this.recoveryStableT = 0;
    }
    if (this.mode === 'recover') {
      inp.throttle = 0; inp.brake = 0; inp.steer = 0; inp.handbrake = true;
      T.normal(c.pos.x, c.pos.z, _ground);
      const alignment = clamp(_up.dot(_ground), -1, 1);
      _axis.crossVectors(_up, _ground);
      if (_axis.lengthSq() < 1e-6) _axis.set(0, 0, this.recoverySign).applyQuaternion(c.quat);
      _axis.normalize().applyQuaternion(_q.copy(c.quat).invert());
      const rate = Math.min(1.05, Math.acos(alignment) * 1.8), limit = c.m * Math.max(1, c.gravity) * 1.8;
      for (const axis of ['x', 'y', 'z'])
        c.recoveryTorqueB[axis] = clamp((_axis[axis] * rate - c.angVelB[axis]) * c.I[axis] * 18, -limit, limit);
      if (alignment > 0.88 && c.wheels.some(w => w.onGround)) this.recoveryStableT += dt;
      else this.recoveryStableT = 0;
      if (this.recoveryStableT > 0.4) {
        c.recoveryTorqueB.set(0, 0, 0); this.mode = 'drive'; this.modeT = 0; this.flipT = 0;
        this.stuckT = 0; this.launchT = 0; this.pickTarget(player.pos.x, player.pos.z);
      }
      c.update(dt); return;
    }

    const dx = this.target.x - c.pos.x, dz = this.target.z - c.pos.z;
    const dist = Math.hypot(dx, dz);
    if (dist < 30) this.pickTarget(player.pos.x, player.pos.z);

    // heading error: + = target is to the right
    const hdg = Math.atan2(fx, fz), want = Math.atan2(dx, dz);
    let err = want - hdg;
    while (err > Math.PI) err -= Math.PI * 2;
    while (err < -Math.PI) err += Math.PI * 2;
    err = -err; // world angle grows toward +X (east); steering +1 = right = toward -X in body frame

    // look ahead for slip faces (steep drops) and big climbs
    const look = Math.max(12, Math.abs(v) * 1.4);
    const h0 = T.height(c.pos.x, c.pos.z);
    let drop = 0, climb = 0;
    for (let k = 1; k <= 3; k++) {
      const d = look * k / 3;
      const hh = T.height(c.pos.x + fx * d, c.pos.z + fz * d) - h0;
      drop = Math.max(drop, -hh / d); climb = Math.max(climb, hh / d);
    }

    if (this.mode === 'drive') {
      let vT = this.cruise * this.skill * (1 - Math.min(0.75, Math.abs(err) / 1.4));
      if (drop > 0.35) vT = Math.min(vT, 9);          // about to go over a slip face
      else if (drop > 0.2) vT = Math.min(vT, 15);
      if (climb > 0.25) vT = Math.max(vT, 20);        // carry speed up the dune
      if (climb > 0.45 && Math.abs(v) < 6) { this.pickTarget(player.pos.x, player.pos.z); } // too steep, find another line
      let thr = clamp((vT - v) * 0.18 * (0.6 + this.aggro * this.skill) + 0.25, 0, 1);
      let brk = v > vT + 6 ? clamp((v - vT - 6) * 0.15, 0, 1) : 0;
      // launches from a stop: full send, paddles dig and the nose lifts
      if (Math.abs(v) < 2 && this.launchT <= 0 && Math.random() < dt * 0.5 * this.skill) this.launchT = 1.2 + Math.random();
      if (this.launchT > 0) { this.launchT -= dt; thr = 1; brk = 0; }
      inp.throttle = thr; inp.brake = brk;
      inp.steer = clamp(err * 1.8, -1, 1);
      inp.handbrake = false;
      // stuck detection
      if (Math.abs(v) < 1.2 && thr > 0.5) this.stuckT += dt; else this.stuckT = Math.max(0, this.stuckT - dt);
      if (this.stuckT > 4) { this.mode = 'reverse'; this.modeT = 0; this.stuckT = 0; this.revSteer = -Math.sign(err || 1); }
    } else if (this.mode === 'reverse') {
      inp.throttle = 0; inp.brake = 1; inp.steer = this.revSteer;
      if (this.modeT > 3.5) {
        this.mode = 'drive'; this.modeT = 0; this.pickTarget(player.pos.x, player.pos.z);
        // Try another line after reversing; keep the actual position and momentum.
        this.revSteer *= -1;
      }
    }
    c.update(dt);
  }
}

// Soft collisions between cars (player, bots): keeps them from driving through each other.
export function resolveCarContacts(cars, dt) {
  const R = 1.55; // per-car radius (cars are ~2.3 m wide, 4.5 m long; two circles each)
  for (let i = 0; i < cars.length; i++) for (let j = i + 1; j < cars.length; j++) {
    const a = cars[i], b = cars[j];
    const dx = b.pos.x - a.pos.x, dz = b.pos.z - a.pos.z, dy = b.pos.y - a.pos.y;
    if (dx * dx + dz * dz > 49 || Math.abs(dy) > 2.5) continue;
    // two circles per car, front and rear
    for (const oa of [-1.1, 1.1]) for (const ob of [-1.1, 1.1]) {
      const pa = _v.set(0, 0, oa).applyQuaternion(a.quat).add(a.pos);
      const ax = pa.x, az = pa.z;
      const pb = _v.set(0, 0, ob).applyQuaternion(b.quat).add(b.pos);
      const ex = pb.x - ax, ez = pb.z - az, d = Math.hypot(ex, ez);
      if (d >= 2 * R || d < 1e-4) continue;
      const nx = ex / d, nz = ez / d, pen = 2 * R - d;
      // relative velocity along normal
      const vr = (b.vel.x - a.vel.x) * nx + (b.vel.z - a.vel.z) * nz;
      const imp = Math.max(0, -vr * 0.6) + pen * 4;
      const ma = a.m, mb = b.m, w = mb / (ma + mb);
      a.vel.x -= nx * imp * w; a.vel.z -= nz * imp * w;
      b.vel.x += nx * imp * (1 - w); b.vel.z += nz * imp * (1 - w);
      a.pos.x -= nx * pen * 0.5 * w; a.pos.z -= nz * pen * 0.5 * w;
      b.pos.x += nx * pen * 0.5 * (1 - w); b.pos.z += nz * pen * 0.5 * (1 - w);
    }
  }
}

function clamp(x, a, b) { return x < a ? a : x > b ? b : x; }
