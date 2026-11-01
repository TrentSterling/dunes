"""Part 'body': every carbon body panel of the GLX pro sand car.

Built for the LEFT side (x < 0) and mirrored:
  * front clip: low pointed hood with a centre ridge, hood/fender creases, raised fender crowns that
    cover the upper front frame rails, a rolled brow over the shock towers, the flat front faces of the
    side cheeks that wrap down beside the front shocks (front.png), three meshed cowl vents;
  * slab doors with a rounded sill cap at BELT_Z, tumblehome crease, rolled shut lines;
  * tall rear side pods rising from the belt behind the door to REAR_DECK_Z, open "scoop" over the rear
    shock tops, carbon pod deck + inner wall beside the engine bay, diagonal rolled lower edge over the
    rear paddle tyre, squared tail block with a pocket for the chassis tail light;
  * roof skin with the striped rear spoiler, carbon A-pillar mirrors, black belly pan / skid plates.

Panels are structured quad grids (rows along the car, columns around the section) whose free edges are
finished with a rolled return (radius + skirt), then given 4 mm thickness with a Solidify modifier.
Outside faces use M('livery') + side_uv (sides) or M('livery_top') + top_uv (tops); the inside of every
panel and the rolled edges' backs are M('carbon') with a 1 UV-unit-per-metre box mapping.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector, Matrix

from common import M, mat, obj_from_bmesh, side_uv, top_uv, apply_transform, aligned_matrix
import spec

V = Vector
BW = spec.BODY_WIDTH / 2.0          # 0.81 half width of doors / pods
THICK = 0.004                       # carbon panel thickness
GAP = 0.0055                        # shut-line gap

# ------------------------------------------------------------------ small math

def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def spline(pts, x):
    """Monotone-ish Catmull-Rom through [(x, y), ...] sorted by x; clamps outside."""
    xs = [p[0] for p in pts]
    if x <= xs[0]:
        return pts[0][1]
    if x >= xs[-1]:
        return pts[-1][1]
    k = max(i for i in range(len(xs) - 1) if xs[i] <= x)
    x0, x1 = xs[k], xs[k + 1]
    y0, y1 = pts[k][1], pts[k + 1][1]

    def slope(i):
        if i <= 0:
            return (pts[1][1] - pts[0][1]) / (xs[1] - xs[0])
        if i >= len(xs) - 1:
            return (pts[-1][1] - pts[-2][1]) / (xs[-1] - xs[-2])
        return (pts[i + 1][1] - pts[i - 1][1]) / (xs[i + 1] - xs[i - 1])
    m0, m1 = slope(k), slope(k + 1)
    h = x1 - x0
    t = (x - x0) / h
    h00 = 2 * t ** 3 - 3 * t ** 2 + 1
    h10 = t ** 3 - 2 * t ** 2 + t
    h01 = -2 * t ** 3 + 3 * t ** 2
    h11 = t ** 3 - t ** 2
    return h00 * y0 + h10 * h * m0 + h01 * y1 + h11 * h * m1


def hermite(z0, z1, s0, s1, h, t):
    """Cubic from z0 (slope s0) to z1 (slope s1) over a span h, at fraction t."""
    h00 = 2 * t ** 3 - 3 * t ** 2 + 1
    h10 = t ** 3 - 2 * t ** 2 + t
    h01 = -2 * t ** 3 + 3 * t ** 2
    h11 = t ** 3 - t ** 2
    return h00 * z0 + h10 * h * s0 + h01 * z1 + h11 * h * s1


def pchip(xk, zk, x, m_start=None):
    """Monotone (Fritsch-Carlson) cubic through any number of knots; m_start optionally fixes the start slope."""
    n = len(xk)
    h = [xk[i + 1] - xk[i] for i in range(n - 1)]
    d = [(zk[i + 1] - zk[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    for i in range(1, n - 1):
        if d[i - 1] * d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def end(d0, d1, h0, h1):
        mm = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
        if mm * d0 <= 0:
            return 0.0
        if d0 * d1 <= 0 and abs(mm) > 3 * abs(d0):
            return 3 * d0
        return mm
    m[0] = end(d[0], d[1], h[0], h[1]) if n > 2 else d[0]
    m[-1] = end(d[-1], d[-2], h[-1], h[-2]) if n > 2 else d[-1]
    if m_start is not None:
        m[0] = max(-3 * abs(d[0]), min(3 * abs(d[0]), m_start)) if d[0] else 0.0
    if x <= xk[0]:
        return zk[0]
    if x >= xk[-1]:
        return zk[-1]
    k = max(i for i in range(n - 1) if xk[i] <= x)
    return hermite(zk[k], zk[k + 1], m[k], m[k + 1], h[k], (x - xk[k]) / h[k])


def smax(a, b, k=0.01):
    """Smooth maximum (C1; adds at most k/2 where a == b)."""
    return 0.5 * (a + b + math.sqrt((a - b) ** 2 + k * k))


def smin(a, b, k=0.01):
    return 0.5 * (a + b - math.sqrt((a - b) ** 2 + k * k))


def ramp(t, w):
    """C1 ramp: 0 for t <= 0, quadratic blend over w, then slope 1 (t - w / 2)."""
    if t <= 0.0:
        return 0.0
    return t * t / (2.0 * w) if t < w else t - 0.5 * w


def unit(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-12)


# ------------------------------------------------------------------ [fix r3] plan-view body widths
# The skin follows the arbiter's half-width tables (spec.FRONT_CLIP_HALF_W / FRONT_CLIP_LOWER_HALF_W /
# REAR_POD_HALF_W): 0.81 only from the pods' front (y -0.95) to y +0.30, tapering into a narrow beak at the
# front and to TAIL_HALF_W at the tail. Monotone cubics through the knots (no steps, no overshoot).

def _pchip_tab(tab, y):
    tab = sorted(tab)
    return pchip([k[0] for k in tab], [k[1] for k in tab], y)


W_UP_TAB = list(spec.REAR_POD_HALF_W) + [(spec.FRONT_CLIP_HALF_W[0][0], BW)] + list(spec.FRONT_CLIP_HALF_W[1:])
# lower band (z 0.6-0.75): spec FRONT_CLIP_LOWER_HALF_W where the cage and the cockpit trim allow it.
# [fix r4] with the A-pillar foot at x -0.63 the windshield-hoop leg (foot -> frame rail (-0.70, 0.82, 0.50)) only
# reaches the lower band at y 0.76-0.82 (outer surface |x| 0.673 @ z 0.9 .. 0.715 @ z 0.55). What holds the lower door
# out now is interior.py's door card (|x| 0.721 @ z 0.55 .. 0.741 @ z 0.9, y <= 0.79) and, at the sill, the frame rail
# (outer surface 0.7254 + 3 mm air + the 15 / 10 mm bottom roll): 0.75 instead of r3's 0.765 at y 0.6 (spec 0.71 @ 0.5,
# 0.67 @ 0.7 is still a conflict)
W_LOW_TAB = [(0.30, BW), (0.55, 0.756), (0.68, 0.750), (0.86, 0.749), (0.97, 0.672)] + \
    [p for p in spec.FRONT_CLIP_LOWER_HALF_W if p[0] >= 1.1]
TUMBLE = 0.018                      # tumblehome of the top edge (x inset of the cap / shoulder start)
# [fix r4] side bulge at the front of the door. r3 needed it for the windshield-hoop leg (foot at x -0.72); the foot is
# now at x -0.63, 9 cm inboard. It stays for interior.py's door card, whose outer face runs at |x| 0.744-0.751 right up
# to its top (z 1.054) as far forward as y 0.76 while FRONT_CLIP_HALF_W narrows to 0.741 there: the tumblehome is taken
# out and the side kept APF_WIDEN wider so the 4 mm skin keeps 3 mm of air over the card. Fades out before the shut line.
APF_WIDEN = 0.0075


def apf_bump(y):
    return smooth((y - 0.58) / 0.08) * (1.0 - smooth((y - 0.775) / 0.055))


def tumble(y):
    return TUMBLE * (1.0 - apf_bump(y))


def w_up(y):
    """Half-width of the body side at belt / crown height (z ~0.9-1.1)."""
    return _pchip_tab(W_UP_TAB, y) + APF_WIDEN * apf_bump(y)


def w_low(y):
    """Half-width of the body side in the lower band (z 0.6-0.75)."""
    if y <= W_LOW_TAB[0][0]:
        return w_up(y)
    return _pchip_tab(W_LOW_TAB, y)


# [fix r3] the bottom 12-15 cm of the doors / rockers / pod fronts roll inward ~4.5 cm (dark tucked band with
# the GLX logo): quarter-ellipse from z 0.66 down to 0.55, then nearly vertical to the sill
TUCK_D, TUCK_Z0, TUCK_ZK = 0.045, 0.55, 0.675


def tuck(z):
    if z >= TUCK_ZK:
        return 0.0
    if z >= TUCK_Z0:
        return TUCK_D * smooth((TUCK_ZK - z) / (TUCK_ZK - TUCK_Z0))
    return TUCK_D + 0.04 * (TUCK_Z0 - z)


def tuck_w(y):
    """The tuck fades out toward the front of the door, where the lower band already narrows."""
    return 1.0 - smooth((y - 0.25) / 0.35)


def pod_side_x(y, z):
    """x of the left body side (outer skin) at station y, height z, below the tumblehome crease (rear pods; the r5
    door formula)."""
    wl, wu = w_low(y), w_up(y)
    b = smooth((z - 0.75) / 0.17)
    return -(wl + (wu - wl) * b - tuck(z) * tuck_w(y))


# ------------------------------------------------------------------ [fix r6] inset door, pod step, door pocket
# arbiter r6 (front_3q / rear_3q / rear_wheel_sidepod): the door's outer surface is INSET to X_DOOR, so the rear pod's
# leading edge (still at REAR_POD_HALF_W 0.81) becomes a forward-facing step ~4 cm proud at y ~-0.62 with a rolled lip
# (R STEP_R) from the sill to the pod top. The door carries a pressed POCKET (rounded rectangle, PK_D deep, crisp outer
# edge, soft inner fillet) under a crisp horizontal crease (DOOR_CREASE_Z) that runs the length of the door; above the
# crease a narrow top band leans in (TB_IN) to a narrow sill cap. Photo check (front_3q lit pocket u 395-512 / rear_3q
# crisp rear edge and bottom ledge, both with solved cameras): pocket y -0.18..+0.58, z 0.78..1.045 (the arbiter's
# y -0.42..+0.35 front edge has no photo feature). Ahead of y 0.40 the section blends into the spec r6 front lower-corner
# tuck (FRONT_CORNER_HALF_W_Z, held from y 0.70 to the shut line and on to the fender's rear end).
X_DOOR = 0.770                         # door outer |x| (pod 0.81 -> 4 cm step)
Y_STEP = -0.622                        # front face of the pod's leading-edge lip
STEP_R = 0.010                         # lip radius
STEP_GAP = 0.005                       # lip return -> door skin
TUCK_D_DOOR = 0.026                    # bottom tuck of the door (its bottom edge stays outboard of the frame rail)
DOOR_CREASE_Z = 1.045                  # crease along the door = the pocket's top edge
TB_IN = 0.006                          # top band lean (tumblehome) above the crease
PK_Y, PK_Z, PK_R, PK_D = (-0.180, 0.580), (0.780, DOOR_CREASE_Z), 0.045, 0.020
PK_D_BOT = 0.014                       # the floor tilts back a little: deepest under the crease
PK_W = (0.014, 0.010, 0.006)           # pocket wall widths: front / rear sides, bottom, top (crisp)
CAP_RO_REAR, CAP_RI = 0.009, 0.006     # door cap outer round (grows to CAP_RO_FRONT) / inner round
# front lower-corner tuck (spec r6), 3 mm inside the photo outline
_FC = sorted(spec.FRONT_CORNER_HALF_W_Z)
FC_Z, FC_U = [k[0] for k in _FC], [k[1] - 0.003 for k in _FC]
# plan width at belt height ahead of the door's straight part (spec FRONT_CLIP_HALF_W past y 0.70)
W_FRONT_TAB = [(0.30, X_DOOR + 0.004), (0.45, X_DOOR + 0.002), (0.70, 0.746)] + \
    [p for p in spec.FRONT_CLIP_HALF_W if p[0] > 0.80]


def corner_u(z):
    """|x| of the spec r6 front lower-corner outline at height z (linear past the end knots)."""
    if z < FC_Z[0]:
        return FC_U[0] + (FC_U[1] - FC_U[0]) / (FC_Z[1] - FC_Z[0]) * (z - FC_Z[0])
    if z > FC_Z[-1]:
        return FC_U[-1] + (FC_U[-1] - FC_U[-2]) / (FC_Z[-1] - FC_Z[-2]) * (z - FC_Z[-1])
    return pchip(FC_Z, FC_U, z)


def w_front(y):
    return _pchip_tab(W_FRONT_TAB, y)


def zb_door(y):
    """Bottom edge (before the roll) of the door: SILL_Z + roll, rising 3 cm ahead of y 0.30 where the tucked front
    corner passes over the frame rail (rail top 0.525 at |x| 0.675-0.725)."""
    return spec.SILL_Z + ROLL_SILL + 0.030 * smooth((y - 0.30) / 0.18)


def door_u(y, z):
    """|x| of the door / fender-rear side skin below the crease, without the pocket: the straight inset door (vertical at
    X_DOOR, bottom tuck TUCK_D_DOOR) blending from y 0.40 into the front lower-corner tuck (min of FRONT_CORNER_HALF_W_Z
    and the plan width w_front, smooth)."""
    u_std = X_DOOR - TUCK_D_DOOR / TUCK_D * tuck(z)
    b = smooth((y - 0.40) / 0.30)
    if b <= 0.0:
        return u_std
    u_fr = smin(corner_u(z), w_front(y), 0.012)
    return lerp(u_std, u_fr, b)


def rail_u(y):
    """|x| of the chassis belt rail centre (A_PILLAR_FOOT -> B_PILLAR_FOOT, straight)."""
    (xa, ya, _), (xb, yb, _) = spec.A_PILLAR_FOOT, spec.B_PILLAR_FOOT
    return -(xb + (xa - xb) * (y - yb) / (ya - yb))


def cap_ro(y):
    """Outer radius of the door cap at station y."""
    return lerp(CAP_RO_REAR, CAP_RO_FRONT, smooth((y - 0.52) / 0.30))


def door_flare(y):
    """Extra width the top of the door needs at its rear end: the cap's inner flank stays >= 3.3 cm outboard of the
    belt rail centre (interior.py wraps a leather roll round the rail and tucks its skirt inside the flank)."""
    need = rail_u(y) + 0.033 + cap_ro(y) + CAP_RI + 0.002
    base = door_u(y, DOOR_CREASE_Z) - TB_IN
    return max(0.0, smax(base, need, 0.008) - base)


def door_xt(y):
    """|x| where the door cap's outer round starts (top of the top band)."""
    return door_u(y, DOOR_CREASE_Z) - TB_IN + door_flare(y)


def pocket(y, z):
    """Depth of the door pocket at (y, z): rounded rectangle (PK_Y x PK_Z, corner R PK_R); the wall profile is crisp at
    the outer edge and fillets softly into the floor, its width PK_W depends on the edge (sides / bottom / top)."""
    y0, y1 = PK_Y
    z0, z1 = PK_Z
    if not (y0 - 1e-6 < y < y1 + 1e-6 and z0 - 1e-6 < z < z1 + 1e-6):
        return 0.0
    cy, cz, hy, hz = 0.5 * (y0 + y1), 0.5 * (z0 + z1), 0.5 * (y1 - y0), 0.5 * (z1 - z0)
    qy, qz = abs(y - cy) - (hy - PK_R), abs(z - cz) - (hz - PK_R)
    if qy > 0 and qz > 0:
        L = math.hypot(qy, qz)
        d, gy, gz = L - PK_R, qy / L, qz / L
    elif qy > qz:
        d, gy, gz = qy - PK_R, 1.0, 0.0
    else:
        d, gy, gz = qz - PK_R, 0.0, 1.0
    if d >= 0:
        return 0.0
    wz = PK_W[2] if z > cz else PK_W[1]
    w = PK_W[0] * gy * gy + wz * gz * gz
    t = min(1.0, -d / w)
    return lerp(PK_D_BOT, PK_D, (z - z0) / (z1 - z0)) * (1.0 - (1.0 - t) ** 2)


def door_side_u(y, z):
    """|x| of the door skin at (y, z) up to the cap start: side (+ the rear-end flare's lower part) with the pocket,
    then above the crease the straight top band to door_xt."""
    zc = DOOR_CREASE_Z
    F = door_flare(y)
    if z <= zc:
        return door_u(y, z) + 0.55 * F * smooth((z - 0.86) / (zc - 0.86)) - pocket(y, z)
    u0 = door_u(y, zc) + 0.55 * F
    z1 = door_top(y) - cap_ro(y)
    t = min(1.0, (z - zc) / max(z1 - zc, 1e-4))
    return u0 + (door_xt(y) - u0) * t


def side_x(y, z):
    """x of the left body side (outer skin) at station y, height z: the r6 inset door ahead of the pod step, the pod's
    side behind it."""
    if y > POD_Y[1] + 0.001:
        return -door_side_u(y, z)
    return pod_side_x(y, z)


# ------------------------------------------------------------------ structured grid surfaces

def grid_normals(P):
    """Per-vertex normals of a grid P[j, i] following the face winding (dPi x dPj)."""
    dPi = np.gradient(P, axis=1)
    dPj = np.gradient(P, axis=0)
    return unit(np.cross(dPi, dPj))


DBG = {}                               # last grids before the rolls (fairness checks)


def fair_grid(P, iters=8, wj=1.0, wi=0.35, lam=0.55, mu=-0.58, pin=1, row_w=None, col_w=None):
    """[fix r6] Boundary-pinned Taubin (lambda | mu) fairing of a structured grid P[j, i]: each interior point moves
    along its normal only (the parameterisation does not drift) toward the spacing-weighted chord of its neighbours
    in j (weight wj) and i (weight wi). Removes section-to-section wobble (zebra bullseyes) and keeps the overall
    curvature (mu step). row_w / col_w: optional per-row / per-column 0..1 masks (0 = frozen)."""
    P = np.array(P, float)
    nj, ni, _ = P.shape
    m = np.ones((nj, ni))
    m[:pin], m[-pin:], m[:, :pin], m[:, -pin:] = 0.0, 0.0, 0.0, 0.0
    if row_w is not None:
        m *= np.asarray(row_w, float)[:, None]
    if col_w is not None:
        m *= np.asarray(col_w, float)[None, :]
    m = m[..., None]

    def chord_res(Q, axis):
        a = np.linalg.norm(np.diff(Q, axis=axis), axis=-1)
        if axis == 0:
            da, db = a[:-1, :, None], a[1:, :, None]
            prv, nxt, mid = Q[:-2], Q[2:], Q[1:-1]
        else:
            da, db = a[:, :-1, None], a[:, 1:, None]
            prv, nxt, mid = Q[:, :-2], Q[:, 2:], Q[:, 1:-1]
        s = np.maximum(da + db, 1e-9)
        res = (db * prv + da * nxt) / s - mid
        R = np.zeros_like(Q)
        if axis == 0:
            R[1:-1] = res
        else:
            R[:, 1:-1] = res
        return R

    for _ in range(iters):
        for f in (lam, mu):
            N = grid_normals(P)
            L = wj * chord_res(P, 0) + wi * chord_res(P, 1)
            P = P + f * m * (L * N).sum(-1, keepdims=True) * N / (wj + wi)
    return P


def grid_fairness(P, axis=0):
    """RMS change of the normal curvature between neighbouring points along an axis (smaller = fairer)."""
    N = grid_normals(P)
    Q = P if axis == 0 else np.transpose(P, (1, 0, 2))
    Nq = N if axis == 0 else np.transpose(N, (1, 0, 2))
    a = np.linalg.norm(np.diff(Q, axis=0), axis=-1)
    d2 = (Q[2:] - Q[1:-1]) / np.maximum(a[1:], 1e-9)[..., None] - (Q[1:-1] - Q[:-2]) / np.maximum(a[:-1], 1e-9)[..., None]
    k = (d2 * Nq[1:-1]).sum(-1) / np.maximum(0.5 * (a[1:] + a[:-1]), 1e-9)
    dk = np.diff(k, axis=0)
    return float(np.sqrt((dk[1:-1, 1:-1] ** 2).mean()))


def _roll_j1(P, r, h, n_arc=4, n_skirt=1, hem=0.0, n_hem=3):
    """Append a rolled return to the last row of P: 90 deg arc of radius r curling inward (-N), a straight
    skirt of length h, optionally a small 180 deg hem back under the panel."""
    nj, ni, _ = P.shape
    N = grid_normals(P)[-1]
    P0 = P[-1]
    T = P[-1] - P[-2]
    T = T - (T * N).sum(-1, keepdims=True) * N
    T = unit(T)
    r = np.broadcast_to(np.asarray(r, float), (ni,))[:, None]
    h = np.broadcast_to(np.asarray(h, float), (ni,))[:, None]
    rows = []
    for k in range(1, n_arc + 1):
        a = 0.5 * math.pi * k / n_arc
        rows.append(P0 + r * math.sin(a) * T - r * (1 - math.cos(a)) * N)
    Q = P0 + r * T - r * N
    for k in range(1, n_skirt + 1):
        rows.append(Q - N * np.maximum(h, 0.002) * (k / n_skirt))
    if hem > 0:
        Qe = Q - N * np.maximum(h, 0.002)
        C = Qe - hem * T
        for k in range(1, n_hem + 1):
            a = math.pi * k / n_hem
            rows.append(C + hem * (math.cos(a) * T - math.sin(a) * N))
    return np.concatenate([P, np.array(rows)], axis=0)


def roll(P, side, r, h, **kw):
    """Rolled edge on one boundary of the grid: side in 'j0', 'j1', 'i0', 'i1'."""
    if side == 'j1':
        return _roll_j1(P, r, h, **kw)
    if side == 'j0':
        return _roll_j1(P[::-1, ::-1], np.asarray(r)[::-1] if np.ndim(r) else r,
                        np.asarray(h)[::-1] if np.ndim(h) else h, **kw)[::-1, ::-1]
    if side == 'i1':
        Q = np.transpose(P, (1, 0, 2))[:, ::-1]          # (ni, nj) with winding kept
        Q = _roll_j1(Q, np.asarray(r)[::-1] if np.ndim(r) else r, np.asarray(h)[::-1] if np.ndim(h) else h, **kw)
        return np.transpose(Q[:, ::-1], (1, 0, 2))
    if side == 'i0':
        Q = np.transpose(P, (1, 0, 2))[::-1]
        Q = _roll_j1(Q, r, h, **kw)
        return np.transpose(Q[::-1], (1, 0, 2))
    raise ValueError(side)


def grid_bmesh(P, bm=None, mat_fn=None):
    """Quads from grid P[j, i] (winding dPi x dPj). mat_fn(center, normal) -> material index."""
    bm = bm or bmesh.new()
    nj, ni, _ = P.shape
    vs = [[bm.verts.new(V(P[j, i])) for i in range(ni)] for j in range(nj)]
    for j in range(nj - 1):
        for i in range(ni - 1):
            q = [vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]]
            co = [v.co for v in q]
            if min((co[k] - co[(k + 1) % 4]).length for k in range(4)) < 1e-7:
                continue
            try:
                f = bm.faces.new(q)
            except ValueError:
                continue
            if mat_fn:
                f.normal_update()
                f.material_index = mat_fn(f.calc_center_median(), f.normal)
    return bm


def orient(P, out_dir):
    """Flip the grid's column order if its winding normal points away from out_dir (vector or fn)."""
    N = grid_normals(P)
    if callable(out_dir):
        d = np.array([[out_dir(P[j, i]) for i in range(P.shape[1])] for j in range(P.shape[0])])
    else:
        d = np.broadcast_to(np.asarray(out_dir, float), P.shape)
    if (N * d).sum() < 0:
        return P[:, ::-1].copy()
    return P


def _cage_tubes():
    """Left-side cage tube centre lines that run just under the skin (spec points; chassis.py builds the
    same tubes): windshield-hoop leg, belt rail, upper front rail. The A-pillar itself goes up through the
    door top and is left out."""
    a, b = spec.A_PILLAR_FOOT, spec.B_PILLAR_FOOT
    return [[(-spec.FRAME_RAIL_X, 0.82, spec.FRAME_RAIL_Z), a], [a, b], [a, T1, T2]]


def clear_tubes(P, clear=THICK + 0.003, soft=0.006):
    """[fix r3] Push grid points radially off the cage tubes so the 4 mm skin keeps `clear` - THICK of air
    (soft-max blend, so the skin bends smoothly around a tube instead of creasing). In place."""
    R = spec.CAGE_TUBE_R
    D = R + clear
    flat = P.reshape(-1, 3)
    for _ in range(2):
        for line in _cage_tubes():
            for a, b in zip(line, line[1:]):
                a = np.asarray(a, float); b = np.asarray(b, float)
                ab = b - a
                t = np.clip(((flat - a) @ ab) / (ab @ ab), 0.0, 1.0)
                c = a + t[:, None] * ab
                v = flat - c
                d = np.linalg.norm(v, axis=1)
                m = (d < D + soft) & (d > 1e-6)
                if not m.any():
                    continue
                dm = d[m]
                nd = np.where(dm < D - soft, D, D + soft / 4.0 * (1.0 + (dm - D) / soft) ** 2)
                flat[m] = c[m] + v[m] * (nd / dm)[:, None]
    P[...] = flat.reshape(P.shape)
    return P


MATS = None


def _palette(key, name, **fallback):
    """common.M(key); if one of its textures is not there yet (the textures agent regenerates them while the parts
    build), a plain stand-in with the same base texture so the body still builds."""
    try:
        return M(key)
    except Exception as e:                               # pragma: no cover - only while textures/ is incomplete
        print('[body] palette %s unavailable (%s) - using a stand-in' % (key, e))
        return mat(name + ' (stand-in)', **fallback)


def mats():
    global MATS
    if MATS is None:
        MATS = {
            'livery': _palette('livery', 'Livery', tex='livery.png', rough=0.22, clearcoat=1.0),
            'top': _palette('livery_top', 'Livery top', tex='livery_top.png', rough=0.22, clearcoat=1.0),
            'carbon': _palette('carbon', 'Carbon gloss', tex='carbon_base.png', rough=0.25, clearcoat=1.0,
                               uv_scale=(6, 6)),
            'black': M('satin_black'), 'gloss': M('gloss_black'), 'mirror': M('mirror'),
            'mesh': M('mesh_grille'), 'alu': M('alu'),
        }
    return MATS


# material slot layout used by every solidified panel (inside faces + rims all become carbon)
SLOTS = ('livery', 'top', 'carbon', 'gloss', 'black')
LIV, TOP, CARB, GLOSS, BLACK = 0, 1, 2, 3, 4


def finish(name, bm, thick=THICK, smooth_deg=48, mirror=False, merge_centre=False, special_uv=None):
    """bmesh (left side) -> object: optional mirror to the right side (merged on x=0 for centre panels),
    Solidify (inside faces + rims become carbon), UVs per material, sharp edges."""
    mt = mats()
    if mirror:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        ret = bmesh.ops.duplicate(bm, geom=geom)
        nv = [g for g in ret['geom'] if isinstance(g, bmesh.types.BMVert)]
        nf = [g for g in ret['geom'] if isinstance(g, bmesh.types.BMFace)]
        for v in nv:
            v.co.x = -v.co.x
        bmesh.ops.reverse_faces(bm, faces=nf)
        if merge_centre:
            cv = [v for v in bm.verts if abs(v.co.x) < 1e-5]
            for v in cv:
                v.co.x = 0.0
            bmesh.ops.remove_doubles(bm, verts=cv, dist=1e-5)
    slots = [mt[s] for s in SLOTS] + [mt['carbon']] * len(SLOTS)
    o = obj_from_bmesh(name, bm, slots, smooth=True, angle=smooth_deg)
    if thick > 0:
        md = o.modifiers.new('thick', 'SOLIDIFY')
        md.thickness = thick
        md.offset = -1.0
        md.use_rim = True
        md.use_even_offset = True
        md.thickness_clamp = 1.0           # [fix r3] no even-offset spikes at the tight roll folds
        md.use_thickness_angle_clamp = True
        md.material_offset = len(SLOTS)
        md.material_offset_rim = len(SLOTS)
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        old = o.data
        o.modifiers.clear()
        o.data = me
        bpy.data.meshes.remove(old)
        me.name = name
    me = o.data
    for p in me.polygons:
        if p.material_index >= len(SLOTS):
            k = p.material_index - len(SLOTS)
            p.material_index = k if k in (GLOSS, BLACK) else CARB
        elif p.material_index == LIV and p.normal.x * (1.0 if p.center.x >= 0 else -1.0) < -0.3:
            p.material_index = CARB          # [fix r3] faces turned toward the centre line never get livery
    assign_uvs(o, special=special_uv)
    set_shading(o, smooth_deg)
    return o


# [fix r2] carbon weave scale: 2.25 UV units per metre (6 tiles x 16 tows per unit -> ~4.4 mm tows), the
# same fine 3K twill as the interior. At 1 unit/m the roof underside and A-pillar trims, 0.2-0.5 m from the
# driver's eye, read as a herringbone of 4-5 cm bricks.
CARBON_UV = 2.25


def assign_uvs(o, special=None, cscale=CARBON_UV):
    """Livery -> side_uv, livery top -> top_uv, everything else -> box projection at cscale units/m."""
    me = o.data
    if 'UVMap' not in me.uv_layers:
        me.uv_layers.new(name='UVMap')
    uv = me.uv_layers['UVMap'].data
    mts = [m.name for m in me.materials]
    liv, top = mats()['livery'].name, mats()['top'].name
    for p in me.polygons:
        n = p.normal
        mname = mts[p.material_index] if p.material_index < len(mts) else ''
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if special:
                r = special(p, co, n)
                if r is not None:
                    uv[li].uv = r
                    continue
            if mname == liv:
                uv[li].uv = side_uv(co, n)
            elif mname == top:
                uv[li].uv = top_uv(co, n)
            else:
                ax = max(range(3), key=lambda k: abs(n[k]))
                if ax == 0:
                    uv[li].uv = (co.y * cscale, co.z * cscale)
                elif ax == 1:
                    uv[li].uv = (co.x * cscale, co.z * cscale)
                else:
                    uv[li].uv = (co.x * cscale, co.y * cscale)


def mark_sharp(o, pred):
    """Flag mesh edges whose two vertices satisfy pred(co_a, co_b) as sharp (after the angle pass)."""
    me = o.data
    att = me.attributes.get('sharp_edge')
    if att is None:
        att = me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    vs = me.vertices
    for e in me.edges:
        a, b = vs[e.vertices[0]].co, vs[e.vertices[1]].co
        if pred(a, b):
            att.data[e.index].value = True


def densify(poly, maxlen):
    """Closed 2D polygon with every edge split into pieces no longer than maxlen."""
    out = []
    n = len(poly)
    for i in range(n):
        a, b = np.array(poly[i], float), np.array(poly[(i + 1) % n], float)
        k = max(1, int(math.ceil(np.linalg.norm(b - a) / maxlen)))
        for j in range(k):
            out.append(tuple(a + (b - a) * (j / k)))
    return out


def set_shading(o, deg):
    me = o.data
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=math.radians(deg))
    except Exception:
        pass
    return o


def side_mat(c, n):
    """Material for body-side grids: sides livery, up-facing tops livery_top, the rest carbon."""
    if n.z > 0.62:
        return TOP
    if n.x < -0.35:
        return LIV
    return CARB


# ------------------------------------------------------------------ the body side section

UP_CREASE = 0.13          # tumblehome crease below the top edge
CAP_R = 0.0125            # radius of the rounded sill cap on doors / pods
X_TOP = -BW + TUMBLE      # x of the side skin where the cap starts at full width (18 mm tumblehome)

# [fix r4] the r3 door top rose to 1.124 and its cap widened into a flat-topped channel that wrapped over the belt rail
# (then at x -0.72 under the skin). With the A-pillar foot at x -0.63 the belt rail runs 4-12 cm inside the skin, so the
# cap is a plain rounded sill cap again (interior_driver_alt_red.png / interior_dash.png: a thin carbon door top with
# the door card right under it). The front of the door still rises to meet the fender's outer shoulder
# (spec.FENDER_SHOULDER_Z starts at 1.125 just ahead of the shut line; front_3q_right.png: one thick rounded ledge).
DOOR_FRONT_TOP = spec.FENDER_SHOULDER_Z[0][1] - 0.001
INT_CARD_TOP, INT_CARD_X = 1.054, -0.752     # interior.py door card: top and outer face (|x| 0.744-0.751, y <= 0.76)


def door_top(y):
    return spec.BELT_Z + (DOOR_FRONT_TOP - spec.BELT_Z) * smooth((y - 0.24) / 0.14)


# [fix r5] the cap's outer round grows toward the front of the door so it meets the fender's broad shoulder roll
# (front_clip SH_R ~0.03 at the shut line, no bead or crease at the shut line)
CAP_RO_FRONT = 0.028


def cap_shape(y, zt):
    """(x_in, z_fb): inner flank x and flank bottom z of the door's top cap at station y ([fix r6] narrow cap on the
    inset door: outer round cap_ro, 2 mm flat, inner round CAP_RI)."""
    xt = -door_xt(y)
    x_in = xt + cap_ro(y) + CAP_RI + 0.002
    zfb = zt - CAP_RI - 0.028
    if x_in > INT_CARD_X - 0.003:                         # flank over the door card: stop above its top
        zfb = max(zfb, min(INT_CARD_TOP + THICK + 0.004, zt - CAP_RI - 0.004))
    return x_in, zfb


def door_levels(y):
    """Fixed-count z levels of the door side from its bottom edge to the crease: the tuck, a cluster at the pocket's
    bottom edge / corners, the flat floor, a cluster under the crease (pocket top wall)."""
    zb = zb_door(y)
    z0, z1 = PK_Z
    lv = [lerp(zb, 0.70, k / 6) ** 1.0 for k in range(6)]          # tuck: zb .. 0.70 (6)
    lv += [0.735, z0 - 0.016, z0, z0 + 0.004, z0 + 0.010, z0 + 0.022, z0 + 0.040]
    lv += [0.88, 0.95]
    lv += [z1 - 0.040, z1 - 0.022, z1 - 0.012, z1 - 0.006, z1 - 0.003, z1]
    return lv


def door_profile(y):
    """(x, z) points of the left door section at station y: side levels (pocket applied), top band, narrow cap."""
    zt = door_top(y)
    ro = cap_ro(y)
    pts = [(-door_side_u(y, z), z) for z in door_levels(y)]
    zc, z1 = DOOR_CREASE_Z, zt - ro
    for t in (0.35, 0.7, 1.0):
        z = lerp(zc, z1, t)
        pts.append((-door_side_u(y, z), z))
    xt = -door_xt(y)
    x_in, zfb = cap_shape(y, zt)
    cx, cz = xt + ro, zt - ro
    for k in range(1, 6):                                  # outer quarter round
        a = math.pi - 0.5 * math.pi * k / 5
        pts.append((cx + ro * math.cos(a), cz + ro * math.sin(a)))
    cx2 = max(x_in - CAP_RI, cx + 0.001)
    pts.append((cx2, zt))                                  # flat top
    cz2 = zt - CAP_RI
    for k in range(1, 4):                                  # inner quarter round
        a = 0.5 * math.pi - 0.5 * math.pi * k / 3
        pts.append((cx2 + CAP_RI * math.cos(a), cz2 + CAP_RI * math.sin(a)))
    xf = cx2 + CAP_RI
    for f in (0.45, 1.0):
        pts.append((xf, lerp(cz2, zfb, f)))
    return pts


def side_profile(y, zb, zt, n_low=5, n_mid=7, n_up=4, top='cap', rs=0.02):
    """(x, z) points of the left body side at station y from the bottom zb to the top zt.

    top='cap': rounded sill cap rolling inward (doors, pods), ending on the inner flank (flat-topped and wider
               where it covers the belt rail at the front of the door).
    top='open': ends at the start of a shoulder arc of radius rs (fender, continues into the top skin)."""
    pts = []
    zl = zb + min(0.17, max(0.03, TUCK_ZK + 0.01 - zb))
    zc = zt - UP_CREASE
    ro = cap_ro(y)
    zend = zt - (ro if top == 'cap' else rs)
    xt = -w_up(y) + tumble(y)
    for k in range(n_low):
        t = k / n_low
        z = lerp(zb, zl, t)
        pts.append((side_x(y, z) + 0.006 * (1 - t) ** 2, z))
    for k in range(n_mid):
        z = lerp(zl, zc, k / n_mid)
        pts.append((side_x(y, z), z))
    x0 = side_x(y, zc)
    for k in range(n_up + 1):
        t = k / n_up
        z = lerp(zc, zend, t)
        pts.append((x0 + (xt - x0) * t ** 1.4, z))
    if top == 'cap':
        x_in, zfb = cap_shape(y, zt)
        cx, cz = xt + ro, zt - ro
        for k in range(1, 6):                                  # outer quarter round
            a = math.pi - 0.5 * math.pi * k / 5
            pts.append((cx + ro * math.cos(a), cz + ro * math.sin(a)))
        cz = zt - CAP_R
        cx2 = max(x_in - CAP_R, cx + 0.002)
        pts.append((cx2, zt))                                  # flat top (2 mm on a plain door cap)
        for k in range(1, 4):                                  # inner quarter round
            a = 0.5 * math.pi - 0.5 * math.pi * k / 3
            pts.append((cx2 + CAP_R * math.cos(a), cz + CAP_R * math.sin(a)))
        xf = cx2 + CAP_R
        for f in (0.45, 1.0):
            pts.append((xf, lerp(cz, zfb, f)))
    return pts


# door/pod station heights ---------------------------------------------------------------------
# [fix r6] the door's rear edge tucks just behind the pod's step face; the pod's side ends STEP_R behind the face (its
# lip roll reaches forward to Y_STEP)
DOOR_Y = (Y_STEP - 0.003, 0.86 - GAP / 2)                # door rear / front edges
POD_Y = (spec.TAIL_BLOCK_Y[1] + GAP / 2, Y_STEP - STEP_R)  # pod side rear / front edges
TAIL_Y0 = spec.TAIL_BLOCK_Y[0] + 0.006                   # tail side skin ends against the 6 mm rear face plate
ROLL_SILL = 0.015                                        # rolled bottom edge radius (visual bottom = zb - r)
ROLL_POD = 0.016
TB_Z0, TB_Z1 = spec.TAIL_BLOCK_Z

# [fix r4] visual bottom edge of the pod shell (rear_wheel_sidepod_right.png: the edge leaves the door sill just ahead
# of the trailing-arm pivot bolt at spec.R_TRAILING_PIVOT (-0.72, -0.85, 0.51) and passes over its mount box (top z 0.555 at
# y -0.80..-0.82), which stay visible under it, and sweeps up steeply and almost straight to the tail block bottom TAIL_BLOCK_Z[0], so the rear coilover and the arm
# show under it; r3 rose ~6 cm lower through y -0.9..-1.3)
POD_BOTTOM = [(-2.20, TB_Z0), (-1.86, TB_Z0), (-1.72, TB_Z0 - 0.012), (-1.50, 1.040), (-1.30, 0.955),
              (-1.10, 0.825), (-0.95, 0.705), (-0.88, 0.635), (-0.82, 0.585), (-0.78, 0.550), (-0.74, 0.515),
              (-0.70, spec.SILL_Z + 0.003), (-0.60, spec.SILL_Z)]


def pod_bottom(y):
    return _pchip_tab(POD_BOTTOM, y) + ROLL_POD


# [integration r3] rear-tyre relief: spec REAR_POD_HALF_W is still 0.79-0.80 wide at y -1.05..-1.10, where the
# front-top quadrant of the rear tyre (inner face |x| 0.782 at the paddles) rises at full bump (game: +0.30 straight
# up); its paddles buried 1-2 cm into the pod's lower front corner from ~+0.18 bump. Pull the skin in to RELIEF_X
# inside the tyre's swept circle (+ margin), blending out over RELIEF_BLEND.
RELIEF_X, RELIEF_MARGIN, RELIEF_BLEND = 0.774, 0.012, 0.085   # [r6] blend 0.045 -> 0.085, C2 falloff (zebra ring)


def tyre_relief(P):
    wx, wy, wz, wr = spec.WHEELS['RL'][:4]
    zc0, zc1 = wz, wz + spec.BUMP
    for idx in np.ndindex(P.shape[:2]):
        x, y, z = P[idx]
        if -x <= RELIEF_X or y > -0.95 or y < -1.25:
            continue
        zc = min(max(z, zc0), zc1)                    # nearest centre on the vertical bump path
        d = math.hypot(y - wy, z - zc) - (wr + RELIEF_MARGIN)
        t = min(max(d / RELIEF_BLEND, 0.0), 1.0)
        w = 1.0 - t * t * t * (t * (6.0 * t - 15.0) + 10.0)
        if w > 0:
            P[idx][0] = -((-x) - ((-x) - RELIEF_X) * w)


def side_panel(name, y0, y1, nj, zb_fn, zt_fn, front=None, rear=None, bottom=(ROLL_SILL, 0.02), ys=None,
               warp=None, post=None, profile=None):
    """Door / pod side skin between stations y0 < y1 (left side). warp(P) may adjust the grid in place.
    profile(y) -> [(x, z), ...] replaces side_profile ([fix r6] the inset door)."""
    rows = []
    ys = ys or [lerp(y0, y1, j / (nj - 1)) for j in range(nj)]
    for y in ys:
        prof = profile(y) if profile else side_profile(y, zb_fn(y), zt_fn(y))
        rows.append([(x, y, z) for (x, z) in prof])
    P = np.array(rows)
    if warp:
        warp(P)
    P = orient(P, (-1, 0, 0))
    # rolled edges: bottom (i0 after orient -> find which end is the bottom)
    bottom_side = 'i0' if P[0, 0, 2] < P[0, -1, 2] else 'i1'
    br = np.array([bottom[0](y) for y in ys]) if callable(bottom[0]) else bottom[0]
    bh = np.array([bottom[1](y) for y in ys]) if callable(bottom[1]) else bottom[1]
    P = roll(P, bottom_side, br, bh, n_arc=4)
    # [fix r3] shut-line returns: full size on the side skin, small over the cap and none on the cap's inner
    # flank (their returns used to converge inside the narrow cap and fold, spiking the solidified skin)
    Nr = grid_normals(P)

    def per_col(rh, j):
        r = np.full(P.shape[1], rh[0]); h = np.full(P.shape[1], rh[1])
        n = Nr[j]
        top = n[:, 2] > 0.45
        flank = n[:, 0] > 0.25
        r[top] = min(rh[0], 0.004); h[top] = min(rh[1], 0.006)
        r[flank] = 0.002; h[flank] = 0.0
        return r, h
    if rear:
        r, h = per_col(rear, 0)
        P = roll(P, 'j0', r, h, n_arc=3)
        Nr = grid_normals(P)
    if front:
        r, h = per_col(front, -1)
        P = roll(P, 'j1', r, h, n_arc=3)
    if post:
        post(P)
    bm = grid_bmesh(P, mat_fn=side_mat)
    return finish(name, bm, mirror=True)

# ------------------------------------------------------------------ [fix r5] front clip: short wings + raised beak
# spec r5 (GLX front_3q / front / rear_3q; the red side variant's long tall fenders are a different body): the front
# fenders are short "wings" that roll in fast ahead of the cowl. Their outer / front edge follows spec.FRONT_CLIP_HALF_W
# (0.72 @ y 0.85 -> 0.40 @ 1.30) at the crown height spec.FENDER_SHOULDER_Z (1.10 @ 0.87 -> 0.93 @ 1.30); inboard of
# |x| 0.40 the wing's front edge runs nearly transverse to the side of the narrow raised centre BEAK
# (spec.HOOD_BEAK_HALF_W, top = spec.HOOD_CENTRE_Z, sides falling 55 deg), the only panel that runs on to the nose. The
# troughs either side of the beak ahead of the wings stay OPEN (coilovers, finned reservoirs and the chassis nose tubes
# show, front.png); the r4 brow / crown_need over the shock hardware is gone (spec r5).
# Pieces (left side, mirrored):
#   body_front_clip     one grid: the fender side (matches the door at the shut line; its lower band stays outboard of
#                       interior's footwell side wall to y 1.0, then wraps inward = the broad, dark forward-facing CHEEK
#                       front.png sees under the wing, u ~380-470), a bezier shoulder roll (R 0.03 -> 0.04, no bead or
#                       crease), the wing top inward to the valley on the beak side (inner edge buried 6 mm in the beak)
#   body_beak           cowl -> nose: crowned top, R 12 mm edge, 55 deg sides, rolled bottom edge, rounded nose lip
#   body_cowl_vents     raised cowl band on the beak at the windshield base; its forward-facing slope carries the three
#                       recessed hex-mesh vents (gloss black frames, 15 mm deep) so the front camera sees them
#   body_hood_bulkhead  closing panel under the wing / beak in front of the footwell

FENDER_Y0 = 0.86 + GAP / 2            # fender rear edge (door front shut line)
COWL_Y = spec.COWL_Y + 0.06           # 0.78: cowl rear edge, clear of the windshield hoop and centre post
NOSE_Y = 1.648                        # beak tip (top surface end on the centre line)
# outer shoulder (crown) height: flat at the door top back to the shut line, then spec FENDER_SHOULDER_Z (its first knot
# (0.87, 1.10) is DOOR_FRONT_TOP + 1 mm 7 mm ahead of the shut line and is left out so the curve has no 1 mm bump)
Z_SHOULDER = [(0.70, DOOR_FRONT_TOP), (FENDER_Y0, DOOR_FRONT_TOP)] + \
    [k for k in spec.FENDER_SHOULDER_Z if k[0] > FENDER_Y0 + 0.02]
# [v2] photo triangulation (front.png + front_3q_right.png, both solved cameras, 5 points, misses 0-7 mm): the three
# cowl vents sit at y 1.07-1.11, z 1.06-1.075, x 0 / +-0.146 (mesh outer ends +-0.208): the hood is a nearly flat deck
# at the spec cowl height (1.10) from the windshield base forward to y ~1.06, where a forward-facing step carrying the
# vents drops ~5 cm on to the beak, which then follows spec HOOD_CENTRE_Z (1.04 @ 1.10 ...) to the nose. The deck is the
# vent band (BAND_H over the beak table below); the beak table behind the step only carries the band and the valley.
BEAK_ZC = [(0.70, 1.0555), (0.95, 1.0545), (1.10, 1.047), (1.20, 1.012), (1.30, 0.970), (1.55, 0.890),
           (1.64, spec.HOOD_FRONT_Z)]
# plan half width of the beak top: the step / vent face spans +-0.24 (front.png outer vent ends +-0.21 plus frames and
# the edge round; the band's steep end face sits at ~0.22-0.25), then it tapers to spec HOOD_BEAK_HALF_W 0.13 @ 1.30;
# the nose stays blunt (front.png: the nose front is a trapezoid ~+-0.13 at its top edge, ~+-0.06-0.07 at the bottom
# = spec's 0.06 "tip"; the orange stripe runs along the left top edge to the front corner, f3q / front triangulation
# x -0.14 at y ~1.66)
BEAK_HW = [(COWL_Y - 0.01, 0.255), (1.00, 0.245), (1.10, 0.238), (1.20, 0.190), (1.30, 0.145), (1.45, 0.125),
           (1.58, 0.112), (NOSE_Y + 0.012, 0.100)]
BEAK_ANG = math.radians(55.0)         # beak side slope (spec: 50-60 deg)
BEAK_RC = 0.012                       # beak top edge radius
# top crown = K(y) * hw^2 (constant curvature across): small at the windshield base, ~3 cm at the step so the outer
# vents tilt ~9 deg outboard-down as in front.png
CROWN_K = (0.10, 0.50)
# how far the beak edge stands above the wing at the valley (front.png: the wing's front edge runs down inboard to
# z ~0.86-0.88 at |x| ~0.19-0.21 where it meets the beak side)
RISE_TAB = [(0.76, 0.012), (0.88, 0.018), (1.00, 0.025), (1.10, 0.032), (1.20, 0.055), (1.30, 0.082), (1.40, 0.095),
            (1.70, 0.095)]
# depth of the beak side face below its (sharp) edge: under the valley behind the wing front edge, bottom ~0.83-0.84
# ahead of it
D_TAB = [(0.76, 0.045), (1.00, 0.058), (1.10, 0.070), (1.20, 0.090), (1.30, 0.110), (1.40, 0.106), (1.50, 0.076),
         (1.60, 0.048), (1.70, 0.040)]
WING_CROWN = 0.005                    # slight convexity of the wing top between the shoulder and the valley
# fender side, lower band (z <= ~0.88): door widths to the shut line, >= 0.666 to y 1.00 (interior int_footwell_side
# x -0.652..-0.656, y <= 1.00, z <= 0.88), then the cheek wraps inward ahead of the footwell (the front tyre at the
# game's 0.52 rad lock sweeps |x| >= 0.61 at y 1.08-1.17)
# [fix r6] convex in plan from the shut line to the cheek's leading edge (r5 held a 0.666 plateau at y 0.97-1.00 for
# interior's footwell wall: an S in every section = zebra rings on the cheek); u = 0.749 - 0.30 d - 1.81 d^2
WF_LOW_TAB = [(0.30, BW), (0.55, 0.756), (0.68, 0.750)] + \
             [(y, 0.749 - 0.30 * (y - 0.86) - 1.81 * (y - 0.86) ** 2) for y in (0.86, 0.92, 0.98, 1.04, 1.10, 1.17)]
# bottom edge of the fender side (rises along the cheek; front.png cheek bottom ~0.6)
ZB_FRONT = [(0.80, spec.SILL_Z + ROLL_SILL + 0.030), (0.88, 0.546), (0.95, 0.552), (1.05, 0.570), (1.12, 0.600),
            (1.20, 0.628)]           # [fix r6] matches zb_door at the shut line (tucked corner over the frame rail)
# leading edge of the fender side / cheek in side view, z -> y
Y_LEAD2 = [(0.40, 1.090), (0.50, 1.105), (0.57, 1.125), (0.63, 1.148), (0.70, 1.163), (0.80, 1.170), (1.00, 1.172),
           (1.20, 1.172)]
# plan view front edge of the wing top (x -> y): the outer edge is the shoulder itself (FRONT_CLIP_HALF_W); from the
# corner at |x| ~0.40 / y 1.30 it runs nearly transverse to the beak side (front.png)
FE_W = [(-0.52, 1.200), (-0.48, 1.240), (-0.44, 1.280), (-0.405, 1.304), (-0.37, 1.319), (-0.32, 1.333),
        (-0.26, 1.350), (-0.20, 1.368), (-0.15, 1.384), (-0.10, 1.398), (-0.05, 1.410)]
# cowl band: the r4 interior dash (COWL_MIN probe, y 0.764-0.80) tops out 1.08-1.113; the skin stays >= 8 mm over it at
# the windshield base, fading out by y 0.84 (interior can lower its dash to the r5 skin and this then does nothing)
COWL_NEED = [(0.0, 1.091), (0.3, 1.084), (0.4, 1.091), (0.5, 1.104), (0.6, 1.116), (0.7, 1.121), (0.8, 1.121)]


def _rear_edge():
    """Top-skin rear edge: the door shut line outboard, then (inboard of the door cap's inner flank, which runs
    nearly fore-aft at x ~-0.70) straight back to the cowl edge."""
    xf = max(cap_shape(y, door_top(y))[0] for y in np.linspace(0.78, DOOR_Y[1], 8)) + 0.006
    return [(-0.80, FENDER_Y0), (xf, FENDER_Y0), (xf + 0.005, 0.836), (xf + 0.009, 0.800),
            (xf + 0.016, COWL_Y), (0.0, COWL_Y)]


REAR_EDGE = _rear_edge()


def solve_edge(xfun, edge, y_guess):
    """y where the column's x(y) meets the plan-view edge y = edge(x)."""
    y = y_guess
    for _ in range(60):
        y_new = spline(edge, xfun(y))
        if abs(y_new - y) < 1e-7:
            break
        y = 0.5 * (y + y_new)
    return y


def smoothed_tab(tab, sigma_fn, lo, hi, step=0.002):
    """[fix r6] pchip through tab (only C1: its curvature jumps at every knot = a zebra kink across the panel), smoothed
    by a Gaussian of width sigma_fn(y) (0 = untouched) and sampled densely; returns f(y)."""
    ys = np.arange(lo - 0.15, hi + 0.15 + step / 2, step)
    zs = np.array([_pchip_tab(tab, y) for y in ys])
    out = []
    for y in ys:
        sg = sigma_fn(y)
        if sg < 1e-4:
            out.append(_pchip_tab(tab, y))
            continue
        w = np.exp(-0.5 * ((ys - y) / sg) ** 2)
        out.append(float((w * zs).sum() / w.sum()))
    out = np.array(out)
    return lambda y: float(np.interp(y, ys, out))


_Z_SHOULDER_S = smoothed_tab(Z_SHOULDER, lambda y: 0.035 * smooth((y - 0.875) / 0.06), 0.70, 1.75)


def z_shoulder(y):
    """Outer top of the fender (spec FENDER_SHOULDER_Z), meeting the door top at the shut line. [fix r6] smoothed
    (curvature continuous) ahead of y 0.875, exact at the shut line."""
    if y < 0.80:
        return _pchip_tab(Z_SHOULDER, y)
    return _Z_SHOULDER_S(y)


def z_centre(y):
    """Beak centre line top (spec HOOD_CENTRE_Z ahead of the vent step, BEAK_ZC behind it under the vent band)."""
    return _pchip_tab(BEAK_ZC, y)


def crown(y):
    return lerp(CROWN_K[0], CROWN_K[1], smooth((y - 0.80) / 0.25)) * beak_hw(y) ** 2


def beak_hw(y):
    return _pchip_tab(BEAK_HW, y)


def rise(y):
    return _pchip_tab(RISE_TAB, y)


def beak_depth(y):
    return _pchip_tab(D_TAB, y)


def z_edge(y):
    """Height of the (sharp, un-rounded) beak top edge."""
    return z_centre(y) - crown(y)


def x_valley(y):
    """Where the wing top meets the beak side (on the beak's 55 deg side line)."""
    return -(beak_hw(y) + rise(y) / math.tan(BEAK_ANG))


def z_valley(y):
    return z_edge(y) - rise(y)


def beak_frame(y):
    """Section frame of the beak at y: (hw, zc, c, T1, T2, C, th1, th2) - crown parabola z = zc - c (ax/hw)^2 up to the
    fillet's top tangent point T1, arc (centre C, angles th1 -> th2) to the side tangent point T2, then the 55 deg
    side line."""
    hw, zc, c = beak_hw(y), z_centre(y), crown(y)
    phi = math.atan(2.0 * c / hw)                             # top slope at the sharp edge
    a = BEAK_ANG
    t = BEAK_RC * math.tan(0.5 * (a - phi))
    E = np.array([hw, zc - c])
    d1 = np.array([math.cos(phi), -math.sin(phi)])
    d2 = np.array([math.cos(a), -math.sin(a)])
    T1, T2 = E - t * d1, E + t * d2
    C = T1 + BEAK_RC * np.array([-math.sin(phi), -math.cos(phi)])
    return hw, zc, c, T1, T2, C, 0.5 * math.pi - phi, 0.5 * math.pi - a


def beak_z(ax, y):
    """Outer surface height of the beak at |x| = ax (crowned top, edge round, side line continued downward)."""
    hw, zc, c, T1, T2, C, th1, th2 = beak_frame(y)
    if ax <= T1[0]:
        return zc - c * (ax / hw) ** 2
    if ax <= T2[0]:
        return C[1] + math.sqrt(max(BEAK_RC ** 2 - (ax - C[0]) ** 2, 0.0))
    return T2[1] - (ax - T2[0]) * math.tan(BEAK_ANG)


def _towers():
    """Upper front rail shock towers (left side) from parts/chassis.py, with its documented fallback."""
    try:
        import importlib
        ch = importlib.import_module('chassis')
        return tuple(ch.T1_TOWER), tuple(ch.T2_TOWER)
    except Exception:
        return (-0.50, 1.38, 0.98), (-0.45, 1.66, 0.95)


T1, T2 = _towers()
RAIL_R = spec.CAGE_TUBE_R


def wf_low(y):
    return _pchip_tab(WF_LOW_TAB, y)


def sh_r(y):
    """Shoulder roll radius: matches the door cap's outer round at the shut line, R 0.04 on the wing."""
    return lerp(CAP_RO_FRONT + 0.002, 0.040, smooth((y - FENDER_Y0) / 0.15))


def side_top_z(y):
    return z_shoulder(y) - sh_r(y)


def x_sh(y):
    """x of the fender side's top (start of the shoulder roll): the door's tumblehome at the shut line, the spec
    outline FRONT_CLIP_HALF_W ahead of it."""
    return -w_up(y) + tumble(y) * (1.0 - smooth((y - FENDER_Y0) / 0.10))


def fside_x(y, z):
    """x of the left fender side / cheek at (y, z) below the shoulder roll. [fix r6] at the shut line it is the door's
    section (spec r6 front-corner tuck, crease + top band); ahead of it the r5 fender formula (lower band, plan width at
    the shoulder) takes over, still capped by the corner tuck, which relaxes ahead of y 0.92."""
    s = smooth((y - FENDER_Y0) / 0.12)
    zt = side_top_z(y)
    zA = min(lerp(0.75, 0.885, s), zt - 0.04)
    zB = lerp(0.92, zt, s)
    wl, wm = wf_low(y), w_up(y)
    u_f = wl + (wm - wl) * smooth((z - zA) / max(zB - zA, 1e-3))
    zc = zt - UP_CREASE
    if z > zc:                                              # (r5) soft tumblehome over the top 13 cm
        u_f -= (x_sh(y) + wm) * ((z - zc) / (zt - zc)) ** 1.4
    u_f = smin(u_f, corner_u(z), 0.016)          # the corner tuck runs on to the cheek's wrap (no outward relaxing)
    zk = DOOR_CREASE_Z
    yd = min(y, FENDER_Y0)                  # [fix r6] the door's shut-line section carried forward unchanged (door_u
    if z <= zk:                             # itself narrows ahead with w_front: an S in the blend)
        u_d = door_u(yd, z)
    else:
        u_d = door_u(yd, zk) - TB_IN * min(1.0, (z - zk) / max(zt - zk, 1e-4))
    return -lerp(u_d, u_f, s)


def zb_front(y):
    return _pchip_tab(ZB_FRONT, y)


def y_lead2(z):
    return _pchip_tab(Y_LEAD2, z)


def fe_w(x):
    return spline(FE_W, x)


COWL_FADE = 0.19                       # long enough that the lifted wing descends convexly into its own front fall


def _cowl_lift(x, y, z):
    """[fix r6] lift of the wing top over the r4 dash at the windshield base: the full COWL_NEED (+ ~4 mm soft max) at
    the rear edge, blended out over COWL_FADE to the natural wing by y ~0.99 instead of an smax with a falling need (the r5 one
    fell 5 cm in 4.5 cm and was cut off at y 0.86: curvature flip + 4 mm step = zebra bullseyes at the cowl corners)."""
    t = min(1.0, max(0.0, (y - 0.797) / COWL_FADE))
    f = 1.0 - t * t * (3.0 - 2.0 * t)
    if f <= 0.0:
        return 0.0
    return f * smax(_pchip_tab(COWL_NEED, abs(x)) - z, 0.0, 0.008)


def shoulder_pts(y):
    """(A, tA, B, P1, P2): bezier of the shoulder roll from the side top A to the wing top start B."""
    zt = side_top_z(y)
    R = sh_r(y)
    xa = fside_x(y, zt)
    dz = 0.01
    dx = (xa - fside_x(y, zt - dz)) / dz
    tA = np.array([dx, 1.0]) / math.hypot(dx, 1.0)
    lean = max(0.0, min(1.0, tA[0]))
    A = np.array([xa, zt])
    B = np.array([xa + R * (1.0 - 0.45 * lean), zt + R])
    k = 0.552 * R
    return A, tA, B, A + tA * k, B - np.array([k, 0.0])


def wing_z(x, y):
    """Wing top height at plan (x, y) between the shoulder top start and the valley (and a little beyond)."""
    _, _, B, _, _ = shoulder_pts(y)
    xb, zs = B
    xv, zv = x_valley(y), z_valley(y)
    t = (x - xb) / (xv - xb)
    tc = min(1.0, max(0.0, t))
    z = zs + (zv - zs) * (3 * tc * tc - 2 * tc ** 3) + WING_CROWN * 16 * tc * tc * (1 - tc) ** 2
    z += _cowl_lift(x, y, z)
    return z


N_WSIDE, N_WSH, N_WTOP = 13, 6, 18


def wing_columns():
    cols = [('side', k / (N_WSIDE - 1)) for k in range(N_WSIDE)]
    cols += [('shoulder', k / N_WSH) for k in range(1, N_WSH + 1)]
    cols += [('top', (k / N_WTOP)) for k in range(1, N_WTOP + 1)]
    cols += [('bury', 1.0)]
    return cols


def wing_point(col, y):
    kind, a = col
    if kind == 'side':
        zb, zt = zb_front(y), side_top_z(y)
        f = 0.5 - 0.5 * math.cos(math.pi * a)                   # denser at the bottom roll and under the shoulder
        f = 0.55 * f + 0.45 * a
        z = lerp(zb, zt, f)
        return (fside_x(y, z), y, z)
    if kind == 'shoulder':
        A, tA, B, P1, P2 = shoulder_pts(y)
        p = (1 - a) ** 3 * A + 3 * a * (1 - a) ** 2 * P1 + 3 * a * a * (1 - a) * P2 + a ** 3 * B
        return (p[0], y, p[1])
    _, _, B, _, _ = shoulder_pts(y)
    xv = x_valley(y)
    if kind == 'bury':
        x = xv + 0.006
        return (x, y, z_valley(y) - 0.001)
    x = lerp(B[0], xv, a)
    return (x, y, wing_z(x, y))


def _solve_y(f, y0, lo=0.70, hi=1.70):
    """Fixed point y = f(y) (damped)."""
    y = y0
    for _ in range(80):
        yn = f(y)
        if abs(yn - y) < 1e-7:
            break
        y = min(hi, max(lo, 0.5 * (y + yn)))
    return y


def wing_range(col):
    kind, a = col
    if kind == 'side':
        return FENDER_Y0, _solve_y(lambda y: y_lead2(wing_point(col, y)[2]), 1.12)
    if kind == 'shoulder':
        y_side = wing_range(('side', 1.0))[1]
        y_fe = _solve_y(lambda y: fe_w(wing_point(('shoulder', 1.0), y)[0]), 1.30)
        return FENDER_Y0, lerp(y_side, y_fe, a ** 0.85)
    xf = lambda y: wing_point(col, y)[0]
    return solve_edge(xf, REAR_EDGE, 0.8), _solve_y(lambda y: fe_w(xf(y)), 1.33)


LIP_R = 0.024                          # rolled lip of the cheek's leading edge and the wing's outer / front edge


def _front_tubes():
    """Cage tubes under the front clip that the skin must clear: the windshield-hoop leg, the belt rail and the first
    part of the upper front rail at the A-pillar foot (ahead of y 0.95 the chassis runs the rail under the r5 wing)."""
    a = spec.A_PILLAR_FOOT
    t = (0.95 - a[1]) / (T1[1] - a[1])
    r1 = tuple(a[k] + (T1[k] - a[k]) * t for k in range(3))
    return [[(-spec.FRAME_RAIL_X, 0.82, spec.FRAME_RAIL_Z), a], [a, spec.B_PILLAR_FOOT], [a, r1]]


NJ_WING, NJ_BEAK = 28, 28              # [fix r6] fewer, evenly spread sections (was 40 / 40) + fair_grid
FAIR_ITERS = 8


def build_front_clip(out):
    cols = wing_columns()
    nj = NJ_WING
    ranges = [wing_range(c) for c in cols]
    P = np.zeros((nj, len(cols), 3))
    for i, c in enumerate(cols):
        y0, y1 = ranges[i]
        for j in range(nj):
            s = j / (nj - 1)
            s = 0.5 * s + 0.5 * (0.5 - 0.5 * math.cos(math.pi * s))
            P[j, i] = wing_point(c, lerp(y0, y1, s))
    P = orient(P, lambda p: (-1, 0, 0.2) if p[2] < side_top_z(p[1]) - 0.01 else (0, 0.1, 1))
    DBG['wing0'] = P.copy()
    if FAIR_ITERS:
        P = fair_grid(P, iters=FAIR_ITERS)
    DBG['wing'] = P.copy()
    inner_last = P[0, -1, 0] > P[0, 0, 0]
    order = list(range(len(cols))) if inner_last else list(range(len(cols)))[::-1]
    cols_o = [cols[k] for k in order]
    fr, fh, rr, rh = [], [], [], []
    for c in cols_o:
        if c[0] in ('side', 'shoulder'):
            fr.append(LIP_R); fh.append(0.018); rr.append(0.007); rh.append(0.012)
            continue
        fr.append(0.018); fh.append(0.014)
        x_r = wing_point(c, wing_range(c)[0])[0]
        notch = x_r < REAR_EDGE[1][0] + 0.002
        rr.append(0.007 if notch else 0.010); rh.append(0.012)
    P = roll(P, 'j1', np.array(fr), np.array(fh), n_arc=5)
    P = roll(P, 'j0', np.array(rr), np.array(rh), n_arc=3)
    side_end = 'i1' if inner_last else 'i0'
    # bottom roll of the fender side: full size (r 15 mm + 20 mm return) unless it would reach the frame rail
    # (|x| 0.7254 below z 0.533) or interior's footwell side wall (|x| 0.652-0.656 to y 1.00)
    eb = P[:, 0] if side_end == 'i0' else P[:, -1]
    avail = []
    for xb, yb, zb_ in eb:
        lim = 0.0
        # ([fix r6] only where the bottom edge runs over the rail / outboard of the footwell wall: the tucked corner's
        # edge is inboard of both - chassis / interior coordination)
        if zb_ - 0.015 < spec.FRAME_RAIL_Z + spec.FRAME_TUBE_R + 0.007 and yb < 0.95 and \
                -xb > spec.FRAME_RAIL_X - spec.FRAME_TUBE_R - 0.006:
            lim = RAIL_OUT
        if 0.89 < yb < 1.01 and -xb > 0.664:
            lim = max(lim, 0.659)
        avail.append(-xb - lim - THICK if lim else lerp(0.016, 0.06, smooth((yb - 0.95) / 0.10)))
    avail = np.array(avail)
    r_sb = np.clip(avail - 0.002, 0.004, 0.015)
    h_sb = np.clip(avail - r_sb, 0.0, 0.02)
    P = roll(P, side_end, r_sb, h_sb, n_arc=4)
    tubes_saved = _cage_tubes
    globals()['_cage_tubes'] = _front_tubes
    try:
        clear_tubes(P)
    finally:
        globals()['_cage_tubes'] = tubes_saved

    def mfn(c, n):
        if n.z > 0.45:
            return TOP
        if n.x < -0.35:
            return LIV
        if n.y > 0.3:
            return GLOSS                    # rolled lips (cheek leading edge, wing front edge)
        return CARB
    bm = grid_bmesh(P, mat_fn=mfn)
    o = finish('body_front_clip', bm, mirror=True, smooth_deg=70)
    out.append(o)


def beak_section(y):
    """(x, z) points of the left half of the beak at y: centre -> crowned top -> edge round -> 55 deg side down to the
    bottom edge (z_edge - beak_depth)."""
    hw, zc, c, T1, T2, C, th1, th2 = beak_frame(y)
    pts = []
    n_top = 10
    for k in range(n_top + 1):
        ax = T1[0] * (k / n_top)
        pts.append((-ax, zc - c * (ax / hw) ** 2))
    for k in range(1, 5):
        th = th1 + (th2 - th1) * k / 4
        pts.append((-(C[0] + BEAK_RC * math.cos(th)), C[1] + BEAK_RC * math.sin(th)))
    xs_, zs_ = pts[-1]
    zbot = z_edge(y) - beak_depth(y)
    # [fix r6] spec r6 front coilover top (-0.222, 1.442, 0.83) and chassis' clevis plates under it (|x| 0.18-0.226,
    # y 1.420-1.464, tops 0.838-0.847): the side skirt is trimmed up to SKIRT_TRIM[2] over them, its edge then at
    # |x| 0.156-0.169 (>= 1.1 cm inboard / over the plates, 3.5 cm from the eye)
    y0t, y1t, zt, rt = SKIRT_TRIM
    wt = smooth((y - y0t + rt) / rt) * smooth((y1t + rt - y) / rt)
    zbot = lerp(zbot, max(zbot, zt), wt)
    n_side = 7
    for k in range(1, n_side + 1):
        z = lerp(zs_, zbot, k / n_side)
        pts.append((xs_ - (zs_ - z) / math.tan(BEAK_ANG), z))
    return pts


SKIRT_TRIM = (1.395, 1.485, 0.858, 0.05)  # y range at full trim, skirt bottom z there, blend length
NOSE_RP = 0.24                         # plan radius of the blunt nose front


def beak_front(ax):
    """Plan view front end of the beak (blunt, rounded corners), y at |x| = ax."""
    ax = min(ax, 0.95 * NOSE_RP)
    return NOSE_Y - NOSE_RP + math.sqrt(NOSE_RP ** 2 - ax * ax)


def build_beak(out):
    ncol = len(beak_section(1.2))
    nj = NJ_BEAK
    P = np.zeros((nj, ncol, 3))
    for i in range(ncol):
        y1 = _solve_y(lambda y: beak_front(abs(beak_section(y)[i][0])), 1.62, lo=1.4, hi=1.7)
        for j in range(nj):
            s = j / (nj - 1)
            s = 0.6 * s + 0.4 * (0.5 - 0.5 * math.cos(math.pi * s))
            y = lerp(BEAK_Y0, y1, s)
            x, z = beak_section(y)[i]
            P[j, i] = (x, y, z)
    P[:, 0, 0] = 0.0
    # full width grid (right half mirrored in front of the left), so the rolls see a symmetric centre column
    Pm = P[:, :0:-1].copy()
    Pm[..., 0] *= -1.0
    P = np.concatenate([Pm, P], axis=1)
    P = orient(P, lambda p: (0, 0.2, 1) if abs(p[0]) < 0.05 else (math.copysign(0.8, p[0]), 0, 0.6))
    DBG['beak0'] = P.copy()
    if FAIR_ITERS:
        P = fair_grid(P, iters=FAIR_ITERS)
    DBG['beak'] = P.copy()
    P = roll(P, 'j1', 0.022, 0.026, n_arc=5)                      # nose: the front face wraps down
    P = roll(P, 'j0', 0.004, 0.008, n_arc=2)                      # rear edge (inside, behind the vent face)
    P = roll(P, 'i0', 0.006, 0.012, n_arc=4)                      # bottom edges of the side faces
    P = roll(P, 'i1', 0.006, 0.012, n_arc=4)

    def mfn(c, n):
        if n.z > 0.45:
            return TOP
        if n.y > 0.3:
            return GLOSS                    # nose lip
        return CARB
    bm = grid_bmesh(P, mat_fn=mfn)
    out.append(finish('body_beak', bm, smooth_deg=60))


def build_hood_bulkhead(out):
    """Closing panel under the wing / beak at the front bulkhead (on top of the chassis footwell front wall, z 0.865),
    so nothing looks through under the wings into the footwell / dash from the front."""
    y = 1.214                                                  # 1.5 cm ahead of the chassis bulkhead hoop top
    xs = np.linspace(-0.445, 0.0, 16)
    rows = []
    for z_frac in (0.0, 1.0):
        row = []
        for x in xs:
            ax = abs(x)
            if ax <= -x_valley(y):
                zs_ = beak_z(ax, y)
            else:
                zs_ = wing_z(x, y)
            row.append((x, y, lerp(0.862, zs_ - THICK - 0.006, z_frac)))
        rows.append(row)
    P = np.array(rows)
    P = orient(P, (0, 1, 0))
    bm = grid_bmesh(P, mat_fn=lambda c, n: CARB)
    out.append(finish('body_hood_bulkhead', bm, mirror=True, merge_centre=True, smooth_deg=60))


# vent band = the hood deck from the windshield base to the vent step (BAND_H over the beak table, its sides running
# down the beak's 55 deg side line into the wings) + the step's forward face with three recessed hex-mesh vents
# (front.png / front_3q triangulation: centres x 0 / +-0.146, y ~1.09, z ~1.07; mesh ~0.125 x 0.035), gloss black
# frames 10 mm wide, mesh 15 mm deep (along the face normal) on a black backing
BAND_H = 0.045                        # deck over the beak table: 1.10 at the windshield base (spec HOOD_CENTRE_Z[0])
VENT_YT, VENT_YB = 1.058, 1.100       # step face: top edge (front row of the deck) / bottom edge (on the beak)
BEAK_Y0 = VENT_YB - 0.012             # the beak grid starts just behind the face bottom
VENT_XC = (-0.148, 0.0, 0.148)
VENT_W, VENT_T = 0.122, 0.035         # opening width / height along the face
VENT_FR, VENT_DEPTH = 0.010, 0.015    # frame width, recess depth
VENT_X0 = 0.236                       # face: true-x layout inside this, stretched to the band / beak ends outside


BAND_SIDE = math.radians(75.0)        # the band's end faces are steeper than the beak sides (front_3q: short black ends)


def band_z(ax, y, H):
    """Band surface: the beak's crowned top and edge round raised by H, then a side steepening from the beak's 55 deg
    to BAND_SIDE within 1 cm."""
    hw, zc, c, T1, T2, C, th1, th2 = beak_frame(y)
    if ax <= T2[0] or H <= 0.0:
        return beak_z(ax, y) + H
    d = ax - T2[0]
    s0, s1, d1 = math.tan(BEAK_ANG), math.tan(BAND_SIDE), 0.010
    if d <= d1:
        return T2[1] + H - s0 * d - 0.5 * (s1 - s0) / d1 * d * d
    return T2[1] + H - s0 * d1 - 0.5 * (s1 - s0) * d1 - s1 * (d - d1)


def _band_end(y, H):
    """|x| where the band surface dips under the wing."""
    lo, hi = -x_valley(y) - 0.04, -x_valley(y) + 0.08
    for _ in range(40):
        m = 0.5 * (lo + hi)
        if band_z(m, y, H) > wing_z(-m, y) - 0.004:
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


def build_cowl_vents(out):
    mt = mats()
    ns = 40                                                   # columns across the full width
    nr = 11
    ys = [VENT_YT - (VENT_YT - (COWL_Y - 0.004)) * (k / (nr - 1)) ** 1.15 for k in range(nr)]   # deck rows, front -> rear
    # columns: a layout coordinate u in [-Xm, Xm]; x = u inside VENT_X0 (true x, so the vents on the face are not
    # skewed), stretched to each row's own end (where the band side meets the wing) outside it
    Xb, Xt = _band_end(VENT_YB, 0.0), _band_end(VENT_YT, BAND_H)
    Xm = 0.5 * (Xb + Xt)
    us = sorted(set([round(Xm * (-1 + 2 * k / ns), 9) for k in range(ns + 1)] + [-VENT_X0, VENT_X0]))
    ncol = len(us) - 1

    def xs_of(u, X):
        x0 = min(VENT_X0, 0.85 * X)
        au = abs(u)
        if au <= x0:
            return u
        return math.copysign(x0 + (au - x0) / (Xm - x0) * (X - x0), u)

    def band_pt(u, y, H):
        x = xs_of(u, _band_end(y, H))
        return V((x, y, band_z(abs(x), y, H)))
    bm = bmesh.new()
    TOPM, GLS, MESH, BACK, CRB = 0, 1, 2, 3, 4
    faces = []                                                # (BMFace, wanted normal direction or None)

    def add(vs, m, want):
        try:
            f = bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = m
        faces.append((f, want))
        return f
    # deck (its front row is the step face's top edge) + rear lip rolling down at the windshield base
    rows = [[bm.verts.new(band_pt(u, y, BAND_H)) for u in us] for y in ys]
    lip = []
    for (dy, dz) in ((-0.006, -0.004), (-0.009, -0.012), (-0.010, -0.024), (-0.010, -0.044)):
        lip.append([bm.verts.new(V((r.co.x, ys[-1] + dy, r.co.z + dz))) for r in rows[-1]])
    grid = rows + lip
    for k, (ra, rb) in enumerate(zip(grid[:-1], grid[1:])):
        for i in range(ncol):
            if k < len(rows) - 1:
                add((ra[i], ra[i + 1], rb[i + 1], rb[i]), TOPM, V((0, 0, 1)))
            else:
                add((ra[i], ra[i + 1], rb[i + 1], rb[i]), CRB if k > len(rows) else TOPM, V((0, -1, 0.4)))
    # step face: ruled between the bottom curve (3 mm into the beak) and the deck's front row

    def bot_pt(u):
        x = xs_of(u, Xb)
        return V((x, VENT_YB, beak_z(abs(x), VENT_YB) - 0.003))

    def top_pt(u):
        return band_pt(u, VENT_YT, BAND_H)
    L = (top_pt(0) - bot_pt(0)).length                        # slant length of the face at the centre
    t_dir = (top_pt(0) - bot_pt(0)).normalized()
    nrm = V((1, 0, 0)).cross(t_dir).normalized()
    if nrm.y < 0:
        nrm = -nrm

    def map2(u, t):
        return bot_pt(u).lerp(top_pt(u), t / L)

    def nrm_at(u, t):
        e = 1e-3
        a = map2(u + e, t) - map2(u - e, t)
        b = map2(u, t + e) - map2(u, t - e)
        n = a.cross(b).normalized()
        return n if n.y > 0 else -n

    def rrect2(xc, tc, w, h, r, k=4):
        """Rounded rectangle in (x, slant) metres around (xc, tc), CCW, 4 * (k + 1) points."""
        pts = []
        for sx, sz, a0 in ((1, 1, 0.0), (-1, 1, 0.5), (-1, -1, 1.0), (1, -1, 1.5)):
            cx, cz = xc + sx * (w / 2 - r), tc + sz * (h / 2 - r)
            for j in range(k + 1):
                a = math.pi * (a0 + 0.5 * j / k)
                pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
        return pts
    tc = 0.5 * L
    holes_o = [rrect2(xc, tc, VENT_W + 2 * VENT_FR, VENT_T + 2 * VENT_FR, 0.010 + VENT_FR) for xc in VENT_XC]
    holes_i = [rrect2(xc, tc, VENT_W, VENT_T, 0.010) for xc in VENT_XC]
    outer2 = [(u, 0.0) for u in us] + [(u, L) for u in us[::-1]]
    bm2 = bmesh.new()
    vo = [bm2.verts.new(V((x, 0.0, t))) for (x, t) in outer2]
    vh = [[bm2.verts.new(V((x, 0.0, t))) for (x, t) in h] for h in holes_o]
    edges = [bm2.edges.new((vo[i], vo[(i + 1) % len(vo)])) for i in range(len(vo))]
    for loop in vh:
        edges += [bm2.edges.new((loop[i], loop[(i + 1) % len(loop)])) for i in range(len(loop))]
    bmesh.ops.triangle_fill(bm2, use_beauty=True, use_dissolve=False, edges=edges)
    bm2.verts.index_update()
    vmap = [bm.verts.new(map2(v.co.x, v.co.z)) for v in bm2.verts]
    for f in bm2.faces:
        add([vmap[v.index] for v in f.verts], CRB, nrm)
    bm2.free()
    # frames (outer loop flush with the face, inner loop 1.5 mm proud), recess walls 15 mm straight back, the hex mesh
    # at the bottom and a black backing 3 mm behind it
    for ho, hi in zip(holes_o, holes_i):
        lo_ = [bm.verts.new(map2(x, t)) for (x, t) in ho]
        li_ = [bm.verts.new(map2(x, t) + nrm_at(x, t) * 0.0015) for (x, t) in hi]
        lw = [bm.verts.new(map2(x, t) - nrm_at(x, t) * VENT_DEPTH) for (x, t) in hi]
        n = len(lo_)
        cm = sum((v.co for v in lw), V()) / n
        for i in range(n):
            i2 = (i + 1) % n
            add((lo_[i], lo_[i2], li_[i2], li_[i]), GLS, nrm)
            mid = (li_[i].co + li_[i2].co) * 0.5
            inward = cm - mid
            inward -= nrm * inward.dot(nrm)
            add((li_[i], li_[i2], lw[i2], lw[i]), GLS, inward)
        cmv = bm.verts.new(cm)
        for i in range(n):
            add((cmv, lw[(i + 1) % n], lw[i]), MESH, nrm)
        lb = [bm.verts.new(v.co - nrm * 0.003) for v in lw]
        cb = bm.verts.new(cm - nrm * 0.003)
        for i in range(n):
            add((cb, lb[(i + 1) % n], lb[i]), BACK, nrm)
    for f, want in faces:
        f.normal_update()
        if want is not None and f.normal.dot(want) < 0:
            f.normal_flip()
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    slots = [mt['top'], mt['gloss'], mt['mesh'], mt['black'], mt['carbon']]
    o = obj_from_bmesh('body_cowl_vents', bm, slots, smooth=True, angle=40)
    me = o.data
    uvl = me.uv_layers.new(name='UVMap').data
    for p in me.polygons:
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if p.material_index == MESH:
                uvl[li].uv = (co.x / 0.11, co.z / 0.11)
            elif p.material_index == TOPM:
                uvl[li].uv = top_uv(co, p.normal)
            else:
                uvl[li].uv = (co.x * CARBON_UV, co.z * CARBON_UV)
    set_shading(o, 40)
    out.append(o)


# ------------------------------------------------------------------ [fix r4] rear pods: inclined shields
# spec r4 + rear.png / rear_3q_right.png / rear_wheel_sidepod_right.png: each pod is ONE carbon shell from the tail
# face to the door shut line (it replaces the r3 pod side + flat deck + tail-block side). Section (left side,
# u = |x|): the lower side at REAR_POD_HALF_W up to z ~1.10, leaning in above it to a rounded shoulder
# (REAR_POD_SHOULDER_HALF_W, radius REAR_POD_SHOULDER_R), the deck rising ~13 deg inboard to its inner top edge
# (REAR_DECK_INNER_HALF_W at spec.rear_deck_z(y)), an inner roll and a short inner wall (at the tail it drops to the
# tail-block floor). The tail block keeps a tighter shoulder (R 0.03 at the face) so the section still covers the
# chassis tail-lamp bezel (x -0.502..-0.590, z 1.169..1.301). Ahead of the deck (rear shock tops at y -1.22 / -1.05,
# bypass caps, tower plates at |x| 0.668) the deck's inner edge sweeps outboard (DECK_END) and the section becomes a
# thin rounded rim - the scoop wall - outboard of the tower plates, the rear upper loop (|x| 0.6675, z 1.255) and the
# main-hoop gusset fin; its top rises to REAR_DECK_Z_FWD at y -1.05 and then drops in one concave fillet (R 0.30)
# along the gusset base to the belt (BELT_Z) at the door shut line, where the section is the door's cap.

POD_THETA = math.radians(13.0)         # deck slope (falls outboard)
POD_THETA_TAIL = math.radians(8.0)     # at the tail face
POD_R_TAIL = 0.030                     # shoulder radius at the tail face
POD_Z_LEAN = 1.10                      # the side leans in above this
DECK_END = (-1.345, -1.29)            # the deck's front edge: its inner edge sweeps out to the rim between these stations
RIM_R, RIM_RI = 0.008, 0.008           # scoop rim: outer / inner roll radius (r5: a sharp carbon lip, was 0.015 / 0.012)
RIM_R_MAX = 0.012                      # (r5: no pillow crown where the rim is wide; was 0.035)
# [fix r5] scoop (rear_wheel_sidepod_right + side photos): the rim top stays at deck height back to y -1.20, then one
# concave drop (R FILLET_R, steepest FILLET_A) runs out level at the belt (BELT_Z) at FILLET_YE, opening the shock /
# reservoir bay to the side; ahead of FILLET_YE the rim is a belt-height sill to the door shut line. (r4: R 0.30 / 55 deg
# to the shut line, held >= 1 cm over interior.py int_rear_quarter - reported: that panel's top must now drop to
# <= BELT_Z - 0.01 from y -1.02 forward.)
# [fix r6] spec r6 REAR_POD_SHOULDER_Z 1.30 / R 0.05 over y -0.95..-1.25 (rear.png: broad flat carbon shield, crisp outer
# top corner at ~(0.72-0.75, 1.28-1.30); rear_3q / rear_wheel_sidepod: the top edge stays high past the shocks and sweeps
# down just behind the main hoop): the r5 scoop is gone - the top holds ~1.30 to y -0.95 (inner edge |x| 0.652, over
# the rear upper rail, outboard of the shocks / bypass caps |x| <= 0.641), then the drop (concave fillet R FILLET_R,
# steepest FILLET_A) runs out level at the belt at FILLET_YE, just behind the pod's leading-edge step.
FILLET_R = 0.25
FILLET_A = math.radians(55.0)
FILLET_YE = -0.645
POD_THETA_SCOOP = math.radians(5.0)    # top slope ahead of the deck's front edge (the flat shield top)
# outer top corner cap where the top is high but the shoulder table is wide (y -0.80..-1.20): rear.png's corner
# (u 1143, v ~197) back-projects to (0.741, 1.27) @ y -0.95 .. (0.70, 1.30) @ -1.10; the table's 0.79 @ -0.95 (set when
# the top there was at the belt) stays the half-width at belt / deck height and the side leans in above it
POD_CORNER_W = [(-1.30, 0.750), (-1.20, 0.713), (-1.15, 0.712), (-1.10, 0.716), (-1.05, 0.726), (-1.00, 0.740),
                (-0.95, 0.755), (-0.90, 0.768), (-0.85, 0.782), (-0.80, 0.800)]
FW_ORANGE_TOP = 1.228                  # interior.py int_firewall_orange top (y -0.93..-0.908, |x| <= 0.762)
# spec r5 left rear brace (B_PILLAR_TOP -> REAR_BRACE_END, tube CAGE_TUBE_R): it runs under the deck's inner top edge
# at y -1.29..-1.45 (centre |x| 0.45-0.43, z 1.29-1.26); the inner wall's return stops >= BRACE_CLEAR over it
BRACE_P0, BRACE_P1 = spec.B_PILLAR_TOP, spec.REAR_BRACE_END
BRACE_CLEAR = 0.006
TAIL_WIDEN = 0.006                     # tail face 6 mm wider than TAIL_HALF_W: the lamp bezel reaches |x| 0.590
TAIL_RAKE = 0.012                      # tail face: bottom 12 mm forward of the top
# chassis r4 (16:12) routes two tubes through the tail block along its inner wall (rear.png): the rear upper loop
# (centre |x| 0.485-0.49, z 1.232, inside the block, out of the tail face beside the lamp) and below it the nested
# rear inner loop (centre |x| 0.448, z 1.161, in the engine bay at the wall's foot). The wall passes between them:
# 7 mm inboard of the deck's inner edge beside the upper loop, then out to WALL_OUT below it.
WALL_IN, WALL_OUT = 0.453, 0.474       # inner wall |x| beside the upper loop / below it (tail block only)
WALL_JOG_Z = (1.183, 1.212, 1.262)     # jog bottom / top, back to the deck's inner edge above the upper loop
N_WALL = 8
# its way down at the block's front, one pinned pod station each (the inner loop climbs to the deck x-bar at y -1.83,
# so the wall can only reach the floor behind y ~-1.90): short (y -1.835) -> down beside the upper loop at WALL_IN to
# WALL_TB_Z[0] (y -1.868) -> out under it to WALL_OUT at WALL_TB_Z[1] (y -1.903) -> down outboard of the inner loop
# to the floor (y -1.938). The wall points sit on fixed levels (bunched 2 mm apart above a raised bottom), so the
# quads between stations do not shear across either loop.
WALL_TB_Y = (-1.835, -1.868, -1.903, -1.938)
WALL_TB_Z = (1.225, 1.198)
TAIL_LOOP_XZ = (-0.4845, 1.232)        # chassis rear_upper_loop where it leaves the tail face (chassis.py XT, ZEXIT)
CARBON_UV_POD = 1.0                    # tail face / pod inside faces: 1 UV unit per metre
# rim inner face |x|: outboard of the rear tower plates (0.668, y -1.32..-1.02), the gusset fin and the rear upper
# loop (outer 0.692 at y -1.37..-0.97, then out to 0.74 at the B-pillar foot), the main-hoop leg (0.761) at the front
RIM_U = [(-1.30, 0.655), (-1.20, 0.652), (-1.06, 0.652), (-0.98, 0.658), (-0.925, 0.700), (-0.875, 0.760),
         (-0.83, 0.768), (-0.72, 0.765), (-0.60, 0.765)]
# (r6: the inner edge |x| 0.652 under the flat top back to y -0.98 - 1.1 cm outboard of the bypass caps / coil bodies,
# its 4 cm return 2.8 cm over the rear upper rail (top 1.234); it sweeps out to the r5 sill (0.768) while the top falls,
# outboard of the rail (outer 0.694 @ -0.92 .. 0.70 @ -0.86), interior.py int_firewall_orange (|x| <= 0.762, top 1.228
# at y -0.93..-0.91, under the top) and int_rear_quarter (|x| 0.755-0.759))
# (r5: >= 0.698 from y -1.20 forward - the rim top drops past the rear upper loop there, so its inner wall stays outboard;
# 0.768 on the belt-height sill, outboard of interior.py's firewall bars / mesh (|x| <= 0.762 at y -0.93..-0.91))
# (r5: the r4 inner ridge over the scoop - body_pod_ridge - is gone: the spec r5 rear brace runs in its place)
# chassis rear upper loop centre line (chassis.py rear_l; tube r CAGE_TUBE_R): kept >= 3 mm under the skin. This is
# the r3 path (z 1.255): chassis r4 runs it lower (ZRAIL 1.212, ZEXIT 1.232), so it is a conservative envelope for
# the shoulder / rim checks; the tail block wall uses WALL_* instead. (r6: chassis r4 ZRAIL + 3 mm from the B-pillar
# to y -1.33, then blending back into the r3 envelope by the tail block)
REAR_LOOP = [(-0.718, -0.617, 1.125), (-0.668, -0.92, 1.215), (-0.670, -1.33, 1.215), (-0.600, -1.56, 1.225),
             (-0.510, -1.84, 1.255),
             (-0.500, -2.20, 1.255)]
LOOP_CLEAR = spec.CAGE_TUBE_R + 0.003 + THICK + 0.002


def tail_rake(z):
    return TAIL_RAKE * (TB_Z1 - z) / (TB_Z1 - TB_Z0)


def tail_widen(y):
    return TAIL_WIDEN * smooth((-1.96 - y) / 0.12)


# scoop rim top (y, z): starts at the deck's shoulder height where the deck ends and rises gently to
# REAR_DECK_Z_FWD at y -1.05 (spec r4 pod front), so the shoulder line runs on without a step
RIM_Z = [(-1.40, 1.300), (-1.29, 1.302), (-1.08, 1.302), (-0.95, 1.278)]


def pod_top_z(y, z_deck):
    """Height of the inner top edge: z_deck (the deck plane at the inner edge) along the deck, rising to RIM_Z on
    the scoop rim, then a rounded break, a short 75 deg drop and one concave fillet (R FILLET_R) that runs out level
    into the belt at FILLET_YE (belt height from there to the door shut line)."""
    s_z = smooth((y - DECK_END[1] + 0.01) / 0.10)
    z0 = lerp(z_deck, _pchip_tab(RIM_Z, y), s_z)
    ze = spec.BELT_Z
    d = max(FILLET_YE - y, 0.0)
    da = FILLET_R * math.sin(FILLET_A)
    if d <= da:
        zf = ze + FILLET_R - math.sqrt(max(FILLET_R ** 2 - d * d, 0.0))
    else:
        zf = ze + FILLET_R * (1 - math.cos(FILLET_A)) + (d - da) * math.tan(FILLET_A)
    return smin(z0, zf, 0.04)


def brace_uz(y):
    """(u, z) of the spec r5 left rear brace centre line at station y (None outside it)."""
    (x0, y0, z0), (x1, y1, z1) = BRACE_P0, BRACE_P1
    if not (y1 <= y <= y0):
        return None
    t = (y - y0) / (y1 - y0)
    return -(x0 + (x1 - x0) * t), z0 + (z1 - z0) * t


def _loop_uz(y):
    """(u, z) of the rear upper loop centre at station y (None where it is not under the pod)."""
    pts = REAR_LOOP
    for a, b in zip(pts, pts[1:]):
        if min(a[1], b[1]) <= y <= max(a[1], b[1]) and a[1] != b[1]:
            t = (y - a[1]) / (b[1] - a[1])
            return -(a[0] + (b[0] - a[0]) * t), a[2] + (b[2] - a[2]) * t
    return None


def wall_bottom_tb(y, z_short):
    """Inner wall bottom z at the tail block (see WALL_TB_Y): z_short ahead of it, the floor behind it."""
    y0, y1, y2, y3 = WALL_TB_Y
    za, zb = WALL_TB_Z
    if y >= y1:
        return lerp(za, z_short, smooth((y - y1) / (y0 - y1)))
    if y >= y2:
        return lerp(zb, za, smooth((y - y2) / (y1 - y2)))
    return lerp(TB_Z0 + 0.005, zb, smooth((y - y3) / (y2 - y3)))


def pod_params(y):
    s_t = smooth((y - TAIL_Y0) / (spec.TAIL_BLOCK_Y[1] - TAIL_Y0))      # 0 at the tail face .. 1 at the block front
    s_x = smooth((y - DECK_END[0]) / (DECK_END[1] - DECK_END[0]))      # 0 on the deck .. 1 in the scoop
    s_f = smooth((y + 0.95) / (POD_Y[1] + 0.95))                        # 0 at y -0.95 .. 1 at the shut line
    tw = tail_widen(y)
    ws = _pchip_tab(list(spec.REAR_POD_SHOULDER_HALF_W) + [(-0.80, BW - TUMBLE), (-0.50, BW - TUMBLE)], y) + tw
    if -1.32 < y < -0.78:
        ws = smin(ws, _pchip_tab(POD_CORNER_W, y) + tw, 0.008)
    s_rim = smooth((y + 0.97) / 0.10)                                  # [r6] flat top (y <= -0.97) .. narrow sill
    ri = lerp(lerp(0.020, RIM_RI, s_rim), CAP_R, s_f)
    u_rim = _pchip_tab(RIM_U, y)
    ui = lerp(spec.REAR_DECK_INNER_HALF_W, u_rim, s_x)
    r_rim = min(max(0.55 * (ws - u_rim) - RIM_RI, RIM_R), RIM_R_MAX)  # a little rounder where it is wide
    R = lerp(POD_R_TAIL, spec.REAR_POD_SHOULDER_R, s_t)                 # spec R on the deck and the flat top
    R = lerp(R, r_rim, s_rim)                                           # rim radius on the sill as it drops
    R = lerp(R, CAP_R, s_f)
    th_d = lerp(POD_THETA_TAIL, POD_THETA, s_t)
    th = lerp(lerp(th_d, POD_THETA_SCOOP, s_x), 0.0, s_f)
    # the deck keeps its plane while its inner edge sweeps outboard (the cut drops down the slope); ahead of it the
    # rim top follows RIM_Z
    z_deck = spec.rear_deck_z(y) - (ui - spec.REAR_DECK_INNER_HALF_W) * math.tan(th_d)
    zi = pod_top_z(y, z_deck)
    # inner wall height: down to the tail-block floor at the tail, a 10 cm return along the deck, 4 cm on the rim
    hw = zi - wall_bottom_tb(y, zi - 0.06)                              # (clear of the inner loop / deck x-bar)
    hw = lerp(lerp(hw, 0.040, smooth(1.6 * s_x)), CAP_R + 0.028, s_f)
    zwb = zi - hw
    lp = _loop_uz(y)
    if lp is not None and y > WALL_TB_Y[0]:     # where the wall (u ui..ui+THICK) would cross the loop it stops above it
        du = ui - lp[0]
        band = spec.CAGE_TUBE_R + 0.003
        w = max(0.0, min(1.0, (band + 0.01 - du) / 0.01, (du + band + THICK + 0.01) / 0.01))
        w *= smooth((y - DECK_END[0] + 0.05) / 0.05)
        zwb = lerp(zwb, max(zwb, lp[1] + spec.CAGE_TUBE_R + 0.024), smooth(w))
    bp = brace_uz(y)
    if bp is not None:              # the wall's return stops over the spec rear brace where it passes under the edge
        rb = spec.CAGE_TUBE_R + BRACE_CLEAR
        du = ui - bp[0]
        w = max(0.0, min(1.0, (rb + 0.012 - du) / 0.012, (du + rb + THICK + 0.012) / 0.012))
        zwb = lerp(zwb, max(zwb, bp[1] + rb), smooth(w))
    # [r6] over interior.py's firewall orange panel (|x| <= 0.762, top FW_ORANGE_TOP, y -0.93..-0.908) the wall's
    # return stops >= 8 mm above it while the inner edge sweeps out over it
    w = min(smooth((y + 0.950) / 0.015), smooth((-0.890 - y) / 0.015)) * smooth((0.772 - ui) / 0.006)
    zwb = lerp(zwb, max(zwb, FW_ORANGE_TOP + 0.008), w)
    return dict(ws=ws, R=R, th=th, ri=ri, ui=ui, zi=zi, zwb=zwb, tw=tw)


def _pod_section(y, zb, prm):
    """(u, z) points of the pod section at station y, from the bottom zb over the shoulder to the inner wall bottom,
    plus the index ranges of its parts."""
    ws, R, th, ri, ui, zi, zwb, tw = (prm[k] for k in ('ws', 'R', 'th', 'ri', 'ui', 'zi', 'zwb', 'tw'))
    tn, cs, sn = math.tan(th), math.cos(th), math.sin(th)
    # keep the top flat >= 3 mm long (narrow rim): shrink the rolls if needed
    room = (ws - ui) - 0.003
    need = R * (1 - sn) + ri * (1 + sn)
    if need > room:
        f = room / need
        R, ri = R * f, ri * f
    uc = ws - R

    def zline(u):
        return zi - (u - ui) * tn
    zc = zline(uc + R * sn) - R * cs
    ci = (ui + ri, zline(ui + ri) - ri / cs)
    zl_top = zc + R                                         # (approx.) top of the outer shoulder
    z_lean = max(min(POD_Z_LEAN, zl_top - 0.13), zb + 0.045)

    def ulow(z):
        return -side_x(y, z) + tw
    pts = []
    zl = zb + min(0.17, max(0.03, TUCK_ZK + 0.01 - zb))
    if zl > z_lean - 0.02:
        zl = zb + 0.45 * (z_lean - zb)
    for k in range(5):
        t = k / 5
        z = lerp(zb, zl, t)
        pts.append((ulow(z) - 0.006 * (1 - t) ** 2, z))
    for k in range(6):
        z = lerp(zl, z_lean, k / 6)
        pts.append((ulow(z), z))
    i_lean = len(pts)
    A = (ulow(z_lean), z_lean)
    du = (ulow(z_lean + 0.005) - ulow(z_lean - 0.005)) / 0.01
    # lean: circular-ish arc from the lower side into the shoulder (end tangent ~2x the chord angle)
    phi = 0.0
    for _ in range(6):
        B = (uc + R * math.cos(phi), zc + R * math.sin(phi))
        ch = math.atan2(A[0] - B[0], max(B[1] - A[1], 1e-4))
        phi = min(max(2.0 * ch - math.atan(-du), 0.0), 0.5 * math.pi - th - 0.25, math.radians(48.0))
    B = (uc + R * math.cos(phi), zc + R * math.sin(phi))
    L = math.hypot(B[0] - A[0], B[1] - A[1])
    ta = np.array([du, 1.0]) / math.hypot(du, 1.0) * L
    tb = np.array([-math.sin(phi), math.cos(phi)]) * L
    for k in range(6):
        t = k / 6
        h00 = 2 * t ** 3 - 3 * t ** 2 + 1; h10 = t ** 3 - 2 * t ** 2 + t
        h01 = -2 * t ** 3 + 3 * t ** 2; h11 = t ** 3 - t ** 2
        pts.append((h00 * A[0] + h10 * ta[0] + h01 * B[0] + h11 * tb[0],
                    h00 * A[1] + h10 * ta[1] + h01 * B[1] + h11 * tb[1]))
    i_arc = len(pts)
    a1 = 0.5 * math.pi - th
    for k in range(7):                                      # outer shoulder
        a = lerp(phi, a1, k / 6)
        pts.append((uc + R * math.cos(a), zc + R * math.sin(a)))
    i_top = len(pts)
    T = pts[-1]
    Ti = (ci[0] + ri * sn, ci[1] + ri * cs)
    for k in range(1, 6):                                   # deck / rim top
        t = k / 5
        pts.append((lerp(T[0], Ti[0], t), lerp(T[1], Ti[1], t)))
    i_roll = len(pts)
    for k in range(1, 5):                                   # inner roll
        a = lerp(a1, math.pi, k / 4)
        pts.append((ci[0] + ri * math.cos(a), ci[1] + ri * math.sin(a)))
    i_wall = len(pts)
    zw0 = pts[-1][1]
    s_tb = smooth((WALL_TB_Y[0] + 0.03 - y) / 0.03)        # tail block: the wall runs down between the two loops
    j0, j1, j2 = WALL_JOG_Z
    zf = TB_Z0 + 0.005
    lev = [lerp(zw0, j2, 0.5), j2, 0.5 * (j1 + j2), j1, j0, lerp(j0, zf, 1 / 3), lerp(j0, zf, 2 / 3), zf]
    assert len(lev) == N_WALL
    zbot = min(zwb, zw0 - 0.004)
    e = min(0.002, (zw0 - zbot) / N_WALL)
    j0e = max(j0, zbot)                                     # the jog out ends at the bottom while that is raised
    for k in range(1, N_WALL + 1):
        t = k / N_WALL
        z = lerp(lerp(zw0, zbot, t), max(lev[k - 1], zbot + (N_WALL - k) * e), s_tb)
        u_tb = WALL_IN + (ui - WALL_IN) * smooth((z - j2) / 0.03)
        if j1 > j0e:
            u_tb += (WALL_OUT - WALL_IN) * min(max((j1 - z) / (j1 - j0e), 0.0), 1.0)
        pts.append((lerp(ui + 0.003 * t, u_tb, s_tb), z))
    return pts, dict(lean=i_lean, arc=i_arc, top=i_top, roll=i_roll, wall=i_wall)


def pod_section(y, prm=None):
    """Pod section at y with the shoulder widened where it would come within LOOP_CLEAR of the rear upper loop."""
    prm = dict(prm or pod_params(y))
    zb = pod_bottom(y) if y > spec.TAIL_BLOCK_Y[1] else TB_Z0 + ROLL_POD
    lp = _loop_uz(y)
    for _ in range(6):
        pts, idx = _pod_section(y, zb, prm)
        if lp is None:
            break
        q = np.array(pts[idx['lean']:idx['roll']])
        a, b = q[:-1], q[1:]
        ab = b - a
        t = np.clip(((np.array(lp) - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-12), 0, 1)
        d = np.linalg.norm(a + t[:, None] * ab - np.array(lp), axis=1).min()
        if d >= LOOP_CLEAR:
            break
        prm['ws'] += (LOOP_CLEAR - d) + 0.001
    return pts, idx, prm


def pod_rows(n=42):
    """Pod stations, spaced evenly along the 3D path of the deck's inner top edge (it sweeps outboard ahead of the
    deck and drops steeply into the belt), so neither the sweep nor the drop shears the quads."""
    y0, y1 = TAIL_Y0, POD_Y[1]
    yy = np.linspace(y0, y1, 600)
    E = np.array([(pod_params(y)['ui'], y, pod_params(y)['zi']) for y in yy])
    ds = np.linalg.norm(np.diff(E, axis=0), axis=1)
    ds *= 1.0 + 0.25 * np.array([1.0 - smooth((y - spec.TAIL_BLOCK_Y[1]) / 0.12) for y in yy[1:]])   # tail block
    cum = np.concatenate([[0.0], np.cumsum(ds)])
    ys = [float(np.interp(t, cum, yy)) for t in np.linspace(0.0, cum[-1], n)]
    for yt in WALL_TB_Y:                                    # the inner wall's steps at the tail block (WALL_TB_Y)
        k = min(range(1, n - 1), key=lambda i: abs(ys[i] - yt))
        ys[k] = yt
    return ys


def pod_mat(c, n):
    if n.z > 0.80:
        return TOP
    if n.x < -0.35:
        return LIV
    return CARB


def _uv_carbon(scale):
    def f(p, co, n):
        if p.material_index != CARB:
            return None
        ax = max(range(3), key=lambda k: abs(n[k]))
        if ax == 0:
            return (co.y * scale, co.z * scale)
        if ax == 1:
            return (co.x * scale, co.z * scale)
        return (co.x * scale, co.y * scale)
    return f


def rake_warp(P, y_f):
    """Lean the rear end of the grid like the tail face (fades out at y_f)."""
    w = np.clip((y_f - P[:, :, 1]) / (y_f - TAIL_Y0), 0.0, 1.0)
    P[:, :, 1] += np.vectorize(tail_rake)(P[:, :, 2]) * w


def build_pod(out):
    ys = pod_rows()
    rows = []
    for y in ys:
        pts, idx, prm = pod_section(y)
        rows.append([(-u, y, z) for (u, z) in pts])
    P = np.array(rows)
    rake_warp(P, spec.TAIL_BLOCK_Y[1])
    tyre_relief(P)
    P = orient(P, lambda p: (-1, 0, 0) if p[2] < 1.0 else (-0.3, 0, 1))
    DBG['pod'] = P.copy()
    first_bottom = ((P[:, 0, 2] - P[:, -1, 2]).sum() - (np.abs(P[:, 0, 0]) - np.abs(P[:, -1, 0])).sum()) < 0
    s_bot, s_wall = ('i0', 'i1') if first_bottom else ('i1', 'i0')
    P = roll(P, s_bot, ROLL_POD, 0.012, n_arc=4)
    lo = [WALL_TB_Y[3] + 0.01 < y < WALL_TB_Y[0] - 0.01 for y in ys]     # wall bottom passing the loops: no curl
    P = roll(P, s_wall, np.where(lo, 0.002, 0.004), np.where(lo, 0.0, 0.003), n_arc=2)
    # [fix r6] front end = the forward-facing STEP over the inset door: a rolled lip (R STEP_R) on the side skin whose
    # return runs in to STEP_GAP off the door skin; where the door's top flares out (rear end, belt rail) the lip
    # shrinks; tiny on the top / inner flank / bottom roll
    Nr = grid_normals(P)
    n = Nr[-1]
    r = np.full(P.shape[1], 0.002); h = np.zeros(P.shape[1])
    for i in range(P.shape[1]):
        if n[i, 2] > 0.45 or n[i, 0] > 0.25 or n[i, 2] < -0.45:
            continue
        room = -P[-1, i, 0] - (door_side_u(DOOR_Y[0], P[-1, i, 2]) + STEP_GAP)
        if room >= STEP_R + 0.002:
            r[i], h[i] = STEP_R, room - STEP_R
        else:
            r[i] = max(0.002, room)
    P = roll(P, 'j1', r, h, n_arc=4)
    bm = grid_bmesh(P, mat_fn=pod_mat)
    out.append(finish('body_pod', bm, mirror=True, special_uv=_uv_carbon(CARBON_UV_POD)))


def build_tail_block(out):
    """Tail face plate (6 mm carbon, raked like the pod's rear end) closing the pod section at TAIL_Y0, with the
    lamp opening at spec.TAIL_LIGHT_XZ / TAIL_LIGHT_WH (the chassis builds the lamp behind it), the tail-block floor
    at TAIL_BLOCK_Z[0] and the orange accent stripe across the deck's rear-outer corner (rear.png)."""
    yb0, yb1 = spec.TAIL_BLOCK_Y                # -2.12 (rear face), -1.86
    pts, idx, prm = pod_section(TAIL_Y0)
    sec = [(-u, z) for (u, z) in pts]
    zf = TB_Z0
    outer = [(sec[0][0] + 0.008, zf)] + [p for p in sec if p[1] >= zf - 1e-6]
    xi = sec[-1][0]
    loop = outer + [(xi + 0.004, zf + 0.004), (xi + 0.012, zf)]
    loop = [p for i, p in enumerate(loop) if i == 0 or math.dist(p, loop[i - 1]) > 1e-4]
    lx, lz = spec.TAIL_LIGHT_XZ
    lw, lh = spec.TAIL_LIGHT_WH
    hw, hh = lw / 2 + 0.002, lh / 2 + 0.002
    hole = round2d([(lx - hw, lz - hh), (lx + hw, lz - hh), (lx + hw, lz + hh), (lx - hw, lz + hh)], [0.006] * 4, 2)
    # the chassis rear upper loop leaves the face just inboard of the lamp (centre |x| 0.4845, z 1.232; 3 mm from the
    # lamp housing): the opening takes in its circle (r tube + 4 mm) through a short neck behind the lamp bezel
    tc, tr = (TAIL_LOOP_XZ[0], TAIL_LOOP_XZ[1]), spec.CAGE_TUBE_R + 0.004
    xe = lx + hw
    if tc[0] - tr < xe + 0.012:
        dz = min(0.012, 0.8 * tr)
        xn = tc[0] - math.sqrt(tr * tr - dz * dz)              # circle point at the neck's height (outboard side)
        ang0 = math.atan2(-dz, xn - tc[0]) % (2 * math.pi)
        ang1 = math.atan2(dz, xn - tc[0]) % (2 * math.pi)
        if ang1 < ang0:
            ang1 += 2 * math.pi
        arc = [(tc[0] + tr * math.cos(a), tc[1] + tr * math.sin(a)) for a in np.linspace(ang0, ang1, 16)]
        if xn > xe + 1e-4:
            arc = [(xe, tc[1] - dz)] + arc + [(xe, tc[1] + dz)]
        new_hole = []                                   # splice it into the inner (+x) edge of the rounded rectangle
        for i, p in enumerate(hole):
            if p[0] > xe - 1e-4 and tc[1] - dz < p[1] < tc[1] + dz:
                continue
            new_hole.append(p)
            if p[0] > xe - 1e-4 and p[1] <= tc[1] - dz and (i + 1 < len(hole) and hole[i + 1][1] > p[1]):
                new_hole += arc
        hole = new_hole
    bm = bmesh.new()

    def Vp(x, z):
        return V((x, yb0 + tail_rake(z), z))
    vo = [bm.verts.new(Vp(x, z)) for (x, z) in loop]
    vh = [bm.verts.new(Vp(x, z)) for (x, z) in hole]
    edges = [bm.edges.new((vo[i], vo[(i + 1) % len(vo)])) for i in range(len(vo))]
    edges += [bm.edges.new((vh[i], vh[(i + 1) % len(vh)])) for i in range(len(vh))]
    bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges)
    for f in bm.faces:
        f.normal_update()
        if f.normal.y > 0:
            f.normal_flip()
        f.material_index = CARB
    out.append(finish('body_tail_face', bm, thick=0.006, mirror=True, smooth_deg=40,
                      special_uv=_uv_carbon(CARBON_UV_POD)))
    # floor of the block (the shell's bottom roll curls in over its outer edge) -----------------------------
    zfl = TB_Z0 + 0.005
    rows = []
    for j in range(6):
        y = lerp(yb0 + 0.006 + tail_rake(zfl), -1.925, j / 5)
        xo = side_x(y, TB_Z0 + ROLL_POD) - tail_widen(y) + 0.018
        xin = -pod_section(y)[0][-1][0] - 0.002
        rows.append([(lerp(xo, xin, i / 4), y, zfl) for i in range(5)])
    P = orient(np.array(rows), (0, 0, -1))
    out.append(finish('body_tail_floor', grid_bmesh(P, mat_fn=lambda c, n: CARB), mirror=True,
                      special_uv=_uv_carbon(CARBON_UV_POD)))
    # orange accent stripe draped over the deck's rear-outer corner -----------------------------------------
    ya, yb = -2.000, yb0 + 0.02

    def deck_pt(f, y):
        """Point on the shell's top surface at fraction f from the shoulder's start (0) to the inner roll (1)."""
        pts, idx, _ = pod_section(y)
        top = pts[idx['arc'] + 2:idx['roll'] + 1]
        cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(np.array(top), axis=0), axis=1))])
        s = f * cum[-1]
        k = min(len(top) - 2, int(np.searchsorted(cum, s, side='right') - 1))
        t = (s - cum[k]) / max(cum[k + 1] - cum[k], 1e-9)
        u = lerp(top[k][0], top[k + 1][0], t); z = lerp(top[k][1], top[k + 1][1], t)
        return np.array([-u, y + tail_rake(z) * (1 if y < yb1 else 0), z + 0.0012])
    bm = bmesh.new()
    ns = 6
    va, vb = [], []
    for k in range(ns + 1):
        t = k / ns
        y = lerp(ya, yb, t)
        f = lerp(0.05, 0.62, t)
        c = deck_pt(f, y)
        c2 = deck_pt(min(1.0, f + 0.02), y + 0.004)
        d = c2 - c
        side = np.cross(d, (0, 0, 1)); side = side / max(np.linalg.norm(side), 1e-9) * 0.015
        va.append(bm.verts.new(V(c - side))); vb.append(bm.verts.new(V(c + side)))
    for k in range(ns):
        f = bm.faces.new((va[k], vb[k], vb[k + 1], va[k + 1]))
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    st = obj_from_bmesh('body_tail_stripe', bm, M('orange'), smooth=False)
    out.append(st)
    from common import mirror_x
    out.append(mirror_x(st, 'body_tail_stripe_R'))


# ------------------------------------------------------------------ [fix r3] engine cover + sill return lip

# Gloss panel between the pods behind the firewall (rear.png / rear_3q: the black cover with the two orange racing
# stripes, seen BEHIND the rear X-brace). Top face: M('livery_top') + top_uv (livery_top.png window u 0.30..0.70,
# v (y + 2.5) / 4.5; textures paints the two orange stripes there, continuous with the roof's).
# [fix r5] (arbiter: keep the lid, lower and slope it; the spec r5 rear cage X now spans OVER it): front edge on the
# firewall top (y -0.92, z 1.27, 3.8 cm over interior's int_firewall_top 1.232), a soft crease 7 cm behind it, then
# ~22 deg down to the rear edge (y -1.265, z 1.155: the charge-pipe merge / stem at x ~0, y -1.26..-1.40 tops out at
# 1.137, so the lid cannot reach the arbiter's (-1.30, 1.12)), top corners rolled R 0.05 into a short side skirt at
# |x| 0.40 (the powertrain filter / reservoir cans stand at |x| >= 0.423, tops 1.24-1.26), a gloss black rear edge band
# with six small hex-mesh vents. >= 10 cm under the X (z 1.373 @ y -0.92, 1.30 @ -1.27).
COVER_HW = 0.405                       # outer edge of the side skirt
COVER_R = 0.05                         # top-corner roll radius
COVER_SKIRT = 0.010
# top centre line (y, z): front edge, crease, slope, rear edge
# [fix r6] spec ENGINE_COVER_FRONT_YZ (-0.92, 1.325) (rear.png panel top edge v ~162; reverses the r5 lowering), same
# ~21 deg fall behind the crease, so the rear edge ends at 1.211 (was 1.155). Air: X arms >= 1.7 cm (y -1.0, |x| 0.32,
# tube bottom 1.337), 4 cm at their upper ends (|x| 0.39 @ y -0.92 over the corner roll); rear braces outboard (|x| 0.50);
# int_firewall_top 1.232 is 6 cm under the skirt.
COVER_TOP = [(spec.ENGINE_COVER_FRONT_YZ[0], spec.ENGINE_COVER_FRONT_YZ[1]), (-0.990, 1.317), (-1.265, 1.211)]
COVER_CREASE_R = 0.25                  # soft crease (round across the slope change)
COVER_BAND_Y = -1.200                  # gloss black rear edge band behind this
COVER_VENTS = (0.070, 0.170, 0.270)    # vent centres |x| (each side)
COVER_VENT_WH = (0.066, 0.016)


# suspension.py xbrace_reservoir (r5): a remote can clamped under each X arm's upper end (|x| 0.28-0.46, y -0.78..-0.967,
# bottom z 1.283-1.30) - inside the spec r6 lid (1.325 @ y -0.92 across |x| <= 0.40). The lid's front edge stays at the
# firewall for |x| <= 0.24 and its corners are chamfered back to y -0.995 (>= 1 cm air past the cans' inboard caps); from
# the rear the corner top edge is 8 mm lower (crease height), the cans sit just in front of it.
COVER_CORNER = (0.240, 0.060, -0.995)  # chamfer start |x|, run, corner front edge y


def cover_front_y(ax):
    x0, run, yc = COVER_CORNER
    return lerp(COVER_TOP[0][0], yc, smooth((ax - x0) / run))


def cover_z(y):
    """Cover top centre-line height: flat-ish front strip, a soft crease (round of COVER_CREASE_R), then the slope."""
    (y0, z0), (y1, z1), (y2, z2) = COVER_TOP
    s0, s1 = (z1 - z0) / (y1 - y0), (z2 - z1) / (y2 - y1)      # slopes dz/dy (positive: falling rearward)
    a = abs(math.atan(s1) - math.atan(s0))
    t = COVER_CREASE_R * math.tan(0.5 * a)                   # tangent length of the round (along y, approx.)
    if y >= y1 + t:
        return z0 + s0 * (y - y0)
    if y <= y1 - t:
        return z1 + s1 * (y - y1)
    u = (y1 + t - y) / (2 * t)                              # quadratic blend across the crease
    za, zb = z1 + s0 * t, z1 - s1 * t
    zm = z1
    return (1 - u) ** 2 * za + 2 * u * (1 - u) * zm + u * u * zb


# interior.py int_firewall_top: a shelf on the firewall, |x| <= 0.53, y -1.005..-0.908, top z 1.232. The lid's front
# part sits over it: there the corner roll flattens (elliptical, shorter skirt) so its bottom edge stays >= 4 mm over
# the shelf; behind the shelf's rear edge it returns to the full roll + skirt within FW_SHELF_RUN.
FW_SHELF = (-1.005, 1.232)
FW_SHELF_RUN = 0.020


def cover_depth(y):
    """Max drop of the corner roll + skirt below the top edge at station y."""
    full = COVER_R + COVER_SKIRT
    xr = COVER_HW - COVER_R
    lim = cover_z(y) + 0.010 * (1 - (xr / COVER_HW) ** 2) - (FW_SHELF[1] + 0.008)
    w = smooth((y - (FW_SHELF[0] - 0.006 - FW_SHELF_RUN)) / FW_SHELF_RUN)
    return lerp(full, min(full, lim), w)


def cover_section(y):
    """(x, dz) points across the left half: crowned top (1 cm), R COVER_R roll, side skirt (flattened over the
    firewall shelf, see cover_depth)."""
    pts = []
    xr = COVER_HW - COVER_R
    for k in range(9):
        x = xr * k / 8
        pts.append((x, 0.010 * (1 - (x / COVER_HW) ** 2)))
    dep = cover_depth(y)
    rz = min(COVER_R, dep - 0.002)
    sk = max(dep - rz, 0.002)
    zc = 0.010 * (1 - (xr / COVER_HW) ** 2) - rz
    for k in range(1, 6):
        a = 0.5 * math.pi * (1 - k / 5)
        pts.append((xr + COVER_R * math.cos(a), zc + rz * math.sin(a)))
    pts.append((COVER_HW, zc - sk))
    return [(-x, dz) for (x, dz) in pts]


def build_engine_cover(out):
    ny = 12
    ys = [lerp(COVER_TOP[-1][0], COVER_TOP[0][0], j / (ny - 1)) for j in range(ny)]
    ys = sorted(set([round(y, 6) for y in ys] + [COVER_BAND_Y, COVER_BAND_Y + 0.004, FW_SHELF[0] - 0.006,
                                                 FW_SHELF[0] - 0.006 - FW_SHELF_RUN]))
    # [fix r6] front corners chamfered back (cover_front_y) clear of suspension.py's X-brace reservoirs
    yr, yf0 = COVER_TOP[-1][0], COVER_TOP[0][0]
    rows = []
    for y in ys:
        t = (y - yr) / (yf0 - yr)
        row = []
        for k, (x, dz) in enumerate(cover_section(y)):
            yk = yr + t * (cover_front_y(abs(x)) - yr)
            xk, dzk = cover_section(yk)[k]
            row.append((xk, yk, cover_z(yk) + dzk))
        rows.append(row)
    P = orient(np.array(rows), (0, 0.35, 1))
    P = roll(P, 'j0', 0.012, 0.012, n_arc=3)
    # front lip: full roll over the firewall top, fading to a small one at the side skirt (the skirt's corner must not
    # curl into the ends of interior.py's int_firewall_top / orange panel at |x| 0.389)
    ax = np.abs(P[-1, :, 0])
    sf = np.array([smooth((v - 0.33) / 0.05) for v in ax])
    P = roll(P, 'j1', 0.012 - 0.008 * sf, 0.010 * (1 - sf), n_arc=3)
    side = 'i0' if abs(P[0, 0, 0]) > abs(P[0, -1, 0]) else 'i1'
    P = roll(P, side, 0.003, 0.002, n_arc=2)
    if side == 'i0':
        P[:, -1, 0] = 0.0
    else:
        P[:, 0, 0] = 0.0

    def mfn(c, n):
        if c.y < COVER_BAND_Y + 0.002:
            return GLOSS                     # rear edge band
        return TOP if n.z > 0.6 else GLOSS
    bm = grid_bmesh(P, mat_fn=mfn)
    out.append(finish('body_engine_cover', bm, mirror=True, merge_centre=True, smooth_deg=50))
    # vents in the black band: hex-mesh inserts over a black backing, 0.6 / 0.3 mm proud of the surface
    mt = mats()
    yb = 0.5 * (COVER_BAND_Y + COVER_TOP[-1][0]) + 0.004
    w, h = COVER_VENT_WH
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    for sx in (-1, 1):
        for xc in COVER_VENTS:
            for lift, mi, sh in ((0.0004, 0, 0.004), (0.0009, 1, 0.0)):
                vs = []
                for (px, py) in round2d([(-w / 2 - sh, -h / 2 - sh), (w / 2 + sh, -h / 2 - sh), (w / 2 + sh, h / 2 + sh),
                                         (-w / 2 - sh, h / 2 + sh)], [0.004 + sh] * 4, 2):
                    x, y = sx * xc + px, yb + py
                    z = cover_z(y) + 0.010 * (1 - (x / COVER_HW) ** 2) + lift
                    vs.append(bm.verts.new(V((x, y, z))))
                f = bm.faces.new(vs)
                f.material_index = mi
                f.normal_update()
                if f.normal.z < 0:
                    f.normal_flip()
                for lp in f.loops:
                    lp[uvl].uv = (lp.vert.co.x / 0.11, lp.vert.co.y / 0.11)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    o = obj_from_bmesh('body_cover_vents', bm, [mt['black'], mt['mesh']], smooth=False)
    out.append(o)


# [fix r4] Sill. spec r4: the body sides end at SILL_Z 0.50 and the frame rails moved up to FRAME_RAIL_Z 0.50 (tube
# |x| 0.6746-0.7254, z 0.4746-0.5254). r3 hung a black skirt (body_sill_lip) down to z 0.468 outboard of the rail
# (then bottom 0.445): it showed as a strip 2.5 cm under the photo's bottom line. Now nothing of the body goes below
# SILL_Z: the door's rolled bottom edge (visual bottom SILL_Z) returns inward at z ~0.50 and stops 3 mm (+ skin)
# outboard of the rail all along the door, which closes the sill without a separate lip. The rail's lower half
# (z 0.475-0.50) is below the sill line, so no skirt that ends at SILL_Z can hide it from the side (reported).
RAIL_OUT = spec.FRAME_RAIL_X + spec.FRAME_TUBE_R + 0.003      # body stays this far outboard of the rail centre


def _sill_budget(y):
    """Room (m) from the door's bottom edge in to RAIL_OUT + skin, less 2 mm for the inward lean of the roll.
    [fix r6] where the tucked front corner's bottom edge runs inboard of the frame rail (or high over it) the rail is not
    in the way: a small roll + return (the interior's door card / footwell sit just inside)."""
    zb = zb_door(y)
    x_bot = side_x(y, zb)                                               # the profile's bottom point
    if -x_bot < spec.FRAME_RAIL_X - spec.FRAME_TUBE_R - 0.006:
        return 0.016
    return (-RAIL_OUT - THICK) - x_bot - 0.002


def door_rows():
    """Door stations: ~5 cm apart, clustered at the pocket's rear / front walls and corners."""
    y0, y1 = DOOR_Y
    a, b = PK_Y
    ys = list(np.linspace(y0, a - 0.035, 9))
    ys += [a - 0.016, a, a + 0.005, a + 0.014, a + 0.028, a + 0.045]
    ys += list(np.linspace(a + 0.045, b - 0.045, 15)[1:-1])
    ys += [b - 0.045, b - 0.028, b - 0.014, b - 0.005, b, b + 0.016]
    ys += list(np.linspace(b + 0.016, y1, 7)[1:])
    return ys


def clear_belt_rail(P):
    """[fix r6] door: keep the skin off the belt rail only (the windshield-hoop leg crosses the spec r6 front-corner tuck
    below z ~0.78 - chassis coordination, no bulge)."""
    saved = globals()['_cage_tubes']
    globals()['_cage_tubes'] = lambda: [[spec.A_PILLAR_FOOT, spec.B_PILLAR_FOOT]]
    try:
        clear_tubes(P)
    finally:
        globals()['_cage_tubes'] = saved


def sill_roll_r(y):
    """Door bottom roll radius: 15 mm where the tucked door leaves room, down to 6 mm at the narrow front."""
    return min(ROLL_SILL, max(0.006, _sill_budget(y) - 0.002))


def sill_return(y):
    """Straight inward return after the roll (the roll always adds >= 2 mm): up to 2 cm, ending at RAIL_OUT + skin."""
    return max(0.0, min(0.02, _sill_budget(y) - sill_roll_r(y)))


# ------------------------------------------------------------------ roof + spoiler

def offset2d(poly, d):
    """Inset a closed CCW 2D polygon by d (positive = inward)."""
    n = len(poly)
    out = []
    P = [np.array(p, float) for p in poly]
    area = sum(P[i][0] * P[(i + 1) % n][1] - P[(i + 1) % n][0] * P[i][1] for i in range(n))
    sgn = 1.0 if area > 0 else -1.0
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        e1 = b - a; e2 = c - b
        n1 = np.array([-e1[1], e1[0]]) * sgn; n2 = np.array([-e2[1], e2[0]]) * sgn
        n1 /= max(np.linalg.norm(n1), 1e-9); n2 /= max(np.linalg.norm(n2), 1e-9)
        m = n1 + n2
        m /= max(np.linalg.norm(m), 1e-9)
        cosh = max(0.3, float(np.dot(m, n1)))
        out.append(tuple(b + m * d / cosh))
    return out


def round2d(pts, radii, steps=3):
    """Round the corners of a closed 2D polygon with per-corner radii (0 = keep)."""
    out = []
    n = len(pts)
    for i in range(n):
        r = radii[i]
        b = np.array(pts[i], float)
        if r <= 0:
            out.append(tuple(b)); continue
        a = np.array(pts[i - 1], float); c = np.array(pts[(i + 1) % n], float)
        d1 = a - b; d2 = c - b
        l1, l2 = np.linalg.norm(d1), np.linalg.norm(d2)
        d1 /= l1; d2 /= l2
        ang = math.acos(max(-1.0, min(1.0, float(np.dot(d1, d2)))))
        if ang < 1e-3 or ang > math.pi - 1e-3:
            out.append(tuple(b)); continue
        t = min(r / math.tan(ang / 2), l1 * 0.45, l2 * 0.45)
        p1, p2 = b + d1 * t, b + d2 * t
        for s in range(steps + 1):
            u = s / steps
            q = p1 * (1 - u) ** 2 + b * 2 * u * (1 - u) + p2 * u * u
            out.append(tuple(q))
    return out


# [fix r4] roof + spoiler (spec r4): the roof tapers in plan from ROOF_WIDTH / 2 (0.63, over the A-pillar tops) at
# ROOF_FRONT_Y to ROOF_REAR_HALF_W (0.59, over the B-pillar tops at |x| 0.56) at ROOF_REAR_Y; the striped spoiler's rear
# face is a trapezoid in rear view, SPOILER_HALF_W 0.54 at its lower edge / 0.49 at its top lip (rear.png). Heights
# follow spec ROOF_REAR_Z 1.54 / SPOILER_TOP_Z 1.58. The chassis sets its LED strips into the face at z 1.495, |x|
# 0.30-0.455; the whip-light brackets (x +-0.35, y -0.47) rise through the section and stand on the spoiler top.
# [fix r5] (lead decision / silhouette critic):
#   * ONE CLOSED CARBON BAND: the roof's side edges come down around the roof rails as a closed section (the band's
#     underside runs BAND_AIR under the rail, its inner wall BAND_AIR inboard of it), so side / rear views show one
#     carbon band instead of a thin skin over an exposed tube ("roof rack"). The rail line is the chassis' own (the
#     hoops' bent centre lines, see _roof_rail). The band's front end rakes up between y 0.43 and 0.33 so the A-pillar
#     corner bend stays visible (front.png / front_3q).
#   * the ceiling (ROOF_CEIL) ramps from 1.4745 at the front to 1.505 over the raised main-hoop cross tube (spec r5
#     B_PILLAR_TOP z 1.475: tube top 1.497); the light-bar bracket slots are gone (the 6 mm brackets pass through).
#   * spoiler: face 10.5 cm instead of 12.2 (bottom SPOILER_FACE_Z 1.475; rear_3q profile was ~13.5 cm vs the photo's
#     6-8), R 10 mm rear corners, a sharp top lip with a small up-kick, and an open gap under the overhang (the face's
#     lower lip returns only 1.5 cm, then the underside rises into a cavity over the main-hoop cross tube).
#   * cockpit: 15 mm satin-black trim with button-head fasteners across the liner just behind the header tube (the
#     liner fills the top ~20-25 % of the 78 deg cockpit frame); two small orange marks on the roof front edge under
#     the light bar (front.png).
# [fix r6] spoiler = a THIN SWEPT BLADE (spec r6): the top rises from ROOF_REAR_Z (y BLADE_Y0) ever steeper into the
# trailing-edge lip (SPOILER_TOP_Z at SPOILER_TRAIL_Y, arched back in plan), the rear face drops to
# SPOILER_FACE_BOTTOM_Z (leaning forward like chassis.spoiler_spec_face), the underside runs forward ~3 cm under the top
# with open air under the overhang (rear braces 4+ cm below). Plan: the roof's rear corners (0.59) sweep in to
# SPOILER_HALF_W[1] by y -0.54; the rear face is the spec trapezoid with rounded corners.
BLADE_Y0 = -0.400                      # the blade top starts rising here
SPOILER_LEAN = 0.15                    # rear face: 1.5 cm forward per 10 cm down (chassis spoiler_spec_face)
SPOILER_R = (0.020, 0.026)             # rear-view corner radii: top lip / lower edge (spec ~0.03; the ends are 5 cm tall)
SPOILER_UNDER = (1.522, 1.529)         # blade underside: mid-blade / over the main-hoop cross (tube top 1.497 at y -0.45)
# ceiling (y, z): 7.5 mm over the header / rails at the front, over the main-hoop cross (top 1.497 at y -0.45) at the rear
ROOF_CEIL = [(0.47, 1.4745), (0.40, 1.4745), (0.30, 1.4745), (0.20, 1.4745), (0.00, 1.478), (-0.20, 1.486),
             (-0.35, 1.497), (-0.42, 1.505)]
BAND_WALL = 0.030                      # [fix r6] max height of the band's inner wall (ceiling - inner edge)
BAND_D = 0.074                         # nominal distance of the band's inner wall from the roof edge (rail inner + air)
BAND_DW = 0.014                        # width of the rounded step from the band underside up to the ceiling
BAND_Y = (0.30, 0.40)                  # the band is full depth behind y 0.30 and rakes up to nothing at 0.40 (light-bar feet)
ROOF_UNDER_Z = ROOF_CEIL[0][1]


def _roof_rail():
    """Left roof rail centre line ends (A, B) as chassis.py builds it: between the nearest points of the bent
    windshield-hoop / main-hoop centre lines to A_PILLAR_TOP / B_PILLAR_TOP (fallback: the spec nodes moved the way
    the bends move them)."""
    rc = spec.CAGE_TUBE_R
    try:
        import importlib
        ch = importlib.import_module('chassis')
        rx, rz = spec.FRAME_RAIL_X, spec.FRAME_RAIL_Z
        wh = ch.fillet_path(ch.mirror_pts([(-rx, 0.82, rz), spec.A_PILLAR_FOOT, spec.A_PILLAR_TOP]),
                            [0.10, 3 * rc, 3 * rc, 0.10], 10)
        mh = ch.fillet_path(ch.mirror_pts([(-rx, spec.MAIN_HOOP_Y + 0.005, rz), spec.B_PILLAR_FOOT,
                                           spec.B_PILLAR_TOP]), 0.09, 10)
        a, b = ch.nearest_on(wh, spec.A_PILLAR_TOP), ch.nearest_on(mh, spec.B_PILLAR_TOP)
        return tuple(a), tuple(b)
    except Exception:                                  # pragma: no cover
        a, b = spec.A_PILLAR_TOP, spec.B_PILLAR_TOP
        return (a[0] + 0.017, a[1] + 0.011, a[2] - 0.014), (b[0] + 0.010, b[1] - 0.007, b[2] - 0.014)


ROOF_RAIL = _roof_rail()


def rail_at(y):
    """(x, z) of the left roof rail centre at station y (clamped to the rail's ends)."""
    a, b = ROOF_RAIL
    t = min(1.0, max(0.0, (y - a[1]) / (b[1] - a[1])))
    return a[0] + (b[0] - a[0]) * t, a[2] + (b[2] - a[2]) * t


def roof_band_z(d, y):
    """[fix r6] band underside at nominal distance d from the roof edge: on the roof-rail centre line out to the rail
    (the skin sits on the rail, its lower half shows), rising inboard so the inner wall stays <= BAND_WALL tall (r5:
    tube bottom - 5 mm; the far band showed under the near one from low side cameras)."""
    rx, rz = rail_at(y)
    hw = roof_half_w(y)
    dc = (hw - abs(rx)) * (spec.ROOF_WIDTH / 2) / hw
    zi = max(rz, roof_ceil(y) - BAND_WALL)
    return lerp(rz, zi, smooth((d - dc) / max(BAND_D - dc, 1e-3)))


def blade_k(x):
    return min(1.0, (x / spec.SPOILER_HALF_W[1]) ** 2)


def lip_y(x):
    """Spoiler trailing edge (top lip) y at |x|, arched back in plan (spec SPOILER_TRAIL_Y; chassis uses the same)."""
    return lerp(spec.SPOILER_TRAIL_Y[0], spec.SPOILER_TRAIL_Y[1], blade_k(x))


def face_bottom_z(x):
    return lerp(spec.SPOILER_FACE_BOTTOM_Z[0], spec.SPOILER_FACE_BOTTOM_Z[1], blade_k(x))


def blade_top_z(y, yl):
    s = min(1.0, max(0.0, (BLADE_Y0 - y) / (BLADE_Y0 - yl)))
    return spec.ROOF_REAR_Z + 0.002 + (spec.SPOILER_TOP_Z - spec.ROOF_REAR_Z - 0.002) * s ** 1.6


def blade_half_w(y):
    """Plan half-width of the roof / blade top: the roof taper, then in to SPOILER_HALF_W[1] by y -0.54."""
    if y >= spec.ROOF_REAR_Y:
        return roof_half_w(y)
    return lerp(spec.ROOF_REAR_HALF_W, spec.SPOILER_HALF_W[1], smooth((spec.ROOF_REAR_Y - y) / 0.09))


def roof_ceil(y):
    return _pchip_tab(ROOF_CEIL, y)


def roof_half_w(y):
    t = min(1.0, max(0.0, (spec.ROOF_FRONT_Y - y) / (spec.ROOF_FRONT_Y - spec.ROOF_REAR_Y)))
    return lerp(spec.ROOF_WIDTH / 2, spec.ROOF_REAR_HALF_W, t)


def roof_liner_mat():
    return mat('Roof liner carbon', tex='carbon_base.png', normal='carbon_normal.png', normal_strength=0.3,
               rough_tex='carbon_rough.png', rough_factor=1.26, clearcoat=0.5, clearcoat_rough=0.08, uv_scale=(6, 6))


def build_roof(out):
    """Roof skin (carbon top, light bar on it) with the side bands over the roof rails + the striped spoiler blade."""
    zt = spec.ROOF_TOP_Z
    yf = spec.ROOF_FRONT_Y + 0.03
    # cross-section in (y, z) per x station. The top stays at ROOF_TOP_Z at the front (light bar) and ramps up to
    # ROOF_REAR_Z by y -0.2; [fix r6] the blade top rises from BLADE_Y0 into the lip (SPOILER_TOP_Z at lip_y(x)), the
    # rear face drops to face_bottom_z(x), the underside runs forward over the main-hoop cross tube, then the ceiling
    # (ROOF_CEIL knots, the band underside at the outer stations) runs forward to the front face.
    zr, zsp = spec.ROOF_REAR_Z, spec.SPOILER_TOP_Z
    w0, w1 = spec.SPOILER_HALF_W
    ramp = [(y, zt + (zr - zt) * 0.5 * (1 - math.cos(math.pi * (0.2 - y) / 0.4))) for y in (0.2, 0.1, 0.0, -0.1, -0.2)]

    def base_pts(xa):
        yl, zfb = lip_y(xa), face_bottom_z(xa)
        yb = yl + SPOILER_LEAN * (zsp - zfb)                       # face bottom (forward of the lip)
        top = [(lerp(BLADE_Y0, yl, t), blade_top_z(lerp(BLADE_Y0, yl, t), yl)) for t in (0.3, 0.52, 0.70, 0.84, 0.94)]
        pts = [(yf, roof_ceil(yf) + 0.002), (yf - 0.004, zt)] + ramp + [(BLADE_Y0, zr + 0.002)] + top + \
            [(yl, zsp + 0.001),                                     # lip (trailing edge)
             (yb, zfb),                                             # lower rear edge
             (yb + 0.030, zfb + 0.006),
             (lerp(yb, -0.475, 0.55), max(zfb + 0.010, SPOILER_UNDER[0])),
             (-0.475, max(zfb + 0.012, SPOILER_UNDER[1])),          # over the main-hoop cross tube
             (-0.445, 1.518)]
        rad = [0.004, 0.006] + [0] * len(ramp) + [0.03] + [0] * len(top) + [0.004, 0.004, 0.020, 0.020, 0.012, 0.010]
        pts += [(y, z) for (y, z) in reversed(ROOF_CEIL)]
        rad += [0] * len(ROOF_CEIL)
        return pts, rad
    b0, _ = base_pts(0.0)
    knots = list(range(len(b0) - len(ROOF_CEIL), len(b0)))
    knot_y = [b0[k][0] for k in knots]
    area = sum(b0[i][0] * b0[(i + 1) % len(b0)][1] - b0[(i + 1) % len(b0)][0] * b0[i][1] for i in range(len(b0)))

    def section(d, xa):
        """Rounded section at nominal distance d from the roof edge (the band lowers the ceiling knots); xa: the
        station's |x| on the blade (lip / face bottom)."""
        base, rad = base_pts(xa)
        pts = [list(p) for p in base]
        g = 1.0 - smooth((d - BAND_D) / BAND_DW)
        if g > 0:
            for k, y in zip(knots, knot_y):
                f = smooth((BAND_Y[1] - y) / (BAND_Y[1] - BAND_Y[0])) * g
                pts[k][1] = lerp(roof_ceil(y), min(roof_ceil(y), roof_band_z(d, y)), f)
        sec = round2d([tuple(p) for p in pts], rad, steps=3)
        return list(reversed(sec)) if area < 0 else sec
    half = spec.ROOF_WIDTH / 2         # nominal half-width the rings are built at; warped to the plan / face below
    xs = []
    nx = 16
    for k in range(nx + 1):
        xs.append(-half + 0.006 + (2 * half - 0.012) * k / nx)
    xs = [x for x in xs if not (0.01 < half - abs(x) < 0.11)]
    # the band (rail inside) + its rounded inner step; they double as the spoiler-corner stations
    band_d = [0.016, 0.030, 0.048, 0.062, BAND_D + 0.0005, BAND_D + 0.004, BAND_D + 0.008, BAND_D + 0.012,
              BAND_D + 0.016, BAND_D + 0.026]
    xs += [sx * (half - d) for sx in (-1, 1) for d in band_d]
    xs.sort()
    # [integration] end inset must stay below half the skin thickness or the end strip turns inside out
    ends = [(half - 0.003, 0.002), (half, 0.0042)]
    bm = bmesh.new()
    rings = []
    stations = [(-e[0], e[1]) for e in reversed(ends)] + [(x, 0.0) for x in xs] + [e for e in ends]
    rt, rb = SPOILER_R

    def to_disc(a, b):
        return a * math.sqrt(max(0.0, 1.0 - 0.5 * b * b)), b * math.sqrt(max(0.0, 1.0 - 0.5 * a * a))
    n = None
    for xn, ins in stations:
        xa = min(1.0, abs(xn) / half) * w1                # the station's |x| on the blade
        yl, zfb = lip_y(xa), face_bottom_z(xa)
        sec = section(half - abs(xn), xa)
        s2 = offset2d(sec, ins) if ins > 0 else sec
        assert n is None or len(s2) == n, 'roof section vertex count changed'
        n = len(s2)
        crown = 0.003 * (1 - (xn / half) ** 2)
        ring = []
        for (y, z) in s2:
            # front corners rounded in plan view
            if y > 0.3 and abs(xn) > half - 0.06:
                dx = abs(xn) - (half - 0.06)
                y -= 0.06 - math.sqrt(max(0.0, 0.06 ** 2 - dx ** 2))
            z += crown * (1 if z > 1.47 else 0.6) * (1.0 - smooth((BLADE_Y0 + 0.02 - y) / 0.10))
            # plan: roof taper -> blade; the last 5 cm before the lip take the rear face's trapezoid
            g = smooth((yl + 0.06 - y) / 0.05)
            hw = lerp(blade_half_w(y), lerp(w0, w1, min(1.0, max(0.0, (z - zfb) / (zsp - zfb)))), g)
            d = (half - abs(xn)) * hw / half                                       # distance from the end
            g_top = smooth((-0.43 - y) / 0.04)
            if g_top > 0:                                   # blade top corners (rear view R rt), along the blade
                zt_l = zsp if y < yl + 0.02 else blade_top_z(y, yl)
                if d < rt and z > zt_l - rt:
                    a, b = to_disc((rt - d) / rt, min(1.0, (z - (zt_l - rt)) / rt))
                    d, z = lerp(d, rt - rt * a, g_top), lerp(z, zt_l - rt + rt * b, g_top)
            g_bot = smooth((yl + 0.05 - y) / 0.02)
            if g_bot > 0 and d < rb and z < zfb + rb:       # lower rear corners (rear view R rb)
                a, b = to_disc((rb - d) / rb, min(1.0, max(0.0, (zfb + rb - z) / rb)))
                d, z = lerp(d, rb - rb * a, g_bot), lerp(z, zfb + rb - rb * b, g_bot)
            x = math.copysign(hw - d, xn)
            ring.append(bm.verts.new(V((x, y, z))))
        rings.append(ring)
    for a_, b_ in zip(rings[:-1], rings[1:]):
        for i in range(n):
            i2 = (i + 1) % n
            bm.faces.new((a_[i], a_[i2], b_[i2], b_[i]))
    # end caps: zipper-stitched between the upper and lower halves of the end profile in y order (the plan sweep makes
    # the end rings non-planar; an ngon cap's triangulation webbed across under the blade)
    for r in (rings[0], rings[-1]):
        nr = len(r)
        k0 = min(range(nr), key=lambda k: r[k].co.y)
        k1 = max(range(nr), key=lambda k: r[k].co.y)
        A, B_ = [r[k0]], [r[k0]]
        k = k0
        while k != k1:
            k = (k + 1) % nr
            A.append(r[k])
        k = k0
        while k != k1:
            k = (k - 1) % nr
            B_.append(r[k])
        i = j = 0
        while i < len(A) - 1 or j < len(B_) - 1:
            if j == len(B_) - 1 or (i < len(A) - 1 and A[i + 1].co.y <= B_[j + 1].co.y):
                tri = (A[i], A[i + 1], B_[j]); i += 1
            else:
                tri = (A[i], B_[j + 1], B_[j]); j += 1
            if len(set(tri)) == 3:
                try:
                    bm.faces.new(tri)
                except ValueError:
                    pass
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for f in bm.faces:
        f.normal_update()
        c, nn = f.calc_center_median(), f.normal
        yl_c, zfb_c = lip_y(abs(c.x)), face_bottom_z(abs(c.x))
        if c.y < -0.44 and nn.z < -0.3:
            # blade underside carbon; the rounded lower rear edge gloss black (rear view: thin dark line)
            f.material_index = GLOSS if (c.y < yl_c + 0.03 and c.z < zfb_c + 0.008) else CARB
        elif c.y < -0.40 and (nn.z > 0.3 or nn.y < -0.3) and abs(nn.x) < 0.7 and c.z > zfb_c - 0.002:
            f.material_index = TOP          # blade top + rear face: striped livery
        elif nn.z > 0.6:
            f.material_index = TOP
        else:
            f.material_index = CARB
    o = finish('body_roof', bm, thick=0.0, smooth_deg=40)

    def spoiler_uv(p, co, nn):
        """Map the whole painted spoiler block (y -0.37..-0.715 in livery_top) onto the visible blade: its top (from
        BLADE_Y0 to the lip) then the rear face (lip -> face bottom, local height)."""
        if p.material_index != TOP or p.center.y > -0.40:
            return None
        xa = abs(co.x)
        if p.normal.y < -0.5:
            t = (zsp - co.z) / (zsp - face_bottom_z(xa))
            yt = lerp(-0.45, -0.715, min(1.0, max(0.0, t)))
        else:
            t = (BLADE_Y0 - co.y) / (BLADE_Y0 - lip_y(xa))
            yt = lerp(-0.37, -0.45, min(1.0, max(0.0, t)))
        return ((co.x + 1.0) / 2.0, (yt - spec.LIVERY_Y[0]) / (spec.LIVERY_Y[1] - spec.LIVERY_Y[0]))
    assign_uvs(o, special=spoiler_uv)
    # ceiling over the cockpit, band undersides and band inner walls: satin-coated carbon liner (box UVs kept)
    me = o.data
    me.materials.append(roof_liner_mat())
    k_lin = len(me.materials) - 1
    for p in me.polygons:
        c, nn = p.center, p.normal
        if not (-0.44 < c.y < yf - 0.004) or c.z > 1.53:
            continue
        inward = nn.x * (1.0 if c.x >= 0 else -1.0) < -0.5
        if nn.z < -0.5 or (inward and c.z < roof_ceil(c.y) + 0.001):
            p.material_index = k_lin
    out.append(o)
    build_roof_details(out, yf)


# liner trim: (y front, y rear) of the 15 mm strip, just behind the header tube as the driver sees it (the tube hides
# y > ~0.41 of the ceiling from spec.DRIVER_EYE)
TRIM_Y = (0.400, 0.385)
TRIM_PITCH = 0.09                     # button-head fastener spacing


def build_roof_details(out, yf):
    """Satin-black liner trim with button-head fasteners, orange marks on the roof front edge (front.png: under the light
    bar, x -0.10..0.0 and +0.09..+0.12)."""
    from common import cylinder, box
    mt = mats()
    y0, y1 = TRIM_Y
    yc = 0.5 * (y0 + y1)
    zc = roof_ceil(yc)
    xw = roof_half_w(yc) - BAND_D - 0.012           # ends at the band's inner step
    trim = box('body_roof_trim', (2 * xw, y0 - y1, 0.003), (0.0, yc, zc - 0.0015), material=mt['black'],
               bevel=0.001, segments=1)
    apply_transform(trim)
    assign_uvs(trim)
    set_shading(trim, 40)
    heads = []
    nb = int((2 * xw - 0.06) / TRIM_PITCH) + 1
    x0 = -(nb - 1) * TRIM_PITCH / 2
    from common import lathe
    for k in range(nb):
        h = lathe('body_roof_fastener', [(0.0048, 0.0), (0.0043, -0.0013), (0.0026, -0.0023), (0.0, -0.0026)],
                  mt['alu'], segments=8)                    # (open back: it sits on the trim)
        h.location = (x0 + k * TRIM_PITCH, yc, zc - 0.003)
        apply_transform(h)
        heads.append(h)
    from common import join
    hj = join(heads, 'body_roof_fasteners')
    set_shading(hj, 50)
    out += [trim, hj]
    # orange marks: 1 mm decal plates on the roof's front face
    marks = []
    for (xa, xb) in ((-0.100, 0.000), (0.090, 0.120)):
        xm = 0.5 * (xa + xb)
        zm = 0.5 * (roof_ceil(yf) + 0.002 + spec.ROOF_TOP_Z) + 0.003 * (1 - (xm / (spec.ROOF_WIDTH / 2)) ** 2)
        m = box('body_roof_mark', (xb - xa, 0.0012, 0.0058), (xm, yf + 0.0004, zm), material=M('orange'))
        apply_transform(m)
        marks.append(m)
    mj = join(marks, 'body_roof_marks')
    assign_uvs(mj)
    out.append(mj)


# ------------------------------------------------------------------ mirrors

def loft_rings(bm, rings, cap=True):
    """Quads between consecutive rings of BMVerts (same count), optional n-gon end caps."""
    n = len(rings[0])
    for ra, rb in zip(rings[:-1], rings[1:]):
        for i in range(n):
            i2 = (i + 1) % n
            bm.faces.new((ra[i], ra[i2], rb[i2], rb[i]))
    if cap:
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])


def safe_M(key, fallback='mirror'):
    """Palette material that needs a texture another agent provides; plain mirror if it is not there yet."""
    try:
        return M(key)
    except Exception:
        return M(fallback)


# side mirrors (front.png: carbon wedge right on the A-pillar; interior_driver_alt_red.png: short stub from the pillar,
# housing outboard over the door top). [fix r4] MIRROR_X follows the A-pillar foot (x -0.63, was -0.72): the housing
# starts 2.5 cm outboard of the pillar tube and its outer tip lands at |x| ~0.80 (front.png 0.80; r3 0.85). Its glass
# centre is ~1 cm higher and the housing is a wedge that is deeper at the pillar end (front.png at the mirror plane: top
# z 1.19-1.20, bottom 1.12 at the pillar end, 1.15 at the tip; the glass in interior_driver_alt_red.png is likewise
# taller at its inner end), so its underside clears the 1.124 door cap it now sits over by ~1 cm. The glass normal bisects the direction to
# spec.DRIVER_EYE and the view straight back along the flank; seen from the eye the glass passes inboard of the door
# post (chassis, |x| ~0.63-0.65 at y 0.30) and outboard of the A-pillar.
# [fix r6] front.png: a FACETED carbon trapezoid wedge ~0.185 x 0.10 m sitting right on the A-pillar / door-cap corner
# with no visible stalk (rear outline: an irregular hexagon - big chamfer at the inner top, small one at the outer top,
# end leaning in at the bottom; flat facets with crisp creases, flat back face carrying the ~0.16 x 0.08 glass); the
# inner end stands on a carbon foot on the door cap at the A-pillar base.
MIRROR_X = (-0.665, -0.850)             # inner / outer end (spec r6 arbiter)
MIRROR_ZC = (1.170, 1.178)              # housing centre at the inner / outer end: bottom 1.1175 inner (door cap 1.099)
MIRROR_H = (0.105, 0.085)
MIRROR_D = (0.064, 0.046)               # depth (back face -> front face) at the inner / outer end: the wedge
MIRROR_YC = 0.668                       # y of the housing's mid depth at the inner end (unrotated)
MIRROR_FOOT_Z = 1.114                   # foot base: on interior.py's int_door_roll (top 1.111, |x| 0.656-0.723) under it
MIRROR_AIM = (-0.10, -1.0, -0.025)      # [fix r6] reflected view: ~6 deg outboard, ~1.4 deg down
# (the arbiter's -0.07 = 4 deg down puts the horizon ABOVE the flat glass for the game's live mirror: from DRIVER_EYE the
# glass spans only 4.9 deg vertically (reflected elevations -6.7..-1.8 deg). -0.025 -> -4.1..+0.8 deg: horizon at 84 %
# of the glass height (upper third), the pod flank in the lower inner part. The bake (22 deg fov, aimed a further
# 1.7 deg down) shows the horizon at ~78 % and the rear tyre top in the lower part.)


def mirror_frame():
    """(glass centre, rotation, glass normal) for the left mirror: the glass normal bisects the direction to
    spec.DRIVER_EYE and the reflected view MIRROR_AIM."""
    gc = V((lerp(*MIRROR_X, 0.5), MIRROR_YC - MIRROR_D[0] / 2, lerp(*MIRROR_ZC, 0.5)))
    e = (V(spec.DRIVER_EYE) - gc).normalized()
    r = V(MIRROR_AIM).normalized()
    n = (e + r).normalized()
    yaw = math.atan2(n.x, -n.y)
    pitch = math.asin(max(-1.0, min(1.0, n.z)))
    rot = Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(-pitch, 4, 'X')
    return gc, rot, n


def mirror_outline():
    """Rear (glass-side) outline of the left housing in (x, z), unrotated: inner bottom, inner side top, top-left after
    the inner chamfer, top-right, outer chamfer end, outer bottom."""
    xi, xo = MIRROR_X

    def X(u):
        return lerp(xi, xo, u)

    def ZB(u):
        return lerp(MIRROR_ZC[0] - MIRROR_H[0] / 2, MIRROR_ZC[1] - MIRROR_H[1] / 2, u)

    def ZT(u):
        return lerp(MIRROR_ZC[0] + MIRROR_H[0] / 2, MIRROR_ZC[1] + MIRROR_H[1] / 2, u)
    return [(X(0.0), ZB(0.0)), (X(0.0), ZB(0.0) + 0.50 * MIRROR_H[0]), (X(0.17), ZT(0.17)),
            (X(0.85), ZT(0.85)), (X(1.0), ZT(1.0) - 0.034), (X(0.97), ZB(1.0))]


def build_mirrors(out):
    """Faceted carbon mirror housing on the A-pillar / door-cap corner, flat glass in its flat back face facing the
    driver, carbon foot under its inner end."""
    mt = mats()
    xi, xo = MIRROR_X
    gc, rot, _n = mirror_frame()
    y_r = MIRROR_YC - MIRROR_D[0] / 2                      # flat back face (glass side)

    def W(x, y, z):
        return gc + rot @ (V((x, y, z)) - gc)

    def depth(x):
        return lerp(MIRROR_D[0], MIRROR_D[1], (x - xi) / (xo - xi))
    rear = mirror_outline()
    front = offset2d(rear, 0.013)
    glass_rim = offset2d(rear, 0.0095)
    glass = offset2d(rear, 0.0105)
    bm = bmesh.new()
    rb = [bm.verts.new(W(x, y_r, z)) for (x, z) in rear]
    fr = [bm.verts.new(W(x, y_r + depth(x), z)) for (x, z) in front]
    gr = [bm.verts.new(W(x, y_r, z)) for (x, z) in glass_rim]
    gk = [bm.verts.new(W(x, y_r + 0.0015, z)) for (x, z) in glass_rim]
    n = len(rear)
    for i in range(n):
        i2 = (i + 1) % n
        bm.faces.new((rb[i], rb[i2], fr[i2], fr[i]))            # chamfer facets
        bm.faces.new((gr[i], gr[i2], rb[i2], rb[i]))            # back face frame around the glass
        bm.faces.new((gk[i], gk[i2], gr[i2], gr[i]))            # glass recess wall
    bm.faces.new(fr)                                            # front facet
    bm.faces.new(gk)                                            # recess floor (behind the glass)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    housing = obj_from_bmesh('body_mirror_housing', bm, [mt['carbon']], smooth=False)
    assign_uvs(housing)
    # glass: flat hexagon just behind the back face plane, UV 0..1 over its extent (u = 0 at the INNER end, v = 0 at
    # the bottom: bake_mirror.py / the game's live mirror)
    bm = bmesh.new()
    yg = y_r - 0.0008
    vs = [bm.verts.new(W(x, yg, z)) for (x, z) in glass]
    c = bm.verts.new(W(sum(p[0] for p in glass) / n, yg, sum(p[1] for p in glass) / n))
    for i in range(n):
        bm.faces.new((c, vs[i], vs[(i + 1) % n]))
    nback = rot @ V((0, -1, 0))
    for f in bm.faces:
        f.normal_update()
        if f.normal.dot(nback) < 0:
            f.normal_flip()
    uvl = bm.loops.layers.uv.new('UVMap')
    gx0, gx1 = max(p[0] for p in glass), min(p[0] for p in glass)          # inner (less negative) / outer x
    gz0, gz1 = min(p[1] for p in glass), max(p[1] for p in glass)
    rinv = rot.inverted()
    for f in bm.faces:
        for lp in f.loops:
            lc = rinv @ (lp.vert.co - gc) + gc
            lp[uvl].uv = ((lc.x - gx0) / (gx1 - gx0), (lc.z - gz0) / (gz1 - gz0))
    glass_o = obj_from_bmesh('body_mirror_glass', bm, safe_M('mirror_baked_side'), smooth=False)
    # carbon foot: tapered faceted block from the housing's inner bottom down on to the door cap (z door_top) at the
    # A-pillar base; its top is buried 6 mm in the housing
    zb0 = MIRROR_ZC[0] - MIRROR_H[0] / 2
    zc_ = max(door_top(MIRROR_YC) - 0.004, MIRROR_FOOT_Z)
    yf0, yf1 = y_r + 0.010, y_r + MIRROR_D[0] - 0.008
    top = [(xi - 0.004, yf0 + 0.006, zb0 + 0.006), (xi - 0.040, yf0 + 0.006, zb0 + 0.006),
           (xi - 0.040, yf1 - 0.004, zb0 + 0.006), (xi - 0.004, yf1 - 0.004, zb0 + 0.006)]
    bot = [(xi + 0.010, yf0 - 0.002, zc_), (xi - 0.052, yf0 - 0.002, zc_), (xi - 0.052, yf1 + 0.006, zc_),
           (xi + 0.010, yf1 + 0.006, zc_)]
    bm = bmesh.new()
    vt = [bm.verts.new(W(*p)) for p in top]
    vb = [bm.verts.new(V(p)) for p in bot]                   # the foot's base stays level on the cap
    for i in range(4):
        i2 = (i + 1) % 4
        bm.faces.new((vb[i], vb[i2], vt[i2], vt[i]))
    bm.faces.new(vt)
    bm.faces.new(vb[::-1])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    foot = obj_from_bmesh('body_mirror_foot', bm, [mt['carbon']], smooth=False)
    assign_uvs(foot)
    out += [housing, glass_o, foot]
    build_rearview(out)


RV_HOUSING = (0.430, 0.075, 0.012)     # panoramic mirror: width, height, edge radius (rear view). [fix r6] a box with
                                       # rounded edges (r5: R 30 mm capsule)
RV_GLASS = (0.414, 0.056, 0.008)       # glass inside the box's rear rim (same 'Mirror baked' + UV 0..1)
# [fix r6] raised 1.5 cm (arbiter: ~1.43, top just under the header tube in front.png) and 8 mm further back so the
# yawed driver-side end stays clear of the header and the top clears the liner trim strip (z 1.4715 at y 0.385-0.40)
RV_C0 = (0.0, 0.372, 1.425)


def build_rearview(out):
    """[fix r2] Wide panoramic rear-view mirror hanging from the windshield header tube behind the centre post
    (front.png, front_3q_right.png), mirror glass inset in its rear face, pitched 8 deg down and yawed 5 deg toward the
    driver, on a short stalk from a 20 mm clamp. Not mirrored (one per car).
    [fix r6] satin black box 430 x 75 mm with R 12 mm edges and a flat back face (r5: capsule with a domed back and
    aluminium end bosses); the glass keeps material 'Mirror baked' with UV 0..1 (the game's live mirror)."""
    from common import lathe, place, cylinder, box
    mt = mats()
    c0 = V(RV_C0)
    hx, hz, hr = RV_HOUSING[0] / 2, RV_HOUSING[1] / 2, RV_HOUSING[2]
    gx, gz, gr = RV_GLASS[0] / 2, RV_GLASS[1] / 2, RV_GLASS[2]
    rot = Matrix.Rotation(math.radians(-5.0), 4, 'Z') @ Matrix.Rotation(math.radians(8.0), 4, 'X')

    def W(x, y, z):
        return c0 + (rot @ V((x, y, z)))

    def rrect(ax, az, r, k=5):
        """Closed rounded rectangle, CCW from the right edge's middle; 4 x (k + 1) points."""
        r = max(0.0015, min(r, ax - 1e-4, az - 1e-4))
        pts = []
        for cxs, czs, a0 in ((1, 1, 0.0), (-1, 1, 0.5), (-1, -1, 1.0), (1, -1, 1.5)):
            cx_, cz_ = cxs * (ax - r), czs * (az - r)
            for j in range(k + 1):
                t = math.pi * (a0 + 0.5 * j / k)
                pts.append((cx_ + r * math.cos(t), cz_ + r * math.sin(t)))
        return pts
    # (offset of the housing outline, depth y): domed back (toward the windshield) -> body -> rear rim; then the recess
    # [fix r6] flat back face (toward the windshield) with a small rounded edge, straight body, rear rim
    prof = [(-0.0030, 0.0205), (-0.0009, 0.0196), (0.0, 0.0175), (0.0, -0.0170), (-0.0013, -0.0228),
            (-0.0035, -0.0250)]
    shapes = [(rrect(hx + d, hz + d, hr + d), y) for d, y in prof]
    shapes += [(rrect(gx, gz, gr), -0.0250), (rrect(gx, gz, gr), -0.0210)]
    bm = bmesh.new()
    rings = [[bm.verts.new(W(x, y, z)) for (x, z) in sh] for sh, y in shapes]
    n = len(rings[0])
    for ra, rb in zip(rings[:-1], rings[1:]):
        for i in range(n):
            i2 = (i + 1) % n
            bm.faces.new((ra[i], ra[i2], rb[i2], rb[i]))
    bm.faces.new(rings[0])
    glass = bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for f in bm.faces:
        f.material_index = 0
    glass.material_index = 1
    # baked panoramic reflection (textures/mirror_rear_view.png) on the glass: UV 0..1 over the glass
    uvl = bm.loops.layers.uv.new('UVMap')
    rinv = rot.inverted()
    for f in bm.faces:
        for lp in f.loops:
            lc = rinv @ (lp.vert.co - c0)
            if f.material_index == 1:
                lp[uvl].uv = ((lc.x + gx) / (2 * gx), (lc.z + gz) / (2 * gz))
            else:
                lp[uvl].uv = (lc.x * 2.0, lc.z * 2.0)
    housing = obj_from_bmesh('body_rearview_housing', bm, [mt['black'], safe_M('mirror_baked')], smooth=True, angle=40)
    set_shading(housing, 40)
    # clamp on the header tube (beside the centre-post root) and the stalk down to the housing top
    xs_ = 0.045
    tc = V((xs_, spec.ROOF_FRONT_Y, spec.A_PILLAR_TOP[2]))
    rc = spec.CAGE_TUBE_R
    clamp = lathe('body_rearview_clamp', [(rc + 0.0005, -0.010), (rc + 0.0045, -0.010), (rc + 0.0058, -0.0075),
                                          (rc + 0.0058, 0.0075), (rc + 0.0045, 0.010), (rc + 0.0005, 0.010),
                                          (rc + 0.0005, -0.010)], mt['black'], segments=20)
    place(clamp, tc, (1, 0, 0))
    apply_transform(clamp)
    set_shading(clamp, 40)
    p0 = W(xs_, -0.002, hz - 0.006)
    d = (p0 - tc)
    d.x = 0.0
    d.normalize()
    p1 = tc + d * (rc + 0.004)
    stalk = cylinder('body_rearview_stalk', 0.0065, (p1 - p0).length, material=mt['black'], segments=12)
    place(stalk, (p0 + p1) / 2, p1 - p0)
    apply_transform(stalk)
    set_shading(stalk, 40)
    out += [housing, clamp, stalk]


# ------------------------------------------------------------------ belly pan

def build_belly(out):
    """[fix r3] The chassis floor pan (top at FLOOR_Z 0.45, flush with the rail bottoms) is the belly now: the old
    centre plate (z 0.3575) and the front skid (z 0.347, ahead of the new front lower-arm pivots at z 0.49-0.50)
    are gone - side photos show nothing below ~0.48 between the wheels and the front.png nose has no skid. Only
    the rear skid under the gear case stays, behind the rear tyres' front edge (hidden in side views)."""
    mt = mats()
    bm = bmesh.new()

    def plate(pts_xy_z, th):
        """Flat-ish plate from an outline [(x, y, z), ...] (CCW from below), thickness up."""
        vb = [bm.verts.new(V(p)) for p in pts_xy_z]
        vt = [bm.verts.new(V((p[0], p[1], p[2] + th))) for p in pts_xy_z]
        n = len(vb)
        cb = bm.verts.new(sum((v.co for v in vb), V()) / n)
        ct = bm.verts.new(sum((v.co for v in vt), V()) / n)
        for i in range(n):
            i2 = (i + 1) % n
            bm.faces.new((cb, vb[i], vb[i2]))
            bm.faces.new((ct, vt[i2], vt[i]))
        for i in range(n):
            i2 = (i + 1) % n
            bm.faces.new((vb[i], vt[i], vt[i2], vb[i2]))

    rw = 0.28
    pts = [(-rw, -1.06), (-rw, -1.32), (-0.20, -1.42), (0.20, -1.42), (rw, -1.32), (rw, -1.06)]
    plate([(x, y, 0.351) for (x, y) in pts][::-1], 0.005)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    o = obj_from_bmesh('body_belly', bm, mt['black'], smooth=False)
    assign_uvs(o)
    set_shading(o, 30)
    out.append(o)


# ------------------------------------------------------------------ build

def build(C):
    out = []
    # doors (between the B-pillar and the front fender) - rolled shut lines front and rear; [fix r3] tapered plan,
    # tucked bottom, sill at SILL_Z, top rising over the belt rail toward the A-pillar
    # [fix r6] inset door with the pocket and the crease, clustered rows at the pocket's ends
    out.append(side_panel('body_door', DOOR_Y[0], DOOR_Y[1], 0, None, None, ys=door_rows(),
                          front=(0.007, 0.012), rear=(0.004, 0.006),
                          bottom=(sill_roll_r, sill_return),
                          post=clear_belt_rail, profile=door_profile))
    # [fix r4] rear pods: one inclined-shield shell from the tail face to the door shut line
    build_pod(out)
    build_front_clip(out)
    build_beak(out)
    build_cowl_vents(out)
    build_hood_bulkhead(out)
    build_tail_block(out)
    build_engine_cover(out)
    build_roof(out)
    build_mirrors(out)
    build_belly(out)
    # mirror the left-only pieces (mirrors) to the right side
    from common import mirror_x
    extra = []
    for o in out:
        if o.name.startswith('body_mirror'):
            extra.append(mirror_x(o, o.name + '_R'))
    out += extra
    C.add(out, 'static')
