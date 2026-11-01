"""Interior / trim / small-part textures (PIL + numpy only)."""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from texlib import *  # noqa


# --------------------------------------------------------------------------- hex mesh

def hex_field(H, W, nx, ny):
    """Pointy-top hex lattice that tiles exactly nx columns x ny row-pairs over (W, H).
    Returns (dist, cx, cy): hex distance from the nearest cell centre in units of the pitch,
    plus that centre in pixels. The lattice is very slightly stretched vertically to tile."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32) + 0.5
    s = W / nx                                   # horizontal pitch (px)
    sy = H / (ny * math.sqrt(3) * s)            # vertical stretch so ny row-pairs fit exactly
    x = xx / s
    y = yy / (s * sy)                            # unstretched units of pitch
    # candidate centres: rows every sqrt(3)/2, odd rows offset by 0.5
    rh = math.sqrt(3) / 2
    r0 = np.floor(y / rh)
    best = np.full(x.shape, 9.0, np.float32); bcx = np.zeros_like(x); bcy = np.zeros_like(x)
    for dr in (-1, 0, 1, 2):
        r = r0 + dr
        off = np.where(np.mod(r, 2) == 1, 0.5, 0.0)
        cxu = np.floor(x - off + 0.5) + off
        for dc in (-1, 0, 1):
            c = cxu + dc
            cyu = r * rh
            px = np.abs(x - c); py = np.abs(y - cyu)
            d = np.maximum(px, px * 0.5 + py * (math.sqrt(3) / 2))     # flat distance to a pointy-top hex edge
            m = d < best
            best = np.where(m, d, best); bcx = np.where(m, c, bcx); bcy = np.where(m, cyu, bcy)
    return best, bcx * s, bcy * s * sy


def make_hex_mesh(N=1024, nx=12):
    ny = max(1, int(round(N / (math.sqrt(3) * (N / nx)))))
    d, cx, cy = hex_field(N, N, nx, ny)
    hole_r = 0.34                                 # r4: hole apothem in pitch units (was .41: 67 % holes -> ~46 %; reads silver)
    px_per = N / nx
    aa = 0.9 / px_per
    hole = 1 - smoothstep(hole_r - aa, hole_r + aa, d)
    # metal shading: brushed horizontal grain + bevel light around the holes (light from top-left)
    grain = fbm(N, N, 3, 61, octaves=3, tile=True, aspect=0.08)
    base = 0.70 + 0.10 * (grain - 0.5)
    rim = smoothstep(hole_r + aa, hole_r + 0.06, d) * (1 - smoothstep(hole_r + 0.06, hole_r + 0.12, d))
    # direction of the rim normal relative to the cell centre
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32) + 0.5
    ang = np.arctan2(yy - cy, xx - cx)
    light = np.cos(ang - math.radians(225))          # +1 on the edge facing the light
    shade = base + rim * 0.18 * light - (1 - smoothstep(hole_r, hole_r + 0.05, d)) * 0.25
    rgb = np.clip(np.stack([shade * 0.95, shade * 0.97, shade * 1.0], -1), 0, 1)
    a = 1 - hole
    return np.concatenate([rgb, a[..., None]], -1)


# --------------------------------------------------------------------------- floor mat

def make_floor_mat(N=1024):
    """Black rubber floor mat: raised border, raised diamond grid, GLX plate (interior_dash.png).
    Layout for UV 0..1 over the whole mat, mat front (toward the pedals) at the top of the image."""
    ss = 2
    M = N * ss
    hgt = np.zeros((M, M), np.float32)
    yy, xx = np.mgrid[0:M, 0:M].astype(np.float32) / M
    # outer raised lip
    border = 0.035
    inner = (xx > border) & (xx < 1 - border) & (yy > border) & (yy < 1 - border)
    edge_d = np.minimum(np.minimum(xx, 1 - xx), np.minimum(yy, 1 - yy))
    lip = smoothstep(0.004, 0.010, edge_d) * (1 - smoothstep(border - 0.006, border, edge_d))
    hgt += lip * 1.0
    # diamond grid ridges (diamonds 1/5 of the width, slightly tall)
    a = (xx * 5.0 + yy * 4.0); b = (xx * 5.0 - yy * 4.0)
    da = np.abs(a - np.round(a)); db = np.abs(b - np.round(b))
    ridge_w = 0.035
    ridges = np.maximum(1 - smoothstep(ridge_w * 0.5, ridge_w, da), 1 - smoothstep(ridge_w * 0.5, ridge_w, db))
    # GLX plate: rounded rectangle in the lower middle
    px0, px1, py0, py1 = 0.16, 0.84, 0.66, 0.86
    in_plate = (xx > px0) & (xx < px1) & (yy > py0) & (yy < py1)
    pd = np.minimum(np.minimum(xx - px0, px1 - xx), np.minimum(yy - py0, py1 - yy))
    plate_rim = (pd > 0) & (pd < 0.012)
    ridges = np.where(in_plate, 0, ridges) * inner
    hgt += ridges * 0.55
    hgt += plate_rim * 0.8
    # GLX letters (outline, raised) centred in the plate
    hpx = (py1 - py0) * 0.55 * M
    def to_px(X, Yv):
        return (X * M, (1 - Yv) * M)
    hh = (py1 - py0) * 0.55
    _, adv = trx_letter_polys()
    wlogo = (adv + 0.30) * hh
    x0 = 0.5 - wlogo / 2
    fill, outl, _ = trx_masks((M, M), to_px, (x0, 1 - (py0 + (py1 - py0) * 0.78)), hh, slant=0.30, outline=0.11, ss=1)
    hgt += outl * 0.75 + fill * 0.15
    # rubber micro texture
    micro = fbm(M, M, 160, 71, octaves=2, tile=True)
    hgt_s = blur(hgt, 1.2 * ss)
    rgb_l = 0.075 + 0.025 * hgt_s + 0.012 * (micro - 0.5)
    # flat tops of ridges are a little lighter / worn
    rgb_l += 0.03 * smoothstep(0.4, 0.9, hgt_s)
    col_img = np.stack([rgb_l, rgb_l, rgb_l * 1.03], -1)
    col_img = Image.fromarray((np.clip(col_img, 0, 1) * 255).astype(np.uint8)).resize((N, N), Image.LANCZOS)
    nrm_h = hgt_s * 5.0 + (micro - 0.5) * 0.4
    nrm = normal_from_height(nrm_h, strength=1.0, wrap=False)
    nrm = Image.fromarray(nrm).resize((N, N), Image.LANCZOS)
    return col_img, nrm


# --------------------------------------------------------------------------- door quilt

def make_door_quilt(N=1024, nx=4, ny=3):
    """Tileable black leather diamond quilting with orange double stitching."""
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32) + 0.5
    u = xx / N * nx; v = yy / N * ny
    a = u + v; b = u - v                         # seam lines where a or b is an integer
    fa = a - np.floor(a); fb = b - np.floor(b)
    da = np.minimum(fa, 1 - fa); db = np.minimum(fb, 1 - fb)   # distance to seams (diagonal units)
    dseam = np.minimum(da, db)
    # cushion height: pillow inside each diamond
    pillow = np.sin(np.pi * np.clip(da * 2, 0, 1)) ** 0.6 * np.sin(np.pi * np.clip(db * 2, 0, 1)) ** 0.6
    # convert diagonal units to pixels for stitch placement (a diagonal unit spans ~ N/nx/2*sqrt2-ish)
    cell = N / nx
    scale = cell / math.sqrt(2) / 1.0           # approximate px per diagonal unit along the normal
    dpx = dseam * scale * 1.0
    # leather grain
    grain = fbm(N, N, 90, 81, octaves=3, tile=True)
    grain2 = fbm(N, N, 22, 82, octaves=2, tile=True)
    h = pillow * 10.0 - (1 - smoothstep(0, 6, dpx)) * 3.0 + (grain - 0.5) * 0.35
    base = 0.055 + 0.030 * pillow + 0.012 * (grain - 0.5) + 0.01 * (grain2 - 0.5)
    rgb = np.stack([base, base, base * 1.04], -1)
    # seam groove darker
    rgb *= (0.55 + 0.45 * smoothstep(0, 4, dpx))[..., None]
    # double orange stitching at +-9 px from each seam: dashes along the seam
    st = np.zeros((N, N), np.float32)
    for dist, along in ((da, b), (db, a)):
        dp = dist * scale
        alongp = along * scale
        dash = (np.mod(alongp, 9.0) < 5.5)
        for off in (7.5,):
            line = 1 - smoothstep(0.9, 1.9, np.abs(dp - off))
            st = np.maximum(st, line * dash)
    st = blur_wrap(st, 0.5)
    stc = np.array(STITCH, np.float32) / 255 * 0.92
    rgb = rgb * (1 - st[..., None]) + stc * st[..., None]
    h = h + st * 1.2
    nrm = normal_from_height(blur_wrap(h, 1.0), strength=1.0)
    return rgb, nrm


# --------------------------------------------------------------------------- suede / logos

def make_seat_suede(N=1024):
    n1 = fbm(N, N, 200, 91, octaves=3, tile=True)
    n2 = fbm(N, N, 14, 92, octaves=3, tile=True)
    nap = fbm(N, N, 400, 93, octaves=1, tile=True, aspect=0.5)
    l = 0.072 + 0.012 * (n1 - 0.5) + 0.010 * (n2 - 0.5) + 0.008 * (nap - 0.5)
    return np.stack([l, l, l * 1.02], -1)


def make_seat_logo(W=1024, H=512):
    """Orange embroidered 'GLX' outline on transparent (seat back, seat_closeup.png)."""
    ss = 2
    Wc, Hc = W * ss, H * ss
    hh = 0.31                                         # cap height as a fraction of image height
    _, adv = trx_letter_polys()
    wlogo = (adv + 0.30) * hh * Hc / Wc
    def to_px(X, Yv):
        return (X * Wc, (1 - Yv) * Hc)
    # logo frame in normalised image coords: X in [0,1] of width, Y in [0,1] of height
    def to_px_n(X, Yv):
        return (X * Hc, (1 - Yv) * Hc)               # use height units for both axes (no stretch)
    x0 = (Wc / Hc - (adv + 0.30) * hh) / 2
    y0 = (1 - hh) / 2
    fill, outl, _ = trx_masks((Hc, Wc), to_px_n, (x0, y0), hh, slant=0.30, outline=0.10, ss=2)
    # satin-stitch threads: fine diagonal lines across the outline
    yy, xx = np.mgrid[0:Hc, 0:Wc].astype(np.float32)
    thread = 0.80 + 0.20 * np.sin((xx * 0.8 + yy * 0.6) * 2.2)
    sheen = fbm(Hc, Wc, 30, 95, octaves=2)
    c = np.array(STITCH, np.float32) / 255
    rgb = c[None, None, :] * (thread * (0.85 + 0.3 * sheen))[..., None]
    rgba = np.concatenate([np.clip(rgb, 0, 1), outl[..., None]], -1)
    im = Image.fromarray((rgba * 255).astype(np.uint8), 'RGBA').resize((W, H), Image.LANCZOS)
    return im


def make_stitch_diamond(N=512, n=2):
    """Orange double-stitch diamond pattern on transparent (tileable, n x n diamonds)."""
    ss = 2
    M = N * ss
    yy, xx = np.mgrid[0:M, 0:M].astype(np.float32) + 0.5
    u = xx / M * n; v = yy / M * n
    a = u + v; b = u - v
    fa = a - np.floor(a); fb = b - np.floor(b)
    da = np.minimum(fa, 1 - fa); db = np.minimum(fb, 1 - fb)
    scale = (M / n) / math.sqrt(2)
    alpha = np.zeros((M, M), np.float32)
    for dist, along in ((da, b), (db, a)):
        dp = dist * scale; ap = along * scale
        dash = smoothstep(0.0, 1.0, np.mod(ap, 20.0)) * (1 - smoothstep(12.0, 13.5, np.mod(ap, 20.0)))
        # double row: dist is unsigned, so |dp - 7| covers both sides of the (invisible) seam
        line = 1 - smoothstep(2.0, 3.6, np.abs(dp - 7.0))
        alpha = np.maximum(alpha, line * dash)
    c = np.array(STITCH, np.float32) / 255
    shade = 0.85 + 0.15 * np.sin(xx * 0.9 + yy * 0.9)
    rgb = c[None, None, :] * shade[..., None]
    rgba = np.concatenate([np.clip(rgb, 0, 1), alpha[..., None]], -1)
    return Image.fromarray((rgba * 255).astype(np.uint8), 'RGBA').resize((N, N), Image.LANCZOS)


# --------------------------------------------------------------------------- firewall panel

def make_firewall_orange(W=1024, H=512):
    """Orange panel above the rear firewall mesh with black torn diagonal stripes (rear.png,
    seat_closeup.png). UV: u across the car (left->right), v up."""
    ss = 2
    Wc, Hc = W * ss, H * ss
    img = np.ones((Hc, Wc, 3), np.float32) * col(ORANGE)
    yy, xx = np.mgrid[0:Hc, 0:Wc].astype(np.float32)
    polys = []
    for c, w in ((0.08, 0.05), (0.30, 0.09), (0.52, 0.04), (0.70, 0.10), (0.93, 0.05)):
        polys.append([((c - 0.12) * Wc, Hc), ((c - 0.12 + w) * Wc, Hc), ((c + 0.12 + w) * Wc, 0), ((c + 0.12) * Wc, 0)])
    m = poly_mask((Hc, Wc), polys)
    n = value_noise(Hc, Wc, 40, 70, 501) * 0.7 + value_noise(Hc, Wc, 130, 220, 502) * 0.3
    grow = dilate(m, 14)
    torn = np.clip(m + (grow - m) * (n > 0.56), 0, 1)
    img = over(img, col((10, 10, 11)), torn * 0.96)
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
