# Review: cast-parsing-task, round 1

## Findings

- [N1] nit — `tests/test_fetch.py:200–203`, `scripts/fetch_letterboxd.py:140–145`: The new structured-data fallback test supplies `actors`, but the real fixture supplies `actor` with 22 names. The comment that current pages carry no structured cast is therefore contradicted by the fixture. Keeping just that fixture's JSON-LD produces a blank `top_cast`, so the test does not establish fallback compatibility with the supplied real page. Exercise the real `actor` shape and support it in the fallback, retaining `actors` compatibility if needed; correct the comment. This is nonblocking because the plural-key limitation predates this commit and the new HTML extraction works for the supplied page.

## Validation and review limits

- Reviewed code commit `aba869a` (`270315f..aba869a`, the requested `HEAD~2..HEAD~1`). The mechanical data commit `3d2ff38` and earlier user-authored commit `270315f` were excluded and remain unreviewed.
- `script/test` passed all 81 tests in an isolated archive of `aba869a`, including the new FilmPage and reparse tests. These cover cast order and limit, entity decoding, language deduplication, filling blanks, overwrite/idempotence, missing cache entries, and avoiding blank replacements.
- A separate probe reproduced the structured-data fallback limitation using the committed real-page fixture.
- `git diff --check` reports trailing whitespace on `tests/fixtures/film.html:7`; no functional impact identified.
- No live fetches or writes to the working dataset were performed. Real-site markup beyond the supplied fixture and the mechanical backfill output were not verified. Reparse tests exercise the transformation function, not the CLI's validation/write failure paths.

Verdict: APPROVED

## Response

[N1] fixed -- the fallback now reads the real `actor` key (then `actors`), the comment no longer claims the structured data has no cast, and a test removes the cast list from the real fixture and checks the fallback yields the same first names and ten in total. Trailing whitespace stripped from the fixture. The 43 backfilled films came from the visible cast list, so the data is unchanged.
