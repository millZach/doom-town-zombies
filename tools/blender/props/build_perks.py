"""perk_*.glb - four 1950s soda vending machines (Juggernog, Speed Cola,
Quick Revive, Double Tap).

~1.00 w x 0.75 d x 2.20 h, origin floor centre, front = -Y.
Objects per file: `machine` (everything solid) and `sign` (the illuminated marquee
panels, material `<perk>_sign_glow`).

Two emissive materials per machine (environment.md #1d):
  `<perk>_sign_glow`  the backlit marquee panel - modest emission (authored 1.2) so the
                      printed artwork stays readable and the room is not flooded;
  `<perk>_trim_glow`  the small bright accents - the neon tube tracing the marquee and
                      the two pilot lamps on the control plate - authored 3.0.
The game classifies them by name (`interactables.js` `glowKind`) and drives the sign in
the 0.85-1.4 band and the trim in the 2.4-4.0 band.

Run:  blender -b --factory-startup --python build_perks.py -- [perkid ...]
"""
import sys, os, math, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib_props import *

HW, HD = 0.500, 0.375      # half width / half depth of the cabinet
FY = -HD                   # front surface plane
CR = 0.085                 # vertical corner radius
BODY_TOP = 1.620           # where the dome starts
CROWN_Z0 = 1.780

# ---------------------------------------------------------------------------- configs

PERKS = {
    'juggernog': dict(
        title='JUGGER', title2='NOG', tag='STRENGTH TONIC', price='2500',
        body=(0.300, 0.0145, 0.0115),      # deep oxblood red
        body2=(0.155, 0.0085, 0.0070),
        panel=(0.560, 0.500, 0.375),       # aged cream
        accent=(0.480, 0.330, 0.062),      # brass
        letter=(0.420, 0.019, 0.014),
        sign=(0.400, 0.030, 0.014),        # red glow
        trim=(0.980, 0.190, 0.085),        # hot neon red accent
        signletter=(0.72, 0.65, 0.48),
        crown='box', font=FONT_COOPER, seed=1.0),
    'speedcola': dict(
        title='SPEED', title2='COLA', tag='QUICK HANDS', price='3000',
        body=(0.022, 0.135, 0.042),        # bottle green
        body2=(0.011, 0.062, 0.022),
        panel=(0.600, 0.570, 0.470),
        accent=(0.480, 0.360, 0.070),
        letter=(0.016, 0.105, 0.036),
        sign=(0.090, 0.420, 0.080),        # acid green glow
        trim=(0.420, 0.980, 0.300),        # hot neon green accent
        signletter=(0.045, 0.10, 0.038),
        crown='slant', font=FONT_BAUHAUS, seed=2.0),
    'quickrevive': dict(
        title='QUICK', title2='REVIVE', tag='ON YOUR FEET', price='1500',
        body=(0.070, 0.190, 0.310),        # powder blue
        body2=(0.470, 0.475, 0.470),       # white upper
        panel=(0.620, 0.630, 0.625),
        accent=(0.520, 0.525, 0.540),
        letter=(0.045, 0.110, 0.205),
        sign=(0.105, 0.300, 0.620),        # ice blue glow
        trim=(0.400, 0.760, 1.000),        # ice-white neon accent
        signletter=(0.035, 0.075, 0.150),
        crown='disc', font=FONT_COOPER, seed=3.0),
    'doubletap': dict(
        title='DOUBLE', title2='TAP', tag='ROOT BEER', price='2000',
        body=(0.110, 0.030, 0.014),        # dark red-brown
        body2=(0.055, 0.016, 0.008),
        panel=(0.260, 0.125, 0.045),
        accent=(0.560, 0.390, 0.072),      # gold
        letter=(0.545, 0.380, 0.075),
        sign=(0.580, 0.260, 0.030),        # amber glow
        trim=(1.000, 0.620, 0.140),        # hot amber neon accent
        signletter=(0.085, 0.035, 0.014),
        crown='arch', font=FONT_BERNARD, seed=4.0),
}


# ---------------------------------------------------------------------------- helpers

def cabinet_rings():
    prof = [
        (0.000, 0.455, 0.330, 0.050),
        (0.042, 0.478, 0.352, 0.060),
        (0.078, HW, HD, CR),
        (BODY_TOP, HW, HD, CR),
        (1.690, HW - 0.005, HD - 0.005, CR + 0.012),
        (1.748, HW - 0.020, HD - 0.020, CR + 0.032),
        (1.795, HW - 0.046, HD - 0.048, CR + 0.062),
        (1.834, HW - 0.094, HD - 0.102, CR + 0.090),
        (1.862, HW - 0.172, HD - 0.180, CR + 0.090),
        (1.880, HW - 0.272, HD - 0.266, CR + 0.020),
    ]
    return [rounded_rect(hw, hd, r, seg=4, z=z) for z, hw, hd, r in prof]


def band(name, z0, z1, out=0.012, r=CR, taper=0.0):
    rings = [
        rounded_rect(HW + out * 0.3, HD + out * 0.3, r, 4, z0),
        rounded_rect(HW + out, HD + out, r + out, 4, z0 + 0.008),
        rounded_rect(HW + out - taper, HD + out - taper, r + out, 4, z1 - 0.008),
        rounded_rect(HW + out * 0.3 - taper, HD + out * 0.3 - taper, r, 4, z1),
    ]
    return loft(name, rings, cap_bottom=False, cap_top=False)


def ellipse(name, rx, rz, depth, loc, rot=(0, 0, 0), seg=26, bevel=0.004):
    pts = [(math.cos(i / seg * TAU) * rx, math.sin(i / seg * TAU) * rz) for i in range(seg)]
    return profile_extrude(name, pts, depth, loc, rot, bevel=bevel, bseg=1)


def bottle(name, h=0.34, loc=(0, 0, 0), squash=0.40):
    s = h / 0.34
    prof = [(0.000, 0.000), (0.075, 0.000), (0.082, 0.014), (0.076, 0.070),
            (0.068, 0.118), (0.071, 0.156), (0.078, 0.190), (0.072, 0.228),
            (0.052, 0.254), (0.034, 0.270), (0.030, 0.294), (0.035, 0.314),
            (0.033, 0.331), (0.000, 0.337)]
    prof = [(r * s, z * s) for r, z in prof]
    ob = lathe(name, prof, verts=22, loc=loc)
    ob.scale = (1.0, squash, 1.0)
    apply_transforms(ob, rot=False, scale=True)
    return ob


def txt(name, body, font, size, loc, rot=(D2R(90), 0, 0), extrude=0.006, bev=0.0018,
        spacing=1.0):
    return text_mesh(name, body, font=font, size=size, extrude=extrude, bev=bev,
                     loc=loc, rot=rot, res=1, bres=0, spacing=spacing)


def neon_frame(name, hw, hh, centre, tilt=0.0, thick=0.016):
    """Four slim bars tracing a rectangle in the plane whose normal is local -Y.

    `tilt` rotates the whole frame about X (the slant crown), so the bars stay flush
    with the sign panel they outline."""
    R = Matrix.Rotation(tilt, 4, 'X')
    C = Vector(centre)

    def P(dx, dz):
        return tuple(C + (R @ Vector((dx, 0.0, dz))))

    r = thick * 0.46
    return [
        rbox(f'{name}_t', (2 * hw + thick, thick, thick), P(0, hh), radius=r, seg=2,
             rot=(tilt, 0, 0)),
        rbox(f'{name}_b', (2 * hw + thick, thick, thick), P(0, -hh), radius=r, seg=2,
             rot=(tilt, 0, 0)),
        rbox(f'{name}_l', (thick, thick, 2 * hh - thick), P(-hw, 0), radius=r, seg=2,
             rot=(tilt, 0, 0)),
        rbox(f'{name}_r', (thick, thick, 2 * hh - thick), P(hw, 0), radius=r, seg=2,
             rot=(tilt, 0, 0)),
    ]


def slats(name, w, h, y, z, x=0.0, n=7, depth=0.018):
    return [rbox(f'{name}_{i}', (w, depth, h / n * 0.55),
                 (x, y, z - h / 2 + h * (i + 0.5) / n), radius=0.0015, seg=1)
            for i in range(n)]


# ---------------------------------------------------------------------------- build

def build_machine(pid, cfg):
    props_scene()
    random.seed(int(cfg['seed'] * 31) + 5)
    sd = cfg['seed']
    FONT = cfg['font']

    m_body = painted(f'{pid}_body', cfg['body'], rough=0.27, wear=0.20, rust=0.30,
                     grime=0.70, dent=0.8, scale=1.0, seed=sd, variation=0.11,
                     dust=0.03, streak=0.50)
    m_body2 = painted(f'{pid}_body2', cfg['body2'], rough=0.29, wear=0.20, rust=0.28,
                      grime=0.72, dent=0.75, scale=1.0, seed=sd + 11, variation=0.11,
                      dust=0.03, streak=0.50)
    m_panel = painted(f'{pid}_panel', cfg['panel'], rough=0.33, wear=0.28, rust=0.22,
                      grime=0.66, dent=0.55, scale=1.0, seed=sd + 21, variation=0.16,
                      dust=0.05, streak=0.55)
    m_chrome = chrome(f'{pid}_chrome', tint=(0.66, 0.67, 0.69), rough=0.14, grime=0.60,
                      scratch=1.0, pit=0.9, scale=1.2, seed=sd + 31)
    m_gold = weathered(f'{pid}_gold', color=cfg['accent'], roughness=0.30, metallic=1.0,
                       wear_color=(0.30, 0.235, 0.105), wear=0.24, wear_rough=0.48,
                       rust=0.16, rust_color=(0.21, 0.115, 0.045), grime=0.60, dust=0.08,
                       variation=0.07, scale=1.5, seed=sd + 41, bump=0.35, dent=0.3,
                       scratch=0.9, speckle=0.10, streak=0.4)
    m_letter = painted(f'{pid}_letter', cfg['letter'], rough=0.31, wear=0.26, rust=0.05,
                       grime=0.5, dent=0.12, scale=2.0, seed=sd + 51, variation=0.10,
                       dust=0.06, streak=0.3, speckle=0.15)
    m_signletter = painted(f'{pid}_signletter', cfg['signletter'], rough=0.38, wear=0.22,
                           rust=0.04, grime=0.45, dent=0.10, scale=2.0, seed=sd + 61,
                           variation=0.10, dust=0.05, streak=0.25, speckle=0.15)
    m_dark = weathered(f'{pid}_dark', color=(0.014, 0.0135, 0.013), roughness=0.66,
                       metallic=0.0, wear_color=(0.09, 0.085, 0.08), wear=0.15, rust=0.0,
                       grime=0.5, dust=0.06, variation=0.06, scale=2.0, seed=sd + 71,
                       bump=0.4, scratch=0.4, speckle=0.15)
    m_rubber = weathered(f'{pid}_rubber', color=(0.022, 0.021, 0.020), roughness=0.82,
                         metallic=0.0, wear=0.12, rust=0.0, grime=0.5, dust=0.08,
                         variation=0.08, scale=3.0, seed=sd + 81, bump=0.5, scratch=0.3,
                         speckle=0.2)
    m_sign = weathered(f'{pid}_sign_src', color=cfg['sign'], roughness=0.28, metallic=0.0,
                       wear_color=(0.50, 0.47, 0.43), wear=0.14, wear_rough=0.6, wear_metal=0.0,
                       rust=0.0, grime=0.26, grime_color=(0.070, 0.070, 0.070),
                       dust=0.04, variation=0.06, scale=1.6, seed=sd + 91,
                       bump=0.25, dent=0.15, scratch=0.4, ao_dist=0.05, speckle=0.12,
                       streak=0.22)

    # small bright accents: the neon tube round the marquee and the pilot lamps.
    # Baked into its own `<pid>_trim_glow` material at 3.0 so the game can run it hot
    # without the big lightbox coming with it (environment.md #1d).
    m_trim = weathered(f'{pid}_trim_src', color=cfg['trim'], roughness=0.20, metallic=0.0,
                       wear_color=(0.55, 0.53, 0.50), wear=0.06, wear_rough=0.5, wear_metal=0.0,
                       rust=0.0, grime=0.28, grime_color=(0.045, 0.045, 0.045),
                       dust=0.05, variation=0.05, scale=3.0, seed=sd + 101,
                       bump=0.18, dent=0.05, scratch=0.30, ao_dist=0.03, speckle=0.10)

    solid, glow, trim = [], [], []

    def S(ob, mat):
        assign(ob, mat); solid.append(ob); return ob

    def G(ob):
        assign(ob, m_sign); glow.append(ob); return ob

    def T(ob):
        assign(ob, m_trim); trim.append(ob); return ob

    # ------------------------------------------------------------- carcass ----
    S(loft('cab', cabinet_rings(), cap_bottom=True, cap_top=True), m_body)

    for sx in (-1, 1):
        for sy in (-1, 1):
            S(cyl(f'foot{sx}{sy}', r=0.034, h=0.080, loc=(sx * 0.385, sy * 0.265, 0.040),
                  verts=10, r_top=0.027), m_chrome)

    if pid == 'quickrevive':      # white upper half
        rings = cabinet_rings()
        up = [[(x * 1.005, y * 1.005, z) for x, y, z in ring] for ring in rings if ring[0][2] >= 1.30]
        top = [[(x * 1.005, y * 1.005, z) for x, y, z in rounded_rect(HW, HD, CR, 4, 1.30)]] + up
        S(loft('cab_upper', top, cap_bottom=False, cap_top=True), m_body2)

    S(band('band_base', 0.082, 0.126, out=0.010), m_chrome)
    S(band('band_low', 0.545, 0.600, out=0.014), m_chrome)
    S(band('band_high', 1.406, 1.458, out=0.014), m_chrome)
    S(band('band_shoulder', 1.565, 1.605, out=0.010, taper=0.003), m_chrome)

    # ------------------------------------------------------------ side panel ----
    for sx in (-1, 1):
        S(rbox(f'sideframe{sx}', (0.013, 0.545, 0.760), (sx * (HW + 0.001), 0.005, 1.010),
               radius=0.009, seg=2), m_body2)
        S(rbox(f'sidepanel{sx}', (0.013, 0.470, 0.680), (sx * (HW + 0.006), 0.005, 1.010),
               radius=0.010, seg=2), m_panel)
        for p in slats(f'slat{sx}', 0.009, 0.20, 0.02, 0.33, x=sx * (HW + 0.005), n=5, depth=0.26):
            S(p, m_dark)
        # bottle opener - period detail
        S(rbox(f'opener{sx}', (0.014, 0.055, 0.090), (sx * (HW + 0.007), -0.230, 0.660),
               radius=0.006, seg=1), m_chrome)
        S(rbox(f'openerslot{sx}', (0.012, 0.028, 0.026), (sx * (HW + 0.014), -0.230, 0.678),
               radius=0.002, seg=1), m_dark)
        S(cyl(f'opencap{sx}', r=0.017, h=0.010, loc=(sx * (HW + 0.010), -0.230, 0.622),
              verts=10, rot=(0, D2R(90), 0)), m_gold)

    # ------------------------------------------------------------ kick plate ----
    S(rbox('kick', (0.88, 0.018, 0.100), (0, FY - 0.006, 0.155), radius=0.005, seg=1), m_chrome)

    # --------------------------------------------------------- bottle outlet ----
    S(rbox('disp_recess', (0.52, 0.010, 0.250), (0.0, FY - 0.005, 0.372), radius=0.004, seg=1),
      m_dark)
    S(rbox('disp_back', (0.46, 0.010, 0.200), (0.0, FY + 0.006, 0.386), radius=0.003, seg=1),
      m_rubber)
    for nm, sz, lc in (
            ('disp_t', (0.60, 0.040, 0.038), (0.0, FY - 0.022, 0.513)),
            ('disp_b', (0.60, 0.040, 0.038), (0.0, FY - 0.022, 0.231)),
            ('disp_l', (0.038, 0.040, 0.320), (-0.281, FY - 0.022, 0.372)),
            ('disp_r', (0.038, 0.040, 0.320), (0.281, FY - 0.022, 0.372))):
        S(rbox(nm, sz, lc, radius=0.005, seg=2), m_chrome)
    # flap hinged at the top, hanging ajar so the dark opening shows above it
    S(rbox('disp_flap', (0.50, 0.014, 0.135), (0.0, FY - 0.036, 0.300), radius=0.004, seg=1,
           rot=(D2R(-17), 0, 0)), m_body2)
    S(rbox('disp_flaplip', (0.50, 0.018, 0.022), (0.0, FY - 0.056, 0.240), radius=0.004, seg=1,
           rot=(D2R(-17), 0, 0)), m_chrome)
    S(rbox('disp_lip', (0.52, 0.016, 0.014), (0.0, FY - 0.048, 0.243), radius=0.003, seg=1),
      m_rubber)

    # ------------------------------------------------------------ coin return ----
    S(rbox('cr_cup', (0.100, 0.030, 0.072), (0.355, FY - 0.016, 0.700), radius=0.009, seg=2),
      m_chrome)
    S(rbox('cr_hole', (0.074, 0.014, 0.044), (0.355, FY - 0.030, 0.696), radius=0.003, seg=1),
      m_dark)
    S(cyl('cr_lever', r=0.020, h=0.018, loc=(0.355, FY - 0.028, 0.772), verts=10,
          rot=(D2R(90), 0, 0)), m_chrome)

    # --------------------------------------------------------------- big door ----
    DZ0, DZ1 = 0.640, 1.378
    dzc = (DZ0 + DZ1) / 2
    S(rbox('door', (0.905, 0.018, DZ1 - DZ0), (0, FY - 0.007, dzc), radius=0.010, seg=2), m_body2)
    S(rbox('door_panel', (0.800, 0.014, DZ1 - DZ0 - 0.10), (0, FY - 0.013, dzc),
           radius=0.007, seg=2), m_panel)
    for nm, sz, lc in (
            ('dtrim_t', (0.865, 0.026, 0.028), (0, FY - 0.019, DZ1 - 0.028)),
            ('dtrim_b', (0.865, 0.026, 0.028), (0, FY - 0.019, DZ0 + 0.028)),
            ('dtrim_l', (0.028, 0.026, DZ1 - DZ0), (-0.419, FY - 0.019, dzc)),
            ('dtrim_r', (0.028, 0.026, DZ1 - DZ0), (0.419, FY - 0.019, dzc))):
        S(rbox(nm, sz, lc, radius=0.005, seg=1), m_chrome)
    S(rbox('handle', (0.026, 0.042, 0.200), (0.392, FY - 0.038, 1.040), radius=0.009, seg=2),
      m_chrome)
    for hz in (0.955, 1.125):
        S(rbox(f'hbrk{hz}', (0.026, 0.026, 0.028), (0.392, FY - 0.024, hz), radius=0.003, seg=1),
          m_chrome)

    # ---- door graphic ------------------------------------------------------
    GY = FY - 0.021
    S(ellipse('medal', 0.295, 0.232, 0.011, (-0.075, GY, 1.135), bevel=0.005), m_gold)
    S(ellipse('medal2', 0.268, 0.207, 0.013, (-0.075, GY - 0.0065, 1.135), bevel=0.004), m_panel)
    S(txt('name1', cfg['title'], FONT, 0.118, (-0.075, GY - 0.017, 1.192)), m_letter)
    S(txt('name2', cfg['title2'], FONT, 0.118, (-0.075, GY - 0.017, 1.068)), m_letter)
    S(text_mesh('tagline', cfg['tag'], font=FONT_ARIALBD, size=0.054,
                loc=(-0.075, GY - 0.012, 0.876), extrude=0.005, bev=0.0014,
                res=2, bres=1, spacing=1.22), m_dark)
    S(bottle('bottle_relief', 0.375, (0.300, GY - 0.005, 0.795)), m_gold)
    S(ellipse('price_disc', 0.098, 0.070, 0.010, (0.300, GY, 1.290), bevel=0.004), m_gold)
    S(txt('price', cfg['price'], FONT, 0.062, (0.300, GY - 0.013, 1.290), extrude=0.005,
          bev=0.0015), m_letter)


    # ---- hardware: screws, keyhole, maker's plate -------------------------
    def screw(nm, loc, r=0.0075):
        ob = cyl(nm, r=r, h=0.006, loc=loc, verts=8, rot=(D2R(90), 0, 0), r_top=r * 0.9)
        return ob
    for sx in (-0.398, 0.398):
        for sz in (DZ0 + 0.028, DZ1 - 0.028, dzc):
            S(screw(f'scr{sx}{sz:.2f}', (sx, FY - 0.033, sz)), m_chrome)
    for sx in (-0.30, 0.0, 0.30):
        S(screw(f'scrt{sx}', (sx, FY - 0.033, DZ1 - 0.028)), m_chrome)
        S(screw(f'scrb{sx}', (sx, FY - 0.033, DZ0 + 0.028)), m_chrome)
    # keyhole
    S(cyl('keyplate', r=0.028, h=0.010, loc=(0.392, FY - 0.026, 0.855), verts=14,
          rot=(D2R(90), 0, 0)), m_chrome)
    S(cyl('keyhole', r=0.011, h=0.008, loc=(0.392, FY - 0.033, 0.855), verts=10,
          rot=(D2R(90), 0, 0)), m_dark)
    # maker's plate
    S(rbox('maker', (0.135, 0.008, 0.042), (0.300, FY - 0.019, 0.585), radius=0.003, seg=1),
      m_gold)
    S(txt('maker_txt', 'VENDO-MATIC', FONT_ARIALBD, 0.016, (0.300, FY - 0.026, 0.585),
          extrude=0.002, bev=0.0006, spacing=1.1), m_dark)
    # side medallion
    for sx in (-1, 1):
        S(cyl(f'sidemed{sx}', r=0.115, h=0.012, loc=(sx * (HW + 0.012), 0.005, 1.180),
              verts=18, rot=(0, D2R(90), 0)), m_gold)
        S(cyl(f'sidemed2{sx}', r=0.096, h=0.014, loc=(sx * (HW + 0.016), 0.005, 1.180),
              verts=18, rot=(0, D2R(90), 0)), m_letter)
        S(text_mesh(f'sideinit{sx}', cfg['title'][0], font=FONT_ARIALBD, size=0.115,
                    loc=(sx * (HW + 0.025), 0.005, 1.180),
                    rot=(D2R(90), 0, D2R(90 * sx)), extrude=0.005, bev=0.0016,
                    res=1, bres=0), m_panel)

    # ------------------------------------------------------------ control plate ----
    CZ = 1.500
    S(rbox('ctrl', (0.86, 0.028, 0.100), (0, FY - 0.013, CZ), radius=0.008, seg=2), m_chrome)
    S(rbox('coin_esc', (0.098, 0.020, 0.068), (0.300, FY - 0.028, CZ), radius=0.005, seg=1),
      m_gold)
    S(rbox('coin_slot', (0.048, 0.016, 0.009), (0.300, FY - 0.039, CZ + 0.012), radius=0.002,
           seg=1), m_dark)
    S(rbox('coin_lbl', (0.058, 0.010, 0.016), (0.300, FY - 0.039, CZ - 0.024),
           radius=0.002, seg=1), m_letter)
    for i, bx in enumerate((-0.320, -0.200, -0.080, 0.040)):
        S(cyl(f'btn{i}', r=0.032, h=0.028, loc=(bx, FY - 0.032, CZ), verts=12,
              rot=(D2R(90), 0, 0), r_top=0.028), m_gold)
        S(cyl(f'btn{i}_f', r=0.022, h=0.016, loc=(bx, FY - 0.044, CZ), verts=12,
              rot=(D2R(90), 0, 0), r_top=0.020), m_letter if i % 2 else m_panel)
    # two pilot lamps in brass bezels - the machine's only tiny hot emissives
    for i, px in enumerate((0.140, 0.213)):
        S(cyl(f'pilot_bz{i}', r=0.023, h=0.022, loc=(px, FY - 0.025, CZ), verts=12,
              rot=(D2R(90), 0, 0), r_top=0.020), m_gold)
        T(uvsphere(f'pilot{i}', r=0.0145, loc=(px, FY - 0.034, CZ), segs=12, rings=7,
                   scale=(1.0, 0.85, 1.0)))

    # ---------------------------------------------------------------- back ----
    S(rbox('back_panel', (0.84, 0.014, 1.02), (0, HD + 0.002, 0.80), radius=0.007, seg=1), m_body2)
    for p in slats('vent', 0.66, 0.40, HD + 0.009, 0.44, n=8, depth=0.014):
        S(p, m_dark)
    S(cyl('conduit', r=0.020, h=0.85, loc=(0.36, HD + 0.026, 1.00), verts=8), m_chrome)
    for zz in (0.68, 1.06, 1.36):
        S(cyl(f'clamp{zz}', r=0.028, h=0.024, loc=(0.36, HD + 0.026, zz), verts=8), m_gold)

    # --------------------------------------------------------------- crown ----
    crown = cfg['crown']
    CZ0, CZ1 = CROWN_Z0, 2.200
    zc = (CZ0 + CZ1) / 2

    if crown == 'box':
        rings = [rounded_rect(0.420, 0.215, 0.050, 4, CZ0 - 0.06),
                 rounded_rect(0.440, 0.232, 0.055, 4, CZ0),
                 rounded_rect(0.440, 0.232, 0.055, 4, CZ1 - 0.085),
                 rounded_rect(0.410, 0.208, 0.085, 4, CZ1 - 0.028),
                 rounded_rect(0.330, 0.145, 0.085, 4, CZ1)]
        S(loft('crown', rings, cap_top=True, cap_bottom=True), m_body2)
        for sy in (-1, 1):
            G(rbox(f'sign{sy}', (0.735, 0.014, 0.300), (0, sy * 0.236, zc - 0.028),
                   radius=0.006, seg=2))
            for nm, sz, lc in (
                    (f'ct{sy}', (0.80, 0.026, 0.030), (0, sy * 0.240, zc + 0.140)),
                    (f'cb{sy}', (0.80, 0.026, 0.030), (0, sy * 0.240, zc - 0.196)),
                    (f'cl{sy}', (0.030, 0.026, 0.365), (-0.385, sy * 0.240, zc - 0.028)),
                    (f'cr{sy}', (0.030, 0.026, 0.365), (0.385, sy * 0.240, zc - 0.028))):
                S(rbox(nm, sz, lc, radius=0.005, seg=1), m_chrome)
            for nb in neon_frame(f'neon{sy}', 0.352, 0.140, (0, sy * 0.250, zc - 0.028)):
                T(nb)
        S(txt('sgn1', cfg['title'], FONT, 0.120, (0, -0.250, zc + 0.045), extrude=0.007),
          m_signletter)
        S(txt('sgn2', cfg['title2'], FONT, 0.120, (0, -0.250, zc - 0.100), extrude=0.007),
          m_signletter)

    elif crown == 'slant':
        tilt = D2R(16)
        S(rbox('crown_base', (0.86, 0.44, 0.085), (0, 0, CZ0 - 0.020), radius=0.018, seg=2),
          m_body2)
        centre = Vector((0.0, -0.010, zc + 0.030))
        R = Matrix.Rotation(tilt, 4, 'X')

        def place(dx, dy, dz):
            """dx across the sign, dy out of it (-ve = toward the player), dz up it."""
            return tuple(centre + (R @ Vector((dx, dy, dz))))

        S(rbox('crown', (0.855, 0.115, 0.410), tuple(centre), radius=0.032, seg=3,
               rot=(tilt, 0, 0)), m_body2)
        for sy in (-1, 1):
            G(rbox(f'sign{sy}', (0.755, 0.012, 0.325), place(0, sy * 0.062, 0),
                   radius=0.005, seg=2, rot=(tilt, 0, 0)))
            for nm, sz, dx, dz in ((f'ct{sy}', (0.815, 0.024, 0.030), 0, 0.176),
                                   (f'cb{sy}', (0.815, 0.024, 0.030), 0, -0.176),
                                   (f'cl{sy}', (0.030, 0.024, 0.385), -0.400, 0),
                                   (f'cr{sy}', (0.030, 0.024, 0.385), 0.400, 0)):
                S(rbox(nm, sz, place(dx, sy * 0.066, dz), radius=0.004, seg=1,
                       rot=(tilt, 0, 0)), m_chrome)
            for nb in neon_frame(f'neon{sy}', 0.368, 0.152, place(0, sy * 0.072, 0),
                                 tilt=tilt):
                T(nb)
        S(txt('sgn1', cfg['title'], FONT, 0.120, place(0, -0.074, 0.074),
              rot=(D2R(90) + tilt, 0, 0), extrude=0.007), m_signletter)
        S(txt('sgn2', cfg['title2'], FONT, 0.120, place(0, -0.074, -0.078),
              rot=(D2R(90) + tilt, 0, 0), extrude=0.007), m_signletter)

    elif crown == 'disc':
        dz = 1.985
        S(rbox('crown_neck', (0.300, 0.220, 0.150), (0, 0, CZ0 - 0.020), radius=0.026, seg=2),
          m_body2)
        S(cyl('crown_disc', r=0.302, h=0.105, loc=(0, 0, dz), verts=18, rot=(D2R(90), 0, 0),
              bevel=0.016), m_chrome)
        for sy in (-1, 1):
            G(cyl(f'sign{sy}', r=0.262, h=0.012, loc=(0, sy * 0.055, dz), verts=20,
                  rot=(D2R(90), 0, 0)))
            S(tube(f'ring{sy}', r_out=0.298, r_in=0.260, h=0.018, loc=(0, sy * 0.057, dz),
                   verts=20, rot=(D2R(90), 0, 0)), m_chrome)
            T(tube(f'neon{sy}', r_out=0.252, r_in=0.236, h=0.016, loc=(0, sy * 0.066, dz),
                   verts=26, rot=(D2R(90), 0, 0)))
        S(txt('sgn1', cfg['title'], FONT, 0.098, (0, -0.068, dz + 0.062), extrude=0.007),
          m_signletter)
        S(txt('sgn2', cfg['title2'], FONT, 0.085, (0, -0.068, dz - 0.062), extrude=0.007),
          m_signletter)
        S(rbox('crown_bar', (0.560, 0.095, 0.045), (0, 0, CZ0 + 0.105), radius=0.010, seg=1),
          m_chrome)

    else:  # 'arch'
        steps = [(CZ0 - 0.06, 0.470, 0.200, 0.040), (CZ0, 0.487, 0.216, 0.050),
                 (1.980, 0.487, 0.216, 0.050), (2.085, 0.470, 0.206, 0.100),
                 (2.155, 0.415, 0.180, 0.140), (CZ1, 0.300, 0.125, 0.120)]
        S(loft('crown', [rounded_rect(hw, hd, r, 4, z) for z, hw, hd, r in steps],
               cap_top=True, cap_bottom=True), m_body2)
        dz = 1.945
        for sy in (-1, 1):
            G(rbox(f'sign{sy}', (0.810, 0.014, 0.270), (0, sy * 0.220, dz), radius=0.007, seg=2))
            for nm, sz, lc in (
                    (f'at{sy}', (0.880, 0.026, 0.030), (0, sy * 0.224, dz + 0.150)),
                    (f'ab{sy}', (0.880, 0.026, 0.030), (0, sy * 0.224, dz - 0.150)),
                    (f'al{sy}', (0.030, 0.026, 0.330), (-0.425, sy * 0.224, dz)),
                    (f'ar{sy}', (0.030, 0.026, 0.330), (0.425, sy * 0.224, dz))):
                S(rbox(nm, sz, lc, radius=0.005, seg=1), m_gold)
            for nb in neon_frame(f'neon{sy}', 0.392, 0.128, (0, sy * 0.232, dz)):
                T(nb)
        S(txt('sgn1', cfg['title'], FONT, 0.112, (0, -0.234, dz + 0.062), extrude=0.007),
          m_signletter)
        S(txt('sgn2', cfg['title2'], FONT, 0.112, (0, -0.234, dz - 0.066), extrude=0.007),
          m_signletter)
        # two beer-tap levers flanking the control plate
        for sx in (-0.398, 0.398):
            S(rbox(f'tapbase{sx}', (0.058, 0.030, 0.058), (sx, FY - 0.026, CZ),
                   radius=0.008, seg=2), m_chrome)
            S(cyl(f'tap{sx}', r=0.017, h=0.135, loc=(sx, FY - 0.086, CZ + 0.030), verts=10,
                  rot=(D2R(64), 0, 0)), m_gold)
            S(lathe(f'tapknob{sx}', [(0.0, 0.0), (0.030, 0.010), (0.037, 0.038),
                                     (0.030, 0.068), (0.0, 0.078)], verts=14,
                    loc=(sx, FY - 0.134, CZ + 0.062), rot=(D2R(-116), 0, 0)), m_gold)

    # ----------------------------------------------------------------- bake ----
    apply_mods(solid + glow + trim)
    print('  pre-bake tris:', tri_count())
    heavy = sorted(((tri_count([o]), o.name) for o in solid + glow + trim), reverse=True)[:10]
    print('  heaviest:', ', '.join(f'{n}={t}' for t, n in heavy))
    # two bake groups: the front fascia gets its own, denser texture set
    DETAIL = ('door', 'dtrim', 'medal', 'name1', 'name2', 'tagline', 'bottle_relief',
              'price', 'ctrl', 'coin_', 'btn', 'disp_', 'cr_', 'handle', 'hbrk', 'kick',
              'sgn1', 'sgn2')
    detail = [o for o in solid if o.name.startswith(DETAIL)]
    shell = [o for o in solid if o not in detail]
    bake_pbr(shell, f'{pid}_shell', size=1536, samples=4, normal_samples=6, margin=0.0028)
    bake_pbr(detail, f'{pid}_face', size=1536, samples=4, normal_samples=6, margin=0.0028)
    # the marquee is a backlit panel: modest, printed artwork must stay readable
    bake_pbr(glow, f'{pid}_sign', size=512, samples=4, normal_samples=6, margin=0.006,
             emissive=True, emission_strength=1.2, mat_name=f'{pid}_sign_glow')
    # the neon tube and the pilot lamps are the hot accents
    bake_pbr(trim, f'{pid}_trim', size=256, samples=4, normal_samples=6, margin=0.012,
             emissive=True, emission_strength=3.0, mat_name=f'{pid}_trim_glow')

    machine = join('machine', solid + trim)
    set_origin(machine, (0, 0, 0))
    sign = join('sign', glow)
    set_origin(sign, (0, 0, 0))

    print('  tris:', tri_count())
    # close-up frames the control plate up through the marquee, so both emissive
    # bands (pilot lamps + neon frame + sign panel) are in one shot
    shots(f'perk_{pid}', target=(0, 0, 1.10), hero=(4.3, 30, 4), close=(1.45, 14, 4),
          close_target=(0.0, -0.18, 1.80), samples=30, res=(560, 740), world=0.5)
    export_prop(f'perk_{pid}.glb', roots=[machine, sign], quality=78)


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    for pid in (args or list(PERKS)):
        print('=== building', pid)
        build_machine(pid, PERKS[pid])


main()
