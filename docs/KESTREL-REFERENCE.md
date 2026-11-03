# Kestrel 01: scripted aircraft pipeline

An original single-engine fighter study for Dunes, generated in Blender and
inspected as its actual GLB in Three.js. Built and verified on 2026-11-03.

Open **http://localhost:5189/jet.html** with `npm start` running.

## What transferred from the references

[Glamis](https://github.com/iotdatabase/glamis_game) supplies the established
Blender build/export approach and generic material, primitive, tube and mesh
joining helpers in `blender/trx_pro/common.py`. Its Unlicense is preserved.
The Kestrel aircraft surfaces, layout, cockpit, gear and articulation are new
source in this repository.

[ViperOneOne's jet notes](https://viperoneone.com/notes/jets/) informed the use of
an explicit dimensional specification, fuselage cross sections with interpolation
that preserves their shape, airfoil sections, a cockpit camera anchored to the
aircraft, and named articulated parts driven by normalized controls. The
[afterburner notes](https://viperoneone.com/notes/afterburner/) informed the
restrained orange glow recessed inside the nozzle. This viewer implements glow
and petal motion; it does not implement a flame plume or heat distortion.
No Viper source code, models, textures or shaders were copied.

General fighter proportions and visible construction were studied through
official [USAF F-16 photographs and description](https://www.af.mil/About-Us/Fact-Sheets/Display/Article/104505/f-16-fighting-falcon/)
and [NAVAIR's F-16 page](https://www.navair.navy.mil/product/F-16-Fighting-Falcon-Viper).
Kestrel is an authored design, not a dimensionally exact F-16 replica or
manufacturer CAD. The lettering and livery are original geometry/materials.

## Where to change the model

| Source | Responsibility |
| --- | --- |
| `blender/kestrel/jet_spec.py` | Fuselage, intake and canopy stations; wing/tail planforms; pilot eye; palette |
| `blender/kestrel/geometry.py` | Station interpolation, shell meshes, airfoil surfaces, text, grouping and pivots |
| `blender/kestrel/parts.py` | Fuselage details, intake, wings, fin, cockpit, landing gear, engine |
| `blender/kestrel/build.py` | Materials, assembly, editable scene, GLB and metadata export |
| `blender/kestrel/render.py` | Independent Cycles inspection views |
| `tools/jet_pipeline.py` | Repeatable CLI and copying the final export into viewer assets |
| `public/js/jet-viewer.js` | Loading, camera, articulation, materials, selection and inspection controls |

Blender uses metres, X right, Y forward, Z up. A fuselage station is
`(y, half_width, top_radius, bottom_radius, center_height)`. The asymmetric
vertical radii allow the belly and dorsal profile to vary independently.
Monotone cubic Hermite interpolation avoids the bulges an unconstrained spline
can introduce between those authored sections.

A wing row is `(span_x, leading_y, trailing_y, z, thickness_over_chord)`.
The generated upper and lower airfoil skins retain real thickness. Flaperons,
stabilators and rudder are separate meshes with explicit pivot nodes.
The cockpit and intake openings remove the underlying fuselage faces so the
interiors are visible rather than covered by an intact outer shell.

Each subsystem is joined under a named empty. GLB extras carry `system`,
`hingeAxis`, `travelDegrees` and `explode`. Those vectors are converted to glTF
coordinates `(x, z, -y)` before export. The viewer uses the original rest
transform plus rotation around the exported axis. It does not rediscover hinges
from mesh bounds. `PilotEye` and its metadata provide the cockpit camera anchor.

The Blender scene has editable meshes grouped by subsystem. Procedural source
remains the authoritative place to change dimensions and regenerate details.
Animation is applied by the viewer; the GLB preserves pivots but has no baked
animation clips or flight physics.

## Reproduce and iterate

The verified baseline is Blender 4.5.2 LTS, Python, Node.js, and installed Chrome
on Windows. The helper finds Blender 4.5 under Program Files; set `BLENDER` or
pass `--blender` to override it. On first setup, `npm run vehicle:setup` installs
the pinned Pillow dependency locally for the shared Glamis helper.

```powershell
npm ci
npm run vehicle:setup
npm run jet:build
npm run jet:render -- --views hero,side,top,rear,cockpit
npm start
# In a second terminal:
npm run jet:verify
```

Change a station or planform in `jet_spec.py`, build, render, then reload the
viewer. Inspect silhouette from side/top/front before adding detail. Check both
deployed and stowed poses. Keep source edits alongside their rendered evidence.
The local build takes about five seconds on this PC; studio renders take longer.

Primary outputs:

- `artifacts/vehicles/kestrel/kestrel.blend`: editable scene.
- `assets/kestrel/kestrel.glb`: self-contained viewer/export model.
- `assets/kestrel/kestrel.json`: dimensions, source hashes and pivot inventory.
- `artifacts/vehicles/kestrel/renders/`: five independent Blender views.
- `artifacts/vehicles/kestrel/viewer/`: real-browser captures and test receipt.

No external fonts or textures are fetched by the viewer. Model lettering is
converted to mesh during the build; installed Bahnschrift is used when present,
with Blender's built-in font as the fallback. Different fonts or Blender
versions can change geometry and export hashes.

## Verification and limits

The final export has **155,456 triangles**, **38 mesh groups**, **27 materials**
and **28 articulated nodes** (including 16 nozzle petals). It is **4,299,944
bytes**. Measured exported bounds are **15.43 m long, 9.81 m wide, 4.80 m high**
with gear deployed. These include probes/pods and differ from nominal design
constants. The 15 browser checks passed on the RTX 5070 Ti through ANGLE/D3D11.

Checks cover all six camera presets, UI-driven part motion, minimum stowed gear
height, assembly separation, surface modes, turntable, pointer orbit, exact
download SHA-256 and a 390 px mobile layout. There were zero runtime errors and
zero failed requests. One shader compiler warning entry reported floating-point
precision warnings (X4122); its text is preserved in the receipt.

Visual inspection caught and corrected three issues that successful exports
alone missed: coincident orange wing faces, landing gear rotating outside the
airframe, and fuselage skin blocking the intake. The final gear bounds clear
1.25 m above the ground; that is a useful regression check, not proof of a
mechanically accurate folding linkage or collision-free gear bay.

- [Browser receipt](verification/kestrel-browser.json)
- [Model and source-hash receipt](verification/kestrel-model.json)
- [Three.js exterior](images/kestrel-viewer.png)
- [Articulated pose](images/kestrel-articulated.png)
- [Blender studio exterior](images/kestrel-studio.png)

This is an inspectable aircraft asset and reusable source pipeline. It has no
flight simulation, rigged pilot, damage model, baked AO or LOD set. The model is
not yet integrated into Jet Game or Dustline, and performance has not been
benchmarked as part of a populated game scene. `tront.xyz/dunes/` remains the
future public destination; this work is local.
