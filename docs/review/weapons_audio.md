# Adversarial review — weapons, first-person animation, audio

**Verdict.** The architecture is there and the audio synthesis library is genuinely ambitious, but
nothing in this area is at BO2 level yet. Aim-down-sights is *broken*, not merely unpolished: the
receiver occupies ~57 % of screen height and you cannot see the sight picture (`renders/weapons/ak74u_ads.png`
is a solid black lump). Firing turns the viewmodel into a white silhouette. There is no shell
ejection, no bolt/slide motion on 8 of 10 guns, no break-open on the Olympia, no cylinder swing on
the Python. Ten weapons share six gunshot recipes and exactly three reload sounds. Every sound in
the game is peak-normalised to the same 0.95, so the mix has no dynamic hierarchy: a UI hover tick
and a 12-gauge blast leave the render at the same peak. Recoil has no spring, no pattern, and
permanently drifts the gun in yaw. `shell_drop`, `ui_click` and `ui_hover` are fully synthesised and
never played by anything.

Guns/animation is roughly a 4/10 against the brief; audio is a 5/10 — good bones, bad mix and far
too little per-weapon identity.

---

## Top 12

### 1. ADS is unusable — the gun body fills the frame and the sight picture is invisible `[both]` `M`

**What's wrong.** `src/player/viewmodel.js:334`
```js
const adsTarget = new THREE.Vector3(-e.aimLocal.x, -e.aimLocal.y, rest.p.z + 0.035);
```
The ADS pose keeps the weapon at essentially its rest depth (`rest.p.z + 0.035`). From the GLBs
(`node tools/inspect-glb.mjs public/models/weapons/ak74u.glb --tree`):
`weapon t=[0.15,-0.10,-0.27]`, `aim t=[0,0.09,0.06]`, `stock t=[-0.01,0.05,0.15]`.
At full ADS the weapon origin lands at z = −0.235, so the rear sight sits **17.5 cm** from the eye and
the stock **8.5 cm**. `src/game/game.js:584` then makes it worse:
```js
this.renderer.vmCamera.fov = 50 - this.viewmodel.ads * 6;   // 50° -> 44°, i.e. MAGNIFIES
```
At 44° vFOV, half-height at 0.175 m is 7.07 cm; the AK receiver is ~4 cm tall → **57 % of screen
height**. That is exactly what `renders/weapons/ak74u_ads.png` shows (an opaque blob with a tiny rear
notch) and what occludes the centre of `renders/review/14_vm_ak74u_ads.jpg`.

**Why it matters.** ADS is the single most-used action in the game. BO2 puts the rear sight ~0.30–0.35 m
from the eye at a wide weapon FOV so the receiver reads as ~15–20 % of frame height and the world is
visible around it. Right now aiming *reduces* what you can see.

**Concrete fix.**
- `viewmodel.js` `_animateWeapon`: anchor the aim node at a fixed eye distance instead of the rest depth:
  ```js
  const D = e.adsDist ?? 0.32;                     // per-weapon override later
  const adsTarget = new THREE.Vector3(-e.aimLocal.x, -e.aimLocal.y, -(D + e.aimLocal.z));
  ```
  For the AK this moves the weapon origin from z = −0.235 to −0.38; the stock goes from 8.5 cm to
  23 cm from the eye.
- `game.js:584`: stop narrowing the viewmodel camera. Use `vmCamera.fov = 50 + this.viewmodel.ads * 8`
  (50 → 58) so ADS *widens* the weapon frustum. Receiver then reads ≈ 4 cm / (2·0.32·tan29°) ≈ 11 %
  of screen height.
- Add `adsDist` per weapon in `config.js` (pistols 0.26, SMG/rifle 0.32, LMG/shotgun 0.34) and a
  per-weapon `adsTime`; today `viewmodel.js:289` uses `s.adsSpeed || 11` and `game.js:587` never
  passes `adsSpeed`, so the M1911 and the RPD aim in at identical speed.
- Re-shoot `renders/weapons/*_ads.png` from a camera matching the new numbers; the current ADS
  check render does not satisfy `docs/ASSET_CONTRACT.md` §3 ("that render must look like a finished
  shooter's hip-fire frame").

---

### 2. Firing bleaches the viewmodel to pure white `[code]` `S`

**What's wrong.** `src/player/viewmodel.js:154` and `:312`
```js
this.flashLight = new THREE.PointLight(0xffb060, 0, 4, 2);   // decay 2
...
this.flashLight.intensity = this.flashTime > 0 ? 6 : 0;      // constant for 50 ms
```
With physically-correct decay 2, irradiance at the ~0.3 m of the weapon body is `6 / 0.3² ≈ 67`.
That is then fed into `UnrealBloomPass(…, strength 0.55, radius 0.55, threshold 0.82)`
(`src/core/renderer.js:148`). Result: `renders/review/19_combat_mp5_firing_hud_perks_powerups.jpg` —
the entire gun and both hands are a white glowing mass for the whole burst.

**Why it matters.** During sustained auto fire the player never sees the weapon. It is the first thing
anyone notices.

**Concrete fix.** In `Viewmodel.update`:
```js
this.flashTime = Math.max(0, this.flashTime - dt);
const fl = this.flashTime / 0.045;                 // 0..1
this.flashLight.intensity = fl * fl * 1.1;         // peak ~1.1, quadratic decay
```
and set `this.flashLight.distance = 1.2` in the constructor so it cannot light the arms from behind.
Shorten `fire()`'s `this.flashTime = 0.05` to `0.032` (2 frames at 60 fps). Additionally clamp the
flash sprite's contribution: `MeshBasicMaterial.color = new THREE.Color(3,2.4,1.8)`
(`viewmodel.js:130`) is already above the 0.82 bloom threshold on its own — drop to `(1.6,1.3,0.9)`
and let the additive blend plus a *short* light do the work.

---

### 3. No shell ejection — the locator and the sound both exist and neither is used `[code]` `M`

**What's wrong.** Every GLB has an `eject` empty at the ejection port (`ak74u: eject t=[0.02,0.05,-0.04]`),
`viewmodel.js:192` reads it into `entry.eject`, and **nothing anywhere references `entry.eject` again**
(`grep -rn "eject" src/` returns only the loader and the placeholder). `src/audio/sfx.js:662`
`SFX.shell_drop` is a fully built 3–5-bounce brass recipe with pitched pings and pans — **never
called**.

**Why it matters.** Brass arcing out of the port and tinkling on concrete is half of what makes a
shooter feel mechanical. Its absence is the loudest "this is a prototype" tell in the whole game.

**Concrete fix.**
- Add a small pooled shell system. Because the viewmodel lives in its own scene/camera
  (`renderer.js:117–118`), spawn the shells **in `vmScene`** as instanced 8-segment cylinders
  (brass, 0.009 × 0.024 m for 5.45/9 mm, 0.0185 × 0.07 m for 12-gauge) so they inherit the weapon FOV.
  Spawn in `Viewmodel.fire()` from `entry.eject.getWorldPosition()` with velocity
  `right * (1.3 ± 0.3) + up * (0.9 ± 0.3) + fwd * (−0.2)` in holder space, angular velocity
  `(rnd(-25,25), rnd(-15,15), rnd(-30,30))` rad/s, gravity 9.8, life 0.8 s, fade out over the last 0.15 s.
- Per-type timing: pistol/rifle/SMG/LMG on every shot; `mode: 'pump'` on the pump stroke (`pumpT`
  crossing 0.35), `mode: 'break'` two shells during the `break` reload at r = 0.3.
- Play `shell_drop` with `playAt` at the player position, delayed ~0.35–0.5 s
  (`audio.playAt('shell_drop', p.pos, { volume: 0.35, delay: 0.38 + Math.random()*0.15 })` — the
  engine already supports `opts.delay`, `audio.js:560`). Suppress when `p.zone` is a wood interior
  and use a lower `rate` there.

---

### 4. Reloads: rigid-body transforms plus one generic sound set for ten weapons `[both]` `L`

**What's wrong.**
- Animation: `viewmodel.js:380–430` translates the whole `arm_L` object toward the mag rest
  position and rotates the gun. The arms are static meshes with baked finger poses
  (`skins: 0` on every GLB), so the left hand flies to the magwell still shaped around the
  handguard, fingers closed on nothing, then flies back. Nothing else moves: `magEmpty`'s
  "charge handle" branch (`:405–410`) just adds a sinusoidal roll because `e.bolt` is null on the AK,
  Galil, MP5 and RPD (only `m14` has a `bolt`, only `m1911` has a `slide`).
- Audio: `weapons.js:158/279/281` play `reload_mag_out`, `reload_mag_in`, `reload_bolt` for
  *every* magazine weapon. The M1911, MP5, AK-74u, Galil, M14 and RPD reload with identical foley.
  The event times are hard-coded fractions (0 / 0.62 / 0.75 of `reloadDur`), so the RPD's 5.2 s
  reload has two sounds in it with a 3.2 s silence, and the M1911's 1.6 s reload has them on top
  of each other.

**Why it matters.** The reload is the second-most-frequent animation in a zombies match and the place
where per-weapon character lives. Generic foley on a rigid arm reads as placeholder.

**Concrete fix.**
- Data-drive it. Add to each `WEAPONS` entry in `config.js`:
  ```js
  reloadEvents: [ [0.05,'mag_release'], [0.18,'mag_out'], [0.46,'mag_grab'], [0.62,'mag_in'], [0.78,'bolt'] ]
  ```
  normalised 0..1, and in `weapons.js` case `'reload'` fire each event once as `vm.reloadT` crosses it
  instead of the three hard-coded thresholds.
- Split the SFX into per-family recipes: `reload_mag_out_steel` / `_polymer` / `_drum`,
  `reload_mag_in_steel` / `_polymer`, `reload_bolt_ak` (heavy, low 900/1600 Hz clack) vs
  `reload_bolt_ar` (bright, 2200/3600/5200) vs `reload_pump` (two-stroke, wood rattle). ~6 new recipes
  reusing `clack()` + `noiseBurst()` — cheap.
- Animation: in `_animateWeapon`'s mag branch, also drive the **right** hand (it never moves — see #8),
  add a mag-well "seat" impulse on the gun at r = 0.62 (`p.y -= 0.012` for 60 ms, `rx += 0.05`), and add
  a visible magazine *in the left hand* during the 0.42–0.66 window (clone `e.mag`, parent to `armL`).

---

### 5. No bolt, slide, break-open or cylinder motion on 8 of 10 guns `[both]` `M`

**What's wrong.** From the GLB trees:

| weapon | moving parts present | animated by code |
|---|---|---|
| m1911 | `slide`, `mag` | slide ✓ |
| m14 | `bolt`, `mag` | bolt ✓ |
| ak74u / galil / mp5 / rpd | `mag` only | nothing reciprocates |
| remington870 | `pump` | pump ✓ |
| olympia | `action`, `barrels` | **nothing** — `kind: 'break'` (`viewmodel.js:419`) only tilts the whole gun; the barrels never open |
| python | `cylinder` | spins in place; never swings out |
| raygun | none | nothing |

`viewmodel.js:442–443` only handles `slide` and `bolt`, and `slideBack` decays at 18/s
(`:295`) while the MP5 fires at 13.3 rounds/s — even if a bolt existed it would barely move.

Separately, `viewmodel.js:427` `e.cylinder.rotateZ(dt * 12 * tilt)` **accumulates forever**:
`_animateWeapon` resets `mag`, `pump`, `slide` and `bolt` to rest every frame (`:379`, `:432–443`)
but never `cylinder`, so the Python's flutes end each reload at a random angle and drift further
every reload.

**Why it matters.** A gun that fires without its action moving reads as a static prop with a light
attached. Reciprocating mass is the core of gun "feel".

**Concrete fix.**
- `[blender:weapons]` Split out `bolt` (charging handle + dust cover) on `build_ak74u.py`,
  `build_galil.py`, `build_mp5.py`, `build_rpd.py`; add a `barrels` pivot empty at the hinge pin on
  `build_olympia.py` and re-parent `barrels` under it; add a `crane` pivot on `build_python.py` so the
  cylinder can swing out about the crane axis.
- `[code]` In `_animateWeapon`, reset `cylinder` from `e.rest` like the others, and drive it with an
  absolute angle (`e.cylinder.rotation.z = rest.z + spin`) not `rotateZ`. Raise the `slideBack`
  decay to a fixed 45 ms duration rather than a rate, and give it a real travel: `0.06 m` for rifles,
  `0.032 m` for the M1911 slide, easing out-in (`Math.sin(u*Math.PI)` where `u = t/0.045`).
- `break` reload: rotate the `barrels` pivot to −38° at r ∈ [0.2, 0.45], hold, close at r ∈ [0.7, 0.9]
  with a `clack` at close; eject two hulls at r = 0.3.

---

### 6. Gun audio: 6 recipes for 10 guns, truncated tails, a voice cap that gates auto fire, and a mix with no hierarchy `[audio]` `L`

**What's wrong.**
1. `src/player/weapons.js:10` maps *type*, not weapon: M14 and Galil are both `gun_rifle`; MP5 and
   AK-74u are both `gun_smg`; Olympia and 870 are both `gun_shotgun`. In BO2 these are unmistakably
   different. PaP adds one flat `gun_pap_layer` at 0.55 for every weapon (`weapons.js:394`).
2. `sfx.js:416` renders guns at `dur: 0.72` (0.95 for shotgun/revolver) while the tail convolver
   uses `lib.ir.street`, a **1.4 s** IR (`audio.js:355`). The outdoor tail is chopped mid-decay and
   then `deClick()` fades the last 8 ms. Every shot ends abruptly.
3. `dsp.js:511–548` `noiseBurst` applies the `drive` waveshaper **before** the amplitude envelope
   (`node → shaper → gain`). With `drive: 5–9` (`satCurve` = tanh(6x)/tanh(6)) the noise is hard
   soft-clipped at constant input level for the entire decay, so the tail is exactly as distorted as
   the transient. Real gunfire gets *cleaner* as it decays; this will read as a constant fizzy hiss.
4. `audio.js:91` `SAME_NAME_CAP.default = 6`. The MP5 at 800 rpm (Double Tap: 1064 rpm) fires 13–18
   shots/second into a 0.72 s buffer — you need ~10–13 concurrent voices. At 6 the engine stops the
   oldest with a 20 ms fade, so during any sustained burst every shot is cut at ~0.4 s. That is an
   audible gate.
5. `audio.js:422` `normalizeBuffer(buf, 0.95)` on *every* sound. A 12-gauge blast, a UI hover tick and
   a footstep all land at 0.95 peak. All relative loudness then has to come from the ad-hoc `gain`
   field and per-call `volume`, and long reverberant sounds (explosion, nuke) end up with far lower
   RMS than short clicks at the same peak — explosions will feel weaker than a hitmarker.
6. `audio.js:289–294` the master `DynamicsCompressor` is `threshold −14, ratio 6, attack 4 ms,
   release 180 ms`. A 4 ms attack eats the first 4 ms of every gunshot — the part that carries the
   crack — and at 6:1 the whole mix (including music, which is routed through `preMaster → master`)
   pumps with gunfire.
7. `audio.js:423` `deClick(buf, 0.0012, …)` applies a 1.2 ms linear fade-in to every one-shot. On a
   gunshot that is ~58 samples of ramp across the sharpest edge in the sound.

**Concrete fix.**
- Per-weapon specs: extend `GUN_SPECS` (`sfx.js:217`) from 6 to 10 entries keyed by weapon id, and
  change `SOUND` in `weapons.js:10` to `gun_${inst.id}`, falling back to the type. Differentiate at
  minimum: M14 (`crack 3400, bodyDec 0.12, thump0 140`, wood-stock mech at 1400/2400 Hz) vs Galil
  (`crack 3000, mech 2200/3600/5200`); AK-74u (`crack 2400, body 640, mechAmp 0.5`, distinct
  low 1100 Hz bolt clack) vs MP5 (current `gun_smg`); Olympia (two barrels, `mech: false`, longer
  `poof`) vs 870 (`mechT 0.03` + the pump as a separate event).
- Split the tail off the shot. Make the rendered buffers **dry** (`spec.tail = 0`) at `dur: 0.28`,
  and add a single persistent `ConvolverNode` (street IR) on a `gunTail` send in the live graph in
  `audio.js._buildGraph()`. One shared reverb means N shots sum into one tail instead of N baked
  tails stacking, the tail is never truncated, and voice cost drops.
- Move the shaper after the envelope in `noiseBurst` (`dsp.js:532` → connect `node → g → shaper → pan`),
  and drop `drive` values by ~40 % to compensate.
- `SAME_NAME_CAP`: add `gun_smg: 14, gun_rifle: 12, gun_lmg: 14, gun_pistol: 8, gun_shotgun: 6`;
  raise `MAX_VOICES` to 80.
- Replace blanket peak-normalisation with a target-LUFS-ish normalisation: add `rec.level` (dBFS RMS
  target) and scale by RMS, clamping peak at 0.99. Suggested targets: guns −13, explosion −11,
  impacts −20, footsteps −28, UI −24, zombie voices −19.
- Master chain: raise `compressor.threshold` to −6, `ratio` to 3, `attack` to 0.02 (let the limiter
  catch peaks) and move `buses.music` to connect *after* the compressor so music does not pump.
- `deClick` fade-in for non-loops: `0.0002`.

---

### 7. Speed Cola pitches the reload sound up an octave `[code]` `S`

**What's wrong.** `src/player/weapons.js:158`
```js
this.game.audio.play('reload_mag_out', { volume: 0.8, rate: 1 / s.reloadMul });
```
`s.reloadMul` is `0.5` with Speed Cola (`weapons.js:56`), so `rate = 2` — the mag-release sample plays
at **double speed and one octave up**, while `reload_mag_in` (`:279`) and `reload_bolt` (`:281`) are
left at rate 1. So with the most commonly bought perk in the game, your reload starts with a chipmunk
click and then drops back to normal pitch.

**Why it matters.** It is a one-line bug on a sound the player hears hundreds of times a match.

**Concrete fix.** Remove the `rate` override entirely and instead render short/long variants, or at
worst clamp it: `rate: THREE.MathUtils.clamp(1 / s.reloadMul, 1, 1.15)`. The correct answer is #4's
normalised event table — with Speed Cola the events simply arrive sooner; the sounds themselves do
not change pitch.

---

### 8. Recoil has no spring, permanently drifts the gun in yaw, and the right hand never moves `[code]` `M`

**What's wrong.**
- `viewmodel.js:268` sets `this.kickSide = (Math.random() - 0.5) * strength` and `:367` applies
  `ry += this.kickSide * 0.02` — **`kickSide` is never decayed** in `update()` (`:291–295` decays
  `kick` and `kickRot` only). After every shot the gun keeps a permanent ±0.6° yaw offset until the
  next shot changes it. On semi-autos this is a visible, permanent misalignment.
- `kick` and `kickRot` decay by pure exponential (`*= 1 - dt*14` / `1 - dt*11`) with a hard ceiling
  (`Math.min(1.6, …)`). There is no overshoot and no settle, so at high RPM the gun parks at a fixed
  offset instead of shaking, and after the last shot it eases back with no snap.
- `player.js:174–178`: `recoilPitch` is pulled fully back to 0 at 5/s, so there is **no recoil the
  player has to control** — every weapon returns to the exact original aim point. Horizontal kick is
  `(Math.random() - 0.4) * s.recoil * 0.3` (`weapons.js:399`) — pure noise, no per-weapon pattern.
- `weapons.js:400` `p.shake(0.03 * heavy)`; trauma is squared in `player.js:191`, so a shotgun blast
  produces `sh = 0.0044` and a camera offset of `0.0044 × 0.05 rad ≈ 0.013°`. Firing a 12-gauge
  literally does not move the camera.
- `arm_R` is reset to rest in `_resetParts` and then **never touched by any animation** — not by
  recoil, not by the reload, not by the bolt rack. The right hand is welded to the grip while the
  gun jumps under it.

**Concrete fix.**
- Decay `kickSide` alongside the others: `this.kickSide *= Math.max(0, 1 - dt * 12);`
- Replace the exponential decay with a critically-damped spring so the gun overshoots and settles:
  ```js
  // per axis: x = position, v = velocity, k = 220, c = 2*sqrt(k) * 0.55 (underdamped)
  this.kickV += (-220 * this.kick - 2 * Math.sqrt(220) * 0.55 * this.kickV) * dt;
  this.kick  += this.kickV * dt;
  ```
  with `fire()` injecting velocity (`this.kickV += 9 * strength`) instead of position.
- Per-weapon recoil patterns in `config.js`: `recoilPattern: [[0,0],[0.9,0.2],[1.6,-0.35],…]` sampled
  by `shotCount % pattern.length`, and leave ~35 % of the accumulated pitch un-recentred
  (`player.js:177`: `this.recoilPitch -= this.recoilPitch * Math.min(1, 5*dt) * 0.65`) so bursts
  actually climb.
- Scale `p.shake()` on fire to `0.10 * heavy` and make `_updateCamera` use `sh = trauma` (not squared)
  for the positional component.
- Drive `arm_R` from `kick` in `_animateWeapon`: `armR.position.z += kick * 0.012; armR.rotateX(kickRot * 0.02)`,
  and pull it back during `magEmpty`'s rack window so the hand visibly slaps the charging handle.

---

### 9. One muzzle flash for every weapon; the Ray Gun has none; no ejection-port or barrel smoke `[code]` `M`

**What's wrong.** `viewmodel.js:116–139` builds a single canvas flash with 6 fixed star spikes.
`fire()` (`:269–274`) randomises only the Z rotation and a uniform scale of 0.09–0.14. So the M1911,
the RPD and the Olympia all produce the same flash at the same size. `weapons.js:398`
```js
vm.fire(heavy * (this.ads ? 0.6 : 1), s.type !== 'raygun');
```
explicitly disables the flash for the Ray Gun — BO2's Ray Gun has a large green bloom at the muzzle.
`muzzleSmoke` fires only `Math.random() < 0.5` (`weapons.js:404`) with 2 particles, and there is no
ejection-port smoke and no sustained-fire barrel smoke.

**Why it matters.** The muzzle flash is the single biggest visual payoff per trigger pull.

**Concrete fix.**
- Add `flash: { scale, color, spikes, sideLen }` to `WEAPONS`: pistol 0.07 / 3 spikes, SMG 0.09,
  rifle 0.11, LMG 0.14, shotgun 0.20 with a wide low-frequency bloom, raygun 0.16 green
  (`color 0x66ff55`, no spikes, add a 0.25 s afterglow on the `glow` mesh).
- Build 3–4 flash textures at init and pick randomly per shot instead of rotating one; scale
  non-uniformly (`x: s, y: s * rnd(0.8,1.25)`), and offset the side cards along the barrel by
  `sideLen` so the shotgun's flash reads as a cone rather than a star.
- Halve the flash when `ads > 0.5` and shift it forward so it does not wash the rear sight.
- Ejection-port smoke: `fx.muzzleSmoke(ejectWorld, right)` at 25 % probability with 1 particle,
  greyer and slower. Barrel smoke: track `heat += 1 per shot; heat *= 1 - dt*0.4;` and when
  `heat > 8` emit one slow 0.25→0.6 m puff from `muzzle` every 0.25 s.

---

### 10. Hit feedback is thin and 70 % of wall impacts are silent `[both]` `M`

**What's wrong.**
- `weapons.js:438`: `if (Math.random() < 0.3) g.audio.playAt('bullet_impact_wall', …)` — seven out of
  ten rounds hit the world in silence, while the decal and sparks still appear. Desync between what
  you see and what you hear.
- `weapons.js:458`: `g.audio.play('flesh_hit', …)` is **2D** (`play`, not `playAt`), so hitting a
  zombie 40 m away sounds identical to point-blank, and gives no directional cue.
- One impact recipe (`bullet_impact_wall`, concrete/plaster) for every surface: the game has cars,
  wooden houses, metal barrels, glass. No ricochet/penetration distinction.
- `hud.js:127–130`: the hitmarker is an opacity toggle over 0.18 s with a `kill` class. No scale pop,
  no headshot variant, no directional damage indicator when the player is hit.
- `zombies.js:371` plays `headshot` positionally (good) but there is no audio distinction on the
  hitmarker itself, and `hitmarker` is capped at 4 concurrent (`audio.js:91`) — a shotgun hitting 5
  zombies retriggers and steals its own voices.

**Concrete fix.**
- Always play the impact; vary it instead: pass surface from the raycast
  (`collision.raycast` should return a `material` tag) and add `bullet_impact_metal`,
  `bullet_impact_wood`, `bullet_impact_glass` recipes — each is a `clack` + `noiseBurst` + optional
  ricochet, ~15 lines apiece reusing what's in `bullet_impact_wall`.
- `flesh_hit` → `playAt(…, e.point, { volume: 0.55 })`.
- `hud.hitmarker()`: add a CSS transform pop (`scale(1.45) → 1` over 90 ms) and a third state
  `headshot` (thicker strokes, warmer colour). Play a brighter `hitmarker_head` ping (add a partial at
  6200 Hz) on head/neck hits.
- Add a directional damage arc: `hud.damageFrom(angle)` driven from `game.js:347`'s `player_hurt` call
  site — currently the player has no idea which side the zombie hit from.

---

### 11. Weapon models and hands are well below "amazing" `[blender:weapons]` `L`

**What's wrong.**
- `renders/weapons/ak74u_hipfire.png`: the receiver, magazine, pistol grip and both hands are
  **outside the frame**. The contract (`docs/ASSET_CONTRACT.md` §3) explicitly requires this check
  render to "look like a finished shooter's hip-fire frame". It doesn't. The barrel is also parallel
  to the view axis, not angled toward screen centre as the contract asks — the 4.3° cant is bolted on
  in code instead (`viewmodel.js:339`).
- `renders/weapons/raygun_detail.png`: the body reads as a smooth red balloon with a chrome bell. No
  panel lines, no fins, no rivets; the "glow_green" rings are blown out to featureless white; the
  sight is a single black block. This is the most iconic weapon in the mode and it looks like a
  bath toy.
- `renders/weapons/m1911_grip.png`: the glove fingers are uniform sausages with no knuckle creases,
  no fingernail plates and no tendon relief; the cuff is a stack of smooth donuts; the sleeve is a
  smooth cone with a repeating rib pattern. The slide has no cocking serrations, no extractor, no
  visible hammer/grip safety, and the front sight is a 1 mm nub.
- `renders/review/13_vm_ak74u_hip.jpg`: in-engine the gun reads as a dark undifferentiated
  silhouette — the viewmodel lighting rig (`viewmodel.js:151–155`: one hemi + one directional +
  two point lights) gives it no rim and no specular separation from the background.

**Concrete fix.**
- `[blender:weapons]` Fix the check-render camera in `build_testbed.py` to 50° vFOV at 16:9 and
  re-frame each `*_hipfire.png` so the weapon sits in the lower-right third with the grip and both
  hands in frame; iterate the `weapon` origin until it does.
- Raygun (`build_raygun.py`): add the boxed lower receiver, 4 cooling fins, a ribbed muzzle bell with
  3 concentric rings, panel seams and 6 visible screws (`lib_weapons.screw`), and tone the
  `glow_green` emission down by ~60 % so the rings read as rings, not a blob.
- Hands (`lib_weapons.build_hand` / `glove_detail`): add a knuckle crease loop per PIP joint
  (0.6 mm indent), a nail plate on the thumb and index, and a webbing fillet between fingers.
  Vary finger radii (index 0.0092, middle 0.0095, ring 0.0088, little 0.0078) instead of one radius.
- Slide serrations on the M1911, gas-tube ports on the AK, the Galil's handle, the 870's ribbed
  forend — all available via `grooves()` / `knurl_band()` already in the library.
- `[code]` Add a rim light to the viewmodel rig: a second `DirectionalLight(0x9fc0ff, 0.8)` from
  behind-left (`position.set(-0.6, 0.4, 0.8)`) so the gun separates from dark backgrounds.

---

### 12. Audio coverage holes: no zombie footsteps, no body fall, no in-round music, dead registry entries `[audio]` `M`

**What's wrong.**
- `grep audio src/ai/zombies.js`: zombies have voice (`groan`, `scream`, `attack`, `death`), a rise
  sound and a bite — and **no footsteps, no body fall, no gib/limb sound, no barricade scrabble
  beyond `board_tear`**. Two dozen zombies sprinting at you in total silence except moans is the
  biggest single reason the horde does not feel physical.
- Music: `src/audio/music.js` defines only `MUSIC.menu` (`:319`) and `MUSIC.game_over` (`:417`).
  There is **no in-round music bed and no tension layer at all** — from round 1 to round 40 the only
  continuous audio is `ambient_loop`. BO2 escalates.
- `SFX.ui_click` (`sfx.js:2002`) and `SFX.ui_hover` (`:2010`) are built and **never played**
  (`grep -rn "ui_click|ui_hover" src/` hits only their definitions). The entire menu in `main.js` is
  silent.
- Player foley: two surfaces only (`footstep_dirt` / `footstep_wood`, `game.js:572`), no concrete for
  the bunker, no landing thud, no jump exertion, no sprint breathing, no ADS-in/out cloth, no
  low-ammo click. `weapon_switch` is one sound played for both the lower and the raise
  (`weapons.js:101`), and it fires even on a fresh pickup that has no lower phase.
- `weapons.js:395`: `setTimeout(() => g.audio.play('reload_bolt', …), 260)` for the pump — wall-clock,
  not game time. It ignores pause, ignores `timeScale`, and is never cancelled on weapon switch or
  death, so you can hear a pump rack after you've swapped guns or gone down.
- `audio.announce()` (`audio.js:760–809`) uses browser `speechSynthesis` at `pitch 0.1`. Whatever
  voice the OS supplies, it will sound like a screen reader, not Samantha/the BO2 announcer.

**Concrete fix.**
- Add `zombie_step_dirt` / `zombie_step_wood` (4 variants, low-passed 900 Hz, gain ~0.35) driven from
  a per-zombie step phase in `zombies.js:524` (`z.stepPhase += step / z.stride`), and
  `zombie_bodyfall` (thud + cloth + gravel, 0.6 s) on the death-ragdoll landing. Cap them
  (`SAME_NAME_CAP.zombie_step_dirt = 10`) and skip any zombie beyond 18 m.
- Add `MUSIC.round_bed` with 3 intensity layers gated by round number, crossfaded via the existing
  `audio.music()`; simplest version: a sub drone + a slow pulse whose rate rises with round, plus a
  detuned choir pad above round 15.
- Wire `ui_click` / `ui_hover` into `main.js`'s button handlers.
- Add `footstep_concrete`, `land_soft` / `land_hard` (from `player.js:162`'s `landDip`), `jump_grunt`,
  `ads_in` / `ads_out` (a 60 ms cloth+detent brush), and split `weapon_switch` into
  `weapon_lower` / `weapon_raise`.
- Replace the `setTimeout` pump with a timer in `Weapons.update` (`this.pumpSoundT`), and replace
  `announce()`'s TTS with pre-rendered formant phrases (the `zombieVoice`/`formantBank` engine in
  `sfx.js` can already produce a processed radio voice) or drop the words and keep the stinger.

---

## Lesser issues

13. `[code]` `S` — **First-shot accuracy was intended and never implemented.** `weapons.js:415`:
    `coneDir(_fwd, pellets > 1 ? spread : spread * (i === 0 && this.ads ? 1 : 1), dir)` — the ternary
    returns `1` on both branches. Also `weapons.js:346` `this.spread *= 1;` is a no-op. Make the first
    shot after ≥0.4 s of no fire use `spreadAds * 0.25`.

14. `[code]` `S` — **Weapon sway is frame-rate dependent.** `viewmodel.js:293–294` feeds the raw
    per-frame `input.mouse.dx` into the sway target, so sway amplitude scales with frame time. Divide
    by `dt` and clamp: `-clamp(s.mouseDx / Math.max(dt,1e-3) * 1.5e-5, -0.06, 0.06)`.

15. `[code]` `S` — **The world muzzle light is not at the muzzle.** `game.js:481–483` puts it at
    `camera.position + forward * 0.9`, i.e. dead ahead at head height. Shadows from the muzzle flash
    therefore point the wrong way. Use `this.weapons.muzzleWorld(_v)` (which already exists,
    `weapons.js:375`).

16. `[code]` `S` — **Idle/bob is a single-axis sine.** `viewmodel.js:347–350` and `player.js:189–190`
    use `|sin(bobTime)|` on Y and `cos` on X with no phase relation beyond 2:1. Use a proper Lissajous
    (`x = sin(t)`, `y = sin(2t)`) plus a `roll = sin(t) * 0.012` and a short dip impulse on each
    footstep event, so walking reads as steps rather than a hum.

17. `[code]` `S` — **No sprint animation, only a sprint pose.** `viewmodel.js:359–361` blends to one
    static offset. Add a 2 Hz swing driven by `bobTime` at ~3× the walk amplitude, plus a small
    counter-rotation, and ease out over 0.12 s on sprint exit (the current `k(…, 8)` is symmetric).

18. `[code]` `S` — **`inspectT` is declared (`viewmodel.js:177`) and never used.** There is no weapon
    inspect. Cheap win: 1.6 s tilt + rotate on a keypress.

19. `[code]` `S` — **Tracers fire on alternate shots only and are one stretched sprite.**
    `weapons.js:444` `this.shotCount % 2 === 0`, and `particles.js:321–330` bails when
    `dist < 2`. Use every 3rd round, add a short 0.06 s muzzle-side glow, and give the tracer a
    brighter head + dimmer tail (two spawns at different sizes).

20. `[code]` `S` — **The knife has no impact variation and no wall hit.** `weapons.js:301` plays
    `knife_hit` only when a zombie is found; swinging into geometry is silent. Add a
    `knife_hit_wall` (metallic scrape) on a short forward raycast.

21. `[audio]` `S` — **Conflicting ducks on round change.** `game.js:210/212` play `round_start`
    (which carries `AUTO_DUCK [0.6, 3.6]`, `audio.js:52`) and then `game.js:215` calls
    `this.audio.duck(0.5, 4)` immediately after, which cancels and replaces the auto duck. Same at
    `_endRound` (`:224/225`). Pick one; the double call makes the duck length non-obvious.

22. `[audio]` `S` — **Perk pickup mutes the horde for 3 s.** `AUTO_DUCK.perk_jingle_* = [0.4, 3.2]`
    (`audio.js:51–54`) drops the whole world bus to 60 % for over three seconds every time you buy a
    perk — mid-round that is dangerous and feels wrong. Reduce to `[0.25, 1.2]` and put the jingle on
    the `ui` bus so it sits above without ducking.

23. `[audio]` `S` — **`gun_pap_layer` is a flat 0.55 on every PaP weapon including the Ray Gun**
    (`weapons.js:394`), which already has its own energy. Scale by type and skip it for `raygun`.

24. `[code]` `S` — **Confusing dead condition in the ADS gate.** `weapons.js:234`:
    `['ready','reload'].includes(this.state) && this.state !== 'reload'` — `'reload'` is added and
    then excluded. Simplify to `this.state === 'ready'`.

25. `[code]` `S` — **PaP camo is applied to the world model too, at full strength.** `makePapMaterial`
    (`viewmodel.js:42–62`) pushes `totalEmissiveRadiance += cm*cm*2.2`. At bloom threshold 0.82
    that is why `renders/review/16_vm_remington870_pap_hip.jpg` has an unreadable green-white blob
    where the receiver should be. Drop to `~0.6` and add a fresnel term so the glow reads on edges
    rather than flat faces.

26. `[audio]` `S` — **No per-bus volume control in the options menu.** `audio.setBusVolume` exists
    (`audio.js:672`) and nothing calls it; `main.js:87` only sets master. Add SFX / Music / Voice
    sliders — trivial, and this mix badly needs them.
