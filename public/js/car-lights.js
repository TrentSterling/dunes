// LED light bar on the roof and two flexible LED whip lights with flags at the
// back of the cage, for any sandrail model. The whips are a damped spring: they
// lean back with speed, swing through turns and bumps, and sag downhill.
import * as THREE from 'three';

const mountCache = new WeakMap();

// roof outline in the body frame (+X left, +Z forward, origin on the ground)
function measureMount(model) {
  const key = model.tpl || model.constructor;
  if (mountCache.has(key)) return mountCache.get(key);
  const body = model.body;
  body.updateMatrixWorld(true);
  const inv = new THREE.Matrix4().copy(body.matrixWorld).invert();
  const m = new THREE.Matrix4(), v = new THREE.Vector3();
  const pts = [];
  body.traverse((o) => {
    if (!o.isMesh || !o.geometry?.attributes?.position) return;
    for (let p = o; p && p !== body; p = p.parent) if (/wheel|tire|tyre|rim|lightbar/i.test(p.name)) return;
    m.multiplyMatrices(inv, o.matrixWorld);
    const pos = o.geometry.attributes.position;
    const step = Math.max(1, Math.floor(pos.count / 4000));
    for (let i = 0; i < pos.count; i += step) { v.fromBufferAttribute(pos, i).applyMatrix4(m); pts.push(v.x, v.y, v.z); }
  });
  let top = -Infinity;
  for (let i = 1; i < pts.length; i += 3) if (pts[i] < 2.6 && pts[i] > top) top = pts[i];
  if (!isFinite(top)) top = 1.8;
  let zF = -Infinity, zR = Infinity, xW = 0;
  for (let i = 0; i < pts.length; i += 3) {
    if (pts[i + 1] < top - 0.18 || pts[i + 1] > top + 0.01) continue;
    zF = Math.max(zF, pts[i + 2]); zR = Math.min(zR, pts[i + 2]); xW = Math.max(xW, Math.abs(pts[i]));
  }
  if (!isFinite(zF)) { zF = 0.6; zR = -0.6; xW = 0.6; }
  xW = Math.min(Math.max(xW, 0.4), 0.85);
  const mount = { top, zF, zR, xW };
  mountCache.set(key, mount);
  return mount;
}

// soft round glow for the LEDs at night
let glowTex = null;
function glowTexture() {
  if (glowTex) return glowTex;
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d');
  const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.25, 'rgba(255,255,255,0.45)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
  glowTex = new THREE.CanvasTexture(c);
  glowTex.colorSpace = THREE.SRGBColorSpace;
  return glowTex;
}

const RINGS = 22, SIDES = 6, WHIP_L = 1.75, WHIP_R = 0.011;
const _c = new THREE.Color(), _v = new THREE.Vector3(), _w = new THREE.Vector3(), _q = new THREE.Quaternion();

class Whip {
  constructor(parent, base, tip) {
    this.base = base; this.tip = tip; // white LED rod, top light in the car's color
    this.th = new THREE.Vector2(); this.om = new THREE.Vector2(); // bend (x left, z forward), rate
    this.group = new THREE.Group(); parent.add(this.group);
    const n = RINGS * SIDES;
    const geo = new THREE.BufferGeometry();
    this.pos = new Float32Array(n * 3); this.col = new Float32Array(n * 3);
    geo.setAttribute('position', new THREE.BufferAttribute(this.pos, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(this.col, 3));
    const idx = [];
    for (let r = 0; r < RINGS - 1; r++) for (let s = 0; s < SIDES; s++) {
      const a = r * SIDES + s, b = r * SIDES + (s + 1) % SIDES, c = a + SIDES, d = b + SIDES;
      idx.push(a, c, b, b, c, d);
    }
    geo.setIndex(idx);
    this.geo = geo;
    this.rod = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ vertexColors: true, toneMapped: false }));
    this.rod.frustumCulled = false;
    this.group.add(this.rod);
    // glow halo along the whip (sprites at a few points)
    this.glows = [];
    for (let i = 0; i < 5; i++) {
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.5, toneMapped: false }));
      s.scale.setScalar(0.32); this.group.add(s); this.glows.push(s);
    }
    // the top light: a bigger glow in the car's color
    this.tipGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: tip, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.9, toneMapped: false }));
    this.tipGlow.scale.setScalar(0.5); this.group.add(this.tipGlow);
    // flag at the tip
    const fg = new THREE.PlaneGeometry(0.34, 0.22, 6, 1); fg.translate(0.17, -0.11, 0);
    this.flagBase = Float32Array.from(fg.attributes.position.array);
    this.flag = new THREE.Mesh(fg, new THREE.MeshStandardMaterial({ color: 0xff5a10, side: THREE.DoubleSide, roughness: 0.8 }));
    this.flag.castShadow = true;
    this.group.add(this.flag);
    this.pts = Array.from({ length: RINGS }, () => new THREE.Vector3());
    this.t = Math.random() * 10;
  }

  // a: proper acceleration of the mount in the body frame (m/s^2, gravity included), v: air speed in body frame
  step(dt, a, v, rough) {
    const K = 150, C = 2.2, G = 6.5, D = 0.1;
    const sub = Math.max(1, Math.ceil(dt / 0.004)), h = dt / sub;
    for (let i = 0; i < sub; i++) {
      // inertia bends the whip against the push, air drag lays it back
      const fx = -G * a.x - D * v.x * Math.abs(v.x) - K * this.th.x - C * this.om.x + rough * (Math.random() - 0.5);
      const fz = -G * a.z - D * v.z * Math.abs(v.z) - K * this.th.y - C * this.om.y + rough * (Math.random() - 0.5);
      this.om.x += fx * h; this.om.y += fz * h;
      this.th.x += this.om.x * h; this.th.y += this.om.y * h;
    }
    const m = this.th.length();
    if (m > 1.05) { this.th.multiplyScalar(1.05 / m); this.om.multiplyScalar(0.5); }
    this.t += dt;
  }

  build(on, wind) {
    const th = this.th, m = th.length(), ux = m > 1e-5 ? th.x / m : 0, uz = m > 1e-5 ? th.y / m : 0;
    // cantilever bend: angle grows along the rod
    const p = this.pts; let x = this.base.x, y = this.base.y, z = this.base.z;
    const ds = WHIP_L / (RINGS - 1);
    for (let r = 0; r < RINGS; r++) {
      p[r].set(x, y, z);
      const s = (r + 0.5) / (RINGS - 1), phi = m * (2 * s - s * s);
      const sp = Math.sin(phi), cp = Math.cos(phi);
      x += ux * sp * ds; y += cp * ds; z += uz * sp * ds;
    }
    const pos = this.pos, col = this.col;
    for (let r = 0; r < RINGS; r++) {
      const a = p[Math.max(0, r - 1)], b = p[Math.min(RINGS - 1, r + 1)];
      const t = _v.subVectors(b, a).normalize();
      const n1 = _w.set(-t.y, t.x, 0); if (n1.lengthSq() < 1e-6) n1.set(1, 0, 0); n1.normalize();
      const n2 = new THREE.Vector3().crossVectors(t, n1);
      const rad = WHIP_R * (1 - 0.5 * r / RINGS);
      // RGB chase climbing the whip
      const f = r / (RINGS - 1);
      if (on) { if (r >= RINGS - 3) _c.copy(this.tip).multiplyScalar(2.2); else _c.setRGB(1.6, 1.6, 1.6); }
      else _c.setRGB(0.05, 0.05, 0.055);
      for (let s = 0; s < SIDES; s++) {
        const ang = s / SIDES * Math.PI * 2, ca = Math.cos(ang) * rad, sa = Math.sin(ang) * rad;
        const k = (r * SIDES + s) * 3;
        pos[k] = p[r].x + n1.x * ca + n2.x * sa; pos[k + 1] = p[r].y + n1.y * ca + n2.y * sa; pos[k + 2] = p[r].z + n1.z * ca + n2.z * sa;
        col[k] = _c.r; col[k + 1] = _c.g; col[k + 2] = _c.b;
      }
    }
    this.geo.attributes.position.needsUpdate = true; this.geo.attributes.color.needsUpdate = true;
    this.geo.computeBoundingSphere();
    for (let i = 0; i < this.glows.length; i++) {
      const r = Math.round((i + 0.5) / this.glows.length * (RINGS - 1));
      const g = this.glows[i];
      g.visible = on;
      if (on) { g.position.copy(p[r]); g.material.color.set(0xffffff); g.material.opacity = 0.35; }
    }
    this.tipGlow.visible = on; this.tipGlow.position.copy(p[RINGS - 1]);
    // flag: hangs off the tip, streams away from the air flow and flutters
    const tip = p[RINGS - 1];
    this.flag.position.copy(tip);
    this.flag.rotation.set(0, Math.atan2(wind.z, -wind.x), 0);
    const fa = this.flag.geometry.attributes.position, b0 = this.flagBase;
    const sp = Math.min(1, wind.length() / 15);
    for (let i = 0; i < fa.count; i++) {
      const u = b0[i * 3] / 0.34;
      fa.array[i * 3 + 2] = b0[i * 3 + 2] + Math.sin(u * 7 - this.t * (6 + 14 * sp)) * u * (0.03 + 0.05 * sp);
      fa.array[i * 3 + 1] = b0[i * 3 + 1] - u * u * 0.12 * (1 - sp);
    }
    fa.needsUpdate = true;
  }
}

export class CarLights {
  constructor(model, color = 0xff2020) {
    this.color = new THREE.Color(color);
    // a black car can't have a black LED: its top light glows white instead
    if (Math.max(this.color.r, this.color.g, this.color.b) < 0.25) this.color.set(0xffffff);
    this.model = model;
    this.on = false;
    const M = measureMount(model);
    this.mount = M;
    const g = this.group = new THREE.Group();
    model.body.add(g);
    // light bar: the model's own bar when it has one (node 'LightBar'), else a black housing on the roof
    let w = Math.min(1.25, M.xW * 1.7);
    this.barLocal = new THREE.Vector3(0, M.top + 0.07, M.zF - 0.02);
    let faceZ = 0.047, faceH = 0.05;
    const own = model.model?.getObjectByName?.('LightBar');
    if (own) {
      model.body.updateMatrixWorld(true);
      const inv = new THREE.Matrix4().copy(model.body.matrixWorld).invert();
      const bb = new THREE.Box3();
      own.traverse((o) => { if (o.isMesh) { o.geometry.computeBoundingBox(); bb.union(o.geometry.boundingBox.clone().applyMatrix4(new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld))); } });
      const size = bb.getSize(new THREE.Vector3());
      bb.getCenter(this.barLocal);
      w = size.x * 0.96; faceZ = size.z / 2 + 0.004; faceH = size.y * 0.55;
    } else {
      const housing = new THREE.Mesh(new THREE.BoxGeometry(w, 0.085, 0.09), new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.5, metalness: 0.3 }));
      housing.position.copy(this.barLocal); housing.castShadow = true;
      g.add(housing);
    }
    this.ownBar = !!own;
    this.ledMat = new THREE.MeshBasicMaterial({ color: 0x222222, toneMapped: false });
    const led = new THREE.Mesh(new THREE.BoxGeometry(w * 0.94, faceH, 0.01), this.ledMat);
    led.position.copy(this.barLocal).add(new THREE.Vector3(0, 0, faceZ));
    led.visible = !own; // the model's own LED face shows when the lights are off
    this.led = led;
    g.add(led);
    this.barGlow = [];
    for (let i = 0; i < 5; i++) {
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: 0xdfeaff, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.75, toneMapped: false }));
      s.position.copy(this.barLocal).add(new THREE.Vector3((i / 4 - 0.5) * w * 0.85, 0, faceZ + 0.045));
      s.scale.setScalar(0.55); s.visible = false;
      g.add(s); this.barGlow.push(s);
    }
    // whips at the back corners of the cage
    const zW = M.zR + 0.05;
    this.whips = [new Whip(g, new THREE.Vector3(M.xW * 0.85, M.top - 0.02, zW), this.color), new Whip(g, new THREE.Vector3(-M.xW * 0.85, M.top - 0.02, zW), this.color)];
    this.prevV = null;
    this.aB = new THREE.Vector3(); this.vB = new THREE.Vector3();
    this._t = 0;
  }

  setOn(on) {
    if (on === this.on) return;
    this.on = on;
    this.ledMat.color.set(on ? 0xffffff : 0x222222).multiplyScalar(on ? 2.2 : 1);
    if (this.ownBar) this.led.visible = on;
    for (const s of this.barGlow) s.visible = on;
  }

  // vel: world velocity of the car, quat: its orientation, camDist: for skipping far work
  update(dt, vel, quat, camDist, wind, rough = 0) {
    if (dt <= 0) return;
    // proper acceleration in the body frame (what the whip mount feels)
    if (!this.prevV) this.prevV = vel.clone();
    const a = _v.subVectors(vel, this.prevV).multiplyScalar(1 / dt);
    this.prevV.copy(vel);
    a.y += 9.81;
    if (a.length() > 120) a.setLength(120); // resets, teleports
    _q.copy(quat).invert();
    this.aB.lerp(a.applyQuaternion(_q), Math.min(1, dt * 25));
    this.vB.copy(vel).sub(wind).applyQuaternion(_q);
    const far = camDist > 220;
    for (const wh of this.whips) {
      wh.step(dt, this.aB, this.vB, rough);
      if (!far) wh.build(this.on, this.vB);
    }
    this.group.visible = camDist < 900;
  }

  // world position and aim of the light bar (for lighting the sand)
  barWorld(outPos, outDir) {
    this.model.body.localToWorld(outPos.copy(this.barLocal).add(_w.set(0, 0, 0.12)));
    outDir.set(0, -0.13, 1).normalize().applyQuaternion(this.model.root.quaternion);
    return outPos;
  }
  whipWorld(i, out) { return this.model.body.localToWorld(out.copy(this.whips[i].pts[Math.floor(RINGS * 0.6)])); }
}
