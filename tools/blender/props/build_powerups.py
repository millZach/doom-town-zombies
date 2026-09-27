"""pu_*.glb - the six power-up pickups.

Max Ammo (ammo can + cartridges), Insta-Kill (skull), Double Points ("x2" coin),
Kaboom (1950s atomic bomb), Carpenter (claw hammer), Fire Sale ($ price tag).

Each is fitted to 0.45 m across its largest dimension, origin at the centre of its
bounding box, front = -Y, in one polished-gold/brass finish baked to a single 1024
texture set.  The game spins them about Z, bobs them and lights them with a green
glow, so every one needs a silhouette that survives a full turn.

Run one per process (re-initialising the scene after a GPU render can crash Blender):
    blender -b --factory-startup --python build_powerups.py -- maxammo
    blender -b --factory-startup --python build_powerups.py -- lineup
"""
import sys, os, math, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib_pu import *

TARGET = 0.45


# ------------------------------------------------------------------ 1. max ammo ----

def p_maxammo():
    """Steel ammunition can, lid swung open, full of gleaming rifle cartridges."""
    g, d, s = gold('ma_g', 1.0), gold_dark('ma_d', 2.0), gold_bright('ma_s', 3.0)
    br = gold('ma_br', 4.0, tint=(0.760, 0.530, 0.170), rough=0.145, grime=0.20,
              wear=0.55, verdigris=0.04)
    o = []
    W, D, H = 0.300, 0.150, 0.155

    can = rbox('can', (W, D, H), (0, 0, 0), radius=0.009, seg=2)
    # hollow out the top so the rounds really sit inside it
    hollow = box('_hollow', (W - 0.030, D - 0.030, 0.150), (0, 0, 0.090))
    carve(can, [hollow])
    o.append((can, g))

    # pressed ribs near the ends, top rails, bottom skid
    for sx in (-0.113, 0.113):
        o.append((rbox(f'rib{sx}', (0.022, D + 0.010, H - 0.026), (sx, 0, -0.006),
                       radius=0.004, seg=1), s))
    for sy in (-1, 1):
        o.append((rbox(f'rail{sy}', (W + 0.014, 0.015, 0.020), (0, sy * (D / 2 + 0.002), H / 2 - 0.006),
                       radius=0.004, seg=1), s))
    for sx in (-1, 1):
        o.append((rbox(f'railx{sx}', (0.015, D + 0.014, 0.020), (sx * (W / 2 + 0.002), 0, H / 2 - 0.006),
                       radius=0.004, seg=1), s))
    o.append((rbox('skid', (W - 0.024, D - 0.016, 0.018), (0, 0, -H / 2 - 0.004),
                   radius=0.004, seg=1), d))

    # ---- lid, swung open on the rear hinge -------------------------------------
    ang = D2R(-62)
    hinge = (0, D / 2 + 0.004, H / 2 + 0.004)
    lid_loc = hinge_place((0, 0, H / 2 + 0.020), hinge, ang)
    LM = Matrix.Translation(lid_loc) @ Matrix.Rotation(ang, 4, 'X')
    o.append((rbox('lid', (W + 0.020, D + 0.020, 0.024), lid_loc, radius=0.005, seg=2,
                   rot=(ang, 0, 0)), g))
    # sealing lip: a frame, not a slab, so the inner face of the lid still shows
    for sy in (-1, 1):
        lp = rbox(f'lidlipY{sy}', (W + 0.004, 0.016, 0.030), (0, 0, 0), radius=0.004, seg=1)
        lp.matrix_world = LM @ Matrix.Translation((0, sy * 0.069, -0.020))
        o.append((lp, d))
    for sx in (-1, 1):
        lp = rbox(f'lidlipX{sx}', (0.016, D + 0.004, 0.030), (0, 0, 0), radius=0.004, seg=1)
        lp.matrix_world = LM @ Matrix.Translation((sx * 0.144, 0, -0.020))
        o.append((lp, d))
    # raised panel + ribs so the outside of the lid isn't a blank slab
    pan = rbox('lidpanel', (W - 0.060, D - 0.040, 0.030), (0, 0, 0), radius=0.006, seg=1)
    pan.matrix_world = LM @ Matrix.Translation((0, 0, 0.003))
    o.append((pan, s))
    for sx in (-1, 1):
        rb = rbox(f'lidrib{sx}', (0.016, D - 0.010, 0.032), (0, 0, 0), radius=0.004, seg=1)
        rb.matrix_world = LM @ Matrix.Translation((sx * 0.114, 0, 0.002))
        o.append((rb, d))
    # inner face gets ribs too - it is the biggest flat area once the lid is open
    for i, sx in enumerate((-0.088, 0.0, 0.088)):
        rb = rbox(f'lidinner{i}', (0.030, D - 0.030, 0.030), (0, 0, 0), radius=0.006, seg=1)
        rb.matrix_world = LM @ Matrix.Translation((sx, 0, -0.018))
        o.append((rb, s))
    # carry handle on the outside of the lid
    hd = pipe_path('handle', [(-0.058, 0.0, 0.014), (-0.062, 0.0, 0.048), (-0.030, 0.0, 0.062),
                              (0.030, 0.0, 0.062), (0.062, 0.0, 0.048), (0.058, 0.0, 0.014)],
                   r=0.0075, verts=8)
    hd.matrix_world = LM
    o.append((hd, s))
    for sx in (-1, 1):
        lg = rbox(f'hlug{sx}', (0.024, 0.026, 0.020), (sx * 0.060, 0.0, 0.012), radius=0.004, seg=1)
        lg.matrix_world = LM @ Matrix.Translation((sx * 0.060, 0.0, 0.012))
        o.append((lg, d))
    # hinge barrel
    o.append((cyl('hingepin', r=0.010, h=W * 0.62, loc=hinge, verts=10, rot=(0, D2R(90), 0)), s))

    # ---- cartridges ------------------------------------------------------------
    random.seed(4)
    for row, sy in enumerate((-0.032, 0.032)):
        for i in range(4):
            x = -0.0765 + i * 0.051
            t = D2R(random.uniform(-5, 5)), D2R(random.uniform(-5, 5)), 0
            o.append((cartridge(f'rnd{row}{i}', loc=(x, sy, 0.028), rot=t, k=1.28, verts=9), br))

    # ---- front furniture -------------------------------------------------------
    # two swing hasps, well clear of the stencil
    for sx in (-1, 1):
        o.append((rbox(f'hasp{sx}', (0.026, 0.018, 0.046), (sx * 0.072, -(D / 2 + 0.008), 0.042),
                       radius=0.004, seg=1), s))
        o.append((cyl(f'hasppin{sx}', r=0.007, h=0.040, loc=(sx * 0.072, -(D / 2 + 0.014), 0.022),
                      verts=8, rot=(0, D2R(90), 0)), d))
        for sy in (-1, 1):
            o.append((bolt(f'bl{sx}{sy}', r=0.009, h=0.007,
                           loc=(sx * 0.113, sy * (D / 2 + 0.006), -0.050),
                           rot=(D2R(-90 * sy), 0, 0)), d))
    for sy, rz in ((-1, 0.0), (1, math.pi)):
        o.append((text_mesh(f'stencil{sy}', 'AMMO', font=FONT_STENCIL, size=0.050,
                            extrude=0.005, bev=0.0015,
                            loc=(0, sy * (D / 2 + 0.008), -0.028),
                            rot=(D2R(90), 0, rz), res=1, bres=0, spacing=1.08), d))
    return o, None


# ----------------------------------------------------------------- 2. insta-kill ----

def p_instakill():
    """Stylised skull - heavy brow, deep sockets, blunt square teeth."""
    g, d, s = gold('sk_g', 5.0), gold_dark('sk_d', 6.0), gold_bright('sk_s', 7.0)
    o = []
    C, A = Vector((0, 0.020, 0.048)), Vector((0.118, 0.130, 0.132))

    def on_skull(dx, dy, dz, k=1.0):
        v = Vector((dx / A.x, dy / A.y, dz / A.z)).normalized()
        return tuple(C + Vector((v.x * A.x, v.y * A.y, v.z * A.z)) * k)

    # One welded shell - cranium, face plate, brow ridge, cheekbones and a blocky jaw -
    # then everything is cut out of it.  A hanging mandible and free-floating zygomatic
    # arches just read as loose bars at 8 m; a solid stylised skull keeps its silhouette.
    skull = uvsphere('skull', 1.0, (0, 0.020, 0.048), segs=30, rings=18,
                     scale=(0.118, 0.130, 0.132))
    # face + jaw as one tapered mass: widest at the cheekbones, narrowing to the chin
    rings = []
    for z, hw, hd, r in ((0.020, 0.090, 0.070, 0.040), (-0.060, 0.102, 0.078, 0.044),
                         (-0.100, 0.098, 0.076, 0.042), (-0.140, 0.082, 0.070, 0.034),
                         (-0.170, 0.060, 0.056, 0.026)):
        rings.append([(x, y - 0.030, zz) for x, y, zz in rounded_rect(hw, hd, r, seg=6, z=z)])
    face = loft('_face', rings, bevel=0.008, bseg=2)
    brow = uvsphere('_brow', 1.0, (0, -0.084, 0.032), segs=22, rings=12,
                    scale=(0.080, 0.020, 0.020))
    fuse(skull, [face, brow])

    cut = []
    for sx in (-1, 1):
        # tapered bores, not ball sockets: a shallow dish reads as a *bulge* at distance,
        # a deep cone with a hard rim reads as a hole
        c = cyl(f'_sock{sx}', r=0.017, h=0.090, loc=(sx * 0.052, -0.084, 0.006), verts=26,
                rot=(D2R(90), 0, 0), r_top=0.040)
        c.scale = (1.0, 0.90, 1.0)   # local Y is world Z after the 90 deg X rotation
        cut.append(c)
        # big far-away spheres shave flats onto the temples so it isn't a helmet
        cut.append(uvsphere(f'_temple{sx}', 0.30, (sx * 0.406, -0.010, 0.070), segs=40, rings=24))
    # flatten the occiput a little - a perfect egg from behind reads as a balloon
    cut.append(uvsphere('_occ', 0.32, (0, 0.456, 0.030), segs=40, rings=24))
    cut.append(profile_extrude('_nose', [(0.0, 0.028), (-0.021, -0.028), (0.021, -0.028)],
                               0.055, (0, -0.112, -0.058)))
    # the grin: a slot milled across the jaw that the teeth then sit in
    cut.append(box('_mouth', (0.124, 0.062, 0.030), (0, -0.092, -0.118)))
    # cranial sutures, milled in as grooves - raised seams on a mirror-gold dome just
    # catch a hard specular and read as fins, an engraved line reads as bone
    cut.append(pipe_path('_sutsag', [on_skull(0, -0.75, 0.66), on_skull(0, -0.35, 0.94),
                                     on_skull(0, 0.15, 1.0), on_skull(0, 0.62, 0.78),
                                     on_skull(0, 0.88, 0.47), on_skull(0, 1.0, 0.10)],
                         r=0.0062, verts=8))
    for sx in (-1, 1):
        cut.append(pipe_path(f'_sutlam{sx}', [
            on_skull(0, 0.99, 0.14), on_skull(sx * 0.26, 0.94, 0.06),
            on_skull(sx * 0.48, 0.84, -0.06), on_skull(sx * 0.66, 0.68, -0.20),
            on_skull(sx * 0.80, 0.46, -0.34)], r=0.0056, verts=8))
    carve(skull, cut)
    o.append((skull, g))

    for i in range(6):
        tx = -0.050 + i * 0.020
        o.append((rbox(f'tooth{i}', (0.0155, 0.030, 0.028), (tx, -0.098, -0.118),
                       radius=0.0035, seg=1), s))
    return o, None


# --------------------------------------------------------------- 3. double points ----

def p_doublepoints():
    """Heavy struck coin with a raised 'x2' in a recessed field."""
    g, d, s = gold('dp_g', 9.0), gold_dark('dp_d', 10.0), gold_bright('dp_s', 11.0)
    o = []
    R, T = 0.196, 0.062

    coin = cyl('coin', r=R, h=T, loc=(0, 0, 0), verts=40, rot=(D2R(90), 0, 0), bevel=0.011)
    cuts = []
    for sy in (-1, 1):
        cuts.append(cyl(f'_field{sy}', r=0.162, h=0.030,
                        loc=(0, sy * (T / 2 + 0.0150 - 0.0060), 0), verts=40, rot=(D2R(90), 0, 0)))
    carve(coin, cuts)
    o.append((coin, g))

    # inner bead ring on each face + the x2
    for sy in (-1, 1):
        y0 = sy * (T / 2 - 0.006)
        o.append((tube(f'bead{sy}', r_out=0.162, r_in=0.150, h=0.010, loc=(0, y0 + sy * 0.004, 0),
                       verts=40, rot=(D2R(90), 0, 0)), s))
        # a text line box includes the ascender/descender, so 'x2' centred on the box sits
        # visibly low - lift it onto the optical centre of the field
        o.append((text_mesh(f'x2_{sy}', 'x2', font=FONT_COOPER, size=0.215, extrude=0.014,
                            bev=0.004, loc=(0, y0, 0.030),
                            rot=(D2R(90), 0, 0 if sy < 0 else math.pi), res=2, bres=1,
                            spacing=1.02), s))
    # reeded edge
    for ob in wedge_ring('knurl', 32, 0.192, (0.016, T - 0.014, 0.012), z=0.0, axis='Y'):
        o.append((ob, s))
    return o, None


# --------------------------------------------------------------------- 4. kaboom ----

def p_nuke():
    """1950s implosion bomb, nose down, boxed tail shroud."""
    g, d, s = gold('nk_g', 13.0), gold_dark('nk_d', 14.0), gold_bright('nk_s', 15.0)
    o = []
    # fat teardrop: blunt round nose at the bottom, tapering up into the tail cone
    prof = [(0.000, -0.232), (0.056, -0.226), (0.098, -0.202), (0.124, -0.158),
            (0.139, -0.092), (0.142, -0.016), (0.137, 0.052), (0.122, 0.112),
            (0.100, 0.166), (0.076, 0.212), (0.058, 0.244), (0.056, 0.262),
            (0.000, 0.264)]
    o.append((lathe('bomb', prof, verts=28), g))

    # nose plug + a short cluster of contact fuzes
    o.append((lathe('nosecap', [(0.000, -0.264), (0.036, -0.256), (0.052, -0.240),
                                (0.054, -0.220), (0.000, -0.216)], verts=22), s))
    o.append((lathe('fuze', [(0.000, -0.320), (0.010, -0.318), (0.016, -0.310),
                             (0.018, -0.266), (0.026, -0.262), (0.026, -0.252),
                             (0.000, -0.250)], verts=14), s))

    # two banding straps, thin
    for k, (z, rr) in enumerate(((-0.140, 0.126), (0.068, 0.132))):
        o.append((tube(f'band{k}', r_out=rr + 0.006, r_in=rr - 0.016, h=0.022, loc=(0, 0, z),
                       verts=24), s))
    # rivet belt
    for i in range(12):
        a = i / 12 * TAU
        o.append((bolt(f'rv{i}', r=0.0095, h=0.006,
                       loc=(math.cos(a) * 0.1395, math.sin(a) * 0.1395, -0.098),
                       rot=(D2R(90), 0, -a)), d))

    # tail: four swept fins, no shroud - a ring or a box just reads as a bucket
    for i in range(4):
        a = i / 4 * TAU + math.pi / 4
        pts = [(0.098, 0.112), (0.206, 0.176), (0.206, 0.300), (0.048, 0.272)]
        o.append((profile_extrude(f'fin{i}', pts, 0.017, (0, 0, 0), rot=(0, 0, a),
                                  bevel=0.005, bseg=2), s))
        o.append((rbox(f'finroot{i}', (0.120, 0.030, 0.020),
                       (math.cos(a) * 0.082, math.sin(a) * 0.082, 0.124),
                       radius=0.006, seg=1, rot=(0, 0, a)), d))

    # stencil on the belly (kept short so it hugs the curve)
    for sy, rz in ((-1, 0.0), (1, math.pi)):
        o.append((text_mesh(f'warn{sy}', 'DANGER', font=FONT_STENCIL, size=0.034,
                            extrude=0.009, bev=0.0012, loc=(0, sy * 0.132, -0.030),
                            rot=(D2R(90), 0, rz), res=1, bres=0, spacing=1.04), d))
    return o, None


# ------------------------------------------------------------------ 5. carpenter ----

def p_carpenter():
    """Claw hammer standing on its handle."""
    g, d, s = gold('hm_g', 17.0), gold_dark('hm_d', 18.0), gold_bright('hm_s', 19.0)
    o = []
    # handle
    o.append((lathe('handle', [(0.000, -0.250), (0.020, -0.248), (0.029, -0.236),
                               (0.027, -0.206), (0.021, -0.150), (0.0195, -0.060),
                               (0.021, 0.010), (0.025, 0.046), (0.000, 0.052)],
                    verts=18), g))
    for i in range(3):
        z = -0.222 + i * 0.038
        o.append((torus(f'grip{i}', R=0.0238, r=0.0048, loc=(0, 0, z), major=16, minor=6), d))
    o.append((tube('ferrule', r_out=0.030, r_in=0.0215, h=0.034, loc=(0, 0, 0.030), verts=18), s))

    # head: eye block, tapered poll, chamfered striking face
    o.append((rbox('eye', (0.062, 0.064, 0.086), (0, 0, 0.068), radius=0.011, seg=2), g))
    o.append((cyl('poll', r=0.043, h=0.100, loc=(0.052, 0, 0.076), verts=20, rot=(0, D2R(90), 0),
                  bevel=0.007, r_top=0.037), g))
    o.append((lathe('face', [(0.000, 0.108), (0.034, 0.106), (0.042, 0.097), (0.042, 0.078),
                             (0.000, 0.076)], verts=20, loc=(0.104, 0, 0.076),
                    rot=(0, D2R(-90), 0)), s))

    # claw: curved wedge with a V slot cut through it
    claw_pts = [(-0.010, 0.112), (-0.060, 0.116), (-0.110, 0.104), (-0.152, 0.072),
                (-0.178, 0.028), (-0.188, -0.014), (-0.168, -0.018), (-0.156, 0.022),
                (-0.132, 0.058), (-0.100, 0.080), (-0.056, 0.086), (-0.010, 0.084)]
    claw = profile_extrude('claw', claw_pts, 0.060, (0, 0, 0), bevel=0.006, bseg=2)
    slot = profile_extrude('_slot', [(-0.210, 0.017), (-0.210, -0.017), (-0.090, 0.0)],
                           0.40, (0, 0, 0), rot=(D2R(90), 0, 0))
    carve(claw, [slot])
    o.append((claw, g))
    o.append((bolt('wedge', r=0.013, h=0.006, loc=(0, 0, 0.112), rot=(0, 0, 0)), s))
    return o, None


# ------------------------------------------------------------------ 6. fire sale ----

def p_firesale():
    """Swing price tag with a big embossed dollar sign."""
    g, d, s = gold('fs_g', 21.0), gold_dark('fs_d', 22.0), gold_bright('fs_s', 23.0)
    o = []
    pts = [(-0.112, 0.048), (0.0, 0.152), (0.112, 0.048), (0.112, -0.152), (-0.112, -0.152)]
    tag = profile_extrude('tag', pts, 0.030, (0, 0, 0), bevel=0.009, bseg=2)
    cuts = [cyl('_hole', r=0.021, h=0.10, loc=(0, 0, 0.098), verts=20, rot=(D2R(90), 0, 0))]
    inner = [(x * 0.84, z * 0.84 + 0.006) for x, z in pts]
    for sy in (-1, 1):
        cuts.append(profile_extrude(f'_panel{sy}', inner, 0.020,
                                    (0, sy * (0.015 + 0.010 - 0.005), 0)))
    carve(tag, cuts)
    o.append((tag, g))

    o.append((tube('grommet', r_out=0.033, r_in=0.021, h=0.038, loc=(0, 0, 0.098), verts=20,
                   rot=(D2R(90), 0, 0)), s))
    o.append((torus('ring', R=0.046, r=0.0085, loc=(0, 0, 0.136), rot=(D2R(90), 0, 0),
                    major=20, minor=7), s))

    for sy, rz in ((-1, 0.0), (1, math.pi)):
        y0 = sy * 0.010
        o.append((text_mesh(f'dollar{sy}', '$', font=FONT_COOPER, size=0.215, extrude=0.018,
                            bev=0.0035, loc=(0, y0, 0.004), rot=(D2R(90), 0, rz),
                            res=2, bres=0), s))
        o.append((text_mesh(f'sale{sy}', 'SALE', font=FONT_STENCIL, size=0.042, extrude=0.006,
                            bev=0.0012, loc=(0, y0, -0.126), rot=(D2R(90), 0, rz),
                            res=1, bres=0, spacing=1.10), d))
    # corner studs
    for sx in (-1, 1):
        o.append((bolt(f'stud{sx}', r=0.010, h=0.006, loc=(sx * 0.088, -0.016, -0.128),
                       rot=(D2R(-90), 0, 0)), d))
        o.append((bolt(f'studb{sx}', r=0.010, h=0.006, loc=(sx * 0.088, 0.016, -0.128),
                       rot=(D2R(90), 0, 0)), d))
    return o, Matrix.Rotation(D2R(13), 4, 'Y')


BUILDERS = {
    'maxammo': p_maxammo, 'instakill': p_instakill, 'doublepoints': p_doublepoints,
    'nuke': p_nuke, 'carpenter': p_carpenter, 'firesale': p_firesale,
}
ORDER = ['maxammo', 'instakill', 'doublepoints', 'nuke', 'carpenter', 'firesale']


def build_one(pid, render=True, export=True, tex=1024):
    props_scene()
    random.seed(hash(pid) % 9999)
    objs_mats, post = BUILDERS[pid]()
    objs = []
    for ob, mat in objs_mats:
        assign(ob, mat)
        objs.append(ob)

    apply_mods(objs)
    for ob in objs:
        shade_smooth(ob, 42)
    print('  pre-bake tris:', tri_count())
    mat = bake_pbr(objs, f'pu_{pid}', size=tex, samples=4, normal_samples=6, margin=0.004)
    regrade(mat)

    root = join(f'pu_{pid}', objs)
    dim = center_and_fit(root, TARGET, post)
    print(f'  {pid}: tris {tri_count()}  size {dim.x:.3f} x {dim.y:.3f} x {dim.z:.3f} m')

    if render:
        pu_shots(f'pu_{pid}', size=TARGET)
    if export:
        export_prop(f'pu_{pid}.glb', roots=[root], quality=84)
    return root


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if args and args[0] == 'lineup':
        ids = args[1:] or ORDER
        lineup(ids, os.path.join(PROPS_RENDERS, 'pu_lineup.png'), yaw_each=30)
        return
    ids = args or ORDER
    if len(ids) > 1:
        # re-initialising the scene after a Cycles GPU render in the same process can take
        # Blender down, so each power-up gets its own process
        import subprocess
        for pid in ids:
            print('=== spawning', pid)
            rc = subprocess.call([bpy.app.binary_path, '-b', '--factory-startup',
                                  '--python', os.path.abspath(__file__), '--', pid])
            if rc != 0:
                print('  FAILED', pid, 'rc', rc)
        subprocess.call([bpy.app.binary_path, '-b', '--factory-startup',
                         '--python', os.path.abspath(__file__), '--', 'lineup'])
        return
    print('=== building', ids[0])
    build_one(ids[0])


main()
