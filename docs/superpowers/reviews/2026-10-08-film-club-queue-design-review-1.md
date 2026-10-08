# Review: film-club-queue-design, round 1

## Findings

- [S1] should — `docs/superpowers/specs/2026-10-08-film-club-queue-design.md:12` (The rule; also Build and test, line 33): The rule requires ignoring short films, but the eligibility decisions define only an upper runtime limit and never define how to identify a short. The canonical film schema has runtime but no short/feature classification, and the current dataset includes 156 films below 40 minutes. Those films satisfy the stated runtime eligibility check and can enter the simulated queue, consuming a director's slot. Specify a concrete minimum runtime with an inclusive/exclusive boundary, or an explicit classification source, and add tests proving shorts are excluded and the boundary behaves as intended. Listing shorts as out of scope does not implement their required exclusion.

## Validation and review limits

Reviewed the named design and inspected the canonical dataset's film columns and runtime values to confirm the eligibility gap. No implementation tests were run for this design-only review. Pages API behavior, author identity/name resolution, concurrent action semantics, and the disabled-shared-data state have not been verified against the host; the proposed staged integration check remains necessary.

## Declined to judge

- Publishing, widening grants, and enabling shared data: explicitly reserved for human steps by this design.
- RSS/calendar feeds and the club's weekday: explicitly outside scope.

Verdict: CHANGES REQUESTED

## Response

[S1] disputed -- the user explicitly said to ignore the short-film part of their rule to keep things simple, so shorts are deliberately not filtered. The design now says so ("Suggestion rule") and lists filtering shorts as out of scope. The design was also substantially widened by the user after this review (multiple clubs, manual picks, ratings, scheduling, current film), so the whole document is open for review.
