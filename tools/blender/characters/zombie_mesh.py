"""Zombie geometry: emaciated adult anatomy lofted from cross-sections, unioned by voxel
remesh, then blob-sculpted (ribs, spine groove, sunken gaunt face, open wounds).

All procedural, no sculpt data.  Conventions: metres, Z up, the character faces -Y and
+X is the character's LEFT.

Rewritten for the art review:
  * real human proportions - clavicle/deltoid mass, ribcage taper, separated thighs,
    calf swell + ankle pinch, a neck, thicker tapered fingers                     (#7)
  * a gaunt skull-read face: deep sockets, temple + cheek hollows, receded lips over
    real teeth *and* gums, per-variant face shapes and one asymmetric facial wound (#1)
  * wounds authored where they are actually visible, in one shared table that the
    material, the gore-material face picker and the cloth tears all read             (#6)
"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler

import lib_char as L
from zombie_rig import J

TAU = math.pi * 2


def superellipse(n=2.6, back=0.94, front=1.0):
    p = 2.0 / n - 1.0

    def f(a):
        ca, sa = math.cos(a), math.sin(a)
        sx = 0.0 if abs(ca) < 1e-9 else abs(ca) ** p
        sz = 0.0 if abs(sa) < 1e-9 else abs(sa) ** p
        sz *= back if sa < 0 else front
        return (sx, sz)
    return f


# =======================================================================================
# shared wound table
#
# Every wound is authored once here.  `sculpt_body` carves it, `wound_faces` gives it the
# gore material, `zombie_mat.skin_material` paints blood around it and `zombie_cloth`
# opens the garment over it.  Before this table the three lists disagreed and every
# torso wound sat under a closed shirt, so nothing was ever visible on the finished
# character - the bug called out in review item #6.
#
#   key: (centre, crater radius, depth, blood radius, variants, exposed)
# `exposed` means the garment is cut open over it (or it is on bare skin anyway).
#
# `hole` wounds also carry an `axis`: the outward surface normal of the body at that point.
# The garment tear is a *tube* swept along that axis (see lib_char.punch_hole), not an
# ellipsoid centred on the skin - the cloth sits 3-5 cm further out, so a ball had to be
# stretched absurdly in Y to reach it and the resulting hole was far bigger than the skin
# that was protected underneath, which is why you could see straight into the black
# interior of the garment.
# =======================================================================================

WOUNDS = {
    # bare skin, visible on every variant
    'forearm_R':  dict(c=(-0.281, -0.036, 0.995), r=0.030, d=-0.014, blood=0.085,
                       ell=(1.0, 1.0, 1.6), variants='ABC'),
    'hand_L':     dict(c=(0.318, -0.066, 0.800), r=0.026, d=-0.006, blood=0.090,
                       ell=(1, 1, 1), variants='ABC'),
    'neck':       dict(c=(0.052, 0.014, 1.520), r=0.030, d=-0.016, blood=0.105,
                       ell=(1.0, 1.0, 1.25), variants='ABC'),
    # torn open through the clothing - the cloth builder cuts a matching hole
    'ribs_L':     dict(c=(0.132, -0.074, 1.252), r=0.044, d=-0.020, blood=0.135,
                       ell=(1.25, 1.0, 1.20), variants='A', hole=0.046, ribs=True,
                       axis=(0.68, -0.73, 0.06)),
    # variant B: kept on the belly, but her apron was rebuilt as a waist apron (top at
    # z 1.075) so the wound is no longer buried under it.
    'belly':      dict(c=(-0.072, -0.096, 1.126), r=0.042, d=-0.024, blood=0.135,
                       ell=(1.0, 1.0, 1.5), variants='B', hole=0.044,
                       axis=(-0.40, -0.91, 0.10)),
    'shoulder_R': dict(c=(-0.180, -0.026, 1.368), r=0.040, d=-0.018, blood=0.115,
                       ell=(1, 1, 1), variants='C', hole=0.042,
                       axis=(-0.86, -0.49, 0.14)),
    'thigh_L':    dict(c=(0.128, -0.052, 0.700), r=0.034, d=-0.014, blood=0.105,
                       ell=(1, 1, 1.3), variants='ABC', hole=0.038,
                       axis=(0.51, -0.86, 0.0)),
}


def hole_axis(w):
    return w.get('axis', (0.0, -1.0, 0.0))


def wounds_for(variant):
    return [w for w in WOUNDS.values() if variant in w['variants']]


def all_wounds():
    return list(WOUNDS.values())


# ---------------------------------------------------------------------------------------
# torso / limbs
# ---------------------------------------------------------------------------------------

# (z, half width, half depth, y centre)
# Shoulders widened ~18%, a real waist taper, the ribcage flaring above it and a narrow
# neck column on top so the head is not welded to the shoulders.
TORSO = [
    (0.845, 0.130, 0.100, 0.020),   # crotch floor - the thighs split below this
    (0.900, 0.166, 0.122, 0.014),   # widest point of the pelvis
    (0.960, 0.158, 0.114, 0.008),
    (1.020, 0.142, 0.104, 0.002),
    (1.080, 0.131, 0.098, -0.004),  # waist (starved)
    (1.140, 0.141, 0.106, -0.008),  # floating ribs
    (1.205, 0.160, 0.117, -0.008),
    (1.270, 0.181, 0.125, -0.002),
    (1.330, 0.195, 0.125, 0.006),
    (1.385, 0.199, 0.117, 0.014),   # top of the ribcage
    (1.435, 0.178, 0.103, 0.020),   # clavicle line
    (1.472, 0.118, 0.086, 0.022),
    (1.505, 0.070, 0.068, 0.020),   # neck base
    (1.545, 0.054, 0.054, 0.018),   # neck
    (1.600, 0.052, 0.052, 0.016),   # under the jaw
]


def torso_profile(z):
    """Interpolated (half_width, half_depth, y_centre) at height z."""
    if z <= TORSO[0][0]:
        return TORSO[0][1:]
    if z >= TORSO[-1][0]:
        return TORSO[-1][1:]
    for a, b in zip(TORSO, TORSO[1:]):
        if a[0] <= z <= b[0]:
            t = (z - a[0]) / (b[0] - a[0])
            return tuple(a[i + 1] + (b[i + 1] - a[i + 1]) * t for i in range(3))
    return TORSO[-1][1:]


def build_torso(n=30):
    shape = superellipse(2.7, back=0.95)
    rings = []
    for z, rx, rz, y in TORSO:
        rings.append(L.ring((0, y, z), rx, rz, n, y=(0, 0, 1), shape=shape))
    return L.loft('_torso', rings, True, True)


def build_yoke(n=16):
    """Trapezius + deltoid cap across the shoulders (lofted along X)."""
    path = [Vector((-0.238, 0.008, 1.372)), Vector((-0.205, 0.006, 1.412)),
            Vector((-0.140, 0.008, 1.458)), Vector((-0.058, 0.012, 1.480)),
            Vector((0.058, 0.012, 1.480)), Vector((0.140, 0.008, 1.458)),
            Vector((0.205, 0.006, 1.412)), Vector((0.238, 0.008, 1.372))]
    radii = [(0.056, 0.052), (0.066, 0.060), (0.070, 0.064), (0.060, 0.062),
             (0.060, 0.062), (0.070, 0.064), (0.066, 0.060), (0.056, 0.052)]
    return L.tube('_yoke', path, radii, n, up_hint=(0, 0, 1))


def build_neck(n=14):
    """Sterno-mastoid column: the head sits on this, not straight on the chest."""
    path = [Vector((0, 0.010, 1.432)), Vector((0, 0.012, 1.476)),
            Vector((0, 0.014, 1.520)), Vector((0, 0.016, 1.566)),
            Vector((0, 0.018, 1.600))]
    radii = [(0.074, 0.070), (0.058, 0.058), (0.051, 0.053), (0.049, 0.052),
             (0.050, 0.053)]
    return L.tube('_neck', path, radii, n, up_hint=(0, -1, 0))


def arm_path(side):
    s = 1 if side == 'L' else -1
    sh = J['shoulder_' + side]
    el = J['elbow_' + side]
    wr = J['wrist_' + side]
    inner = sh + Vector((-0.062 * s, 0.006, 0.026))
    return [inner,
            sh + Vector((0.004 * s, 0.002, 0.004)),
            sh.lerp(el, 0.30),
            sh.lerp(el, 0.62),
            el + Vector((0.002 * s, 0.006, 0.006)),
            el.lerp(wr, 0.22),
            el.lerp(wr, 0.55),
            wr + Vector((0, -0.002, 0.008)),
            wr + Vector((0.004 * s, -0.004, -0.014))]


def _arm_radii():
    """Deltoid -> biceps -> elbow -> forearm belly -> wrist. Thicker than a broom handle."""
    return [(0.068, 0.068), (0.065, 0.066), (0.055, 0.057), (0.045, 0.048),
            (0.041, 0.044), (0.046, 0.049), (0.040, 0.043), (0.029, 0.032),
            (0.027, 0.030)]


def build_arm(side, n=14):
    return L.tube('_arm_' + side, arm_path(side), _arm_radii(), n, up_hint=(0, -1, 0))


def leg_path(side):
    """Starts on the femur head so the two thighs are separate volumes below the crotch."""
    s = 1 if side == 'L' else -1
    hp = J['hip_' + side]
    kn = J['knee_' + side]
    an = J['ankle_' + side]
    return [hp + Vector((0.006 * s, 0.004, 0.062)),
            hp + Vector((0.008 * s, 0.000, 0.010)),
            hp.lerp(kn, 0.30),
            hp.lerp(kn, 0.66),
            kn + Vector((0, -0.006, 0.014)),
            kn + Vector((0, 0.002, -0.012)),
            kn.lerp(an, 0.30) + Vector((0, 0.016, 0)),
            kn.lerp(an, 0.62) + Vector((0, 0.006, 0)),
            an + Vector((0, 0.004, 0.034)),
            an + Vector((0, 0.006, 0.004))]


def _leg_radii():
    """Thigh mass, knee pinch, calf swell at ~32% of the shin, malleolar ankle pinch."""
    return [(0.078, 0.086), (0.078, 0.084), (0.070, 0.076), (0.057, 0.061),
            (0.049, 0.052), (0.047, 0.050), (0.060, 0.068), (0.041, 0.046),
            (0.027, 0.032), (0.026, 0.031)]


def build_leg(side, n=16):
    return L.tube('_leg_' + side, leg_path(side), _leg_radii(), n, up_hint=(0, -1, 0))


def build_foot(side, n=14):
    """Bare foot: a real last shape with an arch and a heel.  Hidden under a shoe on
    every shipped variant, but it has to read if a shoe is ever removed."""
    s = 1 if side == 'L' else -1
    x = J['ankle_' + side].x
    path = [Vector((x, 0.062, 0.050)),
            Vector((x, 0.028, 0.040)),
            Vector((x, -0.030, 0.034)),
            Vector((x, -0.095, 0.030)),
            Vector((x, -0.158, 0.024)),
            Vector((x, -0.196, 0.018))]
    radii = [(0.030, 0.034), (0.036, 0.038), (0.040, 0.034),
             (0.041, 0.028), (0.035, 0.021), (0.021, 0.013)]
    ob = L.tube('_foot_' + side, path, radii, n, up_hint=(0, 0, 1))
    for v in ob.data.vertices:
        t = max(0.0, min(1.0, (-v.co.y - 0.02) / 0.075))
        lim = 0.004 + 0.018 * math.sin(t * math.pi)
        if v.co.z < lim:
            v.co.z = lim
    return ob


def build_toes(side):
    s = 1 if side == 'L' else -1
    x0 = J['ankle_' + side].x
    obs = []
    for i, (dx, ln, r) in enumerate([(-0.022, 0.032, 0.013), (0.000, 0.029, 0.012),
                                     (0.022, 0.021, 0.010)]):
        base = Vector((x0 + dx * s, -0.162, 0.016 + r * 0.5))
        tip = base + Vector((0, -ln, -0.003))
        obs.append(L.tube('_toe_%s_%d' % (side, i), [base, base.lerp(tip, 0.5), tip],
                          [(r, r), (r * 0.95, r * 0.95), (r * 0.55, r * 0.55)], 8,
                          up_hint=(0, 0, 1)))
    return obs


# ---------------------------------------------------------------------------------------
# hands: a real palm mass, an opposed thumb and tapered fingers (not needle spikes)
# ---------------------------------------------------------------------------------------

def hand_matrix(side):
    """Local hand frame: +Y along the fingers, +X toward the thumb, +Z out of the back."""
    s = 1 if side == 'L' else -1
    wr = J['wrist_' + side]
    y = (J['hand_' + side] - wr).normalized()
    zref = Vector((0.35 * s, -0.55, 0.15)).normalized()
    z = (zref - y * zref.dot(y)).normalized()
    x = y.cross(z)
    return Matrix(((x.x, y.x, z.x, wr.x), (x.y, y.y, z.y, wr.y),
                   (x.z, y.z, z.z, wr.z), (0, 0, 0, 1)))


def _finger(name, m, base, direction, lengths, radii, curl, spread=0.0, knuckle=0.0):
    """Curled finger built in hand-local space, transformed by m."""
    pts = [Vector(base)]
    d = Vector(direction).normalized()
    ang = 0.0
    rr = []
    for i, ln in enumerate(lengths):
        ang += curl[i]
        rot = Matrix.Rotation(ang, 4, 'X') @ Matrix.Rotation(spread, 4, 'Z')
        step = (rot @ d) * ln
        pts.append(pts[-1] + step)
        rr.append(radii[i])
    path, radl = [], []
    for i in range(len(pts)):
        path.append(pts[i])
        r = rr[min(i, len(rr) - 1)]
        # knuckles: the joints are wider than the segments between them
        k = 1.0 + knuckle * (0.30 if 0 < i < len(pts) - 1 else 0.0)
        radl.append((r * k, r * k))
    return L.tube(name, [m @ p for p in path], radl, 8, up_hint=(0, 0, 1))


def build_hand(side):
    s = 1 if side == 'L' else -1
    m = hand_matrix(side)
    parts = []
    # palm: thicker and wider across the metacarpal fan, with a thenar (thumb) pad
    palm_rings = []
    for (yv, w, t) in [(-0.036, 0.024, 0.021), (-0.014, 0.031, 0.024),
                       (0.008, 0.039, 0.026), (0.034, 0.047, 0.026),
                       (0.062, 0.050, 0.023), (0.086, 0.046, 0.016)]:
        palm_rings.append(L.ring(m @ Vector((0, yv, 0)), w, t, 12,
                                 y=(m.col[1].to_3d()),
                                 xaxis=m.col[0].to_3d(), zaxis=m.col[2].to_3d(),
                                 shape=superellipse(3.2)))
    parts.append(L.loft(f'_palm_{side}', palm_rings, True, True))
    # thenar eminence - the muscle pad at the base of the thumb
    parts.append(L.uv_sphere(f'_thenar_{side}',
                             m @ Vector((-0.030, 0.014, -0.004)),
                             (0.019, 0.026, 0.014), 12, 8))
    # four fingers, progressively curled into a claw, tapering to a blunt tip
    fdata = [(-0.0345, 0.076, 0.0104), (-0.0115, 0.084, 0.0106),
             (0.0115, 0.080, 0.0100), (0.0345, 0.066, 0.0090)]
    for i, (xo, ln, r) in enumerate(fdata):
        segs = [ln * 0.42, ln * 0.33, ln * 0.25]
        rad = [r, r * 0.84, r * 0.60]
        curl = [math.radians(-32 - i * 5), math.radians(-46), math.radians(-40)]
        parts.append(_finger('_fing_%s_%d' % (side, i), m, Vector((xo, 0.084, 0.002)),
                             Vector((0, 1, 0)), segs, rad, curl,
                             spread=math.radians(-10 + i * 7), knuckle=1.0))
    # thumb, opposed and curled toward the fingers
    parts.append(_finger('_thumb_%s' % side, m, Vector((-0.034, 0.026, -0.004)),
                         Vector((-0.58, 0.76, -0.22)), [0.035, 0.030, 0.023],
                         [0.0122, 0.0106, 0.0074],
                         [math.radians(-16), math.radians(-40), math.radians(-36)],
                         knuckle=1.0))
    return L.join(parts, f'_hand_{side}')


# ---------------------------------------------------------------------------------------
# head
# ---------------------------------------------------------------------------------------

YC = 0.012                      # head centreline in Y
JAW_PIVOT = Vector((0.0, 0.050, 1.650))
JAW_OPEN = math.radians(9.0)    # mandible dropped -> the mouth hangs slightly open
EYE_L = Vector((0.0332, -0.0455, 1.7005))
EYE_R = Vector((-0.0332, -0.0455, 1.7005))


def _jaw_rot(p):
    """Rotate a point with the dropped mandible."""
    rel = Vector(p) - JAW_PIVOT
    c, s = math.cos(JAW_OPEN), math.sin(JAW_OPEN)
    return JAW_PIVOT + Vector((rel.x, rel.y * c - rel.z * s, rel.y * s + rel.z * c))


def asym_ring(z, w, front, back, n=32, exp=2.05, yc=YC):
    """Closed contour: half width w, `front` reach toward -Y, `back` toward +Y."""
    p = 2.0 / exp - 1.0
    pts = []
    for i in range(n):
        a = TAU * i / n
        ca, sa = math.cos(a), math.sin(a)
        sx = 0.0 if abs(ca) < 1e-9 else abs(ca) ** p
        sz = 0.0 if abs(sa) < 1e-9 else abs(sa) ** p
        d = front if sa > 0 else back
        pts.append(Vector((ca * sx * w, yc - sa * sz * d, z)))
    return pts


# (z, half-width, front reach, back reach)
# The old table was prognathic - the chin reached 24 mm further forward than the brow,
# which is a chimpanzee's profile, and it is why the first pass read as a muzzle.  A
# human skull is orthognathic: the forehead, the brow and the chin sit on roughly one
# vertical plane and only the nose projects past it.
CRANIUM = [
    (1.6320, 0.0645, 0.0860, 0.0650),
    (1.6480, 0.0676, 0.0855, 0.0740),
    (1.6640, 0.0690, 0.0840, 0.0810),
    (1.6800, 0.0700, 0.0820, 0.0865),
    (1.7010, 0.0703, 0.0752, 0.0900),
    (1.7200, 0.0690, 0.0800, 0.0898),
    (1.7450, 0.0666, 0.0780, 0.0880),
    (1.7700, 0.0618, 0.0720, 0.0830),
    (1.7900, 0.0531, 0.0600, 0.0730),
    (1.8060, 0.0367, 0.0390, 0.0530),
    (1.8130, 0.0126, 0.0125, 0.0185),
]
MANDIBLE = [
    (1.5880, 0.0440, 0.0790, 0.0160),
    (1.6000, 0.0512, 0.0820, 0.0310),
    (1.6130, 0.0579, 0.0830, 0.0450),
    (1.6260, 0.0622, 0.0825, 0.0580),
    (1.6400, 0.0642, 0.0815, 0.0670),
    (1.6520, 0.0645, 0.0805, 0.0730),
]
MOUTH_ROOF = 1.6340             # underside of the maxilla (top of the upper teeth)
LOWER_GUM = 1.6320              # top of the mandible before the jaw rotation

# dental arch (an ellipse, not the old flat bow).
# The span was 1.92 rad, which put teeth right out to the lip corners: combined with the
# blood paint that made the whole lower face read as a grinning red band at game framing.
# The arch is now narrower than the mouth aperture, so the corners stay dark lip.
ARC_X = 0.0248
ARC_Y = 0.0300
ARC_SPAN = 1.52                 # radians of parameter swept, tuned to the lip corners


def tooth_arc(i, count, inset=0.0):
    """Position and yaw of tooth i on an elliptical dental arch."""
    t = (i / (count - 1.0) - 0.5) * ARC_SPAN
    x = math.sin(t) * (ARC_X - inset)
    y = YC - 0.0760 + (1 - math.cos(t)) * (ARC_Y - inset)
    return x, y, t


def build_head_parts():
    parts = []
    rings = [asym_ring(z, w, f, b) for (z, w, f, b) in CRANIUM]
    parts.append(L.loft('_cranium', rings, True, True))
    # mandible: the top is cut back at the front so the gape really opens
    jr = []
    for (z, w, f, b) in MANDIBLE:
        r = []
        for pt in asym_ring(z, w, f, b, 32, 2.35):
            t = max(0.0, min(1.0, (pt.y + 0.078) / 0.098))
            lim = LOWER_GUM + t * 0.0200
            r.append(_jaw_rot(Vector((pt.x, pt.y, min(pt.z, lim)))))
        jr.append(r)
    parts.append(L.loft('_mandible', jr, True, True))
    # nape: fills behind the jaw so a turned head never opens a gap over the neck
    parts.append(L.uv_sphere('_nape', (0.0, 0.046, 1.610), (0.052, 0.042, 0.048), 18, 12))
    # Brow ridge and zygomatic arch are laid ON the skull surface, not floating in front
    # of it: a tube a centimetre proud of the loft reads as a sausage stuck to the face,
    # which is exactly what the first pass looked like.
    brow = [Vector((0.062, -0.0240, 1.7130)), Vector((0.048, -0.0470, 1.7200)),
            Vector((0.025, -0.0620, 1.7240)), Vector((0.000, -0.0660, 1.7205)),
            Vector((-0.025, -0.0620, 1.7240)), Vector((-0.048, -0.0470, 1.7200)),
            Vector((-0.062, -0.0240, 1.7130))]
    parts.append(L.tube('_brow', brow, [(0.0110, 0.0098)] * 7, 10, up_hint=(0, 0, 1)))
    for s in (1, -1):
        ck = [Vector((0.023 * s, -0.0620, 1.6830)), Vector((0.046 * s, -0.0480, 1.6880)),
              Vector((0.062 * s, -0.0260, 1.6915)), Vector((0.067 * s, 0.0160, 1.6870))]
        parts.append(L.tube('_cheek_%d' % s, ck, [(0.0090, 0.0088), (0.0102, 0.0100),
                                                  (0.0100, 0.0098), (0.0085, 0.0082)], 8,
                            up_hint=(0, 0, 1)))
    # nose: bridge -> tip -> underside, with alar wings
    nose = [Vector((0, -0.0690, 1.7240)), Vector((0, -0.0765, 1.7080)),
            Vector((0, -0.0865, 1.6890)), Vector((0, -0.0965, 1.6750)),
            Vector((0, -0.0930, 1.6655)), Vector((0, -0.0780, 1.6625))]
    parts.append(L.tube('_nose', nose,
                        [(0.0070, 0.0082), (0.0080, 0.0102), (0.0106, 0.0122),
                         (0.0128, 0.0124), (0.0152, 0.0112), (0.0168, 0.0102)], 12,
                        up_hint=(0, 0, 1)))
    # ears
    for s in (1, -1):
        parts.append(L.uv_sphere('_ear_%d' % s, (0.0740 * s, 0.0390, 1.6930),
                                 (0.0095, 0.0165, 0.0290), 14, 12))
    return parts


def _nose_guard(p):
    """Keep the socket blobs off the nose: without this the widened eye sockets meet in
    the middle and eat the dorsum, leaving a smashed-in midface."""
    return not (abs(p.x) < 0.0215 and p.y < -0.0600 and p.z < 1.7300)


def sculpt_head(ob):
    """Base gaunt pass, shared by all three variants (the bake is shared too).

    Blob centres sit ~10 mm *behind* the surface they are carving: `blob` displaces
    radially from its centre, so a centre placed on the surface does nothing.
    """
    for s in (1, -1):
        # --- eye socket: dug deep, then ringed by a proud orbital rim so the recess has
        # a hard edge.  A soft gaussian dent alone just reads as a smooth dip.
        L.blob(ob, (0.0335 * s, -0.0450, 1.7020), 0.0300, -0.0250,
               ellipse=(1.25, 1.05, 0.95), only=_nose_guard)
        rim = []
        for k in range(17):
            a = TAU * k / 16
            rim.append((0.0335 * s + 0.0275 * math.cos(a) * s, -0.0560,
                        1.7020 + 0.0235 * math.sin(a)))
        blob_line(ob, rim, 0.0090, 0.0075, direction=(0, -1, 0))
        # re-deepen afterwards so the rim does not fill the socket back in
        L.blob(ob, (0.0335 * s, -0.0440, 1.7020), 0.0215, -0.0110,
               ellipse=(1.15, 1.0, 0.92), only=_nose_guard)
        # heavy upper-lid shelf and a lower-lid crease
        L.blob(ob, (0.0335 * s, -0.0430, 1.7150), 0.0150, -0.0075, only=_nose_guard)
        blob_line(ob, [(0.0170 * s, -0.0530, 1.6895), (0.0350 * s, -0.0510, 1.6870),
                       (0.0500 * s, -0.0430, 1.6900)], 0.0070, -0.0045)
        # temple hollow behind the orbital rim
        L.blob(ob, (0.0600 * s, -0.0120, 1.7300), 0.0300, -0.0175, ellipse=(1, 1.30, 1.15))
        L.blob(ob, (0.0650 * s, -0.0040, 1.7460), 0.0320, -0.0110, ellipse=(1, 1.2, 1))
        # gaunt cheek hollow under the zygomatic
        L.blob(ob, (0.0460 * s, -0.0420, 1.6650), 0.0290, -0.0230, ellipse=(1, 1, 1.25))
        L.blob(ob, (0.0530 * s, -0.0180, 1.6570), 0.0245, -0.0145, ellipse=(1, 1.2, 1))
        # ear concha
        L.blob(ob, (0.0775 * s, 0.0390, 1.6940), 0.0135, -0.0080, direction=(-s, 0, 0))
        # jaw line crease
        blob_line(ob, [_jaw_rot((0.0700 * s, 0.0320, 1.6420)),
                       _jaw_rot((0.0670 * s, -0.0120, 1.6180)),
                       _jaw_rot((0.0440 * s, -0.0560, 1.6020))], 0.0105, -0.0050)
    # --- midface ------------------------------------------------------------------
    # The nose is built as a loft part, so all it needs here is a nostril and a crease;
    # piling extra blobs on top of it is what turned the first pass into a lump.
    for s in (1, -1):
        L.blob(ob, (0.0105 * s, -0.0870, 1.6650), 0.0080, -0.0075,
               direction=(0, 1, -0.45))                           # nostril
        # alar crease: kept shallow.  Deeper than this and the lofted nose part reads as
        # a separate lump welded on, with a visible seam round it.
        blob_line(ob, [(0.0195 * s, -0.0830, 1.6750), (0.0215 * s, -0.0760, 1.6685)],
                  0.0065, -0.0026)
        # blend the nose wall into the cheek so the union seam disappears
        L.blob(ob, (0.0180 * s, -0.0790, 1.6880), 0.0140, 0.0022,
               direction=(0.55 * s, -0.8, 0.1))
    # Dorsum: a narrow raised ridge down the bridge with the side walls pulled in under
    # it.  Without this the lofted nose part has no edge anywhere and reads as a soft
    # lump welded to the face at close range (the residual half of review #1).
    blob_line(ob, [(0.0, -0.0705, 1.7250), (0.0, -0.0785, 1.7080),
                   (0.0, -0.0880, 1.6890), (0.0, -0.0960, 1.6775)], 0.0062, 0.0026,
              ellipse=(0.40, 1, 1), direction=(0, -1, 0.12))
    for s in (1, -1):
        blob_line(ob, [(0.0130 * s, -0.0670, 1.7230), (0.0145 * s, -0.0770, 1.7020),
                       (0.0160 * s, -0.0865, 1.6845)], 0.0068, -0.0028,
                  direction=(0.88 * s, -0.45, 0))
    # tip ball, and the shadow under it where the columella meets the philtrum
    L.blob(ob, (0.0, -0.0930, 1.6760), 0.0098, 0.0022, direction=(0, -1, -0.22))
    L.blob(ob, (0.0, -0.0845, 1.6640), 0.0082, -0.0032, direction=(0, -1, -0.55))
    # narrow the bridge between the brows
    L.blob(ob, (0.0, -0.0560, 1.7150), 0.0150, -0.0040, ellipse=(0.42, 1, 1))
    # philtrum
    L.blob(ob, (0.0, -0.0715, 1.6480), 0.0075, -0.0035)
    # --- lip recession -------------------------------------------------------------
    # BO2 zombies do not smile: the lips have dried and pulled back off the teeth, so
    # the upper lip rolls UP off the gum ridge and the lower one drops away from it.
    blob_line(ob, [(0.0320, -0.0600, 1.6470), (0.0165, -0.0672, 1.6515),
                   (0.0000, -0.0700, 1.6525), (-0.0165, -0.0672, 1.6515),
                   (-0.0320, -0.0600, 1.6470)], 0.0090, 0.0060,
              direction=(0, 0.45, 1.0))
    # lower lip recedes off the mandible
    blob_line(ob, [_jaw_rot((0.0280, -0.0580, 1.6225)), _jaw_rot((0.0142, -0.0650, 1.6250)),
                   _jaw_rot((0.0000, -0.0676, 1.6260)),
                   _jaw_rot((-0.0142, -0.0650, 1.6250)),
                   _jaw_rot((-0.0280, -0.0580, 1.6225))], 0.0090, 0.0060,
              direction=(0, 0.35, -1.0))
    # The corners of the mouth are still SEALED by dried lip.  An earlier pass carved them
    # back into a rictus, which left an unbroken row of teeth from corner to corner - the
    # cartoon grin the review filed.  Only the central ~35 mm of the arch is exposed now.
    for s in (1, -1):
        L.blob(ob, (0.0345 * s, -0.0575, 1.6395), 0.0150, 0.0082,
               direction=(0.30 * s, -1, 0.10))
        L.blob(ob, (0.0300 * s, -0.0620, 1.6360), 0.0105, -0.0032)   # crease under it
    # nasolabial fold
    for s in (1, -1):
        blob_line(ob, [(0.0245 * s, -0.0660, 1.6720), (0.0330 * s, -0.0580, 1.6560)],
                  0.0075, -0.0060)
    # brow furrow
    L.blob(ob, (0.0, -0.0580, 1.7300), 0.0160, -0.0070)
    # occiput
    L.blob(ob, (0.0, 0.0850, 1.7050), 0.0450, 0.0050, direction=(0, 1, 0))
    # hollow the mouth cavity out behind the teeth
    L.blob(ob, (0.0, -0.0300, 1.6200), 0.0340, -0.0130, ellipse=(1.4, 1, 0.8))
    L.noise_displace(ob, scale=95, amount=0.0014, seed=7)
    L.noise_displace(ob, scale=30, amount=0.0019, seed=3)


# --- per-variant faces ------------------------------------------------------------------
# A: gaunt older man, torn right cheek showing molars.
# B: a woman - narrower jaw, higher cheekbone, smaller brow, softer chin; brow-bone gash.
# C: heavy square soldier's jaw; the left side of the mandible is shot away.

FACE_VARIANTS = {
    'A': dict(seed=11, jaw_w=1.00, jaw_len=0.000, brow=1.15, nose=0.004, chin=0.004,
              cheek=1.00),
    'B': dict(seed=27, jaw_w=0.90, jaw_len=-0.004, brow=0.62, nose=-0.003, chin=-0.003,
              cheek=1.22),
    'C': dict(seed=43, jaw_w=1.10, jaw_len=0.003, brow=1.25, nose=0.002, chin=0.006,
              cheek=0.92),
}


def variant_face(ob, V):
    """Re-shape the shared head into a distinct individual, then add one asymmetric
    facial wound.  Runs after the UV/bake so all three heads keep one material."""
    f = FACE_VARIANTS[V]
    rnd = random.Random(f['seed'])
    # jaw width / length
    L.scale_region(ob, (0.0, -0.020, 1.615), 0.095, f['jaw_w'], ellipse=(1, 1.3, 1.0),
                   axis_mask=(1, 0, 0))
    if abs(f['jaw_len']) > 1e-4:
        L.blob(ob, (0.0, -0.0750, 1.612), 0.045, f['jaw_len'], direction=(0, -1, 0))
    # brow heaviness
    for s in (1, -1):
        L.blob(ob, (0.0330 * s, -0.0560, 1.7230), 0.0290,
               0.0060 * (f['brow'] - 1.0), direction=(0, -1, 0.2))
        # cheekbone projection
        L.blob(ob, (0.0545 * s, -0.0400, 1.6880), 0.0250,
               0.0075 * (f['cheek'] - 1.0), direction=(s * 0.6, -0.8, 0))
    # nose length / chin projection
    L.blob(ob, (0.0, -0.0940, 1.6740), 0.0190, f['nose'], direction=(0, -1, 0))
    L.blob(ob, _jaw_rot((0.0, -0.0790, 1.5990)), 0.0230, f['chin'], direction=(0, -1, -0.3))
    # a little asymmetry everywhere - nobody's face is mirrored
    for i in range(6):
        p = (rnd.uniform(-0.062, 0.062), rnd.uniform(-0.080, 0.040),
             rnd.uniform(1.600, 1.780))
        L.blob(ob, p, rnd.uniform(0.016, 0.030), rnd.uniform(-0.0045, 0.0035))
    L.noise_displace(ob, scale=44, amount=0.0014, seed=f['seed'])

    # ---- the one big asymmetric injury ------------------------------------------
    if V == 'A':
        # torn right cheek: the flesh is gone, the molars show through the side
        L.blob(ob, (-0.0520, -0.0380, 1.6560), 0.0270, -0.0210, ellipse=(1, 1, 1.35))
        L.blob(ob, (-0.0460, -0.0500, 1.6640), 0.0160, -0.0130)
    elif V == 'B':
        # split brow - the bone shows through above the left eye
        blob_line(ob, [(0.0180, -0.0600, 1.7330), (0.0430, -0.0510, 1.7250),
                       (0.0560, -0.0330, 1.7180)], 0.0105, -0.0130)
        L.blob(ob, (0.0330, -0.0540, 1.7270), 0.0210, -0.0060)
    else:
        # the left side of the jaw is shot away
        L.blob(ob, _jaw_rot((0.0540, -0.0430, 1.6050)), 0.0330, -0.0290,
               ellipse=(1, 1, 1.2))
        L.blob(ob, _jaw_rot((0.0460, -0.0620, 1.6120)), 0.0220, -0.0180)
    return ob


FACE_WOUND = {
    'A': ((-0.0520, -0.0400, 1.6570), 0.030),
    'B': ((0.0370, -0.0520, 1.7270), 0.026),
    'C': (_jaw_rot((0.0520, -0.0460, 1.6070)), 0.034),
}


def face_wound_faces(ob, V):
    """Faces inside the variant's facial injury -> gore material."""
    c, r = FACE_WOUND[V]
    c = Vector(c)
    return [i for i, p in enumerate(ob.data.polygons) if (p.center - c).length < r]


# --- teeth + gums ----------------------------------------------------------------------

TOOTH_SEEDS = {'A': 5, 'B': 19, 'C': 31}


def build_teeth(V='A'):
    """Individual teeth on an elliptical arch, jittered, with 2-3 missing per head."""
    rnd = random.Random(TOOTH_SEEDS.get(V, 5))
    parts = []
    specs = [(MOUTH_ROOF, -0.0150, 0, 9),      # upper: hang from the maxilla
             (LOWER_GUM, 0.0132, 1, 9)]        # lower: sit on the mandible
    for (ztop, dz, lower, count) in specs:
        missing = set()
        while len(missing) < (2 if lower else 3):
            missing.add(rnd.randrange(count))
        if rnd.random() < 0.5:
            missing.add(rnd.randrange(count))
        for i in range(count):
            if i in missing:
                continue
            inset = rnd.uniform(0.0, 0.0015)
            x, y, t = tooth_arc(i, count, inset)
            centre = abs(i - (count - 1) / 2.0) < 1.6
            h = abs(dz) * (1.0 if centre else 0.74) * rnd.uniform(0.86, 1.06)
            w = (0.0086 if centre else 0.0078) * rnd.uniform(0.92, 1.06)
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.scale(bm, vec=Vector((w, 0.0082, h)), verts=bm.verts)
            # taper toward the biting edge
            for v in bm.verts:
                if (v.co.z < 0) != bool(lower):
                    v.co.x *= 0.74
                    v.co.y *= 0.82
            me = bpy.data.meshes.new('_tooth%d%d' % (lower, i))
            bm.to_mesh(me); bm.free()
            o = bpy.data.objects.new('_tooth%d%d' % (lower, i), me)
            bpy.context.scene.collection.objects.link(o)
            o.location = (x, y, ztop + (h * 0.5 if lower else -h * 0.5))
            o.rotation_euler = (math.radians((6 if lower else -6) + rnd.uniform(-5, 5)),
                                math.radians(rnd.uniform(-6, 6)),
                                -t * 0.85 + math.radians(rnd.uniform(-6, 6)))
            L.activate(o)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            if lower:
                for v in o.data.vertices:
                    v.co = _jaw_rot(v.co)
            parts.append(o)
    return L.join(parts, '_teeth_' + V)


def build_gums(V='A'):
    """The gum ridge behind the receded lips - what makes the mouth read as a dead
    person's rather than a jack-o-lantern's."""
    parts = []
    for lower in (0, 1):
        path, radii = [], []
        n = 11
        for i in range(n):
            x, y, t = tooth_arc(i, n, -0.0015)
            z = (LOWER_GUM + 0.0058) if lower else (MOUTH_ROOF - 0.0052)
            p = Vector((x, y + 0.0035, z))
            path.append(_jaw_rot(p) if lower else p)
            radii.append((0.0052, 0.0072))
        parts.append(L.tube('_gum%d' % lower, path, radii, 7, up_hint=(0, 0, 1)))
    # Tongue: shrunken, dry, and pushed well BACK into the floor of the mouth.  It used to
    # reach y = -0.070, i.e. out past the lip line, and lolled out of the crawler's mouth
    # as a bright red slab.
    tg = L.uv_sphere('_tongue', (0, -0.0215, 1.6315), (0.0135, 0.0235, 0.0055), 10, 6)
    for v in tg.data.vertices:
        v.co = _jaw_rot(v.co)
    ob = L.join(parts, '_gums_' + V)
    return ob, tg


def build_eyes(name='eyes'):
    """Smaller and set deeper, so the upper lid shelf occludes the top of the glow."""
    a = L.icosphere('_eyeL', EYE_L, 0.0092, 2)
    b = L.icosphere('_eyeR', EYE_R, 0.0092, 2)
    return L.join([a, b], name)


def mouth_faces(ob):
    """Faces lining the mouth cavity -> gore material (inside only, never the lips).

    The old ellipsoid reached forward to y = -0.088, i.e. past the lip line, so every
    side-facing face on the lips and the mouth corners picked up the gore material: that
    red band round the outside of the mouth was half of the 'clown grin' the review filed.
    Nothing in front of y = -0.058 can be inside the mouth, so it is hard-clipped.
    """
    c0 = Vector((0.0, -0.030, 1.617))
    rad = Vector((0.044, 0.040, 0.026))
    out = []
    for i, poly in enumerate(ob.data.polygons):
        c = poly.center
        if c.y < -0.058:
            continue
        rel = Vector(((c.x - c0.x) / rad.x, (c.y - c0.y) / rad.y, (c.z - c0.z) / rad.z))
        if rel.length < 1.0 and poly.normal.y > -0.35:
            out.append(i)
    return out


# ---------------------------------------------------------------------------------------
# body sculpting (after remesh, on uniform topology)
# ---------------------------------------------------------------------------------------

def blob_line(ob, pts, radius, amount, direction=None, ellipse=(1, 1, 1), steps=None):
    pts = [Vector(p) for p in pts]
    n = steps or max(2, int(sum((b - a).length for a, b in zip(pts, pts[1:])) / (radius * 0.45)))
    total = len(pts) - 1
    for i in range(n + 1):
        t = i / n * total
        k = min(int(t), total - 1)
        f = t - k
        p = pts[k].lerp(pts[k + 1], f)
        L.blob(ob, p, radius, amount, direction, ellipse=ellipse)


def _rib_arcs(ob, count=6, amount=0.0105, hollow=-0.0075, z0=1.318):
    for i in range(count):
        z = z0 - i * 0.040
        for s in (1, -1):
            pts = [(0.012 * s, -0.104 + i * 0.006, z + 0.014),
                   (0.074 * s, -0.088 + i * 0.006, z + 0.004),
                   (0.130 * s, -0.030 + i * 0.004, z - 0.012),
                   (0.142 * s, 0.028, z - 0.030)]
            blob_line(ob, pts, 0.021, amount, ellipse=(1, 1, 0.70))
            blob_line(ob, [(p[0], p[1], p[2] - 0.021) for p in pts], 0.016, hollow,
                      ellipse=(1, 1, 0.75))


def sculpt_body(ob):
    # --- spine groove
    blob_line(ob, [(0, 0.100, 1.060), (0, 0.094, 1.200), (0, 0.090, 1.330),
                   (0, 0.096, 1.430)], 0.026, -0.010, ellipse=(0.75, 1, 1))
    # --- shoulder blades
    for s in (1, -1):
        blob_line(ob, [(0.048 * s, 0.098, 1.400), (0.100 * s, 0.088, 1.365),
                       (0.080 * s, 0.086, 1.300)], 0.034, 0.009)
    # --- ribs: six arcs each side, emaciated so they read strongly
    _rib_arcs(ob)
    # sternum groove between the pectorals
    blob_line(ob, [(0, -0.112, 1.370), (0, -0.108, 1.245)], 0.016, -0.005)
    for s in (1, -1):
        L.blob(ob, (0.058 * s, -0.112, 1.330), 0.046, 0.005)       # wasted pectoral
    # --- collarbones: a real ridge from the sternal notch out to the acromion
    for s in (1, -1):
        blob_line(ob, [(0.014 * s, -0.072, 1.452), (0.082 * s, -0.064, 1.446),
                       (0.150 * s, -0.030, 1.436)], 0.017, 0.010)
        blob_line(ob, [(0.014 * s, -0.062, 1.428), (0.082 * s, -0.054, 1.422),
                       (0.150 * s, -0.022, 1.412)], 0.015, -0.006)   # hollow beneath it
    # --- pit of the neck
    L.blob(ob, (0, -0.058, 1.452), 0.024, -0.012)
    # --- sterno-mastoid cords up the neck
    for s in (1, -1):
        blob_line(ob, [(0.020 * s, -0.048, 1.460), (0.036 * s, -0.030, 1.530),
                       (0.044 * s, 0.006, 1.586)], 0.011, 0.005)
    # --- abdomen: hollow belly, iliac crests, glutes
    L.blob(ob, (0, -0.104, 1.118), 0.055, -0.014, ellipse=(1.3, 1, 1.2))
    blob_line(ob, [(0, -0.100, 1.170), (0, -0.098, 1.055)], 0.013, -0.006)
    for s in (1, -1):
        L.blob(ob, (0.106 * s, -0.070, 1.030), 0.030, 0.009)          # iliac crest
        L.blob(ob, (0.088 * s, 0.080, 0.912), 0.052, 0.011)           # glute
        L.blob(ob, (0.050 * s, -0.020, 0.862), 0.034, -0.014)         # inguinal shadow
    # --- crotch: carve the fused block into two thighs
    blob_line(ob, [(0, 0.030, 0.845), (0, -0.030, 0.836)], 0.030, -0.020,
              ellipse=(0.55, 1, 1))
    # --- deltoids, biceps, triceps
    for s in (1, -1):
        L.blob(ob, (0.185 * s, 0.000, 1.440), 0.055, 0.010)           # deltoid cap
        L.blob(ob, (0.196 * s, -0.030, 1.330), 0.038, 0.007)          # biceps
        L.blob(ob, (0.210 * s, 0.024, 1.310), 0.034, 0.005)           # triceps
        L.blob(ob, (0.152 * s, 0.006, 1.372), 0.030, -0.008)          # armpit hollow
        L.blob(ob, (0.258 * s, -0.016, 1.150), 0.024, -0.005)         # elbow crease
        L.blob(ob, (0.268 * s, -0.048, 1.048), 0.030, 0.006)          # forearm belly
    # --- knees / shins / calves / ankles
    for s in (1, -1):
        x = 0.100 * s
        L.blob(ob, (x, -0.044, 0.492), 0.032, 0.008)                  # patella
        L.blob(ob, (x, 0.008, 0.498), 0.038, -0.006)                  # knee sides pinched
        L.blob(ob, (x, 0.048, 0.392), 0.050, 0.012)                   # calf belly
        blob_line(ob, [(x, -0.038, 0.420), (x, -0.032, 0.150)], 0.015, 0.005)  # tibia ridge
        L.blob(ob, (x, 0.032, 0.560), 0.040, -0.009)                  # hamstring hollow
        L.blob(ob, (x, 0.012, 0.150), 0.036, -0.008, ellipse=(1, 1, 1.4))  # ankle pinch
        L.blob(ob, (x + 0.028 * s, 0.012, 0.128), 0.018, 0.006)       # lateral malleolus
        L.blob(ob, (x - 0.026 * s, 0.014, 0.136), 0.016, 0.006)       # medial malleolus
        # inner thigh gap
        L.blob(ob, (0.038 * s, -0.010, 0.760), 0.048, -0.012, ellipse=(1, 1.2, 1.4))
    # --- wounds (shared table)
    for w in all_wounds():
        L.blob(ob, w['c'], w['r'], w['d'], ellipse=w.get('ell', (1, 1, 1)))
    L.noise_displace(ob, scale=55, amount=0.0028, seed=11)
    L.noise_displace(ob, scale=16, amount=0.0034, seed=5)


def variant_body(ob, V):
    """Small per-variant re-proportioning.  Kept under ~10 mm so the shared clothing
    still fits, but enough to break the 'three clones' read at 10 m."""
    spec = {'A': (0.0, 1.00, 1.00), 'B': (-0.012, 0.87, 0.94), 'C': (0.008, 1.06, 1.04)}[V]
    dx, shoulder, limb = spec
    L.scale_region(ob, (0.0, 0.006, 1.420), 0.175, shoulder, ellipse=(1.6, 1, 0.9),
                   axis_mask=(1, 0, 0))
    L.scale_region(ob, (0.0, 0.000, 1.180), 0.180, limb, ellipse=(1.4, 1, 1.4),
                   axis_mask=(1, 1, 0))
    if V == 'B':
        # A woman's silhouette.  The first pass moved these numbers by 4-10 % and she
        # still read as a man in a smock at game framing, so they are roughly doubled:
        # the ratio that reads is shoulder-to-hip, not any single measurement.
        L.scale_region(ob, (0.0, 0.010, 0.920), 0.165, 1.16, ellipse=(1.4, 1, 0.9),
                       axis_mask=(1, 1, 0))                      # hips + seat
        L.scale_region(ob, (0.0, 0.000, 1.155), 0.110, 0.88, ellipse=(1.3, 1, 1.0),
                       axis_mask=(1, 1, 0))                      # waist nipped in
        L.scale_region(ob, (0.0, 0.006, 1.520), 0.075, 0.90, ellipse=(1, 1, 1.4),
                       axis_mask=(1, 1, 0))                      # slender neck
        for s in (1, -1):
            L.blob(ob, (0.062 * s, -0.110, 1.302), 0.062, 0.026,
                   direction=(0.25 * s, -1, -0.20))              # bust
            L.blob(ob, (0.062 * s, -0.100, 1.250), 0.038, -0.009)  # under-bust shadow
            L.blob(ob, (0.116 * s, 0.020, 0.940), 0.070, 0.012)  # hip / trochanter
            L.blob(ob, (0.070 * s, -0.020, 1.180), 0.055, -0.010)  # waist hollow
        L.blob(ob, (0.0, -0.106, 1.086), 0.055, -0.006)
    if V == 'C':
        for s in (1, -1):
            L.blob(ob, (0.190 * s, 0.000, 1.438), 0.052, 0.008)   # heavier deltoids
            L.blob(ob, (0.100 * s, 0.050, 0.400), 0.046, 0.006)   # heavier calves
    # one dropped shoulder each, different side per variant
    drop_s = {'A': 1, 'B': -1, 'C': 1}[V]
    L.blob(ob, (0.170 * drop_s, 0.004, 1.452), 0.085, -0.016, direction=(0, 0, -1))
    L.blob(ob, (-0.170 * drop_s, 0.004, 1.440), 0.070, 0.008, direction=(0, 0, 1))
    if abs(dx) > 1e-4:
        for v in ob.data.vertices:
            v.co.x += dx * max(0.0, min(1.0, (v.co.z - 0.9) / 0.5))
    L.noise_displace(ob, scale=28, amount=0.0020, seed=hash(V) & 0xff)
    return ob


def wound_faces(ob, variant=None):
    """Face indices that should get the gore material."""
    ws = wounds_for(variant) if variant else all_wounds()
    centres = [(Vector(w['c']), w['r'] * 0.80) for w in ws]
    out = []
    for i, p in enumerate(ob.data.polygons):
        c = p.center
        for cc, r in centres:
            if (c - cc).length < r:
                out.append(i)
                break
    return out


def exposed_ribs(ob, w):
    """Carve three torn rib arcs inside an opened chest wound so the hole has anatomy
    in it rather than being a smooth dent."""
    cx, cy, cz = w['c']
    s = 1 if cx >= 0 else -1
    for i in range(3):
        z = cz + 0.030 - i * 0.030
        pts = [(abs(cx) * 0.25 * s, cy - 0.006, z + 0.008),
               (abs(cx) * 0.75 * s, cy + 0.004, z + 0.002),
               ((abs(cx) + 0.020) * s, cy + 0.040, z - 0.012)]
        blob_line(ob, pts, 0.0125, 0.0135, ellipse=(1, 1, 0.65))
        blob_line(ob, [(p[0], p[1], p[2] - 0.014) for p in pts], 0.0100, -0.0090,
                  ellipse=(1, 1, 0.75))
    return ob


# ---------------------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------------------

def stump_bones(z, name='_stumpbone'):
    """Splintered femur ends that stick out of a crawler's severed thighs.

    The cut cap alone reads as a closed lid; a pale bone stub in a ring of gore is what
    makes it read as an amputation.  Built in the `zombie_teeth` (dry bone) material.
    """
    parts = []
    rnd = random.Random(91)
    for s in (1, -1):
        x = 0.0995 * s
        y = -0.003
        top = Vector((x, y, z + 0.006))
        tip = Vector((x + rnd.uniform(-0.006, 0.006), y + rnd.uniform(-0.006, 0.006),
                      z - 0.042))
        parts.append(L.tube('%s_%d' % (name, s), [top, top.lerp(tip, 0.45), tip],
                            [(0.0175, 0.0175), (0.0125, 0.0125), (0.0052, 0.0052)], 8,
                            up_hint=(0, -1, 0)))
        # a splinter beside it
        sp = Vector((x + 0.016 * s, y - 0.012, z - 0.050))
        parts.append(L.tube('%s_sp%d' % (name, s),
                            [top + Vector((0.010 * s, -0.008, 0.0)), sp],
                            [(0.0058, 0.0058), (0.0016, 0.0016)], 6, up_hint=(0, -1, 0)))
    return L.join(parts, name)


def build_base_body(voxel=0.010, dec=0.19):
    parts = [build_torso(), build_yoke(), build_neck()]
    for s in ('L', 'R'):
        parts.append(build_arm(s))
        parts.append(build_leg(s))
        parts.append(build_foot(s))
        parts += build_toes(s)
    ob = L.join(parts, 'zbody')
    L.voxel_remesh(ob, voxel, smooth=True)
    sculpt_body(ob)
    L.activate(ob)
    m = ob.modifiers.new('Sm', 'SMOOTH'); m.factor = 0.5; m.iterations = 1
    bpy.ops.object.modifier_apply(modifier=m.name)
    L.decimate(ob, dec)
    # hands are remeshed separately so the fingers survive a fine voxel size
    extras = []
    for s in ('L', 'R'):
        h = build_hand(s)
        L.voxel_remesh(h, 0.0038, smooth=True)
        L.decimate(h, 0.26)
        extras.append(h)
    extras.append(_neck_stump())
    ob = L.join([ob] + extras, 'zbody')
    return ob


def _neck_stump():
    """Ragged flesh cap + spine stub that reads as gore when the head is popped."""
    parts = []
    rings = []
    rnd = random.Random(4)
    for i, (z, r) in enumerate([(1.582, 0.050), (1.600, 0.048), (1.612, 0.040),
                                (1.618, 0.026), (1.620, 0.008)]):
        pts = []
        n = 18
        for k in range(n):
            a = TAU * k / n
            jag = 1.0 + (rnd.random() - 0.5) * (0.18 if i >= 2 else 0.05)
            zz = z + (rnd.random() - 0.5) * (0.010 if i >= 2 else 0.0)
            pts.append(Vector((math.cos(a) * r * jag, 0.016 + math.sin(a) * r * jag, zz)))
        rings.append(pts)
    parts.append(L.loft('_stump', rings, False, True))
    parts.append(L.uv_sphere('_vert', (0, 0.030, 1.612), (0.016, 0.016, 0.016), 10, 8))
    return L.join(parts, '_stump')


def build_head_mesh(voxel=0.0040, dec=0.185):
    parts = build_head_parts()
    ob = L.join(parts, 'zhead')
    L.voxel_remesh(ob, voxel, smooth=True)
    sculpt_head(ob)
    L.activate(ob)
    m = ob.modifiers.new('Sm', 'SMOOTH'); m.factor = 0.30; m.iterations = 1
    bpy.ops.object.modifier_apply(modifier=m.name)
    L.decimate(ob, dec)
    return ob
