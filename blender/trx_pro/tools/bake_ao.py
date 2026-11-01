"""Bake ambient occlusion into the GLX game asset and re-export the GLB.

    python tools/bake_ao.py --blend out/trx_sandrail.blend --glb out/sandcar.glb

    options: --samples 64       Cycles AO samples per vertex (noise is smoothed afterwards)
             --distance 1.4     AO ray length in metres (cockpit-sized, so the tub/roof/dash shade
                                the interior but open body panels stay bright)
             --max-edge 0.2     edges longer than this are split before baking, so the per-vertex AO
                                has enough resolution on long tubes and big flat panels
             --smooth 2         vertex-graph smoothing passes after the bake
             --out-blend PATH   also save the baked scene (vertex colour 'AO_preview') for inspection
             --threads 4
             --cabin-floor 0.08 lowest AO inside the cockpit box CABIN_BOX (soft 5 cm edges); 0 = off
             --fix-below 0.08   cockpit vertices that Cycles baked darker than this are re-sampled ...
             --fix-rays 96      ... with this many cosine rays (BVH ray casts) whose origin is lifted
             --ray-offset 0.004 this far along the vertex normal, ignoring hits closer than
             --min-hit 0.005    this; the larger of the two values is kept

Runs in about 1.5 minutes on 4 CPU cores (the Cycles bake of ~0.2 M vertices ~50 s, the cockpit re-sample
~35 s single-threaded; the GLB grows by ~2.4 MB: the AO attribute + the split edges). Safe to run more than once on the same
.blend (the .blend itself is never saved unless --out-blend is given).

What it does
  1. opens the built .blend (build.py output: same objects / node names as the GLB) and applies any
     modifiers (the export applies them too, and the bake needs the final topology);
  2. splits long edges (normals are preserved through a temporary corner attribute);
  3. bakes Cycles AO (the whole car occludes itself; no ground plane: the sand's bounce light in
     the game comes from below and must keep reaching the underside) into a per-vertex colour;
  3b. [integration r6] cockpit fix: Cycles starts each AO ray exactly at the vertex, so a decal quad whose
     corners tuck a millimetre into its bezel (keypad face 'Interior switch panel', the kick-panel
     'Interior hex mesh dark') baked 0.000 - black in the game. Cockpit vertices that baked < --fix-below
     are re-sampled with BVH rays lifted --ray-offset along the normal that ignore hits closer than
     --min-hit; then (after smoothing) the cockpit box gets an AO floor
     --cabin-floor (keypad face 0.000 -> ~0.15, the radio face's level);
  4. the parts that spin are made rotationally symmetric: Wheel_XX_Mesh is averaged around the
     axle and SteeringWheel_Mesh around the column, so no shadow rotates with them;
  5. smooths the result over the mesh graph and stores it as the float point attribute `_AO`
     (0 = fully occluded, 1 = open sky) which the glTF exporter writes as the custom vertex
     attribute `_AO` (three.js: geometry.attributes._ao);
  6. re-exports the GLB through build.export_glb (identical export settings and node contract,
     plus export_attributes=True so `_AO` is written).

Game side (glamis-game/public/js/gltf-sandrail.js, patchMaterial / LOOKS): the `_ao` attribute
scales the indirect light (hemisphere + environment diffuse AND environment / clear-coat reflections,
like a three.js aoMap, plus a little of the direct light in deep cavities where the coarse sun shadow
map leaks) through an onBeforeCompile patch; the same patch desaturates the blue sky light and holds
the per-material tuning of the GLX (CARS.pro.look = 'trx'). Cars without `_ao` and without a look
are untouched. Check a bake in the game without installing it:
    node tools/game_shots.mjs renders/game test_ --glb out/sandcar.glb --views chase_f3q,cockpit
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import bmesh  # noqa: E402
import numpy as np  # noqa: E402

AO_ATTR = '_AO'
BAKE_ATTR = 'AO_bake'
# [integration r6] the cockpit (world/Blender frame: x right, y forward, z up), from the cockpit critic
CABIN_BOX = ((-0.75, 0.75), (-0.7, 1.0), (0.45, 1.5))
CABIN_EDGE = 0.05


def log(*a):
    print('[bake_ao]', *a, flush=True)


def mesh_objects():
    return [o for o in bpy.context.scene.objects if o.type == 'MESH' and len(o.data.polygons)]


def corner_normals(me):
    n = np.zeros(len(me.loops) * 3, dtype=np.float32)
    if hasattr(me, 'corner_normals'):
        me.corner_normals.foreach_get('vector', n)
    else:  # Blender < 4.1
        me.calc_normals_split()
        me.loops.foreach_get('normal', n)
    return n.reshape(-1, 3)


def apply_modifiers(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for o in objs:
        if o.modifiers:
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
            o.modifiers.clear()
            o.data = me
            n += 1
    return n


def refine(o, max_edge):
    """Split edges longer than max_edge (a few passes of bisection) keeping the shading normals."""
    me = o.data
    co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    ev = np.zeros(len(me.edges) * 2, dtype=np.int64); me.edges.foreach_get('vertices', ev); ev = ev.reshape(-1, 2)
    if not len(ev) or np.linalg.norm(co[ev[:, 0]] - co[ev[:, 1]], axis=1).max() <= max_edge:
        return 0
    t0 = len(me.polygons)
    tmp = me.attributes.new('_tmp_n', 'FLOAT_VECTOR', 'CORNER')
    tmp.data.foreach_set('vector', corner_normals(me).ravel())
    bm = bmesh.new()
    bm.from_mesh(me)
    for _ in range(8):
        long = [e for e in bm.edges if e.calc_length() > max_edge]
        if not long:
            break
        bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=True, use_single_edge=False)
    bm.to_mesh(me)
    bm.free()
    tmp = me.attributes['_tmp_n']
    n = np.zeros(len(me.loops) * 3, dtype=np.float32)
    tmp.data.foreach_get('vector', n)
    me.attributes.remove(tmp)
    n = n.reshape(-1, 3)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-8)
    me.normals_split_custom_set(n.tolist())
    me.update()
    return len(me.polygons) - t0


def vertex_neighbours(me):
    ev = np.zeros(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get('vertices', ev)
    return ev.reshape(-1, 2)


def smooth(ao, edges, passes):
    if not len(edges):
        return ao
    n = len(ao)
    deg = np.bincount(edges.ravel(), minlength=n).astype(np.float64)
    for _ in range(passes):
        s = np.bincount(edges[:, 0], weights=ao[edges[:, 1]], minlength=n) + \
            np.bincount(edges[:, 1], weights=ao[edges[:, 0]], minlength=n)
        nb = np.where(deg > 0, s / np.maximum(deg, 1), ao)
        ao = 0.5 * ao + 0.5 * nb
    return ao


def rotational_average(co, ao, axis, bin_m=0.004):
    """Average AO over rings around `axis` (0=x, 1=y, 2=z) through the local origin."""
    a = co[:, axis]
    r = np.linalg.norm(np.delete(co, axis, axis=1), axis=1)
    key = np.round(a / bin_m).astype(np.int64) * 100003 + np.round(r / bin_m).astype(np.int64)
    _, inv = np.unique(key, return_inverse=True)
    inv = inv.ravel()
    s = np.bincount(inv, weights=ao)
    c = np.bincount(inv)
    return (s / c)[inv]


def world_coords(o):
    me = o.data
    co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    no = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('normal', no); no = no.reshape(-1, 3)
    mw = np.array(o.matrix_world)
    r = mw[:3, :3]
    wn = no @ np.linalg.inv(r)  # normals: inverse-transpose
    wn /= np.maximum(np.linalg.norm(wn, axis=1, keepdims=True), 1e-9)
    return co @ r.T + mw[:3, 3], wn


def cabin_weight(p):
    """1 inside CABIN_BOX, 0 outside, smoothstep over CABIN_EDGE inside each face of the box."""
    w = np.ones(len(p))
    for ax, (lo, hi) in enumerate(CABIN_BOX):
        t = np.clip(np.minimum(p[:, ax] - lo, hi - p[:, ax]) / CABIN_EDGE, 0.0, 1.0)
        w *= t * t * (3 - 2 * t)
    return w


def scene_bvh(objs):
    from mathutils.bvhtree import BVHTree
    V, F, off = [], [], 0
    for o in objs:
        me = o.data
        co, _ = world_coords(o)
        me.calc_loop_triangles()
        tri = np.zeros(len(me.loop_triangles) * 3, np.int64); me.loop_triangles.foreach_get('vertices', tri)
        V.append(co); F.append(tri.reshape(-1, 3) + off); off += len(co)
    V = np.concatenate(V); F = np.concatenate(F)
    return BVHTree.FromPolygons(V.tolist(), F.tolist(), all_triangles=True, epsilon=0.0)


def offset_ao(bvh, p, n, nray, dist, off, min_hit, rng):
    """Unoccluded fraction of nray cosine-weighted rays from p + n*off (hits closer than min_hit to the
    origin are passed through)."""
    from mathutils import Vector
    a = np.array((1.0, 0, 0)) if abs(n[0]) < 0.9 else np.array((0, 1.0, 0))
    u = np.cross(n, a); u /= np.linalg.norm(u); v = np.cross(n, u)
    r1 = rng.random(nray); r2 = rng.random(nray)
    r = np.sqrt(r1); ph = 2 * np.pi * r2
    d = u[None] * (r * np.cos(ph))[:, None] + v[None] * (r * np.sin(ph))[:, None] + n[None] * np.sqrt(1 - r1)[:, None]
    o0 = Vector(p + n * off)
    free = 0
    for k in range(nray):
        dk = Vector(d[k]); ok = o0.copy(); travelled = 0.0; hit = False
        for _ in range(4):
            loc, hn, idx, dd = bvh.ray_cast(ok, dk, dist - travelled)
            if loc is None:
                break
            t = travelled + dd
            if t < min_hit:  # (a back face up to 2 cm away is NOT skipped: single-sided body skins seen
                #             from the cockpit are back faces and must keep shading the dash below them)
                ok = loc + dk * 1e-4; travelled = t + 1e-4
                continue
            hit = True
            break
        free += not hit
    return free / nray


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blend', default=os.path.join(ROOT, 'out', 'trx_sandrail.blend'))
    ap.add_argument('--glb', default=os.path.join(ROOT, 'out', 'sandcar.glb'))
    ap.add_argument('--samples', type=int, default=64)
    ap.add_argument('--distance', type=float, default=1.4)
    ap.add_argument('--max-edge', type=float, default=0.2)
    ap.add_argument('--smooth', type=int, default=2)
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--out-blend', default='')
    ap.add_argument('--no-export', action='store_true')
    ap.add_argument('--cabin-floor', type=float, default=0.08)
    ap.add_argument('--fix-below', type=float, default=0.08)
    ap.add_argument('--fix-rays', type=int, default=96)
    ap.add_argument('--ray-offset', type=float, default=0.004)
    ap.add_argument('--min-hit', type=float, default=0.005)
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])

    T0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(args.blend))
    objs = mesh_objects()
    log(f'{len(objs)} meshes, opened in {time.time() - T0:.1f}s')

    # 1. final topology + resolution for per-vertex AO
    if apply_modifiers(objs):
        objs = mesh_objects()
    t = time.time()
    added = 0
    for o in objs:
        added += refine(o, args.max_edge)
    log(f'refined long edges: +{added} faces in {time.time() - t:.1f}s')

    # 2. bake target
    for o in objs:
        me = o.data
        for a in list(me.color_attributes):
            if a.name in (BAKE_ATTR, 'AO_preview'):
                me.color_attributes.remove(a)
        if AO_ATTR in me.attributes:
            me.attributes.remove(me.attributes[AO_ATTR])
        ca = me.color_attributes.new(BAKE_ATTR, 'FLOAT_COLOR', 'POINT')
        me.color_attributes.active_color = ca

    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = args.samples
    try:
        sc.cycles.use_adaptive_sampling = False
        sc.cycles.use_denoising = False
    except Exception:
        pass
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = args.threads
    if sc.world is None:
        sc.world = bpy.data.worlds.new('World')
    sc.world.light_settings.distance = args.distance
    sc.render.bake.target = 'VERTEX_COLORS'

    for o in sc.objects:
        o.hide_render = o.type != 'MESH'
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    t = time.time()
    nverts = sum(len(o.data.vertices) for o in objs)
    log(f'baking AO: {nverts} vertices x {args.samples} samples, distance {args.distance} m ...')
    bpy.ops.object.bake(type='AO', target='VERTEX_COLORS')
    log(f'bake done in {time.time() - t:.1f}s')

    # 3. post-process and store as a float point attribute
    bvh = scene_bvh(objs) if args.fix_below > 0 and args.fix_rays > 0 else None
    rng = np.random.default_rng(6)
    nfix = [0, 0, 0.0]
    t = time.time()
    stats = []
    for o in objs:
        me = o.data
        ca = me.color_attributes[BAKE_ATTR]
        col = np.zeros(len(me.vertices) * 4, dtype=np.float32)
        ca.data.foreach_get('color', col)
        ao = col.reshape(-1, 4)[:, 0].astype(np.float64)
        co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        wco, wno = world_coords(o)
        wcab = cabin_weight(wco)
        if bvh is not None:  # 3b. re-sample the cockpit's dark vertices with lifted ray origins
            for i in np.nonzero((wcab > 0) & (ao < args.fix_below))[0]:
                a2 = offset_ao(bvh, wco[i], wno[i], args.fix_rays, args.distance, args.ray_offset, args.min_hit, rng)
                nfix[0] += 1
                if a2 > ao[i]:
                    nfix[1] += 1; nfix[2] += a2 - ao[i]
                    ao[i] = a2
        ao = smooth(ao, vertex_neighbours(me), args.smooth)
        if o.name.startswith('Wheel_'):           # spins about its local X (axle)
            ao = rotational_average(co, ao, 0)
        elif o.name == 'SteeringWheel_Mesh':      # turns about its local Z (column)
            ao = rotational_average(co, ao, 2)
        if args.cabin_floor > 0:
            ao = np.maximum(ao, args.cabin_floor * wcab)
        ao = np.clip(ao, 0.0, 1.0)
        me.color_attributes.remove(ca)
        at = me.attributes.new(AO_ATTR, 'FLOAT', 'POINT')
        at.data.foreach_set('value', ao.astype(np.float32))
        stats.append((o.name, len(ao), float(ao.mean()), float(np.percentile(ao, 5))))
    if bvh is not None:
        log(f'cockpit re-sample: {nfix[0]} vertices < {args.fix_below} ({args.fix_rays} rays, offset {args.ray_offset} m, '
            f'min hit {args.min_hit} m), {nfix[1]} raised (mean +{nfix[2] / max(1, nfix[1]):.3f}); floor {args.cabin_floor}; '
            f'{time.time() - t:.1f}s')
    for s in sorted(stats, key=lambda s: -s[1])[:12]:
        log(f'  {s[0]:24s} verts={s[1]:7d} mean={s[2]:.2f} p5={s[3]:.2f}')

    # 4. export with build.py's exporter settings + the custom attribute
    if not args.no_export:
        import build

        class _Proxy:
            def __init__(self, real, **over):
                self._real, self._over = real, over

            def __getattr__(self, k):
                return self._over[k] if k in self._over else getattr(self._real, k)

        real_gltf = bpy.ops.export_scene.gltf

        def gltf(**kw):
            kw['export_attributes'] = True
            return real_gltf(**kw)

        build.bpy = _Proxy(bpy, ops=_Proxy(bpy.ops, export_scene=_Proxy(bpy.ops.export_scene, gltf=gltf)))
        build.export_glb(os.path.abspath(args.glb))
        build.bpy = bpy
    if args.out_blend:  # inspection copy: AO also as a vertex colour (added after the export)
        for o in objs:
            me = o.data
            ao = np.zeros(len(me.vertices), dtype=np.float32)
            me.attributes[AO_ATTR].data.foreach_get('value', ao)
            pv = me.color_attributes.new('AO_preview', 'FLOAT_COLOR', 'POINT')
            c4 = np.repeat(ao[:, None], 4, axis=1); c4[:, 3] = 1
            pv.data.foreach_set('color', c4.ravel())
            me.color_attributes.active_color = pv
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.out_blend), compress=True)
        log('saved', args.out_blend)
    tris = 0
    for o in objs:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    log(f'triangles {tris}, total {time.time() - T0:.0f}s')


if __name__ == '__main__':
    main()
