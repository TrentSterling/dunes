// Sand deformation: tire ruts, paddle imprints, berms and churned sand.
// Stored in a toroidal (wrap-around) GPU texture that follows the camera, so
// tracks have centimeter detail without needing a texture for the whole map.
// Channels: R = rut depth (m), G = pushed-up berm height (m), B = churn (0..1).
import * as THREE from 'three';

// One instanced draw stamps many tire segments. Each segment is drawn 4 times
// (the window wraps around), and pixels outside the current window are thrown
// away so a segment never smears onto the opposite edge.
const STAMP_VS = /* glsl */`
attribute vec4 aSeg;   // x0 z0 x1 z1
attribute vec4 aP1;    // halfW bermW depth berm
attribute vec4 aP2;    // d0 d1 paddle slip
attribute vec2 aP3;    // type churn
uniform float uW; uniform vec4 uWin;
varying vec2 vAB; varying vec2 vWorld;
varying float vLen, vExt, vHalfW, vBermW, vDepth, vBerm, vD0, vD1, vPaddle, vSlip, vType, vChurn;
void main(){
  vec2 o = aSeg.xy, e = aSeg.zw - aSeg.xy;
  float len = length(e);
  vec2 ax = len > 1e-4 ? e/len : vec2(1.0, 0.0);
  vec2 bx = vec2(-ax.y, ax.x);
  float ext = aP3.x > 0.5 ? 0.14 : 0.18;
  float bw = aP1.x*1.05 + aP1.y*1.3;
  float a = mix(-ext, len + ext, position.x);
  float b = mix(-bw, bw, position.y);
  vAB = vec2(a, b);
  vec2 world = o + ax*a + bx*b;
  vWorld = world;
  vec2 shift = floor(uWin.xy / uW);
  int cp = gl_InstanceID & 3;
  vec2 off = vec2(float(cp & 1), float(cp >> 1));
  vec2 uv = world/uW - shift - off;
  gl_Position = vec4(uv*2.0-1.0, 0.0, 1.0);
  vLen = len; vExt = ext; vHalfW = aP1.x; vBermW = aP1.y; vDepth = aP1.z; vBerm = aP1.w;
  vD0 = aP2.x; vD1 = aP2.y; vPaddle = aP2.z; vSlip = aP2.w; vType = aP3.x; vChurn = aP3.y;
}`;

const STAMP_FS = /* glsl */`
uniform vec4 uWin; uniform float uSpacing; uniform float uDetail;
varying vec2 vAB; varying vec2 vWorld;
varying float vLen, vExt, vHalfW, vBermW, vDepth, vBerm, vD0, vD1, vPaddle, vSlip, vType, vChurn;
void main(){
  if (any(lessThan(vWorld, uWin.xy)) || any(greaterThanEqual(vWorld, uWin.zw))) discard;
  float a = vAB.x, b = vAB.y;
  float t = abs(b)/vHalfW;
  // rounded contact-patch end caps
  float e = max(max(-a, a - vLen), 0.0)/vExt;
  if (e >= 1.0) discard;
  float cap = 0.5 + 0.5*cos(3.14159*e);
  float depth = 0.0, berm = 0.0;
  float d = mix(vD0, vD1, clamp(a/max(vLen,1e-4), 0.0, 1.0)) + min(a,0.0) + max(a-vLen,0.0);
  // rounded cross-section: the floor curves up into the wall, and the wall rolls over
  // into a soft rounded berm instead of a sharp lip
  float prof = 0.5 + 0.5*cos(3.14159*clamp((t - 0.5)/0.55, 0.0, 1.0));
  float u = (abs(b) - 0.8*vHalfW)/(vBermW*1.3 + 0.25*vHalfW);
  if (u > 0.0 && u < 1.0) { float sb = sin(3.14159*u); berm = vBerm*1.1*sb*sb*(1.0 - 0.3*u); }
  if (t < 1.05) {
    depth = vDepth*prof;
    if (vType < 0.5) {
      // paddle tire: transverse trenches where paddles struck, smeared by wheelspin
      float ph = fract(d/uSpacing);
      float pad = pow(0.5 + 0.5*cos(6.2831853*ph), 5.0);
      depth += vPaddle*prof*mix(mix(pad, 0.55, clamp(vSlip, 0.0, 1.0)), 0.45, 1.0 - uDetail);
    } else {
      // ribbed front tire: 3 ribs press grooves, 2 tire grooves leave ridges
      float x = b/vHalfW;
      float ridge = exp(-pow((abs(x) - 0.36)/0.07, 2.0));
      depth -= vPaddle*ridge*prof*uDetail;
    }
  }
  depth = max(depth, 0.0) * cap;
  berm *= cap;
  float churn = vChurn * (t < 1.0 ? 1.0 : (1.0 - smoothstep(0.0, 1.0, (abs(b)-vHalfW)/vBermW)) * 0.8) * cap;
  // impressions pressed half as deep (and berms half as high) as the tire record says
  gl_FragColor = vec4(depth*0.5, berm*0.5, churn, 1.0);
}`;

const CLEAR_VS = /* glsl */`
uniform vec2 uOrigin; uniform vec4 uRange; uniform float uW; uniform vec4 uWin;
void main(){
  vec2 world = uOrigin + vec2(mix(uRange.x, uRange.y, position.x), mix(uRange.z, uRange.w, position.y));
  vec2 shift = floor(uWin.xy / uW);
  vec2 off = vec2(float(gl_InstanceID & 1), float(gl_InstanceID >> 1));
  vec2 uv = world/uW - shift - off;
  gl_Position = vec4(uv*2.0-1.0, 0.0, 1.0);
}`;
const CLEAR_FS = /* glsl */`void main(){ gl_FragColor = vec4(0.0); }`;

const CAP = 4096; // segments per draw

export class SandDeformer {
  constructor(renderer, opts) {
    this.renderer = renderer;
    this.res = opts.res;
    this.texel = opts.texel;
    this.W = this.res * this.texel;
    this.rt = new THREE.WebGLRenderTarget(this.res, this.res, {
      type: THREE.HalfFloatType, format: THREE.RGBAFormat, depthBuffer: false,
      minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, generateMipmaps: false,
      wrapS: THREE.RepeatWrapping, wrapT: THREE.RepeatWrapping,
    });
    this.rt.texture.wrapS = this.rt.texture.wrapT = THREE.RepeatWrapping;
    this.center = null;
    this.win = new THREE.Vector4();
    this.scene = new THREE.Scene();
    this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const quadPos = new THREE.BufferAttribute(new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0, 1, 1, 0]), 3);

    // instanced segment stamps
    const g = new THREE.InstancedBufferGeometry();
    g.setAttribute('position', quadPos);
    g.setIndex([0, 1, 2, 2, 1, 3]);
    this.aSeg = new THREE.InstancedBufferAttribute(new Float32Array(CAP * 4), 4, false, 4);
    this.aP1 = new THREE.InstancedBufferAttribute(new Float32Array(CAP * 4), 4, false, 4);
    this.aP2 = new THREE.InstancedBufferAttribute(new Float32Array(CAP * 4), 4, false, 4);
    this.aP3 = new THREE.InstancedBufferAttribute(new Float32Array(CAP * 2), 2, false, 4);
    for (const [n, a] of [['aSeg', this.aSeg], ['aP1', this.aP1], ['aP2', this.aP2], ['aP3', this.aP3]]) { a.setUsage(THREE.DynamicDrawUsage); g.setAttribute(n, a); }
    g.instanceCount = 0;
    this.segGeo = g;
    this.uWin = { value: this.win };
    const segMat = new THREE.ShaderMaterial({
      uniforms: { uW: { value: this.W }, uWin: this.uWin, uSpacing: { value: 2 * Math.PI * 0.41 / 18 }, uDetail: { value: opts.coarse ? 0 : 1 } },
      vertexShader: STAMP_VS, fragmentShader: STAMP_FS,
      blending: THREE.CustomBlending, blendEquation: THREE.MaxEquation, blendEquationAlpha: THREE.MaxEquation,
      blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor,
      depthTest: false, depthWrite: false, side: THREE.DoubleSide,
    });
    this.segMesh = new THREE.Mesh(g, segMat);
    this.segMesh.frustumCulled = false;
    this.scene.add(this.segMesh);
    this.n = 0;

    const cq = new THREE.InstancedBufferGeometry();
    cq.setAttribute('position', quadPos);
    cq.setIndex([0, 1, 2, 2, 1, 3]);
    cq.instanceCount = 4;
    this.clearPool = [];
    for (let i = 0; i < 4; i++) {
      const mat = new THREE.ShaderMaterial({
        uniforms: { uOrigin: { value: new THREE.Vector2() }, uRange: { value: new THREE.Vector4() }, uW: { value: this.W }, uWin: this.uWin },
        vertexShader: CLEAR_VS, fragmentShader: CLEAR_FS,
        blending: THREE.NoBlending, depthTest: false, depthWrite: false, side: THREE.DoubleSide,
      });
      const m = new THREE.Mesh(cq, mat);
      m.frustumCulled = false; m.visible = false;
      this.scene.add(m);
      this.clearPool.push(m);
    }
    this.clears = [];
    this.replays = [];   // world rectangles to redraw from the track log after clearing
    this.log = null;     // TrackLog
  }

  get texture() { return this.rt.texture; }

  _setWin() { const h = this.W / 2; this.win.set(this.center.x - h, this.center.y - h, this.center.x + h, this.center.y + h); }

  // Keep the window centred on the camera; wipe strips that newly enter it
  // and redraw any stored tracks there.
  follow(x, z) {
    const snap = this.texel * 32;
    const cx = Math.round(x / snap) * snap, cz = Math.round(z / snap) * snap;
    if (!this.center) {
      this.center = new THREE.Vector2(cx, cz);
      this._setWin();
      this._clearAll = true;
      return;
    }
    const c0 = this.center, h = this.W / 2;
    if (cx === c0.x && cz === c0.y) return;
    if (Math.abs(cx - c0.x) >= this.W || Math.abs(cz - c0.y) >= this.W) {
      this._clearAll = true;
    } else {
      if (cx > c0.x) this.clears.push([c0.x + h, cx + h, cz - h, cz + h]);
      if (cx < c0.x) this.clears.push([cx - h, c0.x - h, cz - h, cz + h]);
      if (cz > c0.y) this.clears.push([cx - h, cx + h, c0.y + h, cz + h]);
      if (cz < c0.y) this.clears.push([cx - h, cx + h, cz - h, c0.y - h]);
    }
    c0.set(cx, cz);
    this._setWin();
  }

  inWindow(x, z, margin = 2) {
    if (!this.center) return false;
    const h = this.W / 2 * 0.97 - margin;
    return Math.abs(x - this.center.x) < h && Math.abs(z - this.center.y) < h;
  }
  overlaps(x0, z0, x1, z1) { return this.center && x1 > this.win.x && x0 < this.win.z && z1 > this.win.y && z0 < this.win.w; }

  // one segment in track-log record layout (array-like, offset o)
  stamp(r, o = 0) {
    if (this.n >= CAP) this._drawSegs();
    const i = this.n++;
    this.aSeg.array.set([r[o], r[o + 1], r[o + 2], r[o + 3]], i * 4);
    this.aP1.array.set([r[o + 4], r[o + 5], r[o + 6], r[o + 7]], i * 4);
    this.aP2.array.set([r[o + 8], r[o + 9], r[o + 10], r[o + 11]], i * 4);
    this.aP3.array[i * 2] = r[o + 12]; this.aP3.array[i * 2 + 1] = r[o + 13];
  }

  // redraw stored tracks inside a world rectangle (e.g. a tile that just loaded)
  replay(x0, z0, x1, z1) { if (this.overlaps(x0, z0, x1, z1)) this.replays.push([x0, z0, x1, z1]); }

  _drawSegs() {
    if (!this.n) return;
    for (const a of [this.aSeg, this.aP1, this.aP2, this.aP3]) { a.needsUpdate = true; a.clearUpdateRanges(); a.addUpdateRange(0, this.n * a.itemSize); }
    this.segGeo.instanceCount = this.n * 4;
    for (const m of this.clearPool) m.visible = false;
    this.segMesh.visible = true;
    this.renderer.render(this.scene, this.camera);
    this.n = 0;
  }

  flush() {
    const r = this.renderer;
    const prevTarget = r.getRenderTarget();
    const prevAuto = r.autoClear;
    r.autoClear = false;
    r.setRenderTarget(this.rt);
    const pendingN = this.n; this.n = 0; // live stamps wait until clears are done
    if (this._clearAll) {
      r.setClearColor(0x000000, 0); r.clear(true, false, false); this._clearAll = false;
      this.clears.length = 0;
      this.replays.push([this.win.x, this.win.y, this.win.z, this.win.w]);
    }
    if (this.clears.length) {
      this.segMesh.visible = false;
      for (let i = 0; i < this.clears.length && i < this.clearPool.length; i++) {
        const [x0, x1, z0, z1] = this.clears[i];
        const u = this.clearPool[i].material.uniforms;
        u.uOrigin.value.set(x0, z0);
        u.uRange.value.set(0, x1 - x0 + this.texel, 0, z1 - z0 + this.texel);
        this.clearPool[i].visible = true;
        this.replays.push([x0 - 0.5, z0 - 0.5, x1 + this.texel + 0.5, z1 + this.texel + 0.5]);
      }
      r.render(this.scene, this.camera);
      for (const m of this.clearPool) m.visible = false;
      this.clears.length = 0;
    }
    this.n = pendingN;
    if (this.replays.length && this.log) {
      for (const [x0, z0, x1, z1] of this.replays) this.log.forEachIn(x0, z0, x1, z1, (a, p) => this.stamp(a, p));
      this.replays.length = 0;
    }
    this._drawSegs();
    r.setRenderTarget(prevTarget);
    r.autoClear = prevAuto;
  }
}
