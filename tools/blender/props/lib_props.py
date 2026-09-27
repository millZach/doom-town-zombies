"""Shared helpers for the gameplay props (area `props`).

Adds on top of tools/blender/common.py:
  * geometry builders (rounded boxes, lathes, extruded profiles, bolts, pipes, text)
  * a procedural "weathered surface" material graph (edge wear, crevice grime, rust,
    dust, dents, scratches) driven from world-space coordinates
  * `bake_pbr()` which UV-unwraps a group of objects, bakes that procedural graph into
    base-colour / ORM / normal images and replaces the materials with a single
    glTF-safe Principled material.

Import from a build script:
    import sys, os
    HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(HERE))   # tools/blender
    sys.path.insert(0, HERE)                    # tools/blender/props
    from lib_props import *
"""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector, Matrix, Euler

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from common import *  # noqa: F401,F403

PROPS_DIR = os.path.join(MODELS_DIR, 'props')
PROPS_RENDERS = os.path.join(RENDERS_DIR, 'props')
PROPS_TEX = os.path.join(TEX_CACHE, 'props')
for _d in (PROPS_DIR, PROPS_RENDERS, PROPS_TEX):
    os.makedirs(_d, exist_ok=True)

FONT_COOPER = 'C:/Windows/Fonts/COOPBL.TTF'    # Cooper Black - the 50s soda-fountain face
FONT_BAUHAUS = 'C:/Windows/Fonts/BAUHS93.TTF'  # Bauhaus 93 - geometric retro
FONT_IMPACT = 'C:/Windows/Fonts/impact.ttf'
FONT_STENCIL = 'C:/Windows/Fonts/STENCIL.TTF'  # military stencil
FONT_AGENCY = 'C:/Windows/Fonts/AGENCYB.TTF'
FONT_ARIALBD = 'C:/Windows/Fonts/arialbd.ttf'
FONT_BERNARD = 'C:/Windows/Fonts/BERNHC.TTF'
FONT_BROADWAY = 'C:/Windows/Fonts/BROADW.TTF'

TAU = math.pi * 2
D2R = math.radians

# The GPU is shared with other build agents; channel bakes are noise-free so they run on
# the CPU by default. PROPS_CPU=1 also forces the check renders onto the CPU.
BAKE_ON_CPU = os.environ.get('PROPS_GPU_BAKE', '0') != '1'
FORCE_CPU = os.environ.get('PROPS_CPU', '0') == '1'

import common as _common
_common_setup_gpu = _common.setup_gpu


def _setup_device(samples=64):
    scn = _common_setup_gpu(samples)
    if FORCE_CPU:
        scn.cycles.device = 'CPU'
        try:
            scn.cycles.denoiser = 'OPENIMAGEDENOISE'
        except Exception:
            pass
    return scn


_common.setup_gpu = _setup_device

_texref = None


# --------------------------------------------------------------------------------------
# scene
# --------------------------------------------------------------------------------------

def props_scene():
    """Fresh scene + the world-space texture reference empty every procedural material uses."""
    global _texref
    scn = reset_scene()
    _texref = bpy.data.objects.new('_texref', None)
    link(_texref)
    scn.render.engine = 'CYCLES'
    return scn


def drop_texref():
    global _texref
    if _texref is not None:
        try:
            bpy.data.objects.remove(_texref, do_unlink=True)
        except Exception:
            pass
        _texref = None


# --------------------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------------------

def _finish(name, bm, loc=(0, 0, 0), rot=(0, 0, 0), collection=None):
    bm.normal_update()
    ob = mesh_object(name, bm, collection)
    ob.location = loc
    ob.rotation_euler = rot
    # matrix_world is lazy: force it so callers can immediately place things relative to it
    bpy.context.view_layer.update()
    return ob


def rbox(name, size=(1, 1, 1), loc=(0, 0, 0), radius=0.01, seg=2, rot=(0, 0, 0), collection=None):
    """Box with a bevelled edge (modifier left on so the bake can use it after apply_mods)."""
    ob = box(name, size, loc, collection, rot)
    if radius > 0:
        m = ob.modifiers.new('Bevel', 'BEVEL')
        m.width = radius
        m.segments = seg
        m.limit_method = 'ANGLE'
        m.angle_limit = D2R(40)
        m.harden_normals = False
    return ob


def cyl(name, r=0.1, h=1.0, loc=(0, 0, 0), verts=24, rot=(0, 0, 0), cap=True,
        r_top=None, collection=None, bevel=0.0):
    bm = bmesh.new()
    if r_top is None or abs(r_top - r) < 1e-6:
        bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=verts,
                              radius1=r, radius2=r, depth=h)
    else:
        bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=verts,
                              radius1=r, radius2=r_top, depth=h)
    ob = _finish(name, bm, loc, rot, collection)
    if bevel > 0:
        m = ob.modifiers.new('Bevel', 'BEVEL')
        m.width = bevel; m.segments = 2; m.limit_method = 'ANGLE'; m.angle_limit = D2R(40)
    return ob


def tube(name, r_out=0.1, r_in=0.08, h=1.0, loc=(0, 0, 0), verts=24, rot=(0, 0, 0), collection=None):
    bm = bmesh.new()
    for i in range(verts):
        a0 = i / verts * TAU
        a1 = (i + 1) / verts * TAU
        pts = [(math.cos(a0) * r_in, math.sin(a0) * r_in),
               (math.cos(a0) * r_out, math.sin(a0) * r_out),
               (math.cos(a1) * r_out, math.sin(a1) * r_out),
               (math.cos(a1) * r_in, math.sin(a1) * r_in)]
        for z in (-h / 2, h / 2):
            vs = [bm.verts.new((x, y, z)) for x, y in pts]
            bm.faces.new(vs if z > 0 else vs[::-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    # side walls
    bm.verts.ensure_lookup_table()
    for rr, flip in ((r_out, False), (r_in, True)):
        for i in range(verts):
            a0 = i / verts * TAU; a1 = (i + 1) / verts * TAU
            p = [(math.cos(a0) * rr, math.sin(a0) * rr, -h / 2),
                 (math.cos(a1) * rr, math.sin(a1) * rr, -h / 2),
                 (math.cos(a1) * rr, math.sin(a1) * rr, h / 2),
                 (math.cos(a0) * rr, math.sin(a0) * rr, h / 2)]
            vs = [bm.verts.new(q) for q in p]
            bm.faces.new(vs[::-1] if flip else vs)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    return _finish(name, bm, loc, rot, collection)


def profile_extrude(name, pts_xz, depth=1.0, loc=(0, 0, 0), rot=(0, 0, 0), collection=None,
                    bevel=0.0, bseg=2):
    """Closed 2D profile in the XZ plane, extruded along Y by `depth` (centred on Y=0)."""
    bm = bmesh.new()
    back = [bm.verts.new((x, depth / 2, z)) for x, z in pts_xz]
    front = [bm.verts.new((x, -depth / 2, z)) for x, z in pts_xz]
    bm.faces.new(back)
    bm.faces.new(front[::-1])
    n = len(pts_xz)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([front[i], front[j], back[j], back[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = _finish(name, bm, loc, rot, collection)
    if bevel > 0:
        m = ob.modifiers.new('Bevel', 'BEVEL')
        m.width = bevel; m.segments = bseg; m.limit_method = 'ANGLE'; m.angle_limit = D2R(30)
    return ob


def lathe(name, profile_xz, verts=24, loc=(0, 0, 0), rot=(0, 0, 0), collection=None, close=True):
    """Spin a profile (list of (radius, z)) around the Z axis."""
    bm = bmesh.new()
    rings = []
    for i in range(verts):
        a = i / verts * TAU
        ca, sa = math.cos(a), math.sin(a)
        rings.append([bm.verts.new((r * ca, r * sa, z)) for r, z in profile_xz])
    n = len(profile_xz)
    for i in range(verts):
        r0 = rings[i]; r1 = rings[(i + 1) % verts]
        for k in range(n - 1):
            a, b, c, d = r0[k], r0[k + 1], r1[k + 1], r1[k]
            if (a.co - b.co).length < 1e-6:
                continue
            bm.faces.new([a, b, c, d])
    if close:
        for k, flip in ((0, True), (n - 1, False)):
            if abs(profile_xz[k][0]) > 1e-6:
                ring = [rings[i][k] for i in range(verts)]
                try:
                    bm.faces.new(ring[::-1] if flip else ring)
                except Exception:
                    pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _finish(name, bm, loc, rot, collection)


def rounded_rect(hw, hd, r, seg=4, z=0.0):
    """Points of a rectangle with rounded corners, CCW in the XY plane, at height z."""
    r = max(0.0, min(r, hw - 1e-4, hd - 1e-4))
    pts = []
    corners = [(hw - r, hd - r, 0.0), (-(hw - r), hd - r, math.pi / 2),
               (-(hw - r), -(hd - r), math.pi), (hw - r, -(hd - r), 3 * math.pi / 2)]
    for cx, cy, a0 in corners:
        for k in range(seg + 1):
            a = a0 + k / seg * (math.pi / 2)
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r, z))
    # NOTE: coincident points are deliberately kept so that every ring of a given
    # `seg` has the same vertex count and can be lofted against any other; `loft`
    # drops the degenerate faces and welds the duplicates.
    return pts


def loft(name, rings, cap_bottom=True, cap_top=True, loc=(0, 0, 0), rot=(0, 0, 0),
         collection=None, bevel=0.0, bseg=2):
    """Skin a stack of equal-length vertex rings."""
    bm = bmesh.new()
    vrings = [[bm.verts.new(p) for p in ring] for ring in rings]
    n = len(rings[0])
    for i in range(len(vrings) - 1):
        a, b = vrings[i], vrings[i + 1]
        for k in range(n):
            k2 = (k + 1) % n
            vs = [a[k], a[k2], b[k2], b[k]]
            uniq = []
            for v in vs:
                if not uniq or (v.co - uniq[-1].co).length > 1e-7:
                    uniq.append(v)
            if len(uniq) >= 3 and (uniq[0].co - uniq[-1].co).length > 1e-7:
                try:
                    bm.faces.new(uniq)
                except Exception:
                    pass
    if cap_bottom:
        try:
            bm.faces.new(vrings[0][::-1])
        except Exception:
            pass
    if cap_top:
        try:
            bm.faces.new(vrings[-1])
        except Exception:
            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = _finish(name, bm, loc, rot, collection)
    if bevel > 0:
        m = ob.modifiers.new('Bevel', 'BEVEL')
        m.width = bevel; m.segments = bseg; m.limit_method = 'ANGLE'; m.angle_limit = D2R(30)
    return ob


def bolt(name, r=0.012, h=0.008, loc=(0, 0, 0), rot=(0, 0, 0), collection=None, washer=False):
    """Hex-head bolt / rivet head."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=6,
                          radius1=r, radius2=r * 0.86, depth=h)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, h / 2))
    if washer:
        bm2 = bmesh.new()
        bmesh.ops.create_cone(bm2, cap_ends=True, cap_tris=False, segments=12,
                              radius1=r * 1.5, radius2=r * 1.5, depth=h * 0.35)
        me = bpy.data.meshes.new('_tmp'); bm2.to_mesh(me); bm2.free()
        bm.from_mesh(me); bpy.data.meshes.remove(me)
    ob = _finish(name, bm, loc, rot, collection)
    m = ob.modifiers.new('Bevel', 'BEVEL')
    m.width = r * 0.14; m.segments = 1; m.limit_method = 'ANGLE'; m.angle_limit = D2R(35)
    return ob


def uvsphere(name, r=0.1, loc=(0, 0, 0), rot=(0, 0, 0), segs=16, rings=9, scale=(1, 1, 1),
             collection=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    if scale != (1, 1, 1):
        bmesh.ops.scale(bm, vec=Vector(scale), verts=bm.verts)
    return _finish(name, bm, loc, rot, collection)


def _link_verts(bm, R, wire, L, major=10, minor=6, mat=None):
    """One stadium-shaped chain link lying in the XY plane, long axis X."""
    ring = []
    for i in range(major):
        u = i / major * TAU
        cu, su = math.cos(u), math.sin(u)
        off = L / 2 if cu >= 0 else -L / 2
        loop = []
        for j in range(minor):
            v = j / minor * TAU
            rr = R + wire * math.cos(v)
            p = Vector((rr * cu + off, rr * su, wire * math.sin(v)))
            if mat is not None:
                p = mat @ p
            loop.append(bm.verts.new(p))
        ring.append(loop)
    for i in range(major):
        a, b = ring[i], ring[(i + 1) % major]
        for j in range(minor):
            j2 = (j + 1) % minor
            bm.faces.new([a[j], a[j2], b[j2], b[j]])


def chain(name, points, link_len=0.030, link_r=0.011, wire=0.0035, major=8, minor=5,
          collection=None):
    """Interlocking chain following a polyline."""
    pts = [Vector(p) for p in points]
    # resample the polyline at a constant spacing
    seglen = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
    total = sum(seglen)
    pitch = link_len + link_r * 2 - wire * 4
    n = max(2, int(total / pitch))
    bm = bmesh.new()
    for k in range(n):
        s = (k + 0.5) / n * total
        acc = 0.0
        for i, sl in enumerate(seglen):
            if acc + sl >= s or i == len(seglen) - 1:
                t = (s - acc) / max(sl, 1e-6)
                p = pts[i].lerp(pts[i + 1], min(1.0, t))
                d = (pts[i + 1] - pts[i]).normalized()
                break
            acc += sl
        up = Vector((0, 0, 1))
        if abs(d.dot(up)) > 0.95:
            up = Vector((0, 1, 0))
        x = d
        y = up.cross(x).normalized()
        z = x.cross(y)
        rot = Matrix((x, y, z)).transposed().to_4x4()
        if k % 2:
            rot = rot @ Matrix.Rotation(math.pi / 2, 4, 'X')
        m = Matrix.Translation(p) @ rot
        _link_verts(bm, link_r, wire, link_len, major, minor, m)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _finish(name, bm, (0, 0, 0), (0, 0, 0), collection)


def pipe_path(name, points, r=0.03, verts=10, collection=None, caps=True):
    """Tube following a polyline (list of Vector/tuple)."""
    pts = [Vector(p) for p in points]
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(pts):
        if i == 0:
            d = (pts[1] - pts[0]).normalized()
        elif i == len(pts) - 1:
            d = (pts[-1] - pts[-2]).normalized()
        else:
            d = ((pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()).normalized()
        up = Vector((0, 0, 1))
        if abs(d.dot(up)) > 0.95:
            up = Vector((1, 0, 0))
        x = d.cross(up).normalized()
        y = d.cross(x).normalized()
        ring = []
        for k in range(verts):
            a = k / verts * TAU
            ring.append(bm.verts.new(p + x * (math.cos(a) * r) + y * (math.sin(a) * r)))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(verts):
            k2 = (k + 1) % verts
            bm.faces.new([rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]])
    if caps:
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _finish(name, bm, (0, 0, 0), (0, 0, 0), collection)


def text_mesh(name, body, font=FONT_COOPER, size=0.2, extrude=0.008, bev=0.0025,
              loc=(0, 0, 0), rot=(D2R(90), 0, 0), align='CENTER', spacing=1.0,
              collection=None, res=2, bres=1, shear=0.0):
    """Text object converted to mesh. Default rotation stands it up facing -Y."""
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body
    try:
        cu.font = bpy.data.fonts.load(font, check_existing=True)
    except Exception:
        pass
    cu.size = size
    cu.extrude = extrude
    cu.bevel_depth = bev
    cu.bevel_resolution = bres
    cu.resolution_u = res
    cu.align_x = align
    cu.align_y = 'CENTER'
    cu.space_character = spacing
    cu.shear = shear
    ob = bpy.data.objects.new(name, cu)
    link(ob, collection)
    ob.location = loc
    ob.rotation_euler = rot
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.convert(target='MESH')
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def jitter(ob, amount=0.004, scale=6.0, seed=1, axis=(1, 1, 1)):
    """Push vertices around with value noise - warped planks, dented panels."""
    import mathutils.noise as mn
    rnd = Vector((seed * 13.1, seed * 7.7, seed * 3.3))
    me = ob.data
    for v in me.vertices:
        p = v.co * scale + rnd
        d = Vector((mn.noise(p), mn.noise(p + Vector((5.2, 1.3, 9.1))), mn.noise(p + Vector((2.7, 8.4, 4.4)))))
        v.co += Vector((d.x * axis[0], d.y * axis[1], d.z * axis[2])) * amount
    me.update()
    return ob


def join(name, objs, keep_first_transform=True):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def set_origin(ob, world_point):
    """Move the object origin to a world-space point, keeping the geometry where it is."""
    bpy.context.view_layer.update()
    wp = Vector(world_point)
    mw = ob.matrix_world.copy()
    delta = mw.inverted() @ wp
    ob.data.transform(Matrix.Translation(-delta))
    ob.matrix_world.translation = wp
    return ob


def apply_mods(objs):
    for ob in objs:
        if ob.type != 'MESH' or not ob.modifiers:
            continue
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        for m in list(ob.modifiers):
            try:
                bpy.ops.object.modifier_apply(modifier=m.name)
            except Exception as e:
                print('  modifier apply failed', ob.name, m.name, e)


def tri_count(objs=None):
    objs = objs or [o for o in bpy.context.scene.objects if o.type == 'MESH']
    n = 0
    for o in objs:
        me = o.data
        for p in me.polygons:
            n += len(p.vertices) - 2
    return n


def decimate_to(ob, ratio):
    m = ob.modifiers.new('Dec', 'DECIMATE')
    m.ratio = ratio
    return m


# --------------------------------------------------------------------------------------
# procedural weathering material
# --------------------------------------------------------------------------------------

def _nd(nt, t, **kw):
    n = nt.nodes.new(t)
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def _mix(nt, fac, a, b, blend='MIX'):
    """MixRGB with sockets that may be sockets or constants. Returns the output socket."""
    n = nt.nodes.new('ShaderNodeMixRGB')
    n.blend_type = blend
    for idx, val in ((0, fac), (1, a), (2, b)):
        if val is None:
            continue
        if hasattr(val, 'node'):
            nt.links.new(val, n.inputs[idx])
        elif isinstance(val, (int, float)):
            if idx == 0:
                n.inputs[0].default_value = val
            else:
                n.inputs[idx].default_value = (val, val, val, 1)
        else:
            n.inputs[idx].default_value = (*val[:3], 1)
    return n.outputs[0]


def _math(nt, op, a, b=None, c=None, clamp=False):
    n = nt.nodes.new('ShaderNodeMath')
    n.operation = op
    n.use_clamp = clamp
    for idx, val in ((0, a), (1, b), (2, c)):
        if val is None:
            continue
        if hasattr(val, 'node'):
            nt.links.new(val, n.inputs[idx])
        else:
            n.inputs[idx].default_value = val
    return n.outputs[0]


def _ramp(nt, fac, stops):
    """stops: list of (pos, value_or_rgb)."""
    n = nt.nodes.new('ShaderNodeValToRGB')
    if hasattr(fac, 'node'):
        nt.links.new(fac, n.inputs[0])
    el = n.color_ramp.elements
    while len(el) > 1:
        el.remove(el[-1])
    for i, (pos, val) in enumerate(stops):
        e = el[0] if i == 0 else el.new(pos)
        e.position = pos
        e.color = (val, val, val, 1) if isinstance(val, (int, float)) else (*val[:3], 1)
    return n.outputs[0]


def _coords(nt, scale=1.0, rot=(0, 0, 0), loc=(0, 0, 0)):
    tc = nt.nodes.new('ShaderNodeTexCoord')
    if _texref is not None:
        tc.object = _texref
    mp = nt.nodes.new('ShaderNodeMapping')
    nt.links.new(tc.outputs['Object'], mp.inputs[0])
    mp.inputs[1].default_value = loc
    mp.inputs[2].default_value = rot
    mp.inputs[3].default_value = (scale, scale, scale)
    return mp.outputs[0], tc


def _noise(nt, co, scale=5.0, detail=6.0, rough=0.55, distortion=0.0, w=0.0, dim='3D'):
    n = nt.nodes.new('ShaderNodeTexNoise')
    n.noise_dimensions = dim
    nt.links.new(co, n.inputs['Vector'])
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = detail
    n.inputs['Roughness'].default_value = rough
    n.inputs['Distortion'].default_value = distortion
    if dim == '4D':
        n.inputs['W'].default_value = w
    return n.outputs['Factor']


def weathered(name, color=(0.5, 0.1, 0.1), roughness=0.42, metallic=0.0,
              wear_color=(0.52, 0.52, 0.55), wear=0.35, wear_rough=0.3, wear_metal=1.0,
              rust=0.0, rust_color=(0.26, 0.11, 0.045),
              grime=0.55, grime_color=(0.055, 0.05, 0.045),
              dust=0.2, dust_color=(0.44, 0.40, 0.33),
              variation=0.18, scale=1.0, seed=0.0,
              bump=0.5, dent=0.0, scratch=0.5, ao_dist=0.08,
              pointy_lo=0.49, pointy_hi=0.56, emission=None, emission_strength=0.0,
              speckle=0.35, streak=0.0):
    """A full grunge shader. Only ever used as a bake source - never exported directly.

    color        base paint / material colour
    wear         how much bare scuffed metal shows on the convex edges
    rust         amount of rust blooming from edges and low areas
    grime        dark dirt accumulating in the crevices (AO driven)
    dust         pale dust settling on upward-facing surfaces
    dent         low-frequency bump (panel dents)
    scratch      fine directional scratch bump
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    co, _tc = _coords(nt, scale=scale, loc=(seed * 3.7, seed * 1.9, seed * 5.1))

    geo = nt.nodes.new('ShaderNodeNewGeometry')

    # --- masks -------------------------------------------------------------------
    # convex edge mask (pointiness), broken up by noise so wear is patchy
    edge_raw = _ramp(nt, geo.outputs['Pointiness'], [(pointy_lo, 0.0), (pointy_hi, 1.0)])
    edge_noise = _ramp(nt, _noise(nt, co, 14.0 , 6.0, 0.6), [(0.30, 0.15), (0.62, 1.0)])
    edge = _math(nt, 'MULTIPLY', edge_raw, edge_noise)

    # crevice / cavity mask
    ao = nt.nodes.new('ShaderNodeAmbientOcclusion')
    ao.samples = 8
    ao.inside = True
    ao.only_local = True
    ao.inputs['Distance'].default_value = ao_dist
    cav = _ramp(nt, ao.outputs['AO'], [(0.02, 0.0), (0.45, 1.0)])
    cav_n = _ramp(nt, _noise(nt, co, 5.0, 5.0, 0.6), [(0.35, 0.25), (0.7, 1.0)])
    cav = _math(nt, 'MULTIPLY', cav, cav_n)

    # height above the floor -> more filth low down
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(geo.outputs['Position'], sep.inputs[0])
    low = _ramp(nt, sep.outputs['Z'], [(0.0, 1.0), (0.55, 0.0)])

    # upward-facing mask for dust
    nsep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(geo.outputs['Normal'], nsep.inputs[0])
    up = _ramp(nt, nsep.outputs['Z'], [(0.25, 0.0), (0.85, 1.0)])

    # --- colour ------------------------------------------------------------------
    # base with low-frequency tonal variation (uneven old paint)
    var_n = _noise(nt, co, 2.2, 4.0, 0.55)
    dark = tuple(c * (1 - variation * 1.4) for c in color[:3])
    lite = tuple(min(1.0, c * (1 + variation * 1.1)) for c in color[:3])
    base = _mix(nt, _ramp(nt, var_n, [(0.25, 0.0), (0.75, 1.0)]), dark, lite)

    # micro speckle (kept sub-millimetre so it never reads as sugar)
    if speckle > 0:
        base = _mix(nt, _math(nt, 'MULTIPLY', _noise(nt, co, 260.0, 2.0, 0.5), 0.14 * speckle),
                    base, tuple(c * 0.72 for c in color[:3]))

    rough_out = _math(nt, 'ADD', roughness,
                      _math(nt, 'MULTIPLY', _noise(nt, co, 9.0, 4.0, 0.6), 0.12))
    metal_out = metallic

    # rust: patchy, favours edges and low areas
    if rust > 0:
        rn = _ramp(nt, _noise(nt, co, 4.5, 8.0, 0.75, distortion=1.5),
                   [(0.42, 0.0), (0.66, 1.0)])
        rmask = _math(nt, 'MULTIPLY', rn,
                      _math(nt, 'ADD', _math(nt, 'MULTIPLY', edge_raw, 0.9),
                            _math(nt, 'MULTIPLY', low, 0.55), clamp=True))
        rmask = _math(nt, 'MULTIPLY', rmask, rust, clamp=True)
        rust_dark = tuple(c * 0.45 for c in rust_color[:3])
        rust_col = _mix(nt, _ramp(nt, _noise(nt, co, 22.0, 5.0, 0.6), [(0.35, 0.0), (0.7, 1.0)]),
                        rust_dark, rust_color)
        base = _mix(nt, rmask, base, rust_col)
        rough_out = _mix(nt, rmask, rough_out, 0.93).node.outputs[0] if False else _math(
            nt, 'ADD', _math(nt, 'MULTIPLY', rough_out, _math(nt, 'SUBTRACT', 1.0, rmask)),
            _math(nt, 'MULTIPLY', rmask, 0.92))
        metal_out = _math(nt, 'MULTIPLY', metal_out if not isinstance(metal_out, float) else metal_out,
                          _math(nt, 'SUBTRACT', 1.0, rmask)) if metallic > 0 else 0.0

    # bare scuffed substrate on the sharp edges
    if wear > 0:
        wmask = _math(nt, 'MULTIPLY', edge, wear, clamp=True)
        base = _mix(nt, wmask, base, wear_color)
        rough_out = _math(nt, 'ADD', _math(nt, 'MULTIPLY', rough_out, _math(nt, 'SUBTRACT', 1.0, wmask)),
                          _math(nt, 'MULTIPLY', wmask, wear_rough))
        if wear_metal > 0:
            mprev = metal_out
            metal_out = _math(nt, 'ADD',
                              _math(nt, 'MULTIPLY', mprev, _math(nt, 'SUBTRACT', 1.0, wmask)),
                              _math(nt, 'MULTIPLY', wmask, wear_metal))

    # grime in the crevices
    if grime > 0:
        gmask = _math(nt, 'MULTIPLY', cav, grime, clamp=True)
        gmask = _math(nt, 'ADD', gmask, _math(nt, 'MULTIPLY', _math(nt, 'MULTIPLY', low, grime), 0.45), clamp=True)
        base = _mix(nt, gmask, base, grime_color)
        rough_out = _math(nt, 'ADD', _math(nt, 'MULTIPLY', rough_out, _math(nt, 'SUBTRACT', 1.0, gmask)),
                          _math(nt, 'MULTIPLY', gmask, 0.88))
        metal_out = _math(nt, 'MULTIPLY', metal_out, _math(nt, 'SUBTRACT', 1.0, _math(nt, 'MULTIPLY', gmask, 0.8))) \
            if not isinstance(metal_out, float) or metal_out > 0 else metal_out

    # vertical grime streaks running down from ledges
    if streak > 0:
        mps = nt.nodes.new('ShaderNodeMapping')
        nt.links.new(co, mps.inputs[0])
        mps.inputs[3].default_value = (9.0, 9.0, 0.60)
        st = _ramp(nt, _noise(nt, mps.outputs[0], 7.0, 8.0, 0.75, distortion=1.6),
                   [(0.50, 0.0), (0.70, 1.0)])
        # only under a few patches, and fading out as it runs down
        broad = _ramp(nt, _noise(nt, co, 2.6, 5.0, 0.6), [(0.53, 0.0), (0.74, 1.0)])
        fade = _ramp(nt, _noise(nt, co, 0.9, 2.0, 0.5), [(0.38, 0.25), (0.75, 1.0)])
        smask = _math(nt, 'MULTIPLY', _math(nt, 'MULTIPLY', st, broad),
                      _math(nt, 'MULTIPLY', fade, streak * 0.75), clamp=True)
        streak_col = tuple(g * 0.5 + 0.06 for g in grime_color[:3])
        base = _mix(nt, smask, base, streak_col)
        rough_out = _math(nt, 'ADD', _math(nt, 'MULTIPLY', rough_out,
                                           _math(nt, 'SUBTRACT', 1.0, smask)),
                          _math(nt, 'MULTIPLY', smask, 0.8))

    # pale dust on top surfaces
    if dust > 0:
        dmask = _math(nt, 'MULTIPLY', up,
                      _math(nt, 'MULTIPLY', dust,
                            _ramp(nt, _noise(nt, co, 7.0, 4.0, 0.6), [(0.3, 0.3), (0.75, 1.0)])), clamp=True)
        base = _mix(nt, dmask, base, dust_color)
        rough_out = _math(nt, 'ADD', _math(nt, 'MULTIPLY', rough_out, _math(nt, 'SUBTRACT', 1.0, dmask)),
                          _math(nt, 'MULTIPLY', dmask, 0.95))

    # --- bump --------------------------------------------------------------------
    h = _math(nt, 'MULTIPLY', _noise(nt, co, 55.0, 4.0, 0.55), 0.16 * bump)
    if scratch > 0:
        # long, shallow directional scuffs - NOT an isotropic cell network (that aliases)
        sc = nt.nodes.new('ShaderNodeTexVoronoi')
        sc.feature = 'DISTANCE_TO_EDGE'
        sc.voronoi_dimensions = '3D'
        mp2 = nt.nodes.new('ShaderNodeMapping')
        nt.links.new(co, mp2.inputs[0])
        mp2.inputs[3].default_value = (0.7, 6.0, 6.0)
        nt.links.new(mp2.outputs[0], sc.inputs['Vector'])
        sc.inputs['Scale'].default_value = 11.0
        sc.inputs['Randomness'].default_value = 1.0
        scm = _math(nt, 'MULTIPLY',
                    _ramp(nt, sc.outputs['Distance'], [(0.0, 1.0), (0.035, 0.0)]),
                    _ramp(nt, _noise(nt, co, 3.0, 4.0, 0.6), [(0.35, 0.0), (0.65, 1.0)]))
        h = _math(nt, 'SUBTRACT', h, _math(nt, 'MULTIPLY', scm, 0.055 * scratch))
    if dent > 0:
        dv = nt.nodes.new('ShaderNodeTexVoronoi')
        dv.feature = 'SMOOTH_F1'
        dv.voronoi_dimensions = '3D'
        nt.links.new(co, dv.inputs['Vector'])
        dv.inputs['Scale'].default_value = 6.5
        dv.inputs['Smoothness'].default_value = 0.75
        dv.inputs['Randomness'].default_value = 1.0
        dmask = _math(nt, 'MULTIPLY',
                      _ramp(nt, dv.outputs['Distance'], [(0.0, 0.0), (0.22, 1.0)]),
                      _ramp(nt, _noise(nt, co, 1.4, 3.0, 0.5), [(0.42, 0.0), (0.62, 1.0)]))
        h = _math(nt, 'ADD', h, _math(nt, 'MULTIPLY', dmask, 1.5 * dent))
    if rust > 0:
        h = _math(nt, 'ADD', h, _math(nt, 'MULTIPLY', _noise(nt, co, 40.0, 6.0, 0.8), 0.25 * rust))
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = 1.0
    bp.inputs['Distance'].default_value = 0.0035
    nt.links.new(h, bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], bsdf.inputs['Normal'])

    nt.links.new(base, bsdf.inputs['Base Color'])
    if hasattr(rough_out, 'node'):
        nt.links.new(rough_out, bsdf.inputs['Roughness'])
    else:
        bsdf.inputs['Roughness'].default_value = rough_out
    if hasattr(metal_out, 'node'):
        nt.links.new(metal_out, bsdf.inputs['Metallic'])
    else:
        bsdf.inputs['Metallic'].default_value = float(metal_out)
    if emission is not None:
        bsdf.inputs['Emission Color'].default_value = (*emission[:3], 1)
        bsdf.inputs['Emission Strength'].default_value = emission_strength
    return mat


def chrome(name, tint=(0.83, 0.84, 0.86), rough=0.11, grime=0.35, scratch=1.0, pit=0.4,
           scale=1.0, seed=3.0):
    """Scuffed, pitted chrome trim - smooth, with scratches and tarnish, never grainy."""
    return weathered(name, color=tint, roughness=rough, metallic=1.0,
                     wear_color=(0.40, 0.385, 0.37), wear=0.22, wear_rough=0.42, wear_metal=1.0,
                     rust=0.13 * pit, rust_color=(0.22, 0.12, 0.06),
                     grime=grime, grime_color=(0.055, 0.05, 0.048),
                     dust=0.10, variation=0.035, scale=scale, seed=seed,
                     bump=0.22, dent=0.35, scratch=scratch, ao_dist=0.05,
                     speckle=0.10, streak=0.35)


def painted(name, color, rough=0.30, wear=0.34, rust=0.32, grime=0.62, dent=0.6, scale=1.0,
            seed=0.0, variation=0.15, dust=0.09, streak=0.45, speckle=0.3):
    """Chipped enamel over steel."""
    return weathered(name, color=color, roughness=rough, metallic=0.0,
                     wear_color=(0.205, 0.196, 0.186), wear=wear, wear_rough=0.45, wear_metal=0.9,
                     rust=rust, grime=grime, dust=dust, variation=variation,
                     scale=scale, seed=seed, bump=0.55, dent=dent, scratch=0.7, ao_dist=0.09,
                     speckle=speckle, streak=streak)


_AXIS_VEC = {'X': (1, 0, 0), 'Y': (0, 1, 0), 'Z': (0, 0, 1)}


def wood_mat(name, color=(0.185, 0.112, 0.058), rough=0.74, grime=0.6, seed=0.0, scale=1.0,
             grain=1.0, split=0.5, axis='X', bleach=0.22, knots=1.0):
    """Weathered bare timber. `axis` is the direction the grain runs (world space)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    co, _tc = _coords(nt, scale=scale, loc=(seed * 4.3, seed * 2.1, seed * 6.7))
    geo = nt.nodes.new('ShaderNodeNewGeometry')

    def stretched(sx, cross):
        """Mapping scale that squashes along the grain axis and expands across it."""
        a = _AXIS_VEC[axis]
        return tuple(sx if a[i] else cross for i in range(3))

    # --- grain: noise stretched along the plank ---------------------------------
    mp = nt.nodes.new('ShaderNodeMapping')
    nt.links.new(co, mp.inputs[0])
    mp.inputs[3].default_value = stretched(0.055, 3.6)
    gn = _noise(nt, mp.outputs[0], 11.0, 8.0, 0.68, distortion=0.9)
    grainmask = _ramp(nt, gn, [(0.33, 0.0), (0.52, 0.5), (0.72, 1.0)])

    dark = tuple(c * 0.55 for c in color[:3])
    lite = tuple(min(1.0, c * 1.55 + 0.012) for c in color[:3])
    base = _mix(nt, grainmask, dark, lite)

    # tighter ring lines on top
    mp3 = nt.nodes.new('ShaderNodeMapping')
    nt.links.new(co, mp3.inputs[0])
    mp3.inputs[3].default_value = stretched(0.03, 2.2)
    fine = _noise(nt, mp3.outputs[0], 34.0, 5.0, 0.55, distortion=0.5)
    base = _mix(nt, _math(nt, 'MULTIPLY', _ramp(nt, fine, [(0.42, 0.0), (0.62, 1.0)]), 0.3 * grain),
                base, tuple(c * 0.42 for c in color[:3]))

    # broad tonal blotches - damp/soaked patches, not grey wash
    blot = _ramp(nt, _noise(nt, co, 1.7, 5.0, 0.6), [(0.38, 0.0), (0.72, 1.0)])
    base = _mix(nt, _math(nt, 'MULTIPLY', blot, 0.5), base, tuple(c * 0.5 for c in color[:3]))

    # sun-bleached silvering, restrained
    grey = _ramp(nt, _noise(nt, co, 3.4, 6.0, 0.62), [(0.52, 0.0), (0.78, 1.0)])
    base = _mix(nt, _math(nt, 'MULTIPLY', grey, bleach), base, (0.235, 0.215, 0.19))

    # knots
    kn = None
    if knots > 0:
        kv = nt.nodes.new('ShaderNodeTexVoronoi')
        kv.feature = 'F1'
        mpk = nt.nodes.new('ShaderNodeMapping')
        nt.links.new(co, mpk.inputs[0])
        mpk.inputs[3].default_value = stretched(0.35, 2.4)
        nt.links.new(mpk.outputs[0], kv.inputs['Vector'])
        kv.inputs['Scale'].default_value = 3.0
        kv.inputs['Randomness'].default_value = 1.0
        kn = _ramp(nt, kv.outputs['Distance'], [(0.0, 1.0), (0.10, 0.0)])
        base = _mix(nt, _math(nt, 'MULTIPLY', kn, 0.85 * knots), base,
                    tuple(c * 0.28 for c in color[:3]))

    # dirt in cavities
    ao = nt.nodes.new('ShaderNodeAmbientOcclusion')
    ao.samples = 8; ao.inside = True; ao.only_local = True
    ao.inputs['Distance'].default_value = 0.05
    cav = _ramp(nt, ao.outputs['AO'], [(0.02, 0.0), (0.5, 1.0)])
    base = _mix(nt, _math(nt, 'MULTIPLY', cav, grime), base, (0.030, 0.024, 0.019))

    # worn, splintered light edges
    edge = _ramp(nt, geo.outputs['Pointiness'], [(0.49, 0.0), (0.575, 1.0)])
    edge = _math(nt, 'MULTIPLY', edge, _ramp(nt, _noise(nt, co, 16.0, 5.0, 0.6), [(0.32, 0.2), (0.7, 1.0)]))
    base = _mix(nt, _math(nt, 'MULTIPLY', edge, 0.45), base, (0.33, 0.26, 0.185))

    rough_out = _math(nt, 'ADD', rough, _math(nt, 'MULTIPLY', grainmask, 0.14))
    nt.links.new(base, bsdf.inputs['Base Color'])
    nt.links.new(rough_out, bsdf.inputs['Roughness'])
    bsdf.inputs['Metallic'].default_value = 0.0

    h = _math(nt, 'MULTIPLY', grainmask, 0.45)
    h = _math(nt, 'ADD', h, _math(nt, 'MULTIPLY', fine, 0.3))
    if kn is not None:
        h = _math(nt, 'SUBTRACT', h, _math(nt, 'MULTIPLY', kn, 0.5 * knots))
    # long splits running with the grain
    sp = nt.nodes.new('ShaderNodeTexVoronoi')
    sp.feature = 'DISTANCE_TO_EDGE'
    mp4 = nt.nodes.new('ShaderNodeMapping')
    nt.links.new(co, mp4.inputs[0])
    mp4.inputs[3].default_value = stretched(0.05, 2.0)
    nt.links.new(mp4.outputs[0], sp.inputs['Vector'])
    sp.inputs['Scale'].default_value = 7.0
    h = _math(nt, 'SUBTRACT', h, _math(nt, 'MULTIPLY',
                                       _ramp(nt, sp.outputs['Distance'], [(0.0, 1.0), (0.035, 0.0)]),
                                       1.1 * split))
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = 1.0
    bp.inputs['Distance'].default_value = 0.006
    nt.links.new(h, bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def painted_wood(name, color=(0.62, 0.60, 0.53), rough=0.45, chip=0.55, grime=0.7,
                 scale=1.0, seed=0.0, dust=0.18, axis='X',
                 wood=(0.175, 0.105, 0.052), peel=0.55):
    """Old house paint flaking off timber: broad peeled patches showing bare wood,
    chipped edges, dirt in the mouldings."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    co, _tc = _coords(nt, scale=scale, loc=(seed * 2.9, seed * 5.3, seed * 1.7))
    geo = nt.nodes.new('ShaderNodeNewGeometry')

    def stretched(sx, cross):
        a = _AXIS_VEC[axis]
        return tuple(sx if a[i] else cross for i in range(3))

    # --- the wood underneath ------------------------------------------------
    mpw = nt.nodes.new('ShaderNodeMapping')
    nt.links.new(co, mpw.inputs[0])
    mpw.inputs[3].default_value = stretched(0.055, 3.6)
    grain = _ramp(nt, _noise(nt, mpw.outputs[0], 13.0, 8.0, 0.68, distortion=0.9),
                  [(0.33, 0.0), (0.72, 1.0)])
    woodcol = _mix(nt, grain, tuple(c * 0.55 for c in wood), tuple(min(1.0, c * 1.6) for c in wood))

    # --- paint --------------------------------------------------------------
    dark = tuple(c * 0.78 for c in color[:3])
    lite = tuple(min(1.0, c * 1.12 + 0.02) for c in color[:3])
    paint = _mix(nt, _ramp(nt, _noise(nt, co, 2.4, 5.0, 0.6), [(0.3, 0.0), (0.72, 1.0)]), dark, lite)
    paint = _mix(nt, _math(nt, 'MULTIPLY', _noise(nt, co, 40.0, 3.0, 0.7), 0.25), paint,
                 tuple(c * 0.7 for c in color[:3]))
    # yellowed / nicotine staining low down and in patches
    stain = _ramp(nt, _noise(nt, co, 1.6, 4.0, 0.55), [(0.42, 0.0), (0.8, 1.0)])
    paint = _mix(nt, _math(nt, 'MULTIPLY', stain, 0.45), paint,
                 (color[0] * 0.82, color[1] * 0.70, color[2] * 0.46))

    # --- peel mask: big blotches, hard edged, biased to the edges ------------
    edge = _ramp(nt, geo.outputs['Pointiness'], [(0.487, 0.0), (0.565, 1.0)])
    blob = _ramp(nt, _noise(nt, co, 6.0, 8.0, 0.75, distortion=2.2), [(0.50, 0.0), (0.565, 1.0)])
    blob2 = _ramp(nt, _noise(nt, co, 16.0, 6.0, 0.7, distortion=1.4), [(0.52, 0.0), (0.60, 1.0)])
    peelmask = _math(nt, 'MAXIMUM', blob, _math(nt, 'MULTIPLY', blob2, 0.85))
    peelmask = _math(nt, 'MULTIPLY', peelmask, peel, clamp=True)
    peelmask = _math(nt, 'MAXIMUM', peelmask, _math(nt, 'MULTIPLY', edge, chip), clamp=True)

    base = _mix(nt, peelmask, paint, woodcol)
    rough_out = _math(nt, 'ADD', rough, _math(nt, 'MULTIPLY', peelmask, 0.34))
    rough_out = _math(nt, 'ADD', rough_out, _math(nt, 'MULTIPLY', _noise(nt, co, 9.0, 4.0, 0.6), 0.1))

    # grime in the mouldings
    ao = nt.nodes.new('ShaderNodeAmbientOcclusion')
    ao.samples = 8; ao.inside = True; ao.only_local = True
    ao.inputs['Distance'].default_value = 0.07
    cav = _ramp(nt, ao.outputs['AO'], [(0.02, 0.0), (0.45, 1.0)])
    cav = _math(nt, 'MULTIPLY', cav, grime, clamp=True)
    base = _mix(nt, cav, base, (0.040, 0.034, 0.028))
    rough_out = _math(nt, 'ADD', _math(nt, 'MULTIPLY', rough_out, _math(nt, 'SUBTRACT', 1.0, cav)),
                      _math(nt, 'MULTIPLY', cav, 0.9))

    if dust > 0:
        nsep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(geo.outputs['Normal'], nsep.inputs[0])
        up = _ramp(nt, nsep.outputs['Z'], [(0.3, 0.0), (0.9, 1.0)])
        dm = _math(nt, 'MULTIPLY', up, dust, clamp=True)
        base = _mix(nt, dm, base, (0.42, 0.38, 0.31))

    nt.links.new(base, bsdf.inputs['Base Color'])
    nt.links.new(rough_out, bsdf.inputs['Roughness'])
    bsdf.inputs['Metallic'].default_value = 0.0

    # paint sits proud of the bare patches
    h = _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', 1.0, peelmask), 0.6)
    h = _math(nt, 'ADD', h, _math(nt, 'MULTIPLY', grain, 0.25))
    h = _math(nt, 'ADD', h, _math(nt, 'MULTIPLY', _noise(nt, co, 70.0, 4.0, 0.6), 0.12))
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = 1.0
    bp.inputs['Distance'].default_value = 0.004
    nt.links.new(h, bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def glass_mat(name, color=(0.75, 0.8, 0.78), rough=0.06, alpha=0.35):
    mat = pbr_material(name, color, rough, 0.0)
    b = mat.node_tree.nodes['Principled BSDF']
    b.inputs['Alpha'].default_value = alpha
    b.inputs['IOR'].default_value = 1.45
    mat.blend_method = 'BLEND' if hasattr(mat, 'blend_method') else mat.blend_method
    return mat


# --------------------------------------------------------------------------------------
# baking
# --------------------------------------------------------------------------------------

def _all_materials(objs):
    mats = []
    for o in objs:
        for s in o.material_slots:
            if s.material and s.material not in mats:
                mats.append(s.material)
    return mats


def _find_output(nt):
    for n in nt.nodes:
        if n.type == 'OUTPUT_MATERIAL' and n.is_active_output:
            return n
    for n in nt.nodes:
        if n.type == 'OUTPUT_MATERIAL':
            return n
    return None


def _set_bake_target(mats, img):
    keep = []
    for m in mats:
        nt = m.node_tree
        tn = nt.nodes.new('ShaderNodeTexImage')
        tn.image = img
        for n in nt.nodes:
            n.select = False
        tn.select = True
        nt.nodes.active = tn
        keep.append((m, tn))
    return keep


def _clear_bake_target(keep):
    for m, tn in keep:
        m.node_tree.nodes.remove(tn)


def _channel_bake(objs, mats, img, channel, samples=4):
    """Bake a Principled input (Base Color / Roughness / Metallic) via an emission rewire."""
    tmp = []
    for m in mats:
        nt = m.node_tree
        out = _find_output(nt)
        bsdf = None
        for n in nt.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                bsdf = n
                break
        if out is None:
            continue
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Strength'].default_value = 1.0
        if bsdf is not None and channel in bsdf.inputs:
            sock = bsdf.inputs[channel]
            if sock.is_linked:
                nt.links.new(sock.links[0].from_socket, em.inputs['Color'])
            else:
                v = sock.default_value
                if hasattr(v, '__len__'):
                    em.inputs['Color'].default_value = (v[0], v[1], v[2], 1)
                else:
                    em.inputs['Color'].default_value = (v, v, v, 1)
        prev = out.inputs['Surface'].links[0].from_socket if out.inputs['Surface'].is_linked else None
        nt.links.new(em.outputs[0], out.inputs['Surface'])
        tmp.append((m, em, out, prev))
    _bake(objs, 'EMIT', samples)
    for m, em, out, prev in tmp:
        nt = m.node_tree
        nt.nodes.remove(em)
        if prev is not None:
            nt.links.new(prev, out.inputs['Surface'])


def _bake(objs, btype, samples):
    scn = bpy.context.scene
    scn.cycles.samples = samples
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    kw = {'type': btype, 'use_clear': True, 'margin': 12}
    if btype == 'NORMAL':
        scn.render.bake.normal_space = 'TANGENT'
    bpy.ops.object.bake(**kw)


def unwrap(objs, angle=66, margin=0.0035):
    for o in objs:
        if not o.data.uv_layers:
            o.data.uv_layers.new(name='UVMap')
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.reveal()
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=D2R(angle), island_margin=margin,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def bake_pbr(objs, name, size=1024, samples=4, normal_samples=8, angle=66, margin=0.0035,
             emissive=False, emission_strength=1.0, mat_name=None, do_unwrap=True,
             alpha=1.0):
    """UV unwrap `objs` together, bake their procedural materials into base/ORM/normal
    images and replace every material with one glTF-safe Principled material.

    Returns the new material."""
    import numpy as np
    objs = [o for o in objs if o.type == 'MESH' and len(o.data.polygons)]
    if not objs:
        return None
    scn = _setup_device(samples)
    if BAKE_ON_CPU:
        scn.cycles.device = 'CPU'
    # channel bakes are noise-free; denoising would drag in an OptiX/CUDA context
    scn.cycles.use_denoising = False
    scn.render.bake.use_selected_to_active = False
    apply_mods(objs)
    if do_unwrap:
        unwrap(objs, angle, margin)

    fallback = None
    for o in objs:
        if not o.data.materials or all(s.material is None for s in o.material_slots):
            if fallback is None:
                fallback = weathered(f'{name}_fallback', color=(0.5, 0.5, 0.5))
            print('  WARNING: no material on', o.name, '- using fallback')
            o.data.materials.clear()
            o.data.materials.append(fallback)
    mats = _all_materials(objs)
    if not mats:
        return None

    imgs = {}
    for key, colorspace, is_float in (('base', 'sRGB', False), ('rough', 'Non-Color', False),
                                      ('metal', 'Non-Color', False), ('normal', 'Non-Color', True)):
        im = bpy.data.images.new(f'{name}_{key}', size, size, float_buffer=is_float, alpha=False)
        im.colorspace_settings.name = colorspace
        if key == 'normal':
            im.generated_color = (0.5, 0.5, 1.0, 1.0)
        imgs[key] = im

    for key, channel in (('base', 'Base Color'), ('rough', 'Roughness'), ('metal', 'Metallic')):
        keep = _set_bake_target(mats, imgs[key])
        _channel_bake(objs, mats, imgs[key], channel, samples)
        _clear_bake_target(keep)

    keep = _set_bake_target(mats, imgs['normal'])
    _bake(objs, 'NORMAL', normal_samples)
    _clear_bake_target(keep)

    # compose ORM (R = AO(1), G = roughness, B = metallic)
    n = size * size * 4
    r = np.empty(n, dtype=np.float32); imgs['rough'].pixels.foreach_get(r)
    m = np.empty(n, dtype=np.float32); imgs['metal'].pixels.foreach_get(m)
    orm = np.ones(n, dtype=np.float32)
    orm[1::4] = np.clip(r[0::4], 0.0, 1.0)
    orm[2::4] = np.clip(m[0::4], 0.0, 1.0)
    orm[3::4] = 1.0
    oi = bpy.data.images.new(f'{name}_orm', size, size, float_buffer=False, alpha=False)
    oi.colorspace_settings.name = 'Non-Color'
    oi.pixels.foreach_set(orm)
    oi.update()

    paths = {}
    for key, im in (('base', imgs['base']), ('orm', oi), ('normal', imgs['normal'])):
        p = os.path.join(PROPS_TEX, f'{name}_{key}.png')
        im.filepath_raw = p
        im.file_format = 'PNG'
        im.save()
        paths[key] = p
    bpy.data.images.remove(imgs['rough'])
    bpy.data.images.remove(imgs['metal'])

    # final material
    mn = mat_name or (f'{name}_glow' if emissive else f'{name}_mat')
    mat = bpy.data.materials.new(mn)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    tb = nt.nodes.new('ShaderNodeTexImage'); tb.image = imgs['base']
    tb.location = (-600, 300)
    nt.links.new(tb.outputs['Color'], bsdf.inputs['Base Color'])
    to = nt.nodes.new('ShaderNodeTexImage'); to.image = oi; to.location = (-600, 0)
    sc = nt.nodes.new('ShaderNodeSeparateColor'); sc.location = (-350, 0)
    nt.links.new(to.outputs['Color'], sc.inputs['Color'])
    nt.links.new(sc.outputs['Green'], bsdf.inputs['Roughness'])
    nt.links.new(sc.outputs['Blue'], bsdf.inputs['Metallic'])
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = imgs['normal']; tn.location = (-600, -320)
    nm = nt.nodes.new('ShaderNodeNormalMap'); nm.location = (-350, -320)
    nt.links.new(tn.outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    if emissive:
        nt.links.new(tb.outputs['Color'], bsdf.inputs['Emission Color'])
        bsdf.inputs['Emission Strength'].default_value = emission_strength
    if alpha < 1.0:
        bsdf.inputs['Alpha'].default_value = alpha

    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(mat)
        for p in o.data.polygons:
            p.material_index = 0
    print(f'  baked {name}: {len(objs)} objects, {size}px')
    return mat


def strip_color_attrs(objs=None):
    objs = objs or [o for o in bpy.context.scene.objects if o.type == 'MESH']
    for o in objs:
        me = o.data
        for attr in list(getattr(me, 'color_attributes', [])):
            me.color_attributes.remove(attr)


# --------------------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------------------

def export_prop(filename, roots=None, webp=True, quality=80):
    drop_texref()
    strip_color_attrs()
    path = os.path.join(PROPS_DIR, filename)
    kwargs = dict(filepath=path, export_format='GLB', export_yup=True, export_apply=True,
                  export_extras=True, export_animations=False,
                  export_image_format='WEBP' if webp else 'AUTO')
    if webp:
        kwargs['export_image_quality'] = quality
    if roots is not None:
        bpy.ops.object.select_all(action='DESELECT')
        def sel(o):
            o.select_set(True)
            for c in o.children:
                sel(c)
        for o in roots:
            sel(o)
        kwargs['use_selection'] = True
    bpy.ops.export_scene.gltf(**kwargs)
    kb = os.path.getsize(path) // 1024
    print('EXPORTED', path, kb, 'KB', '| tris', tri_count())
    return path


def _render_safe(**kw):
    """preview_render, falling back to the CPU when the shared GPU is out of memory."""
    global FORCE_CPU
    try:
        return preview_render(**kw)
    except Exception as e:
        print('  GPU render failed (%s) - retrying on CPU' % e)
        FORCE_CPU = True
        return preview_render(**kw)


def shots(stem, target=(0, 0, 1.0), hero=(4.0, 35, 12), close=(1.2, 60, 5), samples=40,
          res=(1100, 700), world=0.7, lens=50, ground=True, close_target=None):
    """Hero 3/4 render + a detail close-up."""
    a = _render_safe(path=os.path.join(PROPS_RENDERS, f'{stem}_hero.png'), target=target,
                     distance=hero[0], yaw_deg=hero[1], pitch_deg=hero[2], res=res,
                     samples=samples, world_strength=world, lens=lens, ground=ground)
    b = _render_safe(path=os.path.join(PROPS_RENDERS, f'{stem}_close.png'),
                     target=close_target or target,
                     distance=close[0], yaw_deg=close[1], pitch_deg=close[2], res=res,
                     samples=samples, world_strength=world, lens=lens, ground=ground)
    return a, b


# public aliases (``from lib_props import *`` skips leading-underscore names)
finish = _finish
mix_rgb = _mix
mathn = _math
ramp = _ramp
noise_tex = _noise
coords = _coords
node = _nd
