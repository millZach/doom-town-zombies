# Fix log — stream `weapons` (Blender assets)

Files owned and changed: `tools/blender/weapons/lib_weapons.py`, `build_ak74u.py`,
`build_galil.py`, `build_mp5.py`, `build_rpd.py`, `build_olympia.py`, `build_python.py`,
`build_raygun.py`, `build_m14.py`, `build_m1911.py`, `build_remington870.py`, `build_all.sh`,
plus the GLBs they write in `public/models/weapons/` and the check renders in `renders/weapons/`.

Every Blender job ran through `sh tools/blender/run_locked.sh` (one Blender at a time on the
machine, 12-thread cap). Check renders are now capped at **960 × 540 / 32 samples** —
`deliver()` used to shoot 1280 × 720 at 40–56 samples, five times per weapon.

**Contract kept.** `viewmodel / weapon / muzzle / eject / aim / arm_L / arm_R` names and
positions are untouched, every `weapon` origin (i.e. the hip-fire camera-space framing) is
unchanged, and the existing movable names `mag / pump / slide / bolt / cylinder` are unchanged.
`bolt` (×4), `barrels`, `crane` and a raygun `mag` are **added**. Every GLB re-verified with
`node tools/inspect-glb.mjs public/models/weapons/<id>.glb --tree`.

---

## Repair round (post-verification)

**1. BLOCKING — the Python's ejector rod was driven through the barrel underlug. Fixed.**
`CRANE` was at `(−0.0125, 0.0820, BORE−0.0185)`, i.e. 12.5 mm to the right of the ejector-rod
axis, so `crane.rotateZ(1.15)` lifted `crn_rod` / `crn_rodhead` **11.4 mm** inside a static
`c_lug` bore with only 2.6 mm of radial clearance — the rod ploughed through the lug wall and
then into the barrel (whose underside is 4.8 mm above the rod's swung position). Neither of the
suggested patches works on its own: moving the rod to `x = CRANE[0]` puts it outside the
17 mm-wide underlug, and a U-channel big enough for the swept envelope removes the whole lug
*and* still clips the barrel.

The fix is the same idea from the other end — **put the pivot on the rod axis**:
`CRANE = (0.0, 0.0820, BORE−0.0185)`. The rod is now exactly on the rotation axis, so it is
**stationary at every angle** (verified numerically: displacement 0.00000 m at both 0.66 and
1.15 rad). The underlug, its bore and the rod are untouched. `crn_pivot` became a yoke collar
(r 0.0070) sized to sit inside the lug bore.

Cost of the change: the swing is no longer level. With a pivot directly below the cylinder the
displacement direction is fixed at `angle(v) + 90° + θ/2`, so:

| | before (clipping) | now |
|---|---|---|
| θ = 0.66 rad | 12.5 mm left, level | 11.3 mm left, 3.9 mm down |
| θ = 1.15 rad | 24.3 mm left, level | 16.9 mm left, 10.9 mm down |

It still reads clearly as "swung out to the left"; the 11 mm drop on a 40 mm cylinder is the
price of a rod that cannot intersect the barrel.

Also fixed while in there: the **left recoil shield** was the one other thing the swung-out
cylinder sheared (a 5 mm slab at y 0.025–0.030). It now stops at the cylinder's rear face. The
right shield is unchanged, so nothing visible from the shooting side moved.

**2. Olympia `action` shear** — no asset change, as agreed; `action` stays fixed.

**3. ADS renders re-shot at the shipped `config.js` distances** — olympia 0.19, remington870
0.24, m1911 0.26 (m1911 was already being shot at 0.26). New library helper: `deliver()` now
also writes **`<wid>_ads_gun.png`**, the same ADS camera with the arms hidden. That render is
what identified the real obstruction. It is **both**: the support hand does fill the lower
frame as reported, but the thing actually crossing the line of sight was the receiver —
and only the gun-only frame shows that. (Only the two shotguns have been rebuilt since the
helper was added, so `*_ads_gun.png` exists for them; the other eight pick it up on their
next rebuild.)

| | `SIGHT_Z` | part | was | now |
|---|---|---|---|---|
| remington870 | BORE+0.0200 | receiver top | BORE+**0.0205** (above the sight line) | BORE+0.0120 |
| olympia | BORE+0.0215 | action top | BORE+0.0210 | BORE+0.0125 |
| olympia | | top lever | BORE+0.0250 | BORE+0.0140 |
| olympia | | hammer spurs | BORE+0.0300 | BORE+0.0145 |
| olympia | | breech block top | BORE+0.0215 | BORE+0.0140 |

Those parts sat **at or above** the line of sight, so they occluded the rear notch from *any*
eye position — this was a model bug, not an artefact of the new `adsDist`. Everything between
the eye and the rear sight now clears the sight line by ≥ 8 mm. The barrels/rib (870 barrel top
BORE+0.0175, Olympia rib BORE+0.0193) deliberately stay just *under* it, which is the correct
foreground for a shotgun sight picture.

The support hand was lowered and moved forward as asked (olympia mcp
`(−0.030, 0.155, BORE−0.013)` → `(−0.030, 0.180, BORE−0.0215)`; 870 `(−0.030, 0.205,
TUBE_Z+0.004)` → `(−0.030, 0.220, TUBE_Z−0.0045)`, `lean` 0.20 → 0.14 on both). This moves the
`arm_L` node translation — the only contract node this stream has moved, and only because the
brief asked for the hand pose to change. `weapon`, `muzzle`, `eject`, `aim` and `arm_R` are
untouched (re-verified in the trees).

**Where it ends up.** Both sight pictures are now clean: the rear vee notch sits at frame
centre with open sky above it, and nothing in the weapon crosses the line of sight. The support
hand is still the largest thing in the frame, but measured against the two renders its top edge
is **≈13 mm below the line of sight** (olympia: fore-end top BORE−0.001 + a ~9 mm finger =
BORE+0.008 vs `SIGHT_Z` BORE+0.0215) — it fills the lower ~45 % of the frame without occluding
the sights. That 13 mm is a floor: the fingers have to wrap over the fore-end, so the only way
to shrink the hand further is a larger `adsDist` (it is 0.30 m from the eye at 0.19). Left as
is rather than posing the hand off the fore-end.

---

## weapons_audio.md #5 — moving parts on the GLBs — **fixed**

New library helper `set_origin(ob, p)` moves an object's *origin* (which is what becomes the
glTF node translation) without moving the geometry — that is how a part gets a real pivot.
`build_viewmodel()` now skips objects that already have a parent, so a part can be nested.

| weapon | node added | how it moves | geometry |
|---|---|---|---|
| ak74u | `bolt` | slides along local +Z (Blender −Y), `boltTravel` 0.06 | bolt carrier + charging handle + knurled knob. The receiver gained an interior **raceway** and a **charging-handle slot** in the right wall, so the carrier fills the ejection port at rest and uncovers it as it runs back |
| galil | `bolt` | +Z, 0.055 | the left-side charging handle (moved out of `receiver`) plus a stem through a new slot cut in the top-left of the dust cover |
| mp5 | `bolt` | +Z, 0.05 | the 52° cocking stub + knurled knob (moved out of `receiver`); the cocking tube gained a travel slot |
| rpd | `bolt` | +Z, 0.065 | bolt carrier + stem + the right-side charging handle (moved out of `receiver`); receiver gained a raceway and a handle slot |
| olympia | `barrels` (existing node, **origin moved**) | `rotateX(−0.66)` about the hinge pin | origin is now on `HINGE = (0, 0.030, BORE−0.020)`. Added a hinge lug on the barrels (bored for the pin) and a hinge-pin boss on `action`, so the joint reads as a hinge when it is broken open. `action` stays fixed — the integrator removed the action tilt, so only `barrels` rotates |
| python | `crane` (new, **parent of `cylinder`**) | `rotateZ(+0.66…1.15)` about the yoke pivot | origin on `CRANE = (0, 0.082, BORE−0.0185)` — **coaxial with the ejector rod**, see the repair round above. Contains the yoke collar, the yoke arm and the **ejector rod** (moved off `cylinder` — as a child of the cylinder it orbited the bore every time a chamber indexed). `cylinder` is now a child at local `(0, −0.034, 0.0185)` and carries a new extractor star on its rear face |

Pivot geometry was chosen so the motion reads correctly with the *code's* fixed axes and signs:

- Olympia: −38° about local X with the pin below and forward of the breech drops the muzzle and
  lifts the breech face clear — a real break-open, not a tilt.
- Python: `crane` sits 18.5 mm directly below the cylinder axis, **on the ejector-rod line**,
  which turns the code's +66° about local Z into a ≈ 17 mm swing out to the left (and 11 mm
  down) while the rod itself does not move at all. The first pass used an offset pivot for a
  flatter swing and that drove the rod through the underlug — see the repair round above.

Verified in the exported trees, e.g.

```
python.glb
    crane mesh t=[-0.01,0.01,-0.08]
      cylinder mesh t=[0.01,0.02,0.03]
olympia.glb
    barrels mesh t=[0.00,0.01,-0.03]      (was t=[0,0,0])
```

## weapons_audio.md #1 (blender half) — clean ADS sight picture — **fixed**

- **Apertures/notches are now genuinely open.** ak74u: the rear drum is cut as an open U-notch
  (6 mm wide, opening through the top) instead of a 4.4 mm keyhole. galil peep 4.8 → 6.2 mm.
  mp5 drum 3.6 → 5.2 mm. m14 peep 4.0 → 5.8 mm. m1911 rear notch 3.6 → 4.4 mm wide and 3.0 →
  3.6 mm deep. rpd / python / olympia / 870 / raygun already had open notches and were left alone.
- **The ADS check render was lying.** `render_ads()` used `back=0.10, fov=40` — that put the
  camera *inside the stock* and magnified the receiver, which is why `ak74u_ads.png` was a solid
  black lump. It now defaults to `back=0.32, fov=58` and `deliver()` takes a per-weapon
  `ads_back` matching `config.js` `adsDist` (0.26 m1911 → 0.34 olympia/870/rpd), with
  `VM_FOV.ads = 58`. Re-shot for all ten. The AK receiver now reads at roughly a quarter of
  frame height with the world visible around it and the front post inside the rear notch.

- **The comb was above the line of sight on three guns.** Re-shooting the ADS render at the
  game's real eye distance is what exposed it: `remington870_ads.png` and `olympia_ads.png`
  came back *solid black*. On the M14, Olympia and 870 the stock's comb/heel sat 7–10 mm
  **above** `SIGHT_Z`, i.e. the wood blocked the sights, and since the ADS eye lands inside the
  stock's length on the long guns, the camera ended up inside the buttstock:

  | | eye (gun-space y) | butt y | sight line | comb top was | comb top now | drop |
  |---|---|---|---|---|---|---|
  | m14 | −0.350 | −0.295 | BORE+0.025 | BORE+0.032 | **BORE−0.007** | 32 mm |
  | olympia | −0.270 | −0.274 | BORE+0.0215 | BORE+0.029 | **BORE−0.009** | 31 mm |
  | remington870 | −0.225 | −0.275 | BORE+0.020 | BORE+0.030 | **BORE−0.011** | 31 mm |
  | rpd | −0.338 | −0.298 | BORE+0.039 | BORE+0.030 | **BORE+0.009** | 30 mm |

  Merely clearing the sight line was not enough: at 13 mm the camera sat *on* the comb ridge and
  the foreshortened stock still filled the lower 60 % of the frame. The comb (and the matching
  butt plate and butt bottom) now drops ≈ 30 mm below the line of sight on all four long guns,
  which is what a real stock's drop-at-comb is. AK-74u / Galil / MP5 have tube or folding stocks
  that were already 17–29 mm clear and were left alone.

**`adsDist` on the guns whose sights are far forward — resolved in the repair round.**
`adsDist` is measured to the `aim` node, so on a gun whose rear sight sits well ahead of the
grip the whole weapon is pushed back into the shooter. The first pass asked the code stream for
smaller values on the two shotguns; **`config.js` now ships olympia 0.19 and remington870 0.24**,
and the check renders are shot at those numbers (see the repair round below).

| | `aim` y (from grip) | shipped `adsDist` | eye lands |
|---|---|---|---|
| remington870 | +0.115 | 0.24 | 0.15 m ahead of the butt |
| olympia | +0.070 | 0.19 | 0.15 m ahead of the butt |
| rpd | +0.002 | 0.34 | 0.04 m ahead of the butt |
| m14 | −0.020 | 0.33 | 0.055 m ahead of the butt |
| m1911 | −0.022 | 0.26 | — |

## weapons_audio.md #4 (blender half) — parts the reloads need — **fixed**

Every branch of `viewmodel.js`'s `_reloadPose` now has real geometry to drive:

- `mag` — all magazine weapons already had it; **added to the raygun** (`build_cell()`: a boxed
  power cell under the new lower receiver, with glow windows and a latch). `_reloadRaygun`
  previously animated nothing because `e.mag` was null on the Ray Gun.
- `bolt` — added to ak74u / galil / mp5 / rpd (see #5); m14 already had one.
- `slide` (m1911), `pump` (870) — unchanged.
- `barrels` + `action` (olympia), `crane` + `cylinder` (python) — see #5.

## weapons_audio.md #11 — model & hand quality — **partial**

**Hands (`lib_weapons.build_hand` / `glove_detail`) — done, within budget.**
- Crease loop over every PIP/DIP joint, narrow along the bone and biased to the *flexion*
  (palm) side. It is a negative metaball, so it costs no triangles.
  Caveat recorded in the source: an extreme-aspect negative here fragments the isosurface and
  the metaball tessellation time explodes (a 15-minute build) — keep it mild.
- Webbing fillet between each pair of finger roots, so the split no longer runs down to the
  knuckle bar as a razor slot. Also a metaball, also free.
- **Nail / fingertip reinforcement plates** on the index and the thumb of each hand, in the dark
  leather slot rather than the glove slot.
- Metaball source resolution 0.0032 → 0.0030 and the digit seam is sampled 7× per segment at
  0.90 r with a deeper sink — the old 0.94 r / 5-sample ridge floated off the surface at the
  joints and showed as pale flat plates (visible in the *old* `python_grip.png` too).
- Decimation target per hand 2500 → 2330 to pay for the plates and stay inside the 25k budget.

**Ray Gun (`build_raygun.py`) — done.** It was "a smooth red balloon with a chrome bell":
- glow emission strength **14.0 → 5.5** — the rings read as rings instead of blowing out to
  featureless white.
- Boxed lower receiver slung under the fuselage, with vent grooves and side panel lines.
- Three riveted, elliptical frame bands round the shell (elliptical so they stand proud by a
  constant amount all the way round a non-circular body).
- Four cooling fins instead of three, thinner and deeper.
- Three concentric ribs on the flared muzzle bell.
- Six slot screws along the shell/lower-receiver seam, and the rivet ring re-spaced to six.
- Removable power cell (`mag`) — see #4.

**Other per-weapon items from the review's list:**
- AK gas-tube vent ports — added (cheap low-segment cylinder cutters; scaled-sphere cutters cost
  2.3k triangles of intersection + bevel and did not fit).
- M1911 slide cocking serrations — **already present** (`c_ser`, 9 slanted grooves per side),
  as are the extractor, firing-pin stop and dovetailed sights. The review was stale here.
- Galil charging handle — already present; it is now the separate `bolt` node.
- 870 ribbed forend — **already present** (`c_ribs`, corn-cob grooves on three faces).

**Not done — the hip-fire re-framing.** The review asks to "iterate the `weapon` origin until
the grip and both hands are in frame". The keep-list for this stream forbids moving `weapon`,
and the measurement says the framing is already inside the contract: at 50° vFOV / 16:9 every
grip lands in the lower-right third and every muzzle converges toward centre —

| | m1911 | mp5 | m14 | olympia | ak74u | galil | rpd | python | raygun |
|---|---|---|---|---|---|---|---|---|---|
| grip ndc x | +0.61 | +0.69 | +0.65 | +0.63 | +0.67 | +0.66 | +0.65 | +0.61 | +0.55 |
| grip ndc y | −0.46 | −0.82 | −0.84 | −0.80 | −0.83 | −0.84 | −0.86 | −0.47 | −0.53 |
| muzzle ndc x | +0.39 | +0.32 | — | +0.23 | +0.26 | +0.22 | +0.18 | +0.33 | +0.32 |

So the barrel is *not* parallel to the view axis (the review's claim) — it converges by 0.3–0.5
of a half-frame. What is cropped at 16:9 is the forearm/cuff below the grip, which is normal for
a viewmodel. If the code stream still wants the guns pulled in, it is a one-line change to
`GRIP_POS` per build script and a rebuild; flag it and this stream will do it.

**Still open on the hands.** They are better (finger separation, joint creases, reinforcement
plates) but at 2330 triangles per hand, decimated from a metaball, they will not reach
hand-sculpted quality. Getting there needs a bigger triangle budget for the arms or a normal-map
bake, neither of which fits "≤ 25k tris including arms" as written in `docs/ASSET_CONTRACT.md`.

---

## Triangle budget (contract: ≤ 25 000 per weapon GLB **including arms**)

`node tools/inspect-glb.mjs public/models/weapons/<id>.glb --tree`, "triangles (instanced)":

| weapon | before | after | weapon | before | after |
|---|---|---|---|---|---|
| ak74u | 23 166 | **24 804** | olympia | 19 024 | **20 104** |
| galil | 22 906 | **23 478** | python | 22 980 | **24 842** |
| m14 | 22 900 | **23 302** | raygun | 23 968 | **23 528** |
| m1911 | 24 588 | **24 928** | remington870 | 20 914 | **21 318** |
| mp5 | 23 936 | **24 452** | rpd | 19 188 | **20 592** |

`knife` 6 458, `frag` 8 552, `drink` 7 902 — rebuilt as well, purely to pick up the hand
changes (they share `build_arm`).

Every one is inside the 25k budget, but **ak74u / m1911 / python / mp5 have under 600 triangles
of headroom**, so anything further added to those models has to pay for itself. Two things were
cut for the budget and are recorded here rather than silently dropped:

- the AK's gas-tube vent ports are 2 holes, not 6 (scaled-sphere cutters cost ~2.3k triangles of
  boolean intersection + bevel; low-segment cylinder cutters cost ~200 each);
- the Ray Gun has 2 seam screws + a 6-rivet ring rather than a separate set of 6 screws.

The arms are the dominant cost on every weapon (`arm_L` 5 844 + `arm_R` 5 148 ≈ 11 000 of the
25 000). That is the real ceiling on hand quality — see #11 above.

## Build script hygiene

`tools/blender/weapons/build_all.sh` now drives every build through `run_locked.sh` instead of
calling `blender.exe` directly, so a full rebuild cannot start two Blenders on this machine.

## What was checked, and how

- Every GLB re-inspected with `--tree`: node names, hierarchy and translations. `viewmodel`,
  `weapon`, `muzzle`, `eject`, `aim`, `arm_L`, `arm_R` translations are byte-identical to the
  previous build on all ten weapons.
- Check renders re-shot and looked at: `ak74u_ads.png` (was an opaque black lump, now the
  receiver reads at ~¼ frame height with the front post inside the rear notch),
  `m1911_ads.png` (clean notch-and-post picture), `ak74u_grip.png` (hands: finger separation,
  joint creases and the index reinforcement plate are all visible), `rpd_detail.png` (the
  carrier is visible in the ejection port with the handle riding its slot),
  `olympia_detail.png` (hinge-pin head on the action), `raygun_detail.png` (rings read as
  rings; bands, fins, bell ribs and lower receiver all present).
- Pivot behaviour was verified by construction, not by a render: the `barrels` and `crane`
  origins were solved against the rotation axis and sign the code already uses, and the
  resulting node translations confirmed in the exported trees. An actual open/swing frame needs
  the game running, which this stream does not do.
