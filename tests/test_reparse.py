import copy, json, pathlib, sys, tempfile, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import reparse_films as rp  # noqa: E402

DATA = json.loads((ROOT / "data/closet.json").read_text(encoding="utf-8"))
FILM = (ROOT / "tests/fixtures/film.html").read_text(encoding="utf-8")


def small(cast_a="", cast_b="Existing Cast"):
    d = copy.deepcopy(DATA)
    cols = d["films"]["cols"]
    d["films"]["rows"] = d["films"]["rows"][:3]
    for r, cast in zip(d["films"]["rows"], (cast_a, cast_b, "")):
        r[cols.index("top_cast")] = cast
    return d, [r[0] for r in d["films"]["rows"]], cols.index("top_cast")


class Reparse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = pathlib.Path(self.tmp.name)

    def test_blank_fields_are_filled_from_cached_pages_only(self):
        d, slugs, ci = small()
        for s in slugs[:2]:
            (self.cache / f"film_{s}.html").write_text(FILM, encoding="utf-8")      # third film has no cached page
        out, stats = rp.reparse(d, self.cache, ["top_cast"])
        rows = out["films"]["rows"]
        self.assertTrue(rows[0][ci].startswith("Graham Chapman; John Cleese"))
        self.assertEqual(rows[1][ci], "Existing Cast", "a non-blank value is kept without --overwrite")
        self.assertEqual(rows[2][ci], "", "no cached page, untouched")
        self.assertEqual((stats["updated"], stats["films"], stats["no_page"]), (1, 1, len(rows) - 2 + 0))
        self.assertEqual(d["films"]["rows"][0][ci], "", "input is not mutated")

    def test_overwrite_replaces_and_is_idempotent(self):
        d, slugs, ci = small()
        for s in slugs:
            (self.cache / f"film_{s}.html").write_text(FILM, encoding="utf-8")
        once, _ = rp.reparse(d, self.cache, ["top_cast"], overwrite=True)
        twice, stats = rp.reparse(once, self.cache, ["top_cast"], overwrite=True)
        self.assertEqual(once, twice)
        self.assertEqual(stats["updated"], 0)
        self.assertTrue(all(r[ci].startswith("Graham Chapman") for r in once["films"]["rows"]))

    def test_an_unknown_field_is_an_error(self):
        d, _, _ = small()
        with self.assertRaisesRegex(ValueError, "unknown field"):
            rp.reparse(d, self.cache, ["no_such_field"])

    def test_a_page_that_yields_nothing_never_blanks_a_value(self):
        d, slugs, ci = small(cast_a="Kept")
        (self.cache / f"film_{slugs[0]}.html").write_text("<html></html>", encoding="utf-8")
        out, _ = rp.reparse(d, self.cache, ["top_cast"], overwrite=True)
        self.assertEqual(out["films"]["rows"][0][ci], "Kept")


if __name__ == "__main__":
    unittest.main()
