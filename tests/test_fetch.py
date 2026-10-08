import http.server, json, pathlib, sys, tempfile, threading, unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_letterboxd as f  # noqa: E402

FIX = ROOT / "tests/fixtures"


class Requests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cache = mock.patch.object(f, "CACHE", pathlib.Path(self.tmp.name))
        cache.start()
        self.addCleanup(cache.stop)

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                browser_headers = (
                    self.headers.get("User-Agent", "").startswith("Mozilla/5.0")
                    and "text/html" in self.headers.get("Accept", "")
                    and "en" in self.headers.get("Accept-Language", "")
                    and self.headers.get("Upgrade-Insecure-Requests") == "1"
                )
                if self.path == "/first/":
                    status = 200 if browser_headers else 403
                elif self.path == "/second/":
                    status = 200 if browser_headers and self.headers.get("Cookie") == "session=test" else 403
                else:
                    status = int(self.path.strip("/"))
                self.send_response(status)
                if self.path == "/first/" and status == 200:
                    self.send_header("Set-Cookie", "session=test; Path=/")
                self.end_headers()
                self.wfile.write(b"<html>film club</html>")

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        base = mock.patch.object(f, "BASE", f"http://127.0.0.1:{server.server_port}")
        base.start()
        self.addCleanup(base.stop)

    def test_browser_headers_and_session_cookies_fetch_successive_pages(self):
        self.assertEqual(f.get("/first/", 0), "<html>film club</html>")
        self.assertEqual(f.get("/second/", 0), "<html>film club</html>")
        self.assertEqual(f.cache_path("/second/").read_text(), "<html>film club</html>")

    def test_blocked_responses_are_not_cached(self):
        for status in (403, 429):
            with self.subTest(status=status):
                path = f"/{status}/"
                with self.assertRaises(f.Blocked):
                    f.get(path, 0)
                self.assertFalse(f.cache_path(path).exists())


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

    def test_list_title_with_notes_class(self):
        page = (FIX / "list.html").read_text(encoding="utf-8")
        page = page.replace('class="title-1 prettify"', 'class="title-1 prettify has-notes"')
        visit, picks = f.parse_list("sander-laks-criterion-closet-picks", page)
        self.assertEqual(visit["visitor"], "Sander Lak")
        self.assertEqual(len(picks), 3)

    def test_film_imdb_id_comes_from_the_imdb_link_or_is_blank(self):
        page = '<a href="http://www.imdb.com/title/tt0050083/maindetails" class="micro-button">IMDb</a>'
        self.assertEqual(f.parse_film("x", "X", 2000, page)["imdb_id"], "tt0050083")
        self.assertEqual(f.parse_film("x", "X", 2000, "<html></html>")["imdb_id"], "")
        self.assertEqual(f.parse_film("x", "X", 2000, '<a href="https://www.imdb.com/name/nm0000001/">x</a>')["imdb_id"], "")

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
        # An empty dataset with the real columns: these tests must not depend on which
        # visits the real data/closet.json happens to contain at the moment.
        real = json.loads((ROOT / "data/closet.json").read_text(encoding="utf-8"))
        (self.dir / "data").mkdir()
        (self.dir / "data/closet.json").write_text(json.dumps(
            {t: {"cols": real[t]["cols"], "rows": []} for t in ("visits", "picks", "films")}), encoding="utf-8")
        root = mock.patch.object(f, "ROOT", self.dir)
        root.start()
        self.addCleanup(root.stop)
        self.index = (FIX / "lists_index.html").read_text(encoding="utf-8")
        self.listing = (FIX / "list.html").read_text(encoding="utf-8")

    def run_main(self, responses, out="out.json", extra=()):
        def fake_get(path, delay, refresh=False):
            body = responses.get(path)
            if body is None and path.startswith("/closetpicks/lists/page/"):
                body = responses["/closetpicks/lists/"]
            if body is None and path.startswith("/film/"):
                body = "<html></html>"          # parse_film is stubbed in these tests
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
