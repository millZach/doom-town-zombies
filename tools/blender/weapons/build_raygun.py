"""Ray Gun - retro 1950s atomic-age sci-fi pistol.

Red enamel body with cream panels, chrome fittings and a glowing green accelerator tube
(material name contains `glow`, so the game drives its intensity).
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_weapons import *                                   # noqa

WID = 'raygun'
BORE = 0.0380
Y_MUZZLE = 0.2350
SIGHT_Z = BORE + 0.0400
GRIP_POS = (0.150, 0.330, -0.082)


def glow_mat():
    # 14.0 blew every ring out to featureless white in `raygun_detail.png`; at ~5.5 the coil
    # and the vent rings still read as rings (weapons_audio.md #11).
    return plain('glow_green', (0.10, 1.0, 0.25), 0.18, 0.0,
                 emission=(0.22, 1.0, 0.32), strength=5.5)


def build_body():
    parts = []
    # main fuselage: a fat teardrop
    body = loft('body_shell', [ring3(ellipse(rx, rz, 20, 0, BORE), y) for y, rx, rz in
                               ((-0.0520, 0.0140, 0.0150), (-0.0400, 0.0215, 0.0240),
                                (-0.0100, 0.0265, 0.0300), (0.0400, 0.0270, 0.0310),
                                (0.0900, 0.0245, 0.0275), (0.1200, 0.0205, 0.0225),
                                (0.1320, 0.0180, 0.0195))])
    finish(body, M('metal_red_enamel'), bev=0.0012, segs=2, texel=0.09, long=1, seed=131)
    parts.append(body)

    # riveted frame bands round the fuselage: the shell was a smooth balloon without them
    # (weapons_audio.md #11).  Elliptical so they sit proud by a constant amount all round.
    for i, (yy, rx, rz) in enumerate(((-0.0180, 0.0252, 0.0284), (0.0620, 0.0259, 0.0295),
                                      (0.1150, 0.0212, 0.0233))):
        d, w = 0.0024, 0.0040
        bd = loft('body_band%d' % i,
                  [ring3(ellipse(rx - 0.0005, rz - 0.0005, 14, 0, BORE), yy - w),
                   ring3(ellipse(rx + d, rz + d, 14, 0, BORE), yy - w * 0.55),
                   ring3(ellipse(rx + d, rz + d, 14, 0, BORE), yy + w * 0.55),
                   ring3(ellipse(rx - 0.0005, rz - 0.0005, 14, 0, BORE), yy + w)],
                  cap_start=True, cap_end=True)
        finish(bd, M('metal_steel'), bev=0.0006, texel=0.04, long=1)
        parts.append(bd)

    # boxed lower receiver slung under the fuselage
    low = prism('body_lower', rrect(0.0320, 0.0190, 0.0045, 2, 0, BORE - 0.0385), 0.0120, 0.1010)
    cut(low, grooves('c_lowv', 4, 0.0165, (0.040, 0.0035, 0.0045),
                     loc=(0, 0.0560, BORE - 0.0470), axis=(0, 1, 0)))
    finish(low, M('metal_red_enamel'), bev=0.0010, segs=1, texel=0.08, long=1, seed=136)
    parts.append(low)
    # two of the six screws sit on the shell/lower-receiver seam; the other four are the
    # rivet ring below.  (The full eight did not fit the 25k budget.)
    for sx in (-1, 1):
        parts.append(finish(screw('body_lsc%d' % sx, 0.0026,
                                  (sx * 0.0160, 0.0560, BORE - 0.0385), 'X', 'slot', 0.0009,
                                  0.0006), M('metal_steel'), bev=0.0002, texel=0.02))

    # cream side panels
    for sx in (-1, 1):
        p = loft('body_panel%d' % sx, [ring3(ellipse(rx, rz, 20, 0, BORE), y) for y, rx, rz in
                                       ((-0.0300, 0.0230, 0.0255), (0.0000, 0.0272, 0.0308),
                                        (0.0500, 0.0276, 0.0316), (0.0900, 0.0252, 0.0282))])
        cut(p, loft('c_p%d' % sx, [ring3(ellipse(rx, rz, 20, 0, BORE), y) for y, rx, rz in
                                   ((-0.0400, 0.0218, 0.0243), (0.0000, 0.0260, 0.0296),
                                    (0.0500, 0.0264, 0.0304), (0.1000, 0.0240, 0.0270))]))
        cut(p, rbox('c_pk%d' % sx, (0.060, 0.20, 0.060), (-sx * 0.0360, 0.03, BORE)))
        cut(p, rbox('c_pt%d' % sx, (0.080, 0.20, 0.060), (0, 0.03, BORE + 0.0480)))
        cut(p, rbox('c_pb%d' % sx, (0.080, 0.20, 0.060), (0, 0.03, BORE - 0.0430)))
        finish(p, M('polymer_cream'), bev=0.0008, texel=0.08, long=1, seed=132 + sx)
        parts.append(p)

    # chrome nose ring + flared emitter
    ring = lathe('body_nosering', [(0.0180, 0.0000), (0.0235, 0.0020), (0.0240, 0.0090),
                                   (0.0190, 0.0110), (0.0180, 0.0090)],
                 segs=20, loc=(0, 0.1320, BORE), rot=(D2R(-90), 0, 0))
    finish(ring, M('metal_steel'), bev=0.0006, texel=0.04, long=1)
    parts.append(ring)
    emit = loft('body_emitter', [ring3(ellipse(r, r, 20, 0, BORE), y) for y, r in
                                 ((0.1430, 0.0150), (0.1900, 0.0128), (0.2050, 0.0128),
                                  (0.2150, 0.0190), (0.2350, 0.0300), (0.2350, 0.0272),
                                  (0.2170, 0.0165), (0.2080, 0.0106), (0.1900, 0.0102),
                                  (0.1430, 0.0110))])
    finish(emit, M('metal_steel'), bev=0.0008, texel=0.05, long=1, seed=133)
    parts.append(emit)
    # cooling fins around the emitter neck (4, thinner and deeper than the old 3)
    for i in range(4):
        f = lathe('body_fin%d' % i, [(0.0148, -0.0016), (0.0312, -0.0016),
                                     (0.0312, 0.0016), (0.0148, 0.0016)],
                  segs=18, loc=(0, 0.1450 + i * 0.0112, BORE), rot=(D2R(-90), 0, 0))
        finish(f, M('metal_red_enamel'), bev=0.0, texel=0.05, long=1)
        parts.append(f)
    # three concentric ribs on the flared muzzle bell, so it is not a smooth chrome balloon
    for i, (yy, rr) in enumerate(((0.2185, 0.0203), (0.2255, 0.0246), (0.2315, 0.0282))):
        rb = lathe('body_bellrib%d' % i, [(rr - 0.0012, -0.0014), (rr + 0.0016, -0.0014),
                                          (rr + 0.0016, 0.0014), (rr - 0.0012, 0.0014)],
                   segs=16, loc=(0, yy, BORE), rot=(D2R(-90), 0, 0))
        finish(rb, M('metal_steel'), bev=0.0, texel=0.03, long=1)
        parts.append(rb)

    # top-mounted spherical reservoir with a chrome cap
    ball = sphere('body_tank', 0.0215, (0, 0.0180, BORE + 0.0310), segs=18, scale=(0.85, 1.5, 0.85))
    finish(ball, M('metal_red_enamel'), bev=0.0, texel=0.07, seed=134)
    parts.append(ball)
    cap = lathe('body_tankcap', [(0.0000, 0.0060), (0.0090, 0.0060), (0.0105, 0.0030),
                                 (0.0105, -0.0060), (0.0000, -0.0060)],
                segs=20, loc=(0, 0.0530, BORE + 0.0300), rot=(D2R(-90), 0, 0))
    finish(cap, M('metal_steel'), bev=0.0005, texel=0.03, long=1)
    parts.append(cap)

    # sights: a chrome blade at the front and a notch on the tank
    fs = sight_post('body_fsight', 0.0030, 0.0038, 0.0060, loc=(0, 0.1500, SIGHT_Z - 0.0060))
    finish(fs, M('metal_steel'), bev=0.0004, texel=0.03, long=1)
    parts.append(fs)
    rs = rear_notch('body_rsight', w=0.0170, t=0.0060, hgt=0.0135, notch_w=0.0040, notch_d=0.0032,
                    loc=(0, -0.0250, SIGHT_Z - 0.0105))
    finish(rs, M('metal_steel'), bev=0.0004, texel=0.03, long=1)
    parts.append(rs)

    # grip
    g = prism_x('body_grip', [(-0.0180, BORE - 0.0270), (0.0040, BORE - 0.0290),
                              (0.0000, BORE - 0.0620), (-0.0110, BORE - 0.0980),
                              (-0.0240, BORE - 0.1250), (-0.0400, BORE - 0.1280),
                              (-0.0510, BORE - 0.1140), (-0.0430, BORE - 0.0820),
                              (-0.0320, BORE - 0.0450), (-0.0330, BORE - 0.0250)],
                -0.0155, 0.0155)
    env = loft('c_ge', [ring3(rrect(w, 0.200, r, 4, 0, BORE - 0.080), y)
                        for y, w, r in ((-0.070, 0.0300, 0.0110), (-0.020, 0.0310, 0.0115),
                                        (0.020, 0.0300, 0.0100))])
    boolean(g, env, 'INTERSECT')
    finish(g, M('metal_red_enamel'), bev=0.0014, segs=2, texel=0.07, long=1, seed=135)
    parts.append(g)
    for sx in (-1, 1):
        ck = checkering('body_gck%d' % sx, 0.058, 0.022, nu=13, nv=6, depth=0.0009, thick=0.0010)
        place(ck, (sx * 0.0158, -0.0280, BORE - 0.0860), (0, -0.33, -0.94), (sx, 0, 0))
        finish(ck, M('polymer_cream'), bev=0.0, texel=0.07)
        parts.append(ck)

    # trigger guard + trigger
    guard = prism_x('body_guard', arc_pts(-0.0090, BORE - 0.0400, 0.0215, 30, -175, 9)
                    + [(-0.0300, BORE - 0.0310), (-0.0250, BORE - 0.0220),
                       (0.0140, BORE - 0.0215), (0.0150, BORE - 0.0310)], -0.0085, 0.0085)
    cut(guard, prism_x('c_g', arc_pts(-0.0090, BORE - 0.0400, 0.0145, 40, -190, 9)
                       + [(-0.0245, BORE - 0.0300), (0.0090, BORE - 0.0295)], -0.03, 0.03))
    finish(guard, M('metal_steel'), bev=0.0008, texel=0.04, long=1)
    parts.append(guard)
    trg = prism_x('body_trigger', [(-0.0140, BORE - 0.0300), (-0.0050, BORE - 0.0305),
                                   (-0.0035, BORE - 0.0480), (-0.0125, BORE - 0.0470)],
                  -0.0050, 0.0050)
    finish(trg, M('metal_steel'), bev=0.0005, texel=0.03, long=1)
    parts.append(trg)

    # rivets around the shell seam
    for i in range(6):
        a = D2R(-50 + i * 40)
        parts.append(finish(screw('body_rivet%d' % i, 0.0022,
                                  (math.sin(a) * 0.0270, 0.0620, BORE + math.cos(a) * 0.0300),
                                  'Y', 'pin', 0.0008), M('metal_steel'), bev=0.0002, texel=0.02))
    return fuse('body', parts)


def build_glow():
    """The accelerator tube and the vent slots that light up."""
    parts = []
    gm = glow_mat()
    tube = cylinder('glow_tube', 0.0125, 0.1400, (0, 0.0500, BORE), 'Y', 24)
    finish(tube, gm, bev=0.0006, texel=0.05, long=1)
    parts.append(tube)
    coil = []
    n = 85                       # 150 was ~1.8k tris of coil alone; the shape is unchanged
    for i in range(n + 1):
        t = i / n
        a = TAU * 7.0 * t
        y = -0.0150 + 0.1300 * t
        cx, cz = math.cos(a) * 0.0180, math.sin(a) * 0.0195
        rr = 0.0032
        ring = [(cx + math.cos(b) * rr, y, BORE + cz + math.sin(b) * rr)
                for b in [TAU * k / 6 for k in range(6)]]
        coil.append(ring)
    co = loft('glow_coil', coil)
    finish(co, gm, bev=0.0, texel=0.03)
    parts.append(co)
    for i in range(3):
        sl = lathe('glow_vent%d' % i, [(0.0270, -0.0020), (0.0300, -0.0020),
                                       (0.0300, 0.0020), (0.0270, 0.0020)],
                   segs=24, loc=(0, 0.0180 + i * 0.0180, BORE), rot=(D2R(-90), 0, 0))
        finish(sl, gm, bev=0.0004, texel=0.03, long=1)
        parts.append(sl)
    bulb = sphere('glow_bulb', 0.0092, (0, 0.2240, BORE), segs=14, scale=(1, 0.55, 1))
    finish(bulb, gm, bev=0.0, texel=0.03)
    parts.append(bulb)
    ob = fuse('glow', parts)
    assign(ob, gm)
    return ob


def build_cell():
    """Removable power cell under the receiver.

    `_reloadRaygun` (viewmodel.js) drops and re-seats `mag`; without this node the Ray Gun's
    reload had nothing to animate (weapons_audio.md #4)."""
    parts = []
    c = prism('mag_cell', rrect(0.0290, 0.0200, 0.0050, 2, 0, BORE - 0.0575), 0.0250, 0.0900)
    cut(c, grooves('c_cellv', 3, 0.0150, (0.040, 0.0035, 0.0040),
                   loc=(0, 0.0575, BORE - 0.0675), axis=(0, 1, 0)))
    finish(c, M('polymer_cream'), bev=0.0010, segs=1, texel=0.07, long=1, seed=137)
    parts.append(c)
    for sx in (-1, 1):
        w = prism('mag_win%d' % sx, [(sx * 0.0142, BORE - 0.0630), (sx * 0.0150, BORE - 0.0630),
                                     (sx * 0.0150, BORE - 0.0520), (sx * 0.0142, BORE - 0.0520)],
                  0.0360, 0.0790)
        finish(w, glow_mat(), bev=0.0004, texel=0.03, long=1)
        parts.append(w)
    lat = rbox('mag_latch', (0.0130, 0.0090, 0.0075), (0, 0.0300, BORE - 0.0490))
    finish(lat, M('metal_steel'), bev=0.0, texel=0.03)
    parts.append(lat)
    return fuse('mag', parts)


def build(arms=True):
    reset_scene()
    prebake()
    guns = [build_body(), build_glow(), build_cell()]
    arm_r = arm_l = None
    if arms:
        arm_r = hand_on_grip((0.0205, -0.0180, BORE - 0.0620), rake=-0.36,
                             elbow=(0.095, -0.035, -0.300))
        arm_l = hand_support_pistol((-0.0290, -0.0270, BORE - 0.0840), rake=-0.42,
                                    elbow=(-0.105, -0.030, -0.300))
    muzzle = (0.0, Y_MUZZLE, BORE)
    eject = (0.0240, 0.0200, BORE + 0.0100)
    aim = (0.0, -0.0250, SIGHT_Z)
    return dict(guns=guns, arm_r=arm_r, arm_l=arm_l, muzzle=muzzle, eject=eject, aim=aim)


if __name__ == '__main__':
    d = build()
    deliver(WID, GRIP_POS, d['guns'], d['muzzle'], d['eject'], d['aim'], d['arm_r'], d['arm_l'],
            movable=('mag',), detail_target=(0, 0.070, 0.010), detail_dist=0.50, lens=50,
            ads_back=0.30)
    print('DONE')
