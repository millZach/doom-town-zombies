/**
 * audio.js — Doom Town audio engine.
 *
 * Sounds come from two places, in this order of preference:
 *
 *  1. **Recorded / generated files** listed in `public/audio/manifest.json`
 *     (name -> { files: [...variants], gain, loop, bus, send, jitter }).
 *     They are fetched and decoded at init and take over the name completely:
 *     real gunshots, real foley, recorded zombie and hellhound vocals, the
 *     layered round stingers, the announcer. This is what ships.
 *
 *  2. **Synthesised recipes** (see sfx.js / music.js), rendered once at init
 *     into an AudioBuffer with an OfflineAudioContext. They are now a
 *     *fallback*: any name the manifest does not cover — or whose files fail
 *     to load — still makes its old sound, so the engine degrades to a fully
 *     playable game with no network at all.
 *
 * Everything downstream of the buffer (buses, spatialisation, the shared
 * reverb sends, ducking, the per-name voice caps, variant choice and pitch
 * jitter) is identical for both, so nothing below cares where a buffer
 * came from.
 *
 * API (see docs/ASSET_CONTRACT.md §5):
 *
 *   await audio.init()                            // from a user gesture
 *   audio.setListener(camera)                     // every frame
 *   audio.play(name, { volume, rate, detune })    -> handle   (2D)
 *   audio.playAt(name, vec3, { volume, rate })    -> handle   (3D)
 *   audio.loop(name, { volume, position, rate })  -> handle
 *   audio.music(name) / audio.stopMusic(fadeSec)
 *   audio.setMasterVolume(v) / audio.duck(amount, seconds)
 *   audio.announce(text)
 *
 * Unknown sound names are a silent no-op and never throw.
 */

import {
  mulberry32, clamp, makeNoiseBuffer, makeIR, normalizeBuffer, rmsNormalize, deClick,
  foldSeamless, makeOffline, trimTail, maybeMono,
} from './dsp.js';
import { SFX, SFX_ALIASES, VOX_LOOKUP } from './sfx.js';
import { STINGERS, MUSIC } from './music.js';

/* ------------------------------------------------------------------ *
 * Registries
 * ------------------------------------------------------------------ */

/** One-shot / looping sound effects, reachable from play/playAt/loop. */
const SOUNDS = Object.assign(Object.create(null), SFX, STINGERS);
/** Long music beds, reachable from audio.music(). */
const TRACKS = Object.assign(Object.create(null), MUSIC);

/**
 * Alternative spellings that resolve to a rendered recipe. Two names pointing at
 * the same recipe object would otherwise be rendered twice; an alias table costs
 * nothing and lets old call sites (`bullet_impact_wall`) and the new contract
 * names (`impact_concrete`) refer to one set of buffers.
 */
const ALIASES = Object.assign(Object.create(null), SFX_ALIASES);

/**
 * Sounds that automatically duck the world while they play. [amount, seconds]
 *
 * The hold is a little under each sound's own length — the recorded stingers
 * are 5.3–10.4 s, and a duck that released halfway through one would pull the
 * horde back up over its own tail. The depths are shallower than they were
 * because the files are mixed to a real hierarchy now (stingers sit ~8 LU
 * under the guns on their own), so the duck only has to make room, not hide
 * everything.
 */
const AUTO_DUCK = {
  round_end: [0.5, 5.2],
  round_start: [0.5, 4.3],
  hellround_start: [0.52, 4.5],
  game_over: [0.7, 8.6],
  nuke_blast: [0.5, 3.4],
  power_on: [0.4, 3.4],
  pap_upgrade: [0.3, 3.6],
  box_music: [0.3, 3.6],
  // A perk jingle used to drop the whole world to 60 % for 3+ seconds — long
  // enough to lose track of the horde standing behind you. It is a *jingle*:
  // it only needs to peek over the top of the mix for a moment.
  perk_jingle_juggernog: [0.25, 1.2],
  perk_jingle_speedcola: [0.25, 1.2],
  perk_jingle_quickrevive: [0.25, 1.2],
  perk_jingle_doubletap: [0.25, 1.2],
};

/**
 * Render sample-rate policy. Sounds whose content is band-limited by their own
 * synthesis (voices behind a 3 kHz formant filter, choir pads, wind, drones)
 * are rendered at a fraction of the context rate: the buffer source resamples
 * transparently on playback and we save both render time and buffer memory.
 *
 * NOTE: anything that uses a ConvolverNode with one of the shared impulse
 * responses must stay at 1.0 — ConvolverNode rejects an IR whose sample rate
 * differs from its context. That is every gun, explosion and raygun sound.
 */
const SR_SCALE = {
  // zombie + hellhound voices: everything above ~5 kHz is already filtered out
  zombie_groan: 0.5, zombie_death: 0.5, zombie_scream: 0.5, zombie_attack: 0.5,
  zombie_rise_dirt: 0.5, hellhound_growl: 0.5, hellhound_bite: 0.5,
  player_hurt: 0.5, player_down: 0.5, perk_burp: 0.5,
  // music: choir pads, low bells, wind
  round_end: 0.5, round_start: 0.5, hellround_start: 0.5, game_over: 0.5,
  menu: 0.5, ambient_loop: 0.5, heartbeat_loop: 0.5, fire_loop: 0.5,
  perk_jingle_juggernog: 0.5, perk_jingle_speedcola: 0.5,
  perk_jingle_quickrevive: 0.5, perk_jingle_doubletap: 0.5,
  door_open: 0.5,
  // mixed content — keep more headroom for the bright bits
  box_music: 0.75, box_open: 0.75, box_close: 0.75, box_teddy: 0.75,
  pap_upgrade: 0.75, power_on: 0.75, powerup_spawn: 0.75, powerup_loop: 0.75,
  powerup_grab: 0.75, hellhound_spawn: 0.75, perk_drink: 0.75,
  board_tear: 0.75, board_repair: 0.75, board_slam: 0.75,
  max_ammo: 0.75, insta_kill: 0.75, double_points: 0.75, carpenter: 0.75, fire_sale: 0.75,
  footstep_dirt: 0.75, footstep_wood: 0.75, footstep_concrete: 0.75,
  zombie_footstep: 0.5, zombie_bodyfall: 0.5, hellhound_footstep: 0.5, hellhound_death: 0.5,
  round_bed_loop: 0.5, round_bed_layer_pulse: 0.5, round_bed_layer_choir: 0.5,
  jump_grunt: 0.5, land_soft: 0.75, land_hard: 0.75,
};

/** Default bus levels. */
const BUS_DEFAULTS = { sfx: 0.9, ui: 0.72, music: 0.62, ambient: 0.5 };

/**
 * How many simultaneous voices of the same sound are allowed.
 *
 * This number used to be 6 for everything, which is *below* the number of
 * voices a single automatic weapon needs: an MP5 at 800 rpm (1064 with Double
 * Tap) fires 13–18 rounds a second, so with a dry buffer of ~0.35 s you need
 * 5–7 voices just for the shots — and each shot also feeds the shared tail.
 * A cap under that stops the oldest voice mid-decay on every trigger pull,
 * which is an audible gate right in the middle of sustained fire.
 */
const SAME_NAME_CAP = {
  default: 6,
  // per-type (legacy names, still used as fallbacks)
  gun_pistol: 10, gun_revolver: 8, gun_rifle: 12, gun_smg: 16, gun_shotgun: 6, gun_lmg: 16,
  // per-weapon
  gun_m1911: 10, gun_python: 8, gun_m14: 12, gun_galil: 14, gun_ak74u: 16, gun_mp5: 16,
  gun_rpd: 16, gun_remington870: 6, gun_olympia: 6, gun_raygun: 8, gun_pap_layer: 12,
  // world
  zombie_groan: 5, zombie_footstep: 12, hellhound_footstep: 10,
  flesh_hit: 8, impact_flesh: 8, impact_concrete: 10, impact_wood: 8,
  impact_metal: 8, impact_dirt: 8, bullet_impact_wall: 10,
  shell_drop: 10, shell_drop_shotgun: 6,
  hitmarker: 8, hitmarker_head: 6,
};
const MAX_VOICES = 80;

/**
 * Loudness targets, in dBFS short-term RMS.
 *
 * Peak-normalising every sound to the same number (what this engine used to do)
 * destroys the mix: a 12-gauge blast, a UI hover tick and a footstep all leave
 * the renderer at 0.95 peak, and a long reverberant explosion ends up with far
 * *less* perceived level than a 40 ms click. Relative loudness then has to be
 * hand-dialled in the `gain` field and at every call site, and it never lines up.
 *
 * Instead every recipe declares (or inherits from this table) a target RMS, and
 * `rmsNormalize` scales to it with a peak ceiling. The numbers below are the
 * actual dynamic hierarchy of the game, loudest to quietest, and with the whole
 * hierarchy living in one place every recipe's `gain` is now simply 1.
 *
 * These are buffer levels, not what reaches the ear. Call sites pass their own
 * `volume` (footsteps at 0.35, impacts at 0.5, guns at 1.0) and positional
 * sounds lose another 10–20 dB to distance, so the quiet end of the table sits a
 * few dB above where you would put it if these were final mix levels.
 */
const LEVEL_DEFAULTS = [
  [/^nuke_blast$/, -9],
  [/^explosion$/, -11],
  [/^gun_(shotgun|olympia|remington870)$/, -11],
  [/^gun_(lmg|rpd|rifle|m14|galil|revolver|python)$/, -12.5],
  [/^gun_/, -13.5],
  [/^raygun_impact$/, -12],
  [/^(headshot|player_down|hellhound_spawn|power_on|pap_upgrade)$/, -14],
  [/^player_hurt$/, -16],
  [/^(round_start|round_end|hellround_start|game_over|box_music)$/, -16],
  [/^(board_slam|board_tear|board_repair|door_open|box_)/, -17],
  [/^(perk_|purchase|powerup_|max_ammo|insta_kill|double_points|carpenter|fire_sale)/, -18],
  [/^zombie_footstep/, -27],
  [/^hellhound_footstep/, -26],
  [/^(zombie_|hellhound_)/, -17],
  [/^(knife_|grenade_)/, -19],
  [/^(impact_|bullet_impact_|flesh_hit)/, -18],
  [/^(reload_|bolt_|slide_|pump_|dry_fire|weapon_)/, -22],
  [/^shell_drop/, -23],
  [/^vox_/, -13],
  [/^(hitmarker|ui_|radio_blip)/, -22],
  [/^(footstep_|land_|jump_|ads_)/, -24],
  [/^(ambient_loop|fire_loop|heartbeat_loop|powerup_loop|round_bed)/, -24],
];

function defaultLevel(name) {
  for (let i = 0; i < LEVEL_DEFAULTS.length; i++) {
    if (LEVEL_DEFAULTS[i][0].test(name)) return LEVEL_DEFAULTS[i][1];
  }
  return null;
}

/** Render concurrency — enough to keep the audio thread busy, not enough to thrash. */
const RENDER_CONCURRENCY = 4;

/* ------------------------------------------------------------------ *
 * Sample library
 * ------------------------------------------------------------------ */

/** Where the manifest and its files live, relative to the served root. */
const AUDIO_DIR = 'audio/';

/** How many files are fetched + decoded at once. */
const LOAD_CONCURRENCY = 8;

/**
 * Fields a manifest entry may carry through to the playback record. Everything
 * else about a file-backed sound (duration, channel count) comes from the
 * decoded buffer, and everything about *how* it is played (bus, send, caps,
 * ducking) is the same machinery the synthesised recipes use.
 */
const MANIFEST_FIELDS = ['gain', 'bus', 'loop', 'send', 'sendAmt', 'jitter', 'rateJit'];

function joinUrl(base, rel) {
  return (base.endsWith('/') ? base : base + '/') + rel;
}

/** Served root, honouring a Vite `base` if one is configured. */
function assetBase() {
  try {
    if (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.BASE_URL) {
      return import.meta.env.BASE_URL;
    }
  } catch (e) { /* not a module env */ }
  return '/';
}

/**
 * How late an on-demand render may still be played (seconds). Long enough to
 * cover a background render finishing, short enough that the sound still reads
 * as belonging to the thing that triggered it.
 */
const LATE_PLAY_GRACE = 0.35;

function hashName(s) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

/** Cached backstop curve used on every offline render's master. */
let SAFETY_CURVE = null;

/** Input range the offline backstop curve is built over. See `_render`. */
const RENDER_SAFETY_DOMAIN = 3;

/**
 * Soft limiter transfer curve: transparent below `thresh`, tanh knee above.
 *
 * `domain` is the crucial parameter. A WaveShaper's curve is indexed over an
 * input of [-1, +1] and **the spec clips the input to that range before the
 * lookup** — so a shaper fed 1.3 does not get a soft knee, it gets the curve's
 * endpoint on every sample over unity, i.e. a flat top with all the aliasing
 * that implies. A limiter is exactly the node that gets fed past unity, so the
 * curve is instead built over an input range of [-domain, +domain] and the
 * signal is scaled by 1/domain on the way in (see `limiterPad` in _buildGraph).
 * The curve then reads a +8 dB peak correctly and bends it, which is the whole
 * point of having one.
 */
function limiterCurve(n = 8192, thresh = 0.7, domain = 1) {
  const c = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const x = (i / (n - 1)) * 2 - 1;
    const a = Math.abs(x) * domain;          // the real input level this slot represents
    let y;
    if (a <= thresh) y = a;
    else y = thresh + (1 - thresh) * Math.tanh((a - thresh) / (1 - thresh));
    c[i] = (x < 0 ? -1 : 1) * Math.min(y, 0.997);
  }
  return c;
}

/**
 * How far past full scale the master limiter can still read (linear, not dB).
 * 2.5 ≈ +8 dB: enough for the loudest one-shot at master volume 2.0, or a
 * four-gun pile-up at 1.0, to land inside the curve instead of on its endpoint.
 */
const LIMITER_DOMAIN = 2.5;

/**
 * Mix headroom, applied to everything just before the master fader.
 *
 * One-shots are deliberately allowed to peak past 1.0 (see `_render`), so
 * without a trim here the loudest single shotgun blast would arrive at the
 * limiter already over unity and get its 3 ms crack bent down — on its own,
 * with nothing else playing. -2.5 dB of headroom means one voice, however
 * peaky, passes the limiter untouched and the limiter only works on pile-ups,
 * which is what a limiter is for. Master volume runs to 2.0, so nothing is lost.
 */
const MASTER_HEADROOM = 0.75;

/* ------------------------------------------------------------------ *
 * Voice handle
 * ------------------------------------------------------------------ */

class Handle {
  constructor(engine, name, src, gain, pannerNode, airFilter, isLoop) {
    this.engine = engine;
    this.name = name;
    this.source = src;
    this.gainNode = gain;
    this.panner = pannerNode || null;
    this.air = airFilter || null;
    this.isLoop = !!isLoop;
    this.isPlaying = true;
    this.startedAt = engine.ctx ? engine.ctx.currentTime : 0;
    this.baseVolume = 1;
  }

  setPosition(v) {
    if (!this.panner || !v) return this;
    const x = v.x != null ? v.x : (v[0] || 0);
    const y = v.y != null ? v.y : (v[1] || 0);
    const z = v.z != null ? v.z : (v[2] || 0);
    const p = this.panner;
    if (p.positionX) {
      p.positionX.value = x; p.positionY.value = y; p.positionZ.value = z;
    } else if (p.setPosition) {
      p.setPosition(x, y, z);
    }
    if (this.air) this.air.frequency.value = this.engine._airCutoff(x, y, z);
    return this;
  }

  setVolume(v, fade = 0.02) {
    if (!this.gainNode || !this.engine.ctx) return this;
    const g = this.gainNode.gain;
    const now = this.engine.ctx.currentTime;
    const target = Math.max(0, v) * this.baseVolume;
    try {
      g.cancelScheduledValues(now);
      g.setValueAtTime(Math.max(1e-5, g.value), now);
      g.linearRampToValueAtTime(target, now + Math.max(0.005, fade));
    } catch (e) { g.value = target; }
    return this;
  }

  setRate(r) {
    if (this.source && this.source.playbackRate) this.source.playbackRate.value = Math.max(0.05, r);
    return this;
  }

  setDetune(cents) {
    if (this.source && this.source.detune) this.source.detune.value = cents;
    return this;
  }

  stop(fadeSec = 0.08) {
    if (!this.isPlaying || !this.engine.ctx) return this;
    this.isPlaying = false;
    const now = this.engine.ctx.currentTime;
    const f = Math.max(0.005, fadeSec || 0.005);
    try {
      const g = this.gainNode.gain;
      g.cancelScheduledValues(now);
      g.setValueAtTime(Math.max(1e-5, g.value), now);
      g.exponentialRampToValueAtTime(1e-4, now + f);
      g.setValueAtTime(0, now + f + 0.005);
    } catch (e) { /* ignore */ }
    try { this.source.stop(now + f + 0.02); } catch (e) { /* already stopped */ }
    this.engine._retire(this);
    return this;
  }
}

/** A handle that does nothing — returned for unknown names so callers can chain. */
const NULL_HANDLE = {
  name: null, isPlaying: false, isLoop: false,
  setPosition() { return this; },
  setVolume() { return this; },
  setRate() { return this; },
  setDetune() { return this; },
  stop() { return this; },
};

/* ------------------------------------------------------------------ *
 * Engine
 * ------------------------------------------------------------------ */

class AudioEngine {
  constructor() {
    this.ctx = null;
    this.ready = false;
    this.initPromise = null;
    this.buffers = new Map();        // name -> AudioBuffer[]
    this.trackBuffers = new Map();   // name -> AudioBuffer
    this.voices = new Set();
    this.nameCounts = new Map();
    this.lastVariant = new Map();
    this.musicHandle = null;
    this.musicName = null;
    this.musicToken = 0;
    this.deferredPromise = null;
    this.masterVolume = 1;
    this.busVolumes = Object.assign({}, BUS_DEFAULTS);
    this.muted = false;
    this.onProgress = null;
    this.initMs = 0;
    /** Names served by `public/audio/**` rather than by a synthesised recipe. */
    this.fileNames = new Set();
    this.filesLoaded = 0;
    this.filesFailed = 0;
    this._listenerState = { x: NaN, y: NaN, z: NaN };
    this._announceQueue = [];
    this._announcing = false;
    this._lib = null;
  }

  /* ---------------- lifecycle ---------------- */

  /**
   * Build the audio graph and render every sound. Must be called from a user
   * gesture. Safe to call more than once (returns the same promise).
   */
  init(opts = {}) {
    if (this.initPromise) return this.initPromise;
    this.initPromise = this._init(opts).catch((err) => {
      console.warn('[audio] init failed, running silent:', err);
      this.ready = false;
      return this;
    });
    return this.initPromise;
  }

  async _init(opts) {
    const t0 = (typeof performance !== 'undefined' ? performance.now() : Date.now());
    const AC = (typeof AudioContext !== 'undefined') ? AudioContext
      : (typeof webkitAudioContext !== 'undefined' ? webkitAudioContext : null);
    if (!AC) throw new Error('Web Audio not supported');

    const ctx = new AC({ latencyHint: 'interactive' });
    this.ctx = ctx;
    if (ctx.state === 'suspended' && ctx.resume) { try { await ctx.resume(); } catch (e) { /* noop */ } }
    this.onProgress = opts.onProgress || this.onProgress;

    this._buildGraph();
    this._buildLib();
    this._buildSends();

    /*
     * Phase 0: the sample library. Every name it covers is taken out of the
     * render queues below, so the synth only ever pays for what the manifest
     * does not provide. A missing or broken manifest is not an error — it just
     * means the whole game falls back to the procedural recipes.
     */
    await this._loadFiles(opts);

    /*
     * Two-phase render. The library is much bigger than it was (ten per-weapon
     * gunshots, twenty-odd reload parts, per-surface impacts, zombie foley), so
     * everything that is not needed in the first seconds of a match is pushed
     * into the background pass: perk jingles, the mystery box, power-ups, the
     * Pack-a-Punch, the end-of-round stingers, the music beds. Init therefore
     * renders *less* than it used to, not more, and anything that does get asked
     * for early is rendered on demand by `_ensure()`.
     */
    const core = [];
    const later = [];
    for (const name of Object.keys(SOUNDS)) {
      (SOUNDS[name] && SOUNDS[name].defer ? later : core).push(name);
    }
    await this._renderAll(core, SOUNDS, this.buffers, 'sfx');

    this.ready = true;
    this.initMs = Math.round((typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0);

    // ---- phase 2: the rare/expensive one-shots, then the long music beds ----
    this.deferredPromise = this._renderAll(later, SOUNDS, this.buffers, 'sfx-deferred')
      .then(() => this._renderAll(Object.keys(TRACKS), TRACKS, this.trackBuffers, 'music'))
      .catch((e) => { console.warn('[audio] deferred render failed:', e); });

    if (opts.awaitMusic) await this.deferredPromise;
    return this;
  }

  /**
   * Phase 0 — fetch and decode `public/audio/manifest.json` and everything it
   * points at, then hand those names over to the file buffers.
   *
   * Nothing here can fail the init: a manifest that 404s, a file that will not
   * decode, a browser without `fetch` — each one just leaves that name to its
   * synthesised recipe. `filesLoaded` records what actually made it.
   */
  async _loadFiles(opts = {}) {
    this.filesLoaded = 0;
    this.filesFailed = 0;
    this.fileNames = new Set();
    if (opts.noFiles || typeof fetch !== 'function') return;

    const base = joinUrl(assetBase(), AUDIO_DIR);
    let manifest = null;
    try {
      const res = await fetch(joinUrl(base, 'manifest.json'), { cache: 'force-cache' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      manifest = await res.json();
    } catch (e) {
      console.warn('[audio] no sample manifest (' + e.message + '); using synthesised sounds');
      return;
    }
    const entries = Object.entries((manifest && manifest.sounds) || {});
    if (!entries.length) return;

    // Flatten to one job per file so the progress bar moves smoothly and a
    // single slow variant cannot stall a whole sound.
    const jobs = [];
    for (const [name, rec] of entries) {
      const files = Array.isArray(rec.files) ? rec.files : [];
      files.forEach((f, i) => jobs.push({ name, rec, i, url: joinUrl(base, f) }));
    }
    const decoded = new Map();     // name -> AudioBuffer[]
    let done = 0;
    const total = jobs.length;

    const worker = async (start) => {
      for (let k = start; k < jobs.length; k += LOAD_CONCURRENCY) {
        const j = jobs[k];
        try {
          const res = await fetch(j.url, { cache: 'force-cache' });
          if (!res.ok) throw new Error('HTTP ' + res.status);
          const bytes = await res.arrayBuffer();
          const buf = await this._decode(bytes);
          let arr = decoded.get(j.name);
          if (!arr) { arr = []; decoded.set(j.name, arr); }
          arr[j.i] = buf;
        } catch (e) {
          this.filesFailed++;
          if (this.filesFailed <= 5) console.warn('[audio] could not load ' + j.url + ':', e.message);
        }
        done++;
        if (this.onProgress && (done % 4 === 0 || done === total)) {
          try { this.onProgress(done / total, 'samples'); } catch (e) { /* noop */ }
        }
      }
    };
    await Promise.all(
      Array.from({ length: Math.min(LOAD_CONCURRENCY, jobs.length) }, (_, i) => worker(i)),
    );

    // Commit whatever decoded. A sound is only taken over if at least one of
    // its variants survived; a half-loaded set simply plays the ones it has.
    for (const [name, rec] of entries) {
      const arr = (decoded.get(name) || []).filter(Boolean);
      if (!arr.length) continue;
      const prev = SOUNDS[name] || TRACKS[name] || null;
      const fileRec = {
        fromFile: true,
        src: rec.src || '',
        dur: arr[0].duration,
        variants: arr.length,
        gain: 1,
      };
      for (const k of MANIFEST_FIELDS) if (rec[k] != null) fileRec[k] = rec[k];
      // `speech` tells announce() when the words stop; only the recipes know it,
      // so carry it across and correct it to the recorded length.
      if (prev && prev.speech != null) fileRec.speech = arr[0].duration;
      SOUNDS[name] = fileRec;
      this.buffers.set(name, arr);
      this.fileNames.add(name);
      this.filesLoaded += arr.length;
    }

    // Music beds. `manifest.tracks` maps a track name onto the sound that holds
    // it, so `music('game_over')` reaches the recorded bed even though the
    // one-shot sting owns the plain `game_over` name.
    const trackMap = Object.assign({}, (manifest && manifest.tracks) || {});
    for (const key of Object.keys(TRACKS)) {
      if (!(key in trackMap) && this.fileNames.has(key)) trackMap[key] = key;
    }
    for (const [track, sound] of Object.entries(trackMap)) {
      const arr = this.buffers.get(sound);
      if (!arr || !arr.length) continue;
      TRACKS[track] = SOUNDS[sound];
      this.trackBuffers.set(track, arr[0]);
      this.fileNames.add(track);
    }

    console.info('[audio] loaded ' + this.filesLoaded + ' sample files for '
      + (this.fileNames.size) + ' names'
      + (this.filesFailed ? ' (' + this.filesFailed + ' failed)' : ''));
  }

  /** decodeAudioData, promise form, on both the modern and the callback API. */
  _decode(bytes) {
    return new Promise((resolve, reject) => {
      let p;
      try { p = this.ctx.decodeAudioData(bytes, resolve, reject); } catch (e) { reject(e); return; }
      if (p && typeof p.then === 'function') p.then(resolve, reject);
    });
  }

  /**
   * Render one sound right now if the deferred pass has not reached it yet.
   * Returns a promise, but callers do not have to wait: the current trigger is
   * silent and every later one plays. Never renders the same name twice.
   */
  _ensure(name) {
    const canon = ALIASES[name] || name;
    if (this.buffers.has(canon) || this.trackBuffers.has(canon)) return Promise.resolve();
    this._pending = this._pending || new Map();
    if (this._pending.has(canon)) return this._pending.get(canon);
    const rec = SOUNDS[canon] || TRACKS[canon];
    if (!rec || typeof rec.build !== 'function' || !this.ctx) return Promise.resolve();
    const target = SOUNDS[canon] ? this.buffers : this.trackBuffers;
    const p = this._renderAll([canon], SOUNDS[canon] ? SOUNDS : TRACKS, target, 'on-demand')
      .catch((e) => { console.warn('[audio] on-demand render failed for ' + canon + ':', e); })
      .then(() => { this._pending.delete(canon); });
    this._pending.set(canon, p);
    return p;
  }

  _buildGraph() {
    const ctx = this.ctx;

    this.destinationGain = ctx.createGain();
    this.destinationGain.gain.value = 1;

    /*
     * Glue compressor.
     *
     * The old settings (−14 dB, 6:1, 4 ms attack, music routed through it) did
     * two things wrong. A 4 ms attack is *slower than the crack of a gunshot*,
     * so the compressor let the transient through unmodified and then clamped
     * the body — which reads as the gun losing its punch a frame after you pull
     * the trigger. And with music upstream of it, every burst of fire pumped the
     * score. Now: a high threshold and a gentle ratio so it only catches the
     * horde-plus-explosion pile-ups, a 20 ms attack that steps out of the way of
     * transients entirely, and music joined downstream (see below).
     */
    this.compressor = ctx.createDynamicsCompressor();
    this.compressor.threshold.value = -6;
    this.compressor.knee.value = 10;
    this.compressor.ratio.value = 3;
    this.compressor.attack.value = 0.02;
    this.compressor.release.value = 0.25;

    // scale into the shaper's readable range, then bend with a curve built over
    // that same range — so the limiter limits instead of clipping (see above)
    this.limiterPad = ctx.createGain();
    this.limiterPad.gain.value = 1 / LIMITER_DOMAIN;
    this.limiter = ctx.createWaveShaper();
    this.limiter.curve = limiterCurve(8192, 0.7, LIMITER_DOMAIN);
    // the knee is where the harmonics are generated, so give it room to fold
    this.limiter.oversample = '4x';

    this.master = ctx.createGain();
    this.master.gain.value = this.masterVolume;

    this.preMaster = ctx.createGain();
    this.preMaster.gain.value = 1;

    // everything that survived the compressor, plus music, meets here — and
    // this is where the mix headroom lives, below the master fader so the
    // player's volume setting still means what it says
    this.postComp = ctx.createGain();
    this.postComp.gain.value = MASTER_HEADROOM;

    // world bus gets ducked under stingers; ui + music do not
    this.duckGain = ctx.createGain();
    this.duckGain.gain.value = 1;

    this.buses = {};
    for (const b of ['sfx', 'ui', 'music', 'ambient']) {
      const g = ctx.createGain();
      g.gain.value = this.busVolumes[b];
      this.buses[b] = g;
    }
    this.buses.sfx.connect(this.duckGain);
    this.buses.ambient.connect(this.duckGain);
    this.duckGain.connect(this.preMaster);
    this.buses.ui.connect(this.preMaster);

    this.preMaster.connect(this.compressor);
    this.compressor.connect(this.postComp);
    // music bypasses the glue compressor so gunfire cannot duck the score
    this.buses.music.connect(this.postComp);

    this.postComp.connect(this.master);
    this.master.connect(this.limiterPad);
    this.limiterPad.connect(this.limiter);
    this.limiter.connect(this.destinationGain);
    this.destinationGain.connect(ctx.destination);

    // listener defaults
    const l = ctx.listener;
    if (l) {
      if (l.forwardX) {
        l.forwardX.value = 0; l.forwardY.value = 0; l.forwardZ.value = -1;
        l.upX.value = 0; l.upY.value = 1; l.upZ.value = 0;
      } else if (l.setOrientation) {
        l.setOrientation(0, 0, -1, 0, 1, 0);
      }
    }
  }

  /** Shared noise beds and impulse responses used by every recipe. */
  _buildLib() {
    const ctx = this.ctx;
    const rng = mulberry32(0xd00d7 >>> 0);
    const noise = {
      white: makeNoiseBuffer(ctx, 2, 4.0, 'white', mulberry32(11)),
      pink: makeNoiseBuffer(ctx, 2, 4.0, 'pink', mulberry32(22)),
      brown: makeNoiseBuffer(ctx, 2, 6.0, 'brown', mulberry32(33)),
    };
    const ir = {
      // tight indoor slap for close mechanics
      tight: makeIR(ctx, { dur: 0.35, tau: 0.09, decay: 2.2, predelay: 0.003, damp: 0.7, seed: 101, early: [[0, 1], [0.005, 0.6], [0.009, 0.4], [0.014, 0.28]] }),
      // suburban living room / house interior
      room: makeIR(ctx, { dur: 0.9, tau: 0.25, decay: 2.0, predelay: 0.006, damp: 0.62, seed: 202 }),
      // open street between houses — short slapback, long-ish flutter
      street: makeIR(ctx, { dur: 1.4, tau: 0.3, decay: 2.6, predelay: 0.012, damp: 0.5, seed: 303, early: [[0, 0.9], [0.017, 0.55], [0.029, 0.42], [0.048, 0.32], [0.071, 0.24], [0.11, 0.16]] }),
      // big reflective hall — sci-fi weapons, box magic
      hall: makeIR(ctx, { dur: 2.4, tau: 0.6, decay: 2.2, predelay: 0.02, damp: 0.42, seed: 404 }),
      // concrete bunker / distant canyon — explosions
      cavern: makeIR(ctx, { dur: 3.6, tau: 1.0, decay: 1.8, predelay: 0.03, damp: 0.35, seed: 505 }),
    };
    this._lib = { noise, ir, rng };
  }

  /**
   * Live effect sends.
   *
   * Gun tails used to be *baked into every shot*: each recipe convolved itself
   * with the 1.4 s street IR and then the buffer was cut at 0.72 s, so every
   * shot ended abruptly mid-decay, and twenty shots meant twenty independent
   * truncated tails stacked on top of each other. Here the tail lives once, in
   * the live graph: recipes render dry and short, and every gun voice feeds this
   * convolver. The tail is never truncated, N shots sum into one coherent
   * reverb the way they do in a real street, and the per-voice buffer cost
   * drops by better than half.
   */
  _buildSends() {
    const ctx = this.ctx;
    const ir = this._lib.ir;
    this.sends = {};
    const mk = (buffer, opts) => {
      const input = ctx.createGain();
      input.gain.value = 1;
      const conv = ctx.createConvolver();
      conv.normalize = true;
      conv.buffer = buffer;
      const hp = ctx.createBiquadFilter();
      hp.type = 'highpass'; hp.frequency.value = opts.hp || 140; hp.Q.value = 0.6;
      const lp = ctx.createBiquadFilter();
      lp.type = 'lowpass'; lp.frequency.value = opts.lp || 7000; lp.Q.value = 0.5;
      const out = ctx.createGain();
      out.gain.value = opts.gain != null ? opts.gain : 1;
      input.connect(conv); conv.connect(hp); hp.connect(lp); lp.connect(out);
      out.connect(opts.dest || this.duckGain);
      return { input, output: out, conv };
    };
    try {
      // the outdoor street slapback every firearm shares
      this.sends.gun = mk(ir.street, { hp: 150, lp: 7200, gain: 1.0 });
      // the big reflective one, for energy weapons and the box
      this.sends.hall = mk(ir.hall, { hp: 200, lp: 9000, gain: 1.0 });
      // distant canyon for explosions
      this.sends.boom = mk(ir.cavern, { hp: 60, lp: 4200, gain: 1.0 });
    } catch (e) {
      console.warn('[audio] effect sends unavailable:', e);
      this.sends = {};
    }
  }

  async _renderAll(names, registry, target, label) {
    let done = 0;
    const jobs = [];
    for (const name of names) {
      const rec = registry[name];
      if (!rec || typeof rec.build !== 'function') continue;
      const variants = Math.max(1, rec.variants || 1);
      for (let v = 0; v < variants; v++) jobs.push({ name, rec, v });
    }
    const total = jobs.length;
    for (let i = 0; i < jobs.length; i += RENDER_CONCURRENCY) {
      const slice = jobs.slice(i, i + RENDER_CONCURRENCY);
      const rendered = await Promise.all(slice.map((j) => this._render(j.name, j.rec, j.v)));
      for (let k = 0; k < slice.length; k++) {
        const j = slice[k];
        const buf = rendered[k];
        if (!buf) continue;
        if (target === this.trackBuffers) target.set(j.name, buf);
        else {
          let arr = target.get(j.name);
          if (!arr) { arr = []; target.set(j.name, arr); }
          arr[j.v] = buf;
        }
      }
      done += slice.length;
      if (this.onProgress) {
        try { this.onProgress(done / total, label); } catch (e) { /* noop */ }
      }
    }
  }

  async _render(name, rec, variant) {
    const dur = Math.max(0.02, rec.dur || 1);
    const xfade = rec.xfade || 0;
    // Long, low-bandwidth beds (wind, drones, pads) are rendered at a reduced
    // rate: the source node resamples on playback, and it saves both render
    // time and a large slice of buffer memory. Anything with a convolution
    // tail must stay at the context rate — ConvolverNode rejects a
    // sample-rate mismatch on its impulse response.
    const scale = rec.srScale || SR_SCALE[name] || 1;
    const sr = Math.round(this.ctx.sampleRate * scale);
    try {
      const octx = makeOffline(sr, 2, dur + xfade + (rec.pad || 0));
      // Render with a lot of headroom: layered gunshots momentarily sum well
      // past 1.0, and an implementation that clamps its offline destination
      // would hard-clip them. The soft-knee curve is a backstop that should
      // never engage, and normalizeBuffer() puts the level back afterwards.
      const master = octx.createGain();
      master.gain.value = rec.renderGain != null ? rec.renderGain : 0.35;
      // The backstop gets the same domain treatment as the master limiter: a
      // WaveShaper clips its *input* to [-1,1] before the curve lookup, so a
      // curve built over [-1,1] would hard-clip exactly the overshoot it exists
      // to catch. Built over [-3,+3] (with the matching pad) it stays smooth up
      // to +9.5 dB, well past anything a recipe can sum to at renderGain 0.35.
      const pad = octx.createGain();
      pad.gain.value = 1 / RENDER_SAFETY_DOMAIN;
      const safety = octx.createWaveShaper();
      safety.curve = SAFETY_CURVE || (SAFETY_CURVE = limiterCurve(4096, 0.88, RENDER_SAFETY_DOMAIN));
      master.connect(pad);
      pad.connect(safety);
      safety.connect(octx.destination);
      const rng = mulberry32((hashName(name) ^ (variant * 0x9e3779b1)) >>> 0);
      rec.build(octx, master, rng, variant, this._lib);
      let buf = await octx.startRendering();
      if (xfade > 0) buf = foldSeamless(this.ctx, buf, dur, xfade);

      // Trim *before* measuring, not after: a 0.12 s click rendered into a
      // 0.3 s buffer would otherwise have two thirds of its "loudness" measured
      // over silence and come out far too loud.
      if (!rec.loop) {
        buf = trimTail(this.ctx, buf, { db: rec.trimDb != null ? rec.trimDb : -60, pad: 0.02, min: 0.04 });
      }

      const level = rec.level != null ? rec.level : defaultLevel(name);
      if (rec.norm != null || level == null) {
        normalizeBuffer(buf, rec.norm != null ? rec.norm : 0.95);
      } else {
        // The ear judges the loudest short window, not the peak. Short sounds
        // get a proportionally short window so a 50 ms tick is measured over
        // the tick rather than over the tick plus its own tail.
        const win = Math.min(rec.levelWindow ?? 0.3, Math.max(0.01, buf.duration * 0.6));
        // One-shots are allowed to peak past full scale. A gunshot's crest
        // factor is enormous — a 3 ms crack over a 120 ms body — so holding its
        // peak at 0.99 would drag its *loudness* far below a boomier sound with
        // the same peak, which is the failure this whole scheme exists to avoid.
        // AudioBuffer data is float and so is the graph, so the overshoot
        // survives to the master, where MASTER_HEADROOM (-2.5 dB) and the sfx
        // bus (-0.9 dB) between them bring the loudest single voice back under
        // unity *before* the limiter — so one shotgun blast keeps its transient
        // intact and the limiter only ever works on pile-ups. 1.25 is the most
        // headroom that survives that budget at master volume 1.0.
        // Loops are sustained and have no business going past full scale.
        const ceil = rec.peakCeil != null ? rec.peakCeil : (rec.loop ? 0.95 : 1.25);
        rmsNormalize(buf, level, { window: win, peak: ceil, maxGain: 16 });
      }

      if (!rec.loop) {
        // 1.2 ms of linear ramp is ~58 samples straight through the sharpest
        // edge in a gunshot — it audibly rounds the crack off. 0.2 ms is enough
        // to stop a DC step without touching the transient.
        deClick(buf, rec.fadeIn != null ? rec.fadeIn : 0.0002, rec.fadeOut != null ? rec.fadeOut : 0.008);
      }
      buf = maybeMono(this.ctx, buf);
      return buf;
    } catch (err) {
      console.warn('[audio] failed to render "' + name + '" variant ' + variant + ':', err);
      return null;
    }
  }

  /* ---------------- internals ---------------- */

  _bus(rec) {
    const b = (rec && rec.bus) || 'sfx';
    return this.buses[b] || this.buses.sfx;
  }

  _pickBuffer(name, rec) {
    const arr = this.buffers.get(name);
    if (!arr || !arr.length) return null;
    if (arr.length === 1) return arr[0];
    // never replay the same variant twice in a row — kills the machine-gun effect
    const last = this.lastVariant.get(name);
    let i = (Math.random() * arr.length) | 0;
    if (i === last) i = (i + 1 + ((Math.random() * (arr.length - 1)) | 0)) % arr.length;
    this.lastVariant.set(name, i);
    return arr[i] || arr[0];
  }

  _airCutoff(x, y, z) {
    const l = this._listenerState;
    const dx = x - (l.x || 0), dy = y - (l.y || 0), dz = z - (l.z || 0);
    const d = Math.sqrt(dx * dx + dy * dy + dz * dz) || 0;
    // high frequencies lose energy over distance; halve the cutoff every 22 m
    return clamp(19000 * Math.pow(0.5, d / 22), 700, 20000);
  }

  _makePanner(x, y, z) {
    const ctx = this.ctx;
    const p = ctx.createPanner();
    try { p.panningModel = 'HRTF'; } catch (e) { p.panningModel = 'equalpower'; }
    p.distanceModel = 'inverse';
    p.refDistance = 2;
    p.rolloffFactor = 1.2;
    p.maxDistance = 60;
    p.coneInnerAngle = 360;
    p.coneOuterAngle = 360;
    p.coneOuterGain = 1;
    if (p.positionX) {
      p.positionX.value = x; p.positionY.value = y; p.positionZ.value = z;
    } else if (p.setPosition) {
      p.setPosition(x, y, z);
    }
    return p;
  }

  _capFor(name) {
    return SAME_NAME_CAP[name] != null ? SAME_NAME_CAP[name] : SAME_NAME_CAP.default;
  }

  _enforceLimits(name) {
    const count = this.nameCounts.get(name) || 0;
    if (count >= this._capFor(name)) {
      let oldest = null;
      for (const v of this.voices) {
        if (v.name === name && !v.isLoop && (!oldest || v.startedAt < oldest.startedAt)) oldest = v;
      }
      if (oldest) oldest.stop(0.02);
    }
    if (this.voices.size >= MAX_VOICES) {
      let oldest = null;
      for (const v of this.voices) {
        if (!v.isLoop && (!oldest || v.startedAt < oldest.startedAt)) oldest = v;
      }
      if (oldest) oldest.stop(0.02);
    }
  }

  _retire(h) {
    if (this.voices.delete(h)) {
      const c = (this.nameCounts.get(h.name) || 1) - 1;
      if (c <= 0) this.nameCounts.delete(h.name);
      else this.nameCounts.set(h.name, c);
    }
  }

  _spawn(name, rec, buffer, opts, position, isLoop) {
    const ctx = this.ctx;
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.loop = !!isLoop;
    if (isLoop) { src.loopStart = 0; src.loopEnd = buffer.duration; }

    const rateJit = rec.rateJit || 0;
    const rate = (opts.rate != null ? opts.rate : 1) * (rateJit ? 1 + (Math.random() * 2 - 1) * rateJit : 1);
    src.playbackRate.value = Math.max(0.05, rate);

    const jitter = rec.jitter || 0;
    const detune = (opts.detune != null ? opts.detune : 0) + (jitter ? (Math.random() * 2 - 1) * jitter : 0);
    if (src.detune && detune) src.detune.value = detune;

    const gain = ctx.createGain();
    const recGain = rec.gain != null ? rec.gain : 1;
    const vol = (opts.volume != null ? opts.volume : 1) * recGain;
    gain.gain.value = vol;

    let node = gain;
    src.connect(gain);

    let pannerNode = null;
    let airFilter = null;
    if (position) {
      const x = position.x != null ? position.x : (position[0] || 0);
      const y = position.y != null ? position.y : (position[1] || 0);
      const z = position.z != null ? position.z : (position[2] || 0);
      airFilter = ctx.createBiquadFilter();
      airFilter.type = 'lowpass';
      airFilter.Q.value = 0.4;
      airFilter.frequency.value = this._airCutoff(x, y, z);
      pannerNode = this._makePanner(x, y, z);
      node.connect(airFilter);
      airFilter.connect(pannerNode);
      node = pannerNode;
    }
    node.connect(this._bus(rec));

    // Shared live tail (see _buildSends) — the reverb every gunshot pours into.
    // The send is tapped *after* the volume gain and the panner, so it already
    // carries this voice's level and its place in the world; only the wet
    // proportion is set here.
    if (rec.send && this.sends && this.sends[rec.send]) {
      const s = ctx.createGain();
      s.gain.value = (rec.sendAmt != null ? rec.sendAmt : 0.3)
        * (opts.sendAmt != null ? opts.sendAmt : 1);
      node.connect(s);
      s.connect(this.sends[rec.send].input);
    }

    const h = new Handle(this, name, src, gain, pannerNode, airFilter, isLoop);
    h.baseVolume = recGain;

    const fadeIn = opts.fadeIn || (isLoop ? 0.08 : 0);
    if (fadeIn > 0) {
      const now = ctx.currentTime;
      gain.gain.setValueAtTime(1e-4, now);
      gain.gain.exponentialRampToValueAtTime(Math.max(1e-4, vol), now + fadeIn);
    }

    const when = ctx.currentTime + (opts.delay || 0);
    try { src.start(when, opts.offset || 0); } catch (e) { return NULL_HANDLE; }

    this.voices.add(h);
    this.nameCounts.set(name, (this.nameCounts.get(name) || 0) + 1);
    if (!isLoop) {
      src.onended = () => { h.isPlaying = false; this._retire(h); };
    }

    const ad = AUTO_DUCK[name];
    if (ad && !opts.noDuck) this.duck(ad[0], ad[1]);

    return h;
  }

  /* ---------------- public API ---------------- */

  /** Canonical name for a possibly-aliased one. */
  _canon(name) { return ALIASES[name] || name; }

  /**
   * A one-shot asked for before the deferred pass rendered it: render it now
   * and play it if it lands soon enough to still belong to the event that asked
   * (a door thunk 200 ms late is a door thunk; 2 s late is a ghost). Silence is
   * the fallback, never a wrong-time sound.
   */
  _playSoon(n, rec, opts, pos) {
    const t0 = this.ctx ? this.ctx.currentTime : 0;
    this._ensure(n).then(() => {
      if (!this.ctx || this.ctx.currentTime - t0 > LATE_PLAY_GRACE) return;
      const buf = this._pickBuffer(n, rec);
      if (!buf) return;
      this._enforceLimits(n);
      this._spawn(n, rec, buf, opts || {}, pos, false);
    });
    return NULL_HANDLE;
  }

  /** 2D playback (UI, the player's own weapon, global stingers). */
  play(name, opts) {
    if (!this.ready || !name) return NULL_HANDLE;
    const n = this._canon(name);
    const rec = SOUNDS[n];
    if (!rec) return NULL_HANDLE;
    const buf = this._pickBuffer(n, rec);
    if (!buf) return this._playSoon(n, rec, opts, null);
    this._enforceLimits(n);
    return this._spawn(n, rec, buf, opts || {}, null, false);
  }

  /** 3D positional playback. `pos` is any {x,y,z} (THREE.Vector3 works). */
  playAt(name, pos, opts) {
    if (!this.ready || !name) return NULL_HANDLE;
    const n = this._canon(name);
    const rec = SOUNDS[n];
    if (!rec) return NULL_HANDLE;
    const buf = this._pickBuffer(n, rec);
    if (!buf) {
      // copy the position: the caller's vector will have moved on by the time
      // the render finishes
      const p = pos || { x: 0, y: 0, z: 0 };
      return this._playSoon(n, rec, opts, { x: p.x || 0, y: p.y || 0, z: p.z || 0 });
    }
    this._enforceLimits(n);
    return this._spawn(n, rec, buf, opts || {}, pos || { x: 0, y: 0, z: 0 }, false);
  }

  /**
   * Start a looping sound. Pass `position` for a positional loop (fires,
   * power-ups); omit it for a 2D loop (heartbeat, ambience).
   * Returns a handle with setPosition / setVolume / stop(fadeSec).
   *
   * Music beds are loopable too, so a caller that wants to *stack* beds (the
   * in-round tension layers) can reach them here instead of through music().
   */
  loop(name, opts) {
    if (!this.ready || !name) return NULL_HANDLE;
    const n = this._canon(name);
    const o = opts || {};
    const rec = SOUNDS[n] || TRACKS[n];
    if (!rec) return NULL_HANDLE;
    const buf = SOUNDS[n] ? this._pickBuffer(n, rec) : this.trackBuffers.get(n);
    if (!buf) { this._ensure(n); return NULL_HANDLE; }
    return this._spawn(n, rec, buf, o, o.position || null, true);
  }

  /** Cross-fade to a music bed. Unknown names stop the music. */
  music(name, opts) {
    if (!this.ready) {
      // called before init finished — replay the request once the graph exists
      if (this.initPromise) this.initPromise.then(() => this.music(name, opts));
      return NULL_HANDLE;
    }
    const o = opts || {};
    const fade = o.fade != null ? o.fade : 1.4;
    name = name ? this._canon(name) : name;
    if (this.musicName === name && this.musicHandle && this.musicHandle.isPlaying) return this.musicHandle;
    this.stopMusic(fade);
    // a looping bed declared in the SFX registry is a perfectly good music bed
    const rec = TRACKS[name] || (SOUNDS[name] && SOUNDS[name].loop ? SOUNDS[name] : null);
    if (!rec) { this.musicName = null; return NULL_HANDLE; }
    this.musicName = name;
    const token = ++this.musicToken;

    const start = () => {
      if (token !== this.musicToken) return NULL_HANDLE;
      const buf = this.trackBuffers.get(name) || this._pickBuffer(name, rec);
      if (!buf) return NULL_HANDLE;
      const h = this._spawn(name, rec, buf, {
        volume: o.volume != null ? o.volume : 1,
        fadeIn: o.fadeIn != null ? o.fadeIn : 1.6,
        noDuck: true,
      }, null, true);
      this.musicHandle = h;
      return h;
    };

    if (this.trackBuffers.has(name) || this.buffers.has(name)) return start();
    // still rendering — start as soon as it is ready
    const p = this.deferredPromise || Promise.resolve();
    p.then(start);
    return NULL_HANDLE;
  }

  stopMusic(fadeSec = 1.4) {
    this.musicToken++;
    this.musicName = null;
    if (this.musicHandle) {
      this.musicHandle.stop(fadeSec);
      this.musicHandle = null;
    }
  }

  setMasterVolume(v) {
    this.masterVolume = clamp(v, 0, 2);
    if (this.master) {
      const now = this.ctx.currentTime;
      this.master.gain.cancelScheduledValues(now);
      this.master.gain.setTargetAtTime(this.muted ? 0 : this.masterVolume, now, 0.02);
    }
    return this;
  }

  getMasterVolume() { return this.masterVolume; }

  /** Per-bus trim: 'sfx' | 'ui' | 'music' | 'ambient'. */
  setBusVolume(bus, v) {
    if (!(bus in this.busVolumes)) return this;
    this.busVolumes[bus] = clamp(v, 0, 2);
    if (!this.buses || !this.buses[bus]) return this;   // applied when the graph is built
    const now = this.ctx.currentTime;
    this.buses[bus].gain.cancelScheduledValues(now);
    this.buses[bus].gain.setTargetAtTime(this.busVolumes[bus], now, 0.03);
    return this;
  }

  /** Current trim for one bus (so an options slider can initialise itself). */
  getBusVolume(bus) { return this.busVolumes[bus] != null ? this.busVolumes[bus] : 1; }
  /** The bus names an options menu should offer sliders for. */
  listBuses() { return Object.keys(this.busVolumes); }

  setMuted(m) {
    this.muted = !!m;
    if (this.master) {
      const now = this.ctx.currentTime;
      this.master.gain.cancelScheduledValues(now);
      this.master.gain.setTargetAtTime(this.muted ? 0 : this.masterVolume, now, 0.03);
    }
    return this;
  }

  /**
   * Duck the world (sfx + ambient) under a stinger or announcement.
   * `amount` is how much to attenuate, 0..1 (0.6 = drop to 40 %).
   * `seconds` is how long to hold before recovering.
   */
  duck(amount = 0.6, seconds = 1.5) {
    if (!this.ctx || !this.duckGain) return this;
    const now0 = this.ctx.currentTime;
    /*
     * Ducks combine, they do not replace. Several call sites fire a stinger
     * (which carries an AUTO_DUCK) and then immediately call duck() by hand;
     * the second call used to cancel the first, so the effective duck was
     * whichever happened to be last and its length was anyone's guess. Taking
     * the deeper amount and the later release makes the order irrelevant.
     */
    let a = clamp(amount, 0, 1);
    let hold = Math.max(0.05, seconds);
    if (this._duckUntil != null && this._duckUntil > now0) {
      a = Math.max(a, this._duckAmount || 0);
      hold = Math.max(hold, this._duckUntil - now0);
    }
    this._duckAmount = a;
    this._duckUntil = now0 + hold;

    const target = Math.max(0.0015, 1 - a);
    const now = now0;
    const g = this.duckGain.gain;
    try {
      g.cancelScheduledValues(now);
      g.setValueAtTime(Math.max(1e-4, g.value), now);
      g.exponentialRampToValueAtTime(target, now + 0.09);
      g.setValueAtTime(target, now + hold);
      g.exponentialRampToValueAtTime(1, now + hold + 0.75);
      g.setValueAtTime(1, now + hold + 0.78);
    } catch (e) { g.value = 1; }
    return this;
  }

  /**
   * Update the 3D listener from a THREE.Camera (or anything with a
   * `matrixWorld` whose `.elements` is a column-major mat4). Cheap enough to
   * call every frame.
   */
  setListener(camera) {
    if (!this.ctx || !camera) return this;
    const l = this.ctx.listener;
    if (!l) return this;
    let px = 0, py = 0, pz = 0, fx = 0, fy = 0, fz = -1, ux = 0, uy = 1, uz = 0;
    const mw = camera.matrixWorld;
    if (mw && mw.elements) {
      const e = mw.elements;
      px = e[12]; py = e[13]; pz = e[14];
      // three.js cameras look down their local -Z
      fx = -e[8]; fy = -e[9]; fz = -e[10];
      ux = e[4]; uy = e[5]; uz = e[6];
      const fl = Math.hypot(fx, fy, fz) || 1;
      fx /= fl; fy /= fl; fz /= fl;
      const ul = Math.hypot(ux, uy, uz) || 1;
      ux /= ul; uy /= ul; uz /= ul;
    } else if (camera.position) {
      px = camera.position.x; py = camera.position.y; pz = camera.position.z;
    } else {
      return this;
    }
    this._listenerState.x = px;
    this._listenerState.y = py;
    this._listenerState.z = pz;
    if (l.positionX) {
      l.positionX.value = px; l.positionY.value = py; l.positionZ.value = pz;
      l.forwardX.value = fx; l.forwardY.value = fy; l.forwardZ.value = fz;
      l.upX.value = ux; l.upY.value = uy; l.upZ.value = uz;
    } else {
      if (l.setPosition) l.setPosition(px, py, pz);
      if (l.setOrientation) l.setOrientation(fx, fy, fz, ux, uy, uz);
    }
    return this;
  }

  /**
   * Announcer line: a squelch, a held carrier, the words, a squelch to close.
   *
   * The words are pre-rendered formant speech (`vox_*` in sfx.js), not
   * `speechSynthesis`. Browser TTS gave a different voice on every machine, no
   * voice at all on some, arrived whenever the platform felt like it, and could
   * not be ducked, filtered or mixed because it never enters the graph. A baked
   * phrase is one voice everywhere, sample-accurate against the squelch, and
   * just another buffer as far as the mixer is concerned.
   *
   * Text outside the announcer's vocabulary gets the radio without the words —
   * a burst of chatter of roughly the right length — which is honest, and is
   * what the review asked for in preference to a robot mispronouncing it.
   */
  announce(text, opts) {
    if (!text) return this;
    this._announceQueue.push({ text: String(text), opts: opts || {} });
    if (!this._announcing) this._drainAnnounce();
    return this;
  }

  /** `Max Ammo` / `INSTA-KILL!` -> `vox_insta_kill`, or null. */
  _voxFor(text) {
    const key = String(text).toLowerCase().replace(/[^a-z]/g, '');
    const name = VOX_LOOKUP[key];
    return name && SOUNDS[name] ? name : null;
  }

  _drainAnnounce() {
    const job = this._announceQueue.shift();
    if (!job) { this._announcing = false; return; }
    this._announcing = true;

    const vox = job.opts.wordless ? null : this._voxFor(job.text);
    const rec = vox ? SOUNDS[vox] : null;
    // lead-in before the words so the squelch has opened first
    const lead = 0.22;
    const speech = rec ? (rec.speech || rec.dur) : clamp(0.3 + job.text.length * 0.06, 0.6, 2.4);
    const total = lead + speech + 0.12;

    this.duck(job.opts.duck != null ? job.opts.duck : 0.45, total + 0.25);
    this.play('radio_blip', { volume: 0.7 });
    // carrier hiss for as long as the transmission is open
    const carrier = this.loop('radio_static', { volume: 0.5, fadeIn: 0.04 });

    if (vox) {
      // if the deferred pass has not reached this phrase yet, render it now and
      // speak a beat later rather than dropping the line
      const say = () => this.play(vox, { volume: job.opts.volume != null ? job.opts.volume : 1 });
      if (this._pickBuffer(vox, rec)) setTimeout(say, lead * 1000);
      else this._ensure(vox).then(() => { if (this._pickBuffer(vox, rec)) say(); });
    }

    setTimeout(() => {
      if (carrier && carrier.stop) carrier.stop(0.12);
      this.play('radio_blip', { volume: 0.5 });
      setTimeout(() => this._drainAnnounce(), 140);
    }, total * 1000);
  }

  /* ---------------- housekeeping ---------------- */

  /** Stop every one-shot and loop (not the music bed). */
  stopAll(fade = 0.1) {
    for (const v of Array.from(this.voices)) {
      if (v !== this.musicHandle) v.stop(fade);
    }
    return this;
  }

  /** Stop only looping voices (fires, heartbeat, ambience). */
  stopLoops(fade = 0.3) {
    for (const v of Array.from(this.voices)) {
      if (v.isLoop && v !== this.musicHandle) v.stop(fade);
    }
    return this;
  }

  suspend() { if (this.ctx && this.ctx.suspend) { try { this.ctx.suspend(); } catch (e) { /* noop */ } } return this; }
  resume() { if (this.ctx && this.ctx.resume) { try { this.ctx.resume(); } catch (e) { /* noop */ } } return this; }

  /**
   * True if the engine knows this sound name. Call sites use this to try a
   * specific name first and fall back to a generic one:
   *   `audio.has('gun_ak74u') ? 'gun_ak74u' : 'gun_smg'`
   */
  has(name) {
    if (!name) return false;
    const n = this._canon(name);
    return !!(SOUNDS[n] || TRACKS[n]);
  }

  /** Every playable one-shot/loop name (for tooling). */
  listSounds() { return Object.keys(SOUNDS).concat(Object.keys(ALIASES)).sort(); }
  /** Every music-bed name. */
  listTracks() { return Object.keys(TRACKS).sort(); }
  /** Names that are just another spelling of a rendered recipe. */
  listAliases() { return Object.assign({}, ALIASES); }
  /** Recipe metadata, for the audition page. */
  info(name) {
    const n = this._canon(name);
    const rec = SOUNDS[n] || TRACKS[n];
    if (!rec) return null;
    const arr = this.buffers.get(n);
    return {
      name,
      canonical: n,
      alias: n !== name ? n : null,
      dur: rec.dur,
      variants: (arr && arr.length) || rec.variants || 1,
      bus: rec.bus || 'sfx',
      loop: !!rec.loop,
      deferred: !!rec.defer,
      level: rec.level != null ? rec.level : defaultLevel(n),
      gain: rec.gain != null ? rec.gain : 1,
      rendered: this.buffers.has(n) || this.trackBuffers.has(n),
      // where this name's audio actually comes from, for the audition page
      fromFile: !!rec.fromFile,
      src: rec.src || (rec.fromFile ? '' : 'synthesised'),
    };
  }
}

export const audio = new AudioEngine();
export default audio;
