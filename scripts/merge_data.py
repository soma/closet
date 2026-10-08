#!/usr/bin/env python3
"""Merge new closet visits into data/closet.json.

    scripts/merge_data.py NEW.json [--overwrite]
    scripts/merge_data.py DIR_WITH_CSVS [--overwrite]   # visits.csv picks.csv films.csv

NEW.json uses the same columnar shape as data/closet.json (tables visits,
picks, films, each {cols, rows}); any table may be omitted. Existing rows win
unless --overwrite. The merged dataset is validated as a whole and only then
written. Run scripts/build.py afterwards to regenerate the HTML.
"""
import argparse, csv, collections, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data/closet.json"
EXCLUDED = ROOT / "data/excluded_lists.json"   # {"slugs": [...]}: Letterboxd lists that are not visits
KEYS = {"visits": "visit_slug", "films": "film_slug", "picks": ("visit_slug", "pick_order")}
INT_COLS = {"num_films", "pick_order", "film_year", "runtime_min", "rating_count"}
FLOAT_COLS = {"avg_rating"}


IMDB_RE = re.compile(r"^tt\d{7,10}$")


class MergeError(Exception):
    pass


def objects(table):
    return [dict(zip(table["cols"], row)) for row in table["rows"]]


def key_of(table, row):
    k = KEYS[table]
    return tuple(row[c] for c in k) if isinstance(k, tuple) else row[k]


def read_csv_dir(path):
    out = {}
    for name in KEYS:
        f = path / f"{name}.csv"
        if not f.exists():
            continue
        with f.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            cols = reader.fieldnames
            rows = []
            for r in reader:
                rows.append([convert(c, r[c]) for c in cols])
        out[name] = {"cols": cols, "rows": rows}
    return out


def convert(col, value):
    if value == "":
        return None if col in INT_COLS | FLOAT_COLS else ""
    if col in INT_COLS:
        return int(value)
    if col in FLOAT_COLS:
        return float(value)
    return value


def validate(data):
    problems = []
    visits = objects(data["visits"])
    films = objects(data["films"])
    picks = objects(data["picks"])
    for table, rows in (("visits", visits), ("films", films), ("picks", picks)):
        seen = set()
        for r in rows:
            k = key_of(table, r)
            if k in seen:
                problems.append(f"duplicate {table} key {k!r}")
            seen.add(k)
    for f in films:
        if f.get("imdb_id") and not IMDB_RE.match(f["imdb_id"]):
            problems.append(f"film {f['film_slug']!r}: invalid imdb_id {f['imdb_id']!r}")
    visit_slugs = {v["visit_slug"] for v in visits}
    film_slugs = {f["film_slug"] for f in films}
    by_visit = collections.defaultdict(list)
    for p in picks:
        if p["visit_slug"] not in visit_slugs:
            problems.append(f"pick references unknown visit {p['visit_slug']!r}")
        if p["film_slug"] not in film_slugs:
            problems.append(f"pick references unknown film {p['film_slug']!r}")
        by_visit[p["visit_slug"]].append(p["pick_order"])
    for slug, orders in by_visit.items():
        if sorted(orders) != list(range(1, len(orders) + 1)):
            problems.append(f"visit {slug!r}: pick_order not contiguous from 1: {sorted(orders)}")
    for v in visits:
        n = len(by_visit.get(v["visit_slug"], []))
        if v["num_films"] != n:
            problems.append(f"visit {v['visit_slug']!r}: num_films={v['num_films']} but {n} picks")
    return problems


VISITOR_RE = re.compile(r"^(.*?)(?:['\u2019]s?)?(?: Criterion)? Closet Picks$")


def clean_visitor(visitor):
    """The fetcher sometimes leaves the whole list title as the visitor
    ("Danny McBride's Closet Picks"): reduce it to the name."""
    m = VISITOR_RE.match(visitor or "")
    return m.group(1).strip() if m and m.group(1).strip() else visitor


def prepare(incoming, excluded=(), existing_films=()):
    """Drop lists that are not visits (with their picks) and tidy visitor names.
    Of the incoming films, only those the exclusion orphaned are dropped: picked
    by an excluded list, and by no remaining incoming pick and no existing pick
    (`existing_films`). Every other incoming film, for example a film-only
    correction, is kept. Only the dataset tables are considered (`_meta` etc. are
    ignored). Returns (incoming copy, dropped slugs)."""
    out = {k: {"cols": list(v["cols"]), "rows": [list(r) for r in v["rows"]]} for k, v in incoming.items() if k in KEYS}
    excluded = set(excluded)
    dropped = []
    if "visits" in out:
        cols = out["visits"]["cols"]
        si, vi = cols.index("visit_slug"), cols.index("visitor") if "visitor" in cols else None
        kept = []
        for r in out["visits"]["rows"]:
            if r[si] in excluded:
                dropped.append(r[si])
                continue
            if vi is not None:
                r[vi] = clean_visitor(r[vi])
            kept.append(r)
        out["visits"]["rows"] = kept
    if dropped and "picks" in out:
        pcols = out["picks"]["cols"]
        pv, pf = pcols.index("visit_slug"), pcols.index("film_slug")
        gone = {r[pf] for r in out["picks"]["rows"] if r[pv] in excluded}
        out["picks"]["rows"] = [r for r in out["picks"]["rows"] if r[pv] not in excluded]
        if "films" in out:
            orphaned = gone - {r[pf] for r in out["picks"]["rows"]} - set(existing_films)
            fs = out["films"]["cols"].index("film_slug")
            out["films"]["rows"] = [r for r in out["films"]["rows"] if r[fs] not in orphaned]
    return out, dropped


def merge(existing, incoming, overwrite=False, excluded=()):
    """Return (merged, stats). Raises MergeError if the result is invalid.

    Films and visits merge row by row. Picks merge per visit: an incoming
    visit that already exists is skipped whole, or with overwrite has all its
    picks replaced, so a visit never ends up with a mix of old and new picks.
    """
    pcols = existing["picks"]["cols"]
    in_use = {r[pcols.index("film_slug")] for r in existing["picks"]["rows"]}
    incoming, dropped = prepare(incoming, excluded, in_use)
    merged = {k: {"cols": list(v["cols"]), "rows": [list(r) for r in v["rows"]]}
              for k, v in existing.items() if k != "_meta"}
    for name in KEYS:
        inc = incoming.get(name)
        if inc and set(inc["cols"]) != set(merged[name]["cols"]):
            raise MergeError(f"{name}: columns differ from dataset: {inc['cols']} vs {merged[name]['cols']}")
    for name in KEYS:
        inc = incoming.get(name)
        if not inc:
            continue
        seen = set()
        for row in objects(inc):
            k = key_of(name, row)
            if k in seen:
                raise MergeError(f"incoming {name} has duplicate key {k!r}")
            seen.add(k)
    existing_visits = {r["visit_slug"] for r in objects(merged["visits"])}
    stats = {}
    for name in ("films", "visits"):
        stats[name] = {"added": 0, "skipped": 0, "replaced": 0}
        inc = incoming.get(name)
        if not inc:
            continue
        cols = merged[name]["cols"]
        index = {key_of(name, dict(zip(cols, r))): i for i, r in enumerate(merged[name]["rows"])}
        for row in objects(inc):
            new_row = [row[c] for c in cols]
            k = key_of(name, row)
            if k not in index:
                merged[name]["rows"].append(new_row)
                index[k] = len(merged[name]["rows"]) - 1
                stats[name]["added"] += 1
            elif overwrite:
                merged[name]["rows"][index[k]] = new_row
                stats[name]["replaced"] += 1
            else:
                stats[name]["skipped"] += 1
    stats["picks"] = {"added": 0, "skipped": 0, "replaced": 0}
    inc = incoming.get("picks")
    if inc:
        cols = merged["picks"]["cols"]
        groups = collections.OrderedDict()
        for row in objects(inc):
            groups.setdefault(row["visit_slug"], []).append([row[c] for c in cols])
        vi = cols.index("visit_slug")
        for slug, rows in groups.items():
            if slug in existing_visits and not overwrite:
                stats["picks"]["skipped"] += len(rows)
                continue
            if slug in existing_visits:
                merged["picks"]["rows"] = [r for r in merged["picks"]["rows"] if r[vi] != slug]
                stats["picks"]["replaced"] += len(rows)
            else:
                stats["picks"]["added"] += len(rows)
            merged["picks"]["rows"].extend(rows)
    problems = validate(merged)
    if problems:
        raise MergeError("merged dataset is invalid:\n  " + "\n  ".join(problems[:20]))
    merged["_meta"] = dict(existing.get("_meta", {}))
    merged["_meta"]["row_counts"] = {k: len(merged[k]["rows"]) for k in KEYS}
    stats["excluded_lists"] = dropped
    return merged, stats


def dump(data):
    out = ["{"]
    keys = list(data)
    for i, k in enumerate(keys):
        v = data[k]
        if k == "_meta":
            out.append(f'"{k}": {json.dumps(v, ensure_ascii=False)}')
        else:
            out.append(f'"{k}": {{"cols": {json.dumps(v["cols"], ensure_ascii=False)}, "rows": [')
            out.append(",\n".join(json.dumps(r, ensure_ascii=False) for r in v["rows"]))
            out.append("]}")
        if i < len(keys) - 1:
            out[-1] += ","
    out.append("}")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    src = pathlib.Path(args.source)
    incoming = read_csv_dir(src) if src.is_dir() else json.loads(src.read_text(encoding="utf-8"))
    existing = json.loads(DATA.read_text(encoding="utf-8"))
    excluded = json.loads(EXCLUDED.read_text(encoding="utf-8"))["slugs"] if EXCLUDED.exists() else []
    try:
        merged, stats = merge(existing, incoming, args.overwrite, excluded)
    except MergeError as e:
        print(f"merge_data: {e}", file=sys.stderr)
        return 1
    DATA.write_text(dump(merged), encoding="utf-8")
    for name, s in stats.items():
        if name == "excluded_lists":
            if s:
                print("excluded (not visits): " + ", ".join(s))
            continue
        print(f"{name}: {s['added']} added, {s['skipped']} skipped, {s['replaced']} replaced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
