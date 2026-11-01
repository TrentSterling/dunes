"""Screens, switch panel, intercom placard, LED faces and tyre sidewall strips."""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from texlib import *  # noqa

SS = 2   # supersampling for vector drawing


def canvas(W, H, color=(0, 0, 0)):
    im = Image.new('RGB', (W * SS, H * SS), color)
    return im, ImageDraw.Draw(im)


def fin(im, W, H):
    return im.resize((W, H), Image.LANCZOS)


def F(name, px):
    return font(name, int(px * SS))


def text(d, xy, s, fnt, fill, anchor='la'):
    d.text((xy[0] * SS, xy[1] * SS), s, font=fnt, fill=fill, anchor=anchor)


def rect(d, box, fill=None, outline=None, width=1, radius=0):
    b = [v * SS for v in box]
    if radius:
        d.rounded_rectangle(b, radius=radius * SS, fill=fill, outline=outline, width=width * SS)
    else:
        d.rectangle(b, fill=fill, outline=outline, width=width * SS)


def glow(im, radius=6, amount=0.6):
    """Add a soft bloom of the bright parts (screens look lit)."""
    a = np.asarray(im).astype(np.float32) / 255
    b = blur(a, radius * SS)
    return Image.fromarray((np.clip(a + b * amount, 0, 1) * 255).astype(np.uint8))


# --------------------------------------------------------------------------- race dash

def make_screen_dash(W=1024, H=512):
    im, d = canvas(W, H, (3, 4, 6))
    # shift-light / tach bar
    rpm, rmax = 5600, 8000
    x0, x1, y0, y1 = 40, 984, 34, 92
    n = 40
    for i in range(n):
        xa = x0 + (x1 - x0) * i / n + 2; xb = x0 + (x1 - x0) * (i + 1) / n - 2
        frac = (i + 0.5) / n
        c = (40, 220, 70) if frac < 0.6 else (250, 210, 30) if frac < 0.82 else (255, 40, 30)
        lit = frac * rmax <= rpm
        hh = y1 - (y1 - y0) * (0.45 + 0.55 * frac)
        if lit:
            rect(d, (xa, hh, xb, y1), fill=c)
        else:
            rect(d, (xa, hh, xb, y1), fill=tuple(int(v * 0.14) for v in c))
    f_s = F('DejaVuSansMono-Bold.ttf', 18)
    for k in range(0, 9):
        x = x0 + (x1 - x0) * k * 1000 / rmax
        text(d, (x, 98), str(k), f_s, (150, 155, 160), 'ma')
    rect(d, (30, 128, 994, 130), fill=(60, 62, 66))
    # gear
    rect(d, (412, 140, 612, 382), outline=(255, 90, 13), width=4, radius=14)
    text(d, (512, 262), '3', F('Inter-ExtraBold.otf', 230), (255, 255, 255), 'mm')
    text(d, (512, 150), 'GEAR', F('DejaVuSans-Bold.ttf', 18), (255, 140, 60), 'ma')
    # speed + rpm
    text(d, (60, 150), 'SPEED', F('DejaVuSans-Bold.ttf', 20), (150, 155, 160))
    text(d, (380, 300), '68', F('Inter-ExtraBold.otf', 150), (255, 255, 255), 'rs')
    text(d, (382, 330), 'MPH', F('DejaVuSans-Bold.ttf', 24), (150, 155, 160), 'ra')
    text(d, (650, 150), 'RPM', F('DejaVuSans-Bold.ttf', 20), (150, 155, 160))
    text(d, (970, 300), '5640', F('Inter-ExtraBold.otf', 120), (255, 255, 255), 'rs')
    text(d, (970, 330), 'BOOST 14.2 PSI', F('DejaVuSans-Bold.ttf', 24), (255, 140, 60), 'ra')
    # bottom data tiles
    tiles = [('WATER', '196', '°F'), ('OIL P', '64', 'PSI'), ('OIL T', '228', '°F'),
             ('FUEL', '74', '%'), ('TRANS', '181', '°F'), ('VOLTS', '14.1', 'V')]
    tw = (994 - 30) / 6
    for i, (lab, val, unit) in enumerate(tiles):
        xa = 30 + i * tw + 4; xb = 30 + (i + 1) * tw - 4
        rect(d, (xa, 396, xb, 492), fill=(14, 16, 20), outline=(48, 52, 58), width=2, radius=8)
        text(d, (xa + 12, 404), lab, F('DejaVuSans-Bold.ttf', 17), (150, 155, 160))
        text(d, (xb - 12, 482), val, F('Inter-ExtraBold.otf', 46), (255, 255, 255) if lab != 'FUEL' else (120, 230, 120), 'rs')
        text(d, (xa + 12, 482), unit, F('DejaVuSans-Bold.ttf', 15), (120, 125, 130), 'ls')
    # warning lights
    for i, c in enumerate([(40, 200, 255), (20, 60, 20), (60, 20, 10)]):
        d.ellipse([(46 + 34 * i) * SS, 352 * SS, (70 + 34 * i) * SS, 376 * SS], fill=c)
    im = glow(im, 5, 0.45)
    return fin(im, W, H)


# --------------------------------------------------------------------------- DuneNav

def make_screen_lowrance(W=1024, H=640):
    im, d = canvas(W, H, (0, 0, 0))
    mapw = 640
    # terrain: dune field in tan with shading
    Hm, Wm = (H - 40 - 44) * SS, mapw * SS
    n1 = fbm(Hm, Wm, 6, 301, octaves=4)
    n2 = fbm(Hm, Wm, 18, 302, octaves=3, aspect=0.5)
    elev = n1 * 0.75 + n2 * 0.25
    gy, gx = np.gradient(elev)
    shade = np.clip(0.86 + (gx - gy) * 55, 0.62, 1.10)
    base = np.array([214, 186, 140], np.float32) / 255
    terr = base[None, None, :] * shade[..., None]
    # contour lines
    cl = np.abs(((elev * 24) % 1.0) - 0.5)
    lines = smoothstep(0.44, 0.49, cl)
    terr = terr * (1 - 0.35 * lines[..., None])
    timg = Image.fromarray((np.clip(terr, 0, 1) * 255).astype(np.uint8))
    im.paste(timg, (0, 40 * SS))
    # trails (dashed grey) and the recorded track (blue) + vehicle arrow
    r = rng(303)
    for k in range(6):
        pts = []
        x, y = r.uniform(0, mapw), r.uniform(40, H - 44)
        ang = r.uniform(0, 2 * math.pi)
        for s in range(40):
            ang += r.normal(0, 0.18); x += math.cos(ang) * 18; y += math.sin(ang) * 18
            pts.append((x * SS, y * SS))
        d.line(pts, fill=(120, 100, 80), width=3 * SS)
    track = []
    x, y, ang = 120, H - 80, -0.9
    for s in range(55):
        ang += math.sin(s * 0.35) * 0.12; x += math.cos(ang) * 9; y += math.sin(ang) * 9
        track.append((x * SS, y * SS))
    d.line(track, fill=(20, 80, 230), width=5 * SS)
    ex, ey = track[-1]
    a = ang
    tri = [(ex + math.cos(a) * 26 * SS, ey + math.sin(a) * 26 * SS),
           (ex + math.cos(a + 2.5) * 16 * SS, ey + math.sin(a + 2.5) * 16 * SS),
           (ex + math.cos(a - 2.5) * 16 * SS, ey + math.sin(a - 2.5) * 16 * SS)]
    d.polygon(tri, fill=(0, 0, 0), outline=(255, 255, 255))
    # waypoints
    for (wx, wy, name) in ((470, 160, 'OLDS HILL'), (300, 300, 'COMP HILL'), (540, 470, 'CAMP')):
        d.ellipse([(wx - 8) * SS, (wy - 8) * SS, (wx + 8) * SS, (wy + 8) * SS], fill=(230, 30, 30), outline=(255, 255, 255), width=2 * SS)
        text(d, (wx + 12, wy - 10), name, F('DejaVuSans-Bold.ttf', 16), (20, 20, 20))
    # scale + north
    rect(d, (16, H - 84, 136, H - 78), fill=(0, 0, 0))
    text(d, (16, H - 104), '0.25 mi', F('DejaVuSans-Bold.ttf', 15), (20, 20, 20))
    d.polygon([((mapw - 40) * SS, 60 * SS), ((mapw - 50) * SS, 90 * SS), ((mapw - 30) * SS, 90 * SS)], fill=(200, 30, 30))
    text(d, (mapw - 40, 94), 'N', F('DejaVuSans-Bold.ttf', 16), (20, 20, 20), 'ma')
    # right data panel
    rect(d, (mapw, 40, W, H - 44), fill=(10, 14, 22))
    items = [('SPEED', '42.6', 'mph'), ('HEADING', '287°', 'M'), ('ODOMETER', '18.4', 'mi'), ('ELEVATION', '322', 'ft')]
    yy = 54
    for lab, val, unit in items:
        rect(d, (mapw + 10, yy, W - 10, yy + 112), fill=(18, 24, 36), radius=6)
        text(d, (mapw + 22, yy + 8), lab, F('DejaVuSans-Bold.ttf', 18), (140, 170, 210))
        text(d, (W - 70, yy + 100), val, F('Inter-ExtraBold.otf', 62), (255, 255, 255), 'rs')
        text(d, (W - 22, yy + 100), unit, F('DejaVuSans-Bold.ttf', 18), (140, 170, 210), 'rs')
        yy += 120
    text(d, (mapw + 22, H - 60), "N 32°58.214'  W 115°04.937'", F('DejaVuSansMono-Bold.ttf', 17), (230, 230, 230))
    # top status bar and bottom soft keys
    rect(d, (0, 0, W, 40), fill=(22, 24, 28))
    text(d, (14, 8), 'DUNENAV', F('DejaVuSans-Bold.ttf', 22), (255, 255, 255))
    text(d, (W - 14, 8), '14:32', F('DejaVuSans-Bold.ttf', 22), (255, 255, 255), 'ra')
    text(d, (W // 2, 8), 'Chart  |  GLAMIS DUNES', F('DejaVuSans.ttf', 20), (200, 205, 210), 'ma')
    rect(d, (0, H - 44, W, H), fill=(22, 24, 28))
    for i, lab in enumerate(['HOME', 'CHART', 'NAV', 'WAYPTS', 'TRACKS', 'MENU']):
        cx = (i + 0.5) * W / 6
        text(d, (cx, H - 34), lab, F('DejaVuSans-Bold.ttf', 18), (210, 215, 220), 'ma')
    im = glow(im, 4, 0.25)
    return fin(im, W, H)


# --------------------------------------------------------------------------- radio

def make_screen_radio(W=512, H=256):
    im, d = canvas(W, H, (4, 8, 14))
    text(d, (20, 14), 'FM1', F('DejaVuSans-Bold.ttf', 30), (255, 140, 40))
    text(d, (W - 20, 14), '12:45', F('DejaVuSans-Bold.ttf', 30), (220, 230, 240), 'ra')
    text(d, (W // 2, 128), '101.5', F('Inter-ExtraBold.otf', 104), (240, 245, 255), 'mm')
    text(d, (W // 2, 192), 'KDNE  GLAMIS', F('DejaVuSans-Bold.ttf', 26), (180, 200, 220), 'mm')
    for i in range(16):
        h = 8 + i * 1.6
        c = (255, 120, 30) if i < 11 else (60, 50, 40)
        rect(d, (20 + i * 12, 240 - h, 28 + i * 12, 240), fill=c)
    text(d, (W - 20, 240), 'VOL 22', F('DejaVuSans-Bold.ttf', 22), (220, 230, 240), 'rs')
    im = glow(im, 4, 0.35)
    return fin(im, W, H)


# --------------------------------------------------------------------------- switch panel

def _icon(d, kind, cx, cy, s, c):
    """Simple vector icons (s = half size, in final pixels)."""
    S = SS
    def L(pts, w=3):
        d.line([(x * S, y * S) for x, y in pts], fill=c, width=int(w * S), joint='curve')
    def E(x0, y0, x1, y1, w=3, fill=None):
        d.ellipse([x0 * S, y0 * S, x1 * S, y1 * S], outline=c, width=int(w * S), fill=fill)
    if kind == 'lightbar':
        d.rounded_rectangle([(cx - s) * S, (cy - s * 0.25) * S, (cx + s) * S, (cy + s * 0.15) * S], radius=3 * S, outline=c, width=3 * S)
        for k in (-0.7, 0, 0.7):
            L([(cx + k * s, cy - s * 0.4), (cx + k * s * 1.3, cy - s)])
    elif kind == 'spot':
        d.pieslice([(cx - s * 0.9) * S, (cy - s * 0.7) * S, (cx + s * 0.5) * S, (cy + s * 0.7) * S], 90, 270, outline=c, width=3 * S)
        for k in (-0.5, 0, 0.5):
            L([(cx + s * 0.1, cy + k * s), (cx + s, cy + k * s * 1.3)])
    elif kind == 'fan':
        E(cx - s * 0.2, cy - s * 0.2, cx + s * 0.2, cy + s * 0.2, fill=c)
        for k in range(3):
            a = k * 2 * math.pi / 3
            d.chord([(cx + math.cos(a) * s * 0.55 - s * 0.45) * S, (cy + math.sin(a) * s * 0.55 - s * 0.45) * S,
                     (cx + math.cos(a) * s * 0.55 + s * 0.45) * S, (cy + math.sin(a) * s * 0.55 + s * 0.45) * S],
                    math.degrees(a) + 60, math.degrees(a) + 240, fill=c)
    elif kind == 'horn':
        d.polygon([((cx - s) * S, (cy - s * 0.3) * S), ((cx - s * 0.3) * S, (cy - s * 0.3) * S), ((cx + s * 0.6) * S, (cy - s) * S),
                   ((cx + s * 0.6) * S, (cy + s) * S), ((cx - s * 0.3) * S, (cy + s * 0.3) * S), ((cx - s) * S, (cy + s * 0.3) * S)], outline=c, width=3 * S)
        L([(cx + s * 0.85, cy - s * 0.5), (cx + s * 1.0, cy - s * 0.7)]); L([(cx + s * 0.85, cy + s * 0.5), (cx + s * 1.0, cy + s * 0.7)])
    elif kind == 'pump':
        d.rounded_rectangle([(cx - s * 0.6) * S, (cy - s * 0.8) * S, (cx + s * 0.4) * S, (cy + s) * S], radius=3 * S, outline=c, width=3 * S)
        L([(cx + s * 0.4, cy - s * 0.4), (cx + s * 0.9, cy - s * 0.1), (cx + s * 0.9, cy + s * 0.6)])
        d.rectangle([(cx - s * 0.4) * S, (cy - s * 0.6) * S, (cx + s * 0.2) * S, (cy - s * 0.15) * S], fill=c)
    elif kind == 'camera':
        d.rounded_rectangle([(cx - s) * S, (cy - s * 0.55) * S, (cx + s) * S, (cy + s * 0.7) * S], radius=4 * S, outline=c, width=3 * S)
        E(cx - s * 0.4, cy - s * 0.35, cx + s * 0.4, cy + s * 0.45)
    elif kind == 'beacon':
        d.polygon([(cx * S, (cy - s) * S), ((cx + s) * S, (cy + s * 0.8) * S), ((cx - s) * S, (cy + s * 0.8) * S)], outline=c, width=3 * S)
        L([(cx, cy - s * 0.3), (cx, cy + s * 0.25)]); E(cx - 2, cy + s * 0.45, cx + 2, cy + s * 0.55, fill=c)
    elif kind == 'whip':
        L([(cx, cy + s), (cx, cy - s)], 4)
        E(cx - s * 0.5, cy - s * 0.6, cx + s * 0.5, cy + s * 0.1, w=2)
        E(cx - s * 0.9, cy - s * 0.95, cx + s * 0.9, cy + s * 0.45, w=2)
    elif kind == 'rock':
        d.polygon([((cx - s) * S, (cy + s * 0.6) * S), ((cx - s * 0.3) * S, (cy - s * 0.5) * S), ((cx + s * 0.2) * S, (cy + s * 0.1) * S),
                   ((cx + s * 0.5) * S, (cy - s * 0.2) * S), ((cx + s) * S, (cy + s * 0.6) * S)], outline=c, width=3 * S)
    elif kind == 'headset':
        d.arc([(cx - s * 0.8) * S, (cy - s) * S, (cx + s * 0.8) * S, (cy + s * 0.6) * S], 180, 360, fill=c, width=3 * S)
        d.rounded_rectangle([(cx - s * 0.95) * S, (cy - s * 0.15) * S, (cx - s * 0.5) * S, (cy + s * 0.6) * S], radius=3 * S, fill=c)
        d.rounded_rectangle([(cx + s * 0.5) * S, (cy - s * 0.15) * S, (cx + s * 0.95) * S, (cy + s * 0.6) * S], radius=3 * S, fill=c)
    elif kind == 'power':
        d.arc([(cx - s * 0.8) * S, (cy - s * 0.7) * S, (cx + s * 0.8) * S, (cy + s * 0.9) * S], 300, 240, fill=c, width=3 * S)
        L([(cx, cy - s), (cx, cy + s * 0.1)])
    else:  # text label icon
        text(d, (cx, cy), kind, F('DejaVuSans-Bold.ttf', s * 0.9), c, 'mm')


def make_switch_panel(W=1024, H=512):
    """2 rows x 6 backlit keys (sPOD style keys like interior_dash.png, rocker layout per spec)."""
    im, d = canvas(W, H, (6, 6, 7))
    keys = [('lightbar', 'LIGHT BAR'), ('spot', 'PODS'), ('whip', 'WHIPS'), ('rock', 'ROCK LT'), ('beacon', 'HAZARD'), ('camera', 'CAMERA'),
            ('fan', 'FAN'), ('pump', 'FUEL PMP'), ('horn', 'HORN'), ('headset', 'INTERCOM'), ('AUX', 'AUX 1'), ('power', 'MAIN')]
    mx, my = 30, 30
    kw = (W - 2 * mx) / 6; kh = (H - 2 * my) / 2
    for i, (icon, lab) in enumerate(keys):
        r, c = divmod(i, 6)
        x0 = mx + c * kw + 8; y0 = my + r * kh + 8; x1 = x0 + kw - 16; y1 = y0 + kh - 16
        lit_orange = (i == 0)
        face = (34, 20, 10) if lit_orange else (20, 21, 24)
        rect(d, (x0, y0, x1, y1), fill=(2, 2, 3), radius=18)
        rect(d, (x0 + 4, y0 + 4, x1 - 4, y1 - 4), fill=face, radius=15)
        rect(d, (x0 + 6, y0 + 6, x1 - 6, (y0 + y1) / 2), fill=tuple(min(255, v + 6) for v in face), radius=13)
        ic = (255, 120, 30) if lit_orange else ((120, 190, 255) if i % 3 else (235, 240, 255))
        _icon(d, icon, (x0 + x1) / 2, (y0 + y1) / 2 - 18, 34, ic)
        text(d, ((x0 + x1) / 2, y1 - 22), lab, F('DejaVuSans-Bold.ttf', 17), (200, 205, 215), 'mm')
        # status LED
        d.ellipse([((x1 - 22) * SS), ((y0 + 12) * SS), ((x1 - 12) * SS), ((y0 + 22) * SS)],
                  fill=(255, 110, 20) if lit_orange else (40, 140, 255) if i in (1, 9, 11) else (25, 28, 32))
    im = glow(im, 5, 0.35)
    return fin(im, W, H)


# --------------------------------------------------------------------------- DCX placard

def make_placard_pci(W=512, H=256):
    Wc, Hc = W * SS, H * SS
    grain = fbm(Hc, Wc, 2, 401, octaves=4, aspect=0.03)
    yy, xx = np.mgrid[0:Hc, 0:Wc].astype(np.float32)
    base = 0.70 + 0.12 * (grain - 0.5) + 0.05 * (xx / Wc - 0.5)
    edge = np.minimum(np.minimum(xx, Wc - xx), np.minimum(yy, Hc - yy)) / SS
    base = base * (0.75 + 0.25 * smoothstep(0, 6, edge)) + 0.12 * (smoothstep(0, 3, edge) - smoothstep(3, 6, edge))
    rgb = np.stack([base * 0.97, base * 0.98, base], -1)
    im = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    # screws
    for (x, y) in ((18, 18), (W - 18, 18), (18, H - 18), (W - 18, H - 18)):
        d.ellipse([(x - 9) * SS, (y - 9) * SS, (x + 9) * SS, (y + 9) * SS], fill=(150, 152, 156), outline=(70, 72, 76), width=2 * SS)
        d.line([((x - 6) * SS, y * SS), ((x + 6) * SS, y * SS)], fill=(60, 62, 66), width=2 * SS)
        d.line([(x * SS, (y - 6) * SS), (x * SS, (y + 6) * SS)], fill=(60, 62, 66), width=2 * SS)
    # logo
    text(d, (W / 2 - 6, 24), 'DCX', F('Inter-BlackItalic.otf', 44), (20, 22, 26), 'ma')
    text(d, (W / 2 + 74, 40), 'DUNE COMMS', F('DejaVuSans-Bold.ttf', 13), (30, 60, 140), 'la')
    d.arc([(W / 2 - 70) * SS, 20 * SS, (W / 2 + 60) * SS, 82 * SS], 200, 330, fill=(30, 60, 140), width=3 * SS)
    # knobs
    for (x, lab) in ((140, 'VOLUME'), (372, 'SQUELCH')):
        y = 150
        d.ellipse([(x - 46) * SS, (y - 46) * SS, (x + 46) * SS, (y + 46) * SS], fill=(40, 42, 46))
        for k in range(36):
            a = k * 2 * math.pi / 36
            d.line([((x + math.cos(a) * 40) * SS, (y + math.sin(a) * 40) * SS), ((x + math.cos(a) * 46) * SS, (y + math.sin(a) * 46) * SS)],
                   fill=(70, 72, 78), width=2 * SS)
        d.ellipse([(x - 34) * SS, (y - 34) * SS, (x + 34) * SS, (y + 34) * SS], fill=(18, 18, 20))
        d.ellipse([(x - 26) * SS, (y - 30) * SS, (x + 22) * SS, (y + 4) * SS], fill=(48, 50, 56))
        d.line([(x * SS, (y - 30) * SS), (x * SS, (y - 12) * SS)], fill=(235, 235, 235), width=4 * SS)
        text(d, (x, 206), lab, F('DejaVuSans-Bold.ttf', 15), (25, 27, 30), 'ma')
        for k in range(9):
            a = math.radians(135 + k * 270 / 8)
            d.line([((x + math.cos(a) * 52) * SS, (y + math.sin(a) * 52) * SS), ((x + math.cos(a) * 58) * SS, (y + math.sin(a) * 58) * SS)],
                   fill=(25, 27, 30), width=2 * SS)
    # blue button
    rect(d, (236, 128, 276, 168), fill=(20, 110, 220), outline=(10, 40, 90), width=2, radius=6)
    rect(d, (240, 131, 272, 145), fill=(80, 160, 250), radius=5)
    text(d, (256, 176), 'PTT', F('DejaVuSans-Bold.ttf', 14), (25, 27, 30), 'ma')
    text(d, (W / 2, H - 30), 'INTERCOM  •  RADIO  •  ' + 'TX/RX', F('DejaVuSans.ttf', 13), (40, 42, 46), 'ma')
    return fin(im, W, H)


# --------------------------------------------------------------------------- LED faces

def make_light_bar_face(W=2048, H=128, face_aspect=1.005 / 0.046):
    """RC dual-row LED bar face. Drawn for a face of `face_aspect` (width/height) mapped to UV 0..1,
    so the round reflector cups stay round on the model (chassis.py light bar: 1.005 x 0.046 m)."""
    Wc, Hc = W * SS, H * SS
    kx = (W / H) / face_aspect          # horizontal pixel squeeze so circles stay round on the model
    yy, xx = np.mgrid[0:Hc, 0:Wc].astype(np.float32) + 0.5
    img = np.zeros((Hc, Wc, 3), np.float32) + col((12, 12, 13))
    # bezel highlight lines
    img = over(img, col((40, 41, 44)), (smoothstep(0, 3, yy) - smoothstep(4, 8, yy)) * 0.8)
    img = over(img, col((30, 31, 33)), (smoothstep(Hc - 9, Hc - 5, yy) - smoothstep(Hc - 3, Hc, yy)) * 0.8)
    rows = (Hc * 0.30, Hc * 0.70)
    rcup = Hc * 0.19
    pitch_y = rcup * 2.25
    pitch = pitch_y * kx
    badge_w = Hc * 2.2 * kx           # gap in the middle for the RC badge
    n_side = int((Wc / 2 - badge_w / 2 - pitch * 0.4) / pitch)
    centers = []
    for side in (-1, 1):
        for i in range(n_side):
            cx = Wc / 2 + side * (badge_w / 2 + pitch * (i + 0.6))
            for ry in rows:
                centers.append((cx, ry))
    cup = np.zeros((Hc, Wc), np.float32); led = np.zeros((Hc, Wc), np.float32); ring = np.zeros((Hc, Wc), np.float32)
    for (cx, cy) in centers:
        x0 = int(cx - rcup * kx - 3); x1 = int(cx + rcup * kx + 3)
        sl = slice(max(0, x0), min(Wc, x1))
        dx = (xx[:, sl] - cx) / kx; dy = yy[:, sl] - cy
        r = np.sqrt(dx * dx + dy * dy) / rcup
        cup[:, sl] = np.maximum(cup[:, sl], 1 - smoothstep(0.95, 1.0, r))
        # faceted reflector: brightness by angle and radius
        ring[:, sl] = np.maximum(ring[:, sl], (1 - smoothstep(0.95, 1.0, r)) * (0.45 + 0.35 * np.cos(np.arctan2(dy, dx) * 8) ** 2 * r))
        led[:, sl] = np.maximum(led[:, sl], 1 - smoothstep(0.22, 0.30, r))
    img = over(img, col((112, 115, 120)) * ring[..., None] / np.maximum(ring.max(), 1e-3), cup)
    img = over(img, col((255, 250, 235)), led)
    # RC badge in the centre top
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    bx0, bx1 = Wc / 2 - badge_w / 2 + 4, Wc / 2 + badge_w / 2 - 4
    d.rounded_rectangle([bx0, Hc * 0.10, bx1, Hc * 0.90], radius=int(Hc * 0.08), fill=(18, 18, 20), outline=(60, 62, 66), width=SS)
    f = font('Inter-BlackItalic.otf', int(Hc * 0.42))
    # draw the letters squeezed so they read right on the stretched face
    tmp = Image.new('L', (int(Hc * 1.6), int(Hc * 0.6)), 0)
    ImageDraw.Draw(tmp).text((tmp.width / 2, tmp.height / 2), 'RC', font=f, fill=255, anchor='mm')
    tmp = tmp.resize((max(1, int(tmp.width * kx)), tmp.height), Image.LANCZOS)
    im.paste((225, 228, 232), (int(Wc / 2 - tmp.width / 2), int(Hc * 0.12)), tmp)
    return fin(im, W, H)


def make_led_pod_face(N=512, face_aspect=2.0):
    """Dual round LED reflector pod face (front bumper lights, front.png). Drawn for a face of
    `face_aspect` (width/height) mapped to UV 0..1 on both axes, so the cups look round on the model."""
    Wc = Hc = N * SS
    kx = 1.0 / face_aspect
    yy, xx = np.mgrid[0:Hc, 0:Wc].astype(np.float32) + 0.5
    img = np.zeros((Hc, Wc, 3), np.float32) + col((14, 14, 15))
    # housing bezel
    ex = np.minimum(xx, Wc - xx) * kx; ey = np.minimum(yy, Hc - yy)
    e = np.minimum(ex, ey) / Hc
    img = over(img, col((48, 49, 52)), (smoothstep(0.0, 0.015, e) - smoothstep(0.03, 0.05, e)) * 0.8)
    for cxn in (0.27, 0.73):
        cx, cy = cxn * Wc, 0.5 * Hc
        dx = (xx - cx) / kx; dy = yy - cy
        r = np.sqrt(dx * dx + dy * dy) / (Hc * 0.40)
        a = np.arctan2(dy, dx)
        inside = 1 - smoothstep(0.97, 1.0, r)
        # chrome ring + faceted reflector + lens sparkle
        facet = 0.55 + 0.35 * np.abs(np.cos(a * 6)) * (0.4 + 0.6 * r)
        img = over(img, col((200, 204, 210)) * facet[..., None], inside)
        img = over(img, col((235, 237, 240)), (smoothstep(0.86, 0.9, r) - smoothstep(0.95, 0.98, r)) * 0.9)
        # LED emitters (cluster of 3) in the centre
        for k in range(3):
            ang = k * 2 * math.pi / 3 + 0.5
            ex_, ey_ = cx + math.cos(ang) * Hc * 0.07 * kx, cy + math.sin(ang) * Hc * 0.07
            rr = np.sqrt(((xx - ex_) / kx) ** 2 + (yy - ey_) ** 2) / (Hc * 0.045)
            img = over(img, col((255, 248, 220)), 1 - smoothstep(0.8, 1.0, rr))
        img = over(img, col((40, 40, 42)), (1 - smoothstep(0.10, 0.12, r)) * 0.0)
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((N, N), Image.LANCZOS)


# --------------------------------------------------------------------------- tyre sidewalls

def _text_strip(W, H, items):
    """Raised-lettering mask. items = (u_left 0..1, u_width 0..1, text, font file, cap height frac, v_center).
    Each text is fitted to its width box (font size limited by the cap height)."""
    m = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(m)
    for ul, uw, s, fname, frac, vc in items:
        size = int(H * frac)
        f = font(fname, size)
        bb = d.textbbox((0, 0), s, font=f)
        tw = bb[2] - bb[0]
        if tw > uw * W:
            size = int(size * uw * W / tw)
            f = font(fname, size)
            bb = d.textbbox((0, 0), s, font=f)
            tw = bb[2] - bb[0]
        x = ul * W + (uw * W - tw) / 2 - bb[0]
        d.text((x, (1 - vc) * H), s, font=f, fill=255, anchor='lm')
        # repeat across the u seam so text never cuts at the wrap
    return np.asarray(m).astype(np.float32) / 255


def make_tire_sidewall(kind='front', W=2048, H=256):
    """Sidewall strip: u wraps once around the tyre, v = 0 at the rim bead (bottom row),
    v = 1 at the shoulder (top row). Letters are upright with their tops toward the shoulder."""
    Ws, Hs = W * 2, H * 2
    B = 'DejaVuSans-Bold.ttf'; R = 'DejaVuSans.ttf'
    items = []
    for rep in (0.0, 0.5):
        o = rep + 0.015
        if kind == 'front':
            items += [(o + 0.000, 0.235, 'GLAMIS TIRE CO', B, 0.30, 0.56),
                      (o + 0.270, 0.180, 'RIDGE CUTTER', B, 0.36, 0.56)]
            items += [(o + 0.010, 0.20, 'TUBELESS • FOR SAND USE ONLY', R, 0.085, 0.24),
                      (o + 0.250, 0.20, '34 x 11.5 - 15   4 PLY   DOT ST7B 2419', R, 0.085, 0.24),
                      (o + 0.300, 0.12, 'MADE IN U.S.A.', R, 0.08, 0.86)]
        else:
            items += [(o + 0.000, 0.215, 'GLAMIS TIRE CO', B, 0.30, 0.56),
                      (o + 0.240, 0.140, 'DUNE PADDLE', B, 0.36, 0.56),
                      (o + 0.395, 0.075, '35x15', B, 0.36, 0.56)]
            items += [(o + 0.010, 0.20, 'TUBELESS • FOR SAND USE ONLY', R, 0.085, 0.24),
                      (o + 0.240, 0.22, '35 x 15 - 15   12 PADDLE   DOT ST7B 2419', R, 0.085, 0.24),
                      (o + 0.300, 0.12, 'MADE IN U.S.A.', R, 0.08, 0.86)]
    letters = _text_strip(Ws, Hs, items)
    yy, xx = np.mgrid[0:Hs, 0:Ws].astype(np.float32)
    v = 1 - (yy + 0.5) / Hs
    # concentric rings: bead ridge near v=0.06, rim guard rib near v=0.10, shoulder grooves near v=0.94
    rings = (np.exp(-((v - 0.06) / 0.02) ** 2) * 0.9 + np.exp(-((v - 0.11) / 0.012) ** 2) * 0.5 +
             np.exp(-((v - 0.95) / 0.01) ** 2) * -0.6 + np.exp(-((v - 0.90) / 0.006) ** 2) * 0.4)
    micro = fbm(Hs, Ws, 120, 501 if kind == 'front' else 502, octaves=2, tile=True)
    hl = blur(letters, 1.6)
    hgt = hl * 1.0 + rings * 0.6 + (micro - 0.5) * 0.08
    # sidewall bulge: slightly convex (normal tilts toward the bead at low v and the shoulder at high v)
    hgt = hgt + 0.0 * v
    lumv = 0.075 + 0.020 * smoothstep(0.3, 0.9, hl) + 0.010 * (micro - 0.5) + 0.008 * rings
    rgb = np.stack([lumv, lumv, lumv * 1.02], -1)
    c = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    n = normal_from_height(hgt * 6.0, strength=1.0, wrap='x')
    n = Image.fromarray(n).resize((W, H), Image.LANCZOS)
    return c, n
