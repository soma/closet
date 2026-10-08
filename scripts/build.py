#!/usr/bin/env python3
"""Build index.html (GitHub Pages) and dist/index.html (Pages upload) from
src/template.html and data/closet.json."""
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
    for target in ("index.html", "dist/index.html"):
        path = root / target
        path.parent.mkdir(exist_ok=True)
        path.write_text(html, encoding="utf-8")
    return html


if __name__ == "__main__":
    build()
