"""Doom Town — single source of truth for the map layout.

Blender coords: X east, Y north, Z up. All walkable floors of street/yellow/green at Z = 0.
Bunker floor at Z = -2.5, reached by a ~25 deg ramp behind a blast door in a concrete headhouse.

House markers are written in *house-local* coordinates (lx = 0 at the front wall growing towards
the back, ly = -6.5..6.5 along the street) and mapped to world here, exactly like build_houses.py
does, so geometry and markers can never drift apart.

Nothing in here imports bpy, so it can be read/validated with plain python too.
"""
import math

# ---------------------------------------------------------------- street / cul-de-sac
STREET_X = 11.5              # |x| boundary plane of the playable street (= house front walls)
ROAD_BULB_C = (0.0, 2.0)
ROAD_BULB_R = 7.6
ROAD_W = 4.6                 # half width of the straight road part
STREET_Y_S = -21.0
STREET_Y_N = 13.0            # mound face

# ---------------------------------------------------------------- houses
WALL_T = 0.22
CEIL_H = 2.72                # ground floor ceiling
HOUSE_D = 11.10              # front-to-back depth
HOUSE_Y0, HOUSE_Y1 = -6.5, 6.5
Y_X1 = -STREET_X             # yellow front (east) wall plane
Y_X0 = Y_X1 - HOUSE_D        # yellow back (west) wall plane
G_X0 = STREET_X              # green front (west) wall plane
G_X1 = G_X0 + HOUSE_D        # green back (east) wall plane

DOOR_W, DOOR_H = 1.8, 2.30   # buyable door opening
BARRIER_W, BARRIER_H, BARRIER_SILL = 1.2, 1.1, 0.9

# ---------------------------------------------------------------- house second storey
# The upstairs is playable: a staircase in the hall (collision = a smooth 29.7 deg ramp) leads
# from the ground floor to a finished floor at UP_FLOOR, with a 2.70 m ceiling above it.
UP_FLOOR = 3.02              # upstairs finished floor (top of the deck)
UP_DECK = 0.12               # deck thickness (2.90 .. 3.02 — sits above the 2.72 ceiling)
UP_CEIL = 5.72               # upstairs top plate / ceiling underside
UP_SILL = UP_FLOOR + BARRIER_SILL          # 3.92 — upstairs barrier-window sill
UP_WIN_Z0, UP_WIN_Z1 = UP_SILL, UP_SILL + BARRIER_H     # 3.92 .. 5.02

# stair: house-local, against the middle of the hall, climbing towards +ly
ST_LX0, ST_LX1 = 7.78, 9.22            # 1.44 m wide (contract: >= 1.2)
ST_LY0, ST_LY1 = -0.55, 4.75           # 5.30 m run for 3.02 m rise -> 29.68 deg
ST_HOLE = (7.68, 9.32, 0.55, 4.75)     # stairwell opening in the deck (lx0, lx1, ly0, ly1)

# single-storey utility wing on the back wall: its flat roof is the upstairs zombie pocket
WING_LX0, WING_LX1 = HOUSE_D, HOUSE_D + 4.20
WING_LY0, WING_LY1 = 3.70, 7.70
UP_BARR_LY0, UP_BARR_LY1 = 4.90, 6.10  # upstairs barrier opening in the back wall

# back door into the yard (back wall, ground floor)
BACKDOOR_LY0, BACKDOOR_LY1 = 0.20, 2.00

# ---------------------------------------------------------------- back yards
YARD_X = 30.0                # outer fence plane (|x|)
YARD_Y = 13.5                # side fence planes (|y|)

# ---------------------------------------------------------------- bunker
HH_X = 4.0                   # headhouse half width
HH_Y0, HH_Y1 = 9.5, 13.6
HH_H = 4.2
COR_X = 1.6                  # ramp cut half width
RAMP_Y0, RAMP_Y1 = 11.6, 17.05
BUNK_Z = -2.5
BUNK_X = 8.0
BUNK_Y0, BUNK_Y1 = 17.2, 28.4
BUNK_CEIL = 0.45
TUNNEL_X0, TUNNEL_X1 = 3.0, 9.0
TUNNEL_Y1 = 34.5
BERM_Y0, BERM_Y1 = 13.0, 35.5
BERM_TOP = 3.25

RAMP_ANGLE = math.degrees(math.atan2(-BUNK_Z, RAMP_Y1 - RAMP_Y0))


# ---------------------------------------------------------------- facing helpers
def facing(direction):
    """Z rotation (radians) so the empty's local -Y points along `direction`."""
    return {'-y': 0.0, '+x': math.pi / 2, '+y': math.pi, '-x': -math.pi / 2}[direction]


def yaw_to(frm, to):
    return math.atan2(to[0] - frm[0], -(to[1] - frm[1]))


def _sxy(side):
    return (-1.0, 1.0) if side == 'yellow' else (1.0, -1.0)


def hp(side, lx, ly, z=0.0):
    """house-local -> world point"""
    sx, sy = _sxy(side)
    return ((Y_X1 if side == 'yellow' else G_X0) + sx * lx, sy * ly, z)


def hyaw(side, dx, dy):
    """house-local facing direction -> world yaw (the empty's local -Y points that way)"""
    sx, sy = _sxy(side)
    return math.atan2(sx * dx, -(sy * dy))


def _house_markers(side, box_n, perk_id, box_local, perk_local, wb_out, wb_in,
                   yard_zone, yard_box_n, up_box_n):
    b = 'yw' if side == 'yellow' else 'gw'
    u = b[0] + 'u'                 # 'yu' / 'gu' — the upstairs barrier
    T = WALL_T
    return [
        ('MK_BARRIER_%s1' % b, hp(side, 3.3, 6.5 - T / 2, BARRIER_SILL), hyaw(side, 0, -1)),
        ('MK_BARRIER_%s2' % b, hp(side, HOUSE_D - T / 2, -3.4, BARRIER_SILL), hyaw(side, -1, 0)),
        ('MK_SPAWN_WIN_%s1' % b, hp(side, 3.3, 11.4, 0.0), hyaw(side, 0, -1)),
        ('MK_SPAWN_WIN_%s2' % b, hp(side, HOUSE_D + 4.2, -3.4, 0.0), hyaw(side, -1, 0)),
        # upstairs barrier window in the back wall, over the flat roof of the utility wing
        ('MK_BARRIER_%s1' % u, hp(side, HOUSE_D - T / 2, (UP_BARR_LY0 + UP_BARR_LY1) / 2, UP_SILL),
         hyaw(side, -1, 0)),
        ('MK_SPAWN_WIN_%s1' % u, hp(side, WING_LX1 - 0.70, (UP_BARR_LY0 + UP_BARR_LY1) / 2,
                                    UP_FLOOR), hyaw(side, -1, 0)),
        ('MK_DOOR_%s_front' % side, hp(side, -1.05, -2.1, 0.0), hyaw(side, 1, 0)),
        ('MK_DOOR_%s_back' % side, hp(side, 10.15, 1.10, 0.0), hyaw(side, 1, 0)),
        ('MK_DOOR_%s_stairs' % side, hp(side, (ST_LX0 + ST_LX1) / 2, -0.78, 0.0), hyaw(side, 0, 1)),
        ('MK_WALLBUY_%s' % wb_out, hp(side, -0.02, 3.3, 1.40), hyaw(side, -1, 0)),
        ('MK_WALLBUY_%s' % wb_in, hp(side, 4.1, -6.5 + T + 0.02, 1.40), hyaw(side, 0, 1)),
        ('MK_PERK_%s' % perk_id, hp(side, *perk_local), hyaw(side, 0, -1)),
        ('MK_BOX_%s' % box_n, hp(side, *box_local), hyaw(side, 0, 1)),
        # mystery box spots added with the yards / upstairs
        ('MK_BOX_%s' % yard_box_n, hp(side, 15.5, -6.0, 0.0), hyaw(side, 0, 1)),
        ('MK_BOX_%s' % up_box_n, hp(side, 8.50, -5.75, UP_FLOOR), hyaw(side, 0, 1)),
        # zombies rising in the yard (zone id is the 4th token: yardw / yarde)
        ('MK_SPAWN_GROUND_%s_1' % yard_zone, hp(side, 16.5, -9.5, 0.0), hyaw(side, -1, 0)),
        ('MK_SPAWN_GROUND_%s_2' % yard_zone, hp(side, 5.5, -10.5, 0.0), hyaw(side, 0, 1)),
        ('MK_SPAWN_GROUND_%s_3' % yard_zone, hp(side, 5.5, 10.5, 0.0), hyaw(side, 0, -1)),
    ]


MARKERS = [
    ('MK_PLAYER_START', (0.0, 8.2, 0.0), facing('-y')),

    # --- zombie ground spawns: open dirt, >= 1.5 m from walls, out of the start view
    ('MK_SPAWN_GROUND_street_1', (-9.4, -15.5, 0.0), facing('-y')),
    ('MK_SPAWN_GROUND_street_2', (9.4, -15.5, 0.0), facing('-y')),
    ('MK_SPAWN_GROUND_street_3', (-9.6, 9.4, 0.0), facing('-y')),
    ('MK_SPAWN_GROUND_street_4', (9.6, 9.4, 0.0), facing('-y')),
    ('MK_SPAWN_GROUND_street_5', (0.0, -19.0, 0.0), facing('+y')),
    ('MK_SPAWN_GROUND_street_6', (-8.4, 11.2, 0.0), facing('-y')),
    ('MK_SPAWN_GROUND_street_7', (8.4, 11.2, 0.0), facing('-y')),
    ('MK_SPAWN_GROUND_bunker_1', (-5.6, 19.6, BUNK_Z), facing('+y')),
    ('MK_SPAWN_GROUND_bunker_2', (5.6, 25.4, BUNK_Z), facing('-y')),

    # --- bunker barrier window (north wall) and its spawn in the sealed service tunnel
    ('MK_BARRIER_bw1', (5.5, BUNK_Y1 - 0.15, BUNK_Z + BARRIER_SILL), facing('-y')),
    ('MK_SPAWN_WIN_bw1', (5.5, 32.6, BUNK_Z), facing('-y')),

    ('MK_DOOR_bunker_door', (0.0, 8.55, 0.0), facing('+y')),

    ('MK_WALLBUY_ak74u', (-BUNK_X + 0.32, 24.6, BUNK_Z + 1.40), facing('+x')),
    ('MK_PERK_quickrevive', (-6.6, 12.10, 0.0), facing('-y')),
    ('MK_PERK_doubletap', (-7.15, 18.30, BUNK_Z), facing('+x')),
    ('MK_BOX_1', (5.2, -11.0, 0.0), facing('-x')),
    ('MK_BOX_4', (5.4, 20.2, BUNK_Z), facing('-x')),
    ('MK_PAP', (0.0, 27.4, BUNK_Z), facing('-y')),
    ('MK_POWER', (-BUNK_X + 0.30, 20.4, BUNK_Z + 1.30), facing('+x')),

    # --- light sources (each sits on a modelled fixture)
    ('MK_LAMP_1', (-8.6, -13.0, 5.32), 0.0),
    ('MK_LAMP_2', (8.6, 5.2, 5.32), 0.0),
    ('MK_LAMP_3', (-8.6, 7.6, 5.32), 0.0),
    ('MK_LAMP_10', (0.0, 19.2, BUNK_Z + 2.30), 0.0),
    ('MK_LAMP_11', (0.0, 23.4, BUNK_Z + 2.30), 0.0),
    ('MK_LAMP_12', (1.30, 14.4, -0.30), 0.0),
]

MARKERS += _house_markers('yellow', '2', 'speedcola', (9.6, -5.6), (1.8, 5.75), 'm14', 'mp5',
                          'yardw', '5', '7')
MARKERS += _house_markers('green', '3', 'juggernog', (9.6, -5.6), (8.6, 5.60), 'olympia',
                          'remington870', 'yarde', '6', '8')

STREET_LAMPS = [(-8.6, -13.0, 0.0), (8.6, 5.2, math.pi), (-8.6, 7.6, -0.5)]
HOUSE_LAMPS = {'yellow': [(4.5, -1.2), (2.9, 4.2)], 'green': [(4.5, -1.2), (7.6, 2.6)]}

for _side, _n in (('yellow', 4), ('green', 5)):
    MARKERS.append(('MK_LAMP_%d' % _n, hp(_side, -0.06, -2.1, 2.36), 0.0))
_n = 6
for _side in ('yellow', 'green'):
    for _loc in HOUSE_LAMPS[_side]:
        MARKERS.append(('MK_LAMP_%d' % _n, hp(_side, _loc[0], _loc[1], 2.46), 0.0))
        _n += 1

# upstairs ceiling fittings (must match build_houses.UP_LIGHTS)
UP_LAMPS = ((2.6, -4.4), (2.6, -0.5), (1.7, 3.9), (4.7, 3.9), (8.4, 2.2), (8.6, -3.8))
_n = 13
for _side in ('yellow', 'green'):
    for _loc in UP_LAMPS:
        MARKERS.append(('MK_LAMP_%d' % _n, hp(_side, _loc[0], _loc[1], UP_CEIL - 0.26), 0.0))
        _n += 1

FIRES = [
    ('MK_FIRE_1', (-7.4, -7.6, 0.05)),
    ('MK_FIRE_2', (7.6, -3.2, 0.05)),
    ('MK_FIRE_3', (-2.3, -12.6, 0.60)),
    ('MK_FIRE_4', (5.4, 8.2, 0.65)),
    ('MK_FIRE_5', (-9.9, 3.4, 0.05)),
    ('MK_FIRE_6', (10.0, -9.4, 0.05)),
    ('MK_FIRE_7', (2.6, 10.8, 0.05)),
    ('MK_FIRE_8', hp('yellow', 3.2, -0.6, 0.05)),
    ('MK_FIRE_9', (0.0, -18.4, 0.05)),
]

ZONES = {
    'street': [
        ((-STREET_X - 0.2, STREET_Y_S - 0.4, -0.3), (STREET_X + 0.2, 9.4, 2.7)),
        ((-STREET_X - 0.2, 9.4, -0.3), (-HH_X - 0.1, STREET_Y_N + 0.2, 2.7)),
        ((HH_X + 0.1, 9.4, -0.3), (STREET_X + 0.2, STREET_Y_N + 0.2, 2.7)),
    ],
    # the ground-floor zones stop *below* the upstairs deck so they never overlap ZONE_*up
    'yellow': [((Y_X0 - 0.1, HOUSE_Y0 - 0.1, -0.3), (Y_X1 + 0.1, HOUSE_Y1 + 0.1, 2.88))],
    'green': [((G_X0 - 0.1, HOUSE_Y0 - 0.1, -0.3), (G_X1 + 0.1, HOUSE_Y1 + 0.1, 2.88))],
    # the upstairs zones start *exactly* at the upstairs floor (multi-level nav contract)
    'yellowup': [((Y_X0 - 0.1, HOUSE_Y0 - 0.1, UP_FLOOR),
                  (Y_X1 + 0.1, HOUSE_Y1 + 0.1, UP_CEIL + 0.05))],
    'greenup': [((G_X0 - 0.1, HOUSE_Y0 - 0.1, UP_FLOOR),
                 (G_X1 + 0.1, HOUSE_Y1 + 0.1, UP_CEIL + 0.05))],
    # back yards: behind each house plus the two side strips, inside the tall boundary fence
    'yardw': [((-YARD_X - 0.2, -YARD_Y - 0.1, -0.3), (Y_X0 - 0.1, YARD_Y + 0.1, 2.9)),
              ((Y_X0 - 0.1, -YARD_Y - 0.1, -0.3), (-STREET_X - 0.1, HOUSE_Y0 - 0.1, 2.9)),
              ((Y_X0 - 0.1, HOUSE_Y1 + 0.1, -0.3), (-STREET_X - 0.1, YARD_Y + 0.1, 2.9)),
              # the utility-wing roof: the zombie pocket for the upstairs barrier window.
              # Unreachable from the ground, but the nav grid still has to see it.
              ((Y_X0 - 0.1 - WING_LX1 + HOUSE_D, WING_LY0 - 0.3, UP_FLOOR - 0.06),
               (Y_X0 - 0.1, WING_LY1 + 0.3, UP_FLOOR + 2.4))],
    'yarde': [((G_X1 + 0.1, -YARD_Y - 0.1, -0.3), (YARD_X + 0.2, YARD_Y + 0.1, 2.9)),
              ((STREET_X + 0.1, -YARD_Y - 0.1, -0.3), (G_X1 + 0.1, HOUSE_Y0 - 0.1, 2.9)),
              ((STREET_X + 0.1, HOUSE_Y1 + 0.1, -0.3), (G_X1 + 0.1, YARD_Y + 0.1, 2.9)),
              ((G_X1 + 0.1, -WING_LY1 - 0.3, UP_FLOOR - 0.06),
               (G_X1 + 0.1 + WING_LX1 - HOUSE_D, -WING_LY0 + 0.3, UP_FLOOR + 2.4))],
    'bunker': [
        ((-COR_X - 0.1, HH_Y0 - 0.2, -0.3), (COR_X + 0.1, RAMP_Y0, 2.7)),
        ((-COR_X - 0.1, RAMP_Y0, BUNK_Z - 0.3), (COR_X + 0.1, BUNK_Y0 + 0.1, 2.7)),
        ((-BUNK_X - 0.1, BUNK_Y0 - 0.1, BUNK_Z - 0.3), (BUNK_X + 0.1, BUNK_Y1 + 0.1, BUNK_CEIL + 0.2)),
        # the sealed service tunnel behind the bunker barrier window: not player-reachable,
        # but MK_SPAWN_WIN_bw1 stands in it and the nav probe only looks inside zone volumes
        ((TUNNEL_X0 - 0.1, BUNK_Y1 - 0.1, BUNK_Z - 0.3),
         (TUNNEL_X1 + 0.1, TUNNEL_Y1 + 0.1, BUNK_CEIL + 0.2)),
    ],
}
