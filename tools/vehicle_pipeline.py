"""Local Blender build, inspection renders and export checks for Dunes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'blender' / 'trx_pro'
OUTPUT = ROOT / 'artifacts' / 'vehicles' / 'glx-pro'
DEPS = ROOT / '.tools' / 'blender-python'


def blender_path(explicit):
    candidate = explicit or os.environ.get('BLENDER') or shutil.which('blender')
    if candidate:
        return Path(candidate).resolve()
    installed = sorted(Path(os.environ.get('ProgramFiles', 'C:/Program Files')).glob(
        'Blender Foundation/Blender */blender.exe'))
    preferred = [p for p in installed if p.parent.name == 'Blender 4.5']
    if preferred or installed:
        return (preferred or installed)[-1]
    raise RuntimeError('Blender was not found. Set BLENDER to its executable path.')


def run_blender(blender, script, args, log_name):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    log = OUTPUT / log_name
    command = [str(blender), '--background', '--factory-startup', '--python-exit-code', '1',
               '--python-expr', 'import sys; sys.path.insert(0, ' + repr(str(DEPS)) + ')',
               '--python', str(script), '--', *map(str, args)]
    start = time.monotonic()
    print('Running', script.name, '| log:', log, flush=True)
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run(command, cwd=SOURCE, stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        print('\n'.join(log.read_text(encoding='utf-8', errors='replace').splitlines()[-40:]))
        raise RuntimeError(f'Blender failed with exit code {result.returncode}; see {log}')
    print(f'Completed in {time.monotonic() - start:.1f}s', flush=True)
    return log


def inspect_export():
    glb = OUTPUT / 'sandcar.glb'
    data = glb.read_bytes()
    magic, version, length = struct.unpack_from('<4sII', data)
    if (magic, version, length) != (b'glTF', 2, len(data)):
        raise RuntimeError('Invalid GLB header')
    size, kind = struct.unpack_from('<II', data, 12)
    if kind != 0x4E4F534A:
        raise RuntimeError('GLB has no leading JSON chunk')
    model = json.loads(data[20:20 + size])
    physics = json.loads((OUTPUT / 'sandcar.physics.json').read_text())
    names = {node.get('name') for node in model['nodes']}
    required = {'Sandcar', 'Chassis', 'Chassis_Mesh', 'SteeringWheel', 'DriverEye'}
    required |= {'Wheel_' + corner for corner in ('FL', 'FR', 'RL', 'RR')}
    required |= {entry['node'] for key in ('wheels', 'links', 'shocks') for entry in physics[key]}
    missing = required - names
    if missing:
        raise RuntimeError('Missing rig nodes: ' + ', '.join(sorted(missing)))
    if len(physics['wheels']) != 4 or not physics['links'] or not physics['shocks']:
        raise RuntimeError('Incomplete wheel/suspension metadata')
    triangles = sum(model['accessors'][primitive['indices']]['count'] // 3
                    for mesh in model['meshes'] for primitive in mesh['primitives']
                    if primitive.get('mode', 4) == 4 and 'indices' in primitive)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    receipt = {
        'verifiedUtc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Generated GLB structure and rig references; visual quality requires rendered inspection.',
        'glbBytes': len(data), 'glbSha256': sha(glb),
        'blendSha256': sha(OUTPUT / 'sandrail.blend'),
        'physicsSha256': sha(OUTPUT / 'sandcar.physics.json'),
        'nodes': len(model['nodes']), 'meshes': len(model['meshes']),
        'materials': len(model.get('materials', [])), 'triangles': triangles,
        'wheels': len(physics['wheels']), 'links': len(physics['links']),
        'shocks': len(physics['shocks']), 'requiredNodesPresent': True,
        'ambientOcclusionBaked': any('_AO' in p.get('attributes', {})
            for m in model['meshes'] for p in m['primitives']),
        'sourceHashes': {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p)
            for p in [SOURCE / 'build.py', SOURCE / 'common.py', SOURCE / 'spec.py',
                      *sorted((SOURCE / 'parts').glob('*.py'))]},
    }
    (OUTPUT / 'build-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'sourceHashes'}, indent=2))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['setup', 'build', 'render', 'bake', 'check', 'suspension'])
    parser.add_argument('--blender', help='Override Blender executable (or set BLENDER)')
    parser.add_argument('--only', help='Build selected comma-separated parts into an inspection .blend')
    parser.add_argument('--views', default='front_3q_right,side_right,rear_3q_right,interior_dash')
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--samples', type=int, default=32)
    parser.add_argument('--threads', type=int, default=8)
    args = parser.parse_args()
    if args.action == 'suspension':
        env = os.environ.copy()
        if args.blender:
            env['BLENDER'] = str(Path(args.blender).resolve())
        subprocess.run([sys.executable, str(ROOT / 'tools' / 'build-suspension-shocks.py')],
                       env=env, check=True)
        return
    if args.action == 'check':
        inspect_export()
        return
    blender = blender_path(args.blender)
    if not blender.is_file():
        raise RuntimeError(f'Blender executable does not exist: {blender}')
    if args.action == 'setup':
        interpreters = sorted(blender.parent.glob('*/python/bin/python.exe'))
        if not interpreters:
            raise RuntimeError('No bundled Windows Python found. Install Pillow for this Blender manually.')
        subprocess.run([str(interpreters[-1]), '-m', 'pip', 'install', '--disable-pip-version-check',
                        '--no-cache-dir', '--target', str(DEPS), 'pillow==12.1.0'], check=True)
        return
    if not (DEPS / 'PIL' / 'Image.py').is_file():
        raise RuntimeError('Local Pillow missing or unreadable. Run npm run vehicle:setup first.')
    if args.action == 'build':
        # Part builders repaint textures in place. Stage their inputs so a build does
        # not silently modify the checked-in upstream artwork. The .blend packs them.
        staged = OUTPUT / 'source'
        shutil.copytree(SOURCE, staged, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('out', 'renders', 'ref', '__pycache__'))
        if args.only:
            parts = sorted(set(args.only.split(',')))
            valid = {p.stem for p in (SOURCE / 'parts').glob('*.py')}
            if not set(parts) <= valid:
                raise RuntimeError('Unknown part; available: ' + ', '.join(sorted(valid)))
            target = OUTPUT / 'parts' / ('_'.join(parts) + '.blend')
            run_blender(blender, staged / 'build.py',
                        ['--strict', '--only', ','.join(parts), '--no-export', '--blend', target],
                        'parts-build.log')
            print('Inspection scene:', target)
        else:
            run_blender(blender, staged / 'build.py',
                        ['--strict', '--blend', OUTPUT / 'sandrail.blend', '--glb', OUTPUT / 'sandcar.glb'],
                        'build.log')
            inspect_export()
    elif args.action == 'render':
        run_blender(blender, SOURCE / 'tools' / 'render.py',
                    ['--blend', OUTPUT / 'sandrail.blend', '--views', args.views,
                     '--width', args.width, '--samples', args.samples, '--threads', args.threads,
                     '--tag', 'dunes_', '--no-overlay'], 'render.log')
        print('Renders:', SOURCE / 'renders')
    elif args.action == 'bake':
        run_blender(blender, SOURCE / 'tools' / 'bake_ao.py',
                    ['--blend', OUTPUT / 'sandrail.blend', '--glb', OUTPUT / 'sandcar.glb'], 'bake.log')
        inspect_export()


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
