"""Shared Blender helpers for the GLX sandrail build (bpy 5.1, runs headless).

Every part module does:
    from common import *
    import spec
    def build(C):            # C = BuildContext
        o = tube(...); C.add(o, 'static')        # or 'Wheel_FL', 'Upright_FR', ...

Conventions (see spec.py): +X right, +Y forward, +Z up, metres, origin on the ground
between the axles. Driver on the left (x < 0).
"""
import math
import os
import bmesh
import bpy
from mathutils import Vector, Matrix, Euler

ROOT = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(ROOT, 'textures')
V = Vector

# ------------------------------------------------------------------ scene

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    return sc


def collection(name, parent=None):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def link(obj, coll=None):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


# ------------------------------------------------------------------ materials

_mats = {}


def srgb(hexstr):
    """'#rrggbb' (sRGB) -> linear RGBA tuple for Principled BSDF."""
    h = hexstr.lstrip('#')
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], 1.0)


def image(path, colorspace='sRGB'):
    """Load (or reuse) an image from textures/ (or an absolute path)."""
    p = path if os.path.isabs(path) else os.path.join(TEX, path)
    name = os.path.basename(p)
    img = bpy.data.images.get(name)
    if img is None:
        img = bpy.data.images.load(p)
        img.name = name
    img.colorspace_settings.name = colorspace
    return img


def mat(name, color='#808080', metal=0.0, rough=0.5, *, tex=None, normal=None, normal_strength=1.0,
        rough_tex=None, emit=None, emit_strength=1.0, emit_tex=None, clearcoat=0.0, clearcoat_rough=0.03,
        alpha=1.0, transmission=0.0, ior=1.45, uv_scale=None, alpha_tex=False, double_sided=False,
        rough_factor=1.0, alpha_clip=None):
    """Principled material that survives glTF export.

    color: '#hex' or linear RGBA tuple. tex: image file in textures/ for base colour (multiplied by
    nothing - colour is ignored when tex is given). normal: tangent-space normal map file.
    rough_tex: greyscale roughness map (glTF packs it into the G channel automatically);
    rough_factor scales it (a Math Multiply node -> glTF roughnessFactor).
    emit: '#hex' emission colour (LEDs, screens); emit_tex: emissive image.
    clearcoat: 0..1 (exported as KHR_materials_clearcoat - use for glossy paint / carbon).
    uv_scale: (su, sv) tiles the textures (exported as KHR_texture_transform).
    alpha_tex: use the base-colour image's alpha. alpha_clip: cutoff (e.g. 0.5) -> hard cut-out,
    exported as glTF alphaMode MASK (Math Round / 1-(a<c) node, which the exporter recognises);
    without it a texture alpha exports as BLEND.
    Materials are cached by name, so call mat('Carbon') anywhere to reuse the same one.
    """
    if name in _mats and _mats[name].name in bpy.data.materials:
        return _mats[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (400, 0)
    b = nt.nodes.new('ShaderNodeBsdfPrincipled'); b.location = (0, 0)
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    col = srgb(color) if isinstance(color, str) else color
    b.inputs['Base Color'].default_value = col
    b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    b.inputs['IOR'].default_value = ior

    mapping = None
    if uv_scale:
        tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-900, 0)
        mapping = nt.nodes.new('ShaderNodeMapping'); mapping.location = (-700, 0)
        mapping.inputs['Scale'].default_value = (uv_scale[0], uv_scale[1], 1)
        nt.links.new(tc.outputs['UV'], mapping.inputs['Vector'])

    def teximg(file, cs, y):
        t = nt.nodes.new('ShaderNodeTexImage'); t.location = (-450, y)
        t.image = image(file, cs)
        if mapping:
            nt.links.new(mapping.outputs['Vector'], t.inputs['Vector'])
        return t

    if tex:
        t = teximg(tex, 'sRGB', 300)
        nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
        if alpha_tex:
            if alpha_clip is not None:
                # glTF alphaMode MASK: alpha -> [Round] (cutoff 0.5) or alpha -> [a < c] -> [1 - x]
                if abs(alpha_clip - 0.5) < 1e-6:
                    r = nt.nodes.new('ShaderNodeMath'); r.operation = 'ROUND'; r.location = (-200, 150)
                    nt.links.new(t.outputs['Alpha'], r.inputs[0])
                    nt.links.new(r.outputs[0], b.inputs['Alpha'])
                else:
                    lt = nt.nodes.new('ShaderNodeMath'); lt.operation = 'LESS_THAN'; lt.location = (-250, 150)
                    lt.inputs[1].default_value = alpha_clip
                    inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.location = (-120, 150)
                    inv.inputs[0].default_value = 1.0
                    nt.links.new(t.outputs['Alpha'], lt.inputs[0])
                    nt.links.new(lt.outputs[0], inv.inputs[1])
                    nt.links.new(inv.outputs[0], b.inputs['Alpha'])
                try:
                    m.surface_render_method = 'DITHERED'
                except Exception:
                    pass
            else:
                nt.links.new(t.outputs['Alpha'], b.inputs['Alpha'])
                try:
                    m.surface_render_method = 'BLENDED'
                except Exception:
                    pass
    if rough_tex:
        t = teximg(rough_tex, 'Non-Color', 0)
        if abs(rough_factor - 1.0) > 1e-6:
            mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.location = (-200, 0)
            mul.inputs[1].default_value = rough_factor
            nt.links.new(t.outputs['Color'], mul.inputs[0])
            nt.links.new(mul.outputs[0], b.inputs['Roughness'])
        else:
            nt.links.new(t.outputs['Color'], b.inputs['Roughness'])
    if normal:
        t = teximg(normal, 'Non-Color', -300)
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.location = (-200, -300)
        nm.inputs['Strength'].default_value = normal_strength
        nt.links.new(t.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    if emit or emit_tex:
        b.inputs['Emission Strength'].default_value = emit_strength
        if emit_tex:
            t = teximg(emit_tex, 'sRGB', 600)
            nt.links.new(t.outputs['Color'], b.inputs['Emission Color'])
        else:
            b.inputs['Emission Color'].default_value = srgb(emit) if isinstance(emit, str) else emit
    if clearcoat:
        b.inputs['Coat Weight'].default_value = clearcoat
        b.inputs['Coat Roughness'].default_value = clearcoat_rough
    if transmission:
        b.inputs['Transmission Weight'].default_value = transmission
    if alpha < 1.0:
        b.inputs['Alpha'].default_value = alpha
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            pass
    m.use_backface_culling = not double_sided
    _mats[name] = m
    return m


LIVERY_COAT = 0.5        # r4: clear coat over the livery (was 1.0; the base roughness map now carries the gloss)


# Standard palette shared by all parts (call these instead of inventing near-duplicates)
def M(key):
    """Common materials by short name."""
    table = {
        # r5 (lead decision, spec.COLORS['cage_gray']): dark charcoal gunmetal powder coat with a clear coat, so each
        # tube shows a crisp specular line (front_3q photo: tube bodies 20-60 sRGB, highlights 180-190). r4 #7d8187
        # m.5 r.35 read light silver in Cycles / ivory in the game cockpit. Powertrain charge pipes inherit 'cage'.
        'cage':        lambda: mat('Cage gunmetal', '#484b50', metal=0.6, rough=0.25, clearcoat=0.6, clearcoat_rough=0.08),
        # r5: spec.COLORS['arm_gray'] - suspension arms AND the front / rear bumper tubes stay a lighter medium grey
        'arm':         lambda: mat('Arm gunmetal', '#868a92', metal=0.6, rough=0.25, clearcoat=0.5, clearcoat_rough=0.08),
        # r4: 3x finer weave (carbon_base.png now holds 48 tows per tile: 3.5 mm tows at 1 UV unit / m), neutral tow
        # albedo ~21 / 39 sRGB (mean 30), roughness tows .22 / .32 (mean ~.27), metal 0, soft normal (.3)
        'carbon':      lambda: mat('Carbon gloss', tex='carbon_base.png', normal='carbon_normal.png', normal_strength=0.3,
                                   rough_tex='carbon_rough.png', clearcoat=1.0, clearcoat_rough=0.08, uv_scale=(6, 6)),
        # r6: interior gloss carbon (dash / console / door tops): carbon_interior.png = the same 48-tow weave in a
        # deeper black with ~45 % less albedo contrast (tows ~19 / 29 sRGB, carbon_base.png 21 / 39), the SHARED
        # carbon_normal.png (a little stronger, .4) so the weave reads mainly in the highlights. Same tiling as
        # M('carbon') (uv_scale 6, 48 tows per tile), so a part can swap the key without touching its UVs.
        # The exterior M('carbon') keeps carbon_base.png (the pod weave matches the photos).
        'carbon_interior': lambda: mat('Carbon interior', tex='carbon_interior.png', normal='carbon_normal.png',
                                       normal_strength=0.4, rough_tex='carbon_rough.png', clearcoat=1.0,
                                       clearcoat_rough=0.08, uv_scale=(6, 6)),
        'carbon_matte':lambda: mat('Carbon satin', tex='carbon_base.png', normal='carbon_normal.png', normal_strength=0.3,
                                   rough_tex='carbon_rough.png', rough_factor=1.8, uv_scale=(6, 6)),
        # r4: per-pixel roughness (livery_rough.png / livery_top_rough.png): black vinyl .08, carbon tows .14 / .26,
        # orange .15, charcoal vinyl .11 - so the black blades read as dark gloss and the carbon as lit weave
        'livery':      lambda: mat('Livery', tex='livery.png', rough_tex='livery_rough.png', clearcoat=LIVERY_COAT,
                                   clearcoat_rough=0.03),
        'livery_top':  lambda: mat('Livery top', tex='livery_top.png', rough_tex='livery_top_rough.png',
                                   clearcoat=LIVERY_COAT, clearcoat_rough=0.03),
        'gloss_black': lambda: mat('Gloss black', '#0b0b0c', rough=0.18, clearcoat=1.0),
        'satin_black': lambda: mat('Satin black', '#111112', rough=0.5),
        'rubber':      lambda: mat('Tire rubber', '#151515', rough=0.6),
        'orange':      lambda: mat('Orange gloss', '#ff5a0d', rough=0.25, clearcoat=0.8),
        'orange_anod': lambda: mat('Orange anodized', '#ff5a0d', metal=0.6, rough=0.35),
        'alu':         lambda: mat('Brushed aluminum', '#c9ccd0', metal=1.0, rough=0.3),
        'polished':    lambda: mat('Polished aluminum', '#e4e6e8', metal=1.0, rough=0.12),
        'chrome':      lambda: mat('Chrome', '#f2f2f2', metal=1.0, rough=0.06),
        'steel_dark':  lambda: mat('Dark steel', '#3a3c3f', metal=0.9, rough=0.4),
        'ceramic':     lambda: mat('Ceramic exhaust', '#8e9196', metal=0.5, rough=0.35),   # downpipes, turbo outlets
        'suede':       lambda: mat('Suede black', '#151515', rough=0.95),
        'leather':     lambda: mat('Leather gray', '#2b2c2e', rough=0.6),
        'stitch':      lambda: mat('Stitch orange', '#ff6a1a', rough=0.7),
        'belt':        lambda: mat('Harness black', '#121212', rough=0.8),
        'glass':       lambda: mat('Lens clear', '#ffffff', rough=0.05, alpha=0.25, transmission=0.0),
        # r3: lamps OFF by default (every photo shows them off); the *_on variants are for the game to swap in
        'led':         lambda: mat('LED white', '#e8e8e6', rough=0.2),
        'led_on':      lambda: mat('LED white on', '#ffffff', emit='#fff6e8', emit_strength=3.0, rough=0.2),
        'tail_red':    lambda: mat('Tail light red', '#7a0306', rough=0.2),
        'tail_red_on': lambda: mat('Tail light red on', '#7a0306', emit='#ff1010', emit_strength=1.5, rough=0.2),
        # r3: hard cut-out (glTF alphaMode MASK, cutoff 0.5) instead of BLEND. r4: satin silver (metal .55, rough .40;
        # at metal .9 it mirrored the dark studio / cowl and read black) and thicker bars (hex_mesh.png ~54 % metal)
        'mesh_grille': lambda: mat('Hex mesh', tex='hex_mesh.png', alpha_tex=True, alpha_clip=0.5, metal=0.55, rough=0.40,
                                   double_sided=True),
        'screen':      lambda: mat('Screen off', '#050608', rough=0.08, clearcoat=1.0),
        'mirror':      lambda: mat('Mirror glass', '#d8dde3', metal=1.0, rough=0.02),
        # r3: baked reflection for the mirrors (textures/mirror_rear_view.png = panoramic rear-view mirror;
        # body may use mirror_baked_side for the door mirrors). The game's live render target replaces it in the
        # cockpit. r6: emission 0.6 -> 0.10 and a real mirror finish (metal 1, rough .06) so from outside (chase /
        # photo views) the glasses read dark, reflecting what is around them (the dark studio + the car) instead of a
        # bright white rectangle. Cycles rear_3q side glass: r5 ~250 sRGB, emission .15 alone (metal 0) still 250 (the
        # sand-coloured albedo lit by the studio), metal 1 + emission .15 ~95, metal 1 + .06 ~70. The baked picture
        # stays the base colour, so the env reflection keeps it readable in the game's non-live cockpit fallback.
        'mirror_baked':      lambda: mat('Mirror baked', tex='mirror_rear_view.png', emit_tex='mirror_rear_view.png',
                                         emit_strength=0.10, metal=1.0, rough=0.06),
        'mirror_baked_side': lambda: mat('Mirror baked side', tex='mirror_side_view.png', emit_tex='mirror_side_view.png',
                                         emit_strength=0.10, metal=1.0, rough=0.06),
    }
    return table[key]()


def side_face_is_inner(co, n, thresh=0.3):
    """True for a body-side face whose normal points toward the car's centre line (the inside of a
    side panel / pod wall). side_uv() alone would map such a face onto the OTHER side's livery half
    (it trusts n.x), so give these faces plain carbon instead - see inner_side_faces_to()."""
    return n.x * (1.0 if co.x >= 0 else -1.0) < -thresh


def inner_side_faces_to(o, mat_from, mat_to, thresh=0.3):
    """Re-assign the faces of mesh object `o` that use material `mat_from` (e.g. M('livery')) and face
    inward (side_face_is_inner on the face centre, world space) to material `mat_to` (e.g. M('carbon'),
    then box-project their UVs). Call before uv_project(). Returns the number of faces changed."""
    me = o.data
    if mat_from.name not in [m.name for m in me.materials if m]:
        return 0
    if mat_to.name not in [m.name for m in me.materials if m]:
        me.materials.append(mat_to)
    names = [m.name if m else None for m in me.materials]
    i_from, i_to = names.index(mat_from.name), names.index(mat_to.name)
    mw = world_matrix(o)
    nm = mw.to_3x3().inverted().transposed()
    k = 0
    for p in me.polygons:
        if p.material_index != i_from:
            continue
        if side_face_is_inner(mw @ p.center, (nm @ p.normal).normalized(), thresh):
            p.material_index = i_to
            k += 1
    return k


# ------------------------------------------------------------------ objects

def obj_from_bmesh(name, bm, material=None, smooth=True, angle=35.0):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    if material is not None:
        mats = material if isinstance(material, (list, tuple)) else [material]
        for m in mats:
            me.materials.append(m)
    shade(o, smooth, angle)
    return o


def shade(o, smooth=True, angle=35.0):
    """Smooth shading with sharp edges above `angle` degrees (glTF splits normals there)."""
    me = o.data
    if not hasattr(me, 'polygons'):
        return o
    for p in me.polygons:
        p.use_smooth = smooth
    if smooth:
        try:
            me.set_sharpness_by_angle(angle=math.radians(angle))
        except Exception:
            pass
    return o


def box(name, size, loc=(0, 0, 0), rot=(0, 0, 0), material=None, bevel=0.0, segments=2):
    """Axis box of full size (sx, sy, sz) at loc, Euler rot in degrees, optional bevelled edges."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = V((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=segments, affect='EDGES', profile=0.5)
    o = obj_from_bmesh(name, bm, material)
    o.location = loc
    o.rotation_euler = Euler([math.radians(a) for a in rot])
    return o


def cylinder(name, r, depth, loc=(0, 0, 0), rot=(0, 0, 0), material=None, segments=32, r2=None, cap=True):
    """Cylinder (cone if r2) along local Z, centred at loc."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segments, radius1=r,
                          radius2=r if r2 is None else r2, depth=depth)
    o = obj_from_bmesh(name, bm, material, angle=40)
    o.location = loc
    o.rotation_euler = Euler([math.radians(a) for a in rot])
    return o


def sphere(name, r, loc=(0, 0, 0), material=None, segs=24, rings=12, scale=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    o = obj_from_bmesh(name, bm, material, angle=80)
    o.location = loc
    o.scale = scale
    return o


def _fillet(points, radius, steps=6):
    """Round the corners of a polyline with arcs of the given radius (pipe-bender look)."""
    pts = [V(p) for p in points]
    if radius <= 0 or len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        d1 = (a - b); d2 = (c - b)
        l1, l2 = d1.length, d2.length
        if l1 < 1e-6 or l2 < 1e-6:
            continue
        d1.normalize(); d2.normalize()
        ang = d1.angle(d2)
        if ang > math.pi - 1e-3:
            out.append(b); continue
        t = radius / math.tan(ang / 2)
        t = min(t, l1 * 0.48, l2 * 0.48)
        p1 = b + d1 * t; p2 = b + d2 * t
        # quadratic bezier through the corner approximates the bend well enough
        for s in range(steps + 1):
            u = s / steps
            out.append(p1 * (1 - u) ** 2 + b * 2 * u * (1 - u) + p2 * u * u)
    out.append(pts[-1])
    return out


def tube(name, points, r, material=None, bend=None, sides=16, cap=True, steps=6):
    """Round tube through 3D points, corners rounded with bend radius (default 3*r... like a bender die).

    Returns a mesh object. Use for cage/frame tubes, hoses, exhaust, tie rods.
    """
    bend = 3.0 * r if bend is None else bend
    pts = _fillet(points, bend, steps)
    cu = bpy.data.curves.new(name + '_c', 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = r
    cu.bevel_resolution = max(1, sides // 4 - 1)
    cu.use_fill_caps = cap
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p.x, p.y, p.z, 1)
    tmp = bpy.data.objects.new(name + '_tmp', cu)
    bpy.context.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    me.name = name
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    if material is not None:
        me.materials.append(material)
    shade(o, True, 60)
    return o


def lathe(name, profile, material=None, segments=48, axis='Z', loc=(0, 0, 0), rot=(0, 0, 0)):
    """Revolve a 2D profile [(radius, height), ...] around Z (then rotate). Wheels, tyres, knobs, shocks."""
    bm = bmesh.new()
    rings = []
    for k in range(segments):
        a = 2 * math.pi * k / segments
        ca, sa = math.cos(a), math.sin(a)
        rings.append([bm.verts.new((r * ca, r * sa, h)) for (r, h) in profile])
    for k in range(segments):
        r0, r1 = rings[k], rings[(k + 1) % segments]
        for i in range(len(profile) - 1):
            try:
                bm.faces.new((r0[i], r1[i], r1[i + 1], r0[i + 1]))
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = obj_from_bmesh(name, bm, material, angle=30)
    o.location = loc
    o.rotation_euler = Euler([math.radians(a) for a in rot])
    return o


def loft(name, sections, material=None, closed=True, cap=True, angle=35.0):
    """Skin a list of cross-sections (each a list of 3D points, same count) into a surface.
    Great for body panels: give sections front-to-back. closed=True closes each ring."""
    bm = bmesh.new()
    rows = [[bm.verts.new(V(p)) for p in sec] for sec in sections]
    n = len(rows[0])
    for j in range(len(rows) - 1):
        a, b = rows[j], rows[j + 1]
        m = n if closed else n - 1
        for i in range(m):
            i2 = (i + 1) % n
            try:
                bm.faces.new((a[i], a[i2], b[i2], b[i]))
            except ValueError:
                pass
    if cap and closed:
        for r in (rows[0], rows[-1]):
            try:
                bm.faces.new(r)
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bmesh(name, bm, material, angle=angle)


def world_matrix(o):
    """Up-to-date world matrix (matrix_world is stale right after setting location/rotation)."""
    if o.parent is None:
        return o.matrix_basis.copy()
    bpy.context.view_layer.update()
    return o.matrix_world.copy()


def apply_transform(o):
    """Bake location/rotation/scale into the mesh (object ends at identity)."""
    mw = world_matrix(o)
    o.parent = None
    o.data.transform(mw)
    o.matrix_basis = Matrix.Identity(4)
    return o


def mirror_x(o, name=None):
    """Copy an object to the other side of the car (x -> -x), with correct normals."""
    c = o.copy()
    c.data = o.data.copy()
    c.name = name or (o.name.replace('_L', '_R') if '_L' in o.name else o.name + '_mirror')
    bpy.context.scene.collection.objects.link(c)
    apply_transform(c)
    c.data.transform(Matrix.Scale(-1, 4, (1, 0, 0)))
    c.data.flip_normals()
    return c


def join(objs, name):
    """Join several mesh objects into one (materials are kept)."""
    objs = [o for o in objs if o and o.type == 'MESH']
    if not objs:
        return None
    for o in objs:
        apply_transform(o)
    base = objs[0]
    bm = bmesh.new()
    mats = []
    for o in objs:
        me = o.data
        remap = []
        for m in me.materials:
            if m not in mats:
                mats.append(m)
            remap.append(mats.index(m))
        tmp = bmesh.new(); tmp.from_mesh(me)
        uv_layers = me.uv_layers.keys()
        for f in tmp.faces:
            if remap:
                f.material_index = remap[min(f.material_index, len(remap) - 1)]
        me2 = bpy.data.meshes.new('tmpj'); tmp.to_mesh(me2); tmp.free()
        bm.from_mesh(me2)
        bpy.data.meshes.remove(me2)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for m in mats:
        me.materials.append(m)
    out = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(out)
    for o in objs:
        bpy.data.objects.remove(o)
    return out


# ------------------------------------------------------------------ UVs

def uv_project(o, fn, layer='UVMap'):
    """Set UVs per face-corner from world-space vertex position: fn(Vector world, Vector normal) -> (u, v)."""
    me = o.data
    if layer not in me.uv_layers:
        me.uv_layers.new(name=layer)
    uv = me.uv_layers[layer].data
    mw = world_matrix(o)
    nm = mw.to_3x3().inverted().transposed()
    for p in me.polygons:
        n = (nm @ p.normal).normalized()
        for li in p.loop_indices:
            co = mw @ me.vertices[me.loops[li].vertex_index].co
            uv[li].uv = fn(co, n)


def side_uv(co, n):
    """Livery atlas mapping for body SIDE panels (see spec.LIVERY_*). Left side -> top half."""
    import spec
    y0, y1 = spec.LIVERY_Y; z0, z1 = spec.LIVERY_Z
    v = (co.z - z0) / (z1 - z0) * 0.5
    left = co.x < 0 if abs(n.x) < 0.3 else n.x < 0
    if left:
        return ((y1 - co.y) / (y1 - y0), 0.5 + v)
    return ((co.y - y0) / (y1 - y0), v)


def top_uv(co, n):
    import spec
    y0, y1 = spec.LIVERY_Y
    return ((co.x + 1.0) / 2.0, (co.y - y0) / (y1 - y0))


def box_uv(o, scale=1.0):
    """Tri-planar style box projection (good for carbon weave, tread, mats)."""
    def f(co, n):
        ax = max(range(3), key=lambda i: abs(n[i]))
        if ax == 0:
            return (co.y * scale, co.z * scale)
        if ax == 1:
            return (co.x * scale, co.z * scale)
        return (co.x * scale, co.y * scale)
    uv_project(o, f)


def cyl_uv(o, axis='Z', scale=1.0):
    def f(co, n):
        if axis == 'X':
            return (math.atan2(co.z, co.y) / (2 * math.pi), co.x * scale)
        if axis == 'Y':
            return (math.atan2(co.z, co.x) / (2 * math.pi), co.y * scale)
        return (math.atan2(co.y, co.x) / (2 * math.pi), co.z * scale)
    uv_project(o, f)


# ------------------------------------------------------------------ build context

class BuildContext:
    """Collects the parts. Groups:
        'static'                - joined into Chassis_Mesh (everything bolted to the frame)
        'Wheel_FL' .. 'Wheel_RR'- spin with the wheel (tyre, rim, beadlock, rotor). Build them AT the
                                  wheel centre from spec.WHEELS; the builder re-parents them.
        'Upright_FL' ..         - move up/down with the wheel and steer with it (front) but do not spin
                                  (spindle, hub carrier, caliper)
        'SteeringWheel'         - the steering wheel itself (rim, spokes, hub, quick release)
        'LightBar'              - roof LED bar (the game lights it with the N key)
        any 'Link_*', 'TieRod_*', 'Halfshaft_*', 'Shock_*' name - a moving suspension piece; register
            its two end points with C.segment(name, a=chassis_end, b=wheel_end, wheel='FL', shock=False)
    """
    def __init__(self):
        self.groups = {}
        self.segments = {}
        self.points = {}

    def add(self, objs, group='static'):
        if not isinstance(objs, (list, tuple)):
            objs = [objs]
        for o in objs:
            if o is not None:
                self.groups.setdefault(group, []).append(o)
        return objs[0] if len(objs) == 1 else objs

    def segment(self, name, objs, a, b, wheel, shock=False):
        """A moving suspension member made of objs, spanning chassis point a -> wheel point b."""
        self.add(objs, name)
        self.segments[name] = {'a': tuple(a), 'b': tuple(b), 'wheel': wheel, 'shock': shock}

    def point(self, name, xyz):
        self.points[name] = tuple(xyz)


def aligned_matrix(origin, zdir):
    """World matrix with its origin at `origin` and local +Z along `zdir` (local X kept level)."""
    z = V(zdir).normalized()
    ref = V((1, 0, 0)) if abs(z.x) < 0.9 else V((0, 1, 0))
    x = (ref - z * ref.dot(z)).normalized()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = V(origin)
    return m


def place(o, origin, zdir):
    """Put an object built around its own Z axis (cylinders, lathe parts, wheels) at origin, Z along zdir."""
    o.matrix_basis = aligned_matrix(origin, zdir)
    return o
