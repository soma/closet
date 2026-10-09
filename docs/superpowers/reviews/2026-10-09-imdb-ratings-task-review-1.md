# Review: IMDb ratings task, round 1

## Findings

- [S1] should — `tests/test_data.py:38–40`: The existing round-trip test still requires both builds' decoded data to equal the canonical dataset. Once the ignored local ratings file exists, the Pages build intentionally adds `imdb_rating` and `imdb_votes`, so this assertion fails. This breaks the required test run after the normal `make update` workflow downloads ratings; the clean-checkout suite misses it because that file is absent. Reproduced the existing test with a synthetic local ratings file: it fails on `dist/index.html`. Keep the root's exact canonical-data assertion, update the Pages expectation to verify its enrichment, and run the suite both with and without synthetic local ratings.

- [S2] should — `scripts/imdb_ratings.py:44–46`: Rows with the wrong number of TSV fields are silently discarded, including during the pre-cache shape check. A valid gzip with the expected header but a two-field data row is therefore accepted and replaces both the cache and the previous ratings output. In a focused update reproduction, a previously populated ratings file became empty and the malformed response was cached. This violates the design's requirement that an unexpected shape abort and preserve the existing file. Reject malformed nonblank rows before filtering to wanted IDs, while retaining the specified skip/count behavior for invalid numeric values. Add a regression covering missing/extra fields and preservation of the previous output and cache.

## Validation and review limits

- Reviewed `bc40fc3..9935d09` (`HEAD~2..HEAD~1`), against the approved design. The subsequent review-document commit is outside scope.
- `script/test` passed all 126 tests in an isolated export of the reviewed commit. Focused checks with synthetic input reproduced both findings above. `git diff --check HEAD~2..HEAD~1` passed.
- Inspected the committed root page's decoded data: it has no rating/vote columns and no ratings attribution date. The ratings file, cache, and Pages output are excluded from tracked artifacts; synthetic build tests cover the root/Pages separation.
- No live IMDb download or Pages-host deployment was exercised. The user's licensing decision was accepted as provided and was not reopened.

Verdict: CHANGES REQUESTED

## Response

[S1] fixed -- the round-trip test keeps the exact canonical assertion for the root file and expects the Pages upload to equal the canonical dataset plus the two IMDb columns when the local ratings file exists (computed with `build.with_ratings`), else the canonical dataset. I had run the suite before fetching the real ratings, so I missed this; the suite now passes both with the real ratings file present and with it moved away (127 tests each time), and failed before the fix with the real file present.
[S2] fixed -- `read_ratings` raises `RatingsError` for any nonblank row without exactly three fields, before filtering to wanted ids, so the pre-cache shape check and the update both refuse it and keep the previous output and cache; skipping and counting invalid numeric values is unchanged. Tests: too few and too many fields, both with and without wanted ids, and an update with a short row leaves the previous ratings file and the cache untouched. The real downloaded file passes the stricter check.
