"""AKS-74u compact carbine - first-person viewmodel.

Gun space: origin at the web of the right hand on the pistol grip, bore along +Y at BORE.
Real AKS-74U: 735 mm with the stock out, 206 mm barrel, 30-round curved magazine.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_weapons import *                                   # noqa

WID = 'ak74u'
BORE = 0.0470
RW, RH = 0.0300, 0.0370          # receiver width / height
Y_MUZZLE = 0.4200
SIGHT_Z = BORE + 0.0400
GRIP_POS = (0.148, 0.268, -0.104)


def build_receiver():
    parts = []
    # stamped receiver: a squared tube with the AK's angled rear
    body = prism('rcv_body', rrect(RW, RH, 0.0040, 2, 0, BORE - 0.0035), -0.0680, 0.1150)
    # magwell flare
    boolean(body, prism('rcv_mw', rrect(0.0295, 0.0180, 0.0035, 2, 0, BORE - 0.0235),
                        0.0340, 0.0800), 'UNION')
    cut(body, rbox('c_mag', (0.0235, 0.0420, 0.0300), (0, 0.0570, BORE - 0.0300)))
    # ejection port (right)
    cut(body, rbox('c_port', (0.020, 0.0480, 0.0165), (0.0170, 0.0440, BORE + 0.0060)))
    # bolt-carrier raceway (interior channel) + the charging-handle slot in the right wall.
    # The `bolt` object rides in these; at full travel the port opens the way it should.
    cut(body, rbox('c_race', (0.0180, 0.1300, 0.0210), (-0.0020, 0.0180, BORE + 0.0075)))
    cut(body, rbox('c_chslot', (0.0110, 0.0870, 0.0115), (0.0115, 0.0385, BORE + 0.0070)))
    # lightening dimples above the magwell
    for sx in (-1, 1):
        cut(body, sphere('c_d%d' % sx, 0.0075, (sx * 0.0152, 0.0570, BORE - 0.0040), 14,
                         scale=(0.5, 2.6, 0.8)))
    finish(body, M('metal_parker'), bev=0.0009, texel=0.06, long=1, jitter=0.2, seed=81)
    parts.append(body)

    # dust cover (top) with stiffening ribs
    dc = prism('rcv_cover', rrect(0.0300, 0.0175, 0.0060, 3, 0, BORE + 0.0225), -0.0640, 0.0880)
    cut(dc, rbox('c_dcb', (0.040, 0.20, 0.020), (0, 0.02, BORE + 0.0060)))
    cut(dc, grooves('c_dcr', 2, 0.0230, (0.040, 0.0035, 0.0040), loc=(0, 0.0200, BORE + 0.0300),
                    axis=(0, 1, 0)))
    finish(dc, M('metal_parker'), bev=0.0008, texel=0.06, long=1, seed=82)
    parts.append(dc)

    # the AKS-74U's hinged rear sight block / receiver cover hinge
    rb = prism('rcv_sightblk', rrect(0.0300, 0.0230, 0.0050, 2, 0, BORE + 0.0300), -0.0700, -0.0450)
    finish(rb, M('metal_parker'), bev=0.0008, texel=0.05, long=1)
    parts.append(rb)
    drum = cylinder('rcv_rsight', 0.0110, 0.0230, (0, -0.0575, BORE + 0.0390), 'Y', 18)
    # open U-notch: the AK's rear sight is a notch, not a peep.  It has to be genuinely open
    # or ADS is a black lump (weapons_audio.md #1).
    cut(drum, cylinder('c_ap', 0.0030, 0.040, (0, -0.0575, SIGHT_Z), 'Y', 16))
    cut(drum, rbox('c_ap2', (0.0060, 0.040, 0.0110), (0, -0.0575, SIGHT_Z + 0.0055)))
    finish(drum, M('metal_parker'), bev=0.0006, texel=0.04, long=1)
    parts.append(drum)

    # safety / selector lever (right side)
    sel = prism_x('rcv_selector', [(0.0090, BORE + 0.0110), (0.0270, BORE + 0.0090),
                                   (0.0300, BORE - 0.0010), (0.0250, BORE - 0.0180),
                                   (0.0150, BORE - 0.0170), (0.0170, BORE - 0.0020)],
                  0.0150, 0.0190)
    finish(sel, M('metal_parker'), bev=0.0007, texel=0.04, long=1)
    parts.append(sel)

    # trigger guard + trigger
    guard = prism_x('rcv_guard', arc_pts(0.0110, BORE - 0.0430, 0.0200, 25, -180, 9)
                    + [(-0.0090, BORE - 0.0340), (-0.0040, BORE - 0.0250),
                       (0.0330, BORE - 0.0250), (0.0340, BORE - 0.0345)], -0.0075, 0.0075)
    cut(guard, prism_x('c_g', arc_pts(0.0110, BORE - 0.0430, 0.0135, 35, -190, 9)
                       + [(-0.0030, BORE - 0.0330), (0.0270, BORE - 0.0325)], -0.03, 0.03))
    finish(guard, M('metal_parker'), bev=0.0007, texel=0.04, long=1)
    parts.append(guard)
    trg = prism_x('rcv_trigger', [(0.0100, BORE - 0.0320), (0.0180, BORE - 0.0325),
                                  (0.0185, BORE - 0.0490), (0.0105, BORE - 0.0480)],
                  -0.0048, 0.0048)
    finish(trg, M('metal_steel'), bev=0.0005, texel=0.03, long=1)
    parts.append(trg)
    # magazine release paddle
    mr = prism_x('rcv_magrel', [(0.0300, BORE - 0.0250), (0.0370, BORE - 0.0255),
                                (0.0360, BORE - 0.0400), (0.0295, BORE - 0.0395)],
                 -0.0060, 0.0060)
    finish(mr, M('metal_parker'), bev=0.0005, texel=0.03, long=1)
    parts.append(mr)
    return fuse('receiver', parts)


def build_grip():
    g = prism_x('grip_body', [(-0.0080, BORE - 0.0240), (0.0090, BORE - 0.0250),
                              (0.0060, BORE - 0.0560), (-0.0060, BORE - 0.0900),
                              (-0.0180, BORE - 0.1180), (-0.0330, BORE - 0.1220),
                              (-0.0440, BORE - 0.1100), (-0.0360, BORE - 0.0800),
                              (-0.0250, BORE - 0.0440), (-0.0240, BORE - 0.0250)],
                -0.0145, 0.0145)
    env = loft('c_ge', [ring3(rrect(w, 0.200, r, 4, 0, BORE - 0.080), y)
                        for y, w, r in ((-0.060, 0.0290, 0.0095), (-0.020, 0.0290, 0.0100),
                                        (0.020, 0.0290, 0.0090))])
    boolean(g, env, 'INTERSECT')
    finish(g, M('polymer_black'), bev=0.0012, segs=2, texel=0.055, long=1, seed=84)
    parts = [g]
    for sx in (-1, 1):
        ck = checkering('grip_ck%d' % sx, 0.052, 0.020, nu=15, nv=7, depth=0.0008, thick=0.0010)
        place(ck, (sx * 0.0148, -0.0230, BORE - 0.0810), (0, -0.30, -0.95), (sx, 0, 0))
        finish(ck, M('polymer_black'), bev=0.0, texel=0.055)
        parts.append(ck)
    return fuse('grip', parts)


def build_front():
    """Barrel, gas block, booster and the wooden handguards."""
    parts = []
    b = loft('frt_barrel', [ring3(ellipse(r, r, 18, 0, BORE), y) for y, r in
                            ((0.0900, 0.0110), (0.1400, 0.0092), (0.2600, 0.0085),
                             (0.3300, 0.0085))])
    cut(b, cylinder('c_b', 0.0033, 0.40, (0, 0.2200, BORE), 'Y', 16))
    finish(b, M('metal_blued'), bev=0.0005, texel=0.05, long=1)
    parts.append(b)

    # gas tube above the barrel with the AK's vent ports.  Low-segment cylinder cutters:
    # scaled-sphere cutters here cost ~2.3k tris of intersection + bevel.
    gt = cylinder('frt_gastube', 0.0092, 0.1250, (0, 0.1900, BORE + 0.0185), 'Y', 18)
    for sx in (-1, 1):
        cut(gt, cylinder('c_gp%d' % sx, 0.0028, 0.0300,
                         (sx * 0.0080, 0.2280, BORE + 0.0190), 'X', 6))
    finish(gt, M('metal_parker'), bev=0.0005, texel=0.05, long=1)
    parts.append(gt)
    gb = prism('frt_gasblock', rrect(0.0230, 0.0430, 0.0035, 2, 0, BORE + 0.0090), 0.2500, 0.2800)
    cut(gb, cylinder('c_gb', 0.0090, 0.05, (0, 0.2650, BORE), 'Y', 18))
    finish(gb, M('metal_parker'), bev=0.0007, texel=0.05, long=1)
    parts.append(gb)
    # front sight base with protective ears
    fb = prism('frt_fsbase', rrect(0.0250, 0.0320, 0.0035, 2, 0, BORE + 0.0180), 0.2800, 0.3080)
    cut(fb, cylinder('c_fb', 0.0090, 0.05, (0, 0.2940, BORE), 'Y', 18))
    cut(fb, rbox('c_fb2', (0.0130, 0.040, 0.0180), (0, 0.2940, BORE + 0.0380)))
    finish(fb, M('metal_parker'), bev=0.0007, texel=0.05, long=1)
    parts.append(fb)
    post = sight_post('frt_fspost', 0.0030, 0.0040, 0.0140, loc=(0, 0.2940, SIGHT_Z - 0.0140))
    finish(post, M('metal_parker'), bev=0.0004, texel=0.03, long=1)
    parts.append(post)

    # AKS-74U conical booster / flash hider
    bo = loft('frt_booster', [ring3(ellipse(r, r, 20, 0, BORE), y) for y, r in
                              ((0.3060, 0.0115), (0.3200, 0.0115), (0.3260, 0.0155),
                               (0.3800, 0.0195), (0.3860, 0.0195), (0.3900, 0.0170),
                               (0.4180, 0.0170), (0.4200, 0.0150))])
    cut(bo, cylinder('c_bo', 0.0125, 0.140, (0, 0.3700, BORE), 'Y', 20))
    cut(bo, grooves('c_bog', 2, 0.0090, (0.050, 0.0030, 0.050), loc=(0, 0.4040, BORE), axis=(0, 1, 0)))
    finish(bo, M('metal_parker'), bev=0.0007, texel=0.05, long=1)
    parts.append(bo)

    # wooden handguards (lower + upper)
    low = loft('frt_hglow', [ring3(rrect(w, h, r, 4, 0, BORE - 0.0125), y)
                             for y, w, h, r in ((0.1150, 0.0330, 0.0230, 0.0070),
                                                (0.1300, 0.0370, 0.0270, 0.0090),
                                                (0.2150, 0.0360, 0.0260, 0.0090),
                                                (0.2450, 0.0320, 0.0220, 0.0080))])
    cut(low, cylinder('c_l', 0.0115, 0.30, (0, 0.1800, BORE), 'Y', 20))
    cut(low, rbox('c_l2', (0.060, 0.30, 0.030), (0, 0.1800, BORE + 0.0135)))
    cut(low, grooves('c_lg', 3, 0.0130, (0.060, 0.0060, 0.0050), loc=(0, 0.1800, BORE - 0.0260),
                     axis=(0, 1, 0)))
    finish(low, M('wood_birch'), bev=0.0010, texel=0.11, long=1, jitter=0.6, seed=86)
    parts.append(low)
    up = loft('frt_hgup', [ring3(rrect(w, h, r, 4, 0, BORE + 0.0185), y)
                           for y, w, h, r in ((0.1200, 0.0300, 0.0210, 0.0065),
                                              (0.1350, 0.0330, 0.0250, 0.0080),
                                              (0.2200, 0.0325, 0.0245, 0.0080),
                                              (0.2450, 0.0290, 0.0200, 0.0070))])
    cut(up, cylinder('c_u', 0.0096, 0.30, (0, 0.1800, BORE + 0.0185), 'Y', 20))
    cut(up, rbox('c_u2', (0.060, 0.30, 0.030), (0, 0.1800, BORE - 0.0015)))
    finish(up, M('wood_birch'), bev=0.0010, texel=0.11, long=1, jitter=0.7, seed=87)
    parts.append(up)
    return fuse('front', parts)


def build_stock():
    """Side-folding triangular tube stock, deployed."""
    parts = []
    for sx in (-1, 1):
        for zz in (BORE + 0.0060, BORE - 0.0260):
            r = cylinder('stk_t%d_%d' % (sx, int(zz * 1e4)), 0.0058, 0.1550,
                         (sx * 0.0135, -0.1520, zz), 'Y', 14)
            finish(r, M('metal_parker'), bev=0.0004, texel=0.04, long=1)
            parts.append(r)
    bar = cylinder('stk_bar', 0.0058, 0.0270, (0, -0.2270, BORE - 0.0100), 'Z', 14)
    finish(bar, M('metal_parker'), bev=0.0004, texel=0.04)
    parts.append(bar)
    plate = prism('stk_plate', rrect(0.0420, 0.0430, 0.0080, 3, 0, BORE - 0.0100), -0.2340, -0.2260)
    finish(plate, M('metal_parker'), bev=0.0009, texel=0.05, long=1)
    parts.append(plate)
    hinge = prism('stk_hinge', rrect(0.0380, 0.0300, 0.0060, 2, 0, BORE - 0.0100), -0.0790, -0.0690)
    finish(hinge, M('metal_parker'), bev=0.0008, texel=0.05, long=1)
    parts.append(hinge)
    return fuse('stock', parts)


def build_mag():
    secs = []
    n = 16
    for i in range(n + 1):
        t = i / n
        z = (BORE - 0.0250) - 0.1700 * t
        y = 0.0560 + 0.0620 * (t ** 1.7)
        secs.append([(p[0], y + p[1], z) for p in rrect(0.0235 - 0.0015 * t,
                                                        0.0300 - 0.0030 * t, 0.0035, 2)])
    mag = loft('mag_body', secs)
    for sx in (-1, 1):       # shallow reinforcing ribs on the magazine flanks only
        cut(mag, grooves('c_mr%d' % sx, 5, 0.0260, (0.0040, 0.0030, 0.0090),
                         loc=(sx * 0.0128, 0.0900, BORE - 0.1100), axis=(0, 0.34, -0.94)))
    finish(mag, M('polymer_black'), bev=0.0009, texel=0.05, long=2, seed=88)
    fl = prism_x('mag_floor', [(0.1100, BORE - 0.1830), (0.1420, BORE - 0.1830),
                               (0.1430, BORE - 0.1930), (0.1090, BORE - 0.1930)], -0.0122, 0.0122)
    finish(fl, M('polymer_black'), bev=0.0008, texel=0.05, long=1)
    return fuse('mag', [mag, fl])


def build_bolt():
    """Bolt carrier + charging handle.

    The game slides this along the bore, rearward = Blender -Y = three.js local +Z
    (`boltTravel` 0.06 m for the AK).  The carrier fills the ejection port at rest and
    uncovers it as it runs back."""
    parts = []
    car = prism('bolt_carrier', rrect(0.0150, 0.0140, 0.0030, 1, -0.0015, BORE + 0.0055),
                0.0100, 0.0850)
    # relief cut so it does not read as a plain bar
    cut(car, rbox('c_bc1', (0.0300, 0.0260, 0.0044), (0, 0.0300, BORE + 0.0145)))
    finish(car, M('metal_steel'), bev=0.0008, texel=0.045, long=1, seed=89)
    parts.append(car)

    st = prism_x('bolt_stem', [(0.0600, BORE + 0.0025), (0.0762, BORE + 0.0025),
                               (0.0762, BORE + 0.0115), (0.0600, BORE + 0.0115)],
                 0.0020, 0.0175)
    finish(st, M('metal_steel'), bev=0.0006, texel=0.035, long=1)
    parts.append(st)
    kn = cylinder('bolt_knob', 0.0069, 0.0140, (0.0242, 0.0681, BORE + 0.0070), 'X', 12,
                  r2=0.0060)
    finish(kn, M('metal_steel'), bev=0.0006, texel=0.03, long=1)
    parts.append(kn)
    ob = fuse('bolt', parts)
    return set_origin(ob, (0.0, 0.0440, BORE + 0.0060))


def build(arms=True):
    reset_scene()
    prebake()
    guns = [build_receiver(), build_grip(), build_front(), build_stock(), build_mag(),
            build_bolt()]
    arm_r = arm_l = None
    if arms:
        arm_r = hand_on_grip((0.0190, -0.0180, BORE - 0.0570), rake=-0.42,
                             elbow=(0.100, -0.030, -0.300))
        arm_l = hand_on_handguard((-0.0255, 0.1750, BORE - 0.0130), lean=0.20,
                                  elbow=(-0.135, -0.020, -0.290))
    muzzle = (0.0, Y_MUZZLE, BORE)
    eject = (0.0180, 0.0440, BORE + 0.0060)
    aim = (0.0, -0.0575, SIGHT_Z)
    return dict(guns=guns, arm_r=arm_r, arm_l=arm_l, muzzle=muzzle, eject=eject, aim=aim)


if __name__ == '__main__':
    d = build()
    deliver(WID, GRIP_POS, d['guns'], d['muzzle'], d['eject'], d['aim'], d['arm_r'], d['arm_l'],
            movable=('mag', 'bolt'), detail_target=(0, 0.130, 0.020), detail_dist=0.78, lens=52,
            ads_back=0.32)
    print('DONE')
