"""Galil 5.56 assault rifle (SAR) - first-person viewmodel.

Gun space: origin at the web of the right hand on the pistol grip, bore along +Y at BORE.
Real Galil SAR: 840 mm with the stock out, 332 mm barrel, 35-round curved magazine.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_weapons import *                                   # noqa

WID = 'galil'
BORE = 0.0470
RW, RH = 0.0330, 0.0390
Y_MUZZLE = 0.5300
SIGHT_Z = BORE + 0.0420
GRIP_POS = (0.148, 0.272, -0.106)


def build_receiver():
    parts = []
    body = prism('rcv_body', rrect(RW, RH, 0.0045, 2, 0, BORE - 0.0040), -0.0760, 0.1420)
    boolean(body, prism('rcv_mw', rrect(0.0320, 0.0190, 0.0040, 2, 0, BORE - 0.0250),
                        0.0320, 0.0860), 'UNION')
    cut(body, rbox('c_mag', (0.0250, 0.0460, 0.0300), (0, 0.0580, BORE - 0.0320)))
    cut(body, rbox('c_port', (0.020, 0.0540, 0.0180), (0.0185, 0.0500, BORE + 0.0060)))
    finish(body, M('metal_parker'), bev=0.0009, texel=0.06, long=1, jitter=0.2, seed=101)
    parts.append(body)

    # top cover with a longitudinal rib and the rear peep sight
    dc = prism('rcv_cover', rrect(0.0330, 0.0190, 0.0065, 3, 0, BORE + 0.0245), -0.0740, 0.1000)
    cut(dc, rbox('c_dcb', (0.045, 0.30, 0.020), (0, 0.02, BORE + 0.0075)))
    cut(dc, grooves('c_dcr', 2, 0.0210, (0.045, 0.0040, 0.0045), loc=(0, 0.0200, BORE + 0.0330),
                    axis=(0, 1, 0)))
    # charging-handle slot in the top left of the cover; the `bolt` object rides in it
    cut(dc, rbox('c_chslot', (0.0050, 0.0900, 0.0110), (-0.0145, 0.0700, BORE + 0.0300)))
    finish(dc, M('metal_parker'), bev=0.0008, texel=0.06, long=1, seed=102)
    parts.append(dc)

    tow = prism('rcv_rtower', rrect(0.0200, 0.0260, 0.0035, 2, 0, BORE + 0.0330), -0.0620, -0.0430)
    # peep aperture - must be a real hole you can see the front post through
    cut(tow, cylinder('c_ap', 0.0031, 0.040, (0, -0.0525, SIGHT_Z), 'Y', 16))
    finish(tow, M('metal_parker'), bev=0.0006, texel=0.04, long=1)
    parts.append(tow)
    for sx in (-1, 1):
        ear = prism('rcv_rear%d' % sx, [(sx * 0.0072, BORE + 0.0300), (sx * 0.0104, BORE + 0.0300),
                                        (sx * 0.0100, BORE + 0.0490), (sx * 0.0068, BORE + 0.0490)],
                    -0.0600, -0.0450)
        finish(ear, M('metal_parker'), bev=0.0005, texel=0.03, long=1)
        parts.append(ear)

    # selector (right) and the Galil's second selector paddle (left)
    for x0, x1 in ((0.0165, 0.0210), (-0.0210, -0.0165)):
        sel = prism_x('rcv_selector', [(0.0050, BORE + 0.0090), (0.0250, BORE + 0.0070),
                                       (0.0270, BORE - 0.0040), (0.0210, BORE - 0.0180),
                                       (0.0110, BORE - 0.0170), (0.0120, BORE - 0.0030)], x0, x1)
        finish(sel, M('metal_parker'), bev=0.0007, texel=0.04, long=1)
        parts.append(sel)

    guard = prism_x('rcv_guard', arc_pts(0.0110, BORE - 0.0440, 0.0205, 25, -180, 9)
                    + [(-0.0095, BORE - 0.0350), (-0.0045, BORE - 0.0260),
                       (0.0330, BORE - 0.0260), (0.0340, BORE - 0.0355)], -0.0080, 0.0080)
    cut(guard, prism_x('c_g', arc_pts(0.0110, BORE - 0.0440, 0.0140, 35, -190, 9)
                       + [(-0.0035, BORE - 0.0340), (0.0270, BORE - 0.0335)], -0.03, 0.03))
    finish(guard, M('metal_parker'), bev=0.0007, texel=0.04, long=1)
    parts.append(guard)
    trg = prism_x('rcv_trigger', [(0.0100, BORE - 0.0330), (0.0180, BORE - 0.0335),
                                  (0.0185, BORE - 0.0500), (0.0105, BORE - 0.0490)],
                  -0.0050, 0.0050)
    finish(trg, M('metal_steel'), bev=0.0005, texel=0.03, long=1)
    parts.append(trg)
    mr = prism_x('rcv_magrel', [(0.0300, BORE - 0.0260), (0.0375, BORE - 0.0265),
                                (0.0365, BORE - 0.0410), (0.0295, BORE - 0.0405)],
                 -0.0062, 0.0062)
    finish(mr, M('metal_parker'), bev=0.0005, texel=0.03, long=1)
    parts.append(mr)
    return fuse('receiver', parts)


def build_grip():
    g = prism_x('grip_body', [(-0.0080, BORE - 0.0250), (0.0095, BORE - 0.0260),
                              (0.0065, BORE - 0.0570), (-0.0055, BORE - 0.0910),
                              (-0.0180, BORE - 0.1200), (-0.0335, BORE - 0.1245),
                              (-0.0450, BORE - 0.1120), (-0.0370, BORE - 0.0815),
                              (-0.0255, BORE - 0.0450), (-0.0245, BORE - 0.0260)],
                -0.0148, 0.0148)
    env = loft('c_ge', [ring3(rrect(w, 0.200, r, 4, 0, BORE - 0.080), y)
                        for y, w, r in ((-0.060, 0.0296, 0.0098), (-0.020, 0.0296, 0.0102),
                                        (0.020, 0.0296, 0.0092))])
    boolean(g, env, 'INTERSECT')
    finish(g, M('polymer_black'), bev=0.0012, segs=2, texel=0.055, long=1, seed=104)
    parts = [g]
    for sx in (-1, 1):
        ck = checkering('grip_ck%d' % sx, 0.054, 0.020, nu=15, nv=7, depth=0.0008, thick=0.0010)
        place(ck, (sx * 0.0151, -0.0235, BORE - 0.0825), (0, -0.30, -0.95), (sx, 0, 0))
        finish(ck, M('polymer_black'), bev=0.0, texel=0.055)
        parts.append(ck)
    return fuse('grip', parts)


def build_front():
    parts = []
    b = loft('frt_barrel', [ring3(ellipse(r, r, 18, 0, BORE), y) for y, r in
                            ((0.1000, 0.0112), (0.1600, 0.0094), (0.3400, 0.0086),
                             (0.4600, 0.0086))])
    cut(b, cylinder('c_b', 0.0032, 0.50, (0, 0.2800, BORE), 'Y', 16))
    finish(b, M('metal_blued'), bev=0.0005, texel=0.05, long=1)
    parts.append(b)
    gt = cylinder('frt_gastube', 0.0094, 0.1900, (0, 0.2250, BORE + 0.0190), 'Y', 18)
    finish(gt, M('metal_parker'), bev=0.0005, texel=0.05, long=1)
    parts.append(gt)
    gb = prism('frt_gasblock', rrect(0.0240, 0.0450, 0.0035, 2, 0, BORE + 0.0095), 0.3250, 0.3560)
    cut(gb, cylinder('c_gb', 0.0092, 0.05, (0, 0.3400, BORE), 'Y', 18))
    finish(gb, M('metal_parker'), bev=0.0007, texel=0.05, long=1)
    parts.append(gb)

    # front sight tower with big protective ears (a Galil hallmark)
    fb = prism('frt_fsbase', rrect(0.0260, 0.0300, 0.0035, 2, 0, BORE + 0.0200), 0.3900, 0.4200)
    cut(fb, cylinder('c_fb', 0.0092, 0.05, (0, 0.4050, BORE), 'Y', 18))
    cut(fb, rbox('c_fb2', (0.0140, 0.040, 0.0200), (0, 0.4050, BORE + 0.0430)))
    finish(fb, M('metal_parker'), bev=0.0007, texel=0.05, long=1)
    parts.append(fb)
    post = sight_post('frt_fspost', 0.0030, 0.0042, 0.0150, loc=(0, 0.4050, SIGHT_Z - 0.0150))
    finish(post, M('metal_parker'), bev=0.0004, texel=0.03, long=1)
    parts.append(post)
    for sx in (-1, 1):
        ear = prism('frt_fsear%d' % sx, [(sx * 0.0074, BORE + 0.0300), (sx * 0.0112, BORE + 0.0300),
                                         (sx * 0.0106, BORE + 0.0520), (sx * 0.0070, BORE + 0.0520)],
                    0.3920, 0.4180)
        finish(ear, M('metal_parker'), bev=0.0005, texel=0.03, long=1)
        parts.append(ear)

    # muzzle brake
    mb = loft('frt_brake', [ring3(ellipse(r, r, 20, 0, BORE), y) for y, r in
                            ((0.4700, 0.0110), (0.4800, 0.0140), (0.5240, 0.0140),
                             (0.5300, 0.0118))])
    cut(mb, cylinder('c_mb', 0.0074, 0.10, (0, 0.5000, BORE), 'Y', 18))
    for i in range(3):
        cut(mb, rbox('c_mbs%d' % i, (0.040, 0.0045, 0.0045),
                     (0, 0.4870 + i * 0.0130, BORE + 0.0115)))
    finish(mb, M('metal_parker'), bev=0.0006, texel=0.04, long=1)
    parts.append(mb)

    # polymer handguard with cooling slots
    hg = loft('frt_hg', [ring3(rrect(w, h, r, 4, 0, BORE + 0.0040), y)
                         for y, w, h, r in ((0.1280, 0.0370, 0.0420, 0.0090),
                                            (0.1450, 0.0420, 0.0470, 0.0110),
                                            (0.2900, 0.0415, 0.0465, 0.0110),
                                            (0.3180, 0.0370, 0.0410, 0.0100),
                                            (0.3260, 0.0320, 0.0360, 0.0090))])
    cut(hg, cylinder('c_h1', 0.0120, 0.30, (0, 0.2200, BORE), 'Y', 20))
    cut(hg, cylinder('c_h2', 0.0106, 0.30, (0, 0.2200, BORE + 0.0190), 'Y', 20))
    cut(hg, rbox('c_h3', (0.024, 0.30, 0.030), (0, 0.2200, BORE + 0.0110)))
    for sx in (-1, 1):
        cut(hg, grooves('c_hs%d' % sx, 4, 0.0270, (0.010, 0.0170, 0.0070),
                        loc=(sx * 0.0205, 0.2180, BORE + 0.0080), axis=(0, 1, 0)))
    cut(hg, grooves('c_hb', 4, 0.0270, (0.020, 0.0170, 0.010),
                    loc=(0, 0.2180, BORE - 0.0190), axis=(0, 1, 0)))
    finish(hg, M('polymer_black'), bev=0.0012, segs=2, texel=0.055, long=1, seed=106)
    parts.append(hg)
    return fuse('front', parts)


def build_stock():
    parts = []
    for sx in (-1, 1):
        for zz in (BORE + 0.0070, BORE - 0.0240):
            r = cylinder('stk_t%d_%d' % (sx, int(zz * 1e4)), 0.0060, 0.1650,
                         (sx * 0.0140, -0.1640, zz), 'Y', 14)
            finish(r, M('metal_parker'), bev=0.0004, texel=0.04, long=1)
            parts.append(r)
    plate = prism('stk_plate', rrect(0.0440, 0.0470, 0.0090, 3, 0, BORE - 0.0085), -0.2500, -0.2410)
    finish(plate, M('polymer_black'), bev=0.0010, texel=0.05, long=1)
    parts.append(plate)
    pad = prism('stk_pad', rrect(0.0410, 0.0440, 0.0090, 3, 0, BORE - 0.0085), -0.2570, -0.2495)
    finish(pad, M('polymer_rubber'), bev=0.0012, texel=0.05, long=1)
    parts.append(pad)
    hinge = prism('stk_hinge', rrect(0.0400, 0.0320, 0.0060, 2, 0, BORE - 0.0085), -0.0870, -0.0760)
    finish(hinge, M('metal_parker'), bev=0.0008, texel=0.05, long=1)
    parts.append(hinge)
    return fuse('stock', parts)


def build_mag():
    secs = []
    n = 16
    for i in range(n + 1):
        t = i / n
        z = (BORE - 0.0260) - 0.1950 * t
        y = 0.0560 + 0.0700 * (t ** 1.7)
        secs.append([(p[0], y + p[1], z) for p in rrect(0.0250 - 0.0016 * t,
                                                        0.0320 - 0.0032 * t, 0.0038, 2)])
    mag = loft('mag_body', secs)
    for sx in (-1, 1):
        cut(mag, grooves('c_mr%d' % sx, 5, 0.0300, (0.0040, 0.0034, 0.0100),
                         loc=(sx * 0.0136, 0.0930, BORE - 0.1250), axis=(0, 0.34, -0.94)))
    finish(mag, M('metal_parker'), bev=0.0009, texel=0.05, long=2, seed=108)
    fl = prism_x('mag_floor', [(0.1190, BORE - 0.2080), (0.1520, BORE - 0.2080),
                               (0.1530, BORE - 0.2180), (0.1180, BORE - 0.2180)], -0.0130, 0.0130)
    finish(fl, M('metal_parker'), bev=0.0008, texel=0.05, long=1)
    return fuse('mag', [mag, fl])


def build_bolt():
    """Galil charging handle: left side, bent up over the cover, reciprocating with the carrier.

    The game slides this rearward along Blender -Y (three.js local +Z), `boltTravel` 0.055 m."""
    parts = []
    ch = prism_x('bolt_handle', [(0.0900, BORE + 0.0230), (0.1120, BORE + 0.0230),
                                 (0.1120, BORE + 0.0400), (0.1020, BORE + 0.0435),
                                 (0.0930, BORE + 0.0370)], -0.0232, -0.0180)
    finish(ch, M('metal_parker'), bev=0.0006, texel=0.04, long=1)
    parts.append(ch)
    # the stem that reaches through the slot in the cover onto the bolt carrier
    st = prism_x('bolt_stem', [(0.0930, BORE + 0.0262), (0.1100, BORE + 0.0262),
                               (0.1100, BORE + 0.0330), (0.0930, BORE + 0.0330)],
                 -0.0186, -0.0126)
    finish(st, M('metal_steel'), bev=0.0005, texel=0.035, long=1)
    parts.append(st)
    ob = fuse('bolt', parts)
    return set_origin(ob, (-0.0200, 0.1010, BORE + 0.0310))


def build(arms=True):
    reset_scene()
    prebake()
    guns = [build_receiver(), build_grip(), build_front(), build_stock(), build_mag(),
            build_bolt()]
    arm_r = arm_l = None
    if arms:
        arm_r = hand_on_grip((0.0195, -0.0190, BORE - 0.0580), rake=-0.42,
                             elbow=(0.100, -0.030, -0.300))
        arm_l = hand_on_handguard((-0.0285, 0.2150, BORE + 0.0050), lean=0.20,
                                  elbow=(-0.135, -0.020, -0.290))
    muzzle = (0.0, Y_MUZZLE, BORE)
    eject = (0.0195, 0.0500, BORE + 0.0060)
    aim = (0.0, -0.0525, SIGHT_Z)
    return dict(guns=guns, arm_r=arm_r, arm_l=arm_l, muzzle=muzzle, eject=eject, aim=aim)


if __name__ == '__main__':
    d = build()
    deliver(WID, GRIP_POS, d['guns'], d['muzzle'], d['eject'], d['aim'], d['arm_r'], d['arm_l'],
            movable=('mag', 'bolt'), detail_target=(0, 0.160, 0.020), detail_dist=0.88, lens=52,
            ads_back=0.32)
    print('DONE')
