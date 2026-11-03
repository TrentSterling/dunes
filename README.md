# Dunes

Driving sandbox and reproducible Blender vehicle modeling project for Trent.
Future public destination: **https://tront.xyz/dunes/**. This checkout is local;
that URL has not been deployed by this project.

Starting point: [iotdatabase/glamis_game](https://github.com/iotdatabase/glamis_game),
imported at `22e58650c892cdae95a7e2f064bdffaefd277785`. Its history, game, vehicle
builders and license are preserved. `upstream` points to Glamis with pushing
disabled. There is no Dunes hosting remote yet.

Jet Game (`../horde3d`) and Dustline (`../dustline`) are inspiration and future
integration references. The buggy pipeline is verified, and the first original
scripted jet is **Kestrel 01**, with its own Three.js inspection viewer.

## Inspect the jet

With `npm start` running, open **http://localhost:5189/jet.html**.

![Kestrel 01 in the Three.js viewer](docs/images/kestrel-viewer.png)

Orbit the actual exported model; open the canopy, retract the landing gear,
move the control surfaces and nozzle petals, or spread the assembly apart.
Six camera views include the cockpit. Livery, clay and wireframe modes expose
the model's shape and construction. The download button returns the complete GLB.

```powershell
# First-time Blender dependency setup, if not already done:
npm run vehicle:setup
npm run jet:build
npm run jet:render
# Keep npm start running in another terminal:
npm run jet:verify
```

- Editable Blender scene: `artifacts/vehicles/kestrel/kestrel.blend`
- Viewer asset: `assets/kestrel/kestrel.glb`
- Shape specification: `blender/kestrel/jet_spec.py`
- [Source guide, ViperOneOne references, and verification](docs/KESTREL-REFERENCE.md)

This is a model and inspection viewer. Flight physics and game integration are
the next stage. The GLB is checked in, so viewing does not require Blender.

## Play locally

Double-click `START-GAME.bat`, or:

```powershell
npm ci
npm start
```

Open **http://localhost:5189/**. WASD drives, C changes camera, M opens the menu.
The normal game initially uses the bundled upstream vehicle. Verification loads
the newly generated vehicle without replacing that baseline.

## Rebuild and inspect the buggy

Tested with **Blender 4.5.2 LTS** on Windows. The helper finds Blender 4.5 in
Program Files; set `BLENDER` or pass `--blender` for another executable.

```powershell
npm run vehicle:setup
npm run vehicle:build
npm run vehicle:render
npm run vehicle:bake
# Leave npm start running in another terminal:
npm run vehicle:verify
```

Setup installs pinned Pillow into `.tools/blender-python`, without modifying
Blender's global installation. Build stages source textures under `artifacts/`
because upstream part scripts repaint them. The editable scene packs its images.
Strict error handling and actual output validation are enabled.

Outputs:

- `artifacts/vehicles/glx-pro/sandrail.blend`: editable scene, packed textures.
- `artifacts/vehicles/glx-pro/sandcar.glb`: game model (bake updates this file).
- `artifacts/vehicles/glx-pro/sandcar.physics.json`: matching wheel/suspension data.
- `artifacts/vehicles/glx-pro/*receipt.json`: build and real-browser verification.
- `blender/trx_pro/renders/dunes_*.png`: studio inspection views.
- `artifacts/vehicles/glx-pro/game-*.png`: game captures of the rebuilt asset.

For a smaller modeling iteration:

```powershell
npm run vehicle:build -- --only body,chassis
```

That creates `artifacts/vehicles/glx-pro/parts/body_chassis.blend`, preserving the
complete game export. Missing upstream reference photos are optional for ordinary
inspection renders; they are required for exact photo-overlay comparisons.

## Read next

- [How the vehicle is built, and how to apply it to a jet](docs/VEHICLE-PIPELINE.md)
- [Current verification evidence](docs/VERIFICATION.md)
- [Original Glamis documentation and controls](docs/GLAMIS-UPSTREAM.md)
- [Upstream Blender source guide](blender/trx_pro/README.md)

The source is released under the upstream [Unlicense](UNLICENSE). Bundled
third-party components retain their licenses, listed in the original guide.
