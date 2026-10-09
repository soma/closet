# Review: imdb-ratings-design, round 1

## Findings

- [S1] should — **Source and licence**: The conclusion that this shared hobby app fits the dataset licence is not established by excluding ratings from Git and restricting page access. IMDb's linked non-commercial guidance expressly restricts altering, republishing, or repurposing the data into movie-information databases, with an exception for individual personal use. A shared Pages app is not clearly covered by that exception. Replace the unconditional compatibility claim with an explicit unresolved requirement: establish permission for this shared display before enabling the ratings upload, or constrain the feature to a permitted use. Also use the prescribed attribution if proceeding under these terms: “Information courtesy of IMDb (https://www.imdb.com). Used with permission.” The proposed footer omits part of it. These points come from [IMDb's non-commercial usage guidance](https://help.imdb.com/article/imdb/general-information/can-i-use-imdb-data-in-my-software/G5JTRESSHJBBHTGX); this finding identifies a design assumption requiring resolution, not a definitive legal conclusion about the app.

## Validation and review limits

- Reviewed the design against `scripts/build.py`, the update Makefile, staging workflow, existing rating displays, and build tests.
- [IMDb's dataset documentation](https://data.imdb.com/non-commercial-datasets/) confirms the gzip/TSV format, daily refresh, and the three proposed ratings columns. Its linked usage guidance was checked on 2026-10-09.
- The separate Pages-only data variant, atomic refresh behavior, staging fingerprint input, and proposed tests otherwise fit the existing architecture. The existing build round-trip test will need to accommodate the enriched Pages variant while retaining the canonical root-data assertion.
- This was a design review; no implementation tests or dataset downloads were performed. No code or design files were changed, and no permission for shared redistribution was established.

Verdict: CHANGES REQUESTED

## Response

[S1] fixed -- the design no longer claims the licence is compatible: "Source and licence" now states the restriction on republishing or repurposing and that permission has NOT been established, records the user's explicit decision (2026-10-09, after being told) to build it enabled and accept the risk, lists the exposure limits (never committed, Pages upload only, public build shows none, deletable switch), and uses a credit that does not include "Used with permission" because we do not have it. Resolving the permission question remains with the user.
