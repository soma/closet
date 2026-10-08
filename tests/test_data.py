import copy, json, pathlib, re, subprocess, sys, tempfile, unittest, base64, gzip

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build, merge_data  # noqa: E402

DATA = json.loads((ROOT / "data/closet.json").read_text(encoding="utf-8"))


def table(cols, rows):
    return {"cols": cols, "rows": rows}


def incoming(visit="new-visit", film="new-film", n=1):
    vc = DATA["visits"]["cols"]
    visit_row = {c: "" for c in vc}
    visit_row.update(visit_slug=visit, visit_title="New", visitor="X", num_films=n)
    fc = DATA["films"]["cols"]
    film_row = {c: None for c in fc}
    film_row.update(film_slug=film, film_title="New Film", film_year=2026)
    return {
        "visits": table(vc, [[visit_row[c] for c in vc]]),
        "films": table(fc, [[film_row[c] for c in fc]]),
        "picks": table(DATA["picks"]["cols"],
                       [[visit, i + 1, film, "New Film", 2026] for i in range(n)]),
    }


class BuiltPage(unittest.TestCase):
    def test_built_blob_round_trips_to_canonical_json(self):
        html = build.build()
        blob = re.search(r'const DATA_B64 = "([^"]*)";', html).group(1)
        self.assertEqual(json.loads(gzip.decompress(base64.b64decode(blob))), DATA)
        def decoded(path):
            page = (ROOT / path).read_text(encoding="utf-8")
            return json.loads(gzip.decompress(base64.b64decode(re.search(r'const DATA_B64 = "([^"]*)";', page).group(1)))), page
        posters = ROOT / "data/posters.json"
        for target in ("index.html", "dist/index.html"):
            data, page = decoded(target)
            self.assertEqual(data, DATA, target)
        # the GitHub Pages file always hotlinks; the Pages upload carries the sprite map when there is one
        self.assertIn("const POSTER_MAP = null;", decoded("index.html")[1])
        dist = decoded("dist/index.html")[1]
        if posters.exists():
            self.assertIn("const POSTER_MAP = " + posters.read_text(encoding="utf-8").strip() + ";", dist)
        else:
            self.assertIn("const POSTER_MAP = null;", dist)
        self.assertEqual(decoded("index.html")[1], html)


class PageUrl(unittest.TestCase):
    def test_pages_url_goes_into_the_pages_upload_only(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"PAGES_URL": "https://pages.example/p/club-x"}):
            build.build()
        self.assertIn('const PAGE_URL = "https://pages.example/p/club-x";', (ROOT / "dist/index.html").read_text(encoding="utf-8"))
        committed = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('const PAGE_URL = "";', committed)
        self.assertNotIn("pages.example", committed)
        build.build()   # leave the default build in place

    def test_pages_url_must_be_plain(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"PAGES_URL": 'https://x/"; alert(1); "'}):
            with self.assertRaises(AssertionError):
                build.build()
        build.build()


class ImdbData(unittest.TestCase):
    def test_every_imdb_id_is_blank_or_well_formed(self):
        cols = DATA["films"]["cols"]
        i = cols.index("imdb_id")
        bad = [r[0] for r in DATA["films"]["rows"] if r[i] and not merge_data.IMDB_RE.match(r[i])]
        self.assertEqual(bad, [])

    def test_merge_rejects_a_malformed_imdb_id(self):
        inc = incoming()
        cols = inc["films"]["cols"]
        inc["films"]["rows"][0][cols.index("imdb_id")] = "nm0000001"
        with self.assertRaisesRegex(merge_data.MergeError, "invalid imdb_id"):
            merge_data.merge(DATA, inc)

    def test_build_injects_the_imdb_map_into_server_js(self):
        build.build()
        server = (ROOT / "dist/server.js").read_text(encoding="utf-8")
        self.assertNotIn("__FILM_IMDB__", server)
        cols = DATA["films"]["cols"]
        with_id = next((r for r in DATA["films"]["rows"] if r[cols.index("imdb_id")]), None)
        if with_id:
            self.assertIn(f'"{with_id[0]}":"{with_id[cols.index("imdb_id")]}"', server)


class Validation(unittest.TestCase):
    def test_existing_dataset_is_valid(self):
        self.assertEqual(merge_data.validate(DATA), [])

    def test_duplicate_orphan_gap_and_count_are_reported(self):
        bad = copy.deepcopy({k: v for k, v in DATA.items() if k != "_meta"})
        bad["visits"]["rows"].append(list(bad["visits"]["rows"][0]))
        bad["picks"]["rows"].append(["ghost-visit", 1, "ghost-film", "G", 2000])
        bad["picks"]["rows"].pop(0)
        text = "\n".join(merge_data.validate(bad))
        for needle in ("duplicate visits", "unknown visit", "unknown film", "not contiguous", "num_films"):
            self.assertIn(needle, text)


class Merge(unittest.TestCase):
    def test_adds_new_visit_and_is_idempotent(self):
        once, stats = merge_data.merge(DATA, incoming())
        self.assertEqual(stats["visits"]["added"], 1)
        self.assertEqual(len(once["visits"]["rows"]), len(DATA["visits"]["rows"]) + 1)
        twice, stats2 = merge_data.merge(once, incoming())
        self.assertEqual({k: twice[k] for k in once if k != "_meta"}, {k: once[k] for k in once if k != "_meta"})
        self.assertEqual((stats2["visits"]["added"], stats2["picks"]["added"]), (0, 0))

    def test_existing_rows_win_without_overwrite(self):
        inc = incoming(visit=DATA["visits"]["rows"][0][0], film="brand-new", n=2)
        merged, stats = merge_data.merge(DATA, inc)
        self.assertEqual(stats["picks"]["skipped"], 2)
        self.assertEqual(merged["picks"], DATA["picks"])

    def test_invalid_merge_changes_nothing(self):
        inc = incoming(n=2)
        inc["visits"]["rows"][0][inc["visits"]["cols"].index("num_films")] = 5
        with self.assertRaises(merge_data.MergeError):
            merge_data.merge(DATA, inc)

    def test_conflicting_incoming_duplicates_are_rejected_in_both_modes(self):
        for table, title_col in (("films", "film_title"), ("visits", "visit_title")):
            inc = incoming()
            cols = inc[table]["cols"]
            dup = list(inc[table]["rows"][0])
            dup[cols.index(title_col)] = "Conflicting"
            inc[table]["rows"].append(dup)
            for overwrite in (False, True):
                with self.assertRaisesRegex(merge_data.MergeError, "duplicate key"):
                    merge_data.merge(DATA, inc, overwrite)

    def test_overwrite_replaces_a_visit_and_its_picks_whole(self):
        slug = DATA["visits"]["rows"][0][0]
        old = len([r for r in DATA["picks"]["rows"] if r[0] == slug])
        inc = incoming(visit=slug, film="brand-new", n=2)
        merged, stats = merge_data.merge(DATA, inc, overwrite=True)
        picks = [r for r in merged["picks"]["rows"] if r[0] == slug]
        self.assertEqual([r[2] for r in picks], ["brand-new", "brand-new"])
        self.assertEqual(stats["picks"]["replaced"], 2)
        self.assertEqual(len(merged["picks"]["rows"]), len(DATA["picks"]["rows"]) - old + 2)

    def test_csv_directory_import(self):
        import csv
        inc = incoming()
        with tempfile.TemporaryDirectory() as d:
            for name, t in inc.items():
                with open(pathlib.Path(d) / f"{name}.csv", "w", newline="", encoding="utf-8") as fh:
                    w = csv.writer(fh)
                    w.writerow(t["cols"])
                    w.writerows([["" if v is None else v for v in r] for r in t["rows"]])
            read = merge_data.read_csv_dir(pathlib.Path(d))
        merged, stats = merge_data.merge(DATA, read)
        self.assertEqual((stats["visits"]["added"], stats["films"]["added"], stats["picks"]["added"]), (1, 1, 1))

    def test_main_leaves_canonical_file_untouched_on_invalid_input(self):
        before = (ROOT / "data/closet.json").read_bytes()
        inc = incoming(n=2)
        inc["visits"]["rows"][0][inc["visits"]["cols"].index("num_films")] = 5
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d) / "bad.json"
            f.write_text(json.dumps(inc))
            self.assertEqual(merge_data.main([str(f)]), 1)
        self.assertEqual((ROOT / "data/closet.json").read_bytes(), before)

    def test_non_visit_lists_are_excluded_with_their_picks_and_orphan_films(self):
        inc = incoming()
        vc, pc, fc = inc["visits"]["cols"], inc["picks"]["cols"], inc["films"]["cols"]
        meta_visit = list(inc["visits"]["rows"][0]); meta_visit[vc.index("visit_slug")] = "all-time-top"
        inc["visits"]["rows"].append(meta_visit)
        shared = list(inc["films"]["rows"][0]); shared[fc.index("film_slug")] = "only-in-meta"
        inc["films"]["rows"].append(shared)
        inc["picks"]["rows"] += [["all-time-top", 1, "new-film", "New Film", 2026], ["all-time-top", 2, "only-in-meta", "Meta", 2026]]
        merged, stats = merge_data.merge(DATA, inc, excluded=["all-time-top"])
        self.assertEqual(stats["excluded_lists"], ["all-time-top"])
        slugs = lambda t, i: {r[i] for r in merged[t]["rows"]}
        self.assertNotIn("all-time-top", slugs("visits", 0))
        self.assertNotIn("only-in-meta", slugs("films", 0), "film nothing else picks is not added")
        self.assertIn("new-film", slugs("films", 0), "film also picked by a real visit is kept")
        self.assertEqual(sum(1 for r in merged["picks"]["rows"] if r[0] == "all-time-top"), 0)
        self.assertEqual(merge_data.validate({k: v for k, v in merged.items() if k != "_meta"}), [])

    def test_canonical_json_with_meta_can_be_merged_again(self):
        merged, stats = merge_data.merge(DATA, DATA)
        self.assertEqual({k: merged[k] for k in ("visits", "picks", "films")}, {k: DATA[k] for k in ("visits", "picks", "films")})
        self.assertEqual((stats["visits"]["added"], stats["films"]["added"], stats["picks"]["added"]), (0, 0, 0))

    def test_an_excluded_list_sharing_a_film_with_an_existing_visit_does_not_swallow_the_films_update(self):
        fc, vc = DATA["films"]["cols"], DATA["visits"]["cols"]
        picked = DATA["picks"]["rows"][0][2]                      # a film an existing visit already picks
        film = next(r for r in DATA["films"]["rows"] if r[0] == picked)
        fixed = list(film); fixed[fc.index("runtime_min")] = 999
        meta = {c: "" for c in vc}; meta.update(visit_slug="meta-list", num_films=1)
        inc = {"films": {"cols": fc, "rows": [fixed]},
               "visits": {"cols": vc, "rows": [[meta[c] for c in vc]]},
               "picks": {"cols": DATA["picks"]["cols"], "rows": [["meta-list", 1, picked, "T", 2000]]}}
        merged, stats = merge_data.merge(DATA, inc, overwrite=True, excluded=["meta-list"])
        got = next(r for r in merged["films"]["rows"] if r[0] == picked)
        self.assertEqual(got[fc.index("runtime_min")], 999, "the film-only correction is applied")
        self.assertEqual(stats["films"]["replaced"], 1)
        self.assertNotIn("meta-list", [r[0] for r in merged["visits"]["rows"]])

    def test_visitor_names_are_cleaned_when_the_title_was_left_in(self):
        c = merge_data.clean_visitor
        self.assertEqual(c("Danny McBride\u2019s Closet Picks"), "Danny McBride")
        self.assertEqual(c("Carla Sim\u00f3n's Closet Picks"), "Carla Sim\u00f3n")
        self.assertEqual(c("Adam Scott's Criterion Closet Picks"), "Adam Scott")
        self.assertEqual(c("Adam Scott"), "Adam Scott")
        self.assertEqual(c("Closet Picks"), "Closet Picks", "never reduce a name to nothing")

    def test_merge_then_build_keeps_new_rows(self):
        merged, _ = merge_data.merge(DATA, incoming())
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "src").mkdir(); (root / "data").mkdir()
            for name in ("template.html", "club.js", "club.css", "server.js"):
                (root / "src" / name).write_text((ROOT / "src" / name).read_text(encoding="utf-8"), encoding="utf-8")
            (root / "data/closet.json").write_text(merge_data.dump(merged), encoding="utf-8")
            html = build.build(root)
            blob = re.search(r'const DATA_B64 = "([^"]*)";', html).group(1)
            built = json.loads(gzip.decompress(base64.b64decode(blob)))
            self.assertIn("new-visit", [r[0] for r in built["visits"]["rows"]])
            self.assertEqual(len(built["visits"]["rows"]), len(DATA["visits"]["rows"]) + 1)


if __name__ == "__main__":
    unittest.main()
