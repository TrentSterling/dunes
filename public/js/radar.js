// Radar: heading-up minimap with a shaded-relief view of the dunes and a blip
// for every computer-driven sandrail and online player.
import { dune } from './terrain-data.js';
import * as THREE from 'three';

export class Radar {
  constructor(canvas, terrain) {
    this.cv = canvas || document.createElement('canvas');
    canvas=this.cv;canvas.width=canvas.height=384;
    this.ctx = canvas.getContext('2d');
    this.range = 600; // metres from centre to edge
    this.terrain = terrain;
    this.buildRelief();
    this.texture=new THREE.CanvasTexture(canvas);this.texture.colorSpace=THREE.SRGBColorSpace;this.texture.flipY=false;
    this.reliefTexture=new THREE.CanvasTexture(this.relief);this.reliefTexture.colorSpace=THREE.SRGBColorSpace;this.reliefTexture.flipY=false;
  }

  buildRelief() {
    const T = this.terrain, N = 2048, src = T.fineN, step = src / N;
    const c = document.createElement('canvas'); c.width = c.height = N;
    const g = c.getContext('2d'), img = g.createImageData(N, N), d = img.data;
    const H = T.fine, cell = T.fineCell * step;
    // DEM plus the procedural dunes, one height per radar pixel
    const G = new Float32Array(N * N), half = T.fineSize / 2;
    for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
      G[j * N + i] = H[Math.min(src - 1, Math.round(j * step)) * src + Math.min(src - 1, Math.round(i * step))] + dune((i + 0.5) * cell - half, (j + 0.5) * cell - half).h;
    }
    const at = (i, j) => G[Math.min(N - 1, Math.max(0, j)) * N + Math.min(N - 1, Math.max(0, i))];
    let hmin = 1e9, hmax = -1e9;
    for (let k = 0; k < H.length; k += 97) { hmin = Math.min(hmin, H[k]); hmax = Math.max(hmax, H[k]); }
    for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
      const dx = (at(i + 1, j) - at(i - 1, j)) / (2 * cell), dz = (at(i, j + 1) - at(i, j - 1)) / (2 * cell);
      // light from the north-west
      const shade = Math.max(0, Math.min(1, 0.62 + (-dx * 0.7 - dz * 0.7) * 1.6 / Math.sqrt(1 + dx * dx + dz * dz)));
      const e = (at(i, j) - hmin) / (hmax - hmin);
      const o = (j * N + i) * 4;
      d[o] = (120 + 110 * e) * shade; d[o + 1] = (92 + 80 * e) * shade; d[o + 2] = (62 + 48 * e) * shade; d[o + 3] = 255;
    }
    g.putImageData(img, 0, 0);
    this.relief = c; this.reliefN = N; this.reliefM = T.fineSize / N; // metres per pixel
  }

  // me: { x, z, fx, fz }, blips: [{ x, z, color, kind }]
  draw(me, blips) {
    const cv = this.cv, g = this.ctx;
    // Keep the uploaded texture dimensions fixed, including on low-DPI screens.
    const dpr = 2;
    const W = cv.width, R = W / 2 - 3 * dpr, cx = W / 2, cy = W / 2;
    const s = R / this.range; // px per metre
    const rot = -Math.PI / 2 - Math.atan2(me.fz, me.fx); // heading-up
    g.clearRect(0, 0, W, W);
    g.save();
    g.beginPath(); g.arc(cx, cy, R, 0, Math.PI * 2); g.clip();
    g.fillStyle = '#2a1f15'; g.fillRect(0, 0, W, W);
    g.translate(cx, cy); g.rotate(rot);
    // relief: world (x,z) -> pixel ((x + size/2)/m, (z + size/2)/m)
    const half = this.terrain.fineSize / 2, m = this.reliefM;
    g.globalAlpha = 0.9;
    g.imageSmoothingEnabled = true;
    g.drawImage(this.relief, (-half - me.x) * s, (-half - me.z) * s, this.reliefN * m * s, this.reliefN * m * s);
    g.globalAlpha = 1;
    // north tick
    g.restore();
    g.save();
    g.translate(cx, cy);
    // range rings
    g.strokeStyle = 'rgba(255,255,255,0.22)'; g.lineWidth = dpr;
    for (const f of [0.33, 0.66]) { g.beginPath(); g.arc(0, 0, R * f, 0, Math.PI * 2); g.stroke(); }
    g.beginPath(); g.moveTo(-R, 0); g.lineTo(R, 0); g.moveTo(0, -R); g.lineTo(0, R); g.stroke();
    // sweep
    const t = performance.now() / 1000 * 1.4;
    const grad = g.createConicGradient ? g.createConicGradient(t, 0, 0) : null;
    if (grad) {
      grad.addColorStop(0, 'rgba(120,255,140,0.28)'); grad.addColorStop(0.12, 'rgba(120,255,140,0)'); grad.addColorStop(1, 'rgba(120,255,140,0)');
      g.fillStyle = grad; g.beginPath(); g.arc(0, 0, R, 0, Math.PI * 2); g.fill();
    }
    // blips
    const cr = Math.cos(rot), sr = Math.sin(rot);
    for (const b of blips) {
      const dx = (b.x - me.x) * s, dz = (b.z - me.z) * s;
      let px = dx * cr - dz * sr, py = dx * sr + dz * cr;
      const d = Math.hypot(px, py);
      const edge = d > R - 6 * dpr;
      if (edge) { px *= (R - 6 * dpr) / d; py *= (R - 6 * dpr) / d; }
      g.fillStyle = b.color; g.strokeStyle = 'rgba(0,0,0,0.8)'; g.lineWidth = 1.5 * dpr;
      g.beginPath();
      if (edge) {
        // arrow on the rim pointing toward an out-of-range car
        const a = Math.atan2(py, px);
        g.save(); g.translate(px, py); g.rotate(a);
        g.moveTo(5 * dpr, 0); g.lineTo(-4 * dpr, -4 * dpr); g.lineTo(-4 * dpr, 4 * dpr); g.closePath();
        g.fill(); g.stroke(); g.restore();
      } else if (b.kind === 'player') {
        g.rect(px - 4.5 * dpr, py - 4.5 * dpr, 9 * dpr, 9 * dpr); g.fill(); g.stroke();
      } else {
        g.arc(px, py, 4.5 * dpr, 0, Math.PI * 2); g.fill(); g.stroke();
      }
    }
    // me: arrow at centre
    g.fillStyle = '#ffffff'; g.strokeStyle = '#000'; g.lineWidth = 1.5 * dpr;
    g.beginPath(); g.moveTo(0, -8 * dpr); g.lineTo(6 * dpr, 7 * dpr); g.lineTo(0, 3 * dpr); g.lineTo(-6 * dpr, 7 * dpr); g.closePath(); g.fill(); g.stroke();
    // N marker on the rim
    const na = rot - Math.PI / 2; // world north is -z
    const nx = Math.cos(na) * (R - 10 * dpr), ny = Math.sin(na) * (R - 10 * dpr);
    // The HUD's N marker is a GPU glyph; this offscreen canvas contains only map geometry.
    this.north={x:nx/(W/2),y:ny/(W/2)};
    g.restore();
    // rim
    g.strokeStyle = 'rgba(255,255,255,0.55)'; g.lineWidth = 2 * dpr;
    g.beginPath(); g.arc(cx, cy, R, 0, Math.PI * 2); g.stroke();
    this.texture.needsUpdate=true;
  }
}
