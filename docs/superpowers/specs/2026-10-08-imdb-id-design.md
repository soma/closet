# IMDb ids in the dataset, the club entries and the UI

## Goal
Every film carries an IMDb id (`tt…`). It must be in the club's scheduled data (the `entries` collection that the Pages data flow exposes to consumers), and the UI links to IMDb.

## Decisions
### Dataset
- New column `imdb_id` appended to `films` in `data/closet.json` (empty string when unknown). Valid values match `^tt\d{7,10}$`; `merge_data.validate` rejects anything else. Incoming merge data must carry the column (the fetcher builds its tables from the dataset's columns, so it does).
- **Backfill source: Wikidata**, which stores both the Letterboxd film slug (P6127) and the IMDb id (P345), so matches are exact on the slug we already hold, with no title or year guessing. `scripts/backfill_imdb.py` queries the public SPARQL endpoint in chunks of 150 slugs with an identifying user agent and a pause between requests, then fills `imdb_id` only where it is blank. A slug with several distinct IMDb ids on Wikidata is left blank and reported. A malformed id is ignored and reported. It never overwrites a non-empty value unless `--overwrite`. It reports counts matched, already set, conflicting, missing. A failed request aborts and writes nothing.
- The fetcher's `parse_film` also extracts the IMDb id from the Letterboxd film page link (`imdb.com/title/tt…`) for newly fetched films; blank if absent. That parsing is untested against a real page, like the rest of `parse_film`; the backfill script can fill blanks afterwards.
- `make backfill-imdb` runs the backfill.

### Club entries (the scheduled data)
- `server.js` receives a build-time map `slug -> imdb_id` (replacing the slug list; the slug set is its keys). `add_entry` stores `imdb_id` on the new entry row next to `film_slug`; empty string if unknown. Consumers of the data flow therefore get it without needing the dataset.
- Existing entries (seven today) lack it. A new idempotent action `fill_imdb` reads all `entries`, sets `imdb_id` on those that lack one where the map has one, and does nothing else (no state change). It writes one global maintenance log row (`club_id` empty, action `fill_imdb`, detail = count) only when it changed something; that row is intentionally absent from every club's activity because club activity filters on `club_id`. The club page calls it once after loading a club whose entries show a missing id that the dataset can supply. Concurrent calls are harmless because the writes are the same values.

### UI
- Film popup: an "IMDb" link (opens `https://www.imdb.com/title/<id>/` in a new tab, `rel="noopener"`) when the film has an id.
- Club view: the film line gets a small "IMDb" link after the title, using the entry's `imdb_id` and falling back to the dataset's.
- No link is shown when the id is blank; ids are validated against the regex before they are put in a URL.

## Testing
Python: backfill against a recorded Wikidata response fixture (match, duplicate-same-id, conflict, malformed, missing, already-set kept, `--overwrite`, request failure writes nothing, chunking); merge validation of ids; fetcher IMDb extraction fixture; build injects the map. Node: `add_entry` stores the id, unknown id stored as empty, `fill_imdb` fills only blanks, is idempotent, changes no state, logs only when it changed something. Browser: popup and club links have the right href and no link for blanks; the club view repairs old entries through `fill_imdb`.

## Out of scope
Matching films without a Letterboxd slug, IMDb ratings, scraping imdb.com, and an IMDb link on Browse cards.
