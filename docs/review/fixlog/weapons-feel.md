# Fix log — stream `weapons-feel`

Files owned/touched: `src/player/viewmodel.js`, `src/player/weapons.js`, `src/player/player.js`,
`src/config.js`, `src/fx/shells.js` (new), `src/fx/tracers.js` (new, repair round).

`npx vite build --logLevel error` passes clean.

---

## Repair round (post-verification)

1. **Blocking — tracer head/tail were the same sprite.** `Particles.tracer(from, to, color)` has no
   size parameter and hard-codes `size0: 0.012 / stretch: 0.3`, so the two spawns differed only in
   colour and additively overlapped into one streak. `particles.js` belongs to the zombies stream, so
   instead of asking for a signature change I added **`src/fx/tracers.js`** (details in lesser item
   19 below) and `weapons.js _fire` now calls `this.tracers.spawn(muzzle, endPoint, head, tail)`
   once. Verified with a headless harness (stubbed canvas): head instance = 1.1 m × 0.055 scale, tail
   instance = 5.0 m × 0.026 scale, trailing 3 m behind it, all matrices finite including the
   degenerate case where the shot is exactly along the view axis.
2. **`vm.fire({ boltTravel })` was dead.** `fire()` reads `opts.boltDur`; the travel comes from the
   weapon def the viewmodel already holds. Removed the unused argument from `weapons.js _fire` and
   corrected the `fire()` JSDoc.
3. **LMG end-of-reload safety commit was a no-op.** `case 'mag_in'` deliberately skips the commit for
   the belt-fed class, so the `if (!this.reloadCommitted) this._reloadEvent('mag_in', …)` net could
   never have refilled the RPD. It now fires `'belt'` for the LMG class. (Unreachable today — the
   event loop drains every beat at `reloadT = 1` first — but it is no longer a trap.)
4. **`_surfaceAt` dead ternary** (`flat ? 'concrete' : 'concrete'`) collapsed to `return 'concrete'`
   with a comment saying why the bunker has no orientation split.
5. **Knife-on-zombie hitmarker** now passes the part it actually reports to `zombies.damage`
   (`hud.hitmarker(killed, 'body')`), so every hitmarker call site carries a part.
6. **Sprint swing** raised to ≈3× the walk amplitude and the ease-out retimed to 0.12 s (review item
   17 asked for both; the first pass was 1.7× and 0.077 s).
7. Corrected two over-claims in this log: the ADS `updateProjectionMatrix` guard (see #1 below) and
   the tracer wording.

Still unverifiable without a live run (flagged for the integrator): the Pack-a-Punch fresnel shader
injection (Vite does not compile GLSL), and whether the muzzle-flash point light — cut to the
review's prescribed peak ≈1.1 / range 1.2 m from 6 / 4 m — now reads as too *dim*. Both are one
screenshot away; the flash peak lives in `viewmodel.js _setupFlash` (`this.flashPeak`) and is a
single-number change.

---

## weapons_audio.md #1 — ADS unusable — **fixed**

- `config.js`: every `WEAPONS` entry gained `adsDist` (0.26 pistol → 0.34 LMG/shotgun) and `adsTime`
  (0.15 s M1911 → 0.32 s RPD). New export `VM_FOV = { hip: 50, ads: 58 }`.
- `viewmodel.js` `_animateWeapon`: the ADS target is now
  `(-aimLocal.x, -aimLocal.y, -(adsDist + aimLocal.z))` — the aim node is anchored at a fixed
  distance from the eye instead of the weapon's rest depth. For the AK the origin moves from
  z = −0.235 to ≈ −0.38.
- `viewmodel.js` `update`: sets `vmCamera.fov = 50 + ads * 8` (widening, not magnifying) *after*
  `game.js` writes its own value, so the fix lands without editing `game.js`. The
  `updateProjectionMatrix` call is guarded by a `> 1e-4` compare, but note that in practice it fires
  every frame while ADS > 0, because `game.js` rewrites `vmCamera.fov` three lines earlier — the
  guard only pays off once that dead line is removed (see "Needs from other streams" #2). One extra
  projection-matrix rebuild per frame is harmless.
- `viewmodel.js` `update`: ADS rate is derived per weapon from `adsTime` (`2.4 / adsTime`) instead of
  the hard-coded `11`, so the M1911 and the RPD no longer aim in at the same speed. `s.adsSpeed`
  still wins if a caller passes it.

Left: the `renders/weapons/*_ads.png` check renders still need re-shooting (Blender stream).

## weapons_audio.md #2 — firing bleaches the viewmodel — **fixed**

- `viewmodel.js` constructor: `flashLight` is now `PointLight(0xffb060, 0, 1.2, 2)` — range 1.2 m so
  it cannot light the arms from behind.
- `viewmodel.js` `update`: `flashLight.intensity = fl * fl * flashPeak` with
  `fl = flashTime / flashDur`, `flashDur = 0.032 s` (+ afterglow), `flashPeak ≈ 1.1` scaled by the
  weapon's flash size and clamped to 0.55–1.9.
- `viewmodel.js` `flashMaterial` / `_setupFlash`: flash textures are now white with an alpha falloff
  and the *material colour* carries the hue, set from the weapon at a normalised HDR magnitude of
  1.55 (1.8 for the Ray Gun) instead of the old fixed `Color(3, 2.4, 1.8)`.
- Bonus (#11's code half): added a `DirectionalLight(0x9fc0ff, 0.8)` rim from behind-left so the gun
  separates from dark backgrounds.

## weapons_audio.md #3 — no shell ejection — **fixed**

- New `src/fx/shells.js` (`ShellSystem`). Two `InstancedMesh` pools per case type (brass 4.9 × 24.5 mm,
  shotshell 9.4 × 68 mm) with baked vertex colours for the rim/head, no per-shot allocation.
- Cases are born in the **viewmodel scene** (parented to `Viewmodel.holder`, identity transform, so
  they inherit the weapon FOV and vanish with the viewmodel during cutscene cameras), fly for 0.30 s
  under camera-space gravity, then hand off to the **world scene**, inheriting camera velocity, where
  they bounce (normal restitution + tangential friction), settle flat on the surface normal and lie
  there for 7 s before fading.
- `viewmodel.js` `ejectShell(kind, scale, boost)` spawns from the `eject` locator with
  `right*(1.3±0.3) + up*(0.9±0.3) + fwd*(−0.2..−0.45)` in weapon space and randomised angular
  velocity.
- Sound: `shell_drop` / `shell_drop_shotgun` play **on the bounce** via `playAt`, volume scaled by
  impact and rate-varied — so the tinkle lines up with the case actually hitting the floor rather than
  a fixed delay. If there is no world scene or no collision system, `_fallbackPing` schedules the
  sound with `delay: 0.3–0.48` instead (never silent). Falls back to `shell_drop` when
  `audio.has('shell_drop_shotgun')` is false.
- Per-type timing in `weapons.js`: every shot for pistol/rifle/SMG/LMG (`shellKind` + `shellScale` in
  `config.js`); `mode: 'pump'` ejects on the pump back-stroke at `pumpT` crossing 0.35; the Olympia
  throws two hulls on the `eject` reload beat; the Python throws six cases on its `eject` beat.

## weapons_audio.md #4 — reload choreography + per-class foley — **fixed**

- `config.js`: `RELOAD_EVENTS` — normalised 0..1 event tables for `pistol / smg / rifle / lmg /
  break / revolver / raygun / shotgun`, plus `reloadClassOf(def)`.
- `weapons.js` `startReload` + `update` case `'reload'`: events fire once each as `vm.reloadT` crosses
  them, replacing the three hard-coded 0 / 0.62 / 0.75 thresholds. Ammo commits on the event
  (`mag_in`, `belt`, `shell`/`shell2`, `close`), with a safety commit if the reload ends first.
- `weapons.js` `RELOAD_SFX`: a `[contractName, legacyFallback, volume]` triple per class per event.
  Every call goes through `_snd()`, which uses `audio.has?.()` to pick the new contract name and
  otherwise falls back to `reload_mag_out` / `reload_mag_in` / `reload_bolt` / `reload_shell`, so the
  reloads are never silent regardless of which stream lands first.
- `viewmodel.js` `_reloadPose` dispatches to a per-class routine, each driving the gun pose, **both**
  arms, the magazine and the moving parts:
  - `_reloadMag` (pistol/SMG/rifle): magwell cant toward camera, mag drops and is hidden, left hand
    tracks it down / off-screen / back, an AK-style **rock-in** when `magRock`, a spare magazine
    cloned into the left hand across the grab→insert window (`_magInHand`), a mag-well **seat
    impulse** at r ≈ 0.62–0.72, and on an empty reload the charging handle is racked by `arm_R`
    (`arm_L` for the pistol slide).
  - `_reloadLmg`: cover-open attitude, belt out, spare belt in the hand, cover slam, bolt.
  - `_reloadBreak`, `_reloadRevolver`, `_reloadShotgun`, `_reloadRaygun` — see #5.
- Weight/overshoot: the weapon position runs through an underdamped spring (`K = 300, ζ = 0.62`)
  blended at `0.45 * (1 - ads)`, so the gun lags and overshoots on fast pose changes but is rock solid
  at full ADS. Recoil translation is applied *after* the spring so the kick keeps its snap.

Left: per-family *recipes* (`reload_mag_out_steel/_polymer/_drum` etc.) are the audio stream's job;
this stream only provides the call sites and the contract names.

## weapons_audio.md #5 — no bolt / slide / break-open / cylinder motion — **fixed (code half)**

- `viewmodel.js` `load`: now also resolves `barrels`, `crane`, `action` and stores their rest
  transforms; `_resetAnimParts` resets all of them (including `cylinder` and `action`, which
  previously accumulated forever).
- **Cylinder drift bug fixed**: `cylinder` is reset from rest every frame and driven by an *absolute*
  angle (`cylAngle` chasing `cylTarget`) instead of `rotateZ(dt * …)`. The Python now indexes one
  chamber per shot (`TAU / mag`) and free-spins during the ejector-rod beat, and the angle is kept
  modulo 2π.
- **Slide/bolt travel** is a fixed **45 ms** cycle (`Math.sin(u·π)`), not an 18 /s decay, so it reads
  identically at 520 rpm and 1064 rpm. Distance comes from `boltTravel` in `config.js`
  (0.032 m M1911 slide → 0.065 m RPD). Applied to both `slide` and `bolt` along local +Z (back), per
  the asset contract. `rackOverride` lets a reload rack the action independently of the fire cycle.
- **Olympia**: `_reloadBreak` rotates the `barrels` node about local X to ≈ −38° over r ∈ [0.18, 0.34],
  holds, and closes over r ∈ [0.74, 0.88] with a wrist-flick and the `reload_break_close` clack; two
  hulls eject at the `eject` beat. If `barrels` is absent it gracefully falls back to tilting the
  whole gun (the old behaviour).
- **Python**: `_reloadRevolver` rotates `crane` about local Z (~66°) to swing the cylinder out; if
  `crane` is absent it slides `cylinder` sideways instead.
- **Placeholder viewmodels** gained `slide` / `barrels` / `crane`+`cylinder` nodes so the animation
  paths are exercised even before the real GLBs land.

Needs from other streams — see "Needs from other streams" below (the `bolt` nodes on
ak74u/galil/mp5/rpd, `barrels` on olympia, `crane` on python).

## weapons_audio.md #7 — Speed Cola pitches the reload — **fixed**

`weapons.js` `startReload` no longer plays anything with `rate: 1 / s.reloadMul`. There is no `rate`
override anywhere in the reload path. Speed Cola only multiplies `reloadDur` by 0.5, and because the
event table is normalised, every beat simply arrives sooner at its natural pitch.

## weapons_audio.md #8 — recoil — **fixed**

- `kickSide` is no longer a never-decayed random offset: all three axes (`kick`, `kickRot`,
  `kickSide`) are **spring-damper** state (`K = 220 / 185 / 150`, `ζ = 0.55 / 0.5 / 0.62`) integrated
  in `Viewmodel.update`, and `fire()` injects **velocity** rather than position. The gun now
  overshoots past rest and settles.
- `config.js`: `recoilPattern` per weapon — `[[pitchMul, yawMul], …]` sampled by
  `shotCount % pattern.length`. The MP5 climbs almost straight with a slow right drift, the AK kicks
  up-left then snaps right, the Galil walks left then right, the shotguns alternate, the Python is
  a big alternating slam.
- `player.js` `addRecoil`: split into a *view kick* (springs back) and a small **permanent** aim shift
  (22 % of the kick, applied straight to `pitch`/`yaw` and clamped), so a burst genuinely walks off
  target and recoil control exists. `recoilPitch` now recentres at 65 % of the old rate and
  `recoilYaw` at 80 %, so bursts also accumulate view kick.
- `player.js` `_updateCamera`: the positional shake component now uses `sh = trauma` (linear) and
  actually offsets `cam.position`; the rotational component keeps `trauma²`. `weapons.js` fires
  `p.shake(0.10 * heavy)` (was `0.03 * heavy`), so a 12-gauge visibly moves the camera.
- `KICK` per family in `weapons.js` plus `kickScale` overrides in `config.js` (Olympia/870 2.2,
  Python 1.8, RPD 1.15).
- `arm_R` is driven from the recoil springs (`position.z += kick * 0.012`,
  `rotateX(kickRot * 0.02)`) and is pulled back during the rack window of an empty reload; `arm_L`
  gets a smaller share.

## weapons_audio.md #9 — muzzle flashes, Ray Gun, smoke — **fixed**

- `config.js`: `flash: { scale, color, spikes, sideLen, wide?, afterglow? }` per weapon — pistol 0.075
  / 3 spikes, SMG 0.09, AK 0.105, rifle 0.11–0.115, LMG 0.145 / 6 spikes, shotguns 0.18–0.2 with
  `wide` and long side cards, Ray Gun 0.17 green / 0 spikes / 0.28 s afterglow.
- `viewmodel.js`: flash textures are generated per `(spikes, variant)` with 3 random variants each and
  picked at random per shot instead of rotating one texture. Non-uniform scale
  (`x: s·wide, y: s·rnd(0.8,1.25)`), side cards scaled and offset along the barrel by `sideLen` so a
  shotgun flash reads as a cone. Flash is halved and pushed forward when `ads > 0.5`.
- **Ray Gun now has a flash**: `weapons.js` passes `flash` for every weapon (the old
  `s.type !== 'raygun'` suppression is gone), and the Ray Gun's `afterglow` keeps a shrinking, fading
  green bloom alive for 0.28 s. Pack-a-Punch recolours it from `projectileColor`.
- `viewmodel.js` also drives any `glow`-named emissive material on the weapon from a `charge` value —
  a flare on each Ray Gun shot and a ramp during the reload's `charge` beat.
- Smoke: `weapons.js` tracks `heat += 1` per shot with `heat *= 1 - dt*0.4`; muzzle smoke probability
  scales with heat (`0.35 + min(0.45, heat*0.04)`) and above `heat > 8` a slow puff is emitted from
  the muzzle every 0.25 s. **Ejection-port smoke** fires at 25 % from the new `ejectWorld()`.

## weapons_audio.md #10 — hit feedback & impacts — **fixed (my half)**

- Wall impacts are **always** audible. The 30 % dice roll is gone; instead the *sound* varies by
  surface: `_surfaceAt(point, normal)` classifies via `map.zoneAt` + face orientation and plays
  `impact_concrete` / `impact_wood` / `impact_dirt` (contract names) with
  `bullet_impact_wall` as the fallback. Shotguns cap at 2 impact voices per shot, rifles at 1.
- `flesh_hit` is now positional: `playAt(impact_flesh → flesh_hit, point, { volume: 0.55 })`.
- Hitmarker: passes the real part to `hud.hitmarker(kill, 'head'|'body'|part)` (the HUD stream's new
  signature) and plays `hitmarker_head` (falling back to `hitmarker`) on head/neck hits.
- Knife: `knife_hit` is now positional, and a miss does a 1.7 m forward raycast and plays
  `knife_hit_wall` (→ `impact_<surface>` → `bullet_impact_wall`) with sparks (lesser item #20).

## Lesser items

| id | status | what changed |
|---|---|---|
| 13 first-shot accuracy | fixed | `weapons.js` `_fire`: `sinceFire >= 0.4` && ADS && single-projectile ⇒ `spread = spreadAds * 0.25`. The dead ternary and the `this.spread *= 1` no-op are gone. |
| 14 frame-rate-dependent sway | fixed | `viewmodel.js` `update`: `clamp(-mouseDx / max(dt,1e-3) * 1.5e-5, ±0.06)`. |
| 15 world muzzle light misplaced | fixed (from my side) | `weapons.js` `_fire` sets `g.muzzleLight.position` to `muzzleWorld()` right after `flashWorldLight()`. `game.js` itself is untouched. |
| 16 single-axis bob | fixed | `player.js` `_updateCamera` and `viewmodel.js` `_animateWeapon` both use a Lissajous (`x = sin t`, `y = sin 2t`), a `roll = sin(t) * 0.012` and a **footstep dip impulse** (`stepDip`, decaying at 8 /s) fired on each bob half-cycle. |
| 17 sprint pose, no animation | fixed | 2 Hz swing driven by `bobTime` with counter-rotation, at ≈3× the walk-bob amplitude (x ±0.040 vs the walk's 0.013); sprint blends *in* at 5.2 /s (≈0.2 s, you have to commit) and *out* at 8.3 /s (≈0.12 s, the review's number) instead of a symmetric 8 /s. |
| 18 `inspectT` unused | fixed | `Viewmodel.inspect()` + a 1.6 s tilt/rotate/wobble pose, bound to **`KeyI`** in `Weapons.update` (only while `ready`). |
| 19 tracers | fixed (rebuilt in the repair round) | every **3rd** round (was alternate shots), plus a 0.06 s `fx.glow` at the muzzle. The head/tail split now comes from a new **`src/fx/tracers.js` (`TracerSystem`)** instead of two `fx.tracer()` calls — `Particles.tracer()` takes no size argument, so the two spawns were geometrically identical. Each tracer is two camera-facing quads on the same ray: a 1.1 m × 55 mm hot head and a 5.0 m × 26 mm dim tail trailing it, both fading over the last 30 % of the flight. Pooled: one geometry, one additive material, one `InstancedMesh` (24 tracers × 2 instances, `DynamicDrawUsage`), no allocation per shot or per frame. Attached to `g.scene` and stepped from `Weapons.update`. Also drops the old `dist < 2` bail (only sub-0.35 m contact shots are skipped). |
| 20 knife has no wall hit | fixed | see #10 above. |
| 24 dead ADS condition | fixed | `['ready','reload'].includes(...) && !== 'reload'` → `this.state === 'ready'`. |
| 25 PaP camo blows out | fixed | `makePapMaterial`: emission dropped from `cm*cm*2.2` to `cm*cm*(0.18 + 1.3*fresnel)*0.6`, with the fresnel built from two new varyings (view normal + view position) so the glow rides edges instead of flat faces. |
| 12 (partial) `setTimeout` pump | fixed | replaced with a **game-time** timer list (`_schedule` / `this.timers`) processed in `Weapons.update`; cleared on weapon switch and when the player goes down. Plays `pump_back` / `pump_forward` (→ `reload_bolt`) at 12 % and 62 % of the pump stroke. |
| 12 (partial) `weapon_switch` split | fixed | `weapon_lower` on the holster phase only (a fresh pickup has no lower phase, so it is silent there) and `weapon_raise` on the swap, both falling back to `weapon_switch`. |
| 12 (partial) player foley | fixed | `player.js` exposes `jumpEvent` and `landEvent` (impact speed); `Weapons.update` consumes them and plays `jump_grunt`, and `land_soft` / `land_hard` (→ `footstep_dirt`) with a camera shake on a hard landing. Sprint breathing (`sprint_breath`) every 1.1 s while sprinting. `ads_in` / `ads_out` on the ADS edge. All name-guarded, so they are silent no-ops until the audio stream renders them. |
| 23 flat PaP layer | fixed | `PAP_LAYER` by family (0.3 SMG → 0.5 shotgun/revolver) and **0 for the Ray Gun**, which is skipped entirely. |

Not mine / not done here: #6 (gun recipes & mix), #11 (Blender models), #12's zombie footsteps,
in-round music, `ui_click`/`ui_hover`, `announce()`, #21, #22, #26, and the HUD half of #10
(hitmarker CSS pop, `damageFrom` call site in `game.js`).

---

## Needs from other streams

1. **`collision.raycast` needs a surface/material tag.** `src/world/collision.js:raycast` returns
   `{ point, normal, distance }` only. `weapons.js _surfaceAt()` currently *infers* the surface from
   `map.zoneAt(point)` plus the face normal, which cannot tell a car door from a plaster wall.
   Please add a `material` (or `surface`) string to the raycast result — the impact call site already
   builds the sound name as `impact_${surface}` and will use it unchanged
   (`impact_flesh | impact_concrete | impact_wood | impact_metal | impact_dirt`).
2. **`game.js:584`** still writes `vmCamera.fov = 50 - ads * 6` every frame. The viewmodel overwrites
   it immediately afterwards, so the behaviour is correct, but the line is now dead and misleading —
   please delete it (or change it to use `VM_FOV` from `config.js`).
3. **`game.js:481` `flashWorldLight`** still parks `muzzleLight` at `camera + forward * 0.9`.
   `weapons.js` repositions it onto the real muzzle right after the call, but it would be cleaner for
   `flashWorldLight` to accept a position (or call `this.weapons.muzzleWorld(_v)` itself).
4. **Footstep surfaces** (`game.js:572`) are still `footstep_wood` / `footstep_dirt` only — a
   `footstep_concrete` branch for `zone === 'bunker'` belongs there, not in my files.
5. **HUD**: `hud.hitmarker(kill, part)` now receives `'head'` on head/neck hits from `weapons.js` and
   `zh[0].part` from the Ray Gun path — the headshot styling is the HUD stream's side. A
   `hud.damageFrom(angle)` call from `game.js`'s `player_hurt` site is still missing.
6. **Asset contract nodes** that the animation code already drives and currently no-ops on:
   `bolt` on ak74u / galil / mp5 / rpd, `barrels` (hinge-pin origin) on olympia, `crane` on python.
   All have graceful fallbacks, but the motion only appears once the GLBs ship them. **Sign check for
   the integrator:** `barrels` is rotated by `-0.66 rad` about local X and `crane` by `+1.15 rad`
   about local Z — if either opens the wrong way, flip the sign in `viewmodel.js`
   `_reloadBreak` / `_reloadRevolver`.
7. **Audio names this stream now calls** (all `has()`-guarded with legacy fallbacks, so order does not
   matter): `gun_<id>` ×10, the full reload-part set, `pump_back` / `pump_forward`,
   `slide_release` / `bolt_pull` / `bolt_release`, `shell_drop` / `shell_drop_shotgun`,
   `impact_flesh|concrete|wood|metal|dirt`, `hitmarker_head`, `knife_hit_wall`, `weapon_lower` /
   `weapon_raise`, `ads_in` / `ads_out`, `land_soft` / `land_hard`, `jump_grunt`, `sprint_breath`,
   `raygun_charge`. (`sprint_breath` and `raygun_charge` are the only two not yet in `sfx.js`;
   `sprint_breath` has no fallback and is a silent no-op until it exists.)
8. **`Particles.tracer()` is now unused by the weapons** — bullet tracers come from
   `src/fx/tracers.js`. It is still called by nothing else that I can see, and it still bails on
   `dist < 2`; if the FX stream wants to keep it, a `size`/`stretch` argument would make it usable
   again, otherwise it can be deleted. Nothing in my files depends on it either way.
