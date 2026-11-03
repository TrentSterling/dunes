# Dunes vehicle pipeline verification

Verified locally on **2026-11-03**, with Blender **4.5.2 LTS**, Pillow **12.1.0**,
installed Chrome, and NVIDIA GeForce **RTX 5070 Ti** through ANGLE/D3D11.
Upstream import: `22e58650c892cdae95a7e2f064bdffaefd277785`.

## Actual results

| Check | Result |
| --- | --- |
| Strict full build from Python source | PASS; 21.1 seconds in the final wrapper run |
| Editable Blender output | Saved and reopened for rendering; 53 images packed |
| Generated geometry before AO | 389,772 triangles |
| Final AO-baked game export | 404,846 triangles; 25,173,556 bytes; `_AO` present |
| Rig/metadata agreement | 48 nodes, 37 glTF meshes, 98 materials; all required nodes present |
| Wheel and suspension metadata | 4 wheels, 18 links, 8 shocks |
| Cycles visual inspection | Exterior three-quarter and interior dashboard rendered at 1280 px, 32 samples |
| Part-only iteration | `--only body,chassis` passed in 7.5 seconds; full baked GLB hash unchanged |
| Checked-in texture preservation | Full and partial wrapper builds left source textures unchanged |
| Game import of final rebuilt GLB | PASS; 4 wheel rigs, 4 uprights, 26 moving suspension segments |
| Keyboard steering | Steering-wheel transform changed |
| Keyboard throttle | Vehicle moved 49.75 m in this capture; wheel rotation and suspension height changed |
| Exterior and live cockpit | Captured in the actual game renderer |
| Runtime errors / failed requests | 0 / 0 |

The browser emitted one shader compiler warning entry containing floating-point
precision warnings (X4122). It did not prevent rendering or the driving checks.
Its exact text is preserved in the browser receipt. This was a short isolated
driving check, not a multiplayer, long-session stability or performance benchmark.

## Reviewable evidence

- [Build/export receipt](verification/build-receipt.json)
- [Browser and motion receipt](verification/browser-receipt.json)
- [Studio exterior](images/rebuilt-buggy-front.png)
- [Studio interior](images/rebuilt-buggy-interior.png)
- [Actual game exterior](images/rebuilt-buggy-game.png)
- [Actual game cockpit](images/rebuilt-buggy-cockpit.png)

Editable artifact: `C:/trontstack/dunes/artifacts/vehicles/glx-pro/sandrail.blend`.
Final game artifact: `C:/trontstack/dunes/artifacts/vehicles/glx-pro/sandcar.glb`.
Detailed logs, pre-bake receipts, and generated files remain in that ignored
artifact folder. The checked-in receipts and images preserve this run's evidence;
later builds can change the ignored working outputs.

The final GLB SHA-256 is
`f811d8d55ad4fe1e74e606ee0d49019e645f2d2908a820fe58d2972d3256af0f`.

## Scope and remaining work

This proves that the supplied buggy's procedural source can be rebuilt, edited,
rendered, exported, baked and driven locally. Its source includes authored shape
definitions and several documented review rounds. It does not prove a universal
one-prompt modeling solution, exact equivalence to the original author's missing
reference images, or a finished new jet/car design.

The normal local game retains its bundled upstream GLX model. The verifier
substitutes the newly generated GLB and JSON in its isolated browser. Original
modeling and integration into Jet Game or Dustline are later milestones.

Dunes has a separate local Git repo with preserved upstream history. No new
GitHub hosting remote or public deployment has been created. The intended public
route remains https://tront.xyz/dunes/.
