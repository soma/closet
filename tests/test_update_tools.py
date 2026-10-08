import json, pathlib, sys, tempfile, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import poster_status as ps  # noqa: E402
import update_summary as us  # noqa: E402


def dataset(visits, films, picks=()):
    return {
        "visits": {"cols": ["visit_slug"], "rows": [[v] for v in visits]},
        "picks": {"cols": ["visit_slug", "film_slug"], "rows": [list(p) for p in picks]},
        "films": {"cols": ["film_slug", "imdb_id", "runtime_min", "avg_rating", "directors", "poster_url"],
                  "rows": [list(f) for f in films]},
    }


class PosterStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = pathlib.Path(self.tmp.name)
        (self.cache / "sheets").mkdir()
        for n, body in (("sheet-00.webp", b"aaaa"), ("sheet-01.webp", b"bb")):
            (self.cache / "sheets" / n).write_bytes(body)
        (self.cache / "sheets.json").write_text(json.dumps({"sheet-00.webp": "h0", "sheet-01.webp": "h1"}))

    def test_everything_is_changed_until_marked_uploaded(self):
        self.assertEqual(ps.changed(self.cache), ["sheet-00.webp", "sheet-01.webp"])
        (self.cache / "uploaded.json").write_text(json.dumps({"sheet-00.webp": "h0", "sheet-01.webp": "OLD"}))
        self.assertEqual(ps.changed(self.cache), ["sheet-01.webp"])

    def test_files_list_matches_what_begin_asset_upload_needs(self):
        self.assertEqual(ps.files(["sheet-01.webp"], self.cache),
                         [{"key": "sheet-01", "name": "sheet-01.webp", "type": "image/webp", "size": 2}])


class Summary(unittest.TestCase):
    def test_counts_new_rows_and_lists_gaps_on_new_films_only(self):
        old = dataset(["v1"], [("f1", "", 90, 4.0, "A", "u")], [("v1", "f1")])
        new = dataset(["v1", "v2"], [("f1", "", 90, 4.0, "A", "u"), ("f2", "", 100, None, "B", "u"), ("f3", "tt0000003", 80, 3.0, "C", "")],
                      [("v1", "f1"), ("v2", "f2"), ("v2", "f3")])
        s = us.summarize(old, new)
        self.assertEqual((s["new_visits"], s["new_films"], s["new_picks"]), (1, 2, 2))
        gaps = s["missing_fields_on_new_films"]
        self.assertEqual((gaps["imdb_id"], gaps["avg_rating"], gaps["poster_url"]), (["f2"], ["f2"], ["f3"]))
        self.assertNotIn("f1", gaps["imdb_id"], "old films are not reported")

    def test_without_a_previous_commit_everything_counts_as_new(self):
        s = us.summarize(None, dataset(["v1"], [("f1", "tt0000001", 90, 4.0, "A", "u")], [("v1", "f1")]))
        self.assertEqual((s["new_visits"], s["new_films"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
