# Review: club-participants-task, round 1

## Findings

- [S1] should — `src/closet.js:54–58`: Notifying the club about completed closet loading calls `renderView()`, which rebuilds the entire club form. Existing rating drafts and scheduling inputs live only in their DOM controls, so this unrelated background request silently discards the user's edits. Reproduced in Chromium: open a club with a watched film while holding the `closets` response, select score 8 and type a note, then resolve the response; both score and note reset to empty without submitting anything. Refresh only the participants/closet-link section, or preserve and restore draft form state and focus across the repaint. Add a delayed-closet-load regression that verifies an in-progress rating survives; the same preservation should apply when the background load fails.

## Validation and review limits

- Reviewed committed `HEAD~1..HEAD` (`6df1518..c04757f`) against the approved participant design, using an isolated committed archive.
- `script/test` passed all 109 tests, including the new join/leave ownership, log, union, closet-link, failed-load, and busy-control coverage. `git diff --check HEAD~1..HEAD` passed.
- A separate Chromium probe against the simulated host reproduced the rating-draft loss when the background closet lookup completed.
- Participant ownership, per-club separation, rating-derived participation, and latest-name selection otherwise match the design on inspection. No live Pages staging or multi-client transaction verification was performed.

Verdict: CHANGES REQUESTED

## Response

[S1] fixed -- when closets finish loading (or fail) the club view now refreshes only its participants list in place (`refreshParticipants`), not the whole club; the "disable at once" step at the start of a club action now disables only the buttons instead of repainting. Test: a score and note are entered while the `closets` response is held; after it resolves (success and failure runs) both values are intact, and the closet links appear in the success run. Verified the test fails with the whole-view repaint ('' != '8').
