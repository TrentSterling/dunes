# Name tags and camera/lighting stalls (0.5.1)

The former label check accepted negative projected depth. With reversed depth,
that includes cars behind the camera, producing misleading floating names.
Labels also projected before the camera matrix was refreshed. The shared bot
and peer projector now rejects near/far and offscreen points in view space;
the camera matrix updates immediately after camera movement.

The first cockpit switch compiled 54 shaders during gameplay in the local
baseline and stalled for 2571 ms. Loading now prepares both canvas and mirror
shader variants, uploads cockpit resources, warms the five camera views and
waits asynchronously for the GPU. Mirrors always draw one glass per frame,
including on camera switches. This moves first-use work into loading.

Time changes recreated the environment capture scene and terrain shadow shader,
and invalidated the terrain material each time. Capture objects and the shadow
material now persist. The visible sun, sky and fog update immediately; a 120 ms
quiet period coalesces rapid input into the latest reflection/shadow capture.
The environment target is replaced and its predecessor disposed. Resolution
and terrain shadow sample count are unchanged.

Local isolated Chrome on RTX 5070 Ti, Ultra, 1440 x 900, four moving bots:

| Interaction | Before, worst frame gap | After, worst frame gap |
| --- | ---: | ---: |
| First cockpit switch | 2571 ms | 18.2 ms |
| Daylight changes | 153 ms | 19.6 ms |
| Night on/off | Not measured | 20.4 ms |

These are single-machine measurements, not universal frame-rate guarantees.
Browser driver shader caches and other GPU work affect timings.

Run `npm run view:verify` against the local server, or set `DUNES_URL` and
`DUNES_OUTPUT` for a packaged/live release. It uses a unique Trystero room and
an isolated Chrome profile. Seven checks cover first/repeated camera changes,
day/night lighting, burst coalescing, both depth conventions, tag placement
while orbiting, exactly one visible tag per test driver, and visibility controls.
Screenshots cover desktop, compact and cockpit views. Raw receipts live under
ignored `artifacts/labels-performance/`.

Also run `npm run radar:verify` after changes to the camera/mirror render path.
The vehicle check remains `npm run vehicle:verify -- --bundled`.

Shader warmup uses the bundled renderer's
[compileAsync API](https://threejs.org/docs/pages/WebGLRenderer.html#compileAsync).
