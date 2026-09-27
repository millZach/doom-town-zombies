import * as THREE from 'three';

// Grey-box stand-in for map_doomtown.glb using the same node naming contract
// (COL_*, ZONE_*, DOOR_*, MK_*). Coordinates are three.js (x east, z south, y up).
export function buildFallbackMap() {
  const root = new THREE.Group();
  root.name = 'fallback_map';
  const mats = {
    ground: new THREE.MeshStandardMaterial({ color: 0x5b5040, roughness: 0.95 }),
    road: new THREE.MeshStandardMaterial({ color: 0x2d2c2b, roughness: 0.9 }),
    yellow: new THREE.MeshStandardMaterial({ color: 0xb59a4a, roughness: 0.85 }),
    green: new THREE.MeshStandardMaterial({ color: 0x7ea58c, roughness: 0.85 }),
    wood: new THREE.MeshStandardMaterial({ color: 0x6b4a2e, roughness: 0.8 }),
    floor: new THREE.MeshStandardMaterial({ color: 0x5a3e28, roughness: 0.7 }),
    concrete: new THREE.MeshStandardMaterial({ color: 0x75726c, roughness: 0.95 }),
    fence: new THREE.MeshStandardMaterial({ color: 0x8c7b64, roughness: 0.9 }),
    metal: new THREE.MeshStandardMaterial({ color: 0x6d5434, roughness: 0.6, metalness: 0.6 }),
    bus: new THREE.MeshStandardMaterial({ color: 0x8a5a1a, roughness: 0.7, metalness: 0.3 }),
    door: new THREE.MeshStandardMaterial({ color: 0x4a2f1c, roughness: 0.7 }),
    col: new THREE.MeshBasicMaterial({ visible: false }),
  };
  const add = (o, name) => { o.name = name; o.userData.name = name; root.add(o); return o; };
  let n = 0;
  // visual + matching collider
  function solid(size, pos, mat, rotY = 0, colOnly = false) {
    const g = new THREE.BoxGeometry(...size);
    if (!colOnly) {
      const m = add(new THREE.Mesh(g, mat), `blk_${n}`);
      m.position.set(...pos); m.rotation.y = rotY;
    }
    const c = add(new THREE.Mesh(g, mats.col), `COL_blk_${n++}`);
    c.position.set(...pos); c.rotation.y = rotY;
  }
  function vis(size, pos, mat, rotY = 0) {
    const m = add(new THREE.Mesh(new THREE.BoxGeometry(...size), mat), `vis_${n++}`);
    m.position.set(...pos); m.rotation.y = rotY; return m;
  }
  // wall along Z at x (from z0 to z1), with openings [{a,b,bottom,top}] in z
  function wallZ(x, z0, z1, y0, h, mat, openings = [], t = 0.25) {
    let cur = z0;
    const ops = [...openings].sort((p, q) => p.a - q.a);
    for (const o of ops) {
      if (o.a > cur) solid([t, h, o.a - cur], [x, y0 + h / 2, (cur + o.a) / 2], mat);
      if (o.bottom > 0) solid([t, o.bottom, o.b - o.a], [x, y0 + o.bottom / 2, (o.a + o.b) / 2], mat);
      if (o.top < h) solid([t, h - o.top, o.b - o.a], [x, y0 + (o.top + h) / 2, (o.a + o.b) / 2], mat);
      cur = o.b;
    }
    if (z1 > cur) solid([t, h, z1 - cur], [x, y0 + h / 2, (cur + z1) / 2], mat);
  }
  function wallX(z, x0, x1, y0, h, mat, openings = [], t = 0.25) {
    let cur = x0;
    const ops = [...openings].sort((p, q) => p.a - q.a);
    for (const o of ops) {
      if (o.a > cur) solid([o.a - cur, h, t], [(cur + o.a) / 2, y0 + h / 2, z], mat);
      if (o.bottom > 0) solid([o.b - o.a, o.bottom, t], [(o.a + o.b) / 2, y0 + o.bottom / 2, z], mat);
      if (o.top < h) solid([o.b - o.a, h - o.top, t], [(o.a + o.b) / 2, y0 + (o.top + h) / 2, z], mat);
      cur = o.b;
    }
    if (x1 > cur) solid([x1 - cur, h, t], [(cur + x1) / 2, y0 + h / 2, z], mat);
  }
  function marker(name, pos, rotY = 0) {
    const o = add(new THREE.Object3D(), name);
    o.position.set(...pos); o.rotation.y = rotY;
    return o;
  }
  function zone(id, min, max, k = 0) {
    const size = [max[0] - min[0], max[1] - min[1], max[2] - min[2]];
    const m = add(new THREE.Mesh(new THREE.BoxGeometry(...size), mats.col), `ZONE_${id}${k ? '.00' + k : ''}`);
    m.position.set((min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2);
  }
  const win = (c) => ({ a: c - 0.6, b: c + 0.6, bottom: 0.9, top: 2.0 });
  const door = (c, w = 1.6) => ({ a: c - w / 2, b: c + w / 2, bottom: 0, top: 2.4 });
  const H = 3.2;

  // ground: street level slab with a hole-free layout (bunker sits north, below)
  solid([90, 0.2, 52], [0, -0.1, 8], mats.ground, 0, true);
  vis([90, 0.02, 52], [0, -0.01, 8], mats.ground).receiveShadow = true;
  vis([9, 0.03, 40], [0, 0.0, 2], mats.road);

  // ---------- yellow house (west) ----------
  wallZ(-12, -7, 7, 0, H, mats.yellow, [door(0)]);
  wallZ(-24, -7, 7, 0, H, mats.yellow, [win(-3.5), win(3.5)]);
  wallX(-7, -24, -12, 0, H, mats.yellow);
  wallX(7, -24, -12, 0, H, mats.yellow);
  vis([12, 0.05, 14], [-18, 0.02, 0], mats.floor);
  vis([12.6, 0.3, 14.6], [-18, H + 0.15, 0], mats.wood);
  solid([2.2, 0.9, 0.9], [-16, 0.45, 5.8], mats.wood); // sofa
  solid([1.2, 0.8, 2.2], [-20, 0.4, -1], mats.wood);   // table
  // ---------- green house (east) ----------
  wallZ(12, -7, 7, 0, H, mats.green, [door(0)]);
  wallZ(24, -7, 7, 0, H, mats.green, [win(-3.5), win(3.5)]);
  wallX(-7, 12, 24, 0, H, mats.green);
  wallX(7, 12, 24, 0, H, mats.green);
  vis([12, 0.05, 14], [18, 0.02, 0], mats.floor);
  vis([12.6, 0.3, 14.6], [18, H + 0.15, 0], mats.wood);
  solid([2.2, 0.9, 0.9], [16, 0.45, 5.8], mats.wood);
  solid([1.2, 0.8, 2.2], [20, 0.4, -1], mats.wood);

  // backyard pockets (window spawns): enclosed, unreachable
  wallX(-7, -32, -24, 0, H, mats.fence); wallX(7, -32, -24, 0, H, mats.fence); wallZ(-32, -7, 7, 0, H, mats.fence);
  wallX(-7, 24, 32, 0, H, mats.fence); wallX(7, 24, 32, 0, H, mats.fence); wallZ(32, -7, 7, 0, H, mats.fence);

  // ---------- street boundary ----------
  wallZ(-12, 7, 22, 0, H, mats.fence); wallZ(-12, -18, -7, 0, H, mats.fence);
  wallZ(12, 7, 22, 0, H, mats.fence); wallZ(12, -18, -7, 0, H, mats.fence);
  wallX(22, -12, 12, 0, H, mats.fence);
  wallX(-18, -12, 12, 0, H, mats.fence, [{ a: -2, b: 2, bottom: 0, top: H }]);

  // bus + truck + debris
  solid([2.6, 3.0, 10.5], [3.2, 1.5, -5], mats.bus, 0.35);
  solid([2.1, 2.0, 5.2], [-5.5, 1.0, 13], mats.metal, -0.2);
  solid([1.2, 1.0, 1.2], [6, 0.5, 8], mats.wood, 0.3);
  solid([0.7, 1.0, 0.7], [-4, 0.5, -8], mats.metal);     // fire barrel
  solid([0.7, 1.0, 0.7], [7.5, 0.5, 17], mats.metal);

  // ---------- bunker (north, floor -2.5) ----------
  const B = -2.5;
  // ramp x -2..2, z -18..-24 descending to B
  const rampLen = 6, rampAngle = Math.atan2(2.5, rampLen);
  {
    const g = new THREE.BoxGeometry(4, 0.2, Math.hypot(rampLen, 2.5));
    const m = add(new THREE.Mesh(g, mats.concrete), 'bunker_ramp');
    m.position.set(0, -1.25 - 0.1, -21); m.rotation.x = -rampAngle;
    const c = add(new THREE.Mesh(g, mats.col), 'COL_bunker_ramp');
    c.position.copy(m.position); c.rotation.copy(m.rotation);
  }
  solid([0.3, 4.5, 6], [-2.15, B + 2.0, -21], mats.concrete);
  solid([0.3, 4.5, 6], [2.15, B + 2.0, -21], mats.concrete);
  // room x -6..6, z -24..-34
  solid([12, 0.2, 10], [0, B - 0.1, -29], mats.concrete);
  wallX(-24, -6, 6, B, 3.6, mats.concrete, [{ a: -2, b: 2, bottom: 0, top: 3.6 }]);
  wallX(-34, -6, 6, B, 3.6, mats.concrete);
  wallZ(6, -34, -24, B, 3.6, mats.concrete);
  wallZ(-6, -34, -24, B, 3.6, mats.concrete, [{ a: -29.6, b: -28.4, bottom: 0.9, top: 2.0 }]);
  // bunker vent pocket (window spawn) x -12..-6
  solid([6, 0.2, 6], [-9, B - 0.1, -29], mats.concrete);
  wallX(-32, -12, -6, B, 3.6, mats.concrete); wallX(-26, -12, -6, B, 3.6, mats.concrete); wallZ(-12, -32, -26, B, 3.6, mats.concrete);
  // bunker door visual + blocker at top of ramp
  const doorB = vis([4, 2.6, 0.25], [0, 1.3, -18], mats.metal); doorB.name = doorB.userData.name = 'DOOR_bunker_door';
  const doorBc = add(new THREE.Mesh(new THREE.BoxGeometry(4, 3.2, 0.5), mats.col), 'COL_DOOR_bunker_door'); doorBc.position.set(0, 1.6, -18);
  // house doors
  for (const [id, x] of [['yellow_front', -12], ['green_front', 12]]) {
    const d = vis([0.12, 2.4, 1.6], [x, 1.2, 0], mats.door); d.name = d.userData.name = `DOOR_${id}`;
    const c = add(new THREE.Mesh(new THREE.BoxGeometry(0.5, 3.2, 1.7), mats.col), `COL_DOOR_${id}`); c.position.set(x, 1.6, 0);
  }
  // barrier blockers
  for (const [id, pos, axis] of [['yw1', [-24, 1.45, -3.5], 'x'], ['yw2', [-24, 1.45, 3.5], 'x'], ['gw1', [24, 1.45, -3.5], 'x'], ['gw2', [24, 1.45, 3.5], 'x'], ['bw1', [-6, B + 1.45, -29], 'x']]) {
    const c = add(new THREE.Mesh(new THREE.BoxGeometry(0.4, 1.1, 1.2), mats.col), `COL_BARRIER_${id}`); c.position.set(...pos);
  }

  // ---------- zones ----------
  zone('street', [-12, -1, -18], [12, 4, 22]);
  zone('yellow', [-24, -1, -7], [-12, 4, 7]);
  zone('green', [12, -1, -7], [24, 4, 7]);
  zone('bunker', [-2, -3, -24], [2, 1, -18]);
  zone('bunker', [-6, -3, -34], [6, 1, -24], 1);

  // ---------- markers (+Z local = facing) ----------
  const E = Math.PI / 2, W = -Math.PI / 2, N = Math.PI, S = 0; // facing east(+x) / west / north(-z) / south(+z)
  marker('MK_PLAYER_START', [0, 0, 12], N);
  [[-9, 18], [9, 19], [-9, -14], [9, -12], [-2, 20], [6, -15], [-8, 3], [8, 2]].forEach(([x, z], i) => marker(`MK_SPAWN_GROUND_street_${i + 1}`, [x, 0, z]));
  marker('MK_SPAWN_GROUND_bunker_1', [4, B, -31]); marker('MK_SPAWN_GROUND_bunker_2', [-3, B, -32.5]);
  marker('MK_BARRIER_yw1', [-24, 0.9, -3.5], E); marker('MK_SPAWN_WIN_yw1', [-29, 0, -3.5]);
  marker('MK_BARRIER_yw2', [-24, 0.9, 3.5], E); marker('MK_SPAWN_WIN_yw2', [-29, 0, 3.5]);
  marker('MK_BARRIER_gw1', [24, 0.9, -3.5], W); marker('MK_SPAWN_WIN_gw1', [29, 0, -3.5]);
  marker('MK_BARRIER_gw2', [24, 0.9, 3.5], W); marker('MK_SPAWN_WIN_gw2', [29, 0, 3.5]);
  marker('MK_BARRIER_bw1', [-6, B + 0.9, -29], E); marker('MK_SPAWN_WIN_bw1', [-10, B, -29]);
  marker('MK_DOOR_yellow_front', [-11, 0, 0], W); marker('MK_DOOR_green_front', [11, 0, 0], E); marker('MK_DOOR_bunker_door', [0, 0, -17], N);
  marker('MK_WALLBUY_m14', [-11.86, 1.45, 4], E);
  marker('MK_WALLBUY_olympia', [11.86, 1.45, 4], W);
  marker('MK_WALLBUY_mp5', [-18, 1.45, -6.86], S);
  marker('MK_WALLBUY_remington870', [18, 1.45, -6.86], S);
  marker('MK_WALLBUY_ak74u', [-5.86, B + 1.45, -26], E);
  marker('MK_PERK_quickrevive', [11.2, 0, 15], W);
  marker('MK_PERK_speedcola', [-23.3, 0, -5.8], E);
  marker('MK_PERK_juggernog', [23.3, 0, -5.8], W);
  marker('MK_PERK_doubletap', [5.3, B, -26.5], W);
  marker('MK_BOX_1', [0, 0, 21.3], N);
  marker('MK_BOX_2', [-18, 0, 6.4], N);
  marker('MK_BOX_3', [18, 0, 6.4], N);
  marker('MK_BOX_4', [-3.5, B, -33.4], S);
  marker('MK_PAP', [2, B, -33.2], S);
  marker('MK_POWER', [5.86, B + 1.3, -31], W);
  [[-8, 4.5, -10], [8, 4.5, 10], [-8, 4.5, 18], [8, 4.5, -14], [-18, 2.8, 0], [18, 2.8, 0], [0, B + 3.2, -29]].forEach((p, i) => marker(`MK_LAMP_${i + 1}`, p));
  [[-4, 1.0, -8], [7.5, 1.0, 17], [4.2, 0.4, -9.5]].forEach((p, i) => marker(`MK_FIRE_${i + 1}`, p));

  // street lamp posts
  for (const p of [[-8, -10], [8, 10], [-8, 18], [8, -14]]) solid([0.15, 4.6, 0.15], [p[0], 2.3, p[1]], mats.metal);

  root.traverse(o => { if (o.isMesh && o.material !== mats.col) { o.castShadow = true; o.receiveShadow = true; } });
  return root;
}
