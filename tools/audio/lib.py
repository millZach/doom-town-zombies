"""lib.py — small ffmpeg/numpy DSP toolkit for the Doom Town audio build.

Everything goes through ffmpeg for decode/encode and numpy for the maths, so
there are no binary python dependencies beyond numpy/scipy.
"""
import json
import os
import re
import subprocess
import tempfile

import numpy as np

SR = 44100
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, **kw)


def decode(path, sr=SR, mono=False):
    """-> (float32 array shape (n, ch), sr)"""
    ch = 1 if mono else 2
    p = subprocess.run(
        [FFMPEG, "-v", "error", "-i", str(path), "-f", "f32le",
         "-ac", str(ch), "-ar", str(sr), "-"],
        check=True, capture_output=True)
    a = np.frombuffer(p.stdout, dtype="<f4").astype(np.float32)
    return a.reshape(-1, ch), sr


def encode(a, path, sr=SR, codec="libvorbis", q=4):
    """Write a float array (n, ch) to an .ogg/.mp3."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    a = np.asarray(a, dtype=np.float32)
    if a.ndim == 1:
        a = a[:, None]
    ch = a.shape[1]
    args = [FFMPEG, "-v", "error", "-y", "-f", "f32le", "-ar", str(sr),
            "-ac", str(ch), "-i", "-"]
    if str(path).endswith(".mp3"):
        args += ["-c:a", "libmp3lame", "-b:a", "128k"]
    else:
        args += ["-c:a", codec, "-q:a", str(q)]
    args += [str(path)]
    subprocess.run(args, input=a.tobytes(), check=True, capture_output=True)
    return path


def duration(path):
    p = run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(path)])
    return float(json.loads(p.stdout)["format"]["duration"])


# ------------------------------------------------------------------ shaping

def to_mono(a):
    return a.mean(axis=1) if a.ndim == 2 and a.shape[1] > 1 else a.reshape(-1)


def stereo(a):
    if a.ndim == 1:
        return np.stack([a, a], axis=1)
    if a.shape[1] == 1:
        return np.repeat(a, 2, axis=1)
    return a


def env(a, sr=SR, win=0.005):
    """Smoothed absolute envelope of a mono signal."""
    m = np.abs(to_mono(a))
    n = max(1, int(sr * win))
    k = np.ones(n, dtype=np.float32) / n
    return np.convolve(m, k, mode="same")


def trim(a, sr=SR, thresh_db=-50.0, head=0.004, tail=0.10):
    """Trim leading/trailing silence, keeping a little padding."""
    e = env(a, sr, 0.003)
    peak = e.max() if e.size else 0.0
    if peak <= 0:
        return a
    t = peak * (10 ** (thresh_db / 20.0))
    idx = np.nonzero(e > t)[0]
    if idx.size == 0:
        return a
    s = max(0, idx[0] - int(sr * head))
    e2 = min(len(a), idx[-1] + int(sr * tail))
    return a[s:e2]


def fade(a, sr=SR, fin=0.002, fout=0.02):
    a = a.copy()
    n = len(a)
    ni = min(int(sr * fin), n // 2)
    no = min(int(sr * fout), n // 2)
    if ni > 1:
        r = np.linspace(0, 1, ni, dtype=np.float32)
        a[:ni] *= r[:, None] if a.ndim == 2 else r
    if no > 1:
        r = np.linspace(1, 0, no, dtype=np.float32)
        a[-no:] *= r[:, None] if a.ndim == 2 else r
    return a


def peak_norm(a, peak=0.89):
    p = np.abs(a).max()
    return a if p <= 0 else a * (peak / p)


def limit(a, ceiling=0.89, knee=0.6):
    """Soft-knee peak limiter so loudness normalising cannot clip.

    The curve must be continuous *and* smooth at the knee. An earlier version
    switched between a linear and a tanh branch at a fixed input level, and the
    two did not meet: every sample that crossed the threshold jumped by ~10 %,
    which is a step edge, which is broadband splatter — audible as a tick, and
    it pushed the inter-sample peaks several dB higher than the sample peak.
    Here the tanh starts *at* the knee with unit slope, so the two branches
    agree in both value and gradient.
    """
    p = np.abs(a).max()
    if p <= ceiling:
        return a
    x = a / ceiling
    ax = np.abs(x)
    y = ax.copy()
    over = ax > knee
    if over.any():
        t = (ax[over] - knee) / (1.0 - knee)
        y[over] = knee + (1.0 - knee) * np.tanh(t)
    return (np.sign(x) * np.minimum(y, 1.0) * ceiling).astype(np.float32)


def seamless(a, sr=SR, xfade=0.5):
    """Make a loop seamless by folding the tail back over the head."""
    n = int(sr * xfade)
    if len(a) <= 2 * n or n < 8:
        return a
    head, body, tail = a[:n], a[n:-n], a[-n:]
    r = np.linspace(0, 1, n, dtype=np.float32)
    if a.ndim == 2:
        r = r[:, None]
    mixed = head * r + tail * (1 - r)
    return np.concatenate([mixed, body], axis=0)


def resample_pitch(a, ratio):
    """Cheap pitch/speed shift by linear resampling. ratio>1 = higher & shorter."""
    n = int(len(a) / ratio)
    if n < 8:
        return a
    x = np.linspace(0, len(a) - 1, n)
    if a.ndim == 2:
        return np.stack([np.interp(x, np.arange(len(a)), a[:, c]) for c in range(a.shape[1])],
                        axis=1).astype(np.float32)
    return np.interp(x, np.arange(len(a)), a).astype(np.float32)


# ------------------------------------------------------------------ filters

def biquad(a, sr, kind, f0, q=0.707, gain_db=0.0):
    """Direct-form-1 biquad (RBJ cookbook), applied per channel."""
    from scipy.signal import lfilter
    w0 = 2 * np.pi * f0 / sr
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2 * q)
    A = 10 ** (gain_db / 40)
    if kind == "lowpass":
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
        aa = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "highpass":
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
        aa = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "bandpass":
        b = [alpha, 0, -alpha]
        aa = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "peaking":
        b = [1 + alpha * A, -2 * cw, 1 - alpha * A]
        aa = [1 + alpha / A, -2 * cw, 1 - alpha / A]
    elif kind == "lowshelf":
        s = 2 * np.sqrt(A) * alpha
        b = [A * ((A + 1) - (A - 1) * cw + s), 2 * A * ((A - 1) - (A + 1) * cw),
             A * ((A + 1) - (A - 1) * cw - s)]
        aa = [(A + 1) + (A - 1) * cw + s, -2 * ((A - 1) + (A + 1) * cw),
              (A + 1) + (A - 1) * cw - s]
    elif kind == "highshelf":
        s = 2 * np.sqrt(A) * alpha
        b = [A * ((A + 1) + (A - 1) * cw + s), -2 * A * ((A - 1) + (A + 1) * cw),
             A * ((A + 1) + (A - 1) * cw - s)]
        aa = [(A + 1) - (A - 1) * cw + s, 2 * ((A - 1) - (A + 1) * cw),
              (A + 1) - (A - 1) * cw - s]
    else:
        raise ValueError(kind)
    b = np.array(b) / aa[0]
    aa = np.array(aa) / aa[0]
    if a.ndim == 2:
        return np.stack([lfilter(b, aa, a[:, c]) for c in range(a.shape[1])],
                        axis=1).astype(np.float32)
    return lfilter(b, aa, a).astype(np.float32)


def lowpass(a, sr, f0, order=2, q=0.707):
    for _ in range(order):
        a = biquad(a, sr, "lowpass", f0, q)
    return a


def highpass(a, sr, f0, order=2, q=0.707):
    for _ in range(order):
        a = biquad(a, sr, "highpass", f0, q)
    return a


def deharsh(a, sr, knee=4000.0, slope=1):
    """Tame everything above `knee` — the fix for a 'screechy' sound."""
    a = biquad(a, sr, "highshelf", knee, 0.7, -9.0 * slope)
    return lowpass(a, sr, min(sr * 0.45, knee * 2.6), order=1)


# ------------------------------------------------------------------ reverb

def ir(sr=SR, dur=2.5, decay=2.4, predelay=0.02, damp=6000.0, seed=7):
    rng = np.random.default_rng(seed)
    n = int(sr * dur)
    t = np.arange(n) / sr
    noise = rng.standard_normal((n, 2)).astype(np.float32)
    envd = np.exp(-t * decay)[:, None]
    h = noise * envd
    h = lowpass(h, sr, damp, order=2)
    pd = int(sr * predelay)
    h = np.concatenate([np.zeros((pd, 2), np.float32), h], axis=0)
    return (h / (np.abs(h).max() + 1e-9)).astype(np.float32)


def convolve(a, h):
    from scipy.signal import fftconvolve
    a = stereo(a)
    h = stereo(h)
    out = np.stack([fftconvolve(a[:, c], h[:, c])[: len(a) + len(h) - 1]
                    for c in range(2)], axis=1)
    return (out / (np.abs(out).max() + 1e-9)).astype(np.float32)


def reverb(a, sr=SR, mix=0.35, **kw):
    h = ir(sr, **kw)
    wet = convolve(a, h)
    dry = np.concatenate([stereo(a), np.zeros((len(wet) - len(a), 2), np.float32)], axis=0)
    return (dry * (1 - mix) + wet * mix).astype(np.float32)


# ------------------------------------------------------------------ analysis

def measure(path):
    """duration / true peak dBTP / integrated LUFS / fraction of energy > 5 kHz."""
    a, sr = decode(path, SR, mono=False)
    if len(a) == 0:
        return None
    m = to_mono(a)
    peak = float(np.abs(a).max())
    peak_db = 20 * np.log10(peak) if peak > 0 else -120.0

    # integrated loudness via ffmpeg's ebur128
    p = subprocess.run(
        [FFMPEG, "-v", "info", "-i", str(path), "-af",
         "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True)
    txt = p.stderr.decode("utf-8", "replace")
    lufs_ff = tp = None
    mm = re.search(r"\{[^{}]*input_i[^{}]*\}", txt, re.S)
    if mm:
        try:
            j = json.loads(mm.group(0))
            lufs_ff = float(j["input_i"])
            tp = float(j["input_tp"])
        except Exception:
            pass

    # spectral harshness: fraction of energy above 5 kHz
    n = 1 << 14
    hop = n // 2
    if len(m) < n:
        m = np.pad(m, (0, n - len(m)))
    win = np.hanning(n).astype(np.float32)
    hi = lo = 0.0
    freqs = np.fft.rfftfreq(n, 1 / SR)
    band = freqs >= 5000
    for s in range(0, len(m) - n + 1, hop):
        sp = np.abs(np.fft.rfft(m[s:s + n] * win)) ** 2
        hi += float(sp[band].sum())
        lo += float(sp.sum())
    harsh = hi / lo if lo > 0 else 0.0

    # centroid
    cent = 0.0
    sp = np.abs(np.fft.rfft(m[: min(len(m), 1 << 16)] * np.hanning(min(len(m), 1 << 16))))
    if sp.sum() > 0:
        f = np.fft.rfftfreq(min(len(m), 1 << 16), 1 / SR)
        cent = float((f * sp).sum() / sp.sum())

    return {
        "duration": len(a) / SR,
        "peak_db": peak_db,
        # ffmpeg reports -inf / no value for clips shorter than its 3 s window,
        # so fall back to the in-house gated meter, which has no such floor.
        "true_peak_db": tp if tp is not None else true_peak(a, SR),
        "lufs": lufs_ff if (lufs_ff is not None and lufs_ff > -70) else lufs(a, SR),
        "ffmpeg_lufs": lufs_ff,
        "harsh_5k": harsh,
        "centroid": cent,
        "bytes": os.path.getsize(path),
    }


def loudnorm(path_in, path_out, lufs=-18.0, tp=-1.5, lra=11.0):
    """Two-pass ffmpeg loudnorm into the output container."""
    p = subprocess.run(
        [FFMPEG, "-v", "info", "-i", str(path_in), "-af",
         f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:print_format=json", "-f", "null", "-"],
        capture_output=True)
    txt = p.stderr.decode("utf-8", "replace")
    mm = re.search(r"\{[^{}]*input_i[^{}]*\}", txt, re.S)
    meas = json.loads(mm.group(0)) if mm else None
    af = f"loudnorm=I={lufs}:TP={tp}:LRA={lra}"
    if meas:
        af += (f":measured_I={meas['input_i']}:measured_TP={meas['input_tp']}"
               f":measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}"
               f":offset={meas.get('target_offset', 0)}:linear=true")
    args = [FFMPEG, "-v", "error", "-y", "-i", str(path_in), "-af", af, "-ar", str(SR)]
    if str(path_out).endswith(".mp3"):
        args += ["-c:a", "libmp3lame", "-b:a", "128k"]
    else:
        args += ["-c:a", "libvorbis", "-q:a", "4"]
    args += [str(path_out)]
    subprocess.run(args, check=True, capture_output=True)
    return path_out


def spectrogram(path_in, path_out, size="900x420"):
    os.makedirs(os.path.dirname(path_out), exist_ok=True)
    subprocess.run(
        [FFMPEG, "-v", "error", "-y", "-i", str(path_in), "-lavfi",
         f"showspectrumpic=s={size}:mode=combined:legend=1:scale=log:stop=16000",
         str(path_out)], check=True, capture_output=True)
    return path_out


# ------------------------------------------------------------------ slicing

def onsets(a, sr=SR, thresh=0.18, gap=0.18, min_level=0.05):
    """Indices where a transient starts. Tuned for gunshots/impacts."""
    e = env(a, sr, 0.002)
    peak = e.max()
    if peak <= 0:
        return []
    t = peak * thresh
    above = e > t
    idx = []
    last = -1e9
    for i in np.nonzero(above)[0]:
        if i - last > sr * gap:
            # back off to where the energy actually starts rising
            j = i
            floor = peak * min_level * 0.2
            while j > 0 and e[j] > floor and i - j < sr * 0.03:
                j -= 1
            idx.append(j)
            last = i
    return idx


def slice_events(a, sr=SR, length=0.9, **kw):
    """Cut a multi-hit recording into individual events."""
    out = []
    ons = onsets(a, sr, **kw)
    for k, s in enumerate(ons):
        e = int(min(len(a), s + sr * length))
        if k + 1 < len(ons):
            e = int(min(e, ons[k + 1] - sr * 0.01))
        seg = a[s:e]
        if len(seg) > sr * 0.05:
            out.append(seg)
    return out


# ------------------------------------------------------ BS.1770 loudness

def _k_weight(x, sr):
    """ITU-R BS.1770 pre-filter: a +4 dB high shelf then a 38 Hz RLB highpass."""
    x = biquad(x, sr, "highshelf", 1681.97, 0.7071, 3.999)
    return biquad(x, sr, "highpass", 38.135, 0.5003)


def lufs(a, sr=SR):
    """Gated integrated loudness (LUFS). Works on any length; short clips fall
    back to the ungated mean, which is what the ear judges for a one-shot."""
    a = np.asarray(a, dtype=np.float32)
    ch = a.reshape(-1, 1) if a.ndim == 1 else a
    z = np.stack([_k_weight(ch[:, c], sr) for c in range(ch.shape[1])], axis=1)
    n = int(sr * 0.4)
    hop = max(1, n // 4)
    if len(z) < n:                      # too short for a 400 ms block
        ms = float(np.mean(z.astype(np.float64) ** 2, axis=0).sum())
        return -0.691 + 10 * np.log10(ms) if ms > 0 else -120.0
    blocks = []
    for s in range(0, len(z) - n + 1, hop):
        ms = np.mean(z[s:s + n].astype(np.float64) ** 2, axis=0).sum()
        blocks.append(ms)
    blocks = np.array(blocks)
    lk = -0.691 + 10 * np.log10(np.maximum(blocks, 1e-20))
    keep = lk > -70.0
    if not keep.any():
        return -120.0
    rel = -0.691 + 10 * np.log10(blocks[keep].mean()) - 10.0
    keep2 = keep & (lk > rel)
    use = blocks[keep2] if keep2.any() else blocks[keep]
    return float(-0.691 + 10 * np.log10(use.mean()))


def true_peak(a, sr=SR, oversample=4):
    """Inter-sample peak, in dBTP. 4x linear upsampling is enough to catch the
    overshoot that makes a file clip on playback despite a legal sample peak."""
    a = np.asarray(a, dtype=np.float32)
    ch = a.reshape(-1, 1) if a.ndim == 1 else a
    pk = 0.0
    for c in range(ch.shape[1]):
        x = ch[:, c].astype(np.float64)
        # Exact band-limited interpolation by zero-padding the spectrum.
        # Linear interpolation can never exceed the sample peak, so it would
        # measure nothing at all; a polyphase resampler under-reads because of
        # its transition band. This is what actually finds the overshoot.
        n = len(x)
        if n < 8:
            pk = max(pk, float(np.abs(x).max()))
            continue
        sp = np.fft.rfft(x)
        up = np.fft.irfft(np.concatenate([sp, np.zeros((n * (oversample - 1)) // 2 + 1,
                                                       dtype=complex)]),
                          n=n * oversample) * oversample
        pk = max(pk, float(np.abs(up).max()))
    return 20 * np.log10(pk) if pk > 0 else -120.0


def harshness(a, sr=SR, split=5000.0):
    """Fraction of spectral energy above `split` — the screech detector."""
    m = to_mono(np.asarray(a, dtype=np.float32))
    n = 1 << 13
    if len(m) < n:
        m = np.pad(m, (0, n - len(m)))
    win = np.hanning(n).astype(np.float32)
    freqs = np.fft.rfftfreq(n, 1 / sr)
    band = freqs >= split
    hi = lo = 0.0
    for s in range(0, len(m) - n + 1, n // 2):
        sp = np.abs(np.fft.rfft(m[s:s + n] * win)) ** 2
        hi += float(sp[band].sum())
        lo += float(sp.sum())
    return hi / lo if lo > 0 else 0.0


def slice_phrases(a, sr=SR, floor_db=-34.0, min_gap=0.22, min_len=0.25,
                  pad_head=0.02, pad_tail=0.14, max_len=4.0):
    """Split a recording into phrases separated by silence.

    Onset slicing is right for gunshots and wrong for voices: a groan swells
    and dips several times, and every dip reads as a new onset, so a two-second
    moan comes out as four half-second fragments. This instead finds the
    *silences* and keeps what lies between them, which is what a phrase is.
    """
    e = env(a, sr, 0.02)
    peak = float(e.max()) if e.size else 0.0
    if peak <= 0:
        return []
    thr = peak * (10 ** (floor_db / 20.0))
    loud = e > thr
    out = []
    i = 0
    n = len(loud)
    gap_n = int(sr * min_gap)
    while i < n:
        if not loud[i]:
            i += 1
            continue
        s = i
        last = i
        while i < n:
            if loud[i]:
                last = i
            elif i - last > gap_n:
                break
            i += 1
        s2 = max(0, s - int(sr * pad_head))
        e2 = min(len(a), last + int(sr * pad_tail))
        if (e2 - s2) >= sr * min_len:
            out.append(a[s2:min(e2, s2 + int(sr * max_len))])
    return out


def split_valleys(seg, sr=SR, target=2.0, min_len=0.6):
    """Cut an over-long phrase at the quietest point, recursively.

    Generated vocal takes often run continuously — the "silence" between two
    groans is really just a breath, well above any silence threshold — so a
    gap-based split returns one long blob. Cutting at the deepest dip in the
    envelope lands between the two groans, which is where a human would cut.
    """
    if len(seg) <= sr * target * 1.6:
        return [seg]
    e = env(seg, sr, 0.04)
    lo = int(len(seg) * 0.28)
    hi = int(len(seg) * 0.72)
    if hi - lo < sr * min_len:
        return [seg]
    k = lo + int(np.argmin(e[lo:hi]))
    a, b = seg[:k], seg[k:]
    if len(a) < sr * min_len or len(b) < sr * min_len:
        return [seg]
    return split_valleys(a, sr, target, min_len) + split_valleys(b, sr, target, min_len)


def phrases(a, sr=SR, target=2.0, floor_db=-22.0, min_gap=0.28, min_len=0.5,
            max_len=8.0):
    """Phrase slicing plus valley splitting — the segmentation for voices."""
    out = []
    for seg in slice_phrases(a, sr, floor_db=floor_db, min_gap=min_gap,
                             min_len=min_len, max_len=max_len):
        out += split_valleys(seg, sr, target, min_len)
    return [s for s in out if len(s) >= sr * min_len]
