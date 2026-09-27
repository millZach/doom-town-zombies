// Xbox-layout gamepad support (standard mapping), BO2 "Default" button layout.
//
//   Left stick  move            Right stick  look          L3  sprint (latched)   R3  knife
//   LT          aim down sights RT           fire
//   LB / RB     frag grenade    A            jump          B   crouch
//   X           reload — or use / buy / rebuild when a prompt is showing (hold to rebuild)
//   Y           switch weapon   Start        pause         D-pad / A / B: menus
//
// The pad writes into the same Input object the keyboard/mouse use (virtual key codes and
// mouse-button state), plus analog `input.pad` values the player reads for movement and look.

const DEAD_MOVE = 0.18;
const DEAD_LOOK = 0.14;
const TRIGGER = 0.35;

// standard-mapping button indices
const B = { A: 0, B: 1, X: 2, Y: 3, LB: 4, RB: 5, LT: 6, RT: 7, BACK: 8, START: 9, L3: 10, R3: 11, UP: 12, DOWN: 13, LEFT: 14, RIGHT: 15 };

/** radial deadzone, rescaled so the usable range still reaches 1 */
function radial(x, y, dz) {
  const m = Math.hypot(x, y);
  if (m < dz) return [0, 0];
  const s = Math.min(1, (m - dz) / (1 - dz)) / m;
  return [x * s, y * s];
}

export class Gamepad {
  constructor(input) {
    this.input = input;
    this.index = null;
    this.prev = new Array(17).fill(false);
    this.connected = false;
    this.onConnect = null;
    this.onPause = null;            // Start pressed during play
    this.onMenuNav = null;          // (dir: 'up'|'down'|'left'|'right'|'accept'|'back'|'start')
    this.sprintLatched = false;
    this.navRepeat = 0;
    this.navHeld = null;
    this.lastActive = 0;
    input.pad = { active: false, lx: 0, ly: 0, rx: 0, ry: 0, lt: 0, rt: 0, usePressed: false, useDown: false };
    input.lastDevice = 'kbm';
    addEventListener('gamepadconnected', e => { this.index = e.gamepad.index; this.connected = true; this.onConnect?.(true, e.gamepad); });
    addEventListener('gamepaddisconnected', e => {
      if (e.gamepad.index === this.index) { this.index = null; this.connected = false; this._releaseAll(); this.onConnect?.(false, e.gamepad); }
    });
    // any keyboard/mouse activity flips prompts back to keyboard glyphs
    const kbm = () => { if (input.lastDevice !== 'kbm') { input.lastDevice = 'kbm'; this.onDeviceChange?.('kbm'); } };
    addEventListener('keydown', kbm);
    addEventListener('mousedown', kbm);
    addEventListener('mousemove', e => { if (Math.abs(e.movementX) + Math.abs(e.movementY) > 6) kbm(); });
  }

  _pad() {
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    if (this.index !== null && pads[this.index]) return pads[this.index];
    for (const p of pads) if (p && p.connected) { this.index = p.index; this.connected = true; return p; }
    return null;
  }

  _releaseAll() {
    const inp = this.input;
    for (const k of ['Space', 'KeyC', 'KeyG', 'KeyV', 'ShiftLeft']) inp.keys.delete(k);
    inp.mouse.left = inp.mouse.right = false;
    Object.assign(inp.pad, { active: false, lx: 0, ly: 0, rx: 0, ry: 0, lt: 0, rt: 0, usePressed: false, useDown: false });
  }

  /** mode: 'play' (drive gameplay input) or 'menu' (navigate DOM screens) */
  poll(dt, mode) {
    const gp = this._pad();
    const inp = this.input;
    if (!gp) { if (inp.pad.active) this._releaseAll(); return; }
    const btn = i => { const b = gp.buttons[i]; return !!b && (b.pressed || b.value > 0.5); };
    const now = gp.buttons.map((b, i) => (i === B.LT || i === B.RT) ? b.value > TRIGGER : btn(i));
    const hit = i => now[i] && !this.prev[i];
    const [lx, ly] = radial(gp.axes[0] || 0, gp.axes[1] || 0, DEAD_MOVE);
    const [rx, ry] = radial(gp.axes[2] || 0, gp.axes[3] || 0, DEAD_LOOK);
    const lt = gp.buttons[B.LT]?.value || 0, rt = gp.buttons[B.RT]?.value || 0;

    const any = now.some(Boolean) || Math.hypot(lx, ly) > 0 || Math.hypot(rx, ry) > 0;
    if (any) {
      this.lastActive = performance.now();
      if (inp.lastDevice !== 'pad') { inp.lastDevice = 'pad'; this.onDeviceChange?.('pad'); }
    }

    if (mode === 'menu') {
      this._releaseAll();
      this._menuNav(dt, now, hit, ly, lx);
      this.prev = now;
      return;
    }

    // ---------------- gameplay
    const pad = inp.pad;
    pad.active = inp.lastDevice === 'pad';
    pad.lx = lx; pad.ly = ly;
    // response curve: fine control near centre, full speed at the edge
    const curve = v => Math.sign(v) * Math.pow(Math.abs(v), 1.9);
    pad.rx = curve(rx); pad.ry = curve(ry);
    pad.lt = lt; pad.rt = rt;

    const setKey = (code, down, pressed) => {
      if (down) { if (!inp.keys.has(code) || pressed) inp.pressed.add(code); inp.keys.add(code); }
      else if (this._owned?.has(code)) inp.keys.delete(code);
      (this._owned ||= new Set())[down ? 'add' : 'delete'](code);
    };
    // A jump, B crouch (edge: the player toggles crouch on a press)
    if (hit(B.A)) inp.pressed.add('Space');
    if (hit(B.B)) inp.pressed.add('KeyC');
    // grenades on either bumper
    if (hit(B.LB) || hit(B.RB)) inp.pressed.add('KeyG');
    // knife
    if (hit(B.R3)) inp.pressed.add('KeyV');
    // switch weapon
    if (hit(B.Y)) inp.mouse.wheel += 1;
    // X: context — the game resolves use vs reload (it knows whether a prompt is up)
    pad.usePressed = hit(B.X);
    pad.useDown = now[B.X];
    // triggers
    const ads = now[B.LT], fire = now[B.RT];
    if (ads && !this.prev[B.LT]) inp.mouse.rightPressed = true;
    if (fire && !this.prev[B.RT]) inp.mouse.leftPressed = true;
    inp.mouse.right = ads || (inp.lastDevice === 'kbm' && inp.mouse.right);
    inp.mouse.left = fire || (inp.lastDevice === 'kbm' && inp.mouse.left);
    // sprint: click L3 to start, stays latched while pushing forward (BO2 style)
    if (hit(B.L3)) this.sprintLatched = true;
    if (ly > -0.35) this.sprintLatched = false;
    setKey('ShiftLeft', this.sprintLatched, false);
    // pause
    if (hit(B.START)) this.onPause?.();
    this.prev = now;
  }

  _menuNav(dt, now, hit, ly, lx) {
    // stick / d-pad with key-repeat so menus feel like a console
    const dir = now[B.UP] || ly < -0.6 ? 'up' : now[B.DOWN] || ly > 0.6 ? 'down'
      : now[B.LEFT] || lx < -0.6 ? 'left' : now[B.RIGHT] || lx > 0.6 ? 'right' : null;
    if (dir) {
      if (dir !== this.navHeld) { this.navHeld = dir; this.navRepeat = 0.38; this.onMenuNav?.(dir); }
      else { this.navRepeat -= dt; if (this.navRepeat <= 0) { this.navRepeat = 0.12; this.onMenuNav?.(dir); } }
    } else this.navHeld = null;
    if (hit(B.A)) this.onMenuNav?.('accept');
    if (hit(B.B)) this.onMenuNav?.('back');
    if (hit(B.START)) this.onMenuNav?.('start');
  }

  /** dual-rumble on the active pad (no-op where unsupported) */
  rumble(strong, weak, ms) {
    if (this.input.lastDevice !== 'pad') return;
    const gp = this._pad();
    const act = gp?.vibrationActuator;
    if (!act?.playEffect) return;
    try {
      act.playEffect('dual-rumble', { startDelay: 0, duration: ms, strongMagnitude: Math.min(1, strong), weakMagnitude: Math.min(1, weak) }).catch(() => {});
    } catch {}
  }
}
