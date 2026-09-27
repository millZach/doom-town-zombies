"""Map-building helpers (my own; common.py is shared and must not be edited).

The core idea is a `Scene` that accumulates *all* visual geometry into one bmesh per material
("banks"), so the exported GLB has a handful of big meshes instead of thousands of objects, and
every surface gets consistent world-scale cube-projected UVs. Collision / zone / marker nodes are
emitted separately with their exact contract names.
"""
import bpy, bmesh, math, random, os, sys
from mathutils import Vector, Matrix, Euler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import link, new_collection, empty, pbr_material, assign  # noqa: E402


# --------------------------------------------------------------------------- bmesh primitives
def _xform(center, size, rot):
    m = Matrix.Translation(Vector(center))
    if rot and any(rot):
        m = m @ Euler(rot, 'XYZ').to_matrix().to_4x4()
    return m @ Matrix.Diagonal(Vector(size).to_4d())


def bm_box(bm, center, size, rot=(0, 0, 0)):
    verts = bmesh.ops.create_cube(bm, size=1.0)['verts']
    bmesh.ops.transform(bm, matrix=_xform(center, size, rot), verts=verts)
    return verts


def bm_box_mm(bm, mn, mx):
    c = [(mn[i] + mx[i]) * 0.5 for i in range(3)]
    s = [abs(mx[i] - mn[i]) for i in range(3)]
    return bm_box(bm, c, s)


def bm_prism(bm, pts2d, depth, matrix=None):
    """Polygon in the local XY plane extruded `depth` along +Z, then transformed by `matrix`."""
    vs = [bm.verts.new((p[0], p[1], 0.0)) for p in pts2d]
    face = bm.faces.new(vs)
    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    top = [e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, depth), verts=top)
    allv = list(vs) + list(top)
    if matrix is not None:
        bmesh.ops.transform(bm, matrix=matrix, verts=allv)
    return allv


def bm_loft(bm, sections, closed=True, cap_start=True, cap_end=True):
    """Skin a list of equal-length point rings into a tube (lofted hull)."""
    rings = [[bm.verts.new(tuple(p)) for p in sec] for sec in sections]
    n = len(sections[0])
    m = n if closed else n - 1
    for a, b in zip(rings, rings[1:]):
        for i in range(m):
            j = (i + 1) % n
            try:
                bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError:
                pass
    if closed:
        if cap_start:
            try: bm.faces.new(rings[0][::-1])
            except ValueError: pass
        if cap_end:
            try: bm.faces.new(rings[-1])
            except ValueError: pass
    return rings


def squircle(hw, hz, zc, n=5.0, segs=24, t0=0.0, t1=2 * math.pi, y0=0.0):
    """Rounded-rectangle cross-section in the YZ plane (list of (y, z))."""
    pts = []
    full = abs(t1 - t0 - 2 * math.pi) < 1e-6
    k = segs if full else segs + 1
    for i in range(k):
        t = t0 + (t1 - t0) * (i / segs if full else i / segs)
        c, sn = math.cos(t), math.sin(t)
        y = hw * (abs(c) ** (2.0 / n)) * (1 if c >= 0 else -1)
        z = hz * (abs(sn) ** (2.0 / n)) * (1 if sn >= 0 else -1)
        pts.append((y + y0, z + zc))
    return pts


def bm_cyl(bm, center, radius, height, segs=12, axis='z', rot=(0, 0, 0), cap=True, r2=None):
    """Cylinder / truncated cone along `axis` centred on `center`."""
    r2 = radius if r2 is None else r2
    bmv = bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segs,
                                radius1=radius, radius2=r2, depth=height)
    verts = bmv['verts']
    pre = {'z': (0, 0, 0), 'x': (0, math.pi / 2, 0), 'y': (math.pi / 2, 0, 0)}[axis]
    m = Matrix.Translation(Vector(center)) @ Euler(rot, 'XYZ').to_matrix().to_4x4() \
        @ Euler(pre, 'XYZ').to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=m, verts=verts)
    return verts


def bm_rock(bm, center, size, seed=0, subd=2):
    """Lumpy chunk of rubble, flattened and part-buried so it settles into the ground."""
    rnd = random.Random(seed)
    tmp = bmesh.new()
    bmesh.ops.create_icosphere(tmp, subdivisions=subd, radius=0.5)
    for v in tmp.verts:
        v.co *= 1.0 + rnd.uniform(-0.18, 0.18)
        v.co.z *= rnd.uniform(0.34, 0.62)
    m = _xform(center, size, (rnd.uniform(0, 3), rnd.uniform(0, 3), rnd.uniform(0, 6)))
    bmesh.ops.transform(tmp, matrix=m, verts=tmp.verts)
    me = bpy.data.meshes.new('_tmp')
    tmp.to_mesh(me); tmp.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


# --------------------------------------------------------------------------- UVs
def bm_uv_cube(bm, scale, faces=None, offset=(0.0, 0.0)):
    uvl = bm.loops.layers.uv.verify()
    inv = 1.0 / scale
    for f in (faces if faces is not None else bm.faces):
        n = f.normal
        ax = 0 if abs(n.x) >= abs(n.y) and abs(n.x) >= abs(n.z) else (1 if abs(n.y) >= abs(n.z) else 2)
        for l in f.loops:
            co = l.vert.co
            if ax == 0:
                u, v = (co.y, co.z)
            elif ax == 1:
                u, v = (co.x, co.z)
            else:
                u, v = (co.x, co.y)
            l[uvl].uv = (u * inv + offset[0], v * inv + offset[1])


# --------------------------------------------------------------------------- block lettering
FONT = {
    'A': ('###', '# #', '###', '# #', '# #'), 'B': ('## ', '# #', '## ', '# #', '## '),
    'C': ('###', '#  ', '#  ', '#  ', '###'), 'D': ('## ', '# #', '# #', '# #', '## '),
    'E': ('###', '#  ', '###', '#  ', '###'), 'F': ('###', '#  ', '###', '#  ', '#  '),
    'G': ('###', '#  ', '# #', '# #', '###'), 'H': ('# #', '# #', '###', '# #', '# #'),
    'I': ('###', ' # ', ' # ', ' # ', '###'), 'J': ('  #', '  #', '  #', '# #', '###'),
    'K': ('# #', '# #', '## ', '# #', '# #'), 'L': ('#  ', '#  ', '#  ', '#  ', '###'),
    'M': ('# #', '###', '###', '# #', '# #'), 'N': ('## ', '# #', '# #', '# #', '# #'),
    'O': ('###', '# #', '# #', '# #', '###'), 'P': ('###', '# #', '###', '#  ', '#  '),
    'Q': ('###', '# #', '# #', '###', '  #'), 'R': ('###', '# #', '## ', '# #', '# #'),
    'S': ('###', '#  ', '###', '  #', '###'), 'T': ('###', ' # ', ' # ', ' # ', ' # '),
    'U': ('# #', '# #', '# #', '# #', '###'), 'V': ('# #', '# #', '# #', '# #', ' # '),
    'W': ('# #', '# #', '###', '###', '# #'), 'X': ('# #', '# #', ' # ', '# #', '# #'),
    'Y': ('# #', '# #', ' # ', ' # ', ' # '), 'Z': ('###', '  #', ' # ', '#  ', '###'),
    '0': ('###', '# #', '# #', '# #', '###'), '1': (' # ', '## ', ' # ', ' # ', '###'),
    '2': ('###', '  #', '###', '#  ', '###'), '3': ('###', '  #', '###', '  #', '###'),
    '4': ('# #', '# #', '###', '  #', '  #'), '5': ('###', '#  ', '###', '  #', '###'),
    '6': ('###', '#  ', '###', '# #', '###'), '7': ('###', '  #', '  #', '  #', '  #'),
    '8': ('###', '# #', '###', '# #', '###'), '9': ('###', '# #', '###', '  #', '###'),
    '.': ('   ', '   ', '   ', '   ', ' # '), '-': ('   ', '   ', '###', '   ', '   '),
    ':': ('   ', ' # ', '   ', ' # ', '   '), ' ': ('   ', '   ', '   ', '   ', '   '),
}


def text_boxes(target, mat, text, origin, run, up, face, h=0.26, depth=0.02, gap=1.0,
               skip=0.0, seed=0, bg=False):
    """DEPRECATED — use lib_sign.sign_text().

    3x5 block lettering. Kept only for tiny incidental marks; `skip` is ignored because in a 3x5
    grid a single dropped pixel turns A into H and R into K ("FHLLOUT SHELTEK", environment.md #6).
    """
    skip = 0.0
    rnd = random.Random(seed)
    px = h / 5.0
    run, up, face = Vector(run).normalized(), Vector(up).normalized(), Vector(face).normalized()
    adv = (3.0 + gap) * px
    total = len(text) * adv - gap * px
    start = Vector(origin) - run * (total / 2.0)
    size = tuple(abs(run[k]) * px + abs(up[k]) * px + abs(face[k]) * depth for k in range(3))
    for i, ch in enumerate(text):
        g = FONT.get(ch.upper())
        if not g:
            continue
        for r, rowstr in enumerate(g):
            for c, cell in enumerate(rowstr):
                if cell != '#' or rnd.random() < skip:
                    continue
                p = (start + run * (i * adv + (c + 0.5) * px) + up * ((2 - r) * px)
                     + face * (depth / 2.0))
                target.box(mat, tuple(p), size, bg=bg)
    return total


# --------------------------------------------------------------------------- geometry mixin
class Geom:
    """Primitive builders that only need `self.bm(mat, bg)` -- shared by Scene and Sub."""

    def box(self, mat, center, size, rot=(0, 0, 0), bg=False):
        return bm_box(self.bm(mat, bg), center, size, rot)

    def box_mm(self, mat, mn, mx, bg=False):
        return bm_box_mm(self.bm(mat, bg), mn, mx)

    def cyl(self, mat, center, radius, height, segs=12, axis='z', rot=(0, 0, 0), r2=None, bg=False):
        return bm_cyl(self.bm(mat, bg), center, radius, height, segs, axis, rot, True, r2)

    def prism(self, mat, pts2d, depth, matrix=None, bg=False):
        return bm_prism(self.bm(mat, bg), pts2d, depth, matrix)

    def loft(self, mat, sections, closed=True, cap_start=True, cap_end=True, bg=False):
        return bm_loft(self.bm(mat, bg), sections, closed, cap_start, cap_end)

    def rock(self, mat, center, size, seed=0, subd=1, bg=False):
        bm = self.bm(mat, bg)
        bm.faces.ensure_lookup_table()
        n0 = len(bm.faces)
        bm_rock(bm, center, size, seed, subd)
        bm.faces.ensure_lookup_table()
        for f in bm.faces[n0:]:
            f.select = True          # carries "keep this faceted" through to the smooth pass

    def slab(self, mat, pts, z_top, z_bot, bg=False):
        slab_prism(self.bm(mat, bg), pts, z_top, z_bot)

    def ring(self, mat, a, b, z_top, z_bot, bg=False):
        strip_prism(self.bm(mat, bg), a, b, z_top, z_bot)

    def disc_slab(self, mat, center, r, z_top, z_bot, n=20, squash=1.0, rot=0.0, bg=False):
        disc(self.bm(mat, bg), center, r, z_top, z_bot, n, squash, rot)

    def decal(self, name, center, size, face=(0, 0, 1), rot=0.0, lift=0.008, bg=False):
        """Stamp an authored decal (lib_decals) as a thin quad just off a surface.

        `face` is the surface normal; the quad's local +up is +Z for walls and +Y for floors,
        rotated by `rot` about the normal. Decal textures are authored with their "top" (the
        source of a streak, the hot end of a soot fan) at v = 1.
        """
        from mathutils import Matrix as _M
        bm = self.bm('decal_' + name, bg)
        f = Vector(face).normalized()
        ref = Vector((0, 0, 1)) if abs(f.z) < 0.9 else Vector((0, 1, 0))
        run = ref.cross(f).normalized()
        up = f.cross(run).normalized()
        if rot:
            m = _M.Rotation(rot, 3, f)
            run, up = m @ run, m @ up
        # Two decals stamped on the same wall at the same lift z-fight each other (the game's
        # polygonOffset separates a decal from its *host*, not from another decal), so every
        # decal gets its own sub-millimetre step.
        self._decal_n = getattr(self, '_decal_n', 0) + 1
        c = Vector(center) + f * (lift + 0.00055 * (self._decal_n % 9))
        w, h = size[0] / 2.0, size[1] / 2.0
        uvl = bm.loops.layers.uv.verify()
        vs = [bm.verts.new(tuple(c + run * a + up * b))
              for (a, b) in ((-w, -h), (w, -h), (w, h), (-w, h))]
        face_ = bm.faces.new(vs)
        face_.select = True
        for lp, uv in zip(face_.loops, ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))):
            lp[uvl].uv = uv
        return face_

    def tube(self, mat, path, radius, segs=8, bg=False):
        """Round tube swept along a polyline of (x, y, z) points."""
        secs = []
        n = len(path)
        for i, p in enumerate(path):
            a = Vector(path[max(i - 1, 0)])
            b = Vector(path[min(i + 1, n - 1)])
            d = (b - a)
            if d.length < 1e-6:
                d = Vector((0, 0, 1))
            d.normalize()
            up = Vector((0, 0, 1)) if abs(d.z) < 0.92 else Vector((1, 0, 0))
            u = d.cross(up).normalized()
            v = u.cross(d).normalized()
            r = radius[i] if isinstance(radius, (list, tuple)) else radius
            secs.append([tuple(Vector(p) + u * (r * math.cos(2 * math.pi * k / segs))
                               + v * (r * math.sin(2 * math.pi * k / segs))) for k in range(segs)])
        return bm_loft(self.bm(mat, bg), secs)


class Sub(Geom):
    """Build a prop in its own local space, then stamp it into a Scene with any 4x4 matrix."""

    def __init__(self):
        self.banks = {}

    def bm(self, mat, bg=False):
        if mat not in self.banks:
            self.banks[mat] = bmesh.new()
        return self.banks[mat]

    def stamp(self, scn, matrix, bg=False):
        for mat, bm in self.banks.items():
            if len(bm.faces):
                bmesh.ops.transform(bm, matrix=matrix, verts=bm.verts)
                keep = [f.select for f in bm.faces]
                me = bpy.data.meshes.new('_stamp')
                bm.to_mesh(me)
                dst = scn.bm(mat, bg)
                dst.faces.ensure_lookup_table()
                n0 = len(dst.faces)
                dst.from_mesh(me)
                dst.faces.ensure_lookup_table()
                for i, f in enumerate(dst.faces[n0:]):
                    f.select = keep[i] if i < len(keep) else False
                bpy.data.meshes.remove(me)
            bm.free()
        self.banks = {}


# --------------------------------------------------------------------------- scene
class Scene(Geom):
    def __init__(self, materials):
        self.materials = materials                  # name -> bpy material
        self.col_vis = new_collection('VIS')
        self.col_col = new_collection('COL')
        self.col_mk = new_collection('MK')
        self.col_bg = new_collection('BG')
        self.banks = {}
        self.bg_banks = {}
        self.objects = []
        self.col_objs = []
        self.uv_scale = {}
        self.bevel = {}
        self.bevel_default = 0.0
        self.smooth_angle = 0.0
        self._col_ids = {}

    # -- geometry banks -----------------------------------------------------
    def bm(self, mat, bg=False):
        d = self.bg_banks if bg else self.banks
        if mat not in d:
            d[mat] = bmesh.new()
        return d[mat]

    def crater(self, mat, center, r, depth=0.16, rim=0.12, n=22, seed=0, bg=False):
        bm = self.bm(mat, bg)
        rnd = random.Random(seed)
        c = bm.verts.new((center[0], center[1], -depth))
        rings = []
        for k, (rr, zz) in enumerate(((0.45, -depth * 0.75), (0.82, -depth * 0.2), (1.0, rim), (1.35, 0.005))):
            vs = []
            for i in range(n):
                t = 2 * math.pi * i / n
                j = 1.0 + rnd.uniform(-0.13, 0.13)
                vs.append(bm.verts.new((center[0] + r * rr * j * math.cos(t),
                                        center[1] + r * rr * j * math.sin(t),
                                        zz + rnd.uniform(-0.02, 0.03) * (1 if k else 0))))
            rings.append(vs)
        for i in range(n):
            bm.faces.new((c, rings[0][i], rings[0][(i + 1) % n]))
        for a, b in zip(rings, rings[1:]):
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((a[i], b[i], b[j], a[j]))

    def plank(self, mat, center, size, rot=(0, 0, 0)):
        return self.box(mat, center, size, rot)

    # -- collision / zones / markers ---------------------------------------
    def _uname(self, name):
        n = self._col_ids.get(name, 0)
        self._col_ids[name] = n + 1
        return name if n == 0 else '%s.%03d' % (name, n)

    def col_box(self, name, mn, mx, rot=None, collection=None):
        c = [(mn[i] + mx[i]) * 0.5 for i in range(3)]
        s = [abs(mx[i] - mn[i]) for i in range(3)]
        return self.col_obj(name, c, s, rot or (0, 0, 0), collection)

    def col_obj(self, name, center, size, rot=(0, 0, 0), collection=None):
        bm = bmesh.new()
        bm_box(bm, (0, 0, 0), size)
        me = bpy.data.meshes.new(self._uname(name))
        bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(me.name, me)
        ob.location = center
        ob.rotation_euler = rot
        link(ob, collection or self.col_col)
        ob.display_type = 'WIRE'
        self.col_objs.append(ob)
        return ob

    def col_ramp(self, name, p0, p1, width, thick=0.4):
        """Smooth ramp collider from p0 to p1 (both on the walking surface)."""
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        length = d.length
        yaw = math.atan2(d.y, d.x) - math.pi / 2          # local +Y along the run
        pitch = math.asin(d.z / length)
        mid = (p0 + p1) * 0.5
        rot = Euler((pitch, 0, yaw), 'XYZ')
        down = rot.to_matrix() @ Vector((0, 0, -thick / 2))
        return self.col_obj(name, mid + down, (width, length, thick), tuple(rot))

    def zone(self, zid, mn, mx):
        return self.col_box('ZONE_' + zid, mn, mx)

    def marker(self, name, loc, yaw=0.0, extras=None):
        return empty(name, loc, (0, 0, yaw), self.col_mk, 0.35, extras)

    def group(self, name, origin=(0, 0, 0)):
        return Group(self, name, origin)

    # -- walls --------------------------------------------------------------
    def wall(self, mat, axis, pos, a0, a1, z0, z1, t, openings=(), col=True,
             col_top=None, inner_mat=None, out=1, bg=False):
        """A wall slab with rectangular openings.

        axis='x': runs along X, normal along Y, `pos` is its centre Y.
        axis='y': runs along Y, normal along X, `pos` is its centre X.
        `inner_mat`: if given, the wall is two 40/60 slabs so inside and outside differ.
        openings: dicts with a0,a1,z0,z1, kind in {'window','door','open','barrier'}, id.
        """
        ops = sorted(openings, key=lambda o: o['a0'])

        def slab(mn_a, mx_a, mn_z, mx_z):
            if mx_a - mn_a < 1e-4 or mx_z - mn_z < 1e-4:
                return
            if inner_mat is None:
                self._slab(mat, axis, pos, mn_a, mx_a, mn_z, mx_z, t, bg)
            else:
                # The inner leaf is grown 2 mm into the outer one. Butting them exactly used to
                # leave ~500 m2 of coplanar faces across the two houses (siding/wallpaper,
                # plaster/siding, wallpaper_a/wallpaper_b) -- two draw calls on one plane.
                ti, ov = t * 0.42, 0.002
                self._slab(mat, axis, pos + out * (t / 2 - ti / 2), mn_a, mx_a, mn_z, mx_z, ti, bg)
                self._slab(inner_mat, axis, pos - out * (ti / 2 - ov / 2), mn_a, mx_a,
                           mn_z, mx_z, t - ti + ov, bg)

        cur = a0
        for o in ops:
            slab(cur, o['a0'], z0, z1)
            slab(o['a0'], o['a1'], z0, o['z0'])
            slab(o['a0'], o['a1'], o['z1'], z1)
            cur = o['a1']
        slab(cur, a1, z0, z1)

        if col:
            top = max(z1, z0 + 3.0) if col_top is None else col_top
            gaps = [(o['a0'], o['a1']) for o in ops if o['kind'] in ('door', 'open')]
            cur = a0
            segs = []
            for g0, g1 in sorted(gaps):
                if g0 - cur > 1e-3:
                    segs.append((cur, g0))
                cur = max(cur, g1)
            if a1 - cur > 1e-3:
                segs.append((cur, a1))
            for s0, s1 in segs:
                self._col_slab(axis, pos, s0, s1, z0, top, t)

    def _slab(self, mat, axis, pos, a0, a1, z0, z1, t, bg=False):
        c_a, s_a = (a0 + a1) / 2, (a1 - a0)
        c_z, s_z = (z0 + z1) / 2, (z1 - z0)
        if axis == 'x':
            self.box(mat, (c_a, pos, c_z), (s_a, t, s_z), bg=bg)
        else:
            self.box(mat, (pos, c_a, c_z), (t, s_a, s_z), bg=bg)

    def _col_slab(self, axis, pos, a0, a1, z0, z1, t):
        c_a, s_a = (a0 + a1) / 2, (a1 - a0)
        c_z, s_z = (z0 + z1) / 2, (z1 - z0)
        if axis == 'x':
            self.col_obj('COL_WALL', (c_a, pos, c_z), (s_a, max(t, 0.2), s_z))
        else:
            self.col_obj('COL_WALL', (pos, c_a, c_z), (max(t, 0.2), s_a, s_z))

    # -- finish -------------------------------------------------------------
    def build(self):
        out = []
        for banks, coll, tag in ((self.banks, self.col_vis, 'M'), (self.bg_banks, self.col_bg, 'BG')):
            for mat, bm in banks.items():
                if len(bm.faces) == 0:
                    bm.free(); continue
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
                bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
                bm.normal_update()
                w = 0.0 if tag == 'BG' else self.bevel.get(mat, self.bevel_default)
                if w > 0.0:
                    edges = [e for e in bm.edges
                             if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > 0.6]
                    if edges:
                        bmesh.ops.bevel(bm, geom=edges, offset=w, segments=1, affect='EDGES',
                                        clamp_overlap=True, profile=0.5, offset_type='OFFSET')
                        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
                        bm.normal_update()
                if self.smooth_angle > 0.0:
                    bm.faces.ensure_lookup_table()
                    for f in bm.faces:
                        f.smooth = not f.select
                    for e in bm.edges:
                        e.smooth = (len(e.link_faces) == 2
                                    and e.calc_face_angle(3.15) < self.smooth_angle)
                if not mat.startswith('decal_'):      # decals carry their own 0..1 quad UVs
                    bm_uv_cube(bm, self.uv_scale.get(mat, 2.0))
                name = ('BG_' + mat) if tag == 'BG' else ('MESH_' + mat)
                me = bpy.data.meshes.new(name)
                bm.to_mesh(me); bm.free()
                ob = bpy.data.objects.new(name, me)
                link(ob, coll)
                m = self.materials.get(mat)
                if m:
                    assign(ob, m)
                else:
                    print('WARNING: no material named %r -- mesh %s exports untextured' % (mat, name))
                out.append(ob)
        self.objects = out
        self.banks = {}
        self.bg_banks = {}
        return out


class Group(Geom):
    """A separately-named node (e.g. DOOR_yellow_front) made of one child mesh per material,
    built in world coordinates but re-centred on `origin` so the game can rotate it."""

    def __init__(self, scn, name, origin=(0, 0, 0)):
        self.scn = scn
        self.name = name
        self.origin = Vector(origin)
        self.banks = {}

    def bm(self, mat, bg=False):
        if mat not in self.banks:
            self.banks[mat] = bmesh.new()
        return self.banks[mat]

    def build(self):
        root = empty(self.name, tuple(self.origin), collection=self.scn.col_vis, size=0.2)
        for mat, bm in self.banks.items():
            if not len(bm.faces):
                bm.free(); continue
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bmesh.ops.translate(bm, vec=-self.origin, verts=bm.verts)
            bm.normal_update()
            if self.scn.smooth_angle > 0.0:
                for f in bm.faces:
                    f.smooth = True
                for e in bm.edges:
                    e.smooth = (len(e.link_faces) == 2
                                and e.calc_face_angle(3.15) < self.scn.smooth_angle)
            if not mat.startswith('decal_'):
                bm_uv_cube(bm, self.scn.uv_scale.get(mat, 2.0), offset=(self.origin.x, self.origin.z))
            me = bpy.data.meshes.new('part_%s_%s' % (mat, self.name.lower()))
            bm.to_mesh(me); bm.free()
            ob = bpy.data.objects.new(me.name, me)
            link(ob, self.scn.col_vis)
            ob.parent = root
            ob.location = (0, 0, 0)
            m = self.scn.materials.get(mat)
            if m:
                assign(ob, m)
        self.banks = {}
        return root


# --------------------------------------------------------------------------- misc
def jitter(rnd, a):
    return rnd.uniform(-a, a)


def culdesac_outline(r, w, y0, cy=2.0, n=44):
    """CCW outline of the road: a rectangle of half-width `w` running north from y0 into a bulb of
    radius `r` centred at (0, cy). Always returns 4 + n points in matching order for any r/w,
    so two calls can be lofted into a kerb / pavement ring."""
    yj = cy - math.sqrt(max(r * r - w * w, 0.01))
    t0 = math.atan2(yj - cy, w)
    t1 = math.pi - t0
    pts = [(-w, y0), (w, y0), (w, yj)]
    for i in range(n):
        t = t0 + (t1 - t0) * (i + 1) / (n + 1)
        pts.append((r * math.cos(t), cy + r * math.sin(t)))
    pts.append((-w, yj))
    return pts


def strip_prism(bm, a, b, z_top, z_bot):
    """Closed ring solid between two matching closed outlines (top face + skirt)."""
    n = len(a)
    vt_a = [bm.verts.new((p[0], p[1], z_top)) for p in a]
    vt_b = [bm.verts.new((p[0], p[1], z_top)) for p in b]
    vb_a = [bm.verts.new((p[0], p[1], z_bot)) for p in a]
    vb_b = [bm.verts.new((p[0], p[1], z_bot)) for p in b]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vt_a[i], vt_a[j], vt_b[j], vt_b[i]))       # top
        bm.faces.new((vb_a[i], vb_b[i], vb_b[j], vb_a[j]))       # bottom
        bm.faces.new((vt_a[i], vb_a[i], vb_a[j], vt_a[j]))       # inner wall
        bm.faces.new((vt_b[i], vt_b[j], vb_b[j], vb_b[i]))       # outer wall


def slab_prism(bm, pts, z_top, z_bot):
    """Solid slab from a closed CCW outline."""
    vt = [bm.verts.new((p[0], p[1], z_top)) for p in pts]
    vb = [bm.verts.new((p[0], p[1], z_bot)) for p in pts]
    bm.faces.new(vt)
    bm.faces.new(list(reversed(vb)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vt[i], vb[i], vb[j], vt[j]))


def disc(bm, center, r, z_top, z_bot, n=24, squash=1.0, rot=0.0):
    pts = []
    for i in range(n):
        t = rot + 2 * math.pi * i / n
        pts.append((center[0] + r * math.cos(t), center[1] + r * squash * math.sin(t)))
    slab_prism(bm, pts, z_top, z_bot)
