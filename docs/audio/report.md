# Audio verification report

`public/audio/**` — 339 files across 132 sound names, 4.10 MB total.

Measured with ffmpeg + numpy (`tools/audio/verify.py`). **Harsh** is the fraction of spectral energy above 5 kHz; it is the number that catches a screech. **LUFS** is ffmpeg's gated integrated loudness, **TP** its true peak.

## Summary

- Files over -1.5 dBTP: **0** (none)
- Files over -1.0 dBTP: **0** (none)
- Files flagged harsh for their group: **3** — handling/reload_lmg_belt_2.ogg, handling/reload_revolver_eject_2.ogg, handling/shell_drop_1.ogg

### Per-group loudness hierarchy

| group | files | median LUFS | max TP | median harsh | max harsh |
|---|---:|---:|---:|---:|---:|
| foley | 39 | -26.9 | -2.15 | 0.05% | 23.44% |
| music | 3 | -24.0 | -6.09 | 0.00% | 1.98% |
| handling | 84 | -23.2 | -2.06 | 19.16% | 73.16% |
| ui | 17 | -23.0 | -4.52 | 10.21% | 40.81% |
| stingers | 4 | -21.6 | -7.81 | 0.00% | 0.00% |
| world | 24 | -20.0 | -2.27 | 0.05% | 36.66% |
| impacts | 43 | -20.0 | -3.08 | 0.00% | 3.19% |
| voices | 79 | -19.0 | -2.81 | 0.15% | 7.70% |
| guns | 46 | -14.2 | -1.62 | 1.15% | 19.91% |

## Every file

| sound | file | s | peak dBFS | TP dBTP | LUFS | >5 kHz | centroid Hz | source |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `ads_in` | handling/ads_in_1.ogg | 0.28 | -8.36 | -5.22 | -23.2 | 4.58% | 3980 | Kenney RPG Audio |
| `ads_in` | handling/ads_in_2.ogg | 0.30 | -7.98 | -4.85 | -23.7 | 40.66% | 6581 | Kenney RPG Audio |
| `ads_in` | handling/ads_in_3.ogg | 0.28 | -7.86 | -4.80 | -23.1 | 0.63% | 2257 | Kenney RPG Audio |
| `ads_out` | handling/ads_out_1.ogg | 0.28 | -8.37 | -5.28 | -23.2 | 33.82% | 5340 | Kenney RPG Audio |
| `ads_out` | handling/ads_out_2.ogg | 0.28 | -8.11 | -5.08 | -23.1 | 1.21% | 2479 | Kenney RPG Audio |
| `ads_out` | handling/ads_out_3.ogg | 0.28 | -8.27 | -5.25 | -23.1 | 0.54% | 2059 | Kenney RPG Audio |
| `ambient_loop` | world/ambient_loop.ogg | 16.00 | -2.91 | -2.91 | -26.3 | 0.00% | 312 | OGA wind + dark ambiences |
| `board_repair` | foley/board_repair_1.ogg | 0.31 | -7.28 | -4.25 | -21.1 | 0.19% | 1586 | OGA 100 CC0 metal & wood SFX |
| `board_repair` | foley/board_repair_2.ogg | 0.23 | -7.63 | -4.61 | -21.1 | 0.01% | 1071 | OGA 100 CC0 metal & wood SFX |
| `board_slam` | foley/board_slam_1.ogg | 0.56 | -6.98 | -3.96 | -20.9 | 0.01% | 916 | Kenney Impact Sounds |
| `board_slam` | foley/board_slam_2.ogg | 0.54 | -7.21 | -4.20 | -20.9 | 0.00% | 590 | Kenney Impact Sounds |
| `board_slam` | foley/board_slam_3.ogg | 0.53 | -7.41 | -4.40 | -20.9 | 0.00% | 649 | Kenney Impact Sounds |
| `board_tear` | foley/board_tear_1.ogg | 0.52 | -6.66 | -3.63 | -21.1 | 5.53% | 2965 | OGA 100 CC0 metal & wood SFX |
| `board_tear` | foley/board_tear_2.ogg | 0.62 | -7.35 | -4.07 | -21.2 | 23.44% | 4225 | OGA 100 CC0 metal & wood SFX |
| `board_tear` | foley/board_tear_3.ogg | 0.18 | -6.75 | -3.73 | -21.2 | 18.38% | 4392 | OGA 100 CC0 metal & wood SFX |
| `bolt_pull` | handling/bolt_pull_1.ogg | 0.31 | -8.10 | -5.09 | -23.4 | 12.99% | 4245 | OGA equipment clicks |
| `bolt_pull` | handling/bolt_pull_2.ogg | 0.28 | -5.87 | -2.69 | -23.1 | 3.05% | 3585 | OGA equipment clicks |
| `bolt_release` | handling/bolt_release_1.ogg | 0.24 | -6.10 | -2.59 | -23.2 | 26.09% | 6187 | OGA equipment clicks |
| `bolt_release` | handling/bolt_release_2.ogg | 0.35 | -6.08 | -2.06 | -23.2 | 18.20% | 5846 | OGA equipment clicks |
| `box_close` | foley/box_close.ogg | 0.37 | -7.29 | -4.28 | -21.1 | 1.64% | 2410 | OGA 100 CC0 metal & wood SFX |
| `box_music` | music/box_music.ogg | 4.60 | -9.43 | -6.09 | -23.6 | 1.98% | 4294 | ElevenLabs box_music |
| `box_open` | foley/box_open.ogg | 0.35 | -7.11 | -4.10 | -21.1 | 2.34% | 2492 | OGA 100 CC0 SFX |
| `box_teddy` | world/box_teddy.ogg | 4.50 | -9.41 | -6.38 | -21.4 | 2.83% | 3288 | ElevenLabs box_teddy |
| `carpenter` | world/carpenter.ogg | 0.39 | -11.69 | -8.45 | -20.0 | 2.26% | 2962 | Kenney Digital Audio |
| `door_open` | foley/door_open_1.ogg | 0.64 | -6.68 | -3.33 | -21.2 | 18.68% | 4439 | OGA door SFX |
| `door_open` | foley/door_open_2.ogg | 0.84 | -5.18 | -2.15 | -21.2 | 8.14% | 3577 | OGA door SFX |
| `double_points` | world/double_points.ogg | 0.37 | -11.38 | -8.19 | -19.9 | 1.99% | 3027 | Kenney Digital Audio |
| `dry_fire` | handling/dry_fire_1.ogg | 0.04 | -9.33 | -6.09 | -23.1 | 17.12% | 4153 | OGA gun lock click |
| `dry_fire` | handling/dry_fire_2.ogg | 0.04 | -11.57 | -8.55 | -23.1 | 8.34% | 4502 | OGA gun lock click |
| `dry_fire` | handling/dry_fire_3.ogg | 0.04 | -11.24 | -8.23 | -23.1 | 10.83% | 4358 | OGA gun lock click |
| `explosion` | guns/explosion_1.ogg | 0.76 | -7.87 | -4.86 | -12.6 | 0.23% | 2656 | ElevenLabs + OGA explosions |
| `explosion` | guns/explosion_2.ogg | 2.25 | -7.88 | -4.85 | -13.8 | 0.00% | 496 | ElevenLabs + OGA explosions |
| `explosion` | guns/explosion_3.ogg | 2.40 | -5.95 | -2.80 | -11.9 | 7.74% | 3495 | ElevenLabs + OGA explosions |
| `fire_loop` | world/fire_loop.ogg | 1.87 | -6.15 | -3.08 | -26.0 | 0.14% | 1767 | OGA fire crackling |
| `fire_sale` | world/fire_sale.ogg | 0.40 | -11.41 | -8.28 | -20.0 | 2.41% | 3194 | Kenney Digital Audio |
| `flesh_hit` | impacts/flesh_hit_1.ogg | 0.43 | -7.80 | -4.78 | -19.9 | 0.00% | 582 | Kenney Impact Sounds |
| `flesh_hit` | impacts/flesh_hit_2.ogg | 0.39 | -7.93 | -4.92 | -20.0 | 0.00% | 673 | Kenney Impact Sounds |
| `flesh_hit` | impacts/flesh_hit_3.ogg | 0.45 | -8.26 | -5.25 | -19.9 | 0.03% | 1214 | Kenney Impact Sounds |
| `footstep_concrete` | foley/footstep_concrete_1.ogg | 0.10 | -8.09 | -5.08 | -26.8 | 0.00% | 1099 | Kenney Impact Sounds + OGA Different Steps |
| `footstep_concrete` | foley/footstep_concrete_2.ogg | 0.10 | -7.56 | -4.54 | -27.0 | 0.05% | 2285 | Kenney Impact Sounds + OGA Different Steps |
| `footstep_concrete` | foley/footstep_concrete_3.ogg | 0.10 | -7.30 | -4.29 | -26.8 | 0.03% | 1942 | Kenney Impact Sounds + OGA Different Steps |
| `footstep_concrete` | foley/footstep_concrete_4.ogg | 0.11 | -7.58 | -4.56 | -26.7 | 0.00% | 1175 | Kenney Impact Sounds + OGA Different Steps |
| `footstep_dirt` | foley/footstep_dirt_1.ogg | 0.23 | -7.21 | -4.20 | -27.0 | 1.03% | 3094 | Kenney Impact Sounds + OGA Different Steps |
| `footstep_dirt` | foley/footstep_dirt_2.ogg | 0.26 | -7.37 | -4.36 | -27.1 | 2.29% | 3744 | Kenney Impact Sounds + OGA Different Steps |
| `footstep_dirt` | foley/footstep_dirt_3.ogg | 0.24 | -6.87 | -3.86 | -27.1 | 2.03% | 3396 | Kenney Impact Sounds + OGA Different Steps |
| `footstep_dirt` | foley/footstep_dirt_4.ogg | 0.23 | -7.31 | -4.30 | -26.9 | 0.65% | 3039 | Kenney Impact Sounds + OGA Different Steps |
| `footstep_wood` | foley/footstep_wood_1.ogg | 0.28 | -7.11 | -4.10 | -26.9 | 0.00% | 64 | Kenney Impact Sounds + OGA Different Steps |
| `footstep_wood` | foley/footstep_wood_2.ogg | 0.27 | -8.56 | -5.54 | -27.4 | 0.00% | 65 | Kenney Impact Sounds + OGA Different Steps |
| `footstep_wood` | foley/footstep_wood_3.ogg | 0.24 | -8.96 | -5.95 | -26.9 | 0.00% | 373 | Kenney Impact Sounds + OGA Different Steps |
| `footstep_wood` | foley/footstep_wood_4.ogg | 0.25 | -7.26 | -4.25 | -26.9 | 0.00% | 365 | Kenney Impact Sounds + OGA Different Steps |
| `game_over` | stingers/game_over.ogg | 10.20 | -10.32 | -10.32 | -21.2 | 0.00% | 680 | ElevenLabs sting + VCSL organ/bell/gong/timpani |
| `grenade_bounce` | handling/grenade_bounce_1.ogg | 0.20 | -8.43 | -5.39 | -23.3 | 19.16% | 4579 | OGA 100 CC0 metal & wood SFX |
| `grenade_bounce` | handling/grenade_bounce_2.ogg | 0.31 | -8.01 | -4.90 | -23.3 | 24.94% | 5408 | OGA 100 CC0 metal & wood SFX |
| `grenade_bounce` | handling/grenade_bounce_3.ogg | 0.30 | -10.75 | -7.69 | -23.6 | 13.59% | 4370 | OGA 100 CC0 metal & wood SFX |
| `grenade_pin` | handling/grenade_pin_1.ogg | 0.40 | -8.37 | -5.30 | -23.3 | 26.85% | 4980 | OGA 100 CC0 metal & wood SFX |
| `grenade_pin` | handling/grenade_pin_2.ogg | 0.39 | -8.53 | -5.52 | -23.2 | 18.83% | 4989 | OGA 100 CC0 metal & wood SFX |
| `gun_ak74u` | guns/gun_ak74u_1.ogg | 0.43 | -5.60 | -2.56 | -14.8 | 0.78% | 2424 | FFSL PPSh |
| `gun_ak74u` | guns/gun_ak74u_2.ogg | 0.43 | -4.98 | -1.96 | -14.9 | 0.75% | 2396 | FFSL PPSh |
| `gun_ak74u` | guns/gun_ak74u_3.ogg | 0.43 | -5.96 | -2.20 | -14.8 | 0.73% | 2353 | FFSL PPSh |
| `gun_ak74u` | guns/gun_ak74u_4.ogg | 0.43 | -5.25 | -1.87 | -14.8 | 0.80% | 2355 | FFSL PPSh |
| `gun_galil` | guns/gun_galil_1.ogg | 0.62 | -5.39 | -2.14 | -14.4 | 0.70% | 2150 | FFSL AR-15 |
| `gun_galil` | guns/gun_galil_2.ogg | 0.62 | -6.31 | -3.26 | -14.4 | 0.65% | 2186 | FFSL AR-15 |
| `gun_galil` | guns/gun_galil_3.ogg | 0.62 | -7.57 | -4.51 | -13.5 | 1.63% | 2515 | FFSL AR-15 |
| `gun_galil` | guns/gun_galil_4.ogg | 0.62 | -7.98 | -4.92 | -13.1 | 0.03% | 1251 | FFSL AR-15 |
| `gun_m14` | guns/gun_m14_1.ogg | 0.41 | -5.14 | -2.01 | -14.8 | 0.75% | 2295 | FFSL SKS |
| `gun_m14` | guns/gun_m14_2.ogg | 0.42 | -6.04 | -2.91 | -14.8 | 0.83% | 2341 | FFSL SKS |
| `gun_m14` | guns/gun_m14_3.ogg | 0.43 | -5.58 | -2.36 | -14.8 | 0.80% | 2300 | FFSL SKS |
| `gun_m14` | guns/gun_m14_4.ogg | 0.45 | -5.45 | -2.13 | -14.8 | 0.83% | 2268 | FFSL SKS |
| `gun_m1911` | guns/gun_m1911_1.ogg | 0.62 | -5.89 | -2.64 | -14.0 | 1.15% | 2837 | FFSL 1911 |
| `gun_m1911` | guns/gun_m1911_2.ogg | 0.62 | -4.78 | -1.71 | -14.1 | 1.18% | 2875 | FFSL 1911 |
| `gun_m1911` | guns/gun_m1911_3.ogg | 0.38 | -7.95 | -4.33 | -13.2 | 1.80% | 2743 | FFSL 1911 |
| `gun_m1911` | guns/gun_m1911_4.ogg | 0.42 | -8.12 | -5.10 | -13.1 | 0.44% | 2088 | FFSL 1911 |
| `gun_mp5` | guns/gun_mp5_1.ogg | 0.44 | -5.66 | -2.47 | -14.8 | 1.44% | 2810 | FFSL Carl Gustav M45 |
| `gun_mp5` | guns/gun_mp5_2.ogg | 0.40 | -5.77 | -2.16 | -15.0 | 1.49% | 2849 | FFSL Carl Gustav M45 |
| `gun_mp5` | guns/gun_mp5_3.ogg | 0.40 | -5.55 | -2.33 | -14.8 | 1.47% | 2800 | FFSL Carl Gustav M45 |
| `gun_mp5` | guns/gun_mp5_4.ogg | 0.50 | -6.61 | -3.38 | -12.9 | 1.35% | 2778 | FFSL Carl Gustav M45 |
| `gun_olympia` | guns/gun_olympia_1.ogg | 0.88 | -5.58 | -2.20 | -14.2 | 1.47% | 2689 | FFSL Model 12 |
| `gun_olympia` | guns/gun_olympia_2.ogg | 0.88 | -5.17 | -1.88 | -14.3 | 1.21% | 2605 | FFSL Model 12 |
| `gun_olympia` | guns/gun_olympia_3.ogg | 0.54 | -7.95 | -4.87 | -13.4 | 2.57% | 2695 | FFSL Model 12 |
| `gun_olympia` | guns/gun_olympia_4.ogg | 0.50 | -7.64 | -3.89 | -12.8 | 1.61% | 2673 | FFSL Model 12 |
| `gun_pap_layer` | handling/gun_pap_layer_1.ogg | 0.57 | -14.87 | -11.86 | -22.9 | 0.00% | 435 | Kenney Sci-Fi Sounds |
| `gun_pap_layer` | handling/gun_pap_layer_2.ogg | 0.57 | -14.40 | -11.38 | -22.9 | 0.00% | 411 | Kenney Sci-Fi Sounds |
| `gun_pap_layer` | handling/gun_pap_layer_3.ogg | 0.53 | -9.57 | -6.56 | -23.0 | 3.64% | 2818 | Kenney Sci-Fi Sounds |
| `gun_pap_layer_heavy` | impacts/gun_pap_layer_heavy_1.ogg | 0.67 | -11.89 | -8.88 | -19.9 | 0.00% | 358 | Kenney Sci-Fi Sounds |
| `gun_pap_layer_heavy` | impacts/gun_pap_layer_heavy_2.ogg | 0.67 | -11.38 | -8.37 | -20.0 | 0.00% | 336 | Kenney Sci-Fi Sounds |
| `gun_pap_layer_heavy` | impacts/gun_pap_layer_heavy_3.ogg | 0.65 | -7.41 | -4.40 | -20.0 | 0.82% | 2343 | Kenney Sci-Fi Sounds |
| `gun_python` | guns/gun_python_1.ogg | 0.38 | -6.81 | -3.80 | -16.2 | 0.30% | 1896 | FFSL Smith & Wesson 642 |
| `gun_python` | guns/gun_python_2.ogg | 0.38 | -5.10 | -1.98 | -16.2 | 0.26% | 1897 | FFSL Smith & Wesson 642 |
| `gun_python` | guns/gun_python_3.ogg | 0.50 | -7.72 | -4.68 | -13.0 | 1.09% | 2338 | FFSL Smith & Wesson 642 |
| `gun_python` | guns/gun_python_4.ogg | 0.45 | -8.27 | -5.25 | -13.1 | 0.37% | 2171 | FFSL Smith & Wesson 642 |
| `gun_raygun` | guns/gun_raygun_1.ogg | 0.46 | -8.50 | -5.39 | -14.1 | 19.91% | 4556 | ElevenLabs raygun_fire |
| `gun_raygun` | guns/gun_raygun_2.ogg | 0.49 | -8.06 | -4.99 | -14.1 | 0.67% | 2127 | ElevenLabs raygun_fire |
| `gun_raygun` | guns/gun_raygun_3.ogg | 0.54 | -7.94 | -4.93 | -14.0 | 0.01% | 997 | ElevenLabs raygun_fire |
| `gun_remington870` | guns/gun_remington870_1.ogg | 0.79 | -5.53 | -1.62 | -14.3 | 1.22% | 2580 | FFSL Nova |
| `gun_remington870` | guns/gun_remington870_2.ogg | 0.79 | -5.51 | -2.38 | -14.3 | 0.96% | 2484 | FFSL Nova |
| `gun_remington870` | guns/gun_remington870_3.ogg | 0.63 | -7.17 | -3.81 | -13.7 | 1.93% | 2949 | FFSL Nova |
| `gun_remington870` | guns/gun_remington870_4.ogg | 0.50 | -8.18 | -5.15 | -13.5 | 0.32% | 1849 | FFSL Nova |
| `gun_rpd` | guns/gun_rpd_1.ogg | 0.47 | -5.85 | -2.54 | -14.8 | 1.31% | 2492 | FFSL AK-47 |
| `gun_rpd` | guns/gun_rpd_2.ogg | 0.47 | -6.34 | -3.33 | -14.7 | 1.17% | 2449 | FFSL AK-47 |
| `gun_rpd` | guns/gun_rpd_3.ogg | 0.45 | -5.59 | -2.42 | -14.6 | 1.32% | 2496 | FFSL AK-47 |
| `gun_rpd` | guns/gun_rpd_4.ogg | 0.50 | -5.57 | -2.42 | -14.7 | 1.15% | 2393 | FFSL AK-47 |
| `headshot` | impacts/headshot_1.ogg | 0.55 | -8.17 | -5.16 | -20.0 | 0.00% | 456 | Kenney Impact Sounds |
| `headshot` | impacts/headshot_2.ogg | 0.55 | -8.10 | -5.09 | -20.0 | 0.00% | 432 | Kenney Impact Sounds |
| `headshot` | impacts/headshot_3.ogg | 0.55 | -7.72 | -4.71 | -19.9 | 0.00% | 358 | Kenney Impact Sounds |
| `heartbeat_loop` | world/heartbeat_loop.ogg | 1.95 | -9.96 | -6.95 | -25.9 | 0.00% | 100 | VCSL Bass Drum |
| `hellhound_bite` | voices/hellhound_bite_1.ogg | 0.63 | -9.37 | -6.36 | -19.0 | 0.22% | 1575 | ElevenLabs hellhound bite takes |
| `hellhound_bite` | voices/hellhound_bite_2.ogg | 0.31 | -11.00 | -7.96 | -19.0 | 0.07% | 1434 | ElevenLabs hellhound bite takes |
| `hellhound_bite` | voices/hellhound_bite_3.ogg | 0.32 | -11.24 | -8.23 | -19.0 | 0.03% | 1258 | ElevenLabs hellhound bite takes |
| `hellhound_bite` | voices/hellhound_bite_4.ogg | 0.31 | -9.60 | -6.57 | -19.4 | 0.08% | 1314 | ElevenLabs hellhound bite takes |
| `hellhound_bite` | voices/hellhound_bite_5.ogg | 0.27 | -9.37 | -6.33 | -18.9 | 0.04% | 1104 | ElevenLabs hellhound bite takes |
| `hellhound_bite` | voices/hellhound_bite_6.ogg | 0.26 | -8.79 | -5.78 | -18.9 | 0.05% | 1050 | ElevenLabs hellhound bite takes |
| `hellhound_death` | voices/hellhound_death_1.ogg | 1.79 | -8.81 | -5.80 | -18.8 | 0.01% | 1350 | ElevenLabs hellhound death takes |
| `hellhound_death` | voices/hellhound_death_2.ogg | 2.80 | -6.92 | -3.87 | -19.0 | 0.57% | 2000 | ElevenLabs hellhound death takes |
| `hellhound_death` | voices/hellhound_death_3.ogg | 1.10 | -6.68 | -3.67 | -19.0 | 0.00% | 243 | ElevenLabs hellhound death takes |
| `hellhound_death` | voices/hellhound_death_4.ogg | 2.77 | -13.73 | -10.71 | -18.8 | 0.00% | 1353 | ElevenLabs hellhound death takes |
| `hellhound_death` | voices/hellhound_death_5.ogg | 0.90 | -9.63 | -6.58 | -19.0 | 0.51% | 1752 | ElevenLabs hellhound death takes |
| `hellhound_footstep` | foley/hellhound_footstep_1.ogg | 0.22 | -7.43 | -4.42 | -26.9 | 0.86% | 3487 | Kenney Impact Sounds + OGA Different Steps |
| `hellhound_footstep` | foley/hellhound_footstep_2.ogg | 0.25 | -7.61 | -4.59 | -27.0 | 2.30% | 3829 | Kenney Impact Sounds + OGA Different Steps |
| `hellhound_footstep` | foley/hellhound_footstep_3.ogg | 0.25 | -7.85 | -4.83 | -27.6 | 2.33% | 3786 | Kenney Impact Sounds + OGA Different Steps |
| `hellhound_footstep` | foley/hellhound_footstep_4.ogg | 0.22 | -7.06 | -4.05 | -27.0 | 0.44% | 3353 | Kenney Impact Sounds + OGA Different Steps |
| `hellhound_growl` | voices/hellhound_growl_1.ogg | 2.70 | -6.46 | -3.45 | -19.0 | 0.01% | 538 | ElevenLabs hellhound growl takes |
| `hellhound_growl` | voices/hellhound_growl_2.ogg | 3.00 | -6.78 | -3.77 | -19.1 | 0.05% | 1329 | ElevenLabs hellhound growl takes |
| `hellhound_growl` | voices/hellhound_growl_3.ogg | 1.33 | -6.63 | -3.62 | -19.0 | 0.00% | 260 | ElevenLabs hellhound growl takes |
| `hellhound_growl` | voices/hellhound_growl_4.ogg | 3.00 | -6.89 | -3.88 | -19.1 | 0.00% | 357 | ElevenLabs hellhound growl takes |
| `hellhound_growl` | voices/hellhound_growl_5.ogg | 2.13 | -7.03 | -4.02 | -19.0 | 0.00% | 488 | ElevenLabs hellhound growl takes |
| `hellhound_growl` | voices/hellhound_growl_6.ogg | 2.79 | -6.37 | -3.36 | -19.0 | 0.00% | 519 | ElevenLabs hellhound growl takes |
| `hellhound_spawn` | guns/hellhound_spawn.ogg | 4.50 | -5.02 | -1.89 | -11.7 | 4.51% | 7498 | ElevenLabs hellhound_spawn |
| `hellround_start` | stingers/hellround_start.ogg | 5.53 | -7.81 | -7.81 | -22.2 | 0.00% | 556 | ElevenLabs sting + VCSL organ/bell/gong/timpani |
| `hitmarker` | ui/hitmarker_1.ogg | 0.04 | -8.82 | -5.85 | -22.8 | 24.26% | 5219 | Kenney Interface Sounds |
| `hitmarker` | ui/hitmarker_2.ogg | 0.04 | -14.00 | -10.95 | -26.7 | 29.31% | 5322 | Kenney Interface Sounds |
| `hitmarker_head` | ui/hitmarker_head_1.ogg | 0.03 | -10.16 | -6.86 | -23.0 | 30.48% | 5513 | Kenney Interface Sounds |
| `hitmarker_head` | ui/hitmarker_head_2.ogg | 0.03 | -16.56 | -12.29 | -25.8 | 40.81% | 6397 | Kenney Interface Sounds |
| `impact_concrete` | impacts/impact_concrete_1.ogg | 0.50 | -6.09 | -3.08 | -19.9 | 0.41% | 1992 | Kenney Impact Sounds |
| `impact_concrete` | impacts/impact_concrete_2.ogg | 0.50 | -6.74 | -3.73 | -19.9 | 0.47% | 1987 | Kenney Impact Sounds |
| `impact_concrete` | impacts/impact_concrete_3.ogg | 0.50 | -6.71 | -3.43 | -20.1 | 0.40% | 2224 | Kenney Impact Sounds |
| `impact_concrete` | impacts/impact_concrete_4.ogg | 0.50 | -6.50 | -3.45 | -19.9 | 0.72% | 2473 | Kenney Impact Sounds |
| `impact_dirt` | impacts/impact_dirt_1.ogg | 0.13 | -7.70 | -4.69 | -19.9 | 0.00% | 543 | Kenney Impact Sounds |
| `impact_dirt` | impacts/impact_dirt_2.ogg | 0.21 | -8.03 | -5.02 | -19.9 | 0.00% | 256 | Kenney Impact Sounds |
| `impact_dirt` | impacts/impact_dirt_3.ogg | 0.18 | -8.08 | -5.07 | -20.5 | 0.00% | 54 | Kenney Impact Sounds |
| `impact_dirt` | impacts/impact_dirt_4.ogg | 0.16 | -8.22 | -5.21 | -19.8 | 0.00% | 441 | Kenney Impact Sounds |
| `impact_glass` | impacts/impact_glass_1.ogg | 0.23 | -8.55 | -5.54 | -20.1 | 0.00% | 1604 | Kenney Impact Sounds |
| `impact_glass` | impacts/impact_glass_2.ogg | 0.20 | -8.08 | -5.07 | -19.9 | 0.00% | 1784 | Kenney Impact Sounds |
| `impact_glass` | impacts/impact_glass_3.ogg | 0.20 | -7.49 | -4.48 | -20.0 | 0.00% | 1681 | Kenney Impact Sounds |
| `impact_metal` | impacts/impact_metal_1.ogg | 0.32 | -7.95 | -4.93 | -20.0 | 0.00% | 2800 | Kenney Impact Sounds |
| `impact_metal` | impacts/impact_metal_2.ogg | 0.25 | -7.71 | -4.67 | -20.1 | 0.00% | 2355 | Kenney Impact Sounds |
| `impact_metal` | impacts/impact_metal_3.ogg | 0.25 | -7.83 | -4.78 | -20.4 | 0.00% | 2925 | Kenney Impact Sounds |
| `impact_metal` | impacts/impact_metal_4.ogg | 0.40 | -7.77 | -4.68 | -20.1 | 0.00% | 3188 | Kenney Impact Sounds |
| `impact_wood` | impacts/impact_wood_1.ogg | 0.33 | -7.56 | -4.55 | -20.0 | 0.00% | 219 | Kenney Impact Sounds |
| `impact_wood` | impacts/impact_wood_2.ogg | 0.33 | -7.82 | -4.80 | -19.9 | 0.00% | 208 | Kenney Impact Sounds |
| `impact_wood` | impacts/impact_wood_3.ogg | 0.33 | -7.83 | -4.82 | -20.0 | 0.00% | 254 | Kenney Impact Sounds |
| `impact_wood` | impacts/impact_wood_4.ogg | 0.33 | -7.74 | -4.73 | -19.9 | 0.00% | 236 | Kenney Impact Sounds |
| `insta_kill` | world/insta_kill.ogg | 0.96 | -10.81 | -7.66 | -19.7 | 5.39% | 2860 | Kenney Digital Audio |
| `jump_grunt` | voices/jump_grunt_1.ogg | 0.27 | -8.63 | -5.52 | -19.0 | 2.02% | 2857 | ElevenLabs player effort takes |
| `jump_grunt` | voices/jump_grunt_2.ogg | 0.31 | -6.66 | -3.65 | -19.0 | 0.66% | 2340 | ElevenLabs player effort takes |
| `jump_grunt` | voices/jump_grunt_3.ogg | 0.30 | -7.35 | -4.34 | -19.1 | 0.43% | 2307 | ElevenLabs player effort takes |
| `jump_grunt` | voices/jump_grunt_4.ogg | 0.38 | -7.01 | -4.00 | -19.1 | 0.81% | 2646 | ElevenLabs player effort takes |
| `knife_hit` | impacts/knife_hit_1.ogg | 0.50 | -7.52 | -4.51 | -17.6 | 0.00% | 588 | Kenney Impact Sounds |
| `knife_hit` | impacts/knife_hit_2.ogg | 0.50 | -7.68 | -4.67 | -17.4 | 0.00% | 938 | Kenney Impact Sounds |
| `knife_hit` | impacts/knife_hit_3.ogg | 0.42 | -8.25 | -5.24 | -20.1 | 0.00% | 331 | Kenney Impact Sounds |
| `knife_hit_wall` | impacts/knife_hit_wall_1.ogg | 0.24 | -7.83 | -4.82 | -20.1 | 0.00% | 1587 | Kenney Impact Sounds |
| `knife_hit_wall` | impacts/knife_hit_wall_2.ogg | 0.12 | -7.74 | -4.72 | -20.1 | 0.00% | 1217 | Kenney Impact Sounds |
| `knife_hit_wall` | impacts/knife_hit_wall_3.ogg | 0.10 | -8.30 | -5.28 | -19.8 | 0.00% | 1222 | Kenney Impact Sounds |
| `knife_swing` | handling/knife_swing_1.ogg | 0.45 | -10.92 | -7.80 | -23.1 | 24.56% | 5473 | OGA sword SFX (StarNinjas) |
| `knife_swing` | handling/knife_swing_2.ogg | 0.45 | -12.31 | -9.17 | -23.2 | 33.09% | 5487 | OGA sword SFX (StarNinjas) |
| `knife_swing` | handling/knife_swing_3.ogg | 0.45 | -11.00 | -7.88 | -23.1 | 28.75% | 4717 | OGA sword SFX (StarNinjas) |
| `land_hard` | impacts/land_hard_1.ogg | 0.15 | -8.13 | -5.12 | -20.3 | 0.00% | 843 | Kenney Impact Sounds |
| `land_hard` | impacts/land_hard_2.ogg | 0.15 | -7.95 | -4.94 | -20.3 | 0.02% | 1528 | Kenney Impact Sounds |
| `land_hard` | impacts/land_hard_3.ogg | 0.15 | -8.18 | -5.16 | -20.3 | 0.02% | 1478 | Kenney Impact Sounds |
| `land_soft` | foley/land_soft_1.ogg | 0.12 | -7.72 | -4.71 | -26.8 | 0.00% | 1006 | Kenney Impact Sounds |
| `land_soft` | foley/land_soft_2.ogg | 0.11 | -7.12 | -4.10 | -26.9 | 0.04% | 1856 | Kenney Impact Sounds |
| `land_soft` | foley/land_soft_3.ogg | 0.12 | -7.30 | -4.28 | -26.9 | 0.03% | 1857 | Kenney Impact Sounds |
| `low_ammo` | ui/low_ammo_1.ogg | 0.19 | -7.57 | -4.52 | -23.2 | 26.62% | 4914 | Kenney RPG Audio |
| `low_ammo` | ui/low_ammo_2.ogg | 0.19 | -7.57 | -4.52 | -23.2 | 26.62% | 4914 | Kenney RPG Audio |
| `max_ammo` | world/max_ammo.ogg | 1.06 | -10.86 | -7.85 | -19.9 | 7.86% | 2554 | Kenney Digital Audio |
| `menu` | music/menu.ogg | 17.50 | -8.53 | -8.53 | -24.0 | 0.00% | 509 | VCSL pipe organ + tubular bells + OGA wind |
| `music_game_over` | music/music_game_over.ogg | 15.00 | -13.62 | -13.62 | -24.0 | 0.00% | 398 | VCSL pipe organ + tubular bells |
| `nuke_blast` | guns/nuke_blast.ogg | 5.04 | -7.96 | -4.95 | -14.4 | 0.00% | 202 | ElevenLabs nuke_blast |
| `pap_upgrade` | world/pap_upgrade.ogg | 4.50 | -7.58 | -4.57 | -21.2 | 22.38% | 4505 | ElevenLabs pap_upgrade |
| `perk_burp` | voices/perk_burp_1.ogg | 0.69 | -10.78 | -7.63 | -19.0 | 0.51% | 2205 | OGA 80 CC0 creature SFX |
| `perk_burp` | voices/perk_burp_2.ogg | 0.90 | -9.55 | -6.45 | -19.0 | 1.78% | 2908 | OGA 80 CC0 creature SFX |
| `perk_burp` | voices/perk_burp_3.ogg | 0.79 | -10.79 | -7.75 | -18.9 | 0.35% | 1892 | OGA 80 CC0 creature SFX |
| `perk_drink` | foley/perk_drink_1.ogg | 0.61 | -7.45 | -4.40 | -21.0 | 17.74% | 4209 | OGA 80 CC0 creature SFX |
| `perk_drink` | foley/perk_drink_2.ogg | 0.40 | -7.06 | -4.02 | -21.1 | 3.12% | 3428 | OGA 80 CC0 creature SFX |
| `perk_jingle_doubletap` | world/perk_jingle_doubletap.ogg | 4.20 | -12.31 | -9.30 | -19.8 | 0.05% | 1894 | ElevenLabs jingle (processed through a cheap speaker) |
| `perk_jingle_juggernog` | world/perk_jingle_juggernog.ogg | 4.20 | -13.45 | -10.42 | -19.7 | 0.04% | 1351 | ElevenLabs jingle (processed through a cheap speaker) |
| `perk_jingle_quickrevive` | world/perk_jingle_quickrevive.ogg | 4.20 | -12.45 | -9.44 | -19.8 | 0.00% | 1218 | ElevenLabs jingle (processed through a cheap speaker) |
| `perk_jingle_speedcola` | world/perk_jingle_speedcola.ogg | 4.20 | -11.23 | -8.22 | -19.8 | 0.01% | 1065 | ElevenLabs jingle (processed through a cheap speaker) |
| `player_down` | voices/player_down_1.ogg | 2.33 | -8.16 | -5.12 | -18.9 | 0.31% | 2007 | ElevenLabs player down take |
| `player_down` | voices/player_down_2.ogg | 2.96 | -6.62 | -3.61 | -18.9 | 1.15% | 1592 | ElevenLabs player down take |
| `player_hurt` | voices/player_hurt_1.ogg | 0.68 | -9.16 | -6.15 | -19.0 | 2.64% | 2897 | ElevenLabs player pain takes |
| `player_hurt` | voices/player_hurt_2.ogg | 0.91 | -7.39 | -4.36 | -18.8 | 0.71% | 2118 | ElevenLabs player pain takes |
| `player_hurt` | voices/player_hurt_3.ogg | 0.36 | -8.60 | -5.55 | -19.1 | 0.46% | 1937 | ElevenLabs player pain takes |
| `player_hurt` | voices/player_hurt_4.ogg | 0.39 | -8.70 | -5.64 | -19.0 | 0.76% | 2062 | ElevenLabs player pain takes |
| `power_on` | world/power_on.ogg | 5.00 | -12.04 | -8.99 | -19.9 | 0.02% | 4354 | ElevenLabs power_on |
| `powerup_blink` | ui/powerup_blink.ogg | 0.40 | -13.20 | -10.19 | -22.9 | 0.00% | 864 | Kenney Digital Audio |
| `powerup_grab` | world/powerup_grab_1.ogg | 0.36 | -16.59 | -13.57 | -19.9 | 0.00% | 626 | ElevenLabs powerup_grab |
| `powerup_grab` | world/powerup_grab_2.ogg | 0.41 | -16.30 | -13.29 | -20.1 | 0.00% | 1261 | ElevenLabs powerup_grab |
| `powerup_loop` | world/powerup_loop.ogg | 2.00 | -17.54 | -14.53 | -25.9 | 0.00% | 433 | Kenney Sci-Fi Sounds |
| `powerup_spawn` | world/powerup_spawn_1.ogg | 0.46 | -12.95 | -9.95 | -19.9 | 21.64% | 5372 | ElevenLabs powerup_spawn |
| `powerup_spawn` | world/powerup_spawn_2.ogg | 0.49 | -12.02 | -8.99 | -19.9 | 28.43% | 6458 | ElevenLabs powerup_spawn |
| `pump_back` | handling/pump_back_1.ogg | 0.09 | -13.90 | -10.47 | -23.5 | 11.41% | 5053 | OGA shotgun cock |
| `pump_back` | handling/pump_back_2.ogg | 0.22 | -10.11 | -7.10 | -23.2 | 19.22% | 4873 | OGA shotgun cock |
| `pump_forward` | handling/pump_forward_1.ogg | 0.12 | -14.25 | -11.24 | -23.4 | 12.98% | 5077 | OGA shotgun cock |
| `pump_forward` | handling/pump_forward_2.ogg | 0.12 | -10.31 | -7.20 | -23.4 | 30.30% | 5147 | OGA shotgun cock |
| `purchase` | world/purchase.ogg | 0.84 | -6.78 | -2.27 | -20.1 | 36.66% | 7178 | Kenney RPG Audio + Interface Sounds |
| `purchase_deny` | ui/purchase_deny.ogg | 0.20 | -10.57 | -6.34 | -23.2 | 10.21% | 4971 | Kenney Interface Sounds |
| `radio_blip` | ui/radio_blip_1.ogg | 0.01 | -14.22 | -11.14 | -22.3 | 1.20% | 3115 | Kenney Interface Sounds |
| `radio_blip` | ui/radio_blip_2.ogg | 0.04 | -10.57 | -7.47 | -26.1 | 1.42% | 4054 | Kenney Interface Sounds |
| `radio_static` | ui/radio_static.ogg | 1.60 | -15.81 | -12.79 | -22.9 | 0.19% | 2138 | generated noise bed |
| `raygun_impact` | guns/raygun_impact_1.ogg | 0.95 | -5.00 | -1.84 | -14.0 | 2.06% | 2948 | ElevenLabs raygun_impact |
| `raygun_impact` | guns/raygun_impact_2.ogg | 0.49 | -7.16 | -4.09 | -14.1 | 5.05% | 4169 | ElevenLabs raygun_impact |
| `reload_break_close` | handling/reload_break_close_1.ogg | 0.50 | -6.45 | -2.88 | -23.4 | 24.34% | 4701 | OGA equipment clicks |
| `reload_break_close` | handling/reload_break_close_2.ogg | 0.50 | -7.15 | -4.05 | -21.1 | 17.96% | 4227 | OGA equipment clicks |
| `reload_break_open` | handling/reload_break_open_1.ogg | 0.12 | -10.50 | -6.82 | -23.3 | 2.78% | 3395 | OGA equipment clicks |
| `reload_break_open` | handling/reload_break_open_2.ogg | 0.28 | -7.44 | -4.21 | -23.4 | 16.65% | 4874 | OGA equipment clicks |
| `reload_lmg_belt` | handling/reload_lmg_belt_1.ogg | 0.29 | -7.82 | -4.82 | -23.3 | 36.24% | 5379 | Kenney RPG Audio |
| `reload_lmg_belt` | handling/reload_lmg_belt_2.ogg | 0.52 | -6.29 | -3.15 | -23.3 | 46.00% ⚠ | 6752 | Kenney RPG Audio |
| `reload_lmg_belt` | handling/reload_lmg_belt_3.ogg | 0.29 | -7.82 | -4.82 | -23.3 | 36.24% | 5379 | Kenney RPG Audio |
| `reload_lmg_in` | handling/reload_lmg_in_1.ogg | 0.34 | -8.57 | -5.43 | -23.3 | 13.95% | 4671 | OGA gun reload sounds |
| `reload_lmg_in` | handling/reload_lmg_in_2.ogg | 0.16 | -8.07 | -5.06 | -23.3 | 1.27% | 2649 | OGA gun reload sounds |
| `reload_lmg_out` | handling/reload_lmg_out_1.ogg | 0.43 | -7.41 | -4.37 | -23.1 | 0.92% | 2662 | OGA gun reload sounds |
| `reload_lmg_out` | handling/reload_lmg_out_2.ogg | 0.09 | -9.87 | -6.79 | -23.1 | 7.46% | 4168 | OGA gun reload sounds |
| `reload_pistol_in` | handling/reload_pistol_in_1.ogg | 0.45 | -7.60 | -4.00 | -23.1 | 31.79% | 6127 | OGA handgun reload |
| `reload_pistol_in` | handling/reload_pistol_in_2.ogg | 0.12 | -10.65 | -7.62 | -24.2 | 21.43% | 4412 | OGA handgun reload |
| `reload_pistol_out` | handling/reload_pistol_out_1.ogg | 0.37 | -5.91 | -2.70 | -23.0 | 11.76% | 5175 | OGA handgun reload |
| `reload_pistol_out` | handling/reload_pistol_out_2.ogg | 0.09 | -9.97 | -6.94 | -23.4 | 22.86% | 4609 | OGA handgun reload |
| `reload_raygun_in` | handling/reload_raygun_in_1.ogg | 0.23 | -8.09 | -5.00 | -23.3 | 24.40% | 4540 | Kenney RPG Audio |
| `reload_raygun_in` | handling/reload_raygun_in_2.ogg | 0.23 | -8.09 | -5.00 | -23.3 | 24.40% | 4540 | Kenney RPG Audio |
| `reload_raygun_out` | handling/reload_raygun_out_1.ogg | 0.37 | -6.63 | -3.54 | -23.2 | 19.95% | 5365 | Kenney RPG Audio |
| `reload_raygun_out` | handling/reload_raygun_out_2.ogg | 0.37 | -6.63 | -3.54 | -23.2 | 19.95% | 5365 | Kenney RPG Audio |
| `reload_revolver_close` | handling/reload_revolver_close_1.ogg | 0.50 | -6.30 | -3.27 | -21.1 | 14.38% | 4417 | OGA equipment clicks |
| `reload_revolver_close` | handling/reload_revolver_close_2.ogg | 0.50 | -6.04 | -2.48 | -21.4 | 9.12% | 4301 | OGA equipment clicks |
| `reload_revolver_eject` | handling/reload_revolver_eject_1.ogg | 0.18 | -9.84 | -6.82 | -23.2 | 27.06% | 5586 | OGA shotgun reload |
| `reload_revolver_eject` | handling/reload_revolver_eject_2.ogg | 0.21 | -8.23 | -4.58 | -23.3 | 73.16% ⚠ | 6621 | OGA shotgun reload |
| `reload_revolver_open` | handling/reload_revolver_open_1.ogg | 0.46 | -7.36 | -4.30 | -22.9 | 28.72% | 4804 | OGA equipment clicks |
| `reload_revolver_open` | handling/reload_revolver_open_2.ogg | 0.26 | -7.26 | -4.21 | -23.4 | 38.83% | 5449 | OGA equipment clicks |
| `reload_rifle_in` | handling/reload_rifle_in_1.ogg | 0.08 | -10.42 | -7.38 | -23.3 | 8.73% | 4408 | OGA gun reload sounds |
| `reload_rifle_in` | handling/reload_rifle_in_2.ogg | 0.30 | -8.44 | -5.24 | -23.3 | 18.65% | 5056 | OGA gun reload sounds |
| `reload_rifle_out` | handling/reload_rifle_out_1.ogg | 0.41 | -7.93 | -4.92 | -22.9 | 1.13% | 2893 | OGA gun reload sounds |
| `reload_rifle_out` | handling/reload_rifle_out_2.ogg | 0.13 | -8.58 | -5.54 | -23.1 | 1.93% | 3017 | OGA gun reload sounds |
| `reload_shotgun_shell` | handling/reload_shotgun_shell_1.ogg | 0.12 | -14.81 | -11.36 | -23.8 | 17.84% | 5851 | OGA shotgun reload |
| `reload_shotgun_shell` | handling/reload_shotgun_shell_2.ogg | 0.11 | -9.58 | -6.39 | -23.3 | 32.67% | 5041 | OGA shotgun reload |
| `reload_shotgun_shell` | handling/reload_shotgun_shell_3.ogg | 0.26 | -8.20 | -4.70 | -23.1 | 36.04% | 5875 | OGA shotgun reload |
| `reload_smg_in` | handling/reload_smg_in_1.ogg | 0.26 | -7.95 | -4.82 | -23.3 | 24.51% | 5699 | OGA gun reload sounds |
| `reload_smg_in` | handling/reload_smg_in_2.ogg | 0.07 | -10.71 | -7.61 | -23.1 | 9.72% | 5021 | OGA gun reload sounds |
| `reload_smg_out` | handling/reload_smg_out_1.ogg | 0.12 | -8.24 | -5.23 | -23.1 | 3.01% | 3432 | OGA gun reload sounds |
| `reload_smg_out` | handling/reload_smg_out_2.ogg | 0.37 | -7.32 | -4.26 | -23.3 | 1.88% | 3276 | OGA gun reload sounds |
| `round_bed_layer_choir` | world/round_bed_layer_choir.ogg | 11.50 | -19.46 | -19.46 | -26.2 | 0.00% | 395 | VCSL pipe organ + tubular bells + OGA wind |
| `round_bed_layer_pulse` | world/round_bed_layer_pulse.ogg | 9.50 | -16.78 | -16.78 | -25.8 | 0.00% | 293 | VCSL pipe organ + tubular bells + OGA wind |
| `round_bed_loop` | world/round_bed_loop.ogg | 13.50 | -12.69 | -12.68 | -26.1 | 0.00% | 411 | VCSL pipe organ + tubular bells + OGA wind |
| `round_end` | stingers/round_end.ogg | 6.37 | -8.27 | -8.27 | -22.0 | 0.00% | 577 | ElevenLabs sting + VCSL organ/bell/gong/timpani |
| `round_start` | stingers/round_start.ogg | 5.34 | -8.82 | -8.82 | -21.6 | 0.00% | 253 | ElevenLabs sting + VCSL organ/bell/gong/timpani |
| `shell_drop` | handling/shell_drop_1.ogg | 0.29 | -7.76 | -4.75 | -26.3 | 65.52% ⚠ | 5620 | OGA 100 CC0 metal & wood SFX |
| `shell_drop` | handling/shell_drop_2.ogg | 0.09 | -15.47 | -12.28 | -26.3 | 26.18% | 5079 | OGA 100 CC0 metal & wood SFX |
| `shell_drop` | handling/shell_drop_3.ogg | 0.24 | -11.48 | -8.02 | -26.2 | 19.74% | 4637 | OGA 100 CC0 metal & wood SFX |
| `shell_drop` | handling/shell_drop_4.ogg | 0.08 | -18.11 | -15.11 | -26.3 | 19.57% | 5344 | OGA 100 CC0 metal & wood SFX |
| `shell_drop` | handling/shell_drop_5.ogg | 0.24 | -12.93 | -9.89 | -26.2 | 24.80% | 5297 | OGA 100 CC0 metal & wood SFX |
| `shell_drop_shotgun` | handling/shell_drop_shotgun_1.ogg | 0.38 | -11.58 | -8.53 | -26.3 | 22.45% | 4013 | OGA 100 CC0 metal & wood SFX |
| `shell_drop_shotgun` | handling/shell_drop_shotgun_2.ogg | 0.12 | -16.17 | -13.15 | -26.2 | 13.76% | 3455 | OGA 100 CC0 metal & wood SFX |
| `shell_drop_shotgun` | handling/shell_drop_shotgun_3.ogg | 0.41 | -12.90 | -9.88 | -26.1 | 33.88% | 4270 | OGA 100 CC0 metal & wood SFX |
| `shell_drop_shotgun` | handling/shell_drop_shotgun_4.ogg | 0.41 | -13.08 | -9.81 | -26.1 | 39.16% | 4282 | OGA 100 CC0 metal & wood SFX |
| `slide_release` | handling/slide_release_1.ogg | 0.09 | -10.89 | -7.82 | -23.0 | 19.74% | 4480 | OGA handgun reload |
| `slide_release` | handling/slide_release_2.ogg | 0.29 | -6.28 | -3.21 | -23.1 | 36.11% | 6417 | OGA handgun reload |
| `sprint_breath` | voices/sprint_breath_1.ogg | 0.39 | -8.44 | -5.43 | -19.0 | 0.02% | 1283 | ElevenLabs player effort takes |
| `sprint_breath` | voices/sprint_breath_2.ogg | 0.25 | -6.84 | -3.83 | -19.4 | 0.82% | 2392 | ElevenLabs player effort takes |
| `sprint_breath` | voices/sprint_breath_3.ogg | 0.44 | -7.39 | -4.37 | -18.9 | 0.08% | 1735 | ElevenLabs player effort takes |
| `ui_back` | ui/ui_back_1.ogg | 0.06 | -7.96 | -4.92 | -23.1 | 4.99% | 4036 | Kenney Interface Sounds |
| `ui_back` | ui/ui_back_2.ogg | 0.09 | -8.20 | -5.19 | -22.9 | 0.23% | 1824 | Kenney Interface Sounds |
| `ui_click` | ui/ui_click_1.ogg | 0.09 | -7.62 | -4.52 | -23.1 | 0.19% | 3303 | Kenney Interface Sounds |
| `ui_click` | ui/ui_click_2.ogg | 0.01 | -15.68 | -12.66 | -22.2 | 0.23% | 2323 | Kenney Interface Sounds |
| `ui_hover` | ui/ui_hover_1.ogg | 0.04 | -10.19 | -7.19 | -22.9 | 23.58% | 5477 | Kenney Interface Sounds |
| `ui_hover` | ui/ui_hover_2.ogg | 0.01 | -14.62 | -11.60 | -22.6 | 30.41% | 5794 | Kenney Interface Sounds |
| `vox_carpenter` | voices/vox_carpenter.ogg | 1.29 | -6.32 | -3.30 | -15.9 | 0.00% | 1239 | ElevenLabs text-to-speech (processed PA) |
| `vox_double_points` | voices/vox_double_points.ogg | 1.43 | -5.83 | -2.81 | -15.9 | 0.00% | 1046 | ElevenLabs text-to-speech (processed PA) |
| `vox_fire_sale` | voices/vox_fire_sale.ogg | 1.44 | -5.85 | -2.84 | -15.8 | 0.01% | 1243 | ElevenLabs text-to-speech (processed PA) |
| `vox_insta_kill` | voices/vox_insta_kill.ogg | 1.44 | -6.24 | -3.22 | -15.9 | 0.01% | 1373 | ElevenLabs text-to-speech (processed PA) |
| `vox_max_ammo` | voices/vox_max_ammo.ogg | 1.58 | -6.47 | -3.44 | -15.8 | 0.00% | 1217 | ElevenLabs text-to-speech (processed PA) |
| `vox_nuke` | voices/vox_nuke.ogg | 1.32 | -6.12 | -3.10 | -15.9 | 0.00% | 952 | ElevenLabs text-to-speech (processed PA) |
| `weapon_lower` | handling/weapon_lower_1.ogg | 0.43 | -7.63 | -4.59 | -22.9 | 0.54% | 1943 | Kenney RPG Audio |
| `weapon_lower` | handling/weapon_lower_2.ogg | 0.41 | -8.58 | -5.57 | -23.1 | 4.21% | 3375 | Kenney RPG Audio |
| `weapon_lower` | handling/weapon_lower_3.ogg | 0.45 | -7.96 | -4.88 | -23.2 | 26.13% | 6210 | Kenney RPG Audio |
| `weapon_raise` | handling/weapon_raise_1.ogg | 0.43 | -8.09 | -5.06 | -23.1 | 0.57% | 2007 | Kenney RPG Audio |
| `weapon_raise` | handling/weapon_raise_2.ogg | 0.45 | -8.42 | -5.11 | -23.2 | 42.28% | 5445 | Kenney RPG Audio |
| `weapon_raise` | handling/weapon_raise_3.ogg | 0.45 | -8.05 | -5.04 | -23.1 | 1.18% | 2367 | Kenney RPG Audio |
| `weapon_switch` | handling/weapon_switch_1.ogg | 0.50 | -7.87 | -4.86 | -23.1 | 1.21% | 2370 | Kenney RPG Audio |
| `weapon_switch` | handling/weapon_switch_2.ogg | 0.49 | -8.34 | -5.30 | -23.1 | 0.66% | 2072 | Kenney RPG Audio |
| `weapon_switch` | handling/weapon_switch_3.ogg | 0.50 | -7.64 | -4.51 | -22.8 | 22.77% | 5788 | Kenney RPG Audio |
| `zombie_attack` | voices/zombie_attack_1.ogg | 1.16 | -8.41 | -5.40 | -19.1 | 7.70% | 3617 | ElevenLabs zombie attack takes |
| `zombie_attack` | voices/zombie_attack_2.ogg | 0.63 | -9.05 | -6.03 | -19.0 | 5.86% | 3181 | ElevenLabs zombie attack takes |
| `zombie_attack` | voices/zombie_attack_3.ogg | 1.11 | -9.43 | -6.41 | -18.9 | 0.60% | 2419 | ElevenLabs zombie attack takes |
| `zombie_attack` | voices/zombie_attack_4.ogg | 1.09 | -9.38 | -6.36 | -19.0 | 0.13% | 2073 | ElevenLabs zombie attack takes |
| `zombie_attack` | voices/zombie_attack_5.ogg | 0.87 | -9.79 | -6.78 | -18.9 | 0.60% | 2496 | ElevenLabs zombie attack takes |
| `zombie_attack` | voices/zombie_attack_6.ogg | 0.77 | -6.99 | -3.98 | -19.0 | 0.81% | 2361 | ElevenLabs zombie attack takes |
| `zombie_attack` | voices/zombie_attack_7.ogg | 0.35 | -7.32 | -4.31 | -19.2 | 0.06% | 1337 | ElevenLabs zombie attack takes |
| `zombie_attack` | voices/zombie_attack_8.ogg | 0.26 | -8.14 | -5.12 | -19.0 | 0.08% | 1215 | ElevenLabs zombie attack takes |
| `zombie_bodyfall` | impacts/zombie_bodyfall_1.ogg | 0.66 | -7.82 | -4.81 | -20.0 | 0.00% | 74 | Kenney Impact Sounds |
| `zombie_bodyfall` | impacts/zombie_bodyfall_2.ogg | 0.71 | -7.76 | -4.75 | -20.0 | 0.00% | 69 | Kenney Impact Sounds |
| `zombie_bodyfall` | impacts/zombie_bodyfall_3.ogg | 0.71 | -7.83 | -4.82 | -19.9 | 0.00% | 68 | Kenney Impact Sounds |
| `zombie_death` | voices/zombie_death_1.ogg | 2.66 | -9.72 | -6.67 | -18.9 | 0.15% | 1893 | ElevenLabs zombie death takes |
| `zombie_death` | voices/zombie_death_2.ogg | 1.44 | -6.46 | -3.45 | -18.9 | 0.21% | 2544 | ElevenLabs zombie death takes |
| `zombie_death` | voices/zombie_death_3.ogg | 2.53 | -6.43 | -3.42 | -18.9 | 0.55% | 2176 | ElevenLabs zombie death takes |
| `zombie_death` | voices/zombie_death_4.ogg | 1.35 | -7.63 | -4.58 | -19.0 | 1.75% | 2805 | ElevenLabs zombie death takes |
| `zombie_death` | voices/zombie_death_5.ogg | 2.80 | -6.66 | -3.64 | -18.9 | 0.11% | 1687 | ElevenLabs zombie death takes |
| `zombie_death` | voices/zombie_death_6.ogg | 1.72 | -6.56 | -3.53 | -19.0 | 1.25% | 2726 | ElevenLabs zombie death takes |
| `zombie_death` | voices/zombie_death_7.ogg | 2.80 | -6.85 | -3.83 | -19.0 | 0.53% | 2335 | ElevenLabs zombie death takes |
| `zombie_death` | voices/zombie_death_8.ogg | 2.22 | -6.60 | -3.57 | -18.9 | 1.77% | 2823 | ElevenLabs zombie death takes |
| `zombie_footstep` | foley/zombie_footstep_1.ogg | 0.13 | -7.63 | -4.62 | -27.0 | 0.00% | 920 | Kenney Impact Sounds + OGA Different Steps |
| `zombie_footstep` | foley/zombie_footstep_2.ogg | 0.13 | -7.18 | -4.17 | -27.0 | 0.03% | 1585 | Kenney Impact Sounds + OGA Different Steps |
| `zombie_footstep` | foley/zombie_footstep_3.ogg | 0.16 | -7.31 | -4.30 | -27.6 | 0.02% | 1493 | Kenney Impact Sounds + OGA Different Steps |
| `zombie_footstep` | foley/zombie_footstep_4.ogg | 0.14 | -7.30 | -4.29 | -27.0 | 0.00% | 979 | Kenney Impact Sounds + OGA Different Steps |
| `zombie_footstep` | foley/zombie_footstep_5.ogg | 0.14 | -7.17 | -4.15 | -26.9 | 0.00% | 933 | Kenney Impact Sounds + OGA Different Steps |
| `zombie_footstep` | foley/zombie_footstep_6.ogg | 0.26 | -6.83 | -3.82 | -26.9 | 0.82% | 2564 | Kenney Impact Sounds + OGA Different Steps |
| `zombie_gib` | impacts/zombie_gib_1.ogg | 0.25 | -6.37 | -3.26 | -21.5 | 1.29% | 2481 | OGA 100 CC0 SFX |
| `zombie_gib` | impacts/zombie_gib_2.ogg | 0.24 | -7.06 | -4.04 | -20.1 | 0.32% | 2037 | OGA 100 CC0 SFX |
| `zombie_gib` | impacts/zombie_gib_3.ogg | 0.41 | -7.63 | -4.60 | -20.1 | 3.19% | 2645 | OGA 100 CC0 SFX |
| `zombie_groan` | voices/zombie_groan_1.ogg | 2.69 | -7.72 | -4.68 | -19.0 | 3.65% | 2105 | ElevenLabs zombie groan / crawler / pain takes |
| `zombie_groan` | voices/zombie_groan_2.ogg | 3.00 | -7.22 | -4.21 | -19.1 | 2.92% | 2440 | ElevenLabs zombie groan / crawler / pain takes |
| `zombie_groan` | voices/zombie_groan_3.ogg | 2.28 | -7.80 | -4.79 | -19.0 | 0.00% | 713 | ElevenLabs zombie groan / crawler / pain takes |
| `zombie_groan` | voices/zombie_groan_4.ogg | 1.55 | -7.24 | -4.22 | -19.0 | 0.02% | 1136 | ElevenLabs zombie groan / crawler / pain takes |
| `zombie_groan` | voices/zombie_groan_5.ogg | 2.17 | -11.49 | -8.48 | -18.9 | 0.00% | 431 | ElevenLabs zombie groan / crawler / pain takes |
| `zombie_groan` | voices/zombie_groan_6.ogg | 1.45 | -6.75 | -3.74 | -19.0 | 0.16% | 1333 | ElevenLabs zombie groan / crawler / pain takes |
| `zombie_groan` | voices/zombie_groan_7.ogg | 1.23 | -8.28 | -5.24 | -19.0 | 0.50% | 1516 | ElevenLabs zombie groan / crawler / pain takes |
| `zombie_groan` | voices/zombie_groan_8.ogg | 2.98 | -6.39 | -3.37 | -18.9 | 1.25% | 2157 | ElevenLabs zombie groan / crawler / pain takes |
| `zombie_groan` | voices/zombie_groan_9.ogg | 0.98 | -6.62 | -3.57 | -19.0 | 0.15% | 1449 | ElevenLabs zombie groan / crawler / pain takes |
| `zombie_groan` | voices/zombie_groan_10.ogg | 2.53 | -8.13 | -5.12 | -18.9 | 0.17% | 1552 | ElevenLabs zombie groan / crawler / pain takes |
| `zombie_groan` | voices/zombie_groan_11.ogg | 1.82 | -10.28 | -7.24 | -18.9 | 0.30% | 2026 | ElevenLabs zombie groan / crawler / pain takes |
| `zombie_groan` | voices/zombie_groan_12.ogg | 1.52 | -8.67 | -5.64 | -19.0 | 0.60% | 2268 | ElevenLabs zombie groan / crawler / pain takes |
| `zombie_rise_dirt` | voices/zombie_rise_dirt_1.ogg | 1.28 | -9.51 | -6.47 | -19.0 | 7.14% | 3320 | ElevenLabs zombie rise takes |
| `zombie_rise_dirt` | voices/zombie_rise_dirt_2.ogg | 3.00 | -9.78 | -6.76 | -19.0 | 0.01% | 1309 | ElevenLabs zombie rise takes |
| `zombie_rise_dirt` | voices/zombie_rise_dirt_3.ogg | 1.21 | -8.77 | -5.74 | -19.0 | 6.35% | 3244 | ElevenLabs zombie rise takes |
| `zombie_rise_dirt` | voices/zombie_rise_dirt_4.ogg | 3.00 | -9.57 | -6.54 | -19.0 | 0.01% | 1177 | ElevenLabs zombie rise takes |
| `zombie_scream` | voices/zombie_scream_1.ogg | 2.60 | -10.15 | -7.13 | -18.8 | 0.05% | 1728 | ElevenLabs sprinter scream takes |
| `zombie_scream` | voices/zombie_scream_2.ogg | 2.01 | -10.86 | -7.85 | -18.9 | 0.02% | 1864 | ElevenLabs sprinter scream takes |
| `zombie_scream` | voices/zombie_scream_3.ogg | 1.69 | -9.74 | -6.72 | -18.9 | 0.01% | 1595 | ElevenLabs sprinter scream takes |
| `zombie_scream` | voices/zombie_scream_4.ogg | 1.47 | -9.86 | -6.82 | -18.8 | 0.01% | 1499 | ElevenLabs sprinter scream takes |
| `zombie_scream` | voices/zombie_scream_5.ogg | 2.56 | -10.92 | -7.91 | -18.8 | 0.01% | 1227 | ElevenLabs sprinter scream takes |
| `zombie_scream` | voices/zombie_scream_6.ogg | 1.92 | -8.62 | -5.61 | -18.9 | 0.01% | 1139 | ElevenLabs sprinter scream takes |
| `zombie_scream` | voices/zombie_scream_7.ogg | 1.82 | -7.30 | -4.29 | -18.9 | 0.09% | 1780 | ElevenLabs sprinter scream takes |
| `zombie_scream` | voices/zombie_scream_8.ogg | 1.49 | -8.03 | -5.01 | -18.9 | 0.03% | 1383 | ElevenLabs sprinter scream takes |
