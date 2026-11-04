// Live cockpit details of the player's car, for the cockpit camera:
//  - the rear-view mirrors show the scene behind, rendered from the driver's eye reflected in each glass
//    (one small render target per glass, one glass re-rendered per frame in turn, driver's arms left out).
//    Outside the cockpit camera, or with opts.mirrorsLive false, the baked mirror images are shown;
//  - the race dash ('Interior screen dash') and the DuneNav chart plotter ('Interior screen lowrance')
//    are GPU glyph screens drawn from the car's state (speed, gear, rpm, boost, heading, track, elevation);
//  - the cabin fill lights of the model's look (LOOKS[look].cabin / cabin2, evaluated in the car shaders), and at
//    night the dim map lamp above the wheel that takes the first one's place (LOOKS[look].nightCabin).
// Everything is per instance: the player's car gets its own copies of the materials and geometries it
// changes, so computer cars of the same model keep the static model.
import * as THREE from 'three';
import { CABIN } from './gltf-sandrail.js';
import { GlyphSurface } from './gpu-ui.js';
import { drawDash, drawNavigator } from './cockpit-display.js';

export const LAYER_ARMS = 1;     // driver's arms: main camera only (not in the mirrors)
export const LAYER_MIRROR = 2;   // mirror glass: main camera only (never into its own render target)

const MIRROR_KIND = { 'Mirror baked': 'rear', 'Mirror baked side': 'side', 'Mirror glass': 'auto' };
const _v = new THREE.Vector3(), _v2 = new THREE.Vector3(), _v3 = new THREE.Vector3(), _m = new THREE.Matrix4(), _c = new THREE.Color(), _c2 = new THREE.Color();
// (r6) glass tint of the live mirrors: the sky in them clipped to 243 with 0.80 - side glasses darker than the panoramic one
const MIRROR_TINT = { L: [0.62, 0.67, 0.74], R: [0.62, 0.67, 0.74], C: [0.72, 0.75, 0.80] };
// (r6) side glasses see 12 % more than their outline (convex look); the panoramic one stays flat
const MIRROR_PAD = { L: 0.06, R: 0.06, C: 0.01 };

export class CockpitLive {
  // model: GltfSandrail; opts.getRadar(): the HUD Radar (relief map) for the chart plotter;
  // opts.mirrorsLive: false shows the baked mirror images in the cockpit too (setMirrorsLive changes it)
  constructor(model, opts = {}) {
    this.model = model;
    this.opts = opts;
    this.active = false;
    this.mirrorsLive = opts.mirrorsLive !== false;
    this.frame = 0;
    this.odo = 0;
    this.trail = [];
    this.boost = 0;
    model.root.updateMatrixWorld(true);
    this.mirrors = [];
    this.screens = {};
    try { this._findMirrors(); } catch (e) { console.warn('cockpit mirrors:', e); this.mirrors = []; }
    this._findScreens();
  }

  // ------------------------------------------------------------------ mirrors
  _findMirrors() {
    const root = this.model.model;
    const toModel = new THREE.Matrix4().copy(root.matrixWorld).invert();
    const found = [];
    root.traverse((o) => { if (o.isMesh && !Array.isArray(o.material) && MIRROR_KIND[o.material?.name]) found.push(o); });
    for (const mesh of found) {
      const g0 = mesh.geometry;
      if (!g0.index || !g0.attributes.uv) continue;
      const M = new THREE.Matrix4().multiplyMatrices(toModel, mesh.matrixWorld);
      const pos = g0.attributes.position, n = pos.count;
      const P = [];
      for (let i = 0; i < n; i++) P.push(_v.fromBufferAttribute(pos, i).applyMatrix4(M).clone());
      // pieces: side glasses left / right of the car, the panoramic one in the middle
      const kind = MIRROR_KIND[mesh.material.name];
      const pieceOf = (p) => (kind === 'rear' ? 'C' : (p.x < -0.4 ? 'L' : p.x > 0.4 ? 'R' : (kind === 'side' ? (p.x < 0 ? 'L' : 'R') : 'C')));
      const vp = P.map(pieceOf);
      const idx = g0.index.array;
      const tris = { L: [], C: [], R: [] };
      for (let t = 0; t < idx.length; t += 3) tris[vp[idx[t]]].push(idx[t], idx[t + 1], idx[t + 2]);
      const keys = ['L', 'C', 'R'].filter(k => tris[k].length);
      if (!keys.length) continue;
      // live geometry: own index (pieces contiguous, one group each) and own UVs
      const g = g0.clone();
      const all = [];
      g.clearGroups();
      const pieces = keys.map((k, mi) => {
        const start = all.length;
        all.push(...tris[k]);
        g.addGroup(start, tris[k].length, mi);
        return this._piece(k, tris[k], P);
      });
      g.setIndex(all);
      const live = pieces.map((pc) => {
        const rt = new THREE.WebGLRenderTarget(pc.res[0], pc.res[1], { type: THREE.HalfFloatType, depthBuffer: true, samples: 0 });
        rt.texture.generateMipmaps = false;
        rt.texture.minFilter = THREE.LinearFilter;
        pc.rt = rt;
        pc.cam = new THREE.PerspectiveCamera(30, pc.res[0] / pc.res[1], 0.05, 150000);
        pc.cam.layers.set(0);
        pc.cam.layers.enable(4); // Local rider stays visible in the rear-view mirrors.
        return new THREE.MeshBasicMaterial({ map: rt.texture, color: new THREE.Color(...(MIRROR_TINT[pc.key] || MIRROR_TINT.C)), fog: false });
      });
      mesh.layers.set(LAYER_MIRROR);
      this.mirrors.push({ mesh, g0, mat0: mesh.material, g, live, pieces, uv: g.attributes.uv });
    }
  }

  // a glass: its vertices (model frame), centre, normal toward the driver, render-target size
  _piece(key, tris, P) {
    const verts = [...new Set(tris)];
    const c = new THREE.Vector3();
    for (const i of verts) c.add(P[i]);
    c.divideScalar(verts.length);
    const nrm = new THREE.Vector3(), e1 = new THREE.Vector3(), e2 = new THREE.Vector3();
    for (let t = 0; t < tris.length; t += 3) {
      e1.subVectors(P[tris[t + 1]], P[tris[t]]); e2.subVectors(P[tris[t + 2]], P[tris[t]]);
      nrm.add(e1.cross(e2));
    }
    nrm.normalize();
    // facing the driver (the eye sits behind the mirrors, toward +z in the glTF frame)
    const eye = this.model.eye ? new THREE.Vector3(-this.model.eye.x, this.model.eye.y, -this.model.eye.z) : new THREE.Vector3(0, 1.25, 0.2);
    if (nrm.dot(_v.subVectors(eye, c)) < 0) nrm.negate();
    // glass extent in its plane -> render target aspect
    const up = new THREE.Vector3(0, 1, 0).addScaledVector(nrm, -nrm.y).normalize();
    const right = new THREE.Vector3().crossVectors(up, nrm);
    let w0 = Infinity, w1 = -Infinity, h0 = Infinity, h1 = -Infinity;
    for (const i of verts) { _v.subVectors(P[i], c); w0 = Math.min(w0, _v.dot(right)); w1 = Math.max(w1, _v.dot(right)); h0 = Math.min(h0, _v.dot(up)); h1 = Math.max(h1, _v.dot(up)); }
    const aspect = (w1 - w0) / Math.max(1e-3, h1 - h0);
    // panoramic 512 x 80..128, side mirrors 160 wide x 96..128 (a little anisotropic when the glass is
    // squarer than that: the side glasses only cover ~70 px on screen at 1280 x 720)
    const res = key === 'C' ? [512, THREE.MathUtils.clamp(Math.round(512 / aspect), 80, 128)] : [160, THREE.MathUtils.clamp(Math.round(160 / aspect), 96, 128)];
    return { key, verts, P: verts.map(i => P[i]), c, n: nrm, up, right, res };
  }

  // aim each glass's camera at the eye's reflection and map the glass onto its image
  _updateMirrors(camera) {
    const root = this.model.model;
    root.updateMatrixWorld();
    const inv = _m.copy(root.matrixWorld).invert();
    const E = _v2.setFromMatrixPosition(camera.matrixWorld).applyMatrix4(inv);   // eye, model frame
    const q = new THREE.Quaternion().setFromRotationMatrix(root.matrixWorld);
    for (const mi of this.mirrors) {
      const uv = mi.uv;
      mi.pieces.forEach((pc, k) => {
        const D = _v.subVectors(E, pc.c).dot(pc.n);
        if (D < 0.02) return;                                   // eye behind the glass
        const Er = E.clone().addScaledVector(pc.n, -2 * D);     // reflected eye
        // camera looks along +n (from behind the glass through it), up = the car's up in the glass plane
        const Z = pc.n.clone().negate(), Y = pc.up, X = new THREE.Vector3().crossVectors(Y, Z);
        const basis = new THREE.Matrix4().makeBasis(X, Y, Z);
        // glass corners in camera space -> off-axis frustum through the glass outline
        let l = Infinity, r = -Infinity, b = Infinity, t = -Infinity, zmin = Infinity;
        const tan = pc.P.map((p) => {
          _v.subVectors(p, Er);
          const x = _v.dot(X), y = _v.dot(Y), z = -_v.dot(Z);
          zmin = Math.min(zmin, z);
          const tx = x / z, ty = y / z;
          l = Math.min(l, tx); r = Math.max(r, tx); b = Math.min(b, ty); t = Math.max(t, ty);
          return [tx, ty];
        });
        const pk = MIRROR_PAD[pc.key] ?? 0.01, padX = pk * (r - l), padY = pk === 0.01 ? padX : pk * (t - b);
        l -= padX; r += padX; b -= padY; t += padY;
        const cam = pc.cam;
        cam.position.copy(Er).applyMatrix4(root.matrixWorld);
        cam.quaternion.setFromRotationMatrix(basis).premultiply(q);
        // near plane on the glass: everything between the reflected eye and the mirror is cut away
        cam.near = Math.max(0.01, zmin - 0.004);
        const H = Math.max(Math.abs(t), Math.abs(b)), W = Math.max(Math.abs(l), Math.abs(r));
        cam.fov = 2 * Math.atan(H) * 180 / Math.PI;
        cam.aspect = W / H;
        pc.tanW = W; pc.tanH = H;
        cam.setViewOffset(2 * W, 2 * H, l + W, H - t, r - l, t - b);
        cam.updateMatrixWorld(true);
        pc.ok = true;
        tan.forEach(([tx, ty], j) => uv.setXY(pc.verts[j], (tx - l) / (r - l), (ty - b) / (t - b)));
      });
      uv.needsUpdate = true;
    }
  }

  renderMirrors(renderer, scene, camera) {
    // (wait for a couple of normal frames: the sun shadow map must exist before it is reused here)
    if (!this.active || !this.mirrorsLive || !this.mirrors.length || (this.updates || 0) < 3) return;
    this._updateMirrors(camera);
    const prevRT = renderer.getRenderTarget(), prevShadow = renderer.shadowMap.autoUpdate;
    renderer.shadowMap.autoUpdate = false;    // the sun shadow map of this frame is reused
    const list = this._pieces || (this._pieces = this.mirrors.flatMap(mi => mi.pieces));
    // Keep the same work budget when entering the cockpit as while driving.
    // Startup warms each target before the loading screen disappears.
    const todo = [list[this.frame++ % list.length]];
    // (r6) the terrain draws only the patches selected (and frustum culled) for one camera: selected for the forward
    // cockpit view it left the sand behind the car out, and the side glasses showed only sky (RGB ~240). Select it for
    // each glass's view (LOD still measured from the eye), then again for the main view. The selection frustum is the
    // glass's, but taller (+-35 deg): the patch boxes come from the base height only, and near the car the rendered sand
    // (dune detail, ruts) lies 2-4 m below them, so the glass's thin, level frustum culled every near patch.
    const terrain = this.opts.getTerrain?.();
    const cc = terrain && (this._cullCam || (this._cullCam = new THREE.PerspectiveCamera()));
    let drawn = false;
    for (const pc of todo) {
      if (!pc.ok) continue;
      if (terrain) {
        cc.position.copy(pc.cam.position); cc.quaternion.copy(pc.cam.quaternion);
        cc.near = pc.cam.near; cc.far = pc.cam.far;
        const H = Math.max(pc.tanH, 0.7);
        cc.fov = 2 * Math.atan(H) * 180 / Math.PI; cc.aspect = pc.tanW / H;
        cc.updateProjectionMatrix(); cc.updateMatrixWorld(true);
        terrain.update(cc, camera.position);
      }
      renderer.setRenderTarget(pc.rt);
      renderer.render(scene, pc.cam);
      drawn = true;
    }
    if (terrain && drawn) terrain.update(camera);
    renderer.setRenderTarget(prevRT);
    renderer.shadowMap.autoUpdate = prevShadow;
    this._mirrorsDrawn = true;
  }

  // ------------------------------------------------------------------ screens
  _findScreens() {
    const want = { 'Interior screen dash': [512, 256, 'dash'], 'Interior screen lowrance': [512, 320, 'lowrance'] };
    const made = new Map();
    this.model.model.traverse((o) => {
      if (!o.isMesh || Array.isArray(o.material)) return;
      const w = want[o.material?.name];
      if (!w || !o.material.emissiveMap) return;
      if (!made.has(o.material)) {
        const target=new THREE.WebGLRenderTarget(w[0],w[1],{depthBuffer:false});
        const tex=target.texture;tex.generateMipmaps=false;
        const surface=new GlyphSurface(this.opts.renderer,this.opts.atlas,{target,capacity:5000});
        const t0 = o.material.emissiveMap;
        tex.flipY = t0.flipY; tex.colorSpace = THREE.SRGBColorSpace; tex.channel = t0.channel;
        tex.offset.copy(t0.offset); tex.repeat.copy(t0.repeat); tex.rotation = t0.rotation; tex.center.copy(t0.center);
        tex.wrapS = t0.wrapS; tex.wrapT = t0.wrapT; tex.anisotropy = 8;
        const m = o.material.clone();
        m.userData = { ...o.material.userData };
        if (o.material.onBeforeCompile) { m.onBeforeCompile = o.material.onBeforeCompile; m.customProgramCacheKey = o.material.customProgramCacheKey; }
        m.emissiveMap = tex;
        if (m.map === t0) m.map = null;
        made.set(o.material, m);
        this.screens[w[2]] = { surface,tex,mat:m,mat0:o.material,meshes:[],t:1e9 };
      }
      const s = Object.values(this.screens).find(s => s.mat0 === o.material);
      s.meshes.push(o);
      o.material = made.get(o.material);
    });
  }

  setActive(on) {
    if (on === this.active) return;
    this.active = on;
    this._swapMirrors();
  }

  setMirrorsLive(on) {
    on = on !== false;
    if (on === this.mirrorsLive) return;
    this.mirrorsLive = on;
    this._swapMirrors();
  }

  // live glass in the cockpit view with live mirrors on, the baked glass otherwise
  _swapMirrors() {
    const live = this.active && this.mirrorsLive;
    for (const mi of this.mirrors) {
      mi.mesh.geometry = live ? mi.g : mi.g0;
      mi.mesh.material = live ? mi.live : mi.mat0;
    }
    this._mirrorsDrawn = false;
  }

  // s: { dt, speed (m/s, signed), gear, rpm, throttle, pos (world), fwd (world, unit), tod (h), day (0..1), cockpit }
  update(s) {
    const dt = s.dt || 0;
    this.updates = (this.updates || 0) + 1;
    // cabin fill: full in the cockpit view, softer from outside, fading with the daylight; (r6) below daylight ~.3 it
    // turns into the dim cool night lamp above the wheel (position, colour and range blended, full at daylight <= .1).
    // (r6) the second fill (between the seats, for the rear-facing dash faces) just fades with the daylight
    const cab = this.model.cabin, nc = this.model.nightCabin, c2 = this.model.cabin2;
    const day = THREE.MathUtils.clamp(s.day ?? 1, 0, 1), k = s.cockpit ? 1 : 0.6;
    if (cab) {
      const t = nc ? THREE.MathUtils.smoothstep(day, 0.1, 0.3) : 1;
      this.model.cabinWorld(CABIN.uCabinPos.value);
      _c.set(cab.color).multiplyScalar(cab.intensity * k * day);
      CABIN.uCabinDist.value = cab.distance;
      if (t < 1) {
        this.model.cabinWorld(_v3, nc.local);
        CABIN.uCabinPos.value.lerp(_v3, 1 - t);
        _c.lerp(_c2.set(nc.color).multiplyScalar(nc.intensity * k), 1 - t);
        CABIN.uCabinDist.value = THREE.MathUtils.lerp(nc.distance, cab.distance, t);
      }
      CABIN.uCabinCol.value.copy(_c);
    } else CABIN.uCabinCol.value.setRGB(0, 0, 0);
    if (c2) {
      this.model.cabinWorld(CABIN.uCabinPos2.value, c2.local);
      CABIN.uCabinCol2.value.set(c2.color).multiplyScalar(c2.intensity * k * day);
      CABIN.uCabinDist2.value = c2.distance;
    } else CABIN.uCabinCol2.value.setRGB(0, 0, 0);
    this.odo += Math.abs(s.speed || 0) * dt;
    const thr = s.throttle || 0;
    this.boost += ((thr > 0.2 ? Math.max(0, (s.rpm - 2500) / 4500) * 18 * thr : -2) - this.boost) * Math.min(1, dt * 3);
    if (s.pos) {
      const last = this.trail[this.trail.length - 1];
      if (!last || Math.hypot(s.pos.x - last[0], s.pos.z - last[1]) > 6) { this.trail.push([s.pos.x, s.pos.z]); if (this.trail.length > 300) this.trail.shift(); }
    }
    // screens are only drawn while someone can read them
    if (!s.cockpit) return;
    const d = this.screens.dash, lw = this.screens.lowrance;
    if (d && (d.t += dt) >= 1 / 15) { d.t = 0; drawDash(d.surface,s,this.boost); }
    if (lw && (lw.t += dt) >= 0.2) { lw.t = 0; drawNavigator(lw.surface,s,this.opts.getRadar?.(),this.trail,this.odo); }
  }

  dispose() {
    this.setActive(false);
    for (const mi of this.mirrors) { for (const pc of mi.pieces) pc.rt?.dispose(); mi.g.dispose(); for (const m of mi.live) m.dispose(); }
    for (const s of Object.values(this.screens)) { for (const o of s.meshes) o.material = s.mat0; s.surface.dispose(); s.mat.dispose(); }
    CABIN.uCabinCol.value.setRGB(0, 0, 0);
    CABIN.uCabinCol2.value.setRGB(0, 0, 0);
  }
}
