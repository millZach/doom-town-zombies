/**
 * el_lib.mjs — shared ElevenLabs helpers for the audio build.
 *
 * The API key is read from .env.local at call time and is NEVER printed,
 * logged or written to any file. Nothing here echoes process.env.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
export const RAW = path.join(ROOT, 'tools/audio/_raw');
export const LOG = path.join(ROOT, 'tools/audio/elevenlabs_log.csv');

/** Read ELEVENLABS_API_KEY out of .env.local. Never logged. */
export function apiKey() {
  const p = path.join(ROOT, '.env.local');
  const txt = fs.readFileSync(p, 'utf8');
  const m = txt.match(/^\s*ELEVENLABS_API_KEY\s*=\s*(.+)\s*$/m);
  if (!m) throw new Error('ELEVENLABS_API_KEY not found in .env.local');
  return m[1].trim().replace(/^["']|["']$/g, '');
}

async function req(url, opts = {}) {
  const res = await fetch(url, {
    ...opts,
    headers: { 'xi-api-key': apiKey(), ...(opts.headers || {}) },
  });
  return res;
}

/** { used, limit, remaining } */
export async function balance() {
  const res = await req('https://api.elevenlabs.io/v1/user/subscription');
  if (!res.ok) throw new Error('subscription check failed: ' + res.status + ' ' + (await res.text()).slice(0, 200));
  const j = await res.json();
  return { used: j.character_count, limit: j.character_limit, remaining: j.character_limit - j.character_count };
}

export async function listVoices() {
  const res = await req('https://api.elevenlabs.io/v1/voices');
  if (!res.ok) throw new Error('voices failed: ' + res.status);
  const j = await res.json();
  return j.voices.map((v) => ({
    id: v.voice_id,
    name: v.name,
    labels: v.labels,
    desc: (v.description || '').slice(0, 120),
  }));
}

function appendLog(row) {
  if (!fs.existsSync(LOG)) {
    fs.writeFileSync(LOG, 'timestamp,kind,name,file,seconds,credits,prompt\n');
  }
  const esc = (s) => '"' + String(s).replace(/"/g, '""') + '"';
  fs.appendFileSync(LOG, [
    new Date().toISOString(), row.kind, row.name, row.file, row.seconds, row.credits, esc(row.prompt || ''),
  ].join(',') + '\n');
}

/** Credits already spent according to our own log. */
export function spentFromLog() {
  if (!fs.existsSync(LOG)) return 0;
  return fs.readFileSync(LOG, 'utf8').split('\n').slice(1).filter(Boolean)
    .reduce((a, l) => {
      const parts = l.split(',');
      return a + (Number(parts[6]) || 0);   // the measured column
    }, 0);
}

/**
 * Generate one sound effect. Returns the credits charged (estimated: 40/sec).
 * Skips (and returns 0) if the output file already exists.
 */
export async function sfx({ name, file, prompt, seconds, influence = 0.45, loop = false }) {
  const out = path.join(RAW, file);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  if (fs.existsSync(out) && fs.statSync(out).size > 2000) return 0;
  const body = {
    text: prompt,
    duration_seconds: Number(seconds.toFixed(2)),
    prompt_influence: influence,
  };
  if (loop) body.loop = true;
  const res = await req('https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_128', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const t = (await res.text()).slice(0, 300);
    throw new Error(`sfx ${name} failed ${res.status}: ${t}`);
  }
  const buf = Buffer.from(await res.arrayBuffer());
  fs.writeFileSync(out, buf);
  // Logged at the documented list price (40 credits/second). The account's own
  // character_count lags behind by a few seconds, so it cannot be sampled
  // per-call; the run reconciles against it at the end instead.
  const credits = Math.round(seconds * 40);
  appendLog({ kind: 'sfx', name, file, seconds, credits, prompt });
  return credits;
}

/** Credits the account actually moved by since the last call (falls back to est). */
let _lastUsed = null;
export async function charged(estimate) {
  try {
    const b = await balance();
    const d = _lastUsed == null ? null : b.used - _lastUsed;
    _lastUsed = b.used;
    return d == null || d < 0 ? Math.round(estimate) : d;
  } catch (e) {
    return Math.round(estimate);
  }
}
export async function primeUsage() { const b = await balance(); _lastUsed = b.used; return b; }

/** Text-to-speech. Credits = characters. */
export async function tts({ name, file, text, voiceId, settings = {} }) {
  const out = path.join(RAW, file);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  if (fs.existsSync(out) && fs.statSync(out).size > 2000) return 0;
  const res = await req(
    `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}?output_format=mp3_44100_128`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        text,
        model_id: 'eleven_multilingual_v2',
        voice_settings: { stability: 0.4, similarity_boost: 0.75, style: 0.5, ...settings },
      }),
    },
  );
  if (!res.ok) {
    const t = (await res.text()).slice(0, 300);
    throw new Error(`tts ${name} failed ${res.status}: ${t}`);
  }
  fs.writeFileSync(out, Buffer.from(await res.arrayBuffer()));
  const credits = text.length;
  appendLog({ kind: 'tts', name, file, seconds: '', credits, prompt: text });
  return credits;
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
