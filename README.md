# The Closet

Criterion Closet picks explorer: one self-contained page, vanilla JS.

- `src/template.html`: the app. `data/closet.json`: the canonical dataset.
- `scripts/build.py` writes `index.html` (GitHub Pages) and `dist/index.html` (upload to Pages) from the two.
- `scripts/merge_data.py NEW.json|CSV_DIR [--overwrite]` validates and merges new visits into `data/closet.json`; run the build afterwards.
- `scripts/fetch_letterboxd.py` (run it yourself, from your own machine) finds closet visits missing from the dataset and writes `new.json` for the merge. It waits between requests, caches pages in `.cache/` and stops at the first 403/429. Film page parsing is untested against a real page: spot-check the new films.
- `script/test` runs everything. One-time setup for the browser check:
  `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/playwright install chromium`
