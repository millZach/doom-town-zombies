import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone as skeletonClone } from 'three/addons/utils/SkeletonUtils.js';

const loader = new GLTFLoader();
const cache = new Map();
let manifestVersion = Date.now();   // bust the browser cache so re-exported models show up

// Resolves to the parsed glTF, or null if the file is missing/invalid (the game then uses a placeholder).
export function loadGLB(url, onProgress) {
  if (cache.has(url)) return cache.get(url);
  const p = new Promise(resolve => {
    loader.load(`${url}?v=${manifestVersion}`, gltf => resolve(gltf), onProgress, () => resolve(null));
  }).then(gltf => {
    if (gltf) {
      gltf.scene.traverse(o => {
        if (o.isMesh) {
          o.castShadow = true;
          o.receiveShadow = true;
          const mats = Array.isArray(o.material) ? o.material : [o.material];
          for (const m of mats) if (m && m.map) m.map.anisotropy = 8;
        }
      });
    }
    return gltf;
  });
  cache.set(url, p);
  return p;
}

export function cloneSkinned(obj) { return skeletonClone(obj); }

// Original (unsanitised) glTF node name — GLTFLoader strips dots from .name.
export function nodeName(o) { return o.userData?.name || o.name || ''; }

export function findNode(root, name) {
  let found = null;
  root.traverse(o => { if (!found && (nodeName(o) === name || o.name === name)) found = o; });
  return found;
}

export function materialsOf(obj) {
  const out = [];
  obj.traverse(o => {
    if (!o.isMesh) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    mats.forEach(m => m && out.push(m));
  });
  return out;
}
