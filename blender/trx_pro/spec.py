"""Shared dimensions for the GLX pro sandrail (all parts read these).

Blender coordinates, meters:  +X = car's RIGHT,  +Y = FORWARD,  +Z = UP.
Origin = on the ground, centred between the axles and between the wheels.
(The glTF exporter turns this into the game's frame: +X right, +Y up, -Z forward.)
The driver sits on the LEFT (x < 0), passenger on the right (x > 0).

Measured from ref/side_right_red_variant.png (same chassis, red livery) at
~470 px per metre (35" rear paddle tyre = 425 px), and from ref/front.png /
ref/rear.png for widths. Everything below is a target; parts may refine shapes
but must keep the HARD POINTS (wheel centres, eye, steering wheel, roof height)
because the game's physics and cockpit camera depend on them.
"""

# ---------------- wheels (HARD POINTS) ----------------
WHEELBASE = 3.00
FRONT_AXLE_Y = +1.50
REAR_AXLE_Y = -1.50
FRONT_TRACK = 1.84          # wheel centre to wheel centre. r3: was 2.20 (tyre-only fits in front.png + front_3q
                            # give 1.83-1.86, prep's joint camera solve 1.82; tyre inner faces at |x| 0.805)
REAR_TRACK = 1.93           # r3: was 2.06 (rear.png paddle fit 1.92-1.95, prep solve 1.91)

FRONT_TIRE_R = 0.430        # 34" ribbed sand front (4 ribs), outer radius
FRONT_TIRE_W = 0.230        # r3: was 0.250 (photo tyre silhouettes 6-7 % narrower at matched rows)
REAR_TIRE_R = 0.452         # 35" paddle tyre, radius to paddle tips
REAR_TIRE_CARCASS_R = 0.402 # radius of the carcass under the paddles. r3: was 0.392 - paddles 1 cm shorter (photo
                            # sawtooth is smaller) while the tip radius / game wheel radius REAR_TIRE_R stays
REAR_TIRE_W = 0.360         # r3: was 0.380 (rear.png / rear_3q silhouettes 6 % narrower)
RIM_BEAD_R = 0.1905         # 15" bead seat
RIM_RING_R = 0.222          # outer radius of the machined beadlock ring
FRONT_RIM_W = 0.180         # 15x7
REAR_RIM_W = 0.255          # 15x10

# wheel centre heights at static ride height (centre >= radius so it sits on the sand)
FRONT_WHEEL_Z = 0.432
REAR_WHEEL_Z = 0.455

WHEELS = {   # name: (x, y, z, radius, width, front)
    'FL': (-FRONT_TRACK / 2, FRONT_AXLE_Y, FRONT_WHEEL_Z, FRONT_TIRE_R, FRONT_TIRE_W, True),
    'FR': (+FRONT_TRACK / 2, FRONT_AXLE_Y, FRONT_WHEEL_Z, FRONT_TIRE_R, FRONT_TIRE_W, True),
    'RL': (-REAR_TRACK / 2, REAR_AXLE_Y, REAR_WHEEL_Z, REAR_TIRE_R, REAR_TIRE_W, False),
    'RR': (+REAR_TRACK / 2, REAR_AXLE_Y, REAR_WHEEL_Z, REAR_TIRE_R, REAR_TIRE_W, False),
}

# suspension travel the game expects (metres at the wheel)
BUMP = 0.30
DROOP = 0.33

# ---------------- overall body ----------------
NOSE_Y = +1.95              # front of the front bumper tubes
TAIL_Y = -2.56              # back of the rear cage bumper = apex of its D-shaped side arc (z ~0.90-0.95, |x| 0.45-0.5).
                            # r4: was -2.48 (side photo, solved camera: rearmost tube edge at u 28 -> y -2.573 @ |x| 0.5;
                            # rear_3q: photo reaches 9-13 px further back at z 0.9-1.0)
ROOF_TOP_Z = 1.485          # top of the roof skin at the FRONT edge (light bar sits on top of this; unchanged)
ROOF_REAR_Z = 1.54          # roof skin top ramps up from ROOF_TOP_Z at y +0.2 to this by y -0.2; the chassis gusset fin
                            # meets the roof here. r4: was 1.52 (side view 1.3-2.2 cm low at y -0.1..+0.15, rear_3q top
                            # edge 19-30 px low)
SPOILER_TOP_Z = 1.565       # top of the striped rear spoiler lip (trailing edge, at SPOILER_TRAIL_Y). r6: was 1.58
                            # (rear.png: the lip at v 20-25 back-projects to z 1.557-1.567 at y -0.62; rear_3q's camera
                            # reads ~1-2 cm high at this station). r4: was 1.55
# r6 new: the spoiler is a THIN swept blade whose trailing edge sits ~12 cm further back than r5 (y -0.50) and overhangs
# the rear braces with an open gap under it (rear_3q: blade ends at u ~637 / 860 fit y -0.58 at |x| 0.48; the centre is
# arched back). (y at the centre line, y at the blade ends |x| = SPOILER_HALF_W[1])
SPOILER_TRAIL_Y = (-0.62, -0.58)
# r6 new: bottom edge of the spoiler's rear face (centre, ends): face ~7.5 cm tall at the centre, ~5 cm at the ends
# (rear_3q face 25 px = 6.8 cm at the centre, 11-20 px at the ends; rear.png face bottom ~1.47-1.49). r5 body had a
# 10.5 cm face (SPOILER_FACE_Z 1.475) plus a band at the ends. The red LED strips sit on the face at z ~1.50-1.505,
# |x| 0.28-0.41 (rear.png), i.e. NOT at the very blade ends.
SPOILER_FACE_BOTTOM_Z = (1.49, 1.515)
ROOF_FRONT_Y = +0.45
ROOF_REAR_Y = -0.45
ROOF_WIDTH = 1.26           # roof skin width at ROOF_FRONT_Y (over the A-pillar tops at |x| 0.60)
ROOF_REAR_HALF_W = 0.59     # r4 new: the roof tapers in plan to this skin half-width at ROOF_REAR_Y (over the B-pillar
                            # tops, now |x| 0.56; rear.png, horizontal scale checked on the spoiler's red LED strips)
SPOILER_HALF_W = (0.47, 0.485)  # spoiler rear face in rear view: half-width of its lower rear edge, of its top lip;
                                # corners rounded R ~0.03. r6: was (0.54, 0.49) - rear.png ends are near-vertical at
                                # |x| 0.485-0.495 (v 25-50), the lower corners round in to ~0.45 at the face bottom;
                                # rear_3q ends fit 0.48 (the critic's 0.46 is too narrow). r4: was the full 0.63
BODY_WIDTH = 1.62           # widest point of the side pods / doors
BELT_Z = 1.085              # top edge of the doors (window sill)
SILL_Z = 0.50               # bottom edge of the body sides at y -0.6..+0.8. r3: was 0.47 (GLX rear_3q 0.53-0.55,
                            # front_3q/rear_3q 3-4 cm low, red side photo 0.48); rises to ~0.58-0.60 at y -0.9
COWL_Y = +0.72              # base of the windshield opening (A-pillar foot)
COWL_Z = 1.10
HOOD_FRONT_Y = +1.62        # front edge of the carbon hood / nose (leading edge y 1.62-1.66)
HOOD_FRONT_Z = 0.88         # r4: was 0.80 (never used). Hood leading edge on the centre line, tucked just behind / at
                            # the bumper top tube (front.png trough 0.87, front_3q nose tip ~0.90)
# r4 new: hood CENTRE-LINE top (y, z) = the top of the raised centre beak (front.png, front_3q; the r3 model was
# 1.06 @ 1.35, 1.04 @ 1.45, 0.99 @ 1.6 - nose 8-12 cm too high)
HOOD_CENTRE_Z = [(0.80, 1.10), (1.10, 1.04), (1.30, 0.97), (1.55, 0.89), (1.64, HOOD_FRONT_Z)]
# r5 new: half-width (y, hw) of the raised centre hood BEAK (black/orange, the only panel that runs on to the nose tip).
# Its sides fall steeply (~50-60 deg) into open troughs over the coilovers / finned reservoirs, which stay UNCOVERED.
# front.png: beak edges at the cowl u ~630/900 (|x| ~0.24, the three cowl vents sit on it), tip u ~740-840 at y 1.62.
HOOD_BEAK_HALF_W = [(0.85, 0.24), (1.10, 0.18), (1.30, 0.13), (1.62, 0.06)]
# Outer fender shoulder / crown top at |x| 0.45-0.70 (y, z). r5: was [(0.90, 1.125), (1.20, 1.04), (1.45, 0.97),
# (1.60, 0.93)] - taken from side_right_red_variant, whose tall long front fenders are a DIFFERENT body. The GLX
# (front_3q far-fender silhouette 1.075 @ .95, 1.005 @ 1.03, .947 @ 1.11, .936 @ 1.19, .928 @ 1.27; rear_3q near edge;
# front.png) has short "wing" fenders that drop away right ahead of the cowl. The r4 rule ">= 1.5 cm of skin over the
# shock tops" is DROPPED: the photos show the coilover tops and finned reservoirs uncovered. First knot stays behind
# parts/body.py FENDER_Y0 (0.865, the door shut line) so the door-front top is FENDER_SHOULDER_Z[0] (1.10, was 1.125).
# side_right_red_variant.png is NOT a reference for the front clip (only for wheelbase / wheels / ride height / cage).
FENDER_SHOULDER_Z = [(0.87, 1.10), (1.00, 1.03), (1.10, 0.96), (1.30, 0.93), (1.50, 0.90)]
B_PILLAR_Y = -0.64          # rear edge of the door / window opening
# Rear pods (r4): inclined, rounded "shields" - the deck top is high at its INNER edge and falls ~12-15 deg outboard
# to a rounded shoulder; the lower pod side stays at REAR_POD_HALF_W (tyre clearance).
REAR_DECK_Z = 1.33          # pod deck INNER top edge at the tail face (y TAIL_BLOCK_Y[0]). r4: was 1.30, level
                            # (rear_3q: the photo's top edge rises from v 341 at the tail to v 315 at y -1.1)
REAR_DECK_Z_FWD = 1.345     # inner top edge at y -1.10, where it meets the gusset / shock-top area. r5: was 1.37
                            # (rear_3q: inner edge ~12 px / 3 cm above the photo at y -1.3..-1.6; tail face 1.33 fits)
REAR_DECK_INNER_HALF_W = 0.46  # r4 new: |x| of that inner top edge (rear.png inner top corner 0.42-0.47)
REAR_POD_SHOULDER_Z = 1.30     # top of the rounded outer shoulder. r6: was 1.27 (rear.png: the photo's outer top corner
                               # (u 1143 / 380, v ~197) back-projects to (0.73, 1.28) @ y -1.0 / (0.70, 1.30) @ -1.1; the
                               # render corner sat 3-7 cm lower and rounder; the pod reads as a broad flat carbon shield)
REAR_POD_SHOULDER_R = 0.05     # r6: was 0.08 (squarer shoulder, same rear.png evidence). Shoulder half-widths unchanged
                               # (the table below is already as wide as the photo corner at y -1.0..-1.1)
TAIL_HALF_W = 0.585            # pod / tail-block half-width at the tail face y -2.12. r4: was 0.62 (rear.png: tail
                               # lamp housing 3.4 cm narrower, photo 0.585)
# r4 new: (y, half-width) of the shoulder at deck height (rear.png pod outline: r3 model 4.9 cm too wide @ -1.2,
# 3.4 @ -1.55, 2.3 @ -1.9). Narrower than REAR_POD_HALF_W: the pod side leans in above z ~1.15.
REAR_POD_SHOULDER_HALF_W = [(-0.95, 0.79), (-1.20, 0.71), (-1.55, 0.665), (-1.90, 0.61), (-2.12, TAIL_HALF_W)]


def rear_deck_z(y):
    """r4: height of the pod deck's inner top edge at station y (linear from the tail face to y -1.10)."""
    y0, y1 = -2.12, -1.10
    t = min(1.0, max(0.0, (y - y0) / (y1 - y0)))
    return REAR_DECK_Z + (REAR_DECK_Z_FWD - REAR_DECK_Z) * t


TAIL_BLOCK_Y = (-2.12, -1.86)  # the squared-off tail block with the red tail light
TAIL_BLOCK_Z = (1.10, REAR_DECK_Z)  # tail block bottom / top (top = deck inner edge). r4: top was 1.30. The rear face
                               # is a curved shield: its outer edge arcs from the top inner corner down to the lamp
TAIL_LIGHT_XZ = (-0.545, 1.235)  # tail-lamp lens centre on the tail-block rear face (left; mirror x), in the face's
                                 # outer lower corner. r4: was (-0.575, 1.205) (rear.png lens centre ~(-0.555, 1.235))
TAIL_LIGHT_WH = (0.060, 0.110)   # lens width x height. r4: was (0.075, 0.150) (rear.png lens ~30 % smaller)

# r3 new: plan-view half-width targets of the body skin, (y, half-width), linear between knots. Parts that live
# under the skin (shock reservoirs, frame, cage) must stay inside them; the body must not exceed them.
# r5: FRONT_CLIP_HALF_W = plan outline of the front-clip skin at crown height (z 0.9-1.1) = the outer/front edge of
# the short "wing" fenders, which roll in fast ahead of the cowl; ahead of y 1.30 only the hood beak (HOOD_BEAK_HALF_W)
# continues to the nose. Inboard of |x| 0.40 the wing's front edge runs nearly transverse to meet the beak side at
# about (+-0.21, 1.35-1.40, 0.93) (front.png). Was [(0.30, 0.81), (0.50, 0.78), (0.70, 0.75), (0.90, 0.72),
# (1.10, 0.675), (1.30, 0.645), (1.50, 0.615)] (front_3q: near wing edge back-projects to |x| 0.35-0.44 at y 1.15-1.30;
# rear_3q: GLX body side ends at y ~0.75-0.85 at |x| 0.75).
FRONT_CLIP_HALF_W = [(0.30, 0.81), (0.50, 0.78), (0.70, 0.75), (0.85, 0.72), (1.00, 0.58), (1.15, 0.47),
                     (1.30, 0.40)]
FRONT_CLIP_LOWER_HALF_W = [(0.50, 0.71), (0.70, 0.67), (0.90, 0.67), (1.10, 0.64), (1.30, 0.59)]  # z 0.6-0.75
# r6 new: (z, max half-width) of the body's front lower corner = the door front / fender side for y 0.70-0.90 seen
# head-on. front.png outline back-projected at y 0.85 (left and right agree to 3 mm): the side tucks UNDER below the belt.
# The r5 skin kept going straight down at |x| 0.745-0.75 (1.4 / 3.9 / 6.8 / ~11 cm too wide at z 0.90 / 0.81 / 0.72 /
# 0.55) and showed the rear paddle tyres beside it. Body skin, the interior door card and the chassis frame rails ahead
# of y ~0.5 (frame_main_loop at |x| 0.70, z 0.50) must all stay inside it (front.png shows only background there).
FRONT_CORNER_HALF_W_Z = [(1.075, 0.717), (0.99, 0.728), (0.90, 0.718), (0.81, 0.70), (0.72, 0.68), (0.63, 0.66),
                         (0.54, 0.633)]
REAR_POD_HALF_W = [(-0.95, 0.81), (-1.15, 0.775), (-1.50, 0.735), (-2.12, TAIL_HALF_W)]  # rear pods, LOWER side
                                             # (z <= ~1.15; the shoulder is REAR_POD_SHOULDER_HALF_W). The rear tyre
                                             # inner face is at |x| 0.785: keep >= 1 cm clear of it. r4: tail knot
                                             # follows TAIL_HALF_W 0.62 -> 0.585

# ---------------- cockpit (HARD POINTS) ----------------
SEAT_X = 0.36               # seat centre lines at x = -SEAT_X (driver) and +SEAT_X
SEAT_H_POINT_Z = 0.62       # hip point height
SEAT_H_POINT_Y = -0.30
DRIVER_EYE = (-0.36, -0.25, 1.255)      # r3: was y -0.20 (eye floated 0.27 m ahead of the seat back; a belted,
PASSENGER_EYE = (+0.36, -0.25, 1.255)   # HANS-equipped head rests on the headrest -> eye ~0.20-0.22 ahead of it)
STEERING_WHEEL_CENTRE = (-0.36, 0.30, 0.955)
STEERING_WHEEL_R = 0.175    # 350 mm suede wheel, rim centre-line radius
STEERING_COLUMN_DIR = (0.0, -0.92, 0.40)   # unit vector from the dash toward the driver (up-back)
DASH_TOP_Z = 1.02           # screen shelf (unchanged)
DASH_FACE_Y = 0.52          # rear face of the dash at screen height
# r6 new: top of the dash's rolled carbon BROW right behind the windshield base (y ~0.62-0.74), (in front of each seat,
# |x| 0.28-0.60 ; centre |x| < 0.22). front.png: the opaque band under the windshield tops out at z ~1.15 (seat cushions
# and harness pads hidden below it; the r5 model showed them down to z 1.10); front_3q: ~1.125; interior_dash.png: a
# thick rolled brow well above the screens. The centre stays <= 1.115 so the hood beak (y 0.85-1.1, z 1.04-1.10) still
# shows over it from DRIVER_EYE in the 78 deg cockpit view (eye -> beak edge ray passes z 1.119 at y 0.70, |x| 0.23).
DASH_BROW_Z = (1.13, 1.115)

# ---------------- materials palette (sRGB hex) ----------------
COLORS = {
    'orange': '#ff5a0d',        # livery orange
    'cage_gray': '#484b50',     # roll-cage tubes: dark charcoal gunmetal powder coat (metallic ~0.6 + clear coat for a
                                # crisp streak). r5 (lead decision): was #7d8187, which read light silver in Cycles and
                                # ivory in the game cockpit; front_3q cage tube bodies sample RGB ~20-60, highlights
                                # 180-190 (game LOOKS 'Cage gunmetal' 0x45484d). r4: was #5c5f63
    'arm_gray': '#868a92',      # r5 new: suspension arms AND the front / rear bumper tubes stay lighter medium grey /
                                # silver (front_3q, front.png, rear.png bumper read clearly lighter than the cage)
    'rubber': '#262626',        # r4 new: tyre tread / paddles / sidewall base (photo sidewall ~26 sRGB)
    'rubber_groove': '#161616', # r4 new: tread grooves
    'carbon_base': '#121314',
    'suede_black': '#141414',
    'leather_gray': '#2a2b2d',
    'stitch_orange': '#ff6a1a',
    'tail_red': '#b0060a',
}

# ---------------- texture atlas for the body livery ----------------
# Side panels are UV-mapped by projecting (y, z) onto this window.
LIVERY_Y = (-2.50, 2.00)
LIVERY_Z = (0.30, 1.60)
# atlas layout (livery.png, 4096 x 4096):  top half  v in [0.5, 1] = LEFT side (seen from the left)
#                                          bottom half v in [0, 0.5] = RIGHT side (seen from the right)
# Inside each half: u runs along the car, v runs up.
# Left side: u = (LIVERY_Y[1] - y) / span  (front of car on the left of the image when seen from the left)
# Right side: u = (y - LIVERY_Y[0]) / span (front of car on the right, like ref/side_right_red_variant.png)
# Top surfaces (hood, roof, deck) use livery_top.png with u = (x + 1) / 2, v = (y - LIVERY_Y[0]) / span.

# ---------------- chassis hard points (frame <-> body <-> suspension <-> interior) ----------------
FLOOR_Z = 0.475             # top of the cockpit floor pan, flush with the rail bottoms (0.4746). r4: was 0.45 (follows
                            # FRAME_RAIL_Z; side photo: nothing below z 0.48-0.49 between the wheels). r3: was 0.38
FRAME_RAIL_X = 0.70         # lower main frame rails (tube centres) run at x = +-0.70 ...
FRAME_RAIL_Z = 0.50         # ... and this height, from y = +1.15 back to y = -1.15. r4: was 0.47 (rail bottom 0.445
                            # still showed as a gunmetal strip 3-4 cm under the photo's bottom line in side / front_3q;
                            # now bottom 0.475, hidden behind the 0.50 sill). r3: was 0.42
CAGE_TUBE_R = 0.0222        # 1.75" OD cage tube
FRAME_TUBE_R = 0.0254       # 2.0" OD main frame tube
SMALL_TUBE_R = 0.0159       # 1.25" bracing
# cage nodes (left side; mirror x for the right)
A_PILLAR_FOOT = (-0.63, 0.74, 1.08)    # windshield corner at the cowl. r4: was x -0.72 (front.png: both pillars'
                                       # outer edges 27-45 px inside the model's, centre |x| 0.59-0.61 nearly vertical;
                                       # front_3q: pillar run 30-35 px off = foot at |x| ~0.63). Pillar now nearly
                                       # vertical in front view; tight (~7 cm) bend into the roof under the light bar
A_PILLAR_TOP = (-0.60, 0.45, 1.445)    # roof front corner
B_PILLAR_FOOT = (-0.74, -0.64, 1.08)   # rear of the door opening at belt height
B_PILLAR_TOP = (-0.56, -0.45, 1.475)   # roof rear corner. r5: z was 1.445 - the roof skin rose in r4 (ROOF_REAR_Z 1.54)
                                       # but the rails stayed low and hung 2-4 cm under it ("roof rack"; side photo window
                                       # top 1.456-1.48). Now the roof rails ramp from A_PILLAR_TOP z 1.445 (unchanged,
                                       # front_3q header bottom 1.42-1.445) up to 1.475 here, inside the closed roof band.
                                       # rear.png: the raised corner hides under the spoiler. r4: x was -0.60 (rear.png:
                                       # hoop/roof-rear corners 5.5-7 cm outside the photo's; the roof tapers in plan)
MAIN_HOOP_Y = -0.80                    # main-hoop leg foot on the frame rail (the hoop leans forward through B_PILLAR_FOOT
                                       # to B_PILLAR_TOP; x +-0.70 at the floor)
# r5 new: REAR CAGE OVER THE ENGINE BAY (rear.png, rear_3q_right, seat_closeup, side photo). The big X-brace does NOT
# lie in the main-hoop plane: it spans over the striped engine cover, from the roof's rear corners back to a cross
# tube between the rear upper rails, so from behind it is seen IN FRONT of the striped cover (rear.png) and from the
# cabin it rises over the firewall top (seat_closeup). Evidence: the cross tube under the X's lower ends ends on the
# rear upper rails (rear.png u 405 / 1150 at v 333 = |x| 0.57 at y -1.68; at y -0.8 it would be |x| 0.8, wider than
# the hoop); the near-vertical posts in rear.png (u ~520-545 from the roof corners down to that tube) are the rear
# braces; rear_3q shows the far brace above the pod; side photo: everything stays under the fin / pod deck.
# Rear-view (rear.png, 1536 x 1024) pixel targets: X upper ends (545, 112) / (995, 112), lower ends (556, 326) /
# (985, 326), crossing ~(772, 220); brace posts u ~525-545 v 70-330; cross tube v ~333, u 405-1150.
REAR_XBAR_YZ = (-1.68, 1.21)           # (y, z) of the rail-to-rail cross tube over the engine bay (left/right ends on
                                       # the rear upper rails, |x| ~0.55-0.58)
REAR_BRACE_END = (-0.40, -1.68, 1.205) # left rear brace: B_PILLAR_TOP -> this point on the cross tube (mirror x). It runs
                                       # along / just inboard of the pod deck's inner top edge (|x| 0.49 @ y -1.0)
X_BRACE_TOP = (-0.515, -0.79, 1.40)    # left upper end of the X, on the left rear brace (mirror x)
X_BRACE_BOT = (-0.33, -1.68, 1.215)    # left lower end, on the cross tube. Each arm runs from one side's TOP to the
                                       # OTHER side's BOT (straight 1.5" tube); the arms cross at ~(0, -1.34, 1.29)
DOOR_OPENING_Y = (-0.62, 0.70)         # the window/door opening between the pillars, above BELT_Z
FIREWALL_Y = -0.92                     # rear cockpit bulkhead (hex mesh grille + orange panel above it)
ENGINE_COVER_FRONT_YZ = (-0.92, 1.325)  # r6 new: front top edge (y, z) of the striped engine cover across |x| <= 0.40,
                                       # falling ~21 deg to the rear from there. rear.png: the photo panel's top edge at
                                       # v ~162 back-projects to z 1.327 @ y -0.92; the r5 cover (1.27) left a see-through
                                       # slot to the dash/hood. Stays >= 1 cm under the X arms (z 1.373 @ y -0.92, |x| 0.39)
                                       # and the rear braces (1.372 @ |x| 0.50); revisits the r5 'lower the lid' decision
FRONT_BULKHEAD_Y = 1.18                # front of the footwell
ENGINE_BAY = {'y': (-2.25, -0.95), 'x': (-0.62, 0.62), 'z': (0.32, 1.25)}
# front suspension pivots on the frame (left side; mirror x)
# r3: front.png / front_3q show both A-arms and the tie rods running in to the narrow nose right beside the
# bumper V-plate; lower arm inner pivots at z ~0.49-0.50 sloping DOWN outward to a ball joint near hub height
# (~(-0.745, 1.50, 0.435)), upper ball joint ~(-0.695, 1.50, 0.705) (upright leans in ~10 deg).
F_LOWER_PIVOTS = [(-0.13, 1.28, 0.49), (-0.10, 1.78, 0.50)]  # r3: was (-0.30, 1.28/1.78, 0.38)
F_UPPER_PIVOTS = [(-0.14, 1.30, 0.70), (-0.14, 1.72, 0.70)]  # r3: was x -0.40
F_SHOCK_TOPS = [(-0.222, 1.442, 0.83), (-0.355, 1.50, 0.87)]  # coilover, bypass (left; mirror x). r6: was
                                                           # (-0.39,1.60,0.945)/(-0.40,1.495,0.958) - set in r3 for a lower eye at
                                                           # |x| 0.60; with the r5 eyes (coil (-0.465,1.50,0.50), bypass
                                                           # (-0.632,1.467,0.485), unchanged) the shocks stood ~8 deg from vertical.
                                                           # GLX photos: both lean steeply INWARD. Coil: front.png spring axis
                                                           # ~36 deg, front_3q spring 27.8 deg in the image; the two-view
                                                           # triangulation leans it ~10 deg BACK in side view (a top at y 1.58
                                                           # gives 38 deg in front_3q - rejected), top z 0.83 keeps the cap ~1 cm
                                                           # under the hood beak's lower edge (z 0.80-0.81 at |x| 0.19-0.20).
                                                           # Bypass: front.png ~35 deg, front_3q top ray, and it must pass the
                                                           # upper A-arm's opening (rear leg y 1.42 / front leg 1.59 at x 0.48).
                                                           # r3: was (-0.44,1.48,1.12)/(-0.40,1.62,1.10)
F_STEER_RACK = (-0.11, 1.70, 0.62)                         # inner tie-rod end. r4: z was 0.59 (front.png AND front_3q:
                                                           # the heims beside the V-plate project exactly at z 0.62).
                                                           # r3: was (-0.22, 1.38, 0.55): the tie
                                                           # rods run in to heims beside the plate (|x| ~0.10, z ~0.60)
                                                           # IN FRONT of the coilovers (front.png, front_3q) = front steer
# rear suspension (trailing arm + radius rods)
R_TRAILING_PIVOT = (-0.72, -0.85, 0.51)    # r4: y was -0.84 (sleeve r ~0.03 + main-hoop leg r 0.022 at only 5.05 cm:
                                           # they intersected; now ~0.9 cm air). r3: was (-0.64, -0.30, 0.50). Side photo: pivot bolt at the lower rear
                                           # corner of the body behind the door, y -0.80 z 0.505 (also
                                           # rear_wheel_sidepod_right); placed 4 cm behind it and on the main-hoop leg's
                                           # outer side so the sleeve clears the leg (-0.70, -0.79) and the arm passes
                                           # inboard of the 1.93-track rear tyre. Moves the pivot out of the cockpit.
R_RADIUS_ROD_PIVOTS = [(-0.42, -1.20, 0.44), (-0.42, -1.25, 0.74)]
R_SHOCK_TOPS = [(-0.56, -1.05, 1.34), (-0.56, -1.22, 1.36)]  # coilover, bypass. r3: z was 1.22/1.24 - the FOX
                                                           # reservoir caps stand above the pod deck behind the gusset
R_DIFF_OUTPUT = (-0.22, -1.50, 0.46)                       # inner CV of the half shaft
