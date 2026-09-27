"""Python .357 Magnum revolver - first-person viewmodel.

Gun space: origin at the web of the right hand on the backstrap, bore along +Y at BORE.
6 inch vent-rib barrel with a full underlug, walnut target grips, 6-shot cylinder.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_weapons import *                                   # noqa

WID = 'python'
BORE = 0.0330
CYL_Y = 0.0480                  # cylinder centre
CYL_R = 0.0200
Y_MUZZLE = 0.2560
SIGHT_Z = BORE + 0.0220   # == front blade tip
GRIP_POS = (0.152, 0.302, -0.066)
# Crane (yoke) pivot: parallel to the bore, COAXIAL with the ejector rod and 18.5 mm below
# the cylinder axis.  The code's +66 deg rotation about local Z then swings the cylinder
# ~17 mm out to the LEFT (and 11 mm down), while the ejector rod sits exactly on the rotation
# axis and does not move at all - so it can never be driven through the barrel underlug, whose
# bore only has 2.6 mm of radial clearance.  (An offset pivot gives a flatter swing but lifts
# the rod 11 mm, straight through the lug wall and then the barrel.)
CRANE = (0.0, 0.0820, BORE - 0.0185)


def build_frame():
    parts = []
    out = [
        (-0.0290, BORE + 0.0140), (0.0100, BORE + 0.0150), (0.0100, BORE + 0.0190),
        (0.0850, BORE + 0.0190), (0.0850, BORE + 0.0060),
        (0.0790, BORE - 0.0110), (0.0180, BORE - 0.0130),
        (0.0180, BORE - 0.0290), (0.0060, BORE - 0.0300),
        (0.0040, BORE - 0.0170), (-0.0100, BORE - 0.0180),
        (-0.0150, BORE - 0.0330), (-0.0280, BORE - 0.0700),
        (-0.0360, BORE - 0.0940), (-0.0480, BORE - 0.0980),
        (-0.0600, BORE - 0.0880), (-0.0520, BORE - 0.0560),
        (-0.0400, BORE - 0.0170), (-0.0330, BORE + 0.0060),
    ]
    fr = prism_x('frm_body', out, -0.0098, 0.0098)
    # cylinder window
    cut(fr, cylinder('c_cyl', CYL_R + 0.0012, 0.0460, (0, CYL_Y, BORE), 'Y', 26))
    # top strap sight channel
    cut(fr, rbox('c_ch', (0.0048, 0.0600, 0.0060), (0, -0.0060, BORE + 0.0185)))
    finish(fr, M('metal_blued'), bev=0.0009, segs=2, texel=0.055, long=1, jitter=0.2, seed=91)
    parts.append(fr)

    # recoil shield behind the cylinder (the cylinder itself stays exposed)
    for sx in (-1, 1):
        # the LEFT shield stops at the cylinder's rear face: anything further forward gets
        # sheared by the cylinder as the crane swings it out
        y1 = 0.0250 if sx < 0 else 0.0300
        sp = prism_x('frm_shield%d' % sx, [(0.0170, BORE + 0.0150), (y1, BORE + 0.0150),
                                           (y1, BORE - 0.0120), (0.0170, BORE - 0.0120)],
                     sx * 0.0098, sx * 0.0168)
        cut(sp, cylinder('c_c%d' % sx, CYL_R + 0.0015, 0.0460, (0, CYL_Y, BORE), 'Y', 26))
        finish(sp, M('metal_blued'), bev=0.0007, texel=0.05, long=1)
        parts.append(sp)
    # top strap over the cylinder
    ts = prism('frm_topstrap', rrect(0.0196, 0.0090, 0.0025, 2, 0, BORE + 0.0125), 0.0170, 0.0810)
    finish(ts, M('metal_blued'), bev=0.0007, texel=0.05, long=1)
    parts.append(ts)

    # trigger guard
    guard = prism_x('frm_guard', arc_pts(-0.0060, BORE - 0.0350, 0.0195, 30, -175, 9)
                    + [(-0.0250, BORE - 0.0260), (-0.0200, BORE - 0.0170),
                       (0.0140, BORE - 0.0160), (0.0150, BORE - 0.0260)], -0.0075, 0.0075)
    cut(guard, prism_x('c_g', arc_pts(-0.0060, BORE - 0.0350, 0.0130, 40, -190, 9)
                       + [(-0.0190, BORE - 0.0245), (0.0090, BORE - 0.0240)], -0.03, 0.03))
    finish(guard, M('metal_blued'), bev=0.0007, texel=0.04, long=1)
    parts.append(guard)
    trg = prism_x('frm_trigger', [(-0.0110, BORE - 0.0250), (-0.0020, BORE - 0.0255),
                                  (0.0000, BORE - 0.0430), (-0.0090, BORE - 0.0420)],
                  -0.0050, 0.0050)
    cut(trg, grooves('c_tr', 6, 0.0026, (0.02, 0.0009, 0.0009), loc=(0, -0.0050, BORE - 0.0340),
                     axis=(0, 0, 1)))
    finish(trg, M('metal_steel'), bev=0.0004, texel=0.03, long=1)
    parts.append(trg)

    # hammer with a checkered spur
    ham = prism_x('frm_hammer', [(-0.0310, BORE + 0.0130), (-0.0190, BORE + 0.0140),
                                 (-0.0170, BORE + 0.0240), (-0.0290, BORE + 0.0300),
                                 (-0.0420, BORE + 0.0290), (-0.0440, BORE + 0.0200)],
                  -0.0042, 0.0042)
    finish(ham, M('metal_blued'), bev=0.0006, texel=0.03, long=1)
    parts.append(ham)
    ck = checkering('frm_hamck', 0.0180, 0.0060, nu=7, nv=3, depth=0.0005, thick=0.0008)
    place(ck, (0, -0.0310, BORE + 0.0298), (0, 1, 0.12), (0, -0.12, 1))
    finish(ck, M('metal_blued'), bev=0.0, texel=0.03)
    parts.append(ck)

    # cylinder release latch (left side)
    lat = prism_x('frm_latch', [(0.0150, BORE + 0.0090), (0.0330, BORE + 0.0085),
                                (0.0330, BORE - 0.0010), (0.0150, BORE - 0.0005)],
                  -0.0190, -0.0165)
    finish(lat, M('metal_blued'), bev=0.0005, texel=0.03, long=1)
    parts.append(lat)

    # rear adjustable sight
    rs = rear_notch('frm_rear', w=0.0150, t=0.0080, hgt=0.0060, notch_w=0.0034, notch_d=0.0034,
                    loc=(0, -0.0140, BORE + 0.0194))
    finish(rs, M('metal_blued'), bev=0.0004, texel=0.03, long=1)
    parts.append(rs)
    for yy in (-0.0200, -0.0080):
        parts.append(finish(screw('frm_rsc%d' % int(yy * 1e4), 0.0024,
                                  (0, yy, BORE + 0.0230), 'Z', 'slot', 0.0008, 0.0005),
                            M('metal_steel'), bev=0.0002, texel=0.02))

    # walnut target grips
    panel = [(-0.0090, BORE - 0.0190), (-0.0170, BORE - 0.0380), (-0.0310, BORE - 0.0740),
             (-0.0420, BORE - 0.1000), (-0.0570, BORE - 0.0960), (-0.0500, BORE - 0.0600),
             (-0.0370, BORE - 0.0180), (-0.0250, BORE - 0.0100)]
    for sx in (-1, 1):
        x0, x1 = (0.0040, 0.0180) if sx > 0 else (-0.0180, -0.0040)
        gp = prism_x('grip_panel_%s' % ('R' if sx > 0 else 'L'), panel, x0, x1)
        env = loft('c_ge%d' % sx, [ring3(rrect(w, 0.200, r, 4, 0, BORE - 0.060), y)
                                   for y, w, r in ((-0.105, 0.0300, 0.0140),
                                                   (-0.070, 0.0355, 0.0165),
                                                   (-0.030, 0.0365, 0.0170),
                                                   (0.005, 0.0320, 0.0140))])
        boolean(gp, env, 'INTERSECT')
        finish(gp, M('wood_walnut'), bev=0.0010, texel=0.075, long=2, jitter=0.4, seed=93 + sx)
        parts.append(gp)
        ck = checkering('grip_ck%d' % sx, 0.048, 0.022, nu=14, nv=7, depth=0.0008, thick=0.0010)
        place(ck, (sx * 0.0168, -0.0330, BORE - 0.0590), (0, -0.36, -0.93), (sx, 0, 0))
        finish(ck, M('wood_walnut'), bev=0.0, texel=0.075, long=2, seed=93 + sx)
        parts.append(ck)
    return fuse('frame', parts)


def build_cylinder():
    """Six-shot fluted cylinder.  The game indexes it about its own axis (three.js local Z).

    The ejector rod now lives on `crane` instead: as a child of the cylinder it would have
    orbited the bore every time a chamber indexed."""
    parts = []
    cy = cylinder('cyl_body', CYL_R, 0.0460, (0, CYL_Y, BORE), 'Y', 30)
    for i in range(6):
        a = TAU * i / 6
        # chamber
        cut(cy, cylinder('c_ch%d' % i, 0.0050, 0.060,
                         (math.cos(a) * 0.0118, CYL_Y, BORE + math.sin(a) * 0.0118), 'Y', 16))
        # flute between chambers
        b = a + TAU / 12
        cut(cy, cylinder('c_fl%d' % i, 0.0062, 0.0340,
                         (math.cos(b) * 0.0248, CYL_Y, BORE + math.sin(b) * 0.0248), 'Y', 16))
        # bolt notch on the outside
        cut(cy, rbox('c_bn%d' % i, (0.0040, 0.0060, 0.0030),
                     (math.cos(b) * CYL_R, CYL_Y + 0.0150, BORE + math.sin(b) * CYL_R),
                     rot=(0, -b, 0)))
    # extractor star on the rear face
    st = cylinder('cyl_star', 0.0092, 0.0035, (0, 0.0243, BORE), 'Y', 18)
    for i in range(6):
        a = TAU * i / 6
        cut(st, cylinder('c_st%d' % i, 0.0038, 0.010,
                         (math.cos(a) * 0.0118, 0.0243, BORE + math.sin(a) * 0.0118), 'Y', 12))
    finish(st, M('metal_steel'), bev=0.0004, texel=0.03, long=1)
    parts.append(st)
    finish(cy, M('metal_blued'), bev=0.0006, texel=0.05, long=1, seed=95)
    parts.insert(0, cy)
    return fuse('cylinder', parts)


def build_crane():
    """Yoke / crane: the arm the cylinder swings out on, plus the ejector rod that rides it.

    Origin is ON the crane pivot, so the game's `crane.rotateZ(+0.66..1.15)` swings the whole
    cylinder assembly out to the left (weapons_audio.md #5)."""
    parts = []
    # yoke collar round the rod, sized to sit inside the lug bore (r 0.0072)
    piv = cylinder('crn_pivot', 0.0070, 0.0160, (CRANE[0], 0.0760, CRANE[2]), 'Y', 16)
    finish(piv, M('metal_blued'), bev=0.0006, texel=0.035, long=1)
    parts.append(piv)
    # arm from the pivot up to the cylinder axis
    d = Vector((0 - CRANE[0], BORE - CRANE[2]))
    L = d.length
    u = d / L
    nvec = Vector((-u.y, u.x)) * 0.0046
    p0 = Vector((CRANE[0], CRANE[2]))
    p1 = Vector((0.0, BORE))
    arm = prism('crn_arm', [tuple(p0 + nvec), tuple(p1 + nvec), tuple(p1 - nvec),
                            tuple(p0 - nvec)], 0.0755, 0.0820)
    finish(arm, M('metal_blued'), bev=0.0008, texel=0.04, long=1)
    parts.append(arm)
    # ejector rod under the barrel, ON the pivot line, so it is stationary through the swing
    rod = cylinder('crn_rod', 0.0046, 0.0560, (0, 0.0950, BORE - 0.0185), 'Y', 16)
    finish(rod, M('metal_blued'), bev=0.0005, texel=0.03, long=1)
    parts.append(rod)
    hd = cylinder('crn_rodhead', 0.0062, 0.0080, (0, 0.1190, BORE - 0.0185), 'Y', 16)
    cut(hd, grooves('c_rh', 3, 0.0022, (0.030, 0.0010, 0.030), loc=(0, 0.1190, BORE - 0.0185),
                    axis=(0, 1, 0)))
    finish(hd, M('metal_blued'), bev=0.0005, texel=0.03, long=1)
    parts.append(hd)
    ob = fuse('crane', parts)
    return set_origin(ob, CRANE)


def build_barrel():
    parts = []
    b = cylinder('bar_tube', 0.0088, 0.1800, (0, 0.1680, BORE), 'Y', 22)
    cut(b, cylinder('c_b', 0.0050, 0.20, (0, 0.1680, BORE), 'Y', 18))
    finish(b, M('metal_blued'), bev=0.0006, texel=0.05, long=1)
    parts.append(b)
    # full-length underlug shrouding the ejector rod
    lug = prism('bar_lug', rrect(0.0170, 0.0210, 0.0045, 3, 0, BORE - 0.0170), 0.0810, 0.2540)
    cut(lug, cylinder('c_lug', 0.0072, 0.20, (0, 0.1700, BORE - 0.0185), 'Y', 18))
    cut(lug, rbox('c_lugf', (0.030, 0.0250, 0.020), (0, 0.0900, BORE - 0.0300)))
    finish(lug, M('metal_blued'), bev=0.0008, texel=0.055, long=1, seed=96)
    parts.append(lug)
    # ventilated rib
    rib = prism('bar_rib', rrect(0.0165, 0.0070, 0.0012, 2, 0, BORE + 0.0125), 0.0820, 0.2545)
    cut(rib, grooves('c_vent', 9, 0.0165, (0.030, 0.0055, 0.0060), loc=(0, 0.1700, BORE + 0.0125),
                     axis=(0, 1, 0)))
    finish(rib, M('metal_blued'), bev=0.0005, texel=0.045, long=1)
    parts.append(rib)
    # bridge between the rib and the barrel
    br = prism('bar_web', rrect(0.0088, 0.0180, 0.0020, 2, 0, BORE + 0.0060), 0.0820, 0.2545)
    finish(br, M('metal_blued'), bev=0.0005, texel=0.045, long=1)
    parts.append(br)
    post = sight_post('bar_fspost', 0.0030, 0.0075, 0.0060, loc=(0, 0.2440, BORE + 0.0160),
                      ramp=True)
    finish(post, M('metal_blued'), bev=0.0004, texel=0.03, long=1)
    parts.append(post)
    crown = cylinder('bar_crown', 0.0092, 0.0030, (0, 0.2545, BORE), 'Y', 22, r2=0.0080)
    cut(crown, cylinder('c_cr', 0.0050, 0.010, (0, 0.2545, BORE), 'Y', 18))
    finish(crown, M('metal_blued'), bev=0.0004, texel=0.03, long=1)
    parts.append(crown)
    return fuse('barrel', parts)


def build(arms=True):
    reset_scene()
    prebake()
    crane = build_crane()
    cyl = build_cylinder()
    # `cylinder` hangs off `crane`: the crane swings the whole assembly out, the cylinder
    # indexes about its own axis inside it.  Blender parenting here is a plain parent with an
    # identity parent-inverse, so the child's location is measured from the crane pivot.
    cyl.parent = crane
    cyl.location = (0.0 - CRANE[0], CYL_Y - CRANE[1], BORE - CRANE[2])
    guns = [build_frame(), crane, build_barrel()]
    arm_r = arm_l = None
    if arms:
        arm_r = hand_on_grip((0.0195, -0.0080, BORE - 0.0380), rake=-0.36,
                             elbow=(0.095, -0.035, -0.300))
        arm_l = hand_support_pistol((-0.0280, -0.0170, BORE - 0.0600), rake=-0.42,
                                    elbow=(-0.105, -0.030, -0.300))
    muzzle = (0.0, Y_MUZZLE, BORE)
    eject = (0.0, CYL_Y, BORE + 0.0060)
    aim = (0.0, -0.0140, SIGHT_Z)
    return dict(guns=guns, arm_r=arm_r, arm_l=arm_l, muzzle=muzzle, eject=eject, aim=aim)


if __name__ == '__main__':
    d = build()
    deliver(WID, GRIP_POS, d['guns'], d['muzzle'], d['eject'], d['aim'], d['arm_r'], d['arm_l'],
            movable=('crane', 'cylinder'), detail_target=(0, 0.080, 0.005), detail_dist=0.48,
            lens=50, ads_back=0.27)
    print('DONE')
