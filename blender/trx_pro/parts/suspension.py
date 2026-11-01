"""Part 'suspension': the long-travel suspension the game animates.

FRONT (each side)  Sandline-style boxed lower A-arm (hexagonal box section, shock pockets + triangular
                   shock tabs on the front leg, raised SANDLINE plate, top gusset plate at the ball
                   joint), boxed upper A-arm (front leg swept forward around the coilover), uniball
                   cups + castle nuts, gunmetal upright/spindle with rear steering arm (double-shear
                   vertical bolt), hub carrier, orange anodized caliper on a slotted/drilled rotor,
                   tie rod with rod ends to the steering rack (static), black anodized dual-rate coilover
                   with a satin finned remote reservoir (static, 36 longitudinal fins) and a black anodized
                   bypass shock with three external bypass tubes + piggyback reservoir. The two shocks
                   lean steeply inboard (tops under the fender brows) and form the GLX's front 'V'.
REAR  (each side)  shallow boxed trailing arm (shock pockets with cross bolts, cross-bolt pivot sleeve
                   with visible bolt heads), upper + lower radius rods with rod ends, gunmetal hub
                   carrier with a big orange anodized caliper + bearing cap, rotor, half shaft with CV
                   housings and ribbed boots, black anodized coilover (remote reservoir, static) and
                   bypass shock; two black remote reservoirs with knurled caps and orange collars
                   clamped on the X-brace behind the seats, hoses to the rear bypass shock tops.

Every moving member is one straight-ish piece registered with C.segment(name, objs, a, b, wheel, shock)
so the game can re-aim it from a (chassis end) to b + dy (wheel end).  Shock lower mounts lie exactly
on the Link_XX_Lower_0 line.  Rotors + hubs go into the Wheel_XX groups (they spin), uprights /
carriers / calipers into Upright_XX.  Built for the LEFT side and mirrored.

Interfaces other parts read: F_COIL_TOP / F_BYP_TOP (front shock top pivots, left side = spec.F_SHOCK_TOPS;
parts/chassis.py builds its clevises there), F_LOWER_PIVOTS / R_TRAILING_PIVOT (= spec, what the arms pivot on).

[fix r3] Every hard point now comes from spec.py (FRONT_TRACK 1.84 / REAR_TRACK 1.93, new pivots, rack, shock
tops); everything else is derived from spec.WHEELS, so the corners follow the track. PROPOSED_SPEC is gone.
"""
import math
import os

import bpy
import bmesh
from mathutils import Vector, Matrix

from common import (M, mat, cylinder, lathe, loft, mirror_x, apply_transform, obj_from_bmesh,
                    uv_project, world_matrix, TEX)
import spec

V = Vector

# ------------------------------------------------------------------ hard points (LEFT side)
# [fix r3] spec.py only. Everything not in spec is derived from the wheel centres (spec.WHEELS), so the
# corners follow FRONT_TRACK / REAR_TRACK.

F_WC = V(spec.WHEELS['FL'][:3])            # (-0.92, 1.50, 0.432)
R_WC = V(spec.WHEELS['RL'][:3])            # (-0.965, -1.50, 0.455)
_F_IN = F_WC.x + spec.FRONT_TIRE_W / 2     # front tyre inner face (-0.805)
_R_IN = R_WC.x + spec.REAR_TIRE_W / 2      # rear tyre inner face (-0.785)


def lerp(a, b, t):
    return V(a) + (V(b) - V(a)) * t


def on_line_at_x(a, b, x):
    """Point on the line a-b where it crosses world x (shock lower mounts sit exactly on the arm line)."""
    a, b = V(a), V(b)
    return lerp(a, b, (x - a.x) / (b.x - a.x))


def on_arm_at_y(a, b, y):
    t = (y - a.y) / (b.y - a.y)
    return lerp(a, b, t)


F_LOWER_PIVOTS = [tuple(p) for p in spec.F_LOWER_PIVOTS]
LR_P = V(F_LOWER_PIVOTS[0])                # lower arm rear pivot  (-0.13, 1.28, 0.49)
LF_P = V(F_LOWER_PIVOTS[1])                # lower arm front pivot (-0.10, 1.78, 0.50)
UR_P = V(spec.F_UPPER_PIVOTS[0])           # upper arm rear pivot  (-0.14, 1.30, 0.70)
UF_P = V(spec.F_UPPER_PIVOTS[1])           # upper arm front pivot (-0.14, 1.72, 0.70)
# [fix r3] ball joints at FRONT_TRACK 1.84 (front.png): the lower arm slopes ~5 deg down outward from its 0.49/0.50
# pivots to a lower uniball at hub height, the upright leans in ~10 deg, the upper arm is about level
LBJ = F_WC + V((0.175, 0.0, 0.003))        # lower uniball (-0.745, 1.50, 0.435)
UBJ = F_WC + V((0.225, 0.0, 0.273))        # upper uniball (-0.695, 1.50, 0.705)
RACK = V(spec.F_STEER_RACK)                # inner tie-rod end (-0.11, 1.70, 0.62), front-steer rack behind the plate
# [fix r5] steering arm 4.5 cm longer forward (TRE y 1.68, was 1.635): the game steers the tie-rod end about the
# wheel centre's vertical axis, so at full lock (0.52) the old TRE swung back to y 1.52 and the tie rod cut through the
# coilover's spring / seat; now it clears them by >= 1.5 cm at any lock / travel (tie rod ~transverse at rest)
TRE = F_WC + V((0.190, 0.180, 0.123))      # outer tie-rod end on a FORWARD steering arm (-0.73, 1.68, 0.555)
#                                            [fix r4] z 0.55 -> 0.57 with the rack at 0.62. [fix r5] 0.57 -> 0.555: the
#                                            photo tie rods' slope (front.png AND front_3q agree) puts the heim ~1.5 cm lower

# front shocks: tops = spec.F_SHOCK_TOPS (the chassis builds its clevises there). Lower eyes (arbiter: coilover
# ~-0.60, bypass ~-0.66) in clevis tabs on the lower arm's top gusset, 4 cm above the arm plane. With the spec
# tops only 0.105 apart, both eyes on the front-leg line put the coilover's spring seat into the bypass and the
# spring 2 cm from the tie rod; so the coilover eye sits on the rear edge of the front leg (x -0.595, y 1.545:
# spring >= 3.5 cm behind the tie rod) and the bypass eye on the front edge of the rear leg (x -0.665, y 1.48):
# eyes 9.6 cm apart, bodies >= 1 cm apart over the whole +0.30/-0.33 travel. Both tab pairs belong to
# Link_FL_Lower_0 (the gusset), so the game's shock ratio (projection on that line) moves them with the arm.


def _lower_plane_z(x, y):
    """z of the lower A-arm's leg plane (LF_P, LR_P, LBJ) at (x, y)."""
    n = (LBJ - LF_P).cross(LR_P - LF_P)
    return LF_P.z - (n.x * (x - LF_P.x) + n.y * (y - LF_P.y)) / n.z


F_ARM_BOT_IN, F_ARM_BOT_OUT = 0.497, 0.39  # [fix r4] lower A-arm bottom edge z at the inner pivots / at the ball joint
F_ARM_DEEPEN, F_ARM_DEEPEN_T = 0.015, (0.28, 0.58)  # [fix r6] plate 1.5 cm deeper at mid/outer span (smoothstep)
#   (arbiter ~0.47; both overlays still put the r4 bottom 2.5-3 cm under the photo silhouette near the pivots -> 0.485)
#   [fix r5] 0.485 -> 0.497: front_3q's lower chamfer highlight and front.png's bottom edge both sit on the 0.50 line
F_UARM_R = 0.0159                          # [fix r6] upper A-arm legs: 1.25" round tube
F_UARM_BOW, F_UARM_BOW_T = 0.020, 0.72     # [fix r6] rear leg plan-view bow (rearward) and where along the leg it peaks
F_EYE_UP = 0.040                           # lower eyes above the arm plane (gusset top +0.016, eye ring r 0.0195)
F_SHOCK_TOPS = [tuple(p) for p in spec.F_SHOCK_TOPS]
F_COIL_TOP = V(F_SHOCK_TOPS[0])            # (-0.39, 1.60, 0.945)
F_BYP_TOP = V(F_SHOCK_TOPS[1])             # (-0.40, 1.495, 0.958)
# [fix r5] front.png (both sides, back-projected): the black-spring coilover's lower eye sits at |x| ~0.45 (front_3q puts
# the spring line at ~0.50-0.53), the outer shock (chrome shaft, external bypass tubes, finned can in line above it) at
# |x| ~0.60. r4 had them at 0.595 / 0.665, i.e. both ~6-14 cm too far out. Tops stay spec.F_SHOCK_TOPS.
# [fix r5b] full-lock check: the tie rod sweeps back to y ~1.59 at x -0.47, so the coilover eye moved back to y 1.502 and
# the bypass eye out / back to (-0.632, 1.467) (over the gusset's rear edge) to keep the spring >= 1.5 cm off both the
# tie rod (any steer / travel) and the bypass body. Front view |x|: coil 0.47, bypass 0.63 (photo ~0.45-0.50 / 0.60).
F_COIL_BOT = V((-0.465, 1.500, _lower_plane_z(-0.465, 1.500) + F_EYE_UP))
F_BYP_BOT = V((-0.632, 1.467, _lower_plane_z(-0.632, 1.467) + F_EYE_UP))

R_TRAILING_PIVOT = tuple(spec.R_TRAILING_PIVOT)
TP = V(R_TRAILING_PIVOT)                   # (-0.72, -0.84, 0.51)
# [fix r3] straight trailing arm: b on the axle line, 0.225 inboard of the wheel centre, so the arm centre line
# stays at |x| <= 0.735 alongside the tyre (outer face >= 1.9 cm inboard of its inner sidewall at |x| 0.785)
R_CARRIER = V((R_WC.x + 0.225, R_WC.y, R_WC.z))      # (-0.74, -1.50, 0.455) = trailing-arm b
R_CX = R_WC.x + 0.230                      # hub-carrier plate centre (-0.735): wholly inboard of the tyre
RRL_A = V(spec.R_RADIUS_ROD_PIVOTS[0])
RRU_A = V(spec.R_RADIUS_ROD_PIVOTS[1])
RRL_B = V((R_CX, R_WC.y + 0.070, R_WC.z - 0.165))    # (-0.735, -1.43, 0.29)
RRU_B = V((R_CX, R_WC.y + 0.070, R_WC.z + 0.160))    # (-0.735, -1.43, 0.615): carrier top + rod eye clear the
#                                                      pod's inner arch lip (|x| 0.71-0.75, z 0.93-1.04) at +0.30

# rear shocks: tops = spec.R_SHOCK_TOPS; bottoms on the trailing-arm line 8-9 cm behind the tops, so the
# shocks lean forward ~6 deg (side photo) and the coilover's motion ratio stays ~0.44
R_COIL_TOP = V(spec.R_SHOCK_TOPS[0])
R_BYP_TOP = V(spec.R_SHOCK_TOPS[1])
R_COIL_BOT = on_arm_at_y(TP, R_CARRIER, R_COIL_TOP.y - 0.080) + V((0.010, 0, 0))   # y -1.13, eye 1 cm inboard
#                                                      in its pocket: spring >= 1.5 cm off the pod skin at bump
R_BYP_BOT = on_arm_at_y(TP, R_CARRIER, R_BYP_TOP.y - 0.090)      # y -1.31
R_COIL_CAP_GAP = 0.080                     # rear coilover cap 8 cm under the eye: clears the tower clevis at bump
# [fix r4] shock top caps (distance eye -> cap top = gap - h): the game stretches each Shock_* mesh along a->b as one
# piece (k = 0.61 front / 0.77-0.86 rear at full bump), so the caps sit far enough down the neck that c * k stays
# clear of the chassis clevis plates (round ends R 0.025) and towers
R_COIL_CAP_H = 0.030
R_BYP_CAP_GAP, R_BYP_CAP_H = 0.082, 0.028
R_FIN_CAP = (0.046, 22)                    # [fix r6] rear.png finned caps (~8 cm dia, ~5 cm tall, longitudinal satin-alu
                                           # fins under the black cap) at the top of both rear shock bodies
F_COIL_CAP_GAP, F_COIL_CAP_H = 0.078, 0.024   # [fix r6] was 0.090 / 0.028: the long spring now ends at 0.74 of the
#                                               eye-to-eye length; narrow top cap r 0.024 (spec r6: <= 2.5 cm by the beak)
F_COIL_CAP_R = 0.024
F_COIL_SPRING_FRAC = 0.74
F_BYP_CAP_GAP, F_BYP_CAP_H = 0.100, 0.026
F_BYP_ZB = 0.44                            # [fix r6] front bypass body bottom at 0.44 of the eye-to-eye length (was 0.33):
#                                            front.png shows ~12 cm of chrome shaft under the body, and the rear upper leg
#                                            passes the shaft (not the 7 cm body) at droop
R_FIT_ANG = -0.785                         # rear coilover cap fitting. [fix r5] forward-inboard, toward the X-brace
#                                            reservoir's hose (was 0.9, forward-outboard; local x ~ world +y, local y ~
#                                            world -x = outboard)
R_BYP_FIT_ANG = -2.356                     # [fix r5] rear bypass cap fitting: rear-inboard, toward the pod-bay can
F_COIL_FIT_ANG = 2.356                     # (front coilover: no remote hose since r5, see F_BYP_FIT_*)
# [fix r5] the front finned can is the BYPASS shock's remote reservoir (front.png: it stands in line above the outer,
# bypass shock): the hose comes into a banjo on the rear rim of the bypass cap, tilted up toward the can
F_BYP_FIT_Z, F_BYP_FIT_RISE = 0.006, 0.0    # [fix r6] level banjo pointing straight back (the cap rises away from
#                                            the static hose at bump instead of into it)
F_BYP_TUBES = (0.0, 1.0)                   # [fix r5b] bypass tubes face OUTBOARD (local +y): the coilover is inboard
HS_A = V(spec.R_DIFF_OUTPUT)
HS_B = V((R_CX + 0.068, R_WC.y, R_WC.z))  # outer CV centre (-0.667), against the carrier's inner face

# wheel mounting faces (agreed with parts/wheels.py FRONT_HUB_FACE -0.020 / REAR_HUB_FACE -0.035, i.e. the
# faces lie that far INBOARD of the tyre centre planes); rotors sit inside the rim's inner flange
F_HUB_X = F_WC.x + 0.020                   # -0.90
R_HUB_X = R_WC.x + 0.035                   # -0.93
F_ROTOR_X = F_WC.x + 0.095                 # -0.825
R_ROTOR_X = R_WC.x + 0.150                 # -0.815 (inside the bead circle where it passes the tyre face)
ROTOR_R = 0.152


# ------------------------------------------------------------------ materials

def mats():
    return {
        'arm': M('arm'),
        'spring': M('gloss_black'),
        'black': M('satin_black'),
        'chrome': M('chrome'),
        'polished': M('polished'),
        'alu': M('alu'),
        'steel': M('steel_dark'),
        'rubber': M('rubber'),
        'orange': M('orange_anod'),
        'rotor': mat('Brake rotor', tex='suspension_rotor.png', metal=0.85, rough=0.38),
        'tatum': mat('Tatum arm plate', tex='suspension_tatum.png', metal=1.0, rough=0.25),   # [fix r6] polished
        'hose': mat('Shock hose', '#151516', rough=0.55),
        # [fix r2] shock bodies, bypass tubes, adjusters and reservoirs: black anodized (front_3q_right.png)
        'anod': mat('Black anodized', '#141416', metal=0.7, rough=0.22),   # [fix r5] rough 0.3 -> 0.22 (slight gloss)
        # [fix r3] finned front remote reservoirs + a near-black fin-root material so the fins read as deep ribs.
        # [fix r4] pale satin silver (photo cans 180-230 lit): at metal 1.0 the #8a8d92 mirrored the dark studio /
        # wheel wells and read black; half-metallic keeps a diffuse base that the game's hemisphere light lifts
        # [fix r6] arbiter: satin aluminium #b9bdc2, metal 1, rough .35 (was #b4b7bb m .5 r .38)
        'fin_alu': mat('Satin aluminum', '#b9bdc2', metal=1.0, rough=0.35),
        'fin_root': mat('Fin root dark', '#2a2b2e', metal=0.6, rough=0.5),
    }


# ------------------------------------------------------------------ textures

def ensure_textures():
    """Paint the two small textures this part owns (rotor face, SANDLINE arm plate) if missing / out of date."""
    rp = os.path.join(TEX, 'suspension_rotor.png')
    tp = os.path.join(TEX, 'suspension_tatum.png')
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    tat_ok = False
    if os.path.exists(tp):
        try:
            tat_ok = Image.open(tp).text.get('trx_ver') == TATUM_TEX_VER
        except Exception:
            tat_ok = False
    if os.path.exists(rp) and tat_ok:
        return
    rng = np.random.default_rng(7)
    if not os.path.exists(rp):
        paint_rotor(rp, rng, np, Image, ImageDraw, ImageFilter)
    if not tat_ok:
        paint_tatum(tp, np.random.default_rng(11), np, Image, ImageDraw, ImageFont, ImageFilter)


def paint_rotor(rp, rng, np, Image, ImageDraw, ImageFilter):

    # rotor: u = 0.5 + dy / (2 R), v = 0.5 + dz / (2 R); friction ring between 0.56 R and R
    S = 512
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    dx, dy = (xx - S / 2 + 0.5) / (S / 2), (yy - S / 2 + 0.5) / (S / 2)
    r = np.sqrt(dx * dx + dy * dy)
    ang = np.arctan2(dy, dx)
    base = 0.47 + 0.035 * np.sin(r * 420.0) + 0.02 * rng.standard_normal((S, S)).astype(np.float32)
    img = np.stack([base * 0.98, base, base * 1.03], -1)
    ring = (r > 0.56) & (r < 0.995)
    out = np.zeros_like(img) + 0.06
    out[ring] = img[ring]
    # darker heat-tint band near the outer edge, pad-wiped band in the middle
    out[ring] *= (0.92 + 0.08 * np.cos((r[ring] - 0.78) * 9.0))[:, None]
    im = Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    c = S / 2
    R = S / 2
    nsl = 12
    for k in range(nsl):          # curved slots
        a0 = 2 * math.pi * k / nsl
        pts = []
        for s in range(11):
            t = s / 10
            rr = 0.62 + 0.30 * t
            aa = a0 + 0.45 * t
            pts.append((c + R * rr * math.cos(aa), c + R * rr * math.sin(aa)))
        d.line(pts, fill=(22, 22, 24), width=int(S * 0.012))
    for k in range(nsl):          # cross-drilled holes between the slots
        a0 = 2 * math.pi * k / nsl
        for rr, da in ((0.69, 0.30), (0.80, 0.47), (0.89, 0.62)):
            aa = a0 + da
            hx, hy = c + R * rr * math.cos(aa), c + R * rr * math.sin(aa)
            hr = S * 0.0115
            d.ellipse([hx - hr - 2, hy - hr - 2, hx + hr + 2, hy + hr + 2], fill=(150, 152, 156))
            d.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=(10, 10, 11))
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    im.save(rp, optimize=True)


TATUM_TEX_VER = 'r6-polished'


def paint_tatum(tp, rng, np, Image, ImageDraw, ImageFont, ImageFilter):
    """[fix r6] SANDLINE plate (512 x 160): bright polished/brushed silver plate with black engraved SANDLINE and CUSTOM
    BUILT lettering (front.png / front_3q: the plates read as bright silver with dark letters). The material is
    metal 1 rough 0.25, so this image is the base colour: silver ~0.80, letters ~0.06."""
    from PIL import PngImagePlugin
    W, H = 512, 160
    row = np.convolve(rng.standard_normal(W + 2), np.ones(3) / 3.0, mode='valid').astype(np.float32)
    streak = np.repeat(row[None, :], H, 0)
    noise = rng.standard_normal((H, W)).astype(np.float32)
    yy = np.mgrid[0:H, 0:W][0].astype(np.float32) / H
    g = 0.80 + 0.018 * streak + 0.008 * noise + 0.03 * (0.5 - yy)
    bg = np.stack([g * 0.985, g, g * 1.02], -1)
    im = Image.fromarray(np.clip(bg * 255, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)

    def font(names, size):
        for root in ('/usr/share/fonts/truetype', '/usr/share/fonts/opentype'):
            for dp, _, files in os.walk(root):
                for n in names:
                    if n in files:
                        return ImageFont.truetype(os.path.join(dp, n), size)
        return ImageFont.load_default()

    f1 = font(['FreeSansBoldOblique.ttf', 'DejaVuSans-BoldOblique.ttf'], 108)
    f2 = font(['FreeSansBold.ttf', 'DejaVuSans-Bold.ttf'], 27)
    d.rounded_rectangle([4, 4, W - 5, H - 5], radius=14, outline=(120, 123, 128), width=4)      # chamfered edge
    d.rounded_rectangle([10, 10, W - 11, H - 11], radius=10, outline=(232, 234, 238), width=2)  # polished bevel
    # engraved letters: dark fill with a thin bright lower-right lip (cut edge catching light)
    for off, col in (((2, 2), (226, 228, 232)), ((0, 0), (16, 16, 18))):
        d.text((W / 2 + off[0], 64 + off[1]), 'SANDLINE', font=f1, fill=col, anchor='mm')
    for off, col in (((1, 1), (226, 228, 232)), ((0, 0), (18, 18, 20))):
        d.text((W / 2 + off[0], 130 + off[1]), 'CUSTOM  BUILT', font=f2, fill=col, anchor='mm')
    im = im.filter(ImageFilter.GaussianBlur(0.5))
    meta = PngImagePlugin.PngInfo()
    meta.add_text('trx_ver', TATUM_TEX_VER)
    im.save(tp, optimize=True, pnginfo=meta)


# ------------------------------------------------------------------ geometry helpers

def sharpen(o, deg=35.0):
    me = o.data
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=math.radians(deg))
    except Exception:
        pass
    return o


def frame(z, x_hint=(1, 0, 0)):
    z = V(z).normalized()
    xh = V(x_hint)
    x = xh - z * xh.dot(z)
    if x.length < 1e-5:
        alt = V((0, 1, 0)) if abs(z.y) < 0.9 else V((1, 0, 0))
        x = alt - z * alt.dot(z)
    x.normalize()
    return x, z.cross(x), z


def mat_from(origin, x, y, z):
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = V(origin)
    return m


def put(o, origin, z, x_hint=(1, 0, 0)):
    x, y, zz = frame(z, x_hint)
    o.matrix_basis = mat_from(origin, x, y, zz)
    return o


def cyl(name, r, p0, p1, material, segs=16, r2=None, cap=True, x_hint=(1, 0, 0), sharp=40):
    p0, p1 = V(p0), V(p1)
    d = p1 - p0
    o = cylinder(name, r, max(d.length, 1e-4), material=material, segments=segs, r2=r2, cap=cap)
    put(o, (p0 + p1) / 2, d, x_hint)
    return sharpen(o, sharp)


def hexnut(name, p, axis, r, h, material):
    return cyl(name, r, V(p) - V(axis).normalized() * h / 2, V(p) + V(axis).normalized() * h / 2, material,
               segs=6, sharp=30)


def lathe_at(name, profile, base, axis, material, segs=24, sharp=35, x_hint=(1, 0, 0)):
    """Revolve [(r, h)] around local Z (closed profiles repeat their first point), then place."""
    o = lathe(name, profile, material, segments=segs)
    put(o, base, axis, x_hint)
    return sharpen(o, sharp)


def bm_obj(name, bm, material, sharp=35):
    o = obj_from_bmesh(name, bm, material)
    return sharpen(o, sharp)


def sweep(name, pts, r, material, sides=12, cap=True, sharp=50, up=None):
    """Round tube along a polyline with parallel-transported frames. r: radius or per-point list."""
    pts = [V(p) for p in pts]
    n = len(pts)
    rad = list(r) if isinstance(r, (list, tuple)) else [r] * n
    T = []
    for i in range(n):
        if i == 0:
            d = pts[1] - pts[0]
        elif i == n - 1:
            d = pts[-1] - pts[-2]
        else:
            d = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
        T.append(d.normalized())
    ref = V(up) if up else (V((0, 0, 1)) if abs(T[0].z) < 0.9 else V((1, 0, 0)))
    N = (ref - T[0] * ref.dot(T[0])).normalized()
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(pts):
        if i > 0:
            N = T[i - 1].rotation_difference(T[i]) @ N
            N = (N - T[i] * N.dot(T[i])).normalized()
        B = T[i].cross(N)
        rings.append([bm.verts.new(p + (N * math.cos(a) + B * math.sin(a)) * rad[i])
                      for a in [2 * math.pi * k / sides for k in range(sides)]])
    for i in range(n - 1):
        r0, r1 = rings[i], rings[i + 1]
        for k in range(sides):
            bm.faces.new((r0[k], r0[(k + 1) % sides], r1[(k + 1) % sides], r1[k]))
    if cap:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    return bm_obj(name, bm, material, sharp)


def round_poly(pts, r, steps=2):
    """Fillet every corner of a closed 2D polygon (quadratic arcs; keeps vertex count constant)."""
    out = []
    n = len(pts)
    for i in range(n):
        ri = r[i] if isinstance(r, (list, tuple)) else r
        p0, p1, p2 = V((*pts[i - 1], 0)), V((*pts[i], 0)), V((*pts[(i + 1) % n], 0))
        d1, d2 = p0 - p1, p2 - p1
        l1, l2 = d1.length, d2.length
        d1.normalize(); d2.normalize()
        ang = d1.angle(d2)
        if ri <= 0 or ang > math.pi - 1e-3:
            out += [(p1.x, p1.y)] * (steps + 1)
            continue
        t = min(ri / math.tan(ang / 2), l1 * 0.49, l2 * 0.49)
        a, b = p1 + d1 * t, p1 + d2 * t
        for k in range(steps + 1):
            u = k / steps
            q = a * (1 - u) ** 2 + p1 * (2 * u * (1 - u)) + b * (u * u)
            out.append((q.x, q.y))
    return out


def rrect(w, h, r, steps=2):
    return round_poly([(w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2), (-w / 2, -h / 2)], r, steps)


def hexbox(w, h, ch=0.28, r=0.0035):
    """Sandline arm section: box with chamfered lower edges (u across the arm, v up)."""
    c = min(w, h) * ch
    pts = [(w / 2, -h / 2 + c), (w / 2, h / 2), (-w / 2, h / 2), (-w / 2, -h / 2 + c),
           (-w / 2 + c, -h / 2), (w / 2 - c, -h / 2)]
    return round_poly(pts, r, 1)


def beam(name, path, outlines, material, up=(0, 0, 1), sharp=32):
    """Loft closed 2D outlines (u horizontal-across, v up) along a 3D path."""
    up = V(up)
    secs = []
    n = len(path)
    path = [V(p) for p in path]
    for i, p in enumerate(path):
        if i == 0:
            T = path[1] - path[0]
        elif i == n - 1:
            T = path[-1] - path[-2]
        else:
            T = (path[i + 1] - path[i]).normalized() + (path[i] - path[i - 1]).normalized()
        T.normalize()
        U = up.cross(T)
        if U.length < 1e-5:
            U = V((1, 0, 0))
        U.normalize()
        W = T.cross(U)
        secs.append([p + U * u + W * v for (u, v) in outlines[i]])
    o = loft(name, secs, material, closed=True, cap=True)
    return sharpen(o, sharp)


def plate(name, outline, origin, ux, uy, th, material, holes=(), sharp=30, uvfn=None):
    """Extruded flat plate: 2D outline (+ optional hole loops) in the (ux, uy) plane, centred on origin."""
    ux, uy = V(ux).normalized(), V(uy).normalized()
    nz = ux.cross(uy).normalized()
    o0 = V(origin) - nz * (th / 2)
    bm = bmesh.new()
    edges = []
    for lp in [outline] + list(holes):
        # [fix r6] drop coincident consecutive points (round_poly repeats unrounded corners): with them,
        # triangle_fill silently failed on some orientations (the left rack clevis plates had no caps)
        q = []
        for pt in lp:
            if not q or abs(pt[0] - q[-1][0]) + abs(pt[1] - q[-1][1]) > 1e-7:
                q.append(pt)
        while len(q) > 3 and abs(q[0][0] - q[-1][0]) + abs(q[0][1] - q[-1][1]) <= 1e-7:
            q.pop()
        vs = [bm.verts.new(o0 + ux * a + uy * b) for (a, b) in q]
        for i in range(len(vs)):
            edges.append(bm.edges.new((vs[i], vs[(i + 1) % len(vs)])))
    res = bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges, normal=nz)
    faces = [g for g in res['geom'] if isinstance(g, bmesh.types.BMFace)]
    ext = bmesh.ops.extrude_face_region(bm, geom=faces)
    vs = [g for g in ext['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=nz * th, verts=vs)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = bm_obj(name, bm, material, sharp)
    if uvfn:
        uv_project(o, uvfn)
    return o


def circle2d(cx, cy, r, n=12):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def ring_profile(ri, ro, w, ch=0.002):
    """Closed lathe profile of a ring/eye: inner radius ri, outer ro, width w (centred)."""
    h = w / 2
    return [(ri, -h), (ro - ch, -h), (ro, -h + ch), (ro, h - ch), (ro - ch, h), (ri, h), (ri, -h)]


def to_world(objs, Mx):
    for o in objs:
        o.matrix_basis = Mx @ o.matrix_basis
    return objs


# ------------------------------------------------------------------ common sub-assemblies

def rod_end(name, centre, bore, shank_dir, m, r_out=0.021, w=0.026, shank=0.035, shank_r=0.0115,
            housing='alu', nut=True):
    """Heim joint: ring housing (bore axis), ball, shank toward the tube, jam nut."""
    c, bore, sd = V(centre), V(bore).normalized(), V(shank_dir).normalized()
    out = [lathe_at(name + '_eye', ring_profile(0.010, r_out, w * 0.8), c, bore, m[housing], segs=14)]
    out.append(lathe_at(name + '_ball', ring_profile(0.0068, 0.0125, w), c, bore, m['chrome'], segs=8))
    s0 = c + sd * (r_out * 0.8)
    out.append(cyl(name + '_neck', shank_r * 1.15, c + sd * (r_out * 0.55), s0 + sd * 0.008, m[housing], segs=10,
                   x_hint=bore))
    out.append(cyl(name + '_shank', shank_r, s0, s0 + sd * shank, m['chrome'], segs=10, x_hint=bore))
    if nut:
        out.append(hexnut(name + '_jam', s0 + sd * (shank * 0.55), sd, shank_r * 1.6, 0.010, m['alu']))
    return out


def bolt(name, p, axis, length, m, r=0.0065, head='alu'):
    p, a = V(p), V(axis).normalized()
    out = [cyl(name, r, p - a * length / 2, p + a * length / 2, m['steel'], segs=8)]
    out.append(hexnut(name + '_head', p + a * (length / 2 + 0.0035), a, r * 1.8, 0.007, m[head]))
    out.append(hexnut(name + '_nut', p - a * (length / 2 + 0.004), a, r * 1.8, 0.008, m[head]))
    return out


def spring_coil(name, r_mean, wire, z0, z1, active, material, seg=12, sides=6, dead=0.75):
    """Helical spring along local Z from z0 to z1 with closed, ground ends."""
    L = z1 - z0
    p_dead = wire * 2.05
    turns = active + 2 * dead
    act_len = L - 2 * dead * p_dead - 2 * wire
    p_act = act_len / active
    pts = []
    n = int(turns * seg) + 1
    for i in range(n):
        s = turns * i / (n - 1)
        if s < dead:
            h = s * p_dead
        elif s > turns - dead:
            h = dead * p_dead + active * p_act + (s - dead - active) * p_dead
        else:
            h = dead * p_dead + (s - dead) * p_act
        a = 2 * math.pi * s
        pts.append((r_mean * math.cos(a), r_mean * math.sin(a), z0 + wire + h))
    return sweep(name, pts, wire, material, sides=sides, cap=True, sharp=70)


# ------------------------------------------------------------------ shocks

def shock_frame(bot, top, bore=(0, 1, 0)):
    """Local frame: z from the lower eye to the upper eye, x = eye bore (`bore` projected)."""
    bot, top = V(bot), V(top)
    x, y, z = frame(top - bot, bore)
    return mat_from(bot, x, y, z), (top - bot).length


def eye_pair(name, L, m, mat_key='anod', w=0.028, bot_axis=None):
    """Upper + lower eyes with spherical bearings, bore along local X (bot_axis: local bore of the lower eye
    when the shaft eyelet is clocked differently, e.g. a cross bolt through a trailing-arm pocket)."""
    out = []
    for z in (0.0, L):
        ax = V((1, 0, 0))
        if z == 0.0 and bot_axis is not None:
            ax = V(bot_axis)
            ax = V((ax.x, ax.y, 0.0)).normalized()
        out.append(lathe_at(name + '_eye', ring_profile(0.0095, 0.0195, w * 0.85), (0, 0, z), ax,
                            m[mat_key], segs=12, x_hint=(0, 0, 1)))
        out.append(lathe_at(name + '_brg', ring_profile(0.0065, 0.0115, w), (0, 0, z), ax, m['chrome'],
                            segs=8, x_hint=(0, 0, 1)))
    return out


def _local_dir(Mx, d):
    return Mx.to_3x3().inverted() @ V(d)


def coilover(name, bot, top, m, body_r=0.031, spring_r=0.041, wire=0.0068, body_mat='anod',
             res_side=None, front=True, seat_z=0.044, bore=(0, 1, 0), coil_seg=12, bot_bore=None, fit_side=-1,
             spring_top_z=None, fit_ang=None, n_turns=None, boss_z0=0.012, cap_gap=0.070, cap_h=0.036,
             cap_cone=False, spring_top_frac=None, spring_sides=6, fit=True, cap_r=None, fin_cap=None):
    """Black anodized dual-rate coilover: lower eye + spring seat on the shaft, chrome shaft, body with
    tender/main springs, crossover slider, threaded preload collar, top cap with hose fitting.
    seat_z: height of the lower spring seat above the lower eye (clears a boxed arm around the eye)."""
    Mx, L = shock_frame(bot, top, bore)
    o = eye_pair(name, L, m, bot_axis=None if bot_bore is None else _local_dir(Mx, bot_bore))
    zb = 0.30 * L if front else 0.27 * L        # body bottom (shaft exposed below)
    zt = L - cap_gap                             # cap top (cap_gap - cap_h) under the upper eye: clears the clevis
    # plates. [fix r4] the game scales the whole shock along its axis, so a part at distance c from the top eye ends at
    # c * k (front k 0.61 at full bump): short caps well down the neck stay out of the clevis plates
    o.append(cyl(name + '_neck', 0.0105, (0, 0, zt + cap_h - 0.006), (0, 0, L - 0.012), m['anod'], segs=12))
    # lower end: eyelet boss + spring seat
    o.append(cyl(name + '_boss', 0.017, (0, 0, boss_z0), (0, 0, seat_z + 0.001), m['anod'], segs=14))
    o.append(lathe_at(name + '_seat_lo', [(0.012, 0.0), (spring_r + wire + 0.004, 0.0),
                                          (spring_r + wire + 0.004, 0.008), (0.018, 0.012), (0.012, 0.012),
                                          (0.012, 0.0)],
                      (0, 0, seat_z), (0, 0, 1), m['anod'], segs=18))
    o.append(cyl(name + '_bump', 0.016, (0, 0, seat_z + 0.011), (0, 0, seat_z + 0.031), m['rubber'], segs=12))
    o.append(cyl(name + '_shaft', 0.011, (0, 0, seat_z + 0.006), (0, 0, zb + 0.01), m['chrome'], segs=14))
    # body
    o.append(lathe_at(name + '_body', [(0.0, 0.0), (body_r - 0.002, 0.0), (body_r + 0.002, 0.006),
                                       (body_r + 0.002, 0.030), (body_r, 0.034), (body_r, zt - zb - 0.03),
                                       (body_r + 0.003, zt - zb - 0.026), (body_r + 0.003, zt - zb),
                                       (0.0, zt - zb)],
                      (0, 0, zb), (0, 0, 1), m[body_mat], segs=16))
    # top cap + hose banjo
    sc_ = cap_h / 0.036
    cprof = ([(0.0, 0.0), (body_r + 0.004, 0.0), (body_r + 0.004, 0.022 * sc_), (body_r - 0.004, 0.030 * sc_),
              (0.015, cap_h), (0.0, cap_h)] if not cap_cone else      # [fix r4] conical top: less to swing into the
             [(0.0, 0.0), (body_r + 0.004, 0.0), (body_r + 0.004, 0.010), (body_r - 0.006, 0.016),   # clevis plates
              (0.016, cap_h), (0.0, cap_h)])
    if cap_r is not None:                     # [fix r6] narrow top: shoulder off the body, then a <= cap_r cap
        cprof = [(0.0, 0.0), (body_r + 0.003, 0.0), (body_r + 0.003, 0.004), (cap_r, 0.013), (cap_r, cap_h - 0.005),
                 (cap_r - 0.006, cap_h), (0.0, cap_h)]
    o.append(lathe_at(name + '_cap', cprof,
                      (0, 0, zt), (0, 0, 1), m['anod'], segs=16))
    if fin_cap is not None:                   # [fix r6] finned band at the top of the body (rear.png finned caps)
        fh, ribs = fin_cap
        o.append(fin_band(name + '_fins', zt - fh, zt - 0.001, body_r + 0.0005, body_r + 0.0065, ribs, m, lite=True))
    fx, fy = (0.0, fit_side) if fit_ang is None else (math.cos(fit_ang), math.sin(fit_ang))
    if fit:
        o.append(cyl(name + '_fit', 0.008, (fx * (body_r - 0.002), fy * (body_r - 0.002), zt + 0.014),
                     (fx * (body_r + 0.016), fy * (body_r + 0.016), zt + 0.014), m['alu'], segs=8))
    # springs: main (bottom) + tender (top) with crossover slider, preload collars on the body
    s0 = seat_z + 0.014
    s_top = zt - 0.075
    if spring_top_z is not None:              # [fix r3] spring ends at this world height (under the upper arm)
        dz = (V(top) - V(bot)).normalized().z
        s_top = min(s_top, max(s0 + 0.08, (spring_top_z - V(bot).z) / max(dz, 0.2)))
    if spring_top_frac is not None:           # [fix r5] long spring: ends at this fraction of the eye-to-eye length
        s_top = min(zt - 0.03, spring_top_frac * L)
    split = s0 + (s_top - s0) * 0.62
    n_main, n_tend = 6.0, 3.2
    if n_turns is not None:
        n_main, n_tend = n_turns
    elif spring_top_z is not None:             # shortened spring: keep a realistic coil pitch
        n_main = max(3.0, round((split - 0.006 - s0) / 0.024 * 2) / 2)
        n_tend = max(2.0, round((s_top - split - 0.006) / 0.021 * 2) / 2)
    o.append(spring_coil(name + '_main', spring_r, wire, s0, split - 0.006, n_main, m['spring'], seg=coil_seg,
                         sides=spring_sides))
    o.append(spring_coil(name + '_tender', spring_r, wire * 0.8, split + 0.006, s_top, n_tend, m['spring'],
                         seg=coil_seg, sides=spring_sides))
    ro = spring_r + wire + 0.003
    o.append(lathe_at(name + '_slider', [(body_r + 0.0015, -0.007), (ro, -0.007), (ro, 0.007),
                                         (body_r + 0.0015, 0.007), (body_r + 0.0015, -0.007)],
                      (0, 0, split), (0, 0, 1), m['alu'], segs=18))
    o.append(lathe_at(name + '_collar', [(body_r + 0.001, 0.0), (ro, 0.0), (ro, 0.010), (body_r + 0.006, 0.016),
                                         (body_r + 0.001, 0.016), (body_r + 0.001, 0.0)],
                      (0, 0, s_top), (0, 0, 1), m['anod'], segs=18))
    if res_side is not None:                      # piggyback reservoir
        sx, sy = res_side
        rz0, rz1 = zt - 0.20, zt - 0.005
        off = V((sx, sy, 0)) * (body_r + 0.026)
        o.append(lathe_at(name + '_res', [(0.0, 0.0), (0.020, 0.0), (0.023, 0.004), (0.023, rz1 - rz0 - 0.004),
                                          (0.020, rz1 - rz0), (0.0, rz1 - rz0)],
                          off + V((0, 0, rz0)), (0, 0, 1), m['anod'], segs=16))
        o.append(cyl(name + '_res_cap', 0.016, off + V((0, 0, rz0 - 0.012)), off + V((0, 0, rz0)), m['alu'], segs=12))
        o.append(cyl(name + '_res_bridge', 0.012, V((0, 0, zt + 0.008)), off * 1.02 + V((0, 0, zt + 0.008)),
                     m['anod'], segs=10))
    return to_world(o, Mx), L


def bypass(name, bot, top, m, body_mat='anod', body_r=0.034, tube_side=(0, 1), res_side=None, bore=(0, 1, 0),
           bot_bore=None, cap_fit=False, low0=0.012, cap_gap=0.076, cap_h=0.034, cap_cone=False, tube_mat='anod',
           knob_out=1.45, fit_ang=0.0, fit_z=0.010, fit_rise=0.0, zb_frac=0.33, fin_cap=None):
    """Bypass shock: lower eye + black bump cap, chrome shaft, black anodized body with 3 external bypass
    tubes and adjuster blocks, top cap, optional piggyback reservoir. [fix r2] Only the shaft is bright
    (front_3q_right.png: the bypass body and its tubes are black anodized, like the coilover)."""
    Mx, L = shock_frame(bot, top, bore)
    o = eye_pair(name, L, m, bot_axis=None if bot_bore is None else _local_dir(Mx, bot_bore))
    lc = 0.092 - low0
    o.append(lathe_at(name + '_lowcap', [(0.0, 0.0), (0.018, 0.0), (0.026, 0.010), (0.028, 0.020),
                                         (0.028, lc - 0.010), (0.024, lc - 0.002), (0.012, lc), (0.0, lc)],
                      (0, 0, low0), (0, 0, 1), m['anod'], segs=16))
    zb = zb_frac * L                             # [fix r6] front: 0.44 (front.png shows ~12 cm of chrome shaft)
    zt = L - cap_gap                             # cap top (cap_gap - cap_h) under the upper eye (see coilover)
    o.append(cyl(name + '_neck', 0.0105, (0, 0, zt + cap_h - 0.006), (0, 0, L - 0.012), m['anod'], segs=12))
    o.append(cyl(name + '_shaft', 0.011, (0, 0, 0.09), (0, 0, zb + 0.01), m['chrome'], segs=14))
    o.append(lathe_at(name + '_body', [(0.0, 0.0), (body_r - 0.003, 0.0), (body_r + 0.003, 0.006),
                                       (body_r + 0.003, 0.034), (body_r, 0.038), (body_r, zt - zb - 0.03),
                                       (body_r + 0.003, zt - zb - 0.026), (body_r + 0.003, zt - zb),
                                       (0.0, zt - zb)],
                      (0, 0, zb), (0, 0, 1), m[body_mat], segs=16))
    sc_ = cap_h / 0.034
    cprof = ([(0.0, 0.0), (body_r + 0.004, 0.0), (body_r + 0.004, 0.020 * sc_), (body_r - 0.006, 0.030 * sc_),
              (0.015, cap_h), (0.0, cap_h)] if not cap_cone else
             [(0.0, 0.0), (body_r + 0.004, 0.0), (body_r + 0.004, 0.010), (body_r - 0.006, 0.016),
              (0.016, cap_h), (0.0, cap_h)])
    o.append(lathe_at(name + '_cap', cprof,
                      (0, 0, zt), (0, 0, 1), m['anod'], segs=16))
    if fin_cap is not None:                       # [fix r6] finned band at the top of the body (rear.png finned caps)
        fh, ribs = fin_cap
        o.append(fin_band(name + '_fins', zt - fh, zt - 0.001, body_r + 0.0005, body_r + 0.0065, ribs, m, lite=True))
    if cap_fit:                                   # remote-reservoir hose fitting on the cap (default: forward side)
        fx, fy = math.cos(fit_ang), math.sin(fit_ang)
        f0 = V((fx * (body_r - 0.002), fy * (body_r - 0.002), zt + fit_z))
        f1 = V((fx * (body_r + 0.016), fy * (body_r + 0.016), zt + fit_z + 0.018 * fit_rise))
        o.append(cyl(name + '_fit', 0.008, f0, f1, m['alu'], segs=8))
    # external bypass tubes on one side of the body
    ux, uy = tube_side
    base = math.atan2(uy, ux)
    rr = body_r + 0.012
    bl = zt - zb                                  # [fix r6] tube spans scale with the body length
    for k, da in enumerate((-0.62, 0.0, 0.62)):
        a = base + da
        cx, cy = rr * math.cos(a), rr * math.sin(a)
        z0 = zb + bl * (0.15 + 0.07 * k)
        z1 = zt - bl * (0.08 + 0.05 * (2 - k))
        o.append(cyl(name + '_tube', 0.0065, (cx, cy, z0), (cx, cy, z1), m[tube_mat], segs=10))
        for z in (z0, z1):
            o.append(cyl(name + '_blk', 0.011, (cx * 0.86, cy * 0.86, z - 0.011), (cx * 0.86, cy * 0.86, z + 0.011),
                         m['anod'], segs=6))
            o.append(cyl(name + '_knob', 0.0085, (cx * 1.12, cy * 1.12, z), (cx * knob_out, cy * knob_out, z),
                         m['anod'], segs=10))
    if res_side is not None:
        sx, sy = res_side
        rz0, rz1 = zt - 0.25, zt - 0.05
        off = V((sx, sy, 0)) * (body_r + 0.027)
        o.append(lathe_at(name + '_res', [(0.0, 0.0), (0.019, 0.0), (0.022, 0.004), (0.022, rz1 - rz0 - 0.004),
                                          (0.019, rz1 - rz0), (0.0, rz1 - rz0)],
                          off + V((0, 0, rz0)), (0, 0, 1), m['anod'], segs=16))
        o.append(cyl(name + '_res_cap', 0.016, off + V((0, 0, rz0 - 0.012)), off + V((0, 0, rz0)), m['anod'], segs=12))
        o.append(cyl(name + '_res_bridge', 0.012, V((0, 0, rz1 - 0.012)), off * 1.02 + V((0, 0, rz1 - 0.012)),
                     m['anod'], segs=10))
    return to_world(o, Mx), L


# ------------------------------------------------------------------ brakes / hubs

def rotor_uv(axis_x, cy, cz, R):
    def f(co, n):
        return (0.5 + (co.y - cy) / (2 * R), 0.5 + (co.z - cz) / (2 * R))
    return f


def rotor_assembly(name, wc, rotor_x, hub_x, m):
    """Spinning parts: slotted/drilled rotor ring, black hat, hub flange with studs."""
    wc = V(wc)
    c = V((rotor_x, wc.y, wc.z))
    ax = V((-1, 0, 0))               # local Z toward the wheel (outboard, left side)
    th = 0.028
    ri = 0.088
    prof = [(ri, -th / 2), (ROTOR_R - 0.002, -th / 2), (ROTOR_R, -th / 2 + 0.002), (ROTOR_R, th / 2 - 0.002),
            (ROTOR_R - 0.002, th / 2), (ri, th / 2), (ri, -th / 2)]
    rot = lathe_at(name + '_rotor', prof, c, ax, m['rotor'], segs=32, sharp=30)
    uv_project(rot, rotor_uv(rotor_x, wc.y, wc.z, ROTOR_R))
    out = [rot]
    # vent vanes visible between the two faces are implied by the texture; hat cup to the hub face
    hat_len = abs(hub_x - rotor_x) - th / 2
    hat = [(ri + 0.004, 0.0), (ri - 0.002, 0.0), (ri - 0.002, hat_len - 0.006), (ri - 0.008, hat_len),
           (0.045, hat_len), (0.045, hat_len - 0.006), (ri - 0.008, 0.004), (ri + 0.004, 0.004), (ri + 0.004, 0.0)]
    out.append(lathe_at(name + '_hat', hat, c + ax * (th / 2 - 0.002), ax, m['black'], segs=16))
    # hub barrel + flange (stops at the wheel mounting face)
    hx0 = rotor_x + 0.03 if rotor_x < -1.0 else rotor_x + 0.02
    out.append(cyl(name + '_hubbarrel', 0.036, (hx0, wc.y, wc.z), (hub_x + 0.012, wc.y, wc.z), m['alu'], segs=16))
    out.append(cyl(name + '_hubflange', 0.080, (hub_x + 0.010, wc.y, wc.z), (hub_x + 0.0005, wc.y, wc.z), m['alu'],
                   segs=24))
    for k in range(6):
        a = 2 * math.pi * k / 6 + math.pi / 6
        p = V((0, 0.062 * math.cos(a), 0.062 * math.sin(a))) + V((0, wc.y, wc.z))
        out.append(cyl(name + '_stud', 0.0065, (hub_x + 0.006, p.y, p.z), (hub_x - 0.012, p.y, p.z), m['steel'],
                       segs=8))
    return out


def caliper(name, wc, rotor_x, ang, m, arc=0.16, r0=0.098, r1=0.162, width=0.064):
    """Curved orange anodized caliper straddling the rotor rim. ang: centre angle in the YZ plane
    (0 = +Y forward, +90 deg = up)."""
    wc = V(wc)
    n = 7
    half = arc / ((r0 + r1) / 2) / 2
    secs = []
    for i in range(n):
        a = ang - half + 2 * half * i / (n - 1)
        ca, sa = math.cos(a), math.sin(a)
        rad = V((0, ca, sa))
        prof = rrect(r1 - r0, width, 0.007, 2)
        cen = V((rotor_x, wc.y, wc.z)) + rad * ((r0 + r1) / 2)
        secs.append([cen + rad * u + V((1, 0, 0)) * v for (u, v) in prof])
    body = sharpen(loft(name + '_body', secs, m['orange']), 32)
    out = [body]
    # bridge bolts + pad pin across the rotor
    for da in (-half * 0.7, half * 0.7):
        a = ang + da
        p = V((rotor_x, wc.y + (r1 - 0.012) * math.cos(a), wc.z + (r1 - 0.012) * math.sin(a)))
        out.append(cyl(name + '_bolt', 0.0065, p - V((width / 2 + 0.006, 0, 0)), p + V((width / 2 + 0.006, 0, 0)),
                       m['alu'], segs=6))
    a = ang
    p = V((rotor_x, wc.y + (r1 + 0.004) * math.cos(a), wc.z + (r1 + 0.004) * math.sin(a)))
    out.append(cyl(name + '_pin', 0.004, p - V((width / 2, 0, 0)), p + V((width / 2, 0, 0)), m['chrome'], segs=8))
    # bleeder + line fitting
    p = V((rotor_x + width / 2 - 0.01, wc.y + r1 * math.cos(ang + half * 0.5), wc.z + r1 * math.sin(ang + half * 0.5)))
    out.append(cyl(name + '_bleed', 0.004, p, p + V((0, math.cos(ang + half * 0.5), math.sin(ang + half * 0.5))) * 0.014,
                   m['alu'], segs=6))
    return out


# ------------------------------------------------------------------ FRONT corner (left)

def front_corner(m):
    segs = {}
    up = V((0, 0, 1))

    # ---------------- lower A-arm, front leg (Link_FL_Lower_0) ----------------
    a, b = LF_P, LBJ
    D = b - a
    L = D.length
    d = D.normalized()
    U = up.cross(d).normalized()           # across the leg, toward the rear leg
    TOP = 0.007                             # arm top surface above the a-b line (shock eyes sit in pockets)

    # [fix r4] Sandline taper (front.png): the top edge stays (centred on the pivot sleeve, TOP above the a-b line from
    # t 0.25), the BOTTOM edge is one straight line from F_ARM_BOT_IN at the inner pivot to F_ARM_BOT_OUT at the ball
    # joint, so the box tapers from ~5.5 cm at the sleeve to ~4 cm a quarter of the way out and ~5 cm at the ball
    # joint (the r3 arm was a 7.8 cm parallelogram plate whose bottom sat 2-5 cm under the photo's)
    def top_off(t):
        s_ = min(1.0, max(0.0, (t - 0.02) / 0.23))
        return 0.026 + (TOP - 0.026) * s_

    def bot_z(t):
        # [fix r6] critic r5: the photo plate is ~1.5 cm deeper from mid span out (pivots / ball joint unchanged)
        s_ = min(1.0, max(0.0, (t - F_ARM_DEEPEN_T[0]) / (F_ARM_DEEPEN_T[1] - F_ARM_DEEPEN_T[0])))
        return F_ARM_BOT_IN + (F_ARM_BOT_OUT - F_ARM_BOT_IN) * t - F_ARM_DEEPEN * s_ * s_ * (3 - 2 * s_)

    def fw(t):
        return 0.042 + 0.010 * min(1.0, t / 0.30) - 0.008 * max(0.0, 1.0 - t / 0.08)

    def leg_section(p, t, w):
        top = p.z + top_off(t)
        bot = min(bot_z(t), top - 0.036)
        return V((p.x, p.y, (top + bot) / 2)), hexbox(w, top - bot), top, bot

    path, outl = [], []
    N = 18
    for i in range(N):
        t = 0.03 + 0.92 * i / (N - 1)
        q, o_, _, _ = leg_section(a + D * t, t, fw(t))
        path.append(q)
        outl.append(o_)
    lo0 = [beam('fl_lower_front', path, outl, m['arm'])]
    # inner pivot sleeve (bolt along Y between the chassis clevis plates, gap 0.05)
    lo0.append(lathe_at('fl_lower_sleeve_f', ring_profile(0.0085, 0.024, 0.046), a, (0, 1, 0), m['arm'], segs=16))
    lo0.append(lathe_at('fl_lower_bush_f', ring_profile(0.0068, 0.0105, 0.048), a, (0, 1, 0), m['black'], segs=10))
    # outer uniball cup (vertical) + top gusset plate tying both legs
    lo0.append(lathe_at('fl_lbj_cup', [(0.0, -0.026), (0.030, -0.026), (0.034, -0.022), (0.034, 0.022),
                                       (0.030, 0.026), (0.0, 0.026)], b, (0, 0, 1), m['arm'], segs=20))
    a2 = LR_P
    D2 = b - a2
    d2 = D2.normalized()
    gu = d
    gv = (d2 - d * d2.dot(d)).normalized()
    org = b + up * (TOP + 0.003)

    def to2(q):
        q = q - b
        return (q.dot(gu), q.dot(gv))
    # [fix r3] the gusset carries both shock clevises; its rear edge stops at t 0.76 of the rear leg (the game
    # moves this plate with the front leg, so a long rear edge would sink into the rear leg at droop)
    # [fix r5] rear-leg corner t 0.76 -> 0.72 so the bypass tabs (eye now x -0.60) stand wholly on the plate
    gpl = [to2(a + D * 0.56), to2(a + D * 0.96), to2(a2 + D2 * 0.96), to2(a2 + D2 * 0.72)]
    gpl = round_poly(gpl, [0.012, 0.02, 0.02, 0.012], 2)
    lo0.append(plate('fl_lower_gusset', gpl, org, gu, gv, 0.006, m['arm']))
    # [fix r5] the coilover eye (x -0.48) sits 2 cm behind the front leg's rear face, inboard of the gusset: a welded
    # shelf (top plate + rear web) cantilevered off the leg's rear face carries its tabs (it stays with this leg)
    zt_ = _lower_plane_z(F_COIL_BOT.x, F_COIL_BOT.y) + TOP + 0.003
    y_face = a.y + D.y * ((F_COIL_BOT.x - a.x) / D.x) + 0.004       # front leg centre line at the eye's x (+4 mm in)
    y_back = F_COIL_BOT.y - 0.032
    shelf = round_poly([(-0.036, y_back - F_COIL_BOT.y), (0.036, y_back - F_COIL_BOT.y),
                        (0.036, y_face - F_COIL_BOT.y - 0.015), (-0.036, y_face - F_COIL_BOT.y + 0.015)],
                       [0.008, 0.008, 0.0, 0.0], 2)
    lo0.append(plate('fl_coil_shelf', shelf, V((F_COIL_BOT.x, F_COIL_BOT.y, zt_)), (1, 0, 0), (0, 1, 0), 0.006,
                     m['arm']))
    web_h = zt_ - bot_z(0.62) - 0.004
    lo0.append(plate('fl_coil_web', rrect(0.072, web_h, 0.006, 2), V((F_COIL_BOT.x, y_back + 0.003, zt_ - web_h / 2)),
                     (1, 0, 0), (0, 0, 1), 0.006, m['arm']))
    # [fix r3] shock clevis tabs standing on the gusset / shelf (bolt along Y, like the hinge)
    for p_m, hw in ((F_COIL_BOT, 0.034), (F_BYP_BOT, 0.040)):
        tri = round_poly([(-hw, -0.030), (hw, -0.030), (0.026, 0.006), (0.0, 0.028), (-0.026, 0.006)],
                         [0.003, 0.003, 0.010, 0.017, 0.010], 2)
        for sgn in (-1, 1):
            lo0.append(plate('fl_shock_tab', tri, p_m + V((0, sgn * 0.0185, 0)), (1, 0, 0), (0, 0, 1), 0.005,
                             m['arm']))
        lo0 += bolt('fl_shock_bolt', p_m, (0, 1, 0), 0.050, m)
    # raised SANDLINE plate on the front face, near the outer end ([fix r4] sized to the tapered face's flat band, above
    # the lower chamfer)
    nface = -U                               # front face normal (forward / outward)
    tt = 0.76
    _, _, ttop, tbot = leg_section(a + D * tt, tt, fw(tt))
    ch_ = min(fw(tt), ttop - tbot) * 0.28
    PW, PH = 0.110, min(0.032, ttop - tbot - ch_ - 0.004)
    pc = a + D * tt
    pc = V((pc.x, pc.y, (ttop + tbot + ch_) / 2)) + nface * (fw(tt) / 2 + 0.002)
    tat = plate('fl_tatum_plate', rrect(PW, PH, 0.005, 2), pc, d, up, 0.004, m['tatum'])
    uv_project(tat, (lambda c0, dd: (lambda co, n: (0.5 + (co - c0).dot(dd) / PW,
                                                     0.5 + (co.z - c0.z) / PH)))(pc, d))
    lo0.append(tat)
    segs['Link_FL_Lower_0'] = (lo0, a, b, False)

    # ---------------- lower A-arm, rear leg (Link_FL_Lower_2) ----------------
    a2 = LR_P
    D2 = b - a2
    path, outl = [], []
    for i in range(12):                      # [fix r4] same straight bottom edge as the front leg; starts at t 0.04
        t = 0.04 + 0.89 * i / 11
        q, o_, _, _ = leg_section(a2 + D2 * t, t, 0.040 - 0.006 * max(0.0, 1.0 - t / 0.10))
        path.append(q)
        outl.append(o_)
    lo2 = [beam('fl_lower_rear', path, outl, m['arm'])]
    lo2.append(lathe_at('fl_lower_sleeve_r', ring_profile(0.0085, 0.024, 0.046), a2, (0, 1, 0), m['arm'], segs=16))
    lo2.append(lathe_at('fl_lower_bush_r', ring_profile(0.0068, 0.0105, 0.048), a2, (0, 1, 0), m['black'], segs=10))
    segs['Link_FL_Lower_2'] = (lo2, a2, b, False)

    # ---------------- upper A-arm (1.25" round tube legs) ----------------
    # [fix r6] front.png / front_3q: the upper arm is two slim, nearly level round tubes (~10-12 px each in front.png),
    # not a boxed plank: both legs are straight 1.25" (r 0.0159) tubes from the pivot sleeves to a small uniball boss.
    # The r6 shocks lean ~36 deg and pass through the arm's opening (coil axis at z 0.70 = (-0.32, 1.465) between the
    # legs at y 1.365 / 1.649; bypass axis (-0.477, 1.485), 6.3 cm in front of the rear leg's centre line), so the
    # front leg no longer sweeps forward round the coilover. The rear leg keeps a gentle 2 cm plan-view bow rearward
    # (peak at 0.72 of the leg) so the bypass body clears it by >= 1.3 cm over the whole +0.30 / -0.33 travel (the
    # analytic + mesh checks in notes/fix_r6_suspension.md); in front view it still reads straight.
    ub = UBJ
    af = UF_P
    ar = UR_P
    fpath = [af + (ub - af) * t for t in (0.030, 0.5, 0.965)]
    up0 = [sweep('fl_upper_front', fpath, F_UARM_R, m['arm'], sides=12, sharp=60)]
    up0.append(lathe_at('fl_upper_sleeve_f', ring_profile(0.0085, 0.0195, 0.041), af, (0, 1, 0), m['arm'], segs=14))
    up0.append(lathe_at('fl_upper_bush_f', ring_profile(0.0068, 0.0100, 0.045), af, (0, 1, 0), m['black'], segs=10))
    # [fix r6] smaller uniball boss (r 0.030 x 0.040 -> 0.024 x 0.032), nut and stud
    up0.append(lathe_at('fl_ubj_cup', [(0.0, -0.016), (0.021, -0.016), (0.024, -0.013), (0.024, 0.013),
                                       (0.021, 0.016), (0.0, 0.016)], ub, (0, 0, 1), m['arm'], segs=18))
    up0.append(hexnut('fl_ubj_nut', ub + V((0, 0, 0.022)), up, 0.0115, 0.012, m['alu']))
    up0.append(cyl('fl_ubj_stud', 0.0065, ub + V((0, 0, 0.027)), ub + V((0, 0, 0.037)), m['chrome'], segs=8))
    # small, thin gusset web between the legs right at the boss (was a broad plate that read as a shock mount)
    gu = (ub - af).normalized()
    gv = (ub - ar).normalized()
    gv = (gv - gu * gv.dot(gu)).normalized()
    org = ub + up * 0.0

    def to2u(q):
        q = q - ub
        return (q.dot(gu), q.dot(gv))
    q = [lerp(af, ub, 0.84), lerp(af, ub, 0.95), lerp(ar, ub, 0.95), lerp(ar, ub, 0.88)]
    up0.append(plate('fl_upper_gusset', round_poly([to2u(p) for p in q], 0.006, 2), org, gu, gv, 0.004, m['arm']))
    segs['Link_FL_Upper_0'] = (up0, af, ub, False)

    rpath = [lerp(ar, ub, t) + V((0.0, -F_UARM_BOW * math.exp(-((t - F_UARM_BOW_T) / 0.17) ** 2), 0.0))
             for t in (0.030, 0.20, 0.36, 0.50, 0.60, 0.68, 0.76, 0.84, 0.91, 0.965)]
    up2 = [sweep('fl_upper_rear', rpath, F_UARM_R, m['arm'], sides=12, sharp=60)]
    up2.append(lathe_at('fl_upper_sleeve_r', ring_profile(0.0085, 0.0195, 0.041), ar, (0, 1, 0), m['arm'], segs=14))
    up2.append(lathe_at('fl_upper_bush_r', ring_profile(0.0068, 0.0100, 0.045), ar, (0, 1, 0), m['black'], segs=10))
    segs['Link_FL_Upper_2'] = (up2, ar, ub, False)

    # ---------------- tie rod ----------------
    ta, tb = RACK, TRE
    td = (tb - ta).normalized()
    tr = rod_end('fl_tie_in', ta, (0, 0, 1), td, m, r_out=0.019, w=0.022, shank=0.040)
    tr += rod_end('fl_tie_out', tb, (0, 0, 1), -td, m, r_out=0.019, w=0.022, shank=0.040)
    # [fix r5] polished tube (front.png: the tie rods read 180-230, brighter than the arms)
    tr.append(cyl('fl_tie_tube', 0.0135, ta + td * 0.056, tb - td * 0.056, m['polished'], segs=14))
    for p in (ta + td * 0.056, tb - td * 0.056):
        tr.append(cyl('fl_tie_end', 0.0150, p - td * 0.006, p + td * 0.006, m['alu'], segs=6))
    segs['TieRod_FL'] = (tr, ta, tb, False)

    # ---------------- shocks ----------------
    # [fix r3] the coilover's springs end just under the upper A-arm (front.png); the body passes through the arm.
    # The hose fitting on its cap faces inboard (local -y) toward the finned reservoir's hose.
    # [fix r5] long gloss-black main + tender spring (14 mm wire, 6.5 + 3 turns) from the lower seat to 70 % of the
    # eye-to-eye length (front_3q: ~10 turns over ~60-70 %); it passes through the upper A-arm (the front leg sweeps
    # around it). The cap's hose fitting faces rear-inboard toward the finned reservoir's hose.
    co, Lc = coilover('fl_coil', F_COIL_BOT, F_COIL_TOP, m, front=True, spring_r=0.040, wire=0.007,
                      spring_top_frac=F_COIL_SPRING_FRAC, n_turns=(6.5, 3.0), coil_seg=12, spring_sides=7,
                      fit_ang=F_COIL_FIT_ANG, cap_gap=F_COIL_CAP_GAP, cap_h=F_COIL_CAP_H, cap_cone=True, fit=False,
                      cap_r=F_COIL_CAP_R)
    segs['Shock_FL'] = (co, F_COIL_TOP, F_COIL_BOT, True)
    # local x = bore (~world +Y), local y = outboard: the bypass stands behind / outboard of the coilover; its
    # tubes face inboard, into the open space between the upper arm's legs; no piggyback; cap 8 mm lower than the
    # rear ones (the game's uniform shock scaling pulls it toward the top clevis at full bump) (the finned can is the remote reservoir)
    # [fix r5] polished external bypass tubes (front.png / front_3q: three bright tubes beside the outer shock), facing
    # inboard (local -y) into the space between the upper arm's legs, with short adjuster knobs (rear-inboard tubes
    # put the knobs into the upper rear leg's sweep)
    by, Lb = bypass('fl_bypass', F_BYP_BOT, F_BYP_TOP, m, body_mat='anod', body_r=0.032, tube_side=F_BYP_TUBES,
                    res_side=None, cap_fit=True, cap_gap=F_BYP_CAP_GAP, cap_h=F_BYP_CAP_H, cap_cone=True,
                    tube_mat='polished', knob_out=1.30, fit_ang=math.pi, fit_z=F_BYP_FIT_Z, fit_rise=F_BYP_FIT_RISE,
                    zb_frac=F_BYP_ZB)
    segs['Shock_FL_2'] = (by, F_BYP_TOP, F_BYP_BOT, True)

    # ---------------- upright / spindle (Upright_FL) ----------------
    # [fix r3] the lower uniball is now at hub height: the upright runs from below it (the arm's cup tucks into a
    # pocket in the upright's lower inner face) up to the upper uniball, leaning in ~10 deg
    upr = []
    z0, z1 = LBJ.z - 0.075, UBJ.z - 0.036
    secs = []
    zs = [z0, z0 + 0.03, F_WC.z + 0.0, F_WC.z + 0.06, F_WC.z + 0.13, z1 - 0.04, z1]
    wy = [0.050, 0.086, 0.122, 0.112, 0.080, 0.058, 0.050]
    dxs = [0.044, 0.050, 0.054, 0.050, 0.046, 0.042, 0.040]

    def upr_x(z):
        return (LBJ.x - 0.035) + ((UBJ.x - 0.012) - (LBJ.x - 0.035)) * (z - LBJ.z) / (UBJ.z - LBJ.z)
    for z, wv, dv in zip(zs, wy, dxs):
        xc = upr_x(z)
        prof = rrect(dv, wv, 0.010, 2)
        secs.append([V((xc + u, F_WC.y + v, z)) for (u, v) in prof])
    upr.append(sharpen(loft('fl_upright', secs, m['arm']), 32))
    # boots between the arm cups and the upright
    upr.append(lathe_at('fl_lbj_boot', [(0.0, 0.0), (0.024, 0.0), (0.020, 0.006), (0.024, 0.010), (0.018, 0.016),
                                        (0.0, 0.016)], LBJ + V((0, 0, 0.024)), up, m['rubber'], segs=16))
    upr.append(hexnut('fl_lbj_nut', LBJ + V((0, 0, -0.032)), up, 0.014, 0.014, m['alu']))
    upr.append(cyl('fl_lbj_stud', 0.0075, LBJ + V((0, 0, -0.040)), LBJ + V((0, 0, -0.050)), m['chrome'], segs=10))
    upr.append(lathe_at('fl_ubj_boot', [(0.0, 0.0), (0.022, 0.0), (0.018, 0.006), (0.022, 0.010), (0.016, 0.017),
                                        (0.0, 0.017)], UBJ + V((0, 0, -0.037)), up, m['rubber'], segs=16))
    # spindle bearing housing out to the hub
    hub_c = V((upr_x(F_WC.z) - 0.020, F_WC.y, F_WC.z))
    sp_len = max(0.04, (hub_c.x - F_ROTOR_X) + 0.030)
    upr.append(lathe_at('fl_spindle', [(0.0, 0.0), (0.052, 0.0), (0.052, 0.012), (0.046, 0.018), (0.046, sp_len - 0.007),
                                       (0.040, sp_len), (0.0, sp_len)],
                        hub_c, (-1, 0, 0), m['arm'], segs=20))
    # [fix r3] steering arm: FORWARD from the upright's front face to the tie-rod end (front steer), double-shear
    # clevis plates + vertical bolt
    xs = upr_x(TRE.z)
    sa_path = [V((xs, F_WC.y + 0.020, TRE.z)), V((xs + (TRE.x - xs) * 0.5, F_WC.y + 0.070, TRE.z)),
               V((TRE.x, TRE.y - 0.030, TRE.z))]
    upr.append(beam('fl_steer_arm', sa_path, [rrect(0.030, 0.050, 0.007, 2)] * 3, m['arm'], up=(0, 0, 1)))
    for s in (-1, 1):
        pz = TRE.z + s * 0.0185
        shp = round_poly([(-0.034, -0.017), (0.012, -0.017), (0.020, 0.0), (0.012, 0.017), (-0.034, 0.017)],
                         [0, 0.004, 0.010, 0.004, 0], 2)
        upr.append(plate('fl_steer_clevis', shp, V((TRE.x, TRE.y, pz)), (0, 1, 0), (1, 0, 0), 0.006, m['arm']))
    upr += bolt('fl_steer_bolt', TRE, (0, 0, 1), 0.050, m)
    # caliper bracket + orange caliper on the front of the rotor, just below the steering arm
    cal_ang = math.radians(8)
    upr += caliper('fl_caliper', F_WC, F_ROTOR_X, cal_ang, m, arc=0.125, r0=0.104, r1=0.158, width=0.056)
    xb = upr_x(F_WC.z) - 0.027                     # upright outer face
    cb = V(((xb + F_ROTOR_X + 0.028) / 2, F_WC.y + 0.090, F_WC.z + 0.010))
    upr.append(box_obj('fl_cal_bracket', (max(0.008, abs(F_ROTOR_X + 0.028 - xb)) + 0.006, 0.070, 0.050), cb,
                       m['arm']))
    # brake hose: caliper inlet up the front of the upright to a tab on its outer face (front.png)
    ca = F_WC.z + 0.158 * math.sin(cal_ang + 0.30)
    bh = [V((F_ROTOR_X + 0.022, F_WC.y + 0.158 * math.cos(cal_ang + 0.30), ca)),
          V((F_ROTOR_X + 0.030, F_WC.y + 0.140, ca + 0.045)),
          V((upr_x(F_WC.z + 0.16) - 0.050, F_WC.y + 0.095, F_WC.z + 0.16)),
          V((upr_x(F_WC.z + 0.19) - 0.024, F_WC.y + 0.040, F_WC.z + 0.19))]
    upr.append(sweep('fl_brake_hose', smooth_path(bh, 3), 0.0048, m['hose'], sides=6))
    upr.append(cyl('fl_brake_tab', 0.008, bh[-1], bh[-1] + V((0.012, -0.004, 0)), m['alu'], segs=6))
    segs['Upright_FL'] = (upr, None, None, False)

    # ---------------- spinning rotor + hub (Wheel_FL) ----------------
    segs['Wheel_FL'] = (rotor_assembly('fl', F_WC, F_ROTOR_X, F_HUB_X, m), None, None, False)
    return segs


# ------------------------------------------------------------------ REAR corner (left)

def rear_corner(m):
    segs = {}
    up = V((0, 0, 1))

    # ---------------- trailing arm (Link_RL_Lower_0) ----------------
    # [fix r2] shallow box (side photo / rear_wheel_sidepod_right.png): ~0.08 m deep at the pivot, growing toward
    # the hub; its underside stays at ~0.46 forward of the rear tyre (y -1.05) and above 0.44 at y -1.2.
    # [fix r3] straight from spec.R_TRAILING_PIVOT to the carrier: centre line |x| <= 0.735 alongside the tyre. The shock eyes sit on the a-b line inside pockets
    # in the box (cross bolts along X through the side walls).
    a, b = TP, R_CARRIER
    D = b - a
    end_t = (R_CARRIER.y + 0.068 - a.y) / D.y     # arm body ends at the carrier front face
    y_end = a.y + D.y * end_t

    def zmin(y):
        if y >= -1.05:
            return 0.462
        if y >= -1.20:
            return 0.462 + (0.440 - 0.462) * (-1.05 - y) / 0.15
        u = min(1.0, (-1.20 - y) / max(1e-3, (-1.20 - y_end)))
        return 0.440 + (R_CARRIER.z - 0.080 - 0.440) * u * u * (3 - 2 * u)

    L_arm = D.length
    # [fix r3] the pivot (spec y -0.84) is behind the main hoop now, so the arm is one straight box: the r2
    # dog-leg around the hoop leg (only for a pivot ahead of the hoop) is gone

    path, outl = [], []
    N = 22
    tops, bots = [], []
    for i in range(N):
        t = 0.03 + (end_t - 0.03) * i / (N - 1)
        p0 = a + D * t
        dist = L_arm * t
        k = min(1.0, max(0.0, (dist - 0.07) / 0.16))
        k = k * k * (3 - 2 * k)
        top = p0.z + 0.038 + (0.055 - 0.038) * k
        bot = p0.z - 0.038 + (min(zmin(p0.y), top - 0.068) - (p0.z - 0.038)) * k
        bot = min(bot, top - 0.068)
        h = top - bot
        w = 0.052 + 0.010 * min(1.0, t / 0.6)
        path.append(V((p0.x, p0.y, (top + bot) / 2)))
        outl.append(hexbox(w, h, ch=0.20, r=0.004))
        tops.append(top); bots.append(bot)
    ta = [beam('rl_trailing', path, outl, m['arm'])]
    # cross-bolt pivot sleeve (bolt along X, chassis clevis gap 0.062; the chassis clevis carries the bolt)
    # [fix r4] sleeve r 0.032 -> 0.027: at the r4 pivot (y -0.85) the main-hoop leg / frame corner node is only ~3.2 cm
    # ahead of the bolt, and the game stretches this member along a->b by up to 1.16 at droop (sleeve -> 0.031 fore-aft)
    ta.append(lathe_at('rl_trail_sleeve', ring_profile(0.010, 0.027, 0.058), a, (1, 0, 0), m['arm'], segs=16))
    ta.append(lathe_at('rl_trail_bush', ring_profile(0.0068, 0.0125, 0.062), a, (1, 0, 0), m['black'], segs=12))
    dd = D.normalized()
    # weld-on side doublers behind the sleeve (low plates, inside the box depth)
    for s_ in (-1, 1):
        g = round_poly([(0.0, -0.026), (0.12, -0.024), (0.12, 0.020), (0.0, 0.026)], [0.01, 0.0, 0.0, 0.01], 2)
        wv = 0.052 / 2 + 0.002
        # [fix r3] start behind the chassis pivot box's side plates (they reach 0.05 behind the bolt)
        ta.append(plate('rl_pivot_gusset', g, a + dd * 0.058 + V((s_ * wv, 0, 0.0)), dd, up, 0.004, m['arm']))
    # rear flange plate onto the carrier front face
    pf = a + D * end_t
    hz = R_CARRIER.z
    ta.append(plate('rl_trail_flange', rrect(0.070, 0.165, 0.012, 2), V((R_CARRIER.x + 0.004, pf.y - 0.004, hz - 0.012)),
                    (1, 0, 0), up, 0.010, m['arm']))
    for dz in (-0.055, 0.035):
        for dx in (-0.022, 0.022):
            ta.append(hexnut('rl_flange_bolt', V((R_CARRIER.x + dx, pf.y + 0.004, hz + dz)), (0, 1, 0), 0.0085, 0.007,
                             m['alu']))
    # shock pockets: dark slot in the top skin + cross bolt (along X) through both side walls
    pk_top = []
    for p_m in (R_COIL_BOT, R_BYP_BOT):
        t_m = (p_m - a).dot(D) / D.length_squared
        i_m = min(range(N), key=lambda i: abs((0.03 + (end_t - 0.03) * i / (N - 1)) - t_m))
        ztop = tops[i_m]
        pk_top.append(ztop - p_m.z)
        slot = plate('rl_pocket', rrect(0.040, 0.082, 0.016, 3), V((p_m.x, p_m.y, ztop + 0.0012)), (1, 0, 0), dd,
                     0.003, m['black'])
        ta.append(slot)
        w_m = 0.052 + 0.010 * min(1.0, t_m / 0.6)
        ta += bolt('rl_shock_bolt', p_m, (1, 0, 0), w_m + 0.004, m)
        for s_ in (-1, 1):       # round boss washers welded on the side walls
            ta.append(cyl('rl_pocket_boss', 0.016, p_m + V((s_ * w_m / 2, 0, 0)), p_m + V((s_ * (w_m / 2 + 0.003), 0, 0)),
                          m['arm'], segs=10))
    segs['Link_RL_Lower_0'] = (ta, a, b, False)

    # ---------------- radius rods ----------------
    for key, ra, rb in (('Link_RL_Lower_2', RRL_A, RRL_B), ('Link_RL_Upper_0', RRU_A, RRU_B)):
        dd = (rb - ra).normalized()
        nm = 'rl_rr_' + key[-7:].lower()
        o = rod_end(nm + '_in', ra, (0, 1, 0), dd, m, r_out=0.022, w=0.028, shank=0.042, housing='alu')
        o += rod_end(nm + '_out', rb, (1, 0, 0), -dd, m, r_out=0.022, w=0.028, shank=0.042, housing='alu')
        o.append(cyl(nm + '_tube', 0.0159, ra + dd * 0.06, rb - dd * 0.06, m['arm'], segs=16))
        for p in (ra + dd * 0.06, rb - dd * 0.06):
            o.append(cyl(nm + '_bung', 0.0172, p - dd * 0.007, p + dd * 0.007, m['arm'], segs=6))
        segs[key] = (o, ra, rb, False)

    # ---------------- shocks ----------------
    # lower eyes clocked to the pocket cross bolts (X); upper eyes keep the chassis clevis bolt axis (Y)
    co, _ = coilover('rl_coil', R_COIL_BOT, R_COIL_TOP, m, body_r=0.034, spring_r=0.040, wire=0.0072, front=False,
                     cap_gap=R_COIL_CAP_GAP, cap_h=R_COIL_CAP_H,
                     seat_z=max(0.082, pk_top[0] + 0.040), bot_bore=(1, 0, 0), coil_seg=10, fit_ang=R_FIT_ANG,
                     spring_top_z=1.15, n_turns=(5.5, 3.0), boss_z0=pk_top[0] + 0.006, fin_cap=R_FIN_CAP)
    segs['Shock_RL'] = (co, R_COIL_TOP, R_COIL_BOT, True)
    # [fix r5] no piggyback any more (at full bump it swung rearward into the body's deck front wall at y -1.30): the
    # bypass's remote reservoir is the black can in the pod bay just behind it (statics r_res), on a short hose from a
    # rear-inboard cap fitting; short adjuster knobs (more room for that can)
    by, _ = bypass('rl_bypass', R_BYP_BOT, R_BYP_TOP, m, body_mat='anod', body_r=0.035, tube_side=(0.0, -1.0),
                   res_side=None, bot_bore=(1, 0, 0), cap_fit=True, cap_gap=R_BYP_CAP_GAP, cap_h=R_BYP_CAP_H,
                   low0=min(0.060, pk_top[1] + 0.016),     # bump cap clears the arm's top skin as it swings
                   knob_out=1.30, fit_ang=R_BYP_FIT_ANG, fin_cap=R_FIN_CAP)
    segs['Shock_RL_2'] = (by, R_BYP_TOP, R_BYP_BOT, True)

    # ---------------- half shaft ----------------
    # [fix r4] the inner CV housing + flange are bolted to the diff output: STATIC (they used to swing ~34 deg with the
    # shaft into powertrain's output flange at bump / droop). Only the shaft, both boots and the outer CV move; the
    # inner boot's big end sits inside the housing's recessed mouth, within 0.056 of the joint centre (= the segment's
    # pivot a), so it stays inside the housing's outline at any angle.
    ha, hb = HS_A, HS_B
    hd = (hb - ha)
    Lh = hd.length
    hs, hs_static = [], []
    cv = [(0.0, -0.040), (0.050, -0.040), (0.056, -0.034), (0.056, 0.022), (0.050, 0.028), (0.046, 0.028),
          (0.046, 0.016), (0.0, 0.016)]
    hs_static.append(lathe_at('rl_cv_in', cv, ha, hd, m['steel'], segs=20))
    hs_static.append(lathe_at('rl_cv_in_fl', ring_profile(0.03, 0.060, 0.010), ha - hd.normalized() * 0.036, hd,
                              m['alu'], segs=20))
    hs.append(lathe_at('rl_cv_out', [(0.0, -0.036), (0.030, -0.042), (0.050, -0.036), (0.054, -0.028),
                                     (0.054, 0.034), (0.046, 0.040), (0.0, 0.040)],
                       hb, hd, m['steel'], segs=20))

    def boot(n1, r0=0.046):
        prof = [(0.0, 0.0), (r0, 0.0)]
        ribs = 4                                 # [fix r5] 5 -> 4 convolutions (triangle budget)
        for k in range(ribs):
            z = 0.008 + (n1 - 0.02) * (k + 0.5) / ribs
            rr = r0 - (r0 - 0.022) * (k + 0.5) / ribs
            prof += [(rr, z - 0.004), (rr - 0.007, z + 0.004)]
        prof += [(0.019, n1 - 0.008), (0.019, n1), (0.0, n1)]
        return prof
    hs.append(lathe_at('rl_boot_in', boot(0.118, 0.039), ha + hd.normalized() * 0.012, hd, m['rubber'], segs=16,
                       sharp=60))
    hs.append(lathe_at('rl_boot_out', boot(0.090), hb - hd.normalized() * 0.034, -hd, m['rubber'], segs=16,
                       sharp=60))
    hs.append(cyl('rl_shaft', 0.0165, ha + hd.normalized() * 0.12, hb - hd.normalized() * 0.11, m['steel'], segs=14))
    segs['static'] = (hs_static, None, None, False)
    segs['Halfshaft_RL'] = (hs, ha, hb, False)

    # ---------------- hub carrier + caliper (Upright_RL) ----------------
    upr = []
    cx = R_CX                                    # [fix r3] wholly inboard of the tyre's inner face
    CW = 0.066                                   # carrier thickness across the car
    secs = []
    zs = [0.255, 0.30, 0.37, 0.455, 0.54, 0.60, 0.645]   # [fix r3] top 0.645: >= 3 cm under the arch lip at bump
    wy = [0.058, 0.084, 0.146, 0.156, 0.146, 0.084, 0.058]
    for z, wv in zip(zs, wy):
        prof = rrect(CW, wv, 0.009, 2)
        secs.append([V((cx + u, R_WC.y + v, z)) for (u, v) in prof])
    upr.append(sharpen(loft('rl_carrier', secs, m['orange']), 32))
    # bearing snout out to the rotor
    upr.append(lathe_at('rl_bearing', [(0.0, 0.0), (0.064, 0.0), (0.064, 0.012), (0.056, 0.020), (0.054, 0.046),
                                       (0.0, 0.046)],
                        V((cx - CW / 2 + 0.002, R_WC.y, R_WC.z)), (-1, 0, 0), m['orange'], segs=24))
    # machined pockets (dark) + silver bolts on the visible rear / front faces
    for yy, sg in ((R_WC.y - 0.078, -1), (R_WC.y + 0.078, 1)):
        for dz in (-0.075, 0.075):
            upr.append(hexnut('rl_carrier_bolt', V((cx, yy + sg * 0.004, R_WC.z + dz)), (0, 1, 0), 0.0085, 0.008,
                              m['alu']))
    for dz in (-0.16, 0.16):
        upr.append(box_obj('rl_carrier_pocket', (0.004, 0.034, 0.05), V((cx + CW / 2 + 0.0005, R_WC.y, R_WC.z + dz)),
                           m['black']))
    # radius-rod clevis plates (bolts along X) at the carrier's front corners
    for rb in (RRL_B, RRU_B):
        for s in (-1, 1):
            shp = round_poly([(-0.045, -0.018), (0.008, -0.018), (0.020, 0.0), (0.008, 0.018), (-0.045, 0.018)],
                             [0, 0.004, 0.012, 0.004, 0], 2)
            upr.append(plate('rl_rr_clevis', shp, V((rb.x + s * 0.0185, rb.y, rb.z)), (0, 1, 0), (0, 0, 1), 0.006,
                             m['arm']))
        upr += bolt('rl_rr_bolt', rb, (1, 0, 0), 0.052, m)
    # orange caliper at the rear of the rotor (rear.png) + bracket
    upr += caliper('rl_caliper', R_WC, R_ROTOR_X, math.radians(180), m, arc=0.20, r0=0.096, r1=0.162, width=0.066)
    upr.append(plate('rl_cal_bracket', round_poly([(-0.035, -0.07), (0.035, -0.07), (0.035, 0.07), (-0.035, 0.07)],
                                                   0.01, 2),
                     V((cx - CW / 2 - 0.006, R_WC.y - 0.105, R_WC.z)), (0, 1, 0), (0, 0, 1), 0.012, m['orange']))
    # [integration] rerouted inside the rim barrel (r < 0.17) until clear of the rim lip (x > -0.885): the old
    # path went through the rim lip and the paddle tyre's inner sidewall
    bh = [V((R_ROTOR_X + 0.022, R_WC.y - 0.118, R_WC.z + 0.118)), V((R_ROTOR_X + 0.045, R_WC.y - 0.112, R_WC.z + 0.112)),
          V((cx - 0.027, R_WC.y - 0.085, R_WC.z + 0.175)), V((cx - CW / 2 - 0.002, R_WC.y - 0.03, R_WC.z + 0.20))]
    upr.append(sweep('rl_brake_hose', smooth_path(bh, 3), 0.0048, m['hose'], sides=6))
    segs['Upright_RL'] = (upr, None, None, False)

    segs['Wheel_RL'] = (rotor_assembly('rl', R_WC, R_ROTOR_X, R_HUB_X, m), None, None, False)
    return segs


# ------------------------------------------------------------------ static parts

# [fix r3] finned remote reservoirs moved under the hood: front.png + front_3q triangulate the cans to bottom
# (0.48, 1.38, 0.77) / top (0.36, 1.41, 0.95). At y 1.38 the upper A-arm's rear leg sweeps through them at bump, so
# they stand 8 cm further back (y 1.305, just ahead of the bulkhead hoop, behind the arms' whole travel), at the
# photo's |x| and height, leaning in ~24 deg; well inside spec.FRONT_CLIP_HALF_W and 8 cm under the skin.
# [fix r5] the r5 wing fenders end ahead of the cowl (front edge runs (-0.44, 1.18) -> (-0.34, 1.345), lip underside
# 0.89-0.92): the can now stands in the OPEN trough just ahead of / outboard of that edge, 0.28 m long (fins ~0.22,
# photo ~0.21 + caps), leaning in 26 deg in line with the outer (bypass) shock as both photos show. It stays behind the
# upper A-arm's rear leg (y <= ~1.37 at full bump; the photo's y ~1.38 is inside that leg's sweep) and outboard of the
# chassis' upper front rail (x -0.32, z 0.82-0.86 at y 1.30-1.35). Its top cap stays >= 2 cm under the wing lip where
# its rear-inboard edge passes under it. (The photo can top is ~0.95: the model's wing lip is ~4.5 cm lower than the
# photos' at |x| 0.36-0.40.)
# [fix r6] the photo can's centre line (front.png FR (473,503)->(543,387) - the arbiter's (455,510)->(520,390) is its
# outboard EDGE; front_3q (795,505)->(838,426)) leans ~31 deg top-inboard in front view, 28.6 deg in front_3q, 7-8 cm
# across (photo width 38-41 px; the r5 can was 9.2 cm). Triangulated it runs (-0.466, 1.402, 0.772) -> (-0.347, 1.474,
# 0.958): INSIDE the upper rear leg's bump sweep (the leg rises from z 0.70 to 0.89 at |x| 0.50 / 0.84 at 0.40) - a
# static can there is hit from +0.10 bump on, and one riding on the bypass is hit too (its lower end rises only ~1/3 as
# fast as the leg). So the can keeps the photo's front-view centre line (both ends back-projected from front.png) at
# y 1.30 -> 1.35, right BEHIND the leg's swept volume (>= 1.2 cm at +0.30; front_3q lean 34 deg, ends ~20 px off). Its
# top is the photo's except that it ends 6 cm lower along the axis, just under the wing's rolled front lip (which, at
# |x| 0.36-0.38, y 1.32-1.34, droops to z 0.88 right where the photo can's top is; the model's wing sits ~4.5 cm lower
# than the photos' there) - in front view the top still meets the wing edge. Hose: a banjo on the FRONT of the top cap
# (an axial one would point into the lip), forward over the leg's sweep, down at y F_HOSE_Y into a level banjo on the
# bypass cap's rear rim.
F_RES_BOT = (-0.4843, 1.2974, 0.7521)     # lower end (black cap + fitting)
F_RES_TOP = (-0.3970, 1.3338, 0.8897)     # upper end (top cap; hose banjo on its front side)
F_RES_R = (0.0325, 0.038)                 # fin root / tip radius (7.6 cm across the fins); caps r 0.0395
F_RES_RIBS = 32                           # [fix r6] 32 bolder fins (48 averaged to a plain grey at render resolution)
F_HOSE_Y = 1.437                          # [fix r6] y of the hose's vertical run down to the bypass banjo
F_RES_CAP = 0.022                         # [fix r6] end cap length (thin black caps, photo)
F_RES_FIT_DIR = (-1.0, 0.0, 0.6)          # [fix r6] top banjo points outboard-up, away from the wing lip and the leg
F_HOSE_Z = 0.945                          # [fix r6] hose crest height (over the leg's bump sweep, outboard of the wing)


def fin_profile(ribs, r_root, r_tip):
    """Star cross-section of a finned can: (points, dark flags). [fix r3] the valley between two fins and the inner
    half of each fin flank use the near-black 'fin root' material (fake ambient occlusion that survives glTF)."""
    pts, dark = [], []
    dA = 2 * math.pi / ribs
    r_mid = r_root + (r_tip - r_root) * 0.45
    prof = ((-0.42, r_root, 1), (-0.30, r_mid, 0), (-0.17, r_tip, 0), (0.17, r_tip, 0), (0.30, r_mid, 1),
            (0.42, r_root, 1))                  # flag = face from this point to the next is dark
    for k in range(ribs):
        c = dA * k
        for da, r, dk in prof:
            pts.append((r * math.cos(c + da * dA), r * math.sin(c + da * dA)))
            dark.append(dk)
    return pts, dark


def fin_band(name, z0, z1, r_root, r_tip, ribs, m, ends=True, lite=False):
    """[fix r6] Longitudinal fins (star section extruded along local Z from z0 to z1), satin aluminium tips and dark
    roots, closed by flat star end faces. Built in local coordinates (the caller places it).
    lite: 4-point fins (flank, tip, flank, dark valley) whose ends close only each fin (the valley sits on the body
    the band is wrapped around): 12 triangles per fin instead of ~24."""
    if lite:
        dA = 2 * math.pi / ribs
        pts, dark = [], []
        for k in range(ribs):
            c = dA * k
            for da, r, dk in ((-0.36, r_root, 0), (-0.16, r_tip, 0), (0.16, r_tip, 0), (0.36, r_root, 1)):
                pts.append((r * math.cos(c + da * dA), r * math.sin(c + da * dA)))
                dark.append(dk)
    else:
        pts, dark = fin_profile(ribs, r_root, r_tip)
    bm = bmesh.new()
    rings = [[bm.verts.new((x, y, z)) for (x, y) in pts] for z in (z0, z1)]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((rings[0][i], rings[0][j], rings[1][j], rings[1][i]))
        f.material_index = dark[i]
    if ends and lite:
        for k in range(ribs):
            q = [4 * k + i for i in range(4)]
            f = bm.faces.new([rings[0][i] for i in reversed(q)]); f.material_index = 0
            f = bm.faces.new([rings[1][i] for i in q]); f.material_index = 0
    elif ends:
        f = bm.faces.new(list(reversed(rings[0]))); f.material_index = 1
        f = bm.faces.new(rings[1]); f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm_obj(name, bm, [m['fin_alu'], m['fin_root']], sharp=28)


def finned_can(name, p0, p1, m, r_root=0.040, r_tip=0.046, ribs=36, cap_len=0.034, fit_top=False, lo_fit=False,
               cap_r=None, top_fit_dir=None):
    """Satin aluminium can with longitudinal fins (star cross-section extruded along the axis) and black
    anodized end caps. Built along local Z then placed from p0 (bottom) to p1 (top). [fix r3] the valley between
    two fins and the inner half of each fin flank use the near-black 'fin root' material, so the fins read as
    deep ribs (fake ambient occlusion that survives glTF) instead of white stripes."""
    p0, p1 = V(p0), V(p1)
    L = (p1 - p0).length
    fins = fin_band(name, cap_len - 0.004, L - cap_len + 0.004, r_root, r_tip, ribs, m, ends=False)
    out = [fins]
    # end caps (black anodized): bottom with the hose boss, top with a shallow dome + small bleed screw
    cr = 0.0465 if cap_r is None else cap_r     # [fix r6] cap radius follows the (slimmer) fins
    cap_lo = [(0.0, 0.0), (cr - 0.0165, 0.0), (cr - 0.0065, 0.006), (cr, 0.012), (cr, cap_len - 0.004),
              (cr - 0.005, cap_len), (0.0, cap_len)]
    out.append(lathe_at(name + '_cap_lo', cap_lo, (0, 0, 0), (0, 0, 1), m['anod'], segs=20, sharp=40))
    cap_hi = [(0.0, L), (cr - 0.0205, L), (cr - 0.0085, L - 0.005), (cr, L - 0.012), (cr, L - cap_len + 0.004),
              (cr - 0.005, L - cap_len), (0.0, L - cap_len)]
    out.append(lathe_at(name + '_cap_hi', cap_hi, (0, 0, 0), (0, 0, 1), m['anod'], segs=20, sharp=40))
    if fit_top:                                   # [fix r3] hose fitting on the top cap, bleed screw below
        if top_fit_dir is None:
            out.append(cyl(name + '_boss', 0.011, (0, 0, L - 0.002), (0, 0, L + 0.014), m['alu'], segs=10))
            out.append(hexnut(name + '_fitnut', (0, 0, L + 0.008), (0, 0, 1), 0.0135, 0.008, m['anod']))
        else:                                     # [fix r6] small cap on top, radial banjo added below (world space)
            out.append(cyl(name + '_boss', 0.008, (0, 0, L - 0.002), (0, 0, L + 0.006), m['alu'], segs=10))
        if lo_fit:                                # [fix r5] black bottom boss + fitting (both photos)
            out.append(cyl(name + '_loboss', 0.013, (0, 0, 0.002), (0, 0, -0.016), m['anod'], segs=12))
            out.append(hexnut(name + '_lofit', (0, 0, -0.012), (0, 0, 1), 0.0125, 0.008, m['anod']))
            out.append(cyl(name + '_bleed', 0.0045, (0.024, 0, 0.001), (0.024, 0, -0.006), m['alu'], segs=6))
        else:
            out.append(cyl(name + '_bleed', 0.006, (0.012, 0, 0.001), (0.012, 0, -0.006), m['alu'], segs=6))
    else:
        out.append(cyl(name + '_boss', 0.011, (0, 0, 0.002), (0, 0, -0.022), m['alu'], segs=10))
        out.append(hexnut(name + '_fitnut', (0, 0, -0.016), (0, 0, 1), 0.0135, 0.010, m['anod']))
        out.append(cyl(name + '_bleed', 0.006, (0.012, 0, L - 0.001), (0.012, 0, L + 0.006), m['alu'], segs=6))
    Mx = mat_from(p0, *frame(p1 - p0, (1, 0, 0)))
    out = to_world(out, Mx)
    if fit_top and top_fit_dir is not None:       # [fix r6] radial banjo on the top cap, square to the axis
        ax = (p1 - p0).normalized()
        fd = V(top_fit_dir)
        fd = (fd - ax * fd.dot(ax)).normalized()
        c = p1 - ax * (cap_len * 0.5)
        cr = 0.0465 if cap_r is None else cap_r
        out.append(cyl(name + '_tfit', 0.0085, c + fd * (cr - 0.003), c + fd * (cr + 0.014), m['alu'], segs=10))
        out.append(hexnut(name + '_tfitnut', c + fd * (cr + 0.009), fd, 0.0115, 0.007, m['anod']))
    return out


def can_top_fit(p0, p1, cap_len, cap_r, top_fit_dir):
    """[fix r6] world position + direction of finned_can's radial top banjo tip (for the hose)."""
    p0, p1 = V(p0), V(p1)
    ax = (p1 - p0).normalized()
    fd = V(top_fit_dir)
    fd = (fd - ax * fd.dot(ax)).normalized()
    return p1 - ax * (cap_len * 0.5) + fd * (cap_r + 0.014), fd


def _xbrace_arm(C=None):
    """Upper-left X-brace arm (outboard top end, inboard-rear lower end) from the built chassis tube 'x_brace_a' when
    it is in the build, else straight from spec: X_BRACE_TOP -> the mirrored X_BRACE_BOT (each arm runs from one side's
    top to the other side's bottom). [fix r5] the old B-pillar / main-hoop fallback (z 1.385 / 1.00, x 0.665) is gone."""
    if C is not None:
        for o in C.groups.get('static', []):
            if o.type == 'MESH' and o.name.startswith('x_brace_a'):
                mw = world_matrix(o)
                vs = [mw @ v.co for v in o.data.vertices]
                if len(vs) > 20:
                    lo = min(v.x for v in vs); hi = max(v.x for v in vs)
                    e0 = [v for v in vs if v.x < lo + 0.03]; e1 = [v for v in vs if v.x > hi - 0.03]
                    p0 = sum(e0, V()) / len(e0); p1 = sum(e1, V()) / len(e1)
                    if p0.z > p1.z:
                        return p0, p1
    top, bot = V(spec.X_BRACE_TOP), V(spec.X_BRACE_BOT)
    return top, V((-bot.x, bot.y, bot.z))


_XB = {'C': None}
R_RES_XY = (-0.476, -1.284)              # [fix r5] rear (bypass) remote can, pod bay (see statics)
R_RES_LEN = 0.19
XB_TUBE_R = 0.0191                       # 1.5" X-brace tube
XB_RES_Y = -0.875                        # can centre station (task box: y -0.80..-0.95, |x| 0.30-0.45)
XB_RES_TILT = math.radians(32.0)         # clamp direction: 32 deg forward of straight down, square to the arm


def xbrace_reservoir(m, r=0.029, length=0.135, cap_l=0.034):
    """[fix r5] Remote reservoir for the rear COILOVER, clamped UNDER / just forward of the X-brace's upper arm (seen
    behind the seats, under the X tube from the rear, never above it): axis parallel to the arm, can top >= 1 cm
    below the tube's top surface, >= 5 cm over the interior firewall's top shelf (z 1.232). Knurled black caps, orange
    collar at the inboard end, two clamps + saddles to the tube; a banjo under the outboard cap feeds a hose that drops
    behind the firewall shelf and runs back, inboard of the gusset fin and under the coilover's top clevis, into the
    coilover cap fitting (forward-inboard, R_FIT_ANG)."""
    top, bot = _xbrace_arm(_XB['C'])
    d = (bot - top).normalized()                      # down-inboard-rear along the arm
    fwd = V((-d.y, d.x, 0.0)).normalized()            # horizontal, square to the arm, pointing forward (+y)
    dn = V((0.0, 0.0, -1.0))
    dn = (dn - d * dn.dot(d)).normalized()
    fwd = (fwd - d * fwd.dot(d)).normalized()
    off = (dn * math.cos(XB_RES_TILT) + fwd * math.sin(XB_RES_TILT)).normalized()
    dist = XB_TUBE_R + r + 0.0055
    # station along the arm that puts the can centre at XB_RES_Y
    t = ((XB_RES_Y - off.y * dist) - top.y) / (bot.y - top.y)
    c = top + (bot - top) * t + off * dist
    tot = length + 2 * cap_l
    p_out, p_in = c - d * (length / 2), c + d * (length / 2)
    out = []
    body = [(0.0, 0.0), (r - 0.002, 0.0), (r, 0.002), (r, length - 0.002), (r - 0.002, length), (0.0, length)]
    out.append(lathe_at('xb_res', body, p_out, d, m['anod'], segs=18))
    # knurled end caps (grooved): the outboard one carries the hose banjo
    k = cap_l / 0.046
    for sgn in (-1, 1):
        prof = [(0.0, 0.0), (r + 0.0025, 0.0), (r + 0.0025, 0.012 * k), (r - 0.0005, 0.015 * k),
                (r + 0.0025, 0.018 * k), (r + 0.0025, 0.030 * k), (r - 0.0005, 0.033 * k), (r + 0.0025, 0.036 * k),
                (r + 0.0025, 0.040 * k), (r - 0.006, cap_l), (0.0, cap_l)]
        out.append(lathe_at('xb_res_cap', prof, p_out if sgn < 0 else p_in, -d if sgn < 0 else d, m['anod'],
                            segs=12, sharp=25))
    # orange anodized collar at the inboard end
    out.append(lathe_at('xb_res_collar', [(r - 0.001, 0.0), (r + 0.0035, 0.0), (r + 0.0035, 0.013),
                                          (r - 0.001, 0.013), (r - 0.001, 0.0)],
                        p_in - d * 0.017, d, m['orange'], segs=18))
    # two clamps: band around the can + saddle up to the tube
    for f in (0.22, 0.78):
        q = p_out + d * (length * f)
        out.append(lathe_at('xb_res_clamp', [(r - 0.001, -0.008), (r + 0.003, -0.008), (r + 0.003, 0.008),
                                             (r - 0.001, 0.008), (r - 0.001, -0.008)], q, d, m['alu'], segs=14))
        gap = dist - r - XB_TUBE_R                  # 5.5 mm between the can and the tube
        out.append(box_obj('xb_res_saddle', (0.016, 0.014, gap + 0.003), V((0, 0, 0)), m['alu']))
        out[-1].matrix_basis = mat_from(q - off * (r + gap * 0.5), *frame(-off, d))
    # banjo under the outboard cap (pointing straight away from the tube) -> hose to the coilover cap fitting
    bq = p_out - d * (cap_l * 0.55)
    b0, b1 = bq + off * (r + 0.001), bq + off * (r + 0.016)
    out.append(cyl('xb_res_fit', 0.0075, b0, b1, m['alu'], segs=8))
    Mr, Lrc = shock_frame(R_COIL_BOT, R_COIL_TOP)
    fa = V((math.cos(R_FIT_ANG), math.sin(R_FIT_ANG), 0.0))
    end = Mr @ (fa * (0.034 + 0.016) + V((0, 0, Lrc - R_COIL_CAP_GAP + 0.014)))
    edir = (Mr.to_3x3() @ fa).normalized()
    hz = 1.283                                        # level run: >= 4 cm over the firewall shelf, under the fin
    hose = [b1, b1 + off * 0.012, V((b1.x - 0.018, b1.y - 0.030, max(hz + 0.006, b1.z - 0.030))),
            V((-0.488, -0.935, hz)), V((end.x + edir.x * 0.045, end.y + edir.y * 0.045, hz)),
            end + edir * 0.014, end]
    out.append(sweep('xb_res_hose', smooth_path(hose, 3), 0.0075, m['hose'], sides=8))
    return out


def statics(m):
    """Left-side static parts (mirrored): front finned remote reservoirs + hoses, rear remote
    reservoirs + hoses.  Centre static parts (steering rack) returned separately."""
    side, centre = [], []
    up = V((0, 0, 1))

    # [fix r2] front finned remote reservoir (front.png, front_3q_right.png): a smooth satin aluminium can,
    # 90 mm across, with fine LONGITUDINAL fins, black anodized end caps + band. [fix r5] in the open trough ahead of
    # the wing edge (see F_RES_TOP), leaning in 26 deg; clamp band + bracket to the bulkhead hoop's top bar behind it.
    rb_, rt_ = V(F_RES_BOT), V(F_RES_TOP)
    ax = (rt_ - rb_).normalized()
    # [fix r5] black bottom boss + fitting (front.png / front_3q). [fix r6] slimmer (7.6 cm), 32 fins, photo lean
    side += finned_can('f_res', rb_, rt_, m, r_root=F_RES_R[0], r_tip=F_RES_R[1], fit_top=True, lo_fit=True,
                       ribs=F_RES_RIBS, cap_r=F_RES_R[1] + 0.0015, cap_len=F_RES_CAP, top_fit_dir=F_RES_FIT_DIR)
    # clamp band where the can passes the chassis bulkhead hoop's top bar height (y 1.19, z 0.86), flat bracket straight
    # back to a saddle on the bar
    hoop_y, hoop_r = spec.FRONT_BULKHEAD_Y + 0.010, spec.CAGE_TUBE_R
    fb = min(0.80, max(0.35, (0.850 - rb_.z) / (rt_.z - rb_.z)))
    mid = lerp(rb_, rt_, fb)
    side.append(cyl('f_res_band', F_RES_R[1] + 0.0035, mid - ax * 0.010, mid + ax * 0.010, m['anod'], segs=20))
    bx_, bz_ = mid.x, mid.z
    y_a, y_b = mid.y - F_RES_R[1], hoop_y + hoop_r + 0.004
    side.append(box_obj('f_res_bracket', (0.024, y_a - y_b + 0.004, 0.010), V((bx_, (y_a + y_b) / 2, bz_)), m['black']))
    side.append(box_obj('f_res_saddle', (0.030, 0.010, 0.022), V((bx_, y_b + 0.002, bz_)), m['black']))
    # [fix r5] hose from the TOP fitting forward to the banjo on the rear rim of the BYPASS cap (the can is the bypass's
    # remote reservoir, in line above it in front.png): it rises off the can, crosses over the upper A-arm's rear leg
    # (top ~0.88 at full bump) at z ~0.94-0.96 and drops into the banjo from behind / above. It never enters the bypass'
    # y band (cap rim y >= 1.458) except at the banjo, so the shock's swing at bump (it pivots about its top eye in the
    # x-z plane) cannot cut it; the coilover has no remote hose.
    Mb, Lb = shock_frame(F_BYP_BOT, F_BYP_TOP)
    ztb = Lb - F_BYP_CAP_GAP
    f0 = V((-(0.032 - 0.002), 0.0, ztb + F_BYP_FIT_Z))
    f1 = V((-(0.032 + 0.016), 0.0, ztb + F_BYP_FIT_Z + 0.018 * F_BYP_FIT_RISE))
    fit = Mb @ f1
    fit_dir = (Mb.to_3x3() @ (f1 - f0)).normalized()
    # [fix r6] can top fitting -> up and forward over the rear leg's bump sweep (leg top <= 0.862 at |x| 0.41) -> down a
    # vertical run at y F_HOSE_Y (>= 1.1 cm in front of the leg, >= 1.5 cm behind the bypass cap's rim) -> level into
    # the banjo
    t0, td = can_top_fit(rb_, rt_, F_RES_CAP, F_RES_R[1] + 0.0015, F_RES_FIT_DIR)
    hy = F_HOSE_Y
    hz = F_HOSE_Z                                # crest over the leg's sweep (leg top <= 0.862 at |x| 0.40, +0.30)
    hose = [t0, t0 + td * 0.012, V((t0.x - 0.016, t0.y + 0.012, hz - 0.006)), V((t0.x - 0.012, t0.y + 0.060, hz)),
            V((fit.x - 0.010, hy - 0.006, hz - 0.040)), V((fit.x + 0.002, hy, fit.z + 0.050)),
            V((fit.x, hy + 0.001, fit.z + 0.012)), fit + fit_dir * 0.010, fit]
    side.append(sweep('f_res_hose', smooth_path(hose, 2), 0.0085, m['hose'], sides=8))

    # [fix r2] remote reservoirs on the upper X-brace arms behind the seats (front.png, seat_closeup.png): black anodized
    # cans with knurled caps and an orange collar. [fix r5] clamped under / forward of the arm (see xbrace_reservoir);
    # they feed the rear coilovers.
    side += xbrace_reservoir(m)
    # [fix r5] the rear BYPASS shock's remote reservoir: a black can standing in the pod bay just behind the bypass,
    # inboard of it (|x| <= 0.50, was 0.60 with the cap 9 cm over the deck, widening the rear view). It stays between
    # the rear brace (x -0.418, >= 1.4 cm), the bypass's adjuster knobs (>= 1.3 cm), the powertrain's finned canister
    # (y >= -1.22 at its back, >= 3 cm) and the deck's front edge (y -1.32); its cap top is spec.rear_deck_z - 0.075,
    # so the can and the short hose looping over from the bypass cap fitting (rear-inboard) stay under the deck line.
    rx_, ry_, rr_ = R_RES_XY[0], R_RES_XY[1], 0.024
    top_z = spec.rear_deck_z(ry_) - 0.075
    rr1 = V((rx_, ry_, top_z - 0.020))                # body top / cap bottom
    rr0 = rr1 - V((0, 0, R_RES_LEN))
    side.append(lathe_at('r_res', [(0.0, 0.0), (rr_ - 0.003, 0.0), (rr_, 0.005), (rr_, R_RES_LEN - 0.006),
                                   (rr_ - 0.003, R_RES_LEN), (0.0, R_RES_LEN)], rr0, up, m['anod'], segs=16))
    side.append(lathe_at('r_res_cap', [(0.0, 0.0), (rr_ + 0.0015, 0.0), (rr_ + 0.0015, 0.006), (rr_ - 0.0005, 0.008),
                                       (rr_ + 0.0015, 0.010), (rr_ + 0.0015, 0.016), (0.016, 0.020), (0.0, 0.020)],
                          rr1, up, m['anod'], segs=14))
    side.append(cyl('r_res_valve', 0.0035, rr1 + V((0.010, -0.006, 0.017)), rr1 + V((0.010, -0.006, 0.028)), m['alu'],
                    segs=6))
    for z in (rr0.z + 0.045, rr0.z + R_RES_LEN - 0.06):
        side.append(cyl('r_res_band', rr_ + 0.002, V((rx_, ry_, z - 0.007)), V((rx_, ry_, z + 0.007)), m['alu'],
                        segs=16))
    tq = V((rx_, ry_, top_z))                          # top fitting (boss + hex) on the cap, hose leaves upward
    side.append(cyl('r_res_fit', 0.008, tq - V((0, 0, 0.002)), tq + V((0, 0, 0.012)), m['alu'], segs=8))
    side.append(hexnut('r_res_fitnut', tq + V((0, 0, 0.006)), (0, 0, 1), 0.0115, 0.007, m['anod']))
    t_end = tq + V((0, 0, 0.012))
    Mb, Lbr = shock_frame(R_BYP_BOT, R_BYP_TOP)
    fa = V((math.cos(R_BYP_FIT_ANG), math.sin(R_BYP_FIT_ANG), 0.0))
    f0 = fa * (0.035 - 0.002) + V((0, 0, Lbr - R_BYP_CAP_GAP + 0.010))
    f1 = fa * (0.035 + 0.016) + V((0, 0, Lbr - R_BYP_CAP_GAP + 0.010))
    fit = Mb @ f1
    fdir = (Mb.to_3x3() @ (f1 - f0)).normalized()
    hz = max(fit.z, t_end.z) + 0.010
    hose = [fit, fit + fdir * 0.012, V(((fit.x + t_end.x) / 2 - 0.004, (fit.y + t_end.y) / 2 - 0.010, hz)),
            t_end + V((0, 0, 0.012)), t_end]
    side.append(sweep('r_res_hose', smooth_path(hose, 4), 0.0080, m['hose'], sides=8))

    # steering rack (centre): [fix r3] short front-steer rack behind the bumper plate (spec.F_STEER_RACK): housing
    # +-0.072 on the chassis rack plate (top face at rk.z - 0.041), rack-end clevises around the tie-rod heims at
    # |x| = |rk.x|, pinion on the left end
    rk = RACK
    y, z = rk.y, rk.z
    xr = abs(rk.x)
    hx = xr - 0.038                                   # housing half-length (0.072)
    centre.append(lathe_at('rack_housing', [(0.0, 0.0), (0.024, 0.0), (0.027, 0.006), (0.027, 2 * hx - 0.006),
                                            (0.024, 2 * hx), (0.0, 2 * hx)], V((-hx, y, z)), (1, 0, 0), m['alu'],
                           segs=16))
    plate_top = z - 0.045 + 0.004
    for sx in (-1, 1):
        # [fix r6] rack-end clevis rebuilt for the tie rod's swing (it tilts ~28 deg about this joint at full bump):
        # a yoke block, two plates 4.5 cm apart (inner faces clear of the tilted heim neck) that stop ~1 cm
        # outboard of the bolt, and high-misalignment cone spacers on the bolt
        # (the game also stretches the tie rod along its axis, up to 1.34x at full droop + full lock, so the heim
        # eye's inboard edge reaches ~2.6 cm from the bolt: the yoke face sits 4 cm in, on the housing's end)
        centre.append(box_obj('rack_yoke', (0.012, 0.032, 0.055), V((sx * (xr - 0.046), y, z)), m['alu']))
        for s_ in (-1, 1):
            shp = round_poly([(-0.044, -0.016), (0.002, -0.016), (0.012, 0.0), (0.002, 0.016), (-0.044, 0.016)],
                             [0, 0.004, 0.008, 0.004, 0], 2)
            centre.append(plate('rack_clevis', shp, V((sx * xr, y, z + s_ * 0.025)), (sx, 0, 0), (0, sx, 0),
                                0.005, m['alu']))
            centre.append(lathe_at('rack_spacer', [(0.0, 0.0), (0.0090, 0.0), (0.0075, 0.0080), (0.0, 0.0080)],
                                   V((sx * xr, y, z + s_ * 0.0225)), (0, 0, -s_), m['steel'], segs=8))
        centre += bolt('rack_bolt', V((sx * xr, y, z)), (0, 0, 1), 0.058, m)
        centre.append(sharpen(cylinder('rack_mount', 0.031, 0.026, material=m['alu'], segments=16), 35))
        put(centre[-1], V((sx * 0.040, y, z)), (1, 0, 0))
        fh = (z - 0.026) - plate_top
        # [fix r5] feet stop at y 1.705: the chassis's raked V-plate (bumper plate) passes y 1.724 at the rack plate
        centre.append(box_obj('rack_foot', (0.040, 0.040, max(0.006, fh)), V((sx * 0.040, y - 0.015, plate_top + fh / 2)),
                              m['alu']))
    # pinion housing on the left end, intermediate shaft straight back along the centre line between the arm pivots
    # and the chassis nose posts, UNDER the upper pivot rail (z ~0.61) to a U-joint behind the arm pivots, then out
    # to the column end at the footwell wall
    pin0 = V((-0.040, y - 0.022, z + 0.012))
    uj2 = V((-0.028, spec.FRONT_BULKHEAD_Y + 0.100, 0.615))     # between the chassis nose posts (|x| >= 0.05)
    pdir = (uj2 - pin0).normalized()
    centre.append(cyl('rack_pinion', 0.020, pin0 - pdir * 0.02, pin0 + pdir * 0.055, m['alu'], segs=16))
    uj = pin0 + pdir * 0.072
    centre.append(sharpen(cylinder('rack_uj', 0.015, 0.03, material=m['steel'], segments=8), 30))
    put(centre[-1], uj, pdir)
    centre.append(cyl('rack_ishaft', 0.010, uj + pdir * 0.015, uj2, m['steel'], segs=10))
    end = V((-0.33, 1.215, 0.66))
    centre.append(sharpen(cylinder('rack_uj2', 0.015, 0.03, material=m['steel'], segments=8), 30))
    put(centre[-1], uj2, end - uj2)
    centre.append(cyl('rack_ishaft2', 0.010, uj2 + (end - uj2).normalized() * 0.015, end, m['steel'], segs=10))
    return side, centre


def box_obj(name, size, loc, material):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = V((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(size) * 0.12, segments=1, affect='EDGES', profile=0.5)
    o = bm_obj(name, bm, material, 30)
    o.location = loc
    return o


def _fillet_pts(points, radius, steps=6):
    """Round the corners of a 3D polyline (quadratic arcs, like common.tube's bender)."""
    pts = [V(p) for p in points]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        d1, d2 = a - b, c - b
        l1, l2 = d1.length, d2.length
        d1.normalize(); d2.normalize()
        ang = d1.angle(d2)
        if ang > math.pi - 1e-3:
            out.append(b)
            continue
        t = min(radius / math.tan(ang / 2), l1 * 0.48, l2 * 0.48)
        p1, p2 = b + d1 * t, b + d2 * t
        for k in range(steps + 1):
            u = k / steps
            out.append(p1 * (1 - u) ** 2 + b * (2 * u * (1 - u)) + p2 * (u * u))
    out.append(pts[-1])
    return out


def smooth_path(pts, steps=4):
    """Catmull-Rom through the points (hoses)."""
    P = [V(p) for p in pts]
    P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for s in range(steps):
            t = s / steps
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(P[-2])
    return out


# ------------------------------------------------------------------ mirror + register

def mirror_group(objs):
    out = []
    for o in objs:
        c = mirror_x(o, o.name + '_R')
        sharpen(c, 35)
        if 'tatum' in o.name:          # keep the logo reading left-to-right on the right side
            uvl = c.data.uv_layers.active
            if uvl:
                for d_ in uvl.data:
                    d_.uv = (1.0 - d_.uv[0], d_.uv[1])
        out.append(c)
    return out


def mx(p):
    return None if p is None else V((-p[0], p[1], p[2]))


def build(C):
    ensure_textures()
    _XB['C'] = C
    m = mats()
    for corner_fn, wl, wr in ((front_corner, 'FL', 'FR'), (rear_corner, 'RL', 'RR')):
        segs = corner_fn(m)
        for name, (objs, a, b, shock) in segs.items():
            objs = [o for o in objs if o is not None]
            right = mirror_group(objs)
            rname = name.replace(wl, wr)
            if a is None:
                C.add(objs, name)
                C.add(right, rname)
            else:
                C.segment(name, objs, a, b, wl, shock=shock)
                C.segment(rname, right, mx(a), mx(b), wr, shock=shock)
    side, centre = statics(m)
    C.add(side, 'static')
    C.add(mirror_group(side), 'static')
    C.add(centre, 'static')
