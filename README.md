# The Closet

Criterion Closet picks explorer: one self-contained page, vanilla JS.

- `src/template.html`: the app. `data/closet.json`: the canonical dataset.
- `scripts/build.py` writes `index.html` (GitHub Pages) and `dist/index.html` (upload to Pages) from the two.
- `scripts/merge_data.py NEW.json|CSV_DIR [--overwrite]` validates and merges new visits into `data/closet.json`; run the build afterwards.
- `script/test` runs everything. One-time setup for the browser check:
  `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/playwright install chromium`
