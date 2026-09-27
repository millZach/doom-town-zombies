"""Build public/models/hellhound.glb - a burned, emaciated dog.

    blender.exe -b --factory-startup --python tools/blender/characters/build_hellhound.py -- [opts]
        --fast --force-bake --stills --sheets

Rebuilt for review item #9.  The previous hound was "a lava-cracked giraffe": barrel far
too long, stilt legs with no angulation, an undersized head, a wire tail, no paws, and a
uniform Voronoi magma crack over the whole body that read as an obsidian golem.  This one
is a compact, deep-chested, short-legged dog: real canine angulation front and rear, paws
with toes and claws, a muzzle with a stop and a nose leather, lips drawn back off the
canines, pinned-back ears with thickness, a matted ruff of fur clumps over the shoulders
and spine, exposed ribs on one flank, and fire that only shows in the deep creases.
"""
import sys, os, math, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, HERE)

import bpy, bmesh, random
from mathutils import Vector, Matrix, Euler
from common import reset_scene, MODELS_DIR, RENDERS_DIR, setup_gpu
import lib_char as L
import zombie_mat as MAT
import zombie_anim as ZA

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
FAST = '--fast' in ARGS
FORCE_BAKE = '--force-bake' in ARGS
STILLS = '--stills' in ARGS
SHEETS = '--sheets' in ARGS
BAKE_VERSION = 'v5'
OUT = os.path.join(MODELS_DIR, 'hellhound.glb')
RDIR = os.path.join(RENDERS_DIR, 'characters')
os.makedirs(RDIR, exist_ok=True)
DEG = math.radians
T0 = time.time()
V = Vector
TAU = math.tau


def log(*a):
    print('[hound %6.1fs]' % (time.time() - T0), *a)


# =======================================================================================
# skeleton
# =======================================================================================
FWD = (0, -1, 0)
UP = (0, 0, 1)

J = {
    'root':    V((0.000, 0.000, 0.000)),
    'hips':    V((0.000, 0.235, 0.600)),
    'spine':   V((0.000, 0.060, 0.625)),
    'chest':   V((0.000, -0.160, 0.640)),
    'neck':    V((0.000, -0.330, 0.695)),
    'head':    V((0.000, -0.470, 0.768)),
    'headtip': V((0.000, -0.658, 0.744)),
    'jaw':     V((0.000, -0.524, 0.726)),
    'jawtip':  V((0.000, -0.656, 0.702)),
    'tail1':   V((0.000, 0.300, 0.630)),
    'tail2':   V((0.000, 0.410, 0.560)),
    'tail3':   V((0.000, 0.492, 0.462)),
    'tailtip': V((0.000, 0.536, 0.352)),
}
SIDE = {
    # front: shoulder -> elbow (BACK) -> carpus (forward) -> paw.
    'fleg1_L': V((0.098, -0.205, 0.600)),
    'fleg2_L': V((0.104, -0.152, 0.378)),
    'fleg3_L': V((0.104, -0.230, 0.152)),
    'fpaw_L':  V((0.104, -0.250, 0.040)),
    'ftoe_L':  V((0.104, -0.318, 0.022)),
    # hind: hip -> stifle (well FORWARD and high) -> hock (well BACK and low) -> paw.
    # The previous table put the stifle only 94 mm forward of the hip and the hock 32 mm
    # behind it, so hip-to-hock was 0.436 m against a 0.478 m chain: the IK straightened
    # it and the hind legs read as stilts.  It is now 0.428 against 0.532.
    'hleg1_L': V((0.100, 0.232, 0.585)),
    'hleg2_L': V((0.106, 0.100, 0.400)),
    'hleg3_L': V((0.106, 0.300, 0.170)),
    'hpaw_L':  V((0.106, 0.215, 0.040)),
    'htoe_L':  V((0.106, 0.148, 0.022)),
}
for k, v in list(SIDE.items()):
    J[k] = v
    J[k[:-2] + '_R'] = V((-v.x, v.y, v.z))

SKELETON = {
    'root':  (None, J['root'], J['root'] + V((0, -0.14, 0)), UP),
    'hips':  ('root', J['hips'], J['spine'], UP),
    'spine': ('hips', J['spine'], J['chest'], UP),
    'chest': ('spine', J['chest'], J['neck'], UP),
    'neck':  ('chest', J['neck'], J['head'], UP),
    'head':  ('neck', J['head'], J['headtip'], UP),
    'jaw':   ('head', J['jaw'], J['jawtip'], UP),
    'tail_1': ('hips', J['tail1'], J['tail2'], UP),
    'tail_2': ('tail_1', J['tail2'], J['tail3'], UP),
    'tail_3': ('tail_2', J['tail3'], J['tailtip'], UP),
}
for s in ('L', 'R'):
    SKELETON['fleg1_' + s] = ('chest', J['fleg1_' + s], J['fleg2_' + s], FWD)
    SKELETON['fleg2_' + s] = ('fleg1_' + s, J['fleg2_' + s], J['fleg3_' + s], FWD)
    SKELETON['fleg3_' + s] = ('fleg2_' + s, J['fleg3_' + s], J['fpaw_' + s], FWD)
    SKELETON['fpaw_' + s] = ('fleg3_' + s, J['fpaw_' + s], J['ftoe_' + s], UP)
    SKELETON['hleg1_' + s] = ('hips', J['hleg1_' + s], J['hleg2_' + s], FWD)
    SKELETON['hleg2_' + s] = ('hleg1_' + s, J['hleg2_' + s], J['hleg3_' + s], FWD)
    SKELETON['hleg3_' + s] = ('hleg2_' + s, J['hleg3_' + s], J['hpaw_' + s], FWD)
    SKELETON['hpaw_' + s] = ('hleg3_' + s, J['hpaw_' + s], J['htoe_' + s], UP)

FRONT_META = (J['fpaw_L'] - J['fleg3_L']).length
HIND_META = (J['hpaw_L'] - J['hleg3_L']).length
JAW_PIVOT = V((0.0, -0.520, 0.742))
JAW_OPEN = math.radians(9.0)


def jaw_rot(p):
    r = V(p) - JAW_PIVOT
    c, s = math.cos(JAW_OPEN), math.sin(JAW_OPEN)
    return JAW_PIVOT + V((r.x, r.y * c - r.z * s, r.y * s + r.z * c))


# =======================================================================================
# mesh
# =======================================================================================
def ring_xz(y, hw, hh, zc, n=22, exp=2.2):
    p = 2.0 / exp - 1.0
    pts = []
    for i in range(n):
        a = TAU * i / n
        ca, sa = math.cos(a), math.sin(a)
        sx = 0.0 if abs(ca) < 1e-9 else abs(ca) ** p
        sz = 0.0 if abs(sa) < 1e-9 else abs(sa) ** p
        pts.append(V((ca * sx * hw, y, zc + sa * sz * hh)))
    return pts


# (y, half width, half height, z centre).  Shorter by ~20%, chest 25% wider and far
# deeper, with a real belly tuck between the ribcage and the loin.
TORSO = [
    (-0.336, 0.070, 0.088, 0.690),
    (-0.292, 0.116, 0.162, 0.658),
    (-0.226, 0.146, 0.210, 0.620),
    (-0.130, 0.142, 0.206, 0.614),
    (-0.028, 0.113, 0.166, 0.630),
    (0.072, 0.109, 0.152, 0.642),
    (0.168, 0.130, 0.176, 0.628),
    (0.252, 0.138, 0.182, 0.610),
    (0.312, 0.110, 0.142, 0.598),
    (0.356, 0.058, 0.074, 0.592),
]


def torso_top(y):
    for a, b in zip(TORSO, TORSO[1:]):
        if a[0] <= y <= b[0]:
            t = (y - a[0]) / (b[0] - a[0])
            hh = a[2] + (b[2] - a[2]) * t
            zc = a[3] + (b[3] - a[3]) * t
            return zc + hh
    return TORSO[0][3] + TORSO[0][2]


def build_head():
    """Skull, muzzle with a stop, nose leather, drawn-back lips, brow, pinned ears."""
    parts = []
    parts.append(L.uv_sphere('_skull', (0, -0.500, 0.778), (0.067, 0.076, 0.065), 24, 18))
    # cheek / masseter mass, so the head is not a ball on a tube
    for sx in (1, -1):
        parts.append(L.uv_sphere('_masseter%d' % sx, (0.052 * sx, -0.478, 0.742),
                                 (0.026, 0.040, 0.034), 14, 10))
    # Muzzle.  It used to run 158 mm from the skull to the nose with a 29 mm tip - as long
    # as the whole braincase and tapering to a point, which is a moose, not a dog.  It is
    # now 105 mm, blunt (38 mm at the nose), and DEEPER than it is wide, which is what
    # gives a mastiff/rottweiler read.  It also sits well below the forehead: the step
    # between the two is the stop.
    # Second pass: the blunt 105 mm muzzle read bear-ish rather than canine, because a
    # dog's muzzle is long AND narrow - wedge-shaped in plan, not a cylinder.  It is now
    # 125 mm and tapers from 49 mm to 30 mm across while staying deep.
    parts.append(L.tube('_muzzle', [V((0, -0.545, 0.762)), V((0, -0.592, 0.754)),
                                    V((0, -0.636, 0.747)), V((0, -0.672, 0.741))],
                        [(0.048, 0.048), (0.042, 0.045), (0.035, 0.041), (0.030, 0.036)],
                        14, up_hint=(0, 0, 1)))
    # nose leather
    parts.append(L.uv_sphere('_nose', (0, -0.682, 0.746), (0.022, 0.015, 0.018), 12, 8))
    # lips drawn back off the canines: a ridge along the muzzle that stops short
    for sx in (1, -1):
        parts.append(L.tube('_lip%d' % sx,
                            [V((0.031 * sx, -0.556, 0.722)), V((0.032 * sx, -0.600, 0.719)),
                             V((0.027 * sx, -0.642, 0.721)), V((0.018 * sx, -0.670, 0.727))],
                            [(0.010, 0.014), (0.011, 0.015), (0.010, 0.013),
                             (0.008, 0.010)], 8, up_hint=(0, 0, 1)))
    jaw = L.tube('_jaw', [V((0, -0.550, 0.714)), V((0, -0.596, 0.710)),
                          V((0, -0.638, 0.707)), V((0, -0.666, 0.704))],
                 [(0.040, 0.036), (0.035, 0.033), (0.029, 0.029), (0.022, 0.024)],
                 12, up_hint=(0, 0, 1))
    for v in jaw.data.vertices:
        v.co = jaw_rot(v.co)
    parts.append(jaw)
    for sx in (1, -1):
        # heavy brow over the socket
        parts.append(L.tube('_brow%d' % sx,
                            [V((0.012 * sx, -0.566, 0.820)), V((0.040 * sx, -0.556, 0.814)),
                             V((0.062 * sx, -0.522, 0.800))],
                            [(0.015, 0.014), (0.017, 0.015), (0.015, 0.013)], 8,
                            up_hint=(0, 0, 1)))
        # Ear: a broad, flat, roughly triangular flap folded back against the skull.  The
        # old version was a tapering tube that came to a point above the head - it read as
        # a horn, and with the long muzzle the whole head came out moose-ish.  Built as a
        # loft of quads so it has real width and a thin, hard edge.
        base = V((0.048 * sx, -0.466, 0.812))
        tipd = V((0.034 * sx, 0.150, 0.088)).normalized()
        wide = V((0.34 * sx, 0.20, -0.92)).normalized()
        rings = []
        # Bigger and cleanly triangular.  At 108 mm with a 3 mm edge the 7 mm voxel
        # remesh ate the tip and what was left read as a nub, which is half of why the
        # head still came out moose-ish.
        for (f, hw, th) in ((0.00, 0.046, 0.0120), (0.28, 0.050, 0.0105),
                            (0.58, 0.040, 0.0088), (0.82, 0.026, 0.0070),
                            (1.00, 0.009, 0.0050)):
            c = base + tipd * (0.142 * f)
            out = V((0.55 * sx, -0.25, 0.28)).normalized()
            pts = []
            for k in range(8):
                a = TAU * k / 8
                pts.append(c + wide * (math.cos(a) * hw) + out * (math.sin(a) * th))
            rings.append(pts)
        parts.append(L.loft('_ear%d' % sx, rings, True, True))
    return parts


def build_paw(pre, s, sx):
    """A real paw: a pad, four toes and claws, instead of a leg tapering to a point."""
    parts = []
    b = J['%spaw_%s' % (pre, s)]
    tp = J['%stoe_%s' % (pre, s)]
    d = (tp - b)
    d.z = 0.0
    if d.length < 1e-6:
        d = V((0, -1, 0))
    d.normalize()
    side = V((d.y, -d.x, 0))
    # metacarpal pad
    parts.append(L.tube('_%spad_%s' % (pre, s),
                        [b + V((0, 0, 0.012)), b + d * 0.030 + V((0, 0, 0.006)),
                         b + d * 0.055],
                        [(0.031, 0.026), (0.036, 0.024), (0.034, 0.018)], 12,
                        up_hint=(0, 0, 1)))
    for i, off in enumerate((-0.027, -0.009, 0.009, 0.027)):
        base = b + d * 0.046 + side * off + V((0, 0, 0.012))
        ln = 0.040 if abs(off) < 0.02 else 0.032
        tip = base + d * ln + V((0, 0, -0.004))
        r = 0.0125 if abs(off) < 0.02 else 0.0105
        parts.append(L.tube('_%stoe_%s%d' % (pre, s, i),
                            [base, base.lerp(tip, 0.55), tip],
                            [(r, r), (r * 0.95, r * 0.9), (r * 0.6, r * 0.55)], 8,
                            up_hint=(0, 0, 1)))
        # claw
        ctip = tip + d * 0.020 + V((0, 0, -0.006))
        parts.append(L.tube('_%sclaw_%s%d' % (pre, s, i), [tip, tip.lerp(ctip, 0.5), ctip],
                            [(r * 0.55, r * 0.55), (r * 0.38, r * 0.38),
                             (0.0012, 0.0012)], 6, up_hint=(0, 0, 1)))
    return parts


def build_body():
    parts = [L.loft('_torso', [ring_xz(*t) for t in TORSO], True, True)]
    # thick neck, flowing into the scruff
    parts.append(L.tube('_neck', [V((0, -0.318, 0.690)), V((0, -0.378, 0.712)),
                                  V((0, -0.436, 0.740)), V((0, -0.482, 0.764))],
                        [(0.118, 0.132), (0.106, 0.118), (0.090, 0.098), (0.074, 0.078)],
                        18, up_hint=(0, 0, 1)))
    # scruff / ruff mass over the shoulders
    parts.append(L.tube('_ruff', [V((0, -0.356, 0.698)), V((0, -0.306, 0.712)),
                                  V((0, -0.252, 0.700))],
                        [(0.112, 0.122), (0.130, 0.142), (0.136, 0.150)], 20,
                        up_hint=(0, 0, 1)))
    parts += build_head()
    for s in ('L', 'R'):
        sx = 1 if s == 'L' else -1
        # front leg: shoulder blade -> upper arm -> forearm -> pastern
        parts.append(L.tube('_fleg_' + s,
                            [J['fleg1_' + s] + V((-0.032 * sx, -0.020, 0.072)),
                             J['fleg1_' + s],
                             J['fleg1_' + s].lerp(J['fleg2_' + s], 0.55),
                             J['fleg2_' + s],
                             J['fleg2_' + s].lerp(J['fleg3_' + s], 0.45),
                             J['fleg3_' + s],
                             J['fpaw_' + s] + V((0, 0.004, 0.028)),
                             J['fpaw_' + s] + V((0, -0.004, 0.014))],
                            [(0.082, 0.114), (0.074, 0.102), (0.058, 0.078), (0.046, 0.058),
                             (0.036, 0.044), (0.030, 0.035), (0.030, 0.034),
                             (0.032, 0.030)],
                            14, up_hint=(0, -1, 0)))
        # hind leg: haunch -> thigh -> gaskin -> hock -> pastern
        parts.append(L.tube('_hleg_' + s,
                            [J['hleg1_' + s] + V((-0.034 * sx, 0.030, 0.060)),
                             J['hleg1_' + s],
                             J['hleg1_' + s].lerp(J['hleg2_' + s], 0.50),
                             J['hleg2_' + s],
                             J['hleg2_' + s].lerp(J['hleg3_' + s], 0.45),
                             J['hleg3_' + s],
                             J['hpaw_' + s] + V((0, -0.006, 0.028)),
                             J['hpaw_' + s] + V((0, 0.004, 0.014))],
                            [(0.102, 0.144), (0.096, 0.132), (0.072, 0.098), (0.048, 0.062),
                             (0.036, 0.046), (0.029, 0.035), (0.030, 0.034),
                             (0.032, 0.030)],
                            14, up_hint=(0, -1, 0)))
        for pre in ('f', 'h'):
            parts += build_paw(pre, s, sx)
    # tail: thick at the root, whipping thin
    parts.append(L.tube('_tail', [J['tail1'], J['tail2'], J['tail3'], J['tailtip']],
                        [(0.042, 0.048), (0.030, 0.033), (0.019, 0.020), (0.007, 0.007)],
                        12, up_hint=(0, 0, 1)))
    ob = L.join(parts, 'hound_body')
    L.voxel_remesh(ob, 0.0070, smooth=True)
    sculpt(ob)
    L.activate(ob)
    m = ob.modifiers.new('Sm', 'SMOOTH'); m.factor = 0.38; m.iterations = 1
    bpy.ops.object.modifier_apply(modifier=m.name)
    L.decimate(ob, 0.20)
    return ob


def sculpt(ob):
    from zombie_mesh import blob_line
    # --- ribs: starved, so they show through the burned hide
    for i in range(6):
        y = -0.190 + i * 0.052
        for sx in (1, -1):
            blob_line(ob, [(0.016 * sx, y, 0.800), (0.082 * sx, y + 0.006, 0.730),
                           (0.128 * sx, y + 0.012, 0.620), (0.090 * sx, y + 0.020, 0.500)],
                      0.019, 0.0090, ellipse=(1, 0.58, 1))
            blob_line(ob, [(0.016 * sx, y - 0.022, 0.800), (0.082 * sx, y - 0.016, 0.730),
                           (0.128 * sx, y - 0.010, 0.620), (0.090 * sx, y - 0.002, 0.500)],
                      0.014, -0.0065, ellipse=(1, 0.58, 1))
    # --- spine ridge and scapulae
    blob_line(ob, [(0, -0.290, 0.762), (0, -0.140, 0.828), (0, 0.060, 0.800),
                   (0, 0.240, 0.796), (0, 0.330, 0.742)], 0.020, 0.011, ellipse=(0.65, 1, 1))
    for sx in (1, -1):
        blob_line(ob, [(0.060 * sx, -0.250, 0.790), (0.098 * sx, -0.200, 0.712),
                       (0.104 * sx, -0.168, 0.628)], 0.028, 0.012)
        L.blob(ob, (0.090 * sx, 0.238, 0.748), 0.048, 0.014)        # tuber coxae
        L.blob(ob, (0.116 * sx, 0.226, 0.590), 0.082, 0.018)        # haunch mass
        L.blob(ob, (0.104 * sx, 0.196, 0.552), 0.052, -0.016)       # flank hollow
        L.blob(ob, (0.104 * sx, -0.212, 0.628), 0.070, 0.016)       # shoulder mass
        L.blob(ob, (0.098 * sx, -0.036, 0.596), 0.064, -0.020)      # belly tuck
        # cheekbone / temporal fossa
        L.blob(ob, (0.045 * sx, -0.552, 0.798), 0.022, -0.015)      # eye socket
        L.blob(ob, (0.058 * sx, -0.500, 0.816), 0.026, -0.010)      # temporal hollow
        L.blob(ob, (0.009 * sx, -0.688, 0.744), 0.009, -0.009,
               direction=(0, 1, -0.3))                              # nostril
        blob_line(ob, [(0.050 * sx, -0.536, 0.730), (0.030 * sx, -0.478, 0.706)],
                  0.015, -0.008)                                    # jowl crease
        # flews: the heavy upper lip hanging past the lower jaw
        L.blob(ob, (0.032 * sx, -0.616, 0.715), 0.020, 0.008,
               direction=(0.4 * sx, -0.3, -0.9))
    # muzzle stop: a hard step where the nasal bone meets the forehead
    blob_line(ob, [(0.030, -0.552, 0.786), (0.0, -0.556, 0.792), (-0.030, -0.552, 0.786)],
              0.016, -0.013, direction=(0, 0, -1))
    # domed cranium above it, so the stop has something to step down from
    L.blob(ob, (0.0, -0.492, 0.836), 0.046, 0.012, direction=(0, -0.15, 1))
    # occipital crest
    blob_line(ob, [(0.020, -0.440, 0.832), (0.0, -0.436, 0.840), (-0.020, -0.440, 0.832)],
              0.016, 0.009)
    # belly line
    L.blob(ob, (0, -0.030, 0.470), 0.078, -0.022, ellipse=(1.4, 1.6, 1))
    # --- leg articulation.  The chain angles were fixed last pass but the surface was a
    # smooth taper over them, so the hind legs still read as stilts in the side view: a
    # joint only reads if there is a muscle above it and a bony point behind it.
    for sx in (1, -1):
        L.blob(ob, (0.104 * sx, 0.195, 0.290), 0.062, 0.013)        # gaskin muscle
        L.blob(ob, (0.106 * sx, 0.318, 0.186), 0.030, 0.012,
               direction=(0.2 * sx, 1, 0.15))                       # calcaneus point
        L.blob(ob, (0.106 * sx, 0.072, 0.402), 0.034, -0.010)       # stifle crease
        L.blob(ob, (0.100 * sx, 0.180, 0.430), 0.054, 0.010)        # thigh mass
        L.blob(ob, (0.104 * sx, 0.255, 0.115), 0.024, -0.008)       # hock hollow in front
        L.blob(ob, (0.104 * sx, -0.190, 0.470), 0.050, 0.011)       # triceps
        L.blob(ob, (0.104 * sx, -0.120, 0.382), 0.026, 0.010,
               direction=(0.2 * sx, 1, 0))                          # olecranon (elbow)
        L.blob(ob, (0.104 * sx, -0.205, 0.300), 0.034, -0.008)      # forearm hollow
    # --- one flank burned away: three exposed rib arcs, deeper than the rest
    for i in range(3):
        y = -0.150 + i * 0.056
        blob_line(ob, [(0.052, y, 0.740), (0.110, y + 0.008, 0.660),
                       (0.122, y + 0.014, 0.578)], 0.016, 0.014, ellipse=(1, 0.5, 1))
        blob_line(ob, [(0.050, y - 0.026, 0.740), (0.106, y - 0.018, 0.660),
                       (0.118, y - 0.012, 0.578)], 0.014, -0.013, ellipse=(1, 0.5, 1))
    L.noise_displace(ob, scale=70, amount=0.0024, seed=5)
    L.noise_displace(ob, scale=22, amount=0.0032, seed=9)


def hide_z(x, y):
    """Top surface of the torso at (x, y) - so a fur clump can lie ON the hide.

    The clumps used to be placed at `torso_top(y)` (the centre-line height) no matter how
    far out in x they sat, which pushed every off-centre clump into the air: that, plus a
    25-degree rake and an 8:1 aspect ratio, is what made them read first as stegosaurus
    plates and then as porcupine quills.
    """
    hw = hh = zc = None
    for a, b in zip(TORSO, TORSO[1:]):
        if a[0] <= y <= b[0]:
            t = (y - a[0]) / (b[0] - a[0])
            hw = a[1] + (b[1] - a[1]) * t
            hh = a[2] + (b[2] - a[2]) * t
            zc = a[3] + (b[3] - a[3]) * t
            break
    if hw is None:
        e = TORSO[0] if y < TORSO[0][0] else TORSO[-1]
        hw, hh, zc = e[1], e[2], e[3]
    # walk the superellipse and take the height at the nearest x
    p_ = 2.0 / 2.2 - 1.0
    best, bz = 1e9, zc + hh
    for i in range(24):
        a = math.pi * 0.5 * i / 23.0
        ca, sa = math.cos(a), math.sin(a)
        px = 0.0 if abs(ca) < 1e-9 else (abs(ca) ** p_) * ca * hw
        pz = zc + (0.0 if abs(sa) < 1e-9 else (abs(sa) ** p_) * sa * hh)
        d = abs(px - abs(x))
        if d < best:
            best, bz = d, pz
    return bz


def _clump(name, x0, y0, sx, ln, w, lift, rnd):
    """One matted lock lying along the hide, swept back and fanning outward."""
    pts, radii = [], []
    n = 5
    for i in range(n):
        t = i / (n - 1.0)
        y = y0 + ln * t
        x = x0 + sx * (0.070 * t * t)
        z = hide_z(x, y) - 0.010 + lift * math.sin(t * 1.9)
        pts.append(V((x, y, z)))
        rw = w * (1.0 - 0.70 * t * t)
        radii.append((max(rw, 0.0018), max(rw * 0.44, 0.0014)))
    return L.tube(name, pts, radii, 6, up_hint=(0, 0, 1))


def build_fur():
    """Sparse, patchy matted hair - clumps that LIE ON the hide, with bald burnt gaps.

    Two failed passes before this one: 58 fat near-vertical pentagonal plates (a
    stegosaurus ridge), then 52 long thin raked spines (a porcupine).  The read the review
    asks for is burned, half-bald hide with a few surviving mats of hair, so: the clumps
    now follow the body surface (`hide_z`), are 4-7 mm proud of it rather than 25 mm, sit
    in four patches with 60-90 mm bald gaps between them, and only eight of them lift off
    the back at all - enough to rough up the silhouette, nowhere near a crest.
    """
    rnd = random.Random(31)
    parts = []
    i = 0
    # four patches down the spine with burnt gaps between; none of them on the centre line
    for (y0, span, cnt) in ((-0.300, 0.105, 7), (-0.140, 0.090, 6),
                            (0.075, 0.080, 5), (0.215, 0.085, 6)):
        for k in range(cnt):
            f = (k + 0.5) / cnt
            sx = 1 if (k % 2 == 0) else -1
            x = sx * rnd.uniform(0.012, 0.062)
            y = y0 + span * f + rnd.uniform(-0.012, 0.012)
            ln = rnd.uniform(0.055, 0.092)
            w = rnd.uniform(0.009, 0.016)
            lift = 0.004 if rnd.random() > 0.35 else rnd.uniform(0.012, 0.019)
            parts.append(_clump('_mat%d' % i, x, y, sx, ln, w, lift, rnd))
            i += 1
    # ruff: the one place a dog really is shaggy - locks sweeping back off the neck
    for k in range(14):
        a = math.pi * (k / 13.0 - 0.5) * 1.5
        x = math.sin(a) * rnd.uniform(0.070, 0.115)
        y = -0.330 + abs(math.cos(a)) * 0.030
        ln = rnd.uniform(0.075, 0.115)
        parts.append(_clump('_ruff%d' % i, x, y, 1 if x >= 0 else -1, ln,
                            rnd.uniform(0.013, 0.020), 0.006, rnd))
        i += 1
    # a few surviving locks on the haunches and shoulders, laid flat
    for sx in (1, -1):
        for (yy, ln) in ((0.150, 0.070), (0.220, 0.062), (-0.230, 0.075), (-0.170, 0.066)):
            x = sx * rnd.uniform(0.070, 0.100)
            parts.append(_clump('_lock%d' % i, x, yy, sx, ln,
                                rnd.uniform(0.010, 0.015), 0.003, rnd))
            i += 1
    ob = L.join(parts, 'hound_fur')
    L.noise_displace(ob, scale=34, amount=0.0026, seed=23)
    L.noise_displace(ob, scale=11, amount=0.0018, seed=41)
    return ob


def build_teeth():
    """Canines that show past the drawn-back lips, plus a working row behind them."""
    parts = []
    for row in (0, 1):
        for i in range(9):
            t = (i / 8.0 - 0.5)
            x = t * 0.044
            y = -0.646 + abs(t) * 0.108
            canine = abs(abs(t) - 0.34) < 0.10
            h = 0.030 if canine else (0.017 if abs(t) > 0.12 else 0.013)
            r1 = 0.0072 if canine else 0.0055
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=r1,
                                  radius2=0.0010, depth=h)
            me = bpy.data.meshes.new('_t%d%d' % (row, i))
            bm.to_mesh(me); bm.free()
            o = bpy.data.objects.new('_t%d%d' % (row, i), me)
            bpy.context.scene.collection.objects.link(o)
            if row == 0:                       # upper, points down from the maxilla
                o.location = (x, y, 0.7290 - h * 0.5)
                o.rotation_euler = (math.pi, 0, 0)
            else:                              # lower, sits on the mandible
                o.location = (x, y, 0.7090 + h * 0.5)
            L.activate(o)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            if row == 1:
                for v in o.data.vertices:
                    v.co = jaw_rot(v.co)
            parts.append(o)
    return L.join(parts, 'hound_teeth')


def build_eyes():
    a = L.icosphere('_eL', (0.045, -0.552, 0.798), 0.0098, 2)
    b = L.icosphere('_eR', (-0.045, -0.552, 0.798), 0.0098, 2)
    return L.join([a, b], 'hound_eyes')


# =======================================================================================
# animation
# =======================================================================================
FPS = 30


class HPose:
    def __init__(self, rig):
        self.rig = rig
        self.rr = {n: rig.rest[n].to_3x3().to_4x4() for n in rig.spec}

    def begin(self):
        self.rig.reset()

    def root(self, loc=(0, 0, 0), pitch=0.0, roll=0.0, yaw=0.0):
        self.rig.set_world('root', Matrix.Translation(V(loc)) @
                           Euler((pitch, roll, yaw), 'XYZ').to_matrix().to_4x4() @
                           self.rr['root'])

    def hips(self, pos, pitch=0.0, roll=0.0, yaw=0.0):
        self.rig.set_world('hips', Matrix.Translation(V(pos)) @
                           Euler((pitch, roll, yaw), 'XYZ').to_matrix().to_4x4() @
                           self.rr['hips'])

    def chain(self, **kw):
        for name, v in kw.items():
            self.rig.set_euler(name, v[0], v[1], v[2])

    def leg(self, pre, side, paw, pitch=0.0, meta_len=0.18, knee_dir=None):
        """pre = 'f' or 'h'. Places the paw exactly; the mid joint follows."""
        b1, b2, b3, b4 = ['%sleg1_%s' % (pre, side), '%sleg2_%s' % (pre, side),
                          '%sleg3_%s' % (pre, side), '%spaw_%s' % (pre, side)]
        paw = V(paw)
        hip = self.rig.bone_head(b1)
        toward = (hip - paw)
        if toward.length < 1e-4:
            toward = V((0, 0, 1))
        toward.normalize()
        lean = V((0, 0.55 if pre == 'h' else -0.14, 0))
        joint = paw + (toward + lean).normalized() * meta_len
        # The pole is the direction the middle joint bulges toward.  A dog's stifle points
        # FORWARD (-Y) and its elbow points BACK (+Y); these two were the wrong way round,
        # which is the other half of why the hind legs came out straight.
        pole = knee_dir or (V((0.15 if side == 'L' else -0.15, 1.0, 0)) if pre == 'f'
                            else V((0.15 if side == 'L' else -0.15, -1.0, 0)))
        self.rig.two_bone_ik(b1, b2, joint, pole)
        self.rig.aim(b3, paw - joint)
        m = (Matrix.Translation(paw) @ Matrix.Rotation(-pitch, 4, 'X') @ self.rr[b4])
        self.rig.set_world(b4, m)


class HLeg:
    def __init__(self, key, phase, duty, front, lift, x, y0):
        self.key = key            # ('f'|'h', 'L'|'R')
        self.phase = phase
        self.duty = duty
        self.front = front
        self.lift = lift
        self.x = x
        self.y0 = y0              # neutral paw Y under the body


BODY_Z = 0.600
PAW_F = -0.250
PAW_H = 0.215


def hound_gait(name, v, frames, legs, body_z, bob, pitch, rig, p, extra=None):
    T = frames / float(FPS)
    act = L.new_action(rig, name)
    for f in range(frames + 1):
        u = (f % frames) / float(frames)
        p.begin()
        p.root((0, 0, 0))
        bz = body_z + bob * math.cos(TAU * 2 * u)
        flex = math.sin(TAU * u) * 1.0
        p.hips((0.006 * math.sin(TAU * u), J['hips'].y, bz - 0.012 * flex),
               pitch=pitch + DEG(8) * flex, roll=DEG(4) * math.sin(TAU * u + 0.6),
               yaw=DEG(3) * math.sin(TAU * u))
        p.chain(spine=(DEG(-11) * flex, DEG(3) * flex, 0),
                chest=(DEG(-8) * flex, DEG(3) * flex, 0),
                neck=(DEG(10) + DEG(6) * flex, 0, DEG(3) * ZA.lnoise(u, 71)),
                head=(DEG(-6) - DEG(8) * flex, DEG(4) * ZA.lnoise(u, 72),
                      DEG(4) * ZA.lnoise(u, 73)),
                jaw=(DEG(10) + DEG(7) * math.sin(TAU * u * 2), 0, 0),
                tail_1=(DEG(-16) + DEG(8) * flex, 0, DEG(6) * ZA.lnoise(u, 74)),
                tail_2=(DEG(-10) + DEG(10) * ZA.lnoise(u, 75), 0, DEG(8) * ZA.lnoise(u, 76)),
                tail_3=(DEG(-6) + DEG(12) * ZA.lnoise(u, 77), 0, DEG(10) * ZA.lnoise(u, 78)))
        for leg in legs:
            pre, side = leg.key
            s = (u - leg.phase) % 1.0
            E = v * leg.duty * T
            if s < leg.duty:
                t = s / leg.duty
                y = leg.y0 - E * leg.front + E * t
                z = 0.028
                pit = DEG(-4) + DEG(22) * max(0.0, (t - 0.65) / 0.35)
            else:
                t = (s - leg.duty) / (1.0 - leg.duty)
                y0 = leg.y0 - E * leg.front + E
                y1 = leg.y0 - E * leg.front
                k = ZA.ease_io(t, 1.7)
                y = y0 + (y1 - y0) * k
                z = 0.028 + leg.lift * math.sin(math.pi * (t ** 0.8))
                pit = DEG(18) * (1 - t) - DEG(8) * t
            p.leg(pre, side, (leg.x, y, z), pitch=pit,
                  meta_len=FRONT_META if pre == 'f' else HIND_META)
        if extra:
            extra(p, u)
        rig.key(f)
    L.finish_action(act, frames)
    return act


def build_anims(rig):
    p = HPose(rig)
    info = []

    # ---- run: transverse gallop, 7 m/s
    frames = 11
    v = 7.0
    legs = [HLeg(('h', 'L'), 0.00, 0.30, 0.42, 0.22, J['hleg1_L'].x, PAW_H),
            HLeg(('h', 'R'), 0.11, 0.30, 0.42, 0.22, J['hleg1_R'].x, PAW_H),
            HLeg(('f', 'L'), 0.46, 0.28, 0.46, 0.24, J['fleg1_L'].x, PAW_F),
            HLeg(('f', 'R'), 0.57, 0.28, 0.46, 0.24, J['fleg1_R'].x, PAW_F)]
    hound_gait('run', v, frames, legs, BODY_Z, 0.042, DEG(2), rig, p)
    info.append(('run', frames, frames / float(FPS), 'v=%.1f m/s' % v))

    # ---- idle: standing, panting, heavy breathing, head low
    n = 90
    act = L.new_action(rig, 'idle')
    for f in range(n + 1):
        u = (f % n) / float(n)
        br = math.sin(TAU * u * 3.0)
        sh = ZA.lnoise(u, 81, (1, 2, 3))
        p.begin()
        p.root((0, 0, 0))
        p.hips((0.010 * sh, J['hips'].y, BODY_Z + 0.006 * br),
               pitch=DEG(1) + DEG(2) * br, roll=DEG(3) * sh, yaw=DEG(4) * sh)
        p.chain(spine=(DEG(2) * br, DEG(2) * sh, 0),
                chest=(DEG(3) * br, DEG(2) * sh, 0),
                neck=(DEG(7) + DEG(4) * br, DEG(4) * sh, DEG(6) * sh),
                head=(DEG(-10) + DEG(5) * sh, DEG(8) * sh, DEG(7) * sh),
                jaw=(DEG(14) + DEG(10) * br, 0, 0),
                tail_1=(DEG(-22) + DEG(6) * sh, 0, DEG(14) * sh),
                tail_2=(DEG(-14), 0, DEG(20) * ZA.lnoise(u, 82)),
                tail_3=(DEG(-8), 0, DEG(24) * ZA.lnoise(u, 83)))
        p.leg('f', 'L', (J['fleg1_L'].x, PAW_F + 0.012 * sh, 0.028), meta_len=FRONT_META)
        p.leg('f', 'R', (J['fleg1_R'].x, PAW_F + 0.018 - 0.010 * sh, 0.028),
              meta_len=FRONT_META)
        p.leg('h', 'L', (J['hleg1_L'].x, PAW_H + 0.008 * sh, 0.028), meta_len=HIND_META)
        p.leg('h', 'R', (J['hleg1_R'].x, PAW_H + 0.014 - 0.008 * sh, 0.028),
              meta_len=HIND_META)
        rig.key(f)
    L.finish_action(act, n)
    info.append(('idle', n, n / float(FPS), ''))

    # ---- attack: a horizontal POUNCE, not a rearing horse (review #16)
    # crouch 0-25%, airborne with the body extended 25-60%, bite and land 60-100%.
    n = 24
    act = L.new_action(rig, 'attack')
    kz = [(0.0, BODY_Z), (0.22, BODY_Z - 0.105), (0.38, BODY_Z + 0.240),
          (0.55, BODY_Z + 0.300), (0.74, BODY_Z + 0.060), (0.90, BODY_Z - 0.050),
          (1.0, BODY_Z)]
    # root drives forward through the leap; the game moves the holder as well, so the
    # clip returns most of the way to keep the two in step.
    kry = [(0.0, 0.0), (0.22, 0.06), (0.40, -0.30), (0.58, -0.52), (0.78, -0.40),
           (1.0, -0.12)]
    # nose-down through the air: the spine stays horizontal, never vertical
    kp = [(0.0, DEG(2)), (0.22, DEG(13)), (0.40, DEG(-8)), (0.58, DEG(-4)),
          (0.78, DEG(10)), (1.0, DEG(2))]
    kjaw = [(0.0, DEG(10)), (0.20, DEG(20)), (0.38, DEG(40)), (0.56, DEG(40)),
            (0.64, DEG(2)), (0.82, DEG(12)), (1.0, DEG(10))]
    # front legs thrown forward, hind legs trailing
    kfy = [(0.0, PAW_F), (0.22, PAW_F + 0.075), (0.40, PAW_F - 0.300),
           (0.58, PAW_F - 0.360), (0.78, PAW_F - 0.130), (1.0, PAW_F)]
    kfz = [(0.0, 0.028), (0.22, 0.028), (0.40, 0.330), (0.58, 0.300), (0.78, 0.050),
           (1.0, 0.028)]
    khy = [(0.0, PAW_H), (0.22, PAW_H - 0.060), (0.42, PAW_H + 0.150),
           (0.60, PAW_H + 0.190), (0.80, PAW_H + 0.030), (1.0, PAW_H)]
    khz = [(0.0, 0.028), (0.20, 0.028), (0.42, 0.190), (0.62, 0.230), (0.80, 0.040),
           (1.0, 0.028)]
    for f in range(n + 1):
        t = f / float(n)
        p.begin()
        p.root((0, ZA.kf(t, kry, 1.6), 0))
        p.hips((0, J['hips'].y, ZA.kf(t, kz, 1.7)), pitch=ZA.kf(t, kp, 1.7),
               roll=DEG(3) * math.sin(t * 7), yaw=DEG(3) * math.sin(t * 5))
        # the spine extends on take-off and coils again on landing
        ext = ZA.kf(t, [(0.0, 0.0), (0.22, DEG(14)), (0.42, DEG(-18)), (0.60, DEG(-14)),
                        (0.80, DEG(10)), (1.0, 0.0)], 1.6)
        p.chain(spine=(ext * 0.55, 0, 0), chest=(ext * 0.65, 0, 0),
                neck=(DEG(6) - ext * 0.5, 0, DEG(3)),
                head=(DEG(-2) - ext * 0.35, DEG(3), DEG(3)),
                jaw=(ZA.kf(t, kjaw, 1.5), 0, 0),
                tail_1=(DEG(-34) - ext * 0.8, 0, DEG(8)),
                tail_2=(DEG(-18), 0, DEG(10)), tail_3=(DEG(-10), 0, DEG(12)))
        fy, fz = ZA.kf(t, kfy, 1.6), ZA.kf(t, kfz, 1.6)
        hy, hz = ZA.kf(t, khy, 1.6), ZA.kf(t, khz, 1.6)
        air = DEG(26) if fz > 0.06 else DEG(0)
        p.leg('f', 'L', (J['fleg1_L'].x, fy - 0.025, fz), pitch=air, meta_len=FRONT_META)
        p.leg('f', 'R', (J['fleg1_R'].x, fy + 0.035, fz * 0.92), pitch=air,
              meta_len=FRONT_META)
        p.leg('h', 'L', (J['hleg1_L'].x, hy, hz), meta_len=HIND_META)
        p.leg('h', 'R', (J['hleg1_R'].x, hy + 0.030, hz * 0.88), meta_len=HIND_META)
        rig.key(f)
    L.finish_action(act, n)
    info.append(('attack', n, n / float(FPS), 'leap'))

    # ---- death: the legs give out, it skids forward and rolls onto its side
    n = 42
    act = L.new_action(rig, 'death')
    kz = [(0.0, BODY_Z), (0.14, BODY_Z - 0.080), (0.34, 0.330), (0.58, 0.170),
          (0.80, 0.118), (1.0, 0.112)]
    kroll = [(0.0, 0.0), (0.18, DEG(-10)), (0.44, DEG(-38)), (0.68, DEG(-70)),
             (0.88, DEG(-84)), (1.0, DEG(-86))]
    kslide = [(0.0, 0.0), (0.22, -0.10), (0.48, -0.30), (0.72, -0.42), (0.90, -0.46),
              (1.0, -0.47)]
    for f in range(n + 1):
        t = f / float(n)
        after = max(0.0, t - 0.72)
        set_ = math.exp(-8 * after) * math.sin(after * 52) if t > 0.72 else 0.0
        p.begin()
        p.root((0, ZA.kf(t, kslide, 1.4), 0))
        p.hips((0.05 * t, J['hips'].y, ZA.kf(t, kz, 1.5)),
               pitch=DEG(8) * math.sin(t * 4) + DEG(3) * set_,
               roll=ZA.kf(t, kroll, 1.5) + DEG(4) * set_, yaw=DEG(14) * t)
        p.chain(spine=(DEG(12) * math.sin(t * 3), DEG(-16) * t, DEG(9) * t),
                chest=(DEG(14) * math.sin(t * 3), DEG(-18) * t, DEG(11) * t),
                neck=(DEG(20) - DEG(44) * t, DEG(-10) * t, DEG(15) * t),
                head=(DEG(-10) + DEG(28) * t + DEG(6) * set_, DEG(16) * t, DEG(18) * t),
                jaw=(DEG(34) * (1 - t) + DEG(6), 0, 0),
                tail_1=(DEG(-28) + DEG(22) * t, 0, DEG(26) * t),
                tail_2=(DEG(-14), 0, DEG(28) * t), tail_3=(DEG(-8), 0, DEG(30) * t))
        fold = ZA.smooth(t * 1.3)
        p.leg('f', 'L', (J['fleg1_L'].x + 0.04 * fold, PAW_F + 0.12 * fold,
                         0.028 + 0.10 * fold), meta_len=FRONT_META)
        p.leg('f', 'R', (J['fleg1_R'].x - 0.11 * fold, PAW_F + 0.02 * fold, 0.028),
              meta_len=FRONT_META)
        p.leg('h', 'L', (J['hleg1_L'].x + 0.04 * fold, PAW_H - 0.10 * fold,
                         0.028 + 0.09 * fold), meta_len=HIND_META)
        p.leg('h', 'R', (J['hleg1_R'].x - 0.12 * fold, PAW_H - 0.02 * fold, 0.028),
              meta_len=HIND_META)
        rig.key(f)
    L.finish_action(act, n)
    info.append(('death', n, n / float(FPS), 'collapse + skid'))
    return info


# =======================================================================================
# build
# =======================================================================================
scn = reset_scene()
scn.render.fps = 30
scn.render.fps_base = 1.0
log('body')
body = build_body()
log('  body tris', L.triangle_count(body))
fur = build_fur()
log('  fur tris', L.triangle_count(fur))
body = L.join([body, fur], 'hound_body')
L.clear_colors(body)
L.smart_uv(body, 68, 0.008)

if FAST:
    skin = MAT.simple('hound_hide', (0.034, 0.028, 0.025), 0.72)
else:
    def char_mat(mat, ob):
        """Charred hide: matted fur over the back, burned bare skin on the flanks, and
        fire ONLY in the deep creases (driven by ambient occlusion, not by a uniform
        Voronoi crack network that read as an obsidian rock golem)."""
        nt = mat.node_tree
        for n in list(nt.nodes):
            if n.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
                nt.nodes.remove(n)
        b = nt.nodes['Principled BSDF']
        co = MAT.N(nt, 'ShaderNodeTexCoord')
        sep = MAT.N(nt, 'ShaderNodeSeparateXYZ')
        MAT.lk(nt, co, 'Object', sep, 'Vector')
        n1 = MAT.noise(nt, 8.0, 8, 0.65, 0.4, (co, 'Object'))
        n2 = MAT.noise(nt, 46.0, 8, 0.62, 0.1, (co, 'Object'))
        n3 = MAT.noise(nt, 210.0, 5, 0.5, 0.0, (co, 'Object'))
        # matted fur: stretched noise, so the clumps read as hair not as marble
        furm = MAT.N(nt, 'ShaderNodeMapping')
        MAT.inp(furm, 'Scale', (1.0, 3.2, 1.0))
        MAT.lk(nt, co, 'Object', furm, 'Vector')
        nfur = MAT.noise(nt, 120.0, 8, 0.72, 0.6)
        MAT.lk(nt, furm, 'Vector', nfur, 'Vector')

        hide = (0.0125, 0.0105, 0.0098, 1)      # burned bare skin
        furc = (0.0330, 0.0250, 0.0195, 1)      # scorched matted hair
        ash = (0.0480, 0.0430, 0.0400, 1)       # ash on the high points

        c0 = MAT.mix(nt, n1, 'Fac', hide, (0.0210, 0.0175, 0.0150, 1))
        # fur lives on the back and the haunches, bare hide on the flanks and belly
        hi = MAT.N(nt, 'ShaderNodeMapRange')
        MAT.lk(nt, sep, 'Z', hi, 'Value')
        hi.inputs[1].default_value = 0.56
        hi.inputs[2].default_value = 0.80
        hi.clamp = True
        furmask = MAT._sub(nt, hi, 'Result', nfur, 'Fac', 'MULTIPLY')
        furmask = MAT._sub(nt, furmask, 'Value', 1.6, op='MULTIPLY')
        c1 = MAT.mix(nt, furmask, 'Value', (c0, 'Result'), furc)
        c1b = MAT.mix(nt, n2, 'Fac', (c1, 'Result'), ash)

        # --- cavity: 1 in the creases, 0 on the exposed surfaces
        ao = MAT.N(nt, 'ShaderNodeAmbientOcclusion')
        ao.samples = 12
        MAT.inp(ao, 'Distance', 0.045)
        cav = MAT.ramp(nt, ao, 'Fac', [(0.30, (1, 1, 1, 1)), (0.86, (0, 0, 0, 1))])
        # break it up so the fire is patchy rather than tracing every crease
        hot = MAT.ramp(nt, n1, 'Fac', [(0.46, (0, 0, 0, 1)), (0.66, (1, 1, 1, 1))])
        emb = MAT._sub(nt, cav, 'Color', hot, 'Color', 'MULTIPLY')
        emb2 = MAT._sub(nt, emb, 'Value', n2, 'Fac', 'MULTIPLY')
        emb2 = MAT._sub(nt, emb2, 'Value', 1.05, op='MULTIPLY')
        c2 = MAT.mix(nt, emb2, 'Value', (c1b, 'Result'), (0.240, 0.040, 0.008, 1))
        MAT.lk(nt, c2, 'Result', b, 'Base Color')
        emc = MAT.mix(nt, emb2, 'Value', (0, 0, 0, 1), (1.0, 0.24, 0.035, 1))
        MAT.lk(nt, emc, 'Result', b, 'Emission Color')
        MAT.inp(b, 'Emission Strength', 1.0)
        rr = MAT.ramp(nt, n3, 'Fac', [(0.2, (0.62, 0.62, 0.62, 1)),
                                      (0.85, (0.94, 0.94, 0.94, 1))])
        MAT.lk(nt, rr, 'Color', b, 'Roughness')
        bp = MAT.N(nt, 'ShaderNodeBump')
        MAT.inp(bp, 'Strength', 0.65); MAT.inp(bp, 'Distance', 0.006)
        MAT.lk(nt, nfur, 'Fac', bp, 'Height')
        bp2 = MAT.N(nt, 'ShaderNodeBump')
        MAT.inp(bp2, 'Strength', 0.34); MAT.inp(bp2, 'Distance', 0.004)
        MAT.lk(nt, n3, 'Fac', bp2, 'Height')
        MAT.lk(nt, bp, 'Normal', bp2, 'Normal')
        MAT.lk(nt, bp2, 'Normal', b, 'Normal')
        return mat

    log('baking hide')
    tex = L.bake_object_material(body, char_mat, 'hound_' + BAKE_VERSION, size=2048,
                                 samples=8, force=FORCE_BAKE,
                                 passes=('DIFFUSE', 'ROUGHNESS', 'NORMAL', 'EMIT'))
    skin = L.baked_material('hound_hide', tex, roughness=0.8, emit_strength=1.1)
body.data.materials.append(skin)
L.shade_smooth_ob(body, 52)

teeth = build_teeth()
L.clear_colors(teeth)
teeth.data.materials.append(MAT.simple('hound_teeth', (0.150, 0.135, 0.100), 0.38))
L.shade_smooth_ob(teeth, 24)
body = L.join([body, teeth], 'hound_body')
eyes = build_eyes()
L.clear_colors(eyes)
# modest ember set back in a socket, not a pair of headlamps (review #2 / #9)
eyes.data.materials.append(MAT.simple('eye_glow', (0.30, 0.075, 0.010), 0.35,
                                      emission=(1.0, 0.22, 0.03), strength=2.5))
L.shade_smooth_ob(eyes, 60)

# docs/ASSET_CONTRACT.md: character <= 25k tris per variant.  The hound is one variant.
HOUND_BUDGET = 24000
if L.triangle_count(body) + L.triangle_count(eyes) > HOUND_BUDGET:
    L.decimate_to(body, HOUND_BUDGET - L.triangle_count(eyes))
log('  final tris', L.triangle_count(body) + L.triangle_count(eyes))

log('rigging')
rig = L.Rig('Armature', SKELETON)
arm = rig.ob
L.activate(body)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
L.fix_weights(body, arm)

for extra, bone in ((eyes, 'head'),):
    g = extra.vertex_groups.new(name=bone)
    g.add([v.index for v in extra.data.vertices], 1.0, 'REPLACE')
    L.activate(extra)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_NAME')

log('animating')
clips = build_anims(rig)
for c in clips:
    log('  clip %-7s %3d frames %.2fs %s' % c)

bpy.context.scene.frame_set(0)
bpy.ops.object.select_all(action='DESELECT')
for ob in (arm, body, eyes):
    ob.select_set(True)
bpy.context.view_layer.objects.active = arm
L.export_character(OUT)
log('EXPORTED', OUT, os.path.getsize(OUT) // 1024, 'KB',
    'tris', L.triangle_count(body) + L.triangle_count(eyes))

if STILLS or SHEETS:
    scn = setup_gpu(40)
    scn.view_settings.view_transform = 'AgX'

if STILLS:
    act = bpy.data.actions['idle']
    arm.animation_data.action = act
    try:
        arm.animation_data.action_slot = act.slots[0]
    except Exception:
        pass
    bpy.context.scene.frame_set(20)
    L.dusk_render(os.path.join(RDIR, 'hound_side.png'), target=(0, -0.05, 0.45),
                  distance=2.2, yaw_deg=92, pitch_deg=4, lens=50, samples=32, res=(896, 504))
    L.dusk_render(os.path.join(RDIR, 'hound_34.png'), target=(0, -0.05, 0.45),
                  distance=2.0, yaw_deg=38, pitch_deg=8, lens=50, samples=32, res=(896, 504))
    L.dusk_render(os.path.join(RDIR, 'hound_head.png'), target=(0, -0.58, 0.77),
                  distance=0.56, yaw_deg=48, pitch_deg=6, lens=50, samples=32, res=(896, 504),
                  ground=False)

if SHEETS:
    tmp = os.path.join(RDIR, '_tmp')
    os.makedirs(tmp, exist_ok=True)
    for name, nframes, dur, note in clips:
        act = bpy.data.actions[name]
        arm.animation_data.action = act
        try:
            arm.animation_data.action_slot = act.slots[0]
        except Exception:
            pass
        paths = []
        for i in range(6):
            f = int(round(i * nframes / 6.0))
            bpy.context.scene.frame_set(f)
            pth = os.path.join(tmp, 'h_%s_%02d.png' % (name, i))
            L.dusk_render(pth, target=(0, -0.05, 0.50), distance=2.6, yaw_deg=80,
                          pitch_deg=8, lens=44, samples=24, res=(340, 300))
            paths.append(pth)
        L.contact_sheet(paths, os.path.join(RDIR, 'anim_hound_%s.png' % name), 6, (340, 300))
log('done')
