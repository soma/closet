import json, pathlib, unittest

SHORT_MAX, LONG_MAX = 40, 180

ROOT = pathlib.Path(__file__).resolve().parent.parent
from playwright.sync_api import sync_playwright  # required: see README.md


def reference_queue(feed=(), n=8):
    """Independent implementation of the club rule, straight from the data file."""
    d = json.loads((ROOT / "data/closet.json").read_text(encoding="utf-8"))
    films = [dict(zip(d["films"]["cols"], r)) for r in d["films"]["rows"]]
    counts = {}
    for r in d["picks"]["rows"]:
        slug = r[d["picks"]["cols"].index("film_slug")]
        counts[slug] = counts.get(slug, 0) + 1
    by = {f["film_slug"]: f for f in films}
    dirs = lambda f: {x.strip() for x in f["directors"].split(";") if x.strip()}
    taken = set().union(*(dirs(by[s]) for s in feed)) if feed else set()
    ok = [f for f in films if counts.get(f["film_slug"]) and f["film_slug"] not in feed and dirs(f)
          and f["runtime_min"] is not None and SHORT_MAX < f["runtime_min"] <= LONG_MAX]
    ok.sort(key=lambda f: (-counts[f["film_slug"]], -(f["avg_rating"] or 0), f["film_year"] or 0, f["film_title"]))
    out = []
    for f in ok:
        if len(out) == n:
            break
        if dirs(f) & taken:
            continue
        out.append(f["film_slug"])
        taken |= dirs(f)
    return out


HOST = (ROOT / "tests/host_sim.js").read_text(encoding="utf-8")
SERVER = (ROOT / "dist/server.js").read_text(encoding="utf-8")
FAKE_PAGES = HOST + """
window.pages = (function () {
  const host = makeHost(%s, []);
  return { call: (a, args) => host.call(a, args, "u1"), currentUser: () => ({ id: "u1", name: "Ann" }) };
})();
""" % json.dumps(SERVER)


class Smoke(unittest.TestCase):
    def test_boots_and_renders_all_views(self):
        counts = json.loads((ROOT / "data/closet.json").read_text(encoding="utf-8"))["_meta"]["row_counts"]
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            logs, errors = [], []
            page.on("console", lambda m: logs.append(m.text))
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto((ROOT / "dist/index.html").as_uri())
            page.wait_for_function("document.querySelector('#app') && document.querySelector('#app').children.length > 0 && !document.querySelector('#app .loading')")
            self.assertTrue(any(f"Loaded {counts['films']} films, {counts['visits']} visits, {counts['picks']} picks" in l for l in logs), logs)
            headings = {
                "browse": "Every film, every angle",
                "visitors": "guests, one closet",
                "recommend": "Tell us a film, we'll tell you a closet",
            }
            for view, heading in headings.items():
                page.evaluate(f"location.hash = '#{view}'")
                page.wait_for_selector(f"#main h2:has-text(\"{heading}\")", timeout=5000)
            self.assertEqual(errors, [])
            browser.close()

    def page(self, p, fake=False):
        browser = p.chromium.launch()
        page = browser.new_page()
        if fake:
            page.add_init_script(FAKE_PAGES)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto((ROOT / "dist/index.html").as_uri())
        page.wait_for_function("typeof clubQueue === 'function' && DB !== null")
        return browser, page, errors

    def test_club_queue_matches_independent_rule(self):
        with sync_playwright() as p:
            browser, page, errors = self.page(p)
            js = "(feed) => clubQueue(DB.films, DB.filmBy, feed, 8).map(f => f.film_slug)"
            self.assertEqual(page.evaluate(js, []), reference_queue())
            first = reference_queue()[0]
            feed = [first, "faces-1968"]
            got = page.evaluate(js, feed)
            self.assertEqual(got, reference_queue(feed))
            self.assertNotIn(first, got)
            self.assertNotIn("the-killing-of-a-chinese-bookie", got)  # Cassavetes is taken
            self.assertEqual(errors, [])
            browser.close()

    def test_club_queue_runtime_boundaries_and_ties(self):
        with sync_playwright() as p:
            browser, page, errors = self.page(p)
            got = page.evaluate("""() => {
              const mk = (slug, rt, picks, dir, rating = 3, year = 2000) => ({ film_slug: slug, film_title: slug, runtime_min: rt,
                _pickCount: picks, _directors: [dir], avg_rating: rating, film_year: year });
              const films = [mk("s40", 40, 9, "A"), mk("s41", 41, 8, "B"), mk("l180", 180, 7, "C"), mk("l181", 181, 6, "D"),
                mk("tie-low", 100, 5, "E", 3.1), mk("tie-high", 100, 5, "F", 4.2), mk("tie-old", 100, 4, "G", 3, 1950), mk("tie-new", 100, 4, "H", 3, 1990)];
              const filmBy = new Map(films.map(f => [f.film_slug, f]));
              return clubQueue(films, filmBy, [], 20).map(f => f.film_slug);
            }""")
            self.assertEqual(got, ["s41", "l180", "tie-high", "tie-low", "tie-old", "tie-new"])
            browser.close()

    def test_club_flow_with_shared_state(self):
        with sync_playwright() as p:
            browser, page, errors = self.page(p, fake=True)
            page.evaluate("location.hash = '#clubs'")
            page.fill("input[aria-label='New club name']", "Friday Film Club")
            page.click("text=Create club")
            page.wait_for_selector("#main h2:has-text('Friday Film Club')")
            first = reference_queue()[0]
            page.click(".suggestions li >> nth=0 >> text=Add to feed")
            page.wait_for_selector(".club-current")
            d = json.loads((ROOT / "data/closet.json").read_text(encoding="utf-8"))
            title = next(r[1] for r in d["films"]["rows"] if r[0] == first)
            self.assertIn(title, page.inner_text(".club-current"))
            self.assertNotIn(title, page.inner_text(".suggestions"))
            page.click(".club-current >> text=Mark watched")
            page.wait_for_selector("h3:has-text('Watched') + ul li")
            page.select_option("select[aria-label='Your score']", "8")
            page.click("text=Rate")
            page.wait_for_selector("text=mean 8.0/10")
            self.assertIn("Ann: 8/10", page.inner_text("#main"))
            self.assertIn("Ann \u00b7 rate", page.inner_text(".club-log"))
            self.assertNotIn("null", page.inner_text("#main"))
            self.assertEqual(errors, [])
            browser.close()

    def test_clubs_tab_without_host_explains_itself(self):
        with sync_playwright() as p:
            browser, page, errors = self.page(p)
            page.evaluate("location.hash = '#clubs'")
            page.wait_for_selector("text=only work in the published Pages app")
            self.assertEqual(errors, [])
            browser.close()


if __name__ == "__main__":
    unittest.main()
