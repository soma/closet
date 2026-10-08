#!/usr/bin/env python3
"""Fetch closet visits missing from data/closet.json from letterboxd.com/closetpicks.

    scripts/fetch_letterboxd.py [--out new.json] [--delay 3] [--max-visits N]

Uses browser-style headers and an in-memory cookie session, waits between
requests, and caches list and film pages under .cache/letterboxd/ so a
rerun skips them (the lists index is always refetched, and a page that fails
to parse is dropped from the cache). It stops at the first 403 or 429 instead of retrying. It writes
columnar JSON for scripts/merge_data.py. Nothing in the dataset is modified.

Parsing of list and index pages is covered by tests against saved pages. Film
page parsing (parse_film) was written without a saved film page to test
against: check its output on a few films before trusting it.
"""
import argparse, html, http.cookiejar, json, pathlib, re, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://letterboxd.com"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
CACHE = ROOT / ".cache/letterboxd"
DATE_RE = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}\b")


class Blocked(Exception):
    pass


class ParseError(Exception):
    pass


def cache_path(path):
    return CACHE / (re.sub(r"[^A-Za-z0-9._-]", "_", path.strip("/")) + ".html")


def get(path, delay, refresh=False):
    """Fetch path. Detail pages are cached and reused; refresh=True (used for
    the list index, which changes) always goes to the network."""
    cached = cache_path(path)
    if cached.exists() and not refresh:
        return cached.read_text(encoding="utf-8")
    time.sleep(delay)
    headers = dict(HEADERS)
    if path.startswith("/closetpicks/lists/page/"):
        headers["Referer"] = BASE + "/closetpicks/lists/"
    req = urllib.request.Request(BASE + path, headers=headers)
    try:
        with OPENER.open(req, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise Blocked(f"{e.code} from letterboxd.com for {path}; stopping. Wait a while or use the official API.")
        raise
    CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(body, encoding="utf-8")
    return body


def parse_index(page):
    """Return (list slugs in page order, last page number)."""
    slugs = re.findall(r'<h2 class="name prettify">\s*<a href="/closetpicks/list/([^/"]+)/"', page)
    if not slugs:
        raise ParseError("no closet lists recognised on the index page")
    pages = [int(n) for n in re.findall(r'/closetpicks/lists/page/(\d+)/', page)]
    return slugs, max(pages, default=1)


def meta(page, prop):
    m = re.search(rf'<meta property="og:{prop}" content="([^"]*)"', page)
    return html.unescape(m.group(1)) if m else ""


def parse_list(slug, page):
    """Return (visit dict, [(pick_order, film_slug, film_title, film_year)])."""
    h1 = re.search(r'<h1 class="title-1 prettify(?: [^"]*)?">\s*([^<]*?)\s*</h1>', page)
    if not h1:
        raise ParseError(f"list {slug}: no title recognised")
    title = html.unescape(h1.group(1))
    description = meta(page, "description")
    date = DATE_RE.search(description)
    m = re.match(r"(.+?)['’]s? Criterion Closet Picks$", title)
    visitor = m.group(1) if m else title
    occupation = re.match(r"(?:" + DATE_RE.pattern + r"\s+)?(?:The|A|An) ([a-z][a-z ]{2,30}?) (?:recently |also )?(?:visited|stopped|dropped|came|joined)", description)
    picks = []
    for order, m in enumerate(re.finditer(r'data-item-name="([^"]*)" data-item-slug="([^"]*)"', page), 1):
        full = html.unescape(m.group(1))
        y = re.search(r"^(.*?)(?: \((\d{4})\))?$", full)
        picks.append((order, m.group(2), y.group(1), int(y.group(2)) if y.group(2) else None))
    if not picks:
        raise ParseError(f"list {slug}: no films recognised")
    youtube = re.search(r'href="(https://www\.youtube\.com/watch\?[^"]+)"', page)
    shop = re.search(r'href="(https://www\.criterion\.com/shop/collection/[^"]+)"', page)
    visit = {
        "visit_slug": slug,
        "visit_url": f"{BASE}/closetpicks/list/{slug}/",
        "visit_title": title,
        "visitor": visitor,
        "visit_date": date.group(0) if date else "",
        "occupation_guess": occupation.group(1) if occupation else "",
        "num_films": len(picks),
        "youtube_url": html.unescape(youtube.group(1)) if youtube else "",
        "criterion_shop_url": html.unescape(shop.group(1)) if shop else "",
        "description": description,
    }
    return visit, picks


def parse_film(slug, title, year, page):
    """Best-effort film row from a film page (JSON-LD plus a few links)."""
    ld = {}
    m = re.search(r'<script type="application/ld\+json">\s*(?:/\*.*?\*/)?\s*(\{.*?\})\s*(?:/\*.*?\*/)?\s*</script>', page, re.S)
    if m:
        try:
            ld = json.loads(m.group(1))
        except json.JSONDecodeError:
            ld = {}

    def names(key):
        v = ld.get(key) or []
        return [x["name"] for x in (v if isinstance(v, list) else [v]) if isinstance(x, dict) and x.get("name")]

    def links(kind):
        return [html.unescape(x) for x in re.findall(rf'href="/films/{kind}/[^"]+/"[^>]*>\s*<span class="text">([^<]+)</span>', page)] or \
               [html.unescape(x) for x in re.findall(rf'href="/films/{kind}/[^"]+/"[^>]*>([^<]+)</a>', page)]

    imdb = re.search(r'imdb\.com/title/(tt\d{7,10})', page)
    rating = (ld.get("aggregateRating") or {})
    runtime = re.search(r"([\d,]+)\s*(?:&nbsp;|\s)*mins", page)
    languages = list(dict.fromkeys(links("language")))     # the page lists the primary language twice
    cast = []
    block = re.search(r'<div class="cast-list text-sluglist">(.*?)</div>', page, re.S)
    if block:   # the structured data carries no cast on current pages
        for name in re.findall(r'<a [^>]*href="/actor/[^"]+/"[^>]*>([^<]+)</a>', block.group(1)):
            name = html.unescape(name).strip()
            if name and name not in cast:
                cast.append(name)
    cast = cast or names("actors")
    return {
        "film_slug": slug, "film_title": title, "film_year": year,
        "runtime_min": int(runtime.group(1).replace(",", "")) if runtime else None,
        "avg_rating": rating.get("ratingValue"), "rating_count": rating.get("ratingCount"),
        "directors": "; ".join(names("director")), "top_cast": "; ".join(cast[:10]),
        "genres": "; ".join(ld.get("genre") or []) if isinstance(ld.get("genre"), list) else (ld.get("genre") or ""),
        "themes": "; ".join(links("theme")), "countries": "; ".join(names("countryOfOrigin")),
        "primary_language": languages[0] if languages else "", "spoken_languages": "; ".join(languages),
        "studios": "; ".join(names("productionCompany")),
        "synopsis": html.unescape(re.sub(r"<[^>]+>", "", (re.search(r'<div class="truncate[^"]*"[^>]*>(.*?)</div>', page, re.S) or [None, ""])[1])).strip(),
        "poster_url": ld.get("image") or meta(page, "image"),
        "imdb_id": imdb.group(1) if imdb else "",
    }


def fetch_parsed(path, delay, parser, refresh=False):
    """get + parse; a page that does not parse is evicted from the cache so a
    rerun refetches it instead of replaying a bad response."""
    page = get(path, delay, refresh)
    try:
        return parser(page)
    except ParseError as e:
        cache_path(path).unlink(missing_ok=True)
        raise ParseError(f"{path}: {e}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="new.json")
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--max-visits", type=int, default=None)
    args = ap.parse_args(argv)

    data = json.loads((ROOT / "data/closet.json").read_text(encoding="utf-8"))
    have_visits = {r[0] for r in data["visits"]["rows"]}
    have_films = {r[0] for r in data["films"]["rows"]}
    try:
        new_slugs, page_no, last = [], 1, 1
        while page_no <= last:
            slugs, last = fetch_parsed("/closetpicks/lists/" + (f"page/{page_no}/" if page_no > 1 else ""), args.delay, parse_index, refresh=True)
            fresh = [s for s in slugs if s not in have_visits]
            new_slugs += fresh
            print(f"index page {page_no}/{last}: {len(fresh)} new")
            if not fresh and page_no > 1:
                break  # lists are newest first: nothing older can be missing
            page_no += 1
        new_slugs = list(dict.fromkeys(new_slugs))[: args.max_visits]
        visits, picks, films = [], [], {}
        for slug in new_slugs:
            visit, vpicks = fetch_parsed(f"/closetpicks/list/{slug}/", args.delay, lambda page, slug=slug: parse_list(slug, page))
            visits.append(visit)
            for order, fslug, ftitle, fyear in vpicks:
                picks.append({"visit_slug": slug, "pick_order": order, "film_slug": fslug, "film_title": ftitle, "film_year": fyear})
                if fslug not in have_films and fslug not in films:
                    films[fslug] = parse_film(fslug, ftitle, fyear, get(f"/film/{fslug}/", args.delay))
            print(f"{slug}: {len(vpicks)} picks")
    except Blocked as e:
        print(f"fetch_letterboxd: {e}\nNothing written; fetched pages are cached, rerun to continue.", file=sys.stderr)
        return 2
    except ParseError as e:
        print(f"fetch_letterboxd: page not recognised, Letterboxd's markup may have changed: {e}\nNothing written.", file=sys.stderr)
        return 3

    def table(name, rows):
        cols = data[name]["cols"]
        return {"cols": cols, "rows": [[r.get(c) for c in cols] for r in rows]}

    out = {"visits": table("visits", visits), "picks": table("picks", picks), "films": table("films", films.values())}
    target = pathlib.Path(args.out)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)
    print(f"wrote {args.out}: {len(visits)} visits, {len(picks)} picks, {len(films)} new films")
    return 0


if __name__ == "__main__":
    sys.exit(main())
