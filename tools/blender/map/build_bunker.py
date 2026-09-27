"""Doom Town — the fallout shelter: earth mound, concrete headhouse, open ramp cut, bunker room
and the sealed service tunnel behind the bunker's barrier window."""
import math, random, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout as L  # noqa: E402
import lib_clutter as CL  # noqa: E402
from lib_sign import sign_text  # noqa: E402

BZ = L.BUNK_Z
BX = L.BUNK_X
BY0, BY1 = L.BUNK_Y0, L.BUNK_Y1
CEIL = L.BUNK_CEIL
CT = 0.30                       # concrete wall thickness
COR = L.COR_X


def op(a0, a1, z0, z1, kind='window', oid=None):
    return dict(a0=a0, a1=a1, z0=z0, z1=z1, kind=kind, id=oid)


# --------------------------------------------------------------------------- mound
def mound(scn):
    notch = 1.95
    outer = [(-16.5, L.BERM_Y0), (-notch, L.BERM_Y0), (-notch, 17.3), (notch, 17.3),
             (notch, L.BERM_Y0), (16.5, L.BERM_Y0), (16.5, L.BERM_Y1), (-16.5, L.BERM_Y1)]
    inner = [(-14.0, 15.6), (-4.6, 15.6), (-4.6, 17.3), (4.6, 17.3),
             (4.6, 15.6), (14.0, 15.6), (14.0, L.BERM_Y1 - 2.6), (-14.0, L.BERM_Y1 - 2.6)]
    bm = scn.bm('dirt')
    vo = [bm.verts.new((p[0], p[1], -0.05)) for p in outer]
    vi = [bm.verts.new((p[0], p[1], L.BERM_TOP)) for p in inner]
    n = len(outer)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vo[i], vo[j], vi[j], vi[i]))
    # top face as three rectangles: a concave n-gon here would tessellate over the ramp cut
    yt = L.BERM_Y1 - 2.6
    for (x0, x1, y0_, y1_) in ((-14.0, -4.6, 15.6, yt), (4.6, 14.0, 15.6, yt),
                               (-4.6, 4.6, 17.3, yt)):
        vs = [bm.verts.new((x0, y0_, L.BERM_TOP)), bm.verts.new((x1, y0_, L.BERM_TOP)),
              bm.verts.new((x1, y1_, L.BERM_TOP)), bm.verts.new((x0, y1_, L.BERM_TOP))]
        bm.faces.new(vs)
    # retaining wall along the mound's south face so it reads as engineered, not a dune
    for (x0, x1) in ((-16.5, -notch), (notch, 16.5)):
        scn.box_mm('concrete_bunker', (x0, L.BERM_Y0 - 0.35, -0.4), (x1, L.BERM_Y0 + 0.25, 0.95))
    rnd = random.Random(31)
    for i in range(40):
        x = rnd.uniform(-15.0, 15.0)
        if abs(x) < notch + 0.6:
            continue
        scn.rock('concrete', (x, L.BERM_Y0 - rnd.uniform(0.2, 1.4), 0.08),
                 (rnd.uniform(0.2, 0.7),) * 3, seed=400 + i)
    # collision: 4 m tall wall along the mound face (street side)
    for (x0, x1) in ((-13.8, -notch), (notch, 13.8)):
        scn.col_box('COL_BERM', (x0, L.BERM_Y0 - 0.5, -0.3), (x1, L.BERM_Y0 + 0.6, 4.2))


# --------------------------------------------------------------------------- headhouse + ramp cut
def headhouse(scn):
    """Concrete blockhouse buried in the mound: a recessed blast-door portal, wing walls,
    bulkhead lights, signage and roof vents. This is what the player sees from the spawn."""
    hx, y0, y1, h = L.HH_X, L.HH_Y0, L.HH_Y1, L.HH_H
    rnd = random.Random(12)
    RE = 0.55                                    # portal recess depth
    door = [op(-1.05, 1.05, 0.0, 2.55, 'door', 'bunker_door')]
    scn.wall('concrete_bunker', 'x', y0 + RE + CT / 2, -hx, hx, 0.0, h, CT, door,
             col_top=4.4, out=-1)
    for s in (-1, 1):
        scn.wall('concrete_bunker', 'y', s * (hx - CT / 2), y0, y1, 0.0, h, CT, (),
                 col_top=4.4, out=s)
    # the recess: the front face steps forward either side of the portal
    for s in (-1, 1):
        scn.box_mm('concrete_bunker', (s * 1.55, y0, -0.4), (s * hx, y1, h))
    scn.box_mm('concrete_bunker', (-1.55, y0, 2.90), (1.55, y0 + RE + CT, h))
    # sloped hood over the portal
    scn.box('concrete_bunker', (0.0, y0 - 0.22, 2.80), (3.5, 1.10, 0.30), rot=(0.30, 0, 0))
    for s in (-1, 1):
        scn.box('concrete_bunker', (s * 1.66, y0 + 0.02, 1.9), (0.22, 0.70, 3.8), rot=(0, 0, 0))
    # inner walls of the entry chamber (corridor width)
    for s in (-1, 1):
        scn.box_mm('concrete_bunker', (s * COR, y0 + RE + CT, -0.4), (s * (hx - CT), y1, h - 0.45))
    scn.box_mm('concrete_bunker', (-hx - 0.30, y0 - 0.30, h - 0.45), (hx + 0.30, y1 + 0.2, h))
    scn.box_mm('concrete_bunker', (-hx - 0.48, y0 - 0.50, h - 0.16), (hx + 0.48, y1 + 0.2, h + 0.06))
    # wing walls flaring out into the mound
    for s in (-1, 1):
        scn.box('concrete_bunker', (s * (hx + 0.85), y0 + 1.5, 0.75), (2.0, 0.45, 1.7))
        scn.box('concrete_bunker', (s * (hx + 0.85), y0 + 1.5, 1.66), (2.1, 0.58, 0.14))
    # steel portal frame, rivets and threshold
    for (dx, dz, sx, sz) in ((0, 2.72, 2.60, 0.18), (-1.22, 1.30, 0.16, 2.92),
                             (1.22, 1.30, 0.16, 2.92)):
        scn.box('metal_rust', (dx, y0 + RE + 0.02, dz), (sx, 0.16, sz))
    for i in range(9):
        for s in (-1, 1):
            scn.cyl('metal_rust', (s * 1.22, y0 + RE - 0.06, 0.25 + i * 0.30), 0.045, 0.10, 8,
                    axis='y')
    scn.box('metal_dark', (0.0, y0 + RE + 0.06, 0.03), (2.40, 0.55, 0.07))
    # bulkhead lights either side of the portal
    for s in (-1, 1):
        scn.box('metal_dark', (s * 1.62, y0 + 0.06, 2.42), (0.24, 0.26, 0.34))
        scn.box('lamp_glow', (s * 1.62, y0 - 0.06, 2.42), (0.17, 0.10, 0.24))
        for k in range(3):
            scn.box('metal_dark', (s * 1.62, y0 - 0.09, 2.30 + k * 0.12), (0.19, 0.06, 0.03))
    # signage: stencilled steel board over the portal (real letterforms, see lib_sign)
    scn.box('metal_rust', (0.0, y0 - 0.03, 3.42), (3.46, 0.06, 0.70))
    scn.box('charred', (0.0, y0 - 0.065, 3.42), (3.24, 0.03, 0.54))
    sign_text(scn, 'paint_stencil_y', 'FALLOUT SHELTER', (0.0, y0 - 0.082, 3.42),
              (1, 0, 0), (0, 0, 1), (0, -1, 0), h=0.30, width=2.96, depth=0.006)
    # weathering on the blockhouse face: wash-down streaks off the roof slab, cracks, soot
    for s in (-1, 1):
        scn.decal('streak', (s * 3.05, y0, 2.55), (1.9, 3.1), (0, -1, 0))
        scn.decal('crack', (s * 2.45, y0, 0.95), (1.5, 1.5), (0, -1, 0))
    scn.decal('water', (-3.35, y0, 1.45), (1.3, 1.1), (0, -1, 0))
    scn.decal('soot', (2.65, y0, 1.30), (1.0, 1.8), (0, -1, 0))
    for i in range(5):
        scn.cyl('metal_rust', (-1.55 + i * 0.775, y0 - 0.085, 3.72), 0.035, 0.05, 8, axis='y')
    # the classic civil-defence fallout shelter plate on the west wing
    CL.fallout_sign(scn, (-2.62, y0 - 0.06, 1.72), (0, -1, 0), w=1.10)
    scn.box('metal_rust', (-2.62, y0 - 0.02, 1.08), (0.10, 0.06, 0.24))
    # hazard striping on the wing faces: one continuous painted band with straight edges
    # (stacked rotated boxes read as a pile of loose tilted tiles — repair round #4)
    for s in (-1, 1):
        CL.hazard_band(scn, (s * 2.35, y0 - 0.004, 1.38), (1, 0, 0), (0, 0, 1), (0, -1, 0),
                       0.34, 2.30, stripe=0.19, angle=0.62, depth=0.010)
    # roof vents and an antenna
    for (vx, vy, r) in ((-2.2, 11.4, 0.34), (2.4, 12.2, 0.28)):
        scn.cyl('metal_rust', (vx, vy, h + 0.45), r, 0.9, 12)
        scn.cyl('metal_rust', (vx, vy, h + 0.95), r * 1.3, 0.12, 12)
        scn.cyl('metal_dark', (vx, vy, h + 1.02), r * 1.15, 0.06, 12)
    scn.cyl('metal_dark', (3.1, 10.3, h + 1.7), 0.05, 3.4, 6)
    for i in range(3):
        scn.box('metal_dark', (3.1, 10.3, h + 1.0 + i * 0.7), (0.9, 0.05, 0.05))
    # sandbags at the base of the wings
    for s in (-1, 1):
        for row in range(2):
            for i in range(5):
                scn.box('fabric_weave_o',
                        (s * (2.7 + i * 0.5), y0 - 0.45, 0.13 + row * 0.24),
                        (0.48, 0.30, 0.24), rot=(0, 0, rnd.uniform(-0.1, 0.1)))
    scn.col_box('COL_HEADHOUSE', (-hx - 0.5, y0 - 0.6, -0.3), (-COR, y1 + 0.3, 4.6))
    scn.col_box('COL_HEADHOUSE', (COR, y0 - 0.6, -0.3), (hx + 0.5, y1 + 0.3, 4.6))
    for s in (-1, 1):
        a, b = sorted((s * (hx - 0.1), s * (hx + 1.95)))
        scn.col_box('COL_HEADHOUSE', (a, y0 + 1.2, -0.3), (b, y0 + 1.8, 2.0))
    # ceiling lamp in the chamber
    scn.box('metal_dark', (0.0, 12.1, 2.52), (0.36, 0.20, 0.10))
    scn.box('lamp_glow', (0.0, 12.1, 2.44), (0.28, 0.14, 0.06))


def ramp(scn):
    y0, y1 = L.RAMP_Y0, L.RAMP_Y1
    # entry landing (flat, inside the headhouse)
    scn.box_mm('concrete_floor', (-COR, L.HH_Y0, -0.45), (COR, y0, -0.005))
    # sloped floor
    dy, dz = y1 - y0, -BZ
    ln = math.hypot(dy, dz)
    pitch = math.atan2(dz, dy)
    scn.box('concrete_floor', (0.0, (y0 + y1) / 2, (0 + BZ) / 2 - 0.22), (2 * COR + 0.08, ln, 0.45),
            rot=(-pitch, 0, 0))     # +8 cm so its edges tuck into the retaining walls
    for s in (-1, 1):
        scn.box('concrete_bunker', (s * (COR + 0.175), (y0 + y1) / 2 - 0.1, -1.10),
                (0.35, dy + 0.5, 4.30))
        scn.box('concrete_bunker', (s * (COR + 0.175), (y0 + y1) / 2 - 0.1, 1.11),
                (0.52, dy + 0.5, 0.14))
        xa, xb = sorted((s * COR, s * (COR + 0.4)))
        scn.col_box('COL_RAMPWALL', (xa, y0 - 0.2, BZ - 0.5), (xb, y1 + 0.2, 1.6))
        # steel handrail down the cut
        for i in range(7):
            t = i / 6.0
            scn.cyl('steel_paint', (s * (COR - 0.12), y0 + dy * t, BZ * t + 0.55), 0.035, 1.1, 6)
        scn.cyl('steel_paint', (s * (COR - 0.12), (y0 + y1) / 2, BZ * 0.5 + 1.05), 0.045, ln, 6,
                axis='y', rot=(-pitch, 0, 0))
    # anti-slip cleats across the slope
    for i in range(18):
        t = (i + 0.5) / 18.0
        scn.box('steel_paint', (0.0, y0 + dy * t, BZ * t + 0.012), (2 * COR - 0.2, 0.09, 0.05),
                rot=(-pitch, 0, 0))
    # bulkhead lamp + conduit on the east retaining wall
    scn.box('metal_dark', (COR - 0.10, 14.4, -0.30), (0.20, 0.26, 0.34))
    scn.box('lamp_glow', (COR - 0.22, 14.4, -0.30), (0.06, 0.16, 0.24))
    scn.box('metal_dark', (COR - 0.10, 14.4, -0.03), (0.26, 0.34, 0.10))
    scn.cyl('metal_dark', (COR - 0.06, 14.9, 0.55), 0.035, 5.0, 8, axis='y', rot=(-pitch, 0, 0))
    for i in range(4):
        scn.box('metal_dark', (COR - 0.06, 12.6 + i * 1.5, 0.75 - i * 0.66), (0.10, 0.10, 0.12))
    # rusted pipes running down the cut
    for (px, r) in ((-COR + 0.14, 0.11), (-COR + 0.14, 0.07)):
        scn.cyl('steel_paint' if r > 0.1 else 'metal_rust',
                (px, (y0 + y1) / 2 + 0.3, BZ * 0.5 + 1.55 - (0.0 if r > 0.1 else 0.28)),
                r, ln + 1.2, 10, axis='y', rot=(-pitch, 0, 0))
    # wayfinding + weathering down the cut
    for s in (-1, 1):
        for k in range(4):
            t = 0.12 + k * 0.26
            scn.decal('streak', (s * (COR - 0.005), y0 + dy * t, BZ * t + 1.05),
                      (2.0, 2.4), (-s, 0, 0), lift=0.010)
        scn.decal('water', (s * (COR - 0.005), y0 + dy * 0.55, BZ * 0.55 + 1.75),
                  (1.5, 1.3), (-s, 0, 0), lift=0.012)
    for (sy, txt, sh, sw) in ((13.4, 'SHELTER', 0.16, 1.05), (16.0, 'LEVEL B', 0.14, 0.85)):
        fz = BZ * (sy - y0) / dy                       # the ramp floor at that station
        sign_text(scn, 'paint_stencil_y', txt, (-COR + 0.01, sy, fz + 1.45),
                  (0, 1, 0), (0, 0, 1), (1, 0, 0), h=sh, width=sw, depth=0.004)
    scn.col_ramp('COL_RAMP_bunker', (0, y0, 0.0), (0, y1, BZ), 2 * COR + 0.1, 0.5)
    scn.col_box('COL_FLOOR_entry', (-COR - 0.1, L.HH_Y0 - 0.2, -1.0), (COR + 0.1, y0 + 0.05, 0.0))


# --------------------------------------------------------------------------- bunker room
def room(scn):
    ceil = CEIL
    # The floor slab is cast in three pieces so the drain channel is a real hole in it: two
    # walking slabs with their inner faces forming the channel cheeks, and a sunk invert
    # CHD below the walking surface. (Repair round #1 — the old "channel" was a solid slab
    # sitting 5 mm *above* the floor with its bars buried inside it.)
    CHW, CHD = 0.22, 0.17
    for (fx0, fx1) in ((-BX - CT, -CHW), (CHW, BX + CT)):
        # top 5 mm below BZ: the crates, drums and floor stencils all start exactly at BZ and
        # were coplanar with it
        scn.box_mm('concrete_floor', (fx0, BY0 - 0.1, BZ - 0.45), (fx1, BY1 + CT, BZ - 0.005))
    scn.box_mm('concrete_floor', (-CHW, BY0 - 0.1, BZ - 0.45), (CHW, BY1 + CT, BZ - CHD))
    scn.col_box('COL_FLOOR_bunker', (-BX - 0.05, BY0 - 0.3, BZ - 1.0), (BX + 0.05, BY1 + 0.05, BZ))
    # walls
    scn.wall('concrete_bunker', 'x', BY0 + CT / 2, -BX, BX, BZ, ceil, CT,
             [op(-COR, COR, BZ, BZ + 2.35, 'open')], col_top=BZ + 3.2, out=-1)
    scn.wall('concrete_bunker', 'x', BY1 - CT / 2, -BX, BX, BZ, ceil, CT,
             [op(4.9, 6.1, BZ + L.BARRIER_SILL, BZ + L.BARRIER_SILL + L.BARRIER_H, 'barrier', 'bw1')],
             col_top=BZ + 3.2, out=1)
    for s in (-1, 1):
        scn.wall('concrete_bunker', 'y', s * (BX - CT / 2), BY0, BY1, BZ, ceil, CT, (),
                 col_top=BZ + 3.2, out=s)
    scn.col_box('COL_BARRIER_bw1', (4.9, BY1 - CT, BZ + L.BARRIER_SILL),
                (6.1, BY1, BZ + L.BARRIER_SILL + L.BARRIER_H))
    # ceiling slab + beams
    scn.box_mm('concrete_floor', (-BX - CT, BY0, ceil), (BX + CT, BY1, ceil + 0.35))
    for i in range(7):
        y = BY0 + 0.9 + i * 1.65
        scn.box('concrete_bunker', (0, y, ceil - 0.14), (2 * BX - 2 * CT, 0.34, 0.28))
    # steel sill / frame around the barrier window
    for (dx, dz, sx, sz) in ((0, L.BARRIER_H / 2 + 0.06, 1.44, 0.12), (0, -L.BARRIER_H / 2 - 0.06, 1.44, 0.12),
                             (-0.66, 0, 0.12, L.BARRIER_H + 0.24), (0.66, 0, 0.12, L.BARRIER_H + 0.24)):
        scn.box('steel_paint', (5.5 + dx, BY1 - CT / 2, BZ + L.BARRIER_SILL + L.BARRIER_H / 2 + dz),
                (sx, CT + 0.08, sz))

    rnd = random.Random(77)
    # structural columns break the hall up (lanes stay >= 1.6 m wide)
    for cx in (-4.2, 4.2):
        for cy in (20.4, 25.2):
            scn.box('concrete_bunker', (cx, cy, BZ + 1.55), (0.62, 0.62, 3.1))
            scn.box('concrete_bunker', (cx, cy, BZ + 0.12), (0.86, 0.86, 0.24))
            scn.box('concrete_bunker', (cx, cy, ceil - 0.22), (0.86, 0.86, 0.26))
            for k in range(6):
                scn.box('paint_bus' if k % 2 == 0 else 'charred',
                        (cx, cy - 0.315, BZ + 0.42 + k * 0.16), (0.60, 0.02, 0.15), rot=(0, 0.7, 0))
            scn.col_obj('COL_COLUMN', (cx, cy, BZ + 1.5), (0.9, 0.9, 3.0))
    # safety walkway + a real recessed drain channel down the middle. (The old white parking
    # stripes and the loose rusty floor plates read as a parking garage — environment.md #18.)
    mid = (BY0 + BY1) / 2
    for sgn in (-1, 1):
        scn.box('paint_stencil_y', (sgn * 1.55, mid, BZ + 0.005), (0.085, BY1 - BY0 - 1.2, 0.010))
    # grate bars across the open channel: 6 mm below the walking surface (so they can never
    # z-fight with it) with a 12 cm dark void showing between them
    nbar = int((BY1 - BY0 - 0.9) / 0.185)
    for i in range(nbar):
        scn.box('steel_paint', (0.0, BY0 + 0.62 + i * 0.185, BZ - 0.020),
                (2 * CHW + 0.06, 0.085, 0.028))
    for i in range(6):                                   # cross ties down in the invert
        scn.box('steel_paint', (0.0, BY0 + 1.6 + i * 1.8, BZ - CHD + 0.02),
                (2 * CHW - 0.02, 0.06, 0.04))
    # hazard chevrons where the ramp lands and in front of the generator bay
    for (cx, cy, yaw) in ((0.0, BY0 + 0.62, 0.0), (-5.3, 20.55, 0.0)):
        for k in range(7):
            bx = cx - 0.9 + k * 0.30
            if abs(bx) < CHW + 0.12:                     # never bridge the open channel
                continue
            scn.box('paint_stencil_y' if k % 2 == 0 else 'paint_stencil_k',
                    (bx, cy, BZ + 0.005), (0.16, 0.9, 0.010), rot=(0, 0, 0.6 + yaw))
    # wall conduit and junction boxes
    for sgn in (-1, 1):
        x = sgn * (BX - CT - 0.06)
        scn.cyl('metal_dark', (x, (BY0 + BY1) / 2, BZ + 2.10), 0.045, BY1 - BY0 - 0.8, 8, axis='y')
        scn.cyl('metal_dark', (x, (BY0 + BY1) / 2, BZ + 1.96), 0.032, BY1 - BY0 - 0.8, 8, axis='y')
        for i in range(5):
            y = BY0 + 1.6 + i * 2.1
            scn.box('metal_dark', (x - sgn * 0.06, y, BZ + 1.62), (0.14, 0.26, 0.34))
            scn.cyl('metal_dark', (x, y, BZ + 1.85), 0.028, 0.5, 6)
    # ventilation trunk along the ceiling (painted sheet steel, rust only at the flanges)
    scn.box('steel_paint', (-2.6, (BY0 + BY1) / 2 + 0.4, ceil - 0.55), (0.62, BY1 - BY0 - 2.0, 0.46))
    for i in range(6):
        scn.box('steel_paint', (-2.6, BY0 + 1.6 + i * 1.8, ceil - 0.55), (0.70, 0.10, 0.54))
        scn.cyl('metal_dark', (-2.6, BY0 + 1.6 + i * 1.8, ceil - 0.24), 0.02, 0.4, 5)
        scn.decal('rust', (-2.288, BY0 + 1.62 + i * 1.8, ceil - 0.68), (0.34, 0.34), (1, 0, 0),
                  lift=0.006)
    scn.cyl('steel_paint', (-2.6, BY0 + 1.0, ceil - 0.55), 0.30, 0.9, 12, axis='y')
    # bunks along the west wall
    for i in range(2):
        y = 21.4 + i * 2.1
        for lvl in (0.42, 1.28):
            scn.box('metal_dark', (-BX + CT + 0.45, y, BZ + lvl), (0.84, 1.90, 0.07))
            scn.box('fabric_weave_o', (-BX + CT + 0.45, y, BZ + lvl + 0.09), (0.76, 1.80, 0.13))
        for k in (-1, 1):
            for j in (-1, 1):
                scn.cyl('metal_dark', (-BX + CT + 0.45 + k * 0.38, y + j * 0.90, BZ + 0.85),
                        0.028, 1.75, 6)
        scn.col_obj('COL_PROP', (-BX + CT + 0.45, y, BZ + 0.8), (0.9, 2.0, 1.6))
    # workbench with clutter
    scn.box('wood_bare', (2.6, BY0 + 0.95, BZ + 0.86), (2.6, 0.72, 0.08))
    for k in (-1, 1):
        scn.box('metal_dark', (2.6 + k * 1.18, BY0 + 0.95, BZ + 0.42), (0.10, 0.66, 0.84))
    scn.box('metal_rust', (2.0, BY0 + 0.95, BZ + 0.98), (0.36, 0.34, 0.16))
    scn.cyl('metal_dark', (3.4, BY0 + 0.95, BZ + 0.98), 0.14, 0.18, 10)
    scn.col_obj('COL_PROP', (2.6, BY0 + 0.95, BZ + 0.45), (2.7, 0.8, 0.9))
    # oil drums
    for (dx, dy, s) in ((6.9, 23.6, 1), (6.4, 24.3, 2), (6.95, 25.1, 3), (-6.6, 17.9, 4)):
        scn.cyl('metal_rust', (dx, dy, BZ + 0.44), 0.30, 0.88, 14, rot=(0, 0, s))
        for z in (0.24, 0.44, 0.64):
            scn.cyl('metal_rust', (dx, dy, BZ + z), 0.315, 0.05, 14)
        scn.cyl('metal_dark', (dx, dy, BZ + 0.885), 0.30, 0.03, 14)
    scn.col_obj('COL_PROP', (6.7, 24.3, BZ + 0.45), (1.3, 2.0, 0.9))
    # services: pipes along the ceiling, conduit, cable trays
    for (x, r, m) in ((-6.4, 0.14, 'steel_paint'), (-5.9, 0.09, 'metal_dark'), (6.2, 0.16, 'steel_paint')):
        scn.cyl(m, (x, (BY0 + BY1) / 2, ceil - 0.42), r, BY1 - BY0 - 0.5, 10, axis='y')
        for i in range(6):
            y = BY0 + 1.2 + i * 1.8
            scn.box('metal_dark', (x, y, ceil - 0.28), (r * 2.6, 0.08, 0.34))
    # hanging cage lamps
    for y in (19.2, 23.4, 27.0):
        scn.cyl('metal_dark', (0, y, ceil - 0.22), 0.02, 0.44, 6)
        scn.cyl('metal_dark', (0, y, ceil - 0.52), 0.16, 0.20, 10, r2=0.10)
        scn.box('lamp_glow', (0, y, ceil - 0.62), (0.16, 0.16, 0.10))
        for k in range(6):
            a = k * math.pi / 3
            scn.cyl('metal_dark', (0.14 * math.cos(a), y + 0.14 * math.sin(a), ceil - 0.58),
                    0.012, 0.22, 4)
    # ---- civil-defence signage (real stencil lettering, lib_sign)
    WX, EX = -BX + CT, BX - CT                 # inner faces of the west / east walls
    scn.box('charred', (-4.6, BY0 + CT + 0.015, BZ + 2.02), (2.15, 0.03, 0.56))
    sign_text(scn, 'paint_stencil_w', 'SHELTER CAPACITY 60', (-4.6, BY0 + CT + 0.035, BZ + 2.02),
              (-1, 0, 0), (0, 0, 1), (0, 1, 0), h=0.17, width=1.90, depth=0.004)
    scn.box('charred', (EX - 0.015, 25.6, BZ + 1.95), (0.03, 0.95, 0.95))
    CL.trefoil(scn, 'paint_stencil_y', (EX - 0.034, 25.6, BZ + 2.10), (-1, 0, 0), r=0.30, depth=0.008)
    sign_text(scn, 'paint_stencil_y', 'SHELTER', (EX - 0.034, 25.6, BZ + 1.62),
              (0, -1, 0), (0, 0, 1), (-1, 0, 0), h=0.11, width=0.80, depth=0.004)
    sign_text(scn, 'paint_stencil_w', 'NO SMOKING', (EX - 0.02, 19.0, BZ + 1.70),
              (0, -1, 0), (0, 0, 1), (-1, 0, 0), h=0.13, width=1.10, depth=0.004)
    sign_text(scn, 'paint_stencil_y', 'AIR FILTRATION', (-2.288, 20.4, CEIL - 0.55),
              (0, 1, 0), (0, 0, 1), (1, 0, 0), h=0.115, width=1.30, depth=0.003)
    sign_text(scn, 'paint_stencil_w', 'EXIT', (0.0, BY0 + CT + 0.01, BZ + 2.52),
              (-1, 0, 0), (0, 0, 1), (0, 1, 0), h=0.16, width=0.74, depth=0.004)

    # ---- shelter stores: steel shelving with ration crates, water cans and medical boxes
    for (sy, label) in ((21.35, 'RATIONS'), (23.15, 'MEDICAL')):
        x = EX - 0.24
        for lvl in range(4):
            z = BZ + 0.22 + lvl * 0.52
            scn.box('metal_dark', (x, sy, z), (0.46, 1.55, 0.035))
        for k in (-1, 1):
            for j in (-1, 1):
                scn.cyl('metal_dark', (x + k * 0.20, sy + j * 0.74, BZ + 0.86), 0.022, 1.72, 6)
        rr = random.Random(int(sy * 10))
        for lvl in range(4):
            z = BZ + 0.24 + lvl * 0.52
            for j in range(3):
                yy = sy - 0.52 + j * 0.52
                if rr.random() < 0.18:
                    continue
                if rr.random() < 0.55:
                    scn.box('wood_bare', (x, yy, z + 0.16), (0.40, 0.44, 0.30),
                            rot=(0, 0, rr.uniform(-0.08, 0.08)))
                    if lvl == 1 or lvl == 2:
                        sign_text(scn, 'paint_stencil_k', label, (x - 0.205, yy, z + 0.18),
                                  (0, -1, 0), (0, 0, 1), (-1, 0, 0), h=0.055, width=0.30,
                                  depth=0.002, kind='black')
                else:
                    for c in range(3):
                        scn.cyl('paint_green_mil', (x + rr.uniform(-0.08, 0.08), yy - 0.16 + c * 0.16,
                                                    z + 0.10), 0.075, 0.20, 10)
        scn.col_obj('COL_PROP', (x, sy, BZ + 0.9), (0.55, 1.7, 1.8))
    # first-aid cabinet
    scn.box('paint_cream', (EX - 0.11, 24.55, BZ + 1.45), (0.20, 0.52, 0.62))
    scn.box('paint_stencil_r', (EX - 0.215, 24.55, BZ + 1.45), (0.012, 0.34, 0.09))
    scn.box('paint_stencil_r', (EX - 0.215, 24.55, BZ + 1.45), (0.012, 0.09, 0.34))
    scn.col_obj('COL_PROP', (EX - 0.11, 24.55, BZ + 1.45), (0.24, 0.56, 0.66))

    # ---- water drums along the north wall, stencilled on the lid
    for i in range(4):
        dx = -3.55 + i * 0.66
        scn.cyl('paint_green_mil', (dx, BY1 - CT - 0.38, BZ + 0.44), 0.30, 0.88, 14)
        for z in (0.24, 0.64):
            scn.cyl('metal_dark', (dx, BY1 - CT - 0.38, BZ + z), 0.313, 0.045, 14)
        scn.cyl('metal_dark', (dx, BY1 - CT - 0.38, BZ + 0.885), 0.30, 0.03, 14)
        sign_text(scn, 'paint_stencil_w', 'WATER', (dx, BY1 - CT - 0.38, BZ + 0.902),
                  (1, 0, 0), (0, 1, 0), (0, 0, 1), h=0.10, width=0.42, depth=0.003)
    scn.col_obj('COL_PROP', (-2.55, BY1 - CT - 0.38, BZ + 0.45), (2.7, 0.7, 0.9))
    # blankets rolled on the bunks
    for i in range(2):
        y = 21.4 + i * 2.1
        for lvl in (0.42, 1.28):
            scn.cyl('fabric_weave_o', (-BX + CT + 0.45, y - 0.72, BZ + lvl + 0.22), 0.11, 0.70, 10,
                    axis='x')

    # lockers, crates, shelving, generator
    for i in range(4):
        x = -BX + CT + 0.32
        y = 25.2 + i * 0.66
        scn.box('paint_green_mil', (x, y, BZ + 0.95), (0.6, 0.62, 1.9))
        scn.box('metal_dark', (x - 0.31, y, BZ + 1.05), (0.03, 0.5, 1.6))
        scn.cyl('chrome', (x - 0.33, y + 0.18, BZ + 1.0), 0.02, 0.16, 6, axis='y')
    scn.col_obj('COL_PROP', (-BX + CT + 0.32, 26.2, BZ + 0.95), (0.66, 2.9, 1.9))
    for (x, y, yaw, w) in ((BX - CT - 0.45, 18.6, 0.0, 0.85), (BX - CT - 0.45, 19.6, 0.0, 0.85)):
        scn.box('wood_bare', (x, y, BZ + 0.3), (w, 0.9, 0.6))
        scn.box('wood_bare', (x, y, BZ + 0.62), (w - 0.06, 0.84, 0.05))
    scn.col_obj('COL_PROP', (BX - CT - 0.45, 19.1, BZ + 0.35), (0.9, 2.0, 0.7))
    # generator
    scn.box('paint_green_mil', (-5.3, 21.6, BZ + 0.55), (1.5, 1.0, 1.1))
    scn.box('metal_dark', (-5.3, 21.6, BZ + 1.16), (1.2, 0.8, 0.14))
    scn.cyl('metal_rust', (-5.9, 21.2, BZ + 1.55), 0.09, 0.9, 8)
    scn.cyl('metal_dark', (-4.6, 21.6, BZ + 0.6), 0.26, 0.5, 12, axis='x')
    scn.col_obj('COL_PROP', (-5.3, 21.6, BZ + 0.6), (1.6, 1.1, 1.2))
    # sandbags and clutter
    for row in range(2):
        for i in range(5):
            scn.box('fabric_weave_o', (2.4 + i * 0.52 + (row % 2) * 0.26, BY0 + 0.75, BZ + 0.13 + row * 0.24),
                    (0.5, 0.3, 0.24), rot=(0, 0, rnd.uniform(-0.08, 0.08)))
    for i in range(22):
        x = rnd.uniform(-BX + 0.9, BX - 0.9); y = rnd.uniform(BY0 + 0.8, BY1 - 0.8)
        if abs(x) < 1.6 and y < BY0 + 2.5:
            continue
        if abs(x) < 0.45:
            continue                         # keep the drain channel clear
        s = rnd.uniform(0.1, 0.32)
        # BZ + ... : without the floor offset all 22 rocks hung at ceiling height in the
        # Pack-a-Punch room (environment.md #5)
        scn.rock(rnd.choice(['concrete', 'charred', 'metal_rust']), (x, y, BZ + s * 0.25),
                 (s * 2, s * 2, s), seed=600 + i)
    # puddles
    for (x, y, r) in ((-2.6, 20.4, 1.2), (3.4, 24.6, 1.5)):
        scn.disc_slab('glass_dark', (x, y), r, BZ + 0.012, BZ - 0.02, n=14, squash=0.7)

    # ---- authored decal dressing (environment.md #8/#18): the walls were 6 x 3 m of bare
    # concrete. Water runs from the ceiling joints, rust bleeds off the pipe brackets, grime
    # collects where the floor meets the wall, and the tiling texture stops reading as tiling.
    WX2, EX2 = -BX + CT, BX - CT
    for (wx, nx) in ((WX2, (1, 0, 0)), (EX2, (-1, 0, 0))):
        for k, y in enumerate((18.4, 20.9, 23.4, 26.1, 27.7)):
            scn.decal('streak', (wx, y + (0.3 if wx > 0 else 0.0), BZ + 1.55),
                      (2.1, 2.7), nx, lift=0.010)
        for y in (19.6, 24.9):
            scn.decal('water', (wx, y, BZ + 2.05), (1.6, 1.4), nx, lift=0.012)
        for y in (21.8, 26.6):
            scn.decal('crack', (wx, y, BZ + 1.25), (2.0, 2.0), nx, lift=0.010)
        for y in (BY0 + 2.0, BY0 + 6.0, BY0 + 9.6):
            scn.decal('grime', (wx, y, BZ + 0.55), (4.0, 1.1), nx, lift=0.010, rot=math.pi)
        for y in (BY0 + 1.6, BY0 + 3.7, BY0 + 5.8, BY0 + 7.9, BY0 + 10.0):
            scn.decal('rust', (wx, y, BZ + 1.30), (0.70, 1.30), nx, lift=0.011)
    for x in (-5.4, -1.2, 3.2, 6.2):
        scn.decal('streak', (x, BY1 - CT, BZ + 1.7), (2.0, 2.5), (0, -1, 0), lift=0.010)
        scn.decal('grime', (x, BY1 - CT, BZ + 0.55), (3.6, 1.1), (0, -1, 0), lift=0.010, rot=math.pi)
    for x in (-6.2, 6.4):
        scn.decal('water', (x, BY1 - CT, BZ + 2.15), (1.5, 1.3), (0, -1, 0), lift=0.012)
        scn.decal('crack', (x, BY0 + CT, BZ + 1.4), (1.8, 1.8), (0, 1, 0), lift=0.010)
    # ceiling water ingress along the beam joints
    for (x, y) in ((-3.4, 19.8), (2.6, 22.6), (5.2, 27.2)):
        scn.decal('water', (x, y, CEIL), (1.3, 1.15), (0, 0, -1), lift=0.010)
    # floor: grime at the walls, and scuffed traffic where the players actually walk
    for (x, y, sz, rot) in ((-4.0, 21.0, (2.6, 2.2), 0.4), (4.4, 23.8, (3.0, 2.4), 1.1),
                            (-2.2, 26.6, (2.8, 2.2), 2.0), (2.0, 19.2, (2.4, 2.0), 0.7)):
        scn.decal('scorch', (x, y, BZ), sz, (0, 0, 1), rot=rot, lift=0.006)
    for (px, py, sz) in ((-4.55, 21.6, 1.5), (2.6, 18.9, 1.2), (6.7, 24.3, 1.3)):
        scn.decal('oil', (px, py, BZ), (sz, sz), (0, 0, 1), lift=0.004)
    # civil-defence notices pinned to the concrete
    scn.decal('poster', (WX2, 19.35, BZ + 1.62), (0.60, 0.84), (1, 0, 0), lift=0.012)
    scn.decal('poster', (-2.9, BY0 + CT, BZ + 1.60), (0.58, 0.80), (0, 1, 0), lift=0.012)
    scn.decal('poster', (EX2, 27.1, BZ + 1.66), (0.58, 0.80), (-1, 0, 0), lift=0.012)


def service_tunnel(scn):
    """Sealed corridor behind the bunker's barrier window — zombie spawn side, never reachable."""
    x0, x1, y0, y1 = L.TUNNEL_X0, L.TUNNEL_X1, BY1, L.TUNNEL_Y1
    scn.box_mm('concrete_bunker', (x0 - CT, y0, BZ - 0.4), (x1 + CT, y1 + CT, BZ))
    scn.box_mm('concrete_bunker', (x0 - CT, y0, BZ), (x0, y1, CEIL + 0.3))
    scn.box_mm('concrete_bunker', (x1, y0, BZ), (x1 + CT, y1, CEIL + 0.3))
    scn.box_mm('concrete_bunker', (x0 - CT, y1, BZ), (x1 + CT, y1 + CT, CEIL + 0.3))
    scn.box_mm('concrete_bunker', (x0 - CT, y0, CEIL), (x1 + CT, y1 + CT, CEIL + 0.3))
    rnd = random.Random(19)
    for i in range(10):
        scn.rock('concrete', (rnd.uniform(x0 + 0.5, x1 - 0.5), rnd.uniform(y0 + 1.0, y1 - 0.5),
                              BZ + 0.1), (rnd.uniform(0.2, 0.5),) * 3, seed=700 + i)
    scn.box('lamp_glow', (6.0, 31.0, CEIL - 0.25), (0.3, 0.3, 0.1))


def blast_door(scn):
    """Visual DOOR_bunker_door: a heavy steel blast door recessed in the headhouse portal."""
    y = L.HH_Y0 + 0.55 + 0.14
    g = scn.group('DOOR_bunker_door', (-1.05, y, 0.0))
    g.box('metal_rust', (0.0, y, 1.28), (2.18, 0.20, 2.56))
    g.box('paint_green_mil', (0.0, y - 0.11, 1.28), (2.02, 0.05, 2.40))
    for i in range(4):
        g.box('metal_rust', (0.0, y - 0.14, 0.34 + i * 0.66), (2.06, 0.06, 0.15))
    for s in (-1, 1):
        for i in range(6):
            g.cyl('metal_rust', (s * 0.94, y - 0.16, 0.26 + i * 0.44), 0.05, 0.08, 8, axis='y')
    # locking wheel + spokes
    g.cyl('metal_rust', (0.58, y - 0.24, 1.02), 0.30, 0.10, 16, axis='y')
    g.cyl('metal_rust', (0.58, y - 0.24, 1.02), 0.24, 0.13, 16, axis='y')
    g.cyl('metal_dark', (0.58, y - 0.30, 1.02), 0.07, 0.14, 10, axis='y')
    for k in range(4):
        a_ = k * math.pi / 4 + 0.3
        g.box('metal_rust', (0.58, y - 0.26, 1.02), (0.56, 0.06, 0.06), rot=(0, a_, 0))
    # painted radiation trefoil on the leaf
    g.cyl('charred', (-0.34, y - 0.125, 1.58), 0.42, 0.02, 20, axis='y')
    CL.trefoil(g, 'paint_bus', (-0.34, y - 0.142, 1.58), (0, -1, 0), r=0.345, depth=0.014)
    # hinges
    for z in (0.35, 1.28, 2.20):
        g.box('metal_dark', (-1.06, y - 0.06, z), (0.30, 0.26, 0.26))
        g.cyl('metal_dark', (-1.16, y - 0.06, z), 0.07, 0.30, 10)
    for i in range(6):
        g.box('paint_bus' if i % 2 == 0 else 'charred', (-0.95 + i * 0.34, y - 0.15, 2.36),
              (0.28, 0.05, 0.30), rot=(0, 0.6, 0))
    g.build()
    scn.col_box('COL_DOOR_bunker_door', (-1.10, L.HH_Y0 + 0.42, 0.0),
                (1.10, L.HH_Y0 + 0.92, 2.60))


def build(scn):
    mound(scn)
    headhouse(scn)
    ramp(scn)
    room(scn)
    service_tunnel(scn)
    blast_door(scn)
