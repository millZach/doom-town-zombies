"""Olympia - side-by-side double-barrel 12-gauge, break action, walnut stock.

Gun space: origin at the web of the right hand on the small of the stock, bores along +Y.
Sawn-off-ish coach gun: 760 mm overall, 470 mm barrels.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_weapons import *                                   # noqa

WID = 'olympia'
BORE = 0.0330                  # centre height between the two bores
DX = 0.0198                    # half the spacing between the barrels
BR = 0.0182                    # barrel outer radius at the breech
Y_BUTT = -0.2650
Y_MUZZLE = 0.4950
SIGHT_Z = BORE + 0.0215
GRIP_POS = (0.150, 0.288, -0.108)
HINGE = (0.0, 0.0300, BORE - 0.0200)   # break-open hinge pin: `barrels` pivots here


def build_stock():
    parts = []
    out = [
        (Y_BUTT, BORE - 0.0920), (Y_BUTT - 0.0080, BORE - 0.0800),
        (Y_BUTT - 0.0070, BORE - 0.0140), (Y_BUTT + 0.0150, BORE - 0.0105),
        (-0.1920, BORE - 0.0095), (-0.1300, BORE - 0.0045),   # comb, 30 mm under the sight line
        (-0.0900, BORE + 0.0090), (-0.0700, BORE - 0.0060),
        (-0.0400, BORE - 0.0135), (-0.0080, BORE - 0.0165),
        (0.0180, BORE - 0.0180), (0.0180, BORE - 0.0350),
        (-0.0140, BORE - 0.0390), (-0.0420, BORE - 0.0430),
        (-0.0700, BORE - 0.0560), (-0.1050, BORE - 0.0800),
        (-0.1600, BORE - 0.0950), (-0.2150, BORE - 0.0940),
        (Y_BUTT + 0.0060, BORE - 0.0880),
    ]
    st = prism_x('stk_body', out, -0.0230, 0.0230)
    env = loft('c_env', [ring3(rrect(w, 0.300, r, 5, 0, BORE - 0.030), y)
                         for y, w, r in ((Y_BUTT - 0.020, 0.0455, 0.0065),
                                         (-0.2200, 0.0450, 0.0080),
                                         (-0.1500, 0.0440, 0.0110),
                                         (-0.0950, 0.0400, 0.0150),
                                         (-0.0400, 0.0400, 0.0140),
                                         (0.0200, 0.0450, 0.0090))])
    boolean(st, env, 'INTERSECT')
    # breech face inlet for the barrels
    cut(st, rbox('c_br', (0.070, 0.060, 0.045), (0, 0.0300, BORE)))
    finish(st, M('wood_walnut'), bev=0.0020, segs=3, texel=0.16, long=1, jitter=0.25, seed=51)
    parts.append(st)

    # chequered panel on the wrist
    for sx in (-1, 1):
        ck = checkering('stk_ck%d' % sx, 0.060, 0.022, nu=17, nv=7, depth=0.0008, thick=0.0010)
        place(ck, (sx * 0.0186, -0.0480, BORE - 0.0180), (0, 1, 0.16), (sx, 0, 0))
        finish(ck, M('wood_walnut'), bev=0.0, texel=0.16, long=1, seed=51)
        parts.append(ck)

    bp = prism_x('stk_plate', [(Y_BUTT - 0.0090, BORE - 0.0935), (Y_BUTT + 0.0015, BORE - 0.0950),
                               (Y_BUTT + 0.0080, BORE - 0.0090), (Y_BUTT - 0.0085, BORE - 0.0130)],
                 -0.0200, 0.0200)
    finish(bp, M('polymer_rubber'), bev=0.0012, texel=0.05, long=2)
    parts.append(bp)
    return fuse('stock', parts)


def build_barrels():
    parts = []
    for sx in (-1, 1):
        b = loft('bar_tube%d' % sx, [
            ring3(ellipse(BR, BR, 20, sx * DX, BORE), 0.0180),
            ring3(ellipse(BR, BR, 20, sx * DX, BORE), 0.0680),
            ring3(ellipse(0.0152, 0.0152, 20, sx * DX, BORE), 0.2200),
            ring3(ellipse(0.0138, 0.0138, 20, sx * DX, BORE), 0.4850),
            ring3(ellipse(0.0138, 0.0138, 20, sx * DX, BORE), 0.4930)])
        cut(b, cylinder('c_b%d' % sx, 0.0093, 0.60, (sx * DX, 0.2500, BORE), 'Y', 22))
        finish(b, M('metal_blued'), bev=0.0007, texel=0.07, long=1, seed=53 + sx)
        parts.append(b)
    # top and bottom ribs joining the tubes
    for z, h in ((BORE + 0.0168, 0.0050), (BORE - 0.0170, 0.0045)):
        rib = prism('bar_rib%d' % int(z * 1e4),
                    rrect(0.0300, h, 0.0012, 2, 0, z), 0.0300, 0.4920)
        finish(rib, M('metal_blued'), bev=0.0005, texel=0.06, long=1)
        parts.append(rib)
    # breech block
    brz = prism('bar_breech', rrect(0.0640, 0.0355, 0.0060, 3, 0, BORE - 0.0038), 0.0140, 0.0620)
    for sx in (-1, 1):
        cut(brz, cylinder('c_ch%d' % sx, 0.0098, 0.030, (sx * DX, 0.0200, BORE), 'Y', 20))
    finish(brz, M('metal_blued'), bev=0.0010, texel=0.06, long=1, seed=57)
    parts.append(brz)
    # bead front sight
    bead = sphere('bar_bead', 0.0026, (0, 0.4860, BORE + 0.0195), segs=14)
    finish(bead, M('metal_brass'), bev=0.0, texel=0.02)
    parts.append(bead)
    # rear sight groove marker on the rib
    rs = rear_notch('bar_rear', w=0.0150, t=0.0050, hgt=0.0044, notch_w=0.0038, notch_d=0.0026,
                    loc=(0, 0.0700, BORE + 0.0193), vee=True)
    finish(rs, M('metal_blued'), bev=0.0004, texel=0.03, long=1)
    parts.append(rs)

    # walnut fore-end under the barrels
    fe = loft('bar_forend', [ring3(rrect(w, h, r, 4, 0, BORE - 0.0150), y)
                             for y, w, h, r in ((0.0900, 0.0440, 0.0250, 0.0090),
                                                (0.1100, 0.0500, 0.0300, 0.0110),
                                                (0.1900, 0.0480, 0.0285, 0.0110),
                                                (0.2250, 0.0420, 0.0240, 0.0100),
                                                (0.2350, 0.0360, 0.0200, 0.0090))])
    for sx in (-1, 1):
        cut(fe, cylinder('c_fe%d' % sx, BR + 0.0008, 0.40, (sx * DX, 0.1600, BORE), 'Y', 22))
    cut(fe, rbox('c_fet', (0.080, 0.40, 0.040), (0, 0.1600, BORE + 0.0190)))
    finish(fe, M('wood_walnut'), bev=0.0012, texel=0.14, long=1, jitter=0.6, seed=59)
    parts.append(fe)
    for sx in (-1, 1):
        ck = checkering('bar_feck%d' % sx, 0.070, 0.020, nu=18, nv=6, depth=0.0008, thick=0.0010)
        place(ck, (sx * 0.0262, 0.1600, BORE - 0.0170), (0, 1, 0), (sx, 0, -0.25))
        finish(ck, M('wood_walnut'), bev=0.0, texel=0.14, long=1, seed=59)
        parts.append(ck)
    # hinge lug that wraps the pin, so the joint reads as a hinge when it is broken open
    lug = prism('bar_lug', rrect(0.0260, 0.0230, 0.0055, 2, 0, HINGE[2]),
                0.0180, 0.0330)
    cut(lug, cylinder('c_pin', 0.0064, 0.080, HINGE, 'X', 18))
    finish(lug, M('metal_blued'), bev=0.0008, texel=0.05, long=1)
    parts.append(lug)
    ob = fuse('barrels', parts)
    # the glTF node translation IS the object origin, so putting it on the pin is what lets the
    # game rotate `barrels` about local X to break the gun open (weapons_audio.md #5).
    return set_origin(ob, HINGE)


def build_action():
    """Receiver, top lever, trigger guard, hammers."""
    parts = []
    # top at BORE+0.0125, 9 mm clear under the line of sight (was BORE+0.0210)
    rec = prism('act_body', rrect(0.0620, 0.0415, 0.0070, 3, 0, BORE - 0.0083), -0.0080, 0.0320)
    cut(rec, rbox('c_top', (0.0200, 0.0300, 0.0140), (0, 0.0060, BORE + 0.0150)))
    finish(rec, M('metal_steel'), bev=0.0010, texel=0.05, long=1, seed=61)
    parts.append(rec)
    lever = prism('act_lever', [(-0.0044, BORE + 0.0080), (0.0044, BORE + 0.0080),
                                (0.0070, BORE + 0.0115), (0.0035, BORE + 0.0140),
                                (-0.0035, BORE + 0.0140), (-0.0070, BORE + 0.0115)],
                  -0.0180, 0.0060)
    finish(lever, M('metal_steel'), bev=0.0006, texel=0.03, long=1)
    parts.append(lever)
    guard = prism_x('act_guard', arc_pts(-0.0230, BORE - 0.0530, 0.0210, 30, -175, 9)
                    + [(-0.0470, BORE - 0.0420), (-0.0400, BORE - 0.0330),
                       (0.0060, BORE - 0.0320), (0.0070, BORE - 0.0420)], -0.0070, 0.0070)
    cut(guard, prism_x('c_g', arc_pts(-0.0230, BORE - 0.0530, 0.0145, 40, -185, 9)
                       + [(-0.0410, BORE - 0.0400), (-0.0020, BORE - 0.0390)], -0.03, 0.03))
    finish(guard, M('metal_steel'), bev=0.0007, texel=0.04, long=1)
    parts.append(guard)
    for i, y in enumerate((-0.0180, -0.0300)):
        t = prism_x('act_trg%d' % i, [(y + 0.0040, BORE - 0.0340), (y - 0.0035, BORE - 0.0345),
                                      (y - 0.0050, BORE - 0.0510), (y + 0.0025, BORE - 0.0500)],
                    -0.0042, 0.0042)
        finish(t, M('metal_steel'), bev=0.0005, texel=0.03, long=1)
        parts.append(t)
    # exposed hammer spurs
    for sx in (-1, 1):
        h = prism_x('act_ham%d' % sx, [(-0.0090, BORE - 0.0005), (0.0010, BORE + 0.0005),
                                       (0.0020, BORE + 0.0125), (-0.0060, BORE + 0.0145),
                                       (-0.0130, BORE + 0.0095)], sx * 0.0100, sx * 0.0160)
        finish(h, M('metal_steel'), bev=0.0006, texel=0.03, long=1)
        parts.append(h)
    # hinge-pin boss on the action, so the barrels have something to pivot against
    pin = cylinder('act_pin_hinge', 0.0058, 0.0650, HINGE, 'X', 18)
    finish(pin, M('metal_steel'), bev=0.0006, texel=0.04, long=1)
    parts.append(pin)
    # pins
    for y in (0.0080, -0.0040):
        parts.append(finish(screw('act_pin%d' % int(y * 1e4), 0.0032,
                                  (0.0312, y, BORE - 0.0060), 'X', 'slot', 0.0010, 0.0005),
                            M('metal_steel'), bev=0.0002, texel=0.02))
    return fuse('action', parts)


def build(arms=True):
    reset_scene()
    prebake()
    guns = [build_stock(), build_barrels(), build_action()]
    arm_r = arm_l = None
    if arms:
        arm_r = hand_on_grip((0.0245, -0.0530, BORE - 0.0300), rake=-0.26,
                             elbow=(0.100, -0.030, -0.300), curl=(0.72, 0.87, 0.91, 0.93))
        # lower and further forward on the fore-end: at the shipped adsDist 0.19 the support
        # hand was the main obstruction in the ADS sight picture
        arm_l = hand_on_handguard((-0.0300, 0.1800, BORE - 0.0215), lean=0.14,
                                  elbow=(-0.140, -0.020, -0.290))
    muzzle = (0.0, Y_MUZZLE, BORE)
    eject = (0.0, 0.0300, BORE + 0.0060)
    aim = (0.0, 0.0700, SIGHT_Z)
    return dict(guns=guns, arm_r=arm_r, arm_l=arm_l, muzzle=muzzle, eject=eject, aim=aim)


if __name__ == '__main__':
    d = build()
    deliver(WID, GRIP_POS, d['guns'], d['muzzle'], d['eject'], d['aim'], d['arm_r'], d['arm_l'],
            movable=('barrels', 'action'), detail_target=(0, 0.140, 0.005), detail_dist=0.80,
            lens=52, grip_view=(0, 0.00, -0.03), ads_back=0.19)
    print('DONE')
