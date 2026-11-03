# Dunes publishing

- Repository: https://github.com/TrentSterling/dunes
- Play: https://tront.xyz/dunes/
- Suspension: https://tront.xyz/dunes/suspension.html
- Kestrel: https://tront.xyz/dunes/jet.html
- Release: 0.3.0

The `Publish Dunes` GitHub Actions workflow packages `public/` and `assets/`
and deploys the result to GitHub Pages on each push to `main`. The project uses
the existing account domain, with no Dunes CNAME or DNS change.

Run `npm run build:pages` locally. Output is `artifacts/pages/dunes/`. To check
the same subdirectory routing, serve `artifacts/pages/` with a static server
and open `/dunes/`. Run `npm ci` first; the build uses Node 22, pinned esbuild and
Trystero packages. Browser verification uses installed Chrome and Playwright.

Only the generated build sets `STATIC_HOSTING = true`. It selects Trystero
multiplayer and reads a generated audio manifest instead of the Node directory
listing. `npm start` retains the original Node relay and 48-hour track store;
append `?net=p2p` to test peer networking on that server.

## Multiplayer

Trystero 0.26.0 is bundled locally with its MIT licenses and dependency notices.
Nostr relays provide peer discovery; game traffic uses WebRTC data channels.
The app ID is `xyz.tront.dunes.v1`. The default room is `public`; `?room=NAME`
selects a separate room (letters, numbers, underscores and hyphens, 48 characters
maximum). A named room is a shared meeting place, not an authentication gate.

The existing car-state contract runs at up to 20 Hz with a pending-send limit.
Names, car changes, shared world settings and live tire tracks use separate
Trystero actions. World settings use per-key revision counters, so late joins
and simultaneous changes converge. Joining peers request nearby track tiles
from one connected donor. Track history is bounded by what active peers still
hold; leaving all browsers loses it. This does not recreate the disk-backed
48-hour store. AI cars retain the original client-local simulation.

No TURN service is configured. Public discovery availability and restrictive
NAT/firewall combinations can affect connection success; solo driving continues.
Two Chrome contexts on this PC using live relays prove actual WebRTC exchange,
not connectivity between every pair of external networks.

## Verification

`npm run multiplayer:verify` drives two isolated Chrome clients in a unique
room through live public signaling. It checks mutual discovery, vehicle-state
exchange, keyboard driving, shared settings, car changes, tracks, room isolation,
reload/rejoin and leaving. Set `DUNES_URL` to the deployed URL and `DUNES_PHASE`
to `live` to write a separate receipt. No mock signaling or peer connection is
substituted. Browser RTC statistics are captured with the report.

The existing vehicle, jet and suspension verifiers accept `DUNES_URL` and
`DUNES_OUTPUT` for subdirectory deployment checks and separate release receipts.
Use `node tools/verify-vehicle.mjs --bundled` for the shipped game model.

The original Glamis history and Unlicense are retained. See GLAMIS-UPSTREAM.md
for the bundled component credits. The suspension viewer's existing local work
is included in this release. JET GAME and Dustline are separate projects.

Release verification receipts are saved under `artifacts/deployment/` locally.
The public `release.json` identifies the version and deployed Git commit.
