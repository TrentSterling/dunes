"""Driver arms for the cockpit view: black fire-suit sleeves with one thin orange accent line and
racing gloves (black / charcoal panels, ribbed knit cuffs, thin orange piping and a small orange logo
on the back of the hand) curled round a 28 mm steering-wheel rim.

    python arms/build_arms.py [--out PATH] [--blend out/part_arms.blend]

Writes ../../assets/driver/arms.glb (one skinned mesh, both arms, plus the static
legs) and the suit textures textures/arms_suit_*.jpg.

Legs (r4): object 'DriverLegs', a static mesh (no bones) in the same frame as the arms' rest pose: fire-suit
thighs, knees and shins from the GLX seat's H-point (spec.SEAT_H_POINT_*) to black race boots, the right
boot on the throttle pad, the left one on the dead pedal (pedal positions of parts/interior.py r4, floor
spec.FLOOR_Z). Its extras hold 'eye' (spec.DRIVER_EYE, Blender axes): the game shows the legs only in a
car whose driver's eye matches it (they are posed for this cockpit).

Rig (glTF joints, all flat - no parent bones, so the game can stretch one bone without shearing
the next): UpperArm.L/R (shoulder -> elbow), ForeArm.L/R (elbow -> wrist), Hand.L/R (wrist ->
knuckles). The fingers are modelled in the grip pose (rigid with Hand). Morph targets 'OpenL' / 'OpenR'
open the fingers and lift the thumb of one glove (used while a spoke passes under that hand; the
game also lifts the hand off the rim then).
Empties Grip.L / Grip.R give the grip frame of each glove in the rest pose: origin on the rim
centre line, X = R x A (along the rim), Y = R (radially out from the wheel centre), Z = A (column
axis, toward the driver). The game places a glove by putting that frame on the rim:
handBone = gripTarget * inverse(gripRest) * handBoneRest. Their extras hold the glove's extent
along X (grip_x_min / grip_x_max) for spoke clearance.

The rest pose is the GLX pro cockpit (spec.py): shoulders where the game puts them (SHOULDER below =
glamis-game driver-arms.js SHOULDER, relative to spec.DRIVER_EYE), hands at ten and two (0.55 rad
above horizontal), so the skin is undeformed in the main view.
Hand coordinates below are for the LEFT glove (index toward +X); the right glove is its mirror.
"""
import argparse
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector, Matrix  # noqa: E402
import common  # noqa: E402
import spec  # noqa: E402

V = Vector
OUT = os.path.normpath(os.path.join(ROOT, "..", "..", "assets", "driver", "arms.glb"))
TEX = os.path.join(ROOT, 'textures')

RIM_R = spec.STEERING_WHEEL_R          # rim centre-line radius
RIM_T = 0.014                          # rim tube radius (28 mm suede rim)
CLEAR = RIM_T + 0.0016                 # glove surface never closer than this to the rim centre line
GRIP_ANG = 0.55                        # hands 0.55 rad above the horizontal (ten and two)
L_UPPER, L_FORE = 0.355, 0.305         # shoulder-elbow, elbow-wrist (tall driver in a fire suit: keeps the elbows bent)
PALM_P0 = (-0.002, 0.030, 0.083)       # palm wrist end (hand coords, before the tilt)
PALM_P1 = (0.001, 0.0262, -0.019)      # palm knuckle end
WRIST_U = (-0.003, 0.030, 0.080)       # wrist joint (before the tilt)
# the glove is modelled with the fingers square to the rim, then turned about the radial axis so
# the hand runs diagonally across the rim and lines up with the forearm (which comes up from
# below, along the rim): a natural, slightly ulnar-deviated wrist instead of a 50 deg bend.
TILT = math.radians(-34.0)
# ...and rolled about the rim so the back of the hand faces out and back toward the driver, the
# fingers wrap over the front of the rim and the thumb hooks round its inside.
ROLL = math.radians(50.0)

# shoulder joint relative to the eye (Blender axes: x right, y forward, z up), a little protracted
# toward the wheel so the elbows keep a natural bend; left shoulder at x - 0.2, right at x + 0.2
SHOULDER = (0.2, -0.07, -0.29)

MATS = ['suit', 'glove', 'grey', 'orange', 'palm', 'knit']
SUIT, GLOVE, GREY, ORANGE, PALM, KNIT = range(6)

# ---- legs (static): H-point of the driver's seat, pedals of the r4 interior (parts/interior.py: PY 0.850,
# DZF = FLOOR_Z - 0.45; pad centres and normals below), a tall driver to match the arms. The shins pass under the
# driver's knee bolster (interior _DASH_D: underside z ~0.65 at y 0.56-0.70), so the knees stay low (z ~0.72)
HIP_X = 0.072                          # hip joints either side of the seat centre line
L_THIGH, L_SHIN = 0.51, 0.50
_DZF = spec.FLOOR_Z - 0.45
THROTTLE = ((-0.265, 0.855, 0.550 + _DZF), (0.0, -0.78, 0.62))          # pad centre, pad normal
DEAD_PEDAL = ((-0.580, 0.862, 0.545 + _DZF), (0.35, -0.70, 0.62))
HEEL_Z = spec.FLOOR_Z + 0.012          # boot heel on the floor mat (mat top ~ FLOOR_Z + 0.007)
LEG_MATS = ['suit', 'boot', 'sole', 'orange']
L_SUIT, L_BOOT, L_SOLE, L_ORANGE = range(4)


def tilt(P):
    """rotate hand-coordinate points (n,3) about the hand Y axis (radial) by TILT"""
    P = np.atleast_2d(np.asarray(P, dtype=float))
    c, s_ = math.cos(TILT), math.sin(TILT)
    out = P.copy()
    out[:, 0] = P[:, 0] * c + P[:, 2] * s_
    out[:, 2] = -P[:, 0] * s_ + P[:, 2] * c
    return out


def roll(P):
    """rotate (n,3) about the rim axis X by ROLL (from +Y toward +Z)"""
    P = np.atleast_2d(np.asarray(P, dtype=float))
    c, s_ = math.cos(ROLL), math.sin(ROLL)
    out = P.copy()
    out[:, 1] = P[:, 1] * c - P[:, 2] * s_
    out[:, 2] = P[:, 1] * s_ + P[:, 2] * c
    return out


def place(P):
    """hand modelling coordinates -> final hand coordinates (tilt, then roll about the rim)"""
    return roll(tilt(P))


def untilt(P):
    P = np.atleast_2d(np.asarray(P, dtype=float))
    c, s_ = math.cos(-TILT), math.sin(-TILT)
    out = P.copy()
    out[:, 0] = P[:, 0] * c + P[:, 2] * s_
    out[:, 2] = -P[:, 0] * s_ + P[:, 2] * c
    return out


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, dtype=float) - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def nrm(v):
    v = np.asarray(v, dtype=float)
    return v / max(np.linalg.norm(v), 1e-12)


# ------------------------------------------------------------------ mesh accumulator
class MeshBuilder:
    def __init__(self):
        self.v = []        # positions
        self.w = []        # {bone: weight}
        self.f = []        # vertex index tuples
        self.uv = []       # per-face list of (u, v)
        self.m = []        # material index per face

    def vert(self, p, w):
        self.v.append(np.asarray(p, dtype=float))
        self.w.append(w)
        return len(self.v) - 1

    def face(self, idx, uvs, mat):
        self.f.append(tuple(idx))
        self.uv.append(list(uvs))
        self.m.append(mat)

    def sweep(self, C, LAT, DOR, a, b, nseg, mat, weight, uv_scale=(1.0, 1.0), disp=None,
              cap_start=False, cap_end=False, u0=0.0):
        """Rings around the curve C (n,3) with frame (LAT, DOR) (lat x dor = tangent), half-widths
        a (lateral) and b (dorsal) per ring. Ring vertex k sits at angle t = 2 pi k / nseg + u0*2pi:
        c + lat cos t a + dor sin t b (+ disp(i, t) * outward). mat(i, k, t) -> material index of
        the quad from ring i to i+1 starting at k. weight(i) -> bone weights of ring i."""
        n = len(C)
        s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
        idx = np.zeros((n, nseg), dtype=np.int64)
        ts = 2 * math.pi * (np.arange(nseg) / nseg + u0)
        for i in range(n):
            for k in range(nseg):
                t = ts[k]
                out = LAT[i] * math.cos(t) + DOR[i] * math.sin(t)
                ra, rb = a[i], b[i]
                p = C[i] + LAT[i] * math.cos(t) * ra + DOR[i] * math.sin(t) * rb
                if disp is not None:
                    p = p + out * disp(i, t)
                idx[i, k] = self.vert(p, weight(i))
        for i in range(n - 1):
            for k in range(nseg):
                k2 = (k + 1) % nseg
                uvs = [(k / nseg * uv_scale[0], s[i] * uv_scale[1]), ((k + 1) / nseg * uv_scale[0], s[i] * uv_scale[1]),
                       ((k + 1) / nseg * uv_scale[0], s[i + 1] * uv_scale[1]), (k / nseg * uv_scale[0], s[i + 1] * uv_scale[1])]
                self.face((idx[i, k], idx[i, k2], idx[i + 1, k2], idx[i + 1, k]), uvs, mat(i, k, ts[k]))
        if cap_end:
            pole = self.vert(C[-1] + (C[-1] - C[-2]) * 0.0, weight(n - 1))
            for k in range(nseg):
                k2 = (k + 1) % nseg
                self.face((idx[-1, k], idx[-1, k2], pole), [(k / nseg, 1), ((k + 1) / nseg, 1), (k / nseg + 0.5 / nseg, 1)], mat(n - 2, k, ts[k]))
        if cap_start:
            pole = self.vert(C[0], weight(0))
            for k in range(nseg):
                k2 = (k + 1) % nseg
                self.face((pole, idx[0, k2], idx[0, k]), [(k / nseg + 0.5 / nseg, 0), ((k + 1) / nseg, 0), (k / nseg, 0)], mat(0, k, ts[k]))
        return idx


def frames_along(C, lat_hint):
    """Tangents + (lat, dor) frames along C. lat_hint(i, T) gives a lateral direction (made
    orthogonal); dor = T x lat so that lat x dor = T (outward-facing quads)."""
    n = len(C)
    T = np.zeros_like(C)
    T[1:-1] = C[2:] - C[:-2]
    T[0] = C[1] - C[0]
    T[-1] = C[-1] - C[-2]
    T = T / np.linalg.norm(T, axis=1, keepdims=True)
    LAT = np.zeros_like(C)
    DOR = np.zeros_like(C)
    for i in range(n):
        l = np.asarray(lat_hint(i, T[i]), dtype=float)
        l = l - T[i] * l.dot(T[i])
        l = nrm(l)
        LAT[i] = l
        DOR[i] = np.cross(T[i], l)
    return T, LAT, DOR


def polyline_samples(P, counts, smooth_iter=0, keep_ends=True):
    """Sample a polyline P (m,3) with counts[j] samples on segment j, then optionally round the
    corners with Laplacian smoothing (end points fixed)."""
    pts = []
    for j in range(len(P) - 1):
        for q in range(counts[j]):
            pts.append(P[j] + (P[j + 1] - P[j]) * (q / counts[j]))
    pts.append(P[-1])
    C = np.array(pts, dtype=float)
    for _ in range(smooth_iter):
        C2 = C.copy()
        C2[1:-1] = 0.25 * C[:-2] + 0.5 * C[1:-1] + 0.25 * C[2:]
        if keep_ends:
            C2[0], C2[-1] = C[0], C[-1]
        C = C2
    return C


# ------------------------------------------------------------------ glove (hand coordinates)
# rim along X through the origin locally; the true rim is the circle of radius RIM_R about
# (0, -RIM_R, 0) in the XY plane - used for the clearance projection.
FINGERS = [
    # name,  x at MCP, MCP radius, lengths (prox, mid, dist to tip centre), half width, half thickness
    # (r5: ~1 mm narrower and spread a little: 3.5-4 mm gaps between the fingers, so they read as four fingers
    # from the driver's seat instead of one mitten; was 0.8-1.5 mm)
    ('index', 0.0315, 0.031, (0.042, 0.025, 0.016), 0.0087, 0.0088),
    ('middle', 0.0103, 0.0315, (0.046, 0.028, 0.017), 0.0090, 0.0091),
    ('ring', -0.0110, 0.031, (0.044, 0.026, 0.016), 0.0085, 0.0087),
    ('pinky', -0.0310, 0.029, (0.034, 0.020, 0.014), 0.0076, 0.0079),
]
MCP_PHI = math.radians(-36.0)


def rim_dist(p):
    """distance from p (hand coords) to the rim centre circle, and the closest circle point"""
    q = np.array([p[0], p[1] + RIM_R, 0.0])
    rho = np.linalg.norm(q[:2])
    c = q * (RIM_R / max(rho, 1e-9))
    c[1] -= RIM_R
    return np.linalg.norm(p - c), c


def finger_chain(x, r0, lens, half_t, open_amt):
    """Joint positions (MCP, PIP, DIP, tip centre) of a finger wrapped round the rim (curled) or
    opened by open_amt (0 = gripping, 1 = open). The curled chain wraps each phalanx tangent to the
    circle of radius m = rim + finger half thickness (tightest grip without penetrating)."""
    m = RIM_T / math.cos(TILT) * 0.96 + half_t + 0.0012
    phi, r = MCP_PHI, r0
    pts = [(phi, r)]
    for L in lens:
        t_a = math.sqrt(max(r * r - m * m, 0.0))
        if L >= t_a:
            rb = math.sqrt(m * m + (L - t_a) ** 2)
            dphi = math.atan2(t_a, m) + math.atan2(L - t_a, m)
        else:
            rb = m
            c = (r * r + m * m - L * L) / (2 * r * m)
            dphi = math.acos(max(-1, min(1, c)))
        phi -= dphi
        r = rb
        pts.append((phi, r))
    yz = [np.array([rr * math.cos(ph), rr * math.sin(ph)]) for ph, rr in pts]
    if open_amt > 0:
        # extend: rotate the whole finger back about the MCP and straighten PIP / DIP
        dirs = [yz[j + 1] - yz[j] for j in range(3)]
        ang = [math.atan2(d[1], d[0]) for d in dirs]
        bends = [ang[j + 1] - ang[j] for j in range(2)]
        bends = [(bb + math.pi) % (2 * math.pi) - math.pi for bb in bends]
        a0 = ang[0] + open_amt * math.radians(62)
        new = [yz[0]]
        a = a0
        for j in range(3):
            if j > 0:
                a += bends[j - 1] * (1 - 0.8 * open_amt)
            new.append(new[-1] + np.array([math.cos(a), math.sin(a)]) * lens[j])
        yz = new
    return [np.array([x, p[0], p[1]]) for p in yz]


def finger_mesh(mb, chain, a0, b0, weight, rings_per=(10, 7, 6), nseg=16, base_back=0.012, grey_pad=True):
    """Sweep a finger along its joint chain with rounded joints, knuckle bulges, seam grooves at
    PIP/DIP, a grey pad over the proximal phalanx, suede palm side and a rounded tip."""
    mcp = chain[0]
    back = mcp + nrm(mcp - chain[1]) * base_back   # start inside the palm
    P = np.array([back] + chain)
    counts = [3] + list(rings_per)
    C = polyline_samples(P, counts, smooth_iter=3)
    # tip cap: extra rings shrinking onto a pole along the last direction
    tdir = nrm(C[-1] - C[-2])
    ncap = 4
    caps = [C[-1] + tdir * (b0 * 0.9) * math.sin(math.pi / 2 * (q + 1) / (ncap + 1)) for q in range(ncap)]
    capr = [math.cos(math.pi / 2 * (q + 1) / (ncap + 1)) for q in range(ncap)]
    C = np.vstack([C, caps])
    nC = len(C)
    # joint ring indices (approximate): sample index of each chain joint
    jidx = [3, 3 + rings_per[0], 3 + rings_per[0] + rings_per[1]]

    def lat_hint(i, T):
        d, c = rim_dist(C[i])
        away = C[i] - c
        return np.cross(nrm(away), T)
    T, LAT, DOR = frames_along(C, lat_hint)
    a = np.full(nC, a0)
    b = np.full(nC, b0)
    a[:3] *= np.linspace(1.12, 1.0, 3)
    b[:3] *= np.linspace(1.15, 1.0, 3)
    for q in range(ncap):
        a[nC - ncap + q] = a0 * 0.92 * capr[q]
        b[nC - ncap + q] = b0 * 0.92 * capr[q]
    a[nC - ncap - 1] *= 0.96
    j1, j2 = jidx[0], jidx[1]
    groove = set()
    for j in jidx[1:]:
        groove.add(j)

    def disp(i, t):
        s = math.sin(t)
        d = 0.0
        if i in groove and s > 0.2:       # stitched seam across the knuckle
            d -= 0.0014 * (s - 0.2)
        for j in jidx:                      # knuckle bulge on the back of the joints
            if abs(i - j) <= 1 and s > 0:
                d += 0.0022 * s * (1 - 0.5 * abs(i - j))
        if j1 + 1 < i < j2 - 1 and s > 0.35:  # (r5) padded strip over the proximal phalanx
            d += 0.0011 * (s - 0.35) / 0.65
        return d

    def mat(i, k, t):
        s = math.sin(t + math.pi / 14)
        if s < -0.45:
            return PALM
        if grey_pad and j1 + 1 <= i < j2 - 1 and s > 0.35:
            return GREY
        return GLOVE
    idx = mb.sweep(C, LAT, DOR, a, b, nseg, mat, weight, uv_scale=(1, 10), disp=disp, cap_end=True)
    return idx


def palm_mesh(mb, weight, nseg=32, nr=20):
    """Back of the hand + palm from the wrist to the knuckle line."""
    P0, P1 = np.array(PALM_P0), np.array(PALM_P1)
    C = np.array([P0 + (P1 - P0) * (i / (nr - 1)) for i in range(nr)])
    T, LAT, DOR = frames_along(C, lambda i, T: np.array([-1.0, 0, 0]))   # lat = pinky side, dor = back
    u = np.linspace(0, 1, nr)
    a = 0.0300 + 0.0125 * smoothstep(0.0, 0.72, u)               # half width
    b = 0.0160 - 0.0042 * smoothstep(0.25, 1.0, u)               # half thickness
    a[-1] *= 0.97
    b[-1] *= 0.94

    def disp(i, t):
        c, s_ = math.cos(t), math.sin(t)
        d = (abs(c) ** 0.7 * abs(s_) ** 0.7) * 0.0022           # soften into a rounded box
        if s_ > 0:
            d += 0.0026 * s_ ** 2                                # domed back of the hand
        elif u[i] < 0.45:
            d += 0.0045 * (-s_) * (1 - u[i] / 0.45)              # heel of the hand
        return d

    def mat(i, k, t):
        s_, c = math.sin(t), math.cos(t)
        uu = i / (nr - 1)
        if s_ < -0.55:
            return PALM
        if 0.16 <= uu <= 0.88 and 0.70 < s_ <= 0.80 and c < 0:
            return ORANGE                                        # thin piping along the panel (index side)
        if 0.50 <= uu <= 0.60 and s_ > 0.97:
            return ORANGE                                        # small logo on the back of the hand
        if s_ > 0.80 and 0.16 <= uu <= 0.88:
            return GREY                                          # charcoal back-of-hand panel
        return GLOVE
    return mb.sweep(C, LAT, DOR, a, b, nseg, mat, weight, uv_scale=(1, 10), disp=disp, u0=0.0)


def thumb_chain(open_amt):
    """Thumb joints (CMC inside the thenar, MCP, IP, tip centre) in FINAL hand coordinates (after
    the tilt): it lies along the rim on the driver's side, pointing up the rim."""
    curled = [(-0.0265, 0.023, 0.058), (0.004, 0.0125, 0.0405), (0.034, 0.0005, 0.0262), (0.055, -0.003, 0.0248)]
    opened = [(-0.0265, 0.023, 0.058), (0.000, 0.026, 0.050), (0.027, 0.033, 0.052), (0.048, 0.035, 0.052)]
    return [np.array(c) + (np.array(o) - np.array(c)) * open_amt for c, o in zip(curled, opened)]


def thumb_mesh(mb, chain, weight, nseg=14):
    """built in final coordinates, then un-tilted (the whole glove is tilted afterwards)"""
    P = np.array(chain)
    C = polyline_samples(P, [5, 7, 5], smooth_iter=3)
    tdir = nrm(C[-1] - C[-2])
    ncap = 4
    b0 = 0.0093
    caps = [C[-1] + tdir * (b0 * 0.9) * math.sin(math.pi / 2 * (q + 1) / (ncap + 1)) for q in range(ncap)]
    capr = [math.cos(math.pi / 2 * (q + 1) / (ncap + 1)) for q in range(ncap)]
    C = np.vstack([C, caps])
    nC = len(C)
    nail = nrm(np.array([0.0, 0.45, 1.0]))          # nail side faces the driver

    def lat_hint(i, T):
        return np.cross(nail, T)
    T, LAT, DOR = frames_along(C, lat_hint)
    u = np.linspace(0, 1, nC)
    a = 0.0105 + 0.0080 * (1 - smoothstep(0.0, 0.33, u))    # thick web / thenar near the base
    b = 0.0093 + 0.0058 * (1 - smoothstep(0.0, 0.33, u))
    for q in range(ncap):
        a[nC - ncap + q] = 0.0105 * 0.92 * capr[q]
        b[nC - ncap + q] = b0 * 0.92 * capr[q]
    ip = 5 + 7

    def disp(i, t):
        s_ = math.sin(t)
        if i == ip and s_ > 0.2:
            return -0.001 * (s_ - 0.2)
        return 0.0

    def mat(i, k, t):
        # (r5) the whole thumb in the dark palm suede (#151517), like the palm side of the photo gloves
        return PALM
    n0 = len(mb.v)
    idx = mb.sweep(C, LAT, DOR, a, b, nseg, mat, weight, uv_scale=(1, 10), disp=disp, cap_end=True)
    mb.v[n0:] = list(untilt(np.array(mb.v[n0:])))
    return idx


def knuckle_pads(mb, chains, weight, nseg=12):
    """A padded guard over each MCP knuckle (grey, separated by seams)."""
    for (name, x, r0, lens, a0, b0), ch in zip(FINGERS, chains):
        mcp, pip = ch[0], ch[1]
        d, c = rim_dist(mcp)
        out = nrm(mcp - c)
        # (r5: thicker moulded pads, 13 x 9.5 mm, standing 5 mm proud)
        cen = mcp + out * (b0 + 0.0034) + nrm(pip - mcp) * 0.003
        half = a0 * 0.97
        P = np.array([cen + np.array([-half, 0, 0]), cen + np.array([half, 0, 0])])
        Cc = polyline_samples(P, [7])
        n = len(Cc)
        T, LAT, DOR = frames_along(Cc, lambda i, T: out)
        prof = np.sin(np.linspace(0.18, math.pi - 0.18, n)) ** 0.5
        a = 0.0066 * prof
        b = 0.0048 * prof
        mb.sweep(Cc, LAT, DOR, a, b, nseg, lambda i, k, t: GREY, weight, uv_scale=(1, 10), cap_start=True, cap_end=True)


def build_glove(open_amt, weight):
    mb = MeshBuilder()
    palm_mesh(mb, weight)
    chains = []
    for name, x, r0, lens, a0, b0 in FINGERS:
        ch = finger_chain(x, r0, lens, b0, open_amt)
        chains.append(ch)
        finger_mesh(mb, ch, a0, b0, weight, grey_pad=name in ('index', 'middle', 'ring', 'pinky'))
    thumb_mesh(mb, thumb_chain(open_amt), weight)
    curled_chains = [finger_chain(x, r0, lens, b0, 0.0) for name, x, r0, lens, a0, b0 in FINGERS]
    # knuckle pads ride on the MCP joints (which do not move when the fingers open)
    knuckle_pads(mb, curled_chains, weight)
    return mb


def clear_rim(P):
    """push glove vertices out of the rim tube (cloth pressed on the rim)"""
    out = P.copy()
    for i, p in enumerate(P):
        d, c = rim_dist(p)
        if d < CLEAR:
            dirn = p - c
            if np.linalg.norm(dirn) < 1e-9:
                dirn = np.array([0, 1.0, 0])
            out[i] = c + nrm(dirn) * CLEAR
    return out


# ------------------------------------------------------------------ pose (GLX cockpit, Blender coords)
def pose(side):
    """side 'L' (driver's left, x more negative) or 'R'. Returns dict of rest-pose points/frames."""
    eye = V(spec.DRIVER_EYE)
    C = V(spec.STEERING_WHEEL_CENTRE)
    A = V(spec.STEERING_COLUMN_DIR).normalized()
    sgn = -1 if side == 'L' else 1
    left = V((sgn, 0, 0)) - A * A.x * sgn
    left.normalize()
    up = (V((0, 0, 1)) - A * A.z).normalized()
    R = (left * math.cos(GRIP_ANG) + up * math.sin(GRIP_ANG)).normalized()
    X = R.cross(A).normalized()
    P = C + R * RIM_R
    M = Matrix((X, R, A)).transposed().to_4x4()
    M.translation = P
    S = V((eye.x + sgn * SHOULDER[0], eye.y + SHOULDER[1], eye.z + SHOULDER[2]))
    wh = V(place(WRIST_U)[0])
    if side == 'R':
        wh.x = -wh.x
    W = M @ wh
    # two-bone IK, elbows down and out (same as the game)
    d = (W - S).length
    toW = (W - S) / d
    d = min(d, L_UPPER + L_FORE - 1e-3)
    a = (L_UPPER ** 2 - L_FORE ** 2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, L_UPPER ** 2 - a * a))
    pole = V((0.8 * sgn, 0, -1))
    pole = (pole - toW * pole.dot(toW)).normalized()
    E = S + toW * a + pole * h
    W = S + toW * d
    return dict(S=S, E=E, W=W, M=M, R=R, A=A, X=X, P=P, C=C, side=side, sgn=sgn)


def hand_to_world(P, M, mirror):
    Q = P.copy()
    if mirror:
        Q[:, 0] = -Q[:, 0]
    R = np.array(M.to_3x3())
    t = np.array(M.translation)
    return Q @ R.T + t


# ------------------------------------------------------------------ sleeve + cuff (world coords)
def sleeve(mb, ps, palm_wrist_world, palm_axis_world):
    S, E, W = np.array(ps['S']), np.array(ps['E']), np.array(ps['W'])
    side = ps['side']
    bU, bF, bH = 'UpperArm.' + side, 'ForeArm.' + side, 'Hand.' + side
    f = nrm(W - E)
    u_dir = nrm(E - S)
    start = S - u_dir * 0.03
    end = W - f * 0.058                      # ends inside the glove cuff
    n_up = 16
    n_fo = 34
    P = np.array([start, E, end])
    C = polyline_samples(P, [n_up, n_fo], smooth_iter=6)
    n = len(C)
    hinge = nrm(np.cross(E - S, W - E))
    inner = nrm((S + W) / 2 - E)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    sE = s[np.argmin(np.linalg.norm(C - E, axis=1))]
    # stripe on the top/outer line of the forearm: the ring angle facing up and outward
    want = nrm(np.array([0.55 * ps['sgn'], 0.0, 1.0]))

    def lat_hint(i, T):
        return hinge
    T, LAT, DOR = frames_along(C, lat_hint)
    mid = int(n_up + n_fo * 0.6)
    tw = math.atan2(want.dot(DOR[mid]), want.dot(LAT[mid]))
    u0 = tw / (2 * math.pi) - 0.5           # texture u = 0.5 (the stripe) faces `want`
    # radius profile: loose suit, slightly oval
    a = np.interp(s, [0, 0.05, sE, s[-1] - 0.06, s[-1]], [0.060, 0.058, 0.050, 0.038, 0.031])
    b = np.interp(s, [0, 0.05, sE, s[-1] - 0.06, s[-1]], [0.057, 0.055, 0.046, 0.035, 0.0285])
    rng = np.random.default_rng(7)
    ph = rng.uniform(0, 2 * math.pi, 6)

    def disp(i, t):
        out = LAT[i] * math.cos(t) + DOR[i] * math.sin(t)
        d = 0.0
        de = s[i] - sE
        # elbow: bunched folds on the inside of the bend, a little bagging on the outside
        ins = out.dot(inner)
        if abs(de) < 0.085:
            env = 0.5 * (1 + math.cos(math.pi * de / 0.085))
            if ins > 0.0:
                d -= 0.0055 * env * ins * (0.5 + 0.5 * math.cos(2 * math.pi * de / 0.026 + 1.3 * math.cos(t)))
            else:
                d += 0.0025 * env * (-ins)
        # loose fabric: gentle diagonal wrinkles along the forearm and upper arm
        d += 0.0011 * math.sin(2 * math.pi * s[i] / 0.11 + 2 * t + ph[0]) * math.sin(t + ph[1])
        d += 0.0008 * math.sin(2 * math.pi * s[i] / 0.07 - 3 * t + ph[2])
        return d

    def weight(i):
        wf = float(smoothstep(sE - 0.06, sE + 0.05, s[i]))
        return {bU: 1 - wf, bF: wf}
    # the arm is long: u around the sleeve, v along it (texture covers 0.8 m)
    idx = mb.sweep(C, LAT, DOR, a, b, 30, lambda i, k, t: SUIT, weight,
                   uv_scale=(1, 1 / 0.8), disp=disp, cap_start=True, u0=u0)
    # ---- glove cuff (gauntlet) from over the sleeve to the wrist of the palm
    c0 = W - f * 0.078
    c1 = W - f * 0.012
    pw = np.array(palm_wrist_world)
    pa = nrm(palm_axis_world)
    # cubic from c0 (along f) to the palm wrist (along the palm axis)
    def bez(t):
        p0, p3 = c0, pw + pa * 0.004
        p1, p2 = c1, pw - pa * 0.02
        return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3
    nc = 16
    Cc = np.array([bez(q / (nc - 1)) for q in range(nc)])
    Tc, LATc, DORc = frames_along(Cc, lambda i, T: hinge)
    uc = np.linspace(0, 1, nc)
    # (r5: a little more flare at the open end and a slimmer wrist - a gauntlet that tapers onto the hand)
    ac = np.interp(uc, [0, 0.06, 0.14, 0.45, 0.75, 1.0], [0.0352, 0.0395, 0.0399, 0.0350, 0.0306, 0.0294])
    bc = np.interp(uc, [0, 0.06, 0.14, 0.45, 0.75, 1.0], [0.0322, 0.0362, 0.0364, 0.0290, 0.0212, 0.0163])
    sc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(Cc, axis=0), axis=1))])
    # black ribbed knit cuff (~4 cm) over the sleeve end, rolled edge, then the glove's wrist
    def disp_c(i, t):
        d = 0.0
        if uc[i] < 0.52:
            d += 0.0009 * math.cos(24 * t)    # knit ribs
        if uc[i] < 0.08:
            d += 0.0012                       # rolled edge
        elif uc[i] > 0.55:                    # (r5) soft leather creases round the wrist
            d += 0.00055 * math.sin(2 * math.pi * sc[i] / 0.011 + 0.9 * math.cos(t) + 0.6 * math.sin(2 * t))
        return d

    def mat_c(i, k, t):
        return KNIT if uc[i] < 0.5 else GLOVE
    sW = sc[np.argmin(np.linalg.norm(Cc - W, axis=1))]

    def weight_c(i):
        wh = float(smoothstep(sW - 0.03, sW + 0.012, sc[i]))
        return {bF: 1 - wh, bH: wh}
    mb.sweep(Cc, LATc, DORc, ac, bc, 30, mat_c, weight_c, uv_scale=(1, 10), disp=disp_c)
    return idx


# ------------------------------------------------------------------ legs + boots (static, world coords)
def foot_frame(pad, pitch_deg, toe_out_deg, contact=0.205, side_sgn=-1):
    """Boot on a pedal pad: heel on the floor, sole pitched up by pitch_deg, toe turned out by toe_out_deg;
    the sole touches the pad plane `contact` m from the heel. Returns origin (heel, sole bottom) and the
    axes s (along the sole), w (lateral, toward +x for no toe-out), u (sole normal)."""
    c, n = np.array(pad[0], dtype=float), nrm(pad[1])
    yaw = math.radians(toe_out_deg) * side_sgn          # left foot: toes turn toward -x
    fh = np.array([math.sin(yaw), math.cos(yaw), 0.0])
    a = math.radians(pitch_deg)
    sdir = fh * math.cos(a) + np.array([0, 0, 1.0]) * math.sin(a)
    w = nrm(np.cross(sdir, [0, 0, 1.0]))                 # lateral (+x side for yaw 0)
    u = np.cross(w, sdir)
    # heel h = (c.x, y, HEEL_Z) moved back along fh by t: solve (h + contact*s - c).n = pad + sole
    h0 = np.array([c[0], c[1], HEEL_Z])
    gap = 0.006 + 0.004
    t = ((h0 + contact * sdir - c).dot(n) - gap) / fh.dot(n)
    h = h0 - fh * t
    h[0] -= sdir[0] * contact * 0.5                      # keep the ball of the foot on the pad centre line
    return h, sdir, w, u


def boot(mb, h, sdir, w, u, side_sgn):
    """Black race boot: lofted rings from the heel to the toe (sole bottom flat, dark sole band), the upper
    rising into an ankle shaft; a thin orange line round the collar."""
    xs = np.array([-0.028, -0.020, -0.008, 0.015, 0.05, 0.09, 0.13, 0.17, 0.20, 0.225, 0.245, 0.257, 0.263])
    hw = np.array([0.020, 0.030, 0.036, 0.039, 0.040, 0.042, 0.046, 0.050, 0.051, 0.048, 0.040, 0.030, 0.016])
    ht = np.array([0.050, 0.080, 0.100, 0.118, 0.128, 0.118, 0.095, 0.074, 0.062, 0.052, 0.042, 0.032, 0.020])
    ns = 20
    rings = []
    for x, a_, t_ in zip(xs, hw, ht):
        ring = []
        for k in range(ns):
            th = 2 * math.pi * k / ns - math.pi / 2          # k = 0 at the bottom centre
            cth, sth = math.cos(th), math.sin(th)
            lat = a_ * np.sign(cth) * abs(cth) ** 0.75
            hh = t_ / 2
            up = hh + hh * (np.sign(sth) * abs(sth) ** (0.55 if sth < 0 else 0.9))
            # outer side of the boot a little fuller than the inner (arch)
            lat *= 1.0 + 0.06 * np.sign(cth) * side_sgn
            q = h + sdir * x + w * lat + u * up
            if q[2] < HEEL_Z:          # heel counter behind the contact point: flat on the floor, not into it
                q[2] = HEEL_Z + (HEEL_Z - q[2]) * 0.15
            ring.append(q)
        rings.append(ring)
    rings = np.array(rings)
    n = len(rings)
    idx = [[mb.vert(rings[i, k], {}) for k in range(ns)] for i in range(n)]
    for i in range(n - 1):
        for k in range(ns):
            k2 = (k + 1) % ns
            # bottom quads and the first band up the side: sole
            mat = L_SOLE if (k <= 2 or k >= ns - 3) else L_BOOT
            mb.face((idx[i][k], idx[i][k2], idx[i + 1][k2], idx[i + 1][k]),
                    [(k / ns, xs[i] * 4), ((k + 1) / ns, xs[i] * 4), ((k + 1) / ns, xs[i + 1] * 4), (k / ns, xs[i + 1] * 4)], mat)
    for end, sign in ((0, -1), (n - 1, 1)):
        cen = rings[end].mean(axis=0) + sdir * 0.004 * sign
        pole = mb.vert(cen, {})
        for k in range(ns):
            k2 = (k + 1) % ns
            f = (idx[end][k], idx[end][k2], pole) if sign > 0 else (pole, idx[end][k2], idx[end][k])
            mb.face(f, [(0, 0), (1, 0), (0.5, 1)], L_SOLE if (k <= 2 or k >= ns - 3) else L_BOOT)
    # ankle shaft: from inside the upper up along the shin, collar with an orange line
    ankle = h + sdir * 0.055 + u * 0.085
    return ankle


def boot_shaft(mb, ankle, knee, side_sgn):
    d = nrm(knee - ankle)
    ts = [-0.02, 0.01, 0.040, 0.046, 0.07, 0.10, 0.13]      # along the shin from the ankle; 6 mm orange line
    C = np.array([ankle + d * t for t in ts])
    T, LAT, DOR = frames_along(C, lambda i, T: np.array([1.0, 0, 0]))
    a = np.interp(ts, [-0.02, 0.04, 0.13], [0.046, 0.044, 0.044])
    b = np.interp(ts, [-0.02, 0.04, 0.13], [0.054, 0.048, 0.046])
    mb.sweep(C, LAT, DOR, a, b, 20, lambda i, k, t: L_ORANGE if i == 2 else L_BOOT, lambda i: {}, uv_scale=(1, 4))


def leg(mb, hip, knee, ankle, side_sgn):
    """Fire-suit leg: thigh from inside the seat, knee, shin, trouser hem over the boot shaft."""
    dT = nrm(knee - hip)
    dS = nrm(ankle - knee)
    start = hip - dT * 0.06
    end = ankle - dS * 0.075                     # trouser hem 7.5 cm above the ankle, over the boot shaft
    P = np.array([start, knee, end])
    C = polyline_samples(P, [14, 14], smooth_iter=5)
    n = len(C)
    hinge = nrm(np.cross(knee - hip, ankle - knee))
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    sK = s[np.argmin(np.linalg.norm(C - knee, axis=1))]
    T, LAT, DOR = frames_along(C, lambda i, T: np.array([-1.0, 0, 0]))
    # stripe (texture u 0.5) on the outer side of the leg
    want = np.array([float(side_sgn), 0.0, 0.25])
    mid = n // 3
    tw = math.atan2(want.dot(DOR[mid]), want.dot(LAT[mid]))
    u0 = tw / (2 * math.pi) - 0.5
    a = np.interp(s, [0, 0.10, sK - 0.16, sK, sK + 0.18, s[-1] - 0.05, s[-1]], [0.078, 0.076, 0.064, 0.055, 0.052, 0.050, 0.058])
    b = np.interp(s, [0, 0.10, sK - 0.16, sK, sK + 0.18, s[-1] - 0.05, s[-1]], [0.070, 0.068, 0.060, 0.058, 0.053, 0.048, 0.056])
    rng = np.random.default_rng(11 if side_sgn < 0 else 12)
    ph = rng.uniform(0, 2 * math.pi, 4)
    inner = nrm((hip + ankle) / 2 - knee)        # inside of the knee bend (down)

    def disp(i, t):
        out = LAT[i] * math.cos(t) + DOR[i] * math.sin(t)
        d = 0.0
        dk = s[i] - sK
        ins = out.dot(inner)
        if abs(dk) < 0.11:
            env = 0.5 * (1 + math.cos(math.pi * dk / 0.11))
            if ins > 0:      # folds behind the knee
                d -= 0.006 * env * ins * (0.5 + 0.5 * math.cos(2 * math.pi * dk / 0.035 + math.cos(t)))
            else:            # knee cap: the suit drawn tight over it
                d += 0.006 * env * (-ins) ** 2
        # loose fabric
        d += 0.0012 * math.sin(2 * math.pi * s[i] / 0.13 + 2 * t + ph[0]) * math.sin(t + ph[1])
        # bunching above the boot
        de = s[-1] - s[i]
        if de < 0.09:
            d += 0.0025 * (1 - de / 0.09) * (0.5 + 0.5 * math.sin(2 * math.pi * de / 0.03 + 3 * t + ph[2]))
        return d
    mb.sweep(C, LAT, DOR, a, b, 22, lambda i, k, t: L_SUIT, lambda i: {}, uv_scale=(1, 1 / 0.8), disp=disp,
             cap_start=True, u0=u0)


def two_bone(A, B, L1, L2, pole):
    d = np.linalg.norm(B - A)
    to = (B - A) / d
    d2 = min(d, L1 + L2 - 1e-4)
    a = (L1 * L1 - L2 * L2 + d2 * d2) / (2 * d2)
    hh = math.sqrt(max(0.0, L1 * L1 - a * a))
    pl = np.asarray(pole, dtype=float)
    pl = nrm(pl - to * pl.dot(to))
    return A + to * a + pl * hh, d


def build_legs():
    mb = MeshBuilder()
    info = {}
    for side, pad, pitch, toe in (('L', DEAD_PEDAL, 32.0, 12.0), ('R', THROTTLE, 38.0, 3.0)):
        sg = -1 if side == 'L' else 1
        h, sdir, w, u = foot_frame(pad, pitch, toe, side_sgn=sg)
        ankle = boot(mb, h, sdir, w, u, sg)
        hip = np.array([-spec.SEAT_X + sg * HIP_X, spec.SEAT_H_POINT_Y + 0.01, spec.SEAT_H_POINT_Z])
        knee, dist = two_bone(hip, ankle, L_THIGH, L_SHIN, (0.22 * sg, 0.0, 1.0))
        boot_shaft(mb, ankle, knee, sg)
        leg(mb, hip, knee, ankle, sg)
        info[side] = dict(hip=hip.round(3).tolist(), knee=knee.round(3).tolist(), ankle=ankle.round(3).tolist(),
                          heel=h.round(3).tolist(), reach=round(float(dist), 3))
    return mb, info


# ------------------------------------------------------------------ textures
def suit_textures():
    """Nomex fire-suit fabric with an orange accent line (u = 0.5) and stitching."""
    from PIL import Image
    W, H = 512, 1024
    rng = np.random.default_rng(3)
    y, x = np.mgrid[0:H, 0:W]
    # twill weave height
    weave = 0.5 + 0.25 * np.sin((x + y) * math.pi / 2.0) + 0.25 * np.sin((x - 2 * y) * math.pi / 3.0)
    noise = rng.normal(0, 1, (H // 8, W // 8))
    noise = np.kron(noise, np.ones((8, 8)))
    from PIL import ImageFilter
    nimg = Image.fromarray(((noise - noise.min()) / np.ptp(noise) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4))
    noise = np.asarray(nimg).astype(float) / 255
    base = np.zeros((H, W, 3))
    # (r6: #1c1d20, was #151515 - the sleeves read as a black hole; weave in the colour .12 -> .03 and in the height .35 ->
    # .06: the 4 px twill aliased into a coarse carbon-twill moire in the game; the noise, seams, stitching and the
    # orange line stay)
    black = np.array([0.110, 0.114, 0.125])               # #1c1d20
    base[:] = black
    base *= (0.97 + 0.03 * weave[..., None]) * (0.9 + 0.2 * noise[..., None])
    u = x / W
    stripe = np.abs(u - 0.5) < 0.008                     # one thin orange line (~5 mm)
    base[stripe] = np.array([1.0, 0.36, 0.06]) * (0.92 + 0.08 * weave[stripe][:, None])
    # dark piping edges + grey stitching either side of the stripe
    edge = (np.abs(u - 0.5) >= 0.008) & (np.abs(u - 0.5) < 0.0105)
    base[edge] = black * 0.6
    stitch = (np.abs(np.abs(u - 0.5) - 0.022) < 0.0022) & ((y // 6) % 2 == 0)
    base[stitch] = np.array([0.20, 0.20, 0.21])
    # side seam with stitching at u = 0 / 1
    seam = (np.minimum(u, 1 - u) < 0.004)
    base[seam] = black * 0.55
    stitch2 = (np.abs(np.minimum(u, 1 - u) - 0.012) < 0.002) & ((y // 6) % 2 == 0)
    base[stitch2] = np.array([0.22, 0.23, 0.25])
    img = Image.fromarray((np.clip(base, 0, 1) ** (1 / 1.0) * 255).astype(np.uint8))
    img.save(os.path.join(TEX, 'arms_suit_base.jpg'), quality=88)
    # normal map from a height field
    h = 0.06 * weave + 0.4 * noise
    h += np.where(stitch | stitch2, 0.8, 0.0)
    h -= np.where(edge | seam, 0.6, 0.0)
    h += np.where(stripe, 0.25, 0.0)
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.9
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.9
    nz = np.ones_like(h)
    nm = np.stack([-gx, gy, nz], -1)
    nm /= np.linalg.norm(nm, axis=-1, keepdims=True)
    Image.fromarray(((nm * 0.5 + 0.5) * 255).astype(np.uint8)).save(os.path.join(TEX, 'arms_suit_normal.jpg'), quality=92)


def glove_textures():
    """(r5) arms_glove_normal.jpg: leather grain + fine creases across the fingers (glove UVs: u around a finger /
    the palm, v = 10 x the length in m, so 1 UV = 10 cm along). Tileable."""
    from PIL import Image, ImageFilter
    W = H = 256
    rng = np.random.default_rng(21)
    def blur_noise(sigma, scale):
        n = rng.normal(0, 1, (H, W))
        n = np.concatenate([n, n], 0); n = np.concatenate([n, n], 1)          # tile-safe blur
        img = Image.fromarray(((n - n.min()) / np.ptp(n) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(sigma))
        a = np.asarray(img).astype(float)[H // 2:H // 2 + H, W // 2:W // 2 + W] / 255
        return (a - a.mean()) * scale
    h = blur_noise(0.8, 1.0) + blur_noise(2.5, 1.5)                              # pebbled grain
    y, x = np.mgrid[0:H, 0:W]
    # creases: wavy lines across v every ~5-9 mm (13-23 px), random depth
    v = y / H
    for k in range(14):
        v0 = rng.uniform(0, 1); amp = rng.uniform(0.004, 0.012); ph = rng.uniform(0, 2 * math.pi)
        dep = rng.uniform(0.6, 1.4)
        vc = v0 + amp * np.sin(2 * math.pi * x / W * rng.integers(1, 3) + ph)
        dv = (v - vc + 0.5) % 1.0 - 0.5
        h -= dep * np.exp(-(dv * H / 1.6) ** 2)
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.35
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.35
    nm = np.stack([-gx, gy, np.ones_like(h)], -1)
    nm /= np.linalg.norm(nm, axis=-1, keepdims=True)
    Image.fromarray(((nm * 0.5 + 0.5) * 255).astype(np.uint8)).save(os.path.join(TEX, 'arms_glove_normal.jpg'), quality=92)


def materials():
    suit = common.mat('Driver suit nomex', tex='arms_suit_base.jpg', normal='arms_suit_normal.jpg', normal_strength=0.8, rough=0.88)
    # (r5) leather grain / crease normal map on the glove panels; darker palm and thumb (#151517)
    glove = common.mat('Glove black', '#1c1c1e', rough=0.58, normal='arms_glove_normal.jpg', normal_strength=0.6)
    grey = common.mat('Glove charcoal panel', '#2b2c30', rough=0.62, normal='arms_glove_normal.jpg', normal_strength=0.6)
    orange = common.mat('Glove orange', '#ff5a0d', rough=0.5)
    palm = common.mat('Glove palm suede', '#151517', rough=0.95, normal='arms_glove_normal.jpg', normal_strength=0.4)
    knit = common.mat('Glove knit cuff', '#121213', rough=0.95)
    return [suit, glove, grey, orange, palm, knit]


def leg_materials():
    suit = common.mat('Driver suit nomex', tex='arms_suit_base.jpg', normal='arms_suit_normal.jpg', normal_strength=0.8, rough=0.88)
    boot_m = common.mat('Boot leather black', '#18181a', rough=0.42)
    sole = common.mat('Boot sole', '#0d0d0e', rough=0.85)
    orange = common.mat('Glove orange', '#ff5a0d', rough=0.5)
    return [suit, boot_m, sole, orange]


# ------------------------------------------------------------------ assemble
def build(args):
    common.reset_scene()
    os.makedirs(TEX, exist_ok=True)
    suit_textures()
    glove_textures()
    mats = materials()
    all_v, all_w, all_f, all_uv, all_m = [], [], [], [], []
    opened = {'L': [], 'R': []}   # per-side open positions (other side and sleeves stay put)
    grips = {}
    bones = {}
    for side in ('L', 'R'):
        ps = pose(side)
        mirror = side == 'R'
        bH = 'Hand.' + side
        w_hand = lambda i: {bH: 1.0}  # noqa: E731
        g0 = build_glove(0.0, w_hand)
        g1 = build_glove(1.0, w_hand)
        Pc = clear_rim(place(np.array(g0.v)))
        Po = place(np.array(g1.v))     # open hand (morph; the game lifts the hand off the rim)
        # glove extent along the rim (for the game's spoke clearance)
        # parts that reach inside the rim circle next to the rim (fingertips, thumb) meet the spokes
        near = np.array([rim_dist(p)[0] < 0.032 and p[1] < 0.004 for p in Pc])
        xs = Pc[near, 0]
        xmin, xmax = float(xs.min()), float(xs.max())
        if mirror:
            xmin, xmax = -xmax, -xmin
        Pw = hand_to_world(Pc, ps['M'], mirror)
        Pow = hand_to_world(Po, ps['M'], mirror)
        faces = g0.f
        if mirror:
            faces = [tuple(reversed(f)) for f in faces]
            uvs = [list(reversed(u)) for u in g0.uv]
        else:
            uvs = g0.uv
        # palm wrist end / axis in world for the cuff
        pw = hand_to_world(place(PALM_P0), ps['M'], mirror)[0]
        pk = hand_to_world(place(PALM_P1), ps['M'], mirror)[0]
        mbs = MeshBuilder()
        sleeve(mbs, ps, pw, pk - pw)
        # merge: glove then sleeve (sleeve has no morph displacement)
        base = len(all_v)
        for sd in opened:
            opened[sd] += list(Pow) if sd == side else list(Pw)
        all_v += list(Pw)
        all_w += g0.w
        all_f += [tuple(base + i for i in f) for f in faces]
        all_uv += uvs
        all_m += g0.m
        base = len(all_v)
        all_v += mbs.v
        for sd in opened:
            opened[sd] += mbs.v
        all_w += mbs.w
        all_f += [tuple(base + i for i in f) for f in mbs.f]
        all_uv += mbs.uv
        all_m += mbs.m
        grips[side] = (ps['M'], xmin, xmax)
        knuckle = hand_to_world(place(PALM_P1), ps['M'], mirror)[0]
        bones['UpperArm.' + side] = (ps['S'], ps['E'], ps)
        bones['ForeArm.' + side] = (ps['E'], ps['W'], ps)
        bones['Hand.' + side] = (ps['W'], V(knuckle), ps)

    # ---- mesh object
    me = bpy.data.meshes.new('DriverArms')
    me.from_pydata([tuple(p) for p in all_v], [], all_f)
    me.update()
    for m in mats:
        me.materials.append(m)
    me.polygons.foreach_set('material_index', all_m)
    uvl = me.uv_layers.new(name='UVMap')
    flat_uv = [c for f in all_uv for uv in f for c in uv]
    uvl.data.foreach_set('uv', flat_uv)
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new('DriverArms', me)
    bpy.context.scene.collection.objects.link(ob)

    # ---- armature (flat bones)
    arm = bpy.data.armatures.new('DriverRig')
    rig = bpy.data.objects.new('DriverRig', arm)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for name, (h, t, ps) in bones.items():
        eb = arm.edit_bones.new(name)
        eb.head = V(h)
        eb.tail = V(t)
        hinge = (ps['E'] - ps['S']).cross(ps['W'] - ps['E']).normalized()
        if name.startswith('Hand'):
            eb.align_roll(ps['R'])
        else:
            eb.align_roll(hinge)
        eb.use_deform = True
    bpy.ops.object.mode_set(mode='OBJECT')
    # skin
    for name in bones:
        ob.vertex_groups.new(name=name)
    for vi, w in enumerate(all_w):
        tot = sum(w.values())
        for bn, ww in w.items():
            if ww > 1e-4:
                ob.vertex_groups[bn].add([vi], ww / tot, 'REPLACE')
    ob.parent = rig
    mod = ob.modifiers.new('Armature', 'ARMATURE')
    mod.object = rig
    # morph target: open hands
    ob.shape_key_add(name='Basis')
    for sd in ('L', 'R'):
        sk = ob.shape_key_add(name='Open' + sd)
        sk.data.foreach_set('co', np.array(opened[sd], dtype=np.float32).ravel())
        sk.value = 0.0

    # ---- legs (static mesh, same frame as the arms' rest pose)
    lmb, linfo = build_legs()
    lme = bpy.data.meshes.new('DriverLegs')
    lme.from_pydata([tuple(p) for p in lmb.v], [], lmb.f)
    lme.update()
    for m in leg_materials():
        lme.materials.append(m)
    lme.polygons.foreach_set('material_index', lmb.m)
    luv = lme.uv_layers.new(name='UVMap')
    luv.data.foreach_set('uv', [c for f in lmb.uv for uv in f for c in uv])
    for p in lme.polygons:
        p.use_smooth = True
    legs_ob = bpy.data.objects.new('DriverLegs', lme)
    legs_ob['eye'] = list(spec.DRIVER_EYE)
    bpy.context.scene.collection.objects.link(legs_ob)
    lme.calc_loop_triangles()
    print('legs: triangles', len(lme.loop_triangles), linfo)

    # ---- grip empties (rest grip frames) with the glove extents as extras
    for side, (M, xmin, xmax) in grips.items():
        e = bpy.data.objects.new('Grip.' + side, None)
        e.empty_display_size = 0.05
        e.matrix_world = M
        e['grip_x_min'] = round(xmin, 4)
        e['grip_x_max'] = round(xmax, 4)
        e['rim_r'] = RIM_R
        e['rim_t'] = RIM_T
        bpy.context.scene.collection.objects.link(e)

    me.calc_loop_triangles()
    tris = len(me.loop_triangles) + len(lme.loop_triangles)
    print('arms: vertices', len(me.vertices), 'triangles', tris)
    for side, (M, xmin, xmax) in grips.items():
        print('grip', side, 'x extent', round(xmin, 4), round(xmax, 4))
    if args.blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend), compress=True)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=args.out, export_format='GLB', export_yup=True, export_apply=False,
                              export_texcoords=True, export_normals=True, export_materials='EXPORT',
                              export_skins=True, export_morph=True, export_morph_normal=True,
                              export_animations=False, export_extras=True, export_cameras=False,
                              export_lights=False, export_image_format='AUTO')
    print('exported', args.out, os.path.getsize(args.out) // 1024, 'KB')
    return tris


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--blend', default=os.path.join(ROOT, 'out', 'part_arms.blend'))
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    build(a)
