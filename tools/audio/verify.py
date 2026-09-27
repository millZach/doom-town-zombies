"""verify.py — measure every shipped file and write docs/audio/report.md.

    python tools/audio/verify.py

For each file: duration, sample peak, true peak (ffmpeg ebur128), integrated
loudness, and a harshness figure — the fraction of spectral energy above
5 kHz. Stingers and voices with a high harshness figure are flagged, because
that is exactly what "sounds like a screech" measures as.

Also renders a spectrogram PNG per stinger and for a few zombie clips into
renders/audio/ so they can be inspected by eye.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
AUD = os.path.join(ROOT, "public/audio")
DOC = os.path.join(ROOT, "docs/audio")
REN = os.path.join(ROOT, "renders/audio")

# Harshness ceilings by group: above this the file is flagged in the report.
HARSH_MAX = {"stingers": 0.03, "voices": 0.12, "music": 0.03,
             "world": 0.45, "guns": 0.30, "impacts": 0.35,
             "handling": 0.45, "foley": 0.35, "ui": 0.50}

SPECTRA = [
    "stingers/round_end.ogg", "stingers/round_start.ogg",
    "stingers/hellround_start.ogg", "stingers/game_over.ogg",
    "voices/zombie_groan_1.ogg", "voices/zombie_groan_4.ogg",
    "voices/zombie_scream_1.ogg", "voices/zombie_attack_1.ogg",
    "voices/zombie_death_1.ogg", "voices/hellhound_growl_1.ogg",
    "voices/vox_max_ammo.ogg",
    "guns/gun_m1911_1.ogg", "guns/gun_remington870_1.ogg",
    "music/menu.ogg", "world/ambient_loop.ogg",
]


CACHE = os.path.join(ROOT, "tools/audio/_measurements.json")


def main():
    mf = json.load(open(os.path.join(AUD, "manifest.json"), encoding="utf-8"))
    # Measurements are cached by (file, size, mtime) so a run interrupted by the
    # machine running out of memory can simply be started again.
    cache = {}
    if os.path.exists(CACHE):
        try:
            cache = json.load(open(CACHE, encoding="utf-8"))
        except Exception:
            cache = {}
    rows = []
    done = 0
    try:
        for name in sorted(mf["sounds"]):
            rec = mf["sounds"][name]
            for f in rec["files"]:
                p = os.path.join(AUD, f)
                if not os.path.exists(p):
                    print("MISSING", f)
                    continue
                st = os.stat(p)
                key = f"{f}|{st.st_size}|{int(st.st_mtime)}"
                m = cache.get(key)
                if m is None:
                    m = lib.measure(p)
                    m = {k: (float(v) if isinstance(v, (int, float)) else v)
                         for k, v in m.items()}
                    cache[key] = m
                m = dict(m)
                grp = f.split("/")[0]
                m.update(name=name, file=f, group=grp, src=rec.get("src", ""),
                         loop=bool(rec.get("loop")))
                m["flag"] = m["harsh_5k"] > HARSH_MAX.get(grp, 0.5)
                rows.append(m)
            done += 1
            if done % 8 == 0:
                json.dump(cache, open(CACHE, "w", encoding="utf-8"))
            print(".", end="", flush=True)
    finally:
        json.dump(cache, open(CACHE, "w", encoding="utf-8"))
    print()

    os.makedirs(REN, exist_ok=True)
    for f in SPECTRA:
        p = os.path.join(AUD, f)
        if os.path.exists(p):
            lib.spectrogram(p, os.path.join(REN, f.replace("/", "_").replace(".ogg", ".png")))

    os.makedirs(DOC, exist_ok=True)
    total = sum(r["bytes"] for r in rows)
    clipped = [r for r in rows if (r["true_peak_db"] or -99) > -1.0]
    hot = [r for r in rows if (r["true_peak_db"] or -99) > -1.5]
    flagged = [r for r in rows if r["flag"]]

    groups = {}
    for r in rows:
        groups.setdefault(r["group"], []).append(r)

    with open(os.path.join(DOC, "report.md"), "w", encoding="utf-8") as fh:
        w = fh.write
        w("# Audio verification report\n\n")
        w(f"`public/audio/**` — {len(rows)} files across "
          f"{len(mf['sounds'])} sound names, {total / 1e6:.2f} MB total.\n\n")
        w("Measured with ffmpeg + numpy (`tools/audio/verify.py`). "
          "**Harsh** is the fraction of spectral energy above 5 kHz; it is the "
          "number that catches a screech. **LUFS** is ffmpeg's gated integrated "
          "loudness, **TP** its true peak.\n\n")

        w("## Summary\n\n")
        w(f"- Files over -1.5 dBTP: **{len(hot)}**"
          + (" — " + ", ".join(r["file"] for r in hot[:8]) if hot else " (none)") + "\n")
        w(f"- Files over -1.0 dBTP: **{len(clipped)}**"
          + (" — " + ", ".join(r["file"] for r in clipped[:8]) if clipped else " (none)") + "\n")
        w(f"- Files flagged harsh for their group: **{len(flagged)}**"
          + (" — " + ", ".join(r["file"] for r in flagged[:8]) if flagged else " (none)") + "\n\n")

        w("### Per-group loudness hierarchy\n\n")
        w("| group | files | median LUFS | max TP | median harsh | max harsh |\n")
        w("|---|---:|---:|---:|---:|---:|\n")
        for g in sorted(groups, key=lambda g: med(groups[g], "lufs")):
            rs = groups[g]
            w(f"| {g} | {len(rs)} | {med(rs, 'lufs'):.1f} | "
              f"{max((r['true_peak_db'] or -99) for r in rs):.2f} | "
              f"{med(rs, 'harsh_5k') * 100:.2f}% | "
              f"{max(r['harsh_5k'] for r in rs) * 100:.2f}% |\n")
        w("\n")

        w("## Every file\n\n")
        w("| sound | file | s | peak dBFS | TP dBTP | LUFS | >5 kHz | centroid Hz | source |\n")
        w("|---|---|---:|---:|---:|---:|---:|---:|---|\n")
        for r in rows:
            flag = " ⚠" if r["flag"] else ""
            w(f"| `{r['name']}` | {r['file']} | {r['duration']:.2f} | "
              f"{r['peak_db']:.2f} | "
              f"{(r['true_peak_db'] if r['true_peak_db'] is not None else float('nan')):.2f} | "
              f"{(r['lufs'] if r['lufs'] is not None else float('nan')):.1f} | "
              f"{r['harsh_5k'] * 100:.2f}%{flag} | {r['centroid']:.0f} | {r['src']} |\n")
    print("wrote", os.path.join(DOC, "report.md"))
    print(f"{len(rows)} files, {total / 1e6:.2f} MB, "
          f"{len(clipped)} over -1 dBTP, {len(flagged)} harsh-flagged")


def med(rs, k):
    xs = sorted(r[k] for r in rs if r[k] is not None)
    return xs[len(xs) // 2] if xs else float("nan")


if __name__ == "__main__":
    main()
