import * as THREE from 'three';
import { Renderer } from './core/renderer.js';
import { Input } from './core/input.js';
import { Gamepad } from './core/gamepad.js';
import { HUD } from './ui/hud.js';
import { Game } from './game/game.js';

const $ = id => document.getElementById(id);

// Silent stand-in so the game runs even before/without the audio engine.
const silentHandle = { stop() {}, setPosition() {}, setVolume() {} };
const silentAudio = {
  init: async () => {}, setListener() {}, play: () => silentHandle, playAt: () => silentHandle, loop: () => silentHandle,
  music() {}, stopMusic() {}, setMasterVolume() {}, duck() {}, announce() {},
};

async function loadAudio() {
  try {
    const mod = await import('./audio/audio.js');
    return mod.audio || mod.default || silentAudio;
  } catch (e) {
    console.warn('[audio] engine unavailable, running silent', e);
    return silentAudio;
  }
}

// guard every audio call so a sound bug can never take the game down
function safeAudio(a) {
  const wrap = {};
  for (const k of Object.keys(silentAudio)) {
    wrap[k] = (...args) => {
      try { const r = a[k]?.(...args); return r ?? (k === 'play' || k === 'playAt' || k === 'loop' ? silentHandle : r); }
      catch (e) { console.warn('[audio]', k, args[0], e); return silentHandle; }
    };
  }
  return wrap;
}

const TIPS = [
  'Headshots are worth 100 points. Aim for the head.',
  'Rebuilding barricades earns points — up to a limit each round.',
  'Juggernog lets you survive five hits instead of two.',
  'The Mystery Box moves when the teddy bear laughs at you.',
  'Turn on the power to wake the perk machines and Pack-a-Punch.',
  'Train the horde in circles. Never let them corner you.',
  'Knife kills are worth 130 points.',
];

const settings = { sens: 1, fov: 75, vol: 0.8, quality: 'high', stick: 1, assist: 'on', invert: 'no' };
try { Object.assign(settings, JSON.parse(localStorage.getItem('dz_settings') || '{}')); } catch {}
const saveSettings = () => { try { localStorage.setItem('dz_settings', JSON.stringify(settings)); } catch {} };

// play-test setups: `?test=r21` starts every game (and every retry) at round 21 with the loadout
const TEST_ID = new URLSearchParams(location.search).get('test');
if (TEST_ID === 'r21') document.querySelector('button[data-action="play"]').textContent = 'Play Test — Round 21';

// debug: `?norender` boots with drawing off (scripted checks in a software-GL browser)
if (new URLSearchParams(location.search).has('norender')) window.__noRender = true;

async function boot() {
  $('load-tip').textContent = TIPS[Math.floor(Math.random() * TIPS.length)];
  const progress = (f, text) => { $('load-fill').style.width = `${Math.round(f * 100)}%`; $('load-status').textContent = text; };

  const renderer = new Renderer($('game'));
  // if the GPU drops the WebGL context (driver reset, VRAM pressure), recover by reloading
  renderer.renderer.domElement.addEventListener('webglcontextlost', e => {
    e.preventDefault();
    console.warn('[gl] context lost — reloading');
    document.body.insertAdjacentHTML('beforeend', '<div class="screen" style="z-index:50;background:#070504;font:400 18px var(--type);color:var(--dim)">Graphics device reset — reloading…</div>');
    setTimeout(() => location.reload(), 1500);
  });
  const input = new Input(renderer.renderer.domElement);
  const hud = new HUD();
  const audio = safeAudio(await loadAudio());
  const game = new Game(renderer, input, audio, hud);
  window.__game = game; // handy for debugging in the console
  const pad = new Gamepad(input);
  game.gamepad = pad;

  await game.load(progress);
  renderer.setQuality(settings.quality);
  applySettings();
  $('loading').classList.add('fade');
  setTimeout(() => $('loading').classList.add('hidden'), 900);

  let audioReady = false;
  let screen = 'menu';
  let returnTo = 'menu';
  const show = (id) => {
    for (const s of ['menu', 'pause', 'options', 'controls', 'gameover']) $(s).classList.toggle('hidden', s !== id);
    screen = id;
  };

  function applySettings() {
    input.sensitivity = settings.sens;
    game.baseFov = settings.fov;
    audio.setMasterVolume(settings.vol);
    $('opt-sens').value = settings.sens; $('opt-sens-v').textContent = Number(settings.sens).toFixed(2);
    $('opt-fov').value = settings.fov; $('opt-fov-v').textContent = settings.fov;
    $('opt-vol').value = settings.vol; $('opt-vol-v').textContent = Math.round(settings.vol * 100);
    $('opt-quality').value = settings.quality;
    input.stickSensitivity = settings.stick;
    input.invertY = settings.invert === 'yes';
    game.aimAssist = settings.assist;
    $('opt-stick').value = settings.stick; $('opt-stick-v').textContent = Number(settings.stick).toFixed(2);
    $('opt-assist').value = settings.assist;
    $('opt-invert').value = settings.invert;
  }
  $('opt-sens').oninput = e => { settings.sens = +e.target.value; applySettings(); saveSettings(); };
  $('opt-fov').oninput = e => { settings.fov = +e.target.value; applySettings(); saveSettings(); };
  $('opt-vol').oninput = e => { settings.vol = +e.target.value; applySettings(); saveSettings(); };
  $('opt-quality').onchange = e => { settings.quality = e.target.value; renderer.setQuality(settings.quality); saveSettings(); };
  $('opt-stick').oninput = e => { settings.stick = +e.target.value; applySettings(); saveSettings(); };
  $('opt-assist').onchange = e => { settings.assist = e.target.value; applySettings(); saveSettings(); };
  $('opt-invert').onchange = e => { settings.invert = e.target.value; applySettings(); saveSettings(); };

  // audio needs a user gesture; start building sounds on the first interaction so Play is instant
  let audioInit = null;
  const onProgress = p => { if (screen === 'menu' && !audioReady) $('menu-status').textContent = `Preparing audio… ${Math.round(p * 100)}%`; };
  const ensureAudio = () => audioInit ||= Promise.resolve(audio.init({ onProgress })).catch(e => console.warn(e)).then(() => {
    if (screen === 'menu') $('menu-status').innerHTML = 'Click <b>Play Solo</b> to begin. Survive as long as you can.';
    audioReady = true;
    if (game.state === 'menu') audio.music('menu');
  });
  addEventListener('pointerdown', ensureAudio, { once: true });
  addEventListener('keydown', ensureAudio, { once: true });

  async function play() {
    const gestured = !navigator.userActivation || navigator.userActivation.hasBeenActive;
    if (!audioReady && gestured) {
      $('menu-status').textContent = 'Preparing audio…';
      await ensureAudio();
    }
    audio.stopMusic(1.5);
    show(null);
    game.start();
    if (TEST_ID) game.applyTest(TEST_ID);
    input.lock();
    if (!audioReady && !gestured) hud.flashMessage('Click or press any key once to turn the sound on', 5000);
  }

  // ---- menu feedback.  `ui_hover` / `ui_click` are part of the new sound contract; if
  // the audio engine hasn't got them yet they are silent no-ops, so this is safe to ship.
  let hovered = null;
  // seconds since the game-over slow-motion started; null while it isn't running
  let goRamp = null;
  const ui = (name, volume) => { if (audioReady) audio.play(name, { volume }); };
  document.body.addEventListener('pointerover', e => {
    const b = e.target.closest('button[data-action], .opt, kbd');
    const btn = e.target.closest('button[data-action]');
    if (!b || b === hovered) return;
    hovered = b;
    if (btn) ui('ui_hover', 0.45);
  });
  document.body.addEventListener('pointerout', e => {
    if (e.target.closest('button[data-action], .opt, kbd') === hovered) hovered = null;
  });
  for (const id of ['opt-sens', 'opt-fov', 'opt-vol']) $(id).addEventListener('change', () => ui('ui_click', 0.4));
  $('opt-quality').addEventListener('change', () => ui('ui_click', 0.5));

  document.body.addEventListener('click', e => {
    const b = e.target.closest('button[data-action]');
    if (!b) return;
    const a = b.dataset.action;
    ui('ui_click', 0.7);
    if (a === 'play' || a === 'retry') play();
    else if (a === 'resume') { show(null); input.lock(); }
    else if (a === 'options' || a === 'controls') { returnTo = screen; show(a); }
    else if (a === 'back') show(returnTo);
    else if (a === 'quit' || a === 'menu') { game.state = 'menu'; game.timeScale = 1; goRamp = null; hud.show(false); game.zombies.clearAll(); show('menu'); audioReady && audio.music('menu'); }
  });

  input.onLockChange = locked => {
    if (!locked && game.state === 'playing' && screen === null) show('pause');
  };
  // clicking the canvas during play re-locks
  renderer.renderer.domElement.addEventListener('click', () => { if (game.state === 'playing' && screen === null && !input.locked) input.lock(); });

  game.onGameOver = stats => {
    game.state = 'over';
    // The world keeps running behind the screen (environment.md #28; the blur/desaturate
    // ramp is the .go-blur backdrop-filter).  It hits at 0.1x — the death beat — and then
    // eases back to real time over ~4 s, because in the 'over' state the only thing still
    // animating is the cinematic camera drift, and holding that at a tenth speed would
    // make the backdrop read as the still frame the review was complaining about.
    game.timeScale = 0.1;
    goRamp = 0;
    input.unlock();
    hud.show(false);
    $('go-sub').textContent = `You survived ${stats.round} round${stats.round === 1 ? '' : 's'}`;
    $('go-stats').innerHTML = [['Kills', stats.kills], ['Headshots', stats.headshots], ['Points', stats.points], ['Downs', stats.downs]]
      .map(([k, v]) => `<div><b>${v}</b><span>${k}</span></div>`).join('');
    show('gameover');
    audio.music('game_over');
  };

  // debug: advance the simulation manually (background tabs throttle requestAnimationFrame)
  window.__step = (n = 1, dt = 1 / 60) => {
    for (let i = 0; i < n; i++) { game.update(dt); input.endFrame(); }
    if (!window.__noRender) renderer.render(dt, game.time);
  };

  // ---------------- controller: device glyphs, pause, menu navigation
  pad.onDeviceChange = d => {
    hud.setDevice(d);
    document.body.classList.toggle('pad-mode', d === 'pad');
    if (d === 'pad' && screen !== null) focusFirst();
    if (d === 'kbm') for (const el of document.querySelectorAll('.pad-focus')) el.classList.remove('pad-focus');
  };
  pad.onConnect = on => { if (on && screen === 'menu') $('menu-status').innerHTML = 'Controller connected — press <b>A</b> to play.'; };
  pad.onPause = () => { if (game.state === 'playing' && screen === null) { show('pause'); input.unlock(); focusFirst(); } };
  let navIdx = 0;
  const focusables = () => screen ? [...$(screen).querySelectorAll('button[data-action], .opt')].filter(el => el.offsetParent !== null) : [];
  function setFocus(i) {
    const els = focusables();
    if (!els.length) return;
    navIdx = (i + els.length) % els.length;
    for (const el of document.querySelectorAll('.pad-focus')) el.classList.remove('pad-focus');
    els[navIdx].classList.add('pad-focus');
    ui('ui_hover', 0.45);
  }
  function focusFirst() { navIdx = 0; setFocus(0); }
  function nudge(el, dir) {
    const inp = el.querySelector('input[type=range]'), sel = el.querySelector('select');
    if (inp) {
      const step = +inp.step || 0.05, v = Math.min(+inp.max, Math.max(+inp.min, +inp.value + dir * step * (inp.max - inp.min > 5 ? 2 : 2)));
      inp.value = v; inp.dispatchEvent(new Event('input')); inp.dispatchEvent(new Event('change'));
    } else if (sel) {
      sel.selectedIndex = (sel.selectedIndex + dir + sel.options.length) % sel.options.length;
      sel.dispatchEvent(new Event('change'));
    }
  }
  pad.onMenuNav = dir => {
    if (!screen) return;
    const els = focusables();
    if (!els.some(el => el.classList.contains('pad-focus'))) { focusFirst(); if (dir !== 'accept') return; }
    const cur = els[navIdx];
    if (dir === 'up') setFocus(navIdx - 1);
    else if (dir === 'down') setFocus(navIdx + 1);
    else if ((dir === 'left' || dir === 'right') && cur?.classList.contains('opt')) nudge(cur, dir === 'left' ? -1 : 1);
    else if ((dir === 'left' || dir === 'right') && cur?.closest('.menu-nav.row')) setFocus(navIdx + (dir === 'left' ? -1 : 1));
    else if (dir === 'accept' && cur?.matches('button')) { cur.click(); setTimeout(focusFirst, 0); }
    else if (dir === 'back') {
      if (screen === 'options' || screen === 'controls') { show(returnTo); focusFirst(); }
      else if (screen === 'pause') { show(null); input.lock(); }
    } else if (dir === 'start') {
      if (screen === 'pause') { show(null); input.lock(); }
      else if (screen === 'menu') play();
    }
  };

  const clock = new THREE.Clock();
  // FPS counter (F3) + automatic quality step-down when a machine can't hold ~40 fps
  const fpsEl = document.createElement('div');
  fpsEl.style.cssText = 'position:fixed;top:8px;right:10px;font:500 13px var(--ui);color:#cfc6b6;text-shadow:0 1px 2px #000;z-index:40;display:none;pointer-events:none';
  document.body.appendChild(fpsEl);
  addEventListener('keydown', e => { if (e.code === 'F3') { e.preventDefault(); fpsEl.style.display = fpsEl.style.display === 'none' ? 'block' : 'none'; } });
  const perf = { acc: 0, n: 0, shown: 0, slow: 0 };
  const TIERS = ['high', 'medium', 'low'];
  function trackPerf(dt) {
    if (document.visibilityState !== 'visible' || dt > 0.25) return;   // ignore tab switches / hitches
    perf.acc += dt; perf.n++;
    if (perf.acc < 2) return;
    const fps = perf.n / perf.acc;
    fpsEl.textContent = `${fps.toFixed(0)} fps · ${renderer.quality}`;
    perf.acc = 0; perf.n = 0;
    if (game.state !== 'playing' || screen !== null) { perf.slow = 0; return; }
    perf.slow = fps < 40 ? perf.slow + 1 : 0;
    const i = TIERS.indexOf(renderer.quality);
    if (perf.slow >= 2 && i >= 0 && i < TIERS.length - 1) {
      perf.slow = 0;
      settings.quality = TIERS[i + 1];
      renderer.setQuality(settings.quality);
      applySettings(); saveSettings();
      hud.flashMessage(`Graphics set to ${settings.quality} for smoother play`, 3000);
    }
  }

  function frame() {
    requestAnimationFrame(frame);
    const dt = clock.getDelta();
    if (window.__noRender) return;   // debug: scripted checks drive the sim via __step
    trackPerf(dt);
    if (goRamp !== null) {
      if (game.state !== 'over') goRamp = null;              // retry/quit took over
      else {
        goRamp += dt;
        // 0.9 s held near-frozen, then a smoothstep back to real time by ~4.4 s
        const k = Math.max(0, Math.min(1, (goRamp - 0.9) / 3.5));
        game.timeScale = 0.1 + 0.9 * (k * k * (3 - 2 * k));
        if (k >= 1) goRamp = null;
      }
    }
    const paused = game.state === 'playing' && screen !== null;
    pad.poll(dt, screen !== null || game.state !== 'playing' ? 'menu' : 'play');
    game.update(paused ? 0 : dt);
    input.endFrame();
    renderer.render(dt, game.time);
  }
  frame();
}

boot().catch(e => {
  console.error(e);
  $('load-status').textContent = 'Failed to load: ' + e.message;
});
