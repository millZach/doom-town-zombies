/**
 * Smoke test for the *real* map GLB.  `node tools/tests/nav_realmap.test.mjs`
 *
 * Loads public/models/map_doomtown.glb headlessly, builds the nav grid exactly the way
 * game.js does, and checks the things that would break gameplay: every zone box is found,
 * the grid builds inside budget, a flow update stays under 3 ms, and a fake zombie walked
 * from every spawn marker actually reaches the player start.
 *
 * It is written to keep working as the map grows an upstairs: it reports stacked cells and
 * per-zone node counts rather than asserting exact numbers.
 */
import fs from 'node:fs';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { GameMap } from '../../src/world/map.js';
import { NavGrid } from '../../src/world/nav.js';

const GLB = new URL('../../public/models/map_doomtown.glb', import.meta.url);
if (!fs.existsSync(GLB)) {
  console.log('skipped: public/models/map_doomtown.glb is not present');
  process.exit(0);
}

let passed = 0, failed = 0;
const log = console.log;
console.log = () => {};
function test(name, fn) {
  try { fn(); passed++; log(`  ok   ${name}`); }
  catch (e) { failed++; log(`  FAIL ${name}\n       ${e.message}`); }
}
function assert(cond, msg) { if (!cond) throw new Error(msg || 'assertion failed'); }

/**
 * Strip images/textures out of a GLB before parsing: three's GLTFLoader decodes them through
 * the DOM (`self.URL.createObjectURL`, `<img>`), which does not exist in node. Nothing here
 * needs materials — only the collision meshes, the ZONE_ boxes and the MK_ markers.
 */
function stripTextures(bytes) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const total = dv.getUint32(8, true);
  let off = 12, jsonChunk = null, rest = [];
  while (off < total) {
    const len = dv.getUint32(off, true), type = dv.getUint32(off + 4, true);
    const data = new Uint8Array(bytes.buffer, bytes.byteOffset + off + 8, len);
    if (type === 0x4e4f534a && !jsonChunk) jsonChunk = data; else rest.push({ type, data });
    off += 8 + len + ((4 - (len % 4)) % 4) * 0;   // chunk lengths are already 4-byte aligned
  }
  const json = JSON.parse(new TextDecoder().decode(jsonChunk));
  const scrub = o => {
    if (!o || typeof o !== 'object') return;
    for (const k of Object.keys(o)) {
      if (/texture$/i.test(k) || k === 'extensions') delete o[k];
      else scrub(o[k]);
    }
  };
  for (const m of json.materials || []) scrub(m);
  delete json.textures; delete json.images; delete json.samplers;
  if (json.extensionsUsed) json.extensionsUsed = json.extensionsUsed.filter(e => !/texture|basis|webp/i.test(e));
  let jsonBytes = new TextEncoder().encode(JSON.stringify(json));
  const pad = (4 - (jsonBytes.length % 4)) % 4;
  if (pad) { const t = new Uint8Array(jsonBytes.length + pad); t.set(jsonBytes); t.fill(0x20, jsonBytes.length); jsonBytes = t; }
  let size = 12 + 8 + jsonBytes.length;
  for (const c of rest) size += 8 + c.data.length;
  const out = new Uint8Array(size);
  const ov = new DataView(out.buffer);
  ov.setUint32(0, 0x46546c67, true); ov.setUint32(4, 2, true); ov.setUint32(8, size, true);
  let w = 12;
  ov.setUint32(w, jsonBytes.length, true); ov.setUint32(w + 4, 0x4e4f534a, true);
  out.set(jsonBytes, w + 8); w += 8 + jsonBytes.length;
  for (const c of rest) {
    ov.setUint32(w, c.data.length, true); ov.setUint32(w + 4, c.type, true);
    out.set(c.data, w + 8); w += 8 + c.data.length;
  }
  return out.buffer;
}

const buf = fs.readFileSync(GLB);
const gltf = await new Promise((res, rej) => new GLTFLoader().parse(stripTextures(buf), '', res, rej));

const map = new GameMap(gltf.scene);
const nav = new NavGrid(map.collision, map.zones);
const t0 = performance.now();
nav.build();
const buildMs = performance.now() - t0;

// exactly the seed list game.js uses
const seeds = [];
for (const [name, mk] of map.markers) {
  if (/^MK_(PLAYER_START|SPAWN_GROUND|DOOR|BOX|PERK|PAP|POWER|WALLBUY)/.test(name))
    seeds.push(mk.pos.clone().addScaledVector(mk.forward, name.startsWith('MK_WALLBUY') || name.startsWith('MK_POWER') ? 0.8 : 0));
  if (name.startsWith('MK_BARRIER_')) seeds.push(mk.pos.clone().addScaledVector(mk.forward, 1.0));
}
nav.pruneIslands(seeds);

const nodes = [];
for (let n = 0; n < nav.height.length; n++) if (nav.walkable(n)) nodes.push(n);
let stacked = 0;
for (let ci = 0; ci < nav.cells; ci++) if (nav.layers[ci] > 1) stacked++;

const flow = [];
for (let i = -3; i < 20; i++) {
  const n = nodes[Math.floor(Math.abs(i) * nodes.length / 20) % nodes.length];
  nav.target = -1;
  const s = performance.now();
  nav.updateFlow(nav.cx(n), nav.height[n], nav.cz(n));
  if (i >= 0) flow.push(performance.now() - s);
}

const start = map.marker('MK_PLAYER_START');
nav.target = -1;
nav.updateFlow(start.pos.x, start.pos.y, start.pos.z);

// steer a fake zombie from every spawn marker to the player start
const dir = new THREE.Vector3();
const stuck = [];
let tried = 0;
for (const [name, m] of map.markers) {
  if (!/^MK_(SPAWN_GROUND|BARRIER)/.test(name)) continue;
  tried++;
  let x = m.pos.x, y = m.pos.y, z = m.pos.z;
  const h0 = nav.heightAt(x, y, z);
  if (!isNaN(h0)) y = h0;
  let ok = false;
  for (let i = 0; i < 2000; i++) {
    const d = nav.direction(x, y, z, dir);
    if (!d) { ok = true; break; }
    x += d.x * 0.12; z += d.z * 0.12;
    const h = nav.heightAt(x, y, z);
    if (!isNaN(h) && Math.abs(h - y) < 0.8) y += (h - y) * 0.5;
  }
  if (!ok) stuck.push(name);
}

log(`\nreal map: ${map.zones.length} zones, ${map.markers.size} markers`);
log(`  ${map.zones.map(z => `${z.id}[${z.box.min.y.toFixed(1)}..${z.box.max.y.toFixed(1)}]`).join(' ')}`);
log('');
test('every zone box has a name and some height', () => {
  for (const z of map.zones) assert(z.id && z.box.max.y > z.box.min.y, `bad zone ${z.id}`);
});
test(`nav builds in under 1500 ms (${nav.w}x${nav.h}, ${buildMs.toFixed(0)} ms)`, () => {
  assert(buildMs < 1500, `took ${buildMs.toFixed(0)} ms`);
});
test(`plenty of walkable nodes survive pruning (${nodes.length})`, () => {
  assert(nodes.length > 1000, `only ${nodes.length} nodes`);
});
test(`flow update under 3 ms (avg ${(flow.reduce((a, b) => a + b, 0) / flow.length).toFixed(2)}, max ${Math.max(...flow).toFixed(2)})`, () => {
  assert(Math.max(...flow) < 3, `max ${Math.max(...flow).toFixed(2)} ms`);
});
test('the player start is on walkable floor', () => {
  const h = nav.heightAt(start.pos.x, start.pos.y, start.pos.z);
  assert(!isNaN(h), 'no nav node under MK_PLAYER_START');
  assert(Math.abs(h - start.pos.y) < 1.0, `marker y ${start.pos.y.toFixed(2)} vs nav ${h.toFixed(2)}`);
  assert(map.zoneAt(start.pos), 'MK_PLAYER_START is not inside any zone box');
});
test('every spawn marker sits in a zone', () => {
  const bad = [];
  for (const [name, m] of map.markers) {
    if (!/^MK_(SPAWN_GROUND|BARRIER)/.test(name)) continue;
    if (!map.zoneAt(m.pos)) bad.push(name);
  }
  assert(!bad.length, `no zone for ${bad.join(', ')}`);
});
test(`every spawn reaches the player (${tried - stuck.length}/${tried})`, () => {
  assert(!stuck.length, `stuck: ${stuck.join(', ')}`);
});

// ---------------------------------------------------------------- all doors open
// game.js builds the grid with every door still closed and reopens regions as they are
// bought. With them all open every gameplay marker has to be reachable from every spawn.
for (const d of map.collision.dynamic) if (d.kind === 'door') d.enabled = false;
const navOpen = new NavGrid(map.collision, map.zones);
const t1 = performance.now();
navOpen.build();
const openBuildMs = performance.now() - t1;
navOpen.pruneIslands(seeds);

const spawns = [...map.markers].filter(([n]) => /^MK_(SPAWN_GROUND|BARRIER)/.test(n));
const goals = [...map.markers].filter(([n]) => /^MK_(PERK|BOX|PAP|POWER|PLAYER_START)/.test(n));
const unreachable = [];
for (const [gname, gm] of goals) {
  navOpen.target = -1;
  navOpen.updateFlow(gm.pos.x, gm.pos.y, gm.pos.z);
  if (navOpen.target < 0) { unreachable.push(`${gname} (no nav node)`); continue; }
  for (const [sname, sm] of spawns) {
    let x = sm.pos.x, y = sm.pos.y, z = sm.pos.z;
    const h0 = navOpen.heightAt(x, y, z);
    if (!isNaN(h0)) y = h0;
    let ok = false;
    for (let i = 0; i < 3000; i++) {
      const d = navOpen.direction(x, y, z, dir);
      if (!d) { ok = true; break; }
      x += d.x * 0.12; z += d.z * 0.12;
      const h = navOpen.heightAt(x, y, z);
      if (!isNaN(h) && Math.abs(h - y) < 0.8) y += (h - y) * 0.5;
    }
    if (!ok) unreachable.push(`${sname} -> ${gname}`);
  }
}
let openNodes = 0, openStacked = 0;
for (let n = 0; n < navOpen.height.length; n++) if (navOpen.walkable(n)) openNodes++;
for (let ci = 0; ci < navOpen.cells; ci++) if (navOpen.layers[ci] > 1) openStacked++;

test(`with every door open, all ${spawns.length} spawns reach all ${goals.length} gameplay markers`, () => {
  assert(!unreachable.length, `${unreachable.length} failures, e.g. ${unreachable.slice(0, 6).join('; ')}`);
});
test('opening the doors only ever adds nodes', () => {
  assert(openNodes >= nodes.length, `${openNodes} with doors open vs ${nodes.length} closed`);
});

console.log = log;
log(`\n  grid ${nav.w}x${nav.h}, ${nodes.length} walkable nodes, ${stacked} stacked cells, build ${buildMs.toFixed(0)} ms`);
log(`  doors open:  ${openNodes} walkable nodes, ${openStacked} stacked cells, build ${openBuildMs.toFixed(0)} ms`);
log(`\n${passed} passed, ${failed} failed\n`);
process.exit(failed ? 1 : 0);
