"""Shared helpers for the asset build scripts (Blender 5.2, run headless).

Usage from a build script:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))   # -> tools/blender
    from common import *

Run:
    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python tools/blender/<area>/build_x.py
"""
import bpy, bmesh, math, os
from mathutils import Vector, Matrix, Euler

PROJECT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MODELS_DIR = os.path.join(PROJECT, 'public', 'models')
RENDERS_DIR = os.path.join(PROJECT, 'renders')
TEX_CACHE = os.path.join(PROJECT, 'tools', 'blender', '_texcache')
for d in (MODELS_DIR, RENDERS_DIR, TEX_CACHE):
    os.makedirs(d, exist_ok=True)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scn = bpy.context.scene
    scn.unit_settings.system = 'METRIC'
    scn.unit_settings.scale_length = 1.0
    return scn


def setup_gpu(samples=64):
    """Cycles on the local RTX GPU (OptiX, falls back to CUDA/CPU)."""
    scn = bpy.context.scene
    scn.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for dev_type in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = dev_type
            prefs.get_devices()
            ok = False
            for d in prefs.devices:
                d.use = d.type != 'CPU'
                ok = ok or d.use
            if ok:
                scn.cycles.device = 'GPU'
                break
        except Exception:
            continue
    scn.cycles.samples = samples
    scn.cycles.use_denoising = True
    try:
        scn.cycles.denoiser = 'OPTIX'
    except Exception:
        pass
    return scn


def link(obj, collection=None):
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def new_collection(name, parent=None):
    col = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(col)
    return col


def mesh_object(name, bm, collection=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    return link(ob, collection)


def box(name, size=(1, 1, 1), loc=(0, 0, 0), collection=None, rot=(0, 0, 0)):
    """Axis-aligned box. size = full extents (x, y, z); loc = centre."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    ob = mesh_object(name, bm, collection)
    ob.location = loc
    ob.rotation_euler = rot
    return ob


def empty(name, loc=(0, 0, 0), rot=(0, 0, 0), collection=None, size=0.25, extras=None):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = 'ARROWS'
    ob.empty_display_size = size
    ob.location = loc
    ob.rotation_euler = rot
    if extras:
        for k, v in extras.items():
            ob[k] = v
    return link(ob, collection)


def apply_transforms(ob, loc=False, rot=True, scale=True):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=loc, rotation=rot, scale=scale)


def pbr_material(name, color=(0.8, 0.8, 0.8), roughness=0.6, metallic=0.0,
                 emission=None, emission_strength=0.0, base_tex=None, rough_tex=None, normal_tex=None,
                 normal_strength=1.0):
    """Principled material using only glTF-exportable wiring (image textures, no procedurals)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color[:3], 1.0)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    if emission is not None:
        bsdf.inputs['Emission Color'].default_value = (*emission[:3], 1.0)
        bsdf.inputs['Emission Strength'].default_value = emission_strength
    if base_tex:
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = _img(base_tex)
        nt.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])
    if rough_tex:
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = _img(rough_tex, non_color=True)
        nt.links.new(t.outputs['Color'], bsdf.inputs['Roughness'])
    if normal_tex:
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = _img(normal_tex, non_color=True)
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = normal_strength
        nt.links.new(t.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def _img(path_or_img, non_color=False):
    img = path_or_img if isinstance(path_or_img, bpy.types.Image) else bpy.data.images.load(path_or_img, check_existing=True)
    if non_color:
        img.colorspace_settings.name = 'Non-Color'
    return img


def assign(ob, mat):
    if ob.data.materials:
        ob.data.materials[0] = mat
    else:
        ob.data.materials.append(mat)
    return ob


def bevel(ob, width=0.01, segments=2):
    m = ob.modifiers.new('Bevel', 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    return m


def shade_smooth(ob, angle_deg=40):
    """Smooth shading with auto-smooth by angle (Blender 4.1+ API)."""
    try:
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.shade_auto_smooth(angle=math.radians(angle_deg))
    except Exception:
        for p in ob.data.polygons:
            p.use_smooth = True


def preview_render(path, target=(0, 0, 1), distance=4.0, yaw_deg=35, pitch_deg=15, lens=50,
                   res=(1280, 720), samples=48, ground=True, world_strength=0.6, cam_loc=None, cam_look=None):
    """Quick lit Cycles check render with a 3-point rig. Leaves no helper objects behind."""
    scn = setup_gpu(samples)
    scn.render.resolution_x, scn.render.resolution_y = res
    scn.render.film_transparent = False
    scn.view_settings.view_transform = 'AgX'
    helpers = []
    if scn.world is None:
        scn.world = bpy.data.worlds.new('World')
    scn.world.use_nodes = True
    bg = scn.world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (0.35, 0.38, 0.42, 1)
    bg.inputs['Strength'].default_value = world_strength
    t = Vector(target)
    if cam_loc is None:
        yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
        cam_loc = t + Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch))) * distance
    cam_data = bpy.data.cameras.new('_prev_cam'); cam_data.lens = lens; cam_data.clip_end = 2000
    cam = bpy.data.objects.new('_prev_cam', cam_data); link(cam); helpers.append(cam)
    cam.location = Vector(cam_loc)
    look = Vector(cam_look) if cam_look is not None else t
    cam.rotation_euler = (look - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scn.camera = cam
    for nm, off, energy, size in (('_key', (3, -3, 4), 400, 2.0), ('_fill', (-4, -2, 2), 120, 4.0), ('_rim', (0, 4, 3), 300, 2.0)):
        ld = bpy.data.lights.new(nm, 'AREA'); ld.energy = energy * (distance / 4.0) ** 2; ld.size = size
        lo = bpy.data.objects.new(nm, ld); link(lo); helpers.append(lo)
        lo.location = t + Vector(off) * (distance / 4.0)
        lo.rotation_euler = (t - lo.location).to_track_quat('-Z', 'Y').to_euler()
    if ground:
        gp = box('_ground', (200, 200, 0.02), (0, 0, -0.011)); helpers.append(gp)
        assign(gp, pbr_material('_ground_mat', (0.18, 0.18, 0.18), 0.8))
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)
    for h in helpers:
        data = h.data
        bpy.data.objects.remove(h, do_unlink=True)
        if data is not None:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)
            elif isinstance(data, bpy.types.Camera):
                bpy.data.cameras.remove(data)
    print('RENDERED', path)
    return path


def bake_tileable(name, build_material_fn, size=1024, passes=('DIFFUSE', 'ROUGHNESS', 'NORMAL'), samples=16, force=False):
    """Bake a procedural material (built by build_material_fn(mat)) on a 1x1 plane into tileable
    image textures in TEX_CACHE. Returns dict pass->filepath. Cached unless force=True.
    Procedural nodes should use Object/Generated coords with seamless noise (e.g. 4D noise on a
    torus mapping) if true tiling matters; for most surfaces mild seams are hidden by UV scale."""
    out = {p: os.path.join(TEX_CACHE, f'{name}_{p.lower()}.png') for p in passes}
    if not force and all(os.path.exists(p) for p in out.values()):
        return out
    scn = setup_gpu(samples)
    bpy.ops.mesh.primitive_plane_add(size=1)
    plane = bpy.context.active_object
    mat = bpy.data.materials.new('_bake_' + name); mat.use_nodes = True
    build_material_fn(mat)
    assign(plane, mat)
    nt = mat.node_tree
    for p in passes:
        img = bpy.data.images.new(f'{name}_{p}', size, size, float_buffer=(p == 'NORMAL'))
        if p != 'DIFFUSE':
            img.colorspace_settings.name = 'Non-Color'
        tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = img
        for n in nt.nodes: n.select = False
        tn.select = True; nt.nodes.active = tn
        bpy.ops.object.select_all(action='DESELECT'); plane.select_set(True)
        bpy.context.view_layer.objects.active = plane
        kw = {'type': p}
        if p == 'DIFFUSE':
            scn.render.bake.use_pass_direct = False
            scn.render.bake.use_pass_indirect = False
            scn.render.bake.use_pass_color = True
        if p == 'NORMAL':
            scn.render.bake.normal_space = 'TANGENT'
        bpy.ops.object.bake(**kw)
        img.filepath_raw = out[p]
        img.file_format = 'PNG'
        img.save()
        nt.nodes.remove(tn)
    bpy.data.objects.remove(plane, do_unlink=True)
    return out


def export_glb(path, selected_objects=None, animations=True, extras=True):
    """Export glTF binary, +Y up. Pass a list of objects to export only those (and their children)."""
    kwargs = dict(filepath=path, export_format='GLB', export_yup=True, export_apply=True,
                  export_extras=extras, export_animations=animations, export_image_format='AUTO')
    if selected_objects is not None:
        bpy.ops.object.select_all(action='DESELECT')
        def sel(o):
            o.select_set(True)
            for c in o.children:
                sel(c)
        for o in selected_objects:
            sel(o)
        kwargs['use_selection'] = True
    bpy.ops.export_scene.gltf(**kwargs)
    print('EXPORTED', path, os.path.getsize(path) // 1024, 'KB')
    return path
