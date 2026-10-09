# IMDb ratings on every film

## Goal
Each film shows its IMDb rating and vote count, not only a link to IMDb.

## Source and licence
IMDb's own non-commercial dataset `title.ratings.tsv.gz` (https://datasets.imdbws.com/): `tconst`, `averageRating`, `numVotes` for every title, refreshed daily, about 8.7 MB. IMDb offers it for personal and non-commercial use with local copies allowed, subject to its terms, and its usage guidance restricts altering, republishing or repurposing the data (for example into movie-information databases), with an exception for individual personal use.

**Unresolved:** whether showing these ratings in a shared Pages app falls under that exception. No permission from IMDb has been obtained. The user decided on 2026-10-09 to build it and turn it on anyway, accepting that risk, after being told this. The design limits the exposure, it does not remove it:
- the ratings are **never committed**: they live in `data/imdb_ratings.json`, which is git-ignored, and are baked only into the Pages upload (`dist/index.html`), visible to people with access to the Pages app, not to the public;
- the committed `index.html` (public GitHub Pages) and `data/closet.json` carry no ratings, so the public site keeps the IMDb link without a rating;
- the Pages build shows a credit in the footer: "Ratings: information courtesy of IMDb (https://www.imdb.com), non-commercial dataset as of <date>". It deliberately does **not** use IMDb's longer wording that ends "Used with permission", because we do not have permission;
- the feature can be switched off by deleting `data/imdb_ratings.json` (or not running the fetch) and rebuilding: the Pages build then shows no ratings and no credit.
No scraping of imdb.com is involved.

## Fetching (`scripts/imdb_ratings.py`)
- One request for the gzip file with an identifying user agent; cached under `.cache/imdb/` and reused when less than a day old unless `--refresh`. The `last-modified` header gives the "as of" date.
- Checks it is a gzip with the header `tconst<TAB>averageRating<TAB>numVotes`; any other shape, a failed request or a truncated file aborts with a message and leaves the existing `data/imdb_ratings.json` untouched. The new file is written atomically.
- Keeps only the ids that appear as `imdb_id` in `data/closet.json`: `{"as_of": "YYYY-MM-DD", "ratings": {"tt0050083": [8.9, 855123], ...}}`. A rating outside 1.0 to 10.0 or a vote count that is not a positive integer is skipped and counted. It reports how many films got a rating and how many ids had none.
- `make imdb-ratings` runs it; `make update` runs it after the IMDb id backfill (ids come first).

## Build
`scripts/build.py` adds two columns, `imdb_rating` and `imdb_votes`, to the films table of the **Pages upload's** embedded data only, when `data/imdb_ratings.json` exists (blank for films without a rating); the root file and `data/closet.json` are unchanged. The footer attribution is added to the Pages upload only when ratings are present. `data/imdb_ratings.json` is an input of the staging fingerprint, so a ratings refresh makes the app "need staging". `build()` still returns the root variant.

## Page
- Film popup: a row "IMDb  ★ 8.9 · 855K votes" in the details column next to the Letterboxd rating, and the IMDb link stays.
- Club film lines: the IMDb link text becomes "IMDb 8.9" when there is a rating.
- Without a rating (no id on Wikidata or Letterboxd, not in the dataset, or the GitHub Pages build) nothing extra is shown.
- Ratings are one decimal; votes are compact (`999`, `1.2K` from 1,000, `345K`, `1.2M`).

## Testing
Python: parsing a generated gzip (filtering to the dataset's ids, rejected ratings and votes, the header check, a truncated gzip, a failed download and an unchanged previous file, cache reuse and `--refresh`); build: the Pages upload's data has the two columns and the root and committed data do not, the footer attribution only with ratings, the staging fingerprint changes with the ratings file. Browser: the popup row and the club link text with and without a rating, the compact vote formatting, the attribution, and the root build showing no ratings.

## Out of scope
Sorting or filtering by IMDb rating, ratings on grid cards, other IMDb fields, and any use of imdb.com pages.
