"""RPD belt-fed light machine gun - first-person viewmodel.

Gun space: origin at the web of the right hand on the small of the stock, bore along +Y at BORE.
Real RPD: 1037 mm, 520 mm barrel, 100-round belt in a drum under the receiver, folding bipod.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_weapons import *                                   # noqa

WID = 'rpd'
BORE = 0.0420
Y_BUTT = -0.2900
Y_MUZZLE = 0.7450
SIGHT_Z = BORE + 0.0390
GRIP_POS = (0.150, 0.280, -0.112)


def build_stock():
    parts = []
    out = [
        (Y_BUTT, BORE - 0.0940), (Y_BUTT - 0.0080, BORE - 0.0830),
        (Y_BUTT - 0.0065, BORE + 0.0020), (Y_BUTT + 0.0150, BORE + 0.0085),
        (-0.2050, BORE + 0.0090), (-0.1450, BORE + 0.0060),   # comb, 30 mm under the
        (-0.1030, BORE + 0.0000), (-0.0800, BORE - 0.0110),   # sight line
        (-0.0450, BORE - 0.0180), (-0.0140, BORE - 0.0220),
        (0.0060, BORE - 0.0240), (0.0060, BORE - 0.0430),
        (-0.0230, BORE - 0.0460), (-0.0500, BORE - 0.0510),
        (-0.0800, BORE - 0.0650), (-0.1180, BORE - 0.0880),
        (-0.1720, BORE - 0.0980), (-0.2300, BORE - 0.0960),
        (Y_BUTT + 0.0060, BORE - 0.0880),
    ]
    st = prism_x('stk_body', out, -0.0230, 0.0230)
    env = loft('c_env', [ring3(rrect(w, 0.300, r, 5, 0, BORE - 0.030), y)
                         for y, w, r in ((Y_BUTT - 0.020, 0.0455, 0.0070),
                                         (-0.2400, 0.0450, 0.0085),
                                         (-0.1600, 0.0430, 0.0115),
                                         (-0.1000, 0.0395, 0.0150),
                                         (-0.0450, 0.0400, 0.0140),
                                         (0.0100, 0.0450, 0.0095))])
    boolean(st, env, 'INTERSECT')
    cut(st, rbox('c_rec', (0.080, 0.090, 0.070), (0, 0.0500, BORE)))
    finish(st, M('wood_birch'), bev=0.0020, segs=3, texel=0.16, long=1, jitter=0.4, seed=121)
    parts.append(st)
    pad = prism_x('stk_plate', [(Y_BUTT - 0.0090, BORE - 0.0955), (Y_BUTT + 0.0015, BORE - 0.0965),
                                (Y_BUTT + 0.0080, BORE + 0.0095), (Y_BUTT - 0.0085, BORE + 0.0030)],
                  -0.0200, 0.0200)
    finish(pad, M('metal_parker'), bev=0.0012, texel=0.05, long=2)
    parts.append(pad)
    return fuse('stock', parts)


def build_receiver():
    parts = []
    body = prism('rcv_body', rrect(0.0420, 0.0520, 0.0060, 3, 0, BORE - 0.0030), -0.0120, 0.1750)
    cut(body, rbox('c_port', (0.020, 0.0620, 0.0200), (0.0225, 0.0800, BORE + 0.0080)))
    # belt feed opening on the left
    cut(body, rbox('c_feed', (0.020, 0.0560, 0.0170), (-0.0225, 0.0800, BORE + 0.0090)))
    # drum mount underneath
    cut(body, rbox('c_drum', (0.030, 0.0620, 0.0100), (0, 0.0800, BORE - 0.0270)))
    # bolt-carrier raceway + the charging-handle slot in the right wall (the `bolt` object
    # rides in these and uncovers the port as it runs back)
    cut(body, rbox('c_race', (0.0245, 0.1350, 0.0180), (0.0003, 0.0875, BORE + 0.0080)))
    cut(body, rbox('c_chslot', (0.0140, 0.1000, 0.0080), (0.0150, 0.1000, BORE + 0.0060)))
    finish(body, M('metal_parker'), bev=0.0011, segs=2, texel=0.065, long=1, jitter=0.2, seed=122)
    parts.append(body)

    # top cover with the feed tray
    cov = prism('rcv_cover', rrect(0.0420, 0.0180, 0.0060, 3, 0, BORE + 0.0300), 0.0120, 0.1450)
    cut(cov, grooves('c_cr', 2, 0.0260, (0.060, 0.0040, 0.0050), loc=(0, 0.0800, BORE + 0.0380),
                     axis=(0, 1, 0)))
    finish(cov, M('metal_parker'), bev=0.0009, texel=0.06, long=1, seed=123)
    parts.append(cov)

    # rear tangent sight
    tow = prism('rcv_rsight', rrect(0.0230, 0.0240, 0.0035, 2, 0, BORE + 0.0320), -0.0080, 0.0120)
    cut(tow, rbox('c_nt', (0.0050, 0.040, 0.0080), (0, 0.0020, SIGHT_Z + 0.0040)))
    finish(tow, M('metal_parker'), bev=0.0006, texel=0.04, long=1)
    parts.append(tow)
    lad = prism('rcv_ladder', rrect(0.0170, 0.0090, 0.0020, 2, 0, BORE + 0.0230), -0.0120, 0.0580)
    finish(lad, M('metal_parker'), bev=0.0006, texel=0.04, long=1)
    parts.append(lad)

    guard = prism_x('rcv_guard', arc_pts(-0.0170, BORE - 0.0560, 0.0210, 30, -180, 9)
                    + [(-0.0380, BORE - 0.0470), (-0.0320, BORE - 0.0380),
                       (0.0050, BORE - 0.0370), (0.0060, BORE - 0.0470)], -0.0080, 0.0080)
    cut(guard, prism_x('c_g', arc_pts(-0.0170, BORE - 0.0560, 0.0145, 40, -190, 9)
                       + [(-0.0320, BORE - 0.0450), (0.0000, BORE - 0.0445)], -0.03, 0.03))
    finish(guard, M('metal_parker'), bev=0.0007, texel=0.04, long=1)
    parts.append(guard)
    trg = prism_x('rcv_trigger', [(-0.0170, BORE - 0.0450), (-0.0090, BORE - 0.0455),
                                  (-0.0075, BORE - 0.0620), (-0.0155, BORE - 0.0610)],
                  -0.0050, 0.0050)
    finish(trg, M('metal_steel'), bev=0.0005, texel=0.03, long=1)
    parts.append(trg)
    return fuse('receiver', parts)


def build_barrel():
    parts = []
    b = loft('bar_tube', [ring3(ellipse(r, r, 20, 0, BORE), y) for y, r in
                          ((0.1600, 0.0160), (0.2000, 0.0135), (0.3000, 0.0118),
                           (0.6200, 0.0105), (0.6800, 0.0105))])
    cut(b, cylinder('c_b', 0.0040, 0.70, (0, 0.4000, BORE), 'Y', 18))
    finish(b, M('metal_parker'), bev=0.0007, texel=0.06, long=1, seed=125)
    parts.append(b)
    # gas tube under the barrel
    gt = cylinder('bar_gastube', 0.0090, 0.3400, (0, 0.4300, BORE - 0.0215), 'Y', 18)
    finish(gt, M('metal_parker'), bev=0.0005, texel=0.05, long=1)
    parts.append(gt)
    gb = prism('bar_gasblock', rrect(0.0230, 0.0430, 0.0035, 2, 0, BORE - 0.0110), 0.5700, 0.6050)
    cut(gb, cylinder('c_gb', 0.0110, 0.05, (0, 0.5875, BORE), 'Y', 18))
    finish(gb, M('metal_parker'), bev=0.0008, texel=0.05, long=1)
    parts.append(gb)
    # front sight with ears
    fb = prism('bar_fsbase', rrect(0.0240, 0.0330, 0.0035, 2, 0, BORE + 0.0180), 0.6800, 0.7080)
    cut(fb, cylinder('c_fb', 0.0110, 0.05, (0, 0.6940, BORE), 'Y', 18))
    cut(fb, rbox('c_fb2', (0.0130, 0.040, 0.0190), (0, 0.6940, BORE + 0.0400)))
    finish(fb, M('metal_parker'), bev=0.0007, texel=0.05, long=1)
    parts.append(fb)
    post = sight_post('bar_fspost', 0.0030, 0.0042, 0.0150, loc=(0, 0.6940, SIGHT_Z - 0.0150))
    finish(post, M('metal_parker'), bev=0.0004, texel=0.03, long=1)
    parts.append(post)
    # muzzle cone
    mz = loft('bar_muzzle', [ring3(ellipse(r, r, 20, 0, BORE), y) for y, r in
                             ((0.7120, 0.0105), (0.7180, 0.0135), (0.7420, 0.0135),
                              (0.7450, 0.0112))])
    cut(mz, cylinder('c_mz', 0.0068, 0.10, (0, 0.7300, BORE), 'Y', 18))
    finish(mz, M('metal_parker'), bev=0.0006, texel=0.04, long=1)
    parts.append(mz)

    # wooden handguard
    hg = loft('bar_hg', [ring3(rrect(w, h, r, 4, 0, BORE - 0.0060), y)
                         for y, w, h, r in ((0.1900, 0.0420, 0.0470, 0.0110),
                                            (0.2100, 0.0470, 0.0520, 0.0130),
                                            (0.3400, 0.0455, 0.0500, 0.0130),
                                            (0.3750, 0.0400, 0.0430, 0.0110),
                                            (0.3840, 0.0340, 0.0360, 0.0095))])
    cut(hg, cylinder('c_h1', 0.0145, 0.30, (0, 0.2800, BORE), 'Y', 20))
    cut(hg, cylinder('c_h2', 0.0105, 0.30, (0, 0.2800, BORE - 0.0215), 'Y', 20))
    cut(hg, rbox('c_h3', (0.021, 0.30, 0.030), (0, 0.2800, BORE - 0.0160)))
    cut(hg, rbox('c_h4', (0.060, 0.30, 0.020), (0, 0.2800, BORE + 0.0300)))
    finish(hg, M('wood_birch'), bev=0.0014, texel=0.13, long=1, jitter=0.6, seed=126)
    parts.append(hg)

    # folded bipod legs tucked under the gas tube
    for sx in (-1, 1):
        leg = cylinder('bar_bipod%d' % sx, 0.0052, 0.1900, (sx * 0.0110, 0.5100, BORE - 0.0350),
                       'Y', 12)
        finish(leg, M('metal_parker'), bev=0.0004, texel=0.04, long=1)
        parts.append(leg)
    bm = prism('bar_bipodmnt', rrect(0.0300, 0.0150, 0.0035, 2, 0, BORE - 0.0320), 0.5950, 0.6200)
    finish(bm, M('metal_parker'), bev=0.0006, texel=0.04, long=1)
    parts.append(bm)
    return fuse('barrel', parts)


def build_drum():
    """100-round belt drum hanging under the receiver."""
    parts = []
    d = lathe('mag_drum', [(0.0000, -0.0620), (0.0520, -0.0620), (0.0620, -0.0560),
                           (0.0620, 0.0480), (0.0530, 0.0540), (0.0000, 0.0540)],
              segs=28, loc=(0, 0.0840, BORE - 0.0940), rot=(D2R(90), 0, 0))
    finish(d, M('metal_parker'), bev=0.0012, texel=0.075, long=2, seed=127)
    parts.append(d)
    # latch band + lid seam
    band = lathe('mag_band', [(0.0625, -0.0080), (0.0650, -0.0060), (0.0650, 0.0060),
                              (0.0625, 0.0080)], segs=28, loc=(0, 0.0840, BORE - 0.0940),
                 rot=(D2R(90), 0, 0))
    finish(band, M('metal_parker'), bev=0.0006, texel=0.05, long=2)
    parts.append(band)
    lat = rbox('mag_latch', (0.0260, 0.0160, 0.0090), (0, 0.0840, BORE - 0.0290))
    finish(lat, M('metal_parker'), bev=0.0008, texel=0.04)
    parts.append(lat)
    # a few belt links climbing into the feed
    for i in range(4):
        t = i / 3.0
        lk = rbox('mag_link%d' % i, (0.0130, 0.0095, 0.0130),
                  (-0.0170 - 0.0020 * i, 0.0790 + 0.0105 * i, BORE - 0.0220 + 0.0090 * i),
                  rot=(D2R(-18), 0, 0))
        finish(lk, M('metal_brass'), bev=0.0006, texel=0.03)
        parts.append(lk)
    return fuse('mag', parts)


def build_bolt():
    """Bolt carrier + the RPD's right-side charging handle.

    Slides rearward along Blender -Y (three.js local +Z), `boltTravel` 0.065 m."""
    parts = []
    car = prism('bolt_carrier', rrect(0.0220, 0.0150, 0.0035, 2, 0.0010, BORE + 0.0075),
                0.0550, 0.1480)
    cut(car, rbox('c_bc', (0.0300, 0.0420, 0.0050), (0, 0.0800, BORE + 0.0165)))
    finish(car, M('metal_steel'), bev=0.0008, texel=0.045, long=1, seed=128)
    parts.append(car)
    st = prism_x('bolt_stem', [(0.1230, BORE + 0.0030), (0.1390, BORE + 0.0030),
                               (0.1390, BORE + 0.0090), (0.1230, BORE + 0.0090)],
                 0.0100, 0.0215)
    finish(st, M('metal_steel'), bev=0.0005, texel=0.035, long=1)
    parts.append(st)
    ch = prism_x('bolt_handle', [(0.1180, BORE + 0.0105), (0.1440, BORE + 0.0105),
                                 (0.1440, BORE + 0.0015), (0.1180, BORE + 0.0015)],
                 0.0210, 0.0300)
    cut(ch, grooves('c_chr', 3, 0.0060, (0.030, 0.0022, 0.0022), loc=(0.0255, 0.1310, BORE + 0.0105),
                    axis=(0, 1, 0)))
    finish(ch, M('metal_parker'), bev=0.0006, texel=0.04, long=1)
    parts.append(ch)
    ob = fuse('bolt', parts)
    return set_origin(ob, (0.0, 0.1000, BORE + 0.0080))


def build(arms=True):
    reset_scene()
    prebake()
    guns = [build_stock(), build_receiver(), build_barrel(), build_drum(), build_bolt()]
    arm_r = arm_l = None
    if arms:
        arm_r = hand_on_grip((0.0250, -0.0620, BORE - 0.0380), rake=-0.22,
                             elbow=(0.100, -0.030, -0.300), curl=(0.70, 0.86, 0.90, 0.92))
        arm_l = hand_on_handguard((-0.0320, 0.2700, BORE - 0.0060), lean=0.20,
                                  elbow=(-0.140, -0.020, -0.290))
    muzzle = (0.0, Y_MUZZLE, BORE)
    eject = (0.0235, 0.0800, BORE + 0.0080)
    aim = (0.0, 0.0020, SIGHT_Z)
    return dict(guns=guns, arm_r=arm_r, arm_l=arm_l, muzzle=muzzle, eject=eject, aim=aim)


if __name__ == '__main__':
    d = build()
    deliver(WID, GRIP_POS, d['guns'], d['muzzle'], d['eject'], d['aim'], d['arm_r'], d['arm_l'],
            movable=('mag', 'bolt'), detail_target=(0, 0.210, 0.005), detail_dist=1.05, lens=52,
            ads_back=0.34)
    print('DONE')
