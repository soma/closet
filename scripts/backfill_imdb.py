#!/usr/bin/env python3
"""Fill blank imdb_id values in data/closet.json from Wikidata.

    scripts/backfill_imdb.py [--overwrite] [--delay 1]

Wikidata stores both the Letterboxd film slug (P6127) and the IMDb id (P345),
so matches are exact on the slug the dataset already holds: no title or year
guessing. A slug with several different IMDb ids is left blank and reported.
Existing ids are kept unless --overwrite. A failed request aborts and writes
nothing. Run scripts/build.py afterwards.
"""
import argparse, json, re, sys, time, urllib.error, urllib.parse, urllib.request

import merge_data

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "closet-explorer/1.0 (hobby film club project)"
IMDB_RE = re.compile(r"^tt\d{7,10}$")
CHUNK = 150


def query_chunk(slugs):
    values = " ".join('"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"' for s in slugs)
    q = f"SELECT ?lb ?imdb WHERE {{ VALUES ?lb {{ {values} }} ?f wdt:P6127 ?lb; wdt:P345 ?imdb }}"
    req = urllib.request.Request(ENDPOINT + "?format=json&query=" + urllib.parse.quote(q),
                                 headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def polite_fetch(slugs, fetch=query_chunk, sleep=time.sleep, attempts=4):
    """On 429, wait as long as the server asks (default 65 s) and try again."""
    for attempt in range(attempts):
        try:
            return fetch(slugs)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == attempts - 1:
                raise
            wait = e.headers.get("Retry-After") if e.headers else None
            wait = int(wait) if wait and wait.isdigit() else 65
            print(f"rate limited by Wikidata, waiting {wait}s", file=sys.stderr)
            sleep(wait)


def lookup(slugs, fetch=query_chunk, delay=1.0, sleep=time.sleep):
    """Return ({slug: set(ids)}, [malformed (slug, id)])."""
    found, malformed = {}, []
    for i in range(0, len(slugs), CHUNK):
        if i:
            sleep(delay)
        for b in polite_fetch(slugs[i:i + CHUNK], fetch, sleep)["results"]["bindings"]:
            slug, imdb = b["lb"]["value"], b["imdb"]["value"]
            if IMDB_RE.match(imdb):
                found.setdefault(slug, set()).add(imdb)
            else:
                malformed.append((slug, imdb))
    return found, malformed


def backfill(data, found, overwrite=False):
    """Return (new data, stats). Mutates nothing."""
    out = json.loads(json.dumps(data))
    cols = out["films"]["cols"]
    si, ii = cols.index("film_slug"), cols.index("imdb_id")
    stats = {"filled": 0, "already_set": 0, "conflicting": [], "missing": 0}
    for row in out["films"]["rows"]:
        ids = found.get(row[si], set())
        if len(ids) > 1:
            stats["conflicting"].append(row[si])
        elif not ids:
            stats["missing"] += 1
        elif row[ii] and not overwrite:
            stats["already_set"] += 1
        else:
            row[ii] = next(iter(ids))
            stats["filled"] += 1
    return out, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--delay", type=float, default=5.0)
    args = ap.parse_args(argv)
    data = json.loads(merge_data.DATA.read_text(encoding="utf-8"))
    cols = data["films"]["cols"]
    if "imdb_id" not in cols:
        print("backfill_imdb: the dataset has no imdb_id column", file=sys.stderr)
        return 1
    si, ii = cols.index("film_slug"), cols.index("imdb_id")
    # only ask about films that still lack an id, so an update is one small request
    slugs = [r[si] for r in data["films"]["rows"] if args.overwrite or not r[ii]]
    if not slugs:
        print("nothing to fill: every film already has an imdb_id")
        return 0
    try:
        found, malformed = lookup(slugs, delay=args.delay)
    except Exception as e:
        print(f"backfill_imdb: request failed, nothing written: {e}", file=sys.stderr)
        return 2
    out, stats = backfill(data, found, args.overwrite)
    problems = merge_data.validate(out)
    if problems:
        print("backfill_imdb: result invalid, nothing written:\n  " + "\n  ".join(problems[:10]), file=sys.stderr)
        return 1
    merge_data.DATA.write_text(merge_data.dump(out), encoding="utf-8")
    print(f"filled {stats['filled']}, kept {stats['already_set']} already set, "
          f"{len(stats['conflicting'])} conflicting (left blank), {stats['missing']} not on Wikidata, {len(malformed)} malformed ignored")
    for s in stats["conflicting"][:10]:
        print("  conflict:", s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
