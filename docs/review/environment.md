# Environment art review — Doom Town

**Reviewer verdict.** This does not read as AAA, and on most frames it does not read as 2012 BO2 either. The
silhouette work and layout are competent — the cul-de-sac reads, the bunker reads, the prop lineup is complete —
but almost every pixel-level decision is working against it. The image is governed by two failures: a bloom/emissive
budget that has no discipline (a single perk sign erases an entire room; the sun erases the right half of the street;
the viewmodel turns into a white ghost when it fires), and a total absence of *authored surface detail* — no decal
dressing, no detail normals, no macro-variation masks, no glass, no contact shadows, no local bounce. The result is
two looks and only two: "milky beige haze" outdoors and "flat wallpaper room lit by a coloured bulb" indoors. On top
of that sit hard, avoidable bugs that a reviewer should never see shipped: 22 rubble rocks floating at the bunker
ceiling, signage whose 3×5 bitmap font spells FHLLOUT SHELTEK, a mystery-box "beam" that is a hard-edged opaque
slab pasted over the sky, and a round counter that renders as an illegible red scribble. BO2 in 2012 had crisp
sun shadows, readable signage, glass, wet specular in the road, layered decals on every wall and a light rig with
dozens of practicals. This has one directional light, one hemisphere, eight lamp points and a global fog.

The prop *models* are the strongest thing here (Juggernog, the crate, the power panel all have real form), and
they're being destroyed by the lighting and the post chain. Fix the light/bloom/exposure discipline first —
issues 1–4 alone will move this more than a month of modelling.

---

## Top 12, ordered by impact

### 1. Emissive + perk point lights blow every interior into a coloured fog bank
**What's wrong.** `09_speedcola_machine_front.jpg` and `08_barricade_zombie_tearing_speedcola.jpg`: the Speed Cola
sign is pure clipped white — you cannot read "SPEED COLA" on the lightbox at all — and a green veil floods the
whole room, killing the wallpaper, the barricade, the lino and the ceiling. `12_juggernog_blocked_view.jpg`: the
Juggernog point light paints a hard red disc on the ceiling and the brick. Cause is a stack of three multipliers:
`interactables.js:238 setPower()` forces every `glow` material to `emissiveIntensity = Math.max(3, base)` (3.0 linear
is ~4× the bloom threshold); `interactables.js:231/239` adds a `PointLight(colour, 9, 5, decay 2)` sitting 0.9 m
from a wall in a 3 m room; and `game.js:636` raises `toneMappingExposure` to 1.18 indoors, amplifying both. Bloom is
then `UnrealBloomPass(strength 0.55, radius 0.55, threshold 0.82)` (`renderer.js:148`) — a very low threshold with a
very wide radius, so anything over 0.82 linear smears across a third of the screen.
**Why it matters.** The perk machines are the single most-looked-at props in a Zombies map, and right now getting near
one destroys the room's art. It also destroys readability: the player cannot see the machine's own branding or the
window they're supposed to be defending.
**Fix.** (a) `renderer.js:148` → `new UnrealBloomPass(res, 0.32, 0.4, 1.15)`. Emissives should bloom, lit surfaces
should not. (b) `interactables.js:238` → drop the `Math.max(3, …)` clamp; author intensity in Blender and use
`m.emissiveIntensity = on ? m.userData.on : 0.02` with `on` in the 0.8–1.4 range for the big lightbox and 2.5–4 only
for the tiny indicator lamps. (c) `interactables.js:231` → `new THREE.PointLight(col, 2.2, 3.2, 2)` and move it to
`+0.45` forward, `+1.55` up so it pools on the floor in front of the machine rather than wall-washing. (d) Split the
lightbox in the perk GLBs into two materials: `glow_sign` (backlit panel, low intensity, keeps its printed artwork
visible) and `glow_trim` (the small bright accents). `[both]` — **M**

### 2. The sun-side of the street is a white void; no depth cueing survives it
**What's wrong.** `01_street_start_horde.jpg`, `02`, `19_combat…`: everything from mid-frame right is an undifferentiated
cream wash. The bus, the far barricades, the neighbouring houses, the horizon and the zombies all merge. In `19` even
the near-field road disappears. Three causes compound: the sky shader pushes `horizon = vec3(1.7, 0.62, 0.18)` toward
the sun plus a `4.0, 2.2, 1.0` disc term (`sky.js:35,43`), the bloom threshold is 0.82, and `FogExp2` is a bright warm
`(0.36, 0.20, 0.13)` at density 0.012 (`game.js:43`) which lifts the whole distance into the same value band as the sun.
**Why it matters.** A 2012 shooter's money shot down a street works because the fog is *darker* than the sky and cooler
than the key light, so buildings silhouette against it. Here fog and sky are the same hue and value, so the map has no
depth and no readable horde silhouettes — you cannot see what's coming at you.
**Fix.** (a) `game.js:43` → cool and darken the fog to `new THREE.Color(0.18, 0.13, 0.12)` and reduce density to
`0.008`; let the sky carry the warmth, not the air. (b) `sky.js:35` → `horizon` toward-sun term down to
`vec3(1.05, 0.44, 0.15)`; `sky.js:43` disc term down to `vec3(2.4, 1.4, 0.7)`. (c) Add an explicit *aerial perspective*
tint that is sun-direction dependent rather than uniform: in the fog, mix toward the warm value only within ~35° of
the sun azimuth (a small custom fog shader chunk, or fake it by keeping `FogExp2` neutral-cool and letting the sky
disc do the warm halo). (d) With bloom fixed per issue 1 the residual halo will read as glare rather than erasure.
`[code]` — **M**

### 3. Mystery box beam is a hard-edged additive slab, not a light column
**What's wrong.** `17_mystery_box_idle_beam.jpg` and `18`: a light-blue rectangle with perfectly hard vertical edges runs
from the ground off the top of frame and visibly *tints the entire background inside it* — you can see the exact
boundary cut across the green house, the sky and the sidewalk. It has no taper, no soft silhouette, no noise, no dust,
no ground pool, and in `19_combat…` it renders as a flat grey-white bar. `interactables.js:465-467`: it is a
`CylinderGeometry(0.16, 0.3, 45, 20)` with a `MeshBasicMaterial`, `side: DoubleSide`, `AdditiveBlending`, `fog: false`,
`opacity 0.16`. DoubleSide + additive doubles the brightness where you see through both walls, so the interior is
*brighter* than the silhouette edge — the opposite of a real light shaft, which is brightest at the rim. `fog: false`
means the beam stays at full strength while the world behind it fogs away, which is why it reads as a UI overlay.
And the box's own light (`interactables.js:468`) is `PointLight(intensity 0, dist 4)` → idle intensity 2 at 4 m: the
beam emits no light onto the box or the ground it stands on.
**Why it matters.** This is the map's navigational landmark and it is the single most artificial element in any frame.
It is what the eye goes to first in two of twenty screenshots.
**Fix.** Replace the basic material with a `ShaderMaterial` doing: (a) view-dependent rim falloff
`float rim = pow(1.0 - abs(dot(normalize(vNormal), normalize(vViewDir))), 1.8);` so the edges glow and the centre
is thin; (b) `side: THREE.FrontSide` (or BackSide only) so you stop double-counting; (c) a vertical scrolling fbm
(`0.6 + 0.4 * noise(vUv * vec2(3.0, 0.6) - vec2(0.0, uTime * 0.12))`) for interior structure; (d) height falloff
squared so the top 30 m is essentially gone — reduce the cylinder to 18 m tall; (e) `fog: true` and wire the scene
fog uniforms so it recedes with distance; (f) raise `this.light` idle to `intensity 6, distance 5` and add a
`0.9 m` radius additive ground disc under the box so the column lands on something. `interactables.js:459-469`.
`[code]` — **M**

### 4. Viewmodel blows to pure white when firing
**What's wrong.** `19_combat_mp5_firing_hud_perks_powerups.jpg`: the MP5 and both hands are a glowing white ghost with
no material, no silhouette, no readable iron sights. The viewmodel is rendered by `vmPass` at `renderer.js:143-146`
and bloom is added at `:148` — *after* the viewmodel pass. So every HDR value on the gun (muzzle-flash-lit metal,
the `envMapIntensity 1.2` PaP camo, the `totalEmissiveRadiance += cm * cm * 2.2` in `viewmodel.js` PaP shader) gets
the full 0.82-threshold / 0.55-radius bloom treatment at point-blank screen size.
**Why it matters.** The gun is on screen 100% of the time and is the player's primary readability anchor. This is a
shipping-blocker-grade defect.
**Fix.** Two changes. (a) Move the viewmodel pass *after* bloom so the gun never contributes to or receives the
bloom convolution: in `renderer.js:_buildComposer`, order = `worldPass → gtao → bloom → vmPass → OutputPass → smaa → grade`.
(b) Clamp the muzzle-flash light on the viewmodel separately — the viewmodel scene should get its own dim flash light
(intensity ≤ 3, distance ≤ 1.2) rather than inheriting world values. If you want the gun to glow on fire, do it with a
small dedicated additive sprite at the muzzle, not by over-exposing the whole mesh. `[code]` — **S**

### 5. 22 rubble rocks float at the bunker ceiling (missing floor offset)
**What's wrong.** `10_bunker_pap_machine.jpg` shows a rusty slab hanging in mid-air near the ceiling; the source render
`renders/map/bunker_pap.png` shows it clearly with a cast shadow on the wall, and `renders/map/bunker_over.png` shows
more of them. Root cause found: `tools/blender/map/build_bunker.py:322` places the rubble scatter at
`(x, y, s * 0.25)` where `s ∈ [0.1, 0.32]`, i.e. absolute Z ≈ 0.03–0.08 m — but the bunker floor is at
`BUNK_Z = -2.5` (`tools/blender/map/layout.py:41`). Every one of the 22 rocks in that loop is sitting 2.5 m above
the floor, right at ceiling height. Note `service_tunnel()` at `:339` gets it right with `BZ + 0.1`.
**Why it matters.** Floating geometry is the single loudest "this is unfinished" signal there is, and it is in the
Pack-a-Punch room — the room players stare at while waiting 3 s for the upgrade animation.
**Fix.** `tools/blender/map/build_bunker.py:322` → `scn.rock(..., (x, y, BZ + s * 0.25), ...)`. Rebuild
`map_doomtown.glb` and re-verify with `node tools/inspect-glb.mjs`. While in there, also check the loose white plank
visible upper-right in `10` and the black hex plate hanging off the beam in `renders/map/bunker_pap.png:~(855,175)`.
`[blender:map]` — **S**

### 6. All signage is 3×5 bitmap boxes, and the wear pass corrupts the letters
**What's wrong.** The FALLOUT SHELTER plate reads **"FHLLOUT SHELTEK"** (`renders/map/south.png`, the headhouse lintel).
Root cause found: `tools/blender/map/lib_map.py:132-152` defines a 3×5 pixel `FONT`, and `text_boxes()` at `:156`
takes a `skip` parameter that randomly deletes that fraction of pixels for a worn look. In a 3×5 grid the *only*
difference between `A` and `H` is the top row, and between `R` and `K` is the top row. `lib_clutter.py:63-68` calls it
with `skip=0.08`, so one dropped pixel turns A→H and R→K. The same generator draws "SCHOOL BUS" and "STOP"
(`lib_vehicles.py:400,403,430`) and the bunker lettering (`build_bunker.py:106`). Separately, every letter pixel is an
individual extruded box standing 12–20 mm proud of the plate — "FALLOUT SHELTER" is ~50 boxes, so the text casts
shadows and reads as Lego, not paint.
**Why it matters.** Signage is how a 1950s test-town establishes period and place. Misspelled, unreadable, Lego-block
signage is worse than no signage. A 2012 AAA shooter painted its signage into the albedo/normal at authored
resolution; this is below 2004.
**Fix.** Stop building type out of geometry. (a) Add a `sign_decal()` helper that renders text to a texture with
PIL/Blender's text object at real stencil proportions, bakes it into the plate's albedo + roughness + a shallow
normal, and applies it as a single quad. (b) If you keep `text_boxes` short-term: set `skip=0.0` everywhere, and
protect glyph-defining pixels — in `text_boxes()` only allow `skip` to remove a pixel if the glyph still has ≥1 pixel
remaining in that row *and* the glyph is not one of the confusable pairs (A/H, R/K, O/D/0, B/8, S/5, E/F). (c) Widen
the font to 5×7 minimum for any text the player reads at under 5 m. `[blender:map]` — **M**

### 7. Shadows are hard, stair-stepped and single-cascade
**What's wrong.** `01_street_start_horde.jpg` and `19`: the long telegraph-pole and debris shadows have jagged,
stair-stepped edges with no penumbra growth over their 20 m length — at the far end a shadow should be 30–50 cm soft
and it is still 2 cm hard. `renderer.js:107` sets `shadowMap.type = THREE.PCFShadowMap`, the cheapest 9-tap kernel;
`sky.js:105` then asks for `shadow.radius = 2.5`, which with a 9-tap PCF kernel produces banding rather than blur.
`sky.js:100-102`: one 4096² map over a ±42 m ortho with `far: 220` — so nothing beyond 42 m of the player casts a
shadow at all, and there is no cascade.
**Why it matters.** Low sun + long shadows is the whole lighting concept of this map. Hard, aliased, single-cascade
shadows are the most visible "browser demo" tell in the street shots.
**Fix.** (a) `renderer.js:107` → `THREE.PCFSoftShadowMap`. (b) `sky.js:105` → `shadow.radius = 1.6` with the soft type.
(c) Split into two cascades: a tight ±14 m / 2048² map for the near field and a ±55 m / 2048² for the far, or at
minimum drop `s` to 30 and keep 4096² for a 1.5 cm texel in the playable core. (d) `sky.js:104` `normalBias 0.03` is
tight for 1 cm texels at grazing sun — go to `0.055` and pull `bias` to `-0.0002` to stop the peter-panning visible
under the debris planks. `[code]` — **M**

### 8. No authored decal dressing anywhere in the world
**What's wrong.** `src/fx/decals.js` contains exactly three decal types — bullet hole, blood, scorch — and all three
are spawned by gameplay. There is not one authored environment decal in the map: no grime streaks under windows, no
rust runs below the bunker pipes, no oil stains under the cars, no tyre marks on the asphalt, no water stains on the
bunker ceiling, no torn posters, no soot fans above the fires, no cracks where the sidewalk meets the kerb. Look at
the bunker wall in `11_power_switch.jpg` — a 6 m × 3 m concrete surface with nothing on it but a faint tiling texture
and two floating pipes. Compare the same wall area in any BO2 map: 10–20 overlapping decals.
**Why it matters.** Decals are what makes a AAA environment look *lived in and destroyed* rather than modelled. This
is the largest single gap between this and the reference, and it is also the cheapest to close.
**Fix.** Two tracks. (a) `[blender:map]`: bake a second "grime" UV channel or authored blend masks into the big
surfaces (bunker walls, house siding, asphalt) so tiling is broken by unique dirt — see issue 9. (b) `[code]`: extend
`decals.js` with a `staticDecal(pos, normal, size, texId, rotation)` API and a small authored list driven off
`MK_DECAL_*` markers exported from the map, using 8–12 hand-drawn canvas textures (streak, splash, crack, soot fan,
oil pool, poster, stencil). Give `DecalSet` a normal map and `depthWrite: false` with `polygonOffsetFactor: -4`
(already there). Also replace the `PlaneGeometry` projection with a clipped box projection for anything on a
non-planar surface — a flat quad on the cracked road will float. `[both]` — **L**

### 9. Textures tile visibly and have no detail layer
**What's wrong.** Wallpaper repeats ~5 times across one wall in `08`/`09`/`12` with an identical diamond every 2.2 m
and the same three "peel" blotches each time. Asphalt (`01`) shows a blotchy low-frequency pattern with no aggregate
detail at footstep range. `tools/blender/map/lib_materials.py:620-660`: *every* material is 1024² — asphalt at a 3 m
tile is 341 px/m, `desert_far` at a 55 m tile is **18 px/m** (which is why the ground in `17_mystery_box_idle_beam.jpg`
is a featureless beige plane). There is no detail-normal layer, no macro-variation mask, no second UV set.
**Why it matters.** Visible tiling is the "asset-flip" tell. BO2 used 1024–2048 base plus a shared high-frequency
detail normal blended at 8–16× the base tile rate on every surface.
**Fix.** (a) Bump the hero surfaces to 2048² (`asphalt`, `sidewalk`, `concrete_bunker`, `siding_*`, `wallpaper_*`,
`woodfloor`) — the contract allows ≤2048². (b) Add a single shared grayscale detail-normal (grain/pores, 512²,
tiled at 0.25 m) and blend it in `pbr_material()` with a second UV scale — one material node group, applied to all
SPEC materials. (c) Add a low-frequency variation mask (0.05–0.2 tiles/m) multiplying albedo brightness ±12% and
roughness ±0.15 to break the repeat. (d) `desert_far` at 55 m tile is unusable — either drop the far ground to a
flat gradient plane or give it a 4 m tile with the far-distance fog hiding the repeat. `[blender:map]` — **M**

### 10. There is no glass — every window is an opaque dark slab
**What's wrong.** `08`, `09`, `12`, `renders/map/start_wide.png`, `renders/map/south.png`: window openings are either
black holes or flat mid-grey rectangles. `lib_materials.py:FLAT` defines `glass` as
`color=(0.16,0.19,0.20), roughness=0.09, metallic=0.0` — fully opaque, no transmission, no alpha. Nothing in the map
reflects the sunset, so the west-facing house fronts (which should be blazing with orange window reflections at this
sun angle) are dead. There's also no broken-glass geometry, no shards, no curtains.
**Why it matters.** At a low sun, glass reflections are half of what sells the hour and the period. This is a free win
that is currently worth zero.
**Fix.** `[both]`. (a) Author glass as `transmission: 0.0, opacity: 0.25, transparent: true, roughness: 0.06,
metalness: 0.0, envMapIntensity: 2.2` — a cheap reflective panel, no refraction needed. Set `envMapIntensity` high
so the PMREM sunset sky reads in it (`sky.js:createEnvironment` already builds a usable env). (b) Give roughly half
the windows a shattered variant: a broken-edge alpha-cut plane plus 3–5 shard slivers, and a scatter of glass chunks
on the ground below. (c) In `map.js:66` you globally force `envMapIntensity = 0.55` on *every* material — exempt
glass and chrome, or raise per-material via a name check. `[both]` — **M**

### 11. The lighting rig is one sun, one hemisphere, eight lamps — no bounce, no practicals, no rim
**What's wrong.** `sky.js:96-109` is the entire world rig: one `DirectionalLight` at 3.8 and one `HemisphereLight` at
0.55. `map.js:114` adds up to 12 lamp points (the map only ships 8 `MK_LAMP_*`), `game.js:89-97` adds up to 6 fire
points. Consequences visible everywhere: interiors have no window light shafts and no bounce, so the far wall in `08`
is a uniform flat value; the shadow side of every house in `01` is a single dead tone with no sky gradient across it;
zombies in `02` have no rim light separating them from the background; the bunker in `10` is lit by exactly one bare
bulb that blooms out, leaving the pillars and the ceiling trunk unmodelled. `game.js:642` also drags
`environmentIntensity` down to 0.2 in the bunker, removing what little ambient shaping there was.
**Why it matters.** AAA lighting is a *rig*, not a sun. Every BO2 interior had 4–8 hand-placed lights doing separation,
bounce and shape.
**Fix.** `[both]`. (a) Export `MK_LIGHT_*` markers from the map with `userData` for colour/intensity/range and place
20–30 non-shadowing fill points: one warm bounce low in each room facing the wallpaper, one cool sky-fill at each
window opening, one kicker behind each perk machine. (b) Add a second directional "rim" light at roughly
`SUN_DIR` rotated 150° in azimuth and 25° up, cool `(0.42, 0.50, 0.72)`, intensity 0.5, `castShadow: false` — this
alone gives the zombies in `02` a readable edge. (c) Make the bunker's hanging cage lamps cast shadows (one of them,
`shadow.mapSize 512`) so the ceiling trunk and pillars finally have form. (d) Interior windows should emit: add a
small warm-fill point just inside each `MK_BARRIER_*` so the opening reads as a light source at dusk.

### 12. The fires do not light or heat the world
**What's wrong.** `17_mystery_box_idle_beam.jpg`: the fire by the picket fence is a formless orange smudge ~20 cm
tall that casts no visible light onto the fence, the ground or the barrel next to it. `particles.js:332-346` spawns
one soft flame blob per frame at 90% probability with a radial-gradient atlas cell — there is no flame *shape*, no
flipbook, no animation. `game.js:91` gives the fire a `PointLight(0xff7a2a, 20, 12, 2)` but only the first 6 of 9
fires get one, and they don't cast shadows, so nothing flickers across the geometry. There is no heat haze, no
ground scorch decal under the fire, no smoke column that reads at distance.
**Why it matters.** "Smouldering fires" is in the art direction (`ASSET_CONTRACT.md`), and it is the only warm local
light source in a map whose whole mood depends on it.
**Fix.** `[code]`. (a) Build a proper 4×4 flame flipbook in `buildAtlas()` (16 frames of a teardrop with noisy edges)
and animate `iParams.w` over the particle's life; raise the spawn rate to 3–4 per frame and stack two size bands.
(b) Add a screen-space heat-haze: a small additive quad above each fire that offsets `tDiffuse` UVs in the grade
pass, or a cheap per-fire refraction sprite. (c) Give the two largest fires a shadow-casting point light
(`mapSize 512`, `radius 2`) so flicker moves across the geometry. (d) Add an authored scorch decal + a persistent
smoke column (tall, slow, low-opacity alpha particles with a 6–10 s life) so fires read from across the map.
(e) `particles.js:172` hard-codes `uFogColor (0.25, 0.17, 0.13)` and `vert:137` hard-codes a fog density of `0.0004`
— neither matches `scene.fog` (`0.36, 0.20, 0.13` at 0.012, i.e. 0.000144), so smoke fogs at a different rate and
hue than the world. Wire both from the scene fog.

---

## Lesser issues

### 13. The HUD round counter renders as an illegible red scribble
Bottom-left of every gameplay shot (`01`, `08`, `19`) there is a ragged dark-red vertical smear that most readers
will assume is a rendering artifact. It is the tally-mark round counter: `hud.js:52-70` draws strokes into
`#round-svg`, and `index.html:18-24`'s `#brush` filter shreds them with a `feTurbulence baseFrequency="0.35 2.2"`
+ `feColorMatrix` alpha matrix `0 0 0 -2.2 1.75` + `feComposite operator="in"`, leaving a speckled fragment of the
original stroke. The `--blood #b3120e` colour is also too dark against a dark HUD.
**Fix** `[code]`: reduce the streak mask to `values="0 0 0 -0.9 0.95"` so it thins rather than destroys the stroke,
drop `baseFrequency` to `"0.25 1.1"`, raise `stroke` to a lighter `#d8342c` with a `drop-shadow(0 0 8px #000)`, and
increase `stroke-width` from 8.5 to 11 in the 200×90 viewBox. Verify at round 1, 5 and 12. **S**

### 14. Three of six power-up HUD icons don't exist
`hud.js:25-29` defines `PU_ICONS` for `instakill`, `doublepoints`, `firesale` only. `powerups.js:5` ships six:
`maxammo`, `nuke` and `carpenter` render as empty 58 px gaps with a green drop-shadow and nothing inside.
**Fix** `[code]`: add the three missing SVGs (ammo box, bomb, hammer/nails), matching the existing emblem style. **S**

### 15. Power-up drops are a green HDR blob that swallows the model
`powerups.js:40` gives the glow sprite `color: new THREE.Color(1.6, 3, 1.4)` at scale 1.3 with additive blending —
3.0 linear, ~3.7× the bloom threshold, over a 0.3 m model. The prop (which is nicely built, see
`renders/props/pu_lineup.png`) is invisible inside it. There's also no ground light pool and no vertical glint,
so a drop across the street doesn't read.
**Fix** `[code]`: sprite colour → `(0.9, 1.7, 0.8)`, scale 0.85; add a 0.7 m additive ground disc under the drop and
a thin 2.5 m vertical fade-out sliver so it's spottable at range; keep `PointLight(0x66ff44, 6, 4, 2)`. **S**

### 16. Mystery-box floating weapon is tiny and hidden behind the lid
`18_mystery_box_open_offer.jpg`: the offered AK is ~60 px tall, half-occluded by the white lid interior, and reads as
a decal on the lid rather than a 3D offer. `interactables.js:533` places the floater at `m.pos + (0, 0.55, 0)` and
`:544` raises it only `0.5 m`; the lid (`:528`) rotates to `lidRest - 1.6` rad, i.e. ~92° back and up, directly into
the sightline. The weapon is also at real world scale, which is small at the 2 m interaction distance.
**Fix** `[code]`: scale the floater group to `1.7`, change the base to `m.pos + (0, 0.85, 0)` with a `0.55` rise, push
it `0.15 m` along `m.forward` toward the player, reduce the lid open angle to `1.25` rad, and add a slow
`floater.rotation.y += dt * 0.5` so the silhouette changes. **S**

### 17. The mystery box's "?" marks are extruded plastic geometry
`renders/props/mystery_box_hero.png`: the question marks are chunky bevelled 3D solids in pale blue, inconsistently
sized and positioned across the four faces, and they are not emissive — they read as bath toys glued to a crate.
The chain is also a perfectly straight run with no catenary sag and it intersects the corner brackets.
**Fix** `[blender:props]`: replace the "?" solids with a baked decal in the crate's albedo + a shallow normal, using a
material named `glow_q` (emission ~0.6) so the game can pulse it; centre it on each face at a consistent size.
Re-run the chain as a curve with gravity sag and re-seat it outside the brackets. **M**

### 18. Bunker reads as a parking garage, not a fallout shelter
`10_bunker_pap_machine.jpg` and `renders/map/bunker_pap.png`: white painted parking-stall stripes run down the floor,
the concrete walls are almost bare, the beams carry an unmotivated orange rust *splatter* that looks like spilled paint
rather than corrosion running downward from a fastener, and the rusty floor plates sit on the stripes like random
tiles. There's no signage, no blast-door detailing visible from inside, no piping continuity, no dust.
**Fix** `[blender:map]`: remove the parking stripes or convert them to a faded yellow safety walkway with hazard
chevrons; add authored wall decals (see issue 8) — stencilled "SHELTER CAPACITY", CD triangles, water stains,
efflorescence bleeding from the ceiling joints; make the beam rust *directional* (streaks running down from bolts,
concentrated at the ends); add a floor grime gradient darkest at the walls. **M**

### 19. Street debris is a scatter of untextured flat cards
`01`, `renders/map/start_wide.png`, `renders/map/south.png`: the road litter is dozens of near-identical flat
rectangles lying dead flat at three or four sizes, in pale grey and brown, with no thickness, no curl, no edge
damage, and no AO contact with the road. It reads as confetti, not blast debris.
**Fix** `[blender:map]`: build 6–8 debris archetypes with real volume (splintered plank, buckled sheet metal with a
curl, torn shingle bundle, crumpled newspaper wad, chunk of stucco with exposed lath, a bent bicycle wheel) and
scatter with random pitch/roll of ±8° so pieces sit on each other, plus a small-gravel layer. Cluster them
directionally away from the blast centre rather than uniformly. **M**

### 20. Trees are bare cylinders meeting at right angles
`renders/map/tree.png`: the "burnt tree" is straight untapered cylinders joined at hard angles with visible seams,
no bark silhouette, no twig taper, no fork geometry. It's the worst-looking asset in the map.
**Fix** `[blender:map]`: `lib_tree.py` — taper every segment (r2 = 0.55 × r), add 2–3 twig generations with
decreasing radius, add a slight random bend per segment, and merge the fork joins. Add a second variant so the three
placed trees aren't identical. **M**

### 21. Interior furniture is untextured flat-shaded boxes
`renders/map/yellow_living.png`: the sofa and armchair are literally rectangular blocks in flat red-brown with no
cushions, legs, piping, fabric texture or sag. The coffee table is a slab on four sticks. The rug is a flat
rectangle. No baseboards or door casings anywhere. Almost none of this is visible in the shipped screenshots because
the interiors are too dark and too hazed to see — which is itself the problem.
**Fix** `[blender:map]`: add cushion separation, tapered legs, arm rolls and a `fabric_*` material with a weave
normal; add skirting boards and door casings to every room (cheap, and it is the single biggest "this is a real
house" cue); add fallen clutter — an overturned lamp, a scatter of picture frames, a knocked-over chair. **M**

### 22. Wall-buy chalk is emissive and generated from a silhouette
`interactables.js:161` builds the chalk plane with `emissive: 0xffffff, emissiveMap: chalk.tex, emissiveIntensity: 0.22`
— chalk does not emit, and under a perk light this will glow. The art itself (`chalkTexture`, `:30-87`) is an
orthographic silhouette of the weapon model with an outline and a hatch fill, which gives you a shape but no
line-weight variation, no construction lines, no price scrawl, no BO2-style stroke feel.
**Fix** `[code]`: drop the emissive entirely (`emissiveIntensity: 0`). Improve the generator by tracing the silhouette
edge with a jittered multi-pass stroke (3 passes at ±1.5 px with varying alpha), adding a few interior detail lines
sampled from the depth discontinuities, and hand-adding a chalk price under the drawing. **S**

### 23. No anti-aliasing beyond SMAA — thin geometry breaks up
`renderer.js:103` sets `antialias: false` and `:128` creates the composer target with `samples: 0`. SMAA alone cannot
hold sub-pixel geometry: the power lines in `01`/`17` render as broken dotted lines, the picket fences shimmer, and
the debris edges crawl.
**Fix** `[code]`: on WebGL2 set `samples: 4` on the composer's `WebGLRenderTarget` (`renderer.js:128`) and gate it
behind the quality setting (`setQuality`: 4 on high, 2 on medium, 0 on low). Keep SMAA for the remaining specular
aliasing. **S**

### 24. Ambient particles spawn indoors and in the bunker
`game.js:528-529` calls `this.fx.embersAround(center, 24)` and `this.fx.ash(center, 20)` every frame around the camera
with no zone test, so embers and falling ash appear inside sealed rooms and 2.5 m underground in the bunker.
**Fix** `[code]`: gate on `this.player.zone` — outdoors only for ash, and for embers use `map.fires` positions as the
emitter origin with a wind drift rather than a camera-centred box. Add a slow interior dust-mote pool for rooms
instead (tiny, near-static, additive, visible in the window shafts). **S**

### 25. Global fog is applied inside buildings
`game.js:43` sets a single `FogExp2` and `:640` only ever changes density for dog rounds. Interiors therefore sit in
the same warm haze, which combined with the exposure lift at `:636` is part of the milky look in `09`. Real interiors
at dusk should be *darker and contrastier* than the street, not hazier.
**Fix** `[code]`: lerp `scene.fog.density` per zone alongside the existing exposure/hemi lerp — `[0.008, 0.003, 0.002]`
for `[street, house, bunker]`, and drop indoor exposure from `[1.0, 1.18, 1.35]` to `[1.0, 1.08, 1.15]` once the
emissive/bloom fix in issue 1 lands. **S**

### 26. Sky has no stars, no dither, and clouds that never read
`sky.js:33-57`: the zenith gradient bands visibly in `17`/`18` (no dithering; the grade pass's grain at
`renderer.js:23` is attenuated by `(1.0 - luma * 0.5)` so it's weakest exactly where banding is worst). The cloud
layer is projected as `d.xz / (h + 0.12)` which stretches into radial streaks near the horizon, and at the shipped
`uClouds = 1` it contributes almost nothing visible — the sky is effectively a two-stop gradient plus a sun.
**Fix** `[code]`: (a) add `col += (hash(gl_FragCoord.xy) - 0.5) / 255.0;` before output to kill the banding; (b) add a
faint star field above `h > 0.25` fading into the smog; (c) raise cloud contrast — `smoothstep(0.30, 0.62, …)` and
`cover * fade * 1.0` — and add a second, slower, larger-scale layer so the sky has shape rather than noise; (d) add
cheap crepuscular rays: a radial-blur sample of the sky's sun term in the grade pass, masked by depth, which at this
sun angle through smog is the highest-value-per-cost addition on this list. **M**

### 27. Backdrop buildings are untextured silhouette pyramids
`renders/map/south.png` and `start_wide.png`: the out-of-bounds neighbourhood is a row of identical flat brown
hip-roof prisms with no siding, no windows, no variation, all the same height and spacing.
**Fix** `[blender:map]`: three roof archetypes × three heights × random yaw, a single shared low-res siding material
(they're `BG_*` so they don't cast shadows — cheap), and a few silhouette accents: a water tower, a windmill, a
leaning billboard. **S**

### 28. Menu and game-over screens are web pages over a frozen frame
`06`/`07`: `#menu`'s CSS gradient (`style.css:130`) crushes the left 38% of the screen to 92% black, destroying the
environment art it's sitting on, and the `_updateMenuCamera` drift (`game.js:538-555`) has a ~140 s period so it
reads as a still. `20_game_over_screen.jpg` is a flat CSS radial red multiply over the live scene with a plain
four-cell stat table — no blur, no desaturation, no grade shift, no motion.
**Fix** `[code]`: (a) menu — narrow the gradient to `rgba(5,3,3,0.88) 0%, rgba(5,3,3,0.55) 22%, transparent 48%` and
speed the camera drift to a ~28 s cycle with a slow dolly-in; (b) game over — drive it through the grade shader
instead of CSS: ramp `uSaturation` to 0.15, `uVignette` to 0.9 and add a progressive blur over 1.5 s, and let the
scene keep rendering behind it at 0.1× timescale so it feels like a death, not a modal. **M**

### 29. Interaction prompt and flash message have no visual identity
`08`/`17`: "Power On" and the buy prompts are plain white sans text floating in the middle of the frame with a text
shadow. No plate, no frame, no BO2-style key glyph treatment beyond a 1 px border on `<b>`.
**Fix** `[code]` `style.css:36-41`: put the prompt on a subtle dark plate with a thin `--gold` left rule, lift
`#prompt` to `top: 58%`, and give `#flash-msg` a slow letter-spacing-in animation plus a hairline rule above and
below so announcements feel authored. **S**

### 30. GTAO radius is too small to give contact shadows outdoors
`renderer.js:139` uses `radius: 0.6` with `blendIntensity: 0.85`. At 0.6 m in a street scene you get a faint crease
darkening and essentially nothing where props meet the ground — visible in `17`, where the crate, the barrel and the
fence posts all sit on the sidewalk with no contact darkening at all. It also runs *before* the fog is composited in
the world pass output, so AO darkens fogged distant pixels.
**Fix** `[code]`: `radius: 1.1, distanceExponent: 1.8, thickness: 0.6, samples: 16`, and add small baked or geometric
contact shadows (a 0.5 m dark alpha disc) under every large placed prop in the map GLB so you don't depend on
screen-space AO for the most important occlusion in the frame. **S**
