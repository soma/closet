# Review: film-links-task, round 1

## Findings

- [S1] should — `src/template.html:2031`: The unknown-film branch clears the route state and rewrites the URL but does not close an existing modal. Reproduced by opening `#film/12-angry-men` and then navigating to `#film/no-such-film`: the URL becomes `#browse` and `STATE.film` is null, but the 12 Angry Men popup remains visible and body scrolling stays disabled. This displays a different film than the requested link and leaves the fallback inconsistent with the page. Close the existing modal and restore scrolling when rejecting an unknown film; add a valid-film-to-unknown-film navigation test, not just an unknown-film cold-load test.

- [S2] should — `src/template.html:1168–1170`: Film routes intentionally leave `STATE.view` unchanged, but `applyHash()` still clears `CLUB.id` and its data because `r.view` is null. Opening a film through a hash change over an existing club therefore loses the underlying club selection. Reproduced on the simulated host: start at `#clubs/id1`, navigate to `#film/12-angry-men`, then press Escape; the result is `#clubs` with no selected club instead of returning to `#clubs/id1`. Preserve club state when applying a film-only route, and cover this transition in the browser tests.

## Validation and review limits

- Reviewed committed `HEAD~1..HEAD` (`cb42dae..6a305bd`) using an isolated committed archive.
- `script/test` passed all 85 tests, including the new direct-load, share-anchor, popup-close, and hash-change tests. `git diff --check HEAD~1..HEAD` passed.
- Separate Chromium probes reproduced both findings against the committed build; the club probe used the existing simulated host.
- No live Pages upload or embedded-host navigation was performed. Actual host behavior when opening the configured share URL in another tab remains unverified.

Verdict: CHANGES REQUESTED

## Response

[S1] fixed -- `syncFilmModal` now closes any open popup (restoring scrolling) before falling back for an unknown film; test navigates from a valid film hash to an unknown one and checks the popup, body overflow, address and state.
[S2] fixed -- `applyHash` only touches the club selection for routes that carry a view; a film route leaves view and club as they were. Test: `#clubs/id1` -> `#film/12-angry-men` -> Escape returns to `#clubs/id1` with the club still selected.
