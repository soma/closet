#!/usr/bin/env python3
"""Re-read film fields from the pages the fetcher already cached (no network).

    scripts/reparse_films.py [--fields top_cast,spoken_languages] [--overwrite]

For every film in data/closet.json that has a cached page in
.cache/letterboxd/film_<slug>.html, recompute the requested fields with
fetch_letterboxd.parse_film. Blank fields are filled; with --overwrite
non-blank ones are replaced too. Films without a cached page are untouched.
Use it after improving parse_film instead of fetching the pages again.
"""
import argparse, json, sys

import fetch_letterboxd as fl
import merge_data


def reparse(data, cache, fields, overwrite=False, parse=fl.parse_film):
    """Return (new data, {"updated": n, "films": n, "no_page": n}). Mutates nothing."""
    out = json.loads(json.dumps(data))
    cols = out["films"]["cols"]
    unknown = [f for f in fields if f not in cols]
    if unknown:
        raise ValueError("unknown field(s): " + ", ".join(unknown))
    idx = {c: i for i, c in enumerate(cols)}
    stats = {"updated": 0, "films": 0, "no_page": 0}
    for row in out["films"]["rows"]:
        path = cache / f"film_{row[idx['film_slug']]}.html"
        if not path.exists():
            stats["no_page"] += 1
            continue
        parsed = parse(row[idx["film_slug"]], row[idx["film_title"]], row[idx["film_year"]], path.read_text(encoding="utf-8"))
        changed = False
        for f in fields:
            new = parsed.get(f)
            if new in (None, "") or new == row[idx[f]]:
                continue
            if row[idx[f]] in (None, "") or overwrite:
                row[idx[f]] = new
                stats["updated"] += 1
                changed = True
        stats["films"] += changed
    return out, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fields", default="top_cast,spoken_languages")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    data = json.loads(merge_data.DATA.read_text(encoding="utf-8"))
    try:
        out, stats = reparse(data, fl.CACHE, [f.strip() for f in args.fields.split(",") if f.strip()], args.overwrite)
    except ValueError as e:
        print(f"reparse_films: {e}", file=sys.stderr)
        return 1
    problems = merge_data.validate(out)
    if problems:
        print("reparse_films: result invalid, nothing written:\n  " + "\n  ".join(problems[:10]), file=sys.stderr)
        return 1
    merge_data.DATA.write_text(merge_data.dump(out), encoding="utf-8")
    print(f"{stats['updated']} field value(s) updated on {stats['films']} films; {stats['no_page']} films have no cached page")
    return 0


if __name__ == "__main__":
    sys.exit(main())
