# Fix log — stream `audio`

Files touched (all owned by this stream):
`src/audio/audio.js`, `src/audio/sfx.js`, `src/audio/dsp.js`, `src/audio/music.js`,
`tools/audio-test.html`.

Verified with `node --check` on all four modules, a construction-stub smoke test that
runs **every recipe's `build()`** (316 renders across all variants, 0 failures, 0 graph
warnings), a stub-driven engine test that calls `init()` and then `play()` on every
registered name (147/147 return a live handle), and `npx vite build --logLevel error`
(passes).

---

## Repair round (second pass)

**The blocking defect: the master limiter could not read anything above unity.**
A `WaveShaper`'s input is clipped to `[-1, +1]` *before* the curve lookup, so a curve
built over `[-1, +1]` maps every sample above full scale to its single endpoint — a flat
top, not a soft knee. The limiter is precisely the node that gets fed past unity (one-shots
are deliberately allowed to peak to 1.25–1.4), so the loudest single shotgun blast or
explosion was being hard-clipped on its own, with nothing else playing. Three changes,
in `audio.js`:

- `limiterCurve(n, thresh, domain)` now builds the curve over `[-domain, +domain]`, and a
  new `limiterPad` gain of `1/domain` sits in front of the shaper. With
  `LIMITER_DOMAIN = 2.5` the limiter reads up to +8 dBFS correctly. Measured through the
  real curve: `0.50 → 0.500`, `0.84 → 0.831`, `1.00 → 0.929`, `1.26 → 0.986`, `2.00 →
  0.997` — a knee, where before everything ≥ 1.0 landed on 0.928 flat.
- `MASTER_HEADROOM = 0.75` on `postComp` (below the master fader, so `setMasterVolume`
  still means what it says). Budget: a 1.25-peak one-shot × sfx bus 0.9 × 0.75 = 0.84 at
  the limiter, i.e. 0.1 dB of gain reduction — a single voice keeps its transient intact
  and the limiter only ever works on pile-ups.
- default one-shot `peakCeil` 1.4 → **1.25**, `limiter.oversample` `2x` → **4x**, and the
  incorrect comment ("the master chain ends in a soft limiter, so the overshoot is caught
  where it should be") replaced with what actually happens.
- The same bug existed on the offline render backstop (`_render()`'s `safety` shaper):
  it now uses `RENDER_SAFETY_DOMAIN = 3` with a matching pad, so the backstop is smooth to
  +9.5 dB instead of clipping the overshoot it exists to catch.

**Also repaired in this round**

- **The announcer is no longer browser TTS** — see #12 below. This was the one item the
  first pass left undone.
- **`MUSIC.menu` given `level: -20`.** It was the last recipe in the library still falling
  back to peak normalisation (the first pass claimed nothing did; that was wrong).
- **`gun_pap_layer_heavy` marked `defer: true`.** It has no call site yet (the selection
  belongs to `weapons.js`, "Needs from other streams" item 2), so it must not cost init
  time while it waits.
- **A deferred sound asked for early is no longer silently dropped.** `play()`/`playAt()`
  route a missing buffer through the new `_playSoon()`, which renders it on demand and
  plays it if it lands within `LATE_PLAY_GRACE` (0.35 s) — so the first `door_open` or
  `perk_jingle` of a match is heard rather than swallowed. Later than that it is still
  dropped, because a door thunk two seconds late is worse than no door thunk.

**Corrections to the first pass's own wording** (the work was right, the log was not):
6.3's saturator reorder landed *in* that pass, not before it; "every recipe's `gain`
normalised to 1.0" is true of all but nine deliberate exceptions (the four perk jingles at
0.8 and the five power-up stingers at 0.85, which are trimmed against their own stinger
group); and "nothing falls back to peak normalisation" was false for `MUSIC.menu` until
this round. All three are fixed in place below.

---

## weapons_audio.md #6 — gun audio: recipes, tails, saturator, voice cap, mix hierarchy, master bus — **fixed**

**6.1 Six recipes for ten guns → ten per-weapon recipes.**
`sfx.js` `GUN_SPECS` / `gunShot()` / `buildGun()`. New ids, all rendered with distinct
calibre, barrel length and action:

| id | what makes it itself |
|---|---|
| `gun_m1911` | subsonic .45 — almost no crack, fat low body, two-stage steel slide cycle at 26/72 ms |
| `gun_python` | .357 Magnum: hardest crack of the pistols, `mech: false`, plus a **cylinder-gap jet** panned to one side and a frame ring |
| `gun_m14` | 7.62×51, `crack 3400`, op-rod mech at 1400/2400/3800, **walnut stock resonance** (`woodModes` at 300 Hz), supersonic zing |
| `gun_galil` | 5.56 in steel: brighter/shorter crack, metallic mech at 2200/3600/5200/7000 |
| `gun_ak74u` | short-barrel 5.45: blast over crack, `body 640` + second layer, **low 1100 Hz bolt carrier** at `mechAmp 0.5` |
| `gun_mp5` | 9mm roller-delayed: quietest body, fastest and brightest chatter (2600–7400) at 11/30 ms |
| `gun_rpd` | belt-fed 7.62×39, heavy carrier, three link clacks torn off the belt |
| `gun_remington870` | 12 ga pump: broad boom, second low layer, wad poof, small action tick |
| `gun_olympia` | 12 ga break-open: biggest body, **no action at all**, longer poof, two barrels ringing |
| `gun_raygun` | unchanged character, retuned level and tail routing |

The six old type names (`gun_pistol`, `gun_revolver`, `gun_rifle`, `gun_smg`,
`gun_shotgun`, `gun_lmg`) still work — they are now **aliases** (`SFX_ALIASES` in
`sfx.js`, resolved by `audio._canon()`), so nothing is rendered twice and no call site
breaks. PaP: `gun_pap_layer` (light, −21 dB) and `gun_pap_layer_heavy` (−18 dB, with a
sub) replace the one flat layer.

**6.2 Truncated tails → one live shared tail.** `audio.js` `_buildSends()` builds three
persistent convolver sends in the runtime graph (`gun` = street IR, `hall`, `boom` =
cavern), each into `duckGain`. Recipes declare `send` / `sendAmt`; `_spawn()` taps the
voice *after* its volume gain and panner, so the tail keeps the shot's level and
position. Gun buffers are now **dry and short** (0.30–0.56 s instead of 0.72/0.95), so
the tail is never truncated, N shots sum into one coherent street instead of stacking N
truncated copies, and a 16-voice burst costs about a third of what it used to.
`raygun_impact`, `explosion` and `nuke_blast` also route to a live send and their baked
tails were cut back (they were being truncated against a 3.6 s IR too).

**6.3 Saturator before the envelope.** Corrected in `dsp.js` `noiseBurst()`: the shaper
now sits **after** the envelope in a parallel dry/wet blend (new `driveMix`), so only the
loud part of the envelope reaches the knee and the tail decays clean instead of staying
as fizzy as the transient. The gun recipes use it: `driveMix 0.6` on the crack,
`0.55` on the body, and the body's drive multiplier dropped from `×1.4` to `×1.2`.

**6.4 Voice cap that gated automatic fire.** `audio.js` `SAME_NAME_CAP` — `gun_mp5`,
`gun_ak74u`, `gun_rpd` 16; `gun_galil` 14; `gun_m14`, `gun_rifle` 12; pistols 8–10;
shotguns 6; impacts 8–10; `hitmarker` 4 → 8. `MAX_VOICES` 56 → 80. Verified: 18 rapid
`gun_mp5` triggers now hold 16 live voices instead of being cut to 6.

**6.5 Everything peak-normalised to 0.95 → a real loudness hierarchy.**
`audio.js` `LEVEL_DEFAULTS` + `defaultLevel()`, applied in `_render()` through
`dsp.rmsNormalize`. Every recipe's `gain` field was normalised to `1.0` (43 of them) apart
from nine deliberate exceptions — the four perk jingles at 0.8 and the five power-up
stingers at 0.85, trimmed against the rest of their own group — so the hierarchy lives in
essentially one place. The resulting ladder, quietest to loudest:
`radio_static −30 · ui_hover −28 · zombie_footstep −27 · footsteps −24 · reload parts
−23…−19 · impacts −18 · zombie voices −17 · stingers −16 · SMG/pistol −13.5 · announcer
−13 · rifles −12.5 · shotguns/explosion −11 · nuke −9`. Since the repair round, **nothing**
falls back to peak normalisation (`MUSIC.menu` was the last holdout).
Two supporting fixes that make this actually work:
- `_render()` now **trims before measuring**. Measuring a 0.12 s click inside a 0.3 s
  buffer put two thirds of its "loudness" over silence.
- the measurement window is proportional (`min(0.3 s, duration × 0.6)`), and one-shots
  are allowed to peak past full scale — **1.25** (loops 0.95). A gunshot's crest factor is
  enormous; a 0.99 ceiling would drag its loudness below a boomier sound at the same peak,
  which is the exact failure the scheme exists to prevent. The overshoot is paid for with
  real headroom further down the chain (`MASTER_HEADROOM`), not hand-waved at the limiter
  — see the repair round above.

**6.6 Master compression.** `audio.js` `_buildGraph()`: threshold −14 → −6, ratio 6 → 3,
attack 4 ms → 20 ms (a 4 ms attack is slower than a gunshot's crack, so it passed the
transient and then clamped the body), knee 8 → 10, release 0.18 → 0.25. The graph was
re-wired so **music bypasses the compressor entirely**:
`sfx+ambient → duck → preMaster → compressor → postComp`, `ui → preMaster`,
`music → postComp`, then `postComp (×0.75 headroom) → master → limiterPad → limiter →
destination`. Gunfire can no longer pump the score, and `setMasterVolume` still governs
everything.

**6.7 `deClick` fade-in.** 1.2 ms → 0.2 ms for one-shots (overridable per recipe via
`fadeIn`). 58 samples of ramp straight through the sharpest edge in the sound is gone.

---

## weapons_audio.md #12 — coverage — **fixed (engine side); some wiring belongs to other streams**

Every name in the NEW SOUND-NAME CONTRACT now exists and is rendered. Automatically
checked by the smoke test ("contract names missing: none", "legacy names broken: none").

**Per-weapon gunshots (10)** — see #6.

**Reload parts (22), `sfx.js` "Weapon handling" section.** Built from a new mechanical
vocabulary (`steelHit`, `railSlide`, `rattle`, `springTwang`, `clothBrush`), one part per
physical event, per class — a rifle magazine *rocks* into a trunnion and locks at the
rear, an SMG magazine goes straight up a well, the RPD has a hinged top cover plus a
belt, the Olympia breaks open, the Python's crane swings out:
`reload_pistol_out/in`, `reload_rifle_out/in`, `reload_smg_out/in`,
`reload_lmg_out/in`, `reload_lmg_belt`, `reload_shotgun_shell`,
`reload_break_open/close`, `reload_revolver_open/eject/close`,
`reload_raygun_out/in`, `bolt_pull`, `bolt_release`, `slide_release`,
`pump_back`, `pump_forward`.
The old `reload_mag_out` / `reload_mag_in` / `reload_bolt` / `reload_shell` recipes were
deleted and re-pointed as aliases onto the rifle set / `bolt_release` /
`reload_shotgun_shell`, so existing `weapons.js` calls keep working and sound better
immediately. **Nothing here should ever be rate-shifted** (see #7 below).

**Brass.** `shell_drop` rewritten with real bounce behaviour (geometric interval and
amplitude decay, per-bounce concrete thud, 5 variants); `shell_drop_shotgun` added as a
dull plastic hull with a weak brass rim.

**Zombie physicality.** `zombie_footstep` (6 variants, scuff-then-weight, everything
above ~2 kHz filtered out, `srScale 0.5`), `zombie_bodyfall` (wet low thud + cloth +
delayed limb impact + grit), `zombie_gib` (pressure release, tissue tear sweeping *up*,
bone snap, then four pieces landing over half a second), `hellhound_footstep` (claw
ticks then pad, with an occasional ember trail), `hellhound_death` (yelp collapsing into
a gurgle, then burning out rather than falling over).

**Impacts per surface.** `impact_concrete`, `impact_wood`, `impact_metal`,
`impact_dirt`, `impact_glass`, plus `impact_flesh` (alias of `flesh_hit`). Shared
`impactStrike()` + `ricochet()` helpers; ricochet probability is per surface (metal 0.8,
concrete 0.4, wood/dirt none). `bullet_impact_wall` and `bullet_impact_*` are aliases, so
the existing call site keeps working.

**UI.** `ui_click` rebuilt as a 1950s toggle (hard contact + bakelite body + one tonal
partial) instead of a beep; `ui_hover` made much quieter and drier; `ui_back` added.

**In-round music.** `music.js`: `round_bed_loop` (8 s seamless — sub drone, two-per-bar
low pulse, a tolling bell well back in the room, broken-radio texture, one distant wrong
voice, wind) plus two stackable layers on the same 8 s grid:
`round_bed_layer_pulse` (driving sixteenths + a swell that crests at the loop point) and
`round_bed_layer_choir` (Dm with a tritone, one voice a semitone off). They are reachable
through **either** `audio.music()` or `audio.loop()` — `loop()` now falls back to the
track registry and `music()` to the SFX registry, so layers can be faded in and out
mid-round without a seam.

**Player foley.** `footstep_concrete`, `land_soft`, `land_hard`, `jump_grunt`,
`ads_in`, `ads_out`, `weapon_lower`, `weapon_raise`, `knife_hit_wall`, `hitmarker_head`,
`low_ammo`, `radio_static`.

**Announcer — browser TTS removed entirely** (repair round). `window.speechSynthesis` is
gone from `audio.js`; the words are now pre-rendered formant speech, exactly as the review
asked. `sfx.js` gains a small speech synthesiser:

- `VOX_PHONES` — a phoneme table: four formant targets per vowel/nasal/liquid, a noise
  band per fricative, and a *silent hold* plus burst plus aspiration per stop (the silence
  is what makes a stop read as a consonant rather than a click).
- `voxPhrase()` — one jittered glottal pulse train (`dsp.glottalBuffer`, the zombie voice's
  source, an octave up and far steadier) with an announcer pitch contour: a push up into
  the first stressed syllable, then a steady fall onto the full stop. It is gated by a
  per-phoneme amplitude envelope and passed through four parallel band-passes whose centre
  frequencies **glide** between phoneme targets (the glide is most of what makes formant
  synthesis read as speech). Then a comms chain: pre-emphasis, parallel saturation, 380 Hz
  – 3.3 kHz band, and one short PA slap.
- Six phrases, the announcer's entire vocabulary: `vox_max_ammo`, `vox_insta_kill`,
  `vox_double_points`, `vox_nuke`, `vox_carpenter`, `vox_fire_sale` — all `defer: true`,
  bus `ui` (so the duck they trigger does not attenuate them), level −13.
- `audio.announce(text)` squashes the text to a key, looks it up in `VOX_LOOKUP`, and
  plays blip → carrier → phrase → blip with the timings taken from the recipe's own
  `speech` length. Text *outside* the vocabulary gets the radio without the words, which
  is the review's stated second-best option and is honest; nothing mispronounces anything.

The voiced/unvoiced balance was measured, not guessed: four unity-gain band-passes throw
away most of a pulse train's energy, so as first written the fricatives came out **14 dB
louder than the vowels** (an offline simulation of the chain gave stressed vowel −35.9
dBFS vs `/s/` −22.0). `VOX_VOICE_MAKEUP` (×6) and `VOX_NOISE_TRIM` (×0.42) put it at
vowel −20.4 / `/s/` −29.6, and nasals — whose 270 Hz F1 sits on the strongest harmonics,
so they were coming out *louder* than the vowels they attach to — were damped from 0.55 to
0.25. That is a normal speech balance.

**Init time.** Deliberately controlled. `_init()` now renders in two phases: `defer: true`
recipes (perk jingles, the mystery box, power-ups, Pack-a-Punch, the end-of-round
stingers, `player_down`, `door_open`, `nuke_blast`, the announcer phrases, …) move to a
background pass that runs after `ready`, and anything asked for before it arrives is
rendered on demand by `_ensure()` — and, since the repair round, *played* by `_playSoon()`
if it lands within 0.35 s. Measured: phase 1 is **212.1 rendered-seconds across 91
recipes**, down from 254.0 at the start of this work, while the library grew from 75 to
131 recipes; the other 104.6 seconds (35 recipes) and the 37.4 seconds of music beds are
rendered in the background.

---

## Lesser issues

**#21 — conflicting ducks on round change — *fixed within audio.js*.** `duck()` now
*combines* rather than replaces: it takes the deeper amount and the later release of any
duck still in flight (`_duckAmount` / `_duckUntil`). The order of `play('round_start')`
(which carries an `AUTO_DUCK`) and the manual `duck(0.5, 4)` right after it no longer
matters, and the duck length is no longer whichever call happened to be last. Verified.

**#22 — perk pickup mutes the horde for 3 s — fixed.** `AUTO_DUCK.perk_jingle_*` was
`[0.4, 3.2–3.4]`, now `[0.25, 1.2]` for all four. The review also asked for the jingle to
sit on a bus that does not duck: it already does — the jingles are on the `music` bus,
which is outside `duckGain` and (as of #6.6) outside the compressor too, so it peeks over
the mix without pulling it down.

**#23 — `gun_pap_layer` flat 0.55 on every PaP weapon including the Ray Gun —
*partial (audio side done)*.** Two weights exist: `gun_pap_layer` (light, −21 dB) and
`gun_pap_layer_heavy` (−18 dB with a sub), so the layer no longer buries the gun. The
player-facing half of this is already resolved in the weapons stream by a different
route — `weapons.js` scales the light layer per weapon type and skips it entirely for the
Ray Gun — so the heavy layer currently has **no call site**. It is therefore `defer: true`
as of the repair round (it must not cost init time while it waits) and still wants
selecting for rifle/LMG/shotgun: see "Needs from other streams" item 2.

**#26 — no per-bus volume control — *partial*.** The engine side is ready:
`setBusVolume(bus, v)` already existed, and `getBusVolume(bus)` and `listBuses()` were
added so an options slider can initialise itself. The menu UI is `main.js` — see below.

---

## `tools/audio-test.html`

- Regrouped into 21 panels covering every new sound; aliases are shown with a `→target`
  tag and deferred recipes with a `·lazy` tag.
- Each button now shows the sound's **dBFS level** rather than its duration, so the mix
  hierarchy is readable at a glance.
- New **Weapon bench** panel: sustained-fire buttons for all ten weapons at their real
  rpm (this is the voice-cap test — the burst must not gate), with brass scheduled at a
  realistic delay; and eight **reload sequences** that play the per-class parts in order
  with the timings a caller should use.
- New **In-round tension bed** panel: stack/unstack `round_bed_loop` and its two layers
  with long fades.
- Audition walks one pass per *recipe* (aliases are skipped), and a press on a
  not-yet-rendered deferred sound reports that it is rendering and retries.

---

## Needs from other streams

Everything below is a change in a file this stream does not own. All the sounds exist
already — unknown names are silent no-ops, so these can land in any order.

1. **`src/player/weapons.js` — per-weapon gunshots (#6).** Line ~393:
   ```js
   const perWeapon = `gun_${inst.id}`;
   const name = g.audio.has?.(perWeapon) ? perWeapon : (SOUND[s.type] || 'gun_rifle');
   g.audio.play(name, { volume: 1, rate: 0.96 + Math.random() * 0.08 });
   ```
   Without this the legacy aliases keep playing, so an M14 and a Galil stay identical.
2. **`src/player/weapons.js` — PaP layer (#23).** *Half landed*: `PAP_LAYER`
   (`weapons.js:20`) already scales the layer per weapon type and excludes the Ray Gun
   (0), which is the player-facing fix. What remains is the second weight —
   `gun_pap_layer_heavy` for rifle/LMG/shotgun, `gun_pap_layer` for pistol/SMG — which
   currently has no call site anywhere, so it is rendered lazily until it gets one.
3. **`src/player/weapons.js` — reload events (#4, #7).** Drive the per-class parts from a
   normalised event table instead of the three hard-coded fractions, and **remove the
   `rate: 1 / s.reloadMul` override** on the first reload sound — with Speed Cola the
   events should arrive sooner, never pitch up. `tools/audio-test.html`'s reload
   sequences give a usable event ordering and timing per class.
4. **`src/player/weapons.js` — pump timer (#12).** Replace
   `setTimeout(() => g.audio.play('reload_bolt'), 260)` with a game-time timer, and play
   `pump_back` then `pump_forward` (about 0.3 s apart) rather than one generic sound.
5. **`src/player/weapons.js` / `src/player/viewmodel.js` — shells (#3).** On each shot,
   `audio.playAt('shell_drop', p.pos, { volume: 0.5, delay: 0.38 + Math.random() * 0.15 })`
   (`shell_drop_shotgun` for the 870/Olympia). The engine already supports `opts.delay`.
6. **`src/player/weapons.js` — impacts (#10).** Always play the impact (drop the
   `Math.random() < 0.3` gate) and pick by surface: `impact_concrete` / `impact_wood` /
   `impact_metal` / `impact_dirt` / `impact_glass`. Make `flesh_hit` positional
   (`playAt(..., e.point, { volume: 0.55 })`) and play `hitmarker_head` on head hits.
7. **`src/ai/zombies.js` — zombie foley (#12).** `zombie_footstep` from a per-zombie step
   phase (skip beyond ~18 m; the cap is already 12), `zombie_bodyfall` on the death
   landing, `zombie_gib` when a limb or the body comes apart, `hellhound_footstep` on dog
   steps and `hellhound_death` in place of the generic death for dogs.
8. **`src/game/game.js` — in-round bed (#12).** Start `audio.music('round_bed_loop')` (or
   `audio.loop`) when a round starts, and layer `round_bed_layer_pulse` in from about
   round 6 and `round_bed_layer_choir` from about round 15 with ~4 s fades. Also add
   `footstep_concrete` for bunker zones, `land_soft`/`land_hard` off `landDip`, and
   `jump_grunt`.
9. **`src/game/game.js` — duplicate ducks (#21).** `duck()` now combines rather than
   replaces so the bug is neutralised, but the explicit `this.audio.duck(0.5, 4)` calls
   right after `play('round_start')` / `play('round_end')` are still redundant and can be
   deleted.
10. **`src/main.js` — bus sliders (#26).** `ui_click` / `ui_hover` are wired into the
    menu handlers already; the per-bus sliders are not. Add SFX / Music / Voice sliders
    calling `audio.setBusVolume(bus, v)` — `audio.listBuses()` and
    `audio.getBusVolume(bus)` exist to initialise them, and the defaults are
    `sfx 0.9 · ui 0.72 · music 0.62 · ambient 0.5`. This is the only part of #26 left.
11. **`src/player/viewmodel.js` / `weapons.js` — handling foley.** `ads_in` / `ads_out` on
    the ADS transition, `weapon_lower` / `weapon_raise` instead of one `weapon_switch`
    (and no lower phase on a fresh pickup), `low_ammo` when the magazine gets short, and
    `knife_hit_wall` on a knife swing that hits geometry.
