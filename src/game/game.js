import * as THREE from 'three';
import { loadGLB } from '../core/assets.js';
import { createSky, createEnvironment, createLights, updateAerial, SUN_DIR } from '../world/sky.js';
import { GameMap } from '../world/map.js';
import { buildFallbackMap } from '../world/fallbackMap.js';
import { NavGrid } from '../world/nav.js';
import { Player } from '../player/player.js';
import { Viewmodel, papUniforms } from '../player/viewmodel.js';
import { Weapons } from '../player/weapons.js';
import { ZombieManager } from '../ai/zombies.js';
import { Particles } from '../fx/particles.js';
import { Decals } from '../fx/decals.js';
import { Door, WallBuy, PerkMachine, PowerSwitch, Barrier, MysteryBox, PackAPunch } from './interactables.js';
import { Powerups } from './powerups.js';
import { PLAYER, PERKS, POINTS, WEAPONS, zombieHealth, zombiesForRound, spawnDelay, zombieSpeedMix, dogHealth, ZONE_LINKS, ZOMBIE } from '../config.js';

const _v = new THREE.Vector3();
const _fwd = new THREE.Vector3();
const _sun = new THREE.Vector3();

// Per-zone atmosphere. Interiors at dusk are *darker and contrastier* than the street, not
// hazier: the fog thins, cools and loses its warm cast as you step inside (environment.md #25).
const ZONE_MOOD = [
  // street                                   house                                    bunker
  { fog: 0.008, exposure: 1.0, hemi: 0.55, env: 0.60, fogCol: new THREE.Color(0.18, 0.13, 0.12) },
  { fog: 0.003, exposure: 1.08, hemi: 0.36, env: 0.42, fogCol: new THREE.Color(0.11, 0.095, 0.10) },
  { fog: 0.002, exposure: 1.15, hemi: 0.22, env: 0.30, fogCol: new THREE.Color(0.075, 0.075, 0.085) },
];

// The in-round tension bed sits a long way under everything else. `Handle.setVolume` scales
// by the registry gain rather than replacing it, so this level has to be re-applied on every
// call, not just passed once to `loop()`.
const BED_VOL = 0.25;
const BED_DUCK = 0.4;   // how far the bed dips under a stinger (the engine's duck bus skips music)

export class Game {
  constructor(renderer, input, audio, hud) {
    this.renderer = renderer;
    this.scene = renderer.scene;
    this.camera = renderer.camera;
    this.input = input;
    this.audio = audio;
    this.hud = hud;
    this.state = 'menu';
    this.time = 0;
    this.timeScale = 1;
    this.baseFov = 75;
    this.indoorLevel = 0;      // 0 street, 1 house, 2 bunker — drives fog/exposure/god rays
    this.roundBed = null;
    this.bedLevel = BED_VOL;   // where the bed wants to sit right now (round vs intermission)
    this._bedAt = -1;          // level the bed was last ramped to (-1 = never)
    this._bedRetry = 0;
  }

  // ------------------------------------------------------------------ loading
  async load(progress) {
    const r = this.renderer;
    progress(0.05, 'Building sky…');
    this.sky = createSky();
    this.scene.add(this.sky);
    const env = createEnvironment(r.renderer);
    this.scene.environment = env;
    this.scene.environmentIntensity = 0.6;
    r.vmScene.environment = env;
    // The air is cooler and darker than the sky: buildings and the horde silhouette against
    // it instead of merging into the same cream value band (environment.md #2a).
    this.scene.fog = new THREE.FogExp2(ZONE_MOOD[0].fogCol.clone(), ZONE_MOOD[0].fog);
    this.lights = createLights(this.scene, r.quality);
    this.fx = new Particles(this.scene);
    this.fx.lightning = pos => this._lightning(pos);
    this.decals = new Decals(this.scene);

    progress(0.12, 'Loading Doom Town…');
    const gltf = await loadGLB('/models/map_doomtown.glb', e => e.total && progress(0.12 + 0.4 * e.loaded / e.total, 'Loading Doom Town…'));
    const root = gltf ? gltf.scene : buildFallbackMap();
    this.usingFallbackMap = !gltf;
    this.scene.add(root);
    this.map = new GameMap(root);
    this.collision = this.map.collision;
    // street lamps + fire lights + the fill/practical rig (bounce, window fills, kickers)
    this.map.buildLightRig(this.scene, r.quality);
    // one place decides what the quality setting means for the whole light budget
    r.onQualityChange = q => {
      this.lights.setQuality(q);
      this.map.setLightQuality(q);
    };

    progress(0.55, 'Mapping the undead routes…');
    await new Promise(res => setTimeout(res, 0));
    this.nav = new NavGrid(this.collision, this.map.zones);
    this.nav.build();
    // everything reachable from a gameplay marker is real floor; the rest (roofs of cars, crates) is pruned
    const seeds = [];
    for (const [name, mk] of this.map.markers) {
      if (/^MK_(PLAYER_START|SPAWN_GROUND|DOOR|BOX|PERK|PAP|POWER|WALLBUY)/.test(name)) seeds.push(mk.pos.clone().addScaledVector(mk.forward, name.startsWith('MK_WALLBUY') || name.startsWith('MK_POWER') ? 0.8 : 0));
      if (name.startsWith('MK_BARRIER_')) seeds.push(mk.pos.clone().addScaledVector(mk.forward, 1.0));
    }
    this.nav.pruneIslands(seeds);

    progress(0.62, 'Waking the dead…');
    this.zombies = new ZombieManager(this);
    await this.zombies.load();

    progress(0.72, 'Cleaning weapons…');
    this.viewmodel = new Viewmodel(r.vmScene, r.vmCamera);
    await Promise.all([...Object.keys(WEAPONS), 'knife', 'frag', 'drink'].map(id => this.viewmodel.load(id)));

    this.player = new Player(this.camera, this.collision);
    this.weapons = new Weapons(this);
    this.powerups = new Powerups(this);
    await this.powerups.load();

    progress(0.82, 'Stocking the machines…');
    await this._buildInteractables();

    // fires: the lights themselves live in the map's pooled rig (every fire has one, the
    // nearest few are live, the biggest casts shadows) — here we only dress the ground.
    this.fireLights = [];
    this.fireLoops = [];
    this._scorchFires();
    this.muzzleLight = new THREE.PointLight(0xffaa55, 0, 9, 2);
    this.scene.add(this.muzzleLight);
    this.lightningLight = new THREE.PointLight(0xb8d4ff, 0, 40, 1.5);
    this.scene.add(this.lightningLight);
    progress(1, 'Ready');
  }

  // a fire that has burned for weeks leaves a mark: without it the flames sit on clean ground
  _scorchFires() {
    for (const f of this.map.fires) {
      const hit = this.collision.raycast(_v.copy(f.pos).add(new THREE.Vector3(0, 0.6, 0)), new THREE.Vector3(0, -1, 0), 2.5);
      const scale = f.extras?.scale || 1;
      if (hit) this.decals.scorchMark(hit.point, hit.normal, 1.5 * scale + Math.random() * 0.5);
    }
  }

  async _buildInteractables() {
    const m = this.map;
    this.interactables = [];
    this.doors = [];
    for (const [id, data] of m.doors) {
      const mk = m.marker(`MK_DOOR_${id}`) || { pos: data.colBox ? data.colBox.getCenter(new THREE.Vector3()) : new THREE.Vector3(), quat: new THREE.Quaternion(), forward: new THREE.Vector3(0, 0, 1) };
      const d = new Door(this, id, mk, data);
      this.doors.push(d);
      this.interactables.push(d);
    }
    for (const mk of m.markersWithPrefix('MK_WALLBUY_')) {
      const id = mk.name.slice('MK_WALLBUY_'.length);
      if (!WEAPONS[id]) continue;
      const w = new WallBuy(this, id, mk);
      await w.init();
      this.interactables.push(w);
    }
    this.perkMachines = [];
    for (const mk of m.markersWithPrefix('MK_PERK_')) {
      const id = mk.name.slice('MK_PERK_'.length);
      if (!PERKS[id]) continue;
      const p = new PerkMachine(this, id, mk);
      await p.init();
      this.perkMachines.push(p);
      this.interactables.push(p);
    }
    const power = m.marker('MK_POWER');
    if (power) { this.powerSwitch = new PowerSwitch(this, power); await this.powerSwitch.init(); this.interactables.push(this.powerSwitch); }
    const pap = m.marker('MK_PAP');
    if (pap) { this.pap = new PackAPunch(this, pap); await this.pap.init(); this.interactables.push(this.pap); }
    const boxes = m.markersWithPrefix('MK_BOX_');
    if (boxes.length) { this.box = new MysteryBox(this, boxes); await this.box.init(); this.interactables.push(this.box); }
    this.barriers = [];
    for (const mk of m.markersWithPrefix('MK_BARRIER_')) {
      const id = mk.name.slice('MK_BARRIER_'.length);
      const b = new Barrier(this, id, mk, m.marker(`MK_SPAWN_WIN_${id}`));
      await b.init();
      b.zone = m.zoneAt(b.inside) || m.zoneAt(mk.pos);
      this.barriers.push(b);
      this.interactables.push(b);
    }
    this.groundSpawns = m.markersWithPrefix('MK_SPAWN_GROUND_').map(s => ({ ...s, pos: s.pos.clone(), zone: s.name.split('_')[3] }));
    for (const s of this.groundSpawns) this._clearSpawn(s);
  }

  /**
   * A ground spawn must stand in the open: set dressing moved in Blender can end up on top of
   * a marker (a parked car's hull swallowed street_2), and a zombie rising there is sealed in.
   * Nudge such a marker to the nearest spot with headroom and no capsule overlap.
   */
  _clearSpawn(s) {
    const col = this.collision;
    const free = (x, y, z) => {
      if (col.raycast(new THREE.Vector3(x, y + 0.1, z), new THREE.Vector3(0, 1, 0), 2.1, { doors: false, barriers: false })) return false;
      const a = new THREE.Vector3(x, y + 0.75, z), b = new THREE.Vector3(x, y + 1.45, z);
      col.capsule(a, b, 0.45, { doors: false, barriers: false });
      return Math.abs(a.x - x) + Math.abs(a.z - z) < 0.02;
    };
    const { x, y, z } = s.pos;
    if (free(x, y, z)) return;
    for (let r = 0.5; r <= 4; r += 0.5) {
      for (let k = 0; k < 16; k++) {
        const a = k / 16 * Math.PI * 2, px = x + Math.cos(a) * r, pz = z + Math.sin(a) * r;
        const gy = col.ground(px, pz, y + 0.6, 1.2, { doors: false, barriers: false });
        if (gy === null || Math.abs(gy - y) > 0.3 || !free(px, gy, pz)) continue;
        console.info(`[spawn] ${s.name} was blocked; moved ${r.toFixed(1)} m`);
        s.pos.set(px, gy, pz);
        return;
      }
    }
    console.warn(`[spawn] ${s.name} is blocked and has no free spot nearby`);
  }

  // ------------------------------------------------------------------ game flow
  start() {
    const m = this.map;
    this.zombies.clearAll();
    this.powerups.clear();
    this.decals.clear();
    this._scorchFires();
    this.round = 0;
    this.kills = 0; this.headshots = 0; this.downs = 0; this.totalPoints = 0;
    this.power = false;
    this.instaKill = this.doublePoints = this.fireSale = false;
    this.unlocked = new Set(['street']);
    this.soloDowned = false;
    const p = this.player;
    p.perks.clear();
    p.maxHealth = PLAYER.health; p.health = p.maxHealth;
    p.points = PLAYER.startPoints;
    p.downed = false; p.dead = false; p.frozen = false;
    const start = m.marker('MK_PLAYER_START') || { pos: new THREE.Vector3(0, 0, 0), forward: new THREE.Vector3(0, 0, -1) };
    p.spawn(start.pos, start.forward);
    this.hud.setPoints(p.points, true);
    this.hud.setPerks([], {});
    // reset world state
    for (const d of this.doors) {
      if (!d.data.open) continue;
      d.data.open = false;
      d.opening = -1;
      this.collision.setEnabled(d.id, true);
      if (d.data.colBox) this.nav.rebuildRegion(d.data.colBox);
      if (d.data.visual) { d.data.visual.visible = true; d.data.visual.position.y = d.startY ?? d.data.visual.position.y; d.data.visual.rotation.z = 0; }
    }
    for (const b of this.barriers) b.repairAll();
    this.box?.reset();
    for (const pm of this.perkMachines) pm.setPower(!!PERKS[pm.perkId].noPower);
    this.pap?.setPower(false);
    this._setPoweredLamps(false);
    this._setMapGlow(false);
    this.weapons.inventory = [];
    this.weapons.grenades = 2;
    this.weapons.state = 'none';
    this.weapons.give('m1911');
    this.state = 'playing';
    this.timeScale = 1;
    this.roundState = 'pre';
    this.roundTimer = 2.5;
    this.nextDogRound = 5 + Math.floor(Math.random() * 3);
    this.boardPoints = 0;
    this.renderer.grade.uniforms.uDowned.value = 0;
    this.hud.setRound(1, false);
    this.hud.show(true);
    if (!this.ambientHandle) this.ambientHandle = this.audio.loop('ambient_loop', { volume: 0.55 });
    if (!this.fireLoops.length) for (const f of this.map.fires.slice(0, 6)) this.fireLoops.push(this.audio.loop('fire_loop', { volume: 0.5, position: f.pos }));
  }

  /**
   * Test setups for play-testing late rounds (`?test=<id>` on the URL). Applied right after
   * start(): the round counter is parked one below the target so the normal round-start
   * sequence (sting, HUD roll, spawn count, zombie health) runs for the target round.
   */
  applyTest(id) {
    const TESTS = {
      r21: {
        round: 21, points: 50000, perks: ['juggernog', 'speedcola', 'doubletap'],
        weapons: [['raygun', true], ['galil', true]], doors: true, power: true,
      },
    };
    const t = TESTS[id];
    if (!t) return false;
    const p = this.player;
    if (t.doors) for (const d of this.doors) if (!d.data.open) d.open(true);
    if (t.power) this.setPower(true);
    for (const id of t.perks) this.givePerk(id);
    this.weapons.inventory = [];
    this.weapons.index = 0;
    for (const [w, pap] of t.weapons) this.weapons.give(w, pap);   // last one ends up in hand
    this.weapons.grenades = 4;
    this.weapons._hud();
    p.points = t.points;
    this.hud.setPoints(p.points, true);
    this.round = t.round - 1;
    this.hud.setRound(this.round, false);
    // keep hellhound rounds on their usual 4-5 round rhythm from here
    this.nextDogRound = t.round + 2 + Math.floor(Math.random() * 2);
    return true;
  }

  _startRound() {
    this.round++;
    this.boardPoints = 0;
    this.powerups.newRound();
    this.dogRound = this.round === this.nextDogRound;
    if (this.dogRound) {
      this.nextDogRound = this.round + 4 + Math.floor(Math.random() * 2);
      this.toSpawn = Math.min(24, 6 + Math.floor(this.round / 3) * 2);
      this.audio.play('hellround_start', { volume: 1 });
      this.hud.flashMessage('Fetch me their souls!', 3500);
    } else {
      this.toSpawn = zombiesForRound(this.round);
      this.audio.play('round_start', { volume: 1 });
    }
    // low tension bed under the whole round
    this.bedLevel = BED_VOL;
    this._ensureRoundBed(2.5);
    this.audio.duck(0.5, 4);
    this.spawnTimer = 1.5;
    this.roundState = 'active';
    this.hud.setRound(this.round, true);
    if (this.round > 1) { this.weapons.grenades = Math.min(4, this.weapons.grenades + 2); this.weapons._hud(); }
  }

  _endRound() {
    this.roundState = 'intermission';
    this.roundTimer = this.round === 0 ? 2 : 10;
    this.audio.play('round_end', { volume: 1 });
    // the bed breathes out between rounds rather than stopping dead (40 % of its in-round level)
    this.bedLevel = BED_VOL * 0.4;
    this._bedTo(this.bedLevel, 3);
    this.audio.duck(0.5, 6);
    if (this.dogRound && this.lastDogPos) this.powerups.drop('maxammo', this.lastDogPos);
    this.dogRound = false;
  }

  _director(dt) {
    if (this.roundState === 'pre' || this.roundState === 'intermission') {
      this.roundTimer -= dt;
      if (this.roundTimer <= 0) this._startRound();
      return;
    }
    if (this.soloDowned) return;
    const alive = this.zombies.aliveCount;
    if (this.toSpawn > 0) {
      this.spawnTimer -= dt;
      const cap = this.dogRound ? Math.min(8, 2 + Math.floor(this.round / 4)) : ZOMBIE.maxAlive;
      if (this.spawnTimer <= 0 && alive < cap) {
        if (this._spawnOne()) this.toSpawn--;
        this.spawnTimer = this.dogRound ? 1.2 + Math.random() * 1.5 : spawnDelay(this.round);
      }
    } else if (alive === 0) this._endRound();
  }

  _activeZones() {
    const pz = this.player.zone || 'street';
    const set = new Set([pz]);
    for (const z of ZONE_LINKS[pz] || []) if (this.unlocked.has(z)) set.add(z);
    return set;
  }

  _spawnOne() {
    const p = this.player;
    if (this.dogRound) {
      // hellhounds strike down near the player
      for (let tries = 0; tries < 30; tries++) {
        const a = Math.random() * Math.PI * 2, d = 7 + Math.random() * 10;
        const x = p.pos.x + Math.cos(a) * d, z = p.pos.z + Math.sin(a) * d;
        // pick the walkable layer nearest the player's own storey, and only one the flow
        // field can reach — a dog on the floor above/below would never get to the player
        const idx = this.nav.nearestReachable(x, p.pos.y, z, 1.5);
        if (idx < 0) continue;
        const hy = this.nav.height[idx];
        if (Math.abs(hy - p.pos.y) > 3.5) continue;     // never drop one through a ceiling
        const pos = new THREE.Vector3(this.nav.cx(idx), hy, this.nav.cz(idx));
        if (pos.distanceTo(p.pos) < 5) continue;
        const zone = this.map.zoneAt(pos);
        if (!zone || !this.unlocked.has(zone)) continue;
        this.zombies.spawn({ kind: 'dog', pos, health: dogHealth(this.round), mode: 'dog' });
        return true;
      }
      return false;
    }
    const zones = this._activeZones();
    const mix = zombieSpeedMix(this.round);
    const rnd = Math.random();
    const gait = rnd < mix.sprint ? 'sprint' : rnd < mix.sprint + mix.run ? 'run' : 'walk';
    const health = zombieHealth(this.round);
    const barriers = this.barriers.filter(b => zones.has(b.zone) && b.spawn && this.unlocked.has(b.zone));
    const grounds = this.groundSpawns.filter(s => zones.has(s.zone) && this.unlocked.has(s.zone) && s.pos.distanceTo(p.pos) > 6);
    const useBarrier = barriers.length && (Math.random() < 0.55 || !grounds.length);
    if (useBarrier) {
      // weight toward closer windows
      barriers.sort((a, b) => a.pos.distanceTo(p.pos) - b.pos.distanceTo(p.pos));
      const b = barriers[Math.floor(Math.pow(Math.random(), 1.6) * barriers.length)];
      const pos = b.spawn.pos.clone().add(new THREE.Vector3((Math.random() - 0.5) * 1.5, 0, (Math.random() - 0.5) * 1.5));
      this.zombies.spawn({ pos, health, gait, mode: 'barrier', barrier: b });
      return true;
    }
    if (grounds.length) {
      grounds.sort((a, b) => a.pos.distanceTo(p.pos) - b.pos.distanceTo(p.pos));
      const s = grounds[Math.floor(Math.pow(Math.random(), 1.4) * grounds.length)];
      const pos = s.pos.clone().add(new THREE.Vector3((Math.random() - 0.5) * 1.2, 0, (Math.random() - 0.5) * 1.2));
      const yaw = Math.atan2(p.pos.x - pos.x, p.pos.z - pos.z);
      this.zombies.spawn({ pos, health, gait, mode: 'rise', yaw });
      return true;
    }
    return false;
  }

  respawnStuck(z) {
    const zones = this._activeZones();
    let grounds = this.groundSpawns.filter(s => zones.has(s.zone) && this.unlocked.has(s.zone));
    if (!grounds.length) {
      // the player's own area has no ground spawns (upstairs): use the unlocked ones with the
      // shortest walk to the player instead of leaving the zombie wedged where it is
      const p = this.player;
      grounds = this.groundSpawns
        .filter(s => this.unlocked.has(s.zone) && s.pos.distanceTo(p.pos) > 6)
        .map(s => ({ s, d: this.nav.distanceAt(s.pos.x, s.pos.y, s.pos.z) }))
        .filter(e => isFinite(e.d))
        .sort((a, b) => a.d - b.d).slice(0, 3).map(e => e.s);
    }
    if (!grounds.length) return;
    const s = grounds[Math.floor(Math.random() * grounds.length)];
    z.pos.copy(s.pos);
    z.state = 'rise';
    z.t = 0;
    z.riseDur = this.zombies._clipDuration(z, 'rise', 2.2);
    this.zombies._play(z, 'rise', { loop: false, fade: 0, restart: true });
  }

  // ------------------------------------------------------------------ economy
  spend(cost) {
    const p = this.player;
    if (p.points < cost) { this.audio.play('purchase_deny', { volume: 0.8 }); return false; }
    p.points -= cost;
    this.hud.setPoints(p.points);
    this.hud.popPoints(-cost);
    this.audio.play('purchase', { volume: 0.8 });
    return true;
  }

  addPoints(n, noDouble = false) {
    if (!n) return;
    const amt = this.doublePoints && !noDouble ? n * 2 : n;
    this.player.points += amt;
    this.totalPoints += amt;
    this.hud.setPoints(this.player.points);
    this.hud.popPoints(amt);
  }

  onZombieKilled(z, info) {
    this.kills++;
    if (z.kind === 'dog') this.lastDogPos = z.pos.clone();
    if (info.part === 'head' && !info.nuke) this.headshots++;
    if (!info.nuke) {
      const pts = info.knife ? POINTS.killKnife : info.part === 'head' ? POINTS.killHead : info.part === 'neck' ? POINTS.killNeck : POINTS.kill;
      this.addPoints(pts);
      const zone = this.map.zoneAt(z.pos);
      if (!this.dogRound) this.powerups.onKill(z.pos, zone && this.unlocked.has(zone) ? zone : null);
    }
  }

  /** chest points of live, visible enemies for controller aim assist */
  _aimTargets() {
    const out = this._aimBuf || (this._aimBuf = []);
    out.length = 0;
    for (const z of this.zombies.list) {
      if (z.state === 'dead' || z.state === 'dogSpawn' || z.state === 'rise' || !z.holder.visible) continue;
      const pos = z._aimPt || (z._aimPt = new THREE.Vector3());
      pos.set(z.pos.x, z.pos.y + (z.kind === 'dog' ? 0.55 : z.crawler ? 0.35 : 1.25), z.pos.z);
      out.push({ pos });
    }
    return out;
  }

  rumble(strong, weak, ms) { this.gamepad?.rumble(strong, weak, ms); }

  hurtPlayer(dmg, z) {
    const p = this.player;
    if (p.downed || this.state !== 'playing') return;
    this.rumble(0.75, 0.55, 220);
    const died = p.damage(dmg, this.time);
    this.audio.play('player_hurt', { volume: 1 });
    this.damagePulse = 1;
    if (died) this._down();
  }

  _down() {
    const p = this.player;
    this.downs++;
    this.rumble(1, 1, 650);
    this.audio.play('player_down', { volume: 1 });
    if (p.perks.has('quickrevive')) {
      p.downed = true;
      this.soloDowned = true;
      this.downTimer = 10;
      p.perks.clear();
      p.maxHealth = PLAYER.health;
      this.hud.setPerks([], {});
      // last stand pistol
      const w = this.weapons;
      this.savedInventory = { inv: w.inventory.map(x => ({ ...x })), index: w.index };
      const pistol = w.inventory.find(x => WEAPONS[x.id].type === 'pistol' || WEAPONS[x.id].type === 'revolver' || x.id === 'raygun');
      w.inventory = [pistol ? { ...pistol } : { id: 'm1911', pap: false, mag: 8, reserve: 40 }];
      w.index = 0;
      w._switchTo(0, true);
    } else {
      p.downed = true;
      p.dead = true;
      this._gameOver();
    }
  }

  _revive() {
    const p = this.player;
    p.downed = false;
    this.soloDowned = false;
    p.health = p.maxHealth;
    const w = this.weapons;
    if (this.savedInventory) {
      // keep ammo used from the last-stand weapon
      const ls = w.inventory[0];
      w.inventory = this.savedInventory.inv;
      const same = w.inventory.find(x => x.id === ls?.id);
      if (same) { same.mag = ls.mag; same.reserve = ls.reserve; }
      w._switchTo(Math.min(this.savedInventory.index, w.inventory.length - 1), true);
      this.savedInventory = null;
    }
    this.hud.setDowned(false);
  }

  _gameOver() {
    this.state = 'dying';
    this.dyingT = 0;
    this.timeScale = 0.35;
    this.audio.play('game_over', { volume: 1 });
    this.audio.stopMusic?.(1);
    this._stopAmbientBeds(1.5);
  }

  // stops the loops that only make sense while a round is running (game over, quit to menu)
  _stopAmbientBeds(fade = 0.8) {
    this.roundBed?.stop?.(fade);
    this.roundBed = null;
    this._bedAt = -1;
    this.heartbeat?.stop?.(0.4);
    this.heartbeat = null;
  }

  /**
   * `audio.loop()` hands back a truthy do-nothing handle when the buffer has not been
   * rendered yet — and `round_bed_loop` is a music track, which the engine renders in its
   * deferred pass, so round 1 can easily ask for it too early. Storing that handle would
   * silence the bed for the whole run, so only a handle that is actually playing counts;
   * `update()` keeps asking until one is.
   */
  _ensureRoundBed(fade = 2.5) {
    const cur = this.roundBed;
    if (cur && cur.isPlaying) { this._bedTo(this.bedLevel, fade); return cur; }
    const h = this.audio.loop?.('round_bed_loop', { volume: this.bedLevel });
    this.roundBed = h && h.isPlaying ? h : null;
    // setVolume() multiplies by the registry gain rather than replacing it, so the level has
    // to be given here too — passing it to loop() alone is not enough
    if (this.roundBed) { this._bedAt = -1; this._bedTo(this.bedLevel, fade); }
    return this.roundBed;
  }

  _bedTo(v, fade) {
    const prev = this._bedAt;
    if (prev >= 0 && Math.abs(v - prev) < 0.004) return;
    this._bedAt = v;
    this.roundBed?.setVolume?.(v, fade);
  }

  /**
   * Per-frame bed upkeep: retry a bed that could not start, and ride the duck.
   *
   * The bed lives on the music bus, and `audio._buildGraph` deliberately wires that bus past
   * `duckGain` ("world bus gets ducked under stingers; ui + music do not"), so `audio.duck()`
   * cannot touch it. Instead the bed *follows* whatever the engine is currently ducking the
   * world by — which covers the AUTO_DUCK stingers (powerups, insta-kill, hellround) as well
   * as the explicit ducks at round start/end, without a second set of timers to keep in sync.
   */
  _updateRoundBed(dt) {
    if (this.roundState === 'pre' && !this.roundBed) return;
    if (!this.roundBed || !this.roundBed.isPlaying) {
      this._bedRetry -= dt;
      if (this._bedRetry <= 0) { this._bedRetry = 1; this._ensureRoundBed(2); }
      return;
    }
    const ctx = this.audio.ctx;
    const ducking = ctx && this.audio._duckUntil > ctx.currentTime ? (this.audio._duckAmount || 0) : 0;
    // a full world duck leaves the bed at BED_DUCK of its level — present, not competing
    const want = this.bedLevel * (1 - ducking * (1 - BED_DUCK));
    this._bedTo(want, want < this._bedAt ? 0.25 : 0.9);
  }

  givePerk(id) {
    const p = this.player;
    p.perks.add(id);
    if (id === 'juggernog') { p.maxHealth = PLAYER.juggHealth; p.health = p.maxHealth; }
    const colors = Object.fromEntries(Object.entries(PERKS).map(([k, v]) => [k, v.color]));
    this.hud.setPerks([...p.perks], colors);
    this.weapons._hud();
  }

  openZones(ids) {
    for (const z of ids) this.unlocked.add(z);
  }

  setPower(on) {
    this.power = on;
    for (const pm of this.perkMachines) pm.setPower(on || !!PERKS[pm.perkId].noPower);
    this.pap?.setPower(on);
    this._setMapGlow(on);
    this.audio.play('power_on', { volume: 1 });
    this.hud.flashMessage('Power On', 3000);
    // lights flicker to life
    let n = 0;
    const flick = setInterval(() => { this._setPoweredLamps(n % 2 === 1 || n > 6); if (++n > 7) clearInterval(flick); }, 110);
    this.player.shake(0.3);
  }

  // bunker lamps run on emergency red until the power is on
  _setPoweredLamps(on) {
    this.map.setLampPower(on);
  }

  // Emissives are authored, not clamped to a value four times over the bloom threshold:
  // big marquees stay readable, only the small trim accents are allowed to be hot
  // (environment.md #1 — the bloom half of it).
  _setMapGlow(on) {
    for (const m of this.map.glowMaterials) {
      m.userData.base ??= m.emissiveIntensity || 1;
      const kind = m.userData.glowKind || 'other';
      const lit = kind === 'trim' ? Math.max(2.2, m.userData.base) : Math.min(1.4, Math.max(0.8, m.userData.base));
      m.emissiveIntensity = on ? lit : m.userData.base * 0.15;
    }
  }

  carpenter() {
    for (const b of this.barriers) b.repairAll();
    this.audio.play('board_slam', { volume: 0.8 });
    this.addPoints(POINTS.carpenter, true);
  }

  get boxMoved() { return this.box && this.box.uses > 3; }

  explode(pos, radius, damage, opts = {}) {
    { const d = this.player.pos.distanceTo(pos); if (d < 14) this.rumble(0.9 * (1 - d / 14), 0.6 * (1 - d / 14), 260); }
    if (opts.ray) {
      this.fx.glowBurst(pos, opts.color || [1, 5, 1, 1], 26, 4);
      this.audio.playAt('raygun_impact', pos, { volume: 0.9 });
    } else {
      this.fx.explosion(pos, radius * 0.7);
      this.audio.playAt('explosion', pos, { volume: 1 });
      const gh = this.collision.raycast(_v.copy(pos).add(new THREE.Vector3(0, 0.3, 0)), new THREE.Vector3(0, -1, 0), 2);
      if (gh) this.decals.scorchMark(gh.point, gh.normal, radius * 0.7);
      this.muzzleLight.color.set(0xff8a3a);
      this.muzzleLight.position.copy(pos);
      this.muzzleLight.intensity = 80;
    }
    const d = this.player.pos.distanceTo(pos);
    this.player.shake(Math.max(0, 0.7 - d / 18));
    if (opts.selfDamage && d < radius * 0.6 && !this.player.downed) this.hurtPlayer(opts.selfDamage, null);
    if (opts.ray && d < 1.4 && !this.player.downed) this.hurtPlayer(25, null);
    let hit = false, kill = false;
    for (const z of this.zombies.inRadius(pos, radius)) {
      if (z === opts.exclude) continue;
      const zd = z.pos.distanceTo(pos);
      const dmg = this.instaKill ? 1e9 : damage * (1 - Math.min(1, zd / radius) * 0.6);
      const killed = this.zombies.damage(z, dmg, { part: 'body', point: _v.set(z.pos.x, z.pos.y + 1, z.pos.z).clone(), explosive: true, gib: true, dir: new THREE.Vector3().subVectors(z.pos, pos).normalize() });
      hit = true;
      if (killed) kill = true; else this.addPoints(POINTS.hit);
    }
    if (hit) this.hud.hitmarker(kill);
  }

  flashWorldLight(color, k = 1) {
    this.camera.getWorldDirection(_v);
    this.muzzleLight.color.set(color);
    this.muzzleLight.position.copy(this.camera.position).addScaledVector(_v, 0.9);
    this.muzzleLight.intensity = 14 * k;
  }

  _lightning(pos) {
    const pts = [];
    let p = pos.clone().add(new THREE.Vector3((Math.random() - 0.5) * 6, 40, (Math.random() - 0.5) * 6));
    const segs = 18;
    for (let i = 0; i <= segs; i++) {
      const t = i / segs;
      const q = new THREE.Vector3().lerpVectors(p, pos, t);
      if (i > 0 && i < segs) q.add(new THREE.Vector3((Math.random() - 0.5) * 2.2, 0, (Math.random() - 0.5) * 2.2));
      pts.push(q);
    }
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: new THREE.Color(4, 5, 8), transparent: true, blending: THREE.AdditiveBlending, fog: false });
    const line = new THREE.Line(geo, mat);
    this.scene.add(line);
    this.lightningLight.position.copy(pos).add(new THREE.Vector3(0, 4, 0));
    this.lightningLight.intensity = 400;
    this.renderer.grade.uniforms.uFlash.value = Math.max(this.renderer.grade.uniforms.uFlash.value, 0.25);
    this.renderer.grade.uniforms.uFlashColor.value.setRGB(0.8, 0.85, 1);
    this.fx.glowBurst(pos.clone().add(new THREE.Vector3(0, 0.3, 0)), [3, 3.5, 5, 1], 30, 5);
    this.decals.scorchMark(pos.clone().add(new THREE.Vector3(0, 0.02, 0)), new THREE.Vector3(0, 1, 0), 1.6);
    let n = 0;
    const flick = setInterval(() => { line.visible = !line.visible; if (++n > 6) { clearInterval(flick); this.scene.remove(line); geo.dispose(); mat.dispose(); } }, 45);
  }

  // ------------------------------------------------------------------ per frame
  update(dtReal) {
    const dt = Math.min(0.05, dtReal) * this.timeScale;
    this.time += dt;
    const t = this.time;
    const input = this.input;
    const g = this.renderer.grade.uniforms;
    papUniforms.uPapTime.value = t;
    this.sky.material.uniforms.uTime.value = t;

    if (this.state === 'playing' || this.state === 'dying') this._updatePlaying(dt, input);
    else this._updateMenuCamera(dt);

    // shared world animation
    const center = this.camera.position;
    this.map.updateLights(dt, t, center);
    for (const f of this.map.fires) {
      // far fires are still visible, but they do not need a full-rate spawn
      if (f.pos.distanceToSquared(center) > 3600 && Math.random() > 0.25) continue;
      this.fx.fire(f.pos, f.extras?.scale || 1);
    }
    this._ambientParticles(dt);
    this.muzzleLight.intensity *= Math.max(0, 1 - dt * 30);
    this.lightningLight.intensity *= Math.max(0, 1 - dt * 8);
    g.uFlash.value = Math.max(0, g.uFlash.value - dt * 1.6);
    this.fx.update(dt);
    this.camera.getWorldDirection(_fwd);
    // The sun's 4096 map re-renders the whole 530k-tri level: do it every other frame. The
    // frustum only moves on frames that re-render, so the map never lags its own projection.
    const sun = this.lights.sun;
    sun.shadow.autoUpdate = false;
    this._shadowTick = (this._shadowTick || 0) + 1;
    if (this._shadowTick % 2 === 0 || this.renderer.quality === 'high') {
      this.lights.follow(center, _fwd);
      sun.shadow.needsUpdate = true;
    }
    updateAerial(this.camera);
    this._updateGodRays(dt);
    this._updateHeatHaze();
    if (this.state === 'playing' || this.state === 'dying') this._updateRoundBed(dt);
    else if (this.roundBed) this._stopAmbientBeds(1.2);
    this.audio.setListener?.(this.camera);
  }

  /**
   * Ambient embers/ash belong to the open air: indoors they used to rain through sealed
   * rooms and 2.5 m of concrete (environment.md #24). Embers now come off the fires and
   * drift, and interiors get a slow dust-mote pool instead.
   */
  _ambientParticles(dt) {
    const center = this.camera.position;
    const inside = this.map.isIndoors(center);
    if (!inside) {
      // embers are born at the fires and blow downwind, not spawned in a box around the head
      const fires = this.map.fires;
      if (fires.length && Math.random() < 0.85) {
        const f = fires[(Math.random() * fires.length) | 0];
        if (f.pos.distanceToSquared(center) < 1600) {
          // embersAround() picks its own absolute height band, so it only needs the column
          if (this.fx.emberDrift) this.fx.emberDrift(f.pos, f.extras?.scale || 1);
          else this.fx.embersAround(f.pos, 1.1);
        }
      }
      if (Math.random() < 0.3) this.fx.ash(center, 20);
    } else if (this.fx.dustMotes && Math.random() < 0.5) {
      // Interior motes: tiny, near-static, they read in the window shafts. There is no
      // indoor fallback on purpose — `fx.ash()` spawns at an absolute world y of 2–9 m and
      // ignores the centre it is handed, so indoors it would drop ash through the ceiling
      // (bunker floor sits at about -2.5 m), which is the artifact environment.md #24 is
      // about. Better no motes than ash inside a sealed room.
      this.fx.dustMotes(center, 4);
    }
  }

  /**
   * Feeds the grade pass the screen-space position of the nearest fires so the air above
   * them shivers (environment.md #12b). Cheap: at most four, only when close.
   */
  _updateHeatHaze() {
    const g = this.renderer.grade.uniforms;
    const heat = g.uHeat.value;
    const cam = this.camera;
    const fires = this.map.fires;
    let n = 0;
    if (fires.length && this.renderer.quality !== 'low') {
      // half-height of the view frustum at 1 m, used to turn metres into uv radius
      const halfH = Math.tan(THREE.MathUtils.degToRad(cam.fov) * 0.5);
      for (const f of fires) {
        if (n >= 4) break;
        const scale = f.extras?.scale || 1;
        const d = cam.position.distanceTo(f.pos);
        if (d > 16 || d < 0.4) continue;
        _sun.copy(f.pos).setY(f.pos.y + 0.9 * scale).project(cam);
        if (_sun.z > 1 || Math.abs(_sun.x) > 1.5 || Math.abs(_sun.y) > 1.5) continue;
        const radius = Math.min(0.7, (1.5 * scale / d) / (2 * halfH));
        const strength = (1 - THREE.MathUtils.smoothstep(d, 3.5, 16)) * Math.min(1, scale);
        if (strength < 0.02) continue;
        heat[n].set(_sun.x * 0.5 + 0.5, _sun.y * 0.5 + 0.5, radius, strength);
        n++;
      }
    }
    g.uHeatCount.value = n;
  }

  /**
   * Crepuscular rays through the smog: the grade pass radially accumulates the sky's own sun
   * term, so buildings, poles and the horde occlude it for free (environment.md #26d).
   */
  _updateGodRays(dt) {
    const g = this.renderer.grade.uniforms;
    if (!this.renderer.godRaysAllowed) { g.uGodRays.value = 0; return; }
    const cam = this.camera;
    _sun.copy(cam.position).addScaledVector(SUN_DIR, 400).project(cam);
    const onScreen = _sun.z < 1 && Math.abs(_sun.x) < 1.8 && Math.abs(_sun.y) < 1.8;
    if (onScreen) g.uSunScreen.value.set(_sun.x * 0.5 + 0.5, _sun.y * 0.5 + 0.5);
    const facing = _fwd.dot(SUN_DIR);
    const indoor = Math.min(1, this.indoorLevel);
    const target = onScreen ? 0.42 * THREE.MathUtils.smoothstep(facing, 0.1, 0.65) * (1 - indoor * 0.9) : 0;
    // the 14-tap radial gather is only paid for while the uniform is above the shader's gate,
    // so a fade that asymptotes at ~0 would keep it running for seconds after you look away
    const v = g.uGodRays.value + (target - g.uGodRays.value) * Math.min(1, dt * 2.5);
    g.uGodRays.value = (target <= 0 && v < 0.006) ? 0 : v;
  }

  _updateMenuCamera(dt) {
    // slow cinematic drift down the street toward the sunset
    const t = this.time;
    // the menu is always outdoors: unwind any interior grade left over from the last run
    this.indoorLevel += (0 - this.indoorLevel) * Math.min(1, dt * 2);
    const mood = ZONE_MOOD[0];
    const r = this.renderer.renderer;
    r.toneMappingExposure += (mood.exposure - r.toneMappingExposure) * Math.min(1, dt * 1.2);
    if (this.scene.fog) {
      this.scene.fog.density += (mood.fog - this.scene.fog.density) * Math.min(1, dt * 0.8);
      this.scene.fog.color.lerp(mood.fogCol, Math.min(1, dt * 0.8));
    }
    const start = this.map.marker('MK_PLAYER_START');
    const c = start ? start.pos : new THREE.Vector3();
    const f = start ? start.forward : new THREE.Vector3(0, 0, 1);
    const right = new THREE.Vector3(-f.z, 0, f.x);
    const along = 3 + Math.sin(t * 0.045) * 4;
    this.camera.position.copy(c).addScaledVector(f, along).addScaledVector(right, Math.sin(t * 0.07) * 1.6);
    this.camera.position.y += 1.5 + Math.sin(t * 0.11) * 0.25;
    const look = c.clone().addScaledVector(f, along + 20).addScaledVector(right, Math.sin(t * 0.05) * 3);
    look.y += 1.9;
    this.camera.lookAt(look);
    this.camera.fov = 58;
    if (this.box?.beam) this.box.beam.visible = false;
    this.camera.updateProjectionMatrix();
    this.viewmodel.holder.visible = false;
  }

  _updatePlaying(dt, input) {
    const p = this.player;
    const g = this.renderer.grade.uniforms;
    this.viewmodel.holder.visible = true;
    this.inputLocked = this.state !== 'playing';

    p.frozen = this.state !== 'playing';
    p.update(dt, input, this.time, {
      blockSprint: input.mouse.left && !!this.weapons.currentInst(),
      aimAssist: this.aimAssist || 'on',
      aimTargets: () => this._aimTargets(),
    });
    // controller X: use/buy/rebuild when a prompt is showing, otherwise reload (BO2 default)
    const pad = input.pad;
    if (pad?.active && (pad.usePressed || pad.useDown || this._padF)) {
      const best = this.state === 'playing' && !p.downed ? this._bestInteractable() : null;
      if (best) {
        if (pad.usePressed) input.pressed.add('KeyF');
        if (pad.useDown) { input.keys.add('KeyF'); this._padF = true; }
      } else if (pad.usePressed) input.pressed.add('KeyR');
      if (!pad.useDown && this._padF) { input.keys.delete('KeyF'); this._padF = false; }
    }
    p.zone = this.map.zoneAt(p.pos) || p.zone;
    // footsteps on each bob half-cycle
    const step = Math.floor(p.bobTime / Math.PI);
    if (step !== this._lastStep) {
      this._lastStep = step;
      if (p.onGround && p.moveAmount > 0.2) {
        const wood = p.zone === 'yellow' || p.zone === 'green';
        this.audio.play(wood ? 'footstep_wood' : 'footstep_dirt', { volume: (p.sprinting ? 0.55 : 0.35) * (p.crouch ? 0.5 : 1), rate: 0.92 + Math.random() * 0.16 });
      }
    }

    this.weapons.update(dt, input);

    // FOV: base -> ADS
    const inst = this.weapons.currentInst();
    const adsFov = inst ? this.baseFov * (WEAPONS[inst.id].adsFov / 70) : this.baseFov;
    const targetFov = THREE.MathUtils.lerp(this.baseFov, adsFov, this.viewmodel.ads) + (p.sprinting ? 4 : 0);
    this.camera.fov += (targetFov - this.camera.fov) * Math.min(1, dt * 12);
    this.camera.updateProjectionMatrix();
    this.renderer.vmCamera.fov = 50 - this.viewmodel.ads * 6;
    this.renderer.vmCamera.updateProjectionMatrix();

    this.viewmodel.update(dt, {
      ads: this.weapons.ads, sprint: p.sprinting, move: p.moveAmount, bobTime: p.bobTime,
      mouseDx: input.mouse.dx, mouseDy: input.mouse.dy, landDip: p.landDip,
      empty: inst ? inst.mag === 0 && WEAPONS[inst.id].type === 'pistol' : false,
    }, this.camera, this.collision);

    this.zombies.update(dt, this.time);

    // interaction
    let prompt = '';
    if (this.state === 'playing' && !p.downed) {
      const best = this._bestInteractable();
      if (best) {
        prompt = best.prompt() || '';
        if (best.hold && input.down('KeyF')) best.holdUse?.(dt);
        else if (input.hit('KeyF')) best.use();
      }
    }
    this.hud.setPrompt(prompt);
    for (const it of this.interactables) it.update(dt, this.time);
    this.powerups.update(dt, this.time);
    if (this.state === 'playing') this._director(dt);

    // downed / revive
    if (p.downed && this.soloDowned) {
      this.downTimer -= dt;
      this.hud.setDowned(true, 1 - this.downTimer / 10, 'Quick Revive is bringing you back…');
      if (this.downTimer <= 0) this._revive();
    }
    if (this.state === 'dying') {
      this.dyingT += dt / this.timeScale;
      g.uDowned.value = Math.min(1, this.dyingT / 2);
      if (this.dyingT > 3.2) this.onGameOver?.({ round: this.round, kills: this.kills, headshots: this.headshots, points: this.totalPoints, downs: this.downs });
    }

    // screen fx
    this.damagePulse = Math.max(0, (this.damagePulse || 0) - dt * 2.2);
    g.uDamage.value = this.damagePulse;
    const hp = p.health / p.maxHealth;
    g.uLowHealth.value += ((hp < 0.55 ? (0.55 - hp) / 0.55 : 0) - g.uLowHealth.value) * Math.min(1, dt * 4);
    g.uInstaKill.value += ((this.instaKill ? 1 : 0) - g.uInstaKill.value) * Math.min(1, dt * 3);
    if (this.state === 'playing') g.uDowned.value += ((p.downed ? 0.8 : 0) - g.uDowned.value) * Math.min(1, dt * 3);
    // same NULL_HANDLE trap as the bed: only a handle that is really playing counts, so a
    // loop asked for before its buffer existed gets retried on the next frame
    if (hp < 0.4 && !this.heartbeat) {
      const h = this.audio.loop('heartbeat_loop', { volume: 0.8 });
      this.heartbeat = h && h.isPlaying ? h : null;
    }
    if (hp >= 0.4 && this.heartbeat) { this.heartbeat.stop?.(0.5); this.heartbeat = null; }

    // environment mood per zone (eye adaptation-ish). Indoors is darker and *clearer*, not
    // hazier: the exposure lift is modest now that emissives no longer bloom (env #1, #25).
    const zone = p.zone;
    const indoor = zone === 'bunker' ? 2 : zone === 'yellow' || zone === 'green' ? 1 : 0;
    this.indoorLevel += (indoor - this.indoorLevel) * Math.min(1, dt * 1.5);
    const mood = ZONE_MOOD[indoor];
    const hemiT = mood.hemi * (this.dogRound ? 0.7 : 1);
    this.lights.hemi.intensity += (hemiT - this.lights.hemi.intensity) * Math.min(1, dt * 1.5);
    // the rim keeps working indoors (that is what separates a zombie from the wallpaper)
    // but at reduced strength, and the warm ground bounce is an outdoor effect only
    if (this.lights.rim) this.lights.rim.intensity += ((indoor ? 0.45 : 0.85) - this.lights.rim.intensity) * Math.min(1, dt * 1.5);
    if (this.lights.bounce) this.lights.bounce.intensity += ((indoor ? 0.12 : 0.5) - this.lights.bounce.intensity) * Math.min(1, dt * 1.5);
    const r = this.renderer.renderer;
    r.toneMappingExposure += (mood.exposure - r.toneMappingExposure) * Math.min(1, dt * 1.2);
    // dog rounds thicken the street fog only — the bunker does not fill with mist
    const fogT = mood.fog * (this.dogRound && !indoor ? 2.6 : 1);
    const fog = this.scene.fog;
    fog.density += (fogT - fog.density) * Math.min(1, dt * 0.6);
    fog.color.lerp(mood.fogCol, Math.min(1, dt * 0.8));
    this.scene.environmentIntensity += (mood.env - this.scene.environmentIntensity) * Math.min(1, dt * 1.5);

    this.hud.update(dt, { spread: this.weapons.spread, showCross: this.viewmodel.ads < 0.5 && !p.sprinting });
  }

  _bestInteractable() {
    const p = this.player;
    const eye = this.camera.position;
    this.camera.getWorldDirection(_v);
    let best = null, bestScore = Infinity;
    for (const it of this.interactables) {
      if (!it.enabled) continue;
      const dx = it.pos.x - p.pos.x, dz = it.pos.z - p.pos.z;
      const d = Math.hypot(dx, dz);
      if (d > it.radius || Math.abs(it.pos.y - (p.pos.y + 1)) > 2.2) continue;
      const to = new THREE.Vector3(it.pos.x - eye.x, 0, it.pos.z - eye.z).normalize();
      const look = new THREE.Vector3(_v.x, 0, _v.z).normalize();
      const dot = to.dot(look);
      if (dot < (d > 0.9 ? 0.2 : -0.1)) continue;
      if (!it.prompt()) continue;
      const score = d * (1.6 - dot);
      if (score < bestScore) { bestScore = score; best = it; }
    }
    return best;
  }
}
