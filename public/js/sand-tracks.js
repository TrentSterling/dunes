// Physical ruts: a sparse grid (15 cm cells) remembering how deep every tire
// pressed the sand and how much it pushed up beside the track. The tire model
// reads it back, so wheels drop into old ruts, follow them, roll easier on the
// packed floor and bump over the berms when crossing them. Shared by every car.
const CELL = 0.15, CN = 128, CHUNK = CELL * CN; // 19.2 m chunks
const Q = 0.005;          // quantization: 5 mm per step, 255 = 1.27 m
const MAX_CHUNKS = 1500;  // ~50 MB; forgotten chunks are rebuilt from the track log when needed

export class SandTracks {
  constructor() { this.chunks = new Map(); this.tick = 0; }

  _chunk(cx, cz, create) {
    const key = cx * 100003 + cz;
    let c = this.chunks.get(key);
    if (!c && create) {
      if (this.chunks.size >= MAX_CHUNKS) this._evict();
      c = { depth: new Uint8Array(CN * CN), berm: new Uint8Array(CN * CN), used: 0 };
      this.chunks.set(key, c);
    }
    if (c) c.used = this.tick;
    return c;
  }

  _evict() {
    let oldK = null, oldT = Infinity;
    for (const [k, c] of this.chunks) if (c.used < oldT) { oldT = c.used; oldK = k; }
    if (oldK !== null) {
      this.chunks.delete(oldK);
      // the 48-hour track log still has these ruts: rebuild them when a car comes back
      if (this.log) {
        const cz = ((oldK % 100003) + 100003 + 50001) % 100003 - 50001, cx = Math.round((oldK - cz) / 100003);
        const T = 64, x0 = cx * CHUNK, z0 = cz * CHUNK;
        for (const [x, z] of [[x0, z0], [x0 + CHUNK, z0], [x0, z0 + CHUNK], [x0 + CHUNK, z0 + CHUNK]]) {
          const t = this.log.tiles.get(Math.floor(x / T) * 65536 + Math.floor(z / T));
          if (t) t.raster = false;
        }
      }
    }
  }

  // press a stored track segment (track-log record) into the grid
  stampSeg(r, o = 0) {
    const x0 = r[o], z0 = r[o + 1], dx = r[o + 2] - x0, dz = r[o + 3] - z0, len = Math.hypot(dx, dz);
    const sink = r[o + 14]; if (sink <= 0.004) return;
    const fx = len > 1e-4 ? dx / len : 1, fz = len > 1e-4 ? dz / len : 0;
    const steps = Math.max(1, Math.ceil(len / 0.3));
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      this.stamp(x0 + dx * t, z0 + dz * t, fx, fz, r[o + 4], 0.2, sink, 0.01 + 0.45 * sink);
    }
  }

  _cell(x, z) {
    const ix = Math.floor(x / CELL), iz = Math.floor(z / CELL);
    const cx = Math.floor(ix / CN), cz = Math.floor(iz / CN);
    return [cx, cz, (iz - cz * CN) * CN + (ix - cx * CN)];
  }

  // rut depth and berm height (m) at a point, bilinear between cells
  read(x, z, out) {
    const fx = x / CELL - 0.5, fz = z / CELL - 0.5;
    const ix = Math.floor(fx), iz = Math.floor(fz), tx = fx - ix, tz = fz - iz;
    let d = 0, b = 0;
    for (let k = 0; k < 4; k++) {
      const jx = ix + (k & 1), jz = iz + (k >> 1);
      const cx = Math.floor(jx / CN), cz = Math.floor(jz / CN);
      const c = this.chunks.get(cx * 100003 + cz);
      if (!c) continue;
      const i = (jz - cz * CN) * CN + (jx - cx * CN);
      const w = ((k & 1) ? tx : 1 - tx) * ((k >> 1) ? tz : 1 - tz);
      d += c.depth[i] * w; b += c.berm[i] * w;
    }
    // half depth, to match the rut map drawn on the terrain (deform.js)
    out.depth = d * Q * 0.5; out.berm = b * Q * 0.5;
    return out;
  }

  // surface offset (m) relative to the untouched dune: berm - depth
  surf(x, z) { const o = this.read(x, z, this._o || (this._o = {})); return o.berm - o.depth; }

  // press a tire footprint: depth across the tread, berm pushed out each side
  stamp(x, z, fx, fz, halfW, halfL, depth, bermH) {
    this.tick++;
    if (depth <= 0.004) return;
    const bw = halfW * 0.8 + 0.08, R = halfW + bw, L = halfL + CELL;
    const sx = -fz, sz = fx; // side axis
    const ext = Math.max(R, L);
    const i0 = Math.floor((x - ext) / CELL), i1 = Math.floor((x + ext) / CELL);
    const j0 = Math.floor((z - ext) / CELL), j1 = Math.floor((z + ext) / CELL);
    const dq = Math.min(255, depth / Q), bq = Math.min(255, bermH / Q);
    for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) {
      const px = (i + 0.5) * CELL - x, pz = (j + 0.5) * CELL - z;
      const a = Math.abs(px * fx + pz * fz), s = Math.abs(px * sx + pz * sz);
      if (a > L || s > R) continue;
      const cap = a > halfL ? 1 - (a - halfL) / CELL : 1;
      const cx = Math.floor(i / CN), cz = Math.floor(j / CN);
      const c = this._chunk(cx, cz, true);
      const k = (j - cz * CN) * CN + (i - cx * CN);
      if (s < halfW) {
        const t = s / halfW, v = dq * (1 - t * t * t * t) * cap;
        if (v > c.depth[k]) c.depth[k] = v;
        if (cap > 0.5) c.berm[k] >>= 1; // a tire rolling over a berm flattens it
      } else {
        const t = (s - halfW) / bw, v = bq * Math.sin(Math.PI * Math.min(1, t * 1.1)) * (1 - 0.4 * t) * cap;
        if (v > c.berm[k] && c.depth[k] < 2) c.berm[k] = v;
      }
    }
  }
}

export function tracksFor(terrain) { return terrain._tracks || (terrain._tracks = new SandTracks()); }
