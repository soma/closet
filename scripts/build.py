#!/usr/bin/env python3
"""Build index.html (GitHub Pages) and dist/index.html + dist/server.js (Pages
upload) from src/template.html, src/club.{js,css}, src/server.js and
data/closet.json."""
import base64, gzip, json, os, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLACEHOLDER = "__DATA_B64__"


def encode(data):
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(gzip.compress(raw, mtime=0)).decode("ascii")


def with_ratings(data, ratings):
    """A copy of the dataset whose films table also has imdb_rating and imdb_votes (null when unrated)."""
    out = json.loads(json.dumps(data))
    films = out["films"]
    idx = films["cols"].index("imdb_id")
    films["cols"] += ["imdb_rating", "imdb_votes"]
    for row in films["rows"]:
        r = ratings.get(row[idx]) if row[idx] else None
        row += [r[0], r[1]] if r else [None, None]
    return out


def build(root=ROOT):
    template = (root / "src/template.html").read_text(encoding="utf-8")
    assert template.count(PLACEHOLDER) == 1, "template must contain one placeholder"
    data = json.loads((root / "data/closet.json").read_text(encoding="utf-8"))
    # IMDb ratings are licensed for personal, non-commercial use and must not be republished, so they are
    # never in the committed files: only the Pages upload carries them, when the (git-ignored) file exists.
    ratings_file = root / "data/imdb_ratings.json"
    ratings = json.loads(ratings_file.read_text(encoding="utf-8")) if ratings_file.exists() else None
    pages_data = with_ratings(data, ratings["ratings"]) if ratings else data
    html = template
    html = html.replace("/*__CLUB_CSS__*/", (root / "src/club.css").read_text(encoding="utf-8"))
    html = html.replace("/*__CLUB_JS__*/", (root / "src/club.js").read_text(encoding="utf-8"))
    html = html.replace("/*__CLOSET_CSS__*/", (root / "src/closet.css").read_text(encoding="utf-8"))
    html = html.replace("/*__CLOSET_JS__*/", (root / "src/closet.js").read_text(encoding="utf-8"))
    cols = data["films"]["cols"]
    imdb = {row[cols.index("film_slug")]: row[cols.index("imdb_id")] or "" for row in data["films"]["rows"]}
    server = (root / "src/server.js").read_text(encoding="utf-8").replace(
        "__FILM_IMDB__", json.dumps(imdb, ensure_ascii=False, separators=(",", ":")))
    (root / "dist").mkdir(exist_ok=True)
    (root / "dist/server.js").write_text(server, encoding="utf-8")
    pages_url = os.environ.get("PAGES_URL", "")
    assert '"' not in pages_url and "\\" not in pages_url and "<" not in pages_url, "PAGES_URL must be a plain URL"
    posters = root / "data/posters.json"
    poster_map = posters.read_text(encoding="utf-8").strip() if posters.exists() else "null"
    variants = (("index.html", data, "", "null", ""),
                ("dist/index.html", pages_data, pages_url, poster_map, ratings["as_of"] if ratings else ""))
    for target, blob_data, page_url, pmap, as_of in variants:
        path = root / target
        path.parent.mkdir(exist_ok=True)
        out = (html.replace(PLACEHOLDER, encode(blob_data)).replace("__PAGE_URL__", page_url)
                   .replace("__POSTER_MAP__", pmap).replace("__IMDB_AS_OF__", as_of))
        path.write_text(out, encoding="utf-8")
    return (html.replace(PLACEHOLDER, encode(data)).replace("__PAGE_URL__", "")
                .replace("__POSTER_MAP__", "null").replace("__IMDB_AS_OF__", ""))


if __name__ == "__main__":
    build()
