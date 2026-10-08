#!/usr/bin/env python3
"""Build index.html (GitHub Pages) and dist/index.html + dist/server.js (Pages
upload) from src/template.html, src/club.{js,css}, src/server.js and
data/closet.json."""
import base64, gzip, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLACEHOLDER = "__DATA_B64__"


def encode(data):
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(gzip.compress(raw, mtime=0)).decode("ascii")


def build(root=ROOT):
    template = (root / "src/template.html").read_text(encoding="utf-8")
    assert template.count(PLACEHOLDER) == 1, "template must contain one placeholder"
    data = json.loads((root / "data/closet.json").read_text(encoding="utf-8"))
    html = template.replace(PLACEHOLDER, encode(data))
    html = html.replace("/*__CLUB_CSS__*/", (root / "src/club.css").read_text(encoding="utf-8"))
    html = html.replace("/*__CLUB_JS__*/", (root / "src/club.js").read_text(encoding="utf-8"))
    slugs = [row[data["films"]["cols"].index("film_slug")] for row in data["films"]["rows"]]
    server = (root / "src/server.js").read_text(encoding="utf-8").replace(
        "__FILM_SLUGS__", json.dumps(slugs, ensure_ascii=False, separators=(",", ":")))
    (root / "dist").mkdir(exist_ok=True)
    (root / "dist/server.js").write_text(server, encoding="utf-8")
    for target in ("index.html", "dist/index.html"):
        path = root / target
        path.parent.mkdir(exist_ok=True)
        path.write_text(html, encoding="utf-8")
    return html


if __name__ == "__main__":
    build()
