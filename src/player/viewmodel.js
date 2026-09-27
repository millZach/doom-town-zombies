import * as THREE from 'three';
import { loadGLB, findNode, nodeName } from '../core/assets.js';
import { WEAPONS, VM_FOV, reloadClassOf } from '../config.js';
import { SUN_DIR } from '../world/sky.js';
import { ShellSystem } from '../fx/shells.js';

const ease = t => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
const clamp01 = t => Math.max(0, Math.min(1, t));
const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
const seg = (t, a, b) => clamp01((t - a) / (b - a));
/** 0 -> 1 -> 0 over [a,b] */
const pulse = (t, a, b) => Math.sin(seg(t, a, b) * Math.PI);
const _identity = new THREE.Quaternion();
const _handTilt = new THREE.Quaternion();
const _handEuler = new THREE.Euler();

// scratch
const _p = new THREE.Vector3();
const _adsT = new THREE.Vector3();
const _t1 = new THREE.Vector3();
const _t2 = new THREE.Vector3();
const _t3 = new THREE.Vector3();
const _t4 = new THREE.Vector3();
const _ejPos = new THREE.Vector3();
const _ejVel = new THREE.Vector3();
const _q1 = new THREE.Quaternion();
const _lagTarget = new THREE.Vector3();

const TAU = Math.PI * 2;

/**
 * Critically-ish damped spring step. Returns the new velocity; caller integrates position.
 * `zeta < 1` overshoots, which is what gives recoil its snap-and-settle.
 */
function springV(x, v, k, zeta, dt) {
  const c = 2 * Math.sqrt(k) * zeta;
  return v + (-k * x - c * v) * dt;
}

// ---------- Pack-a-Punch camo (object-space triplanar, animated) ----------
export const papUniforms = { uPapTime: { value: 0 } };
let camoTex = null;
function getCamoTexture() {
  if (camoTex) return camoTex;
  const s = 256, c = document.createElement('canvas');
  c.width = c.height = s;
  const g = c.getContext('2d');
  g.fillStyle = '#0b0614'; g.fillRect(0, 0, s, s);
  let seed = 42; const r = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 160; i++) {
    const x = r() * s, y = r() * s, rad = 6 + r() * 34;
    const hue = [275, 200, 320, 250][i % 4];
    const gr = g.createRadialGradient(x, y, 0, x, y, rad);
    gr.addColorStop(0, `hsla(${hue},95%,${55 + r() * 20}%,${0.25 + r() * 0.35})`);
    gr.addColorStop(1, `hsla(${hue},95%,40%,0)`);
    g.fillStyle = gr;
    for (const ox of [-s, 0, s]) for (const oy of [-s, 0, s]) { g.save(); g.translate(ox, oy); g.fillRect(x - rad, y - rad, rad * 2, rad * 2); g.restore(); }
  }
  g.strokeStyle = 'rgba(210,160,255,0.35)'; g.lineWidth = 1.5;
  for (let i = 0; i < 40; i++) {
    g.beginPath(); let x = r() * s, y = r() * s; g.moveTo(x, y);
    for (let k = 0; k < 6; k++) { x += (r() - 0.5) * 40; y += (r() - 0.5) * 40; g.lineTo(x, y); }
    g.stroke();
  }
  camoTex = new THREE.CanvasTexture(c);
  camoTex.wrapS = camoTex.wrapT = THREE.RepeatWrapping;
  camoTex.colorSpace = THREE.SRGBColorSpace;
  return camoTex;
}

function makePapMaterial(src) {
  const m = new THREE.MeshStandardMaterial({
    color: 0x2a1f3a, roughness: 0.3, metalness: 0.85,
    normalMap: src.normalMap || null, envMapIntensity: 1.2,
  });
  m.userData.isPap = true;
  const tex = getCamoTexture();
  m.onBeforeCompile = (shader) => {
    shader.uniforms.uCamo = { value: tex };
    shader.uniforms.uPapTime = papUniforms.uPapTime;
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vObjPos;\nvarying vec3 vObjN;\nvarying vec3 vPapVN;\nvarying vec3 vPapVP;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvObjPos = position;\nvObjN = normal;\n' +
        'vPapVN = normalize(normalMatrix * normal);\nvPapVP = -(modelViewMatrix * vec4(position, 1.0)).xyz;');
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform sampler2D uCamo;\nuniform float uPapTime;\nvarying vec3 vObjPos;\nvarying vec3 vObjN;\nvarying vec3 vPapVN;\nvarying vec3 vPapVP;\n' +
        'vec3 camo(vec3 p, vec3 n){ vec3 w = abs(normalize(n)); w /= (w.x+w.y+w.z); float t = uPapTime*0.05; ' +
        'return texture2D(uCamo, p.yz*6.0+vec2(t,t*0.7)).rgb*w.x + texture2D(uCamo, p.xz*6.0+vec2(-t,t)).rgb*w.y + texture2D(uCamo, p.xy*6.0+vec2(t*0.6,-t)).rgb*w.z; }')
      // The camo used to add `cm*cm*2.2` of emission on every face — well over the bloom threshold,
      // which turned an upgraded receiver into a featureless white-green blob. Now it is a quarter
      // of that and weighted by a fresnel term, so the glow rides the *edges* and the panel detail
      // survives.
      .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\nvec3 cm = camo(vObjPos, vObjN);\n' +
        'float papFres = pow(1.0 - clamp(dot(normalize(vPapVN), normalize(vPapVP)), 0.0, 1.0), 3.0);\n' +
        'diffuseColor.rgb = mix(diffuseColor.rgb, cm, 0.8);\ntotalEmissiveRadiance += cm * cm * (0.18 + 1.3 * papFres) * 0.6;');
  };
  return m;
}

// ---------- placeholder viewmodel (until the Blender weapons exist) ----------
function placeholderViewmodel(id) {
  const def = WEAPONS[id] || {};
  const metal = new THREE.MeshStandardMaterial({ color: 0x2b2d30, roughness: 0.45, metalness: 0.8, name: 'metal' });
  const wood = new THREE.MeshStandardMaterial({ color: 0x5a3519, roughness: 0.6, name: 'wood' });
  const glove = new THREE.MeshStandardMaterial({ color: 0x7a5a3a, roughness: 0.85, name: 'glove' });
  const sleeve = new THREE.MeshStandardMaterial({ color: 0x3b3f2a, roughness: 0.95, name: 'sleeve' });
  const glow = new THREE.MeshStandardMaterial({ color: 0x113311, emissive: 0x44ff44, emissiveIntensity: 3, name: 'glow' });
  const root = new THREE.Group(); root.name = 'viewmodel';
  const weapon = new THREE.Group(); weapon.name = 'weapon';
  weapon.position.set(0.12, -0.15, -0.3);
  root.add(weapon);
  const pistol = ['pistol', 'revolver', 'raygun'].includes(def.type) || id === 'knife' || id === 'frag' || id === 'drink';
  const len = pistol ? 0.2 : def.type === 'lmg' ? 0.9 : def.type === 'shotgun' ? 0.85 : def.type === 'smg' ? 0.55 : 0.95;
  const box = (w, h, d, x, y, z, mat, name) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); if (name) m.name = name; weapon.add(m); return m;
  };
  if (id === 'knife') {
    box(0.025, 0.03, 0.12, 0, 0, 0.02, wood);
    box(0.006, 0.03, 0.17, 0, 0.005, -0.12, metal);
  } else if (id === 'frag') {
    const g = new THREE.Mesh(new THREE.SphereGeometry(0.035, 16, 12), new THREE.MeshStandardMaterial({ color: 0x3d4a2a, roughness: 0.7 }));
    g.position.set(0, 0.03, -0.02); weapon.add(g);
  } else if (id === 'drink') {
    const b = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.032, 0.2, 16), new THREE.MeshStandardMaterial({ color: 0x552222, roughness: 0.1, transparent: true, opacity: 0.85, name: 'bottle_liquid' }));
    b.position.set(0, 0.05, -0.02); weapon.add(b);
  } else {
    box(0.04, 0.05, len, 0, 0.02, -len / 2 + 0.06, def.type === 'raygun' ? new THREE.MeshStandardMaterial({ color: 0x8a1c14, roughness: 0.4, metalness: 0.5, name: 'metal' }) : metal);
    box(0.032, 0.1, 0.045, 0, -0.045, 0.02, pistol ? metal : wood);
    if (!pistol) box(0.045, 0.07, 0.25, 0, 0.0, 0.2, wood);
    if (def.type === 'raygun') box(0.03, 0.03, 0.12, 0, 0.06, -0.08, glow);
    box(0.025, pistol ? 0.08 : 0.14, 0.04, 0, -0.08, pistol ? 0.02 : -0.12, metal, 'mag');
    if (def.mode === 'pump') box(0.05, 0.05, 0.14, 0, -0.02, -0.4, wood, 'pump');
    if (def.type === 'pistol') box(0.042, 0.03, len * 0.9, 0, 0.05, -len / 2 + 0.08, metal, 'slide');
    if (def.mode === 'break') box(0.05, 0.05, len * 0.85, 0, 0.02, -len / 2, metal, 'barrels');
    if (def.type === 'revolver') {
      const crane = new THREE.Group(); crane.name = 'crane'; crane.position.set(0, 0.02, -0.02); weapon.add(crane);
      const cyl = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, 0.05, 10), metal);
      cyl.name = 'cylinder'; cyl.rotation.x = Math.PI / 2; crane.add(cyl);
    }
  }
  const mk = (name, x, y, z) => { const o = new THREE.Object3D(); o.name = name; o.position.set(x, y, z); weapon.add(o); return o; };
  mk('muzzle', 0, 0.02, -len + 0.06);
  mk('eject', 0.03, 0.04, -0.05);
  mk('aim', 0, 0.065, 0.02);
  const arm = (name, x, y, z, rx) => {
    const a = new THREE.Group(); a.name = name; a.position.set(x, y, z); weapon.add(a);
    const hand = new THREE.Mesh(new THREE.BoxGeometry(0.075, 0.09, 0.1), glove); a.add(hand);
    const fore = new THREE.Mesh(new THREE.CylinderGeometry(0.042, 0.05, 0.4, 12), sleeve);
    fore.rotation.x = Math.PI / 2 + rx; fore.position.set(0, -0.06, 0.2); a.add(fore);
    return a;
  };
  arm('arm_R', 0.01, -0.07, 0.06, 0.25);
  if (!pistol || def.type === 'raygun') arm('arm_L', -0.02, -0.04, pistol ? 0.02 : -0.3, 0.4);
  root.traverse(o => { if (o.isMesh) o.castShadow = false; });
  return { scene: root };
}

// ---------- muzzle flash ----------
//
// The canvas is pure white with an alpha falloff, so the *material colour* carries the whole hue.
// That lets one texture serve a warm 12-gauge fireball and the Ray Gun's green bloom.
const _flashTex = new Map();
function flashTexture(spikes, variant) {
  const key = `${spikes}:${variant}`;
  if (_flashTex.has(key)) return _flashTex.get(key);
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d');
  let seed = (spikes * 7919 + variant * 104729 + 17) >>> 0;
  const r = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
  const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,255,255,1)');
  gr.addColorStop(0.13, 'rgba(255,255,255,0.86)');
  gr.addColorStop(0.36, 'rgba(255,255,255,0.3)');
  gr.addColorStop(0.7, 'rgba(255,255,255,0.06)');
  gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  g.translate(64, 64);
  g.rotate(r() * TAU);
  for (let i = 0; i < spikes; i++) {
    g.rotate(TAU / Math.max(1, spikes) + (r() - 0.5) * 0.55);
    const len = 30 + r() * 30, w = 3.5 + r() * 6;
    const lg = g.createLinearGradient(0, 0, 0, -len);
    lg.addColorStop(0, 'rgba(255,255,255,0.9)');
    lg.addColorStop(0.45, 'rgba(255,255,255,0.32)');
    lg.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = lg;
    g.beginPath(); g.moveTo(-w, 0); g.lineTo(0, -len); g.lineTo(w, 0); g.fill();
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  _flashTex.set(key, tex);
  return tex;
}

const _flashMat = new Map();
function flashMaterial(spikes, variant) {
  const key = `${spikes}:${variant}`;
  if (_flashMat.has(key)) return _flashMat.get(key);
  const mat = new THREE.MeshBasicMaterial({
    map: flashTexture(spikes, variant), transparent: true, blending: THREE.AdditiveBlending,
    depthWrite: false, color: new THREE.Color(1.6, 1.3, 0.9), side: THREE.DoubleSide, toneMapped: false,
  });
  _flashMat.set(key, mat);
  return mat;
}

const DEFAULT_FLASH = { scale: 0.11, color: 0xffcb8c, spikes: 4, sideLen: 0.7 };

function buildFlash() {
  const grp = new THREE.Group();
  const mat = flashMaterial(4, 0);
  const front = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mat);
  front.name = 'flash_front';
  // side cards lie in the XZ / YZ planes so the flash reads as a cone down the barrel
  const side1 = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mat);
  side1.name = 'flash_side1'; side1.rotation.x = Math.PI / 2;
  const side2 = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mat);
  side2.name = 'flash_side2'; side2.rotation.x = Math.PI / 2; side2.rotation.y = Math.PI / 2;
  grp.add(front, side1, side2);
  grp.visible = false;
  grp.renderOrder = 50;
  return { group: grp, material: mat, front, side1, side2 };
}

export class Viewmodel {
  constructor(vmScene, vmCamera) {
    this.scene = vmScene;
    this.camera = vmCamera;
    this.models = new Map();
    this.current = null;
    this.overlay = null;
    this.holder = new THREE.Group();
    vmScene.add(this.holder);
    // lighting that matches the world orientation
    this.hemi = new THREE.HemisphereLight(0xb8a0a0, 0x3a2a20, 0.9);
    this.sun = new THREE.DirectionalLight(0xffa060, 1.5);
    this.fill = new THREE.PointLight(0xffa060, 0, 3, 2);
    // short range + quadratic decay: the flash lights the gun, never bleaches the whole viewmodel
    this.flashLight = new THREE.PointLight(0xffb060, 0, 1.2, 2);
    // rim light so the gun separates from dark backgrounds
    this.rim = new THREE.DirectionalLight(0x9fc0ff, 0.8);
    this.rim.position.set(-0.6, 0.4, 0.8);
    vmScene.add(this.hemi, this.sun, this.sun.target, this.fill, this.flashLight, this.rim, this.rim.target);
    const f = buildFlash();
    this.flash = f.group;
    this.flashMat = f.material;
    this.flashParts = f;
    this.holder.add(this.flash);
    this.flashTime = 0;
    this.flashDur = 0.032;
    this.flashAfter = 0;
    this.flashPeak = 1.1;
    this.flashFwd = 0;
    this._flashSpin = 0;
    this.sunVis = 1;

    // Ejected brass / hulls. Parented to `holder` (identity transform, same space as the weapon)
    // so they disappear along with the viewmodel during cutscene cameras.
    this.shells = new ShellSystem(this.holder);

    // animation state
    this.ads = 0;
    this.sprint = 0;
    this.kick = 0; this.kickV = 0;          // recoil spring (back/up)
    this.kickRot = 0; this.kickRotV = 0;    // muzzle rise
    this.kickSide = 0; this.kickSideV = 0;  // lateral
    this.swayX = 0; this.swayY = 0;
    this.lower = 0;         // 0 = raised, 1 = fully lowered (switch)
    this.reloadT = -1;      // 0..1 during reload
    this.reloadClass = 'rifle';
    this.reloadKind = 'mag';   // legacy alias
    this.reloadEmpty = false;
    this.shellT = -1;       // 0..1 progress of a single shell being pushed into a tube mag
    this.pumpT = -1;
    this.knifeT = -1;
    this.throwT = -1;
    this.drinkT = -1;
    this.inspectT = -1;
    this.slideT = 99;       // seconds since the action started cycling
    this.slideDur = 0.045;
    this.rackOverride = 0;
    this.cylAngle = 0; this.cylTarget = 0;
    this.charge = 0;        // ray gun capacitor glow
    this.stepDip = 0; this._stepIdx = 0;
    this.lag = new THREE.Vector3(); this.lagV = new THREE.Vector3(); this._hasLag = false;
    this.time = 0;
  }

  async load(id) {
    if (this.models.has(id)) return this.models.get(id);
    let gltf = await loadGLB(`/models/weapons/${id}.glb`);
    const real = !!gltf;
    if (!gltf) gltf = placeholderViewmodel(id);
    const root = gltf.scene;
    const weapon = findNode(root, 'weapon') || root;
    const get = n => findNode(root, n);
    const def = WEAPONS[id] || {};
    const entry = {
      id, real, root, weapon, def, cls: reloadClassOf(def),
      aim: get('aim'), muzzle: get('muzzle'), eject: get('eject'),
      armL: get('arm_L'), armR: get('arm_R'),
      mag: get('mag'), pump: get('pump'), slide: get('slide'), bolt: get('bolt'), cylinder: get('cylinder'),
      barrels: get('barrels'), crane: get('crane'), action: get('action'),
      gunMeshes: [], glowMats: [], originalMats: new Map(), papMats: new Map(),
      magClone: null,
    };
    root.traverse(o => {
      if (!o.isMesh) return;
      o.castShadow = false; o.receiveShadow = false;
      o.frustumCulled = false;
      // gun meshes = anything not under an arm
      let p = o, isArm = false;
      while (p && p !== root) { const nm = nodeName(p); if (nm === 'arm_L' || nm === 'arm_R') { isArm = true; break; } p = p.parent; }
      const mats = Array.isArray(o.material) ? o.material : [o.material];
      mats.forEach(m => {
        if (!m) return;
        if ('envMapIntensity' in m) m.envMapIntensity = 0.9;
        if ((m.name || '').includes('glow') && m.emissive && !entry.glowMats.some(g => g.mat === m)) {
          entry.glowMats.push({ mat: m, base: m.emissiveIntensity ?? 1 });
        }
      });
      if (!isArm) entry.gunMeshes.push(o);
    });
    // rest transforms
    root.updateMatrixWorld(true);
    entry.rest = new Map();
    for (const k of ['weapon', 'armL', 'armR', 'mag', 'pump', 'slide', 'bolt', 'cylinder', 'barrels', 'crane', 'action']) {
      const o = entry[k];
      if (o) entry.rest.set(k, { p: o.position.clone(), q: o.quaternion.clone() });
    }
    // aim point in weapon-local space
    entry.aimLocal = new THREE.Vector3();
    if (entry.aim && entry.aim !== weapon) {
      entry.aimLocal.copy(entry.aim.getWorldPosition(new THREE.Vector3()));
      weapon.worldToLocal(entry.aimLocal);
    } else entry.aimLocal.set(0, 0.06, 0);
    entry.muzzleLocal = new THREE.Vector3();
    if (entry.muzzle) { entry.muzzle.getWorldPosition(entry.muzzleLocal); weapon.worldToLocal(entry.muzzleLocal); }
    else entry.muzzleLocal.set(0, 0.02, -0.5);
    entry.ejectLocal = new THREE.Vector3();
    if (entry.eject) { entry.eject.getWorldPosition(entry.ejectLocal); weapon.worldToLocal(entry.ejectLocal); }
    else entry.ejectLocal.set(0.03, 0.04, -0.05);
    entry.weaponRestZ = entry.rest.get('weapon').p.z;
    root.visible = false;
    this.holder.add(root);
    this.models.set(id, entry);
    return entry;
  }

  setPap(entry, on) {
    for (const mesh of entry.gunMeshes) {
      if (!entry.originalMats.has(mesh)) entry.originalMats.set(mesh, mesh.material);
      const orig = entry.originalMats.get(mesh);
      if (on) {
        const isGlow = (Array.isArray(orig) ? orig : [orig]).some(m => (m?.name || '').includes('glow') || (m?.name || '').includes('bottle'));
        if (isGlow) continue;
        if (!entry.papMats.has(mesh)) entry.papMats.set(mesh, Array.isArray(orig) ? orig.map(makePapMaterial) : makePapMaterial(orig));
        mesh.material = entry.papMats.get(mesh);
      } else mesh.material = orig;
    }
  }

  show(id, pap = false) {
    const entry = this.models.get(id);
    if (this.current) this.current.root.visible = false;
    this.current = entry || null;
    this.reloadT = -1;
    this.shellT = -1;
    this.slideT = 99;
    this.rackOverride = 0;
    this.cylAngle = this.cylTarget = 0;
    this.charge = 0;
    this._hasLag = false;
    if (!entry) return;
    entry.root.visible = true;
    this.setPap(entry, pap);
    this._resetParts(entry);
  }

  setOverlay(id) {
    if (this.overlay) this.overlay.root.visible = false;
    this.overlay = id ? this.models.get(id) || null : null;
    if (this.overlay) { this.overlay.root.visible = true; this._resetParts(this.overlay); }
  }

  _resetParts(e) {
    for (const [k, r] of e.rest) { e[k].position.copy(r.p); e[k].quaternion.copy(r.q); }
    if (e.mag) e.mag.visible = true;
    if (e.magClone) e.magClone.visible = false;
  }

  // ---------------------------------------------------------------- firing

  /**
   * @param {object|number} opts  { strength, pattern:[pitchMul,yawMul], flash:<def.flash|false>,
   *                                kickScale, boltDur, cycle:boolean, ads:0..1 }
   *                              (slide/bolt *travel* comes from the weapon def, not from here)
   *                              (a bare number is read as `strength`, for older call sites)
   */
  fire(opts = {}, legacyFlash) {
    if (typeof opts === 'number') opts = { strength: opts, flash: legacyFlash === false ? false : undefined };
    const strength = opts.strength ?? 1;
    const pat = opts.pattern || [1, 0];
    const kickScale = opts.kickScale ?? 1;
    // inject *velocity* into the springs — the pose then overshoots and settles instead of
    // teleporting to an offset and easing back.
    this.kickV += 9 * strength * kickScale;
    this.kickRotV += 11 * strength * kickScale * (pat[0] ?? 1);
    this.kickSideV += 8 * strength * kickScale * (pat[1] ?? 0);

    if (opts.flash !== false) this._setupFlash(opts.flash || DEFAULT_FLASH, opts.ads ?? this.ads);
    if (opts.cycle !== false) {
      this.slideT = 0;
      this.slideDur = opts.boltDur ?? 0.045;
    }
    // revolvers index one chamber per shot
    if (this.current?.cylinder && this.current.cls === 'revolver') this.cylTarget += TAU / Math.max(1, this.current.def.mag || 6);
  }

  _setupFlash(fdef, ads) {
    const spikes = Math.max(0, fdef.spikes ?? 4);
    const variant = (Math.random() * 3) | 0;
    const mat = flashMaterial(spikes, variant);
    const col = new THREE.Color(fdef.color ?? 0xffcb8c);
    // normalise the hue then push it just over the bloom threshold — no more, or the gun bleaches
    const mx = Math.max(col.r, col.g, col.b) || 1;
    const hdr = fdef.hdr ?? (fdef.afterglow ? 1.8 : 1.55);
    mat.color.setRGB(col.r / mx * hdr, col.g / mx * hdr, col.b / mx * hdr);
    mat.opacity = 1;
    this.flashMat = mat;
    const { front, side1, side2 } = this.flashParts;
    front.material = side1.material = side2.material = mat;

    const adsK = ads > 0.5 ? 0.55 : 1;                    // halve it when aiming
    const s = (fdef.scale ?? 0.11) * (0.86 + Math.random() * 0.28) * adsK;
    const wide = fdef.wide ?? 1;
    this._flashSpin = Math.random() * Math.PI;
    this.flash.scale.set(s * wide, s * (0.8 + Math.random() * 0.45), s);
    const L = fdef.sideLen ?? 0.7;
    side1.scale.set(0.62 * wide, L * 1.7, 1);
    side1.position.z = -L * 0.8;
    side2.scale.copy(side1.scale);
    side2.position.z = side1.position.z;
    front.position.z = 0;
    // shift forward when aiming so it does not wash out the rear sight
    this.flashFwd = 0.02 + (ads > 0.5 ? 0.05 : 0) + (fdef.sideLen ?? 0.7) * s * 0.4;
    this.flashDur = 0.032 + (fdef.afterglow ?? 0);
    this.flashAfter = fdef.afterglow ?? 0;
    this.flashTime = this.flashDur;
    this.flashPeak = clamp(1.1 * ((fdef.scale ?? 0.11) / 0.11), 0.55, 1.9);
    this.flashLight.color.copy(col);
    if (fdef.afterglow) this.charge = Math.max(this.charge, 1);
  }

  /** Throw a case out of the `eject` locator. kind: 'brass' | 'shotshell' */
  ejectShell(kind, scale = 1, boost = 1) {
    const e = this.current;
    if (!e || !kind || kind === 'none') return;
    e.root.updateMatrixWorld(true);
    _ejPos.copy(e.ejectLocal).applyMatrix4(e.weapon.matrixWorld);
    e.weapon.getWorldQuaternion(_q1);
    const right = _t1.set(1, 0, 0).applyQuaternion(_q1);
    const up = _t2.set(0, 1, 0).applyQuaternion(_q1);
    const fwd = _t3.set(0, 0, -1).applyQuaternion(_q1);
    _ejVel.set(0, 0, 0)
      .addScaledVector(right, (1.3 + (Math.random() - 0.5) * 0.6) * boost)
      .addScaledVector(up, (0.9 + (Math.random() - 0.5) * 0.6) * boost)
      .addScaledVector(fwd, -(0.2 + Math.random() * 0.25) * boost);
    this.shells.spawn(kind, _ejPos, _ejVel, null, scale);
  }

  /** Start the 1.6 s inspect flourish. */
  inspect() { if (this.inspectT < 0 && this.reloadT < 0) this.inspectT = 0; }

  // world-space-ish muzzle position mapped into the world camera frame (for tracers / flash light)
  muzzleInCamera(out) {
    const e = this.current;
    if (!e) return out.set(0.12, -0.1, -0.6);
    return out.copy(e.muzzleLocal).applyMatrix4(e.weapon.matrixWorld);
  }

  ejectInCamera(out) {
    const e = this.current;
    if (!e) return out.set(0.15, -0.05, -0.4);
    return out.copy(e.ejectLocal).applyMatrix4(e.weapon.matrixWorld);
  }

  // ---------------------------------------------------------------- per frame

  update(dt, s, worldCamera, collision) {
    this.time += dt;
    const e = this.current;
    const dtc = Math.min(dt, 1 / 30);
    const k = (v, target, speed) => v + (target - v) * Math.min(1, dt * speed);

    // ADS speed is per weapon (adsTime seconds hip -> aimed)
    const adsTime = s.adsTime || e?.def?.adsTime || 0.2;
    const adsRate = s.adsSpeed || 2.4 / Math.max(0.05, adsTime);
    this.ads = k(this.ads, s.ads ? 1 : 0, adsRate);
    // sprint eases in slowly (~0.2 s, you have to commit) and drops out over ~0.12 s so the gun is
    // back on target almost as soon as the key is released
    this.sprint = k(this.sprint, s.sprint ? 1 : 0, s.sprint ? 5.2 : 8.3);

    // recoil springs — underdamped so the gun overshoots past rest and settles
    this.kickV = springV(this.kick, this.kickV, 220, 0.55, dtc);
    this.kick = clamp(this.kick + this.kickV * dtc, -1.2, 1.8);
    this.kickRotV = springV(this.kickRot, this.kickRotV, 185, 0.5, dtc);
    this.kickRot = clamp(this.kickRot + this.kickRotV * dtc, -1.6, 2.2);
    this.kickSideV = springV(this.kickSide, this.kickSideV, 150, 0.62, dtc);
    this.kickSide = clamp(this.kickSide + this.kickSideV * dtc, -1.4, 1.4);

    // frame-rate independent sway: mouse delta is per frame, so normalise by dt
    const inv = 1 / Math.max(dt, 1e-3);
    this.swayX = k(this.swayX, clamp(-(s.mouseDx || 0) * inv * 1.5e-5, -0.06, 0.06), 9);
    this.swayY = k(this.swayY, clamp(-(s.mouseDy || 0) * inv * 1.5e-5, -0.05, 0.05), 9);

    // action cycle timer (fixed duration, not a rate — so it reads the same at any RPM)
    this.slideT += dt;

    // footstep dip impulse (walking should read as steps, not a hum)
    const stepIdx = Math.floor((s.bobTime || 0) / Math.PI);
    if (stepIdx !== this._stepIdx) {
      this._stepIdx = stepIdx;
      if ((s.move || 0) > 0.2) this.stepDip = 1;
    }
    this.stepDip = Math.max(0, this.stepDip - dt * 7);

    // inspect
    if (this.inspectT >= 0) { this.inspectT += dt / 1.6; if (this.inspectT >= 1) this.inspectT = -1; }

    // ray gun capacitor glow decays after each shot / charges during the reload
    this.charge = Math.max(0, this.charge - dt * 3.2);

    // the viewmodel camera *widens* when aiming: the gun shrinks in frame, the sight picture opens
    if (this.camera && this.camera.isPerspectiveCamera) {
      const fov = VM_FOV.hip + (VM_FOV.ads - VM_FOV.hip) * this.ads;
      if (Math.abs(this.camera.fov - fov) > 1e-4) { this.camera.fov = fov; this.camera.updateProjectionMatrix(); }
    }

    // lighting follows the world sun, shadowed when the sun is blocked
    const invQ = worldCamera.quaternion.clone().invert();
    const sunLocal = SUN_DIR.clone().applyQuaternion(invQ);
    this.sun.position.copy(sunLocal).multiplyScalar(5);
    if (collision && Math.random() < 0.25) {
      const hit = collision.raycast(worldCamera.position, SUN_DIR, 80, { doors: true, barriers: false });
      this._sunTarget = hit ? 0.12 : 1;
    }
    this.sunVis = k(this.sunVis, this._sunTarget ?? 1, 3);
    this.sun.intensity = 1.5 * this.sunVis;
    this.hemi.intensity = 0.55 + 0.35 * this.sunVis + (s.ambientBoost || 0);
    this.rim.intensity = 0.55 + 0.35 * this.sunVis;

    // flash: short, quadratic decay, low peak
    this.flashTime = Math.max(0, this.flashTime - dt);
    const fl = this.flashDur > 0 ? this.flashTime / this.flashDur : 0;
    this.flash.visible = this.flashTime > 0 && !!e;
    this.flashLight.intensity = fl * fl * this.flashPeak;
    if (this.flash.visible && this.flashAfter > 0) {
      this.flashMat.opacity = Math.pow(fl, 0.65);
      // the afterglow (Ray Gun) shrinks and fades instead of blinking out
      this.flashParts.front.scale.setScalar(0.55 + 0.45 * fl);
    } else if (this.flash.visible) {
      this.flashMat.opacity = 1;
      this.flashParts.front.scale.setScalar(1);
    }

    if (e) this._animateWeapon(e, dt, s);
    if (this.overlay) this._animateOverlay(this.overlay, dt, s);
    if (e && this.flash.visible) {
      e.root.updateMatrixWorld(true);
      const mp = _t4.copy(e.muzzleLocal).applyMatrix4(e.weapon.matrixWorld);
      e.weapon.getWorldQuaternion(_q1);
      _t1.set(0, 0, -1).applyQuaternion(_q1).multiplyScalar(this.flashFwd);
      this.flash.position.copy(mp).add(_t1);
      this.flashLight.position.copy(mp);
      this.flash.quaternion.copy(_q1);
      this.flash.rotateZ(this._flashSpin ?? 0);
    }

    this.shells.update(dt, worldCamera);
  }

  _resetAnimParts(e) {
    for (const k of ['armL', 'armR', 'mag', 'pump', 'slide', 'bolt', 'cylinder', 'barrels', 'crane', 'action']) {
      const o = e[k], r = e.rest.get(k);
      if (o && r) { o.position.copy(r.p); o.quaternion.copy(r.q); }
    }
    if (e.mag) e.mag.visible = true;
    if (e.magClone) e.magClone.visible = false;
  }

  /** A spare magazine in the left hand during the grab->insert window. */
  _magInHand(e, show, t) {
    if (!e.mag || !e.armL) return;
    if (!e.magClone) {
      const c = e.mag.clone(true);
      c.name = 'mag_spare';
      c.traverse(o => { if (o.isMesh) { o.castShadow = false; o.frustumCulled = false; } });
      c.position.set(-0.01, -0.05, 0.03);
      c.visible = false;
      c.userData.baseQ = e.mag.quaternion.clone();   // keep the part's authored orientation (RPD drum)
      e.armL.add(c);
      e.magClone = c;
    }
    e.magClone.visible = show;
    if (show) {
      _handTilt.setFromEuler(_handEuler.set(0.35 * (1 - t), 0, 0.2 * (1 - t)));
      e.magClone.quaternion.copy(e.magClone.userData.baseQ).premultiply(_handTilt);
      e.magClone.position.set(-0.01, -0.05 - 0.02 * (1 - t), 0.03);
    }
  }

  _animateWeapon(e, dt, s) {
    const rest = e.rest.get('weapon');
    const def = e.def || {};
    const w = e.weapon;
    const ads = ease(this.ads) * (1 - this.sprint);
    const t = this.time;
    this._resetAnimParts(e);
    this.rackOverride = 0;

    // ---- base pose: rest -> ADS. The aim node is anchored at a fixed distance from the eye,
    // so the receiver never fills the frame regardless of where the artist put the weapon origin.
    const o = { p: _p.copy(rest.p), rx: 0, ry: 0, rz: 0 };
    const D = def.adsDist ?? 0.32;
    _adsT.set(-e.aimLocal.x, -e.aimLocal.y, -(D + e.aimLocal.z));
    o.p.lerp(_adsT, ads);

    // hip-fire cant: barrel angled in toward the crosshair (removed when aiming)
    o.ry += 0.075 * (1 - ads);
    o.rx += 0.02 * (1 - ads);
    o.rz -= 0.035 * (1 - ads);

    // ---- movement bob (Lissajous: x = sin t, y = sin 2t) + footstep dip + idle breathing
    const bobAmp = 1 - ads * 0.85;
    const mv = (s.move || 0) * bobAmp;
    const bt = s.bobTime || 0;
    o.p.x += Math.sin(bt) * 0.013 * mv * (1 + this.sprint);
    o.p.y += Math.sin(bt * 2) * 0.009 * mv * (1 + this.sprint * 1.2);
    o.rz += Math.sin(bt) * 0.016 * mv;
    o.ry += Math.sin(bt * 2 + 0.7) * 0.008 * mv;
    o.p.y -= this.stepDip * this.stepDip * 0.007 * mv;
    o.rx += this.stepDip * this.stepDip * 0.022 * mv;
    // breathing: two rates so it never reads as a single hum
    const idle = (1 - Math.min(1, mv * 2)) * bobAmp;
    o.p.y += (Math.sin(t * 1.45) * 0.0022 + Math.sin(t * 0.61) * 0.0011) * idle;
    o.p.x += Math.sin(t * 0.83 + 1.3) * 0.0016 * idle;
    o.rx += Math.sin(t * 1.45 + 0.9) * 0.0045 * idle;
    o.ry += Math.sin(t * 0.67) * 0.0035 * idle;

    // ---- sway
    o.ry += this.swayX * (1 - ads * 0.6);
    o.rx += this.swayY * (1 - ads * 0.6);
    o.p.x += this.swayX * 0.04 * (1 - ads);
    o.p.y -= this.swayY * 0.03 * (1 - ads);

    // ---- sprint: a real 2 Hz swing, not a static pose
    const sp = ease(this.sprint);
    if (sp > 0.001) {
      // the swing rides at ~3x the walk-bob amplitude (walk is 0.013 on x / 0.009 on y) with a
      // counter-rotation, so a sprint reads as the gun being hauled along rather than a held pose
      const sw = Math.sin(bt), sw2 = Math.cos(bt * 2);
      o.p.x += sp * (0.03 + sw * 0.040);
      o.p.y -= sp * (0.05 + Math.abs(sw2) * 0.027);
      o.p.z += sp * (0.02 + sw2 * 0.019);
      o.rx += sp * (-0.26 + sw2 * 0.11);
      o.ry += sp * (0.58 - sw * 0.17);
      o.rz += sp * (0.36 + sw * 0.13);
    }

    // ---- recoil rotation (springs computed in update()); the *translation* is applied after the
    // weight spring below so the kick keeps its snap instead of being smoothed away.
    // kickSide > 0 means the muzzle walks to the *right*, so the yaw/roll terms are negative
    o.rx += this.kickRot * 0.05 * (1 - ads * 0.5);
    o.ry -= this.kickSide * 0.035 * (1 - ads * 0.6);
    o.rz -= this.kickSide * 0.05 * (1 - ads * 0.6);

    // ---- lower for switching / hidden
    const low = ease(clamp01(this.lower));
    o.p.y -= low * 0.35; o.rx -= low * 0.7;
    o.p.y -= (s.landDip || 0) * 0.3;
    o.rx += (s.landDip || 0) * 0.35;

    // ---- inspect flourish
    if (this.inspectT >= 0) {
      const it = clamp01(this.inspectT);
      const inK = ease(seg(it, 0, 0.3)) * (1 - ease(seg(it, 0.7, 1)));
      o.p.x -= inK * 0.05; o.p.y -= inK * 0.025; o.p.z += inK * 0.09;
      o.ry += inK * 0.95; o.rz += inK * 0.5; o.rx += inK * 0.18;
      o.rx += Math.sin(it * 7.5) * 0.03 * inK;
    }

    // ---- reload choreography
    if (this.reloadT >= 0) this._reloadPose(e, o, dt);

    // ---- pump action
    if (e.pump) {
      const pr = e.rest.get('pump');
      e.pump.position.copy(pr.p);
      if (this.pumpT >= 0) {
        const b = Math.sin(clamp01(this.pumpT) * Math.PI);
        e.pump.position.z += b * 0.09;
        if (e.armL) e.armL.position.z += b * 0.09;
        o.rx += b * 0.06; o.p.z += b * 0.01;
      }
    }

    // ---- reciprocating mass: slide / bolt carrier
    const cyc = Math.max(this._boltCycle(), this.rackOverride);
    const travel = def.boltTravel ?? 0.05;
    if (e.slide) {
      const sr = e.rest.get('slide');
      e.slide.position.copy(sr.p);
      e.slide.position.z += cyc * travel + (s.empty && this.reloadT < 0 ? travel * 0.85 : 0);
    }
    if (e.bolt) {
      const br = e.rest.get('bolt');
      e.bolt.position.copy(br.p);
      e.bolt.position.z += cyc * travel;
    }
    // ---- revolver cylinder: absolute angle from rest, never an accumulating rotateZ
    if (e.cylinder) {
      this.cylAngle += (this.cylTarget - this.cylAngle) * Math.min(1, dt * 22);
      if (this.cylAngle > TAU && this.cylTarget > TAU) { this.cylAngle -= TAU; this.cylTarget -= TAU; }
      const cr = e.rest.get('cylinder');
      if (cr) { e.cylinder.position.copy(cr.p); e.cylinder.quaternion.copy(cr.q); }
      e.cylinder.rotateZ(this.cylAngle);
    }

    // ---- right hand follows the gun's recoil instead of being welded to the grip
    if (e.armR) {
      e.armR.position.z += this.kick * 0.012;
      e.armR.position.y += this.kick * 0.003;
      e.armR.rotateX(this.kickRot * 0.02);
    }
    if (e.armL) {
      e.armL.position.z += this.kick * 0.006;
      e.armL.rotateX(this.kickRot * 0.01);
    }

    // ---- melee bash with the gun if no knife model is available
    if (this.knifeT >= 0 && !this.overlay) {
      const kk = Math.sin(clamp01(this.knifeT) * Math.PI);
      o.ry -= kk * 0.6; o.p.x -= kk * 0.08; o.p.z -= kk * 0.1; o.rz += kk * 0.4;
    }
    // hide the gun while an overlay (knife/frag/drink) is up
    o.p.y -= (this.overlay ? 1 : 0) * 0.4;

    // ---- ray gun glow: brighter right after a shot and while the reload charges
    if (e.glowMats.length) {
      const g = clamp01(this.charge);
      for (const gm of e.glowMats) gm.mat.emissiveIntensity = gm.base * (1 + g * 1.6);
    }

    // ---- weight: the gun lags the target pose slightly and overshoots when it stops moving.
    // Faded out at full ADS so the sight picture stays rock solid.
    _lagTarget.copy(o.p);
    if (!this._hasLag) { this.lag.copy(_lagTarget); this.lagV.set(0, 0, 0); this._hasLag = true; }
    const dtc = Math.min(dt, 1 / 45);
    const K = 300, Z = 0.62, C = 2 * Math.sqrt(K) * Z;
    this.lagV.x += (-K * (this.lag.x - _lagTarget.x) - C * this.lagV.x) * dtc;
    this.lagV.y += (-K * (this.lag.y - _lagTarget.y) - C * this.lagV.y) * dtc;
    this.lagV.z += (-K * (this.lag.z - _lagTarget.z) - C * this.lagV.z) * dtc;
    this.lag.addScaledVector(this.lagV, dtc);
    if (!Number.isFinite(this.lag.x + this.lag.y + this.lag.z)) { this.lag.copy(_lagTarget); this.lagV.set(0, 0, 0); }
    const lagMix = 0.45 * (1 - ads);
    o.p.lerp(this.lag, lagMix);

    // recoil translation, after the lag so it stays sharp
    o.p.z += this.kick * 0.045 * (1 - ads * 0.45);
    o.p.y += this.kick * 0.006;
    o.p.x += this.kickSide * 0.012 * (1 - ads * 0.5);

    w.position.copy(o.p);
    w.quaternion.copy(rest.q).slerp(_identity, ads);
    w.rotateX(o.rx); w.rotateY(o.ry); w.rotateZ(o.rz);
  }

  _boltCycle() {
    if (this.slideT >= this.slideDur) return 0;
    return Math.sin(clamp01(this.slideT / this.slideDur) * Math.PI);
  }

  // ---------------------------------------------------------------- reloads

  _reloadPose(e, o, dt) {
    const r = clamp01(this.reloadT);
    const cls = this.reloadClass || reloadClassOf(e.def) || 'rifle';
    const tilt = ease(seg(r, 0, 0.12)) * (1 - ease(seg(r, 0.88, 1)));
    switch (cls) {
      case 'pistol': this._reloadMag(e, o, r, tilt, { pistol: true, rack: 0.84 }); break;
      case 'smg': this._reloadMag(e, o, r, tilt, { rock: !!e.def.magRock, rack: 0.82 }); break;
      case 'rifle': this._reloadMag(e, o, r, tilt, { rock: !!e.def.magRock, rack: 0.84 }); break;
      case 'lmg': this._reloadLmg(e, o, r, tilt); break;
      case 'break': this._reloadBreak(e, o, r, tilt); break;
      case 'revolver': this._reloadRevolver(e, o, r, tilt, dt); break;
      case 'shotgun': this._reloadShotgun(e, o, r, tilt); break;
      case 'raygun': this._reloadRaygun(e, o, r, tilt); break;
      default: this._reloadMag(e, o, r, tilt, { rack: 0.84 });
    }
  }

  /** Box-magazine reload: pistol / SMG / rifle, with an AK-style rock-in when `rock`. */
  _reloadMag(e, o, r, tilt, opt) {
    const armL = e.armL, armR = e.armR;
    const armLRest = e.rest.get('armL');
    // canting the gun over so the magwell faces the camera is what sells a reload
    o.rz += tilt * (opt.pistol ? 0.55 : 0.42);
    o.rx += tilt * 0.16;
    o.ry += tilt * (opt.pistol ? 0.2 : 0.12);
    o.p.x -= tilt * 0.035; o.p.y -= tilt * 0.022; o.p.z += tilt * 0.02;

    const magOut = ease(seg(r, 0.14, 0.30));
    const magIn = ease(seg(r, 0.50, 0.64));

    if (e.mag) {
      const mr = e.rest.get('mag');
      const d = magOut * (1 - magIn);
      e.mag.position.set(mr.p.x, mr.p.y - d * 0.34, mr.p.z + d * 0.06);
      e.mag.visible = d < 0.9;
      if (opt.rock && magIn > 0 && magIn < 1) e.mag.rotateX(-(1 - magIn) * 0.45);
      else if (magIn > 0 && magIn < 1) e.mag.rotateZ((1 - magIn) * 0.12);
    }

    if (armL) {
      const down = ease(seg(r, 0.12, 0.30));
      const away = ease(seg(r, 0.30, 0.44)) * (1 - ease(seg(r, 0.46, 0.60)));
      const ret = ease(seg(r, 0.66, 0.86));
      const magP = e.mag ? e.rest.get('mag').p : _t1.set(0, -0.1, 0);
      _t2.copy(magP).sub(armLRest.p).add(_t3.set(-0.02, -0.06, 0.02));
      const f = down * (1 - ret);
      armL.position.addScaledVector(_t2, f);
      armL.position.y -= away * 0.26;
      armL.position.z += away * 0.05;
      armL.rotateX(-f * 0.35);
      armL.rotateZ(away * 0.4);
      // fresh magazine visible in the hand on the way back up
      this._magInHand(e, r > 0.42 && r < 0.66, seg(r, 0.42, 0.62));
    }

    // palm slap that seats the magazine — the gun takes a short downward hit
    const seat = pulse(r, 0.62, 0.72);
    o.p.y -= seat * 0.016; o.rx += seat * 0.06; o.p.z += seat * 0.006;

    // run the action when the mag came up empty
    if (this.reloadEmpty) {
      const at = opt.rack ?? 0.83;
      const b = pulse(r, at - 0.07, at + 0.09);
      this.rackOverride = Math.max(this.rackOverride, b);
      o.rz -= b * 0.1; o.rx += b * 0.05; o.p.z += b * 0.012;
      const hand = opt.pistol ? armL : armR;   // the pistol's slide is worked by the support hand
      if (hand) { hand.position.z += b * 0.05; hand.position.y += b * 0.02; hand.position.x -= b * 0.012; }
    }
  }

  /** RPD: top cover up, old belt out, new belt laid in, cover slammed, bolt run. */
  _reloadLmg(e, o, r, tilt) {
    const armL = e.armL, armR = e.armR;
    o.rz += tilt * 0.3; o.rx += tilt * 0.34;
    o.p.y -= tilt * 0.045; o.p.z += tilt * 0.05; o.p.x -= tilt * 0.02;

    const open = ease(seg(r, 0.02, 0.18)) * (1 - ease(seg(r, 0.78, 0.9)));
    // no `cover` node in the contract — the open receiver reads through the gun's attitude
    o.rx += open * 0.16;

    if (e.mag) {
      const mr = e.rest.get('mag');
      const d = ease(seg(r, 0.14, 0.3)) * (1 - ease(seg(r, 0.5, 0.68)));
      e.mag.position.set(mr.p.x, mr.p.y - d * 0.3, mr.p.z + d * 0.08);
      e.mag.visible = d < 0.9;
    }
    if (armL) {
      const up = ease(seg(r, 0.02, 0.2)) * (1 - ease(seg(r, 0.26, 0.4)));
      const away = ease(seg(r, 0.3, 0.46)) * (1 - ease(seg(r, 0.5, 0.62)));
      const lay = ease(seg(r, 0.52, 0.7)) * (1 - ease(seg(r, 0.78, 0.94)));
      armL.position.y += up * 0.1 - away * 0.28 + lay * 0.06;
      armL.position.z += up * 0.05 + away * 0.05 + lay * 0.1;
      armL.position.x -= (up + lay) * 0.02;
      armL.rotateX(-(up + lay) * 0.3);
      this._magInHand(e, r > 0.46 && r < 0.7, seg(r, 0.46, 0.66));
    }
    // cover slam
    const slam = pulse(r, 0.76, 0.86);
    o.p.y -= slam * 0.018; o.rx += slam * 0.07;
    // charging handle
    const b = pulse(r, 0.86, 0.97);
    this.rackOverride = Math.max(this.rackOverride, b);
    if (armR) { armR.position.z += b * 0.05; armR.position.x -= b * 0.012; }
  }

  /** Olympia: break the barrels on the hinge pin, hulls out, two fresh shells, snap closed. */
  _reloadBreak(e, o, r, tilt) {
    const armL = e.armL;
    const open = ease(seg(r, 0.18, 0.34)) * (1 - ease(seg(r, 0.74, 0.88)));
    o.rx += tilt * 0.3 + open * 0.2;
    o.rz += tilt * 0.22;
    o.p.y -= tilt * 0.03; o.p.x -= tilt * 0.02;
    if (e.barrels) {
      // `barrels` origin is on the hinge pin: rotate about local X to break it open
      e.barrels.rotateX(-open * 0.66);
    } else {
      o.rx += open * 0.34;      // graceful fallback: tip the whole gun
    }
    if (armL) {
      const pull = pulse(r, 0.28, 0.48);
      const load = pulse(r, 0.48, 0.72);
      armL.position.y -= pull * 0.14 + load * 0.1;
      armL.position.z += pull * 0.11 + load * 0.09;
      armL.position.x -= load * 0.02;
      armL.rotateX(-(pull + load) * 0.25);
    }
    // snap shut — a real break-action closes with a wrist flick
    const close = pulse(r, 0.74, 0.9);
    o.rx -= close * 0.18; o.p.y -= close * 0.014; o.rz += close * 0.06;
  }

  /** Python: crane swings the cylinder out, ejector rod, speed-load, flick closed. */
  _reloadRevolver(e, o, r, tilt, dt) {
    const armL = e.armL;
    const open = ease(seg(r, 0.06, 0.24)) * (1 - ease(seg(r, 0.78, 0.9)));
    o.rz += tilt * 0.72; o.rx += tilt * 0.26; o.p.x -= tilt * 0.05; o.p.y -= tilt * 0.02;
    if (e.crane) {
      // the crane's origin is the crane pivot; +Z swings the cylinder out of the frame
      e.crane.rotateZ(open * 1.15);
    } else if (e.cylinder) {
      e.cylinder.position.x -= open * 0.03;
    }
    // ejector rod push, then the cylinder free-spins a little
    const ej = pulse(r, 0.22, 0.38);
    if (ej > 0.01) this.cylTarget += dt * 9 * ej;
    o.p.z += ej * 0.012; o.rx -= ej * 0.05;
    if (armL) {
      const push = pulse(r, 0.2, 0.4);
      const load = pulse(r, 0.5, 0.78);
      armL.position.y -= push * 0.08 + load * 0.13;
      armL.position.z += push * 0.06 + load * 0.1;
      armL.rotateX(-(push + load) * 0.25);
      this._magInHand(e, r > 0.5 && r < 0.78, seg(r, 0.5, 0.74));
    }
    const shut = pulse(r, 0.78, 0.92);
    o.rz -= shut * 0.2; o.p.x += shut * 0.01;
  }

  /** 870: one shell at a time. `shellT` (0..1) is one insert cycle, driven by weapons.js. */
  _reloadShotgun(e, o, r, tilt) {
    const armL = e.armL;
    o.rz += tilt * 0.3; o.rx += tilt * 0.14;
    o.p.x -= tilt * 0.025; o.p.y -= tilt * 0.022;
    const c = clamp01(this.shellT >= 0 ? this.shellT : r);
    const reach = Math.sin(c * Math.PI);
    if (armL) {
      armL.position.y -= reach * 0.1;
      armL.position.z += reach * 0.09;
      armL.position.x -= reach * 0.02;
      armL.rotateX(-reach * 0.3);
    }
    const push = pulse(c, 0.55, 0.9);
    o.p.z += push * 0.009; o.rx += push * 0.035;
  }

  /** Ray Gun: cell out, cell in, capacitor spins up. */
  _reloadRaygun(e, o, r, tilt) {
    const armL = e.armL;
    o.rz += tilt * 0.4; o.rx += tilt * 0.22; o.p.x -= tilt * 0.03; o.p.y -= tilt * 0.02;
    if (e.mag) {
      const mr = e.rest.get('mag');
      const d = ease(seg(r, 0.18, 0.34)) * (1 - ease(seg(r, 0.55, 0.7)));
      e.mag.position.set(mr.p.x, mr.p.y - d * 0.28, mr.p.z + d * 0.05);
      e.mag.visible = d < 0.9;
    }
    if (armL) {
      const down = ease(seg(r, 0.14, 0.32)) * (1 - ease(seg(r, 0.62, 0.84)));
      const away = ease(seg(r, 0.34, 0.46)) * (1 - ease(seg(r, 0.5, 0.62)));
      armL.position.y -= down * 0.12 + away * 0.2;
      armL.position.z += down * 0.05;
      armL.rotateX(-down * 0.3);
      this._magInHand(e, r > 0.46 && r < 0.68, seg(r, 0.46, 0.66));
    }
    // capacitor spin-up: the glow ramps as the charge event lands
    this.charge = Math.max(this.charge, ease(seg(r, 0.7, 0.96)));
    const kick = pulse(r, 0.74, 0.96);
    o.p.z += kick * 0.01; o.rx -= kick * 0.04;
  }

  _animateOverlay(o, dt, s) {
    const rest = o.rest.get('weapon');
    const w = o.weapon;
    const p = rest.p.clone();
    let rx = 0, ry = 0, rz = 0;
    if (o.id === 'knife' && this.knifeT >= 0) {
      const t = clamp01(this.knifeT);
      const wind = ease(seg(t, 0, 0.2)), slash = ease(seg(t, 0.2, 0.45)), back = ease(seg(t, 0.55, 1));
      p.x += wind * 0.12 - slash * 0.3 + back * 0.18;
      p.y += wind * 0.05 - slash * 0.04;
      p.z -= slash * 0.12 - back * 0.12;
      ry += wind * 0.5 - slash * 1.3 + back * 0.8;
      rz += wind * 0.3 - slash * 0.5 + back * 0.2;
      p.y -= (1 - Math.min(1, t * 8)) * 0.2 + back * 0.25;
    } else if (o.id === 'frag' && this.throwT >= 0) {
      const t = clamp01(this.throwT);
      const up = ease(seg(t, 0, 0.45)), thr = ease(seg(t, 0.45, 0.65)), down = ease(seg(t, 0.65, 1));
      p.y += up * 0.08 - thr * 0.05 - down * 0.3;
      p.z += up * 0.12 - thr * 0.35;
      rx += up * 0.6 - thr * 1.4;
      o.root.visible = t < 0.6;
    } else if (o.id === 'drink' && this.drinkT >= 0) {
      const t = clamp01(this.drinkT);
      const raise = ease(seg(t, 0, 0.3)), tip = ease(seg(t, 0.3, 0.55)) * (1 - ease(seg(t, 0.75, 0.9))), low = ease(seg(t, 0.85, 1));
      p.y -= (1 - raise) * 0.3 + low * 0.35;
      p.x -= raise * 0.06;
      p.z += tip * 0.08;
      rx += tip * 1.0;
    }
    w.position.copy(p);
    w.quaternion.copy(rest.q);
    w.rotateX(rx); w.rotateY(ry); w.rotateZ(rz);
  }

  /** World-model clone of a weapon for the box / wall / PaP (arms removed, centred). */
  worldModel(id) {
    const e = this.models.get(id);
    if (!e) return null;
    const src = e.weapon;
    const clone = src.clone(true);
    clone.position.set(0, 0, 0);
    clone.quaternion.identity();
    const drop = [];
    clone.traverse(o => { const n = nodeName(o); if (n === 'arm_L' || n === 'arm_R' || n === 'mag_spare') drop.push(o); });
    drop.forEach(o => o.parent?.remove(o));
    clone.traverse(o => { if (o.isMesh) { o.castShadow = true; o.visible = true; } });
    const box = new THREE.Box3().setFromObject(clone);
    const c = box.getCenter(new THREE.Vector3());
    const g = new THREE.Group();
    clone.position.sub(c);
    g.add(clone);
    g.userData.length = box.getSize(new THREE.Vector3()).z;
    return g;
  }
}
