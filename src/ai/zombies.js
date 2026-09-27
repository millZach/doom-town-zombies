import * as THREE from 'three';
import { loadGLB, cloneSkinned, findNode, nodeName } from '../core/assets.js';
import { ZOMBIE } from '../config.js';

// nominal clip ground speeds (m/s) used to sync animation to movement; updated from the character build
export const CLIP_SPEED = { walk: 0.9, run: 2.6, sprint: 4.2, dogRun: 7.0, crawl: 0.55 };

const _v = new THREE.Vector3();
const _v2 = new THREE.Vector3();
const _v3 = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _a = new THREE.Vector3();
const _b = new THREE.Vector3();
const _start = new THREE.Vector3();
const _end = new THREE.Vector3();
const _head = new THREE.Vector3();
const _m1 = new THREE.Matrix4();
const _q1 = new THREE.Quaternion();
const _q2 = new THREE.Quaternion();
const _col = new THREE.Color();
const UP = new THREE.Vector3(0, 1, 0);
const DOWN = new THREE.Vector3(0, -1, 0);
const clamp01 = t => Math.max(0, Math.min(1, t));
const wrapPi = a => Math.atan2(Math.sin(a), Math.cos(a));

// ---------------------------------------------------------------- materials
// Every zombie instance owns its materials (SkeletonUtils.clone shares them), so
// eyes, skin tint, wound decals and the corpse fade are all per-zombie.
//
// The injected shader adds three things the art direction asks for:
//   * a cool fresnel rim so the silhouette separates from the fog bank (#10)
//   * fog at 80% of the world rate so they don't wash out at 15 m (#10)
//   * up to 4 bind-space "wound" blobs that ride the skin (#20/#21)
// All zombie materials share one compiled program via customProgramCacheKey.
const ZOMBIE_PROGRAM_KEY = 'bo2-zombie-body';
export const WOUND_SLOTS = 4;

const RIM_SNIPPET = /* glsl */`
#include <opaque_fragment>
{
  float zRim = 1.0 - saturate(dot(normalize(vViewPosition), normal));
  gl_FragColor.rgb += vec3(0.26, 0.33, 0.50) * pow(zRim, 4.0) * 0.16;
  gl_FragColor.rgb += vec3(0.20, 0.17, 0.13) * pow(zRim, 2.0) * 0.035;
}`;

const FOG_SNIPPET = /* glsl */`
#ifdef USE_FOG
  #ifdef FOG_EXP2
    float zFogFactor = 1.0 - exp( - fogDensity * fogDensity * vFogDepth * vFogDepth );
  #else
    float zFogFactor = smoothstep( fogNear, fogFar, vFogDepth );
  #endif
  gl_FragColor.rgb = mix( gl_FragColor.rgb, fogColor, zFogFactor * 0.8 );
#endif`;

const WOUND_SNIPPET = /* glsl */`
#include <color_fragment>
float zWound = 0.0;
for (int wi = 0; wi < ${WOUND_SLOTS}; wi++) {
  float wr = uWounds[wi].w;
  if (wr > 0.0005) {
    float wd = distance(vZBind, uWounds[wi].xyz);
    zWound = max(zWound, 1.0 - smoothstep(wr * 0.22, wr, wd));
  }
}
diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.085, 0.008, 0.006), zWound * 0.93);`;

function zombieProgramKey() { return ZOMBIE_PROGRAM_KEY; }

function enhanceZombieMaterial(m, woundUniform) {
  if ('envMapIntensity' in m) m.envMapIntensity = 0.6;
  // kept transparent for the whole life of the instance so the corpse fade never
  // has to toggle the OPAQUE define (which would force a shader recompile mid-fight)
  m.transparent = true;
  m.depthWrite = true;
  m.opacity = 1;
  m.onBeforeCompile = shader => {
    shader.uniforms.uWounds = woundUniform;
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vZBind;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\n\tvZBind = transformed;');
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', `#include <common>\nvarying vec3 vZBind;\nuniform vec4 uWounds[${WOUND_SLOTS}];`)
      .replace('#include <color_fragment>', WOUND_SNIPPET)
      // the instance is permanently `transparent` so the corpse fade never has to
      // flip the OPAQUE define; forcing alpha from `opacity` keeps a baked texture's
      // alpha channel from punching holes in the body
      .replace('#include <alphamap_fragment>', '#include <alphamap_fragment>\ndiffuseColor.a = opacity;')
      .replace('#include <roughnessmap_fragment>', '#include <roughnessmap_fragment>\nroughnessFactor = mix(roughnessFactor, 0.24, zWound);')
      .replace('#include <opaque_fragment>', RIM_SNIPPET)
      .replace('#include <fog_fragment>', FOG_SNIPPET);
  };
  m.customProgramCacheKey = zombieProgramKey;
  m.needsUpdate = true;
}

// ---------------------------------------------------------------- placeholders
function placeholderZombie() {
  const root = new THREE.Group();
  const skin = new THREE.MeshStandardMaterial({ color: 0x6d7560, roughness: 0.8 });
  const cloth = new THREE.MeshStandardMaterial({ color: 0x5a5146, roughness: 0.95 });
  const eye = new THREE.MeshStandardMaterial({ color: 0x331100, emissive: 0xffaa22, emissiveIntensity: 6, name: 'eye_glow' });
  const mk = (geo, mat, name, parent, pos) => { const m = new THREE.Mesh(geo, mat); m.name = name; m.userData.name = name; m.position.set(...pos); (parent || root).add(m); m.castShadow = true; return m; };
  const hips = new THREE.Group(); hips.name = 'hips'; hips.position.y = 0.95; root.add(hips);
  const chest = new THREE.Group(); chest.name = 'chest'; chest.position.y = 0.35; hips.add(chest);
  mk(new THREE.CapsuleGeometry(0.2, 0.45, 4, 10), cloth, 'body_A', chest, [0, 0.05, 0]);
  const neck = new THREE.Group(); neck.name = 'neck'; neck.position.y = 0.42; chest.add(neck);
  const head = new THREE.Group(); head.name = 'head'; head.position.y = 0.08; neck.add(head);
  mk(new THREE.SphereGeometry(0.12, 14, 10), skin, 'head_A', head, [0, 0.1, 0]);
  mk(new THREE.BoxGeometry(0.12, 0.025, 0.02), eye, 'eyes_A', head, [0, 0.13, 0.105]);
  for (const s of [-1, 1]) {
    const arm = new THREE.Group(); arm.name = s < 0 ? 'upperarm_L' : 'upperarm_R'; arm.position.set(0.25 * s, 0.32, 0); chest.add(arm);
    mk(new THREE.CapsuleGeometry(0.055, 0.5, 4, 8), skin, 'arm', arm, [0, 0, 0.28]).rotation.x = Math.PI / 2;
    const hand = new THREE.Group(); hand.name = s < 0 ? 'hand_L' : 'hand_R'; hand.position.set(0, 0, 0.58); arm.add(hand);
    const leg = new THREE.Group(); leg.name = s < 0 ? 'thigh_L' : 'thigh_R'; leg.position.set(0.11 * s, 0, 0); hips.add(leg);
    mk(new THREE.CapsuleGeometry(0.075, 0.75, 4, 8), cloth, 'leg', leg, [0, -0.45, 0]);
    const foot = new THREE.Group(); foot.name = s < 0 ? 'foot_L' : 'foot_R'; foot.position.set(0, -0.9, 0); leg.add(foot);
  }
  return root;
}

function placeholderDog() {
  const root = new THREE.Group();
  const m = new THREE.MeshStandardMaterial({ color: 0x2a1a14, roughness: 0.7, emissive: 0x220500 });
  const eye = new THREE.MeshStandardMaterial({ color: 0x331100, emissive: 0xff6611, emissiveIntensity: 8, name: 'eye_glow' });
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.22, 0.7, 4, 10), m); body.rotation.x = Math.PI / 2; body.position.y = 0.62; root.add(body);
  const head = new THREE.Group(); head.name = 'head'; head.position.set(0, 0.8, 0.55); root.add(head);
  head.add(new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.2, 0.32), m));
  const e = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.03, 0.02), eye); e.position.set(0, 0.04, 0.16); head.add(e);
  for (const [x, z] of [[-0.14, 0.35], [0.14, 0.35], [-0.14, -0.35], [0.14, -0.35]]) {
    const leg = new THREE.Mesh(new THREE.CapsuleGeometry(0.05, 0.45, 4, 6), m); leg.position.set(x, 0.28, z); leg.name = 'leg'; root.add(leg);
  }
  root.traverse(o => { if (o.isMesh) o.castShadow = true; });
  return root;
}

// ray vs sphere / capsule helpers (return distance along ray or -1)
function raySphere(o, d, c, r) {
  _v.subVectors(o, c);
  const b = _v.dot(d), cc = _v.lengthSq() - r * r;
  const h = b * b - cc;
  if (h < 0) return -1;
  const t = -b - Math.sqrt(h);
  return t >= 0 ? t : -1;
}
function rayCapsule(o, d, pa, pb, r) {
  // closest points between ray (o + t d) and segment pa-pb
  const ba = _a.subVectors(pb, pa), oa = _b.subVectors(o, pa);
  const baba = ba.dot(ba), bard = ba.dot(d), baoa = ba.dot(oa), rdoa = d.dot(oa), oaoa = oa.dot(oa);
  const a = baba - bard * bard;
  let b = baba * rdoa - baoa * bard;
  let c = baba * oaoa - baoa * baoa - r * r * baba;
  let h = b * b - a * c;
  if (h >= 0) {
    const t = (-b - Math.sqrt(h)) / a;
    const y = baoa + t * bard;
    if (y > 0 && y < baba && t > 0) return t;
    // caps
    const oc = y <= 0 ? oa : _v2.subVectors(o, pb);
    b = d.dot(oc); c = oc.dot(oc) - r * r;
    h = b * b - c;
    if (h > 0) { const tt = -b - Math.sqrt(h); if (tt > 0) return tt; }
  }
  return -1;
}

// animation fallbacks used when the GLB is missing a clip. Every one of these is a
// compromise, so `_play` warns once per (kind, clip) instead of failing silently (#22).
const CLIP_FALLBACK = {
  sprint: 'run', run: 'walk', tear: 'attack', climb: 'walk', rise: 'idle', hit: 'idle',
  death_2: 'death_1', death: 'death_1',
  death_front: 'death_1', death_back: 'death_1', death_left: 'death_2', death_right: 'death_2',
  crawl: 'walk', crawl_attack: 'attack', to_crawl: 'death_1',
};

const DEATH_CLIPS = ['death_front', 'death_back', 'death_left', 'death_right'];
// bones that can carry a randomly-placed blood stain at spawn
const STAIN_BONES = ['chest', 'spine', 'hips', 'upperarm_L', 'upperarm_R', 'forearm_L', 'forearm_R', 'thigh_L', 'thigh_R', 'head', 'neck'];

// ---------------------------------------------------------------- manager
export class ZombieManager {
  constructor(game) {
    this.game = game;
    this.scene = game.scene;
    this.list = [];
    this.pool = [];
    this.template = null;
    this.dogTemplate = null;
    this.clips = {};
    this.dogClips = {};
    this.real = false;
    this.dogReal = false;
    this.groanTimer = 0;
    this.eyeMats = new Set();      // kept for compatibility; flicker is per-zombie now
    this._warned = new Set();
    this.maxCorpses = 8;
  }

  async load() {
    const gltf = await loadGLB('/models/zombie.glb');
    if (gltf) {
      this.template = gltf.scene;
      for (const c of gltf.animations) this.clips[c.name] = c;
      this.real = true;
      console.log('[zombies] clips:', Object.keys(this.clips).join(', '));
    }
    const dog = await loadGLB('/models/hellhound.glb');
    if (dog) {
      this.dogTemplate = dog.scene;
      for (const c of dog.animations) this.dogClips[c.name] = c;
      this.dogReal = true;
    }
  }

  get aliveCount() { return this.list.filter(z => z.state !== 'dead').length; }

  /** true when the GLB carries the crawler set (clips + hideable lower legs) */
  get crawlersSupported() { return !!(this.real && this.clips.crawl && this.clips.to_crawl); }

  // ---------------- construction
  _build(kind) {
    const isDog = kind === 'dog';
    const real = isDog ? this.dogReal : this.real;
    let root;
    if (real) root = cloneSkinned(isDog ? this.dogTemplate : this.template);
    else root = isDog ? placeholderDog() : placeholderZombie();
    const holder = new THREE.Group();
    holder.add(root);
    const z = {
      kind, holder, root, real,
      mixer: real ? new THREE.AnimationMixer(root) : null,
      actions: {}, current: null,
      bones: {}, heads: [], variantMeshes: {},
      mats: [], eyeMats: [], skinMats: [],
      wounds: null, woundSlot: 0, skin: null, bindInv: null, restWorld: null,
      pos: holder.position, yaw: 0, vel: new THREE.Vector3(),
      state: 'dead', t: 0, health: 100, speed: 1, gait: 'walk',
      bodyScale: 1, lostLimbs: null,
    };
    if (real) {
      const clips = isDog ? this.dogClips : this.clips;
      for (const [name, clip] of Object.entries(clips)) z.actions[name] = z.mixer.clipAction(clip);
    }
    const boneNames = ['hips', 'spine', 'chest', 'neck', 'head', 'upperarm_L', 'upperarm_R', 'forearm_L', 'forearm_R', 'hand_L', 'hand_R', 'thigh_L', 'thigh_R', 'shin_L', 'shin_R', 'foot_L', 'foot_R'];
    for (const b of boneNames) { const o = findNode(root, b); if (o) z.bones[b] = o; }

    // per-instance wound uniform shared by every material on this zombie
    const wounds = [];
    for (let i = 0; i < WOUND_SLOTS; i++) wounds.push(new THREE.Vector4(0, 0, 0, 0));
    z.wounds = { value: wounds };

    root.traverse(o => {
      if (!o.isMesh) return;
      o.castShadow = true;
      o.receiveShadow = true;
      o.frustumCulled = false;
      if (o.isSkinnedMesh && !z.skin) z.skin = o;
      const nm = nodeName(o.parent && !o.name ? o.parent : o) || o.name;
      // clone every material so tint / fade / wounds are per instance (#2, #20, #21)
      const mats = Array.isArray(o.material) ? o.material : [o.material];
      const cloned = [];
      for (const src of mats) {
        if (!src) { cloned.push(src); continue; }
        const m = src.clone();
        m.name = src.name;
        const isEye = (m.name || '').includes('eye_glow');
        if (isEye) {
          // a dull amber ember, not a headlamp (#2)
          m.emissiveIntensity = 2.2;
          if (m.emissive) m.emissive.setRGB(1.0, 0.34, 0.05);
          m.toneMapped = true;
          // eye_glow ships as alphaMode OPAQUE; the corpse fade drives `opacity` on
          // every material this zombie owns, so the eyes have to be able to fade too
          // or the skull quads stay solid while the body dissolves.
          m.transparent = true;
          m.depthWrite = true;
          m.opacity = 1;
          m.needsUpdate = true;
          z.eyeMats.push(m);
          this.eyeMats.add(m);
        } else {
          enhanceZombieMaterial(m, z.wounds);
          if (/skin|flesh|head|hide/i.test(m.name || '')) z.skinMats.push(m);
        }
        // the hair/helmet slot is its own primitive, so it can be dropped per instance (#20)
        if (/hair|helmet|scalp/i.test(m.name || '')) (z.hairMeshes ||= new Set()).add(o);
        z.mats.push({ m, base: m.color ? m.color.clone() : null, isEye });
        cloned.push(m);
      }
      o.material = Array.isArray(o.material) ? cloned : cloned[0];
      const vm = /(body|head|eyes|legs)_([ABC])/.exec(nodeName(o) || nm);
      if (vm) (z.variantMeshes[vm[2]] ||= []).push({ mesh: o, part: vm[1] });
    });
    // group level nodes (multi-material meshes come in as Groups)
    root.traverse(o => {
      const vm = /(body|head|eyes|legs)_([ABC])/.exec(nodeName(o));
      if (vm && !o.isMesh) {
        o.traverse(c => { if (c.isMesh && !(z.variantMeshes[vm[2]] || []).some(e => e.mesh === c)) (z.variantMeshes[vm[2]] ||= []).push({ mesh: c, part: vm[1] }); });
      }
    });
    if (!z.skinMats.length) z.skinMats = z.mats.filter(e => !e.isEye).map(e => e.m).slice(0, 1);
    this._prepareBindSpace(z);
    return z;
  }

  // Cached matrices for turning a world-space hit into the skeleton's bind space,
  // which is where the wound decals live (they then ride the skin for free).
  _prepareBindSpace(z) {
    const skin = z.skin;
    if (!skin || !skin.skeleton) return;
    z.bindInv = new THREE.Matrix4().copy(skin.bindMatrix).invert();
    z.restWorld = skin.skeleton.boneInverses.map(bi => new THREE.Matrix4().copy(bi).invert());
    z.boneIndex = new Map();
    skin.skeleton.bones.forEach((b, i) => z.boneIndex.set(b, i));
  }

  /** world point -> bind-space point (or null). p_bind = bindMatrix^-1 * restWorld_i * boneWorld_i^-1 * P */
  _bindPoint(z, worldPoint, out = new THREE.Vector3()) {
    if (!z.skin || !z.restWorld) return null;
    const bones = z.skin.skeleton.bones;
    let best = -1, bd = Infinity;
    for (let i = 0; i < bones.length; i++) {
      const d = bones[i].getWorldPosition(_v2).distanceToSquared(worldPoint);
      if (d < bd) { bd = d; best = i; }
    }
    if (best < 0) return null;
    out.copy(worldPoint)
      .applyMatrix4(_m1.copy(bones[best].matrixWorld).invert())
      .applyMatrix4(z.restWorld[best])
      .applyMatrix4(z.bindInv);
    return out;
  }

  _addWound(z, worldPoint, radius = 0.075) {
    if (!z.wounds || !z.real) return;
    const p = this._bindPoint(z, worldPoint, _v3);
    if (!p) return;
    const w = z.wounds.value[z.woundSlot % WOUND_SLOTS];
    z.woundSlot++;
    w.set(p.x, p.y, p.z, radius);
  }

  _clearWounds(z) {
    if (!z.wounds) return;
    for (const w of z.wounds.value) w.set(0, 0, 0, 0);
    z.woundSlot = 0;
  }

  // 0-2 pre-existing stains so no two zombies in a wave are identically clean (#20)
  _seedStains(z) {
    if (!z.real || !z.restWorld || !z.boneIndex) return;
    const n = Math.random() < 0.45 ? 2 : Math.random() < 0.75 ? 1 : 0;
    for (let i = 0; i < n; i++) {
      const name = STAIN_BONES[Math.floor(Math.random() * STAIN_BONES.length)];
      const bone = z.bones[name];
      const idx = bone ? z.boneIndex.get(bone) : undefined;
      if (idx === undefined) continue;
      const rest = z.restWorld[idx];
      const w = z.wounds.value[z.woundSlot % WOUND_SLOTS];
      z.woundSlot++;
      w.set(rest.elements[12] + (Math.random() - 0.5) * 0.12,
        rest.elements[13] + (Math.random() - 0.5) * 0.14,
        rest.elements[14] + (Math.random() - 0.5) * 0.1,
        0.055 + Math.random() * 0.075);
    }
  }

  _play(z, name, { fade = 0.25, loop = true, timeScale = 1, restart = false } = {}) {
    if (!z.real) { z.anim = name; z.animT = 0; return null; }
    let a = z.actions[name];
    if (!a) {
      const alt = CLIP_FALLBACK[name];
      a = alt ? z.actions[alt] : null;
      const key = z.kind + ':' + name;
      if (!this._warned.has(key)) {
        this._warned.add(key);
        console.warn(`[zombies] ${z.kind} clip "${name}" missing — falling back to "${alt || 'nothing'}". The animation will read wrong; re-export the character GLB.`);
      }
    }
    if (!a) return null;
    a.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce, Infinity);
    a.clampWhenFinished = !loop;
    a.timeScale = timeScale;
    if (z.current === a && !restart) return a;
    a.reset();
    // every zombie starts its loop somewhere else in the cycle, so the horde is not
    // a chorus line (#3)
    if (loop && z.phase !== undefined) a.time = z.phase * a.getClip().duration;
    a.enabled = true;
    a.setEffectiveWeight(1);
    a.play();
    if (z.current && z.current !== a) z.current.crossFadeTo(a, fade, false);
    z.current = a;
    return a;
  }

  _clipDuration(z, name, fallback) {
    const a = z.real && (z.actions[name] || z.actions[CLIP_FALLBACK[name]]);
    return a ? a.getClip().duration : fallback;
  }

  // ---------------- spawning
  spawn(opts) {
    const kind = opts.kind || 'zombie';
    let z = this.pool.findIndex(p => p.kind === kind);
    z = z >= 0 ? this.pool.splice(z, 1)[0] : this._build(kind);
    const g = this.game;
    z.holder.visible = true;
    if (!z.holder.parent) this.scene.add(z.holder);
    z.pos.copy(opts.pos);
    z.yaw = opts.yaw ?? Math.random() * Math.PI * 2;
    z.vel.set(0, 0, 0);
    z.health = opts.health;
    z.maxHealth = opts.health;
    z.gait = opts.gait || 'walk';
    z.speed = kind === 'dog' ? 7.2 : z.gait === 'sprint' ? ZOMBIE.sprintSpeed * (0.9 + Math.random() * 0.2) : z.gait === 'run' ? ZOMBIE.runSpeed * (0.9 + Math.random() * 0.2) : ZOMBIE.walkSpeed * (0.8 + Math.random() * 0.4);
    z.t = 0;
    z.attackT = 0;
    z.hitDone = false;
    z.flinch = 0;
    z.flinchDir = 0;
    z.headless = false;
    z.barrier = opts.barrier || null;
    z.stuckT = 0; z.bestDist = Infinity;
    z.groanT = 2 + Math.random() * 6;
    z.burning = 0;
    z.id = (this._id = (this._id || 0) + 1);
    // per-zombie animation clock (#3)
    z.phase = Math.random();
    z.rateJitter = 0.82 + Math.random() * 0.36;
    z.attackDelay = Math.random() * 0.25;
    // per-zombie eye ember (#2)
    z.eyePhase = Math.random() * 6.283;
    z.eyeRate = 5 + Math.random() * 6;
    z.eyeSpike = 0;
    // reset anything the previous life left behind
    z.crawler = false;
    z.knockT = 0; z.knockX = 0; z.knockZ = 0;
    z.deathDir = null;
    z.hitch = 0;
    z.lookYaw = 0; z.lookPitch = 0;
    z.stepCd = 0; z.stepPhase = 0;
    z.footYL = undefined; z.footYR = undefined; z.footDownL = false; z.footDownR = false;
    z.bodyFallDone = false;
    z.dogBurn = false; z.spray = 0;
    z.riseFx = 0;
    z.swipe = false; z.tearing = false;
    if (z.mixer) z.mixer.timeScale = 1;
    this._restoreLimbs(z);
    this._clearWounds(z);
    this._setOpacity(z, 1);

    // variant + per-instance dressing (#20)
    if (kind === 'zombie') {
      const variants = Object.keys(z.variantMeshes);
      z.variant = variants.length ? variants[Math.floor(Math.random() * variants.length)] : 'A';
      for (const [v, list] of Object.entries(z.variantMeshes)) for (const e of list) e.mesh.visible = v === z.variant;
      // 20% come up bald / scalped — hair_A is its own primitive, so it is hideable (#20)
      z.bald = !!z.hairMeshes && Math.random() < 0.2;
      if (z.hairMeshes) for (const m of z.hairMeshes) if (m.visible) m.visible = !z.bald;
      z.bodyScale = 0.90 + Math.random() * 0.17;
      z.mirror = Math.random() < 0.4;
      z.root.scale.set(z.bodyScale * (z.mirror ? -1 : 1), z.bodyScale, z.bodyScale);
      z.shoulderL = (Math.random() - 0.5) * 0.21;
      z.shoulderR = (Math.random() - 0.5) * 0.21;
      this._tint(z);
      this._seedStains(z);
    } else {
      z.bodyScale = 0.95 + Math.random() * 0.12;
      z.mirror = false;
      z.root.scale.setScalar(z.bodyScale);
      z.shoulderL = z.shoulderR = 0;
      this._tint(z);
    }
    z.root.position.set(0, 0, 0);
    z.root.rotation.set(0, 0, 0);
    if (z.mixer) { z.mixer.stopAllAction(); z.current = null; }

    // a few zombies come out of the ground already broken at higher rounds (#4)
    if (kind === 'zombie' && this.crawlersSupported && opts.mode !== 'dog') {
      const round = g.round || 0;
      if (round >= 8 && Math.random() < Math.min(0.14, 0.02 + (round - 8) * 0.012)) this._becomeCrawler(z, { silent: true });
    }

    if (opts.mode === 'rise') {
      z.state = 'rise';
      z.riseDur = this._clipDuration(z, 'rise', 2.2);
      this._play(z, 'rise', { loop: false, fade: 0 });
      // the soil keeps moving for as long as the body is coming out (#14)
      z.riseFx = 0;
      this._riseDirt(z, 1.0);
      g.audio.playAt('zombie_rise_dirt', z.pos, { volume: 0.8 });
      const gh = g.collision.raycast(_v.set(z.pos.x, z.pos.y + 0.6, z.pos.z), _v2.set(0, -1, 0), 2.2);
      if (gh) g.decals.dirtPatch(gh.point, gh.normal, 1.15 + Math.random() * 0.5);
    } else if (opts.mode === 'barrier') {
      z.state = 'toBarrier';
      this._play(z, z.crawler ? 'crawl' : z.gait === 'walk' ? 'walk' : 'run', { fade: 0 });
    } else if (opts.mode === 'dog') {
      z.state = 'dogSpawn';
      z.holder.visible = false;
      z.t = 0;
    } else {
      z.state = 'chase';
      this._play(z, this._gaitClip(z), { fade: 0 });
    }
    this.list.push(z);
    this._applyTransform(z);
    return z;
  }

  _gaitClip(z) {
    if (z.kind === 'dog') return 'run';
    if (z.crawler) return 'crawl';
    return z.gait;
  }

  // per-instance skin/cloth tint so a wave of one variant isn't eight identical copies (#20)
  _tint(z) {
    const hue = (Math.random() - 0.5) * 0.075;
    const val = 0.84 + Math.random() * 0.22;
    const sat = 0.8 + Math.random() * 0.45;
    const hsl = this._hsl || (this._hsl = { h: 0, s: 0, l: 0 });
    for (const e of z.mats) {
      if (e.isEye || !e.base) continue;
      _col.copy(e.base);
      _col.getHSL(hsl);
      if (hsl.s < 0.06) {
        // baked albedo (white tint slot): push a faint warm/cool cast instead of nothing
        _col.setHSL((0.055 + hue * 2 + 1) % 1, 0.055 + Math.random() * 0.07, Math.min(1, hsl.l * val));
      } else {
        _col.setHSL((hsl.h + hue + 1) % 1, Math.min(1, hsl.s * sat), Math.min(1, hsl.l * val));
      }
      e.m.color.copy(_col);
    }
  }

  _setOpacity(z, k) {
    for (const e of z.mats) e.m.opacity = k;
  }

  // ---------------- queries
  raycast(origin, dir, maxDist) {
    const hits = [];
    for (const z of this.list) {
      if (z.state === 'dead' || z.state === 'dogSpawn' || !z.holder.visible) continue;
      // cheap reject: bounding sphere around the body
      const cy = z.crawler ? 0.35 : z.kind === 'dog' ? 0.5 : 0.9;
      _v.set(z.pos.x, z.pos.y + cy, z.pos.z);
      const coarse = raySphere(origin, dir, _v, z.kind === 'dog' ? 0.9 : 1.3);
      if (coarse < 0 && _v.distanceToSquared(origin) > 2) continue;
      if (coarse > maxDist) continue;
      const hb = this._hitboxes(z);
      let best = null;
      for (const h of hb) {
        const t = h.r2 ? rayCapsule(origin, dir, h.a, h.b, h.r) : raySphere(origin, dir, h.a, h.r);
        // heads win ties so shots that clip the skull count as headshots
        if (t >= 0 && t < maxDist && (!best || t < best.t + (h.part === 'head' ? 0.05 : 0))) best = { t, part: h.part, limb: h.limb };
      }
      if (best) hits.push({ zombie: z, dist: best.t, part: best.part, limb: best.limb, point: origin.clone().addScaledVector(dir, best.t) });
    }
    return hits.sort((p, q) => p.dist - q.dist);
  }

  _hitboxes(z) {
    z.holder.updateMatrixWorld(true);
    const B = z.bones;
    const wp = (o, out) => o.getWorldPosition(out);
    const out = [];
    if (z.kind === 'dog') {
      const h = B.head ? wp(B.head, new THREE.Vector3()) : new THREE.Vector3(z.pos.x, z.pos.y + 0.8, z.pos.z);
      out.push({ part: 'head', a: h, r: 0.2 });
      const fwd = new THREE.Vector3(Math.sin(z.yaw), 0, Math.cos(z.yaw));
      const c = new THREE.Vector3(z.pos.x, z.pos.y + 0.6, z.pos.z);
      out.push({ part: 'body', a: c.clone().addScaledVector(fwd, 0.45), b: c.clone().addScaledVector(fwd, -0.45), r: 0.28, r2: true });
      return out;
    }
    if (B.head && B.hips) {
      const head = wp(B.head, new THREE.Vector3());
      const neck = B.neck ? wp(B.neck, new THREE.Vector3()) : head.clone().add(new THREE.Vector3(0, -0.1, 0));
      const hips = wp(B.hips, new THREE.Vector3());
      const up = head.clone().sub(neck); if (up.lengthSq() < 1e-6) up.set(0, 1, 0); up.normalize();
      const s = z.bodyScale || 1;
      if (!z.headless) out.push({ part: 'head', a: head.clone().addScaledVector(up, 0.09 * s), r: 0.135 * s });
      out.push({ part: 'neck', a: neck, b: head, r: 0.07 * s, r2: true });
      out.push({ part: 'body', a: hips.clone().addScaledVector(UP, -0.05), b: neck.clone().addScaledVector(up, -0.05), r: 0.21 * s, r2: true });
      for (const sd of ['L', 'R']) {
        const ua = B['upperarm_' + sd], ha = B['hand_' + sd], th = B['thigh_' + sd], ft = B['foot_' + sd];
        if (ua && ha) out.push({ part: 'limb', limb: 'arm', a: wp(ua, new THREE.Vector3()), b: wp(ha, new THREE.Vector3()), r: 0.075 * s, r2: true });
        if (!z.crawler && th && ft) out.push({ part: 'limb', limb: 'leg', a: wp(th, new THREE.Vector3()), b: wp(ft, new THREE.Vector3()), r: 0.09 * s, r2: true });
      }
    } else {
      const c = z.pos;
      const lift = z.crawler ? 0.42 : 0;
      out.push({ part: 'head', a: new THREE.Vector3(c.x, c.y + 1.72 - lift * 2.4, c.z), r: 0.14 });
      out.push({ part: 'body', a: new THREE.Vector3(c.x, c.y + 0.5 - lift * 0.6, c.z), b: new THREE.Vector3(c.x, c.y + 1.45 - lift * 2, c.z), r: 0.25, r2: true });
    }
    return out;
  }

  headPosition(z, out = new THREE.Vector3()) {
    if (z.bones.head) { z.bones.head.getWorldPosition(out); out.y += 0.08; return out; }
    return out.set(z.pos.x, z.pos.y + (z.kind === 'dog' ? 0.8 : z.crawler ? 0.45 : 1.7), z.pos.z);
  }

  inRadius(center, radius) {
    return this.list.filter(z => z.state !== 'dead' && z.state !== 'dogSpawn' && z.pos.distanceTo(center) < radius + 0.3);
  }

  // ---------------- damage
  damage(z, amount, info = {}) {
    if (z.state === 'dead' || z.state === 'dogSpawn') return false;
    const g = this.game;
    z.health -= amount;
    z.flinch = Math.min(1, z.flinch + 0.6);
    if (info.dir) z.flinchDir = wrapPi(Math.atan2(info.dir.x, info.dir.z) - z.yaw);
    if (!info.burn) { z.hitch = 0.08; z.eyeSpike = 0.15; }
    if (info.point) {
      const amt = info.part === 'head' ? 1.6 : info.part === 'neck' ? 1.25 : info.part === 'limb' ? 0.85 : 1.0;
      g.fx.blood(info.point, info.dir ? _v.copy(info.dir).negate().multiplyScalar(0.4).add(_v2.copy(UP).multiplyScalar(0.2)) : UP, amt);
      if (!info.burn) this._addWound(z, info.point, 0.05 + Math.random() * 0.045 + (info.part === 'head' ? 0.02 : 0));
      if (!info.burn && Math.random() < 0.7) g.audio.playAt('impact_flesh', info.point, { volume: 0.55, rate: 0.9 + Math.random() * 0.3 });
      if (Math.random() < 0.6) this._bloodOnGround(z, info.point, info.dir);
    }
    if (info.incendiary) z.burning = 3;
    if (z.health <= 0) {
      if (this._tryCrawler(z, info, amount)) return false;
      this.kill(z, info);
      return true;
    }
    return false;
  }

  _bloodOnGround(z, point, dir) {
    const g = this.game;
    const from = point.clone();
    const d = dir ? dir.clone().setY(-1.4).normalize() : new THREE.Vector3(0, -1, 0);
    const hit = g.collision.raycast(from, d, 3.5, { doors: true, barriers: false });
    if (hit) g.decals.bloodSplat(hit.point, hit.normal, 0.35 + Math.random() * 0.4);
  }

  // ---------------- crawlers (#4)
  _tryCrawler(z, info, amount = 0) {
    if (z.kind !== 'zombie' || z.crawler || z.headless) return false;
    if (!this.crawlersSupported) return false;
    // Insta-Kill and the nuke are supposed to kill, not maim
    if (amount >= 1e8 || info.nuke) return false;
    if (z.state === 'climb' || z.state === 'rise' || z.state === 'toCrawl') return false;
    // legs shot out from under it, or an explosion at its feet
    const lowHit = info.point ? (info.point.y - z.pos.y) < 0.95 : false;
    const byLimb = info.part === 'limb' && (info.limb === 'leg' || lowHit);
    let chance = 0;
    if (byLimb) chance = 0.8;
    else if (info.explosive) chance = lowHit ? 0.55 : 0.35;
    if (chance <= 0 || Math.random() > chance) return false;
    z.health = Math.max(1, z.maxHealth * 0.3);
    this._becomeCrawler(z, { info });
    return true;
  }

  _becomeCrawler(z, { info = null, silent = false } = {}) {
    const g = this.game;
    z.crawler = true;
    z.gait = 'walk';
    z.speed = ZOMBIE.walkSpeed * 0.85;
    this._hideLegs(z);
    if (!silent) {
      // dropped mid-tear: release the window slot but keep the barrier as the goal,
      // so _toCrawl() sends it back to the same window instead of stranding it
      // outside the building with nothing to path to.
      if (z.barrier && z.barrier.climber === z) z.barrier.climber = null;
      z.tearing = false; z.swipe = false; z.tornThis = false;
      const hipY = z.pos.y + 0.55;
      const at = _v.set(z.pos.x, hipY, z.pos.z).clone();
      g.fx.gibBurst(at, { count: 7, speed: 4.5, size: 0.085, bone: true, groundY: z.pos.y + 0.02 });
      g.fx.blood(at, _v2.set(0, -0.4, 0), 2.6);
      for (const sd of ['L', 'R']) {
        const b = z.bones['shin_' + sd] || z.bones['thigh_' + sd];
        if (!b) continue;
        b.getWorldPosition(_v2);
        g.fx.gibBurst(_v2.clone(), { count: 4, speed: 3.6, size: 0.075, groundY: z.pos.y + 0.02 });
      }
      const gh = g.collision.raycast(_v.set(z.pos.x, z.pos.y + 0.5, z.pos.z), DOWN, 2);
      if (gh) g.decals.bloodSplat(gh.point, gh.normal, 1.1);
      g.audio.playAt('zombie_gib', z.pos, { volume: 0.95 });
      g.audio.playAt('zombie_scream', z.pos, { volume: 0.8, rate: 0.85 });
      z.state = 'toCrawl';
      z.t = 0;
      z.toCrawlDur = this._clipDuration(z, 'to_crawl', 0.65);
      this._play(z, 'to_crawl', { loop: false, fade: 0.08, restart: true });
    }
  }

  _hideLegs(z) {
    let hid = false;
    const list = z.variantMeshes[z.variant] || [];
    for (const e of list) if (e.part === 'legs') { e.mesh.visible = false; hid = true; }
    if (hid) { z.legsHidden = true; return; }
    // no separate legs mesh in this GLB — shrink the lower-leg bones instead
    z.lostLimbs = z.lostLimbs || new Set();
    for (const n of ['shin_L', 'shin_R', 'foot_L', 'foot_R']) if (z.bones[n]) z.lostLimbs.add(n);
  }

  _restoreLimbs(z) {
    if (z.legsHidden) {
      for (const list of Object.values(z.variantMeshes)) for (const e of list) if (e.part === 'legs') e.mesh.visible = true;
      z.legsHidden = false;
    }
    if (z.lostLimbs) {
      for (const n of z.lostLimbs) { const b = z.bones[n]; if (b) b.scale.setScalar(1); }
      z.lostLimbs = null;
    }
  }

  _toCrawl(z, dt) {
    this._faceTowards(z, this.game.player.pos.x, this.game.player.pos.z, dt, 2);
    if (z.t >= (z.toCrawlDur || 0.65)) {
      z.state = z.barrier ? 'toBarrier' : 'chase';
      z.t = 0;
      this._play(z, 'crawl', { fade: 0.25 });
    }
  }

  // ---------------- death
  kill(z, info = {}) {
    const g = this.game;
    z.state = 'dead';
    z.t = 0;
    z.health = 0;
    z.bodyFallDone = false;
    z.eyeSpike = 0;
    if (z.mixer) z.mixer.timeScale = 1;
    if (z.kind === 'dog') {
      this._play(z, 'death', { loop: false, fade: 0.1 });
      z.dogBurn = true;
      const at = _v.set(z.pos.x, z.pos.y + 0.55, z.pos.z).clone();
      g.fx.emberBurst(at, 34, 1.15);
      g.fx.ashPuff(at, 14, 1.1);
      if (g.audio.has?.('hellhound_death')) g.audio.playAt('hellhound_death', z.pos, { volume: 0.95 });
      else g.audio.playAt('hellhound_growl', z.pos, { volume: 0.95, rate: 0.55 });
      const gh = g.collision.raycast(_v.set(z.pos.x, z.pos.y + 0.5, z.pos.z), DOWN, 2);
      if (gh) g.decals.scorchMark(gh.point, gh.normal, 1.5);
    } else {
      const headshot = info.part === 'head' && !info.explosive;
      const limbHit = info.part === 'limb';
      if (headshot || (info.gib && !limbHit && Math.random() < 0.55)) this._popHead(z, info.dir);
      else if (info.gib) {
        // tear off the limb that was actually hit, not a coin-flipped one (#6)
        const hit = this._hitLimb(z, info);
        const which = info.limb || hit?.limb;
        const side = info.side || hit?.side || (Math.random() < 0.5 ? 'L' : 'R');
        if (which === 'leg' && !z.crawler) this._popLegs(z, info.dir);
        else if (limbHit || Math.random() < 0.5) this._popLimb(z, side, info.dir);
      }
      z.deathDir = info.dir ? Math.atan2(info.dir.x, info.dir.z) : null;
      const clip = this._pickDeath(z, info);
      this._play(z, clip, { loop: false, fade: 0.1, restart: true });
      z.deathDur = this._clipDuration(z, clip, 1.5);
      this._applyKnockback(z, info);
      g.audio.playAt('zombie_death', z.pos, { volume: 0.85, rate: 0.9 + Math.random() * 0.25 });
    }
    // ground blood pool
    const gh = g.collision.raycast(_v.set(z.pos.x, z.pos.y + 0.5, z.pos.z), _v2.set(0, -1, 0), 2);
    if (gh) g.decals.bloodSplat(gh.point, gh.normal, 0.9 + Math.random() * 0.5);
    this._capCorpses();
    g.onZombieKilled?.(z, info);
  }

  // Directional death clips when the GLB has them (#5). z.deathDir is the *travel*
  // direction of the shot, so a shot in the back drops the body forward.
  _pickDeath(z, info) {
    // a crawler is already on the floor: the standing side/back falls read as a
    // teleport, so it just collapses forward onto its face
    if (z.crawler) return z.actions.death_front ? 'death_front' : 'death_1';
    const have = DEATH_CLIPS.filter(c => z.actions[c]);
    if (!have.length || z.deathDir === null || z.deathDir === undefined) {
      // no directional set: at least turn the body so the plank fall goes away
      // from the shooter instead of in a fixed direction
      if (z.deathDir !== null && z.deathDir !== undefined) z.yaw = z.deathDir + Math.PI;
      return Math.random() < 0.5 ? 'death_1' : 'death_2';
    }
    const rel = wrapPi(z.deathDir - z.yaw);
    const a = Math.abs(rel);
    let want;
    if (a < Math.PI * 0.25) want = 'death_front';
    else if (a > Math.PI * 0.75) want = 'death_back';
    else want = rel > 0 ? 'death_left' : 'death_right';
    if (info.part === 'head' && z.actions.death_back && Math.random() < 0.5) want = 'death_back';
    return z.actions[want] ? want : have[Math.floor(Math.random() * have.length)];
  }

  // a decaying horizontal shove so the weapon is legible in the death (#5)
  _applyKnockback(z, info) {
    if (!info.dir) return;
    const w = info.weapon || '';
    let push = 0.25;
    if (info.explosive) push = 1.0;
    else if (w === 'olympia' || w === 'remington870') push = 0.85;
    else if (info.part === 'head') push = 0.05;
    else if (w === 'm1911' || w === 'python') push = 0.18;
    if (info.knife) push = 0.12;
    // the impulse decays linearly over 0.35 s, so peak speed is 2x the average
    z.knockT = 0.35;
    z.knockX = info.dir.x * push * 2 / 0.35;
    z.knockZ = info.dir.z * push * 2 / 0.35;
  }

  // keep the N most recent corpses; older ones start their fade immediately
  _capCorpses() {
    const dead = this.list.filter(z => z.state === 'dead' && z.kind !== 'dog');
    if (dead.length <= this.maxCorpses) return;
    dead.sort((a, b) => a.t - b.t);        // newest (smallest t) first
    for (let i = this.maxCorpses; i < dead.length; i++) dead[i].t = Math.max(dead[i].t, 8);
  }

  _popHead(z, dir) {
    if (z.headless) return;
    z.headless = true;
    const g = this.game;
    const hp = this.headPosition(z, new THREE.Vector3());
    g.fx.headPop(hp, dir);
    g.fx.gibBurst(hp, { count: 8, speed: 5.5, size: 0.075, bone: true, dir: dir ? _v.copy(dir).setY(0.35).normalize() : null, groundY: z.pos.y + 0.02,
      onLand: p => { const gh = g.collision.raycast(_v2.set(p.x, p.y + 0.4, p.z), DOWN, 1.2); if (gh) g.decals.bloodSplat(gh.point, gh.normal, 0.5); } });
    // one heavy skull-sized piece that tumbles away and rests — the thing the eye
    // actually tracks out of the spray (#6). A cloned head mesh would allocate
    // mid-fight; this comes out of the same pre-built gib pool.
    g.fx.skullChunk(hp, dir, z.pos.y + 0.02);
    g.audio.playAt('headshot', hp, { volume: 0.9 });
    g.audio.playAt('zombie_gib', hp, { volume: 0.8 });
    // the stump keeps pumping for ~0.6 s
    z.spray = 0.6;
    for (const list of Object.values(z.variantMeshes)) for (const e of list) if (e.part === 'head' || e.part === 'eyes') e.mesh.visible = false;
    if (!z.real) z.root.traverse(o => { if (o.name === 'head_A' || o.name === 'eyes_A') o.visible = false; });
  }

  // Which limb the shot actually landed on. `raycast()` returns `limb: 'arm'|'leg'`
  // but not a side, and weapons.js does not forward it yet, so this resolves both
  // from the hit point against the posed skeleton. Returns null when there is no
  // usable hit point (burn ticks, nukes).
  _hitLimb(z, info) {
    if (!info.point || !z.real) return null;
    let best = null, bd = 0.3 * 0.3;      // must be within 30 cm of a limb bone
    for (const sd of ['L', 'R']) {
      for (const n of ['forearm_', 'hand_', 'upperarm_']) {
        const b = z.bones[n + sd];
        if (!b) continue;
        const d = b.getWorldPosition(_v2).distanceToSquared(info.point);
        if (d < bd) { bd = d; best = { side: sd, limb: 'arm' }; }
      }
      for (const n of ['shin_', 'foot_', 'thigh_']) {
        const b = z.bones[n + sd];
        if (!b) continue;
        const d = b.getWorldPosition(_v2).distanceToSquared(info.point);
        if (d < bd) { bd = d; best = { side: sd, limb: 'leg' }; }
      }
    }
    return best;
  }

  // both legs taken off at the hip by the killing blow (#6) — the corpse falls as a
  // torso. Reuses the crawler's leg-hiding so `_restoreLimbs()` puts it all back.
  _popLegs(z, dir) {
    if (z.legsHidden || z.crawler) return;
    const g = this.game;
    this._hideLegs(z);
    const at = _v.set(z.pos.x, z.pos.y + 0.6, z.pos.z).clone();
    g.fx.gibBurst(at, { count: 9, speed: 5.0, size: 0.1, bone: true, dir: dir ? _v2.copy(dir).setY(0.3).normalize() : null, groundY: z.pos.y + 0.02,
      onLand: p => { const gh = g.collision.raycast(_v2.set(p.x, p.y + 0.4, p.z), DOWN, 1.2); if (gh) g.decals.bloodSplat(gh.point, gh.normal, 0.6); } });
    for (const sd of ['L', 'R']) {
      const b = z.bones['thigh_' + sd];
      if (!b) continue;
      b.getWorldPosition(_v2);
      g.fx.gibBurst(_v2.clone(), { count: 4, speed: 3.8, size: 0.085, groundY: z.pos.y + 0.02 });
    }
    g.fx.blood(at, _v2.set(0, -0.3, 0), 3.4);
    this._addWound(z, at, 0.14);
    const gh = g.collision.raycast(_v.set(z.pos.x, z.pos.y + 0.5, z.pos.z), DOWN, 2);
    if (gh) g.decals.bloodSplat(gh.point, gh.normal, 1.2);
    g.audio.playAt('zombie_gib', at, { volume: 0.95 });
  }

  // arm torn off by an explosion / point-blank shotgun (#6)
  _popLimb(z, side, dir) {
    if (!z.real) return;
    const g = this.game;
    const names = ['forearm_' + side, 'hand_' + side];
    z.lostLimbs = z.lostLimbs || new Set();
    if (names.every(n => z.lostLimbs.has(n))) return;
    const anchor = z.bones['forearm_' + side] || z.bones['upperarm_' + side];
    if (!anchor) return;
    anchor.getWorldPosition(_v2);
    const at = _v2.clone();
    for (const n of names) if (z.bones[n]) z.lostLimbs.add(n);
    g.fx.gibBurst(at, { count: 6, speed: 4.8, size: 0.1, bone: true, dir: dir ? _v.copy(dir).setY(0.3).normalize() : null, groundY: z.pos.y + 0.02,
      onLand: p => { const gh = g.collision.raycast(_v.set(p.x, p.y + 0.4, p.z), DOWN, 1.2); if (gh) g.decals.bloodSplat(gh.point, gh.normal, 0.55); } });
    g.fx.blood(at, _v.set(0, 0.5, 0), 3.0);
    this._addWound(z, at, 0.12);
    g.audio.playAt('zombie_gib', at, { volume: 0.9 });
  }

  nukeAll() {
    const targets = this.list.filter(z => z.state !== 'dead');
    targets.forEach((z, i) => setTimeout(() => {
      if (z.state === 'dead') return;
      this._popHead(z, null);
      this.kill(z, { nuke: true, part: Math.random() < 0.5 ? 'head' : 'body' });
    }, 150 + Math.random() * 1800));
  }

  clearAll() {
    for (const z of this.list) this._recycle(z);
    this.list.length = 0;
  }

  _recycle(z) {
    z.holder.visible = false;
    z.state = 'dead';
    z.crawler = false;
    z.spray = 0;
    if (z.mixer) { z.mixer.stopAllAction(); z.mixer.timeScale = 1; }
    this._restoreLimbs(z);
    this._setOpacity(z, 1);
    this.pool.push(z);
  }

  // ---------------- update
  update(dt, time) {
    const g = this.game;
    const player = g.player;
    const nav = g.nav;
    // flow field toward the player
    nav.updateFlow(player.pos.x, player.pos.y, player.pos.z);

    const remove = [];
    for (const z of this.list) {
      z.t += dt;
      if (z.burning > 0) {
        z.burning -= dt;
        if (Math.random() < 0.6) g.fx.fire(_v.set(z.pos.x, z.pos.y + 0.6 + Math.random() * 0.8, z.pos.z), 0.4);
        if (z.state !== 'dead') this.damage(z, 60 * dt, { burn: true });
      }
      switch (z.state) {
        case 'rise': this._rise(z, dt); break;
        case 'toCrawl': this._toCrawl(z, dt); break;
        case 'toBarrier': this._toBarrier(z, dt); break;
        case 'tear': this._tear(z, dt, time); break;
        case 'climb': this._climb(z, dt); break;
        case 'chase': this._chase(z, dt, time); break;
        case 'attack': this._attack(z, dt, time); break;
        case 'wander': this._wander(z, dt); break;
        case 'dogSpawn': this._dogSpawn(z, dt); break;
        case 'dead': this._dead(z, dt, remove); break;
      }
      if (z.state !== 'dead' && z.state !== 'dogSpawn') this._audio(z, dt);
      // hellhounds smoulder: flames licking off the back and a trail of embers
      if (z.kind === 'dog' && z.state !== 'dead' && z.state !== 'dogSpawn' && Math.random() < 0.7) {
        const back = _v.set(z.pos.x - Math.sin(z.yaw) * 0.25, z.pos.y + 0.55 + Math.random() * 0.2, z.pos.z - Math.cos(z.yaw) * 0.25);
        g.fx.fire(back, 0.32);
      }
      // a torn neck keeps spraying briefly
      if (z.spray > 0) {
        z.spray -= dt;
        this.headPosition(z, _head);
        _head.y -= 0.14;
        g.fx.arterialSpray(_head, _v2.set((Math.random() - 0.5) * 0.4, 1, (Math.random() - 0.5) * 0.4).normalize(), 0.9);
      }
      if (z.mixer) {
        // an 0.08 s hitch in the animation clock when hit (#18)
        if (z.hitch > 0) { z.hitch -= dt; z.mixer.timeScale = z.state === 'dead' ? 1 : 0.3; }
        else if (z.mixer.timeScale !== 1) z.mixer.timeScale = 1;
        z.mixer.update(dt);
      } else this._placeholderAnim(z, dt);
      this._applyTransform(z);
      this._postPose(z, dt);
      this._eyes(z, dt, time);
    }
    for (const z of remove) {
      const i = this.list.indexOf(z);
      if (i >= 0) this.list.splice(i, 1);
      this._recycle(z);
    }
    this._separate(dt);
    this._blockPlayer();
  }

  // Corpses lie where they fell for 8 s, then fade out. They never sink through the
  // tarmac in front of the player any more (#5).
  _dead(z, dt, remove) {
    const g = this.game;
    if (z.knockT > 0) {
      const k = clamp01(z.knockT / 0.35);
      z.pos.x += z.knockX * k * dt;
      z.pos.z += z.knockZ * k * dt;
      z.knockT -= dt;
      const h = g.nav.heightAt(z.pos.x, z.pos.y, z.pos.z);
      if (!isNaN(h) && Math.abs(h - z.pos.y) < 0.8) z.pos.y += (h - z.pos.y) * Math.min(1, dt * 12);
    }
    if (z.kind === 'dog') {
      // burn out rather than explode (#17)
      if (z.dogBurn) {
        const k = z.t < 0.9 ? z.t / 0.9 : Math.max(0, 1 - (z.t - 0.9) / 0.9);
        if (k > 0.02) {
          for (let i = 0; i < 2; i++) {
            g.fx.fire(_v.set(z.pos.x + (Math.random() - 0.5) * 0.5, z.pos.y + 0.25 + Math.random() * 0.45, z.pos.z + (Math.random() - 0.5) * 0.7), 0.35 + k * 0.6);
          }
          if (Math.random() < 0.25) g.fx.ashPuff(_v.set(z.pos.x, z.pos.y + 0.4, z.pos.z), 3, 0.7);
        }
        if (z.t > 1.5) this._setOpacity(z, Math.max(0, 1 - (z.t - 1.5) / 0.6));
        if (z.t > 2.15) remove.push(z);
      } else if (z.t > 4) remove.push(z);
      return;
    }
    if (!z.bodyFallDone && z.t > Math.min(0.75, (z.deathDur || 1.5) * 0.5)) {
      z.bodyFallDone = true;
      g.audio.playAt('zombie_bodyfall', z.pos, { volume: 0.8, rate: 0.92 + Math.random() * 0.18 });
    }
    if (z.t > 8) {
      const f = (z.t - 8) / 1.5;
      this._setOpacity(z, Math.max(0, 1 - f));
      z.pos.y -= dt * 0.1;          // a hint of settling, not a sink through the floor
      if (z.t > 9.5) remove.push(z);
    }
  }

  _applyTransform(z) {
    z.holder.rotation.set(0, z.yaw, 0);
  }

  _eyes(z, dt, time) {
    if (!z.eyeMats.length) return;
    if (z.eyeSpike > 0) z.eyeSpike -= dt;
    if (z.state === 'dead') {
      const k = Math.max(0, 1 - z.t / 1.2);
      for (const m of z.eyeMats) m.emissiveIntensity = 2.0 * k;
      return;
    }
    const spike = z.eyeSpike > 0 ? 2.7 : z.state === 'attack' ? 1.6 : 0;
    const k = 1.8 + Math.sin(time * z.eyeRate + z.eyePhase) * 0.45 + spike;
    for (const m of z.eyeMats) m.emissiveIntensity = k;
  }

  _postPose(z, dt) {
    // Everything below is *additive* on top of the sampled pose, which is only safe
    // when the mixer rewrites those bone quaternions every frame. The placeholder rig
    // has no mixer (`_placeholderAnim` only writes rotation.x on a few nodes), so an
    // additive rotateZ there would integrate forever — hence the `z.real` gate.
    z.flinch = Math.max(0, z.flinch - dt * 4);
    if (z.real) {
      // procedural hit flinch on top of the animation, pushed away from the shot (#18)
      if (z.flinch > 0 && z.state !== 'dead') {
        const f = z.flinch;
        const ca = Math.cos(z.flinchDir || 0), sa = Math.sin(z.flinchDir || 0);
        const b = z.bones.chest || z.bones.spine;
        if (b) { b.rotateX(-ca * f * 0.42); b.rotateZ(sa * f * 0.3); }
        const h = z.bones.head;
        if (h) { h.rotateX(ca * f * 0.3); h.rotateZ(-sa * f * 0.24); }
      }
      // per-instance rest-pose offsets (#20)
      if (z.shoulderL && z.bones.upperarm_L) z.bones.upperarm_L.rotateZ(z.shoulderL);
      if (z.shoulderR && z.bones.upperarm_R) z.bones.upperarm_R.rotateZ(-z.shoulderR);
    }
    // limbs / legs that are gone stay gone
    if (z.lostLimbs) for (const n of z.lostLimbs) { const b = z.bones[n]; if (b) b.scale.setScalar(0.001); }
    if (z.state !== 'dead' && z.state !== 'dogSpawn') {
      this._lookAtPlayer(z, dt);
      this._feet(z, dt);
    }
  }

  // Head/neck look-at, applied in the bone's parent space so it works whatever the
  // rig's local bone axes are (#13).
  _lookAtPlayer(z, dt) {
    if (z.kind === 'dog' || !z.real) return;
    const head = z.bones.head;
    if (!head || !head.parent) return;
    const p = this.game.player.pos;
    const dx = p.x - z.pos.x, dz = p.z - z.pos.z;
    const dist = Math.hypot(dx, dz);
    if (dist > 22) { z.lookYaw *= Math.max(0, 1 - dt * 3); z.lookPitch *= Math.max(0, 1 - dt * 3); return; }
    let yaw = wrapPi(Math.atan2(dx, dz) - z.yaw);
    const eyeY = z.crawler ? z.pos.y + 0.45 : z.pos.y + 1.6;
    let pitch = -Math.atan2((p.y + 1.5) - eyeY, Math.max(0.3, dist));
    yaw = THREE.MathUtils.clamp(yaw, -0.96, 0.96);        // +-55 deg
    pitch = THREE.MathUtils.clamp(pitch, -0.44, 0.44);    // +-25 deg
    const k = Math.min(1, dt * 4);
    z.lookYaw += (yaw - z.lookYaw) * k;
    z.lookPitch += (pitch - z.lookPitch) * k;
    if (Math.abs(z.lookYaw) < 1e-3 && Math.abs(z.lookPitch) < 1e-3) return;
    const right = _v3.set(Math.cos(z.yaw), 0, -Math.sin(z.yaw));
    this._biasBone(z.bones.neck, z.lookYaw * 0.3, z.lookPitch * 0.3, right, z.mirror);
    this._biasBone(head, z.lookYaw * 0.7, z.lookPitch * 0.7, right, z.mirror);
  }

  // Rotates `bone` about a world axis, expressed in its parent's space, so it works
  // whatever the rig's local bone axes are. `mirror` undoes the -X instance flip:
  // Matrix4.decompose() folds the flip into scale.x, so the axis needs its x negated
  // and the angle reversed (a reflection reverses handedness).
  _biasBone(bone, yaw, pitch, right, mirror) {
    if (!bone || !bone.parent) return;
    const s = mirror ? -1 : 1;
    bone.parent.getWorldQuaternion(_q1).invert();
    if (yaw) {
      _v.set(0, 1, 0).applyQuaternion(_q1);
      if (mirror) _v.x = -_v.x;
      _v.normalize();
      bone.quaternion.premultiply(_q2.setFromAxisAngle(_v, yaw * s));
    }
    if (pitch) {
      _v.copy(right).applyQuaternion(_q1);
      if (mirror) _v.x = -_v.x;
      _v.normalize();
      bone.quaternion.premultiply(_q2.setFromAxisAngle(_v, pitch * s));
    }
  }

  // footstep audio from actual foot contact, throttled and near-field only
  _feet(z, dt) {
    const g = this.game;
    if (z.stepCd > 0) z.stepCd -= dt;
    if (z.t < 0.2) return;
    if (z.pos.distanceToSquared(g.player.pos) > 225) return;   // ~15 m
    const hs = Math.hypot(z.vel.x, z.vel.z);
    if (hs < 0.25) return;
    if (z.kind === 'dog') {
      z.stepPhase += dt * Math.max(1.5, hs * 1.15);
      if (z.stepPhase >= 1) {
        z.stepPhase -= 1;
        g.audio.playAt('hellhound_footstep', z.pos, { volume: 0.45, rate: 0.92 + Math.random() * 0.22 });
      }
      return;
    }
    for (const sd of ['L', 'R']) {
      // a crawler has no feet to land — the drag sound comes off the hands
      const b = z.crawler ? (z.bones['hand_' + sd] || z.bones['foot_' + sd]) : z.bones['foot_' + sd];
      if (!b) continue;
      b.getWorldPosition(_v);
      const key = 'footY' + sd, dkey = 'footDown' + sd;
      const prev = z[key];
      z[key] = _v.y;
      const down = (_v.y - z.pos.y) < (z.crawler ? 0.3 : 0.14);
      if (down && !z[dkey] && z.stepCd <= 0 && prev !== undefined && _v.y <= prev + 0.004) {
        z.stepCd = 0.16;
        g.audio.playAt('zombie_footstep', _v, { volume: z.crawler ? 0.3 : 0.5, rate: 0.85 + Math.random() * 0.35 });
      }
      z[dkey] = down;
    }
  }

  _placeholderAnim(z, dt) {
    const r = z.root;
    const hips = r.getObjectByName('hips');
    const chest = r.getObjectByName('chest');
    if (z.state === 'dead') {
      const t = clamp01(z.t / 0.8);
      r.rotation.x = -t * Math.PI / 2 * (z.kind === 'dog' ? 0 : 1);
      r.position.y = t * 0.15;
      return;
    }
    if (z.state === 'rise') { r.position.y = -1.7 * (1 - clamp01(z.t / z.riseDur)); }
    else r.position.y = 0;
    const moving = z.vel.lengthSq() > 0.05;
    const f = z.speed * 2.8;
    if (hips) hips.position.y = 0.95 + (moving ? Math.abs(Math.sin(z.t * f)) * 0.05 : 0);
    if (chest) { chest.rotation.x = 0.25 + Math.sin(z.t * 1.3) * 0.05; chest.rotation.z = Math.sin(z.t * f * 0.5) * 0.12; }
    r.traverse(o => {
      if (o.name === 'thigh_L') o.rotation.x = moving ? Math.sin(z.t * f) * 0.5 : 0;
      if (o.name === 'thigh_R') o.rotation.x = moving ? -Math.sin(z.t * f) * 0.5 : 0;
      if (o.name === 'upperarm_L' || o.name === 'upperarm_R') {
        const atk = z.state === 'attack' || z.state === 'tear' ? Math.sin(z.t * 7) * 0.6 : 0;
        o.rotation.x = -0.2 + atk + Math.sin(z.t * 2 + (o.name === 'upperarm_L' ? 0 : 1)) * 0.1;
      }
    });
    if (z.kind === 'dog') r.position.y = moving ? Math.abs(Math.sin(z.t * 14)) * 0.08 : 0;
  }

  _faceTowards(z, x, zz, dt, rate = 6) {
    const target = Math.atan2(x - z.pos.x, zz - z.pos.z);
    let d = target - z.yaw;
    d = Math.atan2(Math.sin(d), Math.cos(d));
    z.yaw += d * Math.min(1, dt * rate);
  }

  // dirt keeps coming for as long as the body is coming out of the ground (#14)
  _riseDirt(z, amount = 1) {
    this.game.fx.dirtBurst(z.pos, amount);
  }

  _rise(z, dt) {
    if (!z.real && Math.random() < 0.3) this.game.fx.dirtBurst(z.pos, 0.5);
    if (z.t < 0.1) z.riseFx = 0;      // respawnStuck() re-enters this state
    const frac = clamp01(z.t / (z.riseDur || 2.2));
    // three staggered bursts across the rise instead of one at t=0
    if (z.riseFx === 0 && frac > 0.22) { z.riseFx = 1; this._riseDirt(z, 0.7); }
    else if (z.riseFx === 1 && frac > 0.45) { z.riseFx = 2; this._riseDirt(z, 0.55); }
    else if (z.riseFx === 2 && frac > 0.72) { z.riseFx = 3; this._riseDirt(z, 0.4); }
    this._faceTowards(z, this.game.player.pos.x, this.game.player.pos.z, dt, 2);
    if (z.t >= z.riseDur) {
      // a zombie that came out of the ground already broken collapses onto its
      // stumps instead of snapping from a standing rise straight into a crawl
      if (z.crawler && z.actions?.to_crawl) {
        z.state = 'toCrawl';
        z.t = 0;
        z.toCrawlDur = this._clipDuration(z, 'to_crawl', 0.65);
        this._play(z, 'to_crawl', { loop: false, fade: 0.15, restart: true });
        return;
      }
      z.state = 'chase';
      this._play(z, this._gaitClip(z), { fade: 0.3 });
    }
  }

  _toBarrier(z, dt) {
    const b = z.barrier;
    const target = b.outside;
    const dx = target.x - z.pos.x, dz = target.z - z.pos.z;
    const d = Math.hypot(dx, dz);
    this._syncGait(z, Math.min(z.speed, ZOMBIE.runSpeed));
    if (d < 0.12) {
      z.state = 'tear';
      z.t = 0;
      z.vel.set(0, 0, 0);
      this._play(z, z.crawler ? 'crawl' : 'idle', { fade: 0.2 });
      return;
    }
    const sp = Math.min(z.speed, ZOMBIE.runSpeed);
    z.vel.set(dx / d * sp, 0, dz / d * sp);
    const step = Math.min(d, sp * dt);
    z.pos.x += dx / d * step; z.pos.z += dz / d * step;
    const h = this.game.collision.ground(z.pos.x, z.pos.z, z.pos.y + 1.0, 3);
    if (h !== null) z.pos.y += (h - z.pos.y) * Math.min(1, dt * 10);
    this._faceTowards(z, target.x, target.z, dt, 8);
  }

  _tear(z, dt, time) {
    const b = z.barrier;
    const g = this.game;
    // face through the window
    this._faceTowards(z, b.inside.x, b.inside.z, dt, 8);
    z.vel.set(0, 0, 0);
    // player standing right at the window gets swiped through it
    const pd = Math.hypot(g.player.pos.x - b.inside.x, g.player.pos.z - b.inside.z);
    if (!g.player.downed && pd < 1.2 && b.boardsUp() < 6) {
      if (!z.swipe) { z.swipe = true; z.t = 0; this._play(z, this._attackClip(z), { loop: false, fade: 0.15, restart: true }); z.hitDone = false; }
      const dur = this._clipDuration(z, this._attackClip(z), 0.9);
      if (!z.hitDone && z.t > dur * 0.45) {
        z.hitDone = true;
        if (pd < 1.35) g.hurtPlayer(ZOMBIE.hitDamage, z);
      }
      if (z.t > dur) { z.swipe = false; z.t = 0; }
      return;
    }
    z.swipe = false;
    if (b.boardsUp() === 0) {
      if (b.climber && b.climber !== z && b.climber.state === 'climb') return; // wait for the window
      b.climber = z;
      z.state = 'climb';
      z.t = 0;
      z.climbDur = this._clipDuration(z, 'climb', 1.8);
      // square up to the window so the clip's root motion carries it straight through
      z.pos.x = b.outside.x; z.pos.z = b.outside.z;
      z.yaw = Math.atan2(b.marker.forward.x, b.marker.forward.z);
      z.climbFrom = z.pos.clone();
      z.climbTo = b.inside.clone();
      this._play(z, 'climb', { loop: false, fade: 0.15 });
      return;
    }
    // a crawler claws at the boards from the floor, it does not stand up to do it
    const tearClip = z.crawler ? this._attackClip(z) : 'tear';
    const dur = this._clipDuration(z, tearClip, 1.2);
    if (!z.tearing) {
      z.tearing = true; z.t = 0; z.tornThis = false;
      this._play(z, tearClip, { loop: false, fade: 0.15, restart: true });
    }
    if (!z.tornThis && z.t > dur * 0.55) {
      z.tornThis = true;
      b.tearBoard(z);
    }
    if (z.t > dur + 0.1 + Math.random() * 0.3) z.tearing = false;
  }

  _climb(z, dt) {
    const t = clamp01(z.t / z.climbDur);
    z.yaw = Math.atan2(z.climbTo.x - z.climbFrom.x, z.climbTo.z - z.climbFrom.z);
    if (!z.real) {
      z.pos.lerpVectors(z.climbFrom, z.climbTo, t);
      z.pos.y = THREE.MathUtils.lerp(z.climbFrom.y, z.climbTo.y, t) + Math.sin(t * Math.PI) * 0.9;
    }
    if (t >= 1) {
      z.pos.copy(z.climbTo);
      if (z.barrier.climber === z) z.barrier.climber = null;
      z.barrier = null;
      z.state = 'chase';
      if (z.current) z.current.stop();
      z.current = null;
      this._play(z, this._gaitClip(z), { fade: 0 });
    }
  }

  _syncGait(z, speed) {
    const clip = this._gaitClip(z);
    const nominal = z.kind === 'dog' ? CLIP_SPEED.dogRun : CLIP_SPEED[clip] || 1;
    const a = this._play(z, clip, { fade: 0.3 });
    // each zombie runs its own clock, so a pack never converges on one stride (#3)
    if (a) a.timeScale = THREE.MathUtils.clamp(speed / nominal, 0.45, 1.9) * (z.rateJitter || 1);
  }

  _attackClip(z) { return z.crawler && z.actions?.crawl_attack ? 'crawl_attack' : 'attack'; }

  _chase(z, dt, time) {
    const g = this.game, p = g.player, nav = g.nav;
    if (p.downed && g.soloDowned) { z.state = 'wander'; z.t = 0; return; }
    const dx = p.pos.x - z.pos.x, dz = p.pos.z - z.pos.z;
    const d = Math.hypot(dx, dz);
    const dy = Math.abs(p.pos.y - z.pos.y);
    const atkRange = z.kind === 'dog' ? 1.6 : ZOMBIE.attackRange;
    if (d < atkRange && dy < 1.2) {
      // stagger the decision so a pack doesn't swing on the same frame (#3)
      z.attackT = (z.attackT || 0) + dt;
      if (z.attackT >= (z.attackDelay || 0)) {
        z.attackT = 0;
        z.state = 'attack'; z.t = 0; z.hitDone = false;
        this._play(z, this._attackClip(z), { loop: false, fade: 0.15, restart: true });
        if (z.kind === 'zombie') g.audio.playAt('zombie_attack', z.pos, { volume: 0.9, rate: 0.92 + Math.random() * 0.18 });
        else g.audio.playAt('hellhound_bite', z.pos, { volume: 0.9 });
        return;
      }
    } else z.attackT = 0;
    // steering
    let dir = null;
    if ((d < 1.5 && dy < 1.2) || (d < 9 && nav.lineClear(z.pos.x, z.pos.y, z.pos.z, p.pos.x, p.pos.y, p.pos.z))) dir = _dir.set(dx / d, 0, dz / d);
    else dir = nav.direction(z.pos.x, z.pos.y, z.pos.z, _dir);
    if (!dir) dir = _dir.set(dx / (d || 1), 0, dz / (d || 1));
    // side-step: the grid is 0.5 m, so a thin prop (a mannequin, a post) can sit right on the
    // line to the next cell and pin the body with the push-out exactly opposing the steering.
    // Swing the heading for a moment, alternating sides, until it gets round.
    if (z.sideT > 0) {
      z.sideT -= dt;
      const c = Math.cos(1.2 * z.sideSign), s = Math.sin(1.2 * z.sideSign);
      dir.set(dir.x * c - dir.z * s, 0, dir.x * s + dir.z * c);
    }

    const sp = z.speed * (z.slow ? 0.5 : 1);
    z.vel.x += (dir.x * sp - z.vel.x) * Math.min(1, dt * 6);
    z.vel.z += (dir.z * sp - z.vel.z) * Math.min(1, dt * 6);
    const ox = z.pos.x, oz = z.pos.z;
    z.pos.x += z.vel.x * dt;
    z.pos.z += z.vel.z * dt;
    // collide with the level
    this._collide(z);
    const moved = Math.hypot(z.pos.x - ox, z.pos.z - oz);
    if (sp > 0.3 && moved < sp * dt * 0.25) z.blockT = (z.blockT || 0) + dt;
    else z.blockT = Math.max(0, (z.blockT || 0) - dt * 2);
    if (z.blockT > 0.35 && !(z.sideT > 0)) {
      z.blockT = 0; z.sideT = 0.55;
      z.sideSign = z.sideSign === 1 ? -1 : 1;
    }
    // stick to ground
    const h = nav.heightAt(z.pos.x, z.pos.y, z.pos.z);
    if (!isNaN(h) && Math.abs(h - z.pos.y) < 0.8) z.pos.y += (h - z.pos.y) * Math.min(1, dt * 12);
    const hs = Math.hypot(z.vel.x, z.vel.z);
    if (hs > 0.1) this._faceTowards(z, z.pos.x + z.vel.x, z.pos.z + z.vel.z, dt, z.kind === 'dog' ? 10 : z.crawler ? 3 : 5);
    this._syncGait(z, hs);

    // stuck detection -> respawn elsewhere (like the original game does)
    const nd = nav.distanceAt(z.pos.x, z.pos.y, z.pos.z);
    if (nd < z.bestDist - 0.5) { z.bestDist = nd; z.stuckT = 0; }
    else z.stuckT += dt;
    if (z.stuckT > 9 && d > 6) { z.stuckT = 0; z.bestDist = Infinity; g.respawnStuck?.(z); }
  }

  _collide(z) {
    const r = z.kind === 'dog' ? 0.28 : z.crawler ? 0.3 : ZOMBIE.radius;
    if (z.crawler) {
      _start.set(z.pos.x, z.pos.y + 0.18 + r, z.pos.z);
      _end.set(z.pos.x, z.pos.y + 0.55, z.pos.z);
    } else {
      _start.set(z.pos.x, z.pos.y + 0.45 + r, z.pos.z);
      _end.set(z.pos.x, z.pos.y + 1.5, z.pos.z);
    }
    this.game.collision.capsule(_start, _end, r, { doors: true, barriers: true });
    z.pos.x = _start.x; z.pos.z = _start.z;
  }

  _attack(z, dt, time) {
    const g = this.game, p = g.player;
    const clip = this._attackClip(z);
    const dur = this._clipDuration(z, clip, z.kind === 'dog' ? 0.8 : 0.9);
    this._faceTowards(z, p.pos.x, p.pos.z, dt, 8);
    const d = Math.hypot(p.pos.x - z.pos.x, p.pos.z - z.pos.z);
    if (z.kind === 'dog' && z.t < dur * 0.4 && d > 0.9) {
      // lunge
      z.pos.x += Math.sin(z.yaw) * 5 * dt; z.pos.z += Math.cos(z.yaw) * 5 * dt;
      this._collide(z);
    } else if (d > 0.8) {
      z.pos.x += Math.sin(z.yaw) * 0.5 * dt; z.pos.z += Math.cos(z.yaw) * 0.5 * dt;
      this._collide(z);
    }
    z.vel.set(0, 0, 0);
    if (!z.hitDone && z.t > dur * 0.45) {
      z.hitDone = true;
      const range = z.kind === 'dog' ? 1.8 : ZOMBIE.hitRange;
      if (d < range && Math.abs(p.pos.y - z.pos.y) < 1.3) g.hurtPlayer(z.kind === 'dog' ? 40 : ZOMBIE.hitDamage, z);
    }
    if (z.t >= dur) {
      z.state = 'chase';
      this._play(z, this._gaitClip(z), { fade: 0.2 });
    }
  }

  _wander(z, dt) {
    const g = this.game;
    if (!g.player.downed) { z.state = 'chase'; this._play(z, this._gaitClip(z), { fade: 0.3 }); return; }
    // shamble away from the downed player
    const dx = z.pos.x - g.player.pos.x, dz = z.pos.z - g.player.pos.z;
    const d = Math.hypot(dx, dz) || 1;
    if (d < 12) {
      const sp = z.crawler ? ZOMBIE.walkSpeed * 0.85 : ZOMBIE.walkSpeed;
      z.vel.set(dx / d * sp, 0, dz / d * sp);
      z.pos.addScaledVector(z.vel, dt);
      this._collide(z);
      this._faceTowards(z, z.pos.x + z.vel.x, z.pos.z + z.vel.z, dt, 3);
      this._syncGait(z, sp);
    } else { z.vel.set(0, 0, 0); this._play(z, z.crawler ? 'crawl' : 'idle', { fade: 0.4 }); }
    const h = g.nav.heightAt(z.pos.x, z.pos.y, z.pos.z);
    if (!isNaN(h) && Math.abs(h - z.pos.y) < 0.8) z.pos.y += (h - z.pos.y) * Math.min(1, dt * 12);
  }

  _dogSpawn(z, dt) {
    const g = this.game;
    if (!z.struck && z.t > 0.05) {
      z.struck = true;
      g.fx.lightning?.(z.pos);
      g.audio.playAt('hellhound_spawn', z.pos, { volume: 1 });
    }
    if (z.t > 0.8) {
      z.struck = false;
      z.holder.visible = true;
      z.state = 'chase';
      g.fx.glowBurst(_v.set(z.pos.x, z.pos.y + 0.5, z.pos.z), [4, 2, 0.8, 1], 30, 4);
      this._play(z, 'run', { fade: 0 });
      g.audio.playAt('hellhound_growl', z.pos, { volume: 0.9 });
    }
  }

  _audio(z, dt) {
    z.groanT -= dt;
    if (z.groanT <= 0) {
      const g = this.game;
      const d = z.pos.distanceTo(g.player.pos);
      z.groanT = 3 + Math.random() * 6;
      if (d < 35) {
        if (z.kind === 'dog') g.audio.playAt('hellhound_growl', z.pos, { volume: 0.7 });
        else g.audio.playAt(z.gait === 'sprint' && Math.random() < 0.5 ? 'zombie_scream' : 'zombie_groan', z.pos, { volume: 0.85, rate: (z.crawler ? 0.78 : 0.9) + Math.random() * 0.25 });
      }
    }
  }

  _separate(dt) {
    const L = this.list;
    for (let i = 0; i < L.length; i++) {
      const a = L[i];
      if (a.state === 'dead' || a.state === 'climb' || a.state === 'rise' || a.state === 'dogSpawn') continue;
      for (let j = i + 1; j < L.length; j++) {
        const b = L[j];
        if (b.state === 'dead' || b.state === 'climb' || b.state === 'rise' || b.state === 'dogSpawn') continue;
        const dx = b.pos.x - a.pos.x, dz = b.pos.z - a.pos.z;
        const d2 = dx * dx + dz * dz;
        const min = a.crawler || b.crawler ? 0.5 : 0.62;
        if (d2 < min * min && d2 > 1e-6 && Math.abs(a.pos.y - b.pos.y) < 1) {
          const d = Math.sqrt(d2), push = (min - d) * 0.5;
          const nx = dx / d, nz = dz / d;
          const aw = a.state === 'tear' ? 0 : 1, bw = b.state === 'tear' ? 0 : 1;
          a.pos.x -= nx * push * aw; a.pos.z -= nz * push * aw;
          b.pos.x += nx * push * bw; b.pos.z += nz * push * bw;
        }
      }
    }
  }

  _blockPlayer() {
    const p = this.game.player;
    for (const z of this.list) {
      if (z.state === 'dead' || z.state === 'dogSpawn' || z.state === 'rise') continue;
      const dx = p.pos.x - z.pos.x, dz = p.pos.z - z.pos.z;
      const d = Math.hypot(dx, dz);
      const min = z.crawler ? 0.5 : 0.62;
      if (d < min && d > 1e-4 && Math.abs(p.pos.y - z.pos.y) < 1.5) {
        p.pos.x += dx / d * (min - d);
        p.pos.z += dz / d * (min - d);
      }
    }
  }
}
