import * as THREE from 'three';

// Apocalyptic dusk: low orange sun through smoke, dark ash clouds.
export const SUN_DIR = new THREE.Vector3(-0.45, 0.13, 0.88).normalize();

const skyVert = /* glsl */`
  varying vec3 vDir;
  void main() {
    vDir = normalize((modelMatrix * vec4(position, 0.0)).xyz);
    vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    gl_Position = p.xyww;
  }`;

const skyFrag = /* glsl */`
  uniform vec3 uSunDir;
  uniform float uTime;
  uniform float uClouds;
  varying vec3 vDir;

  float hash(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
  float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
  }
  float fbm(vec2 p) { float v = 0.0, a = 0.5; mat2 m = mat2(1.6, 1.2, -1.2, 1.6); for (int i = 0; i < 6; i++) { v += a * noise(p); p = m * p; a *= 0.5; } return v; }

  void main() {
    vec3 d = normalize(vDir);
    float h = d.y;
    float sunDot = max(dot(d, uSunDir), 0.0);
    float towardSun = pow(max(dot(normalize(vec3(d.x, 0.0, d.z)), normalize(vec3(uSunDir.x, 0.0, uSunDir.z))), 0.0), 2.0);

    vec3 zenith = vec3(0.028, 0.030, 0.062);
    vec3 upper = mix(vec3(0.115, 0.065, 0.12), vec3(0.32, 0.125, 0.085), towardSun);
    // the sun side stays warm, but well under the old 1.7 so the street no longer washes out
    vec3 horizon = mix(vec3(0.50, 0.215, 0.125), vec3(1.05, 0.44, 0.15), towardSun);
    vec3 col = mix(horizon, upper, smoothstep(0.0, 0.16, h));
    col = mix(col, zenith, smoothstep(0.18, 0.75, h));
    // below horizon: dusty ground haze
    col = mix(col, vec3(0.24, 0.155, 0.115), smoothstep(0.0, -0.12, h));

    // stars: only high up, drowned out on the sun side and by the smog band
    float starMask = smoothstep(0.25, 0.62, h) * (1.0 - towardSun * 0.8);
    if (starMask > 0.002) {
      vec2 suv = vec2(atan(d.z, d.x) * 2.2, asin(clamp(h, -1.0, 1.0)) * 2.2) * 24.0;
      vec2 ci = floor(suv), cf = fract(suv);
      float r = hash(ci);
      if (r > 0.88) {
        vec2 c2 = vec2(hash(ci + 3.17), hash(ci + 7.71));
        float dd = length(cf - c2);
        float tw = 0.6 + 0.4 * sin(uTime * (1.2 + r * 3.0) + r * 60.0);
        float star = smoothstep(0.13, 0.0, dd) * ((r - 0.88) / 0.12) * tw;
        col += vec3(0.78, 0.84, 1.0) * star * starMask * 0.55;
      }
    }

    // sun disc + glow through haze (the disc used to punch 4.0 and erase the horizon)
    col += vec3(1.35, 0.6, 0.22) * pow(sunDot, 12.0) * 0.85;
    col += vec3(2.4, 1.4, 0.7) * smoothstep(0.9993, 0.99975, sunDot);
    col += vec3(0.5, 0.19, 0.055) * pow(sunDot, 3.0) * 0.5;

    // smoke clouds: two layers (slow macro shape + finer detail), squashed near the horizon
    // so the plane projection stops smearing into radial streaks
    if (h > 0.0 && uClouds > 0.0) {
      float hh = max(h, 0.05);
      vec2 uv = d.xz / (hh + 0.10) * 0.85;
      uv *= mix(0.32, 1.0, smoothstep(0.0, 0.38, h));
      vec2 drift = vec2(uTime * 0.006, uTime * 0.002);
      float big = fbm(uv * 0.42 - drift * 0.45);
      float n = fbm(uv * 1.25 + drift + big * 0.55);
      float n2 = fbm(uv * 3.0 - drift * 1.7 + n);
      float cover = smoothstep(0.30, 0.62, n * 0.72 + n2 * 0.34 + big * 0.20);
      vec3 cloudLit = mix(vec3(0.085, 0.065, 0.062), vec3(0.85, 0.38, 0.13), pow(towardSun, 1.5) * (1.0 - n2) * 0.95 + pow(sunDot, 6.0) * 0.8);
      cloudLit *= 0.5 + 0.5 * smoothstep(0.0, 0.3, h);
      float fade = smoothstep(0.005, 0.13, h) * uClouds;
      col = mix(col, cloudLit, cover * fade);
    }
    // low-amplitude noise so the zenith gradient does not band before tone mapping
    col += (hash(gl_FragCoord.xy + fract(uTime * 3.0)) - 0.5) * 0.0012;
    gl_FragColor = vec4(col, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }`;

/* ------------------------------------------------------------------ *
 * Aerial perspective
 *
 * A single FogExp2 colour cannot be both "cool and dark away from the sun" and "warm haze
 * toward it", and a uniform warm fog is exactly what flattened the street into one cream
 * value band (environment.md #2c). So the fog stays neutral-cool and this patches the fog
 * chunk of the world materials to blend toward a warm haze only within a cone around the
 * sun direction. Materials that never get patched simply keep the plain fog.
 * ------------------------------------------------------------------ */
export const aerialUniforms = {
  uSunDirView: { value: new THREE.Vector3(0, 0, -1) },
  uAerialWarm: { value: new THREE.Color(0.52, 0.28, 0.16) },
  uAerialAmount: { value: 0.9 },
};

const AERIAL_FOG_FRAGMENT = /* glsl */`
#ifdef USE_FOG
  #ifdef FOG_EXP2
    float fogFactor = 1.0 - exp( - fogDensity * fogDensity * vFogDepth * vFogDepth );
  #else
    float fogFactor = smoothstep( fogNear, fogFar, vFogDepth );
  #endif
  float aerialSun = max( dot( normalize( vAerialDir ), uSunDirView ), 0.0 );
  vec3 aerialCol = mix( fogColor, uAerialWarm, pow( aerialSun, 3.0 ) * uAerialAmount );
  gl_FragColor.rgb = mix( gl_FragColor.rgb, aerialCol, fogFactor );
#endif
`;

/** Patch one material's fog so distance haze warms up toward the sun. Safe to call twice. */
export function applyAerialPerspective(material) {
  if (!material || material.fog === false) return material;
  if (!material.isMeshStandardMaterial && !material.isMeshPhysicalMaterial && !material.isMeshLambertMaterial && !material.isMeshPhongMaterial) return material;
  material.userData ??= {};
  if (material.userData.__aerial) return material;
  material.userData.__aerial = true;
  const prev = material.onBeforeCompile;
  material.onBeforeCompile = function (shader, renderer) {
    if (prev) prev.call(this, shader, renderer);
    shader.uniforms.uSunDirView = aerialUniforms.uSunDirView;
    shader.uniforms.uAerialWarm = aerialUniforms.uAerialWarm;
    shader.uniforms.uAerialAmount = aerialUniforms.uAerialAmount;
    shader.vertexShader = shader.vertexShader
      .replace('#include <fog_pars_vertex>', '#include <fog_pars_vertex>\n#ifdef USE_FOG\n  varying vec3 vAerialDir;\n#endif')
      .replace('#include <fog_vertex>', '#include <fog_vertex>\n#ifdef USE_FOG\n  vAerialDir = mvPosition.xyz;\n#endif');
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <fog_pars_fragment>', '#include <fog_pars_fragment>\n#ifdef USE_FOG\n  varying vec3 vAerialDir;\n  uniform vec3 uSunDirView;\n  uniform vec3 uAerialWarm;\n  uniform float uAerialAmount;\n#endif')
      .replace('#include <fog_fragment>', AERIAL_FOG_FRAGMENT);
  };
  // programs are cached by shader source signature — keep the patched ones in their own bucket
  const prevKey = material.customProgramCacheKey;
  material.customProgramCacheKey = function () { return 'aerial1|' + (prevKey ? prevKey.call(this) : ''); };
  material.needsUpdate = true;
  return material;
}

/** Call once a frame: the sun direction the fog leans toward, in view space. */
const _aerialM = new THREE.Matrix4();
export function updateAerial(camera) {
  if (!camera) return;
  camera.updateMatrixWorld();
  _aerialM.copy(camera.matrixWorld).invert();
  aerialUniforms.uSunDirView.value.copy(SUN_DIR).transformDirection(_aerialM).normalize();
}

export function createSky() {
  const mat = new THREE.ShaderMaterial({
    uniforms: { uSunDir: { value: SUN_DIR.clone() }, uTime: { value: 0 }, uClouds: { value: 1 } },
    vertexShader: skyVert,
    fragmentShader: skyFrag,
    side: THREE.BackSide,
    depthWrite: false,
    fog: false,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(500, 48, 24), mat);
  mesh.frustumCulled = false;
  mesh.renderOrder = -1;
  mesh.name = 'sky';
  return mesh;
}

// Pre-filtered environment for PBR reflections (sky without animated clouds detail).
export function createEnvironment(renderer) {
  const envScene = new THREE.Scene();
  const sky = createSky();
  sky.material.uniforms.uClouds.value = 0.6;
  envScene.add(sky);
  // warm ground bounce
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(2000, 2000), new THREE.MeshBasicMaterial({ color: new THREE.Color(0.16, 0.11, 0.08) }));
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -2;
  envScene.add(ground);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const rt = pmrem.fromScene(envScene, 0.02, 0.1, 1000);
  pmrem.dispose();
  return rt.texture;
}

// Shadow budget per quality level. `extent` is the half-width of the sun's ortho frustum:
// smaller = finer texels. 4096² over ±28 m is a 1.4 cm texel in the playable core, which is
// what lets a 20 m pole shadow have a real penumbra instead of a stair-stepped edge.
const SHADOW_TIERS = {
  high: { size: 4096, extent: 28, radius: 3.0, taps: 12 },
  medium: { size: 2048, extent: 26, radius: 2.2, taps: 8 },
  low: { size: 1024, extent: 22, radius: 1.4, taps: 0 },
};

/*
 * r186 removed PCFSoftShadowMap; the one soft filter left (SHADOWMAP_TYPE_PCF) is a fixed
 * 5-tap Vogel disk rotated per pixel by interleaved-gradient noise. Five taps is fine for a
 * one-texel radius and falls apart as dither the moment you widen it — which is exactly what
 * a 28 m frustum under a grazing sun needs (environment.md #7: "hard, aliased, one-sample").
 * So widen the kernel itself: the sample block is swapped for a loop with more taps, once,
 * before any material compiles. The patch is a guarded regex — if three's chunk ever changes
 * shape the replace simply does not fire and we keep stock three's 5 taps.
 */
let shadowFilterTaps = 5;
export function configureShadowFilter(taps) {
  if (!taps || taps <= 5 || taps === shadowFilterTaps) return shadowFilterTaps;
  const src = THREE.ShaderChunk.shadowmap_pars_fragment;
  if (typeof src !== 'string') return shadowFilterTaps;
  const re = /shadow = \(\s*(?:texture\(\s*shadowMap,\s*vec3\(\s*shadowCoord\.xy \+ vogelDiskSample\(\s*\d+,\s*5,\s*phi\s*\) \* radius,\s*shadowCoord\.z\s*\)\s*\)\s*\+?\s*){5}\)\s*\* 0\.2\s*;/;
  if (!re.test(src)) return shadowFilterTaps;
  const n = Math.min(24, taps | 0);
  const loop = `shadow = 0.0;
				for ( int i = 0; i < ${n}; i ++ ) {
					shadow += texture( shadowMap, vec3( shadowCoord.xy + vogelDiskSample( i, ${n}, phi ) * radius, shadowCoord.z ) );
				}
				shadow *= ${(1 / n).toFixed(6)};`;
  THREE.ShaderChunk.shadowmap_pars_fragment = src.replace(re, loop);
  shadowFilterTaps = n;
  return n;
}

/** A radius the compiled kernel can actually resolve — 5 taps cannot carry 3 texels. */
function effectiveRadius(tier) {
  return shadowFilterTaps >= 9 ? tier.radius : Math.min(tier.radius, 1.6);
}

// A rim direction opposite the sun and a little above it: this is what gives zombies an edge
// so they read against the fog instead of dissolving into it.
function rimDirection(azimuthDeg = 150, elevationDeg = 25) {
  const az = Math.atan2(SUN_DIR.x, SUN_DIR.z) + THREE.MathUtils.degToRad(azimuthDeg);
  const el = THREE.MathUtils.degToRad(elevationDeg);
  return new THREE.Vector3(Math.sin(az) * Math.cos(el), Math.sin(el), Math.cos(az) * Math.cos(el)).normalize();
}

// the sun shadow camera's basis (lookAt from SUN_DIR towards the target, world up) — used to
// snap the following frustum to whole shadow texels
const _lc = new THREE.Vector3();
const _lx = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), SUN_DIR).normalize();
const _ly = new THREE.Vector3().crossVectors(SUN_DIR, _lx).normalize();

export function createLights(scene, quality = 'high') {
  let tier = SHADOW_TIERS[quality] || SHADOW_TIERS.high;
  // widen the PCF kernel before anything compiles (see configureShadowFilter). The tap count
  // is baked into the shader, so it is chosen once from the launch quality; `radius` still
  // tracks quality changes live.
  configureShadowFilter(tier.taps);

  const sun = new THREE.DirectionalLight(new THREE.Color(1.0, 0.56, 0.3), 3.8);
  sun.name = 'sun';
  sun.position.copy(SUN_DIR).multiplyScalar(80);
  sun.castShadow = true;
  sun.shadow.mapSize.set(tier.size, tier.size);
  Object.assign(sun.shadow.camera, { left: -tier.extent, right: tier.extent, top: tier.extent, bottom: -tier.extent, near: 1, far: 260 });
  // grazing sun over 1.4 cm texels needs a generous normal bias, but a tiny depth bias so
  // planks and debris stop peter-panning off their own contact shadow
  sun.shadow.bias = -0.0002;
  sun.shadow.normalBias = 0.055;
  // r186 PCF: a Vogel disk whose spread is `radius` texels (blurSamples is VSM-only, so
  // setting it here would do nothing). A wide radius over few taps reads as dither, so the
  // radius is clamped to what the compiled kernel can actually carry.
  sun.shadow.radius = effectiveRadius(tier);
  scene.add(sun, sun.target);

  // cool counter-key: no shadow, cheap, and the single biggest silhouette-readability win
  const rim = new THREE.DirectionalLight(new THREE.Color(0.52, 0.62, 0.9), 0.85);
  rim.name = 'rim';
  rim.castShadow = false;
  const rimDir = rimDirection();
  rim.position.copy(rimDir).multiplyScalar(90);
  scene.add(rim, rim.target);

  // warm ground bounce coming back up from the sunlit asphalt — fills shadow sides and
  // undersides that the hemisphere alone leaves as one dead tone
  const bounce = new THREE.DirectionalLight(new THREE.Color(0.85, 0.46, 0.26), 0.5);
  bounce.name = 'bounce';
  bounce.castShadow = false;
  bounce.position.set(SUN_DIR.x * 0.35, -1, SUN_DIR.z * 0.35).normalize().multiplyScalar(60);
  scene.add(bounce, bounce.target);

  const hemi = new THREE.HemisphereLight(new THREE.Color(0.40, 0.40, 0.66), new THREE.Color(0.22, 0.14, 0.10), 0.55);
  scene.add(hemi);

  return {
    sun, hemi, rim, bounce,
    get shadowExtent() { return tier.extent; },
    // keep the shadow frustum centred slightly ahead of the player (most of the frustum is
    // wasted behind the camera otherwise), snapped to texels to avoid shimmering
    follow(pos, forward) {
      const s = tier.extent;
      const texel = (2 * s) / sun.shadow.mapSize.x;
      let tx = pos.x, tz = pos.z;
      if (forward) {
        const lead = s * 0.32;
        tx += forward.x * lead;
        tz += forward.z * lead;
      }
      // snap in LIGHT space: the shadow texels lie on the shadow camera's own x/y axes, and
      // with a low grazing sun a world-XZ snap still slides every edge by sub-texel amounts
      // as you move or turn — which reads as props' shadows crawling/flickering
      _lc.set(tx, 0, tz);
      const lx = Math.round(_lc.dot(_lx) / texel) * texel - _lc.dot(_lx);
      const ly = Math.round(_lc.dot(_ly) / texel) * texel - _lc.dot(_ly);
      _lc.addScaledVector(_lx, lx).addScaledVector(_ly, ly);
      const cx = _lc.x, cy = _lc.y, cz = _lc.z;
      sun.target.position.set(cx, cy, cz);
      sun.position.set(cx, cy, cz).addScaledVector(SUN_DIR, 110);
      sun.target.updateMatrixWorld();
      // the non-shadowing lights only need their direction kept, but re-centring them keeps
      // the target matrices from drifting far from the play area
      rim.target.position.set(cx, 0, cz);
      rim.position.copy(rim.target.position).addScaledVector(rimDir, 90);
      bounce.target.position.set(cx, 1, cz);
      bounce.position.copy(bounce.target.position).addScaledVector(new THREE.Vector3(SUN_DIR.x * 0.35, -1, SUN_DIR.z * 0.35).normalize(), 60);
    },
    setQuality(q) {
      const t = SHADOW_TIERS[q] || SHADOW_TIERS.high;
      if (t === tier) return;
      tier = t;
      // a wider kernel is a shader change: recompile the scene's materials once so a player
      // who starts on low and moves to high actually gets the soft filter, not just the radius
      const before = shadowFilterTaps;
      if (configureShadowFilter(t.taps) !== before) {
        scene.traverse(o => {
          const m = o.material;
          if (!m) return;
          if (Array.isArray(m)) m.forEach(x => { if (x) x.needsUpdate = true; });
          else m.needsUpdate = true;
        });
      }
      sun.shadow.mapSize.set(t.size, t.size);
      Object.assign(sun.shadow.camera, { left: -t.extent, right: t.extent, top: t.extent, bottom: -t.extent });
      sun.shadow.camera.updateProjectionMatrix();
      sun.shadow.radius = effectiveRadius(t);
      // force the shadow map to be re-allocated at the new resolution
      if (sun.shadow.map) { sun.shadow.map.dispose(); sun.shadow.map = null; }
    },
  };
}
