# Dust rendering and riders

The main view renders the world into a full-resolution HDR target, then renders
soft dust into a target capped at 960 x 540 (at most half the world dimensions).
At native 4K this cuts each large dust billboard's raster area to one sixteenth.
Grains, cars, terrain, radar and GPU glyphs keep their full resolution.

Dust samples scene depth, fades at solid intersections and close to the camera,
then uses depth-weighted upsampling. Tone mapping occurs after compositing.
Small mirror targets retain their existing direct particle rendering.
The render targets and shader variants are prepared during loading.

`npm run dust:verify` uses native 3840 x 2160 Chrome, Ultra quality and a seeded
400-puff near-camera trail. GPU timer queries enclose the whole world/dust/
composite render, with frame pacing excluded. On this RTX 5070 Ti, a local run
measured median 15.65 ms with the original path and 9.38 ms with the new path
(24 samples each). This is a controlled stress comparison, not a universal FPS
claim. It also compares clear-scene colors, foreground center/edge pixels and
viewport resizing. Receipts: `artifacts/dust-rider/dust-verified/`.

The rider uses a CC0 Quaternius humanoid with a Dunes helmet, opaque visor and
orange suit. Its rig is cloned per car, posed against the wheel and pedals, and
steers without extra network packets. The full rider is hidden in first person;
the existing optional cockpit arms remain available. Mirrors can see the rider.
Cars without an authored steering wheel keep their existing presentation.

Source, rebuild instructions and license are retained in `blender/rider/` and
`assets/driver/`. `npm run rider:verify` checks the actual seated mesh and captures
front, side, isolated, steering and cockpit views. `npm run view:verify` guards
camera/lighting warmup and nametag behavior after render-path changes.
