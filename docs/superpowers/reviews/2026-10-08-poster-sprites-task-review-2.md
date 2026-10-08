# Review: poster-sprites-task, round 2

## Findings

None.

## Previous findings

- [S1] resolved — The round-trip test now decodes each HTML artifact independently and checks the root/map-free versus Pages/map-present behavior explicitly. The existing temporary-root browser test covers map-present rendering, and the previously failing round-trip scenario also passes with a supplied map.
- [S2] resolved — Pillow is declared in `requirements-dev.txt`; README and `make posters` specify the virtual-environment setup and command. The new generator tests run through `script/test` and cover center cropping, dimensions, packing across a sheet boundary, missing thumbnails, blocked downloads/resumption, and invalid-image handling.

## Validation and review limits

Reviewed `HEAD~2..HEAD`, ending at `e372de5`, including the Pillow resampling API adjustment and round 1 responses. Ran `script/test` in a temporary export of HEAD using the existing virtual environment, outside the execution sandbox for Chromium: all 51 tests passed. Then added a small poster map only in the temporary export and reran the previously failing round-trip test: it passed. Confirmed `make -n posters` invokes the virtual-environment interpreter without downloading anything.

No real posters were downloaded or uploaded, and no implementation files were edited. Actual Pages asset-row shape, asset URLs, CSP compatibility, and real-sheet rendering remain unverified until the deferred upload/integration checks.

## Declined to judge

- Missing generated sheets and `data/posters.json`: expected pending generation/upload.
- Live Pages deployment and unchanged sprite-rendering behavior beyond the reviewed fixes: outside this round's scope.

Verdict: APPROVED
