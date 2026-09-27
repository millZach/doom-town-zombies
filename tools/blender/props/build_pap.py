"""pap_machine.glb - Pack-a-Punch machine, 2.0 w x 1.1 d x 1.9 h.

Origin: floor centre, front = -Y.  Heavy 1960s lab/industrial plant: riveted steel
chassis, transformer can, ceramic insulators, pressure gauges, conduit, hazard
stripes and a feed aperture where the gun goes in.

Two emissive materials (environment.md #1d, same split as the perk machines):
  `pap_sign_glow`  the big modest surfaces - the ember throat behind the rollers and
                   the control-box screen (authored 1.2);
  `pap_trim_glow`  the four indicator lamps and the beacon (authored 3.0).

Objects:
  machine  - everything static (includes the emissive parts)
  rollers  - the knurled feed drum inside the aperture; its origin is on the drum
             axis, so rotating it about its local X spins it in place.
"""
import sys, os, math, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib_props import *

random.seed(77)

HW, HD = 0.900, 0.520          # half width / half depth of the chassis
FY = -HD                       # front plane
APZ = 0.880                    # aperture centre height
ROLL_Z = APZ + 0.128
ROLL_Y = FY - 0.058


def knurled_drum(name, r, half_len, loc, teeth=20):
    """Cylinder along X with a ribbed surface."""
    bm = bmesh.new()
    rings = []
    for k in range(teeth * 2):
        a = k / (teeth * 2) * TAU
        rr = r if k % 2 == 0 else r * 0.93
        rings.append((math.cos(a) * rr, math.sin(a) * rr))
    for sx in (-half_len, half_len):
        vs = [bm.verts.new((sx, y, z)) for y, z in rings]
        bm.faces.new(vs if sx > 0 else vs[::-1])
    bm.verts.ensure_lookup_table()
    n = len(rings)
    a_ring = [bm.verts.new((-half_len, y, z)) for y, z in rings]
    b_ring = [bm.verts.new((half_len, y, z)) for y, z in rings]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([a_ring[i], a_ring[j], b_ring[j], b_ring[i]])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(name, bm, loc)


def build():
    props_scene()

    olive = painted('pap_olive', (0.042, 0.048, 0.034), rough=0.40, wear=0.42, rust=0.70,
                    grime=0.85, dent=0.95, scale=1.0, seed=1.0, variation=0.14, dust=0.10,
                    streak=0.85)
    olive2 = painted('pap_olive2', (0.062, 0.068, 0.050), rough=0.42, wear=0.40, rust=0.66,
                     grime=0.82, dent=0.9, scale=1.0, seed=4.0, variation=0.14, dust=0.10,
                     streak=0.80)
    rawsteel = weathered('pap_steel', color=(0.105, 0.100, 0.096), roughness=0.46, metallic=1.0,
                         wear_color=(0.42, 0.41, 0.40), wear=0.35, wear_rough=0.28,
                         rust=0.80, rust_color=(0.255, 0.110, 0.042), grime=0.75, dust=0.10,
                         variation=0.10, scale=2.0, seed=7.0, bump=0.7, dent=0.6,
                         scratch=1.0, speckle=0.15, streak=0.7)
    bright = chrome('pap_bright', tint=(0.60, 0.60, 0.62), rough=0.22, grime=0.60,
                    scratch=1.0, pit=1.0, scale=2.0, seed=11.0)
    brassm = weathered('pap_brass', color=(0.430, 0.300, 0.075), roughness=0.32, metallic=1.0,
                       wear_color=(0.60, 0.46, 0.20), wear=0.30, wear_rough=0.22,
                       rust=0.28, rust_color=(0.10, 0.155, 0.095), grime=0.65, dust=0.08,
                       variation=0.09, scale=2.5, seed=13.0, bump=0.5, dent=0.4,
                       scratch=0.9, speckle=0.15, streak=0.5)
    copperm = weathered('pap_copper', color=(0.330, 0.128, 0.052), roughness=0.34, metallic=1.0,
                        wear_color=(0.52, 0.29, 0.14), wear=0.30, wear_rough=0.25,
                        rust=0.50, rust_color=(0.072, 0.180, 0.140), grime=0.65, dust=0.08,
                        variation=0.10, scale=2.5, seed=17.0, bump=0.5, dent=0.4,
                        scratch=0.9, speckle=0.15, streak=0.5)
    hazard = painted('pap_hazard', (0.420, 0.270, 0.018), rough=0.44, wear=0.50, rust=0.45,
                     grime=0.78, dent=0.4, scale=2.0, seed=19.0, variation=0.12, dust=0.10,
                     streak=0.7)
    dark = weathered('pap_dark', color=(0.011, 0.011, 0.010), roughness=0.62, metallic=0.0,
                     wear=0.12, rust=0.0, grime=0.5, dust=0.05, variation=0.05, scale=2.0,
                     seed=23.0, bump=0.4, speckle=0.12)
    rubber = weathered('pap_rubber', color=(0.020, 0.019, 0.018), roughness=0.84, metallic=0.0,
                       wear=0.12, rust=0.0, grime=0.55, dust=0.08, variation=0.08, scale=3.0,
                       seed=29.0, bump=0.6, speckle=0.2)
    porcelain = weathered('pap_porc', color=(0.185, 0.130, 0.095), roughness=0.16, metallic=0.0,
                          wear_color=(0.40, 0.33, 0.26), wear=0.20, wear_rough=0.5,
                          wear_metal=0.0, rust=0.0, grime=0.55, dust=0.16, variation=0.08,
                          scale=3.0, seed=31.0, bump=0.3, speckle=0.12, streak=0.4)
    glassm = weathered('pap_glass', color=(0.28, 0.29, 0.30), roughness=0.08, metallic=0.0,
                       wear=0.08, rust=0.0, grime=0.40, dust=0.28, variation=0.05, scale=3.0,
                       seed=37.0, bump=0.2, speckle=0.1)
    glow_orange = weathered('pap_glow_o', color=(0.95, 0.42, 0.06), roughness=0.25, metallic=0.0,
                            wear=0.0, rust=0.0, grime=0.0, dust=0.06, variation=0.06,
                            scale=4.0, seed=41.0, bump=0.2, speckle=0.1)
    glow_green = weathered('pap_glow_g', color=(0.16, 0.86, 0.28), roughness=0.25, metallic=0.0,
                           wear=0.05, rust=0.0, grime=0.28, grime_color=(0.04, 0.08, 0.04),
                           dust=0.14, variation=0.06, scale=4.0, seed=43.0, bump=0.2,
                           speckle=0.1)
    # the element deep in the throat: mottled hot metal, not a lightbox panel.  High
    # variation + speckle break it up so it never bakes as a flat clipped slab.
    glow_coal = weathered('pap_glow_c', color=(0.700, 0.185, 0.026), roughness=0.58,
                          metallic=0.0, wear=0.0, rust=0.0, grime=0.0, dust=0.0,
                          variation=0.42, scale=6.0, seed=53.0, bump=0.55, speckle=0.45)
    glow_ember = weathered('pap_glow_e', color=(0.620, 0.150, 0.022), roughness=0.55,
                           metallic=0.0, wear=0.0, rust=0.0, grime=0.0,
                           dust=0.0, variation=0.28, scale=5.0, seed=51.0,
                           bump=0.5, speckle=0.35)
    glow_red = weathered('pap_glow_r', color=(0.92, 0.10, 0.05), roughness=0.25, metallic=0.0,
                         wear=0.05, rust=0.0, grime=0.28, grime_color=(0.08, 0.03, 0.03),
                         dust=0.14, variation=0.06, scale=4.0, seed=47.0, bump=0.2, speckle=0.1)

    solid, glow, trim, rollers = [], [], [], []

    def S(ob, mat):
        assign(ob, mat); solid.append(ob); return ob

    def G(ob, mat):
        assign(ob, mat); glow.append(ob); return ob

    def T(ob, mat):
        assign(ob, mat); trim.append(ob); return ob

    def R(ob, mat):
        assign(ob, mat); rollers.append(ob); return ob

    # ------------------------------------------------------------- chassis ----
    S(rbox('plinth', (2 * HW + 0.08, 2 * HD + 0.06, 0.150), (0, 0, 0.075), radius=0.014, seg=2),
      rawsteel)
    S(rbox('body', (2 * HW, 2 * HD, 1.140), (0, 0, 0.720), radius=0.040, seg=2), olive)
    S(rbox('deck', (2 * HW - 0.10, 2 * HD - 0.06, 0.190), (0, 0, 1.385), radius=0.022, seg=2),
      olive2)
    S(rbox('decklip', (2 * HW + 0.02, 2 * HD + 0.02, 0.048), (0, 0, 1.306), radius=0.010, seg=2),
      rawsteel)

    # welded seam ribs + rivets round the chassis
    for zz in (0.310, 0.760, 1.190):
        S(rbox(f'rib{zz}', (2 * HW + 0.030, 2 * HD + 0.030, 0.052), (0, 0, zz),
               radius=0.008, seg=2), olive2)
        for i in range(6):
            x = -HW + 0.12 + i * (2 * HW - 0.24) / 5
            S(bolt(f'rvf{zz}{i}', r=0.016, h=0.010, loc=(x, FY - 0.030, zz),
                   rot=(D2R(-90), 0, 0), washer=True), rawsteel)
    for sx in (-1, 1):
        for i in range(3):
            y = -HD + 0.22 + i * (2 * HD - 0.44) / 2
            S(bolt(f'rvs{sx}{i}', r=0.016, h=0.010, loc=(sx * (HW + 0.030), y, 1.190),
                   rot=(0, D2R(90 * sx), 0), washer=True), rawsteel)

    # feet
    for sx in (-1, 1):
        for sy in (-1, 1):
            S(cyl(f'foot{sx}{sy}', r=0.075, h=0.070, loc=(sx * 0.740, sy * 0.400, 0.035),
                  verts=12), rawsteel)

    # ------------------------------------------------------------ aperture ----
    AW, AH = 0.560, 0.380
    # The surround is a FRAME, not a slab: built solid it capped the recess 36 mm behind
    # the bezel, so the "aperture" was a flat dark plate and the ember throat and rollers
    # behind it were never visible.  Four pieces leaving an AW x AH hole give a real
    # 100 mm deep glowing throat.
    APF = 0.115                        # frame limb width
    for nm, sz, lc in (
            ('ap_sur_t', (AW + 0.230, 0.080, APF), (0, FY - 0.030, APZ + AH / 2 + APF / 2)),
            ('ap_sur_b', (AW + 0.230, 0.080, APF), (0, FY - 0.030, APZ - AH / 2 - APF / 2)),
            ('ap_sur_l', (APF, 0.080, AH + 0.020), (-(AW / 2 + APF / 2), FY - 0.030, APZ)),
            ('ap_sur_r', (APF, 0.080, AH + 0.020), (AW / 2 + APF / 2, FY - 0.030, APZ))):
        S(rbox(nm, sz, lc, radius=0.012, seg=2), olive2)
    for nm, sz, lc in (
            ('ap_t', (AW + 0.150, 0.110, 0.075), (0, FY - 0.052, APZ + AH / 2 + 0.038)),
            ('ap_b', (AW + 0.150, 0.110, 0.075), (0, FY - 0.052, APZ - AH / 2 - 0.038)),
            ('ap_l', (0.075, 0.110, AH - 0.002), (-(AW / 2 + 0.038), FY - 0.052, APZ)),
            ('ap_r', (0.075, 0.110, AH - 0.002), (AW / 2 + 0.038, FY - 0.052, APZ))):
        S(rbox(nm, sz, lc, radius=0.012, seg=2), bright)
    # dark throat (the back of the recess) + emissive slot behind the rollers
    G(rbox('ap_throat', (AW + 0.02, 0.016, AH + 0.02), (0, FY - 0.006, APZ), radius=0.004,
           seg=1), glow_ember)
    for sz in (-1, 1):                       # side walls of the recess
        G(rbox(f'ap_wall{sz}', (0.020, 0.100, AH), (sz * (AW / 2 - 0.010), FY - 0.056, APZ),
               radius=0.003, seg=1), glow_ember)
        G(rbox(f'ap_walh{sz}', (AW, 0.100, 0.020), (0, FY - 0.056, APZ + sz * (AH / 2 - 0.010)),
               radius=0.003, seg=1), glow_ember)
    G(rbox('ap_inner', (AW - 0.22, 0.012, 0.062), (0, FY - 0.022, APZ - 0.026), radius=0.004,
           seg=1), glow_coal)
    # rubber lips top & bottom of the mouth
    for sz in (-1, 1):
        S(rbox(f'ap_lip{sz}', (AW - 0.02, 0.055, 0.028),
               (0, FY - 0.085, APZ + sz * (AH / 2 - 0.020)), radius=0.006, seg=1), rubber)
    # bolts around the bezel
    for i in range(4):
        for sz in (-1, 1):
            x = -0.270 + i * 0.180
            S(bolt(f'apb{i}{sz}', r=0.014, h=0.009,
                   loc=(x, FY - 0.110, APZ + sz * (AH / 2 + 0.038)), rot=(D2R(-90), 0, 0)),
              bright)

    # ------------------------------------------------------ feed roller ----
    R(knurled_drum('roller_main', 0.070, AW / 2 - 0.040, (0, ROLL_Y, ROLL_Z), teeth=18),
      bright)
    for sx in (-1, 1):
        R(cyl(f'roller_end{sx}', r=0.050, h=0.055, loc=(sx * (AW / 2 - 0.010), ROLL_Y, ROLL_Z),
              verts=12, rot=(0, D2R(90), 0)), rawsteel)
        R(cyl(f'roller_hub{sx}', r=0.024, h=0.100, loc=(sx * (AW / 2 + 0.040), ROLL_Y, ROLL_Z),
              verts=10, rot=(0, D2R(90), 0)), rawsteel)
    # static lower roller + bearing blocks belong to the machine
    S(knurled_drum('roller_low', 0.052, AW / 2 - 0.040, (0, ROLL_Y, APZ - 0.128), teeth=14),
      rawsteel)
    for sx in (-1, 1):
        S(rbox(f'bearing{sx}', (0.034, 0.110, 0.330), (sx * (AW / 2 - 0.016), ROLL_Y, APZ),
               radius=0.008, seg=1), rawsteel)

    # ------------------------------------------------------- front fittings ----
    # hazard stripe plate under the aperture
    S(rbox('hz_plate', (1.260, 0.024, 0.145), (0, FY - 0.012, 0.455), radius=0.006, seg=1),
      hazard)
    for i in range(10):
        S(rbox(f'hz{i}', (0.055, 0.014, 0.150), (-0.560 + i * 0.124, FY - 0.026, 0.455),
               radius=0.002, seg=1, rot=(0, D2R(36), 0)), dark)
    # name plate above the aperture
    S(rbox('nameplate', (1.180, 0.024, 0.160), (0, FY - 0.014, 1.190), radius=0.006, seg=1),
      brassm)
    S(text_mesh('name_txt', 'PACK-A-PUNCH', font=FONT_ARIALBD, size=0.098, extrude=0.008,
                bev=0.0018, loc=(0, FY - 0.032, 1.190), res=2, bres=1, spacing=1.10), dark)

    # gauges on the left
    for i, gx in enumerate((-0.640, -0.640)):
        gz = 0.980 if i == 0 else 0.700
        S(cyl(f'g_can{i}', r=0.115, h=0.075, loc=(gx, FY - 0.028, gz), verts=22,
              rot=(D2R(90), 0, 0)), brassm)
        S(cyl(f'g_face{i}', r=0.098, h=0.014, loc=(gx, FY - 0.056, gz), verts=22,
              rot=(D2R(90), 0, 0)), porcelain)
        S(rbox(f'g_needle{i}', (0.006, 0.008, 0.082), (gx + 0.024 * (1 if i else -1),
                                                       FY - 0.066, gz + 0.028),
               radius=0.001, seg=1, rot=(0, D2R(-32 if i else 24), 0)), glow_red)
        S(tube(f'g_ring{i}', r_out=0.114, r_in=0.096, h=0.024, loc=(gx, FY - 0.062, gz),
               verts=22, rot=(D2R(90), 0, 0)), bright)
        for k in range(7):
            a = D2R(-150 + k * 20)
            S(rbox(f'g_t{i}{k}', (0.005, 0.005, 0.018),
                   (gx + math.cos(a) * 0.078, FY - 0.060, gz + math.sin(a) * 0.078),
                   radius=0.001, seg=1, rot=(0, -a - D2R(90), 0)), dark)

    # hand wheel on the right
    S(cyl('wheel_shaft', r=0.028, h=0.180, loc=(0.640, FY - 0.090, 0.820), verts=10,
          rot=(D2R(90), 0, 0)), rawsteel)
    S(tube('wheel_rim', r_out=0.170, r_in=0.142, h=0.040, loc=(0.640, FY - 0.176, 0.820),
           verts=24, rot=(D2R(90), 0, 0)), rawsteel)
    for i in range(4):
        a = i / 4 * TAU
        S(rbox(f'spoke{i}', (0.026, 0.028, 0.160),
               (0.640 + math.cos(a) * 0.078, FY - 0.176, 0.820 + math.sin(a) * 0.078),
               radius=0.004, seg=1, rot=(0, -a + D2R(90), 0)), rawsteel)
    S(cyl('wheel_hub', r=0.048, h=0.060, loc=(0.640, FY - 0.176, 0.820), verts=12,
          rot=(D2R(90), 0, 0)), brassm)

    # lamp row under the name plate
    for i, mat in enumerate((glow_red, glow_orange, glow_green, glow_orange)):
        lx = -0.345 + i * 0.230
        S(cyl(f'lb{i}', r=0.052, h=0.046, loc=(lx, FY - 0.028, 1.320), verts=14,
              rot=(D2R(90), 0, 0), r_top=0.046), brassm)
        T(uvsphere(f'lamp{i}', r=0.038, loc=(lx, FY - 0.052, 1.320), segs=14, rings=8,
                   scale=(1, 0.7, 1)), mat)

    # vent grille low on the front
    for i in range(5):
        S(rbox(f'vent{i}', (1.100, 0.020, 0.024), (0, FY - 0.008, 0.196 + i * 0.048),
               radius=0.002, seg=1), dark)

    # ---------------------------------------------------------- upper works ----
    # transformer can, left
    S(cyl('tx_can', r=0.270, h=0.420, loc=(-0.480, 0.030, 1.690), verts=26, bevel=0.020),
      rawsteel)
    S(tube('tx_band', r_out=0.286, r_in=0.262, h=0.040, loc=(-0.480, 0.030, 1.600), verts=26),
      rawsteel)
    S(cyl('tx_lid', r=0.230, h=0.060, loc=(-0.480, 0.030, 1.920), verts=26, bevel=0.012),
      rawsteel)
    for i in range(10):                      # cooling fins
        a = i / 10 * TAU
        S(rbox(f'fin{i}', (0.020, 0.090, 0.330),
               (-0.480 + math.cos(a) * 0.310, 0.030 + math.sin(a) * 0.310, 1.680),
               radius=0.003, seg=1, rot=(0, 0, -a + D2R(90))), rawsteel)
    # ceramic insulators on the lid
    for sx in (-1, 1):
        S(lathe(f'ins{sx}', [(0.0, 0.0), (0.056, 0.006), (0.038, 0.022), (0.060, 0.040),
                             (0.038, 0.058), (0.058, 0.076), (0.036, 0.094), (0.030, 0.118),
                             (0.0, 0.124)], verts=14,
                loc=(-0.480 + sx * 0.110, 0.030, 1.948)), porcelain)
        S(cyl(f'inscap{sx}', r=0.024, h=0.026, loc=(-0.480 + sx * 0.110, 0.030, 2.072),
              verts=10), copperm)

    # control box, right
    S(rbox('ctrlbox', (0.640, 0.520, 0.380), (0.520, 0.010, 1.670), radius=0.024, seg=2), olive2)
    S(rbox('ctrlface', (0.560, 0.030, 0.310), (0.520, -0.256, 1.670), radius=0.010, seg=2),
      rawsteel)
    G(rbox('ctrlscreen', (0.300, 0.014, 0.150), (0.440, -0.278, 1.712), radius=0.006, seg=1),
      glow_green)
    for i in range(5):
        S(rbox(f'scanline{i}', (0.300, 0.008, 0.008), (0.440, -0.288, 1.762 - i * 0.026),
               radius=0.001, seg=1), dark)
    for i in range(4):
        S(cyl(f'knob{i}', r=0.034, h=0.044, loc=(0.330 + i * 0.110, -0.286, 1.578), verts=12,
              rot=(D2R(90), 0, 0), r_top=0.028), brassm)
    S(rbox('ctrllid', (0.680, 0.560, 0.045), (0.520, 0.010, 1.880), radius=0.010, seg=2),
      rawsteel)
    # beacon
    S(cyl('beacon_base', r=0.075, h=0.055, loc=(0.520, 0.010, 1.930), verts=16), rawsteel)
    T(lathe('beacon', [(0.0, 0.0), (0.070, 0.010), (0.076, 0.052), (0.058, 0.086),
                       (0.0, 0.100)], verts=18, loc=(0.520, 0.010, 1.955)), glow_red)
    S(tube('beacon_cage', r_out=0.082, r_in=0.074, h=0.090, loc=(0.520, 0.010, 1.995), verts=16),
      rawsteel)

    # ------------------------------------------------------------- plumbing ----
    S(pipe_path('pipe_l', [(-0.830, 0.300, 0.300), (-0.830, 0.300, 1.240),
                           (-0.790, 0.260, 1.340), (-0.620, 0.120, 1.420),
                           (-0.520, 0.060, 1.520)], r=0.052, verts=10), copperm)
    S(pipe_path('pipe_r', [(0.850, 0.330, 0.240), (0.850, 0.330, 1.180),
                           (0.820, 0.280, 1.300), (0.700, 0.150, 1.420),
                           (0.600, 0.090, 1.500)], r=0.046, verts=10), rawsteel)
    for z in (0.560, 0.980):
        S(tube(f'flange_l{z}', r_out=0.082, r_in=0.050, h=0.040, loc=(-0.830, 0.300, z),
               verts=14), brassm)
        S(tube(f'flange_r{z}', r_out=0.076, r_in=0.044, h=0.040, loc=(0.850, 0.330, z),
               verts=14), brassm)
    # valve on the left pipe
    S(tube('valve_rim', r_out=0.098, r_in=0.078, h=0.026, loc=(-0.830, 0.300, 0.780),
           verts=18, rot=(0, D2R(90), 0)), brassm)
    S(cyl('valve_stem', r=0.020, h=0.120, loc=(-0.900, 0.300, 0.780), verts=8,
          rot=(0, D2R(90), 0)), brassm)
    # conduit across the front top
    S(pipe_path('conduit', [(-0.830, FY - 0.014, 0.640), (-0.830, FY - 0.014, 0.300),
                            (-0.860, -0.150, 0.220), (-0.910, 0.150, 0.200)],
                r=0.028, verts=8), rawsteel)
    for z in (0.60, 0.36):
        S(tube(f'clip{z}', r_out=0.042, r_in=0.028, h=0.024, loc=(-0.830, FY - 0.014, z),
               verts=10), rawsteel)

    S(pipe_path('mains_cable', [(0.560, FY - 0.020, 0.230), (0.640, FY - 0.120, 0.150),
                                (0.820, FY - 0.230, 0.075), (1.060, FY - 0.180, 0.048),
                                (1.260, FY + 0.050, 0.046)], r=0.036, verts=8), rubber)
    S(tube('cable_gland', r_out=0.058, r_in=0.036, h=0.050, loc=(0.560, FY - 0.012, 0.230),
           verts=12, rot=(D2R(90), 0, 0)), brassm)

    # side hazard chevrons
    for sx in (-1, 1):
        S(rbox(f'sidehz{sx}', (0.022, 0.700, 0.140), (sx * (HW + 0.012), 0.080, 0.980),
               radius=0.004, seg=1), hazard)
        for i in range(5):
            S(rbox(f'sidehzs{sx}{i}', (0.014, 0.056, 0.145),
                   (sx * (HW + 0.024), -0.230 + i * 0.136, 0.980), radius=0.002, seg=1,
                   rot=(D2R(38), 0, 0)), dark)

    # ---------------------------------------------------------------- bake ----
    apply_mods(solid + glow + trim + rollers)
    print('  pre-bake tris:', tri_count())
    heavy = sorted(((tri_count([o]), o.name) for o in solid + glow + trim + rollers),
                   reverse=True)[:8]
    print('  heaviest:', ', '.join(f'{n}={t}' for t, n in heavy))
    bake_pbr(solid, 'pap_body', size=1536, samples=4, normal_samples=6, margin=0.0026)
    bake_pbr(rollers, 'pap_rollers', size=512, samples=4, normal_samples=6, margin=0.006)
    # 1024 + a 20 px island margin: at 512/0.008 the green control screen bled into the
    # ember throat islands and put green pixels in the aperture corners
    bake_pbr(glow, 'pap_glowtex', size=1024, samples=4, normal_samples=6, margin=0.020,
             emissive=True, emission_strength=1.2, mat_name='pap_sign_glow')
    bake_pbr(trim, 'pap_trimtex', size=512, samples=4, normal_samples=6, margin=0.016,
             emissive=True, emission_strength=3.0, mat_name='pap_trim_glow')

    machine = join('machine', solid + glow + trim)
    set_origin(machine, (0, 0, 0))
    roll = join('rollers', rollers)
    set_origin(roll, (0, ROLL_Y, ROLL_Z))

    print('  tris:', tri_count())
    shots('pap_machine', target=(0, 0, 0.95), hero=(4.2, 34, 10), close=(1.30, 14, -2),
          close_target=(0, -0.45, 0.90), samples=30, res=(860, 660), world=0.5)
    export_prop('pap_machine.glb', roots=[machine, roll], quality=78)


build()
