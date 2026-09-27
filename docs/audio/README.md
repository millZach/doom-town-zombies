# Audio pipeline

The game used to synthesise every sound at runtime. It now plays **recorded and
generated files** from `public/audio/**`, and keeps the synthesised recipes as a
fallback for any name a file does not cover.

```
tools/audio/_raw/**            ElevenLabs renders (committed; regenerating costs credits)
<scratch>/ffsl, vcsl, ex, oga  CC0 packs, downloaded (not committed)
        │
        ├─ tools/audio/fetch_oga.py     download CC0 packs from OpenGameArt
        ├─ tools/audio/generate.mjs     ElevenLabs sound generation + TTS
        ├─ tools/audio/lib.py           ffmpeg/numpy DSP: slicing, filters, reverb, LUFS
        └─ tools/audio/build.py         → public/audio/**.ogg + manifest.json
                                        → tools/audio/verify.py → docs/audio/report.md
```

## Rebuilding

```sh
python tools/audio/build.py all        # or: guns handling impacts foley voices world stingers music
python tools/audio/verify.py           # measurements + spectrograms
```

Both are restartable. `build.py` writes each .ogg as it finishes and merges into the
existing `manifest.json`, so a single group can be rebuilt on its own and an
interrupted run loses at most one sound. `verify.py` caches its measurements in
`tools/audio/_measurements.json` keyed by file size and mtime. That matters on a
shared machine: this box runs several build agents at once and numpy/OpenBLAS will
fail an allocation when the Windows commit limit is exhausted. If that happens, set
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` and run the groups one at a time.

`build.py` reads its CC0 sources from the scratch download directory; set `AUDIO_DL`
to point at it. `generate.mjs` reads `ELEVENLABS_API_KEY` from `.env.local` and skips
anything already present in `tools/audio/_raw`, so re-running it is free.

## The manifest

`public/audio/manifest.json`:

```json
{
  "sounds": {
    "zombie_groan": {
      "files": ["voices/zombie_groan_1.ogg", "…"],
      "gain": 1.0, "jitter": 130, "rateJit": 0.07,
      "src": "ElevenLabs zombie groan / crawler / pain takes"
    },
    "gun_m1911": { "files": [...], "send": "gun", "sendAmt": 0.3, ... },
    "ambient_loop": { "files": [...], "loop": true, "bus": "ambient" }
  },
  "tracks": { "menu": "menu", "game_over": "music_game_over" }
}
```

- `files` — the variants. The engine picks one at random per trigger and never
  repeats the previous one.
- `gain`, `bus`, `loop`, `send`, `sendAmt`, `jitter` (cents of detune), `rateJit`
  (fractional playback-rate wobble) pass straight into the playback record.
- `tracks` maps a name reachable from `audio.music()` onto the sound that holds it —
  `game_over` is both a one-shot sting and a looping bed, so the bed lives under its
  own key.

A name that is absent from the manifest, or whose files fail to load, falls back to
its synthesised recipe in `src/audio/sfx.js` / `music.js`. A missing manifest is not
an error: the game then sounds exactly as it did before.

## Mixing

Files are loudness-normalised per category (gated BS.1770, implemented in `lib.lufs`),
not peak-normalised, so the hierarchy survives: guns ≈ −14 LUFS, creature voices ≈ −19,
stingers ≈ −21, footsteps ≈ −27. Three guards run over every file:

- **Harshness** — anything whose energy above 5 kHz exceeds its category cap gets an
  automatic high shelf, repeated until it is under. That guard is what stops a
  "screech"; the stingers come out at 0.00 % above 5 kHz.
- **Peak** — a smooth soft-knee limiter and a per-category sample-peak ceiling. The
  ceilings look low (0.48 for guns) because ffmpeg's true-peak meter reads a broadband
  transient ~3 dB above the sample peak; the shipped files measure 0 over −1 dBTP.
  Guns also get a 14 kHz roll-off, which is what actually killed the inter-sample
  overshoot without costing any loudness — the source recordings are clipped flat at
  the crack, and the near-Nyquist energy that leaves behind is the cause.
- **Small speakers** — `voice_for_small_speakers` shelves the bottom of the stingers
  and music beds until under 45 % of their energy sits below 200 Hz. An organ pedal
  note plus a cinematic sub swell is 90 % sub, which is enormous on monitors and
  *inaudible* on a laptop.

See `report.md` for the per-file table and `renders/audio/` for spectrograms.

## The stingers

`round_end`, `round_start`, `hellround_start` and `game_over` are layered, not single
takes:

1. a reversed gong swell to open,
2. a sustained VCSL pipe-organ pedal chord (the sampled notes A/C/D♯/F♯ make a
   diminished set — exactly the right amount of wrong),
3. a tubular-bell toll,
4. a timpani or bass-drum thump on the downbeat,
5. for the hell round, a hellhound growl buried an octave down,
6. the ElevenLabs cinematic sting itself, low-passed first,
7. one shared reverb, a final de-harsh pass and a long tail.

Original material — no part of any commercial game's music is used or imitated.

Several ElevenLabs candidates were generated per sting (three for `round_end`, two each
for `round_start`, `hellround_start` and `game_over`) and chosen on measurement rather
than by ear: spectral centroid, the share of energy per octave band, and where in the
clip the envelope peaks (a sting should *build*, not land at once). `game_over_b` beat
`game_over_a` on all three — centroid 697 Hz vs 289, peak at 32 % of the clip vs 11 %,
and more than three times the energy in the 200–1200 Hz band a laptop can reproduce.
The unused candidates are still in `tools/audio/_raw/stinger/` if a different take is
wanted; their spectrograms are in `renders/audio/raw/`.

## Credits

`CREDITS.md` at the project root lists every pack, author and licence. The ElevenLabs
material is free-plan output: non-commercial, with attribution.
