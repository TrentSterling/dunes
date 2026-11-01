"""Body-side livery (livery.png) and top livery (livery_top.png) painter.

Everything is painted in metric car coordinates (y forward, z up for the sides; x right, y forward for
the tops) so the artwork lines up with the body panels whatever the image size.

Side design (right side, measured from ref/rear_3q_right.png and ref/front_3q_right.png):
  * low-contrast 6 mm twill carbon base, so from chase distance the panels read as deep gloss black;
  * hard-edged flat graphics in two tones, gloss black #050505 and charcoal #34363a: long stripes that
    follow the flow of the orange bands with sharp angled tips, outlined charcoal bands, and 7 mm black
    outline chevrons on the door;
  * the four orange bands (P1 from the pod top-rear corner beside the tail light, P2, D1 across the door,
    L1 low at the front), traced from the photos (livery_data.py), each with a thin black outline and a
    torn lower edge over a black underlay;
  * the GLX wordmark, a black sill band, a gloss black front fender, and the orange L patches of the
    cheek faces in the spare front strip of the atlas (see CHEEK).
"""
import math

import numpy as np
from PIL import Image, ImageDraw

from texlib import *  # noqa
import spec
import livery_data as LD

# r4: every canvas is painted with FOUR channels: sRGB colour + roughness (livery_rough.png / livery_top_rough.png,
# read by M('livery') / M('livery_top')). Colours are C4(rgb, roughness).
def C4(rgb, rough):
    return np.array(list(rgb) + [rough * 255.0], np.float32) / 255.0


ORANGE_F = C4(ORANGE, 0.15)
BLACK_F = C4((9, 9, 9), 0.08)       # r5: gloss black vinyl 9 sRGB (was 5): critic target 8-10 next to the 42 carbon
SMOKE_F = C4((9, 9, 10), 0.10)      # r5: smoked-black tint laid at SMOKE_A over carbon: a third tone with the weave
SMOKE_A = 0.55                      #     still showing (replaces the flat charcoal vinyl on the sides / tops)
CHARC_F = C4((47, 48, 51), 0.11)    # flat charcoal vinyl (r4: +16 over the carbon mean 30; laid at ~.8 alpha)
SHARD_F = C4((54, 55, 58), 0.11)    # hood / roof shards
GLOSS_F = C4((10, 10, 11), 0.08)    # plain gloss black panels (front fender, cheeks)
SILL_F = C4((9, 9, 10), 0.10)
WHITE_F = C4((226, 227, 229), 0.15)  # hood pinstripes
LOGO_FILL_F = C4((14, 14, 16), 0.10)
CARBON_RGB = np.array([41, 41, 42], np.float32) / 255.0   # r5: livery carbon field tows ~32 / 50, mean ~42 (critic:
                                                          # r4 30 merged with the black vinyl at game distance)
CARBON_LEVELS = 9.0                  # +- sRGB levels of tow contrast (5th..95th percentile), as carbon_base.png
CARBON_TOW_ROUGH = (0.14, 0.26, 0.28)  # warp float / weft float / gap roughness of the baked weave
TOW = 0.0035                         # r4: baked carbon tow width (m), = M('carbon') on the 1-UV/m pod decks

LOGO = dict(y0=-0.43, z0=0.537, height=0.074)   # GLX wordmark: bottom-left corner + cap height (m)

# Cheek faces (the flat front faces of the fender cheeks beside the front shocks, front.png) use the unused
# strip of livery.png in front of the body sides. A cheek vertex (x, y, z) maps like a side vertex with
#     y' = CHEEK['y0'] + CHEEK['k'] * (CHEEK['x_ref'] - |x|)        (1.40 at |x| = 0.80 .. 1.94 at |x| = 0.62)
# i.e. right cheek: u = (y' + 2.5) / 4.5, v = (z - 0.3) / 1.3 * 0.5; left cheek: u = (2.0 - y') / 4.5,
# v = 0.5 + (z - 0.3) / 1.3 * 0.5. Seen from the front, the outer edge is then on the outside on both sides.
CHEEK = dict(y0=1.40, k=3.0, x_ref=0.80)


# --------------------------------------------------------------------------- flow field

def slope_at(y):
    """Direction field of the livery streaks: dz/dy (rising toward the rear)."""
    y = np.asarray(y, np.float64)
    return np.interp(y, [-2.6, -0.62, -0.05, 0.75, 1.25, 2.1], [-0.29, -0.28, -0.17, -0.09, -0.035, -0.02])


def slope_lo(y):
    """r5: steeper field for the LOWER door / sill area (below D1): follows the tail of P1 (dz/dy ~ -0.30) and L1
    (-0.18) instead of D1, as the black streaks on the lower door in rear_3q_right / front_3q_right do."""
    y = np.asarray(y, np.float64)
    return np.interp(y, [-2.6, -0.62, 0.25, 0.60, 0.95, 2.1], [-0.29, -0.29, -0.30, -0.21, -0.15, -0.10])


Y_REF = -0.62            # both fields agree behind this; row parameter q = row height at y = Y_REF
_YS = np.linspace(-3.0, 2.5, 2201)


def _integ(fn):
    z = np.concatenate([[0], np.cumsum(fn(0.5 * (_YS[1:] + _YS[:-1])) * np.diff(_YS))])
    return z - np.interp(Y_REF, _YS, z)


_ZS = _integ(slope_at)
_ZL = _integ(slope_lo)


def stream_z(y):
    """Streamline height offset Zs(y) (integral of the slope field), 0 at Y_REF."""
    return np.interp(y, _YS, _ZS)


def stream_zl(y):
    return np.interp(y, _YS, _ZL)


def lo_weight(q):
    """Weight of the steep lower field for the streak row q (row height at Y_REF): rows under the D1 / P1 divide
    (z ~0.91 at y -0.62) follow P1's tail, rows above follow D1 (blend wide enough that rows never cross)."""
    return 1.0 - smoothstep(0.76, 1.06, np.asarray(q, np.float64))


def row_z(y, q):
    """Height of the streak row q at y."""
    a = lo_weight(q)
    return q + (1.0 - a) * stream_z(y) + a * stream_zl(y)


# --------------------------------------------------------------------------- canvases

class SideCanvas:
    """One body side painted in metric (y, z). Pixel x grows with y (front at the right)."""

    def __init__(self, W, H):
        self.W, self.H = W, H
        self.y0, self.y1 = spec.LIVERY_Y
        self.z0, self.z1 = spec.LIVERY_Z
        self.sx = W / (self.y1 - self.y0)
        self.sz = H / (self.z1 - self.z0)
        xs = self.y0 + (np.arange(W, dtype=np.float32) + 0.5) / self.sx
        zs = self.z1 - (np.arange(H, dtype=np.float32) + 0.5) / self.sz
        self.Y = np.broadcast_to(xs[None, :], (H, W))
        self.Z = np.broadcast_to(zs[:, None], (H, W))

    def px(self, y, z):
        return ((y - self.y0) * self.sx, (self.z1 - z) * self.sz)

    def polys_mask(self, polys, ss=2):
        return poly_mask((self.H, self.W), [[self.px(y, z) for y, z in p] for p in polys], ss=ss)


class TopCanvas:
    """Top surfaces: image x = car x (-1 .. +1, left side at image left), image row 0 = front
    (y = LIVERY_Y[1]), last row = rear (y = LIVERY_Y[0])."""

    def __init__(self, W, H):
        self.W, self.H = W, H
        self.y0, self.y1 = spec.LIVERY_Y
        self.sx = W / 2.0
        self.sy = H / (self.y1 - self.y0)
        xs = -1.0 + (np.arange(W, dtype=np.float32) + 0.5) / self.sx
        ys = self.y1 - (np.arange(H, dtype=np.float32) + 0.5) / self.sy
        self.X = np.broadcast_to(xs[None, :], (H, W))
        self.Yc = np.broadcast_to(ys[:, None], (H, W))

    def px(self, x, y):
        return ((x + 1.0) * self.sx, (self.y1 - y) * self.sy)

    def polys_mask(self, polys, ss=2):
        return poly_mask((self.H, self.W), [[self.px(x, y) for x, y in p] for p in polys], ss=ss)


_WT = {}          # weave tile cache: 16 tows x 64 px (lum deviation -1..1, roughness)
_WT_TOWS, _WT_PX = 16, 64


def _weave_tile():
    if 'd' not in _WT:
        N = _WT_TOWS * _WT_PX
        g = (np.arange(N, dtype=np.float32) + 0.5) / _WT_PX
        U, Vv = np.meshgrid(g, g[::-1])
        lum, _, warp = twill(U, Vv, seed=7, tows=_WT_TOWS, nfib=6)
        lo, hi = np.percentile(lum, [5, 95])
        _WT['d'] = np.clip((lum - lum.mean()) / (0.5 * (hi - lo)), -1.6, 1.4).astype(np.float32)
        fu, fv = U - np.floor(U), Vv - np.floor(Vv)
        k = (np.floor(U) + np.floor(Vv)).astype(np.int32) % 4
        acr = np.where(warp, fu, fv); alg = np.where(warp, k + fv, (k - 2) + fu)
        gap = 1.0 - np.minimum(smoothstep(0.0, 0.10, np.minimum(acr, 1 - acr)),
                               smoothstep(0.0, 0.06, np.minimum(alg, 2 - alg)))
        rw, rf, rg = CARBON_TOW_ROUGH
        r0 = np.where(warp, rw, rf)
        _WT['r'] = (r0 + (rg - r0) * gap).astype(np.float32)
        _WT['blur'] = {}
    return _WT


def _weave_sample(U, V, tow):
    """Anti-aliased weave lookup: (lum deviation, roughness) at metric U, V for tows of `tow` m. The tile is
    pre-blurred to the canvas pixel footprint (taken from the grid spacing) and sampled bilinearly."""
    T = _weave_tile()
    N = _WT_TOWS * _WT_PX
    du = float(np.abs(U[0, 1] - U[0, 0])) if U.shape[1] > 1 else tow
    dv = float(np.abs(V[1, 0] - V[0, 0])) if V.shape[0] > 1 else tow
    su = 0.45 * du / tow * _WT_PX; sv = 0.45 * dv / tow * _WT_PX         # blur sigma in tile px
    key = (round(su, 1), round(sv, 1))
    if key not in T['blur']:
        T['blur'][key] = [blur_wrap_aniso(T[c], key[1], key[0]) for c in ('d', 'r')]
    dt, rt = T['blur'][key]
    fx = np.mod(np.asarray(U, np.float64) / tow * _WT_PX, N)
    fy = np.mod(-np.asarray(V, np.float64) / tow * _WT_PX, N)
    x0 = fx.astype(np.int32); y0 = fy.astype(np.int32)
    ax = (fx - x0).astype(np.float32); ay = (fy - y0).astype(np.float32)
    x1 = (x0 + 1) % N; y1 = (y0 + 1) % N
    out = []
    for t in (dt, rt):
        out.append(t[y0, x0] * (1 - ax) * (1 - ay) + t[y0, x1] * ax * (1 - ay) +
                   t[y1, x0] * (1 - ax) * ay + t[y1, x1] * ax * ay)
    return out


def blur_wrap_aniso(a, sy, sx):
    p = int(max(sy, sx) * 3) + 2
    big = np.pad(a, ((p, p), (p, p)), mode='wrap')
    return blur(big, (sy, sx))[p:p + a.shape[0], p:p + a.shape[1]]


def carbon_base(U, V, seed=7, cloud=None):
    """Neutral twill carbon (U, V in metres) -> float RGBA (A = roughness), same tone as carbon_base.png."""
    U = np.asarray(U); V = np.asarray(V)
    U, V = np.broadcast_arrays(U, V)
    d, r = _weave_sample(U, V, TOW)
    lvl = CARBON_RGB[None, None, :] * 255.0 + CARBON_LEVELS * d[..., None]
    if cloud is not None:
        lvl = lvl * (0.96 + 0.08 * cloud[..., None])
    return np.concatenate([np.clip(lvl / 255.0, 0, 1), r[..., None]], -1).astype(np.float32)


def noise_on(cv, seed, cell_along, cell_across, octaves=3, gain=0.55):
    """Fractal noise on a SideCanvas, features stretched along the streak direction.
    cell_along / cell_across: feature size in metres."""
    qmin = min(cv.z0 - stream_z(cv.y0), cv.z0 - stream_z(cv.y1)) - 0.05
    qmax = max(cv.z1 - stream_z(cv.y1), cv.z1 - stream_z(cv.y0)) + 0.05
    res = min(cell_along, cell_across) / 4.0
    nw = int((cv.y1 - cv.y0) / res) + 2
    nh = int((qmax - qmin) / res) + 2
    scale = max(1.0, (nw * nh) / 9e6) ** 0.5
    nw, nh = int(nw / scale) + 2, int(nh / scale) + 2
    acc = np.zeros((nh, nw), np.float32); amp = 1.0; tot = 0
    for o in range(octaves):
        cx = (cv.y1 - cv.y0) / cell_along * 2 ** o
        cy = (qmax - qmin) / cell_across * 2 ** o
        acc += amp * (value_noise(nh, nw, cy, cx, seed + 31 * o) - 0.5)
        tot += amp; amp *= gain
    acc = np.clip(0.5 + acc / tot * 1.7, 0, 1)
    Q = cv.Z - stream_z(cv.Y[0])[None, :]
    fx = (cv.Y - cv.y0) / (cv.y1 - cv.y0) * (nw - 1)
    fy = (qmax - Q) / (qmax - qmin) * (nh - 1)
    x0 = np.clip(fx.astype(np.int32), 0, nw - 2); y0 = np.clip(fy.astype(np.int32), 0, nh - 2)
    ax = (fx - x0).astype(np.float32); ay = (fy - y0).astype(np.float32)
    return (acc[y0, x0] * (1 - ax) * (1 - ay) + acc[y0, x0 + 1] * ax * (1 - ay) +
            acc[y0 + 1, x0] * (1 - ax) * ay + acc[y0 + 1, x0 + 1] * ax * ay)


# --------------------------------------------------------------------------- geometry helpers

class Band:
    """An orange band from (y, z_top, z_bottom) samples."""

    def __init__(self, samples):
        s = np.asarray(samples, np.float64)
        self.y, self.top, self.bot = s[:, 0], s[:, 1], s[:, 2]

    def poly(self, grow=0.0, extend=0.0, below=None):
        """Outline polygon; grow = outward offset in z, extend = extra length at both tips (y),
        below(y) = extra depth under the bottom edge."""
        y, t, b = self.y.copy(), self.top + grow, self.bot - grow
        if below is not None:
            b = b - below(y)
        if extend:
            y = np.concatenate([[y[0] - extend], y, [y[-1] + extend]])
            t = np.concatenate([[0.5 * (t[0] + b[0])], t, [0.5 * (t[-1] + b[-1])]])
            b = np.concatenate([[t[0]], b, [t[-1]]])
        return list(zip(y, t)) + list(zip(y[::-1], b[::-1]))

    def edge(self, which, y):
        """Top / bottom edge height at y, extrapolated linearly past the tips."""
        e = self.top if which == 'top' else self.bot
        y = np.asarray(y, np.float64)
        k0 = (e[3] - e[0]) / (self.y[3] - self.y[0]); k1 = (e[-1] - e[-4]) / (self.y[-1] - self.y[-4])
        out = np.interp(y, self.y, e)
        out = np.where(y < self.y[0], e[0] + k0 * (y - self.y[0]), out)
        return np.where(y > self.y[-1], e[-1] + k1 * (y - self.y[-1]), out)


BANDS = {n: Band(getattr(LD, n)) for n in ('P1', 'P2', 'D1', 'L1')}


def strip(y0, y1, zt, zb, tip0=0.0, tip1=0.0, n=None):
    """Polygon between two edge functions zt(y) > zb(y) from y0 to y1. tip0 / tip1 (m): the top edge
    starts / ends that much later / earlier than the bottom edge (negative: the bottom edge does),
    which gives the angled, pointed ends of the livery blades."""
    n = n or max(8, int((y1 - y0) / 0.02))
    a0, b0 = (y0 + max(tip0, 0), y0 + max(-tip0, 0))
    a1, b1 = (y1 - max(tip1, 0), y1 - max(-tip1, 0))
    if a1 <= a0 + 0.005 or b1 <= b0 + 0.005:
        return None
    yt = np.linspace(a0, a1, n); yb = np.linspace(b0, b1, n)
    return list(zip(yt, zt(yt))) + list(zip(yb[::-1], zb(yb[::-1])))


def stroke(pts, width, miter_limit=4.0):
    """Polygons of a polyline stroked with mitred joins (angular, like vinyl tape)."""
    P = np.asarray(pts, np.float64); h = width / 2.0
    polys = []
    dirs = []
    for a, b in zip(P[:-1], P[1:]):
        d = b - a; d /= np.linalg.norm(d); n = np.array([-d[1], d[0]])
        dirs.append(n)
        polys.append([tuple(a + n * h), tuple(b + n * h), tuple(b - n * h), tuple(a - n * h)])
    for i in range(1, len(P) - 1):
        n1, n2 = dirs[i - 1], dirs[i]
        m = (n1 + n2) / max(1e-6, 1.0 + float(n1 @ n2))
        if np.linalg.norm(m) > miter_limit:
            m = m / np.linalg.norm(m) * miter_limit
        for s in (1, -1):
            polys.append([tuple(P[i]), tuple(P[i] + s * n1 * h), tuple(P[i] + s * m * h), tuple(P[i] + s * n2 * h)])
    return polys


def stripe_polys(rs, y_range, q_range, probs, L_range=(0.3, 1.4), row_gap=(0.002, 0.016),
                 w_mix=((0.42, 0.003, 0.008), (0.36, 0.008, 0.020), (0.22, 0.020, 0.045)), cut=7.0):
    """Procedural flat stripes along the streamlines (rows of constant q = z - Zs(y)), with sharp angled
    tips. Returns kind -> list of polygons in (y, z)."""
    kinds = list(probs); p = np.array([probs[k] for k in kinds], float); p /= p.sum()
    out = {k: [] for k in kinds}
    q = q_range[0]
    while q < q_range[1]:
        r = rs.random(); acc = 0
        for pr, lo, hi in w_mix:
            acc += pr
            if r <= acc:
                w = rs.uniform(lo, hi)
                break
        ya = y_range[0] - rs.uniform(0.0, 0.7)
        while ya < y_range[1]:
            L = rs.uniform(*L_range)
            k = kinds[rs.choice(len(kinds), p=p)]
            if k != 'none':
                qq = q
                zt = lambda y, qq=qq, w=w: row_z(y, qq) + w
                zb = lambda y, qq=qq: row_z(y, qq)
                c0 = rs.uniform(-cut, cut) * w; c1 = rs.uniform(-cut, cut) * w
                poly = strip(ya, ya + L, zt, zb, c0, c1)
                if poly:
                    out[k].append(poly)
                    if k == 'charc_ol':          # black keyline around a charcoal band
                        g = 0.0035
                        zt2 = lambda y, qq=qq, w=w: row_z(y, qq) + w + g
                        zb2 = lambda y, qq=qq: row_z(y, qq) - g
                        ol = strip(ya - 0.012, ya + L + 0.012, zt2, zb2, c0, c1)
                        if ol:
                            out.setdefault('outline', []).append(ol)
            ya += L * rs.uniform(1.05, 1.6)
        q += w + rs.uniform(*row_gap)
    return out


# --------------------------------------------------------------------------- side painter

# tear envelopes of the orange bands' lower edges (y, amount 0..1), from the photos
TEAR = {
    'P1': [(-1.88, 0.0), (-1.76, 0.75), (-1.6, 1.0), (-1.15, 1.0), (-0.98, 0.55), (-0.80, 0.35), (-0.62, 0.6),
           (-0.45, 1.0), (0.02, 1.0), (0.16, 0.5), (0.24, 0.0)],
    'P2': [(-0.70, 0.0), (-0.55, 0.35), (-0.45, 0.0)],
    'D1': [(-0.65, 0.0), (0.95, 0.0)],
    'L1': [(0.30, 0.0), (0.40, 0.85), (0.80, 1.0), (0.90, 0.6)],
}


def env_fn(name):
    e = TEAR[name]
    return lambda y: np.interp(y, [p[0] for p in e], [p[1] for p in e], left=0.0, right=0.0)


def chevrons():
    """Black outline chevrons on the door (z 0.66 .. 1.05), as polylines (y, z) after the dz nudge."""
    P1, D1, L1 = BANDS['P1'], BANDS['D1'], BANDS['L1']
    return [
        # upper door, pointing to the rear, above D1
        [(0.12, 1.046), (-0.56, 0.992), (0.12, 0.958)],
        # upper door front half, pointing forward
        [(0.14, 1.000), (0.70, 0.947), (0.14, 0.902)],
        # thin long one inside the front chevron
        [(0.26, 0.975), (0.58, 0.948), (0.26, 0.928)],
        # between D1 and the merged P band, pointing to the rear
        [(0.16, float(D1.edge('bot', 0.16)) - 0.016), (-0.30, float(D1.edge('bot', -0.30)) - 0.016),
         (0.16, 0.668)],
        # low at the front under L1, pointing forward
        [(0.24, 0.592), (0.80, 0.533), (0.24, 0.534)],
    ]


def band_distance(y, z):
    """Distance (m, in z) from point(s) (y, z) to the nearest orange band (0 inside one); far = 9."""
    y = np.asarray(y, np.float64); z = np.asarray(z, np.float64)
    out = np.full(np.broadcast(y, z).shape, 9.0)
    for b in BANDS.values():
        inside = (y > b.y[0] - 0.08) & (y < b.y[-1] + 0.08)
        t = b.edge('top', y); bo = b.edge('bot', y)
        d = np.maximum(0.0, np.maximum(z - t, bo - z))
        out = np.where(inside, np.minimum(out, d), out)
    return out


def thin_far(st, rs, near=0.05, far=0.20, p_far=0.44, zone=0.0, p_zone=0.0):
    """Drop dark stripe polygons away from the orange bands: kept if within `near` m of a band, dropped
    with probability rising to p_far at `far` m and beyond (~40 % of all dark shards go). The black
    keylines ('outline') follow the decision of the charcoal band they surround ('charc_ol')."""
    out = {}
    tot = kept = 0
    cen = lambda p: np.asarray(p, np.float64).mean(0)
    ol_keep = []                                    # (centroid, kept) of the charc_ol bands
    for k in [k for k in st if k != 'outline'] + (['outline'] if 'outline' in st else []):
        res = []
        for p in st[k]:
            c = cen(p)
            if k == 'outline' and ol_keep:
                j = int(np.argmin([np.sum((c - q) ** 2) for q, _ in ol_keep]))
                keep = ol_keep[j][1]
            else:
                dist = float(band_distance(c[0], c[1]))
                pd = p_far * float(np.clip((dist - near) / (far - near), 0, 1))
                if dist < zone:                 # r6: the blade stacks own the band surroundings
                    pd = max(pd, p_zone)
                keep = rs.random() >= pd
                if k == 'charc_ol':
                    ol_keep.append((c, keep))
            tot += 1
            if keep:
                res.append(p); kept += 1
        out[k] = res
    print('  thin_far: kept %d of %d dark shards' % (kept, tot))
    return out


class CoarseMask:
    """r6: polygons in (y, z) rasterised at `res` m (grown by `grow` m) for cheap containment tests."""

    def __init__(self, polys, grow=0.0, res=0.005, y0=-2.6, y1=2.1, z0=0.25, z1=1.65):
        self.y0, self.z1, self.res = y0, z1, res
        W = int((y1 - y0) / res) + 1; H = int((z1 - z0) / res) + 1
        m = poly_mask((H, W), [[((y - y0) / res, (z1 - z) / res) for y, z in p] for p in polys], ss=1)
        if grow > 0:
            m = dilate(m, int(round(grow / res)))
        self.m = m > 0.5
        self.C = np.concatenate([np.zeros((1, W), np.int32), np.cumsum(self.m, 0, dtype=np.int32)], 0)

    def hit_interval(self, ys, zlo, zhi):
        """Per sample y: does the z interval [zlo, zhi] touch the mask?"""
        H, W = self.m.shape
        j = np.clip(((np.asarray(ys) - self.y0) / self.res).astype(int), 0, W - 1)
        i0 = np.clip(((self.z1 - np.asarray(zhi)) / self.res).astype(int), 0, H - 1)
        i1 = np.clip(((self.z1 - np.asarray(zlo)) / self.res).astype(int), 0, H - 1)
        return (self.C[i1 + 1, j] - self.C[i0, j]) > 0

    def hit_points(self, pts):
        p = np.asarray(pts, np.float64)
        return bool(self.hit_interval(p[:, 0], p[:, 1], p[:, 1]).any())


# r6: blade stacks. (band, side, y range, first offset beyond the band edge (m; clears the designed keyline bands),
# max offset, presence near / at max offset)
STACKS = [
    ('P1', 'up', (-2.02, -0.40), 0.010, 0.27, 1.00, 0.40),   # pod, above P1 behind P2's tail, up to the pod top
    ('P2', 'up', (-1.24, -0.40), 0.010, 0.25, 1.00, 0.40),   # pod / B-pillar, above P2
    ('D1', 'up', (-0.58, 0.92), 0.046, 0.26, 1.00, 0.60),    # upper door, above D1 (blades stay out of the chevron hulls)
    ('P1', 'dn', (-1.90, 0.26), 0.034, 0.26, 0.90, 0.35),    # under P1's torn edge: pod, then the lower door
    ('D1', 'dn', (-0.58, 0.26), 0.012, 0.10, 0.80, 0.50),    # between D1 and P2 / P (fits the gap only)
    ('P2', 'dn', (-1.22, -0.42), 0.011, 0.040, 0.90, 0.90, ((1.0, 0.008, 0.014),)),   # thin ones in the P1 / P2 gap
    ('L1', 'dn', (0.26, 0.88), 0.042, 0.14, 0.90, 0.50),     # front of the door, under L1's keyline band
]
STACK_W = ((0.45, 0.010, 0.016), (0.35, 0.016, 0.026), (0.20, 0.026, 0.040))   # width mix (p, lo, hi)
STACK_GAP = (0.009, 0.018)       # carbon between the rows
STACK_L = (0.35, 0.65)           # cluster (innermost blade) length (m); outer rows are shorter (>= 18 cm)
STACK_TIP = (10.0, 15.0)         # tip angle (deg): tip length = width / tan(angle)
STACK_KEEP_OUT = [(-0.46, 0.00, 0.520, 0.635),          # GLX wordmark (y0, y1, z0, z1)
                  (0.93, 9.0, -9.0, 9.0),                # gloss black front fender
                  (-9.0, 9.0, -9.0, 0.528)]              # sill band


def _stack_limit(name, side, y):
    """Free height beyond band `name` on `side` at y: the nearest other band's facing edge minus a 1 cm margin
    (+-inf where none)."""
    b = BANDS[name]
    y = np.asarray(y, np.float64)
    if side == 'up':
        e = b.edge('top', y); lim = np.full(y.shape, np.inf)
    else:
        e = b.edge('bot', y); lim = np.full(y.shape, -np.inf)
    for n2, o in BANDS.items():
        if n2 == name:
            continue
        inside = (y >= o.y[0] - 0.02) & (y <= o.y[-1] + 0.02)
        if side == 'up':
            ob = o.edge('bot', y)
            ok = inside & (ob > e + 0.003)
            lim = np.where(ok, np.minimum(lim, ob - 0.010), lim)
        else:
            ot = o.edge('top', y)
            ok = inside & (ot < e - 0.003)
            lim = np.where(ok, np.maximum(lim, ot + 0.010), lim)
    return lim


def blade_stacks(rs, keep=None):
    """Polygons (y, z) of the r6 blade stacks (see STACKS). Each band side is covered by CLUSTERS placed one after
    another along the band: a cluster is a stack of parallel blades, the innermost one 35-65 cm long and each next
    row (1-2 cm further out) staggered shorter at both ends, so the stack tapers into a fan of sharp tips like the
    speed-line stacks in the photos. Blades share the cluster's tip style (mostly)."""
    polys = []
    for st in STACKS:
        name, side, (ya0, ya1), o0, omax, p0, p1 = st[:7]
        wmix = st[7] if len(st) > 7 else STACK_W
        pw = np.array([q[0] for q in wmix]); pw /= pw.sum()
        b = BANDS[name]
        sg = 1.0 if side == 'up' else -1.0
        edge = (lambda y, b=b: b.edge('top', y)) if side == 'up' else (lambda y, b=b: b.edge('bot', y))
        y = ya0 - rs.uniform(0.0, 0.12)
        while y < ya1 - 0.15:
            Lc = rs.uniform(*STACK_L)
            ys, ye = y, min(y + Lc, ya1 + 0.08)
            depth = omax * rs.uniform(0.75, 1.0)
            sa, sb = rs.uniform(0.0, 0.05), rs.uniform(0.01, 0.06)
            kind = int(rs.integers(4))
            o = o0 + rs.uniform(0.0, 0.004); i = 0
            while o < depth:
                k = rs.choice(len(wmix), p=pw)
                w = rs.uniform(wmix[k][1], wmix[k][2])
                ra = ys + i * sa + rs.uniform(-0.025, 0.025); rb = ye - i * sb + rs.uniform(-0.025, 0.025)
                if rb - ra < 0.18:
                    break
                pres = p0 + (p1 - p0) * float(np.clip((o - o0) / max(1e-6, omax - o0), 0, 1))
                if rs.random() < pres:
                    kd = kind if rs.random() < 0.8 else int(rs.integers(4))
                    poly = _stack_blade(rs, name, side, edge, sg, o, w, ra, rb, kd, keep)
                    if poly:
                        polys.append(poly)
                o += w + rs.uniform(*STACK_GAP); i += 1
            y = ye + rs.uniform(-0.06, 0.10)
    print('  blade_stacks: %d blades' % len(polys))
    return polys


def _stack_blade(rs, name, side, edge, sg, o, w, y0, y1, kind=None, keep=None):
    """One blade at offset o (width w) beyond the band edge, trimmed to where it fits (other bands, keep-outs)."""
    ys = np.arange(y0, y1 + 1e-6, 0.01)
    if len(ys) < 10:
        return None
    e = edge(ys)
    lo = np.where(sg > 0, e + o, e - o - w); hi = lo + w           # the blade's z extent at each y
    lim = _stack_limit(name, side, ys)
    fit = (hi <= lim) if sg > 0 else (lo >= lim)
    for (ka, kb, za, zb) in STACK_KEEP_OUT:
        fit &= ~((ys > ka - 0.02) & (ys < kb + 0.02) & (hi > za) & (lo < zb))
    if keep is not None:                              # chevron hulls: trimmed (re-tipped), never cut square
        fit &= ~keep.hit_interval(ys, lo, hi)
    # longest run that fits
    best, run, start = (0, 0), 0, 0
    for i, f in enumerate(fit):
        if f:
            if run == 0:
                start = i
            run += 1
            if run > best[1] - best[0]:
                best = (start, i + 1)
        else:
            run = 0
    if best[1] - best[0] < 15:                        # < 15 cm
        return None
    a, bb = ys[best[0]], ys[best[1] - 1]
    L = bb - a
    ang = math.radians(rs.uniform(*STACK_TIP))
    t = min(w / math.tan(ang), 0.42 * L)
    if kind is None:
        kind = int(rs.integers(4))
    t0, t1 = ((t, -t), (-t, t), (-t, -t), (t, t))[kind]   # parallelogram either lean / knife points up / down
    if sg > 0:
        zt = lambda y: edge(y) + o + w; zb = lambda y: edge(y) + o
    else:
        zt = lambda y: edge(y) - o; zb = lambda y: edge(y) - o - w
    return strip(a, bb, zt, zb, t0, t1)


def paint_side(W, H, seed):
    """Paint the RIGHT side design (front of car at image right). Returns float RGB (H, W, 3) + canvas."""
    cv = SideCanvas(W, H)
    rs = rng(seed)
    Y, Z = cv.Y, cv.Z
    y_row = Y[0]
    big = noise_on(cv, seed + 1, 0.9, 0.25, octaves=3)

    # ---- carbon base (kept as `base` so later steps can re-expose the weave inside black keylines)
    img = carbon_base(Y, Z, cloud=big)
    base = img.copy()

    # ---- procedural streaks following the flow (r5: 2-D field, see row_z): gloss black blades, and smoked-black
    # tints (SMOKE_A over the carbon, weave still visible) in place of the r4 flat charcoal vinyl
    zz = [f(y) for f in (stream_z, stream_zl) for y in (cv.y0, cv.y1)]
    q_lo = cv.z0 - max(zz) - 0.1
    q_hi = cv.z1 - min(zz) + 0.1
    st = stripe_polys(rs, (cv.y0, cv.y1), (q_lo, q_hi),
                      {'black': 0.42, 'charc': 0.13, 'charc_ol': 0.13, 'none': 0.32})
    st = thin_far(st, rng(seed + 77), zone=0.30, p_zone=0.85)   # r3: ~40 % fewer dark shards away from the bands;
    #                                           r6: only ~15 % of the random shards within 30 cm (the stacks go there)
    # r6: the door chevrons' hulls (cleared to carbon further down) keep the random shards and the blade stacks out,
    # so nothing ends in a square cut at a hull edge: shards touching a hull are dropped, stack blades re-tipped
    chev, hull = [], []
    for c in chevrons():
        chev += stroke(c, 0.008)
        hull += stroke(c, 0.030)
        hull.append(list(c))
    keep = CoarseMask(hull, grow=0.008)
    st = {k: [p for p in v if not keep.hit_points(p)] for k, v in st.items()}
    img = over(img, BLACK_F, cv.polys_mask(st.get('outline', []), ss=2) * 0.97)
    img = over(img, SMOKE_F, cv.polys_mask(st['charc'] + st['charc_ol'], ss=2) * SMOKE_A)
    img = over(img, BLACK_F, cv.polys_mask(st['black'], ss=2) * 0.97)

    P1, P2, D1, L1 = (BANDS[n] for n in ('P1', 'P2', 'D1', 'L1'))

    # ---- designed charcoal bands that run beside the orange (black keylines around them)
    # r6: the P1 / P2 keyline bands are gone (their blade stacks start right at the band, as in the photos)
    ch = [
        strip(-0.46, 0.62, lambda y: D1.edge('top', y) + 0.034, lambda y: D1.edge('top', y) + 0.020, 0.20, 0.25),
        strip(0.32, 0.93, lambda y: L1.edge('bot', y) - 0.014, lambda y: L1.edge('bot', y) - 0.030, -0.25, 0.0),
    ]
    ch = [c for c in ch if c]
    ol = [strip(-0.48, 0.64, lambda y: D1.edge('top', y) + 0.038, lambda y: D1.edge('top', y) + 0.016, 0.20, 0.25),
          strip(0.30, 0.95, lambda y: L1.edge('bot', y) - 0.010, lambda y: L1.edge('bot', y) - 0.034, -0.25, 0.0)]
    img = over(img, BLACK_F, cv.polys_mask([o for o in ol if o], ss=2) * 0.97)
    # r5: the bands inside the keylines show the carbon weave (photo: black-outlined carbon shapes), not charcoal
    chm = cv.polys_mask(ch, ss=2)
    img = over(img, base, chm * 0.95)

    # ---- r6: stacks of long straight gloss black blades parallel to the orange bands (replaces the r5 bold slashes
    # with their 5-deg brush-like tips): 25-60 cm long, 1-4 cm wide, 1-2 cm apart, sharp 10-15 deg tips, densest
    # next to each band and thinning out by ~25 cm (rear_wheel_sidepod_right / rear_3q_right). Carbon between them.
    img = over(img, BLACK_F, cv.polys_mask(blade_stacks(rng(seed + 61), keep), ss=2) * 0.97)

    # ---- designed gloss black fills between the bands (as in the photos)
    fills = [
        # between P2 / P1 and D1 behind the B-pillar end of D1
        strip(-0.66, -0.30, lambda y: np.minimum(D1.edge('bot', y), P2.edge('top', y) + 0.05) - 0.004,
              lambda y: P2.edge('top', y) + 0.004, 0.25, -0.10),
        # between D1 and L1 at the front
        strip(0.24, 0.94, lambda y: D1.edge('bot', y) - 0.004, lambda y: np.maximum(L1.edge('top', y) + 0.004, D1.edge('bot', y) - 0.05), 0.12, 0.0),   # r6: pointed rear end (was square)
        # black blade under the charcoal band above D1
        strip(-0.40, 0.48, lambda y: D1.edge('top', y) + 0.013, lambda y: D1.edge('top', y) + 0.006, 0.12, 0.20),
    ]
    img = over(img, BLACK_F, cv.polys_mask([f for f in fills if f], ss=2) * 0.97)

    # ---- black outline chevrons (7 mm tape) on the door
    clear = cv.polys_mask(hull, ss=1)
    rows = np.where(clear.max(1) > 0)[0]; cols = np.where(clear.max(0) > 0)[0]
    r0, r1, k0, k1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    patch = carbon_base(Y[r0:r1, k0:k1], Z[r0:r1, k0:k1], cloud=big[r0:r1, k0:k1])
    img[r0:r1, k0:k1] = over(img[r0:r1, k0:k1], patch, clear[r0:r1, k0:k1] * 0.92)
    img = over(img, BLACK_F, cv.polys_mask(chev, ss=3) * 0.97)

    # ---- orange bands: black outline + black underlay below the torn edges, then the orange
    under = []
    for name, b in BANDS.items():
        e = env_fn(name)
        under.append(b.poly(grow=0.0035, extend=0.010, below=lambda y, e=e: 0.026 * e(y)))
    img = over(img, BLACK_F, cv.polys_mask(under, ss=3) * 0.97)

    # r3: heavier dry-brush tear on the lower edges - chunky bites up to ~18 mm deep (features ~30 x 14 mm
    # plus a little fine detail), short orange drips hanging below the edge between the bites, and a few
    # isolated orange flecks on the black underlay below (rear_wheel_sidepod_right.png)
    band_m = cv.polys_mask([b.poly() for b in BANDS.values()], ss=3)
    chunk = noise_on(cv, seed + 11, 0.030, 0.014, octaves=2, gain=0.5)
    detail = noise_on(cv, seed + 12, 0.010, 0.004, octaves=2)
    blob = noise_on(cv, seed + 13, 0.011, 0.006, octaves=2, gain=0.45)
    tn = chunk * 0.78 + detail * 0.22
    bite = np.zeros((H, W), np.float32); fleck = np.zeros((H, W), np.float32)
    for name, b in BANDS.items():
        env = env_fn(name)(y_row)
        bz = np.interp(y_row, b.y, b.bot, left=np.nan, right=np.nan)
        tz = np.interp(y_row, b.y, b.top, left=np.nan, right=np.nan)
        cols = np.where(~np.isnan(bz) & (env > 0.01))[0]
        if len(cols) == 0:
            continue
        c0, c1 = cols.min(), cols.max() + 1
        Zc = Z[:, c0:c1]; d = Zc - bz[None, c0:c1]; thick = (tz - bz)[None, c0:c1]
        e = env[None, c0:c1]
        reach = np.minimum(0.018 * e, thick * 0.60) + 1e-6
        tc = tn[:, c0:c1]; bc = blob[:, c0:c1]
        rel = np.clip(d / reach, 0, 1)
        bt = (d > -0.001) & (d < reach) & (tc > 0.46 + 0.36 * rel ** 0.8)
        drip = (d < 0) & (d > -0.007 * e) & (tc < 0.40 + 40.0 * d)          # orange hanging below the edge
        isl = (d < -0.004) & (d > -0.024 * e) & (bc > 0.80 - 4.0 * d)       # loose flecks further down
        bite[:, c0:c1] = np.maximum(bite[:, c0:c1], bt)
        fleck[:, c0:c1] = np.maximum(fleck[:, c0:c1], drip | isl)
    orange_a = np.clip(band_m * (1 - bite) + fleck * 0.97, 0, 1)
    orange_a = blur(orange_a, 0.45)
    img = over(img, ORANGE_F[None, None, :] * np.concatenate([np.repeat(0.975 + 0.03 * big[..., None], 3, -1),
                                                              np.ones_like(big)[..., None]], -1), orange_a)

    # black pinstripe inside the front half of D1, curling up at its end (front_3q_right / rear_3q_right)
    ys = np.linspace(0.02, 0.60, 70)
    zc = D1.edge('bot', ys) + 0.46 * (D1.edge('top', ys) - D1.edge('bot', ys))
    zc = zc + np.where(ys > 0.50, (ys - 0.50) ** 2 * 2.6, 0.0)
    t = (ys - ys[0]) / (ys[-1] - ys[0]); w = 0.0024 * np.minimum(1, np.minimum(t / 0.15, (1 - t) / 0.25))
    pin = list(zip(ys, zc + w)) + list(zip(ys[::-1], (zc - w)[::-1]))
    img = over(img, BLACK_F, cv.polys_mask([pin], ss=3) * 0.95)

    # ---- front fender ahead of the door: gloss black with a few charcoal streaks
    front = smoothstep(0.935, 0.975, Y)
    img = over(img, GLOSS_F, front * 0.92)
    sf = stripe_polys(rs, (0.9, 1.4), (q_lo, q_hi), {'charc': 0.35, 'none': 0.65}, L_range=(0.2, 0.5),
                      row_gap=(0.02, 0.06), w_mix=((1.0, 0.003, 0.012),))
    img = over(img, base, cv.polys_mask(sf['charc'], ss=2) * front * 0.75)     # r5: carbon streaks through the black

    # ---- black lower sill band + a carbon keyline on top of it
    img = over(img, SILL_F, (1 - smoothstep(0.503, 0.507, Z)) * 0.95)
    img = over(img, base, (smoothstep(0.507, 0.509, Z) - smoothstep(0.513, 0.515, Z)) * 0.8)

    img = paint_cheek(img, cv)
    return img, cv


def paint_cheek(img, cv):
    """The orange L patches of the right cheek face, seen from the front (outer edge on the left), in the
    spare strip y' = 1.40 .. 2.0 of the side canvas (see CHEEK)."""
    c0 = int((1.37 - cv.y0) * cv.sx)
    sub = img[:, c0:]
    Y, Z = cv.Y[:, c0:], cv.Z[:, c0:]
    k, y0 = CHEEK['k'], CHEEK['y0']
    reg = smoothstep(1.375, 1.395, Y)
    base = over(carbon_base((Y - y0) / k, Z), GLOSS_F, np.ones_like(Y) * 0.75)
    sub = sub * (1 - reg[..., None]) + base * reg[..., None]
    yp = lambda s: y0 + k * s                        # s = 0.80 - |x| (0.03 at the outer edge .. 0.18 inner)
    ztop = lambda s: 1.040 + 0.375 * s               # top edge of the face (brow) at s
    s = np.linspace(0.0, 0.20, 24)
    patches = [
        # stroke along the top edge, thick at the outer edge, thinning inward
        list(zip(yp(s), ztop(s) - 0.008)) + list(zip(yp(s[::-1]), (ztop(s) - 0.052 + 0.10 * s)[::-1])),
        # down the outer edge (the L)
        [(yp(0.0), ztop(0.0)), (yp(0.058), ztop(0.0) - 0.01), (yp(0.058), 0.975), (yp(0.0), 0.945)],
        # bottom wedge from the outer edge, tapering inward
        [(yp(0.0), 0.805), (yp(0.040), 0.797), (yp(0.150), 0.758), (yp(0.165), 0.752), (yp(0.150), 0.746),
         (yp(0.040), 0.738), (yp(0.0), 0.736)],
    ]
    shift = lambda polys: [[(cv.px(y, z)[0] - c0, cv.px(y, z)[1]) for y, z in p] for p in polys]
    shape = Y.shape
    m = poly_mask(shape, shift(patches), ss=3)
    blackk = poly_mask(shape, shift([[(yp(0.0), 0.814), (yp(0.16), 0.762), (yp(0.16), 0.740), (yp(0.0), 0.726)]]), ss=2)
    sub = over(sub, BLACK_F, blackk * reg * 0.95)
    sub = over(sub, ORANGE_F, m * reg)
    img[:, c0:] = sub
    return img


# --------------------------------------------------------------------------- livery.png

def make_livery(size=4096, ss=1.5, seed=20):
    """livery.png: top half = LEFT side seen from the left (front at image left),
    bottom half = RIGHT side seen from the right (front at image right)."""
    W = int(size * ss); H = int(size * ss / 2)
    L = LOGO
    _, adv = trx_letter_polys()
    word_w = (adv + 0.30) * L['height']
    halves = []
    for side in ('left', 'right'):
        img, cv = paint_side(W, H, seed + (0 if side == 'right' else 100))
        if side == 'right':
            fill, outl, _ = trx_masks((H, W), cv.px, (L['y0'], L['z0']), L['height'], slant=0.30, outline=0.085, ss=3)
        else:
            img = img[:, ::-1].copy()            # mirror: front of the car at image left
            yfront = L['y0'] + word_w

            def to_px(X, Zv):
                x, yy = cv.px(yfront - (X - L['y0']), Zv)
                return (W - x, yy)
            fill, outl, _ = trx_masks((H, W), to_px, (L['y0'], L['z0']), L['height'], slant=0.30, outline=0.085, ss=3)
        img = over(img, LOGO_FILL_F, fill * 0.97)
        img = over(img, ORANGE_F, outl)
        halves.append(img)
    full = np.concatenate(halves, 0)       # top = left side, bottom = right side
    return split_rgb_rough(full, (size, size))


def split_rgb_rough(full, size, rough_div=2):
    """4-channel canvas -> (RGB image resized to `size` (w, h), L roughness image at size / rough_div).
    The roughness map is half size (2048 for livery.png): the tow-scale variation is sub-pixel at game distances
    and a full-size map costs ~2.8 MB of JPEG in the GLB; the 3x LANCZOS reduction pre-filters the weave."""
    rgb8 = (np.clip(full[..., :3], 0, 1) * 255 + 0.5).astype(np.uint8)
    r8 = (np.clip(full[..., 3], 0, 1) * 255 + 0.5).astype(np.uint8)
    rs = (size[0] // rough_div, size[1] // rough_div)
    return (Image.fromarray(rgb8).resize(size, Image.LANCZOS),
            Image.fromarray(r8, 'L').resize(rs, Image.LANCZOS))


# --------------------------------------------------------------------------- livery_top.png

def top_blades(rs, xr, yr, n, wr, lr, angle_deg=(0, 0), kinds=None):
    """Random long hard-edged blades running along y inside the box xr x yr: kind -> polys (x, y)."""
    kinds = kinds or {'black': 0.6, 'grey': 0.4}
    ks = list(kinds); pr = np.array([kinds[k] for k in ks]); pr = pr / pr.sum()
    out = {k: [] for k in ks}
    for _ in range(n):
        L = rs.uniform(*lr); w = rs.uniform(*wr)
        cx = rs.uniform(*xr); cy = rs.uniform(*yr)
        a = math.radians(rs.uniform(*angle_deg))
        d = np.array([math.sin(a), math.cos(a)]); nrm = np.array([d[1], -d[0]])
        A = np.array([cx, cy]) - d * L / 2; B = np.array([cx, cy]) + d * L / 2
        # angled cut ends: a parallelogram whose ends are sheared by up to 6 widths
        sa = rs.uniform(-6, 6) * w; sb = rs.uniform(-6, 6) * w
        out[ks[rs.choice(len(ks), p=pr)]].append([tuple(A + nrm * w / 2 + d * max(sa, 0)), tuple(B + nrm * w / 2 - d * max(sb, 0)),
                                                   tuple(B - nrm * w / 2 - d * max(-sb, 0)), tuple(A - nrm * w / 2 + d * max(-sa, 0))])
    return out


def torn(mask, cvsx, seed, grow_m=0.012, thr=0.58, H=None, W=None):
    """Ragged edge: grow a mask by ~grow_m metres where noise allows (torn vinyl look)."""
    H, W = mask.shape
    n = value_noise(H, W, H / (0.02 * cvsx), W / (0.03 * cvsx), seed) * 0.7 + \
        value_noise(H, W, H / (0.006 * cvsx), W / (0.009 * cvsx), seed + 1) * 0.3
    g = dilate(mask, max(1, int(grow_m * cvsx)))
    return np.clip(mask + (g - mask) * (n > thr), 0, 1)


# hood artwork (x, y) -- car's LEFT is x < 0, so in front.png (seen from the front) the wedge shows right of centre.
# r5: re-traced on the r5 beak (spec.HOOD_BEAK_HALF_W) by back-projecting front.png through its solved camera onto the
# built body's 'Livery top' faces (ray cast; top_uv texel = hit (x, y)). The orange is a wedge: ~0.13 m wide just ahead
# of the cowl vents (x -0.09 .. +0.04), its outer edge running out along the beak's left crease and its inner edge
# slanting across, so that in front.png it ends in a point at lower right (photo u 866, v 414 = plan (-0.15, 1.35)).
# Behind the body's vent step (y 1.06-1.10) it continues over the raised deck to the cowl edge (x -0.08..+0.044, the orange
# seen above the centre vent, split by a thin black line). A torn black slash crosses it just ahead of the centre vent
# (upper-left in the photo) and a thin black line cuts off its tip. Re-checked on body r5 v2 (vent step) at 23:55.
HOOD_WEDGE = [(0.044, 0.770), (0.044, 1.050), (0.040, 1.090), (0.024, 1.135), (0.000, 1.160), (-0.016, 1.200),
              (-0.034, 1.245), (-0.058, 1.295), (-0.082, 1.340), (-0.098, 1.352), (-0.128, 1.360), (-0.156, 1.368),
              (-0.150, 1.320), (-0.140, 1.270), (-0.126, 1.210), (-0.112, 1.160), (-0.102, 1.110), (-0.084, 1.060),
              (-0.080, 1.000), (-0.080, 0.900), (-0.082, 0.770)]
HOOD_SLASH = [(0.048, 1.104), (0.048, 1.130), (-0.022, 1.184), (-0.036, 1.168)]   # torn black slash just ahead of the
                                                                                  # centre vent (body r5 vent step y 1.06-1.10)
HOOD_LINE = [(-0.140, 1.372), (-0.104, 1.322), (-0.070, 1.268)]       # thin black line across the tip (5 mm)
HOOD_KEYLINE = [(-0.004, 0.770), (-0.004, 1.000), (-0.006, 1.064)]   # thin black line in the orange behind the centre vent
HOOD_BLACK = [
    # the gloss black nose: everything ahead of the wedge's inner edge on the beak, out to a diagonal on the right half
    [(0.040, 1.090), (0.062, 1.160), (0.080, 1.260), (0.094, 1.380), (0.104, 1.500), (0.110, 1.600), (0.080, 1.700),
     (-0.080, 1.700), (-0.130, 1.600), (-0.150, 1.500), (-0.162, 1.420), (-0.160, 1.372), (-0.128, 1.366),
     (-0.098, 1.358), (-0.082, 1.346), (-0.058, 1.301), (-0.034, 1.251), (-0.016, 1.206), (0.000, 1.166),
     (0.024, 1.141)],
    # black blade hugging the wedge's outer edge, then running out on to the wing valley
    [(-0.104, 0.900), (-0.118, 0.900), (-0.116, 1.000), (-0.124, 1.100), (-0.140, 1.180), (-0.160, 1.260),
     (-0.174, 1.330), (-0.178, 1.380), (-0.166, 1.380), (-0.154, 1.310), (-0.140, 1.240), (-0.124, 1.170),
     (-0.108, 1.090), (-0.100, 1.000)],
    # two diagonal blades on the beak's left side / valley beyond it
    [(-0.150, 1.020), (-0.165, 1.020), (-0.200, 1.200), (-0.236, 1.330), (-0.222, 1.330), (-0.186, 1.200)],
    [(-0.190, 0.960), (-0.200, 0.960), (-0.250, 1.150), (-0.290, 1.280), (-0.282, 1.280), (-0.240, 1.150)],
    # black chevron on the left wing near its front edge
    [(-0.300, 1.200), (-0.250, 1.300), (-0.330, 1.320), (-0.345, 1.305), (-0.275, 1.292), (-0.312, 1.210)],
    # right half of the beak: carbon with black blades along the crease
    [(0.070, 0.960), (0.090, 0.960), (0.128, 1.150), (0.146, 1.300), (0.134, 1.300), (0.110, 1.150)],
    [(0.160, 0.960), (0.185, 0.960), (0.200, 1.080), (0.188, 1.080)],
    [(0.118, 1.200), (0.170, 1.220), (0.182, 1.300), (0.150, 1.290)],
    [(0.210, 1.010), (0.222, 1.010), (0.262, 1.200), (0.300, 1.330), (0.290, 1.330), (0.250, 1.200)],
]
HOOD_PINS = [   # white / silver pinstripe "claws" beside the wedge tip (front_3q_right)
    [(-0.120, 1.300), (-0.146, 1.372), (-0.150, 1.440), (-0.138, 1.520)],
    [(-0.150, 1.300), (-0.170, 1.390), (-0.158, 1.480)],
]


def make_livery_top(W=2048, H=4096, ss=1.5, seed=40):
    Wc, Hc = int(W * ss), int(H * ss)
    cv = TopCanvas(Wc, Hc)
    rs = rng(seed)
    X, Yc = cv.X, cv.Yc
    cloud = value_noise(Hc, Wc, 6, 3, seed + 3)
    img = carbon_base(X, Yc, cloud=cloud)
    cv.base = img.copy()            # r5: plain carbon, re-exposed by the spoiler / deck blades

    # ---- hard-edged blades over the rear deck / roof (y < 0.7)
    # r5: the 'grey' blades are smoked-black tints over the carbon (SMOKE_A), not flat charcoal vinyl
    b = top_blades(rs, (-0.95, 0.95), (-2.5, 0.7), 34, (0.012, 0.06), (0.8, 2.0), (-3, 3), {'black': 0.6, 'grey': 0.4})
    img = over(img, SMOKE_F, cv.polys_mask(b['grey'], ss=2) * SMOKE_A)
    img = over(img, BLACK_F, cv.polys_mask(b['black'], ss=2) * 0.95)
    b = top_blades(rs, (-0.95, 0.95), (-2.5, 0.7), 30, (0.003, 0.007), (0.6, 1.6), (-2, 2), {'black': 0.75, 'grey': 0.25})
    img = over(img, SMOKE_F, cv.polys_mask(b['grey'], ss=2) * SMOKE_A)
    img = over(img, BLACK_F, cv.polys_mask(b['black'], ss=2) * 0.95)

    # ---- fender crowns (outside the hood shield): carbon with gloss black and grey shards along y
    for sx in (-1, 1):
        b = top_blades(rs, (0.36, 0.80), (0.85, 1.30), 14, (0.010, 0.05), (0.25, 0.6), (-14, -4), {'black': 0.6, 'grey': 0.4})
        polys = {k: [[(sx * x, y) for x, y in p] for p in v] for k, v in b.items()}
        img = over(img, SMOKE_F, cv.polys_mask(polys['grey'], ss=2) * SMOKE_A)      # r5: no grey vinyl on the wings
        img = over(img, BLACK_F, cv.polys_mask(polys['black'], ss=2) * 0.95)
    crown = smoothstep(0.62, 0.72, Yc) * smoothstep(0.31, 0.36, np.abs(X))
    img = over(img, GLOSS_F, crown * 0.35)

    # ---- hood (r5): gloss black shards (no grey vinyl: the carbon shows between them), the orange wedge with a lightly
    # torn inner edge, a torn black slash, two thin black lines and the silver claws at the tip
    img = over(img, GLOSS_F, cv.polys_mask(HOOD_BLACK, ss=3) * 0.97)
    wm = cv.polys_mask([HOOD_WEDGE], ss=3)
    tn = value_noise(Hc, Wc, Hc / (0.025 * cv.sx), Wc / (0.010 * cv.sx), seed + 9) * 0.7 + \
        value_noise(Hc, Wc, Hc / (0.008 * cv.sx), Wc / (0.004 * cv.sx), seed + 10) * 0.3
    inner = cv.polys_mask([[(0.046, 1.04), (0.030, 1.04), (-0.010, 1.20), (-0.070, 1.33), (-0.050, 1.33),
                            (0.010, 1.20)]], ss=1)
    wm = np.clip(wm - inner * (tn > 0.66), 0, 1)
    img = over(img, ORANGE_F, blur(wm, 0.45))
    sl = cv.polys_mask([HOOD_SLASH], ss=2)
    img = over(img, BLACK_F, torn(sl, cv.sx, seed + 12, 0.008, 0.6) * 0.96)
    lines = stroke(HOOD_LINE, 0.005) + stroke(HOOD_KEYLINE, 0.006)
    img = over(img, BLACK_F, cv.polys_mask(lines, ss=3) * 0.95)
    pins = []
    for p in HOOD_PINS:
        pins += stroke(p, 0.004)
    img = over(img, WHITE_F, cv.polys_mask(pins, ss=3) * 0.85)

    # r5: the cowl vents are NOT painted any more - body models them as real recessed geometry (paint_vents() is kept
    # below for reference only)

    img = paint_spoiler(img, cv, seed)

    # ---- r3: rear deck / engine-cover panel racing stripes (replaces the 45-deg hazard firewall strip)
    img = paint_deck(img, cv, seed)

    # ---- P1 runs off the pod top at the tail corner: its tip shows on the tail-block top
    for sx in (-1, 1):
        tip = [(sx * 0.818, -2.03), (sx * 0.818, -1.88), (sx * 0.790, -2.00)]
        img = over(img, ORANGE_F, cv.polys_mask([tip], ss=2) * 0.95)

    return split_rgb_rough(img, (W, H))


# Rear deck / engine-cover panel stripes (rear.png, rear_3q_right.png, seat_closeup.png). Window agreed with body:
# |x| < 0.50, y -0.88 .. -1.45 (top_uv). x positions at the window's mid-length y = DECK['ym']; every edge leans
# DECK['lean'] m toward -x per metre toward the rear.
DECK = dict(y0=-1.45, y1=-0.88, xw=0.50, ym=-1.16, lean=0.085,
            left=(-0.235, -0.105),      # plain orange, ~0.13 m
            mid=(-0.105, -0.025),       # gloss black with dark-grey slashes, ~0.08 m
            right=(-0.025, 0.075),      # orange, ~0.10 m, torn black flame flecks along its right edge
            rblack=(0.075, 0.150))      # black band with grey slashes outboard of the right stripe


def paint_deck(img, cv, seed):
    X, Yc = cv.X, cv.Yc
    D = DECK
    y0, y1 = D['y0'], D['y1']
    reg = ((Yc > y0) & (Yc < y1) & (np.abs(X) < D['xw'])).astype(np.float32)
    reg = blur(reg, 0.8)
    sh = lambda y: -D['lean'] * (D['ym'] - y)          # x shift of the edges at y (toward -x at the rear)
    # deck base: carbon, the random roof/deck blades cleared
    img = img * (1 - reg[..., None]) + carbon_base(X, Yc) * reg[..., None]

    def band(xa, xb, ya=y0 - 0.02, yb=y1 + 0.02):
        return [(xa + sh(yb), yb), (xb + sh(yb), yb), (xb + sh(ya), ya), (xa + sh(ya), ya)]

    def slash(xc, w, k, ya=y0 - 0.02, yb=y1 + 0.02):
        """A slanted blade crossing the deck: k = extra x lean over its length."""
        return [(xc - k / 2 + sh(yb), yb), (xc - k / 2 + w + sh(yb), yb), (xc + k / 2 + w + sh(ya), ya),
                (xc + k / 2 + sh(ya), ya)]
    # black leaning blades on the carbon left of the left stripe, a few charcoal ones beyond
    blk = [slash(-0.330, 0.040, 0.10), slash(-0.290, 0.018, 0.06), slash(-0.395, 0.022, 0.12),
           slash(-0.262, 0.016, 0.03)]
    chs = [slash(-0.455, 0.030, 0.10), slash(-0.360, 0.012, 0.08), slash(0.190, 0.020, -0.05),
           slash(0.235, 0.035, -0.08), slash(0.300, 0.014, -0.06)]
    img = over(img, SMOKE_F, cv.polys_mask(chs, ss=2) * reg * SMOKE_A)       # r5: smoked tint, not charcoal
    img = over(img, BLACK_F, cv.polys_mask(blk, ss=2) * reg * 0.96)
    # the two black bands (middle + outboard right) with dark-grey slashes on them
    bands_k = cv.polys_mask([band(*D['mid']), band(*D['rblack'])], ss=3)
    img = over(img, BLACK_F, bands_k * reg * 0.97)
    gs = [slash(-0.090, 0.012, 0.05), slash(-0.062, 0.020, 0.07), slash(-0.040, 0.008, 0.03),
          slash(0.090, 0.016, 0.06), slash(0.118, 0.010, 0.04)]
    img = over(img, C4((48, 49, 52), 0.11), cv.polys_mask(gs, ss=2) * bands_k * reg * 0.95)
    # orange stripes
    om = cv.polys_mask([band(*D['left']), band(*D['right'])], ss=3) * reg
    # torn black flame flecks along the right stripe's right edge: chunky bites up to ~35 mm into the stripe,
    # elongated fore-aft (flame licks pointing forward), plus a few loose black flecks inside
    xr = D['right'][1] + sh(Yc)                          # right edge of the right stripe at each row
    dx = xr - X                                          # distance inside the stripe from its right edge
    n1 = value_noise(cv.H, cv.W, cv.H / (0.060 * cv.sy), cv.W / (0.024 * cv.sx), seed + 51)
    n2 = value_noise(cv.H, cv.W, cv.H / (0.014 * cv.sy), cv.W / (0.007 * cv.sx), seed + 52)
    tn = 0.85 * n1 + 0.15 * n2
    # black flame shapes INSIDE the stripe, in a lane 5..45 mm from its right edge (a thin orange margin stays
    # on the right of most of them, as in rear.png), plus a few loose flecks
    w = np.abs(dx - 0.023) / 0.019
    flame = (dx > 0.004) & (dx < 0.044) & (tn > 0.47 + 0.33 * w ** 2)
    loose = (dx > 0.008) & (dx < 0.055) & (n2 > 0.86) & (n1 > 0.42)
    tear = (flame | loose).astype(np.float32)
    # the left stripe: a clean, slightly ragged left edge only (it is plain in the photos)
    img = over(img, ORANGE_F, blur(om * (1 - tear), 0.45))
    return img


VENTS = dict(xs=[(-0.075, 0.075), (0.105, 0.275), (-0.275, -0.105)], y0=0.795, y1=0.862, frame=0.012, r=0.012)


def paint_vents(img, cv):
    V_ = VENTS
    y0, y1, fr, rr = V_['y0'], V_['y1'], V_['frame'], V_['r']
    # work in the window around the vents only
    xa_, ya_ = cv.px(min(a for a, _ in V_['xs']) - 0.01, y1 + 0.01)
    xb_, yb_ = cv.px(max(b for _, b in V_['xs']) + 0.01, y0 - 0.01)
    r0, r1, c0, c1 = int(ya_), int(yb_) + 1, int(xa_), int(xb_) + 1
    full = img
    img = full[r0:r1, c0:c1]
    X, Yc = cv.X[r0:r1, c0:c1], cv.Yc[r0:r1, c0:c1]

    def rrect(xa, xb, ya, yb, r):
        """Rounded rectangle mask (signed-distance, anti-aliased)."""
        cx, cy = 0.5 * (xa + xb), 0.5 * (ya + yb)
        hx, hy = 0.5 * (xb - xa) - r, 0.5 * (yb - ya) - r
        qx = np.maximum(np.abs(X - cx) - hx, 0); qy = np.maximum(np.abs(Yc - cy) - hy, 0)
        d = np.sqrt(qx * qx + qy * qy) - r
        return np.clip(0.5 - d * cv.sx, 0, 1)
    outer = np.zeros_like(X); inner = np.zeros_like(X)
    for xa, xb in V_['xs']:
        outer = np.maximum(outer, rrect(xa, xb, y0, y1, rr))
        inner = np.maximum(inner, rrect(xa + fr, xb - fr, y0 + fr, y1 - fr, max(0.003, rr - fr)))
    img = over(img, C4((6, 6, 7), 0.10), outer * 0.98)                 # gloss black frame + dark recess
    hexm = hex_pattern(r1 - r0, c1 - c0, cell_px=0.009 * cv.sx, hole=0.58)  # 1 in the holes
    sheen = 0.92 + 0.08 * (1 - np.clip((Yc - y0) / (y1 - y0), 0, 1))
    metal = C4((165, 167, 171), 0.38)
    img = over(img, metal[None, None, :] * np.concatenate([np.repeat(sheen[..., None], 3, -1),
                                                           np.ones_like(sheen)[..., None]], -1), inner * (1 - hexm))
    img = over(img, C4((14, 14, 15), 0.6), inner * hexm * 0.9)          # holes: dark
    full[r0:r1, c0:c1] = img
    return full


def paint_spoiler(img, cv, seed):
    """Roof rear spoiler block (y -0.715 .. -0.37 in livery_top; body.py maps it over the kicked-up top and
    the sloped rear face): gloss black with charcoal diagonal blades and TWO wide orange bands, each crossed
    by black torn diagonal stripes (rear.png, rear_3q_right.png)."""
    X, Yc = cv.X, cv.Yc
    y0, y1 = -0.725, -0.36
    reg = (Yc > y0) & (Yc < y1) & (np.abs(X) < 0.70)
    img = over(img, GLOSS_F, reg * 0.95)
    lean = 0.06                                         # band edges shift +x by this much from top to bottom

    def band(xa, xb, ya=y0, yb=y1):
        return [(xa - lean * (yb - (-0.55)) / 0.35, yb), (xb - lean * (yb - (-0.55)) / 0.35, yb),
                (xb - lean * (ya - (-0.55)) / 0.35, ya), (xa - lean * (ya - (-0.55)) / 0.35, ya)]
    # charcoal diagonal blades on the black outboard of the bands
    blades = [band(-0.50, -0.465), band(-0.43, -0.37), band(-0.34, -0.315), band(0.29, 0.33), band(0.37, 0.43),
              band(0.47, 0.50), band(-0.025, 0.01)]
    img = over(img, cv.base, cv.polys_mask(blades, ss=2) * reg * 0.9)        # r5: carbon showing through the black
    bands = [band(-0.235, -0.068), band(0.058, 0.222)]
    bm = cv.polys_mask(bands, ss=3) * reg
    img = over(img, ORANGE_F, bm)
    # black torn diagonals crossing the bands (one bold, one thin crack each), a notch at the top of the
    # left band and a ragged right edge on the right band (rear.png, rear_3q_right.png)
    def diag(xc, w, k=0.10):
        return [(xc - k, y1), (xc - k + w, y1), (xc + k + w, y0), (xc + k, y0)]
    bold = cv.polys_mask([diag(0.082, 0.028),
                          [(-0.100, y1), (-0.068, y1), (-0.068, -0.462), (-0.092, -0.468)]], ss=2)
    thin = cv.polys_mask([diag(-0.150, 0.006, 0.07), diag(0.168, 0.007, 0.12)], ss=2)
    dm = np.maximum(torn(bold, cv.sx, seed + 31, 0.006, 0.62), thin)
    img = over(img, BLACK_F, dm * bm * 0.96)
    edge = cv.polys_mask([band(0.216, 0.240)], ss=2)
    img = over(img, BLACK_F, torn(edge, cv.sx, seed + 33, 0.010, 0.55) * reg * bm * 0.96)
    return img


def hex_pattern(H, W, cell_px, hole=0.7, angle=0.0):
    """Hexagonal perforation mask: 1 inside the holes, 0 on the metal. cell_px = hole pitch."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    s = cell_px
    qf = (math.sqrt(3) / 3 * xx - 1.0 / 3 * yy) / (s / math.sqrt(3))
    rf = (2.0 / 3 * yy) / (s / math.sqrt(3))
    xc = qf; zc = rf; yc = -xc - zc
    rx = np.round(xc); ry = np.round(yc); rz = np.round(zc)
    dx = np.abs(rx - xc); dy = np.abs(ry - yc); dz = np.abs(rz - zc)
    m1 = (dx > dy) & (dx > dz); m2 = (~m1) & (dy > dz)
    rx = np.where(m1, -ry - rz, rx); ry = np.where(m2, -rx - rz, ry); rz = np.where(~m1 & ~m2, -rx - ry, rz)
    cx = (s / math.sqrt(3)) * (math.sqrt(3) * rx + math.sqrt(3) / 2 * rz)
    cy = (s / math.sqrt(3)) * (1.5 * rz)
    px = np.abs(xx - cx); py = np.abs(yy - cy)
    d = np.maximum(px * (math.sqrt(3) / 2) + py * 0.5, py)
    r = s * 0.5 * hole
    return 1.0 - smoothstep(r - 0.75, r + 0.75, d)
