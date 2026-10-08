# Updating the closet data and the Pages app

Two halves, because scraping is blocked for the agent and only Claude can use the Pages tools.

**On your machine: `make update`**
1. `make fetch` finds visits missing from `data/closet.json`, writes `new.json` (needs your own network access).
2. `make merge` validates and merges them.
3. `make backfill-imdb` fills `imdb_id` for films that lack one (Wikidata, polite and slow; usually one request).
4. `make posters` downloads posters for new films and repacks the sprite sheets with **stable slots**,
   so only the last sheet(s) change.
5. `make build`, `make test`, then `make summary` prints what changed and which sheets need uploading.

Nothing is committed, pushed or uploaded by this.

**With Claude: the `update-closet` skill** (`.claude/skills/update-closet/SKILL.md`). Ask
"update the closet app". It commits the data, builds with the Pages address, uploads only the changed
sheets (`make poster-status` shows them), stages `index.html` and `server.js`, verifies on the real host
and reports. You publish.

Why film data is not page data: it is baked into `index.html`, so a data update is a normal staged
change that you review and publish. Clubs and entries are shared page data; posters are page assets.
