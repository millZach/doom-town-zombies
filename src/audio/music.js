/**
 * music.js — original procedural music for Doom Town.
 *
 * Nothing here is sampled or transcribed from anything: the motifs are written
 * as note lists and realised with the synth primitives in dsp.js.
 *
 * The signature sound is the round stinger: a low inharmonic bell, a
 * choir-like formant pad in D natural/harmonic minor, and a huge reverb.
 * Exports two recipe maps in the same shape sfx.js uses:
 *   STINGERS — one-shots triggered with audio.play()
 *   MUSIC    — long looping beds played with audio.music()
 */

import {
  mulberry32, rnd, rint, jit, clamp, mtof, nf, lerp, lockFreq,
  gainNode, filt, osc, delayNode, panner, expTo, setAt, linTo, ampEnv,
  satCurve, fuzzCurve, foldCurve, shaper, makeReverb,
  formantBank, morphVowel,
  noiseBurst, thump, ping, bell, choirVoice, clack,
} from './dsp.js';

/* ------------------------------------------------------------------ *
 * Shared musical material
 * ------------------------------------------------------------------ */

// D natural minor with a raised 7th available: D E F G A Bb C C#
const D = 62;   // D4

/** A very low tolling bell with a long inharmonic tail. */
function lowBell(ctx, dry, wet, t, midi, amp, dur) {
  const b = bell(ctx, dry, {
    t, freq: mtof(midi), dur, peak: amp,
    partials: [
      [0.5, 0.55, 1.15],    // hum tone an octave below — the church-bell signature
      [1.0, 1.0, 1.0],
      [1.19, 0.45, 0.85],   // minor third
      [1.5, 0.5, 0.75],
      [2.0, 0.42, 0.62],
      [2.52, 0.3, 0.5],
      [3.01, 0.22, 0.4],
      [4.07, 0.14, 0.28],
      [5.43, 0.09, 0.2],
    ],
    stretch: 0.0018,
  });
  b.out.connect(wet);
  return b;
}

/** A sustained choir chord. */
function choirChord(ctx, dry, wet, t, midis, dur, amp, vowel, rng, opts = {}) {
  const voices = [];
  for (let i = 0; i < midis.length; i++) {
    const c = choirVoice(ctx, dry, {
      t: t + i * (opts.stagger ?? 0.05), freq: mtof(midis[i]),
      dur: dur - i * (opts.stagger ?? 0.05),
      peak: amp * (i === 0 ? 1 : 0.8 - i * 0.05),
      vowel: vowel || 'u', voices: opts.voices ?? 4,
      detune: opts.detune ?? 13, spread: opts.spread ?? 7, vib: opts.vib ?? 1,
      attack: opts.attack ?? 0.7, release: opts.release ?? dur * 0.45,
      lp: opts.lp ?? 3000, fscale: opts.fscale ?? 1,
      pan: opts.pan != null ? opts.pan : (i / Math.max(1, midis.length - 1) - 0.5) * 1.1,
      rng,
    });
    c.out.connect(wet);
    voices.push(c);
  }
  return voices;
}

/** Reversed-swell "breath in" before a hit — cheap dread. */
function reverseSwell(ctx, out, lib, rng, t, dur, peak) {
  const s = ctx.createBufferSource();
  s.buffer = lib.noise.pink;
  s.loop = true;
  const bp = filt(ctx, 'bandpass', 400, 0.9);
  setAt(bp.frequency, 260, t);
  expTo(bp.frequency, 3400, t + dur);
  const g = gainNode(ctx, 0);
  setAt(g.gain, 1e-4, t);
  expTo(g.gain, peak, t + dur);
  setAt(g.gain, 0, t + dur + 0.02);
  s.connect(bp); bp.connect(g); g.connect(out);
  s.start(t, rnd(rng, 0, 2));
  s.stop(t + dur + 0.1);
}

/** A sub-bass swell (the thing you feel rather than hear). */
function subSwell(ctx, out, t, f, dur, peak, glideTo) {
  const o1 = osc(ctx, 'sine', f);
  if (glideTo) { setAt(o1.frequency, f, t); expTo(o1.frequency, glideTo, t + dur); }
  const g = gainNode(ctx, 0);
  ampEnv(g.gain, { t, peak, attack: dur * 0.25, hold: dur * 0.2, decay: dur * 0.6, curve: 'lin' });
  o1.connect(g); g.connect(out);
  o1.start(t); o1.stop(t + dur + 0.1);
  return g;
}

/* ================================================================== *
 * Round stingers
 * ================================================================== */

export const STINGERS = {};

/**
 * round_end — the signature cue. Eerie, reverb-drenched, D minor.
 *   low bell tolls on D1/D2, a choir pad breathes Dm → Bb → Dm underneath,
 *   a lone high voice plays the motif A–F–D–C#, and everything dissolves.
 */
STINGERS.round_end = {
  defer: true,
  dur: 7.5, gain: 1.0, bus: 'music',
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 6.0, damp: 2600, preDelay: 0.035, combs: 8, width: 1, gain: 1 });
    const wetGain = gainNode(ctx, 0.85);
    rev.output.connect(wetGain);
    wetGain.connect(out);
    const dry = gainNode(ctx, 0.62);
    dry.connect(out);
    const wet = rev.input;

    // breath in
    reverseSwell(ctx, dry, lib, rng, 0, 0.9, 0.1);
    reverseSwell(ctx, wet, lib, rng, 0, 0.9, 0.12);

    // the toll
    lowBell(ctx, dry, wet, 0.85, D - 24, 0.34, 6.2);      // D2
    lowBell(ctx, dry, wet, 0.88, D - 36, 0.2, 6.4);       // D1 — felt more than heard
    subSwell(ctx, dry, 0.85, mtof(D - 36), 4.0, 0.3);

    // choir: Dm  →  Bb(add9)  →  Dm
    choirChord(ctx, dry, wet, 0.9, [D - 12, D - 5, D, D + 5], 3.4, 0.16, 'u', rng,
      { attack: 1.1, release: 1.6, lp: 2600 });
    choirChord(ctx, dry, wet, 3.5, [D - 16, D - 9, D - 2, D + 4], 3.6, 0.15, 'o', rng,
      { attack: 1.3, release: 2.0, lp: 2400 });

    // the motif: A4  F4  D4  C#4 — slow, ringing, played on a glass-like voice
    const motif = [[1.5, D + 7, 2.6], [2.5, D + 3, 2.6], [3.6, D, 3.0], [4.9, D - 1, 3.4]];
    for (const [t, m, dur] of motif) {
      const p = ping(ctx, dry, {
        t, freq: mtof(m), dur, peak: 0.16, mod: 2.004, index: 0.55, modDecay: 0.25,
        attack: 0.02, pan: jit(rng, 0.35),
      });
      p.out.connect(wet);
      // a shadow an octave up, quieter and detuned — glassy shimmer
      const p2 = ping(ctx, dry, { t: t + 0.02, freq: mtof(m + 12) * 1.003, dur: dur * 0.7, peak: 0.05, pan: jit(rng, 0.6) });
      p2.out.connect(wet);
    }

    // final low hit + long decay
    lowBell(ctx, dry, wet, 5.4, D - 29, 0.22, 2.4);       // A1
    subSwell(ctx, dry, 5.4, mtof(D - 41), 2.0, 0.22);

    // distant wind under the whole thing
    const w = ctx.createBufferSource();
    w.buffer = lib.noise.brown; w.loop = true;
    const wbp = filt(ctx, 'bandpass', 500, 0.7);
    const wg = gainNode(ctx, 0);
    ampEnv(wg.gain, { t: 0, peak: 0.07, attack: 1.5, hold: 2.5, decay: 3.0, curve: 'lin' });
    w.connect(wbp); wbp.connect(wg); wg.connect(out);
    w.start(0, rnd(rng, 0, 3)); w.stop(7.4);
  },
};

/**
 * round_start — a darker, more urgent variation of the same material:
 * transposed down a fourth, the motif inverted and compressed, a tritone in
 * the pad, and a hard low hit to kick the round off.
 */
STINGERS.round_start = {
  dur: 6.5, gain: 1.0, bus: 'music',
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 5.0, damp: 2200, preDelay: 0.03, combs: 8, gain: 1 });
    const wetGain = gainNode(ctx, 0.8);
    rev.output.connect(wetGain); wetGain.connect(out);
    const dry = gainNode(ctx, 0.66); dry.connect(out);
    const wet = rev.input;
    const A = D - 5;   // A3 — the new centre

    // hard hit right at the top
    const th = thump(ctx, dry, { t: 0.01, f0: 120, f1: 24, dur: 1.1, glide: 0.5, peak: 0.85, drive: 4 });
    th.gain.connect(wet);
    noiseBurst(ctx, dry, { noise: lib.noise.brown, t: 0.01, type: 'lowpass', f0: 1400, f1: 90, q: 1.4, sweep: 0.5, attack: 0.003, decay: 0.7, peak: 0.45, drive: 6, rng });

    lowBell(ctx, dry, wet, 0.02, A - 24, 0.34, 5.4);
    lowBell(ctx, dry, wet, 0.05, A - 36, 0.22, 5.6);
    subSwell(ctx, dry, 0.02, mtof(A - 36), 4.2, 0.34);

    // pad: A minor with a flat 5 (Eb) sliding in — the "something is wrong" chord
    choirChord(ctx, dry, wet, 0.25, [A - 12, A - 5, A, A + 3], 3.0, 0.16, 'o', rng,
      { attack: 0.5, release: 1.4, lp: 2400 });
    choirChord(ctx, dry, wet, 2.6, [A - 12, A - 6, A + 3, A + 8], 3.4, 0.15, 'u', rng,
      { attack: 1.0, release: 1.8, lp: 2200 });

    // motif inverted: A  C  Eb  E  (rising, dissonant)
    const motif = [[0.9, A, 2.0], [1.7, A + 3, 2.0], [2.5, A + 6, 2.2], [3.4, A + 7, 3.0]];
    for (const [t, m, dur] of motif) {
      const p = ping(ctx, dry, { t, freq: mtof(m), dur, peak: 0.15, mod: 1.997, index: 0.6, modDecay: 0.22, pan: jit(rng, 0.4) });
      p.out.connect(wet);
    }

    // a rising swell into the last bell
    reverseSwell(ctx, wet, lib, rng, 3.3, 1.0, 0.14);
    lowBell(ctx, dry, wet, 4.35, A - 17, 0.26, 2.2);
    subSwell(ctx, dry, 4.35, mtof(A - 41), 1.8, 0.24);
  },
};

/**
 * hellround_start — the dogs are coming. Chromatic cluster, distorted brass-ish
 * growl, a howl, and the bell hammered rather than tolled.
 */
STINGERS.hellround_start = {
  defer: true,
  dur: 6.5, gain: 1.0, bus: 'music',
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 4.5, damp: 1800, preDelay: 0.025, combs: 8, gain: 1 });
    const wetGain = gainNode(ctx, 0.8);
    rev.output.connect(wetGain); wetGain.connect(out);
    const dry = gainNode(ctx, 0.66); dry.connect(out);
    const wet = rev.input;

    // lightning-ish crack + sub
    noiseBurst(ctx, dry, { noise: lib.noise.white, t: 0.005, type: 'highpass', f0: 4000, q: 0.5, attack: 0.0005, decay: 0.05, peak: 0.55, rng });
    const th = thump(ctx, dry, { t: 0.005, f0: 110, f1: 20, dur: 1.4, glide: 0.6, peak: 0.9, drive: 5 });
    th.gain.connect(wet);

    // hammered bell (three strikes, accelerating)
    lowBell(ctx, dry, wet, 0.02, D - 26, 0.3, 4.5);
    lowBell(ctx, dry, wet, 0.42, D - 25, 0.24, 4.0);
    lowBell(ctx, dry, wet, 0.72, D - 26, 0.28, 5.0);

    // distorted growl pad: a tritone cluster through a fuzz
    const growl = gainNode(ctx, 1);
    const fz = shaper(ctx, fuzzCurve(6, 0.08));
    const glp = filt(ctx, 'lowpass', 1600, 1.2);
    growl.connect(fz); fz.connect(glp);
    const gOut = gainNode(ctx, 0);
    ampEnv(gOut.gain, { t: 0.1, peak: 0.3, attack: 1.2, hold: 1.4, decay: 2.2, curve: 'lin' });
    glp.connect(gOut); gOut.connect(dry); gOut.connect(wet);
    for (const m of [D - 26, D - 20, D - 14, D - 13]) {
      const o1 = osc(ctx, 'sawtooth', mtof(m));
      o1.detune.value = jit(rng, 16);
      const lfo = osc(ctx, 'sine', rnd(rng, 0.2, 0.6));
      const lg = gainNode(ctx, rnd(rng, 8, 22));
      lfo.connect(lg); lg.connect(o1.detune);
      lfo.start(0); lfo.stop(5.5);
      const g = gainNode(ctx, 0.22);
      o1.connect(g); g.connect(growl);
      o1.start(0.05); o1.stop(5.4);
    }

    // choir, but wrong: a semitone cluster
    choirChord(ctx, dry, wet, 0.6, [D - 2, D - 1, D + 5, D + 6], 3.4, 0.13, 'a', rng,
      { attack: 0.9, release: 1.8, lp: 2600, detune: 22 });

    // the howl
    const howl = osc(ctx, 'sawtooth', 300);
    setAt(howl.frequency, 220, 2.4);
    expTo(howl.frequency, 470, 3.3);
    setAt(howl.frequency, 470, 4.0);
    expTo(howl.frequency, 180, 5.2);
    const hbank = formantBank(ctx, 'u', { scale: 0.85, bwScale: 1.8 });
    morphVowel(hbank, 'o', 3.4, 1.0, 0.85);
    const hvib = osc(ctx, 'sine', 5.4);
    const hvg = gainNode(ctx, 26);
    hvib.connect(hvg); hvg.connect(howl.detune);
    hvib.start(2.4); hvib.stop(5.3);
    const hg = gainNode(ctx, 0);
    ampEnv(hg.gain, { t: 2.4, peak: 0.16, attack: 0.5, hold: 0.9, decay: 1.4, curve: 'lin' });
    howl.connect(hbank.input); hbank.output.connect(hg); hg.connect(dry); hg.connect(wet);
    howl.start(2.4); howl.stop(5.3);

    // final stab
    const th2 = thump(ctx, dry, { t: 4.6, f0: 95, f1: 22, dur: 1.4, glide: 0.5, peak: 0.6, drive: 4 });
    th2.gain.connect(wet);
  },
};

/** game_over stinger — the one-shot "you died" cue. */
STINGERS.game_over = {
  defer: true,
  dur: 7.0, gain: 1.0, bus: 'music',
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 6.5, damp: 1800, preDelay: 0.04, combs: 8, gain: 1 });
    const wetGain = gainNode(ctx, 0.9);
    rev.output.connect(wetGain); wetGain.connect(out);
    const dry = gainNode(ctx, 0.6); dry.connect(out);
    const wet = rev.input;

    // one enormous toll
    lowBell(ctx, dry, wet, 0.02, D - 26, 0.36, 6.5);
    lowBell(ctx, dry, wet, 0.05, D - 38, 0.24, 6.5);
    subSwell(ctx, dry, 0.02, mtof(D - 38), 5.0, 0.36, mtof(D - 41));

    // the choir sinks: Dm → Dm(b6) → Ddim, each lower than the last
    choirChord(ctx, dry, wet, 0.1, [D - 12, D - 5, D, D + 3], 3.2, 0.17, 'o', rng, { attack: 0.8, release: 1.6, lp: 2200 });
    choirChord(ctx, dry, wet, 2.8, [D - 14, D - 7, D - 2, D + 1], 3.4, 0.16, 'u', rng, { attack: 1.2, release: 2.0, lp: 1900 });

    // a falling solo line: A  G  F  E  D
    const line = [[0.7, D + 7], [1.6, D + 5], [2.5, D + 3], [3.5, D + 2], [4.6, D]];
    for (let i = 0; i < line.length; i++) {
      const [t, m] = line[i];
      const p = ping(ctx, dry, { t, freq: mtof(m), dur: 2.4 + i * 0.3, peak: 0.15 - i * 0.012, mod: 2.002, index: 0.5, modDecay: 0.25, pan: jit(rng, 0.3) });
      p.out.connect(wet);
    }
    // heart stops
    thump(ctx, dry, { t: 5.3, f0: 64, f1: 22, dur: 1.2, glide: 0.6, peak: 0.35 }).gain.connect(wet);
  },
};

/* ================================================================== *
 * Music beds (audio.music)
 * ================================================================== */

export const MUSIC = {};

/**
 * menu — 24 s seamless loop. A slow, wide, hopeless pad cycling
 * Dm → Bb → Gm → A(#5), a tolling bell every 6 s, wind, and a sub drone.
 */
MUSIC.menu = {
  // the only bed with nothing to compete with, so it sits well above the
  // in-round layers (-27) but still under any one-shot the menu makes
  dur: 24.0, xfade: 3.0, loop: true, gain: 1.0, bus: 'music', srScale: 0.5, level: -20,
  build(ctx, out, rng, v, lib) {
    const total = 27.0;
    const rev = makeReverb(ctx, { decay: 5.5, damp: 2600, preDelay: 0.03, combs: 8, gain: 1 });
    const wetGain = gainNode(ctx, 0.8);
    rev.output.connect(wetGain); wetGain.connect(out);
    const dry = gainNode(ctx, 0.58); dry.connect(out);
    const wet = rev.input;

    const bar = 6.0;
    // Dm — Bb — Gm — A(with a sharp 5 for the sting)
    const prog = [
      [D - 12, D - 5, D, D + 5],          // D  A  D  G ... rooted Dm
      [D - 14, D - 7, D - 2, D + 5],      // Bb F  C  G  (Bb add9)
      [D - 17, D - 10, D - 5, D + 2],     // G  D  A  E  (Gm add9)
      [D - 16, D - 9, D - 4, D + 4],      // Bb… A altered
    ];
    const vowels = ['u', 'o', 'u', 'o'];
    for (let i = 0; i < 4; i++) {
      choirChord(ctx, dry, wet, i * bar, prog[i], bar + 1.6, 0.15, vowels[i], rng, {
        attack: 1.8, release: 2.6, lp: 2400, detune: 15, spread: 8, voices: 4, stagger: 0.12,
      });
    }
    // sub drone — constant D, breathing (frequency locked to the loop grid)
    const sub = osc(ctx, 'sine', lockFreq(mtof(D - 36), 24.0));
    const subg = gainNode(ctx, 0.2);
    for (const n of [1, 2]) {
      const lfo = osc(ctx, 'sine', n / 24.0);
      const lg = gainNode(ctx, 0.05 / n);
      lfo.connect(lg); lg.connect(subg.gain);
      lfo.start(0); lfo.stop(total);
    }
    sub.connect(subg); subg.connect(out);
    sub.start(0); sub.stop(total);

    // a low sawtooth drone bed for body
    for (const [m, a] of [[D - 24, 0.05], [D - 17, 0.03], [D - 12, 0.022]]) {
      const o1 = osc(ctx, 'sawtooth', lockFreq(mtof(m), 24.0));
      const lp = filt(ctx, 'lowpass', 340, 2.2);
      const flfo = osc(ctx, 'sine', 1 / 24.0);
      const flg = gainNode(ctx, 120);
      flfo.connect(flg); flg.connect(lp.frequency);
      flfo.start(0); flfo.stop(total);
      const g = gainNode(ctx, a);
      o1.connect(lp); lp.connect(g); g.connect(dry); g.connect(wet);
      o1.start(0); o1.stop(total);
    }

    // bell tolls on the downbeat of each bar
    const bellNotes = [D - 24, D - 26, D - 29, D - 28];
    for (let i = 0; i < 4; i++) {
      lowBell(ctx, dry, wet, i * bar + 0.05, bellNotes[i], 0.2, 5.6);
    }

    // sparse high motif drifting over the top
    const motif = [
      [2.0, D + 12], [3.2, D + 10], [4.4, D + 7],
      [8.5, D + 10], [9.6, D + 12], [11.0, D + 9],
      [14.5, D + 7], [15.8, D + 5], [17.0, D + 3],
      [20.5, D + 12], [21.9, D + 14], [22.9, D + 12],
    ];
    for (const [t, m] of motif) {
      const p = ping(ctx, dry, {
        t, freq: mtof(m), dur: 3.0, peak: 0.075, mod: 2.003, index: 0.45,
        modDecay: 0.22, pan: jit(rng, 0.65),
      });
      p.out.connect(wet);
    }

    // wind bed (loop-locked LFOs)
    for (let k = 0; k < 2; k++) {
      const s = ctx.createBufferSource();
      s.buffer = lib.noise.brown; s.loop = true;
      s.playbackRate.value = 0.85 + k * 0.25;
      const bp = filt(ctx, 'bandpass', 380 + k * 420, 0.8);
      const g = gainNode(ctx, 0.1 - k * 0.03);
      for (const n of [1, 2, 3]) {
        const lfo = osc(ctx, 'sine', n / 24.0);
        const lg = gainNode(ctx, 0.035 / n);
        lfo.connect(lg); lg.connect(g.gain);
        lfo.start(0); lfo.stop(total);
        const flfo = osc(ctx, 'sine', n / 24.0);
        flfo.detune.value = k * 120;
        const flg = gainNode(ctx, 200 / n);
        flfo.connect(flg); flg.connect(bp.frequency);
        flfo.start(0); flfo.stop(total);
      }
      s.connect(bp); bp.connect(g); g.connect(panner(ctx, k ? 0.6 : -0.6)).connect(out);
      s.start(0, rnd(rng, 0, 3)); s.stop(total);
    }
  },
};

/**
 * game_over music — 16 s seamless loop. Almost nothing happens: a held minor
 * chord, a bell every 8 s, a descending figure, and a lot of room.
 */
MUSIC.game_over = {
  dur: 16.0, xfade: 3.0, loop: true, gain: 1.0, bus: 'music', srScale: 0.5,
  build(ctx, out, rng, v, lib) {
    const total = 19.0;
    const rev = makeReverb(ctx, { decay: 6.5, damp: 2000, preDelay: 0.04, combs: 8, gain: 1 });
    const wetGain = gainNode(ctx, 0.9);
    rev.output.connect(wetGain); wetGain.connect(out);
    const dry = gainNode(ctx, 0.55); dry.connect(out);
    const wet = rev.input;

    // two long chords, 8 s each: Dm  →  Bbm (borrowed, hopeless)
    choirChord(ctx, dry, wet, 0.0, [D - 12, D - 5, D, D + 3], 9.6, 0.15, 'u', rng,
      { attack: 2.6, release: 3.4, lp: 2000, detune: 16, stagger: 0.2 });
    choirChord(ctx, dry, wet, 8.0, [D - 14, D - 7, D - 2, D + 1], 9.6, 0.15, 'o', rng,
      { attack: 2.6, release: 3.4, lp: 1900, detune: 16, stagger: 0.2 });

    // sub — dips a tone for the second chord, then returns before the loop seam
    const subA = lockFreq(mtof(D - 36), 16.0);
    const subB = lockFreq(mtof(D - 38), 16.0);
    const sub = osc(ctx, 'sine', subA);
    setAt(sub.frequency, subA, 7.2);
    linTo(sub.frequency, subB, 8.4);
    setAt(sub.frequency, subB, 14.2);
    linTo(sub.frequency, subA, 15.4);
    const subg = gainNode(ctx, 0.22);
    const slfo = osc(ctx, 'sine', 1 / 16.0);
    const slg = gainNode(ctx, 0.06);
    slfo.connect(slg); slg.connect(subg.gain);
    slfo.start(0); slfo.stop(total);
    sub.connect(subg); subg.connect(out);
    sub.start(0); sub.stop(total);

    // two tolls
    lowBell(ctx, dry, wet, 0.05, D - 26, 0.22, 7.5);
    lowBell(ctx, dry, wet, 8.05, D - 28, 0.2, 7.5);

    // slow descending figure
    const line = [[1.4, D + 7], [3.0, D + 5], [4.8, D + 3], [6.6, D + 2],
                  [9.4, D + 5], [11.0, D + 3], [12.8, D + 1], [14.4, D]];
    for (const [t, m] of line) {
      const p = ping(ctx, dry, { t, freq: mtof(m), dur: 3.4, peak: 0.07, mod: 2.002, index: 0.42, modDecay: 0.2, pan: jit(rng, 0.5) });
      p.out.connect(wet);
    }

    // wind
    const s = ctx.createBufferSource();
    s.buffer = lib.noise.brown; s.loop = true;
    const bp = filt(ctx, 'bandpass', 420, 0.8);
    const g = gainNode(ctx, 0.08);
    for (const n of [1, 2]) {
      const lfo = osc(ctx, 'sine', n / 16.0);
      const lg = gainNode(ctx, 0.03 / n);
      lfo.connect(lg); lg.connect(g.gain);
      lfo.start(0); lfo.stop(total);
      const flfo = osc(ctx, 'sine', n / 16.0);
      const flg = gainNode(ctx, 180 / n);
      flfo.connect(flg); flg.connect(bp.frequency);
      flfo.start(0); flfo.stop(total);
    }
    s.connect(bp); bp.connect(g); g.connect(out);
    s.start(0, rnd(rng, 0, 3)); s.stop(total);
  },
};

/* ================================================================== *
 * In-round tension
 *
 * From round 1 to round 40 the only continuous audio in the game was
 * `ambient_loop`: wind and a drone. Nothing escalated, so nothing ever felt
 * worse than it had five rounds earlier.
 *
 * `round_bed_loop` is the always-on bed — a sub pulse, a heartbeat-adjacent
 * rhythm and a little broken-radio texture, deliberately low enough that it is
 * felt rather than listened to. Two further layers stack *on top* of it through
 * `audio.loop()` (they are seamless loops of the same 8 s grid, so they phase
 * against each other without ever colliding):
 *
 *   round_bed_layer_pulse  — a driving eighth-note pulse + a rising swell.
 *                            Fade in from about round 6.
 *   round_bed_layer_choir  — a detuned, wrong-sounding choir a fifth above.
 *                            Fade in from about round 15.
 *
 * Because everything is locked to the same 8 s length, a caller can start and
 * stop layers at any time with a slow fade and never hear a seam.
 * ================================================================== */

/** The grid every in-round layer shares. Changing it changes all three. */
const BED = 8.0;

MUSIC.round_bed_loop = {
  dur: BED, xfade: 1.6, loop: true, gain: 1.0, bus: 'music', srScale: 0.5, level: -27,
  build(ctx, out, rng, v, lib) {
    const total = BED + 1.8;
    const rev = makeReverb(ctx, { decay: 4.0, damp: 2000, preDelay: 0.03, combs: 6, gain: 1 });
    const wetGain = gainNode(ctx, 0.5);
    rev.output.connect(wetGain); wetGain.connect(out);
    const dry = gainNode(ctx, 0.75); dry.connect(out);

    // --- the floor: a D sub that never stops, breathing on the loop grid ---
    const sub = osc(ctx, 'sine', lockFreq(mtof(D - 36), BED));
    const subg = gainNode(ctx, 0.5);
    for (const n of [1, 2]) {
      const lfo = osc(ctx, 'sine', n / BED);
      const lg = gainNode(ctx, 0.14 / n);
      lfo.connect(lg); lg.connect(subg.gain);
      lfo.start(0); lfo.stop(total);
    }
    sub.connect(subg); subg.connect(out);
    sub.start(0); sub.stop(total);

    // a fifth above it, filtered right down, for weight without pitch
    const fifth = osc(ctx, 'triangle', lockFreq(mtof(D - 29), BED));
    const flp = filt(ctx, 'lowpass', 150, 1.4);
    const fg = gainNode(ctx, 0.16);
    fifth.connect(flp); flp.connect(fg); fg.connect(dry);
    fifth.start(0); fifth.stop(total);

    // --- the pulse: two per bar, low, dull, slightly irregular in level ---
    for (let i = 0; i < 4; i++) {
      const t = i * (BED / 4);
      const amp = i % 2 === 0 ? 0.5 : 0.3;
      const th = thump(ctx, dry, { t, f0: 62, f1: 30, dur: 0.6, glide: 0.2, peak: amp, type: 'sine', drive: 2 });
      th.gain.connect(rev.input);
      // a dry skin hit on top so it reads as a hit, not just a swell
      noiseBurst(ctx, dry, {
        noise: lib.noise.brown, t, type: 'lowpass', f0: 260, f1: 80, q: 1.4,
        sweep: 0.12, attack: 0.004, decay: 0.2, peak: amp * 0.35, rng,
      });
    }

    // --- a slow tolling low bell on the downbeat, well back in the room ---
    const b = bell(ctx, dry, {
      t: 0.02, freq: mtof(D - 26), dur: BED * 0.85, peak: 0.075,
      partials: [[0.5, 0.5, 1.1], [1, 1, 1], [1.19, 0.4, 0.8], [2, 0.3, 0.55], [3.01, 0.15, 0.35]],
      stretch: 0.002,
    });
    b.out.connect(rev.input);

    // --- broken-radio texture: something is transmitting and it is not friendly
    for (let i = 0; i < 3; i++) {
      const t = rnd(rng, 0.4, BED - 1.2);
      noiseBurst(ctx, dry, {
        noise: lib.noise.pink, t, type: 'bandpass', f0: rnd(rng, 1400, 2600), q: 5,
        attack: 0.05, decay: rnd(rng, 0.2, 0.5), peak: 0.035,
        pan: rnd(rng, -0.8, 0.8), curve: 'lin', rng,
      });
    }
    // and one distant, very wrong voice per cycle
    const vo = choirVoice(ctx, dry, {
      t: rnd(rng, 1.0, 3.0), freq: mtof(D - 14) * 1.004, dur: rnd(rng, 2.0, 3.0),
      peak: 0.035, vowel: 'u', voices: 3, detune: 22, spread: 10, vib: 1.6,
      attack: 1.1, release: 1.4, lp: 1400, fscale: 0.9, pan: rnd(rng, -0.6, 0.6), rng,
    });
    vo.out.connect(rev.input);

    // --- wind, so it never sounds like a click track in a vacuum ---
    const w = ctx.createBufferSource();
    w.buffer = lib.noise.brown; w.loop = true;
    const wbp = filt(ctx, 'bandpass', 360, 0.8);
    const wg = gainNode(ctx, 0.07);
    for (const n of [1, 2]) {
      const lfo = osc(ctx, 'sine', n / BED);
      const lg = gainNode(ctx, 0.025 / n);
      lfo.connect(lg); lg.connect(wg.gain);
      lfo.start(0); lfo.stop(total);
      const flfo = osc(ctx, 'sine', n / BED);
      const flg = gainNode(ctx, 140 / n);
      flfo.connect(flg); flg.connect(wbp.frequency);
      flfo.start(0); flfo.stop(total);
    }
    w.connect(wbp); wbp.connect(wg); wg.connect(out);
    w.start(0, rnd(rng, 0, 3)); w.stop(total);
  },
};

MUSIC.round_bed_layer_pulse = {
  dur: BED, xfade: 1.6, loop: true, gain: 1.0, bus: 'music', srScale: 0.5, level: -28,
  build(ctx, out, rng, v, lib) {
    const total = BED + 1.8;
    const rev = makeReverb(ctx, { decay: 2.2, damp: 3200, preDelay: 0.018, combs: 6, gain: 1 });
    const wetGain = gainNode(ctx, 0.35);
    rev.output.connect(wetGain); wetGain.connect(out);
    const dry = gainNode(ctx, 0.85); dry.connect(out);

    // a driving eighth-note figure on a muted, filtered saw — the thing that
    // tells the player the round is no longer a warm-up
    const step = BED / 16;
    for (let i = 0; i < 16; i++) {
      const t = i * step;
      const accent = (i % 4 === 0) ? 1 : (i % 2 === 0 ? 0.6 : 0.34);
      const m = (i % 8 === 6) ? D - 22 : (i % 8 === 3 ? D - 19 : D - 24);
      const o1 = osc(ctx, 'sawtooth', mtof(m));
      o1.detune.value = jit(rng, 8);
      const bp = filt(ctx, 'lowpass', 400, 6);
      setAt(bp.frequency, 220 + accent * 900, t);
      expTo(bp.frequency, 180, t + 0.22);
      const g = gainNode(ctx, 0);
      ampEnv(g.gain, { t, peak: 0.13 * accent, attack: 0.004, decay: step * 0.85 });
      o1.connect(bp); bp.connect(g); g.connect(dry);
      if (i % 4 === 0) g.connect(rev.input);
      o1.start(t); o1.stop(t + step + 0.1);
    }

    // a metallic tick on the off-beats, panned wide, like something in the dark
    for (let i = 0; i < 8; i++) {
      const t = i * (BED / 8) + BED / 16;
      clack(ctx, dry, {
        t, freqs: [rnd(rng, 3400, 5200), rnd(rng, 6400, 9000)],
        dur: 0.02, peak: 0.055, noise: lib.noise.white, bright: 6000, rng,
      });
    }

    // a swell that crests at the loop point so the bed keeps leaning forward
    const sw = ctx.createBufferSource();
    sw.buffer = lib.noise.pink; sw.loop = true;
    const sbp = filt(ctx, 'bandpass', 400, 0.9);
    setAt(sbp.frequency, 260, 0); expTo(sbp.frequency, 2600, BED);
    const sg = gainNode(ctx, 0);
    setAt(sg.gain, 1e-4, 0);
    expTo(sg.gain, 0.075, BED);
    sw.connect(sbp); sbp.connect(sg); sg.connect(out); sg.connect(rev.input);
    sw.start(0, rnd(rng, 0, 2)); sw.stop(total);
  },
};

MUSIC.round_bed_layer_choir = {
  dur: BED, xfade: 1.6, loop: true, gain: 1.0, bus: 'music', srScale: 0.5, level: -29,
  build(ctx, out, rng, v, lib) {
    const rev = makeReverb(ctx, { decay: 5.0, damp: 2400, preDelay: 0.035, combs: 8, gain: 1 });
    const wetGain = gainNode(ctx, 0.75);
    rev.output.connect(wetGain); wetGain.connect(out);
    const dry = gainNode(ctx, 0.45); dry.connect(out);

    // Dm with the fifth sharpened into a tritone against the bed's D — massed,
    // badly tuned, and it never resolves.
    choirChord(ctx, dry, rev.input, 0.0, [D - 12, D - 5, D, D + 6], BED + 1.4, 0.1, 'u', rng,
      { attack: 2.4, release: 3.0, lp: 2100, detune: 24, spread: 11, voices: 4, stagger: 0.25 });
    // one voice a semitone off the rest, drifting — the part that unsettles
    const stray = choirVoice(ctx, dry, {
      t: BED * 0.35, freq: mtof(D + 1), dur: BED * 0.55, peak: 0.05,
      vowel: 'o', voices: 2, detune: 30, spread: 14, vib: 2.2,
      attack: 1.3, release: 1.6, lp: 1900, pan: rnd(rng, -0.5, 0.5), rng,
    });
    stray.out.connect(rev.input);
  },
};

export default { STINGERS, MUSIC };
