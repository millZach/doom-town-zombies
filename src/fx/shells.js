import * as THREE from 'three';

/**
 * Ejected cases.
 *
 * A shell is born in the *viewmodel* scene (camera space) so it inherits the weapon FOV and reads
 * at the right size next to the gun, then — once it has cleared the frame — it is handed off to the
 * world scene where it falls, bounces off the map and settles on the floor. The ground contact is
 * what plays `shell_drop` / `shell_drop_shotgun`, so the tinkle always lines up with the bounce
 * instead of being a fixed delay after the shot.
 *
 * Everything is pooled: two InstancedMeshes per case type (one per scene), no allocation per shot.
 */

const CASE_TYPES = {
  brass: {
    radius: 0.0049, length: 0.0245,
    body: new THREE.Color(0xb08d2a), rim: new THREE.Color(0x7d6320),
    sound: 'shell_drop', soundFallback: 'shell_drop',
    volume: 0.4, bounceLoss: 0.42, spin: 34,
  },
  shotshell: {
    radius: 0.0094, length: 0.068,
    body: new THREE.Color(0x8e1a18), rim: new THREE.Color(0xb59034),
    sound: 'shell_drop_shotgun', soundFallback: 'shell_drop',
    volume: 0.55, bounceLoss: 0.28, spin: 20,
  },
};

const POOL = 28;            // per case type, per scene pass — plenty for a 100-round RPD belt
const VM_LIFE = 0.30;       // seconds a case spends in viewmodel space before the hand-off
const WORLD_LIFE = 7.0;     // seconds a settled case stays on the floor

const _m = new THREE.Matrix4();
const _basis = new THREE.Matrix4();
const _q = new THREE.Quaternion();
const _e = new THREE.Euler();
const _v = new THREE.Vector3();
const _v2 = new THREE.Vector3();
const _v3 = new THREE.Vector3();

function caseGeometry(type) {
  // cylinder along local +Z, with a darker rim / brighter head baked into vertex colours
  const geo = new THREE.CylinderGeometry(type.radius, type.radius * 0.94, type.length, 10, 1, false);
  geo.rotateX(Math.PI / 2);
  const pos = geo.attributes.position;
  const col = new Float32Array(pos.count * 3);
  const half = type.length * 0.5;
  for (let i = 0; i < pos.count; i++) {
    const z = pos.getZ(i);
    // head (rim / primer end) is at +Z (the case flies base-first out of the port)
    const head = z > half - type.length * 0.22 ? 1 : 0;
    const c = head ? type.rim : type.body;
    const shade = 0.85 + 0.3 * (pos.getY(i) / type.radius * 0.5 + 0.5);
    col[i * 3] = c.r * shade; col[i * 3 + 1] = c.g * shade; col[i * 3 + 2] = c.b * shade;
  }
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  return geo;
}

class Shell {
  constructor() {
    this.active = false;
    this.space = 'vm';
    this.kind = 'brass';
    this.pos = new THREE.Vector3();
    this.vel = new THREE.Vector3();
    this.quat = new THREE.Quaternion();
    this.spin = new THREE.Vector3();
    this.age = 0;
    this.scale = 1;
    this.bounces = 0;
    this.resting = false;
    this.restT = 0;
  }
}

export class ShellSystem {
  /** @param vmParent  an object in the viewmodel scene whose transform is identity (the holder). */
  constructor(vmParent) {
    this.vmScene = vmParent;
    this.worldScene = null;
    this.collision = null;
    this.audio = null;
    this.enabled = true;
    this.shells = [];
    for (let i = 0; i < POOL * 2; i++) this.shells.push(new Shell());
    this.next = 0;

    this.meshes = {};           // kind -> { vm, world, geo, mat }
    for (const k of Object.keys(CASE_TYPES)) {
      const type = CASE_TYPES[k];
      const geo = caseGeometry(type);
      const mat = new THREE.MeshStandardMaterial({
        vertexColors: true, metalness: 0.85, roughness: 0.33,
        envMapIntensity: 1.0, name: `shell_${k}`,
      });
      const vm = new THREE.InstancedMesh(geo, mat, POOL);
      vm.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      vm.frustumCulled = false;
      vm.castShadow = false; vm.receiveShadow = false;
      vm.renderOrder = 6;
      vm.count = 0;
      vmParent.add(vm);
      const world = new THREE.InstancedMesh(geo, mat, POOL);
      world.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      world.frustumCulled = false;
      world.castShadow = false; world.receiveShadow = true;
      world.count = 0;
      this.meshes[k] = { vm, world, geo, mat };
    }

    this._camPrev = new THREE.Vector3();
    this._camVel = new THREE.Vector3();
    this._hasCamPrev = false;
    this._gravityVm = new THREE.Vector3(0, -9.8, 0);
  }

  /** Called once by the weapon code, which is the thing that knows about the world scene. */
  attachWorld(scene, collision, audio) {
    if (this.worldScene === scene) return;
    this.worldScene = scene;
    this.collision = collision || null;
    this.audio = audio || null;
    for (const k of Object.keys(this.meshes)) scene.add(this.meshes[k].world);
  }

  /**
   * Spawn a case.
   * @param kind   'brass' | 'shotshell'
   * @param pos    viewmodel-space (= camera-space) position, normally the `eject` locator
   * @param vel    viewmodel-space velocity, m/s
   * @param spin   angular velocity, rad/s
   * @param scale  size multiplier (calibre)
   */
  spawn(kind, pos, vel, spin, scale = 1) {
    if (!this.enabled || !CASE_TYPES[kind]) return null;
    const s = this._take();
    s.active = true;
    s.space = 'vm';
    s.kind = kind;
    s.pos.copy(pos);
    s.vel.copy(vel);
    s.quat.setFromEuler(_e.set(Math.random() * 6.28, Math.random() * 6.28, Math.random() * 6.28));
    if (spin) s.spin.copy(spin);
    else {
      const k = CASE_TYPES[kind].spin;
      s.spin.set((Math.random() - 0.5) * 2 * k, (Math.random() - 0.5) * 1.2 * k, (Math.random() - 0.5) * 2.4 * k);
    }
    s.age = 0;
    s.scale = scale;
    s.bounces = 0;
    s.resting = false;
    s.restT = 0;
    s.pinged = false;
    return s;
  }

  /**
   * The bounce is what normally makes the noise. If there is no world scene or no collision system
   * to bounce against, fall back to a scheduled tinkle so the shot is never silent.
   */
  _fallbackPing(s) {
    const a = this.audio;
    if (!a || s.pinged) return;
    const type = CASE_TYPES[s.kind];
    let name = type.sound;
    if (a.has && !a.has(name)) name = type.soundFallback;
    if (a.has && !a.has(name)) return;
    s.pinged = true;
    a.play(name, {
      volume: type.volume * 0.7,
      rate: 0.9 + Math.random() * 0.25,
      delay: 0.3 + Math.random() * 0.18,
    });
  }

  _take() {
    // prefer a free slot, otherwise recycle the oldest world-space case
    for (let i = 0; i < this.shells.length; i++) {
      const s = this.shells[(this.next + i) % this.shells.length];
      if (!s.active) { this.next = (this.next + i + 1) % this.shells.length; return s; }
    }
    // everything is busy: steal the case that has been lying on the floor the longest
    let oldest = null;
    for (const s of this.shells) if (s.space === 'world' && (!oldest || s.age > oldest.age)) oldest = s;
    return oldest || this.shells[0];
  }

  clear() {
    for (const s of this.shells) s.active = false;
  }

  update(dt, worldCamera) {
    if (dt <= 0) return;
    // camera velocity, so cases handed to the world inherit the player's motion
    if (worldCamera) {
      if (this._hasCamPrev) this._camVel.subVectors(worldCamera.position, this._camPrev).divideScalar(Math.max(dt, 1e-4));
      this._camPrev.copy(worldCamera.position);
      this._hasCamPrev = true;
      // gravity expressed in camera space (viewmodel scene is camera space)
      _q.copy(worldCamera.quaternion).invert();
      this._gravityVm.set(0, -9.8, 0).applyQuaternion(_q);
    }

    const counts = {};
    for (const k of Object.keys(this.meshes)) counts[k] = { vm: 0, world: 0 };

    for (const s of this.shells) {
      if (!s.active) continue;
      s.age += dt;
      if (s.space === 'vm') {
        s.vel.addScaledVector(this._gravityVm, dt);
        s.pos.addScaledVector(s.vel, dt);
        this._spinStep(s, dt);
        if (s.age >= VM_LIFE) this._toWorld(s, worldCamera);
      } else {
        this._stepWorld(s, dt);
      }
      if (!s.active) continue;

      const m = this.meshes[s.kind];
      if (!m) { s.active = false; continue; }
      const target = s.space === 'vm' ? m.vm : m.world;
      const slot = s.space === 'vm' ? counts[s.kind].vm : counts[s.kind].world;
      if (slot >= POOL) continue;
      let sc = s.scale;
      if (s.resting) {
        const fade = 1 - Math.max(0, (s.restT - (WORLD_LIFE - 0.5)) / 0.5);
        sc *= Math.max(0, fade);
        if (fade <= 0) { s.active = false; continue; }
      }
      _m.compose(s.pos, s.quat, _v.set(sc, sc, sc));
      target.setMatrixAt(slot, _m);
      if (s.space === 'vm') counts[s.kind].vm++; else counts[s.kind].world++;
    }

    for (const k of Object.keys(this.meshes)) {
      const m = this.meshes[k];
      m.vm.count = counts[k].vm;
      m.world.count = counts[k].world;
      if (counts[k].vm) m.vm.instanceMatrix.needsUpdate = true;
      if (counts[k].world) m.world.instanceMatrix.needsUpdate = true;
    }
  }

  _spinStep(s, dt) {
    const w = s.spin;
    const len = w.length();
    if (len < 1e-4) return;
    _q.setFromAxisAngle(_v.copy(w).divideScalar(len), len * dt);
    s.quat.premultiply(_q).normalize();
  }

  _toWorld(s, worldCamera) {
    if (!this.worldScene || !worldCamera) { this._fallbackPing(s); s.active = false; return; }
    if (!this.collision) this._fallbackPing(s);
    s.space = 'world';
    s.age = 0;
    s.pos.applyMatrix4(worldCamera.matrixWorld);
    s.vel.applyQuaternion(worldCamera.quaternion).add(this._camVel);
    s.spin.applyQuaternion(worldCamera.quaternion);
  }

  _stepWorld(s, dt) {
    if (s.resting) {
      s.restT += dt;
      if (s.restT > WORLD_LIFE) s.active = false;
      return;
    }
    if (s.age > 6) { this._fallbackPing(s); s.active = false; return; }
    s.vel.y -= 9.8 * dt;
    this._spinStep(s, dt);
    const step = s.vel.length() * dt;
    if (step < 1e-5) return;
    _v.copy(s.vel).divideScalar(s.vel.length());
    const type = CASE_TYPES[s.kind];
    const hit = this.collision ? this.collision.raycast(s.pos, _v, step + 0.01, { doors: true, barriers: false }) : null;
    if (hit) {
      s.pos.copy(hit.point).addScaledVector(hit.normal, 0.004);
      const vn = s.vel.dot(hit.normal);
      // split into normal / tangential: the normal part bounces with restitution, the tangential
      // part is scrubbed by friction. Brass skitters; a shotshell mostly flops and stops.
      _v3.copy(hit.normal).multiplyScalar(vn);
      s.vel.sub(_v3).multiplyScalar(0.72);
      s.vel.addScaledVector(hit.normal, -vn * type.bounceLoss);
      s.vel.x += (Math.random() - 0.5) * 0.25;
      s.vel.z += (Math.random() - 0.5) * 0.25;
      s.spin.multiplyScalar(0.5);
      s.bounces++;
      const impact = Math.abs(vn);
      if (s.bounces <= 3 && impact > 0.4) this._ping(s, type, Math.min(1, impact / 3));
      if (s.bounces >= 4 || s.vel.lengthSq() < 0.1) {
        s.resting = true;
        s.restT = 0;
        // lie flat on the surface
        _v2.set(0, 0, 1).applyQuaternion(s.quat);
        _v2.addScaledVector(hit.normal, -_v2.dot(hit.normal));
        if (_v2.lengthSq() < 1e-6) _v2.set(1, 0, 0);
        _v2.normalize();
        _v3.crossVectors(hit.normal, _v2).normalize();
        _basis.makeBasis(_v3, hit.normal, _v2);
        s.quat.setFromRotationMatrix(_basis);
        s.pos.addScaledVector(hit.normal, type.radius * 0.6);
        s.vel.set(0, 0, 0);
      }
    } else {
      s.pos.addScaledVector(s.vel, dt);
    }
  }

  _ping(s, type, k) {
    const a = this.audio;
    if (!a) return;
    s.pinged = true;
    let name = type.sound;
    if (a.has && !a.has(name)) name = type.soundFallback;
    if (a.has && !a.has(name)) return;
    a.playAt(name, s.pos, {
      volume: type.volume * (0.55 + 0.45 * k),
      rate: 0.9 + Math.random() * 0.25,
    });
  }
}
