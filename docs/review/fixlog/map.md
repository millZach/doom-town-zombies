# Fix log — stream `map` (Blender map assets)

Files owned/changed: `tools/blender/map/*`, `public/models/map_doomtown.glb`, `renders/map/*`.
Nothing in `src/` was touched.

New modules
- `tools/blender/map/lib_sign.py` — real signage lettering (Blender FONT object → mesh).
- `tools/blender/map/lib_decals.py` — authored RGBA decal library (numpy + a small PNG writer,
  no Blender bake), plus `Scene.decal()` in `lib_map.py` to stamp them.

Every Blender job went through `sh tools/blender/run_locked.sh`; check renders at 960x540 / 28
samples. Verified with `python tools/blender/map/validate.py` and
`node tools/inspect-glb.mjs public/models/map_doomtown.glb` after each build.

---

## #5 — 22 rubble rocks floating at the bunker ceiling — **fixed**

`build_bunker.py:room()` — the scatter placed rocks at absolute `z = s * 0.25` while the bunker
floor is at `BUNK_Z = -2.5`, so all 22 hung 2.5 m up, right under the ceiling of the Pack-a-Punch
room (the "rusty slab", the "black hex plate" and the loose chunk upper-right in
`renders/map/bunker_pap.png` are all from this one loop). Now `(x, y, BZ + s * 0.25)`. The scatter
also skips the middle 0.9 m so the new drain channel stays clear.

Checked every other scatter in the bunker for the same bug: `service_tunnel()` was already correct
(`BZ + 0.1`); the mound and headhouse scatters are street-level and correct.

## #6 — 3x5 bitmap signage that spelled "FHLLOUT SHELTEK" — **fixed**

`lib_sign.sign_text()` builds a Blender FONT object (Windows `STENCIL.TTF` for civil-defence
signage, `ariblk.ttf` for vehicle lettering, with a built-in-font fallback), converts it to a mesh,
normalises it to an exact cap height, squashes it to the plate width and stamps ~2–6 mm of proud
paint into the caller's geometry bank. Curve resolution scales with letter height (1/2/3) so a 5 cm
crate stencil is not as expensive as the hero sign.

- The random `skip` pixel-dropping wear pass is gone: wear now lives in the material, so a sign can
  never lose the pixel that separates A from H or R from K. `lib_map.text_boxes()` is kept but
  marked deprecated and forces `skip = 0`; nothing calls it any more.
- Converted: FALLOUT SHELTER over the blast door, the civil-defence plate on the wing wall
  (`lib_clutter.fallout_sign`), SCHOOL BUS ×3 and STOP on the bus (`lib_vehicles`), and the
  DOOM TOWN / POP. 412 town sign (`build_street.sign_doom_town`, which was previously random dark
  bars pretending to be routed letters).
- New flat stencil-paint materials (`paint_stencil_w/y/k/r`) so letters are not cube-projected into
  a 1.5 m rusted-metal tile, and they are excluded from the 13 mm bevel pass that was rounding the
  old letter-boxes into blobs.

## #10 — no glass anywhere — **fixed (asset side)**

`lib_materials.FLAT` — `glass` is now `color (0.35, 0.40, 0.44)`, `roughness 0.055`, `alpha 0.26`;
`glass_car` is `alpha 0.42`. A new `_blend()` helper sets the Principled alpha and the material's
blend method, and the exporter writes `alphaMode: BLEND` with the alpha in `baseColorFactor`
(verified in the exported GLB, see `validate.py`'s new alphaMode line). `map.js` already pushes
`envMapIntensity` to 1.9 for `/glass/` materials and sets `depthWrite = false` when
`opacity < 1`, so the west-facing windows now take the sunset without extra game-side work.

Also: two ground-floor windows per house are now intact panes rather than shards (so there is
something for the low sun to reflect off), and there is a scatter of glass chunks on the floor
under the smashed ones. Puddles keep the opaque `glass_dark` — they are a floor, not a window.

## #18 — bunker read as a parking garage — **fixed**

`build_bunker.py`:
- The white parking stripes are gone. In their place: a faded yellow safety walkway (two lines), a
  real recessed drain channel with concrete kerbs and rusted grate bars down the centre (the loose
  rusty floor plates that read as random tiles are gone), and yellow/black hazard chevrons at the
  foot of the ramp and the generator bay.
- Shelter stores: two steel shelving bays with stencilled RATIONS / MEDICAL crates and ration cans,
  a first-aid cabinet with a red cross, four stencilled WATER drums along the north wall, rolled
  blankets on the bunks. All of it has `COL_PROP` collision and sits against the walls; the
  walking lanes stay ≥ 2.5 m.
- Civil-defence signage in real lettering: SHELTER CAPACITY 60, a radiation trefoil plate with
  SHELTER, NO SMOKING, AIR FILTRATION on the vent trunk, EXIT over the ramp opening, and SHELTER /
  LEVEL B stencils down the ramp cut.
- The unmotivated orange rust *splatter* on the walls and beams was the `concrete_bunker` material:
  its `rust` term is down from 0.75 to 0.28, and directional rust bleeding is now an authored decal
  placed under the pipe brackets instead.
- Authored decals throughout (see #8): water ingress at the ceiling joints, wash-down streaks,
  cracking, floor grime darkest at the walls, oil under the generator and the workbench, civil
  defence posters.

## #19 — street debris was flat untextured cards — **fixed**

`lib_clutter.debris_piece()` / `debris_field()` — eight archetypes with real volume: splintered
plank (with slivered ends and a bent nail), buckled sheet metal with a rolled edge, shingle bundle,
crumpled paper wad, stucco chunk with exposed lath, broken picket section, gravel cluster and a
bent bicycle wheel. Each is stamped with random pitch/roll so pieces sit on each other, and the
field thins out toward the blast centre and skips the wrecks and the spawn point. The two flat-card
scatters in `build_street.py` (52 + 46 boxes) are replaced by these.

## #20 — trees — **partial**

`lib_tree.py` already generated tapered, curving, forking limbs (the review's "bare cylinders at
right angles" describes an older asset). Improvements made: hero trees get a fourth twig
generation (background trees stay at three for budget), branch radii no longer collapse
(`0.60–0.80 ×` parent instead of `0.52–0.72 ×`), and a second variant — a snapped trunk with a
second low limb — alternates with the full-crown one so the three placed trees are not identical.
Not done: bark silhouette displacement on the trunk.

## #21 — interior furniture was flat-shaded boxes — **fixed**

`build_houses.py`:
- `_upholstered()` rebuilds the sofa and armchair: sprung base, front skirt, separate seat cushions
  with rolled fronts and a sag, separate back cushions, rolled arms and turned tapered legs.
- New woven `fabric_weave_r/o/b` materials (over-under weave, slubs, a fuzzy nap and grime) replace
  the flat `fabric_red` / `fabric_olive` on the sofa, bed, rug, curtains and every sandbag.
- The rug now has a woven border and a fringe; the bed gets a cloth pillow.
- Skirting boards now run along the interior walls as well as the perimeter, skipping door
  openings, and every interior opening gets a proper cased architrave (jambs + head).
- Fallen clutter: a toppled floor lamp, three knocked-down picture frames with their glass, a
  dropped drawer, broken glass under the smashed windows.

## #27 — backdrop buildings were identical silhouette prisms — **fixed**

`build_backdrop.py` — three roof archetypes (gable, hip with real end planes, shed) chosen per
house, three storey heights cycled across the twelve neighbours, and new skyline accents:
two farm windmills (splayed lattice tower, fan, vane), two leaning hoardings with torn paper, and a
grain silo with a lean-to.

## #8 — no authored decal dressing — **fixed (asset side)**

`lib_decals.py` generates ten RGBA decal textures procedurally (256², numpy value-noise fBm, written
straight to PNG — no bake, ~1 s for the whole library, cached on a version number): grime streak,
rust run, water stain, oil pool, soot fan, crack network, tyre mark, torn public-information
poster, floor/wall grime gradient and ground scorch.

`Scene.decal(name, centre, size, face, rot, lift)` stamps one as a single quad a few millimetres off
the surface, with its own 0..1 UVs (the cube-UV pass in `Scene.build()` skips `decal_*` banks).
They export as `alphaMode: BLEND` with `baseColorFactor` alpha 1.0, so `map.js` leaves
`depthWrite` on and they behave like proper decals.

Placed: bunker walls/ceiling/floor (streaks, water ingress, rust runs off the brackets, cracking,
grime at the skirting, oil, posters), the headhouse face, the ramp cut, house interiors (ceiling
leaks, cracks, grime, posters, soot off the barrier openings) and exteriors (wash-down under every
window), and the street (oil under every wreck, scorch under every fire, carriageway and kerb
cracking, and the skid marks — which used to be black boxes lying on the road — as tyre decals).
A `surf_z()` helper picks the right surface height so no ground decal ends up buried under the kerb.

The `[code]` half of #8 (a `staticDecal()` API driven from `MK_DECAL_*` markers) was not needed:
the decals are baked into the map asset instead, which costs the game nothing.

## #9 — visible tiling and no detail layer — **partial**

- Resolution: the three surfaces that were genuinely under-resolved are now 2048² —
  `asphalt`, `dirt`, `concrete_floor` (3 m tile: 341 → 683 px/m) plus `concrete_bunker`. The rest
  were already 460–680 px/m at 1024² and were left alone to stay inside the 60 MB file budget.
- `desert_far` was 55 m per tile (18 px/m — the featureless beige plane in the mystery-box shot);
  it is now 10 m.
- `wallpaper_*`: the motif lattice now gets a per-cell hash that fades each diamond independently
  and the motif contrast is down, so the print no longer stamps an identical diamond every 2.2 m.
- The authored decals above are the main tiling-breaker: the big surfaces now carry unique dirt.
- **Not done**: the shared detail-normal at 8–16× the base tile and the macro-variation mask. Both
  need a second UV set *and* a second texture multiplied into base colour, which glTF's single
  `baseColorTexture` cannot express — it would have to be a game-side shader patch (`[code]`),
  not a Blender change.

## Also fixed along the way

- **Opaque shadows on transparent materials.** The first build's check renders came back with hard
  black rectangles stamped across the road, the bunker walls and the house ceilings: the alpha
  helper had turned `use_transparent_shadow` off, so every 26 %-alpha window and every 1 cm decal
  quad cast a *fully opaque* shadow. It is on now (`shadow_method = 'HASHED'` as well, for EEVEE).
  This only ever affected the Blender check renders, never the shipped GLB — but it is exactly the
  kind of thing that would have made the renders lie about the result.

- `sign_paint` was referenced by the road centre line (and the old bunker stripes) but never existed
  in the material registry, so those meshes exported with **no material at all**. Added, and
  `Scene.build()` now prints a warning for any bank whose material name is missing.
- `validate.py` additionally reports the `alphaMode: BLEND` material list and warns if glass or the
  decals lost their transparency in export.
- `build_map.py` takes `--w=` / `--h=` so check renders can be run at 960×540 as required.

## Numbers

`public/models/map_doomtown.glb` — **50.31 MB** (limit 60), **533 051 triangles** (limit 1 500 000),
87 visual meshes, 142 `COL_*`, 8 `ZONE_*`, 59 `MK_*`, 3 `DOOR_*`, 64 materials, 121 images.
`validate.py` → `RESULT: PASS`, with `alphaMode BLEND` on `glass`, `glass_car` and all ten
`decal_*` materials. Was 37.9 MB / 440 109 tris before this stream.

Check renders in `renders/map/` current as of the repair round (960×540 / 24 samples):
`bunker_pap`, `bunker_room`, `bunker_ramp`, `bunker_door`, `south`, `start_wide`, `kerb`, `tree`,
`green_living`, `bus`, `bus_front`. Also current from the round before it: `start`, `yellow_living`,
`topdown_bunker`. The remaining files in that folder (`car_*`, `dummies`, `neighbours`, `topdown`,
`yellow_kitchen`, `yellow_bed`, `green_bed`, `bunker_over`, …) are from the previous stream and are
**stale**. Re-run
`sh tools/blender/run_locked.sh tools/blender/map/build_map.py --renders --samples=28 --w=960 --h=540`
to refresh the full set (note: rendering the whole set in one Blender process hit a GPU
out-of-memory once while another agent's job was running — render in batches with `--only=`).

## Repair round (adversarial verifier)

**1. The drain channel was not recessed — fixed.** The verifier was exactly right: `bm_box` takes
*full* dimensions, so the "channel floor" (centre `BZ-0.055`, height `0.12`) had its top 5 mm
*above* the floor, the kerbs stood 10 mm proud, and the grate bars' top sat exactly at `BZ` —
buried inside the channel slab and coplanar with the floor plane. It rendered as a flat black
stripe, which is what it was.
The floor slab is now cast in three pieces: two walking slabs (`|x| >= 0.22`) whose inner faces
form the channel cheeks, and a sunk invert 0.17 m below the walking surface. The grate is a run of
`steel_paint` bars 6 mm *below* the walking surface (no coplanar faces anywhere) with a 12 cm dark
void visible between them, plus cross ties down in the invert. `COL_FLOOR_bunker` is unchanged, so
the player still walks at `BZ` across it. The ramp-foot chevron now skips the bars that would have
bridged the open channel.

**2. Bunker steelwork was still `metal_rust` — fixed.** New material `steel_paint`
(`painted_metal((0.165, 0.175, 0.170), wear 0.06, dirt 0.55)`): shop-painted steel where rust only
shows through paint chips, instead of `metal_rust`'s full-surface orange splatter. Applied to the
ventilation trunk and its flanges, the ceiling service pipes, the barrier-window frame, the ramp
handrails and stanchions, the anti-slip treads, the big ramp service pipe and the new grate bars.
Motivated rust is kept: the oil drums, the exposed portal frame, the small ramp pipe, the exhaust.
Rust is now *localised* — a small `rust` decal bleeds from each trunk flange.

**3. Oil decals read as holes — fixed.** `d_oil` had a hard edge (`smoothstep(0.33, 0.42)`) at
near-black. Now a wide soft falloff (`0.10 → 0.47`), overall alpha × 0.62 and the floor colour
lifted from 0.012 to 0.040, so it reads as oil soaked into concrete rather than a pit.

**4. Headhouse hazard striping — fixed.** `lib_clutter.hazard_band()` builds the band as stripes
*clipped to the band rectangle* (Sutherland-Hodgman against the four edges) and extruded as
prisms, so the band has straight edges and the stripes tile it exactly (verified numerically: 10
stripes covering 0.7820 m² of a 0.34 × 2.30 m band). The old version stacked 13 rotated boxes whose
corners poked out either side — hence "loose tilted tiles".

**5 / 6. Renders.** `bunker_pap`, `bunker_room`, `bunker_ramp`, `south`, `start_wide`,
`green_living`, `kerb`, `tree`, `bus`, `bus_front` were all re-rendered from the same Blender run
that produced the shipped GLB (960×540, 24 samples), so the images and the export match.
`bus` / `bus_front` prove the SCHOOL BUS flank + tail lettering and the STOP arm.

**Nice-to-haves.** Weave tile 0.9 m → 0.55 m on all three `fabric_weave_*` materials, so the
cube-projected weave reads at the same density on the sofa and the armchair despite their 90°
orientation difference. Wallpaper tile 2.2 m → 2.95 m: roughly a third fewer whole repeats across a
wall (this is a UV-scale change only — no re-bake, and the 2048² map keeps ~695 px/m).

## Known gaps / what a reviewer will still find

- Tiling is reduced, not solved. The shared detail-normal and the macro-variation mask (#9b/#9c)
  need a second UV set multiplied into base colour, which glTF cannot express — that one is a
  game-side shader job.
- Ten decal types is a starter set. Bunker walls carry 5–8 overlapping decals each, house walls 3–4;
  BO2 would run 10–20 with more variety (posters with real artwork, stencils, splashes).
- The debris archetypes are procedural, not sculpted: the stucco/gravel chunks are low-subdivision
  lumps and read as lumps close up.
- The backdrop houses now vary in roof, height and yaw but still share one siding palette.
- Trees are better but the trunks have no bark silhouette.

## Contract

`COL_*`, `ZONE_*`, `MK_*` and `DOOR_*` names and positions are untouched — no marker, zone or
collider was moved, renamed or removed. New solid props (shelving, cabinet, water drums) are
against walls and carry their own `COL_PROP` boxes; the narrowest new lane is ≥ 2.5 m. Debris
pieces are loose litter under 0.3 m and deliberately carry no collision.

---

## Second storey, back yards, and the coplanar-flicker audit

### What was added

- **Staircases.** `build_houses.staircase()` — a straight flight against the middle of each hall,
  house-local lx 7.78..9.22 (1.44 m wide), climbing +ly from ly −0.55 (z 0) to ly 4.75 (z 3.02).
  Visual treads with nosings, risers, a carpet runner with stair rods, closed stringers, a plaster
  soffit, newels, a raking banister and a wall rail. Collision is one `col_ramp`
  (`COL_STAIR_yellow` / `COL_STAIR_green`), 1.50 m wide at **27.8°**.
- **Buyable debris at the foot** — `DOOR_<side>_stairs` (tipped wardrobe, dresser, bed frame, nailed
  planks, rolled rug, plaster dust), `COL_DOOR_<side>_stairs` (ly −0.25..1.30, z 0..2.60),
  `MK_DOOR_<side>_stairs` on the ground-floor side.
- **Upstairs** — `build_houses.upstairs()`: a landing round the stairwell, two bedrooms, a back
  bedroom, a bathroom (lino, clawfoot tub, toilet, basin, mirror cabinet, shower rail) and a box
  room, all with wallpaper, skirting, cased openings, seven ceiling fittings, and a ruin pass
  (fallen plaster, exposed lath, water stains, cracks, soot, a torn poster). A `ZOff` proxy round
  the `Scene` lets the ground-floor furniture builders be reused at z = 3.02 unchanged.
  `floor_deck()` casts the ground-floor ceiling *and* the upstairs deck with the stairwell punched
  out of both, plus trimmer beams and a landing balustrade.
- **Back doors** — `DOOR_<side>_back` / `COL_DOOR_<side>_back` / `MK_DOOR_<side>_back`, a
  1.8 × 2.30 m opening in the back wall with a casing, a concrete stoop and a hanging fly screen.
- **Utility wing** (`utility_wing()`) — a single-storey flat-roofed garage against each back wall
  (lx 11.10..15.30, ly 3.70..7.70) whose deck is exactly at the upstairs floor, so the new upstairs
  barrier window `yu1`/`gu1` has a 0.9 m sill above it. One solid `COL_WING_<side>` gives the roof
  as a walkable pocket and 3 m of blank wall on every other face, so the player can never reach it.
- **Back yards** — new `build_yards.py`: tall board fences with collapsed sections and chain-link
  patches, ≥ 4 m boundary collision, `COL_FLOOR_yardw` / `COL_FLOOR_yarde`, dead-lawn patches, a
  clothes line with rags, a garden shed, a burnt swing set, a dug-up bomb-shelter hatch with spoil,
  garden furniture, an incinerator drum, a wheelbarrow, bins, a woodpile, gas bottles, a vegetable
  patch and blast debris.
- **New markers/zones** — `ZONE_yellowup`, `ZONE_greenup`, `ZONE_yardw`, `ZONE_yarde` (plus a
  fourth yard box over each wing roof so the nav probe sees the spawn pocket, and a new
  `ZONE_bunker` box over the sealed service tunnel where `MK_SPAWN_WIN_bw1` already stood);
  `MK_BARRIER_yu1/gu1`, `MK_SPAWN_WIN_yu1/gu1`, `COL_BARRIER_yu1/gu1`;
  `MK_SPAWN_GROUND_yardw_1..3` / `yarde_1..3`; `MK_BOX_5..8`.
  `ZONE_yellow`/`ZONE_green` now stop at z 2.88 so they never overlap the upstairs zones.

### The chimney was standing in the new stairwell

`chimney()` put a 0.95 m brick stack at house-local (8.4, 3.4) — dead centre of the staircase and
the stairwell opening. It is now on the living-room gable wall at (5.60, −5.75), it has the
fireplace it always implied (firebox, hearth, brick jambs, timber mantel, charred logs) and, for
the first time, collision on both floors. The upstairs dresser that clashed with it moved too.

### Bunker ramp: `COL_FLOOR_street` was an invisible ceiling over the trench

The street floor collider was one box spanning the whole cul-de-sac at z = 0, including the open
ramp cut (x ±1.6, y 11.6..17.05), so a player walking up the ramp hit it at head height and had to
jump onto it. It is now cast in three pieces with x ±1.8, y 11.60..13.30 cut out. `COL_RAMP_bunker`
already reached z = 0 exactly at y = 11.60 and `COL_FLOOR_entry` carries the flat landing in front
of it, so there is no lip and no pit at the head. `validate.py` now samples 40 stations down the
ramp and fails if any `COL_*` box sits within 2 m above the ramp surface, and checks the ramp head
still has a floor.

### Flicker: the coplanar audit

New `tools/blender/map/audit_coplanar.py` (run with `build_map.py -- --audit`). It buckets every
axis-aligned face in the scene by its plane and reports overlapping pairs **from different meshes**
— two different material banks on one plane are two draw calls the depth buffer cannot separate,
and the renderer only gives decals a polygonOffset. First run: **255 plane pairs, ~1900 m²**. Now:
**186 pairs, ~250 m²**, and everything left is either underground or mutually occluded.

Fixed:

| what | where | fix |
|---|---|---|
| every wall built with an `inner_mat` (all house walls, both storeys, the wing): outer and inner leaf butted exactly, ~500 m² of siding/wallpaper/plaster on one plane | `lib_map.Scene.wall` | inner leaf grown 2 mm into the outer one |
| two decals on one wall fighting each other | `lib_map.Scene.decal` | each decal gets its own sub-millimetre lift step |
| hundreds of prop boxes whose bottoms sat exactly on z = 0 (wardrobes, crates, skirting, wall slabs) — this is the "flickering environment props" the report was about | `build_street.ground`, `build_houses` sub-floor, `build_bunker` floor slabs | ground planes dropped 4–5 mm below the collision floor; props now float invisibly above them |
| the kerb: pavement and kerb rings shared the `kerb_out` outline, so a coincident vertical face ran the whole length of the cul-de-sac, plus a coincident underside | `build_street.ground` | pavement tucks 2 cm under the kerb and sits 1 cm lower |
| upstairs deck / ground ceiling / bathroom lino / upstairs ceiling slab all flush with their neighbours | `build_houses.floor_deck`, `upstairs` | 4–15 mm overlaps instead of butt joints |
| stairwell trimmer beams flush with the cut edges of the deck and ceiling | `floor_deck` | inner faces 1 cm inside the opening, tops 1.5 cm inside the deck |
| stair soffit flush with the stringers | `staircase` | soffit 3 cm narrower, tucked between them |
| interior skirting boards flush with the wall face | both `skirt()` helpers | offset `IT/2 + 0.022` so they overlap 3 mm |
| shelf-unit back panel coplanar with its side panels | `shelf_unit` | back panel moved inside |
| backdrop rake boards flush with the roof slab's gable edge (84 m²) | `build_backdrop.ruined_house` | boards 0.16 thick so they stand proud |
| bunker ramp floor slab edges flush with the retaining walls (35 m²) | `build_bunker.ramp` | slab 8 cm wider, tucked under them |
| yard lawn patches: 26 + 18 discs per yard all at one height, 367 m² of mutual z-fight | `build_yards.build_yard` | each patch gets its own top and bottom height |
| skid-mark decals on the scorch discs | `build_street.clutter` | lifted to 0.028 |
| the wing's wash-down streak decal was stamped inside the upstairs barrier opening and rendered as a hanging sheet | `utility_wing` | moved beside the window |

Left alone (reported but invisible): the underside pairs of the road/pavement slabs and the lawn
discs (buried), the bunker ceiling/floor interface, the bus panels and two distant `BG_*` pairs.

### Budget

Adding a whole storey and two yards pushed the file to 65.7 MB, over the 60 MB limit. Recovered by
not bevelling `charred` (a 0.02-albedo matte material — the bevel highlight is invisible on it and
it was the two biggest meshes in the file), thinning the far desert scatter, and dropping WEBP
quality from 82 to 76.

`public/models/map_doomtown.glb` — **53.69 MB** (limit 60), **637 459 triangles** (limit 1 500 000),
88 visual meshes, 280 `COL_*`, 19 `ZONE_*`, 77 `MK_*`, 7 `DOOR_*`.
`python tools/blender/map/validate.py` → `RESULT: PASS`.
`node tools/tests/nav_realmap.test.mjs` → 9 passed, 0 failed (22/22 spawns reach the player; with
every door open all 22 spawns reach all 15 gameplay markers).

New check renders (960×540, 26 samples): `yellow_stairs`, `green_stairs`, `yellow_up`, `green_up`,
`yellow_bed_up`, `green_bed_up`, `yellow_bath_up`, `yellow_box_up`, `yellow_back`, `yellow_yard`,
`yellow_yard2`, `green_yard`, `yard_wide`, `topdown_yardw`, `yellow_pocket`, `green_pocket`.

### Follow-up after in-game testing: choked doorways, upstairs lamps

**The blocking bug.** The kitchen → hall doorway (spine wall `WA`, house-local ly 3.90…5.70) was
flanked by the kitchen shelf unit (ly 3.90…4.80) and the fridge (ly 5.375…6.125), leaving a 0.575 m
slot. Zombies are 0.7 m across and the player 0.64 m, so anything routed through it wedged forever.
The in-game harness reproduced it exactly — 2 of 15 spawns failed at three (−16.7, 0, −5.1) for
yellow and 7 of 15 at (16.7, 0, 5.1) for green.

Auditing every doorway on both floors of both houses found **14** of the 30 wall gaps under 1.0 m
of clear width, not one. All fixed by moving furniture, not by shrinking doorways:

| doorway | was blocked by | moved to |
|---|---|---|
| ground `WA` ly 3.90…5.70 (kitchen ↔ hall) | kitchen shelf unit (5.6, 4.35) | (0.95, 1.95), against the `WB` wall |
| ground `WA` ly 3.90…5.70, hall side | crate stack (6.75, 4.55) | (0.75, 0.55), living room |
| ground `WA` ly −4.20…−2.40 (living ↔ bedroom) | TV console (5.5, −3.2) — 0.22 m clear | (5.55, −0.85) |
| ground hall lane beside the stair | hall dresser (6.60, 1.90) — 0.92 m | (6.45, 1.90) |
| upstairs `UWA` ly −4.20…−2.80 | A1 wardrobe (5.55, −3.30) **and** bedroom-B bed (7.45, −3.55) — 0.00 m clear | wardrobe → (0.60, −3.55); bed → (8.90, −3.60) |
| upstairs `UWA` ly 3.90…5.30 (landing ↔ bathroom) | toppled bookcase (6.70, 5.70) — 0.95 m | bookcase → (9.95, −0.60) |
| upstairs `UWB` lx 1.40…2.90 | second child's bed (1.55, 0.55) — 0.06 m | bed → (4.30, 0.55), cot → (5.45, −1.85) |
| upstairs `UWD` lx 3.60…5.10 | toy chest (4.60, −1.95) + desk (3.10, −0.75) — 0.50 m | chest → (5.40, −0.60), desk → (2.30, −0.75) |
| upstairs `UWE` ly 2.20…3.60 | sewing table (2.55, 2.60) and the basin (3.85, 2.30) — 0.45 m | table → (2.40, 5.00), basin → (4.70, 2.20), mirror → (4.70, 1.78) |
| upstairs landing lanes (1.51 m west, 1.67 m east) | linen cupboard and hall table each left < 1.0 m | cupboard → (6.60, 5.60), hall table 0.40 m deep at lx 10.66 |

**New `validate.py` check — `check_doorways()`.** `COL_WALL` slabs are emitted one per wall
segment, so a doorway is just the gap between two consecutive slabs of the same wall line (grouped
by thin axis, plane and base height, which keeps the ground and upstairs walls apart). For each gap
≥ 1.2 m it takes a corridor 1 m deep on each side of the wall, projects every `COL_PROP` /
`COL_COLUMN` / `COL_SANDBAG` / `COL_TREE` / `COL_SIGN` / `COL_PORCHPOST` that reaches into the
0.30–1.50 m band on to the wall axis, and fails if the widest free run is under 1.0 m. Floors,
ramps, walls, removable `COL_DOOR_*` blockers and `COL_BARRIER_*` fillers are not obstacles. It
also fails on any wall gap between 0.05 m and 1.2 m (a doorway too narrow to be one). 30 doorways
are checked; it reported all 14 failures on the broken build and none on the fixed one.

**Upstairs lights.** The six upstairs ceiling fittings per house now have real `MK_LAMP_13…24`
markers (bulb at `UP_CEIL − 0.26` = 5.46). `UP_LIGHTS` dropped from seven fittings to six so the
total lands exactly on the raised cap. `validate.py`'s `MK_LAMP` cap is 12 → **24** (the game's
LightPool only lights the nearest N sites per quality tier, so extra markers cost nothing);
`MK_FIRE` stays at 9 of 10. The render harness no longer adds preview fills upstairs — the markers
drive real lights now.

**Verified**

- `python tools/blender/map/validate.py` → **PASS** (30 doorways checked, all clear).
- `node tools/tests/nav_realmap.test.mjs` → **9 passed, 0 failed**.
- `node tools/tests/cdp_run.mjs "http://127.0.0.1:5174/?norender" …/spawn_up2.js` → **30/30 reach**
  the player standing upstairs in each house, worst case **31.0 s** (limit 45 s), no errors.
  Before the fix: 9 of 30 failed.
- 53.67 MB, 637 027 tris, 89 `MK_*`.
- New check renders: `green_kitchen` (the doorway that was blocked), `yellow_a2_up`, plus refreshed
  `yellow_living`, `yellow_kitchen`, `yellow_up`, `yellow_bed_up`, `yellow_bath_up`, `yellow_box_up`.
