/**
 * sfx.js — procedural sound-effect recipes for Doom Town.
 *
 * Every entry is a recipe rendered once at init into an AudioBuffer by audio.js:
 *
 *   name: {
 *     dur:      render length in seconds
 *     variants: how many differently-seeded renders to bake (rapid fire never
 *               replays the identical waveform)
 *     gain:     playback gain relative to other sounds
 *     bus:      'sfx' | 'ui' | 'ambient' | 'music'
 *     loop:     true for looping beds
 *     xfade:    extra seconds rendered past `dur` and folded back for a seamless loop
 *     jitter:   random playback detune in cents applied per trigger
 *     rateJit:  random playback-rate spread per trigger
 *     norm:     peak-normalise target
 *     build(ctx, out, rng, variantIndex, lib)
 *   }
 *
 * `lib` carries shared pre-baked noise buffers and impulse responses.
 */

import {
  mulberry32, rnd, rint, pick, jit, clamp, dbToGain, mtof, nf, lerp, lockFreq,
  gainNode, filt, osc, delayNode, panner, chain, expTo, setAt, linTo, ampEnv,
  satCurve, fuzzCurve, foldCurve, chebyCurve, shaper, makeReverb,
  formantBank, morphVowel, glottalBuffer, VOWELS,
  noiseBurst, thump, ping, bell, choirVoice, clack,
} from './dsp.js';

/* ================================================================== *
 * Local helpers
 * ================================================================== */

/** Convolution send: returns the input node; wet output is already connected. */
function tailSend(ctx, out, ir, wet = 0.3, opts = {}) {
  const send = gainNode(ctx, wet);
  const c = ctx.createConvolver();
  c.normalize = true;
  c.buffer = ir;
  const hp = filt(ctx, 'highpass', opts.hp ?? 110, 0.6);
  const lp = filt(ctx, 'lowpass', opts.lp ?? 9000, 0.5);
  send.connect(c);
  c.connect(hp);
  hp.connect(lp);
  lp.connect(out);
  return send;
}

/** Raw-JS granular crackle (fire, dirt, debris, static). Far cheaper than 500 nodes. */
function crackleBuffer(ctx, dur, rng, o = {}) {
  const sr = ctx.sampleRate;
  const n = Math.max(2, Math.ceil(dur * sr));
  const buf = ctx.createBuffer(2, n, sr);
  const density = o.density ?? 30;            // events per second
  const fLo = o.fLo ?? 900;
  const fHi = o.fHi ?? 6500;
  const decLo = o.decayLo ?? 0.004;
  const decHi = o.decayHi ?? 0.03;
  const count = Math.max(1, Math.round(density * dur));
  const chans = [buf.getChannelData(0), buf.getChannelData(1)];
  for (let e = 0; e < count; e++) {
    const start = Math.floor(rnd(rng, 0, dur) * sr);
    const f = Math.exp(lerp(Math.log(fLo), Math.log(fHi), Math.pow(rng(), 1.7)));
    const dec = rnd(rng, decLo, decHi);
    const amp = Math.pow(rng(), 2.2) * (o.amp ?? 0.9) + 0.02;
    const pan = rnd(rng, -1, 1);
    const gl = Math.sqrt((1 - pan) * 0.5), gr = Math.sqrt((1 + pan) * 0.5);
    const len = Math.min(n - start, Math.ceil(dec * 5 * sr));
    const w = (2 * Math.PI * f) / sr;
    const dmp = Math.exp(-1 / (dec * sr));
    const ph0 = rng() * Math.PI * 2;
    for (let i = 0; i < len; i++) {
      const env = Math.pow(dmp, i);
      if (env < 1e-4) break;
      const v = Math.sin(ph0 + w * i) * env * amp;
      const idx = start + i;
      chans[0][idx] += v * gl;
      chans[1][idx] += v * gr;
    }
  }
  return buf;
}

/** Granular gravel/dirt scrape bed (zombie rising, debris). */
function grainBuffer(ctx, dur, rng, o = {}) {
  const sr = ctx.sampleRate;
  const n = Math.max(2, Math.ceil(dur * sr));
  const buf = ctx.createBuffer(2, n, sr);
  const chans = [buf.getChannelData(0), buf.getChannelData(1)];
  const count = Math.round((o.density ?? 500) * dur);
  for (let e = 0; e < count; e++) {
    const start = Math.floor(Math.pow(rng(), o.skew ?? 1) * dur * sr);
    const len = Math.min(n - start, Math.ceil(rnd(rng, 0.0008, 0.006) * sr));
    if (len <= 1) continue;
    const amp = Math.pow(rng(), 1.6) * (o.amp ?? 0.5);
    const pan = rnd(rng, -0.85, 0.85);
    const gl = Math.sqrt((1 - pan) * 0.5), gr = Math.sqrt((1 + pan) * 0.5);
    for (let i = 0; i < len; i++) {
      const w = (rng() * 2 - 1) * (1 - i / len) * amp;
      chans[0][start + i] += w * gl;
      chans[1][start + i] += w * gr;
    }
  }
  return buf;
}

function bufSrc(ctx, buffer, t = 0, opts = {}) {
  const s = ctx.createBufferSource();
  s.buffer = buffer;
  if (opts.rate) s.playbackRate.value = opts.rate;
  if (opts.loop) { s.loop = true; }
  s.start(t, opts.offset ?? 0, opts.duration);
  return s;
}

/* ------------------------------------------------------------------ *
 * Mechanical vocabulary — the parts every gun-handling sound is made of.
 * ------------------------------------------------------------------ */

/**
 * A piece of steel striking another piece of steel: an inharmonic mode cluster
 * with a noise transient, optionally over a low body thud.
 * o: { t, f (fundamental), modes, dur, peak, noise, bright, thud, pan, noiseAmp }
 */
function steelHit(ctx, out, rng, o = {}) {
  const t = o.t ?? 0;
  const base = o.f ?? 2000;
  const modes = o.modes || [1, 1.63, 2.44, 3.41, 4.7];
  const dur = o.dur ?? 0.05;
  const peak = o.peak ?? 0.4;
  for (let i = 0; i < modes.length; i++) {
    ping(ctx, out, {
      t: t + i * 0.0004,
      freq: base * modes[i] * (1 + jit(rng, 0.04)),
      dur: Math.max(0.006, dur * (1 - i * 0.13)),
      peak: peak * Math.max(0.05, 0.95 - i * 0.16),
      type: i < 2 ? 'triangle' : 'sine',
      pan: o.pan,
    });
  }
  if (o.noise) {
    noiseBurst(ctx, out, {
      noise: o.noise, t, type: 'highpass', f0: o.bright ?? base * 1.35, q: 0.7,
      attack: 0.0005, decay: dur * 0.65, peak: peak * (o.noiseAmp ?? 0.8), rng,
    });
  }
  if (o.thud) {
    thump(ctx, out, {
      t, f0: o.thud, f1: o.thud * 0.34, dur: dur * 2.4,
      peak: peak * (o.thudAmp ?? 0.5), type: 'triangle', drive: 2,
    });
  }
  return t + dur * 2.4 + 0.02;
}

/**
 * Metal sliding on metal — a magazine leaving a well, a bolt on its rails, a
 * pump on its tube. A swept band of noise plus the grain of the contact.
 */
function railSlide(ctx, out, rng, o = {}) {
  const t = o.t ?? 0;
  const dur = o.dur ?? 0.09;
  const peak = o.peak ?? 0.3;
  noiseBurst(ctx, out, {
    noise: o.noise, t, type: 'bandpass', f0: o.f0 ?? 2600, f1: o.f1 ?? 1200,
    q: o.q ?? 1.8, sweep: dur, attack: o.attack ?? 0.006, decay: dur,
    peak, curve: o.curve || 'lin', rng,
  });
  const gr = bufSrc(ctx, grainBuffer(ctx, dur + 0.03, rng, { density: o.grain ?? 420, amp: 0.55, skew: o.skew ?? 0.9 }), t);
  const gf = filt(ctx, 'bandpass', o.grainF ?? 3200, 1.1);
  const gg = gainNode(ctx, 0);
  ampEnv(gg.gain, { t, peak: peak * (o.grainAmp ?? 0.55), attack: Math.max(0.004, dur * 0.2), decay: dur, curve: 'lin' });
  gr.connect(gf); gf.connect(gg); gg.connect(out);
  return t + dur + 0.03;
}

/** Loose brass / linked rounds / a spring shifting: n small random clacks. */
function rattle(ctx, out, rng, o = {}) {
  const t = o.t ?? 0;
  const n = o.count ?? 4;
  const spread = o.spread ?? 0.08;
  const f = o.f ?? 3200;
  for (let i = 0; i < n; i++) {
    clack(ctx, out, {
      t: t + rnd(rng, 0, spread),
      freqs: [f * (1 + jit(rng, 0.3)), f * 1.7 * (1 + jit(rng, 0.25))],
      dur: rnd(rng, 0.008, 0.022),
      peak: (o.peak ?? 0.1) * rnd(rng, 0.5, 1),
      noise: o.noise, bright: f * 1.5, rng,
    });
  }
  return t + spread + 0.05;
}

/** A small coil spring letting go — the ping under a mag release or an ejector. */
function springTwang(ctx, out, rng, o = {}) {
  const t = o.t ?? 0;
  const f = o.f ?? 1800;
  const dur = o.dur ?? 0.09;
  const o1 = osc(ctx, 'triangle', f);
  setAt(o1.frequency, f * 1.25, t);
  expTo(o1.frequency, f * 0.8, t + dur);
  const vib = osc(ctx, 'sine', rnd(rng, 45, 90));
  const vg = gainNode(ctx, rnd(rng, 60, 160));
  vib.connect(vg); vg.connect(o1.detune);
  vib.start(t); vib.stop(t + dur + 0.05);
  const g = gainNode(ctx, 0);
  ampEnv(g.gain, { t, peak: o.peak ?? 0.09, attack: 0.001, decay: dur });
  o1.connect(g); g.connect(out);
  o1.start(t); o1.stop(t + dur + 0.05);
  return t + dur + 0.05;
}

/** Cloth / webbing / a sling brushing past. */
function clothBrush(ctx, out, rng, o = {}) {
  const t = o.t ?? 0;
  const dur = o.dur ?? 0.16;
  noiseBurst(ctx, out, {
    noise: o.noise, t, type: 'bandpass', f0: o.f0 ?? 2400, f1: o.f1 ?? 5200,
    q: 0.5, sweep: dur * 0.7, attack: dur * 0.35, decay: dur,
    peak: o.peak ?? 0.12, curve: 'lin', rng,
  });
  return t + dur;
}

/* ================================================================== *
 * Weapons
 * ================================================================== */

/**
 * The shared gunshot architecture:
 *   transient click  → the firing-pin/primer snap, sub-5 ms
 *   crack            → bandpassed noise, the supersonic "crack" of the round
 *   body             → broadband blast, lowpass sweeping down, the muzzle report
 *   thump            → pitch-dropping sine, the punch you feel in the chest
 *   mech             → action/bolt/slide rattle a few ms later
 *
 * Note what is *not* in that list: the tail. Every shot used to convolve itself
 * with the 1.4 s street impulse response and then get cut off at 0.72 s, so the
 * reverb was chopped mid-decay on every single round; twenty rounds meant twenty
 * truncated tails stacked on top of each other, which is both muddy and
 * expensive. The tail now lives once in the live graph (`audio.js _buildSends`)
 * and every gun voice feeds it, so it is never truncated and N shots sum into
 * one coherent street. Recipes here render dry and short.
 */
function gunShot(ctx, out, lib, rng, spec, t = 0) {
  const white = lib.noise.white;
  const pink = lib.noise.pink;
  const dry = gainNode(ctx, 1);
  dry.connect(out);

  const pj = 1 + jit(rng, spec.jitter ?? 0.05);   // per-shot spectral jitter
  const drive = spec.drive ?? 5;

  // 1. primer / firing pin transient
  noiseBurst(ctx, dry, {
    noise: white, t, type: 'highpass', f0: (spec.clickF ?? 4200) * pj, q: 0.6,
    attack: 0.0003, decay: 0.0045, peak: (spec.click ?? 0.55), rng,
  });

  // 2. supersonic crack
  noiseBurst(ctx, dry, {
    noise: white, t: t + 0.0004, type: 'bandpass',
    f0: spec.crack * pj, f1: spec.crack * 0.3 * pj, q: spec.crackQ ?? 0.85,
    sweep: spec.crackDec * 0.8, attack: 0.0005, decay: spec.crackDec,
    peak: spec.crackAmp ?? 0.8, drive, driveMix: spec.driveMix ?? 0.6, rng,
  });

  // 3. muzzle blast body
  noiseBurst(ctx, dry, {
    noise: pink, t: t + 0.0008, type: 'lowpass',
    f0: spec.body * 3.6 * pj, f1: spec.body * 0.42, q: spec.bodyQ ?? 1.4,
    sweep: spec.bodyDec * 0.6, attack: 0.0011, decay: spec.bodyDec,
    peak: spec.bodyAmp ?? 1.0, drive: drive * 1.2, driveMix: 0.55, rng,
  });

  // a second, lower blast layer for the big guns
  if (spec.body2) {
    noiseBurst(ctx, dry, {
      noise: lib.noise.brown, t: t + 0.0015, type: 'lowpass',
      f0: spec.body2 * pj, f1: spec.body2 * 0.3, q: 0.8,
      sweep: spec.bodyDec, attack: 0.002, decay: spec.bodyDec * 1.5,
      peak: spec.body2Amp ?? 0.7, rng,
    });
  }

  // 4. chest thump
  thump(ctx, dry, {
    t: t + 0.0006, f0: spec.thump0 * pj, f1: spec.thump1,
    dur: spec.thumpDec ?? 0.11, glide: (spec.thumpDec ?? 0.11) * 0.55,
    peak: spec.thumpAmp ?? 0.9, type: spec.thumpType || 'sine', drive: 3,
  });

  // 5. mechanical action — the single biggest per-weapon fingerprint. An AK
  // carrier is a slab of steel banging in a stamped receiver (low, loud); an
  // MP5's rollers are small and fast (high, tight); a break-open Olympia has
  // no reciprocating parts at all.
  if (spec.mech !== false) {
    clack(ctx, dry, {
      t: t + (spec.mechT ?? 0.018) * (1 + jit(rng, 0.25)),
      freqs: (spec.mechFreqs || [1900, 3100, 4600, 6400]).map((f) => f * (1 + jit(rng, 0.08))),
      dur: spec.mechDur ?? 0.05, peak: spec.mechAmp ?? 0.22,
      noise: white, bright: (spec.mechFreqs ? spec.mechFreqs[0] : 1900) * 1.3, rng,
    });
    if (spec.mech2T) {
      clack(ctx, dry, {
        t: t + spec.mech2T * (1 + jit(rng, 0.2)),
        freqs: (spec.mechFreqs || [1900, 3100, 4600]).map((f) => f * 0.82 * (1 + jit(rng, 0.09))),
        dur: (spec.mechDur ?? 0.05) * 1.1, peak: (spec.mechAmp ?? 0.22) * 0.8,
        noise: white, bright: 2000, rng,
      });
    }
  }

  return { dry };
}

/**
 * One entry per weapon id (plus the six legacy type names, which are aliases).
 * The point of the table is that no two of these can be mistaken for each other:
 * calibre sets `crack`/`thump`, barrel length sets the balance of crack against
 * `body`, receiver material and action type set `mech`.
 */
const GUN_SPECS = {
  // ---- pistols -------------------------------------------------------
  gun_m1911: {
    // .45 ACP is subsonic: almost no crack, a fat low report, and the loudest
    // part of the whole event is the slide cycling in a steel frame.
    crack: 2200, crackDec: 0.055, crackAmp: 0.78, crackQ: 0.75,
    body: 760, bodyDec: 0.13, bodyAmp: 1.0,
    thump0: 176, thump1: 50, thumpDec: 0.12, thumpAmp: 0.95,
    mechT: 0.026, mech2T: 0.072, mechAmp: 0.38, mechDur: 0.045,
    mechFreqs: [2200, 3400, 4900, 6600],
    drive: 5, click: 0.62, send: 0.26, dur: 0.36,
  },
  gun_python: {
    // .357 Magnum out of a 6" revolver: a genuinely painful crack, a long low
    // body, and a sideways blast out of the cylinder gap that no auto has.
    crack: 2600, crackDec: 0.075, crackAmp: 1.0, crackQ: 0.9,
    body: 520, bodyDec: 0.2, bodyAmp: 1.1, body2: 280, body2Amp: 0.65,
    thump0: 140, thump1: 38, thumpDec: 0.2, thumpAmp: 1.05,
    mech: false, gap: true, frameRing: 2900,
    drive: 7, click: 0.5, send: 0.42, dur: 0.48,
  },
  // ---- rifles --------------------------------------------------------
  gun_m14: {
    // 7.62×51 from a long barrel: the hardest, highest crack in the game, and
    // a walnut stock that rings under the op-rod.
    crack: 3400, crackDec: 0.055, crackAmp: 1.05, crackQ: 1.15,
    body: 780, bodyDec: 0.12, bodyAmp: 0.95,
    thump0: 140, thump1: 42, thumpDec: 0.13, thumpAmp: 0.9,
    mechT: 0.017, mech2T: 0.052, mechAmp: 0.36, mechDur: 0.05,
    mechFreqs: [1400, 2400, 3800, 5200],
    wood: 300, zing: true,
    drive: 8, click: 0.72, send: 0.42, dur: 0.4,
  },
  gun_galil: {
    // 5.56 in an all-steel AK-pattern receiver: a brighter, shorter crack than
    // the M14 and a much more metallic action.
    crack: 3000, crackDec: 0.048, crackAmp: 1.0, crackQ: 1.2,
    body: 840, bodyDec: 0.095, bodyAmp: 0.92,
    thump0: 152, thump1: 46, thumpDec: 0.1, thumpAmp: 0.82,
    mechT: 0.015, mech2T: 0.045, mechAmp: 0.4, mechDur: 0.042,
    mechFreqs: [2200, 3600, 5200, 7000],
    zing: true,
    drive: 7.5, click: 0.68, send: 0.36, dur: 0.38,
  },
  gun_ak74u: {
    // 5.45 dumped out of a 8" barrel: most of the powder burns outside the
    // muzzle, so this is all blast and very little crack — and the bolt carrier
    // is a lump of steel slamming in a stamped box. Low, rude, loud.
    crack: 2400, crackDec: 0.06, crackAmp: 0.95, crackQ: 0.8,
    body: 640, bodyDec: 0.115, bodyAmp: 1.08, body2: 300, body2Amp: 0.5,
    thump0: 158, thump1: 44, thumpDec: 0.12, thumpAmp: 0.95,
    mechT: 0.013, mech2T: 0.038, mechAmp: 0.5, mechDur: 0.055,
    mechFreqs: [1100, 1900, 2900, 4100],
    drive: 8, click: 0.6, send: 0.4, dur: 0.38,
  },
  gun_mp5: {
    // 9mm, roller-delayed, closed bolt: the quietest and tightest report here,
    // with a fast bright chatter of small parts sitting right on top of it.
    crack: 2700, crackDec: 0.036, crackAmp: 0.8, crackQ: 1.05,
    body: 800, bodyDec: 0.065, bodyAmp: 0.8,
    thump0: 160, thump1: 52, thumpDec: 0.06, thumpAmp: 0.62,
    mechT: 0.011, mech2T: 0.03, mechAmp: 0.5, mechDur: 0.035,
    mechFreqs: [2600, 4100, 5600, 7400],
    drive: 5.5, click: 0.6, send: 0.2, dur: 0.3,
  },
  gun_rpd: {
    // 7.62×39 belt-fed, fired from an open bolt with a long heavy carrier and
    // steel links being torn off the belt every round.
    crack: 2500, crackDec: 0.062, crackAmp: 0.92, crackQ: 0.85,
    body: 600, bodyDec: 0.15, bodyAmp: 1.06, body2: 270, body2Amp: 0.6,
    thump0: 142, thump1: 38, thumpDec: 0.16, thumpAmp: 1.02,
    mechT: 0.014, mech2T: 0.042, mechAmp: 0.44, mechDur: 0.06,
    mechFreqs: [1500, 2600, 3900, 5400],
    belt: true,
    drive: 8, click: 0.6, send: 0.4, dur: 0.42,
  },
  // ---- shotguns ------------------------------------------------------
  gun_remington870: {
    crack: 1550, crackDec: 0.09, crackAmp: 0.72, crackQ: 0.6,
    body: 400, bodyDec: 0.22, bodyAmp: 1.15, body2: 210, body2Amp: 0.9,
    thump0: 115, thump1: 30, thumpDec: 0.24, thumpAmp: 1.1,
    mechT: 0.03, mechAmp: 0.16, mechDur: 0.05, mechFreqs: [1500, 2600, 3900],
    poof: 0.24,
    drive: 9, click: 0.42, send: 0.52, dur: 0.52,
  },
  gun_olympia: {
    // Break-open double: there is *no action*. Nothing cycles, nothing clatters
    // — just two barrels of 12-gauge and the barrels themselves ringing.
    crack: 1450, crackDec: 0.105, crackAmp: 0.75, crackQ: 0.55,
    body: 380, bodyDec: 0.25, bodyAmp: 1.2, body2: 195, body2Amp: 0.95,
    thump0: 108, thump1: 28, thumpDec: 0.27, thumpAmp: 1.15,
    mech: false, poof: 0.32, barrelRing: 1650,
    drive: 9.5, click: 0.38, send: 0.58, dur: 0.56,
  },
};

function buildGun(name) {
  const spec = GUN_SPECS[name];
  return function build(ctx, out, rng, v, lib) {
    const g = gunShot(ctx, out, lib, rng, spec, 0.002);
    const dry = g.dry;

    if (spec.zing) {
      // supersonic bullet zing peeling away from the muzzle
      const o1 = osc(ctx, 'sine', 4200);
      setAt(o1.frequency, rnd(rng, 3600, 5000), 0.004);
      expTo(o1.frequency, 700, 0.09);
      const zg = gainNode(ctx, 0);
      ampEnv(zg.gain, { t: 0.004, peak: 0.1, attack: 0.002, decay: 0.09 });
      o1.connect(zg); zg.connect(dry);
      o1.start(0.004); o1.stop(0.12);
    }
    if (spec.poof) {
      // the wad and the unburnt powder leaving the muzzle after the shot
      noiseBurst(ctx, dry, {
        noise: lib.noise.brown, t: 0.012, type: 'lowpass', f0: 900, f1: 200,
        sweep: spec.poof * 0.8, attack: 0.008, decay: spec.poof, peak: 0.35, rng,
      });
    }
    if (spec.belt) {
      // links tearing off the belt and falling out of the feed tray
      for (let i = 0; i < 3; i++) {
        clack(ctx, dry, {
          t: 0.028 + i * 0.015 + rnd(rng, 0, 0.008),
          freqs: [3100 * (1 + jit(rng, 0.2)), 5200 * (1 + jit(rng, 0.2))],
          dur: 0.018, peak: 0.1, noise: lib.noise.white, bright: 4200, rng,
        });
      }
    }
    if (spec.gap) {
      // the sideways jet out of the barrel/cylinder gap — a revolver tell
      noiseBurst(ctx, dry, {
        noise: lib.noise.white, t: 0.0012, type: 'bandpass', f0: 3800, f1: 1400,
        q: 0.9, sweep: 0.05, attack: 0.0008, decay: 0.07, peak: 0.3,
        pan: rnd(rng, 0.35, 0.75), drive: 4, rng,
      });
    }
    if (spec.frameRing) {
      // the steel frame itself ringing for a moment after a magnum load
      ping(ctx, dry, { t: 0.002, freq: spec.frameRing * (1 + jit(rng, 0.05)), dur: 0.16, peak: 0.055, type: 'triangle' });
      ping(ctx, dry, { t: 0.002, freq: spec.frameRing * 1.63, dur: 0.1, peak: 0.03 });
    }
    if (spec.barrelRing) {
      // two long thin steel tubes, struck from the inside
      for (const m of [1, 1.74, 2.61]) {
        ping(ctx, dry, {
          t: 0.003, freq: spec.barrelRing * m * (1 + jit(rng, 0.04)),
          dur: 0.28 / m, peak: 0.05 / m, type: 'triangle',
        });
      }
    }
    if (spec.wood) {
      // stock resonance: the difference between an M14 and everything else
      woodModes(ctx, dry, rng, 0.004, 0.09, 0.14, spec.wood);
    }
  };
}

/* ================================================================== *
 * Zombie voices (formant synthesis over a damaged glottal source)
 * ================================================================== */

/**
 * The zombie voice engine. A jittery, diplophonic glottal pulse train runs
 * through a morphing formant bank, a growl sub-oscillator, a fuzz stage and a
 * wet "throat" noise layer. Everything wobbles, nothing is in tune.
 */
function zombieVoice(ctx, out, lib, rng, o = {}) {
  const t = o.t ?? 0;
  const dur = o.dur ?? 1.6;
  const f0a = o.f0a ?? 80;
  const f0b = o.f0b ?? 66;
  const wob = o.wobble ?? 0.06;
  const wobRate = o.wobRate ?? rnd(rng, 3.4, 6.2);
  const wob2Rate = rnd(rng, 0.7, 1.6);

  const src = glottalBuffer(ctx, {
    dur: dur + 0.15,
    f0: (tt) => {
      const p = clamp(tt / dur, 0, 1);
      const base = lerp(f0a, f0b, o.curve ? o.curve(p) : p);
      const w = 1 + wob * Math.sin(2 * Math.PI * wobRate * tt) * (0.6 + 0.4 * Math.sin(2 * Math.PI * wob2Rate * tt));
      return base * w;
    },
    jitter: o.jitter ?? 0.045,
    shimmer: o.shimmer ?? 0.28,
    rough: o.rough ?? 0.35,
    oq: o.oq ?? 0.6,
    breath: o.breath ?? 0.16,
    rng,
  });
  const s = bufSrc(ctx, src, t);

  // throat/chest resonance before the formants
  const pre = filt(ctx, 'lowpass', o.lp ?? 3600, 0.8);
  const hp = filt(ctx, 'highpass', 55, 0.7);
  s.connect(pre); pre.connect(hp);

  const bank = formantBank(ctx, o.vowel || 'a', { scale: o.fscale ?? 1, bwScale: o.bwScale ?? 1.6 });
  hp.connect(bank.input);
  if (o.vowel2) morphVowel(bank, o.vowel2, t + dur * (o.morphAt ?? 0.35), dur * (o.morphDur ?? 0.5), o.fscale2 ?? o.fscale ?? 1);

  // a touch of un-filtered source keeps the low end
  const direct = gainNode(ctx, o.direct ?? 0.3);
  hp.connect(direct);

  const voice = gainNode(ctx, 1);
  bank.output.connect(voice);
  direct.connect(voice);

  // growl: sub oscillator locked under the voice + ring-mod roughness
  if (o.growl) {
    const sub = osc(ctx, 'triangle', f0a * 0.5);
    setAt(sub.frequency, f0a * 0.5, t);
    expTo(sub.frequency, f0b * 0.5, t + dur);
    const sg = gainNode(ctx, 0);
    setAt(sg.gain, 1e-4, t);
    expTo(sg.gain, o.growl, t + dur * 0.2);
    expTo(sg.gain, 1e-4, t + dur);
    const am = osc(ctx, 'sine', rnd(rng, 18, 34));
    const amg = gainNode(ctx, 0.55);
    am.connect(amg); amg.connect(sg.gain);
    am.start(t); am.stop(t + dur + 0.1);
    sub.connect(sg); sg.connect(voice);
    sub.start(t); sub.stop(t + dur + 0.1);
  }

  // wet throat rattle (phlegm)
  if (o.rattle) {
    const rb = grainBuffer(ctx, dur, rng, { density: o.rattleDensity ?? 90, amp: 0.7 });
    const rs = bufSrc(ctx, rb, t);
    const rf = filt(ctx, 'bandpass', o.rattleF ?? 620, 2.2);
    const rg = gainNode(ctx, 0);
    ampEnv(rg.gain, { t, peak: o.rattle, attack: dur * 0.25, decay: dur * 0.8, curve: 'lin' });
    rs.connect(rf); rf.connect(rg); rg.connect(voice);
  }

  // drive
  let node = voice;
  if (o.drive) {
    const w = shaper(ctx, fuzzCurve(o.drive, 0.1));
    const post = filt(ctx, 'lowpass', o.postLp ?? 4200, 0.7);
    node.connect(w); w.connect(post);
    node = post;
  }

  // overall envelope
  const g = gainNode(ctx, 0);
  const atk = o.attack ?? dur * 0.12;
  const rel = o.release ?? dur * 0.4;
  setAt(g.gain, 1e-4, t);
  expTo(g.gain, o.peak ?? 0.8, t + atk);
  setAt(g.gain, o.peak ?? 0.8, t + Math.max(atk + 0.01, dur - rel));
  expTo(g.gain, 1e-4, t + dur);
  setAt(g.gain, 0, t + dur + 0.01);
  node.connect(g);

  const pan = panner(ctx, o.pan ?? rnd(rng, -0.25, 0.25));
  g.connect(pan);
  pan.connect(out);

  // breath noise around the voice
  if (o.air !== 0) {
    noiseBurst(ctx, out, {
      noise: lib.noise.pink, t, type: 'bandpass', f0: 900, q: 0.6,
      attack: dur * 0.2, decay: dur * 0.85, peak: (o.air ?? 0.08), curve: 'lin', rng,
    });
  }
  return { out: pan, gain: g, bank, end: t + dur + 0.05 };
}

/* ================================================================== *
 * The registry
 * ================================================================== */

export const SFX = {};

/**
 * Alternative spellings resolved by the engine (see audio.js ALIASES). Nothing
 * here is rendered twice: an alias is a pointer, not a copy.
 */
export const SFX_ALIASES = {
  // the six old per-*type* names, kept working for any call site that has not
  // moved to `gun_<weaponId>` yet
  gun_pistol: 'gun_m1911',
  gun_revolver: 'gun_python',
  gun_rifle: 'gun_m14',
  gun_smg: 'gun_mp5',
  gun_shotgun: 'gun_remington870',
  gun_lmg: 'gun_rpd',

  // surfaces: the old single "wall" recipe is now the concrete one
  bullet_impact_wall: 'impact_concrete',
  bullet_impact_concrete: 'impact_concrete',
  bullet_impact_wood: 'impact_wood',
  bullet_impact_metal: 'impact_metal',
  bullet_impact_dirt: 'impact_dirt',
  bullet_impact_glass: 'impact_glass',
  impact_flesh: 'flesh_hit',
  bullet_impact_flesh: 'flesh_hit',

  // handling: the three old generic names map onto the rifle set, which is what
  // they were always closest to
  reload_mag_out: 'reload_rifle_out',
  reload_mag_in: 'reload_rifle_in',
  reload_bolt: 'bolt_release',
  reload_shell: 'reload_shotgun_shell',
  reload_pump: 'pump_forward',

  // old single-sound weapon swap
  weapon_switch_in: 'weapon_raise',
  weapon_switch_out: 'weapon_lower',
};

/* ---------- guns ---------- */
for (const name of Object.keys(GUN_SPECS)) {
  const spec = GUN_SPECS[name];
  SFX[name] = {
    // Dry and short. The reverb lives in the live graph now, so the buffer only
    // has to hold the shot itself — which also means a 16-voice burst costs a
    // third of what it used to.
    dur: spec.dur ?? 0.38,
    variants: 4,
    gain: 1.0,
    jitter: 45,
    rateJit: 0.035,
    send: 'gun',
    sendAmt: spec.send ?? 0.32,
    build: buildGun(name),
  };
}

SFX.gun_raygun = {
  dur: 1.25, variants: 3, gain: 1.0, jitter: 70, rateJit: 0.04,
  level: -13, send: 'hall', sendAmt: 0.22,
  build(ctx, out, rng, v, lib) {
    const t = 0.002;
    const dry = gainNode(ctx, 1); dry.connect(out);
    // a short baked slap only: the full 2.4 s hall lives on the live `hall`
    // send (see the `send` field above), so nothing here is ever truncated
    const tail = tailSend(ctx, out, lib.ir.hall, 0.12, { hp: 200, lp: 9000 });

    // charged "pew": a fast downward glide with FM sidebands + wavefolding
    const car = osc(ctx, 'sawtooth', 1800);
    const base = rnd(rng, 1500, 2100);
    setAt(car.frequency, base * 2.6, t);
    expTo(car.frequency, base, t + 0.012);
    expTo(car.frequency, base * 0.13, t + 0.35);
    const mod = osc(ctx, 'sine', base * 1.47);
    const mg = gainNode(ctx, base * 1.6);
    ampEnv(mg.gain, { t, peak: base * 2.0, attack: 0.004, decay: 0.2 });
    mod.connect(mg); mg.connect(car.frequency);
    mod.start(t); mod.stop(t + 0.6);

    const fold = shaper(ctx, foldCurve(rnd(rng, 1.6, 2.6)));
    const bp = filt(ctx, 'bandpass', 2400, 3.2);
    setAt(bp.frequency, 4800, t); expTo(bp.frequency, 320, t + 0.3);
    const cg = gainNode(ctx, 0);
    ampEnv(cg.gain, { t, peak: 0.55, attack: 0.0015, decay: 0.3 });
    car.connect(fold); fold.connect(bp); bp.connect(cg);
    cg.connect(dry); cg.connect(tail);
    car.start(t); car.stop(t + 0.7);

    // ring-modulated zap shimmer
    const rm1 = osc(ctx, 'sine', rnd(rng, 620, 780));
    const rm2 = osc(ctx, 'sine', rnd(rng, 2900, 3600));
    const rmg = gainNode(ctx, 0);
    const ring = gainNode(ctx, 0);
    rm1.connect(ring);
    rm2.connect(ring.gain);       // ring modulation
    ampEnv(rmg.gain, { t, peak: 0.3, attack: 0.001, decay: 0.22 });
    ring.connect(rmg); rmg.connect(dry); rmg.connect(tail);
    rm1.start(t); rm1.stop(t + 0.5);
    rm2.start(t); rm2.stop(t + 0.5);

    // plasma hiss
    noiseBurst(ctx, dry, {
      noise: lib.noise.white, t, type: 'bandpass', f0: 5200, f1: 700, q: 1.6,
      sweep: 0.18, attack: 0.001, decay: 0.2, peak: 0.28, rng,
    });

    // electrical "sizzle" decay after the shot
    const szB = crackleBuffer(ctx, 0.5, rng, { density: 70, fLo: 2200, fHi: 9000, amp: 0.5 });
    const sz = bufSrc(ctx, szB, t + 0.02);
    const szg = gainNode(ctx, 0);
    ampEnv(szg.gain, { t: t + 0.02, peak: 0.2, attack: 0.01, decay: 0.42 });
    sz.connect(szg); szg.connect(dry); szg.connect(tail);

    // low sub thud so it still feels like a weapon
    thump(ctx, dry, { t, f0: 190, f1: 48, dur: 0.16, peak: 0.45, type: 'triangle', drive: 3 });
  },
};

/**
 * The Pack-a-Punch overlay. It used to be one flat layer played at 0.55 on every
 * upgraded weapon including the Ray Gun (which is already made of electricity).
 * Two weights now exist so a caller can scale it by weapon class, and neither is
 * loud enough to bury the gun underneath it.
 */
function papLayer(o) {
  return {
    dur: o.dur, variants: 3, gain: 1.0, jitter: 60, rateJit: 0.04,
    level: o.level, send: 'hall', sendAmt: 0.25, defer: o.defer ?? false,
    build(ctx, out, rng, v, lib) {
      const t = 0.001;
      const dry = gainNode(ctx, 1); dry.connect(out);
      // upward electric chirp
      const o1 = osc(ctx, 'square', 400);
      setAt(o1.frequency, rnd(rng, 350, 480) * o.f, t);
      expTo(o1.frequency, rnd(rng, 3200, 4400) * o.f, t + 0.05);
      expTo(o1.frequency, 900 * o.f, t + 0.2);
      const bp = filt(ctx, 'bandpass', 2000, 6);
      setAt(bp.frequency, 900, t); expTo(bp.frequency, 5200, t + 0.06); expTo(bp.frequency, 1100, t + 0.25);
      const g = gainNode(ctx, 0);
      ampEnv(g.gain, { t, peak: 0.35, attack: 0.001, decay: o.dec });
      o1.connect(bp); bp.connect(g); g.connect(dry);
      o1.start(t); o1.stop(t + 0.35);
      // shimmering metallic partials
      for (let i = 0; i < 4; i++) {
        ping(ctx, dry, {
          t: t + i * 0.004, freq: rnd(rng, 2400, 6800) * o.f, dur: rnd(rng, 0.1, 0.3),
          peak: 0.08, mod: 1.61, index: 1.2, pan: rnd(rng, -0.8, 0.8),
        });
      }
      if (o.sub) thump(ctx, dry, { t, f0: 210, f1: 54, dur: 0.18, peak: 0.4, type: 'triangle', drive: 3 });
      const spark = crackleBuffer(ctx, 0.3, rng, { density: 55, fLo: 3000, fHi: 11000, amp: 0.5 });
      const ss = bufSrc(ctx, spark, t);
      const sg = gainNode(ctx, 0);
      ampEnv(sg.gain, { t, peak: 0.18, attack: 0.002, decay: 0.26 });
      ss.connect(sg); sg.connect(dry);
    },
  };
}

// pistols / SMGs — a bright tick of energy, nothing more
SFX.gun_pap_layer = papLayer({ dur: 0.55, f: 1.12, dec: 0.16, level: -21 });
// rifles / LMGs / shotguns — the same idea with a low end under it.
// Deferred: weapons.js currently plays the light layer for every class (scaled
// per weapon type), so until it selects this one it must not cost init time.
SFX.gun_pap_layer_heavy = papLayer({ dur: 0.75, f: 0.86, dec: 0.22, level: -18, sub: true, defer: true });

SFX.raygun_impact = {
  defer: true,
  dur: 1.6, variants: 2, gain: 1.0, jitter: 60, send: 'hall', sendAmt: 0.25,
  build(ctx, out, rng, v, lib) {
    const t = 0.002;
    const dry = gainNode(ctx, 1); dry.connect(out);
    const tail = tailSend(ctx, out, lib.ir.hall, 0.2, { hp: 150 });
    // plasma splat: descending fold + sub boom + sizzle
    thump(ctx, dry, { t, f0: 240, f1: 36, dur: 0.5, peak: 0.9, type: 'triangle', drive: 5 });
    const o1 = osc(ctx, 'sawtooth', 900);
    setAt(o1.frequency, rnd(rng, 800, 1200), t);
    expTo(o1.frequency, 70, t + 0.5);
    const fold = shaper(ctx, foldCurve(2.4));
    const lp = filt(ctx, 'lowpass', 3000, 2);
    setAt(lp.frequency, 4000, t); expTo(lp.frequency, 180, t + 0.5);
    const g = gainNode(ctx, 0);
    ampEnv(g.gain, { t, peak: 0.5, attack: 0.002, decay: 0.5 });
    o1.connect(fold); fold.connect(lp); lp.connect(g);
    g.connect(dry); g.connect(tail);
    o1.start(t); o1.stop(t + 0.7);
    const szB = crackleBuffer(ctx, 0.9, rng, { density: 90, fLo: 1500, fHi: 9000, amp: 0.6 });
    const sz = bufSrc(ctx, szB, t);
    const szg = gainNode(ctx, 0);
    ampEnv(szg.gain, { t, peak: 0.4, attack: 0.004, decay: 0.8 });
    sz.connect(szg); szg.connect(dry); szg.connect(tail);
  },
};

SFX.explosion = {
  dur: 2.9, variants: 2, gain: 1.0, jitter: 50, send: 'boom', sendAmt: 0.4,
  build(ctx, out, rng, v, lib) {
    const t = 0.003;
    const dry = gainNode(ctx, 1); dry.connect(out);
    const tail = tailSend(ctx, out, lib.ir.cavern, 0.2, { hp: 80, lp: 5000 });
    // ignition crack
    noiseBurst(ctx, dry, {
      noise: lib.noise.white, t, type: 'highpass', f0: 3000, q: 0.6,
      attack: 0.0005, decay: 0.02, peak: 0.6, rng,
    });
    // main blast
    const b = noiseBurst(ctx, dry, {
      noise: lib.noise.brown, t, type: 'lowpass', f0: 2600, f1: 90, q: 1.6,
      sweep: 0.5, attack: 0.004, decay: 0.75, peak: 1.0, drive: 10, rng,
    });
    if (b) b.gain.connect(tail);
    // sub punch
    const th = thump(ctx, dry, { t, f0: 95, f1: 20, dur: 0.85, glide: 0.45, peak: 1.0, type: 'sine', drive: 4 });
    th.gain.connect(tail);
    // rumble roll-off
    const rumB = crackleBuffer(ctx, 2.4, rng, { density: 55, fLo: 60, fHi: 700, amp: 0.8, decayLo: 0.02, decayHi: 0.18 });
    const rum = bufSrc(ctx, rumB, t + 0.05);
    const rg = gainNode(ctx, 0);
    ampEnv(rg.gain, { t: t + 0.05, peak: 0.55, attack: 0.08, decay: 2.1 });
    rum.connect(rg); rg.connect(dry); rg.connect(tail);
    // debris patter
    const deb = bufSrc(ctx, grainBuffer(ctx, 1.6, rng, { density: 220, amp: 0.5, skew: 0.6 }), t + 0.12);
    const df = filt(ctx, 'bandpass', 2600, 1.2);
    const dg = gainNode(ctx, 0);
    ampEnv(dg.gain, { t: t + 0.12, peak: 0.3, attack: 0.05, decay: 1.4 });
    deb.connect(df); df.connect(dg); dg.connect(dry);
  },
};

SFX.nuke_blast = {
  defer: true,
  dur: 4.5, gain: 1.0, send: 'boom', sendAmt: 0.45,
  build(ctx, out, rng, v, lib) {
    const t = 0.004;
    const dry = gainNode(ctx, 1); dry.connect(out);
    const tail = tailSend(ctx, out, lib.ir.cavern, 0.25, { hp: 60, lp: 4000 });
    // flash crack
    noiseBurst(ctx, dry, { noise: lib.noise.white, t, type: 'highpass', f0: 2200, q: 0.5, attack: 0.001, decay: 0.05, peak: 0.7, rng });
    // enormous blast
    const b = noiseBurst(ctx, dry, {
      noise: lib.noise.brown, t, type: 'lowpass', f0: 2200, f1: 55, q: 1.2,
      sweep: 1.1, attack: 0.006, decay: 1.6, peak: 1.0, drive: 12, rng,
    });
    if (b) b.gain.connect(tail);
    const th = thump(ctx, dry, { t, f0: 72, f1: 15, dur: 1.9, glide: 1.1, peak: 1.0, drive: 4 });
    th.gain.connect(tail);
    // long rolling thunder
    const rum = bufSrc(ctx, crackleBuffer(ctx, 4.2, rng, { density: 40, fLo: 40, fHi: 420, amp: 1.0, decayLo: 0.05, decayHi: 0.35 }), t + 0.1);
    const rlp = filt(ctx, 'lowpass', 420, 0.8);
    const rg = gainNode(ctx, 0);
    ampEnv(rg.gain, { t: t + 0.1, peak: 0.75, attack: 0.25, decay: 3.8, curve: 'lin' });
    rum.connect(rlp); rlp.connect(rg); rg.connect(dry); rg.connect(tail);
    // eerie descending whine after the blast (the "everything died" moment)
    const wh = osc(ctx, 'sine', 700);
    setAt(wh.frequency, 620, t + 0.2); expTo(wh.frequency, 90, t + 3.6);
    const wg = gainNode(ctx, 0);
    ampEnv(wg.gain, { t: t + 0.2, peak: 0.12, attack: 0.5, decay: 3.2, curve: 'lin' });
    wh.connect(wg); wg.connect(tail); wg.connect(dry);
    wh.start(t + 0.2); wh.stop(t + 4.2);
  },
};

SFX.dry_fire = {
  dur: 0.25, variants: 3, gain: 1.0, jitter: 60,
  build(ctx, out, rng, v, lib) {
    clack(ctx, out, { t: 0.002, freqs: [1450, 2700, 4100, 6200], dur: 0.035, peak: 0.55, noise: lib.noise.white, bright: 3000, rng });
    clack(ctx, out, { t: 0.026, freqs: [1100, 2100, 3300], dur: 0.03, peak: 0.28, noise: lib.noise.white, bright: 2400, rng });
    thump(ctx, out, { t: 0.002, f0: 240, f1: 110, dur: 0.045, peak: 0.18, type: 'triangle' });
  },
};





/*
 * The four old generic handling sounds (`reload_mag_out`, `reload_mag_in`,
 * `reload_bolt`, `reload_shell`) have been replaced by the per-class parts
 * further down and are kept working as aliases (see SFX_ALIASES).
 */
SFX.weapon_switch = {
  dur: 0.6, variants: 3, gain: 1.0, jitter: 50,
  build(ctx, out, rng, v, lib) {
    noiseBurst(ctx, out, { noise: lib.noise.pink, t: 0.002, type: 'bandpass', f0: 700, f1: 2200, q: 1.0, sweep: 0.12, attack: 0.02, decay: 0.16, peak: 0.28, rng });
    clack(ctx, out, { t: 0.13, freqs: [1400, 2600, 4000], dur: 0.04, peak: 0.35, noise: lib.noise.white, bright: 2600, rng });
    clack(ctx, out, { t: 0.2, freqs: [900, 1800, 2900], dur: 0.05, peak: 0.25, noise: lib.noise.white, bright: 2000, rng });
    // cloth/sling rustle
    noiseBurst(ctx, out, { noise: lib.noise.pink, t: 0.05, type: 'highpass', f0: 2800, q: 0.5, attack: 0.03, decay: 0.2, peak: 0.1, rng });
  },
};

SFX.knife_swing = {
  dur: 0.5, variants: 3, gain: 1.0, jitter: 80,
  build(ctx, out, rng, v, lib) {
    // whoosh: bandpass noise swept up then down, panned across
    const s = bufSrc(ctx, lib.noise.pink, 0, { loop: true, offset: rnd(rng, 0, 2) });
    const bp = filt(ctx, 'bandpass', 500, 1.6);
    setAt(bp.frequency, 380, 0);
    expTo(bp.frequency, rnd(rng, 1900, 2600), 0.09);
    expTo(bp.frequency, 420, 0.26);
    const g = gainNode(ctx, 0);
    ampEnv(g.gain, { t: 0, peak: 0.6, attack: 0.05, decay: 0.2, curve: 'lin' });
    const p = ctx.createStereoPanner();
    setAt(p.pan, rnd(rng, -0.8, -0.4), 0);
    linTo(p.pan, rnd(rng, 0.4, 0.8), 0.25);
    s.connect(bp); bp.connect(g); g.connect(p); p.connect(out);
    s.stop(0.4);
    // faint blade ring
    ping(ctx, out, { t: 0.02, freq: rnd(rng, 3400, 4600), dur: 0.22, peak: 0.05 });
  },
};

SFX.knife_hit = {
  dur: 0.9, variants: 3, gain: 1.0, jitter: 70,
  build(ctx, out, rng, v, lib) {
    // wet stab: squelch + bone crunch + blade ring
    noiseBurst(ctx, out, { noise: lib.noise.brown, t: 0.001, type: 'lowpass', f0: 1400, f1: 260, q: 2.4, sweep: 0.1, attack: 0.001, decay: 0.16, peak: 0.85, drive: 4, rng });
    noiseBurst(ctx, out, { noise: lib.noise.white, t: 0.004, type: 'bandpass', f0: rnd(rng, 1700, 2400), f1: 600, q: 1.6, sweep: 0.06, attack: 0.001, decay: 0.09, peak: 0.4, rng });
    thump(ctx, out, { t: 0.001, f0: 180, f1: 52, dur: 0.14, peak: 0.55, drive: 3 });
    // gristle
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.3, rng, { density: 260, amp: 0.6, skew: 0.5 }), 0.01);
    const gf = filt(ctx, 'bandpass', 900, 1.4);
    const gg = gainNode(ctx, 0);
    ampEnv(gg.gain, { t: 0.01, peak: 0.3, attack: 0.005, decay: 0.26 });
    gr.connect(gf); gf.connect(gg); gg.connect(out);
    ping(ctx, out, { t: 0.001, freq: rnd(rng, 3800, 5200), dur: 0.3, peak: 0.07, mod: 3.1, index: 0.5 });
  },
};

SFX.grenade_pin = {
  dur: 0.5, variants: 2, gain: 1.0, jitter: 60,
  build(ctx, out, rng, v, lib) {
    clack(ctx, out, { t: 0.002, freqs: [3400, 5100, 7200], dur: 0.02, peak: 0.35, noise: lib.noise.white, bright: 5000, rng });
    // ring scrape
    noiseBurst(ctx, out, { noise: lib.noise.white, t: 0.01, type: 'bandpass', f0: 4200, f1: 2600, q: 5, sweep: 0.06, attack: 0.003, decay: 0.07, peak: 0.25, rng });
    ping(ctx, out, { t: 0.06, freq: 5600, dur: 0.18, peak: 0.12, mod: 2.7, index: 0.6 });
    clack(ctx, out, { t: 0.09, freqs: [2200, 3900], dur: 0.03, peak: 0.2, rng });
  },
};

SFX.grenade_bounce = {
  dur: 0.5, variants: 3, gain: 1.0, jitter: 90, rateJit: 0.08,
  build(ctx, out, rng, v, lib) {
    const f = rnd(rng, 420, 620);
    thump(ctx, out, { t: 0.001, f0: f, f1: f * 0.5, dur: 0.05, peak: 0.6, type: 'triangle', drive: 3 });
    clack(ctx, out, { t: 0.001, freqs: [f * 3.2, f * 5.7, f * 8.1], dur: 0.05, peak: 0.3, noise: lib.noise.white, bright: 2600, rng });
    noiseBurst(ctx, out, { noise: lib.noise.pink, t: 0.001, type: 'bandpass', f0: 1200, q: 1.0, attack: 0.001, decay: 0.05, peak: 0.25, rng });
  },
};

/* ---------- feedback / UI ---------- */

SFX.hitmarker = {
  dur: 0.16, variants: 2, gain: 1.0, bus: 'ui', jitter: 25,
  build(ctx, out, rng, v, lib) {
    ping(ctx, out, { t: 0.0005, freq: 3100, dur: 0.045, peak: 0.6, type: 'triangle' });
    ping(ctx, out, { t: 0.0005, freq: 4650, dur: 0.03, peak: 0.3 });
    noiseBurst(ctx, out, { noise: lib.noise.white, t: 0, type: 'highpass', f0: 5200, q: 0.7, attack: 0.0004, decay: 0.012, peak: 0.45, rng });
  },
};

SFX.headshot = {
  dur: 0.8, variants: 3, gain: 1.0, bus: 'sfx', jitter: 50,
  build(ctx, out, rng, v, lib) {
    // the pop: fast resonant burst with a hard pitch drop, plus wet spray
    const bp = filt(ctx, 'bandpass', 900, 3.2);
    setAt(bp.frequency, rnd(rng, 1500, 2100), 0.001);
    expTo(bp.frequency, 190, 0.09);
    const s = bufSrc(ctx, lib.noise.white, 0, { loop: true, offset: rnd(rng, 0, 2) });
    const g = gainNode(ctx, 0);
    ampEnv(g.gain, { t: 0.001, peak: 1.0, attack: 0.0008, decay: 0.12 });
    const dist = shaper(ctx, satCurve(7));
    s.connect(bp); bp.connect(dist); dist.connect(g); g.connect(out);
    s.stop(0.3);
    thump(ctx, out, { t: 0.001, f0: 210, f1: 42, dur: 0.2, peak: 0.75, drive: 4 });
    // skull crunch
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.35, rng, { density: 300, amp: 0.7, skew: 0.45 }), 0.004);
    const gf = filt(ctx, 'bandpass', 1500, 1.1);
    const gg = gainNode(ctx, 0);
    ampEnv(gg.gain, { t: 0.004, peak: 0.45, attack: 0.002, decay: 0.3 });
    gr.connect(gf); gf.connect(gg); gg.connect(out);
    // wet spray tail
    noiseBurst(ctx, out, { noise: lib.noise.pink, t: 0.02, type: 'bandpass', f0: 2600, f1: 700, q: 0.9, sweep: 0.3, attack: 0.01, decay: 0.34, peak: 0.16, rng });
    // ui confirmation ping riding on top
    ping(ctx, out, { t: 0.0005, freq: 2450, dur: 0.06, peak: 0.25, type: 'triangle' });
  },
};

SFX.flesh_hit = {
  dur: 0.45, variants: 3, gain: 1.0, jitter: 90, rateJit: 0.07,
  build(ctx, out, rng, v, lib) {
    noiseBurst(ctx, out, { noise: lib.noise.brown, t: 0.001, type: 'lowpass', f0: rnd(rng, 900, 1500), f1: 200, q: 2.6, sweep: 0.08, attack: 0.0008, decay: 0.12, peak: 0.9, drive: 4, rng });
    thump(ctx, out, { t: 0.001, f0: rnd(rng, 150, 200), f1: 45, dur: 0.12, peak: 0.6, drive: 3 });
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.25, rng, { density: 200, amp: 0.55, skew: 0.5 }), 0.003);
    const gf = filt(ctx, 'bandpass', rnd(rng, 700, 1200), 1.3);
    const gg = gainNode(ctx, 0);
    ampEnv(gg.gain, { t: 0.003, peak: 0.35, attack: 0.002, decay: 0.2 });
    gr.connect(gf); gf.connect(gg); gg.connect(out);
  },
};

// `bullet_impact_wall` lives on as an alias of `impact_concrete` (below), which
// is the same idea with the rest of the surfaces alongside it.

SFX.player_hurt = {
  dur: 1.2, variants: 3, gain: 1.0, jitter: 40,
  build(ctx, out, rng, v, lib) {
    // impact + a male grunt (formant synthesis, short and pained)
    thump(ctx, out, { t: 0.001, f0: 190, f1: 50, dur: 0.18, peak: 0.8, drive: 4 });
    noiseBurst(ctx, out, { noise: lib.noise.brown, t: 0.001, type: 'lowpass', f0: 1100, f1: 240, q: 1.8, sweep: 0.1, attack: 0.001, decay: 0.16, peak: 0.6, drive: 4, rng });
    zombieVoice(ctx, out, lib, rng, {
      t: 0.02, dur: 0.42, f0a: rnd(rng, 118, 140), f0b: rnd(rng, 86, 100),
      vowel: 'a', vowel2: 'uh', morphAt: 0.4, jitter: 0.018, shimmer: 0.1, rough: 0,
      breath: 0.3, growl: 0, drive: 3, peak: 0.55, attack: 0.02, release: 0.22, air: 0.12,
    });
    // heartbeat thud of adrenaline
    thump(ctx, out, { t: 0.28, f0: 70, f1: 34, dur: 0.3, peak: 0.25 });
  },
};

SFX.player_down = {
  defer: true,
  dur: 3.4, gain: 1.0,
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 3.2, damp: 2600, preDelay: 0.02 });
    rev.output.connect(out);
    // body hits the ground
    thump(ctx, out, { t: 0.002, f0: 120, f1: 28, dur: 0.45, peak: 1.0, drive: 4 });
    noiseBurst(ctx, out, { noise: lib.noise.brown, t: 0.002, type: 'lowpass', f0: 800, f1: 140, q: 1.5, sweep: 0.2, attack: 0.002, decay: 0.35, peak: 0.6, rng });
    // long agonised groan
    const gv = zombieVoice(ctx, out, lib, rng, {
      t: 0.05, dur: 1.5, f0a: 132, f0b: 62, vowel: 'a', vowel2: 'o', morphAt: 0.3, morphDur: 0.6,
      jitter: 0.03, shimmer: 0.2, rough: 0.12, breath: 0.35, drive: 3.5,
      peak: 0.6, attack: 0.05, release: 0.8, air: 0.14, rattle: 0.12,
    });
    gv.out.connect(rev.input);
    // world goes muffled: a descending filtered drone
    const d = osc(ctx, 'sawtooth', 180);
    setAt(d.frequency, 165, 0.1); expTo(d.frequency, 42, 3.0);
    const dl = filt(ctx, 'lowpass', 600, 3);
    setAt(dl.frequency, 900, 0.1); expTo(dl.frequency, 130, 3.0);
    const dg = gainNode(ctx, 0);
    ampEnv(dg.gain, { t: 0.1, peak: 0.28, attack: 0.3, decay: 2.8, curve: 'lin' });
    d.connect(dl); dl.connect(dg); dg.connect(out); dg.connect(rev.input);
    d.start(0.1); d.stop(3.3);
    // tinnitus
    const tin = osc(ctx, 'sine', 4300);
    const tg = gainNode(ctx, 0);
    ampEnv(tg.gain, { t: 0.1, peak: 0.06, attack: 0.15, decay: 3.0, curve: 'lin' });
    tin.connect(tg); tg.connect(out);
    tin.start(0.1); tin.stop(3.3);
  },
};

SFX.heartbeat_loop = {
  dur: 0.8, xfade: 0.12, loop: true, gain: 1.0, level: -20,
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 0.6, damp: 900, preDelay: 0.008, gain: 0.35 });
    rev.output.connect(out);
    const beat = (t, amp, f0, f1, dur) => {
      const th = thump(ctx, out, { t, f0, f1, dur, glide: dur * 0.5, peak: amp, type: 'sine', drive: 2.5 });
      th.gain.connect(rev.input);
      // valve slap / muscle thud texture
      noiseBurst(ctx, out, { noise: lib.noise.brown, t, type: 'lowpass', f0: 240, f1: 70, q: 1.6, sweep: dur * 0.6, attack: 0.004, decay: dur * 0.8, peak: amp * 0.45, rng });
    };
    beat(0.0, 1.0, 78, 34, 0.18);        // lub
    beat(0.235, 0.62, 66, 30, 0.22);     // dub
    // faint blood-rush wash
    noiseBurst(ctx, out, { noise: lib.noise.brown, t: 0, type: 'lowpass', f0: 180, q: 0.8, attack: 0.12, decay: 0.7, peak: 0.07, curve: 'lin', rng });
  },
};

/* ---------- zombies ---------- */

const GROAN_PRESETS = [
  { f0a: 86, f0b: 62, vowel: 'a', vowel2: 'o', dur: 1.9, rough: 0.4, growl: 0.2 },
  { f0a: 74, f0b: 88, vowel: 'uh', vowel2: 'a', dur: 1.6, rough: 0.3, growl: 0.25 },
  { f0a: 96, f0b: 70, vowel: 'o', vowel2: 'u', dur: 2.2, rough: 0.45, growl: 0.18 },
  { f0a: 68, f0b: 58, vowel: 'u', vowel2: 'a', dur: 2.4, rough: 0.5, growl: 0.3 },
  { f0a: 108, f0b: 78, vowel: 'ae', vowel2: 'uh', dur: 1.4, rough: 0.28, growl: 0.16 },
];

SFX.zombie_groan = {
  dur: 2.7, variants: 5, gain: 1.0, jitter: 130, rateJit: 0.07,
  build(ctx, out, rng, v, lib) {
    const p = GROAN_PRESETS[v % GROAN_PRESETS.length];
    const rev = makeReverb(ctx, { decay: 1.4, damp: 2200, preDelay: 0.012, gain: 0.3 });
    rev.output.connect(out);
    const vo = zombieVoice(ctx, out, lib, rng, {
      t: 0.02, dur: p.dur, f0a: p.f0a * (1 + jit(rng, 0.06)), f0b: p.f0b * (1 + jit(rng, 0.06)),
      vowel: p.vowel, vowel2: p.vowel2, morphAt: 0.3, morphDur: 0.55,
      fscale: rnd(rng, 0.9, 1.08), jitter: 0.05, shimmer: 0.3, rough: p.rough,
      breath: 0.18, growl: p.growl, drive: 4, postLp: 3600,
      peak: 0.75, attack: p.dur * 0.22, release: p.dur * 0.45,
      rattle: 0.1, rattleF: rnd(rng, 500, 800), air: 0.07,
      wobble: rnd(rng, 0.05, 0.1),
    });
    vo.out.connect(rev.input);
    // a dry rasping in-breath at the end — deeply unpleasant, very good
    if (v % 2 === 0) {
      noiseBurst(ctx, out, {
        noise: lib.noise.pink, t: p.dur * 0.92, type: 'bandpass', f0: 620, f1: 1400,
        q: 1.6, sweep: 0.28, attack: 0.1, decay: 0.3, peak: 0.16, curve: 'lin', rng,
      });
    }
  },
};

SFX.zombie_scream = {
  dur: 1.75, variants: 3, gain: 1.0, jitter: 120, rateJit: 0.06,
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 1.8, damp: 3000, preDelay: 0.01, gain: 0.35 });
    rev.output.connect(out);
    const dur = rnd(rng, 1.15, 1.45);
    const vo = zombieVoice(ctx, out, lib, rng, {
      t: 0.01, dur,
      f0a: rnd(rng, 150, 190), f0b: rnd(rng, 300, 380),
      curve: (p) => Math.pow(p, 0.55),
      vowel: 'ae', vowel2: 'i', morphAt: 0.25, morphDur: 0.4, fscale: 1.12,
      jitter: 0.06, shimmer: 0.35, rough: 0.18, breath: 0.22,
      growl: 0.1, drive: 9, postLp: 6500, direct: 0.45,
      peak: 0.9, attack: 0.05, release: dur * 0.3, air: 0.12,
      wobble: 0.09, bwScale: 1.3,
    });
    vo.out.connect(rev.input);
    // screech harmonics on top (the part that makes you turn around)
    for (let i = 0; i < 3; i++) {
      const o1 = osc(ctx, 'sawtooth', 1200);
      const f0 = rnd(rng, 900, 1500) * (1 + i * 0.6);
      setAt(o1.frequency, f0, 0.02);
      expTo(o1.frequency, f0 * rnd(rng, 1.6, 2.3), 0.02 + dur * 0.7);
      const bp = filt(ctx, 'bandpass', f0 * 1.5, 7);
      const g = gainNode(ctx, 0);
      ampEnv(g.gain, { t: 0.02 + i * 0.01, peak: 0.1 / (i + 1), attack: 0.08, decay: dur * 0.85, curve: 'lin' });
      o1.connect(bp); bp.connect(g); g.connect(out); g.connect(rev.input);
      o1.start(0.02); o1.stop(dur + 0.2);
    }
  },
};

SFX.zombie_attack = {
  dur: 1.0, variants: 3, gain: 1.0, jitter: 130, rateJit: 0.08,
  build(ctx, out, rng, v, lib) {
    const dur = rnd(rng, 0.42, 0.62);
    zombieVoice(ctx, out, lib, rng, {
      t: 0.005, dur,
      f0a: rnd(rng, 95, 125), f0b: rnd(rng, 135, 185),
      curve: (p) => Math.pow(p, 0.7),
      vowel: 'a', vowel2: 'ae', morphAt: 0.2, morphDur: 0.35,
      jitter: 0.07, shimmer: 0.35, rough: 0.45, breath: 0.2,
      growl: 0.35, drive: 8, postLp: 5200, direct: 0.42,
      peak: 0.95, attack: 0.012, release: dur * 0.45, air: 0.1, wobble: 0.1,
    });
    // arm swipe through the air
    const s = bufSrc(ctx, lib.noise.pink, 0.02, { loop: true, offset: rnd(rng, 0, 2) });
    const bp = filt(ctx, 'bandpass', 500, 1.4);
    setAt(bp.frequency, 340, 0.02); expTo(bp.frequency, 1500, 0.14); expTo(bp.frequency, 400, 0.3);
    const g = gainNode(ctx, 0);
    ampEnv(g.gain, { t: 0.02, peak: 0.22, attack: 0.07, decay: 0.2, curve: 'lin' });
    s.connect(bp); bp.connect(g); g.connect(out);
    s.stop(0.4);
  },
};

SFX.zombie_death = {
  dur: 2.5, variants: 3, gain: 1.0, jitter: 120, rateJit: 0.07,
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 1.5, damp: 2000, preDelay: 0.012, gain: 0.3 });
    rev.output.connect(out);
    const dur = rnd(rng, 1.3, 1.8);
    const vo = zombieVoice(ctx, out, lib, rng, {
      t: 0.005, dur,
      f0a: rnd(rng, 110, 145), f0b: rnd(rng, 42, 58),
      curve: (p) => Math.pow(p, 0.75),
      vowel: 'a', vowel2: 'u', morphAt: 0.18, morphDur: 0.6,
      jitter: 0.07, shimmer: 0.4, rough: 0.55, breath: 0.3,
      growl: 0.3, drive: 6, postLp: 3200,
      peak: 0.85, attack: 0.02, release: dur * 0.6,
      rattle: 0.3, rattleDensity: 160, rattleF: rnd(rng, 420, 700), air: 0.12,
      wobble: 0.13,
    });
    vo.out.connect(rev.input);
    // body collapses
    const tCol = dur * 0.75;
    thump(ctx, out, { t: tCol, f0: 105, f1: 30, dur: 0.35, peak: 0.55, drive: 3 });
    noiseBurst(ctx, out, { noise: lib.noise.brown, t: tCol, type: 'lowpass', f0: 700, f1: 140, q: 1.4, sweep: 0.2, attack: 0.003, decay: 0.3, peak: 0.35, rng });
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.5, rng, { density: 220, amp: 0.5, skew: 0.5 }), tCol);
    const gf = filt(ctx, 'bandpass', 1400, 1.1);
    const gg = gainNode(ctx, 0);
    ampEnv(gg.gain, { t: tCol, peak: 0.2, attack: 0.01, decay: 0.42 });
    gr.connect(gf); gf.connect(gg); gg.connect(out);
  },
};

SFX.zombie_rise_dirt = {
  dur: 2.35, variants: 2, gain: 1.0, jitter: 80,
  build(ctx, out, rng, v, lib) {
    // earth shifting, then a burst of dirt and stones, then a gasp
    const rumble = osc(ctx, 'sine', 48);
    setAt(rumble.frequency, 42, 0); expTo(rumble.frequency, 26, 1.4);
    const rg = gainNode(ctx, 0);
    ampEnv(rg.gain, { t: 0, peak: 0.5, attack: 0.3, decay: 1.1, curve: 'lin' });
    rumble.connect(rg); rg.connect(out);
    rumble.start(0); rumble.stop(1.6);

    const dirt = bufSrc(ctx, grainBuffer(ctx, 1.8, rng, { density: 900, amp: 0.85, skew: 0.75 }), 0.02);
    const dl = filt(ctx, 'lowpass', 2600, 0.8);
    const dhp = filt(ctx, 'highpass', 160, 0.7);
    const dg = gainNode(ctx, 0);
    setAt(dg.gain, 1e-4, 0);
    expTo(dg.gain, 0.5, 0.35);
    setAt(dg.gain, 0.5, 0.6);
    expTo(dg.gain, 0.9, 0.85);   // the burst as the hands break through
    expTo(dg.gain, 0.06, 1.7);
    dirt.connect(dl); dl.connect(dhp); dhp.connect(dg); dg.connect(out);

    // stones clattering
    for (let i = 0; i < 9; i++) {
      const t = rnd(rng, 0.6, 1.6);
      clack(ctx, out, { t, freqs: [rnd(rng, 900, 2400), rnd(rng, 2600, 4800)], dur: rnd(rng, 0.02, 0.06), peak: rnd(rng, 0.06, 0.2), noise: lib.noise.white, bright: 2800, rng });
    }
    // the gasp as it breaks the surface
    zombieVoice(ctx, out, lib, rng, {
      t: 0.95, dur: 1.1, f0a: rnd(rng, 78, 98), f0b: rnd(rng, 60, 72),
      vowel: 'a', vowel2: 'uh', morphAt: 0.35, jitter: 0.06, shimmer: 0.3, rough: 0.4,
      breath: 0.4, growl: 0.22, drive: 5, peak: 0.6, attack: 0.1, release: 0.5,
      rattle: 0.14, air: 0.14,
    });
  },
};

/* ---------- barricades ---------- */

/** Wood resonance modes — used by every board sound. */
function woodModes(ctx, out, rng, t, amp, decay, base) {
  const modes = [1.0, 1.72, 2.61, 3.9, 5.3, 7.1];
  for (let i = 0; i < modes.length; i++) {
    ping(ctx, out, {
      t, freq: base * modes[i] * (1 + jit(rng, 0.03)),
      dur: decay * (1 - i * 0.11), peak: amp * (0.9 - i * 0.13),
      type: i < 2 ? 'triangle' : 'sine',
      pan: jit(rng, 0.3),
    });
  }
}

SFX.board_tear = {
  dur: 1.25, variants: 3, gain: 1.0, jitter: 90, rateJit: 0.06,
  build(ctx, out, rng, v, lib) {
    // nails shrieking out of wood, then a crack and a splintering rip
    const o1 = osc(ctx, 'sawtooth', 600);
    const f0 = rnd(rng, 450, 700);
    setAt(o1.frequency, f0, 0.005);
    expTo(o1.frequency, f0 * rnd(rng, 1.5, 2.4), 0.32);
    const vib = osc(ctx, 'sine', rnd(rng, 26, 48));
    const vg = gainNode(ctx, rnd(rng, 90, 220));
    vib.connect(vg); vg.connect(o1.detune);
    vib.start(0); vib.stop(0.5);
    const bp = filt(ctx, 'bandpass', 1400, 4.5);
    setAt(bp.frequency, 1100, 0.005); expTo(bp.frequency, 2600, 0.3);
    const g = gainNode(ctx, 0);
    ampEnv(g.gain, { t: 0.005, peak: 0.35, attack: 0.02, decay: 0.32, curve: 'lin' });
    o1.connect(bp); bp.connect(g); g.connect(out);
    o1.start(0.005); o1.stop(0.4);

    // splinter rip
    const rip = bufSrc(ctx, grainBuffer(ctx, 0.45, rng, { density: 700, amp: 0.8, skew: 0.9 }), 0.22);
    const rf = filt(ctx, 'bandpass', 2200, 0.9);
    const rg2 = gainNode(ctx, 0);
    ampEnv(rg2.gain, { t: 0.22, peak: 0.6, attack: 0.02, decay: 0.32 });
    rip.connect(rf); rf.connect(rg2); rg2.connect(out);

    // the CRACK
    const tc = 0.3 + rnd(rng, 0, 0.06);
    noiseBurst(ctx, out, { noise: lib.noise.white, t: tc, type: 'bandpass', f0: 2400, f1: 500, q: 1.1, sweep: 0.05, attack: 0.0008, decay: 0.09, peak: 0.85, drive: 5, rng });
    woodModes(ctx, out, rng, tc, 0.28, 0.32, rnd(rng, 200, 280));
    thump(ctx, out, { t: tc, f0: 190, f1: 60, dur: 0.14, peak: 0.4, type: 'triangle', drive: 3 });
    // debris
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.6, rng, { density: 160, amp: 0.5, skew: 0.5 }), tc + 0.05);
    const gf = filt(ctx, 'highpass', 1400, 0.7);
    const gg = gainNode(ctx, 0);
    ampEnv(gg.gain, { t: tc + 0.05, peak: 0.2, attack: 0.02, decay: 0.5 });
    gr.connect(gf); gf.connect(gg); gg.connect(out);
  },
};

SFX.board_repair = {
  dur: 1.45, variants: 2, gain: 1.0, jitter: 70,
  build(ctx, out, rng, v, lib) {
    // board laid on, then three hammer strikes
    noiseBurst(ctx, out, { noise: lib.noise.pink, t: 0.002, type: 'bandpass', f0: 900, f1: 2000, q: 1.0, sweep: 0.12, attack: 0.01, decay: 0.16, peak: 0.28, rng });
    woodModes(ctx, out, rng, 0.14, 0.2, 0.22, rnd(rng, 210, 270));
    let t = 0.3;
    for (let i = 0; i < 3; i++) {
      const base = rnd(rng, 220, 300);
      clack(ctx, out, { t, freqs: [base * 6, base * 11, base * 17], dur: 0.03, peak: 0.45, noise: lib.noise.white, bright: 3200, rng });
      woodModes(ctx, out, rng, t, 0.3, 0.2, base);
      thump(ctx, out, { t, f0: 260, f1: 85, dur: 0.1, peak: 0.45, type: 'triangle', drive: 3 });
      t += rnd(rng, 0.2, 0.3);
    }
  },
};

SFX.board_slam = {
  dur: 1.0, variants: 3, gain: 1.0, jitter: 70,
  build(ctx, out, rng, v, lib) {
    thump(ctx, out, { t: 0.001, f0: 150, f1: 42, dur: 0.24, peak: 0.95, type: 'triangle', drive: 4 });
    noiseBurst(ctx, out, { noise: lib.noise.brown, t: 0.001, type: 'lowpass', f0: 1600, f1: 220, q: 1.6, sweep: 0.12, attack: 0.001, decay: 0.2, peak: 0.7, drive: 4, rng });
    woodModes(ctx, out, rng, 0.001, 0.4, 0.38, rnd(rng, 180, 240));
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.5, rng, { density: 140, amp: 0.4, skew: 0.5 }), 0.02);
    const gf = filt(ctx, 'highpass', 1600, 0.7);
    const gg = gainNode(ctx, 0);
    ampEnv(gg.gain, { t: 0.02, peak: 0.15, attack: 0.01, decay: 0.42 });
    gr.connect(gf); gf.connect(gg); gg.connect(out);
  },
};

/* ---------- economy / interaction ---------- */

SFX.purchase = {
  dur: 1.4, gain: 1.0, bus: 'ui',
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 1.1, damp: 6000, preDelay: 0.008, gain: 0.3 });
    rev.output.connect(out);
    // cash register: mechanism clunk, then a bright two-bell cha-CHING
    clack(ctx, out, { t: 0.002, freqs: [900, 1700, 2600], dur: 0.04, peak: 0.3, noise: lib.noise.white, bright: 2200, rng });
    const ch = (t, f, amp, dur) => {
      const b = bell(ctx, out, {
        t, freq: f, dur, peak: amp,
        partials: [[1, 1, 1], [2.76, 0.7, 0.72], [5.4, 0.45, 0.5], [8.93, 0.3, 0.34], [13.3, 0.18, 0.22]],
        stretch: 0.002, pan: jit(rng, 0.2),
      });
      b.out.connect(rev.input);
    };
    ch(0.02, 1046, 0.35, 0.9);          // C6
    ch(0.085, 1568, 0.32, 1.0);         // G6
    // drawer slide
    noiseBurst(ctx, out, { noise: lib.noise.pink, t: 0.1, type: 'bandpass', f0: 1200, f1: 480, q: 1.2, sweep: 0.2, attack: 0.02, decay: 0.24, peak: 0.16, rng });
    clack(ctx, out, { t: 0.33, freqs: [640, 1180, 1900], dur: 0.05, peak: 0.2, noise: lib.noise.white, bright: 1600, rng });
  },
};

SFX.purchase_deny = {
  dur: 0.7, gain: 1.0, bus: 'ui',
  build(ctx, out, rng, v, lib) {
    const buzz = (t, dur) => {
      const o1 = osc(ctx, 'square', 108);
      const o2 = osc(ctx, 'sawtooth', 109.7);
      const bp = filt(ctx, 'bandpass', 420, 2.2);
      const dist = shaper(ctx, satCurve(9));
      const g = gainNode(ctx, 0);
      // gate it at 34 Hz so it rasps like a broken buzzer
      const gate = osc(ctx, 'square', 34);
      const gg = gainNode(ctx, 0.35);
      gate.connect(gg); gg.connect(g.gain);
      gate.start(t); gate.stop(t + dur + 0.05);
      ampEnv(g.gain, { t, peak: 0.55, attack: 0.004, decay: dur, curve: 'lin' });
      o1.connect(bp); o2.connect(bp); bp.connect(dist); dist.connect(g); g.connect(out);
      o1.start(t); o1.stop(t + dur + 0.05);
      o2.start(t); o2.stop(t + dur + 0.05);
    };
    buzz(0.002, 0.13);
    buzz(0.19, 0.2);
  },
};

SFX.door_open = {
  defer: true,
  dur: 2.5, variants: 2, gain: 1.0, jitter: 50,
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 1.4, damp: 3000, gain: 0.3 });
    rev.output.connect(out);
    // debris shoved aside
    const gr = bufSrc(ctx, grainBuffer(ctx, 1.4, rng, { density: 420, amp: 0.7, skew: 0.8 }), 0.01);
    const gf = filt(ctx, 'bandpass', 1400, 0.8);
    const gg = gainNode(ctx, 0);
    ampEnv(gg.gain, { t: 0.01, peak: 0.5, attack: 0.1, decay: 1.2, curve: 'lin' });
    gr.connect(gf); gf.connect(gg); gg.connect(out); gg.connect(rev.input);
    // hinge creak: friction-modulated resonant sweep
    const cr = osc(ctx, 'sawtooth', 300);
    setAt(cr.frequency, rnd(rng, 230, 330), 0.15);
    expTo(cr.frequency, rnd(rng, 520, 760), 1.1);
    const crMod = osc(ctx, 'sine', 11);
    const crMg = gainNode(ctx, 240);
    crMod.connect(crMg); crMg.connect(cr.detune);
    crMod.start(0); crMod.stop(1.4);
    const cbp = filt(ctx, 'bandpass', 1100, 6);
    setAt(cbp.frequency, 900, 0.15); expTo(cbp.frequency, 2200, 1.0);
    const cg = gainNode(ctx, 0);
    ampEnv(cg.gain, { t: 0.15, peak: 0.3, attack: 0.2, decay: 0.85, curve: 'lin' });
    cr.connect(cbp); cbp.connect(cg); cg.connect(out); cg.connect(rev.input);
    cr.start(0.15); cr.stop(1.3);
    // heavy wooden thud at the end
    thump(ctx, out, { t: 1.15, f0: 130, f1: 38, dur: 0.35, peak: 0.8, type: 'triangle', drive: 4 });
    noiseBurst(ctx, out, { noise: lib.noise.brown, t: 1.15, type: 'lowpass', f0: 1200, f1: 180, q: 1.5, sweep: 0.15, attack: 0.002, decay: 0.28, peak: 0.5, rng });
    woodModes(ctx, out, rng, 1.15, 0.22, 0.4, 170);
  },
};

/* ---------- mystery box ---------- */

SFX.box_open = {
  defer: true,
  dur: 2.0, gain: 1.0,
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 2.0, damp: 4000, gain: 0.35 });
    rev.output.connect(out);
    // chains rattle
    for (let i = 0; i < 12; i++) {
      clack(ctx, out, { t: rnd(rng, 0, 0.35), freqs: [rnd(rng, 3200, 6400), rnd(rng, 6400, 10000)], dur: 0.02, peak: rnd(rng, 0.05, 0.16), noise: lib.noise.white, bright: 6000, rng });
    }
    // lid creaks open
    clack(ctx, out, { t: 0.04, freqs: [820, 1500, 2400], dur: 0.05, peak: 0.4, noise: lib.noise.white, bright: 2200, rng });
    const cr = osc(ctx, 'sawtooth', 380);
    setAt(cr.frequency, 340, 0.12); expTo(cr.frequency, 640, 0.75);
    const cbp = filt(ctx, 'bandpass', 1300, 7);
    setAt(cbp.frequency, 1100, 0.12); expTo(cbp.frequency, 2400, 0.7);
    const cg = gainNode(ctx, 0);
    ampEnv(cg.gain, { t: 0.12, peak: 0.22, attack: 0.15, decay: 0.6, curve: 'lin' });
    cr.connect(cbp); cbp.connect(cg); cg.connect(out); cg.connect(rev.input);
    cr.start(0.12); cr.stop(0.9);
    // otherworldly light pours out
    for (let i = 0; i < 6; i++) {
      const p = ping(ctx, out, {
        t: 0.25 + i * 0.05, freq: nf('A5') * Math.pow(2, i / 12 * 2), dur: 1.2,
        peak: 0.1, mod: 2.02, index: 0.6, pan: jit(rng, 0.7),
      });
      p.out.connect(rev.input);
    }
    noiseBurst(ctx, out, { noise: lib.noise.white, t: 0.2, type: 'bandpass', f0: 900, f1: 7000, q: 0.8, sweep: 0.7, attack: 0.25, decay: 0.7, peak: 0.12, curve: 'lin', rng });
  },
};

SFX.box_close = {
  defer: true,
  dur: 1.6, gain: 1.0,
  build(ctx, out, rng, v, lib) {
    thump(ctx, out, { t: 0.002, f0: 145, f1: 38, dur: 0.3, peak: 0.9, type: 'triangle', drive: 4 });
    noiseBurst(ctx, out, { noise: lib.noise.brown, t: 0.002, type: 'lowpass', f0: 1500, f1: 200, q: 1.5, sweep: 0.12, attack: 0.001, decay: 0.24, peak: 0.65, drive: 4, rng });
    woodModes(ctx, out, rng, 0.002, 0.35, 0.34, 190);
    for (let i = 0; i < 10; i++) {
      clack(ctx, out, { t: 0.02 + rnd(rng, 0, 0.4), freqs: [rnd(rng, 3000, 6000), rnd(rng, 6000, 9500)], dur: 0.018, peak: rnd(rng, 0.04, 0.14), noise: lib.noise.white, bright: 6000, rng });
    }
  },
};

SFX.box_music = {
  defer: true,
  dur: 5.1, gain: 1.0, bus: 'music',
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 2.6, damp: 6500, preDelay: 0.015, gain: 0.45 });
    rev.output.connect(out);
    // A creepy music-box waltz in A harmonic minor — comb-tine timbre:
    // bright inharmonic partials, fast attack, medium decay, slightly out of tune.
    const bpm = 96;
    const beat = 60 / bpm;
    const tine = (t, midi, amp) => {
      const f = mtof(midi) * (1 + jit(rng, 0.004));   // the mechanism is old
      const b = bell(ctx, out, {
        t, freq: f, dur: 1.5, peak: amp,
        partials: [[1, 1, 1], [2.02, 0.5, 0.6], [3.05, 0.34, 0.42], [4.13, 0.22, 0.3], [5.9, 0.14, 0.2], [7.4, 0.08, 0.13]],
        stretch: 0.004, pan: jit(rng, 0.25),
      });
      b.out.connect(rev.input);
      // mechanism tick
      if (rng() < 0.7) {
        clack(ctx, out, { t: t - 0.004, freqs: [5200, 8100], dur: 0.008, peak: 0.035, rng });
      }
    };
    // melody (A harmonic minor: A B C D E F G#) — deliberately childlike then wrong
    const mel = [
      [0, 81, 1], [1, 84, 0.85], [2, 83, 0.8], [3, 81, 0.75],
      [4, 80, 0.9], [5, 81, 0.7], [6, 76, 0.85], [8, 81, 1],
      [9, 88, 0.9], [10, 87, 0.8], [11, 85, 0.75],
      [12, 84, 0.9], [13, 83, 0.7], [14, 80, 0.85], [15, 81, 0.95],
      [16, 79, 0.8], [17, 80, 0.7], [18, 76, 0.9],
    ];
    for (const [b, m, a] of mel) tine(0.05 + b * beat * 0.5, m, a * 0.26);
    // waltz accompaniment: low tine + two soft chord tines
    const bass = [69, 65, 64, 69];
    for (let bar = 0; bar < 4; bar++) {
      const t0 = 0.05 + bar * beat * 1.5;
      tine(t0, bass[bar] - 12, 0.2);
      tine(t0 + beat * 0.5, bass[bar] + 3, 0.09);
      tine(t0 + beat * 1.0, bass[bar] + 7, 0.08);
    }
    // the mechanism winding down at the end — the classic unnerving touch
    tine(4.3, 81, 0.22);
    tine(4.62, 80, 0.16);
    tine(5.0, 68, 0.14);
    // continuous spring-and-cylinder noise
    const mech = bufSrc(ctx, grainBuffer(ctx, 5.2, rng, { density: 55, amp: 0.25 }), 0);
    const mf = filt(ctx, 'highpass', 3600, 0.7);
    const mg = gainNode(ctx, 0.1);
    mech.connect(mf); mf.connect(mg); mg.connect(out);
  },
};

SFX.box_teddy = {
  defer: true,
  dur: 3.0, gain: 1.0,
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 2.4, damp: 4000, gain: 0.4 });
    rev.output.connect(out);
    // a child's laugh, pitched and processed until it is wrong
    const laughAt = (t, f0, dur) => {
      const vo = zombieVoice(ctx, out, lib, rng, {
        t, dur, f0a: f0, f0b: f0 * 0.9, vowel: 'a', vowel2: 'uh', morphAt: 0.5,
        fscale: 1.45, jitter: 0.02, shimmer: 0.12, rough: 0, breath: 0.12,
        growl: 0, drive: 2.5, peak: 0.55, attack: 0.02, release: dur * 0.5,
        air: 0.05, wobble: 0.04, direct: 0.15,
      });
      vo.out.connect(rev.input);
    };
    let t = 0.02;
    const f0 = rnd(rng, 300, 350);
    for (let i = 0; i < 6; i++) {
      laughAt(t, f0 * Math.pow(0.94, i) * (1 + jit(rng, 0.03)), rnd(rng, 0.1, 0.16));
      t += rnd(rng, 0.16, 0.22);
    }
    // descending "bye bye" glissando on a toy-ish tone
    for (let i = 0; i < 8; i++) {
      const p = ping(ctx, out, {
        t: 1.4 + i * 0.075, freq: mtof(88 - i * 2), dur: 0.5,
        peak: 0.12, mod: 2.4, index: 0.8, pan: jit(rng, 0.6),
      });
      p.out.connect(rev.input);
    }
    // whoosh as it flies away
    const s = bufSrc(ctx, lib.noise.pink, 1.35, { loop: true, offset: rnd(rng, 0, 2) });
    const bp = filt(ctx, 'bandpass', 600, 1.2);
    setAt(bp.frequency, 2600, 1.35); expTo(bp.frequency, 260, 2.5);
    const g = gainNode(ctx, 0);
    ampEnv(g.gain, { t: 1.35, peak: 0.45, attack: 0.1, decay: 1.1, curve: 'lin' });
    const p = ctx.createStereoPanner();
    setAt(p.pan, 0, 1.35); linTo(p.pan, rnd(rng, -0.9, 0.9), 2.4);
    s.connect(bp); bp.connect(g); g.connect(p); p.connect(out); g.connect(rev.input);
    s.stop(2.6);
  },
};

/* ---------- perks ---------- */

SFX.perk_drink = {
  defer: true,
  dur: 2.1, variants: 2, gain: 1.0, jitter: 60,
  build(ctx, out, rng, v, lib) {
    // bottle cap, then 4 glugs, then a satisfied exhale
    clack(ctx, out, { t: 0.002, freqs: [3800, 6200, 8800], dur: 0.02, peak: 0.3, noise: lib.noise.white, bright: 6000, rng });
    noiseBurst(ctx, out, { noise: lib.noise.white, t: 0.02, type: 'highpass', f0: 5000, q: 0.6, attack: 0.005, decay: 0.2, peak: 0.16, rng });
    let t = 0.3;
    for (let i = 0; i < 4; i++) {
      const f = rnd(rng, 260, 420) * (1 - i * 0.07);
      // a glug is a fast resonant blip with a downward pitch snap
      const o1 = osc(ctx, 'sine', f);
      setAt(o1.frequency, f * 2.1, t); expTo(o1.frequency, f * 0.75, t + 0.07);
      const g = gainNode(ctx, 0);
      ampEnv(g.gain, { t, peak: 0.5, attack: 0.004, decay: 0.1 });
      o1.connect(g); g.connect(out);
      o1.start(t); o1.stop(t + 0.16);
      noiseBurst(ctx, out, { noise: lib.noise.pink, t, type: 'bandpass', f0: f * 6, f1: f * 2, q: 1.6, sweep: 0.06, attack: 0.003, decay: 0.08, peak: 0.2, rng });
      t += rnd(rng, 0.19, 0.26);
    }
    // exhale
    noiseBurst(ctx, out, { noise: lib.noise.pink, t: t + 0.05, type: 'bandpass', f0: 800, f1: 400, q: 0.9, sweep: 0.35, attack: 0.06, decay: 0.4, peak: 0.22, rng });
  },
};

SFX.perk_burp = {
  defer: true,
  dur: 1.2, variants: 3, gain: 1.0, jitter: 110, rateJit: 0.1,
  build(ctx, out, rng, v, lib) {
    const dur = rnd(rng, 0.45, 0.72);
    // a burp is a very low, very rough glottal buzz through a big open vowel
    const src = glottalBuffer(ctx, {
      dur: dur + 0.1,
      f0: (t) => rnd(rng, 34, 44) * (1 + 0.35 * Math.sin(2 * Math.PI * rnd(rng, 11, 19) * t)),
      jitter: 0.2, shimmer: 0.5, rough: 0.6, oq: 0.4, breath: 0.25, rng,
    });
    const s = bufSrc(ctx, src, 0.005);
    const bank = formantBank(ctx, 'a', { scale: rnd(rng, 0.8, 1.0), bwScale: 2.2 });
    morphVowel(bank, 'o', 0.005 + dur * 0.4, dur * 0.5);
    const dist = shaper(ctx, fuzzCurve(7, 0.15));
    const lp = filt(ctx, 'lowpass', 2600, 0.8);
    const g = gainNode(ctx, 0);
    ampEnv(g.gain, { t: 0.005, peak: 0.85, attack: 0.012, decay: dur, curve: 'lin' });
    s.connect(bank.input); bank.output.connect(dist); dist.connect(lp); lp.connect(g); g.connect(out);
    const direct = gainNode(ctx, 0.3);
    s.connect(direct); direct.connect(dist);
  },
};

/**
 * 1950s radio-ad perk jingle: a cheesy little sung phrase (formant-filtered
 * saw "voices") + a plucked comping chord + a hand-clap-ish tick, the whole
 * thing squeezed into an AM-radio band with tape wow and mild saturation.
 */
function perkJingle(spec) {
  return {
    dur: spec.dur ?? 3.4, gain: 0.8, bus: 'music', srScale: 0.5, defer: true,
    build(ctx, out, rng, v, lib) {
      // --- lo-fi chain: band-limit + saturate + wow ---
      const bus = gainNode(ctx, 1);
      const hp = filt(ctx, 'highpass', 320, 0.7);
      const lp = filt(ctx, 'lowpass', 3300, 0.9);
      const pres = filt(ctx, 'peaking', 1800, 1.2, 5);
      const sat = shaper(ctx, satCurve(3.2));
      const rev = makeReverb(ctx, { decay: 1.1, damp: 3200, preDelay: 0.012, gain: 0.22 });
      bus.connect(hp); hp.connect(pres); pres.connect(lp); lp.connect(sat);
      sat.connect(out);
      sat.connect(rev.input);
      rev.output.connect(out);
      // tape hiss
      const hiss = bufSrc(ctx, lib.noise.pink, 0, { loop: true, offset: rnd(rng, 0, 2) });
      const hf = filt(ctx, 'highpass', 2200, 0.7);
      const hg = gainNode(ctx, 0.012);
      hiss.connect(hf); hf.connect(hg); hg.connect(out);
      hiss.stop(spec.dur ?? 3.4);

      const beat = 60 / (spec.bpm ?? 132);
      const root = spec.root ?? 60;

      // --- sung melody ---
      for (const [b, deg, len, syl] of spec.mel) {
        const t = 0.06 + b * beat;
        const f = mtof(root + deg);
        const c = choirVoice(ctx, bus, {
          t, freq: f, dur: len * beat * 0.95, peak: 0.24,
          vowel: syl || 'a', voices: 3, detune: 10, spread: 6, vib: 1.4,
          attack: 0.05, release: len * beat * 0.4, lp: 3000, fscale: 1.1, rng,
        });
      }
      // --- comping chord stabs (plucky, like a jazz guitar/banjo) ---
      for (const [b, chord] of spec.comp) {
        const t = 0.06 + b * beat;
        for (let i = 0; i < chord.length; i++) {
          const f = mtof(root + chord[i] - 12);
          const o1 = osc(ctx, 'sawtooth', f);
          const bp = filt(ctx, 'bandpass', f * 3, 2.5);
          const g = gainNode(ctx, 0);
          ampEnv(g.gain, { t: t + i * 0.006, peak: 0.1, attack: 0.003, decay: 0.28 });
          o1.connect(bp); bp.connect(g); g.connect(bus);
          o1.start(t); o1.stop(t + 0.4);
        }
      }
      // --- percussion: brushy tick ---
      for (const b of spec.tick || []) {
        noiseBurst(ctx, bus, {
          noise: lib.noise.white, t: 0.06 + b * beat, type: 'bandpass', f0: 5200, q: 0.9,
          attack: 0.001, decay: 0.05, peak: 0.16, rng,
        });
      }
      // --- final sparkle ---
      if (spec.sparkle !== false) {
        for (let i = 0; i < 4; i++) {
          ping(ctx, bus, {
            t: (spec.dur ?? 3.4) - 0.9 + i * 0.05, freq: mtof(root + 24 + i * 5),
            dur: 0.7, peak: 0.07, mod: 2.0, index: 0.5, pan: jit(rng, 0.5),
          });
        }
      }
    },
  };
}

// Juggernog — deep red, heavy, blues-y swagger (Eb major-ish)
SFX.perk_jingle_juggernog = perkJingle({
  root: 63, bpm: 116, dur: 3.6,
  mel: [[0, 0, 1, 'o'], [1, 3, 0.5, 'a'], [1.5, 5, 0.5, 'a'], [2, 7, 1.5, 'o'], [4, 5, 0.5, 'a'], [4.5, 3, 0.5, 'a'], [5, 0, 2, 'u']],
  comp: [[0, [0, 4, 7]], [2, [0, 3, 7]], [4, [5, 9, 12]], [5, [0, 4, 7]]],
  tick: [1, 3, 5],
});
// Speed Cola — green, quick, bright, twice as fast
SFX.perk_jingle_speedcola = perkJingle({
  root: 67, bpm: 168, dur: 3.0,
  mel: [[0, 0, 0.5, 'i'], [0.5, 4, 0.5, 'i'], [1, 7, 0.5, 'e'], [1.5, 12, 1, 'a'],
        [3, 11, 0.5, 'e'], [3.5, 7, 0.5, 'e'], [4, 9, 0.5, 'a'], [4.5, 7, 1.5, 'o']],
  comp: [[0, [0, 4, 7]], [1, [0, 4, 7]], [2, [2, 5, 9]], [3, [7, 11, 14]], [4, [0, 4, 7]]],
  tick: [0.5, 1.5, 2.5, 3.5, 4.5],
});
// Quick Revive — light blue, gentle, a lullaby with a hopeful lift
SFX.perk_jingle_quickrevive = perkJingle({
  root: 65, bpm: 96, dur: 3.8,
  mel: [[0, 0, 1, 'u'], [1, 2, 0.5, 'a'], [1.5, 4, 0.5, 'a'], [2, 7, 1, 'o'], [3, 4, 0.5, 'a'], [3.5, 2, 0.5, 'a'], [4, 0, 2, 'u']],
  comp: [[0, [0, 4, 7]], [2, [5, 9, 12]], [4, [0, 4, 7]]],
  tick: [1, 3],
});
// Double Tap — dark red + gold, punchy, two of everything
SFX.perk_jingle_doubletap = perkJingle({
  root: 62, bpm: 144, dur: 3.2,
  mel: [[0, 0, 0.5, 'a'], [0.5, 0, 0.5, 'a'], [1, 7, 0.5, 'o'], [1.5, 7, 0.5, 'o'],
        [2, 10, 0.5, 'a'], [2.5, 10, 0.5, 'a'], [3, 12, 1.5, 'o'], [5, 0, 1, 'u']],
  comp: [[0, [0, 3, 7]], [1, [0, 3, 7]], [2, [5, 8, 12]], [3, [0, 3, 7]], [5, [0, 3, 7]]],
  tick: [0.5, 1.5, 2.5, 3.5, 4.5, 5.5],
});

/* ---------- machines / power-ups ---------- */

SFX.pap_upgrade = {
  defer: true,
  dur: 4.6, gain: 1.0, bus: 'sfx',
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 2.2, damp: 2800, gain: 0.3 });
    rev.output.connect(out);
    // 1. hatch closes
    thump(ctx, out, { t: 0.01, f0: 160, f1: 45, dur: 0.3, peak: 0.7, type: 'triangle', drive: 3 });
    clack(ctx, out, { t: 0.01, freqs: [1200, 2400, 3900], dur: 0.06, peak: 0.4, noise: lib.noise.white, bright: 2400, rng });
    // 2. motor spins up and runs
    const motor = osc(ctx, 'sawtooth', 60);
    setAt(motor.frequency, 34, 0.15); expTo(motor.frequency, 96, 0.9); setAt(motor.frequency, 96, 3.1); expTo(motor.frequency, 40, 3.9);
    const mlp = filt(ctx, 'lowpass', 1400, 4);
    setAt(mlp.frequency, 600, 0.15); expTo(mlp.frequency, 2200, 1.2); expTo(mlp.frequency, 700, 3.9);
    const mdist = shaper(ctx, satCurve(4));
    const mg = gainNode(ctx, 0);
    ampEnv(mg.gain, { t: 0.15, peak: 0.32, attack: 0.5, hold: 2.5, decay: 0.8, curve: 'lin' });
    motor.connect(mlp); mlp.connect(mdist); mdist.connect(mg); mg.connect(out); mg.connect(rev.input);
    motor.start(0.15); motor.stop(4.1);
    // 3. hydraulic hiss
    noiseBurst(ctx, out, { noise: lib.noise.white, t: 0.5, type: 'bandpass', f0: 3400, f1: 1600, q: 1.1, sweep: 0.8, attack: 0.15, decay: 0.9, peak: 0.16, curve: 'lin', rng });
    noiseBurst(ctx, out, { noise: lib.noise.white, t: 2.6, type: 'bandpass', f0: 2600, f1: 5200, q: 1.0, sweep: 0.3, attack: 0.05, decay: 0.5, peak: 0.2, curve: 'lin', rng });
    // 4. clanks and stamping
    for (const t of [0.85, 1.35, 1.9, 2.45]) {
      clack(ctx, out, { t: t + rnd(rng, -0.04, 0.04), freqs: [rnd(rng, 700, 1400), rnd(rng, 2200, 3600), rnd(rng, 4200, 6000)], dur: 0.07, peak: 0.4, noise: lib.noise.white, bright: 2600, rng });
      thump(ctx, out, { t, f0: 190, f1: 55, dur: 0.16, peak: 0.45, type: 'triangle', drive: 3 });
    }
    // 5. energy charge rising underneath
    const ch = osc(ctx, 'sawtooth', 120);
    setAt(ch.frequency, 90, 1.6); expTo(ch.frequency, 720, 3.3);
    const chbp = filt(ctx, 'bandpass', 800, 5);
    setAt(chbp.frequency, 400, 1.6); expTo(chbp.frequency, 4200, 3.3);
    const chg = gainNode(ctx, 0);
    ampEnv(chg.gain, { t: 1.6, peak: 0.2, attack: 1.4, decay: 0.4, curve: 'lin' });
    ch.connect(chbp); chbp.connect(chg); chg.connect(out); chg.connect(rev.input);
    ch.start(1.6); ch.stop(3.8);
    // 6. the ka-CHUNK and the reveal chime
    thump(ctx, out, { t: 3.25, f0: 140, f1: 35, dur: 0.4, peak: 0.95, drive: 4 });
    clack(ctx, out, { t: 3.25, freqs: [900, 1800, 3100, 4800], dur: 0.09, peak: 0.6, noise: lib.noise.white, bright: 2200, rng });
    const chord = [0, 7, 12, 16];
    for (let i = 0; i < chord.length; i++) {
      const b = bell(ctx, out, { t: 3.32 + i * 0.03, freq: mtof(64 + chord[i]), dur: 1.3, peak: 0.16, pan: jit(rng, 0.5) });
      b.out.connect(rev.input);
    }
    const spark = bufSrc(ctx, crackleBuffer(ctx, 1.0, rng, { density: 60, fLo: 3000, fHi: 11000, amp: 0.5 }), 3.3);
    const sg = gainNode(ctx, 0);
    ampEnv(sg.gain, { t: 3.3, peak: 0.16, attack: 0.02, decay: 0.9 });
    spark.connect(sg); sg.connect(out);
  },
};

SFX.power_on = {
  defer: true,
  dur: 4.0, gain: 1.0,
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 3.0, damp: 2200, gain: 0.35 });
    rev.output.connect(out);
    // the big knife switch
    clack(ctx, out, { t: 0.01, freqs: [700, 1500, 2600, 4200], dur: 0.09, peak: 0.7, noise: lib.noise.white, bright: 2000, rng });
    thump(ctx, out, { t: 0.01, f0: 150, f1: 38, dur: 0.35, peak: 0.85, type: 'triangle', drive: 4 });
    // arc
    const arc = bufSrc(ctx, crackleBuffer(ctx, 0.7, rng, { density: 120, fLo: 1200, fHi: 9000, amp: 0.8 }), 0.02);
    const ag = gainNode(ctx, 0);
    ampEnv(ag.gain, { t: 0.02, peak: 0.45, attack: 0.004, decay: 0.55 });
    arc.connect(ag); ag.connect(out); ag.connect(rev.input);
    // mains hum fading up: 60 Hz + harmonics (it's 1950s America)
    const hum = gainNode(ctx, 0);
    ampEnv(hum.gain, { t: 0.1, peak: 0.3, attack: 1.2, hold: 1.4, decay: 1.2, curve: 'lin' });
    hum.connect(out); hum.connect(rev.input);
    for (const [h, a] of [[1, 1], [2, 0.5], [3, 0.35], [4, 0.18], [5, 0.12], [7, 0.07]]) {
      const o1 = osc(ctx, h % 2 ? 'sine' : 'triangle', 60 * h);
      const g = gainNode(ctx, a * 0.3);
      o1.connect(g); g.connect(hum);
      o1.start(0.1); o1.stop(3.9);
    }
    // fluorescent tubes striking one after another
    for (let i = 0; i < 6; i++) {
      const t = 0.5 + i * rnd(rng, 0.18, 0.38);
      for (let k = 0; k < rint(rng, 2, 5); k++) {
        noiseBurst(ctx, out, {
          noise: lib.noise.white, t: t + k * rnd(rng, 0.012, 0.05), type: 'bandpass',
          f0: rnd(rng, 2200, 5000), q: 1.6, attack: 0.0008, decay: rnd(rng, 0.01, 0.04),
          peak: rnd(rng, 0.1, 0.3), rng,
        });
      }
      ping(ctx, out, { t: t + 0.06, freq: rnd(rng, 700, 1600), dur: 0.3, peak: 0.06 });
    }
    // deep rising whoosh: the town waking up
    const wh = osc(ctx, 'sawtooth', 40);
    setAt(wh.frequency, 28, 0.05); expTo(wh.frequency, 78, 2.2);
    const wlp = filt(ctx, 'lowpass', 300, 3);
    setAt(wlp.frequency, 120, 0.05); expTo(wlp.frequency, 900, 2.2); expTo(wlp.frequency, 200, 3.8);
    const wg = gainNode(ctx, 0);
    ampEnv(wg.gain, { t: 0.05, peak: 0.45, attack: 1.6, decay: 1.9, curve: 'lin' });
    wh.connect(wlp); wlp.connect(wg); wg.connect(out); wg.connect(rev.input);
    wh.start(0.05); wh.stop(3.9);
  },
};

SFX.powerup_spawn = {
  defer: true,
  dur: 2.2, gain: 1.0,
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 2.2, damp: 7000, gain: 0.4 });
    rev.output.connect(out);
    // shimmering rising arpeggio with ring-mod sparkle
    const scale = [0, 4, 7, 11, 14, 16, 19, 23];
    for (let i = 0; i < scale.length; i++) {
      const p = ping(ctx, out, {
        t: 0.02 + i * 0.055, freq: mtof(60 + scale[i]), dur: 1.0 - i * 0.05,
        peak: 0.2, mod: 2.01, index: 0.9, pan: jit(rng, 0.7),
      });
      p.out.connect(rev.input);
    }
    // upward filtered noise sweep
    noiseBurst(ctx, out, { noise: lib.noise.white, t: 0.02, type: 'bandpass', f0: 500, f1: 9000, q: 1.4, sweep: 0.65, attack: 0.1, decay: 0.7, peak: 0.16, curve: 'lin', rng });
    // settling hum
    const h = osc(ctx, 'sine', 220);
    const hg = gainNode(ctx, 0);
    ampEnv(hg.gain, { t: 0.5, peak: 0.1, attack: 0.3, decay: 1.2, curve: 'lin' });
    h.connect(hg); hg.connect(out); hg.connect(rev.input);
    h.start(0.5); h.stop(2.1);
  },
};

SFX.powerup_loop = {
  defer: true,
  dur: 2.4, xfade: 0.6, loop: true, gain: 1.0,
  build(ctx, out, rng, v, lib) {
    // shimmering hum: detuned partials beating against each other + a tremolo
    // glitter layer, everything phase-locked to the loop length so it seams.
    const bus = gainNode(ctx, 0.5);
    bus.connect(out);
    // frequencies locked to exact multiples of 1/2.4 s so the seam phase-aligns
    const partials = [110, 165, 220, 330, 440, 660].map((f) => lockFreq(f, 2.4));
    for (let i = 0; i < partials.length; i++) {
      const o1 = osc(ctx, i < 3 ? 'triangle' : 'sine', partials[i]);
      const g = gainNode(ctx, 0.5 / (i + 1.4));
      // beat rate chosen as an exact multiple of 1/loopDur (2.4 s) -> seamless
      const lfo = osc(ctx, 'sine', (Math.round(rnd(rng, 1, 5)) / 2.4));
      const lg = gainNode(ctx, 0.35 / (i + 1.4));
      lfo.connect(lg); lg.connect(g.gain);
      lfo.start(0); lfo.stop(3.2);
      o1.connect(g); g.connect(bus);
      o1.start(0); o1.stop(3.2);
    }
    // high glitter
    const gl = bufSrc(ctx, crackleBuffer(ctx, 3.0, rng, { density: 26, fLo: 4000, fHi: 12000, amp: 0.5, decayLo: 0.02, decayHi: 0.1 }), 0);
    const gg = gainNode(ctx, 0.2);
    gl.connect(gg); gg.connect(out);
    // airy top
    const s = bufSrc(ctx, lib.noise.pink, 0, { loop: true, offset: rnd(rng, 0, 2) });
    const bp = filt(ctx, 'bandpass', 6000, 1.2);
    const sg = gainNode(ctx, 0.05);
    const slfo = osc(ctx, 'sine', 2 / 2.4);
    const slg = gainNode(ctx, 0.03);
    slfo.connect(slg); slg.connect(sg.gain);
    slfo.start(0); slfo.stop(3.2);
    s.connect(bp); bp.connect(sg); sg.connect(out);
    s.stop(3.2);
  },
};

SFX.powerup_grab = {
  defer: true,
  dur: 1.4, gain: 1.0, bus: 'ui',
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 1.4, damp: 8000, gain: 0.35 });
    rev.output.connect(out);
    const notes = [72, 76, 79, 84];
    for (let i = 0; i < notes.length; i++) {
      const p = ping(ctx, out, { t: 0.005 + i * 0.035, freq: mtof(notes[i]), dur: 0.8, peak: 0.28, mod: 2.0, index: 0.5, pan: jit(rng, 0.4) });
      p.out.connect(rev.input);
    }
    noiseBurst(ctx, out, { noise: lib.noise.white, t: 0.005, type: 'bandpass', f0: 2000, f1: 11000, q: 1.2, sweep: 0.2, attack: 0.02, decay: 0.3, peak: 0.16, curve: 'lin', rng });
  },
};

SFX.powerup_blink = {
  dur: 0.4, gain: 1.0, bus: 'ui',
  build(ctx, out, rng, v, lib) {
    ping(ctx, out, { t: 0.002, freq: mtof(88), dur: 0.12, peak: 0.5, type: 'triangle' });
    ping(ctx, out, { t: 0.002, freq: mtof(95), dur: 0.08, peak: 0.2 });
  },
};

/** Short power-up announcement stingers (played with the announcer VO). */
function powerStinger(spec) {
  return {
    dur: spec.dur ?? 2.4, gain: 0.85, bus: 'music', defer: true,
    build(ctx, out, rng, v, lib) {
      const rev = makeReverb(ctx, { decay: spec.rt ?? 2.4, damp: spec.damp ?? 4500, preDelay: 0.015, gain: 0.45 });
      rev.output.connect(out);
      const root = spec.root ?? 57;
      for (const [t, deg, dur, amp, kind] of spec.notes) {
        if (kind === 'bell') {
          const b = bell(ctx, out, { t, freq: mtof(root + deg), dur, peak: amp, pan: jit(rng, 0.3) });
          b.out.connect(rev.input);
        } else if (kind === 'choir') {
          const c = choirVoice(ctx, out, { t, freq: mtof(root + deg), dur, peak: amp, vowel: spec.vowel || 'o', voices: 4, detune: 12, attack: 0.08, release: dur * 0.5, rng });
          c.out.connect(rev.input);
        } else {
          const p = ping(ctx, out, { t, freq: mtof(root + deg), dur, peak: amp, mod: spec.mod ?? 2.0, index: spec.index ?? 0.6, pan: jit(rng, 0.4) });
          p.out.connect(rev.input);
        }
      }
      if (spec.boom) {
        const th = thump(ctx, out, { t: 0.005, f0: spec.boom, f1: spec.boom * 0.3, dur: 0.8, peak: 0.6, drive: 3 });
        th.gain.connect(rev.input);
      }
      if (spec.noise) {
        noiseBurst(ctx, out, { noise: lib.noise.white, t: 0.005, type: 'bandpass', f0: spec.noise[0], f1: spec.noise[1], q: 1.2, sweep: 0.4, attack: 0.02, decay: 0.5, peak: 0.14, curve: 'lin', rng });
      }
    },
  };
}

SFX.max_ammo = powerStinger({
  root: 60, dur: 2.6, boom: 90, noise: [1200, 8000],
  notes: [[0.01, 0, 1.4, 0.3, 'bell'], [0.12, 7, 1.4, 0.26, 'bell'], [0.24, 12, 1.6, 0.3, 'bell'], [0.36, 19, 1.5, 0.22, 'ping']],
});
SFX.insta_kill = powerStinger({
  root: 45, dur: 2.8, rt: 3.2, damp: 2200, boom: 70,
  notes: [[0.01, 0, 2.2, 0.32, 'bell'], [0.01, 6, 2.0, 0.18, 'bell'], [0.05, 12, 2.0, 0.2, 'choir'], [0.05, 18, 1.8, 0.14, 'choir']],
  vowel: 'o',
});
SFX.double_points = powerStinger({
  root: 62, dur: 2.2, boom: 96,
  notes: [[0.01, 0, 0.9, 0.3, 'ping'], [0.1, 0, 0.9, 0.28, 'ping'], [0.22, 12, 1.2, 0.3, 'bell'], [0.32, 12, 1.2, 0.26, 'bell']],
});
SFX.carpenter = powerStinger({
  root: 55, dur: 2.6, rt: 1.8,
  notes: [[0.01, 0, 1.0, 0.28, 'bell'], [0.16, 5, 1.0, 0.26, 'bell'], [0.32, 9, 1.2, 0.28, 'bell'], [0.48, 12, 1.5, 0.3, 'bell']],
});
SFX.fire_sale = powerStinger({
  root: 64, dur: 2.4, rt: 1.6,
  notes: [[0.01, 0, 0.6, 0.26, 'ping'], [0.1, 4, 0.6, 0.24, 'ping'], [0.2, 7, 0.6, 0.24, 'ping'],
          [0.3, 12, 0.6, 0.26, 'ping'], [0.4, 9, 0.6, 0.22, 'ping'], [0.5, 12, 1.4, 0.3, 'bell']],
});

/* ---------- hellhounds ---------- */

SFX.hellhound_spawn = {
  defer: true,
  dur: 3.9, variants: 1, gain: 1.0, jitter: 40,
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 3.6, damp: 2000, gain: 0.4 });
    rev.output.connect(out);
    // pre-strike static
    const pre = bufSrc(ctx, crackleBuffer(ctx, 0.35, rng, { density: 50, fLo: 2000, fHi: 9000, amp: 0.5 }), 0);
    const pg = gainNode(ctx, 0);
    ampEnv(pg.gain, { t: 0, peak: 0.18, attack: 0.25, decay: 0.1, curve: 'lin' });
    pre.connect(pg); pg.connect(out);
    // the strike: ultra-fast bright transient with a hard pitch fall
    const t0 = 0.34;
    noiseBurst(ctx, out, { noise: lib.noise.white, t: t0, type: 'highpass', f0: 6000, q: 0.5, attack: 0.0004, decay: 0.02, peak: 1.0, rng });
    const b = noiseBurst(ctx, out, { noise: lib.noise.white, t: t0, type: 'bandpass', f0: 5000, f1: 220, q: 0.7, sweep: 0.18, attack: 0.0006, decay: 0.3, peak: 0.95, drive: 8, rng });
    if (b) b.gain.connect(rev.input);
    const th = thump(ctx, out, { t: t0, f0: 130, f1: 22, dur: 0.6, glide: 0.3, peak: 1.0, drive: 4 });
    th.gain.connect(rev.input);
    // electric sizzle
    const sz = bufSrc(ctx, crackleBuffer(ctx, 1.2, rng, { density: 140, fLo: 1500, fHi: 11000, amp: 0.7 }), t0);
    const szg = gainNode(ctx, 0);
    ampEnv(szg.gain, { t: t0, peak: 0.4, attack: 0.002, decay: 1.0 });
    sz.connect(szg); szg.connect(out); szg.connect(rev.input);
    // rolling thunder
    const rum = bufSrc(ctx, crackleBuffer(ctx, 3.2, rng, { density: 45, fLo: 45, fHi: 500, amp: 1.0, decayLo: 0.04, decayHi: 0.3 }), t0 + 0.08);
    const rlp = filt(ctx, 'lowpass', 500, 0.8);
    const rg = gainNode(ctx, 0);
    ampEnv(rg.gain, { t: t0 + 0.08, peak: 0.6, attack: 0.3, decay: 2.9, curve: 'lin' });
    rum.connect(rlp); rlp.connect(rg); rg.connect(out); rg.connect(rev.input);
    // a howl underneath
    zombieVoice(ctx, out, lib, rng, {
      t: t0 + 0.5, dur: 1.5, f0a: 150, f0b: 95, vowel: 'u', vowel2: 'o', morphAt: 0.3,
      fscale: 0.8, jitter: 0.03, shimmer: 0.2, rough: 0.2, breath: 0.15, growl: 0.3,
      drive: 6, peak: 0.3, attack: 0.3, release: 0.8, air: 0.05, wobble: 0.05,
    });
  },
};

SFX.hellhound_growl = {
  dur: 2.05, variants: 3, gain: 1.0, jitter: 120, rateJit: 0.07,
  build(ctx, out, rng, v, lib) {
    const dur = rnd(rng, 1.1, 1.6);
    zombieVoice(ctx, out, lib, rng, {
      t: 0.005, dur, f0a: rnd(rng, 58, 74), f0b: rnd(rng, 50, 64),
      vowel: 'o', vowel2: 'u', morphAt: 0.4, fscale: 0.72, bwScale: 2.2,
      jitter: 0.08, shimmer: 0.4, rough: 0.6, breath: 0.2, oq: 0.5,
      growl: 0.4, drive: 7, postLp: 2600, direct: 0.45,
      peak: 0.85, attack: 0.12, release: dur * 0.45, air: 0.06,
      wobble: 0.14, rattle: 0.12, rattleF: 380,
    });
  },
};

SFX.hellhound_bite = {
  dur: 1.0, variants: 3, gain: 1.0, jitter: 110,
  build(ctx, out, rng, v, lib) {
    // jaw snap: two hard clacks + a bark + flesh
    clack(ctx, out, { t: 0.002, freqs: [520, 980, 1700, 2800], dur: 0.035, peak: 0.7, noise: lib.noise.white, bright: 1800, rng });
    thump(ctx, out, { t: 0.002, f0: 180, f1: 55, dur: 0.1, peak: 0.55, type: 'triangle', drive: 3 });
    zombieVoice(ctx, out, lib, rng, {
      t: 0.0, dur: 0.28, f0a: rnd(rng, 105, 135), f0b: rnd(rng, 70, 88),
      vowel: 'a', vowel2: 'o', morphAt: 0.3, fscale: 0.78,
      jitter: 0.08, shimmer: 0.4, rough: 0.5, breath: 0.25, growl: 0.4,
      drive: 9, peak: 0.8, attack: 0.008, release: 0.16, air: 0.08,
    });
    noiseBurst(ctx, out, { noise: lib.noise.brown, t: 0.01, type: 'lowpass', f0: 1200, f1: 240, q: 2.2, sweep: 0.08, attack: 0.001, decay: 0.14, peak: 0.5, drive: 4, rng });
  },
};

/* ---------- ambience ---------- */

SFX.fire_loop = {
  dur: 4.0, xfade: 0.8, loop: true, gain: 1.0,
  build(ctx, out, rng, v, lib) {
    const total = 4.8;
    // roaring body
    const s = bufSrc(ctx, lib.noise.brown, 0, { loop: true, offset: rnd(rng, 0, 4) });
    const lp = filt(ctx, 'lowpass', 700, 0.8);
    const hp = filt(ctx, 'highpass', 90, 0.7);
    const g = gainNode(ctx, 0.35);
    // slow breathing of the flame
    for (const r of [0.75, 1.25, 2.0]) {
      const lfo = osc(ctx, 'sine', r / 4.0);
      const lg = gainNode(ctx, 0.08);
      lfo.connect(lg); lg.connect(g.gain);
      lfo.start(0); lfo.stop(total);
      const flfo = osc(ctx, 'sine', r / 4.0);
      const flg = gainNode(ctx, 180);
      flfo.connect(flg); flg.connect(lp.frequency);
      flfo.start(0); flfo.stop(total);
    }
    s.connect(hp); hp.connect(lp); lp.connect(g); g.connect(out);
    s.stop(total);
    // hissing mid
    const s2 = bufSrc(ctx, lib.noise.pink, 0, { loop: true, offset: rnd(rng, 0, 4) });
    const bp2 = filt(ctx, 'bandpass', 2200, 0.7);
    const g2 = gainNode(ctx, 0.12);
    const l2 = osc(ctx, 'sine', 3 / 4.0);
    const lg2 = gainNode(ctx, 0.05);
    l2.connect(lg2); lg2.connect(g2.gain);
    l2.start(0); l2.stop(total);
    s2.connect(bp2); bp2.connect(g2); g2.connect(out);
    s2.stop(total);
    // crackle and pops
    const cr = bufSrc(ctx, crackleBuffer(ctx, total, rng, { density: 34, fLo: 700, fHi: 5200, amp: 0.9, decayLo: 0.004, decayHi: 0.05 }), 0);
    const cg = gainNode(ctx, 0.5);
    cr.connect(cg); cg.connect(out);
    // occasional bigger snap
    for (let i = 0; i < 6; i++) {
      noiseBurst(ctx, out, {
        noise: lib.noise.white, t: rnd(rng, 0, total - 0.2), type: 'bandpass',
        f0: rnd(rng, 900, 2600), q: 1.4, attack: 0.0008, decay: rnd(rng, 0.03, 0.09),
        peak: rnd(rng, 0.15, 0.35), rng,
      });
    }
  },
};

SFX.ambient_loop = {
  dur: 18.0, xfade: 2.5, loop: true, gain: 1.0, bus: 'ambient', srScale: 0.5,
  build(ctx, out, rng, v, lib) {
    const total = 20.5;
    const L = 18.0;
    // ---- wind: two bandpassed noise layers with slow, loop-locked motion ----
    for (let k = 0; k < 2; k++) {
      const s = bufSrc(ctx, lib.noise.brown, 0, { loop: true, offset: rnd(rng, 0, 4), rate: 0.8 + k * 0.3 });
      const bp = filt(ctx, 'bandpass', 420 + k * 500, 0.8);
      const g = gainNode(ctx, 0.2 - k * 0.06);
      const p = panner(ctx, k ? 0.55 : -0.55);
      // gusts: frequencies are integer multiples of 1/L so the loop seams
      for (const n of [1, 2, 3]) {
        const lfo = osc(ctx, 'sine', n / L);
        const lg = gainNode(ctx, (0.09 / n) * (1 + k * 0.3));
        lfo.connect(lg); lg.connect(g.gain);
        lfo.start(0); lfo.stop(total);
        const flfo = osc(ctx, 'sine', n / L);
        flfo.detune.value = k * 90;
        const flg = gainNode(ctx, (260 / n) * (1 + k));
        flfo.connect(flg); flg.connect(bp.frequency);
        flfo.start(0); flfo.stop(total);
      }
      s.connect(bp); bp.connect(g); g.connect(p); p.connect(out);
      s.stop(total);
    }
    // whistling through wires / broken windows
    for (let i = 0; i < 3; i++) {
      const o1 = osc(ctx, 'sine', lockFreq(rnd(rng, 700, 1600), L));
      const lfo = osc(ctx, 'sine', Math.round(rnd(rng, 1, 4)) / L);
      const lg = gainNode(ctx, rnd(rng, 40, 140));
      lfo.connect(lg); lg.connect(o1.detune);
      lfo.start(0); lfo.stop(total);
      const g = gainNode(ctx, 0);
      const alfo = osc(ctx, 'sine', Math.round(rnd(rng, 1, 3)) / L);
      const ag = gainNode(ctx, 0.012);
      alfo.connect(ag); ag.connect(g.gain);
      setAt(g.gain, 0.012, 0);
      alfo.start(0); alfo.stop(total);
      o1.connect(g); g.connect(panner(ctx, rnd(rng, -0.8, 0.8))).connect(out);
      o1.start(0); o1.stop(total);
    }
    // ---- low drone: the dread bed ----
    const drone = gainNode(ctx, 0.16);
    drone.connect(out);
    for (const [f, a] of [[41.2, 1], [61.7, 0.55], [82.4, 0.3], [123.5, 0.16]]) {
      const o1 = osc(ctx, 'sawtooth', lockFreq(f, L));
      const lp = filt(ctx, 'lowpass', 240, 2.5);
      const flfo = osc(ctx, 'sine', 1 / L);
      const flg = gainNode(ctx, 90);
      flfo.connect(flg); flg.connect(lp.frequency);
      flfo.start(0); flfo.stop(total);
      const g = gainNode(ctx, a * 0.5);
      o1.connect(lp); lp.connect(g); g.connect(drone);
      o1.start(0); o1.stop(total);
    }
    // ---- distant fires ----
    const cr = bufSrc(ctx, crackleBuffer(ctx, total, rng, { density: 9, fLo: 500, fHi: 2600, amp: 0.7, decayLo: 0.006, decayHi: 0.06 }), 0);
    const crlp = filt(ctx, 'lowpass', 1800, 0.7);
    const crg = gainNode(ctx, 0.16);
    cr.connect(crlp); crlp.connect(crg); crg.connect(out);
    const fb = bufSrc(ctx, lib.noise.brown, 0, { loop: true, offset: rnd(rng, 0, 4) });
    const fbp = filt(ctx, 'bandpass', 300, 0.9);
    const fg = gainNode(ctx, 0.07);
    fb.connect(fbp); fbp.connect(fg); fg.connect(panner(ctx, 0.35)).connect(out);
    fb.stop(total);
    // ---- occasional distant rumbles / collapses ----
    for (let i = 0; i < 4; i++) {
      const t = 1.5 + i * (L - 3) / 4 + rnd(rng, 0, 1.5);
      const dur = rnd(rng, 1.8, 3.4);
      const s = bufSrc(ctx, lib.noise.brown, t, { loop: true, offset: rnd(rng, 0, 4) });
      const lp = filt(ctx, 'lowpass', rnd(rng, 110, 220), 1.2);
      const g = gainNode(ctx, 0);
      ampEnv(g.gain, { t, peak: rnd(rng, 0.2, 0.42), attack: dur * 0.35, decay: dur * 0.7, curve: 'lin' });
      s.connect(lp); lp.connect(g); g.connect(panner(ctx, rnd(rng, -0.7, 0.7))).connect(out);
      s.stop(t + dur + 0.3);
      // a faint tonal groan of stressed metal riding the rumble
      if (rng() < 0.6) {
        const o1 = osc(ctx, 'sawtooth', rnd(rng, 90, 190));
        const bp = filt(ctx, 'bandpass', rnd(rng, 400, 900), 8);
        const og = gainNode(ctx, 0);
        ampEnv(og.gain, { t: t + 0.2, peak: 0.035, attack: dur * 0.3, decay: dur * 0.5, curve: 'lin' });
        o1.connect(bp); bp.connect(og); og.connect(out);
        o1.start(t + 0.2); o1.stop(t + dur);
      }
    }
    // ---- sparse metal clanks and creaks in the distance ----
    for (let i = 0; i < 5; i++) {
      const t = rnd(rng, 0.5, L - 1.5);
      const f = rnd(rng, 400, 1800);
      const p = ping(ctx, out, { t, freq: f, dur: rnd(rng, 0.4, 1.4), peak: rnd(rng, 0.02, 0.055), mod: 1.41, index: 0.7, pan: rnd(rng, -0.9, 0.9) });
      clack(ctx, out, { t, freqs: [f * 1.8, f * 3.2], dur: 0.03, peak: 0.03, rng });
    }
    // ---- a very faint, very wrong distant moan ----
    for (let i = 0; i < 2; i++) {
      const t = 3 + i * 8 + rnd(rng, 0, 3);
      const vo = zombieVoice(ctx, out, lib, rng, {
        t, dur: rnd(rng, 1.8, 2.6), f0a: rnd(rng, 62, 80), f0b: rnd(rng, 52, 66),
        vowel: 'o', vowel2: 'u', morphAt: 0.4, jitter: 0.05, shimmer: 0.3, rough: 0.4,
        breath: 0.2, growl: 0.15, drive: 3, peak: 0.055, attack: 0.5, release: 1.0,
        air: 0.01, pan: rnd(rng, -0.85, 0.85), wobble: 0.07,
      });
    }
  },
};

/* ---------- misc extras (beyond the contract but handy) ---------- */

SFX.footstep_dirt = {
  dur: 0.3, variants: 4, gain: 1.0, jitter: 140, rateJit: 0.12,
  build(ctx, out, rng, v, lib) {
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.16, rng, { density: 700, amp: 0.8, skew: 0.35 }), 0.001);
    const bp = filt(ctx, 'bandpass', rnd(rng, 700, 1500), 0.8);
    const g = gainNode(ctx, 0);
    ampEnv(g.gain, { t: 0.001, peak: 0.7, attack: 0.003, decay: 0.11 });
    gr.connect(bp); bp.connect(g); g.connect(out);
    thump(ctx, out, { t: 0.001, f0: rnd(rng, 110, 160), f1: 55, dur: 0.07, peak: 0.35, drive: 2 });
  },
};

SFX.footstep_wood = {
  dur: 0.3, variants: 4, gain: 1.0, jitter: 140, rateJit: 0.12,
  build(ctx, out, rng, v, lib) {
    const base = rnd(rng, 210, 300);
    woodModes(ctx, out, rng, 0.001, 0.3, 0.13, base);
    noiseBurst(ctx, out, { noise: lib.noise.pink, t: 0.001, type: 'bandpass', f0: rnd(rng, 1400, 2400), q: 0.9, attack: 0.001, decay: 0.05, peak: 0.3, rng });
    thump(ctx, out, { t: 0.001, f0: 150, f1: 70, dur: 0.07, peak: 0.3, type: 'triangle', drive: 2 });
  },
};

SFX.ui_click = {
  dur: 0.16, variants: 2, gain: 1.0, bus: 'ui', level: -22, jitter: 20,
  build(ctx, out, rng, v, lib) {
    // a 1950s toggle switch, not a beep: a small hard contact with a tiny
    // bakelite body behind it and one tonal partial to say "accepted"
    clack(ctx, out, { t: 0.0005, freqs: [2450, 4100, 6100], dur: 0.016, peak: 0.55, noise: lib.noise.white, bright: 5200, rng });
    ping(ctx, out, { t: 0.0008, freq: 1560, dur: 0.055, peak: 0.34, type: 'triangle' });
    ping(ctx, out, { t: 0.0008, freq: 2340, dur: 0.03, peak: 0.16 });
    thump(ctx, out, { t: 0.0005, f0: 420, f1: 200, dur: 0.028, peak: 0.18, type: 'triangle' });
  },
};

SFX.ui_hover = {
  dur: 0.1, variants: 2, gain: 1.0, bus: 'ui', level: -28, jitter: 30,
  build(ctx, out, rng, v, lib) {
    // barely there — it should register as texture under the cursor, not as a note
    ping(ctx, out, { t: 0.001, freq: 2550, dur: 0.028, peak: 0.3, type: 'sine' });
    noiseBurst(ctx, out, { noise: lib.noise.white, t: 0, type: 'highpass', f0: 6200, q: 0.7, attack: 0.0003, decay: 0.008, peak: 0.22, rng });
  },
};

SFX.ui_back = {
  dur: 0.16, gain: 1.0, bus: 'ui', level: -23,
  build(ctx, out, rng, v, lib) {
    clack(ctx, out, { t: 0.0005, freqs: [1700, 2900, 4200], dur: 0.016, peak: 0.45, noise: lib.noise.white, bright: 3600, rng });
    ping(ctx, out, { t: 0.0008, freq: 1180, dur: 0.06, peak: 0.34, type: 'triangle' });
    ping(ctx, out, { t: 0.03, freq: 880, dur: 0.06, peak: 0.22, type: 'triangle' });
  },
};

SFX.radio_blip = {
  dur: 0.35, variants: 2, gain: 1.0, bus: 'ui',
  build(ctx, out, rng, v, lib) {
    // squelch used to top and tail the announcer
    noiseBurst(ctx, out, { noise: lib.noise.white, t: 0.001, type: 'bandpass', f0: 2400, f1: 1100, q: 1.4, sweep: 0.06, attack: 0.002, decay: 0.08, peak: 0.45, drive: 4, rng });
    ping(ctx, out, { t: 0.001, freq: 1300, dur: 0.05, peak: 0.2, type: 'square' });
  },
};

/* ================================================================== *
 * Weapon handling — the per-class reload vocabulary
 *
 * Ten weapons used to share three reload sounds (`reload_mag_out`,
 * `reload_mag_in`, `reload_bolt`), so an M1911, an MP5, an AK-74u, a Galil, an
 * M14 and an RPD all reloaded with identical foley. What follows is one part per
 * physical event, per class, so a caller can schedule them against the actual
 * animation: a rifle magazine *rocks* into a trunnion and locks at the rear, an
 * SMG magazine goes straight up a well, an RPD has a hinged top cover and a belt,
 * a double gun breaks open, a revolver's crane swings out. None of them sound
 * remotely alike, which is the point.
 *
 * These are also deliberately *parts*, not whole reloads: with Speed Cola the
 * events simply arrive sooner. Nothing here should ever be sped up by playback
 * rate — that pitches steel up an octave and it sounds like a toy.
 * ================================================================== */

/** Shared metadata for a handling part: quiet, close, mono-ish, lots of variants. */
function handling(o) {
  return {
    dur: o.dur, variants: o.variants ?? 3, gain: 1.0,
    jitter: o.jitter ?? 55, rateJit: o.rateJit ?? 0.03,
    level: o.level ?? -22, defer: o.defer, build: o.build,
  };
}

/* ---------- pistol: a box magazine in a steel frame ---------- */

SFX.reload_pistol_out = handling({
  dur: 0.5, level: -23,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    // the catch lets go: a small sprung part snapping sideways
    springTwang(ctx, out, rng, { t: 0.002, f: rnd(rng, 2300, 2700), dur: 0.05, peak: 0.1 });
    steelHit(ctx, out, rng, { t: 0.003, f: 3000, modes: [1, 1.71, 2.6], dur: 0.018, peak: 0.34, noise: W, bright: 4200 });
    // the magazine drops down the well under its own weight
    railSlide(ctx, out, rng, { t: 0.024, dur: 0.1, peak: 0.2, f0: 3000, f1: 1500, q: 1.6, noise: P, grain: 380, grainF: 3400 });
    // …and clears the frame
    steelHit(ctx, out, rng, { t: 0.15 + rnd(rng, 0, 0.02), f: 1250, modes: [1, 1.64, 2.5, 3.4], dur: 0.05, peak: 0.28, noise: W, bright: 2000, thud: 240, thudAmp: 0.4 });
    rattle(ctx, out, rng, { t: 0.17, count: 3, spread: 0.1, f: 3000, peak: 0.055, noise: W });
    clothBrush(ctx, out, rng, { t: 0.1, dur: 0.18, peak: 0.07, noise: P });
  },
});

SFX.reload_pistol_in = handling({
  dur: 0.4, level: -21,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    railSlide(ctx, out, rng, { t: 0.002, dur: 0.07, peak: 0.16, f0: 1400, f1: 2800, q: 1.3, noise: P, grain: 300, grainF: 3000 });
    // seated with the heel of the hand — this is the sound of the reload
    steelHit(ctx, out, rng, { t: 0.085, f: 1380, modes: [1, 1.66, 2.48, 3.5, 4.8], dur: 0.055, peak: 0.62, noise: W, bright: 2300, thud: 300, thudAmp: 0.55 });
    // the catch drops back over the notch
    steelHit(ctx, out, rng, { t: 0.125, f: 3500, modes: [1, 1.7], dur: 0.016, peak: 0.2, noise: W, bright: 5000 });
  },
});

/* ---------- rifle: rock-and-lock into a steel trunnion ---------- */

SFX.reload_rifle_out = handling({
  dur: 0.62, level: -22,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    // paddle/lever thrown forward
    steelHit(ctx, out, rng, { t: 0.002, f: 2500, modes: [1, 1.6, 2.4], dur: 0.026, peak: 0.36, noise: W, bright: 3400 });
    springTwang(ctx, out, rng, { t: 0.006, f: rnd(rng, 1500, 1800), dur: 0.08, peak: 0.08 });
    // the magazine rocks forward out of the trunnion — a long, heavy scrape
    railSlide(ctx, out, rng, { t: 0.03, dur: 0.15, peak: 0.26, f0: 2200, f1: 1050, q: 1.9, noise: P, grain: 520, grainF: 2600, grainAmp: 0.7 });
    // the front lug leaves the receiver
    steelHit(ctx, out, rng, { t: 0.2 + rnd(rng, 0, 0.03), f: 1150, modes: [1, 1.63, 2.42, 3.3], dur: 0.06, peak: 0.34, noise: W, bright: 1900, thud: 220, thudAmp: 0.5 });
    // thirty rounds shifting in the body
    rattle(ctx, out, rng, { t: 0.23, count: 5, spread: 0.15, f: 2500, peak: 0.075, noise: W });
    clothBrush(ctx, out, rng, { t: 0.12, dur: 0.22, peak: 0.08, noise: P });
  },
});

SFX.reload_rifle_in = handling({
  dur: 0.6, level: -20,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    rattle(ctx, out, rng, { t: 0.002, count: 4, spread: 0.06, f: 2500, peak: 0.06, noise: W });
    // front lug goes in first
    steelHit(ctx, out, rng, { t: 0.05, f: 1500, modes: [1, 1.61, 2.45], dur: 0.04, peak: 0.42, noise: W, bright: 2400, thud: 260, thudAmp: 0.35 });
    // then the whole magazine rocks back…
    railSlide(ctx, out, rng, { t: 0.09, dur: 0.075, peak: 0.2, f0: 1900, f1: 950, q: 2.0, noise: P, grain: 420, grainF: 2400 });
    // …and locks. Heavy, low, final.
    steelHit(ctx, out, rng, { t: 0.175, f: 1020, modes: [1, 1.59, 2.38, 3.35, 4.6], dur: 0.085, peak: 0.85, noise: W, bright: 1800, thud: 185, thudAmp: 0.7 });
    steelHit(ctx, out, rng, { t: 0.235, f: 3200, modes: [1, 1.72], dur: 0.016, peak: 0.18, noise: W, bright: 4600 });
  },
});

/* ---------- SMG: straight up a polymer-lined well ---------- */

SFX.reload_smg_out = handling({
  dur: 0.46, level: -23,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    steelHit(ctx, out, rng, { t: 0.002, f: 3400, modes: [1, 1.74, 2.6], dur: 0.016, peak: 0.32, noise: W, bright: 5000, noiseAmp: 1.0 });
    springTwang(ctx, out, rng, { t: 0.004, f: rnd(rng, 2600, 3100), dur: 0.045, peak: 0.07 });
    // shorter and drier than a rifle: less steel, more friction
    railSlide(ctx, out, rng, { t: 0.02, dur: 0.1, peak: 0.24, f0: 3400, f1: 1700, q: 1.4, noise: P, grain: 620, grainF: 4000, grainAmp: 0.8 });
    steelHit(ctx, out, rng, { t: 0.135 + rnd(rng, 0, 0.02), f: 1500, modes: [1, 1.68, 2.5], dur: 0.04, peak: 0.26, noise: W, bright: 2400, thud: 260, thudAmp: 0.3 });
    rattle(ctx, out, rng, { t: 0.15, count: 4, spread: 0.1, f: 3400, peak: 0.055, noise: W });
  },
});

SFX.reload_smg_in = handling({
  dur: 0.4, level: -21,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    railSlide(ctx, out, rng, { t: 0.002, dur: 0.06, peak: 0.18, f0: 1800, f1: 3400, q: 1.2, noise: P, grain: 480, grainF: 3800 });
    steelHit(ctx, out, rng, { t: 0.075, f: 1650, modes: [1, 1.7, 2.55, 3.6], dur: 0.05, peak: 0.6, noise: W, bright: 2800, thud: 285, thudAmp: 0.45 });
    steelHit(ctx, out, rng, { t: 0.11, f: 4000, modes: [1, 1.73], dur: 0.014, peak: 0.2, noise: W, bright: 5600 });
  },
});

/* ---------- LMG: a hinged top cover and a belt ---------- */

SFX.reload_lmg_out = handling({
  dur: 0.72, level: -21,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    // latch thumbed back
    steelHit(ctx, out, rng, { t: 0.002, f: 2100, modes: [1, 1.62, 2.44], dur: 0.03, peak: 0.42, noise: W, bright: 3000, thud: 320, thudAmp: 0.3 });
    springTwang(ctx, out, rng, { t: 0.01, f: rnd(rng, 1100, 1400), dur: 0.12, peak: 0.1 });
    // the cover swings up on its hinge — a big sheet of pressed steel groaning
    const cr = osc(ctx, 'sawtooth', 340);
    setAt(cr.frequency, rnd(rng, 280, 360), 0.05);
    expTo(cr.frequency, rnd(rng, 520, 660), 0.26);
    const cbp = filt(ctx, 'bandpass', 1200, 7);
    setAt(cbp.frequency, 900, 0.05); expTo(cbp.frequency, 2100, 0.26);
    const cg = gainNode(ctx, 0);
    ampEnv(cg.gain, { t: 0.05, peak: 0.16, attack: 0.05, decay: 0.22, curve: 'lin' });
    cr.connect(cbp); cbp.connect(cg); cg.connect(out);
    cr.start(0.05); cr.stop(0.34);
    // cover hits its stop
    steelHit(ctx, out, rng, { t: 0.3, f: 900, modes: [1, 1.57, 2.36, 3.2, 4.4], dur: 0.14, peak: 0.45, noise: W, bright: 1700, thud: 190, thudAmp: 0.5 });
    // the spent belt stub falling out of the tray
    rattle(ctx, out, rng, { t: 0.34, count: 6, spread: 0.2, f: 2800, peak: 0.08, noise: W });
    clothBrush(ctx, out, rng, { t: 0.1, dur: 0.3, peak: 0.07, noise: P });
  },
});

SFX.reload_lmg_belt = handling({
  dur: 0.85, level: -23,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    // a hundred linked rounds lifted out of the drum and laid across the tray:
    // dense, disorganised, unmistakably heavy
    rattle(ctx, out, rng, { t: 0.002, count: 11, spread: 0.34, f: 2400, peak: 0.1, noise: W });
    rattle(ctx, out, rng, { t: 0.08, count: 9, spread: 0.36, f: 4200, peak: 0.06, noise: W });
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.5, rng, { density: 240, amp: 0.55, skew: 0.8 }), 0.01);
    const gf = filt(ctx, 'bandpass', 2600, 1.0);
    const gg = gainNode(ctx, 0);
    ampEnv(gg.gain, { t: 0.01, peak: 0.24, attack: 0.05, decay: 0.42, curve: 'lin' });
    gr.connect(gf); gf.connect(gg); gg.connect(out);
    // the first round dropped into the feed tray and pushed against the stop
    steelHit(ctx, out, rng, { t: 0.4, f: 1700, modes: [1, 1.65, 2.5], dur: 0.05, peak: 0.34, noise: W, bright: 2600, thud: 250, thudAmp: 0.4 });
    rattle(ctx, out, rng, { t: 0.44, count: 4, spread: 0.14, f: 3000, peak: 0.07, noise: W });
    clothBrush(ctx, out, rng, { t: 0.0, dur: 0.4, peak: 0.06, noise: P });
  },
});

SFX.reload_lmg_in = handling({
  dur: 0.55, level: -19,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white;
    // the cover comes down hard and the latch snaps over
    steelHit(ctx, out, rng, { t: 0.002, f: 820, modes: [1, 1.58, 2.35, 3.25, 4.5], dur: 0.16, peak: 0.95, noise: W, bright: 1600, thud: 165, thudAmp: 0.75 });
    steelHit(ctx, out, rng, { t: 0.03, f: 1900, modes: [1, 1.66, 2.5], dur: 0.05, peak: 0.4, noise: W, bright: 2800 });
    steelHit(ctx, out, rng, { t: 0.08, f: 2600, modes: [1, 1.72], dur: 0.02, peak: 0.28, noise: W, bright: 3800 });
    rattle(ctx, out, rng, { t: 0.05, count: 3, spread: 0.08, f: 3200, peak: 0.05, noise: W });
  },
});

/* ---------- shotguns ---------- */

SFX.reload_shotgun_shell = handling({
  dur: 0.34, variants: 4, level: -22, jitter: 80, rateJit: 0.06,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    // a plastic hull is dull and squeaky, not metallic — that is the whole tell
    noiseBurst(ctx, out, {
      noise: P, t: 0.002, type: 'bandpass', f0: rnd(rng, 1500, 2100), f1: 850,
      q: 1.7, sweep: 0.055, attack: 0.004, decay: 0.065, peak: 0.3, curve: 'lin', rng,
    });
    // the brass head clicking past the shell stop
    steelHit(ctx, out, rng, { t: 0.07 + rnd(rng, 0, 0.02), f: 1450 * (1 + jit(rng, 0.08)), modes: [1, 1.68, 2.4], dur: 0.028, peak: 0.5, noise: W, bright: 2400, thud: 260, thudAmp: 0.45 });
    springTwang(ctx, out, rng, { t: 0.08, f: rnd(rng, 1300, 1700), dur: 0.06, peak: 0.06 });
  },
});

SFX.reload_break_open = handling({
  dur: 0.64, level: -20,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    // top lever pushed across its detent
    steelHit(ctx, out, rng, { t: 0.002, f: 2800, modes: [1, 1.7, 2.55], dur: 0.024, peak: 0.42, noise: W, bright: 4000 });
    railSlide(ctx, out, rng, { t: 0.01, dur: 0.06, peak: 0.16, f0: 4200, f1: 2600, q: 4, noise: W, grain: 260, grainF: 5000 });
    // the barrels rotate down on the hinge pin: a slow low creak under load
    const cr = osc(ctx, 'sawtooth', 240);
    setAt(cr.frequency, rnd(rng, 190, 250), 0.05);
    expTo(cr.frequency, rnd(rng, 420, 520), 0.3);
    const cbp = filt(ctx, 'bandpass', 900, 8);
    setAt(cbp.frequency, 760, 0.05); expTo(cbp.frequency, 1700, 0.3);
    const cg = gainNode(ctx, 0);
    ampEnv(cg.gain, { t: 0.05, peak: 0.14, attack: 0.06, decay: 0.24, curve: 'lin' });
    cr.connect(cbp); cbp.connect(cg); cg.connect(out);
    cr.start(0.05); cr.stop(0.38);
    // extractors kick, two hulls lift
    springTwang(ctx, out, rng, { t: 0.3, f: rnd(rng, 900, 1200), dur: 0.14, peak: 0.13 });
    for (let i = 0; i < 2; i++) {
      steelHit(ctx, out, rng, { t: 0.31 + i * 0.035 + rnd(rng, 0, 0.02), f: 1900 * (1 + jit(rng, 0.1)), modes: [1, 1.63, 2.4], dur: 0.03, peak: 0.24, noise: W, bright: 2800, pan: i ? 0.3 : -0.3 });
    }
    // and the barrels reach the end of their travel
    steelHit(ctx, out, rng, { t: 0.4, f: 700, modes: [1, 1.6, 2.4, 3.3], dur: 0.12, peak: 0.36, noise: W, bright: 1400, thud: 150, thudAmp: 0.55 });
    clothBrush(ctx, out, rng, { t: 0.06, dur: 0.24, peak: 0.06, noise: P });
  },
});

SFX.reload_break_close = handling({
  dur: 0.5, level: -18,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white;
    // barrel face meets standing breech: two heavy pieces of steel, dead flat
    steelHit(ctx, out, rng, { t: 0.002, f: 640, modes: [1, 1.57, 2.34, 3.2, 4.4, 5.8], dur: 0.2, peak: 1.0, noise: W, bright: 1300, thud: 130, thudAmp: 0.8 });
    // the barrels themselves ring afterwards — long, thin, tubular
    for (const m of [1, 1.72, 2.58]) {
      ping(ctx, out, { t: 0.004, freq: 1600 * m * (1 + jit(rng, 0.03)), dur: 0.3 / m, peak: 0.07 / m, type: 'triangle', pan: jit(rng, 0.3) });
    }
    // the lever snaps back over its detent
    steelHit(ctx, out, rng, { t: 0.09, f: 2900, modes: [1, 1.71, 2.6], dur: 0.022, peak: 0.34, noise: W, bright: 4200 });
    springTwang(ctx, out, rng, { t: 0.095, f: rnd(rng, 2000, 2400), dur: 0.06, peak: 0.07 });
  },
});

/* ---------- revolver ---------- */

SFX.reload_revolver_open = handling({
  dur: 0.5, level: -22,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    // thumb latch
    steelHit(ctx, out, rng, { t: 0.002, f: 3200, modes: [1, 1.72, 2.6], dur: 0.018, peak: 0.36, noise: W, bright: 4600 });
    springTwang(ctx, out, rng, { t: 0.006, f: rnd(rng, 2400, 2900), dur: 0.05, peak: 0.07 });
    // the crane swings out — light, ratchety, a small bearing turning
    railSlide(ctx, out, rng, { t: 0.04, dur: 0.11, peak: 0.16, f0: 2600, f1: 1500, q: 2.4, noise: P, grain: 200, grainF: 3200, grainAmp: 0.4 });
    for (let i = 0; i < 4; i++) {
      steelHit(ctx, out, rng, { t: 0.05 + i * 0.026 + rnd(rng, 0, 0.008), f: 4200 * (1 + jit(rng, 0.12)), modes: [1, 1.7], dur: 0.008, peak: 0.07, noise: W, bright: 6000 });
    }
    // crane reaches its stop
    steelHit(ctx, out, rng, { t: 0.18, f: 1550, modes: [1, 1.64, 2.46, 3.3], dur: 0.06, peak: 0.3, noise: W, bright: 2400, thud: 240, thudAmp: 0.35 });
  },
});

SFX.reload_revolver_eject = handling({
  dur: 0.78, level: -22,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    // ejector rod pressed against its spring
    railSlide(ctx, out, rng, { t: 0.002, dur: 0.07, peak: 0.18, f0: 3400, f1: 2000, q: 3, noise: P, grain: 180, grainF: 4200, grainAmp: 0.4 });
    springTwang(ctx, out, rng, { t: 0.01, f: rnd(rng, 1400, 1800), dur: 0.16, peak: 0.12 });
    // six cases lift together as one ring of brass
    for (let i = 0; i < 6; i++) {
      ping(ctx, out, {
        t: 0.06 + rnd(rng, 0, 0.012), freq: rnd(rng, 2900, 3800), dur: 0.09,
        peak: 0.07, mod: 2.41, index: 0.7, pan: Math.cos((i / 6) * 6.283) * 0.4,
      });
    }
    steelHit(ctx, out, rng, { t: 0.075, f: 1200, modes: [1, 1.6, 2.4], dur: 0.05, peak: 0.26, noise: W, bright: 2000, thud: 210, thudAmp: 0.35 });
    // …and then fall out, bouncing off each other on the way
    for (let i = 0; i < 6; i++) {
      const t0 = 0.16 + rnd(rng, 0, 0.22);
      const f = rnd(rng, 2500, 3900);
      let amp = rnd(rng, 0.045, 0.085), t = t0;
      for (let b = 0; b < 3 && amp > 0.012; b++) {
        ping(ctx, out, { t, freq: f * (1 + jit(rng, 0.1)), dur: 0.1, peak: amp, mod: 2.4, index: 0.8, pan: rnd(rng, -0.6, 0.6) });
        t += rnd(rng, 0.045, 0.1) * (1 + b * 0.5);
        amp *= rnd(rng, 0.4, 0.6);
      }
    }
  },
});

SFX.reload_revolver_close = handling({
  dur: 0.42, level: -20,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    railSlide(ctx, out, rng, { t: 0.002, dur: 0.055, peak: 0.14, f0: 1800, f1: 2800, q: 2.4, noise: P, grain: 180, grainF: 3200, grainAmp: 0.4 });
    // the cylinder seats and the crane latch snaps: crisp, expensive, precise
    steelHit(ctx, out, rng, { t: 0.07, f: 1350, modes: [1, 1.61, 2.42, 3.35, 4.6], dur: 0.075, peak: 0.8, noise: W, bright: 2200, thud: 220, thudAmp: 0.55 });
    steelHit(ctx, out, rng, { t: 0.095, f: 3400, modes: [1, 1.73], dur: 0.014, peak: 0.26, noise: W, bright: 5000 });
    ping(ctx, out, { t: 0.07, freq: 2900, dur: 0.14, peak: 0.05, type: 'triangle' });
  },
});

/* ---------- ray gun ---------- */

SFX.reload_raygun_out = handling({
  dur: 0.66, level: -20, variants: 2,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white;
    // magnetic clamp releases
    steelHit(ctx, out, rng, { t: 0.002, f: 900, modes: [1, 1.49, 2.1], dur: 0.09, peak: 0.42, noise: W, bright: 1800, thud: 180, thudAmp: 0.5 });
    // servo winding down
    const s = osc(ctx, 'sawtooth', 900);
    setAt(s.frequency, rnd(rng, 800, 1000), 0.01);
    expTo(s.frequency, 180, 0.32);
    const sbp = filt(ctx, 'bandpass', 1400, 6);
    setAt(sbp.frequency, 2200, 0.01); expTo(sbp.frequency, 420, 0.32);
    const sg = gainNode(ctx, 0);
    ampEnv(sg.gain, { t: 0.01, peak: 0.2, attack: 0.02, decay: 0.3, curve: 'lin' });
    s.connect(sbp); sbp.connect(sg); sg.connect(out);
    s.start(0.01); s.stop(0.4);
    // the canister depressurising
    noiseBurst(ctx, out, {
      noise: W, t: 0.06, type: 'bandpass', f0: 5200, f1: 1600, q: 1.1,
      sweep: 0.26, attack: 0.012, decay: 0.3, peak: 0.24, curve: 'lin', rng,
    });
    // residual charge bleeding off
    const sz = bufSrc(ctx, crackleBuffer(ctx, 0.4, rng, { density: 40, fLo: 2400, fHi: 9000, amp: 0.5 }), 0.12);
    const zg = gainNode(ctx, 0);
    ampEnv(zg.gain, { t: 0.12, peak: 0.14, attack: 0.02, decay: 0.34 });
    sz.connect(zg); zg.connect(out);
  },
});

SFX.reload_raygun_in = handling({
  dur: 0.98, level: -18, variants: 2,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white;
    // the fresh canister slides home
    noiseBurst(ctx, out, {
      noise: W, t: 0.002, type: 'bandpass', f0: 1200, f1: 3400, q: 1.6,
      sweep: 0.1, attack: 0.01, decay: 0.12, peak: 0.2, curve: 'lin', rng,
    });
    steelHit(ctx, out, rng, { t: 0.13, f: 820, modes: [1, 1.52, 2.16, 3.0], dur: 0.12, peak: 0.7, noise: W, bright: 1700, thud: 150, thudAmp: 0.7 });
    // and the weapon spools back up to ready
    const ch = osc(ctx, 'sawtooth', 120);
    setAt(ch.frequency, 110, 0.16); expTo(ch.frequency, 880, 0.66);
    const cbp = filt(ctx, 'bandpass', 700, 7);
    setAt(cbp.frequency, 420, 0.16); expTo(cbp.frequency, 3800, 0.66);
    const cg = gainNode(ctx, 0);
    ampEnv(cg.gain, { t: 0.16, peak: 0.24, attack: 0.3, decay: 0.28, curve: 'lin' });
    ch.connect(cbp); cbp.connect(cg); cg.connect(out);
    ch.start(0.16); ch.stop(0.9);
    // ready chirp
    ping(ctx, out, { t: 0.7, freq: 1760, dur: 0.16, peak: 0.16, mod: 2.0, index: 0.5, type: 'triangle' });
    ping(ctx, out, { t: 0.74, freq: 2640, dur: 0.2, peak: 0.12, mod: 2.0, index: 0.5 });
    const sz = bufSrc(ctx, crackleBuffer(ctx, 0.35, rng, { density: 55, fLo: 3000, fHi: 11000, amp: 0.5 }), 0.68);
    const zg = gainNode(ctx, 0);
    ampEnv(zg.gain, { t: 0.68, peak: 0.12, attack: 0.02, decay: 0.26 });
    sz.connect(zg); zg.connect(out);
  },
});

/* ---------- bolts, slides and pumps ---------- */

SFX.bolt_pull = handling({
  dur: 0.36, level: -21,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    clothBrush(ctx, out, rng, { t: 0.0, dur: 0.06, f0: 3000, f1: 5000, peak: 0.08, noise: P });
    // carrier dragged back against the recoil spring: the band *rises* because
    // the spring is being wound tighter as the hand pulls
    railSlide(ctx, out, rng, { t: 0.01, dur: 0.085, peak: 0.32, f0: 1500, f1: 3000, q: 1.7, noise: P, grain: 560, grainF: 3000, grainAmp: 0.8, skew: 1.4 });
    springTwang(ctx, out, rng, { t: 0.015, f: rnd(rng, 700, 900), dur: 0.12, peak: 0.09 });
    // and hits the rear of its travel
    steelHit(ctx, out, rng, { t: 0.1, f: 1250, modes: [1, 1.6, 2.4, 3.3, 4.5], dur: 0.06, peak: 0.55, noise: W, bright: 2000, thud: 210, thudAmp: 0.5 });
  },
});

SFX.bolt_release = handling({
  dur: 0.32, level: -19,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    // spring throws it forward — fast, so the friction band falls
    railSlide(ctx, out, rng, { t: 0.0, dur: 0.045, peak: 0.28, f0: 3000, f1: 1300, q: 1.8, noise: P, grain: 620, grainF: 2800, grainAmp: 0.8, skew: 0.6 });
    // into battery: the loudest single mechanical event on a rifle
    steelHit(ctx, out, rng, { t: 0.05, f: 960, modes: [1, 1.58, 2.36, 3.24, 4.45, 5.9], dur: 0.11, peak: 1.0, noise: W, bright: 1750, thud: 170, thudAmp: 0.75 });
    steelHit(ctx, out, rng, { t: 0.068, f: 2700, modes: [1, 1.7], dur: 0.02, peak: 0.24, noise: W, bright: 3800 });
  },
});

SFX.slide_release = handling({
  dur: 0.3, level: -19,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    // shorter travel and less mass than a rifle bolt: brighter and quicker
    railSlide(ctx, out, rng, { t: 0.0, dur: 0.026, peak: 0.26, f0: 3800, f1: 1900, q: 1.6, noise: P, grain: 560, grainF: 3600, grainAmp: 0.7, skew: 0.6 });
    steelHit(ctx, out, rng, { t: 0.03, f: 1420, modes: [1, 1.62, 2.44, 3.35, 4.6], dur: 0.075, peak: 0.95, noise: W, bright: 2400, thud: 250, thudAmp: 0.6 });
    steelHit(ctx, out, rng, { t: 0.045, f: 3600, modes: [1, 1.72], dur: 0.014, peak: 0.22, noise: W, bright: 5200 });
  },
});

SFX.pump_back = handling({
  dur: 0.44, level: -20,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    // forend sliding back along the magazine tube
    railSlide(ctx, out, rng, { t: 0.0, dur: 0.1, peak: 0.34, f0: 2000, f1: 1000, q: 1.5, noise: P, grain: 700, grainF: 2200, grainAmp: 0.9, skew: 1.2 });
    // extractor drags the hull out and the ejector kicks it clear
    steelHit(ctx, out, rng, { t: 0.055, f: 1750, modes: [1, 1.66, 2.5], dur: 0.035, peak: 0.34, noise: W, bright: 2600 });
    ping(ctx, out, { t: 0.09, freq: rnd(rng, 1500, 2100), dur: 0.1, peak: 0.1, mod: 2.3, index: 0.7, pan: rnd(rng, 0.25, 0.6) });
    // action bars hit the rear stop
    steelHit(ctx, out, rng, { t: 0.115, f: 1050, modes: [1, 1.59, 2.38, 3.3], dur: 0.08, peak: 0.6, noise: W, bright: 1800, thud: 195, thudAmp: 0.6 });
    springTwang(ctx, out, rng, { t: 0.02, f: rnd(rng, 620, 820), dur: 0.14, peak: 0.08 });
  },
});

SFX.pump_forward = handling({
  dur: 0.44, level: -19,
  build(ctx, out, rng, v, lib) {
    const W = lib.noise.white, P = lib.noise.pink;
    railSlide(ctx, out, rng, { t: 0.0, dur: 0.085, peak: 0.32, f0: 2200, f1: 1150, q: 1.5, noise: P, grain: 700, grainF: 2300, grainAmp: 0.9, skew: 0.7 });
    // the carrier lifts and rams a fresh shell into the chamber
    noiseBurst(ctx, out, {
      noise: P, t: 0.03, type: 'bandpass', f0: 1700, f1: 900, q: 1.6,
      sweep: 0.05, attack: 0.004, decay: 0.06, peak: 0.24, curve: 'lin', rng,
    });
    // lock-up — the sound that means the 870 is ready
    steelHit(ctx, out, rng, { t: 0.095, f: 880, modes: [1, 1.57, 2.35, 3.22, 4.4], dur: 0.13, peak: 1.0, noise: W, bright: 1650, thud: 160, thudAmp: 0.8 });
    steelHit(ctx, out, rng, { t: 0.115, f: 2400, modes: [1, 1.71], dur: 0.018, peak: 0.24, noise: W, bright: 3400 });
  },
});

/* ---------- brass on the ground ---------- */

SFX.shell_drop = {
  dur: 0.9, variants: 5, gain: 1.0, jitter: 90, rateJit: 0.1, level: -23,
  build(ctx, out, rng, v, lib) {
    // A case does not land flat: it hits on the rim, spins, bounces shorter and
    // shorter, and the last two bounces run into each other. The bounce
    // intervals shrink geometrically and the amplitude with them.
    let t = 0.002;
    let amp = 0.5;
    let gap = rnd(rng, 0.055, 0.1);
    const base = rnd(rng, 2600, 4400);
    const pan0 = rnd(rng, -0.5, 0.5);
    for (let i = 0; i < 6 && amp > 0.02; i++) {
      const f = base * (1 + jit(rng, 0.1));
      const pan = clamp(pan0 + jit(rng, 0.25), -1, 1);
      ping(ctx, out, { t, freq: f, dur: 0.17 * (1 - i * 0.1), peak: amp * 0.55, mod: 2.41, index: 0.9, pan });
      ping(ctx, out, { t, freq: f * 1.73, dur: 0.1, peak: amp * 0.3, pan });
      clack(ctx, out, { t, freqs: [f * 0.58, f * 1.21], dur: 0.01, peak: amp * 0.55, noise: lib.noise.white, bright: 4800, rng });
      // the concrete it lands on
      thump(ctx, out, { t, f0: rnd(rng, 320, 430), f1: 150, dur: 0.028, peak: amp * 0.22, type: 'triangle' });
      t += gap;
      gap *= rnd(rng, 0.62, 0.8);
      amp *= rnd(rng, 0.44, 0.62);
    }
  },
};

SFX.shell_drop_shotgun = {
  dur: 0.7, variants: 4, gain: 1.0, jitter: 70, rateJit: 0.08, level: -22,
  build(ctx, out, rng, v, lib) {
    // a plastic hull with a brass head: one dull slap, one weak second bounce,
    // and it stays where it lands
    let t = 0.002, amp = 0.75;
    const pan = rnd(rng, -0.5, 0.5);
    for (let i = 0; i < 3 && amp > 0.06; i++) {
      noiseBurst(ctx, out, {
        noise: lib.noise.pink, t, type: 'bandpass', f0: rnd(rng, 700, 1100), q: 1.1,
        attack: 0.0008, decay: 0.05, peak: amp * 0.7, pan, rng,
      });
      thump(ctx, out, { t, f0: rnd(rng, 230, 310), f1: 110, dur: 0.05, peak: amp * 0.5, type: 'triangle', drive: 2 });
      // the brass rim, much quieter than a rifle case
      ping(ctx, out, { t, freq: rnd(rng, 1700, 2400), dur: 0.05, peak: amp * 0.13, pan });
      t += rnd(rng, 0.08, 0.15) * (1 + i);
      amp *= rnd(rng, 0.32, 0.46);
    }
  },
};

/* ================================================================== *
 * Bullet impacts, one recipe per surface
 *
 * Seventy per cent of wall hits used to be silent and every surface in the game
 * — cars, wooden houses, oil drums, dirt — produced the same concrete tick.
 * ================================================================== */

/** The part every impact shares: the round arriving, before the surface answers. */
function impactStrike(ctx, out, rng, lib, o) {
  noiseBurst(ctx, out, {
    noise: lib.noise.white, t: 0, type: 'highpass', f0: o.tick ?? 3400, q: 0.7,
    attack: 0.0003, decay: o.tickDec ?? 0.025, peak: o.tickAmp ?? 0.85, rng,
  });
}

/** A ricochet peeling away — a falling whine with a flutter on it. */
function ricochet(ctx, out, rng, o = {}) {
  const t = o.t ?? 0.004;
  const o1 = osc(ctx, 'sine', 3000);
  const f0 = o.f0 ?? rnd(rng, 2400, 3800);
  setAt(o1.frequency, f0, t);
  expTo(o1.frequency, f0 * rnd(rng, 0.22, 0.42), t + (o.dur ?? 0.42));
  const vib = osc(ctx, 'sine', rnd(rng, 9, 24));
  const vg = gainNode(ctx, rnd(rng, 30, 110));
  vib.connect(vg); vg.connect(o1.detune);
  vib.start(t); vib.stop(t + (o.dur ?? 0.42) + 0.1);
  const g = gainNode(ctx, 0);
  ampEnv(g.gain, { t, peak: o.peak ?? 0.22, attack: 0.004, decay: o.dur ?? 0.42 });
  const p = panner(ctx, o.pan != null ? o.pan : rnd(rng, -0.85, 0.85));
  o1.connect(g); g.connect(p); p.connect(out);
  o1.start(t); o1.stop(t + (o.dur ?? 0.42) + 0.15);
}

SFX.impact_concrete = {
  dur: 0.9, variants: 4, gain: 1.0, jitter: 110, rateJit: 0.08, level: -18,
  build(ctx, out, rng, v, lib) {
    impactStrike(ctx, out, rng, lib, { tick: rnd(rng, 2800, 4400), tickDec: 0.028 });
    // the crater: a dry burst with no ring at all
    noiseBurst(ctx, out, { noise: lib.noise.pink, t: 0.001, type: 'bandpass', f0: rnd(rng, 900, 1600), f1: 320, q: 1.4, sweep: 0.06, attack: 0.001, decay: 0.09, peak: 0.55, drive: 4, rng });
    thump(ctx, out, { t: 0.001, f0: 260, f1: 70, dur: 0.07, peak: 0.3, drive: 2 });
    // dust and grit coming off the wall
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.55, rng, { density: 180, amp: 0.5, skew: 0.5 }), 0.01);
    const gf = filt(ctx, 'highpass', 1800, 0.7);
    const gg = gainNode(ctx, 0);
    ampEnv(gg.gain, { t: 0.01, peak: 0.28, attack: 0.008, decay: 0.45 });
    gr.connect(gf); gf.connect(gg); gg.connect(out);
    if (rng() < 0.4) ricochet(ctx, out, rng, { peak: 0.2 });
  },
};

SFX.impact_wood = {
  dur: 0.7, variants: 4, gain: 1.0, jitter: 110, rateJit: 0.08, level: -18,
  build(ctx, out, rng, v, lib) {
    impactStrike(ctx, out, rng, lib, { tick: rnd(rng, 2000, 3000), tickDec: 0.018, tickAmp: 0.6 });
    // wood does not ring, it *knocks* — low resonant modes and a splinter rip
    const base = rnd(rng, 190, 300);
    woodModes(ctx, out, rng, 0.001, 0.34, 0.16, base);
    thump(ctx, out, { t: 0.001, f0: base * 1.1, f1: base * 0.42, dur: 0.09, peak: 0.55, type: 'triangle', drive: 3 });
    noiseBurst(ctx, out, { noise: lib.noise.pink, t: 0.001, type: 'bandpass', f0: rnd(rng, 1100, 1700), f1: 500, q: 1.1, sweep: 0.05, attack: 0.0008, decay: 0.07, peak: 0.45, drive: 3, rng });
    // splinters
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.28, rng, { density: 260, amp: 0.5, skew: 0.6 }), 0.006);
    const gf = filt(ctx, 'bandpass', 2600, 0.9);
    const gg = gainNode(ctx, 0);
    ampEnv(gg.gain, { t: 0.006, peak: 0.24, attack: 0.004, decay: 0.22 });
    gr.connect(gf); gf.connect(gg); gg.connect(out);
  },
};

SFX.impact_metal = {
  dur: 1.1, variants: 4, gain: 1.0, jitter: 120, rateJit: 0.08, level: -17,
  build(ctx, out, rng, v, lib) {
    impactStrike(ctx, out, rng, lib, { tick: rnd(rng, 4000, 6000), tickDec: 0.02, tickAmp: 1.0 });
    // sheet steel: a hard strike into a big inharmonic plate that keeps ringing
    const base = rnd(rng, 620, 1100);
    for (const m of [1, 1.59, 2.14, 2.92, 3.86, 5.4, 7.1]) {
      ping(ctx, out, {
        t: 0.001, freq: base * m * (1 + jit(rng, 0.05)),
        dur: 0.55 / Math.sqrt(m), peak: 0.3 / m, type: m < 2 ? 'triangle' : 'sine',
        pan: jit(rng, 0.35),
      });
    }
    // the dent
    thump(ctx, out, { t: 0.001, f0: 300, f1: 90, dur: 0.09, peak: 0.4, type: 'triangle', drive: 3 });
    noiseBurst(ctx, out, { noise: lib.noise.white, t: 0.001, type: 'bandpass', f0: 2800, f1: 900, q: 1.0, sweep: 0.05, attack: 0.0006, decay: 0.07, peak: 0.5, drive: 5, rng });
    // metal ricochets far more often than concrete does
    if (rng() < 0.8) ricochet(ctx, out, rng, { peak: 0.3, dur: rnd(rng, 0.4, 0.62) });
  },
};

SFX.impact_dirt = {
  dur: 0.6, variants: 4, gain: 1.0, jitter: 120, rateJit: 0.1, level: -20,
  build(ctx, out, rng, v, lib) {
    // no tick, no ring: the round just buries itself
    noiseBurst(ctx, out, { noise: lib.noise.brown, t: 0.001, type: 'lowpass', f0: rnd(rng, 700, 1200), f1: 180, q: 1.5, sweep: 0.07, attack: 0.001, decay: 0.1, peak: 0.8, drive: 3, rng });
    thump(ctx, out, { t: 0.001, f0: rnd(rng, 150, 210), f1: 55, dur: 0.1, peak: 0.55, drive: 2 });
    // the spray of soil coming back down
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.4, rng, { density: 420, amp: 0.6, skew: 0.45 }), 0.008);
    const gf = filt(ctx, 'bandpass', rnd(rng, 900, 1500), 0.8);
    const gg = gainNode(ctx, 0);
    ampEnv(gg.gain, { t: 0.008, peak: 0.34, attack: 0.006, decay: 0.34 });
    gr.connect(gf); gf.connect(gg); gg.connect(out);
  },
};

SFX.impact_glass = {
  dur: 1.2, variants: 3, gain: 1.0, jitter: 130, rateJit: 0.08, level: -18,
  build(ctx, out, rng, v, lib) {
    // the pane breaks, then falls
    noiseBurst(ctx, out, { noise: lib.noise.white, t: 0, type: 'highpass', f0: 5000, q: 0.6, attack: 0.0003, decay: 0.03, peak: 0.9, rng });
    for (let i = 0; i < 5; i++) {
      ping(ctx, out, { t: 0.001 + i * 0.002, freq: rnd(rng, 3200, 9000), dur: rnd(rng, 0.08, 0.3), peak: 0.13 / (i + 1), pan: jit(rng, 0.7) });
    }
    // shards landing
    for (let i = 0; i < 14; i++) {
      const t = 0.05 + Math.pow(rng(), 1.5) * 0.7;
      ping(ctx, out, { t, freq: rnd(rng, 2600, 8000), dur: rnd(rng, 0.03, 0.12), peak: rnd(rng, 0.02, 0.09), pan: rnd(rng, -0.8, 0.8) });
    }
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.9, rng, { density: 150, amp: 0.45, skew: 1.4 }), 0.04);
    const gf = filt(ctx, 'highpass', 3400, 0.7);
    const gg = gainNode(ctx, 0);
    ampEnv(gg.gain, { t: 0.04, peak: 0.22, attack: 0.01, decay: 0.75, curve: 'lin' });
    gr.connect(gf); gf.connect(gg); gg.connect(out);
  },
};

/* ================================================================== *
 * Zombie physicality
 *
 * Two dozen zombies used to sprint at the player in total silence except for
 * moaning: no footsteps, no body hitting the ground, no limbs coming off. The
 * horde has to be *heard* arriving, not just seen.
 * ================================================================== */

SFX.zombie_footstep = {
  dur: 0.32, variants: 6, gain: 1.0, jitter: 170, rateJit: 0.14, level: -27,
  build(ctx, out, rng, v, lib) {
    // a heavy, badly-controlled body: the foot scuffs before it lands, and the
    // weight arrives all at once. Everything above ~2 kHz is gone — these are
    // heard across a street, not next to your ear.
    const drag = v % 2 === 0;
    if (drag) {
      noiseBurst(ctx, out, {
        noise: lib.noise.pink, t: 0.0, type: 'bandpass', f0: rnd(rng, 700, 1100), f1: 420,
        q: 0.9, sweep: 0.08, attack: 0.02, decay: 0.09, peak: 0.28, curve: 'lin', rng,
      });
    }
    const t0 = drag ? 0.055 : 0.002;
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.14, rng, { density: 520, amp: 0.8, skew: 0.35 }), t0);
    const bp = filt(ctx, 'bandpass', rnd(rng, 520, 900), 0.8);
    const lp = filt(ctx, 'lowpass', 1900, 0.7);
    const g = gainNode(ctx, 0);
    ampEnv(g.gain, { t: t0, peak: 0.7, attack: 0.004, decay: 0.1 });
    gr.connect(bp); bp.connect(lp); lp.connect(g); g.connect(out);
    // the mass behind it
    thump(ctx, out, { t: t0, f0: rnd(rng, 90, 125), f1: 44, dur: 0.1, peak: 0.55, drive: 2 });
    // a loose boot or a dragging heel
    if (rng() < 0.4) {
      clack(ctx, out, { t: t0 + rnd(rng, 0.01, 0.03), freqs: [rnd(rng, 600, 1100), rnd(rng, 1500, 2400)], dur: 0.02, peak: 0.06, rng });
    }
  },
};

SFX.zombie_bodyfall = {
  dur: 1.0, variants: 3, gain: 1.0, jitter: 120, rateJit: 0.08, level: -19,
  build(ctx, out, rng, v, lib) {
    // 80 kg of dead weight landing: a wet low thud, the cloth around it
    // collapsing, a bone knocking the ground, and grit underneath
    thump(ctx, out, { t: 0.002, f0: rnd(rng, 95, 125), f1: 26, dur: 0.42, peak: 1.0, drive: 4 });
    noiseBurst(ctx, out, { noise: lib.noise.brown, t: 0.002, type: 'lowpass', f0: 760, f1: 130, q: 1.5, sweep: 0.18, attack: 0.002, decay: 0.3, peak: 0.6, drive: 3, rng });
    // the meat of it
    noiseBurst(ctx, out, { noise: lib.noise.brown, t: 0.004, type: 'bandpass', f0: rnd(rng, 260, 420), f1: 150, q: 2.2, sweep: 0.12, attack: 0.002, decay: 0.16, peak: 0.45, drive: 3, rng });
    // cloth
    clothBrush(ctx, out, rng, { t: 0.01, dur: 0.3, f0: 1600, f1: 3600, peak: 0.16, noise: lib.noise.pink });
    // a second, smaller impact as a limb follows the torso down
    const t2 = rnd(rng, 0.11, 0.19);
    thump(ctx, out, { t: t2, f0: rnd(rng, 130, 180), f1: 45, dur: 0.16, peak: 0.4, type: 'triangle', drive: 3 });
    clack(ctx, out, { t: t2, freqs: [rnd(rng, 420, 700), rnd(rng, 900, 1500)], dur: 0.03, peak: 0.12, noise: lib.noise.white, bright: 1400, rng });
    // grit and dust
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.55, rng, { density: 260, amp: 0.55, skew: 0.5 }), 0.008);
    const gf = filt(ctx, 'bandpass', 1300, 0.9);
    const gg = gainNode(ctx, 0);
    ampEnv(gg.gain, { t: 0.008, peak: 0.26, attack: 0.008, decay: 0.45 });
    gr.connect(gf); gf.connect(gg); gg.connect(out);
  },
};

SFX.zombie_gib = {
  dur: 1.0, variants: 3, gain: 1.0, jitter: 140, rateJit: 0.08, level: -17,
  build(ctx, out, rng, v, lib) {
    // something comes apart: pressure release, tissue tearing, bone snapping,
    // and then the parts landing over the next half second
    noiseBurst(ctx, out, { noise: lib.noise.brown, t: 0.001, type: 'lowpass', f0: rnd(rng, 1300, 2000), f1: 220, q: 2.4, sweep: 0.1, attack: 0.0008, decay: 0.15, peak: 1.0, drive: 5, rng });
    thump(ctx, out, { t: 0.001, f0: rnd(rng, 170, 230), f1: 42, dur: 0.22, peak: 0.75, drive: 4 });
    // the tear: a band of noise sweeping *up* as the fibres let go one by one
    noiseBurst(ctx, out, { noise: lib.noise.pink, t: 0.004, type: 'bandpass', f0: 700, f1: 2600, q: 1.1, sweep: 0.11, attack: 0.004, decay: 0.16, peak: 0.5, drive: 3, curve: 'lin', rng });
    // bone
    clack(ctx, out, { t: 0.006, freqs: [rnd(rng, 700, 1100), rnd(rng, 1700, 2400), rnd(rng, 3200, 4200)], dur: 0.035, peak: 0.45, noise: lib.noise.white, bright: 2600, rng });
    // gristle and spatter
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.45, rng, { density: 340, amp: 0.7, skew: 0.5 }), 0.008);
    const gf = filt(ctx, 'bandpass', rnd(rng, 800, 1400), 1.2);
    const gg = gainNode(ctx, 0);
    ampEnv(gg.gain, { t: 0.008, peak: 0.45, attack: 0.004, decay: 0.36 });
    gr.connect(gf); gf.connect(gg); gg.connect(out);
    // pieces hitting the ground
    for (let i = 0; i < 4; i++) {
      const t = 0.14 + Math.pow(rng(), 1.3) * 0.5;
      noiseBurst(ctx, out, {
        noise: lib.noise.brown, t, type: 'lowpass', f0: rnd(rng, 400, 800), f1: 160,
        q: 1.8, sweep: 0.05, attack: 0.001, decay: 0.07, peak: rnd(rng, 0.12, 0.3),
        pan: rnd(rng, -0.7, 0.7), rng,
      });
      thump(ctx, out, { t, f0: rnd(rng, 110, 170), f1: 50, dur: 0.07, peak: rnd(rng, 0.08, 0.2), type: 'triangle' });
    }
  },
};

SFX.hellhound_footstep = {
  dur: 0.26, variants: 4, gain: 1.0, jitter: 180, rateJit: 0.15, level: -26,
  build(ctx, out, rng, v, lib) {
    // claws first, pad second — the tick is what makes it read as an animal
    for (let i = 0; i < 3; i++) {
      clack(ctx, out, {
        t: 0.001 + i * rnd(rng, 0.004, 0.012),
        freqs: [rnd(rng, 2600, 4200), rnd(rng, 5000, 7500)],
        dur: rnd(rng, 0.008, 0.016), peak: rnd(rng, 0.14, 0.3),
        noise: lib.noise.white, bright: 5200, rng,
      });
    }
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.1, rng, { density: 420, amp: 0.6, skew: 0.4 }), 0.012);
    const bp = filt(ctx, 'bandpass', rnd(rng, 900, 1500), 0.9);
    const g = gainNode(ctx, 0);
    ampEnv(g.gain, { t: 0.012, peak: 0.4, attack: 0.002, decay: 0.06 });
    gr.connect(bp); bp.connect(g); g.connect(out);
    thump(ctx, out, { t: 0.012, f0: rnd(rng, 130, 180), f1: 62, dur: 0.05, peak: 0.3, type: 'triangle' });
    // the ember trail they leave behind
    if (rng() < 0.5) {
      const sz = bufSrc(ctx, crackleBuffer(ctx, 0.14, rng, { density: 40, fLo: 2500, fHi: 8000, amp: 0.35 }), 0.01);
      const zg = gainNode(ctx, 0.08);
      sz.connect(zg); zg.connect(out);
    }
  },
};

SFX.hellhound_death = {
  dur: 2.0, variants: 3, gain: 1.0, jitter: 110, rateJit: 0.06, level: -17,
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 1.6, damp: 2400, preDelay: 0.012, gain: 0.3 });
    rev.output.connect(out);
    const dur = rnd(rng, 0.7, 0.95);
    // a yelp that collapses into a gurgle
    const vo = zombieVoice(ctx, out, lib, rng, {
      t: 0.004, dur,
      f0a: rnd(rng, 210, 270), f0b: rnd(rng, 52, 72),
      curve: (p) => Math.pow(p, 0.5),
      vowel: 'ae', vowel2: 'o', morphAt: 0.16, morphDur: 0.5, fscale: 0.8, bwScale: 2.0,
      jitter: 0.09, shimmer: 0.42, rough: 0.55, breath: 0.3, oq: 0.5,
      growl: 0.35, drive: 8, postLp: 3400, direct: 0.42,
      peak: 0.9, attack: 0.01, release: dur * 0.5, air: 0.1,
      wobble: 0.16, rattle: 0.25, rattleDensity: 150, rattleF: 420,
    });
    vo.out.connect(rev.input);
    // it burns out rather than falling over: the fire that carries them leaves
    const t0 = dur * 0.65;
    noiseBurst(ctx, out, { noise: lib.noise.white, t: t0, type: 'bandpass', f0: 4200, f1: 600, q: 0.9, sweep: 0.45, attack: 0.02, decay: 0.6, peak: 0.3, curve: 'lin', rng });
    const sz = bufSrc(ctx, crackleBuffer(ctx, 0.9, rng, { density: 110, fLo: 900, fHi: 7000, amp: 0.6 }), t0);
    const zg = gainNode(ctx, 0);
    ampEnv(zg.gain, { t: t0, peak: 0.34, attack: 0.03, decay: 0.75 });
    sz.connect(zg); zg.connect(out); zg.connect(rev.input);
    // and the body still hits the ground
    thump(ctx, out, { t: t0 + 0.04, f0: 105, f1: 28, dur: 0.3, peak: 0.55, drive: 3 });
    noiseBurst(ctx, out, { noise: lib.noise.brown, t: t0 + 0.04, type: 'lowpass', f0: 700, f1: 140, q: 1.4, sweep: 0.16, attack: 0.002, decay: 0.24, peak: 0.36, rng });
    // a last descending ember hiss
    const wh = osc(ctx, 'sine', 900);
    setAt(wh.frequency, rnd(rng, 700, 1000), t0 + 0.1);
    expTo(wh.frequency, 120, t0 + 1.0);
    const wg = gainNode(ctx, 0);
    ampEnv(wg.gain, { t: t0 + 0.1, peak: 0.07, attack: 0.08, decay: 0.85, curve: 'lin' });
    wh.connect(wg); wg.connect(rev.input); wg.connect(out);
    wh.start(t0 + 0.1); wh.stop(t0 + 1.2);
  },
};

/* ================================================================== *
 * Player foley
 * ================================================================== */

SFX.footstep_concrete = {
  dur: 0.3, variants: 4, gain: 1.0, jitter: 130, rateJit: 0.12, level: -24,
  build(ctx, out, rng, v, lib) {
    // boot leather on bare concrete: a hard slap with a little grit, no body
    noiseBurst(ctx, out, { noise: lib.noise.white, t: 0.001, type: 'bandpass', f0: rnd(rng, 2200, 3600), q: 0.8, attack: 0.0006, decay: 0.035, peak: 0.55, rng });
    noiseBurst(ctx, out, { noise: lib.noise.pink, t: 0.001, type: 'bandpass', f0: rnd(rng, 900, 1400), q: 1.0, attack: 0.001, decay: 0.07, peak: 0.45, rng });
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.1, rng, { density: 380, amp: 0.45, skew: 0.4 }), 0.002);
    const gf = filt(ctx, 'highpass', 2600, 0.7);
    const gg = gainNode(ctx, 0);
    ampEnv(gg.gain, { t: 0.002, peak: 0.2, attack: 0.002, decay: 0.08 });
    gr.connect(gf); gf.connect(gg); gg.connect(out);
    thump(ctx, out, { t: 0.001, f0: rnd(rng, 150, 200), f1: 78, dur: 0.05, peak: 0.3, type: 'triangle', drive: 2 });
  },
};

SFX.land_soft = {
  dur: 0.4, variants: 3, gain: 1.0, jitter: 90, rateJit: 0.08, level: -22,
  build(ctx, out, rng, v, lib) {
    thump(ctx, out, { t: 0.001, f0: rnd(rng, 110, 150), f1: 48, dur: 0.16, peak: 0.8, drive: 3 });
    noiseBurst(ctx, out, { noise: lib.noise.pink, t: 0.001, type: 'bandpass', f0: 1200, f1: 500, q: 0.9, sweep: 0.06, attack: 0.001, decay: 0.1, peak: 0.4, rng });
    clothBrush(ctx, out, rng, { t: 0.006, dur: 0.16, peak: 0.12, noise: lib.noise.pink });
  },
};

SFX.land_hard = {
  dur: 0.7, variants: 3, gain: 1.0, jitter: 70, rateJit: 0.06, level: -19,
  build(ctx, out, rng, v, lib) {
    // knees, gear, and the breath knocked half out of you
    thump(ctx, out, { t: 0.001, f0: rnd(rng, 95, 125), f1: 30, dur: 0.32, peak: 1.0, drive: 4 });
    noiseBurst(ctx, out, { noise: lib.noise.brown, t: 0.001, type: 'lowpass', f0: 1100, f1: 180, q: 1.5, sweep: 0.12, attack: 0.001, decay: 0.2, peak: 0.6, drive: 3, rng });
    clothBrush(ctx, out, rng, { t: 0.004, dur: 0.24, peak: 0.2, noise: lib.noise.pink });
    rattle(ctx, out, rng, { t: 0.01, count: 4, spread: 0.1, f: 2600, peak: 0.07, noise: lib.noise.white });
    zombieVoice(ctx, out, lib, rng, {
      t: 0.02, dur: 0.22, f0a: rnd(rng, 110, 130), f0b: rnd(rng, 78, 92),
      vowel: 'uh', vowel2: 'a', morphAt: 0.4, jitter: 0.02, shimmer: 0.12, rough: 0,
      breath: 0.4, growl: 0, drive: 2.5, peak: 0.34, attack: 0.012, release: 0.14, air: 0.14,
    });
  },
};

SFX.jump_grunt = {
  dur: 0.5, variants: 4, gain: 1.0, jitter: 130, rateJit: 0.08, level: -24,
  build(ctx, out, rng, v, lib) {
    zombieVoice(ctx, out, lib, rng, {
      t: 0.004, dur: rnd(rng, 0.17, 0.24),
      f0a: rnd(rng, 125, 150), f0b: rnd(rng, 88, 104),
      vowel: 'uh', vowel2: 'o', morphAt: 0.35,
      jitter: 0.02, shimmer: 0.12, rough: 0, breath: 0.42, growl: 0,
      drive: 2.5, peak: 0.6, attack: 0.012, release: 0.12, air: 0.16,
    });
    clothBrush(ctx, out, rng, { t: 0.0, dur: 0.18, peak: 0.1, noise: lib.noise.pink });
  },
};

SFX.ads_in = {
  dur: 0.22, variants: 3, gain: 1.0, jitter: 90, rateJit: 0.06, level: -26,
  build(ctx, out, rng, v, lib) {
    // sleeve against the stock, then the weapon settling into the shoulder
    clothBrush(ctx, out, rng, { t: 0.0, dur: 0.09, f0: 2600, f1: 5200, peak: 0.16, noise: lib.noise.pink });
    clack(ctx, out, { t: 0.055, freqs: [rnd(rng, 1600, 2200), rnd(rng, 3200, 4200)], dur: 0.016, peak: 0.1, noise: lib.noise.white, bright: 3600, rng });
    thump(ctx, out, { t: 0.055, f0: 220, f1: 110, dur: 0.05, peak: 0.1, type: 'triangle' });
  },
};

SFX.ads_out = {
  dur: 0.2, variants: 3, gain: 1.0, jitter: 90, rateJit: 0.06, level: -27,
  build(ctx, out, rng, v, lib) {
    clothBrush(ctx, out, rng, { t: 0.0, dur: 0.1, f0: 4600, f1: 2200, peak: 0.16, noise: lib.noise.pink });
    clack(ctx, out, { t: 0.02, freqs: [rnd(rng, 1300, 1800), rnd(rng, 2600, 3400)], dur: 0.014, peak: 0.07, rng });
  },
};

SFX.weapon_lower = {
  dur: 0.45, variants: 3, gain: 1.0, jitter: 60, rateJit: 0.04, level: -23,
  build(ctx, out, rng, v, lib) {
    // the gun coming off the shoulder and onto the sling
    clothBrush(ctx, out, rng, { t: 0.0, dur: 0.24, f0: 3400, f1: 1600, peak: 0.2, noise: lib.noise.pink });
    rattle(ctx, out, rng, { t: 0.04, count: 3, spread: 0.12, f: 2600, peak: 0.07, noise: lib.noise.white });
    steelHit(ctx, out, rng, { t: 0.14, f: 1500, modes: [1, 1.63, 2.4], dur: 0.04, peak: 0.2, noise: lib.noise.white, bright: 2400, thud: 240, thudAmp: 0.4 });
  },
};

SFX.weapon_raise = {
  dur: 0.5, variants: 3, gain: 1.0, jitter: 60, rateJit: 0.04, level: -21,
  build(ctx, out, rng, v, lib) {
    // hauled up, hands find their places, the gun settles
    clothBrush(ctx, out, rng, { t: 0.0, dur: 0.2, f0: 1600, f1: 3600, peak: 0.2, noise: lib.noise.pink });
    rattle(ctx, out, rng, { t: 0.02, count: 4, spread: 0.14, f: 2900, peak: 0.08, noise: lib.noise.white });
    steelHit(ctx, out, rng, { t: 0.13, f: 1700, modes: [1, 1.66, 2.5], dur: 0.04, peak: 0.34, noise: lib.noise.white, bright: 2800 });
    steelHit(ctx, out, rng, { t: 0.2, f: 1100, modes: [1, 1.6, 2.4], dur: 0.055, peak: 0.28, noise: lib.noise.white, bright: 1900, thud: 220, thudAmp: 0.45 });
  },
};

SFX.knife_hit_wall = {
  dur: 0.6, variants: 3, gain: 1.0, jitter: 110, rateJit: 0.08, level: -21,
  build(ctx, out, rng, v, lib) {
    // steel skating across masonry: a bright scrape with a hard ring on it
    noiseBurst(ctx, out, { noise: lib.noise.white, t: 0.001, type: 'bandpass', f0: rnd(rng, 3400, 5200), f1: 1800, q: 2.2, sweep: 0.1, attack: 0.0008, decay: 0.13, peak: 0.7, drive: 4, rng });
    const base = rnd(rng, 2600, 3800);
    for (const m of [1, 1.71, 2.62]) {
      ping(ctx, out, { t: 0.001, freq: base * m, dur: 0.3 / m, peak: 0.12 / m, type: m < 2 ? 'triangle' : 'sine', pan: jit(rng, 0.4) });
    }
    thump(ctx, out, { t: 0.001, f0: 260, f1: 90, dur: 0.06, peak: 0.25, type: 'triangle', drive: 2 });
    const gr = bufSrc(ctx, grainBuffer(ctx, 0.3, rng, { density: 200, amp: 0.45, skew: 0.5 }), 0.006);
    const gf = filt(ctx, 'highpass', 2200, 0.7);
    const gg = gainNode(ctx, 0);
    ampEnv(gg.gain, { t: 0.006, peak: 0.2, attack: 0.004, decay: 0.24 });
    gr.connect(gf); gf.connect(gg); gg.connect(out);
  },
};

SFX.hitmarker_head = {
  dur: 0.18, variants: 2, gain: 1.0, bus: 'ui', jitter: 25, level: -22,
  build(ctx, out, rng, v, lib) {
    // the same tick as `hitmarker`, but with a bright partial on top so a
    // headshot is audible without looking at the reticle
    ping(ctx, out, { t: 0.0005, freq: 3100, dur: 0.05, peak: 0.6, type: 'triangle' });
    ping(ctx, out, { t: 0.0005, freq: 4650, dur: 0.035, peak: 0.34 });
    ping(ctx, out, { t: 0.0008, freq: 6200, dur: 0.07, peak: 0.28, mod: 2.0, index: 0.4 });
    noiseBurst(ctx, out, { noise: lib.noise.white, t: 0, type: 'highpass', f0: 6000, q: 0.7, attack: 0.0003, decay: 0.014, peak: 0.5, rng });
  },
};

SFX.low_ammo = {
  dur: 0.3, gain: 1.0, bus: 'ui', level: -23,
  build(ctx, out, rng, v, lib) {
    // the follower hitting the top of the magazine — a warning you feel rather
    // than read off the HUD
    clack(ctx, out, { t: 0.001, freqs: [2600, 4100, 5800], dur: 0.02, peak: 0.4, noise: lib.noise.white, bright: 4200, rng });
    ping(ctx, out, { t: 0.001, freq: 1180, dur: 0.1, peak: 0.16, type: 'triangle' });
    ping(ctx, out, { t: 0.055, freq: 990, dur: 0.12, peak: 0.12, type: 'triangle' });
  },
};

/* ---------- radio carrier under the announcer ---------- */

SFX.radio_static = {
  dur: 1.2, xfade: 0.25, loop: true, gain: 1.0, bus: 'ui', level: -30, srScale: 0.75,
  build(ctx, out, rng, v, lib) {
    const total = 1.45;
    // a narrow, gritty carrier band — the sound of a squad radio holding open
    const s = bufSrc(ctx, lib.noise.pink, 0, { loop: true, offset: rnd(rng, 0, 2) });
    const bp = filt(ctx, 'bandpass', 1700, 1.1);
    const hp = filt(ctx, 'highpass', 400, 0.7);
    const lp = filt(ctx, 'lowpass', 3200, 0.7);
    const g = gainNode(ctx, 0.5);
    for (const n of [1, 2, 3]) {
      const lfo = osc(ctx, 'sine', n / 1.2);
      const lg = gainNode(ctx, 0.12 / n);
      lfo.connect(lg); lg.connect(g.gain);
      lfo.start(0); lfo.stop(total);
    }
    s.connect(hp); hp.connect(bp); bp.connect(lp); lp.connect(g); g.connect(out);
    s.stop(total);
    // intermittent crackle
    const cr = bufSrc(ctx, crackleBuffer(ctx, total, rng, { density: 22, fLo: 1200, fHi: 5200, amp: 0.4, decayLo: 0.002, decayHi: 0.02 }), 0);
    const cg = gainNode(ctx, 0.25);
    cr.connect(cg); cg.connect(out);
  },
};

/* ================================================================== *
 * The announcer — formant speech, baked like every other sound
 *
 * The announcer used to be `window.speechSynthesis` pitched down, which meant
 * the game's most recognisable line was whatever screen-reader voice the
 * player's OS happened to ship: a different actor on every machine, missing
 * entirely on some, arriving at an unknown time, and impossible to process
 * because it never enters the audio graph at all — it cannot be ducked, panned,
 * filtered or mixed.
 *
 * These are synthesised instead. A jittered glottal pulse train (the same
 * source the zombies use, an octave up and far steadier) runs through four
 * parallel band-passes whose centre frequencies glide between phoneme formant
 * targets; fricatives are shaped noise, stops are a silent hold followed by a
 * burst and a puff of aspiration, and the whole phrase goes through a
 * comms-band radio chain with a short PA slap. It is the same voice on every
 * machine, it lives on the ui bus with the squelch blips, and at runtime it
 * costs exactly one buffer playback.
 *
 * The vocabulary is closed — six power-ups — so six phrases is the whole job.
 * ================================================================== */

/**
 * Phoneme table.
 *   f:     four formant targets in Hz (male, ~17 cm tract)
 *   damp:  voiced amplitude multiplier (nasals and laterals are quieter)
 *   fric:  unvoiced noise band
 *   stop:  silent hold, then a burst at that band, then aspiration
 */
const VOX_PHONES = {
  // vowels
  aa: { f: [730, 1100, 2450, 3400] },   // f(a)ther
  ae: { f: [660, 1720, 2410, 3300] },   // m(a)x
  eh: { f: [530, 1840, 2480, 3500] },   // s(a)le
  ih: { f: [400, 1980, 2560, 3500] },   // k(i)ll
  iy: { f: [290, 2280, 3000, 3600] },   // fr(ee)
  ao: { f: [570, 840, 2410, 3200] },    // p(oi)nts
  ow: { f: [450, 800, 2400, 3200] },    // amm(o)
  uw: { f: [310, 870, 2240, 3200] },    // n(u)ke
  ah: { f: [640, 1190, 2390, 3300] },   // d(ou)ble
  er: { f: [470, 1350, 1690, 3200] },   // carpent(er)
  // Voiced continuants. `damp` is not cosmetic: a nasal's F1 sits at 270 Hz,
  // right on top of the strongest harmonics of a 100 Hz pulse train, so left at
  // a vowel's amplitude it comes out *louder* than the vowel it is attached to
  // (measured: +1.4 dB). Real nasals and laterals sit several dB under.
  m: { f: [270, 900, 2200, 3000], damp: 0.25 },
  n: { f: [270, 1700, 2600, 3200], damp: 0.25 },
  l: { f: [380, 900, 2700, 3300], damp: 0.45 },
  r: { f: [330, 1060, 1600, 3000], damp: 0.5 },
  // fricatives
  s: { fric: { f: 4700, q: 2.0, g: 0.5, hp: 3200 } },
  f: { fric: { f: 1900, q: 0.8, g: 0.2, hp: 1100 } },
  // stops
  k: { stop: { f: 1900, q: 1.1, g: 0.5, hold: 0.05, asp: 0.06 } },
  t: { stop: { f: 3300, q: 1.3, g: 0.4, hold: 0.045, asp: 0.035 } },
  p: { stop: { f: 1000, q: 0.9, g: 0.38, hold: 0.05, asp: 0.04 } },
  d: { stop: { f: 2500, q: 1.1, g: 0.24, hold: 0.032, asp: 0.014, voice: 0.2 } },
  b: { stop: { f: 800, q: 0.9, g: 0.22, hold: 0.03, asp: 0.012, voice: 0.2 } },
  _: { gap: true },
};

/**
 * Voiced/unvoiced balance, measured rather than guessed.
 *
 * Four unity-gain band-passes throw away most of a glottal pulse train's
 * energy, so the voiced path arrives ~15 dB under raw noise of the same nominal
 * peak: with the bands and the fricatives both left "as written", a phrase
 * comes out as a loud hiss with mumbling underneath it. VOICE_MAKEUP puts the
 * formant path back where it belongs and NOISE_TRIM drops the consonants to
 * roughly 9 dB under the stressed vowel, which is about where speech sits.
 */
const VOX_VOICE_MAKEUP = 6.0;
const VOX_NOISE_TRIM = 0.42;

/** Seconds a script occupies, so a recipe can declare an honest `dur`. */
function voxDur(script) {
  let t = 0;
  for (const st of script) {
    const ph = VOX_PHONES[st[0]] || {};
    if (ph.stop) t += (ph.stop.hold ?? 0.04) + (st[1] || 0.055);
    else t += st[1] || 0.05;
  }
  return t;
}

/**
 * Render one spoken phrase.
 * o: { script: [[sym, dur, amp?]], t, f0a, f0b, scale, gain, drive }
 */
function voxPhrase(ctx, out, lib, rng, o = {}) {
  const script = o.script || [];
  const t0 = o.t ?? 0.015;
  const len = Math.max(0.12, voxDur(script));
  const f0a = o.f0a ?? 128;
  const f0b = o.f0b ?? 94;
  const scale = o.scale ?? 1;
  const GLIDE = 0.035;

  /* ---- the radio the voice is coming out of ---- */
  const sum = gainNode(ctx, 1);
  const preEmph = filt(ctx, 'highshelf', 1700, 0.7, 5);
  const drive = shaper(ctx, satCurve(o.drive ?? 3.4));
  const wet = gainNode(ctx, 0.55);
  const dry = gainNode(ctx, 0.45);
  const post = gainNode(ctx, 1);
  const hp = filt(ctx, 'highpass', 380, 0.7);
  const lp = filt(ctx, 'lowpass', 3300, 0.9);
  sum.connect(preEmph);
  preEmph.connect(drive); drive.connect(wet); wet.connect(post);
  preEmph.connect(dry); dry.connect(post);
  post.connect(hp); hp.connect(lp); lp.connect(out);
  // PA slap: one short reflection, the sound of a tannoy in a big room
  const slap = delayNode(ctx, 0.055, 0.2);
  const slapG = gainNode(ctx, 0.16);
  const slapLP = filt(ctx, 'lowpass', 2100, 0.7);
  lp.connect(slap); slap.connect(slapLP); slapLP.connect(slapG); slapG.connect(out);

  /* ---- glottal source, gated per phoneme, through the formant bank ---- */
  const src = glottalBuffer(ctx, {
    dur: len + 0.16,
    f0: (tt) => {
      const p = clamp(tt / len, 0, 1);
      // announcer cadence: a push up into the first stressed syllable, then a
      // steady fall onto the full stop
      const rise = 1 - Math.pow(1 - Math.min(1, p / 0.16), 2);
      const base = f0a * (1 + 0.09 * rise) - (f0a - f0b) * Math.pow(p, 1.35);
      return base * (1 + 0.012 * Math.sin(2 * Math.PI * 5.1 * tt));
    },
    jitter: 0.016, shimmer: 0.09, rough: o.rough ?? 0.05, oq: 0.58, breath: 0.05, rng,
  });
  const s = bufSrc(ctx, src, t0);
  const voiced = gainNode(ctx, 0);
  s.connect(voiced);

  const BW = [90, 110, 160, 240];
  const LVL = [1, 0.5, 0.26, 0.13];
  // everything voiced meets here, and only here, so the make-up gain does not
  // also lift the consonant noise
  const voiceMix = gainNode(ctx, VOX_VOICE_MAKEUP * (o.voice ?? 1));
  voiceMix.connect(sum);
  const bands = [];
  for (let i = 0; i < 4; i++) {
    const bp = filt(ctx, 'bandpass', 500, 5);
    const g = gainNode(ctx, LVL[i]);
    voiced.connect(bp); bp.connect(g); g.connect(voiceMix);
    bands.push({ bp, cur: 500, bw: BW[i] });
  }
  // a little unfiltered source keeps the chest in the voice
  const direct = gainNode(ctx, 0.16);
  voiced.connect(direct); direct.connect(voiceMix);

  /* ---- walk the script ---- */
  let t = t0;
  let cur = 0;
  setAt(voiced.gain, 0, Math.max(0, t0 - 0.005));
  for (const st of script) {
    const sym = st[0];
    const ph = VOX_PHONES[sym] || {};
    const step = st[1] || 0.05;
    const amp = (st[2] ?? 1) * (ph.damp ?? 1) * (o.gain ?? 1);

    if (ph.f) {
      for (let i = 0; i < bands.length; i++) {
        const b = bands[i];
        const f = clamp(ph.f[i] * scale, 90, 5200);
        setAt(b.bp.frequency, b.cur, Math.max(0, t - GLIDE));
        expTo(b.bp.frequency, f, t + GLIDE * 0.6);
        setAt(b.bp.Q, Math.max(0.7, f / b.bw), Math.max(0, t - GLIDE));
        b.cur = f;
      }
      const atk = Math.min(0.022, step * 0.4);
      setAt(voiced.gain, cur, Math.max(0, t - 0.004));
      linTo(voiced.gain, amp, t + atk);
      cur = amp;
    } else if (ph.fric) {
      const fr = ph.fric;
      setAt(voiced.gain, cur, Math.max(0, t - 0.004));
      linTo(voiced.gain, 0, t + 0.018);
      cur = 0;
      noiseBurst(ctx, sum, {
        noise: lib.noise.white, t, type: 'bandpass', f0: fr.f, q: fr.q, hp: fr.hp,
        attack: 0.022, hold: Math.max(0.01, step - 0.075), decay: 0.055,
        peak: fr.g * VOX_NOISE_TRIM * (st[2] ?? 1), rng,
      });
    } else if (ph.stop) {
      const sp = ph.stop;
      // the silence *is* the consonant — a stop with no hold reads as a click
      setAt(voiced.gain, cur, Math.max(0, t - 0.004));
      linTo(voiced.gain, sp.voice ? cur * 0.12 : 0, t + 0.014);
      cur = sp.voice ? cur * 0.12 : 0;
      const tb = t + (sp.hold ?? 0.04);
      noiseBurst(ctx, sum, {
        noise: lib.noise.white, t: tb, type: 'bandpass', f0: sp.f, q: sp.q,
        attack: 0.0008, decay: 0.028, peak: sp.g * VOX_NOISE_TRIM * (st[2] ?? 1), drive: 2.4, driveMix: 0.4, rng,
      });
      if (sp.asp) {
        noiseBurst(ctx, sum, {
          noise: lib.noise.white, t: tb + 0.004, type: 'highpass', f0: 1300, q: 0.6,
          attack: 0.004, decay: sp.asp, peak: sp.g * VOX_NOISE_TRIM * 0.3 * (st[2] ?? 1), rng,
        });
      }
      t += (sp.hold ?? 0.04);
    } else {
      // word gap
      setAt(voiced.gain, cur, Math.max(0, t - 0.004));
      linTo(voiced.gain, 0, t + 0.02);
      cur = 0;
    }
    t += step;
  }
  setAt(voiced.gain, cur, t);
  linTo(voiced.gain, 0, t + 0.035);
  s.stop(t + 0.12);
  return { end: t + 0.12 };
}

/** name -> [script, options] */
const VOX_LINES = {
  vox_max_ammo: {
    script: [['m', 0.075], ['ae', 0.175, 1.05], ['k', 0.05], ['s', 0.125], ['_', 0.05],
      ['ae', 0.15], ['m', 0.07], ['ow', 0.26, 0.9]],
  },
  vox_insta_kill: {
    script: [['ih', 0.12, 1.05], ['n', 0.07], ['s', 0.125], ['t', 0.05], ['ah', 0.07, 0.8], ['_', 0.045],
      ['k', 0.05], ['ih', 0.135, 1.05], ['l', 0.2, 0.85]],
  },
  vox_double_points: {
    script: [['d', 0.045], ['ah', 0.145, 1.05], ['b', 0.04], ['ah', 0.06, 0.75], ['l', 0.13, 0.8], ['_', 0.05],
      ['p', 0.05], ['ao', 0.135, 1.05], ['ih', 0.07, 0.9], ['n', 0.06], ['t', 0.03], ['s', 0.135]],
    f0a: 132,
  },
  vox_nuke: {
    script: [['n', 0.08], ['iy', 0.045, 0.9], ['uw', 0.26, 1.05], ['k', 0.06]],
    f0a: 136, f0b: 88,
  },
  vox_carpenter: {
    script: [['k', 0.05], ['aa', 0.165, 1.05], ['r', 0.1], ['p', 0.045], ['ah', 0.08, 0.8],
      ['n', 0.06], ['t', 0.035], ['er', 0.2, 0.85]],
  },
  vox_fire_sale: {
    script: [['f', 0.115], ['aa', 0.13, 1.05], ['ih', 0.08], ['er', 0.13, 0.9], ['_', 0.05],
      ['s', 0.13], ['eh', 0.115, 1.0], ['iy', 0.07, 0.9], ['l', 0.175, 0.85]],
  },
};

for (const [name, line] of Object.entries(VOX_LINES)) {
  SFX[name] = {
    dur: voxDur(line.script) + 0.3, variants: 1, gain: 1.0, bus: 'ui',
    level: line.level ?? -13, defer: true,
    // how long the words themselves last, so the engine can close the radio
    // carrier on the last syllable rather than on the render padding
    speech: voxDur(line.script) + 0.06,
    build(ctx, out, rng, v, lib) {
      voxPhrase(ctx, out, lib, rng, Object.assign({ t: 0.02 }, line));
    },
  };
}

/** Spoken lines the engine can reach for, keyed by squashed text. */
export const VOX_LOOKUP = {
  maxammo: 'vox_max_ammo',
  instakill: 'vox_insta_kill',
  doublepoints: 'vox_double_points',
  nuke: 'vox_nuke',
  // the nuke power-up's display name in config.js is "Kaboom!", which is what
  // the announcer actually says — without this key that line went out wordless
  kaboom: 'vox_nuke',
  carpenter: 'vox_carpenter',
  firesale: 'vox_fire_sale',
};

export default SFX;
