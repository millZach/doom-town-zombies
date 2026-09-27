"""Check the exported map GLB against docs/ASSET_CONTRACT.md (names, budgets, geometry rules).

  node is not needed:  python tools/blender/map/validate.py public/models/map_doomtown.glb

Coordinates inside the GLB are glTF (+Y up): Blender (x, y, z) exported as (x, z, -y).
"""
import json, math, struct, sys, os

HOUSES = ('yellow', 'green')
DOORS = ('yellow_front', 'green_front', 'bunker_door',
         'yellow_back', 'green_back', 'yellow_stairs', 'green_stairs')
BARRIERS = ('yw1', 'yw2', 'gw1', 'gw2', 'bw1', 'yu1', 'gu1')

REQUIRED = (['MK_PLAYER_START', 'MK_PAP', 'MK_POWER']
            + ['MK_SPAWN_GROUND_street_%d' % i for i in range(1, 8)]
            + ['MK_SPAWN_GROUND_bunker_%d' % i for i in (1, 2)]
            + ['MK_SPAWN_GROUND_yardw_%d' % i for i in (1, 2, 3)]
            + ['MK_SPAWN_GROUND_yarde_%d' % i for i in (1, 2, 3)]
            + ['MK_BARRIER_' + b for b in BARRIERS]
            + ['MK_SPAWN_WIN_' + b for b in BARRIERS]
            + ['COL_BARRIER_' + b for b in BARRIERS]
            + ['MK_DOOR_' + d for d in DOORS]
            + ['COL_DOOR_' + d for d in DOORS]
            + ['DOOR_' + d for d in DOORS]
            + ['MK_WALLBUY_' + w for w in ('m14', 'olympia', 'mp5', 'remington870', 'ak74u')]
            + ['MK_PERK_' + p for p in ('quickrevive', 'speedcola', 'juggernog', 'doubletap')]
            + ['MK_BOX_%d' % i for i in range(1, 9)]
            + ['COL_STAIR_' + h for h in HOUSES]
            + ['COL_FLOOR_' + h + 'up' for h in HOUSES]
            + ['COL_FLOOR_yardw', 'COL_FLOOR_yarde']
            + ['ZONE_street', 'ZONE_yellow', 'ZONE_green', 'ZONE_bunker',
               'ZONE_yellowup', 'ZONE_greenup', 'ZONE_yardw', 'ZONE_yarde'])

UP_FLOOR = 3.02            # upstairs floor (Blender z / glTF y)
MAX_STAIR_DEG = 32.0
MIN_DOORWAY = 1.00         # clear width a zombie (0.7 m) / the player (0.64 m) needs
DOOR_H0, DOOR_H1 = 0.30, 1.50       # height band sampled through a doorway
# things that actually obstruct a doorway. Walls, floors, ramps, removable door blockers and
# barrier fillers are not obstacles; furniture and clutter are.
OBSTACLE_PREFIXES = ('COL_PROP', 'COL_COLUMN', 'COL_SANDBAG', 'COL_PORCHPOST', 'COL_TREE',
                     'COL_SIGN')


def load(path):
    buf = open(path, 'rb').read()
    assert struct.unpack_from('<I', buf, 0)[0] == 0x46546C67
    jlen = struct.unpack_from('<I', buf, 12)[0]
    return json.loads(buf[20:20 + jlen].decode('utf-8')), len(buf)


# --------------------------------------------------------------------------- node geometry
def _quat_mat(q):
    x, y, z, w = q
    return ((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
            (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
            (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)))


def node_aabb(g, n):
    """World AABB of a mesh node, in glTF axes. None for nodes without a mesh."""
    mi = n.get('mesh')
    if mi is None:
        return None
    lo = [1e30] * 3
    hi = [-1e30] * 3
    for p in g['meshes'][mi]['primitives']:
        a = g['accessors'][p['attributes']['POSITION']]
        if 'min' not in a:
            return None
        for k in range(3):
            lo[k] = min(lo[k], a['min'][k])
            hi[k] = max(hi[k], a['max'][k])
    s = n.get('scale', [1, 1, 1])
    t = n.get('translation', [0, 0, 0])
    m = _quat_mat(n.get('rotation', [0, 0, 0, 1]))
    out_lo = [1e30] * 3
    out_hi = [-1e30] * 3
    for cx in (lo[0], hi[0]):
        for cy in (lo[1], hi[1]):
            for cz in (lo[2], hi[2]):
                v = (cx * s[0], cy * s[1], cz * s[2])
                for k in range(3):
                    w = m[k][0] * v[0] + m[k][1] * v[1] + m[k][2] * v[2] + t[k]
                    out_lo[k] = min(out_lo[k], w)
                    out_hi[k] = max(out_hi[k], w)
    return out_lo, out_hi


def base(name):
    return name.split('.')[0]


# --------------------------------------------------------------------------- checks
def check_ramp_clearance(boxes):
    """Nothing may sit as an invisible ceiling over the open bunker ramp trench.

    The ramp runs (Blender) from y 11.60 z 0.0 down to y 17.05 z -2.50 across x +-1.6, so in
    glTF from (0, 0, -11.60) to (0, -2.50, -17.05). A street-level slab left across it made the
    player stick at the top of the ramp and have to jump onto it.
    """
    y0, y1, z0, z1 = 11.60, 17.05, 0.0, -2.50
    bad = []
    for i in range(1, 40):
        t = i / 40.0
        gz = -(y0 + (y1 - y0) * t)
        gy = z0 + (z1 - z0) * t
        for gx in (-1.2, 0.0, 1.2):
            for (name, lo, hi) in boxes:
                if name.startswith(('COL_RAMP', 'COL_STAIR')):
                    continue
                if lo[0] <= gx <= hi[0] and lo[2] <= gz <= hi[2] \
                        and lo[1] < gy + 2.0 and hi[1] > gy + 0.05:
                    bad.append((name, round(gz, 2), round(gy, 2)))
    uniq = sorted(set(bad))
    if uniq:
        print('FAIL: collision over the bunker ramp (invisible ceiling):')
        for (n, gz, gy) in uniq[:10]:
            print('      %s at three z=%.2f, ramp surface y=%.2f' % (n, gz, gy))
    return not uniq


def check_ramp_head(boxes):
    """No hole or pit where the ramp meets the street (three z -11.7 .. -11.0)."""
    ok = True
    for gz in (-11.0, -11.2, -11.4, -11.55):
        found = False
        for (name, lo, hi) in boxes:
            if not name.startswith('COL_'):
                continue
            if lo[0] <= 0.0 <= hi[0] and lo[2] <= gz <= hi[2] and -0.35 <= hi[1] <= 0.12:
                found = True
                break
        if not found:
            print('FAIL: no floor collision at the head of the ramp, three z=%.2f' % gz)
            ok = False
    return ok


def check_stairs(boxes):
    ok = True
    for h in HOUSES:
        r = [b for b in boxes if base(b[0]) == 'COL_STAIR_' + h]
        if not r:
            print('FAIL: COL_STAIR_%s missing' % h)
            ok = False
            continue
        _n, lo, hi = r[0]
        rise = hi[1] - lo[1]
        run = max(hi[0] - lo[0], hi[2] - lo[2])
        wide = min(hi[0] - lo[0], hi[2] - lo[2])
        deg = math.degrees(math.atan2(max(rise - 0.5, 0.0), run))
        print('  COL_STAIR_%-7s rise %.2f m over %.2f m = %.1f deg, width %.2f m'
              % (h, rise, run, deg, wide))
        if deg > MAX_STAIR_DEG:
            print('FAIL: staircase %s is %.1f deg (max %.0f)' % (h, deg, MAX_STAIR_DEG))
            ok = False
        if wide < 1.0:
            print('FAIL: staircase %s is only %.2f m wide (min 1.0)' % (h, wide))
            ok = False
        if lo[1] > 0.4 or abs(hi[1] - UP_FLOOR) > 0.4:
            print('FAIL: staircase %s does not meet both floors (%.2f .. %.2f)'
                  % (h, lo[1], hi[1]))
            ok = False
    for h in HOUSES:
        d = [b for b in boxes if base(b[0]) == 'COL_DOOR_%s_stairs' % h]
        if d and (d[0][2][1] - d[0][1][1]) < 2.0:
            print('FAIL: COL_DOOR_%s_stairs is only %.2f m tall (min 2.0)'
                  % (h, d[0][2][1] - d[0][1][1]))
            ok = False
    return ok


def check_doorways(boxes):
    """Every gap in a COL_WALL line must have MIN_DOORWAY of clear width through it.

    COL_WALL slabs are emitted per wall segment, so a doorway is simply the gap between two
    consecutive slabs of the same wall. For each gap we take a corridor 1 m deep on both sides
    of the wall plane, project every obstacle that reaches into the 0.30-1.50 m height band on
    to the wall axis, and measure the widest remaining free run inside the gap.

    (This is what caught the green kitchen doorway, where a shelf unit and the fridge left
    0.57 m and zombies wedged there forever.)
    """
    walls = [b for b in boxes if base(b[0]) == 'COL_WALL']
    obstacles = [b for b in boxes if base(b[0]).startswith(OBSTACLE_PREFIXES)]
    lines = {}
    for (nm, lo, hi) in walls:
        ax = 0 if (hi[0] - lo[0]) < (hi[2] - lo[2]) else 2      # thin axis (glTF y is up)
        run = 2 - ax
        lines.setdefault((ax, round((lo[ax] + hi[ax]) / 2, 2), round(lo[1], 1)), []).append(
            (lo[run], hi[run], lo[1], hi[1]))
    ok = True
    checked = 0
    for (ax, plane, _y0), segs in sorted(lines.items()):
        segs.sort()
        run = 2 - ax
        for (a, b) in zip(segs, segs[1:]):
            gap0, gap1 = a[1], b[0]
            if gap1 - gap0 < 1.2:                 # not a doorway (or already a hard fail below)
                if gap1 - gap0 > 0.05:
                    print('FAIL: wall gap of only %.2f m at %s=%.2f, %s %.2f..%.2f'
                          % (gap1 - gap0, 'xyz'[ax], plane, 'xyz'[run], gap0, gap1))
                    ok = False
                continue
            ylo, yhi = min(a[2], b[2]), max(a[3], b[3])
            if yhi - ylo < DOOR_H1:
                continue                           # this wall is not at walking height here
            checked += 1
            blocked = []
            for (nm, lo, hi) in obstacles:
                if hi[1] < ylo + DOOR_H0 or lo[1] > ylo + DOOR_H1:
                    continue
                if hi[ax] < plane - 1.0 or lo[ax] > plane + 1.0:
                    continue
                if hi[run] <= gap0 or lo[run] >= gap1:
                    continue
                blocked.append((max(lo[run], gap0), min(hi[run], gap1), nm))
            blocked.sort()
            free, cur, worst = 0.0, gap0, None
            for (s0, s1, nm) in blocked + [(gap1, gap1, None)]:
                if s0 - cur > free:
                    free = s0 - cur
                cur = max(cur, s1)
                if nm:
                    worst = nm
            if free < MIN_DOORWAY - 1e-3:
                print('FAIL: doorway at %s=%.2f, %s %.2f..%.2f (y %.2f) has only %.2f m clear '
                      '(need %.2f) - blocked by %s'
                      % ('xyz'[ax], plane, 'xyz'[run], gap0, gap1, ylo, free, MIN_DOORWAY, worst))
                ok = False
    print('  doorways checked: %d' % checked)
    return ok


def check_zones(zones):
    """Multi-level nav contract: the ground-floor house zones must stop at or below the
    upstairs floor, and the upstairs zones must start exactly at it."""
    ok = True
    for h in HOUSES:
        g = [z for z in zones if base(z[0]) == 'ZONE_' + h]
        u = [z for z in zones if base(z[0]) == 'ZONE_' + h + 'up']
        if not g or not u:
            print('FAIL: ZONE_%s / ZONE_%sup missing' % (h, h))
            ok = False
            continue
        gtop = max(z[2][1] for z in g)
        ubot = min(z[1][1] for z in u)
        utop = max(z[2][1] for z in u)
        print('  ZONE_%-8s y %.2f .. %.2f   ZONE_%-10s y %.2f .. %.2f'
              % (h, min(z[1][1] for z in g), gtop, h + 'up', ubot, utop))
        if gtop > UP_FLOOR + 1e-3:
            print('FAIL: ZONE_%s reaches y=%.2f, above the upstairs floor %.2f'
                  % (h, gtop, UP_FLOOR))
            ok = False
        if abs(ubot - UP_FLOOR) > 0.02:
            print('FAIL: ZONE_%sup starts at y=%.2f, not at the upstairs floor %.2f'
                  % (h, ubot, UP_FLOOR))
            ok = False
        if utop - ubot < 2.5:
            print('FAIL: ZONE_%sup is only %.2f m tall' % (h, utop - ubot))
            ok = False
    return ok


def check_markers_in_zones(g, zones):
    """Every spawn / box marker has to sit inside some ZONE volume or the nav probe never
    sees the floor it stands on."""
    ok = True
    for n in g['nodes']:
        nm = n.get('name', '')
        if not nm.startswith(('MK_SPAWN_', 'MK_BOX_', 'MK_PERK_')):
            continue
        t = n.get('translation', [0, 0, 0])
        inside = any(all(z[1][k] - 0.05 <= t[k] <= z[2][k] + 0.05 for k in range(3))
                     for z in zones)
        if not inside:
            print('FAIL: %s at (%.2f, %.2f, %.2f) is outside every ZONE box'
                  % (nm, t[0], t[1], t[2]))
            ok = False
    return ok


def main(path):
    g, size = load(path)
    names = [n.get('name', '') for n in g['nodes']]
    ok = True
    missing = [r for r in REQUIRED if r not in names]
    if missing:
        ok = False
        print('MISSING NODES:', ', '.join(missing))
    lamps = [n for n in names if n.startswith('MK_LAMP_')]
    fires = [n for n in names if n.startswith('MK_FIRE_')]
    print('MK_LAMP count %d (<=24)  MK_FIRE count %d (<=10)' % (len(lamps), len(fires)))
    ok &= len(lamps) <= 24 and len(fires) <= 10

    boxes, zones = [], []
    for n in g['nodes']:
        nm = n.get('name', '')
        if not nm.startswith(('COL_', 'ZONE_')):
            continue
        bb = node_aabb(g, n)
        if bb is None:
            continue
        rec = (nm, bb[0], bb[1])
        (zones if nm.startswith('ZONE_') else boxes).append(rec)
    ok &= check_ramp_clearance(boxes)
    ok &= check_ramp_head(boxes)
    ok &= check_stairs(boxes)
    ok &= check_zones(zones)
    ok &= check_doorways(boxes)
    ok &= check_markers_in_zones(g, zones)

    acc = g['accessors']
    tris = 0
    for m in g['meshes']:
        for p in m['primitives']:
            i = p.get('indices')
            tris += (acc[i]['count'] if i is not None else acc[p['attributes']['POSITION']]['count']) / 3
    print('triangles %d (<=1_500_000)   file %.2f MB (<=60)' % (tris, size / 1048576))
    ok &= tris <= 1_500_000 and size <= 60 * 1048576
    print('COL_* %d   ZONE_* %d   MK_* %d   DOOR_* %d'
          % (sum(n.startswith('COL_') for n in names), sum(n.startswith('ZONE_') for n in names),
             sum(n.startswith('MK_') for n in names),
             sum(n.startswith('DOOR_') and '_part' not in n for n in names)))
    print('images %d  materials %d' % (len(g.get('images', [])), len(g.get('materials', []))))
    mats = g.get('materials', [])
    blend = [m.get('name', '?') for m in mats if m.get('alphaMode') == 'BLEND']
    print('alphaMode BLEND (%d): %s' % (len(blend), ', '.join(blend)))
    if not any(n.startswith('glass') for n in blend):
        print('WARNING: no transparent glass material in the export (environment.md #10)')
    if not any(n.startswith('decal_') for n in blend):
        print('WARNING: decal materials are not alpha-blended (environment.md #8)')
    print('RESULT:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'public/models/map_doomtown.glb'))
