"""Part 'powertrain': the rear engine bay (spec.ENGINE_BAY) of the GLX sand car.

Layout (rear.png, rear_3q_right.png, rear_wheel_sidepod_right.png): VW-style rear engine. The LS-type V8
sits behind the rear axle with its FRONT (accessory drive) facing the rear bumper; the orange bellhousing
bolts to a VW-style transaxle whose diff is on the axle line (spec.R_DIFF_OUTPUT) and whose gear case
runs forward under the firewall.

  - dark long block + heads, black valve covers with gloss carbon coil covers / heat shields (r6), plug wires,
    dry-sump pan; r6: mid-grey cast timing cover and valley front cover, gloss black water pump
  - the big gloss ORANGE folded-sheet plenum (flat top sloping to the rear, sharp crease 60 % back,
    concave rear face tapering to a lip, flat sides; 5 mm fold radii) with runners, fuel rails,
    injectors, red FPR, throttle body on the front face; r5: two braided-stainless loops (woven texture, black AN
    hose ends) behind the plenum's rear face - the fuel crossover and the steam line
  - accessory drive facing rearward: crank damper, water pump, alternator, PS pump, idler, serpentine
    belt, dry-sump cog belt, timing cover, blue remote oil filter
  - twin turbos behind the rear wheels with the shaft fore-aft (turbine at the rear, outlet V-band facing the bumper,
    satin compressor in front of it); 4-into-1 stainless headers looping under them, wastegates + dump tubes, 4"
    downpipes sweeping into a V to the rear centre; the woven black sock filter sits straight on each compressor inlet,
    pointing forward under the side-pod overhang (r6: 5 cm further back, pitched up 5 deg)
  - r6: the compressor scroll discharges at its outboard-low side into a glossy ORANGE silicone elbow that hugs the
    outboard side of the compressor (around the filter's base), crosses over the top and turns inboard into the light
    grey charge pipe (rear_3q / rear_wheel_sidepod / rear.png); the charge pipes run up under the rear cage cross tube
    into a Y in front of the throttle body; r5: black silicone couplers with thin orange end lips and polished T-bolt
    clamps, blow-off valve; r6: thin braided boost-reference lines from the runner banks to the compressor covers
  - orange bellhousing, transaxle case with CV output flanges at x = +-0.18, starter, shift cables
  - radiator (leaning, behind the firewall) with a twin-fan shroud, coolant hard pipe to the water pump
  - behind the cockpit: dry-sump oil tank (right), catch can (left), finned and plain canisters
    (fuel filters / shock-reservoir style) by the B-pillars, fire bottle, braided lines

Coordinates: +X right, +Y forward, +Z up (metres). Most pieces are built on the LEFT and mirrored.
Everything is static.
"""
import math
import os

import bmesh
import bpy
from mathutils import Vector, Matrix

from common import (M, mat, box, cylinder, lathe, loft, mirror_x, obj_from_bmesh, uv_project, box_uv,
                    aligned_matrix, shade, TEX)
import spec

V = Vector

# ------------------------------------------------------------------ engine hard points
ZC = 0.62                 # crank centre height
YF = -2.13                # block front face (faces the rear bumper)
YB = -1.59                # block rear face = bellhousing flange
DECK = 0.235              # crank centre -> deck along the bore axis
BANK = math.radians(45.0)
BORE_PITCH = 0.1118       # LS bore spacing
CYL_Y = {-1: [-2.035 + i * BORE_PITCH for i in range(4)],      # left bank cylinder centres (y)
         +1: [-2.013 + i * BORE_PITCH for i in range(4)]}      # right bank (offset by the rod width)
BELT_Y = -2.175           # serpentine belt plane (r4: 2.3 cm further forward so the pulleys sit behind the downpipes)
DIFF = V(spec.R_DIFF_OUTPUT)

# turbo (left side; mirrored for the right). r3: rear.png + rear_3q (triangulated) show the shaft running
# FORE-AFT: the turbine sits at the rear with its outlet V-band facing the rear bumper (the 4" downpipe
# sweeps inboard and down from it to the centre), the compressor is in front of it, and a fat orange
# silicone reducer carries a black sock filter straight FORWARD, inboard of the rear tyre (the old
# across-the-car layout put the elbow and filter inside the 1.93 m-track tyre). The compressor outlet
# leaves the top of the scroll and the charge pipe climbs up and inboard to the throttle-body Y.
T_YAW = math.radians(3.0)                  # compressor end swung slightly outboard
T_C = V((-0.545, -1.900, 0.910))           # centre of the bearing housing (CHRA), left turbo
T_A = V((-math.sin(T_YAW), math.cos(T_YAW), 0.0))     # shaft axis, turbine -> compressor (forward)
T_P = V((math.cos(T_YAW), math.sin(T_YAW), 0.0))      # radial reference direction (inboard)
T_Z = T_C.z


def TP(u, r=0.0, phi=0.0):
    """Point on the turbo: u along the shaft from the CHRA centre (+ toward the compressor), r/phi radial
    (phi measured from the inboard direction T_P toward +Z)."""
    return T_C + T_A * u + (T_P * math.cos(phi) + V((0, 0, 1)) * math.sin(phi)) * r


T_TURB = TP(-0.067)                         # turbine wheel plane centre
T_INLET = TP(-0.067, 0.100, math.radians(-100))       # turbine inlet flange (bottom of the scroll)
COLL = V((T_INLET.x, T_INLET.y, 0.665))     # header collector bottom (primaries enter here)
FILTER_DIR = (T_A + V((0, 0, math.tan(math.radians(5.0))))).normalized()   # sock axis: forward, pitched up 5 deg
F_U0 = 0.098                                # r6: filter base on the compressor inlet nose (y -1.80, rear_3q)
C_PHI_D = 210.0                             # r6: compressor scroll discharge angle (outboard-low, deg)
E_RC, E_R0, E_R1 = 0.117, 0.037, 0.0345     # r6: discharge elbow centre-line radius about the shaft, hose radius at the
                                            # compressor / charge-pipe ends (rw: hose ~0.45 x the filter's diameter)


def discharge_path():
    """r6: centre line of the compressor discharge: cast stub tangent to the scroll at the outboard-low side, then the
    orange silicone elbow hugging the outboard side of the compressor at E_RC from the shaft (around the filter's
    base, axial u ~0.09), over the top and inboard into the charge pipe (left turbo; mirrored)."""
    rc = E_RC
    top = TP(0.093, rc, math.radians(90))
    pts = [TP(0.034, 0.102, math.radians(C_PHI_D)), TP(0.040, 0.108, math.radians(199)),
           TP(0.055, rc - 0.004, math.radians(186)), TP(0.074, rc, math.radians(168)),
           TP(0.090, rc, math.radians(145)), TP(0.094, rc, math.radians(120)),
           TP(0.093, rc, math.radians(100)), top + T_P * 0.022 + V((0, 0, 0.002)),
           top + T_P * 0.058 + V((0, 0, 0.010))]
    return smooth_path(pts, 4)


# ------------------------------------------------------------------ materials

def plenum_orange():
    """r3: glossy powder-coated orange of the sheet-metal intake (rear.png): the livery orange, low
    roughness under a sharp clear coat (crisp highlight)."""
    return mat('Plenum orange', '#ff5a0d', rough=0.12, clearcoat=1.0, clearcoat_rough=0.03)


def mats():
    return {
        'block': mat('Engine cast dark', '#55585d', metal=0.55, rough=0.45),     # r4: photo block/heads ~55 median, lit 110-150
        'head': mat('Engine head dark', '#4e5156', metal=0.55, rough=0.42),
        'vcover': mat('Valve cover wrinkle black', '#0d0d0f', metal=0.15, rough=0.62),
        'banod': mat('Black anodized', '#131315', metal=0.75, rough=0.32),
        'orange': M('orange'),
        'plenum': plenum_orange(),
        # r6 (critic): glossy orange silicone (the compressor discharge elbows read wet-gloss in rear_3q / rw)
        'silicone': mat('Silicone orange', '#ff560a', rough=0.22, clearcoat=0.8, clearcoat_rough=0.05),
        # r5 (rear.png): the charge-pipe / coolant couplers are BLACK silicone with thin orange end lips
        'silicone_black': mat('Silicone black', '#151515', rough=0.6),
        # r5: light grey like the rear bumper / arms (rear.png); M('cage') is now dark charcoal gunmetal
        'pipe': M('arm'),
        'ceramic': M('ceramic'),
        'alu': M('alu'),
        'polished': M('polished'),
        'chrome': M('chrome'),
        'steel': M('steel_dark'),
        'turbine': mat('Turbine housing coated', '#5a5d62', metal=0.6, rough=0.38),
        # r3: bright brushed stainless primaries / collectors (rear_3q), satin cast-aluminium compressor housings
        'stainless': mat('Brushed stainless', '#a3a6aa', metal=1.0, rough=0.28),
        'comp': mat('Compressor cast aluminium', '#b0b3b7', metal=1.0, rough=0.4),
        'satin': M('satin_black'),
        'gloss': M('gloss_black'),
        'rubber': M('rubber'),
        'carbon': M('carbon'),
        'carbon_matte': M('carbon_matte'),
        # r6 (critic + arbiter): the two tall heat-shield / coil-cover plates beside the plenum are gloss carbon
        # (rear.png: weave + clear-coat highlight; r5 black anodised read as a flat black slab)
        'ccover': M('carbon'),
        # r5: braided stainless with a woven texture (sweep(uv_tile=2 pi r)). r6: lighter (texture mean ~#c0c4c8,
        # textures/powertrain_braid_lt.png; the r5 one averaged ~#8c8c8f and read dark grey)
        'braid': mat('Braided stainless woven', tex='powertrain_braid_lt.png', metal=1.0, rough=0.32),
        'hose': mat('Hose black', '#151516', rough=0.7),
        'red': mat('Red anodized', '#b3141b', metal=0.6, rough=0.33),
        'blue': mat('Blue anodized', '#1d4fd6', metal=0.6, rough=0.33),
        'brass': mat('Brass', '#c9a14a', metal=1.0, rough=0.3),
        'case': mat('Transaxle cast', '#8f9296', metal=0.8, rough=0.48),
        # r6: also the timing cover + water-pump housing (rear.png: the block front reads mid-grey cast, not black)
        'valley': mat('Engine valley cast', '#6a6d70', metal=0.3, rough=0.45),
        'soot': mat('Exhaust soot', '#0a0a0a', rough=0.9),
        # r6: woven black sock with a satin sheen (rear_3q / rw: fine weave catching the light; r5 read flat matte)
        'filter': mat('Filter sock', tex='powertrain_sock.png', rough=0.48, clearcoat=0.25, clearcoat_rough=0.25),
        'core': mat('Radiator core', tex='powertrain_radiator.png', metal=0.75, rough=0.42),
        'fins': mat('Finned canister anodized', '#25262a', metal=0.85, rough=0.28),
        'label': mat('Gauge face', '#e9e9e6', rough=0.4),
    }


# ------------------------------------------------------------------ textures (own files)

def _tex(name):
    return os.path.join(TEX, name)


def ensure_textures():
    try:
        import numpy as np
        from PIL import Image
    except Exception:
        return
    p = _tex('powertrain_radiator.png')
    if not os.path.exists(p):
        # radiator core: flat tubes (vertical) with louvred fins between them, 512 px = one tile
        n = 512
        y, x = np.mgrid[0:n, 0:n].astype(np.float32)
        img = np.zeros((n, n, 3), np.float32)
        tube_pitch = 32
        tx = (x % tube_pitch) / tube_pitch
        tube = (tx < 0.16)
        fin = 0.5 + 0.5 * np.sin(y * 2 * np.pi / 5.0 + 0.6 * np.sin(x * 2 * np.pi / tube_pitch))
        base = 0.12 + 0.20 * fin
        base = np.where(tube, 0.30 + 0.06 * np.sin(tx * np.pi / 0.16), base)
        rng = np.random.default_rng(3)
        base = base * (0.92 + 0.08 * rng.random((n, n)))
        img[..., 0] = base * 1.0
        img[..., 1] = base * 1.0
        img[..., 2] = base * 1.04
        Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(p)
    p = _tex('powertrain_sock.png')
    if not os.path.exists(p):
        # r6: black stretch pre-filter sock (rear_3q / rw): a fine plain-weave knit (~2 mm cells) whose raised threads
        # catch the light (~55-70 sRGB) over a near-black base (~16), soft irregular wrinkle shading along the length.
        # One tile = 1/9 of the circumference x 4.9 cm (filter UVs: 9 tiles around, lc.z / 0.049 along).
        n, N = 256, 24
        y, x = np.mgrid[0:n, 0:n].astype(np.float32)
        u, v = (x + 0.5) / n, (y + 0.5) / n
        a, b = (u + v) * N, (u - v) * N
        fa, fb = a - np.floor(a), b - np.floor(b)
        top = ((np.floor(a) + np.floor(b)) % 2) == 0
        across = np.where(top, fa, fb)
        thread = np.sin(np.pi * np.clip(across, 0, 1)) ** 1.5
        rng = np.random.default_rng(7)
        wr = 0.5 + 0.5 * np.sin(2 * np.pi * (v * 2 + 0.15 * np.sin(2 * np.pi * u))) * np.cos(2 * np.pi * u)
        val = 13 + 40 * thread * (0.75 + 0.25 * wr) + 6 * rng.random((n, n))
        val = np.round(val / 2.0) * 2.0
        img = np.stack([val, val, val * 1.06 + 1], -1)
        Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(p, optimize=True)
    p = _tex('powertrain_braid_lt.png')
    if not os.path.exists(p):
        # r5: braided stainless hose cover, one tile = one turn around the hose (u) x one circumference along it (v)
        # (sweep(uv_tile=2 pi r)): 12 strand bundles per direction, plain over/under weave, ~6 wires per bundle.
        # r6: lighter - bars ~230, gaps ~105 (mean ~#c0c4c8; the r5 texture had bars ~205 / gaps 60, mean ~140)
        n, N, wires = 256, 12, 6
        y, x = np.mgrid[0:n, 0:n].astype(np.float32)
        u, v = (x + 0.5) / n, (y + 0.5) / n
        a, b = (u - v) * N, (u + v) * N
        ia, ib = np.floor(a), np.floor(b)
        fa, fb = a - ia, b - ib
        top_a = ((ia + ib) % 2) == 0
        across = np.where(top_a, fa, fb)           # across the visible bundle
        along = np.where(top_a, fb, fa)            # along it (dips under the crossing bundles at the cell ends)
        wire = 0.86 + 0.14 * np.cos(2 * np.pi * across * wires)
        edge = np.clip((np.minimum(across, 1 - across) - 0.015) / 0.10, 0, 1) ** 0.8
        dip = 0.80 + 0.20 * np.sin(np.pi * along) ** 0.6
        val = 100 + (234 - 100) * edge * wire * dip
        rng = np.random.default_rng(11)
        val = val * (0.985 + 0.03 * rng.random((n, n)))
        val = np.round(val / 3.0) * 3.0             # coarser levels: a much smaller PNG (GLB budget)
        img = np.stack([val, val + 3.0, val + 6.0], -1)
        Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(p, optimize=True)


# ------------------------------------------------------------------ geometry helpers

def shade_fixed(o, smooth=True, angle=35.0):
    """common.shade() calls Mesh.set_sharpness_by_angle, which bpy 5.1 does not have (the call fails
    silently and every hard edge ends up smooth-shaded). This is the same thing with the 5.x API;
    build() swaps it in only while the powertrain is being built."""
    me = o.data
    if not hasattr(me, 'polygons'):
        return o
    for p in me.polygons:
        p.use_smooth = smooth
    if smooth:
        for fn in ('set_sharp_from_angle', 'set_sharpness_by_angle'):
            if hasattr(me, fn):
                getattr(me, fn)(angle=math.radians(angle))
                break
    return o


def sharpen(o, deg=35.0):
    shade_fixed(o, True, deg)
    return o


def cyl(name, r, p0, p1, m, segs=24, r2=None, cap=True, sharp=40):
    p0, p1 = V(p0), V(p1)
    d = p1 - p0
    o = cylinder(name, r, d.length, material=m, segments=segs, r2=r2, cap=cap)
    o.matrix_basis = aligned_matrix((p0 + p1) / 2, d)
    return sharpen(o, sharp)


def lathe_at(name, prof, base, axis, m, segs=32, sharp=30):
    o = lathe(name, prof, m, segments=segs)
    o.matrix_basis = aligned_matrix(base, axis)
    return sharpen(o, sharp)


def bbox(name, size, loc, m, bevel=0.0, rot=(0, 0, 0), segs=1):
    o = box(name, size, loc, rot, m, bevel=bevel, segments=segs)
    return sharpen(o, 30)


def oriented_box(name, size, centre, xdir, ydir, m, bevel=0.0, segs=1):
    """Box of size (sx, sy, sz) whose local X/Y follow xdir/ydir (Z = X x Y)."""
    o = box(name, size, (0, 0, 0), material=m, bevel=bevel, segments=segs)
    x = V(xdir).normalized()
    y = (V(ydir) - x * V(ydir).dot(x)).normalized()
    z = x.cross(y)
    mw = Matrix((x, y, z)).transposed().to_4x4()
    mw.translation = V(centre)
    o.matrix_basis = mw
    return sharpen(o, 30)


def smooth_path(pts, steps=5):
    """Catmull-Rom through the points (hoses, pipes)."""
    P = [V(p) for p in pts]
    if len(P) < 3:
        return P
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


def path_len(P):
    return sum((P[i + 1] - P[i]).length for i in range(len(P) - 1))


def path_at(P, s):
    """Point and tangent at arc length s along polyline P."""
    acc = 0.0
    for i in range(len(P) - 1):
        L = (P[i + 1] - P[i]).length
        if acc + L >= s or i == len(P) - 2:
            t = 0.0 if L < 1e-9 else min(1.0, max(0.0, (s - acc) / L))
            return P[i].lerp(P[i + 1], t), (P[i + 1] - P[i]).normalized()
        acc += L
    return P[-1], (P[-1] - P[-2]).normalized()


def path_sub(P, s0, s1, n=8):
    return [path_at(P, s0 + (s1 - s0) * k / n)[0] for k in range(n + 1)]


def sweep(name, pts, r, m, sides=16, cap0=True, cap1=True, sharp=60, radii=None, uv_tile=None):
    """Tube along pts with parallel-transport frames, optional per-point radii, outward normals.
    uv_tile: UVs u = around (one turn = 1), v = arc length / uv_tile (r5: braided lines; automatic for the woven
    braid material with uv_tile = 2 pi r)."""
    if uv_tile is None and m is not None and m.name.startswith('Braided stainless woven'):
        uv_tile = 2 * math.pi * max(r, 1e-4)
    P = [V(p) for p in pts]
    # drop duplicate points
    Q = [P[0]]
    for p in P[1:]:
        if (p - Q[-1]).length > 1e-6:
            Q.append(p)
    P = Q
    n = len(P)
    R = radii if radii is not None else [r] * n
    if radii is not None and len(R) != n:
        R = [radii[min(int(i * len(radii) / n), len(radii) - 1)] for i in range(n)]
    T = []
    for i in range(n):
        if i == 0:
            t = P[1] - P[0]
        elif i == n - 1:
            t = P[-1] - P[-2]
        else:
            t = (P[i + 1] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
            if t.length < 1e-6:
                t = P[i + 1] - P[i]
        T.append(t.normalized())
    ref = V((0, 0, 1)) if abs(T[0].z) < 0.9 else V((1, 0, 0))
    nrm = (ref - T[0] * ref.dot(T[0])).normalized()
    bm = bmesh.new()
    rings = []
    for i in range(n):
        if i > 0:
            q = T[i - 1].rotation_difference(T[i])
            nrm = q @ nrm
            nrm = (nrm - T[i] * nrm.dot(T[i])).normalized()
        b = T[i].cross(nrm)
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            ring.append(bm.verts.new(P[i] + (nrm * math.cos(a) + b * math.sin(a)) * R[i]))
        rings.append(ring)
    uvl = bm.loops.layers.uv.new('UVMap') if uv_tile else None
    acc = [0.0]
    for i in range(1, n):
        acc.append(acc[-1] + (P[i] - P[i - 1]).length)
    for i in range(n - 1):
        r0, r1 = rings[i], rings[i + 1]
        for k in range(sides):
            k2 = (k + 1) % sides
            f = bm.faces.new((r0[k], r0[k2], r1[k2], r1[k]))
            if uvl is not None:
                v0, v1 = acc[i] / uv_tile, acc[i + 1] / uv_tile
                u0, u1 = k / sides, (k + 1) / sides
                for lp, uv in zip(f.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
                    lp[uvl].uv = uv
    if cap0:
        f = bm.faces.new(list(reversed(rings[0])))
        if uvl is not None:
            for lp in f.loops:
                lp[uvl].uv = (0.0, 0.0)
    if cap1:
        f = bm.faces.new(rings[-1])
        if uvl is not None:
            for lp in f.loops:
                lp[uvl].uv = (0.0, 0.0)
    return obj_from_bmesh(name, bm, m, smooth=True, angle=sharp)


def hose(name, pts, r, m, sides=10, steps=4, cap=True):
    return sweep(name, smooth_path(pts, steps), r, m, sides=sides, cap0=cap, cap1=cap)


def ring_band(name, centre, axis, r, w, m, segs=24):
    """Short closed band (clamp / ring) of radius r and width w around axis at centre."""
    a = V(axis).normalized()
    c = V(centre)
    return cyl(name, r, c - a * w / 2, c + a * w / 2, m, segs=segs)


def coupler(name, P, s0, s1, r, mt, clamps=True, sides=20, bolt_dir=None):
    """Silicone coupler following polyline P between arc lengths s0..s1 with two T-bolt clamps.
    r5 (rear.png): black silicone body with a thin (4-5 mm) orange lip ring at each end, polished stainless T-bolt
    clamps (band + bolt block). bolt_dir: optional world direction the T-bolt housings should face (projected normal
    to the pipe); default up."""
    rc = r + 0.006
    out = [sweep(name, path_sub(P, s0 + 0.0045, s1 - 0.0045, 8), rc, mt['silicone_black'], sides=sides)]
    # orange end lips: a short rolled ring flush with the body, its outer edge rounded
    for s, sg in ((s0, 1.0), (s1, -1.0)):
        p, t = path_at(P, s)
        t = t * sg
        prof = [(rc - 0.0016, -0.0002), (rc + 0.0003, 0.0013), (rc + 0.0003, 0.0047)]
        out.append(lathe_at(name + '_lip', prof, p, t, mt['silicone'], segs=16, sharp=50))
    if clamps:
        for s in (s0 + 0.016, s1 - 0.016):
            p, t = path_at(P, s)
            out.append(ring_band(name + '_clamp', p, t, rc + 0.0016, 0.012, mt['polished'], segs=sides))
            # T-bolt housing on the clamp
            if bolt_dir is not None:
                up = V(bolt_dir) - t * V(bolt_dir).dot(t)
                up.normalize()
                side = t.cross(up).normalized()
            else:
                side = t.cross(V((0, 0, 1)))
                if side.length < 1e-3:
                    side = t.cross(V((1, 0, 0)))
                side.normalize()
                up = side.cross(t).normalized()
            out.append(oriented_box(name + '_tbolt', (0.020, 0.012, 0.010), p + up * (rc + 0.0055), t, side,
                                    mt['polished'], bevel=0.002))
            out.append(cyl(name + '_tbolt_nut', 0.0042, p + up * (rc + 0.0055) + side * 0.006,
                           p + up * (rc + 0.0055) + side * 0.014, mt['polished'], segs=6, sharp=30))
    return out


def tip(name, p, t, r, mt, mat_key='ceramic', depth=0.035):
    """Open pipe end: thick lip + recessed sooty disc so the open end never shows through."""
    t = V(t).normalized()
    p = V(p)
    prof = [(r - 0.004, -0.004), (r + 0.002, -0.004), (r + 0.003, 0.004), (r - 0.003, 0.006), (r - 0.004, 0.0),
            (r - 0.004, -0.004)]
    out = [lathe_at(name + '_lip', prof, p, t, mt[mat_key], segs=20)]
    out.append(cyl(name + '_soot', r - 0.004, p - t * depth, p - t * (depth - 0.002), mt['soot'], segs=20))
    out.append(cyl(name + '_inner', r - 0.0042, p - t * depth, p, mt['soot'], segs=20, cap=False))
    flip_normals(out[-1])
    return out


def flip_normals(o):
    o.data.flip_normals()
    return o


def hexnut(name, p, axis, r, h, m):
    return cyl(name, r, V(p), V(p) + V(axis).normalized() * h, m, segs=6, sharp=30)


def bank_frame(side):
    d = V((side * math.sin(BANK), 0.0, math.cos(BANK)))     # bore axis (up and out)
    n = V((side * math.cos(BANK), 0.0, -math.sin(BANK)))    # outward-down, perpendicular to the bore
    return d, n


def bank_pt(side, a, b, y):
    d, n = bank_frame(side)
    return V((0.0, y, ZC)) + d * a + n * b


def section_loft(name, ys, ring_fn, m, sharp=35):
    """Loft closed rings ring_fn(y) -> [(x, z), ...] along y (front to back order irrelevant)."""
    secs = [[(x, y, z) for (x, z) in ring_fn(y)] for y in ys]
    return loft(name, secs, m, closed=True, cap=True, angle=sharp)


def rounded_poly(pts, r, steps=3):
    """Round the corners of a closed 2D polygon."""
    out = []
    n = len(pts)
    rs = r if isinstance(r, (list, tuple)) else [r] * n
    for i in range(n):
        a, b, c = V((*pts[i - 1], 0)), V((*pts[i], 0)), V((*pts[(i + 1) % n], 0))
        ri = rs[i]
        if ri <= 0:
            out.append((b.x, b.y))
            continue
        d1, d2 = (a - b), (c - b)
        l1, l2 = d1.length, d2.length
        d1.normalize(); d2.normalize()
        ang = d1.angle(d2)
        if ang < 1e-3 or ang > math.pi - 1e-3:
            out.append((b.x, b.y))
            continue
        t = min(ri / math.tan(ang / 2), l1 * 0.48, l2 * 0.48)
        p1, p2 = b + d1 * t, b + d2 * t
        for s in range(steps + 1):
            u = s / steps
            q = p1 * (1 - u) ** 2 + b * 2 * u * (1 - u) + p2 * u * u
            out.append((q.x, q.y))
    return out


def scale_ring(ring, c, s, dz=0.0):
    return [(c[0] + (x - c[0]) * s, c[1] + (z - c[1]) * s + dz) for (x, z) in ring]


def circle_pts(c, r, n=24, a0=0.0):
    return [(c[0] + r * math.cos(a0 + 2 * math.pi * k / n), c[1] + r * math.sin(a0 + 2 * math.pi * k / n))
            for k in range(n)]


def hull2d(points):
    pts = sorted(set((round(p[0], 6), round(p[1], 6)) for p in points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def belt(name, circles, y, width, thick, m):
    """Flat belt in the plane y wrapped (convex hull) around circles [(x, z, r), ...]."""
    pts = []
    for (x, z, r) in circles:
        pts += circle_pts((x, z), r, 72)
    H = hull2d(pts)                 # CCW in (x, z)
    # resample: drop points closer than 6 mm
    R = [H[0]]
    for p in H[1:]:
        if math.hypot(p[0] - R[-1][0], p[1] - R[-1][1]) > 0.006:
            R.append(p)
    n = len(R)
    bm = bmesh.new()
    rows = []
    for i in range(n):
        p = V((R[i][0], R[i][1]))
        a, c = V(R[i - 1]), V(R[(i + 1) % n])
        tng = (c - a).normalized()
        out = V((tng.y, -tng.x))        # outward for a CCW polygon
        inner = p
        outer = p + out * thick
        rows.append([bm.verts.new((inner.x, y - width / 2, inner.y)), bm.verts.new((outer.x, y - width / 2, outer.y)),
                     bm.verts.new((outer.x, y + width / 2, outer.y)), bm.verts.new((inner.x, y + width / 2, inner.y))])
    for i in range(n):
        a, b = rows[i], rows[(i + 1) % n]
        for k in range(4):
            k2 = (k + 1) % 4
            bm.faces.new((a[k], b[k], b[k2], a[k2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bmesh(name, bm, m, smooth=True, angle=50)


def disc_pulley(name, x, z, y0, y1, r, m, grooves=True, hub=True, mt=None, segs=32):
    """Pulley/damper on an axis along -y (facing the rear), front face at y1 (more negative)."""
    L = y0 - y1
    prof = [(0.0, 0.0), (r * 0.92, 0.0), (r, L * 0.08)]
    if grooves:
        k = 3
        for i in range(k):
            h0 = L * (0.15 + 0.7 * i / k)
            h1 = L * (0.15 + 0.7 * (i + 0.5) / k)
            prof += [(r, h0), (r - 0.004, h1)]
    prof += [(r, L * 0.92), (r * 0.94, L), (r * 0.6, L), (r * 0.55, L * 0.75), (r * 0.3, L * 0.75),
             (r * 0.28, L * 1.08), (0.0, L * 1.08)]
    out = [lathe_at(name, prof, V((x, y0, z)), (0, -1, 0), m, segs=segs)]
    if hub and mt is not None:
        out.append(hexnut(name + '_bolt', (x, y1 - L * 0.08, z), (0, -1, 0), r * 0.16, 0.012, mt['alu']))
    return out


# ------------------------------------------------------------------ engine long block

def build_block(mt, L, S):
    """Block, heads, valve covers, coil covers, oil pan, timing cover, plug wires, header flanges."""
    def block_ring(y):
        dl0, dl1 = bank_pt(-1, DECK, 0.078, 0), bank_pt(-1, DECK, -0.075, 0)
        dr0, dr1 = bank_pt(1, DECK, 0.078, 0), bank_pt(1, DECK, -0.075, 0)
        return [(-0.185, 0.525), (-0.205, 0.60), (dl0.x, dl0.z), (dl1.x, dl1.z), (-0.06, 0.79), (0.06, 0.79),
                (dr1.x, dr1.z), (dr0.x, dr0.z), (0.205, 0.60), (0.185, 0.525)]
    S.append(section_loft('pt_block', [YF, YB], block_ring, mt['block'], sharp=30))
    # block side ribs / freeze plugs / motor-mount bosses (left; mirrored)
    for y in (-2.02, -1.86, -1.70):
        L.append(cyl('pt_freeze', 0.022, (-0.214, y, 0.64), (-0.205, y, 0.64), mt['alu'], segs=10))
    for y in (-1.94, -1.78):
        L.append(bbox('pt_block_rib', (0.012, 0.018, 0.13), (-0.209, y, 0.60), mt['block'], bevel=0.003))
    # engine mount plates out to the rear lower frame rails
    L.append(oriented_box('pt_mount_plate', (0.27, 0.10, 0.008), (-0.335, -1.74, 0.618), (1, 0, 0.05), (0, 1, 0),
                          mt['banod'], bevel=0.003))
    L.append(cyl('pt_mount_bush', 0.022, (-0.455, -1.74, 0.585), (-0.455, -1.74, 0.634), mt['rubber'], segs=16))

    for side in (-1, 1):
        sl = L if side < 0 else None
        d, n = bank_frame(side)
        ys = CYL_Y[side]
        y0, y1 = -2.118, -1.603

        # head
        def head_ring(y, side=side):
            pts = [(DECK, -0.088), (DECK, 0.098), (0.352, 0.100), (0.362, 0.090), (0.362, -0.090), (0.352, -0.092)]
            return [((bank_pt(side, a, b, 0)).x, (bank_pt(side, a, b, 0)).z) for (a, b) in pts]
        h = section_loft('pt_head', [y0, y1], head_ring, mt['head'], sharp=30)
        S.append(h)
        # valve cover (wrinkle black) with rounded ends
        def vc_ring(y, side=side):
            e = min(y - (-2.105), (-1.615) - y)
            r = 0.016
            ins = 0.0 if e >= r else r - math.sqrt(max(0.0, r * r - (r - e) ** 2))
            prof = [(0.362, -0.088), (0.362, 0.093), (0.372, 0.096), (0.380, 0.090), (0.440, 0.086),
                    (0.440, -0.082), (0.380, -0.086), (0.372, -0.092)]
            out = []
            for (a, b) in prof:
                bb = b * (1 - ins / 0.09)
                aa = 0.362 + (a - 0.362) * (1 - ins / 0.08) if a > 0.362 else a
                q = bank_pt(side, aa, bb, 0)
                out.append((q.x, q.z))
            return out
        vys = [-2.105, -2.1035, -2.099, -2.093, -2.089, -1.631, -1.627, -1.621, -1.6165, -1.615]
        S.append(section_loft('pt_valve_cover', vys, vc_ring, mt['vcover'], sharp=40))
        # valve cover flange bolts (both long sides)
        # (r5: the valve-cover flange bolts were removed: hidden under the coil covers / plug wires)
        # carbon coil-pack cover box on top (its rear end reads as the tall black panel in rear.png)
        # r4: taller satin-carbon coil cover whose top sweeps down into a big rounded rear end (rear.png: a carbon
        # 'sail' on each valve cover with a curved rear outline, top ~3 cm above the r3 box)
        CC_Y0, CC_Y1, CC_A0, CC_A1, CC_RR = -2.098, -1.622, 0.438, 0.516, 0.11
        CC_B1, CC_SLANT = 0.070, 0.012     # outer side pulled in + top falls 12 mm outboard (compressor scroll)

        def cc_ring(y, side=side):
            e1 = (CC_Y1) - y
            r = 0.012
            ins = 0.0 if e1 >= r else r - math.sqrt(max(0.0, r * r - (r - e1) ** 2))
            e0 = y - CC_Y0
            h = CC_A1 - CC_A0
            if e0 < CC_RR:
                h = max(0.010, h * math.sqrt(max(0.0, 1.0 - (1.0 - e0 / CC_RR) ** 2)))
            at = CC_A0 + h - ins
            rr = rounded_poly([(CC_A0, -0.076), (CC_A0, CC_B1), (at - CC_SLANT * h / (CC_A1 - CC_A0), CC_B1),
                               (at, -0.076)],
                              [0.0, 0.0, min(0.018, h * 0.45), min(0.018, h * 0.45)], 3)
            out = []
            for (aa, bb) in rr:
                q = bank_pt(side, aa, bb * (1 - ins / 0.08), 0)
                out.append((q.x, q.z))
            return out
        cys = [CC_Y0 + 0.0005, CC_Y0 + 0.004, CC_Y0 + 0.012, CC_Y0 + 0.024, CC_Y0 + 0.040, CC_Y0 + 0.060, CC_Y0 + 0.082,
               CC_Y0 + CC_RR, -1.634, -1.630, -1.626, -1.623, -1.622]
        cc = section_loft('pt_coil_cover', cys, cc_ring, mt['ccover'], sharp=50)
        box_uv(cc, 1.0)
        S.append(cc)
        for (yy, v) in ((-1.960, -0.05), (-1.960, 0.056), (-1.645, -0.05), (-1.645, 0.056)):
            p = bank_pt(side, CC_A1 - CC_SLANT * (v + 0.076) / (CC_B1 + 0.076), v, yy)
            S.append(cyl('pt_cc_bolt', 0.006, p, p + d * 0.004, mt['alu'], segs=8))
        # plug wires out from under the cover's outer edge, down to the plugs on the head side
        for yi in ys:
            pw = [bank_pt(side, 0.452, 0.071, yi + 0.01), bank_pt(side, 0.44, 0.104, yi + 0.016),
                  bank_pt(side, 0.39, 0.128, yi + 0.022), bank_pt(side, 0.335, 0.116, yi + 0.024)]
            S.append(hose('pt_plug_wire', pw, 0.0048, mt['satin'], sides=6, steps=3))
            S.append(cyl('pt_plug_boot', 0.0075, bank_pt(side, 0.338, 0.117, yi + 0.024),
                         bank_pt(side, 0.318, 0.106, yi + 0.024), mt['satin'], segs=10))
        # exhaust flange strip on the head outer face
        fl0 = bank_pt(side, 0.300, 0.100, -1.86)
        S.append(oriented_box('pt_hdr_flange', (0.008, 0.46, 0.058), fl0 + n * 0.004, n, (0, 1, 0), mt['stainless'],
                              bevel=0.002))

    # dry-sump oil pan with fins
    def pan_ring(y):
        return rounded_poly([(-0.172, 0.53), (0.172, 0.53), (0.165, 0.445), (-0.165, 0.445)], [0, 0, 0.02, 0.02], 2)
    S.append(section_loft('pt_oil_pan', [-2.105, -1.62], pan_ring, mt['banod'], sharp=30))
    for k in range(6):
        y = -2.06 + k * 0.08
        for sx in (-1, 1):
            S.append(bbox('pt_pan_fin', (0.006, 0.012, 0.07), (sx * 0.172, y, 0.49), mt['banod']))
    # pan rail bolts
    for k in range(7):
        y = -2.09 + k * 0.075
        for sx in (-1, 1):
            S.append(cyl('pt_pan_bolt', 0.005, (sx * 0.176, y, 0.522), (sx * 0.183, y, 0.522), mt['alu'], segs=6))

    # (timing cover: build_accessories)


# ---- orange intake plenum (rear.png): r4 rounded scoop / shield
# r4: the critics read the r3 folded box as boxy. rear.png (solved camera) shows a rounded scoop: a gently crowned top
# that curves down toward the rear, a rear face leaning forward (crease y -1.975 z 1.105 -> V point y -2.080 z 1.019)
# whose outline is a rounded trapezoid - full-width top, short vertical sides (to z ~1.065), big rounded lower corners
# into a shallow V that sits on the orange runner banks. Every edge is rounded (8-12 mm), no flat facets.
# The solid is lofted from cross-sections (x, z) along y; in the rear-face zone each section is the shield clipped by
# the leaning face, so the rear face outline IS the section outline.
PY1 = -1.645                   # front (throttle-body) face
PYC = -1.975                   # crease (top -> rear face), before rounding
PYV, PZB = -2.085, 1.013       # V point of the rear face / bottom of the V (all along the plenum)
PW = 0.125                     # half width (crease corners project onto the photo's within 2 px)
PW_FRONT = 0.116               # plan taper toward the front (photo front top edge is narrower)
PZS = 1.066                    # side wall -> lower chamfer
PZT_F, PZT_C = 1.150, 1.108    # crown-line top at the front face / at the crease
P_CROWN = 0.008                # top centre above its side edges
P_RCR = 0.050                  # y-z fillet radius of the crease (top curving down into the rear face)
P_RTC, P_RLC, P_RV = 0.012, 0.036, 0.024   # section corner radii: top corners, lower corners, V bottom
P_RF = 0.010                   # front face edge fillet
TB_Z = 1.085                   # throttle body centre height
PY0 = PYV                      # rear-most point (other code uses it)


def _plenum_top_line(y):
    """Centre-line top before the crease fillet: gently convex, dropping faster toward the rear."""
    s = PY1 - y
    L = PY1 - PYC
    a = 0.06
    b = (PZT_F - PZT_C - a * L) / (L * L)
    return PZT_F - a * s - b * s * s


def _plenum_rear_line(y):
    return PZB + (_plenum_top_line(PYC) - PZB) * (y - PYV) / (PYC - PYV)


def _profile_fillet():
    """(y, z) centre-line profile: top line, R fillet, rear-face line. Returns a dense list front -> rear."""
    # tangent directions (in (y, z) with y decreasing toward the rear)
    eps = 1e-4
    t1 = V((-1.0, (_plenum_top_line(PYC - eps) - _plenum_top_line(PYC + eps)) / (2 * eps) * -1.0)).normalized()
    t2 = V((PYV - PYC, PZB - _plenum_top_line(PYC))).normalized()
    ang = t1.angle(t2)
    tl = P_RCR * math.tan(ang / 2)
    c = V((PYC, _plenum_top_line(PYC)))
    p1, p2 = c - t1 * tl, c + t2 * tl
    pts = []
    n_top = 14
    for i in range(n_top + 1):
        y = PY1 + (p1.x - PY1) * i / n_top
        pts.append(V((y, _plenum_top_line(y))))
    nf = 6
    for i in range(1, nf):
        u = i / nf
        q = p1 * (1 - u) ** 2 + c * 2 * u * (1 - u) + p2 * u * u
        pts.append(q)
    return pts, p2


def plenum_ztop(y):
    """Crown-line top height at station y (used by the strap)."""
    pts, p2 = _profile_fillet()
    if y <= p2.x:
        return _plenum_rear_line(y)
    for a, b in zip(pts[:-1], pts[1:]):
        if a.x >= y >= b.x:
            t = (y - a.x) / (b.x - a.x) if abs(b.x - a.x) > 1e-9 else 0.0
            return a.y + (b.y - a.y) * t
    return pts[0].y


def _plenum_w(y):
    if y <= -1.80:
        return PW
    s = (y - (-1.80)) / (PY1 - (-1.80))
    return PW - (PW - PW_FRONT) * s * s


def _round_open(pts, radii, steps=4):
    """Round the interior corners of an open 2D polyline (endpoints kept); radii per point (0 = sharp)."""
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = V(pts[i - 1]), V(pts[i]), V(pts[i + 1])
        r = radii[i]
        d1, d2 = a - b, c - b
        l1, l2 = d1.length, d2.length
        if r <= 0 or l1 < 1e-7 or l2 < 1e-7:
            out.append(b)
            continue
        d1.normalize(); d2.normalize()
        ang = d1.angle(d2)
        if ang < 1e-3 or ang > math.pi - 1e-3:
            out.append(b)
            continue
        t = min(r / math.tan(ang / 2), l1 * 0.49, l2 * 0.49)
        p1, p2 = b + d1 * t, b + d2 * t
        for s in range(steps + 1):
            u = s / steps
            out.append(p1 * (1 - u) ** 2 + b * 2 * u * (1 - u) + p2 * u * u)
    out.append(V(pts[-1]))
    return out


def _resample(pts, n, k_turn=0.010):
    """Resample an open polyline to n+1 points, denser where it turns (arc length + k * turning angle)."""
    P = [V(p) for p in pts]
    P2 = [P[0]]
    for p in P[1:]:
        if (p - P2[-1]).length > 1e-7:
            P2.append(p)
    P = P2
    w = [0.0]
    for i in range(1, len(P)):
        ds = (P[i] - P[i - 1]).length
        turn = 0.0
        if 0 < i < len(P) - 1:
            d1, d2 = P[i] - P[i - 1], P[i + 1] - P[i]
            if d1.length > 1e-9 and d2.length > 1e-9:
                turn = d1.angle(d2)
        w.append(w[-1] + ds + k_turn * turn)
    out = []
    j = 0
    for k in range(n + 1):
        s = w[-1] * k / n
        while j < len(w) - 2 and w[j + 1] < s:
            j += 1
        t = 0.0 if w[j + 1] - w[j] < 1e-12 else (s - w[j]) / (w[j + 1] - w[j])
        out.append(P[j].lerp(P[j + 1], min(1.0, max(0.0, t))))
    return out


def _path_point(P, s):
    """Point at arc length s along polyline P (clamped) and the index of the segment it lies on."""
    acc = 0.0
    for i in range(len(P) - 1):
        L = (P[i + 1] - P[i]).length
        if acc + L >= s:
            t = 0.0 if L < 1e-12 else (s - acc) / L
            return P[i].lerp(P[i + 1], t), i
        acc += L
    return P[-1], len(P) - 2


def _arclen(P):
    return sum((P[i + 1] - P[i]).length for i in range(len(P) - 1))


def _shield_half(y, inset=0.0):
    """Right half of the (unclipped) rounded shield: bottom centre -> V chamfer -> lower corner -> side wall up."""
    W = _plenum_w(y) - inset
    zb = PZB + inset / math.cos(math.atan2(PZS - PZB, PW))
    pts = [V((-W, PZS)), V((0.0, zb)), V((W, PZS)), V((W, 1.40))]
    rad = [0.0, max(0.0, P_RV - inset), max(0.0, P_RLC - inset), 0.0]
    r = _round_open(pts, rad, steps=8)
    half = []
    for i, p in enumerate(r):
        if p.x >= -1e-9:
            if not half and i > 0 and r[i - 1].x < 0:
                a, b = r[i - 1], p
                half.append(a.lerp(b, -a.x / (b.x - a.x)))
            half.append(p)
    half[0] = V((0.0, half[0].y))
    return half, W


def _plenum_half(y, zc, inset=0.0, nh=26):
    """Right half (x >= 0) of the section at station y with crown-line top zc: the rounded shield clipped by the
    crowned top curve, the clip corner filleted (P_RTC). From the bottom centre to the top centre, nh+1 points;
    None when the clip is below the V bottom."""
    S, W = _shield_half(y, inset)

    def ztop(x):
        return zc - inset - P_CROWN * (x / max(W, 1e-6)) ** 2

    if ztop(0.0) <= S[0].y + 0.0012:
        return None
    j = None
    for i in range(len(S) - 1):
        f0, f1 = S[i].y - ztop(S[i].x), S[i + 1].y - ztop(S[i + 1].x)
        if f0 <= 0.0 < f1:
            j = i
            t = f0 / (f0 - f1)
            Q = S[i].lerp(S[i + 1], t)
            break
    if j is None:
        return None
    Sq = S[:j + 1] + [Q]
    T = [V((Q.x * (1 - k / 12), ztop(Q.x * (1 - k / 12)))) for k in range(13)]
    din = (Q - Sq[-2]).normalized() if (Q - Sq[-2]).length > 1e-9 else (Sq[-2] - Sq[-3]).normalized()
    dout = (T[1] - T[0]).normalized()
    ang = (-din).angle(dout)
    rc = max(0.003, P_RTC - inset)
    if ang < math.pi - 1e-3:
        t = rc / math.tan(ang / 2)
        t = min(t, 0.45 * _arclen(Sq), 0.45 * _arclen(T))
        A, ia = _path_point(Sq, _arclen(Sq) - t)
        B, ib = _path_point(T, t)
        fil = [A * (1 - u) ** 2 + Q * 2 * u * (1 - u) + B * u * u for u in (k / 6 for k in range(7))]
        half = Sq[:ia + 1] + fil + T[ib + 1:]
    else:
        half = Sq + T[1:]
    half[-1] = V((0.0, half[-1].y))
    return _resample(half, nh)


def build_plenum(m):
    """Lofted rounded scoop (see the notes above the constants)."""
    nh = 26
    secs = []
    # front face edge fillet
    for k in range(5):
        th = math.radians(90 - 22.5 * k)
        y = PY1 - P_RF * (1 - math.sin(th))
        ins = P_RF * (1 - math.cos(th))
        secs.append((y, plenum_ztop(y), ins))
    prof, p2 = _profile_fillet()
    for p in prof[1:]:
        if p.x < PY1 - P_RF - 0.004:
            secs.append((p.x, p.y, 0.0))
    # rear face: denser toward the V point
    y0 = p2.x
    n_r = 14
    for i in range(1, n_r + 1):
        u = i / n_r
        u = 1 - (1 - u) ** 1.35
        y = y0 + (PYV + 0.0004 - y0) * u
        secs.append((y, _plenum_rear_line(y), 0.0))
    rings = []
    for (y, zc, ins) in secs:
        h = _plenum_half(y, zc, ins, nh)
        if h is None:
            break
        ring = [(p.x, y, p.y) for p in h] + [(-p.x, y, p.y) for p in reversed(h[1:-1])]
        rings.append(ring)
    bm = bmesh.new()
    vr = [[bm.verts.new(p) for p in ring] for ring in rings]
    n = len(vr[0])
    for a, b in zip(vr[:-1], vr[1:]):
        for i in range(n):
            i2 = (i + 1) % n
            bm.faces.new((a[i], a[i2], b[i2], b[i]))
    # caps: flat front face (fan from its centre), tiny rear end (fan)
    for ring, (y, zc, ins) in ((vr[0], secs[0]), (vr[-1], secs[len(vr) - 1])):
        cz = sum(v.co.z for v in ring) / n
        c = bm.verts.new((0.0, ring[0].co.y, cz))
        for i in range(n):
            bm.faces.new((c, ring[i], ring[(i + 1) % n]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = obj_from_bmesh('pt_plenum', bm, m, smooth=True, angle=70)
    return o


RB_Y0, RB_Y1 = -2.100, -1.625      # runner bank rear end face / front end
# rear end of the coolant hard pipe (build_cooling): down behind the left coil cover, outboard of the alternator and
# in to the water-pump inlet (r5: the steam line B tees into it)
COOLANT_TAIL = [V((-0.260, -2.070, 1.028)), V((-0.275, -2.130, 1.005)), V((-0.255, -2.200, 0.975)),
                V((-0.205, -2.228, 0.958)), V((-0.148, -2.226, 0.922)), V((-0.112, -2.208, 0.884))]


def runner_bank(side, m):
    """One cast runner bank: a slanted wall from the head's intake flange up and inward under the plenum's lower
    chamfer, with a lobe over each runner on its outer face; flat end faces with a 6 mm edge fillet."""
    def quad(y, ins):
        p1 = bank_pt(side, 0.305, -0.097, 0.0)
        p2 = bank_pt(side, 0.360, -0.097, 0.0)
        x3 = side * 0.118
        p3 = V((x3, 0.0, PZB + (PZS - PZB) * abs(x3) / PW - 0.004))
        x4 = side * 0.052
        p4 = V((x4, 0.0, PZB + (PZS - PZB) * abs(x4) / PW - 0.004))
        q = [V((p.x, p.z)) for p in (p1, p2, p3, p4)]
        # runner lobes on the outer face (p2 -> p3)
        ph = min(abs(y - yc) for yc in CYL_Y[side])
        bulge = 0.010 * max(0.0, math.cos(math.pi * min(ph / (BORE_PITCH * 0.62), 1.0) / 2)) ** 2 - 0.002
        e = (q[2] - q[1]).normalized()
        nout = V((-e.y, e.x))
        if nout.x * side < 0:
            nout = -nout
        q[1] = q[1] + nout * bulge * 0.6
        q[2] = q[2] + nout * bulge
        c = sum(q, V((0.0, 0.0))) / 4
        if ins > 0:
            q = [p + (c - p).normalized() * ins for p in q]
        if side > 0:
            q = list(reversed(q))
        r = rounded_poly([(p.x, p.y) for p in q], max(0.002, 0.008 - ins * 0.5), 2)
        return [(x, z) for (x, z) in r]
    ys = []
    f = 0.006
    for k in range(3):
        th = math.radians(90 - 45 * k)
        ys.append((RB_Y0 + f * (1 - math.sin(th)), f * (1 - math.cos(th))))
    nmid = 30
    for i in range(1, nmid):
        ys.append((RB_Y0 + f + (RB_Y1 - RB_Y0 - 2 * f) * i / nmid, 0.0))
    for k in range(3):
        th = math.radians(45 * k)
        ys.append((RB_Y1 - f * (1 - math.cos(th)), f * (1 - math.sin(th))))
    secs = [[(x, y, z) for (x, z) in quad(y, ins)] for (y, ins) in ys]
    o = loft('pt_runner_bank', secs, m, closed=True, cap=True, angle=50)
    return sharpen(o, 50)


def an_fitting(name, p, t, rh, mt, length=0.020, segs=10):
    """Black anodised AN hose end on a braided line of radius rh: socket from p along t (toward the line's other
    end it is not), hex nut at the p end. t points from the fitting INTO the hose."""
    t = V(t).normalized()
    p = V(p)
    rs = rh + 0.0026
    prof = [(0.0, -0.002), (rh + 0.0015, -0.002), (rs, 0.0015), (rs, length - 0.004), (rs - 0.0012, length),
            (rh, length + 0.0006), (0.0, length + 0.0006)]
    out = [lathe_at(name, prof, p, t, mt['banod'], segs=segs, sharp=40)]
    out.append(cyl(name + '_hex', rh + 0.0048, p - t * 0.006, p + t * 0.002, mt['banod'], segs=6, sharp=30))
    return out


def build_braided_loops(mt, S):
    """r5 (rear.png, critic): two ~10-13 mm braided-stainless lines looping from side to side just behind the
    plenum's rear face, with black AN hose ends.
    A: fuel crossover from the rear ends of the rails. 90-degree black hose ends rise from the rail-end ports to the
       photo's fittings (690, 530) / (870, 535) = (+-0.119, -2.112, 1.064); the loop hangs to (775, 588) =
       (0, -2.142, 0.997) under the plenum's V (back-projected onto y planes, symmetrised).
    B: steam / coolant crossover just under and in front of A (hidden behind it at the centre, rear.png (700, 592)
       / (845, 592)): left end on the left valve-cover end face over the alternator (the alternator sits on the
       head's end face), right end on a 90-degree fitting on the right head's end face, rising in the gap in front
       of the PS pump (photo: the line drops to ~(935, 642) on the right)."""
    ra, rb = 0.0068, 0.0055
    # ---- A
    for sx in (-1, 1):
        rail_end = V((sx * 0.185, -2.087, 1.012))
        el = [rail_end, V((sx * 0.185, -2.096, 1.0125)), V((sx * 0.181, -2.106, 1.019)),
              V((sx * 0.168, -2.1115, 1.034)), V((sx * 0.146, -2.1125, 1.051)), V((sx * 0.128, -2.1125, 1.059))]
        S.append(sweep('pt_loopA_elbow', smooth_path(el, 2), ra + 0.0024, mt['banod'], sides=8))
        S.append(cyl('pt_loopA_hex', 0.0105, rail_end + V((0, 0.003, 0)), rail_end + V((0, -0.006, 0)), mt['banod'],
                     segs=6, sharp=30))
    A = [V((-0.128, -2.1125, 1.059)), V((-0.112, -2.118, 1.049)), V((-0.098, -2.124, 1.036)),
         V((-0.078, -2.132, 1.018)), V((-0.048, -2.139, 1.0035)), V((0.0, -2.142, 0.997))]
    A = A + [V((-p.x, p.y, p.z)) for p in reversed(A[:-1])]
    AP = smooth_path(A, 3)
    S.append(sweep('pt_loopA', AP, ra, mt['braid'], sides=8))
    for (p, t) in ((AP[0], AP[1] - AP[0]), (AP[-1], AP[-2] - AP[-1])):
        S += an_fitting('pt_loopA_end', p - t.normalized() * 0.004, t, ra, mt)
    # ---- B: steam line (rear.png (662, 619) -> (725, 591) | (837, 579) -> (894, 616) -> (950, 654)): from a black
    # AN boss on top of the coolant hard pipe (left, above the alternator pulley, behind the belt plane) it rises and
    # runs forward-inboard UNDER A so its crown is hidden behind A's bottom, then back over the PS pulley and down to an
    # AN port on the right valve cover's rear end face, outboard of the PS pump
    CP = smooth_path(COOLANT_TAIL, 3)
    k = min(range(1, len(CP) - 1), key=lambda i: abs(CP[i].x - (-0.212)) + 2 * abs(CP[i].y + 2.224))
    q = CP[k]
    t = (CP[k + 1] - CP[k - 1]).normalized()
    nb = V((0.25, 0.0, 1.0))
    nb = (nb - t * nb.dot(t)).normalized()
    bt = q + nb * 0.031
    S.append(cyl('pt_loopB_boss', 0.0092, q + nb * 0.012, bt - nb * 0.004, mt['banod'], segs=10))
    S.append(cyl('pt_loopB_boss_hex', 0.0104, q + nb * 0.016, q + nb * 0.024, mt['banod'], segs=6, sharp=30))
    B = [bt, bt + nb * 0.010 + V((0.006, 0.0, 0.0)), V((-0.172, -2.212, 0.993)), V((-0.130, -2.190, 0.999)),
         V((-0.090, -2.161, 0.996)), V((-0.050, -2.134, 0.988)), V((0.000, -2.1215, 0.9865)),
         V((0.050, -2.134, 0.988)), V((0.090, -2.161, 0.996)), V((0.125, -2.190, 0.999)), V((0.165, -2.203, 0.987)),
         V((0.215, -2.199, 0.963)), V((0.246, -2.180, 0.931)), V((0.250, -2.150, 0.908)), V((0.250, -2.126, 0.903))]
    BP = smooth_path(B, 3)
    S.append(sweep('pt_loopB', BP, rb, mt['braid'], sides=8))
    S += an_fitting('pt_loopB_end', bt - nb * 0.003, nb, rb, mt, length=0.016)
    S += an_fitting('pt_loopB_end', V((0.250, -2.106, 0.903)), V((0, -1, 0)), rb, mt)
    S.append(cyl('pt_loopB_port', 0.0105, V((0.250, -2.1045, 0.903)), V((0.250, -2.0995, 0.903)), mt['banod'],
                 segs=6, sharp=30))


def build_intake(mt, L, S):
    """Orange plenum, runners, throttle body, fuel rails, injectors, FPR, crossover line."""
    S.append(build_plenum(mt['plenum']))
    # small black strap from the plenum's front top edge up and back to the deck cross tube (rear.png: it shows
    # only between the front edge and the tube)
    # r5: the cross tube moved to spec REAR_XBAR_YZ (y -1.68, z 1.21): the strap now rises almost vertically to it
    xb_y, xb_z = spec.REAR_XBAR_YZ
    s0, s1 = V((0.0, -1.668, plenum_ztop(-1.668) + 0.001)), V((0.0, xb_y + 0.012, xb_z - spec.CAGE_TUBE_R * 0.88))
    S.append(oriented_box('pt_plenum_tab', (0.036, (s1 - s0).length, 0.004), (s0 + s1) / 2, (1, 0, 0), s1 - s0,
                          mt['banod'], bevel=0.0012))
    S.append(oriented_box('pt_plenum_tab_foot', (0.036, 0.022, 0.004), (0.0, -1.672, plenum_ztop(-1.672) + 0.002),
                          (1, 0, 0), (0, 1, 0), mt['banod'], bevel=0.0012))
    # r4: cast orange runner banks (rear.png: under the plenum each side is a smooth orange wall with a flat rear end
    # face and a bolt, not separate tubes), plus the orange valley plate between them under the V
    for side in (-1, 1):
        d, n = bank_frame(side)
        S.append(runner_bank(side, mt['plenum']))
        pe = bank_pt(side, 0.336, -0.065, RB_Y0 - 0.0012)
        S.append(hexnut('pt_bank_bolt', pe, (0, -1, 0), 0.0068, 0.006, mt['alu']))
        # runner base flange plate on the head
        fc = bank_pt(side, 0.333, -0.094, -1.86)
        S.append(oriented_box('pt_intake_flange', (0.007, 0.47, 0.062), fc, -n, (0, 1, 0), mt['plenum'], bevel=0.002))
        # fuel rail (black anodized bar) with red AN ends, injectors into the runners
        rx, rz = side * 0.185, 1.012     # r4: on the injectors over the runner banks' outer faces
        S.append(bbox('pt_fuel_rail', (0.020, 0.45, 0.020), (rx, -1.845, rz), mt['banod'], bevel=0.003))
        for yy in (-2.07, -1.62):
            S.append(cyl('pt_rail_fit', 0.0105, (rx, yy, rz), (rx, yy + (0.016 if yy > -1.8 else -0.016), rz),
                         mt['banod'], segs=6))
        for yi in CYL_Y[side]:
            S.append(cyl('pt_injector', 0.0085, (rx, yi, rz - 0.010), (side * 0.165, yi, 0.972), mt['satin'], segs=10))
            S.append(cyl('pt_inj_clip', 0.0095, (rx, yi, rz - 0.012), (rx, yi, rz - 0.018), mt['alu'], segs=10))
    # intake valley cover between the runners
    def valley_ring(y):
        return [(-0.13, 0.875), (0.13, 0.875), (0.115, 0.93), (-0.115, 0.93)]
    S.append(section_loft('pt_valley', [-2.075, -1.655], valley_ring, mt['valley'], sharp=30))
    # valley plate (dark) with an orange rear flange lip + bolt just under the plenum's V (rear.png v 555-570)
    S.append(bbox('pt_valley_plate', (0.190, 0.462, 0.012), (0.0, -1.862, 0.956), mt['block'], bevel=0.003, segs=1))
    S.append(bbox('pt_valley_lip', (0.120, 0.024, 0.016), (0.0, -2.084, 0.966), mt['plenum'], bevel=0.004, segs=2))
    S.append(hexnut('pt_valley_bolt', (0.0, -2.080, 0.974), (0, 0, 1), 0.0068, 0.006, mt['alu']))

    # r5: the two braided loops behind the plenum's rear face (fuel crossover + steam line), see build_braided_loops
    build_braided_loops(mt, S)
    # fuel-pressure regulator on the FRONT end of the right rail (rear.png: red base, black body, gauge)
    fpr = V((0.185, -1.585, 1.022))
    S.append(lathe_at('pt_fpr', [(0.0, 0.0), (0.018, 0.0), (0.020, 0.006), (0.020, 0.040), (0.026, 0.046),
                                 (0.026, 0.066), (0.018, 0.072), (0.0, 0.072)], fpr, (0, 0, 1), mt['red'], segs=16))
    S.append(lathe_at('pt_fpr_body', [(0.0, 0.0), (0.027, 0.0), (0.027, 0.020), (0.020, 0.030), (0.0, 0.031)],
                      fpr + V((0, 0, 0.046)), (0, 0, 1), mt['banod'], segs=16))
    S.append(cyl('pt_fpr_gauge', 0.016, fpr + V((0.0, -0.022, 0.058)), fpr + V((0.0, -0.034, 0.058)), mt['chrome'],
                 segs=16))
    S.append(cyl('pt_fpr_face', 0.013, fpr + V((0.0, -0.0341, 0.058)), fpr + V((0.0, -0.0345, 0.058)), mt['label'],
                 segs=16))
    S.append(cyl('pt_fpr_adj', 0.006, fpr + V((0, 0, 0.076)), fpr + V((0, 0, 0.089)), mt['alu'], segs=6))
    S.append(hose('pt_fpr_link', [(0.185, -1.604, 1.012), (0.185, -1.596, 1.016), fpr + V((0, -0.004, 0.004))],
                  0.0058, mt['braid'], sides=8, steps=3))
    # fuel feed + return lines forward to AN bulkhead fittings on the rear face of the firewall (r3: they
    # used to run through the frame loop and the firewall into the cockpit)
    S.append(hose('pt_fuel_feed', [(-0.185, -1.62, 1.012), (-0.215, -1.55, 0.962), (-0.24, -1.45, 0.89),
                                   (-0.255, -1.32, 0.78), (-0.25, -1.17, 0.67), (-0.24, -1.04, 0.612),
                                   (-0.235, -0.975, 0.60), (-0.235, -0.942, 0.60)],
                  0.0058, mt['braid'], sides=8))
    S.append(hose('pt_fuel_return', [fpr + V((0.024, 0.0, 0.03)), (0.232, -1.56, 1.025), (0.255, -1.47, 0.95),
                                     (0.27, -1.33, 0.80), (0.25, -1.20, 0.66), (0.25, -1.06, 0.612),
                                     (0.25, -0.975, 0.60), (0.25, -0.942, 0.60)],
                  0.0052, mt['braid'], sides=8))
    # bulkhead plates with the AN fittings (feed left, return right) and the starter-cable grommet
    S.append(oriented_box('pt_bulkhead_plate', (0.10, 0.004, 0.075), (0.225, -0.936, 0.585), (1, 0, 0), (0, 1, 0),
                          mt['banod'], bevel=0.0015))
    S.append(oriented_box('pt_bulkhead_plate', (0.05, 0.004, 0.05), (-0.235, -0.936, 0.60), (1, 0, 0), (0, 1, 0),
                          mt['banod'], bevel=0.0015))
    for x, mk in ((-0.235, 'blue'), (0.25, 'red')):
        S.append(hexnut('pt_bulkhead_nut', (x, -0.938, 0.60), (0, -1, 0), 0.012, 0.007, mt[mk]))
    S.append(cyl('pt_grommet', 0.013, (0.200, -0.938, 0.565), (0.200, -0.948, 0.565), mt['rubber'], segs=12))

    # throttle body on the front face of the plenum (toward the cockpit)
    tb = V((0.0, PY1, TB_Z))
    S.append(cyl('pt_tb_flange', 0.058, tb + V((0, -0.004, 0)), tb + V((0, 0.006, 0)), mt['banod'], segs=28))
    S.append(lathe_at('pt_tb', [(0.0, 0.0), (0.050, 0.0), (0.050, 0.062), (0.047, 0.066), (0.046, 0.066),
                                (0.046, 0.080), (0.0, 0.080)], tb + V((0, 0.006, 0)), (0, 1, 0), mt['banod'], segs=28))
    S.append(oriented_box('pt_tb_motor', (0.045, 0.05, 0.06), tb + V((0.075, 0.04, -0.005)), (1, 0, 0), (0, 1, 0),
                          mt['satin'], bevel=0.006))


def serpentine(name, pulleys, y, width, thick, m, step_deg=9.0):
    """Serpentine belt in the plane y routed around pulleys [(x, z, r, s), ...] in travel order (closed loop).
    s = +1: the belt wraps the pulley counter-clockwise as seen from behind (-y), ribbed side on it;
    s = -1: the pulley is outside the loop (idler pressing on the belt's back). Seen from behind x is right, z up."""
    n = len(pulleys)
    C = [V((p[0], p[1])) for p in pulleys]
    R = [p[2] if p[3] > 0 else p[2] + thick for p in pulleys]
    Sg = [p[3] for p in pulleys]

    def left(d):
        return V((-d.y, d.x))
    outp, inp = [None] * n, [None] * n
    for i in range(n):
        j = (i + 1) % n
        D = C[j] - C[i]
        mlen = D.length
        k = Sg[j] * R[j] - Sg[i] * R[i]
        phi = math.atan2(D.y, D.x)
        al = phi - math.asin(max(-1.0, min(1.0, k / mlen)))
        d = V((math.cos(al), math.sin(al)))
        outp[i] = C[i] - left(d) * (Sg[i] * R[i])
        inp[j] = C[j] - left(d) * (Sg[j] * R[j])
    path = []
    for j in range(n):
        a0 = math.atan2(inp[j].y - C[j].y, inp[j].x - C[j].x)
        a1 = math.atan2(outp[j].y - C[j].y, outp[j].x - C[j].x)
        if Sg[j] > 0:
            sw = (a1 - a0) % (2 * math.pi)
        else:
            sw = -((a0 - a1) % (2 * math.pi))
        ns = max(2, int(abs(math.degrees(sw)) / step_deg))
        for k in range(ns + 1):
            a = a0 + sw * k / ns
            path.append(C[j] + V((math.cos(a), math.sin(a))) * R[j])
    # drop duplicates
    P = [path[0]]
    for p in path[1:]:
        if (p - P[-1]).length > 1e-5:
            P.append(p)
    if (P[0] - P[-1]).length < 1e-5:
        P.pop()
    m_ = len(P)
    bm = bmesh.new()
    rows = []
    for i in range(m_):
        d = (P[(i + 1) % m_] - P[i - 1]).normalized()
        rt = V((d.y, -d.x))
        o = P[i] + rt * thick
        rows.append([bm.verts.new((P[i].x, y - width / 2, P[i].y)), bm.verts.new((o.x, y - width / 2, o.y)),
                     bm.verts.new((o.x, y + width / 2, o.y)), bm.verts.new((P[i].x, y + width / 2, P[i].y))])
    for i in range(m_):
        a_, b_ = rows[i], rows[(i + 1) % m_]
        for k in range(4):
            k2 = (k + 1) % 4
            bm.faces.new((a_[k], b_[k], b_[k2], a_[k2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bmesh(name, bm, m, smooth=True, angle=50)


def show_pulley(name, x, z, y_back, y_front, r, mt, grooved=True, ring=True, segs=32):
    """Black anodised pulley facing the rear: grooved/flat belt band, rolled front lip with a polished ring,
    dished face, raised hub with bolts (rear.png / rear_3q: the big black pulleys with a bright rim)."""
    L = y_back - y_front
    prof = [(0.0, 0.0), (r * 0.80, 0.0), (r, L * 0.10)]
    if grooved:
        for i in range(3):
            h0 = L * (0.18 + 0.62 * i / 3)
            h1 = L * (0.18 + 0.62 * (i + 0.5) / 3)
            prof += [(r, h0), (r - 0.0035, h1)]
    prof += [(r, L * 0.86), (r * 1.04, L * 0.90), (r * 1.04, L * 0.97), (r * 0.98, L), (r * 0.86, L),
             (r * 0.80, L * 0.82), (r * 0.42, L * 0.78), (r * 0.36, L * 1.02), (r * 0.30, L * 1.10), (0.0, L * 1.10)]
    out = [lathe_at(name, prof, V((x, y_back, z)), (0, -1, 0), mt['banod'], segs=segs, sharp=40)]
    if ring:
        out.append(lathe_at(name + '_ring', [(r * 0.87, -0.0006), (r * 1.042, -0.0006), (r * 1.042, 0.0016),
                                             (r * 0.87, 0.0016), (r * 0.87, -0.0006)],
                            V((x, y_back - L * 0.985, z)), (0, -1, 0), mt['polished'], segs=segs))
    out.append(hexnut(name + '_bolt', (x, y_front - L * 0.10, z), (0, -1, 0), max(0.006, r * 0.17), 0.010, mt['alu']))
    for k in range(4):
        a = math.radians(45 + 90 * k)
        p = V((x + r * 0.58 * math.cos(a), y_front - L * 0.80 + L, z + r * 0.58 * math.sin(a)))
        p.y = y_back - L * 0.80
        out.append(cyl(name + '_stud', max(0.0035, r * 0.07), p, p + V((0, -0.006, 0)), mt['alu'], segs=6))
    return out


def build_accessories(mt, L, S):
    """Front (rear-facing) accessory drive, dry-sump pump, oil filter.
    r4: rear.png u 640-940 v 630-790 (solved camera, belt plane y -2.20): the big black pulley at the centre
    (775, 750) is the water pump pulley (0, 0.795) r ~0.06 with a bright rim, two idlers just above it either
    side (840, 668), the alternator up high on the left (650, 655) and the PS pump high on the right (930, 680),
    on the LS 'batwing' water pump; the 0.20 m crank damper sits at the crank (0, 0.62), behind the bumper V."""
    wpc = (0.0, 0.795)
    i1 = (0.084, 0.878)              # idler right of / above the pump (rear.png (840, 668))
    tens = (-0.212, 0.762)           # tensioner idler, lower left
    alt = (-0.172, 0.925)            # (650, 655), behind the coolant drop
    ps = (0.192, 0.915)              # (930, 680), behind the right downpipe
    yb = BELT_Y + 0.012              # back face of the belt-plane pulleys
    # timing cover (front cover) up to the water pump
    tc = rounded_poly([(0.0, 0.505), (0.105, 0.53), (0.135, 0.62), (0.115, 0.74), (0.075, 0.80), (-0.075, 0.80),
                       (-0.115, 0.74), (-0.135, 0.62), (-0.105, 0.53)], 0.03, 3)
    # r6 (critic): the timing cover / water pump read mid-grey cast in rear.png ('Engine valley cast' #6a6d70), not black
    S.append(section_loft('pt_timing_cover', [YF + 0.002, YF - 0.015], lambda y: tc, mt['valley'], sharp=30))
    for (x, z) in ((0.11, 0.60), (-0.11, 0.60), (0.10, 0.72), (-0.10, 0.72), (0.0, 0.53)):
        S.append(cyl('pt_tc_bolt', 0.0055, (x, YF - 0.015, z), (x, YF - 0.022, z), mt['alu'], segs=6))
    # LS 'batwing' water pump: round housing at the centre, arms up to both heads; coolant inlet on the left arm
    wp_pts = circle_pts(wpc, 0.078, 20) + circle_pts((0.128, 0.862), 0.028, 12) + circle_pts((-0.128, 0.862), 0.028, 12)
    wp_out = hull2d(wp_pts)
    S.append(section_loft('pt_wp_body', [YF + 0.004, -2.136, -2.142, -2.148],
                          lambda y: (wp_out if y > -2.139 else scale_ring(wp_out, wpc, 0.97 if y > -2.145 else 0.90)),
                          mt['gloss'], sharp=35))
    for (x, z) in ((0.128, 0.862), (-0.128, 0.862), (0.058, 0.848), (0.0, 0.722)):
        S.append(hexnut('pt_wp_bolt', (x, -2.146, z), (0, -1, 0), 0.0065, 0.007, mt['alu']))
    S.append(cyl('pt_wp_snout', 0.030, (wpc[0], -2.144, wpc[1]), (wpc[0], yb, wpc[1]), mt['gloss'], segs=20))
    # r6: grey cast front cover of the intake valley between the heads, above the water pump (rear.png: a mid-grey
    # bolted face under the plenum's V; r5 showed the dark open valley there)
    vf = rounded_poly([(-0.058, 0.792), (0.058, 0.792), (0.100, 0.846), (0.112, 0.900), (0.100, 0.952),
                       (-0.100, 0.952), (-0.112, 0.900), (-0.100, 0.846)], [0.01, 0.01, 0.02, 0.012, 0.01, 0.01, 0.012, 0.02], 2)
    S.append(section_loft('pt_valley_front', [-2.110, -2.124], lambda y: vf, mt['valley'], sharp=30))
    for (x, z) in ((-0.084, 0.928), (0.084, 0.928), (-0.032, 0.940), (0.032, 0.940)):
        S.append(hexnut('pt_vf_bolt', (x, -2.124, z), (0, -1, 0), 0.0058, 0.006, mt['alu']))
    wi0, wi1 = V((-0.072, -2.140, 0.862)), V((-0.094, -2.188, 0.874))
    S.append(cyl('pt_wp_inlet', 0.024, wi0, wi1, mt['valley'], segs=16))
    S.append(ring_band('pt_wp_inlet_bead', wi1 - (wi1 - wi0).normalized() * 0.006, wi1 - wi0, 0.0265, 0.004,
                       mt['alu'], segs=16))
    # pulleys: water pump, idler, tensioner, alternator, PS pump (front faces y ~-2.19..-2.20)
    S += show_pulley('pt_wp_pulley', wpc[0], wpc[1], yb, yb - 0.038, 0.067, mt, grooved=True, segs=32)
    S += show_pulley('pt_idler', i1[0], i1[1], yb - 0.002, yb - 0.030, 0.032, mt, grooved=False, ring=False, segs=20)
    S.append(cyl('pt_idler_spacer', 0.012, (i1[0], -2.140, i1[1]), (i1[0], yb - 0.001, i1[1]), mt['alu'], segs=10))
    S += show_pulley('pt_tensioner', tens[0], tens[1], yb - 0.002, yb - 0.030, 0.030, mt, grooved=False, ring=False,
                     segs=20)
    S.append(oriented_box('pt_tens_arm', (0.016, 0.012, 0.115), (-0.165, -2.150, 0.715), (0, 1, 0),
                          (0.50, 0.0, -0.40), mt['banod'], bevel=0.003))
    S.append(cyl('pt_tens_pivot', 0.016, (-0.118, -2.135, 0.668), (-0.118, -2.158, 0.668), mt['banod'], segs=16))
    S += show_pulley('pt_alt_pulley', alt[0], alt[1], yb - 0.002, yb - 0.028, 0.034, mt, grooved=True, ring=False,
                     segs=24)
    S += show_pulley('pt_ps_pulley', ps[0], ps[1], yb - 0.002, yb - 0.028, 0.042, mt, grooved=True, ring=True, segs=28)
    # alternator body behind its pulley (finned black case) and the PS pump body (both start at the heads' end faces)
    prof = [(0.0, 0.0), (0.050, 0.0), (0.056, 0.005)]
    for k in range(2):
        h = 0.010 + k * 0.014
        prof += [(0.059, h), (0.055, h + 0.007)]
    prof += [(0.059, 0.033), (0.052, 0.037), (0.0, 0.037)]
    S.append(lathe_at('pt_alt', prof, V((alt[0], -2.119, alt[1])), (0, -1, 0), mt['satin'], segs=24))
    S.append(lathe_at('pt_alt_fan', [(0.012, 0.0), (0.048, 0.0), (0.048, 0.0045), (0.012, 0.0045), (0.012, 0.0)],
                      V((alt[0], -2.156, alt[1])), (0, -1, 0), mt['banod'], segs=20))
    S.append(cyl('pt_alt_terminal', 0.007, (alt[0] - 0.045, -2.140, alt[1] + 0.03), (alt[0] - 0.045, -2.125,
                                                                                    alt[1] + 0.03), mt['red'], segs=8))
    S.append(lathe_at('pt_ps_pump', [(0.0, 0.0), (0.040, 0.0), (0.044, 0.008), (0.044, 0.036), (0.038, 0.043),
                                     (0.0, 0.043)], V((ps[0], -2.119, ps[1])), (0, -1, 0), mt['satin'], segs=20))
    # PS line: down in front of the block face (behind the belt), then forward along the right side of the block
    S.append(hose('pt_ps_line', [(ps[0] - 0.03, -2.148, ps[1] - 0.03), (0.150, -2.152, 0.80), (0.168, -2.150, 0.70),
                                 (0.212, -2.140, 0.610), (0.226, -2.02, 0.585), (0.24, -1.80, 0.585),
                                 (0.25, -1.66, 0.600), (0.25, -1.54, 0.66)], 0.0065, mt['braid'], sides=8))
    # crank damper: 0.20 m, inertia ring + grooved belt band, dished face, centre bolt (behind the bumper V)
    S.append(lathe_at('pt_crank_damper', [(0.0, 0.0), (0.085, 0.0), (0.100, 0.006), (0.100, 0.012), (0.096, 0.016),
                                          (0.100, 0.020), (0.096, 0.024), (0.100, 0.028), (0.100, 0.044),
                                          (0.094, 0.050), (0.074, 0.050), (0.068, 0.046), (0.040, 0.046),
                                          (0.036, 0.062), (0.0, 0.062)], V((0.0, -2.162, ZC)), (0, -1, 0),
                      mt['banod'], segs=24))
    S.append(lathe_at('pt_damper_ring', [(0.075, -0.0006), (0.0952, -0.0006), (0.0952, 0.0016), (0.075, 0.0016),
                                         (0.075, -0.0006)], V((0.0, -2.2115, ZC)), (0, -1, 0), mt['polished'], segs=32))
    S.append(hexnut('pt_damper_bolt', (0.0, -2.224, ZC), (0, -1, 0), 0.016, 0.012, mt['alu']))
    # serpentine belt: crank -> PS (right, high) -> under the idler -> over the water pump -> alternator (left,
    # high) -> tensioner (lower left) -> back to the crank
    S.append(serpentine('pt_belt', [(0.0, ZC, 0.100, 1), (ps[0], ps[1], 0.042, 1), (i1[0], i1[1], 0.032, -1),
                                    (wpc[0], wpc[1], 0.067, 1), (alt[0], alt[1], 0.034, 1),
                                    (tens[0], tens[1], 0.030, 1)], BELT_Y, 0.021, 0.0045, mt['rubber']))

    # dry-sump pump (left low) with its cog belt from the crank
    sp = V((-0.212, -2.0, 0.488))
    prof = [(0.0, 0.0), (0.040, 0.0)]
    for k in range(4):
        h = 0.012 + k * 0.058
        prof += [(0.043, h), (0.043, h + 0.044), (0.037, h + 0.048), (0.037, h + 0.056)]
    prof += [(0.04, 0.245), (0.0, 0.245)]
    S.append(lathe_at('pt_sump_pump', prof, V((sp.x, -1.905, sp.z)), (0, -1, 0), mt['blue'], segs=14))
    for k in range(4):
        y = -1.93 - k * 0.058
        S.append(cyl('pt_sump_fit', 0.011, (sp.x - 0.035, y, sp.z - 0.005), (sp.x - 0.06, y, sp.z - 0.02), mt['red'],
                     segs=6))
    S.append(cyl('pt_sump_cog', 0.048, (sp.x, -2.146, sp.z), (sp.x, -2.160, sp.z), mt['alu'], segs=24))
    S.append(cyl('pt_crank_cog', 0.055, (0, -2.146, ZC), (0, -2.160, ZC), mt['alu'], segs=28))
    S.append(belt('pt_sump_belt', [(0.0, ZC, 0.055), (sp.x, sp.z, 0.048)], -2.153, 0.012, 0.004, mt['rubber']))
    # scavenge lines pan -> pump, pressure line pump -> block
    for k in range(3):
        y = -1.93 - k * 0.058
        S.append(hose('pt_scav', [(sp.x - 0.058, y, sp.z - 0.02), (-0.20, y + 0.03, 0.445), (-0.17, y + 0.06, 0.462)],
                      0.0062, mt['braid'], sides=8, steps=4))
    # oil filter (blue anodized remote housing) on the right side of the block
    of = V((0.205, -1.965, 0.50))
    S.append(bbox('pt_of_mount', (0.03, 0.06, 0.06), (0.200, -1.965, 0.50), mt['banod'], bevel=0.004))
    prof = [(0.0, 0.0), (0.044, 0.0), (0.047, 0.008)]
    for k in range(5):
        h = 0.02 + k * 0.018
        prof += [(0.047, h), (0.043, h + 0.006), (0.047, h + 0.012)]
    prof += [(0.047, 0.12), (0.040, 0.128), (0.0, 0.128)]
    S.append(lathe_at('pt_oil_filter', prof, of + V((0.012, 0, 0)), (1, 0, 0), mt['satin'], segs=16))
    S.append(cyl('pt_oil_filter_cap', 0.042, of + V((0.138, 0, 0)), of + V((0.150, 0, 0)), mt['blue'], segs=20))
    S.append(hexnut('pt_oil_filter_nut', of + V((0.150, 0, 0)), (1, 0, 0), 0.016, 0.010, mt['blue']))
    # oil filter lines forward to the oil tank (right side)
    S.append(hose('pt_oil_line_a', [(0.24, -1.945, 0.535), (0.29, -1.82, 0.56), (0.30, -1.60, 0.575), (0.30, -1.45, 0.58),
                                    (0.30, -1.30, 0.66), (0.315, -1.20, 0.75), (0.335, -1.08, 0.88),
                                    (0.345, -1.01, 0.975)], 0.0075, mt['braid'], sides=6))
    S.append(hose('pt_oil_line_b', [(sp.x - 0.06, -1.93, sp.z - 0.02), (-0.27, -1.85, 0.48), (-0.29, -1.75, 0.52),
                                    (-0.30, -1.55, 0.57), (-0.27, -1.38, 0.56), (-0.17, -1.20, 0.50),
                                    (-0.12, -1.02, 0.45), (0.10, -1.00, 0.44), (0.28, -0.995, 0.52),
                                    (0.33, -0.993, 0.80), (0.33, -0.993, 0.98)], 0.0075, mt['braid'], sides=6))


def arc_path(start, d0, d1, R, steps=10):
    """Horizontal-ish circular arc from `start` heading d0 to heading d1 (unit vectors), radius R."""
    d0, d1 = V(d0).normalized(), V(d1).normalized()
    k = d0.cross(d1)
    ang = d0.angle(d1)
    if k.length < 1e-6 or ang < 1e-4:
        return [V(start)]
    k.normalize()
    cen = V(start) + k.cross(d0) * R
    rel = V(start) - cen
    out = []
    for i in range(steps + 1):
        q = Matrix.Rotation(ang * i / steps, 3, k)
        out.append(cen + q @ rel)
    return out


def s_near(P, q):
    """Arc length along polyline P of the vertex nearest to q."""
    q = V(q)
    acc, best, bs = 0.0, 1e9, 0.0
    for i in range(len(P)):
        if i:
            acc += (P[i] - P[i - 1]).length
        d = (P[i] - q).length
        if d < best:
            best, bs = d, acc
    return bs


def build_headers_turbo(mt, L, S):
    """Left headers, turbo, wastegate, downpipe, inlet coupler + filter, charge pipe (mirrored for the right).
    r3: shaft fore-aft (turbine at the rear, outlet facing the bumper), see T_C."""
    side = -1
    d, n = bank_frame(side)
    ys = CYL_Y[side]
    A, P, Z = T_A, T_P, V((0, 0, 1))
    # ---- 4-into-1 brushed-stainless primaries: out of the head, over the rear lower frame rail, down outboard
    # of it and back into a 2x2 bundle that feeds the collector under the turbine from below (rear_3q)
    offs = [(+0.021, -0.021), (+0.021, +0.021), (-0.021, +0.021), (-0.021, -0.021)]
    for i, yi in enumerate(ys):
        ox, oy = offs[i]
        p0 = bank_pt(side, 0.300, 0.100, yi)
        q = V((COLL.x + ox, COLL.y + oy, COLL.z))
        if yi > -1.86:     # front two: stay high over the rail kink (y -1.66, z .665), drop well outboard of it
            pts = [p0, p0 + n * 0.035, V((-0.39, yi - 0.004, 0.738)), V((-0.495, yi - 0.012, 0.735)),
                   V((-0.565, yi - 0.05, 0.700)), V((-0.588, (yi + q.y) / 2 - 0.03, 0.640)),
                   V((q.x, q.y + 0.010, 0.612)), V((q.x, q.y, 0.640)), q]
        else:               # rear two: straight out and down, then forward-in under the collector
            pts = [p0, p0 + n * 0.035, V((-0.39, yi - 0.004, 0.728)), V((-0.485, yi + 0.004, 0.695)),
                   V((-0.548, (yi + q.y) / 2, 0.640)), V((q.x, q.y - 0.012, 0.612)), V((q.x, q.y, 0.640)), q]
        S.append(sweep('pt_primary', smooth_path(pts, 3), 0.0205, mt['stainless'], sides=10))
    # collector cone up into the turbine inlet flange (bottom of the turbine scroll)
    flange = T_INLET
    cpts = [COLL + V((0, 0, -0.012)), COLL + V((0, 0, 0.035)), flange.lerp(COLL, 0.3), flange - V((0, 0, 0.004))]
    S.append(sweep('pt_collector', smooth_path(cpts, 4), 0.0, mt['stainless'], sides=20,
                   radii=[0.050, 0.050, 0.049, 0.047, 0.045, 0.043, 0.041, 0.040, 0.039, 0.038, 0.038, 0.038, 0.038]))
    S.append(ring_band('pt_coll_vband', flange - V((0, 0, 0.006)), (0, 0, 1), 0.046, 0.012, mt['alu']))

    # ---- turbo (big frame: ~100 mm compressor housing radius), shaft along T_A
    # coated turbine housing + scroll; its inlet feeds down into the collector
    S.append(lathe_at('pt_turbine', [(0.0, 0.0), (0.055, 0.0), (0.078, 0.009), (0.088, 0.027), (0.088, 0.054),
                                     (0.077, 0.068), (0.055, 0.073), (0.050, 0.082), (0.0, 0.082)],
                      TP(-0.031), -A, mt['turbine'], segs=28))
    vol, vr = [], []
    for k in range(21):
        ph = math.radians(170 - 290 * k / 20)          # top-inboard -> over the outboard side -> down to the inlet
        rr = 0.078 + 0.016 * k / 20
        vol.append(TP(-0.067, rr, ph))
        vr.append(0.012 + 0.024 * k / 20)
    S.append(sweep('pt_turb_volute', vol, 0.0, mt['turbine'], sides=12, radii=vr))
    S.append(cyl('pt_turb_inlet', 0.036, TP(-0.067, 0.094, math.radians(-120)) + V((0, 0, 0.01)),
                 flange, mt['turbine'], segs=16))
    # turbine outlet V-band (faces the rear bumper, into the downpipe)
    S.append(ring_band('pt_turb_vband', TP(-0.115), -A, 0.060, 0.016, mt['alu']))
    S.append(cyl('pt_vband_bolt', 0.006, TP(-0.115, 0.064, math.radians(60)),
                 TP(-0.115, 0.064, math.radians(60)) + P * 0.03, mt['alu'], segs=6))
    # centre section (CHRA)
    S.append(lathe_at('pt_chra', [(0.0, 0.0), (0.046, 0.0), (0.046, 0.010), (0.036, 0.013), (0.036, 0.034),
                                  (0.046, 0.037), (0.046, 0.045), (0.0, 0.045)], TP(-0.031), A, mt['steel'], segs=20))
    # satin cast-aluminium compressor housing + scroll. r6: the scroll now discharges at the OUTBOARD-LOW side (phi 210)
    # heading up, into the orange silicone discharge elbow (see below); r5 had the outlet at the top-inboard side
    S.append(lathe_at('pt_compressor', [(0.0, 0.0), (0.088, 0.0), (0.097, 0.010), (0.100, 0.030), (0.091, 0.048),
                                        (0.070, 0.058), (0.056, 0.060), (0.056, 0.074), (0.060, 0.076),
                                        (0.060, 0.084), (0.0, 0.084)], TP(0.012), A, mt['comp'], segs=28))
    cvol, cr = [], []
    for k in range(21):
        ph = math.radians(C_PHI_D + 295 - 295 * k / 20)    # starts top-outboard (145), over the top, inboard, under
        rr = 0.090 + 0.012 * k / 20                       # the bottom and ends outboard-low at the discharge (210)
        cvol.append(TP(0.034, rr, ph))
        cr.append(0.012 + 0.022 * k / 20)
    S.append(sweep('pt_comp_volute', cvol, 0.0, mt['comp'], sides=12, radii=cr, cap1=False))
    # discharge: cast stub continuing the scroll tangentially (up the outboard side) and forward to the elbow
    DP = discharge_path()
    s_stub = 0.034
    S.append(sweep('pt_comp_outlet', path_sub(DP, 0.0, s_stub, 4), 0.034, mt['comp'], sides=20, cap0=False, cap1=True))
    p, t = path_at(DP, s_stub - 0.006)
    S.append(ring_band('pt_comp_outlet_lip', p, t, 0.0365, 0.006, mt['comp'], segs=20))
    # oil feed (braided) from the timing cover, over the coolant drop and the downpipe to the CHRA top;
    # black drain from the CHRA bottom inboard between the primaries to the block
    top, bot = TP(0.0, 0.050, math.radians(90)), TP(0.0, 0.046, math.radians(-90))
    # r4: up between idler 2 and the alternator, over the alternator, in front of the coolant drop
    S.append(cyl('pt_turbo_feed_fit', 0.008, (-0.247, -2.114, 0.797), (-0.247, -2.128, 0.797), mt['red'], segs=6))
    S.append(hose('pt_turbo_feed', [(-0.247, -2.128, 0.797), (-0.31, -2.136, 0.812), (-0.37, -2.122, 0.840),
                                    (-0.43, -2.095, 0.862), (-0.47, -2.060, 0.950), (-0.49, -2.04, 1.035),
                                    TP(-0.070, 0.128, math.radians(100)),
                                    TP(-0.022, 0.080, math.radians(93)), top + V((0, 0, 0.012)), top], 0.0045,
                  mt['braid'], sides=6, steps=3))
    S.append(hose('pt_turbo_drain', [bot, bot + V((0.012, 0.008, -0.034)), (-0.47, -1.872, 0.795),
                                     (-0.37, -1.866, 0.78), (-0.33, -1.862, 0.72), (-0.255, -1.838, 0.668),
                                     (-0.212, -1.82, 0.656)], 0.0085, mt['hose'], sides=6))

    # ---- r6: orange silicone DISCHARGE elbow (rear_3q / rw / rear.png): from the cast stub it hugs the outboard side of
    # the compressor (wrapping the filter's base, rw), passes over the top and turns inboard into the charge pipe;
    # glossy orange, polished T-bolt clamps at both ends
    s0, s1 = s_stub - 0.022, path_len(DP)
    ne = 18
    EP = path_sub(DP, s0, s1, ne)
    er = [E_R0 - (E_R0 - E_R1) * max(0.0, (k / ne - 0.55) / 0.45) for k in range(ne + 1)]
    S.append(sweep('pt_discharge_elbow', EP, E_R0, mt['silicone'], sides=20, radii=er))
    for (sc, rc, bolt) in ((s0 + 0.012, E_R0 + 0.0018, -P), (s1 - 0.014, E_R1 + 0.0018, V((0.0, -1.0, 0.25)))):
        p, t = path_at(DP, sc)
        S.append(ring_band('pt_elbow_clamp', p, t, rc, 0.011, mt['polished'], segs=20))
        up = (bolt - t * bolt.dot(t)).normalized()     # start clamp: T-bolt outboard; end clamp: toward the rear
        side = t.cross(up).normalized()
        S.append(oriented_box('pt_elbow_tbolt', (0.018, 0.012, 0.011), p + up * (rc + 0.005), t, side,
                              mt['polished'], bevel=0.002))
        S.append(cyl('pt_elbow_tbolt_nut', 0.0042, p + up * (rc + 0.005) + side * 0.006,
                     p + up * (rc + 0.005) + side * 0.014, mt['polished'], segs=6, sharp=30))
    # r6: the sock filter sits straight on the compressor inlet (rear_3q projection: near end y -1.80, far end ~-1.55),
    # its base inside the elbow's curve (rw); black rubber neck with a polished clamp, sock pitched up 5 deg
    S.append(lathe_at('pt_filter_neck', [(0.0, -0.004), (0.0585, -0.004), (0.0615, 0.0), (0.0615, 0.024),
                                         (0.0, 0.024)], TP(F_U0 - 0.012), A, mt['rubber'], segs=20))
    S.append(ring_band('pt_filter_clamp', TP(F_U0 - 0.001), A, 0.0635, 0.010, mt['polished'], segs=20))
    f0 = TP(F_U0 + 0.010)
    fprof = [(0.0, 0.0), (0.060, 0.0), (0.066, 0.003), (0.0695, 0.010)]
    # soft irregular wrinkles of the stretch sock instead of the r5 regular pleats
    for (h, dr) in ((0.030, 0.0012), (0.060, -0.0008), (0.090, 0.0016), (0.122, -0.0006), (0.154, 0.0013),
                    (0.186, -0.0010), (0.212, 0.0008)):
        fprof.append((0.0705 + dr, h))
    fprof += [(0.0705, 0.232), (0.068, 0.242), (0.060, 0.249), (0.034, 0.253), (0.0, 0.254)]
    fo = lathe_at('pt_filter', fprof, f0, FILTER_DIR, mt['filter'], segs=24, sharp=60)
    inv = fo.matrix_basis.inverted()

    def fuv(co, nn):
        lc = inv @ co
        return (math.atan2(lc.y, lc.x) / (2 * math.pi) * 9.0, lc.z / 0.049)
    uv_project(fo, fuv)
    S.append(fo)
    S.append(cyl('pt_filter_cap', 0.040, f0 + FILTER_DIR * 0.249, f0 + FILTER_DIR * 0.2575, mt['satin'], segs=20))
    S.append(cyl('pt_filter_logo', 0.020, f0 + FILTER_DIR * 0.257, f0 + FILTER_DIR * 0.259, mt['alu'], segs=16))

    # ---- r6: thin (5.6 mm) braided boost-reference line (rear.png right: from a barb on the runner bank's outer face,
    # up over the fuel rail and the coil cover's inner top edge, then out and down to a nipple on the compressor cover)
    nip = TP(0.024, 0.101, math.radians(68))
    nd = (nip - TP(0.024)).normalized()
    S.append(cyl('pt_ref_nipple', 0.0042, nip - nd * 0.004, nip + nd * 0.012, mt['alu'], segs=6, sharp=30))
    S.append(cyl('pt_ref_barb', 0.0045, V((-0.130, -1.960, 1.012)), V((-0.142, -1.960, 1.026)), mt['alu'], segs=6, sharp=30))
    S.append(hose('pt_boost_ref', [V((-0.140, -1.960, 1.024)), V((-0.158, -1.962, 1.042)), V((-0.200, -1.966, 1.056)),
                                   V((-0.262, -1.968, 1.066)), V((-0.315, -1.966, 1.064)), V((-0.372, -1.962, 1.047)),
                                   V((-0.430, -1.955, 1.030)), nip + nd * 0.040, nip + nd * 0.010], 0.0028, mt['braid'],
                  sides=6, steps=4))

    # ---- wastegate on the collector (outboard) + dump tube back to an open end facing the rear (rear.png left)
    wg = COLL + V((-0.058, -0.030, 0.070))
    wdir = V((-0.45, -0.35, 0.82)).normalized()
    S.append(cyl('pt_wg_stub', 0.022, COLL + V((-0.02, -0.015, 0.055)), wg, mt['stainless'], segs=14))
    S.append(lathe_at('pt_wastegate', [(0.0, 0.0), (0.030, 0.0), (0.034, 0.012), (0.034, 0.040), (0.040, 0.046),
                                       (0.040, 0.058), (0.030, 0.066), (0.0, 0.068)], wg, wdir, mt['satin'], segs=20))
    S.append(cyl('pt_wg_cap', 0.012, wg + wdir * 0.066, wg + wdir * 0.075, mt['alu'], segs=10))
    dpath = smooth_path([wg + V((0.004, -0.022, -0.010)), wg + V((-0.004, -0.060, 0.000)),
                         V((wg.x - 0.002, -2.12, 0.765)), V((wg.x + 0.008, -2.170, 0.785))], 5)
    S.append(sweep('pt_dump_tube', dpath, 0.027, mt['ceramic'], sides=16, cap1=False))
    S += tip('pt_dump_tip', dpath[-1], dpath[-1] - dpath[-2], 0.027, mt)

    # ---- 4" downpipe: turbine outlet (facing the rear) -> back, then inboard and down to the rear centre,
    # ending behind the bumper V (rear.png)
    o0 = TP(-0.123)
    # (rear.png: a straight diagonal in front of the rear side diagonal, over the PS pulley and belt, and in
    # behind the water-pump pulley at the centre)
    # r4: the middle points slide toward the rear.png camera along its sight lines (same image position) so the
    # belt-plane pulleys / coolant drop sit behind the pipe as in the photo
    cam = V((-0.0444, -3.8638, 1.8692))
    dpk = [V((-0.500, -2.110, 0.904)), V((-0.410, -2.165, 0.896)), V((-0.300, -2.205, 0.880)),
           V((-0.200, -2.248, 0.858)), V((-0.120, -2.280, 0.835)), V((-0.075, -2.300, 0.806)),
           V((-0.058, -2.312, 0.768)), V((-0.052, -2.316, 0.728))]
    dpk = [p + (cam - p).normalized() * k for p, k in zip(dpk, (0.005, 0.015, 0.028, 0.030, 0.022, 0.012, 0.004, 0.0))]
    dp = smooth_path([o0, o0 - A * 0.030] + dpk, 4)
    S.append(sweep('pt_downpipe', dp, 0.051, mt['ceramic'], sides=18, cap1=False))
    S += tip('pt_dp_tip', dp[-1], dp[-1] - dp[-2], 0.051, mt, depth=0.05)
    p, t = path_at(dp, 0.10)
    S.append(ring_band('pt_dp_band', p, t, 0.054, 0.016, mt['alu'], segs=24))

    # ---- charge pipe: compressor outlet -> up and inboard (coupler), then up and inboard beside the plenum
    # (upper coupler, rear.png) -> forward along the top -> Y in front of the throttle body
    # (stays inboard of / under the body pod's inner wall: x .467, bottom z ~1.10 behind y -1.8)
    # r5: 3-4 cm further inboard (rear.png centre line (535, 450) / (560, 415) / coupler (583, 382)) and down to
    # z <= 1.142 under the NEW chassis cross tube (spec REAR_XBAR_YZ y -1.68 z 1.21, r .0222: >= 2 cm air); the upper
    # coupler sits just behind that tube, its T-bolts facing inboard (photo: bright clamp hardware on the inner side)
    # r6: starts inside the end of the orange discharge elbow (over the compressor top, heading inboard)
    e1, et = path_at(DP, path_len(DP))
    cp = smooth_path([e1 - et * 0.022, e1, e1 + et * 0.040 + V((0, 0, 0.010)), V((-0.392, -1.808, 1.084)),
                      V((-0.347, -1.792, 1.106)), V((-0.312, -1.757, 1.124)), V((-0.287, -1.705, 1.136)),
                      V((-0.262, -1.625, 1.141)), V((-0.238, -1.520, 1.134)), V((-0.198, -1.405, 1.100)),
                      V((-0.120, -1.330, TB_Z + 0.006)), V((-0.045, -1.318, TB_Z + 0.002)),
                      V((-0.002, -1.330, TB_Z))], 3)
    S.append(sweep('pt_charge_pipe', cp, 0.032, mt['pipe'], sides=14))
    st = s_near(cp, e1 + et * 0.040)
    S += coupler('pt_cp_coupler_low', cp, st + 0.006, st + 0.072, 0.032, mt, bolt_dir=(0.0, -1.0, 0.0))
    st = s_near(cp, (-0.315, -1.762, 1.122))
    S += coupler('pt_cp_coupler_top', cp, st - 0.034, st + 0.034, 0.032, mt, bolt_dir=(1.0, -0.35, 0.15))


def build_charge_y(mt, S):
    """Y stem from the merge to the throttle body + blow-off valve (centre, not mirrored)."""
    tb_in = V((0.0, PY1 + 0.086, TB_Z))
    stem = [V((0.0, -1.335, TB_Z)), V((0.0, -1.42, TB_Z)), tb_in + V((0, 0.012, 0))]
    stem = smooth_path(stem, 3)
    S.append(sweep('pt_charge_stem', stem, 0.044, mt['pipe'], sides=24))
    S.append(lathe_at('pt_charge_merge', [(0.0, 0.0), (0.044, 0.0), (0.050, 0.02), (0.052, 0.05), (0.046, 0.075),
                                          (0.0, 0.08)], V((0.0, -1.30, TB_Z)), (0, -1, 0), mt['pipe'], segs=24))
    sp = [tb_in + V((0, 0.07, 0)), tb_in + V((0, -0.0, 0))]
    S += coupler('pt_tb_coupler', [sp[0], sp[1]], 0.0, 0.07, 0.046, mt)
    # blow-off valve on the stem (black body, alu cap)
    bov = V((0.035, -1.47, TB_Z + 0.036))
    S.append(cyl('pt_bov_stub', 0.016, (0.0, -1.47, TB_Z + 0.015), bov, mt['pipe'], segs=14))
    S.append(lathe_at('pt_bov', [(0.0, 0.0), (0.026, 0.0), (0.028, 0.012), (0.028, 0.040), (0.022, 0.052), (0.0, 0.054)],
                      bov, (0.5, 0.0, 0.86), mt['satin'], segs=18))


def build_transaxle(mt, L, S):
    """Orange bellhousing, VW-style transaxle (diff on the axle line), output flanges, starter, shift cables."""
    def bell_ring(y):
        # interpolate between the flange shape and the case shape
        t = min(1.0, max(0.0, (y - YB) / (-1.415 - YB)))
        a = [(0.0, 0.815), (0.17, 0.785), (0.232, 0.67), (0.222, 0.55), (0.17, 0.46), (0.09, 0.425), (0.0, 0.42)]
        b = [(0.0, 0.655), (0.10, 0.645), (0.122, 0.585), (0.112, 0.52), (0.092, 0.45), (0.06, 0.412), (0.0, 0.405)]
        s = t * t * (3 - 2 * t)
        half = [(a[i][0] * (1 - s) + b[i][0] * s, a[i][1] * (1 - s) + b[i][1] * s) for i in range(len(a))]
        ring = [(x, z) for (x, z) in reversed(half)] + [(-x, z) for (x, z) in half[1:-1]]
        return rounded_poly(ring, 0.02, 2)
    ys = [YB, YB + 0.012, YB + 0.014, -1.54, -1.50, -1.46, -1.43, -1.415]
    S.append(section_loft('pt_bellhousing', ys, bell_ring, mt['orange'], sharp=40))
    # flange bolt circle
    fr = bell_ring(YB)
    for k in range(0, len(fr), 3):
        x, z = fr[k]
        c = V((x * 0.93, YB + 0.014, ZC + (z - ZC) * 0.93))
        S.append(hexnut('pt_bell_bolt', c, (0, 1, 0), 0.0075, 0.008, mt['alu']))
    # diff housing on the axle line + output flanges at x = +-0.15..0.18 (CV joints start at |x| = 0.18)
    S.append(lathe_at('pt_diff', [(0.0, -0.142), (0.070, -0.142), (0.090, -0.125), (0.098, -0.09), (0.098, 0.09),
                                  (0.090, 0.125), (0.070, 0.142), (0.0, 0.142)], DIFF * V((0, 1, 1)) + V((0, 0, 0)),
                      (1, 0, 0), mt['case'], segs=28))
    for sx in (-1, 1):
        c0 = V((sx * 0.140, DIFF.y, DIFF.z))
        S.append(cyl('pt_out_stub', 0.046, c0, c0 + V((sx * 0.012, 0, 0)), mt['case'], segs=20))
        S.append(lathe_at('pt_out_flange', [(0.0, 0.0), (0.052, 0.0), (0.056, 0.004), (0.056, 0.021), (0.050, 0.025),
                                            (0.0, 0.025)], c0 + V((sx * 0.012, 0, 0)), (sx, 0, 0), mt['steel'], segs=24))
        for k in range(6):
            a = 2 * math.pi * k / 6 + 0.3
            p = c0 + V((sx * 0.026, 0.044 * math.cos(a), 0.044 * math.sin(a)))
            S.append(hexnut('pt_cv_bolt', p, (sx, 0, 0), 0.0050, 0.008, mt['alu']))
    # gear case forward to the firewall, with ribs and an end cover
    def case_ring(y):
        rib = 0.006 if any(abs(y - yr) < 0.009 for yr in (-1.33, -1.22, -1.11)) else 0.0
        w = 0.118 - 0.008 * (y + 1.415) / 0.37 + rib
        return rounded_poly([(-w, 0.392 - rib), (w, 0.392 - rib), (w, 0.652 + rib), (-w, 0.652 + rib)], 0.035, 3)
    cys = [-1.416, -1.338, -1.333, -1.327, -1.322, -1.228, -1.223, -1.217, -1.212, -1.118, -1.113, -1.107, -1.102,
           -1.045]
    S.append(section_loft('pt_gear_case', cys, case_ring, mt['case'], sharp=40))
    S.append(section_loft('pt_case_cover', [-1.045, -1.032],
                          lambda y: rounded_poly([(-0.108, 0.40), (0.108, 0.40), (0.108, 0.645), (-0.108, 0.645)],
                                                 0.03, 3), mt['banod'], sharp=40))
    for (x, z) in ((-0.09, 0.42), (0.09, 0.42), (-0.09, 0.625), (0.09, 0.625), (0.0, 0.42), (0.0, 0.625)):
        S.append(hexnut('pt_cover_bolt', (x, -1.032, z), (0, 1, 0), 0.006, 0.006, mt['alu']))
    # side plate (right) and shift tower with cables to the cockpit
    S.append(bbox('pt_case_side', (0.012, 0.20, 0.17), (0.126, -1.23, 0.52), mt['banod'], bevel=0.004))
    S.append(bbox('pt_shift_tower', (0.07, 0.07, 0.05), (-0.03, -1.09, 0.672), mt['case'], bevel=0.008))
    for dx in (-0.05, -0.01):
        S.append(hose('pt_shift_cable', [(dx, -1.085, 0.69), (dx, -1.04, 0.735), (dx - 0.02, -0.985, 0.745),
                                         (dx - 0.04, -0.952, 0.75), (dx - 0.045, -0.94, 0.75)], 0.0065, mt['hose'],
                      sides=6))
        S.append(cyl('pt_shift_grommet', 0.012, (dx - 0.045, -0.936, 0.75), (dx - 0.045, -0.944, 0.75),
                     mt['rubber'], segs=10))
    # starter on the bellhousing (right, high)
    st0 = V((0.19, -1.565, 0.668))
    S.append(lathe_at('pt_starter', [(0.0, 0.0), (0.040, 0.0), (0.044, 0.008), (0.044, 0.15), (0.038, 0.16), (0.0, 0.16)],
                      st0, (0, 1, 0), mt['satin'], segs=20))
    S.append(cyl('pt_starter_sol', 0.022, st0 + V((-0.02, 0.03, 0.05)), st0 + V((-0.02, 0.13, 0.05)), mt['alu'], segs=14))
    S.append(hose('pt_starter_cable', [st0 + V((-0.02, 0.13, 0.07)), (0.17, -1.33, 0.75), (0.19, -1.25, 0.66),
                                       (0.20, -1.13, 0.59), (0.20, -1.02, 0.566), (0.20, -0.975, 0.565),
                                       (0.20, -0.944, 0.565)], 0.0085, mt['hose'], sides=8))


def build_cooling(mt, L, S):
    """Radiator leaning behind the firewall, twin-fan shroud, filler, hoses, coolant hard pipe to the pump."""
    c = V((0.0, -1.064, 0.862))
    up = V((0.0, 0.5, 0.866))
    nrm = V((0.0, -0.866, 0.5))           # rear face direction
    xw, hh, th = 0.255, 0.165, 0.052
    core = oriented_box('pt_rad_core', (2 * xw, 2 * hh, th), c, (1, 0, 0), up, mt['core'], bevel=0.002)
    inv = core.matrix_basis.inverted()

    def ruv(co, nn):
        lc = inv @ co
        return (lc.x / 0.085, lc.y / 0.085)
    uv_project(core, ruv)
    S.append(core)
    for sx in (-1, 1):
        S.append(oriented_box('pt_rad_tank', (0.042, 2 * hh + 0.02, th + 0.012), c + V((sx * (xw + 0.021), 0, 0)),
                              (1, 0, 0), up, mt['alu'], bevel=0.008, segs=2))
        S.append(cyl('pt_rad_mount', 0.010, c + V((sx * (xw + 0.021), 0, 0)) - up * (hh + 0.01),
                     c + V((sx * (xw + 0.021), 0, 0)) - up * (hh + 0.05), mt['rubber'], segs=10))
    S.append(oriented_box('pt_rad_frame_top', (2 * xw, 0.012, th + 0.004), c + up * (hh + 0.006), (1, 0, 0), up,
                          mt['alu'], bevel=0.002))
    S.append(oriented_box('pt_rad_frame_bot', (2 * xw, 0.012, th + 0.004), c - up * (hh + 0.006), (1, 0, 0), up,
                          mt['alu'], bevel=0.002))
    # filler neck + cap on the right tank top
    fn = c + V((xw + 0.021, 0, 0)) + up * (hh + 0.02)
    S.append(cyl('pt_rad_filler', 0.016, fn - up * 0.01, fn + up * 0.025, mt['alu'], segs=16))
    S.append(cyl('pt_rad_cap', 0.024, fn + up * 0.025, fn + up * 0.038, mt['polished'], segs=20))
    # fan shroud (black) on the rear face with two fans
    sc = c + nrm * (th / 2 + 0.022)
    S.append(oriented_box('pt_shroud_plate', (2 * xw + 0.03, 2 * hh + 0.02, 0.006), sc + nrm * 0.018, (1, 0, 0), up,
                          mt['satin'], bevel=0.003))
    for sx in (-1, 1):
        S.append(oriented_box('pt_shroud_side', (0.006, 2 * hh + 0.02, 0.040), sc + V((sx * (xw + 0.012), 0, 0)),
                              (1, 0, 0), up, mt['satin'], bevel=0.002))
    for sx in (-0.125, 0.125):
        fc = sc + V((sx, 0, 0)) + nrm * 0.022
        S.append(lathe_at('pt_fan_ring', [(0.118, -0.012), (0.126, -0.012), (0.126, 0.030), (0.118, 0.030),
                                          (0.118, -0.012)], fc, nrm, mt['satin'], segs=24))
        S.append(lathe_at('pt_fan_motor', [(0.0, 0.0), (0.040, 0.0), (0.042, 0.010), (0.042, 0.040), (0.036, 0.048),
                                           (0.0, 0.050)], fc + nrm * 0.010, nrm, mt['satin'], segs=20))
        S.append(lathe_at('pt_fan_hub', [(0.0, -0.01), (0.034, -0.01), (0.034, 0.012), (0.0, 0.016)], fc, nrm,
                          mt['gloss'], segs=16))
        # struts from the motor to the ring
        for k in range(4):
            a = math.radians(45 + 90 * k)
            ex = V((math.cos(a), 0, 0)) + up * math.sin(a)
            S.append(cyl('pt_fan_strut', 0.004, fc + nrm * 0.035 + ex * 0.04, fc + nrm * 0.03 + ex * 0.12, mt['satin'],
                         segs=6))
        # blades
        for k in range(7):
            a = 2 * math.pi * k / 7
            ex = V((math.cos(a), 0, 0)) + up * math.sin(a)
            ey = nrm.cross(ex).normalized()
            S.append(oriented_box('pt_fan_blade', (0.080, 0.034, 0.003), fc + ex * 0.075 - nrm * 0.002, ex,
                                  ey * 0.9 + nrm * 0.45, mt['satin']))
    # lower hose outlet (left tank bottom) -> grey hard pipe down the left of the bay -> water pump inlet
    out0 = c + V((-(xw + 0.040), 0, 0)) - up * (hh - 0.04)
    out1 = out0 + V((-0.025, -0.013, 0.011))
    # runs back over the left coil cover (under the charge pipe) and drops behind the plenum to the pump
    # r4: in the valley between the (taller) left coil cover and the runner bank / fuel rail, then down behind the
    # cover's rounded rear end and outboard of the alternator to the pump
    cp = smooth_path([out0, out1, V((-0.31, -1.26, 0.86)), V((-0.316, -1.42, 0.965)), V((-0.276, -1.58, 1.020)),
                      V((-0.262, -1.72, 1.032)), V((-0.258, -1.85, 1.034)), V((-0.258, -1.98, 1.032))]
                     + COOLANT_TAIL, 3)
    S.append(sweep('pt_coolant_pipe', cp, 0.020, mt['pipe'], sides=12))
    S += coupler('pt_coolant_hose', cp + [V((-0.092, -2.184, 0.873))], path_len(cp) - 0.016,
                 path_len(cp) + 0.024, 0.021, mt)
    S += coupler('pt_coolant_hose_rad', cp, 0.0, 0.06, 0.021, mt, clamps=True)


def build_canisters(mt, L, S):
    """Oil tank (right), catch can (left), finned + plain canisters by the B-pillars, fire bottle, brackets."""
    # finned canisters (fuel filter / shock-reservoir style) - both sides, tilted back a little
    for side in (-1, 1):
        lst = S
        b0 = V((side * 0.470, -1.138, 0.975))
        ax = V((side * 0.02, -0.15, 1.0)).normalized()
        prof = [(0.0, 0.0), (0.038, 0.0), (0.042, 0.008), (0.042, 0.024)]
        nf = 8
        for k in range(nf):
            h = 0.034 + k * 0.0238
            prof += [(0.048, h + 0.002), (0.048, h + 0.010), (0.042, h + 0.013)]
        prof += [(0.042, 0.236), (0.038, 0.245), (0.0, 0.245)]
        lst.append(lathe_at('pt_fin_can', prof, b0, ax, mt['fins'], segs=16))
        lst.append(cyl('pt_fin_can_cap', 0.030, b0 + ax * 0.244, b0 + ax * 0.262, mt['banod'], segs=20))
        lst.append(cyl('pt_fin_can_fit', 0.011, b0 + ax * 0.262, b0 + ax * 0.284, mt['banod'], segs=6))
        lst.append(cyl('pt_fin_can_base', 0.012, b0, b0 - ax * 0.02, mt['banod'], segs=6))
        # plain canister with brass Schrader valve (shock-reservoir style)
        p0 = V((side * 0.462, -1.008, 0.972))
        ax2 = V((side * 0.03, -0.10, 1.0)).normalized()
        lst.append(lathe_at('pt_res_can', [(0.0, 0.0), (0.033, 0.0), (0.036, 0.006), (0.036, 0.222), (0.033, 0.229),
                                           (0.0, 0.229)], p0, ax2, mt['banod'], segs=20))
        lst.append(cyl('pt_res_cap', 0.026, p0 + ax2 * 0.229, p0 + ax2 * 0.243, mt['banod'], segs=18))
        lst.append(cyl('pt_res_valve', 0.0065, p0 + ax2 * 0.243, p0 + ax2 * 0.265, mt['brass'], segs=8))
        lst.append(ring_band('pt_res_band', p0 + ax2 * 0.06, ax2, 0.0385, 0.014, mt['alu'], segs=20))
        lst.append(ring_band('pt_res_band', p0 + ax2 * 0.16, ax2, 0.0385, 0.014, mt['alu'], segs=20))
        lst.append(hose('pt_res_hose', [p0 + V((0, 0, 0.02)) - ax2 * 0.005, p0 + V((side * 0.03, -0.03, -0.03)),
                                        V((side * 0.53, -1.13, 0.96)), V((side * 0.56, -1.12, 0.93))],
                        0.0075, mt['hose'], sides=8))
        # bracket plate under the tank / canisters, strut down to the radius-rod post
        lst.append(oriented_box('pt_can_bracket', (0.20, 0.22, 0.006), V((side * 0.405, -1.075, 0.962)), (1, 0, 0),
                                (0, 1, 0), mt['pipe'], bevel=0.002))
        lst.append(cyl('pt_can_strut', 0.008, (side * 0.48, -1.17, 0.958), (side * 0.388, -1.222, 0.80), mt['pipe'],
                       segs=8))

    # dry-sump oil tank (right): black anodized, polished cap, breather fitting, AN fittings
    t0 = V((0.335, -1.045, 0.965))
    prof = [(0.0, 0.0), (0.048, 0.0), (0.054, 0.010), (0.054, 0.205), (0.048, 0.218), (0.030, 0.222), (0.0, 0.222)]
    S.append(lathe_at('pt_oil_tank', prof, t0, (0, 0, 1), mt['banod'], segs=28))
    S.append(ring_band('pt_tank_band', t0 + V((0, 0, 0.05)), (0, 0, 1), 0.056, 0.014, mt['alu'], segs=24))
    S.append(ring_band('pt_tank_band', t0 + V((0, 0, 0.16)), (0, 0, 1), 0.056, 0.014, mt['alu'], segs=24))
    S.append(lathe_at('pt_tank_cap', [(0.0, 0.0), (0.028, 0.0), (0.030, 0.006), (0.030, 0.018), (0.024, 0.024),
                                      (0.0, 0.025)], t0 + V((0, 0, 0.222)), (0, 0, 1), mt['polished'], segs=20))
    # r5: breather moved from the top to the outboard side wall near the top and the vent dropped under the body's
    # lowered engine cover (its skirt at |x| 0.40 comes down to 1.18 @ y -1.05 .. 1.10 @ y -1.25)
    S.append(cyl('pt_tank_breather', 0.0095, t0 + V((0.050, 0.0, 0.185)), t0 + V((0.068, 0.0, 0.185)), mt['alu'],
                 segs=8))
    S.append(hose('pt_tank_vent', [t0 + V((0.066, 0.0, 0.185)), (0.411, -1.050, 1.149), (0.414, -1.076, 1.128),
                                   (0.406, -1.12, 1.078), (0.397, -1.158, 1.02), (0.395, -1.165, 0.972)],
                  0.0065, mt['braid'], sides=8))
    # catch can (left): black with a black screw cap, breather hoses from the valve covers
    k0 = V((-0.355, -1.000, 0.990))
    S.append(lathe_at('pt_catch_can', [(0.0, 0.0), (0.040, 0.0), (0.044, 0.008), (0.044, 0.12), (0.040, 0.128),
                                       (0.0, 0.128)], k0, (0, 0, 1), mt['banod'], segs=24))
    S.append(lathe_at('pt_catch_cap', [(0.0, 0.0), (0.049, 0.0), (0.050, 0.004), (0.050, 0.022), (0.046, 0.026),
                                       (0.0, 0.027)], k0 + V((0, 0, 0.128)), (0, 0, 1), mt['gloss'], segs=24))
    for side in (-1, 1):
        p = bank_pt(side, 0.405, 0.0, -1.617)
        S.append(cyl('pt_vc_breather', 0.010, p, p + V((0, 0.03, 0)), mt['alu'], segs=8))
        S.append(hose('pt_breather_hose', [p + V((0, 0.03, 0)), p + V((0, 0.08, 0.03)),
                                           V((-0.25, -1.40, 0.99)) if side < 0 else V((0.30, -1.36, 1.00)),
                                           V((-0.30, -1.20, 1.04)) if side < 0 else V((0.33, -1.16, 1.04)),
                                           V((-0.33, -1.08, 1.08)) if side < 0 else V((0.0, -1.12, 1.10)),
                                           k0 + V((0.03, 0.01 * side, 0.21)), k0 + V((0.02, 0.012 * side, 0.155))],
                      0.0085, mt['hose'],
                      sides=6))
    # fire bottle (polished, red head) low behind the firewall
    fb0, fb1 = V((-0.15, -0.992, 0.668)), V((0.12, -0.992, 0.668))
    S.append(lathe_at('pt_fire_bottle', [(0.0, 0.0), (0.030, 0.0), (0.042, 0.015), (0.045, 0.04), (0.045, 0.24),
                                         (0.040, 0.26), (0.020, 0.27), (0.0, 0.27)], fb0, fb1 - fb0, mt['polished'],
                      segs=24))
    S.append(cyl('pt_fire_head', 0.020, fb0 - V((0.03, 0, 0)), fb0, mt['red'], segs=14))
    for x in (-0.08, 0.06):
        S.append(ring_band('pt_fire_strap', (x, -0.992, 0.668), (1, 0, 0), 0.047, 0.012, mt['satin'], segs=20))


# ------------------------------------------------------------------ main

def build(C):
    import common as _common
    orig_shade = _common.shade
    _common.shade = shade_fixed            # only for the objects created by this part
    try:
        _build(C)
    finally:
        _common.shade = orig_shade


def _build(C):
    ensure_textures()
    mt = mats()
    L, S = [], []                  # L: left-side pieces to mirror; S: done
    build_block(mt, L, S)
    build_intake(mt, L, S)
    build_accessories(mt, L, S)
    HT = []
    build_headers_turbo(mt, L, HT)
    build_charge_y(mt, S)
    build_transaxle(mt, L, S)
    build_cooling(mt, L, S)
    build_canisters(mt, L, S)
    # mirror the left-side pieces; the headers/turbo use the right bank's cylinder offset by shifting y
    right = [mirror_x(o, o.name + '_R') for o in L]
    hr = []
    for o in HT:
        c = mirror_x(o, o.name + '_R')
        hr.append(c)
    # right bank cylinders are 22 mm forward of the left ones: shift the right headers' primaries only
    dy = CYL_Y[1][0] - CYL_Y[-1][0]
    for c in hr:
        if c.name.startswith('pt_primary'):
            for v in c.data.vertices:
                # blend the shift to zero toward the collector so the bundle still meets it
                t = max(0.0, min(1.0, (v.co.z - 0.665) / 0.06))
                v.co.y += dy * t
    for o in S + L + right + HT + hr:
        C.add(o, 'static')
