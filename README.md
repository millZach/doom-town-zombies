# Zombies — Doom Town

A browser survival shooter in the style of Black Ops 2 Zombies, built with Three.js. All models are
original, authored by Python build scripts in Blender 5.2. Audio is recorded/generated sound
effects (see `CREDITS.md`) with a synthesised fallback.

## Play

```
npm install
npm run dev
```

Open http://localhost:5173 in Chrome or Edge, click **Play Solo**.

| | |
|---|---|
| Move / sprint / jump / crouch | W A S D · Shift · Space · C |
| Fire / aim | Mouse 1 · Mouse 2 |
| Reload · Use/buy/rebuild · Knife · Grenade | R · F · V · G |
| Switch weapon | 1 · 2 · mouse wheel |
| Pause | Esc |
| FPS counter | F3 |

**Xbox controller** (plug in or pair before or during play; menus work with the D-pad/stick, A, B, Start):

| | |
|---|---|
| Move / look | Left stick / right stick |
| Sprint / knife | L3 (click to sprint while pushing forward) / R3 |
| Aim / fire | LT / RT |
| Jump / crouch | A / B |
| Reload · use/buy/rebuild | X — reloads, or uses whatever the prompt shows (hold to rebuild) |
| Switch weapon | Y |
| Frag grenade | LB or RB |
| Pause | Start |

BO2-style aim assist (slowdown over zombies, gentle snap on LT) is on by default; stick
sensitivity, aim assist and invert look are in Options. Browsers don't count a controller
press as a user gesture, so if you start with only the controller, click or press a key once
to turn the sound on.

Graphics quality (High / Medium / Low) is in Options. If the game can't hold ~40 fps it steps the
quality down by itself and tells you. The first load takes ~15 s (≈120 MB of models); the first
click in the menu starts the audio.

**Late-round test:** open http://localhost:5173/?test=r21 — the menu button becomes *Play Test — Round 21*
and every game (and retry) starts at round 21 with all doors open, power on, Juggernog, Speed Cola
and Double Tap, a Pack-a-Punched Galil and Ray Gun, and 50,000 points.

## What's in it

Two-storey houses (debris on the stairs to clear, upstairs windows zombies climb in through),
back doors out to both backyards, and the fallout shelter under the street.
Endless rounds with BO2 health/count scaling, points economy (10/hit, 50–130/kill), buyable doors,
window barricades zombies tear down and you rebuild, chalk wall-buys, the Mystery Box (teddy bear
moves it), four perks (Juggernog, Speed Cola, Quick Revive with solo self-revive, Double Tap), power
switch, Pack-a-Punch with animated camo and upgraded weapons, power-ups (Max Ammo, Insta-Kill,
Double Points, Kaboom, Carpenter, Fire Sale) and hellhound rounds.

## Layout

- `src/` — game code (`game/` rules, `ai/` zombies, `player/` movement + weapons, `world/` map/nav/sky,
  `fx/` particles + decals, `ui/` HUD, `audio/` procedural sound engine)
- `tools/blender/<area>/build_*.py` — asset build scripts (re-run to regenerate `public/models`)
- `docs/ASSET_CONTRACT.md` — node/clip naming contract between the Blender assets and the game
- `tools/inspect-glb.mjs` — inspect an exported model; `tools/audio-test.html` — audition every sound

Rebuild an asset: `"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python tools/blender/<area>/<script>.py`

If `public/models/map_doomtown.glb` is missing the game runs on a built-in grey-box layout.
