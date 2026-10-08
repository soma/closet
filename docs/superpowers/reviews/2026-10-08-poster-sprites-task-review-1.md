# Review: poster-sprites-task, round 1

## Findings

- [S1] should — `scripts/build.py:40` / `tests/test_data.py:34`: The build now intentionally embeds the poster map only in `dist/index.html`, but the existing round-trip test still asserts both HTML artifacts equal the root HTML returned by `build()`. Once the planned `data/posters.json` is generated, this test fails on every run. Reproduced in a temporary export by adding a one-film poster map and running `BuiltPage.test_built_blob_round_trips_to_canonical_json`: one assertion failure. Update the test to decode and check each artifact independently, asserting the map is present only in the Pages artifact. Exercise both map-present and map-absent builds. The absence of the map at this commit is expected; the failure in the intended next state is the issue.

- [S2] should — `scripts/make_posters.py:16`: The generator requires Pillow, but no dependency declaration or setup instructions were added; `requirements-dev.txt` still contains only Playwright. The project's virtual environment raises `ModuleNotFoundError: No module named 'PIL'`, so the documented project setup cannot run the new generator. Declare Pillow in an appropriate requirements file and document the interpreter/setup command used for poster generation. Add generator tests to the normal test entry point so this dependency and the crop/packing path are exercised.

## Validation and review limits

- Reviewed `HEAD~1..HEAD`, ending at `1650010`, including generation, sprite rendering/CSS, asset-row projection, build changes, and tests.
- Ran `script/test` in a temporary export of HEAD using the existing virtual environment, outside the execution sandbox for Chromium: all 47 tests passed with the expected absent poster map. Then introduced a small map only in that temporary export and reproduced [S1] with the existing round-trip test.
- Used the system Python's available Pillow to pack 65 synthetic thumbnails in a separate temporary directory. Sheet dimensions and the transition from slot `[0,7,7]` to `[1,0,0]` were correct.
- The submitted suite does not test `make_posters.py`. The new browser test checks DOM/style values and missing-sheet fallback; it does not demonstrate successful decoding/display of a real sheet. Actual Pages asset-row shape, asset URLs, and CSP compatibility remain unverified until upload/integration checks.
- No real posters were downloaded or uploaded. No implementation files were edited.

## Declined to judge

- Missing generated sheets and `data/posters.json`: explicitly expected at this commit.
- Uploading sheets and verifying live Pages rendering: deferred integration work, not performed during this code review.

Verdict: CHANGES REQUESTED

## Response

[S1] fixed -- the round-trip test now decodes each artifact on its own: the root file always has `POSTER_MAP = null`, the Pages upload carries the map exactly when `data/posters.json` exists; a temp-root browser test already covers the map-present build.
[S2] fixed -- Pillow is in requirements-dev.txt and installed in the project venv, `make posters` documented in README, and tests/test_posters.py (run by script/test) covers cropping for several aspect ratios including the centre-crop colour check, slot order across sheets (63 -> [0,7,7], 64 -> [1,0,0]), a blocked run keeping earlier thumbnails and skipping them on rerun, and a bad image not stopping the run.
