import { joinRoom, selfId, getRelaySockets } from '../vendor/trystero.js';
import { REC, tileKey, nowS, KEEP_S } from './track-log.js';

const APP_ID = 'xyz.tront.dunes.v1';
export const DEFAULT_ROOM = 'global';
const COLORS = [0xb00d12, 0x1450c8, 0xe08a00, 0x18a040, 0x8a20c0, 0xd0d0d0];
const WORLD_KEYS = new Set(['weather', 'tod', 'night', 'wind', 'gravity', 'grip', 'softness', 'wheelieControl', 'steerAssist', 'aiCount', 'aiSkill']);
const validValue = v => ['number', 'string', 'boolean'].includes(typeof v) && String(v).length < 40 && (typeof v !== 'number' || Number.isFinite(v));
const vector = (v, length) => Array.isArray(v) && v.length === length && v.every(n => Number.isFinite(n) && Math.abs(n) < 1e8);
const validState = s => s && vector(s.p, 3) && vector(s.q, 4) && vector(s.v, 3) && Array.isArray(s.w) && s.w.length === 4 && s.w.every(w => Array.isArray(w) && w.length <= 8 && w.every(Number.isFinite)) && ['rpm', 'gear', 'thr', 'ts'].every(k => Number.isFinite(s[k]));

// Keep the game's NetClient contract. Only discovery goes through Nostr;
// cars, settings and tire tracks use the connected WebRTC data channels.
export class PeerClient {
  constructor(handlers) {
    this.h = handlers;
    this.id = selfId;
    this.transport = 'trystero';
    const requested=new URLSearchParams(location.search).get('room');
    this.roomId = (!requested||requested==='public'?DEFAULT_ROOM:requested).replace(/[^a-zA-Z0-9_-]/g, '-').slice(0,48)||DEFAULT_ROOM;
    this.peers = new Map();
    this.versions = {};
    this.clock = 0;
    this.born = Date.now();
    this.connected = false;
    this.sendTimer = 0;
    this.metrics = { statesSent: 0, statesReceived: 0, tracksSent: 0, tracksReceived: 0, tilesReceived: 0, sendFailures: 0 };
  }

  connect(name, car) {
    this.name = String(name).slice(0, 24); this.car = String(car).slice(0, 40);
    if (this.room) return;
    for (const [key, value] of Object.entries(this.world?.() || {})) {
      if (WORLD_KEYS.has(key) && validValue(value)) this.versions[key] = { value, counter: 0, author: selfId, born: this.born };
    }
    try {
      this.room = joinRoom({ appId: APP_ID, maxReceiveBytes: 1024 * 1024 }, this.roomId, {
        onJoinError: ({ error }) => { this.lastError = String(error); this.status(); },
      });
      this.control = this.room.makeAction('control');
      this.state = this.room.makeAction('state');
      this.tracks = this.room.makeAction('tracks');
      this.control.onMessage = (message, { peerId }) => this.onControl(message, peerId);
      this.state.onMessage = (state, { peerId }) => {
        if (!this.peers.get(peerId)?.ready || !validState(state)) return;
        this.metrics.statesReceived++; this.h.onState?.(peerId, state);
      };
      this.tracks.onMessage = (data, { peerId }) => this.onTracks(data, peerId);
      this.room.onPeerJoin = peerId => {
        this.peers.set(peerId, { ready: false });
        this.send(this.control, { t: 'hello', name: this.name, car: this.car, versions: this.versions }, peerId);
      };
      this.room.onPeerLeave = peerId => {
        if (this.peers.get(peerId)?.ready) this.h.onLeave?.(peerId);
        this.peers.delete(peerId); this.status();
      };
      this.onPageHide = () => this.disconnect();
      addEventListener('pagehide', this.onPageHide, { once: true });
      this.status();
    } catch (error) {
      this.lastError = error.message;
      this.h.onStatus?.(false, 'Multiplayer unavailable · solo driving');
    }
  }

  status() {
    this.connected = [...this.peers.values()].some(peer => peer.ready);
    const count = [...this.peers.values()].filter(peer => peer.ready).length;
    this.h.onStatus?.(this.connected, `${this.roomId===DEFAULT_ROOM?'Global lobby':'Room '+this.roomId} / ${count+1} ${count?'drivers':'driver'}`);
  }

  send(action, data, target) {
    if (!action) return Promise.resolve();
    return action.send(data, target ? { target } : undefined).catch(error => {
      this.metrics.sendFailures++; this.lastError = error.message;
    });
  }

  mergeVersions(versions, name) {
    if (!versions || typeof versions !== 'object') return;
    const changed = {};
    for (const [key, next] of Object.entries(versions)) {
      if (!WORLD_KEYS.has(key) || !next || !validValue(next.value) || !Number.isSafeInteger(next.counter) || next.counter < 0 || next.counter > 1e9 || typeof next.author !== 'string' || next.author.length > 64 || !Number.isFinite(next.born)) continue;
      this.clock = Math.max(this.clock, next.counter);
      const prev = this.versions[key];
      const newer = !prev || next.counter > prev.counter || (next.counter === prev.counter && (next.counter === 0 ? next.born < prev.born || (next.born === prev.born && next.author < prev.author) : next.author > prev.author));
      if (newer) { this.versions[key] = next; changed[key] = next.value; }
    }
    if (Object.keys(changed).length) {
      if (name) for (const [key, value] of Object.entries(changed)) this.h.onSetting?.(key, value, name);
      else this.h.onWorld?.(changed);
    }
  }

  onControl(message, peerId) {
    if (!message || typeof message !== 'object' || !this.peers.has(peerId)) return;
    if (message.t === 'hello') {
      const name = String(message.name || 'Driver').slice(0, 24), car = String(message.car || 'pro').slice(0, 40);
      if (!this.peers.get(peerId).ready) {
        this.peers.set(peerId, { ready: true, name, car });
        const tint = COLORS[[...peerId].reduce((sum, char) => sum + char.charCodeAt(0), 0) % COLORS.length];
        this.h.onJoin?.(peerId, name, tint, null, car);
        this.status();
      }
      this.mergeVersions(message.versions);
    } else if (message.t === 'name') {
      const name=String(message.name||'Driver').replace(/[\x00-\x1f\x7f]/g,'').trim().slice(0,24)||'Driver';
      this.peers.get(peerId).name=name;this.h.onName?.(peerId,name);
    } else if (message.t === 'setting') {
      this.mergeVersions(message.versions, this.peers.get(peerId).name);
    } else if (message.t === 'car') {
      const car = String(message.car || 'pro').slice(0, 40);
      this.peers.get(peerId).car = car; this.h.onCar?.(peerId, car);
    } else if (message.t === 'trkReq' && Array.isArray(message.keys)) {
      for (const key of message.keys.slice(0, 400)) {
        if (!Array.isArray(key) || key.length !== 2 || !key.every(n => Number.isInteger(n) && Math.abs(n) <= 2000)) continue;
        const tile = this.trackLog?.tiles.get(tileKey(...key));
        const count = Math.min(tile?.n || 0, 8192);
        const buffer = new Float32Array(3 + count * REC);
        buffer.set([2, ...key]);
        if (count) buffer.set(tile.a.subarray((tile.n - count) * REC, tile.n * REC), 3);
        this.send(this.tracks, buffer, peerId);
      }
    }
  }

  onTracks(data, peerId) {
    if (!this.peers.get(peerId)?.ready || (!ArrayBuffer.isView(data) && !(data instanceof ArrayBuffer)) || data.byteLength % 4 || data.byteLength > 1024 * 1024) return;
    // Trystero 0.26 delivers binary actions as Uint8Array views.
    const bytes = ArrayBuffer.isView(data) ? data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength) : data;
    const floats = new Float32Array(bytes);
    const offset = floats[0] === 1 ? 1 : floats[0] === 2 ? 3 : 0;
    if (!offset || floats.length < offset || (floats.length - offset) % REC) return;
    if (offset === 3 && (!Number.isInteger(floats[1]) || !Number.isInteger(floats[2]) || Math.abs(floats[1]) > 2000 || Math.abs(floats[2]) > 2000)) return;
    const now = nowS();
    for (let at = offset; at < floats.length; at += REC) {
      for (let i = 0; i < REC; i++) if (!Number.isFinite(floats[at + i])) return;
      if (floats[at + 15] < now - KEEP_S || floats[at + 15] > now + 300) return;
    }
    if (offset === 1) this.metrics.tracksReceived += (floats.length - 1) / REC;
    else this.metrics.tilesReceived++;
    this.h.onBinary?.(floats);
  }

  sendBinary(buffer) {
    if (!this.connected) return;
    this.metrics.tracksSent += (buffer.length - 1) / REC;
    this.send(this.tracks, buffer);
  }

  sendJSON(message) {
    if (!this.connected || message.t !== 'trkReq') return;
    // One donor avoids receiving the same historical tire tracks from every peer.
    const donor = [...this.peers.keys()].filter(id => this.peers.get(id).ready).sort()[0];
    if (donor) this.send(this.control, message, donor);
  }

  sendSetting(key, value) {
    if (!WORLD_KEYS.has(key) || !validValue(value)) return;
    this.versions[key] = { value, counter: ++this.clock, author: selfId, born: this.born };
    if (this.connected) this.send(this.control, { t: 'setting', versions: { [key]: this.versions[key] } });
  }

  setCar(car) {
    this.car = car;
    if (this.connected) this.send(this.control, { t: 'car', car });
  }

  setName(name) {
    this.name=String(name).trim().slice(0,24)||'Driver';
    // A data channel can be open while its hello is still being handled.
    // Send to those peers too; later arrivals get this.name in their hello.
    if(this.room)this.send(this.control,{t:'name',name:this.name});
  }

  update(dt, getState) {
    if (!this.connected) return;
    this.sendTimer += dt;
    if (this.sendTimer < 0.05 || this.statePending) return;
    this.sendTimer = 0;
    const state = getState(); state.ts = performance.now();
    this.statePending = true; this.metrics.statesSent++;
    this.send(this.state, state).finally(() => { this.statePending = false; });
  }

  diagnostics() {
    return { transport: this.transport, room: this.roomId, id: this.id, peers: [...this.peers.keys()], connected: this.connected,
      metrics: { ...this.metrics }, lastError: this.lastError || null,
      relays: Object.entries(getRelaySockets()).map(([url, socket]) => ({ url, state: socket.readyState })) };
  }

  async disconnect() {
    removeEventListener('pagehide', this.onPageHide);
    await this.room?.leave();
    this.room = null;
    for (const id of this.peers.keys()) this.h.onLeave?.(id);
    this.peers.clear(); this.status();
  }
}
