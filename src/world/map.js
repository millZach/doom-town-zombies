import * as THREE from 'three';
import { Collision } from './collision.js';
import { nodeName } from '../core/assets.js';
import { applyAerialPerspective } from './sky.js';

const _s = new THREE.Vector3();
const _v = new THREE.Vector3();

const INTERIOR_ZONES = new Set(['yellow', 'green', 'bunker', 'yellowup', 'greenup']);

// Active point-light budget per quality level. The *count* of lights in the scene has to
// stay constant while playing (three.js re-compiles every material when it changes), so the
// rig keeps a fixed pool per category and re-targets it to the nearest emitters.
// (the totals stay under the 18 point lights the old fixed rig used, so this is a net win)
const LIGHT_TIERS = {
  high: { lamps: 5, fires: 4, fills: 6, shadowLamp: 512, shadowFire: 512 },
  medium: { lamps: 4, fires: 3, fills: 5, shadowLamp: 512, shadowFire: 0 },
  low: { lamps: 3, fires: 2, fills: 3, shadowLamp: 0, shadowFire: 0 },
};

const lerp = (a, b, t) => a + (b - a) * t;
const smooth01 = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));

/**
 * A site's share of the pool. Two sites (the bunker cage lamp, the biggest fire) also own a
 * dedicated shadow-casting light; `site.own` is how much of the site that light is currently
 * carrying (0 far away, 1 up close). The pooled copy takes the rest, so the site is lit
 * exactly once at any distance — otherwise both burn at full intensity on the same spot and
 * the shadowless copy fills in the very shadows the dedicated light exists to cast.
 */
function siteGain(s) {
  return s.gain * (1 - (s.own || 0));
}

// --- flicker profiles (module level so no closure is allocated per frame) ---
function lampFlicker(t, s) {
  return Math.sin(t * 13 + s.seed) * Math.sin(t * 7.3 + s.seed * 2) > 0.82 ? 0.15 : 1;
}
function fireFlicker(t, s) {
  // two beating sines + a slow breath: a fire never sits still, and this is what makes the
  // flicker travel across the geometry it lights (environment.md #12)
  const f = 0.72 + 0.2 * Math.sin(t * 17 + s.seed) * Math.sin(t * 9.1 + s.seed * 2)
    + 0.12 * Math.sin(t * 3.3 + s.seed * 0.7) + 0.07 * Math.sin(t * 41.7 + s.seed * 3);
  return Math.max(0.25, f);
}

/**
 * A fixed-size pool of non-shadowing point lights shared by many emitter "sites".
 * Each update the nearest N sites own the lights; hand-overs cross-fade so nothing pops.
 */
class LightPool {
  constructor(scene, count) {
    this.scene = scene;
    this.sites = [];
    this.lights = [];
    this._acc = 10;
    this.setCount(count);
  }

  setCount(n) {
    n = Math.max(0, n | 0);
    while (this.lights.length < n) {
      const l = new THREE.PointLight(0xffffff, 0, 10, 2);
      l.castShadow = false;
      l.userData.site = null;
      l.userData.fade = 0;
      this.scene.add(l);
      this.lights.push(l);
    }
    while (this.lights.length > n) {
      const l = this.lights.pop();
      this.scene.remove(l);
    }
    this._acc = 10;
  }

  /** site: { pos, color, intensity, distance, decay?, flicker?, enabled?, gain? } */
  add(site) {
    site.seed ??= Math.random() * 100;
    site.enabled ??= true;
    site.gain ??= 1;
    site.decay ??= 2;
    site.wanted = false;
    this.sites.push(site);
    return site;
  }

  _assign(camPos) {
    const lights = this.lights;
    if (!lights.length) return;
    const pool = [];
    for (const s of this.sites) {
      s.wanted = false;
      if (!s.enabled || siteGain(s) <= 0.001) continue;
      const d2 = s.pos.distanceToSquared(camPos);
      // a light whose reach cannot touch the camera's neighbourhood never wins a slot
      const reach = s.distance + 18;
      if (d2 > reach * reach) continue;
      s._d2 = d2;
      pool.push(s);
    }
    pool.sort((a, b) => a._d2 - b._d2);
    const n = Math.min(lights.length, pool.length);
    for (let i = 0; i < n; i++) pool[i].wanted = true;

    const held = new Set();
    for (const l of lights) {
      const s = l.userData.site;
      if (!s) continue;
      if (s.wanted) { held.add(s); continue; }
      if (l.userData.fade > 0.02) continue;   // let it finish fading out first
      l.userData.site = null;
      l.intensity = 0;
    }
    for (let i = 0; i < n; i++) {
      const s = pool[i];
      if (held.has(s)) continue;
      const free = lights.find(l => !l.userData.site);
      if (!free) break;
      free.userData.site = s;
      free.userData.fade = 0;
      free.position.copy(s.pos);
      free.color.copy(s.color);
      free.distance = s.distance;
      free.decay = s.decay;
      free.intensity = 0;
      held.add(s);
    }
  }

  update(dt, time, camPos) {
    if (!this.lights.length) return;
    this._acc += dt;
    if (this._acc > 0.18) { this._acc = 0; this._assign(camPos); }
    const k = Math.min(1, dt * 5);
    for (const l of this.lights) {
      const s = l.userData.site;
      const want = s && s.enabled && s.wanted ? 1 : 0;
      l.userData.fade = lerp(l.userData.fade, want, k);
      if (!s) { l.intensity = 0; continue; }
      l.position.copy(s.pos);
      l.color.copy(s.color);
      l.distance = s.distance;
      l.decay = s.decay;
      l.intensity = s.intensity * siteGain(s) * (s.flicker ? s.flicker(time, s) : 1) * l.userData.fade;
    }
  }
}

export class GameMap {
  constructor(root) {
    this.root = root;
    this.collision = new Collision();
    this.markers = new Map();     // name -> { pos, quat, forward, object }
    this.zones = [];              // { id, box }
    this.doors = new Map();       // id -> { visual, open }
    this.lamps = [];
    this.fires = [];
    this.lightMarkers = [];       // MK_LIGHT_* (authored fill rig, optional)
    this.glowMaterials = [];
    this.bulbs = [];
    this._process();
  }

  _process() {
    const root = this.root;
    root.updateMatrixWorld(true);
    const staticCols = [], doorCols = new Map(), barrierCols = new Map();
    const hide = [];
    root.traverse(o => {
      const name = nodeName(o);
      if (name.startsWith('COL_')) {
        hide.push(o);
        const meshes = [];
        o.traverse(c => c.isMesh && meshes.push(c));
        if (name.startsWith('COL_DOOR_')) {
          const id = name.slice(9).split('.')[0];
          if (!doorCols.has(id)) doorCols.set(id, []);
          doorCols.get(id).push(...meshes);
        } else if (name.startsWith('COL_BARRIER_')) {
          const id = name.slice(12).split('.')[0];
          if (!barrierCols.has(id)) barrierCols.set(id, []);
          barrierCols.get(id).push(...meshes);
        } else staticCols.push(...meshes);
        return;
      }
      if (name.startsWith('ZONE_')) {
        hide.push(o);
        const id = name.slice(5).split('.')[0].replace(/\d+$/, '');
        const box = new THREE.Box3().setFromObject(o);
        this.zones.push({ id, box });
        return;
      }
      if (name.startsWith('MK_')) {
        const pos = new THREE.Vector3(), quat = new THREE.Quaternion();
        o.matrixWorld.decompose(pos, quat, _s);
        const forward = new THREE.Vector3(0, 0, 1).applyQuaternion(quat);
        forward.y = 0; forward.normalize();
        this.markers.set(name.split('.')[0], { pos, quat, forward, object: o, extras: { ...o.userData } });
        return;
      }
      if (name.startsWith('DOOR_')) {
        const id = name.slice(5).split('.')[0];
        if (!this.doors.has(id)) this.doors.set(id, { id, visual: o, open: false });
      }
      if (o.isMesh) {
        const mats = Array.isArray(o.material) ? o.material : [o.material];
        for (const m of mats) {
          if (!m) continue;
          const mn = (m.name || '').toLowerCase();
          // glass and chrome are the only things in the map that should read the sunset
          // sky back at the player — everything else stays at the flat 0.55
          if ('envMapIntensity' in m) m.envMapIntensity = /glass|chrome|mirror/.test(mn) ? 1.9 : 0.55;
          if (mn.includes('glow')) {
            // the asset contract splits perk marquees (`*_sign_glow`, modest) from the small
            // bright accents (`*_trim_glow`) — record which is which for the power-on pass
            m.userData.glowKind = mn.includes('trim') ? 'trim' : mn.includes('sign') ? 'sign' : 'other';
            this.glowMaterials.push(m);
          }
          if (m.transparent && m.opacity < 1) m.depthWrite = false;
          if (/^decal_/.test(mn)) {
            // authored grime/oil/scorch quads: never write depth (overlapping decals would punch
            // holes in each other), pull toward the camera to beat the surface they sit on
            m.transparent = true;
            m.depthWrite = false;
            m.alphaTest = 0.01;
            m.polygonOffset = true;
            m.polygonOffsetFactor = -4;
            m.polygonOffsetUnits = -4;
            o.renderOrder = 1;
            o.castShadow = false;
          } else if (/glass/.test(mn) && m.transparent) {
            // panes are thin closed boxes: front faces only, no depth write, drawn after decals
            m.side = THREE.FrontSide;
            m.depthWrite = false;
            o.renderOrder = 2;
            o.castShadow = false;
          }
          // distance haze warms up only toward the sun instead of washing the whole street
          applyAerialPerspective(m);
        }
        if (name.startsWith('BG_')) o.castShadow = false;
      }
    });
    // parents of COL/ZONE are hidden entirely
    for (const o of hide) o.visible = false;
    for (const [id] of doorCols) if (!this.doors.has(id)) this.doors.set(id, { id, visual: null, open: false });

    this.collision.setStatic(staticCols);
    for (const [id, meshes] of doorCols) {
      const e = this.collision.addDynamic(id, 'door', meshes);
      const d = this.doors.get(id);
      d.colBox = e?.box;
    }
    for (const [id, meshes] of barrierCols) this.collision.addDynamic('barrier_' + id, 'barrier', meshes);

    for (const [name, m] of this.markers) {
      if (name.startsWith('MK_LAMP_')) this.lamps.push(m);
      if (name.startsWith('MK_FIRE_')) this.fires.push(m);
      if (name.startsWith('MK_LIGHT_')) this.lightMarkers.push({ name, ...m });
    }
    console.log(`[map] ${staticCols.length} colliders, ${this.zones.length} zone boxes, ${this.markers.size} markers, ${this.doors.size} doors`);
  }

  marker(name) { return this.markers.get(name); }
  markersWithPrefix(prefix) {
    const out = [];
    for (const [name, m] of this.markers) if (name.startsWith(prefix)) out.push({ name, ...m });
    return out.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
  }

  /**
   * Which zone a point is in. Zone boxes are stacked vertically now (a house's ground floor
   * and its upstairs share a footprint), so vertical containment decides first: the box that
   * actually contains p.y wins, then the one whose floor is nearest under the point (you are
   * in the storey you are standing on), then the smallest footprint (interiors beat the street).
   */
  zoneAt(p) {
    let best = null, bestScore = Infinity;
    for (const z of this.zones) {
      const b = z.box;
      if (p.x < b.min.x || p.x > b.max.x || p.z < b.min.z || p.z > b.max.z) continue;
      const dy = p.y < b.min.y ? b.min.y - p.y : p.y > b.max.y ? p.y - b.max.y : 0;
      if (dy > 1) continue;
      const area = (b.max.x - b.min.x) * (b.max.z - b.min.z);
      const score = dy * 1000 + Math.max(0, p.y - b.min.y) * 10 + area * 0.1;
      if (score < bestScore) { bestScore = score; best = z.id; }
    }
    return best;
  }

  /** True when a world position is inside one of the enclosed zones (house or bunker). */
  isIndoors(p) {
    const z = this.zoneAt(p);
    return !!z && INTERIOR_ZONES.has(z);
  }

  // ------------------------------------------------------------------ lighting rig
  /**
   * Builds the whole local-light rig: street lamps, fire lights and the fill/practical
   * rig (bounce, window fills, perk kickers) that stops interiors reading as flat
   * wallpaper (environment.md #11, #12).
   */
  buildLightRig(scene, quality = 'high') {
    if (this.rig) return this.rig;
    const tier = LIGHT_TIERS[quality] || LIGHT_TIERS.high;
    this.quality = quality;
    const rig = this.rig = {
      lamps: new LightPool(scene, tier.lamps),
      fires: new LightPool(scene, tier.fires),
      fills: new LightPool(scene, tier.fills),
    };
    this._buildLamps(scene, tier);
    this._buildFires(scene, tier);
    this._buildFills(scene);
    return rig;
  }

  _buildLamps(scene, tier) {
    this.lampSites = [];
    for (const m of this.lamps.slice(0, 12)) {
      const warm = new THREE.Color().setHSL(0.08 + Math.random() * 0.02, 0.85, 0.62);
      const zone = this.zoneAt(_v.copy(m.pos).setY(m.pos.y - 2)) || '';
      const site = this.rig.lamps.add({
        pos: m.pos.clone(), color: warm.clone(), warm: warm.clone(), intensity: 18, base: 18,
        distance: 16, zone, flicker: Math.random() < 0.35 ? lampFlicker : null,
      });
      // the visible bulb is cheap and always on, even when the light itself has no slot
      const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.07, 12, 8), new THREE.MeshBasicMaterial({ color: warm.clone().multiplyScalar(5) }));
      bulb.position.copy(m.pos);
      bulb.castShadow = bulb.receiveShadow = false;
      scene.add(bulb);
      site.bulb = bulb;
      this.bulbs.push(bulb);
      this.lampSites.push(site);
    }
    // one bunker cage lamp casts (static) shadows so the ceiling trunk and the pillars
    // finally have form — the map is static, so the cube map is baked once and re-used.
    const bunkerSite = this.lampSites.find(s => s.zone === 'bunker');
    if (bunkerSite) {
      const l = new THREE.PointLight(bunkerSite.color.clone(), 0, 18, 2);
      l.position.copy(bunkerSite.pos);
      l.castShadow = !!tier.shadowLamp;
      l.shadow.mapSize.set(tier.shadowLamp || 512, tier.shadowLamp || 512);
      l.shadow.bias = -0.004;
      l.shadow.normalBias = 0.05;
      l.shadow.camera.near = 0.15;
      l.shadow.camera.far = 20;
      l.shadow.autoUpdate = false;
      l.shadow.needsUpdate = true;
      scene.add(l);
      this.shadowLamp = l;
      this.shadowLampSite = bunkerSite;
      bunkerSite.own = 0;   // driven per frame by updateLights(): the pooled copy yields as this fades in
    }
  }

  _buildFires(scene, tier) {
    this.fireSites = [];
    let biggest = null;
    for (const f of this.fires) {
      const scale = f.extras?.scale || 1;
      const site = this.rig.fires.add({
        pos: f.pos.clone().add(new THREE.Vector3(0, 0.55 * scale, 0)),
        color: new THREE.Color(1.0, 0.44, 0.15),
        intensity: 16 * scale, distance: 11 * Math.max(1, scale), flicker: fireFlicker, scale,
      });
      this.fireSites.push(site);
      if (!biggest || scale > biggest.scale) biggest = site;
    }
    // the biggest fire gets a real (static) shadow-casting light so its flicker throws
    // shapes across the fence, the barrel and the ground instead of washing them flat
    if (biggest && tier.shadowFire) {
      const l = new THREE.PointLight(biggest.color.clone(), 0, biggest.distance, 2);
      l.position.copy(biggest.pos);
      l.castShadow = true;
      l.shadow.mapSize.set(tier.shadowFire, tier.shadowFire);
      l.shadow.bias = -0.004;
      l.shadow.normalBias = 0.05;
      l.shadow.camera.near = 0.2;
      l.shadow.camera.far = Math.max(12, biggest.distance);
      l.shadow.autoUpdate = false;
      l.shadow.needsUpdate = true;
      scene.add(l);
      this.shadowFire = l;
      this.shadowFireSite = biggest;
      biggest.own = 0;      // ditto — see siteGain()
    }
  }

  // Authored MK_LIGHT_* markers win; without them the rig is derived from the zone boxes,
  // the window barriers and the perk markers so interiors still get bounce/fill/kickers.
  _buildFills(scene) {
    const fills = this.rig.fills;
    this.fillSites = [];
    const addFill = (pos, color, intensity, distance) => {
      const s = fills.add({ pos: pos.clone(), color: color.clone(), intensity, distance });
      this.fillSites.push(s);
      return s;
    };

    if (this.lightMarkers.length) {
      for (const m of this.lightMarkers) {
        const e = m.extras || {};
        const col = parseColor(e.color) || new THREE.Color(1.0, 0.72, 0.5);
        addFill(m.pos, col, Number(e.intensity) || 3.5, Number(e.range ?? e.distance) || 7);
      }
      return;
    }

    const warmBounce = new THREE.Color(1.0, 0.52, 0.28);
    const skyFill = new THREE.Color(0.42, 0.53, 0.86);
    const kicker = new THREE.Color(0.62, 0.70, 0.95);

    // (a) low warm bounce in every interior room: the light the floor throws back up
    for (const z of this.zones) {
      if (!INTERIOR_ZONES.has(z.id)) continue;
      const b = z.box;
      const sx = b.max.x - b.min.x, sz = b.max.z - b.min.z;
      if (sx < 1.5 || sz < 1.5) continue;
      const bunker = z.id === 'bunker';
      const dist = Math.min(13, Math.max(5, Math.hypot(sx, sz) * 0.55));
      const along = sx >= sz ? 'x' : 'z';
      for (const t of [0.34, 0.66]) {
        const p = new THREE.Vector3(
          along === 'x' ? lerp(b.min.x, b.max.x, t) : (b.min.x + b.max.x) * 0.5, 0,
          along === 'z' ? lerp(b.min.z, b.max.z, t) : (b.min.z + b.max.z) * 0.5);
        p.y = b.min.y + (bunker ? 0.75 : 0.55);
        addFill(p, bunker ? new THREE.Color(0.85, 0.55, 0.42) : warmBounce, bunker ? 2.4 : 3.2, dist);
      }
      // (c) a cool ceiling wash so the bunker trunk/pillars are not one dead tone
      if (bunker) {
        const p = new THREE.Vector3((b.min.x + b.max.x) * 0.5, b.max.y - 0.6, (b.min.z + b.max.z) * 0.5);
        addFill(p, new THREE.Color(0.55, 0.62, 0.8), 2.0, dist);
      }
    }

    // (b) every boarded window is a light source at dusk: a cool sky fill on the inside face
    for (const { pos, forward } of this.markersWithPrefix('MK_BARRIER_')) {
      const inFront = _v.copy(pos).addScaledVector(forward, 0.9);
      const inside = this.isIndoors(inFront) ? 1 : -1;
      const p = pos.clone().addScaledVector(forward, 0.75 * inside);
      p.y += 0.45;
      addFill(p, skyFill, 3.0, 5.0);
      // and a dim warm spill on the outside so the opening reads from the street
      const q = pos.clone().addScaledVector(forward, -0.8 * inside);
      q.y += 0.35;
      addFill(q, new THREE.Color(1.0, 0.6, 0.32), 1.6, 3.6);
    }

    // (d) a kicker above/behind each perk machine and the Pack-a-Punch: separation from the wall
    for (const mk of [...this.markersWithPrefix('MK_PERK_'), ...this.markersWithPrefix('MK_PAP')]) {
      const p = mk.pos.clone().addScaledVector(mk.forward, -0.35);
      p.y += 2.0;
      addFill(p, kicker, 2.2, 3.4);
    }
  }

  setLampPower(on) {
    for (const s of this.lampSites || []) {
      if (s.zone !== 'bunker') continue;
      s.color.copy(on ? s.warm : new THREE.Color(1, 0.12, 0.06));
      s.base = on ? 18 : 5;
      s.intensity = s.base;
      s.bulb?.material.color.copy(s.color).multiplyScalar(on ? 5 : 2);
    }
    if (this.shadowLamp && this.shadowLampSite) {
      this.shadowLamp.color.copy(this.shadowLampSite.color);
      this.shadowLamp.shadow.needsUpdate = true;   // re-bake: the blast door may have opened
    }
  }

  /** Per-frame: pools pick their nearest emitters, bulbs and dedicated lights flicker. */
  updateLights(dt, time, camPos) {
    const rig = this.rig;
    if (!rig) return;
    /*
     * Hand-over first, pools second. Each dedicated shadow-casting light fades in over a 5 m
     * band as the player approaches its site and the pooled copy of that same site fades out
     * by exactly the same amount (`site.own`, read back through siteGain()), so the total
     * light on the spot is constant and neither the brightness nor the shadow pops.
     */
    if (this.shadowLamp && this.shadowLampSite) {
      const s = this.shadowLampSite;
      s.own = this.shadowLamp.castShadow ? smooth01((s.distance + 12 - this.shadowLamp.position.distanceTo(camPos)) / 5) : 0;
    }
    if (this.shadowFire && this.shadowFireSite) {
      const s = this.shadowFireSite;
      s.own = this.shadowFire.castShadow ? smooth01((s.distance + 14 - this.shadowFire.position.distanceTo(camPos)) / 5) : 0;
    }
    rig.lamps.update(dt, time, camPos);
    rig.fires.update(dt, time, camPos);
    rig.fills.update(dt, time, camPos);
    for (const s of this.lampSites || []) {
      if (!s.bulb) continue;
      const f = s.flicker ? s.flicker(time, s) : 1;
      s.bulb.visible = f > 0.5;
    }
    if (this.shadowLamp && this.shadowLampSite) {
      const s = this.shadowLampSite;
      this.shadowLamp.intensity = s.intensity * s.gain * (s.own || 0) * (s.flicker ? s.flicker(time, s) : 1);
    }
    if (this.shadowFire && this.shadowFireSite) {
      const s = this.shadowFireSite;
      this.shadowFire.intensity = s.intensity * s.gain * (s.own || 0) * fireFlicker(time, s);
    }
  }

  setLightQuality(q) {
    const tier = LIGHT_TIERS[q] || LIGHT_TIERS.high;
    this.quality = q;
    if (!this.rig) return;
    this.rig.lamps.setCount(tier.lamps);
    this.rig.fires.setCount(tier.fires);
    this.rig.fills.setCount(tier.fills);
    if (this.shadowLamp) {
      this.shadowLamp.castShadow = !!tier.shadowLamp;
      if (tier.shadowLamp) { this.shadowLamp.shadow.mapSize.set(tier.shadowLamp, tier.shadowLamp); this.shadowLamp.shadow.needsUpdate = true; }
    }
    if (this.shadowFire) {
      this.shadowFire.castShadow = !!tier.shadowFire;
      if (tier.shadowFire) { this.shadowFire.shadow.mapSize.set(tier.shadowFire, tier.shadowFire); this.shadowFire.shadow.needsUpdate = true; }
    }
  }

  // --- legacy entry points (kept so older call sites keep working) ---
  addLamps(scene, quality = 'high') {
    this.buildLightRig(scene, quality);
    return this.rig.lamps.lights;
  }

  updateLamps(t) {
    this.updateLights(1 / 60, t, this._lastCam || (this._lastCam = new THREE.Vector3()));
  }
}

function parseColor(c) {
  if (c == null) return null;
  if (Array.isArray(c) && c.length >= 3) return new THREE.Color(c[0], c[1], c[2]);
  if (typeof c === 'number') return new THREE.Color(c);
  if (typeof c === 'string') { try { return new THREE.Color(c); } catch { return null; } }
  return null;
}
