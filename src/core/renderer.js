import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { SMAAPass } from 'three/addons/postprocessing/SMAAPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';

// Final colour grade + screen-space gameplay effects, applied in display space.
const GradeShader = {
  uniforms: {
    tDiffuse: { value: null },
    uTime: { value: 0 },
    uResolution: { value: new THREE.Vector2(1, 1) },
    uDamage: { value: 0 },       // recent-hit pulse 0..1
    uLowHealth: { value: 0 },    // persistent blood edges 0..1
    uInstaKill: { value: 0 },
    uDowned: { value: 0 },
    uFlash: { value: 0 },        // white flash (nuke)
    uFlashColor: { value: new THREE.Color(1, 1, 1) },
    uVignette: { value: 0.42 },
    uGrain: { value: 0.045 },
    uAberration: { value: 0.0012 },
    uSaturation: { value: 0.92 },
    uContrast: { value: 1.08 },
    uLift: { value: new THREE.Vector3(0.012, 0.008, 0.01) },
    uGain: { value: new THREE.Vector3(1.03, 1.0, 0.95) },
    uShadowTint: { value: new THREE.Vector3(0.93, 0.97, 1.08) },
    // crepuscular rays: screen-space position of the sun (uv) + strength (0 = off)
    uSunScreen: { value: new THREE.Vector2(0.5, 0.5) },
    uGodRays: { value: 0.0 },
    uRayColor: { value: new THREE.Vector3(1.0, 0.56, 0.26) },
    // heat haze over the fires: up to 4 sources as (uv.x, uv.y, screen radius, strength)
    uHeat: { value: [new THREE.Vector4(), new THREE.Vector4(), new THREE.Vector4(), new THREE.Vector4()] },
    uHeatCount: { value: 0 },
  },
  vertexShader: /* glsl */`
    varying vec2 vUv;
    void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: /* glsl */`
    uniform sampler2D tDiffuse;
    uniform float uTime, uDamage, uLowHealth, uInstaKill, uDowned, uFlash, uVignette, uGrain, uAberration, uSaturation, uContrast;
    uniform float uGodRays;
    uniform vec2 uResolution, uSunScreen;
    uniform vec3 uLift, uGain, uShadowTint, uFlashColor, uRayColor;
    uniform vec4 uHeat[4];
    uniform int uHeatCount;
    varying vec2 vUv;

    float hash(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
    float noise(vec2 p) {
      vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
      return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
    }
    float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 5; i++) { v += a * noise(p); p *= 2.03; a *= 0.5; } return v; }

    void main() {
      vec2 uv = vUv;

      // heat haze: the air above a fire shivers. Screen-space, so it is nearly free, and it
      // is what makes a fire feel hot instead of being an orange sprite (environment.md #12b).
      if (uHeatCount > 0) {
        float aspect = uResolution.x / max(uResolution.y, 1.0);
        vec2 off = vec2(0.0);
        for (int i = 0; i < 4; i++) {
          float on = step(float(i) + 0.5, float(uHeatCount));
          vec4 hz = uHeat[i];
          vec2 d = (vUv - hz.xy) / max(hz.z, 1e-4);
          d.x *= aspect;
          // the column rises: the mask reaches further up than down
          d.y *= vUv.y > hz.y ? 0.55 : 1.6;
          float m = smoothstep(1.0, 0.1, length(d)) * hz.w * on;
          float w1 = noise(vec2(vUv.x * 46.0, vUv.y * 26.0 - uTime * 2.1) + float(i) * 7.0);
          float w2 = noise(vec2(vUv.y * 38.0, vUv.x * 30.0 - uTime * 1.5) + float(i) * 3.0);
          off += vec2((w1 - 0.5) * 0.011, (w2 - 0.5) * 0.007) * m;
        }
        uv += off;
      }

      vec2 c = uv - 0.5;
      float r2 = dot(c, c);
      // downed / heavy-damage wobble
      uv += c * (uDowned * 0.02 * sin(uTime * 1.7)) ;
      float ab = uAberration * (1.0 + uDamage * 4.0 + uDowned * 3.0) * (0.3 + r2 * 4.0);
      vec3 col;
      col.r = texture2D(tDiffuse, uv + c * ab).r;
      col.g = texture2D(tDiffuse, uv).g;
      col.b = texture2D(tDiffuse, uv - c * ab).b;

      // grade: lift/gain, split tone, contrast, saturation
      float luma = dot(col, vec3(0.2126, 0.7152, 0.0722));
      col = mix(col * uShadowTint, col, smoothstep(0.0, 0.45, luma));
      col = col * uGain + uLift * (1.0 - col);
      col = (col - 0.5) * uContrast + 0.5;
      luma = dot(col, vec3(0.2126, 0.7152, 0.0722));
      col = mix(vec3(luma), col, uSaturation * (1.0 - uDowned * 0.75));

      // insta-kill: desaturated with a cold tint
      if (uInstaKill > 0.0) {
        float l = dot(col, vec3(0.299, 0.587, 0.114));
        col = mix(col, vec3(l) * vec3(0.85, 0.95, 1.05) * 1.05, uInstaKill * 0.55);
      }

      // crepuscular rays: radial accumulation of the sky's bright sun term, occluded for free
      // by everything dark that stands in front of it (buildings, poles, the horde).
      if (uGodRays > 0.005) {
        vec2 toSun = uSunScreen - vUv;
        float sunDist = length(toSun);
        vec2 dir = toSun / max(sunDist, 1e-4);
        float stepLen = min(sunDist, 0.5) / 14.0;
        vec2 sp = vUv;
        float acc = 0.0, w = 1.0, wsum = 0.0;
        for (int i = 0; i < 14; i++) {
          sp += dir * stepLen;
          vec3 s = texture2D(tDiffuse, clamp(sp, vec2(0.0), vec2(1.0))).rgb;
          float l = dot(s, vec3(0.2126, 0.7152, 0.0722));
          acc += smoothstep(0.58, 0.98, l) * w;
          wsum += w;
          w *= 0.87;
        }
        acc /= max(wsum, 1e-4);
        // strongest close to the disc, gone by the far corner of the screen
        float near = smoothstep(1.05, 0.12, sunDist);
        col += uRayColor * acc * near * uGodRays;
      }

      // vignette
      float vig = smoothstep(0.85, 0.2, length(c * vec2(1.0, 0.85)) * (1.0 + uVignette));
      col *= mix(1.0, vig, 0.85);

      // blood edges (low health + hit pulses)
      float edge = smoothstep(0.08, 0.42, r2 + (fbm(uv * 5.0 + uTime * 0.05) - 0.5) * 0.12);
      float blood = clamp(uLowHealth * 0.9 + uDamage * 0.7, 0.0, 1.0) * edge;
      vec3 bloodCol = vec3(0.32, 0.0, 0.0) + vec3(0.25, 0.0, 0.0) * fbm(uv * 12.0);
      col = mix(col, bloodCol * (0.6 + 0.4 * col.r), clamp(blood, 0.0, 0.92));
      col.r += uDamage * 0.12 * edge;

      // downed: darken edges hard, red wash
      col = mix(col, col * vec3(0.9, 0.35, 0.3), uDowned * 0.5);
      col *= 1.0 - uDowned * smoothstep(0.05, 0.3, r2) * 0.8;

      // flash
      col = mix(col, uFlashColor, clamp(uFlash, 0.0, 1.0));

      // film grain
      float g = hash(uv * uResolution + fract(uTime * 37.0) * 100.0) - 0.5;
      col += g * uGrain * (1.0 - luma * 0.5);
      // 8-bit output dither: kills the gradient banding in the sky, costs nothing
      col += (hash(gl_FragCoord.xy + fract(uTime * 11.0)) - 0.5) * (1.6 / 255.0);

      gl_FragColor = vec4(max(col, 0.0), 1.0);
    }`,
};

export class Renderer {
  constructor(container) {
    this.container = container;
    const r = this.renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: 'high-performance', stencil: false });
    r.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    r.setSize(window.innerWidth, window.innerHeight);
    r.shadowMap.enabled = true;
    // PCFShadowMap is the only soft filter left in r186: PCFSoftShadowMap was removed and
    // WebGLShadowMap silently reverts to this one (with a console warning) if you ask for it.
    // r186's PCF is a 5-tap Vogel disk rotated by interleaved-gradient noise and scaled by
    // `shadow.radius`, so the penumbra width is driven from sky.js:SHADOW_TIERS.radius.
    r.shadowMap.type = THREE.PCFShadowMap;
    r.toneMapping = THREE.AgXToneMapping;
    r.toneMappingExposure = 1.0;
    r.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(r.domElement);

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.05, 900);

    // viewmodel: own scene + camera, drawn on top after clearing depth
    this.vmScene = new THREE.Scene();
    this.vmCamera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.01, 10);

    this.quality = 'high';
    this.godRaysAllowed = true;
    // anything that wants to react to the quality setting (light rigs, shadow budgets)
    this.onQualityChange = null;
    this._buildComposer();
    window.addEventListener('resize', () => this.resize());
  }

  // MSAA on the HDR buffer: SMAA alone cannot hold sub-pixel geometry (power lines, picket
  // fences, debris edges). WebGL2 only; 0 disables it.
  _samplesFor(q) {
    if (!this.renderer.capabilities.isWebGL2) return 0;
    return q === 'low' ? 0 : 2;   // 4x on a half-float target cost far more than it bought
  }

  setSamples(n) {
    const c = this.composer;
    if (!c || !c.renderTarget1) return;
    for (const rt of [c.renderTarget1, c.renderTarget2]) {
      if (!rt || rt.samples === n) continue;
      rt.samples = n;
      rt.dispose();   // forces the framebuffer to be re-created with the new sample count
    }
  }

  _buildComposer() {
    const r = this.renderer;
    const w = window.innerWidth, h = window.innerHeight;
    const target = new THREE.WebGLRenderTarget(w * r.getPixelRatio(), h * r.getPixelRatio(), { type: THREE.HalfFloatType, samples: this._samplesFor(this.quality) });
    const composer = this.composer = new EffectComposer(r, target);
    composer.setPixelRatio(r.getPixelRatio());
    composer.setSize(w, h);

    this.worldPass = new RenderPass(this.scene, this.camera);
    composer.addPass(this.worldPass);

    // world-only AO (the viewmodel is drawn after this, so it never gets creased by it).
    // 1.1 m radius so props actually darken where they meet the ground outdoors.
    this.gtao = new GTAOPass(this.scene, this.camera, w, h);
    this.gtao.output = GTAOPass.OUTPUT.Default;
    this.gtao.blendIntensity = 0.85;
    this.gtao.updateGtaoMaterial({ radius: 1.1, distanceExponent: 1.8, thickness: 0.6, scale: 1.0, samples: 16, screenSpaceRadius: false });
    this.gtao.updatePdMaterial({ lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 5, radiusExponent: 1, rings: 2, samples: 16 });
    // AO is low-frequency: compute it at half resolution (a quarter of the fill cost) and let
    // the blend upsample it. The G-buffer pre-pass shrinks with it.
    const gtaoSetSize = this.gtao.setSize.bind(this.gtao);
    this.gtao.setSize = (width, height) => gtaoSetSize(Math.max(1, (width * 0.5) | 0), Math.max(1, (height * 0.5) | 0));
    composer.addPass(this.gtao);

    // Emissives should bloom, lit surfaces should not: high threshold, tight radius.
    this.bloom = new UnrealBloomPass(new THREE.Vector2(w, h), 0.32, 0.4, 1.15);
    composer.addPass(this.bloom);

    // The viewmodel is composited AFTER bloom so it can never smear into a white ghost
    // when the muzzle flash lights it. It still gets tone-mapped by OutputPass below.
    this.vmPass = new RenderPass(this.vmScene, this.vmCamera);
    this.vmPass.clear = false;
    this.vmPass.clearDepth = true;
    composer.addPass(this.vmPass);

    composer.addPass(new OutputPass());

    this.smaa = new SMAAPass();
    composer.addPass(this.smaa);

    this.grade = new ShaderPass(GradeShader);
    composer.addPass(this.grade);
  }

  setQuality(q) {
    this.quality = q;
    const pr = q === 'low' ? 0.75 : q === 'medium' ? 1.0 : Math.min(window.devicePixelRatio, 1.25);
    this.renderer.setPixelRatio(pr);
    this.composer.setPixelRatio(pr);
    this.gtao.enabled = q !== 'low';
    if (this.gtao.enabled) {
      const s = q === 'medium' ? 10 : 16;
      this.gtao.updateGtaoMaterial({ radius: 1.1, distanceExponent: 1.8, thickness: 0.6, scale: 1.0, samples: s, screenSpaceRadius: false });
    }
    this.setSamples(this._samplesFor(q));
    this.grade.uniforms.uGodRays.value = q === 'low' ? 0 : this.grade.uniforms.uGodRays.value;
    this.godRaysAllowed = q !== 'low';
    this.resize();
    this.onQualityChange?.(q);
  }

  resize() {
    const w = window.innerWidth, h = window.innerHeight;
    this.camera.aspect = this.vmCamera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.vmCamera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
    this.composer.setSize(w, h);
    this.grade.uniforms.uResolution.value.set(w, h);
  }

  render(dt, time) {
    this.grade.uniforms.uTime.value = time;
    this.composer.render(dt);
  }
}
