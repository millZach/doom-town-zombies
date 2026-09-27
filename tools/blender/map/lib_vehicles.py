"""Doom Town — lofted 1940s/50s American vehicles.

Every body is skinned from cross-sections sampled along the car's length, so fenders, wheel
arches, shoulders and roofs are genuinely rounded instead of boxy. Bodies are built in vehicle
local space (+X forward, +Y left, +Z up, origin on the ground between the wheels) and stamped
into the scene through lib_map.Sub, so a wreck can be rolled onto its roof with a full matrix.
"""
import math, random, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathutils import Matrix, Euler, Vector  # noqa: E402
from lib_map import Sub, squircle  # noqa: E402
from lib_sign import sign_text  # noqa: E402

GLASS = 'glass_car'


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# --------------------------------------------------------------------------- generic pieces
def wheel(sub, x, y, r=0.40, w=0.26, flat=False, hub='chrome', tyre='rubber', steer=0.0):
    """Tyre with a real sidewall profile plus a hubcap."""
    squash = 0.80 if flat else 1.0
    zc = r * squash
    prof = [(-w / 2, 0.58), (-w / 2 + 0.015, 0.88), (-w / 2 + 0.05, 0.985), (-w / 2 + 0.09, 1.0),
            (w / 2 - 0.09, 1.0), (w / 2 - 0.05, 0.985), (w / 2 - 0.015, 0.88), (w / 2, 0.58)]
    segs = 18
    secs = []
    cs, sn = math.cos(steer), math.sin(steer)
    for (dy, rf) in prof:
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            rr = r * rf
            zz = rr * math.sin(a)
            xx = rr * math.cos(a)
            if flat:
                zz *= squash
                bulge = max(0.0, -math.sin(a)) * 0.10 * r
                dyy = dy * (1.0 + bulge / max(w, 0.01) * 2.2)
            else:
                dyy = dy
            ring.append((x + xx * cs - dyy * sn, y + dyy * cs + xx * sn, zc + zz))
        secs.append(ring)
    sub.loft(tyre, secs)
    # hubcap: shallow chrome dome on the outer face
    outer = w / 2 + 0.005
    dsec = []
    for (dy, rf) in ((outer, 0.0), (outer - 0.005, 0.18), (outer - 0.02, 0.36),
                     (outer - 0.05, 0.50), (outer - 0.09, 0.56)):
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            rr = r * rf
            zz = rr * math.sin(a) * (squash if flat else 1.0)
            xx = rr * math.cos(a)
            dyy = dy if y > 0 else -dy
            ring.append((x + xx * cs - dyy * sn, y + dyy * cs + xx * sn, zc + zz))
        dsec.append(ring)
    sub.loft(hub, dsec[::-1] if y < 0 else dsec)


def bar(sub, mat, pts, w=0.16, h=0.18):
    """Rectangular bar swept along a path (bumpers, trim)."""
    secs = []
    n = len(pts)
    for i, p in enumerate(pts):
        a = Vector(pts[max(i - 1, 0)])
        b = Vector(pts[min(i + 1, n - 1)])
        d = (b - a)
        d.z = 0
        if d.length < 1e-6:
            d = Vector((1, 0, 0))
        d.normalize()
        u = Vector((-d.y, d.x, 0))
        v = Vector((0, 0, 1))
        secs.append([tuple(Vector(p) + u * (w / 2) + v * (h / 2)),
                     tuple(Vector(p) - u * (w / 2) + v * (h / 2)),
                     tuple(Vector(p) - u * (w / 2) - v * (h / 2)),
                     tuple(Vector(p) + u * (w / 2) - v * (h / 2))])
    sub.loft(mat, secs)


def headlight(sub, x, y, z, r=0.15, out=1.0):
    sub.cyl('chrome', (x - 0.03 * out, y, z), r * 1.12, 0.10, 14, axis='x', r2=r * 0.92)
    sub.cyl(GLASS, (x + 0.01 * out, y, z), r * 0.92, 0.05, 14, axis='x')
    sub.cyl('chrome', (x + 0.03 * out, y, z), r * 0.30, 0.03, 10, axis='x')


def seam(sub, mat, secfn, x, z0, z1, steps=7, w=0.022):
    """A panel gap that follows the curved body surface."""
    for i in range(steps):
        z = z0 + (z1 - z0) * (i + 0.5) / steps
        y = secfn(x, z)
        if y is None:
            continue
        for s in (-1, 1):
            sub.box(mat, (x, s * y, z), (w, 0.02, (z1 - z0) / steps * 1.08))


# --------------------------------------------------------------------------- sedan
class Sedan:
    L0, L1 = -2.56, 2.56
    WHEEL = (1.52, -1.56)
    WR, WW = 0.40, 0.26
    C0, C1 = -1.38, 1.08          # cabin
    PILLARS = (0.72, -0.05, -1.08)

    def hw(self, x):
        t = abs(x) / 2.56
        w = 0.95 * (1.0 - 0.34 * t ** 3.2)
        for xw in self.WHEEL:
            w += 0.045 * math.exp(-((x - xw) / 0.62) ** 2)
        return w

    def belt(self, x):
        z = 1.055
        z -= 0.16 * max(0.0, (x - 0.55) / 2.0) ** 1.5
        z -= 0.11 * max(0.0, (-x - 0.95) / 1.6) ** 1.5
        return z

    def sill(self, x):
        z = 0.265
        for xw in self.WHEEL:
            d = abs(x - xw)
            if d < 0.575:
                z = max(z, 0.335 + math.sqrt(max(0.0, 0.575 ** 2 - d ** 2)) * 0.82)
        z = max(z, 0.30 + 0.9 * max(0.0, (abs(x) - 2.30) / 0.26))
        return z

    def cab_hw(self, x):
        t = (x - (self.C0 + self.C1) / 2) / ((self.C1 - self.C0) / 2)
        return 0.815 * (1.0 - 0.20 * t ** 2)

    def cab_top(self, x):
        z = 1.545
        z -= 0.44 * max(0.0, (x - 0.42) / 0.66) ** 1.4
        z -= 0.38 * max(0.0, (-x - 0.86) / 0.52) ** 1.4
        return z

    def surface_y(self, x, z):
        b, s = self.belt(x), self.sill(x)
        if not (s < z < b):
            return None
        hz = (b - s) / 2.0
        u = (z - (b + s) / 2.0) / hz
        u = max(-0.999, min(0.999, u))
        return self.hw(x) * (1 - abs(u) ** 5.0) ** (2.0 / 5.0)


def build_sedan(sub, spec=None, paint='paint_red', burnt=False, flat=(1, 0, 0, 1), seed=0,
                roof_scorch=True, smashed=True):
    sp = spec or Sedan()
    body = 'paint_scorch' if burnt else paint
    rnd = random.Random(seed)
    N = 58
    xs = [sp.L0 + (sp.L1 - sp.L0) * i / (N - 1) for i in range(N)]

    # ---- lower body
    secs = []
    for x in xs:
        b, s = sp.belt(x), sp.sill(x)
        pts = squircle(sp.hw(x), (b - s) / 2.0, (b + s) / 2.0, n=5.0, segs=26)
        secs.append([(x, y, z) for (y, z) in pts])
    sub.loft(body, secs)

    # ---- cabin: glass shell, then paint pillars and roof on top of it
    M = 26
    cxs = [sp.C0 + (sp.C1 - sp.C0) * i / (M - 1) for i in range(M)]
    gsecs = []
    for x in cxs:
        t = sp.cab_top(x)
        b = sp.belt(x) - 0.04
        pts = squircle(sp.cab_hw(x), (t - b) / 2.0, (t + b) / 2.0, n=4.0, segs=22)
        gsecs.append([(x, y, z) for (y, z) in pts])
    sub.loft('charred' if burnt else GLASS, gsecs)

    def cab_ring(x, grow, t0, t1, segs):
        t = sp.cab_top(x)
        b = sp.belt(x) - 0.04
        pts = squircle(sp.cab_hw(x) + grow, (t - b) / 2.0 + grow, (t + b) / 2.0, n=4.0,
                       segs=segs, t0=t0, t1=t1)
        return [(x, y, z) for (y, z) in pts]

    # roof shell (top arc, given thickness by an inner return arc)
    rs = []
    for x in cxs:
        outer = cab_ring(x, 0.030, math.radians(46), math.radians(134), 14)
        inner = cab_ring(x, 0.000, math.radians(134), math.radians(46), 14)
        rs.append(outer + inner)
    sub.loft(body, rs)
    # pillars
    for px in sp.PILLARS:
        ps = []
        for dx in (-0.055, 0.055):
            x = max(sp.C0 + 0.02, min(sp.C1 - 0.02, px + dx))
            outer = cab_ring(x, 0.028, math.radians(2), math.radians(178), 16)
            inner = cab_ring(x, 0.000, math.radians(178), math.radians(2), 16)
            ps.append(outer + inner)
        sub.loft(body, ps)
    # beltline chrome and a rocker strip
    belt_pts = [(x, 0, 0) for x in cxs]
    for s in (-1, 1):
        pts = [(x, s * (sp.hw(x) + 0.008), sp.belt(x) - 0.080) for x in xs[9:-9]]
        bar(sub, 'chrome', pts, 0.018, 0.030)
        pts = [(x, s * (sp.hw(x) * 0.93), 0.315) for x in xs[13:-13]]
        bar(sub, 'chrome', pts, 0.016, 0.028)

    # ---- bumpers
    for (bx, sgn) in ((sp.L1 + 0.06, 1), (sp.L0 - 0.06, -1)):
        pts = []
        for k in range(11):
            u = -1 + 2 * k / 10.0
            yy = u * 0.94
            xx = bx - 0.16 * u * u * sgn
            pts.append((xx, yy, 0.50))
        bar(sub, 'chrome', pts, 0.16, 0.20)
        for u in (-0.55, 0.55):
            sub.cyl('chrome', (bx - 0.05 * sgn, u * 0.94, 0.60), 0.055, 0.30, 10)

    # ---- grille + lights + trim
    gx = sp.L1 - 0.08
    sub.box('charred', (gx - 0.03, 0.0, 0.76), (0.08, 1.42, 0.30))
    for k in range(9):
        sub.box('chrome', (gx, -0.62 + k * 0.155, 0.76), (0.06, 0.055, 0.30))
    sub.box('chrome', (gx + 0.01, 0.0, 0.92), (0.07, 1.50, 0.05))
    sub.box('chrome', (gx + 0.01, 0.0, 0.60), (0.07, 1.50, 0.05))
    for s in (-1, 1):
        headlight(sub, sp.L1 - 0.10, s * 0.68, 0.95, 0.155)
        sub.box('paint_red' if not burnt else 'charred',
                (sp.L0 + 0.07, s * 0.72, 0.86), (0.07, 0.22, 0.15))
        # door handles + seams
        sub.cyl('chrome', (-0.52, s * (sp.hw(-0.52) + 0.02), 0.86), 0.022, 0.16, 6, axis='x')
        sub.cyl('chrome', (0.44, s * (sp.hw(0.44) + 0.02), 0.86), 0.022, 0.16, 6, axis='x')
        # wing mirror
        sub.cyl('chrome', (0.86, s * (sp.hw(0.86) + 0.07), 1.06), 0.014, 0.16, 6)
        sub.box('chrome', (0.86, s * (sp.hw(0.86) + 0.10), 1.16), (0.09, 0.05, 0.12))
    for xs_ in (-1.05, 0.02, 0.98):
        seam(sub, 'charred', sp.surface_y, xs_, sp.sill(xs_) + 0.06, sp.belt(xs_) - 0.03)
    # bonnet / boot shut lines
    for xx in (1.02, -1.16):
        for k in range(9):
            yy = -0.72 + k * 0.18
            sub.box('charred', (xx, yy, sp.belt(xx) + 0.005), (0.02, 0.18, 0.02))

    # ---- wheels
    for i, (wx, sgn) in enumerate(((sp.WHEEL[0], 1), (sp.WHEEL[0], -1),
                                   (sp.WHEEL[1], 1), (sp.WHEEL[1], -1))):
        wheel(sub, wx, sgn * 0.80, sp.WR, sp.WW, flat=bool(flat[i]),
              steer=rnd.uniform(-0.12, 0.12) if i < 2 else 0.0)
        sub.cyl('charred', (wx, sgn * 0.74, 0.44), 0.44, 0.22, 14, axis='y')

    # ---- damage
    if roof_scorch and not burnt:
        for k in range(10):
            x = rnd.uniform(sp.C0 + 0.2, sp.C1 - 0.2)
            sub.box('charred', (x, rnd.uniform(-0.5, 0.5), sp.cab_top(x) + 0.028),
                    (rnd.uniform(0.2, 0.5), rnd.uniform(0.2, 0.5), 0.02),
                    rot=(0, 0, rnd.uniform(0, 3)))
    if smashed:
        for k in range(7):
            x = rnd.uniform(sp.C0 + 0.3, sp.C1 - 0.3)
            sub.box(GLASS, (x, rnd.uniform(-1.0, 1.0), 0.02),
                    (rnd.uniform(0.06, 0.16), rnd.uniform(0.06, 0.16), 0.006),
                    rot=(0, 0, rnd.uniform(0, 3)))


# --------------------------------------------------------------------------- pickup
class Pickup(Sedan):
    L0, L1 = -2.70, 2.60
    WHEEL = (1.58, -1.62)
    WR, WW = 0.44, 0.28
    C0, C1 = -0.42, 1.02
    PILLARS = (0.78, -0.30)

    def hw(self, x):
        t = abs(x) / 2.7
        w = 0.97 * (1.0 - 0.26 * t ** 3.4)
        for xw in self.WHEEL:
            w += 0.05 * math.exp(-((x - xw) / 0.60) ** 2)
        return w

    def belt(self, x):
        if x < -0.36:
            return 1.06
        z = 1.10 - 0.16 * max(0.0, (x - 0.9) / 1.7) ** 1.4
        return z

    def sill(self, x):
        z = 0.28
        for xw in self.WHEEL:
            d = abs(x - xw)
            if d < 0.60:
                z = max(z, 0.36 + math.sqrt(max(0.0, 0.60 ** 2 - d ** 2)) * 0.84)
        z = max(z, 0.32 + 0.9 * max(0.0, (abs(x) - 2.42) / 0.28))
        return z

    def cab_hw(self, x):
        t = (x - (self.C0 + self.C1) / 2) / ((self.C1 - self.C0) / 2)
        return 0.80 * (1.0 - 0.14 * t ** 2)

    def cab_top(self, x):
        return 1.72 - 0.52 * max(0.0, (x - 0.46) / 0.56) ** 1.4


def build_pickup(sub, paint='paint_teal', seed=0, burnt=False):
    sp = Pickup()
    build_sedan(sub, sp, paint, burnt, flat=(0, 1, 0, 0), seed=seed, smashed=True)
    body = 'paint_scorch' if burnt else paint
    # load bed floor, ribs and tailgate
    sub.box('metal_rust', (-1.55, 0.0, 1.00), (2.10, 1.62, 0.05))
    for k in range(7):
        sub.box('metal_rust', (-2.45 + k * 0.30, 0.0, 1.035), (0.06, 1.60, 0.03))
    sub.box(body, (-2.66, 0.0, 0.70), (0.10, 1.86, 0.72))
    for s in (-1, 1):
        sub.box('chrome', (-2.60, s * 0.82, 0.70), (0.06, 0.06, 0.66))
    # spare wheel lying in the bed
    sub.cyl('rubber', (-2.05, 0.42, 1.14), 0.40, 0.22, 16)
    sub.cyl('charred', (-2.05, 0.42, 1.14), 0.17, 0.24, 12)


# --------------------------------------------------------------------------- school bus
def build_bus(sub, seed=0):
    """Snub-nose 1950s school bus: rounded roof, window band, stop arm, scorched paint."""
    rnd = random.Random(seed)
    L0, L1 = -4.70, 4.72
    HW = 1.22
    FLOOR, ROOF = 1.02, 2.94
    body = 'paint_bus'

    def hw(x):
        t = max(0.0, (abs(x) - 3.4) / 1.35)
        return HW * (1.0 - 0.30 * t ** 2)

    def top(x):
        if x > 2.55:
            return 1.44 - 0.16 * max(0.0, (x - 3.9) / 0.85) ** 1.5
        return ROOF - 0.10 * max(0.0, (-x - 4.0) / 0.7) ** 2

    def bot(x):
        z = 0.52
        for xw in (3.28, -3.02, -3.92):
            d = abs(x - xw)
            if d < 0.70:
                z = max(z, 0.46 + math.sqrt(max(0.0, 0.70 ** 2 - d ** 2)) * 0.85)
        return z

    N = 70
    xs = [L0 + (L1 - L0) * i / (N - 1) for i in range(N)]
    secs = []
    for x in xs:
        t, b = top(x), bot(x)
        pts = squircle(hw(x), (t - b) / 2.0, (t + b) / 2.0, n=6.5, segs=26)
        secs.append([(x, y, z) for (y, z) in pts])
    sub.loft(body, secs)
    # scorched roof
    rsec = []
    for x in xs:
        t, b = top(x), bot(x)
        pts = squircle(hw(x) + 0.012, (t - b) / 2.0 + 0.012, (t + b) / 2.0, n=6.5,
                       segs=16, t0=math.radians(58), t1=math.radians(122))
        rsec.append([(x, y, z) for (y, z) in pts])
    sub.loft('charred', rsec, closed=False)

    # window band: dark glass set into the side, with frames; some blown out
    zw0, zw1 = 1.72, 2.62
    for i in range(9):
        x = -4.05 + i * 0.86
        if x > 2.35:
            break
        broken = rnd.random() < 0.45
        for s in (-1, 1):
            yy = hw(x) + 0.008
            sub.box('charred' if broken else GLASS, (x, s * yy, (zw0 + zw1) / 2),
                    (0.72, 0.03, zw1 - zw0))
            for (dz, hgt) in ((zw0 - 0.045, 0.09), (zw1 + 0.045, 0.09)):
                sub.box('metal_dark', (x, s * (yy + 0.012), dz), (0.80, 0.05, hgt))
            for dx in (-0.40, 0.40):
                sub.box('metal_dark', (x + dx, s * (yy + 0.012), (zw0 + zw1) / 2),
                        (0.06, 0.05, zw1 - zw0 + 0.10))
            if broken:
                for k in range(3):
                    sub.box(GLASS, (x + rnd.uniform(-0.3, 0.3), s * (yy + 0.02),
                                    rnd.uniform(zw0, zw1 - 0.15)),
                            (rnd.uniform(0.08, 0.2), 0.012, rnd.uniform(0.08, 0.22)),
                            rot=(rnd.uniform(-0.4, 0.4), 0, 0))
    # windscreen + destination board
    sub.box(GLASS, (2.94, 0.0, 2.16), (0.10, 2.10, 0.86), rot=(0, -0.16, 0))
    sub.box('metal_dark', (2.96, 0.0, 2.70), (0.14, 2.16, 0.20))
    sub.box('charred', (2.99, 0.0, 2.70), (0.05, 1.50, 0.10))
    # rub rails
    for s in (-1, 1):
        for z in (1.08, 1.58):
            pts = [(x, s * (hw(x) + 0.02), z) for x in xs[6:-6]]
            bar(sub, 'charred', pts, 0.05, 0.12)
    # SCHOOL BUS stencilled on both flanks and across the tail
    for s in (-1, 1):
        sign_text(sub, 'paint_stencil_k', 'SCHOOL BUS', (-0.55, s * (hw(-0.55) + 0.028), 1.32),
                  (-s, 0, 0), (0, 0, 1), (0, s, 0), h=0.30, width=2.55, depth=0.005, kind='black')
    sign_text(sub, 'paint_stencil_k', 'SCHOOL BUS', (L0 + 0.028, 0.0, 2.32),
              (0, -1, 0), (0, 0, 1), (-1, 0, 0), h=0.20, width=1.70, depth=0.005, kind='black')
    # bonnet, grille, bumpers, lights
    sub.box(body, (4.10, 0.0, 1.32), (1.2, 1.9, 0.30), rot=(0, 0.06, 0))
    sub.box('charred', (4.62, 0.0, 1.04), (0.10, 1.60, 0.46))
    for k in range(7):
        sub.box('chrome', (4.66, -0.60 + k * 0.20, 1.04), (0.06, 0.07, 0.46))
    for (bx, sgn) in ((4.80, 1), (-4.84, -1)):
        pts = [(bx - 0.14 * (u * u), u * 1.22, 0.74) for u in
               (-1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0)]
        bar(sub, 'chrome', pts, 0.18, 0.24)
    for s in (-1, 1):
        headlight(sub, 4.64, s * 0.86, 1.34, 0.17)
        sub.box('paint_red', (-4.76, s * 0.90, 1.30), (0.07, 0.24, 0.20))
        mx, my = 4.36, s * (HW + 0.24)
        sub.cyl('metal_dark', (mx, my, 2.14), 0.03, 1.30, 6)
        sub.box('metal_dark', (mx, my, 2.74), (0.10, 0.24, 0.28))
        for dx in (3.28, -3.02, -3.92):
            wheel(sub, dx, s * (HW - 0.10), 0.52, 0.30, flat=(dx < 0 and s > 0))
            sub.cyl('charred', (dx, s * (HW - 0.16), 0.56), 0.56, 0.24, 16, axis='y')
    # entry door, stop-sign arm, roof hatch, exhaust
    sub.box('metal_dark', (2.44, HW - 0.01, 1.62), (0.86, 0.06, 2.00))
    sub.box(GLASS, (2.44, HW + 0.02, 2.14), (0.72, 0.03, 0.86))
    sub.cyl('metal_dark', (0.72, -(HW + 0.06), 1.80), 0.035, 0.44, 8, axis='y')
    sub.cyl('chrome', (0.72, -(HW + 0.30), 1.80), 0.350, 0.03, 8, axis='y', rot=(0.39, 0, 0))
    sub.cyl('paint_red', (0.72, -(HW + 0.335), 1.80), 0.325, 0.04, 8, axis='y', rot=(0.39, 0, 0))
    sign_text(sub, 'paint_stencil_w', 'STOP', (0.72, -(HW + 0.362), 1.80),
              (1, 0, 0), (0, 0, 1), (0, -1, 0), h=0.16, width=0.46, depth=0.004, kind='black')
    sub.box('metal_dark', (-2.20, 0.0, ROOF + 0.10), (0.76, 0.76, 0.06), rot=(0.75, 0, 0))
    sub.box('metal_dark', (-2.20, 0.0, ROOF + 0.02), (0.80, 0.80, 0.05))
    sub.cyl('metal_rust', (-4.20, -0.86, 0.42), 0.06, 1.6, 8, axis='x')
    # rust blooms low on the panels
    for i in range(14):
        x = rnd.uniform(L0 + 0.4, L1 - 1.4)
        s = rnd.choice((-1, 1))
        sub.box('metal_rust', (x, s * (hw(x) + 0.014), rnd.uniform(0.7, 1.3)),
                (rnd.uniform(0.2, 0.7), 0.012, rnd.uniform(0.1, 0.35)))


# --------------------------------------------------------------------------- placement
def place(scn, builder, x, y, yaw, roll=0.0, pitch=0.0, dz=0.0, bg=False, **kw):
    sub = Sub()
    builder(sub, **kw)
    m = (Matrix.Translation((x, y, dz))
         @ Euler((roll, pitch, yaw), 'XYZ').to_matrix().to_4x4())
    sub.stamp(scn, m, bg=bg)
    return m
