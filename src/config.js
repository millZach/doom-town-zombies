// Gameplay tuning. Numbers follow Black Ops 2 Zombies where known, scaled to metres.

export const PLAYER = {
  radius: 0.35,
  height: 1.8,
  eyeHeight: 1.62,
  crouchEyeHeight: 1.08,
  proneEyeHeight: 0.45,
  walkSpeed: 4.6,
  sprintSpeed: 6.9,
  crouchSpeed: 2.3,
  adsSpeedMul: 0.55,
  backpedalMul: 0.8,
  jumpVelocity: 5.2,
  gravity: 19,
  sprintDuration: 4.0,
  sprintRecover: 2.2,
  health: 100,
  juggHealth: 250,
  regenDelay: 2.6,
  regenRate: 140,          // hp per second once regen kicks in
  startPoints: 500,
  fov: 70,
};

export const ZOMBIE = {
  hitDamage: 60,           // 2 hits down without Juggernog, 5 with
  attackRange: 1.15,
  hitRange: 1.55,
  maxAlive: 24,
  radius: 0.32,
  walkSpeed: 0.95,
  runSpeed: 2.7,
  sprintSpeed: 4.4,
};

export const POINTS = {
  hit: 10,
  kill: 50,
  killNeck: 60,
  killHead: 100,
  killKnife: 130,
  board: 10,
  boardCapPerRound: 490,
  nuke: 400,
  carpenter: 200,
};

// BO2 zombie health: +100 per round to round 9, then x1.1 per round.
export function zombieHealth(round) {
  if (round < 10) return 150 + 100 * (round - 1);
  return Math.round(950 * Math.pow(1.1, round - 9));
}

// BO2 solo round sizes (roughly 6, 8, 13, 18, 24, ... then growing)
export function zombiesForRound(round) {
  let mult = Math.max(1, round / 5);
  if (round >= 10) mult *= round * 0.15;
  let max = 24 + Math.floor(0.5 * 6 * mult);
  const early = [0, 0.25, 0.3, 0.5, 0.7, 0.9];
  if (round < 6) max = Math.floor(max * early[round]);
  return max;
}

export function spawnDelay(round) {
  return Math.max(0.35, 2.0 * Math.pow(0.95, round - 1));
}

// probability a newly spawned zombie is a runner / sprinter
export function zombieSpeedMix(round) {
  const sprint = Math.min(0.85, Math.max(0, (round - 6) * 0.12));
  const run = Math.min(1 - sprint, Math.max(0, (round - 2) * 0.22));
  return { run, sprint };
}

export function dogHealth(round) {
  return Math.min(1600, 220 + round * 60);
}

export const PERKS = {
  juggernog:   { name: 'Juggernog',     cost: 2500, color: '#d11f1f', desc: 'Take more hits' },
  speedcola:   { name: 'Speed Cola',    cost: 3000, color: '#2fbf4f', desc: 'Faster reloads' },
  quickrevive: { name: 'Quick Revive',  cost: 500,  color: '#5fd0ff', desc: 'Self revive (solo)', noPower: true },
  doubletap:   { name: 'Double Tap Root Beer', cost: 2000, color: '#c9892e', desc: 'Faster fire rate, more damage' },
};

// ---------------------------------------------------------------- weapon feel
//
// adsDist      distance from the eye to the sight (aim node) at full ADS, in metres.
//              BO2 sits the rear sight around 0.26 m (pistols) to 0.34 m (LMG/shotgun);
//              anything closer and the receiver eats the frame.
// adsTime      seconds from hip to full ADS (and back).
// reloadClass  drives both the reload choreography and the per-class reload foley.
// reloadEvents normalised 0..1 event table (see RELOAD_EVENTS below for the class defaults).
// recoilPattern  per-shot [pitchMul, yawMul] sampled by shotCount % length — a real, learnable
//              pattern instead of noise. Positive yaw = the muzzle walks right.
// flash        muzzle flash: scale (metres), colour, spike count, side-card length along the barrel.
// shellKind    brass | shotshell | none — what the ejection port throws out.
// boltTravel   how far `bolt` / `slide` reciprocates, in metres.
//
// type: sound family.  mode: semi | auto | pump | break | projectile
export const WEAPONS = {
  m1911: {
    name: 'M1911', type: 'pistol', mode: 'semi', rpm: 520, damage: 100, headMult: 2.2, mag: 8, reserve: 80,
    reload: 1.6, reloadEmpty: 1.9, spreadHip: 2.6, spreadAds: 0.25, recoil: 1.6, adsFov: 55, pen: 0, range: 30,
    wallCost: 0, slot: 'pistol',
    adsDist: 0.26, adsTime: 0.15, reloadClass: 'pistol', shellKind: 'brass', shellScale: 0.95, boltTravel: 0.032,
    recoilPattern: [[1, 0.25], [1.1, -0.35], [0.95, 0.5], [1.15, -0.2], [1, 0.15], [1.05, -0.45]],
    flash: { scale: 0.075, color: 0xffd7a0, spikes: 3, sideLen: 0.5 },
    pap: { name: 'Mustang & Sally', damage: 1000, mag: 12, reserve: 50, explosive: { radius: 2.8, damage: 1300 }, rpm: 560 },
  },
  olympia: {
    name: 'Olympia', type: 'shotgun', mode: 'break', rpm: 240, damage: 110, pellets: 8, headMult: 1.5, mag: 2, reserve: 38,
    reload: 2.3, spreadHip: 5.5, spreadAds: 3.8, recoil: 5.5, adsFov: 60, pen: 0, range: 14, wallCost: 500,
    adsDist: 0.19, adsTime: 0.26, reloadClass: 'break', shellKind: 'shotshell', ejectOnFire: false, kickScale: 2.2,
    recoilPattern: [[1, -0.35], [1, 0.35]],
    flash: { scale: 0.2, color: 0xffb870, spikes: 2, sideLen: 1.25, wide: 1.35 },
    pap: { name: 'Hades', damage: 240, mag: 2, reserve: 60, incendiary: true },
  },
  m14: {
    name: 'M14', type: 'rifle', mode: 'semi', rpm: 460, damage: 105, headMult: 2.5, mag: 8, reserve: 92,
    reload: 2.2, reloadEmpty: 2.6, spreadHip: 3.0, spreadAds: 0.1, recoil: 2.2, adsFov: 50, pen: 1, range: 60, wallCost: 500,
    adsDist: 0.33, adsTime: 0.24, reloadClass: 'rifle', shellKind: 'brass', shellScale: 1.15, boltTravel: 0.055,
    recoilPattern: [[1.15, -0.3], [1, 0.45], [1.1, -0.15], [0.95, 0.3], [1.2, -0.5], [1, 0.2]],
    flash: { scale: 0.115, color: 0xffcb8c, spikes: 5, sideLen: 0.7 },
    pap: { name: 'Mnesia', damage: 180, mag: 15, reserve: 150, mode: 'auto', rpm: 560 },
  },
  mp5: {
    name: 'MP5', type: 'smg', mode: 'auto', rpm: 800, damage: 70, headMult: 2.0, mag: 30, reserve: 120,
    reload: 2.3, reloadEmpty: 2.7, spreadHip: 3.2, spreadAds: 0.6, recoil: 0.9, adsFov: 55, pen: 0, range: 30, wallCost: 1000,
    adsDist: 0.32, adsTime: 0.17, reloadClass: 'smg', shellKind: 'brass', shellScale: 0.95, boltTravel: 0.05,
    // tight, climbs almost straight with a slow drift to the right
    recoilPattern: [[0.9, 0.05], [0.95, 0.12], [1, 0.2], [1.05, 0.3], [1, 0.42], [0.95, 0.5], [0.9, 0.42], [0.95, 0.28], [1, 0.12], [1.05, -0.05]],
    flash: { scale: 0.09, color: 0xffd0a0, spikes: 4, sideLen: 0.6 },
    pap: { name: 'MP115 Kollider', damage: 120, mag: 40, reserve: 200 },
  },
  remington870: {
    name: 'Remington 870 MCS', type: 'shotgun', mode: 'pump', rpm: 72, damage: 110, pellets: 8, headMult: 1.5, mag: 8, reserve: 32,
    reload: 0.55, spreadHip: 4.8, spreadAds: 3.2, recoil: 5, adsFov: 58, pen: 0, range: 16, wallCost: 1500, perShell: true,
    adsDist: 0.24, adsTime: 0.26, reloadClass: 'shotgun', shellKind: 'shotshell', ejectOnFire: false, kickScale: 2.2,
    recoilPattern: [[1, 0.3], [1, -0.3]],
    flash: { scale: 0.18, color: 0xffba74, spikes: 3, sideLen: 1.1, wide: 1.25 },
    pap: { name: 'Refitted-870 Mechanical Cranium Sequencer', damage: 180, mag: 10, reserve: 60, rpm: 110 },
  },
  ak74u: {
    name: 'AK-74u', type: 'smg', mode: 'auto', rpm: 740, damage: 105, headMult: 2.0, mag: 20, reserve: 160,
    reload: 2.2, reloadEmpty: 2.6, spreadHip: 3.2, spreadAds: 0.6, recoil: 1.2, adsFov: 55, pen: 0, range: 35, wallCost: 1200,
    adsDist: 0.32, adsTime: 0.19, reloadClass: 'smg', magRock: true, shellKind: 'brass', shellScale: 1.0, boltTravel: 0.06,
    // sharper, kicks up-left then snaps right
    recoilPattern: [[1.2, -0.3], [1.1, -0.45], [1, -0.2], [1.05, 0.25], [1.15, 0.5], [1, 0.35], [0.95, -0.1], [1.1, -0.4]],
    flash: { scale: 0.105, color: 0xffc888, spikes: 4, sideLen: 0.75 },
    pap: { name: 'AK74fu2', damage: 160, mag: 40, reserve: 280 },
  },
  galil: {
    name: 'Galil', type: 'rifle', mode: 'auto', rpm: 660, damage: 120, headMult: 2.5, mag: 35, reserve: 315,
    reload: 2.7, reloadEmpty: 3.1, spreadHip: 3.8, spreadAds: 0.35, recoil: 1.3, adsFov: 50, pen: 1, range: 60, box: 3,
    adsDist: 0.32, adsTime: 0.22, reloadClass: 'rifle', magRock: true, shellKind: 'brass', shellScale: 1.05, boltTravel: 0.055,
    recoilPattern: [[1, -0.15], [1.05, -0.3], [1.1, -0.4], [1, -0.2], [0.95, 0.1], [1, 0.3], [1.05, 0.4], [1, 0.15]],
    flash: { scale: 0.11, color: 0xffcf94, spikes: 5, sideLen: 0.7 },
    pap: { name: 'Lamentation', damage: 180, mag: 35, reserve: 490 },
  },
  rpd: {
    name: 'RPD', type: 'lmg', mode: 'auto', rpm: 750, damage: 120, headMult: 2.2, mag: 100, reserve: 400,
    reload: 5.2, spreadHip: 5.0, spreadAds: 0.8, recoil: 1.4, adsFov: 52, pen: 2, range: 60, box: 3, heavy: true,
    adsDist: 0.34, adsTime: 0.32, reloadClass: 'lmg', shellKind: 'brass', shellScale: 1.15, boltTravel: 0.065, kickScale: 1.15,
    recoilPattern: [[1.1, 0.2], [1, -0.25], [1.05, 0.35], [1.15, -0.15], [1, 0.4], [0.95, -0.35], [1.1, 0.15], [1, -0.4]],
    flash: { scale: 0.145, color: 0xffc27f, spikes: 6, sideLen: 0.85 },
    pap: { name: 'Relativistic Punch Device', damage: 180, mag: 125, reserve: 500 },
  },
  python: {
    name: 'Python', type: 'revolver', mode: 'semi', rpm: 150, damage: 520, headMult: 2.0, mag: 6, reserve: 84,
    reload: 3.0, spreadHip: 2.5, spreadAds: 0.15, recoil: 4.5, adsFov: 50, pen: 2, range: 50, box: 3, perShellDisplay: false,
    adsDist: 0.27, adsTime: 0.2, reloadClass: 'revolver', shellKind: 'none', kickScale: 1.8,
    recoilPattern: [[1.25, -0.4], [1.2, 0.45], [1.3, -0.25], [1.15, 0.3]],
    flash: { scale: 0.135, color: 0xffd6a8, spikes: 4, sideLen: 0.55, cylinderGap: true },
    pap: { name: 'Cobra', damage: 1200, mag: 12, reserve: 120 },
  },
  raygun: {
    name: 'Ray Gun', type: 'raygun', mode: 'projectile', rpm: 181, damage: 1000, splash: { radius: 1.8, damage: 300 }, headMult: 1,
    mag: 20, reserve: 160, reload: 2.8, spreadHip: 1.5, spreadAds: 0.1, recoil: 2.0, adsFov: 55, range: 100, box: 1,
    projectileSpeed: 60, projectileColor: 0x5dff55,
    adsDist: 0.3, adsTime: 0.22, reloadClass: 'raygun', shellKind: 'none',
    recoilPattern: [[1, 0.2], [1.05, -0.25], [0.95, 0.3], [1.1, -0.15]],
    flash: { scale: 0.17, color: 0x66ff55, spikes: 0, sideLen: 0.9, afterglow: 0.28 },
    pap: { name: "Porter's X2 Ray Gun", damage: 2000, mag: 40, reserve: 200, projectileColor: 0xff3322, splash: { radius: 2.2, damage: 700 } },
  },
};

// Normalised (0..1 of the reload duration) event tables per reload class. Speed Cola simply makes
// the reload shorter, so every beat arrives sooner — nothing is ever pitch-shifted.
//   *_out / *_in  magazine or belt leaving / entering the weapon
//   grab          the left hand reaches for a fresh magazine (off screen)
//   seat          the palm slap that seats the magazine
//   bolt/slide    the action is released or run
export const RELOAD_EVENTS = {
  pistol: [
    [0.05, 'release'], [0.16, 'mag_out'], [0.34, 'grab'], [0.58, 'mag_in'], [0.70, 'seat'], [0.84, 'slide'],
  ],
  smg: [
    [0.05, 'release'], [0.17, 'mag_out'], [0.36, 'grab'], [0.58, 'mag_in'], [0.70, 'seat'], [0.82, 'bolt'],
  ],
  rifle: [
    [0.05, 'release'], [0.18, 'mag_out'], [0.38, 'grab'], [0.60, 'mag_in'], [0.72, 'seat'], [0.84, 'bolt'],
  ],
  lmg: [
    [0.04, 'cover'], [0.14, 'mag_out'], [0.34, 'grab'], [0.56, 'mag_in'], [0.68, 'belt'], [0.80, 'cover_close'], [0.90, 'bolt'],
  ],
  break: [
    [0.08, 'release'], [0.20, 'open'], [0.34, 'eject'], [0.52, 'shell'], [0.62, 'shell2'], [0.76, 'close'], [0.88, 'lock'],
  ],
  revolver: [
    [0.08, 'open'], [0.26, 'eject'], [0.46, 'grab'], [0.66, 'shell'], [0.80, 'close'], [0.90, 'lock'],
  ],
  raygun: [
    [0.08, 'release'], [0.2, 'mag_out'], [0.42, 'grab'], [0.62, 'mag_in'], [0.78, 'charge'],
  ],
  // the pump gun loads one shell at a time; the loop is driven per shell, not by this table
  shotgun: [[0.25, 'shell']],
};

/** Reload class for a weapon id (falls back to something sane for unknown ids). */
export function reloadClassOf(def) {
  if (!def) return 'rifle';
  if (def.reloadClass) return def.reloadClass;
  if (def.perShell) return 'shotgun';
  if (def.mode === 'break') return 'break';
  if (def.type === 'revolver') return 'revolver';
  if (def.type === 'raygun') return 'raygun';
  if (def.type === 'pistol') return 'pistol';
  if (def.type === 'lmg') return 'lmg';
  if (def.type === 'smg') return 'smg';
  return 'rifle';
}

// Viewmodel camera: ADS *widens* the weapon frustum so the gun shrinks in frame and the sight
// picture opens up (the opposite of zooming the viewmodel in).
export const VM_FOV = { hip: 50, ads: 58 };

export const BOX_COST = 950;
export const PAP_COST = 5000;
export const PAP_AMMO_COST = 4500;
export const FIRE_SALE_BOX_COST = 10;

export const DOORS = {
  yellow_front: { cost: 750, label: 'Door', opens: ['yellow'] },
  green_front: { cost: 750, label: 'Door', opens: ['green'] },
  bunker_door: { cost: 1250, label: 'Blast Door', opens: ['bunker'] },
  // house expansions: debris on the staircase, back doors into the yards
  yellow_stairs: { cost: 1000, label: 'Debris', opens: ['yellowup'] },
  green_stairs: { cost: 1000, label: 'Debris', opens: ['greenup'] },
  yellow_back: { cost: 1000, label: 'Door', opens: ['yardw'] },
  green_back: { cost: 1000, label: 'Door', opens: ['yarde'] },
};

// zone adjacency (used to pick which spawners are active)
export const ZONE_LINKS = {
  street: ['yellow', 'green', 'bunker'],
  yellow: ['street', 'yellowup', 'yardw'],
  green: ['street', 'greenup', 'yarde'],
  bunker: ['street'],
  yellowup: ['yellow'],
  greenup: ['green'],
  yardw: ['yellow'],
  yarde: ['green'],
};
export const DOOR_ZONES = {
  yellow_front: ['street', 'yellow'],
  green_front: ['street', 'green'],
  bunker_door: ['street', 'bunker'],
  yellow_stairs: ['yellow', 'yellowup'],
  green_stairs: ['green', 'greenup'],
  yellow_back: ['yellow', 'yardw'],
  green_back: ['green', 'yarde'],
};

export const POWERUPS = {
  maxammo: { name: 'Max Ammo', sound: 'max_ammo' },
  instakill: { name: 'Insta-Kill', sound: 'insta_kill', duration: 30 },
  doublepoints: { name: 'Double Points', sound: 'double_points', duration: 30 },
  nuke: { name: 'Kaboom!', sound: 'nuke_blast' },
  carpenter: { name: 'Carpenter', sound: 'carpenter' },
  firesale: { name: 'Fire Sale', sound: 'fire_sale', duration: 30 },
};
