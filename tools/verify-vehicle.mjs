// Verify the regenerated asset in the actual game using isolated, headless Chrome.
import { chromium } from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = process.env.DUNES_OUTPUT || path.join(root, 'artifacts/vehicles/glx-pro');
fs.mkdirSync(out, { recursive: true });
const bundled = process.argv.includes('--bundled');
const glb = path.join(root, 'artifacts/vehicles/glx-pro/sandcar.glb');
if (!bundled) assert.ok(fs.existsSync(glb), 'Run npm run vehicle:build first');
const base = process.env.DUNES_URL || 'http://127.0.0.1:5189';
const browser = await chromium.launch({ channel: 'chrome', headless: true,
  args: ['--ignore-gpu-blocklist'] });
const errors = [], warnings = [], failures = [];
const report = { asset: bundled ? 'bundled upstream' : glb, checks: [], errors, warnings, failures };
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript(() => localStorage.setItem('glamis-settings-v1', JSON.stringify({
    car: 'pro', proCarV: 1, showHelp: false, camMode: 0, aiCount: 0,
  })));
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => {
    if (m.type() === 'error') errors.push(m.text());
    if (m.type() === 'warning') warnings.push(m.text());
  });
  page.on('response', r => { if (r.status() >= 400) failures.push(`${r.status()} ${r.url()}`); });
  page.on('requestfailed', r => failures.push(`${r.failure()?.errorText} ${r.url()}`));
  if (!bundled) {
    await page.route('**/assets/pro_sandrail/sandcar.glb', r => r.fulfill({ path: glb, contentType: 'model/gltf-binary' }));
    await page.route('**/assets/pro_sandrail/sandcar.physics.json', r => r.fulfill({
      path: glb.replace(/\.glb$/, '.physics.json'), contentType: 'application/json',
    }));
  }
  await page.goto(`${base}/?q=high&shot&tod=15&room=verify-vehicle-${Date.now()}`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => window.__frames > 10 && window.__game?.model?.wheelRigs?.length === 4,
    null, { timeout: 120000 });
  const waitFrames = async n => {
    const target = await page.evaluate(n => window.__frames + n, n);
    await page.waitForFunction(t => window.__frames >= t, target, { timeout: 60000 });
  };
  report.model = await page.evaluate(() => {
    const g = window.__game, gl = g.renderer.getContext();
    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
    let meshes = 0, triangles = 0;
    g.model.model.traverse(o => {
      if (!o.isMesh) return;
      meshes++;
      triangles += (o.geometry.index?.count || o.geometry.attributes.position.count) / 3;
    });
    return { car: g.settings.car, wheelRigs: g.model.wheelRigs.length,
      uprights: g.model.uprights.length, movingSegments: g.model.segs.length,
      meshes, triangles, renderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
      driverEye: g.model.eye.toArray(), steeringWheel: !!g.model.steeringWheel };
  });
  assert.equal(report.model.car, 'pro');
  assert.equal(report.model.wheelRigs, 4);
  assert.equal(report.model.uprights, 4);
  assert.ok(report.model.movingSegments >= 20);
  assert.ok(report.model.steeringWheel);
  report.checks.push('Loaded GLX pro with four wheels, four uprights, steering wheel and suspension rig');
  await page.evaluate(() => {
    const g = window.__game;
    g.setSetting('aiCount', 0); g.setSetting('showHelp', false);
    g.setOrbit(Math.PI * 0.78, 0.12, 0.62);
  });
  await waitFrames(15);
  await page.screenshot({ path: path.join(out, 'game-front.png') });
  await page.evaluate(() => {
    const g = window.__game;
    g.setSetting('camMode', 2); g.setOrbit(0, 0, 1);
  });
  await waitFrames(15);
  await page.screenshot({ path: path.join(out, 'game-cockpit.png') });
  report.checks.push('Rendered exterior and live cockpit');
  const pose = () => page.evaluate(() => {
    const g = window.__game;
    return { position: g.car.pos.toArray(), speed: g.car.forwardSpeed,
      wheel: g.model.wheelRigs[0].node.quaternion.toArray(),
      steering: g.model.steeringWheel.quaternion.toArray(),
      wheelHeights: g.model.wheelRigs.map(w => w.node.position.y) };
  });
  report.before = await pose();
  await page.keyboard.down('KeyA');
  await waitFrames(20);
  report.steered = await pose();
  await page.keyboard.up('KeyA');
  assert.ok(report.before.steering.some((v, i) => Math.abs(v - report.steered.steering[i]) > 0.01));
  report.checks.push('Keyboard steering visibly changes the steering-wheel transform');
  await page.evaluate(() => { window.__game.setSetting('camMode', 0); window.__game.setOrbit(0, 0.12, 0.75); });
  await page.keyboard.down('KeyW');
  await waitFrames(180);
  await page.keyboard.up('KeyW');
  report.after = await pose();
  report.distanceMetres = Math.hypot(...report.after.position.map((v, i) => v - report.before.position[i]));
  assert.ok(report.after.position.every(Number.isFinite));
  assert.ok(report.distanceMetres > 2, 'Vehicle should move under throttle');
  assert.ok(report.before.wheel.some((v, i) => Math.abs(v - report.after.wheel[i]) > 0.01));
  assert.ok(report.before.wheelHeights.some((v, i) => Math.abs(v - report.after.wheelHeights[i]) > 0.001));
  report.checks.push('Keyboard throttle moves the vehicle; wheels rotate and suspension height changes');
  await page.screenshot({ path: path.join(out, 'game-driving.png') });
  assert.deepEqual(errors, [], 'No browser/runtime errors');
  assert.deepEqual(failures, [], 'No missing or failed resources');
  report.checks.push('No browser errors or failed HTTP resources');
  report.passed = true;
} catch (error) {
  report.passed = false;
  report.failure = error.stack;
  process.exitCode = 1;
} finally {
  report.verifiedUtc = new Date().toISOString();
  fs.writeFileSync(path.join(out, 'browser-receipt.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
  await browser.close();
}
