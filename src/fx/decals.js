import * as THREE from 'three';

// Ring-buffered instanced decals (bullet holes, scorch, blood pools/splats) on collision surfaces.
function canvasTex(draw, size = 128) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  draw(c.getContext('2d'), size);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function rng(seed) { let s = seed; return () => ((s = (s * 16807) % 2147483647) / 2147483647); }

const _white = new THREE.Color(1, 1, 1);
const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now()) / 1000;

class DecalSet {
  /**
   * opts.fade = { hold, over, floor } gives every instance its own age-driven alpha:
   * full strength for `hold` seconds, then a `over`-second fade down to `floor`.
   * It rides on `instanceColor` (which three multiplies into diffuseColor.rgb), and
   * the injected line moves that factor onto the alpha instead. No per-frame
   * allocation, and the whole thing is driven from the mesh's own onBeforeRender so
   * it needs no update() call from the game loop.
   */
  constructor(scene, tex, max, opts = {}) {
    this.max = max;
    this.i = 0;
    const mat = new THREE.MeshStandardMaterial({
      map: tex, transparent: true, depthWrite: false, roughness: opts.roughness ?? 0.9, metalness: 0,
      polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4,
      color: opts.color ?? 0xffffff,
    });
    this.mesh = new THREE.InstancedMesh(new THREE.PlaneGeometry(1, 1), mat, max);
    this.mesh.count = 0;
    this.mesh.receiveShadow = true;
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 5;
    scene.add(this.mesh);
    this._m = new THREE.Matrix4();
    this._q = new THREE.Quaternion();
    this._q2 = new THREE.Quaternion();
    this._p = new THREE.Vector3();
    this._s = new THREE.Vector3();
    this._z = new THREE.Vector3(0, 0, 1);

    this.fade = opts.fade || null;
    if (this.fade) {
      this.born = new Float64Array(max).fill(-1e6);
      for (let i = 0; i < max; i++) this.mesh.setColorAt(i, _white);
      this.mesh.instanceColor.setUsage(THREE.DynamicDrawUsage);
      mat.onBeforeCompile = sh => {
        sh.fragmentShader = sh.fragmentShader.replace(
          '#include <color_fragment>',
          '#include <color_fragment>\n\tdiffuseColor.a *= vColor.r;\n\tdiffuseColor.rgb /= max( vColor.r, 0.001 );');
      };
      this.mesh.onBeforeRender = () => this._ageFade();
    }
  }

  _ageFade() {
    const { hold, over, floor } = this.fade;
    const arr = this.mesh.instanceColor.array;
    const t = now();
    let dirty = false;
    for (let i = 0; i < this.mesh.count; i++) {
      const age = t - this.born[i];
      const k = age <= hold ? 1 : Math.max(floor, 1 - (1 - floor) * Math.min(1, (age - hold) / over));
      if (arr[i * 3] !== k) { arr[i * 3] = arr[i * 3 + 1] = arr[i * 3 + 2] = k; dirty = true; }
    }
    if (dirty) this.mesh.instanceColor.needsUpdate = true;
  }

  add(pos, normal, size) {
    const q = this._q.setFromUnitVectors(this._z, normal);
    q.multiply(this._q2.setFromAxisAngle(this._z, Math.random() * Math.PI * 2));
    this._m.compose(this._p.copy(pos).addScaledVector(normal, 0.004), q, this._s.set(size, size, size));
    this.mesh.setMatrixAt(this.i, this._m);
    if (this.born) {
      this.born[this.i] = now();
      const arr = this.mesh.instanceColor.array;
      arr[this.i * 3] = arr[this.i * 3 + 1] = arr[this.i * 3 + 2] = 1;
      this.mesh.instanceColor.needsUpdate = true;
    }
    this.i = (this.i + 1) % this.max;
    this.mesh.count = Math.min(this.max, this.mesh.count + 1);
    this.mesh.instanceMatrix.needsUpdate = true;
  }

  clear() {
    this.mesh.count = 0;
    this.i = 0;
    if (this.born) this.born.fill(-1e6);
  }
}

export class Decals {
  constructor(scene) {
    const hole = canvasTex((g, s) => {
      const r = rng(7);
      const gr = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
      gr.addColorStop(0, 'rgba(8,6,5,1)'); gr.addColorStop(0.12, 'rgba(15,12,10,0.95)'); gr.addColorStop(0.3, 'rgba(40,34,30,0.55)');
      gr.addColorStop(0.55, 'rgba(60,52,46,0.18)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
      g.fillStyle = gr; g.fillRect(0, 0, s, s);
      g.strokeStyle = 'rgba(20,16,14,0.5)'; g.lineWidth = 1.2;
      for (let i = 0; i < 7; i++) { const a = r() * 6.28; g.beginPath(); g.moveTo(s / 2, s / 2); g.lineTo(s / 2 + Math.cos(a) * s * (0.2 + r() * 0.25), s / 2 + Math.sin(a) * s * (0.2 + r() * 0.25)); g.stroke(); }
    });
    const blood = canvasTex((g, s) => {
      const r = rng(99);
      g.fillStyle = 'rgba(90,4,4,0.92)';
      for (let i = 0; i < 40; i++) {
        const a = r() * 6.28, d = r() * r() * s * 0.42;
        g.beginPath(); g.arc(s / 2 + Math.cos(a) * d, s / 2 + Math.sin(a) * d, 2 + r() * s * 0.12 * (1 - d / (s * 0.45)), 0, 6.28); g.fill();
      }
      g.fillStyle = 'rgba(55,0,0,0.6)';
      for (let i = 0; i < 12; i++) { g.beginPath(); g.arc(s / 2 + (r() - 0.5) * s * 0.3, s / 2 + (r() - 0.5) * s * 0.3, 3 + r() * 10, 0, 6.28); g.fill(); }
    }, 256);
    // disturbed soil left where a zombie clawed its way out (zombies.md #14)
    const dirt = canvasTex((g, s) => {
      const r = rng(4241);
      const gr = g.createRadialGradient(s / 2, s / 2, s * 0.05, s / 2, s / 2, s / 2);
      gr.addColorStop(0, 'rgba(26,20,14,0.92)'); gr.addColorStop(0.45, 'rgba(34,26,18,0.7)');
      gr.addColorStop(0.78, 'rgba(44,35,24,0.28)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
      g.fillStyle = gr; g.fillRect(0, 0, s, s);
      // clods and a cracked rim so it does not read as a soft circle
      for (let i = 0; i < 90; i++) {
        const a = r() * 6.28, d = Math.sqrt(r()) * s * 0.45;
        const rr = 1.5 + r() * s * 0.035;
        g.fillStyle = `rgba(${18 + r() * 26 | 0},${13 + r() * 20 | 0},${8 + r() * 14 | 0},${0.35 + r() * 0.5})`;
        g.beginPath(); g.ellipse(s / 2 + Math.cos(a) * d, s / 2 + Math.sin(a) * d, rr, rr * (0.5 + r() * 0.8), r() * 6.28, 0, 6.28); g.fill();
      }
      g.strokeStyle = 'rgba(12,9,6,0.55)'; g.lineWidth = 1.6;
      for (let i = 0; i < 10; i++) {
        const a = r() * 6.28;
        g.beginPath(); g.moveTo(s / 2 + Math.cos(a) * s * 0.08, s / 2 + Math.sin(a) * s * 0.08);
        g.lineTo(s / 2 + Math.cos(a + (r() - 0.5) * 0.5) * s * (0.2 + r() * 0.24), s / 2 + Math.sin(a + (r() - 0.5) * 0.5) * s * (0.2 + r() * 0.24));
        g.stroke();
      }
    }, 256);
    const scorch = canvasTex((g, s) => {
      const gr = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
      gr.addColorStop(0, 'rgba(5,4,3,0.95)'); gr.addColorStop(0.5, 'rgba(15,12,10,0.6)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
      g.fillStyle = gr; g.fillRect(0, 0, s, s);
    });
    this.holes = new DecalSet(scene, hole, 300);
    this.blood = new DecalSet(scene, blood, 200, { roughness: 0.35 });
    this.scorch = new DecalSet(scene, scorch, 30);
    // the mound stays sharp while the round is still around it, then settles back
    // into the ground rather than vanishing (zombies.md #14)
    this.dirt = new DecalSet(scene, dirt, 48, { roughness: 0.98, fade: { hold: 8, over: 6, floor: 0.3 } });
  }

  bulletHole(pos, normal) { this.holes.add(pos, normal, 0.07 + Math.random() * 0.03); }
  bloodSplat(pos, normal, size = 0.6) { this.blood.add(pos, normal, size * (0.7 + Math.random() * 0.6)); }
  scorchMark(pos, normal, size = 2.5) { this.scorch.add(pos, normal, size); }
  /** disturbed soil where a zombie came out of the ground */
  dirtPatch(pos, normal, size = 1.2) { this.dirt.add(pos, normal, size * (0.85 + Math.random() * 0.35)); }
  clear() { this.holes.clear(); this.blood.clear(); this.scorch.clear(); this.dirt.clear(); }
}
