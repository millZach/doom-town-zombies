// DOM HUD: hand-painted round counter, points, ammo, perks, power-ups, prompts.
import { POWERUPS } from '../config.js';

const $ = id => document.getElementById(id);

// hand-drawn digit strokes in a 40x80 cell
const DIGITS = {
  0: 'M21 5 C 6 6, 3 40, 5 60 C 7 78, 26 80, 31 66 C 37 44, 36 8, 21 5',
  1: 'M12 16 L 22 5 L 21 76',
  2: 'M6 18 C 10 2, 34 2, 32 22 C 30 40, 12 55, 5 76 L 36 73',
  3: 'M6 12 C 18 0, 36 8, 30 26 C 27 34, 20 37, 15 38 C 34 39, 38 60, 28 70 C 18 80, 6 74, 4 66',
  4: 'M28 76 L 27 5 L 4 52 L 38 51',
  5: 'M34 6 L 10 7 L 7 34 C 20 26, 36 34, 34 52 C 32 72, 12 78, 4 68',
  6: 'M31 8 C 16 2, 4 24, 5 50 C 6 72, 30 80, 34 60 C 37 42, 16 36, 6 50',
  7: 'M4 8 L 36 6 C 26 28, 18 50, 14 76',
  8: 'M20 38 C 4 30, 6 6, 20 5 C 34 6, 34 30, 20 38 C 2 44, 4 76, 20 76 C 36 76, 38 44, 20 38',
  9: 'M33 30 C 30 8, 6 6, 6 24 C 6 40, 30 42, 33 28 L 30 76',
};

const PERK_ICONS = {
  juggernog: (c) => `<svg viewBox="0 0 44 48"><path d="M22 2 L40 8 L38 30 C36 40 28 45 22 47 C16 45 8 40 6 30 L4 8 Z" fill="#3a0606" stroke="${c}" stroke-width="2.5"/><path d="M22 12 L31 16 L30 29 C29 34 25 37 22 38 C19 37 15 34 14 29 L13 16 Z" fill="${c}"/></svg>`,
  speedcola: (c) => `<svg viewBox="0 0 44 48"><path d="M22 2 L40 8 L38 30 C36 40 28 45 22 47 C16 45 8 40 6 30 L4 8 Z" fill="#06240c" stroke="${c}" stroke-width="2.5"/><path d="M25 9 L14 27 L21 27 L18 40 L30 20 L23 20 Z" fill="${c}"/></svg>`,
  quickrevive: (c) => `<svg viewBox="0 0 44 48"><path d="M22 2 L40 8 L38 30 C36 40 28 45 22 47 C16 45 8 40 6 30 L4 8 Z" fill="#06202e" stroke="${c}" stroke-width="2.5"/><path d="M18 12 H26 V20 H34 V28 H26 V36 H18 V28 H10 V20 H18 Z" fill="${c}"/></svg>`,
  doubletap: (c) => `<svg viewBox="0 0 44 48"><path d="M22 2 L40 8 L38 30 C36 40 28 45 22 47 C16 45 8 40 6 30 L4 8 Z" fill="#2a1604" stroke="${c}" stroke-width="2.5"/><path d="M14 36 V20 C14 14 18 11 18 11 C18 11 22 14 22 20 V36 Z M22 36 V20 C22 14 26 11 26 11 C26 11 30 14 30 20 V36 Z" fill="${c}"/></svg>`,
};

// ------------------------------------------------------------------ power-up emblems
// One family: struck-metal disc, a hairline inner ring, and a solid glyph.  Every
// power-up in POWERUPS has one — no more empty 58 px holes on the HUD.
const puDisc = (c, inner, plate = '#100d08') =>
  `<svg viewBox="0 0 60 60">
     <circle cx="30" cy="30" r="25.6" fill="${plate}" stroke="${c}" stroke-width="2.8"/>
     <circle cx="30" cy="30" r="21.4" fill="none" stroke="${c}" stroke-width="0.9" opacity="0.4"/>
     ${inner}
   </svg>`;

const PU_ICONS = {
  // ammo crate with two loose rounds sitting on the lid
  maxammo: (c) => puDisc(c, `
    <path d="M23 24 v-6 c0-2.6 4-2.6 4 0 v6 z" fill="${c}"/>
    <path d="M33 24 v-4 c0-2.6 4-2.6 4 0 v4 z" fill="${c}" opacity="0.8"/>
    <rect x="14.5" y="24.5" width="31" height="4.6" fill="${c}"/>
    <path d="M17 30.5 H43 V45.5 H17 Z" fill="none" stroke="${c}" stroke-width="2.6" stroke-linejoin="round"/>
    <path d="M23 37.5 H37" stroke="${c}" stroke-width="2.2" stroke-linecap="round"/>
    <path d="M23 41.5 H33" stroke="${c}" stroke-width="1.6" stroke-linecap="round" opacity="0.6"/>`),

  // skull
  instakill: (c) => puDisc(c, `
    <g transform="translate(30 31.5) scale(0.70) translate(-30 -30)">
      <path d="M30 6 C16 6 9 16 10 28 C10 35 14 38 16 40 L16 48 L22 48 L22 44 L26 44 L26 48 L34 48 L34 44 L38 44 L38 48 L44 48 L44 40 C46 38 50 35 50 28 C51 16 44 6 30 6 Z" fill="${c}"/>
      <circle cx="22" cy="28" r="6.2" fill="#0d0b07"/><circle cx="38" cy="28" r="6.2" fill="#0d0b07"/>
      <path d="M30 34 L26.8 40.5 L33.2 40.5 Z" fill="#0d0b07"/>
    </g>`, '#151109'),

  // x2
  doublepoints: (c) => puDisc(c, `
    <text x="30" y="40.5" text-anchor="middle" font-family="Oswald, 'Arial Narrow', sans-serif" font-weight="600" font-size="27" fill="${c}">x2</text>`),

  // mushroom cloud
  nuke: (c) => puDisc(c, `
    <path d="M13.5 27 C13.5 16 21 10 30 10 C39 10 46.5 16 46.5 27 C41 22.6 36 24.6 30 24.6 C24 24.6 19 22.6 13.5 27 Z" fill="${c}"/>
    <path d="M26.2 25.5 C25.4 32 27 37.5 23.4 45 H36.6 C33 37.5 34.6 32 33.8 25.5 Z" fill="${c}" opacity="0.82"/>
    <path d="M15 48.5 H45" stroke="${c}" stroke-width="2.6" stroke-linecap="round"/>`),

  // claw hammer over fresh boards
  carpenter: (c) => puDisc(c, `
    <path d="M12.5 40.5 L40 30.5 M13.5 45 L34 37.5" stroke="${c}" stroke-width="2.6" stroke-linecap="round" opacity="0.55"/>
    <g transform="rotate(-24 30 29)">
      <rect x="27.6" y="20" width="4.8" height="25" rx="1.4" fill="${c}"/>
      <path d="M18.5 13 H41.5 V20.5 C41.5 23 39 24 37 22.8 L34 20.8 H26 L23 22.8 C21 24 18.5 23 18.5 20.5 Z" fill="${c}"/>
    </g>`),

  // house with a price tag
  firesale: (c) => puDisc(c, `
    <path d="M11 30.5 L30 15 L49 30.5" fill="none" stroke="${c}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M16 30 V45.5 H44 V30" fill="none" stroke="${c}" stroke-width="2.6" stroke-linejoin="round"/>
    <text x="30" y="43" text-anchor="middle" font-family="Oswald, 'Arial Narrow', sans-serif" font-weight="600" font-size="19" fill="${c}">$</text>`),
};

const PU_COLOR = {
  maxammo: '#9ed8ff', instakill: '#f2e6c8', doublepoints: '#ffd257',
  nuke: '#ff9a3c', carpenter: '#e0a765', firesale: '#ff6f3c',
};

export class HUD {
  constructor() {
    this.root = $('hud');
    this.pointsEl = $('points');
    this.popsEl = $('points-pops');
    this.promptEl = $('prompt');
    this.promptText = $('prompt-text') || this.promptEl;
    this.cross = $('crosshair');
    this.hit = $('hitmarker');
    this.roundSvg = $('round-svg');
    this.roundEl = $('round');
    this.perksEl = $('perks');
    this.puEl = $('powerups');
    this.dmgEl = $('dmg-arcs');
    this.displayPoints = 0;
    this.targetPoints = 0;
    this.hitT = 0;
    this._prompt = '';
    this._pus = '';
    this._puNodes = [];
    this._dmg = [];
    this._lastDmgT = -1;
    this.time = 0;
  }

  show(v) { this.root.classList.toggle('hidden', !v); }

  // ---------------------------------------------------------------- round counter
  // BO2: four red tally strokes, a slash across them at five, then painted numerals.
  // Everything is deliberately over-scaled and dark-haloed so it reads on a bright street.
  setRound(n, animate = true) {
    let paths = '';
    if (n <= 5) {
      const marks = Math.min(n, 4);
      for (let i = 0; i < marks; i++) {
        const x = 26 + i * 33;
        const lean = (i % 2 ? 2.5 : -2.5) + (i === 2 ? 1.5 : 0);
        const y0 = 11 + (i % 3) * 1.5, y1 = 79 - (i % 2) * 2.5;
        // slight S-bow so no two strokes are identical
        paths += `<path style="stroke-width:${10.2 - (i % 2) * 1.1}" d="M${(x - lean).toFixed(1)} ${y0} C ${(x + 2.5).toFixed(1)} ${y0 + 26}, ${(x - 3).toFixed(1)} ${y1 - 24}, ${(x + lean).toFixed(1)} ${y1}"/>`;
      }
      if (n >= 5) paths += `<path style="stroke-width:9" d="M8 76 C 44 63, 88 38, 138 15"/>`;
    } else {
      const s = String(n);
      const sw = s.length >= 3 ? 7.2 : 9.2;
      const step = s.length >= 3 ? 43 : 48;
      const x0 = (150 - ((s.length - 1) * step + 40)) / 2;    // centred in the 150-wide viewBox
      [...s].forEach((d, i) => {
        const rot = ((i * 37) % 7 - 3) * 0.55;         // each numeral sits at its own angle
        const dy = ((i * 53) % 5) - 2;
        paths += `<g transform="translate(${x0 + i * step} ${5 + dy}) rotate(${rot.toFixed(2)} 20 40)"><path style="stroke-width:${sw}" d="${DIGITS[d]}"/></g>`;
      });
    }
    this.roundSvg.innerHTML = `<g filter="url(#brush)">${paths}</g>`;
    if (animate) {
      this.roundEl.classList.remove('change');
      void this.roundEl.offsetWidth;
      this.roundEl.classList.add('change');
    }
  }

  setPoints(n, instant = false) {
    this.targetPoints = n;
    if (instant) { this.displayPoints = n; this.pointsEl.textContent = n; }
  }

  popPoints(amount) {
    const el = document.createElement('div');
    el.className = 'pop' + (amount < 0 ? ' neg' : '');
    el.textContent = (amount > 0 ? '+' : '') + amount;
    el.style.setProperty('--dx', `${-30 - Math.random() * 60}px`);
    el.style.setProperty('--dy', `${-20 - Math.random() * 50}px`);
    this.popsEl.appendChild(el);
    setTimeout(() => el.remove(), 950);
  }

  setAmmo(a) {
    const w = $('weapon');
    if (!a) { w.style.visibility = 'hidden'; return; }
    w.style.visibility = 'visible';
    const name = $('weapon-name');
    name.textContent = a.name;
    name.classList.toggle('pap', !!a.pap);
    $('mag').textContent = a.mag;
    $('reserve').textContent = a.reserve;
    const ammo = $('ammo');
    const low = a.mag <= Math.max(1, Math.floor((a.magMax || 1) * 0.25));
    ammo.classList.toggle('low', low && a.mag > 0);
    ammo.classList.toggle('empty', a.mag === 0);
    ammo.classList.toggle('dry', a.mag === 0 && a.reserve === 0);
    const hint = $('reload-hint');
    if (hint) {
      const needs = a.mag === 0 && a.reserve > 0;
      hint.textContent = a.reserve === 0 && a.mag === 0 ? 'No Ammo' : 'Reload';
      hint.classList.toggle('show', a.mag === 0);
      hint.classList.toggle('urgent', needs);
    }
  }

  setGrenades(n) {
    $('nades').innerHTML = '<i></i>'.repeat(Math.max(0, n));
  }

  setPerks(perks, colors) {
    this.perksEl.innerHTML = '';
    for (const p of perks) {
      const d = document.createElement('div');
      d.className = 'perk';
      d.innerHTML = PERK_ICONS[p]?.(colors[p]) || '';
      this.perksEl.appendChild(d);
    }
  }

  setPowerups(list) {
    // list: [{ id, left }]
    const key = list.map(p => p.id).join(',');
    if (key !== this._pus) {
      this._pus = key;
      this.puEl.innerHTML = list.map(p => {
        const c = PU_COLOR[p.id] || '#8fff6a';
        const svg = PU_ICONS[p.id]?.(c) || '';
        return `<div class="pu" style="--pc:${c}"><div class="pu-emblem">${svg}</div><div class="pu-bar"><i></i></div></div>`;
      }).join('');
      this._puNodes = [...this.puEl.children];
    }
    // the countdown ring/bar updates every frame without touching the DOM tree
    for (let i = 0; i < list.length; i++) {
      const el = this._puNodes[i];
      if (!el) continue;
      // instant power-ups pass their own (short) slot length — they have no config duration
      const dur = list[i].dur || POWERUPS[list[i].id]?.duration || 30;
      const f = Math.max(0, Math.min(1, list[i].left / dur));
      el.style.setProperty('--f', f);
      // the flashing "about to run out" state is relative, so a 5 s acknowledgement slot
      // doesn't blink for its whole life
      el.classList.toggle('expiring', list[i].left < Math.min(5, dur * 0.2));
    }
  }

  /** 'kbm' | 'pad' — prompts swap the F key for the Xbox X button */
  setDevice(d) {
    if (d === this.device) return;
    this.device = d;
    const t = this._prompt; this._prompt = null; this.setPrompt(t);
  }

  setPrompt(text) {
    if (text === this._prompt) return;
    const had = !!this._prompt;
    this._prompt = text || '';
    this.promptText.innerHTML = this.device === 'pad'
      ? this._prompt.replace(/<b>F<\/b>/g, '<b class="pad-btn pad-x">X</b>')
      : this._prompt;
    this.promptEl.classList.toggle('show', !!this._prompt);
    if (this._prompt && !had) {
      this.promptEl.classList.remove('in');
      void this.promptEl.offsetWidth;
      this.promptEl.classList.add('in');
    }
  }

  // ---------------------------------------------------------------- hit feedback
  // part: 'head' | 'neck' | anything else.  kill: true for a killing blow.
  hitmarker(kill = false, part = null) {
    const head = part === 'head' || part === 'neck';
    this.hit.classList.toggle('kill', !!kill);
    this.hit.classList.toggle('head', head);
    this.hit.classList.remove('pop');
    void this.hit.offsetWidth;
    this.hit.classList.add('pop');
    this.hitT = kill ? 0.26 : head ? 0.22 : 0.18;
  }

  // angle in radians relative to the view direction: 0 = dead ahead, +ve = to the right.
  damageFrom(angle = 0) {
    // de-dupe: several pellets / a zombie swiping twice in a frame is one arc
    if (this.time - this._lastDmgT < 0.06) return;
    this._lastDmgT = this.time;
    if (!this.dmgEl) return;
    const deg = (angle * 180 / Math.PI).toFixed(1);
    const el = document.createElement('div');
    el.className = 'dmg';
    el.style.transform = `rotate(${deg}deg)`;
    el.innerHTML = `<svg viewBox="-60 -60 120 120"><path d="M -30 -46 A 55 55 0 0 1 30 -46" /></svg>`;
    this.dmgEl.appendChild(el);
    while (this.dmgEl.children.length > 6) this.dmgEl.removeChild(this.dmgEl.firstChild);
    setTimeout(() => el.remove(), 1200);
  }

  announce(text) {
    const el = $('announce');
    el.textContent = text;
    el.classList.remove('show');
    void el.offsetWidth;
    el.classList.add('show');
  }

  flashMessage(text, ms = 2600) {
    const el = $('flash-msg');
    const t = $('flash-text') || el;
    t.textContent = text;
    el.classList.remove('show');
    void el.offsetWidth;
    el.classList.add('show');
    clearTimeout(this._fm);
    this._fm = setTimeout(() => el.classList.remove('show'), ms);
  }

  setDowned(on, frac = 0, text = '') {
    $('downed').classList.toggle('hidden', !on);
    if (on) { $('downed-fill').style.width = `${frac * 100}%`; $('downed-sub').textContent = text; }
  }

  update(dt, { spread = 2, showCross = true } = {}) {
    this.time += dt;
    // count points up smoothly
    if (this.displayPoints !== this.targetPoints) {
      const d = this.targetPoints - this.displayPoints;
      const step = Math.sign(d) * Math.max(1, Math.ceil(Math.abs(d) * Math.min(1, dt * 14)));
      this.displayPoints += Math.abs(step) > Math.abs(d) ? d : step;
      this.pointsEl.textContent = this.displayPoints;
    }
    this.hitT -= dt;
    this.hit.style.opacity = this.hitT > 0 ? Math.min(1, this.hitT / 0.08) : 0;
    this.cross.style.opacity = showCross ? 1 : 0;
    this.cross.style.setProperty('--gap', `${6 + spread * 5.5}px`);
  }
}
