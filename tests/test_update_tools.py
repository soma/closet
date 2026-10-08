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


class StageStatus(unittest.TestCase):
    def setUp(self):
        import stage_status
        self.ss = stage_status
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        for name in self.ss.INPUTS:
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            (self.root / name).write_text(name)
        self.mark = self.root / "staged.json"

    def stage(self):
        self.mark.write_text(json.dumps({"fingerprint": self.ss.fingerprint(self.root)}))

    def test_needs_staging_until_marked_then_again_after_any_input_change(self):
        self.assertTrue(self.ss.needs_staging(self.root, self.mark))
        self.stage()
        self.assertFalse(self.ss.needs_staging(self.root, self.mark))
        (self.root / "src/club.js").write_text("changed")
        self.assertTrue(self.ss.needs_staging(self.root, self.mark))

    def test_an_imdb_only_data_change_with_identical_counts_needs_staging(self):
        data = dataset(["v1"], [("f1", "", 90, 4.0, "A", "u")], [("v1", "f1")])
        (self.root / "data/closet.json").write_text(json.dumps(data))
        self.stage()
        data["films"]["rows"][0][1] = "tt0000001"                 # same visits, films and picks
        (self.root / "data/closet.json").write_text(json.dumps(data))
        s = us.summarize(json.loads(json.dumps(dataset(["v1"], [("f1", "", 90, 4.0, "A", "u")], [("v1", "f1")]))), data)
        self.assertEqual((s["new_visits"], s["new_films"], s["new_picks"]), (0, 0, 0))
        self.assertTrue(self.ss.needs_staging(self.root, self.mark), "counts say nothing changed, the fingerprint does")

    def test_a_failed_staging_is_retried_because_the_mark_is_only_written_after_success(self):
        (self.root / "data/closet.json").write_text("committed new data")
        # data committed and sheets marked uploaded, but staging failed: --mark-staged was never run
        self.assertTrue(self.ss.needs_staging(self.root, self.mark))


class MakeUpdateOrder(unittest.TestCase):
    """The real `update` rule, with the stage recipes replaced by stubs, run in parallel mode."""
    def makefile(self, failing=None):
        import re
        real = (ROOT / "Makefile").read_text(encoding="utf-8")
        rule = re.search(r"^update:\n(?:\t.*\n)+", real, re.M).group(0)
        stages = ["fetch", "merge", "backfill-imdb", "posters", "build", "test", "summary"]
        stubs = "".join(f"{s}:\n\t@{'false' if s == failing else 'true'}; echo {s}\n" for s in stages)
        # a stub that fails must stop the run before it echoes anything for later stages
        stubs = stubs.replace(f"@false; echo {failing}", f"@echo {failing}; false") if failing else stubs
        notpar = ".NOTPARALLEL:\n" if ".NOTPARALLEL:" in real else ""
        return notpar + ".PHONY: update " + " ".join(stages) + "\n" + rule + stubs

    def run_make(self, text, *flags):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "Makefile").write_text(text)
            return subprocess.run(["make", *flags, "update"], cwd=d, capture_output=True, text=True)

    def test_stages_run_in_order_even_with_parallel_flags(self):
        out = self.run_make(self.makefile(), "-j8")
        self.assertEqual(out.returncode, 0, out.stderr)
        stages = [l for l in out.stdout.split("\n") if l in ("fetch", "merge", "backfill-imdb", "posters", "build", "test", "summary")]
        self.assertEqual(stages, ["fetch", "merge", "backfill-imdb", "posters", "build", "test", "summary"])

    def test_a_failing_stage_stops_everything_after_it(self):
        out = self.run_make(self.makefile(failing="merge"), "-j8")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("fetch", out.stdout)
        for later in ("backfill-imdb", "posters", "build", "summary"):
            self.assertNotIn(later, out.stdout.split("\n"))
