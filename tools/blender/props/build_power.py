"""power_switch.glb - wall-mounted 1950s mains disconnect panel.

Origin: centre of the BACK face (sits flat on a wall), front = -Y.

Enclosure 0.600 w x 0.214 d x 0.900 h - that is the part that matters for wall fit.
Full bounds 0.617 x 0.335 x 0.975: the thrown handle and the jaw contacts stand 12 cm off
the door (unavoidable for a lever that swings), the conduit stubs add ~4 cm top and bottom
and the flexible drop on the left flank adds ~1.7 cm.

Objects
  panel  - the cabinet and everything fixed to it (includes the emissive `power_glow` lamps)
  lever  - the knife-switch handle.  Its origin is the pivot, its object transform is
           identity, and it is modelled in the OFF position (hanging down, 12 deg out from
           the wall).  Rotating it about its LOCAL X by -2.4 rad throws it ON: the blades
           swing up into the spring jaws and stop 30.5 deg the other side of vertical.
           Nothing collides anywhere in that travel - `sweep_clearance()` checks every
           4 degrees of it at build time and prints the worst clearance.

Indicator lamps use the material `power_glow`.
"""
import sys, os, math, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib_power import *

random.seed(33)

# The RTX is shared with another build agent; OptiX context creation fails when it is busy,
# so this asset bakes *and* renders on the CPU with OIDN - slower, but it never fights for
# the GPU and never dies half way through a bake.
import common as _common_mod
import lib_props as _lp


def _cpu_device(samples=64):
    scn = bpy.context.scene
    scn.render.engine = 'CYCLES'
    scn.cycles.device = 'CPU'
    scn.cycles.samples = samples
    scn.cycles.use_denoising = True
    try:
        scn.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    return scn


_lp._common_setup_gpu = _cpu_device
_lp._setup_device = _cpu_device
_common_mod.setup_gpu = _cpu_device

# ---------------------------------------------------------------------------- layout ---
W, H = 0.600, 0.900          # backplate footprint on the wall
CW, CH = 0.505, 0.800        # steel case
CY0, CY1 = -0.020, -0.170    # case back / front in Y
DOOR_Y = -0.185              # door slab centre
DFY = -0.200                 # door slab front
FY = -0.214                  # raised door panel front - the working face
BASE_Y = -0.228              # front of the switch's insulating base plate

PIVOT = (0.0, -0.2400, -0.075)
ON_DELTA = -2.4                          # what the game applies, about the lever local X
OFF_TILT = -math.radians(12.0)           # modelled OFF pose
ON_TILT = OFF_TILT + ON_DELTA            # -2.609 rad -> 30.5 deg past vertical

M_OFF = lever_frame(PIVOT, OFF_TILT)
M_ON = lever_frame(PIVOT, ON_TILT)

BLADE_X = 0.058              # blade centres in X
BLADE_L = 0.115              # pivot -> blade tip
POST_X = 0.116               # stand-off insulator centres
JAW_Z = -0.134               # lever-local Z of the jaw bar (just past the blade tips)
OUT = D2R(90)                # rotation that points a +Z primitive along -Y (out of the wall)


def build():
    props_scene()

    # ------------------------------------------------------------------- materials ----
    # NOTE: noise scales are deliberately 4-6x what the 2 m props use; this thing is only
    # 0.6 m across, so lib_props' default grain would read as a flat colour.
    steel = enamel('ps_steel', (0.050, 0.056, 0.048), rough=0.38, wear=0.44, rust=0.60,
                   grime=0.80, dent=0.9, scale=6.0, seed=1.0, variation=0.17, dust=0.10,
                   streak=0.85)
    steel2 = enamel('ps_steel2', (0.082, 0.089, 0.078), rough=0.40, wear=0.42, rust=0.56,
                    grime=0.78, dent=0.85, scale=6.5, seed=4.0, variation=0.17, dust=0.10,
                    streak=0.80)
    galv = plated('ps_galv', tint=(0.50, 0.51, 0.52), rough=0.34, grime=0.60, scratch=1.0,
                  pit=1.0, scale=10.0, seed=7.0)
    rawsteel = weathered('ps_raw', color=(0.098, 0.094, 0.090), roughness=0.46, metallic=1.0,
                         wear_color=(0.42, 0.41, 0.40), wear=0.34, wear_rough=0.28,
                         rust=0.85, rust_color=(0.250, 0.108, 0.042), grime=0.72, dust=0.10,
                         variation=0.12, scale=8.0, seed=9.0, bump=0.7, dent=0.6,
                         scratch=1.0, ao_dist=0.030, speckle=0.05, streak=0.7)
    copper = weathered('ps_copper', color=(0.360, 0.140, 0.055), roughness=0.34, metallic=1.0,
                       wear_color=(0.55, 0.31, 0.15), wear=0.38, wear_rough=0.24,
                       rust=0.50, rust_color=(0.070, 0.180, 0.140), grime=0.58, dust=0.08,
                       variation=0.12, scale=13.0, seed=11.0, bump=0.5, dent=0.3,
                       scratch=0.9, ao_dist=0.022, speckle=0.05, streak=0.4)
    brassm = weathered('ps_brass', color=(0.440, 0.310, 0.078), roughness=0.30, metallic=1.0,
                       wear_color=(0.62, 0.48, 0.21), wear=0.32, wear_rough=0.22,
                       rust=0.26, rust_color=(0.10, 0.155, 0.095), grime=0.58, dust=0.08,
                       variation=0.10, scale=12.0, seed=13.0, bump=0.5, dent=0.35,
                       scratch=0.9, ao_dist=0.022, speckle=0.05, streak=0.5)
    # switchboard slate: deliberately much lighter than the door so the switchgear,
    # the copper and the red handle all read against it from across a room
    slate = weathered('ps_slate', color=(0.235, 0.228, 0.212), roughness=0.44, metallic=0.0,
                      wear_color=(0.36, 0.35, 0.33), wear=0.22, wear_rough=0.5, wear_metal=0.0,
                      rust=0.12, rust_color=(0.18, 0.09, 0.038), grime=0.60, dust=0.16,
                      variation=0.24, scale=9.0, seed=41.0, bump=0.35, dent=0.3, scratch=0.8,
                      ao_dist=0.026, speckle=0.06, streak=0.75)
    bakelite = weathered('ps_bakelite', color=(0.040, 0.027, 0.020), roughness=0.24,
                         metallic=0.0, wear_color=(0.22, 0.17, 0.14), wear=0.32,
                         wear_rough=0.6, wear_metal=0.0, rust=0.0, grime=0.52, dust=0.09,
                         variation=0.12, scale=11.0, seed=15.0, bump=0.4, dent=0.25,
                         scratch=0.7, ao_dist=0.026, speckle=0.06, streak=0.35)
    porcelain = weathered('ps_porc', color=(0.300, 0.232, 0.162), roughness=0.15, metallic=0.0,
                          wear_color=(0.42, 0.35, 0.27), wear=0.20, wear_rough=0.5,
                          wear_metal=0.0, rust=0.0, grime=0.60, dust=0.18, variation=0.10,
                          scale=14.0, seed=17.0, bump=0.3, ao_dist=0.020, speckle=0.05,
                          streak=0.45)
    red_h = enamel('ps_handle', (0.360, 0.034, 0.020), rough=0.26, wear=0.40, rust=0.12,
                   grime=0.42, dent=0.3, scale=14.0, seed=19.0, variation=0.16, dust=0.05,
                   streak=0.22, ao=0.018)
    # forged arm: near-black gunmetal so the red knob is the brightest thing on the panel
    gunmetal = weathered('ps_gun', color=(0.038, 0.037, 0.036), roughness=0.44, metallic=1.0,
                         wear_color=(0.34, 0.33, 0.32), wear=0.40, wear_rough=0.26,
                         rust=0.55, rust_color=(0.220, 0.095, 0.038), grime=0.60, dust=0.06,
                         variation=0.10, scale=12.0, seed=43.0, bump=0.6, dent=0.4,
                         scratch=1.0, ao_dist=0.022, speckle=0.05, streak=0.4)
    red_pl = enamel('ps_red', (0.320, 0.030, 0.021), rough=0.34, wear=0.42, rust=0.34,
                    grime=0.60, dent=0.3, scale=9.0, seed=21.0, variation=0.14, dust=0.08,
                    streak=0.5, ao=0.022)
    cream = enamel('ps_cream', (0.580, 0.540, 0.440), rough=0.42, wear=0.36, rust=0.28,
                   grime=0.66, dent=0.3, scale=9.0, seed=23.0, variation=0.12, dust=0.12,
                   streak=0.85, ao=0.022)
    white = enamel('ps_white', (0.760, 0.740, 0.690), rough=0.40, wear=0.30, rust=0.08,
                   grime=0.36, dent=0.2, scale=11.0, seed=25.0, variation=0.09, dust=0.10,
                   streak=0.25, ao=0.014)
    hazard = enamel('ps_hazard', (0.470, 0.300, 0.022), rough=0.42, wear=0.50, rust=0.34,
                    grime=0.68, dent=0.3, scale=9.0, seed=27.0, variation=0.14, dust=0.08,
                    streak=0.6, ao=0.020)
    dark = weathered('ps_dark', color=(0.013, 0.013, 0.012), roughness=0.60, metallic=0.0,
                     wear=0.14, rust=0.0, grime=0.5, dust=0.05, variation=0.06, scale=10.0,
                     seed=29.0, bump=0.4, ao_dist=0.018, speckle=0.05)
    rubber = weathered('ps_rubber', color=(0.020, 0.019, 0.018), roughness=0.85, metallic=0.0,
                       wear=0.12, rust=0.0, grime=0.55, dust=0.08, variation=0.09, scale=14.0,
                       seed=31.0, bump=0.6, ao_dist=0.020, speckle=0.06)
    lamp_r = weathered('ps_lamp_r', color=(0.95, 0.15, 0.05), roughness=0.20, metallic=0.0,
                       wear=0.06, rust=0.0, grime=0.28, grime_color=(0.08, 0.04, 0.03),
                       dust=0.24, variation=0.08, scale=18.0, seed=35.0, bump=0.2,
                       ao_dist=0.014, speckle=0.05)
    lamp_g = weathered('ps_lamp_g', color=(0.14, 0.82, 0.22), roughness=0.20, metallic=0.0,
                       wear=0.06, rust=0.0, grime=0.28, grime_color=(0.05, 0.08, 0.05),
                       dust=0.24, variation=0.08, scale=18.0, seed=37.0, bump=0.2,
                       ao_dist=0.014, speckle=0.05)

    solid, glow, lever_parts, sign = [], [], [], []

    def S(ob, mat):
        assign(ob, mat); solid.append(ob); return ob

    def P(ob, mat):
        """Placard part - baked on its own sheet so the stencil stays crisp."""
        assign(ob, mat); sign.append(ob); return ob

    def G(ob, mat):
        assign(ob, mat); glow.append(ob); return ob

    def L(ob, mat):
        """Lever part, authored in the lever's local frame."""
        bake_xf(ob, M_OFF)
        assign(ob, mat); lever_parts.append(ob); return ob

    def F(ob, mat):
        """Fixed part authored in the lever's ON frame (the jaw contacts)."""
        bake_xf(ob, M_ON)
        assign(ob, mat); solid.append(ob); return ob

    # ----------------------------------------------------------------- the cabinet ----
    S(rbox('backplate', (W, 0.020, H), (0, -0.010, 0), radius=0.005, seg=2), steel2)
    S(rbox('case', (CW, CY0 - CY1, CH), (0, (CY0 + CY1) / 2, 0), radius=0.012, seg=2), steel)
    S(rbox('cap_t', (CW + 0.026, 0.172, 0.018), (0, -0.094, CH / 2 + 0.007), radius=0.004,
           seg=2), steel2)
    S(rbox('cap_b', (CW + 0.026, 0.172, 0.018), (0, -0.094, -CH / 2 - 0.007), radius=0.004,
           seg=2), steel2)
    for sx in (-1, 1):
        for sz in (-1, 1):
            S(bolt(f'mb{sx}{sz}', r=0.015, h=0.011, loc=(sx * 0.272, -0.020, sz * 0.412),
                   rot=(OUT, 0, 0), washer=True), rawsteel)
    for sx in (-1, 1):
        for i in range(4):
            S(bolt(f'sr{sx}{i}', r=0.009, h=0.006,
                   loc=(sx * (CW / 2), -0.095, -0.30 + i * 0.20),
                   rot=(0, D2R(90 * sx), 0)), rawsteel)

    # ------------------------------------------------------------------- the door ----
    S(rbox('door', (0.496, 0.030, 0.792), (0, DOOR_Y, 0), radius=0.013, seg=3), steel)
    S(rbox('door_panel', (0.404, 0.014, 0.700), (0, FY + 0.007, 0), radius=0.006, seg=2),
      steel)
    for sx in (-1, 1):
        for sz in (-1, 1):
            S(bolt(f'ds{sx}{sz}', r=0.009, h=0.006, loc=(sx * 0.222, DFY, sz * 0.362),
                   rot=(OUT, 0, 0), washer=True), galv)
    # hinges on the left edge
    for sz in (-1, 1):
        zc = sz * 0.262
        S(rbox(f'hl{sz}', (0.052, 0.030, 0.086), (-0.232, DOOR_Y, zc), radius=0.004, seg=2),
          rawsteel)
        S(rbox(f'hb{sz}', (0.048, 0.032, 0.086), (-0.256, -0.150, zc), radius=0.004, seg=2),
          rawsteel)
        S(cyl(f'hk{sz}', r=0.013, h=0.092, loc=(-0.262, -0.186, zc), verts=12), rawsteel)
        S(cyl(f'hp{sz}', r=0.006, h=0.114, loc=(-0.262, -0.186, zc), verts=8), galv)
        for k in (-1, 1):
            S(bolt(f'hbo{sz}{k}', r=0.007, h=0.005, loc=(-0.232, DFY, zc + k * 0.028),
                   rot=(OUT, 0, 0)), galv)
    # draw latches on the right edge
    for sz in (-1, 1):
        zc = sz * 0.238
        S(rbox(f'lt{sz}', (0.044, 0.026, 0.064), (0.244, -0.160, zc), radius=0.004, seg=2),
          rawsteel)
        S(rbox(f'lk{sz}', (0.030, 0.034, 0.048), (0.252, -0.196, zc), radius=0.005, seg=2),
          galv)
        S(rbox(f'lh{sz}', (0.016, 0.014, 0.056), (0.252, -0.216, zc), radius=0.003, seg=1),
          galv)
    # hasp + padlock
    S(rbox('hasp', (0.070, 0.016, 0.044), (0.232, -0.206, 0.0), radius=0.004, seg=2), rawsteel)
    S(rbox('staple', (0.014, 0.020, 0.030), (0.252, -0.212, 0.0), radius=0.002, seg=1), galv)
    S(rbox('padlock', (0.036, 0.016, 0.044), (0.252, -0.230, -0.028), radius=0.006, seg=2),
      rawsteel)
    S(pipe_path('shackle', arc_path((0.252, -0.230, -0.006), 0.014, D2R(-10), D2R(190), 7),
                r=0.005, verts=6), galv)
    S(cyl('lock_key', r=0.006, h=0.008, loc=(0.252, -0.239, -0.036), verts=8, rot=(OUT, 0, 0)),
      brassm)

    # --------------------------------------------------------------- DANGER placard ----
    S(rbox('pl_frame', (0.400, 0.008, 0.124), (0, FY - 0.001, 0.292), radius=0.004, seg=1),
      rawsteel)
    P(rbox('pl_red', (0.384, 0.010, 0.054), (0, FY - 0.006, 0.320), radius=0.003, seg=1),
      red_pl)
    P(rbox('pl_cream', (0.384, 0.010, 0.054), (0, FY - 0.006, 0.264), radius=0.003, seg=1),
      cream)
    P(text_mesh('t_danger', 'DANGER', font=FONT_STENCIL, size=0.042, extrude=0.0032,
                bev=0.0, loc=(0, FY - 0.012, 0.320), res=1, bres=0, spacing=1.10), white)
    P(text_mesh('t_hv', 'HIGH VOLTAGE', font=FONT_STENCIL, size=0.029, extrude=0.0032,
                bev=0.0, loc=(0, FY - 0.012, 0.264), res=1, bres=0, spacing=1.02), dark)
    for sx in (-1, 1):
        S(bolt(f'plb{sx}', r=0.006, h=0.004, loc=(sx * 0.190, FY - 0.005, 0.292),
               rot=(OUT, 0, 0)), galv)

    # ------------------------------------------------------- ammeter + pilot lamps ----
    # the can is short and its dial sits PROUD of the front cap, otherwise the cylinder
    # cap hides the whole gauge
    MX, MZ = -0.140, 0.190
    S(cyl('m_can', r=0.048, h=0.042, loc=(MX, -0.205, MZ), verts=22, rot=(OUT, 0, 0)), rawsteel)
    S(cyl('m_face', r=0.045, h=0.008, loc=(MX, -0.230, MZ), verts=22, rot=(OUT, 0, 0)), cream)
    for i in range(9):
        a = D2R(-162 + i * 18)
        S(rbox(f'm_t{i}', (0.0028, 0.004, 0.011),
               (MX + math.cos(a) * 0.034, -0.2355, MZ + math.sin(a) * 0.034),
               radius=0.0006, seg=1, rot=(0, -a - D2R(90), 0)), dark)
    S(rbox('m_needle', (0.0032, 0.005, 0.040), (MX + 0.012, -0.2365, MZ + 0.013),
           radius=0.0008, seg=1, rot=(0, D2R(-32), 0)), red_pl)
    S(cyl('m_hub', r=0.007, h=0.010, loc=(MX, -0.237, MZ - 0.007), verts=10, rot=(OUT, 0, 0)),
      brassm)
    S(tube('m_ring', r_out=0.052, r_in=0.044, h=0.016, loc=(MX, -0.238, MZ), verts=22,
           rot=(OUT, 0, 0)), brassm)

    for i, (lx, mat) in enumerate(((0.086, lamp_r), (0.168, lamp_g))):
        S(cyl(f'lb{i}', r=0.030, h=0.030, loc=(lx, -0.213, MZ), verts=16, rot=(OUT, 0, 0),
              r_top=0.026), brassm)
        S(tube(f'lr{i}', r_out=0.031, r_in=0.023, h=0.012, loc=(lx, -0.228, MZ), verts=16,
               rot=(OUT, 0, 0)), brassm)
        G(uvsphere(f'lamp{i}', r=0.022, loc=(lx, -0.236, MZ), segs=14, rings=8,
                   scale=(1, 0.75, 1)), mat)

    # --------------------------------------------------------- knife-switch fixings ----
    S(rbox('sw_base', (0.286, 0.016, 0.424), (0, BASE_Y + 0.008, -0.090), radius=0.006, seg=2),
      slate)
    S(rbox('sw_lip', (0.302, 0.008, 0.440), (0, BASE_Y + 0.010, -0.090), radius=0.004, seg=1),
      rawsteel)
    for sx in (-1, 1):
        for zz in (-0.282, 0.100):
            S(bolt(f'sbb{sx}{zz}', r=0.008, h=0.005, loc=(sx * 0.128, BASE_Y, zz),
                   rot=(OUT, 0, 0), washer=True), galv)

    for sx in (-1, 1):
        # hinge end - short insulator + copper block carrying the blade pivot
        S(ribbed_insulator(f'ins_lo{sx}', length=0.016, r=0.026, ribs=1,
                           loc=(sx * POST_X, BASE_Y, PIVOT[2]), rot=(OUT, 0, 0), verts=12),
          porcelain)
        S(rbox(f'hinge_blk{sx}', (0.058, 0.020, 0.044), (sx * 0.090, PIVOT[1], PIVOT[2]),
               radius=0.004, seg=1), copper)
        S(bolt(f'hinge_bolt{sx}', r=0.009, h=0.007,
               loc=(sx * (POST_X - 0.002), PIVOT[1] - 0.010, PIVOT[2]), rot=(OUT, 0, 0),
               washer=True), galv)

        # jaw end - tall ribbed stand-off reaching the ON position of the blade tips
        jw = M_ON @ Vector((sx * POST_X, 0.0, JAW_Z))
        S(ribbed_insulator(f'ins_hi{sx}', length=abs(jw.y - BASE_Y) - 0.010, r=0.026, ribs=3,
                           loc=(sx * POST_X, BASE_Y, jw.z), rot=(OUT, 0, 0), verts=16),
          porcelain)
        F(rbox(f'jaw_bar{sx}', (0.070, 0.022, 0.030), (sx * 0.084, 0.0, JAW_Z),
               radius=0.004, seg=1), copper)
        for sy in (-1, 1):
            F(rbox(f'jaw{sx}{sy}', (0.036, 0.009, 0.056),
                   (sx * BLADE_X, sy * 0.0165, JAW_Z + 0.032), radius=0.002, seg=1), copper)
        # arch over the blade tip so each pole reads as a clamp, not a pair of tabs
        F(rbox(f'jaw_cap{sx}', (0.038, 0.050, 0.012), (sx * BLADE_X, 0.0, JAW_Z - 0.006),
               radius=0.003, seg=1), copper)
        F(bolt(f'jaw_bolt{sx}', r=0.010, h=0.008,
               loc=(sx * (POST_X - 0.002), -0.012, JAW_Z), rot=(OUT, 0, 0), washer=True), galv)

        # lower feed - insulated lead down the slate into a terminal block.  Deliberately
        # NOT copper: four bright copper bars either side of the blades read as noise.
        S(rbox(f'strap{sx}', (0.017, 0.015, 0.142), (sx * POST_X, BASE_Y - 0.006, -0.168),
               radius=0.006, seg=2), rubber)
        S(rbox(f'termblk{sx}', (0.052, 0.024, 0.036), (sx * POST_X, BASE_Y - 0.009, -0.252),
               radius=0.004, seg=1), bakelite)
        S(bolt(f'termbolt{sx}', r=0.008, h=0.006, loc=(sx * POST_X, BASE_Y - 0.021, -0.252),
               rot=(OUT, 0, 0), washer=True), galv)

    # ----------------------------------------------------------------- ON/OFF plate ----
    S(rbox('travel', (0.036, 0.008, 0.428), (0.178, FY - 0.001, -0.090), radius=0.003, seg=1),
      brassm)
    S(text_mesh('t_on', 'ON', font=FONT_STENCIL, size=0.024, extrude=0.002, bev=0.0,
                loc=(0.178, FY - 0.006, 0.098), res=1, bres=0, spacing=1.02), dark)
    S(text_mesh('t_off', 'OFF', font=FONT_STENCIL, size=0.024, extrude=0.002, bev=0.0,
                loc=(0.178, FY - 0.006, -0.272), res=1, bres=0, spacing=1.02), dark)
    for zz in (0.058, -0.232):
        S(rbox(f'tk{zz}', (0.030, 0.006, 0.005), (0.178, FY - 0.005, zz), radius=0.001,
               seg=1), dark)

    # data plate
    S(rbox('dataplate', (0.048, 0.006, 0.056), (-0.178, FY - 0.001, -0.236), radius=0.003,
           seg=1), brassm)
    S(text_mesh('t_amp', '200A', font=FONT_STENCIL, size=0.015, extrude=0.0016, bev=0.0,
                loc=(-0.178, FY - 0.005, -0.236), res=1, bres=0, spacing=1.02), dark)

    # ------------------------------------------------------------------ hazard band ----
    pl, stripes = hazard_band('hz', 0.396, 0.058, (0, FY - 0.003, -0.316), depth=0.010, n=9)
    S(pl, hazard)
    for s in stripes:
        S(s, dark)

    # ---------------------------------------------------------------------- conduit ----
    S(cyl('gland_t', r=0.038, h=0.032, loc=(-0.150, -0.095, 0.412), verts=14), rawsteel)
    S(tube('lock_t', r_out=0.036, r_in=0.027, h=0.014, loc=(-0.150, -0.095, 0.436), verts=14),
      galv)
    S(pipe_path('conduit_t', [(-0.150, -0.095, 0.400), (-0.150, -0.095, 0.434),
                              (-0.150, -0.072, 0.458), (-0.150, -0.016, 0.464)],
                r=0.026, verts=12), galv)
    S(cyl('gland_b', r=0.034, h=0.030, loc=(0.150, -0.095, -0.412), verts=14), rawsteel)
    S(tube('lock_b', r_out=0.032, r_in=0.024, h=0.014, loc=(0.150, -0.095, -0.436), verts=14),
      galv)
    S(pipe_path('conduit_b', [(0.150, -0.095, -0.400), (0.150, -0.095, -0.432),
                              (0.150, -0.074, -0.456), (0.150, -0.016, -0.462)],
                r=0.023, verts=12), galv)
    # flexible armoured drop out of the left flank
    S(cyl('gland_s', r=0.024, h=0.026, loc=(-0.256, -0.110, -0.250), verts=12,
          rot=(0, D2R(90), 0)), rawsteel)
    flexpts = [(-0.252, -0.110, -0.250), (-0.286, -0.108, -0.268), (-0.300, -0.092, -0.316),
               (-0.296, -0.062, -0.372), (-0.278, -0.032, -0.410), (-0.262, -0.010, -0.428)]
    S(pipe_path('flex', flexpts, r=0.014, verts=8), rubber)
    for i in range(1, 5):
        S(cyl(f'flexrib{i}', r=0.017, h=0.007, loc=flexpts[i], verts=8,
              rot=(D2R(64 - i * 12), 0, D2R(14))), galv)

    # ------------------------------------------------------------------- the lever ----
    # Local frame: pivot at the origin, lever hanging along -Z.
    L(cyl('lv_hub', r=0.024, h=0.136, loc=(0, 0, 0), verts=14, rot=(0, D2R(90), 0)), galv)
    for sx in (-1, 1):
        L(rbox(f'lv_blade{sx}', (0.028, 0.015, BLADE_L),
               (sx * BLADE_X, 0, -BLADE_L / 2), radius=0.0025, seg=1), copper)
        L(cyl(f'lv_boss{sx}', r=0.019, h=0.038, loc=(sx * BLADE_X, 0, 0), verts=10,
              rot=(0, D2R(90), 0)), galv)
    # The operating arm: one forged, tapered bar down the centre.  Everything about the
    # lever is sized so it reads as a single big handle from across a room - the twin
    # blades are supporting detail, not the silhouette.  Its width stays inside x +-0.040
    # so it passes between the jaw contacts at x +-0.058.
    L(profile_extrude('lv_arm',
                      [(-0.040, 0.016), (0.040, 0.016), (0.031, -0.078), (0.023, -0.152),
                       (-0.023, -0.152), (-0.031, -0.078)],
                      depth=0.030, loc=(0, -0.008, 0), bevel=0.004, bseg=2), gunmetal)
    # from here out the handle is past the jaw bars' reach (radius > 0.150 from the
    # pivot), so the grip can swell into a proper fist-sized knob
    L(cyl('lv_collar', r=0.026, h=0.028, loc=(0, -0.008, -0.156), verts=14), galv)
    L(cyl('lv_guard', r=0.032, h=0.012, loc=(0, -0.008, -0.164), verts=18), galv)
    L(lathe('lv_grip', [(0.0000, -0.160), (0.0230, -0.165), (0.0340, -0.172),
                        (0.0420, -0.181), (0.0460, -0.192), (0.0465, -0.203),
                        (0.0425, -0.213), (0.0340, -0.221), (0.0200, -0.227),
                        (0.0000, -0.231)],
            verts=22, loc=(0, -0.008, 0)), red_h)

    # ------------------------------------------------------------------------ bake ----
    apply_mods(solid + glow + lever_parts + sign)
    print('  welded away', weld(solid + glow + lever_parts + sign), 'degenerate faces')
    lo, hi = bounds(solid + glow + lever_parts + sign)
    print('  bbox  min %.3f %.3f %.3f   max %.3f %.3f %.3f' % (*lo, *hi))
    print('  size  %.3f w x %.3f d x %.3f h' % (hi.x - lo.x, hi.y - lo.y, hi.z - lo.z))
    print('  pre-bake tris:', tri_count())
    heavy = sorted(((tri_count([o]), o.name) for o in solid + glow + lever_parts),
                   reverse=True)[:6]
    print('  heaviest:', ', '.join(f'{n}={t}' for t, n in heavy))

    print('  validate:', validate(solid + glow + lever_parts + sign), 'problems')

    TEX = int(os.environ.get('POWER_TEX', '1024'))
    bake_pbr(solid, 'power_body', size=TEX, samples=4, normal_samples=6, margin=0.0024)
    # the placard gets its own sheet: at the body's texel density the stencil turns to mush
    bake_pbr(sign, 'power_sign', size=TEX // 2, samples=4, normal_samples=6, margin=0.004)
    bake_pbr(lever_parts, 'power_lever', size=TEX // 2, samples=4, normal_samples=6,
             margin=0.005)
    bake_pbr(glow, 'power_lamp', size=max(64, TEX // 6), samples=4, normal_samples=6,
             margin=0.012, emissive=True, emission_strength=0.9, mat_name='power_glow')

    panel = join('panel', solid + sign + glow)
    set_origin(panel, (0, 0, 0))
    lever = join('lever', lever_parts)
    set_origin(lever, PIVOT)
    print('  panel loc/rot', tuple(round(v, 4) for v in panel.location),
          tuple(round(v, 4) for v in panel.rotation_euler))
    print('  lever loc/rot', tuple(round(v, 4) for v in lever.location),
          tuple(round(v, 4) for v in lever.rotation_euler))

    # --------------------------------------------------------------------- verify ----
    angles = [ON_DELTA * i / 36.0 for i in range(37)]
    d, a, p = sweep_clearance(lever, panel, PIVOT, angles)
    print('  sweep clearance %.4f m at %.3f rad  (worst point %.3f %.3f %.3f)'
          % (d, a, p.x, p.y, p.z))
    print('  tris:', tri_count())

    # ---------------------------------------------------------------------- shots ----
    wall = box('_wall', (3.0, 0.08, 2.4), (0, 0.041, 0))
    assign(wall, pbr_material('_wallmat', (0.095, 0.092, 0.088), 0.90))

    lever.rotation_euler = (ON_DELTA, 0, 0)
    bpy.context.view_layer.update()
    preview_render(path=os.path.join(PROPS_RENDERS, 'power_switch_on.png'),
                   target=(0, -0.14, -0.01), distance=1.55, yaw_deg=30, pitch_deg=8,
                   res=(760, 900), samples=44, world_strength=0.5, ground=False)
    lever.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()

    shots('power_switch', target=(0, -0.14, -0.01), hero=(1.60, 32, 9),
          close=(0.80, 24, -6), close_target=(0, -0.24, -0.11), samples=44,
          res=(760, 900), world=0.5, ground=False)

    bpy.data.objects.remove(wall, do_unlink=True)
    export_prop('power_switch.glb', roots=[panel, lever], quality=82)


build()
