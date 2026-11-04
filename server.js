// Glamis game: game web server + multiplayer relay.
// Usage: node server.js [port]   (default 8080). Then open http://localhost:8080
import http from 'http';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { fileURLToPath } from 'url';
import { WebSocketServer } from 'ws';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC = path.join(__dirname, 'public');
const ASSETS = path.join(__dirname, 'assets'); // sandrail models (.glb), served at /assets/
const PORT = Number(process.argv[2] || process.env.PORT || 8080);
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json',
  '.css': 'text/css', '.png': 'image/png', '.webp': 'image/webp', '.u16': 'application/octet-stream', '.ico': 'image/x-icon',
  '.glb': 'model/gltf-binary', '.gltf': 'model/gltf+json', '.jpg': 'image/jpeg', '.ktx2': 'image/ktx2',
  '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg', '.wav': 'audio/wav', '.m4a': 'audio/mp4',
};

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (p === '/') p = '/index.html';
  const base = p.startsWith('/assets/') ? ASSETS : PUBLIC;
  if (base === ASSETS) p = p.slice('/assets'.length);
  const file = path.normalize(path.join(base, p));
  if (!file.startsWith(base)) { res.writeHead(403); res.end(); return; }
  fs.stat(file, (err, st) => {
    // /assets/audio/ lists its files, so the game only asks for the optional sounds that exist
    if (!err && st.isDirectory() && path.resolve(file) === path.join(ASSETS, 'audio')) {
      fs.readdir(file, (e, names) => { res.writeHead(200, { 'Content-Type': TYPES['.json'], 'Cache-Control': 'no-cache' }); res.end(JSON.stringify(e ? [] : names)); });
      return;
    }
    if (err || !st.isFile()) { res.writeHead(404); res.end('not found'); return; }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream', 'Content-Length': st.size, 'Cache-Control': 'no-cache' });
    fs.createReadStream(file).pipe(res);
  });
});

// ---- tire tracks: every rut is kept for 48 hours, saved in track-data/ ----
// A record is 16 floats (see public/js/track-log.js); slot 15 is its time.
const REC = 16, TILE = 64, KEEP_S = 48 * 3600, EPOCH = Date.UTC(2026, 0, 1) / 1000;
const MAX_RECORDS = 3000000; // ~190 MB; past this the oldest tracks go first
const TRACK_DIR = path.join(__dirname, 'track-data');
const tracks = new Map(); // "tx_tz" -> { a: Float32Array, n, dirty }
let trackTotal = 0;
const nowS = () => Date.now() / 1000 - EPOCH;
function trackTile(key, create) {
  let t = tracks.get(key);
  if (!t && create) { t = { a: new Float32Array(REC * 256), n: 0, dirty: false }; tracks.set(key, t); }
  return t;
}
function addTrackRecords(f, o) {
  for (let p = o; p + REC <= f.length; p += REC) {
    const x = (f[p] + f[p + 2]) * 0.5, z = (f[p + 1] + f[p + 3]) * 0.5;
    if (!Number.isFinite(x) || !Number.isFinite(z) || Math.abs(x) > 1e5 || Math.abs(z) > 1e5) continue;
    const t = trackTile(Math.floor(x / TILE) + '_' + Math.floor(z / TILE), true);
    if ((t.n + 1) * REC > t.a.length) { const b = new Float32Array(t.a.length * 2); b.set(t.a); t.a = b; }
    t.a.set(f.subarray(p, p + REC), t.n * REC); t.n++; t.dirty = true; trackTotal++;
  }
  if (trackTotal > MAX_RECORDS) expireTracks(true);
}
function expireTracks(trim) {
  let cut = nowS() - KEEP_S;
  if (trim) cut = Math.max(cut, cut + (nowS() - cut) * 0.1); // over the limit: drop the oldest tenth of the window
  trackTotal = 0;
  for (const [k, t] of tracks) {
    let j = 0;
    for (let i = 0; i < t.n; i++) if (t.a[i * REC + 15] >= cut) { if (i !== j) t.a.copyWithin(j * REC, i * REC, (i + 1) * REC); j++; }
    if (j !== t.n) { t.n = j; t.dirty = true; }
    trackTotal += t.n;
  }
}
function saveTracks() {
  for (const [k, t] of tracks) {
    if (!t.dirty) continue;
    t.dirty = false;
    const file = path.join(TRACK_DIR, k + '.bin');
    if (!t.n) { fs.rm(file, { force: true }, () => {}); tracks.delete(k); continue; }
    fs.writeFile(file, Buffer.from(t.a.buffer, 0, t.n * REC * 4), () => {});
  }
}
try {
  fs.mkdirSync(TRACK_DIR, { recursive: true });
  for (const f of fs.readdirSync(TRACK_DIR)) {
    if (!/^-?\d+_-?\d+\.bin$/.test(f)) continue;
    const b = fs.readFileSync(path.join(TRACK_DIR, f));
    const n = Math.floor(b.length / (REC * 4));
    const a = new Float32Array(Math.max(n, 256) * REC);
    a.set(new Float32Array(b.buffer.slice(b.byteOffset, b.byteOffset + n * REC * 4)));
    tracks.set(f.slice(0, -4), { a, n, dirty: false });
    trackTotal += n;
  }
  expireTracks(false);
  if (trackTotal) console.log(`Loaded ${trackTotal} tire track pieces from the last 48 hours.`);
} catch (e) { console.log('Could not load saved tracks:', e.message); }
setInterval(saveTracks, 20000);
setInterval(() => expireTracks(false), 10 * 60000);
process.on('SIGINT', () => { saveTracks(); setTimeout(() => process.exit(0), 300); });

// ---- multiplayer relay ----
const wss = new WebSocketServer({ server });
const players = new Map(); // id -> {ws, name, tint, last}
let nextId = 1;
// shared world settings (weather, gravity, grip, ...): the first player in sets them, later changes from anyone apply to all
const world = {};
const WORLD_KEYS = new Set(['weather', 'tod', 'night', 'wind', 'gravity', 'grip', 'softness', 'wheelieControl', 'steerAssist', 'aiCount', 'aiSkill']);
const okValue = (v) => ['number', 'string', 'boolean'].includes(typeof v) && String(v).length < 40;
const COLORS = [0xb00d12, 0x1450c8, 0xe08a00, 0x18a040, 0x8a20c0, 0xd0d0d0, 0x101010, 0xe0c000];

wss.on('connection', (ws) => {
  const id = nextId++;
  const p = { ws, name: 'Driver ' + id, tint: COLORS[(id - 1) % COLORS.length], car: '', last: null };
  players.set(id, p);
  ws.on('message', (data, isBinary) => {
    if (isBinary) {
      // our tire tracks: store them and pass them on to everyone else
      if (data.length < 4 + REC * 4 || data.length % 4) return;
      const f = new Float32Array(data.buffer.slice(data.byteOffset, data.byteOffset + data.length));
      if (f[0] !== 1) return;
      addTrackRecords(f, 1);
      for (const [k, o] of players) if (k !== id && o.ws.readyState === 1) o.ws.send(f);
      return;
    }
    let msg; try { msg = JSON.parse(data); } catch { return; }
    if (msg.t === 'hello') {
      p.name = String(msg.name || p.name).slice(0, 24);
      if (Number.isInteger(msg.tint)) p.tint = msg.tint;
      p.car = String(msg.car || '').slice(0, 40);
      if (msg.world && typeof msg.world === 'object') for (const [k, v] of Object.entries(msg.world)) if (WORLD_KEYS.has(k) && !(k in world) && okValue(v)) world[k] = v;
      const others = [...players].filter(([k]) => k !== id).map(([k, o]) => ({ id: k, name: o.name, tint: o.tint, car: o.car, s: o.last }));
      send(ws, { t: 'welcome', id, tint: p.tint, players: others, world });
      broadcast({ t: 'join', id, name: p.name, tint: p.tint, car: p.car }, id);
      console.log(`+ ${p.name} joined (${players.size} online)`);
    } else if (msg.t === 'state') {
      p.last = msg.s;
      broadcast({ t: 'state', id, s: msg.s }, id);
    } else if (msg.t === 'setting') {
      if (!WORLD_KEYS.has(msg.key) || !okValue(msg.value)) return;
      world[msg.key] = msg.value;
      broadcast({ t: 'setting', key: msg.key, value: msg.value, name: p.name }, id);
      console.log(`  ${p.name} set ${msg.key} = ${msg.value}`);
    } else if (msg.t === 'name') {
      p.name=String(msg.name||'Driver').replace(/[\x00-\x1f\x7f]/g,'').trim().slice(0,24)||'Driver';
      broadcast({t:'name',id,name:p.name},id);
    } else if (msg.t === 'car') {
      p.car = String(msg.car || '').slice(0, 40);
      broadcast({ t: 'car', id, car: p.car }, id);
    } else if (msg.t === 'trkReq' && Array.isArray(msg.keys)) {
      // stored tracks for the tiles a player is driving into
      for (const kk of msg.keys.slice(0, 400)) {
        if (!Array.isArray(kk) || !Number.isInteger(kk[0]) || !Number.isInteger(kk[1])) continue;
        const t = tracks.get(kk[0] + '_' + kk[1]);
        const n = t ? t.n : 0;
        const out = new Float32Array(3 + n * REC);
        out[0] = 2; out[1] = kk[0]; out[2] = kk[1];
        if (n) out.set(t.a.subarray(0, n * REC), 3);
        if (ws.readyState === 1) ws.send(out);
      }
    } else if (msg.t === 'chat') {
      broadcast({ t: 'chat', id, name: p.name, text: String(msg.text).slice(0, 200) }, -1);
    }
  });
  ws.on('close', () => {
    players.delete(id);
    broadcast({ t: 'leave', id }, id);
    console.log(`- ${p.name} left (${players.size} online)`);
  });
});
function send(ws, m) { if (ws.readyState === 1) ws.send(JSON.stringify(m)); }
function broadcast(m, except) { const s = JSON.stringify(m); for (const [k, o] of players) if (k !== except && o.ws.readyState === 1) o.ws.send(s); }

server.listen(PORT, () => {
  console.log(`\nGlamis game server running.`);
  console.log(`  Play on this PC:   http://localhost:${PORT}`);
  for (const ifs of Object.values(os.networkInterfaces())) for (const i of ifs || []) {
    if (i.family === 'IPv4' && !i.internal) console.log(`  Friends on your network: http://${i.address}:${PORT}`);
  }
  console.log('');
});
