"""Cycles check renders of the driver arms inside the car (cockpit view + close-ups).

    python arms/render_arms.py [--car out/trx_sandrail.blend] [--arms out/part_arms.blend]
        [--open 0..1] [--samples 10] [--tag arms_]
Writes renders/<tag>cockpit.png, <tag>hand_l.png, <tag>hand_r.png and <tag>sheet.png.
"""
import argparse, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import bpy
from mathutils import Vector as V
import render as R
import spec

ap = argparse.ArgumentParser()
ap.add_argument('--car', default=os.path.join(ROOT, 'out', 'trx_sandrail.blend'))
ap.add_argument('--arms', default=os.path.join(ROOT, 'out', 'part_arms.blend'))
ap.add_argument('--open', type=float, default=0.0)
ap.add_argument('--samples', type=int, default=10)
ap.add_argument('--width', type=int, default=720)
ap.add_argument('--tag', default='arms_')
ap.add_argument('--only-wheel', action='store_true')
ap.add_argument('--views', default='cockpit,hand_l,hand_r,front')
args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
bpy.ops.wm.open_mainfile(filepath=args.car)
with bpy.data.libraries.load(args.arms) as (src, dst):
    dst.objects = [n for n in src.objects if n.startswith(('DriverArms', 'DriverRig', 'DriverLegs'))]
for o in dst.objects:
    bpy.context.scene.collection.objects.link(o)
arms = bpy.data.objects['DriverArms']
if arms.data.shape_keys:
    for k in ('OpenL', 'OpenR'):
        arms.data.shape_keys.key_blocks[k].value = args.open
if args.only_wheel:
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name not in ('SteeringWheel_Mesh', 'DriverArms'):
            o.hide_render = True
R.setup_world()
sc = bpy.context.scene
sc.cycles.samples = args.samples
sc.render.threads_mode = 'FIXED'; sc.render.threads = 3
# the cabin needs a bit more light than the studio set gives
outs = []
CLIP = {'legs_side': 0.62, 'legs_front': 0.02}   # cut away the door skin / the dash in front of the camera
def shot(name, loc, tgt, lens):
    R.VIEWS['_tmp'] = (loc, tgt, lens, (16, 9), None)
    R.camera('_tmp', args.width)
    sc.camera.data.clip_start = CLIP.get(name, 0.02)
    out = os.path.join(ROOT, 'renders', f'{args.tag}{name}.png')
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    outs.append(out)
e = V(spec.DRIVER_EYE); c = V(spec.STEERING_WHEEL_CENTRE)
VV = {
 'cockpit': (tuple(e), (e.x, e.y + 10, e.z - 1.0), 0),
 'hand_l': ((c.x - 0.45, c.y - 0.35, c.z + 0.30), (c.x - 0.15, c.y, c.z + 0.05), 35),
 'hand_r': ((c.x + 0.35, c.y - 0.45, c.z + 0.25), (c.x + 0.12, c.y, c.z + 0.05), 35),
 'front': ((c.x - 0.05, c.y + 0.75, c.z + 0.25), (c.x, c.y, c.z), 30),
 'eye_l': ((e.x, e.y, e.z), (c.x - 0.16, c.y, c.z + 0.08), 45),
 'glove_out': ((c.x - 0.55, c.y + 0.10, c.z + 0.25), (c.x - 0.16, c.y, c.z + 0.08), 50),
 'glove_top': ((c.x - 0.25, c.y + 0.05, c.z + 0.45), (c.x - 0.16, c.y, c.z + 0.08), 50),
 'glove_in': ((c.x + 0.10, c.y + 0.25, c.z + 0.05), (c.x - 0.16, c.y, c.z + 0.08), 45),
 # legs (r4): the lap and footwell from the eye, and from the open door side
 'legs_down': (tuple(e), (e.x, e.y + 0.9, 0.55), 0),
 'legs_side': ((-1.25, 0.20, 0.80), (-0.40, 0.25, 0.64), 24),
 'legs_front': ((-0.20, 0.66, 0.66), (-0.40, 0.05, 0.66), 22),
}
for v in args.views.split(','):
    shot(v, *VV[v])
from PIL import Image
ims = [Image.open(o).convert('RGB') for o in outs]
W = ims[0].width
sheet = Image.new('RGB', (W * 2, ims[0].height * 2))
for i, im in enumerate(ims):
    sheet.paste(im.resize((W, ims[0].height)), ((i % 2) * W, (i // 2) * ims[0].height))
sheet.save(os.path.join(ROOT, 'renders', f'{args.tag}sheet.png'))
print('sheet', os.path.join(ROOT, 'renders', f'{args.tag}sheet.png'))
