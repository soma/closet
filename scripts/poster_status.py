#!/usr/bin/env python3
"""Which poster sheets still need uploading to the Pages app.

    scripts/poster_status.py            human summary
    scripts/poster_status.py --json     the `files` list for begin_asset_upload (changed sheets only)
    scripts/poster_status.py --mark-uploaded   record the current sheets as uploaded

Compares the hashes in .cache/posters/sheets.json (written by make_posters.py)
with .cache/posters/uploaded.json (written by --mark-uploaded once the sheets
are on the page).
"""
import argparse, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache/posters"


def load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def changed(cache=CACHE):
    current, uploaded = load(cache / "sheets.json"), load(cache / "uploaded.json")
    return sorted(n for n, h in current.items() if uploaded.get(n) != h)


def files(names, cache=CACHE):
    return [{"key": n[:-5], "name": n, "type": "image/webp", "size": (cache / "sheets" / n).stat().st_size} for n in names]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--mark-uploaded", action="store_true")
    args = ap.parse_args(argv)
    if not (CACHE / "sheets.json").exists():
        print("poster_status: no sheets yet, run make posters", file=sys.stderr)
        return 1
    if args.mark_uploaded:
        (CACHE / "uploaded.json").write_text((CACHE / "sheets.json").read_text(encoding="utf-8"), encoding="utf-8")
        print("recorded the current sheets as uploaded")
        return 0
    names = changed()
    if args.json:
        print(json.dumps(files(names), separators=(",", ":")))
    elif names:
        print(f"{len(names)} sheet(s) to upload: " + ", ".join(names))
    else:
        print("all poster sheets are already uploaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
