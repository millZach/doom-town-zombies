# Fix log — stream `characters` (Blender asset rebuild)

Assets rebuilt: `public/models/zombie.glb` (8.6 MB, 3 variants x body/legs/head/eyes,
20 clips) and `public/models/hellhound.glb` (2.5 MB, 23.1k tris, 4 clips).
All contract bone names, mesh node names, material names and clip names are preserved;
`legs_A/B/C`, `crawl`, `crawl_attack`, `to_crawl` and `death_front/back/left/right` are
added on top. Verified with `node tools/inspect-glb.mjs … --tree`. `npx vite build` passes.

Per-variant triangle budget: A 27.3k, B 27.9k, C 26.3k (see the repair-round
section at the end for the budget correction - the written contract says 25k).

---

## zombies.md #1 — the face is a flat mask with a permanent cartoon grin — **fixed**

`tools/blender/characters/zombie_mesh.py`

* `CRANIUM` / `MANDIBLE` tables rebuilt. The old tables were *prognathic*: the chin
  reached 24 mm further forward than the brow, which is a chimpanzee's profile and was
  the real reason the head read as a muzzle. The forehead, brow and chin now sit on one
  vertical plane and only the nose projects past it.
* `sculpt_head()` rewritten. Eye socket carved 25 mm deep with a `_nose_guard` filter so
  the widened sockets no longer meet in the middle and eat the nose dorsum; the socket is
  then ringed by a **proud orbital rim** (`blob_line` around an ellipse, pushed forward)
  and re-deepened, so the recess has a hard edge instead of being a soft dip. Temple
  hollows, zygomatic hollows, masseter shadow, nasolabial folds, brow furrow.
* A note that cost two iterations and is now in the docstring: `L.blob` displaces
  *radially from its centre*, so a blob centred on the surface does nothing — every
  carving blob has to sit ~10 mm behind the surface it is carving.
* **Lip recession, not a grin**: `sculpt_head` rolls the upper lip band up and back off
  the gum ridge and drops the lower lip band off the mandible, and pulls the mouth
  corners back into a dried rictus. `JAW_OPEN` reduced 15° → 12°.
* **Real teeth and gums**: `tooth_arc()` places teeth on an *elliptical* arch
  (`ARC_X/ARC_Y/ARC_SPAN`) with per-tooth random yaw ±6°, random pitch, random inward
  offset 0–1.5 mm and random width; 2–4 teeth per head are deleted, seeded per variant
  (`TOOTH_SEEDS`), so no two smiles are the same and none is continuous. Teeth taper
  toward the biting edge. New `build_gums()` builds upper and lower gum ridges plus a
  shrunken dry tongue.
* Materials (`build_zombie.py`): `zombie_teeth` dropped from `(0.215, 0.192, 0.125)` to
  `(0.120, 0.105, 0.070)`; new `zombie_gum` `(0.075, 0.020, 0.018)`.
* **Distinct faces**: `FACE_VARIANTS` + `variant_face(ob, V)` runs *after* the shared UV
  bake (topology and UVs unchanged, so all three heads still share one `zombie_head`
  material) and re-shapes jaw width/length, brow heaviness, cheekbone projection, nose
  length and chin projection per variant, plus six seeded asymmetric blobs — nobody's
  face is mirrored.
* **One asymmetric facial wound each**: A a torn right cheek, B a split brow with bone
  showing, C the left mandible shot away. `FACE_WOUND` / `face_wound_faces()` give those
  faces the `zombie_gore` material.
* Head resolution raised (voxel 0.0045 → 0.0038, smooth factor 0.45 → 0.30) so 5–10 mm
  features survive the remesh.

**Left**: at extreme close range the nose still reads soft — it is a lofted part on a
voxel-remeshed head, not a sculpt. Acceptable at the game's 1.9 m framing
(`renders/characters/zombie_A_game.png`).

## zombies.md #6 — no gore geometry, wound/blood masks never landed — **fixed (Blender half)**

The actual bug was not a coordinate error in `blob_mask`. Every torso wound was authored
*underneath a closed garment*, and `remove_covered()` then deleted exactly those body
faces — so the painted blood and the sculpted craters were both thrown away before
export. Three separate hard-coded lists (sculpt, gore-material picker, material paint)
had also drifted apart.

* `zombie_mesh.WOUNDS` is now the single shared table. `sculpt_body()` carves from it,
  `wound_faces()` assigns `zombie_gore` from it, `zombie_mat.skin_material()` imports it
  for the blood masks, and `zombie_cloth.tear_open()` cuts the garment open from it.
* Wounds moved onto skin that is actually visible (right forearm, left hand, neck) or
  given `hole=` so the garment is cut open over them (A ribs, B belly, C shoulder, all
  three left thigh).
* `build_zombie.py` passes `protect=` to `remove_covered()` so wound faces survive.
* `lib_char.delete_region()` punches the hole (ellipse stretched 1.9× in Y so the cut
  reaches the shell wherever it sits — the wound centre is on the *skin*, several cm
  further in) and `lib_char.rim_boundary()` extrudes the torn edge inward 6 mm so it
  shows a wall of fabric rather than a zero-thickness cut.
* `zombie_mesh.exposed_ribs()` carves three torn rib arcs inside variant A's open chest
  wound, so the hole has anatomy in it.
* `skin_material()`: dried blood is now applied half flat / half through the drip mask
  (`MAXIMUM`), so a wound is never completely clean, plus a darker clotted core in each
  crater. The head blood masks were tightened — they had been painting a bright red
  clown-mouth across the whole lower face.
* `build_zombie.py` also prints the body's local bounding box at build time so a future
  drift between the mask space and the mesh is obvious.

## zombies.md #7 — mannequin proportions — **fixed**

`zombie_mesh.py`, `zombie_rig.py`

* `TORSO` rebuilt: shoulder ring widened ~18 % (0.185 → 0.199 half-width), a real
  starved waist at 0.131, ribcage flare above it, and a narrow neck column on top.
* `zombie_rig.J`: shoulders moved 12 mm outboard (arm length unchanged).
* `build_yoke()` widened to ±0.238 with deltoid caps; `sculpt_body()` adds a deltoid cap,
  biceps, triceps, armpit hollow, elbow crease, forearm belly, clavicle ridge *and* the
  hollow beneath it, sterno-mastoid cords, a sternum groove and wasted pectorals.
* New `build_neck()` — a real neck column between chest and head.
* `leg_path()` starts on the femur head, so the two thighs are separate volumes below
  z = 0.845; plus an inner-thigh gap and a crotch groove in `sculpt_body()`.
* `_leg_radii()` gives a calf swell at ~32 % of the shin and a malleolar ankle pinch;
  `sculpt_body()` adds patella, tibia ridge, hamstring hollow and both malleoli.
* `build_hand()`: palm thickened and the metacarpal fan widened, a thenar pad added,
  fingers thickened (r 0.0084 → 0.0104) with knuckles and blunt tapered tips instead of
  needle spikes, thumb properly opposed.
* `build_foot()` reshaped, and the shoes (below) replaced the clog silhouette.
* `variant_body(ob, V)` adds per-variant re-proportioning: shoulder width ±6 %, limb
  girth ±4 %, a dropped shoulder on a different side per variant, and for B a wider
  pelvis, a bust and a narrower chest.

## zombies.md #8 — clothing is a paper shell with no tailoring — **fixed**

`zombie_cloth.py`

* `_roll_rings()` gives every hem a real 180° rolled fold (torso shells) and
  `limb_sleeve(cuff_roll=…)` gives sleeves and trouser legs a folded cuff, so hems have
  thickness and a silhouette instead of a zero-thickness horizontal cut.
* New hard-surface dressing built as separate meshes: `ring_band()` (collar band,
  waistband, belt), `collar()` (band + two turned-down points), `placket()`, `button()`,
  `pocket()`, `buckle()`, `clip()` (suspender clips front and back), epaulettes.
* A: work shirt with collar, placket, 5 buttons, chest pocket, belt + buckle, suspenders
  with clips, one sleeve torn shorter than the other.
* B: floral day dress with a waist sash, collar and 4 buttons; apron with a hem, a
  pocket and loose waist ties.
* C: **jump boots** with a laced shaft and three straps, an M1936 pistol belt with a
  buckle, two ammo pouches with flaps, a canteen with a strap, epaulettes, two chest
  pockets — he is no longer a barefoot man in green pyjamas.
* `shoe()` rebuilt: last-shaped sole, proud welt, heel block, rounded toe cap with a
  seam, and three laces across the instep.
* Garment tessellation raised (torso n 28 → 32, limbs n 18 → 22, subdiv 2 → 3) so torn
  edges are ragged rather than rectangular.
* `zombie_mat.cloth_material()`: weave contrast raised (shade 0.62 → 0.46 of base), a new
  `twill` pattern (diagonal saw wave) for the fatigues, a legible large-blossom floral
  with petal centres and leaf sprigs for the dress, and per-garment `uv_scale`
  (A 132 / B 118 / C 86) so the three no longer read as one blotch at different tints.
* Cloth base albedos roughly doubled in `build_zombie.CLOTH` (review #10's Blender half).

## zombies.md #4 — no crawlers — **fixed (Blender half)**

* `lib_char.split_at_z()` bisects the finished, weighted body at z = 0.470 and moves
  everything below into a new object, filling the cut on **both** halves with a ragged
  gore cap (`_cap_open_edges`, restricted to a z band so it does not also fill the wound
  holes). Vertex groups, UVs, materials and the armature modifier all survive.
* `build_zombie.py` exports `legs_A/legs_B/legs_C` — knee-down, separately hideable.
  Hiding one reveals the gore stump that is part of `body_X`, exactly as the contract asks.
  Verified in `renders/characters/zombie_crawler.png`.
* `zombie_anim.py`: `crawl` (30 f, 1.0 s, alternating forearm pulls at **0.55 m/s**, the
  torso propped on the forearms, the head swinging low and lagging, the dead legs
  scuffing), `crawl_attack` (21 f, one-arm swipe from prone, contact at 45 %) and
  `to_crawl` (18 f, 0.6 s collapse from standing to prone with the stumps kicking).

## zombies.md #5 — deaths are one stiff plank fall — **fixed (Blender half)**

`zombie_anim.py`

* Four directional deaths: `death_back`, `death_front`, `death_left`, `death_right`
  (`build_death_side()` is new: spun off its feet, dumped on one shoulder, ~86° of roll
  and 60° of yaw). `death_1` and `death_2` are still exported, built from the same
  back/front builders, so nothing that already references them breaks.
* `_death_body()` gained a **settle tail**: after the torso lands (`land` ≈ 0.78) a fast
  decaying impact ring and a slower limb flop keep the arms, legs, head and spine moving
  for ~0.4 s. The arms and legs carry past the torso instead of stopping with it.

## zombies.md #11 — walk, run and sprint were nearly the same — **fixed**

`zombie_anim.py`. The arms are now driven off the same swing signal as the legs:
walk — the right arm is completely dead, swinging passively at **half** the leg frequency
from a limp shoulder (8°, elbow 20°), while the left stays half-raised and clawed;
run — a real 25° counter-swing both sides; sprint — a 60° pump with the elbows snapping
through. Walk torso roll raised to ±11° (`side_lean`), and a new `head_lag` parameter
lags the head ~1/12 of a cycle behind the chest on all three (4–6°).

## zombies.md #12 — symmetrical two-arm overhead raise — **fixed**

`build_attack(rig, lead=…)` rewritten as a fast diagonal one-arm claw swipe: wind up
across and **behind the shoulder** (not over the head) 0–35 %, contact at 45 % across the
body, follow through past the far hip, recover. The hips rotate ~22° into the swing and
unwind through contact; the trailing arm counterweights and never mirrors. Exported as
`attack_L`, `attack_R` and `attack` (= the right-hand one, so existing callers work).

## zombies.md #15 — `tear` is a symmetric two-hand pull — **fixed**

`build_tear()`: the left hand plants on the window frame at 20 % and stays there as the
brace; the right hand grips, loads with a straining shudder, and rips back past the hip.
A hard 3-frame snap-back (`exp(-26·t)`) hits the torso, head and hips at 55 %, matching
the game's `_tear()` break point, and the weight shifts onto the back foot.

## zombies.md #23 — idle is too calm — **fixed**

`build_idle()`: three sharp ~2-frame head/shoulder snaps per 4 s cycle on top of the
sway, with the jerk amplitude raised ~3× (head pitch 16° → 44°, yaw 18° → 52°) plus
shoulder snaps and a second shudder.

## zombies.md #19 — hair and helmet are hard-edged caps — **fixed**

`zombie_cloth.py`. `_scalp()` now feathers the hairline with a two-frequency wobble that
wanders instead of cutting a clean swim-cap rim, and breaks the mass into clumps with
gaps showing scalp. A's hair is properly receded at the temples with four loose strands
over the ear; B's has a ragged, clumped, noise-broken lower edge. `helmet_C()` gained a
flared rolled rim, a band around the shell, six rivets, a third dent and a proper chin
strap with a buckle.

## zombies.md #2 — eyes are blown-out white headlamps — **fixed (Blender half)**

`build_eyes()` shrinks the spheres from r 0.0118 to 0.0092 and sets them at the socket
floor so the upper-lid shelf occludes the top of the glow. `eye_glow` is exported with
emission `(1.0, 0.34, 0.05)` at strength **1.6** (was 3.2) — a modest ember the game
drives, not a headlamp. The hellhound's eyes are r 0.011 at strength 2.5 (was 4.0), set
into carved sockets.

## zombies.md #14 — `rise` hands appear before the body — **fixed (Blender half)**

`build_rise()` re-timed: the right hand alone breaks the surface at t ≈ 0.02 and
*scrabbles* at the ground (four alternating grabs) for the first ~0.5 s; the left hand
follows at 0.30 and the hips stay at −1.24 m until t = 0.28, so the head does not appear
early.

## zombies.md #9 — the hellhound is a lava-cracked giraffe — **fixed**

`build_hellhound.py` rebuilt.

* **Proportions**: barrel shortened ~20 % (0.785 → 0.63 m), all four legs shortened ~13 %,
  chest widened 25 % (half-width 0.112 → 0.146) and made far deeper (half-height
  0.174 → 0.210) so the withers stay at ~0.83 m and the *body* gets thicker, a real belly
  tuck between ribcage and loin, head enlarged ~22 % (skull radii 0.054/0.062/0.054 →
  0.067/0.076/0.065), neck thickened and a scruff/ruff mass added over the shoulders.
* **Legs**: proper canine angulation — the front goes shoulder → elbow → carpus → paw, the
  hind hip → stifle (well forward) → **hock (well back)** → paw. Lower limbs thickened.
* **Paws**: `build_paw()` builds a metacarpal pad, four toes and four claws at every
  `*paw_*` bone. The legs no longer taper to points.
* **Head**: muzzle set below the forehead with a sculpted **stop**, a nose leather with
  carved nostrils, lip ridges that stop short so the canines show at rest, a heavy brow,
  masseter mass, carved eye sockets and temporal fossae, and broad **thick pinned-back
  ears**. `build_teeth()` gives it real canines that project past the lips.
* **Surface**: the uniform Voronoi magma-crack network is gone. The new material layers
  burned bare hide, stretched matted-fur noise restricted to the back and haunches by a
  height mask, and ash on the high points; the emissive is driven by an **ambient-occlusion
  cavity mask** broken up by noise, so fire shows only in the deep creases.
* **Fur as geometry**: `build_fur()` adds ~58 low-poly tufts along the spine, round the
  ruff and over the shoulders and haunches, swept back along the body (an early pass had
  them vertical and it read as a stegosaurus).
* **Exposed ribs**: three deeply carved rib arcs on one flank, which the cavity mask then
  lights.
* `hound_side.png` / `hound_34.png` / `hound_head.png` and the `anim_hound_*.png` sheets
  are all re-rendered from this same build, so they no longer disagree with the GLB.

## zombies.md #16 — hellhound attack rears like a horse — **fixed**

`build_anims()` `attack` rebuilt as a horizontal pounce: crouch 0–22 %, airborne 22–60 %
with the spine **extended and level** (never vertical), front legs thrown forward, hind
legs trailing, the root arcing +0.30 m up and 0.52 m forward, bite at 38–56 % with the
jaw open to **40°**, then land and recover. `death` rebuilt as a collapse that **skids**
0.47 m forward while rolling 86° onto its side, with an impact settle.

---

## Needs from other streams

All in `src/ai/zombies.js` (owned by the code stream) unless noted.

1. **`legs_X` must be added to the variant-mesh regex.** `_build()` matches
   `/(body|head|eyes)_([ABC])/`; `legs_A/B/C` will therefore **stay visible on every
   variant** and you will see three sets of shins. Change both occurrences to
   `/(body|head|eyes|legs)_([ABC])/`.
2. **Crawlers**: hide `legs_<variant>` rather than zeroing `shin_*`/`foot_*` bone scales —
   the gore stump cap is already built into `body_X` and is revealed by hiding the legs
   object. Play `to_crawl` (0.60 s) on the transition, then loop `crawl`.
3. **`CLIP_SPEED.crawl` should be `0.55`, not `0.8`** — that is the ground speed the
   `crawl` cycle is actually authored at (logged by the build). Feet/hands will slide
   otherwise.
4. New clips available: `attack_L` / `attack_R` (pick randomly in `_chase()`),
   `death_front` / `death_back` / `death_left` / `death_right` (plus `death_1` / `death_2`,
   still present as the back/front pair), `crawl`, `crawl_attack`, `to_crawl`.
5. **Eye material**: `eye_glow` now ships at emissive strength 1.6 with colour
   `(1.0, 0.34, 0.05)`. Line ~155's `Math.max(m.emissiveIntensity, 5)` will undo that —
   it needs to clamp *down* (≈2.2) as review #2 asks.
6. **Per-instance tint (#20)**: the body material is `zombie_skin` and the head material
   is `zombie_head` (shared by all three heads). Match `/zombie_(skin|head)/` or the heads
   will not tint with the bodies.
7. New material names in the GLB: `zombie_gum`, `cloth_B_acc`. Removed: `cloth_B_dress2`
   (variant B has no separate lower garment). Nothing in `src/` referenced it.
8. **Hellhound `attack` now carries root motion** (−0.52 m forward at the bite, returning
   to −0.12 m by the end). If `_dogAttack` also translates the holder during the lunge the
   two will double up — either drive the lunge purely from the clip or scale the holder
   motion down.
9. The hellhound `death` clip is 1.40 s and ends flat on its side with a 0.47 m skid —
   long enough for review #17's "play the death clip in full, burn out, leave a scorch"
   instead of the current explosion at 0.35 s.

## Not done / partial

* **Variant B reads as a woman, but weakly.** The dress, apron, long hair, narrower
  shoulders, wider pelvis and bust are all there, but at 15 m in fog the silhouette is
  still close to A's. A shorter overall height and a more fitted bodice would help; left
  as partial.
* **`build_foot()`** (the bare foot under the shoe) is improved but still simple — it is
  never visible on any shipped variant.
* The hellhound has no smoke trail or fire venting from the mouth; those are particle/FX
  features and belong to the code stream.
* Fur is low-poly tuft geometry, not hair cards — deliberate, for the triangle budget.

---

# Repair round (adversarial verification follow-up)

`docs/review/fixlog/characters-verify.json` filed eight blocking items against the first
pass. Both assets were rebuilt and re-verified; every check below was made from the
exported GLB or from a fresh check render, not from the previous claims.

**Correction to the header of this log:** the earlier line "Per-variant triangle budget
(35k allowed)" was not in any contract — `docs/ASSET_CONTRACT.md:43` says 25k per variant,
and the integrator raised the character ceiling to ~35k separately. The numbers now, from
`node tools/inspect-glb.mjs public/models/zombie.glb --tree`:

| variant | body | legs | head | eyes | total |
|---|---|---|---|---|---|
| A | 15,279 | 3,836 | 8,050 | 160 | **27,325** |
| B | 15,152 | 4,042 | 8,554 | 160 | **27,908** |
| C | 15,172 | 4,450 | 6,534 | 160 | **26,316** |

hellhound: 23,074 tris (its own 24k backstop). `build_zombie.BUDGET` is a hard decimate
backstop at 35,500 so nothing can ship above it; the three variants land ~7k under it
without needing it. All three are still above the written 25k contract — that is the
integrator's allowance, not a number this stream invented.

## Blocking items

1. **`rise` re-timed (#14) — fixed, and now proved at build time.** Root cause: the grave
   was 1.40 m deep while the arm is 0.569 m long, so every "hand above the soil" target was
   clamped by `two_bone_ik` to max reach and the hand stayed underground until t = 0.90 s.
   The grave is now 0.92 m (still deep enough to hide the skull at t = 0), the right wrist
   has four alternating claw-and-drag keys through the first third, and the left wrist is
   held under the soil until 0.30 of the clip. `build_rise` FK-checks the bones as it keys
   them and prints the crossings, so this can no longer be claimed without being measured:
   `[rise] surface crossings (fraction of clip): hand_R 0.03  hand_L 0.32  head 0.52`
   — i.e. 0.07 s / 0.70 s / 1.14 s of a 2.20 s clip. `renders/characters/anim_rise.png` is
   re-framed (tight on the ground, front-loaded sampling at t = 0, .05, .13, .24, .45, .72)
   so the single hand is visible in four frames before anything else appears.
2. **Garment holes are ragged tears with flesh behind — fixed.** `zombie_cloth.tear_open`
   now calls the new `lib_char.punch_hole`, which sweeps a *tube* along the wound axis,
   deletes the straddling faces and then snaps the surviving rim onto a ragged ellipse
   (`jag=0.26`), so the cut follows a curve instead of the quad grid; the rim is flicked
   3 mm off the body and `rim_boundary` walls it 11 mm deep. The black void is gone for a
   second reason: `build_zombie._protect` now protects the skin under the hole with the
   *same swept tube* the hole is cut with at 1.9x radius (the old sphere at 1.55x was
   smaller than the hole the cloth builder cut, so the player looked through the tear into
   the unlit inside of the garment). See the thigh in `zombie_A_front.png`,
   `zombie_C_front.png` and the close-up `zombie_stump.png`.
3. **Crawler severed end — fixed.** `split_at_z` caps both halves with a poked ragged gore
   crater, `ZM.stump_bones` adds splintered femur ends in the dry-bone material, and the
   cap faces within 12 mm of the cut are forced to `zombie_gore` on both `body_X` and
   `legs_X`. `renders/characters/zombie_stump.png` is a new check render shot from *below*
   the cut — the cap is a torn red crater with bone in it. Related fix: the earlier
   "everything within 12 mm of the cut" rule also painted the *outside* of the trouser
   leg, so an intact zombie wore a bright red ring round each knee in every render; the
   rule is now limited to faces whose normal is vertical (the cap faces).
4. **Variant C's jump boots read — fixed.** The trouser leg stops at station 7 (z = 0.254)
   and flares (`taper_end=1.30`) so it blouses over the boot cuff at 0.250, and the shaft
   was shortened to match. Boots, cuff roll and straps are visible in `zombie_C_front.png`
   and `zombie_C_34.png`.
5. **Hellhound spinal fur — fixed.** Third attempt. Pass 1 was 58 fat near-vertical plates
   (stegosaurus); pass 2 was 52 long thin raked spines (porcupine) — both because the
   clumps were placed at `torso_top(y)`, the centre-line height, however far out in x they
   sat, which lifted every off-centre clump into the air. There is now a `hide_z(x, y)`
   that solves the torso superellipse, and the clumps lie *on* the hide: four patches with
   60-90 mm bald gaps between them, 4-7 mm proud of the surface, only a third of them
   lifted at all, plus a ruff and a few haunch locks. `hound_side.png` / `hound_34.png`
   show burnt patchy hide with embers in the gaps and an unbroken back line.
6. **Variant B's belly wound — fixed.** The bib apron became a period-correct *waist*
   apron tied at z = 1.048 (`_apronband` replaces the bib straps), so the torn dress and
   the wound above it are in clear view; the apron also clears the now fuller dress.
7. **Crawl speed mismatch — closed from this side too.** `zombie_anim.CRAWL_V` was still
   0.80 while the code stream had moved `CLIP_SPEED.crawl` to 0.55. The cycle is now
   authored at 0.55 m/s and the build logs `clip crawl 30 frames 1.00s v=0.55 m/s`.

## Partials improved

* **#1 "B must read as a woman".** `torso_shell` gained a `shape_fn(z)` hook and variant
  B's dress now carries real tailoring (`_figure_B`: +24 mm bust, -15 mm waist, +18 mm hip
  spring) instead of tracing the same tube as the soldier's jacket; the body under it went
  to 0.87 shoulder scale, 1.16 hips, a nipped waist, a slimmer neck and a larger bust with
  an under-bust shadow. `zombie_B_34.png` / `zombie_B_back.png`.
* **#1 nose.** The lofted nose had no edge anywhere. There is now a narrow raised dorsum
  ridge with the side walls pulled in under it, a tip ball and a columella shadow, so the
  nose carries a highlight edge at head framing instead of reading as a lump.
* **#8 tailoring/folds.** New `zombie_cloth.folds()`: structural folds instead of noise —
  belt bunching rings, a diagonal drape from each shoulder point to the opposite waist, an
  armpit crush, elbow-crook creases, seat/groin drag and stacked bunching above each knee
  and each boot. Every fold is authored as a groove plus the roll above it. Garment ring
  density was raised (shirt/jacket 18-20 -> 30 steps, sleeves `subdiv` 2 -> 3) so a 25 mm
  fold has vertices to move.
* **#9 hound anatomy.** Muzzle lengthened 105 -> 125 mm and narrowed to a wedge (49 -> 30
  mm across), jaw and lips follow it, ears enlarged 108 -> 142 mm with a 5 mm edge so the
  voxel remesh no longer eats the tips, and the legs got the masses a joint needs in order
  to read: gaskin, calcaneus point, stifle crease, thigh mass, triceps, olecranon. Remesh
  0.0080 -> 0.0070 with decimate 0.24 -> 0.20 to keep that detail.
* **#19 hair.** `hair_A`'s locks were up to 33 mm thick, stood 13 mm off the skull and
  reached round to azimuths over the cheekbone — at head framing they read as splinters
  driven through the face, which is worse than the swim cap the review filed. Now 34
  strands at a third of the thickness, hugging the skull, stopped behind the ear, plus a
  thinning crown fringe and nape wisps. `hair_B` went from 25-39 mm planks to 8-13 mm
  strands, 26 -> 36 locks plus 14 long ones.

## Bug found and fixed while verifying (not in the review)

Variant B had a flat "blade" of dress and waistband material sweeping from the waist to
the chest in every pose — visible in the first pass's own `zombie_B_front.png`. Diagnosed
by re-rendering the exported GLB with one flat colour per material (it was `cloth_B_dress`
plus `cloth_B_acc`, not a shadow). Cause: `clean_arm_weights` only stripped arm weights
from vertices *further* than 90 mm from an arm, and in the rest pose the hand hangs beside
the hip, so the dress waist and the apron band kept `hand_R` at full weight and were
dragged out into a sail. Garment panels are now never driven by a forearm or a hand at any
distance (`distal_all=True`; proximal shoulder/upperarm weights still win near the
shoulder, so sleeve heads and yokes still follow the deltoid). A second trap is guarded
too: `orphan_guard()` height-weights any unweighted vertex *before* `L.fix_weights` can
resolve it from its nearest weighted neighbour — which, beside the hip, is a hand vertex.
Both are reported in the build log (`stripped stray arm weights from N verts`,
`orphan verts N`), and a `WARNING <part> still arm-weighted on N verts` line fires if a
non-sleeve panel ever keeps one again.

## Build-script safety

`--variants=A` (or any partial set) no longer writes `public/models/zombie.glb`; it writes
`tools/blender/_texcache/_scratch_zombie_<set>.glb`. Only the full `--variants=ABC` build
can touch the shipped asset. Check renders are capped at 896x504 / 32 samples, and
`--stills=<views>` / `--sheets=<clips>` render only the views or clips being iterated on.

## Verified after the repair

* `node tools/inspect-glb.mjs public/models/zombie.glb --tree`: 22 bones with the contract
  names, `body/legs/head/eyes_A/B/C`, all 20 clips (`walk run sprint idle tear hit climb
  rise crawl crawl_attack to_crawl attack attack_L attack_R death_1 death_2 death_front
  death_back death_left death_right`), materials including `eye_glow`, `zombie_gore`,
  `zombie_gum`, `cloth_B_acc`.
* `node tools/inspect-glb.mjs public/models/hellhound.glb --tree`: 26 joints, 4 clips
  (`run idle attack death`), 23,074 tris.

## Still not done

* The hound's head is canine now, but the neck/ruff mass still reads nearly as wide as the
  skull at 3/4 view, and the hind legs, while shaped, are straighter than a real dog's.
* Gore albedo is deliberately dark (`zombie_gore` 0.046/0.015/0.012) to keep the mouth
  interior from reading as a cartoon grin; on the severed knee that costs some punch in
  low light.
* Variant B's floral print still reads as blotches rather than flowers at any distance.
