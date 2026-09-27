import * as THREE from 'three';

// Procedural 4x4 texture atlas (128px cells)
// 0 soft dot, 1 smoke puff, 2 flame, 3 spark streak, 4 blood blob, 5 flare star, 6 ember, 7 debris chunk, 8 ring
function buildAtlas() {
  const cell = 128, N = 4;
  const c = document.createElement('canvas');
  c.width = c.height = cell * N;
  const g = c.getContext('2d');
  const at = (k) => [(k % N) * cell, Math.floor(k / N) * cell];
  const rand = (() => { let s = 1234567; return () => ((s = (s * 16807) % 2147483647) / 2147483647); })();

  const radial = (k, stops) => {
    const [x, y] = at(k);
    const gr = g.createRadialGradient(x + 64, y + 64, 0, x + 64, y + 64, 62);
    stops.forEach(([o, col]) => gr.addColorStop(o, col));
    g.fillStyle = gr; g.fillRect(x, y, cell, cell);
  };
  radial(0, [[0, 'rgba(255,255,255,1)'], [0.35, 'rgba(255,255,255,0.55)'], [1, 'rgba(255,255,255,0)']]);
  // smoke: many soft blobs
  {
    const [x, y] = at(1);
    g.save(); g.beginPath(); g.rect(x, y, cell, cell); g.clip();
    for (let i = 0; i < 70; i++) {
      const a = rand() * Math.PI * 2, r = rand() * 34;
      const px = x + 64 + Math.cos(a) * r, py = y + 64 + Math.sin(a) * r, rr = 10 + rand() * 22;
      const gr = g.createRadialGradient(px, py, 0, px, py, rr);
      gr.addColorStop(0, `rgba(255,255,255,${0.10 + rand() * 0.08})`); gr.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = gr; g.fillRect(x, y, cell, cell);
    }
    g.restore();
  }
  // flame: teardrop with noisy edges
  {
    const [x, y] = at(2);
    g.save(); g.beginPath(); g.rect(x, y, cell, cell); g.clip();
    for (let i = 0; i < 60; i++) {
      const t = rand();
      const px = x + 64 + (rand() - 0.5) * 40 * (1 - t), py = y + 100 - t * 80, rr = 8 + (1 - t) * 26 * rand();
      const gr = g.createRadialGradient(px, py, 0, px, py, rr);
      gr.addColorStop(0, `rgba(255,255,255,${0.16 + (1 - t) * 0.1})`); gr.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = gr; g.fillRect(x, y, cell, cell);
    }
    g.restore();
  }
  // spark streak (vertical)
  {
    const [x, y] = at(3);
    const gr = g.createLinearGradient(x + 64, y, x + 64, y + cell);
    gr.addColorStop(0, 'rgba(255,255,255,0)'); gr.addColorStop(0.5, 'rgba(255,255,255,1)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = gr;
    g.beginPath(); g.ellipse(x + 64, y + 64, 9, 62, 0, 0, Math.PI * 2); g.fill();
    const gr2 = g.createRadialGradient(x + 64, y + 64, 0, x + 64, y + 64, 20);
    gr2.addColorStop(0, 'rgba(255,255,255,0.9)'); gr2.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = gr2; g.fillRect(x, y, cell, cell);
  }
  // blood blob: irregular with droplets
  {
    const [x, y] = at(4);
    g.save(); g.beginPath(); g.rect(x, y, cell, cell); g.clip();
    g.fillStyle = 'rgba(255,255,255,0.95)';
    for (let i = 0; i < 26; i++) {
      const a = rand() * Math.PI * 2, r = rand() * rand() * 40;
      g.beginPath(); g.arc(x + 64 + Math.cos(a) * r, y + 64 + Math.sin(a) * r, 4 + rand() * 18 * (1 - r / 45), 0, Math.PI * 2); g.fill();
    }
    g.restore();
  }
  // flare star (muzzle)
  {
    const [x, y] = at(5);
    radial(5, [[0, 'rgba(255,255,255,1)'], [0.18, 'rgba(255,255,255,0.8)'], [0.5, 'rgba(255,255,255,0.12)'], [1, 'rgba(255,255,255,0)']]);
    g.save(); g.translate(x + 64, y + 64);
    for (let i = 0; i < 7; i++) {
      g.rotate(Math.PI * 2 / 7 + rand() * 0.3);
      const gr = g.createLinearGradient(0, 0, 0, -62);
      gr.addColorStop(0, 'rgba(255,255,255,0.9)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = gr;
      g.beginPath(); g.moveTo(-5, 0); g.lineTo(0, -40 - rand() * 22); g.lineTo(5, 0); g.fill();
    }
    g.restore();
  }
  radial(6, [[0, 'rgba(255,255,255,1)'], [0.15, 'rgba(255,255,255,0.9)'], [0.4, 'rgba(255,255,255,0.15)'], [1, 'rgba(255,255,255,0)']]);
  // debris chunk: hard-edged irregular polygon
  {
    const [x, y] = at(7);
    g.fillStyle = 'rgba(255,255,255,1)';
    g.beginPath();
    for (let i = 0; i < 7; i++) {
      const a = (i / 7) * Math.PI * 2, r = 30 + rand() * 30;
      const px = x + 64 + Math.cos(a) * r, py = y + 64 + Math.sin(a) * r;
      i ? g.lineTo(px, py) : g.moveTo(px, py);
    }
    g.fill();
  }
  // ring
  {
    const [x, y] = at(8);
    const gr = g.createRadialGradient(x + 64, y + 64, 30, x + 64, y + 64, 62);
    gr.addColorStop(0, 'rgba(255,255,255,0)'); gr.addColorStop(0.6, 'rgba(255,255,255,0.8)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = gr; g.fillRect(x, y, cell, cell);
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.generateMipmaps = true;
  tex.minFilter = THREE.LinearMipmapLinearFilter;
  return tex;
}

const vert = /* glsl */`
  attribute vec3 iPos;
  attribute vec4 iColor;
  attribute vec3 iVel;
  attribute vec4 iParams;   // size, rotation, stretch, frame
  uniform float uFogDensity; // = scene.fog.density ^ 2 (FogExp2)
  varying vec2 vUv;
  varying vec4 vColor;
  varying float vFog;
  void main() {
    vec4 mv = viewMatrix * vec4(iPos, 1.0);
    float size = iParams.x;
    vec2 corner = position.xy;
    vec2 off;
    if (iParams.z > 0.0) {
      vec2 v = (viewMatrix * vec4(iVel, 0.0)).xy;
      float l = length(v);
      vec2 dir = l > 1e-4 ? v / l : vec2(0.0, 1.0);
      vec2 perp = vec2(-dir.y, dir.x);
      off = perp * corner.x * size + dir * corner.y * size * (1.0 + iParams.z * l);
    } else {
      float c = cos(iParams.y), s = sin(iParams.y);
      off = vec2(c * corner.x - s * corner.y, s * corner.x + c * corner.y) * size;
    }
    mv.xy += off;
    gl_Position = projectionMatrix * mv;
    float f = iParams.w;
    vUv = (vec2(mod(f, 4.0), 3.0 - floor(f / 4.0)) + uv) / 4.0;
    vColor = iColor;
    vFog = 1.0 - exp(-uFogDensity * dot(mv.xyz, mv.xyz));
  }`;

const frag = /* glsl */`
  uniform sampler2D map;
  uniform vec3 uTint;
  uniform float uAdditive;
  uniform vec3 uFogColor;
  varying vec2 vUv;
  varying vec4 vColor;
  varying float vFog;
  void main() {
    vec4 t = texture2D(map, vUv);
    vec3 col = vColor.rgb * t.rgb * mix(uTint, vec3(1.0), uAdditive);
    float a = t.a * vColor.a;
    if (uAdditive > 0.5) { col *= a * (1.0 - vFog); gl_FragColor = vec4(col, 1.0); }
    else { col = mix(col, uFogColor, vFog * 0.8); gl_FragColor = vec4(col, a); }
  }`;

class Pool {
  constructor(max, atlas, additive) {
    this.max = max;
    this.count = 0;
    const g = new THREE.InstancedBufferGeometry();
    const quad = new THREE.PlaneGeometry(1, 1);
    g.index = quad.index;
    g.setAttribute('position', quad.getAttribute('position'));
    g.setAttribute('uv', quad.getAttribute('uv'));
    this.aPos = new THREE.InstancedBufferAttribute(new Float32Array(max * 3), 3).setUsage(THREE.DynamicDrawUsage);
    this.aCol = new THREE.InstancedBufferAttribute(new Float32Array(max * 4), 4).setUsage(THREE.DynamicDrawUsage);
    this.aVel = new THREE.InstancedBufferAttribute(new Float32Array(max * 3), 3).setUsage(THREE.DynamicDrawUsage);
    this.aPar = new THREE.InstancedBufferAttribute(new Float32Array(max * 4), 4).setUsage(THREE.DynamicDrawUsage);
    g.setAttribute('iPos', this.aPos); g.setAttribute('iColor', this.aCol); g.setAttribute('iVel', this.aVel); g.setAttribute('iParams', this.aPar);
    g.instanceCount = 0;
    this.material = new THREE.ShaderMaterial({
      uniforms: {
        map: { value: atlas },
        uTint: { value: new THREE.Color(0.55, 0.45, 0.4) },
        uAdditive: { value: additive ? 1 : 0 },
        uFogColor: { value: new THREE.Color(0.25, 0.17, 0.13) },
        uFogDensity: { value: 0.012 * 0.012 },
      },
      vertexShader: vert, fragmentShader: frag,
      transparent: true, depthWrite: false,
      blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
    });
    this.mesh = new THREE.Mesh(g, this.material);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = additive ? 20 : 10;
    // particle state (SoA)
    const f = n => new Float32Array(max * n);
    this.p = f(3); this.v = f(3); this.life = f(1); this.maxLife = f(1);
    this.size = f(2); this.c0 = f(4); this.c1 = f(4); this.rot = f(2); this.phys = f(3); // gravity, drag, stretch
    this.frame = f(1);
  }

  spawn(o) {
    if (this.count >= this.max) return;
    const i = this.count++;
    this.p.set([o.x, o.y, o.z], i * 3);
    this.v.set([o.vx || 0, o.vy || 0, o.vz || 0], i * 3);
    this.life[i] = 0; this.maxLife[i] = o.life;
    this.size[i * 2] = o.size0; this.size[i * 2 + 1] = o.size1 ?? o.size0;
    const c0 = o.c0, c1 = o.c1 || o.c0;
    this.c0.set(c0, i * 4); this.c1.set(c1, i * 4);
    this.rot[i * 2] = o.rot ?? Math.random() * 6.28; this.rot[i * 2 + 1] = o.spin || 0;
    this.phys[i * 3] = o.gravity || 0; this.phys[i * 3 + 1] = o.drag || 0; this.phys[i * 3 + 2] = o.stretch || 0;
    this.frame[i] = o.frame || 0;
  }

  update(dt) {
    let n = this.count;
    const { p, v, life, maxLife } = this;
    for (let i = 0; i < n; i++) {
      life[i] += dt;
      if (life[i] >= maxLife[i]) {
        // swap-remove
        n--;
        if (i !== n) this._move(n, i);
        i--;
        continue;
      }
      const g = this.phys[i * 3], drag = this.phys[i * 3 + 1];
      const k = Math.max(0, 1 - drag * dt);
      v[i * 3] *= k; v[i * 3 + 1] = v[i * 3 + 1] * k - g * dt; v[i * 3 + 2] *= k;
      p[i * 3] += v[i * 3] * dt; p[i * 3 + 1] += v[i * 3 + 1] * dt; p[i * 3 + 2] += v[i * 3 + 2] * dt;
      this.rot[i * 2] += this.rot[i * 2 + 1] * dt;
    }
    this.count = n;
    const aP = this.aPos.array, aC = this.aCol.array, aV = this.aVel.array, aR = this.aPar.array;
    for (let i = 0; i < n; i++) {
      const t = life[i] / maxLife[i];
      aP[i * 3] = p[i * 3]; aP[i * 3 + 1] = p[i * 3 + 1]; aP[i * 3 + 2] = p[i * 3 + 2];
      aV[i * 3] = v[i * 3]; aV[i * 3 + 1] = v[i * 3 + 1]; aV[i * 3 + 2] = v[i * 3 + 2];
      for (let c = 0; c < 4; c++) aC[i * 4 + c] = this.c0[i * 4 + c] + (this.c1[i * 4 + c] - this.c0[i * 4 + c]) * t;
      // fade-in over first 10% for soft particles
      const fin = Math.min(1, t * 10);
      aC[i * 4 + 3] *= fin;
      aR[i * 4] = this.size[i * 2] + (this.size[i * 2 + 1] - this.size[i * 2]) * t;
      aR[i * 4 + 1] = this.rot[i * 2];
      aR[i * 4 + 2] = this.phys[i * 3 + 2];
      aR[i * 4 + 3] = this.frame[i];
    }
    const geo = this.mesh.geometry;
    geo.instanceCount = n;
    this.aPos.needsUpdate = this.aCol.needsUpdate = this.aVel.needsUpdate = this.aPar.needsUpdate = true;
    this.aPos.clearUpdateRanges(); this.aPos.addUpdateRange(0, n * 3);
    this.aVel.clearUpdateRanges(); this.aVel.addUpdateRange(0, n * 3);
    this.aCol.clearUpdateRanges(); this.aCol.addUpdateRange(0, n * 4);
    this.aPar.clearUpdateRanges(); this.aPar.addUpdateRange(0, n * 4);
  }

  _move(from, to) {
    const cp = (arr, k) => { for (let c = 0; c < k; c++) arr[to * k + c] = arr[from * k + c]; };
    cp(this.p, 3); cp(this.v, 3); cp(this.life, 1); cp(this.maxLife, 1); cp(this.size, 2);
    cp(this.c0, 4); cp(this.c1, 4); cp(this.rot, 2); cp(this.phys, 3); cp(this.frame, 1);
  }
}

const rnd = (a, b) => a + Math.random() * (b - a);
const _v = new THREE.Vector3();
const _t1 = new THREE.Vector3();
const _t2 = new THREE.Vector3();

// ---------------------------------------------------------------- gore gibs
// Lumpy low-poly chunks (limbs / head / torso pieces) with a cheap ballistic
// integrator and a single ground bounce. Pooled: meshes are created once and
// hidden when idle, so a gib burst never allocates.
function chunkGeometry(seed, squash = 1) {
  const g = new THREE.IcosahedronGeometry(1, 0);
  const p = g.attributes.position;
  let s = seed;
  const rr = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < p.count; i++) {
    const k = 0.5 + rr() * 0.8;
    p.setXYZ(i, p.getX(i) * k, p.getY(i) * k * squash, p.getZ(i) * k * (0.7 + rr() * 0.6));
  }
  p.needsUpdate = true;
  g.computeVertexNormals();
  return g;
}

class GibPool {
  constructor(scene, max = 56) {
    this.max = max;
    this.free = [];
    this.live = [];
    this.material = new THREE.MeshStandardMaterial({ color: 0x4d0f0b, roughness: 0.38, metalness: 0, emissive: 0x150201, emissiveIntensity: 1 });
    this.boneMaterial = new THREE.MeshStandardMaterial({ color: 0xa89a82, roughness: 0.62, metalness: 0 });
    const geos = [chunkGeometry(11, 1.0), chunkGeometry(977, 0.55), chunkGeometry(4231, 1.6), chunkGeometry(77003, 0.8)];
    for (let i = 0; i < max; i++) {
      const m = new THREE.Mesh(geos[i % geos.length], this.material);
      m.visible = false;
      m.castShadow = true;
      scene.add(m);
      this.free.push(m);
    }
  }

  spawn(o) {
    const m = this.free.pop();
    if (!m) return null;
    m.visible = true;
    m.material = o.bone ? this.boneMaterial : this.material;
    m.position.set(o.x, o.y, o.z);
    m.rotation.set(rnd(0, 6.28), rnd(0, 6.28), rnd(0, 6.28));
    const s = o.size ?? 0.07;
    m.scale.set(s * rnd(0.7, 1.3), s * rnd(0.7, 1.3), s * rnd(0.7, 1.3));
    m.userData.gib = {
      vx: o.vx || 0, vy: o.vy || 0, vz: o.vz || 0,
      wx: rnd(-14, 14), wy: rnd(-14, 14), wz: rnd(-14, 14),
      life: 0, maxLife: o.life ?? 6, groundY: o.groundY ?? -1e9,
      onLand: o.onLand || null, bounces: 0, rest: false, s,
      trail: o.trail !== false,
    };
    this.live.push(m);
    return m;
  }

  update(dt, fx) {
    for (let i = this.live.length - 1; i >= 0; i--) {
      const m = this.live[i];
      const d = m.userData.gib;
      d.life += dt;
      if (!d.rest) {
        d.vy -= 16 * dt;
        const k = Math.max(0, 1 - 0.6 * dt);
        d.vx *= k; d.vz *= k;
        m.position.x += d.vx * dt; m.position.y += d.vy * dt; m.position.z += d.vz * dt;
        m.rotation.x += d.wx * dt; m.rotation.y += d.wy * dt; m.rotation.z += d.wz * dt;
        // a wet trail while it is still flying fast
        if (fx && d.trail && d.life < 0.5 && Math.random() < 0.5) {
          fx.alpha.spawn({ x: m.position.x, y: m.position.y, z: m.position.z, vx: d.vx * 0.15, vy: d.vy * 0.15, vz: d.vz * 0.15,
            life: rnd(0.25, 0.5), size0: rnd(0.02, 0.04), size1: 0.01, c0: [0.4, 0.015, 0.01, 1], c1: [0.22, 0, 0, 0.6], frame: 4, gravity: 9.8, stretch: 0.05 });
        }
        if (m.position.y <= d.groundY + d.s * 0.5) {
          m.position.y = d.groundY + d.s * 0.5;
          d.bounces++;
          if (d.onLand && d.bounces === 1) { d.onLand(m.position); d.onLand = null; }
          if (d.bounces > 2 || Math.abs(d.vy) < 1.2) {
            d.rest = true;
            d.vx = d.vy = d.vz = 0;
            m.rotation.x = Math.PI * 0.5 * Math.random();
          } else {
            d.vy = -d.vy * 0.28;
            d.vx *= 0.45; d.vz *= 0.45;
            d.wx *= 0.4; d.wy *= 0.4; d.wz *= 0.4;
          }
        }
      }
      const fade = d.maxLife - d.life;
      if (fade < 0.7) m.scale.setScalar(Math.max(0.001, d.s * Math.max(0, fade / 0.7)));
      if (d.life >= d.maxLife) {
        m.visible = false;
        this.live.splice(i, 1);
        this.free.push(m);
      }
    }
  }

  clear() {
    for (const m of this.live) { m.visible = false; this.free.push(m); }
    this.live.length = 0;
  }
}

export class Particles {
  constructor(scene) {
    this.scene = scene;
    this.atlas = buildAtlas();
    this.add = new Pool(4000, this.atlas, true);
    this.alpha = new Pool(3000, this.atlas, false);
    scene.add(this.alpha.mesh, this.add.mesh);
    this.gibPool = new GibPool(scene);
  }

  update(dt) {
    this._syncFog();
    this.add.update(dt);
    this.alpha.update(dt);
    this.gibPool.update(dt, this);
  }

  // particles must fog exactly like the world does, or smoke floats in front of
  // the fog bank instead of sitting inside it (environment.md #12e)
  _syncFog() {
    const f = this.scene && this.scene.fog;
    if (!f) return;
    const density = f.isFogExp2 ? f.density : 0.012;
    const k = density * density;
    for (const pool of [this.add, this.alpha]) {
      const u = pool.material.uniforms;
      u.uFogColor.value.copy(f.color);
      u.uFogDensity.value = k;
    }
  }

  setAmbient(color) { this.alpha.material.uniforms.uTint.value.copy(color); }

  // ---------- presets ----------
  sparks(pos, normal, count = 8, color = [4, 2.4, 1.0, 1]) {
    for (let i = 0; i < count; i++) {
      _v.set(rnd(-1, 1), rnd(-1, 1), rnd(-1, 1)).normalize().multiplyScalar(0.6).add(normal).normalize().multiplyScalar(rnd(3, 9));
      this.add.spawn({ x: pos.x, y: pos.y, z: pos.z, vx: _v.x, vy: _v.y, vz: _v.z, life: rnd(0.12, 0.35), size0: 0.018, size1: 0.01,
        c0: color, c1: [color[0] * 0.8, color[1] * 0.3, 0.1, 0], frame: 3, stretch: 0.045, gravity: 9, drag: 1.5 });
    }
    this.add.spawn({ x: pos.x + normal.x * 0.02, y: pos.y + normal.y * 0.02, z: pos.z + normal.z * 0.02, life: 0.06, size0: 0.22, size1: 0.1, c0: [3, 2, 1.2, 1], frame: 5 });
  }

  dust(pos, normal, color = [0.55, 0.5, 0.45, 0.55]) {
    for (let i = 0; i < 3; i++) {
      _v.copy(normal).multiplyScalar(rnd(0.4, 1.4)).add(_t1.set(rnd(-0.3, 0.3), rnd(0, 0.3), rnd(-0.3, 0.3)));
      this.alpha.spawn({ x: pos.x, y: pos.y, z: pos.z, vx: _v.x, vy: _v.y, vz: _v.z, life: rnd(0.6, 1.2), size0: 0.08, size1: rnd(0.35, 0.6),
        c0: color, c1: [color[0], color[1], color[2], 0], frame: 1, drag: 2.5, gravity: -0.1, spin: rnd(-1, 1) });
    }
    for (let i = 0; i < 4; i++) {
      _v.copy(normal).multiplyScalar(rnd(1.5, 3.5)).add(_t1.set(rnd(-1, 1), rnd(0, 1.5), rnd(-1, 1)));
      this.alpha.spawn({ x: pos.x, y: pos.y, z: pos.z, vx: _v.x, vy: _v.y, vz: _v.z, life: rnd(0.4, 0.8), size0: rnd(0.015, 0.03),
        c0: [color[0] * 0.5, color[1] * 0.5, color[2] * 0.5, 1], frame: 7, gravity: 9.8, spin: rnd(-10, 10) });
    }
  }

  // `dir` is the spray direction (roughly back along the bullet, plus some up).
  // amount 1 = a body shot, 1.4 = a headshot, 3.5+ = a decapitation.
  blood(pos, dir, amount = 1) {
    // fine droplets — the readable part of the hit at 10 m
    const n = Math.round(18 * amount);
    for (let i = 0; i < n; i++) {
      _v.set(rnd(-1, 1), rnd(-0.5, 1), rnd(-1, 1)).multiplyScalar(0.75).add(dir).normalize().multiplyScalar(rnd(1.4, 6.5) * (0.8 + amount * 0.2));
      this.alpha.spawn({ x: pos.x, y: pos.y, z: pos.z, vx: _v.x, vy: _v.y, vz: _v.z, life: rnd(0.4, 0.95), size0: rnd(0.022, 0.065), size1: 0.014,
        c0: [0.46, 0.018, 0.012, 1], c1: [0.24, 0.0, 0.0, 0.85], frame: 4, gravity: 9.8, stretch: 0.06 });
    }
    // heavy slow gouts that arc and fall
    for (let i = 0; i < Math.ceil(4 * amount); i++) {
      _v.set(rnd(-1, 1), rnd(0, 1), rnd(-1, 1)).multiplyScalar(0.9).add(dir).normalize().multiplyScalar(rnd(0.6, 2.4));
      this.alpha.spawn({ x: pos.x, y: pos.y, z: pos.z, vx: _v.x, vy: _v.y + 0.5, vz: _v.z, life: rnd(0.5, 1.1), size0: rnd(0.05, 0.11), size1: rnd(0.03, 0.06),
        c0: [0.34, 0.01, 0.008, 1], c1: [0.18, 0.0, 0.0, 0.9], frame: 4, gravity: 12, stretch: 0.09, spin: rnd(-4, 4) });
    }
    // the mist — a short-lived dark red puff that gives the hit volume
    for (let i = 0; i < Math.ceil(3 * amount); i++) {
      _v.copy(dir).multiplyScalar(rnd(0.3, 1.3)).add(_t1.set(rnd(-0.3, 0.3), rnd(-0.1, 0.4), rnd(-0.3, 0.3)));
      this.alpha.spawn({ x: pos.x, y: pos.y, z: pos.z, vx: _v.x, vy: _v.y + 0.2, vz: _v.z, life: rnd(0.3, 0.65), size0: 0.09, size1: rnd(0.4, 0.8) * (0.7 + amount * 0.25),
        c0: [0.35, 0.02, 0.02, 0.62], c1: [0.2, 0.0, 0.0, 0], frame: 1, drag: 3.2, spin: rnd(-2, 2) });
    }
    // a stretched arterial streak straight back along the spray for big hits
    if (amount > 1.1) {
      for (let i = 0; i < Math.ceil(2 * amount); i++) {
        _v.copy(dir).multiplyScalar(rnd(3, 8)).add(_t1.set(rnd(-0.6, 0.6), rnd(-0.2, 0.6), rnd(-0.6, 0.6)));
        this.alpha.spawn({ x: pos.x, y: pos.y, z: pos.z, vx: _v.x, vy: _v.y, vz: _v.z, life: rnd(0.18, 0.4), size0: rnd(0.035, 0.07), size1: 0.02,
          c0: [0.6, 0.03, 0.02, 1], c1: [0.3, 0.0, 0.0, 0], frame: 4, gravity: 6, stretch: 0.14 });
      }
    }
  }

  // a sustained jet from an open wound — call every frame for ~0.6 s
  arterialSpray(pos, dir, strength = 1) {
    const n = Math.random() < strength ? 2 : 1;
    for (let i = 0; i < n; i++) {
      _v.copy(dir).multiplyScalar(rnd(1.2, 3.4) * strength).add(_t1.set(rnd(-0.5, 0.5), rnd(-0.2, 0.3), rnd(-0.5, 0.5)));
      this.alpha.spawn({ x: pos.x, y: pos.y, z: pos.z, vx: _v.x, vy: _v.y, vz: _v.z, life: rnd(0.35, 0.8), size0: rnd(0.025, 0.055), size1: 0.015,
        c0: [0.45, 0.015, 0.01, 1], c1: [0.22, 0, 0, 0.8], frame: 4, gravity: 11, stretch: 0.1 });
    }
    if (Math.random() < 0.35) {
      this.alpha.spawn({ x: pos.x, y: pos.y, z: pos.z, vx: dir.x * 0.4, vy: dir.y * 0.4 + 0.2, vz: dir.z * 0.4, life: rnd(0.25, 0.5), size0: 0.06, size1: rnd(0.2, 0.35),
        c0: [0.32, 0.02, 0.02, 0.5], c1: [0.18, 0, 0, 0], frame: 1, drag: 3.5, spin: rnd(-2, 2) });
    }
  }

  headPop(pos, dir) {
    const up = dir ? _t2.copy(dir).normalize() : _t2.set(0, 1, 0);
    this.blood(pos, up, 4.2);
    // chunk shower — skull fragments and scalp
    for (let i = 0; i < 46; i++) {
      _v.set(rnd(-1, 1), rnd(0.1, 1.6), rnd(-1, 1)).normalize().multiplyScalar(rnd(2, 7));
      this.alpha.spawn({ x: pos.x, y: pos.y, z: pos.z, vx: _v.x, vy: _v.y, vz: _v.z, life: rnd(0.6, 1.4), size0: rnd(0.025, 0.07), size1: rnd(0.02, 0.05),
        c0: [0.35, 0.05, 0.04, 1], c1: [0.18, 0.02, 0.02, 1], frame: 7, gravity: 11, spin: rnd(-14, 14) });
    }
    // 0.25 s red mist ball
    this.alpha.spawn({ x: pos.x, y: pos.y, z: pos.z, life: 0.28, size0: 0.25, size1: 0.9,
      c0: [0.35, 0.02, 0.02, 0.6], c1: [0.22, 0.0, 0.0, 0], frame: 1, spin: rnd(-1, 1) });
    this.alpha.spawn({ x: pos.x, y: pos.y, z: pos.z, life: 0.45, size0: 0.18, size1: 1.3,
      c0: [0.28, 0.015, 0.015, 0.35], c1: [0.18, 0.0, 0.0, 0], frame: 1, drag: 2.4, spin: rnd(-1, 1) });
  }

  /**
   * Physical gore chunks with a ground bounce.
   * opts: count, speed, size, groundY, dir, onLand(pos), bone (pale bone shards)
   */
  gibBurst(pos, opts = {}) {
    const count = opts.count ?? 6;
    const speed = opts.speed ?? 4;
    const dir = opts.dir || null;
    for (let i = 0; i < count; i++) {
      _v.set(rnd(-1, 1), rnd(0.15, 1.2), rnd(-1, 1)).normalize();
      if (dir) _v.addScaledVector(dir, 0.7).normalize();
      _v.multiplyScalar(rnd(0.45, 1) * speed);
      this.gibPool.spawn({
        x: pos.x + rnd(-0.08, 0.08), y: pos.y + rnd(-0.08, 0.08), z: pos.z + rnd(-0.08, 0.08),
        vx: _v.x, vy: _v.y, vz: _v.z,
        size: (opts.size ?? 0.09) * rnd(0.6, 1.4),
        life: opts.life ?? rnd(5, 8),
        groundY: opts.groundY ?? pos.y - 1.6,
        onLand: i === 0 ? opts.onLand : null,
        bone: opts.bone && i % 4 === 0,
      });
    }
    this.blood(pos, dir ? _t2.copy(dir) : _t2.set(0, 1, 0), 2.2);
  }

  /**
   * One heavy, slow-tumbling skull-sized chunk thrown clear of a head pop, so the
   * decapitation has a single readable object to follow instead of only a spray
   * (zombies.md #6). Uses the pre-built gib pool — nothing is allocated here.
   */
  skullChunk(pos, dir, groundY) {
    _v.set(rnd(-1, 1), rnd(0.5, 1.1), rnd(-1, 1)).normalize();
    if (dir) _v.addScaledVector(_t2.copy(dir).setY(0.25).normalize(), 1.1).normalize();
    _v.multiplyScalar(rnd(3.2, 5.4));
    const m = this.gibPool.spawn({
      x: pos.x, y: pos.y, z: pos.z, vx: _v.x, vy: _v.y, vz: _v.z,
      size: 0.17, life: 9, groundY: groundY ?? pos.y - 1.7, bone: true, trail: true,
    });
    if (m) {
      const d = m.userData.gib;
      d.wx *= 0.35; d.wy *= 0.35; d.wz *= 0.35;   // a skull tumbles, it does not blur
    }
    return m;
  }

  clearGibs() { this.gibPool.clear(); }

  muzzleSmoke(pos, dir) {
    for (let i = 0; i < 2; i++) {
      _v.copy(dir).multiplyScalar(rnd(0.4, 1.2)).add(_t1.set(rnd(-0.2, 0.2), rnd(0.1, 0.4), rnd(-0.2, 0.2)));
      this.alpha.spawn({ x: pos.x, y: pos.y, z: pos.z, vx: _v.x, vy: _v.y, vz: _v.z, life: rnd(0.5, 1.0), size0: 0.05, size1: rnd(0.25, 0.4),
        c0: [0.7, 0.68, 0.65, 0.22], c1: [0.7, 0.68, 0.65, 0], frame: 1, drag: 2, gravity: -0.3, spin: rnd(-1, 1) });
    }
  }

  tracer(from, to, color = [5, 3.5, 1.8, 0.9]) {
    _v.subVectors(to, from);
    const dist = _v.length();
    if (dist < 2) return;
    _v.divideScalar(dist);
    const speed = 350;
    const life = Math.min(0.2, dist / speed);
    this.add.spawn({ x: from.x + _v.x * 1.5, y: from.y + _v.y * 1.5, z: from.z + _v.z * 1.5, vx: _v.x * speed, vy: _v.y * speed, vz: _v.z * speed,
      life, size0: 0.012, c0: color, c1: color, frame: 3, stretch: 0.3 });
  }

  fire(pos, scale = 1) {
    // call every frame per fire source
    if (Math.random() < 0.9) {
      this.add.spawn({ x: pos.x + rnd(-0.18, 0.18) * scale, y: pos.y, z: pos.z + rnd(-0.18, 0.18) * scale, vx: rnd(-0.1, 0.1), vy: rnd(0.9, 1.7) * scale, vz: rnd(-0.1, 0.1),
        life: rnd(0.45, 0.8), size0: rnd(0.35, 0.55) * scale, size1: 0.12 * scale, c0: [3.2, 1.25, 0.35, 0.8], c1: [1.2, 0.2, 0.02, 0], frame: 2, rot: rnd(-0.3, 0.3), spin: rnd(-0.6, 0.6) });
    }
    if (Math.random() < 0.25) {
      this.alpha.spawn({ x: pos.x + rnd(-0.2, 0.2) * scale, y: pos.y + 0.7 * scale, z: pos.z + rnd(-0.2, 0.2) * scale, vx: rnd(-0.2, 0.3), vy: rnd(0.9, 1.6), vz: rnd(-0.2, 0.2),
        life: rnd(2.5, 4), size0: 0.3 * scale, size1: rnd(1.6, 2.6) * scale, c0: [0.09, 0.08, 0.075, 0.5], c1: [0.2, 0.18, 0.17, 0], frame: 1, spin: rnd(-0.3, 0.3), drag: 0.2 });
    }
    if (Math.random() < 0.12) {
      this.add.spawn({ x: pos.x + rnd(-0.2, 0.2), y: pos.y + 0.3, z: pos.z + rnd(-0.2, 0.2), vx: rnd(-0.6, 0.6), vy: rnd(1.5, 3), vz: rnd(-0.6, 0.6),
        life: rnd(1.2, 2.4), size0: 0.025, size1: 0.01, c0: [5, 2, 0.5, 1], c1: [2, 0.4, 0.05, 0], frame: 6, drag: 0.4, gravity: -0.3 });
    }
  }

  embersAround(center, radius = 25) {
    this.add.spawn({ x: center.x + rnd(-radius, radius), y: rnd(0.2, 6), z: center.z + rnd(-radius, radius), vx: rnd(-0.4, 0.8), vy: rnd(0.2, 0.7), vz: rnd(-0.4, 0.4),
      life: rnd(3, 6), size0: 0.02, size1: 0.008, c0: [4, 1.6, 0.4, 1], c1: [2, 0.4, 0.05, 0], frame: 6, drag: 0.1 });
  }

  ash(center, radius = 22) {
    this.alpha.spawn({ x: center.x + rnd(-radius, radius), y: rnd(2, 9), z: center.z + rnd(-radius, radius), vx: rnd(-0.3, 0.5), vy: rnd(-0.5, -0.2), vz: rnd(-0.3, 0.3),
      life: rnd(6, 10), size0: 0.018, size1: 0.018, c0: [0.75, 0.72, 0.7, 0.8], c1: [0.6, 0.6, 0.6, 0], frame: 7, spin: rnd(-3, 3) });
  }

  explosion(pos, radius = 3, color = [4, 1.6, 0.4, 1]) {
    this.add.spawn({ x: pos.x, y: pos.y, z: pos.z, life: 0.12, size0: radius * 0.8, size1: radius * 1.6, c0: [6, 4, 2.5, 1], c1: [3, 1, 0.2, 0], frame: 5 });
    for (let i = 0; i < 18; i++) {
      _v.set(rnd(-1, 1), rnd(-0.2, 1), rnd(-1, 1)).normalize().multiplyScalar(rnd(1, 4) * radius * 0.5);
      this.add.spawn({ x: pos.x, y: pos.y, z: pos.z, vx: _v.x, vy: _v.y, vz: _v.z, life: rnd(0.25, 0.55), size0: radius * 0.35, size1: radius * 0.7,
        c0: color, c1: [color[0] * 0.3, color[1] * 0.1, 0.02, 0], frame: 2, drag: 4, spin: rnd(-2, 2) });
    }
    for (let i = 0; i < 12; i++) {
      _v.set(rnd(-1, 1), rnd(0, 1), rnd(-1, 1)).normalize().multiplyScalar(rnd(0.5, 2) * radius * 0.4);
      this.alpha.spawn({ x: pos.x, y: pos.y + 0.3, z: pos.z, vx: _v.x, vy: _v.y + 0.5, vz: _v.z, life: rnd(1.5, 3), size0: radius * 0.3, size1: radius * rnd(0.9, 1.4),
        c0: [0.12, 0.1, 0.09, 0.75], c1: [0.25, 0.22, 0.2, 0], frame: 1, drag: 1.8, gravity: -0.4, spin: rnd(-1, 1) });
    }
    this.sparks(pos, _t2.set(0, 1, 0), 20);
  }

  dirtBurst(pos, amount = 1) {
    for (let i = 0; i < Math.round(32 * amount); i++) {
      _v.set(rnd(-1, 1), rnd(1.5, 3.4), rnd(-1, 1)).multiplyScalar(rnd(0.7, 1.9));
      this.alpha.spawn({ x: pos.x + rnd(-0.38, 0.38), y: pos.y + 0.05, z: pos.z + rnd(-0.38, 0.38), vx: _v.x, vy: _v.y, vz: _v.z, life: rnd(0.6, 1.3), size0: rnd(0.03, 0.09),
        c0: [0.18, 0.13, 0.09, 1], c1: [0.15, 0.1, 0.07, 1], frame: 7, gravity: 9.8, spin: rnd(-8, 8) });
    }
    for (let i = 0; i < Math.round(10 * amount); i++) {
      this.alpha.spawn({ x: pos.x + rnd(-0.5, 0.5), y: pos.y + 0.15, z: pos.z + rnd(-0.5, 0.5), vx: rnd(-0.6, 0.6), vy: rnd(0.3, 1.0), vz: rnd(-0.6, 0.6), life: rnd(1.2, 2.6), size0: 0.3, size1: rnd(1.0, 1.9),
        c0: [0.32, 0.26, 0.2, 0.55], c1: [0.32, 0.26, 0.2, 0], frame: 1, drag: 1.5, spin: rnd(-1, 1) });
    }
    // a couple of heavier clods that arc out of the hole
    for (let i = 0; i < Math.round(4 * amount); i++) {
      _v.set(rnd(-1, 1), rnd(2, 4), rnd(-1, 1)).multiplyScalar(rnd(0.6, 1.2));
      this.alpha.spawn({ x: pos.x + rnd(-0.25, 0.25), y: pos.y + 0.1, z: pos.z + rnd(-0.25, 0.25), vx: _v.x, vy: _v.y, vz: _v.z, life: rnd(0.9, 1.5), size0: rnd(0.08, 0.14), size1: rnd(0.06, 0.1),
        c0: [0.14, 0.1, 0.07, 1], c1: [0.12, 0.09, 0.06, 1], frame: 7, gravity: 12, spin: rnd(-6, 6) });
    }
  }

  // hellhound burn-out: flame licks, embers and drifting ash from one spot
  emberBurst(pos, count = 26, scale = 1) {
    for (let i = 0; i < count; i++) {
      _v.set(rnd(-1, 1), rnd(0.2, 1.4), rnd(-1, 1)).normalize().multiplyScalar(rnd(0.6, 2.6) * scale);
      this.add.spawn({ x: pos.x + rnd(-0.2, 0.2), y: pos.y + rnd(-0.1, 0.25), z: pos.z + rnd(-0.2, 0.2), vx: _v.x, vy: _v.y + 0.6, vz: _v.z,
        life: rnd(0.8, 2.2), size0: rnd(0.018, 0.035), size1: 0.008, c0: [5, 2, 0.5, 1], c1: [2, 0.35, 0.04, 0], frame: 6, drag: 0.5, gravity: -0.4 });
    }
  }

  ashPuff(pos, count = 10, scale = 1) {
    for (let i = 0; i < count; i++) {
      _v.set(rnd(-1, 1), rnd(0, 1), rnd(-1, 1)).normalize().multiplyScalar(rnd(0.2, 0.9) * scale);
      this.alpha.spawn({ x: pos.x + rnd(-0.3, 0.3), y: pos.y + rnd(0, 0.4), z: pos.z + rnd(-0.3, 0.3), vx: _v.x, vy: _v.y + 0.35, vz: _v.z,
        life: rnd(1.6, 3.6), size0: rnd(0.02, 0.05), size1: rnd(0.02, 0.05), c0: [0.5, 0.48, 0.46, 0.75], c1: [0.35, 0.34, 0.33, 0], frame: 7, spin: rnd(-3, 3), drag: 0.8, gravity: 0.6 });
    }
    this.alpha.spawn({ x: pos.x, y: pos.y + 0.3, z: pos.z, vx: 0, vy: 0.5, vz: 0, life: rnd(2.2, 3.4), size0: 0.4 * scale, size1: rnd(1.4, 2.2) * scale,
      c0: [0.1, 0.09, 0.085, 0.55], c1: [0.2, 0.19, 0.18, 0], frame: 1, drag: 1.2, gravity: -0.3, spin: rnd(-0.5, 0.5) });
  }

  glowBurst(pos, color = [0.6, 4, 0.8, 1], count = 20, speed = 3) {
    for (let i = 0; i < count; i++) {
      _v.set(rnd(-1, 1), rnd(-1, 1), rnd(-1, 1)).normalize().multiplyScalar(rnd(0.5, 1) * speed);
      this.add.spawn({ x: pos.x, y: pos.y, z: pos.z, vx: _v.x, vy: _v.y, vz: _v.z, life: rnd(0.3, 0.7), size0: 0.05, size1: 0.01, c0: color, c1: [color[0], color[1], color[2], 0], frame: 6, drag: 2 });
    }
    this.add.spawn({ x: pos.x, y: pos.y, z: pos.z, life: 0.25, size0: 0.3, size1: 1.2, c0: color, c1: [color[0], color[1], color[2], 0], frame: 0 });
  }

  // a single glowing sprite (e.g. ray gun projectile trail)
  glow(pos, size, color, life = 0.08, frame = 0) {
    this.add.spawn({ x: pos.x, y: pos.y, z: pos.z, life, size0: size, size1: size * 0.3, c0: color, c1: [color[0], color[1], color[2], 0], frame });
  }
}
