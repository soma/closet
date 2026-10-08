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
window.__delays = {};
window.__plan = {};   // per club: queue of { delay, reject } consumed by successive club_state calls
(function () {   // delay or fail club_state so tests can make responses arrive out of order
  const orig = window.pages.call;
  window.pages.call = (a, args) => {
    const step = a === "club_state" ? ((window.__plan[args.club_id] || []).shift() || {}) : {};
    const delay = step.delay != null ? step.delay : (a === "club_state" ? (window.__delays[args.club_id] || 0) : 0);
    return new Promise(r => setTimeout(r, delay)).then(() => {
      if (step.reject) throw new Error("stale failure");
      return orig(a, args);
    });
  };
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
                _pickCount: picks, _directors: Array.isArray(dir) ? dir : [dir], avg_rating: rating, film_year: year });
              const films = [mk("s40", 40, 9, "A"), mk("s41", 41, 8, "B"), mk("l180", 180, 7, "C"), mk("l181", 181, 6, "D"),
                mk("tie-low", 100, 5, "E", 3.1), mk("tie-high", 100, 5, "F", 4.2), mk("tie-old", 100, 4, "G", 3, 1950), mk("tie-new", 100, 4, "H", 3, 1990)];
              const filmBy = new Map(films.map(f => [f.film_slug, f]));
              const plain = clubQueue(films, filmBy, [], 20).map(f => f.film_slug);
              // co-directors: a film with a taken director is skipped, and picking it takes both
              const co = [mk("solo-x", 100, 9, "X"), mk("duo-xy", 100, 8, ["X", "Y"]), mk("solo-y", 100, 7, "Y"), mk("solo-z", 100, 6, "Z")];
              const coBy = new Map(co.map(f => [f.film_slug, f]));
              const coQueue = clubQueue(co, coBy, [], 20).map(f => f.film_slug);
              const duoFirst = clubQueue(co.slice(1), coBy, [], 20).map(f => f.film_slug);
              const feedY = clubQueue(co, coBy, ["solo-y"], 20).map(f => f.film_slug);
              return { plain, coQueue, duoFirst, feedY };
            }""")
            self.assertEqual(got["plain"], ["s41", "l180", "tie-high", "tie-low", "tie-old", "tie-new"])
            self.assertEqual(got["coQueue"], ["solo-x", "solo-y", "solo-z"])      # duo-xy skipped: X taken
            self.assertEqual(got["duoFirst"], ["duo-xy", "solo-z"])               # duo takes X and Y
            self.assertEqual(got["feedY"], ["solo-x", "solo-z"])                  # Y taken by the feed
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

    def test_slow_response_for_a_previous_club_never_overwrites_the_current_one(self):
        with sync_playwright() as p:
            browser, page, errors = self.page(p, fake=True)
            ids = page.evaluate("""async () => {
              const a = await window.pages.call("create_club", { name: "Club A" });
              const b = await window.pages.call("create_club", { name: "Club B" });
              window.__delays[a.id] = 600;
              return [a.id, b.id];
            }""")
            a, b = ids
            page.evaluate(f"location.hash = '#clubs/{a}'")      # A starts loading (slow)
            page.wait_for_timeout(100)
            page.evaluate(f"location.hash = '#clubs/{b}'")      # user switches to B (fast)
            page.wait_for_selector("#main h2:has-text('Club B')")
            page.wait_for_timeout(900)                           # A's response arrives late
            page.evaluate("renderView()")                        # any repaint must still show B
            self.assertIn("Club B", page.inner_text("#main h2"))
            self.assertEqual(page.evaluate("CLUB.data.club.data.name"), "Club B")
            page.click(".suggestions li >> nth=0 >> text=Add to feed")
            page.wait_for_selector(".club-current")
            counts = page.evaluate(f"""async () => [
              (await window.pages.call("club_state", {{ club_id: "{a}" }})).entries.length,
              (await window.pages.call("club_state", {{ club_id: "{b}" }})).entries.length]""")
            self.assertEqual(counts, [0, 1])
            # navigating away to the list while a club is still loading must show the list
            page.evaluate(f"location.hash = '#clubs/{a}'")
            page.wait_for_timeout(100)
            page.evaluate("location.hash = '#clubs'")
            page.wait_for_selector("text=Film clubs")
            page.wait_for_timeout(900)
            self.assertIn("Film clubs", page.inner_text("#main h2"))
            self.assertEqual(errors, [])
            browser.close()

    def test_stale_failure_for_a_revisited_club_does_not_disturb_the_view(self):
        with sync_playwright() as p:
            browser, page, errors = self.page(p, fake=True)
            a, b = page.evaluate("""async () => {
              const a = await window.pages.call("create_club", { name: "Club A" });
              const b = await window.pages.call("create_club", { name: "Club B" });
              window.__plan[a.id] = [{ delay: 700, reject: true }, { delay: 50 }];
              return [a.id, b.id];
            }""")
            page.evaluate(f"location.hash = '#clubs/{a}'")   # slow request that will fail
            page.wait_for_timeout(100)
            page.evaluate(f"location.hash = '#clubs/{b}'")
            page.wait_for_selector("#main h2:has-text('Club B')")
            page.evaluate(f"location.hash = '#clubs/{a}'")   # back to A: fast request that succeeds
            page.wait_for_selector("#main h2:has-text('Club A')")
            page.wait_for_timeout(1000)                        # the old failure lands now
            self.assertEqual(page.evaluate("CLUB.id"), a)
            self.assertIn("Club A", page.inner_text("#main h2"))
            self.assertEqual(page.evaluate("CLUB.error"), "")
            self.assertEqual(page.evaluate("location.hash"), f"#clubs/{a}")
            browser.close()

    def test_out_of_band_short_and_long_films_can_be_picked(self):
        d = json.loads((ROOT / "data/closet.json").read_text(encoding="utf-8"))
        fc, pc = d["films"]["cols"], d["picks"]["cols"]
        picked = {r[pc.index("film_slug")] for r in d["picks"]["rows"]}
        films = [dict(zip(fc, r)) for r in d["films"]["rows"]]
        titles = [f["film_title"] for f in films]
        short = next(f for f in films if f["film_slug"] in picked and f["runtime_min"] <= SHORT_MAX and titles.count(f["film_title"]) == 1)
        long_ = next(f for f in films if f["film_slug"] in picked and f["runtime_min"] > LONG_MAX and titles.count(f["film_title"]) == 1)
        with sync_playwright() as p:
            browser, page, errors = self.page(p, fake=True)
            self.assertNotIn(short["film_slug"], reference_queue(n=2000))
            self.assertNotIn(long_["film_slug"], reference_queue(n=2000))
            page.evaluate("location.hash = '#clubs'")
            page.fill("input[aria-label='New club name']", "Odd Picks")
            page.click("text=Create club")
            page.wait_for_selector("#main h2:has-text('Odd Picks')")
            for n, f in enumerate((short, long_), 1):
                page.fill("input[aria-label='Search films']", f["film_title"])
                page.wait_for_selector(f".club-list li:has-text(\"{f['film_title']}\") >> text=Add to feed")
                page.click(f".club-list li:has-text(\"{f['film_title']}\") >> text=Add to feed >> nth=0")
                page.wait_for_function("(n) => CLUB.data && CLUB.data.entries.length === n && !CLUB.busy", arg=n)
            state = page.evaluate("""async () => { const cs = await window.pages.call("list_clubs", {});
              return (await window.pages.call("club_state", { club_id: cs[0].id })).entries.map(e => e.data.film_slug); }""")
            self.assertEqual(sorted(state), sorted([short["film_slug"], long_["film_slug"]]))
            browser.close()

    def open_link(self, p, hash_, preset=True):
        """Load the page straight on a link, as someone following it would."""
        browser = p.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        pre = 'window.pages.call("create_club", { name: "Preset Club" });' if preset else ""
        page.add_init_script(FAKE_PAGES + pre)
        page.goto((ROOT / "dist/index.html").as_uri() + hash_)
        return browser, page, errors

    def test_link_straight_into_a_club(self):
        with sync_playwright() as p:
            browser, page, errors = self.open_link(p, "#clubs/id1")
            page.wait_for_selector("#main h2:has-text('Preset Club')")
            self.assertEqual(page.evaluate("location.hash"), "#clubs/id1")
            self.assertIn("#clubs/id1", page.inner_text(".club-link"))
            page.reload()                                         # a reload keeps you in the club
            page.wait_for_selector("#main h2:has-text('Preset Club')")
            self.assertEqual(errors, [])
            browser.close()

    def test_link_to_an_unknown_club_falls_back_to_the_list_with_a_message(self):
        with sync_playwright() as p:
            browser, page, errors = self.open_link(p, "#clubs/does-not-exist")
            page.wait_for_selector("#main h2:has-text('Film clubs')")
            page.wait_for_selector(".club-error:has-text('unknown club')")
            self.assertEqual(page.evaluate("location.hash"), "#clubs")
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
