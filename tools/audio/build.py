"""build.py — turn the raw CC0 packs and ElevenLabs renders into the shipped
`public/audio/**` library plus `public/audio/manifest.json`.

    python tools/audio/build.py [group ...]

Groups: guns handling impacts foley voices world stingers music ui all

Everything is deterministic: re-running rebuilds byte-identical output.
Sources live in the scratch download directory (see DL below); nothing under
`tools/audio/_raw` is touched except to read the ElevenLabs renders.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
OUT = os.path.join(ROOT, "public/audio")
RAW = os.path.join(ROOT, "tools/audio/_raw")
DL = os.environ.get(
    "AUDIO_DL",
    r"C:\Users\zache\AppData\Local\Temp\claude\D--Opus-5-5-BO2-Zombies"
    r"\5e4104e6-13d4-45ae-8dc3-3058220ac27e\scratchpad")

SR = lib.SR
FFSL = os.path.join(DL, "ffsl", "Prepared SFX Library")
VCSL = os.path.join(DL, "vcsl")
EX = os.path.join(DL, "ex")
OGA = os.path.join(DL, "oga")

rng = np.random.default_rng(20250923)

# ---------------------------------------------------------------- loudness

# Integrated loudness targets (LUFS, gated, BS.1770). The hierarchy the brief
# asks for: guns loudest, zombie voices under them, stingers well under the
# guns, UI and footsteps quietest.
LEVEL = {
    "gun": -13.0,
    "boom": -11.5,
    "energy": -14.0,
    "voice": -19.0,      # zombies, hounds, the player
    "vox": -16.0,        # the announcer
    "impact": -20.0,
    "handling": -23.0,
    "shell": -26.0,
    "foley": -21.0,
    "footstep": -27.0,
    "ui": -23.0,
    "powerup": -20.0,
    "stinger": -21.0,    # 8 LU under the guns
    "music": -24.0,
    "ambient": -26.0,
}

# Delivery ceiling, as a *sample* peak.
#
# ffmpeg's ebur128 true-peak meter reads a broadband transient about 3 dB above
# what exact sinc interpolation finds (its BS.1770 4x FIR overshoots on clicks),
# and it is the meter the report quotes, so the build leaves that much room:
# transient material is held near -5 dBFS so it still lands under -1 dBTP when
# ffmpeg measures it, while sustained material — which has no such overshoot —
# is allowed nearer the top.
PEAK_CEIL = {
    "gun": 0.48, "boom": 0.50, "energy": 0.50,
    "impact": 0.58, "handling": 0.60, "shell": 0.62,
    "foley": 0.62, "footstep": 0.64, "ui": 0.60, "powerup": 0.62,
    "voice": 0.68, "vox": 0.72,
    "stinger": 0.74, "music": 0.74, "ambient": 0.74,
}


def level(a, target_lufs, ceiling):
    """Normalise to a gated-LUFS target and hold the peak under `ceiling`.

    A gunshot has an enormous crest factor — a 3 ms crack over a 150 ms body —
    so simply scaling until its peak is legal would drop its *loudness* far
    below a boomier sound with the same peak, and the whole hierarchy would
    collapse. Instead the gain and a soft knee alternate: each pass pushes the
    loudness back to target and bends whatever pokes through, which keeps the
    transient audible and the file legal.
    """
    if lib.lufs(a, SR) <= -119:
        return a
    for _ in range(4):
        cur = lib.lufs(a, SR)
        a = (a * (10 ** ((target_lufs - cur) / 20.0))).astype(np.float32)
        if float(np.abs(a).max()) <= ceiling:
            break
        a = lib.limit(a, ceiling)
    p = float(np.abs(a).max())
    if p > ceiling:
        a = (a * (ceiling / p)).astype(np.float32)
    return a


# How much energy above 5 kHz each category is allowed before it gets an
# automatic high-shelf. This is the "screech" guard: stingers and voices are
# held very low, a metal click is allowed to be bright because it is a click.
HARSH_CAP = {
    "stinger": 0.03, "music": 0.03, "ambient": 0.05,
    "voice": 0.12, "vox": 0.12,
    "gun": 0.30, "boom": 0.25, "energy": 0.30,
    "impact": 0.35, "foley": 0.35, "footstep": 0.35,
    "handling": 0.38, "shell": 0.35,
    "ui": 0.42, "powerup": 0.35,
}


def deharsh_to(a, cap, knee=5000.0):
    """High-shelf the top until the >5 kHz energy fraction is under `cap`."""
    for _ in range(4):
        if lib.harshness(a, SR) <= cap:
            break
        a = lib.biquad(a, SR, "highshelf", knee, 0.7, -6.0)
        a = lib.lowpass(a, SR, 13000, order=1)
        knee *= 0.88
    return a


# ---------------------------------------------------------------- registry

BUILT = {}     # name -> manifest entry (files already written to disk)
BYTES = [0]

# Which folder under public/audio each category ships in.
SUBDIR = {"gun": "guns", "boom": "guns", "energy": "guns",
          "voice": "voices", "vox": "voices",
          "impact": "impacts", "handling": "handling", "shell": "handling",
          "foley": "foley", "footstep": "foley", "ui": "ui",
          "powerup": "world", "stinger": "stingers", "music": "music",
          "ambient": "world"}


def emit(name, variants, cat, loop=False, bus=None, gain=1.0, src="", mono=True,
         send=None, send_amt=None, jitter=None, rate_jit=None):
    """Shape, normalise and *write* one sound, and record its manifest entry.

    Each variant is encoded as soon as it is finished and the float array is
    dropped. Holding all 324 of them in memory until the end cost several
    hundred megabytes and this machine shares its RAM with other build agents;
    encoding as we go keeps the peak flat and means a crash cannot lose more
    than the sound in hand.
    """
    sub = SUBDIR[cat]
    files = []
    n = len(variants)
    for i, v in enumerate(variants):
        v = np.asarray(v, dtype=np.float32)
        v = lib.to_mono(v) if mono else lib.stereo(v)
        if not loop:
            v = lib.trim(v, SR)
            v = lib.fade(v, SR, 0.0015, 0.02)
        v = deharsh_to(v, HARSH_CAP.get(cat, 0.5))
        v = level(v, LEVEL[cat], PEAK_CEIL.get(cat, 0.6))
        rel = f"{sub}/{name}" + (f"_{i + 1}" if n > 1 else "") + ".ogg"
        path = os.path.join(OUT, rel)
        lib.encode(v, path, SR, q=(5 if cat in ("stinger", "music", "ambient") else 4))
        BYTES[0] += os.path.getsize(path)
        files.append(rel)
        del v

    entry = {"files": files, "gain": round(gain, 3)}
    # A one-shot with no explicit jitter still gets a touch of variation so a
    # repeated trigger never sounds like the same buffer twice.
    if not loop and cat not in ("stinger", "music", "ambient", "vox"):
        if jitter is None:
            jitter = 25
        if rate_jit is None:
            rate_jit = 0.02
    b = bus or CAT_BUS.get(cat)
    if b:
        entry["bus"] = b
    if loop:
        entry["loop"] = True
    for val, key in ((send, "send"), (send_amt, "sendAmt"),
                     (jitter, "jitter"), (rate_jit, "rateJit")):
        if val is not None:
            entry[key] = val
    entry["src"] = src
    BUILT[name] = entry


def dec(path, mono=False):
    a, _ = lib.decode(path, SR, mono=False)
    return lib.to_mono(a) if mono else a


def pool(paths, length=0.6, thresh=0.12, gap=0.12, mono=True):
    """Every transient event found across `paths`, in order."""
    out = []
    for p in paths:
        try:
            a = dec(p, mono=mono)
        except Exception as e:
            print("  ! cannot read", p, e)
            continue
        for s in lib.slice_events(a, SR, length=length, thresh=thresh, gap=gap):
            out.append(s)
    return out


def pick(xs, n, seed=0):
    """n items spread evenly over xs (wrapping if there are too few)."""
    if not xs:
        return []
    idx = [int(round(i * (len(xs) - 1) / max(1, n - 1))) if n > 1 else 0 for i in range(n)]
    return [xs[i % len(xs)] for i in idx]


def vary(a, ratio):
    return lib.resample_pitch(a, ratio)


def cut(a, seconds, fade_out=0.06):
    n = int(SR * seconds)
    if len(a) <= n:
        return a
    return lib.fade(a[:n], SR, 0.0, fade_out)


# ================================================================== guns ===

GUN_SRC = {
    # name             near take,                 second take,         pitch, tail
    "gun_m1911":       ("1911/A_42P.wav", "1911/A_34P.wav", 1.00, 0.62),
    "gun_python":      ("Smith & Wesson 642/V_27P.wav", "Smith & Wesson 642/V_22P.wav", 0.94, 0.80),
    "gun_m14":         ("SKS/U_14P.wav", "SKS/U_19P.wav", 1.02, 0.72),
    "gun_galil":       ("AR-15/D_32P.wav", "AR-15/D_24P.wav", 1.03, 0.62),
    "gun_ak74u":       ("PPSh/P_30P.wav", "PPSh/P_16P.wav", 1.06, 0.52),
    "gun_mp5":         ("Carl Gustav M45/G_31P.wav", "Carl Gustav M45/G_20P.wav", 1.04, 0.50),
    "gun_rpd":         ("AK-47/C_28P.wav", "AK-47/C_31P.wav", 0.97, 0.60),
    "gun_remington870": ("Nova/O_21P.wav", "Nova/O_17P.wav", 0.96, 0.85),
    "gun_olympia":     ("Model 12/K_22P.wav", "Model 12/K_17P.wav", 0.93, 0.90),
}


def build_guns():
    for name, (near, far, pitch, tail) in GUN_SRC.items():
        shots = []
        for f in (near, far):
            p = os.path.join(FFSL, f)
            if not os.path.exists(p):
                print("  ! missing", p)
                continue
            a = dec(p, mono=True)
            shots += lib.slice_events(a, SR, length=tail + 0.25, thresh=0.06, gap=0.4)
        shots = [s for s in shots if len(s) > SR * 0.2]
        if not shots:
            continue
        # keep the closest-sounding takes first, then fill to four with micro
        # pitch variants so a burst never repeats a buffer verbatim
        base = shots[:4]
        ratios = [1.0, 1.0, 1.0, 1.0][: len(base)]
        while len(base) < 4:
            k = len(base) - len(shots)
            base.append(shots[k % len(shots)])
            ratios.append([1.035, 0.968, 1.018, 0.982][(len(base) - 1) % 4])
        vs = []
        for s, r in zip(base, ratios):
            x = vary(s, pitch * r)
            x = lib.highpass(x, SR, 38, order=2)
            # tame the very top so a burst of automatic fire never gets fizzy,
            # and roll off the last octave: the source recordings are clipped
            # flat at the crack, and the near-Nyquist energy that leaves behind
            # is what drives the inter-sample peaks several dB past the sample
            # peak on a true-peak meter.
            x = lib.biquad(x, SR, "highshelf", 9000, 0.7, -4.0)
            x = lib.lowpass(x, SR, 14000, order=1)
            x = cut(lib.trim(x, SR, -46, head=0.002, tail=0.02), tail, fade_out=0.09)
            vs.append(x)
        emit(name, vs, "gun", src="FFSL " + near.split("/")[0],
             send="gun", send_amt=0.30, jitter=40, rate_jit=0.03)

    # Ray gun — ElevenLabs
    a = dec(os.path.join(RAW, "special/raygun_fire.mp3"), mono=True)
    segs = lib.slice_events(a, SR, length=1.3, thresh=0.14, gap=0.5)
    vs = [cut(lib.trim(s, SR, -48), 1.15, 0.12) for s in segs[:3]] or [cut(a, 1.15)]
    emit("gun_raygun", vs, "energy", src="ElevenLabs raygun_fire",
         send="hall", send_amt=0.22, jitter=60, rate_jit=0.04)

    a = dec(os.path.join(RAW, "special/raygun_impact.mp3"), mono=True)
    segs = lib.slice_events(a, SR, length=1.1, thresh=0.14, gap=0.5)
    vs = [cut(lib.trim(s, SR, -48), 0.95, 0.12) for s in segs[:2]] or [cut(a, 0.95)]
    emit("raygun_impact", vs, "energy", src="ElevenLabs raygun_impact",
         send="hall", send_amt=0.3, jitter=70)

    # Pack-a-Punch energy layer — a soft sci-fi shimmer stacked over a shot
    ff = sorted(glob_ogg(os.path.join(EX, "kenney_sci-fi-sounds"), "forceField"))
    la = sorted(glob_ogg(os.path.join(EX, "kenney_sci-fi-sounds"), "laserLarge"))
    vs = []
    for i, p in enumerate((ff[:2] + la[:2])[:3]):
        x = dec(p, mono=True)
        x = lib.lowpass(x, SR, 5200, order=2)
        x = lib.highpass(x, SR, 120, order=1)
        vs.append(cut(lib.trim(x, SR, -46), 0.55, 0.12))
    if vs:
        emit("gun_pap_layer", vs, "handling", src="Kenney Sci-Fi Sounds",
             send="hall", send_amt=0.25)
        emit("gun_pap_layer_heavy", [vary(v, 0.82) for v in vs], "impact",
             src="Kenney Sci-Fi Sounds", send="hall", send_amt=0.3)


def glob_ogg(d, stem=""):
    out = []
    for root, _, files in os.walk(d):
        for f in files:
            if f.lower().endswith((".ogg", ".wav", ".mp3")) and stem.lower() in f.lower():
                out.append(os.path.join(root, f))
    return sorted(out)


# ============================================================== handling ===

def build_handling():
    """Reloads, bolts, pumps, slides, switches — from recorded mechanisms."""
    mech = pool([
        os.path.join(OGA, "equipment-clicks-iii/equipment_clicks3.wav"),
        os.path.join(OGA, "equipment-clicks-ii/equipmentclicks.wav"),
    ], length=0.55, thresh=0.10, gap=0.13)
    rifle = pool([os.path.join(OGA, "gun-reload-sounds/assaultriflereload1_0.wav")],
                 length=0.6, thresh=0.10, gap=0.10)
    pistol = pool([os.path.join(OGA, "handgun-reload-sound-effect/reload.wav"),
                   os.path.join(OGA, "gun-reload-sounds/gunreload1.wav")],
                  length=0.6, thresh=0.10, gap=0.10)
    shotg = pool([os.path.join(OGA, "gun-reload-sounds/shotguncock_0.wav"),
                  os.path.join(OGA, "shotgun-reload-sound-effects/4_shell_reload.mp3")],
                 length=0.5, thresh=0.12, gap=0.12)
    starn = pool(glob_ogg(os.path.join(EX, "oga_gun_reload_-_starninjas")),
                 length=0.5, thresh=0.12, gap=0.10)
    lock = pool([os.path.join(OGA, "gun-reload-lock-or-click-sound/"
                                   "gun_reload_lock_or_click_sound.mp3")],
                length=0.4, thresh=0.12, gap=0.06)
    metal = pool(glob_ogg(os.path.join(EX, "oga_100-CC0-wood-metal-SFX"), "metal_hit"),
                 length=0.5, thresh=0.2, gap=0.2)
    kmetal = glob_ogg(os.path.join(EX, "kenney_rpg-audio"), "metalClick") + \
        glob_ogg(os.path.join(EX, "kenney_rpg-audio"), "metalLatch")
    kmetal = [dec(p, mono=True) for p in kmetal[:8]]
    belt = [dec(p, mono=True) for p in glob_ogg(os.path.join(EX, "kenney_rpg-audio"), "beltHandle")[:4]]
    cloth = [dec(p, mono=True) for p in glob_ogg(os.path.join(EX, "kenney_rpg-audio"), "cloth")[:6]]

    allmech = mech + starn + metal
    if not allmech:
        print("  ! no mechanical pool")
        return

    def mk(name, src_pool, idxs, pitch=1.0, dur=0.42, cat="handling", tag=""):
        vs = []
        for i in idxs:
            if not src_pool:
                return
            x = src_pool[i % len(src_pool)]
            x = vary(x, pitch)
            x = lib.highpass(x, SR, 110, order=1)
            vs.append(cut(lib.trim(x, SR, -46), dur, 0.05))
        emit(name, vs, cat, src=tag, jitter=35, rate_jit=0.02)

    # magazines: out is a heavier clack, in is a solid seat
    mk("reload_pistol_out", pistol or allmech, [0, 2], 1.06, 0.45, tag="OGA handgun reload")
    mk("reload_pistol_in", pistol or allmech, [1, 2], 0.98, 0.5, tag="OGA handgun reload")
    mk("reload_rifle_out", rifle or allmech, [0, 1], 0.96, 0.5, tag="OGA gun reload sounds")
    mk("reload_rifle_in", rifle or allmech, [2, 3], 0.92, 0.55, tag="OGA gun reload sounds")
    mk("reload_smg_out", rifle or allmech, [1, 0], 1.10, 0.42, tag="OGA gun reload sounds")
    mk("reload_smg_in", rifle or allmech, [3, 2], 1.06, 0.45, tag="OGA gun reload sounds")
    mk("reload_lmg_out", rifle or allmech, [0, 2], 0.86, 0.6, tag="OGA gun reload sounds")
    mk("reload_lmg_in", rifle or allmech, [3, 1], 0.82, 0.62, tag="OGA gun reload sounds")
    mk("reload_lmg_belt", (belt or cloth or allmech), [0, 1, 2], 0.9, 0.6,
       tag="Kenney RPG Audio")
    mk("reload_shotgun_shell", shotg or allmech, [1, 3, 5], 1.0, 0.4,
       tag="OGA shotgun reload")
    mk("reload_break_open", allmech, [4, 9], 0.88, 0.55, tag="OGA equipment clicks")
    mk("reload_break_close", allmech, [5, 11], 0.84, 0.5, tag="OGA equipment clicks")
    mk("reload_revolver_open", allmech, [6, 13], 1.02, 0.5, tag="OGA equipment clicks")
    mk("reload_revolver_eject", (shotg or allmech), [2, 4], 1.12, 0.45,
       tag="OGA shotgun reload")
    mk("reload_revolver_close", allmech, [7, 15], 0.9, 0.5, tag="OGA equipment clicks")
    mk("reload_raygun_out", (kmetal or allmech), [0, 2], 1.2, 0.4, tag="Kenney RPG Audio")
    mk("reload_raygun_in", (kmetal or allmech), [1, 3], 1.1, 0.45, tag="Kenney RPG Audio")
    mk("bolt_pull", allmech, [8, 17], 0.95, 0.4, tag="OGA equipment clicks")
    mk("bolt_release", allmech, [10, 19], 1.0, 0.35, tag="OGA equipment clicks")
    mk("slide_release", (pistol or allmech), [2, 1], 1.05, 0.32, tag="OGA handgun reload")
    mk("pump_back", shotg or allmech, [0, 2], 0.95, 0.35, tag="OGA shotgun cock")
    mk("pump_forward", shotg or allmech, [1, 3], 0.9, 0.35, tag="OGA shotgun cock")
    mk("dry_fire", (lock or kmetal or allmech), [0, 1, 2], 1.15, 0.2, tag="OGA gun lock click")
    mk("weapon_switch", (cloth or allmech), [0, 2, 4], 1.0, 0.5, tag="Kenney RPG Audio")
    mk("weapon_lower", (cloth or allmech), [1, 3, 5], 0.92, 0.45, tag="Kenney RPG Audio")
    mk("weapon_raise", (cloth or allmech), [2, 4, 0], 1.08, 0.45, tag="Kenney RPG Audio")
    mk("ads_in", (cloth or allmech), [3, 5, 1], 1.15, 0.28, tag="Kenney RPG Audio")
    mk("ads_out", (cloth or allmech), [4, 0, 2], 1.05, 0.28, tag="Kenney RPG Audio")
    mk("low_ammo", (kmetal or allmech), [3, 3], 1.3, 0.2, cat="ui", tag="Kenney RPG Audio")

    # shell casings on the ground
    shells = pool(glob_ogg(os.path.join(EX, "oga_100-CC0-wood-metal-SFX"), "keys_"),
                  length=0.6, thresh=0.14, gap=0.14) or allmech
    emit("shell_drop", [cut(lib.trim(vary(shells[i % len(shells)], 1.25 + 0.05 * i), SR, -48), 0.55, 0.08)
                        for i in range(5)], "shell",
         src="OGA 100 CC0 metal & wood SFX", jitter=70, rate_jit=0.05)
    emit("shell_drop_shotgun",
         [cut(lib.trim(vary(shells[(i + 2) % len(shells)], 0.85), SR, -48), 0.6, 0.08)
          for i in range(4)], "shell",
         src="OGA 100 CC0 metal & wood SFX", jitter=60, rate_jit=0.05)


# =============================================================== impacts ===

def build_impacts():
    def kp(stem, n, cat="impact", name=None, pitch=1.0, dur=0.6, tag="Kenney Impact Sounds"):
        ps = glob_ogg(os.path.join(EX, "kenney_impact-sounds"), stem)
        if not ps:
            print("  ! no kenney", stem)
            return
        vs = []
        for i in range(n):
            x = dec(ps[i % len(ps)], mono=True)
            x = vary(x, pitch)
            vs.append(cut(lib.trim(x, SR, -46), dur, 0.06))
        emit(name or stem, vs, cat, src=tag, jitter=60, rate_jit=0.05)

    kp("impactMetal_light", 4, name="impact_metal", pitch=1.0, dur=0.55)
    kp("impactWood_medium", 4, name="impact_wood", pitch=1.0, dur=0.5)
    kp("impactGlass_light", 3, name="impact_glass", pitch=1.0, dur=0.6)
    kp("impactPlate_light", 4, name="impact_concrete", pitch=0.9, dur=0.5)
    kp("impactSoft_medium", 4, name="impact_dirt", pitch=0.85, dur=0.45)
    kp("impactPunch_medium", 3, name="flesh_hit", cat="impact", pitch=0.92, dur=0.45)
    kp("impactPunch_heavy", 3, name="knife_hit", cat="impact", pitch=1.0, dur=0.5)
    kp("impactMetal_medium", 3, name="knife_hit_wall", cat="impact", pitch=1.1, dur=0.5)
    kp("impactSoft_heavy", 3, name="zombie_bodyfall", cat="impact", pitch=0.8, dur=0.9)
    kp("impactPlank_medium", 3, name="board_slam", cat="foley", pitch=0.9, dur=0.8)

    # wet gore for gibs, from the CC0 squish/splatter recordings
    gib = pool(glob_ogg(os.path.join(EX, "oga_100-CC0-SFX_0"), "plop") +
               glob_ogg(os.path.join(EX, "oga_sfx_100_v2"), "hit_"),
               length=0.7, thresh=0.15, gap=0.2)
    if gib:
        emit("zombie_gib", [cut(lib.trim(vary(gib[i % len(gib)], 0.8), SR, -46), 0.8, 0.1)
                            for i in range(3)], "impact",
             src="OGA 100 CC0 SFX", jitter=70, rate_jit=0.06)

    # headshot / hitmarker — a wet crack and a short tick
    hs = glob_ogg(os.path.join(EX, "kenney_impact-sounds"), "impactBell_heavy")
    tick = glob_ogg(os.path.join(EX, "kenney_interface-sounds"), "tick_")
    if hs:
        vs = [cut(lib.trim(vary(dec(hs[i % len(hs)], mono=True), 0.75), SR, -46), 0.55, 0.08)
              for i in range(3)]
        emit("headshot", vs, "impact", src="Kenney Impact Sounds", jitter=50)
    if tick:
        emit("hitmarker", [cut(lib.trim(dec(p, mono=True), SR, -46), 0.16, 0.03)
                           for p in tick[:2]], "ui", bus="ui",
             src="Kenney Interface Sounds", jitter=40)
        emit("hitmarker_head", [cut(lib.trim(vary(dec(p, mono=True), 1.25), SR, -46), 0.18, 0.03)
                                for p in tick[:2]], "ui", bus="ui",
             src="Kenney Interface Sounds", jitter=40)

    # explosions
    ex_paths = [os.path.join(OGA, "explosions-4/explosion1_0.ogg"),
                os.path.join(OGA, "explosions-4/explosion2.ogg"),
                os.path.join(OGA, "chunky-explosion/Chunky Explosion.mp3")]
    ex_paths = [p for p in ex_paths if os.path.exists(p)]
    el = os.path.join(RAW, "special/explosion_big.mp3")
    vs = []
    if os.path.exists(el):
        a = dec(el, mono=True)
        for s in lib.slice_events(a, SR, length=2.6, thresh=0.14, gap=0.8)[:2]:
            vs.append(cut(lib.trim(s, SR, -50), 2.4, 0.3))
    for p in ex_paths[:2]:
        vs.append(cut(lib.trim(dec(p, mono=True), SR, -50), 2.4, 0.3))
    if vs:
        emit("explosion", vs[:3], "boom", src="ElevenLabs + OGA explosions",
             send="boom", send_amt=0.4, jitter=50, rate_jit=0.04)

    nb = os.path.join(RAW, "special/nuke_blast.mp3")
    if os.path.exists(nb):
        a = lib.lowpass(dec(nb, mono=True), SR, 3800, order=2)
        emit("nuke_blast", [cut(lib.trim(a, SR, -55), 5.2, 0.6)], "boom",
             src="ElevenLabs nuke_blast", send="boom", send_amt=0.5)

    # grenades
    pin = glob_ogg(os.path.join(EX, "oga_100-CC0-wood-metal-SFX"), "metal_spring")
    if pin:
        emit("grenade_pin", [cut(lib.trim(vary(dec(p, mono=True), 1.2), SR, -46), 0.4, 0.05)
                             for p in pin[:2]], "handling",
             src="OGA 100 CC0 metal & wood SFX", jitter=50)
    bnc = glob_ogg(os.path.join(EX, "oga_100-CC0-wood-metal-SFX"), "metal_hit")
    if bnc:
        emit("grenade_bounce",
             [cut(lib.trim(vary(dec(p, mono=True), 1.35), SR, -46), 0.35, 0.05)
              for p in bnc[:3]], "handling",
             src="OGA 100 CC0 metal & wood SFX", jitter=80, rate_jit=0.07)

    # knife swing — a cloth/air whoosh
    sw = glob_ogg(os.path.join(EX, "oga_sword_-_starninjas_1")) or \
        glob_ogg(os.path.join(EX, "kenney_rpg-audio"), "drawKnife")
    if sw:
        emit("knife_swing", [cut(lib.trim(vary(dec(p, mono=True), 0.95), SR, -46), 0.45, 0.08)
                             for p in sw[:3]], "handling",
             src="OGA sword SFX (StarNinjas)", jitter=60, rate_jit=0.05)


# ================================================================= foley ===

def build_foley():
    # footsteps -------------------------------------------------------------
    def steps(name, paths, n, pitch=1.0, dur=0.35, cat="footstep", tag=""):
        arr = [p for p in paths if os.path.exists(p)]
        if not arr:
            print("  ! no steps for", name)
            return
        vs = []
        for i in range(n):
            x = dec(arr[i % len(arr)], mono=True)
            x = vary(x, pitch * (1 + 0.03 * ((i % 3) - 1)))
            vs.append(cut(lib.trim(x, SR, -44), dur, 0.05))
        emit(name, vs, cat, src=tag, jitter=90, rate_jit=0.07)

    kdirt = glob_ogg(os.path.join(EX, "kenney_impact-sounds"), "footstep_grass")
    kwood = glob_ogg(os.path.join(EX, "kenney_impact-sounds"), "footstep_wood")
    kconc = glob_ogg(os.path.join(EX, "kenney_impact-sounds"), "footstep_concrete")
    ogravel = glob_ogg(os.path.join(EX, "oga_[kdd]DifferentSteps_0"))
    gravel = [p for p in ogravel if "gravel" in p or "mud" in p]
    owood = [p for p in ogravel if "wood" in p]
    ostone = [p for p in ogravel if "stone" in p]

    steps("footstep_dirt", kdirt + gravel, 4, 1.0, 0.35,
          tag="Kenney Impact Sounds + OGA Different Steps")
    steps("footstep_wood", kwood + owood, 4, 1.0, 0.35,
          tag="Kenney Impact Sounds + OGA Different Steps")
    steps("footstep_concrete", kconc + ostone, 4, 1.0, 0.35,
          tag="Kenney Impact Sounds + OGA Different Steps")
    # a zombie is heavier, slower and drags
    steps("zombie_footstep", kconc + kdirt + gravel, 6, 0.78, 0.5,
          tag="Kenney Impact Sounds + OGA Different Steps")
    steps("hellhound_footstep", kdirt + gravel, 4, 1.35, 0.25,
          tag="Kenney Impact Sounds + OGA Different Steps")
    steps("land_soft", kconc, 3, 0.9, 0.4, tag="Kenney Impact Sounds")
    steps("land_hard", kconc + kdirt, 3, 0.7, 0.6, cat="impact",
          tag="Kenney Impact Sounds")

    # boards ----------------------------------------------------------------
    tear = glob_ogg(os.path.join(EX, "oga_100-CC0-wood-metal-SFX"), "wood_breaking") + \
        glob_ogg(os.path.join(EX, "oga_100-CC0-wood-metal-SFX"), "wood_cracking")
    rep = glob_ogg(os.path.join(EX, "oga_100-CC0-wood-metal-SFX"), "wood_hammer") + \
        glob_ogg(os.path.join(EX, "oga_100-CC0-wood-metal-SFX"), "hammer_")
    if tear:
        emit("board_tear", [cut(lib.trim(vary(dec(p, mono=True), 0.92), SR, -46), 1.1, 0.12)
                            for p in tear[:3]], "foley",
             src="OGA 100 CC0 metal & wood SFX", jitter=60, rate_jit=0.05)
    if rep:
        emit("board_repair", [cut(lib.trim(dec(p, mono=True), SR, -46), 1.0, 0.12)
                              for p in rep[:2]], "foley",
             src="OGA 100 CC0 metal & wood SFX", jitter=60, rate_jit=0.05)

    # doors -----------------------------------------------------------------
    doors = glob_ogg(os.path.join(EX, "oga_door_close_-_starninjas")) + \
        glob_ogg(os.path.join(EX, "oga_sfx_100_v2"), "door_") + \
        [os.path.join(OGA, "creaky-door-hinge-spooky/creaky_door_hinge.wav")]
    doors = [p for p in doors if os.path.exists(p)]
    if doors:
        emit("door_open", [cut(lib.trim(vary(dec(p, mono=True), 0.9), SR, -46), 2.2, 0.2)
                           for p in doors[:2]], "foley",
             src="OGA door SFX", jitter=40)

    # mystery box -----------------------------------------------------------
    wood = glob_ogg(os.path.join(EX, "oga_100-CC0-SFX_0"), "wooded_box_open") + \
        glob_ogg(os.path.join(EX, "oga_100-CC0-wood-metal-SFX"), "wood_close")
    if wood:
        emit("box_open", [cut(lib.trim(dec(wood[0], mono=True), SR, -46), 1.4, 0.15)], "foley",
             src="OGA 100 CC0 SFX")
        emit("box_close", [cut(lib.trim(vary(dec(wood[-1], mono=True), 0.95), SR, -46), 1.2, 0.15)],
             "foley", src="OGA 100 CC0 metal & wood SFX")

    # perks -----------------------------------------------------------------
    drink = glob_ogg(os.path.join(EX, "oga_80-CC0-creature-SFX_0"), "eat_") + \
        glob_ogg(os.path.join(EX, "oga_100-CC0-SFX_0"), "splash")
    if drink:
        emit("perk_drink", [cut(lib.trim(vary(dec(p, mono=True), 0.95), SR, -46), 1.6, 0.15)
                            for p in drink[:2]], "foley",
             src="OGA 80 CC0 creature SFX", jitter=40)
    burp = glob_ogg(os.path.join(EX, "oga_80-CC0-creature-SFX_0"), "burp_")
    if burp:
        vs = [cut(lib.trim(vary(dec(p, mono=True), 0.85), SR, -46), 1.1, 0.12) for p in burp[:2]]
        vs.append(cut(lib.trim(vary(dec(burp[0], mono=True), 0.72), SR, -46), 1.2, 0.12))
        emit("perk_burp", vs, "voice", src="OGA 80 CC0 creature SFX", jitter=70, rate_jit=0.06)

    # purchase / deny -------------------------------------------------------
    coins = glob_ogg(os.path.join(EX, "kenney_rpg-audio"), "handleCoins")
    conf = glob_ogg(os.path.join(EX, "kenney_interface-sounds"), "confirmation")
    err = glob_ogg(os.path.join(EX, "kenney_interface-sounds"), "error")
    if coins and conf:
        a = dec(coins[0], mono=True)
        b = dec(conf[0], mono=True)
        n = max(len(a), len(b))
        mix = np.zeros(n, np.float32)
        mix[: len(a)] += a
        mix[: len(b)] += b * 0.55
        emit("purchase", [cut(lib.trim(mix, SR, -46), 1.2, 0.12)], "powerup", bus="ui",
             src="Kenney RPG Audio + Interface Sounds")
    if err:
        emit("purchase_deny", [cut(lib.trim(vary(dec(err[0], mono=True), 0.8), SR, -46), 0.7, 0.08)],
             "ui", bus="ui", src="Kenney Interface Sounds")

    # UI --------------------------------------------------------------------
    for name, stem, pitch in (("ui_click", "click_", 1.0), ("ui_hover", "tick_", 1.15),
                              ("ui_back", "back_", 1.0)):
        ps = glob_ogg(os.path.join(EX, "kenney_interface-sounds"), stem)
        if ps:
            emit(name, [cut(lib.trim(vary(dec(p, mono=True), pitch), SR, -46), 0.35, 0.05)
                        for p in ps[:2]], "ui", bus="ui",
                 src="Kenney Interface Sounds", jitter=30)

    glitch = glob_ogg(os.path.join(EX, "kenney_interface-sounds"), "glitch_")
    if glitch:
        emit("radio_blip", [cut(lib.trim(vary(dec(p, mono=True), 1.2), SR, -46), 0.25, 0.04)
                            for p in glitch[:2]], "ui", bus="ui",
             src="Kenney Interface Sounds", jitter=40)


# ================================================================ voices ===

def build_voices():
    """Zombies, hellhounds, the player, the announcer — all recorded takes.

    Each ElevenLabs render holds several vocalisations in one pass, so they are
    segmented into phrases (silence, then a cut at the quietest dip inside an
    over-long phrase — see lib.phrases) and each phrase becomes one variant.
    """
    def take(rel, **kw):
        p = os.path.join(RAW, rel)
        if not os.path.exists(p):
            print("  ! missing", p)
            return []
        return lib.phrases(dec(p, mono=True), SR, **kw)

    def voice(name, segs, n, lp=None, hp=70, pitches=None, cat="voice", dur=3.0,
              tag="", tilt=None):
        if not segs:
            print("  ! no material for", name)
            return
        pitches = pitches or [1.0, 0.94, 1.06, 0.9, 1.03, 0.97, 1.09, 0.92]
        vs = []
        for i in range(n):
            x = segs[i % len(segs)]
            # once the real takes run out, the extra variants are pitched
            x = vary(x, 1.0 if i < len(segs) else pitches[i % len(pitches)])
            x = lib.highpass(x, SR, hp, order=1)
            if tilt:
                x = lib.biquad(x, SR, "highshelf", tilt[0], 0.7, tilt[1])
            if lp:
                x = lib.lowpass(x, SR, lp, order=1)
            vs.append(cut(lib.trim(x, SR, -42), dur, 0.14))
        emit(name, vs, cat, src=tag, jitter=130, rate_jit=0.07)

    # zombies ---------------------------------------------------------------
    groans = []
    for f in ("zombie/groan_a.mp3", "zombie/groan_b.mp3", "zombie/groan_c.mp3",
              "zombie/groan_d.mp3", "zombie/groan_e.mp3",
              "zombie/crawler.mp3", "zombie/pain.mp3"):
        groans += take(f, target=2.2, min_len=0.7)
    voice("zombie_groan", groans, 12, lp=5200, dur=3.0,
          tag="ElevenLabs zombie groan / crawler / pain takes")

    screams = []
    for f in ("zombie/scream_a.mp3", "zombie/scream_b.mp3", "zombie/scream_c.mp3"):
        screams += take(f, target=2.0, min_len=0.7)
    # a sprinter must read as a throaty roar, never as a shriek
    voice("zombie_scream", screams, 8, lp=7000, dur=2.6, tilt=(3500, -7.0),
          tag="ElevenLabs sprinter scream takes")

    attacks = []
    for f in ("zombie/attack_a.mp3", "zombie/attack_b.mp3", "zombie/attack_c.mp3"):
        attacks += take(f, target=1.2, min_len=0.25, floor_db=-18.0, min_gap=0.15)
    voice("zombie_attack", attacks, 8, lp=6500, dur=1.6,
          tag="ElevenLabs zombie attack takes")

    deaths = []
    for f in ("zombie/death_a.mp3", "zombie/death_b.mp3", "zombie/death_c.mp3"):
        deaths += take(f, target=2.4, min_len=0.8)
    voice("zombie_death", deaths, 8, lp=5200, dur=2.8,
          tag="ElevenLabs zombie death takes")

    voice("zombie_rise_dirt", take("zombie/rise.mp3", target=2.5, min_len=0.6),
          4, lp=7000, dur=3.0, tag="ElevenLabs zombie rise takes")

    # hellhound -------------------------------------------------------------
    voice("hellhound_growl",
          take("hound/growl.mp3", target=2.4, min_len=0.8)
          + take("hound/growl_b.mp3", target=2.4, min_len=0.8),
          6, lp=5200, dur=3.0, tag="ElevenLabs hellhound growl takes")
    voice("hellhound_bite",
          take("hound/bite.mp3", target=1.0, min_len=0.25, floor_db=-18.0, min_gap=0.15)
          + take("hound/bite_b.mp3", target=1.0, min_len=0.25, floor_db=-18.0, min_gap=0.15),
          6, lp=6500, dur=1.5, tag="ElevenLabs hellhound bite takes")
    voice("hellhound_death",
          take("hound/death.mp3", target=2.2, min_len=0.7)
          + take("hound/death_b.mp3", target=2.2, min_len=0.7),
          5, lp=5500, dur=2.8, tag="ElevenLabs hellhound death takes")

    # the player ------------------------------------------------------------
    voice("player_hurt",
          take("human/hurt.mp3", target=1.0, min_len=0.25, floor_db=-18.0, min_gap=0.14),
          4, lp=7000, dur=1.5, tag="ElevenLabs player pain takes")
    voice("player_down", take("human/down.mp3", target=3.0, min_len=1.0),
          2, lp=6500, dur=3.6, tag="ElevenLabs player down take")
    efforts = take("human/effort.mp3", target=0.7, min_len=0.2,
                   floor_db=-20.0, min_gap=0.12)
    voice("jump_grunt", efforts, 4, lp=7000, dur=1.0,
          tag="ElevenLabs player effort takes")
    voice("sprint_breath", efforts[::-1], 3, lp=4500, dur=1.2,
          tag="ElevenLabs player effort takes")

    # announcer -------------------------------------------------------------
    for name, rel in (("vox_max_ammo", "vox/max_ammo.mp3"),
                      ("vox_insta_kill", "vox/insta_kill.mp3"),
                      ("vox_double_points", "vox/double_points.mp3"),
                      ("vox_nuke", "vox/nuke.mp3"),
                      ("vox_carpenter", "vox/carpenter.mp3"),
                      ("vox_fire_sale", "vox/fire_sale.mp3")):
        p = os.path.join(RAW, rel)
        if not os.path.exists(p):
            continue
        a = lib.trim(dec(p, mono=True), SR, -46, head=0.01, tail=0.12)
        # old PA / field radio: band-limit hard, saturate, add a little room
        x = lib.highpass(a, SR, 380, order=2)
        x = lib.lowpass(x, SR, 3200, order=2)
        x = lib.biquad(x, SR, "peaking", 1800, 1.2, 5.0)
        x = np.tanh(x * 2.6).astype(np.float32) * 0.6
        x = lib.lowpass(x, SR, 3400, order=1)
        wet = lib.to_mono(lib.reverb(x, SR, mix=0.18, dur=0.8, decay=5.0,
                                     predelay=0.008, damp=2600, seed=5))
        emit(name, [lib.fade(wet, SR, 0.004, 0.05)], "vox", bus="ui",
             src="ElevenLabs text-to-speech (processed PA)")

    # radio carrier hiss (loop)
    n = int(SR * 2.0)
    hiss = rng.standard_normal(n).astype(np.float32)
    hiss = lib.lowpass(lib.highpass(hiss, SR, 600, 2), SR, 2600, 2)
    hiss *= 0.25
    emit("radio_static", [lib.seamless(hiss, SR, 0.4)], "ui", loop=True, bus="ui",
         src="generated noise bed")



# ================================================================= world ===

def build_world():
    def one(name, path, cat, dur=None, pitch=1.0, lp=None, tag="", bus=None, mono=True):
        if not os.path.exists(path):
            print("  ! missing", path)
            return
        x = dec(path, mono=mono)
        if pitch != 1.0:
            x = vary(x, pitch)
        if lp:
            x = lib.lowpass(x, SR, lp, order=1)
        x = lib.trim(x, SR, -48)
        if dur:
            x = cut(x, dur, 0.2)
        emit(name, [x], cat, src=tag, bus=bus, mono=mono)

    one("power_on", os.path.join(RAW, "special/power_on.mp3"), "powerup", dur=5.0,
        tag="ElevenLabs power_on")
    # the Pack-a-Punch animation runs ~4.5 s, so the sound must not outlast it
    one("pap_upgrade", os.path.join(RAW, "special/pap_upgrade.mp3"), "powerup", dur=4.5,
        tag="ElevenLabs pap_upgrade")
    one("hellhound_spawn", os.path.join(RAW, "special/hellhound_spawn.mp3"), "boom",
        dur=4.5, tag="ElevenLabs hellhound_spawn")
    one("box_teddy", os.path.join(RAW, "special/box_teddy.mp3"), "powerup", dur=4.5,
        lp=7000, tag="ElevenLabs box_teddy")
    # the box music is played *positionally* (from the box itself), and a
    # stereo buffer is downmixed by the panner anyway, so keep it mono
    # the mystery box spins for 4.4 s (interactables.js), so the jingle stops with it
    one("box_music", os.path.join(RAW, "special/box_music.mp3"), "music", dur=4.6,
        lp=8000, bus="music", tag="ElevenLabs box_music", mono=True)

    p = os.path.join(RAW, "special/powerup_spawn.mp3")
    if os.path.exists(p):
        a = dec(p, mono=True)
        segs = lib.slice_events(a, SR, length=1.8, thresh=0.13, gap=0.5) or [a]
        emit("powerup_spawn", [cut(lib.trim(s, SR, -46), 1.6, 0.15) for s in segs[:2]],
             "powerup", src="ElevenLabs powerup_spawn", jitter=40)
    p = os.path.join(RAW, "special/powerup_grab.mp3")
    if os.path.exists(p):
        a = dec(p, mono=True)
        segs = lib.slice_events(a, SR, length=1.2, thresh=0.13, gap=0.4) or [a]
        emit("powerup_grab", [cut(lib.trim(s, SR, -46), 1.1, 0.12) for s in segs[:2]],
             "powerup", src="ElevenLabs powerup_grab", jitter=40)

    # power-up beacon loop + blink
    ff = glob_ogg(os.path.join(EX, "kenney_sci-fi-sounds"), "forceField")
    if ff:
        x = dec(ff[0], mono=True)
        x = lib.lowpass(x, SR, 4200, order=1)
        x = lib.seamless(np.tile(x, 3)[: int(SR * 2.4)], SR, 0.4)
        emit("powerup_loop", [x], "ambient", loop=True, src="Kenney Sci-Fi Sounds")
    ph = glob_ogg(os.path.join(EX, "kenney_digital-audio"), "phaserUp")
    if ph:
        emit("powerup_blink", [cut(lib.trim(lib.lowpass(dec(ph[0], mono=True), SR, 5000, 1),
                                            SR, -46), 0.4, 0.06)], "ui", bus="ui",
             src="Kenney Digital Audio")

    # power-up announcements double as short cues
    for name, stem in (("max_ammo", "powerUp1"), ("insta_kill", "powerUp3"),
                       ("double_points", "powerUp5"), ("carpenter", "powerUp7"),
                       ("fire_sale", "powerUp9")):
        ps = glob_ogg(os.path.join(EX, "kenney_digital-audio"), stem)
        if ps:
            x = lib.lowpass(dec(ps[0], mono=True), SR, 5200, order=1)
            emit(name, [cut(lib.trim(x, SR, -46), 1.2, 0.1)], "powerup", bus="ui",
                 src="Kenney Digital Audio")

    # loops -----------------------------------------------------------------
    fire = os.path.join(OGA, "fire-crackling/fire-1.wav")
    if os.path.exists(fire):
        x = dec(fire, mono=False)
        x = lib.lowpass(x, SR, 7000, order=1)
        x = lib.seamless(x[: int(SR * 8.0)], SR, 1.0)
        # positional (one per fire in the map), so mono — the panner would
        # collapse a stereo buffer anyway and it costs twice the memory
        emit("fire_loop", [x], "ambient", loop=True, mono=True,
             src="OGA fire crackling")

    amb = os.path.join(DL, "ex/oga_dark_ambiences/ambience-2.wav")
    wind = os.path.join(OGA, "mild-wind-background-noise/wind background noise 2.wav")
    layers = []
    if os.path.exists(wind):
        w = dec(wind, mono=False)
        layers.append(lib.lowpass(w, SR, 2200, order=1) * 0.9)
    if os.path.exists(amb):
        d = dec(amb, mono=False)
        layers.append(lib.lowpass(d, SR, 3000, order=1) * 0.7)
    if layers:
        n = int(SR * 18.0)
        mix = np.zeros((n, 2), np.float32)
        for lyr in layers:
            t = np.tile(lyr, (int(n / len(lyr)) + 1, 1))[:n]
            mix += t
        emit("ambient_loop", [lib.seamless(mix, SR, 2.0)], "ambient", loop=True,
             mono=False, bus="ambient", src="OGA wind + dark ambiences")

    # heartbeat — a real bass drum, two thumps a second apart
    bd = os.path.join(VCSL, "BDrumNew_hit_v2_rr1_Sum.wav")
    if os.path.exists(bd):
        h = lib.lowpass(lib.trim(dec(bd, mono=True), SR, -46), SR, 220, order=2)
        n = int(SR * 1.0)
        beat = np.zeros(n, np.float32)
        for off, amp in ((0.0, 1.0), (0.26, 0.62)):
            s = int(SR * off)
            m = min(len(h), n - s)
            beat[s:s + m] += h[:m] * amp
        emit("heartbeat_loop", [lib.seamless(np.tile(beat, 2), SR, 0.05)], "ambient",
             loop=True, src="VCSL Bass Drum")


# ============================================================== stingers ===

def organ(note, dur, gain=1.0, pitch=1.0, rank="pedal"):
    """One sustained VCSL pipe-organ note, looped out to `dur` seconds.

    `rank` picks the register: "pedal" is the 16' pedal stops (the weight),
    "manual" is the Man3 flue chorus an octave or two up (the part a laptop
    speaker can actually reproduce).
    """
    names = ([f"NT5_PedalQuiet_{note}_rr1.wav", f"NT5_Man3Quiet_{note}_rr1.wav"]
             if rank == "pedal" else
             [f"NT5_Man3Quiet_{note}_rr1.wav", f"NT5_PedalQuiet_{note}_rr1.wav"])
    p = next((os.path.join(VCSL, f) for f in names
              if os.path.exists(os.path.join(VCSL, f))), None)
    if p is None:
        return None
    x = lib.to_mono(dec(p))
    x = lib.trim(x, SR, -50, head=0.0, tail=0.3)
    if pitch != 1.0:
        x = vary(x, pitch)
    n = int(SR * dur)
    if len(x) < n:
        x = np.tile(x, int(n / len(x)) + 1)
    return x[:n] * gain


def sample(fn, pitch=1.0, gain=1.0):
    p = os.path.join(VCSL, fn)
    if not os.path.exists(p):
        return None
    x = lib.to_mono(dec(p))
    x = lib.trim(x, SR, -52, head=0.0, tail=0.4)
    if pitch != 1.0:
        x = vary(x, pitch)
    return x * gain


def place(canvas, x, at, gain=1.0):
    if x is None:
        return canvas
    s = int(SR * at)
    m = min(len(x), len(canvas) - s)
    if m > 0:
        canvas[s:s + m] += x[:m] * gain
    return canvas


def swell(x, attack, release, total):
    """Shape a sustained sample into a slow swell."""
    n = len(x)
    e = np.ones(n, np.float32)
    na = min(n, int(SR * attack))
    nr = min(n - na, int(SR * release))
    if na > 1:
        e[:na] = np.linspace(0, 1, na) ** 1.8
    if nr > 1:
        e[-nr:] *= np.linspace(1, 0, nr) ** 1.6
    return (x * e)[: int(SR * total)]


def band_share(a, lo, hi):
    m = lib.to_mono(np.asarray(a, dtype=np.float32))
    sp = np.abs(np.fft.rfft(m * np.hanning(len(m)))) ** 2
    fr = np.fft.rfftfreq(len(m), 1 / SR)
    tot = sp.sum()
    return float(sp[(fr >= lo) & (fr < hi)].sum() / tot) if tot > 0 else 0.0


def voice_for_small_speakers(a, cap=0.45, knee=150.0):
    """Stop the sub-bass swamping everything a laptop can actually reproduce.

    An organ pedal note and a cinematic sub swell put 90 % of their energy under
    200 Hz. On studio monitors that is enormous; on the speakers this game will
    be played through it is *inaudible*, and the sting reads as a faint thud.
    Shelving the bottom down until it is under `cap` of the total leaves the
    weight present without letting it mask the bell and the choir.
    """
    for _ in range(6):
        if band_share(a, 0, 200) <= cap:
            break
        a = lib.biquad(a, SR, "lowshelf", knee, 0.7, -3.0)
    return a


def build_stingers():
    """EL sting + VCSL organ/bell/gong/timpani, layered, then de-harshed."""
    plans = {
        "round_end": dict(
            el="stinger/round_end_b.mp3", dur=6.6, el_gain=0.85, el_at=0.25,
            organs=[("D#1", "pedal", 0.0, 6.2, 0.55, 1.0),
                    ("A1", "pedal", 0.6, 5.4, 0.30, 1.0),
                    ("D#2", "manual", 0.5, 5.2, 0.26, 1.0)],
            bells=[("chimes_C3_pp_rr2.wav", 1.15, 0.62, 0.5),
                   ("TB_hit_G4_v2_1.wav", 3.5, 0.20, 0.5)],
            gong=("gong_p.wav", 0.0, 0.42, 0.82), timp=None,
            rev=dict(mix=0.4, dur=3.2, decay=1.5, predelay=0.03, damp=2600, seed=11),
            knee=3600, cap=0.45),
        "round_start": dict(
            el="stinger/round_start_a.mp3", dur=5.4, el_gain=0.7, el_at=0.3,
            organs=[("A1", "pedal", 0.0, 5.0, 0.5, 0.94),
                    ("A2", "manual", 0.45, 4.6, 0.38, 1.0),
                    ("C3", "manual", 0.9, 4.0, 0.24, 1.0)],
            bells=[("chimes_D3_pp_rr3.wav", 1.4, 0.70, 0.45),
                   ("TB_hit_C4_v2_1.wav", 3.0, 0.26, 0.5)],
            gong=("gong_2_mp.wav", 0.0, 0.34, 0.78),
            timp=("Timpani1_Hit_v2_rr1_Sum.wav", 0.02, 0.45, 0.82),
            rev=dict(mix=0.42, dur=3.0, decay=1.7, predelay=0.03, damp=2300, seed=12),
            knee=3200, cap=0.42),
        "hellround_start": dict(
            el="stinger/hellround_start_b.mp3", dur=5.6, el_gain=0.75, el_at=0.1,
            organs=[("F#1", "pedal", 0.2, 5.0, 0.45, 0.92),
                    ("F#2", "manual", 0.6, 4.6, 0.34, 1.0),
                    ("C3", "manual", 1.0, 4.0, 0.26, 1.0)],
            bells=[("TB_hit_C4_v2_1.wav", 2.1, 0.30, 0.5)],
            gong=("gong_f.wav", 0.0, 0.5, 0.7),
            timp=("Timpani2_Hit_v2_rr1_Sum.wav", 0.0, 0.55, 0.76),
            growl=("hound/growl.mp3", 0.9, 0.34, 0.72),
            rev=dict(mix=0.38, dur=3.4, decay=1.4, predelay=0.035, damp=2000, seed=13),
            knee=3000, cap=0.45),
        "game_over": dict(
            # _b builds instead of hitting at once, and carries twice the mid
            # energy of _a — it is the one that reads as mournful rather than
            # as a low thud
            el="stinger/game_over_b.mp3", dur=10.5, el_gain=0.85, el_at=0.25,
            organs=[("A1", "pedal", 0.0, 9.6, 0.5, 1.0),
                    ("A2", "manual", 1.0, 8.4, 0.36, 1.0),
                    ("C3", "manual", 2.4, 6.6, 0.24, 1.0)],
            bells=[("chimes_C3_pp_rr2.wav", 2.0, 0.55, 0.5),
                   ("chimes_F#3_p_rr1.wav", 5.4, 0.36, 0.5),
                   ("TB_hit_C4_v2_1.wav", 8.0, 0.22, 0.5)],
            gong=("gong_mf.wav", 0.0, 0.34, 0.75), timp=None,
            rev=dict(mix=0.45, dur=4.0, decay=1.2, predelay=0.04, damp=2400, seed=14),
            knee=3400, cap=0.42),
    }

    for name, pl in plans.items():
        n = int(SR * pl["dur"])
        c = np.zeros(n, np.float32)

        # 1. the reversed gong swell that opens the sting
        if pl.get("gong"):
            fn, at, g, pitch = pl["gong"]
            x = sample(fn, pitch=pitch, gain=g)
            if x is not None:
                rev_x = x[::-1].copy()
                rev_x = lib.lowpass(rev_x, SR, 2600, order=2)
                head = min(len(rev_x), int(SR * min(2.6, pl["dur"] * 0.45)))
                rev_x = lib.fade(rev_x[-head:], SR, 0.4, 0.08)
                place(c, rev_x, at)

        # 2. the sustained organ bed — pedal for weight, manual for audibility
        for note, rank, at, dur, g, pitch in pl["organs"]:
            x = organ(note, dur + 0.4, gain=g, pitch=pitch, rank=rank)
            if x is not None:
                x = swell(x, min(1.4, dur * 0.35), min(2.2, dur * 0.5), dur)
                x = lib.lowpass(x, SR, 2400 if rank == "pedal" else 4200, order=1)
                place(c, x, at)

        # 3. bell tolls — the part that carries on a small speaker
        for fn, at, g, pitch in pl["bells"]:
            x = sample(fn, pitch=pitch, gain=g)
            if x is not None:
                x = lib.lowpass(x, SR, 3400, order=1)
                place(c, x, at)

        # 4. a low drum under the downbeat
        if pl.get("timp"):
            fn, at, g, pitch = pl["timp"]
            x = sample(fn, pitch=pitch, gain=g)
            if x is not None:
                place(c, lib.lowpass(x, SR, 900, order=2), at)

        # 5. a buried growl for the hell round
        if pl.get("growl"):
            rel, at, g, pitch = pl["growl"]
            p = os.path.join(RAW, rel)
            if os.path.exists(p):
                segs = lib.phrases(dec(p, mono=True), SR, target=2.4, min_len=0.8)
                if segs:
                    x = lib.lowpass(vary(segs[0], pitch), SR, 1400, order=2) * g
                    place(c, x, at)

        # 6. the ElevenLabs sting itself, de-harshed first
        p = os.path.join(RAW, pl["el"])
        if os.path.exists(p):
            x = lib.to_mono(dec(p))
            x = lib.trim(x, SR, -50, head=0.0, tail=0.3)
            x = lib.deharsh(x, SR, knee=pl["knee"])
            x = lib.fade(x, SR, 0.35, 0.6)
            place(c, x, pl["el_at"], pl["el_gain"])

        # 7. one shared space, a final de-harsh pass, a low-end trim so the mids
        #    survive on laptop speakers, and a slow top and tail
        w = lib.reverb(c, SR, **pl["rev"])[:n]
        w = lib.deharsh(w, SR, knee=pl["knee"] + 400)
        w = lib.highpass(w, SR, 32, order=1)
        w = voice_for_small_speakers(w, cap=pl["cap"])
        w = lib.fade(w, SR, 0.14, min(1.2, pl["dur"] * 0.25))
        emit(name, [w], "stinger", bus="music", mono=False,
             src="ElevenLabs sting + VCSL organ/bell/gong/timpani")



# ================================================================= music ===

def build_music():
    """Long beds: the menu track, the death track and the in-round layers."""
    def bed(name, notes, dur, bell_every=None, wind=0.0, seed=3, lp=2600, cat="music"):
        n = int(SR * dur)
        c = np.zeros(n, np.float32)
        for note, rank, gain, pitch in notes:
            x = organ(note, dur + 1.0, gain=gain, pitch=pitch, rank=rank)
            if x is not None:
                place(c, lib.lowpass(x[:n], SR, lp, order=1), 0.0)
        if bell_every:
            b = sample("chimes_C3_pp_rr2.wav", 1.0, 0.3)
            if b is not None:
                b = lib.lowpass(b, SR, 3000, order=1)
                t = bell_every * 0.5
                while t < dur - 1.0:
                    place(c, b, t, 0.8 if int(t) % 2 else 0.5)
                    t += bell_every
        if wind > 0:
            wp = os.path.join(OGA, "mild-wind-background-noise/wind background noise 2.wav")
            if os.path.exists(wp):
                w = lib.to_mono(dec(wp))
                w = lib.lowpass(w, SR, 1400, order=2)
                w = np.tile(w, int(n / len(w)) + 1)[:n]
                c += w * wind
        s = lib.reverb(c, SR, mix=0.35, dur=3.0, decay=1.6, predelay=0.03,
                       damp=2200, seed=seed)[:n]
        s = lib.deharsh(s, SR, knee=3200)
        s = voice_for_small_speakers(s, cap=0.42)
        emit(name, [lib.seamless(s, SR, 2.5)], cat, loop=True, bus="music",
             mono=False, src="VCSL pipe organ + tubular bells + OGA wind")

    # A(#5)/dim colouring — the notes VCSL actually sampled (A, C, D#, F#) are a
    # diminished set, which is exactly the right amount of wrong for this.
    bed("menu", [("A1", "pedal", 0.45, 1.0), ("A2", "manual", 0.34, 1.0),
                 ("C3", "manual", 0.22, 1.0), ("D#2", "manual", 0.18, 1.0)],
        20.0, bell_every=5.0, wind=0.5, seed=21)
    bed("round_bed_loop", [("D#1", "pedal", 0.4, 1.0), ("D#2", "manual", 0.24, 1.0),
                           ("A2", "manual", 0.16, 1.0)], 16.0,
        wind=0.3, seed=22, cat="ambient")
    bed("round_bed_layer_pulse", [("A1", "pedal", 0.4, 1.0),
                                  ("A2", "manual", 0.26, 1.0)], 12.0,
        seed=23, cat="ambient")
    bed("round_bed_layer_choir", [("C3", "manual", 0.34, 1.0),
                                  ("F#2", "manual", 0.22, 1.0)], 14.0,
        seed=24, cat="ambient")

    # the death track: the same funeral material, looping
    n = int(SR * 18.0)
    c = np.zeros(n, np.float32)
    for note, rank, g in (("A1", "pedal", 0.45), ("A2", "manual", 0.34),
                          ("C3", "manual", 0.2)):
        x = organ(note, 18.5, gain=g, rank=rank)
        if x is not None:
            place(c, lib.lowpass(x[:n], SR, 2400, order=1), 0.0)
    b = sample("chimes_C3_pp_rr2.wav", 1.0, 0.26)
    if b is not None:
        for t in (1.0, 7.0, 13.0):
            place(c, lib.lowpass(b, SR, 2800, order=1), t)
    s = lib.reverb(c, SR, mix=0.42, dur=3.6, decay=1.3, predelay=0.04, damp=2100, seed=31)[:n]
    s = lib.deharsh(s, SR, knee=3000)
    s = voice_for_small_speakers(s, cap=0.42)
    emit("music_game_over", [lib.seamless(s, SR, 3.0)], "music", loop=True, bus="music",
         mono=False, src="VCSL pipe organ + tubular bells")

    # perk jingles — a period advertising jingle per machine, played through a
    # cheap vending-machine speaker (band-limited, saturated, small room)
    jingles = {
        "perk_jingle_juggernog": ("jingle/juggernog.mp3", 0.97),
        "perk_jingle_speedcola": ("jingle/speedcola.mp3", 1.04),
        "perk_jingle_quickrevive": ("jingle/quickrevive.mp3", 1.0),
        "perk_jingle_doubletap": ("jingle/doubletap.mp3", 0.98),
    }
    for name, (rel, pitch) in jingles.items():
        src = os.path.join(RAW, rel)
        if not os.path.exists(src):
            print("  ! no jingle", rel)
            continue
        x = dec(src, mono=True)
        x = vary(x, pitch)
        x = lib.highpass(x, SR, 300, order=2)
        x = lib.lowpass(x, SR, 4200, order=2)
        x = np.tanh(x * 1.8).astype(np.float32) * 0.7
        x = lib.to_mono(lib.reverb(x, SR, mix=0.16, dur=0.9, decay=4.0,
                                   predelay=0.01, damp=3000, seed=41))
        emit(name, [cut(lib.trim(x, SR, -46), 4.2, 0.3)], "powerup", bus="music",
             src="ElevenLabs jingle (processed through a cheap speaker)")


# ================================================================== main ===

GROUPS = {
    "guns": build_guns,
    "handling": build_handling,
    "impacts": build_impacts,
    "foley": build_foley,
    "voices": build_voices,
    "world": build_world,
    "stingers": build_stingers,
    "music": build_music,
}

# Which engine bus and playback hints each category gets by default.
CAT_BUS = {"ui": "ui", "stinger": "music", "music": "music", "ambient": "ambient"}


def write_out():
    """Assemble the manifest. Entries for names not built this run are kept, so
    a single group can be rebuilt without wiping the rest of the library."""
    mpath = os.path.join(OUT, "manifest.json")
    manifest = {}
    if os.path.exists(mpath):
        try:
            old = json.load(open(mpath, encoding="utf-8"))
            for name, e in old.get("sounds", {}).items():
                if all(os.path.exists(os.path.join(OUT, f)) for f in e.get("files", [])):
                    manifest[name] = e
        except Exception as e:
            print("  ! could not read the existing manifest:", e)
    manifest.update(BUILT)
    manifest = {k: manifest[k] for k in sorted(manifest)}

    total = sum(os.path.getsize(os.path.join(OUT, f))
                for e in manifest.values() for f in e["files"])
    # music tracks are reached through audio.music(); `game_over` is both a
    # one-shot sting and a bed, so the bed keeps a separate key.
    out = {"version": 1, "sampleRate": SR, "sounds": manifest,
           "tracks": {"menu": "menu", "game_over": "music_game_over"}}
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(f"\n{len(manifest)} sounds, "
          f"{sum(len(v['files']) for v in manifest.values())} files, "
          f"{total / 1e6:.2f} MB  ({len(BUILT)} rebuilt this run)")


def main():
    os.makedirs(OUT, exist_ok=True)
    args = sys.argv[1:] or ["all"]
    groups = list(GROUPS) if "all" in args else args
    for g in groups:
        if g not in GROUPS:
            print("unknown group", g)
            continue
        print("==", g)
        GROUPS[g]()
    write_out()


if __name__ == "__main__":
    main()
