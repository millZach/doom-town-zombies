import * as THREE from 'three';

/**
 * Multi-level navigation grid + Dijkstra flow field toward the player.
 *
 * The world is cut into 0.5 m cells in XZ. Each cell stores up to K walkable *surfaces*
 * ("layers"), found by repeatedly raycasting down from the top of the zone box that covers
 * the cell. A surface counts when the hit faces up (normal.y > 0.6) and there is at least
 * HEADROOM metres of free space above it — so a table top, the underside of a slab or the
 * gap under a staircase never become nodes, but the ground floor *under* an upper floor does.
 *
 * A node is (cell, layer) and is addressed by one integer:  node = cell * K + layer.
 * Layers are stored bottom-up (layer 0 is the lowest surface in that cell).
 * All the per-node arrays (`height`, `edges`, `near`, `dist`) are indexed by node, so the
 * old `nav.height[idx] / nav.dist[idx] / nav.cx(idx)` style still works — `idx` is now a node.
 *
 * Every query takes the agent's y so it can pick the right layer:
 *   index/nodeAt(x,y,z), heightAt(x,y,z), distanceAt(x,y,z), direction(x,y,z,out),
 *   updateFlow(x,y,z), nearestWalkable(x,y,z,r), lineClear(ax,ay,az,bx,by,bz).
 * The old 2-arg / 4-arg forms still work and mean "the lowest layer in that cell".
 */
// 8 neighbours: 0..3 orthogonal (+x, -x, +z, -z), 4..7 diagonal
const DX = new Int8Array([1, -1, 0, 0, 1, 1, -1, -1]);
const DZ = new Int8Array([0, 0, 1, -1, 1, -1, 1, -1]);

const MAX_STEP = 0.45;        // biggest height change an agent can walk over (per 0.5 m cell)
const K = 4;                  // layers per cell (2 bits per direction in `edgeLayer`)
const HEADROOM = 1.7;         // free space a surface needs above it to be walkable
const MIN_LAYER_GAP = 0.5;    // two surfaces closer than this are the same floor
const MAX_PROBE = 10;         // downward raycasts per cell
const SAME_FLOOR = 1.2;       // a surface further than this off the query y is only a fallback
const PROBE_MASK = { doors: false, barriers: false };   // surfaces are static: doors only gate edges
const WALL_MASK = { doors: true, barriers: true };

const _up = new THREE.Vector3(0, 1, 0);
const _down = new THREE.Vector3(0, -1, 0);
const _o = new THREE.Vector3();
const _d3 = new THREE.Vector3();

/** How badly a surface at height `h` fits an agent whose feet are at `y` (above is 3x worse). */
function vScore(h, y) { const d = h - y; return d > 0 ? d * 3 : -d; }

class MinHeap {
  constructor(n) { this.idx = new Int32Array(n); this.key = new Float32Array(n); this.size = 0; this.topKey = 0; }
  push(i, k) {
    let p = this.size++;
    while (p > 0) {
      const parent = (p - 1) >> 1;
      if (this.key[parent] <= k) break;
      this.idx[p] = this.idx[parent]; this.key[p] = this.key[parent]; p = parent;
    }
    this.idx[p] = i; this.key[p] = k;
  }
  pop() {
    const top = this.idx[0];
    this.topKey = this.key[0];
    const li = this.idx[--this.size], lk = this.key[this.size];
    let p = 0;
    for (;;) {
      let c = 2 * p + 1;
      if (c >= this.size) break;
      if (c + 1 < this.size && this.key[c + 1] < this.key[c]) c++;
      if (this.key[c] >= lk) break;
      this.idx[p] = this.idx[c]; this.key[p] = this.key[c]; p = c;
    }
    this.idx[p] = li; this.key[p] = lk;
    return top;
  }
}

export class NavGrid {
  constructor(collision, zoneBoxes, cell = 0.5) {
    this.col = collision;
    this.cell = cell;
    this.K = K;
    const b = new THREE.Box3();
    zoneBoxes.forEach(z => b.union(z.box));
    this.minX = Math.floor(b.min.x) - 1; this.minZ = Math.floor(b.min.z) - 1;
    this.w = Math.ceil((b.max.x - this.minX + 1) / cell);
    this.h = Math.ceil((b.max.z - this.minZ + 1) / cell);
    const cells = this.w * this.h;
    const n = cells * K;
    this.cells = cells;
    this.height = new Float32Array(n).fill(NaN);   // per node: surface height
    this.layers = new Uint8Array(cells);           // per cell: how many layer slots are in use
    this.edges = new Uint8Array(n);                // per node: 8-neighbour bitmask
    this.edgeLayer = new Uint16Array(n);           // per node: 2 bits per direction = neighbour layer
    this.near = new Uint8Array(n);                 // nodes hugging walls cost more
    this.tight = new Uint8Array(n);                // 1 = a zombie's body doesn't fit here (static geometry)
    this.blocked = new Uint8Array(n);              // 1 = pruned island (geometry kept, see pruneIslands)
    this.dist = new Float32Array(n).fill(Infinity);
    this.zoneBoxes = zoneBoxes;
    this.heap = new MinHeap(n * 8);
    this.target = -1;
    this._buf = new Float64Array(K);
  }

  // ---------------------------------------------------------------- addressing
  /** Cell index (ignores y), or -1 outside the grid. */
  cellIndex(x, z) {
    const i = Math.floor((x - this.minX) / this.cell), j = Math.floor((z - this.minZ) / this.cell);
    if (i < 0 || j < 0 || i >= this.w || j >= this.h) return -1;
    return j * this.w + i;
  }
  cellOf(node) { return (node / K) | 0; }
  layerOf(node) { return node - ((node / K) | 0) * K; }
  cx(node) { const ci = (node / K) | 0; return this.minX + ((ci % this.w) + 0.5) * this.cell; }
  cz(node) { const ci = (node / K) | 0; return this.minZ + (((ci / this.w) | 0) + 0.5) * this.cell; }
  nodeHeight(node) { return node < 0 ? NaN : this.height[node]; }

  /** Layer in cell `ci` whose surface best matches feet height `y`; -1 if the cell is empty. */
  _layerAt(ci, y) {
    const cnt = this.layers[ci];
    if (!cnt) return -1;
    const base = ci * K;
    if (!isFinite(y)) {
      // legacy 2-arg queries: the lowest (y = -Infinity) or highest (y = +Infinity) surface
      if (y > 0) { for (let l = cnt - 1; l >= 0; l--) if (!isNaN(this.height[base + l]) && !this.blocked[base + l]) return l; return -1; }
      for (let l = 0; l < cnt; l++) if (!isNaN(this.height[base + l]) && !this.blocked[base + l]) return l;
      return -1;
    }
    let best = -1, bd = Infinity;
    for (let l = 0; l < cnt; l++) {
      const h = this.height[base + l];
      if (isNaN(h) || this.blocked[base + l]) continue;
      const s = vScore(h, y);
      if (s < bd) { bd = s; best = l; }
    }
    return best;
  }

  /**
   * Node index for a world point, or -1.
   * `index(x, y, z)` — picks the layer closest to (and not far above) y.
   * `index(x, z)`    — legacy: the lowest layer in the cell.
   */
  index(x, y, z) {
    if (z === undefined) { z = y; y = -Infinity; }
    const ci = this.cellIndex(x, z);
    if (ci < 0) return -1;
    const l = this._layerAt(ci, y);
    return l < 0 ? -1 : ci * K + l;
  }
  nodeAt(x, y, z) { return this.index(x, y, z); }

  // ---------------------------------------------------------------- build
  build() {
    const t0 = performance.now();
    for (let ci = 0; ci < this.cells; ci++) this._probeCell(ci);
    const t1 = performance.now();
    for (let ci = 0; ci < this.cells; ci++) {
      const cnt = this.layers[ci];
      for (let l = 0; l < cnt; l++) this._buildEdges(ci * K + l);
    }
    this._markTight();
    this._markNear();
    let nodes = 0, stacked = 0;
    for (let ci = 0; ci < this.cells; ci++) { nodes += this.layers[ci]; if (this.layers[ci] > 1) stacked++; }
    console.log(`[nav] ${this.w}x${this.h}x${K} grid built in ${(performance.now() - t0).toFixed(0)} ms (probe ${(t1 - t0).toFixed(0)} ms), ${nodes} nodes, ${stacked} stacked cells`);
  }

  /** Find every walkable surface in a cell, bottom-up, by repeated downward rays. */
  _probeCell(ci) {
    const base = ci * K;
    for (let l = 0; l < K; l++) { this.height[base + l] = NaN; this.edges[base + l] = 0; this.edgeLayer[base + l] = 0; this.near[base + l] = 0; this.blocked[base + l] = 0; }
    this.layers[ci] = 0;
    const x = this.cx(base), z = this.cz(base);
    let top = -Infinity, bot = Infinity;
    for (const zb of this.zoneBoxes) {
      const b = zb.box;
      if (x >= b.min.x && x <= b.max.x && z >= b.min.z && z <= b.max.z) {
        if (b.max.y > top) top = b.max.y;
        if (b.min.y < bot) bot = b.min.y;
      }
    }
    if (top === -Infinity) return;
    const floor = bot - 1.5;
    const buf = this._buf;
    let y = top + 0.5, count = 0, last = Infinity;
    for (let iter = 0; iter < MAX_PROBE && count < K; iter++) {
      const far = y - floor;
      if (far <= 0) break;
      _o.set(x, y, z);
      const hit = this.col.raycast(_o, _down, far, PROBE_MASK);
      if (!hit) break;
      const hy = hit.point.y;
      y = hy - 0.02;                         // continue just below this face
      if (hit.normal.y <= 0.6) continue;     // a wall or a ceiling, not a floor
      if (last - hy < MIN_LAYER_GAP) continue;   // the far side of the slab we just accepted
      _o.set(x, hy + 0.05, z);
      if (this.col.raycast(_o, _up, HEADROOM, PROBE_MASK)) continue;   // no room to stand
      buf[count++] = hy;
      last = hy;
    }
    for (let l = 0; l < count; l++) this.height[base + l] = buf[count - 1 - l];   // store bottom-up
    this.layers[ci] = count;
  }

  _buildEdges(node) {
    this.edges[node] = 0;
    this.edgeLayer[node] = 0;
    const h0 = this.height[node];
    if (isNaN(h0)) return;
    const ci = (node / K) | 0;
    const i = ci % this.w, j = (ci - i) / this.w;
    const x0 = this.cx(node), z0 = this.cz(node);
    for (let d = 0; d < 8; d++) {
      const ni = i + DX[d], nj = j + DZ[d];
      if (ni < 0 || nj < 0 || ni >= this.w || nj >= this.h) continue;
      if (d >= 4 && !this._orthoOk(node, d)) continue;   // no corner cutting
      const nci = nj * this.w + ni;
      const cnt = this.layers[nci];
      if (!cnt) continue;
      const step = MAX_STEP * (d >= 4 ? 1.41 : 1);
      // closest reachable surface in the neighbouring cell
      let bl = -1, bh = 0, bd = Infinity;
      for (let l = 0; l < cnt; l++) {
        const h1 = this.height[nci * K + l];
        if (isNaN(h1)) continue;
        const dh = Math.abs(h1 - h0);
        if (dh > step || dh >= bd) continue;
        bd = dh; bl = l; bh = h1;
      }
      if (bl < 0) continue;
      // wall between? (cast from this node's own height, following the ramp)
      const len = this.cell * (d >= 4 ? Math.SQRT2 : 1);
      const hy = (bh - h0) / len;
      const inv = 1 / Math.hypot(DX[d], DZ[d]);
      let blocked = false;
      for (let u = 0; u < 2; u++) {
        _o.set(x0, h0 + (u ? 1.3 : 0.5), z0);
        _d3.set(DX[d] * inv, hy, DZ[d] * inv).normalize();
        if (this.col.raycast(_o, _d3, len * Math.sqrt(1 + hy * hy) + 0.05, WALL_MASK)) { blocked = true; break; }
      }
      if (blocked) continue;
      this.edges[node] |= 1 << d;
      this.edgeLayer[node] |= (bl & 3) << (d * 2);
    }
  }

  _orthoOk(node, d) {
    // diagonal only if both orthogonal neighbours are open (dirs 0..3 are built first)
    const ox = DX[d] > 0 ? 0 : 1, oz = DZ[d] > 0 ? 2 : 3;
    const e = this.edges[node];
    return (e & (1 << ox)) !== 0 && (e & (1 << oz)) !== 0;
  }

  /**
   * Body clearance. Edges are only tested along the line between cell centres, so a 0.1 m slot
   * between a car and a crate reads as open road and the flow field routes zombies into it,
   * where their 0.3 m+ bodies wedge. A node whose centre can't hold a zombie-sized capsule is
   * marked tight; it stays walkable (a narrow doorway is the only way through, and every route
   * through it pays the same) but costs enough that open ground always wins when there is any.
   */
  _markTight() {
    const R = 0.3, a = new THREE.Vector3(), b = new THREE.Vector3();
    for (let node = 0; node < this.height.length; node++) {
      this.tight[node] = 0;
      const h = this.height[node];
      if (isNaN(h)) continue;
      const x = this.cx(node), z = this.cz(node);
      a.set(x, h + 0.5 + R, z); b.set(x, h + 1.4, z);
      this.col.capsule(a, b, R, PROBE_MASK);
      if (Math.abs(a.x - x) + Math.abs(a.z - z) > 0.05) this.tight[node] = 1;
    }
  }

  _markNear() {
    for (let node = 0; node < this.height.length; node++) {
      this.near[node] = isNaN(this.height[node]) ? 0 : this.tight[node] ? 4 : ((this.edges[node] & 0x0f) !== 0x0f ? 1 : 0);
    }
  }

  /** Neighbour node across edge `d` of `node` (caller must have checked the edge bit). */
  _step(node, d) {
    const ci = (node / K) | 0;
    const i = ci % this.w, j = (ci - i) / this.w;
    const nci = (j + DZ[d]) * this.w + (i + DX[d]);
    return nci * K + ((this.edgeLayer[node] >> (d * 2)) & 3);
  }

  /**
   * Mark every node not connected to a seed point (car roofs, crate tops, sealed rooms).
   * The geometry is *kept* — only `blocked` is set — so re-running this after a door opens
   * can hand a whole sealed storey back, even though `rebuildRegion` only re-probes the
   * handful of cells around the door itself.
   */
  pruneIslands(seeds) {
    const n = this.height.length;
    const seen = this._seen && this._seen.length === n ? this._seen.fill(0) : (this._seen = new Uint8Array(n));
    const stack = [];
    for (const s of seeds) {
      const i = this._search(s.x, s.y ?? -Infinity, s.z, 2, false, true);
      if (i >= 0 && !seen[i]) { seen[i] = 1; stack.push(i); }
    }
    while (stack.length) {
      const node = stack.pop();
      const e = this.edges[node];
      for (let d = 0; d < 8; d++) {
        if (!(e & (1 << d))) continue;
        const k = this._step(node, d);
        if (!seen[k] && !isNaN(this.height[k])) { seen[k] = 1; stack.push(k); }
      }
    }
    let removed = 0;
    for (let k = 0; k < n; k++) {
      if (isNaN(this.height[k])) { this.blocked[k] = 0; continue; }
      this.blocked[k] = seen[k] ? 0 : 1;
      if (!seen[k]) removed++;
    }
    this.seeds = seeds;
    this.target = -1;
    console.log(`[nav] pruned ${removed} unreachable nodes`);
  }

  /** Recompute a region (e.g. after a door opens). */
  rebuildRegion(box) {
    const i0 = Math.max(0, Math.floor((box.min.x - this.minX) / this.cell) - 2), i1 = Math.min(this.w - 1, Math.ceil((box.max.x - this.minX) / this.cell) + 2);
    const j0 = Math.max(0, Math.floor((box.min.z - this.minZ) / this.cell) - 2), j1 = Math.min(this.h - 1, Math.ceil((box.max.z - this.minZ) / this.cell) + 2);
    for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) this._probeCell(j * this.w + i);
    for (let j = Math.max(0, j0 - 1); j <= Math.min(this.h - 1, j1 + 1); j++)
      for (let i = Math.max(0, i0 - 1); i <= Math.min(this.w - 1, i1 + 1); i++) {
        const ci = j * this.w + i;
        const cnt = this.layers[ci];
        for (let l = 0; l < cnt; l++) this._buildEdges(ci * K + l);
      }
    this._markNear();
    if (this.seeds) this.pruneIslands(this.seeds);
    this.target = -1;
  }

  // ---------------------------------------------------------------- queries
  walkable(node) { return node >= 0 && !isNaN(this.height[node]) && this.edges[node] !== 0 && !this.blocked[node]; }

  /**
   * Nearest walkable node to a point.
   * `nearestWalkable(x, y, z, maxR)` — new form; `nearestWalkable(x, z)` — legacy (lowest layer).
   */
  nearestWalkable(x, y, z, maxR = 6) {
    if (arguments.length <= 2) { z = y; y = -Infinity; maxR = 6; }
    return this._search(x, y, z, maxR, false);
  }
  /** Same, but only nodes the current flow field can reach. */
  nearestReachable(x, y, z, maxR = 6) { return this._search(x, y, z, maxR, true); }

  /**
   * Ring search. A surface more than SAME_FLOOR metres off `y` is only ever a fallback: a
   * seed (or a player) standing inside a crate must not latch onto the crate's *roof* just
   * because that is the only surface in its own cell — it keeps looking for real floor first.
   */
  _search(x, y, z, maxR, needFinite, ignoreBlocked) {
    const fin = isFinite(y);
    let fb = -1, fbs = Infinity;
    const ci0 = this.cellIndex(x, z);
    if (ci0 >= 0) {
      const node = this._bestIn(ci0, y, needFinite, ignoreBlocked);
      if (node >= 0) {
        const s = fin ? vScore(this.height[node], y) : 0;
        if (s <= SAME_FLOOR) return node;
        fb = node; fbs = s;
      }
    }
    const ci = Math.floor((x - this.minX) / this.cell), cj = Math.floor((z - this.minZ) / this.cell);
    const rings = Math.ceil(maxR / this.cell);
    for (let r = 1; r <= rings; r++) {
      let best = -1, bd = Infinity, bs = 0;
      for (let dj = -r; dj <= r; dj++) {
        const aj = Math.abs(dj);
        for (let di = -r; di <= r; di++) {
          if (aj !== r && Math.abs(di) !== r) continue;
          const i = ci + di, j = cj + dj;
          if (i < 0 || j < 0 || i >= this.w || j >= this.h) continue;
          const node = this._bestIn(j * this.w + i, y, needFinite, ignoreBlocked);
          if (node < 0) continue;
          const dh = fin ? vScore(this.height[node], y) : 0;
          const d = di * di + dj * dj + dh * dh * 4;
          if (d < bd) { bd = d; best = node; bs = dh; }
        }
      }
      if (best < 0) continue;
      if (bs <= SAME_FLOOR) return best;
      if (bs < fbs) { fb = best; fbs = bs; }
    }
    return fb;
  }

  /** Best walkable layer of a cell for feet height y, or -1. */
  _bestIn(ci, y, needFinite, ignoreBlocked) {
    const cnt = this.layers[ci];
    if (!cnt) return -1;
    const base = ci * K;
    let best = -1, bd = Infinity;
    for (let l = 0; l < cnt; l++) {
      const node = base + l;
      const h = this.height[node];
      if (isNaN(h) || this.edges[node] === 0) continue;
      if (this.blocked[node] && !ignoreBlocked) continue;
      if (needFinite && !isFinite(this.dist[node])) continue;
      const s = isFinite(y) ? vScore(h, y) : (y > 0 ? -l : l);
      if (s < bd) { bd = s; best = node; }
    }
    return best;
  }

  /** Dijkstra from the target position. `updateFlow(x, y, z)` (legacy: `updateFlow(x, z)`). */
  updateFlow(x, y, z) {
    if (z === undefined) { z = y; y = -Infinity; }
    const t = this.nearestWalkable(x, y, z);
    if (t < 0) return;
    if (t === this.target) return;
    this.target = t;
    const dist = this.dist;
    dist.fill(Infinity);
    const heap = this.heap;
    heap.size = 0;
    dist[t] = 0;
    heap.push(t, 0);
    const w = this.w, edges = this.edges, edgeLayer = this.edgeLayer, near = this.near, blocked = this.blocked;
    while (heap.size) {
      const node = heap.pop();
      const d0 = dist[node];
      if (heap.topKey > d0) continue;        // stale entry, already settled by a shorter path
      const ci = (node / K) | 0;
      const i = ci % w, j = (ci - i) / w;
      const e = edges[node], el = edgeLayer[node];
      if (!e) continue;
      for (let d = 0; d < 8; d++) {
        if (!(e & (1 << d))) continue;
        const nnode = ((j + DZ[d]) * w + (i + DX[d])) * K + ((el >> (d * 2)) & 3);
        if (blocked[nnode]) continue;
        const cost = (d >= 4 ? 1.414 : 1) * (1 + near[nnode] * 0.6);
        const nd = d0 + cost;
        if (nd < dist[nnode]) { dist[nnode] = nd; heap.push(nnode, nd); }
      }
    }
  }

  /**
   * Steering direction (unit XZ) toward the flow target, or null if lost.
   * `direction(x, y, z, out)` (legacy: `direction(x, z, out)`).
   */
  direction(x, y, z, out) {
    if (out === undefined) { out = z; z = y; y = -Infinity; }
    let node = this.index(x, y, z);
    if (node < 0 || !isFinite(this.dist[node])) {
      node = this._search(x, y, z, 3, true);
      if (node < 0) return null;
      out.set(this.cx(node) - x, 0, this.cz(node) - z);
      if (out.lengthSq() < 1e-4) return null;
      return out.normalize();
    }
    let best = -1, bd = this.dist[node];
    const e = this.edges[node], el = this.edgeLayer[node];
    const ci = (node / K) | 0;
    const i = ci % this.w, j = (ci - i) / this.w;
    for (let d = 0; d < 8; d++) {
      if (!(e & (1 << d))) continue;
      const nnode = ((j + DZ[d]) * this.w + (i + DX[d])) * K + ((el >> (d * 2)) & 3);
      if (this.dist[nnode] < bd) { bd = this.dist[nnode]; best = nnode; }
    }
    if (best < 0) return null;   // at the target node
    out.set(this.cx(best) - x, 0, this.cz(best) - z);
    if (out.lengthSq() < 1e-6) return null;
    return out.normalize();
  }

  /** Flow-field distance at a point. `distanceAt(x, y, z)` (legacy: `distanceAt(x, z)`). */
  distanceAt(x, y, z) {
    const node = this.index(x, y, z);
    return node < 0 ? Infinity : this.dist[node];
  }

  /**
   * Height of the surface an agent at (x, y, z) is standing on, NaN if none.
   * Never returns a floor from another storey: the layer closest to y wins and surfaces
   * above the agent are weighted 3x, so a zombie downstairs is never snapped upstairs.
   */
  heightAt(x, y, z) {
    const node = this.index(x, y, z);
    return node < 0 ? NaN : this.height[node];
  }

  /**
   * Straight walkable line between two points (DDA over cells), following the layer the
   * edges lead to — so it is false between a point downstairs and a point upstairs.
   * `lineClear(ax, ay, az, bx, by, bz)` (legacy: `lineClear(ax, az, bx, bz)`).
   */
  lineClear(ax, ay, az, bx, by, bz) {
    if (by === undefined) { bz = bx; bx = az; az = ay; ay = -Infinity; by = -Infinity; }
    let node = this.index(ax, ay, az);
    if (!this.walkable(node)) return false;
    const end = this.index(bx, by, bz);
    if (!this.walkable(end)) return false;
    const dx = bx - ax, dz = bz - az;
    const len = Math.hypot(dx, dz);
    const steps = Math.ceil(len / (this.cell * 0.5));
    let prev = (node / K) | 0;
    for (let s = 1; s <= steps; s++) {
      const t = s / steps;
      const ci = this.cellIndex(ax + dx * t, az + dz * t);
      if (ci < 0) return false;
      if (ci === prev) continue;
      const pi = prev % this.w, pj = (prev - pi) / this.w;
      const ni = ci % this.w, nj = (ci - ni) / this.w;
      const di = ni - pi, dj = nj - pj;
      let d = -1;
      for (let k = 0; k < 8; k++) if (DX[k] === di && DZ[k] === dj) { d = k; break; }
      if (d < 0 || !(this.edges[node] & (1 << d))) return false;
      node = this._step(node, d);
      if (!this.walkable(node)) return false;
      prev = ci;
    }
    return node === end;
  }
}
