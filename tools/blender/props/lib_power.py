"""Helpers used only by build_power.py (power_switch.glb).

`lib_props.py` is shared with the other props scripts and is read-only for this asset,
so everything new the power switch needs lives here.
"""
import bpy, bmesh, math
from mathutils import Vector, Matrix, Euler

from lib_props import *  # noqa: F401,F403


# --------------------------------------------------------------------------------------
# transforms
# --------------------------------------------------------------------------------------

def bake_xf(ob, M):
    """Bake a world matrix into the mesh and leave the object transform identity.

    The lever is modelled in a local frame whose origin is the pivot and whose -Z is
    "hanging straight down"; one matrix drops the whole assembly into its OFF pose.
    Because the object transform ends up identity, the exported `lever` node carries no
    rotation of its own and the game's "rotate about local X" is unambiguous.
    """
    bpy.context.view_layer.update()
    ob.data.transform(M @ ob.matrix_basis)
    ob.location = (0.0, 0.0, 0.0)
    ob.rotation_euler = (0.0, 0.0, 0.0)
    ob.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()
    return ob


def lever_frame(pivot, tilt):
    """Matrix mapping the lever's local frame (pivot at origin, -Z = down) into world."""
    return Matrix.Translation(Vector(pivot)) @ Matrix.Rotation(tilt, 4, 'X')


# --------------------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------------------

def ribbed_insulator(name, length=0.06, r=0.024, ribs=3, loc=(0, 0, 0), rot=(0, 0, 0),
                     verts=14, collection=None):
    """Porcelain stand-off insulator: a ribbed post running along +Z before `rot`."""
    prof = [(0.0, 0.0), (r * 0.80, 0.0), (r * 0.80, length * 0.08)]
    for i in range(ribs):
        z0 = length * (0.12 + 0.80 * (i + 0.05) / ribs)
        z1 = length * (0.12 + 0.80 * (i + 0.45) / ribs)
        z2 = length * (0.12 + 0.80 * (i + 0.85) / ribs)
        prof += [(r * 0.62, z0), (r, z1), (r * 0.62, z2)]
    prof += [(r * 0.72, length * 0.96), (r * 0.72, length), (0.0, length)]
    return lathe(name, prof, verts=verts, loc=loc, rot=rot, collection=collection)


def enamel(name, color, rough=0.34, wear=0.40, rust=0.40, grime=0.66, dent=0.55, scale=6.0,
           seed=0.0, variation=0.15, dust=0.10, streak=0.55, speckle=0.05, ao=0.035,
           wear_color=(0.205, 0.196, 0.186)):
    """Chipped enamel over steel, tuned for a 0.6 m prop.

    `painted()` in lib_props is authored for 2 m machines: its noise scales and its 9 cm
    cavity radius wash out completely on something this small, so this wrapper drives
    `weathered()` with a much tighter grain and a small AO distance.
    """
    return weathered(name, color=color, roughness=rough, metallic=0.0,
                     wear_color=wear_color, wear=wear, wear_rough=0.45, wear_metal=0.9,
                     rust=rust, grime=grime, dust=dust, variation=variation, scale=scale,
                     seed=seed, bump=0.55, dent=dent, scratch=0.8, ao_dist=ao,
                     speckle=speckle, streak=streak)


def plated(name, tint=(0.52, 0.53, 0.54), rough=0.32, grime=0.55, scratch=1.0, pit=0.8,
           scale=9.0, seed=3.0, ao=0.028):
    """Scuffed galvanised / plated steel at prop scale."""
    return weathered(name, color=tint, roughness=rough, metallic=1.0,
                     wear_color=(0.40, 0.385, 0.37), wear=0.24, wear_rough=0.42,
                     wear_metal=1.0, rust=0.16 * pit, rust_color=(0.22, 0.12, 0.06),
                     grime=grime, grime_color=(0.055, 0.05, 0.048), dust=0.10,
                     variation=0.04, scale=scale, seed=seed, bump=0.25, dent=0.35,
                     scratch=scratch, ao_dist=ao, speckle=0.05, streak=0.35)


def arc_path(centre, radius, a0, a1, steps=8, plane='XZ', x=0.0):
    """Points along a circular arc - padlock shackles, cable loops."""
    cx, cy, cz = centre
    pts = []
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        if plane == 'XZ':
            pts.append((cx + math.cos(a) * radius, cy, cz + math.sin(a) * radius))
        else:  # 'YZ'
            pts.append((x, cy + math.cos(a) * radius, cz + math.sin(a) * radius))
    return pts


def hazard_band(prefix, width, height, loc, depth=0.010, n=9, angle=38.0):
    """Yellow/black diagonal hazard band. Returns (plate, [stripes]) - unassigned."""
    x0, y0, z0 = loc
    plate = rbox(f'{prefix}_plate', (width, depth, height), (x0, y0, z0), radius=0.003, seg=1)
    sw = height * 0.42
    pitch = width / n
    stripes = []
    for i in range(n):
        x = x0 - width / 2 + pitch * (i + 0.5)
        stripes.append(rbox(f'{prefix}_s{i}', (sw, depth * 0.55, height * 0.86),
                            (x, y0 - depth * 0.72, z0), radius=0.001, seg=1,
                            rot=(0, D2R(angle), 0)))
    return plate, stripes


# --------------------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------------------

def sweep_clearance(lever, panel, pivot, angles, min_radius=0.045, max_samples=1600):
    """Worst penetration of `lever` into `panel` while rotating about world X at `pivot`.

    Points closer than `min_radius` to the pivot are ignored: the blades genuinely share
    space with the hinge blocks there (that *is* the hinge).
    Returns (signed_distance, angle, world_point); negative = inside the panel mesh.
    """
    pv = Vector(pivot)
    pts = []
    for v in lever.data.vertices:
        w = lever.matrix_world @ v.co
        # radius measured in the plane of rotation (YZ) - X offset is irrelevant
        if math.hypot(w.y - pv.y, w.z - pv.z) >= min_radius:
            pts.append(w)
    if len(pts) > max_samples:
        pts = pts[::max(1, len(pts) // max_samples)]
    inv = panel.matrix_world.inverted()
    worst = (1e9, 0.0, Vector())
    for a in angles:
        R = Matrix.Rotation(a, 4, 'X')
        for p in pts:
            q = pv + (R @ (p - pv))
            ql = inv @ q
            ok, loc, nrm, _idx = panel.closest_point_on_mesh(ql)
            if not ok:
                continue
            d = (ql - loc).dot(nrm)
            if d < worst[0]:
                worst = (d, a, q.copy())
    return worst


def weld(objs, dist=1e-5):
    """Merge coincident verts and drop zero-area faces.

    `bolt(washer=True)` in lib_props appends the washer cylinder without merging it, which
    leaves a dozen degenerate faces per bolt; there are ~20 bolts on this panel.  Returns
    the number of faces removed.
    """
    removed = 0
    for o in objs:
        if o.type != 'MESH':
            continue
        bm = bmesh.new()
        bm.from_mesh(o.data)
        before = len(bm.faces)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
        bmesh.ops.dissolve_degenerate(bm, dist=dist, edges=bm.edges)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        removed += before - len(bm.faces)
        bm.to_mesh(o.data)
        bm.free()
        o.data.update()
    return removed


def validate(objs):
    """Report geometry that would upset the ray-traced bake (NaNs, empty or degenerate
    meshes, loose verts). Returns the number of problems found."""
    bad = 0
    for o in objs:
        if o.type != 'MESH':
            continue
        me = o.data
        nan = sum(1 for v in me.vertices if not all(math.isfinite(c) for c in v.co))
        huge = sum(1 for v in me.vertices if max(abs(c) for c in v.co) > 100.0)
        if not len(me.polygons):
            print('  !! no faces:', o.name); bad += 1
        if nan:
            print('  !! %d non-finite verts:' % nan, o.name); bad += 1
        if huge:
            print('  !! %d runaway verts:' % huge, o.name); bad += 1
        tiny = sum(1 for p in me.polygons if p.area < 1e-12)
        if tiny:
            print('  !! %d zero-area faces:' % tiny, o.name); bad += 1
    return bad


def bounds(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        if o.type != 'MESH':
            continue
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
    return lo, hi
