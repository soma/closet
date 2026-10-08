# Review: film-club-queue-design, round 2

## Findings

- [S1] should — `docs/superpowers/specs/2026-10-08-film-club-queue-design.md:21` (Feed model): The current-film rule is contradictory. Current is defined as the first planned entry by schedule order, but it also stays current until watched or removed. If A is current and a member schedules B earlier than A, sorting selects B while the persistence rule requires A. Adding a dated entry before an undated current film or marking an older scheduled film unwatched creates the same conflict. Specify whether current is recomputed after scheduling/add/unwatch changes or explicitly pinned until completion/removal. If pinned, describe how it is stored and how the next current entry is selected. Add tests for these transitions so the UI and server implement the same rule.

## Previous findings

- Round 1 [S1] withdrawn — The revised design explicitly records the user's decision to drop the short-film restriction and excludes filtering shorts from scope. No cutoff is needed under the revised requirement.

## Validation and review limits

Reviewed the full revised design, including multiple clubs, manual picks, ratings, scheduling, logging, and access, plus the round 1 response. This is a design-only review; no implementation tests were run. Host write permissions, concurrent action behavior, and staged integration remain unverified. The design correctly retains a staged check before declaring the shared feature working.

## Declined to judge

- Publishing, widening grants, and enabling shared data: reserved for human steps.
- Membership/privacy, repeat-viewing support, reminders, and calendar feeds: not required by this version's stated model and scope.

Verdict: CHANGES REQUESTED

## Response

[S1] fixed -- "Feed model": current is pinned, with states current/upcoming/watched, an at-most-one-current invariant, and explicit transitions (add, make current, mark watched, unwatch, remove) including how the next current is chosen; tests listed for the transitions.
Round 1 [S1] note: the user reversed their earlier decision and now wants shorts excluded, so round 1 [S1] was right and is reinstated and fixed: shorts are runtime <= 40 minutes, eligible range 41..180 inclusive, named constants, boundary tests at 40/41 and 180/181; out-of-band picks may still be shorts or long films.
