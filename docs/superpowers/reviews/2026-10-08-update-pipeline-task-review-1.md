# Review: update-pipeline-task, round 1

## Findings

- [S1] should — `.claude/skills/update-closet/SKILL.md:27–29`: New-row counts and pending poster uploads do not establish that there is nothing to stage. Filling an existing film's IMDb ID changes `data/closet.json` and the built HTML/server map but produces zero new visits and films and no changed sheets, so this rule skips the requested update. It also prevents recovery after step 4 commits the data and step 6 marks the sheets uploaded but step 7 fails: the next invocation sees no work although the build was never staged. Check actual data/build changes and unfinished staging before exiting; allow resuming staging when there is no new commit to make. Cover an IMDb-only update and a retry after staging failure.

- [S2] should — `Makefile:44`: The update stages are sibling prerequisites, so Make does not enforce their required ordering with `-j` or inherited parallel `MAKEFLAGS`. Fetch and merge can run together, and merge and backfill can both read and overwrite `data/closet.json`; posters/build/test/summary can observe older or incomplete results. A harmless probe using the actual target and stubbed recipes under `make -j8` confirmed merge ran before fetch finished. Encode sequential execution or explicit dependencies so each stage finishes successfully before the next starts, and test ordering and failure propagation without network calls.

- [N1] nit — `scripts/backfill_imdb.py:92,101`: Restricting lookup to blank IDs leaves `backfill()`'s reporting inconsistent: it checks for absent lookup results before counting existing IDs. Every already-populated film is therefore counted as `missing` and printed as “not on Wikidata.” A reproduction with 1,465 existing IDs and one successful new lookup reports `filled 1, kept 0 already set, ... 1465 not on Wikidata`, although every film now has an ID. Count preserved IDs before inspecting lookup results, and assert the incremental run's statistics as well as its requested slugs.

## Validation and review limits

- Reviewed committed `HEAD~1..HEAD`, ending at `0bbf1a0`, using an isolated archive of the commit. The user's uncommitted edits to `scripts/fetch_letterboxd.py`, `tests/test_fetch.py`, and `README.md` were excluded and were not reviewed.
- `script/test` passed all 59 tests in the committed archive, including browser tests. `git diff --check HEAD~1..HEAD` passed.
- Additional local probes reproduced the IMDb-only zero-count summary, incorrect backfill statistics, and parallel Make ordering. Stable-slot and sheet-hash regression tests passed.
- No live scraping, Wikidata requests, Pages uploads, staging, or publishing were performed. The skill's real-host API instructions and asset replacement behavior remain unverified; local tests do not exercise that deployment workflow.

Verdict: CHANGES REQUESTED

## Response

[S1] fixed -- new scripts/stage_status.py: "needs staging" is a fingerprint of everything the Pages upload is built from (data, poster map, app sources, build script), recorded only after staging succeeds. The skill now decides "nothing to do" only when no uncommitted data changes, no sheets to upload and the fingerprint is current, and resumes at the first unfinished step. Tests: an IMDb-only change with identical counts, and a retry after a failed staging.
[S2] fixed -- Makefile: `.NOTPARALLEL:` plus `update` as sequential `$(MAKE)` lines so a failing stage stops the run. Tests run the real `update` rule with stubbed stages under `make -j8`: order preserved, a failing merge stops everything after it.
[N1] fixed -- backfill() counts already-set films before looking at lookup results; test asserts the incremental statistics (1 filled, N-1 kept, 0 missing).
