import * as THREE from 'three';
import { WEAPONS, PERKS, POINTS, zombieHealth, RELOAD_EVENTS, reloadClassOf } from '../config.js';
import { TracerSystem } from '../fx/tracers.js';

const _v = new THREE.Vector3();
const _v2 = new THREE.Vector3();
const _fwd = new THREE.Vector3();
const _up = new THREE.Vector3();
const _right = new THREE.Vector3();
const DEG = Math.PI / 180;

// fallback family sounds, used only when the engine has no `gun_<id>` recipe
const SOUND = { pistol: 'gun_pistol', rifle: 'gun_rifle', smg: 'gun_smg', shotgun: 'gun_shotgun', lmg: 'gun_lmg', revolver: 'gun_revolver', raygun: 'gun_raygun' };

// how hard each family shoves the camera / viewmodel (per-weapon `kickScale` overrides this)
const KICK = { shotgun: 2.2, revolver: 1.8, lmg: 1.15, rifle: 1.0, smg: 0.85, pistol: 0.9, raygun: 1.2 };

// Pack-a-Punch energy layer: scaled by family, and skipped entirely on the Ray Gun, which has
// plenty of its own.
const PAP_LAYER = { shotgun: 0.5, revolver: 0.5, lmg: 0.45, rifle: 0.42, smg: 0.3, pistol: 0.35, raygun: 0 };

/**
 * Reload foley, keyed by reload class then by the event name in `RELOAD_EVENTS`.
 * [primary, fallback, volume] — `primary` comes from the new sound contract, `fallback` is the
 * pre-existing recipe so nothing goes silent if the audio stream has not landed yet.
 * Nothing here is ever pitch-shifted: Speed Cola shortens the reload, which moves the event times.
 */
const RELOAD_SFX = {
  pistol: {
    mag_out: ['reload_pistol_out', 'reload_mag_out', 0.75],
    mag_in: ['reload_pistol_in', 'reload_mag_in', 0.8],
    slide: ['slide_release', 'reload_bolt', 0.8],
  },
  smg: {
    mag_out: ['reload_smg_out', 'reload_mag_out', 0.75],
    mag_in: ['reload_smg_in', 'reload_mag_in', 0.8],
    bolt: ['bolt_release', 'reload_bolt', 0.8],
  },
  rifle: {
    mag_out: ['reload_rifle_out', 'reload_mag_out', 0.78],
    mag_in: ['reload_rifle_in', 'reload_mag_in', 0.82],
    bolt: ['bolt_pull', 'reload_bolt', 0.8],
  },
  lmg: {
    cover: ['reload_lmg_out', 'reload_mag_out', 0.7],
    mag_out: ['reload_lmg_out', 'reload_mag_out', 0.6],
    belt: ['reload_lmg_belt', 'reload_shell', 0.75],
    mag_in: ['reload_lmg_in', 'reload_mag_in', 0.8],
    cover_close: ['reload_lmg_in', 'reload_mag_in', 0.6],
    bolt: ['bolt_pull', 'reload_bolt', 0.85],
  },
  break: {
    open: ['reload_break_open', 'reload_bolt', 0.8],
    shell: ['reload_shotgun_shell', 'reload_shell', 0.75],
    shell2: ['reload_shotgun_shell', 'reload_shell', 0.75],
    close: ['reload_break_close', 'reload_bolt', 0.85],
  },
  revolver: {
    open: ['reload_revolver_open', 'reload_bolt', 0.75],
    eject: ['reload_revolver_eject', 'reload_shell', 0.8],
    shell: ['reload_revolver_load', 'reload_shell', 0.8],
    close: ['reload_revolver_close', 'reload_bolt', 0.85],
  },
  raygun: {
    mag_out: ['reload_raygun_out', 'reload_mag_out', 0.75],
    mag_in: ['reload_raygun_in', 'reload_mag_in', 0.8],
    charge: ['raygun_charge', 'powerup_spawn', 0.5],
  },
  shotgun: {
    shell: ['reload_shotgun_shell', 'reload_shell', 0.8],
  },
};

function coneDir(fwd, spreadDeg, out) {
  const a = Math.random() * Math.PI * 2;
  const r = Math.sqrt(Math.random()) * Math.tan(spreadDeg * DEG);
  _up.set(0, 1, 0);
  if (Math.abs(fwd.y) > 0.99) _up.set(1, 0, 0);
  _right.crossVectors(fwd, _up).normalize();
  _up.crossVectors(_right, fwd).normalize();
  return out.copy(fwd).addScaledVector(_right, Math.cos(a) * r).addScaledVector(_up, Math.sin(a) * r).normalize();
}

export class Weapons {
  constructor(game) {
    this.game = game;
    this.inventory = [];
    this.index = 0;
    this.grenades = 2;
    this.state = 'none';
    this.t = 0;
    this.cooldown = 0;
    this.queued = 0;
    this.reloadDur = 0;
    this.reloadCommitted = false;
    this.reloadEvents = null;
    this.reloadEventIdx = 0;
    this.reloadClass = 'rifle';
    this.pumpT = -1;
    this.pumpEjected = false;
    this.projectiles = [];
    this.nades = [];
    this.spread = 2;
    this.shotCount = 0;
    this.pending = null;
    this.maxSlots = 2;
    // feel / feedback bookkeeping
    this.sinceFire = 99;       // seconds since the last shot (first-shot accuracy)
    this.heat = 0;             // barrel heat -> sustained-fire smoke
    this.smokeT = 0;
    this.timers = [];          // game-time scheduled callbacks (never wall clock)
    this.breathT = 0;
    this._wasGround = true;
    this._adsWas = false;
    // tracers: a bright head quad + a longer, thinner, dimmer tail quad (see src/fx/tracers.js)
    this.tracers = new TracerSystem();
  }

  // ---------------- audio helpers
  /** First name the audio engine actually has; otherwise the fallback (silent if unknown). */
  _snd(name, fallback) {
    const a = this.game.audio;
    if (!a) return name;
    if (typeof a.has === 'function') return a.has(name) ? name : (fallback || name);
    return name;
  }

  _play(name, fallback, opts) { this.game.audio.play(this._snd(name, fallback), opts); }
  _playAt(name, fallback, pos, opts) { this.game.audio.playAt(this._snd(name, fallback), pos, opts); }

  /** Schedule a callback in *game* time — survives pause, timeScale and weapon switches. */
  _schedule(delay, fn) { this.timers.push({ t: delay, fn }); }
  _clearTimers() { this.timers.length = 0; }

  // ---------------- inventory
  find(id) { return this.inventory.find(w => w.id === id); }
  currentInst() { return this.state === 'none' ? null : this.inventory[this.index] || null; }
  busy() { return ['switch', 'reload', 'knife', 'grenade', 'drink'].includes(this.state); }
  get busyDrinking() { return this.state === 'drink'; }

  stats(inst) {
    const base = WEAPONS[inst.id];
    const s = inst.pap ? { ...base, ...base.pap, pap: base.pap } : { ...base };
    s.displayName = inst.pap ? base.pap.name : base.name;
    const perks = this.game.player.perks;
    if (perks.has('doubletap')) { s.rpm *= 1.33; s.damageMul = 2; } else s.damageMul = 1;
    s.reloadMul = perks.has('speedcola') ? 0.5 : 1;
    return s;
  }

  refill(inst) {
    const s = this.stats(inst);
    inst.reserve = s.reserve;
    if (inst === this.currentInst()) this._hud();
    this.game.audio.play('purchase');
  }

  give(id, pap = false) {
    const g = this.game;
    let inst = this.find(id);
    if (inst) {
      inst.pap = pap || inst.pap;
    } else {
      inst = { id, pap, mag: 0, reserve: 0 };
      if (this.inventory.length < this.maxSlots) this.inventory.push(inst);
      else if (this.inventory.length) this.inventory[this.index] = inst;
      else this.inventory.push(inst);
    }
    const s = this.stats(inst);
    inst.mag = s.mag; inst.reserve = s.reserve;
    g.audio.play('purchase');
    this._switchTo(this.inventory.indexOf(inst), true);
  }

  takeCurrent() {
    const inst = this.currentInst();
    if (!inst) return;
    this.inventory.splice(this.index, 1);
    this.index = 0;
    if (this.inventory.length) this._switchTo(0, false);
    else { this.state = 'none'; this.game.viewmodel.show(null); this._hud(); }
  }

  _switchTo(i, fresh = false) {
    const vm = this.game.viewmodel;
    this.pendingIndex = i;
    this.state = 'switch';
    this.t = 0;
    this.switchPhase = vm.current ? 'lower' : 'raise';
    this.freshRaise = fresh;
    this._clearTimers();
    this.heat = 0;
    this.sinceFire = 99;
    if (this.switchPhase === 'raise') this._swapModel();
    vm.reloadT = -1;
    vm.shellT = -1;
    this.pumpT = -1; vm.pumpT = -1;
    // a fresh pickup has no lower phase, so it must not play the holster sound
    if (this.switchPhase === 'lower') this._play('weapon_lower', 'weapon_switch', { volume: 0.55 });
  }

  _swapModel() {
    this.index = this.pendingIndex;
    const inst = this.inventory[this.index];
    const vm = this.game.viewmodel;
    if (inst) vm.show(inst.id, inst.pap);
    this._play('weapon_raise', 'weapon_switch', { volume: 0.6 });
    this._hud();
  }

  cycle(dir) {
    if (this.inventory.length < 2 || this.state === 'drink' || this.state === 'grenade') return;
    this._switchTo((this.index + dir + this.inventory.length) % this.inventory.length);
  }

  // ---------------- actions
  drink(perkId, done) {
    const g = this.game;
    this.state = 'drink';
    this.t = 0;
    this.onDrink = done;
    g.viewmodel.setOverlay('drink');
    g.viewmodel.drinkT = 0;
    const col = new THREE.Color(PERKS[perkId].color);
    const ov = g.viewmodel.overlay;
    if (ov) ov.root.traverse(o => {
      if (!o.isMesh) return;
      (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => {
        if (!m) return;
        if (m.name.includes('bottle_liquid')) m.color.copy(col).multiplyScalar(0.6);
        if (m.name.includes('bottle_label')) m.color.copy(col);
      });
    });
  }

  startReload() {
    const inst = this.currentInst();
    if (!inst || this.state !== 'ready') return;
    const s = this.stats(inst);
    if (inst.mag >= s.mag || inst.reserve <= 0) return;
    const vm = this.game.viewmodel;
    this.state = 'reload';
    this.t = 0;
    this.reloadCommitted = false;
    const cls = reloadClassOf(s);
    const empty = inst.mag === 0;
    this.reloadClass = cls;
    this.reloadEmpty = empty;
    // legacy kind, still used by anything reading vm.reloadKind
    const kind = cls === 'shotgun' ? 'shell' : cls === 'break' ? 'break' : cls === 'revolver' ? 'revolver'
      : cls === 'lmg' ? 'lmg' : empty ? 'magEmpty' : 'mag';
    this.reloadKind = kind;
    const base = empty && s.reloadEmpty ? s.reloadEmpty : s.reload;
    this.reloadDur = base * s.reloadMul;
    this.reloadEvents = RELOAD_EVENTS[cls] || RELOAD_EVENTS.rifle;
    this.reloadEventIdx = 0;
    if (cls === 'shotgun') { this.shellT = 0; this.reloadDur = 0.35 * s.reloadMul; }
    vm.reloadClass = cls;
    vm.reloadKind = kind;
    vm.reloadEmpty = empty;
    vm.reloadT = 0;
    vm.shellT = cls === 'shotgun' ? 0 : -1;
  }

  /** Fire one normalised reload beat: the foley plus whatever mechanically happens on it. */
  _reloadEvent(name, inst, s) {
    const g = this.game, vm = g.viewmodel;
    const cls = this.reloadClass;
    const tbl = RELOAD_SFX[cls];
    const e = tbl && tbl[name];
    if (e) this._play(e[0], e[1], { volume: e[2] });

    const commitAll = () => {
      if (this.reloadCommitted) return;
      this.reloadCommitted = true;
      const need = s.mag - inst.mag;
      const take = Math.min(need, inst.reserve);
      inst.mag += take; inst.reserve -= take;
      this._hud();
    };
    const commitOne = () => {
      if (inst.mag < s.mag && inst.reserve > 0) { inst.mag++; inst.reserve--; this._hud(); }
      this.reloadCommitted = inst.mag >= s.mag || inst.reserve <= 0;
    };

    switch (name) {
      case 'mag_in': if (cls !== 'lmg') commitAll(); break;
      case 'belt': commitAll(); break;
      case 'shell': cls === 'break' ? commitOne() : commitAll(); break;
      case 'shell2': commitOne(); break;
      case 'eject':
        // hulls / cases leaving the gun
        if (cls === 'break') { vm.ejectShell('shotshell', 1, 0.7); vm.ejectShell('shotshell', 1, 0.55); }
        else if (cls === 'revolver') for (let i = 0; i < Math.min(6, s.mag || 6); i++) vm.ejectShell('brass', s.shellScale ?? 1, 0.35);
        break;
      default: break;
    }
  }

  melee() {
    if (['knife', 'drink', 'grenade'].includes(this.state)) return;
    const g = this.game;
    this.prevState = this.state === 'reload' ? 'ready' : this.state;
    if (this.state === 'reload') g.viewmodel.reloadT = -1;
    this.state = 'knife';
    this.t = 0;
    this.knifeHit = false;
    const hasKnife = g.viewmodel.models.get('knife')?.real;
    if (hasKnife) g.viewmodel.setOverlay('knife');
    g.viewmodel.knifeT = 0;
    g.audio.play('knife_swing', { volume: 0.8 });
    // lunge toward a nearby zombie
    const target = this._meleeTarget(2.6);
    if (target && target.d > 1.1) {
      const p = g.player;
      _v.set(target.z.pos.x - p.pos.x, 0, target.z.pos.z - p.pos.z).normalize();
      p.vel.x += _v.x * 7; p.vel.z += _v.z * 7;
    }
  }

  throwGrenade() {
    if (this.grenades <= 0 || ['knife', 'drink', 'grenade', 'switch'].includes(this.state)) return;
    const g = this.game;
    if (this.state === 'reload') g.viewmodel.reloadT = -1;
    this.state = 'grenade';
    this.t = 0;
    this.thrown = false;
    g.viewmodel.setOverlay(g.viewmodel.models.get('frag')?.real ? 'frag' : null);
    g.viewmodel.throwT = 0;
    g.viewmodel.lower = 0.6;
    g.audio.play('grenade_pin', { volume: 0.8 });
  }

  _meleeTarget(range) {
    const g = this.game, p = g.player;
    g.camera.getWorldDirection(_fwd);
    _fwd.y = 0; _fwd.normalize();
    let best = null;
    for (const z of g.zombies.list) {
      if (z.state === 'dead' || z.state === 'dogSpawn') continue;
      _v.set(z.pos.x - p.pos.x, 0, z.pos.z - p.pos.z);
      const d = _v.length();
      if (d > range || Math.abs(z.pos.y - p.pos.y) > 1.4) continue;
      if (_v.normalize().dot(_fwd) < 0.55 && d > 0.8) continue;
      if (!best || d < best.d) best = { z, d };
    }
    return best;
  }

  // ---------------- per frame
  update(dt, input) {
    const g = this.game, vm = g.viewmodel, p = g.player;
    this.t += dt;
    this.cooldown -= dt;
    this.queued -= dt;
    this.sinceFire += dt;
    const inst = this.currentInst();
    const s = inst ? this.stats(inst) : null;
    const locked = g.inputLocked;

    // game-time timers (pump strokes etc.) — never setTimeout
    if (this.timers.length) {
      for (let i = this.timers.length - 1; i >= 0; i--) {
        const tm = this.timers[i];
        tm.t -= dt;
        if (tm.t <= 0) { this.timers.splice(i, 1); try { tm.fn(); } catch { /* ignore */ } }
      }
    }
    if (p.downed || p.dead) this._clearTimers();

    // hand the shell system the world it falls into (once)
    if (vm.shells && g.scene) vm.shells.attachWorld(g.scene, g.collision, g.audio);
    // tracers live in the world scene and fly on their own clock
    if (g.scene) this.tracers.attach(g.scene);
    this.tracers.update(dt, g.camera);

    // inputs
    if (!locked && !p.downed) {
      if (input.hit('Digit1')) this.index !== 0 && this.inventory[0] && this._switchTo(0);
      if (input.hit('Digit2')) this.index !== 1 && this.inventory[1] && this._switchTo(1);
      if (input.mouse.wheel) this.cycle(input.mouse.wheel > 0 ? 1 : -1);
      if (input.hit('KeyR')) this.startReload();
      if (input.hit('KeyV') || input.hit('KeyE')) this.melee();
      if (input.hit('KeyG')) this.throwGrenade();
      if (input.hit('KeyI') && this.state === 'ready') vm.inspect();
    } else if (!locked && p.downed) {
      if (input.hit('KeyR')) this.startReload();
    }
    if (input.mouse.leftPressed) this.queued = 0.18;

    const ads = !locked && input.mouse.right && !!s && !p.sprinting && this.state === 'ready';
    this.ads = !!ads;
    p.adsFactor = vm.ads;

    // ADS cloth / detent brush
    if (this.ads !== this._adsWas) {
      this._adsWas = this.ads;
      if (s) this._play(this.ads ? 'ads_in' : 'ads_out', null, { volume: 0.35 });
    }

    // player foley that the player object flags for us
    if (p.jumpEvent) { p.jumpEvent = false; this._play('jump_grunt', null, { volume: 0.4, rate: 0.95 + Math.random() * 0.1 }); }
    if (p.landEvent > 0) {
      const hard = p.landEvent > 7;
      this._play(hard ? 'land_hard' : 'land_soft', 'footstep_dirt', { volume: hard ? 0.7 : 0.4, rate: hard ? 0.85 : 1 });
      if (hard) p.shake(0.08);
      p.landEvent = 0;
    }
    // sprint breathing
    if (p.sprinting && !p.downed) {
      this.breathT -= dt;
      if (this.breathT <= 0) { this.breathT = 1.1; this._play('sprint_breath', null, { volume: 0.3, rate: 0.95 + Math.random() * 0.12 }); }
    } else this.breathT = Math.min(this.breathT, 0.35);

    switch (this.state) {
      case 'switch': {
        const lowerDur = 0.22, raiseDur = this.freshRaise ? 0.6 : 0.32;
        if (this.switchPhase === 'lower') {
          vm.lower = Math.min(1, this.t / lowerDur);
          if (this.t >= lowerDur) { this._swapModel(); this.switchPhase = 'raise'; this.t = 0; }
        } else {
          vm.lower = 1 - Math.min(1, this.t / raiseDur);
          if (this.t >= raiseDur) { vm.lower = 0; this.state = 'ready'; }
        }
        break;
      }
      case 'ready': {
        if (!inst) break;
        const auto = s.mode === 'auto';
        const trigger = !locked && (auto ? input.mouse.left : this.queued > 0);
        if (trigger && p.sprinting) { p.sprintLock = 0.25; p.sprinting = false; }
        if (trigger && this.cooldown <= 0 && this.pumpT < 0 && !p.sprinting) {
          if (inst.mag > 0) { this._fire(inst, s); this.queued = 0; }
          else {
            this.queued = 0;
            g.audio.play('dry_fire');
            this.cooldown = 0.25;
            if (inst.reserve > 0) this.startReload();
          }
        }
        // auto reload after the last round of a semi-auto magazine
        if (inst.mag === 0 && inst.reserve > 0 && this.cooldown <= -0.15 && this.state === 'ready') this.startReload();
        break;
      }
      case 'reload': {
        if (!inst) { this.state = 'ready'; break; }
        if (this.reloadClass === 'shotgun') this._shellReload(dt, inst, s, input);
        else {
          vm.reloadT = Math.min(1, this.t / this.reloadDur);
          // normalised event table: with Speed Cola the beats simply arrive sooner
          const ev = this.reloadEvents;
          while (ev && this.reloadEventIdx < ev.length && vm.reloadT >= ev[this.reloadEventIdx][0]) {
            this._reloadEvent(ev[this.reloadEventIdx][1], inst, s);
            this.reloadEventIdx++;
          }
          if (this.t >= this.reloadDur) {
            // safety net if a beat was somehow skipped: use the event that actually commits for
            // this class ('mag_in' is deliberately a no-op on the belt-fed LMG)
            if (!this.reloadCommitted) this._reloadEvent(this.reloadClass === 'lmg' ? 'belt' : 'mag_in', inst, s);
            this.state = 'ready'; vm.reloadT = -1; vm.shellT = -1;
          }
          // firing interrupts a reload only after the ammo is in
          if (this.reloadCommitted && this.queued > 0 && vm.reloadT > 0.8) { this.state = 'ready'; vm.reloadT = -1; }
        }
        break;
      }
      case 'knife': {
        const dur = 0.55;
        vm.knifeT = this.t / dur;
        if (!this.knifeHit && this.t > 0.14) {
          this.knifeHit = true;
          const tgt = this._meleeTarget(1.9);
          if (tgt) {
            const dmg = g.instaKill ? 1e9 : 150;
            const hp = g.zombies.headPosition(tgt.z, new THREE.Vector3()).add(new THREE.Vector3(0, -0.35, 0));
            g.camera.getWorldDirection(_v);
            const killed = g.zombies.damage(tgt.z, dmg, { part: 'body', point: hp, dir: _v.clone(), knife: true });
            if (!killed) g.addPoints(POINTS.hit);
            g.hud.hitmarker(killed, 'body');
            g.audio.playAt('knife_hit', hp, { volume: 1 });
            p.shake(0.15);
          } else {
            // swinging into geometry should not be silent
            g.camera.getWorldDirection(_v);
            const hit = g.collision.raycast(g.camera.position, _v, 1.7, { doors: true, barriers: true });
            if (hit) {
              const surf = this._surfaceAt(hit.point, hit.normal);
              this._playAt('knife_hit_wall', this._snd(`impact_${surf}`, 'bullet_impact_wall'), hit.point, { volume: 0.5, rate: 1.1 });
              g.fx.sparks(hit.point, hit.normal, 3);
              p.shake(0.05);
            }
          }
        }
        if (this.t >= dur) { this.state = inst ? 'ready' : 'none'; vm.knifeT = -1; vm.setOverlay(null); }
        break;
      }
      case 'grenade': {
        const dur = 0.75;
        vm.throwT = this.t / dur;
        if (!this.thrown && this.t > 0.32) { this.thrown = true; this._spawnGrenade(); }
        if (this.t >= dur) { this.state = inst ? 'ready' : 'none'; vm.throwT = -1; vm.setOverlay(null); vm.lower = 0; }
        break;
      }
      case 'drink': {
        const dur = 2.6;
        vm.drinkT = this.t / dur;
        vm.lower = this.t < 0.25 ? this.t / 0.25 : this.t > dur - 0.35 ? (dur - this.t) / 0.35 : 1;
        if (this.t > 1.4 && !this.gulped) { this.gulped = true; g.audio.play('perk_drink', { volume: 0.9 }); }
        if (this.t >= dur) {
          this.gulped = false;
          vm.drinkT = -1; vm.setOverlay(null); vm.lower = 0;
          this.state = inst ? 'ready' : 'none';
          g.audio.play('perk_burp', { volume: 0.7 });
          this.onDrink?.();
          this.onDrink = null;
        }
        break;
      }
    }

    // pump / bolt cycling after a shot
    if (this.pumpT >= 0) {
      const prev = this.pumpT;
      this.pumpT += dt / this.pumpDur;
      vm.pumpT = this.pumpT;
      // the hull leaves the port on the back stroke
      if (!this.pumpEjected && prev < 0.35 && this.pumpT >= 0.35) {
        this.pumpEjected = true;
        vm.ejectShell('shotshell', 1, 0.8);
      }
      if (this.pumpT >= 1) { this.pumpT = -1; vm.pumpT = -1; }
    }

    // barrel heat -> sustained-fire smoke from the muzzle
    this.heat *= Math.max(0, 1 - dt * 0.4);
    this.smokeT -= dt;
    if (this.heat > 8 && this.smokeT <= 0 && s) {
      this.smokeT = 0.25;
      g.camera.getWorldDirection(_fwd);
      g.fx.muzzleSmoke(this.muzzleWorld(_v2), _fwd.multiplyScalar(0.35));
    }

    this._updateProjectiles(dt);
    this._updateGrenades(dt);

    // crosshair spread
    const target = s ? (this.ads ? s.spreadAds : s.spreadHip) * (1 + p.moveAmount * 0.7 + (p.onGround ? 0 : 1.2)) * (p.crouch ? 0.8 : 1) : 2;
    this.spread += (target - this.spread) * Math.min(1, dt * 12);
  }

  _shellReload(dt, inst, s, input) {
    const g = this.game, vm = g.viewmodel;
    const per = Math.max(0.12, s.reload * s.reloadMul);
    this.shellT += dt;
    // ramp the hold pose in rather than snapping to it on the first frame
    vm.reloadT = Math.min(0.5, this.t / 0.3);
    vm.shellT = Math.min(1, this.shellT / per);
    if (this.shellT >= per && inst.mag < s.mag && inst.reserve > 0) {
      this.shellT = 0;
      inst.mag++; inst.reserve--;
      const e = RELOAD_SFX.shotgun.shell;
      this._play(e[0], e[1], { volume: e[2], rate: 0.97 + Math.random() * 0.07 });
      this._hud();
    }
    const done = inst.mag >= s.mag || inst.reserve <= 0;
    if ((done && this.shellT > 0.2) || (this.queued > 0 && inst.mag > 0)) {
      this.state = 'ready';
      vm.reloadT = -1;
      vm.shellT = -1;
      if (s.mode === 'pump') { this.pumpT = 0; this.pumpEjected = true; this.pumpDur = 0.45; this._pumpSounds(0.45); }
    }
  }

  /** Two-stroke pump foley, scheduled in game time off the pump animation. */
  _pumpSounds(dur) {
    this._schedule(dur * 0.12, () => this._play('pump_back', 'reload_bolt', { volume: 0.7, rate: 1 }));
    this._schedule(dur * 0.62, () => this._play('pump_forward', 'reload_bolt', { volume: 0.65, rate: 0.92 }));
  }

  _hud() {
    const inst = this.currentInst();
    const g = this.game;
    if (!inst) { g.hud.setAmmo(null); return; }
    const s = this.stats(inst);
    g.hud.setAmmo({ name: s.displayName, mag: inst.mag, magMax: s.mag, reserve: inst.reserve, pap: inst.pap });
    g.hud.setGrenades(this.grenades);
  }

  muzzleWorld(out) {
    const g = this.game;
    g.viewmodel.muzzleInCamera(_v);
    const ndc = _v.clone().project(g.renderer.vmCamera);
    out.set(ndc.x, ndc.y, 0.5).unproject(g.camera);
    const cam = g.camera.position;
    return out.sub(cam).normalize().multiplyScalar(0.7).add(cam);
  }

  ejectWorld(out) {
    const g = this.game;
    g.viewmodel.ejectInCamera(_v);
    const ndc = _v.clone().project(g.renderer.vmCamera);
    out.set(ndc.x, ndc.y, 0.5).unproject(g.camera);
    const cam = g.camera.position;
    return out.sub(cam).normalize().multiplyScalar(0.55).add(cam);
  }

  /**
   * Best-effort surface tag for impact foley. `collision.raycast` does not return a material yet
   * (see the fix log), so this infers from the zone and the face orientation.
   */
  _surfaceAt(point, normal) {
    const g = this.game;
    const zone = g.map?.zoneAt?.(point) || g.player.zone;
    const flat = normal.y > 0.62;
    // the bunker is poured concrete floor to ceiling, so orientation tells us nothing there
    if (zone === 'bunker') return 'concrete';
    // wooden interiors: the floorboards ring differently from the planking on the walls
    if (zone === 'yellow' || zone === 'green') return 'wood';
    // outside: bare earth underfoot, masonry when you hit a wall
    return flat ? 'dirt' : 'concrete';
  }

  // ---------------- firing
  _fire(inst, s) {
    const g = this.game, p = g.player, vm = g.viewmodel;
    inst.mag--;
    this.shotCount++;
    this.cooldown = 60 / s.rpm;
    const firstShot = this.sinceFire >= 0.4;
    this.sinceFire = 0;
    this.heat += 1;
    if (s.mode === 'pump') {
      this.pumpT = 0;
      this.pumpEjected = false;
      this.pumpDur = Math.max(0.35, 60 / s.rpm * 0.8);
      this._pumpSounds(this.pumpDur);
    }
    this._hud();

    // ---- audio: per-weapon recipe first, family recipe only as a fallback
    g.audio.play(this._snd(`gun_${inst.id}`, SOUND[s.type] || 'gun_rifle'), { volume: 1, rate: 0.97 + Math.random() * 0.06 });
    const papVol = PAP_LAYER[s.type] ?? 0.4;
    if (inst.pap && papVol > 0) g.audio.play('gun_pap_layer', { volume: papVol });

    // ---- recoil: per-weapon pattern, sampled by shot index so bursts are learnable
    const pattern = s.recoilPattern && s.recoilPattern.length ? s.recoilPattern[this.shotCount % s.recoilPattern.length] : [1, 0];
    const heavy = s.kickScale ?? KICK[s.type] ?? 1;
    let flash = s.flash || undefined;
    if (flash && s.type === 'raygun' && inst.pap) flash = { ...flash, color: s.projectileColor ?? flash.color };
    g.rumble?.(0.06 * heavy, 0.22 + 0.12 * heavy, s.mode === 'auto' ? 45 : 80);
    vm.fire({
      strength: this.ads ? 0.6 : 1,
      kickScale: heavy,
      pattern,
      flash,
      ads: vm.ads,
      // the slide/bolt *travel* comes from the weapon def the viewmodel already holds; only the
      // cycle *duration* is worth overriding per shot, and 45 ms is right for every gun we ship.
      cycle: s.mode !== 'break' && s.type !== 'raygun',
    });
    // pattern[1] > 0 walks the muzzle right; addRecoil's yaw is positive-left, hence the sign
    p.addRecoil(
      s.recoil * 0.55 * (pattern[0] ?? 1) * (this.ads ? 0.65 : 1),
      -s.recoil * 0.34 * (pattern[1] ?? 0) * (this.ads ? 0.7 : 1));
    p.shake(0.1 * heavy * (this.ads ? 0.75 : 1));

    // ---- brass out of the port
    if (s.ejectOnFire !== false && s.shellKind && s.shellKind !== 'none') {
      vm.ejectShell(s.shellKind, s.shellScale ?? 1);
      if (Math.random() < 0.25) g.fx.muzzleSmoke(this.ejectWorld(_v2), _up.set(0.15, 0.6, 0).normalize().multiplyScalar(0.3));
    }

    const muzzle = this.muzzleWorld(new THREE.Vector3());
    g.flashWorldLight(s.type === 'raygun' ? (inst.pap ? 0xff3322 : 0x55ff55) : 0xffaa55, s.type === 'raygun' ? 1.5 : 1);
    // flashWorldLight parks the light dead ahead at head height, which throws every shadow the
    // wrong way — put it on the actual muzzle instead.
    if (g.muzzleLight) g.muzzleLight.position.copy(muzzle);
    g.camera.getWorldDirection(_fwd);
    if (s.type !== 'raygun' && Math.random() < 0.35 + Math.min(0.45, this.heat * 0.04)) g.fx.muzzleSmoke(muzzle, _fwd);

    if (s.mode === 'projectile') { this._spawnRay(inst, s, muzzle); return; }

    const origin = g.camera.position.clone();
    const pellets = s.pellets || 1;
    let spread = (this.ads ? s.spreadAds : s.spreadHip) * (1 + p.moveAmount * 0.6 + (p.onGround ? 0 : 1)) * (p.crouch ? 0.8 : 1);
    if (pellets > 1) spread = this.ads ? s.spreadAds : s.spreadHip;
    // first-shot accuracy: the opening round of a burst goes where the sights point
    if (pellets === 1 && this.ads && firstShot) spread = s.spreadAds * 0.25;
    const perZombie = new Map();
    const dir = new THREE.Vector3();
    let impactsPlayed = 0;
    for (let i = 0; i < pellets; i++) {
      coneDir(_fwd, spread, dir);
      const mapHit = g.collision.raycast(origin, dir, 220, { doors: true, barriers: false });
      const maxD = mapHit ? mapHit.distance : 220;
      const zh = g.zombies.raycast(origin, dir, maxD);
      const pen = (s.pen || 0) + 1;
      let endPoint = mapHit ? mapHit.point : origin.clone().addScaledVector(dir, 80);
      for (let k = 0; k < Math.min(pen, zh.length); k++) {
        const h = zh[k];
        const falloff = pellets > 1 ? Math.max(0.25, 1 - Math.max(0, h.dist - 4) / s.range) : (h.dist > s.range ? 0.65 : 1);
        const partMul = h.part === 'head' ? s.headMult : h.part === 'neck' ? Math.max(1.3, s.headMult * 0.6) : h.part === 'limb' ? 0.85 : 1;
        const dmg = s.damage * s.damageMul * falloff * partMul * (k === 0 ? 1 : k === 1 ? 0.75 : 0.5);
        let e = perZombie.get(h.zombie);
        if (!e) { e = { dmg: 0, part: h.part, point: h.point, dir: dir.clone() }; perZombie.set(h.zombie, e); }
        e.dmg += dmg;
        if (h.part === 'head') { e.part = 'head'; e.point = h.point; }
        else if (h.part === 'neck' && e.part !== 'head') e.part = 'neck';
        if (k === 0) endPoint = h.point;
      }
      const reachedWall = zh.length < pen && mapHit;
      if (reachedWall) {
        g.decals.bulletHole(mapHit.point, mapHit.normal);
        if (Math.random() < 0.6) g.fx.sparks(mapHit.point, mapHit.normal, pellets > 1 ? 2 : 6);
        g.fx.dust(mapHit.point, mapHit.normal);
        // always audible — only the *sound* varies, never whether there is one
        if (impactsPlayed < (pellets > 1 ? 2 : 1)) {
          impactsPlayed++;
          const surf = this._surfaceAt(mapHit.point, mapHit.normal);
          this._playAt(`impact_${surf}`, 'bullet_impact_wall', mapHit.point, {
            volume: (pellets > 1 ? 0.42 : 0.55), rate: 0.92 + Math.random() * 0.16,
          });
        }
      }
      if (s.explosive && (zh.length || mapHit)) {
        const at = zh.length ? zh[0].point : mapHit.point;
        g.explode(at, s.explosive.radius, s.explosive.damage * s.damageMul, { weapon: inst.id });
      }
      // tracers: every third round. A short hot head quad plus a long, thin, dim tail quad —
      // genuinely two different sizes, which fx.tracer() (no size argument) cannot express.
      if (s.type !== 'pistol' && s.type !== 'revolver' && (pellets === 1 ? this.shotCount % 3 === 0 : i < 2)) {
        const head = inst.pap ? [3, 1.5, 5, 0.95] : [5, 3.2, 1.6, 0.9];
        const tail = inst.pap ? [1.2, 0.6, 2, 0.4] : [2, 1.3, 0.6, 0.35];
        this.tracers.spawn(muzzle, endPoint, head, tail);
        g.fx.glow(muzzle, 0.13, head, 0.06);
      }
    }
    // apply damage (one hit/kill event per zombie per shot, like the original)
    let anyHit = false, anyKill = false, anyHead = false, fleshPoint = null;
    for (const [z, e] of perZombie) {
      anyHit = true;
      if (e.part === 'head') anyHead = true; else fleshPoint = e.point;
      const dmg = g.instaKill ? 1e9 : e.dmg;
      const killed = g.zombies.damage(z, dmg, { part: e.part, point: e.point, dir: e.dir, weapon: inst.id, incendiary: s.incendiary, gib: s.type === 'shotgun' && z.pos.distanceTo(p.pos) < 4 });
      if (killed) anyKill = true;
      else g.addPoints(POINTS.hit);
    }
    if (anyHit) {
      g.hud.hitmarker(anyKill, anyHead ? 'head' : 'body');
      this._play(anyHead ? 'hitmarker_head' : 'hitmarker', 'hitmarker', { volume: 0.55 });
      if (fleshPoint) g.audio.playAt(this._snd('impact_flesh', 'flesh_hit'), fleshPoint, { volume: 0.55, rate: 0.94 + Math.random() * 0.12 });
    }
  }

  _spawnRay(inst, s, muzzle) {
    const g = this.game;
    g.camera.getWorldDirection(_fwd);
    // aim converges on the crosshair target
    const target = g.collision.raycast(g.camera.position, _fwd, 200) ?.point || g.camera.position.clone().addScaledVector(_fwd, 100);
    const dir = target.clone().sub(muzzle).normalize();
    coneDir(dir, this.ads ? s.spreadAds : s.spreadHip * 0.5, dir);
    const c = new THREE.Color(s.projectileColor);
    this.projectiles.push({ pos: muzzle.clone(), vel: dir.multiplyScalar(s.projectileSpeed), life: 3, s, inst, color: [c.r * 5, c.g * 5, c.b * 5, 1] });
  }

  _updateProjectiles(dt) {
    const g = this.game;
    for (let i = this.projectiles.length - 1; i >= 0; i--) {
      const pr = this.projectiles[i];
      pr.life -= dt;
      const step = pr.vel.length() * dt;
      const dir = pr.vel.clone().normalize();
      const mapHit = g.collision.raycast(pr.pos, dir, step + 0.05, { doors: true, barriers: false });
      const zh = g.zombies.raycast(pr.pos, dir, mapHit ? mapHit.distance : step);
      // trail
      for (let k = 0; k < 3; k++) g.fx.glow(pr.pos.clone().addScaledVector(dir, (k / 3) * step), 0.22, pr.color, 0.12);
      if (zh.length || mapHit || pr.life <= 0) {
        const at = zh.length ? zh[0].point : mapHit ? mapHit.point : pr.pos;
        const s = pr.s;
        if (zh.length) {
          const z = zh[0].zombie;
          const killed = g.zombies.damage(z, g.instaKill ? 1e9 : s.damage * s.damageMul, { part: zh[0].part, point: at, dir, weapon: pr.inst.id, gib: true });
          if (!killed) g.addPoints(POINTS.hit);
          g.hud.hitmarker(killed, zh[0].part);
        }
        g.explode(at, s.splash.radius, s.splash.damage * s.damageMul, { weapon: pr.inst.id, ray: true, color: pr.color, exclude: zh[0]?.zombie });
        this.projectiles.splice(i, 1);
        continue;
      }
      pr.pos.addScaledVector(pr.vel, dt);
    }
  }

  _spawnGrenade() {
    const g = this.game, p = g.player;
    this.grenades--;
    this._hud();
    g.camera.getWorldDirection(_fwd);
    const pos = g.camera.position.clone().addScaledVector(_fwd, 0.5).add(new THREE.Vector3(0, -0.15, 0));
    const vel = _fwd.clone().multiplyScalar(15).add(new THREE.Vector3(0, 3.2, 0)).add(new THREE.Vector3(p.vel.x, 0, p.vel.z));
    let mesh = null;
    const fragModel = g.viewmodel.models.get('frag');
    if (fragModel?.real) { mesh = g.viewmodel.worldModel('frag'); }
    if (!mesh) mesh = new THREE.Mesh(new THREE.SphereGeometry(0.04, 12, 8), new THREE.MeshStandardMaterial({ color: 0x3d4a2a, roughness: 0.6 }));
    mesh.castShadow = true;
    g.scene.add(mesh);
    this.nades.push({ pos, vel, fuse: 2.6, mesh, bounces: 0 });
  }

  _updateGrenades(dt) {
    const g = this.game;
    for (let i = this.nades.length - 1; i >= 0; i--) {
      const n = this.nades[i];
      n.fuse -= dt;
      n.vel.y -= 16 * dt;
      const step = n.vel.length() * dt;
      if (step > 1e-5) {
        const dir = n.vel.clone().normalize();
        const hit = g.collision.raycast(n.pos, dir, step + 0.05, { doors: true, barriers: true });
        if (hit) {
          n.pos.copy(hit.point).addScaledVector(hit.normal, 0.05);
          const vn = n.vel.dot(hit.normal);
          n.vel.addScaledVector(hit.normal, -1.5 * vn).multiplyScalar(0.45);
          if (Math.abs(vn) > 2) g.audio.playAt('grenade_bounce', n.pos, { volume: 0.6 });
          n.bounces++;
        } else n.pos.addScaledVector(n.vel, dt);
      }
      n.mesh.position.copy(n.pos);
      n.mesh.rotation.x += dt * 8; n.mesh.rotation.z += dt * 5;
      if (n.fuse <= 0) {
        g.scene.remove(n.mesh);
        this.nades.splice(i, 1);
        const round = g.round;
        g.explode(n.pos, 5.0, Math.max(400, zombieHealth(round) * 1.3), { grenade: true, selfDamage: 35 });
      }
    }
  }
}
