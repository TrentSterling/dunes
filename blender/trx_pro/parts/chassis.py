"""Part 'chassis': everything structural plus the exterior lights.

Frame rails + floor pan, roll cage through the spec cage nodes, door / dash / harness bars,
X-brace in the main-hoop plane, the gray cut-out gusset fins behind the B-pillars, rear upper
rails that run back over the side pods into the big rounded multi-tube rear bumper basket, front
clip with shock towers, double-shear clevis tabs at every suspension pivot in spec.py, the front
trapezoid hoop bumper with its V-shield centre plate (hex-mesh windows) and two dual-round LED pods,
roof RC LED light bar (own 'LightBar' group, brackets static), whip-light mounts, roof red LED strips
and the tail-light units in the tail blocks.

Coordinates: +X right, +Y forward, +Z up (metres). Driver on the left (x < 0).
Most pieces are built for the LEFT side and mirrored with mirror_x().

[fix r3] Everything follows spec.py r3: frame rails at FRAME_RAIL_Z, floor pan flush with the rail bottoms,
narrow nose rails carrying F_LOWER_PIVOTS, upper pivot rail over F_UPPER_PIVOTS, rack plate at F_STEER_RACK,
trailing-arm pivot box at R_TRAILING_PIVOT, rear shock towers at R_SHOCK_TOPS, tail lamps at TAIL_LIGHT_XZ /
TAIL_LIGHT_WH on the TAIL_BLOCK_Y[0] face, rear bumper to TAIL_Y, gusset fins up to ROOF_REAR_Z.

Interfaces other parts may read: T1_TOWER / T2_TOWER (upper front rail shock towers, left side; the rail
runs A_PILLAR_FOOT -> T1 -> T2 -> bumper top bar corner), front_shock_tops(), RACK_PLATE_TOP_Z (top of the
steering-rack plate, |x| <= 0.13, y F_STEER_RACK.y +- 0.035), REAR_RAIL (left rear upper rail polyline).
All lights are modelled OFF (as photographed): the light bar face and LED pods do not emit (the game draws
its own lit LED face over 'LightBar'); tail lenses emit 0.15 at most, the 'Tail light brake' strip material
is separate so the game can light it.
"""
import math
import os

import bpy
import bmesh
from mathutils import Vector, Matrix

from common import (M, mat, tube, box, cylinder, lathe, loft, mirror_x, join, place, apply_transform,
                    obj_from_bmesh, uv_project, box_uv, TEX, aligned_matrix)
import spec

V = Vector
RC = spec.CAGE_TUBE_R        # 1.75" cage tube
RF = spec.FRAME_TUBE_R       # 2.00" main frame tube
RS = spec.SMALL_TUBE_R       # 1.25" bracing
RX = 0.0191                  # 1.50" X-brace / bumper inner tubes
HI, MID, LO = 32, 28, 20     # tube() 'sides' -> 18-gon, 16-gon, 12-gon cross-sections

# front shock towers (left side; parts/body.py reads T1_TOWER / T2_TOWER for the hood clearance): nothing on the nose may
# rise above the hood / fender brows. [fix r5] the upper rail ends on the bulkhead hoop (T1). [fix r6] spec r6 moved the
# front shock tops in under the hood beak (coil (-0.222, 1.442, 0.83), bypass (-0.355, 1.50, 0.87)): the r5 trough rail's
# low bend (TROUGH_LOW) sat on the new coil axis. The region behind the shock tops (y 1.30-1.40, |x| 0.25-0.40, z 0.78-0.87)
# is filled by the upper arm's rear leg at bump, the wing's rolled front lip and the finned reservoir, and the beak hem
# (|x| 0.19, z 0.81) sits right inboard of the coil top, so no rail can run from there back to the bulkhead. As in front.png /
# front_3q (triangulated, notes/fix_r6_chassis.md): the outer 'trough' tube rises from the bumper top bar near its swept-back
# corner straight back / in / up to TR_B1 and turns rearward there into the BYPASS TOWER node (TR_BTW); the inner nose tube
# rises beside the beak, runs back along the beak side over the coil top and turns outboard into the same node. The bypass
# eye hangs in a clevis straight under the trough tube (y 1.50), the coilover eye in a clevis straight under the nose
# tube's rear turn - both towers lie on the shocks' upper axis extension, away from their swing (bump / droop) fans.
T1_TOWER = (-0.318, 1.19, 0.86)   # upper front rail end: node on the front bulkhead hoop's top bar (wing underside 0.93)
T2_TOWER = (-0.30, 1.50, 0.900)   # [fix r6] kept for parts/body.py's hood clearance only (no tube runs T1 -> T2 since r5);
                                  # the r6 bypass tower clevis hangs from the trough tube at (-0.296, 1.50, 0.931)
TR_B1 = (-0.268, 1.550, 0.937)    # [fix r6] trough tube's rear bend (front.png u 600 v 395 / front_3q u 916 v 423)
TR_BTW = (-0.330, 1.440, 0.924)   # [fix r6] bypass tower node: trough tube and nose tube end here (over the bypass top)
NOSE_TOWER = (-0.226, 1.452, 0.897)  # [fix r6] nose tube's rear turn, over the coilover top (clevis plates hang from it)


def NOSE_INNER_PTS(by, bz_top):
    """[fix r5] inner nose tube centre line (left): bumper top bar -> up beside the hood beak (top 0.935) -> back along
    the beak side. [fix r6] -> over the coilover top (NOSE_TOWER) -> out into the bypass tower node TR_BTW."""
    return [(-0.175, by - 0.004, bz_top + 0.003), (-0.18, 1.84, 0.935), (-0.20, 1.665, 0.905), (-0.217, 1.52, 0.897),
            NOSE_TOWER, TR_BTW]


# [fix r5] rear cage / shield / fin / door bar hard points (left side)
REAR_BRACE_BEND = (-0.428, -1.06, 1.341)  # rear brace bend: rear.png posts (u 525-545 from v 70 to 330), X top |x| ~0.48
REAR_K_LOW_XZ = (-0.470, 0.905)           # virtual corner: D back -> straight shield leg (at y TAIL_Y + RC)
REAR_TRAY_C = (-0.250, -2.430, 0.632)     # shield bottom corner (rear.png: bottom bar |x| <= 0.25)
# [fix r6] main frame rail front tuck (spec FRONT_CORNER_HALF_W_Z): straight-line knots of the left rail between the
# main-hoop foot run (|x| FRAME_RAIL_X) and the bulkhead corner; R 0.25 bends at both knots. The windshield-hoop leg
# foot sits on the tucked rail at y 0.82 (body / interior: read these instead of (-FRAME_RAIL_X, 0.82, FRAME_RAIL_Z))
RAIL_TUCK = [(-spec.FRAME_RAIL_X, 0.48, spec.FRAME_RAIL_Z), (-0.597, 0.74, spec.FRAME_RAIL_Z)]
A_HOOP_FOOT = (round(-0.597 + (0.597 - 0.575) * (0.82 - 0.74) / (1.15 - 0.74), 4), 0.82, spec.FRAME_RAIL_Z)
FIN_OFF = spec.CAGE_TUBE_R + 0.003        # fin centre plane inboard of the B-pillar centre line
FIN_TIP = (-0.4615, -1.12)                # (x, y) where the fin's top edge meets the pod ridge (z from rear_deck_z)
DOOR_BAR_X = -0.712                       # door bar run (inner face -0.690)
# [fix r5] raked V-plate (front.png / front_3q back-projected)
PLATE_TIP = (1.656, 0.485)                # (y, z) of the plate tip (front face, centre)
PLATE_TOP_YZ = (1.925, 0.86)              # (y, z) a second point of the front face plane (under the top tube)
PLATE_T = 0.007
PLATE_HW0, PLATE_HW_K = 0.050, 0.2755     # half-width at the tip, growth per metre of height (top hw ~0.157)
PLATE_TOP_Z = 0.872
PLATE_WIN_UP = ((0.724, 0.068), (0.816, 0.095))   # (z, half-width) bottom / top of the upper window
PLATE_WIN_LO = ((0.536, 0.022), (0.692, 0.057))   # lower window
RACK_PLATE_D, RACK_PLATE_YC = 0.054, 1.683        # rack plate depth / centre y (front edge behind the plate)

# [fix r3] nose hard points (left side), derived from spec.F_LOWER_PIVOTS / F_UPPER_PIVOTS. The lower nose rails run
# 58 mm inboard of the lower-arm pivots (the arm's 24 mm sleeve keeps ~8 mm of air to the 2" rail) at the pivot
# height, so the double-shear tabs stick straight out; nothing hangs below z 0.48 ahead of y 1.6 (front.png).
_FLP = spec.F_LOWER_PIVOTS
NOSE_REAR = (_FLP[0][0] + 0.058, _FLP[0][1], max(_FLP[0][2] + 0.005, 0.495))
NOSE_FRONT = (_FLP[1][0] + 0.058, _FLP[1][1], max(_FLP[1][2] + 0.007, 0.507))
NOSE_TIP_Y = 1.836                       # front U-turn of the nose rails ([fix r5] 2.4 cm shorter: just ahead of the
                                         # front lower-arm clevis, it shows under the raked plate's tip)
# upper pivot rail: straight fore-aft tube 65 mm over the upper-arm pivots, the tabs hang down to them
UPR_X = spec.F_UPPER_PIVOTS[0][0] + 0.01
UPR_Z = spec.F_UPPER_PIVOTS[0][2] + 0.065
# [fix r6] front bumper from front.png + front_3q triangulated (two cameras, rays agree to <= 7 mm): the top bar is straight
# across the nose (y 1.925) and sweeps back 9 cm to tight (~3 cm) top corners; the side tubes rake back as they fall in to the
# lower corners under the light pods' outer edges; the lower bars run forward / in to the V-plate's edges. Top bar 1.25"
# (RB_TOP), sides + lower bars ~1.06" (RB_LOW) - photo ~3.0 / ~2.4 cm. r5 was a flat D-loop hoop (1.75") at y 1.92.
BUMPER_Y, BUMPER_TOP_Z = 1.925, 0.886
BUMPER_FLAT_HW = 0.17                       # straight middle of the top bar (|x|), then a R 0.25 sweep back to the corner
BUMPER_CORNER = (-0.371, 1.836, 0.879)      # top corner (front.png u 505 v 460 / front_3q u 953 v 464)
BUMPER_LOW_CORNER = (-0.300, 1.765, 0.745)  # lower corner (front.png u 560 v 546 / front_3q u 963 v 531)
BUMPER_LOW_Z = 0.748                        # lower bar end on the V-plate edge
RB_TOP, RB_LOW = spec.SMALL_TUBE_R, 0.0135
# [fix r6] LED pods: face 12 x 7 cm centred at POD_C (triangulated; r5 had them 12.7 cm further forward, flush with the
# top bar) - they sit behind the top bar on the lower bars
POD_C = (-0.212, 1.800, 0.809)
RACK_PLATE_TOP_Z = spec.F_STEER_RACK[2] - 0.041
BULKHEAD_X = -0.565                      # front bulkhead hoop legs (steered tyre sweeps to |x| 0.61 at y 1.18)


def front_shock_tops():
    """Front shock top pivots (left side) the clevises must hold: parts/suspension.py's F_COIL_TOP / F_BYP_TOP
    (what the shock eyes are actually built at) when it has them under the hood, else spec.F_SHOCK_TOPS."""
    tops = None
    try:
        import importlib
        sus = importlib.import_module('suspension')
        cand = [getattr(sus, n, None) for n in ('F_COIL_TOP', 'F_BYP_TOP')]
        if all(c is not None for c in cand):
            tops = [tuple(float(c[i]) for i in range(3)) for c in cand]
    except Exception:
        tops = None
    if not tops or max(t[2] for t in tops) > 1.02:
        tops = [tuple(p) for p in spec.F_SHOCK_TOPS]
    return tops


# ------------------------------------------------------------------ small math helpers

def mx(p):
    return (-p[0], p[1], p[2])


def lerp3(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def at_z(a, b, z):
    """Point on segment a-b at height z."""
    return lerp3(a, b, (z - a[2]) / (b[2] - a[2]))


def at_y(a, b, y):
    return lerp3(a, b, (y - a[1]) / (b[1] - a[1]))


def mirror_pts(pts):
    """Left-side polyline -> full symmetric polyline (left ... right)."""
    return list(pts) + [mx(p) for p in reversed(pts)]


def fillet_path(points, radii, steps=8):
    """[fix r4] Round the corners of a 3D polyline with true circular arcs (pipe-bender look).

    radii: one bend radius for every corner or a list with one radius per interior corner (0 = sharp).
    Two neighbouring bends may share a segment up to 96 % of its length (both shrink proportionally when they
    would overlap); `steps` arc segments per 90 deg of sweep."""
    pts = [V(p) for p in points]
    n = len(pts)
    if n < 3:
        return pts
    if not isinstance(radii, (list, tuple)):
        radii = [radii] * (n - 2)
    seg = [(pts[i + 1] - pts[i]).length for i in range(n - 1)]
    info = [None] * n
    tt = [0.0] * n
    for i in range(1, n - 1):
        R = radii[i - 1]
        d1, d2 = pts[i - 1] - pts[i], pts[i + 1] - pts[i]
        if R <= 0 or seg[i - 1] < 1e-6 or seg[i] < 1e-6:
            continue
        d1.normalize(); d2.normalize()
        ang = d1.angle(d2)
        if ang > math.pi - 1e-3 or ang < 1e-3:
            continue
        info[i] = (d1, d2, ang)
        tt[i] = R / math.tan(ang / 2)
    for j in range(n - 1):                      # segment j joins corners j and j+1
        need = tt[j] + tt[j + 1]
        if need > 0.96 * seg[j]:
            f = 0.96 * seg[j] / need
            tt[j] *= f
            tt[j + 1] *= f
    out = [pts[0]]
    for i in range(1, n - 1):
        b = pts[i]
        if info[i] is None or tt[i] <= 1e-6:
            out.append(b.copy())
            continue
        d1, d2, ang = info[i]
        t = tt[i]
        Rr = t * math.tan(ang / 2)
        p1, p2 = b + d1 * t, b + d2 * t
        cen = b + (d1 + d2).normalized() * (Rr / math.sin(ang / 2))
        v1, v2 = p1 - cen, p2 - cen
        sweep = v1.angle(v2)
        k = max(2, int(math.ceil(steps * sweep / (math.pi / 2))))
        for s_ in range(k + 1):
            u = s_ / k
            q = (v1 * math.sin((1 - u) * sweep) + v2 * math.sin(u * sweep)) / math.sin(sweep)
            out.append(cen + q)
    out.append(pts[-1])
    return out


def nearest_on(path, p):
    """Closest point on a polyline (list of Vectors) to p."""
    p = V(p)
    best, bd = None, 1e9
    for a, b in zip(path, path[1:]):
        ab = b - a
        L2 = ab.length_squared
        t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, (p - a).dot(ab) / L2))
        q = a + ab * t
        d = (q - p).length
        if d < bd:
            best, bd = q, d
    return tuple(best)


# ------------------------------------------------------------------ materials

def mats():
    return {
        'cage': M('cage'),
        # [fix r5] lead decision: the front bumper / nose tubes and the rear bumper basket (D, V, tray, lower rails) are
        # the lighter 'arm' grey (spec.COLORS['arm_gray']); roll cage, frame and the rear cage stay dark gunmetal
        'arm': M('arm'),
        'dark': M('steel_dark'),
        'black': M('satin_black'),
        'gloss': M('gloss_black'),
        'alu': M('alu'),
        'chrome': M('chrome'),
        'polished_tl': M('polished'),
        # [fix r6] LED pods OFF: geometric faceted reflector cones, the facets alternating two warm satin-metal tones
        # (front.png / front_3q: the reflectors read bright champagne, L ~150-230, in any light)
        # [fix r6] arbiter colours on real faceted geometry (the darker #9c8a66 test read as an empty grey cup)
        'facet_a': mat('LED pod reflector warm', '#d6c39c', metal=0.1, rough=0.35),
        'facet_b': mat('LED pod reflector light', '#f2eadb', metal=0.1, rough=0.35),
        'podlens': mat('LED pod lens', '#ffffff', rough=0.03, alpha=0.06, clearcoat=1.0, clearcoat_rough=0.02),
        'glass': M('glass'),
        # [fix r5] the spoiler LED strips' lens (the game lights 'Tail light lens dark' with the brake lamps): smoked
        # near-black lens with ~10 small red LED dots (chassis_spoiler_led.png), gloss rough .1 + clear coat 1.0
        'red': (mat('Tail light lens dark', tex='chassis_spoiler_led.png', emit_tex='chassis_spoiler_led_emit.png',
                    emit_strength=0.15, rough=0.10, clearcoat=1.0, clearcoat_rough=0.05) if ensure_spoiler_led()[0] else
                mat('Tail light lens dark', '#1c0304', rough=0.10, clearcoat=1.0, emit='#ff1a12', emit_strength=0.15)),
        'mesh': M('mesh_grille'),
        # [fix r4] bumper window inserts: OPAQUE silver perforated screen (chassis_perf_mesh.png, 3.3 mm pitch at 0.04 m
        # per tile); the r3 MASK hex mesh over a black backing read as a dark hole in the game. [fix r6] light bars
        # #d0d3d6, ~35 % open, bright metal (.8 / rough .25: at .9 it mirrored the black Cycles studio and read L ~60) with a
        # punched-hole normal relief so it sparkles (photo L 150-210)
        'hexmesh': mat('Bumper perf mesh', tex='chassis_perf_mesh.png', normal='chassis_perf_mesh_n.png', normal_strength=0.6,
                       metal=0.8, rough=0.25),
        'gusset': mat('Gusset gray paint', '#6d7176', metal=0.3, rough=0.5),
        # [fix r5] the V-shield with a small engraved SANDLINE between the windows. [fix r6] slate powder coat #4a4e58,
        # metal .3 / rough .45 (photo median (60, 60, 67); the r5 #343948 rendered (24, 26, 31))
        'plate': mat('Bumper plate', tex='chassis_bumper_plate.png', metal=0.3, rough=0.45),
        'plate_plain': mat('Bumper plate plain', '#4a4e58', metal=0.3, rough=0.45),
        # [fix r3] floor pan top: satin aluminium (matches the interior floor)
        'floor': mat('Floor pan satin alu', '#9a9da1', metal=1.0, rough=0.45),
    }


# ------------------------------------------------------------------ geometry helpers

def sharpen(o, deg):
    """Smooth shading with sharp edges above `deg` (common.shade()'s call is missing in bpy 5.1)."""
    me = o.data
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=math.radians(deg))
    except Exception:
        pass
    return o


def B(*a, sharp=25, **k):
    """box() with proper sharp edges."""
    return sharpen(box(*a, **k), sharp)


def round_poly(pts, r, steps=4):
    """Round the corners of a closed 2D polygon. r: radius or per-corner list (0 = sharp)."""
    out = []
    n = len(pts)
    for i in range(n):
        ri = r[i] if isinstance(r, (list, tuple)) else r
        b = V((pts[i][0], pts[i][1], 0))
        if ri <= 0:
            out.append((b.x, b.y))
            continue
        a = V((pts[i - 1][0], pts[i - 1][1], 0))
        c = V((pts[(i + 1) % n][0], pts[(i + 1) % n][1], 0))
        d1, d2 = a - b, c - b
        l1, l2 = d1.length, d2.length
        d1.normalize(); d2.normalize()
        ang = d1.angle(d2)
        if ang < 1e-3 or ang > math.pi - 1e-3:
            out.append((b.x, b.y))
            continue
        t = min(ri / math.tan(ang / 2), l1 * 0.49, l2 * 0.49)
        rr = t * math.tan(ang / 2)
        p1, p2 = b + d1 * t, b + d2 * t
        cen = b + (d1 + d2).normalized() * (rr / math.sin(ang / 2))
        a1 = math.atan2(p1.y - cen.y, p1.x - cen.x)
        a2 = math.atan2(p2.y - cen.y, p2.x - cen.x)
        da = a2 - a1
        while da > math.pi:
            da -= 2 * math.pi
        while da < -math.pi:
            da += 2 * math.pi
        for s in range(steps + 1):
            aa = a1 + da * s / steps
            out.append((cen.x + rr * math.cos(aa), cen.y + rr * math.sin(aa)))
    return out


def circle2d(cx, cy, r, n=16, start=0.0):
    return [(cx + r * math.cos(start + 2 * math.pi * k / n), cy + r * math.sin(start + 2 * math.pi * k / n))
            for k in range(n)]


def plate(name, outer, holes, origin, ux, uy, thick, material, uv=None, centered=True):
    """Flat plate (with holes) from 2D outlines in the (ux, uy) frame at origin, thickness along ux x uy.

    uv: optional fn(x2d, y2d) -> (u, v) for the faces (planar mapping in the plate frame)."""
    o = V(origin)
    ux = V(ux).normalized()
    uy = V(uy).normalized()
    n = ux.cross(uy).normalized()
    base = o - n * (thick / 2 if centered else 0.0)
    bm = bmesh.new()
    edges = []
    for loop in [outer] + list(holes):
        vs = [bm.verts.new(base + ux * x + uy * y) for (x, y) in loop]
        edges += [bm.edges.new((vs[i], vs[(i + 1) % len(vs)])) for i in range(len(vs))]
    bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges, normal=n)
    faces = list(bm.faces)
    ret = bmesh.ops.extrude_face_region(bm, geom=faces)
    newv = [g for g in ret['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=n * thick, verts=newv)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if uv:
        lay = bm.loops.layers.uv.new('UVMap')
        for f in bm.faces:
            for lp in f.loops:
                d = lp.vert.co - o
                lp[lay].uv = uv(d.dot(ux), d.dot(uy))
    return sharpen(obj_from_bmesh(name, bm, material, angle=30), 25)


def quad(name, corners, material, uvs=None):
    """Single double-vertex quad (one-sided, normal by winding)."""
    bm = bmesh.new()
    vs = [bm.verts.new(V(c)) for c in corners]
    f = bm.faces.new(vs)
    if uvs:
        lay = bm.loops.layers.uv.new('UVMap')
        for lp, uvv in zip(f.loops, uvs):
            lp[lay].uv = uvv
    return obj_from_bmesh(name, bm, material, smooth=False)


def cyl(name, r, h, origin, zdir, material, segs=12, r2=None, cap=True):
    o = cylinder(name, r, h, material=material, segments=segs, r2=r2, cap=cap)
    place(o, origin, zdir)
    return sharpen(o, 40 if segs >= 10 else 65)


def weld(o, dist=1e-5):
    """Merge coincident vertices (closes lofted rings) and make the normals consistent and outward."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return o


def inward_normals(o):
    """Make an open lathe cup face its axis (inside visible) - local Z is the axis."""
    me = o.data
    me.update()
    score = 0.0
    for p in me.polygons:
        c = p.center
        radial = V((c.x, c.y, 0))
        if radial.length > 1e-6:
            score += p.normal.dot(radial.normalized())
    if score > 0:
        me.flip_normals()
    return o


def inward_normals_world(o, c, ax):
    """[fix r6] Make an open cup (transform applied, axis ax through c) face its axis (inside visible)."""
    me = o.data
    me.update()
    ax = V(ax).normalized()
    score = 0.0
    for p in me.polygons:
        d = V(p.center) - V(c)
        radial = d - ax * d.dot(ax)
        if radial.length > 1e-6:
            score += p.normal.dot(radial.normalized())
    if score > 0:
        me.flip_normals()
    return o


def bolt(p, a, length, mt, r=0.0060):
    """Bolt along axis a through p: hex head on +a end, nut on -a end."""
    p = V(p); a = V(a).normalized()
    out = [cyl('bolt', r, length, p, a, mt['alu'], segs=8)]
    out.append(cyl('bolt_head', r * 1.75, 0.007, p + a * (length / 2 - 0.0035), a, mt['alu'], segs=6))
    out.append(cyl('bolt_nut', r * 1.75, 0.008, p - a * (length / 2 - 0.004), a, mt['dark'], segs=6))
    return out


def clevis(name, pivot, axis, base, mt, gap=0.05, w=0.046, th=0.006, material=None, bolt_len=None, base_hw=None):
    """Double-shear tab pair welded to the tube whose axis passes through `base`, bolt at `pivot`."""
    p = V(pivot); a = V(axis).normalized(); b = V(base)
    d = p - b
    d = d - a * d.dot(a)
    L = max(d.length, 0.02)
    u = d.normalized() if d.length > 1e-6 else (V((1, 0, 0)) - a * a.x).normalized()
    v = a.cross(u)
    arc = [(w / 2 * math.cos(t), w / 2 * math.sin(t)) for t in
           [-math.pi / 2 + math.pi * k / 8 for k in range(9)]]
    bh = w * 0.62 if base_hw is None else base_hw
    outline = [(-L, -bh), (-w * 0.25, -w / 2)] + arc + [(-w * 0.25, w / 2), (-L, bh)]
    objs = []
    for s in (-1, 1):
        org = p + a * s * (gap / 2 + th / 2)
        objs.append(plate(name, outline, [], org, u, v, th, material or mt['cage']))
    objs += bolt(p, a, bolt_len or (gap + 2 * th + 0.018), mt)
    return objs


# ------------------------------------------------------------------ textures (fallbacks)

def _tex_path(name):
    return os.path.join(TEX, name)


def ensure_lightbar_textures():
    """Make chassis_lightbar_face/emit.png (dual-row reflector cups) unless they exist."""
    face, emit = _tex_path('chassis_lightbar_face.png'), _tex_path('chassis_lightbar_emit.png')
    if os.path.exists(face) and os.path.exists(emit):
        return
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except Exception:
        return
    W, H = 2048, 128
    im = Image.new('RGB', (W, H), (14, 14, 15))
    em = Image.new('RGB', (W, H), (0, 0, 0))
    d, de = ImageDraw.Draw(im), ImageDraw.Draw(em)
    n = 40
    pitch = W / n
    for row, cyy in enumerate((H * 0.30, H * 0.72)):
        for k in range(n):
            cx = pitch * (k + 0.5) + (pitch * 0.5 if row else 0)
            if cx > W - pitch * 0.4:
                continue
            r = H * 0.19
            for i in range(14, 0, -1):          # chrome reflector: bright rim -> dark centre
                rr = r * i / 14
                g = int(60 + 150 * (i / 14) ** 1.6)
                d.ellipse([cx - rr, cyy - rr, cx + rr, cyy + rr], fill=(g, g, g + 4))
            d.ellipse([cx - r * 0.22, cyy - r * 0.22, cx + r * 0.22, cyy + r * 0.22], fill=(255, 238, 190))
            de.ellipse([cx - r * 0.30, cyy - r * 0.30, cx + r * 0.30, cyy + r * 0.30], fill=(255, 250, 240))
    # thin black frame
    d.rectangle([0, 0, W - 1, 5], fill=(8, 8, 8)); d.rectangle([0, H - 6, W - 1, H - 1], fill=(8, 8, 8))
    im.save(face)
    em.filter(ImageFilter.GaussianBlur(1.2)).save(emit)


def _font(size):
    from PIL import ImageFont
    for f in ('/usr/share/fonts/opentype/inter/Inter-ExtraBoldItalic.otf',
              '/usr/share/fonts/opentype/inter/InterDisplay-BoldItalic.otf',
              '/usr/share/fonts/truetype/freefont/FreeSansBoldOblique.ttf'):
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                pass
    return ImageFont.load_default()


TEX_VERSION = 'v7'      # bump to repaint the chassis_* textures below


def _stale(path):
    """True when a chassis texture is missing or was painted by an older TEX_VERSION (kept in a PNG text chunk)."""
    if not os.path.exists(path):
        return True
    try:
        from PIL import Image
        return Image.open(path).text.get('chassis_tex') != TEX_VERSION
    except Exception:
        return True


def _save(img, path):
    from PIL.PngImagePlugin import PngInfo
    info = PngInfo()
    info.add_text('chassis_tex', TEX_VERSION)
    img.save(path, pnginfo=info)


def ensure_smoked_lightbar():
    """chassis_lightbar_smoked.png: the RC bar face as it looks OFF behind its smoked gloss cover - near-black,
    chrome cups barely visible, light-grey RC logo (~80 mm wide) in the centre (front.png, front_3q_right.png).
    Painted for the 1.005 x 0.046 m face quad (2048 x 128 px: 2038 px/m across, 2783 px/m up)."""
    out = _tex_path('chassis_lightbar_smoked.png')
    if not _stale(out):
        return out
    try:
        import numpy as np
        from PIL import Image, ImageDraw, ImageFilter
    except Exception:
        return None
    W, H = 2048, 128
    src = _tex_path('light_bar_face.png')
    if not os.path.exists(src):
        ensure_lightbar_textures()
        src = _tex_path('chassis_lightbar_face.png')
    if os.path.exists(src):
        a = np.asarray(Image.open(src).convert('RGB').resize((W, H)), dtype=np.float32) / 255.0
    else:
        a = np.full((H, W, 3), 0.06, np.float32)
    lum = a.mean(axis=2, keepdims=True)
    # smoked tint: [fix r3] ~12 % of the original value (p95 39 -> ~22): near-uniform gloss black with only the
    # RC badge reading; slightly cool, the hot LED chips knocked right down
    # [fix r4] darker still: the LED cells / reflector cups top out at ~11 sRGB (critic: <= 10-12, barely visible)
    k = min(0.12, 0.036 / max(float(np.percentile(a, 99.5)), 1e-3))
    # [fix r6] cups at ~25 % of that contrast: a glossy smoked slab where the reflector cells barely show (front.png)
    sm = a * k * 0.25
    sm = sm * np.array([0.96, 0.98, 1.04], np.float32) + 0.008
    img = Image.fromarray((np.clip(sm, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    # blank the centre badge of the source texture: plain smoked cover there
    cx = W // 2
    bw = int(0.105 * 2038)
    d.rectangle([cx - bw // 2, 6, cx + bw // 2, H - 7], fill=(5, 5, 6))
    # RC logo: drawn upright on a big canvas, then squeezed to 80 x 34 mm in texture pixels
    big = Image.new('L', (900, 420), 0)
    bd = ImageDraw.Draw(big)
    f = _font(340)
    bb = bd.textbbox((0, 0), 'RC', font=f)
    bd.text(((900 - (bb[2] - bb[0])) // 2 - bb[0], (420 - (bb[3] - bb[1])) // 2 - bb[1]), 'RC', font=f, fill=255)
    bbox = big.getbbox() or (0, 0, 900, 420)
    big = big.crop(bbox)
    # [fix r4] badge ~56 x 22 mm (front.png: 59 x 21 mm; ~30 % of the bar height), mid grey ~150 (was 70 x 30 mm, 190)
    lw, lh = int(0.056 * 2038), int(0.022 * 2783)
    logo = big.resize((lw, lh), Image.LANCZOS)
    col = Image.new('RGB', (lw, lh), (150, 152, 156))
    img.paste(col, (cx - lw // 2, H // 2 - lh // 2 - 6), logo)
    _save(img.filter(ImageFilter.GaussianBlur(0.6)), out)
    return out


def ensure_perf_mesh():
    """[fix r4] chassis_perf_mesh.png: opaque silver perforated screen for the bumper V-plate windows. One tile = 40 x 40 mm,
    12 staggered holes across (3.3 mm pitch). [fix r6] light bars #d0d3d6 with a brighter punched rim, ~35 % open (r5 ~45 %),
    plus chassis_perf_mesh_n.png: tangent-space normal map of the punched holes (bars flat, holes dished) so the bright
    metal sparkles like the photo's screen (front.png L 150-210)."""
    out, nout = _tex_path('chassis_perf_mesh.png'), _tex_path('chassis_perf_mesh_n.png')
    if not _stale(out) and not _stale(nout):
        return out
    try:
        import numpy as np
        from PIL import Image, ImageFilter
    except Exception:
        return None
    N = 512
    n = 12
    p = N / n                                  # hole pitch in px (horizontal)
    rows = int(round(N / (p * math.sqrt(3) / 2)))
    rows += rows % 2                           # even number of rows so the stagger tiles
    py = N / rows
    rad = p * math.sqrt(0.35 * (py / p) / math.pi)   # open area pi r^2 / (p * py) = 0.35
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    best = np.full((N, N), 1e9, np.float32)
    for j in range(-1, rows + 1):
        off = (p / 2) if j % 2 else 0.0
        cy = (j + 0.5) * py
        for i in range(-1, n + 2):
            cx = (i + 0.5) * p + off
            d = np.hypot(xx - cx, yy - cy)
            best = np.minimum(best, d)
    hole = np.clip((rad + 0.8 - best) / 1.6, 0, 1)          # anti-aliased hole mask
    base = np.array([0xd0, 0xd3, 0xd6], np.float32) / 255.0
    edge = np.clip(1 - np.abs(best - rad) / 2.5, 0, 1)       # brighter punched edge
    col = np.minimum(base[None, None, :] * (1 + 0.10 * edge[..., None]), 1.0)
    dark = np.array([14, 14, 15], np.float32) / 255.0
    col = col * (1 - hole[..., None]) + dark * hole[..., None]
    _save(Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)), out)
    # height: 1 on the bars, rounding down into each hole over ~2 px (punched lip), 0 inside
    h = np.clip((best - rad + 2.0) / 3.0, 0, 1)
    h = h * h * (3 - 2 * h)
    h = np.asarray(Image.fromarray((h * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255.0
    gx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5
    gy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5
    k = 2.2
    nx, ny, nz = -gx * k, gy * k, np.ones_like(h)           # image rows run down: +v is up
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    nm = np.stack([nx / ln, ny / ln, nz / ln], axis=-1) * 0.5 + 0.5
    _save(Image.fromarray((np.clip(nm, 0, 1) * 255).astype(np.uint8)), nout)
    return out


def ensure_bumper_plate():
    """[fix r5] chassis_bumper_plate.png: the raked V-plate's dark blue-black powder coat (#343948, front.png after its cool
    grade) with a small ENGRAVED 'SANDLINE' between the two windows: ~75 x 13 mm letters only ~+20 L over the base with a
    1 px dark inner edge. Plate coordinates x -0.25..0.25, s 0..0.50 m (s = distance up the plate from its tip),
    2048 px/m."""
    out = _tex_path('chassis_bumper_plate.png')
    if not _stale(out):
        return out
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageChops
    except Exception:
        return None
    N = 1024
    ppm = N / PLATE_TEX_M
    base = (0x4a, 0x4e, 0x58)            # [fix r6] slate (was #343948)
    im = Image.new('RGB', (N, N), base)
    big = Image.new('L', (1400, 300), 0)
    bd = ImageDraw.Draw(big)
    f = _font(260)
    bb = bd.textbbox((0, 0), 'SANDLINE', font=f)
    bd.text(((1400 - (bb[2] - bb[0])) // 2 - bb[0], (300 - (bb[3] - bb[1])) // 2 - bb[1]), 'SANDLINE', font=f, fill=255)
    big = big.crop(big.getbbox() or (0, 0, 1400, 300))
    lw, lh = int(0.075 * ppm), int(0.013 * ppm)
    logo = big.resize((lw, lh), Image.LANCZOS)
    cx, cy = N // 2, int(N - TATUM_S * ppm)
    x0, y0 = cx - lw // 2, cy - lh // 2
    # engraved: letter face a little lighter (+~20 L), a 1 px dark rim on the upper-left inner edge (cut shadow)
    im.paste(Image.new('RGB', (lw, lh), (0x5c, 0x61, 0x6c)), (x0, y0), logo)
    edge = ImageChops.subtract(logo, ImageChops.offset(logo, 1, 1))
    im.paste(Image.new('RGB', (lw, lh), (0x2c, 0x2f, 0x37)), (x0, y0), edge)
    _save(im.filter(ImageFilter.GaussianBlur(0.4)), out)
    return out


PLATE_TEX_M = 0.50       # [fix r5] the plate texture covers 0.50 x 0.50 m of plate (x -0.25..0.25, s 0..0.50)
TATUM_S = 0.278          # distance up the bumper plate (from its tip) of the SANDLINE lettering (world z ~0.711)


def ensure_tail_lens():
    """[fix r5] chassis_tail_lens.png (+ _emit): the tail-light lens as it looks OFF (rear.png): smoked near-black lens
    (#120304) with ONE vertical column of 6 small red LED dots (#8a0f0f, ~4 mm) in the inboard third (u ~0.76; on both
    lamps u grows inboard), over the lower 70 % of the lens; a very faint rim. u across the lens width, v up its height
    (spec.TAIL_LIGHT_WH, 3.2 px/mm). The emit map has the dots only (the game lights them at night)."""
    out, emo = _tex_path('chassis_tail_lens.png'), _tex_path('chassis_tail_lens_emit.png')
    if not _stale(out) and not _stale(emo):
        return out, emo
    try:
        import numpy as np
        from PIL import Image, ImageFilter
    except Exception:
        return None, None
    LW_, LH_ = spec.TAIL_LIGHT_WH
    W, H = 192, int(round(192 * LH_ / LW_))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    u = (xx + 0.5) / W                  # 0 .. 1 across (inboard at u = 1)
    v = 1.0 - (yy + 0.5) / H            # 0 .. 1 up
    base = np.array([0x12, 0x03, 0x04], np.float32) / 255.0
    img = np.ones((H, W, 3), np.float32) * base
    img *= (0.90 + 0.20 * v)[..., None]
    emit = np.zeros((H, W, 3), np.float32)
    dot = np.array([0x8a, 0x0f, 0x0f], np.float32) / 255.0
    ux = TAIL_DOT_U
    for k in range(6):
        vz = 0.06 + (k + 0.5) * 0.64 / 6
        r = np.hypot((u - ux) * LW_, (v - vz) * LH_)
        m = np.clip((0.0021 - r) / 0.0005, 0, 1)
        img = img * (1 - m[..., None]) + dot * m[..., None]
        emit += (np.exp(-(r / 0.0022) ** 2))[..., None] * np.array([1.0, 0.10, 0.06])
    du = np.minimum(u, 1 - u) * LW_
    dv = np.minimum(v, 1 - v) * LH_
    rim = np.exp(-(np.maximum(np.minimum(du, dv) - 0.0005, 0) / 0.0012) ** 2)
    img += rim[..., None] * np.array([0.05, 0.008, 0.008])
    _save(Image.fromarray((np.clip(emit, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7)), emo)
    _save(Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.4)), out)
    return out, emo


TAIL_DOT_U = 0.76        # u of the tail-lamp LED dot column (inboard third)


SL_W, SL_H = 0.142, 0.009           # [fix r5] spoiler LED strip lens (rear.png: slim strip ~15 cm x 1.5 cm with its bezel)
SL_BZ = 0.003                       # black bezel margin round the lens


def ensure_spoiler_led():
    """[fix r5] chassis_spoiler_led.png (+ _emit): the spoiler's slim tail-light strip as it looks OFF (rear.png):
    smoked lens #1c0304 with 10 evenly spaced 6 mm red LED dots (#7a0c0c) on the centre line. u along the strip,
    v up (3.6 px/mm). The emit map has the dots only."""
    out, emo = _tex_path('chassis_spoiler_led.png'), _tex_path('chassis_spoiler_led_emit.png')
    if not _stale(out) and not _stale(emo):
        return out, emo
    try:
        import numpy as np
        from PIL import Image, ImageFilter
    except Exception:
        return None, None
    W, H = 512, 32
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    x = ((xx + 0.5) / W - 0.5) * SL_W           # metres along the strip
    y = (0.5 - (yy + 0.5) / H) * SL_H           # metres up
    img = np.ones((H, W, 3), np.float32) * (np.array([0x1c, 0x03, 0x04], np.float32) / 255.0)
    img *= (0.90 + 0.20 * (y / SL_H + 0.5))[..., None]
    emit = np.zeros((H, W, 3), np.float32)
    dot = np.array([0x7a, 0x0c, 0x0c], np.float32) / 255.0
    n = 10
    pitch = SL_W / n
    for k in range(n):
        cx = -SL_W / 2 + (k + 0.5) * pitch
        r = np.hypot(x - cx, y)
        m = np.clip((0.0030 - r) / 0.0006, 0, 1)
        img = img * (1 - m[..., None]) + dot * m[..., None]
        emit += (np.exp(-(r / 0.0028) ** 2))[..., None] * np.array([1.0, 0.10, 0.06])
    _save(Image.fromarray((np.clip(emit, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)), emo)
    _save(Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.4)), out)
    return out, emo


# ------------------------------------------------------------------ build

def tail_rake(z):
    """Lean of the body's tail-block rear face (parts/body.py: bottom 12 mm forward of the top)."""
    z0, z1 = spec.TAIL_BLOCK_Z
    return 0.012 * (z1 - z) / (z1 - z0)


def shear_to_tail_face(o):
    """Bake the transform and lean the object like the tail-block rear face (y += tail_rake(z))."""
    apply_transform(o)
    for v in o.data.vertices:
        v.co.y += tail_rake(v.co.z)
    o.data.update()
    return o


def _roof_trees(C):
    """BVH trees of the body's built roof / spoiler objects (build.py builds 'body' before 'chassis'); [] without it."""
    from mathutils.bvhtree import BVHTree
    out = []
    for o in C.groups.get('static', []):
        if o.type != 'MESH' or not o.name.startswith('body_roof'):
            continue
        mw = o.matrix_world.copy() if o.parent else o.matrix_basis.copy()
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.transform(mw)
        out.append(BVHTree.FromBMesh(bm))
        bm.free()
    return out


def spoiler_spec_face(x, z):
    """[fix r6] spec r6 spoiler rear face without the body: trailing edge (top lip) at SPOILER_TRAIL_Y, arched back
    in plan (quadratic from the centre to the blade ends at SPOILER_HALF_W[1]); the face drops near-vertically (a
    slight forward lean, 1.5 cm per 10 cm) from SPOILER_TOP_Z to SPOILER_FACE_BOTTOM_Z. Returns (y, outward normal)."""
    k = min(1.0, (x / spec.SPOILER_HALF_W[1]) ** 2)
    yt = spec.SPOILER_TRAIL_Y[0] + (spec.SPOILER_TRAIL_Y[1] - spec.SPOILER_TRAIL_Y[0]) * k
    lean = 0.15
    return yt + lean * max(0.0, spec.SPOILER_TOP_Z - z), V((0.0, -1.0, -lean)).normalized()


def spoiler_face_bottom_z(x):
    k = min(1.0, (x / spec.SPOILER_HALF_W[1]) ** 2)
    return spec.SPOILER_FACE_BOTTOM_Z[0] + (spec.SPOILER_FACE_BOTTOM_Z[1] - spec.SPOILER_FACE_BOTTOM_Z[0]) * k


def spoiler_face(C, x, z):
    """[fix r4] (y, outward normal) of the spoiler's rear face at (x, z): ray-cast against the body's built roof when
    it is already in the build context, else the spec r6 face (spoiler_spec_face). [fix r6] ray window y -0.72..-0.44
    (the r6 blade's trailing edge is at y -0.58..-0.62)."""
    try:
        best = None
        for t in _roof_trees(C):
            hit = t.ray_cast(V((x, -1.20, z)), V((0, 1, 0)), 1.0)
            if hit[0] is not None and hit[1].y < -0.1 and (best is None or hit[0].y < best[0].y):
                best = hit
        if best is not None and -0.72 < best[0].y < -0.44:
            n = best[1].normalized()
            if n.y > 0:
                n = -n
            if abs(n.x) < 0.5:
                return best[0].y, V((0.0, n.y, n.z)).normalized()
    except Exception:
        pass
    return spoiler_spec_face(x, z)


def roof_skin_z(C, x, y, default):
    """[fix r6] height of the body's roof / spoiler top skin at (x, y) (downward ray-cast), else default."""
    try:
        best = None
        for t in _roof_trees(C):
            hit = t.ray_cast(V((x, y, 2.5)), V((0, 0, -1)), 1.5)
            if hit[0] is not None and (best is None or hit[0].z > best[0].z):
                best = hit
        if best is not None and 1.40 < best[0].z < 1.70:
            return best[0].z
    except Exception:
        pass
    return default


def polyline_at_y(pts, y):
    """Point at height-independent station y on a polyline (first segment that spans it)."""
    for a, b in zip(pts, pts[1:]):
        if min(a[1], b[1]) <= y <= max(a[1], b[1]) and abs(b[1] - a[1]) > 1e-9:
            return at_y(a, b, y)
    return min(pts, key=lambda p: abs(p[1] - y))


def split_at_y(path, y):
    """Split a polyline at every crossing of station y (pieces share the crossing point)."""
    out, cur = [], [V(path[0])]
    for a, b in zip(path, path[1:]):
        a, b = V(a), V(b)
        if (a.y - y) * (b.y - y) < 0:
            c = a + (b - a) * ((y - a.y) / (b.y - a.y))
            cur.append(c)
            out.append(cur)
            cur = [c.copy()]
        cur.append(b)
    out.append(cur)
    return out


def build(C):
    TUBES.clear()
    PATHS.clear()
    ensure_perf_mesh()
    ensure_bumper_plate()
    ensure_tail_lens()
    mt = mats()
    S = []          # static, both sides already
    Lf = []         # left-side static objects to mirror

    def T(name, pts, r=RC, sides=MID, bend=None, m=None, side=False, steps=8):
        """Bent tube. bend: radius for every corner (default 3 r) or a per-corner list (fillet_path)."""
        fp = fillet_path(pts, 3.0 * r if bend is None else bend, steps)
        return TP(name, fp, r, sides, m, side)

    def TP(name, fp, r=RC, sides=MID, m=None, side=False):
        """Tube along an already filleted centre line."""
        fp = [V(p) for p in fp]
        o = sharpen(tube(name, fp, r, m or mt['cage'], bend=0, sides=sides), 55)
        (Lf if side else S).append(o)
        PATHS[name] = fp
        TUBES.append((name, [tuple(p) for p in fp], r, side))
        return o

    def corner_gusset(name, corner, d1, d2, L1, L2=None, side=True, th=0.004, m=None):
        """Small welded triangular gusset in the plane of two tubes meeting at `corner` (centreline point),
        legs along d1/d2, concave free edge."""
        L2 = L2 or L1
        u, w = V(d1).normalized(), V(d2).normalized()
        nn = u.cross(w).normalized()
        e2 = nn.cross(u).normalized()

        def to2(q):
            return (q.dot(u), q.dot(e2))
        P1, P2 = to2(u * L1), to2(w * L2)
        cpt = ((P1[0] + P2[0]) * 0.36, (P1[1] + P2[1]) * 0.36)
        hyp = [((1 - t) ** 2 * P1[0] + 2 * t * (1 - t) * cpt[0] + t * t * P2[0],
                (1 - t) ** 2 * P1[1] + 2 * t * (1 - t) * cpt[1] + t * t * P2[1]) for t in [k / 6 for k in range(7)]]
        outline = [(0.0, 0.0)] + hyp
        outline = round_poly(outline, [0] + [0.006] + [0] * 5 + [0.006], steps=2)
        o = plate(name, outline, [], V(corner), u, e2, th, m or mt['cage'])
        (Lf if side else S).append(o)
        return o

    A_F, A_T = spec.A_PILLAR_FOOT, spec.A_PILLAR_TOP
    B_F, B_T = spec.B_PILLAR_FOOT, spec.B_PILLAR_TOP
    RX0, RZ = spec.FRAME_RAIL_X, spec.FRAME_RAIL_Z
    MHY = spec.MAIN_HOOP_Y
    FZ = spec.FLOOR_Z

    # ============================================================ FRAME
    # [fix r3] one bent 2" loop: rear radius-rod post -> main rail (kinks inboard right at the main-hoop foot so the
    # trailing-arm pivot box sits outboard of it) -> main rail at FRAME_RAIL_Z -> in along the front bulkhead (lower
    # bar, inside the steered tyre's sweep) -> narrow nose rails under the lower-arm pivots -> U-turn behind the
    # bumper plate -> other side.
    post_x = -0.36
    post = (post_x, -1.225, 0.42)
    nr, nf = NOSE_REAR, NOSE_FRONT
    # rear end: diagonal from the hoop foot in to x = post_x, then straight back into the post (the rear radius-rod
    # inner eye at (-0.42, -1.20, 0.44) sits outboard of it); front: bulkhead bar ends inboard of the lower-arm
    # rear sleeve
    # [fix r4] the bulkhead bar's inner end follows the rail height (was a hard-coded z 0.478 that dipped below the
    # raised 0.50 rail), level with the lower of the rail / nose-rail heights
    # [fix r4] rear corner: the rail turns inboard 1 cm ahead of the main-hoop foot (the leg still lands on it) and runs
    # nearly transverse to x -0.60 before the diagonal to the post, so the trailing-arm sleeve at R_TRAILING_PIVOT
    # (r 0.032 about (y -0.85, z 0.51), x -0.749..-0.691) keeps ~1 mm of air to the 2" rail (it overlapped 6 mm)
    # [fix r6] front tuck (spec FRONT_CORNER_HALF_W_Z: 0.633 at z 0.54, front.png shows only background outside it):
    # the rail turns in from y 0.48 (two R 0.25 bends) to |x| 0.597 at y 0.74, then runs nearly straight to the
    # bulkhead corner, so its outer face stays inside the outline ahead of y ~0.72 (was |x| 0.70 to y 1.02)
    loop_l = [post, (post_x, -1.06, 0.452), (-0.600, -0.815, RZ - 0.010), (-RX0, MHY + 0.010, RZ)] + RAIL_TUCK + \
             [(BULKHEAD_X - 0.01, 1.15, RZ), (-0.100, 1.162, min(RZ, nr[2]) - 0.004), nr, nf, (nf[0], NOSE_TIP_Y, nf[2])]
    lrad = [0.085, 0.05, 0.025, 0.25, 0.25] + [0.085] * 5
    T('frame_main_loop', mirror_pts(loop_l), RF, HI, bend=lrad + lrad[::-1])
    FRAME_FRONT_L[:] = loop_l[3:7]

    def frame_rail_x(y):
        """|x| of the (left) main frame rail centre line at y (straight-segment polyline; bends are R 0.25)."""
        return -polyline_at_y(loop_l[3:7], y)[0]
    nose_pts = loop_l[6:]

    def nose_rail_at_y(y):
        """Centre of the lower nose rail at a given y (left side)."""
        return polyline_at_y(nose_pts, y)

    # floor stiffeners: flat hat-channel strips right under the pan (8 mm deep, never below z 0.438)
    for y in (0.62, 0.05, -0.45):
        S.append(B('floor_xm', (1.0, 0.05, 0.006), (0, y, FZ - 0.004 - 0.003), material=mt['dark'], bevel=0.002))
    T('floor_xm_rear', [(-0.68, -0.82, RZ), (0.68, -0.82, RZ)], 0.019, LO)      # at rail height under the hoop

    # floor pan (satin aluminium top at FLOOR_Z, flush with the rail bottoms), outline inside the rails
    # [fix r6] the pan's side edge follows the tucked rail 2.8 cm inside its centre line
    pfl = [(-(frame_rail_x(y_) - 0.028), y_) for y_ in (0.47, 0.745)] + [(-0.548, 1.130)]
    pan_o = pfl + [(-0.540, 1.150), (-0.540, 1.205), (0.540, 1.205), (0.540, 1.150)] + \
        [(-x_, y_) for x_, y_ in pfl[::-1]] + [(0.672, MHY + 0.012), (0.548, -0.915), (-0.548, -0.915),
                                              (-0.672, MHY + 0.012)]
    S.append(plate('floor_pan', round_poly(pan_o, 0.01, steps=2), [], (0, 0, FZ - 0.002), (1, 0, 0), (0, 1, 0), 0.004,
                   mt['floor'], uv=lambda a, b: (a, b)))
    # footwell front wall (front bulkhead plate) from the pan up to the bulkhead hoop top bar
    fw_top = 0.865                      # just over the bulkhead hoop's top bar (z 0.86)
    S.append(B('footwell_wall', (1.08, 0.004, fw_top - FZ), (0, spec.FRONT_BULKHEAD_Y + 0.025, (FZ + fw_top) / 2),
               material=mt['dark']))

    # ============================================================ ROLL CAGE
    # main hoop: floor -> B-pillar foot -> B-pillar top -> across the roof rear -> mirror
    # [fix r4] foot 5 mm ahead of MAIN_HOOP_Y: the leg's back face cleared the trailing-arm sleeve (pivot y -0.85,
    # front face y -0.818) by -0.9 mm at the spec position; +4 mm now
    mh_floor = (-RX0, MHY + 0.005, RZ)
    T('main_hoop', mirror_pts([mh_floor, B_F, B_T]), RC, HI, bend=0.09, steps=10)
    # windshield hoop: rail -> A-pillar foot -> A-pillar top -> across the roof front -> mirror.
    # [fix r4] A_PILLAR_FOOT moved in to |x| 0.63: the pillar is nearly vertical in front view; tight 3r bend into the
    # roof bar at A_PILLAR_TOP (was one 0.11 m radius everywhere), gentle 0.10 m kink at the cowl (hidden in the dash)
    a_floor = A_HOOP_FOOT                              # [fix r6] on the tucked rail (|x| 0.593; was 0.70)
    DEBUG['a_floor'] = [a_floor]
    T('windshield_hoop', mirror_pts([a_floor, A_F, A_T]), RC, HI, bend=[0.10, 3 * RC, 3 * RC, 0.10], steps=10)
    WH, MH = PATHS['windshield_hoop'], PATHS['main_hoop']
    # tubes that end on a hoop corner end on its BENT centre line (the corner point itself lies outside the bend,
    # where the end cap stuck out of the tube)
    A_F2, A_T2, B_T2 = nearest_on(WH, A_F), nearest_on(WH, A_T), nearest_on(MH, B_T)
    # roof side rails + centre roof bow ([fix r4] the roof tapers in plan: B_PILLAR_TOP |x| 0.56, A_PILLAR_TOP 0.60)
    roof_l = [A_T2, B_T2]
    T('roof_rail', roof_l, RC, HI, side=True)
    rb = polyline_at_y(roof_l, 0.0)
    T('roof_bow', [rb, mx(rb)], RC, MID)
    # door top (belt) rail and the vertical door post at the front of the door opening
    belt_l = [A_F2, B_F]
    T('belt_rail', belt_l, RC, HI, side=True)
    # [fix r4] the door post is 1.5" (the equal-diameter junction with the belt rail left a z-fighting sliver beside the
    # driver's left hand) and both its ends sit on the other tubes' centre lines
    # [fix r6] parallel to the A-pillar, ~4-5 cm behind it in plan (front_3q / side: roof rail y 0.40 -> belt rail
    # y 0.62, photo line (-0.61, 0.40, 1.43) -> (-0.66, 0.62, 1.11))
    door_post_bot = polyline_at_y(belt_l, 0.62)
    dp_top = V(polyline_at_y(roof_l, 0.40))
    DEBUG['door_post'] = [tuple(dp_top), tuple(door_post_bot)]
    T('door_post', [tuple(dp_top), door_post_bot], RX, HI, side=True)
    # [fix r5] mid door bar: bends out right behind the A-pillar leg and runs at x -0.712 (inner face -0.690, inside the
    # door card volume; interior CARD_X -0.676) to the main-hoop leg, so it no longer shows across the door quilting
    db_f, db_r = at_z(A_F, a_floor, 0.76), at_z(B_F, mh_floor, 0.76)
    # [integration r6] the bar reaches x -0.712 only at y 0.46 (was db_f.y - 0.15 = 0.634): body r6 tucks the front of
    # the door in (skin inner face x -0.728 @y .54, -0.697 @.62, -0.682 @.70, z .76) and the old run poked 3 cm out
    # through the door skin at y .54-.70. Now >= 1.2 cm inside the skin; in front of y ~.52 it crosses the door-card /
    # dash-end slot at z .74-.78 (48 deg below the driver's eye: outside the 78 deg cockpit view)
    T('door_bar', [db_f, (DOOR_BAR_X, 0.46, 0.76), (DOOR_BAR_X, db_r[1] + 0.08, 0.76), db_r], RC, LO,
      bend=0.08, side=True)
    # dash bar between the A-pillar legs, inside the dash
    dz = 0.95
    d_l = at_z(A_F, a_floor, dz)
    T('dash_bar', [d_l, mx(d_l)], RC, MID)
    # centre windshield post roof front -> cowl -> dash bar. [fix r6] 1.5" (front.png / interior_dash: as thick as the
    # bumper's inner tubes); same path. Gaps: rear-view mirror clamp 1.6 cm / housing 2.9 cm, cowl vents 1.0 cm, enters
    # the dash below z 1.0 (brow z 1.115 stays in front of it)
    T('windshield_post', [(0, 0.45, spec.A_PILLAR_TOP[2]), (0, 0.735, 1.065), (0, d_l[1], dz)], RX, MID, bend=0.05)
    # harness bar between the main hoop legs ([fix r5] the X-brace no longer lies in the main-hoop plane: see REAR CAGE)
    hb_z = 1.00
    hb_l = at_z(B_F, mh_floor, hb_z)
    T('harness_bar', [hb_l, mx(hb_l)], RC, HI)
    # small welded corner gussets: harness bar under-side, door post top (both sides of the post)
    corner_gusset('gus_harness', hb_l, (1, 0, 0), V(mh_floor) - V(B_F), 0.085)
    corner_gusset('gus_doorpost', dp_top, (0, -1, 0), V(door_post_bot) - dp_top, 0.075)
    corner_gusset('gus_doorpost', dp_top, (0, 1, 0), V(door_post_bot) - dp_top, 0.06)
    # dash bar to A-pillar legs (top side)
    corner_gusset('gus_dash', d_l, (1, 0, 0), V(A_F) - V(a_floor), 0.07)

    # ============================================================ REAR UPPER RAIL + REAR BUMPER (D / SHIELD)
    # [fix r4] one continuous bent centre line per side: B-pillar -> back under the pod shoulder -> in and up through the
    # tail block, beside the lamp, out of its rear face at z ~1.23 -> the bumper's top run falls ~12 deg going back ->
    # one large bend (R 0.25) down into the near-vertical back (tube back face at TAIL_Y, apex z ~0.93).
    # [fix r5] rear.png shield: below the apex the legs sweep in along a straight ~40 deg diagonal (rear view) to the
    # bottom corners (+-0.25, -2.43, 0.632); the bottom bar is short (|x| <= 0.25) and 3 cm lower. The centre line is
    # split inside the tail blocks (y -1.99, hidden): rail = cage gunmetal, bumper basket = the lighter arm grey.
    ty = spec.TAIL_Y
    tby0, tby1 = spec.TAIL_BLOCK_Y
    ZRAIL = 1.212          # under the r4 pod shoulder (|x| 0.67, y -0.92..-1.33): top 1.234, >= 1.6 cm under the skin;
                           # 1.6 cm over the coilover collars (top 1.174), outboard of the shock caps (|x| <= 0.617)
    ZEXIT = 1.232          # leaves the tail-block rear face (side photo 1.23)
    zr = ZEXIT
    XT = -0.484            # beside the lamp housing (inner edge |x| 0.509): 3 mm of air
    g_bot = at_z(B_T, B_F, 1.125)
    g_tip = (-0.668, -0.92, ZRAIL)
    yb = ty + RC                                           # centre line of the vertical back
    k_top = (-0.522, yb, ZEXIT - 0.215 * (tby0 - yb))      # virtual corner: top run / back
    k_low = (REAR_K_LOW_XZ[0], yb, REAR_K_LOW_XZ[1])        # virtual corner: back / straight shield leg
    tray_c = REAR_TRAY_C                                   # bottom corner of the shield
    rear_l = [g_bot, g_tip, (-0.670, -1.33, ZRAIL), (-0.598, -1.56, ZRAIL + 0.006), (XT - 0.004, tby1, ZEXIT - 0.002),
              (XT, tby0, ZEXIT), k_top, k_low, tray_c]
    rad = [0.10, 0.10, 0.12, 0.12, 0.10, 0.25, 0.10, 0.05]
    full = fillet_path(mirror_pts(rear_l), rad + rad[::-1], 10)
    parts_ = split_at_y(full, -1.99)
    TP('rear_upper_rail', parts_[0], RC, HI, side=True)
    TP('rear_bumper_d', parts_[1], RC, HI, m=mt['arm'])
    PATHS['rear_upper_loop'] = full
    REAR_RAIL[:] = rear_l
    RUL = [p for p in full if p.x < 0]

    def rail_at_y(y):
        return polyline_at_y(rear_l[1:6], y)

    def loop_at_z(z, path=None, ymax=-2.30):
        """Point on the bent bumper D (left half, behind ymax) at height z, on its upper (top -> back) branch."""
        path = path or RUL
        cand = [(a, b_) for a, b_ in zip(path, path[1:]) if a.y < ymax and b_.y < ymax and (a.z - z) * (b_.z - z) <= 0]
        a, b_ = cand[0]
        t = (z - a.z) / (b_.z - a.z) if abs(b_.z - a.z) > 1e-9 else 0.0
        return tuple(a + (b_ - a) * t)

    # ============================================================ REAR CAGE OVER THE ENGINE BAY  [fix r5]
    # spec r5 (rear.png, rear_3q, seat_closeup): rail-to-rail cross tube at REAR_XBAR_YZ (moved from y -1.83); a rear
    # brace per side from the roof's rear corner (main-hoop bend) back to REAR_BRACE_END on the cross tube, with ONE
    # gentle bend at y -1.06 so it passes >= 5 mm inboard of the body pod's inner ridge (|x| 0.459, z 1.28-1.345 behind
    # y -1.05); the big X from straight 1.5" arms, each from one brace (at y -0.79) to the OTHER side's X_BRACE_BOT on
    # the cross tube - it spans over the engine cover, seen in front of the striped cover from behind.
    xb_y, xb_z = spec.REAR_XBAR_YZ
    xr = rail_at_y(xb_y)
    T('rear_deck_xbar', [(xr[0] + 0.008, xb_y, xb_z), (-xr[0] - 0.008, xb_y, xb_z)], RC, MID)
    rbe = spec.REAR_BRACE_END
    T('rear_brace', [B_T2, REAR_BRACE_BEND, (rbe[0], rbe[1], xb_z)], RX, HI, bend=0.30, side=True, steps=10)
    BRP = PATHS['rear_brace']
    x_top = polyline_at_y(BRP, spec.X_BRACE_TOP[1])
    x_bot = spec.X_BRACE_BOT
    T('x_brace_a', [x_top, mx(x_bot)], RX, MID)           # left top -> right bottom (suspension reads this name)
    T('x_brace_b', [mx(x_top), x_bot], RX, MID)
    DEBUG['x_top'] = [tuple(x_top)]
    # [fix r4] second arc, nested ~4.5 cm inside the D (side photo / rear_3q: two parallel tubes on the arc): off the
    # cross tube (T joint, [fix r5] now at y -1.68), down along the tail block's inner wall bottom (rear.png x ~-0.45,
    # z ~1.16), level to y -2.40, R 0.09 bend down into a near-vertical back at y -2.493, onto the shield's leg
    inner_end = loop_at_z(0.80)
    inner_l = [(-0.448, xb_y, xb_z), (-0.448, -1.93, 1.163), (-0.449, -2.40, 1.158),
               (-0.452, ty + 0.067, 1.04), (-0.440, ty + 0.067, 0.90), inner_end]
    T('rear_inner_loop', inner_l, RX, MID, bend=[0.05, 0.06, 0.09, 0.05, 0.05], side=True, steps=10, m=mt['arm'])
    # V crossbar (rear.png): from the D at z ~1.11 down to a short flat centre in the rear plane
    V_MID_Z = 0.935                                        # rear.png at y -2.53: 0.935-0.944
    v_end = loop_at_z(1.11)
    v_l = [v_end, (-0.145, ty + 0.022, V_MID_Z)]
    T('rear_v_bar', mirror_pts(v_l), RX, MID, bend=0.07, m=mt['arm'])
    # [fix r5] shield braces: from the V bar's flat ends DOWN and OUTWARD to the bottom corners (rear.png)
    tray_top = (-0.145, ty + 0.022, V_MID_Z)
    tray_bot = (tray_c[0] + 0.030, tray_c[1], tray_c[2])
    T('rear_diag', [tray_top, tray_bot], RX, MID, side=True, m=mt['arm'])
    # lower rear rails: shield bottom corner -> forward -> over the half shaft -> radius-rod post top. Level stretch at
    # y -1.82..-1.66 between the engine-mount bush (top z 0.64) and the front exhaust primaries (bottom ~0.685).
    # [fix r6] rear.png shows nothing but the D leg and the diagonal at each bottom corner: the rail now leaves the
    # corner straight forward in the rear camera's shadow of the diagonal (|x| 0.22 -> 0.205, z ~0.62, until y -2.23,
    # 2.5 cm behind the timing cover), steps out round the block's corner at z ~0.665 (hidden behind the engine-front
    # accessories) and joins the old level stretch. 1.5" tube. Rear camera: 4/104 centre-line samples visible (r5 39/122).
    lrr = [(tray_c[0] + 0.015, tray_c[1], tray_c[2]), (-0.220, -2.38, 0.620), (-0.205, -2.23, 0.628),
           (-0.262, -2.13, 0.668), (-0.29, -1.98, 0.665), (-0.425, -1.82, 0.6565), (-0.492, -1.66, 0.6655),
           (post_x, -1.26, 0.80)]
    T('rear_lower_rail', lrr, RX, MID, bend=0.06, side=True, m=mt['arm'])
    # radius-rod post and its brace up to the rear upper rail (behind the shock towers)
    T('rr_post', [(post_x, -1.225, 0.40), (post_x, -1.225, 0.81)], RF, MID, side=True)
    T('rr_brace', [(post_x - 0.005, -1.24, 0.80), rail_at_y(-1.50)], RS, LO, side=True)
    # centre box sitting on the shield's bottom bar (alu grille + two vents), two tabs under it, two straps to the V bar
    bb_y, bb_z = tray_c[1], tray_c[2]
    S.append(B('rear_box', (0.24, 0.08, 0.10), (0, bb_y + 0.004, bb_z + RC + 0.004 + 0.05), material=mt['black'],
               bevel=0.008))
    S.append(B('rear_box_face', (0.20, 0.004, 0.030), (0, bb_y - 0.0365, bb_z + 0.105), material=mt['alu'], bevel=0.002))
    for sx in (-1, 1):
        S.append(B('rear_box_vent', (0.085, 0.004, 0.032), (sx * 0.052, bb_y - 0.0365, bb_z + 0.060), material=mt['mesh']))
        S.append(B('rear_box_tab', (0.03, 0.085, 0.005), (sx * 0.08, bb_y + 0.01, bb_z + RC + 0.0015), material=mt['arm'],
                   bevel=0.001))
        S.append(sharpen(tube('rear_box_strap', [(sx * 0.08, bb_y - 0.025, bb_z + 0.12),
                                                 (sx * 0.08, ty + 0.03, V_MID_Z - RX * 0.6)],
                              0.0055, mt['arm'], sides=12), 55))


    # ============================================================ GUSSET FINS
    # [fix r5] painted alu fin behind each B-pillar (side photo, rear_wheel_sidepod_right, rear.png): a flat plate
    # hugging the pillar's INNER side (its plane contains the pillar direction, FIN_OFF inboard of the pillar centre
    # line) so it stays inside the rear-view outline (|x| ~0.50 under the roof corner, 0.55 at z 1.40); concave top edge
    # (~4 cm sag) from under the roof's rear corner down to the pod's inner ridge, which it meets tangentially at y
    # -1.12 (no free tip); the lower edge runs forward over the rear brace to the pillar at z 1.165; triangular cut-out.
    pF, pT = V(B_F), V(B_T)
    deck = spec.rear_deck_z
    e1 = (pT - pF).normalized()
    tip = V((FIN_TIP[0], FIN_TIP[1], deck(FIN_TIP[1]) - 0.002))
    ao = V((-1.0, 0.0, 0.0))
    ao = (ao - e1 * ao.dot(e1)).normalized()                 # outboard, perpendicular to the pillar
    bo = e1.cross(ao).normalized()
    D_ = tip - pT

    def fin_f(ph):
        n_ = ao * math.cos(ph) + bo * math.sin(ph)
        return n_.dot(D_) + FIN_OFF
    lo_, hi_ = -1.2, 1.2
    if fin_f(lo_) * fin_f(hi_) > 0:
        hi_ = 0.0
    for _ in range(60):
        mid = 0.5 * (lo_ + hi_)
        if fin_f(lo_) * fin_f(mid) <= 0:
            hi_ = mid
        else:
            lo_ = mid
    ph = 0.5 * (lo_ + hi_)
    nrm = (ao * math.cos(ph) + bo * math.sin(ph)).normalized()   # outboard normal of the fin plane
    p0 = pT - nrm * FIN_OFF                                       # a point on the fin's centre plane
    e2 = nrm.cross(e1).normalized()
    if (tip - p0).dot(e2) < 0:
        e2 = -e2

    def on_plane(y, z):
        x = p0.x - (nrm.y * (y - p0.y) + nrm.z * (z - p0.z)) / nrm.x
        return V((x, y, z))

    def to2(p):
        d = V(p) - p0
        return (d.dot(e1), d.dot(e2))

    def pillar_pt(z, off=-0.010):
        """2D point on the plate's front edge (just forward of the pillar centre line) at world height z."""
        return ((z - p0.z) / e1.z, off)

    def behind_pillar(z, d):
        q = at_z(B_F, B_T, z)
        return (q[1] - d, z)

    def bez(t):
        (y0, z0), (yc, zc), (y2, z2) = FIN_TOP
        return ((1 - t) ** 2 * y0 + 2 * t * (1 - t) * yc + t * t * y2, (1 - t) ** 2 * z0 + 2 * t * (1 - t) * zc + t * t * z2)

    def fin_top_z(y):
        best = min((abs(bez(k / 200)[0] - y), bez(k / 200)[1]) for k in range(201))
        return best[1]
    FIN_TOP = [(-0.488, 1.500), (-0.80, tip.z), (tip.y, tip.z)]
    top_yz = [bez(k / 10) for k in range(11)]
    top2 = [to2(on_plane(y, z)) for (y, z) in top_yz]
    # lower edge: from the tip down ~2.5 cm, forward under the deck line, then the diagonal strap to the pillar
    low2 = [to2(on_plane(tip.y + 0.02, tip.z - 0.026)), to2(on_plane(-0.90, 1.300)),
            to2(on_plane(*behind_pillar(1.17, 0.010)))]
    outer = [pillar_pt(1.165), pillar_pt(1.462)] + top2 + low2
    rad = [0.006, 0.012] + [0.0] * len(top2) + [0.015, 0.05, 0.006]
    rad[2] = 0.008
    rad[2 + len(top2) - 1] = 0.010
    outer = round_poly(outer, rad, steps=3)
    # cut-out (rear_3q / rear_wheel photos: a big window, the fin reads as a curved band): front edge 2.8 cm behind the
    # pillar, top edge following the concave top edge 3.6 cm under it back to y -0.93, lower edge a straight strap
    # ~3 cm over the plate's lower edge (most of it below the pod deck)
    cA = behind_pillar(1.23, 0.028)
    cB = behind_pillar(1.445, 0.028)
    top_h = [(y_, fin_top_z(y_) - 0.036) for y_ in (-0.60, -0.70, -0.80, -0.88)]
    cT = (-0.935, fin_top_z(-0.935) - 0.037)
    hole_yz = [cA, cB] + top_h + [cT]
    hole = round_poly([to2(on_plane(*q)) for q in hole_yz], [0.014, 0.016, 0, 0, 0, 0, 0.010], steps=4)
    gus = plate('gusset_fin', outer, [hole], p0, e1, e2, 0.006, mt['gusset'])
    DEBUG['fin'] = [tuple(p0 + e1 * u + e2 * v) for (u, v) in outer + outer[:1]]
    DEBUG['fin_hole'] = [tuple(p0 + e1 * u + e2 * v) for (u, v) in hole + hole[:1]]
    DEBUG['fin_plane'] = (tuple(p0), tuple(nrm))
    _FIN.update(plane=(tuple(p0), tuple(nrm)), top_z=fin_top_z, y_range=(FIN_TOP[2][0], FIN_TOP[0][0]))
    Lf.append(gus)


    # ============================================================ FRONT CLIP
    by, bz_top = BUMPER_Y, BUMPER_TOP_Z
    # [fix r5] raked V-plate (front.png + front_3q back-projected): front face in the plane through the plate tip
    # PLATE_TIP and the bumper top tube, half-width PLATE_HW0 at the tip growing PLATE_HW_K per metre of height
    py0, pz0 = PLATE_TIP
    pdy, pdz = PLATE_TOP_YZ[0] - py0, PLATE_TOP_YZ[1] - pz0
    pup = V((0, pdy, pdz)).normalized()
    pxv = V((1, 0, 0))
    pn = pxv.cross(pup).normalized()          # plate normal (points back and up, into the car)

    def plate_y(z, back=False):
        """y of the plate's front face (or back face) at height z."""
        return py0 + (z - pz0) * pdy / pdz - (PLATE_T / abs(pn.y) if back else 0.0)

    def plate_hw(z):
        return PLATE_HW0 + PLATE_HW_K * (z - pz0)

    def ps(z):  # distance up the plate (from its tip) for a world z
        return (z - pz0) / pup.z
    # front bulkhead hoop (legs on the bulkhead lower bar, |x| <= 0.59 below z 0.75: steered-tyre sweep)
    T('front_bulkhead_hoop', mirror_pts([(BULKHEAD_X, 1.152, RZ), (BULKHEAD_X, 1.19, 0.86)]), RC, MID, bend=0.08)
    # upper pivot rail: bulkhead hoop top bar -> straight fore-aft 65 mm over the upper-arm pivots (|x| <= 0.20,
    # clear of the pedal box / master cylinders and the steering shaft) -> [fix r5] into the raked plate's back face
    zu_end = UPR_Z - 0.006
    upr = [(-0.15, 1.19, 0.86), (UPR_X, 1.25, UPR_Z), (UPR_X, 1.79, UPR_Z), (UPR_X + 0.012, plate_y(zu_end, True) + 0.004, zu_end)]
    T('upper_pivot_rail', upr, RC, MID, bend=0.05, side=True)
    # nose posts + diagonal (lower nose rail <-> upper pivot rail), clear of the arm tabs and the rack; [fix r5] the front
    # post moved back to y 1.60 so it stays behind the raked plate
    p_r = nose_rail_at_y(1.355)
    T('nose_post_r', [(p_r[0], 1.355, p_r[2] + 0.02), (UPR_X, 1.355, UPR_Z - 0.02)], RS, LO, side=True)
    p_f = nose_rail_at_y(1.60)
    T('nose_post_f', [(p_f[0], 1.60, p_f[2] + 0.02), (UPR_X, 1.60, UPR_Z - 0.02)], RS, LO, side=True)
    p_d = nose_rail_at_y(1.42)
    T('nose_diag', [(p_d[0], 1.42, p_d[2] + 0.02), (UPR_X, 1.56, UPR_Z - 0.018)], RS, LO, side=True)
    # (1) the upper front rail runs from the A-pillar foot straight down onto the front bulkhead hoop's top bar (T1,
    #     >= 3.7 cm under the wing skin);
    T1 = T1_TOWER
    T('upper_front_rail', [A_F2, T1], RC, HI, side=True)

    # ============================================================ FRONT BUMPER  [fix r6]
    # top bar (1.25"): straight across the nose, R 0.25 sweep back to tight top corners that turn down 4.5 cm
    corner = V(BUMPER_CORNER)
    lowc = V(BUMPER_LOW_CORNER)
    d_side = (lowc - corner).normalized()
    c_down = corner + d_side * 0.045
    flat_l = (-BUMPER_FLAT_HW, by, bz_top)
    top_l = [tuple(c_down), tuple(corner), flat_l]
    T('front_bumper_top', mirror_pts(top_l), RB_TOP, HI, bend=[0.030, 0.25, 0.25, 0.030], m=mt['arm'], steps=10)
    TOPP = PATHS['front_bumper_top']
    # side + lower bar (smaller tube, sleeved into the top bar's turned-down end): rakes back / in to the lower corner under
    # the pod's outer edge, then forward / in to the V-plate's edge
    zl = BUMPER_LOW_Z
    low_end = (-(plate_hw(zl) + 0.006), plate_y(zl) - 0.010, zl)
    s_start = c_down - d_side * 0.012
    T('front_bumper_low', [tuple(s_start), tuple(lowc), low_end], RB_LOW, MID, bend=0.035, side=True, m=mt['arm'])

    def top_bar_at_x(x):
        """Point on the (left half of the) top bar centre line at a given x."""
        pts = [p for p in TOPP if p.x <= 0.0]
        best = min(range(len(pts) - 1), key=lambda i: 0 if min(pts[i].x, pts[i + 1].x) <= x <= max(pts[i].x, pts[i + 1].x)
                   else 1 + min(abs(pts[i].x - x), abs(pts[i + 1].x - x)))
        a, b_ = pts[best], pts[best + 1]
        t = 0.0 if abs(b_.x - a.x) < 1e-9 else max(0.0, min(1.0, (x - a.x) / (b_.x - a.x)))
        return a + (b_ - a) * t

    # trough tube (1.25", front.png / front_3q): off the top bar's top just inboard of the corner, straight back / in / up
    # to TR_B1, then rearward to the bypass tower node TR_BTW
    tb0 = top_bar_at_x(-0.355)
    tr_start = (tb0.x, tb0.y, tb0.z + RB_TOP * 0.75)
    T('trough_rail', [tr_start, TR_B1, TR_BTW], RS, MID, bend=0.06, side=True, m=mt['arm'])
    UFP = PATHS['trough_rail']

    def front_rail_at_y(y):
        return polyline_at_y(UFP, y)
    # shock-tower brace: from the upper pivot rail up and out to the trough tube (ahead of the shocks)
    for yy_ in (1.68,):
        q_ = front_rail_at_y(yy_)
        T('tower_brace', [(UPR_X - 0.004, yy_, UPR_Z - 0.004), (q_[0] + 0.008, yy_, q_[2] - 0.012)], RS, LO, side=True,
          m=mt['arm'])
    # inner nose tubes (front.png): rise from the bumper top bar beside the hood beak (|x| 0.175-0.20, top 0.935), run back
    # along the beak side over the coilover top and turn outboard into the bypass tower node
    nb0 = top_bar_at_x(-0.175)
    ni = NOSE_INNER_PTS(nb0.y, nb0.z)
    ni[0] = (nb0.x, nb0.y, nb0.z + RB_TOP * 0.6)
    T('nose_inner', ni, RS, MID, bend=[0.07, 0.07, 0.10, 0.035], side=True, m=mt['arm'])
    NIP = PATHS['nose_inner']
    # weld cap over the tower node (both tubes end there)
    Lf.append(sharpen(lathe('tower_node', [(0.0, -RS * 1.05), (RS * 0.75, -RS * 0.95), (RS * 1.06, -RS * 0.3),
                                           (RS * 1.06, RS * 0.3), (RS * 0.75, RS * 0.95), (0.0, RS * 1.05)],
                            mt['arm'], segments=12, loc=TR_BTW), 50))
    # steering-rack plate at spec.F_STEER_RACK on two short uprights from the nose rails; [fix r5] its front edge stays
    # behind the raked plate (y <= 1.71)
    S.append(B('rack_plate', (0.26, RACK_PLATE_D, 0.008), (0, RACK_PLATE_YC, RACK_PLATE_TOP_Z - 0.004), material=mt['cage'],
               bevel=0.002))
    q = nose_rail_at_y(RACK_PLATE_YC)
    z0u, z1u = q[2] + RF - 0.006, RACK_PLATE_TOP_Z - 0.006
    Lf.append(B('rack_upright', (0.03, 0.04, z1u - z0u), (q[0], RACK_PLATE_YC, (z0u + z1u) / 2), material=mt['cage'],
                bevel=0.002))

    # [fix r5] V-plate: one straight-sided trapezoid, raked back from under the top tube to the nose rails, two silver
    # perforated windows (wide upper, narrow lower) and the small engraved SANDLINE between them
    porg = V((0, py0, pz0)) + pn * (PLATE_T / 2)              # centre plane: the front face lies on the spec'd plane
    s_top = ps(PLATE_TOP_Z)
    hw_top = plate_hw(PLATE_TOP_Z)
    outer = round_poly([(-PLATE_HW0, 0), (PLATE_HW0, 0), (hw_top, s_top), (-hw_top, s_top)], [0.014, 0.014, 0.004, 0.004],
                       steps=4)
    (z1b, w1b), (z1t, w1t) = PLATE_WIN_UP
    (z2b, w2b), (z2t, w2t) = PLATE_WIN_LO
    h1 = round_poly([(-w1b, ps(z1b)), (w1b, ps(z1b)), (w1t, ps(z1t)), (-w1t, ps(z1t))], 0.008)
    h2 = round_poly([(-w2b, ps(z2b)), (w2b, ps(z2b)), (w2t, ps(z2t)), (-w2t, ps(z2t))], 0.007)
    half = PLATE_TEX_M / 2
    cp = plate('bumper_plate', outer, [h1, h2], porg, pxv, pup, PLATE_T, mt['plate'],
               uv=lambda a, b: ((half - a) / PLATE_TEX_M, b / PLATE_TEX_M))
    S.append(cp)
    # opaque silver perforated inserts just behind the windows ([fix r6] 3.3 mm pitch at 0.04 m per tile, with relief)
    for hole in (h1, h2):
        cx_ = sum(qq[0] for qq in hole) / len(hole); cy_ = sum(qq[1] for qq in hole) / len(hole)
        grown = [(cx_ + (x - cx_) * 1.10, cy_ + (y - cy_) * 1.10) for (x, y) in hole]
        S.append(plate('bumper_mesh', grown, [], porg + pn * (PLATE_T / 2 + 0.0012), pxv, pup, 0.0015, mt['hexmesh'],
                       uv=lambda a, b: (a / 0.04, b / 0.04)))
    # plate foot (front.png): the tip sits on the nose rails; two small gunmetal ear tabs welded to the rails stick out
    # beside its lower corners (bolts at x +-0.068, z ~0.51) and the plate bolts onto them
    for sx in (-1, 1):
        zb_ = pz0 + 0.026
        ear = round_poly([(sx * 0.040, -0.022), (sx * 0.088, -0.022), (sx * 0.084, 0.018), (sx * 0.048, 0.030)],
                         [0.004, 0.008, 0.010, 0.004], steps=3)
        if sx > 0:
            ear = ear[::-1]
        S.append(plate('plate_ear', ear, [], V((0, plate_y(zb_, True), zb_)) + pn * 0.003, pxv, pup, 0.006, mt['cage']))
        c_ = V((sx * 0.068, plate_y(zb_), zb_))
        S.append(cyl('plate_bolt', 0.0072, 0.005, c_ + pn * (PLATE_T - 0.0025), -pn, mt['alu'], segs=6))

    # [fix r6] LED pods (dual round, OFF), behind the top bar on the lower bars: satin-black rounded housing with a thin
    # (5 mm) front frame; per lamp a shallow faceted polished reflector cone (r 28 mm, 12 mm deep, 14 facets x 2 rings), a
    # black emitter disc with a small LED chip ('LED white', which the game lights) and a clear lens
    pcx, pfy, pcz = POD_C
    pod_w, pod_h, pod_d = 0.124, 0.072, 0.050
    FR = 0.005                          # front frame width
    LIP = 0.007                         # frame depth (lens / reflector face sit this far behind the frame front)
    lip_out = round_poly([(-pod_w / 2, -pod_h / 2), (pod_w / 2, -pod_h / 2), (pod_w / 2, pod_h / 2),
                          (-pod_w / 2, pod_h / 2)], 0.026, steps=5)
    fw_, fh_ = pod_w - 2 * FR, pod_h - 2 * FR
    lip_in = round_poly([(-fw_ / 2, -fh_ / 2), (fw_ / 2, -fh_ / 2), (fw_ / 2, fh_ / 2), (-fw_ / 2, fh_ / 2)],
                        0.0215, steps=5)
    CUP_R, CUP_D, CUP_DX = 0.0272, 0.012, 0.0279
    # the frame ring runs back past the cups' apex (the housing used to start right behind the rims and its front face
    # filled the cups: only a thin ring of facets showed); the housing is the same rounded outline behind it
    RING_D = LIP + CUP_D + 0.002
    Lf.append(plate('pod_lip', lip_out, [lip_in], (pcx, pfy - RING_D / 2, pcz), (1, 0, 0), (0, 0, 1), RING_D,
                    mt['black']))
    body_o = round_poly([(-pod_w / 2 + 0.0015, -pod_h / 2 + 0.0015), (pod_w / 2 - 0.0015, -pod_h / 2 + 0.0015),
                         (pod_w / 2 - 0.0015, pod_h / 2 - 0.0015), (-pod_w / 2 + 0.0015, pod_h / 2 - 0.0015)], 0.0245,
                        steps=5)
    body_d = pod_d - RING_D + 0.001
    Lf.append(plate('pod_body', body_o, [], (pcx, pfy - RING_D + 0.001 - body_d / 2, pcz), (1, 0, 0), (0, 0, 1), body_d,
                    mt['black']))
    yface = pfy - LIP                   # reflector rims / bezel face
    # bezel face (dark satin) between and around the two cups
    cups2 = [circle2d(sx_ * CUP_DX, 0.0, CUP_R + 0.0004, n=28) for sx_ in (-1, 1)]
    Lf.append(plate('pod_bezel', lip_in, [c_[::-1] for c_ in cups2], (pcx, yface - 0.0008, pcz), (1, 0, 0), (0, 0, 1),
                    0.0016, mt['black']))
    for sx_ in (-1, 1):
        cxw = pcx + sx_ * CUP_DX
        # faceted cone: emitter ring -> mid ring -> rim, flat shaded (14 facets, two rings)
        cup = lathe('pod_cup', [(0.0068, -CUP_D), (0.0155, -CUP_D * 0.52), (CUP_R, 0.0)], mt['facet_a'],
                    segments=14)
        cup.data.materials.append(mt['facet_b'])
        place(cup, (cxw, yface, pcz), (0, 1, 0))
        apply_transform(cup)
        inward_normals_world(cup, V((cxw, yface, pcz)), V((0, 1, 0)))
        cc_ = V((cxw, yface, pcz))
        rings_ = {0: [], 1: []}
        for p_ in cup.data.polygons:
            p_.use_smooth = False
            d_ = V(p_.center) - cc_
            rings_[1 if math.hypot(d_.x, d_.z) > 0.0158 else 0].append((math.atan2(d_.z, d_.x), p_.index))
        for rk, lst in rings_.items():
            for rank, (_, pi_) in enumerate(sorted(lst)):
                cup.data.polygons[pi_].material_index = (rank + rk) % 2
        Lf.append(cup)
        Lf.append(cyl('pod_emitter', 0.0070, 0.0016, (cxw, yface - CUP_D + 0.0004, pcz), (0, 1, 0), mt['black'], segs=14))
        Lf.append(B('pod_chip', (0.0032, 0.0012, 0.0032), (cxw, yface - CUP_D + 0.0016, pcz), material=M('led')))
    # clear lens 2 mm behind the frame front, very slightly domed so it catches one highlight
    ylen = pfy - 0.002
    lens_pts = round_poly([(-fw_ / 2 + 0.001, -fh_ / 2 + 0.001), (fw_ / 2 - 0.001, -fh_ / 2 + 0.001),
                           (fw_ / 2 - 0.001, fh_ / 2 - 0.001), (-fw_ / 2 + 0.001, fh_ / 2 - 0.001)], 0.020, steps=5)
    bm = bmesh.new()
    c0 = bm.verts.new((pcx, ylen + 0.0015, pcz))
    ring = [bm.verts.new((pcx + a, ylen, pcz + b)) for (a, b) in lens_pts]
    for i in range(len(ring)):
        bm.faces.new((c0, ring[(i + 1) % len(ring)], ring[i]))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for f in bm.faces:
        if f.normal.y < 0:
            f.normal_flip()
    Lf.append(obj_from_bmesh('pod_lens', bm, mt['podlens'], smooth=True, angle=80))
    # pod foot bracket down onto the lower bar (which passes under the pod's front edge)
    lowp = [V(p) for p in PATHS['front_bumper_low']]
    lb_ = V(nearest_on(lowp, (pcx, pfy - 0.02, pcz - pod_h / 2)))
    zb_top = pcz - pod_h / 2 + 0.002
    zb_bot = lb_.z + RB_LOW * 0.5
    Lf.append(B('pod_bracket', (0.026, 0.020, zb_top - zb_bot), (pcx, min(lb_.y, pfy - 0.012), (zb_top + zb_bot) / 2),
                material=mt['black'], bevel=0.003))


    # ============================================================ SUSPENSION TABS
    cl = []
    for p in spec.F_LOWER_PIVOTS:
        cl += clevis('tab_fl_lower', p, (0, 1, 0), nose_rail_at_y(p[1]), mt, gap=0.05, w=0.036, base_hw=0.026)
    for p in spec.F_UPPER_PIVOTS:
        cl += clevis('tab_fl_upper', p, (0, 1, 0), (UPR_X, p[1], UPR_Z), mt, gap=0.048)
    # [fix r6] front shock towers: the coilover eye hangs in a clevis straight under the nose tube's rear turn, the bypass
    # eye straight under the trough tube - both plates point up along the shock's upper axis extension, >= 75 deg away
    # from the body's swing fan (bump .. droop), so the caps never swing into them
    f_tops = front_shock_tops()
    cpt = V(f_tops[0])
    base_c = nearest_on(NIP, (cpt.x, cpt.y, cpt.z + 0.07))
    cl += clevis('tab_f_shock', f_tops[0], (0, 1, 0), base_c, mt, gap=0.032, w=0.038, base_hw=RS * 0.9)
    bpt = V(f_tops[1])
    base_b = front_rail_at_y(bpt.y)
    cl += clevis('tab_f_shock', f_tops[1], (0, 1, 0), base_b, mt, gap=0.032, w=0.038, base_hw=RS * 0.9)
    DEBUG['f_shock_bases'] = [tuple(base_c), tuple(base_b)]
    # [fix r3] rear trailing-arm pivot box at spec.R_TRAILING_PIVOT: bolt along X, double-shear side plates welded to
    # the main-hoop leg and the rail node, front + top closing plates, floor plate at >= z 0.445; bolt head outboard
    tp = V(spec.R_TRAILING_PIVOT)
    gapT, thT = 0.066, 0.007            # sleeve 58 mm + 4 mm of float each side
    # [fix r4] box rebuilt around the r4 pivot (y -0.85, z 0.51 - right behind the raised rail's corner node): side plates
    # from the hoop leg / rail corner back round the bolt (R 0.042), bottom edge 3 mm under the rail bottom (nothing
    # below z 0.47), top and front closing plates clear of the sleeve (r 0.032), open underneath
    leg = at_z(mh_floor, B_F, tp.z)
    yf = leg[1] + 0.012                       # front edge (on the rail corner, ahead of the leg)
    RB = 0.042
    zb, ztp = tp.z - 0.038, tp.z + RB
    side_o = round_poly([(yf, zb), (tp.y, zb)] + [(tp.y - RB * math.sin(a), tp.z - RB * math.cos(a))
                                                  for a in [math.pi * k / 8 for k in range(1, 8)]]
                        + [(tp.y, ztp), (yf, ztp)], [0.004] + [0] * 9 + [0.004], steps=2)
    for s_ in (-1, 1):
        xs = tp.x + s_ * (gapT / 2 + thT / 2)
        cl.append(plate('trailing_box_side', side_o, [], (xs, 0, 0), (0, 1, 0), (0, 0, 1), thT, mt['cage']))
    xo, xi = tp.x - gapT / 2 - thT, tp.x + gapT / 2 + thT
    cl.append(B('trailing_box_top', (xi - xo, 0.034, 0.006), ((xo + xi) / 2, yf - 0.017, ztp - 0.003), material=mt['cage'],
                bevel=0.0015))
    cl.append(B('trailing_box_front', (xi - xo, 0.006, ztp - zb), ((xo + xi) / 2, tp.y + 0.041, (zb + ztp) / 2),
                material=mt['cage'], bevel=0.0015))
    # pivot bolt: hex head + washer on the outside (side photo: just under the pod's lower edge), nut inside
    bx_o = xo - 0.001
    cl.append(cyl('trailing_bolt', 0.0062, gapT + 2 * thT + 0.016, tp, (1, 0, 0), mt['alu'], segs=10))
    cl.append(cyl('trailing_washer', 0.016, 0.006, V((bx_o - 0.003, tp.y, tp.z)), (1, 0, 0), mt['alu'], segs=14))
    cl.append(cyl('trailing_bolt_head', 0.0125, 0.010, V((bx_o - 0.011, tp.y, tp.z)), (1, 0, 0), mt['alu'], segs=6))
    cl.append(cyl('trailing_nut', 0.0125, 0.010, V((xi + 0.005, tp.y, tp.z)), (1, 0, 0), mt['dark'], segs=6))
    for p in spec.R_RADIUS_ROD_PIVOTS:
        cl += clevis('tab_r_radius', p, (0, 1, 0), (post_x, p[1], p[2]), mt, gap=0.052, w=0.036)   # + misalignment spacers
    # [fix r5] rear shock mounts: the r4 upright tower plates on the rail (|x| 0.67, up to z 1.38) stuck out of the rear
    # silhouette. Now a double-shear plate pair hangs each shock top off the REAR BRACE (|x| ~0.43): level-ish plates
    # (clear of the reservoir caps below the eye), all inside |x| <= 0.585 and open in the body's pod scoop (rear.png:
    # nothing outboard of |x| ~0.57 above z 1.3). Where a plate crosses the gusset fin's tail its lower edge is notched
    # over the fin (>= 6 mm of air).
    gapR, thR = 0.032, 0.006
    fp0, fnr = V(_FIN['plane'][0]), V(_FIN['plane'][1])

    def fin_x(y, z):
        return fp0.x - (fnr.y * (y - fp0.y) + fnr.z * (z - fp0.z)) / fnr.x
    for p in spec.R_SHOCK_TOPS:
        e_ = V(p)
        bq = V(polyline_at_y(BRP, p[1]))
        ex, ez, bx_, bz_ = e_.x, e_.z, bq.x, bq.z
        arc = [(ex - 0.025 * math.sin(math.pi * k / 8), ez - 0.025 * math.cos(math.pi * k / 8)) for k in range(9)]
        low = [(bx_ + 0.012, bz_ - 0.022), (bx_ - 0.016, bz_ - 0.022)]
        rl = [0.003, 0.006]
        ztop_ = max(ez, bz_) + 0.028
        ft = _FIN['top_z'](p[1]) if _FIN['y_range'][0] <= p[1] <= _FIN['y_range'][1] else None
        if ft is not None:
            fx = fin_x(p[1], ft)
            zn = ft + 0.006 + 0.003
            ztop_ = max(ztop_, zn + 0.022)
            low += [(fx + 0.014, zn), (fx - 0.014, zn)]
            rl += [0.006, 0.006]
        low += [(ex + 0.016, ez - 0.024)]
        rl += [0.004]
        outline = low + arc[1:] + [(ex + 0.016, ez + 0.025), (bx_ - 0.006, ztop_), (bx_ + 0.012, ztop_)]
        outline = round_poly(outline, rl + [0] * 8 + [0.004, 0.008, 0.003], steps=2)
        for s_ in (-1, 1):
            yy_ = p[1] + s_ * (gapR / 2 + thR / 2)
            cl.append(plate('tab_r_shock', outline, [], (0, yy_, 0), (1, 0, 0), (0, 0, 1), thR, mt['cage']))
        cl += bolt(p, (0, 1, 0), gapR + 2 * thR + 0.018, mt)
    Lf += cl

    # ============================================================ REAR LIGHTS + ROOF HARDWARE
    # [fix r3] tail lamps at spec.TAIL_LIGHT_XZ / TAIL_LIGHT_WH behind the body's lamp opening in the tail-block rear
    # face (TAIL_BLOCK_Y[0], raked like body.tail_rake): smoked-red lens (off) recessed ~20 mm in a chamfered
    # gloss-carbon pocket, thin bright rim, faint vertical LED strip; the strip has its own material for the game.
    tby = spec.TAIL_BLOCK_Y[0]
    tl_x, tl_z = spec.TAIL_LIGHT_XZ
    LW, LH = spec.TAIL_LIGHT_WH
    RECESS = 0.020
    y_lens = tby + RECESS                       # lens front face (before the rake shear)
    lens_tex, lens_emit = ensure_tail_lens()
    if lens_tex:
        lens_mat = mat('Tail light lens', tex='chassis_tail_lens.png', emit_tex='chassis_tail_lens_emit.png',
                       emit_strength=0.15, rough=0.05, clearcoat=1.0)
        brake_mat = mat('Tail light brake', tex='chassis_tail_lens.png', emit_tex='chassis_tail_lens_emit.png',
                        emit_strength=0.15, rough=0.05, clearcoat=1.0)
    else:
        lens_mat = brake_mat = mt['red']
    lens_uv = lambda a, b: (0.5 + a / LW, 0.5 + b / LH)     # seen from behind, +x is on the right
    lens_out = round_poly([(-LW / 2, -LH / 2), (LW / 2, -LH / 2), (LW / 2, LH / 2), (-LW / 2, LH / 2)], 0.008, steps=3)
    tl = []
    tl.append(plate('tail_lens', lens_out, [], (tl_x, y_lens + 0.003, tl_z), (1, 0, 0), (0, 0, 1), 0.006, lens_mat,
                    uv=lens_uv))
    # [fix r5] the brake strip covers the LED dot column only (inboard third, lower 70 % of the lens)
    sa, sw2 = (TAIL_DOT_U - 0.5) * LW, 0.0028
    sb0, sb1 = (0.05 - 0.5) * LH, (0.71 - 0.5) * LH
    ys_ = y_lens - 0.0006
    tl.append(quad('tail_brake_strip', [(tl_x + sa - sw2, ys_, tl_z + sb0), (tl_x + sa + sw2, ys_, tl_z + sb0),
                                         (tl_x + sa + sw2, ys_, tl_z + sb1), (tl_x + sa - sw2, ys_, tl_z + sb1)],
                   brake_mat, uvs=[lens_uv(sa - sw2, sb0), lens_uv(sa + sw2, sb0), lens_uv(sa + sw2, sb1),
                                   lens_uv(sa - sw2, sb1)]))

    def rrect(w, h, r, y, steps=3):
        pts = round_poly([(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)], r, steps=steps)
        return [(tl_x + a, y, tl_z + b) for (a, b) in pts]
    # chamfered gloss-carbon pocket: from just behind the face plate's opening (79 x 154 mm) in to the lens edge
    BZ_W, BZ_H, BZ_Y = LW + 0.022, LH + 0.022, tby + 0.0062
    rings = [rrect(BZ_W, BZ_H, 0.012, BZ_Y), rrect(LW + 0.003, LH + 0.003, 0.0095, y_lens - 0.0005),
             rrect(LW + 0.003, LH + 0.003, 0.0095, y_lens + 0.012), rrect(BZ_W, BZ_H, 0.012, BZ_Y + 0.006)]
    bez = weld(loft('tail_bezel', rings + [rings[0]], M('carbon'), closed=True, cap=False, angle=30))
    sharpen(bez, 30)
    box_uv(bez, 1.8)     # finer weave on this small part (~5 mm tows)
    tl.append(bez)
    tl.append(B('tail_housing', (LW + 0.012, 0.03, LH + 0.012), (tl_x, y_lens + 0.006 + 0.015, tl_z),
                material=mt['black'], bevel=0.006))
    for o in tl:
        Lf.append(shear_to_tail_face(o))
    # tab between the top rail (beside the lamp, inboard) and the lamp housing
    # [fix r4] the rail now runs right beside the housing (3 mm): a short strap under the rail into the housing side
    tab_x0, tab_x1 = XT + 0.004, tl_x + (LW + 0.012) / 2 - 0.004
    Lf.append(shear_to_tail_face(B('tail_mount', (abs(tab_x1 - tab_x0), 0.02, 0.010), ((tab_x0 + tab_x1) / 2, y_lens + 0.02, zr - RC - 0.003),
                                   material=mt['cage'], bevel=0.002)))
    # [fix r4] spoiler tail lights: two slim LED strips set into the spoiler's rear face at mid-height (rear.png /
    # rear_3q: |x| 0.30..0.455, ~20 mm tall), polished bezel round a dark red lens (OFF). The face is the body's: its
    # position and lean come from the built roof when the body is in the build, else from the body's r4 section.
    # [fix r6] spec r6: strips at |x| 0.30-0.44, z ~1.50-1.505 on the (arched, ~12 cm further back) blade face; the
    # plate is yawed along the face chord between its two ends (face y from the body's built roof, else the spec face)
    SL_Z = 1.503
    xa_, xb_ = -0.30, -(0.30 + SL_W)
    xc = (xa_ + xb_) / 2
    sl_mat = mt['red']             # 'Tail light lens dark' (textured strip, see mats())
    fya, fna = spoiler_face(C, xa_, SL_Z)
    fyb, fnb = spoiler_face(C, xb_, SL_Z)
    fy, fn = spoiler_face(C, xc, SL_Z)
    chord = V((xb_ - xa_, fyb - fya, 0.0)).normalized()          # outboard along the face
    if chord.x > 0:
        chord = -chord
    fpt = V((xc, (fya + fyb) / 2 * 0.5 + fy * 0.5, SL_Z))
    # face normal: horizontal part perpendicular to the chord (backwards), vertical lean from the centre sample
    nh = V((chord.y, -chord.x, 0.0))
    if nh.y > 0:
        nh = -nh
    nrm_ = (nh * math.hypot(fn.y, 0.0) + V((0, 0, fn.z))).normalized()
    up = nrm_.cross(chord).normalized()
    if up.z < 0:
        up = -up
    # [fix r5] slim gloss-black bezel (3 mm margin): the strip reads as one smoked-black line ~1.5 x 15 cm
    bz_o = round_poly([(-SL_W / 2 - SL_BZ, -SL_H / 2 - SL_BZ), (SL_W / 2 + SL_BZ, -SL_H / 2 - SL_BZ),
                       (SL_W / 2 + SL_BZ, SL_H / 2 + SL_BZ), (-SL_W / 2 - SL_BZ, SL_H / 2 + SL_BZ)], 0.0065, steps=3)
    ln_o = round_poly([(-SL_W / 2, -SL_H / 2), (SL_W / 2, -SL_H / 2), (SL_W / 2, SL_H / 2), (-SL_W / 2, SL_H / 2)],
                      0.004, steps=3)
    ux_ = -chord                                  # plate x axis: towards the centre line ...
    nn_ = ux_.cross(up).normalized()
    if nn_.dot(nrm_) < 0:                         # ... with the plate normal out of the face (backwards)
        ux_ = -ux_
        nn_ = -nn_
    Lf.append(plate('spoiler_led_bezel', bz_o, [ln_o], fpt + nn_ * (0.0035 / 2 - 0.0012), ux_, up, 0.0035, mt['gloss']))
    Lf.append(plate('spoiler_led_lens', ln_o, [], fpt + nn_ * (0.002 / 2 - 0.0012), ux_, up, 0.002, sl_mat,
                     uv=lambda a, b: (0.5 + a / SL_W, 0.5 + b / SL_H)))
    DEBUG['spoiler_face'] = (fy, tuple(fn), fya, fyb, tuple(fpt))
    # whip-light mounts (rear.png: aluminium posts standing on the spoiler top at x +-0.35): bracket off the
    # main-hoop roof tube up through the spoiler, black base, aluminium post, knurled black QD collar.
    # [fix r6] the base stands on the body's skin height at (x, y) (downward ray-cast), else the spec r6 blade top
    wx, wy = -0.35, -0.47
    bz_w = B_T[2]                         # [fix r5] the main-hoop roof tube height (spec r5 1.475)
    zs = roof_skin_z(C, wx, wy, spec.ROOF_REAR_Z + (spec.SPOILER_TOP_Z - spec.ROOF_REAR_Z) * 0.12)
    DEBUG['whip_base_z'] = zs
    Lf.append(sharpen(tube('whip_bracket', [(wx, B_T[1], bz_w + RC * 0.7), (wx, wy, bz_w + 0.03),
                                            (wx, wy, zs)],
                           0.008, mt['cage'], sides=12, bend=0.012), 55))
    Lf.append(cyl('whip_base', 0.017, 0.006, (wx, wy, zs + 0.002), (0, 0, 1), mt['black'], segs=14))
    Lf.append(cyl('whip_post', 0.012, 0.042, (wx, wy, zs + 0.026), (0, 0, 1), mt['alu'], segs=14))
    Lf.append(cyl('whip_qd', 0.0135, 0.012, (wx, wy, zs + 0.050), (0, 0, 1), mt['black'], segs=12))

    # ============================================================ LIGHT BAR
    # The bar is OFF in the photos: smoked near-black gloss cover, chrome cups barely visible, light-grey RC logo
    # in the centre. No emission here - the game draws its own lit LED face over the bar when the lights are
    # switched on (car-lights.js hides it again when they are off).
    smoked = ensure_smoked_lightbar()
    if smoked:
        face_mat = mat('Light bar face', tex='chassis_lightbar_smoked.png', rough=0.05, clearcoat=1.0, clearcoat_rough=0.02)
    else:
        face_mat = mat('Light bar face', '#0d0d0f', rough=0.05, clearcoat=1.0)
    LB_L, LB_H, LB_D = 1.05, 0.078, 0.066
    lbx, lby, lbz = 0.0, 0.425, 1.528
    lb = []
    lb.append(B('lightbar_housing', (LB_L, LB_D, LB_H), (lbx, lby - 0.004, lbz), material=mt['gloss'], bevel=0.012,
                segments=3))
    for k in range(5):  # rear heat-sink fins
        lb.append(B('lightbar_fin', (LB_L - 0.06, 0.012, 0.004), (lbx, lby - LB_D / 2 - 0.008, lbz - 0.026 + k * 0.013),
                    material=mt['black']))
    for sx in (-1, 1):
        lb.append(B('lightbar_endcap', (0.022, LB_D + 0.008, LB_H + 0.008), (sx * (LB_L / 2 + 0.006), lby - 0.004, lbz),
                    material=mt['black'], bevel=0.006))
    fy = lby + LB_D / 2 - 0.004 + 0.0012
    fw, fh = LB_L - 0.045, LB_H - 0.032
    lb.append(quad('lightbar_face', [(-fw / 2, fy, lbz - fh / 2), (fw / 2, fy, lbz - fh / 2), (fw / 2, fy, lbz + fh / 2),
                                     (-fw / 2, fy, lbz + fh / 2)][::-1], face_mat,
                   uvs=[(1, 1), (0, 1), (0, 0), (1, 0)]))
    C.add(lb, 'LightBar')
    # end brackets (static): plate from the roof corner up to the bar end, pivot knob
    for sx in (-1, 1):
        bxp = sx * (LB_L / 2 + 0.024)
        br = plate('lightbar_bracket', round_poly([(-0.026, -0.10), (0.026, -0.10), (0.022, 0.0), (-0.022, 0.0)],
                                                  [0.004, 0.004, 0.02, 0.02]),
                   [], (bxp, lby, lbz), (0, 1, 0), (0, 0, 1), 0.006, mt['black'])
        S.append(br)
        S.append(cyl('lightbar_knob', 0.014, 0.018, (bxp + sx * 0.010, lby, lbz), (1, 0, 0), mt['black'], segs=12))
        S.append(B('lightbar_foot', (0.075, 0.045, 0.012), (sx * 0.578, lby, A_T[2] + RC - 0.002), material=mt['black'],
                   bevel=0.002))

    # ============================================================ mirror + register
    for o in Lf:
        S.append(mirror_x(o))
    S += Lf
    C.add(S, 'static')


DEBUG = {}          # filled by build(): outlines for debug overlays
_FIN = {}           # filled by build(): gusset fin plane / top-edge function (the rear shock tabs notch over it)
TUBES = []          # filled by build(): (name, centre-line points, radius, left-side-only) of every tube (debug overlays)
PATHS = {}          # filled by build(): tube name -> filleted centre line (list of Vectors, as built)
REAR_RAIL = []      # filled by build(): left rear upper rail polyline (B-pillar -> tail -> bumper hoop)
FRAME_FRONT_L = []  # filled by build(): left main frame rail polyline from the main-hoop foot to the bulkhead corner
                    # ([fix r6] tucked in to |x| 0.597 at y 0.74; interior / body can read it)
