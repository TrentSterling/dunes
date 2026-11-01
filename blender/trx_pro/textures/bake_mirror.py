"""Bake the mirror reflections (textures/mirror_rear_view.png, textures/mirror_side_view.png) with Cycles.

    python textures/bake_mirror.py --blend out/part_textures_all.blend [--samples 48]
        [--only rear,side] [--threads 0]

Opens a full-car build, adds a desert (sky gradient world, sun, sand floor with dunes further out) and renders
from the VIRTUAL eye of each mirror: spec.DRIVER_EYE reflected in the mirror plane, looking through the mirror,
with the car geometry on the camera side of the glass deleted (so the cowl, dash and the mirror housing in front
of the glass do not show). Mapped with:
    panoramic mirror (M('mirror_baked')):      u = 0 at the car-LEFT end of the glass (x = -0.225), v = 0 bottom
    door mirror (M('mirror_baked_side')):      u = 0 at the glass's INNER end, v = 0 bottom (as body.py maps it;
                                               painted for the driver's LEFT mirror, the mirror_x copy on the right
                                               reads right too). Rendered from the eye reflected in body.py's aimed
                                               glass (mirror_frame()), so the driver looks straight back along the
                                               flank; 22 deg fov, aimed 5 deg outboard.
The panoramic view is rendered 1024 x 320 with a 74 deg horizontal fov and squashed to 1024 x 160, like the
wide convex glass of a real panoramic mirror. Nothing here edits the blend on disk.
"""
import argparse
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy  # noqa: E402
from mathutils import Vector, Matrix  # noqa: E402
import numpy as np  # noqa: E402
import spec  # noqa: E402

V = Vector
TEX = os.path.join(ROOT, 'textures')

# panoramic mirror: body.py build_rearview (centre, pitch 8 deg down, yaw 5 deg toward the driver)
REAR_C = V((0.0, 0.405, 1.372))
REAR_ROT = Matrix.Rotation(math.radians(-5.0), 3, 'Z') @ Matrix.Rotation(math.radians(8.0), 3, 'X')
# door mirror glass (left): body.py build_mirrors - flat glass facing -y at y ~0.6375, centre x ~-0.85, z ~1.19
SIDE_C = V((-0.852, 0.6375, 1.188))


def reflect(p, c, n):
    return p - 2.0 * (p - c).dot(n) * n


def setup_world(strength=1.0):
    sc = bpy.context.scene
    w = bpy.data.worlds.new('MirrorBakeSky')
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    nt.links.new(sep.outputs['Z'], ramp.inputs['Fac'])
    cr = ramp.color_ramp
    # world 'Generated' z = direction z (-1..1); the ramp clamps it to 0..1 (the sand floor covers z < 0)
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0.80, 0.86, 0.93, 1)        # pale hazy horizon
    cr.elements[1].position = 1.0
    cr.elements[1].color = (0.16, 0.33, 0.75, 1)        # deep blue zenith
    e = cr.elements.new(0.14)
    e.color = (0.45, 0.62, 0.88, 1)
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = strength
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])


def add_sun():
    ld = bpy.data.lights.new('MirrorBakeSun', 'SUN')
    ld.energy = 4.5
    ld.angle = math.radians(1.0)
    ld.color = (1.0, 0.96, 0.9)
    o = bpy.data.objects.new('MirrorBakeSun', ld)
    bpy.context.scene.collection.objects.link(o)
    # high afternoon sun from behind-left so the cockpit and the seat backs catch light
    o.rotation_euler = (math.radians(38.0), 0.0, math.radians(160.0))
    return o


def add_desert():
    """Sand floor: flat around the car, rolling dunes further out (heights rise with distance)."""
    import bmesh
    n, R = 160, 420.0
    bm = bmesh.new()
    verts = []
    rs = np.random.default_rng(5)
    waves = [(rs.uniform(0, 2 * math.pi), rs.uniform(0.012, 0.05), rs.uniform(0, 2 * math.pi)) for _ in range(9)]
    for j in range(n + 1):
        row = []
        for i in range(n + 1):
            # denser near the centre: map a uniform grid through a cubic
            u = (i / n) * 2 - 1
            v = (j / n) * 2 - 1
            x = R * u * abs(u) ** 1.5
            y = R * v * abs(v) ** 1.5
            d = math.hypot(x, y)
            h = 0.0
            for ang, k, ph in waves:
                h += math.sin((x * math.cos(ang) + y * math.sin(ang)) * k + ph)
            h = (h / 3.0 + 1.0) * 4.0 * min(1.0, max(0.0, (d - 25.0) / 60.0)) ** 1.2
            row.append(bm.verts.new((x, y, h - 0.002)))
        verts.append(row)
    for j in range(n):
        for i in range(n):
            bm.faces.new((verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i]))
    me = bpy.data.meshes.new('MirrorBakeSand')
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new('MirrorBakeSand', me)
    bpy.context.scene.collection.objects.link(o)
    m = bpy.data.materials.new('MirrorBakeSandMat')
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (0.62, 0.45, 0.27, 1)
    b.inputs['Roughness'].default_value = 0.95
    me.materials.append(m)
    return o


def cut_in_front_of(c, n, keep_beyond):
    """Delete the car geometry on the camera side of the mirror plane (signed distance along n, the glass
    normal toward the driver, below `keep_beyond` m): the cowl, dash, header tube and the mirror housing itself
    sit at or in front of the glass and must not show in the reflection."""
    import bmesh
    for o in list(bpy.context.scene.objects):
        if o.type != 'MESH' or o.name.startswith('MirrorBake'):
            continue
        mw = o.matrix_world
        me = o.data
        bm = bmesh.new()
        bm.from_mesh(me)
        dead = [v for v in bm.verts if (mw @ v.co - c).dot(n) < keep_beyond]
        if dead:
            bmesh.ops.delete(bm, geom=dead, context='VERTS')
            bm.to_mesh(me)
        bm.free()


def camera(name, loc, direction, hfov_deg, res, clip_start):
    cd = bpy.data.cameras.new(name)
    cd.lens_unit = 'FOV'
    cd.sensor_fit = 'HORIZONTAL'
    cd.angle = math.radians(hfov_deg)
    cd.clip_start = clip_start
    cd.clip_end = 2000.0
    o = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = V(direction).to_track_quat('-Z', 'Y').to_euler()
    sc = bpy.context.scene
    sc.camera = o
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    return o


def render_to(path_tmp):
    sc = bpy.context.scene
    sc.render.filepath = path_tmp
    sc.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)


def finish(path_tmp, out_name, size, flip=True):
    from PIL import Image
    im = Image.open(path_tmp).convert('RGB')
    if flip:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    im = im.resize(size, Image.LANCZOS)
    p = os.path.join(TEX, out_name)
    im.save(p, optimize=True)
    a = np.asarray(im).astype(np.float32)
    print('wrote', p, im.size, 'mean', a.reshape(-1, 3).mean(0).round(1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blend', default=os.path.join(ROOT, 'out', 'part_textures_all.blend'))
    ap.add_argument('--samples', type=int, default=48)
    ap.add_argument('--only', default='rear,side')
    ap.add_argument('--threads', type=int, default=0)
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    a = ap.parse_args(argv)
    tmp = os.environ.get('TMPDIR', '')
    if not os.path.isdir(tmp):
        tmp = os.path.join(ROOT, 'out')
    eye = V(spec.DRIVER_EYE)
    for view in a.only.split(','):
        prepare(a)
        if view == 'rear':
            n = (REAR_ROT @ V((0, -1, 0))).normalized()          # glass normal, toward the driver
            ev = reflect(eye, REAR_C, n)
            dist = abs((eye - REAR_C).dot(n))
            cut_in_front_of(REAR_C, n, 0.07)
            # look straight back past the eye (slightly right of the driver so both seat backs show), a little down
            d = V((0.16, -0.975, -0.15)).normalized()
            camera('MirrorBakeRear', ev, d, 74.0, (1024, 320), dist + 0.02)
            p = os.path.join(tmp, 'mirror_rear_raw.png')
            render_to(p)
            finish(p, 'mirror_rear_view.png', (1024, 160))
        elif view == 'side':
            # Left door mirror. body.py aims its glass so the driver sees straight back along the flank
            # (mirror_frame(): normal = bisector of the eye direction and (-0.04, -1, 0)); render from the eye
            # reflected in that glass, looking along the reflected ray. The flat glass covers only ~5 deg, so use
            # a 22 deg fov (like a mildly convex glass). Fallback without body.mirror_frame: the old flat glass.
            gc, n, r = SIDE_C, V((0, -1, 0)), V((-0.13, -1.0, 0.0)).normalized()
            try:
                sys.path.insert(0, os.path.join(ROOT, 'parts'))
                import body as _body
                gc, _rot, n = _body.mirror_frame()
                gc, n = V(gc), V(n).normalized()
                r = ((V(spec.DRIVER_EYE) - gc).normalized()).reflect(n) * -1.0
            except Exception as e:
                print('side mirror: body.mirror_frame() unavailable (%s) - using the flat glass' % e)
            ev = reflect(eye, gc, n)
            dist = abs((eye - gc).dot(n))
            cut_in_front_of(gc, n, 0.04)
            # aim 5 deg outboard of the reflected ray (the glass's outer half matters more than the cockpit)
            d = (Matrix.Rotation(math.radians(-5.0 if gc.x < 0 else 5.0), 3, 'Z') @ r + V((0, 0, -0.03))).normalized()
            camera('MirrorBakeSide', ev, d, 22.0, (512, 256), dist + 0.02)
            p = os.path.join(tmp, 'mirror_side_raw.png')
            render_to(p)
            # body.py maps the door glass with u = 0 at its INNER end, so the camera image is used unflipped
            finish(p, 'mirror_side_view.png', (512, 256), flip=False)


def prepare(a):
    bpy.ops.wm.open_mainfile(filepath=a.blend)
    sc = bpy.context.scene
    # remove any render studio a previous render.py run saved into the blend
    for coll in list(bpy.data.collections):
        if coll.name == 'RenderStudio':
            for o in list(coll.objects):
                bpy.data.objects.remove(o, do_unlink=True)
    for o in list(sc.objects):
        if o.type == 'LIGHT' or o.type == 'CAMERA':
            bpy.data.objects.remove(o, do_unlink=True)
    setup_world(1.0)
    add_sun()
    add_desert()
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = a.samples
    sc.cycles.use_denoising = True
    if a.threads:
        sc.render.threads_mode = 'FIXED'
        sc.render.threads = a.threads
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0.0
    sc.render.film_transparent = False


if __name__ == '__main__':
    main()
