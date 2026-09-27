"""Doom Town — burnt desert trees.

Recursive branching swept as tapered tubes along curving paths, so limbs thin out and bend
instead of being straight sticks. Trunks get a root flare and charred bark.
"""
import math, random, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathutils import Matrix, Vector  # noqa: E402
from lib_map import Sub  # noqa: E402


def _perp(d):
    a = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    return d.cross(a).normalized()


def _limb(sub, mat, p, d, length, r0, r1, depth, rnd, curve, droop, char_mat, bg=False):
    segs = max(4, 4 + depth)
    path, radii = [], []
    pos = Vector(p)
    d = Vector(d).normalized()
    # one consistent bend axis per limb so it arcs instead of zig-zagging
    axis = (Matrix.Rotation(rnd.uniform(0, 6.283), 3, d) @ _perp(d)).normalized()
    bend = rnd.uniform(0.35, 1.05) * (1.0 + 0.4 * (3 - depth))
    for i in range(segs + 1):
        path.append(tuple(pos))
        t = i / segs
        radii.append(r0 * (1.0 - t) ** 1.35 + r1 * t)
        step = length / segs
        pos = pos + d * step
        d = (Matrix.Rotation(bend / segs, 3, axis) @ d)
        d = (d + Vector((rnd.uniform(-curve, curve), rnd.uniform(-curve, curve),
                         -droop)) * step).normalized()
    sub.tube(mat if depth > 1 else char_mat, path, radii, segs=max(5, 3 + depth * 2), bg=bg)
    if depth <= 0:
        return
    n = rnd.randint(2, 3) if depth > 1 else rnd.randint(1, 3)
    end_d = (Vector(path[-1]) - Vector(path[-2])).normalized()
    for k in range(n):
        t = rnd.uniform(0.55, 1.0)
        i = min(len(path) - 1, int(t * segs))
        base = Vector(path[i])
        side = _perp(end_d)
        side = (Matrix.Rotation(rnd.uniform(0, 6.283), 3, end_d) @ side).normalized()
        spread = rnd.uniform(0.55, 1.15) if depth > 1 else rnd.uniform(0.7, 1.6)
        nd = (end_d + side * spread).normalized()
        rr = radii[i] * rnd.uniform(0.60, 0.80)
        _limb(sub, mat, tuple(base), nd, length * rnd.uniform(0.58, 0.80),
              rr, rr * 0.30, depth - 1, rnd, curve * 1.3, droop * 1.6 + 0.02, char_mat, bg)


def build_tree(sub, h=4.6, seed=0, bark='bark', char='charred', lean=0.06, depth=3,
               variant=0):
    """variant 0: full crown. variant 1: snapped trunk with a short, angry crown."""
    rnd = random.Random(seed)
    # root flare
    for k in range(6):
        a = 2 * math.pi * k / 6 + rnd.uniform(-0.3, 0.3)
        r = rnd.uniform(0.30, 0.46)
        sub.tube(bark, [(math.cos(a) * r, math.sin(a) * r, 0.0),
                        (math.cos(a) * r * 0.5, math.sin(a) * r * 0.5, h * 0.09),
                        (0.0, 0.0, h * 0.22)],
                 [0.085, 0.10, 0.13], segs=6)
    trunk_h = h * (0.40 if variant else 0.46)
    d = Vector((rnd.uniform(-lean, lean), rnd.uniform(-lean, lean), 1.0)).normalized()
    _limb(sub, bark, (0, 0, 0.0), d, trunk_h, 0.250 if not variant else 0.290,
          0.120 if not variant else 0.155, depth, rnd, 0.05, 0.02, char)
    if variant:
        # a second, lower limb so the two placed trees do not read as the same asset
        a = rnd.uniform(0, 6.283)
        nd = Vector((math.cos(a) * 0.55, math.sin(a) * 0.55, 1.0)).normalized()
        _limb(sub, bark, (0, 0, trunk_h * 0.45), nd, trunk_h * 0.8, 0.130, 0.055,
              max(1, depth - 1), rnd, 0.08, 0.03, char)
    # a couple of snapped stumps low on the trunk
    for k in range(2):
        a = rnd.uniform(0, 6.283)
        z = trunk_h * rnd.uniform(0.35, 0.75)
        sub.tube(char, [(0, 0, z), (math.cos(a) * 0.45, math.sin(a) * 0.45, z + 0.22)],
                 [0.075, 0.035], segs=6)


def place(scn, x, y, h=4.6, seed=0, bg=False, collide=True, yaw=None, depth=None,
          variant=None):
    import random as _r
    rnd = _r.Random(seed * 7 + 3)
    sub = Sub()
    # hero trees get a fourth twig generation; the 30-odd background ones stay cheap
    depth = (3 if bg else 4) if depth is None else depth
    variant = (1 if seed % 3 == 0 else 0) if variant is None else variant
    build_tree(sub, h, seed, depth=depth, variant=variant)
    m = Matrix.Translation((x, y, 0.0)) @ Matrix.Rotation(
        rnd.uniform(0, 6.283) if yaw is None else yaw, 4, 'Z')
    sub.stamp(scn, m, bg=bg)
    if collide and not bg:
        scn.col_obj('COL_TREE', (x, y, 1.6), (0.7, 0.7, 3.2))
