# Art-direction review — zombies & hellhounds

**Bar:** "the zombies look realistic like they did in original BO2" (Treyarch gritty realism: individual human
faces and proportions, thick period clothing with real seams and volume, decayed skin with actual open wounds
and exposed bone, heavy asymmetric lurching, crawlers, dramatic knockback deaths, gibs).

## Verdict

They do not meet the bar, and the gap is not a polish gap — it is a category gap. What is on screen right now
is a *stylised cartoon zombie*: a smooth mannequin with a permanently grinning row of cube teeth, two
blown-out white headlamp eyes, a paper-thin shirt with a hard cut hem, and no blood or wounds anywhere on the
body despite the material script claiming to paint them. `03_zombie_variants_ABC_front.jpg` and
`04_zombie_faces_closeup.jpg` read closer to a Halloween-decoration mask or a *Plants vs. Zombies* silhouette
than to a Treyarch zombie; the fixed ear-to-ear grin in particular is the single most damaging read, because
BO2 zombies never smile — their lips have *receded*, which is a completely different shape. In motion it is
worse: `01`, `02` and `19` all show a pack of three-to-five zombies walking at the *identical* stride phase
with the *identical* frozen T-rex claw arm pose, which instantly reads as cloned NPCs rather than a horde.
There are no crawlers at all (the word "crawl" does not appear anywhere in `src/` or the build scripts),
deaths are one stiff 1.5 s plank fall followed by the corpse sinking through the floor, and a headshot simply
switches the head mesh off with no stump, no flying head and no gibs. The hellhound is the weakest asset in
the game: `hound_side.png` is a lava-cracked giraffe — body far too long, legs stick-thin and far too tall,
head too small, tail a wire, no fur, no ruff, no muscle — and the Voronoi magma-crack overlay reads as a
generic "rock elemental", not a burned dog. The animation *code* underneath is genuinely good (asymmetric
limps, looping noise, per-limb styles in `zombie_anim.py`), which makes it more frustrating that the pose
amplitudes and the game-side playback throw nearly all of that away.

---

## Top 10 by impact

### 1. The face is a flat mask with a permanent cartoon grin and cube teeth — `[blender:characters]` — L

**What's wrong.** `renders/characters/zombie_A_head.png` and `zombie_B_head.png` at close range, and
`04_zombie_faces_closeup.jpg` in game: the mouth is a single fixed ear-to-ear opening with a straight arc of
individually visible box-shaped teeth and a painted bright-red lower lip. There is no gum line, no separation
between upper and lower dental arcades, no tongue, no visible mouth cavity depth. The cheeks are convex and
full, the jaw is a smooth undifferentiated slab, and the nose is a tiny soft bump with no nostrils, no alar
crease and no septum shadow. `zombie_mesh.py` *does* build a brow ridge (l.309), nose tube (l.322), ears
(l.329) and sculpts eye sockets (l.339) — but the amplitudes are ~0.01–0.04 m blobs on a 0.19 m head, so they
are invisible at any distance and read as a mask at close range. All three variants share one head base with
only hair/helmet swapped: A, B and C have the *same* face (compare `zombie_A_head.png` to `zombie_B_head.png`).

**Why it matters.** The face is the whole read. BO2 zombies are recognisably individual dead *people* —
sunken temples, hollow cheeks over visible zygomatic arches, receded lips exposing teeth *and gums*, one torn
cheek showing molars through the side of the face, milky irises. A symmetrical grin is the single strongest
"cartoon" signal in the current build and it is on every zombie in every frame.

**Fix.** In `tools/blender/characters/zombie_mesh.py`:
- `sculpt_head()`: deepen the negative blobs. Eye socket from `-0.0185` to `-0.032` and widen the ellipse to
  `(1.45, 1.1, 1.0)`; add a new temple hollow at `(±0.058, -0.012, 1.735)` r 0.032 amount `-0.020`; add a
  cheek hollow under the zygomatic at `(±0.048, -0.042, 1.665)` r 0.030 amount `-0.024`.
- Replace the single mouth opening with a **lip recession**: raise the upper lip band and drop the lower one
  so ~3 mm of gum shows above and below the teeth, then round the dental arc — `_tooth_arc()` (l.379) should
  place teeth on an elliptical arc with per-tooth random yaw ±6° and random inward offset 0–1.5 mm, and 2–3
  teeth per head should be *deleted* (seeded by variant) so the smile is broken.
- Add a per-variant face-shape pass so A/B/C differ: drive `sculpt_head` from a `seed` argument that offsets
  the brow, nose length, jaw width and chin projection by ±15%.
- Add one asymmetric facial wound per variant: a torn-cheek hole on A (cut a 0.018 m hole through the cheek at
  `(0.050, -0.030, 1.655)` and cap it with `zombie_gore`), a missing-lower-jaw silhouette on C (delete the jaw
  parts below `z = 1.615` on one side), an exposed brow-bone gash on B.
- Give the teeth a real material split: `zombie_teeth` at `(0.215, 0.192, 0.125)` is currently too light and
  too uniform — drop to `(0.12, 0.105, 0.070)` with a per-tooth brown gradient toward the root, and add a
  `zombie_gum` material `(0.075, 0.020, 0.018)`.

---

### 2. Eyes are blown-out white headlamps, and every zombie in the level flickers in unison — `[both]` — S

**What's wrong.** `04_zombie_faces_closeup.jpg`: the eyes are pure-white saturated discs — the brightest
pixels on the model, brighter than the fires behind them — with no iris, no socket occlusion and no falloff.
In `03_zombie_variants_ABC_front.jpg` they're the only thing you can identify about the faces at 6 m.
`build_zombie.py` l.89 sets `emission=(1.0, 0.42, 0.06)` which is fine, but `src/ai/zombies.js` l.155 forces
`emissiveIntensity = Math.max(m.emissiveIntensity, 5)` and l.449–450 then drive **one shared material set**
(`this.eyeMats`) with a single global `5 + Math.sin(time * 9) * 0.6` — so every zombie on the map pulses at
exactly the same rate and phase, and none of them ever dims.

**Why it matters.** BO2's eye glow is a *dull* amber ember that you notice in shadow and barely see in
daylight. A white blowout kills the face shape underneath it (it is a large part of why issue #1 reads so
badly) and synchronised flicker is an immediate tell that these are instances of one object.

**Fix.**
- `src/ai/zombies.js` l.155: clamp down instead of up — `m.emissiveIntensity = 2.2`, and set
  `m.emissive.setRGB(1.0, 0.34, 0.05)` so it cannot drift white. Drop `m.toneMapped = true`.
- l.449–450: delete the global flicker. Instead, give each zombie its own eye material instance in `_build()`
  (`e.mesh.material = e.mesh.material.clone()`, stored on `z.eyeMat`) with `z.eyePhase = Math.random() * 6.28`
  and `z.eyeRate = 5 + Math.random() * 6`, then in `update()` per zombie:
  `z.eyeMat.emissiveIntensity = 1.8 + Math.sin(time * z.eyeRate + z.eyePhase) * 0.45`, and spike to 4.5 for
  0.15 s on `damage()` and while `state === 'attack'`.
- `zombie_mesh.py` `build_eyes()` (l.417): shrink the spheres from r `0.0118` to `0.0092` and push them
  2 mm deeper into the socket so the upper-lid shelf occludes the top of the glow.

---

### 3. The horde walks in perfect lockstep — `[code]` — S

**What's wrong.** `01_street_start_horde.jpg`, `02_zombies_backlit_group.jpg` and
`19_combat_mp5_firing_hud_perks_powerups.jpg` all show 3–5 zombies whose legs are at the same point in the
stride and whose arms are in the same pose. `spawn()` in `src/ai/zombies.js` never randomises the action
phase, and `_syncGait()` (l.594) sets `a.timeScale = clamp(speed / nominal, 0.5, 1.6)` from the *actual*
speed, which for zombies in the same gait is almost the same number — so they converge rather than diverge.
Per-zombie variation is a single uniform scale `0.92–1.14` (l.223) and nothing else.

**Why it matters.** This is the highest-impact *cheapest* fix in the list. A BO2 horde reads as a crowd
because every zombie is on its own clock. Right now the crowd reads as a chorus line, and it undoes even
well-authored animation.

**Fix.** In `src/ai/zombies.js`:
- `spawn()`: add `z.phase = Math.random()` and `z.rateJitter = 0.82 + Math.random() * 0.36`.
- `_play()`: after `a.reset()`, add `if (loop) a.time = z.phase * a.getClip().duration;`.
- `_syncGait()`: multiply the computed timeScale by `z.rateJitter` and widen the clamp to `0.45–1.9`.
- Also stagger the *decision* timing: `z.attackDelay = Math.random() * 0.25` added before the `_chase` →
  `attack` transition at l.608, so they don't all swing on the same frame.

---

### 4. There are no crawlers — `[both]` — L

**What's wrong.** `grep -rn "crawl"` over `src/` and `tools/blender/characters/` returns nothing. The GLB
clip list is `attack, climb, death_1, death_2, hit, idle, rise, run, sprint, tear, walk` — no crawl loop, no
crawl-attack, no leg-loss transition. Shooting a zombie's legs (hitbox `part: 'limb'`, l.301) does nothing
distinct.

**Why it matters.** The crawler is one of the two or three things people picture when they hear "BO2
zombies" — the grenade that leaves three of them dragging themselves at you, the round you can't end because
one crawler is stuck behind a car. Its absence is felt more than any texture detail.

**Fix.**
- `[blender:characters]` `zombie_anim.py`: add `crawl` (loop, ~0.8 m/s, alternating forearm pulls with the
  torso dragging and the head swinging low), `crawl_attack` (one-arm forward swipe from prone, ~0.7 s) and
  `to_crawl` (a ~0.6 s transition from standing collapse to prone). Build a second body variant set or a
  shape-key/bone-scale trick that hides the shins — simplest is a `legless` flag in `build_zombie.py` that
  zeroes the `shin_*`/`foot_*`/`toe_*` bone scales and caps the thigh stumps with `zombie_gore`.
- `[code]` `src/ai/zombies.js`: on an explosive kill or a `limb`-part killing blow to the legs, instead of
  `kill()`, set `z.crawler = true`, play `to_crawl`, scale the leg bones to 0, set
  `z.speed = ZOMBIE.walkSpeed * 0.85`, lower the hitbox capsule to `y + 0.25`, and add a `crawl` branch to
  `_gaitClip()`. Restore ~30% health so it isn't instantly dead.

---

### 5. Deaths are one stiff plank fall, then the body sinks through the floor — `[both]` — M

**What's wrong.** `renders/characters/anim_death_1.png`: the zombie falls backward as a single rigid unit —
the spine, arms and legs all rotate together about the ankles, the arms make one symmetrical windmill, and it
lands flat with no settle, no limb flop, no head bounce. There are only two death clips (1.5 s and 1.6 s), so
in a group kill you see the same fall repeatedly. In `src/ai/zombies.js` `kill()` computes
`z.deathDir = info.dir ? Math.atan2(...)` (l.357) and **never uses it** — bullets from any direction produce
the same fall. Then `update()` l.423–425 sinks the corpse at 0.35 m/s and deletes it 5.5 s after death, so
bodies visibly melt through the tarmac in front of the player.

**Why it matters.** BO2 deaths sell the weapon. A shotgun blast throws the zombie backward and off its feet;
a headshot drops it like a sack straight down. Uniform, directionless, self-deleting deaths make every gun
feel the same and make the street feel like it has no memory of the fight.

**Fix.**
- `[blender:characters]` `zombie_anim.py`: add `death_3` (drop to knees then face-plant), `death_4` (spin and
  fall sideways) and `death_head` (instant boneless collapse straight down, for headshots). Add a settle tail
  to each — 0.4 s where the limbs keep moving after the torso stops.
- `[code]` `kill()`: use `z.deathDir`. Apply a decaying horizontal impulse to `z.pos` over the first 0.35 s
  (`0.8 m` for a shotgun at close range via `info.weapon`, `0.25 m` for a rifle, `0` for a headshot), and
  yaw `z.holder` to face away from the shot so the fall direction matches.
- Pick `death_head` when `info.part === 'head'`, otherwise a random one of four.
- Change the corpse lifetime: hold the body for 8 s with no sink, then fade over 1.5 s via material opacity
  (or keep the last N=8 corpses and fade the oldest). Never sink through a visible floor.

---

### 6. No gore geometry and no gibs anywhere — `[both]` — L

**What's wrong.** `_popHead()` (l.366) hides `head_X` and `eyes_X` and calls `fx.headPop()`. There is no
neck-stump mesh under the head — the contract (§2) explicitly asks for the stump to "read as gore, not a
hole into the void", and nothing in `build_zombie.py` builds one. No detached head is spawned. Nothing is
ever dismembered: `info.gib` (used by explosions and point-blank shotgun, `weapons.js` l.451/489) only
triggers the same head-hide with 50% probability. `fx.headPop()` (`particles.js` l.304) is 14 small sprites
plus `blood(pos, up, 3.5)` — roughly 35 particles total for a decapitation. And on the *body*, all the wound
detail is painted only: `skin_material()` in `zombie_mat.py` mixes `dried`/`fresh` blood colours into blob
masks at hard-coded object-space points (l.211–226), but none of it is visible in
`zombie_A_front.png`/`_back.png`/`_34.png` or in `04` — those blob centres (z ≈ 0.63–1.48) do not appear to
land on the baked body at all. There is no *geometric* wound anywhere: no crater, no exposed rib, no torn
flesh silhouette.

**Why it matters.** BO2 zombies are readable as damaged bodies even before you shoot them — ribs through a
torn shirt, an arm missing below the elbow, exposed shoulder bone. And when you do shoot them, chunks come
off. Right now a head just blinks out of existence, which looks like a bug.

**Fix.**
- `[blender:characters]` `build_zombie.py`: add a `neck_stump` mesh (a shallow 0.06 m cone of ragged
  triangles, `zombie_gore` material, plus a small white vertebra cylinder) parented to the `neck` bone,
  hidden until the head pops. Add per-variant open wounds as real geometry: on A, cut the shirt open over the
  left ribs and expose 3 rib arcs; on B, an open forearm wound with the ulna showing; on C, a missing left
  hand with a `zombie_gore` cap.
- Verify the painted wounds actually land: print the body object's local bounding box in `build_zombie.py`
  and re-derive the `blob_mask` centres in `skin_material()` (l.211–226) from it rather than hard-coding —
  right now they produce nothing visible.
- `[code]` `_popHead()`: spawn a physical detached head — clone the `head_X` mesh into a loose `THREE.Mesh`
  with a simple ballistic + bounce integrator, 4 s lifetime. Triple `fx.headPop()` to ~45 chunk sprites plus
  a 0.25 s red mist puff (`alpha.spawn` frame 1, `size1: 0.8`, `c0: [0.35, 0.02, 0.02, 0.6]`) and a
  downward arterial spray that persists ~0.6 s from the stump.
- `[code]` add `_popLimb(z, side)` on `info.gib` hits to `part: 'limb'`: hide the limb by zeroing the bone
  scale, cap with a gore quad, spawn the limb as a loose mesh.

---

### 7. Body proportions are a mannequin, not a human — `[blender:characters]` — L

**What's wrong.** `zombie_A_front.png`, `zombie_A_back.png`, `zombie_A_34.png`: sloped narrow shoulders with
no deltoid or clavicle mass; a torso that is a smooth superellipse tube with no ribcage taper and no
sternum; a solid fused block from hip to mid-thigh with no crotch separation (very obvious in `_34`); legs
that are two even cylinders with no calf swell and no ankle narrowing; feet that are shapeless wedge "clogs"
with a stuck-on heel and no toe break (`anim_walk.png`, every frame); hands that are flat mittens with four
thin spikes (`zombie_A_34.png`, left hand) and no palm mass or thumb opposition; a head that sits directly on
the shoulders with no neck cylinder. `zombie_B_front.png` compounds it — the housewife's legs are two
identical smooth tubes ending in white blobs, and the hair is a solid slab wedge hanging off the skull like
a plank.

**Why it matters.** Silhouette is what you read at 15 m in fog, which is most of the game
(`01`, `19`). A BO2 zombie silhouette is unmistakably a person: shoulder width ~2.4 head-widths, defined
calf/ankle, a real shoe, one shoulder dropped. This silhouette is a shop dummy.

**Fix.** In `zombie_mesh.py`:
- `build_yoke()` / `torso_profile()`: widen the shoulder ring by 18% and add deltoid blobs at
  `(±0.185, 0, 1.44)` r 0.055; add a clavicle ridge line and a sternum groove; taper the waist an extra 12%.
- Separate the legs: `leg_path()` should start the thigh at the true hip socket with a gap — add an inner
  crotch cut so the two thighs are distinct volumes from `z = 0.85` down.
- `build_leg()`: add a calf bulge (r ×1.22 at 32% of shin length) and an ankle pinch (r ×0.62 at the malleoli).
- `build_foot()`: build an actual 1950s shoe — a last-shaped sole 0.265 m long with a 0.02 m welt, a rounded
  toe cap, a heel block, and a laced upper. The current wedge is the worst single silhouette element below
  the waist.
- `build_hand()`: thicken the palm to 0.026 m, widen the metacarpal fan, give the thumb a real opposed
  position, and taper the fingers instead of leaving needle spikes.
- Add a neck cylinder r 0.052 between `chest` and `head` so the head is not welded to the torso.
- Randomise per variant: ±8% shoulder width, ±6% height, one dropped shoulder (rotate `shoulder_L` −7° in the
  rest pose for B).

---

### 8. Clothing is a paper shell with no tailoring — `[blender:characters]` — M

**What's wrong.** `zombie_A_back.png` shows the shirt as a thin surface that simply *stops* in a straight
horizontal cut at the waist, with a visible zero-thickness edge. No collar, no cuffs, no buttons, no plackets,
no pockets, no belt, no waistband — the trousers are a painted colour change on the same tube. The suspenders
are two flat 5 mm ribbons floating over the shirt with no clip hardware, no tension bend and no shoulder
indentation. `zombie_B_front.png`: the dress is a cone with a hard rim hem and the apron is a flat rectangle
with the *same* blotch texture as the shirt. `zombie_C_front.png` is the worst — the contract asks for
"olive fatigues, webbing", and the soldier has no webbing pouches, no boots (he is **barefoot** with a
helmet), no belt, and his jacket is two flat lapel triangles. All three share one 1024² cloth bake, so the
shirt, apron and dress read as the same material at different tints.

**Why it matters.** BO2's 1950s Nuketown zombies are legible *characters* — you can see the bowling shirt,
the apron strings, the mailman's satchel. Thickness and a hem are what separate "clothed" from "painted".

**Fix.** In `zombie_cloth.py` / `build_zombie.py`:
- Give every garment real thickness: solidify each cloth shell to 4–6 mm with a rolled (not flat) hem, and
  flare the hem outward 8–12 mm so it catches a rim light.
- Add the hard-surface details as separate small meshes: collar band + points, cuff bands, a belt with a
  buckle, 4–5 buttons, a chest pocket, suspender clips.
- `cloth_material()`: give each garment its own bake with a distinct weave scale and a distinct pattern —
  A's shirt a fine poplin, B's dress a printed floral (the contract says "floral" and there is none), C's
  fatigues a heavy twill. Raise the weave contrast; the current bakes read as a uniform blotch at 1 m.
- C specifically: add jump boots with laces, an M1936 pistol belt, two ammo pouches, a canteen, and a chin
  strap on the helmet. Currently he reads as "man in green pyjamas with a saucepan".
- Tear the silhouette, not just the texture: cut actual ragged notches into the hems and sleeve ends (10–15
  vertices displaced outward/inward per edge loop) so the outline is broken against the sky in `02`.

---

### 9. The hellhound is a lava-cracked giraffe, not a burned dog — `[blender:characters]` — L

**What's wrong.** `hound_side.png`: the body is roughly 1.35× too long for its height, the legs are near-even
pipes with almost no hock/stifle angulation and read as stilts, the head is undersized relative to the barrel
of the chest, the neck has no ruff or trapezius mass, the tail is a bare wire, and there are no paws — the
legs just taper to points (`hound_34.png`). `hound_head.png`: the muzzle is a smooth rounded tube with no
stop, no nose leather, no lips, no brow; the ears are flat paddles; the eye is a single flat white circle
with a hard edge sitting *on* the surface, no socket. The surface treatment is a Voronoi "magma crack"
network over a uniform dark grey — it reads as an obsidian rock golem, not charred flesh. There is no fur
anywhere, no exposed rib, no burned-away skin. `05_hellhounds.jpg` in game confirms it: at 8 m they read as
smooth brown quadruped props with two orange dots. The anim contact sheets (`anim_hound_run.png`,
`anim_hound_attack.png`) show a *different, older* surface — flat orange stripes instead of the crack
network — so the check renders and the shipped GLB disagree.

**Why it matters.** BO2 hellhounds are compact, heavy, muscular, matted-fur-over-burned-skin, with fire
visibly venting from the mouth and along the spine, and a smoke trail. They are scary because they look like
something that was a dog and is now on fire. This looks like a decorative garden sculpture.

**Fix.** In `build_hellhound.py`:
- Proportions: shorten the barrel by ~20%, shorten all four legs by ~15% (shoulder stays ~0.85 m per the
  contract, so the body gets *thicker*, not shorter overall), widen the chest by 25%, enlarge the head by
  ~18%, thicken the neck and add a shoulder/scruff ruff.
- Add real paws with toes and claws at each `*paw_*` bone, and a hock joint with a proper backward angle on
  the hind legs.
- Head: add a muzzle stop, a nose leather with nostrils, lip lines that expose the canines at rest, a heavy
  brow, and pinned-back ears with thickness.
- Surface: replace the uniform Voronoi crack with a layered material — matted fur clumps over the shoulders
  and haunches (geometry: 40–60 low-poly fur tufts along the spine and ruff), burned bare hide on the flanks,
  and glowing fissures **only** in the deep creases (drive the emissive mask by curvature/AO, not by a
  uniform Voronoi). Add 2–3 exposed rib arcs on one flank.
- Eyes: replace the flat disc with a recessed sphere in a socket, r 0.011, emission `(1.0, 0.22, 0.03)`
  strength 2.5 (currently 4.0 and it blows out — see issue #2).
- Re-render `hound_*.png` and the `anim_hound_*.png` sheets from the *same* build so they stop disagreeing.

---

### 10. Zombies disappear into the background under the game's lighting — `[code]` — M

**What's wrong.** `01_street_start_horde.jpg` and `19_combat_mp5_firing_hud_perks_powerups.jpg`: at 12–20 m
the zombies are featureless dark grey blobs against the fog — you cannot tell variant, facing, gait or even
how many there are. In `02_zombies_backlit_group.jpg` the ones at 6 m are silhouettes with a bright fog wash
over them and no form-defining shading at all. Contributors: `createLights()` in `src/world/sky.js` gives one
low warm directional (`3.8`, colour `(1.0, 0.56, 0.3)`) plus a hemi at `0.55`, so anything facing away from
the sun gets only flat sky fill; `FogExp2` at `0.012` (l.43) washes out contrast from ~15 m; the cloth base
albedos are `0.02–0.09` (`build_zombie.py` l.213, l.232) which is near-black; and `envMapIntensity = 0.5` is
forced on every zombie material (`zombies.js` l.156), halving their only fill.

**Why it matters.** BO2 lights zombies so they *always* read against the background — strong rim from the
sky, enough fill to see the face, and characters that are lighter in value than the ground. A player needs to
count the horde at a glance; right now they vanish.

**Fix.**
- `src/ai/zombies.js` l.156: raise to `m.envMapIntensity = 1.15` for zombie materials (keep 0.5 for the map).
- `src/world/sky.js` `createLights()`: add a dedicated dim cool rim light opposite the sun
  (`new THREE.DirectionalLight(0x8fa6c8, 0.9)`, no shadow) so every zombie gets an edge separating it from
  the fog. This is the single biggest readability win.
- `src/game/game.js` l.641: the outdoor fog density `0.012` is fine for the map but eats the zombies — either
  drop to `0.008`, or add a per-material `fogFactor` reduction on zombie materials via `onBeforeCompile` so
  they fog at ~60% of the world rate.
- Raise the cloth base albedos in `build_zombie.py` by ~2× (`0.022` → `0.048`, `0.048` → `0.095`); they are
  currently darker than the tarmac.
- Optional but cheap: add a very subtle per-zombie point light is *not* wanted (cost), but a 0.15-strength
  wrapped-diffuse term on `zombie_skin` would restore face form in shadow.

---

## Lesser issues

### 11. Walk, run and sprint are nearly the same animation — `[blender:characters]` — M

`anim_walk.png`, `anim_run.png` and `anim_sprint.png` are hard to tell apart: the same upright torso, the
same forward lean, the same stride length, and in all three the arms are frozen in an identical bent-elbow
"T-rex claw" hold with only a few degrees of noise (see `run_style()` / `sprint_style()` in `zombie_anim.py`,
which vary the *legs* richly but leave the arms nearly static). BO2's walker drags one foot with the torso
rolling ~12° side to side and one arm hanging completely dead; the sprinter pumps its arms hard and leads
with the head. **Fix:** in `build_loco()`, drive the arms from the same `sw` swing signal as the legs —
walk: one arm fully limp (`upperarm` 8°, elbow 20°, swinging passively at half the leg frequency), other arm
reaching; run: 25° counter-swing; sprint: 60° pump. Increase torso roll (`lean`/`wob`) to ±10° for walk and
add a 4–6° head lag behind the chest.

### 12. The attack is a symmetrical two-arm overhead raise — `[blender:characters]` — S

`anim_attack.png` frame 3: both arms go straight up above the head in a symmetric "hooray" pose before coming
down. That is the cartoon-zombie cliché, not a BO2 attack, which is a fast diagonal one-arm claw swipe across
the body (alternating left/right) with the shoulder driving through and the opposite arm trailing.
**Fix:** replace with `attack_L` and `attack_R` — wind-up 0–35%, contact at 45% (per the contract), follow
through to 100%, with the hips rotating ~20° into the swing. Pick randomly in `_chase()` (`zombies.js` l.610).

### 13. Zombies never look at the player — `[code]` — S

The head is fully driven by the clip; nothing aims it. `z.bones.head` is already resolved (l.144). BO2
zombies lock onto you. **Fix:** in `_postPose()` (l.457), after `mixer.update`, add a clamped head/neck
look-at toward `game.player.pos` — split 30% into `neck`, 70% into `head`, clamped to ±55° yaw / ±25° pitch,
damped at ~4/s. Suppress it while `state === 'dead'`.

### 14. `rise` has no dirt mound and hands appear before the body — `[both]` — S

`anim_rise.png`: the first two frames are empty ground, then two detached hands and a shoe pop out of a flat
plane, then the whole figure rises through it. There is no soil displacement, no mound, no hands clawing at
the *surface*. `dirtBurst()` (`particles.js` l.373) fires once at spawn (`zombies.js` l.234) with 16 chunks
and 5 dust puffs — far too little, and all of it is over before the body is out.
**Fix:** `[code]` call `dirtBurst` three times staggered over the rise (t = 0, 0.45, 0.9) and double the
counts; add a flat dark decal at the spawn point that fades after 8 s. `[blender:characters]` re-time the
`rise` clip so one hand breaks the surface alone for the first 0.5 s and claws at the ground before the head
appears.

### 15. `tear` is a symmetric two-hand pull with no weight — `[blender:characters]` — S

`anim_tear.png`: both arms move together, straight back, with the torso static. A BO2 zombie plants one hand
on the frame, yanks with the other, and its whole body recoils when the board gives.
**Fix:** asymmetric — left hand braces on the window frame, right yanks; add a 3-frame snap-back on the torso
and head at the moment the board breaks (~55%, matching `_tear()` l.569).

### 16. Hellhound attack rears up like a horse — `[blender:characters]` — S

`anim_hound_attack.png` frames 3–4: the hound stands vertically on its hind legs with a straight spine. A
hellhound pounce is a horizontal leap — body extended, front legs forward, jaw wide, hind legs trailing. The
`jaw` bone exists but barely opens in any frame.
**Fix:** rebuild `attack` as a leap: crouch 0–25%, airborne extension 25–60% (root translates +1.2 m forward
and +0.5 m up), bite/land 60–100%, with the jaw opening to ~40°. Add a `death` that collapses and skids
rather than a clean fall.

### 17. Hellhound death is an explosion — `[code]` — S

`kill()` l.350: dogs get `fx.explosion(... 1.6 ...)`, an `explosion` sound, and the mesh is switched off at
0.35 s. BO2 hellhounds collapse, burn out, and leave a scorch. **Fix:** play the `death` clip in full, ramp
`fx.fire` up over ~0.8 s as the body sags, then fade the mesh over 0.5 s and leave a scorch decal. Keep a
small ember burst, drop the explosion and the `explosion` SFX (use `hellhound_growl` pitched down + fire).

### 18. Hit flinch is a single chest tilt with no direction — `[code]` — S

`_postPose()` l.460–463 rotates the chest `-flinch * 0.35` on X and `±0.15` on Z keyed off `z.id % 2` — so
the flinch is always the same shape regardless of where the bullet came from, and the same side every time
for a given zombie. **Fix:** store `info.dir` on damage as `z.flinchDir` (local-space), and rotate the chest
*away* from it on both axes, plus a sharper `head` counter-rotation and a 0.08 s hitch in `mixer.timeScale`.

### 19. Hair and helmet are hard-edged caps — `[blender:characters]` — S

`zombie_A_head.png`: the hair is a smooth shell with a visible hard rim where it meets the forehead, like a
swim cap. `zombie_B_head.png`: a solid slab wedge hanging past the jaw with a flat bottom edge.
`zombie_C_front.png`: the helmet is a plain dome with no rim flare, no rivets, no chin strap, and it floats.
**Fix:** feather the hairline with an irregular, partly-receded edge and break the mass into 4–6 clumps with
gaps showing scalp; give B's hair a ragged, matted lower edge. Add a flared rim, band, rivets and a chin
strap to the helmet.

### 20. Only three variants and no per-instance dressing — `[code]` — S

Three bodies × three heads, chosen uniformly (`spawn()` l.219–224), with only a ±7% uniform scale. In a
24-zombie wave you see each variant eight times, identically. **Fix (cheap, code-only):** per instance,
randomly tint `zombie_skin` hue ±0.03 and value ±12% on a cloned material; randomly hide the hair mesh (20%
bald); randomly offset `shoulder_L/R` rest rotation by ±6°; and randomly mirror-scale X (`root.scale.x *= -1`
with a matching material side flip) for a free second silhouette per variant.

### 21. Blood impact FX are far too small and there are no wound decals on the body — `[code]` — M

`fx.blood()` (`particles.js` l.290) emits `6 * amount` droplets + `2 * amount` puffs — a body shot is 8
particles total, which is invisible at 10 m in fog (`19`). Ground splats only fire 35% of the time
(`zombies.js` l.328) and nothing is ever painted on the zombie itself. **Fix:** triple the droplet count,
add a short-lived stretched arterial jet along `-dir`, and add a persistent dark decal projected onto the
zombie at the hit point (a small pooled decal atlas on the skin material, or a cheap 3-slot decal array in
the shader).

### 22. `rise` and `climb` fall back to the wrong clips on a partial asset — `[code]` — S

`_play()` l.173 maps `rise → idle` and `climb → walk` when a clip is missing. Both are silently wrong
(a zombie would stand still while emerging from the ground). Not currently hit, since all clips exist — but
it will mask a future asset regression. **Fix:** log a one-time warning when a fallback is used.

### 23. Idle is too calm — `[blender:characters]` — S

`anim_idle.png`: a gentle even sway across all six frames, no twitch, no head jerk, no jaw movement. The
contract asks for "swaying, twitchy". `twitch()` exists in `zombie_anim.py` (l.480) but the amplitude in
`build_idle()` is small. **Fix:** raise the jerk amplitude to ~3× and add 2–3 sharp 2-frame head/shoulder
snaps per 4 s cycle.
