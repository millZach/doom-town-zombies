import * as THREE from 'three';
import { loadGLB } from '../core/assets.js';
import { POWERUPS, POINTS } from '../config.js';

const ORDER = ['maxammo', 'instakill', 'doublepoints', 'nuke', 'carpenter', 'firesale'];
// how long an instant power-up (max ammo / nuke / carpenter) is acknowledged in the HUD strip
const PULSE_TIME = 5;

function placeholderModel(id) {
  const gold = new THREE.MeshStandardMaterial({ color: 0xd8a640, metalness: 1, roughness: 0.3 });
  const g = new THREE.Group();
  let m;
  switch (id) {
    case 'maxammo': m = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.26, 0.22), gold); break;
    case 'instakill': m = new THREE.Mesh(new THREE.SphereGeometry(0.2, 16, 12), gold); break;
    case 'doublepoints': m = new THREE.Mesh(new THREE.TorusGeometry(0.16, 0.05, 10, 24), gold); break;
    case 'nuke': m = new THREE.Mesh(new THREE.CapsuleGeometry(0.1, 0.3, 4, 12), gold); m.rotation.z = Math.PI / 2; break;
    case 'carpenter': m = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.4, 0.08), gold); break;
    default: m = new THREE.Mesh(new THREE.OctahedronGeometry(0.2), gold);
  }
  g.add(m);
  return g;
}

export class Powerups {
  constructor(game) {
    this.game = game;
    this.active = [];          // on-ground drops
    this.timers = {};          // id -> seconds left (timed power-ups: insta-kill, x2, fire sale)
    // Instant power-ups (max ammo, nuke, carpenter) have no duration, so they never used to
    // reach the HUD at all — their emblems were unreachable code (environment.md #14).  They
    // now get a short acknowledgement slot in the same strip that drains and disappears.
    this.pulses = {};          // id -> seconds left of the HUD acknowledgement
    this.models = {};
    this.bag = [];
    this.dropsThisRound = 0;
    this.killsSinceDrop = 0;
    // ---- drop presentation (review item 15)
    // The old halo was a 3.0-linear sprite at scale 1.3 over a 0.3 m gold prop — ~3.7x the
    // bloom threshold, so the model it was advertising was invisible inside it.  Now:
    // a restrained halo that shows the prop, a ground pool that plants it, and a thin
    // vertical sliver so a drop across the street still reads.
    const radial = (stops, size = 128) => {
      const c = document.createElement('canvas'); c.width = c.height = size;
      const g = c.getContext('2d');
      const gr = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
      for (const [o, col] of stops) gr.addColorStop(o, col);
      g.fillStyle = gr; g.fillRect(0, 0, size, size);
      const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
    };
    const halo = radial([[0, 'rgba(215,255,190,1)'], [0.22, 'rgba(120,255,80,0.55)'], [0.62, 'rgba(60,230,30,0.16)'], [1, 'rgba(40,255,20,0)']]);
    this.glowMat = new THREE.SpriteMaterial({ map: halo, color: new THREE.Color(0.9, 1.7, 0.8), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true });
    this.poolMat = new THREE.MeshBasicMaterial({
      map: radial([[0, 'rgba(180,255,150,0.9)'], [0.35, 'rgba(90,255,60,0.35)'], [1, 'rgba(40,255,20,0)']]),
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, opacity: 0.55, fog: true,
    });
    // a soft vertical sliver: 2.5 m of fading green so the drop is spottable at range
    const slv = document.createElement('canvas'); slv.width = 8; slv.height = 128;
    {
      const g = slv.getContext('2d');
      const gr = g.createLinearGradient(0, 128, 0, 0);
      gr.addColorStop(0, 'rgba(190,255,160,0.85)'); gr.addColorStop(0.35, 'rgba(110,255,70,0.28)'); gr.addColorStop(1, 'rgba(90,255,60,0)');
      g.fillStyle = gr; g.fillRect(0, 0, 8, 128);
      const gx = g.createLinearGradient(0, 0, 8, 0);
      gx.addColorStop(0, 'rgba(0,0,0,1)'); gx.addColorStop(0.5, 'rgba(0,0,0,0)'); gx.addColorStop(1, 'rgba(0,0,0,1)');
      g.globalCompositeOperation = 'destination-out';
      g.fillStyle = gx; g.fillRect(0, 0, 8, 128);
    }
    const slvTex = new THREE.CanvasTexture(slv); slvTex.colorSpace = THREE.SRGBColorSpace;
    this.sliverMat = new THREE.SpriteMaterial({ map: slvTex, color: new THREE.Color(0.55, 1.1, 0.5), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.8 });
  }

  async load() {
    for (const id of ORDER) {
      const g = await loadGLB(`/models/props/pu_${id}.glb`);
      const model = g ? g.scene : placeholderModel(id);
      // the drop has to read as *gold* while sitting inside a green halo: push the
      // sunset env reflection and give the metal a faint self-lit floor so the model
      // never goes to silhouette against its own glow.
      model.traverse(o => {
        if (!o.isMesh) return;
        (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => {
          if (!m || m.userData._puTuned) return;
          m.userData._puTuned = true;
          if (m.envMapIntensity !== undefined) m.envMapIntensity = 1.8;
          if (m.emissive && m.emissive.getHex() === 0x000000) { m.emissive.setHex(0x4a2f06); m.emissiveIntensity = 0.55; }
        });
      });
      this.models[id] = model;
    }
  }

  newRound() { this.dropsThisRound = 0; }

  _next() {
    if (!this.bag.length) {
      this.bag = ORDER.filter(id => id !== 'firesale' || this.game.boxMoved).slice();
      for (let i = this.bag.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [this.bag[i], this.bag[j]] = [this.bag[j], this.bag[i]]; }
    }
    return this.bag.pop();
  }

  onKill(pos, zone) {
    this.killsSinceDrop++;
    if (this.dropsThisRound >= 4 || !zone) return;
    const chance = Math.min(0.08, 0.018 + this.killsSinceDrop * 0.0008);
    if (Math.random() < chance) this.drop(this._next(), pos);
  }

  drop(id, pos) {
    const g = this.game;
    this.dropsThisRound++;
    this.killsSinceDrop = 0;
    const grp = new THREE.Group();
    const model = this.models[id].clone(true);
    model.traverse(o => { if (o.isMesh) { o.castShadow = true; } });
    grp.add(model);
    const glow = new THREE.Sprite(this.glowMat); glow.scale.setScalar(0.85); grp.add(glow);
    // 2.5 m sliver rising from the drop — visible from across the street, invisible up close
    const sliver = new THREE.Sprite(this.sliverMat);
    sliver.scale.set(0.34, 2.5, 1); sliver.center.set(0.5, 0.06); grp.add(sliver);
    const light = new THREE.PointLight(0x66ff44, 6, 4, 2); grp.add(light);
    const ground = g.collision.ground(pos.x, pos.z, pos.y + 1, 4) ?? pos.y;
    grp.position.set(pos.x, ground + 0.7, pos.z);
    // ground pool sits in world space (the group bobs; the pool must not)
    const pool = new THREE.Mesh(new THREE.PlaneGeometry(1.4, 1.4), this.poolMat.clone());
    pool.rotation.x = -Math.PI / 2;
    pool.position.set(pos.x, ground + 0.025, pos.z);
    pool.renderOrder = 2;
    g.scene.add(pool);
    g.scene.add(grp);
    this.active.push({ id, grp, model, glow, sliver, pool, light, t: 0, life: 30 });
    g.audio.playAt('powerup_spawn', grp.position, { volume: 1 });
    const loop = g.audio.loop('powerup_loop', { volume: 0.5, position: grp.position });
    this.active[this.active.length - 1].loop = loop;
  }

  update(dt, time) {
    const g = this.game;
    for (let i = this.active.length - 1; i >= 0; i--) {
      const p = this.active[i];
      p.t += dt;
      p.model.rotation.y += dt * 1.6;
      p.grp.position.y += Math.sin(time * 2.2) * 0.002;
      const left = p.life - p.t;
      const vis = left > 8 ? true : left > 3 ? Math.sin(p.t * 12) > -0.3 : Math.sin(p.t * 26) > 0;
      p.model.visible = p.glow.visible = p.sliver.visible = p.pool.visible = vis;
      // slow shimmer so the gold prop catches the eye without being drowned by the halo
      const shimmer = 0.82 + Math.sin(time * 2.6 + p.grp.position.x) * 0.18;
      p.glow.scale.setScalar(0.85 * shimmer);
      p.pool.material.opacity = 0.5 * shimmer;
      p.light.intensity = vis ? 6 * shimmer : 0;
      const d = Math.hypot(g.player.pos.x - p.grp.position.x, g.player.pos.z - p.grp.position.z);
      const dy = Math.abs(g.player.pos.y + 0.8 - p.grp.position.y);
      if ((d < 1.3 && dy < 1.6 && !g.player.downed) || left <= 0) {
        if (left > 0) this.grab(p.id, p.grp.position.clone());
        g.scene.remove(p.grp);
        g.scene.remove(p.pool);
        p.pool.material.dispose();
        p.loop?.stop(0.1);
        this.active.splice(i, 1);
      }
    }
    // timed effects
    const list = [];
    for (const [id, t] of Object.entries(this.timers)) {
      const nt = t - dt;
      if (nt <= 0) { delete this.timers[id]; this._end(id); }
      else { this.timers[id] = nt; list.push({ id, left: nt, dur: POWERUPS[id]?.duration || 30 }); }
    }
    // instant power-ups get a 5 s acknowledgement slot after the strip's timed entries
    for (const [id, t] of Object.entries(this.pulses)) {
      const nt = t - dt;
      if (nt <= 0) delete this.pulses[id];
      else { this.pulses[id] = nt; list.push({ id, left: nt, dur: PULSE_TIME }); }
    }
    g.hud.setPowerups(list);
    g.instaKill = !!this.timers.instakill;
    g.doublePoints = !!this.timers.doublepoints;
    g.fireSale = !!this.timers.firesale;
  }

  grab(id, pos) {
    const g = this.game;
    const cfg = POWERUPS[id];
    g.audio.play('powerup_grab', { volume: 1 });
    g.audio.play(cfg.sound, { volume: 1 });
    g.audio.announce(cfg.name);
    g.hud.announce(cfg.name);
    g.fx.glowBurst(pos, [0.8, 4, 0.6, 1], 30, 4);
    // timed ones live in the strip for their duration; instant ones get a short slot so the
    // pickup is confirmed on the HUD as well as by the announcer (environment.md #14)
    if (!cfg.duration) this.pulses[id] = PULSE_TIME;
    switch (id) {
      case 'maxammo':
        for (const w of g.weapons.inventory) w.reserve = g.weapons.stats(w).reserve;
        g.weapons.grenades = 4;
        g.weapons._hud();
        break;
      case 'nuke':
        g.renderer.grade.uniforms.uFlash.value = 1;
        g.player.shake(0.8);
        g.zombies.nukeAll();
        setTimeout(() => g.addPoints(POINTS.nuke, true), 1800);
        break;
      case 'carpenter':
        g.carpenter();
        break;
      default:
        if (cfg.duration) this.timers[id] = cfg.duration;
        if (id === 'firesale') g.audio.play('box_music', { volume: 0.5 });
    }
  }

  _end(id) {
    if (id === 'instakill' || id === 'doublepoints') this.game.audio.play('powerup_blink', { volume: 0.6 });
  }

  clear() {
    for (const p of this.active) { this.game.scene.remove(p.grp); this.game.scene.remove(p.pool); p.pool.material.dispose(); p.loop?.stop(0); }
    this.active.length = 0;
    this.timers = {};
    this.pulses = {};
  }
}
