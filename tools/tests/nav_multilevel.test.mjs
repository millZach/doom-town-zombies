/**
 * Multi-level navigation tests.  `node tools/tests/nav_multilevel.test.mjs`
 *
 * The map GLB does not have the upstairs yet, so everything here runs against a synthetic
 * two-storey scene built from plain three.js boxes:
 *
 *      y=2.9  ┌──── upper floor ────┐ · · · · ·        (x from -8 to 0)
 *             │  far  │ door │ near │      ╱ 30° ramp  (x from 0 to 5, z from 1 to 3)
 *      y=0    └─────── ground floor ──────────────┘    (x from -8 to 8)
 *
 * plus a solid table under the upper floor (too low to stand on *or* under) and a dynamic
 * "door" collider that seals the far upstairs room until it is opened.
 */
import * as THREE from 'three';
import { Collision } from '../../src/world/collision.js';
import { NavGrid } from '../../src/world/nav.js';

// ------------------------------------------------------------------ tiny test runner
let passed = 0, failed = 0;
const quiet = !process.argv.includes('--verbose');
const log = console.log;
if (quiet) console.log = () => {};          // nav.js is chatty; keep the report readable
function test(name, fn) {
  try { fn(); passed++; log(`  ok   ${name}`); }
  catch (e) { failed++; log(`  FAIL ${name}\n       ${e.message}`); }
}
function assert(cond, msg) { if (!cond) throw new Error(msg || 'assertion failed'); }
function near(a, b, eps, msg) { if (!(Math.abs(a - b) <= eps)) throw new Error(`${msg || ''} expected ${b} ±${eps}, got ${a}`); }

// ------------------------------------------------------------------ scene helpers
function box(sx, sy, sz, x, y, z, rotZ = 0) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz));
  m.position.set(x, y, z);
  if (rotZ) m.rotation.z = rotZ;
  return m;
}
/** Slab spanning [x0,x1] x [z0,z1] whose *top* face is at `top`, `t` thick. */
function slab(x0, x1, z0, z1, top, t = 0.3) {
  return box(x1 - x0, t, z1 - z0, (x0 + x1) / 2, top - t / 2, (z0 + z1) / 2);
}
/** Wall spanning [x0,x1] x [z0,z1] from y0 to y1. */
function wall(x0, x1, z0, z1, y0, y1) {
  return box(Math.max(x1 - x0, 0.3), y1 - y0, Math.max(z1 - z0, 0.3), (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
}

const RAMP_DEG = 30;
const FLOOR_Y = 2.9;
/** A `deg` ramp whose top surface runs from (xBot, 0) up to (xTop, top). */
function ramp(xBot, top, deg, z0, z1) {
  const run = top / Math.tan(deg * Math.PI / 180);
  const xTop = xBot - run;
  const len = Math.hypot(run, top);
  const m = box(len, 0.06, z1 - z0, (xBot + xTop) / 2, top / 2, (z0 + z1) / 2, -deg * Math.PI / 180);
  return m;
}

function buildScene() {
  const g = new THREE.Group();
  const stat = [];
  const add = m => { g.add(m); stat.push(m); return m; };

  add(slab(-8, 8, -8, 8, 0));                      // ground floor
  add(slab(-8, 0, -8, 8, FLOOR_Y));                // upper floor over the west half
  for (const w of [[-8.3, -8, -8.3, 8.3], [8, 8.3, -8.3, 8.3], [-8, 8, -8.3, -8], [-8, 8, 8, 8.3]])
    add(wall(w[0], w[1], w[2], w[3], 0, 7));       // outer walls
  add(ramp(5.02, FLOOR_Y, RAMP_DEG, 1, 3));        // 30 degree ramp up to the upper floor
  // interior wall on the upper floor with a doorway at z in [-1, 1]
  add(wall(-4.15, -3.85, -8, -1, FLOOR_Y, FLOOR_Y + 2.6));
  add(wall(-4.15, -3.85, 1, 8, FLOOR_Y, FLOOR_Y + 2.6));
  // a solid 1.1 m table under the upper floor: no headroom on top (1.5 m) and none under it
  add(box(1.4, 1.1, 1.4, -4, 0.55, 4));
  // a 2x2 m platform 1.2 m up in the open half: walkable in itself, connected to nothing
  add(box(2, 1.2, 2, 6, 0.6, -6));

  const doorMesh = wall(-4.15, -3.85, -1, 1, FLOOR_Y, FLOOR_Y + 2.0);
  g.add(doorMesh);
  g.updateMatrixWorld(true);

  const col = new Collision();
  col.setStatic(stat);
  const door = col.addDynamic('test_door', 'door', [doorMesh]);

  const zones = [
    { id: 'ground', box: new THREE.Box3(new THREE.Vector3(-8, -0.5, -8), new THREE.Vector3(8, 2.9, 8)) },
    { id: 'upper', box: new THREE.Box3(new THREE.Vector3(-8, 2.9, -8), new THREE.Vector3(0, 6.5, 8)) },
    { id: 'openspace', box: new THREE.Box3(new THREE.Vector3(0, -0.5, -8), new THREE.Vector3(8, 6.5, 8)) },
  ];
  return { col, zones, door };
}

// ------------------------------------------------------------------ the scene
log('\nsynthetic two-storey scene');
const { col, zones, door } = buildScene();
const nav = new NavGrid(col, zones);
const tBuild0 = performance.now();
nav.build();
const buildMs = performance.now() - tBuild0;

const SEEDS = [
  new THREE.Vector3(6, 0, 6),          // ground floor, open half
  new THREE.Vector3(-2, FLOOR_Y, 0),   // upstairs, near room
  new THREE.Vector3(-6, FLOOR_Y, 0),   // upstairs, far room (behind the door)
];
nav.pruneIslands(SEEDS);

const K = nav.K;
const cellLayers = (x, z) => {
  const ci = nav.cellIndex(x, z);
  const out = [];
  for (let l = 0; l < nav.layers[ci]; l++) if (!isNaN(nav.height[ci * K + l])) out.push(nav.height[ci * K + l]);
  return out;
};

// ------------------------------------------------------------------ 1. layers
log('\nlayer discovery');
test('two layers under the upper floor', () => {
  const ls = cellLayers(-2.25, 0.25);
  assert(ls.length === 2, `expected 2 layers at (-2.25, 0.25), got ${ls.length} [${ls}]`);
  near(ls[0], 0, 0.02, 'lower layer');
  near(ls[1], FLOOR_Y, 0.02, 'upper layer');
});
test('one layer where nothing is stacked', () => {
  const ls = cellLayers(6.25, 6.25);
  assert(ls.length === 1, `expected 1 layer at (6.25, 6.25), got [${ls}]`);
  near(ls[0], 0, 0.02, 'ground');
});
test('layers are stored bottom-up', () => {
  let stacked = 0;
  for (let ci = 0; ci < nav.cells; ci++) {
    if (nav.layers[ci] < 2) continue;
    stacked++;
    for (let l = 1; l < nav.layers[ci]; l++) {
      const a = nav.height[ci * K + l - 1], b = nav.height[ci * K + l];
      assert(isNaN(a) || isNaN(b) || b > a, 'layer heights must ascend');
    }
  }
  assert(stacked > 100, `expected a lot of stacked cells, got ${stacked}`);
});
test('a 1.1 m table with 1.5 m headroom is not walkable, and neither is under it', () => {
  const ls = cellLayers(-4.25, 4.25);   // only the upper floor overhead, nothing at 1.1 or 0
  assert(!ls.some(h => h < 2), `table cell should have no low node, got [${ls}]`);
  assert(ls.length === 1 && Math.abs(ls[0] - FLOOR_Y) < 0.02, `expected just the upper floor, got [${ls}]`);
  assert(cellLayers(-6.25, 4.25).length === 2, 'the floor beside the table is still fine');
});
test('the ramp underside is not a node, and the ground under its low end is not either', () => {
  // under the low half of the ramp there is less than 1.7 m of headroom
  const low = cellLayers(4.25, 2.25);
  assert(low.length === 1, `expected only the ramp surface at (4.25, 2.25), got [${low}]`);
  assert(low[0] > 0.3, `that surface should be the ramp, got ${low[0]}`);
});
test('the ramp is a continuous run of nodes from ground to upper floor', () => {
  for (let x = 0.25; x < 5; x += 0.5) {
    const ls = cellLayers(x, 2.25);
    const wanted = (5.02 - x) / 5.02 * FLOOR_Y;
    assert(ls.some(h => Math.abs(h - wanted) < 0.25), `no ramp node at x=${x} (wanted ~${wanted.toFixed(2)}, got [${ls}])`);
  }
});

// ------------------------------------------------------------------ 2. per-layer queries
log('\nlayer-aware queries');
test('heightAt never snaps across floors', () => {
  near(nav.heightAt(-2.25, 0.0, 0.25), 0, 0.02, 'agent downstairs');
  near(nav.heightAt(-2.25, 0.3, 0.25), 0, 0.02, 'agent hopping downstairs');
  near(nav.heightAt(-2.25, FLOOR_Y, 0.25), FLOOR_Y, 0.02, 'agent upstairs');
  near(nav.heightAt(-2.25, FLOOR_Y + 0.4, 0.25), FLOOR_Y, 0.02, 'agent jumping upstairs');
  // halfway up a ladderless gap the nearer floor still wins, never the far one
  near(nav.heightAt(-2.25, 1.0, 0.25), 0, 0.02, 'below the midpoint -> ground floor');
});
test('index/nodeAt pick different nodes for the two storeys', () => {
  const a = nav.index(-2.25, 0, 0.25), b = nav.index(-2.25, FLOOR_Y, 0.25);
  assert(a >= 0 && b >= 0 && a !== b, 'expected two distinct nodes in one cell');
  assert(nav.cellOf(a) === nav.cellOf(b), 'same cell');
  assert(nav.layerOf(a) === 0 && nav.layerOf(b) === 1, 'ground is layer 0');
});
test('legacy 2-arg signatures still resolve to the lowest layer', () => {
  near(nav.heightAt(-2.25, 0.25), 0, 0.02, 'legacy heightAt');
  assert(nav.index(-2.25, 0.25) === nav.index(-2.25, 0, 0.25), 'legacy index');
});
test('no edge from the upper floor down to the ground floor', () => {
  const up = nav.index(-0.25, FLOOR_Y, 5.25);          // upper floor edge, away from the ramp
  assert(up >= 0, 'expected an upper-floor node');
  for (let d = 0; d < 8; d++) {
    if (!(nav.edges[up] & (1 << d))) continue;
    near(nav.height[nav._step(up, d)], FLOOR_Y, 0.5, `edge ${d} leaves the storey:`);
  }
});

// ------------------------------------------------------------------ 3. flow field across storeys
log('\nflow field');
const flowTimes = [];
function flowTo(x, y, z) {
  nav.target = -1;
  const t0 = performance.now();
  nav.updateFlow(x, y, z);
  flowTimes.push(performance.now() - t0);
}

/** Walk a fake zombie along the flow field. Returns its track. */
function walk(x, y, z, steps = 900, step = 0.12) {
  const dir = new THREE.Vector3();
  const track = { maxY: y, minY: y, x, y, z, ok: false, n: 0 };
  for (let i = 0; i < steps; i++) {
    track.n = i;
    const d = nav.direction(x, y, z, dir);
    if (!d) { track.ok = true; break; }               // standing on the target node
    x += d.x * step; z += d.z * step;
    const h = nav.heightAt(x, y, z);
    if (!isNaN(h) && Math.abs(h - y) < 0.8) y += (h - y) * 0.5;   // the same snap zombies.js does
    track.maxY = Math.max(track.maxY, y); track.minY = Math.min(track.minY, y);
    track.x = x; track.y = y; track.z = z;
  }
  return track;
}

test('a ground-floor agent walks to the ramp and up to an upstairs target', () => {
  flowTo(-2.25, FLOOR_Y, 0.25);
  const t = walk(6.25, 0, 6.25);
  assert(t.ok, `agent never reached the target (stopped at ${t.x.toFixed(1)},${t.y.toFixed(1)},${t.z.toFixed(1)})`);
  near(t.y, FLOOR_Y, 0.2, 'finished upstairs:');
  assert(Math.hypot(t.x - (-2.25), t.z - 0.25) < 1.0, `finished at ${t.x.toFixed(2)}, ${t.z.toFixed(2)}`);
  assert(t.minY < 0.1, 'should have started on the ground floor');
});
test('an upstairs agent walks back down to a ground-floor target', () => {
  flowTo(6.25, 0, 6.25);
  const t = walk(-2.25, FLOOR_Y, -4.25);   // near room: the far one is still sealed here
  assert(t.ok, `agent never came back down (stopped at ${t.x.toFixed(1)},${t.y.toFixed(1)},${t.z.toFixed(1)})`);
  near(t.y, 0, 0.2, 'finished downstairs:');
  assert(t.maxY > 2.5, 'should have started upstairs');
});
test('the flow field distinguishes the two layers of one cell', () => {
  flowTo(-2.25, FLOOR_Y, 0.25);
  const dUp = nav.distanceAt(6.25, 0, 6.25);
  const dDown = nav.distanceAt(-2.25, 0, 0.25);
  assert(isFinite(dUp) && isFinite(dDown), 'both should be reachable');
  assert(nav.distanceAt(-2.25, FLOOR_Y, 0.25) === 0, 'the target node itself is at distance 0');
  assert(dDown > 20, `standing right under the target is a long walk (got ${dDown.toFixed(1)})`);
});
test('lineClear is false between floors and true along one', () => {
  assert(!nav.lineClear(-2.25, 0, 0.25, -2.25, FLOOR_Y, 0.25), 'straight up through a floor');
  assert(!nav.lineClear(-2.25, 0, 0.25, -5.25, FLOOR_Y, 0.25), 'diagonally up through a floor');
  assert(nav.lineClear(-2.25, 0, 0.25, -6.25, 0, -2.25), 'clear run on the ground floor');
  assert(nav.lineClear(-2.25, FLOOR_Y, 0.25, -2.25, FLOOR_Y, 5.25), 'clear run upstairs');
  assert(!nav.lineClear(-2.25, FLOOR_Y, 0.25, -6.25, FLOOR_Y, 5.25), 'through the closed door');
});

// ------------------------------------------------------------------ 4. doors
log('\ndoors (rebuildRegion)');
test('a closed door seals the far upstairs room', () => {
  flowTo(6.25, 0, 6.25);
  assert(!isFinite(nav.distanceAt(-6.25, FLOOR_Y, 0.25)), 'far room should be unreachable');
  assert(isFinite(nav.distanceAt(-2.25, FLOOR_Y, 0.25)), 'near room should be reachable');
});
test('opening it reconnects the room through rebuildRegion', () => {
  col.setEnabled('test_door', false);
  nav.rebuildRegion(door.box);
  flowTo(6.25, 0, 6.25);
  assert(isFinite(nav.distanceAt(-6.25, FLOOR_Y, 0.25)), 'far room should now be reachable');
  assert(nav.lineClear(-4.75, FLOOR_Y, 0.25, -3.25, FLOOR_Y, 0.25), 'the doorway is walkable');
});
test('a zombie now walks through the doorway into the far room', () => {
  flowTo(-6.25, FLOOR_Y, 0.25);
  const t = walk(6.25, 0, 6.25);
  assert(t.ok, `never arrived (stopped at ${t.x.toFixed(1)},${t.y.toFixed(1)},${t.z.toFixed(1)})`);
  assert(Math.hypot(t.x - (-6.25), t.z - 0.25) < 1.0, `finished at ${t.x.toFixed(2)}, ${t.z.toFixed(2)}`);
});
test('closing it again seals the room', () => {
  col.setEnabled('test_door', true);
  nav.rebuildRegion(door.box);
  flowTo(6.25, 0, 6.25);
  assert(!isFinite(nav.distanceAt(-6.25, FLOOR_Y, 0.25)), 'far room should be sealed again');
  assert(isFinite(nav.distanceAt(-2.25, FLOOR_Y, 0.25)), 'near room still reachable');
  col.setEnabled('test_door', false);
  nav.rebuildRegion(door.box);
});

// ------------------------------------------------------------------ 5. pruning
log('\nisland pruning');
test('the unreachable 1.2 m platform is pruned', () => {
  assert(cellLayers(6.25, -6.25).some(h => Math.abs(h - 1.2) < 0.05), 'the platform surface was found');
  assert(nav.index(6.25, 1.2, -6.25) < 0, 'but no node is handed out for it');
  assert(!isFinite(nav.distanceAt(6.25, 1.2, -6.25)), 'and it is not in the flow field');
});
test('prune is non-destructive: re-seeding hands the island back', () => {
  nav.pruneIslands([...SEEDS, new THREE.Vector3(6, 1.2, -6)]);
  const n = nav.index(6.25, 1.2, -6.25);
  assert(nav.walkable(n), 'the platform is walkable once it is seeded');
  near(nav.height[n], 1.2, 0.05, 'platform height');
  nav.pruneIslands(SEEDS);
  assert(nav.index(6.25, 1.2, -6.25) < 0, 'and pruned again');
  assert(nav.walkable(nav.index(6.25, 0, 6.25)), 'ground floor still fine');
  assert(nav.walkable(nav.index(-6.25, FLOOR_Y, 0.25)), 'far upstairs room still fine');
});

// ------------------------------------------------------------------ 6. map.zoneAt
log('\nmap.zoneAt with stacked zone boxes');
{
  const { GameMap } = await import('../../src/world/map.js');
  const fake = Object.create(GameMap.prototype);
  fake.zones = [
    { id: 'street', box: new THREE.Box3(new THREE.Vector3(-40, 0, -40), new THREE.Vector3(40, 9, 40)) },
    { id: 'yellow', box: new THREE.Box3(new THREE.Vector3(-8, 0, -8), new THREE.Vector3(0, 2.9, 8)) },
    { id: 'yellowup', box: new THREE.Box3(new THREE.Vector3(-8, 2.9, -8), new THREE.Vector3(0, 5.6, 8)) },
    { id: 'yardw', box: new THREE.Box3(new THREE.Vector3(-20, 0, -8), new THREE.Vector3(-8, 4, 8)) },
  ];
  const at = (x, y, z) => fake.zoneAt(new THREE.Vector3(x, y, z));
  test('ground floor of the house', () => assert(at(-4, 0, 0) === 'yellow', `got ${at(-4, 0, 0)}`));
  test('upstairs of the house', () => assert(at(-4, 2.95, 0) === 'yellowup', `got ${at(-4, 2.95, 0)}`));
  test('standing exactly on the upstairs floor', () => assert(at(-4, 2.9, 0) === 'yellowup', `got ${at(-4, 2.9, 0)}`));
  test('head height on the ground floor is still the ground floor', () => assert(at(-4, 1.7, 0) === 'yellow', `got ${at(-4, 1.7, 0)}`));
  test('the street outside', () => assert(at(20, 0, 0) === 'street', `got ${at(20, 0, 0)}`));
  test('the back yard', () => assert(at(-12, 0, 0) === 'yardw', `got ${at(-12, 0, 0)}`));
  test('above the roof is nothing indoors', () => assert(at(-4, 7, 0) === 'street', `got ${at(-4, 7, 0)}`));
}

// ------------------------------------------------------------------ 7. performance at map scale
log('\nperformance');
function bigScene() {
  const g = new THREE.Group();
  const stat = [];
  const add = m => { g.add(m); stat.push(m); return m; };
  add(slab(-24, 24, -26, 26, 0));
  add(slab(-24, 0, -26, 26, FLOOR_Y));
  for (const w of [[-24.3, -24, -26.3, 26.3], [24, 24.3, -26.3, 26.3], [-24, 24, -26.3, -26], [-24, 24, 26, 26.3]])
    add(wall(w[0], w[1], w[2], w[3], 0, 7));
  add(ramp(5.02, FLOOR_Y, RAMP_DEG, 1, 3));
  // a deterministic grid of 2x2 m pillars with 4 m corridors between them: enough geometry to
  // make the BVH and the wall rays realistic without cutting the floor into islands
  for (let px = -21; px <= 21; px += 6) {
    for (let pz = -23; pz <= 23; pz += 6) {
      if (px > -2 && px < 7 && pz > -1 && pz < 5) continue;       // keep the ramp clear
      add(wall(px - 1, px + 1, pz - 1, pz + 1, 0, 2.6));
      if (px < -1) add(wall(px - 1, px + 1, pz - 1, pz + 1, FLOOR_Y, FLOOR_Y + 2.6));
    }
  }
  g.updateMatrixWorld(true);
  const c = new Collision();
  c.setStatic(stat);
  return {
    col: c,
    zones: [
      { id: 'g', box: new THREE.Box3(new THREE.Vector3(-24, -0.5, -26), new THREE.Vector3(24, 2.9, 26)) },
      { id: 'u', box: new THREE.Box3(new THREE.Vector3(-24, 2.9, -26), new THREE.Vector3(0, 6.5, 26)) },
      { id: 'o', box: new THREE.Box3(new THREE.Vector3(0, -0.5, -26), new THREE.Vector3(24, 6.5, 26)) },
    ],
  };
}
const big = bigScene();
const bigNav = new NavGrid(big.col, big.zones);
const t0 = performance.now();
bigNav.build();
const bigBuild = performance.now() - t0;
bigNav.pruneIslands([new THREE.Vector3(12, 0, 10), new THREE.Vector3(-12, FLOOR_Y, 10)]);

const bigFlow = [];
const bigWalkable = [];
for (let n = 0; n < bigNav.height.length; n++) if (bigNav.walkable(n)) bigWalkable.push(n);
for (let i = -4; i < 24; i++) {                     // the first few calls are JIT warm-up
  const n = bigWalkable[Math.floor(Math.abs(i) * bigWalkable.length / 24) % bigWalkable.length];
  bigNav.target = -1;
  const s0 = performance.now();
  bigNav.updateFlow(bigNav.cx(n), bigNav.height[n], bigNav.cz(n));
  if (i >= 0) bigFlow.push(performance.now() - s0);
}
let steerMs = 0, steerAlloc = 0;
const avg = a => a.reduce((x, y) => x + y, 0) / a.length;
const max = a => a.reduce((x, y) => Math.max(x, y), 0);

test(`big-grid build (${bigNav.w}x${bigNav.h}) under 1500 ms`, () => {
  assert(bigBuild < 1500, `took ${bigBuild.toFixed(0)} ms`);
});
test('flow update under 3 ms', () => {
  assert(max(bigFlow) < 3, `max ${max(bigFlow).toFixed(2)} ms, avg ${avg(bigFlow).toFixed(2)} ms`);
});
test('steering allocates nothing per call', () => {
  // sample real nodes so every call goes down the hot path, then run 24 zombies x 60 frames
  const pts = [];
  for (const n of bigWalkable) {
    if (pts.length >= 400) break;
    if (isFinite(bigNav.dist[n]) && bigNav.dist[n] > 0) pts.push([bigNav.cx(n), bigNav.height[n], bigNav.cz(n)]);
  }
  assert(pts.length > 200, `expected plenty of reachable nodes, got ${pts.length}`);
  const out = new THREE.Vector3();
  const steer = () => {
    let hits = 0;
    for (let i = 0; i < 24 * 60; i++) {
      const p = pts[i % pts.length];
      if (bigNav.direction(p[0], p[1], p[2], out)) hits++;
      bigNav.heightAt(p[0], p[1], p[2]);
      bigNav.distanceAt(p[0], p[1], p[2]);
    }
    return hits;
  };
  steer(); steer();                          // warm up
  global.gc?.();
  const before = process.memoryUsage().heapUsed;
  const t0 = performance.now();
  const hits = steer();
  const ms = performance.now() - t0;
  global.gc?.();
  const grew = (process.memoryUsage().heapUsed - before) / 1024;
  steerMs = ms / (24 * 60);
  steerAlloc = grew;
  assert(hits > 24 * 60 * 0.9, `expected nearly every sample to steer (got ${hits})`);
  // without --expose-gc this only catches gross leaks: uncollected young garbage counts too
  const budget = global.gc ? 32 : 1500;
  assert(grew < budget, `heap grew ${grew.toFixed(0)} KB over ${24 * 60} steering calls (budget ${budget} KB)`);
});

// ------------------------------------------------------------------ report
console.log = log;
let nodes = 0, stacked = 0;
for (let ci = 0; ci < nav.cells; ci++) { nodes += nav.layers[ci]; if (nav.layers[ci] > 1) stacked++; }
log(`\ntimings`);
log(`  small scene  ${nav.w}x${nav.h} cells, ${nodes} nodes, ${stacked} stacked cells, build ${buildMs.toFixed(0)} ms`);
log(`  big scene    ${bigNav.w}x${bigNav.h} cells, ${bigWalkable.length} walkable nodes, build ${bigBuild.toFixed(0)} ms`);
log(`  flow update  avg ${avg(bigFlow).toFixed(2)} ms, max ${max(bigFlow).toFixed(2)} ms over ${bigFlow.length} targets`);
log(`  small flow   avg ${avg(flowTimes).toFixed(2)} ms over ${flowTimes.length} targets`);
log(`  steering     ${(steerMs * 1000).toFixed(2)} us per agent per frame (24 zombies = ${(steerMs * 24).toFixed(3)} ms/frame)`);
log(`  steer alloc  ${steerAlloc.toFixed(0)} KB / ${24 * 60} calls${global.gc ? '' : '  (run with --expose-gc for an exact figure)'}`);
log(`\n${passed} passed, ${failed} failed\n`);
process.exit(failed ? 1 : 0);
