// Dev-only helpers for screenshot tours / automated checks. Load in the console:
//   await import('/dev/tour.js')
const g = window.__game;
const V = g.player.pos.constructor;
export function begin({ power = true, doors = true } = {}) {
  document.getElementById('loading').classList.add('hidden');
  document.getElementById('menu').classList.add('hidden');
  g.start();
  g.roundTimer = 1e9;
  window.__step(30);
  if (doors) for (const d of g.doors) d.open();
  if (power) g.setPower(true);
  window.__step(60);
}
export function view(x, y, z, yaw, pitch = 0) {
  const p = g.player; p.pos.set(x, y, z); p.yaw = yaw; p.pitch = pitch; p.vel.set(0, 0, 0); window.__step(15);
}
export function look(mk, dist = 2.2, dy = 0, pitch = -0.05, side = 0) {
  const m = g.map.marker(mk); const p = g.player;
  p.pos.copy(m.pos).addScaledVector(m.forward, dist);
  p.pos.x += -m.forward.z * side; p.pos.z += m.forward.x * side;
  const h = g.nav.heightAt(p.pos.x, p.pos.z);
  p.pos.y = (isNaN(h) ? m.pos.y : h) + dy;
  const d = m.pos.clone().sub(p.pos);
  p.yaw = Math.atan2(-d.x, -d.z); p.pitch = pitch; p.vel.set(0, 0, 0);
  window.__step(15);
}
export function zom(x, z, v, gait = 'walk', y = 0) {
  const zz = g.zombies.spawn({ pos: new V(x, y, z), health: 1e6, gait, mode: 'chase' });
  if (v && zz.variantMeshes[v]) { for (const [k, l] of Object.entries(zz.variantMeshes)) for (const e of l) e.mesh.visible = k === v; zz.variant = v; }
  return zz;
}
const origUpdate = g.zombies.update.bind(g.zombies);
export function freezeAI(on = true) {
  const zm = g.zombies;
  zm.update = on ? (dt => { for (const z of zm.list) { z.mixer?.update(dt); zm._applyTransform(z); } }) : origUpdate;
}
export function hud(on) { document.getElementById('hud').classList.toggle('hidden', !on); }
export function viewmodel(on) { g.renderer.vmPass.enabled = on; }
export { g, V };
