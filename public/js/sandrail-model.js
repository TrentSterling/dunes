// Procedural 3D model of the long-travel 4-seat sandrail from the reference
// photos: candy red tub with white flames, black cage with red roof, chrome
// coilovers, black A-arms, ribbed fronts, paddle rears, chrome V8 out back.
// Model space: origin mid-wheelbase on the ground, +Z forward, +X = car's left.
import * as THREE from 'three';
import { SANDRAIL_SPEC } from './vehicle-physics.js';

const UP = new THREE.Vector3(0, 1, 0);

export function makeMaterials(tint = 0xb00d12) {
  const candy = new THREE.MeshPhysicalMaterial({
    color: tint, metalness: 0.55, roughness: 0.28, clearcoat: 1.0, clearcoatRoughness: 0.04,
    sheen: 0.3, sheenColor: new THREE.Color(0xff3020),
  });
  return {
    candy,
    flames: makeFlameMaterial(tint),
    black: new THREE.MeshPhysicalMaterial({ color: 0x0c0c0d, metalness: 0.3, roughness: 0.42, clearcoat: 0.6, clearcoatRoughness: 0.2 }),
    satinBlack: new THREE.MeshStandardMaterial({ color: 0x151515, metalness: 0.2, roughness: 0.6 }),
    chrome: new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 1.0, roughness: 0.06 }),
    alu: new THREE.MeshStandardMaterial({ color: 0xc8c8cc, metalness: 1.0, roughness: 0.3 }),
    rubber: new THREE.MeshStandardMaterial({ color: 0x161616, metalness: 0.0, roughness: 0.88 }),
    seat: new THREE.MeshStandardMaterial({ color: 0x111111, metalness: 0.1, roughness: 0.55 }),
    seatRed: new THREE.MeshPhysicalMaterial({ color: 0x9a0a0e, metalness: 0.2, roughness: 0.45, clearcoat: 0.3 }),
    amber: new THREE.MeshPhysicalMaterial({ color: 0xffa000, emissive: 0x6a3000, metalness: 0.1, roughness: 0.1, transmission: 0.3, thickness: 0.01, clearcoat: 1 }),
    beadRed: new THREE.MeshPhysicalMaterial({ color: 0xc0101a, metalness: 0.8, roughness: 0.25, clearcoat: 1 }),
    mirror: new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 1, roughness: 0.02 }),
    engineRed: new THREE.MeshPhysicalMaterial({ color: 0x8a0a0c, metalness: 0.5, roughness: 0.35, clearcoat: 0.8 }),
    floor: makeDiamondPlate(tint),
  };
}

function makeFlameMaterial(tint) {
  const W = 2048, H = 512;
  const c = document.createElement('canvas');
  c.width = W; c.height = H;
  const g = c.getContext('2d');
  const base = new THREE.Color(tint);
  const grad = g.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, '#' + base.clone().multiplyScalar(1.25).getHexString());
  grad.addColorStop(0.5, '#' + base.getHexString());
  grad.addColorStop(1, '#' + base.clone().multiplyScalar(0.7).getHexString());
  g.fillStyle = grad; g.fillRect(0, 0, W, H);
  // Classic hot-rod flames: licks start behind the front shocks and stream
  // rearward, fanning slightly, each a tapered S-curve with a dark outline.
  const rnd = mulberry32(11);
  const licks = [];
  const N = 8;
  for (let i = 0; i < N; i++) {
    const f = i / (N - 1);
    licks.push({
      x0: W * (0.28 + 0.05 * Math.sin(f * Math.PI)), y: H * (0.22 + 0.58 * f),
      len: W * (0.26 + 0.24 * Math.sin(f * Math.PI) + rnd() * 0.08),
      amp: 18 + rnd() * 26, ph: rnd() * 6.28, w: 26 + 16 * Math.sin(f * Math.PI) + rnd() * 8,
      fan: (f - 0.5) * 0.5,
    });
  }
  const path = (l, inset) => {
    const steps = 80;
    g.beginPath();
    const top = [], bot = [];
    for (let s2 = 0; s2 <= steps; s2++) {
      const t = s2 / steps;
      const x = l.x0 + l.len * t;
      const yc = l.y + l.fan * l.len * 0.25 * t + Math.sin(t * 5.0 + l.ph) * l.amp * t + Math.sin(t * 11 + l.ph * 2) * 4 * t;
      const bulge = 1 + 0.8 * Math.exp(-((t - 0.12) ** 2) / 0.01);
      const hw = Math.max(0.5, l.w * Math.pow(1 - t, 0.75) * bulge - inset);
      top.push([x, yc - hw]); bot.push([x, yc + hw]);
    }
    g.moveTo(l.x0 - 10, l.y);
    for (const p of top) g.lineTo(p[0], p[1]);
    for (let i = bot.length - 1; i >= 0; i--) g.lineTo(bot[i][0], bot[i][1]);
    g.closePath();
  };
  // solid flame root that the licks grow out of
  g.fillStyle = '#ffffff';
  g.beginPath(); g.ellipse(W * 0.29, H * 0.5, W * 0.035, H * 0.33, 0, 0, Math.PI * 2); g.fill();
  for (const l of licks) { path(l, 0); g.fill(); }
  g.beginPath(); g.ellipse(W * 0.29, H * 0.5, W * 0.035, H * 0.33, 0, 0, Math.PI * 2); g.fill();
  g.strokeStyle = 'rgba(70,0,0,0.9)'; g.lineWidth = 4; g.lineJoin = 'round';
  for (const l of licks) { path(l, -2); g.stroke(); }
  // re-fill to keep overlaps clean (outline only on the outer edge)
  g.fillStyle = '#fafafa';
  for (const l of licks) { path(l, 1.5); g.fill(); }
  g.beginPath(); g.ellipse(W * 0.29, H * 0.5, W * 0.033, H * 0.31, 0, 0, Math.PI * 2); g.fill();
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 16;
  return new THREE.MeshPhysicalMaterial({ map: tex, metalness: 0.3, roughness: 0.3, clearcoat: 1.0, clearcoatRoughness: 0.04 });
}

function makeDiamondPlate(tint) {
  const c = document.createElement('canvas'); c.width = c.height = 256;
  const g = c.getContext('2d');
  g.fillStyle = '#' + new THREE.Color(tint).multiplyScalar(0.8).getHexString(); g.fillRect(0, 0, 256, 256);
  g.fillStyle = 'rgba(255,200,200,0.35)';
  for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) {
    g.save(); g.translate(x * 32 + (y % 2) * 16 + 8, y * 32 + 8); g.rotate((x + y) % 2 ? 0.6 : -0.6);
    g.fillRect(-9, -2, 18, 4); g.restore();
  }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(6, 10);
  t.colorSpace = THREE.SRGBColorSpace;
  return new THREE.MeshStandardMaterial({ map: t, metalness: 0.7, roughness: 0.35 });
}

function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

// ---------- geometry helpers ----------
const cylCache = new Map();
function unitCyl(radial = 14) {
  if (!cylCache.has(radial)) {
    const g = new THREE.CylinderGeometry(1, 1, 1, radial, 1, false);
    g.translate(0, 0.5, 0);
    cylCache.set(radial, g);
  }
  return cylCache.get(radial);
}
const sphGeo = new THREE.SphereGeometry(1, 14, 10);

// A straight tube between a and b (Vector3s), as a mesh we can re-aim later.
function rod(a, b, r, mat, radial = 14) {
  const m = new THREE.Mesh(unitCyl(radial), mat);
  m.userData.r = r;
  aimRod(m, a, b);
  m.castShadow = true; m.receiveShadow = true;
  return m;
}
const _d = new THREE.Vector3(), _q = new THREE.Quaternion();
function aimRod(m, a, b) {
  _d.subVectors(b, a);
  const len = _d.length();
  m.position.copy(a);
  m.quaternion.setFromUnitVectors(UP, _d.multiplyScalar(1 / Math.max(len, 1e-6)));
  m.scale.set(m.userData.r, len, m.userData.r);
}
function joint(p, r, mat) {
  const m = new THREE.Mesh(sphGeo, mat); m.position.copy(p); m.scale.setScalar(r); m.castShadow = true; return m;
}
// polyline cage tube with ball joints
function tubePath(group, pts, r, mat, closed = false) {
  const v = pts.map(p => p.isVector3 ? p : new THREE.Vector3(...p));
  for (let i = 0; i < v.length - 1; i++) group.add(rod(v[i], v[i + 1], r, mat));
  if (closed) group.add(rod(v[v.length - 1], v[0], r, mat));
  for (const p of v) group.add(joint(p, r * 1.02, mat));
}
// mirrored helper: given points on the left (+X) side, build both sides
function both(fn) { fn(1); fn(-1); }
const V = (x, y, z) => new THREE.Vector3(x, y, z);

// Flat panel from a polygon in a plane. pts: array of Vector3 (coplanar, CCW).
function panel(pts, mat, uvFn, thickness = 0) {
  const geo = new THREE.BufferGeometry();
  const pos = [], uv = [], idx = [];
  pts.forEach(p => { pos.push(p.x, p.y, p.z); const t = uvFn ? uvFn(p) : [0, 0]; uv.push(t[0], t[1]); });
  for (let i = 1; i < pts.length - 1; i++) idx.push(0, i, i + 1);
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  geo.setIndex(idx);
  geo.computeVertexNormals();
  const m = new THREE.Mesh(geo, mat);
  m.material.side = THREE.DoubleSide;
  m.castShadow = true; m.receiveShadow = true;
  return m;
}

function box(w, h, d, mat, x, y, z) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
  m.position.set(x, y, z); m.castShadow = true; m.receiveShadow = true;
  return m;
}

// ---------- wheels ----------
function latheTire(profile, segs = 64) {
  const pts = profile.map(([r, x]) => new THREE.Vector2(r, x));
  const g = new THREE.LatheGeometry(pts, segs);
  g.rotateZ(Math.PI / 2); // lathe axis Y -> X
  return g;
}

function makeRim(mats, radius, width, spokes) {
  const g = new THREE.Group();
  // barrel
  const barrel = new THREE.Mesh(new THREE.CylinderGeometry(radius * 0.96, radius * 0.96, width * 0.92, 40, 1, true), mats.chrome);
  barrel.rotation.z = Math.PI / 2; g.add(barrel);
  // outer lip + red beadlock ring with bolts
  const lip = new THREE.Mesh(new THREE.TorusGeometry(radius, radius * 0.06, 10, 48), mats.chrome);
  lip.rotation.y = Math.PI / 2; lip.position.x = width * 0.46; g.add(lip);
  const bead = new THREE.Mesh(new THREE.TorusGeometry(radius * 1.02, radius * 0.07, 8, 48), mats.beadRed);
  bead.rotation.y = Math.PI / 2; bead.position.x = width * 0.49; bead.scale.z = 0.6; g.add(bead);
  const boltG = new THREE.CylinderGeometry(radius * 0.025, radius * 0.025, radius * 0.06, 6);
  boltG.rotateZ(Math.PI / 2);
  const bolts = new THREE.InstancedMesh(boltG, mats.chrome, 24);
  const m4 = new THREE.Matrix4();
  for (let i = 0; i < 24; i++) {
    const a = i / 24 * Math.PI * 2;
    m4.makeTranslation(width * 0.52, Math.cos(a) * radius * 1.02, Math.sin(a) * radius * 1.02);
    bolts.setMatrixAt(i, m4);
  }
  g.add(bolts);
  // face with spokes (billet style)
  const face = new THREE.Mesh(new THREE.CylinderGeometry(radius * 0.3, radius * 0.34, width * 0.25, 24), mats.chrome);
  face.rotation.z = Math.PI / 2; face.position.x = width * 0.25; g.add(face);
  const cap = new THREE.Mesh(new THREE.SphereGeometry(radius * 0.18, 16, 10, 0, Math.PI * 2, 0, Math.PI / 2), mats.chrome);
  cap.rotation.z = -Math.PI / 2; cap.position.x = width * 0.36; g.add(cap);
  for (let i = 0; i < spokes; i++) {
    const a = i / spokes * Math.PI * 2;
    const sp = new THREE.Mesh(new THREE.BoxGeometry(width * 0.16, radius * 0.66, radius * 0.16), mats.chrome);
    sp.position.set(width * 0.3, Math.cos(a) * radius * 0.6, Math.sin(a) * radius * 0.6);
    sp.rotation.x = -a;
    g.add(sp);
  }
  g.traverse(o => { if (o.isMesh) { o.castShadow = true; } });
  return g;
}

function makeFrontWheel(mats, r, w) {
  const g = new THREE.Group();
  // ribbed sand tire: 3 rounded ribs, 2 grooves
  const prof = [];
  const rim = 0.19;
  prof.push([rim, -w * 0.48]);
  prof.push([r * 0.78, -w * 0.52]);
  const ribs = 3;
  for (let i = 0; i <= 48; i++) {
    const x = -w * 0.5 + w * i / 48;
    const t = (i / 48) * ribs;
    const inGroove = Math.abs(t - Math.round(t)) < 0.08 && i > 2 && i < 46;
    const edge = Math.cos((i / 48 - 0.5) * Math.PI) ** 0.25;
    prof.push([r * (0.86 + 0.14 * edge) - (inGroove ? 0.018 : 0), x]);
  }
  prof.push([r * 0.78, w * 0.52]);
  prof.push([rim, w * 0.48]);
  const tire = new THREE.Mesh(latheTire(prof, 72), mats.rubber);
  tire.castShadow = true; tire.receiveShadow = true;
  g.add(tire);
  g.add(makeRim(mats, rim, w * 0.9, 8));
  return g;
}

function makeRearWheel(mats, r, w, paddles = 18) {
  const g = new THREE.Group();
  const rim = 0.2, base = r - 0.045;
  const prof = [[rim, -w * 0.48], [base * 0.85, -w * 0.54], [base * 0.97, -w * 0.5], [base, -w * 0.4], [base, w * 0.4], [base * 0.97, w * 0.5], [base * 0.85, w * 0.54], [rim, w * 0.48]];
  const tire = new THREE.Mesh(latheTire(prof, 72), mats.rubber);
  tire.castShadow = true; tire.receiveShadow = true;
  g.add(tire);
  // paddles: slightly V-shaped rubber cups
  const padG = new THREE.BoxGeometry(w * 0.98, 0.05, 0.034);
  padG.translate(0, base + 0.02, 0);
  // bevel the tips by squashing top verts
  const pa = padG.attributes.position;
  for (let i = 0; i < pa.count; i++) if (pa.getY(i) > base + 0.03) pa.setX(i, pa.getX(i) * 0.94);
  padG.computeVertexNormals();
  const pads = new THREE.InstancedMesh(padG, mats.rubber, paddles);
  const m4 = new THREE.Matrix4();
  for (let i = 0; i < paddles; i++) { m4.makeRotationX(i / paddles * Math.PI * 2); pads.setMatrixAt(i, m4); }
  pads.castShadow = true; pads.receiveShadow = true;
  g.add(pads);
  g.add(makeRim(mats, rim, w * 0.85, 10));
  return g;
}

// ---------- coilover shock ----------
function makeShock(mats, bodyLen = 0.36, bodyR = 0.034) {
  const g = new THREE.Group();
  const body = new THREE.Mesh(unitCyl(20), mats.chrome); body.scale.set(bodyR, bodyLen, bodyR); g.add(body);
  const res = new THREE.Mesh(unitCyl(16), mats.chrome); res.scale.set(bodyR * 0.85, bodyLen * 0.7, bodyR * 0.85);
  res.position.set(bodyR * 2.1, bodyLen * 0.25, 0); g.add(res);
  const cap = new THREE.Mesh(unitCyl(20), mats.alu); cap.scale.set(bodyR * 1.25, 0.03, bodyR * 1.25); cap.position.y = -0.005; g.add(cap);
  const shaft = new THREE.Mesh(unitCyl(12), mats.chrome); g.add(shaft);
  // spring (helix)
  const turns = 9, pts = [];
  for (let i = 0; i <= turns * 24; i++) {
    const a = i / 24 * Math.PI * 2;
    pts.push(new THREE.Vector3(Math.cos(a) * bodyR * 1.75, i / (turns * 24), Math.sin(a) * bodyR * 1.75));
  }
  const spring = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), turns * 24, 0.0075, 6, false), mats.chrome);
  g.add(spring);
  const seat = new THREE.Mesh(unitCyl(20), mats.alu); seat.scale.set(bodyR * 2.0, 0.015, bodyR * 2.0); g.add(seat);
  const eye = new THREE.Mesh(new THREE.TorusGeometry(0.018, 0.007, 8, 16), mats.chrome); g.add(eye);
  g.userData = { body, shaft, spring, seat, eye, bodyLen };
  g.traverse(o => { if (o.isMesh) o.castShadow = true; });
  return g;
}
// aim shock: top mount a, bottom mount b (in parent space)
const _sd = new THREE.Vector3();
function aimShock(s, a, b) {
  _sd.subVectors(b, a);
  const len = _sd.length();
  s.position.copy(a);
  s.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), _sd.multiplyScalar(1 / len));
  // local -Y points from top to bottom. Body hangs from top.
  const u = s.userData;
  u.body.position.y = -u.bodyLen; u.body.scale.y = u.bodyLen;
  u.shaft.scale.set(0.011, len - u.bodyLen * 0.5, 0.011); u.shaft.position.y = -len;
  const springTop = -0.03, springBot = -len + 0.06;
  u.spring.position.y = springBot; u.spring.scale.y = (springTop - springBot);
  u.seat.position.y = springBot - 0.01;
  u.eye.position.y = -len;
}

// ---------- the car ----------
export class SandrailModel {
  constructor(opts = {}) {
    const spec = SANDRAIL_SPEC;
    this.spec = spec;
    const mats = makeMaterials(opts.tint ?? 0xb00d12);
    this.mats = mats;
    this.root = new THREE.Group();        // placed at physics CG
    this.body = new THREE.Group();        // model space
    this.body.position.set(-spec.cg[0], -spec.cg[1], -spec.cg[2]);
    this.root.add(this.body);
    this._buildTub(mats);
    this._buildCage(mats);
    this._buildInterior(mats);
    this._buildEngine(mats);
    this._buildTail(mats);
    this._buildSuspension(mats);
    this.root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  }

  _buildTub(m) {
    const b = this.body;
    const zr = -1.30, zf = 1.05, yb = 0.33, yt = 0.98;
    const uvSide = (sgn) => (p) => [(zf - p.z) / (zf - zr + 1.1) * 1.0 + 0.0, (p.y - yb) / (yt - yb)];
    both((s) => {
      const x = 0.80 * s;
      // main side panel with flames
      const side = panel([V(x, yb, zr), V(x, yb + 0.03, zf), V(x, yt, zf), V(x, yt, zr)], m.flames,
        (p) => [(zf + 1.0 - p.z) / (zf - zr + 1.0), (p.y - yb) / (yt - yb)]);
      // flip uv so flames start at the front on both sides
      b.add(side);
      // nose side panels taper to the front
      const nz = 2.12, nx = 0.24 * s;
      b.add(panel([V(x, yb + 0.03, zf), V(nx, 0.40, nz), V(nx, 0.70, nz), V(x, yt, zf)], m.flames,
        (p) => [(zf + 1.0 - p.z) / (zf - zr + 1.0), (p.y - yb) / (yt - yb)]));
      // top rail cap (black tube along the tub top edge)
      tubePath(b, [[x, yt + 0.01, zr - 0.05], [x, yt + 0.01, zf], [nx * 1.15, 0.72, nz - 0.02]], 0.022, m.black);
      // lower frame rail
      tubePath(b, [[x * 0.98, yb, zr - 0.05], [x * 0.98, yb + 0.03, zf], [nx, 0.40, nz]], 0.02, m.black);
    });
    // belly pan and nose front
    b.add(panel([V(0.8, 0.33, -1.30), V(-0.8, 0.33, -1.30), V(-0.8, 0.36, 1.05), V(-0.24, 0.40, 2.12), V(0.24, 0.40, 2.12), V(0.8, 0.36, 1.05)], m.candy));
    b.add(panel([V(0.24, 0.40, 2.12), V(-0.24, 0.40, 2.12), V(-0.24, 0.70, 2.12), V(0.24, 0.70, 2.12)], m.candy));
    // nose top / hood (front cowl) sloping up to the dash
    b.add(panel([V(0.24, 0.70, 2.12), V(-0.24, 0.70, 2.12), V(-0.80, 0.98, 1.05), V(0.80, 0.98, 1.05)], m.candy));
    // nose "chin" plate visible in the front photo
    const chin = panel([V(0.13, 0.36, 2.20), V(-0.13, 0.36, 2.20), V(-0.17, 0.72, 2.16), V(0.17, 0.72, 2.16)], m.candy);
    chin.position.z = 0.02; b.add(chin);
    // red front hoop bumper (tubular, candy red)
    tubePath(b, [[0.48, 0.88, 1.55], [0.42, 0.98, 1.95], [0.20, 1.02, 2.15], [-0.20, 1.02, 2.15], [-0.42, 0.98, 1.95], [-0.48, 0.88, 1.55]], 0.026, m.candy);
    tubePath(b, [[0.20, 1.02, 2.15], [0.16, 0.72, 2.16]], 0.024, m.candy);
    tubePath(b, [[-0.20, 1.02, 2.15], [-0.16, 0.72, 2.16]], 0.024, m.candy);
    // floor
    const fl = new THREE.Mesh(new THREE.PlaneGeometry(1.56, 2.3), m.floor);
    fl.rotation.x = -Math.PI / 2; fl.position.set(0, 0.36, -0.15); b.add(fl);
    // firewall behind rear seats
    b.add(panel([V(0.8, 0.33, -1.30), V(-0.8, 0.33, -1.30), V(-0.8, 0.98, -1.30), V(0.8, 0.98, -1.30)], m.candy));
  }

  _buildCage(m) {
    const b = this.body, r = 0.022;
    const yT = 1.78; // roof height
    both((s) => {
      const x = 0.74 * s, xt = 0.66 * s;
      // A-pillar from front of tub up to roof front
      tubePath(b, [[0.80 * s, 0.98, 1.05], [xt, yT, 0.62], [xt, yT, -1.22], [0.80 * s, 0.98, -1.30]], r, m.black);
      // B pillar
      tubePath(b, [[0.80 * s, 0.98, -0.20], [xt, yT, -0.22]], r, m.black);
      // A-pillar down-bar into nose (the forward bars in photos)
      tubePath(b, [[xt, yT, 0.62], [0.50 * s, 1.08, 1.45], [0.40 * s, 0.90, 1.85]], r, m.black);
      // side diagonals / door bars
      tubePath(b, [[0.80 * s, 0.98, 0.70], [0.80 * s, 0.98, -0.20]], r * 0.9, m.black);
      tubePath(b, [[x * 1.05, 1.18, -0.20], [x * 1.05, 1.18, -1.28]], r * 0.8, m.black);
      // rear down bars to the tail
      tubePath(b, [[xt, yT, -1.22], [0.62 * s, 1.15, -2.05]], r, m.black);
      // rear shock tower bar
      tubePath(b, [[0.80 * s, 0.98, -1.30], [0.80 * s, 1.40, -1.30], [xt, yT, -1.22]], r, m.black);
    });
    // roof cross bars
    tubePath(b, [[0.66, 1.78, 0.62], [-0.66, 1.78, 0.62]], r, m.black);
    tubePath(b, [[0.66, 1.78, -0.22], [-0.66, 1.78, -0.22]], r, m.black);
    tubePath(b, [[0.66, 1.78, -1.22], [-0.66, 1.78, -1.22]], r, m.black);
    // rear X brace
    tubePath(b, [[0.66, 1.78, -1.22], [-0.80, 0.98, -1.30]], r * 0.9, m.black);
    tubePath(b, [[-0.66, 1.78, -1.22], [0.80, 0.98, -1.30]], r * 0.9, m.black);
    // dash bar with amber lights
    tubePath(b, [[0.50, 1.08, 1.45], [-0.50, 1.08, 1.45]], r, m.black);
    tubePath(b, [[0.80, 0.98, 1.05], [0.50, 1.08, 1.45]], r * 0.9, m.black);
    tubePath(b, [[-0.80, 0.98, 1.05], [-0.50, 1.08, 1.45]], r * 0.9, m.black);
    // center windshield bar
    tubePath(b, [[0, 1.78, 0.62], [0, 1.09, 1.45]], r * 0.9, m.black);
    // red roof panel (slightly inset), with rivet rows
    const roof = box(1.30, 0.012, 1.86, m.candy, 0, 1.80, -0.30);
    b.add(roof);
    const rivG = new THREE.SphereGeometry(0.006, 6, 4);
    const rivets = new THREE.InstancedMesh(rivG, m.chrome, 80);
    const m4 = new THREE.Matrix4(); let k = 0;
    for (let i = 0; i < 20; i++) for (const sx of [-0.62, 0.62]) { m4.makeTranslation(sx, 1.807, 0.6 - i * 0.096); rivets.setMatrixAt(k++, m4); }
    for (let i = 0; i < 20; i++) for (const sz of [0.6, -1.2]) { m4.makeTranslation(-0.6 + i * 0.063, 1.807, sz); rivets.setMatrixAt(k++, m4); }
    b.add(rivets);
    // amber oval lights on the dash bar
    both((s) => {
      const lg = new THREE.Group();
      const bucket = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.06, 0.07, 24), m.chrome);
      bucket.rotation.x = Math.PI / 2; lg.add(bucket);
      const lens = new THREE.Mesh(new THREE.CircleGeometry(0.068, 24), m.amber);
      lens.position.z = 0.036; lg.add(lens);
      lg.scale.set(1.25, 0.8, 1);
      lg.position.set(0.40 * s, 1.18, 1.47);
      const stalk = rod(V(0.40 * s, 1.08, 1.45), V(0.40 * s, 1.15, 1.46), 0.01, m.chrome);
      b.add(lg, stalk);
    });
    // center rear-view mirror
    const mir = box(0.22, 0.06, 0.01, m.mirror, 0, 1.70, 0.58); b.add(mir);
    b.add(rod(V(0, 1.78, 0.60), V(0, 1.73, 0.585), 0.008, m.chrome));
  }

  _buildInterior(m) {
    const b = this.body;
    const seat = (x, z) => {
      const g = new THREE.Group();
      const base = box(0.46, 0.10, 0.48, m.seat, 0, 0.47, 0); g.add(base);
      const back = box(0.46, 0.66, 0.10, m.seat, 0, 0.82, -0.25); back.rotation.x = -0.18; g.add(back);
      const bolsterL = box(0.06, 0.55, 0.12, m.seatRed, 0.21, 0.80, -0.22); bolsterL.rotation.x = -0.18; g.add(bolsterL);
      const bolsterR = bolsterL.clone(); bolsterR.position.x = -0.21; g.add(bolsterR);
      const head = box(0.30, 0.16, 0.10, m.seat, 0, 1.22, -0.32); head.rotation.x = -0.18; g.add(head);
      const insert = box(0.26, 0.40, 0.02, m.seatRed, 0, 0.84, -0.19); insert.rotation.x = -0.18; g.add(insert);
      // harness straps
      for (const sx of [-0.08, 0.08]) { const st = box(0.045, 0.6, 0.008, m.seatRed, sx, 0.84, -0.18); st.rotation.x = -0.18; g.add(st); }
      g.position.set(x, 0, z);
      b.add(g);
    };
    seat(0.38, 0.40); seat(-0.38, 0.40); seat(0.38, -0.78); seat(-0.38, -0.78);
    // steering wheel (driver on the left, +X)
    const sw = new THREE.Group();
    const rim = new THREE.Mesh(new THREE.TorusGeometry(0.16, 0.016, 10, 32), m.seatRed); sw.add(rim);
    for (let i = 0; i < 3; i++) { const sp = box(0.012, 0.15, 0.02, m.chrome, 0, 0, 0); sp.position.set(Math.cos(i * 2.09) * 0.075, Math.sin(i * 2.09) * 0.075, 0); sp.rotation.z = i * 2.09 + Math.PI / 2; sw.add(sp); }
    sw.add(new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.03, 16).rotateX(Math.PI / 2), m.chrome));
    sw.position.set(0.38, 1.02, 0.86); sw.rotation.x = -0.5;
    this.steeringWheel = sw;
    b.add(sw);
    b.add(rod(V(0.38, 1.02, 0.86), V(0.38, 0.78, 1.30), 0.018, m.chrome));
    // dash panel
    b.add(box(1.4, 0.22, 0.05, m.satinBlack, 0, 0.92, 1.0));
    // shifter
    b.add(rod(V(0.02, 0.40, 0.55), V(0.02, 0.75, 0.48), 0.012, m.chrome));
    b.add(joint(V(0.02, 0.76, 0.48), 0.025, m.black));
  }

  _buildEngine(m) {
    const b = this.body;
    const e = new THREE.Group();
    e.position.set(0, 0.0, -1.92);
    b.add(e);
    // block + oil pan (red)
    e.add(box(0.48, 0.34, 0.70, m.engineRed, 0, 0.62, 0));
    e.add(box(0.40, 0.12, 0.62, m.satinBlack, 0, 0.40, 0));
    // heads + chrome valve covers on each bank (V8, 45 deg)
    both((s) => {
      const vc = box(0.16, 0.10, 0.66, m.chrome, 0.24 * s, 0.86, 0);
      vc.rotation.z = -0.62 * s; e.add(vc);
      const fins = box(0.17, 0.02, 0.62, m.alu, 0.255 * s, 0.92, 0); fins.rotation.z = -0.62 * s; e.add(fins);
      // headers: 4 chrome primaries per side sweeping back and out
      for (let i = 0; i < 4; i++) {
        const z0 = -0.24 + i * 0.16;
        const pts = [V(0.36 * s, 0.70, z0), V(0.50 * s, 0.62, z0 - 0.05), V(0.56 * s, 0.56, -0.40), V(0.50 * s, 0.56, -0.62)];
        const tube = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 16, 0.026, 10), m.chrome);
        e.add(tube);
      }
      // collector + exhaust tip out the back
      e.add(rod(V(0.50 * s, 0.56, -0.62), V(0.48 * s, 0.58, -0.95), 0.05, m.chrome, 18));
      const tip = new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.055, 0.04, 18, 1, true), m.chrome);
      tip.rotation.x = Math.PI / 2; tip.position.set(0.48 * s, 0.58, -0.97); e.add(tip);
    });
    // intake: supercharger case + chrome air cleaner on top
    e.add(box(0.30, 0.16, 0.50, m.chrome, 0, 0.95, 0.02));
    const ac = new THREE.Mesh(new THREE.CylinderGeometry(0.20, 0.20, 0.10, 32), m.chrome); ac.position.set(0, 1.10, 0.02); e.add(ac);
    const acf = new THREE.Mesh(new THREE.CylinderGeometry(0.19, 0.19, 0.06, 32), m.satinBlack); acf.position.set(0, 1.05, 0.02); e.add(acf);
    // front pulleys / belt
    const pul = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.09, 0.04, 24), m.chrome); pul.rotation.x = Math.PI / 2; pul.position.set(0, 0.62, 0.37); e.add(pul);
    // transaxle under the rear axle line
    const tx = box(0.40, 0.26, 0.42, m.alu, 0, 0.42, 0.25); e.add(tx);
    this.engine = e;
  }

  _buildTail(m) {
    const b = this.body;
    // flat, wide rear tray / wing above the engine sloping up at the back
    const zf = -2.08, zb = -2.78, yf = 1.02, yb2 = 1.20, w = 0.96;
    b.add(panel([V(w, yf, zf), V(-w, yf, zf), V(-w, yb2, zb), V(w, yb2, zb)], m.candy));
    // side plates
    both((s) => {
      b.add(panel([V(w * s, yf, zf), V(w * s, yb2, zb), V(w * s, yb2 - 0.28, zb), V(w * s, yf - 0.06, zf)], m.candy));
    });
    // rear lower red frame (bumper) like the rear photo
    tubePath(b, [[0.92, 0.95, -2.75], [0.70, 0.55, -2.70], [-0.70, 0.55, -2.70], [-0.92, 0.95, -2.75]], 0.026, m.candy);
    tubePath(b, [[0.70, 0.55, -2.70], [0.62, 0.45, -2.10]], 0.022, m.candy);
    tubePath(b, [[-0.70, 0.55, -2.70], [-0.62, 0.45, -2.10]], 0.022, m.candy);
    tubePath(b, [[0.62, 1.15, -2.05], [0.62, 0.45, -2.10], [0.80, 0.33, -1.30]], 0.022, m.black);
    tubePath(b, [[-0.62, 1.15, -2.05], [-0.62, 0.45, -2.10], [-0.80, 0.33, -1.30]], 0.022, m.black);
    tubePath(b, [[0.62, 1.15, -2.05], [-0.62, 1.15, -2.05]], 0.022, m.black);
  }

  _buildSuspension(m) {
    const b = this.body;
    this.wheelRigs = [];
    const spec = this.spec;
    spec.wheels.forEach((w, i) => {
      const s = Math.sign(w.x);
      const rig = { spec: w, s };
      // hub pivot (moves with suspension), steer group, spin group
      rig.hub = new THREE.Group();
      rig.steer = new THREE.Group();
      rig.spin = w.front ? makeFrontWheel(m, w.r, w.w) : makeRearWheel(m, w.r, w.w);
      // wheel geometry built along +X outward: mirror for the right side
      if (s < 0) rig.spin.scale.x = -1;
      rig.spinHolder = new THREE.Group();
      rig.spinHolder.add(rig.spin);
      rig.steer.add(rig.spinHolder);
      rig.hub.add(rig.steer);
      // knuckle / upright
      const upr = box(0.06, 0.26, 0.10, m.satinBlack, -0.12 * s, 0, 0); rig.steer.add(upr);
      const hubCap = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.10, 16).rotateZ(Math.PI / 2), m.alu);
      hubCap.position.x = -0.07 * s; rig.steer.add(hubCap);
      b.add(rig.hub);
      if (w.front) {
        // A-arm chassis pivots (front/rear legs), upper and lower
        rig.lowerPiv = [V(0.24 * s, 0.38, 1.98), V(0.30 * s, 0.36, 1.45)];
        rig.upperPiv = [V(0.26 * s, 0.64, 1.92), V(0.32 * s, 0.62, 1.50)];
        rig.arms = [];
        for (let k = 0; k < 4; k++) { const a = rod(V(), V(0, 1, 0), 0.02, m.black); b.add(a); rig.arms.push(a); }
        rig.shockTop = V(0.44 * s, 1.10, 1.62);
        rig.shock = makeShock(m, 0.34, 0.036); b.add(rig.shock);
        // tie rod
        rig.tie = rod(V(), V(0, 1, 0), 0.012, m.chrome); b.add(rig.tie);
        rig.tiePiv = V(0.22 * s, 0.50, 1.86);
      } else {
        // trailing arm: pivot forward at the chassis, boxed arm to the hub
        rig.trailPiv = V(0.74 * s, 0.50, -0.55);
        rig.arms = [rod(V(), V(0, 1, 0), 0.035, m.black), rod(V(), V(0, 1, 0), 0.028, m.black)];
        rig.arms.forEach(a => b.add(a));
        rig.shockTop = V(0.80 * s, 1.40, -1.32);
        rig.shock = makeShock(m, 0.40, 0.04); b.add(rig.shock);
        // second shock (bypass) as in the photos: dual chrome coilovers
        rig.shock2 = makeShock(m, 0.38, 0.034); b.add(rig.shock2);
        rig.shockTop2 = V(0.70 * s, 1.36, -1.30);
        // CV axle from transaxle
        rig.axle = rod(V(), V(0, 1, 0), 0.03, m.alu); b.add(rig.axle);
      }
      this.wheelRigs.push(rig);
    });
    this.update(null);
  }

  // Pose from a physics state (SandrailPhysics.getState().w array) or null for ride height.
  update(wheelStates, steerAngle = 0) {
    const spec = this.spec;
    this.wheelRigs.forEach((rig, i) => {
      const w = rig.spec;
      const ws = wheelStates ? wheelStates[i] : [w.sag, 0, 0, 0];
      const comp = ws[0], angle = ws[1], steer = ws[2];
      const hubY = w.y - w.sag + comp;
      rig.hub.position.set(w.x, hubY, w.z);
      rig.steer.rotation.y = steer;
      rig.spinHolder.rotation.x = angle;
      const s = rig.s;
      if (w.front) {
        const ballLow = V(w.x - 0.13 * s, hubY - 0.11, w.z);
        const ballUp = V(w.x - 0.15 * s, hubY + 0.12, w.z);
        aimRod(rig.arms[0], rig.lowerPiv[0], ballLow);
        aimRod(rig.arms[1], rig.lowerPiv[1], ballLow);
        aimRod(rig.arms[2], rig.upperPiv[0], ballUp);
        aimRod(rig.arms[3], rig.upperPiv[1], ballUp);
        const lowMount = new THREE.Vector3().lerpVectors(new THREE.Vector3().addVectors(rig.lowerPiv[0], rig.lowerPiv[1]).multiplyScalar(0.5), ballLow, 0.72);
        aimShock(rig.shock, rig.shockTop, lowMount);
        const tieEnd = V(w.x - 0.14 * s + Math.sin(steer) * 0.0, hubY + 0.0, w.z + 0.10 - steer * 0.1 * s);
        aimRod(rig.tie, rig.tiePiv, tieEnd);
      } else {
        const hubIn = V(w.x - 0.16 * s, hubY, w.z);
        aimRod(rig.arms[0], rig.trailPiv, hubIn);
        aimRod(rig.arms[1], V(rig.trailPiv.x, rig.trailPiv.y + 0.22, rig.trailPiv.z - 0.1), V(hubIn.x, hubY + 0.1, w.z + 0.08));
        const mount = new THREE.Vector3().lerpVectors(rig.trailPiv, hubIn, 0.86);
        aimShock(rig.shock, rig.shockTop, mount);
        aimShock(rig.shock2, rig.shockTop2, new THREE.Vector3().lerpVectors(rig.trailPiv, hubIn, 0.78));
        aimRod(rig.axle, V(0.18 * s, 0.42, -1.67), hubIn);
      }
    });
    if (this.steeringWheel) this.steeringWheel.rotation.z = steerAngle * 6;
  }
}
