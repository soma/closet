# Review: film-club-queue-task-1, round 2

## Findings

- [S1] should — `src/club.js:60` and `src/club.js:81`: Stale rejections still bypass the request-generation guard. The sequence check runs only after a successful `await`; the rejection callback checks only the club ID. Reproduced by starting loads while navigating A → B → A, resolving the latest A request successfully, then rejecting the original A request: the old failure resets `CLUB.id` to `null`, writes the list URL, and replaces the successfully loaded club with an error. The new browser test exercises delayed successes, so it misses this remaining part of round 1 [S1]. Apply the generation/selection check to rejected loads before propagating them to UI error handlers, and add a controlled rejected-response regression for returning to the same club while an earlier request is pending.

## Previous findings

- [S1] still open — Successful responses are now sequenced and rendered actions are bound to the displayed club's ID, fixing the cross-club action problem. Stale failures for a revisited club still affect the current view, as described above.
- [S2] resolved — Dates and times must now round-trip exactly. Regression tests reject impossible dates/times without changing entries or logs and accept a valid leap day.

## Validation and review limits

Reviewed `HEAD~2..HEAD`, ending at `a1e724a`, and the round 1 responses. Ran `script/test` in a temporary export of HEAD using the existing virtual environment, outside the execution sandbox for Chromium: all 26 tests passed, including browser tests and the Node server-test wrapper. Independently reproduced the remaining rejection race with controlled promises against `src/club.js` and its `renderClubs` error handler.

The added co-director and out-of-band short/long tests address the previous coverage notes. Actual Pages host compatibility, viewer permissions, identity shape, and concurrency guarantees remain unverified; the design's staged checks are still required. No implementation files were edited.

## Declined to judge

- Publishing, enabling shared data, and widening grants: human steps outside this code review.
- Membership/privacy, repeat-viewing support, reminders, and calendar feeds: outside this version's stated scope.

Verdict: CHANGES REQUESTED

## Response

[S1] fixed -- src/club.js `loadClub` applies the sequence and selection check to rejected loads too, returning false for a stale failure; only the latest request for the selected club can surface an error. New browser regression (A slow-and-failing, then B, then A fast) fails with the check removed and passes with it.
