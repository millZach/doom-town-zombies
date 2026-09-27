"""Authored decal dressing (environment.md #8).

The map had zero authored environment decals: bare 6 x 3 m concrete walls, no grime under the
windows, no rust runs under the pipes, no oil under the cars. This module generates a small
library of RGBA decal textures procedurally (numpy + a tiny PNG writer -- no Blender bake, so
they are cheap and deterministic) and `Scene.decal()` in lib_map stamps them as thin quads a few
millimetres off the surface they dress.

Decals are also what breaks up the visible tiling of the base materials (#9): a wall with eight
overlapping unique stains no longer reads as one texture repeated five times.
"""
import os, sys, zlib, struct, math

_HERE = os.path.dirname(os.path.abspath(__file__))
TEX_CACHE = os.path.abspath(os.path.join(_HERE, '..', '_texcache'))   # == common.TEX_CACHE
os.makedirs(TEX_CACHE, exist_ok=True)

VERSION = 9          # bump to force regeneration
RES = 256


# --------------------------------------------------------------------------- png out
def write_png(path, rgba):
    """rgba: uint8 HxWx4 numpy array."""
    h, w = rgba.shape[:2]
    raw = bytearray()
    data = rgba.tobytes()
    stride = w * 4
    for y in range(h):
        raw.append(0)
        raw += data[y * stride:(y + 1) * stride]

    def chunk(tag, payload):
        c = struct.pack('>I', len(payload)) + tag + payload
        return c + struct.pack('>I', zlib.crc32(tag + payload) & 0xffffffff)

    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(bytes(raw), 6))
           + chunk(b'IEND', b''))
    with open(path, 'wb') as f:
        f.write(png)
    return path


# --------------------------------------------------------------------------- noise
def _np():
    import numpy as np
    return np


def lattice(freq, seed, np):
    rs = np.random.RandomState(seed & 0x7fffffff)
    return rs.random_sample((freq, freq))


def vnoise(n, freq, seed, np, sx=1.0, sy=1.0):
    """Tileable value noise on an n x n grid (freq cells, anisotropic via sx/sy)."""
    fx, fy = max(1, int(freq * sx)), max(1, int(freq * sy))
    g = lattice(max(fx, fy), seed, np)[:fy, :fx]
    u = np.arange(n) * (fx / n)
    v = np.arange(n) * (fy / n)
    i0 = np.floor(u).astype(int) % fx
    j0 = np.floor(v).astype(int) % fy
    i1, j1 = (i0 + 1) % fx, (j0 + 1) % fy
    tu, tv = u - np.floor(u), v - np.floor(v)
    tu = tu * tu * (3 - 2 * tu)
    tv = tv * tv * (3 - 2 * tv)
    a = g[np.ix_(j0, i0)] * (1 - tu)[None, :] + g[np.ix_(j0, i1)] * tu[None, :]
    b = g[np.ix_(j1, i0)] * (1 - tu)[None, :] + g[np.ix_(j1, i1)] * tu[None, :]
    return a * (1 - tv)[:, None] + b * tv[:, None]


def fbm(n, freq, seed, np, oct_=5, rough=0.5, sx=1.0, sy=1.0):
    out = np.zeros((n, n))
    amp, tot, f = 1.0, 0.0, freq
    for k in range(oct_):
        out += amp * vnoise(n, f, seed + k * 977, np, sx, sy)
        tot += amp
        amp *= rough
        f *= 2
    return out / tot


def smoothstep(a, b, x, np):
    t = np.clip((x - a) / max(b - a, 1e-6), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def grid(n, np):
    y, x = np.mgrid[0:n, 0:n]
    return x / (n - 1.0), y / (n - 1.0)


# --------------------------------------------------------------------------- decal art
def d_streak(n, np):
    """Grime washing down from the top edge (under a sill, a ledge, a gutter)."""
    x, y = grid(n, np)
    fine = fbm(n, 24, 11, np, 4, 0.6, sx=3.0, sy=0.14)
    med = fbm(n, 6, 23, np, 5, 0.55, sx=2.0, sy=0.3)
    runs = smoothstep(0.42, 0.72, fine * 0.65 + med * 0.5, np)
    length = 0.35 + 0.65 * med
    fall = smoothstep(0.0, 0.10, y, np) * (1.0 - smoothstep(0.0, 1.0, y / np.clip(length, 0.15, 1.0), np))
    a = np.clip(runs * fall * 1.35 + fall * 0.22 * med, 0, 1) ** 1.15
    a *= smoothstep(0.0, 0.05, x, np) * smoothstep(0.0, 0.05, 1 - x, np)
    col = np.stack([0.055 + 0.05 * fine, 0.048 + 0.042 * fine, 0.040 + 0.034 * fine], -1)
    return col, a * 0.85


def d_rust_run(n, np):
    """Orange corrosion bleeding down from a fastener / pipe bracket."""
    x, y = grid(n, np)
    src = np.exp(-(((x - 0.5) / 0.16) ** 2 + ((y - 0.06) / 0.07) ** 2))
    fine = fbm(n, 30, 71, np, 4, 0.6, sx=2.6, sy=0.12)
    spread = 0.10 + 0.34 * y
    lat = np.exp(-((x - 0.5) / spread) ** 2)
    runs = smoothstep(0.45, 0.68, fine, np) * lat
    a = np.clip(src * 1.2 + runs * (1.0 - smoothstep(0.35, 1.0, y, np)) * 1.1, 0, 1)
    t = np.clip(fine * 1.2, 0, 1)
    col = np.stack([0.30 + 0.16 * t, 0.105 + 0.075 * t, 0.032 + 0.028 * t], -1)
    return col, a ** 1.1


def d_water_stain(n, np):
    """Water ingress from a ceiling joint: grey-green blotch ringed with white efflorescence."""
    x, y = grid(n, np)
    warp = fbm(n, 4, 131, np, 5, 0.6) - 0.5
    r = np.sqrt(((x - 0.5) * 1.15 + warp * 0.55) ** 2 + ((y - 0.42) * 1.35 + warp * 0.45) ** 2)
    body = 1.0 - smoothstep(0.20, 0.44, r, np)
    rim = smoothstep(0.30, 0.38, r, np) * (1.0 - smoothstep(0.38, 0.46, r, np))
    fine = fbm(n, 22, 57, np, 4, 0.65)
    a = np.clip(body * 0.62 + rim * 0.45, 0, 1) * (0.45 + 0.5 * fine)
    dark = np.stack([0.075 + 0.045 * fine, 0.080 + 0.045 * fine, 0.072 + 0.036 * fine], -1)
    # the efflorescence rim is a faint salt bloom, not white paint
    pale = np.stack([0.24 + 0.10 * fine, 0.24 + 0.10 * fine, 0.23 + 0.09 * fine], -1)
    col = dark * (1 - rim[..., None]) + pale * rim[..., None]
    return col, np.clip(a, 0, 1) * 0.62


def d_oil(n, np):
    """Oil pooled under a wreck: near-black centre, feathered edge, faint sheen ring."""
    x, y = grid(n, np)
    warp = fbm(n, 3, 211, np, 5, 0.62) - 0.5
    r = np.sqrt(((x - 0.5) * 1.0 + warp * 0.7) ** 2 + ((y - 0.5) * 1.12 + warp * 0.6) ** 2)
    # a wide, soft falloff and a lifted floor colour: a hard near-black ellipse reads as a hole
    # punched in the concrete, not as oil soaked into it (repair round #3)
    body = 1.0 - smoothstep(0.10, 0.47, r, np)
    sheen = smoothstep(0.22, 0.34, r, np) * (1.0 - smoothstep(0.34, 0.44, r, np))
    fine = fbm(n, 18, 313, np, 4, 0.6)
    a = np.clip(body * (0.70 + 0.30 * fine) + sheen * 0.22, 0, 1) * 0.62
    col = np.stack([0.040 + 0.05 * sheen, 0.036 + 0.035 * sheen, 0.036 + 0.07 * sheen], -1)
    return col, a


def d_soot(n, np):
    """Soot fan above a fire / a blown-out window."""
    x, y = grid(n, np)
    fan = np.clip(1.0 - np.abs(x - 0.5) / (0.16 + 0.80 * (1 - y)), 0, 1)
    fine = fbm(n, 10, 409, np, 5, 0.62, sx=1.2, sy=0.6)
    a = np.clip(fan ** 1.15 * (0.55 + 1.1 * fine) * (1.0 - smoothstep(0.25, 1.0, 1 - y, np)) * 1.3, 0, 1)
    col = np.stack([0.016 + 0.02 * fine, 0.015 + 0.018 * fine, 0.015 + 0.016 * fine], -1)
    return col, a * 0.95


def d_crack(n, np):
    """Hairline cracking radiating across concrete."""
    x, y = grid(n, np)
    a = np.zeros((n, n))
    import random
    rnd = random.Random(7)
    for b in range(9):
        px, py = rnd.uniform(0.35, 0.65), rnd.uniform(0.35, 0.65)
        ang = rnd.uniform(0, 6.283)
        w = rnd.uniform(0.0045, 0.0085)
        for step in range(140):
            ang += rnd.uniform(-0.16, 0.16)
            px += math.cos(ang) * 0.0048
            py += math.sin(ang) * 0.0048
            if not (0.02 < px < 0.98 and 0.02 < py < 0.98):
                break
            ww = w * (1.0 - 0.6 * step / 140.0)
            d2 = (x - px) ** 2 + (y - py) ** 2
            a = np.maximum(a, np.exp(-d2 / (ww * ww)) * (1.0 - 0.55 * step / 140.0))
    fine = fbm(n, 30, 511, np, 3, 0.6)
    a = np.clip(a * (0.6 + 0.7 * fine), 0, 1)
    col = np.stack([0.030 + 0.03 * fine, 0.028 + 0.028 * fine, 0.027 + 0.026 * fine], -1)
    return col, a


def d_tyre(n, np):
    """A tyre mark: two tread bands with block pattern, smeared along +Y."""
    x, y = grid(n, np)
    band = (np.exp(-((x - 0.36) / 0.115) ** 2) + np.exp(-((x - 0.64) / 0.115) ** 2))
    tread = 1.0
    fine = fbm(n, 3, 613, np, 2, 0.5, sx=0.1, sy=1.0)
    fade = smoothstep(0.0, 0.10, y, np) * (1.0 - smoothstep(0.55, 1.0, y, np))
    a = np.clip(band * tread * fade * (0.70 + 0.5 * fine), 0, 1) * 0.8
    col = np.stack([0.018 + 0.02 * fine, 0.017 + 0.018 * fine, 0.017 + 0.017 * fine], -1)
    return col, a


def d_poster(n, np):
    """A torn public-information poster: paper ground, printed bars, a bold emblem band."""
    x, y = grid(n, np)
    paper = fbm(n, 26, 719, np, 4, 0.6)
    edge = fbm(n, 7, 811, np, 4, 0.6)
    keep = ((x > 0.08 + 0.05 * edge) & (x < 0.92 - 0.05 * edge)
            & (y > 0.06 + 0.06 * edge) & (y < 0.94 - 0.07 * edge))
    tear = smoothstep(0.46, 0.58, edge, np) * smoothstep(0.55, 0.85, y, np)
    a = np.where(keep, 1.0, 0.0) * (1.0 - tear)
    base = np.stack([0.50 + 0.18 * paper, 0.47 + 0.17 * paper, 0.40 + 0.15 * paper], -1)
    ink = np.stack([0.055, 0.050, 0.048], -1)
    red = np.stack([0.32, 0.045, 0.035], -1)
    col = base.copy()
    # header band + body text lines, laid out as printed bars
    hdr = (y > 0.12) & (y < 0.24) & (x > 0.14) & (x < 0.86)
    col[hdr] = red
    for k in range(6):
        yy0 = 0.34 + k * 0.078
        w = 0.72 - (0.28 if k % 3 == 2 else 0.0)
        ln = (y > yy0) & (y < yy0 + 0.030) & (x > 0.16) & (x < 0.16 + w)
        col[ln] = ink
    grime = fbm(n, 5, 907, np, 5, 0.6)
    col *= (0.55 + 0.55 * grime)[..., None]
    return np.clip(col, 0, 1), np.clip(a, 0, 1)


def d_dust_edge(n, np):
    """Soft floor grime that darkens where a floor meets a wall."""
    x, y = grid(n, np)
    fine = fbm(n, 9, 1013, np, 5, 0.6, sx=2.2, sy=0.7)
    a = (1.0 - smoothstep(0.0, 0.85, y, np)) * (0.45 + 0.75 * fine)
    a *= smoothstep(0.0, 0.06, x, np) * smoothstep(0.0, 0.06, 1 - x, np)
    col = np.stack([0.048 + 0.04 * fine, 0.044 + 0.036 * fine, 0.040 + 0.032 * fine], -1)
    return col, np.clip(a, 0, 1) * 0.8


def d_scorch(n, np):
    """Ground scorch under a fire."""
    x, y = grid(n, np)
    warp = fbm(n, 3, 1117, np, 5, 0.6) - 0.5
    r = np.sqrt((x - 0.5) ** 2 + (y - 0.5) ** 2) + warp * 0.22
    fine = fbm(n, 16, 1213, np, 4, 0.6)
    a = (1.0 - smoothstep(0.16, 0.48, r, np)) * (0.55 + 0.6 * fine)
    col = np.stack([0.016 + 0.03 * fine, 0.014 + 0.024 * fine, 0.013 + 0.020 * fine], -1)
    return col, np.clip(a, 0, 1) * 0.95


# name -> (generator, roughness)
DECALS = {
    'streak':  (d_streak, 0.94),
    'rust':    (d_rust_run, 0.86),
    'water':   (d_water_stain, 0.90),
    'oil':     (d_oil, 0.32),
    'soot':    (d_soot, 0.96),
    'crack':   (d_crack, 0.92),
    'tyre':    (d_tyre, 0.88),
    'poster':  (d_poster, 0.90),
    'grime':   (d_dust_edge, 0.94),
    'scorch':  (d_scorch, 0.96),
}


def generate(force=False, res=RES):
    """Write every decal PNG into the texture cache (cached on VERSION). -> {name: path}"""
    np = _np()
    out = {}
    for name, (fn, _rough) in DECALS.items():
        path = os.path.join(TEX_CACHE, 'decal_%s_v%d.png' % (name, VERSION))
        out[name] = path
        if os.path.exists(path) and not force:
            continue
        col, alpha = fn(res, np)
        rgba = np.empty((res, res, 4), dtype=np.uint8)
        # sRGB encode the colour so it survives the glTF baseColorTexture round-trip
        srgb = np.clip(col, 0.0, 1.0) ** (1.0 / 2.2)
        rgba[..., :3] = (srgb * 255.0 + 0.5).astype(np.uint8)
        rgba[..., 3] = (np.clip(alpha, 0, 1) * 255.0 + 0.5).astype(np.uint8)
        write_png(path, rgba)
        print('decal', name, '->', os.path.basename(path))
    return out


if __name__ == '__main__':
    generate(force='--force' in sys.argv)
