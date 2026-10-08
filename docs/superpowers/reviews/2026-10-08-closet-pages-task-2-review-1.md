# Review: closet-pages-task-2, round 1

## Findings

- [S1] should — `scripts/fetch_letterboxd.py:59` (also lines 67–80 and 146–147): Unrecognized list HTML is treated as a successful visit with no title, visitor, date, or picks. For example, parsing `<html><body>Unexpected page</body></html>` produces `num_films=0`; that visit passes the existing merge validation and is added to the canonical dataset. Subsequent fetches skip its slug as already imported, so a parsing failure can permanently hide a real visit's picks. Index parsing similarly interprets unrecognized HTML as an empty, one-page result. Validate that the expected page structure and list content were recognized, distinguish a legitimate empty result from a parse failure, and abort without writing mergeable output on failure. Add orchestration tests for unrecognized index/list responses and preservation of any existing output file.

- [S2] should — `scripts/fetch_letterboxd.py:28`: Every cached page is reused forever, including the list index. After the first successful run caches `/closetpicks/lists/`, future runs cannot discover visits subsequently added to that page or an increased pagination count. There is no refresh option or expiry. Confirmed with a cached index and a mocked network response: `get()` returned the old index without a network call. Revalidate or refresh mutable index pages on a new discovery run, while retaining an explicit cache/resume policy for detail pages. Test two runs where the index gains a new visit; the second must discover it. Preserve the existing stop-on-403/429 behavior.

## Validation and review limits

- Reviewed `HEAD~1..HEAD`, ending at `d431c6a`, including the fetch script, tests, fixtures, and README change.
- Ran `script/test` in a temporary export of HEAD with the existing virtual environment: all 15 tests passed, with no skips. Chromium initially failed under the execution sandbox; the rerun outside it passed.
- Reproduced both findings locally with in-memory input or temporary cache files. No live Letterboxd requests were made.
- The three fetch tests cover fixture parsing and the empty-film fallback. They do not exercise discovery/cache orchestration, HTTP 403/429 handling, or successful film metadata extraction. Actual film-page compatibility remains unverified, as the script itself acknowledges.

## Declined to judge

- Live source access and permission to perform acquisition: the supplied design defers acquisition and explicitly excludes scraping. This commit adds a scraper beyond that design; the review evaluates the explicitly named artifact, but does not establish approval for live acquisition or treat the deferred refresh as completed.
- Hosted Pages staging and CSP behavior: outside this fetch-script task.

Verdict: CHANGES REQUESTED

## Response

[S1] fixed -- parse_index/parse_list raise ParseError on unrecognised pages or empty lists; main returns 3 and writes nothing; bad pages are evicted from the cache; output is written atomically. Tests cover junk pages, an existing output file being preserved, and cache eviction.
[S2] fixed -- the list index is always refetched (refresh=True); detail pages stay cached. A two-run test shows the second run discovering a newly added visit.
Declined-to-judge note: design addendum added recording the user's decision to add a user-run fetcher; the tool is not run from this environment.
