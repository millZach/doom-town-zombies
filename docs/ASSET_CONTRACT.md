# Asset contract — "Doom Town" zombies

Browser survival shooter in the style of Black Ops 2 Zombies (Three.js r186, single-player, desktop).
Every 3D asset is authored by a Python build script run in **headless Blender 5.2** and exported
to `public/models/*.glb`. The game loads assets by the file names, node names and clip names below —
treat them as an API. If an asset is missing the game falls back to a placeholder, so partial
delivery is fine, but wrong names silently break things.

**No copied assets.** Everything is original, built from scratch. Match the *feel* of BO2 (gritty,
realistic, weathered, high-contrast lighting), not its exact designs or logos.

## Tooling

- Blender: `"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python <script>`
- Shared helpers: `tools/blender/common.py` (`reset_scene`, `box`, `empty`, `pbr_material`, `bake_tileable`,
  `preview_render`, `export_glb`, …). Import it with
  `sys.path.insert(0, <path to tools/blender>)`. Extend it only by adding new functions to *your own*
  module (e.g. `tools/blender/map/lib_map.py`) — other agents are using `common.py` concurrently.
- Build scripts live in `tools/blender/<area>/build_*.py` (areas: `map`, `characters`, `weapons`, `props`).
  The script is the asset; the .glb is a build artefact. Scripts must be re-runnable from scratch.
- Check renders go to `renders/<area>/` (≤1280×720, Cycles GPU, ≤64 samples). **Look at every render
  with the Read tool and judge it critically** — change, render, look, correct.
- Verify each exported GLB with `node tools/inspect-glb.mjs public/models/<file>.glb --tree`
  (names, triangle counts, clips, skin joints).
- The GPU (RTX 5070 laptop) is shared by several agents rendering at once; keep renders small and
  sample counts modest, and don't leave long bakes running needlessly.

## Global conventions

- Units: metres, real-world scale. Blender Z-up; export with `+Y up` (the helper does). Blender
  (x, y, z) becomes three.js (x, z, −y).
- **"Front" = Blender −Y** (becomes three.js +Z). Characters, machines and props face −Y.
- Origin at the floor contact point (centre of the footprint) unless stated otherwise.
- glTF only exports Principled BSDF + image textures. **Procedural node materials must be baked**
  to image textures (`bake_tileable` for tiling surfaces, or a UV bake for unique objects) — never
  ship an asset whose look depends on unbaked procedural nodes (they export as flat colour).
- Don't leave stray colour attributes on meshes: GLTFLoader multiplies vertex colours into base colour.
- Realism bar: PBR with colour variation, grime, edge wear, dirt near the ground, roughness variation
  and normal detail. Flat single-colour surfaces read as placeholder. Bevel hard edges that catch light.
- Emissive parts (lights, logos, eyes, glows) use a material whose **name contains `glow`**; the game
  drives their intensity (power on/off, flicker).
- Keep textures ≤2048² (1024² for small props). Prefer `export_image_format='WEBP'` or JPEG to keep
  files small. Budgets: map ≤ 60 MB and ≤ 1.5M tris; character ≤ 25k tris per variant; weapon ≤ 25k
  tris including arms; props ≤ 20k tris each.

## Art direction

1950s Nevada atomic-test-site suburb ("Doom Town") at an apocalyptic dusk: burnt-orange and ash-grey
sky, smouldering fires, scorch marks, blown-out windows, mannequins, pastel 50s houses (one faded
mustard-yellow, one faded mint-green) with peeling paint, rusted cars and a burned-out school bus.
Gritty realism, not cartoon. The game adds lighting, fog, fire particles, bloom and colour grading.

---

## 1. Map — `public/models/map_doomtown.glb` (area `map`)

Coordinates below are Blender (X east, Y north, Z up). Layout is a guideline; exact placement is the
map builder's call, **markers are the contract**.

### Layout (ten zones)

| zone id | what | notes |
|---|---|---|
| `street` | start area: cul-de-sac street between the houses, ~X −12…12, Y −22…16 | open air, zombies rise from the ground |
| `yellow` | **ground floor** of the yellow house, west (~X −24…−12, Y −7…7) | front door faces the street (east wall) |
| `green` | **ground floor** of the green house, east (mirror, ~X 12…24) | front door faces the street (west wall) |
| `yellowup` | first floor of the yellow house: landing, two bedrooms, box room, bathroom | reached by the staircase behind `yellow_stairs` |
| `greenup` | first floor of the green house (mirror) | reached by the staircase behind `green_stairs` |
| `yardw` | fenced back yard of the yellow house: behind it (X −30…−22.6) plus both side strips (Y ±7…13.5) | reached through `yellow_back`; holds `yw1`/`yw2` window spawns |
| `yarde` | fenced back yard of the green house (mirror, X 22.6…30) | reached through `green_back`; holds `gw1`/`gw2` window spawns |
| `bunker` | fallout shelter north of the cul-de-sac, floor at Z = −2.5, reached by a ramp/stairwell | concrete, industrial, holds Pack-a-Punch and the power switch |

- Street ↔ yellow via buyable door `yellow_front`, street ↔ green via `green_front`, street ↔ bunker via
  `bunker_door`. Each house also has two more buyable doors: `<side>_stairs` (a debris pile at the
  foot of the staircase, opening the first floor) and `<side>_back` (the back door into its yard).
- **Every walkable floor in street/yellow/green/yardw/yarde is at Z = 0** (terrain may undulate
  ±0.1 m away from doors and windows). Houses have a slab floor at Z = 0; the porch step can be
  decorative. The two first floors are at **Z = 3.02** with a 2.70 m ceiling above them.
- **Multi-level:** walkable surfaces may now stack — a house first floor over its ground floor, and
  the utility-wing roofs that serve the upstairs barrier windows. The navigation grid is layered, so
  the rules are:
  - **Headroom ≥ 1.75 m** above every walkable surface, measured to the underside of whatever is
    above it. Floor-to-floor 2.7–3.0 m is safe.
  - **At most 4 stacked walkable surfaces per 0.5 m cell** (floor + prop tops count).
  - `ZONE_*` boxes must enclose every walkable surface **in Z as well as XY** — the probe only runs
    from `max Z + 0.5` down to `min Z − 1.5`, so a zone has to be tall enough to cover porches,
    steps and prop tops inside it.
  - The ground-floor `ZONE_yellow`/`ZONE_green` boxes must end **at or below** the first-floor level
    and `ZONE_yellowup`/`ZONE_greenup` must start **exactly at** it (Z = 3.02); they must not
    overlap vertically.
  - Nothing walkable may sit above the bunker — it stays under a mound/berm the player can't climb.
- Stairs/ramps: the *collision* is a smooth `COL_*` ramp, **≤ 32°**, ≥ 1.0 m wide (the house
  staircases are 1.44 m of visual tread over a 1.50 m ramp at 27.8°), meeting both floors within
  0.4 m of their heights. Visual treads/risers/banister are separate geometry from the ramp; if a
  collision mesh ever uses real steps instead, risers ≤ 0.45 m and treads ≥ 0.5 m deep.
  **No `COL_*` may sit within 2 m above the bunker ramp surface** — `COL_FLOOR_street` is cut out
  over the open trench (X ±1.8, Y 11.6…13.3) so the ramp is not capped by an invisible slab, and
  the ramp's top edge meets street level flush (≤ 0.1 m lip, no gap).
- The first floors are playable: bedrooms, a landing, a bathroom and a box room, dressed like the
  ground floor, walking lanes ≥ 1.4 m, ceiling ≥ 2.5 m. The upstairs ceiling/roof is **not** in COL.
- Every new area needs at least one seed marker standing on its floor (not on furniture):
  `MK_SPAWN_GROUND_*`, `MK_BARRIER_*`, `MK_PERK_*`, `MK_BOX_*`, `MK_WALLBUY_*`, `MK_DOOR_*` or `MK_PAP`.
- The playable area is enclosed by fences, rubble, cars and house walls, all backed by tall invisible
  collision (≥ 3 m) so the player can never leave. Beyond it: yards, more ruined houses, power poles,
  desert, distant mesas/mountains (visual only, `BG_*` meshes, low-poly is fine at distance).
- Iconic set dressing: burned-out school bus parked askew in the street, a rusted pickup, picket fences,
  mailboxes, 50s mannequins, fire barrels, craters, scattered debris, street lamps, a sign
  "DOOM TOWN — POP. 0".
- Interiors: 50s furniture (sofa, kitchen counters, fridge, table, TV, lamps), wallpaper, wood
  floors, broken plaster, debris — dense enough to feel lived-in, but keep ≥ 1.6 m wide walking lanes.
- **Doorways must stay clear.** Every gap in a `COL_WALL` line — interior doorway, passage or
  exterior door opening — needs **≥ 1.0 m of continuous clear width** through it, measured over the
  0.30–1.50 m height band and within 1 m of the wall on both sides. A zombie is 0.7 m across and the
  player 0.64 m, so anything narrower wedges them permanently. `validate.py` finds every such gap
  and fails on any `COL_PROP`/`COL_COLUMN`/`COL_SANDBAG`/`COL_TREE`/`COL_SIGN`/`COL_PORCHPOST`
  that eats it. Furniture goes against walls between doorways, never in front of them.

### Collision and gameplay nodes (exact names)

- `COL_*` — collision meshes, simple boxes/ramps, hidden in-game. Must cover every walkable floor
  (street ground, house floors, ramp, bunker floor) and every obstacle/wall. **No ceilings or roofs
  in COL.** Wall/boundary colliders ≥ 3 m tall.
- `COL_DOOR_<doorId>` — blocker for each buyable door, removed when bought. The visual door is
  `DOOR_<doorId>` (a mesh or empty with mesh children; the game animates it away). Door openings
  ≥ 1.4 m wide, ≥ 2.2 m tall.
- `COL_BARRIER_<id>` — box filling each barrier window so the player can't climb through.
- `ZONE_<zoneId>` — one or more box meshes per zone covering its walkable volume (hidden in-game; used
  for "which zone is the player in"). Multiple boxes: `ZONE_street`, `ZONE_street.001` is fine —
  the game reads the prefix up to the first `.`.
- Empties (`MK_*`). Orientation matters where stated: the empty's **local −Y axis** is its "facing".

| marker | count | meaning |
|---|---|---|
| `MK_PLAYER_START` | 1 | street, facing (−Y) toward the action |
| `MK_SPAWN_GROUND_<zone>_<n>` | street 6–8, bunker 2, `yardw` 3, `yarde` 3 | zombie rises from the ground here; open dirt/grass, out of the player's direct start view, ≥ 1.5 m from walls. The **zone id is the 4th `_`-separated token**, so it may not contain an underscore |
| `MK_BARRIER_<id>` | yellow `yw1`,`yw2`,`yu1`; green `gw1`,`gw2`,`gu1`; bunker `bw1` | window barricade: at the **sill centre**, on the wall's middle plane, −Y facing **into the playable zone**. `yu1`/`gu1` are upstairs, in the back wall, sill at first floor + 0.9 m |
| `MK_SPAWN_WIN_<id>` | one per barrier | where the zombie for that barrier spawns: 3–6 m outside the window, out of sight of players, on ground at the floor level of the window's outside. `yu1`/`gu1` spawn on the flat roof of the utility wing, at the first-floor level |
| `MK_DOOR_<doorId>` | 7 | interaction point in front of each buyable door, on the side the player buys it from: `yellow_front`, `green_front`, `bunker_door` (street side), `yellow_stairs`, `green_stairs` (ground-floor side of the staircase), `yellow_back`, `green_back` (inside the house) |
| `MK_WALLBUY_<weaponId>` | 5 | on a wall surface ~1.4 m up, 2 cm off the wall, −Y pointing out of the wall. `m14` + `olympia` in street (e.g. on house exterior walls/garage), `mp5` in yellow, `remington870` in green, `ak74u` in bunker |
| `MK_PERK_<perkId>` | 4 | floor spot for a vending machine (1.2 w × 0.9 d × 2.3 h), −Y = machine front. `quickrevive` street, `speedcola` yellow, `juggernog` green, `doubletap` bunker |
| `MK_BOX_<n>` | 8 | mystery box spots (1.8 w × 0.8 d clearance, −Y = front): 1 street, 2 yellow, 3 green, 4 bunker, 5 yardw, 6 yarde, 7 yellowup, 8 greenup |
| `MK_PAP` | 1 | Pack-a-Punch machine (2.2 w × 1.2 d), bunker |
| `MK_POWER` | 1 | power switch mounted on a bunker wall, ~1.3 m up, −Y out of the wall |
| `MK_LAMP_<n>` | ≤ 24 | a real light source position (street lamp bulb, porch light, indoor/upstairs ceiling fitting). The game lights only the nearest N by quality tier, so extra markers are free |
| `MK_FIRE_<n>` | ≤ 10 | base of a fire (burning barrel, car fire, debris fire); the game adds flames + flickering light |

**Barrier windows**: an opening exactly **1.2 m wide × 1.1 m tall with the sill at floor + 0.9 m**
through the exterior wall. The game places `barricade.glb` (below) at `MK_BARRIER_<id>`. The ground on
the outside must be flat for ≥ 1.2 m at the same level as the floor inside (zombies climb straight
through: they stand 0.6 m outside the wall plane and land 0.8 m inside it). The outside area where
`MK_SPAWN_WIN_*` sits must be unreachable by the player but walkable from the spawn to the window.

For the two **upstairs** barriers (`yu1`, `gu1`) that outside area is the flat roof of a
single-storey utility wing built against the house's back wall: its deck is exactly at the
first-floor level (Z = 3.02) so the sill is 0.9 m above it, it is walkable `COL_*` from
`MK_SPAWN_WIN_<id>` all the way to the window with ≥ 1.2 m of flat roof either side, and it is a
sheer 3 m wall on every other face — no walkable surface connects to it, so the player can never
get up there.

**Coplanar geometry / flicker.** Two surfaces on the same plane that overlap will z-fight. The
renderer only applies `polygonOffset` to decals, so everything else has to be separated: props
never sit exactly on a floor plane (ground planes are 4–5 mm below Z = 0 for that reason), trim
and panels overlap their host rather than butting flush, two decals on one wall never share a
lift, and rugs/patches lying on the same surface each get their own height. Run
`build_map.py -- --audit` to list every cross-mesh coplanar overlap in the scene.

---

## 2. Characters (area `characters`)

### `public/models/zombie.glb`

- One armature (`Armature`) with bones **named exactly** (underscores, no dots):
  `root, hips, spine, chest, neck, head, shoulder_L, upperarm_L, forearm_L, hand_L, shoulder_R,
  upperarm_R, forearm_R, hand_R, thigh_L, shin_L, foot_L, toe_L, thigh_R, shin_R, foot_R, toe_R`
  (extra finger/jaw bones allowed). `root` sits at the origin on the floor.
- Height ≈ 1.8 m, origin between the feet, facing −Y, rest pose A- or T-pose.
- Three visual variants skinned to the same armature, each split into body + head:
  `body_A`/`head_A` (1950s townsman: torn white shirt, suspenders, grey slacks), `body_B`/`head_B`
  (housewife: tattered floral dress, apron), `body_C`/`head_C` (soldier: olive fatigues, webbing).
  The game shows one variant per zombie and hides `head_X` when a headshot pops the head, so the
  neck stump underneath should read as gore, not a hole into the void.
- Rotting skin, exposed wounds, blood, dirt; torn cloth silhouette. Eyes: small emissive mesh(es)
  `eyes_A/B/C` with material named `eye_glow` (bright orange-yellow).
- Clips (glTF animation names exactly; in-place unless stated; 30 fps):

| clip | loop | notes |
|---|---|---|
| `idle` | yes | swaying, twitchy |
| `walk` | yes | slow asymmetric shamble, ~0.9 m/s, arms low/forward (report stride speed) |
| `run` | yes | lurching jog, ~2.6 m/s, arms out |
| `sprint` | yes | frantic full sprint, ~4.2 m/s |
| `attack` | no | two-handed swipe, ~0.9 s, contact at ~45% |
| `tear` | no | grabbing and ripping a board toward itself (reaching forward ~0.6 m at hand height 1.2 m), ~1.2 s |
| `climb` | no | climbing through a window (sill 0.9 m): starts standing 0.6 m outside the wall facing it, ends standing 0.8 m inside. **Root-motion in the clip on the `hips`/`root` bone: +1.4 m forward (−Y)**; ~1.8 s |
| `rise` | no | clawing up out of the ground: starts fully below ground (hips ≈ −1.4 m), ends standing; vertical motion in the clip; ~2.2 s |
| `death_1`, `death_2` | no | fall backward / crumple forward, end lying on the ground |
| `hit` | no | short flinch, ~0.35 s (upper body only is fine) |

### `public/models/hellhound.glb`

Charred, emaciated demonic dog ~0.85 m at the shoulder, glowing `eye_glow` eyes, origin at feet,
facing −Y. Bones free-form but include one named `head`. Clips: `idle`, `run` (loop, ~7 m/s),
`attack` (lunge + bite, ~0.8 s), `death`.

---

## 3. Weapons (area `weapons`)

First-person **viewmodels with arms**, one GLB per weapon: `public/models/weapons/<id>.glb`.

| id | name | type |
|---|---|---|
| `m1911` | M1911 | .45 pistol (starting weapon) |
| `olympia` | Olympia | side-by-side double-barrel shotgun, wooden stock, break action |
| `m14` | M14 | wooden-stock semi-auto rifle |
| `mp5` | MP5 | SMG |
| `remington870` | Remington 870 | pump shotgun (object `pump`) |
| `ak74u` | AK-74u | compact carbine |
| `galil` | Galil | assault rifle |
| `rpd` | RPD | belt-fed LMG with drum |
| `python` | Python | .357 revolver (object `cylinder`) |
| `raygun` | Ray Gun | retro 1950s sci-fi pistol: red/cream body, glowing green tube (material `glow`) |
| `knife` | knife | right arm holding a combat knife, blade forward, framed for a slash |
| `frag` | frag grenade | right hand holding a frag grenade |
| `drink` | perk bottle | right hand holding a generic glass soda bottle: bottle glass, liquid material `bottle_liquid`, label material `bottle_label` (the game tints both per perk) |

**Camera-space authoring.** Blender origin = the player's eye. The camera looks along **Blender +Y**
(three −Z), up = +Z. Model everything where it should appear on screen in hip fire with a **50°
vertical FOV at 16:9**: weapon in the lower right, barrel angled slightly toward screen centre, arms
entering from the bottom edge. Verify with a check render from a camera at the origin
(`rotation_euler = (90°, 0, 0)`, sensor fit vertical, 50° FOV, 1280×720) — that render must look like
a finished shooter's hip-fire frame.

Hierarchy per GLB:

```
viewmodel          (empty at origin)
└─ weapon          (empty, origin at the grip — the game rotates/kicks the gun around this)
   ├─ <gun meshes>          any names; movable parts named mag / pump / cylinder / bolt / slide
   ├─ muzzle        (empty at the barrel tip; no rotation — the barrel points along +Y like the view)
   ├─ eject         (empty at the ejection port)
   ├─ aim           (empty at the rear sight / optic centre; the sight line must run parallel to +Y
   │                 so the game can align it with the view axis for aim-down-sights)
   ├─ arm_R         (right forearm + gloved hand gripping the gun; origin at the wrist)
   └─ arm_L         (left forearm + hand on the foregrip/under the barrel; origin at the wrist — the
                     game moves it for reloads, so it must be one separate object)
```

- Arms: dark olive field-jacket sleeves (rolled cuff), worn tan leather work gloves. Build one
  parametric hand (finger curl per finger) and reuse it; posed fingers must wrap the grip plausibly.
- The same GLB doubles as the **world model** (mystery box, wall-buy float): the game hides `arm_*`
  and uses the `weapon` node alone, so the gun must be complete without the arms.
- Materials: names containing `metal`, `wood`, `polymer` for gun parts; `sleeve`, `glove`, `skin` for
  arms. The game swaps gun (not arm) materials for an animated Pack-a-Punch camo.
- Real proportions: the M1911 is 0.22 m long, the M14 1.12 m. Believable detail: sights, rails,
  screws, knurling, trigger guards, slings mounts. Metal: blued/parkerised with edge wear; wood: grain
  with dark worn handling marks.

---

## 4. Props (area `props`) — `public/models/props/<name>.glb`

| file | contents |
|---|---|
| `perk_juggernog.glb`, `perk_speedcola.glb`, `perk_quickrevive.glb`, `perk_doubletap.glb` | 1950s soda vending machines ≈ 1.1 w × 0.8 d × 2.2 h, origin floor centre, front −Y. Distinct colour schemes: Juggernog deep red, Speed Cola green, Quick Revive light blue/white, Double Tap dark red-brown with gold. Original logos/lettering built from text objects (the names may appear as text). Illuminated sign panel with a `glow` material. |
| `mystery_box.glb` | weathered wooden weapons crate ≈ 1.5 w × 0.6 d × 0.55 h with painted question marks (`glow` material, blue-white), iron fittings, chains. The lid is a separate object `lid` with its origin on the rear hinge line so rotating about local X opens it. Front −Y. |
| `teddy_bear.glb` | worn plush teddy bear ≈ 0.4 m tall (the box's "bye-bye" bear), origin at its base. |
| `pap_machine.glb` | Pack-a-Punch machine ≈ 2.0 w × 1.1 d × 1.9 h: heavy industrial device with rollers, pipes, a hatch where the gun goes in, heavy bolts, warning stripes, `glow` lights. Front −Y. Optional separate `rollers` object. |
| `power_switch.glb` | wall-mounted electrical panel ≈ 0.6 w × 0.25 d × 0.9 h. Origin at the **back centre** (sits flat on the wall), front −Y. The handle is object `lever`, origin at its pivot, rotates about local X; model it in the OFF (down) position. Indicator lamps `glow`. |
| `barricade.glb` | window barricade for the 1.2 × 1.1 m opening: trim frame plus six planks `board_1` … `board_6`, each nailed across the opening in its final position, slightly crooked, with visible nails. Origin at the **sill centre**, −Y = the interior side. Boards sit on the interior face. |
| `pu_maxammo.glb`, `pu_instakill.glb`, `pu_doublepoints.glb`, `pu_nuke.glb`, `pu_carpenter.glb`, `pu_firesale.glb` | power-up pickups ≈ 0.45 m, origin at their centre: ammo crate, skull, "x2" emblem, 50s atomic bomb, claw hammer, price tag with "$". Gold/brass metallic finish (the game adds a green glow). |

---

## 5. Audio (area `audio`, code only — no files needed)

`src/audio/audio.js`, fully procedural Web Audio (synthesised at init into AudioBuffers via
OfflineAudioContext or live nodes). No sample files, no copied music. API contract:

```js
import { audio } from './audio/audio.js';
await audio.init();                 // call from a user gesture; builds all buffers
audio.setListener(camera);          // call every frame (position + orientation)
audio.play(name, { volume, rate, detune }) -> handle  // 2D (UI, player weapon)
audio.playAt(name, vec3, { volume, rate }) -> handle  // 3D positional
audio.loop(name, { volume, position }) -> handle      // handle.setPosition(v), handle.setVolume(v), handle.stop(fadeSec)
audio.music(name) / audio.stopMusic(fadeSec)
audio.setMasterVolume(v); audio.duck(amount, seconds) // e.g. duck world audio during stingers
audio.announce(text)                 // announcer voice line (e.g. speechSynthesis, deep & processed-sounding if possible)
```

Names the game will call (unknown names must be a silent no-op, never throw):
`gun_pistol, gun_rifle, gun_smg, gun_shotgun, gun_lmg, gun_revolver, gun_raygun, gun_pap_layer`
(extra sci-fi layer played with packed guns), `raygun_impact, explosion, dry_fire, reload_mag_out,
reload_mag_in, reload_bolt, reload_shell, shell_drop, weapon_switch, knife_swing, knife_hit,
grenade_pin, grenade_bounce, hitmarker, headshot, flesh_hit, bullet_impact_wall, player_hurt,
player_down, heartbeat_loop, zombie_groan, zombie_scream (sprinter), zombie_attack, zombie_death,
zombie_rise_dirt, board_tear, board_repair, board_slam, purchase, purchase_deny, door_open,
box_open, box_music (~5 s music-box jingle while the box spins), box_close, box_teddy (laugh +
whoosh), perk_drink, perk_burp, perk_jingle_juggernog, perk_jingle_speedcola,
perk_jingle_quickrevive, perk_jingle_doubletap, pap_upgrade (~4 s machine process), power_on,
powerup_spawn, powerup_loop, powerup_grab, powerup_blink, max_ammo, insta_kill, double_points,
nuke_blast, carpenter, fire_sale, hellhound_spawn (lightning strike), hellhound_growl,
hellhound_bite, round_start, round_end, hellround_start, game_over, fire_loop, ambient_loop`
(wind, distant fires, low drone). Music tracks for `audio.music()`: `menu`, `game_over`.

Round stingers are the signature sound: `round_end` is an eerie, reverb-drenched minor-key motif
(think choir-like pads + a low bell), `round_start` a darker variation of it. Original compositions.
