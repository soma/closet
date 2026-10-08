import copy, io, json, pathlib, sys, unittest, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import backfill_imdb as b  # noqa: E402
import merge_data  # noqa: E402

DATA = json.loads((ROOT / "data/closet.json").read_text(encoding="utf-8"))


def response(pairs):
    return {"results": {"bindings": [{"lb": {"value": s}, "imdb": {"value": i}} for s, i in pairs]}}


def small():
    d = copy.deepcopy(DATA)
    d["films"]["rows"] = d["films"]["rows"][:6]
    cols = d["films"]["cols"]
    for r in d["films"]["rows"]:
        r[cols.index("imdb_id")] = ""
    return d, [r[0] for r in d["films"]["rows"]], cols.index("imdb_id")


class Backfill(unittest.TestCase):
    def test_lookup_matches_dedupes_and_flags_malformed(self):
        slugs = ["a", "b", "c", "d"]
        fetch = lambda chunk: response([("a", "tt0000001"), ("a", "tt0000001"), ("b", "tt0000002"), ("b", "tt0000009"), ("c", "nm0000001")])
        found, malformed = b.lookup(slugs, fetch, delay=0, sleep=lambda s: None)
        self.assertEqual(found, {"a": {"tt0000001"}, "b": {"tt0000002", "tt0000009"}})
        self.assertEqual(malformed, [("c", "nm0000001")])

    def test_chunks_of_150_with_a_pause_between_requests(self):
        calls, pauses = [], []
        fetch = lambda chunk: calls.append(len(chunk)) or response([])
        b.lookup([str(i) for i in range(320)], fetch, delay=7, sleep=pauses.append)
        self.assertEqual((calls, pauses), ([150, 150, 20], [7, 7]))

    def test_backfill_fills_blanks_only_and_reports(self):
        d, slugs, ii = small()
        d["films"]["rows"][1][ii] = "tt1111111"            # already set, Wikidata disagrees
        found = {slugs[0]: {"tt0000001"}, slugs[1]: {"tt0000002"}, slugs[2]: {"tt0000003", "tt0000004"}}
        out, stats = b.backfill(d, found)
        ids = [r[ii] for r in out["films"]["rows"]]
        self.assertEqual(ids[:3], ["tt0000001", "tt1111111", ""])    # filled, kept, conflict left blank
        self.assertEqual((stats["filled"], stats["already_set"], stats["conflicting"], stats["missing"]), (1, 1, [slugs[2]], 3))
        self.assertEqual(d["films"]["rows"][0][ii], "", "input is not mutated")
        out, stats = b.backfill(d, found, overwrite=True)
        self.assertEqual(out["films"]["rows"][1][ii], "tt0000002")
        self.assertTrue(all(not r[ii] or merge_data.IMDB_RE.match(r[ii]) for r in out["films"]["rows"]))

    def test_429_waits_as_told_then_retries_and_gives_up_after_four_attempts(self):
        waits = []
        def err():
            return urllib.error.HTTPError("u", 429, "slow down", {"Retry-After": "120"}, io.BytesIO())
        outcomes = [err(), err(), response([("a", "tt0000001")])]
        def fetch(chunk):
            o = outcomes.pop(0)
            if isinstance(o, Exception):
                raise o
            return o
        self.assertEqual(b.polite_fetch(["a"], fetch, waits.append)["results"]["bindings"][0]["lb"]["value"], "a")
        self.assertEqual(waits, [120, 120])
        always = lambda chunk: (_ for _ in ()).throw(err())
        with self.assertRaises(urllib.error.HTTPError):
            b.polite_fetch(["a"], always, lambda s: None)

    def test_a_failed_lookup_leaves_the_dataset_file_untouched(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "closet.json"
            path.write_bytes((ROOT / "data/closet.json").read_bytes())
            before = path.read_bytes()
            with mock.patch.object(merge_data, "DATA", path), \
                 mock.patch.object(b, "lookup", side_effect=urllib.error.URLError("network down")):
                self.assertEqual(b.main([]), 2)
            self.assertEqual(path.read_bytes(), before)

    def test_other_http_errors_are_not_retried(self):
        n = []
        def boom(chunk):
            n.append(1)
            raise urllib.error.HTTPError("u", 500, "boom", {}, io.BytesIO())
        with self.assertRaises(urllib.error.HTTPError):
            b.polite_fetch(["a"], boom, lambda s: None)
        self.assertEqual(len(n), 1)


if __name__ == "__main__":
    unittest.main()
