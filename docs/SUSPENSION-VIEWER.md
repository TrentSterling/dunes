# GLX Pro suspension viewer

Local URL: http://localhost:5189/suspension.html

The server is shared with the Glamis game at http://localhost:5189/. This viewer
uses the previously rebuilt and baked GLX Pro model, copied byte-for-byte from
`artifacts/vehicles/glx-pro/sandcar.glb` to `assets/suspension/sandcar.glb`. The
bundled game assets, driving physics and original game animation are unchanged.

## Controls

- Drag to orbit, scroll or pinch to zoom, right-drag or Shift-drag to pan.
- Cross axle, all four wheels, front axle, rear axle and rolling bump cycles.
- Pause freezes the pose. Wheel sliders enter manual mode immediately.
- Single bump drives the front actuator pair. Response frequency and damping
  control a fixed-step, second-order actuator response with a 240 Hz step.
- Steering follows the front kingpin axes. The stand holds the commanded hub
  heights while the steering moves.
- Full car, ghost body, or suspension only; optional wheels and joint overlay.
- Overview, front, rear, side, underneath and front-detail camera presets.
- Reset stops motion, clears travel and steering, and restores the overview.

## Rig construction and limits

`public/js/suspension-rig.js` uses the exported hardpoints. The front lower and
upper arms rotate as rigid pieces about the axes joining their inboard mounts.
A numerical constraint solve preserves the upright's ball-joint spacing and
the requested wheel-center height. Steering rotates the upright and wheel about
the moving kingpin. Camber and lateral wheel displacement follow those points.

The rear is a point-link model: the trailing-arm assembly rotates about its
inboard point while both radius rods keep their rest lengths. This models that
inboard connection as spherical. It does not claim that the modeled pivot
hardware supports all resulting angular motion. The neutral-connected solution
approaches a singularity around 163 mm droop. The viewer stops at 150 mm, rather
than scaling a rigid rod or jumping to a folded solution. Front travel is
330 mm droop and 300 mm bump; rear travel is 150 mm droop and 300 mm bump.

The original eight joined shock nodes are removed from the viewer scene. A separate Blender export
preserves their authored component geometry as 170 meshes: eyes, bodies,
shafts, springs, seats, collars, adjusters and bypass tubes. Bodies and eyes
remain rigid. Spring pitch changes with the distance between the seats; the
visible chrome shaft span extends into the barrel. Shock lower eyes follow the
same rigid arm transform as their mounting tabs; upper eyes stay on the chassis.

The fixed steering-rack endpoints use an adjustable visual tie-rod length; this
is not an Ackermann/rack solver. Halfshafts telescope. Hoses remain with the
static chassis. Collision stops, coil bind, compliance, tire deformation, loads,
road contact and full chassis dynamics are not solved. The actuator response is
for visual testing, not a measured spring/damper specification. Test pads follow
the wheel center and approximate the tire support height analytically.

## Rebuild

```powershell
npm run suspension:build
npm start
# In another terminal:
npm run suspension:verify
```

The build routes through `tools/vehicle_pipeline.py`, using staged copies of
the original Blender source and its local Pillow installation. It never repaints
the checked-in artwork. The complete car must already have been built by
`npm run vehicle:build`; the existing baked car is reused rather than rebuilt.

- Builder: `tools/build-suspension-shocks.py`
- Standalone shock scene: `artifacts/vehicles/glx-pro/suspension-shocks.blend`
- Exported model, physics and separate shocks: `assets/suspension/`
- Browser UI: `public/suspension.html`, `public/suspension.css`
- Viewer: `public/js/suspension-viewer.js`
- Rig solver: `public/js/suspension-rig.js`

## Verification on 2026-11-03

`npm run suspension:verify`: 14 checks passed, no runtime errors or failed
requests. Actual renderer: ANGLE / NVIDIA GeForce RTX 5070 Ti / Direct3D 11.
One Three.js shader precision warning is recorded in the receipt.

The 21-pose sweep combines seven travel commands with three steering angles.
It checks rigid link length and upright closure errors below 0.1 mm, compares
actual shock-eye mesh centers against the moving mounts below 0.1 mm, checks
that the shock barrels retain their scale, and checks actual hub height against
the control values. Authored GLB node names are distinguished from loader-made
material primitive names using the loader's authored-node associations. All
eight original joined shock nodes must be detached from the scene. This avoids
a static bypass remaining behind a moving one, even if visibility is changed.
It also exercises independent sliders, cycle and pause,
patterns, bump response, damping, view modes, camera presets, pointer orbit and
a 390-pixel-wide layout.

Full receipts and screenshots:
`artifacts/vehicles/glx-pro/suspension-viewer/verification.json` and `sweep.json`.
Selected durable receipt: `docs/verification/suspension-browser.json`.
Rest, front/rear, underside, ghost and articulated suspension captures were
visually inspected. These checks establish the viewer's behavior and point
connections; they do not establish collision-free or manufactured hardware.

The game server was started for Trent and intentionally left running. Its
startup PID was 40660; check current ownership before stopping it. Logs are
`artifacts/server-suspension.log` and `artifacts/server-suspension-error.log`.
Automatic opening through the in-app browser was unavailable; the local URLs
remain directly accessible. No deployment or remote push was performed.

## Duplicate geometry audit (rig revision 02)

After a report of stationary duplicates, all eight replaced shock assemblies
were detached rather than hidden. The rig resolves authored GLB nodes through
loader associations, bypassing similarly named material primitives. Viewer and
rig module URLs carry a revision, and the footer shows `RIG REV 02`; an already
open page must reload to run the new code.

A rest-pose comparison of all 34 original moving mesh nodes against the joined
static chassis found zero shared triangles after quantizing positions to 0.1 mm.
This is an exact-geometry check, not proof against every visually similar part.
Fresh front, rear and chassis-only captures are under
`artifacts/vehicles/glx-pro/suspension-viewer/duplicate-audit/`, alongside
`static-overlap.json` and `nodes.json`. The 14-check browser verifier passes.
