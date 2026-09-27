"""Doom Town — the two 1950s houses.

The plan is authored once in house-local coordinates (lx = 0 at the front wall, growing towards the
back; ly = -6.5..6.5 along the street) and mapped to world space per house: the yellow house mirrors
in X, the green one mirrors in X *and* Y, so the two interiors read differently while sharing code.
"""
import math, random, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_map import bm_prism  # noqa: E402
from mathutils import Matrix, Euler, Vector  # noqa: E402
import layout as L  # noqa: E402

T = L.WALL_T
IT = 0.13                      # interior wall thickness
CH = L.CEIL_H                  # 2.72 ground floor ceiling
UF = L.UP_FLOOR                # 3.02 upstairs finished floor
UD = L.UP_DECK                 # 0.12 deck thickness -> joists 2.90 .. 3.02
C2 = L.UP_CEIL                 # 5.72 second floor top plate (2.70 m clear upstairs)
RIDGE = C2 + 2.32
OVER = 0.45                    # eave overhang
BACK = 11.10
UZ0, UZ1 = L.UP_WIN_Z0, L.UP_WIN_Z1     # upstairs window opening 3.92 .. 5.02

# interior extents
IX0, IX1 = T, BACK - T
IY0, IY1 = -6.5 + T, 6.5 - T
WA = 6.10                      # main spine wall (lx)
WB = 1.60                      # living / kitchen wall (ly)
WC = -1.20                     # bedroom / hall wall (ly)

# upstairs partitions (house-local)
UWA = 6.10                     # landing / front-rooms spine (lx)
UWB = 1.60                     # bedroom A2 / bathroom block (ly)
UWC = -1.20                    # landing / bedroom B (ly)
UWD = -2.60                    # bedroom A1 / A2 (ly)
UWE = 3.30                     # box room / bathroom (lx)
UP_OPS = {                     # openings, kept clear of every partition line
    'UWA': [(-4.20, -2.80), (3.90, 5.30)],
    'UWB': [(1.40, 2.90)],
    'UWC': [(7.40, 9.20)],
    'UWD': [(3.60, 5.10)],
    'UWE': [(2.20, 3.60)],
}
UP_LIGHTS = ((2.6, -4.4), (2.6, -0.5), (1.7, 3.9), (4.7, 3.9), (8.4, 2.2), (8.6, -3.8))
# (8.4, 2.2) hangs over the stairwell. Each of these six gets an MK_LAMP marker per house.
SLX0, SLX1 = L.ST_LX0, L.ST_LX1
SLY0, SLY1 = L.ST_LY0, L.ST_LY1
HX0, HX1, HY0, HY1 = L.ST_HOLE                  # stairwell opening in the deck
N_TREAD = 16
STAIR_RISE = UF / N_TREAD
STAIR_GOING = (SLY1 - SLY0) / N_TREAD


class TF:
    """house-local -> world"""
    def __init__(self, side):
        self.side = side
        if side == 'yellow':
            self.ox, self.sx, self.sy = L.Y_X1, -1.0, 1.0
        else:
            self.ox, self.sx, self.sy = L.G_X0, 1.0, -1.0

    def x(self, lx):
        return self.ox + self.sx * lx

    def y(self, ly):
        return self.sy * ly

    def p(self, lx, ly, z=0.0):
        return (self.x(lx), self.y(ly), z)

    def yaw(self, dx, dy):
        wx, wy = self.sx * dx, self.sy * dy
        return math.atan2(wx, -wy)

    def rng_x(self, a, b):
        a, b = self.x(a), self.x(b)
        return (min(a, b), max(a, b))

    def rng_y(self, a, b):
        a, b = self.y(a), self.y(b)
        return (min(a, b), max(a, b))

    # ---- walls -----------------------------------------------------------
    def wall_y(self, scn, mat, lx, ly0, ly1, z0, z1, t, ops=(), **kw):
        a0, a1 = self.rng_y(ly0, ly1)
        wops = [dict(o, a0=min(self.y(o['a0']), self.y(o['a1'])),
                     a1=max(self.y(o['a0']), self.y(o['a1']))) for o in ops]
        kw['out'] = kw.get('out', 1) * self.sx
        scn.wall(mat, 'y', self.x(lx), a0, a1, z0, z1, t, wops, **kw)

    def wall_x(self, scn, mat, ly, lx0, lx1, z0, z1, t, ops=(), **kw):
        a0, a1 = self.rng_x(lx0, lx1)
        wops = [dict(o, a0=min(self.x(o['a0']), self.x(o['a1'])),
                     a1=max(self.x(o['a0']), self.x(o['a1']))) for o in ops]
        kw['out'] = kw.get('out', 1) * self.sy
        scn.wall(mat, 'x', self.y(ly), a0, a1, z0, z1, t, wops, **kw)

    def box(self, scn, mat, lx, ly, z, sx, sy, sz, yaw=0.0, tilt=(0, 0)):
        return scn.box(mat, self.p(lx, ly, z), (sx, sy, sz),
                       rot=(tilt[0], tilt[1], self.yaw(math.sin(yaw), -math.cos(yaw))))

    def col(self, scn, name, lx0, ly0, z0, lx1, ly1, z1):
        ax0, ax1 = self.rng_x(lx0, lx1)
        ay0, ay1 = self.rng_y(ly0, ly1)
        return scn.col_box(name, (ax0, ay0, z0), (ax1, ay1, z1))


def op(a0, a1, z0, z1, kind='window', oid=None):
    return dict(a0=a0, a1=a1, z0=z0, z1=z1, kind=kind, id=oid)


# --------------------------------------------------------------------------- pieces
def roof_plane(scn, mat, x0, z0, x1, z1, y0, y1, thick=0.13):
    dx, dz = x1 - x0, z1 - z0
    ln = math.hypot(dx, dz)
    pitch = -math.atan2(dz, dx)
    nx, nz = -dz / ln, dx / ln
    cx = (x0 + x1) / 2 - thick / 2 * nx
    cz = (z0 + z1) / 2 - thick / 2 * nz
    scn.box(mat, (cx, (y0 + y1) / 2, cz), (ln, abs(y1 - y0), thick), rot=(0, pitch, 0))


def prism_xz(scn, mat, pts_xz, y_from, y_to):
    m = Matrix.Translation((0, y_from, 0)) @ Euler((math.pi / 2, 0, 0)).to_matrix().to_4x4()
    scn.prism(mat, pts_xz, y_from - y_to, m)


def window_frame(scn, tf, axis, pos_l, a0, a1, z0, z1, trim, broken=True, seed=0, boarded=False, bare=False):
    """Trim + sill + mullions + shards of glass in an opening. axis 'x' (runs along lx) or 'y'."""
    rnd = random.Random(seed)
    tw, td = 0.075, T + 0.06
    if axis == 'y':
        w = pos_l
        for (b0, b1, zz0, zz1) in ((a0 - tw, a1 + tw, z1, z1 + tw), (a0 - tw, a1 + tw, z0 - tw, z0),
                                   (a0 - tw, a0, z0, z1), (a1, a1 + tw, z0, z1)):
            tf.box(scn, trim, w, (b0 + b1) / 2, (zz0 + zz1) / 2, td, abs(b1 - b0), abs(zz1 - zz0))
        tf.box(scn, trim, w - 0.02, (a0 + a1) / 2, z0 - 0.045, T + 0.16, abs(a1 - a0) + 0.20, 0.055)
        if not bare:
            tf.box(scn, trim, w, (a0 + a1) / 2, (z0 + z1) / 2, T * 0.7, 0.05, abs(z1 - z0))
        if bare:
            pass
        elif not broken:
            tf.box(scn, 'glass', w, (a0 + a1) / 2, (z0 + z1) / 2, 0.02, abs(a1 - a0), abs(z1 - z0))
        else:
            for i in range(5):
                bz = rnd.uniform(z0, z1 - 0.2)
                tf.box(scn, 'glass', w, rnd.uniform(a0 + 0.1, a1 - 0.1), bz + 0.1,
                       0.014, rnd.uniform(0.10, 0.30), rnd.uniform(0.10, 0.34))
        if boarded:
            for i in range(3):
                zz = z0 + (i + 0.5) * (z1 - z0) / 3
                tf.box(scn, 'wood_bare', w, (a0 + a1) / 2 + rnd.uniform(-0.08, 0.08), zz,
                       0.045, abs(a1 - a0) + 0.22, 0.17, tilt=(rnd.uniform(-0.06, 0.06), 0))
    else:
        yy = pos_l
        for (b0, b1, zz0, zz1) in ((a0 - tw, a1 + tw, z1, z1 + tw), (a0 - tw, a1 + tw, z0 - tw, z0),
                                   (a0 - tw, a0, z0, z1), (a1, a1 + tw, z0, z1)):
            tf.box(scn, trim, (b0 + b1) / 2, yy, (zz0 + zz1) / 2, abs(b1 - b0), td, abs(zz1 - zz0))
        tf.box(scn, trim, (a0 + a1) / 2, yy - 0.02, z0 - 0.045, abs(a1 - a0) + 0.20, T + 0.16, 0.055)
        if not bare:
            tf.box(scn, trim, (a0 + a1) / 2, yy, (z0 + z1) / 2, 0.05, T * 0.7, abs(z1 - z0))
        if bare:
            pass
        elif not broken:
            tf.box(scn, 'glass', (a0 + a1) / 2, yy, (z0 + z1) / 2, abs(a1 - a0), 0.02, abs(z1 - z0))
        else:
            for i in range(5):
                bz = rnd.uniform(z0, z1 - 0.2)
                tf.box(scn, 'glass', rnd.uniform(a0 + 0.1, a1 - 0.1), yy, bz + 0.1,
                       rnd.uniform(0.10, 0.30), 0.014, rnd.uniform(0.10, 0.34))
        if boarded:
            for i in range(3):
                zz = z0 + (i + 0.5) * (z1 - z0) / 3
                tf.box(scn, 'wood_bare', (a0 + a1) / 2 + rnd.uniform(-0.08, 0.08), yy, zz,
                       abs(a1 - a0) + 0.22, 0.045, 0.17, tilt=(0, rnd.uniform(-0.06, 0.06)))


# --------------------------------------------------------------------------- furniture
def _upholstered(scn, x, y, yaw, w, mat, seats, seed=0, sag=0.0):
    """Shared body for the sofa / armchair: sprung base, separate seat and back cushions,
    rolled arms and turned legs (environment.md #21 -- these used to be plain blocks)."""
    rnd = random.Random(seed)
    c, s = math.cos(yaw), math.sin(yaw)

    def b(dx, dy, dz, sx, sy, sz, m=mat, tilt=(0, 0)):
        scn.box(m, (x + dx * c - dy * s, y + dx * s + dy * c, dz), (sx, sy, sz),
                rot=(tilt[0], tilt[1], yaw))

    def cy(dx, dy, dz, r, ln, axis='y', m=mat, r2=None, tilt=(0, 0)):
        scn.cyl(m, (x + dx * c - dy * s, y + dx * s + dy * c, dz), r, ln, 10, axis=axis,
                rot=(tilt[0], tilt[1], yaw), r2=r2)

    aw = 0.19                                     # arm width
    sw = (w - 2 * aw) / seats                     # seat width
    b(0, 0.02, 0.30, w - 2 * aw + 0.02, 0.82, 0.16)          # sprung base
    b(0, -0.38, 0.26, w, 0.08, 0.30)                         # front skirt
    for i in range(seats):
        dx = -(w - 2 * aw) / 2 + sw * (i + 0.5)
        b(dx, -0.03, 0.455, sw - 0.035, 0.70, 0.19,
          tilt=(rnd.uniform(-0.03, 0.03) - sag, rnd.uniform(-0.02, 0.02)))
        cy(dx, -0.375, 0.455, 0.085, sw - 0.06)              # rolled cushion front
    b(0, 0.36, 0.64, w, 0.16, 0.76)                          # back frame
    for i in range(seats):
        dx = -(w - 2 * aw) / 2 + sw * (i + 0.5)
        b(dx, 0.245, 0.70, sw - 0.04, 0.17, 0.52, tilt=(-0.12, 0))
    for k in (-1, 1):                                        # arms + roll
        b(k * (w / 2 - aw / 2), 0.0, 0.50, aw, 0.84, 0.44)
        cy(k * (w / 2 - aw / 2), 0.0, 0.72, aw / 2, 0.84)
        cy(k * (w / 2 - aw / 2), -0.42, 0.72, aw / 2, aw, axis='x')
    for k in (-1, 1):                                        # turned legs
        for j in (-1, 1):
            scn.cyl('wood_bare', (x + (k * (w / 2 - 0.10)) * c - (j * 0.33) * s,
                                  y + (k * (w / 2 - 0.10)) * s + (j * 0.33) * c, 0.11),
                    0.038, 0.22, 8, r2=0.022)
    scn.col_obj('COL_PROP', (x, y, 0.4), (w + 0.05, 0.95, 0.8), (0, 0, yaw))


def sofa(scn, x, y, yaw, mat='fabric_weave_r', seed=0):
    _upholstered(scn, x, y, yaw, 2.05, mat, 2, seed=seed, sag=0.03)


def armchair(scn, x, y, yaw, mat='fabric_weave_r'):
    _upholstered(scn, x, y, yaw, 0.94, mat, 1, seed=5)


def table(scn, x, y, yaw, w=1.5, d=0.9, h=0.75, top='wood_bare'):
    c, s = math.cos(yaw), math.sin(yaw)
    scn.box(top, (x, y, h - 0.03), (w, d, 0.06), rot=(0, 0, yaw))
    scn.box(top, (x, y, h - 0.10), (w - 0.18, d - 0.18, 0.09), rot=(0, 0, yaw))
    for k in (-1, 1):
        for j in (-1, 1):
            dx, dy = k * (w / 2 - 0.09), j * (d / 2 - 0.09)
            scn.box(top, (x + dx * c - dy * s, y + dx * s + dy * c, (h - 0.14) / 2),
                    (0.07, 0.07, h - 0.14), rot=(0, 0, yaw))
    scn.col_obj('COL_PROP', (x, y, h / 2), (w, d, h), (0, 0, yaw))


def chair(scn, x, y, yaw, mat='wood_bare'):
    c, s = math.cos(yaw), math.sin(yaw)
    scn.box(mat, (x, y, 0.45), (0.44, 0.44, 0.05), rot=(0, 0, yaw))
    scn.box(mat, (x - 0.20 * s, y + 0.20 * c, 0.72), (0.44, 0.05, 0.50), rot=(0, 0, yaw))
    for k in (-1, 1):
        for j in (-1, 1):
            dx, dy = k * 0.18, j * 0.18
            scn.box(mat, (x + dx * c - dy * s, y + dx * s + dy * c, 0.21), (0.045, 0.045, 0.43),
                    rot=(0, 0, yaw))


def tv_console(scn, x, y, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    scn.box('wood_bare', (x, y, 0.36), (1.05, 0.52, 0.66), rot=(0, 0, yaw))
    scn.box('wood_bare', (x, y, 0.72), (1.12, 0.58, 0.07), rot=(0, 0, yaw))
    scn.box('glass_dark', (x - 0.28 * s, y + 0.28 * c, 0.45), (0.62, 0.05, 0.46), rot=(0, 0, yaw))
    scn.box('chrome', (x - 0.28 * s, y + 0.28 * c, 0.45), (0.68, 0.03, 0.52), rot=(0, 0, yaw))
    for k in (-1, 1):
        scn.cyl('chrome', (x + (0.42 * k) * c - 0.30 * s, y + (0.42 * k) * s + 0.30 * c, 0.20),
                0.035, 0.07, 8, axis='y', rot=(0, 0, yaw))
    for k in (-1, 1):
        for j in (-1, 1):
            dx, dy = k * 0.44, j * 0.20
            scn.box('wood_bare', (x + dx * c - dy * s, y + dx * s + dy * c, 0.05),
                    (0.07, 0.07, 0.10), rot=(0, 0, yaw))
    scn.col_obj('COL_PROP', (x, y, 0.4), (1.15, 0.62, 0.8), (0, 0, yaw))


def dresser(scn, x, y, yaw, w=1.2, h=0.92, d=0.52):
    c, s = math.cos(yaw), math.sin(yaw)
    scn.box('wood_bare', (x, y, h / 2), (w, d, h), rot=(0, 0, yaw))
    for i in range(3):
        zz = 0.18 + i * 0.28
        scn.box('wood_bare', (x - (d / 2 + 0.012) * s, y + (d / 2 + 0.012) * c, zz),
                (w - 0.12, 0.03, 0.22), rot=(0, 0, yaw))
        scn.cyl('chrome', (x - (d / 2 + 0.05) * s, y + (d / 2 + 0.05) * c, zz), 0.022, 0.16, 6,
                axis='x', rot=(0, 0, yaw))
    scn.col_obj('COL_PROP', (x, y, h / 2), (w, d + 0.1, h), (0, 0, yaw))


def bed(scn, x, y, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    def b(dx, dy, dz, sx, sy, sz, m):
        scn.box(m, (x + dx * c - dy * s, y + dx * s + dy * c, dz), (sx, sy, sz), rot=(0, 0, yaw))
    b(0, 0, 0.26, 1.45, 2.00, 0.18, 'wood_bare')
    b(0, 0, 0.42, 1.38, 1.94, 0.18, 'fabric_weave_o')
    b(0, 1.02, 0.55, 1.45, 0.08, 0.90, 'wood_bare')
    b(0, -1.02, 0.36, 1.45, 0.08, 0.40, 'wood_bare')
    b(0, 0.70, 0.56, 1.10, 0.42, 0.14, 'cloth_white')
    scn.col_obj('COL_PROP', (x, y, 0.3), (1.5, 2.1, 0.6), (0, 0, yaw))


def counter_run(scn, x0, y0, x1, y1, h=0.90, d=0.62, sink=False):
    """Kitchen counter between two points (axis-aligned)."""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    sx, sy = abs(x1 - x0), abs(y1 - y0)
    if sx < sy:
        sx = d
    else:
        sy = d
    scn.box('wood_trim_y', (cx, cy, (h - 0.1) / 2 + 0.1), (sx - 0.04, sy - 0.04, h - 0.1))
    scn.box('lino', (cx, cy, h + 0.02), (sx, sy, 0.05))
    scn.box('plaster', (cx, cy, 0.05), (sx - 0.14, sy - 0.14, 0.10))
    if sink:
        scn.box('chrome', (cx, cy, h + 0.02), (min(sx, 0.7), min(sy, 0.5), 0.07))
        scn.cyl('chrome', (cx, cy + 0.18 if sy > sx else cy, h + 0.18), 0.02, 0.28, 6)
    scn.col_obj('COL_PROP', (cx, cy, h / 2), (sx, sy, h))


def fridge(scn, x, y, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    scn.box('paint_cream', (x, y, 0.82), (0.72, 0.66, 1.64), rot=(0, 0, yaw))
    scn.box('paint_cream', (x - 0.345 * s, y + 0.345 * c, 0.86), (0.66, 0.03, 1.50), rot=(0, 0, yaw))
    scn.cyl('chrome', (x - 0.38 * s - 0.26 * c, y + 0.38 * c - 0.26 * s, 1.05), 0.022, 0.5, 6)
    scn.col_obj('COL_PROP', (x, y, 0.82), (0.8, 0.75, 1.64), (0, 0, yaw))


def stove(scn, x, y, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    scn.box('paint_cream', (x, y, 0.45), (0.76, 0.64, 0.90), rot=(0, 0, yaw))
    scn.box('metal_dark', (x, y, 0.92), (0.78, 0.66, 0.05), rot=(0, 0, yaw))
    for k in (-1, 1):
        for j in (-1, 1):
            dx, dy = k * 0.19, j * 0.15
            scn.cyl('metal_dark', (x + dx * c - dy * s, y + dx * s + dy * c, 0.95), 0.10, 0.03, 10)
    scn.box('glass_dark', (x - 0.33 * s, y + 0.33 * c, 0.45), (0.52, 0.03, 0.36), rot=(0, 0, yaw))
    scn.col_obj('COL_PROP', (x, y, 0.45), (0.82, 0.7, 0.9), (0, 0, yaw))


def floor_lamp(scn, x, y):
    scn.cyl('metal_dark', (x, y, 0.02), 0.16, 0.04, 10)
    scn.cyl('metal_dark', (x, y, 0.80), 0.022, 1.56, 8)
    scn.cyl('paint_cream', (x, y, 1.66), 0.20, 0.30, 12, r2=0.15)
    scn.box('lamp_glow', (x, y, 1.60), (0.12, 0.12, 0.12))


def picture(scn, mat, x, y, z, w, h, yaw):
    scn.box('wood_bare', (x, y, z), (w, 0.05, h), rot=(0, 0, yaw))
    scn.box(mat, (x, y, z), (w - 0.09, 0.07, h - 0.09), rot=(0, 0, yaw))


def stair_z(ly):
    """Walking height of the staircase at a house-local ly (clamped to the flight)."""
    t = max(0.0, min(1.0, (ly - SLY0) / (SLY1 - SLY0)))
    return t * UF


def staircase(scn, tf, trim, side):
    """Visual flight (treads, risers, stringers, newels, banister) + a smooth ramp collider.

    The flight climbs towards +ly from ly = SLY0 (z 0) to ly = SLY1 (z UF = 3.02): 5.30 m of
    run for 3.02 m of rise, i.e. 29.7 deg — inside the contract's 32 deg limit for collision.
    """
    rnd = random.Random(7 if side == 'yellow' else 8)
    cx = (SLX0 + SLX1) / 2
    w = SLX1 - SLX0

    # ---- treads and risers (the last "tread" is the upstairs floor itself)
    for i in range(N_TREAD):
        z = (i + 1) * STAIR_RISE
        ly = SLY0 + i * STAIR_GOING
        if i < N_TREAD - 1:
            tf.box(scn, 'woodfloor', cx, ly + STAIR_GOING / 2 + 0.012, z - 0.023,
                   w, STAIR_GOING + 0.055, 0.046)                   # tread + nosing
        tf.box(scn, 'wood_white', cx, ly - 0.007, z - STAIR_RISE / 2 - 0.023,
               w - 0.02, 0.028, STAIR_RISE - 0.046)                 # riser
    # carpet runner up the middle, a few mm proud of the treads
    for i in range(N_TREAD - 1):
        z = (i + 1) * STAIR_RISE
        ly = SLY0 + i * STAIR_GOING
        tf.box(scn, 'fabric_weave_r', cx, ly + STAIR_GOING / 2 + 0.012, z + 0.006,
               w - 0.42, STAIR_GOING + 0.02, 0.014)
        tf.box(scn, 'chrome', cx, ly + 0.018, z - STAIR_RISE + 0.055, w - 0.44, 0.028, 0.016)

    # ---- closed stringers on both sides, following the pitch
    pitch = math.atan2(UF, SLY1 - SLY0)
    ln = math.hypot(UF, SLY1 - SLY0)
    for k, lx in ((-1, SLX0 - 0.03), (1, SLX1 + 0.03)):
        tf.box(scn, trim, lx, (SLY0 + SLY1) / 2, UF / 2 - 0.16, 0.06, ln, 0.34,
               tilt=(pitch, 0))
    # soffit closing the underside (keeps the understair dark, no open joists)
    tf.box(scn, 'plaster', cx, (SLY0 + SLY1) / 2, UF / 2 - 0.30, w - 0.03, ln, 0.05,
           tilt=(pitch, 0))

    # ---- newel posts + banister on the open (−lx) side, and a wall rail on the other
    for (ly, z) in ((SLY0 - 0.06, 0.0), (SLY1 + 0.06, UF)):
        tf.box(scn, trim, SLX0 - 0.06, ly, z + 0.50, 0.12, 0.12, 1.00)
        tf.box(scn, trim, SLX0 - 0.06, ly, z + 1.04, 0.16, 0.16, 0.10)
    tf.box(scn, trim, SLX0 - 0.06, (SLY0 + SLY1) / 2, UF / 2 + 0.92, 0.07, ln, 0.06,
           tilt=(pitch, 0))
    n_bal = 15
    for i in range(n_bal):
        t = (i + 0.5) / n_bal
        ly = SLY0 + (SLY1 - SLY0) * t
        z = t * UF
        tf.box(scn, 'wood_white', SLX0 - 0.06, ly, z + 0.48, 0.045, 0.045, 0.86)
    for i in range(6):                       # a few balusters knocked out
        t = rnd.uniform(0.1, 0.9)
        tf.box(scn, 'wood_white', SLX0 - 0.06, SLY0 + (SLY1 - SLY0) * t,
               t * UF + rnd.uniform(0.10, 0.55), 0.045, 0.045, rnd.uniform(0.15, 0.4),
               tilt=(rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5)))
    # wall-side handrail on brackets
    tf.box(scn, trim, SLX1 + 0.07, (SLY0 + SLY1) / 2, UF / 2 + 0.92, 0.055, ln, 0.05,
           tilt=(pitch, 0))

    # ---- collision: one smooth ramp, plus the flat pad at the foot
    scn.col_ramp('COL_STAIR_' + side, tf.p(cx, SLY0, 0.0), tf.p(cx, SLY1, UF), w + 0.06, 0.45)


def stair_debris_door(scn, tf, door_id):
    """The buyable blockage at the foot of the stairs: smashed furniture, planks and plaster."""
    rnd = random.Random(sum(ord(c) for c in door_id))
    g = scn.group('DOOR_' + door_id, tf.p((SLX0 + SLX1) / 2, 0.5, 0.0))
    ly0, ly1 = -0.25, 1.30
    cx = (SLX0 + SLX1) / 2

    def b(mat, lx, ly, z, sx, sy, sz, tilt=(0, 0)):
        g.box(mat, tf.p(lx, ly, z), (sx, sy, sz),
              rot=(tilt[0] * tf.sy, tilt[1] * tf.sx, 0.0))

    # a wardrobe tipped across the flight, back panel to the room
    b('wood_bare', cx + 0.10, ly0 + 0.62, 0.80, 1.18, 0.56, 1.75, tilt=(0.30, 0.06))
    b('wood_bare', cx + 0.10, ly0 + 0.50, 0.82, 1.02, 0.05, 1.55, tilt=(0.30, 0.06))
    # a dresser on its side and a bed frame wedged above it
    b('charred', cx - 0.44, ly0 + 0.28, 0.30, 0.52, 0.92, 0.60, tilt=(-0.18, 0.0))
    b('wood_bare', cx - 0.10, ly0 + 1.05, 1.42, 1.32, 0.09, 0.90, tilt=(0.46, 0.0))
    for i in range(4):
        b('wood_bare', cx - 0.10, ly0 + 1.05 - 0.02 * i, 1.10 + i * 0.22, 1.26, 0.05, 0.05,
          tilt=(0.46, 0.0))
    # planks nailed across, criss-crossed
    for i in range(6):
        z = 0.22 + i * 0.36
        b(rnd.choice(['wood_bare', 'wood_white', 'charred', 'wood_bare']),
          cx + rnd.uniform(-0.12, 0.12), ly0 + rnd.uniform(0.0, 0.25), z,
          1.86, 0.045, 0.19, tilt=(rnd.uniform(-0.10, 0.10), rnd.uniform(-0.05, 0.05)))
        for k in (-1, 1):
            g.box('metal_dark', tf.p(cx + k * 0.82, ly0 + 0.02, z), (0.05, 0.03, 0.03))
    b('wood_white', cx - 0.30, ly0 + 0.16, 1.15, 0.20, 0.05, 2.60, tilt=(0.0, 0.42))
    b('wood_bare', cx + 0.34, ly0 + 0.16, 1.15, 0.20, 0.05, 2.60, tilt=(0.0, -0.42))
    # rubble, plaster chunks and a rolled rug packed into the gaps
    for i in range(26):
        lx = cx + rnd.uniform(-0.80, 0.80)
        ly = rnd.uniform(ly0, ly1 - 0.2)
        z = rnd.uniform(0.05, 1.05) + max(0.0, stair_z(ly) - 0.1)
        s = rnd.uniform(0.10, 0.30)
        g.rock(rnd.choice(['plaster', 'rubble', 'brick', 'charred']), tf.p(lx, ly, z),
               (s * 2.1, s * 2.1, s), seed=311 + i)
    g.cyl('fabric_weave_o', tf.p(cx + 0.45, ly0 + 0.35, 0.22), 0.17, 1.30, 10,
          axis='x', rot=(0, 0, tf.yaw(1, 0.25)))
    for i in range(14):                       # plaster dust and lath shaken out of the ceiling
        g.box('plaster', tf.p(cx + rnd.uniform(-0.85, 0.85), ly0 + rnd.uniform(-0.1, 1.2),
                              rnd.uniform(0.04, 1.9)),
              (rnd.uniform(0.18, 0.5), rnd.uniform(0.14, 0.4), 0.035),
              rot=(rnd.uniform(-0.8, 0.8), rnd.uniform(-0.8, 0.8), rnd.uniform(0, 3.1)))
    g.build()
    tf.col(scn, 'COL_DOOR_' + door_id, SLX0 - 0.18, ly0, 0.0, SLX1 + 0.18, ly1, 2.60)


class ZOff:
    """Proxy round a Scene that lifts every primitive by `dz`.

    The ground-floor furniture builders all hard-code their heights above z = 0; wrapping the
    scene lets the same sofa / bed / dresser code furnish the upstairs without duplicating it.
    """

    def __init__(self, scn, dz):
        self.scn, self.dz = scn, dz

    def _p(self, c):
        return (c[0], c[1], c[2] + self.dz)

    def box(self, mat, center, size, rot=(0, 0, 0), bg=False):
        return self.scn.box(mat, self._p(center), size, rot, bg)

    def box_mm(self, mat, mn, mx, bg=False):
        return self.scn.box_mm(mat, self._p(mn), self._p(mx), bg)

    def cyl(self, mat, center, radius, height, segs=12, axis='z', rot=(0, 0, 0), r2=None, bg=False):
        return self.scn.cyl(mat, self._p(center), radius, height, segs, axis, rot, r2, bg)

    def rock(self, mat, center, size, seed=0, subd=1, bg=False):
        return self.scn.rock(mat, self._p(center), size, seed, subd, bg)

    def col_obj(self, name, center, size, rot=(0, 0, 0), collection=None):
        return self.scn.col_obj(name, self._p(center), size, rot, collection)

    def col_box(self, name, mn, mx, rot=None, collection=None):
        return self.scn.col_box(name, self._p(mn), self._p(mx), rot, collection)

    def decal(self, name, center, size, face=(0, 0, 1), rot=0.0, lift=0.008, bg=False):
        return self.scn.decal(name, self._p(center), size, face, rot, lift, bg)


# --------------------------------------------------------------------------- upstairs fittings
def wardrobe(scn, x, y, yaw, w=1.15, d=0.58, h=2.05, open_=False, mat='wood_bare'):
    c, s = math.cos(yaw), math.sin(yaw)

    def b(dx, dy, dz, sx, sy, sz, m=mat, rot=(0, 0)):
        scn.box(m, (x + dx * c - dy * s, y + dx * s + dy * c, dz), (sx, sy, sz),
                rot=(rot[0], rot[1], yaw))
    b(0, 0.02, h / 2, w, d - 0.04, h)
    b(0, 0, h + 0.05, w + 0.10, d + 0.06, 0.10)                 # cornice
    b(0, 0, 0.06, w + 0.04, d + 0.02, 0.12)                     # plinth
    if open_:
        b(w / 4, -d / 2 - 0.02, h / 2 - 0.06, w / 2 - 0.05, 0.04, h - 0.30)     # shut leaf
        b(-w / 4, 0.02, h / 2 - 0.06, w / 2 - 0.08, 0.04, h - 0.34)            # open leaf, inside
        for i in range(3):                                                      # shelves
            b(-w / 4, 0.02, 0.45 + i * 0.52, w / 2 - 0.06, d - 0.10, 0.03)
        scn.cyl('metal_rust', (x + (d / 2 - 0.10) * s, y - (d / 2 - 0.10) * c, h - 0.34),
                0.012, w - 0.22, 6, axis='x', rot=(0, 0, yaw))
    else:
        for k in (-1, 1):
            b(k * (w / 4), -d / 2 - 0.01, h / 2 - 0.06, w / 2 - 0.03, 0.03, h - 0.30)
            scn.cyl('chrome', (x + (k * 0.07) * c + (d / 2 + 0.05) * s,
                               y + (k * 0.07) * s - (d / 2 + 0.05) * c, h / 2), 0.016, 0.11, 6,
                    axis='x', rot=(0, 0, yaw))
    scn.col_obj('COL_PROP', (x, y, h / 2), (w + 0.12, d + 0.12, h), (0, 0, yaw))


def bathtub(scn, x, y, yaw):
    c, s = math.cos(yaw), math.sin(yaw)

    def b(dx, dy, dz, sx, sy, sz, m):
        scn.box(m, (x + dx * c - dy * s, y + dx * s + dy * c, dz), (sx, sy, sz), rot=(0, 0, yaw))
    b(0, 0, 0.30, 1.62, 0.74, 0.60, 'paint_cream')                # shell
    b(0, 0, 0.585, 1.46, 0.60, 0.13, 'glass_dark')                # dark water / grime inside
    b(0, 0, 0.62, 1.70, 0.80, 0.055, 'paint_cream')               # rim
    for k in (-1, 1):                                             # cast-iron claw feet
        for j in (-1, 1):
            scn.cyl('chrome', (x + (k * 0.66) * c - (j * 0.27) * s,
                               y + (k * 0.66) * s + (j * 0.27) * c, 0.05), 0.055, 0.10, 8, r2=0.075)
    scn.cyl('chrome', (x - 0.74 * c + 0.0 * s, y - 0.74 * s, 0.80), 0.022, 0.30, 8)
    scn.cyl('chrome', (x - 0.68 * c, y - 0.68 * s, 0.94), 0.018, 0.16, 8, axis='x', rot=(0, 0, yaw))
    scn.col_obj('COL_PROP', (x, y, 0.33), (1.75, 0.85, 0.66), (0, 0, yaw))


def toilet(scn, x, y, yaw):
    c, s = math.cos(yaw), math.sin(yaw)

    def b(dx, dy, dz, sx, sy, sz, m='paint_cream'):
        scn.box(m, (x + dx * c - dy * s, y + dx * s + dy * c, dz), (sx, sy, sz), rot=(0, 0, yaw))
    scn.cyl('paint_cream', (x, y, 0.18), 0.17, 0.36, 12, r2=0.13)         # pedestal
    scn.cyl('paint_cream', (x - 0.03 * s, y + 0.03 * c, 0.39), 0.21, 0.12, 14, r2=0.23)
    b(0, 0.03, 0.455, 0.40, 0.46, 0.04, 'cloth_white')                    # seat
    b(0, 0.34, 0.60, 0.46, 0.22, 0.46)                                    # cistern
    b(0, 0.34, 0.85, 0.50, 0.26, 0.05, 'wood_bare')
    scn.cyl('chrome', (x - 0.20 * s + 0.20 * c, y + 0.20 * c + 0.20 * s, 0.80), 0.014, 0.10, 6,
            axis='x', rot=(0, 0, yaw))
    scn.col_obj('COL_PROP', (x, y, 0.42), (0.5, 0.75, 0.85), (0, 0, yaw))


def basin(scn, x, y, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    scn.cyl('paint_cream', (x, y, 0.38), 0.12, 0.76, 10, r2=0.17)
    scn.box('paint_cream', (x, y, 0.80), (0.58, 0.44, 0.13), rot=(0, 0, yaw))
    scn.box('glass_dark', (x, y, 0.855), (0.42, 0.30, 0.035), rot=(0, 0, yaw))
    scn.cyl('chrome', (x + 0.16 * s, y - 0.16 * c, 0.92), 0.016, 0.14, 6)
    scn.col_obj('COL_PROP', (x, y, 0.45), (0.62, 0.5, 0.9), (0, 0, yaw))


def mirror_cabinet(scn, x, y, z, yaw, w=0.62, h=0.72, broken=True):
    c, s = math.cos(yaw), math.sin(yaw)
    scn.box('paint_cream', (x, y, z), (w, 0.16, h), rot=(0, 0, yaw))
    if broken:
        rnd = random.Random(int(abs(x * 13 + y * 7)))
        for i in range(5):
            scn.box('glass', (x - (0.085) * s + (w * 0.3 * (i - 2) / 2.0) * c,
                              y + (0.085) * c + (w * 0.3 * (i - 2) / 2.0) * s,
                              z + rnd.uniform(-0.18, 0.18)),
                    (w * 0.26, 0.012, rnd.uniform(0.15, 0.34)), rot=(0, 0, yaw))
    else:
        scn.box('glass', (x - 0.085 * s, y + 0.085 * c, z), (w - 0.08, 0.012, h - 0.08),
                rot=(0, 0, yaw))


def bookcase(scn, x, y, yaw, w=0.90, h=1.60, d=0.30, seed=0, toppled=False):
    rnd = random.Random(seed)
    if toppled:
        scn.box('wood_bare', (x, y, 0.16), (w, h, d), rot=(0, 0.06, yaw))
        for i in range(10):
            scn.box(rnd.choice(['wallpaper_a', 'charred', 'wood_bare']),
                    (x + rnd.uniform(-0.7, 0.7), y + rnd.uniform(-0.7, 0.7), 0.04),
                    (0.16, 0.22, 0.045), rot=(0, rnd.uniform(-0.2, 0.2), rnd.uniform(0, 3.1)))
        scn.col_obj('COL_PROP', (x, y, 0.16), (w + 0.1, h + 0.1, 0.34), (0, 0, yaw))
        return
    shelf_unit(scn, x, y, yaw, w, h, d, seed)


def cot(scn, x, y, yaw):
    c, s = math.cos(yaw), math.sin(yaw)

    def b(dx, dy, dz, sx, sy, sz, m='wood_white'):
        scn.box(m, (x + dx * c - dy * s, y + dx * s + dy * c, dz), (sx, sy, sz), rot=(0, 0, yaw))
    b(0, 0, 0.42, 0.72, 1.28, 0.08)
    b(0, 0, 0.50, 0.66, 1.22, 0.10, 'cloth_white')
    for j in (-1, 1):
        b(0, j * 0.64, 0.68, 0.72, 0.05, 0.60)
    for k in (-1, 1):
        for i in range(7):
            b(k * 0.36, -0.56 + i * 0.187, 0.70, 0.04, 0.04, 0.56)
    for k in (-1, 1):
        for j in (-1, 1):
            b(k * 0.34, j * 0.60, 0.21, 0.06, 0.06, 0.42)
    scn.col_obj('COL_PROP', (x, y, 0.5), (0.8, 1.36, 1.0), (0, 0, yaw))


def shelf_unit(scn, x, y, yaw, w=0.95, h=1.85, d=0.32, seed=0):
    rnd = random.Random(seed)
    c, s = math.cos(yaw), math.sin(yaw)

    def b(dx, dy, dz, sx, sy, sz, m):
        scn.box(m, (x + dx * c - dy * s, y + dx * s + dy * c, dz), (sx, sy, sz), rot=(0, 0, yaw))
    for k in (-1, 1):
        b(k * (w / 2), 0, h / 2, 0.05, d, h, 'wood_bare')
    # the back panel sits *inside* the side panels: at d/2 - 0.02 its outer face was exactly
    # coplanar with theirs and the two z-fought along a 5 cm strip at each end.
    b(0, d / 2 - 0.05, h / 2, w, 0.04, h, 'wood_bare')
    for i in range(4):
        zz = 0.28 + i * (h - 0.4) / 3.0
        b(0, 0, zz, w - 0.06, d, 0.035, 'wood_bare')
        for j in range(rnd.randint(1, 5)):
            ox = rnd.uniform(-w / 2 + 0.1, w / 2 - 0.1)
            r = rnd.uniform(0.035, 0.055)
            scn.cyl(rnd.choice(['metal_rust', 'paint_red', 'paint_cream']),
                    (x + ox * c - rnd.uniform(-0.06, 0.06) * s,
                     y + ox * s + rnd.uniform(-0.06, 0.06) * c, zz + 0.08), r, 0.13, 8)
    scn.col_obj('COL_PROP', (x, y, h / 2), (w + 0.1, d + 0.1, h), (0, 0, yaw))


def curtain(scn, tf, axis, pos_l, a0, a1, z0, z1, mat='fabric_red', seed=0):
    """Torn drapes hanging beside a window opening."""
    rnd = random.Random(seed)
    for k, side in ((0, a0 - 0.02), (1, a1 + 0.02)):
        wdt = rnd.uniform(0.22, 0.34)
        hh = (z1 - z0) * rnd.uniform(0.75, 1.05)
        off = wdt / 2 * (1 if k else -1)
        if axis == 'y':
            tf.box(scn, mat, pos_l - 0.14, side + off, z1 - hh / 2 + 0.08, 0.05, wdt, hh)
            tf.box(scn, 'wood_bare', pos_l - 0.16, (a0 + a1) / 2, z1 + 0.12, 0.05, (a1 - a0) + 0.5, 0.05)
        else:
            tf.box(scn, mat, (side + off), pos_l - 0.14, z1 - hh / 2 + 0.08, wdt, 0.05, hh)
            tf.box(scn, 'wood_bare', (a0 + a1) / 2, pos_l - 0.16, z1 + 0.12, (a1 - a0) + 0.5, 0.05, 0.05)


def paper_scatter(scn, x, y, r, n, seed, mat='plaster'):
    rnd = random.Random(seed)
    for i in range(n):
        a = rnd.uniform(0, 6.283)
        d = r * math.sqrt(rnd.random())
        scn.box(mat, (x + d * math.cos(a), y + d * math.sin(a), 0.005),
                (rnd.uniform(0.11, 0.20), rnd.uniform(0.14, 0.23), 0.003),
                rot=(0, rnd.uniform(-0.05, 0.05), rnd.uniform(0, 3.14)))


def debris_pile(scn, x, y, r, n, seed, mats=('plaster', 'wood_bare', 'brick', 'rubble')):
    rnd = random.Random(seed)
    for i in range(n):
        a = rnd.uniform(0, 6.3)
        d = r * math.sqrt(rnd.random())
        m = rnd.choice(mats)
        if m == 'wood_bare':
            scn.box(m, (x + d * math.cos(a), y + d * math.sin(a), rnd.uniform(0.03, 0.22)),
                    (rnd.uniform(0.5, 1.5), rnd.uniform(0.08, 0.2), 0.05),
                    rot=(rnd.uniform(-0.5, 0.5), rnd.uniform(-0.3, 0.3), rnd.uniform(0, 3.14)))
        else:
            s = rnd.uniform(0.10, 0.34)
            scn.rock(m, (x + d * math.cos(a), y + d * math.sin(a), s * 0.14), (s * 2, s * 2, s), seed=seed * 7 + i)


# --------------------------------------------------------------------------- upstairs
def _deck_rects(x0, x1, y0, y1):
    """The four rectangles of a slab with the stairwell hole punched out of it."""
    return [(x0, HX0, y0, y1), (HX1, x1, y0, y1),
            (HX0, HX1, y0, HY0), (HX0, HX1, HY1, y1)]


def floor_deck(scn, tf, side, trim):
    """Ground-floor ceiling + upstairs floor deck, both pierced by the stairwell opening."""
    for (a0, a1, b0, b1) in _deck_rects(T, BACK - T, -6.5 + T, 6.5 - T):
        if a1 - a0 < 1e-3 or b1 - b0 < 1e-3:
            continue
        tf.box(scn, 'plaster', (a0 + a1) / 2, (b0 + b1) / 2, CH + 0.09,
               a1 - a0 + 0.05, b1 - b0 + 0.05, 0.18)                     # 2.72 .. 2.90
    for (a0, a1, b0, b1) in _deck_rects(0.0, BACK, -6.5, 6.5):
        if a1 - a0 < 1e-3 or b1 - b0 < 1e-3:
            continue
        # 2.885 .. 3.016: overlaps the ceiling below it and stops 4 mm under the COL floor,
        # so neither the ceiling nor the furniture standing at UF shares a plane with it
        tf.box(scn, 'woodfloor', (a0 + a1) / 2, (b0 + b1) / 2, UF - 0.0695,
               a1 - a0, b1 - b0, 0.131)
        scn.col_box('COL_FLOOR_' + side + 'up',
                    (min(tf.x(a0), tf.x(a1)), min(tf.y(b0), tf.y(b1)), UF - UD),
                    (max(tf.x(a0), tf.x(a1)), max(tf.y(b0), tf.y(b1)), UF))
    # Trimmer beams round the stairwell. Their inner faces sit 1 cm *inside* the opening and
    # their tops 1.5 cm *inside* the deck, so no face is coplanar with the cut edges (which is
    # what makes trim like this z-fight).
    for (a0, a1, b0, b1) in ((HX0 - 0.10, HX0 + 0.01, HY0 - 0.10, HY1 + 0.10),
                             (HX1 - 0.01, HX1 + 0.10, HY0 - 0.10, HY1 + 0.10),
                             (HX0 + 0.01, HX1 - 0.01, HY0 - 0.10, HY0 + 0.01),
                             (HX0 + 0.01, HX1 - 0.01, HY1 - 0.01, HY1 + 0.10)):
        tf.box(scn, trim, (a0 + a1) / 2, (b0 + b1) / 2, 2.7625, a1 - a0, b1 - b0, 0.285)
    # Landing balustrade: the raking banister of the flight guards most of the west edge, so
    # the landing needs the east edge, the head of the well and a short return at the west.
    def rail(lx, ly, sx, sy):
        tf.box(scn, trim, lx, ly, UF + 0.99, sx, sy, 0.06)
        tf.box(scn, trim, lx, ly, UF + 0.38, sx * 0.7, sy * 0.7, 0.05)
        n = max(2, int(max(sx, sy) / 0.17))
        for i in range(n):
            t = (i + 0.5) / n - 0.5
            tf.box(scn, 'wood_white', lx + (sx - 0.05) * t * (sx > sy),
                   ly + (sy - 0.05) * t * (sy > sx), UF + 0.50, 0.045, 0.045, 0.90)
    rail(HX1 + 0.06, (HY0 + HY1) / 2, 0.07, HY1 - HY0 + 0.12)
    rail((HX0 + HX1) / 2, HY0 - 0.06, HX1 - HX0 + 0.12, 0.07)
    rail(HX0 - 0.06, (HY0 + HY1) / 2 + 1.2, 0.07, HY1 - HY0 - 2.4)
    for (lx, ly) in ((HX1 + 0.06, HY0 - 0.06), (HX1 + 0.06, HY1 + 0.02), (HX0 - 0.06, HY0 - 0.06)):
        tf.box(scn, trim, lx, ly, UF + 0.53, 0.11, 0.11, 1.06)
        tf.box(scn, trim, lx, ly, UF + 1.09, 0.15, 0.15, 0.09)


def upstairs(scn, tf, side, trim, rnd):
    """Bedrooms, landing and bathroom over the ground floor — 1950s, lived-in and ruined."""
    wp_a = 'wallpaper_a' if side == 'yellow' else 'wallpaper_b'
    wp_b = 'wallpaper_b' if side == 'yellow' else 'wallpaper_a'
    zs = ZOff(scn, UF)                       # furniture builders work at "floor = 0"

    # ---------------- partitions
    tf.wall_y(scn, wp_a, UWA, IY0, IY1, UF, C2, IT,
              [op(a, b, UF, UF + 2.15, 'open') for (a, b) in UP_OPS['UWA']],
              inner_mat=wp_b, col=True, col_top=C2)
    tf.wall_x(scn, wp_b, UWB, IX0, UWA - IT / 2, UF, C2, IT,
              [op(a, b, UF, UF + 2.15, 'open') for (a, b) in UP_OPS['UWB']],
              inner_mat=wp_a, col=True, col_top=C2)
    tf.wall_x(scn, wp_a, UWC, UWA + IT / 2, IX1, UF, C2, IT,
              [op(a, b, UF, UF + 2.15, 'open') for (a, b) in UP_OPS['UWC']],
              inner_mat=wp_b, col=True, col_top=C2)
    tf.wall_x(scn, wp_b, UWD, IX0, UWA - IT / 2, UF, C2, IT,
              [op(a, b, UF, UF + 2.15, 'open') for (a, b) in UP_OPS['UWD']],
              inner_mat=wp_a, col=True, col_top=C2)
    tf.wall_y(scn, wp_b, UWE, UWB + IT / 2, IY1, UF, C2, IT,
              [op(a, b, UF, UF + 2.15, 'open') for (a, b) in UP_OPS['UWE']],
              inner_mat=wp_b, col=True, col_top=C2)

    # skirting + cased openings, exactly as downstairs
    def skirt(ax, pos, a0, a1, gaps=(), off=0.03):
        cur, segs = a0, []
        for (g0, g1) in sorted(gaps):
            if g0 - cur > 0.06:
                segs.append((cur, g0))
            cur = max(cur, g1)
        if a1 - cur > 0.06:
            segs.append((cur, a1))
        for (s0, s1) in segs:
            if ax == 'y':
                tf.box(scn, trim, pos + off, (s0 + s1) / 2, UF + 0.06, 0.05, s1 - s0, 0.12)
            else:
                tf.box(scn, trim, (s0 + s1) / 2, pos + off, UF + 0.06, s1 - s0, 0.05, 0.12)

    skirt('y', IX0, IY0, IY1, [])
    skirt('y', IX1, IY0, IY1, [], -0.03)
    skirt('x', IY0, IX0, IX1, [])
    skirt('x', IY1, IX0, IX1, [], -0.03)
    INNER = (('y', UWA, IY0, IY1, UP_OPS['UWA']), ('x', UWB, IX0, UWA, UP_OPS['UWB']),
             ('x', UWC, UWA, IX1, UP_OPS['UWC']), ('x', UWD, IX0, UWA, UP_OPS['UWD']),
             ('y', UWE, UWB, IY1, UP_OPS['UWE']))
    for (ax, pos, a0, a1, gaps) in INNER:
        skirt(ax, pos, a0, a1, gaps, IT / 2 + 0.022)
        skirt(ax, pos, a0, a1, gaps, -(IT / 2 + 0.022))
        for (g0, g1) in gaps:
            for e in (g0, g1):
                if ax == 'y':
                    tf.box(scn, trim, pos, e, UF + 1.10, IT + 0.11, 0.11, 2.21)
                else:
                    tf.box(scn, trim, e, pos, UF + 1.10, 0.11, IT + 0.11, 2.21)
            if ax == 'y':
                tf.box(scn, trim, pos, (g0 + g1) / 2, UF + 2.21, IT + 0.11, abs(g1 - g0) + 0.22, 0.11)
            else:
                tf.box(scn, trim, (g0 + g1) / 2, pos, UF + 2.21, abs(g1 - g0) + 0.22, IT + 0.11, 0.11)

    # ---------------- ceiling + two light fittings
    tf.box(scn, 'plaster', BACK / 2, 0, C2 + 0.07, BACK - 2 * T + 0.05, 13.0 - 2 * T + 0.05, 0.18)
    for (lx_, ly_) in UP_LIGHTS:
        tf.box(scn, 'plaster', lx_, ly_, C2 - 0.04, 0.22, 0.22, 0.06)
        scn.cyl('metal_dark', tf.p(lx_, ly_, C2 - 0.14), 0.014, 0.18, 6)
        scn.cyl('paint_cream', tf.p(lx_, ly_, C2 - 0.30), 0.17, 0.20, 12, r2=0.09)
        tf.box(scn, 'lamp_glow', lx_, ly_, C2 - 0.28, 0.12, 0.12, 0.12)

    # ---------------- bedroom A1 (front, over the living room)
    bed(zs, *tf.p(2.10, -5.05)[:2], tf.yaw(1, 0))
    tf.box(scn, 'fabric_weave_b', 2.6, -3.55, UF + 0.008, 2.4, 1.8, 0.014)
    dresser(zs, *tf.p(4.10, -5.70)[:2], tf.yaw(0, 1), 1.10, 0.86, 0.48)
    wardrobe(zs, *tf.p(0.60, -3.55)[:2], tf.yaw(1, 0), 1.20, 0.58, 2.05, open_=True)
    tf.box(scn, 'wood_bare', 0.62, -5.90, UF + 0.28, 0.46, 0.42, 0.56)        # nightstand
    tf.box(scn, 'paint_cream', 0.62, -5.90, UF + 0.70, 0.20, 0.20, 0.30)
    picture(zs, 'charred', *tf.p(0.30, -3.9)[:2], 1.75, 0.05, 0.46, tf.yaw(1, 0))
    paper_scatter(zs, tf.x(3.4), tf.y(-3.4), 1.4, 8, 61, wp_a)

    # ---------------- bedroom A2 (two children's beds, a cot and a toy chest)
    bed(zs, *tf.p(1.55, -1.85)[:2], tf.yaw(1, 0))
    bed(zs, *tf.p(4.30, 0.55)[:2], tf.yaw(1, 0))
    cot(zs, *tf.p(5.45, -1.85)[:2], tf.yaw(0, -1))
    tf.box(scn, 'wood_bare', 5.40, -0.60, UF + 0.26, 0.92, 0.52, 0.52)        # toy chest
    tf.box(scn, 'wood_bare', 5.40, -0.60, UF + 0.55, 0.98, 0.58, 0.06)
    scn.col_obj('COL_PROP', tf.p(5.40, -0.60, UF + 0.29), (1.0, 0.6, 0.58))
    table(zs, *tf.p(2.30, -0.75)[:2], tf.yaw(0, 1), 1.05, 0.55, 0.70)
    chair(zs, *tf.p(2.30, -1.40)[:2], tf.yaw(0, 1))
    tf.box(scn, 'fabric_weave_o', 2.9, -1.0, UF + 0.008, 2.0, 1.5, 0.014)
    for i in range(9):                                                        # scattered toys
        s = rnd.uniform(0.06, 0.13)
        scn.box(rnd.choice(['paint_red', 'paint_cream', 'wood_bare', 'chrome']),
                tf.p(rnd.uniform(0.7, 5.4), rnd.uniform(-2.3, 1.3), UF + s / 2),
                (s * 1.6, s * 1.4, s), rot=(0, 0, rnd.uniform(0, 3.1)))

    # ---------------- box room (lx 0.22 .. 3.30, ly 1.60 .. 6.28): junk, trunks, a sewing table
    for i in range(3):
        tf.box(scn, 'wood_bare', 0.85, 5.40, UF + 0.23 + i * 0.46, 0.86, 0.64, 0.44,
               tilt=(0, 0), yaw=rnd.uniform(-0.15, 0.15))
    scn.col_obj('COL_PROP', tf.p(0.85, 5.40, UF + 0.69), (0.95, 0.75, 1.38))
    table(zs, *tf.p(2.40, 5.00)[:2], tf.yaw(-1, 0), 1.10, 0.58, 0.74)
    scn.box('metal_dark', tf.p(2.40, 5.00, UF + 0.86), (0.42, 0.24, 0.20))
    scn.cyl('metal_dark', tf.p(2.25, 5.00, UF + 1.00), 0.10, 0.06, 10, axis='x')
    shelf_unit(zs, *tf.p(0.60, 3.30)[:2], tf.yaw(-1, 0), 0.85, 1.70, 0.30, seed=41)
    tf.box(scn, 'wood_bare', 2.70, 4.90, UF + 0.20, 0.70, 0.44, 0.40, tilt=(0.05, 0))
    debris_pile(zs, tf.x(1.9), tf.y(4.2), 1.0, 12, 77)

    # ---------------- bathroom (lx 3.30 .. 6.10, ly 1.60 .. 6.28)
    tf.box(scn, 'lino', (UWE + UWA) / 2, (UWB + IY1) / 2, UF + 0.014,
           UWA - UWE - IT, IY1 - UWB - IT, 0.032)
    bathtub(zs, *tf.p(4.55, 5.55)[:2], tf.yaw(0, -1))
    toilet(zs, *tf.p(5.55, 2.35)[:2], tf.yaw(-1, 0))
    basin(zs, *tf.p(4.70, 2.20)[:2], tf.yaw(0, 1))
    mirror_cabinet(zs, *tf.p(4.70, 1.78)[:2], 1.52, tf.yaw(0, 1), 0.52, 0.66)
    for i in range(4):                                     # a hanging shower rail and curtain
        scn.cyl('chrome', tf.p(3.80 + i * 0.5, 5.00, UF + 1.95), 0.016, 0.5, 6, axis='x')
    tf.box(scn, 'cloth_white', 3.80, 4.95, UF + 1.35, 0.06, 0.9, 1.15, tilt=(0, 0.04))
    tf.box(scn, 'glass', 3.45, 3.95, UF + 0.006, 0.5, 0.7, 0.008)              # broken tiles
    for i in range(12):
        scn.box('paint_cream', tf.p(rnd.uniform(3.5, 6.0), rnd.uniform(1.9, 6.1), UF + 0.008),
                (0.13, 0.13, 0.012), rot=(0, rnd.uniform(-0.1, 0.1), rnd.uniform(0, 3.1)))

    # ---------------- landing (round the stairwell) + the upstairs barrier window
    tf.box(scn, 'fabric_weave_r', 6.90, 2.40, UF + 0.008, 1.2, 3.2, 0.014)     # runner
    bookcase(zs, *tf.p(9.95, -0.60)[:2], tf.yaw(1, 0), 0.90, 1.60, 0.30, seed=43, toppled=True)
    tf.box(scn, 'wood_bare', 10.66, 2.55, UF + 0.38, 0.34, 1.10, 0.76)         # hall table
    tf.box(scn, 'wood_bare', 10.66, 2.55, UF + 0.78, 0.40, 1.20, 0.05)
    scn.col_obj('COL_PROP', tf.p(10.66, 2.55, UF + 0.40), (0.42, 1.25, 0.8))
    scn.cyl('paint_cream', tf.p(10.66, 2.20, UF + 0.95), 0.12, 0.30, 10, r2=0.07)
    # linen cupboard against the landing's south wall
    wardrobe(zs, *tf.p(6.60, 5.60)[:2], tf.yaw(1, 0), 1.00, 0.45, 1.95)
    debris_pile(zs, tf.x(10.3), tf.y(3.4), 1.0, 11, 79)

    # ---------------- bedroom B (back, over the ground-floor bedroom) — keeps MK_BOX clear
    bed(zs, *tf.p(8.90, -3.60)[:2], tf.yaw(0, 1))   # clear of the landing / bedroom B doorway
    dresser(zs, *tf.p(10.35, -2.20)[:2], tf.yaw(-1, 0), 1.10, 0.90, 0.50)
    wardrobe(zs, *tf.p(10.30, -5.30)[:2], tf.yaw(-1, 0), 1.15, 0.58, 2.05)
    tf.box(scn, 'fabric_weave_o', 7.3, -3.4, UF + 0.008, 1.8, 2.4, 0.014)
    paper_scatter(zs, tf.x(8.6), tf.y(-2.0), 1.3, 7, 63, wp_b)

    # ---------------- ruin pass: fallen plaster, soot, cracks, rain damage
    for i in range(34):
        lx = rnd.uniform(0.5, BACK - 0.5)
        ly = rnd.uniform(-6.0, 6.0)
        if HX0 - 0.2 < lx < HX1 + 0.2 and HY0 - 0.2 < ly < HY1 + 0.2:
            continue
        s = rnd.uniform(0.05, 0.19)
        scn.rock(rnd.choice(['plaster', 'rubble', 'charred', 'wood_bare']),
                 tf.p(lx, ly, UF + s * 0.3), (s * 2.2, s * 2.2, s), seed=420 + i)
    for i in range(7):                                     # lath showing through the ceiling
        lx = rnd.uniform(1.0, BACK - 1.0)
        ly = rnd.uniform(-5.4, 5.4)
        tf.box(scn, 'charred', lx, ly, C2 - 0.035, rnd.uniform(0.6, 1.5),
               rnd.uniform(0.5, 1.2), 0.06)
        for k in range(4):
            tf.box(scn, 'wood_bare', lx - 0.4 + k * 0.27, ly, C2 - 0.09, 0.06, 0.9, 0.05)

    def dc(name, lx, ly, z, size, nrm, rot=0.0, lift=0.010):
        scn.decal(name, tf.p(lx, ly, z), size,
                  (tf.sx * nrm[0], tf.sy * nrm[1], nrm[2]), rot=rot, lift=lift)
    for (lx, ly) in ((2.4, -4.2), (4.6, 3.4), (9.2, -3.6)):
        dc('water', lx, ly, C2, (1.2, 1.1), (0, 0, -1))
    for (lx, ly) in ((7.2, 1.2), (2.0, 0.4)):
        dc('crack', lx, ly, C2, (2.2, 2.2), (0, 0, -1))
    for (lx, ly, nrm, sz) in ((3.2, -6.28, (0, 1, 0), (3.2, 1.0)), (0.22, -2.0, (1, 0, 0), (3.0, 1.0)),
                              (10.88, 3.2, (-1, 0, 0), (3.0, 1.0)), (5.6, 6.28, (0, -1, 0), (2.6, 1.0))):
        dc('grime', lx, ly, UF + 0.45, sz, nrm, rot=math.pi)
    dc('soot', 10.88, 5.50, UF + 1.35, (1.6, 1.7), (-1, 0, 0))
    dc('poster', 0.22, -4.6, UF + 1.55, (0.56, 0.78), (1, 0, 0), lift=0.008)
    dc('streak', 10.88, 1.4, UF + 1.5, (1.8, 2.0), (-1, 0, 0))


def utility_wing(scn, tf, side, trim):
    """Single-storey flat-roofed wing on the back wall. Its roof is the spawn pocket for the
    upstairs barrier window: walkable, 0.90 m below the sill, and unreachable from the ground."""
    sid = 'siding_yellow' if side == 'yellow' else 'siding_green'
    x0, x1 = L.WING_LX0, L.WING_LX1
    y0, y1 = L.WING_LY0, L.WING_LY1
    zr = UF                                    # roof deck top = upstairs floor level
    # slab, walls, flat roof
    tf.box(scn, 'concrete', (x0 + x1) / 2, (y0 + y1) / 2, 0.03, x1 - x0, y1 - y0, 0.30)
    WT, WTOP = 0.13, zr - 0.13
    tf.wall_y(scn, sid, x1 - WT / 2, y0, y1, 0.16, WTOP, WT,
              [op(y0 + 0.55, y1 - 0.55, 0.16, 2.30)], inner_mat='plaster', out=1, col=False)
    tf.wall_x(scn, sid, y0 + WT / 2, x0, x1, 0.16, WTOP, WT, inner_mat='plaster', out=-1, col=False)
    tf.wall_x(scn, sid, y1 - WT / 2, x0, x1, 0.16, WTOP, WT,
              [op(x0 + 1.10, x0 + 2.30, 1.10, 2.10)], inner_mat='plaster', out=1, col=False)
    tf.box(scn, 'shingle', (x0 + x1) / 2, (y0 + y1) / 2, zr - 0.075, x1 - x0 + 0.16,
           y1 - y0 + 0.16, 0.15)               # flat roof deck, top exactly at UF
    tf.box(scn, 'charred', (x0 + x1) / 2, (y0 + y1) / 2, WTOP - 0.95, x1 - x0 - 2 * WT - 0.03,
           y1 - y0 - 2 * WT - 0.03, 1.8)       # dark interior so the openings do not see sky
    for (a0, a1, b0, b1) in ((x1 + 0.03, x1 + 0.10, y0 - 0.08, y1 + 0.08),
                             (x0 + 2.0, x1 + 0.10, y0 - 0.08, y0 - 0.01),
                             (x0 + 2.0, x1 + 0.10, y1 + 0.01, y1 + 0.08)):
        tf.box(scn, trim, (a0 + a1) / 2, (b0 + b1) / 2, zr + 0.055,
               abs(a1 - a0), abs(b1 - b0), 0.11)     # low upstand, clear of the climb-in lane
    # up-and-over garage door, hanging off its track
    tf.box(scn, 'wood_white', x1 - 0.22, (y0 + y1) / 2, 1.20, 0.07, y1 - y0 - 1.24, 2.06,
           tilt=(0, 0.03))
    for i in range(4):
        tf.box(scn, 'wood_bare', x1 - 0.28, (y0 + y1) / 2, 0.36 + i * 0.52,
               0.05, y1 - y0 - 1.28, 0.07, tilt=(0, 0.03))
    window_frame(scn, tf, 'x', y1 - WT / 2, x0 + 1.10, x0 + 2.30, 1.10, 2.10, trim, True, 51)
    scn.cyl('metal_rust', tf.p(x1 + 0.12, (y0 + y1) / 2, zr - 0.22), 0.07, y1 - y0, 8, axis='y')
    scn.cyl('metal_rust', tf.p(x1 + 0.12, y0 + 0.25, (zr - 0.22) / 2), 0.05, zr - 0.22, 8)
    # gravel + storm damage on the roof
    rnd = random.Random(19 if side == 'yellow' else 20)
    for i in range(22):
        s = rnd.uniform(0.07, 0.22)
        lx = rnd.uniform(x0 + 0.3, x1 - 0.3)
        ly = rnd.uniform(y0 + 0.3, y1 - 0.3)
        if abs(ly - (L.UP_BARR_LY0 + L.UP_BARR_LY1) / 2) < 0.9 and lx < x0 + 2.6:
            continue                                        # keep the climb-in lane clear
        scn.rock(rnd.choice(['rubble', 'charred', 'shingle']), tf.p(lx, ly, UF + s * 0.25),
                 (s * 2.0, s * 2.0, s), seed=470 + i)
    scn.decal('grime', tf.p((x0 + x1) / 2, (y0 + y1) / 2, UF), (3.4, 3.4), (0, 0, 1), lift=0.006)
    scn.decal('streak', tf.p(x0 + 0.02, L.UP_BARR_LY0 - 0.75, UF + 1.20),
              (1.1, 1.9), (tf.sx * 1.0, 0, 0), lift=0.012)
    # one solid collider: the sides are 3 m of blank wall, the top is the walkable pocket
    tf.col(scn, 'COL_WING_' + side, x0, y0, -0.2, x1 + 0.12, y1, UF)


def back_door(scn, tf, door_id, trim):
    """Boarded back door into the yard + its blocker and stoop."""
    y0, y1 = L.BACKDOOR_LY0, L.BACKDOOR_LY1
    cy = (y0 + y1) / 2
    # casing
    tf.box(scn, trim, BACK - T / 2, cy, L.DOOR_H + 0.06, T + 0.10, y1 - y0 + 0.26, 0.12)
    for k in (-1, 1):
        tf.box(scn, trim, BACK - T / 2, cy + k * ((y1 - y0) / 2 + 0.06), L.DOOR_H / 2,
               T + 0.10, 0.12, L.DOOR_H + 0.12)
    # concrete stoop outside
    tf.box(scn, 'sidewalk', BACK + 0.70, cy, 0.005, 1.50, y1 - y0 + 0.9, 0.15)
    tf.box(scn, 'sidewalk', BACK + 1.60, cy, -0.02, 0.40, y1 - y0 + 0.5, 0.10)

    g = scn.group('DOOR_' + door_id, tf.p(BACK, cy, 0.0))
    cx = tf.x(BACK - T / 2)
    wy = tf.y(cy)
    rnd = random.Random(sum(ord(c) for c in door_id))
    g.box(trim, (cx, wy, 1.05), (T * 0.5, 1.72, 2.10))
    for j in range(3):
        g.box(trim, (cx + tf.sx * T * 0.28, wy, 0.42 + j * 0.62), (0.03, 1.40, 0.44))
    g.box('glass', (cx + tf.sx * T * 0.18, wy, 1.80), (0.04, 1.30, 0.42))
    g.cyl('chrome', (cx + tf.sx * T * 0.34, wy + tf.sy * 0.66, 1.02), 0.045, 0.14, 8, axis='x')
    # a fly screen hanging off one hinge, plus nailed boards
    # screen door hanging off its top hinge, flat against the leaf (a solid sheet here read
    # as a black slab over the whole door)
    for (ddy, ddz, ssy, ssz) in ((0.0, 2.05, 1.66, 0.075), (0.0, 0.06, 1.66, 0.075),
                                 (-0.79, 1.05, 0.075, 2.06), (0.79, 1.05, 0.075, 2.06),
                                 (0.0, 1.05, 0.075, 2.06)):
        g.box('wood_white', (cx + tf.sx * T * 0.82, wy + tf.sy * ddy, ddz), (0.05, ssy, ssz))
    g.box('glass', (cx + tf.sx * T * 0.82, wy, 1.05), (0.02, 1.60, 2.00))
    for i in range(4):
        z = 0.40 + i * 0.52
        g.box('wood_bare', (cx + tf.sx * T * 0.62, wy + tf.sy * rnd.uniform(-0.10, 0.10), z),
              (0.05, 2.00, 0.20), rot=(rnd.uniform(-0.05, 0.05), 0, 0))
        for k in (-1, 1):
            g.box('metal_dark', (cx + tf.sx * T * 0.86, wy + tf.sy * k * 0.80, z),
                  (0.02, 0.05, 0.05))
    g.build()
    tf.col(scn, 'COL_DOOR_' + door_id, BACK - T - 0.06, y0, 0.0, BACK + 0.12, y1, L.DOOR_H)


# --------------------------------------------------------------------------- the house
def build_house(scn, side, door_id):
    tf = TF(side)
    sid = 'siding_yellow' if side == 'yellow' else 'siding_green'
    trim = 'wood_trim_y' if side == 'yellow' else 'wood_trim_g'
    wp_main = 'wallpaper_a' if side == 'yellow' else 'wallpaper_b'
    wp_alt = 'wallpaper_b' if side == 'yellow' else 'wallpaper_a'
    rnd = random.Random(1 if side == 'yellow' else 2)

    # ---------------- floors
    tf.box(scn, 'woodfloor', BACK / 2, 0, -0.092, BACK + 0.10, 13.1, 0.18)             # sub floor
    tf.box(scn, 'lino', (IX0 + WA) / 2, (WB + IY1) / 2, 0.012,
           WA - IX0, IY1 - WB, 0.03)                                                   # kitchen lino
    tf.col(scn, 'COL_FLOOR_' + side, 0.0, -6.5, -1.0, BACK, 6.5, 0.0)

    # foundation skirt
    tf.wall_y(scn, 'concrete', 0.02, -6.56, 6.56, -0.45, 0.16, 0.30, col=False)
    tf.wall_y(scn, 'concrete', BACK - 0.02, -6.56, 6.56, -0.45, 0.16, 0.30, col=False)
    tf.wall_x(scn, 'concrete', -6.48, 0.0, BACK, -0.45, 0.16, 0.30, col=False)
    tf.wall_x(scn, 'concrete', 6.48, 0.0, BACK, -0.45, 0.16, 0.30, col=False)

    # ---------------- ground floor exterior walls
    front_ops = [op(-3.0, -1.2, 0.0, L.DOOR_H, 'door', door_id),
                 op(-5.9, -4.3, 0.95, 2.15), op(4.4, 5.6, 0.95, 2.15)]
    tf.wall_y(scn, sid, T / 2, -6.5, 6.5, 0.0, CH + 0.22, T, front_ops,
              inner_mat=wp_main, out=-1, col_top=4.0)
    back_ops = [op(-4.0, -2.8, L.BARRIER_SILL, L.BARRIER_SILL + L.BARRIER_H, 'barrier', 'yw2' if side == 'yellow' else 'gw2'),
                op(L.BACKDOOR_LY0, L.BACKDOOR_LY1, 0.0, L.DOOR_H, 'door', side + '_back'),
                op(2.4, 3.6, 0.95, 2.15)]
    tf.wall_y(scn, sid, BACK - T / 2, -6.5, 6.5, 0.0, CH + 0.22, T, back_ops,
              inner_mat=wp_alt, out=1, col_top=4.0)
    south_ops = [op(1.6, 2.8, 0.95, 2.15), op(7.6, 8.8, 0.95, 2.15)]
    tf.wall_x(scn, sid, -6.5 + T / 2, 0.0, BACK, 0.0, CH + 0.22, T, south_ops,
              inner_mat=wp_main, out=-1, col_top=4.0)
    north_ops = [op(2.7, 3.9, L.BARRIER_SILL, L.BARRIER_SILL + L.BARRIER_H, 'barrier', 'yw1' if side == 'yellow' else 'gw1'),
                 op(7.8, 9.0, 0.95, 2.15)]
    tf.wall_x(scn, sid, 6.5 - T / 2, 0.0, BACK, 0.0, CH + 0.22, T, north_ops,
              inner_mat=wp_alt, out=1, col_top=4.0)

    # ---------------- interior walls
    tf.wall_y(scn, wp_main, WA, IY0, IY1, 0.0, CH, IT,
              [op(-4.2, -2.4, 0.0, 2.15, 'open'), op(3.9, 5.7, 0.0, 2.15, 'open')],
              inner_mat=wp_alt, col_top=CH)
    tf.wall_x(scn, wp_main, WB, IX0, WA - IT / 2, 0.0, CH, IT,
              [op(1.6, 3.4, 0.0, 2.15, 'open')], inner_mat=wp_alt, col_top=CH)
    tf.wall_x(scn, wp_alt, WC, WA + IT / 2, IX1, 0.0, CH, IT,
              [op(7.4, 9.2, 0.0, 2.15, 'open')], inner_mat=wp_alt, col_top=CH)

    # ---------------- skirting boards + door casings (environment.md #21)
    def skirt(ax, pos, a0, a1, gaps=(), off=0.03):
        cur, segs = a0, []
        for (g0, g1) in sorted(gaps):
            if g0 - cur > 0.06:
                segs.append((cur, g0))
            cur = max(cur, g1)
        if a1 - cur > 0.06:
            segs.append((cur, a1))
        for (s0, s1) in segs:
            if ax == 'y':
                tf.box(scn, trim, pos + off, (s0 + s1) / 2, 0.06, 0.05, s1 - s0, 0.12)
            else:
                tf.box(scn, trim, (s0 + s1) / 2, pos + off, 0.06, s1 - s0, 0.05, 0.12)

    skirt('y', IX0, IY0, IY1, [(-3.0, -1.2)])                   # front wall (minus the door)
    skirt('y', IX1, IY0, IY1, [], -0.03)
    skirt('x', IY0, IX0, IX1, [])
    skirt('x', IY1, IX0, IX1, [], -0.03)
    INNER = (('y', WA, IY0, IY1, [(-4.2, -2.4), (3.9, 5.7)]),
             ('x', WB, IX0, WA, [(1.6, 3.4)]),
             ('x', WC, WA, IX1, [(7.4, 9.2)]))
    for (ax, pos, a0, a1, gaps) in INNER:
        skirt(ax, pos, a0, a1, gaps, IT / 2 + 0.022)
        skirt(ax, pos, a0, a1, gaps, -(IT / 2 + 0.022))
    for (ax, pos, _a0, _a1, gaps) in INNER:                     # cased openings
        for (g0, g1) in gaps:
            for e in (g0, g1):
                if ax == 'y':
                    tf.box(scn, trim, pos, e, 1.10, IT + 0.11, 0.11, 2.21)
                else:
                    tf.box(scn, trim, e, pos, 1.10, 0.11, IT + 0.11, 2.21)
            if ax == 'y':
                tf.box(scn, trim, pos, (g0 + g1) / 2, 2.21, IT + 0.11, abs(g1 - g0) + 0.22, 0.11)
            else:
                tf.box(scn, trim, (g0 + g1) / 2, pos, 2.21, abs(g1 - g0) + 0.22, IT + 0.11, 0.11)

    # ---------------- windows & door trim
    bw = ('yw', 'gw')[side != 'yellow']
    window_frame(scn, tf, 'y', T / 2, -5.9, -4.3, 0.95, 2.15, trim, True, 11)
    window_frame(scn, tf, 'y', T / 2, 4.4, 5.6, 0.95, 2.15, trim, False, 12, boarded=True)
    window_frame(scn, tf, 'y', BACK - T / 2, 2.4, 3.6, 0.95, 2.15, trim, True, 13)
    window_frame(scn, tf, 'x', -6.5 + T / 2, 1.6, 2.8, 0.95, 2.15, trim, True, 14)
    window_frame(scn, tf, 'x', -6.5 + T / 2, 7.6, 8.8, 0.95, 2.15, trim, True, 15, boarded=True)
    window_frame(scn, tf, 'x', 6.5 - T / 2, 7.8, 9.0, 0.95, 2.15, trim, False, 16)
    # barrier windows: bare trim only (the game drops barricade.glb in)
    window_frame(scn, tf, 'x', 6.5 - T / 2, 2.7, 3.9, L.BARRIER_SILL, L.BARRIER_SILL + L.BARRIER_H,
                 trim, True, 17, bare=True)
    window_frame(scn, tf, 'y', BACK - T / 2, -4.0, -2.8, L.BARRIER_SILL, L.BARRIER_SILL + L.BARRIER_H,
                 trim, True, 18, bare=True)
    for bid, ax, pos, a0, a1 in ((bw + '1', 'x', 6.5, 2.7, 3.9), (bw + '2', 'y', BACK, -4.0, -2.8)):
        if ax == 'x':
            tf.col(scn, 'COL_BARRIER_' + bid, a0, 6.5 - T, L.BARRIER_SILL, a1, 6.5,
                   L.BARRIER_SILL + L.BARRIER_H)
        else:
            tf.col(scn, 'COL_BARRIER_' + bid, BACK - T, a0, L.BARRIER_SILL, BACK, a1,
                   L.BARRIER_SILL + L.BARRIER_H)

    # door frame + porch
    tf.box(scn, trim, T / 2, -2.1, L.DOOR_H + 0.06, T + 0.10, 2.06, 0.12)
    for k in (-1, 1):
        tf.box(scn, trim, T / 2, -2.1 + k * 0.96, L.DOOR_H / 2, T + 0.10, 0.12, L.DOOR_H + 0.12)
    for i in range(3):
        tf.box(scn, 'chrome', -0.01, -3.35 - i * 0.16, 1.95, 0.03, 0.07, 0.17)
    tf.box(scn, 'wood_bare', -0.03, -2.1, 0.10, 0.08, 1.30, 0.06)
    porch(scn, tf, trim)

    # ---------------- ceiling, upstairs deck, second storey shell and roof
    ceiling_hole(scn, tf, rnd)
    floor_deck(scn, tf, side, trim)

    bu = ('yu1', 'gu1')[side != 'yellow']
    up_front = [op(-5.9, -4.7, UZ0, UZ1), op(-2.4, -1.2, UZ0, UZ1), op(4.4, 5.6, UZ0, UZ1)]
    up_back = [op(-4.6, -3.4, UZ0, UZ1), op(1.0, 2.2, UZ0, UZ1),
               op(L.UP_BARR_LY0, L.UP_BARR_LY1, UZ0, UZ1, 'barrier', bu)]
    up_south = [op(1.6, 2.8, UZ0, UZ1), op(7.6, 8.8, UZ0, UZ1)]
    up_north = [op(1.4, 2.6, UZ0, UZ1), op(4.2, 5.4, UZ0, UZ1), op(9.4, 10.6, UZ0, UZ1)]
    # the upstairs is playable now, so these walls carry collision up to the ceiling
    tf.wall_y(scn, sid, T / 2, -6.5, 6.5, CH + 0.22, C2, T, up_front,
              inner_mat=wp_main, out=-1, col=True, col_top=C2 + 0.3)
    tf.wall_y(scn, sid, BACK - T / 2, -6.5, 6.5, CH + 0.22, C2, T, up_back,
              inner_mat=wp_alt, out=1, col=True, col_top=C2 + 0.3)
    tf.wall_x(scn, sid, -6.5 + T / 2, 0.0, BACK, CH + 0.22, C2, T, up_south,
              inner_mat=wp_main, out=-1, col=True, col_top=C2 + 0.3)
    tf.wall_x(scn, sid, 6.5 - T / 2, 0.0, BACK, CH + 0.22, C2, T, up_north,
              inner_mat=wp_alt, out=1, col=True, col_top=C2 + 0.3)
    for (axs, pos, a0, a1) in ([('y', T / 2, o['a0'], o['a1']) for o in up_front]
                               + [('y', BACK - T / 2, o['a0'], o['a1']) for o in up_back[:2]]
                               + [('x', -6.5 + T / 2, o['a0'], o['a1']) for o in up_south]
                               + [('x', 6.5 - T / 2, o['a0'], o['a1']) for o in up_north]):
        window_frame(scn, tf, axs, pos, a0, a1, UZ0, UZ1, trim,
                     rnd.random() < 0.6, 30 + int(abs(pos) * 7 + a0 * 3))
    # upstairs barrier window: bare trim, blocker, and the wing roof outside it
    window_frame(scn, tf, 'y', BACK - T / 2, L.UP_BARR_LY0, L.UP_BARR_LY1, UZ0, UZ1,
                 trim, True, 19, bare=True)
    tf.col(scn, 'COL_BARRIER_' + bu, BACK - T, L.UP_BARR_LY0, UZ0, BACK, L.UP_BARR_LY1, UZ1)

    upstairs(scn, tf, side, trim, rnd)
    utility_wing(scn, tf, side, trim)

    for (lx_, ly_) in L.HOUSE_LAMPS[side]:
        ceiling_lamp(scn, tf, lx_, ly_)
    roof(scn, tf, trim)
    chimney(scn, tf, trim)
    furnish(scn, tf, side, trim, rnd)
    make_door(scn, tf, door_id, trim)
    staircase(scn, tf, trim, side)
    stair_debris_door(scn, tf, side + '_stairs')
    back_door(scn, tf, side + '_back', trim)


def porch(scn, tf, trim):
    tf.box(scn, 'sidewalk', -0.95, -2.1, -0.01, 1.9, 4.6, 0.18)
    tf.box(scn, 'sidewalk', -2.12, -2.1, -0.03, 0.46, 2.4, 0.11)
    for ly in (-4.15, -0.05):
        tf.box(scn, trim, -1.76, ly, 1.28, 0.14, 0.14, 2.56)
    tf.box(scn, trim, -0.95, -2.1, 2.60, 2.0, 4.7, 0.10)
    roof_plane(scn, 'shingle', tf.x(0.0), 2.86, tf.x(-2.05), 2.56, tf.y(-4.5), tf.y(0.3), 0.10)
    tf.box(scn, trim, -2.06, -2.1, 2.48, 0.08, 4.8, 0.18)
    tf.box(scn, 'lamp_glow', -0.06, -2.1, 2.36, 0.15, 0.15, 0.20)
    tf.box(scn, 'metal_dark', -0.06, -2.1, 2.50, 0.20, 0.20, 0.09)
    tf.box(scn, 'metal_dark', 0.05, -2.1, 2.44, 0.12, 0.10, 0.30)
    scn.col_obj('COL_PORCHPOST', tf.p(-1.76, -4.15, 1.3), (0.2, 0.2, 2.6))
    scn.col_obj('COL_PORCHPOST', tf.p(-1.76, -0.05, 1.3), (0.2, 0.2, 2.6))


def ceiling_hole(scn, tf, rnd):
    """Collapsed patch of ceiling above the living room, with joists showing."""
    cx, cy = 3.2, -0.6
    tf.box(scn, 'charred', cx, cy, CH + 0.095, 2.4, 2.0, 0.21)
    for i in range(5):
        tf.box(scn, 'wood_bare', cx - 1.0 + i * 0.5, cy, CH + 0.02, 0.09, 2.0, 0.22)
    for i in range(10):
        tf.box(scn, 'plaster', cx + rnd.uniform(-1.4, 1.4), cy + rnd.uniform(-1.2, 1.2),
               CH - rnd.uniform(0.0, 0.35), rnd.uniform(0.2, 0.7), rnd.uniform(0.2, 0.6), 0.05,
               tilt=(rnd.uniform(-0.8, 0.8), rnd.uniform(-0.8, 0.8)))
    debris_pile(scn, tf.x(cx), tf.y(cy), 1.5, 22, 91)


def roof(scn, tf, trim):
    x_eave_f = tf.x(-OVER)
    x_ridge = tf.x(BACK / 2)
    x_eave_b = tf.x(BACK + OVER)
    y0, y1 = tf.y(-6.5 - 0.42), tf.y(6.5 + 0.42)
    roof_plane(scn, 'shingle', x_eave_f, C2, x_ridge, RIDGE, y0, y1, 0.14)
    roof_plane(scn, 'shingle', x_ridge, RIDGE, x_eave_b, C2, y0, y1, 0.14)
    scn.box('shingle', (x_ridge, (y0 + y1) / 2, RIDGE + 0.09), (0.46, abs(y1 - y0), 0.13))
    # fascia + soffit
    for xe in (x_eave_f, x_eave_b):
        scn.box(trim, (xe, (y0 + y1) / 2, C2 - 0.12), (0.08, abs(y1 - y0), 0.30))
    # gable end walls
    for ly, yfrom, yto in ((-6.5, tf.y(-6.5), tf.y(-6.5 + T)), (6.5, tf.y(6.5), tf.y(6.5 - T))):
        pts = [(tf.x(0.0), C2), (tf.x(BACK), C2), (tf.x(BACK / 2), RIDGE - 0.08)]
        prism_xz(scn, 'siding_green' if tf.side == 'green' else 'siding_yellow', pts, yfrom, yto)
    # rake boards
    for ly in (-6.5 - 0.42, 6.5 + 0.42):
        for (xa, za, xb, zb) in ((tf.x(-OVER), C2, tf.x(BACK / 2), RIDGE),
                                 (tf.x(BACK / 2), RIDGE, tf.x(BACK + OVER), C2)):
            dx, dz = xb - xa, zb - za
            ln = math.hypot(dx, dz)
            scn.box(trim, ((xa + xb) / 2, tf.y(ly), (za + zb) / 2 - 0.13), (ln, 0.09, 0.22),
                    rot=(0, -math.atan2(dz, dx), 0))
    # gutter
    for xe, s in ((x_eave_f, 1), (x_eave_b, -1)):
        scn.cyl('metal_rust', (xe + s * 0.06, (y0 + y1) / 2, C2 - 0.30), 0.075, abs(y1 - y0),
                8, axis='y')
    scn.cyl('metal_rust', (x_eave_f + 0.06, tf.y(5.9), 2.9), 0.055, 5.0, 8)


def ceiling_lamp(scn, tf, lx, ly):
    tf.box(scn, 'plaster', lx, ly, CH - 0.04, 0.22, 0.22, 0.06)
    scn.cyl('metal_dark', tf.p(lx, ly, CH - 0.13), 0.014, 0.16, 6)
    scn.cyl('paint_cream', tf.p(lx, ly, CH - 0.28), 0.17, 0.20, 12, r2=0.09)
    tf.box(scn, 'lamp_glow', lx, ly, CH - 0.26, 0.12, 0.12, 0.12)


def chimney(scn, tf, trim):
    """Brick stack on the living-room gable wall, with the fireplace it serves.

    It used to stand at (8.4, 3.4) — which is where the new staircase and the stairwell
    opening are, so it speared straight through both of them.
    """
    lx, ly = 5.60, -5.75
    x, y = tf.x(lx), tf.y(ly)
    scn.box('brick', (x, y, 4.3), (0.95, 0.95, 8.6))
    scn.box('brick', (x, y, 8.68), (1.12, 1.12, 0.22))
    scn.box('charred', (x, y, 8.84), (0.55, 0.55, 0.12))
    # fireplace: firebox, hearth slab, brick arch and a timber mantel (living room side)
    tf.box(scn, 'charred', lx, ly + 0.50, 0.52, 0.72, 0.16, 0.88)
    tf.box(scn, 'charred', lx, ly + 0.20, 0.50, 0.70, 0.60, 0.84)
    tf.box(scn, 'concrete', lx, ly + 0.72, 0.03, 1.30, 0.60, 0.10)
    tf.box(scn, trim, lx, ly + 0.52, 1.08, 1.32, 0.26, 0.10)
    for k in (-1, 1):
        tf.box(scn, trim, lx + k * 0.58, ly + 0.50, 0.53, 0.16, 0.20, 1.06)
    for i in range(5):
        tf.box(scn, 'charred', lx + (i - 2) * 0.16, ly + 0.30, 0.14,
               0.13, 0.42, 0.09, tilt=(0, 0.1 * (i - 2)))
    scn.col_obj('COL_PROP', tf.p(lx, ly, 1.35), (1.05, 1.05, 2.7))
    scn.col_obj('COL_PROP', tf.p(lx, ly, 1.35 + UF), (1.05, 1.05, 2.7))


def make_door(scn, tf, door_id, trim):
    """Boarded-over front door, its own node so the game can animate it away."""
    g = scn.group('DOOR_' + door_id, tf.p(0.0, -3.0, 0.0))
    cx, cy = tf.x(T / 2), tf.y(-2.1)
    rnd = random.Random(sum(ord(c) for c in door_id))
    # door leaf
    g.box(trim, (cx, cy, 1.05), (T * 0.5, 1.72, 2.10))
    for j in range(2):
        for k in (-1, 1):
            g.box(trim, (cx + T * 0.30, cy + k * 0.40, 0.58 + j * 0.94), (0.03, 0.62, 0.66))
    g.box('glass_dark', (cx + T * 0.20, cy, 1.72), (0.05, 0.52, 0.34))
    g.cyl('chrome', (cx + T * 0.34, cy + 0.66, 1.02), 0.045, 0.14, 8, axis='x')
    g.box('chrome', (cx + T * 0.30, cy + 0.66, 1.02), (0.05, 0.12, 0.22))
    # nailed-on boards
    for i in range(5):
        z = 0.32 + i * 0.47
        g.box('wood_bare', (cx + T * 0.55, cy + rnd.uniform(-0.10, 0.10), z),
              (0.05, 2.02, 0.20), rot=(rnd.uniform(-0.05, 0.05), 0, 0))
        for k in (-1, 1):
            g.box('metal_dark', (cx + T * 0.80, cy + k * 0.82, z), (0.02, 0.05, 0.05))
    g.box('wood_bare', (cx + T * 0.58, cy, 1.25), (0.05, 0.20, 2.10), rot=(0.42, 0, 0))
    g.build()
    tf.col(scn, 'COL_DOOR_' + door_id, -0.12, -3.02, 0.0, T + 0.16, -1.18, L.DOOR_H)


def furnish(scn, tf, side, trim, rnd):
    # ---- living room (lx 0.22..6.10, ly -6.28..1.60)
    sofa(scn, *tf.p(2.3, -5.55)[:2], tf.yaw(0, 1), 'fabric_red')
    armchair(scn, *tf.p(1.15, -3.4)[:2], tf.yaw(1, 0))
    table(scn, *tf.p(2.4, -4.0)[:2], tf.yaw(0, 1), 1.15, 0.6, 0.44)
    tv_console(scn, *tf.p(5.55, -0.85)[:2], tf.yaw(-1, 0))
    floor_lamp(scn, *tf.p(0.8, -5.7)[:2])
    scn.box('wood_bare', (tf.x(3.0), tf.y(-6.20), 1.75), (0.72, 0.05, 0.56))
    scn.box('charred', (tf.x(3.0), tf.y(-6.18), 1.75), (0.62, 0.04, 0.46))
    # ---- kitchen (lx 0.22..6.10, ly 1.60..6.28)
    counter_run(scn, tf.x(0.55), tf.y(2.6), tf.x(0.55), tf.y(5.1), sink=True)
    counter_run(scn, tf.x(4.55), tf.y(5.92), tf.x(5.95), tf.y(5.92))
    fridge(scn, *tf.p(5.5, 5.75)[:2], tf.yaw(0, -1))
    stove(scn, *tf.p(5.4, 2.5)[:2], tf.yaw(-1, 0))
    table(scn, *tf.p(3.1, 3.6)[:2], 0.0, 1.25, 0.85, 0.76)
    chair(scn, *tf.p(3.1, 2.85)[:2], tf.yaw(0, 1))
    chair(scn, *tf.p(3.1, 4.35)[:2], tf.yaw(0, -1))
    chair(scn, *tf.p(2.15, 3.6)[:2], tf.yaw(1, 0))
    # ---- bedroom (lx 6.10..10.88, ly -6.28..-1.20)
    bed(scn, *tf.p(7.3, -4.6)[:2], tf.yaw(0, 1))
    dresser(scn, *tf.p(10.1, -1.9)[:2], tf.yaw(-1, 0))
    scn.box('wood_bare', (tf.x(10.84), tf.y(-5.4), 1.55), (0.06, 0.70, 0.95))
    scn.box('chrome', (tf.x(10.79), tf.y(-5.4), 1.55), (0.03, 0.58, 0.83))
    # ---- hall (lx 6.10..10.88, ly -1.20..6.28); the staircase is built separately
    dresser(scn, *tf.p(6.45, 1.90)[:2], tf.yaw(1, 0), 0.9, 0.78, 0.42)
    debris_pile(scn, tf.x(10.3), tf.y(5.7), 1.0, 12, 55)

    # ---- second dressing pass: rugs, shelves, curtains, clutter
    # living room rug: pile, a woven border and a fringe at each end
    tf.box(scn, 'fabric_weave_r', 2.6, -4.3, 0.008, 2.6, 1.9, 0.014)
    tf.box(scn, 'fabric_weave_b', 2.6, -4.3, 0.010, 2.44, 1.74, 0.013)
    tf.box(scn, 'fabric_weave_r', 2.6, -4.3, 0.012, 2.24, 1.54, 0.012)
    for k in (-1, 1):
        for i in range(13):
            tf.box(scn, 'cloth_white', 1.32 * k + 2.6, -4.3 - 0.72 + i * 0.12, 0.006,
                   0.09, 0.02, 0.008)
    tf.box(scn, 'fabric_weave_o', 10.1, 3.2, 0.008, 1.3, 2.8, 0.014)      # hall runner
    shelf_unit(scn, *tf.p(0.62, -1.15)[:2], tf.yaw(-1, 0), 0.95, 1.85, 0.32, seed=3)
    shelf_unit(scn, *tf.p(0.95, 1.95)[:2], tf.yaw(0, 1), 0.80, 1.55, 0.28, seed=4)
    shelf_unit(scn, *tf.p(6.6, -5.9)[:2], tf.yaw(0, 1), 0.85, 1.65, 0.30, seed=5)
    # wardrobe + bedside table in the bedroom
    tf.box(scn, 'wood_bare', 9.9, -6.0, 1.05, 1.25, 0.62, 2.10)
    tf.box(scn, 'wood_bare', 9.9, -5.69, 1.12, 1.10, 0.04, 1.86)
    scn.col_obj('COL_PROP', tf.p(9.9, -6.0, 1.05), (1.35, 0.7, 2.1))
    tf.box(scn, 'wood_bare', 6.55, -5.6, 0.28, 0.48, 0.44, 0.56)
    tf.box(scn, 'paint_cream', 6.55, -5.6, 0.72, 0.22, 0.22, 0.32)
    # coat rack + suitcase + crates in the hall
    scn.cyl('wood_bare', tf.p(6.55, -0.55, 0.90), 0.045, 1.80, 8)
    scn.cyl('wood_bare', tf.p(6.55, -0.55, 0.03), 0.22, 0.06, 10)
    for k in (-1, 1):
        tf.box(scn, 'wood_bare', 6.55, -0.55 + k * 0.16, 1.74, 0.34, 0.05, 0.05)
    tf.box(scn, 'wood_bare', 10.2, 1.0, 0.14, 0.70, 0.42, 0.28, tilt=(0.0, 0.05))
    for i in range(2):
        tf.box(scn, 'wood_bare', 0.75, 0.55, 0.24 + i * 0.46, 0.80, 0.60, 0.46)
    scn.col_obj('COL_PROP', tf.p(0.75, 0.55, 0.46), (0.9, 0.7, 0.92))
    # curtains over the four ground-floor windows
    curtain(scn, tf, 'y', T / 2, -5.9, -4.3, 0.95, 2.15, 'fabric_weave_r', 11)
    curtain(scn, tf, 'x', -6.5 + T / 2, 1.6, 2.8, 0.95, 2.15, 'fabric_weave_o', 12)
    curtain(scn, tf, 'y', BACK - T / 2, 2.4, 3.6, 0.95, 2.15, 'fabric_weave_o', 13)
    curtain(scn, tf, 'x', 6.5 - T / 2, 7.8, 9.0, 0.95, 2.15, 'fabric_weave_r', 14)
    # papers, broken crockery, fallen chair
    paper_scatter(scn, tf.x(3.6), tf.y(-2.2), 1.5, 9, 21, 'wallpaper_a')
    paper_scatter(scn, tf.x(3.2), tf.y(4.6), 1.3, 8, 22, 'lino')
    paper_scatter(scn, tf.x(10.2), tf.y(2.4), 1.0, 7, 23, 'wallpaper_b')
    scn.box('wood_bare', (tf.x(4.2), tf.y(2.4), 0.22), (0.44, 0.44, 0.05),
            rot=(1.4, 0.2, tf.yaw(0, 1)))
    scn.box('wood_bare', (tf.x(4.05), tf.y(2.2), 0.46), (0.44, 0.05, 0.50),
            rot=(1.4, 0.2, tf.yaw(0, 1)))
    # picture frames and a wall clock
    for (plx, ply, pz, pw, ph, ax) in ((1.3, -6.22, 1.80, 0.52, 0.40, 'x'),
                                       (6.02, -3.1, 1.85, 0.05, 0.46, 'y'),
                                       (10.80, 1.4, 1.78, 0.05, 0.36, 'y')):
        if ax == 'x':
            tf.box(scn, 'wood_bare', plx, ply, pz, pw, 0.05, ph)
            tf.box(scn, 'charred', plx, ply - 0.02, pz, pw - 0.08, 0.04, ph - 0.08)
        else:
            tf.box(scn, 'wood_bare', plx, ply, pz, pw, 0.46, ph)
            tf.box(scn, 'charred', plx - 0.02, ply, pz, pw - 0.02, 0.38, ph - 0.08)
    scn.cyl('wood_bare', tf.p(0.30, 4.1, 2.05), 0.20, 0.07, 14, axis='x')
    scn.cyl('paint_cream', tf.p(0.26, 4.1, 2.05), 0.165, 0.03, 14, axis='x')
    # light switches / sockets
    for (slx, sly, sz) in ((0.28, -2.9, 1.15), (6.02, 4.0, 1.15), (0.28, 2.0, 0.28)):
        tf.box(scn, 'paint_cream', slx, sly, sz, 0.03, 0.10, 0.14)

    # scattered clutter
    for i in range(46):
        lx = rnd.uniform(0.5, BACK - 0.5); ly = rnd.uniform(-6.0, 6.0)
        m = rnd.choice(['rubble', 'wood_bare', 'charred', 'plaster'])
        s = rnd.uniform(0.05, 0.20)
        scn.rock(m, tf.p(lx, ly, s * 0.3), (s * 2.2, s * 2.2, s), seed=200 + i)

    # ---- the house did not just get emptied, it got knocked over (environment.md #21)
    # toppled floor lamp
    scn.cyl('metal_dark', tf.p(4.55, -2.35, 0.19), 0.022, 1.50, 8, axis='x',
            rot=(0, 0, tf.yaw(0.9, 0.4)))
    scn.cyl('paint_cream', tf.p(5.20, -2.05, 0.21), 0.20, 0.30, 12, r2=0.15, axis='x',
            rot=(0, 0, tf.yaw(0.9, 0.4)))
    scn.cyl('metal_dark', tf.p(3.90, -2.65, 0.02), 0.16, 0.04, 10)
    # knocked-down picture frames
    for (plx, ply, pyaw) in ((1.62, -5.85, 0.8), (7.10, 1.05, -0.4), (2.30, 5.40, 2.1)):
        tf.box(scn, 'wood_bare', plx, ply, 0.026, 0.52, 0.40, 0.05, tilt=(0.0, 0.06))
        tf.box(scn, 'glass', plx, ply, 0.052, 0.44, 0.32, 0.006)
    # a chair on its back and a dropped drawer
    tf.box(scn, 'wood_bare', 10.35, 4.45, 0.10, 0.60, 0.44, 0.20, tilt=(0.0, 0.10))
    tf.box(scn, 'wood_bare', 10.35, 4.45, 0.21, 0.54, 0.38, 0.03)
    # broken glass under the smashed windows
    for (glx, gly) in ((0.72, -5.10), (0.72, 5.00), (BACK - 0.72, 3.00), (2.20, -5.90)):
        for i in range(7):
            scn.box('glass', tf.p(glx + rnd.uniform(-0.35, 0.35), gly + rnd.uniform(-0.35, 0.35),
                                  0.008), (rnd.uniform(0.04, 0.13), rnd.uniform(0.03, 0.09), 0.004),
                    rot=(0, rnd.uniform(-0.1, 0.1), rnd.uniform(0, 3.14)))

    # ---- authored decals: ceiling leaks, grime at the skirting, soot, a torn poster
    def dc(name, lx, ly, z, size, nrm, rot=0.0, lift=0.010):
        scn.decal(name, tf.p(lx, ly, z), size,
                  (tf.sx * nrm[0], tf.sy * nrm[1], nrm[2]), rot=rot, lift=lift)
    for (lx, ly) in ((2.8, -3.6), (8.8, 2.4), (3.4, 4.6)):
        dc('water', lx, ly, CH, (1.15, 1.0), (0, 0, -1))
    for (lx, ly) in ((5.4, -4.9), (9.2, -3.1)):
        dc('crack', lx, ly, CH, (2.2, 2.2), (0, 0, -1))
    for (lx, ly, nrm, sz, r) in ((3.4, -6.28, (0, 1, 0), (3.4, 1.0), math.pi),
                                 (0.22, -3.5, (1, 0, 0), (3.2, 1.0), math.pi),
                                 (0.22, 4.0, (1, 0, 0), (3.0, 1.0), math.pi),
                                 (10.88, 2.2, (-1, 0, 0), (3.2, 1.0), math.pi),
                                 (8.0, 6.28, (0, -1, 0), (3.0, 1.0), math.pi)):
        dc('grime', lx, ly, 0.45, sz, nrm, rot=r)
    dc('poster', WA - IT / 2, -4.2, 1.62, (0.62, 0.86), (-1, 0, 0), lift=0.008)
    dc('poster', 0.22, 1.05, 1.55, (0.58, 0.80), (1, 0, 0))
    dc('soot', 10.88, -3.4, 1.95, (1.5, 1.6), (-1, 0, 0))
    dc('streak', 10.88, -0.2, 1.85, (1.8, 2.0), (-1, 0, 0))
    # outside: wash-down under every window and soot out of the barrier openings
    for (lx, ly, nrm) in ((0.0, -5.1, (-1, 0, 0)), (0.0, 5.0, (-1, 0, 0)),
                          (BACK, 3.0, (1, 0, 0)), (2.2, -6.5, (0, -1, 0)),
                          (8.2, -6.5, (0, -1, 0)), (8.4, 6.5, (0, 1, 0))):
        dc('streak', lx, ly, 0.47, (1.8, 1.0), nrm, lift=0.012)
    dc('soot', BACK, -3.4, 2.35, (1.5, 1.7), (1, 0, 0), lift=0.012)
    dc('soot', 3.3, 6.5, 2.35, (1.5, 1.7), (0, 1, 0), lift=0.012)


def build(scn):
    build_house(scn, 'yellow', 'yellow_front')
    build_house(scn, 'green', 'green_front')
