# Fix log — stream `lighting-post`

Files owned/changed: `src/core/renderer.js`, `src/world/sky.js`, `src/world/map.js`, `src/game/game.js`.
`npx vite build --logLevel error` passes (exit 0). The pooled light rig was also exercised headless
(synthetic map root → `buildLightRig` → 300 frames of `updateLights` → quality switch) to confirm slot
hand-over, flicker and the quality tiers behave.

**Repair round.** Six blocking problems from the adversarial verifier are fixed: the dead
`hasOwnLight` flag that let two sites run coincident lights (#11, #12), the no-op `PCFSoftShadowMap`
plus a real widened PCF kernel in its place (#7), the indoor `fx.ash` fallback that spawned outside
the room (#24), and all three round-bed audio defects (discarded volume, permanently-silent bed after
an unready buffer, and the false ducking claim). Details are inline in each section below.

---

## environment.md #1 (bloom half only) — **fixed**

- `renderer.js:_buildComposer` — `UnrealBloomPass(res, 0.32, 0.4, 1.15)` (was `0.55 / 0.55 / 0.82`).
  Threshold now sits above lit surfaces, so only real emissives bloom, and the radius is half as wide.
- `game.js:_setMapGlow` (new, called from `setPower` and `start`) — replaces the
  `emissiveIntensity = Math.max(2, base)` clamp. Marquee-type glow materials are clamped to `0.8–1.4`,
  only `*_trim_glow` accents are allowed `≥2.2`, and unpowered glow sits at `base * 0.15`.
- `map.js:_process` — every `*glow*` material is tagged `userData.glowKind = 'sign' | 'trim' | 'other'`
  from the new asset-node contract (`<perkId>_sign_glow` / `<perkId>_trim_glow`) so the split above works
  the moment the Blender stream lands the split materials; until then everything is treated as a sign.
- `game.js:_updatePlaying` — indoor exposure lift dropped from `[1.0, 1.18, 1.35]` to
  `[1.0, 1.08, 1.15]` (`ZONE_MOOD`), which is what compounded the bloom indoors.

Not mine: `interactables.js:231/238` (perk point light + emissive clamp) — see "Needs from other streams".

## #2 sun-side white void / fog + sky values — **fixed**

- `game.js:load` — fog is now `FogExp2(Color(0.18, 0.13, 0.12), 0.008)` (was warm `0.36, 0.20, 0.13` at
  `0.012`): the air is cooler and darker than the sky, so buildings and the horde silhouette against it.
- `sky.js:skyFrag` — `horizon` toward-sun term `1.7, 0.62, 0.18 → 1.05, 0.44, 0.15`; disc term
  `4.0, 2.2, 1.0 → 2.4, 1.4, 0.7`; glow/zenith/ground haze pulled down to match.
- #2c aerial perspective, done properly rather than faked: `sky.js:applyAerialPerspective()` +
  `updateAerial(camera)` patch the fog chunk of the world materials (`map.js:_process` applies it to every
  map material) so the haze only blends toward a warm value inside a cone around the sun
  (`pow(dot(viewDir, sunDirView), 3.0)`), and stays neutral-cool everywhere else. Materials that are not
  patched (zombies, props, viewmodel) simply keep the plain fog — no breakage, and any other stream can
  opt in by calling `applyAerialPerspective(material)`.

## #4 viewmodel blows to white — **fixed (my half)**

- `renderer.js:_buildComposer` — pass order is now
  `worldPass → gtao → bloom → vmPass → OutputPass → smaa → grade`. The viewmodel is composited after the
  bloom convolution, so it can neither feed it nor receive it; GTAO stays world-only (it runs before the
  viewmodel is drawn).
- The second half (a dim dedicated muzzle-flash light for the viewmodel scene) is the weapons stream's.

## #7 shadows - **fixed (one high-resolution cascade with a widened PCF kernel)**

- `renderer.js` - `shadowMap.type = THREE.PCFShadowMap`. **Repair:** the earlier `PCFSoftShadowMap`
  was a no-op - r186 removed it, `WebGLShadowMap.render()` warns and silently reverts to
  `PCFShadowMap`, i.e. exactly the baseline value plus a console warning every session.
- `sky.js:configureShadowFilter(taps)` (new) - the real soft-shadow fix for r186. Stock
  `SHADOWMAP_TYPE_PCF` is a **fixed 5-tap** Vogel disk rotated per pixel by interleaved-gradient
  noise; five taps cannot carry a wide radius (it reads as dither), which is why the review's
  "hard, aliased" shadow survives any amount of `shadow.radius`. So the kernel itself is widened:
  the sample block in `THREE.ShaderChunk.shadowmap_pars_fragment` is swapped, once and before any
  material compiles, for a loop with **12 taps on high / 8 on medium** (x hardware PCF = 48 / 32
  filtered taps). The patch is a guarded regex - if three's chunk ever changes shape the replace
  simply does not fire and stock three's 5 taps stay. Verified against the installed `three@0.186`:
  the regex matches, the emitted GLSL is a plain constant-bound loop, and re-running it is a no-op.
- `sky.js:SHADOW_TIERS` - high `4096` / `+-28 m` / radius 3.0 / 12 taps (~1.4 cm texel, ~4 cm
  penumbra), medium `2048` / `+-26` / 2.2 / 8, low `1024` / `+-22` / 1.4 / stock kernel.
  `effectiveRadius()` clamps the radius to what the *compiled* kernel can resolve, so a session
  launched on low and raised to high never gets a wide radius over 5 taps; `setQuality` recompiles
  the scene's materials once if the tap count actually changed.
- `sun.shadow.blurSamples` removed - it only affects `VSMShadowMap` and was inert here.
- `sky.js:createLights` - `bias -0.0002`, `normalBias 0.055` (peter-panning under planks/debris).
- `sky.js:follow(pos, forward)` - the frustum is centred 32 % of its extent ahead of the player and
  snapped to texels, so the budget is spent in front of the camera and the map does not shimmer.
- **Deliberately not done: a second sun cascade.** Confirmed against the installed build:
  `THREE.SunLight` does not exist in the WebGL renderer (the cascade path in the shadow chunk is
  WebGPU-only), so a CSM would mean two shadow-casting directional lights splitting the sun, with a
  hard player-following seam where they meet - worse than the single tight cascade above.

## #11 lighting rig (bounce / fill / practicals / rim) — **fixed**

- `sky.js:createLights` now builds a rig, not a sun: key sun `3.8`, a cool non-shadowing **rim**
  (`0.52, 0.62, 0.9` at `0.85`, azimuth `SUN_DIR + 150°`, elevation `25°` — zombies.md #10's "single
  biggest readability win"), a warm **ground bounce** from below (`0.85, 0.46, 0.26` at `0.5`), and the
  hemisphere. All three follow the player.
- `map.js` — new pooled local-light rig (`buildLightRig` / `updateLights` / `setLightQuality`):
  - `LightPool` keeps a **fixed** number of point lights in the scene (changing the count re-compiles
    every material in three.js) and re-targets them to the nearest emitters with a cross-fade, so nothing
    pops and distant emitters cost nothing.
  - Sites: 12 street/bunker lamps, 9 fires, and ~22 procedural fill sites (the shipped map GLB
    has no `MK_LIGHT_*` markers yet, so the derived rig is what actually runs).
  - Fills are derived from the map when no authored markers exist: a low warm bounce ×2 per interior
    room, a cool ceiling wash in the bunker, a cool sky-fill on the inside face of every `MK_BARRIER_*`
    window plus a dim warm spill outside it, and a kicker above/behind every perk machine and the PaP.
  - **`MK_LIGHT_*` markers win when present** (`extras.color` / `intensity` / `range`), so the Blender
    stream can author the rig without any further code change.
  - **Hand-over, not double-lighting (repair):** the two sites that also own a dedicated
    shadow-casting light carry a `site.own` term (0 far away -> 1 within ~5 m of the switch-on
    distance, smoothstepped). The dedicated light is scaled by `own` and the pooled copy by
    `1 - own` through the new `siteGain()`, which `LightPool._assign` and `LightPool.update` both
    respect. Previously the flag (`hasOwnLight`) was written and never read, so the bunker cage lamp
    and the biggest fire each ran **two coincident lights** - double brightness, and the shadowless
    copy filled in the very shadows the dedicated light exists to cast. Exercised headless: the sum
    of pooled + dedicated intensity is now constant (10.00) at every distance across the crossover,
    and the old hard binary `near` switch is gone, so nothing pops either.
  - One bunker cage lamp casts real shadows (`shadow.mapSize 512`, `autoUpdate = false` — the bunker is
    static, so the cube map is baked once and re-baked only when the power state changes). The ceiling
    trunk and pillars finally have form without paying for a dynamic cube shadow every frame.
  - Budget: high `5 lamps + 4 fires + 6 fills` = 15 pooled + 2 shadow lights, i.e. *fewer* point lights
    than the old fixed 18, better distributed. Medium 12, low 8.
- `game.js:_updatePlaying` — `environmentIntensity` indoors raised from `[0.6, 0.35, 0.2]` to
  `[0.60, 0.42, 0.30]`, hemi from `[0.55, 0.32, 0.16]` to `[0.55, 0.36, 0.22]`; the rim keeps working
  indoors at `0.45` while the outdoor ground bounce drops to `0.12`.

## #12 fires must light and flicker the world - **fixed (the lighting half is mine)**

- `map.js:_buildFires` — **every** fire gets a light (was: the first 6 of 9), scaled by the marker's
  `scale`, with a proper flicker profile (two beating sines + a slow breath + a fast jitter) instead of
  one sine; the pool keeps the nearest 4 live.
- The largest fire gets a **shadow-casting** point light (`512`, static bake) on high, so its flicker
  moves light and shadow across the fence, the barrel and the ground. **Repair:** it now cross-fades
  with its pooled copy over a 5 m band (`site.own` / `siteGain()`, see #11) instead of both burning
  at once and switching on a hard distance test.
- `renderer.js` GradeShader + `game.js:_updateHeatHaze` — screen-space **heat haze**: up to four nearby
  fires are fed to the grade pass as `(uv, radius, strength)` and the air above them shivers with a
  rising, noise-driven UV offset. Off on low quality and when nothing is close.
- `game.js:_scorchFires` — an authored scorch decal is stamped under every fire at load and after every
  `decals.clear()`, so the flames no longer sit on clean ground.
- Not mine: the flame flipbook, spawn rate and smoke column (`particles.js`, #12a/d) — the particle
  stream's `_syncFog` already landed, so the fog-mismatch part of #12e is closed.

## #23 anti-aliasing — **fixed**

- `renderer.js:_samplesFor` / `setSamples` — the composer's HDR target now gets MSAA on WebGL2:
  `4` on high, `2` on medium, `0` on low, re-allocated live when the quality setting changes. SMAA is
  kept on top for the remaining specular aliasing.

## #24 ambient embers/ash indoors — **fixed**

- `game.js:_ambientParticles` (new) — gated on `map.isIndoors(camera.position)` (new helper in `map.js`
  using the zone boxes). Outdoors: embers are now born **at the fires** (nearest ones, ≤40 m) and drift,
  not sprayed in a 24 m box around the player's head; ash still falls. Indoors and in the bunker: no ash,
  no embers - a slow interior mote pool instead (`fx.dustMotes`, when the particle stream lands it).
  **Repair:** there is deliberately **no indoor fallback** any more. `Particles.ash()` spawns at an
  *absolute* world `y` of 2-9 m and ignores the centre it is handed, so the old `fx.ash(center, 3.2)`
  fallback was born above the ceiling - outside the room entirely in the bunker (floor ~ -2.5 m) and
  raining down through the ceiling in the houses, which is precisely the artifact #24 reports. Until
  `fx.dustMotes` exists, indoors gets no ambient particles at all. The outdoor ember fallback also
  dropped its pointless `.setY()` (`embersAround` picks its own height band).
- Fire particle spawns are also distance-throttled beyond 60 m.

## #25 fog inside buildings — **fixed**

- `game.js:ZONE_MOOD` + `_updatePlaying` — density, colour, exposure, hemi and env intensity are all
  lerped per zone: `density [0.008, 0.003, 0.002]` and the colour cools from `(0.18,0.13,0.12)` outdoors
  to `(0.075,0.075,0.085)` in the bunker, so interiors read darker and contrastier rather than hazier.
  Dog rounds only thicken the *street* fog (×2.6) — the bunker no longer fills with mist.
- `_updateMenuCamera` unwinds the interior grade (exposure/fog) when you quit to the menu from inside.

## #26 sky: stars / dither / cloud readability — **fixed**

- `sky.js:skyFrag` — a twinkling star field above `h > 0.25`, masked out toward the sun and by the smog
  band; a per-pixel noise dither before output; clouds rebuilt as two layers (slow macro shape + finer
  detail) with the horizon projection squashed so it stops smearing into radial streaks, and contrast
  raised to `smoothstep(0.30, 0.62, …)` so the layer actually reads.
- `renderer.js` GradeShader — an 8-bit output dither (`1.6/255`) kills the residual gradient banding that
  the luma-attenuated film grain could not.
- #26d crepuscular rays: implemented in the grade pass (14-tap radial accumulation of bright pixels
  toward the sun, so buildings, poles and the horde occlude them for free) and driven from
  `game.js:_updateGodRays` — projected sun position, faded by how far off-axis you are looking, off
  indoors and off on low quality.

## #30 GTAO outdoors — **fixed**

- `renderer.js` — `radius: 1.1, distanceExponent: 1.8, thickness: 0.6, samples: 16` (was
  `0.6 / 1.5 / 1.2 / 12`), with `samples` dropped to 10 on medium and the pass disabled on low.
- The "baked contact discs under large props" half of the fix is a map-GLB change (not my files).

## Audio: `round_bed_loop` - **fixed**

- `game.js:_startRound` -> `_ensureRoundBed()` starts the bed on the first round and keeps the handle;
  `_endRound` drops `bedLevel` to 40 % of it between rounds and `_startRound` brings it back.
- **Repair 1 - the level was being thrown away.** `Handle.setVolume(v)` computes `v * baseVolume`
  where `baseVolume` is the registry gain, so it *scales*, it does not replace: the old
  `setVolume(1, 2.5)` right after `loop(..., { volume: 0.25 })` ramped the bed to full gain. Every
  level change now goes through `_bedTo(level, fade)`, which passes the real target (`BED_VOL = 0.25`
  in round, `0.1` between rounds) and remembers where the bed was last ramped to.
- **Repair 2 - an unready buffer used to silence the bed for the whole run.** `audio.loop()` returns
  the *truthy* `NULL_HANDLE` while a buffer is missing, and `round_bed_loop` is a music track, which
  the engine renders in its deferred pass - so round 1 can easily ask too early. `_ensureRoundBed()`
  only stores a handle whose `isPlaying` is true, and `_updateRoundBed()` retries once a second until
  one comes back. (`heartbeat_loop` had the same trap and is now guarded the same way.)
- **Repair 3 - the "it goes through the duck bus" claim was wrong.** `MUSIC.round_bed_loop` declares
  `bus: 'music'`, and `audio.js:_buildGraph` wires `buses.music` straight to `postComp`, deliberately
  bypassing `duckGain` - `audio.duck()` never touched the bed. `_updateRoundBed()` now *follows* the
  engine's own duck state (`_duckUntil` / `_duckAmount`, read-only, absent -> no duck) and rides the
  bed down to `BED_DUCK = 40 %` of its level under a full duck. That covers the AUTO_DUCK stingers
  (powerups, insta-kill, hellround start) as well as the explicit round-start/round-end ducks,
  without a parallel set of timers to keep in sync. No playback-rate tricks anywhere.
- `_stopAmbientBeds()` stops it (and the heartbeat) on game over, and `update()` stops it whenever the
  state leaves `playing`/`dying` - which covers quit-to-menu, since `main.js` sets `game.state`
  directly and is not a file I own.
- Unknown sound names are silent no-ops, so this is safe before the audio stream lands the asset.
- Verified headless by driving the real `_ensureRoundBed` / `_bedTo` / `_updateRoundBed` source
  against a fake engine: silent-buffer -> no latch and no spurious starts, ready -> exactly one start
  at 0.25, half duck -> 0.175, full duck -> 0.10, release -> 0.25, intermission -> 0.10.

## Also fixed this round (perf, from the verifier's notes)

- `game.js:_updateGodRays` + `renderer.js` GradeShader - the god-ray strength approached zero
  asymptotically while the shader gate sat at `0.001`, so the 14-tap radial gather kept running for
  ~3 s after you looked away. The fade now snaps to 0 below `0.006` and the gate is `0.005`.

---

## Needs from other streams

1. **weapons stream** (`viewmodel.js` / `weapons.js`) — #4b: give the viewmodel scene its own dim muzzle
   flash light (intensity ≤ 3, distance ≤ 1.2) instead of inheriting world values, and drop the PaP
   `totalEmissiveRadiance += cm * cm * 2.2` a little. The post-order fix stops the white ghost, but the
   gun can still be over-exposed before bloom is even involved.
2. **interactables stream** (`interactables.js`) — #1b/c: drop the `Math.max(3, base)` emissive clamp and
   move the perk `PointLight(col, 9, 5)` to `(col, 2.2, 3.2)` at `+0.45` forward / `+1.55` up. My bloom
   threshold assumes emissives are authored, not clamped. Also #22: `emissiveIntensity: 0` on the
   wall-buy chalk (it currently glows under the perk lights).
3. **particles stream** (`particles.js`) — two optional APIs I call through feature detection, with
   fallbacks in place today:
   - `fx.emberDrift(pos, scale)` — embers rising off a fire with wind drift (I currently fall back to
     `embersAround(firePos, 1.1)`).
   - `fx.dustMotes(center, radius)` - tiny near-static interior motes for rooms/bunker. **This one is
     now load-bearing:** interiors get *no* ambient particles until it exists, because `ash()` spawns
     at an absolute world y of 2-9 m regardless of the centre it is given and therefore cannot be
     used indoors. Either add `dustMotes`, or make `ash()` honour `center.y`.
4. **decals stream** (`decals.js`) — the scorch ring buffer is only 30 entries, so the 9 fire scorch marks
   I stamp get recycled by grenade/ray scorches during a long game. A separate static-decal set (#8's
   `staticDecal()` API) would keep authored dressing from being evicted by gameplay.
5. **blender:map stream** — `MK_LIGHT_*` markers are now consumed if present (`extras.color`,
   `extras.intensity`, `extras.range`); when any exist they replace my procedural fill rig entirely.
   Also: the perk `<perkId>_sign_glow` / `<perkId>_trim_glow` split is already handled by name.
6. **zombies stream** — if you want the horde to fog exactly like the world does under the new
   sun-directional haze, call `applyAerialPerspective(material)` from `sky.js` on the zombie materials
   (safe, idempotent, no-op when `material.fog === false`).

## Known limitations

- The bunker lamp and the big fire use **baked** (non-auto-updating) shadow cube maps: moving zombies do
  not cast from them. This is the deliberate trade for not paying 12 extra scene passes per frame on a
  laptop that overheats. The bunker map is re-baked when the power state changes.
- The heat haze is a post-process UV offset with no depth test, so a fire very close to the camera also
  shimmers whatever is drawn in front of it (including the gun). Strength falls off past 3.5 m and is
  zero past 16 m, which keeps it out of the way in practice.
