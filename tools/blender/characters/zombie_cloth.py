"""Clothing for the three zombie variants.

Rebuilt for review item #8: every garment has a rolled hem with real thickness, a collar
band, cuffs, buttons and a belt; the soldier gets jump boots, webbing pouches and a
canteen; and each garment is torn open over the body wound it is supposed to reveal so
the gore underneath is actually visible (#6).
"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix

import lib_char as L
import zombie_mesh as ZM
from zombie_rig import J

TAU = math.pi * 2
DEG = math.radians


def _jag(rnd, amp, n, smoothness=2):
    """Loop-closed random offsets per ring vertex."""
    raw = [rnd.uniform(-amp, amp) for _ in range(n)]
    for _ in range(smoothness):
        raw = [(raw[i - 1] + 2 * raw[i] + raw[(i + 1) % n]) * 0.25 for i in range(n)]
    return raw


def _roll_rings(ring, roll=0.0055, steps=4, up=1.0):
    """Curl a hem ring back on itself: a 180 degree fold, inward and (for a bottom hem)
    upward.  This is what separates 'clothed' from 'painted' in silhouette."""
    c = Vector((0, 0, 0))
    for p in ring:
        c += p
    c /= len(ring)
    out = []
    for k in range(1, steps + 1):
        a = math.pi * k / steps
        rad = roll * (1.0 - math.cos(a))
        lift = roll * math.sin(a) * up
        r = []
        for p in ring:
            d = Vector((p.x - c.x, p.y - c.y, 0.0))
            if d.length > 1e-6:
                d.normalize()
            r.append(Vector((p.x - d.x * rad, p.y - d.y * rad, p.z + lift)))
        out.append(r)
    return out


def torso_shell(name, z0, z1, inflate, steps=16, n=26, hem_amp=0.0, hem_seed=1,
                top_amp=0.0, flare=0.0, flare_pow=2.0, exp=2.7, hem_roll=0.0055,
                top_roll=0.0, shape_fn=None):
    """A garment shell over the torso.  `shape_fn(z)` adds extra fullness at a height,
    which is how a garment gets tailoring the shared body table does not have (a bust, a
    nipped waist, a hip spring) - review #8, and the reason variant B read as a sack."""
    rnd = random.Random(hem_seed)
    jag0 = _jag(rnd, hem_amp, n) if hem_amp else [0.0] * n
    jag1 = _jag(rnd, top_amp, n) if top_amp else [0.0] * n
    shape = ZM.superellipse(exp, back=0.96)
    rings = []
    for i in range(steps + 1):
        f = i / steps
        z = z0 + (z1 - z0) * f
        w, d, yc = ZM.torso_profile(z)
        fl = flare * ((1.0 - f) ** flare_pow)
        ex = shape_fn(z) if shape_fn else 0.0
        pts = L.ring((0, yc, z), w + inflate + fl + ex, d + inflate + fl + ex, n,
                     y=(0, 0, 1), shape=shape)
        if i == 0 and hem_amp:
            pts = [Vector((p.x, p.y, p.z + jag0[k])) for k, p in enumerate(pts)]
        if i == steps and top_amp:
            pts = [Vector((p.x, p.y, p.z + jag1[k])) for k, p in enumerate(pts)]
        rings.append(pts)
    pre = _roll_rings(rings[0], hem_roll, up=1.0)[::-1] if hem_roll else []
    post = _roll_rings(rings[-1], top_roll, up=-1.0) if top_roll else []
    return L.loft(name, pre + rings + post, True, True)


def limb_sleeve(name, path, radii, t0, t1, inflate, n=16, hem_amp=0.0, hem_seed=2,
                taper_end=1.0, subdiv=3, cuff_roll=0.0045):
    """A sleeve/trouser leg over a segment of a limb path (t in path-index space)."""
    rnd = random.Random(hem_seed)
    i0 = max(0, int(math.floor(t0)))
    i1 = min(len(path) - 1, int(math.ceil(t1)))
    sub, rad = [], []
    for i in range(i0, i1 + 1):
        sub.append(Vector(path[i]))
        rx, rz = radii[i]
        rad.append((rx + inflate, rz + inflate))
    if rad:
        rad[-1] = (rad[-1][0] * taper_end, rad[-1][1] * taper_end)
    if subdiv > 1:
        fine, frad = [], []
        for i in range(len(sub) - 1):
            for k in range(subdiv):
                f = k / float(subdiv)
                fine.append(sub[i].lerp(sub[i + 1], f))
                frad.append((rad[i][0] + (rad[i + 1][0] - rad[i][0]) * f,
                             rad[i][1] + (rad[i + 1][1] - rad[i][1]) * f))
        fine.append(sub[-1]); frad.append(rad[-1])
        sub, rad = fine, frad
    nroll = 0
    if cuff_roll:
        # a real cuff: the tube folds back on itself at the open end
        d = (sub[-1] - sub[-2]).normalized()
        end = Vector(sub[-1])
        r0 = rad[-1]
        for k in range(1, 4):
            a = math.pi * k / 3.0
            sub.append(end + d * (cuff_roll * math.sin(a)))
            shrink = cuff_roll * (1.0 - math.cos(a)) * 0.9
            rad.append((max(0.005, r0[0] - shrink), max(0.005, r0[1] - shrink)))
            nroll += 1
    ob = L.tube(name, sub, rad, n, up_hint=(0, -1, 0))
    if hem_amp:
        verts = ob.data.vertices
        jag = _jag(rnd, hem_amp, n)
        d = (sub[len(sub) - 1 - nroll] - sub[len(sub) - 2 - nroll]).normalized()
        for r in range(nroll + 1):
            for k in range(n):
                idx = len(verts) - (r + 1) * n + k
                if 0 <= idx < len(verts):
                    verts[idx].co += d * jag[k]
    return ob


# ---------------------------------------------------------------------------------------
# hard-surface dressing
# ---------------------------------------------------------------------------------------

def ring_band(name, z, inflate, height=0.020, n=20, exp=2.7):
    """A closed band around the torso (collar band, waistband, belt)."""
    rings = []
    for f in (0.0, 0.35, 0.65, 1.0):
        zz = z + height * f
        w, d, yc = ZM.torso_profile(zz)
        bulge = inflate + 0.0035 * math.sin(math.pi * f)
        rings.append(L.ring((0, yc, zz), w + bulge, d + bulge, n, y=(0, 0, 1),
                            shape=ZM.superellipse(exp, back=0.96)))
    return L.loft(name, rings, True, True)


def button(name, z, out, r=0.0072, t=0.0030):
    """A disc button on the front placket."""
    w, d, yc = ZM.torso_profile(z)
    y = yc - (d + out)
    return L.tube(name, [Vector((0, y, z)), Vector((0, y - t, z))],
                  [(r, r), (r * 0.85, r * 0.85)], 10, up_hint=(0, 0, 1))


def placket(name, z0, z1, out, w=0.016):
    """The buttoned strip down the front of a shirt."""
    pts, radii = [], []
    n = 6
    for i in range(n):
        z = z0 + (z1 - z0) * i / (n - 1.0)
        ww, d, yc = ZM.torso_profile(z)
        pts.append(Vector((0, yc - (d + out), z)))
        # (depth, width): on a vertical run the tube frame puts rx along -Y, so passing
        # the width first made the placket a blade sticking straight out of the chest.
        radii.append((0.0032, w))
    return L.tube(name, pts, radii, 8, up_hint=(0, 0, 1))


def collar(name, z, out, height=0.038, spread=DEG(26)):
    """A collar band plus two turned-down points at the front."""
    parts = [ring_band(name + '_band', z, out, height * 0.55, n=20)]
    w, d, yc = ZM.torso_profile(z + height * 0.4)
    for s in (1, -1):
        pts = [Vector((0.012 * s, yc - (d + out) - 0.004, z + height)),
               Vector((0.034 * s, yc - (d + out) * 0.92 - 0.002, z + height * 0.55)),
               Vector((0.048 * s, yc - (d + out) * 0.78, z + height * 0.05))]
        parts.append(L.tube(name + '_pt%d' % s, pts,
                            [(0.013, 0.0035), (0.016, 0.0035), (0.010, 0.0030)], 6,
                            up_hint=(0, -1, 0)))
    return L.join(parts, name)


def pocket(name, z, x, out, w=0.048, h=0.058):
    """A patch pocket on the chest."""
    ww, d, yc = ZM.torso_profile(z + h * 0.5)
    y = yc - (d + out)
    rings = []
    for (dy, sw, sh) in ((0.0, 1.0, 1.0), (-0.010, 0.98, 0.99), (-0.013, 0.90, 0.94)):
        pts = []
        for (ax, az) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            pts.append(Vector((x + ax * w * 0.5 * sw, y + dy, z + az * h * 0.5 * sh)))
        rings.append(pts)
    return L.loft(name, rings, True, True)


def buckle(name, z, out, w=0.046, h=0.030, t=0.006):
    ww, d, yc = ZM.torso_profile(z)
    y = yc - (d + out) - 0.004
    parts = []
    for (ox, oz, sx, sz) in ((0, h * 0.5, w, 0.008), (0, -h * 0.5, w, 0.008),
                             (-w * 0.5, 0, 0.008, h), (w * 0.5, 0, 0.008, h)):
        parts.append(L.box_like(name + '_%d' % len(parts), (sx, t, sz), (ox, y, z + oz)))
    parts.append(L.box_like(name + '_pin', (0.006, t * 0.8, h * 0.8), (0, y - 0.002, z)))
    return L.join(parts, name)


def strap(name, pts, w=0.016, t=0.007, n=6):
    return L.tube(name, [Vector(p) for p in pts], [(w, t)] * len(pts), n, up_hint=(0, 0, 1))


def clip(name, s, x, z, out=0.050, back=False):
    """A suspender clip: a small metal tab where the strap meets the waistband."""
    w, d, yc = ZM.torso_profile(z)
    y = yc + (d + out) * (0.88 if back else -0.88)
    return L.box_like(name, (0.020, 0.010, 0.026), (s * x, y, z))


def shoulder_yoke(name, inflate, n=14):
    """Cloth over the trapezius/deltoid mass - without it the shirt leaves bare shoulders."""
    path = [Vector((-0.240, 0.008, 1.370)), Vector((-0.206, 0.006, 1.410)),
            Vector((-0.150, 0.008, 1.452)), Vector((-0.080, 0.011, 1.474)),
            Vector((0.0, 0.012, 1.480)),
            Vector((0.080, 0.011, 1.474)), Vector((0.150, 0.008, 1.452)),
            Vector((0.206, 0.006, 1.410)), Vector((0.240, 0.008, 1.370))]
    radii = [(0.058 + inflate, 0.054 + inflate), (0.068 + inflate, 0.062 + inflate),
             (0.072 + inflate, 0.066 + inflate), (0.062 + inflate, 0.064 + inflate),
             (0.060 + inflate, 0.064 + inflate),
             (0.062 + inflate, 0.064 + inflate), (0.072 + inflate, 0.066 + inflate),
             (0.068 + inflate, 0.062 + inflate), (0.058 + inflate, 0.054 + inflate)]
    return L.tube(name, path, radii, n, up_hint=(0, 0, 1))


def over_shoulder_strap(name, s, out=0.036, w=0.018, t=0.007, top_x=0.150, top_z=1.538):
    """Suspender / webbing: up the chest, over the shoulder, down the back."""
    pts = []
    for (z, xf, yf) in [(1.010, 0.46, -0.84), (1.150, 0.42, -0.90), (1.290, 0.40, -0.90),
                        (1.390, 0.42, -0.78)]:
        ww, dd, yc = ZM.torso_profile(z)
        pts.append(Vector((s * xf * (ww + out), yc + yf * (dd + out), z)))
    pts.append(Vector((s * top_x * 0.92, -0.030, top_z - 0.012)))
    pts.append(Vector((s * top_x, 0.010, top_z)))
    pts.append(Vector((s * top_x * 0.94, 0.048, top_z - 0.016)))
    for (z, xf, yf) in [(1.380, 0.44, 0.82), (1.250, 0.42, 0.90), (1.120, 0.42, 0.92),
                        (1.010, 0.46, 0.88)]:
        ww, dd, yc = ZM.torso_profile(z)
        pts.append(Vector((s * xf * (ww + out), yc + yf * (dd + out), z)))
    # (t, w): the cross-section frame puts rx along the depth axis on the vertical
    # runs, so passing (w, t) made every suspender a blade sticking out of the chest.
    return L.tube(name, pts, [(t, w)] * len(pts), 8, up_hint=(0, 0, 1))


def rumple(ob, seed=0, big=0.008, fine=0.0018):
    """Fabric never hangs smooth: low-frequency sag plus fine creases."""
    L.noise_displace(ob, scale=9.0, amount=big, seed=seed)
    L.noise_displace(ob, scale=42.0, amount=fine, seed=seed + 7)
    return ob


def _ring_fold(ob, z, cx, cy, r, amount, band=0.16):
    """A horizontal fold ring: vertices within `band*r` of height z move radially in or
    out from the limb/torso axis.  Negative = the groove, positive = the roll above it."""
    L.blob(ob, (cx, cy, z), r, amount, ellipse=(1, 1, band))


def folds(ob, kind, seed=0):
    """Structural fabric folds, on top of `rumple`'s noise (review #8).

    Noise alone reads as a crumpled paper bag: real cloth breaks in a few places for
    mechanical reasons - it bunches where it is belted, it stacks above the knee and the
    boot, it drags diagonally from the shoulder point to the opposite hip - and every
    break is a roll with a shadow under it, never a dent on its own.  Each fold here is
    therefore authored as a groove plus the roll that sits above it.
    """
    rnd = random.Random(seed)
    if kind == 'top':
        # bunching where the shirt/dress is tucked or belted
        for z, a in ((1.062, -0.0085), (1.092, 0.0060), (1.124, -0.0070),
                     (1.156, 0.0045), (1.192, -0.0045)):
            w, d, yc = ZM.torso_profile(z)
            _ring_fold(ob, z, 0.0, yc, 0.235, a, 0.085)
        # diagonal drape from each shoulder point across to the opposite waist
        for s in (1, -1):
            pts = []
            for i in range(5):
                f = i / 4.0
                z = 1.430 - 0.300 * f
                w, d, yc = ZM.torso_profile(z)
                x = s * (0.150 - 0.230 * f)
                pts.append((x, yc - (d + 0.026) * (1.0 - 0.55 * f * f), z))
            ZM.blob_line(ob, pts, 0.030, -0.0050)
            ZM.blob_line(ob, [(x, y, z + 0.022) for (x, y, z) in pts], 0.026, 0.0032)
        # armpit crush: the sleeve head always collapses into the pit
        for s in (1, -1):
            w, d, yc = ZM.torso_profile(1.360)
            L.blob(ob, (s * 0.152, yc - 0.020, 1.352), 0.052, -0.0070,
                   ellipse=(1, 1.4, 1))
            L.blob(ob, (s * 0.150, yc - 0.010, 1.398), 0.044, 0.0040)
        # elbow crook on each sleeve
        for side, s in (('L', 1), ('R', -1)):
            e = J['elbow_' + side]
            L.blob(ob, (e.x, e.y + 0.020, e.z), 0.055, -0.0060, ellipse=(1, 1, 1.25))
            L.blob(ob, (e.x, e.y - 0.014, e.z + 0.030), 0.044, 0.0040)
    elif kind == 'bottom':
        # seat and groin drag
        w, d, yc = ZM.torso_profile(0.900)
        for s in (1, -1):
            ZM.blob_line(ob, [(s * 0.028, yc - d - 0.020, 0.900),
                              (s * 0.072, yc - d - 0.006, 0.960),
                              (s * 0.104, yc - d * 0.55, 1.000)], 0.028, -0.0050)
        _ring_fold(ob, 0.960, 0.0, yc, 0.230, 0.0045, 0.10)
        for side in ('L', 'R'):
            kn = J['knee_' + side]
            an = J['ankle_' + side]
            # stacked bunching above the knee, and again where the hem breaks on the shoe
            for dz, a in ((0.112, -0.0060), (0.078, 0.0045), (0.046, -0.0055),
                          (0.016, 0.0040)):
                _ring_fold(ob, kn.z + dz, kn.x, kn.y, 0.108, a, 0.14)
            for dz, a in ((0.126, -0.0050), (0.092, 0.0040), (0.058, -0.0045)):
                _ring_fold(ob, an.z + dz, an.x, an.y, 0.098, a, 0.14)
    return ob


def tear_open(ob, wounds, seed=0):
    """Cut the garment open over every wound flagged `hole`, then give the torn edge a
    wall of fabric so it does not read as a decal.

    `L.punch_hole` sweeps a tube along the wound's outward axis and then snaps the
    surviving rim onto a ragged ellipse, so the cut follows the curve instead of the quad
    grid.  The previous `delete_region` call left an axis-aligned stair-stepped rectangle
    - the flagship failure of review #6's repair round.
    """
    cut = 0
    for i, w in enumerate(wounds):
        if not w.get('hole'):
            continue
        cut += L.punch_hole(ob, w['c'], ZM.hole_axis(w), w['hole'],
                            jag=0.26, seed=seed + i * 17, depth=0.15, flap=0.0030)
    if cut:
        # a real wall of fabric round the tear, deep enough to catch the key light
        L.rim_boundary(ob, 0.011, seed=seed, jag=0.55)
    return cut


# ---------------------------------------------------------------------------------------
# footwear
# ---------------------------------------------------------------------------------------

SOLE = [(0.086, 0.028), (0.062, 0.038), (0.026, 0.043), (-0.026, 0.045),
        (-0.082, 0.046), (-0.136, 0.044), (-0.182, 0.037), (-0.208, 0.024)]


def shoe(side, kind='shoe'):
    """A real 1950s shoe: last-shaped sole, welt, heel block, rounded toe cap and a
    laced upper.  The old wedge was the worst silhouette element below the waist."""
    x = J['ankle_' + side].x
    parts = []
    sole_z = 0.011 if kind == 'shoe' else 0.013
    # --- sole
    parts.append(L.tube('_sole_' + side, [Vector((x, y, sole_z)) for y, w in SOLE],
                        [(w, sole_z * 0.92) for y, w in SOLE], 14, up_hint=(0, 0, 1)))
    # --- welt: a narrow proud rim where the upper is stitched to the sole
    parts.append(L.tube('_welt_' + side,
                        [Vector((x, y, sole_z * 2.0)) for y, w in SOLE],
                        [(w + 0.0035, 0.0040) for y, w in SOLE], 14, up_hint=(0, 0, 1)))
    # --- upper: heel counter -> instep -> toe cap
    up = [(0.076, 0.030, 0.050), (0.052, 0.038, 0.050), (0.016, 0.041, 0.048),
          (-0.028, 0.041, 0.044), (-0.080, 0.040, 0.038), (-0.132, 0.038, 0.032),
          (-0.176, 0.033, 0.026), (-0.202, 0.020, 0.017)]
    parts.append(L.tube('_upper_' + side,
                        [Vector((x, y, sole_z * 1.4 + h * 0.45)) for y, w, h in up],
                        [(w, h) for y, w, h in up], 16, up_hint=(0, 0, 1)))
    # --- toe cap seam
    parts.append(L.tube('_toecap_' + side,
                        [Vector((x - 0.038, -0.118, 0.026)), Vector((x, -0.126, 0.040)),
                         Vector((x + 0.038, -0.118, 0.026))],
                        [(0.0035, 0.0030)] * 3, 6, up_hint=(0, 0, 1)))
    # --- heel block
    hh = 0.024 if kind == 'shoe' else 0.030
    parts.append(L.box_like('_heel_' + side, (0.068, 0.078, hh),
                            (x, 0.052, hh * 0.5 + 0.001)))
    # --- laces across the instep
    for i, yy in enumerate((-0.014, -0.042, -0.070)):
        r = 0.0030
        parts.append(L.tube('_lace_%s_%d' % (side, i),
                            [Vector((x - 0.030, yy, 0.052 - i * 0.004)),
                             Vector((x, yy - 0.004, 0.060 - i * 0.004)),
                             Vector((x + 0.030, yy, 0.052 - i * 0.004))],
                            [(r, r)] * 3, 6, up_hint=(0, 0, 1)))
    if kind == 'boot':
        # Jump-boot shaft up the shin.  It used to run to z = 0.262 and the trouser leg
        # ran all the way down to the ankle over it, so none of this was ever visible and
        # the soldier read as wearing the same low slipper as variant A.  The shaft now
        # tops out at 0.250 and variant_C's trouser is bloused over it at z ~ 0.242.
        shaft = [(0.040, 0.072), (0.032, 0.132), (0.026, 0.190), (0.022, 0.246)]
        parts.append(L.tube('_shaft_' + side,
                            [Vector((x, y, z)) for y, z in shaft],
                            [(0.062, 0.064), (0.060, 0.062), (0.058, 0.060),
                             (0.057, 0.059)], 14, up_hint=(0, -1, 0)))
        # top cuff roll, so the shaft has a lip for the trouser to sit on
        parts.append(L.tube('_bcuff_' + side,
                            [Vector((x, 0.023, 0.236)), Vector((x, 0.022, 0.250))],
                            [(0.062, 0.064), (0.060, 0.062)], 14, up_hint=(0, -1, 0)))
        for i, zz in enumerate((0.104, 0.166, 0.226)):
            parts.append(L.tube('_bstrap_%s_%d' % (side, i),
                                [Vector((x - 0.058, 0.032, zz)),
                                 Vector((x, -0.034, zz + 0.004)),
                                 Vector((x + 0.058, 0.032, zz))],
                                [(0.0050, 0.0070)] * 3, 6, up_hint=(0, 0, 1)))
        # laced speed-hooks up the front of the shaft
        for i, zz in enumerate((0.086, 0.132, 0.178)):
            parts.append(L.tube('_bhook_%s_%d' % (side, i),
                                [Vector((x - 0.026, -0.040, zz)),
                                 Vector((x + 0.026, -0.040, zz + 0.012))],
                                [(0.0030, 0.0030)] * 2, 5, up_hint=(0, 0, 1)))
    ob = L.join(parts, '_shoe_%s_%s' % (side, kind))
    for v in ob.data.vertices:
        if v.co.z < 0.0015:
            v.co.z = 0.0015
    return ob


# ---------------------------------------------------------------------------------------
# variants
# ---------------------------------------------------------------------------------------

def variant_A():
    """1950s townsman: torn work shirt, suspenders, grey slacks, worn shoes."""
    top, bottom, acc = [], [], []
    shirt = torso_shell('_shirt', 0.996, 1.500, 0.026, steps=30, hem_amp=0.032,
                        hem_seed=11, top_amp=0.008, hem_roll=0.0060)
    top.append(shirt)
    top.append(collar('_collarA', 1.462, 0.030, height=0.042))
    top.append(placket('_plkA', 1.010, 1.470, 0.028, w=0.017))
    for i, z in enumerate((1.412, 1.340, 1.268, 1.196, 1.122)):
        top.append(button('_btnA%d' % i, z, 0.032))
    top.append(pocket('_pktA', 1.270, -0.086, 0.028))
    top.append(shoulder_yoke('_yokeA', 0.020))
    for s in ('L', 'R'):
        path, radii = ZM.arm_path(s), ZM._arm_radii()
        cut = 5 if s == 'L' else 4        # right sleeve torn shorter
        top.append(limb_sleeve('_sleeve_' + s, path, radii, 0, cut, 0.017,
                               hem_amp=0.022, hem_seed=20 + ord(s), cuff_roll=0.0050))
    # suspenders over the shoulders, with clips at the waistband
    for s in (1, -1):
        acc.append(over_shoulder_strap('_susp_%d' % s, s, out=0.042, w=0.019, t=0.007))
        acc.append(clip('_clipF%d' % s, s, 0.062, 1.062, out=0.042))
        acc.append(clip('_clipB%d' % s, s, 0.062, 1.058, out=0.042, back=True))
    # slacks
    bottom.append(torso_shell('_waist', 0.840, 1.095, 0.030, steps=16, top_amp=0.006,
                              hem_roll=0.0))
    acc.append(ring_band('_beltA', 1.040, 0.036, 0.026))
    acc.append(buckle('_bkA', 1.053, 0.036))
    for s in ('L', 'R'):
        path, radii = ZM.leg_path(s), ZM._leg_radii()
        cut = 8 if s == 'R' else 6        # left trouser leg torn off at the shin
        bottom.append(limb_sleeve('_trouser_' + s, path, radii, 1, cut, 0.029,
                                  hem_amp=0.026 if cut < 8 else 0.012,
                                  hem_seed=30 + ord(s), taper_end=0.94,
                                  cuff_roll=0.0055))
        acc.append(shoe(s, 'shoe'))
    return top, bottom, acc, []


def _figure_B(z):
    """Dress tailoring: a bust, a nipped waist and a hip spring.

    The body table is shared by all three variants, so without this the dress traced the
    same tube as the soldier's jacket and B read as a man in a smock however feminine the
    face was (review #1 / #8).
    """
    return (0.024 * math.exp(-((z - 1.298) / 0.062) ** 2) +         # bust
            -0.015 * math.exp(-((z - 1.145) / 0.052) ** 2) +        # waist
            0.018 * math.exp(-((z - 0.975) / 0.085) ** 2))          # hips


def variant_B():
    """Housewife: tattered floral day dress with a waist seam, apron, low shoes."""
    top, bottom, acc = [], [], []
    dress = torso_shell('_dress', 0.556, 1.468, 0.030, steps=26, hem_amp=0.058,
                        hem_seed=41, top_amp=0.006, flare=0.120, flare_pow=2.4,
                        hem_roll=0.0060, shape_fn=_figure_B)
    top.append(dress)
    top.append(ring_band('_waistB', 1.052, 0.034, 0.030))     # waist seam / sash
    top.append(collar('_collarB', 1.446, 0.032, height=0.030, spread=DEG(34)))
    for i, z in enumerate((1.400, 1.336, 1.272, 1.208)):
        top.append(button('_btnB%d' % i, z, 0.034, r=0.0058))
    top.append(shoulder_yoke('_yokeB', 0.019))
    for s in ('L', 'R'):
        path, radii = ZM.arm_path(s), ZM._arm_radii()
        top.append(limb_sleeve('_dsleeve_' + s, path, radii, 0, 3, 0.018,
                               hem_amp=0.020, hem_seed=50 + ord(s), cuff_roll=0.0050))
    # Apron: a WAIST apron, not a bib.  The bib version topped out at z = 1.190 and sat
    # straight over her belly wound, so review #6's per-variant open wound did not exist
    # for B in practice (verifier's blocking item).  A waist apron tied at 1.06 leaves the
    # torn dress and the wound under it in clear view, and it is period-correct anyway.
    rings = []
    rnd = random.Random(7)
    n = 16
    for i in range(10):
        f = i / 9.0
        z = 0.640 + (1.075 - 0.640) * f
        w, d, yc = ZM.torso_profile(z)
        # the apron has to sit OUTSIDE the dress, whose own flare is 0.120
        fl = 0.130 * ((1.0 - (z - 0.556) / 0.912) ** 2.4)
        rr = w + 0.058 + _figure_B(z) + fl
        dd = d + 0.058 + _figure_B(z) + fl
        pts = []
        for k in range(n):
            a = -math.pi * 0.46 + math.pi * 0.92 * k / (n - 1.0)
            pts.append(Vector((math.sin(a) * rr * 0.96, yc - math.cos(a) * dd,
                               z + (rnd.uniform(-0.024, 0.0) if i == 0 else 0.0))))
        for k in range(n):
            a = math.pi * 0.46 - math.pi * 0.92 * k / (n - 1.0)
            pts.append(Vector((math.sin(a) * rr * 0.92, yc - math.cos(a) * dd * 0.93,
                               z + (rnd.uniform(-0.024, 0.0) if i == 0 else 0.0))))
        rings.append(pts)
    panel = [L.loft('_apron', rings, True, True)]
    # apron waistband, where the bib straps used to be
    acc.append(ring_band('_apronband', 1.048, 0.056, 0.022, n=20))
    # apron waist ties, hanging loose behind
    for s in (1, -1):
        acc.append(strap('_tie%d' % s,
                         [(s * 0.080, 0.106, 1.070), (s * 0.128, 0.128, 1.020),
                          (s * 0.150, 0.152, 0.940), (s * 0.140, 0.168, 0.860)],
                         w=0.004, t=0.013))
    acc.append(pocket('_pktB', 0.930, -0.060, 0.062, w=0.062, h=0.062))
    for s in ('L', 'R'):
        acc.append(shoe(s, 'shoe'))
    return top, bottom, acc, panel


def variant_C():
    """Soldier: olive fatigues, M1936 webbing, ammo pouches, canteen, jump boots."""
    top, bottom, acc = [], [], []
    top.append(torso_shell('_jacket', 0.950, 1.505, 0.032, steps=30, hem_amp=0.016,
                           hem_seed=61, top_amp=0.006, hem_roll=0.0060))
    top.append(collar('_collarC', 1.462, 0.036, height=0.040))
    top.append(placket('_plkC', 0.985, 1.470, 0.034, w=0.019))
    for i, z in enumerate((1.404, 1.324, 1.244, 1.164, 1.084, 1.004)):
        top.append(button('_btnC%d' % i, z, 0.038, r=0.0068))
    for s in (1, -1):
        top.append(pocket('_pktC%d' % s, 1.246, s * 0.090, 0.034, w=0.062, h=0.066))
        # shoulder epaulette
        top.append(strap('_epa%d' % s,
                         [(s * 0.070, 0.010, 1.482), (s * 0.140, 0.008, 1.466),
                          (s * 0.196, 0.006, 1.430)], w=0.020, t=0.005))
    top.append(shoulder_yoke('_yokeC', 0.026))
    for s in ('L', 'R'):
        path, radii = ZM.arm_path(s), ZM._arm_radii()
        top.append(limb_sleeve('_jsleeve_' + s, path, radii, 0, 7, 0.020,
                               hem_amp=0.014, hem_seed=70 + ord(s), taper_end=0.92,
                               cuff_roll=0.0050))
    bottom.append(torso_shell('_cwaist', 0.836, 1.035, 0.034, steps=14, top_amp=0.004,
                              hem_roll=0.0))
    for s in ('L', 'R'):
        path, radii = ZM.leg_path(s), ZM._leg_radii()
        # stop at station 7 (z ~ 0.254) and flare: paratrooper trousers are bloused OVER
        # the boot top, which is the only way the jump boots are ever seen.
        bottom.append(limb_sleeve('_ctrouser_' + s, path, radii, 1, 7, 0.032,
                                  hem_amp=0.010, hem_seed=80 + ord(s), taper_end=1.30,
                                  cuff_roll=0.0075))
        acc.append(shoe(s, 'boot'))
    # --- M1936 pistol belt + Y harness
    acc.append(ring_band('_belt', 1.030, 0.044, 0.032, n=26))
    acc.append(buckle('_bkC', 1.046, 0.044, w=0.052, h=0.034))
    for s in (1, -1):
        acc.append(over_shoulder_strap('_harness_%d' % s, s, out=0.052, w=0.024, t=0.008,
                                       top_x=0.158, top_z=1.552))
    # --- two ammo pouches on the belt, a canteen on the right hip
    for i, (sx, yy) in enumerate(((1, -0.118), (-1, -0.118))):
        w, d, yc = ZM.torso_profile(1.000)
        p = L.box_like('_pouch%d' % i, (0.092, 0.058, 0.090),
                       (sx * 0.078, yc - d - 0.040, 0.996))
        flap = L.box_like('_pflap%d' % i, (0.096, 0.062, 0.022),
                          (sx * 0.078, yc - d - 0.041, 1.040))
        acc.append(L.join([p, flap], '_pouch%d' % i))
    w, d, yc = ZM.torso_profile(0.985)
    cant = L.tube('_canteen', [Vector((-0.150, yc + d * 0.55, 0.955)),
                               Vector((-0.152, yc + d * 0.55, 1.010))],
                  [(0.046, 0.026), (0.046, 0.026)], 14, up_hint=(0, 0, 1))
    acc.append(cant)
    acc.append(strap('_cantstrap',
                     [(-0.128, yc + d * 0.40, 1.040), (-0.150, yc + d * 0.55, 1.020)],
                     w=0.014, t=0.005))
    return top, bottom, acc, []


def _belt_ring(z, inflate, n=22):
    w, d, yc = ZM.torso_profile(z)
    pts = []
    for i in range(n + 1):
        a = TAU * i / n
        pts.append(Vector((math.cos(a) * (w + inflate), yc - math.sin(a) * (d + inflate), z)))
    return pts


def _arm_radii():
    return ZM._arm_radii()


def _leg_radii():
    return ZM._leg_radii()


# ---------------------------------------------------------------------------------------
# head extras
# ---------------------------------------------------------------------------------------

def _cran(z):
    tbl = ZM.CRANIUM
    if z <= tbl[0][0]:
        return tbl[0][1:]
    if z >= tbl[-1][0]:
        return tbl[-1][1:]
    for a, b in zip(tbl, tbl[1:]):
        if a[0] <= z <= b[0]:
            t = (z - a[0]) / (b[0] - a[0])
            return tuple(a[i + 1] + (b[i + 1] - a[i + 1]) * t for i in range(3))
    return tbl[-1][1:]


def _cran_point(z, az, grow):
    """A point `grow` metres off the cranium at height z and azimuth az.

    az = pi/2 is the face (-Y), az = -pi/2 (or 3pi/2) is the back of the head.
    Below the skull table the radius holds and flares slightly, so hair that hangs past
    the jaw does not collapse onto the neck.
    """
    w, fr, bk = _cran(z)
    if z < ZM.CRANIUM[0][0]:
        grow += (ZM.CRANIUM[0][0] - z) * 0.22
    p = 2.0 / 2.05 - 1.0
    ca, sa = math.cos(az), math.sin(az)
    sx = 0.0 if abs(ca) < 1e-9 else abs(ca) ** p
    sz = 0.0 if abs(sa) < 1e-9 else abs(sa) ** p
    d = (fr if sa > 0 else bk) + grow
    return Vector((ca * sx * (w + grow), ZM.YC - sa * sz * d, z))


def _lock(name, az, z_top, z_bot, grow, rmid, seed, drift=0.0, stations=7, segs=5,
          lift=1.0):
    """One matted lock of hair lying on the scalp, from z_top down to z_bot.

    Hair is built as a set of these, NOT as one closed shell.  The shell version looked
    exactly like the swim cap review #19 complained about: the hairline was a hard rim
    cut through a smooth surface, and no amount of noise on it reads as hair.  Separate
    locks give real gaps with scalp showing between them and a broken silhouette.
    """
    rnd = random.Random(seed)
    path, radii = [], []
    for i in range(stations):
        f = i / (stations - 1.0)
        z = z_top + (z_bot - z_top) * f
        a = az + drift * f + rnd.uniform(-0.025, 0.025)
        g = grow * (0.35 + lift * math.sin(math.pi * min(1.0, 0.18 + f * 0.86)))
        path.append(_cran_point(z, a, g))
        # thin at the root, fat in the body of the lock, tapering to a wisp
        k = math.sin(math.pi * min(1.0, 0.22 + f * 0.82))
        r = rmid * (0.42 + 0.72 * k) * rnd.uniform(0.86, 1.14)
        if f > 0.86:
            r *= 0.40
        radii.append((r, r * 0.72))
    return L.tube(name, path, radii, segs, up_hint=(0, 0, 1))


def hair_A():
    """Balding: thin matted strands round the back and sides, bare crown and temples.

    Second pass.  The first lock version was right in principle and wrong in every
    number: 20 locks up to 33 mm thick, standing 13 mm off the skull, with the end
    stations reaching round to azimuths over the cheekbone - at head framing they read as
    wooden splinters stuck through the face, which is worse than the swim cap review #19
    filed.  Now: 34 strands at a third of the thickness, hugging the skull (grow 8 mm),
    stopped well behind the ear, and a hairline that is ragged because every strand starts
    at a different height.
    """
    parts = []
    rnd = random.Random(21)
    n = 34
    # az = pi/2 is the face.  Nothing forward of 2.85 / behind 6.55 so no strand can
    # cross a cheek.
    A0, A1 = 2.88, 6.52
    for i in range(n):
        f = i / (n - 1.0)
        az = A0 + (A1 - A0) * f + rnd.uniform(-0.035, 0.035)
        back = max(0.0, math.cos(az - 4.712))          # 1 at the back of the head
        z_top = 1.706 + 0.062 * back + rnd.uniform(-0.016, 0.010)
        z_bot = 1.650 - 0.030 * back + rnd.uniform(-0.016, 0.008)
        parts.append(_lock('_lkA%d' % i, az, z_top, z_bot, 0.0080,
                           rnd.uniform(0.0042, 0.0072), 100 + i,
                           drift=rnd.uniform(-0.10, 0.10)))
    # a thinning fringe over the crown: short, sparse, scalp showing between
    for i in range(10):
        az = 3.25 + (6.05 - 3.25) * (i / 9.0) + rnd.uniform(-0.06, 0.06)
        parts.append(_lock('_crwA%d' % i, az, 1.784 + rnd.uniform(-0.012, 0.008),
                           1.716 + rnd.uniform(-0.014, 0.010), 0.0060,
                           rnd.uniform(0.0034, 0.0056), 150 + i,
                           drift=rnd.uniform(-0.08, 0.08), stations=5, segs=4))
    # a few loose wisps at the nape, hanging past the hairline
    for i in range(6):
        az = 4.05 + (5.40 - 4.05) * (i / 5.0)
        parts.append(_lock('_wspA%d' % i, az, 1.688 + rnd.uniform(-0.02, 0.02),
                           1.598 + rnd.uniform(-0.02, 0.01), 0.0090,
                           rnd.uniform(0.0028, 0.0044), 200 + i,
                           drift=rnd.uniform(-0.18, 0.18), stations=5, segs=4))
    ob = L.join(parts, '_hairA')
    L.noise_displace(ob, scale=44, amount=0.0016, seed=21)
    L.noise_displace(ob, scale=9, amount=0.0030, seed=27)
    return ob


def hair_B():
    """A woman's matted, shoulder-length hair: locks over the whole scalp, short at the
    hairline and long down the back, with a ragged broken lower edge."""
    parts = []
    rnd = random.Random(37)
    n = 36
    part_az = 1.90                 # side parting, so the crown is not radially symmetric
    for i in range(n):
        az = TAU * i / n
        c = math.cos(az - 1.5708)                       # +1 at the face, -1 at the back
        z_bot = 1.622 + 0.080 * c + rnd.uniform(-0.026, 0.018)
        z_top = 1.802 - 0.016 * abs(math.sin((az - part_az) * 0.5))
        # 8-13 mm strands, not the 25-39 mm planks of the first pass
        parts.append(_lock('_lkB%d' % i, az, z_top, z_bot, 0.0105,
                           rnd.uniform(0.0042, 0.0068), 300 + i,
                           drift=rnd.uniform(-0.16, 0.16), stations=7))
    # long locks down the back and over the shoulders, past the jaw line
    for i in range(14):
        az = 3.20 + (6.20 - 3.20) * (i / 13.0) + rnd.uniform(-0.05, 0.05)
        parts.append(_lock('_lngB%d' % i, az, 1.716 + rnd.uniform(-0.03, 0.02),
                           1.506 + rnd.uniform(-0.034, 0.026), 0.0130,
                           rnd.uniform(0.0044, 0.0078), 400 + i,
                           drift=rnd.uniform(-0.20, 0.20), stations=7, lift=0.7))
    ob = L.join(parts, '_hairB')
    L.noise_displace(ob, scale=40, amount=0.0024, seed=37)
    L.noise_displace(ob, scale=8, amount=0.0055, seed=41)
    return ob


def helmet_C():
    """Dented M1 steel pot: flared rim, band, rivets and a chin strap."""
    rings = []
    for (z, w, f, b) in [(1.6960, 0.1010, 0.0980, 0.1150),
                         (1.7050, 0.1000, 0.0970, 0.1140),
                         (1.7150, 0.0985, 0.0955, 0.1125),
                         (1.7400, 0.0930, 0.0900, 0.1070),
                         (1.7700, 0.0840, 0.0810, 0.0975),
                         (1.7980, 0.0690, 0.0650, 0.0820),
                         (1.8200, 0.0430, 0.0390, 0.0530),
                         (1.8300, 0.0130, 0.0110, 0.0160)]:
        rings.append(ZM.asym_ring(z, w, f, b, 28, 2.0))
    # flared rim: the bottom ring rolls outward and down
    rim = ZM.asym_ring(1.6910, 0.1050, 0.1020, 0.1190, 28, 2.0)
    rim2 = ZM.asym_ring(1.6880, 0.1020, 0.0990, 0.1160, 28, 2.0)
    ob = L.loft('_helmet', [rim2, rim] + rings, True, True)
    L.blob(ob, (0.055, -0.060, 1.760), 0.035, -0.011)
    L.blob(ob, (-0.030, 0.070, 1.790), 0.030, -0.009)
    L.blob(ob, (0.078, 0.030, 1.724), 0.026, -0.007)
    parts = [ob]
    # band around the shell
    band = []
    for f in (0.0, 0.5, 1.0):
        band.append(ZM.asym_ring(1.7080 + f * 0.010, 0.0995 + 0.0022, 0.0965 + 0.0022,
                                 0.1135 + 0.0022, 28, 2.0))
    parts.append(L.loft('_hband', band, True, True))
    # rivets
    for a in range(6):
        ang = TAU * a / 6 + 0.3
        parts.append(L.uv_sphere('_rivet%d' % a,
                                 (math.cos(ang) * 0.098, ZM.YC - math.sin(ang) * 0.108,
                                  1.7130), (0.0055, 0.0055, 0.0055), 8, 6))
    # chin strap, hanging loose on one side
    chin = L.tube('_chinstrap', [Vector((0.090, 0.010, 1.700)), Vector((0.082, -0.030, 1.636)),
                                 Vector((0.040, -0.062, 1.592)), Vector((-0.030, -0.064, 1.586)),
                                 Vector((-0.076, -0.034, 1.628)), Vector((-0.090, 0.010, 1.700))],
                  [(0.009, 0.004)] * 6, 6, up_hint=(0, 0, 1))
    parts.append(chin)
    parts.append(L.box_like('_chinbk', (0.018, 0.010, 0.014), (-0.004, -0.062, 1.586)))
    return L.join(parts, '_helmet')
