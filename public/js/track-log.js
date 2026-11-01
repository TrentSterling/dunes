// Tire-track log: every rut any sandrail presses into the sand is kept as a
// short segment record for 48 hours. The game server stores them (so they
// survive restarts and every player sees them); the client keeps the tiles
// near its cars and replays them into the visual rut map and the physics grid.
//
// Record layout (16 floats):
//  0 x0, 1 z0, 2 x1, 3 z1, 4 halfW, 5 bermW, 6 depth, 7 berm, 8 d0, 9 d1,
//  10 paddle, 11 slip, 12 type (0 paddle, 1 ribbed front), 13 churn, 14 sink, 15 time (s since EPOCH)
export const REC = 16;
export const TILE = 64;                       // m
export const KEEP_S = 48 * 3600;              // tracks last 48 hours
export const EPOCH = Date.UTC(2026, 0, 1) / 1000;
export const nowS = () => Date.now() / 1000 - EPOCH;
export const tileKey = (tx, tz) => tx * 65536 + tz;

const LOAD_R = 340;   // m around each local car: tiles kept loaded
const DROP_R = 900;   // tiles farther than this from every car are released

class Tile {
  constructor(tx, tz) { this.tx = tx; this.tz = tz; this.a = new Float32Array(REC * 64); this.n = 0; this.state = 0; this.reqT = 0; this.raster = false; }
  push(r, o = 0) {
    if ((this.n + 1) * REC > this.a.length) { const b = new Float32Array(this.a.length * 2); b.set(this.a); this.a = b; }
    this.a.set(r.subarray ? r.subarray(o, o + REC) : r.slice(o, o + REC), this.n * REC); this.n++;
  }
}

export class TrackLog {
  constructor() {
    this.tiles = new Map();
    this.outbox = [];          // our records not yet sent to the server
    this.send = null;          // (Float32Array) => void, set by the net layer
    this.request = null;       // ([[tx,tz],...]) => void
    this.connected = false;
    this.onRecords = null;     // (Float32Array, count) called for records from elsewhere
    this.onTile = null;        // (tile) called when a tile's stored tracks arrive
    this._sendT = 0;
  }

  _tile(tx, tz, create) {
    const k = tileKey(tx, tz);
    let t = this.tiles.get(k);
    if (!t && create) { t = new Tile(tx, tz); this.tiles.set(k, t); }
    return t;
  }
  static tileOf(r, o = 0) { return [Math.floor((r[o] + r[o + 2]) * 0.5 / TILE), Math.floor((r[o + 1] + r[o + 3]) * 0.5 / TILE)]; }

  // a segment one of our own cars just pressed (already drawn live)
  addOwn(r) {
    const [tx, tz] = TrackLog.tileOf(r);
    this._tile(tx, tz, true).push(r);
    this.outbox.push(r.slice ? r.slice() : Float32Array.from(r));
  }

  // records from another player (live broadcast)
  addRemote(buf, o, count) {
    for (let i = 0; i < count; i++) {
      const p = o + i * REC;
      const [tx, tz] = TrackLog.tileOf(buf, p);
      const t = this._tile(tx, tz, false);
      if (t && t.state === 2) t.push(buf, p);
    }
    this.onRecords?.(buf, o, count);
  }

  // stored tracks for one tile arrived from the server
  receiveTile(tx, tz, buf, o, count) {
    const t = this._tile(tx, tz, true);
    // keep our own records made after the request went out (not in the server's copy yet)
    const keep = [];
    for (let i = 0; i < t.n; i++) if (t.a[i * REC + 15] >= t.reqT - 2) keep.push(t.a.slice(i * REC, (i + 1) * REC));
    t.n = 0;
    if (t.a.length < (count + keep.length) * REC) t.a = new Float32Array((count + keep.length + 64) * REC);
    t.a.set(buf.subarray(o, o + count * REC), 0); t.n = count;
    for (const r of keep) t.push(r);
    t.state = 2; t.raster = false;
    this.onTile?.(t);
  }

  // every records in tiles touching the rectangle
  forEachIn(x0, z0, x1, z1, fn) {
    const m = 4;
    const tx0 = Math.floor((x0 - m) / TILE), tx1 = Math.floor((x1 + m) / TILE);
    const tz0 = Math.floor((z0 - m) / TILE), tz1 = Math.floor((z1 + m) / TILE);
    for (let tz = tz0; tz <= tz1; tz++) for (let tx = tx0; tx <= tx1; tx++) {
      const t = this.tiles.get(tileKey(tx, tz));
      if (!t || !t.n) continue;
      const a = t.a;
      for (let i = 0; i < t.n; i++) {
        const p = i * REC;
        if (Math.max(a[p], a[p + 2]) < x0 - 1 || Math.min(a[p], a[p + 2]) > x1 + 1 || Math.max(a[p + 1], a[p + 3]) < z0 - 1 || Math.min(a[p + 1], a[p + 3]) > z1 + 1) continue;
        fn(a, p);
      }
    }
  }

  // keep tiles around our cars loaded, release far ones, upload new records
  update(dt, cars) {
    this._sendT += dt;
    if (this._sendT >= 0.5) {
      this._sendT = 0;
      if (this.connected && this.send && this.outbox.length) {
        const n = Math.min(this.outbox.length, 2000);
        const buf = new Float32Array(1 + n * REC);
        buf[0] = 1;
        for (let i = 0; i < n; i++) buf.set(this.outbox[i], 1 + i * REC);
        this.outbox.splice(0, n);
        this.send(buf);
      } else if (!this.connected && this.outbox.length > 50000) this.outbox.splice(0, this.outbox.length - 50000);
      const want = [], now = nowS();
      for (const c of cars) {
        const tx0 = Math.floor((c.x - LOAD_R) / TILE), tx1 = Math.floor((c.x + LOAD_R) / TILE);
        const tz0 = Math.floor((c.z - LOAD_R) / TILE), tz1 = Math.floor((c.z + LOAD_R) / TILE);
        for (let tz = tz0; tz <= tz1; tz++) for (let tx = tx0; tx <= tx1; tx++) {
          const t = this._tile(tx, tz, true);
          if (t.state === 0 || (t.state === 1 && now - t.reqT > 10)) {
            if (this.connected && this.request) { t.state = 1; t.reqT = now; want.push([tx, tz]); }
            else if (t.state === 0) { t.state = 2; this.onTile?.(t); } // offline: tracks only live in this session
          }
        }
      }
      if (want.length) this.request(want);
      // release tiles far from every car (the server still has them)
      if (this.connected) for (const [k, t] of this.tiles) {
        const cx = (t.tx + 0.5) * TILE, cz = (t.tz + 0.5) * TILE;
        let near = false;
        for (const c of cars) if (Math.abs(c.x - cx) < DROP_R && Math.abs(c.z - cz) < DROP_R) { near = true; break; }
        if (!near && !this.outbox.some(r => Math.floor((r[0] + r[2]) * 0.5 / TILE) === t.tx && Math.floor((r[1] + r[3]) * 0.5 / TILE) === t.tz)) this.tiles.delete(k);
      }
    }
  }

  // connection (re)established: fetch the stored tracks for everything loaded
  setConnected(on) {
    this.connected = on;
    if (on) for (const t of this.tiles.values()) if (t.state !== 1) t.state = 0;
  }

  expire() {
    const cut = nowS() - KEEP_S;
    let changed = false;
    for (const t of this.tiles.values()) {
      let j = 0;
      for (let i = 0; i < t.n; i++) if (t.a[i * REC + 15] >= cut) { if (i !== j) t.a.copyWithin(j * REC, i * REC, (i + 1) * REC); j++; }
      if (j !== t.n) { t.n = j; changed = true; }
    }
    return changed;
  }
}

// Turns a wheel's per-frame stamps into ~1 m segments worth keeping.
export class TrackPen {
  constructor() { this.on = false; this.r = new Float32Array(REC); }
  // s: the stamp drawn this frame (deform record layout); returns a finished record or null
  feed(s, maxLen) {
    const r = this.r;
    if (!this.on) { r.set(s); r[0] = s[2]; r[1] = s[3]; r[8] = s[9]; this.on = true; return null; }
    r[2] = s[2]; r[3] = s[3]; r[9] = s[9];
    for (const k of [6, 7, 10, 11, 13, 14]) if (s[k] > r[k]) r[k] = s[k];
    r[4] = s[4]; r[5] = s[5]; r[12] = s[12];
    const dx = r[2] - r[0], dz = r[3] - r[1], len = Math.hypot(dx, dz);
    if (len < 0.05) return null;
    // done when long enough, or when the wheel turns away from the segment's line
    const hx = s[2] - s[0], hz = s[3] - s[1], hl = Math.hypot(hx, hz);
    const bend = hl > 1e-3 ? 1 - (dx * hx + dz * hz) / (len * hl) : 0;
    if (len >= maxLen || bend > 0.006 || len > 4) return this._emit(s);
    return null;
  }
  // wheel left the ground: finish what's there
  lift() { const out = this.on && Math.hypot(this.r[2] - this.r[0], this.r[3] - this.r[1]) > 0.05 ? this._emit(null) : null; this.on = false; return out; }
  _emit(s) {
    const out = this.r.slice();
    out[15] = nowS();
    if (s) { this.r.set(s); this.r[0] = s[2]; this.r[1] = s[3]; this.r[8] = s[9]; } else this.on = false;
    return out;
  }
}
