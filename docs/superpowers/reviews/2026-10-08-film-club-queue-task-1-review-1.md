# Review: film-club-queue-task-1, round 1

## Findings

- [S1] should — `src/club.js:54` (also `renderClubs`, line 70): Club loads unconditionally assign their response to the shared `CLUB.data`, even if the selected club has changed while awaiting the host. Starting a load for A, switching to B, resolving B, then resolving A leaves `CLUB.id === "B"` and A's data in `CLUB.data`; reproduced with controlled promises against this module. A later render can show A's heading/feed while suggestion and search actions submit B's club ID. A stale rejected request also resets the current selection via the unconditional error callback. Capture the requested club and a request generation, ignore stale successes and failures, and bind rendered actions to the club whose data is displayed. Add delayed-response browser coverage for switching clubs and navigating away during a load/action.

- [S2] should — `src/server.js:12`: Date validation accepts calendar values that JavaScript normalizes rather than rejects. `add_entry` accepts `watched_on: "2026-02-31"` and stores that impossible date verbatim; `validTime()` has the same issue for scheduling. Such rows produce misleading watched history and schedule ordering despite passing the server's validation. Validate calendar components (including leap years) and hour/minute bounds, or require an exact round-trip match after parsing. Test February 29 in leap/non-leap years, February 31, and invalid scheduled dates/times, asserting rejected actions leave entries and logs unchanged.

## Validation and review limits

- Reviewed `HEAD~1..HEAD`, ending at `8055624`, against the approved design: server actions, club UI/CSS, template/build integration, and tests.
- Ran `script/test` in a temporary export of HEAD using the existing virtual environment, outside the execution sandbox for Chromium: all 24 Python tests passed, including the Node server-test wrapper and browser flow tests.
- Reproduced the stale club response with controlled promises and the invalid date through the submitted host simulator. No implementation files were edited.
- Host-backed behavior remains unverified: the browser flow uses `tests/host_sim.js`, which executes reads and writes synchronously. It does not establish actual Pages API compatibility, viewer write permissions, identity shape, or concurrency guarantees for the one-current/one-rating/idempotence invariants. The design's staged action checks remain necessary before claiming the shared app works.
- The suite lacks explicit co-director fixtures and browser coverage for out-of-band short/long picks required by the design; the corresponding implementation paths were inspected but those scenarios were not exercised here.

## Declined to judge

- Publishing, enabling shared data, and widening page grants: reserved for human steps by the design; no external writes were performed during this review.
- Membership/privacy, repeat-viewing support, reminders, and calendar feeds: outside this version's stated scope.

Verdict: CHANGES REQUESTED

## Response

[S1] fixed -- src/club.js: loads are sequenced (`clubLoadSeq`) and only stored when still current for the same club; stale successes and failures are ignored; every action in a rendered club is bound to that club's id (`d.club.id`) and no longer reads `CLUB.id` at click time. Browser tests with delayed `club_state` responses cover switching clubs (including a repaint afterwards) and navigating to the list during a load. Verified the test fails with the guard removed.
[S2] fixed -- src/server.js: dates and times must round-trip exactly through Date; node tests cover Feb 29 in leap and non-leap years, Feb 31, Apr 31, month 00/13, hour 25, minute 60, and assert rejected actions leave entries and log unchanged.
Review-limit notes addressed: added co-director fixtures (taken director skipped, picking takes both, feed-taken director) and browser coverage for out-of-band short and long picks. Real Pages host compatibility stays to be verified on the staged page, as the design says.
