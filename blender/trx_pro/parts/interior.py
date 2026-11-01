"""Part 'interior': the cockpit the player sits in (ref/interior_dash.png, ref/seat_closeup.png).

  * gloss carbon DASH across the cockpit: a thin high visor over the digital dash that falls gradually toward the
    centre, a lower passenger-side lip over the DuneNav (the hood shows beyond it), driver knee bolster down to
    z ~0.66 (footwell closed off from the eye), passenger side open below z ~0.78; satin carbon on the top behind
    the lip; bold hard-edged orange blades with black underlines baked with the carbon weave into
    textures/interior_dash_decal.png (+ normal map); two dark hex-mesh knee grilles;
  * left digital race dash (0.25 x 0.13 glass, black bezel, tilted up), right DuneNav Pro 9 7 with its side keys
    (night chart), centre stack with race radio, backlit switch panel, two red push buttons, DCX intercom plate,
    marine stereo pod. Screens are dimly lit (emission 0.6); TRX_SCREENS_OFF=1 builds them switched off;
  * narrow carbon centre stack column + console tunnel (orange bands, lightning wedge on the passenger side), tall
    sequential shifter, two cutting-brake levers leaning forward from a low pivot box, aluminium perforated pedals
    (~1.1 m ahead of the H-point) + footrests, charcoal diamond floor mats, polished floor rivets, passenger grab
    handle;
  * steering wheel (group 'SteeringWheel', built round spec.STEERING_WHEEL_CENTRE about
    spec.STEERING_COLUMN_DIR): 350 mm suede rim with orange 12 o'clock stripe and orange stitching,
    3 flat black anodized spokes with polished chamfers, satin hub + flat horn button with the DRV logo.
    Quick-release hub, column and its support are static;
  * two GLX race seats: suede centre (GLX embroidery + orange diamond stitching on the back), black leather
    shoulder wings, black suede outer rolls, grey suede inserts on the lower bolsters, orange double stitching,
    dashed orange seam stitch, gloss-black harness-slot rings; 5-point harnesses with shoulder pads + labels,
    cam-lock buckle;
  * quilted door cards (grained leather upper band, orange seam stitch) with polished aluminium handles,
    carbon rear-quarter panels, footwell side panels, rear firewall (carbon, hex-mesh grille windows, orange striped
    band, orange top strip).

Coordinates: +X right, +Y forward, +Z up (metres). Driver on the LEFT (x < 0).
Textures painted here (PIL) are written to textures/interior_*.png when missing or out of date.
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector, Matrix

from common import (M, mat, tube, box, cylinder, lathe, sphere, mirror_x, join, apply_transform,
                    obj_from_bmesh, uv_project, top_uv, TEX, aligned_matrix, world_matrix)
import spec

V = Vector
SX = spec.SEAT_X
FZ = spec.FLOOR_Z
DZF = FZ - 0.45              # r4: the floor rose 0.45 -> 0.475; pedals / footrests (absolute heights) follow it
EYE = V(spec.DRIVER_EYE)

# =====================================================================================================
#  TEXTURES
# =====================================================================================================
TEXV = 'interior-v20'

# dash decal atlas (must match the UV functions below)
DEC_W, DEC_H = 4096, 2048
# r3 atlas: region A = dash / stack rear faces, (x, z) projection, x -0.72..0.72, z 1.10..0.45 (rows 0..1430);
DA_X0, DA_Z1, DA_PPM = -0.72, 1.10, 2800.0     # r6: 2200 -> 2800 px/m (region A now uses the whole atlas)
SB_W, SB_Z0 = 0.40, 0.50                              # seat back texture: 0.40 m wide, z 0.50..1.30
SB_ZSPAN = 0.80
LEATHER_U = 0.050            # r6: the suede centre panel's half width between the shoulder straps (leather outboard)


def seat_leather_zh(u):
    """r6: top of the charcoal leather wing on the seat back's centre panel at |u| (the headrest suede with the GLX
    embroidery above it dips to ~1.152 between the pass-throughs and rises toward the outer top corners)."""
    return 1.152 + 0.55 * np.maximum(0.0, u - LEATHER_U)
CS = 2.2                     # r6 (arbiter): x2.2 finer weave (photo twill ~4-5 mm; 1.6 mm tows). r5: 1.0 -
                             # carbon UV units per metre in the cockpit. r5: was 1.8 (1.9 mm tows with the r4 48-tow
                             # carbon_base.png, finer than the body and shimmering in the game); now 3.5 mm like the body


def _tp(name):
    return os.path.join(TEX, name)


def _font(size, weight='Bold', italic=False):
    from PIL import ImageFont
    nm = 'Inter-%s%s.otf' % (weight, 'Italic' if italic else '')
    for p in ('/usr/share/fonts/opentype/inter/' + nm, '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _save(img, name):
    from PIL import PngImagePlugin
    info = PngImagePlugin.PngInfo()
    info.add_text('interior', TEXV)
    img.save(_tp(name), pnginfo=info, optimize=True)


def _tiled(h, w, px, name):
    from PIL import Image
    t = np.asarray(Image.open(_tp(name)).convert('RGB').resize((px, px), Image.LANCZOS)).astype(np.float32)
    return np.tile(t, (h // px + 2, w // px + 2, 1))[:h, :w]


def _poly_alpha(h, w, polys, ss=2):
    from PIL import Image, ImageDraw
    im = Image.new('L', (w * ss, h * ss), 0)
    dr = ImageDraw.Draw(im)
    for p in polys:
        dr.polygon([(x * ss, y * ss) for (x, y) in p], fill=255)
    im = im.resize((w, h), Image.LANCZOS)
    return np.asarray(im).astype(np.float32) / 255.0


def _blade(top0, top1, h0, h1, lead_cut=0.060, tear=0.05, rng=None, teeth=7):
    """Hard-edged vinyl blade (metres, (x, z) or (y, z)): straight top/bottom edges from the leading end top0 -> the
    trailing end top1 (top-edge points), heights h0 / h1, a slanted sharp cut at the lead and a torn trailing end.
    Returns (polygon, flecks)."""
    rng = rng or np.random.default_rng(1)
    (xa, za), (xb, zb) = top0, top1
    sgn = 1.0 if xb > xa else -1.0
    L = abs(xb - xa)
    zt = lambda x: za + (zb - za) * (x - xa) / (xb - xa)
    hh = lambda x: h0 + (h1 - h0) * (x - xa) / (xb - xa)
    top = [(xa + sgn * lead_cut, zt(xa + sgn * lead_cut))]
    bot = [(xa, zt(xa) - hh(xa))]
    xe_t = xb
    xe_b = xb - sgn * tear * 0.6
    top.append((xe_t, zt(xe_t)))
    bot.append((xe_b, zt(xe_b) - hh(xe_b)))
    # torn trailing edge: zig-zag from the top end back to the bottom end, teeth reaching up to `tear` inward
    tornpts = []
    for k in range(1, teeth):
        f = k / teeth
        z = zt(xe_t) - hh(xe_t) * f
        x = xe_t - sgn * (tear * (0.15 + 0.85 * rng.uniform(0, 1)) * (0.5 if k % 2 else 1.0) + tear * 0.6 * f)
        tornpts.append((x, z))
    poly = top + tornpts + bot[::-1]
    flecks = []
    for k in range(rng.integers(2, 5)):
        fx = xe_t + sgn * rng.uniform(0.004, tear * 0.8)
        fz = zt(xe_t) - hh(xe_t) * rng.uniform(0.1, 0.9)
        w, h = rng.uniform(0.004, 0.012), rng.uniform(0.002, 0.006)
        flecks.append([(fx, fz), (fx + sgn * w, fz + h * 0.3), (fx + sgn * w * 0.8, fz - h), (fx - sgn * w * 0.2, fz - h * 0.7)])
    return poly, flecks


def _underline(top0, top1, h0, h1, gap=0.003, t=0.004, start=0.03, stop=0.06):
    """Thin black line parallel to a blade's bottom edge."""
    (xa, za), (xb, zb) = top0, top1
    sgn = 1.0 if xb > xa else -1.0
    zt = lambda x: za + (zb - za) * (x - xa) / (xb - xa)
    hh = lambda x: h0 + (h1 - h0) * (x - xa) / (xb - xa)
    x0, x1 = xa + sgn * start, xb - sgn * stop
    b0, b1 = zt(x0) - hh(x0) - gap, zt(x1) - hh(x1) - gap
    return [(x0 + sgn * 0.012, b0), (x1, b1), (x1 - sgn * 0.010, b1 - t), (x0, b0 - t)]


def _jag(n, amp, rng, smooth=3, notch_p=0.06, notch=2.5):
    """Smooth random edge offsets (metres) with occasional sharp notches (torn vinyl edge)."""
    w = rng.normal(0, 1, n + 2 * smooth)
    k = np.ones(2 * smooth + 1) / (2 * smooth + 1)
    w = np.convolve(w, k, 'same')[smooth:smooth + n]
    w = w / (w.std() + 1e-9) * amp
    for i in range(n):
        if rng.uniform() < notch_p:
            w[i] -= amp * notch * rng.uniform(0.6, 1.0)
    return w


def _stroke(x0, x1, zt0, zt1, h0, h1, rng, lead=0.03, lead_mode='point', tongues=4, tear=0.06, jag=0.0012,
            tip=False):
    """r4 torn brush stroke in (x, z) metres: leading end at x0 (sharp point or diagonal cut), trailing end at x1
    torn into tongues (or tapering to a point if tip). Top edge from zt0 to zt1, height h0 -> h1. Returns polygon."""
    sgn = 1.0 if x1 > x0 else -1.0
    L = abs(x1 - x0)
    n = max(8, int(L / 0.004))
    xb = np.linspace(x0, x1 - sgn * (0.0 if tip else tear), n)
    t = (xb - x0) / (x1 - x0)
    zt = zt0 + (zt1 - zt0) * t + _jag(n, jag, rng)
    hh = h0 + (h1 - h0) * t
    zb = zt - hh + _jag(n, jag, rng, notch_p=0.08)
    # leading end
    ld = np.clip((xb - x0) * sgn / max(lead, 1e-4), 0, 1)
    if lead_mode == 'point':
        mid = (zt + zb) / 2
        zt = mid + (zt - mid) * (ld ** 0.8)
        zb = mid + (zb - mid) * (ld ** 0.8)
    else:                                                    # diagonal cut: the top edge starts later
        zt = np.where(ld < 1, zb + (zt - zb) * ld, zt)
    if tip:
        zt = zt - (zt - zb) * np.clip((t - 0.6) / 0.4, 0, 1) ** 1.3 * 0.5
        zb = zb + (zt - zb) * np.clip((t - 0.6) / 0.4, 0, 1) ** 1.3 * 0.9
    top = list(zip(xb, zt))
    bot = list(zip(xb, zb))
    end = []
    if not tip:
        # torn trailing end: tongues of different length reaching to x1
        xe = xb[-1]
        zt_e, zb_e = zt[-1], zb[-1]
        for k in range(tongues):
            f0, f1 = k / tongues, (k + 1) / tongues
            za = zt_e + (zb_e - zt_e) * f0
            zc = zt_e + (zb_e - zt_e) * (f0 + f1) / 2
            zb2 = zt_e + (zb_e - zt_e) * f1
            reach = tear * rng.uniform(0.35, 1.0)
            end += [(xe + sgn * reach * 0.55, za + (zc - za) * 0.2), (xe + sgn * reach, zc),
                    (xe + sgn * reach * 0.3, zb2 + (zc - zb2) * 0.3)]
    return top + end + bot[::-1]


def _shards(x0, x1, zt0, zt1, h, rng, n=3, size=(0.006, 0.02)):
    """Black shard cut-outs (sharp triangles / quads) along a stroke, some biting its edges."""
    out = []
    for k in range(n):
        f = rng.uniform(0.25, 0.95)
        x = x0 + (x1 - x0) * f
        zt = zt0 + (zt1 - zt0) * f
        z = zt - h * rng.choice([rng.uniform(-0.1, 0.25), rng.uniform(0.75, 1.1), rng.uniform(0.3, 0.7)])
        L = rng.uniform(*size)
        hgt = L * rng.uniform(0.18, 0.4)
        ang = math.radians(rng.uniform(-8, 14))
        ca, sa = math.cos(ang), math.sin(ang)
        pts = [(-L / 2, 0), (L / 2 * rng.uniform(0.6, 1), hgt * rng.uniform(-0.2, 0.4)), (L * rng.uniform(0.1, 0.3), -hgt),
               (-L * rng.uniform(0.1, 0.3), -hgt * rng.uniform(0.3, 0.8))]
        out.append([(x + a * ca - b * sa, z + a * sa + b * ca) for (a, b) in pts])
    return out


def _pinstripe(x0, x1, z0, z1, w=0.0007):
    return [(x0, z0), (x1, z1), (x1, z1 - w), (x0, z0 - w)]


def paint_dash_decal():
    """Dash / stack rear faces (x, z projection, DA_* window): deep black carbon weave with the photo's torn orange brush
    strokes (interior_dash.png 600-1440 px / 270-390 px, back-projected onto the dash face), black shard cut-outs and grey
    pinstripes. r6: one region at 2800 px/m (r3-r5 had a second console-side region B; those graphics are geometry now)."""
    from PIL import Image
    H, W = DEC_H, DEC_W
    col = np.zeros((H, W, 3), np.float32)
    nrm = np.zeros((H, W, 3), np.float32)
    # r6: one region (A) over the whole atlas at 2800 px/m, 2.2x finer weave (4.4 px per 1.6 mm tow), deep black gloss
    # carbon: tows ~18 / 30 sRGB (r5: 37 mean, 1.5x contrast - read light grey with a printed-looking weave). The console
    # and stack sides are plain interior carbon now; their orange flash / swoosh are geometry inlays (build_inlays).
    pa = int(round(DA_PPM / (6.0 * CS)))                        # 212 px per carbon tile (48 tows)
    col = _tiled(H, W, pa, 'carbon_base.png')
    nrm = _tiled(H, W, pa, 'carbon_normal.png')
    lum = col.mean(-1, keepdims=True)
    col = 24.0 + (lum - lum.mean()) * (6.0 / 9.0)              # carbon_base tows 21 / 39 -> 18 / 30
    col = np.repeat(col, 3, -1) * np.array([1.0, 1.0, 1.04], np.float32)

    def A(p):
        return [((x - DA_X0) * DA_PPM, (DA_Z1 - z) * DA_PPM) for (x, z) in p]

    rng = np.random.default_rng(23)
    orange, dark, grey, under = [], [], [], []

    def layered(x0, x1, zt0, zt1, h0, h1, drop=0.006, grow=0.004, ext=0.03, **kw):
        """Orange stroke on a slightly larger black vinyl stroke offset downward (the livery's layered look)."""
        st = dict(kw)
        under.append(A(_stroke(x0 - 0.01 * (1 if x1 > x0 else -1), x1 + ext * (1 if x1 > x0 else -1), zt0 - drop + grow,
                               zt1 - drop + grow, h0 + 2 * grow, h1 + 2 * grow, rng, **st)))
        orange.append(A(_stroke(x0, x1, zt0, zt1, h0, h1, rng, **st)))

    J = dict(jag=0.0005)
    # ---- region A strokes
    # A: short blade under the radio, over the switch panel, tapering to a point
    layered(-0.198, 0.112, 0.913, 0.921, 0.019, 0.010, drop=0.005, ext=0.04, lead=0.012, lead_mode='cut', tip=True, **J)
    dark += [A(p) for p in _shards(-0.17, 0.08, 0.913, 0.919, 0.016, rng, n=3, size=(0.010, 0.026))]
    grey.append(A(_pinstripe(-0.150, 0.06, 0.8925, 0.8975)))
    # B: main band from the pointed lead under the digital dash, rising to the right, behind the switch panel
    layered(-0.445, -0.06, 0.869, 0.888, 0.024, 0.030, drop=0.008, grow=0.005, lead=0.05, tongues=4, tear=0.04, **J)
    dark += [A(p) for p in _shards(-0.40, -0.10, 0.871, 0.886, 0.028, rng, n=3)]
    grey.append(A(_pinstripe(-0.36, -0.12, 0.8385, 0.8440)))
    # C: lower streaks under B (photo slivers), rising
    orange.append(A(_stroke(-0.425, -0.075, 0.829, 0.838, 0.006, 0.009, rng, lead=0.04, tongues=3, tear=0.05, **J)))
    orange.append(A(_stroke(-0.300, -0.090, 0.8215, 0.8265, 0.004, 0.005, rng, lead=0.03, tongues=2, tear=0.03, **J)))
    # broad torn patch between the switch panel and the DuneNav: two bands on black (B / C continue behind both)
    under.append(A(_stroke(-0.03, 0.235, 0.909, 0.913, 0.066, 0.070, rng, lead=0.02, lead_mode='cut', tongues=3,
                           tear=0.04, jag=0.0008)))
    orange.append(A(_stroke(-0.02, 0.215, 0.902, 0.907, 0.020, 0.022, rng, lead=0.02, lead_mode='cut', tongues=3,
                            tear=0.03, jag=0.0008)))
    orange.append(A(_stroke(-0.02, 0.205, 0.873, 0.877, 0.024, 0.026, rng, lead=0.02, lead_mode='cut', tongues=4,
                            tear=0.035, jag=0.0008)))
    dark += [A(p) for p in _shards(0.07, 0.19, 0.902, 0.906, 0.018, rng, n=3, size=(0.008, 0.024))]
    dark += [A(p) for p in _shards(0.07, 0.19, 0.873, 0.876, 0.022, rng, n=2, size=(0.008, 0.02))]
    grey.append(A(_pinstripe(0.03, 0.21, 0.9155, 0.9195)))
    # streaks past the DuneNav's right edge (photo: torn orange slivers under a gloss-black band with a grey line)
    under.append(A(_stroke(0.36, 0.56, 0.915, 0.925, 0.030, 0.022, rng, lead=0.02, lead_mode='cut', tongues=3,
                           tear=0.05, jag=0.0005)))
    grey.append(A(_pinstripe(0.36, 0.50, 0.9105, 0.9145)))
    orange.append(A(_stroke(0.36, 0.495, 0.896, 0.900, 0.009, 0.005, rng, lead=0.01, lead_mode='cut', tongues=3,
                            tear=0.04, **J)))
    orange.append(A(_stroke(0.40, 0.47, 0.8885, 0.891, 0.004, 0.003, rng, lead=0.01, lead_mode='cut', tongues=2,
                            tear=0.02, **J)))
    for (bx, bz, bw) in ((0.505, 0.897, 0.012), (0.528, 0.8955, 0.006), (0.548, 0.894, 0.010)):
        orange.append(A([(bx, bz), (bx + bw, bz + 0.0006), (bx + bw * 0.8, bz - 0.0035), (bx + 0.001, bz - 0.003)]))
    # driver's far left, above the door-side knee grille: one short sliver
    layered(-0.660, -0.50, 0.905, 0.916, 0.010, 0.012, lead=0.03, tongues=3, tear=0.03, **J)
    au = _poly_alpha(H, W, under)
    col = col * (1 - au[..., None]) + np.array([9, 9, 10], np.float32) * au[..., None]
    ao = _poly_alpha(H, W, orange)
    ad = _poly_alpha(H, W, dark)
    ag = _poly_alpha(H, W, grey, ss=4)
    rn = np.random.default_rng(3).normal(0, 1, (H // 8, W // 8)).astype(np.float32)
    rn = np.asarray(Image.fromarray(((rn * 20) + 128).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC),
                    np.float32) / 255.0 - 0.5
    oc = np.array([255, 90, 13], np.float32)[None, None, :] * (1.0 + 0.04 * rn[..., None])
    col = col * (1 - ao[..., None]) + oc * ao[..., None]
    col = col * (1 - ad[..., None]) + np.array([8, 8, 9], np.float32) * ad[..., None]
    col = col * (1 - ag[..., None]) + np.array([118, 120, 126], np.float32) * ag[..., None]
    flat = np.array([128, 128, 255], np.float32)
    k = np.clip(au + ao + ad + ag, 0, 1)[..., None]
    nrm = nrm * (1 - k) + flat * k
    _save(Image.fromarray(col.clip(0, 255).astype(np.uint8)), 'interior_dash_decal.png')
    nim = Image.fromarray(nrm.clip(0, 255).astype(np.uint8)).resize((W // 2, H // 2), Image.LANCZOS)
    _save(nim, 'interior_dash_decal_normal.png')


def paint_switch_grid():
    """Re-lay the shared 2 x 6 switch panel keys as the car's 4 x 3 panel."""
    from PIL import Image
    src = Image.open(_tp('switch_panel.png')).convert('RGB')
    keys = []
    for j in range(2):
        for i in range(6):
            x0 = int(42 + 160.6 * i)
            y0 = int(42 + 226 * j)
            keys.append(src.crop((x0, y0, x0 + 138, y0 + 203)))
    out = Image.new('RGB', (1024, 1024), (8, 8, 9))
    kw, kh = 222, 300
    gx, gy = (1024 - 4 * kw) // 5, (1024 - 3 * kh) // 4
    order = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    for n, k in enumerate(order):
        r, c = divmod(n, 4)
        out.paste(keys[k].resize((kw, kh), Image.LANCZOS), (gx + c * (kw + gx), gy + r * (kh + gy)))
    _save(out, 'interior_switch_grid.png')


def paint_lowrance_bezel():
    from PIL import Image, ImageDraw
    W = 1024
    ppm = W / LOW_W
    H = int(round(LOW_H * ppm))
    yy = np.linspace(0, 1, H)[:, None]
    base = (14 + 6 * (1 - yy)) * np.ones((H, W))
    img = Image.fromarray(np.dstack([base, base, base * 1.04]).clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)

    def px(a, b):
        return ((a + LOW_W / 2) * ppm, (LOW_H / 2 - b) * ppm)

    ga0, ga1 = LG_A0 - LG_W / 2, LG_A0 + LG_W / 2
    x0, y0 = px(ga0 - 0.002, LG_H / 2 + 0.002)
    x1, y1 = px(ga1 + 0.002, -LG_H / 2 - 0.002)
    d.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=(24, 24, 26))
    x0, y0 = px(ga0, LG_H / 2)
    x1, y1 = px(ga1, -LG_H / 2)
    d.rectangle([x0, y0, x1, y1], fill=(3, 3, 4))
    # vertical DUNENAV on the left strip, reading bottom -> top
    f = _font(70, 'Black')
    tw = int(d.textlength('DUNENAV', font=f)) + 20
    t = Image.new('L', (tw, 90), 0)
    ImageDraw.Draw(t).text((10, 4), 'DUNENAV', font=f, fill=255)
    t = t.rotate(90, expand=True)
    sc = (0.098 * ppm) / t.height
    t = t.resize((max(1, int(t.width * sc)), int(t.height * sc)), Image.LANCZOS)
    cx, cy = px((ga0 - LOW_W / 2) / 2, -0.004)
    img.paste((235, 235, 238), (int(cx - t.width / 2), int(cy - t.height / 2)), t)
    # PRO 9 badge bottom right of the glass
    f2 = _font(30, 'Bold')
    bx, by = px(ga1 - 0.036, -LG_H / 2 - 0.0025)
    d.text((bx, by), 'PRO', font=f2, fill=(225, 225, 228))
    d.text((bx + d.textlength('PRO ', font=f2), by), '9', font=_font(30, 'Black'), fill=(225, 225, 228))
    # printed button wells on the right strip
    for k in range(LBTN_N):
        cx, cy = px(LBTN_A, LBTN_B0 - k * LBTN_DB)
        r = 0.0060 * ppm
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(30, 30, 33), outline=(70, 70, 74), width=3)
    _save(img, 'interior_lowrance_bezel.png')


def paint_race_radio():
    from PIL import Image, ImageDraw
    W, H = 512, 160
    img = Image.new('RGB', (W, H), (26, 27, 29))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=(52, 53, 56), width=4)
    d.rounded_rectangle([24, 26, 236, 104], radius=6, fill=(12, 12, 12))
    # r5: LCD switched off (interior_dash.png): unlit grey-green glass, segments only faintly visible
    d.rectangle([32, 34, 228, 96], fill=(58, 64, 56))
    d.text((40, 38), '146.520', font=_font(40, 'Bold'), fill=(50, 56, 48))
    d.text((40, 80), 'CH 07  TX', font=_font(13, 'Bold'), fill=(50, 56, 48))
    d.text((24, 116), 'RACE RADIO', font=_font(18, 'Bold'), fill=(200, 200, 205))
    for r in range(2):
        for c in range(4):
            x, y = 262 + c * 60, 28 + r * 60
            d.rounded_rectangle([x, y, x + 48, y + 44], radius=8, fill=(44, 45, 49), outline=(70, 71, 75), width=2)
            d.text((x + 17, y + 12), '123456*#'[r * 4 + c], font=_font(18, 'Bold'), fill=(210, 210, 215))
    _save(img, 'interior_race_radio.png')


def paint_stereo_face():
    from PIL import Image, ImageDraw
    W, H = 512, 384
    ppm = W / 0.108
    img = Image.new('RGB', (W, H), (16, 16, 17))
    d = ImageDraw.Draw(img)

    def px(a, b):
        return ((a + 0.054) * ppm, (0.0405 - b) * ppm)

    x0, y0 = px(-0.038, 0.037)
    x1, y1 = px(0.038, 0.001)
    d.rounded_rectangle([x0, y0, x1, y1], radius=8, fill=(4, 4, 5), outline=(60, 60, 64), width=2)
    cx, cy = px(0.0, -0.020)
    for r, c in ((0.0150, (90, 92, 96)), (0.0132, (30, 30, 32))):
        rr = r * ppm
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=c)
    for sx in (-1, 1):
        for k in range(2):
            bx, by = px(sx * (0.026 + k * 0.013), -0.020)
            d.rounded_rectangle([bx - 22, by - 16, bx + 22, by + 16], radius=6, fill=(46, 46, 50))
    d.text(px(-0.050, 0.0395), 'MARINE AUDIO', font=_font(18, 'Bold'), fill=(170, 170, 175))
    _save(img, 'interior_stereo_face.png')


def paint_seat_back():
    """Suede seat-back centre panel: GLX embroidery up top, orange diamond stitching lower down."""
    from PIL import Image
    W, H = 1024, 2048
    ppm = W / SB_W
    base = _tiled(H, W, int(0.20 * ppm), 'seat_suede.png')
    base = base * (11.5 / max(1.0, float(base.mean())))         # r5: ~12 sRGB (#0c0c0e; r3-r4 15 rendered 2x light)
    img = Image.fromarray(base.clip(0, 255).astype(np.uint8)).convert('RGBA')

    def row(z):
        return int((SB_Z0 + SB_ZSPAN - z) * ppm)

    # r6: charcoal leather wings round the harness pass-throughs on the centre panel (seat_closeup.png): leather where
    # z >= SEAT_GREY_Z and |u| >= LEATHER_U up to the headrest suede (seat_leather_zh); colour + roughness map
    from PIL import ImageDraw, ImageFilter
    px_u = np.abs(0.5 - (np.arange(W) + 0.5) / W)[None, :] * SB_W          # |u| (m) per column
    px_z = (SB_Z0 + SB_ZSPAN - (np.arange(H) + 0.5) / ppm)[:, None]        # z (m) per row
    zh = seat_leather_zh(px_u)
    lm = ((px_z >= SEAT_GREY_Z) & (px_u >= LEATHER_U) & (px_z <= zh)).astype(np.float32)
    lm = np.asarray(Image.fromarray((lm * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255
    # diamond stitching (0.08 x 0.12 m diamonds) between the straps (not on the leather)
    st = Image.open(_tp('stitch_diamond.png')).convert('RGBA').resize((int(0.16 * ppm), int(0.24 * ppm)), Image.LANCZOS)
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    r0, r1 = row(1.035), row(0.60)
    x0 = W // 2 - st.width // 2
    for yy in range(r0 - st.height // 4, r1, st.height):
        for xx in range(x0 - 2 * st.width, W, st.width):
            layer.alpha_composite(st, (xx, yy))
    mask = Image.new('L', (W, H), 0)
    hw = int(0.100 * ppm)
    ImageDraw.Draw(mask).rectangle([W // 2 - hw, r0, W // 2 + hw, r1], fill=255)
    la = np.asarray(layer).copy()
    la[..., 3] = (la[..., 3].astype(np.float32) * np.asarray(mask, np.float32) / 255 * (1 - lm)).astype(np.uint8)
    img.alpha_composite(Image.fromarray(la))
    a = np.asarray(img).astype(np.float32)
    grain = _band_noise_hw(H, W, 120, 220, 41) * 0.035 + _band_noise_hw(H, W, 12, 24, 42) * 0.03
    leather = np.array([58.0, 61.0, 66.0], np.float32)[None, None, :] * (1.0 + grain[..., None])
    a[..., :3] = a[..., :3] * (1 - lm[..., None]) + leather * lm[..., None]
    # seam: a dark 2.5 mm groove just inside the leather edge, soft shadow on the suede side
    edge = np.asarray(Image.fromarray((lm * 255).astype(np.uint8)).filter(ImageFilter.FIND_EDGES), np.float32) / 255
    edge = np.asarray(Image.fromarray((np.clip(edge * 3, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.0)),
                      np.float32) / 255
    a[..., :3] *= (1.0 - 0.55 * np.clip(edge * 2.5, 0, 1))[..., None]
    img = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    # GLX embroidery
    # r3: lettering 0.77x and 0.035 m higher; satin-stitch outline thinned ~40 % (eroded from both sides)
    logo = Image.open(_tp('seat_logo.png')).convert('RGBA')
    r_, g_, b_, a_ = logo.split()
    a_ = a_.filter(ImageFilter.MinFilter(9))
    logo = Image.merge('RGBA', (r_, g_, b_, a_))
    lw = int(0.215 * 0.77 * ppm)
    logo = logo.resize((lw, int(lw * logo.height / logo.width)), Image.LANCZOS)
    img.alpha_composite(logo, (W // 2 - logo.width // 2, row(1.215) - logo.height // 2))
    _save(img.convert('RGB'), 'interior_seat_back.png')
    rough = 0.93 + (0.60 - 0.93) * lm                           # suede .93 / leather .60 (glTF roughness texture)
    rim = Image.fromarray((rough * 255).clip(0, 255).astype(np.uint8)).resize((W // 4, H // 4), Image.LANCZOS)
    _save(rim, 'interior_seat_back_rough.png')


def paint_harness_label():
    """r5: 55 x 65 mm shoulder-pad label (seat_closeup.png): white field, black crow silhouette in the upper 60 %, black
    'GEAR' along the lower edge."""
    from PIL import Image, ImageDraw
    W, H = 440, 520
    img = Image.new('RGB', (W, H), (24, 24, 25))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([10, 10, W - 10, H - 10], radius=18, fill=(238, 238, 234))
    # perched crow facing left (body, raised wing, head with beak, fanned tail, legs), upper 60 %
    crow = [(70, 150), (112, 118), (150, 104), (176, 92), (204, 84), (236, 90), (262, 112), (300, 98), (352, 62),
            (392, 50), (370, 92), (340, 130), (372, 140), (404, 174), (360, 172), (330, 186), (300, 222), (262, 246),
            (226, 256), (192, 252), (168, 236), (150, 206), (132, 176), (104, 166)]
    d.polygon(crow, fill=(16, 16, 16))
    d.polygon([(70, 150), (34, 160), (66, 168), (104, 166)], fill=(16, 16, 16))      # beak
    d.ellipse([118, 128, 132, 142], fill=(238, 238, 234))                          # eye
    for x0 in (212, 238):                                                           # legs + feet
        d.line([(x0, 252), (x0 - 6, 296)], fill=(16, 16, 16), width=8)
        d.line([(x0 - 6, 296), (x0 - 26, 304)], fill=(16, 16, 16), width=6)
        d.line([(x0 - 6, 296), (x0 + 12, 306)], fill=(16, 16, 16), width=6)
    d.line([(150, 306), (330, 306)], fill=(16, 16, 16), width=8)                   # perch
    d.text((W // 2, 420), 'GEAR', font=_font(118, 'Black'), fill=(16, 16, 16), anchor='mm')
    _save(img, 'interior_harness_label.png')


def paint_perf_alu():
    from PIL import Image, ImageDraw
    W = 512
    rng = np.random.default_rng(5)
    br = rng.normal(0, 1, (W, 1)).astype(np.float32) * 6 + rng.normal(0, 1, (W, W)).astype(np.float32) * 2
    base = 168 + br                 # r3: satin aluminium (was 196), less glare through the wheel
    img = Image.fromarray(np.dstack([base, base + 2, base + 6]).clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    n = 8
    p = W / n
    for j in range(n + 1):
        for i in range(n + 1):
            cx = i * p + (p / 2 if j % 2 else 0)
            cy = j * p
            r = p * 0.30
            for ox in (-W, 0, W):
                for oy in (-W, 0, W):
                    d.ellipse([cx + ox - r - 2, cy + oy - r - 2, cx + ox + r + 2, cy + oy + r + 2], fill=(120, 122, 126))
                    d.ellipse([cx + ox - r, cy + oy - r, cx + ox + r, cy + oy + r], fill=(14, 14, 15))
    _save(img, 'interior_perf_alu.png')


def _band_noise(n, f_lo, f_hi, seed):
    """Seamless band-pass noise (n x n), frequencies in cycles per tile, normalised to std 1."""
    rng = np.random.default_rng(seed)
    w = rng.normal(0, 1, (n, n))
    F = np.fft.fft2(w)
    fy = np.fft.fftfreq(n)[:, None] * n
    fx = np.fft.fftfreq(n)[None, :] * n
    fr = np.sqrt(fx * fx + fy * fy)
    band = np.exp(-((np.log(np.maximum(fr, 1e-3)) - np.log(math.sqrt(f_lo * f_hi))) / (0.5 * np.log(f_hi / f_lo))) ** 2)
    out = np.real(np.fft.ifft2(F * band))
    return (out - out.mean()) / (out.std() + 1e-9)


def paint_leather_normal():
    """Fine pebble leather grain (~1.2 mm cells, soft 6 mm wrinkles), seamless, 0.125 m per 512 px tile."""
    from PIL import Image
    n = 512
    pebble = -np.abs(_band_noise(n, 80, 130, 21))            # ridged: soft domes with creases between them
    wrinkle = _band_noise(n, 15, 28, 22)
    h = pebble * 1.0 + wrinkle * 0.45
    gy, gx = np.gradient(h)
    k = 0.9
    nx, ny, nz = -gx * k, gy * k, np.ones_like(h)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    rgb = np.dstack([nx / ln, ny / ln, nz / ln]) * 0.5 + 0.5
    _save(Image.fromarray((rgb * 255).clip(0, 255).astype(np.uint8)), 'interior_leather_normal.png')


def paint_grey_suede():
    """The shared black suede brightened to the grey inserts of the GLX seat (#4a4b50 mean)."""
    from PIL import Image
    a = np.asarray(Image.open(_tp('seat_suede.png')).convert('RGB')).astype(np.float32)
    mean = a.reshape(-1, 3).mean(0)
    # r6: #6e7480 bluish grey (seat_closeup / interior_dash / front.png bolsters L 122-151; r5 #1e2023 read black)
    tgt = np.array([110, 116, 128], np.float32)
    dev = (a - mean) * 5.0                                   # the shared nap is very flat (std ~1.2)
    H, W = a.shape[:2]
    mott = _band_noise_hw(H, W, 6, 14, 51) * 4.0 + _band_noise_hw(H, W, 60, 120, 52) * 2.5
    out = tgt + dev + mott[..., None]
    _save(Image.fromarray(out.clip(0, 255).astype(np.uint8)), 'interior_seat_grey_suede.png')


def paint_lowrance_night():
    """Night palette of the shared DuneNav chart page: dark slate terrain with dim relief, light labels, the track
    and markers kept saturated (the day chart glowed beige in the game)."""
    from PIL import Image
    a = np.asarray(Image.open(_tp('screen_lowrance.png')).convert('RGB')).astype(np.float32)
    H, W = a.shape[:2]
    out = a * 0.80
    y0, y1, x1 = int(H * 0.0625), int(H * 0.93), int(W * 0.625)          # chart window (left 5/8, between bars)
    m = a[y0:y1, :x1]
    L = m.mean(-1, keepdims=True)
    mx, mn = m.max(-1, keepdims=True), m.min(-1, keepdims=True)
    sat = (mx - mn) / np.maximum(mx, 1)
    rel = (L - L.mean()) / (L.std() + 1e-6)                          # terrain relief
    terrain = np.array([30, 36, 44], np.float32) * (1.0 + 0.22 * rel)
    terrain += np.array([10, 9, 4], np.float32) * np.clip(rel, 0, 3)  # faint warm ridges
    dark_ink = (L < 70)                                               # labels / contour lines / roads
    ink = np.array([150, 158, 168], np.float32) * np.ones_like(m)
    keep = (sat > 0.45) & (np.abs(m[..., 2:3] - m[..., 0:1]) > 60)    # blue track, red markers
    res = np.where(dark_ink, ink, terrain)
    res = np.where(keep, m * 0.85 + np.array([0, 20, 30], np.float32) * (m[..., 2:3] > m[..., 0:1]), res)
    out[y0:y1, :x1] = res
    _save(Image.fromarray(out.clip(0, 255).astype(np.uint8)), 'interior_screen_lowrance_night.png')


def paint_screen_off():
    """r4: switched-off screen glass for the static model (every photo shows the screens off). It is the screens'
    EMISSIVE map on purpose: the game's cockpit-live.js swaps an emissive map for its live canvas."""
    from PIL import Image
    W, H = 64, 64
    yy = np.linspace(0, 1, H)[:, None] * np.ones((1, W))
    v = 2.0 + 2.0 * (1 - yy)
    _save(Image.fromarray(np.dstack([v, v * 1.05, v * 1.25]).clip(0, 255).astype(np.uint8)), 'interior_screen_off.png')


def paint_webbing_normal():
    """r4: harness webbing: ~1.5 mm ribs running ALONG the strap (u = across the strap, 36 ribs per strap width;
    v = along, 0.25 m per tile) with a faint weave / slub noise along the length."""
    from PIL import Image
    W, H = 512, 256
    u = (np.arange(W) + 0.5) / W
    ph = u * 36.0
    h = np.abs(np.sin(math.pi * ph)) ** 0.7                    # rounded ribs with narrow grooves
    dhdu = np.gradient(h) * W / 36.0
    rng = np.random.default_rng(7)
    slub = rng.normal(0, 1, (H // 4, W // 8)).astype(np.float32)
    slub = np.asarray(Image.fromarray(((slub * 30) + 128).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC),
                      np.float32) / 255.0 - 0.5
    weave = np.sin(np.arange(H)[:, None] * 2 * math.pi / 4.0 + (np.floor(ph)[None, :] % 2) * math.pi) * 0.15
    nx = -dhdu[None, :] * 0.35 * np.ones((H, 1)) + slub * 0.10
    ny = weave * 0.6 + np.gradient(slub, axis=0) * 2.0
    nz = np.ones_like(nx)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    rgb = np.dstack([nx / ln, ny / ln, nz / ln]) * 0.5 + 0.5
    _save(Image.fromarray((rgb * 255).clip(0, 255).astype(np.uint8)), 'interior_webbing_normal.png')


def paint_hex_dark():
    """The shared hex mesh darkened to the dark-grey dash grilles of interior_dash.png (alpha kept)."""
    from PIL import Image
    a = np.asarray(Image.open(_tp('hex_mesh.png')).convert('RGBA')).astype(np.float32)
    a[..., :3] *= 0.42
    _save(Image.fromarray(a.clip(0, 255).astype(np.uint8), 'RGBA'), 'interior_hex_dark.png')


def paint_floor_mat():
    """The shared diamond floor mat lifted to charcoal rubber: background ~sRGB 50, the raised ribs and the GLX
    plate edge lighter (contrast doubled about the old 21 mean)."""
    from PIL import Image
    a = np.asarray(Image.open(_tp('floor_mat.png')).convert('RGB')).astype(np.float32)
    m = float(a.mean())
    out = 54.0 + (a - m) * 2.1
    _save(Image.fromarray(out.clip(0, 255).astype(np.uint8)), 'interior_floor_mat.png')


def paint_mpi_logo():
    """Satin-black horn-button / spoke badge face with the small white DRV logo (square, 0.06 m across)."""
    from PIL import Image, ImageDraw
    W = 512
    img = Image.new('RGB', (W, W), (18, 18, 19))
    d = ImageDraw.Draw(img)
    f = _font(150, 'Black', italic=True)
    t = Image.new('L', (W, W), 0)
    td = ImageDraw.Draw(t)
    tw = td.textlength('DRV', font=f)
    td.text(((W - tw) / 2, W / 2 - 95), 'DRV', font=f, fill=255)
    # italic shear when the font has no italic face
    t = t.transform((W, W), Image.AFFINE, (1, 0.22, -0.22 * W / 2, 0, 1, 0), resample=Image.BICUBIC)
    bb = t.getbbox()
    if bb:
        crop = t.crop(bb)
        sc = (0.50 * W) / crop.width                 # logo 30 mm wide on the 60 mm texture
        crop = crop.resize((int(crop.width * sc), max(1, int(crop.height * sc))), Image.LANCZOS)
        img.paste((236, 236, 236), ((W - crop.width) // 2, (W - crop.height) // 2), crop)
        # thin underline swoosh
        y = (W + crop.height) // 2 + 8
        d.polygon([((W - crop.width) // 2 + 10, y), ((W + crop.width) // 2, y - 6), ((W + crop.width) // 2 - 6, y + 4),
                   ((W - crop.width) // 2 + 6, y + 9)], fill=(236, 236, 236))
    _save(img, 'interior_mpi_logo.png')


def paint_pci():
    """r6: the shared placard_pci.png with its aluminium field scaled to ~#9da1a6 (brushed aluminium ~150-160)."""
    from PIL import Image
    a = np.asarray(Image.open(_tp('placard_pci.png')).convert('RGB')).astype(np.float32)
    lum = a.mean(-1)
    field = a[(lum > 140) & (np.abs(a[..., 2] - a[..., 0]) < 25)].mean(0)
    k = np.array([157.0, 161.0, 166.0], np.float32) / np.maximum(field, 1.0)
    _save(Image.fromarray((a * k).clip(0, 255).astype(np.uint8)), 'interior_pci.png')


def paint_wheel_badge():
    """r6: white 24 x 12 mm badge on the 6 o'clock spoke (interior_dash.png): white field, small black italic DRV."""
    from PIL import Image, ImageDraw
    W, H = 256, 128
    img = Image.new('RGB', (W, H), (232, 232, 230))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=(150, 150, 152), width=4)
    d.text((W // 2, H // 2 - 4), 'DRV', font=_font(70, 'Black', italic=True), fill=(18, 18, 20), anchor='mm')
    d.line([(70, 100), (190, 92)], fill=(18, 18, 20), width=5)
    _save(img, 'interior_wheel_badge.png')


def _band_noise_hw(h, w, f_lo, f_hi, seed):
    """Seamless band-pass noise (h x w), frequencies in cycles per tile (along the longer side), std 1."""
    rng = np.random.default_rng(seed)
    F = np.fft.fft2(rng.normal(0, 1, (h, w)))
    fy = np.fft.fftfreq(h)[:, None] * max(h, w)
    fx = np.fft.fftfreq(w)[None, :] * max(h, w)
    fr = np.sqrt(fx * fx + fy * fy)
    band = np.exp(-((np.log(np.maximum(fr, 1e-3)) - np.log(math.sqrt(f_lo * f_hi))) / (0.5 * np.log(f_hi / f_lo))) ** 2)
    out = np.real(np.fft.ifft2(F * band))
    return (out - out.mean()) / (out.std() + 1e-9)


def paint_door_quilt():
    """r5: door quilting (interior_dash.png): puffy black leather diamonds 64 x 72 mm with deep seam valleys and TWO
    orange stitch rows 6 mm apart along every seam (was the shared door_quilt.png: 42 mm diamonds, one row, shallow).
    Tile = 2 x 2 diamonds = QUILT_TILE (0.128 x 0.144 m) at 8 px / mm; OpenGL normal map + colour with baked valley AO."""
    from PIL import Image
    DW, DH = 64.0, 72.0                                    # diamond width / height (mm)
    PX = 8.0
    W, H = int(2 * DW * PX), int(2 * DH * PX)
    x = (np.arange(W) + 0.5)[None, :] / PX                 # mm, +x to the right
    y = (H - (np.arange(H) + 0.5))[:, None] / PX           # mm, +y up (texture v)
    s, t = x / DW, y / DH
    kn = math.hypot(1 / DW, 1 / DH)                        # |grad| of s +- t per mm
    a = s + t
    b = s - t
    da = (a - np.round(a)) / kn                            # signed distance (mm) to the nearest seam of each family
    db = (b - np.round(b)) / kn
    d = np.minimum(np.abs(da), np.abs(db))
    rin = 0.5 / kn                                         # diamond inradius (mm)
    # pillow: rounded crown, V into the seam, narrow 1.6 mm groove at the seam centre; height in mm
    hh = 3.2 * (1 - (1 - np.clip(d / (0.85 * rin), 0, 1)) ** 2.2) - 0.7 * np.exp(-(d / 0.9) ** 2)
    hh += 0.06 * _band_noise_hw(H, W, 60, 110, 31) - 0.10 * np.abs(_band_noise_hw(H, W, 9, 16, 32))   # grain, soft creases
    # stitches: two rows at +-3 mm of each seam line, 4 mm dashes every 6 mm along the seam
    along_a = b * (0.5 * math.hypot(DW, DH))               # along family-a lines (mm)
    along_b = a * (0.5 * math.hypot(DW, DH))
    st = np.zeros((H, W), np.float32)
    for dd, al in ((da, along_a), (db, along_b)):
        for off in (-3.0, 3.0):
            across = np.abs(dd - off)
            ph = (al / 6.0) % 1.0
            dash = np.clip(1.0 - np.abs(ph - 0.33) / 0.33, 0, 1) ** 0.35
            st = np.maximum(st, np.clip(1.0 - across / 0.75, 0, 1) ** 0.6 * (dash > 0.25) * np.clip(dash * 1.6, 0, 1))
    hh = hh + 0.35 * st
    # colour: black leather with darker valleys (baked occlusion) and a faint sheen on the crowns
    ao = 0.42 + 0.58 * np.clip((hh + 0.7) / 3.9, 0, 1) ** 0.8
    base = (19.0 + 2.5 * _band_noise_hw(H, W, 30, 60, 33)) * ao
    col = np.dstack([base, base * 1.0, base * 1.08])
    thread = np.array([236, 100, 28], np.float32)
    col = col * (1 - st[..., None]) + thread * (0.75 + 0.25 * ao[..., None]) * st[..., None]
    _save(Image.fromarray(col.clip(0, 255).astype(np.uint8)), 'interior_door_quilt.png')
    gy, gx = np.gradient(hh)                               # per pixel; rows run DOWN = -y
    nx, ny = -gx * PX, gy * PX                             # height mm per pixel -> slope per mm
    nz = np.ones_like(hh)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    rgb = np.dstack([nx / ln, ny / ln, nz / ln]) * 0.5 + 0.5
    _save(Image.fromarray((rgb * 255).clip(0, 255).astype(np.uint8)), 'interior_door_quilt_normal.png')


def paint_seat_suede():
    """r5: the seat's black suede ~0.45x darker in linear albedo (seat_closeup.png: centre / headrest ~17-20 under the
    studio, r4 render 51): the shared seat_suede.png nap scaled to a mean of ~12 sRGB (#0c0c0e)."""
    from PIL import Image
    a = np.asarray(Image.open(_tp('seat_suede.png')).convert('RGB')).astype(np.float32)
    m = a.reshape(-1, 3).mean(0)
    out = np.array([12.0, 12.0, 13.5], np.float32) + (a - m) * 0.75
    _save(Image.fromarray(out.clip(0, 255).astype(np.uint8)), 'interior_seat_suede.png')


_PAINTERS = {
    'interior_door_quilt.png': paint_door_quilt,
    'interior_seat_suede.png': paint_seat_suede,
    'interior_screen_off.png': paint_screen_off,
    'interior_webbing_normal.png': paint_webbing_normal,
    'interior_mpi_logo.png': paint_mpi_logo,
    'interior_screen_lowrance_night.png': paint_lowrance_night,
    'interior_floor_mat.png': paint_floor_mat,
    'interior_hex_dark.png': paint_hex_dark,
    'interior_leather_normal.png': paint_leather_normal,
    'interior_seat_grey_suede.png': paint_grey_suede,
    'interior_dash_decal.png': paint_dash_decal,
    'interior_switch_grid.png': paint_switch_grid,
    'interior_lowrance_bezel.png': paint_lowrance_bezel,
    'interior_race_radio.png': paint_race_radio,
    'interior_stereo_face.png': paint_stereo_face,
    'interior_seat_back.png': paint_seat_back,
    'interior_harness_label.png': paint_harness_label,
    'interior_perf_alu.png': paint_perf_alu,
    'interior_wheel_badge.png': paint_wheel_badge,
    'interior_pci.png': paint_pci,
}


def ensure_textures(force=False):
    from PIL import Image
    for name, fn in _PAINTERS.items():
        ok = False
        if not force and os.path.exists(_tp(name)):
            try:
                ok = Image.open(_tp(name)).text.get('interior') == TEXV
            except Exception:
                ok = False
        if not ok:
            try:
                fn()
                print('[interior] painted', name)
            except Exception as e:      # never fail the build on a texture: fall back to plain colours
                print('[interior] texture', name, 'failed:', e)


def have(name):
    return os.path.exists(_tp(name))


# =====================================================================================================
#  MATERIALS
# =====================================================================================================

def mats():
    t = have
    lgrain = 'interior_leather_normal.png' if t('interior_leather_normal.png') else None
    # r4: the screens are OFF in the static model (photos): base #050608 under a clear coat, emission = a near-black
    # 'off' texture (kept as the emissive MAP so cockpit-live.js can still put its live canvas there; strength 0.6 as
    # before, so the game's lit screens keep their brightness). TRX_SCREENS_ON=1 builds the old lit pictures.
    scr_on = os.environ.get('TRX_SCREENS_ON', '') not in ('', '0')
    off_tex = 'interior_screen_off.png' if t('interior_screen_off.png') else None
    scr_off = None
    low_tex = 'interior_screen_lowrance_night.png' if t('interior_screen_lowrance_night.png') else 'screen_lowrance.png'
    mt = {
        'carbon': M('carbon'),
        # r5: darker suede (interior_seat_suede.png, ~#0c0c0e); also the wheel rim (same material, game LOOKS key)
        'suede': (mat('Interior suede', tex='interior_seat_suede.png', rough=0.95, uv_scale=(5, 5))
                  if t('interior_seat_suede.png') else M('suede')),
        # r6: suede centre with the charcoal leather wings round the pass-throughs painted in (+ roughness map)
        'seatback': (mat('Interior seat back', tex='interior_seat_back.png', rough=0.93,
                         rough_tex='interior_seat_back_rough.png' if t('interior_seat_back_rough.png') else None)
                     if t('interior_seat_back.png') else M('suede')),
        'leather': M('leather'),
        # black seat leather with a fine pebble grain; grey suede only on the inner faces of the lower bolsters
        # r6: charcoal leather shoulder wings (~#3a3d42, seat_closeup.png; r5 #131416 read black)
        'seat_leather': mat('Interior seat leather', '#3a3d42', rough=0.6, normal=lgrain, normal_strength=0.3,
                            uv_scale=(4, 4)) if lgrain else mat('Interior seat leather', '#3a3d42', rough=0.6),
        'seat_grey_suede': (mat('Interior seat grey suede', tex='interior_seat_grey_suede.png', rough=0.95, uv_scale=(5, 5))
                            if t('interior_seat_grey_suede.png') else mat('Interior seat grey suede', '#3a3b3e', rough=0.95)),
        'leather_blk': mat('Interior leather black', '#161617', rough=0.72, normal=lgrain, normal_strength=0.3,
                           uv_scale=(4, 4)) if lgrain else mat('Interior leather black', '#161617', rough=0.72),
        'shell': mat('Interior seat shell fabric', '#0f0f10', rough=0.85),     # r3: sRGB ~15
        'stitch': M('stitch'),
        # r4: darker webbing (#0e0e0e) with fine 1.5 mm ribs along the strap
        'belt': (mat('Interior harness webbing', '#0e0e0e', rough=0.75, normal='interior_webbing_normal.png',
                     normal_strength=0.8) if t('interior_webbing_normal.png') else M('belt')),
        # r5: mesh-faced shoulder pads with the webbing relief
        'pad': (mat('Interior harness pad', '#171717', rough=0.9, normal='interior_webbing_normal.png', normal_strength=0.6)
                if t('interior_webbing_normal.png') else mat('Interior harness pad', '#171717', rough=0.9)),
        'label': mat('Interior harness label', tex='interior_harness_label.png', rough=0.6),
        'black': M('satin_black'),
        'gloss': M('gloss_black'),
        'anod': mat('Interior black anodized', '#161618', metal=0.7, rough=0.33),
        # r3: satin (not gloss) horn button + ring, small white DRV logo
        'horn': mat('Interior horn satin black', '#121213', rough=0.5),
        # r6: the spoke plate stays the satin black anodised finish (game LOOKS SteeringWheel_Mesh entry); white badge
        'spoke': mat('Interior black anodized', '#161618', metal=0.7, rough=0.33),
        'badge': (mat('Interior wheel badge', tex='interior_wheel_badge.png', rough=0.4) if t('interior_wheel_badge.png')
                  else mat('Interior wheel badge', '#e8e8e6', rough=0.4)),
        'mpi': mat('Interior MPI badge', tex='interior_mpi_logo.png', rough=0.5) if t('interior_mpi_logo.png')
               else mat('Interior horn satin black', '#121213', rough=0.5),
        'rubber': M('rubber'),
        'hole': mat('Interior slot black', '#050505', rough=0.9),
        'alu': M('alu'),
        'polished': M('polished'),
        'chrome': M('chrome'),
        'steel': M('steel_dark'),
        'red': mat('Interior red button', '#c4090b', rough=0.22, clearcoat=0.6),
        'blue': mat('Interior blue button', '#1e74e8', rough=0.3, clearcoat=0.5),
        'orange': M('orange'),
        'mesh': M('mesh_grille'),
        'mesh_dark': (mat('Interior hex mesh dark', tex='interior_hex_dark.png', alpha_tex=True, alpha_clip=0.5, metal=0.85,
                          rough=0.45, double_sided=True) if t('interior_hex_dark.png') else M('mesh_grille')),
        'carbon_satin': M('carbon'),        # r5: the dash brow / visor top is gloss carbon too (was 'Carbon satin')
        'livery_top': M('livery_top'),
        'perf': mat('Interior perforated aluminum', tex='interior_perf_alu.png', metal=0.85, rough=0.32),
        # r3: charcoal rubber (sRGB ~50, was 21) with lighter raised diamond ribs / GLX plate edge
        'mat': mat('Interior floor mat', tex='interior_floor_mat.png' if t('interior_floor_mat.png') else 'floor_mat.png',
                   normal='floor_mat_normal.png', rough=0.75),
        # r5: own quilt (64 x 72 mm diamonds, double stitch rows, deep valleys); was the shared door_quilt.png
        'quilt': (mat('Interior door quilt', tex='interior_door_quilt.png', normal='interior_door_quilt_normal.png', rough=0.5)
                  if t('interior_door_quilt_normal.png') else
                  mat('Interior door quilt', tex='door_quilt.png', normal='door_quilt_normal.png', rough=0.5)),
        # r6: deep black gloss (tows 18 / 30), 2.2x finer weave; softer relief (the half-res normal map is ~2 px per tow)
        'decal': mat('Interior dash carbon', tex='interior_dash_decal.png', normal='interior_dash_decal_normal.png',
                     normal_strength=0.4, rough=0.25, clearcoat=1.0),
        'fw_orange': mat('Interior firewall orange', tex='firewall_orange.png', rough=0.25, clearcoat=0.9),
        # r3: lit for the game but much dimmer (emission 0.6, was 1.3-1.6) under a clear coat; the DuneNav uses a
        # night chart. TRX_SCREENS_OFF=1 swaps all three for the shared M('screen') (every photo shows them off).
        'scr_dash': mat('Interior screen dash', '#050608', emit_tex='screen_dash.png' if scr_on else off_tex,
                        emit_strength=0.6, rough=0.08, clearcoat=1.0),
        'scr_low': mat('Interior screen lowrance', '#050608', emit_tex=low_tex if scr_on else off_tex, emit_strength=0.6,
                       rough=0.08, clearcoat=1.0),
        'scr_radio': mat('Interior screen stereo', '#050608', emit_tex='screen_radio.png' if scr_on else off_tex,
                         emit_strength=0.6, rough=0.08, clearcoat=1.0),
        'switches': mat('Interior switch panel', tex='interior_switch_grid.png', emit_tex='interior_switch_grid.png',
                        emit_strength=0.45, rough=0.3),
        # r4: matte suede 12 o'clock marker (photo: matte leather band, not gloss paint); the game has a LOOKS entry
        'marker': mat('Wheel marker orange', '#ff5a0d', rough=0.85),
        # r4: bead-blasted escutcheon dish (photo: pale satin silver; a rough metal also reads light under soft keys)
        'esc': mat('Interior escutcheon satin aluminum', '#d6d9dc', metal=1.0, rough=0.42),
        # r4: the recess between the dash lip and the cowl: matte near-black so it reads as a dark gap (photo), not
        # as a grey shelf where 'Satin black' (rough .5) mirrors the sky at the driver's grazing angle in the game
        'recess': mat('Interior dash recess black', '#060607', rough=0.92),
        'low_bezel': mat('Interior lowrance bezel', tex='interior_lowrance_bezel.png', rough=0.2, clearcoat=0.6),
        'radio': mat('Interior race radio face', tex='interior_race_radio.png', rough=0.4),
        'stereo': mat('Interior stereo face', tex='interior_stereo_face.png', rough=0.3),
        # r6: own copy of the shared placard tinted to brushed aluminium (~#9da1a6; it rendered near-white)
        'pci': mat('Interior PCI plate', tex='interior_pci.png' if t('interior_pci.png') else 'placard_pci.png', metal=0.35,
                   rough=0.35),
    }
    # r5: suede barely reflects - the default 4 % dielectric specular (F0 0.04 at roughness 0.95) floored the seats at
    # ~2x the photo's brightness whatever the albedo; lower the specular level (glTF KHR_materials_specular)
    for k in ('suede', 'seatback', 'seat_grey_suede', 'belt', 'pad'):
        try:
            mt[k].node_tree.nodes['Principled BSDF'].inputs['Specular IOR Level'].default_value = 0.15
        except Exception:
            pass
    return mt


# =====================================================================================================
#  GEOMETRY HELPERS
# =====================================================================================================

def smooth01(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def interp(table, x):
    """Piecewise-linear lookup in [(x, y), ...] (sorted)."""
    if x <= table[0][0]:
        return table[0][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return table[-1][1]


def catmull(pts, sub=2, closed=False):
    """Catmull-Rom resample of a 2D/3D polyline (each segment split into `sub`)."""
    P = [np.array(p, float) for p in pts]
    n = len(P)
    out = []
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0 = P[(i - 1) % n] if (closed or i > 0) else P[i]
        p1 = P[i]
        p2 = P[(i + 1) % n]
        p3 = P[(i + 2) % n] if (closed or i + 2 < n) else P[(i + 1) % n]
        for k in range(sub):
            t = k / sub
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    if not closed:
        out.append(P[-1])
    return [tuple(p) for p in out]


def sharpen(o, deg=40):
    me = o.data
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=math.radians(deg))
    except Exception:
        pass
    return o


def finish_bm(name, bm, mlist, deg=40, recalc=False, face_toward=None):
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    o = obj_from_bmesh(name, bm, mlist, smooth=True, angle=deg)
    return sharpen(o, deg)


def grid_bm(P, closed_u=False, cap=False, bm=None):
    """Quad grid from rows of points (rows = sections). Returns (bm, [(face, j, i)], caps)."""
    bm = bm or bmesh.new()
    rows, cols = len(P), len(P[0])
    vs = [[bm.verts.new(V(p)) for p in row] for row in P]
    faces = []
    for j in range(rows - 1):
        for i in range(cols - (0 if closed_u else 1)):
            i2 = (i + 1) % cols
            q = [vs[j][i], vs[j][i2], vs[j + 1][i2], vs[j + 1][i]]
            uq = []
            for v in q:
                if v not in uq:
                    uq.append(v)
            if len(uq) < 3:
                continue
            try:
                faces.append((bm.faces.new(uq), j, i))
            except ValueError:
                pass
    caps = []
    if cap and closed_u:
        for r in (vs[0], vs[-1][::-1]):
            try:
                caps.append(bm.faces.new(r[::-1]))
            except ValueError:
                pass
    return bm, faces, caps


def set_uv(bm, face, fn):
    lay = bm.loops.layers.uv.verify()
    n = face.normal
    for lp in face.loops:
        lp[lay].uv = fn(lp.vert.co, n)


def metric_uv(scale=1.0):
    """Box projection, `scale` UV units per metre (carbon / leather / suede)."""
    def f(co, n):
        ax = max(range(3), key=lambda i: abs(n[i]))
        if ax == 0:
            return (co.y * scale, co.z * scale)
        if ax == 1:
            return (co.x * scale, co.z * scale)
        return (co.x * scale, co.y * scale)
    return f


def decal_A(co, n):
    return ((co.x - DA_X0) * DA_PPM / DEC_W, 1.0 - (DA_Z1 - co.z) * DA_PPM / DEC_H)


def rrect(w, h, r, n=4):
    """Rounded rectangle outline (CCW), centred, r = corner radius (or 4-list)."""
    rs = r if isinstance(r, (list, tuple)) else [r] * 4
    out = []
    corners = [(w / 2, -h / 2, -90), (w / 2, h / 2, 0), (-w / 2, h / 2, 90), (-w / 2, -h / 2, 180)]
    for (cx, cy, a0), rr in zip(corners, rs):
        sx = -1 if cx > 0 else 1
        sy = -1 if cy > 0 else 1
        if rr <= 0:
            out.append((cx, cy))
            continue
        ox, oy = cx + sx * rr, cy + sy * rr
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            out.append((ox + rr * math.cos(a), oy + rr * math.sin(a)))
    return out


def poly_area(pts):
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


def offset2d(pts, d):
    """Offset a CCW polygon inward by d (miter, clamped)."""
    n = len(pts)
    P = [V((p[0], p[1], 0)) for p in pts]
    out = []
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        e1 = (b - a)
        e2 = (c - b)
        if e1.length < 1e-9:
            e1 = e2
        if e2.length < 1e-9:
            e2 = e1
        e1.normalize(); e2.normalize()
        n1 = V((-e1.y, e1.x, 0)); n2 = V((-e2.y, e2.x, 0))
        m = n1 + n2
        if m.length < 1e-6:
            m = n1
        m.normalize()
        k = 1.0 / max(0.35, m.dot(n1))
        q = b + m * d * k
        out.append((q.x, q.y))
    return out


def slab(name, outline, frame, depth, mats_fb, bevel=0.0, segs=2, uv_front=None, uv_side=None, back=True,
         front_mat=0, side_mat=1, deg=35):
    """Extrude a 2D outline (in frame (origin, ux, uy)) from c=-depth (back) to c=0 (front face), with a rounded
    front edge of radius `bevel`.  uv_front(a, b) -> (u, v) for the front cap (frame coords)."""
    org, ux, uy = V(frame[0]), V(frame[1]).normalized(), V(frame[2]).normalized()
    nz = ux.cross(uy).normalized()
    pts = list(outline)
    if poly_area(pts) < 0:
        pts = pts[::-1]

    def W(a, b, c):
        return org + ux * a + uy * b + nz * c

    rings = [(pts, -depth)]
    if bevel > 0:
        for k in range(segs + 1):
            ang = 0.5 * math.pi * k / segs
            rings.append((offset2d(pts, bevel * (1 - math.cos(ang))), -bevel + bevel * math.sin(ang)))
    else:
        rings.append((pts, 0.0))
    bm = bmesh.new()
    vr = [[bm.verts.new(W(a, b, c)) for (a, b) in ring] for ring, c in rings]
    n = len(pts)
    lay = bm.loops.layers.uv.verify()
    side_faces = []
    for j in range(len(vr) - 1):
        for i in range(n):
            i2 = (i + 1) % n
            try:
                f = bm.faces.new((vr[j][i], vr[j][i2], vr[j + 1][i2], vr[j + 1][i]))
                f.material_index = side_mat
                side_faces.append(f)
            except ValueError:
                pass
    fr = bm.faces.new(vr[-1])
    fr.material_index = front_mat
    inv = Matrix((ux, uy, nz)).transposed().inverted()
    for lp in fr.loops:
        loc = inv @ (lp.vert.co - org)
        lp[lay].uv = uv_front(loc.x, loc.y) if uv_front else (loc.x * CS, loc.y * CS)
    if back:
        bk = bm.faces.new(vr[0][::-1])
        bk.material_index = side_mat
        side_faces.append(bk)
    suv = uv_side or metric_uv(CS)
    for f in side_faces:
        f.normal_update()
        for lp in f.loops:
            lp[lay].uv = suv(lp.vert.co, f.normal)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    o = obj_from_bmesh(name, bm, mats_fb, smooth=True, angle=deg)
    return sharpen(o, deg)


def face_frame(origin, normal, up=(0, 0, 1)):
    """(origin, ux, uy) for a face whose front normal is `normal` (ux = viewer's right, uy = up)."""
    n = V(normal).normalized()
    ux = V(up).cross(n).normalized()
    uy = n.cross(ux).normalized()
    return (V(origin), ux, uy)


def quad(name, frame, w, h, material, c=0.0, uv=((0, 0), (1, 0), (1, 1), (0, 1)), a0=0.0, b0=0.0):
    org, ux, uy = frame
    nz = ux.cross(uy)
    bm = bmesh.new()
    pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    vs = [bm.verts.new(org + ux * (a0 + a) + uy * (b0 + b) + nz * c) for (a, b) in pts]
    f = bm.faces.new(vs)
    lay = bm.loops.layers.uv.verify()
    for lp, t in zip(f.loops, uv):
        lp[lay].uv = t
    o = obj_from_bmesh(name, bm, [material], smooth=False)
    return o


def cyl_at(name, r, h, base, axis, material, segs=16, r2=None, cap=True, deg=40):
    """Cylinder from base along axis (length h)."""
    ax = V(axis).normalized()
    o = cylinder(name, r, h, (0, 0, 0), material=material, segments=segs, r2=r2, cap=cap)
    o.matrix_basis = aligned_matrix(V(base) + ax * h / 2, ax)
    apply_transform(o)
    return sharpen(o, deg)


def lathe_at(name, profile, base, axis, material, segs=24, deg=35):
    o = lathe(name, profile, material, segments=segs)
    o.matrix_basis = aligned_matrix(V(base), V(axis))
    apply_transform(o)
    return sharpen(o, deg)


def ttube(name, pts, r, material, sides=12, bend=None, deg=55):
    return sharpen(tube(name, pts, r, material, sides=sides, bend=bend), deg)


def bbox_uv(w, h):
    return lambda a, b: (a / w + 0.5, b / h + 0.5)


def xform(objs, mw):
    for o in objs:
        apply_transform(o)
        o.data.transform(mw)
    return objs


def ribbon(name, pts, normals, width, thick, material, mats_extra=None, uvlen=True, sub=3):
    """Flat strap (rectangular section) along a polyline; normals[i] = the 'face' direction at pts[i]."""
    P = [V(p) for p in pts]
    N = [V(n).normalized() for n in normals]
    if sub > 1 and len(P) > 2:
        P = [V(p) for p in catmull([tuple(p) for p in P], sub)]
        Nn = [V(p) for p in catmull([tuple(n) for n in N], sub)]
        N = [n.normalized() for n in Nn]
    secs = []
    for i, p in enumerate(P):
        if i == 0:
            t = P[1] - P[0]
        elif i == len(P) - 1:
            t = P[-1] - P[-2]
        else:
            t = P[i + 1] - P[i - 1]
        t.normalize()
        s = t.cross(N[i]).normalized()
        nn = s.cross(t).normalized()
        hw, ht = width / 2, thick / 2
        secs.append([p - s * hw - nn * ht, p + s * hw - nn * ht, p + s * hw + nn * ht, p - s * hw + nn * ht])
    bm, faces, caps = grid_bm(secs, closed_u=True, cap=True)
    lay = bm.loops.layers.uv.verify()
    acc = [0.0]
    for i in range(1, len(P)):
        acc.append(acc[-1] + (P[i] - P[i - 1]).length)
    for f, j, i in faces:
        f.material_index = 0
        for lp in f.loops:
            # u across, v along
            k = [kk for kk in range(4) if (secs[j][kk] - lp.vert.co).length < 1e-7 or (secs[j + 1][kk] - lp.vert.co).length < 1e-7]
            jj = j if any((secs[j][kk] - lp.vert.co).length < 1e-7 for kk in range(4)) else j + 1
            kk = k[0] if k else 0
            lp[lay].uv = ((0.0, 1.0, 1.0, 0.0)[kk], acc[jj] * 4)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    o = obj_from_bmesh(name, bm, [material] + (mats_extra or []), smooth=True, angle=50)
    return sharpen(o, 50)


# =====================================================================================================
#  DASH
# =====================================================================================================
# r4: top of the body's hood skin at its rear edge (y 0.775-0.78, probed from parts/body.py r4; the skin is 4 mm
# thick with a short return lip at y 0.767-0.775); the dash front tucks 1.6 cm under it
COWL_MIN = [(0.0, 1.100), (0.1, 1.099), (0.2, 1.096), (0.25, 1.094), (0.3, 1.084), (0.35, 1.087), (0.4, 1.091),
            (0.45, 1.098), (0.5, 1.105), (0.55, 1.111), (0.6, 1.117), (0.7, 1.119)]   # r6: re-probed (body r6, y 0.766)
DASH_X = 0.672              # dash ends against the door cards
DRV_BROW = (-0.665, -0.115)  # x range of the visor over the digital dash

# r4: the passenger / centre dash has NO top shelf any more (the photo shows the hood right behind the lip): a rounded
# gloss lip (R ~23 mm, crown at y ~0.535) on the face, then the top drops behind it into a satin-black recess (floor
# z ~0.98, just over the chassis dash bar whose top is 0.972 at y 0.736-0.78) that rises again at y ~0.765 to tuck
# under the hood's rear edge. Lip crown height LIP_Z at the centre, lowered toward the passenger door by PASS_DROP
# (photo lip top: 1.044 @ x 0, 1.025 @ 0.14, 1.007 @ 0.26, 0.99 @ 0.36, 0.98 @ 0.43).
LIP_Z = 1.018               # (photo back-projection with the current camera: 1.019 @ x 0 .. 1.002 @ 0.37)
RECESS_FLOOR = 0.979        # >= 7 mm over the dash bar
PASS_DROP = [(0.10, 0.0), (0.20, -0.006), (0.26, -0.013), (0.36, -0.027), (0.43, -0.034), (0.60, -0.036),
             (0.672, -0.030)]
# (y, z) control profile, front-bottom -> front-top -> top under the hood -> recess wall / floor -> lip -> face ->
# lower curl -> underside. 'C' = cowl-derived, ('L', dz) = lip crown + dz, ('F', z) = recess floor (>= RECESS_FLOOR)
# r6 (spec DASH_BROW_Z): a rolled carbon BROW across the whole width right behind the hood's rear edge (y 0.766): its front
# face rises steeply behind the hood edge, the crown ('B' = brow_z(x)) sits at y ~0.70, and behind it the top falls to the
# driver's visor over the digital dash / to the passenger lip. ('B', dz) = brow crown + dz.
_DASH_N = [(0.80, 0.785), (0.80, 'C1'), (0.776, 'C'), (0.764, ('C', 0.004)), (0.752, ('B', -0.019)),
           (0.733, ('B', -0.005)), (0.708, ('B', 0.0)), (0.682, ('B', -0.003)), (0.652, ('B', -0.016)),
           (0.622, ('B', -0.040)), (0.590, ('L', 0.010)), (0.558, ('L', 0.002)), (0.533, ('L', 0.0)),
           (0.513, ('L', -0.008)), (0.507, ('L', -0.022)), (0.513, ('L', -0.033)), (0.521, ('L', -0.050)),
           (0.522, 0.92), (0.524, 0.875), (0.527, 0.835), (0.534, 0.810), (0.550, 0.794), (0.578, 0.785),
           (0.62, 0.780), (0.70, 0.778)]
# r3: the driver's lower dash / knee bolster comes down to z ~0.66 (0.40 m ahead of the knees, ~0.11 m over the shins)
# so the footwell and the pedal pads are closed off from the eye; visor over a deep pocket for the digital dash.
# r6: the visor top rises forward into the brow crown (was a near-flat 1.07-1.086 top)
_DASH_D = [(0.80, 0.655), (0.80, 'C1'), (0.776, 'C'), (0.764, ('C', 0.004)), (0.752, ('B', -0.019)),
           (0.733, ('B', -0.005)), (0.708, ('B', 0.0)), (0.682, ('B', -0.002)), (0.645, ('B', -0.010)),
           (0.600, ('B', -0.024)), (0.545, ('B', -0.037)), (0.490, 1.087), (0.466, 1.079),
           (0.455, 1.066), (0.457, 1.057), (0.470, 1.054), (0.51, 1.056), (0.545, 1.052), (0.546, 0.92),
           (0.548, 0.84), (0.553, 0.76), (0.562, 0.690), (0.580, 0.662), (0.615, 0.650), (0.70, 0.645)]
assert len(_DASH_N) == len(_DASH_D)
DASH_FACE_K = 17            # first face point (below the lip / visor pocket); points from here down get the end lift
DASH_LIFT_K = 18


BROW_FALL = 0.105           # r4: the visor ends right of the digital dash and drops into the lip by x -0.05
BROW_FALL_X0 = -0.155       # (r3 fell gradually from -0.19 over 0.29 m, leaving a shelf over the centre)


def brow_w(x):
    return smooth01((x - DRV_BROW[0]) / 0.04) * (1 - smooth01((x - BROW_FALL_X0) / BROW_FALL))


def brow_z(x):
    """r6 spec DASH_BROW_Z: crown height of the dash brow - 1.13 in front of each seat (|x| 0.28-0.60), 1.115 over the
    centre (|x| < 0.22) so the hood beak still shows from DRIVER_EYE; eases down ~1 cm toward the door ends."""
    zs, zc = spec.DASH_BROW_Z
    ax = abs(x)
    return zc + (zs - zc) * smooth01((ax - 0.22) / 0.06) - 0.010 * smooth01((ax - 0.60) / 0.07)


def _prof_z(z, x, zc, lip):
    if z == 'C1':
        return zc - 0.022
    if z == 'C':
        return zc
    if isinstance(z, tuple):
        tag, v = z
        if tag == 'C':
            return zc + v
        if tag == 'L':
            return lip + v
        if tag == 'B':
            return brow_z(x) + v
        if tag == 'F':
            return max(RECESS_FLOOR, min(v, lip - 0.014))
    return z


def dash_profile(x):
    zc = interp(COWL_MIN, abs(x)) - 0.016
    wd = brow_w(x)
    drop = interp(PASS_DROP, x)
    lip = LIP_Z + drop
    out = []
    for k, (n, d) in enumerate(zip(_DASH_N, _DASH_D)):
        zn = _prof_z(n[1], x, zc, lip)
        zd = _prof_z(d[1], x, zc, lip)
        if k == DASH_FACE_K:
            zn = min(zn, lip - 0.050)
        out.append((lerp(n[0], d[0], wd), lerp(zn, zd, wd)))
    # round the dash ends in plan: the face swings forward (less toward the front, so the top keeps its order) and the
    # lower edge lifts near the doors
    e = smooth01((abs(x) - 0.585) / (DASH_X - 0.585))
    for k in range(3, len(out)):
        y, z = out[k]
        sw = 0.045 * e * e * min(1.0, max(0.0, (0.74 - y) / 0.2))
        out[k] = (y + sw, z + (0.035 * e if k >= DASH_LIFT_K else 0.0))
    vis = catmull(out[2:], 2)
    return out[:2] + vis


def dash_face_y(x, z):
    """Approximate rear face of the dash at (x, z) (for mounting things on it)."""
    pr = dash_profile(x)
    best = None
    for (y0, z0), (y1, z1) in zip(pr[8:], pr[9:]):
        if min(z0, z1) <= z <= max(z0, z1) and abs(z1 - z0) > 1e-6:
            y = y0 + (y1 - y0) * (z - z0) / (z1 - z0)
            best = y if best is None else min(best, y)
    return best if best is not None else 0.52


def build_dash(S, mt):
    xs = []
    x = -DASH_X
    while x < DASH_X - 1e-6:
        xs.append(x)
        ax = abs(x)
        step = 0.012 if (ax > 0.60 or abs(x - DRV_BROW[0]) < 0.07
                         or BROW_FALL_X0 - 0.03 < x < BROW_FALL_X0 + BROW_FALL + 0.03) else 0.025
        x += step
    xs.append(DASH_X)
    secs = [[(x, y, z) for (y, z) in dash_profile(x)] for x in xs]
    bm, faces, caps = grid_bm(secs, closed_u=True, cap=True)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for f, j, i in faces:
        c = f.calc_center_median()
        wb = brow_w(c.x)
        if f.normal.y < -0.45 and c.z < 1.03 + 0.045 * wb and c.y < 0.62:
            f.material_index = 1
            set_uv(bm, f, decal_A)
        elif c.y > 0.585 - 0.03 * wb and c.z > 0.93 and f.normal.z > -0.3 and f.normal.y < 0.5:
            # r5: the top behind the lip / visor is gloss carbon like the photos (r4: near-black recess #060607 read as a
            # black trench in the game, satin carbon as dead black); only the throat under the hood's rear edge stays dark
            f.material_index = 3 if (c.y > 0.768 and wb < 0.5) else 0     # r6: only under the hood edge
            set_uv(bm, f, metric_uv(CS))
        else:
            f.material_index = 0
            set_uv(bm, f, metric_uv(CS))
    for f in caps:
        f.material_index = 0
        set_uv(bm, f, metric_uv(CS))
    S.append(finish_bm('int_dash', bm, [mt['carbon'], mt['decal'], mt['carbon_satin'], mt['recess']], deg=50))
    # dash end trims (rubber edge where the dash meets the door cards)
    for sx in (-1, 1):
        pr = dash_profile(sx * DASH_X)
        pts = [(sx * (DASH_X - 0.004), y, z) for (y, z) in pr[3:]]
        # r4: no fillet steps (the profile is already dense): 2.5k -> ~0.5k triangles per edge
        S.append(sharpen(tube('int_dash_edge', pts, 0.004, mt['rubber'], sides=6, bend=0.0, steps=1), 55))


# =====================================================================================================
#  SCREENS + CENTRE STACK ITEMS
# =====================================================================================================
STACK_X = -0.02


def stack_face_y(z):
    return 0.46 + 0.172 * (z - 0.62)


STACK_N = V((0.0, -math.cos(math.atan(0.172)), math.sin(math.atan(0.172))))


# r3 screen geometry (shared with the texture painters)
DD_TILT = 18.0                                     # digital dash face tilt (deg, up toward the eye)
DD_C = (-0.33, 0.512, 0.972)                       # glass centre: bottom edge ~9 mm over the column, top under the visor
DD_GW, DD_GH = 0.250, 0.132                        # glass
DD_BW, DD_BH = 0.278, 0.156                        # black bezel / housing
LOW_X, LOW_Z = 0.30, 0.893
LOW_W, LOW_H = 0.235, 0.150
LG_W, LG_H, LG_A0 = 0.170, 0.106, -0.009           # DuneNav glass size / x offset (keys strip on the right)
LBTN_A, LBTN_B0, LBTN_DB, LBTN_N = 0.0965, 0.0525, 0.0175, 7


def knee_grille(S, mt, name, x0, x1, z0, z1):
    """Hex mesh over a black void in a thin carbon frame, on the plane through the dash face at z0 / z1."""
    xc = (x0 + x1) / 2
    pa = V((xc, dash_face_y(xc, z1), z1))
    pb = V((xc, dash_face_y(xc, z0), z0))
    up = (pa - pb).normalized()
    n = V((1, 0, 0)).cross(up).normalized()          # points out of the face, toward the cabin (-y)
    if n.y > 0:
        n = -n
    w, h = x1 - x0, (pa - pb).length
    c = (pa + pb) / 2
    fr = (c, up.cross(n).normalized(), up)          # quad() faces ux x uy = +n
    S.append(quad(name + '_void', (c + n * 0.0015, fr[1], fr[2]), w, h, mt['hole']))
    S.append(quad(name, (c + n * 0.004, fr[1], fr[2]), w, h, mt['mesh_dark'],
                  uv=[(0, 0), (w / 0.12, 0), (w / 0.12, h / 0.12), (0, h / 0.12)]))
    ring = rrect(w + 0.018, h + 0.018, 0.008)
    inner = rrect(w - 0.002, h - 0.002, 0.004)
    bm = bmesh.new()
    org, ux, uy = c + n * 0.0065, fr[1], fr[2]
    vo = [bm.verts.new(org + ux * a + uy * b) for (a, b) in catmull(ring, 1, closed=True)]
    vi = [bm.verts.new(org + ux * a + uy * b - n * 0.001) for (a, b) in catmull(inner, 1, closed=True)]
    vb = [bm.verts.new(org + ux * a + uy * b - n * 0.0055) for (a, b) in catmull(ring, 1, closed=True)]
    m = len(vo)
    lay = bm.loops.layers.uv.verify()
    for i in range(m):
        i2 = (i + 1) % m
        for q in ((vo[i], vo[i2], vi[i2], vi[i]), (vb[i], vb[i2], vo[i2], vo[i])):
            f = bm.faces.new(q)
            for lp in f.loops:
                lp[lay].uv = metric_uv(CS)(lp.vert.co, n)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for f in bm.faces:
        f.normal_update()
        if f.normal.dot(n) < -0.5:
            f.normal_flip()
    S.append(finish_bm(name + '_frame', bm, [mt['carbon']], deg=40))


def build_screens(S, mt):
    # ---- left: digital race dash under the visor. r3: larger (0.25 x 0.136 glass) in a black bezel, tilted up
    # toward the eye; centred a little right of the column like the photo, bottom edge clear above the column
    p = math.radians(DD_TILT)
    n = V((0, -math.cos(p), math.sin(p)))
    fr = face_frame(DD_C, n)
    S.append(slab('int_dash_screen_housing', rrect(DD_BW, DD_BH, 0.010), fr, 0.040, [mt['gloss'], mt['anod']],
                  bevel=0.004, segs=2))
    S.append(quad('int_dash_screen', fr, DD_GW, DD_GH, mt['scr_dash'], c=0.0007, b0=0.001))
    # small badge strips under the glass (maker logo left, model right)
    S.append(quad('int_dash_screen_badge', fr, 0.030, 0.0055, mt['alu'], c=0.0007, a0=0.105, b0=-0.0735))
    S.append(quad('int_dash_screen_badge', fr, 0.018, 0.0055, mt['alu'], c=0.0007, a0=-0.110, b0=-0.0735))

    # hex-mesh grilles in the dash lower face (interior_dash.png): one under the column, one on the door side of it
    knee_grille(S, mt, 'int_knee_grille', -0.44, -0.22, 0.752, 0.808)
    knee_grille(S, mt, 'int_knee_grille_door', -0.62, -0.47, 0.765, 0.900)

    # ---- right: DuneNav on the passenger side of the dash face, turned a little toward the driver.
    # r3: an Pro 9 7 (0.235 x 0.150, 7 keys on the right strip) - the photo unit is ~0.20-0.24 m wide, not 0.285
    c = V((LOW_X, 0.0, LOW_Z))
    c.y = dash_face_y(LOW_X, LOW_Z) - 0.034
    n0 = (EYE - c).normalized()
    n = (V((0, -1, 0.22)).normalized() * 0.65 + n0 * 0.35).normalized()
    fr = face_frame(c, n)
    S.append(slab('int_lowrance', rrect(LOW_W, LOW_H, 0.012), fr, 0.050, [mt['low_bezel'], mt['gloss']], bevel=0.005,
                  segs=3, uv_front=bbox_uv(LOW_W, LOW_H)))
    S.append(quad('int_lowrance_glass', fr, LG_W, LG_H, mt['scr_low'], c=0.0008, a0=LG_A0))
    org, ux, uy = fr
    nz = ux.cross(uy)
    for k in range(LBTN_N):
        b = org + ux * LBTN_A + uy * (LBTN_B0 - k * LBTN_DB)
        S.append(cyl_at('int_lowrance_btn', 0.0050, 0.0032, b, nz, mt['rubber'], segs=12))
    # bracket into the dash face
    S.append(slab('int_lowrance_mount', rrect(0.10, 0.07, 0.01), (org - nz * 0.050, ux, uy), 0.04, [mt['anod'], mt['anod']]))

    # dzus fasteners on the dash face
    for (fx, fz) in ((-0.08, 0.950), (0.10, 0.950), (0.60, 0.92), (-0.60, 0.80), (0.55, 0.815), (0.13, 0.825)):
        fy = dash_face_y(fx, fz)
        S.append(lathe_at('int_dash_dzus', [(0.0, 0.0), (0.0065, 0.0), (0.006, 0.0018), (0.0035, 0.0028), (0.0, 0.003)],
                          (fx, fy + 0.0005, fz), (0, -1, 0.05), mt['anod'], segs=12))

    # ---- centre stack items (x = STACK_X)
    sx = STACK_X
    # race radio under the dash lip
    zr = 0.953
    fr = face_frame((sx, dash_face_y(sx, zr) - 0.012, zr), (0, -1, 0.05))
    S.append(slab('int_radio', rrect(0.150, 0.047, 0.004), fr, 0.10, [mt['radio'], mt['black']], bevel=0.003, segs=1,
                  uv_front=bbox_uv(0.150, 0.047)))
    S.append(cyl_at('int_radio_knob', 0.0085, 0.012, fr[0] + fr[1] * -0.084 + fr[2] * 0.004, fr[1].cross(fr[2]),
                    mt['rubber'], segs=14))
    # switch panel
    # r4: landscape 4 x 3 panel (photo W/H ~1.33: 0.134 x 0.104, was square), bottom kept at ~0.80, so the short
    # orange blade shows between it and the radio like in the photo
    zs = 0.852
    fr = face_frame((sx, stack_face_y(zs) - 0.017, zs), STACK_N)
    S.append(slab('int_switch_bezel', rrect(0.134, 0.104, 0.008), fr, 0.03, [mt['anod'], mt['anod']], bevel=0.004))
    S.append(quad('int_switch_keys', fr, 0.120, 0.090, mt['switches'], c=0.0007))
    org, ux, uy = fr
    nz = ux.cross(uy)
    for a, b in ((-0.058, -0.043), (0.058, -0.043), (-0.058, 0.043), (0.058, 0.043)):
        S.append(cyl_at('int_switch_screw', 0.0028, 0.0015, org + ux * a + uy * b, nz, mt['chrome'], segs=8))
    # red push buttons on the dash face either side of the switch panel
    for bx in (sx - 0.098, sx + 0.098):
        zb = 0.815
        yb = dash_face_y(bx, zb)
        base = V((bx, yb, zb))
        d = V((0, -1, 0.12)).normalized()
        S.append(lathe_at('int_red_btn_bezel', [(0.0, 0.0), (0.0135, 0.0), (0.0135, 0.004), (0.0115, 0.0065),
                                                (0.0, 0.0065)], base - d * 0.001, d, mt['chrome'], segs=20))
        S.append(lathe_at('int_red_btn', [(0.0, 0.0), (0.0098, 0.0), (0.0098, 0.007), (0.0075, 0.0105),
                                          (0.004, 0.0118), (0.0, 0.012)], base + d * 0.004, d, mt['red'], segs=20))
    # DCX intercom plate
    zp = 0.776
    fr = face_frame((sx, stack_face_y(zp) - 0.003, zp), STACK_N)
    S.append(slab('int_pci', rrect(0.112, 0.056, 0.003), fr, 0.006, [mt['pci'], mt['alu']], bevel=0.0012, segs=1,
                  uv_front=bbox_uv(0.112, 0.056)))
    org, ux, uy = fr
    nz = ux.cross(uy)
    for a in (-0.0255, 0.0255):
        b = org + ux * a + uy * 0.0045
        S.append(lathe_at('int_pci_knob', [(0.0, 0.0), (0.0095, 0.0), (0.0095, 0.009), (0.008, 0.0125), (0.0, 0.0125)],
                          b, nz, mt['rubber'], segs=16))
        S.append(cyl_at('int_pci_knob_cap', 0.0045, 0.0128, b, nz, mt['alu'], segs=12))
    S.append(slab('int_pci_ptt_cap', rrect(0.011, 0.012, 0.002), (org + uy * 0.006 + nz * 0.007, ux, uy), 0.007,
                  [mt['blue'], mt['blue']], bevel=0.002, segs=1))
    # stereo pod
    zt = 0.690
    fr = face_frame((sx, stack_face_y(zt) - 0.036, zt), STACK_N)
    org, ux, uy = fr
    nz = ux.cross(uy)
    S.append(slab('int_stereo_pod', rrect(0.126, 0.098, 0.012), (org - nz * 0.001, ux, uy), 0.05,
                  [mt['carbon'], mt['carbon']], bevel=0.008, segs=2))
    S.append(slab('int_stereo', rrect(0.108, 0.081, 0.006), (org + nz * 0.006, ux, uy), 0.008,
                  [mt['stereo'], mt['black']], bevel=0.002, segs=1, uv_front=bbox_uv(0.108, 0.081)))
    S.append(quad('int_stereo_screen', (org + nz * 0.0068, ux, uy), 0.072, 0.034, mt['scr_radio'], b0=0.019))
    kb = org + nz * 0.006 + uy * -0.020
    S.append(lathe_at('int_stereo_knob', [(0.0, 0.0), (0.0125, 0.0), (0.0125, 0.010), (0.011, 0.014), (0.0, 0.014)],
                      kb, nz, mt['rubber'], segs=20))
    S.append(cyl_at('int_stereo_knob_ring', 0.0128, 0.003, kb + nz * 0.0085, nz, mt['chrome'], segs=20))


def build_stack(S, mt):
    """Carbon centre stack: horizontal sections from the console up into the dash face."""
    # r3: start at the (raised) floor and drop any level below it (FZ 0.45 folded the old loft)
    # r4: the stack now stops at 0.974, under the dash lip / satin-black recess floor (>= 0.979); its old top cap
    # (1.005, reaching back to y 0.78) stood up through the new recess as a grey gloss shelf in the game
    zs = [FZ + 0.001] + [z for z in (0.47, 0.52, 0.56, 0.60, 0.64, 0.68, 0.72, 0.76, 0.80, 0.84, 0.88, 0.91, 0.935,
                                     0.955, 0.974) if z > FZ + 0.012]
    secs = []
    for z in zs:
        # r3: a narrow column (photo: just wider than the stereo) that widens into the dash face at the top and
        # flares a little into the console at the bottom
        hw = (0.068 + 0.130 * smooth01((z - 0.90) / 0.10) ** 1.6 + 0.040 * smooth01((0.64 - z) / 0.18) ** 1.3)
        yf = stack_face_y(z) + 0.004 * smooth01((z - 0.90) / 0.10) - 0.03 * smooth01((0.62 - z) / 0.20)
        rr = min(0.024, hw * 0.3)
        y1 = 0.78
        pts = []
        # rear (face) corners rounded, front corners square-ish (hidden inside the dash)
        for k in range(5):
            a = math.radians(180 + 90 * k / 4)
            pts.append((STACK_X - hw + rr + rr * math.cos(a), yf + rr + rr * math.sin(a)))
        for k in range(5):
            a = math.radians(270 + 90 * k / 4)
            pts.append((STACK_X + hw - rr + rr * math.cos(a), yf + rr + rr * math.sin(a)))
        pts += [(STACK_X + hw, y1), (STACK_X - hw, y1)]
        secs.append([(x, y, z) for (x, y) in pts])
    bm, faces, caps = grid_bm(secs, closed_u=True, cap=True)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for f, j, i in faces + [(c, 0, 0) for c in caps]:
        n = f.normal
        if n.y < -0.5:
            f.material_index = 1
            set_uv(bm, f, decal_A)
        else:                                  # r6: the sides are plain interior carbon (swoosh = geometry inlay)
            f.material_index = 0
            set_uv(bm, f, metric_uv(CS))
    S.append(finish_bm('int_stack', bm, [mt['carbon'], mt['decal']], deg=45))


# =====================================================================================================
#  CONSOLE TUNNEL
# =====================================================================================================

def console_dims(y):
    w = smooth01((y - 0.10) / 0.12)
    w2 = smooth01((y - 0.30) / 0.15)
    hb = lerp(0.094, 0.110, w) + 0.010 * w2          # r3: narrower tunnel (photo)
    ht = lerp(0.078, 0.092, w) + 0.006 * w2
    # r3: floor 7 cm higher -> the tunnel top rises with it at the rear (>= FZ + 0.105 so the side wall + top
    # radius never fold), about the same absolute height further forward (the shifter / stack stay put)
    zt = interp([(-0.40, FZ + 0.105), (-0.34, min(FZ + 0.135, 0.592)), (-0.22, 0.597), (0.0, 0.600), (0.30, 0.605),
                 (0.45, 0.615), (0.62, 0.635)], y)
    return hb, ht, zt


def build_console(S, mt):
    ys = [-0.405, -0.39, -0.36, -0.32, -0.26, -0.18, -0.10, -0.02, 0.06, 0.10, 0.14, 0.18, 0.22, 0.30, 0.38,
          0.46, 0.54, 0.62]
    secs = []
    for y in ys:
        hb, ht, zt = console_dims(y)
        e = smooth01((-0.36 - y) / 0.05)          # round the rear end
        hb2, ht2 = hb - 0.02 * e, ht - 0.02 * e
        r = 0.032
        z0 = FZ + 0.001
        pts = [(0.0, z0), (hb2, z0), (hb2 - 0.002, z0 + 0.06)]
        for k in range(6):
            a = math.radians(90 * k / 5)
            pts.append((ht2 - r + r * math.cos(a), zt - r + r * math.sin(a)))
        pts.append((0.0, zt + 0.002))
        left = [(-x, z) for (x, z) in pts[1:-1][::-1]]
        loop = pts + left
        secs.append([(x, y, z) for (x, z) in loop])
    bm, faces, caps = grid_bm(secs, closed_u=True, cap=True)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for f, j, i in faces + [(c, 0, 0) for c in caps]:
        n = f.normal
        f.material_index = 0                   # r6: plain interior carbon (the lightning flash is a geometry inlay)
        set_uv(bm, f, metric_uv(CS))
    S.append(finish_bm('int_console', bm, [mt['carbon']], deg=40))
    build_inlays(S, mt)


def console_side_x(y, z):
    """|x| of the console tunnel's side surface at (y, z) (its profile: wall, slight lean-in, top radius)."""
    hb, ht, zt = console_dims(y)
    e = smooth01((-0.36 - y) / 0.05)
    hb2, ht2 = hb - 0.02 * e, ht - 0.02 * e
    r = 0.032
    pts = [(hb2, FZ + 0.001), (hb2 - 0.002, FZ + 0.061)]
    for k in range(6):
        a = math.radians(90 * k / 5)
        pts.append((ht2 - r + r * math.cos(a), zt - r + r * math.sin(a)))
    for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
        if z0 <= z <= z1 and z1 > z0:
            return x0 + (x1 - x0) * (z - z0) / (z1 - z0)
    return pts[-1][0]


def stack_side_x(y, z):
    """x of the centre stack's passenger-side (+x) surface at (y, z) (straight side, rounded rear corner)."""
    hw = (0.068 + 0.130 * smooth01((z - 0.90) / 0.10) ** 1.6 + 0.040 * smooth01((0.64 - z) / 0.18) ** 1.3)
    yf = stack_face_y(z) + 0.004 * smooth01((z - 0.90) / 0.10) - 0.03 * smooth01((0.62 - z) / 0.20)
    rr = min(0.024, hw * 0.3)
    dy = y - (yf + rr)
    if dy >= 0:
        return STACK_X + hw
    return STACK_X + hw - rr + math.sqrt(max(0.0, rr * rr - dy * dy))


def _inlay(name, poly, surf, mlist, lift, cuts=3, mat_index=0):
    """Thin decal-like inlay: 2D polygon in (y, z), triangulated, subdivided and laid on a side surface x = surf(y, z)
    (+lift along +x), facing +x."""
    bm = bmesh.new()
    vs = [bm.verts.new((0.0, y, z)) for (y, z) in poly]
    f = bm.faces.new(vs)
    bmesh.ops.triangulate(bm, faces=[f], quad_method='BEAUTY', ngon_method='EAR_CLIP')
    if cuts:
        bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=cuts, use_grid_fill=True)
    for v in bm.verts:
        v.co.x = surf(v.co.y, v.co.z) + lift
    for fc in bm.faces:
        fc.normal_update()
        if fc.normal.x < 0:
            fc.normal_flip()
        fc.material_index = mat_index
    return obj_from_bmesh(name, bm, mlist, smooth=False)


def build_inlays(S, mt):
    """r6: the orange graphics on the console / stack sides as thin geometry inlays (were painted in the decal atlas's
    region B at 1000 px/m): the filled lightning flash low on the console's passenger-side front (interior_dash.png),
    pointing rearward, with a torn gloss-black edge along its top, and the small swoosh on the stack's passenger flank."""
    rng = np.random.default_rng(29)
    z0 = FZ + 0.030
    flash = [(0.300, z0 + 0.062), (0.215, z0 + 0.052), (0.236, z0 + 0.040), (0.160, z0 + 0.030), (0.178, z0 + 0.020),
             (0.098, z0 + 0.004), (0.205, z0 + 0.010), (0.190, z0 + 0.021), (0.262, z0 + 0.029), (0.248, z0 + 0.041),
             (0.305, z0 + 0.048)]
    S.append(_inlay('int_console_flash', flash[::-1], console_side_x, [mt['orange']], 0.0008))
    tearl = [(0.300, z0 + 0.062), (0.215, z0 + 0.052), (0.236, z0 + 0.040), (0.160, z0 + 0.030)]
    for k, (a, b) in enumerate(zip(tearl, tearl[1:])):
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        tear = [(a[0], a[1] + 0.003), (m[0], m[1] + 0.0045 + rng.uniform(0, 0.003)), (b[0], b[1] + 0.003),
                (b[0], b[1] - 0.0015), (m[0] + 0.004, m[1] - 0.0005), (a[0], a[1] - 0.0015)]
        if poly_area(tear) < 0:
            tear = tear[::-1]
        S.append(_inlay('int_console_flash_tear', tear, console_side_x, [mt['gloss']], 0.0013, cuts=1))
    sw = _stroke(0.585, 0.49, 0.703, 0.716, 0.011, 0.005, rng, lead=0.02, tip=True)
    sw = [(float(y), float(z)) for (y, z) in sw]
    if poly_area(sw) < 0:
        sw = sw[::-1]
    S.append(_inlay('int_stack_swoosh', sw, stack_side_x, [mt['orange']], 0.0008, cuts=1))


# =====================================================================================================
#  STEERING WHEEL + COLUMN
# =====================================================================================================
SW_C = V(spec.STEERING_WHEEL_CENTRE)
SW_DIR = V(spec.STEERING_COLUMN_DIR).normalized()
SW_R = spec.STEERING_WHEEL_R


def build_rim(mt):
    """Suede rim (local frame: X right, Y = 12 o'clock, Z toward the driver)."""
    na = 144
    ar, az = 0.0140, 0.0152                 # radial / axial half thickness (28 x 30 mm)
    # r6: two continuous 2 mm orange stitch bands 4 mm apart on the inner circumference (phi 146-154 / 161-169; phi 90 =
    # driver face, 180 = inner edge), interrupted where the spoke sleeves flare into the rim (interior_dash.png)
    phis = sorted(set([k * 22.5 for k in range(16)] + [b for band in RIM_STITCH for b in band]))
    secs = []
    for k in range(na):
        th = 2 * math.pi * k / na
        ring = []
        for ph in phis:
            p = math.radians(ph)
            rr = SW_R + ar * math.cos(p)
            # slightly flattened driver face
            zz = az * math.sin(p) * (0.92 if math.sin(p) > 0 else 1.0)
            ring.append((rr * math.cos(th), rr * math.sin(th), zz))
        secs.append(ring)
    secs.append(secs[0])
    bm, faces, _ = grid_bm(secs, closed_u=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    band_i = [phis.index(b[0]) for b in RIM_STITCH]
    lay = bm.loops.layers.uv.verify()
    for f, j, i in faces:
        th = math.degrees(2 * math.pi * (j + 0.5) / na)
        near_spoke = min(abs((th - sa + 180.0) % 360.0 - 180.0) for sa in SPOKE_ANGLES) < 11.0
        if abs(th - 90.0) < 5.1:
            f.material_index = 1          # orange 12 o'clock stripe
        elif i in band_i and not near_spoke:
            f.material_index = 2          # orange stitch bands
        else:
            f.material_index = 0
        for lp in f.loops:
            co = lp.vert.co
            lp[lay].uv = (math.atan2(co.y, co.x) / (2 * math.pi) * 1.1 * 5, co.z * 5 + math.hypot(co.x, co.y) * 5)
    return finish_bm('sw_rim', bm, [mt['suede'], mt['marker'], mt['stitch']], deg=60)


HUB_DZ = -0.045               # r5: dished wheel - the hub plane sits 45 mm toward the dash from the rim centre plane
SPOKE_T = 0.0045
# r6 (interior_dash.png): one flat satin-black plate - a flat hub disc (R HUB_PLATE_R) with concave fillets into three wide
# plain arms (no slots) that slope up from SPOKE_R0 to the rim's back; suede sleeves cover the arms from SLEEVE_R0 to the
# rim. Arm widths (full, mm): 3 / 9 o'clock 40 at the hub -> 46 at r 0.105, 6 o'clock 56 -> 48.
SPOKE_R0, SPOKE_R1 = 0.060, 0.170          # flat hub plate out to R0, then the arms slope to the rim's back at R1
SPOKE_ANGLES = (0.0, 180.0, 270.0)         # 3, 9, 6 o'clock (local wheel frame, +Y = 12 o'clock)
HUB_PLATE_R, HUB_FILLET_R, HUB_CUT_R = 0.050, 0.010, 0.064
SLEEVE_R0, SLEEVE_R_END = 0.105, 0.174
SLEEVE_HT, SLEEVE_HW_MID = 0.012, 0.018    # sleeve half thickness / half width (36 x 24 mm rounded rectangle)
RIM_STITCH = ((146.0, 154.0), (161.0, 169.0))


def spoke_ztop(r):
    """Top (driver-side) face height of the plate at radius r (local wheel frame): flat hub, then the sloped arms."""
    z0, z1 = HUB_DZ - 0.0055, -0.010
    return z0 + (z1 - z0) * max(0.0, r - SPOKE_R0) / (SPOKE_R1 - SPOKE_R0)


def spoke_hw(ang, r):
    """Half width of the bare arm at radius r (the 3 / 9 o'clock arms widen outward, the 6 o'clock one narrows)."""
    t = min(1.0, max(0.0, (r - 0.050) / (SLEEVE_R0 - 0.050)))
    return lerp(0.028, 0.024, t) if abs(ang - 270.0) < 1 else lerp(0.020, 0.023, t)


def sleeve_hw(ang, r):
    """Half width of the suede sleeve: starts 1 mm wider than the bare arm, slims to 36 mm, flares into the rim."""
    w0 = spoke_hw(ang, SLEEVE_R0) + 0.001
    w = lerp(w0, SLEEVE_HW_MID, smooth01((r - SLEEVE_R0) / 0.035))
    return w + (0.028 - SLEEVE_HW_MID) * smooth01((r - (SLEEVE_R_END - 0.019)) / 0.015) ** 1.5


def plate_hw(ang, r):
    """Half width of the plate itself (narrows inside the sleeve so it never pokes out of the suede)."""
    if r <= SLEEVE_R0:
        return spoke_hw(ang, r)
    return max(0.010, min(spoke_hw(ang, SLEEVE_R0), sleeve_hw(ang, r) - 0.004 - 0.15 * (r - SLEEVE_R0)))


def plate_with_hole(name, outer, holes, frame, thick, mlist, ch=0.0009):
    """Flat plate in frame (origin, ux, uy) (front face at c = 0, normal ux x uy), back at -thick, outline `outer`
    (2D CCW) with see-through `holes` (2D loops); 0.9 mm chamfer round every top edge. Material 0 everywhere."""
    org, ux, uy = V(frame[0]), V(frame[1]).normalized(), V(frame[2]).normalized()
    nz = ux.cross(uy).normalized()
    Wp = lambda a, b, c: org + ux * a + uy * b + nz * c
    loops = [outer] + holes
    bm = bmesh.new()
    rings = []
    for li, lp in enumerate(loops):
        lp = lp if (poly_area(lp) > 0) == (li == 0) else lp[::-1]
        inset = offset2d(lp, ch)
        rings.append(([bm.verts.new(Wp(a, b, -thick)) for (a, b) in lp], [bm.verts.new(Wp(a, b, -ch)) for (a, b) in lp],
                      [bm.verts.new(Wp(a, b, 0.0)) for (a, b) in inset]))
    for (vb, vm, vt) in rings:
        n = len(vb)
        for i in range(n):
            i2 = (i + 1) % n
            for (p, q) in ((vb, vm), (vm, vt)):
                try:
                    bm.faces.new((p[i], p[i2], q[i2], q[i]))
                except ValueError:
                    pass
    for layer in (2, 0):
        edges = []
        for rg in rings:
            vs = rg[layer]
            for i in range(len(vs)):
                e = bm.edges.get((vs[i], vs[(i + 1) % len(vs)])) or bm.edges.new((vs[i], vs[(i + 1) % len(vs)]))
                edges.append(e)
        bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges, normal=nz if layer == 2 else -nz)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    lay = bm.loops.layers.uv.verify()
    for f in bm.faces:
        f.material_index = 0
        for l in f.loops:
            d = l.vert.co - org
            l[lay].uv = (d.dot(ux) * 8, d.dot(uy) * 8)
    return finish_bm(name, bm, mlist, deg=40)


def hub_outline(n_disc=10, n_fil=5):
    """2D outline (CCW) of the flat hub plate: disc R HUB_PLATE_R united with the three arm roots (cut at HUB_CUT_R),
    concave R HUB_FILLET_R fillets where the arm sides meet the disc."""
    R, Rf = HUB_PLATE_R, HUB_FILLET_R
    info = []
    for ang in sorted(SPOKE_ANGLES):
        pc = spoke_hw(ang, 0.055) + Rf
        info.append((ang, pc, math.sqrt((R + Rf) ** 2 - pc * pc)))
    out = []
    for k, (ang, pc, sc) in enumerate(info):
        a = math.radians(ang)
        d, pn = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
        L = lambda s, p: (d[0] * s + pn[0] * p, d[1] * s + pn[1] * p)
        a1 = math.atan2(pc, -sc)                         # -p fillet: disc tangent -> line tangent (CW)
        for t in np.linspace(0, 1, n_fil + 1):
            aa = a1 + (math.pi / 2 - a1) * t
            out.append(L(sc + Rf * math.cos(aa), -pc + Rf * math.sin(aa)))
        out.append(L(HUB_CUT_R, -spoke_hw(ang, HUB_CUT_R)))
        out.append(L(HUB_CUT_R, spoke_hw(ang, HUB_CUT_R)))
        a2 = math.atan2(-pc, -sc)                        # +p fillet: line tangent -> disc tangent (CW)
        for t in np.linspace(0, 1, n_fil + 1):
            aa = -math.pi / 2 + (a2 + math.pi / 2) * t
            out.append(L(sc + Rf * math.cos(aa), pc + Rf * math.sin(aa)))
        ang2, pc2, sc2 = info[(k + 1) % len(info)]
        t0 = ang + math.degrees(math.atan2(pc, sc))
        t1 = ang2 - math.degrees(math.atan2(pc2, sc2))
        if t1 <= t0:
            t1 += 360.0
        m = max(2, int((t1 - t0) / 360.0 * 4 * n_disc))
        for t in np.linspace(t0, t1, m + 1)[1:-1]:
            out.append((R * math.cos(math.radians(t)), R * math.sin(math.radians(t))))
    return out


def build_spokes(mt):
    """r6: plain satin-black spoke plate (interior_dash.png): flat hub plate with filleted arm roots + three sloped arms
    (no slots), suede sleeves over the outer arms, flaring into the rim's back. (r5: 34 -> 30 mm slotted bars.)"""
    out = []
    zh = spoke_ztop(0.0)
    out.append(plate_with_hole('sw_hub_plate', hub_outline(), [], (V((0, 0, zh)), V((1, 0, 0)), V((0, 1, 0))),
                               SPOKE_T, [mt['spoke']]))
    dr = SPOKE_R1 - SPOKE_R0
    dz = spoke_ztop(SPOKE_R1) - spoke_ztop(SPOKE_R0)
    L = math.hypot(dr, dz)
    cb = dr / L
    for ang in SPOKE_ANGLES:
        a = math.radians(ang)
        d = V((math.cos(a), math.sin(a), 0))
        pn = V((-math.sin(a), math.cos(a), 0))
        e = (d * dr + V((0, 0, dz))).normalized()
        org = d * SPOKE_R0 + V((0, 0, zh))
        s_back, s_tip = -0.006, (0.172 - SPOKE_R0) / cb
        ss = sorted(set([float(x) for x in np.linspace(s_back, s_tip - 0.006, 9)] +
                        [(SLEEVE_R0 - SPOKE_R0) / cb + k * 0.004 for k in range(-1, 4)]))
        hw = lambda s: plate_hw(ang, SPOKE_R0 + max(s, 0.0) * cb)
        side = [(s, -hw(s)) for s in ss]
        tip = [(s_tip - 0.006 + 0.006 * math.sin(t), hw(s_tip) * -math.cos(t)) for t in np.linspace(0, math.pi, 5)[1:-1]]
        outer = side + tip + [(s, hw(s)) for s in ss[::-1]]
        out.append(plate_with_hole('sw_spoke', outer, [], (org, e, pn), SPOKE_T, [mt['spoke']]))
        out.append(build_sleeve(mt, ang))
    return out


def build_sleeve(mt, ang):
    """Suede sleeve over one arm: rounded-rectangle sections (in the plane of the tangential and the wheel axis) at radial
    stations from SLEEVE_R0 (rounded start cuff) to SLEEVE_R_END inside the rim; its centre plane follows the plate's
    mid-thickness, then sweeps into the rim's centre plane over the last ~19 mm while it widens (the flare)."""
    a = math.radians(ang)
    d = V((math.cos(a), math.sin(a), 0))
    pn = V((-math.sin(a), math.cos(a), 0))
    r0, r1 = SLEEVE_R0, SLEEVE_R_END
    cuff = 0.007
    rs = [r0 + cuff * (1 - math.cos(0.5 * math.pi * k / 4)) for k in range(5)] + \
         [float(x) for x in np.linspace(r0 + cuff + 0.006, r1 - 0.020, 4)] + \
         [float(x) for x in np.linspace(r1 - 0.016, r1, 6)]
    secs = []
    for r in rs:
        f = math.sin(0.5 * math.pi * min(1.0, (r - r0) / cuff)) if r < r0 + cuff else 1.0
        f = 0.35 + 0.65 * f
        hw = sleeve_hw(ang, r) * (0.55 + 0.45 * f)
        zc_plate = spoke_ztop(r) - SPOKE_T / 2
        b = smooth01((r - (r1 - 0.019)) / 0.019)
        zc = lerp(zc_plate, -0.001, b)
        ht = lerp(SLEEVE_HT, 0.0125, b) * f
        rc = min(0.009, 0.85 * min(hw, ht))
        ring = rrect(2 * hw, 2 * ht, rc, n=3)
        secs.append([tuple(d * r + pn * u + V((0, 0, zc + w))) for (u, w) in ring])
    bm, faces, caps = grid_bm(secs, closed_u=True, cap=True)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    lay = bm.loops.layers.uv.verify()
    for f in bm.faces:
        f.material_index = 0
        for lp in f.loops:
            co = lp.vert.co
            lp[lay].uv = (co.dot(pn) * 5 + co.z * 5, co.dot(d) * 5)
    return finish_bm('sw_sleeve', bm, [mt['suede']], deg=60)


def build_steering(S, mt):
    mw = aligned_matrix(SW_C, SW_DIR)
    W = []
    W.append(build_rim(mt))
    W += build_spokes(mt)
    H = HUB_DZ
    # hub boss + horn button: satin black, crown <= 3 mm, flat centre with the DRV logo (r5: dished 45 mm toward the dash)
    W.append(lathe('sw_boss', [(0.0, H - 0.034), (0.033, H - 0.034), (0.035, H - 0.031), (0.035, H - 0.0105),
                               (0.0, H - 0.0105)], mt['anod'], segments=32))
    W.append(lathe('sw_horn', [(0.0, H - 0.0055), (0.0335, H - 0.0055), (0.0335, H + 0.0010), (0.0318, H + 0.0026),
                               (0.028, H + 0.0036), (0.0225, H + 0.0040), (0.0, H + 0.0040)], mt['horn'], segments=40))
    logo = cylinder('sw_horn_logo', 0.0222, 0.0004, (0, 0, H + 0.0042), material=mt['mpi'], segments=40)
    apply_transform(logo)
    uv_project(logo, lambda co, n: (0.5 + co.x / 0.06, 0.5 + co.y / 0.06))
    W.append(logo)
    W.append(lathe('sw_horn_ring', [(0.0295, H - 0.002), (0.0345, H - 0.002), (0.0345, H + 0.0018), (0.0295, H + 0.0018)],
                   mt['horn'], segments=40))
    # r6: small WHITE badge on the bare 6 o'clock arm below the hub (interior_dash.png), lying on its sloped face
    rb = 0.083
    e6 = V((0, -(SPOKE_R1 - SPOKE_R0), spoke_ztop(SPOKE_R1) - spoke_ztop(SPOKE_R0))).normalized()
    W.append(quad('sw_spoke_badge', (V((0, -rb, spoke_ztop(rb) + 0.0004)), V((1, 0, 0)), -e6), 0.024, 0.012,
                  mt['badge']))
    for k in range(6):
        a = math.radians(30 + 60 * k)
        W.append(lathe('sw_bolt', [(0.0, 0.0), (0.0034, 0.0), (0.0030, 0.0018), (0.0, 0.0024)], mt['polished'],
                       segments=10, loc=(0.0405 * math.cos(a), 0.0405 * math.sin(a), H - 0.0056)))
    for o in W:
        sharpen(o, 40)
    xform(W, mw)

    # ---- static: quick-release hub, column, collar at the dash, support to the dash bar
    st = []
    H = HUB_DZ
    st.append(lathe('sw_qr', [(0.0, H - 0.034), (0.029, H - 0.034), (0.029, H - 0.046), (0.0265, H - 0.048),
                              (0.0265, H - 0.068), (0.029, H - 0.070), (0.029, H - 0.078), (0.020, H - 0.084),
                              (0.0, H - 0.084)], mt['anod'], segments=32))
    st.append(lathe('sw_qr_ring', [(0.0266, H - 0.050), (0.0285, H - 0.050), (0.0285, H - 0.064), (0.0266, H - 0.064)],
                    mt['polished'], segments=32))
    st.append(lathe('sw_column', [(0.0, H - 0.083), (0.0159, H - 0.083), (0.0159, -0.40), (0.0, -0.40)], mt['polished'],
                    segments=24))
    # where the column meets the dash face
    tcol = (dash_face_y(SW_C.x, 0.85) - SW_C.y) / (-SW_DIR.y)
    st.append(lathe('sw_collar', [(0.0162, -tcol + 0.004), (0.030, -tcol + 0.004), (0.033, -tcol + 0.0), (0.036, -tcol - 0.006),
                                  (0.016, -tcol - 0.006)], mt['anod'], segments=28))
    st.append(lathe('sw_column_clamp', [(0.0162, -tcol + 0.040), (0.0215, -tcol + 0.040), (0.0215, -tcol + 0.020),
                                        (0.0162, -tcol + 0.020)], mt['anod'], segments=20))
    for o in st:
        sharpen(o, 40)
    xform(st, mw)
    tsup = tcol + 0.07
    p0 = SW_C - SW_DIR * tsup
    st.append(ttube('sw_column_support', [tuple(p0), (p0.x, p0.y + 0.06, p0.z + 0.04), (p0.x, 0.756, 0.95)], 0.012,
                    mt['anod'], sides=12))
    S.extend(st)
    return W


# =====================================================================================================
#  SEATS + HARNESSES
# =====================================================================================================
SEAT_PATH_CTRL = [(0.112, 0.586), (0.06, 0.584), (0.0, 0.577), (-0.15, 0.556), (-0.30, 0.539), (-0.385, 0.533),
                  (-0.425, 0.552), (-0.441, 0.61), (-0.452, 0.72), (-0.464, 0.86), (-0.474, 1.00), (-0.480, 1.12),
                  (-0.479, 1.205), (-0.477, 1.245)]
SLOT_Z = 1.108
SLOT_U = 0.097


# r6: see-through harness pass-throughs (seat_closeup.png): rounded trapezoids, inner side vertical, outer side leaning
# out toward the bottom, top at SLOT_Z + 0.03; the shoulder strap comes through their lower part and drapes over the
# bottom of the 12 mm gloss-black loop
SLOT_W_TOP, SLOT_W_BOT, SLOT_H, SLOT_R = 0.060, 0.095, 0.075, 0.013
SLOT_IN = 0.033             # |u| of the strap centre minus the opening's inner edge
SLOT_LOOP_R = 0.006


def slot_frame(xc, su, path=None):
    """(q, n, t, ux, outline) of one pass-through: q on the seat surface at the opening's inner-edge station, outline
    in (a = world +x, b = along t) metres relative to q (CCW)."""
    sg = 1.0 if su > 0 else -1.0
    u_in = abs(su) - SLOT_IN                                 # opening's inner edge |u|
    uc = u_in + SLOT_W_BOT / 2
    q, n, t = seat_surface(xc, sg * uc, z=SLOT_Z, path=path)
    ux = V((1, 0, 0))
    bt = (SLOT_Z + 0.030 - q.z) / max(0.5, t.z)
    bb = bt - SLOT_H
    a_in = -SLOT_W_BOT / 2
    quad_ = [(a_in, bb), (a_in + SLOT_W_BOT, bb), (a_in + SLOT_W_TOP, bt), (a_in, bt)]
    if sg < 0:
        quad_ = [(-a, b) for (a, b) in quad_][::-1]
    return q, n, t, ux, round_outline(quad_, SLOT_R, n=4)


def cut_passthroughs(seat, mt, xc, path):
    """Boolean the two pass-throughs through the seat back (prisms along the back's normal); the cut walls take the
    gloss-black material."""
    bm = bmesh.new()
    for su in (-SLOT_U, SLOT_U):
        q, n, t, ux, outline = slot_frame(xc, su, path)
        lo = [bm.verts.new(q + ux * a + t * b - n * 0.16) for (a, b) in outline]
        hi = [bm.verts.new(q + ux * a + t * b + n * 0.05) for (a, b) in outline]
        m = len(outline)
        for i in range(m):
            bm.faces.new((lo[i], lo[(i + 1) % m], hi[(i + 1) % m], hi[i]))
        bm.faces.new(hi)
        bm.faces.new(lo[::-1])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    cutter = obj_from_bmesh('int_seat_cutter', bm, [mt['gloss']], smooth=False)
    mod = seat.modifiers.new('passthrough', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = cutter
    try:
        mod.solver = 'EXACT'
    except Exception:
        pass
    try:
        mod.material_mode = 'TRANSFER'
    except Exception:
        pass
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(seat.evaluated_get(dg))
    seat.modifiers.clear()
    old = seat.data
    seat.data = me
    me.name = old.name
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cutter)
    sharpen(seat, 55)


SEAM_Y = -0.045             # transverse tuck across the cushion centre panel


def seat_path(n=58):
    dense = catmull(SEAT_PATH_CTRL, 8)
    P = [V((0, p[0], p[1])) for p in dense]
    acc = [0.0]
    for i in range(1, len(P)):
        acc.append(acc[-1] + (P[i] - P[i - 1]).length)
    L = acc[-1]
    # arc length of the cushion seam (path runs front -> back along -y there)
    s_seam = next(acc[i] for i in range(len(P)) if P[i].y <= SEAM_Y)
    samples = sorted(set([float(x) for x in np.linspace(0, L, n)] + [s_seam - 0.006, s_seam, s_seam + 0.006]))
    samples = [x for i, x in enumerate(samples) if i == 0 or x - samples[i - 1] > 0.003]
    out = []
    k = 0
    for s in samples:
        while k < len(acc) - 2 and acc[k + 1] < s:
            k += 1
        t = (s - acc[k]) / max(1e-9, acc[k + 1] - acc[k])
        out.append(P[k].lerp(P[k + 1], t))
    res = []
    m = len(out)
    for i, p in enumerate(out):
        t = (out[min(i + 1, m - 1)] - out[max(i - 1, 0)]).normalized()
        nrm = V((0, t.z, -t.y))
        res.append((p, t, nrm))
    return res


def seat_params(p):
    """(hw, cw, bh, th) at a path point (y, z)."""
    z = p.z
    wb = smooth01((z - 0.565) / 0.07)                       # 0 on the cushion, 1 up the back
    # cushion
    fc = smooth01((p.y - 0.02) / 0.09)                       # bolsters fade into the front roll
    c_hw, c_cw, c_bh, c_th = 0.248, 0.112, lerp(0.068, 0.040, fc), 0.078
    # back
    b_hw = interp([(0.56, 0.252), (0.95, 0.250), (1.10, 0.222), (1.20, 0.200), (1.26, 0.186)], z)
    up = smooth01((z - 1.075) / 0.05)
    b_cw = lerp(0.112, b_hw - 0.024, up)
    b_bh = interp([(0.56, 0.085), (0.64, 0.120), (0.90, 0.118), (1.00, 0.085), (1.07, 0.040), (1.13, 0.012)], z)
    b_th = interp([(0.56, 0.072), (1.0, 0.060), (1.15, 0.048), (1.26, 0.040)], z)
    return (lerp(c_hw, b_hw, wb), lerp(c_cw, b_cw, wb), lerp(c_bh, b_bh, wb), lerp(c_th, b_th, wb))


_LAB = ['back', 'back', 'shell', 'shell', 'side', 'bolster', 'bolster', 'bolster', 'bolster', 'bolster', 'pipe',
        'centre', 'centre']


def seat_section(hw, cw, bh, th, rb=0.022):
    bw = hw - cw
    left = [(0.0, -th), (-0.5 * hw, -th), (-hw + rb, -th), (-hw + rb * 0.29, -th + rb * 0.29), (-hw, -th + rb),
            (-hw, max(-th + rb + 0.004, bh * 0.40)),
            (-hw + bw * 0.10, bh * 0.88 + 0.003), (-hw + bw * 0.33, bh + 0.005),
            (-cw - bw * 0.30, bh * 0.74 + 0.003), (-cw - bw * 0.10, bh * 0.30 + 0.004),
            (-cw - 0.0035, 0.0062), (-cw + 0.0012, 0.0030), (-cw + 0.013, -0.0005), (-cw * 0.5, -0.0042)]
    loop = left + [(0.0, -0.005)] + [(-u, w) for (u, w) in left[1:][::-1]]
    labs = _LAB + ['centre', 'centre'] + _LAB[1:][::-1] + [_LAB[0]]
    return loop, labs


def seat_surface(xc, u, z=None, y=None, path=None):
    """Point on the seat's centre-panel surface plane + its normal: on the back by z, on the cushion by y."""
    path = path or seat_path()
    best = None
    for p, t, n in path:
        d = abs(p.z - z) if z is not None else abs(p.y - y)
        ok = (p.z > 0.6) if z is not None else (p.z < 0.6 and p.y > -0.40)
        if ok and (best is None or d < best[0]):
            best = (d, p, n, t)
    _, p, n, t = best
    hw, cw, bh, th = seat_params(p)
    loop, _ = seat_section(hw, cw, bh, th)
    front = sorted([q for q in loop[5:-4]], key=lambda q: q[0])
    w = front[-1][1]
    for (u0, w0), (u1, w1) in zip(front, front[1:]):
        if u0 <= u <= u1 and u1 - u0 > 1e-9:
            w = w0 + (w1 - w0) * (u - u0) / (u1 - u0)
            break
    return V((xc + u, p.y, p.z)) + n * w, n, t


SEAT_GREY_Z = 0.97          # grey suede inserts stop just under the harness slots
SEAT_GREY_EDGE = 13          # catmull-loop vertex just outboard of the bolster crest: grey from here to the inner seam
SEAT_PIPE_IDX = 21           # catmull-loop vertex in the middle of the bolster / centre-panel seam step


def stitch_3d(name, pts, nrms, material, dash=0.0058, gap=0.0040, w=0.0015, lift=0.0009):
    """Dashed stitch line lying on a curved surface: pts along the seam, nrms = surface normals there."""
    P = [V(p) for p in pts]
    N = [V(n).normalized() for n in nrms]
    acc = [0.0]
    for a, b in zip(P, P[1:]):
        acc.append(acc[-1] + (b - a).length)

    def at(sv):
        k = 0
        while k < len(acc) - 2 and acc[k + 1] < sv:
            k += 1
        t = min(1.0, max(0.0, (sv - acc[k]) / max(1e-9, acc[k + 1] - acc[k])))
        return P[k].lerp(P[k + 1], t), N[k].lerp(N[k + 1], t).normalized()

    bm = bmesh.new()
    for k in range(int(acc[-1] / (dash + gap))):
        (p0, n0), (p1, n1) = at(k * (dash + gap)), at(k * (dash + gap) + dash)
        d = p1 - p0
        if d.length < 1e-6:
            continue
        nn = (n0 + n1).normalized()
        sd = d.cross(nn).normalized() * (w / 2)
        q = [p0 - sd + n0 * lift, p1 - sd + n1 * lift, p1 + sd + n1 * lift, p0 + sd + n0 * lift]
        f = bm.faces.new([bm.verts.new(c) for c in q])
        f.normal_update()
        if f.normal.dot(nn) < 0:
            f.normal_flip()
    return obj_from_bmesh(name, bm, [material], smooth=False)


def seat_stitches(S, mt, xc, secs, rows):
    """Orange double stitching along the bolster front edges / shoulder wings and the grey insert seams."""
    nloop = len(secs[0])
    main = [r for r, row in enumerate(rows) if row[3] > 0.99]

    def line(idx, off, zmax=9.0, zmin=-9.0, ymax=9.0):
        pts, nrm = [], []
        for r in main:
            ring = secs[r]
            p = V(ring[idx])
            if not (zmin <= p.z <= zmax) or p.y > ymax:
                continue
            ta = (V(ring[(idx + 1) % nloop]) - V(ring[idx - 1])).normalized()       # across the seam
            r0, r1 = max(r - 1, main[0]), min(r + 1, main[-1])
            tl = (V(secs[r1][idx]) - V(secs[r0][idx])).normalized()                # along the seam
            n = ta.cross(tl).normalized()
            if n.dot(rows[r][2]) < 0:                 # front-facing seams: normal leans along the seat normal
                n = -n
            pts.append(p + ta * off)
            nrm.append(n)
        return pts, nrm

    for idx in (12, nloop - 12):                 # outer front edge of each bolster / shoulder wing
        for off in (-0.0026, 0.0026):
            pts, nrm = line(idx, off, ymax=0.10)
            if len(pts) > 2:
                S.append(stitch_3d('int_seat_stitch', pts, nrm, mt['stitch']))
    for idx in (SEAT_GREY_EDGE, nloop - SEAT_GREY_EDGE):   # outer seam of the grey suede inserts
        for off in (-0.0024, 0.0024):
            pts, nrm = line(idx, off, zmax=SEAT_GREY_Z - 0.01, ymax=0.10)
            if len(pts) > 2:
                S.append(stitch_3d('int_seat_stitch', pts, nrm, mt['stitch']))
    # r3: single 1.5 mm dashed orange stitch on the centre-panel side seams (was solid piping, also across the top)
    for idx in (SEAT_PIPE_IDX, nloop - SEAT_PIPE_IDX):
        pts, nrm = line(idx, 0.0, ymax=0.10)
        if len(pts) > 2:
            S.append(stitch_3d('int_seat_seam_stitch', pts, nrm, mt['stitch'], dash=0.0050, gap=0.0035, w=0.0015,
                               lift=0.0012))



SEAT_SQ_Z0 = 0.525          # r4: below this the seat shell is compressed so its bottom rests on the rails (FZ + 0.012)


def squash_bottom(o, z0=SEAT_SQ_Z0, zmin_t=None):
    """r4: the floor rose to 0.475 while the H-point / cushion stay put: compress the shell's lower side wall and pan
    (z < z0) so the bottom sits at FZ + 0.012 on the seat rails instead of 2 cm inside the floor."""
    zmin_t = FZ + 0.012 if zmin_t is None else zmin_t
    vs = o.data.vertices
    zmin = min(v.co.z for v in vs)
    if zmin >= zmin_t:
        return
    k = (z0 - zmin_t) / (z0 - zmin)
    for v in vs:
        if v.co.z < z0:
            v.co.z = z0 - (z0 - v.co.z) * k
    o.data.update()


def build_seat(S, mt, xc):
    path = seat_path()
    # end roundings (cushion front, back top)
    rows = []
    hw0, cw0, bh0, th0 = seat_params(path[0][0])
    R0 = 0.040
    for k in range(4, 0, -1):
        a = 0.5 * math.pi * k / 4
        p, t, n = path[0]
        rows.append((p - t * (R0 * math.sin(a)) + n * (-0.012 * math.sin(a)), t, n, math.cos(a), R0))
    for p, t, n in path:
        rows.append((p, t, n, 1.0, 0.0))
    R1 = 0.034
    for k in range(1, 5):
        a = 0.5 * math.pi * k / 4
        p, t, n = path[-1]
        rows.append((p + t * (R1 * math.sin(a)), t, n, math.cos(a), R1))
    secs, labs_all = [], None
    for p, t, n, f, R in rows:
        hw, cw, bh, th = seat_params(p)
        loop, labs = seat_section(hw, cw, bh, th)
        loop = catmull(loop, 2, closed=True)
        labs_all = [lb for lb in labs for _ in range(2)]
        wm = (bh - th) * 0.5
        sec = []
        dip = 0.0065 * math.exp(-((p.y - SEAM_Y) / 0.0045) ** 2) if p.z < 0.6 else 0.0
        for (u, w) in loop:
            if f < 1.0:
                u = u * (hw - R * (1 - f)) / hw
                w = wm + (w - wm) * f
            if dip > 1e-4 and abs(u) < cw - 0.004 and w > -0.02:
                w -= dip * smooth01((cw - 0.004 - abs(u)) / 0.012)
            q = V((xc + u, 0, 0)) + V((0, p.y, p.z)) + n * w
            sec.append(tuple(q))
        secs.append(sec)
    bm, faces, caps = grid_bm(secs, closed_u=True, cap=True)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    # materials: 0 shell, 1 leather, 2 stitch, 3 suede (cushion), 4 seat-back panel
    for f, j, i in faces + [(c, 0, 0) for c in caps]:
        lab = labs_all[i] if f not in caps else 'back'
        c = f.calc_center_median()
        if lab in ('back', 'shell'):
            f.material_index = 0
            set_uv(bm, f, metric_uv(2.0))
        elif lab in ('side', 'bolster'):
            ii = min(i, len(labs_all) - 1 - i)        # same index on both halves of the section
            if lab == 'side' or ii < SEAT_GREY_EDGE:
                f.material_index = 3                  # black suede outer roll (orange stitch on its front edge)
                set_uv(bm, f, metric_uv(CS))
            elif c.z < SEAT_GREY_Z:
                f.material_index = 5                  # grey suede inserts on the lower bolsters (seat_closeup.png)
                set_uv(bm, f, metric_uv(2.0))
            elif c.z > seat_leather_zh(abs(c.x - xc)):
                f.material_index = 3                  # r6: the headrest suede wraps the outer top corners
                set_uv(bm, f, metric_uv(CS))
            else:
                f.material_index = 1                  # charcoal leather shoulder wings
                set_uv(bm, f, metric_uv(2.0))
        elif lab == 'pipe':
            # r3: no solid orange piping any more - the seam reads through the 1.5 mm dashed stitch (seat_stitches)
            f.material_index = 3 if (c.z < SEAT_GREY_Z or c.z > seat_leather_zh(abs(c.x - xc))) else 1
            set_uv(bm, f, metric_uv(CS))
        else:
            if c.z > 0.585 and f.normal.y > 0.4:
                f.material_index = 4
                set_uv(bm, f, lambda co, n: (0.5 - (co.x - xc) / SB_W, (co.z - SB_Z0) / SB_ZSPAN))
            else:
                f.material_index = 3
                set_uv(bm, f, metric_uv(CS))
    seat = finish_bm('int_seat', bm, [mt['shell'], mt['seat_leather'], mt['stitch'], mt['suede'], mt['seatback'],
                                      mt['seat_grey_suede']], deg=55)
    # r6: see-through harness pass-throughs (seat_closeup.png: the firewall / hex mesh shows through them), cut through
    # the whole back (boolean), lined in gloss black, framed by a 12 mm round gloss-black loop on the front
    cut_passthroughs(seat, mt, xc, path)
    squash_bottom(seat)
    S.append(seat)
    seat_stitches(S, mt, xc, secs, rows)
    for su in (-SLOT_U, SLOT_U):
        q, n, t, ux, outline = slot_frame(xc, su, path)
        loop = offset2d(outline, -(SLOT_LOOP_R - 0.0015))           # loop centre line just outside the opening
        pts = [tuple(q + n * 0.0025 + ux * a + t * b) for (a, b) in loop]
        pts.append(pts[0])
        S.append(ttube('int_seat_slot_ring', pts, SLOT_LOOP_R, mt['gloss'], sides=12, bend=0.0))
    # seat base / mounting frame
    # r3: the floor came up to 0.45, the shell bottom (0.455 at the rear) now sits right on it: low sliders only
    zb = 0.533 - 0.078
    if zb - 0.002 - FZ > 0.006:
        S.append(slab('int_seat_base', rrect(0.38, 0.40, 0.03), (V((xc, -0.17, zb - 0.002)), V((1, 0, 0)),
                                                                 V((0, 1, 0))),
                      zb - 0.002 - FZ, [mt['anod'], mt['anod']], bevel=0.004, segs=1))
    for sx in (-1, 1):
        S.append(box('int_seat_rail', (0.028, 0.50, 0.010), (xc + sx * 0.15, -0.14, FZ + 0.005), material=mt['alu'],
                     bevel=0.002, segments=1))


def build_harness(S, mt, xc):
    path = seat_path()
    hb_y, hb_z = -0.659, 1.0
    belt_w, belt_t = 0.074, 0.0022
    buckle = V((xc, -0.205, 0.0))
    bq, bn, _ = seat_surface(xc, 0.0, y=buckle.y, path=path)
    buckle = bq + bn * 0.012
    for su in (-SLOT_U, SLOT_U):
        xs = xc + su
        q, n, t = seat_surface(xc, su, z=SLOT_Z, path=path)
        _, _, _, th = seat_params(q)
        back = q - n * (th + 0.006)
        front = q + n * 0.006
        pts = [(xs, hb_y - 0.045, hb_z - 0.07), (xs, hb_y - 0.030, hb_z + 0.005), (xs, hb_y - 0.008, hb_z + 0.026),
               (xs, hb_y + 0.03, hb_z + 0.040)]
        nrm = [(0, -1, 0.3), (0, -0.7, 0.7), (0, -0.2, 1), (0, 0.2, 1)]
        # r6: the strap comes through the LOWER part of the see-through pass-through (face up, travelling forward) and
        # drapes over the bottom of the gloss loop (seat_closeup.png); the opening above it stays open
        bb = (SLOT_Z + 0.030 - SLOT_H - q.z) / max(0.5, t.z)
        pts += [tuple(back + t * (bb + 0.0045) + n * 0.006), tuple(q + t * (bb + 0.0045) + n * 0.003),
                tuple(q + t * (bb - 0.0045) + n * 0.0102), tuple(q + t * (bb - 0.022) + n * 0.0065)]
        nrm += [tuple(t), tuple(t), tuple((n * 0.7 + t * 0.7).normalized()), tuple(n)]
        # down the seat back, then forward onto the cushion toward the buckle
        for z in (1.03, 0.98, 0.88, 0.78, 0.68, 0.61):
            qq, nn, tt = seat_surface(xc, su * lerp(1.0, 0.85, (1.06 - z) / 0.45), z=z, path=path)
            pts.append(tuple(qq + nn * 0.004))
            nrm.append(tuple(nn))
        for y in (-0.36, -0.29):
            qq, nn, tt = seat_surface(xc, su * 0.62, y=y, path=path)
            pts.append(tuple(qq + nn * 0.004))
            nrm.append(tuple(nn))
        pts.append(tuple(buckle + V((su * 0.30, -0.035, -0.004))))
        nrm.append(tuple(bn))
        S.append(ribbon('int_harness_shoulder', pts, nrm, 0.054, belt_t, mt['belt'], sub=2))
        # shoulder pad 100 x 15 mm from just under the loop; r6: ~28 cm long, the label (55 x 65 mm, white with the crow)
        # at chest height ~26 cm under the pass-through, near the pad's lower end (seat_closeup.png 'ON GEAR')
        ppts, pn = [], []
        for z in (1.036, 0.97, 0.90, 0.83, 0.762):
            qq, nn, tt = seat_surface(xc, su * lerp(1.0, 0.85, (1.06 - z) / 0.45), z=z, path=path)
            ppts.append(tuple(qq + nn * 0.0128))
            pn.append(tuple(nn))
        S.append(ribbon('int_harness_pad', ppts, pn, 0.100, 0.015, mt['pad'], sub=2))
        zl = 0.802
        qq, nn, tt = seat_surface(xc, su * lerp(1.0, 0.85, (1.06 - zl) / 0.45), z=zl, path=path)
        lf = (qq + nn * 0.0207, V((-1, 0, 0)), tt)
        S.append(quad('int_harness_label', lf, 0.055, 0.065, mt['label']))
        # adjuster buckle behind the bar
        S.append(box('int_harness_adjuster', (0.08, 0.012, 0.03), (xs, hb_y - 0.04, hb_z - 0.055), material=mt['alu']))
    # lap belts from the side anchors over the cushion to the buckle
    for sgn in (-1, 1):
        pts, nrm = [], []
        pts.append((xc + sgn * 0.265, -0.41, FZ + 0.05)); nrm.append((sgn * 0.6, 0.2, 0.8))
        pts.append((xc + sgn * 0.235, -0.385, 0.53)); nrm.append((sgn * 0.5, 0.0, 0.9))
        for u, y in ((0.17, -0.355), (0.12, -0.31), (0.07, -0.25)):
            qq, nn, tt = seat_surface(xc, sgn * u, y=y, path=path)
            pts.append(tuple(qq + nn * 0.005 + V((0, 0, 0.004 if u > 0.15 else 0)))); nrm.append(tuple(nn))
        pts.append(tuple(buckle + V((sgn * 0.035, -0.012, -0.004)))); nrm.append(tuple(bn))
        S.append(ribbon('int_harness_lap', pts, nrm, belt_w, belt_t, mt['belt'], sub=2))
        S.append(box('int_harness_anchor', (0.03, 0.05, 0.02), (xc + sgn * 0.265, -0.41, FZ + 0.03), material=mt['alu']))
    # sub strap from the front of the cushion
    pts, nrm = [], []
    for y in (0.03, -0.06, -0.14):
        qq, nn, tt = seat_surface(xc, 0.0, y=y, path=path)
        pts.append(tuple(qq + nn * 0.004)); nrm.append(tuple(nn))
    pts.append(tuple(buckle + V((0, 0.03, -0.004)))); nrm.append(tuple(bn))
    S.append(ribbon('int_harness_sub', pts, nrm, 0.050, belt_t, mt['belt'], sub=2))
    # cam-lock buckle
    S.append(lathe_at('int_harness_buckle', [(0.0, -0.004), (0.040, -0.004), (0.043, 0.0), (0.042, 0.006), (0.036, 0.009),
                                             (0.0, 0.009)], buckle - bn * 0.004, bn, mt['polished'], segs=28))
    S.append(lathe_at('int_harness_buckle_c', [(0.0, 0.0), (0.024, 0.0), (0.024, 0.006), (0.0, 0.007)],
                      buckle + bn * 0.006, bn, mt['anod'], segs=20))
    lv = V((1, 0.25, 0)).normalized()
    S.append(box('int_harness_lever', (0.060, 0.012, 0.006), tuple(buckle + bn * 0.013 + lv * 0.012), material=mt['anod']))


# =====================================================================================================
#  DOOR CARDS, SIDE PANELS, FIREWALL
# =====================================================================================================

def _leg_y(a, b, z):
    t = (z - a[2]) / (b[2] - a[2])
    return a[1] + (b[1] - a[1]) * t


def hoop_y(z):          # main-hoop leg (behind the door), left side
    return _leg_y((-0.70, spec.MAIN_HOOP_Y, spec.FRAME_RAIL_Z), spec.B_PILLAR_FOOT, z)


def apillar_y(z):       # windshield-hoop leg (front of the door)
    return _leg_y((-0.70, 0.82, spec.FRAME_RAIL_Z), spec.A_PILLAR_FOOT, z)


CARD_X = -0.676          # inner face of the door card (left side)
CARD_BACK = -0.758
CARD_Z = (FZ + 0.002, 1.054)    # r4: bottom on the floor (0.477; was 0.452, 2 cm under the new floor)
QUILT_TILE = (0.128, 0.144)      # r5: interior_door_quilt.png tile: 2 x 2 diamonds of 64 x 72 mm
KICK_Z = 0.540                   # r4: carbon kick strip over the frame rail (rail inner face |x| 0.6746, top 0.525)


# r6: the front lower corner of the door tucks under (spec FRONT_CORNER_HALF_W_Z; body door_u / corner_u) and the chassis
# frame rail tucks in ahead of y 0.48 (chassis RAIL_TUCK: rail inner face |x| 0.675 @ y 0.40 -> 0.586 @ 0.70 -> 0.558 @
# 1.00, probed on the built chassis). The door card, kick strip, footwell sides and floor mats follow both.
RAIL_IN = [(0.40, 0.675), (0.48, 0.669), (0.55, 0.645), (0.60, 0.625), (0.65, 0.6055), (0.70, 0.586), (0.74, 0.575),
           (0.78, 0.5696), (0.82, 0.5674), (0.90, 0.563), (1.00, 0.5578), (1.05, 0.555), (1.10, 0.544)]
CARD_U, CARD_BACK_U = -CARD_X, -CARD_BACK


def rail_in(y):
    """|x| of the chassis frame rail's inner face at station y (z 0.475-0.525)."""
    return interp(RAIL_IN, y)


def skin_u(y, z):
    """|x| of the body's outer side skin at (y, z) (door / front lower corner; r6 body side_x, fender side ahead of the
    shut line); fallback: inset door 0.770 blending into spec FRONT_CORNER_HALF_W_Z ahead of y 0.40."""
    try:
        import body as _body
        u = -_body.side_x(y, z)
        if y > 0.80:
            try:
                u = min(u, -_body.fside_x(y, z))
            except Exception:
                pass
        return u
    except Exception:
        fc = sorted(spec.FRONT_CORNER_HALF_W_Z)
        uc = interp(fc, z) - 0.003
        return lerp(0.770, min(0.770, uc), smooth01((y - 0.40) / 0.30))


# body door hem: its inward return lip (z 0.535-0.565) reaches |x| 0.734 behind y 0.40 and follows the tucked front corner
# in to 0.612 (probed on the built body); the front clip's lip is 0.628 ahead of y 0.88
HEM_IN = [(0.40, 0.734), (0.45, 0.730), (0.50, 0.713), (0.55, 0.665), (0.60, 0.645), (0.65, 0.625), (0.70, 0.613),
          (0.86, 0.612), (0.88, 0.628)]


def skin_env(y, z):
    """skin_u, enveloped over +-25 mm in y: the door's front shut-line kink (y ~0.49) and the corner's concave turn put
    the real skin inside the chord between grid columns."""
    return min(skin_u(y - 0.025, z), skin_u(y, z), skin_u(y + 0.025, z))


def hem_lim(y, z):
    """Outer |x| limit (8 mm inside) from the door's bottom hem lip, opening up 0.8 m/m above it."""
    return interp(HEM_IN, y) - 0.008 + 0.8 * max(0.0, z - 0.565)


def card_face_u(y, z):
    """|x| of the door card's cabin-side face: CARD_U, pulled in where the tucked skin comes within 21 mm (13 mm skin
    clearance + 8 mm card) or the hem lip within 16 mm and, right at the floor, onto the tucked frame rail's inner face
    (behind the kick strip)."""
    u = min(CARD_U, skin_env(y, z) - 0.021, hem_lim(y, z) - 0.008)
    ur = rail_in(y) - 0.002
    if ur < u:
        u = min(u, ur + (u - ur) * smooth01((z - 0.530) / 0.030))
    return u


def card_back_u(y, z):
    """|x| of the card's back face: CARD_BACK_U clamped 13 mm inside the body skin and 8 mm inside the hem lip, <= 0.730
    behind the door pocket and <= 0.75 elsewhere in the inset door zone (arbiter r6), <= 0.728 behind the door's rear
    edge return (y < -0.56), <= 0.72 over the sill; >= 4 mm behind the face."""
    lim = min(CARD_BACK_U, skin_env(y, z) - 0.013, hem_lim(y, z))
    if -0.42 < y < 0.58 and 0.775 < z < 1.06:
        lim = min(lim, 0.730)
    if -0.60 < y < 0.70:
        lim = min(lim, 0.75)
    if y < -0.56:
        lim = min(lim, 0.728)
    if z < 0.56:
        lim = min(lim, 0.72)
    return max(lim, card_face_u(y, z) + 0.004)


def card_grid(name, z_lo, z_hi, y_lo, y_hi, face_off, thick, mlist, nz=22, ny=34, uvs=2.0):
    """A door-card layer as a closed grid: rows over z, columns over y (y_lo(z)..y_hi(z)), cabin face at
    card_face_u - face_off, back at min(face + thick, card_back_u) (left side; mirrored later)."""
    rows = []
    for j in range(nz + 1):
        z = z_lo + (z_hi - z_lo) * j / nz
        a, b = y_lo(z), y_hi(z)
        ys = [a + (b - a) * (0.5 - 0.5 * math.cos(math.pi * i / ny)) for i in range(ny + 1)]
        fr_ = [(-(card_face_u(y, z) - face_off), y, z) for y in ys]
        bk_ = [(-min(card_face_u(y, z) - face_off + thick, card_back_u(y, z)), y, z) for y in ys[::-1]]
        rows.append(fr_ + bk_)
    bm, faces, caps = grid_bm(rows, closed_u=True, cap=True)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for f in bm.faces:
        f.material_index = 0
        set_uv(bm, f, metric_uv(uvs))
    return finish_bm(name, bm, mlist, deg=40)


def warp_to_card(o, base_u=None):
    """Move every vertex of a card-mounted object (built on the flat card face |x| = CARD_U) inward by the card's local
    tuck (CARD_U - card_face_u). Returns the largest shift."""
    mx = 0.0
    for v in o.data.vertices:
        sft = CARD_U - card_face_u(v.co.y, v.co.z)
        if sft > 1e-5:
            v.co.x += sft if v.co.x < 0 else -sft
            mx = max(mx, sft)
    o.data.update()
    return mx


# r5: door top roll. chassis belt_rail (straight, spec A_PILLAR_FOOT -> B_PILLAR_FOOT, 1.75" tube) runs from |x| 0.63 at the
# A-pillar to 0.74 at the main hoop, so it passes from inboard of the door card (front) to over its back (rear). The upper
# band and a black leather roll are ONE swept profile per station y: band face (|x| BAND_U) with a rounded lower edge, a
# lean into a R ROLL_R roll that is concentric with the rail where the rail is inboard (ROLL_T shell + ~4 mm clearance),
# a flat top at ROLL_TOP, an outboard round, and an outboard skirt that tucks 3 mm inside the body door cap's inner flank
# (parts/body.py cap_shape). interior_dash.png / interior_driver_alt_red.png: the smooth black band runs to the door top
# and wraps over it - no tube shows along the door top.
RAIL_ZC = spec.A_PILLAR_FOOT[2] - 0.0007      # rail centre z (measured 1.0793 on the built chassis)
RAIL_RR = spec.CAGE_TUBE_R + 0.0004           # polygon radius of the 18-gon tube
ROLL_R, ROLL_T, ROLL_C = 0.030, 0.004, 0.0035
ROLL_TOP = RAIL_ZC + RAIL_RR + ROLL_C + ROLL_T + 0.0005     # ~1.110
BAND_U = 0.660               # band face |x| (CARD_X + 0.016)
BAND_BACK_U = 0.678          # band back, 2 mm into the card
ROLL_Y = (-0.598, 0.672)     # rear end just ahead of the main-hoop leg, front end under the A-pillar foot / dash end
# band lower edge: rear, a tab dipping round the handle, then stepping up toward the dash (the quilt rises there)
# (interior_dash.png, near face-on to the door, ~714 px/m there - checked on the quilt height 0.30 m and the band: rear band
# 0.105 m under the door top, tab bottom 0.225 under it, 0.215 m long; quilt nearly up to the roll in front of the tab)
BAND_ZB_REAR, BAND_ZB_TAB, BAND_ZB_FRONT = 1.005, 0.887, 1.030   # r5b front 1.050 -> 1.030: the rail's underside
                                                                 # is at 1.057 there (quilt/band cleared it by <0)
TAB_Y = (0.008, 0.222)
TAB_RAMP = (0.030, 0.035)    # rounded rear / front steps of the tab
HANDLE_Y, HANDLE_Z = 0.102, 0.986
LATCH_Y = 0.117              # dark latch slot in the roll's inboard top (photo notch above the handle's centre-front)

_FLANK_FALLBACK = [(-0.70, 0.765, 1.085), (0.30, 0.765, 1.0905), (0.40, 0.7538, 1.099), (0.50, 0.735, 1.099),
                   (0.60, 0.7218, 1.099), (0.65, 0.7313, 1.099), (0.70, 0.7205, 1.099), (0.75, 0.7092, 1.099)]


def rail_u(y):
    (xa, ya, _), (xb, yb, _) = spec.A_PILLAR_FOOT, spec.B_PILLAR_FOOT
    return -(xb + (xa - xb) * (y - yb) / (ya - yb))


def body_flank(y):
    """(|x| of the body door cap's inner flank, door top z) at station y."""
    try:
        import body as _body
        zt = _body.door_top(y)
        xin, _ = _body.cap_shape(y, zt)
        return -xin, zt
    except Exception:
        return interp([(a, b) for a, b, c in _FLANK_FALLBACK], y), interp([(a, c) for a, b, c in _FLANK_FALLBACK], y)


def band_zb(y):
    if y < TAB_Y[0]:
        return lerp(BAND_ZB_REAR, BAND_ZB_TAB, smooth01((y - TAB_Y[0] + TAB_RAMP[0]) / TAB_RAMP[0]))
    if y < TAB_Y[1]:
        return BAND_ZB_TAB
    return lerp(BAND_ZB_TAB, BAND_ZB_FRONT, smooth01((y - TAB_Y[1]) / TAB_RAMP[1]))


def roll_ui(y):
    return min(BAND_U - 0.003, rail_u(y) - (RAIL_RR + ROLL_C + ROLL_T + 0.0005))


def roll_centre(y):
    """(u, z) centre of the roll's R ROLL_R arc at station y (concentric with the rail where the rail is inboard)."""
    return roll_ui(y) + ROLL_R, ROLL_TOP - ROLL_R


def band_face_top(y):
    """(z, angle deg) where the vertical band face (|x| BAND_U) meets the roll arc from below. r5b: the face no longer
    leans in over a fixed height (in front of the tab that lean cut through the rail's lower half): it rises straight
    to the roll circle and then follows that circle round the rail's underside / inboard side."""
    uc, zc = roll_centre(y)
    du = max(-ROLL_R + 1e-4, min(ROLL_R - 1e-4, BAND_U - uc))
    dz = -math.sqrt(ROLL_R * ROLL_R - du * du)
    return zc + dz, math.degrees(math.atan2(dz, du)) % 360.0


def band_face_u(y, z):
    """|x| of the band face at (y, z) (vertical low down, then on the roll arc)."""
    zf, a0 = band_face_top(y)
    if z <= zf:
        return BAND_U
    uc, zc = roll_centre(y)
    w = math.sqrt(max(0.0, ROLL_R * ROLL_R - (min(z, zc) - zc) ** 2))
    return uc - w                             # inboard side of the roll circle (180..270 deg)


ROLL_K0 = 5                  # index of the first lean point (the inner shell starts there)


def roll_profile(y):
    """Outer (u, z) contour of the band + roll at station y, and the matching inner shell from ROLL_K0 on."""
    ur = rail_u(y)
    fu, ztb = body_flank(y)
    ui = roll_ui(y)
    zt = ROLL_TOP
    R = ROLL_R
    zrc = zt - R
    uo = fu - 0.003
    zob = ztb - 0.024
    zb = band_zb(y)
    Ro = 0.012
    zf0, a0 = band_face_top(y)
    out = [(BAND_BACK_U, zb + 0.004), (BAND_U + 0.007, zb), (BAND_U + 0.0021, zb + 0.0021), (BAND_U, zb + 0.007),
           (BAND_U, (zb + 0.007 + zf0) / 2), (BAND_U, zf0)]
    for k in range(1, 5):                     # round the rail's underside / inboard side on the roll circle to 180 deg
        a = math.radians(a0 + (180.0 - a0) * k / 4)
        out.append((ui + R + R * math.cos(a), zrc + R * math.sin(a)))
    for k in range(1, 7):
        a = math.radians(180 - 15 * k)
        out.append((ui + R + R * math.cos(a), zrc + R * math.sin(a)))
    u1 = uo - Ro
    for t in (0.33, 0.67):
        out.append((lerp(ui + R, u1, t), zt + 0.0015 * math.sin(math.pi * t)))      # slight crown
    for k in range(0, 5):
        a = math.radians(90 - 22.5 * k)
        out.append((u1 + Ro * math.cos(a), zt - Ro + Ro * math.sin(a)))
    out.append((uo, lerp(zt - Ro, zob, 0.5)))
    out.append((uo, zob))
    # inner shell: offset of out[ROLL_K0:] by ROLL_T toward the rail side
    seg = out[ROLL_K0:]
    inner = []
    for i, (u, z) in enumerate(seg):
        u0, z0 = seg[max(i - 1, 0)]
        u1_, z1_ = seg[min(i + 1, len(seg) - 1)]
        du, dz = u1_ - u0, z1_ - z0
        ln = math.hypot(du, dz) or 1.0
        nu, nz = dz / ln, -du / ln            # right-hand normal of the travel direction = inward (toward the rail)
        inner.append([u + nu * ROLL_T, z + nz * ROLL_T])
    # keep the rail clear: push inner points (and their outer twins) radially away from the rail centre
    need = RAIL_RR + ROLL_C
    for i, q in enumerate(inner):
        du, dz = q[0] - ur, q[1] - RAIL_ZC
        d = math.hypot(du, dz)
        if d < need:
            s = (need - d) / max(d, 1e-6)
            q[0] += du * s
            q[1] += dz * s
            ou, oz = out[ROLL_K0 + i]
            out[ROLL_K0 + i] = (ou + du * s, oz + dz * s)
    # the hidden shell can be coarser, except round the rail's underside (chords there grazed the rail)
    keep = list(range(0, 6)) + list(range(6, len(inner) - 1, 2)) + [len(inner) - 1]
    return out, [tuple(inner[i]) for i in keep]


def build_door_roll(mt):
    """Left door band + top roll (one closed swept mesh)."""
    ys = []
    y = ROLL_Y[0]
    while y < ROLL_Y[1] - 1e-6:
        ys.append(y)
        near = (TAB_Y[0] - TAB_RAMP[0] - 0.006 < y < TAB_Y[0] + 0.006) or \
               (TAB_Y[1] - 0.006 < y < TAB_Y[1] + TAB_RAMP[1] + 0.006)
        y += 0.008 if near else 0.045
    ys.append(ROLL_Y[1])
    secs = []
    for y in ys:
        out, inner = roll_profile(y)
        # band back top: under the rail where the rail passes over the band back (y > -0.1)
        dub = BAND_BACK_U - rail_u(y)
        rb = RAIL_RR + ROLL_C + 0.003
        zbk = RAIL_ZC - math.sqrt(rb * rb - dub * dub) if abs(dub) < rb else out[ROLL_K0][1]
        loop = out + inner[::-1] + [(BAND_BACK_U, min(out[ROLL_K0][1], zbk))]
        secs.append([(-u, y, z) for (u, z) in loop])
    bm, faces, caps = grid_bm(secs, closed_u=True, cap=True)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for f in bm.faces:
        f.material_index = 0
        set_uv(bm, f, metric_uv(2.0))
    o = finish_bm('int_door_roll', bm, [mt['leather_blk']], deg=50)
    L = [o]
    # dark latch slot on the roll's inboard top (interior_dash.png: small notch in the door top above the handle). A real
    # 12 mm notch would open the rail (the roll is concentric with it here), so it is a 40 x 12 mm black slot plate
    # lying on the roll with a polished lip.
    ui = roll_ui(LATCH_Y)
    a = math.radians(140)
    c = V((-(ui + ROLL_R + ROLL_R * math.cos(a)), LATCH_Y, ROLL_TOP - ROLL_R + ROLL_R * math.sin(a)))
    n = V((-math.cos(a), 0, math.sin(a)))      # outward roll normal at that angle (world, left side)
    ux = V((0, 1, 0))
    fr = (c + n * 0.0010, ux, n.cross(ux).normalized())
    L.append(slab('int_door_latch', rrect(0.048, 0.012, 0.003, n=2), fr, 0.0012, [mt['hole'], mt['anod']], bevel=0.0006,
                  segs=1))
    return L


def build_door_card(mt):
    """Left door card; returned objects get mirrored for the passenger side."""
    L = []
    z0, z1 = CARD_Z
    yr = lambda z: hoop_y(z) + 0.030
    yf = lambda z: apillar_y(z) - 0.028
    # r6: a grid (rows over z, columns over y) so the card can bend in at the door's tucked lower front corner and onto the
    # tucked frame rail (card_face_u / card_back_u); was a flat slab at CARD_X with a clamped back
    L.append(card_grid('int_door_card', z0, z1, yr, yf, 0.0, CARD_BACK_U - CARD_U, [mt['leather_blk']], nz=18, ny=28))
    # r5: upper band + leather door-top roll over the belt rail (was a flat band to 1.054 with the rail exposed above)
    L += build_door_roll(mt)
    # handle (interior_dash.png): r5 polished lozenge escutcheon on the band's handle tab
    hu = band_face_u(HANDLE_Y, HANDLE_Z)
    hfr = (V((-hu, HANDLE_Y, HANDLE_Z)), V((0, 1, 0)), V((0, 0, 1)))
    L += door_handle(mt, hfr)
    # quilted inset: r5 its top follows the band's lower edge (tucked 1 cm behind it): low round the handle tab, stepping
    # up toward the dash in front of it (photo)
    ys = [0.70, 0.40] + [TAB_Y[1] + TAB_RAMP[1] * (1 - k / 6) for k in range(7)] + [0.10] + \
         [TAB_Y[0] - TAB_RAMP[0] * k / 6 for k in range(7)] + [-0.30, -0.70]
    top = [(yy, band_zb(yy) + 0.012) for yy in ys]
    q = [(-0.58, 0.690), (0.60, 0.745), (0.645, 0.775), (0.645, band_zb(0.645) + 0.012)]
    q += [p for p in top if -0.58 < p[0] < 0.645] + [(-0.58, band_zb(-0.58) + 0.012)]
    q = [(max(yr(z) + 0.035, y), z) if y < 0 else (min(yf(z) - 0.05, y), z) for (y, z) in q]
    qo = round_outline(q, 0.010, n=2)
    quilt = slab('int_door_quilt', qo, (V((CARD_X + 0.004, 0, 0)), V((0, 1, 0)), V((0, 0, 1))), 0.006,
                 [mt['quilt'], mt['leather_blk']], bevel=0.004, segs=2,
                 uv_front=lambda a, b: (a / QUILT_TILE[0], b / QUILT_TILE[1]))
    # piping around the quilt
    piping = ttube('int_door_quilt_piping', [(CARD_X + 0.0045, a, b) for (a, b) in qo + [qo[0]]], 0.0028,
                   mt['leather_blk'], sides=8, bend=0.0)          # outline already rounded (fillets cost 10k tris)
    L += [quilt, piping]
    # lower panel: double orange stitch (r6: bends in with the card) and the carbon vent
    for dz in (0.0, 0.007):
        pts = [(yr(0.6) + 0.04, 0.610 + dz), (-0.1, 0.625 + dz), (0.35, 0.653 + dz), (yf(0.67) - 0.06, 0.673 + dz)]
        L.append(stitch_line('int_door_stitch', pts, CARD_X + 0.0007, mt['stitch']))
    for o in L[-4:]:
        warp_to_card(o)
    # kick strip along the card bottom, 8 mm proud of the card face (r6: a bent grid following the card / tucked rail)
    L.append(card_grid('int_door_kick', FZ + 0.002, KICK_Z, lambda z: yr(z) + 0.012, lambda z: yf(z) - 0.012, 0.008,
                       0.012, [mt['carbon']], nz=4, ny=30, uvs=CS))
    # r6: the vent stops at y 0.50, clear of the tucked front corner
    vent = [(0.20, 0.552), (0.50, 0.552), (0.50, 0.625), (0.26, 0.625)]
    L.append(slab('int_door_vent', round_outline(vent, 0.015), (V((CARD_X + 0.003, 0, 0)), V((0, 1, 0)), V((0, 0, 1))),
                  0.006, [mt['carbon'], mt['leather_blk']], bevel=0.002, segs=1, uv_front=lambda a, b: (a * CS, b * CS)))
    warp_to_card(L[-1])
    return L


def door_handle(mt, fr):
    """r5 escutcheon in frame fr (origin on the band face, ux = +y forward, uy = up, normal into the cabin): polished
    aluminium lozenge (fat R 44 mm rear end, R 16 mm front end, straight tapered edges), 7.5 mm proud with a 3 mm rounded
    outer bevel and a 6 mm rim, a 7 mm deep satin dish; lever, slot and two screws inside the dish. Size from the photo's
    own proportions (escutcheon 2.8 diamonds long, 0.9 x the rear band height): 170 x 88 mm (the critic's 120 x 65 has the
    same 1.9:1 aspect but would read ~30 % small against the 64 x 72 mm quilt and the band)."""
    org, ux, uy = fr
    nz = ux.cross(uy).normalized()
    W = lambda a, b, c: org + ux * a + uy * b + nz * c
    circ = []
    for (cx, cy, r) in ((-0.041, 0.0, 0.044), (0.069, 0.0, 0.016)):
        circ += [(cx + r * math.cos(t), cy + r * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 48, endpoint=False)]
    out = _resample_closed(_hull2d(circ), 56)
    if poly_area(out) < 0:
        out = out[::-1]
    D, RH, BV, RIM, DISH = 0.004, 0.0075, 0.003, 0.006, 0.007
    rings = [(out, -D), (out, RH - BV)]
    for k in range(3):                                     # rounded outer bevel
        ang = 0.5 * math.pi * (k + 1) / 3
        rings.append((offset2d(out, BV * (1 - math.cos(ang))), RH - BV + BV * math.sin(ang)))
    rings.append((offset2d(out, RIM - 0.0012), RH))
    rings.append((offset2d(out, RIM), RH - 0.0012))       # round-over into the dish
    rings.append((offset2d(out, RIM + 0.0018), RH - DISH))
    bm = bmesh.new()
    vr = [[bm.verts.new(W(a, b, c)) for (a, b) in ring] for ring, c in rings]
    n = len(out)
    lay = bm.loops.layers.uv.verify()
    for j in range(len(vr) - 1):
        for i in range(n):
            i2 = (i + 1) % n
            f = bm.faces.new((vr[j][i], vr[j][i2], vr[j + 1][i2], vr[j + 1][i]))
            f.material_index = 1 if j == len(vr) - 2 else 0
    fl = bm.faces.new(vr[-1])
    fl.material_index = 1
    bk = bm.faces.new(vr[0][::-1])
    bk.material_index = 0
    for f in bm.faces:
        for lp in f.loops:
            co = lp.vert.co - org
            lp[lay].uv = (co.dot(ux) * 20, co.dot(uy) * 20)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    pod = finish_bm('int_door_handle_pod', bm, [mt['polished'], mt['esc']], deg=40)
    L = [pod]
    fz = RH - DISH                                         # dish floor
    for (a, b) in ((-0.022, 0.022), (-0.010, -0.024)):      # photo: one screw above, one below the lever's rear part
        L.append(lathe_at('int_door_handle_screw', [(0.0, 0.0), (0.0030, 0.0), (0.0026, 0.0011), (0.0, 0.0014)],
                          W(a, b, fz), nz, mt['chrome'], segs=10))
    # black slot at the lever's rear end and the polished lever: up out of the slot, then forward along the dish
    L.append(slab('int_door_handle_slot', rrect(0.014, 0.010, 0.004, n=3), (W(-0.050, -0.008, fz + 0.0003), ux, uy),
                  0.0003, [mt['hole'], mt['hole']]))
    p0, p1, p2 = W(-0.050, -0.008, fz + 0.0015), W(-0.040, -0.0065, fz + 0.0062), W(0.068, 0.012, fz + 0.0062)
    L.append(ttube('int_door_handle_lever', [tuple(p0), tuple(p1), tuple(p2)], 0.0045, mt['polished'], sides=10,
                   bend=0.008))
    L.append(sharpen(sphere('int_door_handle_lever_end', 0.0050, tuple(p2), mt['polished'], segs=12, rings=8), 80))
    return L


def _hull2d(pts):
    pts = sorted(set((round(x, 7), round(y, 7)) for x, y in pts))
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def _resample_closed(pts, n):
    P = [V((p[0], p[1], 0)) for p in pts] + [V((pts[0][0], pts[0][1], 0))]
    acc = [0.0]
    for a_, b_ in zip(P, P[1:]):
        acc.append(acc[-1] + (b_ - a_).length)
    out, k = [], 0
    for i in range(n):
        sv = acc[-1] * i / n
        while acc[k + 1] < sv:
            k += 1
        t = (sv - acc[k]) / max(1e-9, acc[k + 1] - acc[k])
        q = P[k].lerp(P[k + 1], t)
        out.append((q.x, q.y))
    return out


def round_outline(pts, r, n=4):
    """Round every corner of a closed 2D polygon with radius r."""
    out = []
    m = len(pts)
    if poly_area(pts) < 0:
        pts = pts[::-1]
    for i in range(m):
        a, b, c = V((*pts[i - 1], 0)), V((*pts[i], 0)), V((*pts[(i + 1) % m], 0))
        d1, d2 = (a - b), (c - b)
        l1, l2 = d1.length, d2.length
        d1.normalize(); d2.normalize()
        ang = d1.angle(d2)
        if ang < 1e-3 or ang > math.pi - 1e-3:
            out.append((b.x, b.y)); continue
        t = min(r / math.tan(ang / 2), l1 * 0.45, l2 * 0.45)
        rr = t * math.tan(ang / 2)
        p1, p2 = b + d1 * t, b + d2 * t
        cen = b + (d1 + d2).normalized() * (rr / math.sin(ang / 2))
        a1 = math.atan2(p1.y - cen.y, p1.x - cen.x)
        a2 = math.atan2(p2.y - cen.y, p2.x - cen.x)
        da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        for k in range(n + 1):
            aa = a1 + da * k / n
            out.append((cen.x + rr * math.cos(aa), cen.y + rr * math.sin(aa)))
    return out


def stitch_line(name, pts2d, x, material, dash=0.0065, gap=0.0045, w=0.0016):
    """Dashed stitch line on a plane x = const (left-side door card), points in (y, z)."""
    P = [V(p) for p in catmull(pts2d, 6)]
    acc = [0.0]
    for a, b in zip(P, P[1:]):
        acc.append(acc[-1] + (b - a).length)

    def at(s):
        k = 0
        while k < len(acc) - 2 and acc[k + 1] < s:
            k += 1
        t = (s - acc[k]) / max(1e-9, acc[k + 1] - acc[k])
        return P[k].lerp(P[k + 1], min(1.0, max(0.0, t)))

    bm = bmesh.new()
    n = int(acc[-1] / (dash + gap))
    for k in range(n):
        p0, p1 = at(k * (dash + gap)), at(k * (dash + gap) + dash)
        d = (p1 - p0)
        if d.length < 1e-6:
            continue
        d.normalize()
        nrm = V((-d.y, d.x))
        q = [p0 - nrm * w / 2, p1 - nrm * w / 2, p1 + nrm * w / 2, p0 + nrm * w / 2]
        vs = [bm.verts.new((x, c.x, c.y)) for c in q]
        f = bm.faces.new(vs)
        f.normal_update()
        if f.normal.x < 0:
            f.normal_flip()
    return obj_from_bmesh(name, bm, [material], smooth=False)


# r4: lower edge of the pod skin's inward curl beside the rear quarter (body r4, ray-probed: lowest z where the skin
# is still >= 7 mm outboard of the panel's back face), +~8 mm. Below it the chassis trailing-arm box / bolt live.
QUARTER_BOTTOM = [(-0.93, 0.702), (-0.915, 0.692), (-0.90, 0.680), (-0.885, 0.664), (-0.87, 0.654), (-0.855, 0.642),
                  (-0.84, 0.633), (-0.825, 0.625), (-0.81, 0.615), (-0.795, 0.598), (-0.78, 0.593), (-0.76, 0.590)]
XQ = -0.755                  # r4: quarter panel cabin face (was -0.760): back face 8 mm inside the pod rim (|x| 0.765)
XF = -0.662                  # r4: lower filler panel cabin face, inboard of the trailing-arm bolt end (|x| 0.672)


# front face of the windshield-hoop leg (chassis windshield_hoop, probed sections) and the door / front-clip shut line
LEG_FRONT = [(0.50, 0.829), (0.55, 0.835), (0.60, 0.829), (0.65, 0.822), (0.70, 0.815), (0.75, 0.808), (0.80, 0.801),
             (0.85, 0.794), (0.90, 0.787)]
SHUT_Y = 0.86


def footwell_u(y, z):
    """12 mm inside the skin, 30 mm at the door / front-clip shut line (both return flanges reach ~22 mm in), inside the
    hem lip at the bottom."""
    dent = 0.018 * (1.0 - smooth01((abs(y - SHUT_Y) - 0.015) / 0.025))
    return min(0.652, skin_env(y, z) - 0.012 - dent, hem_lim(y, z))


def build_footwell_side(mt, ny=26, nz=14, t=0.004):
    # r6: starts at the hoop leg's front face (its rear edge cut the leg foot and the door bar where they meet the leg)
    y_lo = lambda z: interp(LEG_FRONT, z) + 0.010
    ytop0 = y_lo(0.86)

    def zb_of(y):
        uc = footwell_u(y, 0.52) + t / 2
        d = abs(uc - (rail_in(y) + 0.025))
        return 0.500 + math.sqrt(max(0.0, 0.0255 ** 2 - d * d)) + 0.001 if d < 0.0255 else FZ + 0.001

    def zt_of(y):
        return interp([(ytop0, 0.86), (0.80, 0.88), (1.00, 0.84)], y)

    rings = []
    for i in range(ny + 1):
        sp = i / ny
        col = []
        for j in range(nz + 1):
            tp = j / nz
            y = lerp(y_lo(lerp(0.52, 0.87, tp)), 1.00, sp)
            col.append((y, zb_of(y) + (zt_of(y) - zb_of(y)) * tp))
        rings.append([(-footwell_u(y, z), y, z) for (y, z) in col] +
                     [(-(footwell_u(y, z) + t), y, z) for (y, z) in col[::-1]])
    bm, faces, caps = grid_bm(rings, closed_u=True, cap=True)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for f in bm.faces:
        f.material_index = 0
        set_uv(bm, f, metric_uv(CS))
    return finish_bm('int_footwell_side', bm, [mt['carbon']], deg=40)


def build_side_panels(S, mt):
    L = []
    # rear quarter (beside the seat back, behind the main-hoop leg, to the firewall), carbon.
    # r4: its bottom follows the pod skin's lower curl (it poked 2 cm out of the skin at y -0.88 and cut the chassis
    # trailing-arm box); near the top its front edge steps back behind the hoop leg (the leg's outer face is |x| 0.760)
    pod_top = [(-0.95, 1.175), (-0.90, 1.172), (-0.80, 1.138), (-0.70, 1.090), (-0.62, 1.060)]
    fy = lambda z: hoop_y(z) + 0.005 - 0.022 * smooth01((z - 0.85) / 0.15)
    yb = [(y, z) for (y, z) in QUARTER_BOTTOM if spec.FIREWALL_Y - 0.004 < y < fy(z)]
    z_front0 = interp(QUARTER_BOTTOM, fy(0.6))
    outline = [(spec.FIREWALL_Y - 0.004, interp(QUARTER_BOTTOM, spec.FIREWALL_Y - 0.004))]
    outline += yb                                          # back -> front along the skin's lower curl
    outline.append((fy(z_front0), z_front0))
    for z in (0.75, 0.85, 0.95, 1.0, 1.05):
        outline.append((fy(z), z))
    for (y, z) in pod_top[::-1]:
        if y < fy(1.05) and y > spec.FIREWALL_Y - 0.01:
            outline.append((y, z - 0.014))
    outline.append((spec.FIREWALL_Y - 0.004, interp(pod_top, spec.FIREWALL_Y) - 0.014))
    L.append(slab('int_rear_quarter', outline, (V((XQ, 0, 0)), V((0, 1, 0)), V((0, 0, 1))), 0.004,
                  [mt['carbon'], mt['carbon']], uv_front=lambda a, b: (a * CS, b * CS)))
    # r4: lower filler inboard of the hoop leg / trailing-arm box, floor to just over the quarter panel's lower edge
    yf0 = hoop_y(FZ) + 0.004
    filler = [(spec.FIREWALL_Y - 0.002, FZ), (yf0, FZ), (yf0, 0.70), (spec.FIREWALL_Y - 0.002, 0.73)]
    L.append(slab('int_quarter_filler', round_outline(filler, 0.01), (V((XF, 0, 0)), V((0, 1, 0)), V((0, 0, 1))), 0.003,
                  [mt['carbon'], mt['carbon']], uv_front=lambda a, b: (a * CS, b * CS)))
    # grommet / filler cap on the quarter panel (seat_closeup.png); r4: up to z 0.80 (the panel now starts ~0.64)
    L.append(lathe_at('int_quarter_grommet', [(0.0, 0.0), (0.024, 0.0), (0.024, 0.004), (0.019, 0.007), (0.0, 0.007)],
                      (XQ, -0.86, 0.80), (1, 0, 0), mt['polished'], segs=20))
    # footwell side wall under the dash
    # [integration r3] front end 1.10 -> 1.00 and x -0.668 -> -0.652: the r3 front clip's lower skin narrows to
    # |x| 0.648-0.656 at y 1.0-1.04 and turns in to 0.60 at y 1.08, so the old panel stood 1-2 cm out of the body
    # r6: the body's lower front corner now tucks in to |x| 0.61-0.65 below z 0.62 (y 0.65-0.95; 0.58 at y 1.0) and the
    # flat panel at |x| 0.652 stood up to 4 cm out of it: a grid whose face follows the skin 12 mm inside it, its bottom
    # edge resting on the tucked frame rail (centre |x| rail_in + 0.025, z 0.50, OD 50 mm) instead of reaching the floor
    L.append(build_footwell_side(mt))
    for o in L:
        S.append(mirror_x(o))
    S.extend(L)


def build_firewall(S, mt):
    y = spec.FIREWALL_Y
    X = 0.762
    fr = (V((0, y, 0)), V((-1, 0, 0)), V((0, 0, 1)))        # face normal +y (into the cabin)
    zl, zg, zo, zt = 0.975, 1.162, 1.228, 1.232
    # [integration r3] notch the outer bottom corners: the rear trailing arms (spec R_TRAILING_PIVOT, y -0.84) pass
    # through the firewall plane at |x| ~0.72, z ~0.50 (+0.04 at full bump)
    xn, zn = 0.665, 0.590
    S.append(slab('int_firewall_lower', [(-xn, FZ), (xn, FZ), (xn, zn), (X, zn), (X, zl), (-X, zl), (-X, zn), (-xn, zn)],
                  fr, 0.012, [mt['carbon'], mt['carbon']],
                  uv_front=lambda a, b: (a * CS, b * CS)))
    # grille windows (hex mesh) with carbon frame bars
    for sx in (-1, 1):
        xa, xb = sx * 0.035, sx * (X - 0.03)
        cx, w = (xa + xb) / 2, abs(xb - xa)
        m = quad('int_firewall_mesh', (V((cx, y - 0.006, (zl + zg) / 2)), V((-1, 0, 0)), V((0, 0, 1))), w, zg - zl,
                 mt['mesh'], uv=[(0, 0), (w / 0.36, 0), (w / 0.36, (zg - zl) / 0.36), (0, (zg - zl) / 0.36)])
        S.append(m)
    for (xa, xb) in ((-X, -X + 0.032), (-0.036, 0.036), (X - 0.032, X)):
        S.append(slab('int_firewall_bar', [(xa, zl - 0.005), (xb, zl - 0.005), (xb, zg + 0.005), (xa, zg + 0.005)],
                      (V((0, y + 0.012, 0)), V((-1, 0, 0)), V((0, 0, 1))), 0.026, [mt['carbon'], mt['carbon']],
                      bevel=0.003, segs=1, uv_front=lambda a, b: (a * CS, b * CS)))
    S.append(slab('int_firewall_sill', [(-X, zl - 0.012), (X, zl - 0.012), (X, zl + 0.006), (-X, zl + 0.006)],
                  (V((0, y + 0.014, 0)), V((-1, 0, 0)), V((0, 0, 1))), 0.028, [mt['carbon'], mt['carbon']],
                  bevel=0.004, segs=2, uv_front=lambda a, b: (a * CS, b * CS)))
    # orange striped band above the grille. r4: its outer top corners step in under the body's pod rim (inner face
    # |x| 0.757 @ z 1.19 .. 0.738 @ z 1.21-1.24 at the firewall)
    XO = 0.726
    band = [(-X, zg), (X, zg), (X, 1.180), (XO, 1.200), (XO, zo), (-XO, zo), (-XO, 1.200), (-X, 1.180)]
    S.append(slab('int_firewall_orange', band, (V((0, y + 0.012, 0)), V((-1, 0, 0)),
                  V((0, 0, 1))), 0.03, [mt['fw_orange'], mt['carbon']], bevel=0.004, segs=2,
                  uv_front=lambda a, b: ((X - a) / (2 * X), (b - zg) / 0.30 + 0.35)))
    # top strip (orange with black tears, livery_top atlas)
    top = slab('int_firewall_top', [(-0.53, y - 0.085), (0.53, y - 0.085), (0.53, y + 0.012), (-0.53, y + 0.012)],
               (V((0, 0, zt)), V((1, 0, 0)), V((0, 1, 0))), 0.008, [mt['livery_top'], mt['carbon']], bevel=0.003,
               segs=1, uv_front=lambda a, b: top_uv(V((a, b, zt)), V((0, 0, 1))))
    S.append(top)


# =====================================================================================================
#  CONTROLS, PEDALS, FLOOR
# =====================================================================================================

def build_controls(S, mt):
    # ---- sequential shifter on the console, right of the driver
    # r5 (interior_dash.png, interior_dash_alt_beige.png): a flat black-anodised gate lever - two 10 x 8 mm bars with a
    # 20 mm open slot between them (bars side by side fore-aft, the slot seen from the side), bridged at the top under a
    # black satin ball knob (dia 50 mm) on a 30 mm stem; it rises out of a recessed slot in the carbon console top
    # (r4: thin polished rods on a rubber plate)
    by = 0.30                   # rises right behind the stack base, beside the stereo (interior_dash.png)
    hb, ht, zt = console_dims(by)
    bx = -0.045
    # recessed slot: black opening in a thin black anodised trim ring, flush with the console top
    S.append(slab('int_shifter_slot_trim', rrect(0.034, 0.118, 0.012), (V((bx, by, zt + 0.0035)), V((1, 0, 0)),
                                                                         V((0, 1, 0))),
                  0.003, [mt['anod'], mt['anod']], bevel=0.0012, segs=1))
    S.append(slab('int_shifter_slot', rrect(0.020, 0.100, 0.008), (V((bx, by, zt + 0.0036)), V((1, 0, 0)), V((0, 1, 0))),
                  0.0004, [mt['hole'], mt['hole']]))
    lean = V((0.0, -0.13, 1.0)).normalized()
    p0 = V((bx, by, zt))
    top = p0 + lean * 0.205                # bridge top (r3: knob centre ~0.27 above the console)
    for dy in (-0.015, 0.015):
        a_ = p0 + V((0, dy, 0)) - lean * 0.02
        b_ = top + V((0, dy, 0)) - lean * 0.006
        d = (b_ - a_)
        o = box('int_shifter_bar', (0.008, 0.010, d.length), (0, 0, 0), material=mt['anod'], bevel=0.0015, segments=1)
        o.matrix_basis = aligned_matrix((a_ + b_) / 2, d)
        apply_transform(o)
        S.append(sharpen(o, 40))
    o = box('int_shifter_bridge', (0.008, 0.040, 0.014), (0, 0, 0), material=mt['anod'], bevel=0.003, segments=2)
    o.matrix_basis = aligned_matrix(top - lean * 0.007, lean)
    apply_transform(o)
    S.append(sharpen(o, 40))
    S.append(cyl_at('int_shifter_stem', 0.0080, 0.032, top - lean * 0.002, lean, mt['anod'], segs=14))
    kc = top + lean * (0.030 + 0.022)
    S.append(sharpen(sphere('int_shifter_knob', 0.025, tuple(kc), mt['horn'], segs=24, rings=14), 80))
    S.append(lathe_at('int_shifter_collar', [(0.0, 0.0), (0.011, 0.0), (0.011, 0.006), (0.0085, 0.009), (0.0, 0.009)],
                      kc - lean * 0.030, lean, mt['anod'], segs=16))

    # ---- two cutting-brake levers with black balls, rising from a low pivot box on the console's left flank and
    # leaning FORWARD (pulled back to brake): interior_dash.png balls ~(-0.10, 0.19, 0.68), behind the shifter.
    # r3: levers 48 mm apart, 0.255 / 0.222 long, the second ~12 deg more forward -> balls staggered, no overlap
    # (pivot / lean solved against the photo's ball centres with the camera of tools/render.py)
    cby = 0.04
    hb, ht, zt = console_dims(cby)
    cbx = -hb - 0.030                        # pivot axis just outboard of the console wall
    cbz = FZ + 0.035
    S.append(slab('int_cutbrake_box', rrect(0.070, 0.12, 0.008), (V((cbx + 0.006, cby, FZ + 0.046)), V((1, 0, 0)),
                                                                   V((0, 1, 0))),
                  0.045, [mt['anod'], mt['anod']], bevel=0.004, segs=1))
    S.append(slab('int_cutbrake_boot', rrect(0.054, 0.09, 0.008), (V((cbx + 0.006, cby, FZ + 0.0475)), V((1, 0, 0)),
                                                                    V((0, 1, 0))),
                  0.002, [mt['rubber'], mt['rubber']]))
    lean = lambda deg, tx: V((tx, math.sin(math.radians(deg)), math.cos(math.radians(deg))))
    for k, (dx, d, L) in enumerate(((-0.024, lean(41, 0.03), 0.255), (0.024, lean(47, 0.05), 0.222))):
        d = d.normalized()
        piv = V((cbx + dx, cby, cbz))
        # r5: flat 20 x 6 mm bars (photo), not round rods
        o = box('int_cutbrake_lever', (0.006, 0.020, L), (0, 0, 0), material=mt['polished'], bevel=0.0018, segments=1)
        o.matrix_basis = aligned_matrix(piv + d * (L / 2), d)
        apply_transform(o)
        S.append(sharpen(o, 40))
        S.append(sharpen(sphere('int_cutbrake_ball', 0.021, tuple(piv + d * (L + 0.012)), mt['gloss'], segs=20, rings=12), 80))
        S.append(cyl_at('int_cutbrake_pivot', 0.010, 0.014, piv - V((0.007, 0, 0)), (1, 0, 0), mt['alu'], segs=14))

    # ---- driver pedals (aluminium, perforated pads), dead pedal; passenger footrest
    def pad(name, c, w, h, n, up=(0, 0, 1)):
        fr = face_frame(c, n, up)
        return slab(name, rrect(w, h, 0.008), fr, 0.006, [mt['perf'], mt['alu']], bevel=0.0015, segs=1,
                    uv_front=lambda a, b: (a / 0.08, b / 0.08))

    # r3: pedals ~1.1 m ahead of the H-point (were 1.3 m), all above the raised floor; the pedal box hangs under the
    # dash at |x| >= 0.25 (the chassis upper pivot rail runs at |x| <= 0.20)
    PY = 0.850                  # r4: 6 cm further forward (with the floor +2.5 cm the pad bottoms showed under the dash)
    nb = V((0, -0.82, 0.57)).normalized()
    bc = V((-0.405, PY, 0.552 + DZF))
    S.append(pad('int_pedal_brake', tuple(bc), 0.078, 0.100, nb))
    piv = V((-0.405, PY + 0.09, 0.705 + DZF))
    arm = piv - (bc + nb * -0.006)
    o = box('int_pedal_brake_arm', (0.012, 0.026, arm.length), (0, 0, 0), material=mt['alu'], bevel=0.003, segments=1)
    o.matrix_basis = aligned_matrix((piv + bc) / 2 + nb * -0.012, arm)
    apply_transform(o)
    S.append(sharpen(o, 40))
    nt = V((0, -0.78, 0.62)).normalized()
    # r4: +3 cm (floor +2.5 cm): the pad's lower edge (y ~0.734) now sits on its hinge, above the mat
    tc = V((-0.265, PY + 0.005, 0.520 + DZF + 0.005))
    S.append(pad('int_pedal_throttle', tuple(tc), 0.070, 0.165, nt))
    S.append(cyl_at('int_pedal_throttle_hinge', 0.009, 0.06, (-0.295, PY - 0.048, FZ + 0.020), (1, 0, 0), mt['anod'],
                    segs=12))
    nd = V((0.35, -0.70, 0.62)).normalized()
    # r6: 7 cm inboard and 15 mm narrower: the frame rail / footwell side now tuck in to |x| 0.565 here
    S.append(pad('int_dead_pedal', (-0.512, PY + 0.012, 0.545 + DZF), 0.085, 0.20, nd))
    S.append(slab('int_pedal_box', rrect(0.29, 0.07, 0.01), (V((-0.395, PY + 0.09, 0.715 + DZF)), V((1, 0, 0)), V((0, 0, 1))),
                  0.06, [mt['anod'], mt['anod']], bevel=0.004, segs=1))
    for mx_ in (-0.44, -0.37):
        S.append(cyl_at('int_master_cyl', 0.014, 0.10, (mx_, PY + 0.15, 0.71 + DZF), (0, 1, 0.2), mt['alu'], segs=14))
    np_ = V((-0.45, -0.62, 0.64)).normalized()
    S.append(pad('int_pass_footrest', (0.175, 1.03, 0.555 + DZF), 0.10, 0.22, np_))
    S.append(box('int_pass_footrest_brace', (0.04, 0.10, 0.03), (0.185, 1.074, FZ + 0.03), material=mt['alu'], bevel=0.004))

    # ---- twin 12 V / USB socket box on the floor beside the console (driver side)
    ub = V((-0.19, 0.56, FZ + 0.055))
    S.append(slab('int_usb_box', rrect(0.11, 0.07, 0.006), (ub, V((0, -1, 0)), V((0, 0, 1))), 0.045,
                  [mt['black'], mt['black']], bevel=0.003, segs=1))
    for dz in (0.017, -0.017):
        c = ub + V((-0.0005, 0.0, dz))
        S.append(cyl_at('int_usb_socket', 0.0125, 0.004, c, (-1, 0, 0), mt['anod'], segs=16))
        S.append(cyl_at('int_usb_socket_in', 0.008, 0.0042, c, (-1, 0, 0), mt['hole'], segs=16))

    # ---- passenger floor grab handle (black powder-coated loop, interior_dash.png)
    hy = 0.735
    S.append(ttube('int_pass_grab', [(0.19, hy - 0.02, FZ + 0.006), (0.205, hy, FZ + 0.075), (0.53, hy, FZ + 0.075),
                                     (0.545, hy - 0.02, FZ + 0.006)], 0.0105, mt['black'], sides=12, bend=0.03))
    for x in (0.19, 0.545):
        S.append(slab('int_pass_grab_foot', rrect(0.05, 0.035, 0.008), (V((x, hy - 0.02, FZ + 0.005)), V((1, 0, 0)),
                                                                          V((0, 1, 0))), 0.004, [mt['black'], mt['black']]))


def build_floor(S, mt):
    def floor_mat(name, x0, x1, y0, y1, v0=0.0, v1=1.0):
        w, h = x1 - x0, y1 - y0
        xc, yc = (x0 + x1) / 2, (y0 + y1) / 2
        fr = (V((xc, yc, FZ + 0.007)), V((1, 0, 0)), V((0, 1, 0)))
        ol = rrect(w, h, 0.03)
        # r6: the outer edge stays 6 mm inside the chassis frame rail's inner face, which tucks in from |x| 0.675 at
        # y 0.40 to 0.586 at 0.70 and 0.544 at 1.10 (the mats ran 3-5 cm into the rail at y 0.65-0.80); the outline
        # is resampled every 2 cm so the clamp follows the curve (r4 front_taper only handled y > 1.035)
        sx = 1 if xc > 0 else -1
        dense = []
        for i in range(len(ol)):
            (a0, b0), (a1, b1) = ol[i], ol[(i + 1) % len(ol)]
            k = max(1, int(math.hypot(a1 - a0, b1 - b0) / 0.02))
            dense += [(a0 + (a1 - a0) * j / k, b0 + (b1 - b0) * j / k) for j in range(k)]
        ol = [(sx * min(sx * (u + xc), rail_in(v + yc) - 0.006) - xc, v) for u, v in dense]
        return slab(name, ol, fr, 0.006, [mt['mat'], mt['rubber']], bevel=0.0025, segs=1,
                    uv_front=lambda a, b: (a / w + 0.5, v0 + (b / h + 0.5) * (v1 - v0)))
    S.append(floor_mat('int_mat_driver', -0.615, -0.135, 0.12, 0.80))
    # r4: the front mats stop short of the chassis front floor rail (y 1.13-1.19, z FZ..FZ+0.05)
    S.append(floor_mat('int_mat_driver_front', -0.62, -0.135, 0.83, 1.115, 0.45, 0.95))
    S.append(floor_mat('int_mat_pass', 0.135, 0.615, 0.12, 0.72))
    S.append(floor_mat('int_mat_pass_front', 0.135, 0.62, 0.76, 1.115, 0.45, 0.95))
    # floor bolts (floor pan fasteners seen in the photo) beside the tunnel
    for x in (-0.12, 0.12):
        for y in (-0.05, 0.40, 0.85):
            S.append(lathe_at('int_floor_bolt', [(0.0, 0.0), (0.008, 0.0), (0.007, 0.003), (0.0, 0.004)], (x, y, FZ),
                              (0, 0, 1), mt['polished'], segs=10))
    # r3: small polished rivet heads along the edges of the (satin aluminium) floor pan: both sides along the
    # frame rails, across the front footwell wall and the rear firewall (one joined mesh)
    rivets = []
    pts = [(sx * min(0.652, rail_in(y) - 0.015), y) for sx in (-1, 1) for y in np.arange(-0.80, 1.06, 0.095)]
    pts += [(x, 1.119) for x in np.arange(-0.50, 0.51, 0.10) if abs(x) > 0.12]
    pts += [(x, spec.FIREWALL_Y + 0.020) for x in np.arange(-0.62, 0.63, 0.124) if abs(x) > 0.15]
    for (x, y) in pts:
        rivets.append(lathe('int_floor_rivet', [(0.0, 0.0), (0.0042, 0.0), (0.0036, 0.0013), (0.002, 0.0021),
                                                (0.0, 0.0024)], mt['polished'], segments=8, loc=(float(x), float(y), FZ)))
    S.append(join(rivets, 'int_floor_rivets'))


# =====================================================================================================
#  BUILD
# =====================================================================================================

def build(C):
    ensure_textures()
    mt = mats()
    S = []
    build_dash(S, mt)
    build_screens(S, mt)
    build_stack(S, mt)
    build_console(S, mt)
    wheel = build_steering(S, mt)
    build_controls(S, mt)
    build_floor(S, mt)
    for xc in (-SX, SX):
        build_seat(S, mt, xc)
        build_harness(S, mt, xc)
    card = build_door_card(mt)
    for o in card:
        S.append(mirror_x(o))
    S.extend(card)
    build_side_panels(S, mt)
    build_firewall(S, mt)
    for o in S + wheel:          # bmesh names its UV layer 'Float2'; the shared meshes use 'UVMap'
        me = o.data
        if len(me.uv_layers) and 'UVMap' not in me.uv_layers:
            me.uv_layers[0].name = 'UVMap'
    C.add(S, 'static')
    C.add(wheel, 'SteeringWheel')
