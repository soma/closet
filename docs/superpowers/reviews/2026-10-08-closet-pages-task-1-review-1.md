# Review: closet-pages-task-1, round 1

## Findings

- [S1] should — `scripts/merge_data.py:113`: Incoming film and visit duplicates are collapsed by the merge index before `validate(merged)` runs. Two incoming film rows with the same new slug and conflicting titles are accepted: without `--overwrite`, the first title wins; with it, the last wins. This loses conflicting input without the duplicate-slug error required by the design. The duplicate fixture currently tests `validate()` directly, so it misses this behavior through the actual import path. Check incoming key uniqueness before merging (while still allowing references to existing records), and add regression tests that conflicting duplicate films and visits raise `MergeError` in both modes without changing the canonical file.

- [S2] should — `tests/test_browser.py:10`: The required browser smoke check silently becomes optional when Playwright is absent. In this review, `script/test` exited successfully with seven passing tests and the sole browser test skipped. No dependency/setup declaration is included in the change, so a fresh checkout can report a successful full test run without ever booting the app. The approved design requires `script/test` to run the browser check. Declare/document the Playwright and Chromium setup and make the full test entry point fail with an actionable message when these prerequisites are missing; verify a run in which the smoke test executes.

- [N1] nit — `tests/test_browser.py:26`: Checking only that `#app` contains more than 100 characters does not establish that each requested view rendered. Browse already satisfies this assertion, so a broken hash handler that leaves Browse visible for every navigation would pass. Assert a distinct heading or element in `#main` for each view, using a condition-based wait instead of the fixed 300 ms delay. This follows the design's explicit requirement to verify all three views.

## Validation and review limits

- Ran `script/test` in a temporary export of HEAD to avoid rewriting the reviewed checkout: seven tests passed, one browser test skipped because Playwright is unavailable.
- Confirmed that `data/closet.json` exactly equals the decoded dataset from `d338403:index.html`.
- Reproduced the conflicting duplicate-film import in memory with both overwrite settings; both were accepted.
- Reviewed the complete script/test changes and the HTML changes. CSV ingestion and overwrite behavior lack dedicated automated coverage in the submitted suite; browser behavior remains unverified here.

## Declined to judge

- Live data acquisition and hosted Pages staging/CSP behavior: outside the named build/merge/tests task; the design explicitly defers data acquisition and hosted preview validation.

Verdict: CHANGES REQUESTED

## Response

[S1] fixed -- scripts/merge_data.py rejects duplicate incoming keys before merging; tests cover films and visits in both modes, plus overwrite, CSV import and main() leaving the file untouched on invalid input.
[S2] fixed -- script/test fails with setup instructions when playwright is missing; README.md and requirements-dev.txt document setup; the smoke test no longer skips and ran green here.
[N1] fixed -- smoke test asserts a distinct h2 per view with a condition-based wait.
