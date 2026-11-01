"""Assemble the GLX sandrail from parts/*.py and export the game asset.

    python build.py [--only part1,part2] [--no-export] [--blend out/trx.blend] [--glb out/x.glb]

Writes out/sandcar.glb, out/sandcar.physics.json and out/trx_sandrail.blend.
The node names and physics.json layout follow the game's 'sandcar' family contract
(public/js/gltf-sandrail.js): Wheel_XX (empty at the wheel centre) > Wheel_XX_Mesh,
Upright_XX, Link_*/TieRod_*/Halfshaft_*/Shock_* (origin at mid-span, local Z along the
member so the game can re-aim and stretch them), SteeringWheel (local Z = column axis
toward the driver) > SteeringWheel_Mesh, Chassis > Chassis_Mesh, DriverEye, PassengerEye.
"""
import argparse
import importlib
import json
import math
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'parts'))

import bpy  # noqa: E402
from mathutils import Vector, Matrix  # noqa: E402
import common  # noqa: E402
from common import BuildContext, join, apply_transform, collection, link  # noqa: E402
import spec  # noqa: E402

V = Vector


def gl(p):
    """Blender (x right, y fwd, z up) -> glTF (x right, y up, -z fwd)."""
    return [round(p[0], 4), round(p[2], 4), round(-p[1], 4)]


def empty(name, loc=(0, 0, 0), parent=None, coll=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.1
    e.location = loc
    (coll or bpy.context.scene.collection).objects.link(e)
    if parent:
        e.parent = parent
    return e


def aligned_matrix(origin, zdir):
    """World matrix with origin and local +Z along zdir (X kept as horizontal as possible)."""
    z = V(zdir).normalized()
    ref = V((1, 0, 0)) if abs(z.x) < 0.9 else V((0, 1, 0))
    x = (ref - z * ref.dot(z)).normalized()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = V(origin)
    return m


def set_object_frame(o, mw):
    """Keep the mesh where it is in the world but give the object the world matrix mw."""
    apply_transform(o)
    o.data.transform(mw.inverted())
    o.matrix_basis = mw


def discover_parts(only=None):
    names = sorted(f[:-3] for f in os.listdir(os.path.join(ROOT, 'parts')) if f.endswith('.py'))
    if only:
        return [n for n in names if n in only]
    return [n for n in names if not n.startswith('_')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--skip', default='')
    ap.add_argument('--no-export', action='store_true')
    ap.add_argument('--strict', action='store_true', help='stop on the first part error')
    ap.add_argument('--blend', default=None,
                    help='default: out/trx_sandrail.blend for an export build, out/part_<only>.blend with --no-export')
    ap.add_argument('--glb', default=os.path.join(ROOT, 'out', 'sandcar.glb'))
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])

    common.reset_scene()
    C = BuildContext()
    only = set(filter(None, args.only.split(',')))
    if args.blend is None:
        # [integration r4] a test build (--no-export) without --blend used to overwrite the full
        # out/trx_sandrail.blend with a partial scene; it now goes to out/part_<only>.blend.
        if args.no_export:
            tagname = '_'.join(sorted(only)) if only else 'all'
            args.blend = os.path.join(ROOT, 'out', 'part_%s.blend' % tagname)
        else:
            args.blend = os.path.join(ROOT, 'out', 'trx_sandrail.blend')
    skip = set(filter(None, args.skip.split(',')))
    errors = {}
    for name in discover_parts(only):
        if name in skip:
            continue
        try:
            mod = importlib.import_module(name)
            before = {k: len(v) for k, v in C.groups.items()}
            mod.build(C)
            added = sum(len(v) - before.get(k, 0) for k, v in C.groups.items())
            print(f'[part] {name}: {added} objects')
        except Exception:
            errors[name] = traceback.format_exc()
            print(f'[part] {name} FAILED\n{errors[name]}')
            if args.strict:
                raise

    assemble(C)
    # [integration r2] test builds (--no-export, usually --only <part>) used to overwrite the real
    # out/sandcar.physics.json with a partial one (0 links); they now write it next to their .blend.
    if args.no_export:
        phys = os.path.splitext(args.blend)[0] + '.physics.json'
    else:
        # [integration r4] named after the GLB (x.glb -> x.physics.json), the pairing tools/game_shots.mjs and
        # the game loader use; --glb out/part_x.glb used to overwrite out/sandcar.physics.json.
        phys = os.path.splitext(args.glb)[0] + '.physics.json'
    write_physics(C, phys)
    os.makedirs(os.path.dirname(args.blend), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.blend, compress=True)
    if not args.no_export:
        export_glb(args.glb)
    stats()
    if errors:
        print('PART ERRORS:', ', '.join(errors))
        sys.exit(2)


def assemble(C):
    coll = collection('TRX_Sandrail')
    root = empty('Sandcar', coll=coll)
    groups = C.groups

    # static frame, body, engine, interior -> one mesh with many materials
    chassis = empty('Chassis', parent=root, coll=coll)
    static = join(groups.get('static', []), 'Chassis_Mesh')
    if static:
        link(static, coll); static.parent = chassis

    # wheels: empty at the centre, joined spinning mesh under it
    for c, (x, y, z, r, w, front) in spec.WHEELS.items():
        we = empty('Wheel_' + c, (x, y, z), parent=root, coll=coll)
        objs = groups.get('Wheel_' + c, [])
        if objs:
            m = join(objs, 'Wheel_%s_Mesh' % c)
            link(m, coll)
            m.data.transform(Matrix.Translation((-x, -y, -z)))
            m.parent = we
            m.location = (0, 0, 0)
        up = groups.get('Upright_' + c, [])
        if up:
            u = join(up, 'Upright_' + c)
            link(u, coll)
            set_object_frame(u, Matrix.Translation((x, y, z)))
            u.parent = root

    # moving suspension members: origin at mid-span, local Z along a->b
    for name, s in C.segments.items():
        objs = groups.get(name, [])
        if not objs:
            continue
        m = join(objs, name)
        link(m, coll)
        a, b = V(s['a']), V(s['b'])
        set_object_frame(m, aligned_matrix((a + b) / 2, b - a))
        m.parent = root

    # steering wheel: local Z = column axis toward the driver
    sw = groups.get('SteeringWheel', [])
    if sw:
        e = empty('SteeringWheel', parent=root, coll=coll)
        e.matrix_basis = aligned_matrix(spec.STEERING_WHEEL_CENTRE, spec.STEERING_COLUMN_DIR)
        m = join(sw, 'SteeringWheel_Mesh')
        link(m, coll)
        m.data.transform(e.matrix_basis.inverted())
        m.parent = e
        m.matrix_parent_inverse = Matrix.Identity(4)
        m.matrix_basis = Matrix.Identity(4)

    lb = groups.get('LightBar', [])
    if lb:
        m = join(lb, 'LightBar')
        link(m, coll)
        cen = sum((V(v.co) for v in m.data.vertices), V()) / max(1, len(m.data.vertices))
        set_object_frame(m, Matrix.Translation(cen))
        m.parent = root

    # any other named groups (e.g. 'Needle_Speed') become their own nodes
    known = {'static', 'SteeringWheel', 'LightBar'} | set(C.segments) | {'Wheel_' + c for c in spec.WHEELS} | {'Upright_' + c for c in spec.WHEELS}
    for g, objs in groups.items():
        if g in known or not objs:
            continue
        m = join(objs, g)
        link(m, coll)
        cen = sum((V(v.co) for v in m.data.vertices), V()) / max(1, len(m.data.vertices))
        set_object_frame(m, Matrix.Translation(cen))
        m.parent = root

    empty('DriverEye', spec.DRIVER_EYE, parent=root, coll=coll)
    empty('PassengerEye', spec.PASSENGER_EYE, parent=root, coll=coll)
    empty('CenterOfMass', (0, -0.35, 0.62), parent=root, coll=coll)
    empty('CameraChase', (0, -6.6, 2.8), parent=root, coll=coll)
    for name, p in C.points.items():
        empty(name, p, parent=root, coll=coll)

    # anything left loose in the scene root (helpers) is removed
    for o in list(bpy.context.scene.collection.objects):
        bpy.data.objects.remove(o)


def write_physics(C, path):
    wheels = []
    for c, (x, y, z, r, w, front) in spec.WHEELS.items():
        wheels.append({'name': c, 'node': 'Wheel_' + c, 'center': gl((x, y, z)), 'radius': r, 'width': w,
                       'steer': front, 'drive': not front, 'rest_length': 0.55, 'travel': spec.BUMP + spec.DROOP})
    links, shocks = [], []
    for name, s in C.segments.items():
        (shocks if s['shock'] else links).append({'node': name, 'wheel': s['wheel'], 'a': gl(s['a']), 'b': gl(s['b'])})
    data = {
        'units': 'meters', 'coordinates': 'glTF: +X right, +Y up, -Z forward', 'name': 'GLX pro sandrail',
        'mass_kg': 1250, 'wheelbase_m': spec.WHEELBASE,
        'inertia_box': {'height': 1.4, 'length': spec.NOSE_Y - spec.TAIL_Y, 'width': spec.BODY_WIDTH + 0.4},
        'bump_m': spec.BUMP, 'droop_m': spec.DROOP, 'engine_torque_nm': 1400,
        'wheels': wheels, 'links': links, 'shocks': shocks,
        'driver_eye': gl(spec.DRIVER_EYE), 'center_of_mass': gl((0, -0.35, 0.62)),
        'light_bar': True,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=1)
    print('wrote', path, len(links), 'links', len(shocks), 'shocks')


def export_glb(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    kw = dict(filepath=path, export_format='GLB', export_apply=True, export_yup=True,
              export_texcoords=True, export_normals=True, export_materials='EXPORT',
              export_cameras=False, export_lights=False, export_extras=False, export_animations=False)
    # JPEG keeps the GLB under the 25 MB budget (PNG livery atlases alone were ~8 MB); the exporter
    # still writes PNG for any texture wired to an Alpha socket (hex mesh), so cut-outs survive.
    try:
        bpy.ops.export_scene.gltf(**kw, export_image_format='JPEG', export_image_quality=90, export_jpeg_quality=90)
    except TypeError:
        bpy.ops.export_scene.gltf(**kw, export_image_format='JPEG')
    print('exported', path, os.path.getsize(path) // 1024, 'KB')


def stats():
    tris = 0
    for o in bpy.data.objects:
        if o.type == 'MESH':
            o.data.calc_loop_triangles()
            tris += len(o.data.loop_triangles)
    print('objects', len(bpy.data.objects), 'materials', len(bpy.data.materials), 'triangles', tris)


if __name__ == '__main__':
    main()
