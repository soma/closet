import json, pathlib, sys, tempfile, unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_letterboxd as f  # noqa: E402

FIX = ROOT / "tests/fixtures"


class Parsing(unittest.TestCase):
    def test_index(self):
        slugs, last = f.parse_index((FIX / "lists_index.html").read_text(encoding="utf-8"))
        self.assertEqual(slugs[0], "sander-laks-criterion-closet-picks")
        self.assertEqual(len(slugs), 3)
        self.assertEqual(last, 43)

    def test_list(self):
        visit, picks = f.parse_list("sander-laks-criterion-closet-picks", (FIX / "list.html").read_text(encoding="utf-8"))
        self.assertEqual(visit["visitor"], "Sander Lak")
        self.assertEqual(visit["visit_date"], "August 9, 2026")
        self.assertEqual(visit["occupation_guess"], "designer")
        self.assertEqual(visit["num_films"], len(picks))
        self.assertEqual([p[0] for p in picks], [1, 2, 3])
        self.assertIn(("crumb", "Crumb", 1994), [(p[1], p[2], p[3]) for p in picks])

    def test_film_without_json_ld_still_returns_a_row(self):
        row = f.parse_film("x", "X", 2000, "<html></html>")
        self.assertEqual((row["film_slug"], row["film_year"], row["runtime_min"]), ("x", 2000, None))

    def test_unrecognised_pages_raise_instead_of_parsing_as_empty(self):
        junk = "<html><body>Unexpected page</body></html>"
        with self.assertRaises(f.ParseError):
            f.parse_index(junk)
        with self.assertRaises(f.ParseError):
            f.parse_list("x", junk)
        listing = (FIX / "list.html").read_text(encoding="utf-8")
        with self.assertRaises(f.ParseError):
            f.parse_list("x", listing.split("<ul>")[0] + "</body></html>")  # title but no films


class Orchestration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)
        patcher = mock.patch.object(f, "CACHE", self.dir / "cache")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.index = (FIX / "lists_index.html").read_text(encoding="utf-8")
        self.listing = (FIX / "list.html").read_text(encoding="utf-8")

    def run_main(self, responses, out="out.json", extra=()):
        def fake_get(path, delay, refresh=False):
            body = responses.get(path)
            if body is None and path.startswith("/closetpicks/lists/page/"):
                body = responses["/closetpicks/lists/"]
            if isinstance(body, Exception):
                raise body
            if not refresh and f.cache_path(path).exists():
                return f.cache_path(path).read_text(encoding="utf-8")
            f.CACHE.mkdir(parents=True, exist_ok=True)
            f.cache_path(path).write_text(body, encoding="utf-8")
            return body
        with mock.patch.object(f, "get", fake_get), mock.patch.object(f, "parse_film", lambda s, t, y, p: {"film_slug": s, "film_title": t, "film_year": y}):
            return f.main(["--out", str(self.dir / out), "--delay", "0", *extra])

    def test_second_run_discovers_a_visit_added_to_the_index(self):
        base = {"/closetpicks/lists/": self.index, "/closetpicks/lists/page/2/": self.index,
                "/closetpicks/list/sander-laks-criterion-closet-picks/": self.listing}
        data_visits = {r[0] for r in json.loads((ROOT / "data/closet.json").read_text(encoding="utf-8"))["visits"]["rows"]}
        self.assertNotIn("sander-laks-criterion-closet-picks", data_visits)
        grown = self.index.replace("sander-laks-criterion-closet-picks", "brand-new-visit-picks", 1)
        responses = dict(base, **{"/closetpicks/list/brand-new-visit-picks/": self.listing})
        self.assertEqual(self.run_main(base, "first.json", ["--max-visits", "1"]), 0)
        self.assertIn("sander-laks-criterion-closet-picks", [r[0] for r in json.loads((self.dir / "first.json").read_text())["visits"]["rows"]])
        responses["/closetpicks/lists/"] = grown
        self.assertEqual(self.run_main(responses, "second.json", ["--max-visits", "1"]), 0)
        self.assertIn("brand-new-visit-picks", [r[0] for r in json.loads((self.dir / "second.json").read_text())["visits"]["rows"]])

    def test_unrecognised_list_aborts_keeps_existing_output_and_evicts_cache(self):
        out = self.dir / "out.json"
        out.write_text("previous")
        responses = {"/closetpicks/lists/": self.index, "/closetpicks/lists/page/2/": self.index,
                     "/closetpicks/list/sander-laks-criterion-closet-picks/": "<html>nope</html>"}
        self.assertEqual(self.run_main(responses, extra=["--max-visits", "1"]), 3)
        self.assertEqual(out.read_text(), "previous")
        self.assertFalse(f.cache_path("/closetpicks/list/sander-laks-criterion-closet-picks/").exists())

    def test_block_stops_without_writing(self):
        out = self.dir / "out.json"
        out.write_text("previous")
        responses = {"/closetpicks/lists/": f.Blocked("403")}
        self.assertEqual(self.run_main(responses), 2)
        self.assertEqual(out.read_text(), "previous")


if __name__ == "__main__":
    unittest.main()
