# Fix log — stream `zombies-code`

Files owned/changed: `src/ai/zombies.js`, `src/fx/particles.js`, `src/fx/decals.js`.
`npx vite build --logLevel error` passes (exit 0). No dev server or browser was started.

> **Revision 2 (repair round).** The first version of this log said the crawler and
> directional-death paths were dormant because the GLB lacked the clips. **That was
> wrong** — `public/models/zombie.glb` was re-exported after it was written. See
> "Asset status" immediately below; everything in #4, #5 and #20 is live.

## Asset status (verified by parsing the GLB JSON chunk, not assumed)

`public/models/zombie.glb` (rebuilt 19:41) ships:

* clips: `attack, attack_L, attack_R, climb, crawl, crawl_attack, death_1, death_2,
  death_back, death_front, death_left, death_right, hit, idle, rise, run, sprint,
  tear, to_crawl, walk` — so **`get crawlersSupported` is `true`** and
  `_pickDeath()` picks from the real directional set.
* meshes: `body_A` (5 prims: zombie_skin / **zombie_gore** / cloth_A_shirt /
  cloth_A_leather / cloth_A_slacks), `head_A` (5 prims incl. **`hair_A`** as its own
  primitive), `eyes_A`, **`legs_A`** (4 prims). So `_hideLegs()` takes the mesh branch
  (not the bone-scale fallback), the gore stump cap is present on the torso, and the
  20% bald variant is possible.
* only variant **A** exists, so per-instance variety currently comes from tint, scale,
  mirror, shoulder offset, stains and the bald roll — not from B/C bodies.

`public/models/hellhound.glb` has `attack, death, idle, run` and an `eye_glow`
material, so the #17 burn-out path is live too.

Consequences that were re-checked line by line this round, since these paths had
never been exercised under a correct assumption:

* `damage()` returns `false` (not a kill) when a hit makes a crawler. Both call sites
  handle that correctly — `weapons.js:739` and `game.js:574` both do
  `if (killed) …; else g.addPoints(POINTS.hit)`, so the player gets hit points.
* Insta-Kill / the nuke no longer get downgraded to a maiming: `_tryCrawler()` now
  bails on `amount >= 1e8` or `info.nuke`.
* A zombie converted mid-`tear` no longer strands its window (see #4 below).
* A spawn-as-crawler that comes up through `mode: 'rise'` now chains
  `rise → to_crawl → crawl` instead of snapping from a standing rise into a crawl.
* Crawlers get a forward face-plant death, a floor-level tear animation, and their
  step sound off the hands rather than hidden feet.

The big structural change is in `ZombieManager._build()`: **every zombie instance now owns its
materials**. `SkeletonUtils.clone` shares material references, which is why eye glow, skin tone,
wound decals and the corpse fade were all previously impossible per-zombie. Each clone is run
through `enhanceZombieMaterial()`, which injects one shared shader variant (pinned with
`customProgramCacheKey`, so all zombies still compile to a single program):

* a cool fresnel rim term (modest — the lighting stream's `rim` directional does the heavy lifting)
* fog at 80% of the world rate (the lighting stream already dropped density `0.012 → 0.008`, so this
  is only a small extra separation, not a second full compensation)
* up to 4 **bind-space wound blobs** (`uWounds[4]`) — world hit points are converted to the
  skeleton's bind space via `p_bind = bindMatrix⁻¹ · restWorld_i · boneWorld_i⁻¹ · P`, so a wound
  decal rides the skin through every animation for free
* `diffuseColor.a = opacity`, so the instance can stay permanently `transparent` (the corpse fade
  never flips the `OPAQUE` define, i.e. never triggers a mid-fight shader recompile) without a baked
  texture's alpha channel punching holes in the body

---

## zombies.md #2 — eye glow / unison flicker — **fixed (code part)**

* `_build()` — eye materials are cloned per zombie, clamped **down** to `emissiveIntensity = 2.2`,
  `emissive.setRGB(1.0, 0.34, 0.05)`, `toneMapped = true`. They are collected into `z.eyeMats`.
* `spawn()` — `z.eyePhase = rand*2π`, `z.eyeRate = 5..11`.
* `_eyes(z, dt, time)` (new, called per zombie from `update()`) —
  `1.8 + sin(time*rate + phase)*0.45`, `+2.7` for 0.15 s on damage (`z.eyeSpike`, set in `damage()`),
  `+1.6` while `state === 'attack'`, and fading to 0 over 1.2 s once dead.
* The global `const flick = 5 + sin(time*9)*0.6` loop over `this.eyeMats` in `update()` is **gone**.
  `this.eyeMats` still exists (and is still populated) so nothing that referenced it breaks.
* **Repair round:** `eye_glow` is `alphaMode: OPAQUE` in both GLBs and is deliberately routed
  around `enhanceZombieMaterial()`, so it never got `transparent = true` and `_setOpacity()` was a
  no-op on it — the body dissolved during the 8→9.5 s corpse fade (and the hellhound's 1.5→2.15 s
  burn-out) while the eye quads stayed solid and popped out of existence at removal. `_build()`
  now sets `transparent / depthWrite / opacity` on the eye clone too, so the eyes fade with the
  body. (Both eye and body materials are transparent with `depthWrite: true`, so draw order
  between them is still resolved by the depth test.)

## #3 — lockstep horde — **fixed**

* `spawn()` — `z.phase`, `z.rateJitter = 0.82..1.18`, `z.attackDelay = 0..0.25`.
* `_play()` — a looping action starts at `z.phase * clip.duration`.
* `_syncGait()` — clamp widened to `0.45..1.9` and multiplied by `z.rateJitter`.
* `_chase()` — the chase→attack transition is held for `z.attackDelay` (accumulated in `z.attackT`),
  so a pack does not swing on one frame. Attack grunt is also pitch-jittered.

## #4 — crawlers — **fixed, and LIVE (the GLB ships the whole set)**

* `get crawlersSupported()` — true only when `zombie.glb` carries `crawl` **and** `to_crawl`.
  **It does**, so every path below runs in the shipped build.
* `_tryCrawler(z, info, amount)` — called from `damage()` *instead of* `kill()` when health hits 0:
  80% for a `limb` hit below `z.pos.y + 0.95`, 55%/35% for an explosive (low/high). Health is
  restored to 30% of max and `damage()` returns `false`, so the shooter gets hit points, not a kill.
* `_becomeCrawler()` — hides the legs, plays `to_crawl` (new `'toCrawl'` state → `_toCrawl()`), then
  `crawl`. Gore: two leg-position `fx.gibBurst` calls + a big `fx.blood`, a 1.1 m ground pool,
  `zombie_gib` and a pitched-down `zombie_scream`.
* `_hideLegs()` — hides the contract's `legs_A/B/C` meshes when present (revealing the stump cap
  baked into `body_X`); **falls back** to scaling `shin_*`/`foot_*` bones to 0.001 when they are not.
  `_restoreLimbs()` undoes both on recycle.
* Speed `ZOMBIE.walkSpeed * 0.85`; `_gaitClip()` → `crawl`; `_attackClip()` → `crawl_attack` when the
  clip exists; `_collide()` uses a low capsule (`y+0.18 … y+0.55`, r 0.3); `_hitboxes()` drops the leg
  capsules and the placeholder boxes are lowered; `_separate()`/`_blockPlayer()` use a 0.5 m radius;
  `raycast()`'s coarse sphere is re-centred at `y+0.35`.
* Spawn-as-crawler: from round 8, `min(0.14, 0.02 + (round-8)*0.012)` chance (silent — no gore burst).

Added this round, now that the path is known to be live:

* `_tryCrawler()` bails on `amount >= 1e8` (Insta-Kill) and `info.nuke`, which used to be
  downgraded from a kill to a maiming.
* **Barrier hand-off.** A zombie cut down while tearing used to become a crawler with `z.barrier`
  still set and the barrier's `climber` slot still pointing at it. `_becomeCrawler()` now releases
  the `climber` slot and clears `tearing / swipe / tornThis`, and `_toCrawl()` returns to
  `'toBarrier'` (not `'chase'`) when a barrier is still assigned — so it crawls back to the same
  window instead of being stranded outside the building with nothing to path to.
* **Rise → crawl.** `_rise()` chains into `'toCrawl'` when `z.crawler` is already set, so a
  spawn-as-crawler comes out of the ground and collapses onto its stumps instead of snapping
  from a standing rise straight into a crawl cycle.
* `_pickDeath()` returns `death_front` for a crawler — the standing side/back falls read as a
  teleport from a floor pose.
* `_tear()` uses `crawl` in place of `idle` and `crawl_attack` in place of `tear` for crawlers, so
  a crawler claws at the boards from the floor instead of standing up to do it.
* `_feet()` takes a crawler's step contacts off `hand_L/R` (threshold 0.3 m) instead of the hidden
  feet.

## #5 — directional deaths / corpses melting through the floor — **fixed (code part)**

* `_pickDeath(z, info)` — uses `z.deathDir` (previously computed and never read). The shot's travel
  direction relative to the zombie's facing picks `death_front` (<45°, i.e. shot in the back),
  `death_back` (>135°), `death_left`/`death_right` in between; a headshot biases to `death_back`.
  When the directional set is absent it falls back to `death_1`/`death_2` **and yaws the body** so the
  plank fall at least goes away from the shooter.
* `_applyKnockback()` — a linearly-decaying horizontal impulse over 0.35 s, integrated in `_dead()`:
  1.0 m explosive, 0.85 m shotgun (`olympia`/`remington870`), 0.25 m rifle, 0.18 m pistol/revolver,
  0.12 m knife, 0.05 m headshot. The body stays on the ground height while it slides.
* `_dead()` — **no sink for 8 s**, then opacity `1 → 0` over 1.5 s with a 0.1 m/s settle, removed at
  9.5 s (was: sinking at 0.35 m/s from 3.2 s, gone at 5.5 s).
* `_capCorpses()` — at most `maxCorpses = 8` bodies; older ones are pushed straight into their fade.
* `zombie_bodyfall` fires at half the death clip (capped at 0.75 s).

## #5 — directional deaths — note

All four of `death_front/back/left/right` ship in the GLB, so `_pickDeath()` uses the real
directional set (the mapping was checked against `zombie_anim.py`'s clip builders). Nothing was
changed here this round beyond the crawler case above.

## #6 — gibs — **fixed (code part)**

* `_popHead(z, dir)` — on top of the (already enlarged) `fx.headPop`, spawns 8 physical
  `fx.gibBurst` chunks with bone shards, an `onLand` callback that paints a blood decal where the
  first chunk lands, `zombie_gib`, and `z.spray = 0.6` which drives `fx.arterialSpray` from the stump
  every frame in `update()`.
* `_popLimb(z, side, dir)` — zeroes the `forearm_*`/`hand_*` bone scale (re-applied every frame in
  `_postPose` via `z.lostLimbs`), spawns 6 bone-flecked chunks + a 3.0-amount blood burst, adds a
  large wound decal at the stump, plays `zombie_gib`.
* **Repair round — the limb that comes off is now the limb that was hit.** `kill()` used to call
  `this._popLimb(z, Math.random() < 0.5 ? 'L' : 'R', info.dir)`, so a point-blank blast to the
  right arm could tear off the left one. New `_hitLimb(z, info)` resolves *side* **and** *arm vs
  leg* by testing `info.point` against the posed `forearm/hand/upperarm` and `shin/foot/thigh`
  bones (30 cm acceptance radius), and honours `info.limb` / `info.side` if `weapons.js` ever
  forwards them. `kill()` now:
  * never pops the head on a `part: 'limb'` hit;
  * calls new `_popLegs(z, dir)` when the killing gib hit resolved to a **leg** — both legs come
    off at the hip (reusing `_hideLegs()`, so the gore stump cap shows and `_restoreLimbs()`
    cleans up), 9 + 2×4 bone chunks, a 3.4 blood burst, a 1.2 m ground pool and `zombie_gib`;
  * otherwise pops the arm on the resolved side — guaranteed on a limb hit, 50% otherwise
    (an explosion genuinely has no side, so that case still rolls).
* **Detached head.** Still not a cloned `head_X` rigid body, but no longer only a spray: new
  `Particles.skullChunk()` throws **one heavy 0.17 m bone-material chunk** with damped spin and a
  9 s life out of the existing pooled `GibPool` (no mid-fight allocation), so the decapitation has
  a single object the eye can follow out of the mist and watch come to rest.

## #10 — zombies vanish into the background — **fixed (code part)**

* `envMapIntensity` raised `0.5 → 1.15` on zombie materials only (the map keeps 0.5).
* Fresnel rim + 80% fog in the injected shader (above). Deliberately *not* using
  `sky.applyAerialPerspective()` — that patches the same fog chunk and the two would collide.
* The `rim` directional and the fog density drop were done by `lighting-post`.

## #13 — zombies never look at the player — **fixed**

* `_lookAtPlayer()` + `_biasBone()`, called from `_postPose()` after `mixer.update`. Clamped to
  ±55° yaw / ±25° pitch, damped at 4/s, split 30% neck / 70% head, released over 22 m, suppressed
  while dead or during `dogSpawn`.
* The rotation is applied **in the bone's parent space** (`bone.quaternion.premultiply` about a world
  axis mapped through `parent.getWorldQuaternion().invert()`), so it does not care which way the
  rig's local bone axes point. Mirrored instances (see #20) are corrected by negating the axis' x and
  the angle, because `Matrix4.decompose()` folds a -X flip into `scale.x`.

## #14 — rise dirt timing — **fixed (code part)**

* `_rise()` fires three extra staggered `dirtBurst` calls at 22% / 45% / 72% of the rise on top of
  the spawn burst (`z.riseFx` gate, reset when `respawnStuck()` re-enters the state), so soil keeps
  moving until the body is out. Counts inside `dirtBurst` were already doubled.
* `decals.js` — new `dirtPatch(pos, normal, size)` decal set (48-deep ring buffer, 256² texture:
  dark soil gradient + ~90 clods + a cracked rim) laid down at the spawn point.
* **Repair round — it fades now.** `DecalSet` takes an optional `fade: { hold, over, floor }`;
  the dirt set uses `{ hold: 8, over: 6, floor: 0.3 }`, i.e. full strength for 8 s (what the review
  asked), then a 6 s fade down to a faint 30% residue rather than a hard disappearance in front of
  the player. Per-instance age rides on `instanceColor` (three multiplies it into
  `diffuseColor.rgb`); one injected line moves that factor onto the alpha and divides it back out
  of the rgb, so the colour is untouched. It is driven from the mesh's own `onBeforeRender`, so it
  needs no `update()` call from `game.js` (which this stream does not own), touches at most 48
  floats a frame and allocates nothing. `DecalSet.add()` also stopped allocating a `Quaternion`
  and a `Vector3` per decal.

## #17 — hellhound death is an explosion — **fixed**

* `kill()` for `kind === 'dog'` — no more `fx.explosion` and no more `explosion` SFX. It plays the
  `death` clip, bursts 34 embers + an ash puff, and drops a 1.5 m scorch decal.
* `_dead()` — ramps `fx.fire` up over 0.9 s and back down over 0.9 s (2 sources/frame) with
  intermittent ash, then fades the body out over 0.6 s from t=1.5 s and removes it at 2.15 s.
* Audio: `hellhound_death` when `audio.has?.()` reports it, otherwise `hellhound_growl` at rate 0.55.

## #18 — directional hit flinch — **fixed**

* `damage()` stores `z.flinchDir = wrapPi(atan2(dir.x, dir.z) - z.yaw)` and `z.hitch = 0.08`.
* `_postPose()` rotates the chest away from the shot on both axes (`-cos(a)` on X, `+sin(a)` on Z)
  with a sharper opposite head counter-rotation, instead of the fixed `z.id % 2` shape.
* `update()` drops `mixer.timeScale` to 0.3 for the 0.08 s hitch (never while dead).
* **Repair round — the additive pose block is now gated on `z.real`.** The flinch, the head
  counter-rotation and the per-instance shoulder offset are all `rotateX/rotateZ`, i.e. *additive*
  on top of the sampled pose. That is only safe because the mixer rewrites those quaternions every
  frame (confirmed: all 20 clips carry `upperarm_L/R`, `chest` and `head` rotation channels). On
  the **placeholder** path (`zombie.glb` failed to load) there is no mixer — `_placeholderAnim()`
  only writes `rotation.x` on a few nodes — so `upperarm_*.rotateZ(z.shoulder*)` integrated
  without bound (~6 rad/s at 60 fps: spinning arms) and the placeholder head drifted a little with
  every hit. `_postPose()` now runs that whole block only `if (z.real)`. The `z.lostLimbs` scale
  reset stays outside the gate because it is an absolute `setScalar`, not additive.

## #20 — per-instance dressing — **fixed (within what variant A can give)**

* Done: per-instance **material clones**; hue ±0.037 / saturation ×0.8–1.25 / value ×0.84–1.06 tint
  (baked white-albedo slots get a faint warm cast instead of nothing, which is where the skin bake
  lands); scale widened to `0.90–1.07`; random ±6° `upperarm_L/R` rest offset applied every frame;
  **mirror-scale X on 40% of instances** for a free second silhouette per variant (three handles the
  negative determinant via `frontFaceCW`; the look-at maths is corrected for it).
* Done: 0–2 random pre-existing blood stains seeded at random bone rest positions (`_seedStains`).
* **Done this round: the 20% bald variant.** The earlier claim that hair is joined into `head_V`
  was wrong — `hair_A` is its own material and its own primitive inside the 5-primitive `head_A`
  mesh, which `GLTFLoader` gives us as a separately hideable child mesh. `_build()` collects any
  mesh carrying a `/hair|helmet|scalp/i` material into `z.hairMeshes`; `spawn()` rolls `z.bald` at
  20% and hides them *after* the variant-visibility pass (so the two do not fight, and a
  non-bald respawn gets the hair back).
* **Remaining ceiling:** the shipped GLB only contains variant **A** (`body_A/head_A/eyes_A/
  legs_A`), so there is one body at runtime. Everything above is silhouette/colour variation on
  that one body; real variety still needs B and C from the character stream.

## #21 — blood FX too small, no wound decals — **fixed**

* `particles.js` `blood()` is now 18 droplets/amount (was 6) + heavy arcing gouts + a dark red mist
  puff + a stretched arterial streak for big hits; `arterialSpray()` and a much larger `headPop()`
  (46 chunks + two mist balls) were added.
* `zombies.js damage()` — amount scaled by part (1.6 head / 1.25 neck / 1.0 body / 0.85 limb), ground
  splat chance 0.35 → 0.6, positional `impact_flesh`.
* Wound decals on the body: **done**, via the bind-space `uWounds` slots described at the top. Every
  non-burn hit stamps one (radius 0.05–0.115), limb loss stamps a 0.12 one; slots are ring-buffered
  per zombie and cleared on spawn.

## #22 — `rise`/`climb` fall back to the wrong clips — **fixed**

* The fallback table is now the module-level `CLIP_FALLBACK` (extended with the crawl and directional
  death entries) and `_play()` logs a one-time `console.warn` per `kind:clip` naming the substitute
  and telling you to re-export. `_clipDuration()` uses the same table so timings follow the fallback.

## Audio hooks (new sound-name contract)

* `zombie_footstep` — `_feet()`, from actual `foot_L/R` bone contact (crossing below `pos.y + 0.14`
  while descending), throttled to 0.16 s, only while moving and within 15 m; quieter for crawlers.
* `hellhound_footstep` — speed-driven stride timer, same 15 m gate.
* `zombie_bodyfall` — `_dead()`, at half the death clip.
* `zombie_gib` — `_popHead()`, `_popLimb()`, `_becomeCrawler()`.
* `impact_flesh` — `damage()`, positional at the hit point (70% of hits).
* `hellhound_death` — `kill()`, behind `audio.has?.()` with a pitched-down growl fallback.
* No playback-rate tricks are used to shorten anything.

## environment.md #12(e) — particle fog mismatch — **fixed**

`particles.js` — `uFogDensity` is now a uniform (was a hard-coded `0.0004` in the vertex shader) and
`Particles._syncFog()` copies `scene.fog.color` and `density²` into both pools every frame, so smoke
and blood fog at exactly the world rate and hue even as `game.js` lerps density between zones.

---

## Repair-round summary (all four verifier blockers)

| verifier blocker | outcome |
| --- | --- |
| stale risk assessment (GLB rebuilt after the log) | **corrected** — see "Asset status"; crawler/directional-death/bald paths re-audited and hardened |
| eye materials never fade with the corpse | **fixed** — `_build()` makes the eye clone transparent |
| placeholder zombies' arms spin | **fixed** — additive pose block gated on `z.real` in `_postPose()` |
| `_popLimb` picks a random side | **fixed** — `_hitLimb()` resolves side + arm/leg from the hit point; new `_popLegs()` |

Also this round: `_tryCrawler()` respects Insta-Kill/nuke; crawler barrier hand-off; rise→crawl
chain; crawler death/tear/footstep clips; `skullChunk()`; the 20% bald variant; a fading dirt
patch; and the unreachable `z.dogBurst` branch removed.

---

## Left / not done

* **#6 — a true detached head mesh.** `skullChunk()` throws a pooled skull-sized bone chunk, which
  reads correctly, but it is not a cloned `head_A` group tumbling with the face on it. Doing that
  properly wants a small pool of loose head meshes built once at load (the head is 5 primitives, so
  cloning per pop would allocate mid-fight).
* **#20 — only variant A exists in the GLB**, so per-instance variety is limited to tint, scale,
  mirror, shoulder offset, stains and the bald roll. Needs `body_B/C` from the character stream.
* **Crawlers still climb barriers** using the standing `climb` clip. Acceptable (BO2 crawlers do
  come through windows) but it will look odd until there is a crawl-climb clip.
* **No wound decal on the placeholder rig** — `_addWound()` requires a skinned mesh, so the
  GLB-failed-to-load path has no wounds or stains. Degraded fallback, by design.

## Needs from other streams

1. **`src/player/weapons.js`** (weapons stream): `ZombieManager.raycast()` returns a `limb` field
   (`'arm' | 'leg'`) on each hit. `weapons.js:426` builds `e = { dmg, part, point, dir }` and
   `:451` passes that to `zombies.damage()`. Forwarding `limb: h.limb` (and a `side` if you add
   one) would make leg shots deterministically create crawlers and make limb gibs exact.
   *Not blocking any more:* `_tryCrawler()` falls back to a height heuristic and `_hitLimb()` now
   resolves side and arm-vs-leg from `info.point` against the posed skeleton, so both work today.
2. **`src/player/weapons.js`**: `info.weapon` is already the weapon id, which `_applyKnockback()`
   reads for shotgun knockback. No change needed — just don't rename the ids `olympia` /
   `remington870`.
3. ~~export hair as a separate node~~ — **already satisfied**: `hair_A` ships as its own primitive.
4. ~~ship `crawl`/`to_crawl`/`legs_A`/directional deaths~~ — **already satisfied** (verified in the
   19:41 `zombie.glb`). What is still missing from the contract: `legs_B`/`legs_C` and `body_B/C`,
   `head_B/C`, `eyes_B/C` (only variant A exists), and a crawl-specific climb.
5. **`src/game/game.js`**: `explode()` passes `part: 'body'` and a point at `z.pos.y + 1`, so an
   explosion at a zombie's feet reads as a high hit and takes the lower 35% crawler chance instead
   of 55%, and `_hitLimb()` can't resolve a side for it. Passing the actual blast centre height
   (or `part: 'limb'` when the blast is below the hips) would make grenade-made crawlers and
   grenade-torn limbs land the way BO2's do. Cosmetic, not blocking.
6. **`src/audio/*`** (audio stream): the new names used here are `zombie_footstep`,
   `hellhound_footstep`, `zombie_bodyfall`, `zombie_gib`, `hellhound_death`, `impact_flesh`.
   `hellhound_death` and `impact_flesh` are confirmed present; the rest are silent no-ops if
   missing (`playAt` returns `NULL_HANDLE` for unknown names), so ordering is fine.
