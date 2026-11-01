"""Render the built sandrail from the reference-photo cameras and make comparison sheets + overlays.

    python tools/render.py [--blend out/trx_sandrail.blend]
        [--views side_right,front_3q_right,...] [--samples 24] [--width 960] [--tag name]
        [--no-overlay] [--threads N]

Outputs per view (in renders/):
    <tag><view>.png          the Cycles render
    <tag>compare_<view>.png  reference photo left, render right
    <tag>overlay_<view>.png  the photo with the render blended at 50 %, the render's silhouette
                             outlined in CYAN and the photo's silhouette (its alpha cut-out) in YELLOW.
                             Where cyan and yellow disagree the model's shape differs from the photo.
    <tag>mask_<view>.png     the render's silhouette (alpha = car), for your own measurements

Views (photo-matched cameras, solved by least squares from wheel outlines + known hard points):
    side_right, front_3q_right, front, rear_3q_right, rear, rear_wheel_right (alias rear_wheel_sidepod_right),
    interior_dash, seat
  plus cockpit (game driver eye, 78 deg vertical fov) and top (plan view), which have no photo.
For photo views the image has the photo's aspect ratio and --width is the LONGER side
(so the portrait views rear_wheel_right and seat render at e.g. 640 x 960 for --width 960).

Studio (fix round 5): black world + near-black matte floor (albedo 0.004, so the lower panels do not
mirror a grey floor). The rig turns with the camera (STUDIO_RIG 'rel' rows are placed relative to the
view heading, see studio_yaw); two square soft keys ~35 deg up at the camera's front corners, long thin
softbox STRIPS (rim strips behind, two overhead strips, two side strips) that draw crisp highlight lines
on gloss black. Broad lights from above (TopD, CabinD, low fills) are diffuse-only (visible_glossy=False):
they light the car but are never mirrored, so the hood, pod tops, spoiler and roof liner reflect black
instead of silver. Per-view overrides / extra lights / exposure offsets live in STUDIO_VIEW.
View transform 'Standard' (Filmic/AgX desaturated the livery orange #ff5a0d to ~(217,117,23));
EXPOSURE is set so the orange lands at V~250 like the photos and the car medians are within ~10 %.

Fix round 6: a reflection-only SWEEP (StudioDome, see DOME_PROFILE): a big hemisphere seen only by glossy
rays (camera / diffuse / shadow visibility off, never light-sampled), so the clear-coated paint, carbon,
cage and tyres show long soft reflection bands while the camera background stays dark and the diffuse /
orange calibration and the per-view exposures stay as in r5. Dark at the horizon, brighter above it, black
on the far side (the r5 'no silver hood / pod tops / spoiler back' rule), cool-tinted like the photos'
reflections; per-view gain / profile / tint in STUDIO_VIEW ('_dome', '_dome_profile', '_dome_rgb').
The key softbox is now diffuse-only (its hard-edged square mirrored as crumpled white shapes on the
dented cowl / fenders - the sweep carries its reflection, soft-edged), the rim / overhead strips are
thinner (0.12 m: crisp lines, less coverage).
"""
import argparse
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy  # noqa: E402
from mathutils import Vector, Matrix  # noqa: E402
import spec  # noqa: E402

V = Vector

# ---------------------------------------------------------------------------------------------
# Cameras.
# Photo views are dicts:  loc = camera position (m, car frame), ypr = (yaw, pitch, roll) in rad
# (yaw = heading of the view direction in the XY plane, 0 = +X, pi/2 = +Y; pitch = elevation;
# roll = rotation about the view axis), f = focal length as a fraction of the image WIDTH
# (f_px / width_px), size = the reference photo's pixel size (sets the aspect), ref = photo file.
# Solved in the prep step (least-squares solver, see the prep report): tyre outlines from the photos' alpha cut-outs
# fitted to the model's wheel meshes (+ light-bar ends, headlights, roof strip, dash features...).
# The four exterior 3/4 + front/rear views were solved jointly with a shared front/rear track
# correction, because the photos show a narrower track than spec (see the prep report).
#
# Legacy tuple views (loc, look-at target, focal mm (0 = 78 deg vertical game fov), (w, h) aspect,
# reference) still work - other scripts (arms/render_arms.py) add their own this way.
# ---------------------------------------------------------------------------------------------
VIEWS = {
    # 9.5 m away, ~66 mm equivalent: nearly orthographic (red-livery variant of the same chassis)
    'side_right': dict(ref='side_right_red_variant.png', size=(2172, 724),
                       loc=(9.5000, -0.0261, 0.7760), ypr=(3.15723, -0.00011, -0.01162), f=1.82828),
    'front_3q_right': dict(ref='front_3q_right.png', size=(1536, 1024),
                           loc=(3.3480, 6.4431, 1.0380), ypr=(-2.07827, -0.04673, 0.00151), f=1.81432),
    'front': dict(ref='front.png', size=(1536, 1024),
                  loc=(0.0062, 5.4385, 1.1885), ypr=(-1.57174, -0.10671, -0.00358), f=1.68083),
    'rear_3q_right': dict(ref='rear_3q_right.png', size=(1536, 1024),
                          loc=(4.6322, -4.5688, 1.3025), ypr=(2.42100, -0.07752, -0.01830), f=1.38369),
    # low and close behind the bumper (wide lens): huge bumper, small roof
    'rear': dict(ref='rear.png', size=(1536, 1024),
                 loc=(-0.0444, -3.8638, 1.8692), ypr=(1.55518, -0.41682, 0.01160), f=0.95357),
    # ahead of and outboard of the right rear wheel, looking back at it (focal length only loosely
    # determined: 1000-2000 px fit about equally; this one balances the pod corner and rear bumper)
    'rear_wheel_right': dict(ref='rear_wheel_sidepod_right.png', size=(1024, 1536),
                             loc=(1.9384, 0.0136, 1.1350), ypr=(-2.29312, -0.16895, 0.05172), f=1.26953),
    # from the passenger door opening, wide lens. r5 re-solve (prep): 17 features (dash screen + DuneNav glass
    # corners, radio, red buttons, switch panel, DCX plate, stereo, steering-wheel centre / top / bottom, driver
    # door escutcheon) from the model's own quads: rms 48.6 -> 32.5 px at 1536 (wheel top 109 -> 73 px). The
    # distance along the view axis stays weakly determined (dash rms 25-28 px for any x 0.73..1.3); the residuals
    # left are the model's layout (its dash screen sits ~4 cm further left behind the wheel than the photo's, its
    # floor mats do not match the photo's). clip 0.20 cuts away the passenger door bar 0.1 m from the lens.
    'interior_dash': dict(ref='interior_dash.png', size=(1536, 1024), clip=0.20,
                          loc=(0.73153, -0.19820, 1.16721), ypr=(2.47979, -0.40888, -0.19217), f=0.76306),
    # the PASSENGER seat through the windshield opening, telephoto (~200 mm equiv.) from above the nose (the
    # foreground tube is the centre windshield post, the carbon plate with bolts its base on the cowl). r5 re-solve
    # (prep): seat-back logo, both harness slots, seat-back top, post base + post and roof-front-tube lines:
    # 23 cm further back with a 9 % longer lens than r4 (logo/post-base errors 24/35 -> 12/13 px at 1024 wide).
    # The model's centre post still renders ~117 px wide vs ~88 px in the photo: a 1.75" tube where the real post
    # looks like 1.25" (camera distance cannot fix that - the seat back width matches, 660 px).
    'seat': dict(ref='seat_closeup.png', size=(1024, 1536),
                 loc=(-0.27181, 2.75673, 1.41122), ypr=(-1.37983, -0.09853, -0.11358), f=5.64433),
    'cockpit': (spec.DRIVER_EYE, (spec.DRIVER_EYE[0], spec.DRIVER_EYE[1] + 10, spec.DRIVER_EYE[2] - 1.0), 0, (16, 9), None),
    'top': ((0, -0.2, 12), (0, -0.2, 0), 50, (1, 2), None),
}
ALIASES = {'rear_wheel_sidepod_right': 'rear_wheel_right', 'side': 'side_right', 'f3q': 'front_3q_right',
           'r3q': 'rear_3q_right', 'dash': 'interior_dash', 'interior': 'interior_dash'}

STUDIO_COLL = 'RenderStudio'
OLD_STUDIO = ('KeyTop', 'KeyFrontR', 'KeyRearR', 'FillL', 'FillFront', 'FillRear', 'CabinFill', 'StudioFloor')


# ---------------------------------------------------------------------------------------------
# studio
#
# r5 (prep): a product-photo studio, re-oriented for every view. Gloss black only shows what it
# mirrors, so the rig keeps every large glossy-visible source out of the directions the big paint
# panels mirror from the camera (the far side of the car at 15-55 deg elevation: the hood / pod tops
# / roof from the 3/4 cameras, the spoiler's rear face - tilted 18 deg up - from the rear camera).
#   * camera-relative ('rel', (azimuth offset from the camera side, elevation, distance) about AIM):
#     the key softbox beside the camera, a fill on the other side, two thin rim strips high behind;
#   * car-fixed: two thin overhead strips along the car (crisp highlight lines on the hood beak, pod
#     shoulders and roof edges), a long strip above the right side (shoulder / belt-line highlight
#     line; the left one only for the symmetric front / rear / top views);
#   * diffuse-only fills (visible_glossy off, never seen in a reflection): low front fills for the
#     tyres and underside, a broad top wash for the engine bay and seats, a small cabin fill.
# 'Standard' view transform (AgX turned the livery orange (251,85,2) of the photos into (217,117,23));
# EXPOSURE puts the livery orange (#ff5a0d) of a key-lit panel at the photos' ~248 red.
# Rig yaw = the camera's view heading + 180 deg (cockpit / top / legacy tuple views: STUDIO_DEFAULT_YAW).
# r6 (prep): Key diffuse-only (450 -> 420 W: the f3q door orange (243,85,14), photo (248,74,2)); its glossy
# role goes to the reflection-only sweep below (DOME_*). Rim / overhead strips 0.3 -> 0.12 m wide at ~the same
# radiance; Fill 150 -> 260 W, low fills / top wash lower (the photos' cage / arm / body shadows are deeper:
# p10 2-13 vs 25-60). Energies from a light-group fit (every light in its own Cycles light group, one render per
# view, scales fitted to the photos' region percentiles), rounded and checked by eye.
# ---------------------------------------------------------------------------------------------
STUDIO_AIM = (0.0, -0.2, 0.8)
STUDIO_DEFAULT_YAW = 61.0          # = the front_3q_right camera's side (cockpit, top, arms/render_arms.py)
EXPOSURE = -0.3                    # EV, 'Standard' view transform
WORLD_RGB = (0.0016, 0.0017, 0.0019)
FLOOR_ALBEDO = 0.004              # near-black: grazing reflections of a lit floor greyed the lower panels
#  name,        kind,  where,                 size, size_y, aim_z (or a full target point for 'fix'), glossy, energy (W)
STUDIO_RIG = [
    ('Key',      'rel',  (-25.0, 35.0, 6.0),    2.6,  2.6,   0.75,  False, 420.0),
    ('Fill',     'rel',  (65.0, 28.0, 6.5),     2.6,  2.6,   0.75,  True,  260.0),
    ('RimA',     'rel',  (140.0, 55.0, 6.0),    3.0,  0.12,  1.0,   True,  32.0),
    ('RimB',     'rel',  (220.0, 55.0, 6.0),    3.0,  0.12,  1.0,   True,  32.0),
    ('OverL',    'down', (-1.0, -0.1, 4.6),     3.4,  0.12,  None,  True,  16.0),
    ('OverR',    'down', (1.0, -0.1, 4.6),      3.4,  0.12,  None,  True,  16.0),
    ('SideR',    'fix',  (3.4, -0.3, 3.2),      5.0,  0.4,   0.9,   True,  120.0),
    ('SideL',    'fix',  (-3.4, -0.3, 3.2),     5.0,  0.4,   0.9,   True,  130.0),
    ('LowD',     'rel',  (-15.0, 8.0, 4.5),     1.6,  0.8,   0.45,  False, 25.0),
    ('LowFillD', 'rel',  (50.0, 8.0, 4.5),      1.6,  0.8,   0.45,  False, 32.0),
    ('TopD',     'fix',  (0.0, -0.4, 5.5),      3.0,  4.5,   0.0,   False, 85.0),
    ('CabinD',   'fix',  (0.0, -0.2, 1.42),     0.8,  0.8,   0.6,   False, 14.0),
]
# per-view changes: {light: None (off) | dict(where=..., energy=...), '_add': [extra STUDIO_RIG-style rows],
#                    '_ev': exposure offset (each photo had its own exposure; calibrated on its orange),
#                    '_dome': sweep gain (default DOME_GAIN, 0 = off), '_dome_profile': {sector: knots} overriding
#                    DOME_PROFILE's sectors, '_dome_rgb': sweep tint}
# (tried for 'front': a low dim wall behind the car for the warm cheek reflections of front.png - on the
# model's narrower front clip it only drew white slivers on the panel edges, so it is not used)
STUDIO_VIEW = {
    'front_3q_right': {'SideL': None, '_dome': 1.5},
    # (the spoiler's rear face mirrors the side sector 20-35 deg up from this camera: keep that band dark)
    'rear_3q_right': {'SideL': None, '_dome': 1.5,
                      '_dome_profile': {'side': ((0.0, 0.0), (25.0, 0.04), (40.0, 0.12), (55.0, 0.25), (90.0, 0.30))}},
    'side_right': {'SideL': None},
    'rear_wheel_right': {'SideL': None},
    # interior photos had their own cabin lighting / exposure: a soft fill from just outside the passenger door
    # opening behind the camera (diffuse only) and +EV so the dash decal orange reads like the photo's (~250 red)
    'interior_dash': {'SideL': None, '_ev': 0.5,
                      '_add': [('DoorFillD', 'rel', (0.0, 25.0, 2.6), 1.8, 1.2, 0.75, False, 150.0)]},
    # the seat photo is exposed darker (firewall orange panel at ~247 red, not clipped)
    'seat': {'SideL': None, '_ev': -0.5},
    'cockpit': {'SideL': None, '_dome': 0.5},     # (the hood mirrors the f3q-side sweep from the driver's eye)
    # high camera behind: the key goes higher and wider so the spoiler's rear face does not mirror it
    # and the overhead strips and the rims (ahead of the car) go: the engine cover slopes toward this camera
    # and mirrored them as white panels where the photo shows it black; lighter top wash (the plenum faces
    # straight up) and low fill (it lit the bumper tubes head-on)
    # A strip across the car high behind (60+ deg up from the spoiler, 70+ deg from the engine cover, so neither
    # mirrors it) gives the cage and bumper tubes and the engine metal their top highlight lines instead.
    'rear': {'Key': dict(where=(-35.0, 58.0, 6.0)), 'OverL': None, 'OverR': None, 'RimA': None, 'RimB': None,
             'TopD': dict(energy=40.0), 'LowD': dict(energy=30.0), '_dome': 1.0,
             # sweep: almost nothing in the near sector below 35 deg (the spoiler's rear face mirrors 20-35 deg there),
             # a dim band ahead of the car low down for the soft grey sheen on the carbon pod tops (rear.png)
             '_dome_profile': {'near': ((0.0, 0.0), (20.0, 0.03), (35.0, 0.12), (55.0, 0.50), (90.0, 0.60)),
                               'far': ((0.0, 0.08), (15.0, 0.10), (30.0, 0.05), (60.0, 0.0), (90.0, 0.0))},
             '_add': [('RearStrip', 'fix', (0.0, -2.5, 5.0), 3.0, 0.4, (0.0, -1.4, 0.9), True, 240.0)]},
    # front.png's fender cheeks mirror a bright surround at the car's sides, low down (|az| 60-120, el -10..10)
    # (side strips at half power: on the dented front clip they drew white loops on the fenders, hood p90 172 vs 140)
    'front': {'_dome': 2.0, '_dome_profile': {'side': ((0.0, 0.45), (15.0, 0.45), (30.0, 0.30), (90.0, 0.25))},
              'SideL': dict(energy=60.0), 'SideR': dict(energy=55.0),
              '_dome_rgb': (1.0, 1.0, 1.08)},       # (the cheeks' surround reads warm in front.png, the cage cool)
}


# ---------------------------------------------------------------------------------------------
# r6 (prep): reflection-only soft sweep. A large hemisphere (radius DOME_RADIUS about the car) whose emission is
# seen ONLY by glossy rays (camera, diffuse, transmission and shadow visibility off; emission_sampling NONE, so it is
# never light-sampled either): it adds the long soft reflection bands of a product studio's sweep/scrims to the
# clear-coated paint, carbon, cage and tyres, but lights nothing diffusely (the r5 diffuse / orange calibration and
# exposures stay valid) and the camera background stays dark. It turns with the rig like the 'rel' lights.
# Radiance (Emission strength) by elevation (deg) per sector about the camera side: 'near' = behind the camera
# (|azimuth| <= 30 deg: a light grey sweep wall rising into the ceiling), 'side' (60-120), 'far' = beyond the car
# (>= 150), blended linearly in azimuth between. 'far' stays black: the hood, pod tops and roof mirror the far side
# from the 3/4 cameras (the r4 silver), and the spoiler's rear face mirrors the near sector only ~12 deg up from the
# rear camera, where the sweep is dimmest.
# Values from a light-group fit (one Cycles render per view, every light and 16 sweep segments in their own light
# group, segment radiances + light scales fitted to the photos' region percentiles of paint / pods / roof / spoiler /
# cage / arms / tyres); per-view gain '_dome' in STUDIO_VIEW (the photos were not all lit alike: the front photo's
# fender cheeks mirror a bright surround, the 3/4 photos' doors mostly black).
# ---------------------------------------------------------------------------------------------
DOME_RADIUS = 12.0
DOME_CENTER = (0.0, -0.2, 0.8)
DOME_PROFILE = {
    'near': ((0.0, 0.0), (8.0, 0.10), (20.0, 0.50), (35.0, 0.80), (55.0, 0.80), (90.0, 0.70)),
    'side': ((0.0, 0.0), (10.0, 0.03), (25.0, 0.12), (50.0, 0.25), (90.0, 0.30)),
    'far': ((0.0, 0.0), (90.0, 0.0)),
}
DOME_RGB = (0.88, 1.0, 1.30)     # cool, luminance ~1: the photos' reflections on black paint / tyres / cage run blue
                                 # (B-R +10..+28 sRGB in all four exterior photos; STUDIO_VIEW '_dome_rgb' overrides)
DOME_GAIN = 1.0                    # default per-view gain (STUDIO_VIEW '_dome' overrides; 0 = no sweep)


def view_ref(view):
    v = VIEWS[view]
    return v.get('ref') if isinstance(v, dict) else v[4]


def _studio_collection():
    sc = bpy.context.scene
    coll = bpy.data.collections.get(STUDIO_COLL)
    if coll is None:
        coll = bpy.data.collections.new(STUDIO_COLL)
    if coll.name not in sc.collection.children:
        sc.collection.children.link(coll)
    return coll


def _clear_studio(lights_only=False):
    names = set() if lights_only else set(OLD_STUDIO)
    coll = bpy.data.collections.get(STUDIO_COLL)
    if coll:
        names |= {o.name for o in coll.objects if (o.type == 'LIGHT' or not lights_only)}
    for n in names:
        o = bpy.data.objects.get(n)
        if o is not None:
            bpy.data.objects.remove(o, do_unlink=True)


def _area(coll, name, loc, energy, size, size_y=None, target=(0, 0, 0.6), color=(1.0, 1.0, 1.0), spread=180,
          glossy=True, rotation=None):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.shape = 'RECTANGLE'
    ld.size = size
    ld.size_y = size_y if size_y is not None else size
    ld.color = color
    try:
        ld.spread = math.radians(spread)
    except Exception:
        pass
    o = bpy.data.objects.new(name, ld)
    coll.objects.link(o)
    o.location = loc
    if rotation is not None:
        o.rotation_euler = rotation
    else:
        d = V(target) - V(loc)
        o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()   # local Y (size_y) stays as vertical as possible
    try:
        o.visible_glossy = glossy          # False: lights diffuse surfaces but is never seen in a reflection
    except Exception:
        pass
    return o


def _interp(knots, x):
    if x <= knots[0][0]:
        return knots[0][1]
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / max(1e-9, x1 - x0)
    return knots[-1][1]


def dome_radiance(az, el, profile=None):
    """Sweep radiance for azimuth `az` (deg about the camera side) and elevation `el` (deg).
    `profile`: sectors overriding DOME_PROFILE's (STUDIO_VIEW '_dome_profile')."""
    pr = dict(DOME_PROFILE, **(profile or {}))
    a = abs((az + 180.0) % 360.0 - 180.0)
    near, side, far = (_interp(pr[k], el) for k in ('near', 'side', 'far'))
    if a <= 30.0:
        return near
    if a < 60.0:
        return near + (side - near) * (a - 30.0) / 30.0
    if a <= 120.0:
        return side
    if a < 150.0:
        return side + (far - side) * (a - 120.0) / 30.0
    return far


def _dome(coll, psi, gain, profile=None, rgb=None, n_az=96, n_el=22):
    """Reflection-only sweep hemisphere (see DOME_PROFILE), radiance baked into a point colour attribute."""
    o = bpy.data.objects.get('StudioDome')
    if o is not None:
        bpy.data.objects.remove(o, do_unlink=True)
    if gain <= 0.0:
        return None
    cx, cy, cz = DOME_CENTER
    verts, faces, rad = [], [], []
    els = [-4.0] + [88.0 * j / (n_el - 1) for j in range(n_el)]       # skirt 4 deg below the centre height
    for el in els:
        for i in range(n_az):
            az = 360.0 * i / n_az
            h, e = math.radians(psi + az), math.radians(el)
            verts.append((cx + DOME_RADIUS * math.cos(e) * math.cos(h), cy + DOME_RADIUS * math.cos(e) * math.sin(h),
                          cz + DOME_RADIUS * math.sin(e)))
            rad.append(dome_radiance(az, max(el, 0.0), profile))
    for j in range(len(els) - 1):
        for i in range(n_az):
            a, b = j * n_az + i, j * n_az + (i + 1) % n_az
            faces.append((a, a + n_az, b + n_az, b))                     # normals face the car (inward)
    top = len(verts)
    verts.append((cx, cy, cz + DOME_RADIUS))
    rad.append(sum(dome_radiance(360.0 * i / n_az, 90.0, profile) for i in range(n_az)) / n_az)
    base = (len(els) - 1) * n_az
    for i in range(n_az):
        faces.append((base + i, top, base + (i + 1) % n_az))
    me = bpy.data.meshes.new('StudioDome')
    me.from_pydata(verts, [], faces)
    me.update()
    ca = me.color_attributes.new('Rad', 'FLOAT_COLOR', 'POINT')
    col = rgb or DOME_RGB
    for k, r in enumerate(rad):
        ca.data[k].color = (r * gain * col[0], r * gain * col[1], r * gain * col[2], 1.0)
    m = bpy.data.materials.get('StudioDomeMat')
    if m is None:
        m = bpy.data.materials.new('StudioDomeMat')
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        at = nt.nodes.new('ShaderNodeAttribute')
        at.attribute_type = 'GEOMETRY'
        at.attribute_name = 'Rad'
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Strength'].default_value = 1.0
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(at.outputs['Color'], em.inputs['Color'])
        nt.links.new(em.outputs[0], out.inputs[0])
        try:
            m.cycles.emission_sampling = 'NONE'     # found by glossy BSDF rays only, never light-sampled
        except Exception:
            pass
    me.materials.append(m)
    o = bpy.data.objects.new('StudioDome', me)
    coll.objects.link(o)
    for attr, val in (('visible_camera', False), ('visible_diffuse', False), ('visible_glossy', True),
                      ('visible_transmission', False), ('visible_volume_scatter', False), ('visible_shadow', False)):
        try:
            setattr(o, attr, val)
        except Exception:
            pass
    return o


def studio_yaw(view):
    """Rig heading (deg): the camera's side of the car = view heading + 180."""
    v = VIEWS.get(view)
    if view in ('cockpit', 'top') or v is None:
        return STUDIO_DEFAULT_YAW
    if isinstance(v, dict):
        return math.degrees(v['ypr'][0]) + 180.0
    d = V(v[1]) - V(v[0])
    if d.xy.length < 1e-6 or v[4] is None:
        return STUDIO_DEFAULT_YAW
    return math.degrees(math.atan2(d.y, d.x)) + 180.0


def setup_lights(view=None):
    """(Re)build the studio lights for a view (None = the default front-3/4 orientation)."""
    _clear_studio(lights_only=True)
    coll = _studio_collection()
    psi = studio_yaw(view) if view else STUDIO_DEFAULT_YAW
    over = STUDIO_VIEW.get(view, {}) if view else STUDIO_VIEW['front_3q_right']
    bpy.context.scene.view_settings.exposure = EXPOSURE + over.get('_ev', 0.0)   # per-photo exposure offset
    ax, ay, az = STUDIO_AIM
    out = []
    for (name, kind, where, sx, sy, aim_z, glossy, energy) in STUDIO_RIG + list(over.get('_add', ())):
        if name in over and over[name] is None:
            continue
        ch = over.get(name) or {}
        where = ch.get('where', where)
        energy = ch.get('energy', energy)
        nm = 'Studio' + name
        if kind == 'rel':
            a, e, dist = where
            h = math.radians(psi + a)
            el = math.radians(e)
            loc = (ax + dist * math.cos(el) * math.cos(h), ay + dist * math.cos(el) * math.sin(h), az + dist * math.sin(el))
            o = _area(coll, nm, loc, energy, sx, sy, target=(ax, ay, aim_z), glossy=glossy)
        elif kind == 'down':          # overhead strip pointing straight down, long side along the car (world Y)
            o = _area(coll, nm, where, energy, sx, sy, glossy=glossy, rotation=(0.0, 0.0, math.pi / 2))
        else:
            if isinstance(aim_z, (tuple, list)):           # full target point
                tgt = tuple(aim_z)
            else:
                tgt = (0.0, where[1] + (0.5 if name == 'CabinD' else 0.0), aim_z)
            o = _area(coll, nm, where, energy, sx, sy, target=tgt, glossy=glossy)
        out.append(o)
    _dome(coll, psi, over.get('_dome', DOME_GAIN), over.get('_dome_profile'),   # r6 sweep (not in the returned list)
          over.get('_dome_rgb'))
    return out


def setup_world(view=None):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    try:
        sc.cycles.use_denoising = True
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.render.film_transparent = False
    # r5: 'Standard' (no tone curve): the photos' saturated orange keeps its hue, gloss black stays black
    # and the highlight lines clip to white like the photos'. AgX lifted the blacks and turned the orange yellow.
    # (r4 asked bl_rna for the transform list, which only holds 'NONE' for this dynamic enum, so it fell back to Filmic)
    try:
        sc.view_settings.view_transform = 'Standard'
    except TypeError:
        pass
    try:
        sc.view_settings.look = 'None'
    except Exception:
        pass
    sc.view_settings.exposure = EXPOSURE
    sc.view_settings.gamma = 1.0
    try:
        sc.cycles.max_bounces = 8
        sc.cycles.glossy_bounces = 4
        sc.cycles.transparent_max_bounces = 8
        sc.cycles.sample_clamp_indirect = 8.0     # no fireflies from glossy bounces at low sample counts
        sc.cycles.blur_glossy = 0.5
    except Exception:
        pass

    # black seamless backdrop: near-black world (a hint of light so the cabin is not pitch black)
    w = sc.world or bpy.data.worlds.new('Studio')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    if bg is None:
        bg = w.node_tree.nodes.new('ShaderNodeBackground')
        out = w.node_tree.nodes.get('World Output') or w.node_tree.nodes.new('ShaderNodeOutputWorld')
        w.node_tree.links.new(bg.outputs[0], out.inputs[0])
    bg.inputs['Color'].default_value = (*WORLD_RGB, 1)
    bg.inputs['Strength'].default_value = 1.0

    _clear_studio()
    coll = _studio_collection()

    # near-black matte floor (contact shadows; nothing bright for the lower panels to mirror)
    me = bpy.data.meshes.new('StudioFloor')
    s = 40.0
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    f = bpy.data.objects.new('StudioFloor', me)
    coll.objects.link(f)
    m = bpy.data.materials.get('StudioFloorMat') or bpy.data.materials.new('StudioFloorMat')
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (FLOOR_ALBEDO, FLOOR_ALBEDO, FLOOR_ALBEDO * 1.1, 1)
    b.inputs['Roughness'].default_value = 0.85
    try:
        b.inputs['Specular IOR Level'].default_value = 0.0
    except Exception:
        pass
    f.data.materials.append(m)
    setup_lights(view)


# ---------------------------------------------------------------------------------------------
# camera
# ---------------------------------------------------------------------------------------------
def view_matrix(loc, ypr):
    yaw, pitch, roll = ypr
    fwd = V((math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)))
    right = fwd.cross(V((0, 0, 1))).normalized()
    up = right.cross(fwd)
    r2 = right * math.cos(roll) + up * math.sin(roll)
    u2 = up * math.cos(roll) - right * math.sin(roll)
    m = Matrix((r2, u2, -fwd)).transposed().to_4x4()
    m.translation = V(loc)
    return m


def resolution(view, width):
    v = VIEWS[view]
    if isinstance(v, dict):
        w, h = v['size']
        if w >= h:
            return width, max(2, int(round(width * h / w)))
        return max(2, int(round(width * w / h))), width
    aspect = v[3]
    return width, int(width * aspect[1] / aspect[0])


def camera(view, width):
    v = VIEWS[view]
    cam = bpy.data.objects.get('RefCam')
    if not cam:
        cd = bpy.data.cameras.new('RefCam')
        cam = bpy.data.objects.new('RefCam', cd)
        bpy.context.scene.collection.objects.link(cam)
    cd = cam.data
    cd.clip_start = 0.02
    cd.clip_end = 200
    cd.shift_x = cd.shift_y = 0.0
    if isinstance(v, dict):
        cd.clip_start = v.get('clip', 0.02)   # >0.02 cuts away a body panel the photographer had opened/removed
        cam.matrix_world = view_matrix(v['loc'], v['ypr'])
        cd.type = 'PERSP'
        cd.sensor_fit = 'HORIZONTAL'
        cd.sensor_width = 36.0
        cd.lens = v['f'] * 36.0
    else:
        loc, tgt, focal, aspect, _ = v
        cam.matrix_world = Matrix.Identity(4)
        cam.location = loc
        d = V(tgt) - V(loc)
        cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        if focal == 0:  # game cockpit: 78 deg vertical field of view
            cd.sensor_fit = 'VERTICAL'
            cd.angle = math.radians(78)
        else:
            cd.sensor_fit = 'AUTO'
            cd.lens = focal
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = resolution(view, width)
    sc.render.resolution_percentage = 100


# ---------------------------------------------------------------------------------------------
# outputs
# ---------------------------------------------------------------------------------------------
def _ref_image(ref):
    from PIL import Image
    p = os.path.join(ROOT, 'ref', ref) if ref else None
    if not p or not os.path.exists(p):
        return None
    return Image.open(p).convert('RGBA')


def compare(ref, out, sheet):
    from PIL import Image
    r = Image.open(out).convert('RGB')
    im = _ref_image(ref)
    if im is None:
        return
    bg = Image.new('RGBA', im.size, (20, 20, 22, 255))
    bg.alpha_composite(im)
    im = bg.convert('RGB')
    h = r.height
    im = im.resize((int(round(im.width * h / im.height)), h), Image.LANCZOS)
    s = Image.new('RGB', (im.width + r.width + 8, h), (255, 255, 255))
    s.paste(im, (0, 0))
    s.paste(r, (im.width + 8, 0))
    s.save(sheet)


def render_mask(path):
    """Silhouette pass: 1 sample, transparent film, studio hidden -> alpha = the car."""
    sc = bpy.context.scene
    coll = bpy.data.collections.get(STUDIO_COLL)
    hidden = [o for o in (coll.objects if coll else []) if o.type != 'LIGHT' and not o.hide_render]
    saved = (sc.cycles.samples, sc.render.film_transparent, sc.cycles.use_denoising, sc.render.filepath,
             sc.render.image_settings.color_mode, sc.cycles.max_bounces, sc.render.filter_size)
    try:
        for o in hidden:
            o.hide_render = True
        sc.cycles.samples = 1
        sc.render.film_transparent = True
        sc.cycles.use_denoising = False
        sc.cycles.max_bounces = 0
        sc.render.filter_size = 0.01
        sc.render.image_settings.color_mode = 'RGBA'
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
    finally:
        for o in hidden:
            o.hide_render = False
        (sc.cycles.samples, sc.render.film_transparent, sc.cycles.use_denoising, sc.render.filepath,
         sc.render.image_settings.color_mode, sc.cycles.max_bounces, sc.render.filter_size) = saved


def _edge(mask, width=1):
    """Boundary pixels of a boolean mask, about `width` px thick."""
    import numpy as np
    m = mask
    er = m.copy()
    for _ in range(max(1, width)):
        e2 = er.copy()
        e2[1:, :] &= er[:-1, :]
        e2[:-1, :] &= er[1:, :]
        e2[:, 1:] &= er[:, :-1]
        e2[:, :-1] &= er[:, 1:]
        er = e2
    return m & ~er


def overlay(ref, out, mask_path, path):
    import numpy as np
    from PIL import Image, ImageDraw
    r = Image.open(out).convert('RGB')
    W, H = r.size
    im = _ref_image(ref)
    if im is None:
        return
    im = im.resize((W, H), Image.LANCZOS)
    photo_alpha = np.array(im)[..., 3] >= 128
    bg = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    bg.alpha_composite(im)
    blend = Image.blend(bg.convert('RGB'), r, 0.5)
    a = np.array(blend)
    lw = max(1, int(round(W / 640)))
    a[_edge(photo_alpha, lw)] = (255, 205, 0)
    if mask_path and os.path.exists(mask_path):
        m = Image.open(mask_path)
        m = (m.split()[-1] if m.mode in ('RGBA', 'LA') else m.convert('L')).resize((W, H))
        a[_edge(np.array(m) >= 128, lw)] = (0, 255, 255)
    o = Image.fromarray(a)
    d = ImageDraw.Draw(o)
    d.rectangle([0, 0, 330, 16], fill=(0, 0, 0))
    d.text((4, 2), 'cyan = render silhouette   yellow = photo', fill=(0, 255, 255))
    o.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blend', default=os.path.join(ROOT, 'out', 'trx_sandrail.blend'))
    ap.add_argument('--views', default='side_right,front_3q_right,front,rear_3q_right,rear,interior_dash,cockpit')
    ap.add_argument('--samples', type=int, default=24)
    ap.add_argument('--width', type=int, default=960, help='image width (photo views: the longer side)')
    ap.add_argument('--tag', default='')
    ap.add_argument('--no-overlay', action='store_true', help='skip the silhouette pass + overlay image')
    ap.add_argument('--threads', type=int, default=0, help='Cycles CPU threads (0 = all)')
    ap.add_argument('--exposure', type=float, default=None, help='override the studio exposure (EV)')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.open_mainfile(filepath=args.blend)
    setup_world()
    sc = bpy.context.scene
    if args.exposure is not None:
        sc.view_settings.exposure = args.exposure
    sc.cycles.samples = args.samples
    if args.threads > 0:
        sc.render.threads_mode = 'FIXED'
        sc.render.threads = args.threads
    rdir = os.path.join(ROOT, 'renders')
    os.makedirs(rdir, exist_ok=True)
    for v in args.views.split(','):
        v = ALIASES.get(v.strip(), v.strip())
        if v not in VIEWS:
            print('unknown view', v, '- known:', ', '.join(VIEWS))
            continue
        camera(v, args.width)
        setup_lights(v)              # r5: the rig turns with the camera (see the studio notes above)
        if args.exposure is not None:
            sc.view_settings.exposure = args.exposure
        out = os.path.join(rdir, f'{args.tag}{v}.png')
        sc.render.filepath = out
        sc.render.image_settings.color_mode = 'RGB'
        bpy.ops.render.render(write_still=True)
        ref = view_ref(v)
        compare(ref, out, os.path.join(rdir, f'{args.tag}compare_{v}.png'))
        if ref and not args.no_overlay:
            mpath = os.path.join(rdir, f'{args.tag}mask_{v}.png')
            render_mask(mpath)
            overlay(ref, out, mpath, os.path.join(rdir, f'{args.tag}overlay_{v}.png'))
        print('rendered', out)


if __name__ == '__main__':
    main()
