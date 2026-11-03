"""Export the existing authored shock parts separately for the inspection rig.

Run with system Python. Source artwork is staged by vehicle_pipeline; only the
eight shock assemblies are exported. The baked car itself is copied unchanged.
"""
from pathlib import Path
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets' / 'suspension'

if '--inside-blender' not in sys.argv:
    from vehicle_pipeline import blender_path, SOURCE, OUTPUT, DEPS
    staged = OUTPUT / 'source'
    shutil.copytree(SOURCE, staged, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('out', 'renders', 'ref', '__pycache__'))
    OUT.mkdir(parents=True, exist_ok=True)
    command = [str(blender_path(None)), '--background', '--threads', '8',
               '--python-exit-code', '1', '--python', str(Path(__file__).resolve()),
               '--', '--inside-blender', str(staged), str(DEPS)]
    log = OUTPUT / 'suspension-shocks-build.log'
    with log.open('w') as f:
        subprocess.run(command, stdout=f, stderr=subprocess.STDOUT, check=True)
    for name in ['sandcar.glb', 'sandcar.physics.json']:
        shutil.copy2(OUTPUT / name, OUT / name)
    print('Exported split shock components and copied the rebuilt car:', OUT)
    sys.exit(0)

import bpy
from mathutils import Vector
staged, deps = sys.argv[-2:]
sys.path[:0] = [staged, str(Path(staged) / 'parts'), deps]
import common
import suspension
common.reset_scene()
context = common.BuildContext()
suspension.build(context)
keep = set()
parts = []
convert = lambda p: [p.x, p.z, -p.y]
for name, segment in context.segments.items():
    if not segment['shock']:
        continue
    top, bottom = Vector(segment['a']), Vector(segment['b'])
    axis = (top - bottom).normalized()
    length = (top - bottom).length
    objects = context.groups[name]
    spring_points = []
    for obj in objects:
        if '_main' in obj.name or '_tender' in obj.name:
            spring_points.extend((common.world_matrix(obj) @ v.co - bottom).dot(axis) for v in obj.data.vertices)
    spring_min = min(spring_points) if spring_points else 0
    spring_max = max(spring_points) if spring_points else length
    for i, obj in enumerate(objects):
        source_name = obj.name
        common.apply_transform(obj)
        axial = [(v.co - bottom).dot(axis) for v in obj.data.vertices]
        center = (min(axial) + max(axial)) / 2
        if '_main' in source_name or '_tender' in source_name:
            kind = 'spring'
        elif '_slider' in source_name:
            kind = 'slider'
        elif '_shaft' in source_name:
            kind = 'shaft'
        elif any(t in source_name for t in ['_boss', '_seat_lo', '_bump', '_lowcap']):
            kind = 'bottom'
        elif ('_eye' in source_name or '_brg' in source_name) and center < length / 2:
            kind = 'bottom'
        else:
            kind = 'top'
        obj.name = f'{name}__{i:02d}'
        keep.add(obj)
        parts.append(dict(node=obj.name, shock=name, kind=kind, source=source_name,
                          top=convert(top), bottom=convert(bottom), length=length,
                          springMin=spring_min, springMax=spring_max, axialCenter=center,
                          axialMin=min(axial), axialMax=max(axial)))
for obj in list(bpy.data.objects):
    if obj not in keep:
        bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'artifacts/vehicles/glx-pro/suspension-shocks.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT / 'shocks.glb'), export_format='GLB',
                          export_yup=True, export_apply=True, export_animations=False)
(OUT / 'shocks.json').write_text(json.dumps(parts, indent=2) + '\n')
print('Split shock export:', len(parts), 'parts')
