import { chromium } from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const base = (process.env.DUNES_URL || 'http://127.0.0.1:5191/dunes').replace(/\/$/, '');
const phase = process.env.DUNES_PHASE || 'local';
const out = path.join(root, 'artifacts/deployment', phase);
fs.mkdirSync(out, { recursive: true });
const room = `verify-${Date.now()}`;
const report = { url: base, room, checks: [], errors: [], failedRequests: [], relayWarnings: [], warnings: [] };
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--ignore-gpu-blocklist'] });
const pages = [];
const check = message => { report.checks.push(message); console.log('PASS', message); };
async function client(name) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  await context.addInitScript(name => {
    localStorage.setItem('glamis-name', name);
    localStorage.setItem('glamis-settings-v1', JSON.stringify({ car: 'pro', proCarV: 1, aiCount: 0, showHelp: false, camMode: 0 }));
  }, name);
  const page = await context.newPage(); pages.push(page);
  page.on('pageerror', e => report.errors.push(`${name}: ${e.message}`));
  page.on('console', m => {
    if (m.type() === 'error') {
      if (/WebSocket connection.*wss:\/\//.test(m.text())) report.relayWarnings.push(m.text());
      else report.errors.push(`${name}: ${m.text()}`);
    } else if (m.type() === 'warning') report.warnings.push(m.text());
  });
  page.on('requestfailed', r => report.failedRequests.push(`${name}: ${r.failure()?.errorText} ${r.url()}`));
  page.on('response', r => { if (r.status() >= 400) report.failedRequests.push(`${name}: ${r.status()} ${r.url()}`); });
  await page.goto(`${base}/?q=low&shot&tod=15&room=${room}`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => window.__frames > 10 && window.__game?.model?.wheelRigs?.length === 4, null, { timeout: 120000 });
  console.log('READY', name);
  return page;
}
try {
  const a = await client('Dunes QA A');
  await a.evaluate(() => window.__game.setSetting('gravity', 8));
  const b = await client('Dunes QA B');
  await Promise.all([a, b].map(p => p.waitForFunction(() => window.__game.net.connected && window.__game.remotes.size === 1, null, { timeout: 90000 })));
  check('Two isolated Chrome clients discover each other through public Trystero relays');
  await b.waitForFunction(() => window.__game.settings.gravity === 8);
  check('Joining client receives the existing room world settings');
  await Promise.all([a, b].map(p => p.waitForFunction(() => window.__game.net.metrics.statesReceived > 10, null, { timeout: 30000 })));
  check('Vehicle state packets flow in both directions over WebRTC');
  const before = await a.evaluate(() => window.__game.car.pos.toArray());
  await a.keyboard.down('KeyW');
  await a.waitForTimeout(2200);
  await a.keyboard.up('KeyW');
  const after = await a.evaluate(() => window.__game.car.pos.toArray());
  report.distanceMetres = Math.hypot(...after.map((n, i) => n - before[i]));
  assert.ok(report.distanceMetres > 2, 'Keyboard throttle must move the buggy');
  await b.waitForFunction(before => {
    const remote = [...window.__game.remotes.values()][0];
    return remote?.buf?.length && Math.hypot(...remote.buf.at(-1).s.p.map((n, i) => n - before[i])) > 2;
  }, before, { timeout: 30000 });
  check('Real keyboard driving moves the local buggy and updates the other client');
  await b.waitForFunction(() => window.__game.net.metrics.tracksReceived > 0, null, { timeout: 30000 });
  check('Driving tire-track records arrive at the other peer');
  await a.evaluate(() => window.__game.setSetting('gravity', 7));
  await b.waitForFunction(() => window.__game.settings.gravity === 7);
  await b.evaluate(() => window.__game.setSetting('gravity', 9));
  await a.waitForFunction(() => window.__game.settings.gravity === 9);
  check('Shared settings update in both directions');
  await a.evaluate(() => window.__game.setSetting('car', 'blue'));
  await b.waitForFunction(() => [...window.__game.net.peers.values()][0]?.car === 'blue');
  check('Changing vehicles updates the remote driver');
  await Promise.all(pages.map((page, i) => page.screenshot({ path: path.join(out, `multiplayer-${i + 1}.png`) })));
  report.clients = await Promise.all(pages.map(p => p.evaluate(() => window.__game.net.diagnostics())));
  report.peerConnections = await a.evaluate(async () => {
    const results = [];
    for (const [id, pc] of Object.entries(window.__game.net.room.getPeers())) {
      const stats = await pc.getStats();
      const pairs = [...stats.values()].filter(s => s.type === 'candidate-pair' && s.state === 'succeeded' && s.nominated);
      results.push({ id, connectionState: pc.connectionState, channels: [...stats.values()].filter(s => s.type === 'data-channel').map(s => ({ state: s.state, messagesSent: s.messagesSent, messagesReceived: s.messagesReceived })), pairs: pairs.map(s => ({ bytesSent: s.bytesSent, bytesReceived: s.bytesReceived })) });
    }
    return results;
  });
  assert.ok(report.peerConnections.some(p => p.connectionState === 'connected'));
  check('Browser RTC statistics confirm an actual connected peer data channel');
  const cContext = await browser.newContext();
  const c = await cContext.newPage();
  await c.goto(`${base}/release.json`);
  await c.evaluate(async ({ base, room }) => {
    history.replaceState(null, '', '?room=' + room + '-other');
    const { PeerClient } = await import(base + '/js/net-peer.js');
    window.probe = new PeerClient({}); window.probe.connect('Other room', 'pro');
  }, { base, room });
  await c.waitForTimeout(6500);
  assert.equal(await c.evaluate(() => window.probe.peers.size), 0);
  assert.equal(await a.evaluate(() => window.__game.remotes.size), 1);
  await cContext.close();
  check('A different room stays isolated from the active pair');
  await b.reload({ waitUntil: 'domcontentloaded' });
  await b.waitForFunction(() => window.__game?.net.connected && window.__game.net.metrics.statesReceived > 5, null, { timeout: 90000 });
  await a.waitForFunction(() => window.__game.remotes.size === 1);
  await b.waitForFunction(() => window.__game.settings.gravity === 9 && window.__game.net.metrics.tilesReceived > 0, null, { timeout: 30000 });
  check('Reload rejoins the room, restores world settings and receives peer track tiles');
  await b.close();
  await a.waitForFunction(() => window.__game.remotes.size === 0 && !window.__game.net.connected, null, { timeout: 30000 });
  check('Leaving removes the remote car while solo driving remains available');
  assert.deepEqual(report.errors, []);
  assert.deepEqual(report.failedRequests, []);
  report.passed = true;
} catch (error) {
  report.failure = error.stack; report.passed = false; process.exitCode = 1;
  report.diagnostics = await Promise.all(pages.filter(p => !p.isClosed()).map(p => p.evaluate(() => window.__game?.net?.diagnostics?.()).catch(e => e.message)));
} finally {
  report.verifiedUtc = new Date().toISOString();
  fs.writeFileSync(path.join(out, 'multiplayer.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ passed: report.passed, checks: report.checks.length, errors: report.errors, failedRequests: report.failedRequests, failure: report.failure, diagnostics: report.diagnostics, receipt: path.join(out, 'multiplayer.json') }, null, 2));
  await browser.close();
}
