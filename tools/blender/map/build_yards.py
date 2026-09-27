"""Doom Town — the two back yards, now playable.

Each house sits inside a fenced lot that wraps round it on three sides: the back yard proper
behind the house plus the two side strips. The player reaches it through the new back door
(`DOOR_<side>_back`); the ground-floor window spawns that already sat out here
(`MK_SPAWN_WIN_yw1/yw2/gw1/gw2`) keep working, and three ground spawns per yard were added.

House-local coordinates are used wherever the layout should mirror (lx grows away from the
street, ly runs along it), exactly like build_houses.py.
"""
import math, random, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout as L  # noqa: E402
import lib_clutter as CL  # noqa: E402
import lib_tree as TREE  # noqa: E402
from build_houses import TF, debris_pile, table, chair  # noqa: E402

YX, YY = L.YARD_X, L.YARD_Y
HB = L.HOUSE_D                       # 11.10 — back wall plane in house-local lx
LXF = YX - L.STREET_X                # 18.50 — the back fence, in house-local lx


# --------------------------------------------------------------------------- fencing
def board_fence(scn, p0, p1, h=2.15, seed=0, gap_chance=0.10, mat='wood_bare'):
    """Weathered vertical-board fence: posts, two rails, warped boards, missing boards."""
    rnd = random.Random(seed)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ln = math.hypot(dx, dy)
    if ln < 0.2:
        return
    ux, uy = dx / ln, dy / ln
    nx, ny = -uy, ux
    yaw = math.atan2(uy, ux)
    npost = max(2, int(ln / 2.3) + 1)
    for i in range(npost):
        t = ln * i / (npost - 1)
        hh = h * rnd.uniform(0.98, 1.10)
        scn.box('wood_bare', (p0[0] + ux * t, p0[1] + uy * t, hh / 2 - 0.1),
                (0.13, 0.13, hh + 0.2), rot=(0, 0, yaw))
        scn.box('wood_bare', (p0[0] + ux * t, p0[1] + uy * t, hh + 0.02),
                (0.19, 0.19, 0.07), rot=(0, 0, yaw))
    for z in (h * 0.24, h * 0.72):
        scn.box(mat, (p0[0] + ux * ln / 2, p0[1] + uy * ln / 2, z), (ln, 0.055, 0.11),
                rot=(0, 0, yaw))
    step = 0.195
    n = int(ln / step)
    run = 0
    for i in range(n):
        t = (i + 0.5) * step
        if rnd.random() < gap_chance:
            run = rnd.randint(1, 3)
        if run:
            run -= 1
            continue
        hh = h * rnd.uniform(0.90, 1.0)
        lean = rnd.uniform(-0.055, 0.055) if rnd.random() < 0.35 else rnd.uniform(-0.012, 0.012)
        x, y = p0[0] + ux * t, p0[1] + uy * t
        scn.box(mat, (x + nx * 0.048, y + ny * 0.048, hh / 2),
                (0.135, 0.028, hh), rot=(lean * ny, -lean * nx, yaw))
    scn.decal('grime', (p0[0] + ux * ln * 0.5 + nx * 0.07, p0[1] + uy * ln * 0.5 + ny * 0.07,
                        h * 0.30), (min(ln * 0.8, 6.0), h * 0.6), (nx, ny, 0), rot=math.pi,
              lift=0.012)


def yard_boundary(scn, side):
    """Fences + >= 3 m of invisible collision all round the lot."""
    sx = -1.0 if side == 'yellow' else 1.0
    tag = 'yardw' if side == 'yellow' else 'yarde'
    x_out = sx * YX
    x_in = sx * L.STREET_X
    seed = 600 if side == 'yellow' else 650
    # outer (back) fence, in two runs with a collapsed section in the middle
    board_fence(scn, (x_out, -YY), (x_out, -1.6), 2.15, seed=seed)
    board_fence(scn, (x_out, 2.2), (x_out, YY), 2.15, seed=seed + 1)
    # the collapsed bit: flattened boards + a chain-link panel wired across the gap
    rnd = random.Random(seed + 9)
    for i in range(9):
        scn.box('wood_bare', (x_out - sx * rnd.uniform(0.1, 1.3), rnd.uniform(-1.7, 2.3),
                              rnd.uniform(0.03, 0.16)), (0.14, 1.5, 0.03),
                rot=(0, rnd.uniform(-0.25, 0.25), rnd.uniform(-0.4, 0.4)))
    for i in range(4):
        CL.chainlink_panel(scn, x_out - sx * 0.18, -1.3 + i * 1.0, yaw=math.pi / 2, flat=False,
                           seed=seed + 20 + i)
    for i in range(3):
        scn.cyl('metal_rust', (x_out - sx * 0.18, -1.6 + i * 1.9, 1.05), 0.045, 2.1, 8)
    # side fences
    for sgn in (-1, 1):
        board_fence(scn, (x_in, sgn * YY), (x_out, sgn * YY), 2.05, seed=seed + 30 + sgn,
                    gap_chance=0.07)
    # --- collision: 4 m walls, plus the strip of street boundary above the existing fence
    t = 0.35
    for (a0, b0, a1, b1) in ((x_out - sx * t, -YY - t, x_out, YY + t),
                             (min(x_in, x_out), -YY - t, max(x_in, x_out), -YY),
                             (min(x_in, x_out), YY, max(x_in, x_out), YY + t)):
        scn.col_box('COL_BOUND', (min(a0, a1), min(b0, b1), -0.3), (max(a0, a1), max(b0, b1), 4.2))
    for (y0, y1) in ((-YY - t, L.HOUSE_Y0), (L.HOUSE_Y1, YY + t)):
        scn.col_box('COL_BOUND', (min(x_in, x_in + sx * t), y0, -0.3),
                    (max(x_in, x_in + sx * t), y1, 4.2))
    # --- walkable ground
    for (x0, y0, x1, y1) in ((sx * (L.HOUSE_D + L.STREET_X), -YY - 0.2, x_out, YY + 0.2),
                             (x_in, -YY - 0.2, sx * (L.HOUSE_D + L.STREET_X), L.HOUSE_Y0),
                             (x_in, L.HOUSE_Y1, sx * (L.HOUSE_D + L.STREET_X), YY + 0.2)):
        scn.col_box('COL_FLOOR_' + tag, (min(x0, x1), min(y0, y1), -1.0),
                    (max(x0, x1), max(y0, y1), 0.0))


# --------------------------------------------------------------------------- yard props
def clothes_line(scn, tf, lx0, lx1, ly, seed=0):
    rnd = random.Random(seed)
    for lx in (lx0, lx1):
        scn.cyl('metal_rust', tf.p(lx, ly, 0.90), 0.045, 1.80, 8)
        tf.box(scn, 'metal_rust', lx, ly, 1.74, 0.07, 1.20, 0.07)
    for k in (-0.5, 0.5):
        n = 9
        for i in range(n):
            t0, t1 = i / n, (i + 1) / n
            def pt(t):
                sag = 0.16 * 4 * t * (1 - t)
                return (lx0 + (lx1 - lx0) * t, ly + k, 1.72 - sag)
            a, b = pt(t0), pt(t1)
            mid = tuple((a[j] + b[j]) / 2 for j in range(3))
            d = tuple(b[j] - a[j] for j in range(3))
            ln = math.sqrt(sum(v * v for v in d))
            scn.cyl('metal_dark', tf.p(*mid), 0.010, ln * 1.03, 5, axis='x',
                    rot=(0, -math.asin(max(-1, min(1, d[2] / ln))), tf.yaw(1, 0)))
    for i in range(7):                                  # rags still pegged out
        t = rnd.uniform(0.12, 0.88)
        lx = lx0 + (lx1 - lx0) * t
        w = rnd.uniform(0.35, 0.65)
        h = rnd.uniform(0.45, 0.95)
        tf.box(scn, rnd.choice(['cloth_white', 'fabric_weave_o', 'fabric_weave_b', 'cloth_navy']),
               lx, ly + rnd.choice((-0.5, 0.5)), 1.68 - h / 2, w, 0.035, h,
               tilt=(0, rnd.uniform(-0.12, 0.12)))
    scn.col_obj('COL_PROP', tf.p(lx0, ly, 0.9), (0.2, 0.2, 1.8))
    scn.col_obj('COL_PROP', tf.p(lx1, ly, 0.9), (0.2, 0.2, 1.8))


def garden_shed(scn, tf, lx, ly, yaw_dir, seed=0):
    """Timber shed with a pitched felt roof, a leaning door and a small window."""
    w, d, h = 2.60, 2.10, 2.05
    rnd = random.Random(seed)
    for (dx, dy, sx_, sy_) in ((0, d / 2, w, 0.09), (0, -d / 2, w, 0.09),
                               (w / 2, 0, 0.09, d), (-w / 2, 0, 0.09, d)):
        tf.box(scn, 'wood_bare', lx + dx, ly + dy, h / 2, sx_, sy_, h)
    for i in range(int(w / 0.16)):                      # board texture on the long face
        tf.box(scn, 'wood_bare', lx - w / 2 + (i + 0.5) * 0.16, ly - d / 2 - 0.035, h / 2,
               0.145, 0.03, h * rnd.uniform(0.97, 1.0))
    tf.box(scn, 'shingle', lx - 0.1, ly, h + 0.20, w + 0.45, d + 0.40, 0.10, tilt=(0, 0.16))
    tf.box(scn, 'wood_bare', lx, ly - d / 2 - 0.06, 0.95, 0.80, 0.05, 1.86,
           tilt=(0, 0), yaw=0.0)
    tf.box(scn, 'wood_bare', lx + 0.95, ly - d / 2 - 0.20, 0.92, 0.72, 0.06, 1.80,
           tilt=(0.0, 0.0), yaw=0.35)                   # door off its hinges, leaning
    tf.box(scn, 'glass', lx - 0.85, ly - d / 2 - 0.05, 1.42, 0.46, 0.03, 0.42)
    tf.box(scn, 'wood_white', lx - 0.85, ly - d / 2 - 0.07, 1.42, 0.54, 0.03, 0.50)
    scn.decal('rust', tf.p(lx + 0.4, ly - d / 2 - 0.06, 1.1), (1.4, 1.6),
              (0, -tf.sy * 1.0, 0), lift=0.014)
    scn.col_obj('COL_PROP', tf.p(lx, ly, h / 2), (w + 0.2, d + 0.2, h + 0.3))


def swing_set(scn, tf, lx, ly, seed=0):
    """Burnt-out A-frame swing set, one seat left hanging, the other on the ground."""
    rnd = random.Random(seed)
    h, span = 2.10, 2.60
    for k in (-1, 1):
        for j in (-1, 1):
            tf.box(scn, 'charred', lx + k * (span / 2) - j * 0.0, ly + j * 0.62, h / 2,
                   0.09, 0.09, h + 0.22, tilt=(j * 0.28, -k * 0.02))
    tf.box(scn, 'charred', lx, ly, h + 0.02, span + 0.45, 0.11, 0.11)
    for k in (-1, 1):
        for i in range(2):
            dz = 0.55 + i * 0.0
            scn.cyl('metal_rust', tf.p(lx + k * 0.55 + i * 0.30 - 0.15, ly, h * 0.62),
                    0.011, h * 0.76, 5)
    tf.box(scn, 'wood_bare', lx + 0.40, ly, h - 1.62, 0.44, 0.16, 0.05, tilt=(0.06, 0))
    tf.box(scn, 'wood_bare', lx - 1.05, ly + 0.45, 0.03, 0.44, 0.16, 0.05,
           tilt=(0, 0.0), yaw=0.8)
    for i in range(3):
        scn.cyl('metal_rust', tf.p(lx - 1.0 + rnd.uniform(-0.3, 0.3), ly + 0.4, 0.02),
                0.010, rnd.uniform(0.6, 1.2), 5, axis='x', rot=(0, 0, rnd.uniform(0, 3.1)))
    scn.col_obj('COL_PROP', tf.p(lx, ly, 1.1), (span + 0.5, 1.5, 2.2))


def shelter_hatch(scn, tf, lx, ly, seed=0):
    """A half-dug family fallout shelter: spoil heap, timbered pit, steel hatch thrown open."""
    rnd = random.Random(seed)
    scn.disc_slab('dirt_scorch', tf.p(lx, ly, 0)[:2], 1.55, 0.015, -0.05, n=16)
    scn.box_mm('charred', (min(tf.x(lx - 0.75), tf.x(lx + 0.75)), min(tf.y(ly - 0.55), tf.y(ly + 0.55)), -1.1),
               (max(tf.x(lx - 0.75), tf.x(lx + 0.75)), max(tf.y(ly - 0.55), tf.y(ly + 0.55)), -0.08))
    for (a, b, sa, sb) in ((0.82, 0.0, 0.10, 1.30), (-0.82, 0.0, 0.10, 1.30),
                           (0.0, 0.62, 1.74, 0.10), (0.0, -0.62, 1.74, 0.10)):
        tf.box(scn, 'wood_bare', lx + a, ly + b, 0.08, sa, sb, 0.22)
    tf.box(scn, 'steel_paint', lx - 0.30, ly - 1.25, 0.46, 1.60, 0.12, 1.10, tilt=(0.30, 0))
    scn.cyl('metal_rust', tf.p(lx - 0.30, ly - 1.55, 0.86), 0.035, 0.44, 6, axis='x')
    for i in range(16):                                  # spoil heap
        a = rnd.uniform(0, 6.283)
        d = rnd.uniform(1.15, 2.1)
        s = rnd.uniform(0.18, 0.46)
        scn.rock('dirt', tf.p(lx + d * math.cos(a), ly + d * math.sin(a), s * 0.18),
                 (s * 2.3, s * 2.3, s), seed=seed * 13 + i)
    scn.box('wood_bare', tf.p(lx + 1.85, ly + 0.9, 0.55), (0.06, 0.06, 1.10))
    scn.box('paint_stencil_w', tf.p(lx + 1.85, ly + 0.9, 1.18), (0.42, 0.04, 0.34))
    scn.col_obj('COL_PROP', tf.p(lx, ly, 0.20), (2.0, 1.5, 0.4))


def yard_furniture(scn, tf, seed=0):
    rnd = random.Random(seed)
    table(scn, *tf.p(13.4, -1.55)[:2], tf.yaw(0, 1), 1.25, 0.85, 0.72, top='metal_rust')
    chair(scn, *tf.p(13.4, -2.45)[:2], tf.yaw(0, 1), 'metal_rust')
    scn.box('metal_rust', tf.p(12.5, -0.85, 0.20), (0.44, 0.50, 0.05), rot=(1.5, 0.2, tf.yaw(0, 1)))
    scn.box('metal_rust', tf.p(12.5, -1.05, 0.45), (0.44, 0.05, 0.50), rot=(1.5, 0.2, tf.yaw(0, 1)))
    # a sun lounger with rotted webbing
    for k in (-1, 1):
        scn.cyl('metal_rust', tf.p(15.3, -3.4 + k * 0.32, 0.26), 0.022, 1.75, 6, axis='x',
                rot=(0, 0, tf.yaw(1, 0)))
    for i in range(8):
        tf.box(scn, 'fabric_weave_o', 14.5 + i * 0.22, -3.4, 0.27, 0.16, 0.66, 0.02,
               tilt=(0, rnd.uniform(-0.05, 0.05)))
    scn.col_obj('COL_PROP', tf.p(15.3, -3.4, 0.18), (1.9, 0.8, 0.36))
    # incinerator drum + a wheelbarrow on its side
    scn.cyl('metal_rust', tf.p(17.4, 1.9, 0.44), 0.32, 0.88, 14)
    scn.cyl('charred', tf.p(17.4, 1.9, 0.86), 0.29, 0.07, 14)
    scn.col_obj('COL_PROP', tf.p(17.4, 1.9, 0.44), (0.7, 0.7, 0.9))
    scn.cyl('metal_rust', tf.p(12.2, 2.9, 0.30), 0.42, 0.55, 12, axis='x',
            rot=(0, 0, tf.yaw(1, 0.4)))
    scn.cyl('rubber', tf.p(12.9, 3.25, 0.16), 0.16, 0.07, 12, axis='y', rot=(0, 0, tf.yaw(1, 0.4)))
    for k in (-1, 1):
        scn.cyl('wood_bare', tf.p(11.7, 2.9 + k * 0.22, 0.12), 0.026, 0.9, 6, axis='x',
                rot=(0, 0, tf.yaw(1, 0.4)))
    # concrete birdbath, toppled
    scn.cyl('concrete', tf.p(14.0, 3.9, 0.12), 0.20, 0.24, 12, r2=0.14)
    scn.cyl('concrete', tf.p(14.55, 4.15, 0.07), 0.38, 0.14, 14)
    # a vegetable patch gone to nothing, staked out with string
    for i in range(6):
        scn.cyl('wood_bare', tf.p(16.6 + (i % 3) * 0.7, -6.3 + (i // 3) * 0.9, 0.38),
                0.02, 0.76, 5, rot=(rnd.uniform(-0.1, 0.1), 0, 0))
    scn.box('dirt_scorch', tf.p(17.3, -5.85, 0.026), (2.6, 1.6, 0.05))


def build_yard(scn, side):
    tf = TF(side)
    tag = 'yardw' if side == 'yellow' else 'yarde'
    seed = 700 if side == 'yellow' else 760
    rnd = random.Random(seed)
    sx = -1.0 if side == 'yellow' else 1.0

    yard_boundary(scn, side)

    # --- dead lawn: patches of scorched and bleached ground so it is not one flat dirt plane
    # Each patch gets its own height: two patches sharing z would z-fight over their whole
    # overlap (the audit found 367 m2 of it the first time round).
    for i in range(26):
        lx = rnd.uniform(11.7, LXF - 1.0)
        ly = rnd.uniform(-YY + 0.8, YY - 0.8)
        scn.disc_slab(rnd.choice(['dirt_scorch', 'desert']), tf.p(lx, ly, 0)[:2],
                      rnd.uniform(0.9, 2.6), 0.008 + 0.0035 * (i % 7), -0.05 - 0.004 * (i % 5), n=14,
                      squash=rnd.uniform(0.6, 1.3), rot=rnd.uniform(0, 3))
    for i in range(18):                                   # the side strips too
        ly = rnd.choice((-1, 1)) * rnd.uniform(7.0, YY - 0.8)
        lx = rnd.uniform(0.6, 10.5)
        scn.disc_slab(rnd.choice(['dirt_scorch', 'desert']), tf.p(lx, ly, 0)[:2],
                      rnd.uniform(0.8, 2.0), 0.009 + 0.0035 * (i % 7), -0.06 - 0.004 * (i % 5), n=12,
                      squash=rnd.uniform(0.6, 1.3), rot=rnd.uniform(0, 3))

    # --- the set pieces
    garden_shed(scn, tf, 16.9, 9.6, 0.0, seed=seed + 1)
    clothes_line(scn, tf, 12.6, 16.8, -8.6, seed=seed + 2)
    swing_set(scn, tf, 14.2, -11.0, seed=seed + 3)
    shelter_hatch(scn, tf, 15.2, 9.9, seed=seed + 4)
    yard_furniture(scn, tf, seed=seed + 5)

    # a burnt car pushed against the back fence and a dead tree in the corner
    for (tlx, tly, th, ts) in ((17.2, -3.9, 4.4, seed + 6), (3.2, -10.6, 3.6, seed + 7)):
        TREE.place(scn, *tf.p(tlx, tly)[:2], th, seed=ts, collide=False)
        # a shorter trunk collider than lib_tree's default 3.2 m one, so its top stays inside
        # the yard ZONE box (the nav probe only looks inside the zone volume)
        scn.col_obj('COL_TREE', tf.p(tlx, tly, 1.15), (0.7, 0.7, 2.3))

    # --- side strips: bins, a lean-to woodpile, an old bicycle, gas bottles
    CL.bin_can(scn, *tf.p(1.7, 8.2)[:2], yaw=tf.yaw(0, -1), seed=seed + 10)
    CL.bin_can(scn, *tf.p(2.4, 8.4)[:2], yaw=tf.yaw(0, -1), tipped=True, lid=False, seed=seed + 11)
    CL.bin_can(scn, *tf.p(6.8, -8.1)[:2], yaw=tf.yaw(0, 1), seed=seed + 12)
    for i in range(9):                                    # split logs stacked against the wall
        tf.box(scn, 'wood_bare', 8.6 + (i % 3) * 0.34, 7.45, 0.12 + (i // 3) * 0.24,
               0.30, 1.30, 0.22, tilt=(0, 0), yaw=0.0)
    scn.col_obj('COL_PROP', tf.p(8.95, 7.45, 0.36), (1.1, 1.4, 0.75))
    CL.tricycle(scn, *tf.p(4.6, -7.6)[:2], yaw=tf.yaw(1, 0.4))
    for i in range(2):
        scn.cyl('paint_red', tf.p(9.9, -7.9 + i * 0.42, 0.34), 0.17, 0.66, 12)
        scn.cyl('chrome', tf.p(9.9, -7.9 + i * 0.42, 0.70), 0.05, 0.10, 8)
    scn.col_obj('COL_PROP', tf.p(9.9, -7.7, 0.34), (0.42, 0.9, 0.7))

    # --- fallout debris blown across the lot
    bx0, bx1 = sorted((tf.x(11.9), tf.x(LXF - 1.1)))
    CL.debris_field(scn, 26, (bx0, -YY + 1.0, bx1, YY - 1.0),
                    avoid=[tf.p(16.6, 6.5)[:2] + (2.4,), tf.p(14.2, -11.0)[:2] + (2.2,),
                           tf.p(15.2, 9.9)[:2] + (2.4,), tf.p(15.5, -6.0)[:2] + (1.6,),
                           tf.p(16.5, -9.5)[:2] + (1.6,)],
                    seed=seed + 20, blast=(0.0, -12.0), scale=0.85)
    sx0, sx1 = sorted((tf.x(0.5), tf.x(10.9)))
    for sgn in (-1, 1):
        y0, y1 = sorted((tf.y(sgn * 7.0), tf.y(sgn * (YY - 1.0))))
        CL.debris_field(scn, 10, (sx0, y0, sx1, y1),
                        avoid=[tf.p(5.5, sgn * 10.5)[:2] + (1.6,)],
                        seed=seed + 40 + sgn, blast=(0.0, -12.0), scale=0.75)
    for i in range(30):
        lx = rnd.uniform(11.8, LXF - 1.0)
        ly = rnd.uniform(-YY + 0.8, YY - 0.8)
        s = rnd.uniform(0.08, 0.30)
        scn.rock(rnd.choice(['rubble', 'charred', 'brick', 'concrete']),
                 tf.p(lx, ly, s * 0.16), (s * 2.1, s * 2.1, s), seed=seed + 100 + i)

    # --- ground decals: paths worn to bare dirt, oil, scorch, cracked concrete
    scn.decal('grime', tf.p(12.3, 1.1, 0.0), (4.0, 2.4), (0, 0, 1), rot=rnd.uniform(0, 3), lift=0.005)
    scn.decal('scorch', tf.p(14.2, -11.0, 0.0), (3.2, 3.2), (0, 0, 1), lift=0.004)
    scn.decal('oil', tf.p(17.2, 2.0, 0.0), (1.8, 1.5), (0, 0, 1), lift=0.005)
    scn.decal('crack', tf.p(12.0, 1.2, 0.0), (2.6, 2.6), (0, 0, 1), lift=0.004)
    for sgn in (-1, 1):
        scn.decal('grime', tf.p(5.5, sgn * 8.6, 0.0), (5.0, 2.2), (0, 0, 1),
                  rot=math.pi / 2, lift=0.005)
    # wash-down streaks on the back of the house and on the fence
    for (lx, ly, nrm) in ((L.HOUSE_D, -5.2, (1, 0, 0)), (L.HOUSE_D, 1.2, (1, 0, 0))):
        scn.decal('streak', tf.p(lx, ly, 0.5), (1.9, 1.1),
                  (tf.sx * nrm[0], tf.sy * nrm[1], 0), lift=0.014)


def build(scn):
    build_yard(scn, 'yellow')
    build_yard(scn, 'green')
