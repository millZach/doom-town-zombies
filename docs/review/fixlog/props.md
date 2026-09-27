# Fix log — stream `props` (Blender assets)

Files owned and changed: `tools/blender/props/build_perks.py`,
`tools/blender/props/build_mysterybox.py`, `tools/blender/props/build_pap.py`, the GLBs they
write in `public/models/props/`, and the check renders in `renders/props/`.
`lib_props.py` was **not** touched — every other props script bakes through it.

Every Blender job ran through `sh tools/blender/run_locked.sh` (one Blender on the machine at
a time, 12-thread cap); 8 jobs total. Check renders were dropped to ≤ 960×540-equivalent at
30 samples for the same reason, which is why the committed renders are smaller than before.

**Nothing in the game-facing API moved.** Verified with
`node tools/inspect-glb.mjs public/models/props/<file>.glb --tree`:

| file | nodes | tris | materials |
|---|---|---|---|
| `perk_juggernog.glb` | `machine`, `sign` | 20 004 | `…_shell_mat`, `…_face_mat`, **`juggernog_sign_glow`**, **`juggernog_trim_glow`** |
| `perk_speedcola.glb` | `machine`, `sign` | 16 116 | same pattern |
| `perk_quickrevive.glb` | `machine`, `sign` | 20 498 | same pattern |
| `perk_doubletap.glb` | `machine`, `sign` | 18 844 | same pattern |
| `mystery_box.glb` | `crate`, `lid` (origin still `[0, 0.50, −0.32]` on the hinge line) | 13 690 | `mbox_body_mat`, **`glow_q`**, `mbox_lid_mat` |
| `pap_machine.glb` | `machine`, `rollers` (origin still `[0, 1.01, 0.58]` on the drum axis) | 17 904 | `pap_body_mat`, **`pap_sign_glow`**, **`pap_trim_glow`**, `pap_rollers_mat` |

---

## environment.md #1(d) — split each perk marquee into sign + trim glow — **fixed**

`build_perks.py`. Every machine now ships two emissive materials instead of one, named so
`interactables.js` `glowKind()` sorts them without any per-asset table:

- **`<perkId>_sign_glow`** — the backlit marquee panel only (unchanged geometry, still the
  `sign` node). Baked at `emission_strength = 1.2`, which the exporter writes as
  `emissiveFactor [1,1,1]` + `KHR_materials_emissive_strength 1.2`, so GLTFLoader hands
  three.js `emissiveIntensity = 1.2` — inside the code's `sign` band `[0.85, 1.4]`, and the
  authored value therefore survives the clamp rather than being pulled to the floor.
  Previously this baked at `0.5`, which exported as `emissiveFactor [0.5,0.5,0.5]` with no
  extension → `emissiveIntensity = 1` → clamped to `0.85` → an effective `0.425`. The panel
  keeps its dark printed lettering on top, so "JUGGER NOG" / "SPEED COLA" read as artwork on
  a lit box instead of a white rectangle.
- **`<perkId>_trim_glow`** — the small bright accents, `emission_strength = 3.0` →
  `emissiveIntensity = 3.0`, inside the `trim` band `[2.4, 4.0]`. Two new pieces of geometry
  carry it:
  - a **16 mm neon tube tracing the marquee**, sitting just proud of the sign panel and
    inside the existing chrome/gold bezel, on **both** faces of the crown. New helper
    `neon_frame()` builds it as four slim rounded bars in the sign's own plane; it takes a
    `tilt` so the Speed Cola slant crown gets a frame that lies flush with its 16° panel.
    Quick Revive's round crown gets a `tube()` ring (r 0.236–0.252) instead of a rectangle.
    Bar/ring extents were solved per crown against the existing letter and bezel bounds, so
    nothing intersects the `sgn1`/`sgn2` text or the chrome trim.
  - **two pilot lamps in brass bezels** on the control plate at x = 0.140 / 0.213 — the one
    span that is free of buttons, the coin escutcheon and (on Double Tap) the beer taps.
- New per-perk `trim=` colour in `PERKS`: hot neon red / green / ice-white / amber, i.e. a
  hotter, whiter version of each machine's sign colour so the accent separates from the panel.
- Cost: +820 tris on Juggernog, similar elsewhere; one extra 256² emissive texture per file.

**Judged from the renders.** All four close-ups now show three distinct emissive levels — a
readable mid-bright panel, a hot outline, and two small hot lamps — instead of one flat glow.
That is what issue #1 asked for on the asset side; the matching light/bloom discipline is
already in `interactables.js` (see `fixlog/props-hud.md`) and still needs
`UnrealBloomPass(res, 0.32, 0.4, 1.15)` in `renderer.js` from the renderer stream, or the
trim band will bloom wider than authored.

## environment.md #17 — mystery box "?" marks and chains — **fixed**

`build_mysterybox.py`.

**The marks.** The four-face + lid "?" were `text_mesh(extrude=0.006, bev=0.0022)` in Cooper
Black — a chunky bevelled solid standing **30 mm** off the boards, casting its own shadow,
at two sizes and off-centre (x = ∓0.10, 3° / 7° rotations). Now:

- flat glyphs, `extrude=0.0004, bev=0.0`, in the **Stencil** face (so the bowl carries a real
  stencil bridge), sitting **5 mm** off the plank plane — about 1.5 mm of clear air over the
  planks' own ±3.5 mm warp, which is enough not to z-fight and far too little to read as a
  solid. No bevel means no moulded edge highlight, which is what made the old ones look like
  bath toys.
- one size per face family (0.290 on the long faces and the lid, 0.215 on the ends), every
  one centred on its panel at `PANEL_Z = (SKID + ZT) / 2`, with only a ±2–4° hand-painted lean.
- material renamed `box_glow` → **`glow_q`** at `emission_strength 0.6`, which is what
  `glowKind()` routes to the low `mark` band `[0.35, 0.9]`; effective emissive works out at
  0.54, so the marks breathe rather than burn.
- The paint took **three passes** to get right and that is worth recording: a flat glyph sits
  at pointiness ≈ 0.5 everywhere, so `weathered()`'s edge-wear ramp barely fires and the first
  two bakes produced a *pristine* mark on a filthy crate — a clean vinyl decal, which is its
  own kind of wrong. Saturating the ramp (`pointy_lo 0.30`, `pointy_hi 0.50`) puts the whole
  face at full `edge_raw` and hands the pattern entirely to the breakup noise, so `scale`
  becomes the chip size: 5.0 gives ~15 mm flakes of bare grain through the pale blue. The
  glyph stays legible because the noise ramp bottoms out at 0.15.
- Tri count fell from 17 670 to 13 690 — the flat marks cost ~4 000 tris less than the solids.

**The chains.** Both runs were hand-typed polylines; the front one passed *through* the corner
brackets (bracket front face −(HD+0.0255), rivet heads −(HD+0.0285), chain axis −(HD+0.030)
with a 14.6 mm link radius). Now:

- new `catenary()` helper: straight lerp horizontally, real `cosh` drop vertically, so the
  curve is flat-bottomed and steep at the anchors the way a slack chain actually hangs.
- front run is a 20-link catenary at −(HD+0.050) — 6 mm clear of the rivet heads — anchored at
  x = ±(HW−0.155), inboard of the corner caps. End run is a 14-link catenary at −(HW+0.050).
- new `eye_plate()` helper puts a backing plate and a ring at each of the four anchors, so the
  chains are shackled to something instead of ending in mid-air.
- the hasp/padlock moved from x = 0.47 to x = 0.30 (onto the mid batten, where it has
  something to be bolted to) and 17 mm further out, which also takes it out of the chain's
  line — at 0.47 the new catenary passed straight through the padlock body.

**Not done, deliberately.** The review asked for the mark to be "a baked decal in the crate's
albedo". It is a separate flat quad with its own material instead, because the game has to
drive the mark's `emissiveIntensity` independently (`MysteryBox.update` breathes it in sync
with the beam) — baking it into `mbox_body_mat` would make that impossible. Visually the
result is the same: flat, no silhouette, wood grain showing through.

## `pap_machine.glb` rebuild — **fixed, plus two further defects found**

`build_pap.py`. The GLB on disk was stale (built 15:01, script edited 15:11), so the two fixes
already in the script had never shipped. Rebuilt, and both are confirmed gone in
`renders/props/pap_machine_close.png`: the **four black squares at the aperture bezel corners**
are now closed by the bezel limbs meeting, and the **aperture glow is the crushed `glow_ember`
(0.620, 0.150, 0.022)** rather than a hot orange.

Looking at that render honestly surfaced two more, both fixed in the same stream:

1. **The aperture was not an aperture.** `ap_surround` was a solid 0.080 m-deep slab across the
   whole opening, so it capped the recess 36 mm behind the bezel — the ember throat walls, the
   emissive slot and the feed rollers were all *behind* it and had never been visible. What the
   old render showed as a flat dark plate was the front face of that slab. It is now built as
   **four limbs leaving an AW × AH hole**, which gives a real 100 mm deep glowing throat with
   the rollers sitting inside it. This is the single biggest read change on the machine.
2. **Green pixels in the aperture corners.** The 512² emissive bake with an 8‰ island margin
   let the green control screen bleed into the ember throat's UV islands. Bake is now 1024²
   with a 20‰ margin; the bleed is gone.

Also, while the aperture was open: `ap_inner` (a 0.47 × 0.10 m slab of `glow_orange`) then
read as a blown-out cream rectangle with hard edges — exactly the undisciplined emissive the
review complains about elsewhere. It is now 0.34 × 0.062 m in a new mottled `glow_coal`
(high `variation`/`speckle`) so it reads as hot metal deep in the throat rather than a lightbox.

And the same sign/trim split as the perks was applied, since `PackAPunch` uses the identical
`glowMats()` path: **`pap_sign_glow`** (ember throat + control screen, authored 1.2) and
**`pap_trim_glow`** (the four indicator lamps + the beacon, authored 3.0).

---

## Not in this stream

- `build_power.py` / `lib_power.py` / `build_powerups.py` / `lib_pu.py` and their GLBs were
  left alone as instructed. Note `power_switch.glb` still ships a single `power_glow`, so its
  indicator lamps land in the conservative `sign` band rather than `trim`; whoever owns that
  script may want the same split.
- `teddy_bear.glb` and `barricade.glb` have no review items and were not rebuilt; both still
  verify clean (`board_1`…`board_6` + `frame`, and `teddy_bear`).
- `docs/ASSET_CONTRACT.md` §4 still describes a single `glow` material for the perk marquees
  and the box marks. It is shared with every other stream so I did not edit it, but the table
  rows for `perk_*.glb`, `mystery_box.glb` and `pap_machine.glb` are now understated — the
  real contract is `<perkId>_sign_glow` + `<perkId>_trim_glow`, `glow_q`, and
  `pap_sign_glow` + `pap_trim_glow`.

## Needs from other streams

1. **`src/core/renderer.js`** — environment.md #1(a). Every emissive here is authored against
   `UnrealBloomPass(res, 0.32, 0.4, 1.15)`. At the shipped `threshold 0.82 / radius 0.55` the
   trim band (3.0) will smear much wider than intended and the 1.2 sign panels will start to
   bloom too, which puts issue #1 back where it started.
2. **`src/game/interactables.js`** (props-hud stream) — no change needed; the naming it already
   keys off is exactly what these GLBs now ship. Worth re-checking `MysteryBox.init`'s comment,
   which still says the crate "currently ships `glow`" — it ships `glow_q` now.
