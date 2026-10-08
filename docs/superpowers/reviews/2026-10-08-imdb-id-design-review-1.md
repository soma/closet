# Review: imdb-id-design, round 1

## Findings

- [N1] nit — `docs/superpowers/specs/2026-10-08-imdb-id-design.md:15`: `fill_imdb` updates entries across all clubs but emits one count-only log row. Existing club activity reads log rows by `club_id` (`src/server.js`, `club_state`), so clarify whether this is a global maintenance log that is intentionally absent from club activity, or emit a separate count per affected club. Add the corresponding log-scope assertion to the action tests.

## Validation and review limits

Reviewed the named design and the existing server's log filtering. Confirmed the proposed Wikidata identifiers against the official property definitions: [P6127, Letterboxd film ID](https://www.wikidata.org/wiki/Property:P6127) and [P345, IMDb ID](https://www.wikidata.org/wiki/Property:P345). Exact slug matching, conflict rejection, and preserving existing IDs avoid introducing title-based guesses.

No implementation tests or live backfill were run for this design-only review. Wikidata coverage and real Letterboxd extraction remain unverified. The assertion that concurrent fills are harmless still needs verification against actual host update semantics: assigning the same IMDb value does not by itself prove that a write preserves concurrent changes to other entry fields. Implementation should preserve those fields and verify the host's transaction/conflict behavior. Existing-entry repair is lazy until a qualifying club is opened; deployed data-flow completeness must be checked separately from the UI's dataset fallback.

## Declined to judge

- IMDb ratings, IMDb scraping, films without Letterboxd slugs, and Browse-card links: explicitly outside scope.
- Performing the backfill or mutating deployed shared data: not part of this design review.

Verdict: APPROVED

## Response

[N1] fixed -- design: `fill_imdb` writes one global maintenance row with an empty club_id, intentionally not shown in club activity; the action tests will assert it is absent from `club_state` logs.
Review-limits note: updates write the whole entry data object, as every existing action does, so a concurrent change to another field of the same entry could be overwritten; this is an existing limitation of the host's update semantics that can only be checked against the real host, and is flagged in the final report.
