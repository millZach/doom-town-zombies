"""Helpers owned by build_powerups.py (the six pu_*.glb pickups).

lib_props.py is shared/read-only, so anything new the power-ups need lives here:
  * the gold / brass material family they all share
  * boolean carving (skull sockets, nose cavity, tag grommet)
  * a lathed rifle cartridge
  * transform utilities (flatten, rotate, centre + fit to a target size)
  * the render helpers: per-prop turntable angles and the six-up lineup sheet
"""
import bpy, bmesh, math, os
from mathutils import Vector, Matrix, Euler

import sys
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from lib_props import *  # noqa: F401,F403
from lib_props import _render_safe  # underscore names are skipped by `import *`


# --------------------------------------------------------------------------------------
# materials - one polished-gold family, three tones
# --------------------------------------------------------------------------------------

def gold(name, seed=1.0, tint=(0.745, 0.472, 0.078), rough=0.16, grime=0.22, wear=0.45,
         verdigris=0.07, scale=3.6, dent=0.25, dust=0.02, variation=0.07):
    """Cast, polished gold: bright buffed highlights on every edge, soot in the recesses,
    a whisper of verdigris in the deep corners.

    The wear ramp starts *above* 0.5 on purpose - pointiness is ~0.5 on a flat face, so a
    band that opens below it paints the whole prop with the pale wear colour and the gold
    turns to bone."""
    return weathered(name, color=tint, roughness=rough, metallic=1.0,
                     wear_color=(0.985, 0.870, 0.560), wear=wear, wear_rough=0.07, wear_metal=1.0,
                     rust=verdigris, rust_color=(0.095, 0.150, 0.105),
                     grime=grime, grime_color=(0.030, 0.024, 0.016),
                     dust=dust, dust_color=(0.30, 0.26, 0.20),
                     variation=variation, scale=scale, seed=seed,
                     bump=0.42, dent=dent, scratch=0.75, ao_dist=0.035,
                     pointy_lo=0.503, pointy_hi=0.566, speckle=0.08, streak=0.10)


def gold_dark(name, seed=2.0):
    """Recessed / engraved areas: antiqued, sooty, much rougher so the relief reads."""
    return gold(name, seed, tint=(0.300, 0.178, 0.030), rough=0.42, grime=0.55, wear=0.30,
                verdigris=0.18, scale=4.2, dent=0.18, dust=0.05, variation=0.10)


def gold_bright(name, seed=3.0):
    """Polished trim / steel-ish gold: mirror-bright, for rims, bands and struck faces."""
    return gold(name, seed, tint=(0.885, 0.735, 0.355), rough=0.095, grime=0.15, wear=0.50,
                verdigris=0.03, scale=3.0, dent=0.20, dust=0.01, variation=0.05)


# --------------------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------------------

def carve(target, cutters, solver='EXACT', op='DIFFERENCE'):
    """Boolean `cutters` against `target`, apply, and delete the cutters."""
    if not isinstance(cutters, (list, tuple)):
        cutters = [cutters]
    for c in cutters:
        m = target.modifiers.new('carve', 'BOOLEAN')
        m.operation = op
        m.object = c
        try:
            m.solver = solver
        except Exception:
            pass
    bpy.ops.object.select_all(action='DESELECT')
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    for m in list(target.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except Exception as e:
            print('  carve failed on', target.name, e)
            target.modifiers.remove(m)
    for c in cutters:
        try:
            bpy.data.objects.remove(c, do_unlink=True)
        except Exception:
            pass
    return target


def fuse(target, others, solver='EXACT'):
    """Boolean-union `others` into `target` (proper welded surface, no shading seams)."""
    return carve(target, others, solver=solver, op='UNION')


# .30-cal-ish rifle round, base at z = 0, tip at z = +length.  Chunky on purpose so a
# cartridge still reads as a cartridge at 8 m.
_ROUND_PROFILE = [
    (0.0000, 0.0000), (0.0124, 0.0000), (0.0124, 0.0032), (0.0114, 0.0060),
    (0.0111, 0.0380), (0.0070, 0.0500), (0.0066, 0.0640), (0.0048, 0.0800),
    (0.0026, 0.0900), (0.0000, 0.0960),
]


def cartridge(name, loc=(0, 0, 0), rot=(0, 0, 0), k=1.0, verts=9, collection=None):
    prof = [(r * k, z * k) for r, z in _ROUND_PROFILE]
    return lathe(name, prof, verts=verts, loc=loc, rot=rot, collection=collection)


def hinge_place(centre, hinge, angle_x):
    """Location for an object whose closed centre is `centre`, swung about a hinge line
    running along X through `hinge` by `angle_x` radians."""
    c, h = Vector(centre), Vector(hinge)
    off = c - h
    r = Matrix.Rotation(angle_x, 4, 'X')
    return tuple(h + (r @ off))


def torus(name, R=0.1, r=0.02, loc=(0, 0, 0), rot=(0, 0, 0), major=20, minor=8, collection=None):
    bm = bmesh.new()
    rings = []
    for i in range(major):
        u = i / major * TAU
        cu, su = math.cos(u), math.sin(u)
        ring = []
        for j in range(minor):
            v = j / minor * TAU
            rr = R + r * math.cos(v)
            ring.append(bm.verts.new((rr * cu, rr * su, r * math.sin(v))))
        rings.append(ring)
    for i in range(major):
        a, b = rings[i], rings[(i + 1) % major]
        for j in range(minor):
            j2 = (j + 1) % minor
            bm.faces.new([a[j], a[j2], b[j2], b[j]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(name, bm, loc, rot, collection)


def wedge_ring(prefix, n, r, size, z=0.0, mat_list=None, axis='Z', phase=0.0, rot_extra=0.0):
    """n small boxes evenly spaced on a circle - knurling, fluting, rivet belts."""
    out = []
    for i in range(n):
        a = phase + i / n * TAU
        if axis == 'Z':
            loc = (math.cos(a) * r, math.sin(a) * r, z)
            rr = (0, 0, a + rot_extra)
        else:  # ring lying in the XZ plane (the coin's rim), spinning about Y
            loc = (math.cos(a) * r, z, math.sin(a) * r)
            rr = (0, -a + rot_extra, 0)
        out.append(rbox(f'{prefix}{i}', size, loc, radius=min(size) * 0.22, seg=1, rot=rr))
    return out


# --------------------------------------------------------------------------------------
# post-bake grade
# --------------------------------------------------------------------------------------

def regrade(mat, rough=(0.05, 0.50), metal=(0.70, 0.30), sat=(1.0, 0.94, 0.70), save=True):
    """Grade the baked texture set in place.

    The weathering graph is tuned for painted steel: it sprays a little dust, grime and
    pale edge-wear everywhere, which on a 100% metal turns gold into bone and pushes the
    roughness up until nothing reflects.  Rather than fight the (shared, read-only) shader
    we remap its output:  roughness and metallic are squeezed back toward polished metal,
    and the base colour is re-saturated toward the gold hue.  All the *variation* the
    bake produced is preserved - only the range is changed.

    rough/metal: (offset, gain) applied to the ORM green/blue channels.
    sat:         per-channel gain on the base colour (sRGB-encoded byte buffer).
    """
    import numpy as np
    done = set()
    for n in mat.node_tree.nodes:
        if n.type != 'TEX_IMAGE' or n.image is None or n.image.name in done:
            continue
        im = n.image
        done.add(im.name)
        if im.name.endswith('_normal'):
            continue
        cnt = im.size[0] * im.size[1] * 4
        a = np.empty(cnt, dtype=np.float32)
        im.pixels.foreach_get(a)
        a = a.reshape(-1, 4)
        if im.name.endswith('_orm'):
            a[:, 1] = np.clip(rough[0] + rough[1] * a[:, 1], 0.0, 1.0)
            a[:, 2] = np.clip(metal[0] + metal[1] * a[:, 2], 0.0, 1.0)
        else:
            for i, k in enumerate(sat[:3]):
                a[:, i] = np.clip(a[:, i] * k, 0.0, 1.0)
        im.pixels.foreach_set(a.reshape(-1))
        im.update()
        if save and im.filepath_raw:
            try:
                im.save()
            except Exception:
                pass
    return mat


# --------------------------------------------------------------------------------------
# transforms
# --------------------------------------------------------------------------------------

def flatten_transform(ob):
    """Bake the object transform into the mesh so mesh-space == world-space."""
    bpy.context.view_layer.update()
    ob.data.transform(ob.matrix_world)
    ob.matrix_world = Matrix.Identity(4)
    return ob


def bbox(ob):
    bpy.context.view_layer.update()
    cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    mn = Vector([min(c[i] for c in cs) for i in range(3)])
    mx = Vector([max(c[i] for c in cs) for i in range(3)])
    return mn, mx


def center_and_fit(ob, target=0.45, post=None):
    """Bake the transform, optionally rotate (`post`, a Matrix about the origin), then
    centre the bounding box on the origin and scale so the largest dimension == target."""
    flatten_transform(ob)
    if post is not None:
        ob.data.transform(post)
    mn, mx = bbox(ob)
    ctr = (mn + mx) * 0.5
    dim = mx - mn
    k = target / max(dim) if target else 1.0
    ob.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation(-ctr))
    ob.data.update()
    mn, mx = bbox(ob)
    return (mx - mn)


# --------------------------------------------------------------------------------------
# renders
# --------------------------------------------------------------------------------------

def pu_shots(stem, size=0.45, samples=40, res=(860, 860)):
    """Front-three-quarter hero + a rear-three-quarter so the back of the prop is judged too.
    Shot long (3 x the prop) so the perspective matches what the player sees at 3-10 m."""
    d = size * 3.0
    a = _render_safe(path=os.path.join(PROPS_RENDERS, f'{stem}_hero.png'), target=(0, 0, 0),
                     distance=d, yaw_deg=34, pitch_deg=16, res=res, samples=samples,
                     world_strength=0.55, lens=85, ground=False)
    b = _render_safe(path=os.path.join(PROPS_RENDERS, f'{stem}_back.png'), target=(0, 0, 0),
                     distance=d, yaw_deg=152, pitch_deg=10, res=res, samples=samples,
                     world_strength=0.55, lens=85, ground=False)
    return a, b


def lineup(ids, path, yaw_each=28.0, cols=3, pitch=0.68, cam_yaw=0.0, cam_pitch=6.0,
           samples=48, res=(1280, 720), lens=50):
    """Import the exported GLBs and render them as a contact sheet."""
    props_scene()
    scn = bpy.context.scene
    n = len(ids)
    rows = (n + cols - 1) // cols
    roots = []
    for i, pid in enumerate(ids):
        p = os.path.join(PROPS_DIR, f'pu_{pid}.glb')
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=p)
        new = [o for o in bpy.data.objects if o not in before]
        col, row = i % cols, i // cols
        x = (col - (cols - 1) / 2.0) * pitch
        z = ((rows - 1) / 2.0 - row) * pitch
        for o in new:
            if o.parent is None:
                mw = o.matrix_world.copy()
                mw.translation = Vector((0, 0, 0))
                o.matrix_world = (Matrix.Translation((x, 0, z))
                                  @ Matrix.Rotation(D2R(yaw_each), 4, 'Z') @ mw)
                roots.append(o)
    bpy.context.view_layer.update()
    # frame the whole grid: 36 mm sensor fitted to the long (horizontal) axis
    need_w, need_h = cols * pitch + 0.16, rows * pitch + 0.16
    dist = 1.04 * max(need_w * lens / 36.0, need_h * lens / (36.0 * res[1] / res[0]))
    return _render_safe(path=path, target=(0, 0, 0), distance=dist, yaw_deg=cam_yaw,
                        pitch_deg=cam_pitch, res=res, samples=samples, world_strength=0.55,
                        lens=lens, ground=False)
