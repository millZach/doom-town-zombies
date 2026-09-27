# Fix log — stream `props-hud`

Files owned and changed: `src/game/interactables.js`, `src/game/powerups.js`, `src/ui/hud.js`,
`src/style.css`, `index.html`, `src/main.js`.
`npx vite build --logLevel error` passes clean.

**Repair round (post-verification):** three changes — the mystery-box ground pool was never
added to the scene (`this.pool` vs `this.groundPool`, #3), the three new power-up emblems were
unreachable because instant power-ups never entered the HUD list (#14), and the game-over
slow-motion is now a ramp rather than a permanent tenth-speed (#28). Details in each section.

---

## environment.md #1 — perk emissive + point lights blow interiors out — **fixed**

- `interactables.js` / new `GLOW_BANDS`, `glowKind()`, `glowMats()`, `setGlow()`
  (replaces the old one-line `glowMats`). Materials are now classified by name:
  - `…_sign_glow` (or any generic `glow`) → **sign** band `[0.85, 1.4]`. The authored
    Blender value wins as long as it sits in the band. Off value `0.02`.
  - `…_trim_glow` / `…accent` / `…lamp` / `…indicator` / `…bulb` → **trim** band
    `[2.4, 4.0]`, off value `0`.
  - `glow_q` / `question` → **mark** band `[0.35, 0.9]` (mystery-box "?").
  Both the split and the un-split GLBs work; the `Math.max(3, …)` clamp is gone from all
  three call sites (`PerkMachine.setPower`, `PowerSwitch.init/update`, `PackAPunch.init/setPower`).
  Materials are de-duplicated, so a material shared by several meshes is driven once.
- `PerkMachine.init` — light is now `PointLight(col, 2.2, 3.2, 2)` at `+0.45` forward,
  `+1.55` up (was `9 / 5 m` at `+0.9 / +1.8`), so it pools on the floor in front of the
  machine instead of wall-washing the room.
- `PerkMachine.update` — flicker scaled to the new intensity, plus a lazy neon wobble that
  is applied to the **trim** materials only (the sign stays steady and readable).
- `PackAPunch` — light `2.6 / 4 m` at `+0.6` forward (was `6 / 5 m` at `+1.0`);
  the `working` flare is `2.6 + rand*3.5` instead of `6 + rand*10`.

## environment.md #3 — mystery box beam — **fixed**

`interactables.js` / `BEAM_VERT`, `BEAM_FRAG`, `radialTexture()`, `MysteryBox.init`,
`MysteryBox.moveTo`, `MysteryBox.update`.

- `ShaderMaterial` replacing `MeshBasicMaterial`, `side: FrontSide` (no more double-counting
  through both cylinder walls).
- View-dependent rim falloff `pow(1 - |dot(N,V)|, 1.8)` — edges glow, centre is thin.
- Seamless scrolling fbm for interior structure (noise is sampled on a circle around the
  cylinder so there is no wrap seam), scrolling at `uTime * 0.55`.
- Height falloff `pow(1 - v, 2.6)` with a `smoothstep(0, 0.05, v)` bottom feather, and the
  cylinder is now **18 m** (`0.30 → 0.52 m` radius), not 45 m.
- Distance fog folded into the alpha (`1 - exp(-d²z²)`), with `uFogDensity` driven from
  `scene.fog.density` every frame so it tracks the per-zone/dog-round fog lerp. Additive
  blending cannot mix toward a fog colour, so this is done as an attenuation.
- Ground pool: a **2.6 m** additive radial disc at `+0.03 m`, breathing with the column.
  (Repair round: the disc was built as `this.groundPool` but added to the scene as
  `this.pool` — which is `undefined` at init time, since `this.pool` is the weapon-id array
  assigned in `use()`. THREE logged `object not an instance of THREE.Object3D` and the disc
  was never in the scene. Fixed at `MysteryBox.init`; the plane was also grown from 1.8 m to
  2.6 m because a 1.8 m disc is almost entirely hidden under the crate footprint.)
- `this.light` idle is now `intensity 6, distance 5` (was `2 / 4`), so the column actually
  lights the crate and the ground it stands on; open state `9 ± 2.5`.

## environment.md #13 — round counter illegible — **fixed**

- `index.html` `#brush` filter (already partly reworked before this pass; finished here):
  low-frequency warp (`0.035 0.09`, displacement 5) + a **62 % solid core** that is merged
  *under* the dry-brush streak layer, so the streak mask thins the stroke instead of
  shredding it; streak mask is `0 0 0 -0.9 0.95` at `baseFrequency 0.25 1.1`; a dilated
  over-spray fleck layer at 0.22 alpha sells the paint. Filter region retightened to the
  new viewBox.
- `index.html` — `#round-svg` viewBox `0 0 200 90` → `0 0 150 92`, so the art fills the
  element instead of occupying its left 70 %.
- `style.css` — stroke `var(--blood) #b3120e` → `var(--chalk-red) #d8342c`, base stroke-width
  `8.5 → 9.5`, element `320×144 → 296×182`, and a triple drop-shadow
  (`0 0 8px #000`, `0 2px 3px`, plus a soft red bleed) so it reads on bright asphalt.
  The round-change pulse flashes to a warm white rather than pure `#fff`.
- `hud.js` `setRound()` — four leaning, S-bowed tally strokes with per-stroke widths and
  end-point jitter, a diagonal slash at five, and hand-drawn numerals from `DIGITS` each at
  its own small rotation/offset. Stroke widths retuned for the new viewBox; numerals are
  now centred in it. Verified shapes for n = 1, 4, 5, 12, 100.

## environment.md #14 — missing power-up HUD icons — **fixed**

`hud.js` `puDisc()` + `PU_ICONS`. All six power-ups now have an emblem in one family
(struck-metal disc, hairline inner ring, solid glyph): **maxammo** ammo crate with two loose
rounds on the lid, **nuke** mushroom cloud over a ground line, **carpenter** claw hammer over
fresh boards, plus the existing skull / x2 / house-with-$. Per-power-up colours in `PU_COLOR`.
`style.css` gives each one a `.pu-emblem` with a colour-matched glow and a `.pu-bar`
countdown driven by `--f` (set every frame in `setPowerups` without touching the DOM tree).

**Repair round — the review's premise was wrong, and the icons were unreachable.** The review
said max ammo / nuke / carpenter "render as empty 58 px gaps"; in fact they never rendered at
all. `Powerups.update` built the HUD list purely from `this.timers`, and `grab()` only wrote
`this.timers` for ids that have a `duration` in `config.js POWERUPS` — which those three do
not. So the three new emblems were dead code. Plumbed properly:

- `powerups.js` — new `this.pulses` map (id → seconds left) and `PULSE_TIME = 5`. `grab()`
  sets `this.pulses[id] = PULSE_TIME` for any power-up without a `duration`; `update()`
  drains it and appends those entries to the same HUD list after the timed ones; `clear()`
  resets it. So picking up a Max Ammo now puts the crate emblem in the strip for 5 s with a
  draining bar, matching BO2's brief acknowledgement, then it pops out.
- Both kinds of entry now carry their own `dur`, and `hud.setPowerups` uses
  `list[i].dur || POWERUPS[id]?.duration || 30`, so a 5 s slot drains over 5 s and not 30.
- The `expiring` blink threshold is relative now (`left < min(5, dur * 0.2)`), so a 5 s
  acknowledgement slot does not blink for its entire life while a 30 s buff still blinks for
  its last 5 s.

## environment.md #15 — power-up drop glow swallows the model — **fixed**

`powerups.js` constructor, `load()`, `drop()`, `update()`, `clear()`.

- Halo sprite `color (1.6, 3, 1.4) @ scale 1.3` → `(0.9, 1.7, 0.8) @ scale 0.85`, and the
  gradient has a much longer soft tail so it no longer reads as a hard blob.
- New 1.4 m additive **ground pool** placed in world space (it does not bob with the drop).
- New 2.5 m vertical **sliver** sprite, bright at the base and faded out at the top with
  soft side edges, so a drop across the street is spottable.
- A slow shimmer (`0.82 ± 0.18`) drives halo scale, pool opacity and light intensity together.
- `load()` now tunes the drop models once: `envMapIntensity = 1.8` and, where the material
  has no authored emissive, a faint `0x4a2f06 @ 0.55` floor — so the gold prop stays gold
  inside a green halo instead of silhouetting.
- `PointLight(0x66ff44, 6, 4, 2)` kept as the review asked. Pool geometry/material is
  removed and disposed on pickup, expiry and `clear()`.

## environment.md #16 — box floating weapon tiny and hidden — **fixed**

`interactables.js` `MysteryBox.init` / `update`.

- `floater.scale = 1.7`.
- Base moved from `pos + (0, 0.55, 0)` to `pos + (0, 0.85, 0) + forward * 0.15`, rise
  `0.5 → 0.55`.
- Lid open angle `1.6 → 1.25` rad, so it no longer swings into the sightline.
- The floater now carries its own yaw (`this.spin`): it spins at ~2.4 rad/s while the box is
  cycling, decelerating with the cycle, then **settles back to broadside** for the offer with
  a slow ±10° sway and a small vertical bob — so the offered weapon is presented sideways and
  readable, BO2-style, but the cycle still changes silhouette.
- The offer used to start sinking immediately over its 12 s window; it now holds up for 9.5 s
  and sinks over the last 2.5 s.

## environment.md #17 — mystery box "?" marks — **partial** (the rest is `[blender:props]`)

Code side done: `MysteryBox.init` collects the crate's emissive materials (current crate ships
them as `glow`, the reworked one as `glow_q`), clamps them into the low **mark** band
`[0.35, 0.9]` so they stop burning, and `update()` breathes them in sync with the beam
(`0.72 + 0.28·sin`, ×1.8 while the box is open). The placeholder crate's "?" material was
renamed `glow_q` at `emissiveIntensity 0.6` to match the contract.
Still needed in Blender: replacing the extruded plastic "?" solids with a baked decal +
shallow normal, consistent size/placement per face, and the chain catenary/bracket fix.

## environment.md #22 — wall-buy chalk — **fixed**

`interactables.js` `chalkTexture()` and `WallBuy.init()`.

- **Emissive removed entirely** — no `emissive` / `emissiveMap` / `emissiveIntensity` on the
  chalk material at all, so it can no longer glow under a perk light.
- The generator was rewritten. It now renders the weapon with a **normal** material rather
  than flat white, which gives both the silhouette mask *and* interior normal
  discontinuities. From that it draws, in order:
  1. a light diagonal hatch inside the body (a drawing, not a filled blob);
  2. **interior construction lines** traced along the normal discontinuities (receiver /
     magazine / barrel joins), with jitter and dropouts;
  3. the silhouette in **three jittered passes** at `(0,0)/(+1.4,-1.1)/(-1.3,+1.2)` px with
     different alphas and dab sizes, modulated by a slow "pressure" term so the line fattens
     and thins along the contour, plus random dry-brush skips;
  4. the **price scrawled underneath** in three offset passes with a hand underline scratch
     (canvas band added below the art band; the quad is offset so the *art* still centres on
     the marker and under the mounted gun);
  5. a chalk-dust grain multiply and an erosion toward the plate edges.
  Strokes accumulate into a float coverage buffer instead of thousands of
  `fillStyle`/`fillRect` round-trips, so this stays cheap at load.

## environment.md #28 — menus / game over — **partial** (in-scope code done; grade shader + menu-camera drift are other streams)

- `index.html` — menu gained `.menu-scrim`, `.bars`, `.title-block`, `.title-rule`;
  game over gained `.go-blur`, `.go-vig`, `.bars`, `.go-eyebrow`, `.go-rule`.
- `style.css` — the menu gradient is off `#menu` and onto `.menu-scrim`, narrowed to the
  review's `rgba(5,3,3,0.88) 0%, 0.55 22%, transparent 48%` plus a small bottom lift, so the
  environment art survives. Animated film grain, a staggered title/rule/nav entrance, and
  cinematic letterbox bars that slide in.
- Game over is no longer a flat CSS red multiply: `.go-blur` ramps a
  `backdrop-filter: blur(9px) saturate(0.16) brightness(0.52)` over 1.8 s across the live
  scene, `.go-vig` fades a dark red vignette in over it, the title/rule/sub/stat cells stagger
  in, and the four stat cells animate individually.
- `main.js` `onGameOver` sets `game.timeScale = 0.1` so the world keeps running behind the
  screen almost frozen (restored to 1 on "End Game"/"Main Menu"; `game.start()` already
  resets it). **Repair round:** a flat `0.1` was close to counter-productive — in the `over`
  state `game.js` only runs `_updateMenuCamera` and ambient FX, so a permanent tenth-speed
  just slowed the already ~140 s camera drift by 10× and made the backdrop read as *more* of
  a still frame, which is exactly what #28 complains about. It now **hits** at `0.1` for the
  death beat, holds 0.9 s, and smoothsteps back to real time by ~4.4 s (`goRamp` in the frame
  loop, cancelled on retry/quit). Note this is still the weakest part of #28: the real ask
  (grade-shader desaturate/vignette ramp, and a faster menu drift with a dolly-in) lives in
  `renderer.js` / `game.js`, neither of which I own — see "Needs from other streams".
- Button hover treatment reworked (gold/blood tick, letter-spacing, glow).

## environment.md #29 — prompt / flash message identity — **fixed**

`style.css` + `index.html`.

- `#prompt` moved to `top: 58%`, put on a left-anchored dark plate that fades out to the
  right, with a 3 px **gold rule** (`.prompt-rule`) down its left edge and a slide-up `in`
  animation. `#prompt b` is now a proper BO2-style key glyph: gold hairline border, gold
  tinted fill, inner glow, min-width so `F` and `MOUSE 1` both look deliberate.
- `#flash-msg` gained hairline rules above and below that **draw outward** from the centre
  as it appears, and the text animates letter-spacing in from `0.34em` with a blur
  resolve — announcements now feel authored.

## weapons_audio.md #10 (HUD portions) — **fixed in HUD, needs call sites**

- `hud.hitmarker(kill, part)` — takes a body part, adds a `head` state (thicker, warm
  `#ffe9a8` strokes), a `kill` state (thicker red), a combined `kill.head` (orange), and a
  **scale pop** (`scale(1.5) → 1` over 110 ms) on every registration. Scoped as
  `#hitmarker.pop` so it cannot collide with the points `.pop` class (which is now scoped to
  `#points-pops .pop`).
- `hud.damageFrom(angle)` — directional damage arc: a rotated SVG arc at the crosshair with a
  scale-in/fade-out over 1.2 s, de-duplicated at 60 ms so a shotgun or a double swipe is one
  arc, capped at 6 concurrent. Styled in `#dmg-arcs` / `.dmg`.
- Low ammo: `setAmmo` drives `low` / `empty` / `dry` states plus a `#reload-hint`
  ("Reload" / "No Ammo") that slides in at zero mag; `low` is amber, `empty` blinks red,
  `dry` greys everything out and stops blinking.

## Menu sounds — **fixed**

`main.js` — `ui_hover` (0.45) on first pointerover of each `button[data-action]`, `ui_click`
(0.7) on every menu button click, and `ui_click` (0.4/0.5) on option slider/select commits.
All routed through the guarded `audio` wrapper, so unknown names are silent no-ops and the
order of the audio stream landing does not matter.

---

## Needs from other streams

1. **`src/player/weapons.js` (weapons stream)** — two of the four `hud.hitmarker()` call sites
   now pass a part (`:736`, `:771`, landed by the weapons stream). `weapons.js:471`
   (`g.hud.hitmarker(killed)`) still does not, so the headshot hitmarker state never fires on
   that path — harmless, but it should pass the hit part as the second argument
   (`'head'` / `'neck'` / anything else).
2. **`src/game/game.js` (gameplay stream)** — `game.js:518` (`this.hud.hitmarker(kill)`, the
   melee path) should pass a part too. And `hud.damageFrom(angle)` is implemented but still
   called from nowhere. At the `player_hurt` call site (~`game.js:347`), compute the yaw of the attacker
   relative to the camera forward and call it:
   ```js
   const to = attacker.pos.clone().sub(this.camera.position);
   this.camera.getWorldDirection(_fwd);
   const ang = Math.atan2(to.x * _fwd.z - to.z * _fwd.x, to.x * _fwd.x + to.z * _fwd.z);
   this.hud.damageFrom(-ang);
   ```
   (0 = dead ahead, positive = to the right.)
3. **`src/core/renderer.js` (renderer stream)** — environment.md #1(a) and #28(b) are outside
   my files: bloom should become `UnrealBloomPass(res, 0.32, 0.4, 1.15)` (my emissive budget
   is authored against that threshold, and the perk signs will still be slightly hot at the
   current `0.82`), and the game-over grade ramp (`uSaturation → 0.15`, `uVignette → 0.9`)
   would replace/reinforce my CSS `backdrop-filter` version.
4. **`src/game/game.js`** — environment.md #28(a): `_updateMenuCamera`'s drift period is ~140 s
   so the menu reads as a still; the review asks for a ~28 s cycle with a slow dolly-in.
   My game-over slow-motion ramp relies on `_updateMenuCamera` being what runs in the `over`
   state; once the drift is faster, the ramp will finally have something to reveal.
5. **Blender (props)** — the perk GLBs need the `<perkId>_sign_glow` / `<perkId>_trim_glow`
   split for item #1 to land fully; until then every perk emissive is treated as a sign
   (conservative — nothing blows out, but the small accent lamps are not as hot as they
   should be). The mystery crate needs `glow_q` + the decal rework for #17.
