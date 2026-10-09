#!/usr/bin/env python3
"""Fetch IMDb ratings for the films in data/closet.json from IMDb's own dataset.

    scripts/imdb_ratings.py [--refresh]

Downloads title.ratings.tsv.gz from https://datasets.imdbws.com/ (one request, cached
for a day under .cache/imdb/), keeps the ids that appear as imdb_id in
data/closet.json and writes data/imdb_ratings.json:
    {"as_of": "YYYY-MM-DD", "ratings": {"tt0050083": [8.9, 855123], ...}}

That file is git-ignored on purpose: IMDb offers the dataset for personal and
non-commercial use and its terms restrict republishing, so the ratings go only into
the Pages upload (scripts/build.py), never into the public repository. Delete the
file and rebuild to switch the feature off. Anything unexpected (a failed download, a
truncated file, another header) aborts and leaves the previous file untouched.
"""
import argparse, datetime, email.utils, gzip, json, pathlib, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"
USER_AGENT = "closet-explorer/1.0 (hobby film club project)"
HEADER = "tconst\taverageRating\tnumVotes"
MAX_AGE = 24 * 3600


class RatingsError(Exception):
    pass


def read_ratings(raw, wanted):
    """Return ({id: [rating, votes]}, {"skipped": n}) for the wanted ids in a gzip of the dataset."""
    try:
        text = gzip.decompress(raw).decode("utf-8")
    except (OSError, EOFError, UnicodeDecodeError) as e:
        raise RatingsError(f"not a complete gzip of the dataset: {e}")
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != HEADER:
        raise RatingsError(f"unexpected header {lines[0][:60]!r}, expected {HEADER!r}")
    wanted = set(wanted)
    out, skipped = {}, 0
    for n, line in enumerate(lines[1:], 2):
        if not line:
            continue
        parts = line.rstrip("\r").split("\t")
        if len(parts) != 3:                      # a row of the wrong shape means the file is not what we expect
            raise RatingsError(f"malformed row {n}: {len(parts)} fields instead of 3")
        if parts[0] not in wanted:
            continue
        try:
            rating, votes = float(parts[1]), int(parts[2])
        except ValueError:
            skipped += 1
            continue
        if not (1.0 <= rating <= 10.0) or votes < 1:
            skipped += 1
            continue
        out[parts[0]] = [round(rating, 1), votes]
    return out, {"skipped": skipped}


def download(opener=urllib.request.urlopen):
    req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    with opener(req, timeout=120) as r:
        body = r.read()
        stamp = r.headers.get("Last-Modified")
        expected = r.headers.get("Content-Length")
    if expected and int(expected) != len(body):
        raise RatingsError(f"truncated download: {len(body)} of {expected} bytes")
    as_of = email.utils.parsedate_to_datetime(stamp).date().isoformat() if stamp else datetime.date.today().isoformat()
    return body, as_of


def get_dataset(cache, refresh=False, opener=urllib.request.urlopen, now=time.time):
    """The dataset bytes and their 'as of' date, from the cache when it is under a day old."""
    gz, meta = cache / "title.ratings.tsv.gz", cache / "as_of.txt"
    if not refresh and gz.exists() and meta.exists() and now() - gz.stat().st_mtime < MAX_AGE:
        return gz.read_bytes(), meta.read_text(encoding="utf-8").strip()
    body, as_of = download(opener)
    read_ratings(body, [])                       # shape check before it replaces the cache
    cache.mkdir(parents=True, exist_ok=True)
    gz.write_bytes(body)
    meta.write_text(as_of + "\n", encoding="utf-8")
    return body, as_of


def update(root=ROOT, refresh=False, opener=urllib.request.urlopen, now=time.time):
    data = json.loads((root / "data/closet.json").read_text(encoding="utf-8"))
    cols = data["films"]["cols"]
    ids = {r[cols.index("imdb_id")] for r in data["films"]["rows"] if r[cols.index("imdb_id")]}
    raw, as_of = get_dataset(root / ".cache/imdb", refresh, opener, now)
    ratings, stats = read_ratings(raw, ids)
    target = root / "data/imdb_ratings.json"
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps({"as_of": as_of, "ratings": dict(sorted(ratings.items()))}, separators=(",", ":")) + "\n", encoding="utf-8")
    tmp.replace(target)
    return {"as_of": as_of, "ids": len(ids), "rated": len(ratings), "unrated": len(ids) - len(ratings), "skipped": stats["skipped"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args(argv)
    try:
        s = update(refresh=args.refresh)
    except (RatingsError, urllib.error.URLError, OSError) as e:
        print(f"imdb_ratings: {e}\nNothing written; the previous data/imdb_ratings.json (if any) is unchanged.", file=sys.stderr)
        return 1
    print(f"IMDb ratings as of {s['as_of']}: {s['rated']} of {s['ids']} films rated, {s['unrated']} without a rating"
          + (f", {s['skipped']} invalid rows skipped" if s["skipped"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
