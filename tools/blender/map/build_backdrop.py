"""Doom Town — everything outside the playable area: side/back yards, ruined neighbours,
power lines, the desert plain and distant mesas. All of it goes into BG_* meshes."""
import math, random, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout as L  # noqa: E402
import build_props as P  # noqa: E402
from build_street import picket_fence, power_pole, wire, dead_tree  # noqa: E402


def ruined_house(scn, x, y, yaw, w=10.0, d=8.5, h=2.9, sid='siding_white', seed=0, ruin=0.5):
    """A neighbour house seen over the fence: gable roof with overhangs, corner boards,
    framed windows, a porch with rails and steps, chimney, garage -- or a burnt shell."""
    rnd = random.Random(seed)
    c, s = math.cos(yaw), math.sin(yaw)
    trim = rnd.choice(['wood_white', 'wood_trim_y', 'wood_trim_g'])
    burnt = rnd.random() < ruin * 0.5
    if burnt:
        sid, trim = 'charred', 'charred'

    def b(dx, dy, dz, sx, sy, sz, m, rot=(0, 0, 0)):
        scn.box(m, (x + dx * c - dy * s, y + dx * s + dy * c, dz), (sx, sy, sz),
                rot=(rot[0], rot[1], yaw + rot[2]), bg=True)

    two = rnd.random() < 0.4
    top = h * (2.02 if two else 1.0)
    collapsed = burnt or rnd.random() < ruin * 0.45
    # foundation + walls
    b(0, 0, 0.14, w + 0.55, d + 0.55, 0.46, 'concrete')
    wall_h = []
    for (dx, dy, sx, sy) in ((0, d / 2, w, 0.22), (0, -d / 2, w, 0.22),
                             (w / 2, 0, 0.22, d), (-w / 2, 0, 0.22, d)):
        hh = top * (rnd.uniform(0.42, 0.85) if (collapsed and rnd.random() < 0.55) else 1.0)
        wall_h.append(hh)
        b(dx, dy, hh / 2 + 0.30, sx, sy, hh, sid)
        b(dx, dy, hh + 0.34, sx + 0.12, sy + 0.12, 0.12, trim)
        if burnt and hh < top * 0.95:
            for k in range(6):
                t = -0.4 + k * 0.16
                b(dx + (sx > sy) * t * w, dy + (sy > sx) * t * d, hh + 0.55,
                  0.09, 0.09, rnd.uniform(0.25, 0.75), 'charred')
    # corner boards
    for (dx, dy) in ((w / 2, d / 2), (w / 2, -d / 2), (-w / 2, d / 2), (-w / 2, -d / 2)):
        b(dx, dy, top / 2 + 0.30, 0.20, 0.20, top, trim)
    # windows with frames and sills
    rows = 2 if two else 1
    for r in range(rows):
        zz = 1.70 + r * h
        for i in range(3):
            for sgn in (-1, 1):
                if rnd.random() < 0.18:
                    continue
                dx = -w / 2 + (i + 1) * w / 4
                b(dx, sgn * (d / 2 + 0.03), zz, 1.00, 0.08, 1.08, 'glass_dark')
                b(dx, sgn * (d / 2 + 0.07), zz, 1.20, 0.07, 1.28, trim)
                b(dx, sgn * (d / 2 + 0.09), zz - 0.70, 1.34, 0.12, 0.08, trim)
        for i in range(2):
            for sgn in (-1, 1):
                dy = -d / 2 + (i + 1) * d / 3
                b(sgn * (w / 2 + 0.03), dy, zz, 0.08, 0.95, 1.05, 'glass_dark')
                b(sgn * (w / 2 + 0.07), dy, zz, 0.07, 1.14, 1.24, trim)
    # front door + porch
    b(w * 0.08, -(d / 2 + 0.05), 1.42, 0.98, 0.10, 2.10, trim)
    b(w * 0.08, -(d / 2 - 0.10), 1.42, 1.20, 0.10, 2.34, trim)
    if rnd.random() < 0.72:
        b(w * 0.08, -(d / 2 + 0.95), 0.32, 2.9, 2.0, 0.28, 'concrete')
        for st in range(2):
            b(w * 0.08, -(d / 2 + 1.98 + st * 0.30), 0.10 + st * 0.0, 2.2 - st * 0.3,
              0.30, 0.20 - st * 0.08, 'concrete')
        for k in (-1, 1):
            b(w * 0.08 + k * 1.28, -(d / 2 + 1.82), 1.58, 0.15, 0.15, 2.5, trim)
            b(w * 0.08 + k * 1.28, -(d / 2 + 1.0), 0.86, 0.10, 1.7, 0.09, trim)
            b(w * 0.08 + k * 1.28, -(d / 2 + 1.0), 0.54, 0.10, 1.7, 0.09, trim)
            for j in range(5):
                b(w * 0.08 + k * 1.28, -(d / 2 + 0.3 - j * 0.35), 0.66, 0.06, 0.06, 0.55, trim)
        b(w * 0.08, -(d / 2 + 1.0), 2.86, 3.2, 2.2, 0.16, trim)
        b(w * 0.08, -(d / 2 + 1.05), 3.02, 3.3, 2.3, 0.14, 'shingle', rot=(0.17, 0, 0))
    # roof -- three archetypes so the skyline is not one silhouette repeated (environment.md #27)
    kind = rnd.choice(('gable', 'gable', 'hip', 'shed'))
    if not collapsed:
        pitch = rnd.uniform(0.34, 0.54)
        half = w / 2 + 0.55
        rise = (w / 2) * math.tan(pitch)
        ln = math.hypot(half, rise)
        if kind == 'shed':
            pitch *= 0.62
            rise = w * math.tan(pitch)
            b(0, 0, top + 0.36 + rise / 2, math.hypot(w + 1.1, rise), d + 1.1, 0.17, 'shingle',
              rot=(0, -pitch, 0))
            b(0, 0, top + 0.30, w + 1.2, d + 1.2, 0.14, trim)
            for sgn in (-1, 1):
                for i in range(5):
                    b(0, sgn * (d / 2 - 0.02), top + 0.36 + rise * (i + 0.5) / 5.0, w, 0.20,
                      rise / 5.0 + 0.01, sid)
        else:
            hipin = (d * 0.30) if kind == 'hip' else 0.0
            for sgn in (-1, 1):
                b(sgn * (half / 2), 0, top + 0.36 + rise / 2, ln, d + 1.1 - 2 * hipin, 0.17,
                  'shingle', rot=(0, -sgn * pitch, 0))
                b(sgn * (w / 2 + 0.52), 0, top + 0.26, 0.09, d + 1.1 - 2 * hipin, 0.32, trim)
                for yy in (-(d / 2 + 0.5 - hipin), d / 2 + 0.5 - hipin):
                    # 0.16 not 0.10: at 0.10 the board's outer face landed exactly on the roof
                    # slab's gable edge and the two z-fought
                    b(sgn * (half / 2), yy, top + 0.46 + rise / 2, ln, 0.16, 0.22, trim,
                      rot=(0, -sgn * pitch, 0))
            b(0, 0, top + 0.44 + rise, 0.46, d + 1.1 - 2 * hipin, 0.16, 'shingle')
            if kind == 'hip':
                epitch = math.atan2(rise, d / 2)
                eln = math.hypot(d / 2 + 0.55, rise)
                for sgn in (-1, 1):
                    b(0, sgn * (d / 4 + 0.28), top + 0.36 + rise / 2, w + 1.1, eln, 0.17,
                      'shingle', rot=(sgn * epitch, 0, 0))
            else:
                for sgn in (-1, 1):
                    for i in range(6):
                        ww = w * (1 - i / 6.0)
                        b(0, sgn * (d / 2 - 0.02), top + 0.36 + rise * (i + 0.5) / 6.0, ww, 0.20,
                          rise / 6.0 + 0.01, sid)
        if rnd.random() < 0.5:
            for i in range(8):
                b(rnd.uniform(-w / 2, w / 2), rnd.uniform(-d / 2, d / 2),
                  top + 0.44 + rise * rnd.uniform(0.2, 0.9), rnd.uniform(0.8, 1.8),
                  rnd.uniform(0.6, 1.4), 0.15, 'charred',
                  rot=(0, -rnd.choice([-1, 1]) * pitch, 0))
    else:
        # exposed rafters and a caved-in roof
        pitch = rnd.uniform(0.36, 0.5)
        for i in range(9):
            yy = -d / 2 + (i + 0.5) * d / 9.0
            for sgn in (-1, 1):
                if rnd.random() < 0.4:
                    continue
                ln = (w / 2) / math.cos(pitch)
                b(sgn * (w / 4), yy, top * 0.92 + (w / 4) * math.tan(pitch), ln, 0.10, 0.14,
                  'charred', rot=(0, -sgn * pitch, 0))
        for i in range(14):
            b(rnd.uniform(-w / 2, w / 2), rnd.uniform(-d / 2, d / 2),
              top * 0.5 + rnd.uniform(-0.5, 0.6), rnd.uniform(1.0, 3.2),
              rnd.uniform(0.15, 0.5), 0.12, rnd.choice(['wood_bare', 'charred']),
              rot=(rnd.uniform(-0.7, 0.7), rnd.uniform(-0.7, 0.7), rnd.uniform(0, 3)))
        for i in range(12):
            scn.rock(rnd.choice(['plaster', 'brick', 'rubble']),
                     (x + rnd.uniform(-w / 2, w / 2) * c - rnd.uniform(-d / 2, d / 2) * s,
                      y + rnd.uniform(-w / 2, w / 2) * s + rnd.uniform(-d / 2, d / 2) * c,
                      rnd.uniform(0.15, 0.7)), (rnd.uniform(0.5, 1.6),) * 3,
                     seed=seed * 13 + i, bg=True)
    # chimney
    if rnd.random() < 0.75:
        cz = top + 1.8
        b(w * 0.28, d * 0.22, cz / 2, 0.85, 0.85, cz, 'brick')
        b(w * 0.28, d * 0.22, cz + 0.14, 1.02, 1.02, 0.24, 'brick')
    # garage wing
    if rnd.random() < 0.5:
        gw, gd = 4.4, 5.2
        b(-(w / 2 + gw / 2 + 0.1), d * 0.08, 1.52, gw, gd, 2.6, sid)
        b(-(w / 2 + gw / 2 + 0.1), d * 0.08, 2.92, gw + 0.6, gd + 0.6, 0.20, 'shingle',
          rot=(0, 0.22, 0))
        b(-(w / 2 + gw / 2 + 0.1), -(d * 0.08 + gd / 2), 1.30, gw - 0.8, 0.12, 2.1,
          'charred' if burnt else 'wood_white')


def mesa(scn, x, y, r, h, seed=0):
    rnd = random.Random(seed)
    bm = scn.bm('desert_far', bg=True)
    n = 11
    base, top = [], []
    for i in range(n):
        a = 2 * math.pi * i / n
        j = 1.0 + rnd.uniform(-0.2, 0.2)
        base.append(bm.verts.new((x + r * j * math.cos(a), y + r * j * math.sin(a), -2.0)))
        k = rnd.uniform(0.34, 0.55)
        top.append(bm.verts.new((x + r * j * k * math.cos(a), y + r * j * k * math.sin(a),
                                 h * rnd.uniform(0.93, 1.0))))
    for i in range(n):
        jj = (i + 1) % n
        bm.faces.new((base[i], base[jj], top[jj], top[i]))
    bm.faces.new(list(reversed(top)))


def windmill(scn, x, y, h=9.0, seed=0):
    """Farm windmill: a splayed lattice tower with a fan and a vane -- a silhouette accent."""
    rnd = random.Random(seed)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        sx, sy = math.cos(a), math.sin(a)
        scn.cyl('metal_rust', (x + sx * 0.75, y + sy * 0.75, h / 2), 0.055, h * 1.02, 5,
                rot=(-sy * 0.115, sx * 0.115, 0), bg=True)
    for i in range(5):
        z = 0.9 + i * (h - 1.6) / 4.0
        r = 1.5 * (1.0 - z / (h * 1.35))
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            b2 = a + math.pi / 2
            scn.cyl('metal_rust', (x + (math.cos(a) + math.cos(b2)) * r / 2,
                                   y + (math.sin(a) + math.sin(b2)) * r / 2, z),
                    0.022, r * 1.45, 4, axis='x',
                    rot=(0, 0, math.atan2(math.sin(b2) - math.sin(a), math.cos(b2) - math.cos(a))),
                    bg=True)
    scn.cyl('metal_dark', (x, y, h + 0.15), 0.16, 0.5, 8, axis='x', bg=True)
    for k in range(14):
        a = 2 * math.pi * k / 14 + rnd.uniform(-0.04, 0.04)
        scn.box('metal_rust', (x + 0.02, y + math.cos(a) * 0.82, h + 0.15 + math.sin(a) * 0.82),
                (0.03, 0.30, 0.86), rot=(a, 0.22, 0), bg=True)
    scn.box('metal_rust', (x - 1.15, y, h + 0.55), (1.5, 0.03, 0.75), bg=True)


def billboard(scn, x, y, yaw, w=7.0, h=3.2, z=4.6, lean=0.07):
    """A leaning roadside hoarding: posts, frame, torn paper."""
    c, s = math.cos(yaw), math.sin(yaw)
    for k in (-1, 1):
        scn.cyl('wood_bare', (x + k * (w / 2 - 0.6) * c, y + k * (w / 2 - 0.6) * s, z / 2 + 0.2),
                0.16, z + 0.4, 8, rot=(s * lean, -c * lean, 0), bg=True)
    scn.box('wood_bare', (x, y, z + h / 2), (w, 0.18, h), rot=(s * lean, -c * lean, yaw), bg=True)
    scn.box('plaster', (x - s * 0.12, y + c * 0.12, z + h / 2), (w - 0.5, 0.06, h - 0.45),
            rot=(s * lean, -c * lean, yaw), bg=True)
    scn.box('paint_red', (x - s * 0.15, y + c * 0.15, z + h - 0.55), (w - 1.0, 0.05, 0.55),
            rot=(s * lean, -c * lean, yaw), bg=True)
    for k in range(3):
        scn.box('charred', (x - s * 0.16 + c * (-1.8 + k * 1.8),
                            y + c * 0.16 + s * (-1.8 + k * 1.8), z + h / 2 - 0.35),
                (1.3, 0.04, 0.22), rot=(s * lean, -c * lean, yaw), bg=True)
    for k in (-1, 1):
        scn.box('wood_bare', (x + k * (w / 2 - 0.6) * c, y + k * (w / 2 - 0.6) * s, z - 0.9),
                (2.4, 0.10, 0.10), rot=(0, 0.9 * k, yaw), bg=True)


def landmarks(scn):
    """Silhouette accents on the horizon: windmills, hoardings, a grain silo."""
    windmill(scn, -24.0, 33.0, 9.4, seed=1)
    windmill(scn, 41.0, -34.0, 8.2, seed=2)
    billboard(scn, 21.0, -33.0, math.radians(-104), 7.4, 3.2, 4.4)
    billboard(scn, -26.0, -48.0, math.radians(78), 6.6, 2.9, 4.0, lean=-0.05)
    for (sx_, sy_, r, hh) in ((-58.0, -8.0, 3.0, 13.0), (-52.5, -8.0, 2.4, 10.0)):
        scn.cyl('concrete', (sx_, sy_, hh / 2), r, hh, 14, bg=True)
        scn.cyl('metal_rust', (sx_, sy_, hh + 0.7), r * 1.05, 1.5, 14, r2=r * 0.25, bg=True)
    scn.box('metal_rust', (-55.2, -12.4, 3.0), (9.0, 6.0, 6.0), bg=True)
    scn.box('metal_rust', (-55.2, -12.4, 6.3), (9.6, 6.6, 0.4), rot=(0.1, 0, 0), bg=True)


def build(scn):
    rnd = random.Random(99)
    # ---- desert plain (a ring around the built area so it never z-fights the dirt slabs)
    # NOTE: the north quad is split around the buried bunker / service tunnel so the plain
    # never passes through them (x -10..10, y 16.4..35.2 stays empty).
    for (x0, y0, x1, y1) in ((-420, -420, 420, -28.0),
                             (-420, 16.4, -10.0, 420), (10.0, 16.4, 420, 420),
                             (-10.0, 35.2, 10.0, 420),
                             (-420, -28.0, -32.1, 16.4), (32.1, -28.0, 420, 16.4)):
        scn.box_mm('desert', (x0, y0, -1.2), (x1, y1, -0.02), bg=True)
    # blend strip under the built area (kept clear of the bunker ramp cut)
    scn.box_mm('desert', (-32.1, -28.0, -1.2), (32.1, 6.4, -0.55), bg=True)
    for (x0, x1) in ((-32.1, -2.1), (2.1, 32.1)):
        scn.box_mm('desert', (x0, 6.4, -1.2), (x1, 16.4, -0.55), bg=True)

    # ---- beyond the two back yards. The yards themselves are playable now and are built for
    # real in build_yards.py (fences, collision, dressing); out here we only keep the next lot
    # along so the skyline over the fence is not empty.
    for sgn in (-1, 1):
        picket_fence(scn, (sgn * 34.5, -15.0), (sgn * 34.5, 15.0), 1.15, seed=300 + sgn, bg=True)
        dead_tree(scn, sgn * 33.0, sgn * 9.5, 5.2, seed=330 + sgn, bg=True)
        for i in range(5):
            scn.rock('concrete', (sgn * 32.5 + rnd.uniform(-1.5, 2.5), rnd.uniform(-12, 12), 0.1),
                     (rnd.uniform(0.3, 0.9),) * 3, seed=340 + i + sgn, bg=True)

    # ---- the rest of the neighbourhood
    houses = [(-34.0, -24.0, 0.15, 11.0, 9.0, 'siding_white', 1, 0.7),
              (-36.0, 4.0, -0.1, 10.0, 8.5, 'siding_green', 2, 0.35),
              (-33.0, 24.0, 0.05, 12.0, 9.0, 'siding_yellow', 3, 0.8),
              (34.0, -22.0, -0.2, 11.0, 9.0, 'siding_yellow', 4, 0.5),
              (36.0, 6.0, 0.12, 10.5, 8.0, 'siding_white', 5, 0.75),
              (33.0, 26.0, 0.0, 11.5, 9.0, 'siding_green', 6, 0.4),
              (-14.0, -40.0, 1.6, 12.0, 9.0, 'siding_white', 7, 0.6),
              (12.0, -42.0, 1.5, 11.0, 9.0, 'siding_green', 8, 0.85),
              (-44.0, -46.0, 0.6, 12.0, 9.0, 'siding_yellow', 9, 0.9),
              (46.0, -44.0, -0.5, 12.0, 9.0, 'siding_white', 10, 0.55),
              (-52.0, 20.0, 0.3, 11.0, 9.0, 'siding_green', 11, 0.65),
              (54.0, 22.0, 0.2, 11.0, 9.0, 'siding_yellow', 12, 0.7)]
    for i, (hx, hy, yaw, w, d, sid, sd, ru) in enumerate(houses):
        ruined_house(scn, hx, hy, yaw, w, d, (2.6, 2.9, 3.25)[i % 3], sid, sd, ru)
    landmarks(scn)

    # ---- road continuing south, with wrecks
    scn.box_mm('asphalt', (-5.2, -120.0, -0.3), (5.2, -22.6, 0.011), bg=True)
    P.sedan(scn, -2.6, -30.0, math.radians(75), 'paint_teal', seed=21, burnt=True, bg=True)
    P.sedan(scn, 3.0, -44.0, math.radians(-100), 'paint_cream', seed=22, bg=True)
    P.pickup(scn, -3.4, -58.0, math.radians(20), 'paint_red', seed=23, bg=True)

    # ---- power lines marching away
    for i in range(9):
        y = -26.0 - i * 13.0
        power_pole(scn, 14.5, y, 8.5, seed=500 + i, bg=True)
        if i:
            wire(scn, (14.5, y + 13.0, 7.9), (14.5, y, 7.9), sag=1.6, bg=True)
            wire(scn, (14.5, y + 13.0, 7.05), (14.5, y, 7.05), sag=1.8, bg=True)
    for i in range(6):
        x = 18.0 + i * 15.0
        power_pole(scn, x, 20.0, 8.5, seed=560 + i, bg=True)
        if i:
            wire(scn, (x - 15.0, 20.0, 7.9), (x, 20.0, 7.9), sag=1.8, bg=True)

    # ---- water tower
    tx, ty = -46.0, 40.0
    for a in (0.5, 2.1, 3.7, 5.3):
        scn.cyl('metal_rust', (tx + 3.2 * math.cos(a), ty + 3.2 * math.sin(a), 6.0), 0.18, 12.4, 6,
                rot=(0.14 * math.sin(a), -0.14 * math.cos(a), 0), bg=True)
    scn.cyl('metal_rust', (tx, ty, 14.0), 3.6, 5.2, 14, bg=True)
    scn.cyl('metal_rust', (tx, ty, 17.2), 3.7, 1.4, 14, r2=0.5, bg=True)

    # ---- dead trees and scrub scattered over the plain
    for i in range(18):
        a = rnd.uniform(0, 6.283)
        d = rnd.uniform(40, 220)
        dead_tree(scn, math.cos(a) * d, math.sin(a) * d * 0.8, rnd.uniform(3.0, 6.0), seed=700 + i, bg=True)
    for i in range(95):
        a = rnd.uniform(0, 6.283); d = rnd.uniform(48, 320)
        s = rnd.uniform(0.6, 2.6)
        scn.rock('desert', (math.cos(a) * d, math.sin(a) * d * 0.85, s * 0.2), (s * 2.4, s * 2.4, s),
                 seed=800 + i, bg=True)

    # ---- distant mesas
    for i in range(16):
        a = rnd.uniform(0, 6.283)
        d = rnd.uniform(600, 1600)
        mesa(scn, math.cos(a) * d, math.sin(a) * d, rnd.uniform(90, 300), rnd.uniform(35, 120),
             seed=900 + i)
    mesa(scn, -420, 1150, 420, 190, seed=950)
    mesa(scn, 700, 1400, 520, 240, seed=951)
