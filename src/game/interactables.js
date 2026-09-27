import * as THREE from 'three';
import { loadGLB, findNode, nodeName } from '../core/assets.js';
import { WEAPONS, PERKS, DOORS, BOX_COST, PAP_COST, PAP_AMMO_COST, FIRE_SALE_BOX_COST, POINTS } from '../config.js';

const clamp01 = t => Math.max(0, Math.min(1, t));
const ease = t => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
const _v = new THREE.Vector3();

async function prop(name) {
  const g = await loadGLB(`/models/props/${name}.glb`);
  return g ? g.scene.clone(true) : null;
}

function placeAt(obj, marker) {
  obj.position.copy(marker.pos);
  obj.quaternion.copy(marker.quat);
  return obj;
}

// ------------------------------------------------------------------ emissive budget
//
// The perk/PaP GLBs split their lightbox into two materials:
//   <perkId>_sign_glow   the printed marquee.  It has to stay *readable*, so it is
//                        authored just above the bloom threshold and no higher —
//                        a backlit panel, not a lamp.
//   <perkId>_trim_glow   the small accent lamps / edge tubes.  Those are allowed to
//                        be hot, because they are a few dozen pixels each.
// Older GLBs only carry a generic `glow` material; those are treated as a sign so a
// missing split can never blow the room out.  The previous `Math.max(3, …)` clamp is
// gone: 3.0 linear is ~4x the bloom threshold over an entire lightbox.
const GLOW_BANDS = { sign: [0.85, 1.4], trim: [2.4, 4.0], mark: [0.35, 0.9] };

function glowKind(name) {
  const n = (name || '').toLowerCase();
  if (!n.includes('glow')) return null;
  if (n.includes('glow_q') || n.includes('q_glow') || n.includes('question')) return 'mark';
  if (n.includes('trim') || n.includes('accent') || n.includes('lamp') || n.includes('indicator') || n.includes('bulb')) return 'trim';
  return 'sign';
}

// -> [{ mat, kind }] with mat.userData.on / .off filled in.  Deduped: one material
// shared by several meshes must only be driven once.
function glowMats(obj) {
  const out = [], seen = new Set();
  obj.traverse(o => {
    if (!o.isMesh) return;
    (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => {
      if (!m || seen.has(m)) return;
      const kind = glowKind(m.name);
      if (!kind) return;
      seen.add(m);
      const [lo, hi] = GLOW_BANDS[kind];
      const authored = m.emissiveIntensity || 1;
      m.userData.on = Math.min(hi, Math.max(lo, authored));
      m.userData.off = kind === 'trim' ? 0.0 : 0.02;
      m.userData.kind = kind;
      out.push({ mat: m, kind });
    });
  });
  return out;
}

const setGlow = (glows, on, scale = 1) => {
  for (const g of glows) g.mat.emissiveIntensity = on ? g.mat.userData.on * scale : g.mat.userData.off;
};

// ------------------------------------------------------------------ chalk wall-buy art
//
// Hand-drawn look, generated at load time from the weapon model:
//   1. the weapon is rendered orthographically with a *normal* material, so we get both
//      a silhouette mask and the interior normal discontinuities (receiver/magazine/
//      barrel joins) to draw construction lines from;
//   2. the outline is traced with three jittered passes of short chalk dabs at varying
//      alpha, so the line has weight variation instead of a uniform 1 px border;
//   3. a light diagonal hatch fills the body, heavier under the barrel;
//   4. the price is scrawled underneath in the same chalk;
//   5. the whole thing is multiplied by a dusty grain field and eroded near the plate
//      edges, so it reads as chalk on plaster, not as a decal.
// Nothing here is emissive — chalk does not emit (review item 22).
const ART_H = 256, PRICE_H = 64;    // canvas is ART_H + PRICE_H tall; art sits in the top band

function chalkTexture(renderer, model, price = 0) {
  const W = 512, H = ART_H + PRICE_H;
  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
  const scene = new THREE.Scene();
  const nrm = new THREE.MeshNormalMaterial();
  const m = model.clone(true);
  m.traverse(o => { if (o.isMesh) o.material = nrm; });
  scene.add(m);
  const halfW = Math.max(size.z, size.y * 2) * 0.52, halfH = halfW / 2;
  const cam = new THREE.OrthographicCamera(-halfW, halfW, halfH, -halfH, 0.01, 10);
  cam.position.set(center.x + 3, center.y, center.z);
  cam.lookAt(center);
  const rt = new THREE.WebGLRenderTarget(W, ART_H);
  const prevRT = renderer.getRenderTarget();
  const prevClear = renderer.getClearColor(new THREE.Color()), prevAlpha = renderer.getClearAlpha();
  renderer.setRenderTarget(rt);
  renderer.setClearColor(0x000000, 0);
  renderer.clear();
  renderer.render(scene, cam);
  const px = new Uint8Array(W * ART_H * 4);
  renderer.readRenderTargetPixels(rt, 0, 0, W, ART_H, px);
  renderer.setRenderTarget(prevRT);
  renderer.setClearColor(prevClear, prevAlpha);
  rt.dispose();
  nrm.dispose();

  // flip into canvas row order, split into a coverage mask and a packed normal
  const N = W * ART_H;
  const mask = new Uint8Array(N), nx = new Uint8Array(N), ny = new Uint8Array(N);
  for (let y = 0; y < ART_H; y++) for (let x = 0; x < W; x++) {
    const s = (y * W + x) * 4, d = (ART_H - 1 - y) * W + x;
    mask[d] = px[s + 3] > 16 ? 1 : 0;
    nx[d] = px[s]; ny[d] = px[s + 1];
  }

  let seed = 20250922 % 2147483647;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);

  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const g = c.getContext('2d');
  g.clearRect(0, 0, W, H);
  const CHALK = '238,234,224';

  // strokes accumulate into a float coverage buffer rather than through thousands of
  // fillStyle/fillRect round-trips — this runs during the loading screen, once per wall buy.
  const cov = new Float32Array(W * H);
  const dab = (x, y, s, a) => {
    for (let dy = 0; dy < s; dy++) {
      const yy = y + dy;
      if (yy < 0 || yy >= H) continue;
      for (let dx = 0; dx < s; dx++) {
        const xx = x + dx;
        if (xx < 0 || xx >= W) continue;
        const i = yy * W + xx;
        cov[i] = 1 - (1 - cov[i]) * (1 - a);
      }
    }
  };

  const at = (x, y) => (x < 0 || y < 0 || x >= W || y >= ART_H ? 0 : mask[y * W + x]);

  // ---- 1. hatch fill (light, so the silhouette stays a drawing not a blob)
  for (let y = 0; y < ART_H; y++) for (let x = 0; x < W; x++) {
    if (!mask[y * W + x]) continue;
    const diag = (x + y * 2) % 9;
    if (diag < 2 && rnd() < 0.85) dab(x, y, 1, 0.34 + rnd() * 0.22);
    else if (rnd() < 0.18) dab(x, y, 1, 0.12 + rnd() * 0.1);
  }

  // ---- 2. interior construction lines from normal discontinuities
  for (let y = 1; y < ART_H - 1; y++) for (let x = 1; x < W - 1; x++) {
    const i = y * W + x;
    if (!mask[i] || !mask[i - 1] || !mask[i + 1] || !mask[i - W] || !mask[i + W]) continue;
    const d = Math.abs(nx[i] - nx[i + 1]) + Math.abs(ny[i] - ny[i + 1]) +
              Math.abs(nx[i] - nx[i + W]) + Math.abs(ny[i] - ny[i + W]);
    if (d < 46) continue;
    for (let p = 0; p < 2; p++) {
      if (rnd() > 0.72) continue;
      dab(x + ((rnd() * 3) | 0) - 1, y + ((rnd() * 3) | 0) - 1, 2, 0.45 + rnd() * 0.35);
    }
  }

  // ---- 3. silhouette: three jittered passes with real line-weight variation
  const OUT = [[0, 0, 1.0, 4], [1.6, -1.2, 0.75, 3], [-1.5, 1.3, 0.6, 3]];
  for (let y = 0; y < ART_H; y++) for (let x = 0; x < W; x++) {
    if (!mask[y * W + x]) continue;
    if (at(x - 1, y) && at(x + 1, y) && at(x, y - 1) && at(x, y + 1)) continue;   // interior
    // pressure varies slowly along the contour so the stroke fattens and thins
    const pressure = 0.55 + 0.45 * Math.sin(x * 0.055 + y * 0.09) * Math.sin(y * 0.031 + 1.7);
    for (const [ox, oy, a, s] of OUT) {
      if (rnd() > 0.93) continue;   // dry-brush skips
      dab(Math.round(x + ox + (rnd() - 0.5) * 1.6), Math.round(y + oy + (rnd() - 0.5) * 1.6), s, a * (0.42 + pressure * 0.62));
    }
  }

  // ---- 4. the price, scrawled under the drawing
  if (price > 0) {
    const label = String(price);
    g.textAlign = 'center'; g.textBaseline = 'middle';
    for (let p = 0; p < 3; p++) {
      g.save();
      g.translate(W * 0.5 + (rnd() - 0.5) * 2.4, ART_H + PRICE_H * 0.46 + (rnd() - 0.5) * 2.4);
      g.rotate(-0.035 + (rnd() - 0.5) * 0.02);
      g.font = `600 ${46 - p * 1.5}px "Special Elite", "Courier New", monospace`;
      g.fillStyle = `rgba(${CHALK},${p === 0 ? 0.8 : 0.34})`;
      g.fillText(label, 0, 0);
      g.restore();
    }
    // underline scratch
    g.strokeStyle = `rgba(${CHALK},0.45)`; g.lineWidth = 2.2; g.lineCap = 'round';
    g.beginPath();
    const uy = ART_H + PRICE_H * 0.82;
    g.moveTo(W * 0.5 - 62, uy + 2);
    g.bezierCurveTo(W * 0.5 - 20, uy - 2.5, W * 0.5 + 24, uy + 2.5, W * 0.5 + 62, uy - 1.5);
    g.stroke();
  }

  // ---- 5. fold the text pass (drawn through canvas 2D) into the coverage buffer,
  //         then multiply by a grainy chalk-dust field and erode at the plate edges
  const img = g.getImageData(0, 0, W, H), data = img.data;
  const noise = new Float32Array(1024);
  for (let i = 0; i < 1024; i++) noise[i] = rnd();
  const R = 238, G = 234, B = 222;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const p = y * W + x, i = p * 4;
    let a = cov[p];
    const text = data[i + 3] / 255;
    if (text > 0) a = 1 - (1 - a) * (1 - text);
    if (a <= 0.002) { data[i + 3] = 0; continue; }
    const grain = 0.72 + 0.28 * (noise[(x * 7 + y * 131) & 1023] * 0.6 + noise[((x >> 2) * 37 + (y >> 1) * 11) & 1023] * 0.4);
    const ex = Math.min(1, Math.min(x, W - 1 - x) / 26), ey = Math.min(1, Math.min(y, H - 1 - y) / 20);
    data[i] = R; data[i + 1] = G; data[i + 2] = B;
    data[i + 3] = Math.min(255, a * 255 * grain * Math.min(ex, ey));
  }
  g.putImageData(img, 0, 0);

  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  // plane sizing: the art band is the part that must sit over the mounted weapon, so the
  // quad is offset downward by half the price band.
  const planeW = halfW * 2 * 1.25;
  const planeH = planeW * (H / W);
  return { tex, planeW, planeH, offsetY: (PRICE_H / 2 / H) * planeH };
}

// ------------------------------------------------------------------ base
class Interactable {
  constructor(game, pos) { this.game = game; this.pos = pos.clone(); this.radius = 1.6; this.hold = false; this.enabled = true; }
  prompt() { return null; }
  use() {}
  update() {}
}

// ------------------------------------------------------------------ doors
export class Door extends Interactable {
  constructor(game, id, marker, data) {
    super(game, marker.pos);
    this.id = id;
    this.cfg = DOORS[id] || { cost: 1000, label: 'Door', opens: [] };
    this.data = data;
    this.radius = 2.2;
    this.opening = -1;
  }
  prompt() {
    if (this.data.open) return null;
    return `Hold <b>F</b> to open ${this.cfg.label} [Cost: ${this.cfg.cost}]`;
  }
  use() {
    const g = this.game;
    if (this.data.open) return;
    if (!g.spend(this.cfg.cost)) return;
    this.open();
  }
  open(quiet = false) {
    const g = this.game;
    this.data.open = true;
    this.opening = 0;
    g.map.collision.setEnabled(this.id, false);
    if (this.data.colBox) g.nav.rebuildRegion(this.data.colBox);
    g.openZones(this.cfg.opens);
    if (!quiet) g.audio.playAt('door_open', this.pos, { volume: 1 });
    const v = this.data.visual;
    this.startY = v ? v.position.y : 0;
    if (v) this.startPos = v.position.clone();
    if (!quiet) for (let i = 0; i < 4; i++) g.fx.dirtBurst(_v.copy(this.pos).add(new THREE.Vector3((Math.random() - 0.5) * 1.5, 0, (Math.random() - 0.5) * 1.5)));
  }
  update(dt) {
    if (this.opening < 0) return;
    this.opening += dt;
    const v = this.data.visual;
    if (v) {
      const t = clamp01(this.opening / 1.1);
      v.position.y = this.startY + ease(t) * 3.2;
      v.rotation.z = Math.sin(this.opening * 20) * 0.02 * (1 - t);
      if (t >= 1) { v.visible = false; this.opening = -1; }
    } else this.opening = -1;
  }
}

// ------------------------------------------------------------------ wall buys
export class WallBuy extends Interactable {
  constructor(game, weaponId, marker) {
    super(game, marker.pos);
    this.weaponId = weaponId;
    this.def = WEAPONS[weaponId];
    this.marker = marker;
    this.radius = 1.7;
    this.bought = false;
  }
  async init() {
    const g = this.game;
    await g.viewmodel.load(this.weaponId);
    const model = g.viewmodel.worldModel(this.weaponId);
    if (!model) return;
    const chalk = chalkTexture(g.renderer.renderer, model, this.def.wallCost);
    // drawing a touch larger than the real gun that mounts over it; the quad is pushed
    // down so the *art* band (not the price band) lands on the marker.
    const geo = new THREE.PlaneGeometry(chalk.planeW, chalk.planeH);
    geo.translate(0, -chalk.offsetY, 0);
    const plane = new THREE.Mesh(geo,
      new THREE.MeshStandardMaterial({
        map: chalk.tex, transparent: true, depthWrite: false, roughness: 1, metalness: 0,
        polygonOffset: true, polygonOffsetFactor: -2,
        // a faint self-light so the chalk reads in the dusk and indoors, as BO2's wall
        // drawings do (the user found the pure-diffuse version invisible)
        emissive: 0xffffff, emissiveMap: chalk.tex, emissiveIntensity: 0.45,
      }));
    placeAt(plane, this.marker);
    g.scene.add(plane);
    // the real gun mounted over the chalk after the first purchase (BO2 behaviour)
    this.mount = model;
    model.visible = false;
    const grp = new THREE.Group();
    placeAt(grp, this.marker);
    grp.add(model);
    model.rotation.y = Math.PI / 2;     // barrel along the wall
    model.position.z = 0.07;
    g.scene.add(grp);
  }
  prompt() {
    const g = this.game;
    const inv = g.weapons.find(this.weaponId);
    if (inv) {
      const cost = inv.pap ? PAP_AMMO_COST : Math.round(this.def.wallCost / 2);
      return `Hold <b>F</b> for ${inv.pap ? 'Upgraded ' : ''}Ammo [Cost: ${cost}]`;
    }
    return `Hold <b>F</b> for ${this.def.name} [Cost: ${this.def.wallCost}]`;
  }
  use() {
    const g = this.game;
    const inv = g.weapons.find(this.weaponId);
    if (inv) {
      const cost = inv.pap ? PAP_AMMO_COST : Math.round(this.def.wallCost / 2);
      const st = g.weapons.stats(inv);
      if (inv.reserve >= st.reserve && inv.mag >= st.mag) { g.audio.play('purchase_deny'); return; }
      if (!g.spend(cost)) return;
      g.weapons.refill(inv);
    } else {
      if (!g.spend(this.def.wallCost)) return;
      g.weapons.give(this.weaponId);
      if (!this.bought && this.mount) { this.bought = true; this.mount.visible = true; }
    }
  }
}

// ------------------------------------------------------------------ perks
function placeholderPerk(color) {
  const grp = new THREE.Group();
  const body = new THREE.Mesh(new THREE.BoxGeometry(1.1, 2.2, 0.8), new THREE.MeshStandardMaterial({ color, roughness: 0.5, metalness: 0.3 }));
  body.position.y = 1.1; grp.add(body);
  const sign = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.5, 0.05), new THREE.MeshStandardMaterial({ color: 0x111111, emissive: color, emissiveIntensity: 0.2, name: 'glow' }));
  sign.position.set(0, 1.75, 0.41); grp.add(sign);
  grp.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  return grp;
}

export class PerkMachine extends Interactable {
  constructor(game, perkId, marker) {
    super(game, marker.pos);
    this.perkId = perkId;
    this.cfg = PERKS[perkId];
    this.marker = marker;
    this.radius = 1.9;
    this.buys = 0;
    this.jingleT = 20 + Math.random() * 40;
  }
  async init() {
    const g = this.game;
    let obj = await prop(`perk_${this.perkId}`);
    if (!obj) obj = placeholderPerk(new THREE.Color(this.cfg.color));
    placeAt(obj, this.marker);
    g.scene.add(obj);
    this.obj = obj;
    this.glows = glowMats(obj);
    const col = new THREE.Color(this.cfg.color);
    // A perk machine is a fridge with a lightbox, not a floodlight.  The old rig was a
    // PointLight(col, 9, 5) sitting 0.9 m out at chest height in a 3 m room, which
    // wall-washed the whole interior in one hue.  This one pools on the floor in front
    // of the machine and dies inside 3.2 m.
    this.lightOn = 2.2;
    this.light = new THREE.PointLight(col, 0, 3.2, 2);
    this.light.position.copy(this.marker.pos).addScaledVector(this.marker.forward, 0.45).add(new THREE.Vector3(0, 1.55, 0));
    g.scene.add(this.light);
    this.setPower(g.power || this.cfg.noPower);
  }
  setPower(on) {
    this.powered = on;
    setGlow(this.glows, on);
    this.light.intensity = on ? this.lightOn : 0;
  }
  prompt() {
    const g = this.game;
    if (!this.powered) return 'You must turn on the power first!';
    if (g.player.perks.has(this.perkId)) return null;
    if (this.perkId === 'quickrevive' && this.buys >= 3) return null;
    return `Hold <b>F</b> for ${this.cfg.name} [Cost: ${this.cfg.cost}]`;
  }
  use() {
    const g = this.game;
    if (!this.powered || g.player.perks.has(this.perkId) || g.weapons.busyDrinking) return;
    if (this.perkId === 'quickrevive' && this.buys >= 3) return;
    if (!g.spend(this.cfg.cost)) return;
    this.buys++;
    g.audio.playAt(`perk_jingle_${this.perkId}`, this.pos, { volume: 0.7 });
    g.weapons.drink(this.perkId, () => g.givePerk(this.perkId));
  }
  update(dt, t) {
    if (!this.powered) return;
    // lazy neon-tube flicker: mostly steady, with an occasional dropout on the trim
    const wob = 0.92 + Math.sin(t * 3 + this.pos.x) * 0.06 + Math.sin(t * 17.3 + this.pos.z) * 0.02;
    this.light.intensity = this.lightOn * wob;
    for (const g of this.glows) if (g.kind === 'trim') g.mat.emissiveIntensity = g.mat.userData.on * wob;
    this.jingleT -= dt;
    if (this.jingleT < 0) {
      this.jingleT = 60 + Math.random() * 90;
      if (this.pos.distanceTo(this.game.player.pos) < 10) this.game.audio.playAt(`perk_jingle_${this.perkId}`, this.pos, { volume: 0.45 });
    }
  }
}

// ------------------------------------------------------------------ power switch
export class PowerSwitch extends Interactable {
  constructor(game, marker) { super(game, marker.pos); this.marker = marker; this.radius = 1.7; this.flip = -1; }
  async init() {
    const g = this.game;
    let obj = await prop('power_switch');
    if (!obj) {
      obj = new THREE.Group();
      const panel = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.9, 0.25), new THREE.MeshStandardMaterial({ color: 0x55605a, roughness: 0.6, metalness: 0.5 }));
      panel.position.set(0, 0, 0.125); obj.add(panel);
      const lever = new THREE.Group(); lever.name = 'lever'; lever.position.set(0, 0, 0.26); obj.add(lever);
      const h = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.35, 0.06), new THREE.MeshStandardMaterial({ color: 0x222222, metalness: 0.7, roughness: 0.4 }));
      h.position.y = -0.15; lever.add(h);
      const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.04), new THREE.MeshStandardMaterial({ color: 0x220000, emissive: 0xff2200, emissiveIntensity: 0.1, name: 'glow' }));
      lamp.position.set(0.2, 0.32, 0.26); obj.add(lamp);
      obj.traverse(o => { if (o.isMesh) o.castShadow = true; });
    }
    placeAt(obj, this.marker);
    g.scene.add(obj);
    this.obj = obj;
    this.lever = findNode(obj, 'lever');
    this.leverRest = this.lever ? this.lever.rotation.x : 0;
    this.glows = glowMats(obj);
    setGlow(this.glows, false);
  }
  prompt() { return this.game.power ? null : 'Hold <b>F</b> to turn on Power'; }
  use() {
    if (this.game.power) return;
    this.flip = 0;
    this.game.audio.playAt('board_slam', this.pos, { volume: 0.7, rate: 0.7 });
  }
  update(dt) {
    if (this.flip < 0) return;
    this.flip += dt;
    const t = clamp01(this.flip / 0.6);
    if (this.lever) this.lever.rotation.x = this.leverRest - ease(t) * 2.4;
    if (t >= 1) {
      this.flip = -1;
      setGlow(this.glows, true);
      this.game.setPower(true);
    }
  }
}

// ------------------------------------------------------------------ barricades
export class Barrier extends Interactable {
  constructor(game, id, marker, spawnMarker) {
    super(game, marker.pos);
    this.id = id;
    this.marker = marker;
    this.spawn = spawnMarker;
    this.radius = 1.9;
    this.hold = true;
    this.boards = [];
    this.repairT = 0;
    this.climber = null;
    const f = marker.forward;
    const col = game.map.collision;
    const out = marker.pos.clone().addScaledVector(f, -0.6);
    const inn = marker.pos.clone().addScaledVector(f, 0.8);
    const gOut = col.ground(out.x, out.z, marker.pos.y + 0.5, 4, { doors: false, barriers: false });
    const gIn = col.ground(inn.x, inn.z, marker.pos.y + 0.5, 4, { doors: false, barriers: false });
    out.y = gOut ?? marker.pos.y - 0.9; inn.y = gIn ?? marker.pos.y - 0.9;
    this.outside = out; this.inside = inn;
  }
  async init() {
    const g = this.game;
    let obj = await prop('barricade');
    if (!obj) {
      obj = new THREE.Group();
      const wood = new THREE.MeshStandardMaterial({ color: 0x6e5236, roughness: 0.85 });
      for (let i = 0; i < 6; i++) {
        const b = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.14, 0.04), wood);
        b.name = `board_${i + 1}`;
        b.position.set(0, 0.12 + i * 0.17, 0.1);
        b.rotation.z = (Math.random() - 0.5) * 0.25;
        b.castShadow = true;
        obj.add(b);
      }
    }
    placeAt(obj, this.marker);
    g.scene.add(obj);
    this.obj = obj;
    for (let i = 1; i <= 6; i++) {
      const b = findNode(obj, `board_${i}`);
      if (!b) continue;
      this.boards.push({ obj: b, up: true, restP: b.position.clone(), restQ: b.quaternion.clone(), anim: -1, mode: null, from: new THREE.Vector3(), fromQ: new THREE.Quaternion() });
    }
  }
  boardsUp() { return this.boards.filter(b => b.up).length; }
  tearBoard(z) {
    const g = this.game;
    const up = this.boards.filter(b => b.up);
    if (!up.length) return;
    const b = up[up.length - 1 - Math.floor(Math.random() * Math.min(2, up.length))];
    b.up = false; b.anim = 0; b.mode = 'tear';
    b.spin = new THREE.Vector3((Math.random() - 0.5) * 6, (Math.random() - 0.5) * 6, (Math.random() - 0.5) * 6);
    g.audio.playAt('board_tear', this.pos, { volume: 1 });
    g.fx.dust(_v.copy(this.pos).add(new THREE.Vector3(0, 0.5, 0)), this.marker.forward.clone().negate(), [0.45, 0.38, 0.3, 0.5]);
  }
  repairOne() {
    const b = this.boards.find(x => !x.up && x.anim < 0);
    if (!b) return false;
    b.up = true; b.anim = 0; b.mode = 'repair';
    // fly in from the floor at the player's feet
    const local = this.obj.worldToLocal(this.game.player.pos.clone().add(new THREE.Vector3(0, 0.3, 0)));
    b.from.copy(local);
    b.fromQ.setFromEuler(new THREE.Euler(Math.random(), Math.random(), Math.random()));
    b.obj.visible = true;
    return true;
  }
  repairAll() {
    for (const b of this.boards) if (!b.up) { b.up = true; b.anim = -1; b.obj.visible = true; b.obj.position.copy(b.restP); b.obj.quaternion.copy(b.restQ); }
  }
  prompt() {
    if (this.boardsUp() >= 6) return null;
    // only from the inside
    const p = this.game.player.pos;
    _v.subVectors(p, this.pos);
    if (_v.dot(this.marker.forward) < 0.1) return null;
    return 'Hold <b>F</b> to Rebuild Barrier';
  }
  holdUse(dt) {
    const g = this.game;
    this.repairT -= dt;
    if (this.repairT > 0) return;
    if (this.boardsUp() >= 6) return;
    if (this.repairOne()) {
      this.repairT = g.player.perks.has('speedcola') ? 0.55 : 1.0;
      setTimeout(() => {
        g.audio.playAt('board_slam', this.pos, { volume: 1 });
        g.player.shake(0.12);
        if (g.boardPoints < POINTS.boardCapPerRound) { g.boardPoints += POINTS.board; g.addPoints(POINTS.board); }
      }, 250);
      g.audio.playAt('board_repair', this.pos, { volume: 0.8 });
    }
  }
  update(dt) {
    for (const b of this.boards) {
      if (b.anim < 0) continue;
      b.anim += dt;
      if (b.mode === 'tear') {
        const t = b.anim;
        const out = new THREE.Vector3(0, 0, -1).multiplyScalar(t * 2.2);   // toward the outside (local -Z)
        b.obj.position.copy(b.restP).add(out).add(new THREE.Vector3(0, -4.9 * t * t + 1.2 * t, 0));
        b.obj.rotation.set(b.spin.x * t, b.spin.y * t, b.spin.z * t);
        if (t > 0.7) { b.obj.visible = false; b.anim = -1; }
      } else {
        const t = clamp01(b.anim / 0.25);
        b.obj.position.lerpVectors(b.from, b.restP, ease(t));
        b.obj.position.y += Math.sin(t * Math.PI) * 0.4;
        b.obj.quaternion.slerpQuaternions(b.fromQ, b.restQ, ease(t));
        if (t >= 1) { b.anim = -1; b.obj.position.copy(b.restP); b.obj.quaternion.copy(b.restQ); }
      }
    }
  }
}

// ------------------------------------------------------------------ mystery box beam
//
// A light shaft, not a decal.  The old beam was a DoubleSide additive cylinder with
// `fog: false`, so it was brightest in the middle (you saw through both walls), had a
// hard silhouette and stayed full strength while the world behind it fogged away —
// which is exactly why it read as a UI overlay pasted over the sky (review item 3).
//
// This one:  * FrontSide, so nothing is double-counted;
//            * view-dependent rim falloff, so the *edges* glow and the centre is thin,
//              which is how a real shaft of dusty air behaves;
//            * a seamless scrolling fbm for interior structure;
//            * a squared height falloff over a sane 18 m column, so the top is gone;
//            * distance fog folded into the alpha, so it recedes with the world.
const BEAM_VERT = /* glsl */`
  varying vec2 vUv;
  varying vec3 vNrm;
  varying vec3 vView;
  varying float vDepth;
  void main() {
    vUv = uv;
    vNrm = normalize(normalMatrix * normal);
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vView = -mv.xyz;
    vDepth = -mv.z;
    gl_Position = projectionMatrix * mv;
  }`;

const BEAM_FRAG = /* glsl */`
  uniform float uTime;
  uniform float uOpacity;
  uniform float uFogDensity;
  uniform vec3 uColor;
  varying vec2 vUv;
  varying vec3 vNrm;
  varying vec3 vView;
  varying float vDepth;

  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123); }
  float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
  }
  float fbm(vec2 p) {
    float a = 0.5, s = 0.0;
    for (int i = 0; i < 3; i++) { s += a * vnoise(p); p *= 2.03; a *= 0.5; }
    return s;
  }

  void main() {
    vec3 N = normalize(vNrm);
    vec3 V = normalize(vView);
    float rim = pow(1.0 - abs(dot(N, V)), 1.8);
    float h = clamp(vUv.y, 0.0, 1.0);
    float height = pow(1.0 - h, 2.6) * smoothstep(0.0, 0.05, h);
    // seamless around the cylinder: sample the noise on a circle, scroll it vertically
    float th = vUv.x * 6.2831853;
    vec2 q = vec2(cos(th), sin(th)) * 2.1 + vec2(0.0, h * 5.0 - uTime * 0.55);
    float n = 0.58 + 0.42 * fbm(q);
    float a = uOpacity * (0.16 + rim * 1.25) * height * n;
    // distance fog, folded into the alpha because additive blending cannot mix to fog colour
    float fog = 1.0 - exp(-uFogDensity * uFogDensity * vDepth * vDepth);
    a *= (1.0 - fog);
    gl_FragColor = vec4(uColor, clamp(a, 0.0, 1.0));
  }`;

// soft additive disc used for the pool the beam lands in
function radialTexture(stops) {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d');
  const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  for (const [o, col] of stops) gr.addColorStop(o, col);
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// ------------------------------------------------------------------ mystery box
function placeholderBox() {
  const grp = new THREE.Group();
  const wood = new THREE.MeshStandardMaterial({ color: 0x4a3420, roughness: 0.8 });
  const base = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.45, 0.6), wood); base.position.y = 0.225; grp.add(base);
  const lid = new THREE.Group(); lid.name = 'lid'; lid.position.set(0, 0.45, -0.3); grp.add(lid);
  const lm = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.1, 0.6), wood); lm.position.set(0, 0.05, 0.3); lid.add(lm);
  const q = new THREE.Mesh(new THREE.PlaneGeometry(0.2, 0.25), new THREE.MeshStandardMaterial({ color: 0x000000, emissive: 0x88bbff, emissiveIntensity: 0.6, name: 'glow_q' }));
  q.position.set(0, 0.25, 0.301); grp.add(q);
  grp.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  return grp;
}

export class MysteryBox extends Interactable {
  constructor(game, markers) {
    super(game, markers[0].pos);
    this.markers = markers;
    this.index = 0;
    this.radius = 2.0;
    this.state = 'idle';
    this.t = 0;
    this.uses = 0;
    this.offer = null;
  }
  async init() {
    const g = this.game;
    this.template = await prop('mystery_box') || placeholderBox();
    this.teddyTemplate = await prop('teddy_bear');
    this.obj = this.template;
    g.scene.add(this.obj);
    this.lid = findNode(this.obj, 'lid');
    this.lidRest = this.lid ? this.lid.rotation.x : 0;
    // The crate's only emissive is the painted "?" — material `glow` on the current crate,
    // `glow_q` on the reworked one (asset contract).  Either way it is a *mark*, not a
    // lightbox, so it is held in the low band and breathed rather than left burning.
    this.marks = glowMats(this.obj);
    for (const q of this.marks) q.mat.userData.on = Math.min(GLOW_BANDS.mark[1], Math.max(GLOW_BANDS.mark[0], q.mat.userData.on));

    // ---- light column
    this.beamMat = new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uOpacity: { value: 1 },
        uFogDensity: { value: g.scene.fog?.density ?? 0.008 },
        uColor: { value: new THREE.Color(0.42, 0.66, 1.25) },
      },
      vertexShader: BEAM_VERT,
      fragmentShader: BEAM_FRAG,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      side: THREE.FrontSide,
      fog: false,           // handled in the shader (additive can't mix toward fog colour)
    });
    this.beam = new THREE.Mesh(new THREE.CylinderGeometry(0.30, 0.52, 18, 28, 1, true), this.beamMat);
    this.beam.renderOrder = 3;
    g.scene.add(this.beam);

    // ---- the pool the column lands in, so it stands on something
    this.groundPool = new THREE.Mesh(
      // 2.6 m so the falloff clears the crate footprint — a 1.8 m disc was almost entirely
      // hidden under the box itself and only the very edge of the gradient was ever visible
      new THREE.PlaneGeometry(2.6, 2.6),
      new THREE.MeshBasicMaterial({
        map: radialTexture([[0, 'rgba(190,220,255,0.95)'], [0.35, 'rgba(120,175,255,0.45)'], [1, 'rgba(60,120,255,0)']]),
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: true, opacity: 0.55,
      }));
    this.groundPool.rotation.x = -Math.PI / 2;
    this.groundPool.renderOrder = 2;
    g.scene.add(this.groundPool);

    // the beam now actually emits: the crate and the ground under it are lit by it
    this.light = new THREE.PointLight(0x9fc4ff, 0, 5, 2);
    g.scene.add(this.light);
    this.floater = new THREE.Group();
    this.floater.scale.setScalar(1.7);   // BO2 shows the offer oversized, it is a poster not a prop
    this.spin = 0;
    g.scene.add(this.floater);
    this.reset();
  }
  /** new game: the box starts at a random one of its spots (it can be the street one) */
  reset() {
    this.state = 'idle';
    this.t = 0;
    this.uses = 0;
    this.offer = null;
    if (this.floater) while (this.floater.children.length) this.floater.remove(this.floater.children[0]);
    if (this.obj) this.obj.rotation.set(0, 0, 0);
    this.moveTo(Math.floor(Math.random() * this.markers.length), false);
  }
  moveTo(i, fx = true) {
    this.index = i;
    const m = this.markers[i];
    this.pos.copy(m.pos);
    placeAt(this.obj, m);
    this.obj.visible = true;
    this.obj.scale.setScalar(1);
    this.beam.position.copy(m.pos).add(new THREE.Vector3(0, 9, 0));
    this.groundPool.position.copy(m.pos).add(new THREE.Vector3(0, 0.03, 0));
    this.light.position.copy(m.pos).add(new THREE.Vector3(0, 1.1, 0)).addScaledVector(m.forward, 0.3);
    if (fx) this.game.fx.glowBurst(this.light.position, [1, 2, 4, 1], 40, 5);
  }
  cost() { return this.game.fireSale ? FIRE_SALE_BOX_COST : BOX_COST; }
  prompt() {
    if (this.state === 'idle') return `Hold <b>F</b> for Random Weapon [Cost: ${this.cost()}]`;
    if (this.state === 'offer' && this.offer) return `Hold <b>F</b> for ${WEAPONS[this.offer].name}`;
    return null;
  }
  use() {
    const g = this.game;
    if (this.state === 'idle') {
      if (!g.spend(this.cost())) return;
      this.uses++;
      this.state = 'spin';
      this.t = 0;
      this.cycleT = 0;
      this.paid = this.cost();
      g.audio.playAt('box_open', this.pos, { volume: 1 });
      g.audio.playAt('box_music', this.pos, { volume: 0.9 });
      const pool = Object.keys(WEAPONS).filter(id => id !== 'm1911' && !g.weapons.find(id));
      const weights = pool.map(id => WEAPONS[id].box ?? 2);
      let r = Math.random() * weights.reduce((a, b) => a + b, 0);
      this.final = pool[0];
      for (let i = 0; i < pool.length; i++) { r -= weights[i]; if (r <= 0) { this.final = pool[i]; break; } }
      this.pool = pool;
      this.teddy = !g.fireSale && this.uses > 3 && this.markers.length > 1 && Math.random() < 0.18;
    } else if (this.state === 'offer' && this.offer) {
      g.weapons.give(this.offer);
      this.offer = null;
      this._clearFloater();
      this.state = 'closing';
      this.t = 0;
    }
  }
  _clearFloater() { while (this.floater.children.length) this.floater.remove(this.floater.children[0]); }
  _show(id) {
    this._clearFloater();
    const m = this.game.viewmodel.worldModel(id);
    if (m) { m.rotation.y = Math.PI / 2; this.floater.add(m); }
  }
  update(dt, time) {
    const g = this.game;
    this.t += dt;
    const m = this.markers[this.index];
    const lidOpen = this.state === 'spin' || this.state === 'offer' || this.state === 'teddy' ? 1 : 0;
    // 1.25 rad (~72°) instead of 1.6: the old angle threw the lid straight up the sightline
    if (this.lid) this.lid.rotation.x += ((this.lidRest - lidOpen * 1.25) - this.lid.rotation.x) * Math.min(1, dt * 8);
    const lit = this.state !== 'gone' && this.state !== 'rising';
    this.beam.visible = this.groundPool.visible = lit;
    const breathe = 0.9 + Math.sin(time * 1.15) * 0.12 + Math.sin(time * 0.37) * 0.05;
    this.beamMat.uniforms.uTime.value = time;
    this.beamMat.uniforms.uOpacity.value = breathe * (lidOpen ? 1.5 : 1);
    if (g.scene.fog) this.beamMat.uniforms.uFogDensity.value = g.scene.fog.density;
    this.groundPool.material.opacity = 0.42 * breathe * (lidOpen ? 1.6 : 1);
    // the "?" marks breathe with the column (item 17 — the rest is a Blender fix)
    for (const q of this.marks) q.mat.emissiveIntensity = q.mat.userData.on * (0.72 + 0.28 * Math.sin(time * 1.15 + 0.4)) * (lidOpen ? 1.8 : 1);
    this.light.intensity = lidOpen ? 9 + Math.sin(time * 26) * 2.5 : 6 * breathe;

    // BO2: the offer rises clear of the crate, broadside to the player, at poster scale
    const base = m.pos.clone().add(new THREE.Vector3(0, 0.85, 0)).addScaledVector(m.forward, 0.15);
    if (this.state === 'spin') this.spin += dt * (2.4 - 1.7 * clamp01(this.t / 4.4));
    else if (this.state === 'offer') {
      const settled = Math.round(this.spin / (Math.PI * 2)) * Math.PI * 2;   // back to broadside
      this.spin += (settled - this.spin) * Math.min(1, dt * 3);
    } else if (this.state === 'teddy') this.spin += dt * 2;
    this.floater.quaternion.copy(m.quat);
    this.floater.rotateY(this.spin + (this.state === 'offer' ? Math.sin(time * 0.8) * 0.18 : 0));

    if (this.state === 'spin') {
      // weapons cycle and rise out of the box, slowing down
      const dur = 4.4;
      const k = clamp01(this.t / dur);
      this.cycleT -= dt;
      if (this.cycleT <= 0) {
        this.cycleT = 0.05 + k * k * 0.35;
        const pick = this.pool[Math.floor(Math.random() * this.pool.length)];
        this._show(k > 0.97 ? this.final : pick);
      }
      this.floater.position.copy(base).add(new THREE.Vector3(0, ease(k) * 0.55, 0));
      if (this.t >= dur) {
        this.t = 0;
        if (this.teddy) {
          this._clearFloater();
          if (this.teddyTemplate) this.floater.add(this.teddyTemplate.clone(true));
          else this.floater.add(new THREE.Mesh(new THREE.SphereGeometry(0.2), new THREE.MeshStandardMaterial({ color: 0x8a6a4a })));
          this.state = 'teddy';
          g.audio.playAt('box_teddy', this.pos, { volume: 1 });
          g.addPoints(this.paid, true);
        } else {
          this._show(this.final);
          this.offer = this.final;
          this.state = 'offer';
        }
      }
    } else if (this.state === 'offer') {
      // hold the offer up where it can be read, then sink it back in the last 2.5 s
      const sink = clamp01((this.t - 9.5) / 2.5);
      this.floater.position.copy(base).add(new THREE.Vector3(0, 0.55 - ease(sink) * 0.55 + Math.sin(time * 1.7) * 0.015, 0));
      if (this.t >= 12) { this.offer = null; this._clearFloater(); this.state = 'closing'; this.t = 0; }
    } else if (this.state === 'closing') {
      if (this.t > 0.6) { this.state = 'idle'; g.audio.playAt('box_close', this.pos, { volume: 0.8 }); }
    } else if (this.state === 'teddy') {
      this.floater.position.copy(base).add(new THREE.Vector3(0, 0.55 + this.t * 0.4, 0));
      if (this.t > 2.2) { this._clearFloater(); this.state = 'rising'; this.t = 0; }
    } else if (this.state === 'rising') {
      this.obj.position.y = m.pos.y + this.t * this.t * 3;
      this.obj.rotation.y += dt * this.t * 4;
      if (this.t > 2.2) {
        g.fx.glowBurst(this.obj.position, [1, 2, 4, 1], 40, 6);
        this.obj.visible = false;
        this.state = 'gone'; this.t = 0;
        const choices = this.markers.map((_, i) => i).filter(i => i !== this.index);
        this.nextIndex = choices[Math.floor(Math.random() * choices.length)];
      }
    } else if (this.state === 'gone') {
      if (this.t > 1.5) {
        this.obj.rotation.set(0, 0, 0);
        this.moveTo(this.nextIndex);
        g.audio.playAt('powerup_spawn', this.pos, { volume: 1 });
        g.hud.flashMessage('The Mystery Box has moved!');
        this.state = 'idle';
      }
    }
  }
}

// ------------------------------------------------------------------ pack-a-punch
function placeholderPap() {
  const grp = new THREE.Group();
  const metal = new THREE.MeshStandardMaterial({ color: 0x3b3f44, roughness: 0.5, metalness: 0.8 });
  const b = new THREE.Mesh(new THREE.BoxGeometry(2.0, 1.2, 1.0), metal); b.position.y = 0.6; grp.add(b);
  const top = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 1.8, 16), metal); top.rotation.z = Math.PI / 2; top.position.set(0, 1.4, 0); grp.add(top);
  const g = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.12, 0.05), new THREE.MeshStandardMaterial({ color: 0x110022, emissive: 0x9955ff, emissiveIntensity: 0.1, name: 'glow' }));
  g.position.set(0, 1.0, 0.51); grp.add(g);
  grp.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  return grp;
}

export class PackAPunch extends Interactable {
  constructor(game, marker) { super(game, marker.pos); this.marker = marker; this.radius = 2.2; this.state = 'idle'; this.t = 0; }
  async init() {
    const g = this.game;
    this.obj = await prop('pap_machine') || placeholderPap();
    placeAt(this.obj, this.marker);
    g.scene.add(this.obj);
    this.glows = glowMats(this.obj);
    setGlow(this.glows, false);
    this.rollers = findNode(this.obj, 'rollers');
    this.lightOn = 2.6;
    this.light = new THREE.PointLight(0xa070ff, 0, 4, 2);
    this.light.position.copy(this.marker.pos).addScaledVector(this.marker.forward, 0.6).add(new THREE.Vector3(0, 1.3, 0));
    g.scene.add(this.light);
    this.floater = new THREE.Group();
    g.scene.add(this.floater);
  }
  setPower(on) {
    setGlow(this.glows, on);
    this.light.intensity = on ? this.lightOn : 0;
  }
  prompt() {
    const g = this.game;
    if (!g.power) return 'You must turn on the power first!';
    if (this.state === 'ready') return `Hold <b>F</b> to take ${this.cfgName}`;
    if (this.state !== 'idle') return null;
    const cur = g.weapons.currentInst();
    if (!cur || cur.pap) return null;
    return `Hold <b>F</b> to Pack-a-Punch [Cost: ${PAP_COST}]`;
  }
  use() {
    const g = this.game;
    if (!g.power) return;
    if (this.state === 'ready') {
      g.weapons.give(this.weaponId, true);
      this._clear();
      this.state = 'idle';
      return;
    }
    if (this.state !== 'idle') return;
    const cur = g.weapons.currentInst();
    if (!cur || cur.pap || g.weapons.busy()) return;
    if (!g.spend(PAP_COST)) return;
    this.weaponId = cur.id;
    this.cfgName = WEAPONS[cur.id].pap.name;
    g.weapons.takeCurrent();
    this.state = 'in';
    this.t = 0;
    g.audio.playAt('pap_upgrade', this.pos, { volume: 1 });
    this._clear();
    const m = g.viewmodel.worldModel(this.weaponId);
    if (m) { m.rotation.y = Math.PI / 2; this.floater.add(m); }
  }
  _clear() { while (this.floater.children.length) this.floater.remove(this.floater.children[0]); }
  update(dt, time) {
    const g = this.game;
    this.t += dt;
    const front = this.marker.pos.clone().addScaledVector(this.marker.forward, 0.75).add(new THREE.Vector3(0, 1.1, 0));
    const inside = this.marker.pos.clone().add(new THREE.Vector3(0, 1.1, 0));
    this.floater.quaternion.copy(this.marker.quat);
    if (this.rollers && g.power) this.rollers.rotation.x += dt * (this.state === 'in' || this.state === 'working' ? 12 : 1);
    if (this.state === 'in') {
      const k = clamp01(this.t / 1.0);
      this.floater.position.lerpVectors(front, inside, ease(k));
      if (k >= 1) { this.state = 'working'; this.t = 0; this.floater.visible = false; }
    } else if (this.state === 'working') {
      this.light.intensity = this.lightOn + Math.random() * 3.5;
      if (Math.random() < 0.3) g.fx.sparks(front.clone().addScaledVector(this.marker.forward, -0.3), this.marker.forward, 3, [2.5, 1.5, 4, 1]);
      if (this.t > 2.8) {
        this.state = 'out'; this.t = 0; this.floater.visible = true;
        // swap the displayed model's materials to the camo
        const vm = g.viewmodel.models.get(this.weaponId);
        if (vm) { g.viewmodel.setPap(vm, true); this._clear(); const m = g.viewmodel.worldModel(this.weaponId); g.viewmodel.setPap(vm, !!g.weapons.find(this.weaponId)?.pap); if (m) { m.rotation.y = Math.PI / 2; this.floater.add(m); } }
      }
    } else if (this.state === 'out') {
      const k = clamp01(this.t / 1.0);
      this.floater.position.lerpVectors(inside, front, ease(k));
      if (k >= 1) { this.state = 'ready'; this.t = 0; }
    } else if (this.state === 'ready') {
      this.floater.position.copy(front).add(new THREE.Vector3(0, Math.sin(time * 2) * 0.03, 0));
      const k = clamp01(this.t / 15);
      if (this.t > 15) { this._clear(); this.state = 'idle'; g.hud.flashMessage('Upgraded weapon lost...'); }
      else this.floater.position.lerp(inside, k * k * 0.5);
    } else if (g.power) this.light.intensity = this.lightOn;
  }
}
