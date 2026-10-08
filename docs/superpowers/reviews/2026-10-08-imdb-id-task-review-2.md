# Review: imdb-id-task, round 2

## Findings

- [S2] should — `src/club.js:126` (`clubLinkUrl`): Any nonempty `document.referrer` is treated as the public page URL, but it is not a reliable source for that URL. In a top-level page it can identify an unrelated site that linked here; in a cross-origin iframe it normally contains only the parent's origin, losing the page path. For example, with referrer `https://pages.auctionet.com/`, the function produces `https://pages.auctionet.com/#clubs/id1`, which does not identify page 266. I also reproduced it choosing an unrelated `https://example.org/` over the actual app address. Both clipboard success and fallback then present the wrong URL. Use a verified canonical host-page URL or an explicit host-provided URL for the embedded app, and the current document URL for standalone use; do not infer a complete page address from an arbitrary referrer. Add cases for unrelated, origin-only, and absent referrers, and verify that the resulting hosted URL opens the intended club. The browser's cross-origin referrer behavior is documented in [MDN's Referrer-Policy reference](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy).

## Previous findings

- [S1] resolved — `backfill-imdb` is now included in the Makefile, help, and `.PHONY`; `make -n backfill-imdb` expands to the new script without making a live request.
- [N1] resolved — The new temporary-file test invokes `main()` with a failed lookup, checks its nonzero result, and verifies byte-for-byte preservation of the dataset.

## Validation and review limits

Reviewed `HEAD~2..HEAD`, ending at `b3734cc`, including the share icon addition and round 1 responses. Ran `script/test` in a temporary export of HEAD using the existing virtual environment, outside the execution sandbox for Chromium: all 42 tests passed. The share tests use a directly loaded local file with an empty referrer and therefore do not exercise the problematic URL selection branch. Independently reproduced that branch with a nonempty external referrer.

No live backfill, deployment, or shared-data mutation was performed. Actual Pages URL/iframe routing and clipboard permissions remain unverified. The selected-input fallback and clipboard behavior pass their mocked browser tests.

## Declined to judge

- The ongoing data backfill and deployed IMDb entry repair: outside this round's requested artifact scope.
- Unchanged backfill matching and shared-state concurrency: not re-reviewed in this fix/share-icon round.

Verdict: CHANGES REQUESTED

## Response

[S2] fixed -- the referrer is no longer used. The link base is `PAGE_URL`, baked in at build time from the `PAGES_URL` environment variable into `dist/index.html` only (the Pages share address carries a token and the repository is public, so it is never written into the committed `index.html`); when empty the app uses its own address. Tests: configured base, empty base, a misleading `Referer` header ignored, the committed file free of the URL, and a non-plain URL rejected by the build. Whether the hosted link opens the intended club still has to be checked on the real page.
