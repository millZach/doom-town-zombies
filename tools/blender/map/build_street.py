"""Doom Town — the cul-de-sac: ground, road, kerbs, pavements, fences, boundary collision,
street lamps, power poles and the yard dressing."""
import math, random, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_map import culdesac_outline  # noqa: E402
import layout as L  # noqa: E402

R, W = L.ROAD_BULB_R, L.ROAD_W
Y0 = L.STREET_Y_S - 0.6
SX = L.STREET_X


# --------------------------------------------------------------------------- ground
def ground(scn):
    # dirt everywhere except where the two house slabs go
    cut = L.COR_X + 0.42               # the bunker ramp cut must stay open
    for (x0, x1, y0, y1) in (
            (-32.0, L.Y_X0, -27.0, 16.5),
            (L.G_X1, 32.0, -27.0, 16.5),
            (L.Y_X0, L.G_X1, -27.0, L.HOUSE_Y0),
            (-SX, SX, L.HOUSE_Y0, L.HOUSE_Y1),
            (L.Y_X0, -cut, L.HOUSE_Y1, 16.5),
            (cut, L.G_X1, L.HOUSE_Y1, 16.5),
            (-cut, cut, L.HOUSE_Y1, L.RAMP_Y0)):
        # top 5 mm below z=0 so the hundreds of props whose boxes start at 0.0 are not
        # coplanar with it (that is what makes prop bases shimmer)
        scn.box_mm('dirt', (x0, y0, -0.6), (x1, y1, -0.005))

    road = culdesac_outline(R, W, Y0)
    kerb_in = culdesac_outline(R - 0.10, W - 0.10, Y0 + 0.02)
    kerb_out = culdesac_outline(R + 0.55, W + 0.55, Y0)
    walk_in = culdesac_outline(R + 0.53, W + 0.53, Y0)
    walk_out = culdesac_outline(R + 2.05, W + 2.05, Y0)
    scn.slab('asphalt', road, 0.012, -0.35)
    scn.ring('concrete', kerb_in, kerb_out, 0.085, -0.37)
    # The pavement used to start on the kerb's outer outline with the same top and bottom: a
    # coincident vertical face ran the whole length of the kerb, and a coincident underside
    # with it. It now tucks 2 cm under the kerb and sits 1 cm lower.
    scn.ring('sidewalk', walk_in, walk_out, 0.075, -0.34)

    # centre line of the straight road (weathered paint)
    for i in range(12):
        y = -21.5 + i * 1.9
        if y > -6.0:
            break
        scn.box('sign_paint', (0.0, y, 0.016), (0.14, 1.05, 0.006))

    # scorch / burnt patches and craters
    rnd = random.Random(11)
    for (x, y, r) in [(-2.3, -12.6, 4.4), (5.4, 8.2, 3.2), (0.0, -18.4, 2.6)] + \
                     [(f[1][0], f[1][1], 1.7) for f in L.FIRES[:2] + L.FIRES[4:7]]:
        scn.disc_slab('dirt_scorch', (x, y), r, 0.019, -0.05, n=18,
                      squash=rnd.uniform(0.7, 1.2), rot=rnd.uniform(0, 3))
    for (x, y, r, s) in ((6.4, -16.2, 2.2, 1), (-5.6, 6.4, 2.0, 2), (9.2, 5.6, 1.7, 3),
                         (-9.4, -11.6, 2.0, 4), (-3.2, -3.4, 2.4, 5), (2.8, -7.4, 1.6, 6)):
        scn.crater('dirt_scorch', (x, y), r, 0.17, 0.11, seed=s)
        for i in range(9):
            a = rnd.uniform(0, 6.3); d = r * rnd.uniform(1.1, 1.9)
            scn.rock(rnd.choice(['rubble', 'charred', 'concrete']),
                     (x + d * math.cos(a), y + d * math.sin(a), 0.0),
                     (rnd.uniform(0.18, 0.5),) * 3, seed=s * 31 + i)


def surf_z(x, y):
    """Top of whatever surface is at (x, y): asphalt 0.012, kerb/pavement 0.085, dirt 0.0.
    Ground decals have to sit on the right one or they vanish under the kerb."""
    if y < 2.0 - math.sqrt(max(R * R - W * W, 0.01)):
        a = abs(x)
        return 0.012 if a <= W else (0.085 if a <= W + 2.05 else 0.0)
    d = math.hypot(x, y - 2.0)
    return 0.012 if d <= R else (0.085 if d <= R + 2.05 else 0.0)


# --------------------------------------------------------------------------- fences
def picket_fence(scn, p0, p1, h=1.15, seed=0, mat='wood_white', post_mat='wood_bare', bg=False):
    rnd = random.Random(seed)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ln = math.hypot(dx, dy)
    ux, uy = dx / ln, dy / ln
    nx, ny = -uy, ux
    npost = max(2, int(ln / 2.4) + 1)
    for i in range(npost):
        t = ln * i / (npost - 1)
        scn.box(post_mat, (p0[0] + ux * t, p0[1] + uy * t, h * 0.52),
                (0.11, 0.11, h * 1.04 + 0.12), rot=(0, 0, math.atan2(uy, ux)), bg=bg)
    # rails
    for z in (h * 0.28, h * 0.78):
        scn.box(mat, (p0[0] + ux * ln / 2, p0[1] + uy * ln / 2, z), (ln, 0.05, 0.10),
                rot=(0, 0, math.atan2(uy, ux)), bg=bg)
    step = 0.145
    n = int(ln / step)
    for i in range(n):
        if rnd.random() < 0.13:
            continue
        t = (i + 0.5) * step
        hh = h * rnd.uniform(0.93, 1.0)
        lean = rnd.uniform(-0.09, 0.09) if rnd.random() < 0.3 else rnd.uniform(-0.02, 0.02)
        x, y = p0[0] + ux * t, p0[1] + uy * t
        scn.box(mat, (x + nx * 0.03, y + ny * 0.03, hh / 2),
                (0.085, 0.030, hh), rot=(lean * ny, -lean * nx, math.atan2(uy, ux)), bg=bg)
        scn.box(mat, (x + nx * 0.03, y + ny * 0.03, hh + 0.035),
                (0.085, 0.030, 0.075), rot=(0, 0, math.atan2(uy, ux)), bg=bg)


def chain_fence(scn, p0, p1, h=2.0, seed=0):
    rnd = random.Random(seed)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ln = math.hypot(dx, dy); ux, uy = dx / ln, dy / ln
    yaw = math.atan2(uy, ux)
    npost = max(2, int(ln / 3.0) + 1)
    for i in range(npost):
        t = ln * i / (npost - 1)
        scn.cyl('metal_rust', (p0[0] + ux * t, p0[1] + uy * t, h / 2), 0.045, h + 0.1, 8)
    for z in (0.08, h - 0.05):
        scn.cyl('metal_rust', (p0[0] + ux * ln / 2, p0[1] + uy * ln / 2, z), 0.032, ln, 8,
                axis='x', rot=(0, 0, yaw))
    # sagging mesh panels, faked with thin crossed slats
    for i in range(int(ln / 0.55)):
        t = (i + 0.5) * 0.55
        sag = 0.04 * math.sin(t * 1.7)
        scn.box('metal_rust', (p0[0] + ux * t, p0[1] + uy * t, h * 0.5 + sag),
                (0.02, 0.012, h - 0.2), rot=(0, rnd.uniform(-0.05, 0.05), yaw))


def boundary(scn):
    """Fences + tall invisible collision so the player can never leave the street."""
    yw = L.HOUSE_Y1
    segs_w = [((-SX, L.STREET_Y_S), (-SX, L.HOUSE_Y0)), ((-SX, yw), (-SX, L.STREET_Y_N - 0.2))]
    segs_e = [((SX, L.STREET_Y_S), (SX, L.HOUSE_Y0)), ((SX, yw), (SX, L.STREET_Y_N - 0.2))]
    for i, (a, b) in enumerate(segs_w + segs_e):
        picket_fence(scn, a, b, 1.15, seed=100 + i)
    # south end: collapsed fence, concrete blocks, rubble
    chain_fence(scn, (-SX, L.STREET_Y_S), (-3.4, L.STREET_Y_S), 2.1, seed=5)
    chain_fence(scn, (3.4, L.STREET_Y_S), (SX, L.STREET_Y_S), 2.1, seed=6)
    rnd = random.Random(3)
    for i in range(5):
        x = -3.2 + i * 1.6
        scn.box('concrete', (x, L.STREET_Y_S + 0.1, 0.45), (1.5, 0.75, 0.9),
                rot=(0, 0, rnd.uniform(-0.15, 0.15)))
        scn.box('concrete', (x, L.STREET_Y_S + 0.1, 0.92), (1.5, 0.42, 0.06))
    for i in range(26):
        x = rnd.uniform(-SX + 0.5, SX - 0.5)
        y = L.STREET_Y_S + rnd.uniform(0.4, 1.8)
        scn.rock(rnd.choice(['rubble', 'concrete', 'charred']), (x, y, 0.06), (rnd.uniform(0.25, 0.8),) * 3, seed=i)

    # --- collision: 4 m tall walls all round
    t = 0.35
    for (x0, y0, x1, y1) in ((-SX - t, L.STREET_Y_S - 0.2, -SX, L.HOUSE_Y0),
                             (-SX - t, yw, -SX, L.STREET_Y_N + 0.2),
                             (SX, L.STREET_Y_S - 0.2, SX + t, L.HOUSE_Y0),
                             (SX, yw, SX + t, L.STREET_Y_N + 0.2)):
        scn.col_box('COL_BOUND', (x0, y0, -0.2), (x1, y1, 4.2))
    scn.col_box('COL_BOUND', (-SX - t, L.STREET_Y_S - t, -0.2), (SX + t, L.STREET_Y_S + 0.05, 4.2))
    # Floor. It is cut out over the open bunker ramp trench: the single slab used to run right
    # across it at z = 0, so a player climbing the ramp hit an invisible ceiling at street level
    # and had to jump onto it. The ramp's own collider (COL_RAMP_bunker) reaches z = 0 exactly at
    # y = RAMP_Y0, and COL_FLOOR_entry carries the flat landing in front of it, so cutting this
    # hole leaves no gap at the head of the ramp.
    CUT_X, CUT_Y0, CUT_Y1 = 1.8, L.RAMP_Y0, L.STREET_Y_N + 0.3
    scn.col_box('COL_FLOOR_street', (-SX - 0.1, L.STREET_Y_S - 0.1, -1.0), (SX + 0.1, CUT_Y0, 0.0))
    scn.col_box('COL_FLOOR_street', (-SX - 0.1, CUT_Y0, -1.0), (-CUT_X, CUT_Y1, 0.0))
    scn.col_box('COL_FLOOR_street', (CUT_X, CUT_Y0, -1.0), (SX + 0.1, CUT_Y1, 0.0))


# --------------------------------------------------------------------------- street furniture
def street_lamp(scn, x, y, yaw=0.0, h=5.3, seed=0):
    scn.cyl('concrete', (x, y, 0.12), 0.30, 0.24, 12)
    scn.cyl('metal_dark', (x, y, h * 0.5), 0.085, h, 10, r2=0.065)
    # curved arm
    n = 7
    for i in range(n):
        t = (i + 0.5) / n
        a = t * math.pi * 0.5
        ax = x + math.cos(yaw) * 1.35 * math.sin(a)
        ay = y + math.sin(yaw) * 1.35 * math.sin(a)
        az = h + 0.42 * (1 - math.cos(a))
        scn.cyl('metal_dark', (ax, ay, az), 0.055, 0.30, 8, axis='x',
                rot=(0, -a + math.pi / 2, yaw))
    lx, ly = x + math.cos(yaw) * 1.35, y + math.sin(yaw) * 1.35
    scn.box('metal_dark', (lx, ly, h + 0.40), (0.62, 0.34, 0.16), rot=(0, 0, yaw))
    scn.box('lamp_glow', (lx, ly, h + 0.30), (0.50, 0.26, 0.05), rot=(0, 0, yaw))
    return (lx, ly, h + 0.32)


def power_pole(scn, x, y, h=8.5, seed=0, arms=2, bg=False):
    rnd = random.Random(seed)
    lean = rnd.uniform(-0.03, 0.03)
    scn.cyl('wood_bare', (x, y, h / 2), 0.16, h, 8, r2=0.12, rot=(lean, 0, 0), bg=bg)
    for i in range(arms):
        z = h - 0.5 - i * 0.85
        scn.box('wood_bare', (x, y, z), (2.4, 0.14, 0.14), bg=bg)
        for s in (-1, 1):
            scn.cyl('glass', (x + s * 1.05, y, z + 0.18), 0.055, 0.2, 6, bg=bg)
            scn.box('wood_bare', (x + s * 0.5, y, z - 0.35), (0.9, 0.09, 0.09), rot=(0, 0.72, 0), bg=bg)


def wire(scn, p0, p1, sag=0.9, n=8, r=0.025, mat='metal_dark', bg=False):
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        def pt(t):
            return (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t,
                    p0[2] + (p1[2] - p0[2]) * t - sag * 4 * t * (1 - t))
        a, b = pt(t0), pt(t1)
        mid = tuple((a[i] + b[i]) / 2 for i in range(3))
        d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        ln = math.sqrt(sum(v * v for v in d))
        yaw = math.atan2(d[1], d[0])
        pitch = -math.asin(max(-1, min(1, d[2] / ln)))
        scn.cyl(mat, mid, r, ln * 1.02, 5, axis='x', rot=(0, pitch, yaw), bg=bg)


def mailbox(scn, x, y, yaw, seed=0):
    scn.cyl('wood_bare', (x, y, 0.55), 0.055, 1.1, 8)
    scn.box('metal_rust', (x, y, 1.18), (0.22, 0.44, 0.20), rot=(0, 0, yaw))
    scn.cyl('metal_rust', (x, y, 1.28), 0.11, 0.44, 10, axis='y', rot=(0, 0, yaw))
    scn.box('paint_red', (x + 0.13 * math.cos(yaw), y + 0.13 * math.sin(yaw), 1.32),
            (0.05, 0.05, 0.22), rot=(0, 0, yaw))


def fire_barrel(scn, x, y, seed=0, tipped=False):
    rnd = random.Random(seed)
    if tipped:
        scn.cyl('metal_rust', (x, y, 0.30), 0.30, 0.88, 14, axis='x', rot=(0, 0, rnd.uniform(0, 3)))
        return
    scn.cyl('metal_rust', (x, y, 0.44), 0.30, 0.88, 14)
    for z in (0.22, 0.44, 0.66):
        scn.cyl('metal_rust', (x, y, z), 0.315, 0.05, 14)
    scn.cyl('charred', (x, y, 0.86), 0.27, 0.06, 14)
    for i in range(4):
        a = rnd.uniform(0, 6.3)
        scn.box('wood_bare', (x + 0.1 * math.cos(a), y + 0.1 * math.sin(a), 0.98),
                (0.06, 0.06, 0.55), rot=(rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), a))


import lib_tree as TREE  # noqa: E402
import lib_clutter as CL  # noqa: E402
import lib_sign as SIGN  # noqa: E402


def dead_tree(scn, x, y, h=4.6, seed=0, bg=False):
    TREE.place(scn, x, y, h, seed=seed, bg=bg, collide=not bg)


def sign_doom_town(scn, x, y, yaw):
    scn.cyl('wood_bare', (x - 1.5 * math.sin(yaw), y + 1.5 * math.cos(yaw), 1.3), 0.11, 2.6, 8)
    scn.cyl('wood_bare', (x + 1.5 * math.sin(yaw), y - 1.5 * math.cos(yaw), 1.3), 0.11, 2.6, 8)
    scn.box('wood_white', (x, y, 2.05), (3.3, 0.10, 1.25), rot=(0, 0, yaw))
    scn.box('wood_bare', (x, y, 2.05), (3.5, 0.07, 0.10), rot=(0, 0, yaw))
    # real painted lettering on both faces
    c, s = math.cos(yaw), math.sin(yaw)
    for sgn in (-1, 1):
        run = (c * sgn, s * sgn, 0)
        face = (s * sgn, -c * sgn, 0)
        base = (x + face[0] * 0.052, y + face[1] * 0.052, 0.0)
        SIGN.sign_text(scn, 'paint_stencil_k', 'DOOM TOWN', (base[0], base[1], 2.34),
                       run, (0, 0, 1), face, h=0.30, width=2.70, depth=0.004, kind='black')
        SIGN.sign_text(scn, 'paint_stencil_k', 'POP. 412', (base[0], base[1], 1.86),
                       run, (0, 0, 1), face, h=0.18, width=1.60, depth=0.004, kind='black')
    scn.decal('streak', (x + s * 0.052, y - c * 0.052, 1.55), (3.0, 0.45), (s, -c, 0), lift=0.006)
    scn.col_obj('COL_SIGN', (x, y, 1.3), (3.4 * abs(math.cos(yaw)) + 0.3, 3.4 * abs(math.sin(yaw)) + 0.3, 2.6))


def dressing(scn):
    rnd = random.Random(23)
    for (x, y, yaw) in L.STREET_LAMPS:
        street_lamp(scn, x, y, yaw=yaw)
    for (x, y, s) in ((-10.6, -18.5, 1), (10.6, -9.5, 2), (10.8, 8.4, 3)):
        power_pole(scn, x, y, 8.5, seed=s)
    wire(scn, (-10.6, -18.5, 7.9), (10.6, -9.5, 7.9), sag=1.4)
    wire(scn, (10.6, -9.5, 7.9), (10.8, 8.4, 7.9), sag=1.2)
    wire(scn, (10.6, -9.5, 7.05), (10.8, 8.4, 7.05), sag=1.4)

    mailbox(scn, -10.3, -5.0, 1.57, 1)
    mailbox(scn, 10.3, 5.0, -1.57, 2)
    for (x, y, tip, s) in ((L.FIRES[0][1][0], L.FIRES[0][1][1], False, 1),
                           (L.FIRES[1][1][0], L.FIRES[1][1][1], False, 2),
                           (L.FIRES[6][1][0], L.FIRES[6][1][1], False, 3),
                           (-9.4, -5.0, True, 4), (8.0, 11.4, True, 5)):
        fire_barrel(scn, x, y, seed=s, tipped=tip)
    # debris fires (MK_FIRE_5 / 6) get a pile of burning timber to sit in
    for (fx, fy) in (L.FIRES[4][1][:2], L.FIRES[5][1][:2]):
        for i in range(7):
            a = rnd.uniform(0, 6.3)
            scn.box('charred', (fx + rnd.uniform(-0.5, 0.5), fy + rnd.uniform(-0.5, 0.5),
                                rnd.uniform(0.06, 0.34)),
                    (rnd.uniform(0.7, 1.5), rnd.uniform(0.1, 0.2), 0.09),
                    rot=(rnd.uniform(-0.6, 0.6), rnd.uniform(-0.4, 0.4), a))
    dead_tree(scn, -10.1, -9.5, 4.8, seed=1)
    dead_tree(scn, 10.2, -13.5, 4.2, seed=2)
    dead_tree(scn, -10.4, 10.6, 3.9, seed=3)
    sign_doom_town(scn, 0.0, -20.0, 0.0)

    # rubble, planks, tyres — dense at the edges, sparser on the carriageway
    for i in range(130):
        x = rnd.uniform(-SX + 0.5, SX - 0.5)
        y = rnd.uniform(L.STREET_Y_S + 0.5, L.STREET_Y_N - 0.6)
        on_road = (x * x + (y - 2.0) ** 2 < 58) or (abs(x) < 4.8 and y < 2.0)
        if on_road and rnd.random() < 0.62:
            continue
        r = rnd.uniform(0.09, 0.40)
        scn.rock(rnd.choice(['rubble', 'brick', 'charred', 'rubble', 'concrete']),
                 (x, y, r * 0.16), (r * 2.1, r * 2.1, r), seed=i)
    # blast debris with real volume: splintered planks, buckled sheet metal, shingle bundles,
    # stucco chunks with exposed lath, a bent bicycle wheel (environment.md #19)
    AVOID = [(0.0, 8.2, 2.4), (-2.3, -12.6, 5.0), (5.4, 8.2, 2.8), (-8.4, 5.6, 2.8),
             (8.6, -15.4, 2.8), (8.8, -1.2, 2.8), (0.0, -20.0, 2.0)]
    CL.debris_field(scn, 54, (-SX + 0.8, L.STREET_Y_S + 1.0, SX - 0.8, L.STREET_Y_N - 1.2),
                    avoid=AVOID, seed=71, blast=(-2.3, -12.6))
    for i in range(11):
        x = rnd.uniform(-SX + 1.0, SX - 1.0); y = rnd.uniform(-19, 11)
        if abs(x) < 4.0:
            continue
        scn.cyl('rubber', (x, y, 0.11), 0.36, 0.22, 14, r2=0.36,
                rot=(rnd.uniform(0, 0.3), 0, rnd.uniform(0, 3)))
    # loose bricks from the chimneys, stacked crates
    for (cx, cy) in ((-7.2, -3.4), (6.8, 6.2), (-3.4, 9.4)):
        for i in range(9):
            scn.box('brick', (cx + rnd.uniform(-0.7, 0.7), cy + rnd.uniform(-0.7, 0.7),
                              rnd.uniform(0.04, 0.26)), (0.22, 0.11, 0.08),
                    rot=(0, rnd.uniform(-0.2, 0.2), rnd.uniform(0, 3.14)))
    for (cx, cy, n) in ((-9.6, -17.4, 3), (9.4, 3.2, 2)):
        for i in range(n):
            scn.box('wood_bare', (cx + rnd.uniform(-0.1, 0.1), cy + rnd.uniform(-0.1, 0.1),
                                  0.22 + i * 0.44), (0.82, 0.62, 0.44),
                    rot=(0, 0, rnd.uniform(-0.3, 0.3)))
        scn.col_obj('COL_PROP', (cx, cy, 0.44 * n / 2), (0.9, 0.8, 0.44 * n))
    # sandbag wall near the bunker entrance
    for row in range(3):
        for i in range(7):
            scn.box('fabric_weave_o', (-5.6 + i * 0.52 + (row % 2) * 0.26, 10.2, 0.13 + row * 0.24),
                    (0.5, 0.3, 0.24), rot=(0, 0, rnd.uniform(-0.08, 0.08)))
    scn.col_obj('COL_SANDBAG', (-4.0, 10.2, 0.4), (4.0, 0.42, 0.8))


def clutter(scn):
    """Lived-in density, weighted towards the road in front of the spawn."""
    rnd = random.Random(404)
    CL.skid_marks(scn, [(2.2, 6.4, -0.9, -2.2), (-2.9, 4.6, -4.2, -3.4),
                        (4.6, -2.0, 1.4, -8.4), (-4.2, -9.0, -2.0, -14.0)], seed=2, z=0.028)
    CL.bin_can(scn, 2.45, 3.70, yaw=0.7, tipped=True, lid=False, seed=1)
    CL.bin_can(scn, -3.95, 6.15, yaw=-0.4, seed=2)
    CL.bin_can(scn, 7.15, -6.30, yaw=1.2, seed=3)
    CL.bin_can(scn, -7.70, 2.10, yaw=0.2, tipped=True, seed=4)
    CL.tricycle(scn, -1.70, 1.35, yaw=1.9)
    CL.tricycle(scn, 6.35, 3.30, yaw=-0.6, toppled=False)
    CL.suitcase(scn, 2.95, -1.35, yaw=0.5, open_=True, seed=5)
    CL.suitcase(scn, -6.20, -12.40, yaw=2.2, seed=6)
    CL.newspapers(scn, 0.60, 4.30, 2.3, 16, seed=7)
    CL.newspapers(scn, -2.60, -3.10, 1.9, 12, seed=8)
    CL.newspapers(scn, 3.70, -6.60, 2.0, 12, seed=9)
    CL.newspapers(scn, -8.40, 8.20, 1.8, 10, seed=10)
    CL.newspapers(scn, 8.10, 1.10, 1.7, 10, seed=11)
    CL.pallet(scn, -4.65, 0.25, yaw=0.45)
    CL.pallet(scn, 5.10, 5.60, yaw=-0.8, lean=0.05)
    CL.pallet(scn, -9.30, -14.60, yaw=1.2)
    CL.chainlink_panel(scn, 4.30, 1.70, yaw=0.9)
    CL.chainlink_panel(scn, -6.80, -6.20, yaw=-0.5)
    CL.tyre_pile(scn, -8.90, -2.20, n=5, seed=12)
    CL.tyre_pile(scn, 9.40, -12.60, n=4, seed=13)
    CL.hydrant(scn, -8.35, -7.40, yaw=0.3)
    # toppled mailbox and a snapped street sign lying in the road
    scn.cyl('wood_bare', (7.6, -5.6, 0.07), 0.055, 1.05, 8, axis='x', rot=(0, 0, 0.7))
    scn.box('metal_rust', (7.0, -5.1, 0.12), (0.44, 0.22, 0.20), rot=(0, 0.3, 0.7))
    scn.cyl('metal_dark', (-1.1, -7.9, 0.06), 0.045, 2.6, 8, axis='x', rot=(0, 0, 1.15))
    scn.box('sign_paint', (-0.1, -6.8, 0.07), (0.70, 0.16, 0.05), rot=(0, 0, 1.15))
    # more sandbags flanking the bunker approach
    for row in range(3):
        for i in range(6):
            scn.box('fabric_weave_o', (3.1 + i * 0.52 + (row % 2) * 0.26, 10.4, 0.13 + row * 0.24),
                    (0.5, 0.3, 0.24), rot=(0, 0, rnd.uniform(-0.08, 0.08)))
    scn.col_obj('COL_SANDBAG', (4.7, 10.4, 0.4), (3.6, 0.42, 0.8))
    # crates, bottles, cans and loose brick scattered along the kerbs
    for (cx, cy, n) in ((-10.2, 1.4, 3), (8.8, 7.2, 2), (-8.2, -18.0, 3), (9.6, -7.2, 2)):
        for i in range(n):
            scn.box('wood_bare', (cx + rnd.uniform(-0.15, 0.15), cy + rnd.uniform(-0.15, 0.15),
                                  0.21 + i * 0.42), (0.78, 0.58, 0.42),
                    rot=(0, 0, rnd.uniform(-0.4, 0.4)))
        scn.col_obj('COL_PROP', (cx, cy, 0.21 * n), (0.9, 0.7, 0.42 * n))
    for i in range(64):
        x = rnd.uniform(-10.4, 10.4)
        y = rnd.uniform(-19.5, 12.0)
        if abs(x) < 1.2 and 6.0 < y < 12.0:
            continue
        scn.cyl(rnd.choice(['metal_rust', 'glass', 'paint_cream']),
                (x, y, 0.045), rnd.uniform(0.028, 0.045), rnd.uniform(0.10, 0.18), 8,
                axis='x', rot=(0, 0, rnd.uniform(0, 3.14)))
    CL.debris_field(scn, 34, (-10.6, -19.5, 10.6, 12.2),
                    avoid=[(0.0, 8.2, 2.2), (-2.3, -12.6, 4.8), (5.4, 8.2, 2.6),
                           (-8.4, 5.6, 2.6), (8.6, -15.4, 2.6), (8.8, -1.2, 2.6)],
                    seed=73, blast=(0.0, -18.4), scale=0.75)
    # road grime: oil under every wreck, scorch under every fire, cracking in the carriageway
    # and along the kerb (environment.md #8)
    for (ox, oy, osz) in ((-2.3, -12.6, 3.4), (5.4, 8.2, 2.6), (-8.4, 5.6, 2.6),
                          (8.6, -15.4, 2.6), (8.8, -1.2, 2.6)):
        scn.decal('oil', (ox, oy, surf_z(ox, oy)), (osz, osz * 0.8), (0, 0, 1),
                  rot=rnd.uniform(0, 3.1), lift=0.005)
    for (fx, fy, _z) in [f[1] for f in L.FIRES]:
        scn.decal('scorch', (fx, fy, max(surf_z(fx, fy), 0.020)), (2.6, 2.6), (0, 0, 1),
                  rot=rnd.uniform(0, 3.1), lift=0.004)
    for (cx, cy, cs) in ((-3.4, -4.6, 3.0), (4.2, -8.8, 3.4), (-3.0, 3.6, 3.2),
                         (6.9, 2.2, 2.8), (1.2, -16.0, 3.0),
                         (-5.9, -9.4, 2.2), (-8.9, 2.0, 2.2), (5.9, -4.6, 2.2),
                         (7.7, 6.45, 2.0), (-5.9, -19.2, 2.4), (5.9, -19.0, 2.2)):
        scn.decal('crack', (cx, cy, surf_z(cx, cy)), (cs, cs), (0, 0, 1),
                  rot=rnd.uniform(0, 3.1), lift=0.004)
    for (cx, cy, cs) in ((-6.3, -13.0, 1.6), (6.3, -6.0, 1.5), (-8.4, 5.4, 1.5)):
        scn.decal('grime', (cx, cy, surf_z(cx, cy)), (cs * 2, cs), (0, 0, 1),
                  rot=rnd.uniform(0, 3.1), lift=0.003)


def build(scn):
    ground(scn)
    boundary(scn)
    dressing(scn)
    clutter(scn)
