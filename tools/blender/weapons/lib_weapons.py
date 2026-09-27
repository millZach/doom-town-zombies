"""Shared library for the first-person weapon viewmodels.

Everything is authored in **camera space**: origin = the player's eye, the view looks along
Blender +Y, up = +Z, 50 deg vertical FOV at 16:9.  Individual weapons are modelled in *gun space*
(origin at the grip reference point, bore along +Y, up +Z, right +X) and then hung under the
`weapon` empty, whose location is the whole hip-fire framing.

    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from lib_weapons import *

Do not edit tools/blender/common.py - other agents use it concurrently.
"""
import bpy, bmesh, math, os, sys, random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import *                                     # noqa: F401,F403
from mathutils import Vector, Matrix, Euler, Quaternion

TAU = math.pi * 2.0
D2R = math.radians

WEAPONS_DIR = os.path.join(MODELS_DIR, 'weapons')
WRENDERS = os.path.join(RENDERS_DIR, 'weapons')
for _d in (WEAPONS_DIR, WRENDERS):
    os.makedirs(_d, exist_ok=True)

# Camera / framing constants -------------------------------------------------
FOV_V = 50.0                      # vertical field of view, degrees
ASPECT = 16.0 / 9.0
_TAN_V = math.tan(D2R(FOV_V) * 0.5)
_TAN_H = _TAN_V * ASPECT


def ndc(p):
    """Screen position of a camera-space point, in [-1,1] x [-1,1] (x right, y up)."""
    p = Vector(p)
    if p.y <= 1e-6:
        return None
    return (p.x / (_TAN_H * p.y), p.z / (_TAN_V * p.y))


# ---------------------------------------------------------------------------
#  Low level mesh helpers
# ---------------------------------------------------------------------------

def _finalise(name, bm, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    link(ob)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scale
    return ob


def rbox(name, size, loc=(0, 0, 0), rot=(0, 0, 0)):
    """Axis aligned box, `size` = full extents, `loc` = centre."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    return _finalise(name, bm, loc, rot)


def sphere(name, r, loc=(0, 0, 0), segs=20, scale=(1, 1, 1), rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=max(4, segs // 2), radius=r)
    return _finalise(name, bm, loc, rot, scale)


_AXIS_ROT = {'X': (0, math.pi / 2, 0), 'Y': (-math.pi / 2, 0, 0), 'Z': (0, 0, 0)}


def cylinder(name, r, h, loc=(0, 0, 0), axis='Z', segs=24, r2=None, rot=None, caps=True,
             arc=None, start=0.0):
    """Cylinder / cone / pie slice along `axis`, centred on loc.  r2 = far-end radius."""
    r2 = r if r2 is None else r2
    arc = TAU if arc is None else arc
    full = abs(arc - TAU) < 1e-6
    bm = bmesh.new()
    n = segs if full else max(3, int(round(segs * arc / TAU)))
    bot, top = [], []
    for i in range(n if full else n + 1):
        a = start + arc * (i / n)
        c, s = math.cos(a), math.sin(a)
        bot.append(bm.verts.new((c * r, s * r, -h * 0.5)))
        top.append(bm.verts.new((c * r2, s * r2, h * 0.5)))
    m = len(bot)
    rng = range(m) if full else range(m - 1)
    for i in rng:
        j = (i + 1) % m
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    if not full:
        cb = bm.verts.new((0, 0, -h * 0.5))
        ct = bm.verts.new((0, 0, h * 0.5))
        for i in range(m - 1):
            bm.faces.new((cb, bot[i + 1], bot[i]))
            bm.faces.new((ct, top[i], top[i + 1]))
        bm.faces.new((cb, bot[0], top[0], ct))
        bm.faces.new((cb, ct, top[m - 1], bot[m - 1]))
    elif caps:
        bm.faces.new(list(reversed(bot)))
        bm.faces.new(top)
    r0 = _AXIS_ROT[axis] if rot is None else rot
    ob = _finalise(name, bm, loc, r0)
    apply_transforms(ob, rot=True, scale=True)
    ob.location = loc
    return ob


def tube(name, ro, ri, h, loc=(0, 0, 0), axis='Z', segs=24, ro2=None, ri2=None):
    """Hollow cylinder (pipe) along `axis`."""
    ro2 = ro if ro2 is None else ro2
    ri2 = ri if ri2 is None else ri2
    bm = bmesh.new()
    ring = []
    for i in range(segs):
        a = TAU * i / segs
        c, s = math.cos(a), math.sin(a)
        ring.append((bm.verts.new((c * ro, s * ro, -h * .5)), bm.verts.new((c * ri, s * ri, -h * .5)),
                     bm.verts.new((c * ro2, s * ro2, h * .5)), bm.verts.new((c * ri2, s * ri2, h * .5))))
    for i in range(segs):
        a, b = ring[i], ring[(i + 1) % segs]
        bm.faces.new((a[0], b[0], b[2], a[2]))      # outside
        bm.faces.new((a[3], b[3], b[1], a[1]))      # inside
        bm.faces.new((a[1], b[1], b[0], a[0]))      # bottom ring
        bm.faces.new((a[2], b[2], b[3], a[3]))      # top ring
    r0 = _AXIS_ROT[axis]
    ob = _finalise(name, bm, loc, r0)
    apply_transforms(ob, rot=True, scale=True)
    ob.location = loc
    return ob


def prism(name, pts, y0, y1, loc=(0, 0, 0), rot=(0, 0, 0)):
    """Extrude a closed 2D polygon given in the (x, z) plane from y0 to y1.

    `pts` must be counter-clockwise when looking from +Y toward the origin."""
    bm = bmesh.new()
    a = [bm.verts.new((p[0], y0, p[1])) for p in pts]
    b = [bm.verts.new((p[0], y1, p[1])) for p in pts]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    return _finalise(name, bm, loc, rot)


def prism_x(name, pts, x0, x1, loc=(0, 0, 0), rot=(0, 0, 0)):
    """Extrude a closed 2D polygon given in the (y, z) plane from x0 to x1.
    This is *the* workhorse for gun side profiles (frames, stocks, receivers)."""
    bm = bmesh.new()
    a = [bm.verts.new((x0, p[0], p[1])) for p in pts]
    b = [bm.verts.new((x1, p[0], p[1])) for p in pts]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    return _finalise(name, bm, loc, rot)


def arc_pts(cu, cv, r, a0, a1, n=8):
    """Points on an arc, degrees.  Use to round off outline corners."""
    return [(cu + math.cos(D2R(a0 + (a1 - a0) * i / n)) * r,
             cv + math.sin(D2R(a0 + (a1 - a0) * i / n)) * r) for i in range(n + 1)]


def slide_profile(w, z_bot, z_flank, z_top, n=10, flat=0.0):
    """Classic pistol-slide cross section in (x, z): flat bottom, vertical flanks, domed top."""
    hw = w * 0.5
    pts = [(-hw, z_bot), (hw, z_bot), (hw, z_flank)]
    rise = z_top - z_flank
    for i in range(n + 1):
        a = math.pi * i / n
        x = math.cos(a) * hw
        z = z_flank + math.sin(a) ** (1.0 - flat) * rise
        pts.append((x, z))
    pts.append((-hw, z_flank))
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) > 1e-7 or abs(p[1] - out[-1][1]) > 1e-7:
            out.append(p)
    return out


def loft(name, rings, cap_start=True, cap_end=True, loc=(0, 0, 0), rot=(0, 0, 0), closed=True):
    """Skin a list of equal-length vertex rings (each a list of 3D points)."""
    bm = bmesh.new()
    vs = [[bm.verts.new(Vector(p)) for p in r] for r in rings]
    n = len(rings[0])
    for k in range(len(rings) - 1):
        for i in range(n if closed else n - 1):
            j = (i + 1) % n
            try:
                bm.faces.new((vs[k][i], vs[k][j], vs[k + 1][j], vs[k + 1][i]))
            except ValueError:
                pass
    if cap_start and closed:
        bm.faces.new(list(reversed(vs[0])))
    if cap_end and closed:
        bm.faces.new(vs[-1])
    return _finalise(name, bm, loc, rot)


def lathe(name, pts, segs=24, loc=(0, 0, 0), rot=(0, 0, 0), arc=None):
    """Spin a profile (list of (radius, z)) about the Z axis.

    A profile of 3+ points whose two ends are both off-axis is treated as a CLOSED section
    (e.g. a ring or a fin) and the loop is joined, so the result is a solid, not an open shell -
    open shells make the EXACT boolean solver produce garbage."""
    arc = TAU if arc is None else arc
    if (len(pts) >= 3 and abs(pts[0][0]) > 1e-6 and abs(pts[-1][0]) > 1e-6
            and (abs(pts[0][0] - pts[-1][0]) > 1e-9 or abs(pts[0][1] - pts[-1][1]) > 1e-9)):
        pts = list(pts) + [pts[0]]
    full = abs(arc - TAU) < 1e-6
    rings = []
    m = segs if full else segs + 1
    for i in range(m):
        a = arc * i / segs
        c, s = math.cos(a), math.sin(a)
        rings.append([(c * p[0], s * p[0], p[1]) for p in pts])
    # rings here are along the sweep; transpose so the loft skins rings of the profile
    bm = bmesh.new()
    vs = [[bm.verts.new(p) for p in r] for r in rings]
    for k in range(m - 1 if not full else m):
        k2 = (k + 1) % m
        for i in range(len(pts) - 1):
            try:
                bm.faces.new((vs[k][i], vs[k][i + 1], vs[k2][i + 1], vs[k2][i]))
            except ValueError:
                pass
    ob = _finalise(name, bm, loc, rot)
    merge_doubles(ob, 1e-5)
    return ob


def rrect(w, h, r, n=4, cx=0.0, cz=0.0):
    """Rounded rectangle profile (list of (x, z)), CCW seen from +Y."""
    r = min(r, w * 0.5 - 1e-5, h * 0.5 - 1e-5)
    x, z = w * 0.5 - r, h * 0.5 - r
    pts = []
    for cor, a0 in (((x, -z), -math.pi / 2), ((x, z), 0.0), ((-x, z), math.pi / 2), ((-x, -z), math.pi)):
        for i in range(n + 1):
            a = a0 + (math.pi / 2) * i / n
            pts.append((cx + cor[0] + math.cos(a) * r, cz + cor[1] + math.sin(a) * r))
    # dedupe
    out = []
    for p in pts:
        if not out or (abs(p[0] - out[-1][0]) > 1e-7 or abs(p[1] - out[-1][1]) > 1e-7):
            out.append(p)
    if abs(out[0][0] - out[-1][0]) < 1e-7 and abs(out[0][1] - out[-1][1]) < 1e-7:
        out.pop()
    return out


def ellipse(rx, rz, n=16, cx=0.0, cz=0.0, phase=0.0):
    return [(cx + math.cos(phase + TAU * i / n) * rx, cz + math.sin(phase + TAU * i / n) * rz) for i in range(n)]


def ring3(prof, y, sx=1.0, sz=1.0, ox=0.0, oz=0.0):
    """Turn a 2D (x, z) profile into a 3D ring at a given y."""
    return [(p[0] * sx + ox, y, p[1] * sz + oz) for p in prof]


# ---------------------------------------------------------------------------
#  Object operations
# ---------------------------------------------------------------------------

def act(ob):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    return ob


def merge_doubles(ob, dist=1e-5):
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bm.to_mesh(me)
    bm.free()
    return ob


def boolean(target, cutter, op='DIFFERENCE', remove=True):
    m = target.modifiers.new('bool', 'BOOLEAN')
    m.object = cutter
    m.operation = op
    m.solver = 'EXACT'
    act(target)
    bpy.ops.object.modifier_apply(modifier=m.name)
    if remove:
        d = cutter.data
        bpy.data.objects.remove(cutter, do_unlink=True)
        if d and d.users == 0:
            bpy.data.meshes.remove(d)
    return target


def cut(target, *cutters):
    for c in cutters:
        boolean(target, c, 'DIFFERENCE')
    return target


def fuse(name, objs):
    """Join a list of objects into one (transforms applied), keeping material slots."""
    objs = [o for o in objs if o is not None]
    if len(objs) == 1:
        objs[0].name = name
        return objs[0]
    base = objs[0]
    act(base)
    for o in objs[1:]:
        o.select_set(True)
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.join()
    base.name = name
    base.data.name = name
    return base


def dup(ob, name, loc=None, rot=None, scale=None, mirror_x=False):
    new = ob.copy()
    new.data = ob.data.copy()
    new.name = name
    new.data.name = name
    link(new)
    if loc is not None:
        new.location = loc
    if rot is not None:
        new.rotation_euler = rot
    if scale is not None:
        new.scale = scale
    if mirror_x:
        new.scale = (-new.scale.x, new.scale.y, new.scale.z)
        act(new)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode='OBJECT')
    return new


def xform(ob, mat):
    """Bake a world-space matrix into the mesh data."""
    ob.data.transform(mat)
    return ob


def set_origin(ob, p):
    """Move the object ORIGIN to gun-space point `p` without moving the geometry.

    The exported glTF node translation is the object origin, so this is how a movable part
    gets a meaningful pivot (`barrels` on the hinge pin, `crane` on the yoke pivot).  Only
    valid for objects whose mesh is already authored in gun space with location (0,0,0) or
    whose location is baked in `ob.location`."""
    p = Vector(p)
    cur = Vector(ob.location)
    ob.data.transform(Matrix.Translation(cur - p))
    ob.location = p
    return ob


# ---------------------------------------------------------------------------
#  UVs
# ---------------------------------------------------------------------------

def uv_project(ob, texel=0.20, long=None, jitter=0.0, seed=0):
    """Per-face planar projection.

    long=None  -> triplanar (U,V taken from the two axes the face normal is *not* dominant in)
    long=0/1/2 -> U is always that axis (directional grain: wood along a stock, machining marks)
    """
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name='UVMap')
    uv = me.uv_layers[0]
    rnd = random.Random(seed)
    ju, jv = (rnd.uniform(-1, 1) * jitter, rnd.uniform(-1, 1) * jitter)
    s = 1.0 / max(texel, 1e-6)
    for poly in me.polygons:
        n = poly.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        if long is None:
            u_ax, v_ax = [i for i in range(3) if i != ax]
            flip = n[ax] < 0
        else:
            if ax == long:
                u_ax, v_ax = [i for i in range(3) if i != ax]
            else:
                u_ax = long
                v_ax = [i for i in range(3) if i != ax and i != long][0]
            flip = n[ax] < 0
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            u = co[u_ax] * s
            v = co[v_ax] * s
            if flip:
                u = -u
            uv.data[li].uv = (u + ju, v + jv)
    return ob


# ---------------------------------------------------------------------------
#  Finishing (bevel + smooth + material)
# ---------------------------------------------------------------------------

def finish(ob, mat=None, bev=0.0007, segs=2, angle=38, texel=0.065, long=None, smooth=True,
           bevel_angle=32, jitter=0.0, seed=0):
    uv_project(ob, texel, long, jitter, seed)
    if bev and bev > 0:
        m = ob.modifiers.new('Bevel', 'BEVEL')
        m.width = bev
        m.segments = segs
        m.limit_method = 'ANGLE'
        m.angle_limit = D2R(bevel_angle)
        m.miter_outer = 'MITER_SHARP'
        m.harden_normals = False
        m.use_clamp_overlap = True
        act(ob)
        bpy.ops.object.modifier_apply(modifier=m.name)   # bake it: fuse() would lose it
    if smooth:
        shade_smooth(ob, angle)
    if mat is not None:
        assign(ob, mat)
    return ob


def finish_all(objs, mat=None, **kw):
    for o in objs:
        finish(o, mat, **kw)
    return objs


# ---------------------------------------------------------------------------
#  Detail generators
# ---------------------------------------------------------------------------

def screw(name, r=0.0022, loc=(0, 0, 0), axis='Y', kind='slot', head=0.0009, depth=0.0006):
    """Screw / pin head that sits proud of a surface.  kind: slot | hex | phillips | pin."""
    parts = []
    h = cylinder(name, r, head, (0, 0, 0), 'Z', 16, r2=r * 0.95)
    parts.append(h)
    if kind == 'slot':
        parts.append(rbox(name + '_c', (r * 2.4, r * 0.34, depth * 2), (0, 0, head * 0.5)))
    elif kind == 'phillips':
        parts.append(rbox(name + '_c', (r * 2.2, r * 0.30, depth * 2), (0, 0, head * 0.5)))
        parts.append(rbox(name + '_d', (r * 0.30, r * 2.2, depth * 2), (0, 0, head * 0.5)))
    elif kind == 'hex':
        parts.append(cylinder(name + '_c', r * 0.62, depth * 2, (0, 0, head * 0.5), 'Z', 6))
    ob = parts[0]
    for c in parts[1:]:
        boolean(ob, c, 'DIFFERENCE')
    ob.rotation_euler = _AXIS_ROT[axis]
    apply_transforms(ob, rot=True, scale=True)
    ob.location = loc
    return ob


def knurl_band(name, r, h, loc=(0, 0, 0), axis='Z', n_around=40, n_up=8, depth=0.00035, rot=None):
    """Diamond knurling: a cylinder whose alternating grid vertices are pushed out."""
    bm = bmesh.new()
    verts = []
    for j in range(n_up + 1):
        row = []
        z = -h * .5 + h * j / n_up
        for i in range(n_around):
            a = TAU * i / n_around
            rr = r + (depth if (i + j) % 2 == 0 else -depth)
            row.append(bm.verts.new((math.cos(a) * rr, math.sin(a) * rr, z)))
        verts.append(row)
    for j in range(n_up):
        for i in range(n_around):
            k = (i + 1) % n_around
            bm.faces.new((verts[j][i], verts[j][k], verts[j + 1][k], verts[j + 1][i]))
    bm.faces.new(list(reversed(verts[0])))
    bm.faces.new(verts[-1])
    ob = _finalise(name, bm, (0, 0, 0), _AXIS_ROT[axis] if rot is None else rot)
    apply_transforms(ob, rot=True, scale=True)
    ob.location = loc
    return ob


def grooves(name, count, pitch, size, loc=(0, 0, 0), axis=(0, 1, 0), rot=(0, 0, 0)):
    """One object made of `count` boxes spaced by `pitch` along `axis` - use as a boolean cutter
    for slide serrations, cooling fins, ladder rails."""
    ax = Vector(axis).normalized()
    bm = bmesh.new()
    for i in range(count):
        t = (i - (count - 1) * 0.5) * pitch
        sub = bmesh.new()
        bmesh.ops.create_cube(sub, size=1.0)
        bmesh.ops.scale(sub, vec=Vector(size), verts=sub.verts)
        bmesh.ops.translate(sub, vec=ax * t, verts=sub.verts)
        me = bpy.data.meshes.new('_tmp')
        sub.to_mesh(me)
        sub.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    return _finalise(name, bm, loc, rot)


def checkering(name, w, h, nu=14, nv=18, depth=0.0008, thick=0.0012, dome=0.0):
    """A CLOSED slab of diamond checkering lying in the local XY plane, points toward +Z.
    Place it with `place()`; it is meant to sit on a surface, not to be booleaned."""
    bm = bmesh.new()
    du, dv = w / nu, h / nv
    grid = {}

    def zc(x, y):
        if dome <= 0:
            return 0.0
        t = min(1.0, abs(y) / (h * .5))
        return -dome * t * t

    for i in range(nu + 1):
        for j in range(nv + 1):
            x, y = -w * .5 + i * du, -h * .5 + j * dv
            grid[(i, j)] = bm.verts.new((x, y, zc(x, y)))
    for i in range(nu):
        for j in range(nv):
            x, y = -w * .5 + (i + .5) * du, -h * .5 + (j + .5) * dv
            c = bm.verts.new((x, y, zc(x, y) + depth))
            q = (grid[(i, j)], grid[(i + 1, j)], grid[(i + 1, j + 1)], grid[(i, j + 1)])
            for k in range(4):
                bm.faces.new((q[k], q[(k + 1) % 4], c))
    # back plate + rim
    back = {}
    for i in range(nu + 1):
        for j in range(nv + 1):
            if i in (0, nu) or j in (0, nv):
                x, y = -w * .5 + i * du, -h * .5 + j * dv
                back[(i, j)] = bm.verts.new((x, y, zc(x, y) - thick))
    border = ([(i, 0) for i in range(nu + 1)] + [(nu, j) for j in range(1, nv + 1)]
              + [(i, nv) for i in range(nu - 1, -1, -1)] + [(0, j) for j in range(nv - 1, 0, -1)])
    for k in range(len(border)):
        a0, b0 = border[k], border[(k + 1) % len(border)]
        bm.faces.new((grid[a0], grid[b0], back[b0], back[a0]))
    bm.faces.new([back[k] for k in reversed(border)])
    ob = _finalise(name, bm)
    merge_doubles(ob, 1e-6)
    return ob


def place(ob, origin, x_dir, z_dir):
    """Bake a placement into the mesh: local +X -> x_dir, local +Z -> z_dir, origin -> origin."""
    xd = Vector(x_dir).normalized()
    zd = Vector(z_dir).normalized()
    yd = zd.cross(xd).normalized()
    zd = xd.cross(yd).normalized()
    m = Matrix(((xd.x, yd.x, zd.x, origin[0]),
                (xd.y, yd.y, zd.y, origin[1]),
                (xd.z, yd.z, zd.z, origin[2]),
                (0, 0, 0, 1)))
    ob.data.transform(m)
    return ob


def sight_post(name, w=0.0026, t=0.0022, hgt=0.006, loc=(0, 0, 0), ramp=True):
    """Front sight blade: a post with a ramped front face."""
    if ramp:
        pts = [(-w * .5, 0), (w * .5, 0), (w * .5, hgt), (-w * .5, hgt * 0.92)]
        ob = prism(name, pts, -t * .5, t * .5)
    else:
        ob = rbox(name, (w, t, hgt), (0, 0, hgt * .5))
    ob.location = loc
    return ob


def rear_notch(name, w=0.012, t=0.004, hgt=0.006, notch_w=0.0034, notch_d=0.0034, loc=(0, 0, 0),
               vee=False):
    """Rear sight blade with a notch in the top centre.  The object origin is at the BASE of the
    blade, so the notch floor ends up at exactly loc.z + hgt - notch_d (put `aim` there)."""
    ob = rbox(name, (w, t, hgt), (0, 0, 0))
    ob.data.transform(Matrix.Translation((0, 0, hgt * 0.5)))     # base at local z = 0
    if vee:
        c = prism(name + '_c', [(-notch_w, hgt - notch_d), (notch_w, hgt - notch_d),
                                (notch_w * 1.6, hgt + notch_d), (-notch_w * 1.6, hgt + notch_d)],
                  -t * 1.5, t * 1.5)
    else:
        c = rbox(name + '_c', (notch_w, t * 3, notch_d * 2), (0, 0, hgt))
    boolean(ob, c, 'DIFFERENCE')
    ob.location = loc
    return ob


# ---------------------------------------------------------------------------
#  Baked material library
# ---------------------------------------------------------------------------

_MAT_CACHE = {}
BAKE_SIZE = 512


def _nodes(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type not in ('OUTPUT_MATERIAL', 'BSDF_PRINCIPLED'):
            nt.nodes.remove(n)
    return nt, nt.nodes.get('Principled BSDF')


def _seamless(nt, ru=None, rv=None):
    """Seamless (torus-embedded) 4D coordinates from the UV layer.

    Returns (vector_socket, w_socket).  ru/rv scale the feature size along U and V
    (1.0 = one noise unit per UV tile; smaller = stretched features along that axis)."""
    ru = 1.0 if ru is None else ru
    rv = ru if rv is None else rv
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['UV'], sep.inputs[0])

    def trig(op, sock, mul):
        a = nt.nodes.new('ShaderNodeMath')
        a.operation = 'MULTIPLY'
        a.inputs[1].default_value = TAU
        nt.links.new(sock, a.inputs[0])
        f = nt.nodes.new('ShaderNodeMath')
        f.operation = op
        nt.links.new(a.outputs[0], f.inputs[0])
        m = nt.nodes.new('ShaderNodeMath')
        m.operation = 'MULTIPLY'
        m.inputs[1].default_value = mul / TAU
        nt.links.new(f.outputs[0], m.inputs[0])
        return m.outputs[0]

    comb = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(trig('COSINE', sep.outputs['X'], ru), comb.inputs['X'])
    nt.links.new(trig('SINE', sep.outputs['X'], ru), comb.inputs['Y'])
    nt.links.new(trig('COSINE', sep.outputs['Y'], rv), comb.inputs['Z'])
    w = trig('SINE', sep.outputs['Y'], rv)
    return comb.outputs[0], w


def _noise(nt, vec, w, scale=8.0, detail=6.0, rough=0.5, distortion=0.0, dim='4D'):
    n = nt.nodes.new('ShaderNodeTexNoise')
    n.noise_dimensions = dim
    nt.links.new(vec, n.inputs['Vector'])
    if 'W' in n.inputs:
        nt.links.new(w, n.inputs['W'])
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = detail
    n.inputs['Roughness'].default_value = rough
    if 'Distortion' in n.inputs:
        n.inputs['Distortion'].default_value = distortion
    return n.outputs['Fac']


def _voronoi(nt, vec, w, scale=20.0, randomness=1.0, feature='F1', out='Distance', dim='4D'):
    n = nt.nodes.new('ShaderNodeTexVoronoi')
    n.voronoi_dimensions = dim
    n.feature = feature
    nt.links.new(vec, n.inputs['Vector'])
    if 'W' in n.inputs:
        nt.links.new(w, n.inputs['W'])
    n.inputs['Scale'].default_value = scale
    n.inputs['Randomness'].default_value = randomness
    return n.outputs[out]


def _ramp(nt, fac, stops, interp='LINEAR'):
    r = nt.nodes.new('ShaderNodeValToRGB')
    r.color_ramp.interpolation = interp
    el = r.color_ramp.elements
    while len(el) > 1:
        el.remove(el[-1])
    for i, (pos, col) in enumerate(stops):
        e = el[0] if i == 0 else el.new(pos)
        e.position = pos
        e.color = (*col[:3], 1.0) if len(col) >= 3 else (col[0], col[0], col[0], 1.0)
    nt.links.new(fac, r.inputs['Fac'])
    return r.outputs['Color']


def _mix(nt, fac, a, b, blend='MIX', dtype='RGBA'):
    m = nt.nodes.new('ShaderNodeMix')
    m.data_type = dtype
    m.blend_type = blend
    m.clamp_result = True
    fi, ai, bi = (0, 6, 7) if dtype == 'RGBA' else (0, 2, 3)
    if hasattr(fac, 'name'):
        nt.links.new(fac, m.inputs[fi])
    else:
        m.inputs[fi].default_value = fac
    for sock, val in ((ai, a), (bi, b)):
        if hasattr(val, 'name'):
            nt.links.new(val, m.inputs[sock])
        elif dtype == 'RGBA':
            m.inputs[sock].default_value = (*val[:3], 1.0)
        else:
            m.inputs[sock].default_value = val
    return m.outputs['Result']


def _math(nt, op, a, b=None, c=None, clamp=False):
    m = nt.nodes.new('ShaderNodeMath')
    m.operation = op
    m.use_clamp = clamp
    for i, v in enumerate((a, b, c)):
        if v is None:
            continue
        if hasattr(v, 'name'):
            nt.links.new(v, m.inputs[i])
        else:
            m.inputs[i].default_value = v
    return m.outputs[0]


def _bump(nt, bsdf, height, strength=0.3, distance=1.0):
    b = nt.nodes.new('ShaderNodeBump')
    b.inputs['Strength'].default_value = strength
    b.inputs['Distance'].default_value = distance
    nt.links.new(height, b.inputs['Height'])
    nt.links.new(b.outputs['Normal'], bsdf.inputs['Normal'])
    return b


# --- procedural definitions -------------------------------------------------

def _b_blued(mat):
    nt, bsdf = _nodes(mat)
    v, w = _seamless(nt, 0.055, 2.0)            # stretched along U = machining marks
    vi, wi = _seamless(nt, 1.0, 1.0)
    lines = _noise(nt, v, w, scale=48, detail=3, rough=0.62)
    blotch = _noise(nt, vi, wi, scale=5, detail=8, rough=0.6)
    wear = _noise(nt, vi, wi, scale=9, detail=5, rough=0.6)
    wear_m = _ramp(nt, wear, [(0.60, (0, 0, 0)), (0.74, (1, 1, 1))])
    base = _ramp(nt, blotch, [(0.30, (0.0255, 0.0270, 0.0345)), (0.72, (0.0560, 0.0590, 0.0720))])
    base = _mix(nt, _math(nt, 'MULTIPLY', lines, 0.20), base, (0.0620, 0.0650, 0.0780))
    base = _mix(nt, _math(nt, 'MULTIPLY', wear_m, 0.55), base, (0.230, 0.234, 0.244))
    bsdf.inputs['Base Color'].default_value = (0.03, 0.031, 0.036, 1)
    nt.links.new(base, bsdf.inputs['Base Color'])
    rough = _mix(nt, blotch, 0.19, 0.31, dtype='FLOAT')
    rough = _mix(nt, _math(nt, 'MULTIPLY', lines, 0.45), rough, 0.34, dtype='FLOAT')
    rough = _mix(nt, _math(nt, 'MULTIPLY', wear_m, 0.7), rough, 0.15, dtype='FLOAT')
    nt.links.new(rough, bsdf.inputs['Roughness'])
    h = _mix(nt, 0.35, lines, blotch)
    _bump(nt, bsdf, h, 0.07)


def _b_parker(mat):
    nt, bsdf = _nodes(mat)
    v, w = _seamless(nt, 1.0, 1.0)
    vl, wl = _seamless(nt, 0.14, 2.0)
    grain = _voronoi(nt, v, w, scale=110, randomness=1.0)
    grain2 = _noise(nt, v, w, scale=40, detail=6, rough=0.75)
    big = _noise(nt, v, w, scale=4.0, detail=7, rough=0.6)
    scratch = _ramp(nt, _noise(nt, vl, wl, scale=30, detail=2, rough=0.8), [(0.62, (0, 0, 0)), (0.70, (1, 1, 1))])
    wear = _ramp(nt, _noise(nt, v, w, scale=7, detail=6, rough=0.55), [(0.63, (0, 0, 0)), (0.78, (1, 1, 1))])
    base = _ramp(nt, big, [(0.28, (0.0190, 0.0195, 0.0190)), (0.75, (0.0400, 0.0405, 0.0395))])
    base = _mix(nt, _math(nt, 'MULTIPLY', grain2, 0.28), base, (0.0125, 0.0130, 0.0125))
    base = _mix(nt, _math(nt, 'MULTIPLY', wear, 0.5), base, (0.125, 0.127, 0.132))
    base = _mix(nt, _math(nt, 'MULTIPLY', scratch, 0.45), base, (0.200, 0.202, 0.208))
    nt.links.new(base, bsdf.inputs['Base Color'])
    rough = _mix(nt, big, 0.62, 0.78, dtype='FLOAT')
    rough = _mix(nt, _math(nt, 'MULTIPLY', wear, 0.8), rough, 0.30, dtype='FLOAT')
    rough = _mix(nt, _math(nt, 'MULTIPLY', scratch, 0.7), rough, 0.22, dtype='FLOAT')
    nt.links.new(rough, bsdf.inputs['Roughness'])
    h = _mix(nt, 0.7, _math(nt, 'MULTIPLY', grain, 1.0), grain2)
    _bump(nt, bsdf, h, 0.15)


def _b_steel(mat):
    nt, bsdf = _nodes(mat)
    v, w = _seamless(nt, 0.06, 2.0)
    vi, wi = _seamless(nt, 1.0, 1.0)
    lines = _noise(nt, v, w, scale=34, detail=3, rough=0.75)
    blotch = _noise(nt, vi, wi, scale=6, detail=6, rough=0.55)
    base = _ramp(nt, blotch, [(0.25, (0.33, 0.335, 0.345)), (0.8, (0.48, 0.485, 0.495))])
    base = _mix(nt, _math(nt, 'MULTIPLY', lines, 0.5), base, (0.56, 0.565, 0.58))
    nt.links.new(base, bsdf.inputs['Base Color'])
    rough = _mix(nt, lines, 0.13, 0.30, dtype='FLOAT')
    rough = _mix(nt, blotch, rough, 0.24, dtype='FLOAT')
    nt.links.new(rough, bsdf.inputs['Roughness'])
    _bump(nt, bsdf, lines, 0.10)


def _b_brass(mat):
    nt, bsdf = _nodes(mat)
    v, w = _seamless(nt, 0.10, 2.0)
    vi, wi = _seamless(nt, 1.0, 1.0)
    lines = _noise(nt, v, w, scale=26, detail=3, rough=0.7)
    patina = _noise(nt, vi, wi, scale=8, detail=7, rough=0.6)
    base = _ramp(nt, patina, [(0.25, (0.40, 0.27, 0.085)), (0.8, (0.66, 0.50, 0.19))])
    base = _mix(nt, _math(nt, 'MULTIPLY', lines, 0.4), base, (0.72, 0.58, 0.26))
    nt.links.new(base, bsdf.inputs['Base Color'])
    nt.links.new(_mix(nt, patina, 0.20, 0.42, dtype='FLOAT'), bsdf.inputs['Roughness'])
    _bump(nt, bsdf, lines, 0.08)


def _b_polymer(mat):
    nt, bsdf = _nodes(mat)
    v, w = _seamless(nt, 1.0, 1.0)
    pebble = _voronoi(nt, v, w, scale=95, randomness=1.0)
    pebble = _ramp(nt, pebble, [(0.0, (0, 0, 0)), (0.28, (1, 1, 1))])
    fine = _noise(nt, v, w, scale=160, detail=2, rough=0.5)
    big = _noise(nt, v, w, scale=5, detail=6, rough=0.55)
    scuff = _ramp(nt, _noise(nt, v, w, scale=13, detail=6, rough=0.6), [(0.66, (0, 0, 0)), (0.80, (1, 1, 1))])
    base = _ramp(nt, big, [(0.3, (0.0125, 0.0125, 0.0140)), (0.75, (0.0310, 0.0310, 0.0335))])
    base = _mix(nt, _math(nt, 'MULTIPLY', pebble, 0.30), base, (0.006, 0.006, 0.007))
    base = _mix(nt, _math(nt, 'MULTIPLY', scuff, 0.5), base, (0.075, 0.073, 0.072))
    nt.links.new(base, bsdf.inputs['Base Color'])
    rough = _mix(nt, pebble, 0.58, 0.40, dtype='FLOAT')
    rough = _mix(nt, big, rough, 0.50, dtype='FLOAT')
    rough = _mix(nt, _math(nt, 'MULTIPLY', scuff, 0.8), rough, 0.30, dtype='FLOAT')
    nt.links.new(rough, bsdf.inputs['Roughness'])
    h = _mix(nt, 0.30, pebble, fine)
    _bump(nt, bsdf, h, 0.22)


def _b_rubber(mat):
    nt, bsdf = _nodes(mat)
    v, w = _seamless(nt, 1.0, 1.0)
    cell = _voronoi(nt, v, w, scale=55, randomness=1.0)
    cell = _ramp(nt, cell, [(0.0, (0, 0, 0)), (0.35, (1, 1, 1))])
    big = _noise(nt, v, w, scale=6, detail=6, rough=0.55)
    base = _ramp(nt, big, [(0.3, (0.0095, 0.0095, 0.0102)), (0.8, (0.0235, 0.0235, 0.0250))])
    base = _mix(nt, _math(nt, 'MULTIPLY', cell, 0.4), base, (0.004, 0.004, 0.0045))
    nt.links.new(base, bsdf.inputs['Base Color'])
    nt.links.new(_mix(nt, big, 0.74, 0.90, dtype='FLOAT'), bsdf.inputs['Roughness'])
    _bump(nt, bsdf, cell, 0.5)


def _wood(mat, c_dark, c_mid, c_light, pore=0.5, gloss=0.30):
    nt, bsdf = _nodes(mat)
    v, w = _seamless(nt, 0.045, 1.6)         # grain stretched along U
    vf, wf = _seamless(nt, 0.02, 2.4)
    vi, wi = _seamless(nt, 1.0, 1.0)
    grain = _noise(nt, v, w, scale=6.5, detail=8, rough=0.62, distortion=0.9)
    rings = _ramp(nt, grain, [(0.30, (0, 0, 0)), (0.44, (1, 1, 1)), (0.56, (0.15, 0.15, 0.15)),
                              (0.70, (0.85, 0.85, 0.85))], interp='B_SPLINE')
    fibre = _noise(nt, vf, wf, scale=40, detail=4, rough=0.7)
    figure = _noise(nt, vi, wi, scale=3.0, detail=7, rough=0.6)
    handle = _ramp(nt, _noise(nt, vi, wi, scale=4.5, detail=6, rough=0.55),
                   [(0.40, (0, 0, 0)), (0.70, (1, 1, 1))])
    base = _mix(nt, rings, c_dark, c_mid)
    base = _mix(nt, _math(nt, 'MULTIPLY', figure, 0.55), base, c_light)
    base = _mix(nt, _math(nt, 'MULTIPLY', fibre, 0.22), base, c_dark)
    # dark worn handling marks: oil/dirt in the grain, polished sheen
    dark = tuple(x * 0.45 for x in c_dark)
    base = _mix(nt, _math(nt, 'MULTIPLY', handle, 0.45), base, dark)
    nt.links.new(base, bsdf.inputs['Base Color'])
    rough = _mix(nt, rings, gloss + 0.22, gloss, dtype='FLOAT')
    rough = _mix(nt, _math(nt, 'MULTIPLY', fibre, 0.5), rough, gloss + 0.28, dtype='FLOAT')
    rough = _mix(nt, _math(nt, 'MULTIPLY', handle, 0.85), rough, gloss - 0.14, dtype='FLOAT')
    nt.links.new(rough, bsdf.inputs['Roughness'])
    bsdf.inputs['Specular IOR Level'].default_value = 0.5
    h = _mix(nt, pore, _math(nt, 'MULTIPLY', fibre, 1.0), rings)
    _bump(nt, bsdf, h, 0.22)


def _b_walnut(mat):
    _wood(mat, (0.0080, 0.0033, 0.0015), (0.0270, 0.0118, 0.0052), (0.0520, 0.0250, 0.0112), 0.62, 0.30)


def _b_birch(mat):
    _wood(mat, (0.038, 0.021, 0.0090), (0.098, 0.060, 0.027), (0.168, 0.112, 0.057), 0.55, 0.36)


def _b_sleeve(mat):
    nt, bsdf = _nodes(mat)
    vu, wu = _seamless(nt, 0.035, 3.0)
    vv, wv = _seamless(nt, 3.0, 0.035)
    vi, wi = _seamless(nt, 1.0, 1.0)
    warp = _noise(nt, vu, wu, scale=55, detail=2, rough=0.5)
    weft = _noise(nt, vv, wv, scale=55, detail=2, rough=0.5)
    weave = _math(nt, 'MULTIPLY', _math(nt, 'ADD', warp, weft), 0.5)
    dirt = _noise(nt, vi, wi, scale=5, detail=8, rough=0.62)
    fade = _noise(nt, vi, wi, scale=1.7, detail=5, rough=0.5)
    base = _ramp(nt, fade, [(0.25, (0.0265, 0.0295, 0.0170)), (0.8, (0.0480, 0.0520, 0.0300))])
    base = _mix(nt, _math(nt, 'MULTIPLY', weave, 0.55), base, (0.0165, 0.0185, 0.0110))
    base = _mix(nt, _math(nt, 'MULTIPLY', _ramp(nt, dirt, [(0.55, (0, 0, 0)), (0.85, (1, 1, 1))]), 0.55),
                base, (0.055, 0.046, 0.032))
    nt.links.new(base, bsdf.inputs['Base Color'])
    nt.links.new(_mix(nt, weave, 0.96, 0.80, dtype='FLOAT'), bsdf.inputs['Roughness'])
    bsdf.inputs['Specular IOR Level'].default_value = 0.25
    _bump(nt, bsdf, weave, 0.55)


def _b_glove(mat):
    """Dark oiled work-glove leather: pebble grain, knuckle creases, worn sheen."""
    nt, bsdf = _nodes(mat)
    v, w = _seamless(nt, 1.0, 1.0)
    vc, wc = _seamless(nt, 0.55, 1.1)
    cells = _voronoi(nt, v, w, scale=34, randomness=1.0)
    cells = _ramp(nt, cells, [(0.0, (0, 0, 0)), (0.30, (1, 1, 1))])
    fine = _noise(nt, v, w, scale=110, detail=3, rough=0.55)
    crease = _noise(nt, vc, wc, scale=7, detail=7, rough=0.62, distortion=1.8)
    crease_m = _ramp(nt, crease, [(0.40, (1, 1, 1)), (0.50, (0, 0, 0)), (0.60, (1, 1, 1))])
    dirt = _noise(nt, v, w, scale=3, detail=8, rough=0.6)
    rub = _ramp(nt, _noise(nt, v, w, scale=9, detail=6, rough=0.55),
                [(0.58, (0, 0, 0)), (0.76, (1, 1, 1))])       # polished/worn high spots
    base = _ramp(nt, dirt, [(0.25, (0.0120, 0.0078, 0.0048)), (0.80, (0.0335, 0.0228, 0.0148))])
    base = _mix(nt, _math(nt, 'MULTIPLY', cells, 0.40), base, (0.0090, 0.0056, 0.0034))
    base = _mix(nt, _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', 1.0, crease_m, clamp=True), 0.60),
                base, (0.0062, 0.0038, 0.0022))
    base = _mix(nt, _math(nt, 'MULTIPLY', rub, 0.45), base, (0.0560, 0.0410, 0.0280))
    nt.links.new(base, bsdf.inputs['Base Color'])
    rough = _mix(nt, cells, 0.58, 0.47, dtype='FLOAT')
    rough = _mix(nt, dirt, rough, 0.62, dtype='FLOAT')
    rough = _mix(nt, _math(nt, 'MULTIPLY', rub, 0.9), rough, 0.40, dtype='FLOAT')
    nt.links.new(rough, bsdf.inputs['Roughness'])
    bsdf.inputs['Specular IOR Level'].default_value = 0.55
    h = _mix(nt, 0.35, _mix(nt, 0.50, cells, fine), crease_m)
    _bump(nt, bsdf, h, 0.26)


def _b_glove_dark(mat):
    _b_glove(mat)
    nt = mat.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    src = bsdf.inputs['Base Color'].links[0].from_socket
    m = nt.nodes.new('ShaderNodeMix')
    m.data_type = 'RGBA'
    m.blend_type = 'MULTIPLY'
    m.inputs[0].default_value = 1.0
    nt.links.new(src, m.inputs[6])
    m.inputs[7].default_value = (0.42, 0.40, 0.44, 1.0)
    nt.links.new(m.outputs['Result'], bsdf.inputs['Base Color'])


def _b_skin(mat):
    nt, bsdf = _nodes(mat)
    v, w = _seamless(nt, 1.0, 1.0)
    pore = _voronoi(nt, v, w, scale=240, randomness=1.0)
    blotch = _noise(nt, v, w, scale=8, detail=7, rough=0.6)
    base = _ramp(nt, blotch, [(0.25, (0.235, 0.128, 0.086)), (0.8, (0.365, 0.215, 0.152))])
    nt.links.new(base, bsdf.inputs['Base Color'])
    nt.links.new(_mix(nt, blotch, 0.50, 0.62, dtype='FLOAT'), bsdf.inputs['Roughness'])
    _bump(nt, bsdf, pore, 0.18)


def _b_paint(mat, col, rough=0.42, chip=(0.10, 0.10, 0.11)):
    nt, bsdf = _nodes(mat)
    v, w = _seamless(nt, 1.0, 1.0)
    vl, wl = _seamless(nt, 0.10, 2.0)
    orange = _noise(nt, v, w, scale=70, detail=3, rough=0.5)
    big = _noise(nt, v, w, scale=5, detail=7, rough=0.6)
    chips = _ramp(nt, _noise(nt, v, w, scale=26, detail=7, rough=0.65), [(0.70, (0, 0, 0)), (0.76, (1, 1, 1))])
    scratch = _ramp(nt, _noise(nt, vl, wl, scale=26, detail=2, rough=0.8), [(0.64, (0, 0, 0)), (0.72, (1, 1, 1))])
    dark = tuple(x * 0.62 for x in col)
    light = tuple(min(1.0, x * 1.25 + 0.02) for x in col)
    base = _ramp(nt, big, [(0.3, dark), (0.8, light)])
    base = _mix(nt, _math(nt, 'MULTIPLY', chips, 0.85), base, chip)
    base = _mix(nt, _math(nt, 'MULTIPLY', scratch, 0.35), base, (0.22, 0.21, 0.20))
    nt.links.new(base, bsdf.inputs['Base Color'])
    r = _mix(nt, orange, rough, rough + 0.12, dtype='FLOAT')
    r = _mix(nt, _math(nt, 'MULTIPLY', chips, 0.9), r, 0.72, dtype='FLOAT')
    nt.links.new(r, bsdf.inputs['Roughness'])
    _bump(nt, bsdf, _mix(nt, 0.5, orange, chips), 0.20)


def _b_red(mat):
    _b_paint(mat, (0.255, 0.028, 0.020), 0.32)


def _b_cream(mat):
    _b_paint(mat, (0.520, 0.455, 0.330), 0.40)


_METALLIC = {
    'metal_blued': 0.92, 'metal_parker': 0.88, 'metal_steel': 0.96, 'metal_brass': 0.96,
    'metal_red_enamel': 0.0, 'polymer_cream': 0.0,
}

_BAKERS = {
    'metal_blued': _b_blued,
    'metal_parker': _b_parker,
    'metal_steel': _b_steel,
    'metal_brass': _b_brass,
    'polymer_black': _b_polymer,
    'polymer_rubber': _b_rubber,
    'wood_walnut': _b_walnut,
    'wood_birch': _b_birch,
    'sleeve_olive': _b_sleeve,
    'glove_leather': _b_glove,
    'glove_leather_dark': _b_glove_dark,
    'skin_hand': _b_skin,
    'metal_red_enamel': _b_red,
    'polymer_cream': _b_cream,
}


def M(name, force=False):
    """Get a baked material by name (see _BAKERS).  Textures are cached on disk."""
    if name in _MAT_CACHE and not force:
        return _MAT_CACHE[name]
    if name not in _BAKERS:
        raise KeyError('unknown material ' + name)
    tex = bake_tileable(name, _BAKERS[name], size=BAKE_SIZE,
                        passes=('DIFFUSE', 'ROUGHNESS', 'NORMAL'), samples=12, force=force)
    metallic = _METALLIC.get(name, 0.0)
    mat = pbr_material(name, (0.6, 0.6, 0.6), 0.5, metallic,
                       base_tex=tex['DIFFUSE'], rough_tex=tex['ROUGHNESS'],
                       normal_tex=tex['NORMAL'], normal_strength=1.0)
    _MAT_CACHE[name] = mat
    return mat


def plain(name, color, rough=0.5, metallic=0.0, emission=None, strength=0.0):
    key = '~' + name
    if key in _MAT_CACHE:
        return _MAT_CACHE[key]
    m = pbr_material(name, color, rough, metallic, emission=emission, emission_strength=strength)
    _MAT_CACHE[key] = m
    return m


def prebake(names=None, force=False):
    """Bake the whole library up front (one Cycles session) so per-weapon builds are quick."""
    for n in (names or list(_BAKERS)):
        M(n, force=force)


# ---------------------------------------------------------------------------
#  Parametric gloved hand + arm
# ---------------------------------------------------------------------------

MB_S = 10.0            # metaballs are authored 10x up (Blender clamps resolution at 0.005)
MB_STIFF = 5.0
MB_K = 0.712           # surface offset = MB_K * element radius  (measured)

# finger -> (knuckle x, y, z), segment lengths, radii per joint, spread deg, droop deg
_FINGERS = [
    ('index',  (-0.0295, 0.0975, 0.0000), (0.0440, 0.0270, 0.0215), (0.0108, 0.0100, 0.0089, 0.0078), -5.0, 2.0),
    ('middle', (-0.0098, 0.1040, 0.0020), (0.0480, 0.0308, 0.0230), (0.0113, 0.0104, 0.0093, 0.0081), -1.0, 1.0),
    ('ring',   (0.0102, 0.1005, 0.0005), (0.0450, 0.0290, 0.0220), (0.0106, 0.0098, 0.0087, 0.0077), 3.5, 2.0),
    ('pinky',  (0.0292, 0.0905, -0.0035), (0.0360, 0.0225, 0.0200), (0.0095, 0.0088, 0.0079, 0.0070), 9.0, 4.0),
]
_MCP, _PIP, _DIP = 92.0, 104.0, 68.0


def _mb_k(stiff):
    """Surface offset factor: surface sits at k*radius from an isolated element core."""
    return math.sqrt(max(1e-6, 1.0 - (0.6 / stiff) ** (1.0 / 3.0)))


def _mb_elem(mb, kind, co, radius, size=(0, 0, 0), quat=None, negative=False, stiff=MB_STIFF):
    e = mb.elements.new()
    e.type = kind
    e.co = Vector(co) * MB_S
    e.radius = radius * MB_S / _mb_k(stiff)
    e.stiffness = stiff
    e.size_x, e.size_y, e.size_z = size
    if quat is not None:
        e.rotation = quat
    e.use_negative = negative
    return e


def _mb_capsule(mb, p0, p1, r, stiff=MB_STIFF, negative=False):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    L = d.length
    if L < 1e-6:
        return _mb_elem(mb, 'BALL', p0, r, stiff=stiff, negative=negative)
    q = Vector((1, 0, 0)).rotation_difference(d.normalized())
    half = max(0.0, (L * 0.5) * MB_S)
    return _mb_elem(mb, 'CAPSULE', (p0 + p1) * 0.5, r, (half, 0, 0), q, negative, stiff)


def _mb_ell(mb, co, half, quat=None, stiff=MB_STIFF, negative=False):
    """Ellipsoid with world half-axes `half` (metres)."""
    rr = max(half)
    size = tuple(h / rr for h in half)
    return _mb_elem(mb, 'ELLIPSOID', co, rr, size, quat, negative, stiff)


def _finger_chain(k, segl, sp, dr, curl, spread):
    """Joint positions of one digit: list of (start, end, rot3x3) per segment."""
    base = (Matrix.Translation(Vector(k))
            @ Matrix.Rotation(D2R(sp * spread), 4, 'Z')
            @ Matrix.Rotation(D2R(-dr), 4, 'X'))
    ang = (_MCP * curl, _PIP * curl, _DIP * curl)
    out = []
    m = base
    p = Vector(k)
    for s in range(3):
        m = m @ Matrix.Rotation(D2R(-ang[s]), 4, 'X')
        nxt = m @ Vector((0, segl[s], 0))
        out.append((p, nxt, m.to_3x3()))
        m = Matrix.Translation(nxt) @ m.to_3x3().to_4x4()
        p = nxt
    return out


def hand_chains(curl=(0.85, 0.90, 0.92, 0.92), spread=1.0, thumb_curl=0.55,
                thumb_abduct=0.0, thumb_roll=0.0):
    """Skeleton of one hand, shared by the metaball body and the seam geometry.
    Returns (fingers, thumb) where each digit is (segments, radii) and each segment is
    (start, end, rot3x3)."""
    out = []
    for i, (nm, k, segl, rr, sp, dr) in enumerate(_FINGERS):
        c = curl[i] if hasattr(curl, '__len__') else curl
        out.append((_finger_chain(k, segl, sp, dr, c, spread), rr))
    tc = thumb_curl
    cmc = Vector((-0.0285, 0.0255, -0.0060))
    tm = (Matrix.Translation(cmc)
          @ Matrix.Rotation(D2R(62 + thumb_abduct), 4, 'Z')
          @ Matrix.Rotation(D2R(-30 + thumb_roll), 4, 'Y')
          @ Matrix.Rotation(D2R(-14 - 26 * tc), 4, 'X'))
    seg = (0.0405, 0.0325, 0.0260)
    rad = (0.0128, 0.0110, 0.0096, 0.0084)
    ang = (0.0, 40 * tc, 54 * tc)
    p, m, tch = cmc.copy(), tm, []
    for s in range(3):
        m = m @ Matrix.Rotation(D2R(-ang[s]), 4, 'X')
        nxt = m @ Vector((0, seg[s], 0))
        tch.append((p, nxt, m.to_3x3()))
        m = Matrix.Translation(nxt) @ m.to_3x3().to_4x4()
        p = nxt
    return out, (tch, rad)


def build_hand(name, side='R', curl=(0.85, 0.90, 0.92, 0.92), spread=1.0,
               thumb_curl=0.55, thumb_abduct=0.0, thumb_roll=0.0, res=0.0030,
               target_tris=2330, fat=1.0):
    """Gloved hand, no cuff.  Local frame: wrist at origin, fingers toward +Y, back of hand
    toward +Z, thumb toward -X (right hand)."""
    mb = bpy.data.metaballs.new(name + '_mb')
    mb.resolution = max(0.005, res * MB_S)
    mb.render_resolution = mb.resolution
    mb.threshold = 0.6
    ob = bpy.data.objects.new(name + '_mb', mb)
    link(ob)
    S = 9.0                       # high stiffness -> tight blends, fingers stay distinct
    fingers, (tch, trad) = hand_chains(curl, spread, thumb_curl, thumb_abduct, thumb_roll)

    # ---- palm: a flat slab built from several low blobs --------------------
    for co, half in (
            ((0.000, 0.0610, 0.0000), (0.0385, 0.0330, 0.0136)),      # main block
            ((0.000, 0.0925, 0.0010), (0.0385, 0.0120, 0.0128)),      # knuckle bar
            ((0.000, 0.0230, -0.0005), (0.0288, 0.0180, 0.0124)),     # heel
            ((-0.0225, 0.0390, -0.0050), (0.0164, 0.0250, 0.0138)),   # thenar
            ((0.0255, 0.0450, -0.0030), (0.0108, 0.0250, 0.0116)),    # hypothenar
            ((0.0000, -0.0035, 0.0000), (0.0213, 0.0105, 0.0116))):   # wrist stump
        _mb_ell(mb, co, tuple(h * fat for h in half), stiff=S)
    for nm, k, segl, rr, sp, dr in _FINGERS:
        _mb_ell(mb, (k[0], k[1] - 0.005, k[2] + 0.0052),
                (rr[0] * 0.84, rr[0] * 1.08, rr[0] * 0.60), stiff=S)

    # ---- fingers ----------------------------------------------------------
    for i, (ch, rr) in enumerate(fingers):
        for s, (p, nxt, rot) in enumerate(ch):
            r0, r1 = rr[s] * fat, rr[s + 1] * fat
            _mb_capsule(mb, p, nxt, (r0 + r1) * 0.5 * 0.95, stiff=S)
            if s < 2:
                _mb_ell(mb, nxt, (r1 * 1.06, r1 * 0.38, r1 * 1.10), stiff=S)
                pv = (nxt - p).normalized()
                _mb_ell(mb, nxt - pv * r1 * 0.95, (r1 * 0.55, r1 * 0.20, r1 * 0.62),
                        stiff=2.4, negative=True)
                # crease loop over the PIP/DIP: narrow along the bone so it cuts a line, not a
                # dent, and biased to the FLEXION (palm) side, which is where a glove folds -
                # and away from the dorsal seam ridge, which would otherwise float off the
                # surface where the crease indents it
                # (keep it mild: a very flat negative here fragments the isosurface and the
                # metaball tessellation time explodes)
                dz = (rot @ Vector((0, 0, 1))).normalized()
                _mb_ell(mb, nxt - pv * r1 * 1.05 - dz * r1 * 0.30,
                        (r1 * 0.62, r1 * 0.20, r1 * 0.40), stiff=2.2, negative=True)
        tip = ch[-1][1]
        _mb_ell(mb, tip, (rr[3] * 0.90 * fat, rr[3] * 0.86 * fat, rr[3] * 0.90 * fat), stiff=S)

    # ---- grooves between the fingers (and into the web) --------------------
    for i in range(3):
        a, b = fingers[i][0], fingers[i + 1][0]
        for s in range(3):
            for t in (0.0, 0.22, 0.5, 0.78, 1.0):
                pa = a[s][0].lerp(a[s][1], t)
                pb = b[s][0].lerp(b[s][1], t)
                mid = (pa + pb) * 0.5
                gap = (pb - pa).length
                _mb_ell(mb, mid, (gap * 0.26, gap * 0.26, gap * 0.82),
                        stiff=2.0, negative=True)
        # carry the split a little way back into the knuckle bar
        w0 = (a[0][0] + b[0][0]) * 0.5
        _mb_ell(mb, w0 - Vector((0, 0.0075, 0)), (0.0044, 0.0060, 0.0110),
                stiff=2.0, negative=True)
        # webbing fillet: the skin/leather bridge between the finger roots, so the split does
        # not run all the way down to the knuckle bar as a razor slot
        ra, rb = fingers[i][1][0], fingers[i + 1][1][0]
        gap = (b[0][0] - a[0][0]).length
        web = (a[0][0] + b[0][0]) * 0.5 + Vector((0, 0.0028, -0.0042))
        _mb_ell(mb, web, (gap * 0.28, (ra + rb) * 0.26, (ra + rb) * 0.22), stiff=S)

    # ---- thumb ------------------------------------------------------------
    for s, (p, nxt, rot) in enumerate(tch):
        _mb_capsule(mb, p, nxt, (trad[s] + trad[s + 1]) * 0.5 * fat * 0.96, stiff=S)
        if s < 2:
            r1 = trad[s + 1] * fat
            _mb_ell(mb, nxt, (r1 * 1.06, r1 * 0.40, r1 * 1.10), stiff=S)
            pv = (nxt - p).normalized()
            _mb_ell(mb, nxt - pv * r1 * 0.95, (r1 * 0.55, r1 * 0.20, r1 * 0.62),
                    stiff=2.4, negative=True)
    _mb_ell(mb, tch[-1][1], (trad[3] * 0.90 * fat, trad[3] * 0.86 * fat, trad[3] * 0.90 * fat),
            stiff=S)
    # crease where the thumb leaves the thenar pad
    _mb_ell(mb, Vector((-0.0300, 0.0385, -0.0020)), (0.0052, 0.0090, 0.0120),
            stiff=2.0, negative=True)

    # ---- convert ----------------------------------------------------------
    ob.scale = (1.0 / MB_S, 1.0 / MB_S, 1.0 / MB_S)
    act(ob)
    bpy.ops.object.convert(target='MESH')
    ob = bpy.context.active_object
    apply_transforms(ob, rot=True, scale=True)
    ob.name = name
    ob.data.name = name
    merge_doubles(ob, 1e-5)
    ntri = sum(max(0, len(pp.vertices) - 2) for pp in ob.data.polygons)
    if target_tris and ntri > target_tris * 1.12:
        d = ob.modifiers.new('Dec', 'DECIMATE')
        d.ratio = target_tris / float(ntri)
        act(ob)
        bpy.ops.object.modifier_apply(modifier=d.name)
    if side == 'L':
        _mirror_x(ob)
    return ob


def _ridge(name, samples, w=0.0011, h=0.0010, sink=0.0004):
    """A thin welt/stitch ridge lying on a surface.  `samples` = [(point, normal, tangent)]."""
    rings = []
    for q, n, u in samples:
        n = Vector(n).normalized()
        v = Vector(u).cross(n)
        if v.length < 1e-6:
            continue
        v.normalize()
        q = Vector(q)
        rings.append([q + v * w - n * sink, q + n * h, q - v * w - n * sink])
    if len(rings) < 2:
        return None
    return loft(name, rings, cap_start=True, cap_end=True)


def _digit_seam(chain, radii, per_seg=7, out=(0, 0, 1), scale=0.90):
    """Sample a smooth seam line along the back of a digit.

    The per-segment frames jump by the joint angle, so the offset direction is carried along
    the centreline by parallel transport - otherwise the ridge fans out into a flat plate at
    every knuckle."""
    pts, rads = [], []
    for i, (p0, p1, rot) in enumerate(chain):
        last = (i == len(chain) - 1)
        for k in range(per_seg + (1 if last else 0)):
            t = k / float(per_seg)
            pts.append(p0.lerp(p1, t))
            rads.append(radii[i] + (radii[i + 1] - radii[i]) * t)
    pts.append(chain[-1][1] + (chain[-1][1] - chain[-1][0]).normalized() * radii[-1] * 0.30)
    rads.append(radii[-1] * 0.55)

    n = (chain[0][2] @ Vector(out)).normalized()
    samples = []
    for i, q in enumerate(pts):
        a = pts[max(0, i - 1)]
        b = pts[min(len(pts) - 1, i + 1)]
        u = (b - a)
        if u.length < 1e-9:
            u = (chain[0][1] - chain[0][0])
        u.normalize()
        n = (n - u * n.dot(u))
        if n.length < 1e-6:
            n = Vector((0, 0, 1)) - u * u.z
        n.normalize()
        samples.append((q + n * rads[i] * scale, n.copy(), u.copy()))
    return samples


# palm blobs, mirrored from build_hand: used to lay the back panel on the real surface
_PALM_BLOBS = (((0.000, 0.0610, 0.0000), (0.0385, 0.0330, 0.0136)),
               ((0.000, 0.0925, 0.0010), (0.0385, 0.0120, 0.0128)),
               ((0.000, 0.0230, -0.0005), (0.0288, 0.0180, 0.0124)),
               ((-0.0225, 0.0390, -0.0050), (0.0164, 0.0250, 0.0138)),
               ((0.0255, 0.0450, -0.0030), (0.0108, 0.0250, 0.0116)),
               ((0.0000, -0.0035, 0.0000), (0.0213, 0.0105, 0.0116)))


def _back_z(x, y):
    """Height of the back of the hand: the upper envelope of the palm blobs."""
    best = -1.0
    for (cx, cy, cz), (hx, hy, hz) in _PALM_BLOBS:
        t = 1.0 - ((x - cx) / hx) ** 2 - ((y - cy) / hy) ** 2
        if t > 0.0:
            best = max(best, cz + hz * math.sqrt(t))
    return best if best > -0.5 else 0.0


def _back_halfw(y, zmin=0.0075):
    """Widest x at this y where the back of the hand is still at least `zmin` high."""
    lo, hi = 0.0, 0.045
    if _back_z(0.0, y) < zmin:
        return 0.0
    for _ in range(24):
        mid = (lo + hi) * 0.5
        if _back_z(mid, y) >= zmin:
            lo = mid
        else:
            hi = mid
    return lo


def glove_detail(curl=(0.85, 0.90, 0.92, 0.92), spread=1.0, thumb_curl=0.55,
                 thumb_abduct=0.0, thumb_roll=0.0):
    """Stitched seams and the back-of-hand panel: what actually makes it read as a glove.
    Returns (seam_parts, panel_parts) - the seams take the stitching material."""
    fingers, (tch, trad) = hand_chains(curl, spread, thumb_curl, thumb_abduct, thumb_roll)
    seams, parts = [], []
    for i, (ch, rr) in enumerate(fingers):
        r = _ridge('gl_seam_f%d' % i, _digit_seam(ch, rr), w=0.0006, h=0.0009, sink=0.0026)
        if r:
            seams.append(r)
    r = _ridge('gl_seam_t', _digit_seam(tch, trad), w=0.0007, h=0.0009, sink=0.0026)
    if r:
        seams.append(r)

    # --- back-of-hand panel: a shaped pad with a bevelled edge ---------------
    rings = []
    NY = 9
    for i in range(NY):
        t = i / float(NY - 1)
        y = 0.0175 + (0.0900 - 0.0175) * t
        # a smooth lens outline, tapered at both ends, clamped inside the real palm width
        shape = math.sin(math.pi * (0.13 + 0.74 * t)) ** 0.55
        halfw = min(_back_halfw(y, 0.0090) * 0.80, 0.0300 * shape)
        if halfw < 0.004:
            continue
        top, bot = [], []
        for k in range(7):
            x = -halfw + 2 * halfw * k / 6.0
            z = _back_z(x, y)
            edge = 1.0 if 0 < k < 6 else 0.30
            top.append((x, y, z + 0.0018 * edge))
            bot.append((x, y, z - 0.0055))
        rings.append(top + list(reversed(bot)))
    pad = loft('gl_backpanel', rings, cap_start=True, cap_end=True)
    parts.append(pad)

    # --- knuckle relief bumps on the panel ----------------------------------
    for nm, k, segl, rr, sp, dr in _FINGERS:
        c = (k[0], k[1] - 0.0080, _back_z(k[0], k[1] - 0.0080) - 0.0030)
        b = sphere('gl_knuck_%s' % nm, rr[0] * 0.78, (0, 0, 0), segs=8, scale=(1.0, 1.30, 0.55))
        apply_transforms(b, rot=True, scale=True)
        b.data.transform(Matrix.Translation(Vector(c)))
        parts.append(b)

    # --- nail / fingertip reinforcement plates ------------------------------
    # A shooting glove has a hard patch over the nail of the trigger finger and the thumb;
    # it is also what stops the distal segment reading as a bare tube (weapons_audio.md #11).
    for nm, ch, rr in (('index', fingers[0][0], fingers[0][1]), ('thumb', tch, trad)):
        p0, p1, rot = ch[-1]
        u = (p1 - p0).normalized()
        n = (rot @ Vector((0, 0, 1)))
        n = (n - u * n.dot(u))
        if n.length < 1e-6:
            continue
        n.normalize()
        s = u.cross(n).normalized()
        r = rr[-1]
        c = p0.lerp(p1, 0.50) + n * (r * 0.72)
        pl = sphere('gl_nail_%s' % nm, 1.0, (0, 0, 0), segs=10,
                    scale=(r * 0.70, (p1 - p0).length * 0.44, r * 0.32))
        apply_transforms(pl, rot=True, scale=True)
        place(pl, tuple(c), tuple(s), tuple(n))
        parts.append(pl)
    return seams, parts


def _mirror_x(ob):
    ob.scale = (-1, 1, 1)
    act(ob)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def glove_cuff(name, length=0.055, r0=(0.0290, 0.0235), r1=(0.0362, 0.0308), n=20, strap=True):
    """Flared leather gauntlet cuff running back from the wrist along -Y: a hard welted lip,
    a stitch line, a wrist strap and a buckle.  Built in hand-local space (wrist at origin)."""
    prof = [(-0.0020, 1.000), (-0.0100, 1.030), (-0.0118, 1.115), (-0.0150, 1.118),
            (-0.0172, 1.055)]
    rings = []
    for y, sc in prof:
        rings.append([(math.cos(TAU * j / n) * r0[0] * sc, y, math.sin(TAU * j / n) * r0[1] * sc)
                      for j in range(n)])
    for i in range(6):
        t = (i + 1) / 6.0
        y = -0.0172 - (length - 0.0172) * t
        rx = r0[0] * 1.055 + (r1[0] - r0[0] * 1.055) * t ** 1.25
        rz = r0[1] * 1.055 + (r1[1] - r0[1] * 1.055) * t ** 1.25
        ring = []
        for j in range(n):
            a = TAU * j / n
            w = 1.0 + 0.026 * math.sin(a * 5.0 + y * 48.0) * t
            ring.append((math.cos(a) * rx * w, y, math.sin(a) * rz * w))
        rings.append(ring)
    ob = loft(name, rings, cap_start=False, cap_end=True)
    parts = [ob]
    if strap:
        band = []
        for y in (-0.0300, -0.0425):
            t = (-y - 0.0172) / (length - 0.0172)
            rx = r0[0] * 1.055 + (r1[0] - r0[0] * 1.055) * t ** 1.25 + 0.0024
            rz = r0[1] * 1.055 + (r1[1] - r0[1] * 1.055) * t ** 1.25 + 0.0024
            band.append([(math.cos(TAU * j / n) * rx, y, math.sin(TAU * j / n) * rz)
                         for j in range(n)])
        parts.append(loft(name + '_band', band, cap_start=True, cap_end=True))
        t = (0.0360 - 0.0172) / (length - 0.0172)
        rz = r0[1] * 1.055 + (r1[1] - r0[1] * 1.055) * t ** 1.25
        parts.append(rbox(name + '_buckle', (0.0110, 0.0185, 0.0048),
                          (0.0, -0.0363, -(rz + 0.0032))))
    return fuse(name, parts)


def cuff_stitch(name, length=0.055, r0=(0.0290, 0.0235), r1=(0.0362, 0.0308), n=20):
    """Stitch line just inside the cuff lip, and a second one at the back edge."""
    parts = []
    for y, sc, extra in ((-0.0215, 1.055, 0.0006), (-length + 0.0035, None, 0.0006)):
        if sc is None:
            t = (length - 0.0035 - 0.0172) / (length - 0.0172)
            rx = r0[0] * 1.055 + (r1[0] - r0[0] * 1.055) * t ** 1.25
            rz = r0[1] * 1.055 + (r1[1] - r0[1] * 1.055) * t ** 1.25
        else:
            rx, rz = r0[0] * sc, r0[1] * sc
        samples = []
        for j in range(n + 1):
            a = TAU * j / n
            c, s = math.cos(a), math.sin(a)
            q = Vector((c * (rx + extra), y, s * (rz + extra)))
            nrm = Vector((c / max(rx, 1e-5), 0, s / max(rz, 1e-5))).normalized()
            samples.append((q, nrm, Vector((-s * rx, 0, c * rz)).normalized()))
        r = _ridge(name + '_%d' % int(y * 1e4), samples, w=0.0009, h=0.0008, sink=0.0003)
        if r:
            parts.append(r)
    return parts


def wrist_watch(name, r_out=0.0370, r_side=0.0424, along=(0, -1, 0), out=(0, 0, 1),
                at=0.0700):
    """Small field watch on the back of the forearm.  The sleeve section is elliptical, so the
    case and strap follow that ellipse - a constant radius leaves the strap floating."""
    parts = []
    a = Vector(along).normalized()
    o = Vector(out).normalized()
    side = a.cross(o).normalized()
    axis_pt = a * at

    def rad(ang):
        c, s_ = math.cos(ang), math.sin(ang)
        return 1.0 / math.sqrt((c / r_out) ** 2 + (s_ / r_side) ** 2)

    c = axis_pt + o * (rad(0.0) - 0.0034)
    case = lathe(name + '_case', [(0.0000, -0.0040), (0.0082, -0.0040), (0.0096, -0.0016),
                                  (0.0096, 0.0026), (0.0076, 0.0040), (0.0000, 0.0040)], segs=14)
    place(case, tuple(c), tuple(side), tuple(o))
    finish(case, None, bev=0.0004, texel=0.03)
    parts.append(case)
    face = lathe(name + '_face', [(0.0000, 0.0041), (0.0072, 0.0041), (0.0072, 0.0032),
                                  (0.0000, 0.0032)], segs=14)
    place(face, tuple(c), tuple(side), tuple(o))
    finish(face, None, bev=0.0, texel=0.03)
    parts.append(face)
    for sgn in (1, -1):
        st = []
        for k in range(5):
            t = k / 4.0
            ang = D2R(16.0 + 76.0 * t) * sgn
            d = (o * math.cos(ang) + side * math.sin(ang)).normalized()
            q = axis_pt + d * (rad(ang) - 0.0024)
            st.append([q + a * 0.0072 + d * 0.0022, q - a * 0.0072 + d * 0.0022,
                       q - a * 0.0072 - d * 0.0022, q + a * 0.0072 - d * 0.0022])
        band = loft(name + '_band%d' % sgn, st, cap_start=True, cap_end=True)
        finish(band, None, bev=0.0004, texel=0.03)
        parts.append(band)
    return parts


def build_arm(name, side='R', wrist=(0, 0, 0), fingers=(0, 1, 0), back=(1, 0, 0),
              elbow=None, curl=(0.85, 0.90, 0.92, 0.92), thumb_curl=0.55,
              thumb_abduct=0.0, thumb_roll=0.0, spread=1.0, fat=1.0,
              forearm_len=0.30, wrist_r=(0.0275, 0.0225), elbow_r=(0.048, 0.042),
              sleeve_start=0.10, cuff_at=0.50, res=0.0030, rings=11, seed=3,
              hand_tris=2330, glove_mat=None, sleeve_mat=None, cuff_len=0.055,
              watch=None):
    """Gloved hand + stitched seams + gauntlet cuff + forearm in an olive field-jacket sleeve.
    Returns ONE mesh object whose object origin is at `wrist`.

    Material slots: 0 glove leather, 1 dark leather (cuff/strap), 2 olive sleeve,
    3 stitching, 4 watch steel."""
    hand = build_hand(name + '_hand', side, curl, spread, thumb_curl, thumb_abduct, thumb_roll,
                      res, hand_tris, fat)
    seams, panels = glove_detail(curl, spread, thumb_curl, thumb_abduct, thumb_roll)
    detail = seams + panels
    w0 = Vector(wrist)
    e0 = Vector(elbow) if elbow is not None else w0 - Vector(fingers).normalized() * forearm_len
    fore_dir = (e0 - w0).normalized()
    cuff = glove_cuff(name + '_cuff', cuff_len, n=18)
    stitches = cuff_stitch(name + '_cst', cuff_len, n=14)
    if watch is None:
        watch = (side == 'L')
    watch_parts = []
    if watch:
        _L = (e0 - w0).length
        _t = 0.0700 / max(_L, 1e-4)
        _k = _t ** 0.75
        _sl = 0.0080 if _t > max(sleeve_start, (cuff_len + 0.004) / max(_L, 1e-4)) else 0.0
        watch_parts = wrist_watch(
            name + '_watch',
            r_out=wrist_r[1] + (elbow_r[1] - wrist_r[1]) * _k + _sl + 0.0012,
            r_side=wrist_r[0] + (elbow_r[0] - wrist_r[0]) * _k + _sl + 0.0012)

    for o in detail:
        finish(o, None, bev=0.0, texel=0.05, smooth=True, angle=46)
    for o in stitches:
        finish(o, None, bev=0.0, texel=0.05, smooth=True, angle=46)
    if side == 'L':
        for o in [cuff] + detail + stitches + watch_parts:
            _mirror_x(o)
    mhand = _oriented(wrist, fingers, back)
    mfore = _oriented(wrist, -fore_dir, back)
    for o in [hand] + detail:
        xform(o, mhand)
    # the cuff and the watch ride the forearm, not the hand
    for o in [cuff] + stitches + watch_parts:
        xform(o, mfore)

    finish(hand, None, bev=0.0, texel=0.048, smooth=True, angle=34)
    finish(cuff, None, bev=0.0006, texel=0.046, smooth=True, angle=34)

    groups = ([(hand, 0)] + [(o, 3) for o in seams]
              + [(o, 1 if '_nail' in o.name else 0) for o in panels]
              + [(cuff, 1)] + [(o, 3) for o in stitches]
              + [(o, 1 if '_band' in o.name else 4) for o in watch_parts])
    idx = []
    for o, slot in groups:
        idx += [slot] * len(o.data.polygons)
    glove = fuse(name + '_glove', [o for o, _ in groups])

    w, e = w0, e0
    axis = (e - w)
    L = axis.length
    axis.normalize()
    up = Vector(back) - axis * Vector(back).dot(axis)
    if up.length < 1e-5:
        up = Vector((0, 0, 1)) - axis * axis.z
    up.normalize()
    rgt = axis.cross(up).normalized()

    rnd = random.Random(seed)
    sec, n = [], 16
    for i in range(rings):
        t = i / (rings - 1)
        p = w + axis * (L * t)
        k = t ** 0.75
        ra = wrist_r[0] + (elbow_r[0] - wrist_r[0]) * k
        rb = wrist_r[1] + (elbow_r[1] - wrist_r[1]) * k
        sleeve = t > max(sleeve_start, (cuff_len + 0.004) / L)
        if sleeve:
            ra += 0.0080
            rb += 0.0080
        roll = 0.0
        if abs(t - cuff_at) < 0.11:
            roll = 0.0105 * math.cos((t - cuff_at) / 0.11 * math.pi * 0.5) ** 2
        ring = []
        for j in range(n):
            a = TAU * j / n
            fold = 0.0
            if sleeve:
                fold = (math.sin(a * 3.0 + t * 9.0) * 0.0023
                        + math.sin(a * 5.0 - t * 13.0) * 0.0015
                        + math.sin(a * 9.0 + t * 6.0) * 0.0008
                        + rnd.uniform(-1, 1) * 0.0005) * min(1.0, (t - sleeve_start) * 5)
            ring.append(p + rgt * (math.cos(a) * (ra + roll + fold))
                        + up * (math.sin(a) * (rb + roll + fold)))
        sec.append(ring)
    arm = loft(name + '_fore', sec, cap_start=True, cap_end=True)
    finish(arm, None, bev=0.0, texel=0.080, smooth=True)

    ob = fuse(name, [glove, arm])
    ob.data.materials.clear()
    for m in (glove_mat or M('glove_leather'), M('glove_leather_dark'),
              sleeve_mat or M('sleeve_olive'),
              plain('glove_stitch', (0.0300, 0.0232, 0.0155), 0.70),
              plain('sleeve_watch_steel', (0.125, 0.128, 0.134), 0.38, 1.0)):
        ob.data.materials.append(m)
    ng = len(idx)
    for i, poly in enumerate(ob.data.polygons):
        poly.material_index = idx[i] if i < ng else 2
    ob.location = wrist
    ob.data.transform(Matrix.Translation(-Vector(wrist)))
    return ob


MCP_REF = Vector((-0.0098, 0.1040, 0.0020))     # middle-finger knuckle in hand-local space


def wrist_from_mcp(mcp, fingers, back, side='R'):
    """Where the wrist must sit so that the middle-finger knuckle lands on `mcp`."""
    R = _oriented((0, 0, 0), fingers, back).to_3x3()
    ref = Vector((-MCP_REF.x, MCP_REF.y, MCP_REF.z)) if side == 'L' else MCP_REF
    return tuple(Vector(mcp) - R @ ref)


def _oriented(origin, fwd, up):
    """4x4 matrix whose local +Y is `fwd` and local +Z is as close to `up` as possible."""
    y = Vector(fwd).normalized()
    z = Vector(up).normalized()
    x = y.cross(z)
    if x.length < 1e-6:
        x = y.cross(Vector((1, 0, 0)))
    x.normalize()
    z = x.cross(y).normalized()
    m = Matrix((
        (x.x, y.x, z.x, origin[0]),
        (x.y, y.y, z.y, origin[1]),
        (x.z, y.z, z.z, origin[2]),
        (0, 0, 0, 1)))
    return m


def build_viewmodel(grip_pos, gun_objects, muzzle, eject, aim, arm_r=None, arm_l=None,
                    extra_empties=None):
    """Wire up the contract hierarchy.  All coordinates of the gun objects / empties are in
    *gun space* (origin = grip_pos in camera space, bore along +Y)."""
    root = empty('viewmodel', (0, 0, 0), size=0.06)
    wep = empty('weapon', grip_pos, size=0.05)
    wep.parent = root
    # children keep an identity parent-inverse: their local (gun-space) coordinates are simply
    # offset by grip_pos, which is exactly the framing we want.
    for o in gun_objects:
        if o is None:
            continue
        if o.parent is not None:      # already nested (e.g. `cylinder` under `crane`)
            continue
        o.parent = wep
    empties = [('muzzle', muzzle), ('eject', eject), ('aim', aim)]
    empties += list((extra_empties or {}).items())
    for nm, p in empties:
        e = empty(nm, p, size=0.02)
        e.parent = wep
    for a in (arm_r, arm_l):
        if a is None:
            continue
        a.parent = wep
    bpy.context.view_layer.update()
    return root, wep


def export_weapon(root, wid):
    path = os.path.join(WEAPONS_DIR, wid + '.glb')
    bpy.ops.object.select_all(action='DESELECT')

    def sel(o):
        o.select_set(True)
        for c in o.children:
            sel(c)
    sel(root)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_yup=True,
                              export_apply=True, export_extras=True, export_animations=False,
                              use_selection=True, export_image_format='WEBP',
                              export_image_quality=88, export_texture_dir='')
    print('EXPORTED', path, os.path.getsize(path) // 1024, 'KB')
    return path


def tri_count():
    dg = bpy.context.evaluated_depsgraph_get()
    total = 0
    for ob in bpy.context.scene.objects:
        if ob.type != 'MESH':
            continue
        me = ob.evaluated_get(dg).to_mesh()
        total += sum(max(0, len(p.vertices) - 2) for p in me.polygons)
        ob.evaluated_get(dg).to_mesh_clear()
    return total


# ---------------------------------------------------------------------------
#  Renders
# ---------------------------------------------------------------------------

_HELPERS = []


def _clear_helpers():
    global _HELPERS
    for h in _HELPERS:
        try:
            d = h.data
            bpy.data.objects.remove(h, do_unlink=True)
            if d is not None and d.users == 0:
                for coll in (bpy.data.meshes, bpy.data.lights, bpy.data.cameras):
                    try:
                        coll.remove(d)
                        break
                    except Exception:
                        pass
        except Exception:
            pass
    _HELPERS = []


def _world_dusk(strength=1.0):
    scn = bpy.context.scene
    if scn.world is None:
        scn.world = bpy.data.worlds.new('World')
    wd = scn.world
    wd.use_nodes = True
    nt = wd.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = strength
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange')          # Generated Z is -1..1
    mr.inputs['From Min'].default_value = -1.0
    mr.inputs['From Max'].default_value = 1.0
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    el = ramp.color_ramp.elements
    el[0].position = 0.0
    el[0].color = (0.055, 0.045, 0.038, 1)           # ground bounce, straight down
    el[1].position = 0.44
    el[1].color = (0.30, 0.20, 0.13, 1)
    for pos, col in ((0.50, (1.00, 0.46, 0.17)), (0.60, (0.62, 0.34, 0.22)),
                     (0.78, (0.22, 0.20, 0.24)), (1.00, (0.085, 0.105, 0.165))):
        e = el.new(pos)
        e.color = (*col, 1)
    nt.links.new(mr.outputs['Result'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    return wd


def _stage(ground=True):
    """A cheap dusk environment so a viewmodel render reads like a game frame."""
    global _HELPERS
    _world_dusk(0.72)
    if ground:
        g = box('_stage_ground', (60, 60, 0.02), (0, 6, -1.62))
        assign(g, plain('_stage_gnd', (0.085, 0.072, 0.060), 0.92))
        _HELPERS.append(g)
        bk = box('_stage_wall', (40, 0.4, 14), (0, 16, 5.0))
        assign(bk, plain('_stage_wall_m', (0.075, 0.066, 0.062), 0.95))
        _HELPERS.append(bk)
    specs = (('_key', (-1.1, -0.35, 1.25), 520, 1.6, (1.0, 0.86, 0.70)),
             ('_fill', (1.5, -0.6, 0.15), 62, 2.2, (0.55, 0.62, 0.85)),
             ('_rim', (0.75, 1.5, 0.95), 230, 1.0, (1.0, 0.55, 0.28)),
             ('_bounce', (0.0, 0.7, -1.2), 45, 2.5, (1.0, 0.72, 0.48)))
    for nm, off, energy, size, col in specs:
        ld = bpy.data.lights.new(nm, 'AREA')
        ld.energy = energy
        ld.size = size
        ld.color = col
        lo = bpy.data.objects.new(nm, ld)
        link(lo)
        _HELPERS.append(lo)
        lo.location = Vector(off) * 2.2
        lo.rotation_euler = (Vector((0, 0.45, -0.1)) - lo.location).to_track_quat('-Z', 'Y').to_euler()


def render_eye(path, samples=48, res=(1280, 720), fov=FOV_V, cam_loc=(0, 0, 0), stage=True,
               exposure=0.0):
    """The in-game frame: camera at the eye looking along +Y."""
    scn = setup_gpu(samples)
    scn.render.resolution_x, scn.render.resolution_y = res
    scn.render.film_transparent = False
    scn.view_settings.view_transform = 'AgX'
    scn.view_settings.look = 'AgX - Medium High Contrast'
    scn.view_settings.exposure = exposure
    _stage(stage)
    cd = bpy.data.cameras.new('_eye')
    cd.sensor_fit = 'VERTICAL'
    cd.lens_unit = 'FOV'
    cd.angle_y = D2R(fov)
    cd.clip_start = 0.01
    cd.clip_end = 500
    cam = bpy.data.objects.new('_eye', cd)
    link(cam)
    _HELPERS.append(cam)
    cam.location = cam_loc
    cam.rotation_euler = (math.pi / 2, 0, 0)
    scn.camera = cam
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)
    _clear_helpers()
    print('RENDERED', path)
    return path


def render_ads(path, aim_pos, back=0.32, samples=32, res=(960, 540), fov=58.0):
    """Sit the camera behind the `aim` empty and look straight down +Y.

    `back` / `fov` mirror the *game's* ADS numbers (`config.js` `adsDist`, `VM_FOV.ads`): the
    aim node is anchored a fixed distance from the eye and the viewmodel frustum WIDENS when
    aiming.  The old 0.10 m / 40 deg pair put the camera inside the stock and magnified the
    receiver to a black lump - see weapons_audio.md #1."""
    return render_eye(path, samples, res, fov,
                      cam_loc=(aim_pos[0], aim_pos[1] - back, aim_pos[2]), stage=True)


def render_detail(path, target, distance=0.42, yaw=38, pitch=18, samples=56, res=(1280, 720),
                  lens=70, bg=0.35):
    """Studio 3/4 render of the gun alone (arms hidden by the caller if desired)."""
    scn = setup_gpu(samples)
    scn.render.resolution_x, scn.render.resolution_y = res
    scn.render.film_transparent = False
    scn.view_settings.view_transform = 'AgX'
    scn.view_settings.look = 'AgX - Medium High Contrast'
    scn.view_settings.exposure = 0.0
    if scn.world is None:
        scn.world = bpy.data.worlds.new('World')
    scn.world.use_nodes = True
    for n in list(scn.world.node_tree.nodes):
        scn.world.node_tree.nodes.remove(n)
    nt = scn.world.node_tree
    out = nt.nodes.new('ShaderNodeOutputWorld')
    b = nt.nodes.new('ShaderNodeBackground')
    b.inputs['Strength'].default_value = bg * 0.55
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = -1.0
    mr.inputs['From Max'].default_value = 1.0
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    rp = nt.nodes.new('ShaderNodeValToRGB')
    el = rp.color_ramp.elements
    el[0].position = 0.0; el[0].color = (0.020, 0.021, 0.025, 1)
    el[1].position = 0.48; el[1].color = (0.10, 0.11, 0.135, 1)
    e = el.new(0.70); e.color = (0.42, 0.45, 0.52, 1)
    e = el.new(1.0); e.color = (0.85, 0.88, 0.95, 1)
    nt.links.new(mr.outputs['Result'], rp.inputs['Fac'])
    nt.links.new(rp.outputs['Color'], b.inputs['Color'])
    nt.links.new(b.outputs[0], out.inputs['Surface'])
    t = Vector(target)
    ya, pi_ = D2R(yaw), D2R(pitch)
    cam_loc = t + Vector((math.sin(ya) * math.cos(pi_), -math.cos(ya) * math.cos(pi_), math.sin(pi_))) * distance
    cd = bpy.data.cameras.new('_det')
    cd.lens = lens
    cd.clip_start = 0.005
    cam = bpy.data.objects.new('_det', cd)
    link(cam)
    _HELPERS.append(cam)
    cam.location = cam_loc
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scn.camera = cam
    for nm, off, energy, size, col in (('_k', (-0.9, -0.8, 1.0), 19, 0.9, (1.0, 0.94, 0.86)),
                                       ('_f', (1.1, -0.7, 0.05), 5.5, 1.4, (0.62, 0.70, 0.92)),
                                       ('_r', (0.5, 1.2, 0.7), 12, 0.7, (1.0, 0.72, 0.45)),
                                       ('_t', (-0.2, 0.2, 1.4), 9, 1.2, (0.95, 0.95, 1.0))):
        ld = bpy.data.lights.new(nm, 'AREA')
        ld.energy = energy * (distance / 0.42) ** 2
        ld.size = size * distance / 0.42
        ld.color = col
        lo = bpy.data.objects.new(nm, ld)
        link(lo)
        _HELPERS.append(lo)
        lo.location = t + Vector(off) * distance * 2.0
        lo.rotation_euler = (t - lo.location).to_track_quat('-Z', 'Y').to_euler()
    gp = box('_det_ground', (10, 10, 0.02), (t.x, t.y, t.z - distance * 0.85))
    assign(gp, plain('_det_gnd', (0.045, 0.045, 0.05), 0.55))
    _HELPERS.append(gp)
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)
    _clear_helpers()
    print('RENDERED', path)
    return path


def hide(objs, state=True):
    for o in objs:
        if o is None:
            continue
        o.hide_render = state
        for c in o.children_recursive:
            c.hide_render = state


def report(wid, wep, muzzle, aim, eject, movable, extra=''):
    print('=' * 60)
    print('WEAPON', wid)
    gp = Vector(wep.location)
    for nm, p in (('weapon', (0, 0, 0)), ('muzzle', muzzle), ('aim', aim), ('eject', eject)):
        c = gp + Vector(p)
        s = ndc(c)
        print('  %-8s cam=(%.4f, %.4f, %.4f)  ndc=(%.2f, %.2f)' % (nm, c.x, c.y, c.z, s[0], s[1]) if s
              else '  %-8s cam=(%.4f, %.4f, %.4f)' % (nm, c.x, c.y, c.z))
    print('  movable:', ', '.join(movable) if movable else '(none)')
    dg = bpy.context.evaluated_depsgraph_get()
    tot = 0
    for ob in sorted(bpy.context.scene.objects, key=lambda o: o.name):
        if ob.type != 'MESH':
            continue
        me = ob.evaluated_get(dg).to_mesh()
        n = sum(max(0, len(pp.vertices) - 2) for pp in me.polygons)
        ob.evaluated_get(dg).to_mesh_clear()
        tot += n
        print('    %-22s %6d' % (ob.name, n))
    print('  TOTAL tris:', tot)
    if extra:
        print(' ', extra)
    print('=' * 60)

# ---------------------------------------------------------------------------
#  Standard hand poses (gun space: bore +Y, up +Z, right +X)
# ---------------------------------------------------------------------------

def hand_on_grip(mcp, rake=-0.36, curl=(0.74, 0.90, 0.93, 0.95), thumb_curl=0.22,
                 thumb_abduct=-26, elbow=(0.095, -0.035, -0.300), name='arm_R', **kw):
    """Right hand wrapped round a pistol grip.  `mcp` = where the middle knuckle sits on the
    right side of the grip; `rake` = how far the fingers point down (grip rake)."""
    f = Vector((0.05, 1.0, rake)).normalized()
    b = Vector((0.962, -0.02, 0.272)).normalized()
    w = wrist_from_mcp(mcp, f, b, 'R')
    return build_arm(name, 'R', wrist=w, fingers=tuple(f), back=tuple(b),
                     elbow=(w[0] + elbow[0], w[1] + elbow[1], w[2] + elbow[2]),
                     curl=curl, thumb_curl=thumb_curl, thumb_abduct=thumb_abduct,
                     cuff_at=0.52, forearm_len=0.30, seed=4, **kw)


def hand_on_handguard(mcp, lean=0.22, curl=(0.88, 0.92, 0.94, 0.95), thumb_curl=0.32,
                      thumb_abduct=-20, elbow=(-0.150, 0.010, -0.285), name='arm_L', **kw):
    """Left support hand under a handguard: knuckles on the LEFT of the tube, fingers wrapping
    up and over the top, thumb lying forward along the near side."""
    f = Vector((0.12, lean, 0.965)).normalized()
    b = Vector((-0.965, 0.08, 0.16)).normalized()
    w = wrist_from_mcp(mcp, f, b, 'L')
    return build_arm(name, 'L', wrist=w, fingers=tuple(f), back=tuple(b),
                     elbow=(w[0] + elbow[0], w[1] + elbow[1], w[2] + elbow[2]),
                     curl=curl, thumb_curl=thumb_curl, thumb_abduct=thumb_abduct,
                     cuff_at=0.52, forearm_len=0.30, seed=9, **kw)


def hand_support_pistol(mcp, rake=-0.42, curl=(0.88, 0.92, 0.94, 0.95), thumb_curl=0.30,
                        thumb_abduct=-34, elbow=(-0.105, -0.030, -0.300), name='arm_L', **kw):
    """Left hand cupping the right hand on a pistol grip."""
    f = Vector((0.055, 1.0, rake)).normalized()
    b = Vector((-0.948, 0.02, 0.318)).normalized()
    w = wrist_from_mcp(mcp, f, b, 'L')
    return build_arm(name, 'L', wrist=w, fingers=tuple(f), back=tuple(b),
                     elbow=(w[0] + elbow[0], w[1] + elbow[1], w[2] + elbow[2]),
                     curl=curl, thumb_curl=thumb_curl, thumb_abduct=thumb_abduct,
                     cuff_at=0.52, forearm_len=0.30, seed=9, **kw)


# ---------------------------------------------------------------------------
def deliver(wid, grip_pos, guns, muzzle, eject, aim, arm_r=None, arm_l=None, movable=(),
            detail_target=(0, 0.06, 0.0), detail_dist=0.45, lens=50, extra_empties=None,
            export=True, renders=True, grip_view=None, samples=32, ads_back=0.32,
            res=(960, 540)):
    """Assemble, export, report and shoot the four standard check renders.

    Check renders are capped at 960x540 / 32 samples: this machine runs one Blender job at a
    time and overheats."""
    root, wep = build_viewmodel(grip_pos, guns, muzzle, eject, aim, arm_r, arm_l, extra_empties)
    gp = Vector(grip_pos)
    if export:
        export_weapon(root, wid)
        report(wid, wep, muzzle, aim, eject, list(movable))
    if renders:
        render_eye(os.path.join(WRENDERS, wid + '_hipfire.png'), samples=samples, res=res)
        gv = grip_view or (0, -0.02, -0.05)
        render_detail(os.path.join(WRENDERS, wid + '_grip.png'), target=tuple(gp + Vector(gv)),
                      distance=0.42, yaw=-52, pitch=14, samples=samples, lens=40, res=res)
        render_ads(os.path.join(WRENDERS, wid + '_ads.png'), tuple(gp + Vector(aim)),
                   back=ads_back, samples=samples, res=res)
        hide([arm_r, arm_l], True)
        # same camera, gun only: tells you whether an obstruction in the sight picture is the
        # weapon or a hand, which the combined frame cannot
        render_ads(os.path.join(WRENDERS, wid + '_ads_gun.png'), tuple(gp + Vector(aim)),
                   back=ads_back, samples=samples, res=res)
        render_detail(os.path.join(WRENDERS, wid + '_detail.png'),
                      target=tuple(gp + Vector(detail_target)),
                      distance=detail_dist, yaw=34, pitch=16, samples=samples, lens=lens, res=res)
        render_detail(os.path.join(WRENDERS, wid + '_detail2.png'),
                      target=tuple(gp + Vector(detail_target)),
                      distance=detail_dist, yaw=-142, pitch=12, samples=samples, lens=lens,
                      res=res)
        hide([arm_r, arm_l], False)
    return root, wep
