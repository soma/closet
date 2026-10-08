# Review: poster-refresh-task, round 1

## Findings

None.

## Validation and review limits

Reviewed `HEAD~1..HEAD`, ending at `4855561`. The app starts a 30-minute refresh after the initial poster-sheet lookup, only when a poster map and host API are available. Subsequent sprite creation uses the refreshed URL registry, providing a refresh interval shorter than the supplied one-hour signed-URL lifetime.

Ran `script/test` in a temporary export of HEAD using the existing virtual environment, outside the execution sandbox for Chromium: all 51 tests passed. Also disabled the refresh startup call only in that temporary export and reran the focused browser test: it failed waiting for the replacement URL. This confirms the new test detects the absence of periodic refresh in the tested execution.

The test uses a simulated host and virtual time. Real signed-URL expiration, background-tab suspension/resumption, and recovery from prolonged host failures were not exercised. Refresh updates the registry for subsequent renders; it does not rewrite background URLs on existing sprite elements. No repository implementation files were edited and no external data was changed.

## Declined to judge

- Poster generation/upload and unchanged sprite-sheet rendering: outside this narrow refresh change.
- Live Pages deployment and verification of the host's one-hour token lifetime: the lifetime was supplied as task context; no live integration run was performed.

Verdict: APPROVED
