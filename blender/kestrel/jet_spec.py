"""Kestrel 01: authored fighter dimensions, metres, X right / Y forward / Z up.

Original airframe, informed by F-16 photographs and general proportions, not a
manufacturer CAD reconstruction. See docs/KESTREL-REFERENCE.md for provenance.
"""
NAME = 'Kestrel 01'
LENGTH = 15.2
SPAN = 9.8
FIN_TOP = 4.8
ENGINE_Z = 2.16
DRIVER_EYE = (0, 3.34, 3.08)
CANOPY_HINGE = (0, 2.12, 2.92)
# Revision 02: landmark placement checked against the USAF three-view drawing.
# Cockpit builders keep their local coordinates; assembly applies this offset.
COCKPIT_OFFSET = (0, -.60, -.12)
WING_OFFSET = (0, -.45, 0)
INTAKE_OFFSET_Y = -.75

# y, half-width, top radius, bottom radius, center height. Ordered nose to tail.
STATIONS = [
    (7.60, .012, .012, .012, 1.98), (7.37, .065, .061, .055, 2.00),
    (7.00, .145, .13, .12, 2.04), (6.55, .245, .225, .19, 2.10),
    (6.00, .365, .315, .275, 2.17), (5.50, .46, .385, .35, 2.22),
    (5.08, .515, .425, .39, 2.27), (4.60, .56, .445, .415, 2.29),
    (4.00, .61, .44, .44, 2.30), (3.35, .65, .43, .47, 2.30),
    (2.60, .70, .45, .51, 2.26), (1.90, .77, .59, .58, 2.20),
    (1.10, .87, .68, .65, 2.16), (.15, .94, .69, .72, 2.14),
    (-.85, .95, .67, .75, 2.14), (-1.90, .91, .65, .75, 2.15),
    (-2.90, .83, .64, .74, 2.16), (-3.90, .73, .62, .69, 2.16),
    (-4.80, .65, .61, .63, 2.16), (-5.65, .60, .565, .58, 2.16),
    (-6.45, .57, .55, .55, 2.16), (-6.87, .56, .54, .54, 2.16),
]
# span station: x, leading y, trailing y, z, thickness/chord
WING = [(.62, 1.18, -3.15, 2.10, .075), (1.15, .92, -3.12, 2.10, .073),
        (2.10, .18, -3.04, 2.11, .070), (3.20, -.63, -2.96, 2.14, .067),
        (4.20, -1.35, -2.88, 2.18, .063), (4.78, -1.77, -2.83, 2.20, .060)]
TAIL = [(.55, -4.55, -7.15, 2.04, .065), (1.20, -4.84, -7.23, 2.00, .061),
        (2.80, -5.85, -7.15, 1.94, .050)]
CANOPY = [(2.10, .05, .02), (2.30, .27, .19), (2.65, .44, .43),
          (3.20, .51, .66), (3.85, .51, .69), (4.42, .43, .52),
          (4.85, .28, .25), (5.14, .025, .01)]
# Raked sill: a rising rear fairing and lower forward windscreen seat.
CANOPY_BASE = [(2.10,2.92),(2.65,2.82),(3.20,2.73),(3.85,2.69),(4.42,2.65),(5.14,2.62)]
INTAKE = [(4.35,.52,.16,.33,1.79), (4.30,.58,.20,.38,1.79),
          (4.15,.60,.22,.40,1.79), (3.65,.61,.24,.42,1.79),
          (2.85,.61,.28,.43,1.80), (1.80,.61,.35,.43,1.82),
          (.45,.58,.42,.43,1.85)]
INTAKE = [(y+INTAKE_OFFSET_Y,w,t,b,z) for y,w,t,b,z in INTAKE]
INTAKE_OUTER = INTAKE + [(-.80,.52,.35,.30,1.96),(-1.35,.42,.28,.22,2.04)]

PALETTE = {
    'airframe': '#74848c', 'underside': '#a3adb0', 'nose': '#414d53',
    'panels': '#5f7079', 'edge': '#39474f', 'orange': '#ec5d22',
    'ink': '#1c272d', 'white': '#e6e9e3', 'rubber': '#151b1f',
}
