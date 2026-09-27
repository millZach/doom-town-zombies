"""Procedural, seamlessly-tileable texture library for Doom Town, baked to PNG once and cached.

Seamlessness trick: every noise/voronoi is 4D and sampled on a torus built from the UV --
vector = (cos(2pi.u).ru, sin(2pi.u).ru, cos(2pi.v).rv), W = sin(2pi.v).rv with ru = fu/2pi.
`fu`/`fv` are then literally "number of noise cycles across the tile" in each axis, so anisotropic
detail (wood grain, rain streaks) stays perfectly tileable. Structured patterns (clapboard courses,
shingle tabs, floor planks, tiles) use fract() of the UV with an integer period, which tiles too.

Each entry declares `m` = how many metres of real surface one tile covers; lib_map uses that for
world-scale cube-projected UVs so nothing stretches.
"""
import bpy, os, sys, math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import bake_tileable, pbr_material, TEX_CACHE  # noqa: E402
import lib_decals as DEC  # noqa: E402

TAU = 6.283185307179586


# --------------------------------------------------------------------------- node helpers
def nd(nt, idname, props=None, ins=None):
    n = nt.nodes.new(idname)
    if props:
        for k, v in props.items():
            setattr(n, k, v)
    if ins:
        for k, v in ins.items():
            sock = n.inputs[k]
            dv = sock.default_value
            if hasattr(dv, '__len__'):
                if not hasattr(v, '__len__'):
                    v = (v,) * len(dv)
                elif len(v) == 3 and len(dv) == 4:
                    v = (*v, 1.0)
            sock.default_value = v
    return n


def lk(nt, a, b):
    nt.links.new(a, b)


def _set(nt, sock, v):
    if hasattr(v, 'is_output'):
        lk(nt, v, sock)
    else:
        dv = sock.default_value
        if hasattr(dv, '__len__'):
            if not hasattr(v, '__len__'):
                v = (v,) * len(dv)
            elif len(v) == 3 and len(dv) == 4:
                v = (*v, 1.0)
        sock.default_value = v


def mth(nt, op, a, b=None, c=None, clamp=False):
    n = nd(nt, 'ShaderNodeMath', {'operation': op, 'use_clamp': clamp})
    for i, v in enumerate((a, b, c)):
        if v is not None:
            _set(nt, n.inputs[i], v)
    return n.outputs[0]


def mix(nt, fac, c1, c2, blend='MIX'):
    n = nd(nt, 'ShaderNodeMixRGB', {'blend_type': blend})
    _set(nt, n.inputs['Factor'], fac)
    _set(nt, n.inputs['Color1'], c1)
    _set(nt, n.inputs['Color2'], c2)
    return n.outputs['Color']


def ramp(nt, fac, stops, interp='LINEAR'):
    n = nd(nt, 'ShaderNodeValToRGB')
    n.color_ramp.interpolation = interp
    el = n.color_ramp.elements
    while len(el) > 1:
        el.remove(el[-1])
    for i, (p, c) in enumerate(stops):
        e = el[0] if i == 0 else el.new(min(max(p, 0.0), 1.0))
        e.position = min(max(p, 0.0), 1.0)
        e.color = (*c, 1.0) if len(c) == 3 else c
    lk(nt, fac, n.inputs['Factor'])
    return n.outputs['Color']


def bw(nt, fac, stops, interp='LINEAR'):
    return ramp(nt, fac, [(p, (v, v, v)) for p, v in stops], interp)


def con(nt, x, lo=0.38, hi=0.62, out0=0.0, out1=1.0):
    """Remap + clamp: the workhorse for turning low-contrast fractal noise into usable masks."""
    n = nd(nt, 'ShaderNodeMapRange', {'clamp': True})
    _set(nt, n.inputs['Value'], x)
    n.inputs['From Min'].default_value = lo
    n.inputs['From Max'].default_value = hi
    n.inputs['To Min'].default_value = out0
    n.inputs['To Max'].default_value = out1
    return n.outputs['Result']


def uvxy(nt):
    uv = nd(nt, 'ShaderNodeUVMap')
    sep = nd(nt, 'ShaderNodeSeparateXYZ')
    lk(nt, uv.outputs['UV'], sep.inputs['Vector'])
    return sep.outputs['X'], sep.outputs['Y']


def seam(nt, fu, fv):
    u, v = uvxy(nt)
    a = mth(nt, 'MULTIPLY', u, TAU)
    b = mth(nt, 'MULTIPLY', v, TAU)
    ru, rv = fu / TAU, fv / TAU
    x = mth(nt, 'MULTIPLY', mth(nt, 'COSINE', a), ru)
    y = mth(nt, 'MULTIPLY', mth(nt, 'SINE', a), ru)
    z = mth(nt, 'MULTIPLY', mth(nt, 'COSINE', b), rv)
    w = mth(nt, 'MULTIPLY', mth(nt, 'SINE', b), rv)
    c = nd(nt, 'ShaderNodeCombineXYZ')
    lk(nt, x, c.inputs['X']); lk(nt, y, c.inputs['Y']); lk(nt, z, c.inputs['Z'])
    return c.outputs['Vector'], w


def noise(nt, fu, fv, detail=8.0, rough=0.5, dist=0.0, lac=2.0):
    vec, w = seam(nt, fu, fv)
    n = nd(nt, 'ShaderNodeTexNoise', {'noise_dimensions': '4D'},
           {'Scale': 1.0, 'Detail': detail, 'Roughness': rough, 'Distortion': dist, 'Lacunarity': lac})
    lk(nt, vec, n.inputs['Vector'])
    lk(nt, w, n.inputs['W'])
    return n.outputs['Factor']


def voro(nt, fu, fv, feature='F1', randomness=1.0, smooth=0.0):
    vec, w = seam(nt, fu, fv)
    n = nd(nt, 'ShaderNodeTexVoronoi', {'voronoi_dimensions': '4D', 'feature': feature},
           {'Scale': 1.0, 'Randomness': randomness})
    if 'Smoothness' in n.inputs:
        n.inputs['Smoothness'].default_value = smooth
    lk(nt, vec, n.inputs['Vector'])
    lk(nt, w, n.inputs['W'])
    return n


def cellrand(nt, fu, fv, randomness=1.0):
    vn = voro(nt, fu, fv, 'F1', randomness)
    s = nd(nt, 'ShaderNodeSeparateXYZ')
    lk(nt, vn.outputs['Color'], s.inputs['Vector'])
    return s.outputs['X'], vn


def flakes(nt, fu, fv, cluster_f=3.0, bias=None, amount=0.3, soft=0.03):
    """Hard-edged paint-flake mask covering roughly `amount` of the surface, plus its dark rim."""
    cr, vn = cellrand(nt, fu, fv)
    big = con(nt, noise(nt, cluster_f, cluster_f, detail=5, rough=0.6), 0.36, 0.64)
    score = mth(nt, 'MULTIPLY', cr, big)
    if bias is not None:
        score = mth(nt, 'ADD', score, mth(nt, 'MULTIPLY', bias, 0.45))
    t = 1.0 - amount
    mask = con(nt, score, t, t + soft)
    rim = bw(nt, vn.outputs['Distance'], [(0.0, 1.0), (0.22, 0.0)])
    return mask, rim


def frac(nt, val, n_rows):
    return mth(nt, 'FRACT', mth(nt, 'MULTIPLY', val, float(n_rows)))


def idx(nt, val, n_rows):
    return mth(nt, 'FLOOR', mth(nt, 'MULTIPLY', val, float(n_rows)))


def hsh(nt, a, b=None):
    """Deterministic 0..1 hash of one or two integer indices (per-brick/plank randomisation)."""
    x = mth(nt, 'MULTIPLY', a, 12.9898)
    if b is not None:
        x = mth(nt, 'ADD', x, mth(nt, 'MULTIPLY', b, 78.2331))
    return mth(nt, 'FRACT', mth(nt, 'MULTIPLY', mth(nt, 'SINE', x), 43758.5453))


def band(nt, f, w=0.03):
    """1 in the middle of a fract() band, 0 at its two edges (joint/groove lines)."""
    return bw(nt, f, [(0.0, 0.0), (w, 1.0), (1.0 - w, 1.0), (1.0, 0.0)])


def finish(nt, color, rough, height=None, bump=1.0, dist=0.06, metallic=0.0):
    b = nd(nt, 'ShaderNodeBsdfPrincipled', ins={'Metallic': metallic})
    out = nt.nodes.get('Material Output') or nd(nt, 'ShaderNodeOutputMaterial')
    _set(nt, b.inputs['Base Color'], color)
    _set(nt, b.inputs['Roughness'], rough)
    if height is not None:
        bn = nd(nt, 'ShaderNodeBump', ins={'Strength': bump, 'Distance': dist})
        _set(nt, bn.inputs['Height'], height)
        lk(nt, bn.outputs['Normal'], b.inputs['Normal'])
    lk(nt, b.outputs['BSDF'], out.inputs['Surface'])


def _clear(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.bl_idname != 'ShaderNodeOutputMaterial':
            nt.nodes.remove(n)
    return nt


def scale(c, k, add=0.0):
    return tuple(min(1.0, max(0.0, v * k + add)) for v in c)


# =========================================================================== surfaces
def siding(paint, primer=(0.42, 0.395, 0.360), rows=8, dirty=0.55, peel=0.30):
    """Clapboard lap siding with peeling paint. Tile = 2 m -> `rows` boards."""
    def build(mat):
        nt = _clear(mat)
        u, v = uvxy(nt)
        rw = frac(nt, v, rows)
        boardid = idx(nt, v, rows)
        prof = bw(nt, rw, [(0.0, 0.08), (0.020, 0.30), (0.048, 1.00), (0.97, 0.60), (1.0, 0.55)])
        seg = idx(nt, u, 1)
        bh = hsh(nt, boardid, seg)
        grain = noise(nt, 4, rows * 24.0, detail=6, rough=0.75)
        warp = con(nt, noise(nt, 2.6, 2.6, detail=5), 0.36, 0.64)
        bias = bw(nt, rw, [(0.0, 1.0), (0.20, 0.15), (1.0, 0.0)])
        pm, rim = flakes(nt, 16, 16 * rows / 8.0, 3.0, bias, amount=peel, soft=0.02)
        dirt = con(nt, noise(nt, 6, 2.6, detail=9, rough=0.72), 0.40, 0.74)
        streak = con(nt, noise(nt, 70, 2.0, detail=5, rough=0.8), 0.36, 0.70)
        tone = mix(nt, warp, scale(paint, 0.72), scale(paint, 1.24, 0.05))
        tone = mix(nt, mth(nt, 'MULTIPLY', bh, 0.45), tone, scale(paint, 0.80))
        tone = mix(nt, mth(nt, 'MULTIPLY', grain, 0.22), tone, scale(paint, 0.88))
        wood = mix(nt, mth(nt, 'MULTIPLY', grain, 0.95), primer, scale(primer, 0.55))
        col = mix(nt, pm, tone, wood)
        col = mix(nt, mth(nt, 'MULTIPLY', mth(nt, 'MULTIPLY', rim, pm), 0.9), col, (0.085, 0.072, 0.060))
        col = mix(nt, bw(nt, rw, [(0.0, 1.0), (0.030, 0.0)]), col, (0.040, 0.035, 0.030))
        gr = mth(nt, 'MULTIPLY', mth(nt, 'ADD', mth(nt, 'MULTIPLY', dirt, 0.6),
                                      mth(nt, 'MULTIPLY', mth(nt, 'MULTIPLY', dirt, streak), 0.9)), dirty)
        col = mix(nt, gr, col, (0.32, 0.28, 0.23), 'MULTIPLY')
        rgh = mix(nt, pm, mix(nt, grain, 0.45, 0.60), 0.92)
        h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', prof, 0.85), mth(nt, 'MULTIPLY', grain, 0.13))
        h = mth(nt, 'SUBTRACT', h, mth(nt, 'MULTIPLY', pm, 0.10))
        finish(nt, col, rgh, h, bump=0.9, dist=0.05)
    return build


def shingles(mat):
    """Asphalt 3-tab roof shingles: 2 m tile = 13 courses (0.15 m exposure) of 4 tabs (0.5 m)."""
    nt = _clear(mat)
    u, v = uvxy(nt)
    rows, cols = 13.0, 4.0
    rw = frac(nt, v, rows)
    rowid = idx(nt, v, rows)
    off = mth(nt, 'MULTIPLY', mth(nt, 'MODULO', rowid, 2.0), 0.5)
    uu = mth(nt, 'ADD', mth(nt, 'MULTIPLY', u, cols), off)
    tab = mth(nt, 'FRACT', uu)
    tabid = mth(nt, 'MODULO', mth(nt, 'FLOOR', uu), cols)
    th = hsh(nt, tabid, rowid)
    th2 = hsh(nt, mth(nt, 'ADD', tabid, 5.0), mth(nt, 'ADD', rowid, 11.0))
    # narrow slot between tabs
    slot = bw(nt, tab, [(0.0, 0.0), (0.012, 1.0), (0.988, 1.0), (1.0, 0.0)])
    # each course drops a hard shadow on the one below, and its own butt edge is lifted
    shadow = bw(nt, rw, [(0.0, 0.0), (0.16, 1.0)])
    butt = bw(nt, rw, [(0.0, 1.0), (0.05, 0.0), (0.93, 0.0), (1.0, 0.55)])
    grit = noise(nt, 190, 190, detail=4, rough=0.85)
    blotch = con(nt, noise(nt, 3.5, 3.5, detail=7, rough=0.6, dist=0.6), 0.38, 0.62)
    wear = con(nt, noise(nt, 9, 9, detail=8, rough=0.7), 0.42, 0.66)
    base = mix(nt, blotch, (0.036, 0.034, 0.033), (0.088, 0.081, 0.073))
    base = mix(nt, th, base, (0.021, 0.020, 0.019))
    base = mix(nt, mth(nt, 'MULTIPLY', th2, 0.7), base, (0.105, 0.092, 0.076))
    base = mix(nt, con(nt, grit, 0.42, 0.74, 0.0, 0.75), base, (0.180, 0.158, 0.125))
    base = mix(nt, mth(nt, 'MULTIPLY', wear, 0.55), base, (0.145, 0.112, 0.088))
    col = mix(nt, mth(nt, 'SUBTRACT', 1.0, shadow), base, (0.007, 0.0068, 0.0066))
    col = mix(nt, mth(nt, 'SUBTRACT', 1.0, slot), col, (0.005, 0.005, 0.005))
    col = mix(nt, mth(nt, 'MULTIPLY', butt, 0.30), col, (0.105, 0.094, 0.080))
    h = mth(nt, 'MULTIPLY', shadow, slot)
    h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', h, 0.9), mth(nt, 'MULTIPLY', grit, 0.16))
    finish(nt, col, mix(nt, grit, 0.82, 0.96), h, bump=1.0, dist=0.06)


def brick(mat):
    nt = _clear(mat)
    uv = nd(nt, 'ShaderNodeUVMap')
    b = nd(nt, 'ShaderNodeTexBrick', {'offset': 0.5, 'squash': 1.0},
           ins={'Scale': 1.0, 'Brick Width': 0.20, 'Row Height': 0.0833,
                'Mortar Size': 0.010, 'Mortar Smooth': 0.30, 'Bias': 0.0,
                'Color1': (0.255, 0.086, 0.060), 'Color2': (0.130, 0.050, 0.040),
                'Mortar': (0.250, 0.238, 0.220)})
    lk(nt, uv.outputs['UV'], b.inputs['Vector'])
    grain = noise(nt, 110, 110, detail=5, rough=0.8)
    stain = con(nt, noise(nt, 3.0, 3.0, detail=8, rough=0.65, dist=0.8), 0.40, 0.66)
    soot = con(nt, noise(nt, 5, 2.2, detail=9, rough=0.72), 0.48, 0.78)
    col = mix(nt, mth(nt, 'MULTIPLY', grain, 0.40), b.outputs['Color'], (0.115, 0.050, 0.040))
    col = mix(nt, mth(nt, 'MULTIPLY', stain, 0.45), col, (0.30, 0.27, 0.24), 'MULTIPLY')
    col = mix(nt, mth(nt, 'MULTIPLY', soot, 0.85), col, (0.11, 0.100, 0.092), 'MULTIPLY')
    h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', b.outputs['Factor'], 0.85), mth(nt, 'MULTIPLY', grain, 0.15))
    finish(nt, col, mix(nt, grain, 0.74, 0.90), h, bump=1.0, dist=0.06)


def concrete(tint=(0.42, 0.415, 0.400), cracky=1.0, board=False, rust=0.0, joints=0.0,
             pore_amt=1.0, grain_amt=1.0):
    def build(mat):
        nt = _clear(mat)
        u, v = uvxy(nt)
        blotch = con(nt, noise(nt, 2.6, 2.6, detail=9, rough=0.6, dist=0.4), 0.36, 0.64)
        med = con(nt, noise(nt, 8, 8, detail=8, rough=0.65), 0.40, 0.62)
        fine = noise(nt, 70, 70, detail=6, rough=0.8)
        pores = voro(nt, 46, 46, 'F1')
        poresm = bw(nt, pores.outputs['Distance'], [(0.0, 1.0), (0.14, 0.0)])
        crack = voro(nt, 3, 3, 'DISTANCE_TO_EDGE')
        sparse = con(nt, noise(nt, 3.2, 3.2, detail=6, rough=0.6), 0.54, 0.60)
        crackm = mth(nt, 'MULTIPLY', bw(nt, crack.outputs['Distance'], [(0.0, 1.0), (0.010, 0.0)]), sparse)
        crack2 = voro(nt, 17, 17, 'DISTANCE_TO_EDGE')
        crackm = mth(nt, 'MAXIMUM', crackm, mth(nt, 'MULTIPLY',
                     bw(nt, crack2.outputs['Distance'], [(0.0, 1.0), (0.020, 0.0)]),
                     con(nt, noise(nt, 4.4, 4.4, detail=6), 0.56, 0.64)))
        col = mix(nt, blotch, scale(tint, 0.76), scale(tint, 1.20))
        col = mix(nt, mth(nt, 'MULTIPLY', med, 0.55), col, scale(tint, 0.62))
        col = mix(nt, mth(nt, 'MULTIPLY', fine, 0.32 * grain_amt), col, scale(tint, 0.86))
        col = mix(nt, mth(nt, 'MULTIPLY', poresm, 0.35 * pore_amt), col, scale(tint, 0.62))
        col = mix(nt, mth(nt, 'MULTIPLY', crackm, 0.85 * cracky), col, (0.050, 0.046, 0.044))
        h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', fine, 0.12 * grain_amt), mth(nt, 'MULTIPLY', med, 0.25))
        h = mth(nt, 'SUBTRACT', h, mth(nt, 'MULTIPLY', crackm, 0.6 * cracky))
        h = mth(nt, 'SUBTRACT', h, mth(nt, 'MULTIPLY', poresm, 0.30 * pore_amt))
        if board:
            bd = band(nt, frac(nt, v, 8), 0.035)
            col = mix(nt, mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', 1.0, bd), 0.6), col, (0.135, 0.130, 0.125))
            col = mix(nt, mth(nt, 'MULTIPLY', band(nt, frac(nt, u, 3), 0.008), 0.0), col, col)
            h = mth(nt, 'ADD', h, mth(nt, 'MULTIPLY', bd, 0.30))
            tie = mth(nt, 'MULTIPLY', bw(nt, frac(nt, v, 8), [(0.42, 0.0), (0.48, 1.0), (0.54, 0.0)]),
                      bw(nt, frac(nt, u, 4), [(0.42, 0.0), (0.48, 1.0), (0.54, 0.0)]))
            col = mix(nt, mth(nt, 'MULTIPLY', tie, 0.8), col, (0.14, 0.095, 0.060))
            h = mth(nt, 'SUBTRACT', h, mth(nt, 'MULTIPLY', tie, 0.5))
        if joints > 0.0:
            jt = mth(nt, 'MINIMUM', band(nt, frac(nt, u, joints), 0.010), band(nt, frac(nt, v, joints), 0.010))
            col = mix(nt, mth(nt, 'SUBTRACT', 1.0, jt), col, (0.085, 0.080, 0.078))
            h = mth(nt, 'SUBTRACT', h, mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', 1.0, jt), 0.55))
        if rust > 0.0:
            st = con(nt, noise(nt, 60, 1.8, detail=7, rough=0.8), 0.50, 0.66)
            st2 = con(nt, noise(nt, 5, 2.2, detail=5), 0.48, 0.62)
            col = mix(nt, mth(nt, 'MULTIPLY', mth(nt, 'MULTIPLY', st, st2), rust), col, (0.190, 0.080, 0.032))
        finish(nt, col, mix(nt, fine, 0.70, 0.90), h, bump=0.55, dist=0.018)
    return build


def asphalt(mat):
    nt = _clear(mat)
    agg = voro(nt, 130, 130, 'F1', 1.0)
    aggm = bw(nt, agg.outputs['Distance'], [(0.0, 1.0), (0.40, 0.0)])
    fine = noise(nt, 220, 220, detail=4, rough=0.85)
    patch = con(nt, noise(nt, 2.4, 2.4, detail=8, rough=0.6, dist=0.6), 0.38, 0.64)
    patch2 = con(nt, noise(nt, 6.0, 6.0, detail=8, rough=0.65), 0.42, 0.62)
    # alligator cracking, only in a few patches
    c1 = voro(nt, 6, 6, 'DISTANCE_TO_EDGE')
    c2 = voro(nt, 22, 22, 'DISTANCE_TO_EDGE')
    sp1 = con(nt, noise(nt, 2.8, 2.8, detail=6, rough=0.6), 0.52, 0.60)
    sp2 = con(nt, noise(nt, 4.0, 4.0, detail=7, rough=0.6), 0.57, 0.63)
    cm = mth(nt, 'MAXIMUM',
             mth(nt, 'MULTIPLY', bw(nt, c1.outputs['Distance'], [(0.0, 1.0), (0.013, 0.0)]), sp1),
             mth(nt, 'MULTIPLY', bw(nt, c2.outputs['Distance'], [(0.0, 1.0), (0.030, 0.0)]), sp2))
    base = mix(nt, patch, (0.040, 0.039, 0.038), (0.088, 0.085, 0.080))
    base = mix(nt, mth(nt, 'MULTIPLY', patch2, 0.6), base, (0.058, 0.056, 0.054))
    base = mix(nt, mth(nt, 'MULTIPLY', aggm, 0.70), base, (0.150, 0.140, 0.124))
    base = mix(nt, con(nt, fine, 0.45, 0.70, 0.0, 0.50), base, (0.115, 0.110, 0.100))
    col = mix(nt, mth(nt, 'MULTIPLY', cm, 0.92), base, (0.009, 0.0088, 0.0086))
    h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', aggm, 0.55), mth(nt, 'MULTIPLY', fine, 0.35))
    h = mth(nt, 'SUBTRACT', h, mth(nt, 'MULTIPLY', cm, 0.95))
    rgh = mix(nt, aggm, mix(nt, patch, 0.60, 0.82), 0.92)
    finish(nt, col, rgh, h, bump=1.0, dist=0.05)


def ground(dry=(0.190, 0.135, 0.078), pale=(0.360, 0.290, 0.190),
           grass=(0.105, 0.098, 0.036), tufts=0.85, scorch=0.0):
    def build(mat):
        nt = _clear(mat)
        big = con(nt, noise(nt, 2.2, 2.2, detail=9, rough=0.65, dist=0.4), 0.34, 0.66)
        med = con(nt, noise(nt, 8, 8, detail=9, rough=0.68), 0.36, 0.66)
        fine = noise(nt, 65, 65, detail=6, rough=0.85)
        tuft = con(nt, noise(nt, 17, 17, detail=8, rough=0.72, dist=1.4), 0.52, 0.62)
        blade = noise(nt, 210, 30, detail=4, rough=0.9)
        blade2 = noise(nt, 30, 210, detail=4, rough=0.9)
        peb, pebr = voro(nt, 26, 26, 'F1', 1.0), cellrand(nt, 26, 26)[0]
        pebm = mth(nt, 'MULTIPLY', bw(nt, peb.outputs['Distance'], [(0.0, 1.0), (0.34, 0.0)]),
                   con(nt, noise(nt, 6, 6, detail=5), 0.46, 0.56))
        grit = voro(nt, 85, 85, 'F1', 1.0)
        gritm = bw(nt, grit.outputs['Distance'], [(0.0, 1.0), (0.30, 0.0)])
        mud = voro(nt, 9, 9, 'DISTANCE_TO_EDGE')
        mudm = mth(nt, 'MULTIPLY', bw(nt, mud.outputs['Distance'], [(0.0, 1.0), (0.020, 0.0)]),
                   con(nt, noise(nt, 3.4, 3.4, detail=6), 0.48, 0.58))
        col = mix(nt, big, dry, pale)
        col = mix(nt, mth(nt, 'MULTIPLY', med, 0.85), col, scale(dry, 0.50))
        col = mix(nt, mth(nt, 'MULTIPLY', mudm, 0.8), col, scale(dry, 0.35))
        col = mix(nt, mth(nt, 'MULTIPLY', gritm, 0.55), col, scale(pale, 1.15, 0.03))
        col = mix(nt, pebm, col, mix(nt, pebr, (0.360, 0.340, 0.310), (0.135, 0.125, 0.115)))
        gcol = mix(nt, con(nt, blade, 0.40, 0.62), grass, scale(grass, 2.1, 0.02))
        gcol = mix(nt, con(nt, blade2, 0.42, 0.60, 0.0, 0.7), gcol, scale(grass, 0.45))
        col = mix(nt, mth(nt, 'MULTIPLY', tuft, tufts), col, gcol)
        col = mix(nt, con(nt, fine, 0.40, 0.70, 0.0, 0.45), col, scale(dry, 0.62))
        if scorch > 0:
            sm = con(nt, noise(nt, 3.0, 3.0, detail=7, rough=0.62), 0.42, 0.64)
            col = mix(nt, mth(nt, 'MULTIPLY', sm, scorch), col, (0.020, 0.018, 0.017))
        h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', med, 0.40), mth(nt, 'MULTIPLY', fine, 0.30))
        h = mth(nt, 'ADD', h, mth(nt, 'MULTIPLY', pebm, 0.80))
        h = mth(nt, 'ADD', h, mth(nt, 'MULTIPLY', gritm, 0.25))
        h = mth(nt, 'SUBTRACT', h, mth(nt, 'MULTIPLY', mudm, 0.55))
        h = mth(nt, 'ADD', h, mth(nt, 'MULTIPLY', mth(nt, 'MULTIPLY', tuft, blade), 0.55))
        finish(nt, col, mix(nt, fine, 0.86, 0.98), h, bump=1.2, dist=0.055)
    return build


def wallpaper(base=(0.640, 0.570, 0.400), motif=(0.430, 0.190, 0.165),
              stripe=True, pitch=12.0, mrows=6.0):
    def build(mat):
        nt = _clear(mat)
        u, v = uvxy(nt)
        col = base
        if stripe:
            st = band(nt, frac(nt, u, pitch), 0.16)
            col = mix(nt, mth(nt, 'MULTIPLY', st, 0.45), col, scale(base, 1.18, 0.03))
            thin = band(nt, frac(nt, u, pitch * 2), 0.03)
            col = mix(nt, mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', 1.0, thin), 0.30), col, scale(motif, 1.1))
        # repeating diamond / starburst motif on a staggered lattice. Every cell gets its own
        # hash-driven strength so the print fades and blooms across the wall instead of stamping
        # an identical diamond every 2.2 m (environment.md #9).
        ri = idx(nt, v, mrows)
        ou = mth(nt, 'MULTIPLY', mth(nt, 'MODULO', ri, 2.0), 0.5)
        uu = mth(nt, 'ADD', mth(nt, 'MULTIPLY', u, mrows * 0.75), ou)
        du = mth(nt, 'ABSOLUTE', mth(nt, 'SUBTRACT', mth(nt, 'FRACT', uu), 0.5))
        dv = mth(nt, 'ABSOLUTE', mth(nt, 'SUBTRACT', frac(nt, v, mrows), 0.5))
        d = mth(nt, 'ADD', du, dv)
        cell = hsh(nt, mth(nt, 'FLOOR', uu), ri)
        fade = con(nt, cell, 0.08, 0.92, 0.45, 1.0)
        petal = mth(nt, 'MULTIPLY', bw(nt, d, [(0.16, 1.0), (0.21, 0.0)]), fade)
        ring = mth(nt, 'MULTIPLY', bw(nt, d, [(0.25, 0.0), (0.28, 1.0), (0.31, 0.0)]), fade)
        dot = mth(nt, 'MULTIPLY', bw(nt, d, [(0.05, 1.0), (0.08, 0.0)]), fade)
        col = mix(nt, mth(nt, 'MULTIPLY', petal, 0.72), col, motif)
        col = mix(nt, mth(nt, 'MULTIPLY', ring, 0.60), col, scale(motif, 0.75))
        col = mix(nt, mth(nt, 'MULTIPLY', dot, 0.85), col, scale(motif, 1.5, 0.08))
        # damage: smoke, water stains, tears revealing plaster
        stain = con(nt, noise(nt, 2.8, 2.8, detail=9, rough=0.65, dist=0.6), 0.44, 0.74)
        col = mix(nt, mth(nt, 'MULTIPLY', stain, 0.85), col, (0.28, 0.22, 0.16), 'MULTIPLY')
        smoke = con(nt, noise(nt, 4, 1.6, detail=9, rough=0.7), 0.48, 0.80)
        col = mix(nt, mth(nt, 'MULTIPLY', smoke, 0.6), col, (0.18, 0.16, 0.15), 'MULTIPLY')
        tear = noise(nt, 4.5, 5.5, detail=8, rough=0.6, dist=1.1)
        tm = con(nt, tear, 0.615, 0.625)
        plasterc = mix(nt, noise(nt, 45, 45, detail=6), (0.470, 0.440, 0.405), (0.330, 0.305, 0.285))
        col = mix(nt, tm, col, plasterc)
        col = mix(nt, mth(nt, 'MULTIPLY', con(nt, tear, 0.598, 0.612), mth(nt, 'SUBTRACT', 1.0, tm)),
                  col, (0.075, 0.065, 0.055))
        fine = noise(nt, 90, 90, detail=5)
        h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', fine, 0.25), mth(nt, 'MULTIPLY', tm, -0.7))
        finish(nt, col, mix(nt, tm, 0.62, 0.90), h, bump=0.55, dist=0.03)
    return build


def woodfloor(mat):
    nt = _clear(mat)
    u, v = uvxy(nt)
    rows = 10.0
    rw = frac(nt, v, rows)
    rowid = idx(nt, v, rows)
    stagger = mth(nt, 'FRACT', mth(nt, 'MULTIPLY', rowid, 0.37))
    uu = mth(nt, 'ADD', mth(nt, 'MULTIPLY', u, 2.0), stagger)
    seg = mth(nt, 'FRACT', uu)
    segid = mth(nt, 'MODULO', mth(nt, 'FLOOR', uu), 2.0)
    ph = hsh(nt, rowid, segid)
    joint = mth(nt, 'MULTIPLY', band(nt, rw, 0.035), band(nt, seg, 0.010))
    grain = noise(nt, 6, rows * 28, detail=7, rough=0.8)
    grain2 = noise(nt, 3, rows * 7, detail=5)
    base = mix(nt, ph, (0.118, 0.068, 0.033), (0.225, 0.140, 0.072))
    base = mix(nt, mth(nt, 'MULTIPLY', grain, 0.75), base, (0.062, 0.034, 0.016))
    base = mix(nt, mth(nt, 'MULTIPLY', grain2, 0.40), base, (0.180, 0.115, 0.058))
    scuff = con(nt, noise(nt, 4, 4, detail=9, rough=0.7, dist=0.5), 0.42, 0.70)
    base = mix(nt, mth(nt, 'MULTIPLY', scuff, 0.85), base, (0.24, 0.20, 0.16), 'MULTIPLY')
    dust = con(nt, noise(nt, 10, 10, detail=8), 0.44, 0.66)
    base = mix(nt, mth(nt, 'MULTIPLY', dust, 0.35), base, (0.285, 0.250, 0.205))
    col = mix(nt, mth(nt, 'SUBTRACT', 1.0, joint), base, (0.016, 0.011, 0.008))
    h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', joint, 0.75), mth(nt, 'MULTIPLY', grain, 0.28))
    finish(nt, col, mix(nt, scuff, 0.80, 0.46), h, bump=0.75, dist=0.04)


def lino(mat):
    nt = _clear(mat)
    u, v = uvxy(nt)
    n = 8.0
    cu, cv = frac(nt, u, n), frac(nt, v, n)
    chk = mth(nt, 'MODULO', mth(nt, 'ADD', idx(nt, u, n), idx(nt, v, n)), 2.0)
    speck = noise(nt, 330, 330, detail=3, rough=0.9)
    light = mix(nt, con(nt, speck, 0.42, 0.62), (0.500, 0.480, 0.430), (0.740, 0.720, 0.660))
    dark = mix(nt, con(nt, speck, 0.42, 0.62), (0.060, 0.058, 0.056), (0.185, 0.178, 0.168))
    col = mix(nt, chk, light, dark)
    grout = mth(nt, 'MULTIPLY', band(nt, cu, 0.012), band(nt, cv, 0.012))
    col = mix(nt, mth(nt, 'SUBTRACT', 1.0, grout), col, (0.045, 0.042, 0.040))
    wear = con(nt, noise(nt, 3.5, 3.5, detail=9, rough=0.65, dist=0.5), 0.44, 0.72)
    col = mix(nt, mth(nt, 'MULTIPLY', wear, 0.9), col, (0.26, 0.22, 0.17), 'MULTIPLY')
    peelm = con(nt, noise(nt, 4.0, 4.0, detail=7, dist=1.2), 0.625, 0.640)
    sub = mix(nt, noise(nt, 60, 60, detail=5), (0.215, 0.160, 0.105), (0.130, 0.095, 0.060))
    col = mix(nt, peelm, col, sub)
    h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', grout, 0.65), mth(nt, 'MULTIPLY', speck, 0.10))
    h = mth(nt, 'SUBTRACT', h, mth(nt, 'MULTIPLY', peelm, 0.5))
    finish(nt, col, mix(nt, wear, 0.32, 0.78), h, bump=0.6, dist=0.025)


def rusted(base=(0.28, 0.28, 0.29), heavy=0.8):
    def build(mat):
        nt = _clear(mat)
        big = con(nt, noise(nt, 3.5, 3.5, detail=9, rough=0.62, dist=0.7), 0.36, 0.64)
        med = con(nt, noise(nt, 13, 13, detail=8, rough=0.7, dist=0.4), 0.38, 0.64)
        fine = noise(nt, 100, 100, detail=5, rough=0.85)
        pit = voro(nt, 40, 40, 'F1', 1.0)
        pitm = mth(nt, 'MULTIPLY', bw(nt, pit.outputs['Distance'], [(0.0, 1.0), (0.28, 0.0)]),
                   con(nt, big, 0.35, 0.65))
        rm = con(nt, big, 0.42 - 0.22 * heavy, 0.70 - 0.22 * heavy)
        rm2 = mth(nt, 'MULTIPLY', rm, con(nt, med, 0.30, 0.70, 0.35, 1.0))
        col = mix(nt, fine, base, scale(base, 1.35))
        rust1 = mix(nt, med, (0.215, 0.080, 0.028), (0.400, 0.175, 0.060))
        rust2 = mix(nt, fine, (0.100, 0.042, 0.020), (0.255, 0.105, 0.040))
        col = mix(nt, rm2, col, rust1)
        col = mix(nt, mth(nt, 'MULTIPLY', con(nt, med, 0.55, 0.78), heavy), col, rust2)
        col = mix(nt, mth(nt, 'MULTIPLY', pitm, 0.75 * heavy), col, (0.055, 0.026, 0.014))
        h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', rm2, 0.35), mth(nt, 'MULTIPLY', fine, 0.30))
        h = mth(nt, 'SUBTRACT', h, mth(nt, 'MULTIPLY', pitm, 0.75))
        finish(nt, col, mix(nt, rm2, 0.36, 0.94), h, bump=0.95, dist=0.03)
    return build


def painted_metal(paint=(0.45, 0.06, 0.05), wear=0.5, dirt_amt=0.55):
    def build(mat):
        nt = _clear(mat)
        big = con(nt, noise(nt, 3.5, 3.5, detail=8, rough=0.6, dist=0.6), 0.36, 0.64)
        fine = noise(nt, 140, 140, detail=5)
        scratch = con(nt, noise(nt, 60, 8, detail=7, rough=0.85), 0.58, 0.70)
        chip, rim = flakes(nt, 22, 22, 3.2, amount=0.16 + 0.34 * wear, soft=0.015)
        dirt = con(nt, noise(nt, 6, 2.6, detail=9, rough=0.72), 0.44, 0.72)
        col = mix(nt, mth(nt, 'MULTIPLY', big, 0.55), paint, scale(paint, 1.30, 0.03))
        col = mix(nt, mth(nt, 'MULTIPLY', scratch, 0.45), col, scale(paint, 1.8, 0.14))
        rust = mix(nt, fine, (0.175, 0.068, 0.026), (0.310, 0.130, 0.048))
        col = mix(nt, chip, col, rust)
        col = mix(nt, mth(nt, 'MULTIPLY', mth(nt, 'MULTIPLY', rim, chip), 0.85), col, (0.085, 0.040, 0.018))
        col = mix(nt, mth(nt, 'MULTIPLY', dirt, dirt_amt), col, (0.22, 0.20, 0.175), 'MULTIPLY')
        h = mth(nt, 'SUBTRACT', mth(nt, 'MULTIPLY', fine, 0.3), mth(nt, 'MULTIPLY', chip, 0.55))
        finish(nt, col, mix(nt, chip, mix(nt, big, 0.24, 0.46), 0.88), h, bump=0.55, dist=0.02)
    return build


def bare_wood(tone=(0.240, 0.180, 0.115), rows=6.0):
    def build(mat):
        nt = _clear(mat)
        u, v = uvxy(nt)
        rw = frac(nt, v, rows)
        rid = idx(nt, v, rows)
        ph = hsh(nt, rid, 3.0)
        grain = noise(nt, 5, rows * 32, detail=7, rough=0.8)
        grain2 = noise(nt, 2.5, rows * 8, detail=5)
        knot = voro(nt, 3, rows * 2.0, 'F1', 1.0)
        knotm = bw(nt, knot.outputs['Distance'], [(0.0, 1.0), (0.14, 0.0)])
        col = mix(nt, ph, scale(tone, 0.52), scale(tone, 1.65))
        col = mix(nt, con(nt, grain, 0.30, 0.72), col, scale(tone, 0.34))
        col = mix(nt, mth(nt, 'MULTIPLY', grain2, 0.55), col, scale(tone, 1.45))
        col = mix(nt, mth(nt, 'MULTIPLY', knotm, 0.8), col, scale(tone, 0.30))
        split = bw(nt, rw, [(0.0, 1.0), (0.030, 0.0), (0.970, 0.0), (1.0, 1.0)])
        col = mix(nt, mth(nt, 'MULTIPLY', split, 0.9), col, (0.035, 0.028, 0.020))
        grime = con(nt, noise(nt, 5, 5, detail=9, rough=0.7), 0.42, 0.70)
        col = mix(nt, mth(nt, 'MULTIPLY', grime, 0.55), col, (0.22, 0.19, 0.16), 'MULTIPLY')
        h = mth(nt, 'SUBTRACT', mth(nt, 'MULTIPLY', grain, 0.55), mth(nt, 'MULTIPLY', split, 0.85))
        h = mth(nt, 'SUBTRACT', h, mth(nt, 'MULTIPLY', knotm, 0.3))
        finish(nt, col, mix(nt, grain, 0.74, 0.94), h, bump=0.85, dist=0.035)
    return build


def painted_wood(paint=(0.78, 0.76, 0.71), rows=6.0, peel=0.35, dirty=0.55):
    def build(mat):
        nt = _clear(mat)
        u, v = uvxy(nt)
        rw = frac(nt, v, rows)
        rid = idx(nt, v, rows)
        ph = hsh(nt, rid, 7.0)
        grain = noise(nt, 5, rows * 30, detail=7, rough=0.8)
        bias = bw(nt, rw, [(0.0, 1.0), (0.14, 0.1), (0.86, 0.1), (1.0, 1.0)])
        pm, rim = flakes(nt, 20, 20, 2.8, bias, amount=peel, soft=0.02)
        wood = mix(nt, mth(nt, 'MULTIPLY', grain, 0.9), (0.235, 0.180, 0.120), (0.120, 0.088, 0.055))
        col = mix(nt, mth(nt, 'MULTIPLY', ph, 0.30), paint, scale(paint, 0.82))
        col = mix(nt, mth(nt, 'MULTIPLY', grain, 0.22), col, scale(paint, 0.86))
        col = mix(nt, pm, col, wood)
        col = mix(nt, mth(nt, 'MULTIPLY', mth(nt, 'MULTIPLY', rim, pm), 0.85), col, (0.080, 0.070, 0.060))
        split = bw(nt, rw, [(0.0, 1.0), (0.014, 0.0), (0.986, 0.0), (1.0, 1.0)])
        col = mix(nt, mth(nt, 'MULTIPLY', split, 0.55), col, (0.075, 0.068, 0.060))
        grime = con(nt, noise(nt, 7, 3.2, detail=9, rough=0.72), 0.42, 0.72)
        col = mix(nt, mth(nt, 'MULTIPLY', grime, dirty), col, (0.24, 0.215, 0.185), 'MULTIPLY')
        h = mth(nt, 'SUBTRACT', mth(nt, 'MULTIPLY', grain, 0.35), mth(nt, 'MULTIPLY', split, 0.85))
        h = mth(nt, 'SUBTRACT', h, mth(nt, 'MULTIPLY', pm, 0.22))
        finish(nt, col, mix(nt, pm, 0.44, 0.90), h, bump=0.75, dist=0.03)
    return build


def plaster(mat):
    nt = _clear(mat)
    big = con(nt, noise(nt, 2.6, 2.6, detail=9, rough=0.6, dist=0.4), 0.36, 0.64)
    fine = noise(nt, 80, 80, detail=6, rough=0.8)
    sw = con(nt, noise(nt, 9, 9, detail=6, rough=0.55, dist=1.4), 0.38, 0.64)
    crack = voro(nt, 7, 7, 'DISTANCE_TO_EDGE')
    cm = mth(nt, 'MULTIPLY', bw(nt, crack.outputs['Distance'], [(0.0, 1.0), (0.012, 0.0)]),
             con(nt, noise(nt, 3.0, 3.0, detail=6), 0.50, 0.58))
    col = mix(nt, big, (0.500, 0.475, 0.435), (0.680, 0.655, 0.605))
    col = mix(nt, mth(nt, 'MULTIPLY', sw, 0.45), col, (0.400, 0.375, 0.345))
    col = mix(nt, con(nt, noise(nt, 3.5, 1.8, detail=9), 0.46, 0.76, 0.0, 0.75), col,
              (0.24, 0.205, 0.175), 'MULTIPLY')
    col = mix(nt, mth(nt, 'MULTIPLY', cm, 0.85), col, (0.100, 0.090, 0.082))
    h = mth(nt, 'SUBTRACT', mth(nt, 'ADD', mth(nt, 'MULTIPLY', sw, 0.45), mth(nt, 'MULTIPLY', fine, 0.25)),
            mth(nt, 'MULTIPLY', cm, 0.8))
    finish(nt, col, mix(nt, fine, 0.80, 0.93), h, bump=0.35, dist=0.012)


def fabric(tone=(0.130, 0.040, 0.034), weave=26.0, dirty=0.55):
    """Upholstery / canvas: an actual over-under weave with slubs and a fuzzy nap, so sofas and
    sandbags stop reading as flat-shaded blocks (environment.md #21)."""
    def build(mat):
        nt = _clear(mat)
        u, v = uvxy(nt)
        wu = bw(nt, frac(nt, u, weave), [(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)])
        wv = bw(nt, frac(nt, v, weave), [(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)])
        chk = mth(nt, 'MODULO', mth(nt, 'ADD', idx(nt, u, weave), idx(nt, v, weave)), 2.0)
        thread = mix(nt, chk, wu, wv)
        fuzz = noise(nt, 240, 240, detail=4, rough=0.85)
        slub = con(nt, noise(nt, 20, 20, detail=7, rough=0.6), 0.40, 0.66)
        col = mix(nt, mth(nt, 'MULTIPLY', thread, 0.55), scale(tone, 0.62), scale(tone, 1.28, 0.01))
        col = mix(nt, mth(nt, 'MULTIPLY', slub, 0.50), col, scale(tone, 0.78))
        col = mix(nt, mth(nt, 'MULTIPLY', fuzz, 0.30), col, scale(tone, 1.35, 0.015))
        grime = con(nt, noise(nt, 4, 4, detail=9, rough=0.7), 0.44, 0.74)
        col = mix(nt, mth(nt, 'MULTIPLY', grime, dirty), col, (0.26, 0.23, 0.20), 'MULTIPLY')
        h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', thread, 0.60), mth(nt, 'MULTIPLY', fuzz, 0.22))
        finish(nt, col, mix(nt, fuzz, 0.86, 0.97), h, bump=0.8, dist=0.008)
    return build


def desert(mat):
    nt = _clear(mat)
    big = con(nt, noise(nt, 1.8, 1.8, detail=9, rough=0.65, dist=0.4), 0.36, 0.64)
    med = con(nt, noise(nt, 9, 9, detail=8, rough=0.7), 0.40, 0.62)
    fine = noise(nt, 70, 70, detail=5)
    scrub = con(nt, noise(nt, 14, 14, detail=8, rough=0.7, dist=1.2), 0.54, 0.64)
    col = mix(nt, big, (0.165, 0.118, 0.072), (0.350, 0.278, 0.188))
    col = mix(nt, mth(nt, 'MULTIPLY', med, 0.80), col, (0.125, 0.092, 0.058))
    col = mix(nt, mth(nt, 'MULTIPLY', fine, 0.45), col, (0.300, 0.248, 0.175))
    col = mix(nt, scrub, col, (0.085, 0.078, 0.038))
    h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', med, 0.45), mth(nt, 'MULTIPLY', fine, 0.30))
    finish(nt, col, 0.94, h, bump=0.7, dist=0.07)


# =========================================================================== registry
#  name: (builder, tile size in metres, texture resolution, metallic, normal strength)
SPEC = {
    'siding_yellow':   (siding((0.470, 0.365, 0.120), dirty=0.75, peel=0.30), 2.0, 1024, 0.0, 1.0),
    'siding_green':    (siding((0.255, 0.375, 0.285), dirty=0.75, peel=0.32), 2.0, 1024, 0.0, 1.0),
    'siding_white':    (siding((0.560, 0.545, 0.500), primer=(0.30, 0.26, 0.21),
                               dirty=0.75, peel=0.45), 2.0, 1024, 0.0, 1.0),
    'shingle':         (shingles, 2.0, 1024, 0.0, 1.0),
    'brick':           (brick, 2.0, 1024, 0.0, 1.0),
    'concrete':        (concrete(cracky=0.35), 2.0, 1024, 0.0, 0.45),
    'rubble':          (concrete((0.135, 0.120, 0.105), cracky=0.5), 1.2, 1024, 0.0, 0.7),
    'concrete_floor':  (concrete((0.250, 0.248, 0.242), cracky=0.8, joints=2.0,
                                 pore_amt=0.06, grain_amt=0.0), 3.0, 2048, 0.0, 0.12),
    'concrete_bunker': (concrete((0.300, 0.300, 0.296), cracky=0.55, board=True, rust=0.28,
                                 pore_amt=0.35, grain_amt=0.35), 2.0, 2048, 0.0, 0.30),
    'sidewalk':        (concrete((0.430, 0.425, 0.410), cracky=0.8, joints=1.0), 2.0, 1024, 0.0, 0.5),
    'asphalt':         (asphalt, 3.0, 2048, 0.0, 1.0),
    'dirt':            (ground(), 3.0, 2048, 0.0, 0.7),
    'dirt_scorch':     (ground((0.150, 0.120, 0.090), (0.230, 0.195, 0.150),
                               (0.130, 0.115, 0.060), tufts=0.22, scorch=0.80), 3.0, 1024, 0.0, 1.0),
    'wallpaper_a':     (wallpaper((0.640, 0.565, 0.390), (0.430, 0.175, 0.150), True, 14.0, 9.0), 2.95, 1024, 0.0, 1.0),
    'wallpaper_b':     (wallpaper((0.455, 0.500, 0.450), (0.215, 0.250, 0.360), True, 9.0, 7.0), 2.95, 1024, 0.0, 1.0),
    'woodfloor':       (woodfloor, 2.0, 1024, 0.0, 1.0),
    'lino':            (lino, 1.6, 1024, 0.0, 1.0),
    'plaster':         (plaster, 2.0, 1024, 0.0, 1.0),
    'fabric_weave_r':  (fabric((0.130, 0.040, 0.034), 26.0), 0.55, 1024, 0.0, 1.0),
    'fabric_weave_o':  (fabric((0.125, 0.125, 0.080), 22.0, dirty=0.7), 0.55, 1024, 0.0, 1.0),
    'fabric_weave_b':  (fabric((0.048, 0.052, 0.075), 26.0), 0.55, 1024, 0.0, 1.0),
    'metal_rust':      (rusted(), 1.5, 1024, 0.30, 1.0),
    'metal_dark':      (rusted((0.085, 0.085, 0.090), 0.14), 1.5, 1024, 0.60, 1.0),
    # bunker steelwork: shop-painted, with rust only where the paint has chipped. `metal_rust`
    # splattered orange over whole beams, rails and treads (environment.md #18, repair #2).
    'steel_paint':     (painted_metal((0.165, 0.175, 0.170), 0.06, 0.55), 1.5, 1024, 0.35, 1.0),
    'paint_red':       (painted_metal((0.300, 0.045, 0.035), 0.55), 1.5, 1024, 0.40, 1.0),
    'paint_teal':      (painted_metal((0.075, 0.200, 0.215), 0.50), 1.5, 1024, 0.40, 1.0),
    'paint_cream':     (painted_metal((0.560, 0.535, 0.455), 0.50), 1.5, 1024, 0.35, 1.0),
    'paint_bus':       (painted_metal((0.560, 0.365, 0.045), 0.60), 1.5, 1024, 0.35, 1.0),
    'paint_scorch':    (painted_metal((0.055, 0.048, 0.044), 0.55, 0.70), 1.5, 1024, 0.30, 0.6),
    'paint_green_mil': (painted_metal((0.110, 0.130, 0.080), 0.45), 1.5, 1024, 0.40, 1.0),
    'wood_bare':       (bare_wood(), 1.5, 1024, 0.0, 1.0),
    'bark':            (bare_wood((0.088, 0.070, 0.052), rows=2.0), 1.0, 1024, 0.0, 1.0),
    'wood_white':      (painted_wood((0.640, 0.625, 0.580), 6.0, 0.24, 0.75), 1.5, 1024, 0.0, 1.0),
    'wood_trim_y':     (painted_wood((0.620, 0.585, 0.510), 5.0, 0.20, 0.65), 1.5, 1024, 0.0, 1.0),
    'wood_trim_g':     (painted_wood((0.565, 0.580, 0.545), 5.0, 0.20, 0.65), 1.5, 1024, 0.0, 1.0),
    'desert':          (desert, 8.0, 1024, 0.0, 1.0),
    # 55 m per tile was 18 px/m -- a featureless beige plane (environment.md #9). At 10 m the
    # repeat is hidden by distance haze and the ground finally has texture at the horizon.
    'desert_far':      (desert, 10.0, 1024, 0.0, 1.0),
}

FLAT = {
    # window glass: a cheap reflective panel (no refraction). `alpha` makes the exporter write
    # alphaMode BLEND, and map.js already pushes envMapIntensity to 1.9 for /glass/ so the
    # sunset sky finally shows up in the west-facing windows (environment.md #10).
    'glass':        dict(color=(0.35, 0.40, 0.44), roughness=0.055, metallic=0.0, alpha=0.26),
    'glass_car':    dict(color=(0.09, 0.11, 0.13), roughness=0.075, metallic=0.0, alpha=0.42),
    'glass_dark':   dict(color=(0.016, 0.018, 0.022), roughness=0.20, metallic=0.0),
    'chrome':       dict(color=(0.58, 0.58, 0.60), roughness=0.24, metallic=1.0),
    'rubber':       dict(color=(0.024, 0.024, 0.026), roughness=0.85, metallic=0.0),
    'charred':      dict(color=(0.020, 0.019, 0.018), roughness=0.94, metallic=0.0),
    'fabric_red':   dict(color=(0.130, 0.040, 0.034), roughness=0.93, metallic=0.0),
    'fabric_olive': dict(color=(0.125, 0.125, 0.080), roughness=0.90, metallic=0.0),
    'cloth_white':  dict(color=(0.330, 0.315, 0.285), roughness=0.92, metallic=0.0),
    'cloth_navy':   dict(color=(0.030, 0.034, 0.055), roughness=0.90, metallic=0.0),
    'skin_mann':    dict(color=(0.505, 0.480, 0.450), roughness=0.38, metallic=0.0),
    'collision':    dict(color=(0.9, 0.1, 0.4), roughness=1.0, metallic=0.0),
    # worn road / floor marking paint (was referenced by the road centre line but never defined,
    # so those meshes exported with no material at all)
    'sign_paint':   dict(color=(0.470, 0.450, 0.400), roughness=0.80, metallic=0.0),
    'lamp_glow':    dict(color=(0.85, 0.70, 0.45), roughness=0.25, metallic=0.0,
                         emission=(1.0, 0.74, 0.40), emission_strength=5.0),
    'sign_glow':    dict(color=(0.60, 0.20, 0.10), roughness=0.55, metallic=0.0,
                         emission=(1.0, 0.30, 0.10), emission_strength=1.5),
    # stencil paint for real lettering (lib_sign). Flat colour, no tiling texture: a 4 cm letter
    # cube-projected into a 1.5 m tile is noise, not paint.
    'paint_stencil_w': dict(color=(0.520, 0.500, 0.455), roughness=0.72, metallic=0.0),
    'paint_stencil_y': dict(color=(0.560, 0.365, 0.045), roughness=0.70, metallic=0.0),
    'paint_stencil_k': dict(color=(0.028, 0.026, 0.025), roughness=0.78, metallic=0.0),
    'paint_stencil_r': dict(color=(0.300, 0.045, 0.035), roughness=0.70, metallic=0.0),
}

DECAL_ROUGH = {name: rough for name, (_fn, rough) in DEC.DECALS.items()}
DECAL_MATS = ['decal_' + n for n in DECAL_ROUGH]

UV_SCALE = {k: v[1] for k, v in SPEC.items()}
UV_SCALE.update({k: 1.0 for k in FLAT})
UV_SCALE.update({k: 1.0 for k in DECAL_MATS})


def _blend(mat, alpha=None):
    """Make a material alpha-blended in a way the glTF exporter picks up (alphaMode BLEND)."""
    nt = mat.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    if alpha is not None and bsdf is not None:
        bsdf.inputs['Alpha'].default_value = alpha
    # NB: `use_transparent_shadow` must stay ON. With it off, a 26 %-alpha window and every
    # 1 cm decal quad casts a *fully opaque* shadow — the check renders came back with black
    # rectangles stamped across the road and the bunker walls.
    for attr, val in (('blend_method', 'BLEND'), ('surface_render_method', 'BLENDED'),
                      ('shadow_method', 'HASHED'), ('use_transparent_shadow', True)):
        try:
            setattr(mat, attr, val)
        except Exception:
            pass
    return mat


def decal_material(name, tex, roughness=0.9):
    """Alpha-blended decal quad material: colour and alpha both from the one RGBA image."""
    mat = pbr_material(name, base_tex=tex, roughness=roughness, metallic=0.0)
    nt = mat.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    img = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeTexImage'), None)
    if img is not None and bsdf is not None:
        nt.links.new(img.outputs['Alpha'], bsdf.inputs['Alpha'])
    return _blend(mat)


def build_all(force=False, only=None):
    """Bake (cached) and return {name: bpy.types.Material}."""
    mats = {}
    for name, (fn, metres, res, metallic, nstr) in SPEC.items():
        if only and name not in only:
            continue
        tex = bake_tileable(name, fn, size=res, samples=12, force=force)
        mats[name] = pbr_material(name, base_tex=tex['DIFFUSE'], rough_tex=tex['ROUGHNESS'],
                                  normal_tex=tex['NORMAL'], normal_strength=nstr, metallic=metallic)
    for name, kw in FLAT.items():
        kw = dict(kw)
        alpha = kw.pop('alpha', None)
        mats[name] = pbr_material(name, **kw)
        if alpha is not None:
            _blend(mats[name], alpha)
    paths = DEC.generate(force=force)
    for dname, path in paths.items():
        mats['decal_' + dname] = decal_material('decal_' + dname, path, DECAL_ROUGH[dname])
    return mats


if __name__ == '__main__':
    import common
    common.reset_scene()
    build_all(force=('--force' in sys.argv))
    print('BAKED', len(SPEC), 'materials into', TEX_CACHE)
