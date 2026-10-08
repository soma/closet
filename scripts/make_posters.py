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
import argparse, hashlib, io, json, pathlib, sys, time, urllib.error, urllib.request

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


def slot(pos):
    return pos[0] * PER_SHEET + pos[2] * COLS + pos[1]


def at(n):
    return [n // PER_SHEET, n % COLS, (n % PER_SHEET) // COLS]


def assign(wanted, previous):
    """Stable slots: a poster that already has one keeps it (so an update only
    changes the sheets that gained posters), new posters take the lowest free
    slots, posters no longer wanted free theirs. `previous` is the old
    data/posters.json content, ignored when the sheet geometry differs."""
    old = {}
    if previous and (previous.get("cols"), previous.get("rows")) == (COLS, ROWS):
        old = previous.get("map", {})
    wanted_set = set(wanted)
    kept = {s: pos for s, pos in old.items() if s in wanted_set}
    used = {slot(p) for p in kept.values()}
    n = 0
    for s in wanted:
        if s in kept:
            continue
        while n in used:
            n += 1
        kept[s] = at(n)
        used.add(n)
    return kept


def pack(items, cache=CACHE, previous=None):
    """Sheets of COLS x ROWS thumbnails. Returns the map; writes the sheets and
    a manifest of their content hashes (sheets.json) so uploads can be limited
    to what changed."""
    wanted = [s for s, _ in items if (cache / "thumbs" / f"{s}.png").exists()]
    mapping = assign(wanted, previous)
    sheets = cache / "sheets"
    sheets.mkdir(parents=True, exist_ok=True)
    for old in sheets.glob("sheet-*.webp"):
        old.unlink()
    count = (max((slot(p) for p in mapping.values()), default=-1) // PER_SHEET) + 1
    manifest = {}
    for index in range(count):
        sheet = Image.new("RGB", (COLS * THUMB_W, ROWS * THUMB_H), (14, 12, 10))
        for slug, pos in mapping.items():
            if pos[0] == index:
                with Image.open(cache / "thumbs" / f"{slug}.png") as im:
                    sheet.paste(im, (pos[1] * THUMB_W, pos[2] * THUMB_H))
        name = f"sheet-{index:02d}.webp"
        sheet.save(sheets / name, "WEBP", quality=72, method=6)
        manifest[name] = hashlib.sha1((sheets / name).read_bytes()).hexdigest()
    (cache / "sheets.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
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
    posters = ROOT / "data/posters.json"
    previous = json.loads(posters.read_text(encoding="utf-8")) if posters.exists() else None
    result = pack(items, previous=previous)
    (ROOT / "data/posters.json").write_text(json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8")
    total = sum(p.stat().st_size for p in (CACHE / "sheets").glob("sheet-*.webp"))
    print(f"{len(result['map'])} of {len(items)} posters in {-(-len(result['map']) // PER_SHEET)} sheets, {total // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
