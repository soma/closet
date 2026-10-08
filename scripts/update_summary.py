#!/usr/bin/env python3
"""What a data update changed, compared with the last commit.

    scripts/update_summary.py
"""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import poster_status, stage_status  # noqa: E402


def keys(data, table, col):
    cols = data[table]["cols"]
    return {r[cols.index(col)] for r in data[table]["rows"]}


def summarize(old, new):
    films = new["films"]
    cols = films["cols"]
    added = keys(new, "films", "film_slug") - (keys(old, "films", "film_slug") if old else set())
    rows = {r[cols.index("film_slug")]: dict(zip(cols, r)) for r in films["rows"]}
    gaps = {}
    for field in ("imdb_id", "runtime_min", "avg_rating", "directors", "poster_url"):
        gaps[field] = sorted(s for s in added if rows[s].get(field) in (None, ""))
    return {
        "new_visits": len(keys(new, "visits", "visit_slug") - (keys(old, "visits", "visit_slug") if old else set())),
        "new_films": len(added),
        "new_picks": len(new["picks"]["rows"]) - (len(old["picks"]["rows"]) if old else 0),
        "missing_fields_on_new_films": gaps,
        "totals": {t: len(new[t]["rows"]) for t in ("visits", "picks", "films")},
    }


def main():
    new = json.loads((ROOT / "data/closet.json").read_text(encoding="utf-8"))
    shown = subprocess.run(["git", "show", "HEAD:data/closet.json"], cwd=ROOT, capture_output=True, text=True)
    old = json.loads(shown.stdout) if shown.returncode == 0 else None
    s = summarize(old, new)
    print(f"new visits {s['new_visits']}, new films {s['new_films']}, new picks {s['new_picks']}  (totals {s['totals']})")
    for field, slugs in s["missing_fields_on_new_films"].items():
        if slugs:
            print(f"  new films missing {field}: {len(slugs)} e.g. {', '.join(slugs[:5])}")
    names = poster_status.changed() if (poster_status.CACHE / "sheets.json").exists() else []
    print("poster sheets to upload: " + (", ".join(names) if names else "none"))
    print("Pages app: " + ("needs staging" if stage_status.needs_staging() else "staged and current"))
    print("next: ask Claude to run the update-closet skill to stage and upload (nothing is pushed or published)")


if __name__ == "__main__":
    main()
