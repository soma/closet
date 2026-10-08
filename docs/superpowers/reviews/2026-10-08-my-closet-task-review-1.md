# Review: my-closet-task, round 1

## Findings

- [S1] should — `src/closet.js:51–62,98,115–118`: Loads initiated by the closet view and film popup supersede one another, but the winning popup load only refreshes toggles. It never paints the waiting closet view. Reproduced by delaying `closets`, navigating to `#closet`, then to `#film/12-angry-men` before loading completes, resolving all requests, and closing the popup: `CLOSET.rows` is populated and the address is `#closet`, but the main view stays on “Loading closets…”. Coordinate shared loads or notify all current consumers when the accepted load completes. Add a browser regression covering simultaneous view/popup consumers; the existing stale-response test checks only cached rows.

- [S2] should — `src/closet.js:65–75,95`: Setting `CLOSET.busy` does not repaint or disable existing controls until the action finishes, and `closetAct()` has no busy guard. A delayed popup add reproducibly leaves `CLOSET.busy === true` while the toggle's `disabled` property remains false. Repeated clicks can start overlapping mutations and refreshes, and one completion can clear the busy flag while another action remains pending. Disable visible mutation controls immediately and prevent concurrent action entry; cover delayed actions from both the popup and closet controls. This is explicitly required by the design's loading behavior.

- [S3] should — `src/closet.js:70–75,85–99`: Popup errors are invisible. Failed actions set `CLOSET.error`, but the popup renders only the toggle; initial popup loads also discard failures with an empty rejection handler. On Browse, a rejected add with “a closet holds at most 200 films” leaves the popup unchanged with no visible error. An initial load failure instead leaves a disabled “My closet…” control with no explanation. Show load/action errors at the popup control and provide a recovery path for a failed load. Test failures from a direct film link and from a toggle outside the closet tab.

- [S4] should — `src/closet.js:47`: “Other closets” breaks equal-overlap ties by larger closet size before name, contrary to the approved design's overlap-then-name order. A probe with Amy owning one film and Zoe owning two, each sharing one film with the caller, returns Zoe before Amy. Remove the extra size tie-breaker and add an equal-overlap, unequal-size test; the current browser fixture has distinct overlaps and cannot catch this deviation.

## Validation and review limits

- Reviewed committed `HEAD~1..HEAD` (`75590bc..88fa4ff`) against the approved My Closet design, using an isolated committed archive.
- `script/test` passed all 95 tests, including server-action ownership/cap tests and the new browser tests. `git diff --check HEAD~1..HEAD` passed.
- Separate Chromium probes against the simulated host reproduced the stranded loading view, enabled pending-action toggle, invisible action error, and tie-order mismatch.
- Trusted-actor filtering and recommendation parameterization match the design on inspection and in the existing tests. No live Pages staging or multi-client concurrency verification was performed; the simulator does not establish live-host transaction guarantees.

Verdict: CHANGES REQUESTED

## Response

[S1] fixed -- one shared load state (`loading`, `rows`, `loadError`) and a single `notifyClosets()` that repaints every consumer (the closet view and all popup toggles) whenever the latest load finishes; `ensureClosets()` never starts a second load while one is in flight. Test: the view starts a delayed load, a film popup asks while it is in flight, and after closing the popup the view shows "My picks" with exactly one load. Verified it fails with the repaint removed.
[S2] fixed -- `closetAct` ignores a call while busy and notifies at once, so every control is disabled immediately (view buttons and popup toggle). Tests: a delayed add from the popup (disabled at once, a second click counts as one call) and a delayed remove from the closet view (all buttons disabled, a second Remove ignored).
[S3] fixed -- the popup toggle shows `closet-toggle-msg` with action and load errors and becomes "Retry my closet" after a failed load; the closet tab shows the load error with a Retry button. Tests: a failed add outside the closet tab (message, then a working retry clears it), a failed load from a direct film link (message, Retry works), a failed load on the closet tab.
[S4] fixed -- the extra closet-size tie-break is removed; equal overlap is ordered by name. Test with equal overlap and unequal sizes (Amy 1 film, Zoe 2, both sharing one).
