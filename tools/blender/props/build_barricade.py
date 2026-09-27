"""barricade.glb - boarded-up window barricade for the 1.2 x 1.1 m opening.

Origin: sill centre (opening spans X -0.6..0.6, Z 0..1.1, wall mid-plane Y = 0).
-Y is the interior (playable) side; the six planks sit on the interior face.

Objects: frame, board_1 .. board_6  (each board's origin is its own centre)
"""
import sys, os, math, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib_props import *

random.seed(7)

W, H = 1.2, 1.1          # opening
CASE_OUT_W, CASE_OUT_H = 1.36, 1.25   # outer size of the frame ring
CASE_FRONT = -0.165      # interior face of the frame
CASE_BACK = 0.065        # buried in the wall
BOARD_Y = -0.208         # plank centre (planks 0.03 thick -> -0.223 .. -0.193)
BOARD_T = 0.030


def plank(name, length, height, thick, loc, rot, seed):
    """Warped, chamfered timber plank."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(length, thick, height), verts=bm.verts)
    xe = [e for e in bm.edges if abs(e.verts[0].co.x - e.verts[1].co.x) > 1e-4]
    bmesh.ops.subdivide_edges(bm, edges=xe, cuts=7, use_grid_fill=False)
    ze = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-4]
    bmesh.ops.subdivide_edges(bm, edges=ze, cuts=1, use_grid_fill=False)
    ob = finish(name, bm, loc, rot)
    jitter(ob, amount=0.012, scale=2.2, seed=seed, axis=(0.22, 0.30, 0.75))
    m = ob.modifiers.new('Bevel', 'BEVEL')
    m.width = 0.0035; m.segments = 2; m.limit_method = 'ANGLE'; m.angle_limit = D2R(35)
    return ob


def nail(name, loc, rot=(0, 0, 0), r=0.0068, out=0.0042):
    """Round nail head standing proud of the plank, with a stub of shank behind it."""
    bm = bmesh.new()
    # slightly domed head
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=12,
                          radius1=r, radius2=r * 0.80, depth=out)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, out / 2))
    bm2 = bmesh.new()
    bmesh.ops.create_cone(bm2, cap_ends=True, cap_tris=False, segments=8,
                          radius1=r * 0.32, radius2=r * 0.32, depth=0.03)
    bmesh.ops.translate(bm2, verts=bm2.verts, vec=(0, 0, -0.015))
    me = bpy.data.meshes.new('_n'); bm2.to_mesh(me); bm2.free()
    bm.from_mesh(me); bpy.data.meshes.remove(me)
    ob = finish(name, bm, loc, rot)
    m = ob.modifiers.new('Bevel', 'BEVEL')
    m.width = r * 0.16; m.segments = 1; m.limit_method = 'ANGLE'
    return ob


def build():
    props_scene()

    # ---------------------------------------------------------------- frame ----
    frame_parts = []
    # chunky wooden casing ring around the opening, deep enough to always meet the wall
    hw, hh = W / 2, H
    ow, oh = CASE_OUT_W / 2, CASE_OUT_H
    depth = CASE_BACK - CASE_FRONT
    ymid = (CASE_BACK + CASE_FRONT) / 2
    segs = [
        # name, x0, x1, z0, z1
        ('frame_l', -ow, -hw, -0.06, oh),
        ('frame_r', hw, ow, -0.06, oh),
        ('frame_t', -hw, hw, H, oh),
        ('frame_b', -hw, hw, -0.06, 0.0),
    ]
    for nm, x0, x1, z0, z1 in segs:
        ob = rbox(nm, (x1 - x0, depth, z1 - z0),
                  ((x0 + x1) / 2, ymid, (z0 + z1) / 2), radius=0.006, seg=2)
        frame_parts.append(ob)

    # stepped architrave mouldings on the face of the casing (inner bead + outer backband)
    BEAD_Y = CASE_FRONT - 0.012
    beads = [
        ('bead_li', -hw, -hw + 0.024, -0.06, oh), ('bead_ri', hw - 0.024, hw, -0.06, oh),
        ('bead_ti', -hw, hw, H - 0.024, H), ('bead_bi', -hw, hw, 0.0, 0.024),
        ('bead_lo', -ow, -ow + 0.030, -0.06, oh), ('bead_ro', ow - 0.030, ow, -0.06, oh),
        ('bead_to', -ow, ow, oh - 0.030, oh),
    ]
    for nm, x0, x1, z0, z1 in beads:
        frame_parts.append(rbox(nm, (x1 - x0, 0.024, z1 - z0),
                                ((x0 + x1) / 2, BEAD_Y, (z0 + z1) / 2), radius=0.005, seg=2))

    # stool / sill projecting into the room
    sill = rbox('frame_sill', (CASE_OUT_W + 0.09, 0.26, 0.042),
                (0, -0.100, -0.081), radius=0.008, seg=2)
    frame_parts.append(sill)
    # apron under the sill
    frame_parts.append(rbox('frame_apron', (CASE_OUT_W - 0.05, 0.030, 0.080),
                            (0, -0.205, -0.142), radius=0.005, seg=2))
    # thin reveal lining around the inside of the opening (hides the wall cut)
    for nm, x0, x1, z0, z1, yl in (
            ('rev_l', -hw, -hw + 0.014, 0.0, H, 0.30),
            ('rev_r', hw - 0.014, hw, 0.0, H, 0.30),
            ('rev_t', -hw, hw, H - 0.014, H, 0.30)):
        frame_parts.append(box(nm, (x1 - x0, yl, z1 - z0), ((x0 + x1) / 2, 0.0, (z0 + z1) / 2)))

    # a few splintered stubs of earlier boards still nailed to the frame
    stub = plank('frame_stub1', 0.22, 0.13, 0.026, (-0.56, BOARD_Y + 0.016, 0.375),
                 (0, D2R(9), D2R(3)), 31)
    frame_parts.append(stub)
    stub2 = plank('frame_stub2', 0.17, 0.12, 0.026, (0.575, BOARD_Y + 0.016, 0.885),
                  (0, D2R(-12), D2R(-4)), 32)
    frame_parts.append(stub2)

    for ob in frame_parts:
        jitter(ob, amount=0.0022, scale=5.0, seed=hash(ob.name) % 97, axis=(1, 0.4, 1))

    paint = painted_wood('frame_paint', color=(0.60, 0.565, 0.455), rough=0.44, chip=0.65,
                         grime=0.9, seed=2.0, scale=1.0, peel=0.72, dust=0.12)
    paint2 = painted_wood('frame_paint_rev', color=(0.50, 0.465, 0.365), rough=0.52, chip=0.8,
                          grime=1.0, seed=6.0, scale=1.0, peel=0.85, dust=0.10)
    bare = wood_mat('frame_bare', color=(0.175, 0.105, 0.052), rough=0.78, grime=0.75,
                    seed=5.0, scale=1.0, grain=1.0, split=0.85, axis='X')
    for ob in frame_parts:
        if ob.name.startswith('frame_stub'):
            assign(ob, bare)
        elif ob.name.startswith('rev_'):
            assign(ob, paint2)
        else:
            assign(ob, paint)

    # ---------------------------------------------------------------- boards ----
    steel = weathered('nail_steel', color=(0.185, 0.175, 0.168), roughness=0.62, metallic=1.0,
                      wear_color=(0.42, 0.41, 0.40), wear=0.18, wear_rough=0.4,
                      rust=0.95, rust_color=(0.26, 0.115, 0.045), grime=0.6,
                      dust=0.08, variation=0.12, scale=9.0, seed=9.0, bump=1.0,
                      dent=0.3, scratch=0.9, ao_dist=0.02, pointy_lo=0.42, pointy_hi=0.62)

    boards = []
    layout = [
        # z, length, tilt(deg), xoff, y-lift (some boards stand proud)
        (0.095, 1.44, 3.4, -0.030, 0.000),
        (0.278, 1.37, -5.2, 0.048, -0.016),
        (0.462, 1.47, 0.8, 0.005, 0.004),
        (0.652, 1.39, -1.6, -0.052, -0.022),
        (0.838, 1.34, 6.0, 0.038, 0.002),
        (1.008, 1.45, -2.6, -0.012, -0.014),
    ]
    for i, (z, ln, tilt, xoff, ylift) in enumerate(layout, start=1):
        seed = 100 + i * 7
        hgt = 0.132 + random.uniform(-0.016, 0.018)
        b = plank(f'board_{i}', ln, hgt, BOARD_T, (xoff, BOARD_Y + ylift, z),
                  (random.uniform(-0.03, 0.03), D2R(tilt), random.uniform(-0.05, 0.05)), seed)
        t = random.uniform(0.82, 1.22)
        assign(b, wood_mat(f'board_wood_{i}', color=(0.172 * t, 0.104 * t, 0.050 * t),
                           rough=0.76, grime=0.8, seed=float(i) * 3.1, scale=1.0,
                           grain=1.0, split=0.85, axis='X',
                           bleach=0.10 + 0.18 * (i % 3) / 2.0))
        parts = [b]
        # nails: two at each end, plus the odd extra
        ends = [-ln / 2 + 0.055, ln / 2 - 0.055]
        k = 0
        for ex in ends:
            for dz in (-hgt * 0.26, hgt * 0.27):
                k += 1
                nx = ex + random.uniform(-0.012, 0.012)
                nl = b.matrix_world @ Vector((nx, -BOARD_T / 2 - 0.0055, dz))
                nb = nail(f'board_{i}_nail_{k}', nl)
                nb.rotation_euler = (D2R(90) + random.uniform(-0.16, 0.16),
                                     random.uniform(-0.22, 0.22), 0)
                assign(nb, steel)
                parts.append(nb)
        boards.append((f'board_{i}', parts, b))

    # ---------------------------------------------------------------- bake ----
    all_objs = frame_parts + [o for _, ps, _ in boards for o in ps]
    apply_mods(all_objs)
    bake_pbr(all_objs, 'barricade', size=2048, samples=4, normal_samples=6, margin=0.0025)

    # ------------------------------------------------------------- assemble ----
    frame = join('frame', frame_parts)
    set_origin(frame, (0, 0, 0))

    finals = []
    for nm, parts, bd in boards:
        c = bd.matrix_world.translation.copy()
        ob = join(nm, parts)
        set_origin(ob, c)
        finals.append(ob)

    print('tris:', tri_count())
    shots('barricade', target=(0, -0.05, 0.55), hero=(3.5, 30, 10), close=(1.05, 50, 2),
          close_target=(-0.42, -0.1, 0.30), ground=False, samples=48)
    export_prop('barricade.glb', roots=[frame] + finals)


build()
