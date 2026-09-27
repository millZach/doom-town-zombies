import * as THREE from 'three';

/**
 * Tracer rounds.
 *
 * `Particles.tracer()` (owned by another stream) spawns a single fixed-size stretched sprite, so the
 * "bright head + dim tail" the review asks for cannot be expressed through it. This is a small
 * self-contained system instead: every tracer is drawn as *two* camera-facing quads of different
 * size and brightness — a short, wide, white-hot head and a long, thin, dim tail that trails behind
 * it — flying from the muzzle to the impact point at a real projectile speed.
 *
 * Everything is pooled: one geometry, one material, one InstancedMesh (2 instances per live tracer),
 * DynamicDrawUsage, no allocation per shot or per frame.
 */

const MAX = 24;                 // live tracers; 2 instances each
const SPEED = 380;              // m/s — fast enough to read as a streak, slow enough to see
const HEAD_LEN = 1.1;           // metres
const HEAD_W = 0.055;
const TAIL_LEN = 5.0;
const TAIL_W = 0.026;

const _m = new THREE.Matrix4();
const _q = new THREE.Quaternion();
const _c = new THREE.Color();
const _x = new THREE.Vector3();
const _y = new THREE.Vector3();
const _z = new THREE.Vector3();
const _p = new THREE.Vector3();
const _view = new THREE.Vector3();

let _tex = null;
function streakTexture() {
  if (_tex) return _tex;
  const W = 32, H = 128;
  const c = document.createElement('canvas');
  c.width = W; c.height = H;
  const g = c.getContext('2d');
  g.clearRect(0, 0, W, H);
  // v = 1 (top of the quad) is the head end: opaque, fading to nothing at the tail end,
  // with a soft falloff across the width so the edges never show as a hard rectangle.
  const img = g.createImageData(W, H);
  for (let y = 0; y < H; y++) {
    const v = 1 - y / (H - 1);                       // 1 at the head
    const along = Math.pow(v, 1.6);                  // bright head, long soft fade
    for (let x = 0; x < W; x++) {
      const u = (x + 0.5) / W * 2 - 1;               // -1..1 across
      const across = Math.max(0, 1 - u * u);
      const a = along * across * across;
      const i = (y * W + x) * 4;
      img.data[i] = 255; img.data[i + 1] = 255; img.data[i + 2] = 255;
      img.data[i + 3] = Math.min(255, a * 255) | 0;
    }
  }
  g.putImageData(img, 0, 0);
  _tex = new THREE.CanvasTexture(c);
  _tex.colorSpace = THREE.SRGBColorSpace;
  _tex.minFilter = THREE.LinearMipmapLinearFilter;
  _tex.wrapS = _tex.wrapT = THREE.ClampToEdgeWrapping;
  return _tex;
}

class Tracer {
  constructor() {
    this.active = false;
    this.from = new THREE.Vector3();
    this.dir = new THREE.Vector3(0, 0, -1);
    this.dist = 0;
    this.t = 0;
    this.life = 0;
    this.head = [5, 3.2, 1.6, 0.9];
    this.tail = [2, 1.3, 0.6, 0.3];
  }
}

export class TracerSystem {
  constructor() {
    this.scene = null;
    this.enabled = true;
    this.pool = [];
    for (let i = 0; i < MAX; i++) this.pool.push(new Tracer());
    this.next = 0;

    const geo = new THREE.PlaneGeometry(1, 1);       // local +Y is the direction of travel
    const mat = new THREE.MeshBasicMaterial({
      map: streakTexture(), transparent: true, depthWrite: false,
      blending: THREE.AdditiveBlending, side: THREE.DoubleSide, toneMapped: false,
      name: 'tracer',
    });
    this.mesh = new THREE.InstancedMesh(geo, mat, MAX * 2);
    this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX * 2 * 3), 3);
    this.mesh.instanceColor.setUsage(THREE.DynamicDrawUsage);
    this.mesh.frustumCulled = false;
    this.mesh.castShadow = this.mesh.receiveShadow = false;
    this.mesh.count = 0;
    this.geo = geo;
    this.mat = mat;
  }

  /** Idempotent — the weapon code calls this every frame because it is the thing that knows the scene. */
  attach(scene) {
    if (!scene || this.scene === scene) return;
    this.scene = scene;
    scene.add(this.mesh);
  }

  /**
   * @param from  world-space muzzle
   * @param to    world-space impact point
   * @param head  [r,g,b,a] of the hot core
   * @param tail  [r,g,b,a] of the trailing streak (dimmer, and drawn much thinner/longer)
   */
  spawn(from, to, head, tail) {
    if (!this.enabled) return;
    _p.subVectors(to, from);
    const dist = _p.length();
    if (dist < 0.35) return;                          // muzzle-contact shot: nothing to streak
    const s = this._take();
    s.active = true;
    s.from.copy(from);
    s.dir.copy(_p).divideScalar(dist);
    s.dist = dist;
    s.t = 0;
    s.life = Math.min(0.28, dist / SPEED + 0.035);    // +35 ms so short shots still register
    if (head) s.head = head;
    if (tail) s.tail = tail;
  }

  clear() { for (const s of this.pool) s.active = false; }

  _take() {
    for (let i = 0; i < this.pool.length; i++) {
      const s = this.pool[(this.next + i) % this.pool.length];
      if (!s.active) { this.next = (this.next + i + 1) % this.pool.length; return s; }
    }
    const s = this.pool[this.next];
    this.next = (this.next + 1) % this.pool.length;
    return s;
  }

  update(dt, camera) {
    if (!this.scene || dt <= 0) return;
    let n = 0;
    const cam = camera ? camera.position : null;
    for (const s of this.pool) {
      if (!s.active) continue;
      s.t += dt;
      if (s.t >= s.life) { s.active = false; continue; }
      const u = s.t / s.life;
      // the head races down the ray and stops at the impact point; the tail catches up behind it
      const travelled = Math.min(s.dist, u * s.dist + 0.001);
      const fade = u < 0.7 ? 1 : 1 - (u - 0.7) / 0.3;
      // head: short, wide, hot. tail: long, thin, dim — two genuinely different quads.
      const headLen = Math.min(HEAD_LEN, travelled);
      const tailStart = Math.max(0, travelled - headLen - TAIL_LEN);
      const tailLen = Math.max(0, travelled - headLen - tailStart);
      n = this._segment(n, s, travelled - headLen, headLen, HEAD_W, s.head, fade, cam);
      if (tailLen > 0.2) n = this._segment(n, s, tailStart, tailLen, TAIL_W, s.tail, fade * 0.85, cam);
    }
    this.mesh.count = n;
    if (n) { this.mesh.instanceMatrix.needsUpdate = true; this.mesh.instanceColor.needsUpdate = true; }
  }

  /** One camera-facing quad from `start` metres along the ray, `len` long and `w` wide. */
  _segment(n, s, start, len, w, col, fade, cam) {
    if (n >= MAX * 2 || len <= 0.001) return n;
    _p.copy(s.from).addScaledVector(s.dir, start + len * 0.5);
    _y.copy(s.dir);
    if (cam) _view.subVectors(_p, cam); else _view.set(0, 0, 1);
    _x.crossVectors(_y, _view);
    if (_x.lengthSq() < 1e-8) _x.set(1, 0, 0).cross(_y);       // dead-on shot: any perpendicular
    if (_x.lengthSq() < 1e-8) _x.set(0, 1, 0);
    _x.normalize();
    _z.crossVectors(_x, _y).normalize();
    _m.makeBasis(_x, _y, _z);
    _q.setFromRotationMatrix(_m);
    _m.compose(_p, _q, _view.set(w, len, 1));
    this.mesh.setMatrixAt(n, _m);
    const a = (col[3] ?? 1) * fade;
    _c.setRGB(col[0] * a, col[1] * a, col[2] * a);
    this.mesh.setColorAt(n, _c);
    return n + 1;
  }
}
