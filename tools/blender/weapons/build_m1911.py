"""M1911 .45 pistol - first-person viewmodel.

Gun space: origin at the web of the shooting hand on the backstrap; bore along +Y at z = BORE;
+X = right side of the gun.  Real M1911A1: 216 mm long, 135 mm tall, 23.4 mm slide width.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_weapons import *                                   # noqa

WID = 'm1911'
BORE = 0.0280                 # bore axis height in gun space
SW = 0.0234                   # slide width
Y_REAR = -0.0300              # rear face of the slide
Y_MUZZLE = 0.1670             # slide 196 mm; 216 mm muzzle-to-beavertail

SLIDE_BOT, SLIDE_FLANK, SLIDE_TOP = 0.0130, 0.0268, 0.0378
GRIP_POS = (0.152, 0.300, -0.064)

TX = 0.060                    # texture tile for gun metal (metres)


# ---------------------------------------------------------------------------
def build_slide():
    parts = []
    prof = slide_profile(SW, SLIDE_BOT, SLIDE_FLANK, SLIDE_TOP, n=11, flat=0.35)
    body = prism('slide_body', prof, Y_REAR, 0.1660)

    # --- rear cocking serrations (slanted, 1911 style) -----------------------
    for sx in (-1, 1):
        g = grooves('c_ser%d' % sx, 9, 0.00345, (0.010, 0.00130, 0.040),
                    loc=(sx * (SW * 0.5 + 0.0035), -0.0125, 0.0245),
                    axis=(0, 1, 0), rot=(D2R(-16), 0, 0))
        cut(body, g)

    # --- ejection port (right side, lowered & flared) ------------------------
    cut(body, rbox('c_port', (0.030, 0.0470, 0.0155), (0.0135, 0.0645, 0.0340)))
    cut(body, rbox('c_port2', (0.030, 0.0470, 0.0120), (0.0150, 0.0645, 0.0300), rot=(0, D2R(-14), 0)))

    # --- muzzle end: bushing + recoil-spring plug ----------------------------
    cut(body, cylinder('c_bore', 0.00860, 0.032, (0, 0.1570, BORE), 'Y', 28))
    cut(body, cylinder('c_plug', 0.00600, 0.032, (0, 0.1570, BORE - 0.0150), 'Y', 24))
    # chamfer the lower front corner of the slide
    cut(body, rbox('c_fl', (0.06, 0.020, 0.014), (0.0, 0.1678, SLIDE_BOT - 0.0055), rot=(D2R(34), 0, 0)))
    bush = tube('slide_bushing', 0.00855, 0.00700, 0.0080, (0, 0.1622, BORE), 'Y', 28)
    finish(bush, M('metal_blued'), bev=0.0004, texel=0.035, long=1)
    parts.append(bush)
    plug = cylinder('slide_plug', 0.00590, 0.0060, (0, 0.1632, BORE - 0.0150), 'Y', 24)
    cut(plug, cylinder('c_p2', 0.0032, 0.010, (0, 0.1648, BORE - 0.0150), 'Y', 20))
    finish(plug, M('metal_blued'), bev=0.0004, texel=0.035, long=1)
    parts.append(plug)

    # --- firing-pin stop plate + extractor on the rear face ------------------
    cut(body, rbox('c_fp', (0.0105, 0.0040, 0.0140), (0, Y_REAR + 0.0010, BORE + 0.0008)))
    fps = rbox('slide_fpstop', (0.0098, 0.0030, 0.0133), (0, Y_REAR + 0.0017, BORE + 0.0008))
    finish(fps, M('metal_blued'), bev=0.0004, texel=0.035, long=1)
    parts.append(fps)
    ext = cylinder('slide_extractor', 0.0026, 0.0500, (0.0072, Y_REAR + 0.0245, BORE + 0.0048), 'Y', 14)
    finish(ext, M('metal_blued'), bev=0.0003, texel=0.035, long=1)
    parts.append(ext)

    # --- sights (dovetailed blades) -----------------------------------------
    fs = sight_post('slide_frontsight', w=0.0032, t=0.0034, hgt=0.0042,
                    loc=(0, 0.1505, SLIDE_TOP - 0.0007))
    rs = rear_notch('slide_rearsight', w=0.0160, t=0.0055, hgt=0.0072, notch_w=0.0044,
                    notch_d=0.0036, loc=(0, Y_REAR + 0.0078, SLIDE_TOP - 0.0007))
    parts += [fs, rs]

    finish(body, M('metal_blued'), bev=0.00075, segs=2, texel=TX, long=1, jitter=0.31, seed=11)
    for o in (fs, rs):
        finish(o, M('metal_blued'), bev=0.00045, texel=0.035, long=1)
    return fuse('slide', [body] + parts)


# ---------------------------------------------------------------------------
FRAME_OUTLINE = [
    (-0.0300, 0.0128), (0.1185, 0.0128),                      # under the slide
    (0.1185, -0.0040), (0.1150, -0.0062), (0.0420, -0.0062),  # dust cover bottom
    (0.0392, -0.0110),
] + arc_pts(0.0250, -0.0215, 0.0145, 38, -66, 7) + [          # trigger-guard front bow
    (0.0160, -0.0357), (0.0030, -0.0330), (-0.0030, -0.0285),
    (-0.0075, -0.0440), (-0.0140, -0.0665), (-0.0208, -0.0900),  # front strap, 16 deg rake
    (-0.0262, -0.0938), (-0.0700, -0.0938),                   # magwell floor
    (-0.0762, -0.0862), (-0.0655, -0.0480), (-0.0560, -0.0148),
    (-0.0508, 0.0020), (-0.0520, 0.0072), (-0.0412, 0.0128),   # backstrap + beavertail
]

TRIGGER_GUARD_HOLE = (arc_pts(0.0245, -0.0195, 0.0108, 30, -140, 9)
                      + [(0.0040, -0.0262), (0.0012, -0.0180), (0.0030, -0.0092),
                         (0.0180, -0.0080), (0.0290, -0.0090)])


def build_frame():
    parts = []
    fr = prism_x('frame_body', FRAME_OUTLINE, -0.0112, 0.0112)
    cut(fr, prism_x('c_tg', TRIGGER_GUARD_HOLE, -0.03, 0.03))
    cut(fr, prism_x('c_well', [(-0.0255, -0.0962), (-0.0706, -0.0962),
                               (-0.0545, -0.0290), (-0.0215, -0.0290)], -0.0104, 0.0104))
    # recess for the grip panels
    for x0, x1 in ((-0.0125, -0.0082), (0.0082, 0.0125)):
        cut(fr, prism_x('c_gr', [(-0.0150, -0.0250), (-0.0248, -0.0880), (-0.0695, -0.0880),
                                 (-0.0495, -0.0250)], x0, x1))
    # mainspring-housing + front-strap serrations
    cut(fr, grooves('c_msh', 11, 0.0050, (0.040, 0.0016, 0.0016),
                    loc=(0, -0.0625, -0.0555), axis=(0, 0.276, -0.961), rot=(D2R(16), 0, 0)))
    cut(fr, grooves('c_fs', 7, 0.0050, (0.040, 0.0014, 0.0014),
                    loc=(0, -0.0146, -0.0600), axis=(0, -0.276, -0.961), rot=(D2R(-16), 0, 0)))
    finish(fr, M('metal_parker'), bev=0.00075, segs=2, texel=TX, long=1, jitter=0.17, seed=3)
    parts.append(fr)

    rail = rbox('frame_rail', (SW, 0.1485, 0.0060), (0, 0.0443, 0.0098))
    cut(rail, rbox('c_r1', (0.0190, 0.20, 0.02), (0, 0.04, 0.0128)))
    finish(rail, M('metal_parker'), bev=0.0006, texel=TX, long=1, seed=5)
    parts.append(rail)

    trg = prism_x('frame_trigger', [(0.0030, -0.0078), (0.0092, -0.0080), (0.0100, -0.0250),
                                    (0.0026, -0.0248)], -0.0060, 0.0060)
    cut(trg, grooves('c_tr', 6, 0.0028, (0.02, 0.0010, 0.0010), loc=(0, 0.0102, -0.0165),
                     axis=(0, 0, 1)))
    finish(trg, M('metal_steel'), bev=0.0004, texel=0.04, long=1)
    parts.append(trg)

    ham = prism_x('frame_hammer', [(-0.0395, 0.0150), (-0.0300, 0.0152), (-0.0286, 0.0232),
                                   (-0.0350, 0.0300), (-0.0455, 0.0300), (-0.0500, 0.0250),
                                   (-0.0470, 0.0180)], -0.0034, 0.0034)
    cut(ham, cylinder('c_ham', 0.0044, 0.02, (0, -0.0400, 0.0258), 'X', 18))
    finish(ham, M('metal_steel'), bev=0.0005, texel=0.04, long=1)
    parts.append(ham)
    parts.append(finish(screw('frame_hpin', 0.0026, (0.0113, -0.0378, 0.0148), 'Y', 'pin', 0.0008),
                        M('metal_steel'), bev=0.0002, texel=0.03))

    for x0, x1 in ((0.0112, 0.0152), (-0.0152, -0.0112)):
        sf = prism_x('frame_safety', [(-0.0330, 0.0040), (-0.0240, 0.0052), (-0.0232, 0.0096),
                                      (-0.0352, 0.0100), (-0.0400, 0.0064)], x0, x1)
        finish(sf, M('metal_steel'), bev=0.0005, texel=0.04, long=1)
        parts.append(sf)

    ss = prism_x('frame_slidestop', [(0.0170, 0.0038), (0.0300, 0.0046), (0.0322, 0.0092),
                                     (0.0210, 0.0104), (0.0120, 0.0082), (0.0112, 0.0050)],
                 -0.0150, -0.0112)
    finish(ss, M('metal_steel'), bev=0.0005, texel=0.04, long=1)
    parts.append(ss)
    parts.append(finish(cylinder('frame_sspin', 0.0038, 0.0044, (-0.0133, 0.0262, 0.0068), 'X', 18),
                        M('metal_steel'), bev=0.0004, texel=0.03))
    parts.append(finish(cylinder('frame_sspin_r', 0.0034, 0.0022, (0.0122, 0.0262, 0.0068), 'X', 18),
                        M('metal_steel'), bev=0.0004, texel=0.03))

    mr = cylinder('frame_magrel', 0.0044, 0.0040, (-0.0128, 0.0052, -0.0165), 'X', 20)
    cut(mr, cylinder('c_mr', 0.0016, 0.004, (-0.0142, 0.0052, -0.0165), 'X', 14))
    finish(mr, M('metal_steel'), bev=0.0004, texel=0.03)
    parts.append(mr)

    # --- grip panels ---------------------------------------------------------
    panel_outline = [(-0.0160, -0.0252), (-0.0136, -0.0330), (-0.0252, -0.0872),
                     (-0.0348, -0.0908), (-0.0662, -0.0876), (-0.0505, -0.0290),
                     (-0.0415, -0.0245)]
    grip_dn = (0, -0.276, -0.961)                  # straight down the grip
    for sx in (-1, 1):
        x0, x1 = (0.0082, 0.0157) if sx > 0 else (-0.0157, -0.0082)
        gp = prism_x('grip_panel_%s' % ('R' if sx > 0 else 'L'), panel_outline, x0, x1)
        finish(gp, M('wood_walnut'), bev=0.0008, texel=0.075, long=2, jitter=0.4, seed=7 + sx)
        parts.append(gp)
        ck = checkering('grip_ck_%d' % sx, 0.050, 0.024, nu=11, nv=6, depth=0.00095, thick=0.0010)
        place(ck, (sx * 0.01555, -0.0348, -0.0562), grip_dn, (sx, 0, 0))
        finish(ck, M('wood_walnut'), bev=0.0, texel=0.075, long=2, jitter=0.4, seed=7 + sx)
        parts.append(ck)
        for yy, zz in ((-0.0258, -0.0348), (-0.0455, -0.0748)):
            boss = cylinder('grip_boss%d_%d' % (sx, int(zz * 1e4)), 0.0050, 0.0022,
                            (sx * 0.0158, yy, zz), 'X', 20)
            finish(boss, M('wood_walnut'), bev=0.0004, texel=0.075, long=2)
            parts.append(boss)
            parts.append(finish(screw('grip_screw%d_%d' % (sx, int(zz * 1e4)), 0.0031,
                                      (sx * 0.0169, yy, zz), 'X', 'slot', 0.0012, 0.0006),
                                M('metal_steel'), bev=0.0002, texel=0.03))
    return fuse('frame', parts)


# ---------------------------------------------------------------------------
def build_mag():
    body = prism_x('mag_body', [(-0.0222, -0.0290), (-0.0540, -0.0290),
                                (-0.0705, -0.0945), (-0.0272, -0.0945)], -0.0098, 0.0098)
    fp = prism_x('mag_plate', [(-0.0248, -0.0922), (-0.0692, -0.0922),
                               (-0.0712, -0.0998), (-0.0240, -0.0998)], -0.0112, 0.0112)
    finish(body, M('metal_parker'), bev=0.0005, texel=TX, long=2)
    finish(fp, M('metal_blued'), bev=0.0008, texel=TX, long=1)
    return fuse('mag', [body, fp])


def build_barrel():
    b = cylinder('barrel', 0.00680, 0.0900, (0, 0.1220, BORE), 'Y', 26)
    cut(b, cylinder('c_b', 0.00575, 0.120, (0, 0.1220, BORE), 'Y', 24))
    cut(b, cylinder('c_crown', 0.00660, 0.0032, (0, 0.1662, BORE), 'Y', 24, r2=0.0058))
    finish(b, M('metal_steel'), bev=0.0004, texel=0.05, long=1)
    return b


# ---------------------------------------------------------------------------
def build(arms=True):
    reset_scene()
    prebake()
    slide = build_slide()
    frame = build_frame()
    mag = build_mag()
    barrel = build_barrel()
    guns = [slide, frame, mag, barrel]

    arm_r = arm_l = None
    if arms:
        # right hand: wrapped on the grip, trigger finger on the trigger, thumb up the frame
        r_fing = (0.05, 0.935, -0.352)
        r_back = (0.962, -0.02, 0.272)
        r_wrist = wrist_from_mcp((0.0180, -0.0040, -0.0325), r_fing, r_back, 'R')
        arm_r = build_arm('arm_R', 'R', wrist=r_wrist, fingers=r_fing, back=r_back,
                          elbow=(r_wrist[0] + 0.095, r_wrist[1] - 0.035, r_wrist[2] - 0.300),
                          curl=(0.74, 0.90, 0.93, 0.95), thumb_curl=0.24, thumb_abduct=-26,
                          cuff_at=0.52, forearm_len=0.30, seed=4)
        # left hand: wraps the right hand from below-left, thumb forward under the frame
        l_fing = (0.055, 0.905, -0.422)
        l_back = (-0.948, 0.02, 0.318)
        l_wrist = wrist_from_mcp((-0.0272, -0.0175, -0.0545), l_fing, l_back, 'L')
        arm_l = build_arm('arm_L', 'L', wrist=l_wrist, fingers=l_fing, back=l_back,
                          elbow=(l_wrist[0] - 0.105, l_wrist[1] - 0.030, l_wrist[2] - 0.300),
                          curl=(0.88, 0.92, 0.94, 0.95), thumb_curl=0.30, thumb_abduct=-34,
                          cuff_at=0.52, forearm_len=0.30, seed=9)

    muzzle = (0.0, Y_MUZZLE, BORE)
    eject = (0.0125, 0.0645, BORE + 0.0060)
    aim = (0.0, Y_REAR + 0.0078, SLIDE_TOP + 0.0035)   # notch floor = front sight top
    root, wep = build_viewmodel(GRIP_POS, guns, muzzle, eject, aim, arm_r, arm_l)
    return dict(root=root, wep=wep, guns=guns, arm_r=arm_r, arm_l=arm_l,
                muzzle=muzzle, eject=eject, aim=aim, slide=slide, mag=mag)


if __name__ == '__main__':
    d = build()
    gp = Vector(GRIP_POS)
    if '--noexport' not in sys.argv:
        export_weapon(d['root'], WID)
        report(WID, d['wep'], d['muzzle'], d['aim'], d['eject'], ['slide', 'mag'])
    RES = (960, 540)
    render_eye(os.path.join(WRENDERS, WID + '_hipfire.png'), samples=32, res=RES)
    render_detail(os.path.join(WRENDERS, WID + '_grip.png'),
                  target=tuple(gp + Vector((0, -0.020, -0.050))),
                  distance=0.42, yaw=-52, pitch=14, samples=32, lens=40, res=RES)
    # back/fov mirror the game's ADS numbers for the M1911 (config.js adsDist 0.26, VM_FOV.ads)
    render_ads(os.path.join(WRENDERS, WID + '_ads.png'),
               tuple(gp + Vector(d['aim'])), back=0.26, samples=32, res=RES)
    hide([d['arm_r'], d['arm_l']], True)
    render_detail(os.path.join(WRENDERS, WID + '_detail.png'),
                  target=tuple(gp + Vector((0, 0.055, -0.020))),
                  distance=0.40, yaw=34, pitch=16, samples=32, lens=50, res=RES)
    render_detail(os.path.join(WRENDERS, WID + '_detail2.png'),
                  target=tuple(gp + Vector((0, 0.050, -0.025))),
                  distance=0.40, yaw=-142, pitch=12, samples=32, lens=50, res=RES)
    print('DONE')
