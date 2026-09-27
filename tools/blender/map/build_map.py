"""Doom Town — assemble everything and export public/models/map_doomtown.glb.

Run:
  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup \
      --python tools/blender/map/build_map.py -- [--renders] [--force-bake] [--no-export]
"""
import bpy, math, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import common  # noqa: E402
from common import MODELS_DIR, RENDERS_DIR, setup_gpu, link, assign  # noqa: E402
import lib_materials as LM  # noqa: E402
import lib_map  # noqa: E402
import layout as L  # noqa: E402
import build_street, build_houses, build_bunker, build_props, build_backdrop  # noqa: E402
import build_yards  # noqa: E402

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.join(MODELS_DIR, 'map_doomtown.glb')


def build_scene(force_bake=False):
    t0 = time.time()
    common.reset_scene()
    mats = LM.build_all(force=force_bake)
    print('materials ready in %.1fs' % (time.time() - t0))
    scn = lib_map.Scene(mats)
    scn.uv_scale = dict(LM.UV_SCALE)
    # chamfer hard edges so they catch the low sun; terrain and huge slabs are left alone
    scn.smooth_angle = 0.55          # smooth curved lofts, keep box corners sharp
    scn.bevel_default = 0.013
    for flat in ('dirt', 'dirt_scorch', 'asphalt', 'desert', 'desert_far', 'sidewalk',
                 'glass', 'glass_dark', 'sign_paint', 'fabric_olive', 'lino', 'woodfloor',
                 'wallpaper_a', 'wallpaper_b', 'plaster', 'fabric_weave_r', 'fabric_weave_o',
                 'fabric_weave_b', 'paint_stencil_w', 'paint_stencil_y', 'paint_stencil_k',
                 'paint_stencil_r'):
        scn.bevel[flat] = 0.0
    for dm in LM.DECAL_MATS:                 # decal quads are single faces: never bevel them
        scn.bevel[dm] = 0.0
    # `charred` is near-black and matte: a bevel highlight on it is invisible, and it was the
    # single biggest mesh in the export. Not bevelling it costs nothing and saves ~70k tris.
    scn.bevel['charred'] = 0.0
    for fine, w in (('wood_white', 0.008), ('wood_bare', 0.010), ('wood_trim_y', 0.008),
                    ('wood_trim_g', 0.008), ('chrome', 0.008), ('metal_rust', 0.010),
                    ('metal_dark', 0.010), ('steel_paint', 0.010), ('rubble', 0.008), ('brick', 0.008)):
        scn.bevel[fine] = w

    build_street.build(scn)
    build_houses.build(scn)
    build_bunker.build(scn)
    build_yards.build(scn)
    build_props.build(scn)
    build_backdrop.build(scn)

    for zid, boxes in L.ZONES.items():
        for (mn, mx) in boxes:
            scn.zone(zid, mn, mx)
    for (name, loc, yaw) in L.MARKERS:
        scn.marker(name, loc, yaw)
    for (name, loc) in L.FIRES:
        scn.marker(name, loc, 0.0)

    objs = scn.build()
    colmat = mats['collision']
    for ob in scn.col_objs:
        assign(ob, colmat)
    tris = 0
    for ob in objs:
        ob.data.calc_loop_triangles()
        tris += len(ob.data.loop_triangles)
    print('built %d meshes, %d colliders, ~%d tris in %.1fs' %
          (len(objs), len(scn.col_objs), tris, time.time() - t0))
    return scn


# --------------------------------------------------------------------------- check renders
def _arg(name, default):
    for a in ARGV:
        if a.startswith('--%s=' % name):
            return float(a.split('=', 1)[1])
    return default


def dusk_world(strength=None):
    """Burnt-orange apocalyptic dusk: a vertical gradient sky, no visible sun disc."""
    strength = _arg('world', 2.20) if strength is None else strength
    scn = bpy.context.scene
    if scn.world is None:
        scn.world = bpy.data.worlds.new('World')
    scn.world.use_nodes = True
    nt = scn.world.node_tree
    for n in list(nt.nodes):
        if n.bl_idname != 'ShaderNodeOutputWorld':
            nt.nodes.remove(n)
    out = nt.nodes['World Output']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs['Vector'])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = -0.35
    mr.inputs['From Max'].default_value = 0.55
    mr.clamp = True
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    el = ramp.color_ramp.elements
    while len(el) > 1:
        el.remove(el[-1])
    stops = [(0.00, (0.055, 0.030, 0.020)), (0.34, (0.420, 0.140, 0.050)),
             (0.395, (1.000, 0.330, 0.085)), (0.46, (0.560, 0.230, 0.115)),
             (0.62, (0.120, 0.085, 0.100)), (1.00, (0.030, 0.030, 0.055))]
    for i, (p_, c) in enumerate(stops):
        e = el[0] if i == 0 else el.new(p_)
        e.position = p_
        e.color = (*c, 1.0)
    nt.links.new(mr.outputs['Result'], ramp.inputs['Factor'])
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = strength
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    return scn


def add_sun():
    ld = bpy.data.lights.new('_sun', 'SUN')
    ld.energy = _arg('sun', 5.0)
    ld.angle = math.radians(3.0)
    ld.color = (1.0, 0.44, 0.17)
    ob = bpy.data.objects.new('_sun', ld)
    link(ob)
    ob.rotation_euler = (math.radians(86), 0, math.radians(-125))
    return ob


def add_fill_lights():
    """Stand-ins for the in-game fire / lamp light so the check renders read like the game."""
    out = []
    for (name, loc) in L.FIRES:
        ld = bpy.data.lights.new('_f', 'POINT')
        ld.energy = 900
        ld.color = (1.0, 0.45, 0.14)
        ld.shadow_soft_size = 0.4
        ob = bpy.data.objects.new('_f', ld)
        link(ob)
        ob.location = (loc[0], loc[1], loc[2] + 0.8)
        out.append(ob)
    # preview-only fills: the modelled ceiling fixtures upstairs and in the halls carry the
    # `lamp_glow` material (the game drives those), but they have no MK_LAMP marker because
    # the contract caps the map at 12. They exist so the check renders are not black.
    for side in ('yellow', 'green'):
        for (lx, ly, z) in ((8.4, 2.2, L.CEIL_H - 0.28), (9.9, -0.6, L.CEIL_H - 0.28)):
            ld = bpy.data.lights.new('_u', 'POINT')
            ld.energy = 520
            ld.color = (1.0, 0.82, 0.58)
            ld.shadow_soft_size = 0.3
            ob = bpy.data.objects.new('_u', ld)
            link(ob)
            ob.location = L.hp(side, lx, ly, z)
            out.append(ob)
    for (name, loc, yaw) in L.MARKERS:
        if not name.startswith('MK_LAMP'):
            continue
        ld = bpy.data.lights.new('_l', 'POINT')
        ld.energy = _arg('lamp', 620)
        ld.color = (1.0, 0.80, 0.55)
        ld.shadow_soft_size = 0.25
        ob = bpy.data.objects.new('_l', ld)
        link(ob)
        ob.location = (loc[0], loc[1], loc[2] - 0.1)
        out.append(ob)
    return out


SHOTS = [
    ('start', (0.0, 8.2, 1.70), (0.0, -12.0, 2.40), 20),
    ('start_wide', (0.0, 8.2, 1.70), (-6.0, -6.0, 2.60), 18),
    ('yellow_front', (-6.0, -2.1, 1.70), (-16.0, -2.4, 1.60), 24),
    ('green_front', (6.0, 2.1, 1.70), (16.0, 2.4, 1.60), 24),
    ('bus', (3.6, -7.0, 1.70), (-4.0, -14.5, 1.40), 28),
    ('south', (4.6, -17.6, 1.70), (-3.0, -2.0, 3.20), 20),
    ('kerb', (-8.8, -4.0, 1.70), (4.0, -13.0, 1.60), 24),
    ('car_teal', (-5.2, 3.2, 1.55), (-8.6, 5.9, 0.90), 35),
    ('dummies', (-3.4, -6.4, 1.55), (-6.0, -8.7, 1.10), 40),
    ('tree', (-4.6, -6.6, 1.70), (-10.1, -9.5, 3.30), 30),
    ('neighbours', (-9.5, -16.0, 1.70), (-30.0, -24.0, 3.20), 30),
    ('car_flip', (0.4, 4.4, 1.70), (5.4, 8.4, 0.80), 24),
    ('car_cream', (6.0, -3.4, 1.55), (8.9, -1.2, 0.85), 35),
    ('bus_front', (3.0, -8.4, 1.60), (-0.6, -11.6, 1.40), 30),
    ('bunker_door', (0.4, 4.0, 1.70), (0.0, 12.5, 1.90), 26),
    ('yellow_living', (-16.90, -1.10, 1.65), (-12.60, -5.60, 1.05), 22),
    ('yellow_kitchen', (-13.00, 2.40, 1.65), (-16.20, 6.20, 1.20), 22),
    ('yellow_bed', (-18.30, -1.90, 1.65), (-22.20, -5.60, 1.10), 20),
    ('yellow_hall', (-18.40, 5.60, 1.65), (-22.20, 1.00, 1.30), 20),
    ('green_living', (16.90, 1.10, 1.65), (12.60, 5.60, 1.05), 22),
    ('green_bed', (18.30, 1.90, 1.65), (22.20, 5.60, 1.10), 20),
    ('bunker_room', (-1.2, 18.4, -0.85), (3.0, 26.0, -1.75), 18),
    ('bunker_pap', (3.0, 22.0, -0.85), (-4.0, 27.5, -1.60), 20),
    ('bunker_over', (-6.6, 18.2, -0.60), (6.0, 27.0, -1.90), 17),
    ('bunker_ramp', (0.0, 11.2, 1.55), (0.3, 18.0, -1.90), 20),
    ('bunker_ramp_side', (0.0, 16.4, -1.30), (0.0, 11.0, 1.30), 22),
    # --- second storey, staircases, back yards and the upstairs spawn pockets
    ('yellow_stairs', (-21.80, -0.90, 1.78), (-19.60, 3.00, 1.25), 17),
    ('green_stairs', (21.80, 0.90, 1.78), (19.60, -3.00, 1.25), 17),
    ('yellow_up', (-18.30, 1.20, 4.62), (-22.20, 5.40, 4.10), 20),
    ('green_up', (18.30, -1.20, 4.62), (22.20, -5.40, 4.10), 20),
    ('yellow_bed_up', (-12.90, -5.80, 4.58), (-17.20, -3.60, 3.80), 22),
    ('green_bed_up', (12.90, 5.80, 4.58), (17.20, 3.60, 3.80), 22),
    ('yellow_yard', (-23.70, 1.10, 1.70), (-28.20, -5.20, 1.05), 22),
    ('green_yard', (23.70, -1.10, 1.70), (28.20, 5.20, 1.05), 22),
    ('yellow_pocket', (-26.90, 4.10, 4.65), (-22.50, 5.70, 4.20), 22),
    ('green_pocket', (26.90, -4.10, 4.65), (22.50, -5.70, 4.20), 22),
    ('yellow_back', (-25.60, 1.10, 1.75), (-21.60, 1.80, 1.40), 26),
    ('yellow_a2_up', (-12.30, 1.30, 4.57), (-16.70, -1.80, 3.90), 20),
    ('green_kitchen', (14.50, -4.60, 1.65), (18.40, -4.80, 1.35), 22),
    ('yellow_bath_up', (-15.20, 2.05, 4.58), (-16.70, 5.80, 3.85), 20),
    ('yellow_box_up', (-12.10, 2.30, 4.58), (-14.60, 5.50, 3.85), 20),
    ('yellow_yard2', (-23.40, -0.60, 1.72), (-28.60, -7.20, 1.05), 24),
    ('yard_wide', (-27.5, -12.0, 6.8), (-23.0, 4.0, 0.8), 20),
    ('topdown_yardw', (-21.0, 0.0, 30.0), (-21.0, 0.001, 0.0), 32),
    ('topdown', (0.0, 0.0, 58.0), (0.0, 0.001, 0.0), 24),
    ('topdown_bunker', (0.0, 20.0, 46.0), (0.0, 20.001, 0.0), 24),
]


def render_checks(only=None, samples=48, res=(1280, 720), scene=None):
    from mathutils import Vector
    if scene is not None:
        for ob in scene.col_objs:
            ob.hide_render = True
        for ob in scene.col_mk.objects:
            ob.hide_render = True
    scn = dusk_world()
    setup_gpu(samples)
    scn.render.resolution_x, scn.render.resolution_y = res
    scn.render.film_transparent = False
    scn.view_settings.view_transform = 'AgX'
    scn.view_settings.look = 'AgX - Medium High Contrast'
    scn.view_settings.exposure = _arg('exposure', -1.2)
    sun = add_sun()
    fills = add_fill_lights()
    outdir = os.path.join(RENDERS_DIR, 'map')
    os.makedirs(outdir, exist_ok=True)
    cam_data = bpy.data.cameras.new('_cam'); cam_data.clip_end = 3000
    cam = bpy.data.objects.new('_cam', cam_data); link(cam)
    scn.camera = cam
    for (name, loc, look, lens) in SHOTS:
        if only and name not in only:
            continue
        cam_data.lens = lens
        cam.location = Vector(loc)
        cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        scn.render.filepath = os.path.join(outdir, name + '.png')
        bpy.ops.render.render(write_still=True)
        print('RENDERED', scn.render.filepath)
    bpy.data.objects.remove(cam, do_unlink=True)
    bpy.data.objects.remove(sun, do_unlink=True)
    for f in fills:
        bpy.data.objects.remove(f, do_unlink=True)


def export():
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_yup=True,
                              export_apply=True, export_extras=True, export_animations=False,
                              export_image_format='WEBP', export_image_quality=76,
                              export_texture_dir='', export_cameras=False, export_lights=False)
    print('EXPORTED', OUT, os.path.getsize(OUT) // 1024, 'KB')


if __name__ == '__main__':
    scn = build_scene(force_bake='--force-bake' in ARGV)
    if '--audit' in ARGV:
        import audit_coplanar
        meshes = [o for o in bpy.data.objects
                  if o.type == 'MESH' and not o.name.startswith(('COL_', 'ZONE_'))]
        audit_coplanar.audit(meshes, limit=int(_arg('auditn', 45)))
    if '--no-export' not in ARGV:
        export()
    if '--renders' in ARGV:
        only = None
        for a in ARGV:
            if a.startswith('--only='):
                only = set(a.split('=', 1)[1].split(','))
        render_checks(only, samples=int(_arg('samples', 48)),
                      res=(int(_arg('w', 1280)), int(_arg('h', 720))), scene=scn)
