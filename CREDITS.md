# Credits

Doom Town is an original game. Nothing here is taken from Call of Duty or any other
commercial title — no ripped assets, no copied music, no reproduced logos. What follows
is every third-party source used to build the shipped audio in `public/audio/**`, with
its licence.

Every file in `public/audio/**` is a *derivative*: the source recordings were sliced,
pitched, filtered, layered, loudness-normalised and re-encoded by
`tools/audio/build.py`. The originals are not redistributed.

---

## Sound effects and voice generated with ElevenLabs

Zombie and hellhound vocals, the player's pain and effort sounds, the four round
stingers, the four perk jingles, the Ray Gun, the mystery-box teddy laugh, the music
box, the power switch, the Pack-a-Punch machine, the power-up cues, the hellhound
lightning strike, the nuke and the grenade blasts were generated with
**[ElevenLabs](https://elevenlabs.io)** (sound generation + text-to-speech). The
announcer lines ("Max Ammo!", "Insta-Kill!", "Double Points!", "Kaboom!",
"Carpenter!", "Fire Sale!") are ElevenLabs text-to-speech, processed into an old
PA/field-radio voice.

Generated on the ElevenLabs **free plan**, which is for **non-commercial use with
attribution**. If this project is ever distributed commercially, these files must be
regenerated on a paid ElevenLabs plan or replaced. Every generation is logged in
`tools/audio/elevenlabs_log.csv`.

---

## Recorded sources

### Kenney — CC0 1.0 (public domain)

<https://kenney.nl> · "free to use in personal, educational and commercial projects".

| Pack | Used for |
|---|---|
| Impact Sounds | footsteps (dirt / wood / concrete), zombie and hellhound footsteps, landings, surface impacts, flesh hits, headshots, knife hits, body falls, board slams |
| Interface Sounds | UI click / hover / back, purchase confirmation, purchase denial, hit markers, radio blips |
| RPG Audio | weapon raise / lower / swap, ADS in / out, belt handling, coin handling for purchases, Ray Gun mechanism |
| Sci-Fi Sounds | Pack-a-Punch energy layer, power-up beacon loop |
| Digital Audio | power-up pickup cues (Max Ammo, Insta-Kill, Double Points, Carpenter, Fire Sale), power-up blink |

### OpenGameArt — all CC0 1.0 (public domain)

| Submission | Author | Used for |
|---|---|---|
| [The Free Firearm Sound Library](https://opengameart.org/content/the-free-firearm-sound-library) | bart | **every firearm in the game** — 1911, S&W 642, SKS, AR-15, PPSh, Carl Gustav M45, AK-47, Benelli Nova, Winchester Model 12 |
| [100 CC0 SFX](https://opengameart.org/content/100-cc0-sfx) | rubberduck | mystery box open, gibs, plops |
| [100 CC0 SFX #2](https://opengameart.org/content/100-cc0-sfx-2) | rubberduck | doors, wet impacts |
| [100 CC0 metal and wood SFX](https://opengameart.org/content/100-cc0-metal-and-wood-sfx) | rubberduck | board tear / repair, shell casings, grenade pin and bounce, box close, mechanical clacks |
| [80 CC0 creature SFX](https://opengameart.org/content/80-cc0-creature-sfx) | rubberduck | perk drink, perk burp |
| [Equipment Clicks II](https://opengameart.org/content/equipment-clicks-ii) · [III](https://opengameart.org/content/equipment-clicks-iii) | LFA | bolts, break-action and revolver mechanisms |
| [Gun reload sounds](https://opengameart.org/content/gun-reload-sounds) | SpringySpringo | rifle / SMG / LMG magazines |
| [Handgun Reload Sound Effect](https://opengameart.org/content/handgun-reload-sound-effect) | zer0_sol | pistol magazines, slide release |
| [Shotgun Reload Sound effects](https://opengameart.org/content/shotgun-reload-sound-effects) | zer0_sol | shell loading, revolver eject |
| [Gun reload, lock or click sound](https://opengameart.org/content/gun-reload-lock-or-click-sound) | pauliuw | dry fire |
| [2 Gun Reloads](https://opengameart.org/content/2-gun-reloads) | StarNinjas | extra mechanical layers |
| [4 Door Closes](https://opengameart.org/content/4-door-closes) | StarNinjas | doors |
| [20 Sword Sound Effects](https://opengameart.org/content/20-sword-sound-effects-attacks-and-clashes) | StarNinjas | knife swing |
| [Different steps on wood, stone, leaves, gravel and mud](https://opengameart.org/content/different-steps-on-wood-stone-leaves-gravel-and-mud) | TinyWorlds | footstep variety |
| [Door Open, Door Close Set](https://opengameart.org/content/door-open-door-close-set) | qubodup | doors |
| [Creaky Door Hinge Spooky](https://opengameart.org/content/creaky-door-hinge-spooky) | w.forster.1 | door open |
| [Explosions](https://opengameart.org/content/explosions-4) | EZduzziteh | grenade blasts |
| [Chunky Explosion](https://opengameart.org/content/chunky-explosion) | Joth | grenade blasts |
| [Fire Crackling](https://opengameart.org/content/fire-crackling) | AntumDeluge | the fire loop |
| [Mild Wind Background Noise](https://opengameart.org/content/mild-wind-background-noise) | Bashar3A | ambience, the menu bed |
| [Dark Ambiences](https://opengameart.org/content/dark-ambiences) | Ogrebane | ambience |

### Versilian Community Sample Library (VCSL) — CC0 1.0 (public domain)

<https://github.com/sgossner/VCSL> · Versilian Studios / Sam Gossner.

Pipe organ (quiet pedal and manual), tubular bells, gong, timpani and bass drum. These
are the instruments underneath the four round stingers, the menu bed, the death bed, the
in-round tension layers and the heartbeat loop.

---

## Licence summary

| Source | Licence | Attribution required | Commercial use |
|---|---|---|---|
| Kenney packs | CC0 1.0 | no (credited anyway) | yes |
| OpenGameArt submissions above | CC0 1.0 | no (credited anyway) | yes |
| VCSL | CC0 1.0 | no (credited anyway) | yes |
| ElevenLabs (free plan) | ElevenLabs Terms | **yes** | **no** — see above |

No CC-BY-SA, GPL or non-commercial-only material is used. No copyrighted game audio is
used.
