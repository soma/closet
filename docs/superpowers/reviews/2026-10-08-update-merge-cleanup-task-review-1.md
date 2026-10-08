# Review: update-merge-cleanup-task, round 1

## Findings

- [S1] should — `scripts/merge_data.py:111`: `prepare()` assumes every incoming top-level value is a table with `cols` and `rows`. Canonical dataset JSON also contains `_meta`, so feeding a canonical export or a previous merge result into the merger now raises `KeyError: 'cols'`, even with no exclusions. Reproduced with `merge(data, data)`: the parent commit succeeds, while this commit crashes. Copy/prepare only the supported tables and preserve the existing metadata policy; add a regression test for incoming canonical JSON containing `_meta`.

- [S2] should — `scripts/merge_data.py:129–133`: After dropping any excluded visit, film filtering retains only films referenced by the remaining **incoming** picks. This silently drops updates for films used by existing real visits when those visits are absent from the incremental input. Reproduced with an existing film picked eight times in the canonical dataset: a film-only runtime correction applies with `overwrite=True`, but adding an excluded visit that picks the same film causes the correction to disappear and reports zero film replacements. Remove only films made orphaned by the exclusion, considering surviving existing picks as well as incoming picks; preserve unrelated film-only updates. Add coverage for an excluded list sharing a film with an existing visit that is not repeated in the input.

## Validation and review limits

- Reviewed only commit `a665df39a0e33ea0ab00846aa39c5e01a36769a6`, including the Orchestration test-isolation changes. The later mechanical data commit, the user's uncommitted changes to `scripts/fetch_letterboxd.py` and `README.md`, and the rest of their `tests/test_fetch.py` changes were excluded and were not reviewed.
- `script/test` passed all 67 tests in an isolated archive of the reviewed commit. `git diff --check a665df3^ a665df3` passed. The two findings were reproduced separately against that archive; neither case is covered by the current tests.
- The new exclusion/shared-new-film and visitor-cleanup tests pass, and Orchestration tests now use temporary empty datasets with the canonical columns. No live scraping or external data verification was performed.

Verdict: CHANGES REQUESTED

## Response

[S1] fixed -- `prepare()` copies only the dataset tables (`visits`, `picks`, `films`), so `_meta` and other keys are ignored; test merges the canonical JSON into itself (no changes, nothing added).
[S2] fixed -- an incoming film is dropped only when an excluded list picked it, no remaining incoming pick does, and no existing pick does (`existing_films`, computed in `merge`); every other incoming film, including film-only corrections, is kept. Test: an excluded list sharing a film with an existing, not-repeated visit no longer swallows that film's runtime correction under overwrite. Re-ran the real fetch output through the new logic: still 60 visits, 866 picks, 43 films, so the already merged and staged data is unchanged.
