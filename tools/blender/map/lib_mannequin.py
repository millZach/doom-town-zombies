"""Doom Town — 1950s department-store / civil-defence test mannequins.

Lofted torso with a real waist and shoulders, a tapered neck, an egg head and two-segment
jointed limbs swept as tubes. Built in local space (+X forward, +Z up, origin between the feet)
and stamped through lib_map.Sub, so a figure can be toppled with any matrix.
"""
import math, random, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathutils import Matrix, Euler, Vector  # noqa: E402
from lib_map import Sub, squircle  # noqa: E402


def ring(z, hy, hx, n=2.3, segs=16):
    """Horizontal body cross-section: ellipse-ish, hx forward/back, hy across."""
    return [(x, y, z) for (y, x) in squircle(hy, hx, 0.0, n=n, segs=segs)]


TORSO = [(0.78, 0.150, 0.108), (0.86, 0.163, 0.114), (0.95, 0.152, 0.106),
         (1.04, 0.132, 0.094), (1.13, 0.150, 0.104), (1.22, 0.178, 0.114),
         (1.31, 0.196, 0.112), (1.38, 0.196, 0.104), (1.42, 0.150, 0.088),
         (1.45, 0.092, 0.070)]


def _limb(sub, mat, a, b, c, r0, r1, r2, segs=9):
    """Two-segment tapered limb through a -> b -> c with a rounded joint at b."""
    path, radii = [], []
    for i in range(5):
        t = i / 4.0
        path.append(tuple(Vector(a).lerp(Vector(b), t)))
        radii.append(r0 + (r1 - r0) * t)
    for i in range(1, 6):
        t = i / 5.0
        path.append(tuple(Vector(b).lerp(Vector(c), t)))
        radii.append(r1 + (r2 - r1) * t)
    sub.tube(mat, path, radii, segs=segs)
    sub.cyl(mat, b, r1 * 1.12, r1 * 1.6, segs)


def _arm(sub, mat, side, shoulder_pitch, spread, elbow, hand=True):
    s = side
    sh = Vector((0.0, s * 0.185, 1.345))
    d1 = Vector((math.sin(shoulder_pitch), s * math.sin(spread), -math.cos(shoulder_pitch)))
    d1.normalize()
    el = sh + d1 * 0.30
    ax = Vector((0, s, 0)).cross(d1).normalized()
    d2 = (Matrix.Rotation(elbow, 3, ax) @ d1).normalized()
    wr = el + d2 * 0.27
    _limb(sub, mat, tuple(sh), tuple(el), tuple(wr), 0.058, 0.043, 0.033)
    sub.cyl(mat, tuple(sh), 0.068, 0.10, 10)
    if hand:
        hd = wr + d2 * 0.09
        sub.box(mat, tuple(hd), (0.075, 0.045, 0.14),
                rot=(0, math.atan2(d2.x, -d2.z), 0))


def _leg(sub, mat, side, spread=0.0, bend=0.0):
    s = side
    hp = Vector((0.0, s * 0.088, 0.80))
    kn = Vector((0.02, s * (0.095 + spread), 0.44))
    an = Vector((0.0, s * (0.098 + spread * 1.4), 0.085))
    _limb(sub, mat, tuple(hp), tuple(kn), tuple(an), 0.098, 0.068, 0.050)
    sub.box(mat, (0.055, s * (0.098 + spread * 1.4), 0.042), (0.24, 0.10, 0.085))


def _head(sub, mat):
    sub.cyl(mat, (0.0, 0.0, 1.50), 0.052, 0.10, 12, r2=0.062)
    prof = [(1.545, 0.055), (1.575, 0.088), (1.615, 0.104), (1.660, 0.108),
            (1.705, 0.100), (1.740, 0.078), (1.760, 0.040)]
    secs = [ring(z, r, r * 0.92, n=2.0, segs=14) for (z, r) in prof]
    secs.insert(0, ring(1.525, 0.030, 0.028, n=2.0, segs=14))
    secs.append(ring(1.772, 0.014, 0.013, n=2.0, segs=14))
    sub.loft(mat, secs)


def build_mannequin(sub, clothes=None, burnt=False, missing=(), seed=0,
                    arms=((0.25, 0.16, 0.5), (-0.15, 0.22, 0.9)), scale=1.0):
    """clothes: None | 'dress' | 'suit'.  missing: any of arm_l, arm_r, head, leg_l, leg_r."""
    rnd = random.Random(seed)
    skin = 'charred' if burnt else 'skin_mann'
    sub.loft(skin, [ring(z, hy, hx) for (z, hy, hx) in TORSO])
    sub.cyl(skin, (0.0, 0.0, 0.775), 0.145, 0.06, 16)
    if 'head' not in missing:
        _head(sub, skin)
    else:
        sub.cyl(skin, (0.0, 0.0, 1.47), 0.055, 0.05, 12)
    for (side, key, a) in ((1, 'arm_l', arms[0]), (-1, 'arm_r', arms[1])):
        if key in missing:
            sub.cyl(skin, (0.0, side * 0.185, 1.345), 0.062, 0.09, 10)
            continue
        _arm(sub, skin, side, a[0], a[1], a[2])
    for (side, key) in ((1, 'leg_l'), (-1, 'leg_r')):
        if key in missing:
            sub.cyl(skin, (0.0, side * 0.088, 0.78), 0.10, 0.08, 12)
            continue
        _leg(sub, skin, side, rnd.uniform(-0.01, 0.02))

    if clothes == 'dress':
        cloth = 'charred' if burnt else 'fabric_red'
        secs = [ring(1.30, 0.206, 0.124), ring(1.18, 0.190, 0.122), ring(1.06, 0.150, 0.108),
                ring(0.96, 0.168, 0.120), ring(0.80, 0.225, 0.160), ring(0.62, 0.285, 0.205),
                ring(0.50, 0.310, 0.224)]
        sub.loft(cloth, secs, cap_start=False, cap_end=False)
        sub.box(cloth, (0.0, 0.0, 1.335), (0.20, 0.40, 0.05))
        for s in (-1, 1):
            sub.cyl(cloth, (0.0, s * 0.19, 1.29), 0.075, 0.13, 10)
    elif clothes == 'suit':
        shirt = 'charred' if burnt else 'cloth_white'
        coat = 'charred' if burnt else 'cloth_navy'
        secs = [ring(1.40, 0.200, 0.108), ring(1.31, 0.204, 0.120), ring(1.22, 0.186, 0.122),
                ring(1.12, 0.160, 0.112), ring(1.02, 0.146, 0.104), ring(0.94, 0.160, 0.114)]
        sub.loft(shirt, secs, cap_start=False, cap_end=False)
        sub.box(coat, (0.116, 0.0, 1.20), (0.03, 0.055, 0.34))
        sub.box(coat, (0.118, 0.0, 1.375), (0.03, 0.085, 0.07))
        secs = [ring(0.96, 0.176, 0.126), ring(0.80, 0.176, 0.126), ring(0.62, 0.160, 0.116)]
        sub.loft(coat, secs, cap_start=False, cap_end=False)
        for s in (-1, 1):
            sub.cyl(coat, (0.0, s * 0.088, 0.40), 0.082, 0.44, 10)

    if burnt:
        for i in range(8):
            z = rnd.uniform(0.5, 1.5)
            a = rnd.uniform(0, 6.28)
            sub.box('charred', (0.11 * math.cos(a), 0.19 * math.sin(a), z),
                    (0.09, 0.09, rnd.uniform(0.06, 0.18)), rot=(0, 0, a))


def place(scn, x, y, yaw, roll=0.0, pitch=0.0, dz=0.0, bg=False, collide=True, **kw):
    sub = Sub()
    build_mannequin(sub, **kw)
    m = (Matrix.Translation((x, y, dz)) @ Euler((roll, pitch, yaw), 'XYZ').to_matrix().to_4x4())
    sub.stamp(scn, m, bg=bg)
    if collide and not bg:
        scn.col_obj('COL_PROP', (x, y, dz + 0.85), (0.55, 0.65, 1.75), (0, 0, yaw))
    return m
