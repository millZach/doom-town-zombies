"""M14 7.62 mm semi-auto rifle - first-person viewmodel.

Gun space: origin at the web of the right hand on the small of the stock, bore along +Y at BORE.
Real M14: 1118 mm overall, 559 mm barrel, walnut stock, 20-round box magazine.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_weapons import *                                   # noqa

WID = 'm14'
BORE = 0.0380
Y_BUTT = -0.3350
Y_MUZZLE = 0.7830                   # 1118 mm overall
SIGHT_Z = BORE + 0.0250   # == front post tip, so the sight line is parallel to +Y
GRIP_POS = (0.145, 0.290, -0.112)
TX = 0.075


def build_stock():
    """One-piece walnut stock: butt, comb, wrist, fore-end."""
    parts = []
    top = BORE - 0.0060
    out = [
        (Y_BUTT, BORE - 0.0860), (Y_BUTT - 0.0075, BORE - 0.0740),
        (Y_BUTT - 0.0065, BORE - 0.0130), (Y_BUTT + 0.0140, BORE - 0.0085),
        (-0.2560, BORE - 0.0075), (-0.1880, BORE - 0.0070),          # comb, 30 mm under
        (-0.1420, BORE - 0.0060), (-0.1180, BORE - 0.0060),          # the sight line
        (-0.0820, BORE - 0.0090), (-0.0300, BORE - 0.0110),
        (0.0180, BORE - 0.0110), (0.0620, BORE - 0.0120),
        (0.1450, BORE - 0.0125), (0.2400, BORE - 0.0130),
        (0.3260, BORE - 0.0135), (0.3480, BORE - 0.0230),            # fore-end tip
        (0.3300, BORE - 0.0330), (0.2400, BORE - 0.0350),
        (0.1450, BORE - 0.0355), (0.0700, BORE - 0.0360),
        (0.0180, BORE - 0.0430),                                     # magwell cut-out front
        (0.0180, BORE - 0.0560), (-0.0280, BORE - 0.0560),
        (-0.0560, BORE - 0.0470),                                    # trigger area
        (-0.0900, BORE - 0.0560), (-0.1280, BORE - 0.0720),
        (-0.1900, BORE - 0.0900), (-0.2600, BORE - 0.0930),
        (-0.3080, BORE - 0.0850), (Y_BUTT + 0.0040, BORE - 0.0770),
    ]
    st = prism_x('stk_body', out, -0.0235, 0.0235)
    # give the stock a real rounded cross-section that changes along its length
    env = loft('c_env', [ring3(rrect(w, 0.300, r, 5, 0, BORE - 0.0300), y)
                         for y, w, r in ((Y_BUTT - 0.020, 0.0470, 0.0060),
                                         (Y_BUTT + 0.030, 0.0470, 0.0070),
                                         (-0.2000, 0.0450, 0.0090),
                                         (-0.1250, 0.0400, 0.0140),
                                         (-0.0700, 0.0415, 0.0130),
                                         (0.0000, 0.0470, 0.0060),
                                         (0.1000, 0.0470, 0.0070),
                                         (0.2000, 0.0440, 0.0105),
                                         (0.3000, 0.0415, 0.0120),
                                         (0.3600, 0.0375, 0.0125))])
    boolean(st, env, 'INTERSECT')
    # barrel channel
    cut(st, cylinder('c_ch', 0.0140, 0.60, (0, 0.2200, BORE), 'Y', 20))
    cut(st, rbox('c_chr', (0.0280, 0.60, 0.030), (0, 0.2200, BORE + 0.0140)))
    # receiver inlet
    cut(st, rbox('c_rec', (0.0350, 0.2200, 0.0300), (0, 0.0950, BORE + 0.0080)))
    # magazine well
    cut(st, prism_x('c_mag', [(0.0180, BORE - 0.0110), (0.0700, BORE - 0.0120),
                              (0.0760, BORE - 0.0600), (0.0100, BORE - 0.0600)], -0.0135, 0.0135))
    # trigger slot
    cut(st, rbox('c_trg', (0.0130, 0.0420, 0.0300), (0, -0.0280, BORE - 0.0420)))
    finish(st, M('wood_walnut'), bev=0.0018, segs=3, texel=0.17, long=1, jitter=0.3, seed=21)
    parts.append(st)

    # upper handguard
    hg = loft('stk_uhg', [ring3(rrect(w, 0.060, r, 4, 0, BORE + 0.0060), y)
                          for y, w, r in ((0.1520, 0.0310, 0.0090), (0.1650, 0.0330, 0.0105),
                                          (0.2900, 0.0325, 0.0110), (0.3450, 0.0300, 0.0110),
                                          (0.3560, 0.0270, 0.0105))])
    cut(hg, rbox('c_hgu', (0.060, 0.40, 0.040), (0, 0.2500, BORE + 0.0400)))
    cut(hg, cylinder('c_hgb', 0.0126, 0.40, (0, 0.2500, BORE), 'Y', 22))
    cut(hg, rbox('c_hgd', (0.060, 0.40, 0.040), (0, 0.2500, BORE - 0.0180)))
    finish(hg, M('wood_walnut'), bev=0.0010, texel=0.17, long=1, jitter=0.5, seed=23)
    parts.append(hg)

    # steel butt plate with a hinged shoulder rest
    bp = prism_x('stk_plate', [(Y_BUTT - 0.0085, BORE - 0.0870), (Y_BUTT + 0.0010, BORE - 0.0880),
                               (Y_BUTT + 0.0075, BORE - 0.0070), (Y_BUTT - 0.0080, BORE - 0.0120)],
                 -0.0205, 0.0205)
    cut(bp, grooves('c_bpg', 9, 0.0080, (0.060, 0.0022, 0.0022),
                    loc=(Y_BUTT - 0.0040, -0.0130, BORE), axis=(0, 0, 1), rot=(0, 0, 0)))
    finish(bp, M('metal_parker'), bev=0.0008, texel=0.05, long=2)
    parts.append(bp)

    # sling swivels
    for y in (-0.2450, 0.2950):
        sw = tube('stk_swivel%d' % int(y * 1e3), 0.0072, 0.0050, 0.0032,
                  (0, y, BORE - (0.0600 if y < 0 else 0.0370)), 'Z', 16)
        finish(sw, M('metal_parker'), bev=0.0004, texel=0.03)
        parts.append(sw)
    return fuse('stock', parts)


def build_receiver():
    parts = []
    body = prism('rcv_body', rrect(0.0330, 0.0340, 0.0055, 3, 0, BORE + 0.0040), -0.0480, 0.1520)
    # heel / rear hump
    boolean(body, prism('rcv_hump', rrect(0.0320, 0.0300, 0.0060, 3, 0, BORE + 0.0140),
                        -0.0480, 0.0060), 'UNION')
    # ejection port (right)
    cut(body, rbox('c_port', (0.020, 0.0620, 0.0180), (0.0175, 0.0560, BORE + 0.0110)))
    # clip guide / top opening
    cut(body, rbox('c_top', (0.0210, 0.0900, 0.0130), (0, 0.0560, BORE + 0.0215)))
    finish(body, M('metal_parker'), bev=0.0009, texel=TX, long=1, jitter=0.2, seed=31)
    parts.append(body)

    # bolt (movable) is built separately; op-rod on the right side
    rod = prism('rcv_oprod', rrect(0.0110, 0.0140, 0.0030, 2, 0.0210, BORE + 0.0035), 0.0900, 0.3600)
    finish(rod, M('metal_parker'), bev=0.0006, texel=0.05, long=1)
    parts.append(rod)

    # rear aperture sight
    tow = prism('rcv_sighttower', [(-0.0090, BORE + 0.0190), (0.0090, BORE + 0.0190),
                                   (0.0090, BORE + 0.0330), (-0.0090, BORE + 0.0330)],
                -0.0320, -0.0140)
    cut(tow, cylinder('c_ap', 0.0029, 0.030, (0, -0.0230, SIGHT_Z), 'Y', 16))
    cut(tow, cylinder('c_apc', 0.0048, 0.0090, (0, -0.0150, SIGHT_Z), 'Y', 18))
    finish(tow, M('metal_parker'), bev=0.0005, texel=0.04, long=1)
    parts.append(tow)
    for sx in (-1, 1):
        kn = knurl_band('rcv_sknob%d' % sx, 0.0062, 0.0055, (sx * 0.0122, -0.0230, BORE + 0.0270),
                        'X', n_around=20, n_up=4, depth=0.0004)
        finish(kn, M('metal_parker'), bev=0.0, texel=0.03)
        parts.append(kn)

    # trigger group: guard + trigger + safety
    guard = prism_x('rcv_guard', arc_pts(-0.0310, BORE - 0.0630, 0.0200, 30, -180, 9)
                    + [(-0.0510, BORE - 0.0560), (-0.0480, BORE - 0.0460),
                       (-0.0100, BORE - 0.0430), (-0.0090, BORE - 0.0530)], -0.0072, 0.0072)
    cut(guard, prism_x('c_g', arc_pts(-0.0310, BORE - 0.0630, 0.0135, 40, -190, 9)
                       + [(-0.0455, BORE - 0.0540), (-0.0160, BORE - 0.0520)], -0.03, 0.03))
    finish(guard, M('metal_parker'), bev=0.0006, texel=0.04, long=1)
    parts.append(guard)
    trg = prism_x('rcv_trigger', [(-0.0330, BORE - 0.0430), (-0.0250, BORE - 0.0435),
                                  (-0.0230, BORE - 0.0610), (-0.0310, BORE - 0.0600)],
                  -0.0052, 0.0052)
    finish(trg, M('metal_steel'), bev=0.0005, texel=0.03, long=1)
    parts.append(trg)
    sfty = prism_x('rcv_safety', [(-0.0140, BORE - 0.0400), (-0.0030, BORE - 0.0400),
                                  (-0.0030, BORE - 0.0470), (-0.0150, BORE - 0.0470)],
                   -0.0048, 0.0048)
    finish(sfty, M('metal_parker'), bev=0.0005, texel=0.03, long=1)
    parts.append(sfty)
    return fuse('receiver', parts)


def build_bolt():
    """Bolt + operating-rod handle (the game can cycle it)."""
    h = prism('bolt_handle', rrect(0.0230, 0.0130, 0.0040, 2, 0.0250, BORE + 0.0060), 0.0680, 0.0900)
    k = cylinder('bolt_knob', 0.0068, 0.0130, (0.0355, 0.0790, BORE + 0.0060), 'X', 18)
    b = prism('bolt_body', rrect(0.0180, 0.0150, 0.0040, 2, 0, BORE + 0.0110), 0.0330, 0.0940)
    for o in (h, k, b):
        finish(o, M('metal_steel'), bev=0.0006, texel=0.04, long=1)
    return fuse('bolt', [h, k, b])


def build_barrel():
    parts = []
    b = loft('bar_barrel', [
        ring3(ellipse(0.0135, 0.0135, 20, 0, BORE), 0.1400),
        ring3(ellipse(0.0120, 0.0120, 20, 0, BORE), 0.2400),
        ring3(ellipse(0.0098, 0.0098, 20, 0, BORE), 0.4200),
        ring3(ellipse(0.0090, 0.0090, 20, 0, BORE), 0.6900),
        ring3(ellipse(0.0090, 0.0090, 20, 0, BORE), 0.7100)])
    cut(b, cylinder('c_bore', 0.0046, 0.80, (0, 0.4000, BORE), 'Y', 18))
    finish(b, M('metal_parker'), bev=0.0006, texel=0.06, long=1)
    parts.append(b)

    # gas cylinder under the barrel
    gc = cylinder('bar_gas', 0.0115, 0.2600, (0, 0.5100, BORE - 0.0135), 'Y', 20)
    cut(gc, cylinder('c_gc', 0.0092, 0.30, (0, 0.5100, BORE - 0.0135), 'Y', 18))
    finish(gc, M('metal_parker'), bev=0.0006, texel=0.05, long=1)
    parts.append(gc)
    gp = prism('bar_gasplug', rrect(0.0180, 0.0190, 0.0030, 2, 0, BORE - 0.0080), 0.3850, 0.4250)
    finish(gp, M('metal_parker'), bev=0.0008, texel=0.05, long=1)
    parts.append(gp)

    # front sight with protective wings
    fb = prism('bar_fsbase', rrect(0.0240, 0.0150, 0.0030, 2, 0, BORE + 0.0060), 0.6880, 0.7080)
    finish(fb, M('metal_parker'), bev=0.0006, texel=0.04, long=1)
    parts.append(fb)
    post = sight_post('bar_fspost', 0.0028, 0.0042, 0.0140, loc=(0, 0.6980, BORE + 0.0110))
    finish(post, M('metal_parker'), bev=0.0005, texel=0.03, long=1)
    parts.append(post)
    for sx in (-1, 1):
        wg = prism('bar_fswing%d' % sx, [(sx * 0.0080, BORE + 0.0110), (sx * 0.0118, BORE + 0.0110),
                                         (sx * 0.0112, BORE + 0.0290), (sx * 0.0074, BORE + 0.0290)],
                   0.6900, 0.7060)
        finish(wg, M('metal_parker'), bev=0.0005, texel=0.03, long=1)
        parts.append(wg)

    # flash suppressor
    fs = cylinder('bar_flash', 0.0142, 0.0640, (0, 0.7510, BORE), 'Y', 22, r2=0.0150)
    cut(fs, cylinder('c_fs', 0.0102, 0.0700, (0, 0.7510, BORE), 'Y', 20))
    for i in range(4):
        a = D2R(35 + i * 44)
        cut(fs, rbox('c_fsl%d' % i, (0.0035, 0.0400, 0.040), (0, 0.7560, BORE), rot=(0, -a, 0)))
    cut(fs, grooves('c_fsg', 3, 0.0090, (0.050, 0.0030, 0.050), loc=(0, 0.7350, BORE), axis=(0, 1, 0)))
    finish(fs, M('metal_parker'), bev=0.0006, texel=0.04, long=1)
    parts.append(fs)
    return fuse('barrel', parts)


def build_mag():
    secs = []
    n = 12
    for i in range(n + 1):
        t = i / n
        z = (BORE - 0.0150) - 0.1180 * t
        y = 0.0430 + 0.0140 * (t ** 1.8)
        secs.append([(p[0], y + p[1], z) for p in rrect(0.0250 - 0.0010 * t, 0.0455 - 0.0040 * t,
                                                        0.0038, 2)])
    mag = loft('mag_body', secs)
    finish(mag, M('metal_parker'), bev=0.0009, texel=0.05, long=2, seed=41)
    fl = prism_x('mag_floor', [(0.0350, BORE - 0.1300), (0.0800, BORE - 0.1300),
                               (0.0810, BORE - 0.1400), (0.0340, BORE - 0.1400)], -0.0138, 0.0138)
    finish(fl, M('metal_parker'), bev=0.0009, texel=0.05, long=1)
    return fuse('mag', [mag, fl])


def build(arms=True):
    reset_scene()
    prebake()
    guns = [build_stock(), build_receiver(), build_bolt(), build_barrel(), build_mag()]
    arm_r = arm_l = None
    if arms:
        # the M14 has no pistol grip: the hand wraps the small of the stock
        arm_r = hand_on_grip((0.0250, -0.0620, BORE - 0.0310), rake=-0.20,
                             elbow=(0.100, -0.030, -0.300), curl=(0.70, 0.86, 0.90, 0.92))
        arm_l = hand_on_handguard((-0.0290, 0.2450, BORE - 0.0080), lean=0.22,
                                  elbow=(-0.140, -0.020, -0.290))
    muzzle = (0.0, Y_MUZZLE, BORE)
    eject = (0.0195, 0.0560, BORE + 0.0110)
    aim = (0.0, -0.0230, SIGHT_Z)
    return dict(guns=guns, arm_r=arm_r, arm_l=arm_l, muzzle=muzzle, eject=eject, aim=aim)


if __name__ == '__main__':
    d = build()
    deliver(WID, GRIP_POS, d['guns'], d['muzzle'], d['eject'], d['aim'], d['arm_r'], d['arm_l'],
            movable=('mag', 'bolt'), detail_target=(0, 0.230, 0.010), detail_dist=1.05, lens=52,
            grip_view=(0, 0.00, -0.03), ads_back=0.33)
    print('DONE')
