# Driving UI and startup mirror repair (0.4.0)

The driving page has one WebGL canvas. HUD, loading messages, menu controls,
driver labels, help, notifications and the name editor use SDF glyph quads.
The cockpit dashboard and navigator use the same renderer in GPU render targets.
The suspension and jet viewers retain their existing interfaces for this pass.

`gpu-ui.js` supplies glyph layout, clipped primitives and the render pass.
`game-ui.js` supplies HUD layout and input hit testing. `menu.js` supplies the
settings interface and name editor; `settings.js` retains the settings schema.
The renderer uses an orthographic camera compatible with reversed depth.
Offscreen radar canvases contain map geometry only; no runtime text is painted
with Canvas2D. Authored artwork and decals on the original model stay intact.

The atlas includes 523 glyphs from Barlow Condensed Bold, distributed under the
SIL Open Font License in `assets/fonts/OFL.txt`. The original font, generated SDF
PNG and metrics are checked in, so normal builds require no font-generation
tools. To regenerate, run `python tools/build-font.py` with Pillow, NumPy, SciPy
and fontTools installed. Characters outside the atlas fall back to `?`.

The name editor supports selection, cursor movement, backspace/delete, clipboard
shortcuts, save/cancel and a GPU on-screen keyboard. It uses keyboard events
without a hidden HTML input. Browser-native IME composition is not implemented.
Names persist locally and propagate through Trystero without rebuilding the car,
changing the peer ID or reloading the page. Menu input is consumed before driving
and orbit controls. Key bindings, sliders, weather, teleport and car choices are
preserved; changing the graphics preset still explicitly reloads the game.

## Why the mirror looked crumpled

The old `sightNotch` adjustment moved chassis vertices along the driver's
eye-to-front-tire sightlines, including the mirror glass and housing. On the
bundled GLX pro, all seven driver-side glass vertices changed, with a maximum
displacement of 0.166267 m. Three opposite-side vertices changed by up to
0.028293 m. Disabling that adjustment restored both mirrors exactly to their
source GLB positions. The adjustment is removed for GLX pro and pro 2.

No collision-damage mesh deformation system was found. Steering, suspension
animation and the separate front-wheel clearance stretch remain in place.
The source models were not re-exported or edited for this fix.

## Verification

`npm run polish:verify` opens two isolated Chrome contexts through live Trystero
signaling and uses actual keyboard and pointer events. Its checks cover:

- Normal URLs entering global without a click and exchanging vehicle states.
- In-place rename, remote labels/roster, validation, cancellation and persistence.
- GPU menu choices, dragging sliders, keyboard focus, scroll, rebinding and teleport.
- No DOM text/controls or Canvas2D text calls, including cockpit instruments.
- A 390-pixel compact menu and on-screen name keyboard.
- Both side mirrors matching original GLB vertices before any driving input.

Receipts and screenshots are under `artifacts/polish/`; `DUNES_URL` and
`DUNES_OUTPUT` select a target and a separate result directory. The default
test uses the global lobby but does not change shared world settings.
The existing multiplayer verifier uses a unique room to test shared settings,
vehicle changes, tracks, isolation, rejoin and leave. The vehicle verifier
checks keyboard driving, steering, suspension motion and cockpit rendering.
These browser checks use this PC; they do not establish cross-device or
restrictive-NAT connectivity or physical gamepad behavior.

The 0.4.0 local release run passed 11 UI/global-room checks, 11 packaged
multiplayer checks and 5 packaged vehicle checks, with no runtime errors or
failed resource requests. A separate temporary Node relay check passed rename
broadcast and late-join roster updates. Screenshots include the full cockpit,
driver menu, name editor and compact keyboard. `node tools/verify-release.mjs`
compares the published release and asset hashes to the committed checkout.
