"""Character authoring helpers (Blender 5.2, headless).

Owned by the character agent. `common.py` is shared and must not be edited, so everything
character specific lives here: lofted organic geometry, blob sculpting, voxel remesh + UV bake,
armature construction with exact contract bone names, and a matrix based posing/IK system used
to keyframe the animation clips.

Conventions (contract): metres, Z up in Blender, character faces -Y, +X is the character's LEFT.
"""
import bpy, bmesh, math, os, random
from mathutils import Vector, Matrix, Euler, Quaternion

TAU = math.pi * 2.0


# --------------------------------------------------------------------------------------
# geometry primitives
# --------------------------------------------------------------------------------------

def _ortho(y):
    """A stable pair of axes perpendicular to y."""
    y = Vector(y).normalized()
    ref = Vector((0, -1, 0))
    if abs(y.dot(ref)) > 0.95:
        ref = Vector((0, 0, 1))
    z = (ref - y * ref.dot(y)).normalized()
    x = y.cross(z)
    return x, z


def ring(center, rx, rz, n=16, y=(0, 0, 1), xaxis=None, zaxis=None, shape=None, phase=0.0):
    """A closed elliptical ring of n points around `center` in the plane perpendicular to `y`.

    shape(angle) -> (sx, sz) multiplier lets a cross-section be squashed / pear shaped.
    """
    c = Vector(center)
    if xaxis is None or zaxis is None:
        xaxis, zaxis = _ortho(y)
    xaxis = Vector(xaxis).normalized()
    zaxis = Vector(zaxis).normalized()
    pts = []
    for i in range(n):
        a = TAU * i / n + phase
        sx, sz = (1.0, 1.0) if shape is None else shape(a)
        pts.append(c + xaxis * (math.cos(a) * rx * sx) + zaxis * (math.sin(a) * rz * sz))
    return pts


def loft(name, rings, cap_start=True, cap_end=True, collection=None):
    """Build a quad tube through a list of equal-length point rings."""
    bm = bmesh.new()
    vrings = [[bm.verts.new(p) for p in r] for r in rings]
    n = len(rings[0])
    for a, b in zip(vrings, vrings[1:]):
        for i in range(n):
            j = (i + 1) % n
            try:
                bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError:
                pass
    if cap_start:
        try:
            bm.faces.new(list(reversed(vrings[0])))
        except ValueError:
            pass
    if cap_end:
        try:
            bm.faces.new(vrings[-1])
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


def tube(name, path, radii, n=16, shape=None, cap_start=True, cap_end=True,
         up_hint=(0, -1, 0), collection=None):
    """Loft along a polyline. radii = list of (rx, rz) per station, in the frame where
    x = side axis, z = up_hint-ish axis, both perpendicular to the local path direction."""
    path = [Vector(p) for p in path]
    rings = []
    prev_x = None
    for i, p in enumerate(path):
        if i == 0:
            d = path[1] - path[0]
        elif i == len(path) - 1:
            d = path[-1] - path[-2]
        else:
            d = path[i + 1] - path[i - 1]
        d.normalize()
        hint = Vector(up_hint)
        if abs(d.dot(hint)) > 0.95:
            hint = Vector((1, 0, 0))
        xa = hint.cross(d).normalized()
        if prev_x is not None and xa.dot(prev_x) < 0:
            xa = -xa
        prev_x = xa
        za = d.cross(xa).normalized()
        rx, rz = radii[i]
        rings.append(ring(p, rx, rz, n, y=d, xaxis=xa, zaxis=za, shape=shape))
    return loft(name, rings, cap_start, cap_end, collection)


def uv_sphere(name, center, radii, seg=24, rings_n=16, collection=None):
    """Ellipsoid built as a UV sphere (poles on Z)."""
    rx, ry, rz = radii
    c = Vector(center)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings_n, radius=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * rx, v.co.y * ry, v.co.z * rz)) + c
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


def icosphere(name, center, radius, subdiv=3, collection=None):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    for v in bm.verts:
        v.co += Vector(center)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


# --------------------------------------------------------------------------------------
# blob sculpting: gaussian falloff displacement, used to carve faces / anatomy
# --------------------------------------------------------------------------------------

def blob(ob, center, radius, amount, direction=None, falloff='smooth', ellipse=(1, 1, 1),
         only=None):
    """Push vertices near `center` by `amount` along `direction` (default: radial from center).

    ellipse scales the distance metric per axis, so a blob can be a ridge or a slab.
    only(v_world) -> bool filters which verts are affected.
    """
    c = Vector(center)
    e = Vector(ellipse)
    d = Vector(direction).normalized() if direction is not None else None
    for v in ob.data.vertices:
        p = v.co
        rel = Vector(((p.x - c.x) / e.x, (p.y - c.y) / e.y, (p.z - c.z) / e.z))
        t = rel.length / radius
        if t >= 1.0:
            continue
        if only is not None and not only(p):
            continue
        if falloff == 'smooth':
            w = 1.0 - t * t
            w = w * w * w
        elif falloff == 'linear':
            w = 1.0 - t
        else:
            w = math.cos(t * math.pi * 0.5)
        dirv = d if d is not None else ((p - c).normalized() if (p - c).length > 1e-6 else Vector((0, 0, 1)))
        v.co = p + dirv * (amount * w)


def scale_region(ob, center, radius, factor, ellipse=(1, 1, 1), axis_mask=(1, 1, 1)):
    """Scale vertices near center toward/away from the center axis, gaussian weighted."""
    c = Vector(center)
    e = Vector(ellipse)
    m = Vector(axis_mask)
    for v in ob.data.vertices:
        p = v.co
        rel = Vector(((p.x - c.x) / e.x, (p.y - c.y) / e.y, (p.z - c.z) / e.z))
        t = rel.length / radius
        if t >= 1.0:
            continue
        w = (1.0 - t * t) ** 2
        s = 1.0 + (factor - 1.0) * w
        off = p - c
        v.co = c + Vector((off.x * (1 + (s - 1) * m.x), off.y * (1 + (s - 1) * m.y),
                           off.z * (1 + (s - 1) * m.z)))


def noise_displace(ob, scale=40.0, amount=0.004, seed=0, mask=None):
    rnd = random.Random(seed)
    ox, oy, oz = rnd.random() * 100, rnd.random() * 100, rnd.random() * 100
    from mathutils import noise as bnoise
    for v in ob.data.vertices:
        p = v.co
        n = bnoise.noise(Vector((p.x * scale + ox, p.y * scale + oy, p.z * scale + oz)))
        a = amount if mask is None else amount * mask(p)
        v.co = p + v.normal * (n * a)


# --------------------------------------------------------------------------------------
# object utilities
# --------------------------------------------------------------------------------------

def activate(ob):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    return ob


def join(objs, name):
    base = objs[0]
    activate(base)
    for o in objs[1:]:
        o.select_set(True)
    bpy.ops.object.join()
    base.name = name
    base.data.name = name
    return base


def duplicate(ob, name):
    new = ob.copy()
    new.data = ob.data.copy()
    new.name = name
    new.data.name = name
    bpy.context.scene.collection.objects.link(new)
    return new


def voxel_remesh(ob, voxel=0.012, adaptivity=0.0, smooth=True):
    activate(ob)
    ob.data.remesh_voxel_size = voxel
    ob.data.remesh_voxel_adaptivity = adaptivity
    bpy.ops.object.voxel_remesh()
    if smooth:
        bpy.ops.object.modifier_add(type='SMOOTH')
        ob.modifiers[-1].factor = 0.6
        ob.modifiers[-1].iterations = 3
        bpy.ops.object.modifier_apply(modifier=ob.modifiers[-1].name)
    return ob


def decimate(ob, ratio):
    if ratio >= 1.0:
        return ob
    activate(ob)
    m = ob.modifiers.new('Dec', 'DECIMATE')
    m.decimate_type = 'COLLAPSE'
    m.ratio = ratio
    bpy.ops.object.modifier_apply(modifier=m.name)
    return ob


def triangle_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def smart_uv(ob, angle=66.0, margin=0.02):
    activate(ob)
    if not ob.data.uv_layers:
        ob.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    return ob


def shade_smooth_ob(ob, angle=50):
    activate(ob)
    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(angle))
    except Exception:
        for p in ob.data.polygons:
            p.use_smooth = True


def clear_colors(ob):
    while ob.data.color_attributes:
        ob.data.color_attributes.remove(ob.data.color_attributes[0])


# --------------------------------------------------------------------------------------
# baking a procedural material to this object's UVs
# --------------------------------------------------------------------------------------

def uv_signature(ob):
    """Short hash of the mesh + UV layout, so a cached bake is never reused on new geometry."""
    import zlib, struct
    me = ob.data
    h = zlib.crc32(struct.pack('<ii', len(me.vertices), len(me.polygons)))
    if me.uv_layers.active:
        data = me.uv_layers.active.data
        step = max(1, len(data) // 400)
        buf = b''.join(struct.pack('<HH', int(data[i].uv[0] * 4096) & 0xffff,
                                   int(data[i].uv[1] * 4096) & 0xffff)
                       for i in range(0, len(data), step))
        h = zlib.crc32(buf, h)
    vstep = max(1, len(me.vertices) // 300)
    co = b''.join(struct.pack('<HHH', int(me.vertices[i].co.x * 2048) & 0xffff,
                              int(me.vertices[i].co.y * 2048) & 0xffff,
                              int(me.vertices[i].co.z * 2048) & 0xffff)
                  for i in range(0, len(me.vertices), vstep))
    h = zlib.crc32(co, h)
    return '%08x' % h


def bake_object_material(ob, build_fn, name, size=1024, samples=8, cache_dir=None,
                         passes=('DIFFUSE', 'ROUGHNESS', 'NORMAL'), force=False):
    """Build a procedural material with build_fn(mat, ob), bake it to `ob`'s UVs, and
    return a dict pass -> image filepath (PNG in cache_dir)."""
    from common import TEX_CACHE, setup_gpu
    cache_dir = cache_dir or TEX_CACHE
    name = '%s_%s' % (name, uv_signature(ob))
    out = {p: os.path.join(cache_dir, f'{name}_{p.lower()}.png') for p in passes}
    if not force and all(os.path.exists(p) for p in out.values()):
        return out
    scn = setup_gpu(samples)
    scn.render.bake.margin = 8
    mat = bpy.data.materials.new('_bake_' + name)
    mat.use_nodes = True
    build_fn(mat, ob)
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    nt = mat.node_tree
    for p in passes:
        img = bpy.data.images.new(f'{name}_{p}', size, size, float_buffer=(p == 'NORMAL'),
                                  alpha=False)
        if p not in ('DIFFUSE', 'EMIT'):
            img.colorspace_settings.name = 'Non-Color'
        tn = nt.nodes.new('ShaderNodeTexImage')
        tn.image = img
        for n in nt.nodes:
            n.select = False
        tn.select = True
        nt.nodes.active = tn
        activate(ob)
        if p == 'DIFFUSE':
            scn.render.bake.use_pass_direct = False
            scn.render.bake.use_pass_indirect = False
            scn.render.bake.use_pass_color = True
        if p == 'NORMAL':
            scn.render.bake.normal_space = 'TANGENT'
        bpy.ops.object.bake(type=p, use_clear=True)
        img.filepath_raw = out[p]
        img.file_format = 'PNG'
        img.save()
        nt.nodes.remove(tn)
        bpy.data.images.remove(img)
    ob.data.materials.clear()
    bpy.data.materials.remove(mat)
    return out


def baked_material(name, tex, roughness=0.75, normal_strength=1.0, emit_strength=0.0):
    from common import pbr_material
    mat = pbr_material(name, base_tex=tex.get('DIFFUSE'), rough_tex=tex.get('ROUGHNESS'),
                       normal_tex=tex.get('NORMAL'), roughness=roughness,
                       normal_strength=normal_strength)
    if tex.get('EMIT') and emit_strength > 0:
        nt = mat.node_tree
        bsdf = nt.nodes.get('Principled BSDF')
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(tex['EMIT'], check_existing=True)
        nt.links.new(t.outputs['Color'], bsdf.inputs['Emission Color'])
        bsdf.inputs['Emission Strength'].default_value = emit_strength
    return mat


# --------------------------------------------------------------------------------------
# armature
# --------------------------------------------------------------------------------------

class Rig:
    """Armature built from an explicit bone table, plus a matrix based poser.

    Bone spec: name -> (parent, head, tail, roll_ref)
    roll_ref is a world vector the bone's local +Z is aligned to (align_roll).
    Poses are authored as armature-space matrices; basis matrices are derived analytically,
    so no depsgraph updates are needed while keyframing.
    """

    def __init__(self, name, bones, collection=None):
        arm = bpy.data.armatures.new(name)
        ob = bpy.data.objects.new(name, arm)
        (collection or bpy.context.scene.collection).objects.link(ob)
        self.ob = ob
        self.spec = bones
        self.parent = {n: b[0] for n, b in bones.items()}
        self.head = {n: Vector(b[1]) for n, b in bones.items()}
        self.tail = {n: Vector(b[2]) for n, b in bones.items()}
        self.ref = {n: Vector(b[3]).normalized() for n, b in bones.items()}
        activate(ob)
        bpy.ops.object.mode_set(mode='EDIT')
        eb = {}
        for n, (p, h, t, r) in bones.items():
            b = arm.edit_bones.new(n)
            b.head = Vector(h)
            b.tail = Vector(t)
            eb[n] = b
        for n, (p, h, t, r) in bones.items():
            if p:
                eb[n].parent = eb[p]
                eb[n].use_connect = (Vector(h) - Vector(bones[p][2])).length < 1e-5
            eb[n].align_roll(Vector(r))
        bpy.ops.object.mode_set(mode='OBJECT')
        # cache rest matrices (armature space)
        self.rest = {n: ob.data.bones[n].matrix_local.copy() for n in bones}
        self.length = {n: (self.tail[n] - self.head[n]).length for n in bones}
        self.order = self._hierarchy_order()
        ob.rotation_mode = 'QUATERNION'
        for pb in ob.pose.bones:
            pb.rotation_mode = 'QUATERNION'
        self.basis = {}
        self._world = {}

    def _hierarchy_order(self):
        out, seen = [], set()

        def visit(n):
            if n in seen:
                return
            p = self.parent[n]
            if p:
                visit(p)
            seen.add(n)
            out.append(n)
        for n in self.spec:
            visit(n)
        return out

    # ---- posing -----------------------------------------------------------------
    def reset(self):
        self.basis = {n: Matrix.Identity(4) for n in self.spec}
        self._world = {}

    def set_basis(self, name, mat):
        self.basis[name] = mat.copy()
        self._world.clear()

    def set_euler(self, name, pitch=0.0, twist=0.0, bend=0.0, loc=None):
        """Local rotation in bone axes: X=pitch(+ = toward the bone's +Z ref), Y=twist, Z=bend."""
        m = Euler((pitch, twist, bend), 'XYZ').to_matrix().to_4x4()
        if loc is not None:
            m = Matrix.Translation(Vector(loc)) @ m
        self.set_basis(name, m)

    def world(self, name):
        """Armature-space matrix of a bone under the current basis set."""
        if name in self._world:
            return self._world[name]
        p = self.parent[name]
        basis = self.basis.get(name, Matrix.Identity(4))
        if p:
            m = self.world(p) @ (self.rest[p].inverted() @ self.rest[name]) @ basis
        else:
            m = self.rest[name] @ basis
        self._world[name] = m
        return m

    def set_world(self, name, mat):
        """Set a bone's armature-space matrix directly (converted to a basis matrix)."""
        p = self.parent[name]
        if p:
            rel = self.rest[p].inverted() @ self.rest[name]
            basis = (self.world(p) @ rel).inverted() @ mat
        else:
            basis = self.rest[name].inverted() @ mat
        self.set_basis(name, basis)

    def bone_head(self, name):
        return self.world(name).translation.copy()

    def bone_tail(self, name):
        w = self.world(name)
        return w.translation + w.col[1].to_3d().normalized() * self.length[name]

    @staticmethod
    def aim_matrix(origin, ydir, ref):
        y = Vector(ydir).normalized()
        r = Vector(ref)
        z = r - y * r.dot(y)
        if z.length < 1e-6:
            z = Vector((0, 0, 1)) - y * y.z
            if z.length < 1e-6:
                z = Vector((0, -1, 0))
        z.normalize()
        x = y.cross(z)
        m = Matrix((
            (x.x, y.x, z.x, origin.x),
            (x.y, y.y, z.y, origin.y),
            (x.z, y.z, z.z, origin.z),
            (0, 0, 0, 1)))
        return m

    def aim(self, name, ydir, ref=None):
        ref = self.ref[name] if ref is None else Vector(ref)
        self.set_world(name, self.aim_matrix(self.bone_head(name), ydir, ref))

    def two_bone_ik(self, b1, b2, target, pole, ref1=None, ref2=None):
        """Analytic IK: aims b1/b2 so that b2's tail lands on `target`.
        `pole` is the direction the joint (knee/elbow) bulges toward."""
        h = self.bone_head(b1)
        l1, l2 = self.length[b1], self.length[b2]
        d = Vector(target) - h
        dist = d.length
        if dist < 1e-5:
            d = Vector((0, 0, -1)); dist = 1e-5
        dist = max(min(dist, (l1 + l2) * 0.999), abs(l1 - l2) + 1e-4)
        n = d.normalized()
        a = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
        hgt = math.sqrt(max(l1 * l1 - a * a, 0.0))
        p = Vector(pole)
        p = p - n * p.dot(n)
        if p.length < 1e-6:
            p = Vector((0, -1, 0))
            p = p - n * p.dot(n)
        p.normalize()
        knee = h + n * a + p * hgt
        self.aim(b1, knee - h, ref1)
        self.aim(b2, (Vector(target) - knee), ref2)
        return knee

    # ---- keyframing --------------------------------------------------------------
    def apply_to_pose(self):
        for n in self.order:
            pb = self.ob.pose.bones[n]
            pb.matrix_basis = self.basis.get(n, Matrix.Identity(4))

    def key(self, frame, bones=None):
        self.apply_to_pose()
        for n in (bones or self.order):
            pb = self.ob.pose.bones[n]
            pb.keyframe_insert('location', frame=frame)
            pb.keyframe_insert('rotation_quaternion', frame=frame)


def new_action(rig, name):
    ob = rig.ob
    if ob.animation_data is None:
        ob.animation_data_create()
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    ob.animation_data.action = act
    try:  # Blender 4.4+ slotted actions
        slot = act.slots.new(id_type='OBJECT', name=name)
        ob.animation_data.action_slot = slot
    except Exception:
        pass
    return act


def action_fcurves(act):
    """Blender 4.4+ slotted actions: walk layers -> strips -> channelbags."""
    if hasattr(act, 'fcurves'):
        return list(act.fcurves)
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for cb in getattr(strip, 'channelbags', []):
                out.extend(cb.fcurves)
    return out


def finish_action(act, frame_end, interpolation='BEZIER'):
    for fc in action_fcurves(act):
        for kp in fc.keyframe_points:
            kp.interpolation = interpolation
            kp.handle_left_type = 'AUTO_CLAMPED'
            kp.handle_right_type = 'AUTO_CLAMPED'
    try:
        act.use_frame_range = True
        act.frame_start = 0.0
        act.frame_end = float(frame_end)
    except Exception:
        pass
    return act


def export_character(path, animations=True, image_format='WEBP', quality=82):
    kwargs = dict(filepath=path, export_format='GLB', export_yup=True, export_apply=True,
                  export_extras=False, export_animations=animations,
                  export_animation_mode='ACTIONS',
                  export_bake_animation=False,
                  export_optimize_animation_size=False,
                  export_force_sampling=True,
                  export_image_format=image_format, export_image_quality=quality,
                  export_def_bones=False, export_anim_single_armature=True,
                  export_nla_strips=False)
    bpy.ops.export_scene.gltf(**kwargs)
    print('EXPORTED', path, os.path.getsize(path) // 1024, 'KB')
    return path


def box_like(name, size, loc, collection=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    ob.location = loc
    activate(ob)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return ob


def inside(ob, p, margin=0.0):
    """True when point p is at least `margin` inside the closed mesh `ob`."""
    ok, loc, nrm, _ = ob.closest_point_on_mesh(p)
    if not ok:
        return False
    d = p - loc
    return d.dot(nrm) < 0.0 and d.length > margin


def covered_by(ob, p, face_normal, margin=0.012, max_gap=0.075, align=0.30):
    """True when p sits under `ob` *along its own surface normal*.

    A plain inside test is not enough: the flat end cap of a sleeve makes the bare
    forearm just past the hem test as "inside", which punched holes in visible skin.
    """
    ok, loc, nrm, _ = ob.closest_point_on_mesh(p)
    if not ok:
        return False
    d = p - loc
    if d.dot(nrm) >= 0.0:
        return False
    dist = d.length
    if dist < margin or dist > max_gap:
        return False
    return face_normal.dot((loc - p).normalized()) > align


def remove_covered(body, covers, margin=0.020, protect=None):
    """Delete body faces buried inside the clothing volumes (saves triangles, no clipping).

    `protect(center) -> bool` keeps a face even when it tests as covered; used so the
    exposed-wound geometry survives under a garment that has been torn open over it.
    """
    import bmesh as _bm
    keep = []
    for i, poly in enumerate(body.data.polygons):
        c = poly.center
        n = poly.normal
        if protect is not None and protect(c):
            continue
        if any(covered_by(cv, c, n, margin) for cv in covers):
            keep.append(i)
    if not keep:
        return 0
    bm = _bm.new()
    bm.from_mesh(body.data)
    bm.faces.ensure_lookup_table()
    doomed = [bm.faces[i] for i in keep]
    _bm.ops.delete(bm, geom=doomed, context='FACES')
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    clean_loose(body)
    return len(keep)


def solidify(ob, thickness=0.005, offset=-1.0, rim=True):
    """Give an open cloth shell real thickness, so a hem shows an edge and a tear shows
    a wall instead of a zero-thickness cut."""
    activate(ob)
    m = ob.modifiers.new('Sld', 'SOLIDIFY')
    m.thickness = thickness
    m.offset = offset
    m.use_rim = rim
    m.use_rim_only = False
    m.use_even_offset = True
    try:
        m.nonmanifold_thickness_mode = 'CONSTRAINTS'
        m.solidify_mode = 'NON_MANIFOLD'
    except Exception:
        pass
    bpy.ops.object.modifier_apply(modifier=m.name)
    return ob


def delete_region(ob, centre, radius, ellipse=(1, 1, 1), jitter=0.0, seed=0):
    """Punch a hole through a mesh: delete every face whose centre is inside the
    ellipsoid.  `jitter` wobbles the radius per face so the rim is ragged."""
    import bmesh as _bm
    c = Vector(centre)
    e = Vector(ellipse)
    rnd = random.Random(seed)
    bm = _bm.new()
    bm.from_mesh(ob.data)
    doomed = []
    for f in bm.faces:
        p = f.calc_center_median()
        rel = Vector(((p.x - c.x) / e.x, (p.y - c.y) / e.y, (p.z - c.z) / e.z))
        r = radius * (1.0 + jitter * (rnd.random() - 0.5) * 2.0)
        if rel.length < r:
            doomed.append(f)
    if doomed:
        _bm.ops.delete(bm, geom=doomed, context='FACES')
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            _bm.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(doomed)


def decimate_to(ob, target):
    """Collapse-decimate `ob` down to (at most) `target` triangles.  No-op if already under."""
    cur = triangle_count(ob)
    if cur <= target or cur == 0:
        return cur
    decimate(ob, max(0.05, float(target) / float(cur)))
    return triangle_count(ob)


def _frame(axis):
    a = Vector(axis).normalized()
    ref = Vector((0, 0, 1))
    if abs(a.dot(ref)) > 0.92:
        ref = Vector((0, -1, 0))
    u = (ref - a * ref.dot(a)).normalized()
    v = a.cross(u)
    return a, u, v


def punch_hole(ob, centre, axis, radius, jag=0.30, seed=0, depth=0.18, flap=0.0028):
    """Tear a hole through a garment shell along `axis`, following a ragged *ellipse*.

    `delete_region` alone cuts on quad boundaries, so on a lofted garment the result is an
    axis-aligned stair-stepped rectangle - which is exactly what review #6 complained
    about.  Here the faces that straddle the contour are removed and the surviving rim
    vertices are then *snapped onto* the contour (tangentially, so the shell is not pulled
    onto the body), which makes the cut follow the curve at any tessellation.  The rim is
    finally flicked outward a couple of millimetres so the torn edge lifts off the skin and
    catches light instead of reading as a printed decal.

    The cut is a swept *tube* around `axis`, not an ellipsoid: the wound centre is on the
    skin and the garment sits several centimetres further out, so a ball centred on the
    wound had to be stretched absurdly in Y to reach the cloth at all.
    """
    import bmesh as _bm
    rnd = random.Random(seed)
    c = Vector(centre)
    ax, ux, vx = _frame(axis)
    ph = [rnd.uniform(0, TAU) for _ in range(3)]

    def r_at(a):
        wob = (0.55 * math.sin(3 * a + ph[0]) + 0.30 * math.sin(5 * a + ph[1]) +
               0.15 * math.sin(8 * a + ph[2]))
        return radius * (1.0 + jag * wob)

    def polar(p):
        rel = p - c
        al = rel.dot(ax)
        per = rel - ax * al
        return al, per, math.atan2(per.dot(vx), per.dot(ux))

    bm = _bm.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    inside = set()
    for v in bm.verts:
        al, per, a = polar(v.co)
        if abs(al) < depth and per.length < r_at(a):
            inside.add(v)
    if not inside:
        bm.free()
        return 0
    doomed = [f for f in bm.faces if any(v in inside for v in f.verts)]
    if not doomed:
        bm.free()
        return 0
    touched = set()
    for f in doomed:
        touched.update(f.verts)
    _bm.ops.delete(bm, geom=doomed, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        _bm.ops.delete(bm, geom=loose, context='VERTS')
    bm.normal_update()
    survivors = [v for v in touched if v.is_valid and v.link_faces]
    for v in survivors:
        if not any(len(e.link_faces) == 1 for e in v.link_edges):
            continue
        al, per, a = polar(v.co)
        if abs(al) > depth or per.length < 1e-5:
            continue
        want = r_at(a)
        v.co += per.normalized() * (want - per.length)
        if flap:
            n = v.normal.copy()
            if n.length > 1e-6:
                v.co += n.normalized() * (flap * rnd.uniform(0.35, 1.0))
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(doomed)


def ragged_boundary(ob, amount=0.010, along=None, seed=0, zmax=None):
    """Displace boundary (open-edge) vertices so a hem or a tear breaks the silhouette."""
    import bmesh as _bm
    rnd = random.Random(seed)
    bm = _bm.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    moved = 0
    for v in bm.verts:
        if zmax is not None and v.co.z > zmax:
            continue
        if any(len(e.link_faces) == 1 for e in v.link_edges):
            d = Vector(along) if along else v.normal.copy()
            if d.length < 1e-6:
                continue
            v.co += d.normalized() * (rnd.random() - 0.35) * amount
            moved += 1
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return moved


def rim_boundary(ob, depth=0.005, seed=0, jag=0.0):
    """Extrude every open boundary inward along -normal, so a torn hole in a cloth shell
    shows a wall of fabric instead of a zero-thickness cut."""
    import bmesh as _bm
    rnd = random.Random(seed)
    bm = _bm.new()
    bm.from_mesh(ob.data)
    bm.normal_update()
    edges = [e for e in bm.edges if len(e.link_faces) == 1]
    if not edges:
        bm.free()
        return 0
    ret = _bm.ops.extrude_edge_only(bm, edges=edges)
    verts = [g for g in ret['geom'] if isinstance(g, _bm.types.BMVert)]
    for v in verts:
        n = v.normal.copy()
        if n.length < 1e-6:
            continue
        v.co -= n.normalized() * (depth * (1.0 + jag * (rnd.random() - 0.5)))
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(verts)


def _cap_open_edges(bm, mat_index, jag=0.010, seed=0, push=(0, 0, 0), zband=None):
    """Fill open boundary loops with a ragged gore cap (optionally only inside zband)."""
    import bmesh as _bm
    rnd = random.Random(seed)
    edges = [e for e in bm.edges if len(e.link_faces) == 1]
    if zband is not None:
        lo, hi = zband
        edges = [e for e in edges
                 if lo <= e.verts[0].co.z <= hi and lo <= e.verts[1].co.z <= hi]
    if not edges:
        return []
    res = _bm.ops.holes_fill(bm, edges=edges, sides=0)
    new = [f for f in res.get('faces', []) if f.is_valid]
    if not new:
        return []
    poked = _bm.ops.poke(bm, faces=new)
    faces = [f for f in poked.get('faces', []) if f.is_valid]
    # poke again: a single fan is a lid of long spokes, two gives a crater that can be
    # pushed into a torn surface
    poked2 = _bm.ops.poke(bm, faces=faces)
    faces2 = [f for f in poked2.get('faces', []) if f.is_valid]
    if faces2:
        faces = faces2
    centres = set()
    for f in faces:
        f.material_index = mat_index
        f.smooth = False
    # every cap vertex that is not on the cut ring can be pushed: that is what turns a
    # flat lid into a ragged crater of torn flesh
    for f in faces:
        for v in f.verts:
            if all(len(e.link_faces) == 2 for e in v.link_edges):
                centres.add(v)
    for v in centres:
        v.co += Vector(push) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1),
                                       rnd.uniform(-1, 1))) * jag
    # holes_fill does not guarantee winding: a cap wound the wrong way faces into the body
    # and renders as a flat grey lid instead of gore.  `push` always points out of the
    # stump, so it is the outward reference.
    ref = Vector(push)
    if ref.length > 1e-6:
        ref.normalize()
        bm.normal_update()
        flip = [f for f in faces if f.is_valid and f.normal.dot(ref) < 0.0]
        if flip:
            _bm.ops.reverse_faces(bm, faces=flip)
    return [f for f in faces if f.is_valid]


def split_at_z(ob, z, newname, mat_index=0, jag=0.008, seed=0):
    """Cut `ob` at world height z; everything below moves into a new object `newname`.

    Both halves get a ragged cap over the cut, so hiding the lower half (a crawler whose
    legs were blown off) reveals a gore stump instead of a hole into the void.
    Vertex groups, UVs, materials and the armature modifier all survive the split.
    """
    import bmesh as _bm
    me = ob.data
    bm = _bm.new()
    bm.from_mesh(me)
    _bm.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                         plane_co=(0, 0, z), plane_no=(0, 0, 1), dist=1e-5,
                         clear_inner=False, clear_outer=False)
    bm.to_mesh(me)
    bm.free()
    me.update()

    lower = duplicate(ob, newname)

    def trim(target, keep_above, push):
        b = _bm.new()
        b.from_mesh(target.data)
        doomed = [f for f in b.faces
                  if (f.calc_center_median().z < z) == bool(keep_above)]
        if doomed:
            _bm.ops.delete(b, geom=doomed, context='FACES')
        loose = [v for v in b.verts if not v.link_faces]
        if loose:
            _bm.ops.delete(b, geom=loose, context='VERTS')
        _cap_open_edges(b, mat_index, jag, seed, push,
                        zband=(z - 0.012, z + 0.012))
        b.to_mesh(target.data)
        b.free()
        target.data.update()

    trim(ob, True, (0, 0, -jag * 1.6))
    trim(lower, False, (0, 0, jag * 1.6))
    return ob, lower


def clean_loose(ob):
    import bmesh as _bm
    bm = _bm.new()
    bm.from_mesh(ob.data)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        _bm.ops.delete(bm, geom=loose, context='VERTS')
    edges = [e for e in bm.edges if not e.link_faces]
    if edges:
        _bm.ops.delete(bm, geom=edges, context='EDGES')
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(loose)


def fix_weights(ob, arm, limit=4):
    """Every vertex must be weighted or the glTF exporter invents a neutral bone."""
    deform = {g.index: g.name for g in ob.vertex_groups}
    orphans = [v.index for v in ob.data.vertices
               if not any(g.weight > 1e-5 for g in v.groups if g.group in deform)]
    if orphans:
        # nearest weighted vertex wins
        weighted = [v for v in ob.data.vertices if v.index not in set(orphans)]
        from mathutils.kdtree import KDTree
        kd = KDTree(len(weighted))
        for i, v in enumerate(weighted):
            kd.insert(v.co, i)
        kd.balance()
        for idx in orphans:
            _, i, _ = kd.find(ob.data.vertices[idx].co)
            src = weighted[i]
            for g in src.groups:
                if g.weight > 1e-5:
                    ob.vertex_groups[g.group].add([idx], g.weight, 'REPLACE')
    activate(ob)
    try:
        bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=limit)
        bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
    except Exception as e:
        print('weight cleanup failed', e)
    return len(orphans)


def contact_sheet(paths, out, cols, cell=(320, 460), bg=(0.08, 0.08, 0.09, 1.0)):
    """Composite rendered frames into a single grid image (numpy, no external deps)."""
    import numpy as np
    rows = (len(paths) + cols - 1) // cols
    W, H = cell[0] * cols, cell[1] * rows
    canvas = np.zeros((H, W, 4), dtype=np.float32)
    canvas[:, :] = bg
    for i, p in enumerate(paths):
        img = bpy.data.images.load(p)
        if tuple(img.size) != tuple(cell):
            img.scale(cell[0], cell[1])
        px = np.array(img.pixels[:], dtype=np.float32).reshape(cell[1], cell[0], 4)
        r, c = divmod(i, cols)
        y0 = H - (r + 1) * cell[1]
        canvas[y0:y0 + cell[1], c * cell[0]:(c + 1) * cell[0]] = px
        bpy.data.images.remove(img)
    res = bpy.data.images.new('_sheet', W, H, alpha=True)
    res.pixels = canvas.reshape(-1).tolist()
    res.filepath_raw = out
    res.file_format = 'PNG'
    res.save()
    bpy.data.images.remove(res)
    print('SHEET', out)
    return out


def dusk_render(path, target=(0, 0, 0.95), distance=3.6, yaw_deg=35, pitch_deg=6, lens=50,
                res=(1280, 720), samples=48, key=340.0, fill=75.0, rim=200.0, sky=0.55,
                ground=True, exposure=0.0):
    """Check render lit like the game's apocalyptic dusk: warm low key, cool sky fill.

    Deliberately restrained so albedo mistakes are visible instead of being blown out.
    """
    import sys as _s
    from common import setup_gpu, pbr_material, assign
    scn = setup_gpu(samples)
    scn.render.resolution_x, scn.render.resolution_y = res
    scn.render.film_transparent = False
    scn.view_settings.view_transform = 'AgX'
    scn.view_settings.exposure = exposure
    helpers = []
    if scn.world is None:
        scn.world = bpy.data.worlds.new('World')
    scn.world.use_nodes = True
    wnt = scn.world.node_tree
    for n in list(wnt.nodes):
        if n.type != 'OUTPUT_WORLD':
            wnt.nodes.remove(n)
    out = wnt.nodes['World Output']
    bg = wnt.nodes.new('ShaderNodeBackground')
    grad = wnt.nodes.new('ShaderNodeTexGradient')
    grad.gradient_type = 'LINEAR'
    tex = wnt.nodes.new('ShaderNodeTexCoord')
    mp = wnt.nodes.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (math.radians(90), 0, 0)
    ramp = wnt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.30
    ramp.color_ramp.elements[0].color = (0.32, 0.12, 0.05, 1)
    ramp.color_ramp.elements[1].position = 0.62
    ramp.color_ramp.elements[1].color = (0.10, 0.11, 0.15, 1)
    wnt.links.new(tex.outputs['Generated'], mp.inputs['Vector'])
    wnt.links.new(mp.outputs['Vector'], grad.inputs['Vector'])
    wnt.links.new(grad.outputs['Fac'], ramp.inputs[0])
    wnt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = sky
    wnt.links.new(bg.outputs['Background'], out.inputs['Surface'])

    t = Vector(target)
    yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
    cam_loc = t + Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch),
                          math.sin(pitch))) * distance
    cd = bpy.data.cameras.new('_cam'); cd.lens = lens; cd.clip_end = 500
    cam = bpy.data.objects.new('_cam', cd)
    bpy.context.scene.collection.objects.link(cam); helpers.append(cam)
    cam.location = cam_loc
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scn.camera = cam
    rig = (('_key', (2.4, -3.0, 2.2), key, 2.2, (1.0, 0.62, 0.34)),
           ('_fill', (-3.4, -1.6, 1.6), fill, 4.0, (0.45, 0.58, 0.85)),
           ('_rim', (-1.2, 3.4, 2.6), rim, 1.6, (1.0, 0.74, 0.48)))
    for nm, off, energy, size, col in rig:
        ld = bpy.data.lights.new(nm, 'AREA')
        ld.energy = energy * (distance / 3.6) ** 2
        ld.size = size
        ld.color = col
        lo = bpy.data.objects.new(nm, ld)
        bpy.context.scene.collection.objects.link(lo); helpers.append(lo)
        lo.location = t + Vector(off) * (distance / 3.6)
        lo.rotation_euler = (t - lo.location).to_track_quat('-Z', 'Y').to_euler()
    if ground:
        gp = box_like('_gnd', (60, 60, 0.02), (0, 0, -0.011)); helpers.append(gp)
        assign(gp, pbr_material('_gndmat', (0.055, 0.048, 0.040), 0.92))
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)
    for h in helpers:
        d = h.data
        bpy.data.objects.remove(h, do_unlink=True)
        if isinstance(d, bpy.types.Mesh):
            bpy.data.meshes.remove(d)
        elif isinstance(d, bpy.types.Light):
            bpy.data.lights.remove(d)
        elif isinstance(d, bpy.types.Camera):
            bpy.data.cameras.remove(d)
    print('RENDERED', path)
    return path
