"""Remington 870 12-gauge pump shotgun - first-person viewmodel.

Gun space: origin at the web of the right hand on the small of the stock, bore along +Y.
Real 870: 1060 mm with a 508 mm barrel; this is the short 470 mm riot version (~950 mm).
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_weapons import *                                   # noqa

WID = 'remington870'
BORE = 0.0360
TUBE_Z = BORE - 0.0270          # magazine tube centre
Y_BUTT = -0.2900
Y_MUZZLE = 0.6300
SIGHT_Z = BORE + 0.0200   # == notch floor == bead centre
GRIP_POS = (0.150, 0.288, -0.110)


def build_stock():
    parts = []
    out = [
        (Y_BUTT, BORE - 0.0980), (Y_BUTT - 0.0080, BORE - 0.0860),
        (Y_BUTT - 0.0070, BORE - 0.0160), (Y_BUTT + 0.0160, BORE - 0.0125),
        (-0.2050, BORE - 0.0115), (-0.1400, BORE - 0.0060),   # comb, 30 mm under the sight line
        (-0.0980, BORE + 0.0080), (-0.0760, BORE - 0.0070),
        (-0.0440, BORE - 0.0155), (-0.0140, BORE - 0.0190),
        (0.0080, BORE - 0.0200), (0.0080, BORE - 0.0390),
        (-0.0200, BORE - 0.0420), (-0.0480, BORE - 0.0470),
        (-0.0780, BORE - 0.0610), (-0.1150, BORE - 0.0860),
        (-0.1700, BORE - 0.1010), (-0.2300, BORE - 0.1000),
        (Y_BUTT + 0.0060, BORE - 0.0940),
    ]
    st = prism_x('stk_body', out, -0.0235, 0.0235)
    env = loft('c_env', [ring3(rrect(w, 0.300, r, 5, 0, BORE - 0.030), y)
                         for y, w, r in ((Y_BUTT - 0.020, 0.0460, 0.0065),
                                         (-0.2400, 0.0455, 0.0080),
                                         (-0.1600, 0.0440, 0.0110),
                                         (-0.1000, 0.0400, 0.0150),
                                         (-0.0450, 0.0400, 0.0140),
                                         (0.0100, 0.0450, 0.0090))])
    boolean(st, env, 'INTERSECT')
    cut(st, rbox('c_rec', (0.080, 0.080, 0.060), (0, 0.0400, BORE)))
    finish(st, M('wood_walnut'), bev=0.0020, segs=3, texel=0.16, long=1, jitter=0.4, seed=71)
    parts.append(st)
    for sx in (-1, 1):
        ck = checkering('stk_ck%d' % sx, 0.058, 0.020, nu=16, nv=6, depth=0.0008, thick=0.0010)
        place(ck, (sx * 0.0190, -0.0520, BORE - 0.0210), (0, 1, 0.20), (sx, 0, 0))
        finish(ck, M('wood_walnut'), bev=0.0, texel=0.16, long=1, seed=71)
        parts.append(ck)
    pad = prism_x('stk_pad', [(Y_BUTT - 0.0100, BORE - 0.1000), (Y_BUTT + 0.0015, BORE - 0.1010),
                              (Y_BUTT + 0.0085, BORE - 0.0110), (Y_BUTT - 0.0090, BORE - 0.0150)],
                  -0.0205, 0.0205)
    finish(pad, M('polymer_rubber'), bev=0.0014, texel=0.05, long=2)
    parts.append(pad)
    return fuse('stock', parts)


def build_receiver():
    parts = []
    # top at BORE+0.0120, i.e. 8 mm clear under the line of sight (was BORE+0.0205, which is
    # ABOVE SIGHT_Z - the receiver blocked the rear notch from every eye position)
    body = prism('rcv_body', rrect(0.0400, 0.0345, 0.0075, 3, 0, BORE - 0.0053), -0.0060, 0.1160)
    # loading port underneath
    cut(body, rbox('c_load', (0.030, 0.0640, 0.0120), (0, 0.0400, BORE - 0.0235)))
    # ejection port (right)
    cut(body, rbox('c_port', (0.020, 0.0700, 0.0150), (0.0200, 0.0560, BORE + 0.0000)))
    finish(body, M('metal_blued'), bev=0.0011, segs=2, texel=0.07, long=1, jitter=0.2, seed=73)
    parts.append(body)

    # trigger plate assembly
    grp = prism_x('rcv_tgroup', [(-0.0040, BORE - 0.0230), (0.0380, BORE - 0.0230),
                                 (0.0380, BORE - 0.0360), (-0.0040, BORE - 0.0370)],
                  -0.0150, 0.0150)
    finish(grp, M('metal_blued'), bev=0.0008, texel=0.05, long=1)
    parts.append(grp)
    guard = prism_x('rcv_guard', arc_pts(0.0100, BORE - 0.0490, 0.0215, 30, -180, 9)
                    + [(-0.0115, BORE - 0.0400), (-0.0060, BORE - 0.0300),
                       (0.0330, BORE - 0.0295), (0.0340, BORE - 0.0400)], -0.0080, 0.0080)
    cut(guard, prism_x('c_g', arc_pts(0.0100, BORE - 0.0490, 0.0150, 40, -190, 9)
                       + [(-0.0050, BORE - 0.0380), (0.0270, BORE - 0.0370)], -0.03, 0.03))
    finish(guard, M('metal_blued'), bev=0.0007, texel=0.04, long=1)
    parts.append(guard)
    trg = prism_x('rcv_trigger', [(0.0090, BORE - 0.0380), (0.0170, BORE - 0.0385),
                                  (0.0180, BORE - 0.0560), (0.0100, BORE - 0.0550)],
                  -0.0050, 0.0050)
    finish(trg, M('metal_steel'), bev=0.0005, texel=0.03, long=1)
    parts.append(trg)
    sb = cylinder('rcv_safety', 0.0044, 0.0330, (0, 0.0345, BORE - 0.0290), 'X', 18)
    finish(sb, M('metal_steel'), bev=0.0005, texel=0.02)
    parts.append(sb)
    # carrier (shell lifter) inside the loading port
    car = prism('rcv_carrier', rrect(0.0230, 0.0050, 0.0015, 2, 0, BORE - 0.0215), 0.0120, 0.0650)
    finish(car, M('metal_steel'), bev=0.0004, texel=0.04, long=1)
    parts.append(car)
    # action-bar lock
    abl = prism_x('rcv_ablock', [(-0.0020, BORE - 0.0240), (0.0080, BORE - 0.0245),
                                 (0.0080, BORE - 0.0330), (-0.0025, BORE - 0.0325)],
                  -0.0175, -0.0140)
    finish(abl, M('metal_steel'), bev=0.0005, texel=0.03, long=1)
    parts.append(abl)
    return fuse('receiver', parts)


def build_barrel():
    parts = []
    b = loft('bar_tube', [ring3(ellipse(r, r, 20, 0, BORE), y) for y, r in
                          ((0.1050, 0.0175), (0.1400, 0.0158), (0.2200, 0.0138),
                           (0.5600, 0.0128), (0.6280, 0.0128))])
    cut(b, cylinder('c_b', 0.0094, 0.70, (0, 0.3600, BORE), 'Y', 22))
    finish(b, M('metal_blued'), bev=0.0007, texel=0.07, long=1, seed=75)
    parts.append(b)
    # magazine tube + end cap
    mt = loft('bar_magtube', [ring3(ellipse(r, r, 18, 0, TUBE_Z), y) for y, r in
                              ((0.1000, 0.0128), (0.4200, 0.0128), (0.4300, 0.0142),
                               (0.4520, 0.0142), (0.4560, 0.0120))])
    cut(mt, grooves('c_mtg', 3, 0.0055, (0.040, 0.0016, 0.0016), loc=(0, 0.4410, TUBE_Z),
                    axis=(0, 1, 0)))
    finish(mt, M('metal_blued'), bev=0.0006, texel=0.05, long=1)
    parts.append(mt)
    # barrel ring joining tube and barrel
    ring = prism('bar_ring', rrect(0.0280, 0.0480, 0.0060, 3, 0, BORE - 0.0135), 0.4180, 0.4330)
    cut(ring, cylinder('c_r1', 0.0130, 0.040, (0, 0.4250, BORE), 'Y', 20))
    cut(ring, cylinder('c_r2', 0.0130, 0.040, (0, 0.4250, TUBE_Z), 'Y', 20))
    finish(ring, M('metal_blued'), bev=0.0006, texel=0.05, long=1)
    parts.append(ring)
    # bead front sight
    bs = prism('bar_fsbase', rrect(0.0080, 0.0075, 0.0015, 2, 0, BORE + 0.0150), 0.6050, 0.6180)
    finish(bs, M('metal_blued'), bev=0.0004, texel=0.03, long=1)
    parts.append(bs)
    bead = sphere('bar_bead', 0.0028, (0, 0.6115, BORE + 0.0200), segs=14)
    finish(bead, M('metal_brass'), bev=0.0, texel=0.02)
    parts.append(bead)
    rs = rear_notch('bar_rear', w=0.0140, t=0.0050, hgt=0.0050, notch_w=0.0038, notch_d=0.0030,
                    loc=(0, 0.1150, BORE + 0.0180), vee=True)
    finish(rs, M('metal_blued'), bev=0.0004, texel=0.03, long=1)
    parts.append(rs)
    return fuse('barrel', parts)


def build_pump():
    """Ribbed walnut fore-end + twin action bars.  The game slides this along Y."""
    parts = []
    body = loft('pump_body', [ring3(rrect(w, h, r, 4, 0, TUBE_Z + 0.0010), y)
                              for y, w, h, r in ((0.1450, 0.0400, 0.0400, 0.0120),
                                                 (0.1600, 0.0455, 0.0450, 0.0140),
                                                 (0.2450, 0.0450, 0.0445, 0.0140),
                                                 (0.2750, 0.0400, 0.0400, 0.0125),
                                                 (0.2830, 0.0340, 0.0345, 0.0110))])
    cut(body, cylinder('c_p1', 0.0140, 0.30, (0, 0.2100, TUBE_Z), 'Y', 22))
    cut(body, cylinder('c_p2', 0.0165, 0.30, (0, 0.2100, BORE), 'Y', 22))
    cut(body, rbox('c_p3', (0.060, 0.30, 0.030), (0, 0.2100, BORE + 0.0180)))
    # the classic corn-cob ribs
    cut(body, grooves('c_ribs', 9, 0.0132, (0.090, 0.0055, 0.0090),
                      loc=(0, 0.2120, TUBE_Z - 0.0235), axis=(0, 1, 0)))
    for sx in (-1, 1):
        cut(body, grooves('c_ribs%d' % sx, 9, 0.0132, (0.010, 0.0055, 0.060),
                          loc=(sx * 0.0232, 0.2120, TUBE_Z), axis=(0, 1, 0)))
    finish(body, M('wood_walnut'), bev=0.0009, texel=0.13, long=1, jitter=0.7, seed=77)
    parts.append(body)
    for sx in (-1, 1):
        bar = prism('pump_bar%d' % sx, rrect(0.0055, 0.0100, 0.0015, 2, sx * 0.0160,
                                             BORE - 0.0175), 0.0500, 0.1550)
        finish(bar, M('metal_blued'), bev=0.0005, texel=0.04, long=1)
        parts.append(bar)
    return fuse('pump', parts)


def build(arms=True):
    reset_scene()
    prebake()
    guns = [build_stock(), build_receiver(), build_barrel(), build_pump()]
    arm_r = arm_l = None
    if arms:
        arm_r = hand_on_grip((0.0248, -0.0560, BORE - 0.0330), rake=-0.26,
                             elbow=(0.100, -0.030, -0.300), curl=(0.72, 0.87, 0.91, 0.93))
        # lower and further forward on the pump: at the shipped adsDist 0.24 the support
        # hand was the main obstruction in the ADS sight picture
        arm_l = hand_on_handguard((-0.0300, 0.2200, TUBE_Z - 0.0045), lean=0.14,
                                  elbow=(-0.140, -0.020, -0.290))
    muzzle = (0.0, Y_MUZZLE, BORE)
    eject = (0.0215, 0.0560, BORE + 0.0060)
    aim = (0.0, 0.1150, SIGHT_Z)
    return dict(guns=guns, arm_r=arm_r, arm_l=arm_l, muzzle=muzzle, eject=eject, aim=aim)


if __name__ == '__main__':
    d = build()
    deliver(WID, GRIP_POS, d['guns'], d['muzzle'], d['eject'], d['aim'], d['arm_r'], d['arm_l'],
            movable=('pump',), detail_target=(0, 0.180, 0.005), detail_dist=0.95, lens=52,
            grip_view=(0, 0.00, -0.03), ads_back=0.24)
    print('DONE')
