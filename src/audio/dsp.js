/**
 * dsp.js — low-level procedural synthesis primitives for the Doom Town audio engine.
 *
 * Everything here is pure Web Audio / plain JS. No samples, no external assets.
 * These helpers are used from inside OfflineAudioContext render passes (see audio.js),
 * so they are written to be cheap to build and deterministic given a seeded RNG.
 */

/* ------------------------------------------------------------------ *
 * Random
 * ------------------------------------------------------------------ */

/** Small fast seeded PRNG (mulberry32). Deterministic renders => reproducible sounds. */
export function mulberry32(seed) {
  let a = seed >>> 0;
  return function rng() {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const rnd = (rng, a = 0, b = 1) => a + (b - a) * rng();
export const rint = (rng, a, b) => Math.floor(a + (b - a + 1) * rng()) | 0;
export const pick = (rng, arr) => arr[Math.min(arr.length - 1, (rng() * arr.length) | 0)];
/** bipolar jitter in [-x, x] */
export const jit = (rng, x) => (rng() * 2 - 1) * x;
export const clamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);
export const dbToGain = (db) => Math.pow(10, db / 20);
export const mtof = (m) => 440 * Math.pow(2, (m - 69) / 12);
export const lerp = (a, b, t) => a + (b - a) * t;

/** Note name -> midi. "A3", "C#4", "Eb2". */
const NOTE_BASE = { c: 0, d: 2, e: 4, f: 5, g: 7, a: 9, b: 11 };
export function nm(name) {
  const m = /^([a-gA-G])([#b]?)(-?\d+)$/.exec(String(name).trim());
  if (!m) return 69;
  let v = NOTE_BASE[m[1].toLowerCase()];
  if (m[2] === '#') v += 1;
  else if (m[2] === 'b') v -= 1;
  return v + (parseInt(m[3], 10) + 1) * 12;
}
/** Note name -> frequency. */
export const nf = (name) => mtof(nm(name));

/**
 * Snap a frequency to the nearest exact multiple of 1/loopDur so that a
 * sustained tone phase-aligns across a loop seam (no cancellation in the
 * crossfade). The pitch shift is far below the just-noticeable difference.
 */
export const lockFreq = (f, loopDur) => Math.max(1, Math.round(f * loopDur)) / loopDur;

/* ------------------------------------------------------------------ *
 * Noise
 * ------------------------------------------------------------------ */

/** Fill a Float32Array with coloured noise. color: 'white' | 'pink' | 'brown' | 'blue' */
export function fillNoise(data, rng, color = 'white') {
  const n = data.length;
  if (color === 'pink') {
    let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
    for (let i = 0; i < n; i++) {
      const w = rng() * 2 - 1;
      b0 = 0.99886 * b0 + w * 0.0555179;
      b1 = 0.99332 * b1 + w * 0.0750759;
      b2 = 0.969 * b2 + w * 0.153852;
      b3 = 0.8665 * b3 + w * 0.3104856;
      b4 = 0.55 * b4 + w * 0.5329522;
      b5 = -0.7616 * b5 - w * 0.016898;
      data[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362) * 0.16;
      b6 = w * 0.115926;
    }
  } else if (color === 'brown') {
    let last = 0;
    for (let i = 0; i < n; i++) {
      const w = rng() * 2 - 1;
      last = (last + 0.02 * w) / 1.02;
      data[i] = last * 3.6;
    }
  } else if (color === 'blue') {
    let prev = 0;
    for (let i = 0; i < n; i++) {
      const w = rng() * 2 - 1;
      data[i] = (w - prev) * 0.55;
      prev = w;
    }
  } else {
    for (let i = 0; i < n; i++) data[i] = rng() * 2 - 1;
  }
  return data;
}

export function makeNoiseBuffer(ctx, channels, dur, color, rng) {
  const n = Math.max(1, Math.ceil(dur * ctx.sampleRate));
  const buf = ctx.createBuffer(channels, n, ctx.sampleRate);
  for (let c = 0; c < channels; c++) fillNoise(buf.getChannelData(c), rng, color);
  return buf;
}

/* ------------------------------------------------------------------ *
 * Impulse responses (for convolution reverb / gun tails)
 * ------------------------------------------------------------------ */

/**
 * Build a synthetic impulse response.
 * opts: { dur, decay (power curve), tau (exp seconds), predelay, damp (0..1),
 *         early: [[timeSec, gain], ...], width (0..1), seed }
 */
export function makeIR(ctx, opts = {}) {
  const sr = ctx.sampleRate;
  const dur = opts.dur ?? 1.5;
  const n = Math.max(2, Math.ceil(dur * sr));
  const buf = ctx.createBuffer(2, n, sr);
  const rng = opts.rng || mulberry32(opts.seed ?? 12345);
  const tau = opts.tau ?? dur / 4;
  const power = opts.decay ?? 2.0;
  const pre = Math.floor((opts.predelay ?? 0.005) * sr);
  const damp = clamp(opts.damp ?? 0.5, 0, 0.98);
  const width = clamp(opts.width ?? 0.85, 0, 1);

  for (let c = 0; c < 2; c++) {
    const d = buf.getChannelData(c);
    // diffuse exponentially-decaying noise tail, one-pole lowpass with time-varying damping
    let lp = 0;
    const chOff = c === 0 ? 0 : Math.floor(width * 0.0017 * sr);
    for (let i = 0; i < n; i++) {
      const idx = i - pre - chOff;
      if (idx < 0) { d[i] = 0; continue; }
      const t = idx / sr;
      const frac = idx / n;
      const env = Math.pow(Math.max(0, 1 - frac), power) * Math.exp(-t / tau);
      const w = (rng() * 2 - 1) * env;
      // damping grows with time: high frequencies die first
      const a = clamp(0.12 + damp * 0.82 * frac, 0.02, 0.96);
      lp = lp + (1 - a) * (w - lp);
      d[i] = lp * 1.6;
    }
    // early reflections
    const early = opts.early || [[0.0, 0.9], [0.011, 0.5], [0.019, 0.38], [0.031, 0.3], [0.047, 0.22]];
    for (let e = 0; e < early.length; e++) {
      const tOff = early[e][0] * (1 + (c ? 0.07 : -0.05)) + (opts.predelay ?? 0.005);
      const g = early[e][1] * (1 + (c ? -0.1 : 0.1) * width);
      const at = Math.floor(tOff * sr);
      // short noise splat instead of a click, so it doesn't sound digital
      const len = Math.max(2, Math.floor(0.0018 * sr));
      for (let k = 0; k < len && at + k < n; k++) {
        d[at + k] += (rng() * 2 - 1) * g * (1 - k / len);
      }
    }
  }
  return buf;
}

/* ------------------------------------------------------------------ *
 * Node helpers
 * ------------------------------------------------------------------ */

export function gainNode(ctx, v = 1) {
  const g = ctx.createGain();
  g.gain.value = v;
  return g;
}

export function filt(ctx, type, freq, q = 1, gainDb = 0) {
  const f = ctx.createBiquadFilter();
  f.type = type;
  f.frequency.value = Math.max(10, freq);
  f.Q.value = q;
  f.gain.value = gainDb;
  return f;
}

export function osc(ctx, type = 'sine', freq = 440) {
  const o = ctx.createOscillator();
  o.type = type;
  o.frequency.value = freq;
  return o;
}

export function delayNode(ctx, time, max) {
  const d = ctx.createDelay(Math.max(time * 2, max || 1));
  d.delayTime.value = time;
  return d;
}

export function panner(ctx, x) {
  const p = ctx.createStereoPanner();
  p.pan.value = clamp(x, -1, 1);
  return p;
}

/** Chain a list of nodes together, returns the last. */
export function chain(...nodes) {
  for (let i = 0; i < nodes.length - 1; i++) nodes[i].connect(nodes[i + 1]);
  return nodes[nodes.length - 1];
}

/** Safe exponential ramp (exponentialRamp can't hit 0). */
export function expTo(param, v, t) {
  param.exponentialRampToValueAtTime(Math.max(1e-5, v), Math.max(0, t));
  return param;
}
export function setAt(param, v, t) {
  param.setValueAtTime(v, Math.max(0, t));
  return param;
}
export function linTo(param, v, t) {
  param.linearRampToValueAtTime(v, Math.max(0, t));
  return param;
}

/**
 * Percussive amplitude envelope on a gain param.
 * o: { t, peak, attack, hold, decay, curve:'exp'|'lin', end }
 */
export function ampEnv(param, o = {}) {
  const t = o.t ?? 0;
  const peak = o.peak ?? 1;
  const a = Math.max(0.0003, o.attack ?? 0.002);
  const hold = o.hold ?? 0;
  const dec = Math.max(0.005, o.decay ?? 0.15);
  param.cancelScheduledValues(t);
  if ((o.curve ?? 'exp') === 'exp') {
    setAt(param, 1e-4, t);
    expTo(param, peak, t + a);
    if (hold > 0) setAt(param, peak, t + a + hold);
    expTo(param, peak * (o.floor ?? 0.0004), t + a + hold + dec);
    setAt(param, 0, t + a + hold + dec + 0.003);
  } else {
    setAt(param, 0, t);
    linTo(param, peak, t + a);
    if (hold > 0) setAt(param, peak, t + a + hold);
    linTo(param, 0, t + a + hold + dec);
  }
  return param;
}

/* ------------------------------------------------------------------ *
 * Waveshaper curves
 * ------------------------------------------------------------------ */

const curveCache = new Map();
function cached(key, make) {
  let c = curveCache.get(key);
  if (!c) { c = make(); curveCache.set(key, c); }
  return c;
}

/** tanh-ish saturation. k in ~[1..60]. */
export function satCurve(k = 6, n = 2048) {
  return cached('sat' + k + '_' + n, () => {
    const c = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const x = (i / (n - 1)) * 2 - 1;
      c[i] = Math.tanh(x * k) / Math.tanh(k);
    }
    return c;
  });
}

/** Hard-ish asymmetric fuzz — good for growls and blown speakers. */
export function fuzzCurve(k = 8, bias = 0.12, n = 2048) {
  return cached('fuzz' + k + '_' + bias, () => {
    const c = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const x = (i / (n - 1)) * 2 - 1 + bias;
      const y = Math.tanh(x * k);
      c[i] = clamp(y - Math.tanh(bias * k), -1, 1);
    }
    return c;
  });
}

/** Wavefolder — metallic / sci-fi harmonics. */
export function foldCurve(amt = 2.2, n = 2048) {
  return cached('fold' + amt, () => {
    const c = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const x = ((i / (n - 1)) * 2 - 1) * amt;
      c[i] = Math.sin(x * Math.PI * 0.5);
    }
    return c;
  });
}

/** Chebyshev harmonic exciter of order k. */
export function chebyCurve(k = 3, n = 2048) {
  return cached('cheb' + k, () => {
    const c = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const x = clamp((i / (n - 1)) * 2 - 1, -1, 1);
      c[i] = Math.cos(k * Math.acos(x));
    }
    return c;
  });
}

export function shaper(ctx, curve, oversample = '4x') {
  const w = ctx.createWaveShaper();
  w.curve = curve;
  w.oversample = oversample;
  return w;
}

/* ------------------------------------------------------------------ *
 * Reverb — cheap Schroeder/Freeverb-style network from native nodes.
 * Much faster to render than convolution for long music beds.
 * ------------------------------------------------------------------ */

const COMB_MS = [29.7, 31.1, 33.9, 35.3, 37.1, 39.7, 41.1, 43.7];
const ALLPASS_MS = [5.0, 6.83, 8.71, 10.4];

function reverbHalf(ctx, spread, decay, dampHz, combs) {
  const input = gainNode(ctx, 1);
  const sum = gainNode(ctx, 1 / Math.sqrt(combs));
  for (let i = 0; i < combs; i++) {
    const ms = COMB_MS[i % COMB_MS.length] * spread;
    const dt = ms / 1000;
    const cIn = gainNode(ctx, 1);
    const dly = delayNode(ctx, dt, 0.2);
    const lp = filt(ctx, 'lowpass', dampHz, 0.4);
    // feedback gain from RT60: g = 10^(-3*dt/decay)
    const g = clamp(Math.pow(10, (-3 * dt) / Math.max(0.2, decay)), 0, 0.985);
    const fb = gainNode(ctx, g);
    input.connect(cIn);
    cIn.connect(dly);
    dly.connect(lp);
    lp.connect(fb);
    fb.connect(cIn);
    dly.connect(sum);
  }
  // diffusion allpasses
  let node = sum;
  for (let i = 0; i < ALLPASS_MS.length; i++) {
    const dt = (ALLPASS_MS[i] * spread) / 1000;
    const g = 0.55;
    const apIn = gainNode(ctx, 1);
    const dly = delayNode(ctx, dt, 0.1);
    const fb = gainNode(ctx, g);
    const ff = gainNode(ctx, -g);
    const out = gainNode(ctx, 1);
    node.connect(apIn);
    node.connect(ff);
    apIn.connect(dly);
    dly.connect(fb);
    fb.connect(apIn);
    dly.connect(out);
    ff.connect(out);
    node = out;
  }
  return { input, output: node };
}

/**
 * Stereo reverb. Returns { input, output } — connect dry sends into input.
 * opts: { decay (RT60 sec), damp (Hz), preDelay (sec), width, combs, lowCut }
 */
export function makeReverb(ctx, opts = {}) {
  const decay = opts.decay ?? 2.4;
  const damp = opts.damp ?? 4200;
  const combs = opts.combs ?? 6;
  const input = gainNode(ctx, 1);
  const pre = delayNode(ctx, Math.max(0.001, opts.preDelay ?? 0.018), 0.5);
  const hp = filt(ctx, 'highpass', opts.lowCut ?? 90, 0.6);
  input.connect(pre);
  pre.connect(hp);

  const L = reverbHalf(ctx, 1.0, decay, damp, combs);
  const R = reverbHalf(ctx, 1.0 + 0.043 * (opts.width ?? 1), decay * 1.02, damp * 0.94, combs);
  hp.connect(L.input);
  hp.connect(R.input);

  const merger = ctx.createChannelMerger(2);
  L.output.connect(merger, 0, 0);
  R.output.connect(merger, 0, 1);
  const out = gainNode(ctx, opts.gain ?? 1);
  merger.connect(out);
  return { input, output: out };
}

/* ------------------------------------------------------------------ *
 * Formant synthesis (zombies, choir, announcer-ish voices)
 * ------------------------------------------------------------------ */

export const VOWELS = {
  a:  { f: [730, 1090, 2440, 3400, 4300], bw: [90, 110, 150, 200, 260], db: [0, -6, -14, -22, -30] },
  ae: { f: [660, 1720, 2410, 3300, 4200], bw: [90, 120, 160, 200, 260], db: [0, -8, -16, -24, -32] },
  e:  { f: [530, 1840, 2480, 3500, 4500], bw: [80, 110, 150, 200, 260], db: [0, -11, -16, -24, -32] },
  i:  { f: [270, 2290, 3010, 3600, 4600], bw: [70, 110, 140, 190, 250], db: [0, -17, -22, -28, -36] },
  o:  { f: [570, 840, 2410, 3200, 3900], bw: [80, 100, 150, 200, 260], db: [0, -7, -20, -28, -34] },
  u:  { f: [300, 870, 2240, 3200, 3900], bw: [70, 100, 150, 200, 260], db: [0, -15, -25, -32, -40] },
  er: { f: [490, 1350, 1690, 3200, 3900], bw: [90, 120, 150, 200, 260], db: [0, -9, -11, -22, -32] },
  uh: { f: [520, 1190, 2390, 3300, 4100], bw: [90, 120, 150, 200, 260], db: [0, -8, -16, -24, -32] },
};

/**
 * Parallel band-pass formant bank.
 * Returns { input, output, bands:[{bp, gain, f, bw}] } so callers can automate
 * formant frequencies over time (vowel morphs, screams that open up, …).
 */
export function formantBank(ctx, vowel = 'a', opts = {}) {
  const v = VOWELS[vowel] || VOWELS.a;
  const scale = opts.scale ?? 1;
  const count = Math.min(opts.count ?? 5, v.f.length);
  const input = gainNode(ctx, 1);
  const output = gainNode(ctx, opts.gain ?? 1);
  const bands = [];
  for (let i = 0; i < count; i++) {
    const f = v.f[i] * scale;
    const bw = v.bw[i] * (opts.bwScale ?? 1);
    const bp = filt(ctx, 'bandpass', f, Math.max(0.5, f / bw));
    const g = gainNode(ctx, dbToGain(v.db[i] + (opts.tilt ?? 0) * i));
    input.connect(bp);
    bp.connect(g);
    g.connect(output);
    bands.push({ bp, gain: g, f, bw });
  }
  return { input, output, bands };
}

/** Morph a formant bank to another vowel over time. */
export function morphVowel(bank, vowel, t, dur, scale = 1) {
  const v = VOWELS[vowel] || VOWELS.a;
  for (let i = 0; i < bank.bands.length; i++) {
    const b = bank.bands[i];
    if (i >= v.f.length) continue;
    const f = v.f[i] * scale;
    b.bp.frequency.setValueAtTime(b.bp.frequency.value, t);
    expTo(b.bp.frequency, f, t + dur);
    b.gain.gain.setValueAtTime(b.gain.gain.value, t);
    linTo(b.gain.gain, dbToGain(v.db[i]), t + dur);
  }
}

/**
 * Glottal source buffer: a Rosenberg-ish pulse train with per-period jitter,
 * shimmer and optional diplophonia (alternating periods) — the thing that makes
 * a voice sound damaged / inhuman. Output is the *derivative* flow (buzzy, bright).
 *
 * o: { dur, f0(t)->Hz, jitter, shimmer, rough (0..1 diplophonia),
 *      oq (open quotient), breath (0..1), rng }
 */
export function glottalBuffer(ctx, o = {}) {
  const sr = ctx.sampleRate;
  const dur = o.dur ?? 1;
  const n = Math.max(2, Math.ceil(dur * sr));
  const buf = ctx.createBuffer(1, n, sr);
  const d = buf.getChannelData(0);
  const rng = o.rng || mulberry32(7);
  const f0fn = typeof o.f0 === 'function' ? o.f0 : () => o.f0 ?? 100;
  const jitter = o.jitter ?? 0.03;
  const shimmer = o.shimmer ?? 0.18;
  const rough = o.rough ?? 0;
  const oqBase = o.oq ?? 0.62;
  const breath = o.breath ?? 0.08;

  let phase = 1;      // force a new period on the first sample
  let period = 1;
  let amp = 1;
  let oq = oqBase;
  let alt = 0;
  let prev = 0;

  for (let i = 0; i < n; i++) {
    const t = i / sr;
    if (phase >= 1) {
      phase -= 1;
      const f = Math.max(20, f0fn(t));
      let p = sr / f;
      p *= 1 + jit(rng, jitter);
      alt ^= 1;
      if (rough > 0 && alt) {
        // diplophonic: every other period gets longer + quieter => subharmonic growl
        p *= 1 + rough * 0.9;
        amp = 1 - rough * 0.55 + jit(rng, shimmer * 0.5);
      } else {
        amp = 1 + jit(rng, shimmer);
      }
      period = Math.max(4, p);
      oq = clamp(oqBase + jit(rng, 0.06), 0.25, 0.92);
    }
    let g = 0;
    const x = phase;
    const openEnd = oq * 0.72;
    if (x < openEnd) {
      g = 0.5 * (1 - Math.cos((Math.PI * x) / openEnd));
    } else if (x < oq) {
      g = Math.cos((Math.PI * (x - openEnd)) / (2 * (oq - openEnd)));
    }
    g *= amp;
    // derivative => lip radiation, gives the buzz its bite
    let out = (g - prev) * 6;
    prev = g;
    if (breath > 0) out += (rng() * 2 - 1) * breath * (0.35 + 0.65 * g);
    d[i] = clamp(out, -1, 1);
    phase += 1 / period;
  }
  return buf;
}

/* ------------------------------------------------------------------ *
 * Reusable layer builders (the vocabulary the sound recipes speak)
 * ------------------------------------------------------------------ */

/**
 * Filtered noise burst. The workhorse for gunfire bodies, impacts, whooshes.
 * o: { noise (AudioBuffer), t, dur, attack, decay, hold, peak, type, f0, f1,
 *      q, sweep (sec), hp, drive, driveMix, pan, offset, rate }
 *
 * Signal order matters: the saturator sits **after** the amplitude envelope, in
 * a parallel blend with the clean signal. Driving the noise before the envelope
 * (the obvious wiring) soft-clips at a constant input level for the whole
 * decay, so the tail ends up exactly as distorted as the transient and the
 * sound reads as a flat fizzy hiss. Real gunfire is filthy at the transient and
 * gets cleaner as it decays — which is what post-envelope drive gives you, for
 * free, because only the loud part of the envelope reaches the knee.
 *
 * `out` on the returned object is the node everything downstream should tap
 * (reverb sends included); `gain` is the pre-saturation envelope node.
 */
export function noiseBurst(ctx, out, o = {}) {
  const t = o.t ?? 0;
  const noise = o.noise;
  if (!noise) return null;
  const s = ctx.createBufferSource();
  s.buffer = noise;
  s.loop = true;
  if (o.rate) s.playbackRate.value = o.rate;
  const off = o.offset ?? (o.rng ? rnd(o.rng, 0, Math.max(0.01, noise.duration - 0.05)) : 0);

  let node = s;
  const f = filt(ctx, o.type || 'bandpass', o.f0 ?? 1200, o.q ?? 1.2);
  if (o.f1 != null) {
    setAt(f.frequency, o.f0 ?? 1200, t);
    expTo(f.frequency, o.f1, t + (o.sweep ?? o.decay ?? 0.1));
  }
  node.connect(f);
  node = f;

  if (o.hp) { const h = filt(ctx, 'highpass', o.hp, 0.7); node.connect(h); node = h; }
  if (o.lp) { const l = filt(ctx, 'lowpass', o.lp, 0.7); node.connect(l); node = l; }

  const g = gainNode(ctx, 0);
  ampEnv(g.gain, {
    t, peak: o.peak ?? 0.7, attack: o.attack ?? 0.001,
    hold: o.hold ?? 0, decay: o.decay ?? 0.12, curve: o.curve,
  });
  node.connect(g);

  let tail = g;
  if (o.drive) {
    const mix = clamp(o.driveMix ?? 0.65, 0, 1);
    const sum = gainNode(ctx, 1);
    const w = shaper(ctx, satCurve(o.drive));
    const wet = gainNode(ctx, mix);
    const dry = gainNode(ctx, 1 - mix);
    g.connect(w); w.connect(wet); wet.connect(sum);
    g.connect(dry); dry.connect(sum);
    tail = sum;
  }
  if (o.pan != null) { const p = panner(ctx, o.pan); tail.connect(p); tail = p; }
  tail.connect(out);

  const total = (o.attack ?? 0.001) + (o.hold ?? 0) + (o.decay ?? 0.12) + 0.02;
  s.start(t, off);
  s.stop(t + total);
  return { source: s, filter: f, gain: g, out: tail, end: t + total };
}

/**
 * Pitch-dropping tonal thump — the "chest punch" under a gunshot / explosion.
 * o: { t, f0, f1, dur, peak, type, drive, glide }
 */
export function thump(ctx, out, o = {}) {
  const t = o.t ?? 0;
  const o1 = osc(ctx, o.type || 'sine', o.f0 ?? 160);
  setAt(o1.frequency, o.f0 ?? 160, t);
  expTo(o1.frequency, o.f1 ?? 45, t + (o.glide ?? o.dur ?? 0.09));
  const g = gainNode(ctx, 0);
  ampEnv(g.gain, { t, peak: o.peak ?? 0.8, attack: o.attack ?? 0.0015, decay: o.dur ?? 0.14 });
  let node = o1;
  node.connect(g);
  let tail = g;
  if (o.drive) { const w = shaper(ctx, satCurve(o.drive)); g.connect(w); tail = w; }
  tail.connect(out);
  o1.start(t);
  o1.stop(t + (o.dur ?? 0.14) + 0.05);
  return { osc: o1, gain: g, end: t + (o.dur ?? 0.14) + 0.05 };
}

/**
 * A single decaying sine/FM partial — bells, pings, chimes, metal ring.
 * o: { t, freq, dur, peak, type, mod (ratio), index, detune, pan, attack }
 */
export function ping(ctx, out, o = {}) {
  const t = o.t ?? 0;
  const dur = o.dur ?? 0.6;
  const car = osc(ctx, o.type || 'sine', o.freq ?? 880);
  if (o.detune) car.detune.value = o.detune;
  let mod = null;
  if (o.mod) {
    mod = osc(ctx, 'sine', (o.freq ?? 880) * o.mod);
    const mg = gainNode(ctx, (o.freq ?? 880) * (o.index ?? 1));
    ampEnv(mg.gain, { t, peak: (o.freq ?? 880) * (o.index ?? 1), attack: 0.002, decay: dur * (o.modDecay ?? 0.35) });
    mod.connect(mg);
    mg.connect(car.frequency);
    mod.start(t);
    mod.stop(t + dur + 0.05);
  }
  const g = gainNode(ctx, 0);
  ampEnv(g.gain, { t, peak: o.peak ?? 0.3, attack: o.attack ?? 0.003, decay: dur });
  car.connect(g);
  let tail = g;
  if (o.pan != null) { const p = panner(ctx, o.pan); g.connect(p); tail = p; }
  tail.connect(out);
  car.start(t);
  car.stop(t + dur + 0.06);
  return { osc: car, mod, gain: g, out: tail, end: t + dur + 0.06 };
}

/**
 * Inharmonic FM bell — the low bell in the round stingers.
 * o: { t, freq, dur, peak, index, ratio, pan }
 */
export function bell(ctx, out, o = {}) {
  const t = o.t ?? 0;
  const dur = o.dur ?? 3.5;
  const f = o.freq ?? 110;
  const partials = o.partials || [
    [1.0, 1.0, 1.0], [2.0, 0.55, 0.78], [2.98, 0.4, 0.6],
    [4.17, 0.3, 0.42], [5.43, 0.22, 0.3], [6.79, 0.15, 0.22], [8.21, 0.1, 0.16],
  ];
  const bus = gainNode(ctx, o.peak ?? 0.25);
  for (let i = 0; i < partials.length; i++) {
    const [r, a, dm] = partials[i];
    const p = osc(ctx, 'sine', f * r * (1 + (o.stretch ?? 0.0015) * i * i));
    const g = gainNode(ctx, 0);
    ampEnv(g.gain, { t, peak: a, attack: 0.004 + i * 0.002, decay: dur * dm });
    p.connect(g);
    g.connect(bus);
    p.start(t);
    p.stop(t + dur * dm + 0.1);
  }
  // strike transient
  const strike = osc(ctx, 'triangle', f * 7.3);
  const sg = gainNode(ctx, 0);
  ampEnv(sg.gain, { t, peak: (o.peak ?? 0.25) * 0.5, attack: 0.001, decay: 0.05 });
  strike.connect(sg);
  sg.connect(bus);
  strike.start(t);
  strike.stop(t + 0.1);

  let tail = bus;
  if (o.pan != null) { const p = panner(ctx, o.pan); bus.connect(p); tail = p; }
  tail.connect(out);
  return { bus, out: tail, end: t + dur + 0.1 };
}

/**
 * Detuned "choir" pad voice: several saw/triangle oscillators through a formant
 * bank + slow vibrato. Sounds like massed voices without any sample.
 * o: { t, freq, dur, peak, vowel, voices, detune, vib, attack, release, type }
 */
export function choirVoice(ctx, out, o = {}) {
  const t = o.t ?? 0;
  const dur = o.dur ?? 3;
  const freq = o.freq ?? 220;
  const n = o.voices ?? 4;
  const rng = o.rng || mulberry32(99);
  const src = gainNode(ctx, 1 / n);
  const oscs = [];
  for (let i = 0; i < n; i++) {
    const t0 = o.type || (i % 2 ? 'sawtooth' : 'triangle');
    const p = osc(ctx, t0, freq);
    p.detune.value = jit(rng, o.detune ?? 14) + (i - (n - 1) / 2) * (o.spread ?? 7);
    // slow independent vibrato per voice => chorus without a chorus unit
    const lfo = osc(ctx, 'sine', rnd(rng, 3.4, 5.6));
    const lg = gainNode(ctx, rnd(rng, 3, 9) * (o.vib ?? 1));
    lfo.connect(lg);
    lg.connect(p.detune);
    lfo.start(t);
    lfo.stop(t + dur + 1);
    // slow drift
    const drift = osc(ctx, 'sine', rnd(rng, 0.09, 0.27));
    const dg = gainNode(ctx, rnd(rng, 4, 11));
    drift.connect(dg);
    dg.connect(p.detune);
    drift.start(t);
    drift.stop(t + dur + 1);
    p.connect(src);
    p.start(t);
    p.stop(t + dur + 0.9);
    oscs.push(p);
  }
  const bank = formantBank(ctx, o.vowel || 'u', { scale: o.fscale ?? 1, bwScale: 1.5 });
  const pre = filt(ctx, 'lowpass', o.lp ?? 3400, 0.6);
  src.connect(pre);
  pre.connect(bank.input);
  // a little direct signal keeps it from sounding like a telephone
  const dry = gainNode(ctx, 0.28);
  pre.connect(dry);

  const g = gainNode(ctx, 0);
  const atk = o.attack ?? 0.6;
  const rel = o.release ?? 1.2;
  setAt(g.gain, 1e-4, t);
  expTo(g.gain, o.peak ?? 0.2, t + atk);
  setAt(g.gain, o.peak ?? 0.2, t + Math.max(atk, dur - rel));
  expTo(g.gain, 1e-4, t + dur);
  setAt(g.gain, 0, t + dur + 0.02);

  bank.output.connect(g);
  dry.connect(g);
  let tail = g;
  if (o.pan != null) { const p = panner(ctx, o.pan); g.connect(p); tail = p; }
  tail.connect(out);
  return { gain: g, bank, out: tail, oscs, end: t + dur + 0.05 };
}

/**
 * Short metallic "clack" cluster — mechanical action, latches, shells, hammers.
 * o: { t, freqs:[], dur, peak, noise, bright }
 */
export function clack(ctx, out, o = {}) {
  const t = o.t ?? 0;
  const rng = o.rng || mulberry32(3);
  const peak = o.peak ?? 0.4;
  const bus = gainNode(ctx, 1);
  bus.connect(out);
  const freqs = o.freqs || [2100, 3300, 4700, 6100];
  for (let i = 0; i < freqs.length; i++) {
    const f = freqs[i] * (1 + jit(rng, 0.05));
    const p = osc(ctx, 'sine', f);
    const g = gainNode(ctx, 0);
    ampEnv(g.gain, { t: t + i * 0.0006, peak: peak * (0.9 - i * 0.16), attack: 0.0008, decay: (o.dur ?? 0.045) * (1 - i * 0.12) });
    p.connect(g);
    g.connect(bus);
    p.start(t);
    p.stop(t + (o.dur ?? 0.045) + 0.02);
  }
  if (o.noise) {
    noiseBurst(ctx, bus, {
      noise: o.noise, t, type: 'highpass', f0: o.bright ?? 2600, q: 0.7,
      attack: 0.0006, decay: (o.dur ?? 0.045) * 0.7, peak: peak * 0.8, rng,
    });
  }
  return { bus, end: t + (o.dur ?? 0.05) + 0.03 };
}

/* ------------------------------------------------------------------ *
 * Buffer post-processing
 * ------------------------------------------------------------------ */

/** Peak-normalise a rendered buffer so every sound has a predictable level. */
export function normalizeBuffer(buf, target = 0.95) {
  let peak = 0;
  for (let c = 0; c < buf.numberOfChannels; c++) {
    const d = buf.getChannelData(c);
    for (let i = 0; i < d.length; i++) {
      const a = d[i] < 0 ? -d[i] : d[i];
      if (a > peak) peak = a;
    }
  }
  if (peak < 1e-6) return buf;
  const k = target / peak;
  if (k > 0.999 && k < 1.001) return buf;
  for (let c = 0; c < buf.numberOfChannels; c++) {
    const d = buf.getChannelData(c);
    for (let i = 0; i < d.length; i++) d[i] *= k;
  }
  return buf;
}

/**
 * Loudness-target normalisation.
 *
 * Peak-normalising everything to the same number is what kills a mix: a 12-gauge
 * blast, a UI tick and a footstep all land at 0.95 peak, and a long reverberant
 * explosion ends up with far *less* perceived level than a 40 ms click at the
 * same peak. So instead we normalise to a target short-term RMS — the loudest
 * `window` seconds of the sound, which is what the ear actually judges — and
 * then let a peak ceiling pull the gain back down if the transient would clip.
 *
 * Returns the linear gain that was applied (1 when nothing was done).
 *
 * o: { window (sec, default 0.3), peak (ceiling, default 0.99), maxGain, minGain }
 */
export function rmsNormalize(buf, targetDb = -18, o = {}) {
  const ch = buf.numberOfChannels;
  const n = buf.length;
  if (!n || !ch) return 1;
  const data = [];
  for (let c = 0; c < ch; c++) data.push(buf.getChannelData(c));

  // running sum of the per-sample mean square, plus the absolute peak
  let peak = 0;
  const acc = new Float64Array(n + 1);
  for (let i = 0; i < n; i++) {
    let s = 0;
    for (let c = 0; c < ch; c++) {
      const v = data[c][i];
      s += v * v;
      const a = v < 0 ? -v : v;
      if (a > peak) peak = a;
    }
    acc[i + 1] = acc[i] + s / ch;
  }
  if (peak < 1e-6) return 1;

  const win = Math.max(1, Math.min(n, Math.floor((o.window ?? 0.3) * buf.sampleRate)));
  const hop = Math.max(1, Math.floor(win / 8));
  let best = 0;
  for (let i = 0; i + win <= n; i += hop) {
    const ms = (acc[i + win] - acc[i]) / win;
    if (ms > best) best = ms;
  }
  if (win >= n) best = acc[n] / n;
  const rms = Math.sqrt(best);
  if (rms < 1e-7) return 1;

  const target = Math.pow(10, targetDb / 20);
  let k = target / rms;
  const ceil = o.peak ?? 0.99;
  if (peak * k > ceil) k = ceil / peak;
  k = clamp(k, o.minGain ?? 1e-3, o.maxGain ?? 64);
  if (k > 0.999 && k < 1.001) return 1;
  for (let c = 0; c < ch; c++) {
    const d = data[c];
    for (let i = 0; i < n; i++) d[i] *= k;
  }
  return k;
}

/** Fade the very start/end to zero to kill clicks on one-shots. */
export function deClick(buf, fadeIn = 0.0015, fadeOut = 0.006) {
  const sr = buf.sampleRate;
  const ni = Math.min(buf.length, Math.floor(fadeIn * sr));
  const no = Math.min(buf.length, Math.floor(fadeOut * sr));
  for (let c = 0; c < buf.numberOfChannels; c++) {
    const d = buf.getChannelData(c);
    for (let i = 0; i < ni; i++) d[i] *= i / ni;
    for (let i = 0; i < no; i++) d[d.length - 1 - i] *= i / no;
  }
  return buf;
}

/**
 * Chop the dead air off the end of a one-shot. Renders are given generous
 * lengths so reverb tails are never clipped; this reclaims whatever the tail
 * did not actually use, which is a large share of total buffer memory.
 */
export function trimTail(ctx, buf, opts = {}) {
  const sr = buf.sampleRate;
  const ch = buf.numberOfChannels;
  let peak = 0;
  for (let c = 0; c < ch; c++) {
    const d = buf.getChannelData(c);
    for (let i = 0; i < d.length; i++) {
      const a = d[i] < 0 ? -d[i] : d[i];
      if (a > peak) peak = a;
    }
  }
  if (peak < 1e-6) return buf;
  const limit = peak * Math.pow(10, (opts.db ?? -60) / 20);
  let last = 0;
  for (let c = 0; c < ch; c++) {
    const d = buf.getChannelData(c);
    for (let i = d.length - 1; i > last; i--) {
      const a = d[i] < 0 ? -d[i] : d[i];
      if (a > limit) { if (i > last) last = i; break; }
    }
  }
  const pad = Math.ceil((opts.pad ?? 0.02) * sr);
  const minLen = Math.ceil((opts.min ?? 0.05) * sr);
  const n = Math.max(minLen, Math.min(buf.length, last + pad));
  if (n >= buf.length - 256) return buf;
  const out = ctx.createBuffer(ch, n, sr);
  for (let c = 0; c < ch; c++) out.getChannelData(c).set(buf.getChannelData(c).subarray(0, n));
  return out;
}

/**
 * If both channels are identical, keep one. Saves half the memory on anything
 * that turned out to be mono (thumps, single-oscillator pings, …).
 */
export function maybeMono(ctx, buf, tol = 0.002) {
  if (buf.numberOfChannels !== 2) return buf;
  const L = buf.getChannelData(0);
  const R = buf.getChannelData(1);
  for (let i = 0; i < L.length; i++) {
    const d = L[i] - R[i];
    if (d > tol || d < -tol) return buf;
  }
  const out = ctx.createBuffer(1, buf.length, buf.sampleRate);
  out.getChannelData(0).set(L);
  return out;
}

/**
 * Turn a render of length (dur + xfade) into a seamless loop of length dur by
 * folding the overhang back over the head with an equal-power crossfade.
 */
export function foldSeamless(ctx, buf, dur, xfade) {
  const sr = buf.sampleRate;
  const n = Math.floor(dur * sr);
  const nx = Math.min(Math.floor(xfade * sr), n, buf.length - n);
  if (nx <= 0) return buf;
  const outBuf = ctx.createBuffer(buf.numberOfChannels, n, sr);
  for (let c = 0; c < buf.numberOfChannels; c++) {
    const src = buf.getChannelData(c);
    const dst = outBuf.getChannelData(c);
    dst.set(src.subarray(0, n));
    for (let i = 0; i < nx; i++) {
      const t = i / nx;
      // Intermediate crossfade law. An equal-power (cos/sin) fade is right for
      // uncorrelated material (wind, reverb tails) but boosts phase-locked
      // drones by +3 dB; an equal-gain fade is right for the drones but digs a
      // -3 dB hole in the noise. Normalising by the geometric mean of the two
      // laws splits the error: worst case +/-1.5 dB, which nobody hears.
      let a = 1 - t;          // fades out the overhang
      let b = t;              // fades in the head
      const norm = Math.sqrt((a + b) * Math.sqrt(a * a + b * b)) || 1;
      a /= norm; b /= norm;
      dst[i] = dst[i] * b + src[n + i] * a;
    }
  }
  return outBuf;
}

/** Offline-context factory bound to a fixed sample rate. */
export function makeOffline(sampleRate, channels, seconds) {
  const len = Math.max(128, Math.ceil(seconds * sampleRate));
  const OAC = (typeof OfflineAudioContext !== 'undefined')
    ? OfflineAudioContext
    : (typeof webkitOfflineAudioContext !== 'undefined' ? webkitOfflineAudioContext : null);
  if (!OAC) throw new Error('OfflineAudioContext unavailable');
  return new OAC(channels, len, sampleRate);
}
