"""mystery_box.glb - weathered wooden weapons crate, 1.5 x 0.6 x 0.55 m.

Origin: floor centre. Front = -Y.
Objects: crate (body, chains, ironwork), lid (origin on the rear hinge line,
         rotate about local X to open).

The question marks are *paint*, not geometry (environment.md #17): a flat stencil
0.8 mm proud of the boards, no bevel and no extrusion silhouette, so they read as a
sprayed marking that has chipped off the grain rather than a plastic solid.  They keep
their own material `glow_q` (emission 0.6) so `interactables.js` can pulse them in the
low "mark" band.  One size per face family, centred on the panel.

The chains are true catenaries hung between eye plates and routed clear of the corner
brackets and rivets.
"""
import sys, os, math, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib_props import *

random.seed(21)

HW, HD = 0.75, 0.30      # half width / half depth of the carcass
SKID = 0.055             # runner height
ZT = 0.420               # top of the body
LID_SKIRT_LO, LID_SKIRT_HI = 0.398, 0.470
LID_TOP_HI = 0.505
HINGE = (0.0, 0.325, 0.495)


def plank(name, size, loc, rot=(0, 0, 0), seed=1, warp=0.004, cuts=(2, 1), bw=0.0035):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    longest = max(range(3), key=lambda i: size[i])
    axis_name = 'xyz'[longest]
    edges = [e for e in bm.edges
             if abs(getattr(e.verts[0].co, axis_name) - getattr(e.verts[1].co, axis_name)) > 1e-4]
    bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts[0], use_grid_fill=False)
    ob = finish(name, bm, loc, rot)
    if warp:
        jitter(ob, amount=warp, scale=3.0, seed=seed, axis=(1, 1, 1))
    m = ob.modifiers.new('Bevel', 'BEVEL')
    m.width = bw; m.segments = 1; m.limit_method = 'ANGLE'; m.angle_limit = D2R(35)
    return ob


def rivet(name, loc, rot, r=0.007):
    ob = bolt(name, r=r, h=0.005, loc=loc, rot=rot)
    return ob


def catenary(p0, p1, sag, n=16, k=2.1):
    """Polyline of a chain hanging between two anchors.

    The horizontal run is a straight lerp; the drop follows a real catenary
    (cosh), so the curve is flat-bottomed and steep at the anchors the way a
    loose chain actually hangs - not a parabola and definitely not a straight run."""
    p0, p1 = Vector(p0), Vector(p1)
    ck = math.cosh(k)
    return [tuple(p0.lerp(p1, t) + Vector((0, 0, sag * (math.cosh(k * (2 * t - 1)) - ck)
                                           / (ck - 1.0))))
            for t in (i / (n - 1.0) for i in range(n))]


def eye_plate(name, loc, normal='y'):
    """Small backing plate + ring the chain is shackled to."""
    if normal == 'y':
        pl = rbox(f'{name}_p', (0.050, 0.008, 0.050), loc, radius=0.002, seg=1)
        rg = tube(f'{name}_r', r_out=0.020, r_in=0.012, h=0.008,
                  loc=(loc[0], loc[1] + math.copysign(0.012, loc[1]), loc[2]),
                  verts=12, rot=(D2R(90), 0, 0))
    else:
        pl = rbox(f'{name}_p', (0.008, 0.050, 0.050), loc, radius=0.002, seg=1)
        rg = tube(f'{name}_r', r_out=0.020, r_in=0.012, h=0.008,
                  loc=(loc[0] + math.copysign(0.012, loc[0]), loc[1], loc[2]),
                  verts=12, rot=(0, D2R(90), 0))
    return [pl, rg]


def build():
    props_scene()

    wood_a = wood_mat('crate_wood_a', color=(0.150, 0.093, 0.047), rough=0.78, grime=0.8,
                      seed=1.0, grain=1.0, split=0.8, axis='X', bleach=0.22)
    wood_b = wood_mat('crate_wood_b', color=(0.178, 0.108, 0.052), rough=0.75, grime=0.75,
                      seed=4.0, grain=1.0, split=0.7, axis='X', bleach=0.14)
    wood_v = wood_mat('crate_wood_v', color=(0.160, 0.098, 0.048), rough=0.77, grime=0.85,
                      seed=7.0, grain=1.0, split=0.8, axis='Z', bleach=0.18)
    wood_y = wood_mat('crate_wood_y', color=(0.165, 0.100, 0.050), rough=0.77, grime=0.85,
                      seed=9.0, grain=1.0, split=0.8, axis='Y', bleach=0.18)
    iron = weathered('crate_iron', color=(0.115, 0.108, 0.103), roughness=0.60, metallic=1.0,
                     wear_color=(0.40, 0.39, 0.38), wear=0.30, wear_rough=0.35,
                     rust=0.85, rust_color=(0.245, 0.105, 0.042), grime=0.7,
                     dust=0.10, variation=0.14, scale=4.0, seed=13.0, bump=0.9,
                     dent=0.45, scratch=1.0, ao_dist=0.03, pointy_lo=0.44, pointy_hi=0.60)
    chain_iron = weathered('crate_chain', color=(0.105, 0.098, 0.093), roughness=0.62, metallic=1.0,
                           wear_color=(0.45, 0.44, 0.43), wear=0.45, wear_rough=0.3,
                           rust=0.8, rust_color=(0.26, 0.115, 0.045), grime=0.6,
                           dust=0.08, variation=0.12, scale=8.0, seed=17.0, bump=1.0,
                           dent=0.2, scratch=0.8, ao_dist=0.02, pointy_lo=0.42, pointy_hi=0.62)
    # stencil paint: pale ice blue, sprayed on and half worn away.  High wear +
    # scratch + speckle so the wood grain shows through it; almost no bump, because
    # paint on sawn timber has no relief of its own (environment.md #17).
    # A flat glyph sits at pointiness 0.5 everywhere, so the usual edge-wear ramp barely
    # fires and the paint bakes out pristine - a clean decal on a filthy crate, which is
    # what the first two passes produced.  Saturating the ramp (0.30 -> 0.50) puts the
    # whole face at full edge_raw and hands the pattern entirely to the breakup noise, so
    # `scale` becomes the chip size: 5.0 gives ~15 mm flakes of bare grain rather than a
    # uniform 25 % brown wash.
    qpaint = weathered('q_paint_src', color=(0.38, 0.68, 0.98), roughness=0.64, metallic=0.0,
                       wear_color=(0.150, 0.093, 0.047), wear=1.0, wear_rough=0.84,
                       wear_metal=0.0, rust=0.0, grime=0.62, grime_color=(0.05, 0.06, 0.07),
                       dust=0.16, variation=0.42, scale=5.0, seed=23.0,
                       bump=0.18, dent=0.0, scratch=1.0, ao_dist=0.02, speckle=0.55,
                       streak=0.55, pointy_lo=0.30, pointy_hi=0.50)

    body, iron_parts, glow_parts = [], [], []

    # ------------------------------------------------------------- runners ----
    for sx in (-1, 1):
        body.append(plank(f'skid_{sx}', (0.10, 0.66, SKID), (sx * 0.60, 0, SKID / 2),
                          seed=int(30 + sx), warp=0.003))
    body.append(plank('skid_c', (0.10, 0.66, SKID), (0, 0, SKID / 2), seed=32, warp=0.003))

    # --------------------------------------------------------- side panels ----
    z0, z1 = SKID, ZT
    n = 4
    ph = (z1 - z0) / n
    for i in range(n):
        zc = z0 + ph * (i + 0.5)
        for sy, tag in ((-1, 'f'), (1, 'b')):
            p = plank(f'wall_{tag}{i}', (2 * HW, 0.024, ph - 0.005), (0, sy * (HD - 0.012), zc),
                      (random.uniform(-0.004, 0.004), 0, 0), seed=40 + i * 3 + (sy > 0), warp=0.0035)
            assign(p, wood_a if i % 2 else wood_b)
            body.append(p)
    # end panels: vertical boards
    for sx in (-1, 1):
        for j in range(3):
            yc = -HD + 0.10 + j * 0.20
            p = plank(f'end_{sx}_{j}', (0.024, 0.195, z1 - z0 - 0.004),
                      (sx * (HW - 0.012), yc, (z0 + z1) / 2), seed=60 + j + (sx > 0) * 5, warp=0.003)
            assign(p, wood_v)
            body.append(p)

    # inner floor (seen when the lid opens)
    inner = plank('inner_floor', (2 * HW - 0.06, 2 * HD - 0.06, 0.022), (0, 0, SKID + 0.012),
                  seed=70, warp=0.002)
    assign(inner, wood_y)
    body.append(inner)

    # ---------------------------------------------------- battens / corners ----
    for sx in (-1, 1):
        for sy in (-1, 1):
            b1 = plank(f'post_{sx}{sy}', (0.055, 0.032, z1 - z0 + 0.012),
                       (sx * (HW - 0.028), sy * (HD + 0.006), (z0 + z1) / 2), seed=80, warp=0.002)
            assign(b1, wood_v)
            body.append(b1)
            b2 = plank(f'post2_{sx}{sy}', (0.030, 0.055, z1 - z0 + 0.012),
                       (sx * (HW + 0.006), sy * (HD - 0.028), (z0 + z1) / 2), seed=81, warp=0.002)
            assign(b2, wood_v)
            body.append(b2)
    for sy in (-1, 1):
        for sx in (-0.30, 0.30):
            b = plank(f'mid_{sy}_{sx}', (0.058, 0.026, z1 - z0 + 0.006),
                      (sx, sy * (HD + 0.004), (z0 + z1) / 2), seed=85, warp=0.002)
            assign(b, wood_v)
            body.append(b)
    # top rail all round
    for sy in (-1, 1):
        r = plank(f'rail_{sy}', (2 * HW + 0.02, 0.040, 0.034), (0, sy * (HD + 0.001), z1 - 0.017),
                  seed=88, warp=0.002)
        assign(r, wood_a)
        body.append(r)

    for ob in body:
        if not ob.data.materials:
            assign(ob, wood_b)

    # --------------------------------------------------------- iron corners ----
    for sx in (-1, 1):
        for sy in (-1, 1):
            for zc, h in ((z0 + 0.035, 0.09), (z1 - 0.045, 0.09)):
                a = rbox(f'br_a{sx}{sy}{zc:.2f}', (0.115, 0.005, h),
                         (sx * (HW - 0.055), sy * (HD + 0.023), zc), radius=0.0015, seg=1)
                b = rbox(f'br_b{sx}{sy}{zc:.2f}', (0.005, 0.115, h),
                         (sx * (HW + 0.023), sy * (HD - 0.055), zc), radius=0.0015, seg=1)
                iron_parts += [a, b]
                for t in (-0.035, 0.035):
                    iron_parts.append(rivet(f'rv_a{sx}{sy}{zc:.2f}{t}',
                                            (sx * (HW - 0.055) + t, sy * (HD + 0.026), zc),
                                            (D2R(90) if sy < 0 else D2R(-90), 0, 0)))
                    iron_parts.append(rivet(f'rv_b{sx}{sy}{zc:.2f}{t}',
                                            (sx * (HW + 0.026), sy * (HD - 0.055) + t, zc),
                                            (0, D2R(-90) if sx < 0 else D2R(90), 0)))
    # corner caps on the top edge
    for sx in (-1, 1):
        for sy in (-1, 1):
            iron_parts.append(rbox(f'cap{sx}{sy}', (0.13, 0.006, 0.05),
                                   (sx * (HW - 0.06), sy * (HD + 0.023), z1 - 0.02),
                                   radius=0.0015, seg=1))

    # end handles
    for sx in (-1, 1):
        pts = [(sx * (HW + 0.028), -0.085, 0.385), (sx * (HW + 0.075), -0.055, 0.352),
               (sx * (HW + 0.082), 0.0, 0.342), (sx * (HW + 0.075), 0.055, 0.352),
               (sx * (HW + 0.028), 0.085, 0.385)]
        iron_parts.append(pipe_path(f'handle_{sx}', pts, r=0.009, verts=8))
        for sy in (-1, 1):
            iron_parts.append(rbox(f'hplate_{sx}{sy}', (0.012, 0.05, 0.05),
                                   (sx * (HW + 0.020), sy * 0.085, 0.385), radius=0.002, seg=1))

    # hasp + padlock on the front (unlatched, hanging).  Mounted on the mid batten at
    # x = 0.30, so it sits on something and stays clear of the chain's line.
    LX, LY = 0.30, HD + 0.043
    iron_parts.append(rbox('hasp_plate', (0.09, 0.008, 0.10), (LX, -LY, z1 - 0.055),
                           radius=0.002, seg=1))
    iron_parts.append(rbox('hasp_staple', (0.026, 0.020, 0.048), (LX, -(LY + 0.010), z1 - 0.085),
                           radius=0.002, seg=1))
    lockbody = rbox('padlock', (0.052, 0.020, 0.062), (LX, -(LY + 0.026), z1 - 0.135),
                    radius=0.008, seg=2)
    iron_parts.append(lockbody)
    iron_parts.append(pipe_path('shackle', [
        (LX - 0.018, -(LY + 0.026), z1 - 0.108), (LX - 0.018, -(LY + 0.026), z1 - 0.088),
        (LX - 0.012, -(LY + 0.022), z1 - 0.076), (LX, -(LY + 0.020), z1 - 0.073),
        (LX + 0.012, -(LY + 0.022), z1 - 0.076), (LX + 0.018, -(LY + 0.026), z1 - 0.088),
        (LX + 0.018, -(LY + 0.026), z1 - 0.108)], r=0.006, verts=7))

    # ------------------------------------------------------------- chains ----
    # Both runs are real catenaries between eye plates, and both sit at least 6 mm
    # clear of the corner brackets (front face -(HD+0.0255)) and their rivet heads
    # (-(HD+0.0285)); the links are 0.0146 m in outer radius, so the chain axis has
    # to sit at -(HD+0.050) or further out.  environment.md #17.
    CY = -(HD + 0.0500)                # front chain axis depth
    CX = -(HW + 0.0500)                # end chain axis offset
    AX = HW - 0.155                    # anchors sit inboard of the corner caps
    for sx in (-1, 1):
        for ob in eye_plate(f'eye_f{sx}', (sx * AX, -(HD + 0.026), 0.392), normal='y'):
            iron_parts.append(ob)
    for sy in (-1, 1):
        for ob in eye_plate(f'eye_e{sy}', (-(HW + 0.026), sy * 0.205, 0.290), normal='x'):
            iron_parts.append(ob)

    ch1 = chain('chain_front',
                catenary((-AX, CY, 0.378), (AX, CY, 0.384), sag=0.215, n=20, k=2.15),
                link_len=0.030, link_r=0.011, wire=0.0036, minor=4)
    ch2 = chain('chain_end',
                catenary((CX, -0.205, 0.278), (CX, 0.205, 0.284), sag=0.125, n=14, k=2.0),
                link_len=0.028, link_r=0.010, wire=0.0034, minor=4)
    for c in (ch1, ch2):
        assign(c, chain_iron)

    for ob in iron_parts:
        assign(ob, iron)

    # ---------------------------------------------------------------- lid ----
    lid_parts = []
    # skirt
    for sy in (-1, 1):
        lid_parts.append(plank(f'lid_sk_y{sy}', (2 * HW + 0.05, 0.026, LID_SKIRT_HI - LID_SKIRT_LO),
                               (0, sy * (HD + 0.012), (LID_SKIRT_LO + LID_SKIRT_HI) / 2),
                               seed=90 + (sy > 0), warp=0.003))
    for sx in (-1, 1):
        lid_parts.append(plank(f'lid_sk_x{sx}', (0.026, 2 * HD + 0.05, LID_SKIRT_HI - LID_SKIRT_LO),
                               (sx * (HW + 0.012), 0, (LID_SKIRT_LO + LID_SKIRT_HI) / 2),
                               seed=92 + (sx > 0), warp=0.003))
    # top boards
    for j in range(4):
        yc = -HD + 0.0825 + j * 0.155
        p = plank(f'lid_top_{j}', (2 * HW + 0.05, 0.150, LID_TOP_HI - LID_SKIRT_HI + 0.01),
                  (0, yc, (LID_SKIRT_HI + LID_TOP_HI) / 2 - 0.005), seed=100 + j, warp=0.004)
        assign(p, wood_a if j % 2 else wood_b)
        lid_parts.append(p)
    # cross battens
    for sx in (-0.52, 0.52):
        b = plank(f'lid_bat_{sx}', (0.075, 2 * HD + 0.04, 0.030), (sx, 0, LID_TOP_HI + 0.014),
                  seed=110, warp=0.002)
        assign(b, wood_y)
        lid_parts.append(b)

    lid_iron = []
    # strap hinges (upper leaf belongs to the lid)
    for sx in (-0.42, 0.42):
        lid_iron.append(rbox(f'hng_l{sx}', (0.07, 0.19, 0.006), (sx, HD - 0.055, LID_TOP_HI + 0.003),
                             radius=0.0015, seg=1))
        lid_iron.append(cyl(f'hng_k{sx}', r=0.011, h=0.085, loc=(sx, HD + 0.040, LID_TOP_HI - 0.004),
                            verts=10, rot=(0, D2R(90), 0)))
        for t in (-0.05, 0.03):
            lid_iron.append(rivet(f'hng_rv{sx}{t}', (sx, HD - 0.075 + t, LID_TOP_HI + 0.007), (0, 0, 0)))
    # lid corner straps
    for sx in (-1, 1):
        for sy in (-1, 1):
            lid_iron.append(rbox(f'lcap{sx}{sy}', (0.10, 0.006, LID_SKIRT_HI - LID_SKIRT_LO - 0.01),
                                 (sx * (HW - 0.03), sy * (HD + 0.028),
                                  (LID_SKIRT_LO + LID_SKIRT_HI) / 2), radius=0.0015, seg=1))
            lid_iron.append(rbox(f'lcap2{sx}{sy}', (0.006, 0.10, LID_SKIRT_HI - LID_SKIRT_LO - 0.01),
                                 (sx * (HW + 0.028), sy * (HD - 0.03),
                                  (LID_SKIRT_LO + LID_SKIRT_HI) / 2), radius=0.0015, seg=1))
    for ob in lid_parts:
        if not ob.data.materials:
            assign(ob, wood_v)
    for ob in lid_iron:
        assign(ob, iron)
    lid_parts += lid_iron

    # body-side hinge leaves
    for sx in (-0.42, 0.42):
        lf = rbox(f'hngb{sx}', (0.07, 0.11, 0.006), (sx, HD + 0.012, LID_SKIRT_LO - 0.012),
                  radius=0.0015, seg=1)
        assign(lf, iron)
        iron_parts.append(lf)

    # ------------------------------------------------------ question marks ----
    # Painted stencils, not extruded plastic (environment.md #17): flat glyphs with
    # zero bevel sitting 0.8 mm off the boards, so the silhouette has no moulded
    # edge highlight and the mark reads as sprayed paint.  One size per face family,
    # every one centred on its panel.
    PANEL_Z = (SKID + ZT) / 2          # vertical centre of the side/end boards

    def qmark(name, size, loc, rot):
        t = text_mesh(name, '?', font=FONT_STENCIL, size=size, extrude=0.0004, bev=0.0,
                      loc=loc, rot=rot, res=3, bres=0)
        assign(t, qpaint)
        return t

    QS, QE = 0.290, 0.215              # long faces / end faces
    glow_parts.append(qmark('q_front', QS, (0.0, -(HD + 0.0050), PANEL_Z),
                            (D2R(90), 0, D2R(2))))
    glow_parts.append(qmark('q_back', QS, (0.0, (HD + 0.0050), PANEL_Z),
                            (D2R(90), 0, math.pi - D2R(2))))
    glow_parts.append(qmark('q_endL', QE, (-(HW + 0.0055), 0.0, PANEL_Z),
                            (D2R(90), 0, D2R(-90))))
    glow_parts.append(qmark('q_endR', QE, ((HW + 0.0055), 0.0, PANEL_Z),
                            (D2R(90), 0, D2R(90))))
    q_lid = qmark('q_lid', QS, (0.0, 0.0, LID_TOP_HI + 0.0058), (0, 0, D2R(-4)))

    # --------------------------------------------------------------- bake ----
    body_group = body + iron_parts + [ch1, ch2]
    lid_group = lid_parts
    apply_mods(body_group + lid_group + glow_parts + [q_lid])
    bake_pbr(body_group, 'mbox_body', size=1536, samples=4, normal_samples=6, margin=0.0025)
    bake_pbr(lid_group, 'mbox_lid', size=1024, samples=4, normal_samples=6, margin=0.003)
    bake_pbr(glow_parts + [q_lid], 'mbox_q', size=512, samples=4, normal_samples=6,
             margin=0.006, emissive=True, emission_strength=0.6, mat_name='glow_q')

    crate = join('crate', body_group + glow_parts)
    set_origin(crate, (0, 0, 0))
    lid = join('lid', lid_group + [q_lid])
    set_origin(lid, HINGE)

    print('tris:', tri_count())
    shots('mystery_box', target=(0, 0, 0.30), hero=(2.9, 34, 16), close=(0.85, 8, 6),
          close_target=(0.0, -0.30, 0.26), samples=30, res=(900, 560))
    export_prop('mystery_box.glb', roots=[crate, lid])


build()
