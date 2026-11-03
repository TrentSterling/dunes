// Package only browser files. Node multiplayer, saved tracks and authoring files stay local.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import './build-network.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'artifacts', 'pages', 'dunes');
// Fixed output inside this checkout; never accept a caller-supplied deletion target.
if (path.relative(root, out) !== path.join('artifacts', 'pages', 'dunes')) throw new Error('Unsafe output path');
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out, { recursive: true });
fs.cpSync(path.join(root, 'public'), out, { recursive: true });
fs.cpSync(path.join(root, 'assets'), path.join(out, 'assets'), {
  recursive: true,
  filter: source => !path.relative(path.join(root, 'assets'), source).split(path.sep).some(part => part.startsWith('_backup_')),
});
fs.writeFileSync(path.join(out, 'js', 'runtime-config.js'), 'export const STATIC_HOSTING = true;\n');
const audio = fs.readdirSync(path.join(out, 'assets', 'audio')).filter(name => /\.(mp3|ogg|wav|m4a)$/i.test(name)).sort();
fs.writeFileSync(path.join(out, 'assets', 'audio', 'index.json'), JSON.stringify(audio) + '\n');
fs.copyFileSync(path.join(root, 'UNLICENSE'), path.join(out, 'UNLICENSE'));
fs.writeFileSync(path.join(out, '.nojekyll'), '');
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
fs.writeFileSync(path.join(out, 'release.json'), JSON.stringify({ name: pkg.name, version: pkg.version, mode: 'trystero-p2p', commit: process.env.GITHUB_SHA || null }, null, 2) + '\n');
console.log(`Built Dunes ${pkg.version}: ${out}`);
