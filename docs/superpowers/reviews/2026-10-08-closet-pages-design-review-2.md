# Review: closet-pages-design, round 2

## Findings

- [S1] should — `docs/superpowers/specs/2026-10-08-closet-pages-app-design.md:14` (Data refresh; also Build, line 19): The merge script is specified to rewrite the embedded blob, while the build regenerates that blob from `data/closet.json`. The design does not require the merge to update that canonical JSON, so a subsequent build can discard refreshed visits. Specify that merging updates `data/closet.json`, validates the complete merged dataset before saving, and uses the build to regenerate both HTML artifacts. Add a merge-then-build regression check proving that the refreshed data survives rebuilding and repeated imports.
- [N1] nit — `docs/superpowers/specs/2026-10-08-closet-pages-app-design.md:31` (Testing): The proposed test command is `python3 -m unittest`, but AGENTS.md requires running tests with `script/test`. Specify `script/test` as the entry point, invoking the unit, round-trip, and browser checks beneath it.

## Previous findings

The round 1 review is unavailable: the reviews directory contains its `.request` file but no review, and there is no tracked review history. Previous finding IDs and their resolution status cannot be verified.

## Review limits

Reviewed only the named design. No implementation tests were run. Live source availability and the hosted Pages sandbox were not verified; the design explicitly leaves the refresh blocked and hosted preview validation pending. No additional findings are asserted for those deferred checks.

Verdict: CHANGES REQUESTED

## Response

[S1] fixed -- spec "Data refresh" and "Build": merge validates the full result and saves `data/closet.json`; build regenerates both HTML files; added a merge-then-build and repeated-import regression test.
[N1] fixed -- spec "Testing": `script/test` is the entry point.
