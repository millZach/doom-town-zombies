"""teddy_bear.glb - the mystery box's "bye-bye" bear.

Sitting plush bear ~0.40 m tall, origin at its base, facing -Y.
"""
import sys, os, math, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib_props import *

random.seed(11)


def blob(name, r, loc, scale=(1, 1, 1), rot=(0, 0, 0), segs=18, rings=11):
    return uvsphere(name, r=r, loc=loc, rot=rot, segs=segs, rings=rings, scale=scale)


def build():
    props_scene()

    fur = weathered('teddy_fur', color=(0.145, 0.092, 0.052), roughness=0.93, metallic=0.0,
                    wear_color=(0.215, 0.160, 0.105), wear=0.40, wear_rough=0.98,
                    wear_metal=0.0, rust=0.0, grime=0.88, grime_color=(0.026, 0.020, 0.015),
                    dust=0.26, dust_color=(0.30, 0.27, 0.22), variation=0.30, scale=3.0,
                    seed=1.0, bump=2.6, dent=0.10, scratch=0.15, ao_dist=0.05,
                    speckle=1.15, streak=0.45, pointy_lo=0.485, pointy_hi=0.58)
    fur2 = weathered('teddy_fur_light', color=(0.245, 0.172, 0.105), roughness=0.92,
                     metallic=0.0, wear_color=(0.28, 0.22, 0.16), wear=0.35, wear_rough=0.98,
                     wear_metal=0.0, rust=0.0, grime=0.70, grime_color=(0.032, 0.026, 0.020),
                     dust=0.24, variation=0.28, scale=3.0, seed=5.0, bump=2.6, dent=0.1,
                     scratch=0.15, ao_dist=0.05, speckle=1.15, streak=0.42)
    felt = weathered('teddy_felt', color=(0.075, 0.030, 0.022), roughness=0.88, metallic=0.0,
                     wear_color=(0.16, 0.10, 0.07), wear=0.30, rust=0.0, grime=0.6,
                     dust=0.15, variation=0.2, scale=5.0, seed=9.0, bump=1.2, speckle=0.5)
    button = weathered('teddy_button', color=(0.020, 0.018, 0.016), roughness=0.22,
                       metallic=0.0, wear_color=(0.22, 0.21, 0.20), wear=0.30, rust=0.0,
                       grime=0.5, dust=0.10, variation=0.08, scale=8.0, seed=13.0,
                       bump=0.3, scratch=0.6, speckle=0.15)
    ribbon = weathered('teddy_ribbon', color=(0.215, 0.022, 0.020), roughness=0.70,
                       metallic=0.0, wear_color=(0.20, 0.14, 0.10), wear=0.35, rust=0.0,
                       grime=0.62, dust=0.18, variation=0.2, scale=5.0, seed=17.0,
                       bump=0.9, scratch=0.3, speckle=0.5, streak=0.3)
    thread = weathered('teddy_thread', color=(0.30, 0.27, 0.21), roughness=0.9, metallic=0.0,
                       wear=0.2, rust=0.0, grime=0.5, dust=0.12, variation=0.15, scale=9.0,
                       seed=23.0, bump=1.2, speckle=0.4)

    objs = []

    def A(ob, mat):
        assign(ob, mat); objs.append(ob); return ob

    # ---------------------------------------------------------------- body ----
    A(blob('body', 0.095, (0, 0.010, 0.150), scale=(1.0, 0.92, 1.12)), fur)
    A(blob('belly', 0.072, (0, -0.052, 0.135), scale=(1.0, 0.72, 1.05)), fur2)
    A(blob('head', 0.079, (0, -0.012, 0.300), scale=(1.0, 0.95, 0.94)), fur)
    A(blob('muzzle', 0.040, (0, -0.072, 0.283), scale=(1.10, 0.90, 0.78)), fur2)

    # ears
    for sx in (-1, 1):
        A(blob(f'ear{sx}', 0.034, (sx * 0.060, 0.004, 0.360), scale=(1.0, 0.55, 1.0),
               segs=14, rings=9), fur)
        A(blob(f'earin{sx}', 0.020, (sx * 0.058, -0.020, 0.356), scale=(1.0, 0.30, 1.0),
               segs=12, rings=8), fur2)

    # legs, splayed forward (sitting)
    for sx in (-1, 1):
        A(blob(f'leg{sx}', 0.052, (sx * 0.062, -0.055, 0.052),
               scale=(0.85, 1.55, 0.80), rot=(0, 0, D2R(-sx * 14)), segs=16, rings=10), fur)
        A(blob(f'foot{sx}', 0.040, (sx * 0.070, -0.138, 0.048),
               scale=(0.85, 0.60, 0.95), segs=14, rings=9), fur)
        A(blob(f'pad{sx}', 0.028, (sx * 0.070, -0.170, 0.050),
               scale=(0.90, 0.30, 1.05), segs=12, rings=8), fur2)

    # arms
    for sx in (-1, 1):
        A(blob(f'shoulder{sx}', 0.042, (sx * 0.082, -0.005, 0.202), segs=12, rings=8), fur)
        A(blob(f'arm{sx}', 0.040, (sx * 0.100, -0.030, 0.158),
               scale=(0.88, 0.95, 1.65), rot=(D2R(-20), 0, D2R(sx * 16)), segs=14, rings=10), fur)
        A(blob(f'paw{sx}', 0.038, (sx * 0.118, -0.068, 0.088),
               scale=(0.92, 0.98, 0.88), segs=12, rings=8), fur2)

    # ---------------------------------------------------------------- face ----
    for sx, r in ((-1, 0.0175), (1, 0.0150)):      # mismatched button eyes
        A(blob(f'eye{sx}', r, (sx * 0.035, -0.072, 0.320), scale=(1.0, 0.60, 1.0),
               segs=14, rings=9), button)
        A(cyl(f'eyering{sx}', r=r * 1.30, h=0.004, loc=(sx * 0.035, -0.069, 0.320), verts=14,
              rot=(D2R(90), 0, 0)), thread)
    A(blob('nose', 0.019, (0, -0.104, 0.293), scale=(1.25, 0.70, 0.85), segs=14, rings=9), button)
    # stitched mouth
    A(pipe_path('mouth', [(-0.026, -0.098, 0.262), (-0.012, -0.104, 0.256),
                          (0.0, -0.106, 0.258), (0.012, -0.104, 0.256),
                          (0.026, -0.098, 0.262)], r=0.0035, verts=6), thread)

    # ------------------------------------------------------- repairs / seams ----
    # patch stitched over the belly
    A(rbox('patch', (0.058, 0.010, 0.050), (0.030, -0.100, 0.150), radius=0.004, seg=2,
           rot=(0, D2R(8), D2R(12))), felt)
    for i in range(6):
        a = i / 6 * TAU
        A(pipe_path(f'stitch{i}', [
            (0.030 + math.cos(a) * 0.034, -0.102, 0.150 + math.sin(a) * 0.030),
            (0.030 + math.cos(a) * 0.022, -0.106, 0.150 + math.sin(a) * 0.019)],
            r=0.0025, verts=5), thread)
    # seam down the centre of the body
    A(pipe_path('seam', [(0, -0.100, 0.215), (0, -0.108, 0.180), (0, -0.112, 0.140),
                         (0, -0.106, 0.100)], r=0.0028, verts=6), thread)

    # ribbon round the neck
    A(tube('ribbon', r_out=0.072, r_in=0.058, h=0.022, loc=(0, -0.004, 0.238), verts=22), ribbon)
    for sx in (-1, 1):
        A(blob(f'bow{sx}', 0.026, (sx * 0.040, -0.082, 0.226), scale=(1.0, 0.50, 0.62),
               rot=(0, 0, D2R(sx * 34)), segs=12, rings=8), ribbon)
    A(blob('bowknot', 0.013, (0, -0.086, 0.228), scale=(1.0, 0.7, 1.0), segs=10, rings=7), ribbon)

    # ----------------------------------------------------------------- bake ----
    apply_mods(objs)
    for ob in objs:
        shade_smooth(ob, 60)
    print('  pre-bake tris:', tri_count())
    bake_pbr(objs, 'teddy', size=1024, samples=4, normal_samples=6, margin=0.004)

    bear = join('teddy_bear', objs)
    set_origin(bear, (0, 0, 0))
    print('  tris:', tri_count())
    shots('teddy_bear', target=(0, -0.04, 0.20), hero=(0.95, 28, 12), close=(0.40, 12, 6),
          close_target=(0, -0.05, 0.30), samples=48, res=(820, 900), world=0.5)
    export_prop('teddy_bear.glb', roots=[bear], quality=80)


build()
