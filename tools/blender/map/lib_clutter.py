"""Doom Town — small street dressing: bins, tricycle, luggage, newspapers, tyre piles,
signage emblems and the fallout-shelter sign plate."""
import math, random, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathutils import Matrix, Euler, Vector  # noqa: E402
from lib_map import Sub  # noqa: E402
from lib_sign import sign_text  # noqa: E402


# --------------------------------------------------------------------------- signage
def annular_sector(r0, r1, a0, a1, n=8):
    pts = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        pts.append((r1 * math.cos(a), r1 * math.sin(a)))
    for i in range(n + 1):
        a = a1 + (a0 - a1) * i / n
        pts.append((r0 * math.cos(a), r0 * math.sin(a)))
    return pts


def _face_matrix(c, face):
    """Matrix putting a local XY polygon on a wall whose outward normal is `face`."""
    f = Vector(face).normalized()
    if abs(f.y) > 0.5:
        rot = Euler((math.pi / 2, 0, 0 if f.y < 0 else math.pi), 'XYZ')
    else:
        rot = Euler((math.pi / 2, 0, math.pi / 2 if f.x > 0 else -math.pi / 2), 'XYZ')
    return Matrix.Translation(Vector(c)) @ rot.to_matrix().to_4x4()


def trefoil(target, mat, c, face, r=0.30, depth=0.02, bg=False):
    """Proper radiation trefoil: three 60 deg blades around a central disc."""
    m = _face_matrix(c, face)
    for k in range(3):
        a0 = math.radians(90 + k * 120 - 30)
        target.prism(mat, annular_sector(r * 0.32, r, a0, a0 + math.radians(60), 9),
                     depth, m, bg=bg)
    target.prism(mat, annular_sector(0.0001, r * 0.175, 0, 2 * math.pi, 14), depth, m, bg=bg)


def fallout_sign(target, c, face, w=1.05, bg=False):
    """The 1961 civil-defence fallout shelter sign: black plate, three yellow triangles,
    and stencilled text underneath."""
    f = Vector(face).normalized()
    m = _face_matrix(c, face)
    target.prism('metal_rust', [(-w / 2 - 0.03, -w / 2 - 0.03), (w / 2 + 0.03, -w / 2 - 0.03),
                                (w / 2 + 0.03, w / 2 + 0.03), (-w / 2 - 0.03, w / 2 + 0.03)],
                 0.03, m, bg=bg)
    m2 = _face_matrix(Vector(c) + f * 0.03, face)
    target.prism('charred', [(-w / 2, -w / 2), (w / 2, -w / 2), (w / 2, w / 2), (-w / 2, w / 2)],
                 0.012, m2, bg=bg)
    m3 = _face_matrix(Vector(c) + f * 0.042, face)
    R = w * 0.40
    for k in range(3):
        a = math.radians(90 + k * 120)
        tip = (R * 0.16 * math.cos(a), R * 0.16 * math.sin(a))
        b1 = (R * math.cos(a - 0.62), R * math.sin(a - 0.62))
        b2 = (R * math.cos(a + 0.62), R * math.sin(a + 0.62))
        target.prism('paint_bus', [tip, b1, b2], 0.012, m3, bg=bg)
    up = Vector((0, 0, 1))
    run = f.cross(up) * -1.0
    sign_text(target, 'paint_stencil_y', 'FALLOUT', tuple(Vector(c) + f * 0.048 - up * (w * 0.30)),
              tuple(run), (0, 0, 1), tuple(f), h=w * 0.115, width=w * 0.80, depth=0.004, bg=bg)
    sign_text(target, 'paint_stencil_y', 'SHELTER', tuple(Vector(c) + f * 0.048 - up * (w * 0.43)),
              tuple(run), (0, 0, 1), tuple(f), h=w * 0.115, width=w * 0.80, depth=0.004, bg=bg)


def _clip_half(poly, nx, ny, d):
    """Sutherland-Hodgman clip of a convex polygon to the half-plane nx*x + ny*y <= d."""
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        da = nx * a[0] + ny * a[1] - d
        db = nx * b[0] + ny * b[1] - d
        if da <= 0.0:
            out.append(a)
        if (da > 0.0) != (db > 0.0):
            t = da / (da - db)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def _area(poly):
    s = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        s += x0 * y1 - x1 * y0
    return abs(s) * 0.5


def hazard_band(target, centre, run, up, face, w, h, mats=('paint_bus', 'charred'),
                stripe=0.19, angle=0.62, depth=0.010, bg=False):
    """A continuous diagonal hazard band.

    Each stripe is a parallelogram *clipped to the band rectangle*, so the band has straight
    edges and reads as one painted strip. Stacking rotated boxes instead (what this replaces)
    leaves their corners poking out and reads as a pile of loose tilted tiles.
    """
    r, u, f = Vector(run).normalized(), Vector(up).normalized(), Vector(face).normalized()
    c = Vector(centre)
    m = Matrix(((r.x, u.x, f.x, c.x), (r.y, u.y, f.y, c.y), (r.z, u.z, f.z, c.z), (0, 0, 0, 1)))
    rect = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    nx, ny = math.cos(angle), math.sin(angle)
    span = abs(nx) * w + abs(ny) * h
    k0, k1 = int(-span / (2 * stripe)) - 1, int(span / (2 * stripe)) + 1
    for k in range(k0, k1 + 1):
        poly = _clip_half(_clip_half(rect, nx, ny, (k + 1) * stripe), -nx, -ny, -k * stripe)
        if len(poly) >= 3 and _area(poly) > 1e-4:
            target.prism(mats[k % 2], poly, depth, m, bg=bg)


# --------------------------------------------------------------------------- props
def bin_can(scn, x, y, yaw=0.0, tipped=False, lid=True, seed=0, bg=False):
    rnd = random.Random(seed)
    sub = Sub()
    sub.cyl('metal_rust', (0, 0, 0.42), 0.30, 0.84, 16, r2=0.255)
    for z in (0.18, 0.42, 0.66):
        sub.cyl('metal_rust', (0, 0, z), 0.305 - (0.42 - z) * 0.06, 0.035, 16)
    sub.cyl('charred', (0, 0, 0.845), 0.28, 0.02, 16)
    for s in (-1, 1):
        sub.cyl('metal_dark', (0, s * 0.30, 0.60), 0.018, 0.24, 6, axis='x')
    if lid:
        sub.cyl('metal_rust', (0, 0, 0.88), 0.325, 0.06, 16, r2=0.28)
        sub.cyl('metal_dark', (0, 0, 0.94), 0.05, 0.07, 8)
    m = Matrix.Translation((x, y, 0.30 if tipped else 0.0)) @ Euler(
        (math.radians(92) if tipped else 0.0, 0, yaw), 'XYZ').to_matrix().to_4x4()
    sub.stamp(scn, m, bg=bg)
    if tipped:
        for i in range(9):
            a = rnd.uniform(-0.8, 0.8)
            d = rnd.uniform(0.5, 1.5)
            scn.box(rnd.choice(['plaster', 'charred', 'wood_bare', 'wallpaper_a']),
                    (x + math.cos(yaw + a) * d, y + math.sin(yaw + a) * d, 0.02),
                    (rnd.uniform(0.1, 0.26), rnd.uniform(0.1, 0.24), 0.03),
                    rot=(0, 0, rnd.uniform(0, 3)), bg=bg)
    elif not bg:
        scn.col_obj('COL_PROP', (x, y, 0.45), (0.66, 0.66, 0.92))


def tricycle(scn, x, y, yaw=0.0, toppled=True, seed=0):
    sub = Sub()
    fw, rw = 0.19, 0.115
    sub.cyl('rubber', (0.30, 0, fw), fw, 0.07, 14, axis='y')
    sub.cyl('chrome', (0.30, 0, fw), fw * 0.35, 0.08, 10, axis='y')
    for s in (-1, 1):
        sub.cyl('rubber', (-0.24, s * 0.20, rw), rw, 0.055, 12, axis='y')
        sub.cyl('chrome', (-0.24, s * 0.20, rw), rw * 0.4, 0.065, 8, axis='y')
    sub.tube('paint_red', [(0.30, 0, fw + 0.02), (0.12, 0, 0.30), (-0.20, 0, 0.30)], 0.022, segs=7)
    sub.tube('paint_red', [(-0.20, 0, 0.30), (-0.24, -0.20, rw + 0.02)], 0.018, segs=6)
    sub.tube('paint_red', [(-0.20, 0, 0.30), (-0.24, 0.20, rw + 0.02)], 0.018, segs=6)
    sub.cyl('chrome', (0.12, 0, 0.34), 0.016, 0.34, 8, axis='y')
    for s in (-1, 1):
        sub.cyl('rubber', (0.12, s * 0.17, 0.34), 0.022, 0.08, 8, axis='y')
    sub.box('cloth_navy', (-0.20, 0, 0.35), (0.22, 0.14, 0.05))
    m = Matrix.Translation((x, y, 0.20 if toppled else 0.0)) @ Euler(
        (math.radians(84) if toppled else 0.0, 0, yaw), 'XYZ').to_matrix().to_4x4()
    sub.stamp(scn, m)


def suitcase(scn, x, y, yaw=0.0, open_=False, seed=0, bg=False):
    rnd = random.Random(seed)
    scn.box('wood_bare', (x, y, 0.11), (0.62, 0.42, 0.22), rot=(0, 0, yaw), bg=bg)
    scn.box('charred', (x, y, 0.11), (0.64, 0.44, 0.03), rot=(0, 0, yaw), bg=bg)
    scn.cyl('chrome', (x, y - 0.22 * math.cos(yaw), 0.23), 0.02, 0.16, 6, axis='x',
            rot=(0, 0, yaw), bg=bg)
    if open_:
        c, s = math.cos(yaw), math.sin(yaw)
        scn.box('wood_bare', (x - 0.45 * c, y - 0.45 * s, 0.05), (0.62, 0.42, 0.10),
                rot=(0, 0, yaw), bg=bg)
        for i in range(7):
            scn.box(rnd.choice(['cloth_white', 'fabric_red', 'cloth_navy', 'fabric_olive']),
                    (x + rnd.uniform(-0.7, 0.3), y + rnd.uniform(-0.5, 0.5), 0.03),
                    (rnd.uniform(0.15, 0.35), rnd.uniform(0.12, 0.3), 0.035),
                    rot=(0, 0, rnd.uniform(0, 3)), bg=bg)


def newspapers(scn, x, y, r, n, seed=0, bg=False):
    rnd = random.Random(seed)
    for i in range(n):
        a = rnd.uniform(0, 6.283)
        d = r * math.sqrt(rnd.random())
        px, py = x + math.cos(a) * d, y + math.sin(a) * d
        if rnd.random() < 0.3:
            scn.box('plaster', (px, py, 0.035), (0.30, 0.22, 0.07),
                    rot=(0, 0, rnd.uniform(0, 3)), bg=bg)
        else:
            for k in range(rnd.randint(1, 3)):
                scn.box('plaster', (px + rnd.uniform(-0.1, 0.1), py + rnd.uniform(-0.1, 0.1),
                                    0.006 + k * 0.004),
                        (rnd.uniform(0.22, 0.34), rnd.uniform(0.17, 0.26), 0.004),
                        rot=(rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05),
                             rnd.uniform(0, 3)), bg=bg)


def tyre_pile(scn, x, y, n=5, seed=0, bg=False):
    rnd = random.Random(seed)
    for i in range(n):
        scn.cyl('rubber', (x + rnd.uniform(-0.08, 0.08), y + rnd.uniform(-0.08, 0.08),
                           0.11 + i * 0.17), 0.38, 0.19, 16, r2=0.38,
                rot=(rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), rnd.uniform(0, 3)),
                bg=bg)
        scn.cyl('charred', (x, y, 0.11 + i * 0.17), 0.21, 0.20, 12, bg=bg)
    if not bg:
        scn.col_obj('COL_PROP', (x, y, n * 0.085), (0.84, 0.84, n * 0.17))


def hydrant(scn, x, y, yaw=0.0):
    scn.cyl('paint_red', (x, y, 0.06), 0.20, 0.12, 12)
    scn.cyl('paint_red', (x, y, 0.36), 0.135, 0.52, 12, r2=0.115)
    scn.cyl('paint_red', (x, y, 0.64), 0.155, 0.08, 12)
    scn.cyl('paint_red', (x, y, 0.71), 0.085, 0.10, 12, r2=0.05)
    for s in (-1, 1):
        scn.cyl('paint_red', (x + s * 0.13 * math.cos(yaw), y + s * 0.13 * math.sin(yaw), 0.46),
                0.07, 0.12, 10, axis='x', rot=(0, 0, yaw))
    scn.col_obj('COL_PROP', (x, y, 0.4), (0.4, 0.4, 0.8))


def pallet(scn, x, y, yaw=0.0, lean=0.0, seed=0, bg=False):
    sub = Sub()
    for i in range(3):
        sub.box('wood_bare', (0, -0.44 + i * 0.44, 0.045), (1.15, 0.12, 0.09))
    for i in range(6):
        sub.box('wood_bare', (-0.52 + i * 0.21, 0, 0.105), (0.14, 1.05, 0.022))
    m = Matrix.Translation((x, y, 0.0)) @ Euler((lean, 0, yaw), 'XYZ').to_matrix().to_4x4()
    sub.stamp(scn, m, bg=bg)


def chainlink_panel(scn, x, y, yaw=0.0, flat=True, seed=0, bg=False):
    sub = Sub()
    for s in (-1, 1):
        sub.cyl('metal_rust', (s * 1.1, 0, 0.9), 0.035, 1.9, 8)
    for z in (0.05, 1.78):
        sub.cyl('metal_rust', (0, 0, z), 0.028, 2.2, 8, axis='x')
    for i in range(11):
        sub.box('metal_rust', (-1.05 + i * 0.21, 0, 0.9), (0.012, 0.010, 1.75),
                rot=(0, 0.05 * ((-1) ** i), 0))
    for i in range(9):
        sub.box('metal_rust', (0, 0, 0.12 + i * 0.2), (2.15, 0.010, 0.012))
    m = Matrix.Translation((x, y, 0.03 if flat else 0.0)) @ Euler(
        (math.radians(90) if flat else 0.0, 0, yaw), 'XYZ').to_matrix().to_4x4()
    sub.stamp(scn, m, bg=bg)


def skid_marks(scn, pts, w=0.9, seed=0, z=0.014):
    """Tyre marks as authored decals rather than black boxes lying on the road."""
    rnd = random.Random(seed)
    for (x0, y0, x1, y1) in pts:
        ln = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(ln / 2.6))
        ang = math.atan2(y1 - y0, x1 - x0) - math.pi / 2       # decal 'up' runs along the skid
        for i in range(n):
            t0, t1 = i / n, (i + 1) / n
            cx = x0 + (x1 - x0) * (t0 + t1) / 2
            cy = y0 + (y1 - y0) * (t0 + t1) / 2
            scn.decal('tyre', (cx, cy, z), (w, ln / n * 1.04), (0, 0, 1),
                      rot=ang + rnd.uniform(-0.03, 0.03), lift=0.004)


# --------------------------------------------------------------------------- blast debris
def debris_piece(scn, kind, x, y, yaw=0.0, s=1.0, seed=0, bg=False, tilt=None):
    """One piece of blast debris with real volume (environment.md #19).

    The street used to be strewn with flat 4 cm cards at three sizes; these are eight archetypes
    that sit on each other, curl, splinter and catch the low sun.
    """
    rnd = random.Random(seed)
    sub = Sub()
    pitch, roll = tilt if tilt else (rnd.uniform(-0.14, 0.14), rnd.uniform(-0.14, 0.14))
    lift = 0.0
    if kind == 'plank':
        ln, wd, th = rnd.uniform(0.9, 2.2) * s, rnd.uniform(0.11, 0.20) * s, 0.045 * s
        mat = rnd.choice(['wood_bare', 'wood_white', 'charred'])
        sub.box(mat, (0, 0, th / 2), (ln, wd, th), rot=(0, rnd.uniform(-0.03, 0.03), 0))
        for e in (-1, 1):                                    # splintered ends
            for k in range(3):
                sl = rnd.uniform(0.05, 0.22) * s
                sub.box(mat, (e * (ln / 2 + sl / 2), rnd.uniform(-0.35, 0.35) * wd,
                              th * rnd.uniform(0.3, 0.8)),
                        (sl, wd * rnd.uniform(0.18, 0.4), th * rnd.uniform(0.3, 0.7)),
                        rot=(0, rnd.uniform(-0.25, 0.25), rnd.uniform(-0.2, 0.2)))
        if rnd.random() < 0.5:                               # a bent nail
            sub.cyl('metal_rust', (rnd.uniform(-0.4, 0.4) * ln, 0, th + 0.02 * s), 0.008 * s,
                    0.07 * s, 5)
        lift = 0.0
    elif kind == 'sheet':
        wd, dp = rnd.uniform(0.7, 1.4) * s, rnd.uniform(0.5, 0.9) * s
        n = 7
        for i in range(n):
            t = (i + 0.5) / n - 0.5
            curl = 0.16 * s * (t * t * 4.0)
            sub.box('metal_rust', (t * wd, 0, curl + 0.02 * s), (wd / n * 1.02, dp, 0.018 * s),
                    rot=(0, -t * 1.1, rnd.uniform(-0.02, 0.02)))
        for e in (-1, 1):                                    # rolled edge
            sub.cyl('metal_rust', (0, e * dp / 2, 0.035 * s), 0.022 * s, wd * 0.98, 8, axis='x')
        lift = 0.0
    elif kind == 'shingle':
        for i in range(rnd.randint(3, 5)):
            sub.box('shingle', (rnd.uniform(-0.06, 0.06) * s, rnd.uniform(-0.06, 0.06) * s,
                                0.012 * s + i * 0.018 * s),
                    (rnd.uniform(0.3, 0.46) * s, rnd.uniform(0.22, 0.34) * s, 0.017 * s),
                    rot=(rnd.uniform(-0.18, 0.18), rnd.uniform(-0.18, 0.18), rnd.uniform(0, 3)))
    elif kind == 'paper':
        sub.rock('cloth_white', (0, 0, 0.055 * s), (0.20 * s, 0.17 * s, 0.11 * s), seed=seed, subd=1)
        for k in range(3):
            sub.box('cloth_white', (rnd.uniform(-0.1, 0.1) * s, rnd.uniform(-0.1, 0.1) * s,
                                    0.05 * s), (0.16 * s, 0.13 * s, 0.006 * s),
                    rot=(rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(0, 3)))
    elif kind == 'stucco':
        r = rnd.uniform(0.22, 0.42) * s
        sub.rock('plaster', (0, 0, r * 0.28), (r * 2.0, r * 1.7, r * 0.8), seed=seed, subd=1)
        for k in range(rnd.randint(2, 4)):                   # exposed lath
            a = rnd.uniform(0, 6.283)
            sub.box('wood_bare', (math.cos(a) * r * 0.8, math.sin(a) * r * 0.8, r * 0.45),
                    (r * 2.4, 0.035 * s, 0.012 * s),
                    rot=(0, rnd.uniform(-0.3, 0.3), a + rnd.uniform(-0.3, 0.3)))
    elif kind == 'wheel':
        R, tube = 0.33 * s, 0.028 * s
        bend = rnd.uniform(0.10, 0.22)
        secs = []
        for i in range(17):
            a = 2 * math.pi * i / 16
            cxp, cyp = math.cos(a) * R, math.sin(a) * R
            czp = bend * R * math.sin(a * 2)
            ring = []
            for k in range(6):
                b = 2 * math.pi * k / 6
                ring.append((cxp + math.cos(a) * tube * math.cos(b), cyp + math.sin(a) * tube * math.cos(b),
                             czp + tube * math.sin(b) + tube + 0.004))
            secs.append(ring)
        sub.loft('metal_rust', secs, closed=True, cap_start=False, cap_end=False)
        for k in range(8):
            a = math.pi * k / 8
            sub.cyl('chrome', (0, 0, tube + 0.004), 0.004 * s, R * 1.9, 4, axis='x',
                    rot=(0, 0, a))
        pitch = rnd.uniform(-0.5, 0.5)
    elif kind == 'picket':
        for k in range(rnd.randint(2, 3)):
            sub.box('wood_white', (k * 0.16 * s, 0, 0.022 * s),
                    (0.085 * s, rnd.uniform(0.6, 1.0) * s, 0.032 * s),
                    rot=(rnd.uniform(-0.05, 0.05), 0, rnd.uniform(-0.04, 0.04)))
        sub.box('wood_white', (0.16 * s, rnd.uniform(-0.2, 0.2) * s, 0.055 * s),
                (0.55 * s, 0.05 * s, 0.09 * s))
    else:                                                    # 'gravel'
        for k in range(rnd.randint(5, 9)):
            r = rnd.uniform(0.03, 0.09) * s
            sub.rock(rnd.choice(['rubble', 'concrete', 'brick']),
                     (rnd.uniform(-0.3, 0.3) * s, rnd.uniform(-0.3, 0.3) * s, r * 0.4),
                     (r * 2.2, r * 2.0, r), seed=seed * 31 + k, subd=1)
    m = Matrix.Translation((x, y, lift)) @ Euler((pitch, roll, yaw), 'XYZ').to_matrix().to_4x4()
    sub.stamp(scn, m, bg=bg)


DEBRIS_KINDS = ('plank', 'plank', 'sheet', 'shingle', 'paper', 'stucco', 'picket', 'gravel')


def debris_field(scn, n, bounds, avoid=(), seed=0, blast=(0.0, -12.0), bg=False, scale=1.0):
    """Scatter debris, thinning out toward the blast centre and clustering downwind of it."""
    rnd = random.Random(seed)
    x0, y0, x1, y1 = bounds
    placed = 0
    for i in range(n * 3):
        if placed >= n:
            break
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        skip = False
        for (ax, ay, ar) in avoid:
            if (x - ax) ** 2 + (y - ay) ** 2 < ar * ar:
                skip = True
                break
        if skip:
            continue
        d = math.hypot(x - blast[0], y - blast[1])
        if rnd.random() > min(1.0, 0.25 + d / 16.0):      # sparse right at the crater
            continue
        kind = rnd.choice(DEBRIS_KINDS if rnd.random() > 0.06 else ('wheel',))
        debris_piece(scn, kind, x, y, rnd.uniform(0, 6.283), scale * rnd.uniform(0.75, 1.25),
                     seed=seed * 97 + i, bg=bg)
        placed += 1
