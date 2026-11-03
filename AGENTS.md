# Dunes operating notes

Read root TrontStack instructions, README.md and docs/VEHICLE-PIPELINE.md.

Trent wants a reliable procedural 3D modeling workflow for detailed cars and a
proper jet. A runnable script alone does not satisfy visual quality. Generate
the mesh, inspect multi-view renders, import it into the actual game, and test
moving parts. This is a separate local repository at C:/trontstack/dunes.

- Acquire this repo's .agentcoord lease before writing. Preserve other leases.
- `upstream` is iotdatabase/glamis_game. Do not push to it. No origin exists yet.
- https://tront.xyz/dunes/ is the future route, not a deployed site.
- Jet Game and Dustline are references; do not change their repos from this task.
- Preserve upstream history, license, bundled models and source artwork.
- Build through tools/vehicle_pipeline.py. Its staged inputs prevent upstream
  texture painters from modifying the checked-in source artwork.
- Keep generated outputs under ignored artifacts/, .tools/, or the existing
  ignored blender/trx_pro/renders/ folder.
- Use --strict and --python-exit-code 1. Inspect logs and actual outputs.
- The browser verifier substitutes generated GLB/JSON in an isolated context;
  it does not overwrite bundled assets or drive the owner's open browser.
- A successful buggy export does not establish a finished jet or flight model.

`npm start` serves localhost:5189. Run `npm run vehicle:setup`, `vehicle:build`,
`vehicle:render`, `vehicle:bake`, and `vehicle:verify` for the full pipeline.
Verification needs the local server and installed Chrome. Blender 4.5.2 and
Pillow 12.1.0 are the verified baseline. See docs/VERIFICATION.md for evidence.

`npm run vehicle:build -- --only wheels` creates a part inspection scene without
overwriting the full export. `npm run vehicle:check` checks the GLB/metadata pair.
