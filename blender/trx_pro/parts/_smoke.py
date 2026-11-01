"""Pipeline smoke test (not a real part; files starting with _ are skipped by build.py)."""
from common import *
import spec


def build(C):
    for c, (x, y, z, r, w, front) in spec.WHEELS.items():
        t = cylinder('tire_' + c, r, w, (x, y, z), (0, 90, 0), M('rubber'))
        C.add(t, 'Wheel_' + c)
        u = box('upr_' + c, (0.06, 0.12, 0.2), (x - math.copysign(0.2, x), y, z), material=M('arm'))
        C.add(u, 'Upright_' + c)
    C.add(box('floor', (1.5, 3.0, 0.05), (0, 0, 0.38), material=M('carbon')))
    C.add(tube('cage', [spec.A_PILLAR_FOOT, spec.A_PILLAR_TOP, spec.B_PILLAR_TOP, spec.B_PILLAR_FOOT], spec.CAGE_TUBE_R, M('cage')))
    side = box('side', (0.02, 3.0, 0.6), (-0.81, 0, 0.78), material=M('livery'))
    uv_project(side, side_uv)
    C.add(side)
    a = (-0.30, 1.28, 0.38); b = (-0.95, 1.5, 0.33)
    C.segment('Link_FL_Lower_0', tube('arm', [a, b], 0.02, M('arm')), a, b, 'FL')
    s1 = (-0.44, 1.48, 1.12); s2 = (-0.80, 1.47, 0.36)
    C.segment('Shock_FL', cylinder('shock', 0.03, (V(s1) - V(s2)).length, ((s1[0] + s2[0]) / 2, (s1[1] + s2[1]) / 2, (s1[2] + s2[2]) / 2), material=M('satin_black')), s1, s2, 'FL', shock=True)
    sw = lathe('rim', [(0.16, -0.012), (0.19, -0.012), (0.19, 0.012), (0.16, 0.012), (0.16, -0.012)], M('suede'), segments=32)
    place(sw, spec.STEERING_WHEEL_CENTRE, spec.STEERING_COLUMN_DIR)
    C.add(sw, 'SteeringWheel')
    C.add(box('bar', (1.0, 0.08, 0.09), (0, 0.42, 1.53), material=M('satin_black')), 'LightBar')
