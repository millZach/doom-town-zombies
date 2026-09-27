"""Knife, frag grenade and perk bottle - single-hand first-person viewmodels.

Run with --which=knife|frag|drink (default: all three).
Gun space for these: origin at the web of the right hand around the object's handle.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_weapons import *                                   # noqa


# ===========================================================================
#  knife
# ===========================================================================
def build_knife():
    """Combat knife: 175 mm clip-point blade, steel guard, stacked-leather grip, steel pommel.
    Held blade forward, angled for a slash."""
    parts = []
    # blade: a long flat prism with a clip point and a fuller
    bl = [(-0.0110, 0.0000), (-0.0112, 0.0300), (-0.0114, 0.1000), (-0.0108, 0.1420),
          (-0.0060, 0.1680), (0.0000, 0.1800),
          (0.0090, 0.1560), (0.0135, 0.1100), (0.0140, 0.0500), (0.0140, 0.0000)]
    blade = prism_x('kn_blade', bl, -0.0022, 0.0022)
    # grind the edge: two angled cutters along the cutting side
    for sx in (-1, 1):
        cut(blade, rbox('c_ed%d' % sx, (0.010, 0.30, 0.030),
                        (sx * 0.0068, 0.090, -0.0250), rot=(0, D2R(-16 * sx), 0)))
        cut(blade, rbox('c_cl%d' % sx, (0.010, 0.10, 0.020),
                        (sx * 0.0062, 0.1640, 0.0230), rot=(D2R(28), D2R(-14 * sx), 0)))
        # fuller (blood groove)
        cut(blade, cylinder('c_fu%d' % sx, 0.0030, 0.0900, (sx * 0.0022, 0.0780, 0.0075), 'Y', 14))
    finish(blade, M('metal_steel'), bev=0.0004, texel=0.05, long=1, seed=141)
    parts.append(blade)

    # guard
    gd = prism_x('kn_guard', [(-0.0090, -0.0130), (0.0090, -0.0130), (0.0100, -0.0030),
                              (0.0080, 0.0040), (-0.0080, 0.0040), (-0.0100, -0.0030)],
                 -0.0050, 0.0050)
    boolean(gd, rbox('kn_gq', (0.0100, 0.0090, 0.0360), (0, -0.0090, 0.0000)), 'UNION')
    finish(gd, M('metal_parker'), bev=0.0008, texel=0.04, long=1)
    parts.append(gd)

    # stacked leather washer grip
    rings = []
    for i in range(17):
        t = i / 16.0
        z = -0.0135 - 0.1020 * t
        r = 0.0118 + 0.0038 * math.sin(math.pi * t) - 0.0022 * t
        w = 1.0 + (0.05 if i % 2 else -0.05)
        rings.append([(math.cos(a) * r * w, math.sin(a) * r * 0.80 * w, z)
                      for a in [TAU * k / 18 for k in range(18)]])
    grip = loft('kn_grip', rings)
    finish(grip, M('polymer_rubber'), bev=0.0, texel=0.05, smooth=True)
    parts.append(grip)

    # pommel
    pm = lathe('kn_pommel', [(0.0000, 0.0000), (0.0100, 0.0010), (0.0116, -0.0062),
                             (0.0092, -0.0142), (0.0000, -0.0168)],
               segs=20, loc=(0, 0, -0.1150))
    finish(pm, M('metal_parker'), bev=0.0006, texel=0.03, long=1)
    parts.append(pm)
    return fuse('knife', parts)


def deliver_knife():
    reset_scene()
    prebake()
    kn = build_knife()
    # blade forward with a slight rise; the flat of the blade faces the camera
    place(kn, (0, 0, 0), (-0.96, 0.10, 0.26), (0.10, 0.955, 0.28))
    # hammer grip: handle across the palm, fingers up and over, back of the hand to the camera
    fing = (0.10, 0.10, 0.99)
    back = (-0.93, 0.16, 0.32)
    wrist = wrist_from_mcp((0.0125, -0.0400, -0.0070), fing, back, 'R')
    arm_r = build_arm('arm_R', 'R', wrist=wrist, fingers=fing, back=back,
                      elbow=(wrist[0] + 0.090, wrist[1] - 0.040, wrist[2] - 0.300),
                      curl=(0.88, 0.92, 0.93, 0.94), thumb_curl=0.28, thumb_abduct=-30,
                      cuff_at=0.52, forearm_len=0.30, seed=4)
    muzzle = (0.0180, 0.1719, 0.0504)
    eject = (0.0, 0.0, 0.0)
    aim = (0.0080, 0.0764, 0.0224)
    deliver('knife', (0.124, 0.258, -0.056), [kn], muzzle, eject, aim, arm_r, None,
            movable=(), detail_target=(0.010, 0.060, 0.025), detail_dist=0.42, lens=50)


# ===========================================================================
#  frag grenade (Mk 2 "pineapple" - period correct for 1950s Nevada)
# ===========================================================================
def build_frag():
    parts = []
    body = lathe('frg_body', [(0.0000, -0.0300), (0.0180, -0.0295), (0.0268, -0.0170),
                              (0.0288, 0.0000), (0.0268, 0.0175), (0.0180, 0.0300),
                              (0.0000, 0.0305)], segs=26)
    # the cast fragmentation grid
    for i in range(5):
        cut(body, lathe('c_h%d' % i, [(0.0264, -0.0013), (0.0340, -0.0013),
                                      (0.0340, 0.0013), (0.0264, 0.0013)],
                        segs=26, loc=(0, 0, -0.0215 + i * 0.0108)))
    for i in range(10):
        a = TAU * i / 10
        cut(body, rbox('c_v%d' % i, (0.0032, 0.0110, 0.0700),
                       (math.cos(a) * 0.0330, math.sin(a) * 0.0330, 0), rot=(0, 0, a)))
    finish(body, M('metal_parker'), bev=0.0007, texel=0.045, seed=151)
    parts.append(body)
    # fuze assembly
    fz = lathe('frg_fuze', [(0.0000, 0.0300), (0.0105, 0.0305), (0.0115, 0.0360),
                            (0.0092, 0.0405), (0.0092, 0.0470), (0.0000, 0.0470)], segs=20)
    finish(fz, M('metal_parker'), bev=0.0006, texel=0.03)
    parts.append(fz)
    # spoon (safety lever)
    sp = prism_x('frg_spoon', [(0.0085, 0.0455), (0.0180, 0.0450), (0.0250, 0.0330),
                               (0.0265, 0.0050), (0.0245, -0.0180), (0.0215, -0.0175),
                               (0.0235, 0.0050), (0.0220, 0.0320), (0.0160, 0.0415),
                               (0.0085, 0.0420)], -0.0070, 0.0070)
    finish(sp, M('metal_parker'), bev=0.0005, texel=0.03, long=1)
    parts.append(sp)
    # pull ring + pin
    rg = lathe('frg_ring', [(0.0092, -0.0016), (0.0125, -0.0016), (0.0125, 0.0016),
                            (0.0092, 0.0016)], segs=20, loc=(-0.0150, 0.0000, 0.0425),
               rot=(D2R(90), 0, 0))
    finish(rg, M('metal_steel'), bev=0.0, texel=0.02)
    parts.append(rg)
    pin = cylinder('frg_pin', 0.0016, 0.0180, (-0.0055, 0.0000, 0.0425), 'X', 10)
    finish(pin, M('metal_steel'), bev=0.0, texel=0.02)
    parts.append(pin)
    return fuse('frag', parts)


def deliver_frag():
    reset_scene()
    prebake()
    fg = build_frag()
    place(fg, (0.0030, 0.0090, 0.0215), (1, 0, 0), (-0.22, 0.26, 0.94))
    # back of the hand toward the camera, fingers wrapping over the far side of the grenade
    fing = (-0.24, 0.30, 0.92)
    back = (0.93, -0.06, 0.36)
    wrist = wrist_from_mcp((0.0275, 0.0080, 0.0030), fing, back, 'R')
    arm_r = build_arm('arm_R', 'R', wrist=wrist, fingers=fing, back=back,
                      elbow=(wrist[0] + 0.075, wrist[1] - 0.045, wrist[2] - 0.300),
                      curl=(0.66, 0.70, 0.74, 0.78), thumb_curl=0.34, thumb_abduct=-4,
                      fat=1.02, cuff_at=0.52, forearm_len=0.30, seed=4)
    deliver('frag', (0.126, 0.300, -0.082), [fg], (0, 0.030, 0.055), (0, 0, 0), (0, 0.010, 0.030),
            arm_r, None, movable=(), detail_target=(0, 0.010, 0.020), detail_dist=0.28, lens=50)


# ===========================================================================
#  perk bottle
# ===========================================================================
def build_drink():
    parts = []
    prof = [(0.0000, -0.0600), (0.0300, -0.0600), (0.0322, -0.0560),
            (0.0330, -0.0200), (0.0322, 0.0180), (0.0295, 0.0330),
            (0.0215, 0.0480), (0.0140, 0.0600), (0.0128, 0.0720),
            (0.0150, 0.0780), (0.0148, 0.0840), (0.0120, 0.0850),
            (0.0112, 0.0790), (0.0112, 0.0620), (0.0122, 0.0560),
            (0.0190, 0.0450), (0.0270, 0.0310), (0.0298, 0.0170),
            (0.0302, -0.0200), (0.0298, -0.0550), (0.0000, -0.0550)]
    glass = lathe('bottle_glass', prof, segs=28)
    mat_glass = plain('bottle_glass', (0.55, 0.62, 0.52), 0.06, 0.0)
    try:
        b = mat_glass.node_tree.nodes.get('Principled BSDF')
        b.inputs['Transmission Weight'].default_value = 0.92
        b.inputs['IOR'].default_value = 1.46
        b.inputs['Roughness'].default_value = 0.06
    except Exception:
        pass
    finish(glass, mat_glass, bev=0.0006, texel=0.05, smooth=True)
    parts.append(glass)

    liq = lathe('bottle_liquid', [(0.0000, -0.0545), (0.0294, -0.0545), (0.0294, 0.0165),
                                  (0.0265, 0.0305), (0.0186, 0.0440), (0.0000, 0.0470)], segs=26)
    finish(liq, plain('bottle_liquid', (0.42, 0.10, 0.05), 0.10, 0.0), bev=0.0, texel=0.05)
    parts.append(liq)

    label = lathe('bottle_label', [(0.0336, -0.0300), (0.0336, 0.0180)], segs=28)
    finish(label, plain('bottle_label', (0.62, 0.58, 0.50), 0.62, 0.0), bev=0.0, texel=0.05)
    parts.append(label)

    cap = lathe('bottle_cap', [(0.0000, 0.0852), (0.0140, 0.0852), (0.0152, 0.0830),
                               (0.0152, 0.0780), (0.0138, 0.0765)], segs=22)
    cut(cap, grooves('c_crimp', 20, 0.0048, (0.0018, 0.0018, 0.010),
                     loc=(0, 0, 0.0800), axis=(1, 0, 0)))
    finish(cap, M('metal_steel'), bev=0.0004, texel=0.02)
    parts.append(cap)
    return fuse('bottle', parts)


def deliver_drink():
    reset_scene()
    prebake()
    bt = build_drink()
    place(bt, (0.0000, 0.0060, 0.0100), (1, 0, 0), (-0.22, 0.50, 0.84))
    fing = (-0.26, 0.33, 0.91)
    back = (0.92, -0.08, 0.38)
    wrist = wrist_from_mcp((0.0300, 0.0045, 0.0000), fing, back, 'R')
    arm_r = build_arm('arm_R', 'R', wrist=wrist, fingers=fing, back=back,
                      elbow=(wrist[0] + 0.075, wrist[1] - 0.045, wrist[2] - 0.300),
                      curl=(0.62, 0.66, 0.70, 0.74), thumb_curl=0.34, thumb_abduct=-4,
                      fat=1.02, cuff_at=0.52, forearm_len=0.30, seed=4)
    deliver('drink', (0.126, 0.300, -0.086), [bt], (0, 0.045, 0.085), (0, 0, 0), (0, 0.020, 0.030),
            arm_r, None, movable=(), detail_target=(0, 0.010, 0.030), detail_dist=0.30, lens=50)


if __name__ == '__main__':
    which = 'all'
    for a in sys.argv:
        if a.startswith('--which='):
            which = a.split('=', 1)[1]
    if which in ('all', 'knife'):
        deliver_knife()
    if which in ('all', 'frag'):
        deliver_frag()
    if which in ('all', 'drink'):
        deliver_drink()
    print('DONE')
