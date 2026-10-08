#!/usr/bin/env python3
"""Pack the film posters into sprite sheets for the Pages app.

    scripts/make_posters.py [--delay 0.5] [--sheets-only]

Pages blocks hotlinked images, so the posters are uploaded to the page as a
few dozen sprite sheets instead of 1466 files. Stage 1 downloads each poster
once (polite delay, honest user agent, stops at the first 403/429), centre
crops it to 2:3 and stores a small thumbnail under .cache/posters/thumbs/.
Stage 2 packs the thumbnails into WebP sheets under .cache/posters/sheets/ and
writes data/posters.json (slug -> [sheet, column, row]); the sheets stay out of
git, the small map is committed.
"""
import argparse, io, json, pathlib, sys, time, urllib.error, urllib.request

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache/posters"
USER_AGENT = "closet-explorer/1.0 (hobby film club project; stops on 403/429)"
THUMB_W, THUMB_H = 160, 240
COLS, ROWS = 8, 8
PER_SHEET = COLS * ROWS


class Blocked(Exception):
    pass


def thumb(data):
    """Centre crop to 2:3 (what the app's object-fit: cover shows) and shrink."""
    im = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = im.size
    if w * THUMB_H > h * THUMB_W:               # too wide: crop the sides
        nw = round(h * THUMB_W / THUMB_H)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:                                       # too tall: crop top and bottom
        nh = round(w * THUMB_H / THUMB_W)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return im.resize((THUMB_W, THUMB_H), Image.Resampling.LANCZOS)


def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        return urllib.request.urlopen(req, timeout=30).read()
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise Blocked(f"{e.code} for {url}; stopping. Thumbnails so far are kept, rerun later to continue.")
        raise


def films(data):
    cols = data["films"]["cols"]
    return [(r[cols.index("film_slug")], r[cols.index("poster_url")]) for r in data["films"]["rows"]]


def fetch_thumbs(items, delay, cache=CACHE, get=download):
    out = cache / "thumbs"
    out.mkdir(parents=True, exist_ok=True)
    failed = []
    for n, (slug, url) in enumerate(items, 1):
        target = out / f"{slug}.png"
        if target.exists() or not url:
            continue
        time.sleep(delay)
        try:
            thumb(get(url)).save(target, "PNG")
        except Blocked:
            raise
        except Exception as e:                  # one bad image must not stop the run
            failed.append((slug, str(e)))
        if n % 100 == 0:
            print(f"{n}/{len(items)}", flush=True)
    return failed


def pack(items, cache=CACHE):
    """Sheets of COLS x ROWS thumbnails in dataset order. Returns the map."""
    have = [(s, cache / "thumbs" / f"{s}.png") for s, _ in items if (cache / "thumbs" / f"{s}.png").exists()]
    sheets = cache / "sheets"
    sheets.mkdir(parents=True, exist_ok=True)
    for old in sheets.glob("sheet-*.webp"):
        old.unlink()
    mapping = {}
    for start in range(0, len(have), PER_SHEET):
        chunk = have[start:start + PER_SHEET]
        index = start // PER_SHEET
        sheet = Image.new("RGB", (COLS * THUMB_W, ROWS * THUMB_H), (14, 12, 10))
        for k, (slug, path) in enumerate(chunk):
            col, row = k % COLS, k // COLS
            sheet.paste(Image.open(path), (col * THUMB_W, row * THUMB_H))
            mapping[slug] = [index, col, row]
        sheet.save(sheets / f"sheet-{index:02d}.webp", "WEBP", quality=72, method=6)
    return {"cols": COLS, "rows": ROWS, "map": mapping}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--sheets-only", action="store_true")
    args = ap.parse_args(argv)
    items = films(json.loads((ROOT / "data/closet.json").read_text(encoding="utf-8")))
    if not args.sheets_only:
        try:
            failed = fetch_thumbs(items, args.delay)
        except Blocked as e:
            print(f"make_posters: {e}", file=sys.stderr)
            return 2
        for slug, why in failed:
            print(f"failed: {slug}: {why}", file=sys.stderr)
    result = pack(items)
    (ROOT / "data/posters.json").write_text(json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8")
    total = sum(p.stat().st_size for p in (CACHE / "sheets").glob("sheet-*.webp"))
    print(f"{len(result['map'])} of {len(items)} posters in {-(-len(result['map']) // PER_SHEET)} sheets, {total // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
