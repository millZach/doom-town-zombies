import * as THREE from 'three';
import { MeshBVH } from 'three-mesh-bvh';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

// World-space baked collision geometry in BVHs: one static set plus toggleable dynamic sets
// (door blockers, window-barrier blockers).
function bakeGeometry(meshes) {
  const geos = [];
  for (const m of meshes) {
    m.updateWorldMatrix(true, false);
    let g = m.geometry.clone();
    g = g.index ? g.toNonIndexed() : g;
    for (const k of Object.keys(g.attributes)) if (k !== 'position') g.deleteAttribute(k);
    g.applyMatrix4(m.matrixWorld);
    geos.push(g);
  }
  if (!geos.length) return null;
  const merged = mergeGeometries(geos, false);
  return merged;
}

const _seg = new THREE.Line3();
const _box = new THREE.Box3();
const _triPt = new THREE.Vector3();
const _capPt = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _ray = new THREE.Ray();
const _tn = new THREE.Vector3();

export class Collision {
  constructor() {
    this.static = null;           // MeshBVH
    this.dynamic = [];            // { id, kind: 'door'|'barrier', bvh, enabled }
  }

  setStatic(meshes) {
    const g = bakeGeometry(meshes);
    this.static = g ? new MeshBVH(g) : null;
  }

  addDynamic(id, kind, meshes) {
    const g = bakeGeometry(meshes);
    if (!g) return null;
    const entry = { id, kind, bvh: new MeshBVH(g), enabled: true, box: new THREE.Box3() };
    g.computeBoundingBox();
    entry.box.copy(g.boundingBox);
    this.dynamic.push(entry);
    return entry;
  }

  setEnabled(id, enabled) {
    for (const d of this.dynamic) if (d.id === id) d.enabled = enabled;
  }

  *_sets(mask) {
    if (this.static) yield this.static;
    for (const d of this.dynamic) {
      if (!d.enabled) continue;
      if (d.kind === 'door' && mask.doors) yield d.bvh;
      if (d.kind === 'barrier' && mask.barriers) yield d.bvh;
    }
  }

  /**
   * Push a capsule (segment start/end + radius) out of the geometry. Mutates start/end.
   * Returns the largest upward push normal seen (for ground detection).
   * `walkable` (a normal.y threshold, 0 = off): contacts at least that flat are resolved by a
   * purely vertical lift, so a slope never shoves the capsule back down itself — without it
   * every ramp bleeds off most of the uphill velocity as if it were a wall.
   */
  capsule(start, end, radius, mask = { doors: true, barriers: true }, walkable = 0) {
    _seg.start.copy(start); _seg.end.copy(end);
    let maxUp = 0;
    for (let iter = 0; iter < 2; iter++) {
      for (const bvh of this._sets(mask)) {
        _box.makeEmpty();
        _box.expandByPoint(_seg.start); _box.expandByPoint(_seg.end);
        _box.min.addScalar(-radius); _box.max.addScalar(radius);
        bvh.shapecast({
          intersectsBounds: b => b.intersectsBox(_box),
          intersectsTriangle: tri => {
            const dist = tri.closestPointToSegment(_seg, _triPt, _capPt);
            if (dist < radius) {
              const depth = radius - dist;
              if (dist > 1e-5) _dir.subVectors(_capPt, _triPt).divideScalar(dist);
              else { tri.getNormal(_tn); _dir.copy(_tn); }
              if (_dir.y > maxUp) maxUp = _dir.y;
              if (walkable > 0 && _dir.y >= walkable) {
                const lift = Math.min(depth / _dir.y, radius);
                _seg.start.y += lift; _seg.end.y += lift;
              } else {
                _seg.start.addScaledVector(_dir, depth);
                _seg.end.addScaledVector(_dir, depth);
              }
            }
          },
        });
      }
    }
    start.copy(_seg.start); end.copy(_seg.end);
    return maxUp;
  }

  /** Nearest hit or null: { point, normal, distance } */
  raycast(origin, dir, far = 1000, mask = { doors: true, barriers: false }) {
    _ray.origin.copy(origin); _ray.direction.copy(dir);
    let best = null;
    for (const bvh of this._sets(mask)) {
      const hit = bvh.raycastFirst(_ray, THREE.DoubleSide, 0, far);
      if (hit && (!best || hit.distance < best.distance)) best = hit;
    }
    if (!best) return null;
    const n = best.face ? best.face.normal.clone() : new THREE.Vector3(0, 1, 0);
    if (n.dot(dir) > 0) n.negate();
    return { point: best.point.clone(), normal: n, distance: best.distance };
  }

  /** Ground height below (x, fromY, z), or null. */
  ground(x, z, fromY = 5, maxDrop = 20, mask = { doors: true, barriers: false }) {
    const hit = this.raycast(new THREE.Vector3(x, fromY, z), new THREE.Vector3(0, -1, 0), maxDrop, mask);
    return hit ? hit.point.y : null;
  }
}
