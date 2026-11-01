"""Shared helpers for the procedural texture generator (PIL + numpy only).

Everything is painted procedurally; nothing is downloaded. See generate.py.
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ORANGE = (255, 90, 13)          # spec.COLORS['orange'] #ff5a0d
STITCH = (255, 106, 26)         # spec.COLORS['stitch_orange']

FONT_DIRS = ['/usr/share/fonts/truetype', '/usr/share/fonts/opentype']


def font(name, size):
    """Find a system font by file name (e.g. 'DejaVuSans-Bold.ttf')."""
    for d in FONT_DIRS:
        for root, _, files in os.walk(d):
            if name in files:
                return ImageFont.truetype(os.path.join(root, name), size)
    print('WARNING: font not found', name)
    return ImageFont.truetype(os.path.join('/usr/share/fonts/truetype/dejavu', 'DejaVuSans-Bold.ttf'), size)


def save(img, name, **kw):
    p = os.path.join(HERE, name)
    if isinstance(img, np.ndarray):
        img = to_img(img)
    img.save(p, optimize=True, **kw)
    print('wrote', name, img.size, img.mode, os.path.getsize(p) // 1024, 'KB')
    return p


def to_img(a):
    a = np.asarray(a)
    if a.dtype != np.uint8:
        a = np.clip(a * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return Image.fromarray(a)


# ------------------------------------------------------------------ noise

def rng(seed):
    return np.random.default_rng(seed)


def value_noise(h, w, cells_y, cells_x, seed, tile=False, resample=Image.BICUBIC):
    """Smooth value noise in [0,1] of shape (h, w) with roughly cells_x x cells_y features."""
    r = rng(seed)
    cy, cx = max(1, int(cells_y)), max(1, int(cells_x))
    if tile:
        g = r.random((cy, cx)).astype(np.float32)
        big = np.tile(g, (3, 3))
        im = Image.fromarray(big, 'F').resize((w * 3, h * 3), resample)
        a = np.asarray(im)[h:2 * h, w:2 * w]
    else:
        g = r.random((cy + 3, cx + 3)).astype(np.float32)
        im = Image.fromarray(g, 'F')
        # crop away the border cells so bicubic edges do not show
        sx = w / cx; sy = h / cy
        im = im.resize((int(round((cx + 3) * sx)), int(round((cy + 3) * sy))), resample)
        a = np.asarray(im)[int(sy * 1.5):int(sy * 1.5) + h, int(sx * 1.5):int(sx * 1.5) + w]
        if a.shape != (h, w):
            a = np.asarray(Image.fromarray(np.ascontiguousarray(a), 'F').resize((w, h), Image.BILINEAR))
    return np.clip(a, 0, 1).astype(np.float32)


def fbm(h, w, cells, seed, octaves=4, tile=False, gain=0.5, aspect=1.0):
    """Fractal value noise in [0,1]. cells = feature count across the width at octave 0.
    aspect > 1 stretches features horizontally."""
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        cx = cells * (2 ** o)
        cy = max(1, cx * h / w * aspect)
        out += amp * (value_noise(h, w, cy, cx, seed + 101 * o, tile=tile) - 0.5)
        tot += amp
        amp *= gain
    return np.clip(0.5 + out / tot * 1.6, 0, 1)


def _box1d(a, r, axis):
    """Box filter of half-width r (edge-clamped) along axis via cumulative sums."""
    if r <= 0:
        return a
    n = a.shape[axis]
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    p = np.pad(a, pad, mode='edge')
    c = np.cumsum(p, axis=axis, dtype=np.float64)
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def blur(a, radius, axes=(0, 1)):
    """Approximate Gaussian blur (3 box passes) of a float array; radius ~ sigma in pixels.
    radius may be a (ry, rx) pair for anisotropic blur."""
    a = np.asarray(a, np.float32)
    if a.ndim == 3:
        return np.stack([blur(a[..., c], radius, axes) for c in range(a.shape[2])], -1)
    rr = radius if isinstance(radius, (tuple, list)) else (radius, radius)
    out = a
    for ax, s in zip((0, 1), rr):
        if s <= 0:
            continue
        # box half-width giving ~sigma after 3 passes: sigma^2 = 3 * ((2r+1)^2 - 1) / 12
        r = max(1, int(round((math.sqrt(4 * s * s + 1) - 1) / 2)))
        for _ in range(3):
            out = _box1d(out, r, ax)
    return out


def blur_wrap(a, radius):
    """Gaussian blur that wraps around the edges (seamless textures)."""
    h, w = a.shape[:2]
    p = int(radius * 3) + 2
    big = np.pad(a, ((p, p), (p, p)) + ((0, 0),) * (a.ndim - 2), mode='wrap')
    return blur(big, radius)[p:p + h, p:p + w]


def normal_from_height(hgt, strength=1.0, wrap=True):
    """Tangent-space normal map (OpenGL convention, +Y = up in the image) from a height field.
    hgt is in pixels-ish units scaled by strength. Returns uint8 RGB."""
    if wrap == 'x':
        dx = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) * 0.5
        dy = np.gradient(hgt, axis=0)
    elif wrap:
        dx = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) * 0.5
        dy = (np.roll(hgt, -1, 0) - np.roll(hgt, 1, 0)) * 0.5
    else:
        dx = np.gradient(hgt, axis=1)
        dy = np.gradient(hgt, axis=0)
    nx = -dx * strength
    ny = dy * strength          # image rows go down, +V goes up -> flip sign
    nz = np.ones_like(hgt)
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / l, ny / l, nz / l], -1)
    return np.clip((n * 0.5 + 0.5) * 255 + 0.5, 0, 255).astype(np.uint8)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def srgb_to_lin(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(np.asarray(c, np.float32), 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def col(rgb):
    """(r,g,b) 0..255 -> float array 0..1."""
    return np.array(rgb, np.float32) / 255.0


# ------------------------------------------------------------------ carbon weave

def twill(u, v, seed=7, tows=16, nfib=48):
    """Analytic 2x2 twill carbon weave.

    u, v: coordinates in tow widths (float arrays). Returns (lum, height, warp) where lum is an
    sRGB-ish brightness factor around 1.0, height in 0..1, warp = 1 where the vertical tow is on top.
    Periodic with `tows` tows (multiple of 4) so a tile of `tows` x `tows` is seamless.
    """
    r = rng(seed)
    i = np.floor(u).astype(np.int32)
    j = np.floor(v).astype(np.int32)
    fu = (u - i).astype(np.float32)
    fv = (v - j).astype(np.float32)
    k = (i + j) % 4
    warp = k < 2
    # across / along coordinates of the float on top
    a = np.where(warp, fu, fv)
    b = np.where(warp, k + fv, (k - 2) + fu)              # 0..2 along the float
    # tow cross-section (rounded) and float bulge
    across = np.sqrt(np.clip(np.sin(np.pi * a), 0, 1))
    bulge = 0.55 + 0.45 * np.sin(np.pi * b / 2.0)
    hgt = across * bulge
    # per-tow fibre streaks (constant along the tow); keep nfib <= ~px per tow / 2 to avoid aliasing
    fib_w = r.random((tows, nfib)).astype(np.float32)
    fib_f = r.random((tows, nfib)).astype(np.float32)
    # smooth the fibre tables a little
    for t in (fib_w, fib_f):
        t[:] = 0.75 * t + 0.125 * np.roll(t, 1, 1) + 0.125 * np.roll(t, -1, 1)
    ti = np.where(warp, i, j) % tows
    fi = np.clip((a * nfib).astype(np.int32), 0, nfib - 1)
    fib = np.where(warp, fib_w[ti, fi], fib_f[ti, fi])
    # per-float random brightness (some tows catch more light)
    tone_w = r.random((tows, tows)).astype(np.float32)
    tone = tone_w[i % tows, j % tows]
    lum = np.where(warp, 1.16, 0.80) * (0.86 + 0.20 * across) * (0.84 + 0.24 * fib) * (0.95 + 0.10 * tone)
    # dark gaps between tows and at float ends
    gap = np.minimum(smoothstep(0.0, 0.045, a), smoothstep(0.0, 0.045, 1 - a))
    endg = np.minimum(smoothstep(0.0, 0.035, b), smoothstep(0.0, 0.035, 2 - b))
    g = np.minimum(gap, 0.45 + 0.55 * endg)
    lum = lum * (0.62 + 0.38 * g)
    hgt = hgt * (0.6 + 0.4 * g) + 0.03 * (fib - 0.5)
    return lum.astype(np.float32), hgt.astype(np.float32), warp


# ------------------------------------------------------------------ geometry helpers

def poly_mask(shape, polys, ss=1):
    """Rasterise a list of polygons (lists of (x, y) pixel coords) into a float mask 0..1.
    ss>1 supersamples for anti-aliasing."""
    h, w = shape
    im = Image.new('L', (w * ss, h * ss), 0)
    d = ImageDraw.Draw(im)
    for p in polys:
        if len(p) >= 3:
            d.polygon([(x * ss, y * ss) for x, y in p], fill=255)
    if ss > 1:
        im = im.resize((w, h), Image.BOX)
    return np.asarray(im).astype(np.float32) / 255.0


def dilate(mask, px):
    """Grow a 0..1 mask by ~px pixels (MaxFilter)."""
    im = Image.fromarray((np.clip(mask, 0, 1) * 255).astype(np.uint8))
    k = int(px) * 2 + 1
    while k > 1:
        kk = min(k, 9) if min(k, 9) % 2 == 1 else min(k, 9) - 1
        im = im.filter(ImageFilter.MaxFilter(kk))
        k -= (kk - 1)
    return np.asarray(im).astype(np.float32) / 255.0


def erode(mask, px):
    return 1.0 - dilate(1.0 - mask, px)


def over(dst, color, alpha):
    """Composite a flat colour (or colour image) over dst with alpha (h, w)."""
    a = np.clip(alpha, 0, 1)[..., None]
    return dst * (1 - a) + np.asarray(color, np.float32) * a


# ------------------------------------------------------------------ GLX logo

def trx_letter_polys():
    """The blocky italic 'GLX' wordmark as polygons in a unit cap-height frame (y up, before
    the italic shear). Returns list of (outers, holes) per glyph and the total advance width."""
    G = [(0.18, 0.0), (1.30, 0.0), (1.46, 0.14), (1.46, 0.56), (0.80, 0.56), (0.80, 0.36), (1.13, 0.36),
         (1.13, 0.27), (0.33, 0.27), (0.33, 0.73), (1.46, 0.73), (1.46, 1.0), (0.18, 1.0), (0.0, 0.84), (0.0, 0.16)]
    L = [(0.0, 0.0), (1.20, 0.0), (1.20, 0.27), (0.33, 0.27), (0.33, 1.0), (0.0, 1.0)]
    X1 = [(0.0, 0.0), (0.40, 0.0), (0.80, 0.36), (1.20, 0.0), (1.62, 0.0), (1.02, 0.52), (1.52, 1.0),
          (1.12, 1.0), (0.82, 0.70), (0.50, 1.0), (0.09, 1.0), (0.60, 0.52)]
    glyphs = [([G], []), ([L], []), ([X1], [])]
    advances = [1.46, 1.20, 1.62]
    gap = 0.24
    out = []
    x = 0.0
    for (outers, holes), adv in zip(glyphs, advances):
        out.append(([[(px + x, py) for px, py in o] for o in outers], [[(px + x, py) for px, py in h] for h in holes]))
        x += adv + gap
    return out, x - gap


def trx_masks(shape, to_px, origin, height, slant=0.30, outline=0.13, ss=3):
    """Rasterise the GLX wordmark.

    to_px(x, y) maps logo-frame metres to pixel coords. origin = bottom-left (x, y) in metres,
    height = cap height in metres. Returns (fill_mask, outline_mask, width_m) where outline_mask is
    a band of `outline` * height around (outside) the glyph edges. Only the logo's bounding box is
    rasterised (supersampled ss times), so it is cheap on huge canvases.
    """
    glyphs, width = trx_letter_polys()

    def P(px, py):
        X = origin[0] + (px + slant * py) * height
        Y = origin[1] + py * height
        return to_px(X, Y)

    h, w = shape
    pts = [P(*q) for outers, holes in glyphs for o in outers for q in o]
    p0 = np.array(to_px(origin[0], origin[1])); p1 = np.array(to_px(origin[0], origin[1] + height))
    px_per_h = np.linalg.norm(p1 - p0)
    th = max(1, int(round(outline * px_per_h * ss)))
    m = int(outline * px_per_h) + 4
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    bx0 = max(0, int(min(xs)) - m); by0 = max(0, int(min(ys)) - m)
    bx1 = min(w, int(max(xs)) + m + 1); by1 = min(h, int(max(ys)) + m + 1)
    fullf = np.zeros(shape, np.float32); fullo = np.zeros(shape, np.float32)
    if bx1 <= bx0 or by1 <= by0:
        return fullf, fullo, width * height + slant * height
    BW, BH = (bx1 - bx0) * ss, (by1 - by0) * ss
    fill = Image.new('L', (BW, BH), 0)
    d = ImageDraw.Draw(fill)
    loc = lambda q: ((P(*q)[0] - bx0) * ss, (P(*q)[1] - by0) * ss)
    for outers, holes in glyphs:
        for o in outers:
            d.polygon([loc(q) for q in o], fill=255)
        for hh in holes:
            d.polygon([loc(q) for q in hh], fill=0)
    big = fill
    k = th * 2 + 1
    while k > 1:
        kk = min(k, 9) if min(k, 9) % 2 == 1 else min(k, 9) - 1
        big = big.filter(ImageFilter.MaxFilter(kk))
        k -= (kk - 1)
    f = np.asarray(fill.resize((bx1 - bx0, by1 - by0), Image.BOX)).astype(np.float32) / 255
    b = np.asarray(big.resize((bx1 - bx0, by1 - by0), Image.BOX)).astype(np.float32) / 255
    fullf[by0:by1, bx0:bx1] = f
    fullo[by0:by1, bx0:bx1] = np.clip(b - f, 0, 1)
    return fullf, fullo, width * height + slant * height
