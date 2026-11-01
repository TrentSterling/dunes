"""Procedural texture generator for the GLX sandrail (PIL + numpy only, nothing downloaded).

    python textures/generate.py            # everything
    python textures/generate.py carbon livery   # selected groups

Writes the PNGs next to this file. See README.md for the list.
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from texlib import *  # noqa
import spec  # noqa

GROUPS = {}


def group(fn):
    GROUPS[fn.__name__] = fn
    return fn


# =========================================================================== carbon

# r4: neutral tow albedo ~21 / 39 sRGB (mean 30, +-9) so carbon reads as lit weave next to the #050505 gloss black
# vinyl (photo pod carbon 42-73 lit, blades ~5). 3x finer weave: 48 tows per 1024 px tile (21 px per tow); with
# M('carbon') tiling 6x per UV unit that is 3.5 mm tows at 1 UV unit / m (pod decks, coil cover), ~1.9 mm in the
# cockpit (CS 1.8). Roughness: glossy warp floats .22, satin weft floats .31, gaps up to .35 (mean ~.27).
CARBON_SRGB = (30.0, 30.0, 30.0)       # mean sRGB of the weave (0..255)
CARBON_CONTRAST = 9.0                  # +- levels between the bright and dark floats (5th..95th percentile)
CARBON_TOWS = 48                       # tows per 1024 px tile (multiple of 4 -> seamless 2x2 twill)
CARBON_ROUGH = (0.22, 0.31, 0.35)      # warp float / weft float / gap roughness


def carbon_rgb(lum, base=CARBON_SRGB, contrast=CARBON_CONTRAST):
    """Weave brightness factor (twill() lum, ~0.6..1.3) -> neutral sRGB float colour, mean `base`,
    5th..95th percentile spread +-`contrast` levels."""
    m = float(np.mean(lum)); lo, hi = np.percentile(lum, [5, 95])
    d = (lum - m) / max(1e-6, 0.5 * (hi - lo))                 # ~ -1 .. +1
    d = np.clip(d, -1.6, 1.4)
    b = np.asarray(base, np.float32)
    return np.clip((b[None, None, :] + contrast * d[..., None]) / 255.0, 0, 1)


def carbon_maps(N=1024, tows=CARBON_TOWS, seed=7):
    """Shared weave fields for carbon_base / carbon_normal / carbon_rough (seamless N x N, `tows` tows)."""
    y, x = np.mgrid[0:N, 0:N].astype(np.float32)
    u = (x + 0.5) / (N / tows)
    v = (N - y - 0.5) / (N / tows)          # +V up
    nfib = max(4, int(N / tows / 2))
    lum, hgt, warp = twill(u, v, seed=seed, tows=tows, nfib=nfib)
    return lum, hgt, warp, u, v


@group
def carbon():
    N = 1024
    tows = CARBON_TOWS
    lum, hgt, warp, u, v = carbon_maps(N, tows)
    cloud = fbm(N, N, 2, 33, octaves=3, tile=True)
    lum_c = lum * (0.97 + 0.06 * cloud)
    save(carbon_rgb(lum_c), 'carbon_base.png')
    # normal map: tow relief (rounded tows, float bulge, dark gaps sink). Height scaled with the tow size so the
    # per-tow slopes match the r3 map (16 tows: h * 8); M('carbon') uses normal_strength .3 on top of that.
    fine = fbm(N, N, 192, 44, octaves=1, tile=True)
    h = hgt * 8.0 * (16.0 / tows) + (fine - 0.5) * 0.10
    h = blur_wrap(h, 0.6)
    save(normal_from_height(h, strength=1.0), 'carbon_normal.png')
    # roughness: warp floats glossy, weft floats satin, gaps / float ends roughest
    fu, fv = u - np.floor(u), v - np.floor(v)
    k = (np.floor(u) + np.floor(v)).astype(np.int32) % 4
    acr = np.where(warp, fu, fv); alg = np.where(warp, k + fv, (k - 2) + fu)      # across / along the top float
    gap = 1.0 - np.minimum(smoothstep(0.0, 0.10, np.minimum(acr, 1 - acr)),
                           smoothstep(0.0, 0.06, np.minimum(alg, 2 - alg)))
    rw, rf, rg = CARBON_ROUGH
    rough = np.where(warp, rw, rf) + (rg - np.where(warp, rw, rf)) * gap
    rough = rough * (0.95 + 0.10 * cloud)
    save(Image.fromarray((np.clip(rough, 0, 1) * 255 + 0.5).astype(np.uint8), 'L'), 'carbon_rough.png')
    print('  carbon_base mean sRGB %.1f, rough mean %.3f' % (carbon_rgb(lum_c).mean() * 255, rough.mean()))


# r6: interior carbon (M('carbon_interior'), dash / console / door tops): the same 48-tow weave as carbon_base.png
# (same fields, seed and cloud, so carbon_normal.png and carbon_rough.png line up with it) in a deeper black with
# ~45 % less albedo contrast: tows ~19 / 29 sRGB (carbon_base.png 21 / 39). The weave then shows mainly in the
# highlights through the shared normal map, like the gloss dash carbon in interior_dash.png.
CARBON_INT_SRGB = (24.0, 24.0, 24.6)
CARBON_INT_CONTRAST = 5.0


@group
def carbon_interior():
    N = 1024
    lum, hgt, warp, u, v = carbon_maps(N, CARBON_TOWS)
    cloud = fbm(N, N, 2, 33, octaves=3, tile=True)
    lum_c = lum * (0.97 + 0.06 * cloud)
    rgb = carbon_rgb(lum_c, base=CARBON_INT_SRGB, contrast=CARBON_INT_CONTRAST)
    save(rgb, 'carbon_interior.png')
    lo, hi = np.percentile(rgb[..., 0] * 255, [5, 95])
    print('  carbon_interior mean sRGB %.1f, tows p5/p95 %.1f / %.1f' % (rgb.mean() * 255, lo, hi))


@group
def livery():
    import livery_paint
    im, rough = livery_paint.make_livery()
    save(im, 'livery.png')
    save(rough, 'livery_rough.png')


@group
def livery_top():
    import livery_paint
    im, rough = livery_paint.make_livery_top()
    save(im, 'livery_top.png')
    save(rough, 'livery_top_rough.png')


@group
def hex_mesh():
    import interior_paint as ip
    save(ip.make_hex_mesh(), 'hex_mesh.png')


@group
def floor_mat():
    import interior_paint as ip
    c, n = ip.make_floor_mat()
    save(c, 'floor_mat.png'); save(n, 'floor_mat_normal.png')


@group
def door_quilt():
    import interior_paint as ip
    c, n = ip.make_door_quilt()
    save(c, 'door_quilt.png'); save(n, 'door_quilt_normal.png')


@group
def seat():
    import interior_paint as ip
    save(ip.make_seat_suede(), 'seat_suede.png')
    save(ip.make_seat_logo(), 'seat_logo.png')
    save(ip.make_stitch_diamond(), 'stitch_diamond.png')


@group
def firewall():
    import interior_paint as ip
    save(ip.make_firewall_orange(), 'firewall_orange.png')


@group
def screens():
    import gauges_paint as gp
    save(gp.make_screen_lowrance(), 'screen_lowrance.png')
    save(gp.make_screen_dash(), 'screen_dash.png')
    save(gp.make_screen_radio(), 'screen_radio.png')
    save(gp.make_switch_panel(), 'switch_panel.png')
    save(gp.make_placard_pci(), 'placard_pci.png')


@group
def lights():
    import gauges_paint as gp
    save(gp.make_light_bar_face(), 'light_bar_face.png')
    save(gp.make_led_pod_face(), 'led_pod_face.png')


@group
def tires():
    import gauges_paint as gp
    for kind in ('front', 'rear'):
        c, n = gp.make_tire_sidewall(kind)
        save(c, 'tire_%s_sidewall.png' % kind)
        save(n, 'tire_%s_sidewall_normal.png' % kind)


if __name__ == '__main__':
    names = sys.argv[1:] or list(GROUPS)
    for n in names:
        print('==', n)
        GROUPS[n]()
