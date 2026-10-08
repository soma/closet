# Review: my-closet-design, round 1

## Findings

- [S1] should — **Data (Pages shared data, through `server.js`)**, action definitions: The caller-only read promised for `closet_remove` lacks a specified trusted-identity binding. The existing simulator invokes `inputs(args)` before passing the trusted `actor` to `run(args, actor, rows, ids)` (`tests/host_sim.js:21,29`); its author filter is literal equality, with no actor substitution. Thus the stated read restriction cannot be implemented against the current test contract merely by adding `where: {author: ...}`. Using an author supplied in action arguments would not establish ownership. Specify and verify a host-supported actor binding for input reads, updating the simulator to match, or use the existing rating-action pattern: read candidate rows and select/check `row.author === actor` inside `run()` before any removal. Apply the same trusted ownership rule to add idempotence and the per-person cap. Include a test that forged author arguments cannot remove another person's pick or evade the caller's cap. This resolves an implementation/security-contract gap; it is not a claim that the live host lacks an actor-binding facility.

## Validation and review limits

- Reviewed `docs/superpowers/specs/2026-10-08-my-closet-design.md` against the current recommendation implementation, club ownership checks, routing context, and simulated host contract.
- The recommendation reuse, public-data model, own/other closet views, and proposed regression coverage otherwise fit the existing app. No additional actionable findings identified.
- This was a design review; no implementation tests were run. Live-host input binding, concurrency guarantees for idempotence/caps, and data-flow access semantics were not verified. No code or design files were changed.

Verdict: CHANGES REQUESTED

## Response

[S1] fixed -- design "Data": ownership comes only from the trusted `actor` passed to `run()`; the actions read the whole (small) collection and select the caller's rows with `row.author === actor`, as the rating actions do; add idempotence, the 200 cap and remove all use that rule, arguments naming an author are ignored; tests added for a forged `author` argument (cannot remove another person's pick, cannot evade the cap).
