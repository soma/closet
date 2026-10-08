# The Closet

Criterion Closet picks explorer: one self-contained page, vanilla JS.

- `src/template.html`: the app. `data/closet.json`: the canonical dataset.
- `scripts/build.py` writes `index.html` (GitHub Pages) and `dist/index.html` (upload to Pages) from the two.
- `scripts/merge_data.py NEW.json|CSV_DIR [--overwrite]` validates and merges new visits into `data/closet.json`; run the build afterwards.
- `scripts/fetch_letterboxd.py` finds closet visits missing from the dataset and writes `new.json` for the merge. It uses browser-style headers and an in-memory cookie session, waits between requests, caches pages in `.cache/` and stops at the first 403/429. Film page parsing is untested against a real page: spot-check the new films.
- `script/test` runs everything. One-time setup for the browser check:
  `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/playwright install chromium`

Quick start: `make help`. To refresh the data from your own machine: `make refresh`.

For the Pages upload, build with the page address so the share icon copies the right link: `PAGES_URL=<the Pages share URL> make build`, then upload `dist/`. The address contains a token, so it is only baked into `dist/index.html`, never the committed `index.html`.

Posters in the Pages app: Pages blocks hotlinked images, so `make posters` (needs `make setup` once) packs them into sprite sheets in `.cache/posters/sheets/`, which are uploaded to the page as assets (not committed); the small `data/posters.json` map is committed.
