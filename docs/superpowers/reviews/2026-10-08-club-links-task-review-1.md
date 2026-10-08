# Review: club-links-task, round 1

## Findings

- [N1] nit — `src/club.js:169`: The link instructions say to append the fragment to the page address without accounting for an existing fragment. For an address already ending in `#clubs/id1`, following this literally produces `#clubs/id1#clubs/id1`, which the router treats as an unknown club ID. Say to replace any existing `#…` portion, or provide a complete copyable link when the host's public page URL is available.

## Validation and review limits

Reviewed `HEAD~1..HEAD`, ending at `27357d4`, including the generated HTML changes. The unknown-club error now survives loading the club list, and the new tests cover direct entry, reload, and fallback to the list with an error and corrected hash.

Ran `script/test` in a temporary export of HEAD using the existing virtual environment, outside the execution sandbox for Chromium: all 29 tests passed, including both new deep-link tests. No implementation files were edited. The browser tests exercise local HTML with the simulated Pages host; forwarding a public host-page fragment into the hosted app remains unverified.

## Declined to judge

- Actual Pages deployment, outer-page/iframe routing, and host permissions: not exercised by this local code review.
- Unchanged club server actions and other explorer features: outside this round's requested artifact scope.

Verdict: APPROVED

## Response

[N1] fixed -- the hint now says to replace anything after `#` in the page address.
