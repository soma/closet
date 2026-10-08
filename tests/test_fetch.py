import pathlib, sys, unittest

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


if __name__ == "__main__":
    unittest.main()
