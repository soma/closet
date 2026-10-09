import datetime, gzip, io, json, pathlib, subprocess, sys, tempfile, unittest, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import imdb_ratings as ir  # noqa: E402

LAST_MODIFIED = "Thu, 08 Oct 2026 00:39:31 GMT"


def dataset(rows, header=ir.HEADER, eol="\n"):
    return gzip.compress((header + eol + eol.join("\t".join(map(str, r)) for r in rows) + eol).encode())


class Parsing(unittest.TestCase):
    def test_keeps_only_wanted_ids_and_rounds_to_one_decimal(self):
        raw = dataset([("tt0000001", "9.04", "855123"), ("tt0000002", "7.0", "10"), ("tt0000009", "5.5", "5")])
        got, stats = ir.read_ratings(raw, {"tt0000001", "tt0000002"})
        self.assertEqual(got, {"tt0000001": [9.0, 855123], "tt0000002": [7.0, 10]})
        self.assertEqual(stats["skipped"], 0)

    def test_invalid_rows_are_skipped_and_counted(self):
        raw = dataset([("tt0000001", "0.5", "10"), ("tt0000002", "11", "10"), ("tt0000003", "7", "0"), ("tt0000004", "abc", "5"),
                       ("tt0000005", "7.7", "-3"), ("tt0000006", "8.1", "20")])
        got, stats = ir.read_ratings(raw, {f"tt000000{i}" for i in range(1, 7)})
        self.assertEqual(got, {"tt0000006": [8.1, 20]})
        self.assertEqual(stats["skipped"], 5)

    def test_windows_line_endings_work(self):
        got, _ = ir.read_ratings(dataset([("tt0000001", "8.0", "100")], eol="\r\n"), {"tt0000001"})
        self.assertEqual(got, {"tt0000001": [8.0, 100]})

    def test_a_different_header_is_refused(self):
        with self.assertRaisesRegex(ir.RatingsError, "unexpected header"):
            ir.read_ratings(dataset([("tt0000001", "8.0", "100")], header="tconst\tscore\tvotes"), {"tt0000001"})

    def test_a_truncated_or_non_gzip_file_is_refused(self):
        raw = dataset([("tt%07d" % i, "7.0", "100") for i in range(2000)])
        with self.assertRaisesRegex(ir.RatingsError, "complete gzip"):
            ir.read_ratings(raw[: len(raw) // 2], {"tt0000001"})
        with self.assertRaisesRegex(ir.RatingsError, "complete gzip"):
            ir.read_ratings(b"<html>not found</html>", set())


class Resp:
    def __init__(self, body, last_modified=LAST_MODIFIED, length=None):
        self.body, self.headers = body, {"Last-Modified": last_modified, "Content-Length": str(len(body) if length is None else length)}
    def read(self): return self.body
    def __enter__(self): return self
    def __exit__(self, *a): return False


class Fetching(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "data").mkdir()
        films = {"cols": ["film_slug", "imdb_id"], "rows": [["a", "tt0000001"], ["b", "tt0000002"], ["c", ""], ["d", "tt0000004"]]}
        (self.root / "data/closet.json").write_text(json.dumps({"films": films}))
        self.raw = dataset([("tt0000001", "9.0", "1000"), ("tt0000002", "6.5", "20"), ("tt0000099", "5", "5")])
        self.calls = 0

    def opener(self, resp=None):
        def go(req, timeout=None):
            self.calls += 1
            self.last_request = req
            if isinstance(resp, Exception):
                raise resp
            return resp or Resp(self.raw)
        return go

    def out(self):
        return json.loads((self.root / "data/imdb_ratings.json").read_text())

    def test_update_writes_only_this_projects_ids_with_the_as_of_date(self):
        s = ir.update(self.root, opener=self.opener())
        self.assertEqual(self.out(), {"as_of": "2026-10-08", "ratings": {"tt0000001": [9.0, 1000], "tt0000002": [6.5, 20]}})
        self.assertEqual((s["ids"], s["rated"], s["unrated"]), (3, 2, 1))
        self.assertIn("closet-explorer", self.last_request.headers["User-agent"])

    def test_the_download_is_cached_for_a_day_then_refetched(self):
        t = [1000.0]
        ir.update(self.root, opener=self.opener(), now=lambda: t[0])
        ir.update(self.root, opener=self.opener(), now=lambda: t[0] + 3600)
        self.assertEqual(self.calls, 1, "one request serves the second run")
        ir.update(self.root, refresh=True, opener=self.opener(), now=lambda: t[0] + 3600)
        self.assertEqual(self.calls, 2, "--refresh asks again")
        import os
        gz = self.root / ".cache/imdb/title.ratings.tsv.gz"
        os.utime(gz, (t[0] - 2 * 86400, t[0] - 2 * 86400))
        ir.update(self.root, opener=self.opener(), now=lambda: t[0])
        self.assertEqual(self.calls, 3, "an old cache is replaced")

    def test_failures_leave_the_previous_file_and_cache_untouched(self):
        ir.update(self.root, opener=self.opener())
        before = (self.root / "data/imdb_ratings.json").read_bytes()
        cache_before = (self.root / ".cache/imdb/title.ratings.tsv.gz").read_bytes()
        for bad in (urllib.error.URLError("network down"), Resp(self.raw, length=len(self.raw) + 100),
                    Resp(dataset([("tt0000001", "9", "9")], header="a\tb\tc")), Resp(b"<html>oops</html>")):
            with self.assertRaises((ir.RatingsError, urllib.error.URLError)):
                ir.update(self.root, refresh=True, opener=self.opener(bad))
            self.assertEqual((self.root / "data/imdb_ratings.json").read_bytes(), before)
            self.assertEqual((self.root / ".cache/imdb/title.ratings.tsv.gz").read_bytes(), cache_before)

    def test_a_missing_last_modified_falls_back_to_today(self):
        r = Resp(self.raw); del r.headers["Last-Modified"]
        ir.update(self.root, opener=self.opener(r))
        self.assertEqual(self.out()["as_of"], datetime.date.today().isoformat())


class NeverCommitted(unittest.TestCase):
    def test_the_ratings_file_is_git_ignored_and_not_tracked(self):
        ignored = subprocess.run(["git", "check-ignore", "-q", "data/imdb_ratings.json"], cwd=ROOT)
        self.assertEqual(ignored.returncode, 0, "data/imdb_ratings.json must be git-ignored")
        tracked = subprocess.run(["git", "ls-files", "data/imdb_ratings.json"], cwd=ROOT, capture_output=True, text=True).stdout
        self.assertEqual(tracked.strip(), "")


if __name__ == "__main__":
    unittest.main()
