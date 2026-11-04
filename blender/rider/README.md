# Dunes rider builder

Run Blender 4.5 with:

```powershell
& 'C:/Program Files/Blender Foundation/Blender 4.5/blender.exe' --background --factory-startup --python-exit-code 1 --python blender/rider/build_rider.py
```

The default input is the retained CC0 Quaternius male humanoid in `source/`.
Its original glTF and binary are unchanged. Texture references are stripped in
a staged copy because the rider uses new opaque materials. The face is removed;
the helmet and visor are generated and weighted to the existing head bone.

Output: `assets/driver/rider.glb`. Editable scene and temporary input:
`artifacts/rider-source/`. The export has 65 bones and 13,492 triangles.

See `assets/driver/RIDER-CREDITS.md` and `QUATERNIUS-LICENSE.txt` for provenance
and the original license notice. There are no downloaded textures in the export.

`npm run rider:verify` checks independent player/bot skeletons, seating, steering
reach and cockpit/mirror visibility in the actual game and saves screenshots.
