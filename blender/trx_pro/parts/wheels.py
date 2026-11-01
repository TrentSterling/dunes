"""Part 'wheels': the four spinning wheel assemblies (tyre + black beadlock wheel).

Groups 'Wheel_FL' / 'Wheel_FR' / 'Wheel_RL' / 'Wheel_RR', built at spec.WHEELS centres with the
axle along X. Each wheel is modelled once as a RIGHT-hand wheel (outer face toward +X) and mirrored
for the left side, so the beadlock face looks outward on both sides and the paddles scoop the same
way (forward drive) on both rear tyres.

FRONT  34x10 ribbed sand tyre (spec.FRONT_TIRE_W 0.23): 6 crowned ribs (the outer two are shoulder ribs
       rolling into the balloon shoulder) and 5 narrow deep grooves (9 mm, 15 mm deep, near-vertical walls,
       2 mm rib edge bevels), lettered sidewalls (textures/wheels_sidewall_front*.png), 15x7 wheel.
REAR   35x15 paddle tyre (spec.REAR_TIRE_W 0.36): carcass (half-width W/2 - 4 mm, crown spec.REAR_TIRE_CARCASS_R)
       with a rounded shoulder (r4) and N_PADDLES curved scoop paddles reaching spec.REAR_TIRE_R (r6: a thin blade
       tapering ~42 % from ~13.5 mm at the knee to ~7.8 mm under the lip, a deeper concave scoop face hooking ~9.6 mm
       forward, a 4.2 mm ~59-degree front lip bevel with hard edges (crisp gloss line), a 3.8 mm flat top and a soft
       rounded back; one straight tapered back face, a convex knee and an S-curved ramp with a long trailing
       fillet - see paddle_profile()), slightly V-angled,
       running across the full width and wrapping ~5 cm down both shoulders in a 34 mm round into broad fins
       (tyre overall width W + 6 mm, as the photo silhouettes); 15x10 wheel.
RUBBER (r4) 'Tire tread' RUBBER_HEX #171717 rough 0.40 / 'Tire paddle' rough PADDLE_ROUGH 0.32 (spec.COLORS['rubber']
       is #262626, which renders far too light in the tools/render.py studio - see RUBBER_HEX), 'Tire groove'
       GROOVE_HEX #0e0e0e rough 0.75 on groove walls and floors, paddle root fillets and the crown valleys between
       the paddles (fake ambient occlusion that survives glTF). Sidewalls: flat #171717, satin rough 0.45; the
       lettering (GLAMIS TIRE CO / RIDGE CUTTER / DUNE PADDLE) lives only in the normal map (black
       embossed) and the roughness map (letter faces 0.34, slightly glossier) - no painted grey letters.
       Paint-pen '35.5-2' on four paddles per rear tyre (textures/wheels_paddle_marks.png: off-white and
       gold rows, + _rough.png), placed where rear.png / rear_3q / rear_wheel_sidepod show them.
WHEEL  gloss black 12 split-spoke face recessed deep in the barrel, machined (polished) chamfers on
       every spoke edge, the face ring and the hub collar; satin black beadlock ring (r5/r6, build_scallop_ring):
       a base annulus plus a clamp ring whose INNER EDGE is an S-wave with N_SC = 28 periods (r6), machined bright:
       polished wall + 2.5 mm polished round on its top edge (hard edge to the satin face), a 1.2 mm polished
       chamfer on the outer edge, and 56 polished 16.8 mm button heads with dark sockets in two staggered rows
       (r6, the photos' zig-zag: one in every lobe, one outboard of every crest) - the bright machined 'chain' of
       front_3q / rear_3q (r5: 30 flat washer + hex heads in one row read as small dim dots); 6 lug nuts,
       domed centre cap, valve stem. The barrel/flanges use a double-sided black so the wheel never looks
       see-through with backface culling. r6: real sharp edges (sharpen(); common.shade()'s call fails in bpy 5.1).

Hub mounting faces (for the suspension agent's rotors/hubs, which go in the same groups):
    FRONT_HUB_FACE / REAR_HUB_FACE = signed distance of the wheel's mounting face from the tyre
    centre plane, positive toward the OUTER side of the car. Everything of the wheel lies outboard
    of that face except the barrel/tyre; a rotor up to ~0.160 m radius fits inside the barrel.
"""
import math

import bpy
import bmesh
from mathutils import Vector, Matrix

from common import M, mat, obj_from_bmesh, mirror_x
import spec

V = Vector

N_PADDLES = 20                 # rear paddles, even (a tip at 12 and at 6 o'clock -> bounding box = REAR_TIRE_R).
                               # Side photo silhouette: peaks every 18.2 deg (19.8); rear_3q overlay: the lips
                               # line up with 20 (the photos' extra bands are the lip roll / dish of each paddle)
FRONT_HUB_FACE = -0.020        # mounting face: 20 mm inboard of the tyre centre plane (15x7)
REAR_HUB_FACE = -0.035         # 15x10 deep dish (~4+6): spoke face ~0.16 m behind the ring, as in the photos
RING_IN = 0.184                # beadlock base annulus inner radius (r6: 0.188 -> the deeper scallop lobes need room)
RING_OUT = spec.RIM_RING_R     # 0.222
RING_T = 0.013                 # ring thickness
N_SC = 28                      # r6: scallop periods of the clamp ring's wavy inner edge (one lobe + one crest each)
N_BOLTS = 2 * N_SC             # r6: 56 bolts in two staggered rows - one in every lobe (inner row) and one just
                               # outboard of every crest (outer row); the photos' zig-zag of bright heads (r5: 30, one row)
N_SPOKES = 12

SEG_TIRE_F = 56                # radial segments
SEG_TIRE_R = 3 * N_PADDLES     # 3 per paddle pitch
SEG_RIM = 48


# r4 rubber. The arbiter's spec.COLORS['rubber'] '#262626' (sRGB 38) with a 0.72 sidewall renders the f3q front
# sidewall at 74 sRGB in the tools/render.py studio (photo 27-32, r3 44): with spec 0 it is still 51 (the low front
# fill lights the sidewall head-on), and a rougher sidewall only spreads more of the big soft keys into it (0.5 -> 63,
# 0.72 -> 74). Measured sweep (scratchpad notes/fix_r4_wheels.md): #161616-#1a1a1a at rough ~0.4 gives sidewall 40-48,
# tread crowns 75-78 (photo 76) and rear paddles p50 54/45 (photo 43/36) with crisper highlights - so the rubber is a
# little darker than spec (sRGB 23, still lighter than r3's 15) and satin-glossy, as the dressed tyres in the photos
# (dark base, crisp highlight bands). The game lifts the tyre lighting itself (gltf-sandrail.js LOOKS).
RUBBER_HEX = '#171717'          # tread crowns, paddles, sidewall base (spec.COLORS['rubber'] is '#262626', see above)
RUBBER_ROUGH = 0.40             # tread crowns (r3 0.38): crisp highlight bands on the ribs
PADDLE_ROUGH = 0.32             # paddle faces and the bevelled lips (crisp edge highlights; rear view p50 49/39 vs photo 43/36)
SIDE_ROUGH = 0.45               # sidewall rubber in the rough map; embossed letter faces 0.34 (slightly glossier)
GROOVE_HEX = '#0e0e0e'          # groove floors/walls, paddle root fillets, crown valleys (spec 'rubber_groove' #161616)
GROOVE_ROUGH = 0.75


def _tread_mat():
    return mat('Tire tread', RUBBER_HEX, rough=RUBBER_ROUGH)


def _groove_mat():
    return mat('Tire groove', GROOVE_HEX, rough=GROOVE_ROUGH)


def _side_mat(kind):
    """Lettered sidewall (r4): flat rubber colour; the lettering is only in my normal + roughness strips
    (textures/wheels_sidewall_<kind>_normal.png / _rough.png: black embossed letters, slightly glossier
    than the satin rubber) if generated, else the shared textures/tire_*_sidewall_normal.png."""
    import os
    from common import TEX
    own = 'wheels_sidewall_%s' % kind
    shared = 'tire_%s_sidewall' % kind
    if os.path.exists(os.path.join(TEX, own + '_normal.png')):
        rough = own + '_rough.png' if os.path.exists(os.path.join(TEX, own + '_rough.png')) else None
        return mat('Tire sidewall ' + kind, RUBBER_HEX, normal=own + '_normal.png', normal_strength=2.5,
                   rough=SIDE_ROUGH, rough_tex=rough)
    return mat('Tire sidewall ' + kind, RUBBER_HEX, normal=shared + '_normal.png', normal_strength=2.5,
               rough=SIDE_ROUGH)


def _paddle_mat():
    import os
    from common import TEX
    if os.path.exists(os.path.join(TEX, 'wheels_paddle_marks.png')):
        rough = 'wheels_paddle_marks_rough.png'
        rough = rough if os.path.exists(os.path.join(TEX, rough)) else None
        return mat('Tire paddle', tex='wheels_paddle_marks.png', rough=PADDLE_ROUGH, rough_tex=rough)
    return _tread_mat()


def _mats():
    return {
        'rubber': _tread_mat(),
        'groove': _groove_mat(),
        'side_f': _side_mat('front'),
        'side_r': _side_mat('rear'),
        'paddle': _paddle_mat(),
        'black': M('gloss_black'),
        # barrel / drop centre / flanges: seen through the spokes from both sides, so double-sided
        # (with backface culling in the game the wheel must never look see-through)
        'barrel': mat('Wheel barrel black', '#0b0b0c', rough=0.22, clearcoat=1.0, double_sided=True),
        'machined': M('polished'),
        'bolt': M('polished'),          # r3: bright polished heads (chrome mirrored the dark studio -> read dim)
        'alu': M('alu'),
        'satin': M('satin_black'),
    }


# ------------------------------------------------------------------ mesh helpers

class MB:
    """bmesh accumulator with a per-object material list."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.mats = []

    def mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def obj(self, angle=35.0, recalc=False):
        if recalc:
            bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        return sharpen(obj_from_bmesh(self.name, self.bm, self.mats, True, angle), angle)


def sharpen(o, deg):
    """r6: sharp edges above `deg` (glTF splits the normals there). common.shade() calls set_sharpness_by_angle,
    which bpy 5.1 renamed set_sharp_from_angle, and swallows the error - so before r6 every wheel mesh was smooth
    across every edge (spoke chamfers, hex flats, paddle lip bevels and end caps). Edges flagged sharp in the bmesh
    (e.g. the beadlock round / face boundary) are kept."""
    me = o.data
    att = me.attributes.get('sharp_edge')
    keep = [i for i, v in enumerate(att.data) if v.value] if att is not None else []
    try:
        me.set_sharp_from_angle(angle=math.radians(deg))
    except Exception:
        return o
    if keep:
        att = me.attributes.get('sharp_edge') or me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
        for i in keep:
            att.data[i].value = True
    return o


def revolve(mb, prof, segs, mats, center=(0.0, 0.0), xoff=0.0, phase=0.0):
    """Revolve a profile [(r, x), ...] around an axis parallel to X through (y, z) = center.

    Face normals follow the profile direction: axial component = dr, radial component = -dx
    (walk outward in r on a +X-facing face, walk toward -x on an outward-facing tread).
    mats: one material or a list with one entry per profile segment. r == 0 makes a pole.
    """
    bm = mb.bm
    if not isinstance(mats, (list, tuple)):
        mats = [mats] * (len(prof) - 1)
    mis = [mb.mi(m) for m in mats]
    cy, cz = center
    cols = []
    for i, (r, x) in enumerate(prof):
        if r < 1e-9:
            v = bm.verts.new((x + xoff, cy, cz))
            cols.append([v] * segs)
        else:
            col = []
            for k in range(segs):
                a = phase + 2 * math.pi * k / segs
                col.append(bm.verts.new((x + xoff, cy + r * math.cos(a), cz + r * math.sin(a))))
            cols.append(col)
    for i in range(len(prof) - 1):
        c0, c1 = cols[i], cols[i + 1]
        for k in range(segs):
            k2 = (k + 1) % segs
            a, b, c, d = c0[k], c1[k], c1[k2], c0[k2]
            if a is d:
                vs = (a, b, c)
            elif b is c:
                vs = (a, b, d)
            else:
                vs = (a, b, c, d)
            try:
                f = bm.faces.new(vs)
                f.material_index = mis[i]
            except ValueError:
                pass


def polar(r, phi, x):
    return V((x, r * math.cos(phi), r * math.sin(phi)))


def offset_poly(pts, d):
    """Inset a CCW 2D polygon by d (miter joins)."""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2 = V(pts[i - 1]), V(pts[i]), V(pts[(i + 1) % n])
        e1 = (p1 - p0).normalized(); e2 = (p2 - p1).normalized()
        n1 = V((-e1.y, e1.x)); n2 = V((-e2.y, e2.x))          # inward normals for CCW
        m = (n1 + n2)
        if m.length < 1e-6:
            m = n1
        m.normalize()
        cosh = max(0.35, m.dot(n1))
        out.append(p1 + m * (d / cosh))
    return out


def extrude_outline(mb, poly2d, to3d, depth, bevel, m_top, m_chamf, m_side):
    """Solid from a CCW 2D outline: top face, machined chamfer all round, sides, bottom.

    to3d(u, v, h) maps outline coords + height (0 = top surface, negative = down) to 3D.
    """
    bm = mb.bm
    inner = offset_poly(poly2d, bevel)
    top = [bm.verts.new(to3d(p.x, p.y, 0.0)) for p in inner]
    edge = [bm.verts.new(to3d(p[0], p[1], -bevel)) for p in poly2d]
    bot = [bm.verts.new(to3d(p[0], p[1], -depth)) for p in poly2d]
    n = len(poly2d)
    it, ic, isd = mb.mi(m_top), mb.mi(m_chamf), mb.mi(m_side)
    created = []
    f = bm.faces.new(top); f.material_index = it; created.append(f)
    f = bm.faces.new(list(reversed(bot))); f.material_index = isd; created.append(f)
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((edge[i], edge[j], top[j], top[i])); f.material_index = ic; created.append(f)
        f = bm.faces.new((bot[i], bot[j], edge[j], edge[i])); f.material_index = isd; created.append(f)
    # orient outward (closed solid) and triangulate the n-gons
    bmesh.ops.recalc_face_normals(bm, faces=created)
    ngons = [f for f in created if len(f.verts) > 4]
    bmesh.ops.triangulate(bm, faces=ngons, quad_method='BEAUTY', ngon_method='BEAUTY')


# ------------------------------------------------------------------ tyre profiles

def env_r(x, rm, ar, ax, n):
    """Superellipse crown: r on the tyre envelope at axial position x."""
    t = min(1.0, abs(x) / ax)
    return rm + ar * (1.0 - t ** n) ** (1.0 / n)


def env_samples(rm, ar, ax, n, count):
    """Envelope points from +x shoulder over the crown to -x shoulder (x decreasing)."""
    out = []
    for i in range(count + 1):
        t = math.pi * i / count
        c, s = math.cos(t), math.sin(t)
        x = ax * math.copysign(abs(c) ** (2.0 / n), c)
        r = rm + ar * abs(s) ** (2.0 / n)
        out.append((r, x))
    return out


# front tread (front_3q_right.png / front.png): 6 ribs ~30 mm wide (the outer two are shoulder ribs
# rolling into the balloon shoulder), 5 narrow deep grooves with near-vertical walls
F_GROOVES = (0.078, 0.039, 0.0, -0.039, -0.078)   # groove centre lines (x), pitch 39 mm
F_GW, F_GWB, F_GD = 0.0045, 0.0039, 0.015         # groove half width at the top / at the floor, depth
F_BEV = 0.002                                     # rib edge bevel radius
F_CROWN = 0.0012                                  # rib crown height


def _env_frame(xg, renv, h=1e-4):
    """Envelope point, tangent and outward normal at x = xg, as 2D (x, r) vectors."""
    e = V((xg, renv(xg)))
    s = (renv(xg + h) - renv(xg - h)) / (2 * h)
    tau = V((1.0, s)).normalized()
    nrm = V((-tau.y, tau.x))
    return e, tau, nrm


def groove_pts(xg, renv):
    """One groove (x decreasing): bevelled rib edge, near-vertical wall, rounded floor, wall, bevel.
    Built square to the local envelope. Returns [(r, x)], [tag per segment]."""
    e, tau, nrm = _env_frame(xg, renv)
    gw, gwb, gd, rb = F_GW, F_GWB, F_GD, F_BEV
    c45 = 1.0 - math.sqrt(0.5)
    uw = [(gw + rb, 0.0), (gw + c45 * rb, -c45 * rb), (gw, -rb), (gwb, -(gd - 0.0025)), (0.0, -gd)]
    uw = uw + [(-u, w) for (u, w) in reversed(uw[:-1])]
    pts = []
    for u, w in uw:
        p = e + tau * u + nrm * w
        pts.append((p.y, p.x))
    tags = ['tread', 'tread', 'groove', 'groove', 'groove', 'groove', 'tread', 'tread']
    return pts, tags


def front_tire_profile():
    """Front tyre half-section [(r, x)] from the outer bead over the tread to the inner bead, and a
    material tag for every segment ('side' lettered sidewall, 'tread' rib rubber, 'groove')."""
    hw = spec.FRONT_RIM_W / 2
    W = spec.FRONT_TIRE_W / 2            # 0.115 (r3; was 0.125)
    R = spec.FRONT_TIRE_R                # 0.430
    rm, n = 0.325, 2.4
    ar = R - rm
    renv = lambda x: env_r(x, rm, ar, W, n)
    xb = hw + 0.0095                      # outer bead, just behind the beadlock ring
    # sidewall bulge from the bead out to the widest point (rm, W); the offsets were drawn for a 0.0255 bulge
    # (W 0.125) and scale with the actual one so the sidewall never pokes out past W
    f = (W - xb) / 0.0255
    so = [0.0015, 0.0045, 0.0085, 0.0130, 0.0175, 0.0215]
    outer = [(0.205, xb), (0.2215, xb)] + [(r_, xb + o * f) for r_, o in zip((0.2245, 0.232, 0.245, 0.262, 0.282, 0.305), so)] + [(rm, W)]
    inner = [(rm, -W)] + [(r_, -xb - o * f) for r_, o in reversed(list(zip((0.232, 0.245, 0.262, 0.282, 0.305), so[1:])))] + \
        [(0.2215, -hw - 0.0095), (0.2105, -hw - 0.0065), (0.2045, -hw - 0.003)]

    def env_at_theta(th):                 # superellipse point by parameter angle (deg), x >= 0
        c, s = math.cos(math.radians(th)), math.sin(math.radians(th))
        return (rm + ar * s ** (2.0 / n), W * c ** (2.0 / n))

    edge = F_GROOVES[0] + F_GW + F_BEV                 # outer bevel top of the outer groove
    th0 = math.degrees(math.acos((edge / W) ** (n / 2.0)))
    # shoulder rib: crowned near its groove edge, then rolling over the balloon shoulder
    sh = []
    for f, bump in ((0.80, 0.85), (0.62, 0.45), (0.45, 0.12), (0.30, 0.0), (0.16, 0.0), (0.06, 0.0)):
        r, x = env_at_theta(th0 * f)
        sh.append((r + F_CROWN * bump, x))
    prof = list(outer)
    for p in reversed(sh):                # shoulder (x decreasing toward the groove)
        prof.append(p)
    for g_i, xg in enumerate(F_GROOVES):
        gp, _ = groove_pts(xg, renv)
        if g_i > 0:                       # crowned inner rib between the previous groove and this one
            x_hi, x_lo = prof[-1][1], gp[0][1]
            for f in (0.3, 0.7):
                x = x_hi + (x_lo - x_hi) * f
                prof.append((renv(x) + F_CROWN * (1.0 - (2 * f - 1) ** 2), x))
        prof += gp
    for (r, x) in sh:
        prof.append((r, -x))
    prof += inner
    # tags: lettered sidewall up to the shoulder, rib rubber over the tread, then the groove walls
    tags = []
    for (ra, xa), (rb_, xb_) in zip(prof, prof[1:]):
        side = min(ra, rb_) >= SIDE_R0 - 1e-4 and max(ra, rb_) <= 0.4015 and abs(xa) > 0.05 and abs(xb_) > 0.05
        tags.append('side' if side else 'tread')
    # mark groove walls / floors (segments whose both ends lie deeper than 3 mm below the envelope)
    for i, ((ra, xa), (rb_, xb_)) in enumerate(zip(prof, prof[1:])):
        if abs(xa) < 0.09 and abs(xb_) < 0.09 and ra < renv(xa) - 0.0019 and rb_ < renv(xb_) - 0.0019:
            tags[i] = 'groove'
    # true rib crown height = spec radius (the game measures the wheel radius from the bounds)
    rmax = max(r for r, x in prof)
    k = (R - rm) / (rmax - rm)
    prof = [((rm + (r - rm) * k) if r > rm else r, x) for (r, x) in prof]
    return prof, tags


# old (r2) rear carcass the hand-tuned paddle outline below was drawn for; it is mapped onto the actual one
_R2_AX, _R2_BUTT_X, _R2_AR = 0.186, 0.1955, 0.092


REAR_ENV_N = 3.6                # r4: rounder shoulder (r3 4.5 = square box shoulder; critics + rear.png / rear_3q)


def rear_env():
    """Rear carcass superellipse. r3: half-width derived from spec.REAR_TIRE_W (was hard-coded 0.186),
    crown radius spec.REAR_TIRE_CARCASS_R."""
    return dict(rm=0.300, ar=spec.REAR_TIRE_CARCASS_R - 0.300, ax=spec.REAR_TIRE_W / 2 - 0.004, n=REAR_ENV_N)


def rear_tire_profile():
    hw = spec.REAR_RIM_W / 2
    e = rear_env()
    rm, ax = e['rm'], e['ax']
    xb = hw + 0.0095
    # sidewall bulge offsets were drawn for ax - xb = 0.049 (W 0.38); scale with the actual bulge
    f = (ax - xb) / 0.049
    so = [0.0025, 0.0085, 0.0165, 0.0245, 0.0315, 0.0365]
    rs = (0.2245, 0.230, 0.238, 0.249, 0.262, 0.278)
    outer = [(0.205, xb), (0.2215, xb)] + [(r_, xb + o * f) for r_, o in zip(rs, so)] + [(rm, ax)]
    inner = [(rm, -ax)] + [(r_, -xb - o * f) for r_, o in reversed(list(zip(rs[1:], so[1:])))] + \
        [(0.2215, -hw - 0.0095), (0.2105, -hw - 0.0065), (0.2045, -hw - 0.003)]
    crown = env_samples(rm, e['ar'], ax, e['n'], 18)[1:-1]
    return outer + crown + inner


def rear_tags(prof, r1=0.372):
    """Rear carcass: lettered sidewall band, the crown between the paddles in the dark groove
    rubber (a deep valley between paddles in the photos), plain rubber at the beads."""
    tags = []
    for (ra, xa), (rb, xb) in zip(prof, prof[1:]):
        if min(ra, rb) >= SIDE_R0 - 1e-4 and max(ra, rb) <= r1 + 1e-4 and abs(xa) > 0.05 and abs(xb) > 0.05:
            tags.append('side')
        elif min(ra, rb) > r1 - 1e-4 and max(abs(xa), abs(xb)) < 0.135:
            tags.append('groove')       # r3: only the crown valleys; the shoulder stays lit rubber (a dark
                                        # shoulder ring made the paddle ends read as thorns from the side)
        else:
            tags.append('tread')
    return tags


# ------------------------------------------------------------------ wheel pieces

def build_tire(front, m):
    mb = MB('tire_' + ('F' if front else 'R'))
    if front:
        prof, tags = front_tire_profile()
        side = m['side_f']
        segs, phase = SEG_TIRE_F, 0.0
    else:
        prof = rear_tire_profile()
        tags = rear_tags(prof)
        side = m['side_r']
        segs, phase = SEG_TIRE_R, math.pi / 2
    lut = {'side': side, 'tread': m['rubber'], 'groove': m['groove']}
    revolve(mb, prof, segs, [lut[t] for t in tags], phase=phase)
    return mb.obj(angle=50)


PADDLE_H_MM = 53.0             # profile heights below are drawn in mm for this base->tip height (crown)


def _mm(pts):
    return [(t * 0.001, h / PADDLE_H_MM) for (t, h) in pts]


def paddle_profile():
    """Paddle cross-section [(t, s)]: t tangential (m, at the crown), s = height fraction from the base
    (3 mm inside the carcass) to the tip. Negative t = leading side (rolling direction of forward drive).
    r4 (rear_wheel_sidepod / rear_3q / rear close-ups + critics): a CUPPED SCOOP paddle - the leading
    (driving, forward) face is steep and dished ~12 mm (chord: root fillet foot -> lip) under a lip that
    curls ~12 mm forward over the cup (the rolled band between the ramps in the photos); the blade is
    15 mm thick at the bevelled lip (~4 mm rounds front and back, catch a highlight line) and tapers out
    into a long, convex trailing ramp (~75 mm) that meets the carcass in a
    ~20 mm fillet; ~20 mm fillet at the root of the driving face. The photos show exactly these big
    convex, text-moulded backs: from ahead of the wheel (rear_wheel_sidepod, front of the tyre: the backs
    face up) and from behind on the upper half (rear.png, rear_3q), and the flat-topped, cupped lips with
    convex undersides along the rear_3q back silhouette. (r3 had the wedge the other way round: thin
    steep backs that read as bars over a wide grey carcass from behind.) ~60 % of the 125 mm base pitch
    is paddle (incl. fillets ~70 %), the rest open carcass (~5 deg).
    r5 (critics: "soft rounded pillows" -> thin curved scoops with crisp edges; side photo back silhouette:
    concave driving face with the tip hooked forward + long straight trailing ramp; rear.png close-up: from
    behind each paddle shows a crisp lip with a moulding-vent row, a dark concave neck under it (moulded
    text) and a lighter ramp (marker writing)): the whole driving face is ONE concave scoop (a quadratic
    sweep from vertical at the root to 115 deg under the lip) from a thick ~13 mm root fillet up to a 12 mm
    lip that leans ~9 mm forward of the face root; the lip has a 6.8 mm flat top between two 2.6 mm
    45-degree bevels (hard shading edges -> crisp highlight lines: the paddle object is smooth-shaded only
    below 32 deg); behind the lip a 2 mm vertical back, a short concave neck, a convex knee and an S-curved
    ramp (convex, then hollow) that runs out in a long trailing fillet. The blade is 12-13 mm thick for its
    top ~9 mm and flares into the ramp below (a short neck: a long thin blade read as thorns in side view);
    base 90 mm of the 125 mm pitch (35 mm open valley).
    r6 (critics: "thick, blocky, flat-matte" -> thin the blade toward the tip ~40 %, curve the face into a scoop,
    bevel the lip for a gloss highlight): the blade is ~13.5 mm thick (normal to its mid-line) at the knee (h 27)
    and tapers straight to ~7.8 mm under the lip (r5: 12-13 mm lip on a 19 mm neck flaring into the ramp at h 41);
    the scoop face is deeper (~4 mm sagitta, r5 2.5) and hooks ~9.6 mm forward; the lip has a 4.2 mm front bevel at
    ~59 deg (hard edges on both sides -> a crisp highlight line facing up-forward), a 3.8 mm flat top and a soft
    rounded back; behind it one straight tapered back face down to a convex knee at h 27 and the S-curved ramp.
    24 points (indices used by MARK_FACE / MARK_FACE_BACK):
      0 lead fillet foot, 1-2 root fillet, 3-8 concave scoop face, 9 front bevel start, 10 lip top front
      edge, 11 lip top back edge (s = 1 at 10 and 11), 12 back round, 13 lip back, 14-16 tapered back face,
      17 knee, 18-22 ramp, 23 trailing foot (feet 3 mm inside the carcass)."""
    return _mm([(-25.0, 0.0), (-17.2, 2.4), (-13.4, 6.4),
                (-12.0, 11.5), (-11.6, 18.5), (-11.9, 25.5), (-13.0, 32.2), (-15.0, 38.6), (-18.0, 44.4),
                (-21.6, 49.4), (-19.4, 53.0), (-15.6, 53.0), (-13.35, 51.7), (-12.35, 49.7),
                (-8.8, 44.0), (-5.2, 38.6), (-1.7, 32.2), (1.4, 27.0),
                (6.4, 22.4), (14.0, 16.8), (24.5, 10.8), (37.0, 5.4), (50.0, 1.8), (60.0, 0.0)])


def paddle_profile_end():
    """Blunt cross-section of the paddle END (the buttress down the shoulder), same point layout as
    paddle_profile(): broad, rounded fins on the shoulder (rear_wheel_sidepod, rear_3q, side photo), no
    thin hooked lip there (a thin lip read as thorns from the side): ~19 mm thick under ~4 mm bevels."""
    return _mm([(-28.0, 0.0), (-19.5, 2.9), (-15.6, 7.2),
                (-14.2, 12.0), (-14.0, 18.8), (-14.4, 25.5), (-15.2, 32.0), (-16.6, 38.3), (-18.4, 44.0),
                (-19.6, 48.6), (-17.0, 52.4), (-9.4, 53.0), (-6.45, 51.3), (-5.15, 48.8),
                (-2.2, 43.8), (0.6, 38.4), (3.8, 32.4), (7.0, 27.4),
                (11.6, 22.4), (18.6, 16.8), (28.6, 10.8), (41.0, 5.4), (54.0, 1.8), (64.0, 0.0)])


MARK_FACE = (3, 9)             # scoop driving-face points that could carry marker writing (fillet end .. lip bevel)
# paddle LIP angle (deg, 0 = forward, 90 = up) -> marks texture row (0 = off-white '35.5-2', 1 = gold); each
# resolves to the nearest paddle (paddle k's lip sits at 90 + k * 360 / N_PADDLES). Found by casting the photos'
# mark pixels through the matched cameras onto this model (r4): rear.png's two white numbers sit on the ramps of
# the paddles with lips at 108 and 162 deg (rear_3q's on the 162 one too), rear_wheel_sidepod's two gold numbers
# on the ramps of the 36 and 342 deg paddles. All on the convex trailing ramps with the image top at the lip,
# so they read upright from behind and upside down from ahead of the wheel, as in the photos.
MARK_LIPS = {108.0: 0, 162.0: 0, 36.0: 1, 342.0: 1}
MARK_FACE_BACK = (15, 22)      # r6: mid back face .. lower ramp - the writing centre lands just past the knee on
                               # the upper ramp, which faces the rear camera even on the 162-deg paddle (on the
                               # steeper r6 back face it read foreshortened); r5 (13, 21)
MARK_BACK_LIPS = set(MARK_LIPS)  # paddles whose writing is on the BACK ramp (all of them, r4)
MARK_SPAN_V = 0.062            # metres of paddle face covered by one row of the marks texture (~ the ramp length)
V_LEAD = 0.006                 # V-angle: the paddle centre leads its ends by 6 mm (r2: 16 mm)


def _paddle_at(lip_deg):
    k = round(((lip_deg - 90.0) % 360.0) / (360.0 / N_PADDLES)) % N_PADDLES
    return int(k)


MARKED = {_paddle_at(a): row for a, row in MARK_LIPS.items()}
MARKED_BACK = {_paddle_at(a) for a in MARK_BACK_LIPS}

# Paddle outline in the meridian plane (x across the tread, r radial), outer half (x >= 0): flat top at
# spec.REAR_TIRE_R, a soft rounded corner, then an END BUTTRESS that carries the paddle ~35-40 mm down
# over the shoulder onto the sidewall (rear_wheel_sidepod_right.png, rear_3q_right.png). The r2 points
# are mapped onto the actual carcass: x scaled with its half-width (the buttress ends stand 7 mm proud of
# the carcass, so the tyre's overall width is W + 6 mm: rear.png's silhouette fit), r stretched with
# its height below r 0.41 (the paddle tips stay at spec.REAR_TIRE_R).
P_CORNER_R = 0.034             # r5: one round from the flat top into the end buttress (rear.png: the lips hook
                               # down over the shoulder; r3 0.026, r2 0.022)
P_FAN_ANGLES = (70.0, 51.0, 34.0, 21.0, 13.0)            # deg from +x toward +r (r5: 5 stations, r4 6, r3 7)
# r3: the paddle ends stay as thick as the crown down the shoulder (photos: broad rounded fins, not thorns)
P_FAN_K = (1.0, 1.05, 1.09, 1.10, 1.06)                  # paddle thickness scale per fan station (r4: the
                                                          # end profile itself is now the thick one)
P_FAN_BLUNT = (0.45, 0.85, 1.0, 1.0, 1.0)                # blend toward paddle_profile_end() per fan station
P_FAN_SWEEP = (0.0, 0.002, 0.005, 0.008, 0.010)          # trailing sweep (m) of the end buttress (rear.png:
                                                          # the paddle ends hook back over the shoulder)


def _map_x(x):
    e = rear_env()
    if x <= _R2_AX:
        return x * e['ax'] / _R2_AX
    butt = spec.REAR_TIRE_W / 2 + 0.003
    return e['ax'] + (x - _R2_AX) * (butt - e['ax']) / (_R2_BUTT_X - _R2_AX)


def _map_r(r):
    """r2 shoulder radius -> same relative height on the actual carcass shoulder (r < 0.41 only)."""
    e = rear_env()
    return 0.3 + (r - 0.3) * e['ar'] / _R2_AR


def _paddle_outline():
    R = spec.REAR_TIRE_R
    rho = P_CORNER_R
    # r3: the end fin stands up to 7 mm proud of the shoulder and blends into the sidewall at r ~0.345,
    # just above the lettering (photos: broad rounded fins on the shoulder; r2 ran them down to r 0.305)
    ax = rear_env()['ax']
    butt = [V((ax + d, r)) for (d, r) in ((0.0057, _map_r(0.405)), (0.0070, _map_r(0.380)), (0.0062, 0.370),
                                          (0.0030, 0.358), (0.0008, 0.350), (-0.0005, 0.344))]
    xa = butt[0].x + 0.0008 - rho          # corner arc ends just outside the first buttress point
    pts = [V((0.0, R)), V((xa, R))]
    for k in range(1, 9):
        a = math.radians(90.0 - 90.0 * k / 8)
        pts.append(V((xa + rho * math.cos(a), R - rho + rho * math.sin(a))))
    return pts + butt


def _fan_centre():
    return V((_map_x(0.140), _map_r(0.335)))


def _ray_poly(p0, d, poly):
    """First hit (smallest t > 0) of the ray p0 + t d with an open 2D polyline."""
    best = None
    for a, b in zip(poly, poly[1:]):
        e = b - a
        den = d.x * (-e.y) - d.y * (-e.x)
        if abs(den) < 1e-12:
            continue
        w = a - p0
        t = (w.x * (-e.y) - w.y * (-e.x)) / den
        u = (d.x * w.y - d.y * w.x) / den
        if t > 1e-6 and -1e-6 <= u <= 1 + 1e-6 and (best is None or t < best):
            best = t
    return best


def _ray_carcass(p0, d, e):
    """Ray (from inside the carcass) to the carcass surface, by bisection."""
    def inside(p):
        return p.x < e['ax'] and p.y < env_r(abs(p.x), e['rm'], e['ar'], e['ax'], e['n'])
    lo, hi = 0.0, 0.25
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if inside(p0 + d * mid):
            lo = mid
        else:
            hi = mid
    return lo


def paddle_stations():
    """[(B, T, k)]: base point (3 mm inside the carcass) and outline point in the meridian plane
    (x, r), and the thickness scale, from the inner buttress across the tread to the outer one."""
    e = rear_env()
    out = []
    c = _fan_centre()
    for x, bl in ((0.0, 0.0), (c.x, 0.25)):
        rb = env_r(x, e['rm'], e['ar'], e['ax'], e['n']) - 0.003
        out.append((V((x, rb)), V((x, spec.REAR_TIRE_R)), 1.0, 0.0, bl))
    poly = _paddle_outline()
    for ang, k, sw, bl in zip(P_FAN_ANGLES, P_FAN_K, P_FAN_SWEEP, P_FAN_BLUNT):
        d = V((math.cos(math.radians(ang)), math.sin(math.radians(ang))))
        tb = _ray_carcass(c, d, e)
        tt = _ray_poly(c, d, poly)
        tt = max(tt, tb + 0.0009)                      # >= 0.9 mm proud at the buttress tip
        out.append((c + d * (tb - 0.003), c + d * tt, k, sw, bl))
    left = [(V((-b.x, b.y)), V((-t.x, t.y)), k, sw, bl) for (b, t, k, sw, bl) in reversed(out[1:])]
    return left + out


def build_paddles(m, flip_u=False):
    """N_PADDLES cupped scoop paddles lofted across the tread and around both shoulders (end buttresses).
    The MARKED paddles carry the marker writing on their convex trailing ramps (MARKED_BACK; r4) or on the
    dished driving face (UVs into wheels_paddle_marks.png, one texture row per ink colour); flip_u for
    wheels that will be mirrored, so the writing still reads left-to-right. The deepest root fillets use
    the dark groove rubber to fake the ambient occlusion in the valleys."""
    mb = MB('paddles')
    e = rear_env()
    half = spec.REAR_TIRE_W / 2
    prof = paddle_profile()
    sts = paddle_stations()
    mi = mb.mi(m['paddle'])
    mg = mb.mi(m['groove'])
    bm = mb.bm
    uvl = bm.loops.layers.uv.new('UVMap')
    rb0 = env_r(0.0, e['rm'], e['ar'], e['ax'], e['n']) - 0.003
    H0 = spec.REAR_TIRE_R - rb0                       # base -> tip height at the crown
    # v down the driving face by arc length from the lip (v = 0) toward the root (v = 1 at MARK_SPAN_V)
    i_a, i_b = MARK_FACE
    arc = {i_b: 0.0}
    for i in range(i_b - 1, i_a - 1, -1):
        (t0, s0), (t1, s1) = prof[i + 1], prof[i]
        arc[i] = arc[i + 1] + math.hypot(t1 - t0, (s1 - s0) * H0)
    arc_v = {i: min(1.0, a / MARK_SPAN_V) for i, a in arc.items()}
    # same down the convex trailing ramp, from the lip end of the back round toward the root; there the
    # image top is the lip side (upright from behind, upside down from ahead of the wheel, as the photos)
    j_a, j_b = MARK_FACE_BACK
    arcb = {j_a: 0.0}
    for i in range(j_a + 1, j_b + 1):
        (t0, s0), (t1, s1) = prof[i - 1], prof[i]
        arcb[i] = arcb[i - 1] + math.hypot(t1 - t0, (s1 - s0) * H0)
    arcb_v = {i: 1.0 - min(1.0, a / MARK_SPAN_V) for i, a in arcb.items()}
    root = [max(prof[i][1], prof[(i + 1) % len(prof)][1]) <= 0.085 for i in range(len(prof))]
    # phase: the lip of one paddle (centre station) sits exactly at 12 o'clock, so with an even paddle
    # count there is a tip at 90 and 270 deg and the bounding box radius is exactly spec.REAR_TIRE_R
    t_lip = [t for (t, s_) in prof if s_ == 1.0][0]
    phase = math.pi / 2 - (-V_LEAD + t_lip) / rb0
    us = [max(0.0, min(1.0, (b.x + half) / (2 * half))) for (b, t, k, sw, bl) in sts]
    prof_end = paddle_profile_end()
    for kp in range(N_PADDLES):
        phi0 = phase + 2 * math.pi * kp / N_PADDLES
        loops = []
        for (B, T, k, sw, bl) in sts:
            ax_ = min(abs(B.x), half)
            tv = -V_LEAD * (1.0 - (ax_ / half) ** 1.6) + sw    # V: paddle centre leads the ends
            loop = []
            for (t, s), (te, se) in zip(prof, prof_end):
                t, s = t + (te - t) * bl, s + (se - s) * bl
                p = B + (T - B) * s
                # tangential offsets -> angle at the CENTRE base radius, so every station spans the
                # same angle and neighbouring paddles never overlap where the shoulder drops
                phi = phi0 + (tv + t * k) / rb0
                # forward drive spins the wheel toward -phi (top moves +Y): leading side = -phi
                loop.append(bm.verts.new((p.x, p.y * math.cos(phi), p.y * math.sin(phi))))
            loops.append(loop)
        faces = []
        n = len(prof)
        row = MARKED.get(kp)
        back = kp in MARKED_BACK
        fa, fb, fv = (j_a, j_b, arcb_v) if back else (i_a, i_b, arc_v)
        for j in range(len(sts) - 1):
            a, b = loops[j], loops[j + 1]
            for i in range(n):
                i2 = (i + 1) % n
                f = bm.faces.new((a[i], a[i2], b[i2], b[i]))
                f.material_index = mg if root[i] else mi
                faces.append(f)
                for lp, (jj, ii) in zip(f.loops, ((j, i), (j, i2), (j + 1, i2), (j + 1, i))):
                    if row is not None and fa <= i < fb:
                        u = (1.0 - us[jj]) if flip_u else us[jj]
                        lp[uvl].uv = (u, 0.5 * (1 - row) + 0.5 * fv[ii])
                    else:
                        lp[uvl].uv = (0.01, 0.99)
        f0 = bm.faces.new(loops[0]); f1 = bm.faces.new(list(reversed(loops[-1])))
        f0.material_index = f1.material_index = mg
        for f in (f0, f1):
            for lp in f.loops:
                lp[uvl].uv = (0.01, 0.99)
        faces += [f0, f1]
        bmesh.ops.recalc_face_normals(bm, faces=faces)
        bmesh.ops.triangulate(bm, faces=[f0, f1], quad_method='BEAUTY', ngon_method='BEAUTY')
    return mb.obj(angle=PADDLE_SMOOTH_ANGLE)    # r5: hard lip bevel edges, smooth scoop / neck / ramp / fillets


PADDLE_SMOOTH_ANGLE = 40.0      # r6: lip bevel edges turn 59-67 deg (hard), the back round 30-38 (smooth)


def face_top(front):
    """Axial position of the spoke face ring's top surface (outer side = +)."""
    return (FRONT_HUB_FACE + 0.048) if front else (REAR_HUB_FACE + 0.029)


def rim_profile(hw):
    """Barrel seen from inside (normals toward the axle) + inner flange + outer lip under the ring."""
    # r5: 13 points (was 18) - the inner flange and the drop centre are only seen from inside the car
    return [(0.200, -hw + 0.002), (0.2068, -hw - 0.003), (0.2035, -hw - 0.0080), (0.1920, -hw - 0.0095),
            (0.1850, -hw - 0.0065), (0.1830, -hw + 0.012), (0.1680, -hw + 0.027), (0.1660, -hw + 0.068),
            (0.1760, -hw + 0.084), (0.1760, hw + 0.0072), (0.1800, hw + 0.0104), (0.1890, hw + 0.0104),
            (0.1930, hw + 0.0104)]


def build_rim(front, m):
    hw = (spec.FRONT_RIM_W if front else spec.REAR_RIM_W) / 2
    hub = FRONT_HUB_FACE if front else REAR_HUB_FACE
    F = face_top(front)                      # top of the spoke face ring (deep-dish face)
    mb = MB('rim_' + ('F' if front else 'R'))
    blk, mac = m['black'], m['machined']

    # barrel + flanges
    revolve(mb, rim_profile(hw), SEG_RIM, m['barrel'])

    # beadlock ring (r5): build_scallop_ring() - a separate object (own smoothing angle)

    # face ring that carries the spokes (machined chamfer on its inner top edge)
    fr_in, fr_out, ft = 0.149, 0.1765, 0.020
    fo = fr_out - 0.0013
    fp = [(fr_in, F - 0.0035), (fr_in + 0.0035, F), (fo - 0.0025, F), (fo, F - 0.0025),
          (fo, F - ft), (fr_in, F - ft), (fr_in, F - 0.0035)]
    revolve(mb, fp, SEG_RIM, [mac, blk, blk, blk, blk, blk])

    # hub with domed centre cap and machined collar
    h0 = hub                    # mounting face
    h1 = hub + 0.025            # hub front face
    hp = [(0.0, h1 + 0.035), (0.016, h1 + 0.0342), (0.028, h1 + 0.0315), (0.036, h1 + 0.026), (0.040, h1 + 0.019),
          (0.041, h1 + 0.0125), (0.0412, h1 + 0.0115), (0.0465, h1 + 0.0115), (0.0478, h1 + 0.0100),
          (0.0478, h1 + 0.0055), (0.0530, h1 + 0.0010), (0.0560, h1), (0.0860, h1), (0.0890, h1 - 0.003),
          (0.0890, h0 + 0.002), (0.0870, h0), (0.0, h0)]
    hm = [blk] * 6 + [mac, mac, mac] + [blk] * 7
    revolve(mb, hp, 24, hm)

    # 12 split spokes (Y), each an extruded outline with a machined chamfer all round
    r_h, r_t = 0.078, 0.155               # spoke root (on the hub) / tip (buried in the face ring)
    top_h = h1 + 0.004
    depth = 0.022

    def xtop(r):
        return top_h + (F - 0.0008 - top_h) * (r - r_h) / (r_t - r_h)

    rf, rc = 0.112, 0.124                 # fork, crotch radii
    da = math.radians(6.2)                # arm tip half-spread
    for i in range(N_SPOKES):
        p0 = 2 * math.pi * i / N_SPOKES

        def to3d(u, v, h, p0=p0):
            r = math.hypot(u, v)
            ang = p0 + math.atan2(v, u)
            return polar(r, ang, xtop(r) + h)

        def pt(r, t):        # (radius, tangential offset) -> local 2D (u, v)
            a = t / r
            return (r * math.cos(a), r * math.sin(a))

        tip_r = r_t
        aw = 0.0080          # half arm width
        rm_ = 0.134
        outline = [pt(r_h, -0.0120), pt(0.095, -0.0108), pt(rf, -0.0104),
                   pt(rm_, -(tip_r * da * 0.62 + aw)),
                   pt(tip_r, -(tip_r * da + aw)), pt(tip_r, -(tip_r * da - aw)),
                   pt(rm_, -(tip_r * da * 0.62 - aw)), pt(rc, 0.0),
                   pt(rm_, (tip_r * da * 0.62 - aw)), pt(tip_r, (tip_r * da - aw)),
                   pt(tip_r, (tip_r * da + aw)), pt(rm_, (tip_r * da * 0.62 + aw)),
                   pt(rf, 0.0104), pt(0.095, 0.0108), pt(r_h, 0.0120)]
        extrude_outline(mb, outline, to3d, depth, 0.0024, blk, mac, blk)
    return mb.obj(angle=60)      # r6: 45-deg spoke chamfers shade as rolled edges (catch the lights, as r5 did); 90-deg steps sharp


# r6 beadlock layout (front_3q / rear_3q / rear_wheel_sidepod close-ups at 6-10x): the bright machined line is an
# S-wave with N_SC periods, and the polished button heads sit in a ZIG-ZAG on both sides of it - an inner row nested
# in the lobes (the wave wraps round them on the centre side) and an outer row just outboard of the crests, ~11.5 px
# apart round the ring in rear_3q (~24 mm) = 2 bolts per wave period. Checked with a 2D clearance script: >= 1.4 mm
# from the top of the polished round to every head, heads 9 mm apart, outer heads 2.1 mm inside RING_OUT.
BOLT_R_IN = 0.1995             # inner bolt row (in the lobes)
BOLT_R_OUT = 0.2115            # outer bolt row (outboard of the crests)
BOLT_PHASE = math.radians(3.0)  # angle of inner bolt 0 (= the first lobe)
BOLT_HEAD_R = 0.0084           # r6: 16.8 mm polished button heads (r5 18 mm flat washer + 13 mm hex read as small dim
                               # dots: flat facets mirror the dark studio; a dome catches a light from any side)
BOLT_HEAD_H = 0.0045           # dome height above the ring face
SC_DEPTH = 0.0045              # scallop pocket depth below the clamp-ring face (the machined wall)
SC_CHAMFER = 0.0025            # r6: 2.5 mm polished machined round on the wall's top edge (two facets, smooth-shaded
                               # together with the polished wall below it; hard edge to the satin face)
SC_RC = 0.1930                 # wave centre radius
SC_A = 0.0062                  # wave amplitude (edge 0.1868 in the lobes .. 0.1992 at the crests)
SC_BETA = 1.5                  # tanh shaping: fuller lobes and crests than a sine, no kinks
SC_SAMPLES = 12                # edge samples per wave period
OUT_CHAMFER = 0.0012           # r6: polished chamfer on the ring's outer edge (a thin bright rim at the bead)


def scallop_edge():
    """r6: the clamp ring's wavy INNER edge [(phi, r)]: r = SC_RC - SC_A * tanh(SC_BETA cos(N_SC (phi - BOLT_PHASE)))
    / tanh(SC_BETA) - the lobes (edge pushed toward the axle) at the inner bolts, the crests (edge pulled out) at the
    outer bolts. Its polished wall + round is the bright S-wave of the photos."""
    n = N_SC * SC_SAMPLES
    out = []
    th = math.tanh(SC_BETA)
    for i in range(n):
        ph = BOLT_PHASE + 2 * math.pi * i / n
        c = math.cos(N_SC * (ph - BOLT_PHASE))
        out.append((ph, SC_RC - SC_A * math.tanh(SC_BETA * c) / th))
    return out


def bolt_centres():
    """[(phi, r)] of the 2 * N_SC beadlock bolts: inner row in the lobes, outer row half a period on."""
    out = []
    for k in range(N_SC):
        ph = BOLT_PHASE + 2 * math.pi * k / N_SC
        out.append((ph, BOLT_R_IN))
        out.append((ph + math.pi / N_SC, BOLT_R_OUT))
    return out


def build_scallop_ring(front, m):
    """Beadlock ring from the barrel lip at x0 to its face x0 + RING_T (r5 scalloped ring, r6 machined 'chain'):
    - a satin black base annulus RING_IN..(under the clamp ring) whose top face is the floor of the scallop
      pockets, SC_DEPTH below the ring face, with a small round on its inner edge;
    - the clamp ring on top of it: wavy inner wall machined bright (M('polished') - a scallop cut through the black
      anodising), a polished SC_CHAMFER round on its top edge (two facets, smooth-shaded with the wall so wall + round
      read as one bright rolled line in any light), then a hard edge to the flat satin face;
    - the outer edge: a polished OUT_CHAMFER chamfer and a satin wall down to x0, revolved separately (open
      underneath, it sits on the base)."""
    hw = (spec.FRONT_RIM_W if front else spec.REAR_RIM_W) / 2
    x0 = hw + 0.0105
    mb = MB('ring_' + ('F' if front else 'R'))
    bm = mb.bm
    satin, mac = m['satin'], m['machined']
    x1 = x0 + RING_T
    xs = x1 - SC_DEPTH
    ri, ro = RING_IN, RING_OUT
    edge = scallop_edge()
    emax = max(r for _, r in edge)
    revolve(mb, [(ri, x0), (ri, xs - 0.0010), (ri + 0.0010, xs), (emax + 0.0015, xs)], SEG_RIM, satin)
    n = len(edge)
    pts = [V((r * math.cos(ph), r * math.sin(ph))) for ph, r in edge]
    ms, mm_ = mb.mi(satin), mb.mi(mac)
    rf = ro - OUT_CHAMFER                               # face outer radius
    rows = []
    k = 1.0 - math.sqrt(0.5)
    for i, (ph, r) in enumerate(edge):
        tng = (pts[(i + 1) % n] - pts[i - 1]).normalized()
        nrm = V((tng.y, -tng.x))                        # in-plane normal into the ring (CCW edge -> outward)
        cs, sn = math.cos(ph), math.sin(ph)
        e = pts[i]
        row = [(xs - 0.0004, e), (x1 - SC_CHAMFER, e), (x1 - k * SC_CHAMFER, e + nrm * (k * SC_CHAMFER)),
               (x1, e + nrm * SC_CHAMFER), (x1, V((rf * cs, rf * sn)))]
        rows.append([bm.verts.new((x, p.x, p.y)) for (x, p) in row])
    seg_m = [mm_, mm_, mm_, ms]                         # machined wall, rounded chamfer (2 facets), satin face
    faces = []
    for i in range(n):
        a, b = rows[i], rows[(i + 1) % n]
        for kk in range(len(seg_m)):
            f = bm.faces.new((a[kk], b[kk], b[kk + 1], a[kk + 1]))
            f.material_index = seg_m[kk]
            faces.append(f)
    # orientation: the flat face (segment 3) must face +X; flip the whole open strip if it does not
    bm.normal_update()
    if faces[3].normal.x < 0:
        for f in faces:
            f.normal_flip()
    # hard edge between the polished round and the satin face (the face stays flat-shaded; wall + round smooth)
    for i in range(n):
        e_ = bm.edges.get((rows[i][3], rows[(i + 1) % n][3]))
        if e_ is not None:
            e_.smooth = False
    # outer edge: polished chamfer + satin wall (circular, so a plain revolve with fewer segments)
    nseg = 4 * N_SC
    revolve(mb, [(rf, x1), (ro, x1 - OUT_CHAMFER), (ro, x0)], nseg, [mac, satin], phase=BOLT_PHASE)
    return mb.obj(angle=50)


def build_hardware(front, m):
    """Beadlock bolts (r6: polished button heads in two staggered rows), lug nuts, valve stem."""
    hw = (spec.FRONT_RIM_W if front else spec.REAR_RIM_W) / 2
    hub = FRONT_HUB_FACE if front else REAR_HUB_FACE
    F = face_top(front)
    x1 = hw + 0.0105 + RING_T
    mb = MB('hw_' + ('F' if front else 'R'))
    bolt = m['bolt']
    # r6: ISO 7380-style button heads: a low polished dome (8 segments, smooth) with a dark socket disc on top, sunk
    # 0.2 mm into the satin ring face - round heads light up from any side, as the photos' bright dots do
    rb, h = BOLT_HEAD_R, BOLT_HEAD_H
    sock = [(0.0, h), (0.40 * rb, h)]
    dome = [(0.40 * rb, h), (0.80 * rb, 0.70 * h), (rb, 0.0)]
    for ph, r in bolt_centres():
        cen = (r * math.cos(ph), r * math.sin(ph))
        revolve(mb, sock, 8, m['satin'], center=cen, xoff=x1 - 0.0002, phase=ph)
        revolve(mb, dome, 8, bolt, center=cen, xoff=x1 - 0.0002, phase=ph)

    # lug nuts (6, between alternate spokes) on the hub face
    h1 = hub + 0.025
    nut = [(0.0, 0.0162), (0.0055, 0.0162), (0.0100, 0.0155), (0.0118, 0.0125), (0.0118, 0.002), (0.0098, 0.0)]
    for j in range(6):
        ph = math.pi / N_SPOKES + 2 * math.pi * j / 6
        revolve(mb, nut, 6, m['alu'], center=(0.061 * math.cos(ph), 0.061 * math.sin(ph)), xoff=h1,
                phase=ph)

    # valve stem on the face ring between two spokes
    ph = math.pi / N_SPOKES + math.pi / 6 * 3
    rv = 0.1625
    stem = [(0.0038, 0.017), (0.0042, 0.016), (0.0048, 0.002), (0.0058, 0.0)]
    cap = [(0.0, 0.0298), (0.0030, 0.0295), (0.0040, 0.028), (0.0040, 0.0175), (0.0038, 0.017)]
    c = (rv * math.cos(ph), rv * math.sin(ph))
    revolve(mb, stem, 10, m['satin'], center=c, xoff=F - 0.0005)
    revolve(mb, cap, 10, m['alu'], center=c, xoff=F - 0.0005)
    return mb.obj(angle=50)      # r6: the 8-segment domes stay round (facets meet at ~40 deg); hex nut flats (60) sharp


# ------------------------------------------------------------------ UVs for the lettered sidewalls

def sidewall_uv(o, side_mats, centre, r0, r1):
    """u wraps once (text reads clockwise seen from that face), v = 0 at the bead, 1 at the shoulder."""
    me = o.data
    if 'UVMap' not in me.uv_layers:
        me.uv_layers.new(name='UVMap')
    uv = me.uv_layers['UVMap'].data
    idx = {i for i, mm in enumerate(me.materials) if mm in side_mats}
    cy, cz = centre[1], centre[2]
    for p in me.polygons:
        if p.material_index not in idx:
            continue
        sgn = 1.0 if p.normal.x > 0 else -1.0
        us, vs = [], []
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            dy, dz = co.y - cy, co.z - cz
            th = math.atan2(dz, dy)
            us.append((-sgn * th / (2 * math.pi)) % 1.0)
            vs.append((math.hypot(dy, dz) - r0) / (r1 - r0))
        if max(us) - min(us) > 0.5:
            us = [u + 1.0 if u < 0.5 else u for u in us]
        for li, u, v in zip(p.loop_indices, us, vs):
            uv[li].uv = (u, v)


# ------------------------------------------------------------------ assembly

def make_wheel(front, m, flip_u=False):
    objs = [build_tire(front, m), build_rim(front, m), build_scallop_ring(front, m), build_hardware(front, m)]
    if not front:
        objs.insert(1, build_paddles(m, flip_u))
    return objs


def build(C):
    m = _mats()
    for c, (x, y, z, r, w, front) in spec.WHEELS.items():
        objs = make_wheel(front, m, flip_u=x < 0)
        if x < 0:
            mirrored = []
            for o in objs:
                mo = mirror_x(o, o.name + '_L')
                mirrored.append(mo)
                me = o.data
                bpy.data.objects.remove(o)
                bpy.data.meshes.remove(me)
            objs = mirrored
        for o in objs:
            o.name = 'wheel_%s_%s' % (c, o.name.split('_')[0])
            o.data.transform(Matrix.Translation((x, y, z)))
        r1 = 0.405 if front else 0.372
        sidewall_uv(objs[0], {m['side_f'], m['side_r']}, (x, y, z), 0.2215, r1)
        C.add(objs, 'Wheel_' + c)


# ------------------------------------------------------------------ sidewall textures (run once by hand)
#   cd blender/trx_pro && python -c "import sys; sys.path[:0] = ['.', 'parts']; \
#       import wheels; wheels.make_textures(); wheels.make_paddle_marks()"
# Writes textures/wheels_sidewall_{front,rear}_normal.png + _rough.png. u wraps once round the tyre
# (clockwise reading), v = 0 at r = SIDE_R0 (bead, just outside the beadlock ring), v = 1 at the
# shoulder radius SIDE_R1[kind]. Letters are laid out in metres so they keep their true shape.

SIDE_R0 = 0.2215
SIDE_R1 = {'front': 0.405, 'rear': 0.372}

# main ring: words spread evenly round the tyre (measured, so they never overlap), as on the real
# Glamis Tire Co sidewalls (photos: big, wide, widely spaced raised letters, once around)
SIDE_MAIN = {   # words, cap height m, tracking m, x-stretch, v centre, start angle deg
    # cap height ~42 mm as in rear_3q_right.png / front_3q_right.png; the rear ring sits low enough
    # (r 0.267..0.309) to clear the paddle end buttresses that come down over the shoulder
    'rear': (['GLAMIS', 'TIRE', 'CO', 'DUNE', 'PADDLE', '35.5"'], 0.042, 0.0080, 1.06, 0.44, 4.0),
    'front': (['GLAMIS TIRE CO', 'RIDGE CUTTER'], 0.042, 0.0072, 1.08, 0.50, 12.0),
}
SIDE_SMALL = {  # angle deg, text, cap height m, v centre
    'rear': [(60, 'TUBELESS  -  FOR SAND USE ONLY', 0.0062, 0.165),
             (228, '35 x 15 - 15     %d PADDLE     NHS     DOT ST7B 2419' % N_PADDLES, 0.0062, 0.165),
             (150, 'MADE IN U.S.A.', 0.0060, 0.165)],
    'front': [(40, 'TUBELESS  -  FOR SAND USE ONLY', 0.0065, 0.195),
              (215, '34 x 10 - 15     6 RIB     NHS     DOT ST7B 2419', 0.0065, 0.195),
              (322, 'MADE IN U.S.A.', 0.0062, 0.80)],
}


def make_textures(W=4096, H=256):
    import os
    import sys
    import numpy as np
    from PIL import Image, ImageDraw
    from common import TEX
    sys.path.insert(0, TEX)
    import texlib as T

    ss = 2
    Ws, Hs = W * ss, H * ss
    for kind in ('front', 'rear'):
        r0, r1 = SIDE_R0, SIDE_R1[kind]
        rm = 0.5 * (r0 + r1)
        pxm = Ws / (2 * math.pi * rm)                 # canvas pixels per metre (square, at mid radius)
        Hc = int(round((r1 - r0) * pxm))
        canvas = Image.new('L', (Ws, Hc), 0)
        def word_img(text, ch, trk, stretch, bold):
            fsize = max(8, int(ch * pxm / 0.73))
            f = T.font('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf', fsize)
            advs = [(c_, f.getlength(c_) if c_ != ' ' else fsize * 0.45) for c_ in text]
            tw = int(sum(a_ for _, a_ in advs) + trk * pxm * (len(advs) - 1)) + 8
            th = int(fsize * 1.4)
            tmp = Image.new('L', (tw, th), 0)
            d = ImageDraw.Draw(tmp)
            x = 4
            for c_, a_ in advs:      # glyph by glyph so the tracking is exact
                d.text((x, th * 0.5), c_, font=f, fill=255, anchor='lm')
                x += a_ + trk * pxm
            return tmp.resize((max(1, int(tw * stretch)), th), Image.LANCZOS)

        def put(img, x0, vc):
            x0 = int(x0) % Ws
            y0 = int((1 - vc) * Hc - img.height / 2)
            a_ = np.asarray(canvas).copy()
            src = np.asarray(img)
            cols = (np.arange(img.width) + x0) % Ws
            ys = slice(max(0, y0), min(Hc, y0 + img.height))
            sy = slice(ys.start - y0, ys.stop - y0)
            a_[ys, cols] = np.maximum(a_[ys, cols], src[sy, :])
            canvas.paste(Image.fromarray(a_))

        words, ch, trk, stretch, vc, start = SIDE_MAIN[kind]
        imgs = [word_img(w_, ch, trk, stretch, True) for w_ in words]
        gap = (Ws - sum(im.width for im in imgs)) / len(imgs)
        assert gap > 0, 'sidewall text does not fit'
        x = start / 360.0 * Ws
        for im in imgs:
            put(im, x, vc)
            x += im.width + gap
        for ang, text, chs, vcs in SIDE_SMALL[kind]:
            im = word_img(text, chs, chs * 0.25, 1.0, False)
            put(im, ang / 360.0 * Ws, vcs)
        letters = np.asarray(canvas.resize((Ws, Hs), Image.LANCZOS)).astype(np.float32) / 255.0
        yy = np.mgrid[0:Hs, 0:Ws][0].astype(np.float32)
        v = 1 - (yy + 0.5) / Hs
        # moulded rings: rim-guard ridge by the bead, fine rib, and a shoulder groove
        rings = (np.exp(-((v - 0.055) / 0.028) ** 2) * 1.0 + np.exp(-((v - 0.135) / 0.008) ** 2) * 0.45 +
                 np.exp(-((v - 0.955) / 0.010) ** 2) * -0.7 + np.exp(-((v - 0.915) / 0.006) ** 2) * 0.35)
        micro = T.fbm(Hs, Ws, 160, 611 if kind == 'front' else 612, octaves=3, tile=True)
        hl = T.blur(letters, 1.4)
        hgt = hl * 1.0 + rings * 0.7 + (micro - 0.5) * 0.06
        # r4: no colour map - the material is flat rubber #262626 and the lettering is black embossed: it
        # lives in the normal map (raised letters, moulded rings) and the roughness map only: satin-gloss
        # rubber SIDE_ROUGH 0.45, letter faces 0.34 (slightly glossier moulding, as the photos' letters catch
        # the light without being lighter grey), ridge tops a touch glossier, faint micro variation
        let = T.smoothstep(0.35, 0.9, hl)
        rough = SIDE_ROUGH - 0.11 * let - 0.03 * np.clip(rings, 0, 1) + 0.04 * (micro - 0.5)
        rgh = Image.fromarray((np.clip(rough, 0, 1) * 255 + 0.5).astype(np.uint8)).resize((W, H), Image.LANCZOS)
        nrm = Image.fromarray(T.normal_from_height(hgt * 5.0, strength=1.0, wrap='x')).resize((W, H), Image.LANCZOS)
        old = os.path.join(TEX, 'wheels_sidewall_%s.png' % kind)       # r3 colour strip (no longer used)
        if os.path.exists(old):
            os.remove(old)
        for img, name in ((nrm, 'wheels_sidewall_%s_normal.png' % kind),
                          (rgh, 'wheels_sidewall_%s_rough.png' % kind)):
            p = os.path.join(TEX, name)
            img.save(p, optimize=True)
            print('wrote', p, img.size, os.path.getsize(p) // 1024, 'KB')


# paint-pen digits as hand strokes in a unit box (x right, y up, baseline y = 0, cap height 1)
_MARKER_STROKES = {
    '3': [[(0.08, 0.86), (0.30, 1.00), (0.62, 0.98), (0.78, 0.80), (0.64, 0.58), (0.38, 0.52)],
          [(0.56, 0.55), (0.82, 0.40), (0.84, 0.16), (0.64, 0.01), (0.32, 0.00), (0.06, 0.15)]],
    '5': [[(0.86, 1.00), (0.28, 0.97), (0.20, 0.56), (0.48, 0.64), (0.76, 0.55), (0.88, 0.30),
           (0.78, 0.08), (0.50, 0.00), (0.22, 0.04), (0.06, 0.17)]],
    '2': [[(0.06, 0.74), (0.24, 0.96), (0.58, 1.00), (0.80, 0.84), (0.78, 0.60), (0.50, 0.34),
           (0.06, 0.00), (0.94, 0.04)]],
    '-': [[(0.10, 0.44), (0.66, 0.49)]],
    '.': [[(0.30, 0.03), (0.40, 0.07)]],
}
_MARKER_W = {'3': 0.62, '5': 0.62, '2': 0.64, '-': 0.56, '.': 0.42}
MARK_INKS = ((232, 230, 223), (201, 166, 64))      # row 0 off-white #e8e6df, row 1 gold #c9a640


def make_paddle_marks(W=2048, H=512, text='35.5-2'):
    """textures/wheels_paddle_marks.png (+ _rough.png): rubber colour with the paint-pen tyre-size number
    that the photos show on the paddles' driving faces. Two rows, each MARK_SPAN_V metres of driving face
    (v) by the full tread width spec.REAR_TIRE_W (u): row 0 (top half) off-white (rear.png / rear_3q:
    '35.5-2' on two paddles per tyre), row 1 (bottom half) gold (rear_wheel_sidepod_right.png, where the
    gold number on a front-top paddle reads upside down). The image top of each row is the paddle root,
    so the number reads upright from behind. Hand-written look: per-glyph baseline wander and size
    jitter, ~10 deg slant, wobbly ~2.2 mm strokes with round ends, text ~0.16 m wide on the outer half."""
    import os
    import numpy as np
    from PIL import Image, ImageDraw
    from common import TEX
    rng = np.random.default_rng(3552)
    span_u, span_v = spec.REAR_TIRE_W, MARK_SPAN_V
    k = 3                                         # supersample
    pxm = W * k / span_u                          # canvas px per metre (square pixels)
    Hc = int(round(span_v * pxm))
    rows_rgb, rows_rough = [], []
    for row, ink in enumerate(MARK_INKS):
        img = Image.new('L', (W * k, Hc), 0)
        d = ImageDraw.Draw(img)
        ch = (0.031 + 0.002 * row) * pxm              # cap height
        adv = [(_MARKER_W[c] + 0.20) * ch for c in text]
        x = (0.45 + 0.23 * row) * W * k - 0.5 * sum(adv)       # r4: white ~0.45 (rear.png), gold ~0.68 (rw)
        base0 = Hc * 0.5 + ch * 0.5
        slant = 0.17
        wpx = 0.0022 * pxm
        for c, a in zip(text, adv):
            dy = rng.normal(0, 0.05) * ch + (x / (W * k) - 0.5) * 0.10 * ch    # wander + rising line
            sc = 1.0 + rng.normal(0, 0.05)
            for stroke in _MARKER_STROKES[c]:
                # densify with a Catmull-Rom-ish chaikin pass for smooth hand curves
                pts = [(u + rng.normal(0, 0.018), v + rng.normal(0, 0.018)) for (u, v) in stroke]
                for _ in range(2):
                    q = [pts[0]]
                    for (u0, v0), (u1, v1) in zip(pts, pts[1:]):
                        q += [(0.75 * u0 + 0.25 * u1, 0.75 * v0 + 0.25 * v1), (0.25 * u0 + 0.75 * u1, 0.25 * v0 + 0.75 * v1)]
                    q.append(pts[-1])
                    pts = q
                P = [(x + (u + slant * v) * ch * sc, base0 - dy - v * ch * sc) for (u, v) in pts]
                for i, ((x0, y0), (x1, y1)) in enumerate(zip(P, P[1:])):
                    w = wpx * (0.85 + 0.3 * rng.random())
                    d.line([(x0, y0), (x1, y1)], fill=255, width=max(1, int(round(w))))
                    d.ellipse((x1 - w / 2, y1 - w / 2, x1 + w / 2, y1 + w / 2), fill=255)
                w = wpx
                d.ellipse((P[0][0] - w / 2, P[0][1] - w / 2, P[0][0] + w / 2, P[0][1] + w / 2), fill=255)
            x += a
        a = np.asarray(img.resize((W, H // 2), Image.LANCZOS)).astype(np.float32) / 255.0
        nz = Image.fromarray((rng.random((H // 8, W // 4)) * 255).astype(np.uint8)).resize((W, H // 2), Image.BICUBIC)
        noise = np.asarray(nz).astype(np.float32) / 255.0
        a = a * (0.72 + 0.28 * noise)                                   # patchy paint coverage
        rub = np.full(a.shape, float(int(RUBBER_HEX[1:3], 16)), np.float32)   # 'Tire tread' rubber (r4 #262626)
        rgb = np.stack([rub * (1 - a) + ink[i] * a for i in range(3)], -1)
        rows_rgb.append(rgb)
        rows_rough.append(PADDLE_ROUGH * (1 - a) + 0.72 * a)            # matte paint on glossy rubber
    rgb = np.concatenate(rows_rgb, 0)
    rough = np.concatenate(rows_rough, 0)
    for arr, name, mode in ((rgb, 'wheels_paddle_marks.png', 'RGB'), (rough * 255.0, 'wheels_paddle_marks_rough.png', 'L')):
        out = Image.fromarray(np.clip(arr + 0.5, 0, 255).astype(np.uint8), mode if mode == 'L' else None)
        p = os.path.join(TEX, name)
        out.save(p, optimize=True)
        print('wrote', p, out.size, os.path.getsize(p) // 1024, 'KB')


if __name__ == '__main__':
    import sys
    if '--textures' in sys.argv:
        make_textures()
        make_paddle_marks()
