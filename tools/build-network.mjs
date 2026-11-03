import { build } from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
await build({
  entryPoints: [path.join(root, 'tools/trystero-entry.mjs')],
  outfile: path.join(root, 'public/vendor/trystero.js'),
  bundle: true, format: 'esm', platform: 'browser', target: 'es2022', minify: true,
  legalComments: 'inline', banner: { js: '// Trystero 0.26.0. See TRYSTERO-LICENSES.txt. Rebuild: npm run build:net' },
});
const packages = ['trystero', '@trystero-p2p/nostr', '@trystero-p2p/core', '@noble/secp256k1'];
const licenses = packages.map(name => {
  const dir = path.join(root, 'node_modules', name);
  const license = fs.readdirSync(dir).find(file => /^license(?:\.md|\.txt)?$/i.test(file));
  if (!license) throw new Error(`Missing license: ${name}`);
  return `${name}\n${fs.readFileSync(path.join(dir, license), 'utf8')}`;
});
fs.writeFileSync(path.join(root, 'public/vendor/TRYSTERO-LICENSES.txt'), licenses.join('\n\n'));
console.log('Bundled Trystero 0.26.0 and dependency licenses');
