// Inspect a .glb without Blender: node tree, meshes, skins, animations, materials, triangle counts.
// Usage: node tools/inspect-glb.mjs public/models/zombie.glb [--tree]
import fs from 'node:fs';

const file = process.argv[2];
const showTree = process.argv.includes('--tree');
if (!file) { console.error('usage: node tools/inspect-glb.mjs <file.glb> [--tree]'); process.exit(1); }
const buf = fs.readFileSync(file);
if (buf.readUInt32LE(0) !== 0x46546c67) throw new Error('not a GLB');
const jsonLen = buf.readUInt32LE(12);
const gltf = JSON.parse(buf.subarray(20, 20 + jsonLen).toString('utf8'));

const nodes = gltf.nodes || [];
const meshes = gltf.meshes || [];
const accessors = gltf.accessors || [];
let totalTris = 0;
const meshTris = meshes.map(m => m.primitives.reduce((s, p) => {
  const n = p.indices !== undefined ? accessors[p.indices].count : accessors[p.attributes.POSITION].count;
  return s + n / 3;
}, 0));

console.log(`file: ${file}  (${(buf.length / 1048576).toFixed(2)} MB)`);
console.log(`nodes: ${nodes.length}  meshes: ${meshes.length}  materials: ${(gltf.materials || []).length}  images: ${(gltf.images || []).length}  skins: ${(gltf.skins || []).length}`);

const childOf = new Set(nodes.flatMap(n => n.children || []));
const roots = (gltf.scenes?.[gltf.scene ?? 0]?.nodes) ?? nodes.map((_, i) => i).filter(i => !childOf.has(i));
function walk(i, depth) {
  const n = nodes[i];
  let tris = 0;
  if (n.mesh !== undefined) { tris = meshTris[n.mesh]; totalTris += tris; }
  if (showTree) {
    const t = n.translation ? ` t=[${n.translation.map(v => v.toFixed(2)).join(',')}]` : '';
    const kind = n.mesh !== undefined ? ` mesh(${Math.round(tris)} tris${n.skin !== undefined ? ', skinned' : ''})` : (n.camera !== undefined ? ' camera' : '');
    const ex = n.extras ? ` extras=${JSON.stringify(n.extras)}` : '';
    console.log(`${'  '.repeat(depth)}${n.name ?? '(unnamed)'}${kind}${t}${ex}`);
  }
  (n.children || []).forEach(c => walk(c, depth + 1));
}
roots.forEach(r => walk(r, 0));
console.log(`triangles (instanced in scene): ${Math.round(totalTris)}`);

const named = nodes.map(n => n.name || '');
const prefixes = {};
for (const nm of named) { const p = nm.split('_')[0]; if (['MK', 'COL', 'ZONE', 'DOOR'].includes(p)) (prefixes[p] ||= []).push(nm); }
for (const [p, list] of Object.entries(prefixes)) console.log(`${p}_ (${list.length}): ${list.join(', ')}`);

for (const a of gltf.animations || []) {
  const inputs = a.samplers.map(s => accessors[s.input]);
  const dur = Math.max(...inputs.map(x => (x.max ? x.max[0] : 0)));
  console.log(`animation "${a.name}": ${a.channels.length} channels, ${dur.toFixed(2)}s`);
}
if (gltf.skins) for (const s of gltf.skins) console.log(`skin joints (${s.joints.length}): ${s.joints.map(j => nodes[j].name).join(', ')}`);
if (gltf.materials) console.log('materials: ' + gltf.materials.map(m => m.name).join(', '));
