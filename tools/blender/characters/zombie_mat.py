"""Procedural materials for the zombies, built for UV baking (glTF only ships images)."""
import bpy, math
from mathutils import Vector


def N(nt, kind, **kw):
    n = nt.nodes.new(kind)
    for k, v in kw.items():
        if '.' in k:
            a, b = k.split('.')
            getattr(n, a)[b].default_value = v
        else:
            setattr(n, k, v)
    return n


def inp(node, key, value):
    _in(node, key).default_value = value
    return node


# Blender 5.x renamed 'Fac' -> 'Factor'; Mix/MapRange have several same-named sockets.
def _out(node, key):
    if isinstance(key, int):
        return node.outputs[key]
    if node.bl_idname == 'ShaderNodeMix' and key == 'Result':
        return node.outputs[2]                      # the colour Result
    names = [o.name for o in node.outputs]
    if key not in names and key == 'Fac':
        key = 'AO' if node.bl_idname == 'ShaderNodeAmbientOcclusion' else 'Factor'
    if key not in names and key == 'Factor' and 'AO' in names:
        key = 'AO'
    return node.outputs[key]


def _in(node, key):
    if isinstance(key, int):
        return node.inputs[key]
    names = [i.name for i in node.inputs]
    if key not in names and key == 'Fac':
        key = 'Factor'
    return node.inputs[key]


def lk(nt, a, ao, b, bi):
    nt.links.new(_out(a, ao), _in(b, bi))


def noise(nt, scale, detail=6, rough=0.55, dist=0.0, coord=None, dim='3D'):
    n = N(nt, 'ShaderNodeTexNoise')
    n.noise_dimensions = dim
    inp(n, 'Scale', scale); inp(n, 'Detail', detail); inp(n, 'Roughness', rough)
    inp(n, 'Distortion', dist)
    if coord:
        lk(nt, coord[0], coord[1], n, 'Vector')
    return n


def ramp(nt, src, out, stops):
    r = N(nt, 'ShaderNodeValToRGB')
    lk(nt, src, out, r, 'Fac')
    el = r.color_ramp.elements
    while len(el) > 1:
        el.remove(el[-1])
    el[0].position = stops[0][0]
    el[0].color = stops[0][1]
    for pos, col in stops[1:]:
        e = el.new(pos)
        e.color = col
    return r


def mix(nt, fac_node, fac_out, a, b, name='Mix'):
    """Colour mix; a and b can be (node, out) tuples or RGBA constants."""
    m = N(nt, 'ShaderNodeMix')
    m.data_type = 'RGBA'
    m.blend_type = 'MIX'
    if fac_node is not None:
        nt.links.new(_out(fac_node, fac_out), m.inputs[0])
    for key, val in (('A', a), ('B', b)):
        idx = 6 if key == 'A' else 7
        if isinstance(val, tuple) and len(val) == 2 and hasattr(val[0], 'outputs'):
            lk(nt, val[0], val[1], m, idx)
        else:
            m.inputs[idx].default_value = val
    return m


def _sub(nt, a, ao, b, bo=None, op='SUBTRACT', clamp=True):
    m = N(nt, 'ShaderNodeMath')
    m.operation = op
    m.use_clamp = clamp
    lk(nt, a, ao, m, 0)
    if hasattr(b, 'outputs'):
        lk(nt, b, bo, m, 1)
    else:
        m.inputs[1].default_value = b
    return m



def blob_mask(nt, co, center, radii, soft=0.45):
    """1 inside an ellipsoid at `center`, fading to 0 at its surface."""
    sub = N(nt, 'ShaderNodeVectorMath'); sub.operation = 'SUBTRACT'
    lk(nt, co, 'Object', sub, 0)
    sub.inputs[1].default_value = center
    div = N(nt, 'ShaderNodeVectorMath'); div.operation = 'DIVIDE'
    lk(nt, sub, 'Vector', div, 0)
    div.inputs[1].default_value = radii
    ln = N(nt, 'ShaderNodeVectorMath'); ln.operation = 'LENGTH'
    lk(nt, div, 'Vector', ln, 0)
    mr = N(nt, 'ShaderNodeMapRange')
    lk(nt, ln, 'Value', mr, 'Value')
    mr.inputs[1].default_value = 1.0
    mr.inputs[2].default_value = soft
    mr.inputs[3].default_value = 0.0
    mr.inputs[4].default_value = 1.0
    mr.clamp = True
    return mr


def mask_union(nt, masks):
    cur = masks[0]
    out = 'Result'
    for m in masks[1:]:
        cur = _sub(nt, cur, out, m, 'Result', 'MAXIMUM')
        out = 'Value'
    return cur, out


# ---------------------------------------------------------------------------------------

def skin_material(mat, ob, blood_head=True, seed=0.0):
    """Rotting flesh: mottled necrotic base, bruising, veins, dirt in crevices, blood."""
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
            nt.nodes.remove(n)
    bsdf = nt.nodes['Principled BSDF']

    co = N(nt, 'ShaderNodeTexCoord')
    sep = N(nt, 'ShaderNodeSeparateXYZ')
    lk(nt, co, 'Object', sep, 'Vector')

    # --- base mottling -------------------------------------------------------------
    n_big = noise(nt, 6.0, 8, 0.62, 0.4, (co, 'Object'))
    n_mid = noise(nt, 22.0, 8, 0.58, 0.2, (co, 'Object'))
    n_fine = noise(nt, 110.0, 6, 0.50, 0.0, (co, 'Object'))
    n_pore = noise(nt, 300.0, 3, 0.45, 0.0, (co, 'Object'))
    n_blotch = noise(nt, 2.4, 6, 0.70, 0.6, (co, 'Object'))

    pale = (0.168, 0.164, 0.132, 1)      # grey-green necrotic
    sallow = (0.215, 0.176, 0.104, 1)    # jaundiced
    bruise = (0.072, 0.058, 0.082, 1)    # purple
    rot = (0.046, 0.040, 0.030, 1)       # dark decay
    # Dried blood on a body is brown-black, not cherry.  The old values were so saturated
    # (R 6-12x G) that under the game's warm key they read as bright red paint, which is
    # what made the mouth a clown grin and the arms look sprayed.
    dried = (0.052, 0.024, 0.018, 1)     # dried blood - dark oxidised brown
    fresh = (0.086, 0.021, 0.016, 1)     # wet blood - still dark, just wetter

    c1 = mix(nt, n_big, 'Fac', pale, sallow)
    bruise_mask = ramp(nt, n_mid, 'Fac', [(0.42, (0, 0, 0, 1)), (0.68, (1, 1, 1, 1))])
    c2 = mix(nt, bruise_mask, 'Color', (c1, 'Result'), bruise)
    rot_mask = ramp(nt, n_big, 'Fac', [(0.54, (0, 0, 0, 1)), (0.76, (1, 1, 1, 1))])
    c2b = mix(nt, rot_mask, 'Color', (c2, 'Result'), rot)
    blotch = ramp(nt, n_blotch, 'Fac', [(0.30, (0, 0, 0, 1)), (0.72, (1, 1, 1, 1))])
    c3 = mix(nt, blotch, 'Color', (c2b, 'Result'), (0.088, 0.092, 0.062, 1))

    # --- veins ---------------------------------------------------------------------
    vor = N(nt, 'ShaderNodeTexVoronoi')
    vor.feature = 'DISTANCE_TO_EDGE'
    inp(vor, 'Scale', 55.0)
    vd = N(nt, 'ShaderNodeMapping')
    inp(vd, 'Scale', (1.0, 1.0, 1.0))
    lk(nt, co, 'Object', vd, 'Vector')
    lk(nt, vd, 'Vector', vor, 'Vector')
    vein = ramp(nt, vor, 'Distance', [(0.0, (1, 1, 1, 1)), (0.012, (0, 0, 0, 1))])
    vein_fade = N(nt, 'ShaderNodeMix'); vein_fade.data_type = 'RGBA'
    vein_fade.blend_type = 'MULTIPLY'
    vein_fade.inputs[0].default_value = 1.0
    lk(nt, vein, 'Color', vein_fade, 6)
    lk(nt, n_big, 'Fac', vein_fade, 7)
    c4 = mix(nt, vein_fade, 'Result', (c3, 'Result'), (0.055, 0.040, 0.062, 1))

    # --- ambient-occlusion dirt ----------------------------------------------------
    ao = N(nt, 'ShaderNodeAmbientOcclusion')
    ao.samples = 8
    inp(ao, 'Distance', 0.06)
    ao_r = ramp(nt, ao, 'Fac', [(0.15, (1, 1, 1, 1)), (0.85, (0, 0, 0, 1))])
    c5 = mix(nt, ao_r, 'Color', (c4, 'Result'), (0.030, 0.024, 0.018, 1))

    # --- blood: head/chin, hands, and streaks running down from the wounds ---------
    # vertical falloff mask built from object Z
    def band(lo, hi):
        m = N(nt, 'ShaderNodeMapRange')
        nt.links.new(sep.outputs['Z'], m.inputs[0])
        m.inputs[1].default_value = lo
        m.inputs[2].default_value = hi
        m.inputs[3].default_value = 0.0
        m.inputs[4].default_value = 1.0
        m.clamp = True
        return m

    drip = noise(nt, 3.0, 6, 0.6, 0.0)
    drip_v = N(nt, 'ShaderNodeMapping')
    inp(drip_v, 'Scale', (6.0, 6.0, 0.35))
    lk(nt, co, 'Object', drip_v, 'Vector')
    lk(nt, drip_v, 'Vector', drip, 'Vector')
    drip_r = ramp(nt, drip, 'Fac', [(0.40, (0, 0, 0, 1)), (0.60, (1, 1, 1, 1))])

    # --- wounds ---------------------------------------------------------------------
    # The wound positions come from the single shared table in zombie_mesh, the same one
    # the sculptor, the gore-material face picker and the cloth tears read.  They used to
    # be hard-coded here and had drifted away from the geometry (and every torso wound sat
    # under a closed shirt that was then deleted), which is why none of this paint was
    # ever visible on the finished character - review item #6.
    from zombie_mesh import all_wounds
    ws = all_wounds()

    # dried blood: smeared around each wound, running downward.  Half of it is applied
    # flat and half through the drip mask, so a wound is never completely clean.
    dried_masks = [blob_mask(nt, co, tuple(w['c']),
                             (w['blood'], w['blood'] * 0.92, w['blood'] * 1.35), 0.22)
                   for w in ws]
    dried_masks.append(blob_mask(nt, co, (0.0, -0.070, 1.480), (0.140, 0.100, 0.150), 0.15))
    dm, dout = mask_union(nt, dried_masks)
    drip_mul = _sub(nt, dm, dout, drip_r, 'Color', 'MULTIPLY')
    dm_flat = _sub(nt, dm, dout, 0.55, op='MULTIPLY')
    dm2 = _sub(nt, drip_mul, 'Value', dm_flat, 'Value', 'MAXIMUM')
    c6 = mix(nt, dm2, 'Value', (c5, 'Result'), dried)

    # fresh wet blood only in the wound craters themselves
    wet_masks = [blob_mask(nt, co, tuple(w['c']),
                           (w['r'] * 0.95, w['r'] * 0.90, w['r'] * 1.15), 0.32)
                 for w in ws]
    gm, gout = mask_union(nt, wet_masks)
    gash_m2 = _sub(nt, gm, gout, 1.0, op='MULTIPLY')
    c7 = mix(nt, gash_m2, 'Value', (c6, 'Result'), fresh)
    # the deepest part of each crater goes darker still - clotted, not glossy red
    deep = [blob_mask(nt, co, tuple(w['c']),
                      (w['r'] * 0.55, w['r'] * 0.52, w['r'] * 0.62), 0.45) for w in ws]
    dpm, dpo = mask_union(nt, deep)
    c7 = mix(nt, dpm, dpo, (c7, 'Result'), (0.026, 0.008, 0.007, 1))

    # hands: filthy and bloodied to the wrist
    hand_masks = [blob_mask(nt, co, (sx * 0.312, -0.066, 0.800), (0.085, 0.085, 0.110), 0.25)
                  for sx in (1, -1)]
    hm_n, hm_o = mask_union(nt, hand_masks)
    hand_m = _sub(nt, hm_n, hm_o, 0.9, op='MULTIPLY')
    c8 = mix(nt, hand_m, 'Value', (c7, 'Result'), (0.040, 0.020, 0.014, 1))

    # ground dirt on the lower legs
    dirt_z = N(nt, 'ShaderNodeMapRange')
    lk(nt, sep, 'Z', dirt_z, 'Value')
    dirt_z.inputs[1].default_value = 0.55; dirt_z.inputs[2].default_value = 0.05; dirt_z.clamp = True
    dirt_m0 = _sub(nt, dirt_z, 'Result', n_mid, 'Fac', 'MULTIPLY')
    dirt_m = _sub(nt, dirt_m0, 'Value', 0.8, op='MULTIPLY')
    c9 = mix(nt, dirt_m, 'Value', (c8, 'Result'), (0.052, 0.042, 0.030, 1))

    if blood_head:
        # kept tight to the mouth and the chin under it: when these were wider they
        # painted a bright red clown-mouth across the whole lower face.
        # Tighter still, and much darker.  At the previous size and saturation this pair
        # of masks painted a cherry-red band right across the chin and lower lip, which is
        # the single biggest reason the face still read as a grinning cartoon at game
        # framing.  The smear now stays under the jaw and inside the aperture.
        mouth = blob_mask(nt, co, (0.0, -0.050, 1.604), (0.042, 0.032, 0.040), 0.25)
        mm2 = _sub(nt, mouth, 'Result', drip_r, 'Color', 'MULTIPLY')
        mm3 = _sub(nt, mm2, 'Value', 0.65, op='MULTIPLY')
        c8b = mix(nt, mm3, 'Value', (c9, 'Result'), dried)
        inner = blob_mask(nt, co, (0.0, -0.032, 1.617), (0.030, 0.026, 0.021), 0.40)
        c9 = mix(nt, inner, 'Result', (c8b, 'Result'), (0.042, 0.013, 0.011, 1))

    lk(nt, c9, 'Result', bsdf, 'Base Color')

    # --- roughness -----------------------------------------------------------------
    rr = ramp(nt, n_fine, 'Fac', [(0.15, (0.62, 0.62, 0.62, 1)), (0.85, (0.98, 0.98, 0.98, 1))])
    wet = N(nt, 'ShaderNodeMix'); wet.data_type = 'RGBA'; wet.blend_type = 'MIX'
    nt.links.new(_out(gash_m2, 'Value'), wet.inputs[0])
    lk(nt, rr, 'Color', wet, 6)
    wet.inputs[7].default_value = (0.26, 0.26, 0.26, 1)
    lk(nt, wet, 'Result', bsdf, 'Roughness')
    inp(bsdf, 'Specular IOR Level', 0.42)

    # --- bump: pores, wrinkles, sagging lumps --------------------------------------
    bump1 = N(nt, 'ShaderNodeBump')
    inp(bump1, 'Strength', 0.26); inp(bump1, 'Distance', 0.010)
    lk(nt, n_fine, 'Fac', bump1, 'Height')
    bump2 = N(nt, 'ShaderNodeBump')
    inp(bump2, 'Strength', 0.22); inp(bump2, 'Distance', 0.0016)
    lk(nt, n_pore, 'Fac', bump2, 'Height')
    lk(nt, bump1, 'Normal', bump2, 'Normal')
    bump3 = N(nt, 'ShaderNodeBump')
    inp(bump3, 'Strength', 0.42); inp(bump3, 'Distance', 0.022)
    lk(nt, n_mid, 'Fac', bump3, 'Height')
    lk(nt, bump2, 'Normal', bump3, 'Normal')
    lk(nt, bump3, 'Normal', bsdf, 'Normal')
    return mat


def cloth_material(mat, ob, base=(0.78, 0.76, 0.70), weave=0.55, dirt=(0.20, 0.16, 0.11),
                   pattern=None, uv_scale=70.0, blood=0.55, wear=0.6):
    """Woven fabric with dirt, sweat stains, blood and worn edges.
    `pattern`: None | 'floral' | 'twill' """
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
            nt.nodes.remove(n)
    bsdf = nt.nodes['Principled BSDF']
    co = N(nt, 'ShaderNodeTexCoord')
    sep = N(nt, 'ShaderNodeSeparateXYZ')
    lk(nt, co, 'Object', sep, 'Vector')

    uvm = N(nt, 'ShaderNodeMapping')
    inp(uvm, 'Scale', (uv_scale, uv_scale, uv_scale))
    lk(nt, co, 'UV', uvm, 'Vector')

    # weave: two perpendicular wave textures
    wv1 = N(nt, 'ShaderNodeTexWave')
    wv1.bands_direction = 'X'; wv1.wave_profile = 'SIN'
    inp(wv1, 'Scale', 1.0); inp(wv1, 'Distortion', 0.6); inp(wv1, 'Detail', 2.0)
    lk(nt, uvm, 'Vector', wv1, 'Vector')
    wv2 = N(nt, 'ShaderNodeTexWave')
    wv2.bands_direction = 'Y'; wv2.wave_profile = 'SIN'
    inp(wv2, 'Scale', 1.0); inp(wv2, 'Distortion', 0.6); inp(wv2, 'Detail', 2.0)
    lk(nt, uvm, 'Vector', wv2, 'Vector')
    wsum = _sub(nt, wv1, 'Fac', wv2, 'Fac', 'ADD')

    nb = noise(nt, 5.0, 6, 0.6, 0.3, (co, 'Object'))
    nm = noise(nt, 34.0, 6, 0.55, 0.0, (co, 'Object'))
    nf = noise(nt, 160.0, 4, 0.5, 0.0, (co, 'Object'))

    base4 = (base[0], base[1], base[2], 1)
    # higher weave contrast: the old 0.62 read as a uniform blotch at 1 m
    shade = (base[0] * 0.46, base[1] * 0.46, base[2] * 0.46, 1)
    c0 = mix(nt, wsum, 'Value', base4, shade)
    c0b = mix(nt, nb, 'Fac', (c0, 'Result'),
              (base[0] * 0.78, base[1] * 0.80, base[2] * 0.76, 1))

    if pattern == 'floral':
        # A printed day-dress floral.  The first pass used blossom/leaf colours only a
        # shade off the cloth base, so at any distance it read as amorphous mud blobs
        # rather than flowers.  Three things fixed that: a cream blossom with roughly 3x
        # the base's luminance, a rust centre, and a petal edge that is scalloped by a
        # noise offset on the Voronoi distance instead of being a perfect circle.
        v = N(nt, 'ShaderNodeTexVoronoi')
        v.feature = 'F1'
        inp(v, 'Scale', 13.0)
        inp(v, 'Randomness', 0.90)
        lk(nt, co, 'Object', v, 'Vector')
        # scalloped petal edge: d' = d + 0.022 * (n - 0.5)
        pn = noise(nt, 78.0, 4, 0.55, 0.0, (co, 'Object'))
        pn2 = _sub(nt, pn, 'Fac', 0.5, op='SUBTRACT', clamp=False)
        pn3 = _sub(nt, pn2, 'Value', 0.030, op='MULTIPLY', clamp=False)
        dj = _sub(nt, v, 'Distance', pn3, 'Value', 'ADD', clamp=False)
        fr = ramp(nt, dj, 'Value', [(0.030, (1, 1, 1, 1)), (0.046, (0, 0, 0, 1))])
        c0b = mix(nt, fr, 'Color', (c0b, 'Result'), (0.585, 0.545, 0.462, 1))
        # petal separations: a ring of shadow just inside the blossom edge
        fr1 = ramp(nt, dj, 'Value', [(0.020, (0, 0, 0, 1)), (0.030, (1, 1, 1, 1)),
                                     (0.041, (0, 0, 0, 1))])
        c0b = mix(nt, fr1, 'Color', (c0b, 'Result'), (0.330, 0.288, 0.230, 1))
        # rust-red centre
        fr0 = ramp(nt, v, 'Distance', [(0.008, (1, 1, 1, 1)), (0.017, (0, 0, 0, 1))])
        c0b = mix(nt, fr0, 'Color', (c0b, 'Result'), (0.320, 0.110, 0.070, 1))
        # leaf sprigs between the blossoms
        v2 = N(nt, 'ShaderNodeTexVoronoi'); v2.feature = 'F1'
        inp(v2, 'Scale', 27.0)
        m2 = N(nt, 'ShaderNodeMapping'); inp(m2, 'Location', (3.1, 1.7, 0.4))
        inp(m2, 'Scale', (1.0, 1.0, 2.1))
        lk(nt, co, 'Object', m2, 'Vector'); lk(nt, m2, 'Vector', v2, 'Vector')
        fr2 = ramp(nt, v2, 'Distance', [(0.010, (1, 1, 1, 1)), (0.024, (0, 0, 0, 1))])
        # leaves must not sit on top of the blossoms
        fr2b = _sub(nt, fr2, 'Color', fr, 'Color', 'SUBTRACT')
        c0b = mix(nt, fr2b, 'Value', (c0b, 'Result'), (0.062, 0.110, 0.052, 1))
    elif pattern == 'twill':
        # heavy diagonal twill for the fatigues
        tw = N(nt, 'ShaderNodeTexWave')
        tw.bands_direction = 'DIAGONAL'; tw.wave_profile = 'SAW'
        inp(tw, 'Scale', 1.0); inp(tw, 'Distortion', 1.2); inp(tw, 'Detail', 3.0)
        lk(nt, uvm, 'Vector', tw, 'Vector')
        tr = ramp(nt, tw, 'Fac', [(0.30, (0, 0, 0, 1)), (0.62, (1, 1, 1, 1))])
        c0b = mix(nt, tr, 'Color', (c0b, 'Result'),
                  (base[0] * 1.35, base[1] * 1.32, base[2] * 1.22, 1))
        wsum = _sub(nt, wsum, 'Value', tw, 'Fac', 'ADD')
    elif pattern == 'camo':
        nc = noise(nt, 11.0, 4, 0.7, 0.5, (co, 'Object'))
        cr = ramp(nt, nc, 'Fac', [(0.44, (0, 0, 0, 1)), (0.50, (1, 1, 1, 1))])
        c0b = mix(nt, cr, 'Color', (c0b, 'Result'),
                  (base[0] * 0.58, base[1] * 0.70, base[2] * 0.46, 1))

    # grime: general soiling plus heavy dirt low down
    grime = ramp(nt, nm, 'Fac', [(0.35, (0, 0, 0, 1)), (0.75, (1, 1, 1, 1))])
    c1 = mix(nt, grime, 'Color', (c0b, 'Result'), (dirt[0], dirt[1], dirt[2], 1))
    lowz = N(nt, 'ShaderNodeMapRange')
    lk(nt, sep, 'Z', lowz, 'Value')
    lowz.inputs[1].default_value = 0.95; lowz.inputs[2].default_value = 0.15; lowz.clamp = True
    lowm = _sub(nt, lowz, 'Result', nb, 'Fac', 'MULTIPLY')
    c2 = mix(nt, lowm, 'Value', (c1, 'Result'),
             (dirt[0] * 0.7, dirt[1] * 0.7, dirt[2] * 0.7, 1))

    # ambient occlusion in the folds
    ao = N(nt, 'ShaderNodeAmbientOcclusion'); ao.samples = 8
    inp(ao, 'Distance', 0.05)
    aor = ramp(nt, ao, 'Fac', [(0.15, (1, 1, 1, 1)), (0.92, (0, 0, 0, 1))])
    c3 = mix(nt, aor, 'Color', (c2, 'Result'), (dirt[0] * 0.30, dirt[1] * 0.30, dirt[2] * 0.30, 1))

    # blood soaked through around the torso wounds
    bz_lo = N(nt, 'ShaderNodeMapRange')
    lk(nt, sep, 'Z', bz_lo, 'Value')
    bz_lo.inputs[1].default_value = 0.96; bz_lo.inputs[2].default_value = 1.12
    bz_lo.clamp = True
    bz_hi = N(nt, 'ShaderNodeMapRange')
    lk(nt, sep, 'Z', bz_hi, 'Value')
    bz_hi.inputs[1].default_value = 1.44; bz_hi.inputs[2].default_value = 1.22
    bz_hi.clamp = True
    bz = _sub(nt, bz_lo, 'Result', bz_hi, 'Result', 'MULTIPLY')
    bsp = noise(nt, 8.0, 6, 0.6, 0.0, (co, 'Object'))
    bspr = ramp(nt, bsp, 'Fac', [(0.36, (0, 0, 0, 1)), (0.70, (1, 1, 1, 1))])
    bm = _sub(nt, bz, 'Value', bspr, 'Color', 'MULTIPLY')
    bm2 = _sub(nt, bm, 'Value', blood, op='MULTIPLY')
    c4 = mix(nt, bm2, 'Value', (c3, 'Result'), (0.072, 0.030, 0.023, 1))
    lk(nt, c4, 'Result', bsdf, 'Base Color')

    rr = ramp(nt, nf, 'Fac', [(0.2, (0.72, 0.72, 0.72, 1)), (0.85, (0.95, 0.95, 0.95, 1))])
    lk(nt, rr, 'Color', bsdf, 'Roughness')
    inp(bsdf, 'Specular IOR Level', 0.3)

    b1 = N(nt, 'ShaderNodeBump')
    inp(b1, 'Strength', weave * 0.5); inp(b1, 'Distance', 0.0016)
    lk(nt, wsum, 'Value', b1, 'Height')
    b2 = N(nt, 'ShaderNodeBump')
    inp(b2, 'Strength', 0.55 * wear); inp(b2, 'Distance', 0.014)
    lk(nt, nm, 'Fac', b2, 'Height')
    lk(nt, b1, 'Normal', b2, 'Normal')
    lk(nt, b2, 'Normal', bsdf, 'Normal')
    return mat


def leather_material(mat, ob, base=(0.030, 0.026, 0.021), uv_scale=90.0):
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
            nt.nodes.remove(n)
    bsdf = nt.nodes['Principled BSDF']
    co = N(nt, 'ShaderNodeTexCoord')
    v = N(nt, 'ShaderNodeTexVoronoi'); v.feature = 'DISTANCE_TO_EDGE'
    inp(v, 'Scale', 220.0)
    lk(nt, co, 'Object', v, 'Vector')
    nb = noise(nt, 12.0, 6, 0.6, 0.2, (co, 'Object'))
    c = mix(nt, nb, 'Fac', (base[0], base[1], base[2], 1),
            (base[0] * 1.9, base[1] * 1.9, base[2] * 1.8, 1))
    ao = N(nt, 'ShaderNodeAmbientOcclusion'); ao.samples = 8
    inp(ao, 'Distance', 0.04)
    aor = ramp(nt, ao, 'Fac', [(0.3, (1, 1, 1, 1)), (0.9, (0, 0, 0, 1))])
    c2 = mix(nt, aor, 'Color', (c, 'Result'), (0.02, 0.016, 0.012, 1))
    lk(nt, c2, 'Result', bsdf, 'Base Color')
    rr = ramp(nt, nb, 'Fac', [(0.2, (0.40, 0.40, 0.40, 1)), (0.8, (0.75, 0.75, 0.75, 1))])
    lk(nt, rr, 'Color', bsdf, 'Roughness')
    b1 = N(nt, 'ShaderNodeBump')
    inp(b1, 'Strength', 0.5); inp(b1, 'Distance', 0.003)
    lk(nt, v, 'Distance', b1, 'Height')
    lk(nt, b1, 'Normal', bsdf, 'Normal')
    return mat


def hair_material(mat, ob, base=(0.017, 0.013, 0.010)):
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
            nt.nodes.remove(n)
    bsdf = nt.nodes['Principled BSDF']
    co = N(nt, 'ShaderNodeTexCoord')
    m = N(nt, 'ShaderNodeMapping'); inp(m, 'Scale', (60.0, 60.0, 8.0))
    lk(nt, co, 'Object', m, 'Vector')
    n1 = noise(nt, 6.0, 8, 0.7, 0.0)
    lk(nt, m, 'Vector', n1, 'Vector')
    c = mix(nt, n1, 'Fac', (base[0], base[1], base[2], 1),
            (base[0] * 3.0, base[1] * 2.6, base[2] * 2.2, 1))
    lk(nt, c, 'Result', bsdf, 'Base Color')
    inp(bsdf, 'Roughness', 0.62)
    b = N(nt, 'ShaderNodeBump')
    inp(b, 'Strength', 0.7); inp(b, 'Distance', 0.004)
    lk(nt, n1, 'Fac', b, 'Height')
    lk(nt, b, 'Normal', bsdf, 'Normal')
    return mat


# --- simple (unbaked, already glTF-safe) materials --------------------------------------

def simple(name, color, roughness=0.6, metallic=0.0, emission=None, strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = roughness
    b.inputs['Metallic'].default_value = metallic
    if emission:
        b.inputs['Emission Color'].default_value = (*emission, 1)
        b.inputs['Emission Strength'].default_value = strength
    return mat
