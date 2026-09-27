"""MP5 9 mm SMG - first-person viewmodel.

Gun space: origin at the web of the right hand on the pistol grip, bore along +Y at z = BORE.
Real MP5A3: 490 mm with the stock retracted, 225 mm barrel, 30-round curved magazine.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_weapons import *                                   # noqa

WID = 'mp5'
BORE = 0.0400
RCV_R = 0.0158                 # receiver tube radius
Y_MUZZLE = 0.2980
SIGHT_Z = BORE + 0.0345
GRIP_POS = (0.145, 0.255, -0.098)
TX = 0.060


def build_receiver():
    parts = []
    # --- main tube: round top, flat-ish sides, squared bottom -----------------
    prof = (arc_pts(0, BORE, RCV_R, -30, 210, 16)
            + [(-0.0152, BORE - 0.0125), (-0.0152, BORE - 0.0190),
               (0.0152, BORE - 0.0190), (0.0152, BORE - 0.0125)])
    body = prism('rcv_body', prof, -0.0960, 0.1560)
    # magazine well housing
    mw = prism('rcv_magwell', rrect(0.0300, 0.0340, 0.0035, 3, 0, BORE - 0.0250), 0.0490, 0.0930)
    boolean(body, mw, 'UNION')
    # ejection port (right side)
    cut(body, rbox('c_port', (0.020, 0.0420, 0.0160), (0.0165, 0.0300, BORE + 0.0035)))
    # trigger-group housing (polymer lower) is a separate object below
    cut(body, rbox('c_low', (0.040, 0.0760, 0.0140), (0, 0.0060, BORE - 0.0250)))
    # cocking-handle tube along the top left of the barrel
    cut(body, cylinder('c_ch', 0.0092, 0.070, (-0.0118, 0.1400, BORE + 0.0140), 'Y', 20))
    # receiver end cap / stock mount
    cut(body, rbox('c_back', (0.040, 0.020, 0.040), (0, -0.0985, BORE)))
    finish(body, M('metal_parker'), bev=0.0008, texel=TX, long=1, jitter=0.2, seed=2)
    parts.append(body)

    # --- barrel + cocking-handle tube ----------------------------------------
    bar = cylinder('rcv_barrel', 0.0112, 0.1720, (0, 0.2120, BORE), 'Y', 24)
    cut(bar, cylinder('c_bore', 0.0048, 0.22, (0, 0.2120, BORE), 'Y', 20))
    cut(bar, cylinder('c_crown', 0.0072, 0.0040, (0, 0.2970, BORE), 'Y', 20, r2=0.0050))
    finish(bar, M('metal_blued'), bev=0.0005, texel=0.05, long=1)
    parts.append(bar)

    cht = tube('rcv_chtube', 0.0108, 0.0086, 0.1420, (-0.0118, 0.2190, BORE + 0.0140), 'Y', 20)
    # slot along the tube so the cocking handle has somewhere to travel
    cut(cht, rbox('c_chslot', (0.0062, 0.0800, 0.0062), (-0.0203, 0.2440, BORE + 0.0206)))
    finish(cht, M('metal_parker'), bev=0.0005, texel=0.05, long=1)
    parts.append(cht)

    # --- front sight: hooded ring with a post --------------------------------
    hood = tube('rcv_fhood', 0.0128, 0.0102, 0.0220, (0, 0.2640, BORE + 0.0230), 'Y', 22)
    for a in (0, 90, 180, 270):
        cut(hood, rbox('c_h%d' % a, (0.0036, 0.030, 0.030), (0, 0.2640, BORE + 0.0230),
                       rot=(0, D2R(a + 45), 0)))
    base = prism('rcv_fbase', [(-0.0092, BORE + 0.0060), (0.0092, BORE + 0.0060),
                               (0.0060, BORE + 0.0190), (-0.0060, BORE + 0.0190)], 0.2540, 0.2740)
    post = sight_post('rcv_fpost', 0.0026, 0.0030, 0.0072,
                      loc=(0, 0.2640, SIGHT_Z - 0.0072))
    for o in (hood, base, post):
        finish(o, M('metal_parker'), bev=0.0005, texel=0.04, long=1)
    parts += [hood, base, post]

    # --- rear rotary drum sight ----------------------------------------------
    drum = cylinder('rcv_drum', 0.0135, 0.0170, (0, -0.0560, SIGHT_Z), 'Y', 22)
    for i in range(12):
        a = TAU * i / 12
        cut(drum, rbox('c_d%d' % i, (0.0022, 0.0200, 0.0060),
                       (math.cos(a) * 0.0120, -0.0560, SIGHT_Z + math.sin(a) * 0.0120),
                       rot=(0, a, 0)))
    # the rear drum's aperture: a real 5 mm peep, otherwise ADS is an opaque disc
    cut(drum, cylinder('c_ap', 0.0026, 0.030, (0, -0.0560, SIGHT_Z), 'Y', 16))
    tower = prism('rcv_rtower', [(-0.0078, BORE + 0.0080), (0.0078, BORE + 0.0080),
                                 (0.0078, BORE + 0.0370), (-0.0078, BORE + 0.0370)],
                  -0.0700, -0.0420)
    cut(tower, cylinder('c_t', 0.0142, 0.020, (0, -0.0560, SIGHT_Z), 'Y', 22))
    cut(tower, cylinder('c_t2', 0.0030, 0.040, (0, -0.0560, SIGHT_Z), 'Y', 14))
    for o in (drum, tower):
        finish(o, M('metal_parker'), bev=0.0005, texel=0.04, long=1)
    parts += [drum, tower]

    # --- handguard (slim polymer tube) ---------------------------------------
    HC = BORE + 0.0045
    hg = loft('rcv_handguard', [
        ring3(ellipse(0.0184, 0.0176, 22, -0.0040, HC), 0.1160),
        ring3(ellipse(0.0206, 0.0194, 22, -0.0040, HC), 0.1310),
        ring3(ellipse(0.0208, 0.0196, 22, -0.0040, HC), 0.2000),
        ring3(ellipse(0.0196, 0.0186, 22, -0.0040, HC), 0.2280),
        ring3(ellipse(0.0168, 0.0162, 22, -0.0040, HC), 0.2360)])
    inner = loft('c_hg', [ring3(ellipse(0.0152, 0.0146, 22, -0.0040, HC), 0.1000),
                          ring3(ellipse(0.0152, 0.0146, 22, -0.0040, HC), 0.2600)])
    cut(hg, inner)
    # finger grooves along the underside
    cut(hg, grooves('c_hgv', 5, 0.0185, (0.070, 0.0065, 0.0044),
                    loc=(0, 0.1740, BORE - 0.0205), axis=(0, 1, 0)))
    finish(hg, M('polymer_black'), bev=0.0010, segs=2, texel=0.055, long=1, seed=6)
    parts.append(hg)

    # --- sling loop + handguard pin ------------------------------------------
    sl = tube('rcv_sling', 0.0072, 0.0050, 0.0030, (0, 0.2480, BORE - 0.0190), 'Z', 16)
    finish(sl, M('metal_parker'), bev=0.0004, texel=0.03)
    parts.append(sl)
    return fuse('receiver', parts)


def build_lower():
    """Polymer trigger group: grip, trigger guard, selector, magazine catch."""
    parts = []
    out = [(-0.0245, BORE - 0.0180), (0.0620, BORE - 0.0180), (0.0620, BORE - 0.0320),
           (0.0480, BORE - 0.0360), (0.0430, BORE - 0.0430)]
    out += arc_pts(0.0260, BORE - 0.0480, 0.0185, 25, -120, 7)
    out += [(0.0090, BORE - 0.0640), (0.0010, BORE - 0.0560), (-0.0030, BORE - 0.0400),
            (-0.0180, BORE - 0.0760), (-0.0330, BORE - 0.1140), (-0.0430, BORE - 0.1400),
            (-0.0560, BORE - 0.1420), (-0.0700, BORE - 0.1330), (-0.0620, BORE - 0.1050),
            (-0.0490, BORE - 0.0660), (-0.0430, BORE - 0.0300)]
    low = prism_x('low_body', out, -0.0152, 0.0152)
    hole = arc_pts(0.0265, BORE - 0.0470, 0.0128, 40, -150, 9) + [
        (0.0060, BORE - 0.0540), (0.0035, BORE - 0.0430), (0.0060, BORE - 0.0330),
        (0.0230, BORE - 0.0318), (0.0350, BORE - 0.0330)]
    cut(low, prism_x('c_tg', hole, -0.03, 0.03))
    # hollow the grip sides so it reads as a moulded shell
    for x0, x1 in ((-0.0156, -0.0116), (0.0116, 0.0156)):
        cut(low, prism_x('c_gs', [(-0.0245, BORE - 0.0520), (-0.0400, BORE - 0.1080),
                                  (-0.0620, BORE - 0.1180), (-0.0500, BORE - 0.0560)], x0, x1))
    finish(low, M('polymer_black'), bev=0.0010, segs=2, texel=0.055, long=1, seed=8)
    parts.append(low)

    trg = prism_x('low_trigger', [(0.0210, BORE - 0.0350), (0.0290, BORE - 0.0355),
                                  (0.0300, BORE - 0.0530), (0.0225, BORE - 0.0520)],
                  -0.0055, 0.0055)
    finish(trg, M('metal_blued'), bev=0.0005, texel=0.04, long=1)
    parts.append(trg)

    # selector lever (left) + its mirror stub
    for x0, x1, nm in ((-0.0210, -0.0150, 'L'), (0.0150, 0.0200, 'R')):
        sel = prism_x('low_sel' + nm, [(0.0090, BORE - 0.0230), (0.0180, BORE - 0.0250),
                                       (0.0200, BORE - 0.0320), (0.0080, BORE - 0.0330),
                                       (0.0045, BORE - 0.0285)], x0, x1)
        finish(sel, M('polymer_black'), bev=0.0006, texel=0.04, long=1)
        parts.append(sel)
    pin = cylinder('low_selpin', 0.0068, 0.0420, (0, 0.0128, BORE - 0.0282), 'X', 18)
    finish(pin, M('metal_blued'), bev=0.0005, texel=0.03)
    parts.append(pin)

    # grip texture panels
    for sx in (-1, 1):
        ck = checkering('low_ck%d' % sx, 0.058, 0.022, nu=16, nv=7, depth=0.0007, thick=0.0009)
        place(ck, (sx * 0.0152, -0.0420, BORE - 0.0880), (0, -0.34, -0.94), (sx, 0, 0))
        finish(ck, M('polymer_black'), bev=0.0, texel=0.055)
        parts.append(ck)
    # push pins
    for yy in (-0.0170, 0.0540):
        parts.append(finish(screw('low_pin%d' % int(yy * 1e4), 0.0042,
                                  (-0.0156, yy, BORE - 0.0250), 'X', 'pin', 0.0012),
                            M('metal_blued'), bev=0.0003, texel=0.03))
    return fuse('lower', parts)


def build_stock():
    """Retracted sliding stock: two rods and a butt plate."""
    parts = []
    for sx in (-1, 1):
        r = tube('stk_rod%d' % sx, 0.0072, 0.0052, 0.0900, (sx * 0.0215, -0.1360, BORE - 0.0040),
                 'Y', 16)
        finish(r, M('metal_parker'), bev=0.0005, texel=0.05, long=1)
        parts.append(r)
    cap = prism('stk_cap', rrect(0.0620, 0.0430, 0.0060, 3, 0, BORE - 0.0040), -0.1010, -0.0930)
    plate = prism('stk_plate', rrect(0.0500, 0.0480, 0.0080, 3, 0, BORE - 0.0060), -0.1860, -0.1790)
    strut = prism('stk_strut', rrect(0.0560, 0.0180, 0.0040, 2, 0, BORE - 0.0260), -0.1840, -0.1080)
    for o in (cap, plate, strut):
        finish(o, M('metal_parker'), bev=0.0008, texel=TX, long=1)
    parts += [cap, plate, strut]
    pad = prism('stk_pad', rrect(0.0470, 0.0450, 0.0090, 3, 0, BORE - 0.0060), -0.1930, -0.1855)
    finish(pad, M('polymer_rubber'), bev=0.0010, texel=0.05)
    parts.append(pad)
    return fuse('stock', parts)


def build_mag():
    """Curved 30-round 9 mm magazine."""
    rings = []
    n = 22
    for i in range(n + 1):
        t = i / n
        z = (BORE - 0.0280) - 0.2050 * t
        y = 0.0710 + 0.0230 * (t ** 1.9)              # curves forward as it goes down
        w = 0.0210 - 0.0012 * t
        d = 0.0300 - 0.0035 * t
        rings.append(ring3(rrect(w, d, 0.0030, 2), y, 1, 1, 0, z))
    # rings are in (x,z) at a given y -> need them as sections along the magazine, so rebuild
    secs = []
    for i in range(n + 1):
        t = i / n
        z = (BORE - 0.0040) - 0.1720 * t
        y = 0.0700 + 0.0430 * (t ** 1.75)
        w = 0.0215 - 0.0016 * t
        d = 0.0300 - 0.0035 * t
        secs.append([(p[0], y + p[1], z) for p in rrect(w, d, 0.0034, 2)])
    mag = loft('mag_body', secs)
    finish(mag, M('metal_parker'), bev=0.0008, texel=0.05, long=2, seed=12)
    base = prism_x('mag_base', [(0.1010, BORE - 0.1620), (0.1290, BORE - 0.1620),
                                (0.1300, BORE - 0.1730), (0.1000, BORE - 0.1730)],
                   -0.0124, 0.0124)
    finish(base, M('polymer_black'), bev=0.0008, texel=0.05, long=1)
    return fuse('mag', [mag, base])


def build_bolt():
    """MP5 cocking handle: a 52-degree stub with a knurled knob riding the tube over the barrel.

    The game slides it rearward along Blender -Y (three.js local +Z), `boltTravel` 0.05 m."""
    parts = []
    ch = cylinder('bolt_stub', 0.0052, 0.0300, (-0.0210, 0.2740, BORE + 0.0250), 'Z',
                  16, rot=(D2R(-40), 0, 0))
    ch.rotation_euler = (0, D2R(-52), 0)
    apply_transforms(ch, rot=True, scale=True)
    ch.location = (-0.0118, 0.2740, BORE + 0.0140)
    finish(ch, M('metal_parker'), bev=0.0006, texel=0.04, long=1)
    parts.append(ch)
    knob = knurl_band('bolt_knob', 0.0072, 0.0130, (-0.0245, 0.2740, BORE + 0.0280), 'Z',
                      n_around=24, n_up=5, depth=0.0004, rot=(0, D2R(-52), 0))
    finish(knob, M('metal_parker'), bev=0.0, texel=0.04, long=1)
    parts.append(knob)
    ob = fuse('bolt', parts)
    return set_origin(ob, (-0.0170, 0.2740, BORE + 0.0210))


def build(arms=True):
    reset_scene()
    prebake()
    guns = [build_receiver(), build_lower(), build_stock(), build_mag(), build_bolt()]
    arm_r = arm_l = None
    if arms:
        arm_r = hand_on_grip((0.0190, -0.0250, BORE - 0.0560), rake=-0.40,
                             elbow=(0.100, -0.030, -0.300))
        arm_l = hand_on_handguard((-0.0255, 0.1720, BORE - 0.0040), lean=0.20,
                                  elbow=(-0.125, -0.020, -0.290))
    muzzle = (0.0, Y_MUZZLE, BORE)
    eject = (0.0175, 0.0300, BORE + 0.0040)
    aim = (0.0, -0.0560, SIGHT_Z)
    return dict(guns=guns, arm_r=arm_r, arm_l=arm_l, muzzle=muzzle, eject=eject, aim=aim)


if __name__ == '__main__':
    d = build()
    deliver(WID, GRIP_POS, d['guns'], d['muzzle'], d['eject'], d['aim'], d['arm_r'], d['arm_l'],
            movable=('mag', 'bolt'), detail_target=(0, 0.100, 0.020), detail_dist=0.62, lens=50,
            grip_view=(0, -0.01, -0.05), ads_back=0.32)
    print('DONE')
