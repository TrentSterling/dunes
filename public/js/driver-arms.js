// The driver's arms and gloves for the cockpit view: fire-suit sleeves from the shoulders to
// racing gloves that grip the steering wheel at a quarter past nine and turn with it.
//
// assets/driver/arms.glb (built by trx-build/arms/build_arms.py) is one skinned mesh with six flat
// bones (UpperArm/ForeArm/Hand .L/.R), the gloves modelled curled round a 28 mm rim, morph targets
// OpenL/OpenR (open hand) and empties Grip.L/Grip.R (the rest grip frame of each glove: X along the
// rim, Y = column axis toward the driver, Z = radially inward, i.e. Blender's R x A / A / R turned
// to glTF axes; extras grip_x_min/max = glove extent along the rim).
// Each frame: each glove holds the rim at a fixed spot and turns with the wheel while it stays in a
// comfortable zone round its home (9:15); when it leaves the zone the hand lets go and re-grips
// near home: it slides back along the rim with loosened fingers (opening them and lifting off a
// little only while it passes over a spoke), always to a spot clear of the spokes and of the other
// glove - shuffle steering, one hand at a time, both gloves stay on the rim. Back near straight
// ahead both hands return to 9:15. The forearm and upper arm follow by two-bone IK from a fixed shoulder (elbows down
// and out). update(angle, dt) - dt in seconds, measured from the clock when left out.
// (r6) Rest grip at 9:15 instead of ten and two (at 10 / 2 the gloves covered the live dash screen's readouts): each
// hand sits on the rim just above its 3 / 9 spoke, the glove's lower edge on the spoke's suede sleeve (that one overlap
// is allowed at the rest spot only), and is rolled ROLL about the rim tangent so the knuckles face up and back toward
// the driver's eye and the finger tips show on the rim's inner side.
// Until the asset loads (or if it fails) the old procedural arms are shown.
// The asset also holds 'DriverLegs' (r4): static fire-suit legs and race boots posed on the pedals of the
// GLX cockpit; they are shown only in a car whose driver's eye matches the one they were built for.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone as cloneSkinned } from 'three/addons/utils/SkeletonUtils.js';
import { patchMaterial } from './gltf-sandrail.js';
import { LAYER_ARMS } from './cockpit-live.js';

const ARMS_URL = 'assets/driver/arms.glb';
let armsAsset = null;
// tests / tools can hand in an already loaded (or loading) arms glTF
export function setArmsAsset(gltfOrPromise) { armsAsset = Promise.resolve(gltfOrPromise); }
function loadArmsAsset() {
  if (!armsAsset) armsAsset = new GLTFLoader().loadAsync(ARMS_URL).catch((e) => { console.warn('driver arms: using the simple arms,', e?.message || e); return null; });
  return armsAsset;
}

const _q = new THREE.Quaternion(), _a = new THREE.Vector3(), _b = new THREE.Vector3(), _c = new THREE.Vector3(), _d = new THREE.Vector3();
const _m = new THREE.Matrix4(), _m2 = new THREE.Matrix4(), _s = new THREE.Vector3();
const UP = new THREE.Vector3(0, 1, 0);
const ARMS_LOOK = { ao: 0, envSat: 0.3, ambSat: 0.35, direct: 0 };
// the legs sit in the dark footwell under the dash (no baked AO): less sky light than the arms
const LEGS_LOOK = { ao: 0, envSat: 0.3, ambSat: 0.35, direct: 0, amb: 0.45, env: 0.5 };
const GRIP = 0.14;                       // home: 9:15, the grip point this far above horizontal (rad): glove centres ~9 deg up
const ROLL = 0.47;                       // gloves rolled about the rim tangent toward the driver (rad), knuckles up / back
const PUSH = 0.65, PULL = 1.2;           // comfort zone: a hand turns with the wheel this far up / down (rad)
const HOP_T = 0.24;                      // seconds to slide a hand back along the rim and re-grip
const LOOSE = 0.3;                       // fingers loosened (open morph) while a hand slides
const LIFT_R = 0.013, LIFT_A = 0.02;     // passing over a spoke: out from the rim / toward the driver (m)
// shoulders relative to the eye (body frame: +X left, +Y up, +Z forward), a little protracted toward
// the wheel so the elbows keep a natural bend (trx-build/arms/build_arms.py uses the same offsets)
export const SHOULDER = { x: 0.2, y: -0.29, z: -0.07 };
const CLEAR = 0.03;                      // spare angle between a glove and a spoke (rad)
const smooth = (e0, e1, x) => { const t = THREE.MathUtils.clamp((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t); };
const wrap = (a) => Math.atan2(Math.sin(a), Math.cos(a));

// rotation taking the orthonormal basis (d0, n0, d0 x n0) to (d1, n1, d1 x n1)
function basisQuat(d0, n0, d1, n1, out) {
  const B0 = _m.makeBasis(d0, n0, _a.crossVectors(d0, n0));
  const B1 = _m2.makeBasis(d1, n1, _b.crossVectors(d1, n1));
  return out.setFromRotationMatrix(B1.multiply(B0.transpose()));
}

export class DriverArms {
  // model: GltfSandrail (body frame +X left, +Z forward); returns null without a steering wheel
  static for(model) {
    const sw = model.steeringWheel;
    if (!sw || !model.eye) return null;
    return new DriverArms(model, sw);
  }

  constructor(model, sw) {
    this.model = model;
    const body = model.body;
    model.root.updateMatrixWorld(true);
    const inv = body.matrixWorld.clone().invert();
    const M = inv.clone().multiply(sw.matrixWorld);
    // wheel centre, column axis (toward the driver), rim centre-line radius, rim tube radius, spokes
    this.c = new THREE.Vector3().setFromMatrixPosition(M);
    this.axis = new THREE.Vector3().setFromMatrixColumn(M, 1).normalize();
    this.left = new THREE.Vector3(1, 0, 0).addScaledVector(this.axis, -this.axis.x).normalize();
    this.down = new THREE.Vector3().crossVectors(this.axis, this.left);   // +angle turns left -> down
    const pts = [];   // (radius, angle, axial offset) of every steering-wheel vertex
    let rMax = 0;
    sw.traverse((o) => {
      if (!o.isMesh) return;
      const Mm = inv.clone().multiply(o.matrixWorld);
      const p = o.geometry.attributes.position;
      for (let i = 0; i < p.count; i++) {
        _a.fromBufferAttribute(p, i).applyMatrix4(Mm).sub(this.c);
        const ax = _a.dot(this.axis);
        _a.addScaledVector(this.axis, -ax);
        const r = _a.length();
        rMax = Math.max(rMax, r);
        pts.push(r, Math.atan2(_a.dot(this.down), _a.dot(this.left)), ax);
      }
    });
    // rim tube radius from the rim's thickness along the column, centre-line radius inside the outer edge
    let axMin = Infinity, axMax = -Infinity;
    for (let i = 0; i < pts.length; i += 3) if (pts[i] > rMax * 0.9) { axMin = Math.min(axMin, pts[i + 2]); axMax = Math.max(axMax, pts[i + 2]); }
    this.tube = THREE.MathUtils.clamp((axMax - axMin) / 2, 0.008, 0.025);
    this.r = THREE.MathUtils.clamp(rMax - this.tube, 0.11, 0.24);
    // spokes: angular intervals occupied just inside the rim (2 deg bins, small gaps closed)
    const NB = 180, bins = new Array(NB).fill(0);
    for (let i = 0; i < pts.length; i += 3) {
      if (pts[i] < this.r * 0.8 || pts[i] > this.r - this.tube * 1.3) continue;
      bins[Math.floor((pts[i + 1] + Math.PI) / (2 * Math.PI) * NB) % NB]++;
    }
    let occ = bins.map(n => n >= 2);
    for (let pass = 0; pass < 2; pass++) occ = occ.map((v, i) => v || (occ[(i + NB - 1) % NB] && occ[(i + 1) % NB]) || (occ[(i + NB - 1) % NB] && occ[(i + 2) % NB]));
    this.spokes = [];
    if (occ.some(v => !v) && occ.some(v => v)) {
      const s0 = occ.findIndex(v => !v);
      let start = -1;
      for (let k = 1; k <= NB; k++) {
        const i = (s0 + k) % NB;
        if (occ[i] && !occ[(i + NB - 1) % NB]) start = i;
        if (occ[i] && !occ[(i + 1) % NB] && start >= 0) {
          const n = (i - start + NB) % NB + 1;
          const half = n * Math.PI / NB;
          this.spokes.push({ mid: wrap(-Math.PI + (start * 2 * Math.PI / NB) + half), half });
        }
      }
    }
    this.ext = [[-0.04, 0.04], [-0.04, 0.04]];   // glove extent along the rim (m), from the asset
    this.setGrip(GRIP, ROLL);
    this.hands = null;
    const e = model.eye;
    this.shoulders = [new THREE.Vector3(e.x + SHOULDER.x, e.y + SHOULDER.y, e.z + SHOULDER.z), new THREE.Vector3(e.x - SHOULDER.x, e.y + SHOULDER.y, e.z + SHOULDER.z)];
    this.group = new THREE.Group();
    this.group.visible = false;
    this.group.layers.set(LAYER_ARMS);
    body.add(this.group);
    this._buildProcedural();
    this.ready = false;
    this.ready = loadArmsAsset().then((gltf) => { if (gltf && this.group.parent) { try { this._useAsset(gltf); } catch (err) { console.warn('driver arms:', err); } } });
  }

  setVisible(v) {
    if (v && !this.group.visible) this.hands = null;   // back in the cockpit: hands start at home
    this.group.visible = v;
  }

  dir(theta, out) { return out.copy(this.left).multiplyScalar(Math.cos(theta)).addScaledVector(this.down, Math.sin(theta)); }

  // hands: home angle and comfort zone on the rim (rim angle 0 = left, +angle = down); for the left hand +angle pulls
  // down, for the right hand it pushes up. grip: the home grip point's height above horizontal (rad); roll: the gloves'
  // roll about the rim tangent toward the driver (rad). The spoke nearest each home (the 9 / 3 spokes) is that hand's
  // seat: at its rest spot on the wheel the glove may lie on it (thumb / pinky edge on the spoke's sleeve)
  setGrip(grip, roll = this.roll ?? ROLL) {
    this.grip = grip; this.roll = roll;
    this.home = [-grip, Math.PI + grip];
    this.zone = [[-grip - PUSH, -grip + PULL], [Math.PI + grip - PULL, Math.PI + grip + PUSH]];
    for (const sp of this.spokes) sp.seat = -1;
    for (const si of [0, 1]) {
      let best = null;
      for (const sp of this.spokes) if (!best || Math.abs(wrap(this.home[si] - sp.mid)) < Math.abs(wrap(this.home[si] - best.mid))) best = sp;
      if (best && Math.abs(wrap(this.home[si] - best.mid)) < 0.6) best.seat = si;
    }
    this.hands = null;
  }

  // ---------------------------------------------------------------- skinned asset
  _useAsset(gltf) {
    const root = cloneSkinned(gltf.scene);
    root.updateMatrixWorld(true);
    const meshes = [];   // one SkinnedMesh per material (glTF primitive), all on the same skeleton
    root.traverse((o) => { if (o.isSkinnedMesh) meshes.push(o); });
    const get = (n) => root.getObjectByName(n) || root.getObjectByName(n.replace('.', ''));
    if (!meshes.length) throw new Error('no skinned mesh in arms.glb');
    const mesh = meshes[0];
    const sides = ['L', 'R'].map((s, si) => {
      const up = get('UpperArm.' + s), fo = get('ForeArm.' + s), ha = get('Hand.' + s), gr = get('Grip.' + s);
      if (!up || !fo || !ha || !gr) throw new Error('arms.glb is missing bones');
      const W = (o) => o.matrixWorld.clone();
      const rU = W(up), rF = W(fo), rH = W(ha), rG = W(gr);
      const S0 = new THREE.Vector3().setFromMatrixPosition(rU), E0 = new THREE.Vector3().setFromMatrixPosition(rF), W0 = new THREE.Vector3().setFromMatrixPosition(rH);
      const n0 = new THREE.Vector3().crossVectors(_a.subVectors(E0, S0), _b.subVectors(W0, E0)).normalize();
      const local = (m, v, isDir) => { const r = v.clone(); const mi = m.clone().invert(); return isDir ? r.transformDirection(mi) : r.applyMatrix4(mi); };
      const bone = (node, rest, head, tail) => {
        const d = local(rest, tail, false).normalize();
        const s = new THREE.Vector3(); rest.decompose(new THREE.Vector3(), new THREE.Quaternion(), s);
        return { node, d, n: local(rest, n0, true).addScaledVector(d, -local(rest, n0, true).dot(d)).normalize(), len: head.distanceTo(tail), scale: s, stretchY: Math.abs(d.y) > 0.98 };
      };
      const ext = gr.userData || {};
      return {
        up: bone(up, rU, S0, E0), fo: bone(fo, rF, E0, W0),
        hand: { node: ha, gripInv: rH.clone().invert().multiply(rG).invert(), nLocal: local(rH, n0, true), restScale: new THREE.Vector3().setFromMatrixScale(rH) },
        xmin: ext.grip_x_min ?? -0.07, xmax: ext.grip_x_max ?? 0.07,
        morph: mesh.morphTargetDictionary ? mesh.morphTargetDictionary['Open' + s] : undefined,
        si,
      };
    });
    // the bones are driven directly in the body frame: re-parent them under the arms group
    for (const s of sides) for (const b of [s.up.node, s.fo.node, s.hand.node]) this.group.add(b);
    for (const sm of meshes) {
      sm.frustumCulled = false;
      sm.castShadow = false; sm.receiveShadow = true;
      const g = sm.geometry;
      if (!g.attributes.bakedAO) g.setAttribute('bakedAO', new THREE.BufferAttribute(new Float32Array(g.attributes.position.count).fill(1), 1));
      for (const m of (Array.isArray(sm.material) ? sm.material : [sm.material])) {
        m.envMapIntensity = 0.45;
        // (r6) trilinear + anisotropic filtering on the suit / glove maps (the sleeves seen at a grazing angle aliased)
        for (const t of [m.map, m.normalMap]) if (t) { t.anisotropy = 8; t.generateMipmaps = true; t.minFilter = THREE.LinearMipmapLinearFilter; }
        // black fabric and leather: keep the blue sky light from tinting them navy
        patchMaterial(m, ARMS_LOOK);
      }
      this.group.add(sm);
    }
    this._useLegs(root);
    this.meshes = meshes;
    this.sides = sides;
    this.group.traverse(o => o.layers.set(LAYER_ARMS));
    for (const s of sides) this.ext[s.si] = [s.xmin, s.xmax];
    this.hands = null;
    for (const o of this.proc) this.group.remove(o);
    this.ready = true;
    this.update(this._lastAngle || 0, 0);
  }

  // static legs of the asset: posed for one cockpit, so only where this car's eye matches the asset's
  _useLegs(root) {
    const legs = root.getObjectByName('DriverLegs');
    const e = legs?.userData?.eye;   // Blender axes (x right, y forward, z up)
    if (!legs || !Array.isArray(e)) return;
    const assetEye = new THREE.Vector3(-e[0], e[2], e[1]);   // body frame
    if (assetEye.distanceTo(this.model.eye) > 0.03) return;
    legs.removeFromParent();
    // asset (glTF: +X right, -Z forward) -> body frame (+X left, +Z forward): half a turn about Y
    legs.position.set(0, 0, 0).add(this.model.eye).sub(assetEye);
    legs.quaternion.setFromAxisAngle(UP, Math.PI);
    legs.scale.set(1, 1, 1);
    const own = new Map();
    legs.traverse((o) => {
      if (!o.isMesh) return;
      o.castShadow = false; o.receiveShadow = true;
      const g = o.geometry;
      if (!g.attributes.bakedAO) g.setAttribute('bakedAO', new THREE.BufferAttribute(new Float32Array(g.attributes.position.count).fill(1), 1));
      const swap = (m) => {
        if (!own.has(m)) { const c = m.clone(); c.userData = { ...m.userData, lookPatched: false }; c.envMapIntensity = 0.45; for (const t of [c.map, c.normalMap]) if (t) t.anisotropy = 8; patchMaterial(c, LEGS_LOOK); own.set(m, c); }
        return own.get(m);
      };
      o.material = Array.isArray(o.material) ? o.material.map(swap) : swap(o.material);
    });
    this.group.add(legs);
    this.legs = legs;
  }

  // ---------------------------------------------------------------- where the hands hold the rim
  // glove centre offset and half width along the rim (rad) of hand si; the glove's local X
  // (= R x A) runs toward decreasing rim angle
  _span(si) {
    const [x0, x1] = this.ext[si];
    return { c: -(x0 + x1) / (2 * this.r), h: (x1 - x0) / (2 * this.r) };
  }

  // can hand si hold the rim at world angle w (wheel turned by a) without touching a spoke or the
  // other glove (centre at world angle otherW)?
  _free(si, w, a, otherW) {
    const { c, h } = this._span(si);
    const gc = w + c;
    const seated = Math.abs(wrap(w - a - this.home[si])) < 0.06;   // the rest spot on the wheel, by its seat spoke
    for (const sp of this.spokes) if (!(seated && sp.seat === si) && Math.abs(wrap(gc - sp.mid - a)) < h + sp.half + CLEAR) return false;
    if (otherW !== undefined) {
      const o = this._span(1 - si);
      if (Math.abs(wrap(gc - otherW - o.c)) < h + o.h + 0.02) return false;
    }
    return true;
  }

  // the free spot nearest the home of hand si, inside its comfort zone (kept off its ends)
  _spot(si, a, otherW) {
    const [lo, hi] = this.zone[si], home = this.home[si];
    for (let k = 0; k < 160; k++) {
      const w = home + (k >> 1) * 0.02 * (k & 1 ? -1 : 1);
      if (w < lo + 0.12 || w > hi - 0.12) continue;
      if (this._free(si, w, a, otherW)) return w;
    }
    return home;
  }

  // shuffle steering: advance the hands' state by dt seconds at wheel angle a
  _plan(a, dt) {
    if (!this.hands) {
      this.hands = [0, 1].map(si => ({ si, g: 0, w: 0, lift: 0, open: 0, hop: null }));
      const w0 = this._spot(0, a);
      this.hands[0].g = w0 - a;
      this.hands[1].g = this._spot(1, a, w0) - a;
      this.straightT = 0;
      dt = 0;
    }
    this.straightT = Math.abs(a) < 0.15 ? this.straightT + dt : 0;
    for (const h of this.hands) {
      const o = this.hands[1 - h.si];
      const oW = o.hop ? o.hop.wt : o.g + a;
      if (!h.hop) {
        const w = h.g + a, [lo, hi] = this.zone[h.si];
        const over = Math.max(lo - w, w - hi);
        // wheel back near straight for a moment: return to ten and two
        const away = this.straightT > 0.35 && Math.abs(w - this._spot(h.si, a, oW)) > 0.2;
        if ((over > 0 && (!o.hop || over > 0.35)) || (away && !o.hop)) h.hop = { w0: w, wt: w, t: 0 };
      }
      let clash = false;
      if (h.hop) {
        const hp = h.hop;
        hp.t = Math.min(1, hp.t + dt / HOP_T);
        hp.wt = this._spot(h.si, a, oW);
        h.w = hp.w0 + (hp.wt - hp.w0) * smooth(0, 1, hp.t);
        clash = !this._free(h.si, h.w, a);          // over a spoke right now: lift off a little
        h.open = Math.max(LOOSE * Math.sin(Math.PI * hp.t), h.lift);
        if (hp.t >= 1) { h.g = hp.wt - a; h.hop = null; }
      } else {
        h.w = h.g + a;
        h.open = h.lift;
      }
      h.lift += ((clash ? 1 : 0) - h.lift) * (dt > 0 ? Math.min(1, dt * 30) : 1);
    }
  }

  // grip frame of hand h this frame: radial direction R, rim point P (body frame), open amount
  _gripPose(h) {
    const R = this.dir(h.w, new THREE.Vector3());
    const P = this.c.clone().addScaledVector(R, this.r + LIFT_R * h.lift).addScaledVector(this.axis, LIFT_A * h.lift);
    return { R, P, open: Math.min(1, Math.max(h.open || 0, 1.2 * h.lift)) };
  }

  update(wheelAngle, dt) {
    const now = performance.now() / 1000;
    if (dt === undefined) dt = this._clock === undefined ? 0 : now - this._clock;
    this._clock = now;
    this._lastAngle = wheelAngle;
    if (!this.group.visible) return;
    this._plan(wheelAngle, THREE.MathUtils.clamp(dt, 0, 0.1));
    if (!this.ready) { this._updateProcedural(); return; }
    const A0 = this.axis, cr = Math.cos(this.roll), sr = Math.sin(this.roll);
    for (const s of this.sides) {
      const { R: R0, P, open } = this._gripPose(this.hands[s.si]);
      // glove: grip frame on the rim (local X = R x A, Y = A, Z = -R, as exported), rolled about the rim tangent X
      // (R toward A: knuckles toward the driver; the curl round the rim tube is unchanged)
      const R = R0.clone().multiplyScalar(cr).addScaledVector(A0, sr);
      const A = A0.clone().multiplyScalar(cr).addScaledVector(R0, -sr);
      const X = _c.crossVectors(R, A).normalize();
      const Z = _d.copy(R).negate();
      const G = new THREE.Matrix4().makeBasis(X, A, Z).setPosition(P);
      const H = G.multiply(s.hand.gripInv);
      const hn = s.hand.node;
      H.decompose(hn.position, hn.quaternion, _s);
      hn.scale.copy(s.hand.restScale);
      if (s.morph !== undefined) for (const sm of this.meshes) if (sm.morphTargetInfluences) sm.morphTargetInfluences[s.morph] = open;
      // two-bone IK from the shoulder to the wrist, elbows down and out
      const S = this.shoulders[s.si];
      const Wr = hn.position;
      const toW = new THREE.Vector3().subVectors(Wr, S);
      let d = toW.length(); toW.divideScalar(d);
      let L1 = s.up.len, L2 = s.fo.len;
      const k = Math.max(1, d / (0.985 * (L1 + L2)));  // out of reach (other cars): stretch the sleeves a little
      L1 *= k; L2 *= k;
      const a = (L1 * L1 - L2 * L2 + d * d) / (2 * d);
      const h = Math.sqrt(Math.max(0, L1 * L1 - a * a));
      const pole = new THREE.Vector3(s.si ? -0.8 : 0.8, -1, 0);
      pole.addScaledVector(toW, -pole.dot(toW)).normalize();
      const E = S.clone().addScaledVector(toW, a).addScaledVector(pole, h);
      const n = new THREE.Vector3().crossVectors(_a.subVectors(E, S), _b.subVectors(Wr, E)).normalize();
      // upper arm: hinge axis as at rest
      const dU = new THREE.Vector3().subVectors(E, S).normalize();
      const dF = new THREE.Vector3().subVectors(Wr, E).normalize();
      this._aim(s.up, S, dU, n, k);
      // forearm: split the twist between elbow and wrist (hinge axis blended with the hand's)
      const nh = s.hand.nLocal.clone().applyQuaternion(hn.quaternion);
      nh.addScaledVector(dF, -nh.dot(dF)).normalize();
      const nF = nh.dot(n) > -0.3 ? n.clone().add(nh).normalize() : n.clone();
      nF.addScaledVector(dF, -nF.dot(dF)).normalize();
      this._aim(s.fo, E, dF, nF, k);
    }
  }

  // place bone b with its head at p, its length axis along dir and its hinge axis along n
  _aim(b, p, dir, n, stretch) {
    const node = b.node;
    basisQuat(b.d, b.n, dir, n, node.quaternion);
    node.position.copy(p);
    node.scale.copy(b.scale);
    if (b.stretchY && stretch > 1) node.scale.y *= stretch;
  }

  // ---------------------------------------------------------------- simple fallback arms
  _buildProcedural() {
    const sw0 = this.c.clone().addScaledVector(this.dir(-0.5, _a), this.r);
    const reach = this.shoulders[0].distanceTo(sw0);
    this.L1 = reach * 0.56; this.L2 = reach * 0.53;
    const suit = new THREE.MeshStandardMaterial({ color: 0x1c1d20, roughness: 0.92, metalness: 0, envMapIntensity: 0.45 });
    const stripe = new THREE.MeshStandardMaterial({ color: 0xff5a0d, roughness: 0.8, envMapIntensity: 0.45 });
    const glove = new THREE.MeshStandardMaterial({ color: 0x111113, roughness: 0.7, metalness: 0.05, envMapIntensity: 0.45 });
    const cuff = new THREE.MeshStandardMaterial({ color: 0x3a3d42, roughness: 0.75, envMapIntensity: 0.45 });
    this.proc = [];
    const add = (m) => { this.group.add(m); this.proc.push(m); return m; };
    const cyl = (r0, r1, mat) => add(new THREE.Mesh(new THREE.CylinderGeometry(r1, r0, 1, 14, 1, true), mat));
    const ball = (r, mat) => add(new THREE.Mesh(new THREE.SphereGeometry(r, 14, 10), mat));
    this.arms = [0, 1].map(() => {
      const upper = cyl(0.054, 0.045, suit), fore = cyl(0.044, 0.036, suit);
      const shoulder = ball(0.058, suit), elbow = ball(0.048, suit);
      const band = add(new THREE.Mesh(new THREE.CylinderGeometry(0.043, 0.043, 0.012, 14), stripe));
      const hand = new THREE.Group();
      const palm = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 12), glove); palm.scale.set(0.048, 0.052, 0.066); hand.add(palm);
      const fingers = new THREE.Mesh(new THREE.TorusGeometry(0.03, 0.022, 8, 14, Math.PI * 1.25), glove);
      fingers.rotation.set(0, Math.PI / 2, -Math.PI * 0.6); fingers.position.set(0, -0.005, 0.01); hand.add(fingers);
      const thumb = new THREE.Mesh(new THREE.CapsuleGeometry(0.016, 0.04, 4, 8), glove);
      thumb.position.set(0, 0.035, -0.02); thumb.rotation.x = 1.1; hand.add(thumb);
      const c2 = new THREE.Mesh(new THREE.CylinderGeometry(0.048, 0.05, 0.05, 14), cuff); c2.position.z = -0.075; c2.rotation.x = Math.PI / 2; hand.add(c2);
      add(hand);
      return { upper, fore, band, hand, shoulder, elbow };
    });
    for (const o of this.proc) o.traverse(m => { m.castShadow = false; m.receiveShadow = true; m.layers.set(LAYER_ARMS); });
  }

  _updateProcedural() {
    for (let s = 0; s < 2; s++) {
      const arm = this.arms[s];
      const { P: H, R: dir } = this._gripPose(this.hands[s]);
      const S = this.shoulders[s];
      const toH = _c.copy(H).sub(S); let d = toH.length(); toH.divideScalar(d);
      d = Math.min(d, this.L1 + this.L2 - 1e-3);
      const a = (this.L1 * this.L1 - this.L2 * this.L2 + d * d) / (2 * d);
      const h = Math.sqrt(Math.max(0, this.L1 * this.L1 - a * a));
      const pole = _d.set(s ? -0.8 : 0.8, -1, 0); pole.addScaledVector(toH, -pole.dot(toH)).normalize();
      const E = S.clone().addScaledVector(toH, a).addScaledVector(pole, h);
      const Hn = S.clone().addScaledVector(toH, d);
      arm.shoulder.position.copy(S); arm.elbow.position.copy(E);
      this._bone(arm.upper, S, E);
      this._bone(arm.fore, E, Hn);
      arm.band.position.copy(E).lerp(Hn, 0.82);
      arm.band.quaternion.copy(arm.fore.quaternion);
      arm.hand.position.copy(Hn);
      const fwd = _c.copy(Hn).sub(E).normalize();
      arm.hand.quaternion.setFromRotationMatrix(new THREE.Matrix4().lookAt(new THREE.Vector3(), fwd.negate(), dir));
    }
  }

  _bone(mesh, A, B) {
    const len = A.distanceTo(B);
    mesh.position.copy(A).lerp(B, 0.5);
    mesh.scale.set(1, Math.max(0.01, len), 1);
    mesh.quaternion.setFromUnitVectors(UP, _d.copy(B).sub(A).normalize());
  }
}
