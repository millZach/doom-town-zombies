"""fetch_oga.py — download CC0 / CC-BY sound packs from OpenGameArt.

Usage: python tools/audio/fetch_oga.py <outdir> <slug> [slug ...]

For each submission slug it records the licence and author into
<outdir>/_manifest.json and downloads every attached audio file / archive
into <outdir>/<slug>/.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (asset fetch; game audio build)"}


def get(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def strip(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def scrape(slug):
    h = get("https://opengameart.org/content/" + slug)
    m = re.search(r"field-name-field-art-licenses.*?</div>\s*</div>", h, re.S)
    lic = strip(m.group(0)).split("License(s):")[-1].strip() if m else "?"
    m = re.search(r'<h2[^>]*>(.*?)</h2>', h, re.S)
    title = strip(m.group(1)) if m else slug
    m = re.search(r'submitted by.*?<a[^>]*>([^<]+)</a>', h, re.S | re.I)
    author = m.group(1).strip() if m else "?"
    files = []
    for u in re.findall(r'https://opengameart\.org/sites/default/files/[^"\']+', h):
        u = u.replace("&amp;", "&")
        if "audio_preview" in u or "/styles/" in u:
            continue
        if re.search(r"\.(zip|7z|rar|wav|ogg|mp3|flac|tar\.gz)$", u, re.I):
            files.append(u)
    return {"slug": slug, "title": title, "author": author, "license": lic,
            "url": "https://opengameart.org/content/" + slug,
            "files": sorted(set(files))}


def main():
    out = sys.argv[1]
    slugs = sys.argv[2:]
    os.makedirs(out, exist_ok=True)
    mf_path = os.path.join(out, "_manifest.json")
    mf = json.load(open(mf_path)) if os.path.exists(mf_path) else {}
    for slug in slugs:
        try:
            info = scrape(slug)
        except Exception as e:
            print(f"{slug}: SCRAPE FAILED {e}")
            continue
        d = os.path.join(out, slug)
        os.makedirs(d, exist_ok=True)
        got = []
        for u in info["files"]:
            name = urllib.parse.unquote(u.rsplit("/", 1)[-1])
            p = os.path.join(d, name)
            if os.path.exists(p) and os.path.getsize(p) > 512:
                got.append(name)
                continue
            try:
                open(p, "wb").write(get(u, binary=True))
                got.append(name)
            except Exception as e:
                print(f"  {slug}/{name}: DL FAILED {e}")
        info["downloaded"] = got
        mf[slug] = info
        print(f"{slug} [{info['license']}] by {info['author']}: {len(got)} files")
    json.dump(mf, open(mf_path, "w"), indent=1)


if __name__ == "__main__":
    main()
