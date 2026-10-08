---
name: update-closet
description: Use when the closet explorer data has been refreshed (make update) or the user asks to update the Pages app with new closet data, new posters or IMDb ids. Stages the build and uploads changed poster sheets to Pages page 266. Never pushes or publishes.
---

# Update the closet Pages app

The scraping and data steps run on the **user's machine** (`make update`): Letterboxd and
criterion.com block this agent's environment, so never fetch from them here. This skill is the
half that only Claude can do, through the Pages MCP tools: stage the build, upload the poster
sheets that changed, verify on the real host.

Page id **266**, repo `~/projects/barsoom/lab/closet`. Film data lives inside `index.html`
(built from `data/closet.json`); clubs and entries are page data; posters are page assets in the
`poster_sheets` collection. See `docs/update-pipeline.md`.

## Rules
- Never push, and never publish: staging is the end. The user reviews and publishes at
  https://pages.auctionet.com/pages/266.
- Never commit the Pages share URL (it contains a token and the repo is public). It only goes into
  `dist/index.html` through the `PAGES_URL` environment variable.
- Do not touch uncommitted changes you did not make (for example the user's edits to the fetcher).
  Commit only the files this update produced.
- Run `script/test` before committing. Follow CLAUDE.md: small commits, no agent mentions in commit messages.

## Steps
1. **Check the data is updated.** `make summary`. If `new visits` and `new films` are 0 and
   nothing is listed to upload, tell the user there is nothing to do. If the data was not refreshed
   yet, ask them to run `make update` on their machine (do not attempt the fetch).
2. **Spot-check the new films.** The summary lists new films missing `imdb_id`, `runtime_min`,
   `avg_rating`, `directors` or `poster_url`. Film page parsing was written without a saved page, so
   gaps are expected at first; report them. A new film with no directors or runtime can never be
   suggested by the club rule. IMDb ids missing on Wikidata stay blank and show no link.
3. **Run the tests**: `script/test` must pass.
4. **Commit the data**: `git add data/closet.json data/posters.json index.html` (and nothing else),
   commit with a message like `Add N closet visits and M films`. Never `git push`.
5. **Build for Pages.** `list_pages` (name "closet") gives `share_url`;
   `PAGES_URL=<share_url> python3 scripts/build.py`.
6. **Upload changed poster sheets first** (the new map refers to them):
   - `python3 scripts/poster_status.py --json` prints the `files` array for `begin_asset_upload`.
     Empty list = nothing to upload, skip to step 7.
   - `begin_asset_upload(id=266, collection="poster_sheets", files=<that list>)` (at most 200).
   - PUT each file from `.cache/posters/sheets/` to its `put_url` with `curl -X PUT -H "Content-Type: image/webp" --data-binary @file`; expect 204.
   - `finalize_asset_upload` with one row per slot: `{"asset_id": <slot asset_id>, "data": {"sheet": <number from the key, e.g. sheet-03 -> 3>}}`. All must be in `stored`, none in `failed`.
   - Only then `python3 scripts/poster_status.py --mark-uploaded`.
   - If "Uploaded files are not switched on", stop and ask the user to have an administrator switch it on.
7. **Stage the build**: `begin_upload(266, [index.html, server.js])`, PUT `dist/index.html` and
   `dist/server.js` (`Content-Type: text/html` and `application/javascript`), then `finalize_upload`.
8. **Verify on the real host** with `run_page_action` (nothing is kept): `poster_sheets` returns every
   sheet with an `asset_url`; `list_clubs` works; `fill_imdb` reports 0 or only entries that still lack an id.
   Check `read_page_events` for new errors.
9. **Report**: new visits/films/picks, gaps found, sheets uploaded, what is staged, and that the user
   must publish. Say plainly what was not verified (browser rendering of the new posters).

## If something fails
- `begin_upload`/`begin_asset_upload` URLs expire after 15 minutes: request fresh ones.
- A sheet in `failed`: upload just that file again; finalizing a stored file is harmless.
- The poster map in `data/posters.json` changes only by appending (stable slots); if many sheets show
  as changed, something repacked: check `git diff data/posters.json` before uploading.
