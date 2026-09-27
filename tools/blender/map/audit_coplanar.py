"""Find coplanar overlapping faces between different meshes — the source of z-fighting flicker.

Two surfaces that share a plane and overlap in 2D will flicker in game whenever both are
visible: the depth buffer cannot separate them. Decals are drawn with polygonOffset by the
renderer, but ordinary props are not, so anything lying exactly on a floor / wall / panel has
to be lifted a few millimetres (or the duplicate face deleted).

Only *cross-mesh* pairs are reported. Faces inside one merged material bank share a draw call
and are almost always internal (the shared wall between two adjacent slabs, for example);
faces from two different material banks are two different draw calls and always fight.

    python build_map.py -- --audit            (inside Blender, after the scene is built)
"""
import math
from collections import defaultdict

EPS_N = 1e-4          # how axis-aligned a face has to be
EPS_P = 5e-4          # plane quantisation (0.5 mm)
MIN_AREA = 0.004      # ignore slivers smaller than 40 cm^2


def _faces(ob):
    me = ob.data
    mw = ob.matrix_world
    me.calc_loop_triangles()
    out = []
    for poly in me.polygons:
        n = mw.to_3x3() @ poly.normal
        ln = n.length
        if ln < 1e-9:
            continue
        n = n / ln
        ax = None
        for k in range(3):
            if abs(abs(n[k]) - 1.0) < EPS_N:
                ax = k
                break
        if ax is None:
            continue
        vs = [mw @ me.vertices[i].co for i in poly.vertices]
        u, v = (ax + 1) % 3, (ax + 2) % 3
        lo = [min(p[u] for p in vs), min(p[v] for p in vs)]
        hi = [max(p[u] for p in vs), max(p[v] for p in vs)]
        if (hi[0] - lo[0]) * (hi[1] - lo[1]) < MIN_AREA:
            continue
        out.append((ax, vs[0][ax], lo, hi, 1 if n[ax] > 0 else -1,
                    (sum(p[u] for p in vs) / len(vs), sum(p[v] for p in vs) / len(vs))))
    return out


def audit(objects, limit=40, verbose=True):
    """objects: iterable of mesh objects. Returns a list of (area, description) tuples."""
    buckets = defaultdict(list)
    for ob in objects:
        name = ob.name.replace('MESH_', '')
        for (ax, p, lo, hi, sgn, mid) in _faces(ob):
            buckets[(ax, round(p / EPS_P))].append((name, lo, hi, sgn, mid))

    hits = defaultdict(lambda: [0.0, 0, None])
    for (ax, q), items in buckets.items():
        if len(items) < 2:
            continue
        # grid index so a 3000-face bucket does not become 4.5M comparisons
        grid = defaultdict(list)
        for idx, (name, lo, hi, sgn, mid) in enumerate(items):
            for gx in range(int(math.floor(lo[0])), int(math.floor(hi[0])) + 1):
                for gy in range(int(math.floor(lo[1])), int(math.floor(hi[1])) + 1):
                    grid[(gx, gy)].append(idx)
        seen = set()
        for cell in grid.values():
            for i in range(len(cell)):
                for j in range(i + 1, len(cell)):
                    a, b = cell[i], cell[j]
                    if items[a][0] == items[b][0]:
                        continue                     # same mesh / same draw call
                    key = (a, b) if a < b else (b, a)
                    if key in seen:
                        continue
                    seen.add(key)
                    na, loa, hia, sa, mida = items[a]
                    nb, lob, hib, sb, midb = items[b]
                    ow = min(hia[0], hib[0]) - max(loa[0], lob[0])
                    oh = min(hia[1], hib[1]) - max(loa[1], lob[1])
                    if ow <= 1e-4 or oh <= 1e-4:
                        continue
                    area = ow * oh
                    if area < MIN_AREA:
                        continue
                    k = (min(na, nb), max(na, nb), 'xyz'[ax])
                    rec = hits[k]
                    rec[0] += area
                    rec[1] += 1
                    if rec[2] is None or area > rec[2][0]:
                        c = [0.0, 0.0, 0.0]
                        c[ax] = q * EPS_P
                        c[(ax + 1) % 3] = (max(loa[0], lob[0]) + min(hia[0], hib[0])) / 2
                        c[(ax + 2) % 3] = (max(loa[1], lob[1]) + min(hia[1], hib[1])) / 2
                        rec[2] = (area, tuple(round(v, 2) for v in c), sa, sb)

    out = sorted(((v[0], k, v[1], v[2]) for k, v in hits.items()), reverse=True)
    if verbose:
        print('--- COPLANAR AUDIT: %d cross-mesh plane pairs ---' % len(out))
        for (area, (ma, mb, ax), n, worst) in out[:limit]:
            print('  %8.2f m2  %4d faces  %-22s / %-22s  %s  worst %.2f m2 at %s  n=%+d/%+d'
                  % (area, n, ma, mb, ax, worst[0], worst[1], worst[2], worst[3]))
    return out
