# GPU radar and continuous bot movement (0.5.0)

The radar's old Canvas2D map is replaced by a WebGL render target. Its fragment
shader shares the terrain's height textures, gradients and procedural dune
functions, so it shades the same landscape as the driving view. Contours,
range rings, compass glyphs, bot dots, player diamonds and edge arrows are drawn
on the GPU. The cockpit navigator gets a separate north-up GPU map with the
same driver markers. No radar pixels are generated or uploaded by Canvas2D.

The HUD map is heading-up, with 300 m, 600 m, 1.2 km and 2.5 km ranges. The
visible plus/minus controls adjust range; B toggles visibility. If hidden, a
Show Radar control remains available. This release restores the HUD radar once
for old hidden/dash-only configurations, then preserves subsequent preferences.
Keyboard arrow bindings use readable words supported by the glyph atlas.

## Bot jumps removed

The old AI called `spawnNear` when more than 1.6 km away, instantly reset its
pose after a rollover, and reset again after an unsuccessful reverse maneuver.
The game also recreated all bots when the player changed cars and moved them
along with player teleports. These were actual discontinuities in simulation,
not just marker or network interpolation artifacts.

Now bots return by steering toward the player. Stuck bots reverse and choose
another line. An overturned, settled bot gets a bounded body-frame torque that
rolls it upright through the existing vehicle physics. The assist stops after
the wheels settle. Runtime AI never calls reset or writes position/orientation.
Car changes and player teleports leave existing bot objects and poses intact.
New bots still spawn when the game starts or the bot count increases.

AI remains local to each client, as before. This change does not turn bots into
network-owned shared entities or change the player's manual/automatic reset.

## Checks and evidence

- `npm run bots:verify` passed four deterministic scenarios using the actual
  AI and 1000 Hz vehicle physics: distant return, failed reverse, physical
  rollover recovery and a seeded 60-second drive with reset calls forbidden.
- The flat-ground inverted-car scenario recovered in 7.05 seconds, including
  the initial recovery delay. Its largest 1/60-second position step was 0.060 m
  and angular step 0.0231 rad. This is a specific scenario, not a universal
  recovery-time guarantee for every dune or vehicle.
- `npm run radar:verify` passed ten actual-game checks. Render-target pixel
  reads confirmed terrain coverage and correctly rotated colored markers.
  Four bots drove through 360 rendered frames with zero resets or detected
  position jumps. A second isolated Chrome context supplied a real WebRTC peer.
- Screenshots cover the heading-up HUD, close radar view, cockpit navigator
  and 390-pixel compact layout. Render-scale changes and saved visibility were
  exercised. There were no runtime errors or failed resource requests.

Local receipts/screenshots are in `artifacts/radar-bots/local/`; live release
checks use `artifacts/radar-bots/live/`. Both verifiers accept `DUNES_URL` and
`DUNES_OUTPUT`. Real signaling between two contexts on this PC does not prove
cross-device or restrictive-NAT connectivity.
