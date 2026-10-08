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


def reference_reco(seeds, limit=30, lens="all"):
    """Independent co-pick ranking: score = sum over visitors of overlap^2 / their closet size."""
    d = json.loads((ROOT / "data/closet.json").read_text(encoding="utf-8"))
    pc = d["picks"]["cols"]
    by_film, by_visit = {}, {}
    for r in d["picks"]["rows"]:
        v, order, film = r[pc.index("visit_slug")], r[pc.index("pick_order")], r[pc.index("film_slug")]
        by_film.setdefault(film, []).append(v)
        by_visit.setdefault(v, []).append((order, film))
    for v in by_visit:
        by_visit[v].sort(key=lambda t: t[0])
    seeds = list(dict.fromkeys(seeds))
    overlap = {}
    for s in seeds:
        for v in by_film.get(s, []):
            overlap[v] = overlap.get(v, 0) + 1
    score, support = {}, {}
    for v, oc in overlap.items():
        picks = by_visit[v]
        w = oc * oc / (len(picks) or 1)
        for _, film in picks:
            if film in seeds:
                continue
            score[film] = score.get(film, 0) + w
            support[film] = support.get(film, 0) + 1
    ranked = sorted(score, key=lambda f: (-score[f], -support[f]))     # stable, like the app
    return [(f, round(score[f], 9)) for f in ranked[:limit]]


def reference_nearest(mine, n=5):
    d = json.loads((ROOT / "data/closet.json").read_text(encoding="utf-8"))
    vc, pc = d["visits"]["cols"], d["picks"]["cols"]
    names = {r[vc.index("visit_slug")]: r[vc.index("visitor")] for r in d["visits"]["rows"]}
    picks = {}
    for r in d["picks"]["rows"]:
        picks.setdefault(r[pc.index("visit_slug")], []).append(r[pc.index("film_slug")])
    out = []
    for v, films in picks.items():
        shared = sum(1 for f in films if f in mine)
        if shared:
            out.append((-shared, len(films), names.get(v, ""), v))
    out.sort()
    return [(v, -neg, size) for neg, size, _, v in out[:n]]


HOST = (ROOT / "tests/host_sim.js").read_text(encoding="utf-8")
SERVER = (ROOT / "dist/server.js").read_text(encoding="utf-8")
FAKE_PAGES = HOST + """
window.pages = (function () {
  const host = makeHost(%s, []);
  window.__host = host;
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

    def page_at(self, p, hash_):
        """Load the built page straight on a link."""
        browser = p.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto((ROOT / "dist/index.html").as_uri() + hash_)
        page.wait_for_function("typeof DB !== 'undefined' && DB !== null")
        return browser, page, errors

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
            self.assertEqual(page.locator(".club-link").count(), 0, "no long link text any more")
            link = page.locator("a.share-link")
            self.assertEqual(link.get_attribute("aria-label"), "Link to this club")
            self.assertTrue(link.get_attribute("href").endswith("dist/index.html#clubs/id1"), link.get_attribute("href"))
            self.assertEqual((link.get_attribute("target"), link.get_attribute("rel")), ("_blank", "noopener"))
            page.reload()                                         # a reload keeps you in the club
            page.wait_for_selector("#main h2:has-text('Preset Club')")
            self.assertEqual(errors, [])
            browser.close()

    def test_club_link_base_is_the_configured_page_url_else_the_apps_own_address(self):
        with sync_playwright() as p:
            browser, page, errors = self.page(p)
            got = page.evaluate("""() => [
              clubLinkUrl("id 1", "https://pages.example/p/club-x#old"),
              clubLinkUrl("id1", ""),
              clubLinkUrl("id1")]""")
            self.assertEqual(got[0], "https://pages.example/p/club-x#clubs/id%201")
            self.assertTrue(got[1].endswith("dist/index.html#clubs/id1"))
            self.assertEqual(got[1], got[2])                      # default build has no PAGE_URL
            browser.close()

    def test_a_misleading_referrer_is_ignored(self):
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(extra_http_headers={"Referer": "https://example.org/somewhere"})
            page = ctx.new_page()
            page.goto((ROOT / "dist/index.html").as_uri())
            page.wait_for_function("typeof DB !== 'undefined' && DB !== null")
            self.assertNotIn("example.org", page.evaluate("clubLinkUrl('id1')"))
            browser.close()

    def test_the_club_link_icon_is_a_real_link_with_the_configured_base(self):
        with sync_playwright() as p:
            browser, page, errors = self.open_link(p, "#clubs/id1")
            page.wait_for_selector("a.share-link")
            self.assertEqual(page.locator("button.club-share").count(), 0, "no copy button, no copy-paste fallback")
            self.assertEqual(page.locator("input.club-share-url").count(), 0)
            got = page.evaluate("""() => [pageLink("clubs/x", "https://pages.example/p/c#old"), pageLink("film/a b", ""), pageLink("film/q")]""")
            self.assertEqual(got[0], "https://pages.example/p/c#clubs/x")
            self.assertTrue(got[1].endswith("dist/index.html#film/a b"))
            self.assertEqual(got[1].replace("a b", "q"), got[2])
            self.assertEqual(errors, [])
            browser.close()

    def test_link_straight_into_a_film_popup(self):
        with sync_playwright() as p:
            browser, page, errors = self.page_at(p, "#film/12-angry-men")
            page.wait_for_selector(".film-modal h3:has-text('12 Angry Men')")
            self.assertEqual(page.evaluate("location.hash"), "#film/12-angry-men")
            link = page.locator(".film-modal a.share-link")
            self.assertTrue(link.get_attribute("href").endswith("dist/index.html#film/12-angry-men"))
            self.assertEqual((link.get_attribute("target"), link.get_attribute("rel"), link.get_attribute("aria-label")),
                             ("_blank", "noopener", "Link to this film"))
            page.reload()                                           # a reload keeps the popup
            page.wait_for_selector(".film-modal h3:has-text('12 Angry Men')")
            self.assertEqual(errors, [])
            browser.close()

    def test_opening_and_closing_a_film_popup_keeps_the_address_in_step(self):
        with sync_playwright() as p:
            browser, page, errors = self.page_at(p, "#visitors")
            page.wait_for_selector("#main h2:has-text('guests, one closet')")
            page.evaluate("openFilmModal('12-angry-men')")
            self.assertEqual(page.evaluate("location.hash"), "#film/12-angry-men")
            page.keyboard.press("Escape")                           # closing returns to the view we were on
            self.assertEqual(page.locator(".film-modal").count(), 0)
            self.assertEqual(page.evaluate("location.hash"), "#visitors")
            page.evaluate("openFilmModal('12-angry-men')")
            page.evaluate("openVisitorModal(DB.visits[0].visit_slug)")   # another popup leaves the film address
            self.assertEqual(page.locator(".film-modal").count(), 0)
            self.assertEqual(page.evaluate("location.hash"), "#visitors")
            self.assertEqual(errors, [])
            browser.close()

    def test_changing_the_address_opens_and_closes_the_film_popup(self):
        with sync_playwright() as p:
            browser, page, errors = self.page_at(p, "#browse")
            page.wait_for_selector("#main h2:has-text('Every film')")
            page.evaluate("location.hash = '#film/8-half'")
            page.wait_for_selector(".film-modal h3:has-text('8½')")
            page.evaluate("location.hash = '#recommend'")
            page.wait_for_function("document.querySelectorAll('.film-modal').length === 0")
            self.assertEqual(page.evaluate("STATE.view"), "recommend")
            self.assertEqual(errors, [])
            browser.close()

    def test_navigating_from_a_film_to_an_unknown_film_closes_the_popup(self):
        with sync_playwright() as p:
            browser, page, errors = self.page_at(p, "#film/12-angry-men")
            page.wait_for_selector(".film-modal h3:has-text('12 Angry Men')")
            self.assertEqual(page.evaluate("document.body.style.overflow"), "hidden")
            page.evaluate("location.hash = '#film/no-such-film'")
            page.wait_for_function("document.querySelectorAll('.film-modal').length === 0")
            self.assertEqual(page.evaluate("document.body.style.overflow"), "")
            self.assertEqual(page.evaluate("location.hash"), "#browse")
            self.assertIsNone(page.evaluate("STATE.film"))
            self.assertEqual(errors, [])
            browser.close()

    def test_a_film_link_over_a_club_keeps_the_club(self):
        with sync_playwright() as p:
            browser, page, errors = self.open_link(p, "#clubs/id1")
            page.wait_for_selector("#main h2:has-text('Preset Club')")
            page.evaluate("location.hash = '#film/12-angry-men'")
            page.wait_for_selector(".film-modal h3:has-text('12 Angry Men')")
            self.assertEqual(page.evaluate("[STATE.view, CLUB.id]"), ["clubs", "id1"])
            page.keyboard.press("Escape")
            page.wait_for_function("document.querySelectorAll('.film-modal').length === 0")
            self.assertEqual(page.evaluate("location.hash"), "#clubs/id1")
            page.wait_for_selector("#main h2:has-text('Preset Club')")
            self.assertEqual(errors, [])
            browser.close()

    def test_a_film_link_to_an_unknown_film_falls_back_quietly(self):
        with sync_playwright() as p:
            browser, page, errors = self.page_at(p, "#film/no-such-film")
            page.wait_for_selector("#main h2:has-text('Every film')")
            self.assertEqual(page.locator(".film-modal").count(), 0)
            self.assertEqual(page.evaluate("location.hash"), "#browse")
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

    def test_imdb_links_in_popup_and_club_and_old_entries_are_repaired(self):
        slug, imdb = "12-angry-men", "tt0050083"
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            fake = FAKE_PAGES
            # give the server a known id for one film regardless of the dataset state
            server = SERVER.replace("const FILM_SLUGS =", f'FILM_IMDB["{slug}"] = "{imdb}";\nconst FILM_SLUGS =', 1)
            fake = fake.replace(json.dumps(SERVER), json.dumps(server))
            pre = f"""(function () {{
              const host = window.__host;
              host.call("create_club", {{ name: "Old Entries" }}, "u1");
              host.call("add_entry", {{ club_id: "id1", film_slug: "{slug}" }}, "u1");
              host.db.entries[0].data.imdb_id = "";     // added before the column existed
            }})();"""
            page.add_init_script(fake + pre)
            page.goto((ROOT / "dist/index.html").as_uri() + "#clubs/id1")
            page.wait_for_function("typeof DB !== 'undefined' && DB !== null")
            page.evaluate(f"DB.filmBy.get('{slug}').imdb_id = '{imdb}'")
            page.evaluate("renderView()")
            page.wait_for_selector("#main h2:has-text('Old Entries')")
            link = page.locator(".club-current a.ext")
            link.wait_for()
            self.assertEqual(link.get_attribute("href"), f"https://www.imdb.com/title/{imdb}/")
            self.assertEqual(link.get_attribute("rel"), "noopener")
            page.wait_for_function(f"__host.db.entries[0].data.imdb_id === '{imdb}'")   # repaired by fill_imdb
            page.evaluate(f"openFilmModal('{slug}')")
            modal = page.locator(".film-modal a.ext")
            self.assertEqual(modal.get_attribute("href"), f"https://www.imdb.com/title/{imdb}/")
            page.evaluate(f"closeModal(); DB.filmBy.get('{slug}').imdb_id = ''; openFilmModal('{slug}')")
            self.assertEqual(page.locator(".film-modal a.ext").count(), 0)          # no id, no link
            self.assertEqual(errors, [])
            browser.close()

    def test_posters_use_sprite_sheets_when_uploaded_and_hotlinks_otherwise(self):
        import shutil, tempfile, sys
        sys.path.insert(0, str(ROOT / "scripts"))
        import build as builder
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "src").mkdir(); (root / "data").mkdir()
            for name in ("template.html", "club.js", "club.css", "closet.js", "closet.css", "server.js"):
                shutil.copy(ROOT / "src" / name, root / "src" / name)
            shutil.copy(ROOT / "data/closet.json", root / "data/closet.json")
            (root / "data/posters.json").write_text(json.dumps({"cols": 8, "rows": 8, "map": {"12-angry-men": [0, 3, 2], "8-half": [1, 7, 7]}}))
            builder.build(root)
            self.assertNotIn('"12-angry-men":[0', (root / "index.html").read_text(encoding="utf-8"), "GitHub Pages build keeps hotlinking")
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                gif = "data:image/gif;base64,R0lGODlhAQABAAAAACw="
                pre = f"""__host.db.poster_sheets = [{{ id: "ps0", key: "sheet-00", data: {{ sheet: 0 }}, asset_url: "{gif}", author: "u1", created_at: "1", updated_at: "1" }}];"""
                page.add_init_script(FAKE_PAGES + pre)
                page.goto((root / "dist/index.html").as_uri())
                page.wait_for_function("typeof DB !== 'undefined' && DB !== null")
                got = page.evaluate("""() => {
                  const card = f => posterCard(DB.filmBy.get(f));
                  const a = card("12-angry-men"), b = card("8-half"), c = card("zorns-lemma");
                  const s = a.querySelector(".sprite");
                  return { sprite: !!s, size: s && s.style.backgroundSize, pos: s && s.style.backgroundPosition, img: !!a.querySelector("img"),
                           sheetMissing: !b.querySelector(".sprite") && !!b.querySelector("img"),     // sheet 1 not uploaded
                           unmapped: !c.querySelector(".sprite") && !!c.querySelector("img") };
                }""")
                self.assertEqual((got["sprite"], got["size"], got["img"]), (True, "800% 800%", False))
                x, y = [float(v.rstrip("%")) for v in got["pos"].split()]
                self.assertAlmostEqual(x, 3 / 7 * 100, places=2)
                self.assertAlmostEqual(y, 2 / 7 * 100, places=2)
                self.assertTrue(got["sheetMissing"] and got["unmapped"])
                # the signed addresses expire after an hour: the app asks again every 30 minutes
                page.clock.install()
                page.reload()
                page.wait_for_function("typeof DB !== 'undefined' && DB !== null")
                page.evaluate("__host.db.poster_sheets[0].asset_url = 'data:image/gif;base64,R0lGODlhAQABAAAAADs='")
                page.clock.fast_forward("31:00")
                page.wait_for_function("POSTER_SHEETS[0] && POSTER_SHEETS[0].endsWith('ADs=')")
                self.assertEqual(errors, [])
                browser.close()

    def closet_page(self, p, hash_, mine=(), others=None, init_extra=""):
        """The built page with a fake host whose closet_picks already hold `mine` (as u1) and `others` {author: (name, slugs)}."""
        browser = p.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        rows, n = [], 0
        for slug in mine:
            n += 1
            rows.append({"id": f"c{n}", "data": {"film_slug": slug, "by_name": "Ann"}, "author": "u1", "created_at": f"{n:08d}", "updated_at": "1"})
        for author, (name, slugs) in (others or {}).items():
            for slug in slugs:
                n += 1
                rows.append({"id": f"c{n}", "data": {"film_slug": slug, "by_name": name}, "author": author, "created_at": f"{n:08d}", "updated_at": "1"})
        page.add_init_script(FAKE_PAGES + f"__host.db.closet_picks = {json.dumps(rows)};" + init_extra)
        page.goto((ROOT / "dist/index.html").as_uri() + hash_)
        page.wait_for_function("typeof DB !== 'undefined' && DB !== null")
        return browser, page, errors

    def test_for_you_matches_an_independent_co_pick_ranking(self):
        mine = ["12-angry-men", "8-half", "faces-1968"]
        with sync_playwright() as p:
            browser, page, errors = self.closet_page(p, "#closet", mine)
            page.wait_for_selector("#main h3:has-text('For you')")
            got = page.evaluate(f"computeRecommendations({json.dumps(mine)}, 'all', 24).map(r => [r.slug, Math.round(r.score * 1e9) / 1e9])")
            self.assertEqual([tuple(g) for g in got], reference_reco(mine, 24))
            shown = page.evaluate("""() => { const h = [...document.querySelectorAll('#main h3')].find(x => x.textContent === 'For you');
              return [...h.nextElementSibling.nextElementSibling.querySelectorAll('.poster-card')].map(c => c.dataset.slug); }""")
            self.assertEqual(shown, [f for f, _ in reference_reco(mine, 24)])
            self.assertFalse(set(shown) & set(mine), "films already in the closet are never suggested")
            self.assertEqual(errors, [])
            browser.close()

    def test_recommend_tab_still_gives_the_same_results_for_fixed_seeds(self):
        seeds = ["12-angry-men", "8-half"]
        with sync_playwright() as p:
            browser, page, errors = self.page_at(p, "#recommend/seeds=" + ",".join(seeds))
            got = page.evaluate("computeRecommendations().map(r => [r.slug, Math.round(r.score * 1e9) / 1e9])")
            self.assertEqual([tuple(g) for g in got], reference_reco(seeds, 30))
            self.assertEqual(errors, [])
            browser.close()

    def test_closest_visitors_are_ranked_by_shared_picks_then_smaller_closets(self):
        mine = ["12-angry-men", "8-half", "faces-1968", "mon-oncle"]
        with sync_playwright() as p:
            browser, page, errors = self.closet_page(p, "#closet", mine)
            page.wait_for_selector("#main h3:has-text('Closest visitors')")
            got = page.evaluate(f"nearestVisitors(new Set({json.dumps(mine)}), 5).map(n => [n.visit.visit_slug, n.shared, n.size])")
            self.assertEqual([tuple(g) for g in got], reference_nearest(set(mine), 5))
            self.assertEqual(page.locator(".closet-near li").count(), 5)
            self.assertEqual(errors, [])
            browser.close()

    def test_other_closets_are_listed_by_overlap_and_open_read_only(self):
        others = {"u2": ("Bob", ["12-angry-men", "8-half"]), "u3": ("Cleo", ["12-angry-men", "mon-oncle", "faces-1968"]), "u4": ("Dan", ["zorns-lemma"])}
        with sync_playwright() as p:
            browser, page, errors = self.closet_page(p, "#closet", ["12-angry-men", "faces-1968"], others)
            page.wait_for_selector(".closet-others li")
            names = page.locator(".closet-others li a").all_inner_texts()
            self.assertEqual(names, ["Cleo", "Bob", "Dan"])           # 2 in common, 1, 0
            self.assertIn("2 in common with you", page.locator(".closet-others li").first.inner_text())
            page.click(".closet-others li a >> text=Cleo")
            page.wait_for_selector("#main h2:has-text(\"Cleo's closet\")")
            self.assertEqual(page.evaluate("location.hash"), "#closet/u3")
            self.assertEqual(page.locator(".closet-item").count(), 0, "read-only: no remove buttons")
            self.assertEqual(page.locator("#main .poster-card").count(), 3)
            self.assertEqual(page.locator("#main .poster-card:has-text('in your closet too')").count(), 2)
            self.assertIn("2 in common with you", page.inner_text("#main"))
            self.assertEqual(page.locator("a.share-link").get_attribute("aria-label"), "Link to this closet")
            self.assertEqual(errors, [])
            browser.close()

    def test_a_link_to_someone_elses_closet_and_to_a_missing_one(self):
        with sync_playwright() as p:
            browser, page, errors = self.closet_page(p, "#closet/u2", [], {"u2": ("Bob", ["12-angry-men"])})
            page.wait_for_selector("#main h2:has-text(\"Bob's closet\")")
            page.reload()
            page.wait_for_selector("#main h2:has-text(\"Bob's closet\")")
            page.evaluate("location.hash = '#closet/nobody'")
            page.wait_for_selector("#main h2:has-text('My closet')")
            page.wait_for_selector(".club-error:has-text(\"doesn't exist\")")
            self.assertEqual(page.evaluate("location.hash"), "#closet")
            page.evaluate("location.hash = '#closet/u1'")             # my own id: just my closet
            page.wait_for_selector("#main h2:has-text('My closet')")
            self.assertEqual(errors, [])
            browser.close()

    def test_adding_and_removing_from_the_film_popup_and_the_closet_view(self):
        with sync_playwright() as p:
            browser, page, errors = self.closet_page(p, "#closet", [])
            page.wait_for_selector("#main h2:has-text('My closet')")
            self.assertEqual(page.locator("#main h3:has-text('For you')").count(), 0, "nothing to base it on yet")
            page.evaluate("openFilmModal('12-angry-men')")
            toggle = page.locator(".film-modal .closet-toggle")
            toggle.wait_for()
            page.wait_for_function("document.querySelector('.closet-toggle').textContent.includes('Add to my closet')")
            toggle.click()
            page.wait_for_function("document.querySelector('.closet-toggle').textContent.includes('In my closet')")
            self.assertEqual(page.evaluate("__host.db.closet_picks.map(r => [r.author, r.data.film_slug, r.data.by_name])"), [["u1", "12-angry-men", "Ann"]])
            page.keyboard.press("Escape")
            page.wait_for_selector("#main h3:has-text('My picks')")
            self.assertEqual(page.locator(".closet-item").count(), 1)
            self.assertTrue(page.locator("#main h3:has-text('For you')").count() == 1)
            page.click(".closet-item >> text=Remove")
            page.wait_for_selector("#main h3:has-text('For you')", state="detached")
            self.assertEqual(page.evaluate("__host.db.closet_picks.length"), 0)
            # the search box adds too
            page.fill("input[aria-label='Search films to add to my closet']", "Persona")
            page.click(".club-list li >> text=Add to my closet >> nth=0")
            page.wait_for_selector(".closet-item")
            self.assertEqual(page.evaluate("__host.db.closet_picks.length"), 1)
            self.assertEqual(errors, [])
            browser.close()

    def test_a_slow_older_closets_response_never_overwrites_a_newer_one(self):
        with sync_playwright() as p:
            browser, page, errors = self.closet_page(p, "#browse", ["12-angry-men"])
            got = page.evaluate("""async () => {
              const orig = window.pages.call;
              let n = 0;
              window.pages.call = (a, args) => {
                if (a !== "closets") return orig(a, args);
                n += 1;
                const mine = n;
                return orig(a, args).then(rows => new Promise(r => setTimeout(() => r(mine === 1 ? [] : rows), mine === 1 ? 300 : 0)));
              };
              const slow = loadClosets();      // started first, answers last, with an old (empty) snapshot
              const fast = loadClosets();
              await Promise.all([slow, fast]);
              return [CLOSET.rows.length, await slow, await fast];
            }""")
            self.assertEqual(got, [1, False, True])
            self.assertEqual(errors, [])
            browser.close()

    # a wrapper around the fake host: delay or fail chosen actions, and count the calls
    SLOW = """
    window.__calls = {}; window.__delay = {}; window.__fail = {};
    (function () {
      const orig = window.pages.call;
      window.pages.call = (a, args) => {
        window.__calls[a] = (window.__calls[a] || 0) + 1;
        if (window.__fail[a] > 0) { window.__fail[a]--; return new Promise((_, no) => setTimeout(() => no(new Error(window.__failMsg || "boom")), window.__delay[a] || 0)); }
        return new Promise(r => setTimeout(r, window.__delay[a] || 0)).then(() => orig(a, args));
      };
    })();"""

    def test_equal_overlap_closets_are_ordered_by_name_not_size(self):
        with sync_playwright() as p:
            browser, page, errors = self.page(p)
            got = page.evaluate("""() => {
              const rows = [["u2", "Zoe", "12-angry-men"], ["u2", "Zoe", "zorns-lemma"], ["u3", "Amy", "12-angry-men"], ["u4", "Max", "8-half"]]
                .map(([author, by_name, film_slug], i) => ({ author, by_name, film_slug, created_at: String(i).padStart(4, "0") }));
              return otherClosets(groupClosets(rows), "u1", new Set(["12-angry-men"])).map(o => [o.person.name, o.shared]);
            }""")
            self.assertEqual(got, [["Amy", 1], ["Zoe", 1], ["Max", 0]])      # same overlap: name decides, not the bigger closet
            browser.close()

    def test_a_load_that_finishes_after_the_view_and_popup_both_asked_repaints_both(self):
        with sync_playwright() as p:
            browser, page, errors = self.closet_page(p, "#browse", ["12-angry-men"], init_extra=self.SLOW)
            page.evaluate("window.__delay.closets = 500")
            page.evaluate("location.hash = '#closet'")                     # the view starts the load
            page.wait_for_selector("text=Loading closets")
            page.evaluate("location.hash = '#film/12-angry-men'")          # the popup asks while it is in flight
            page.wait_for_function("document.querySelector('.closet-toggle').textContent.includes('In my closet')", timeout=5000)
            page.keyboard.press("Escape")
            page.wait_for_selector("#main h3:has-text('My picks')")        # the waiting view was repainted too
            self.assertEqual(page.evaluate("window.__calls.closets"), 1, "one shared load, not one per consumer")
            self.assertEqual(errors, [])
            browser.close()

    def test_a_pending_action_disables_the_controls_at_once_and_ignores_a_second_click(self):
        with sync_playwright() as p:
            browser, page, errors = self.closet_page(p, "#browse", [], init_extra=self.SLOW)
            page.evaluate("openFilmModal('12-angry-men')")
            page.wait_for_function("document.querySelector('.closet-toggle').textContent.includes('Add to my closet')")
            page.evaluate("window.__delay.closet_add = 500")
            page.click(".closet-toggle")
            self.assertTrue(page.locator(".closet-toggle").is_disabled(), "disabled immediately, not when the action ends")
            page.evaluate("document.querySelector('.closet-toggle').click()")   # a second click while pending
            page.wait_for_function("document.querySelector('.closet-toggle').textContent.includes('In my closet')", timeout=5000)
            self.assertEqual(page.evaluate("window.__calls.closet_add"), 1)
            self.assertFalse(page.locator(".closet-toggle").is_disabled())
            self.assertEqual(page.evaluate("CLOSET.busy"), False)
            self.assertEqual(errors, [])
            browser.close()

    def test_every_closet_control_is_disabled_while_an_action_runs(self):
        with sync_playwright() as p:
            browser, page, errors = self.closet_page(p, "#closet", ["12-angry-men", "8-half"], init_extra=self.SLOW)
            page.wait_for_selector(".closet-item")
            page.evaluate("window.__delay.closet_remove = 500")
            page.locator(".closet-item >> text=Remove").first.click()
            page.wait_for_function("[...document.querySelectorAll('.closet-item button')].every(b => b.disabled)")
            page.evaluate("document.querySelectorAll('.closet-item button')[1].click()")   # another Remove while pending
            page.wait_for_function("document.querySelectorAll('.closet-item').length === 1", timeout=5000)
            self.assertEqual(page.evaluate("window.__calls.closet_remove"), 1)
            self.assertEqual(errors, [])
            browser.close()

    def test_a_failed_add_shows_its_error_in_the_popup(self):
        with sync_playwright() as p:
            browser, page, errors = self.closet_page(p, "#browse", [], init_extra=self.SLOW)
            page.evaluate("openFilmModal('12-angry-men')")
            page.wait_for_function("document.querySelector('.closet-toggle').textContent.includes('Add to my closet')")
            page.evaluate("window.__fail.closet_add = 1; window.__failMsg = 'a closet holds at most 200 films'")
            page.click(".closet-toggle")
            page.wait_for_selector(".closet-toggle-msg:has-text('at most 200 films')")
            self.assertTrue(page.locator(".closet-toggle").is_enabled(), "the person can try again")
            page.click(".closet-toggle")                                    # next attempt works and clears the message
            page.wait_for_function("document.querySelector('.closet-toggle').textContent.includes('In my closet')")
            self.assertEqual(page.locator(".closet-toggle-msg").inner_text(), "")
            self.assertEqual(errors, [])
            browser.close()

    def test_a_failed_load_from_a_direct_film_link_is_explained_and_can_be_retried(self):
        with sync_playwright() as p:
            browser, page, errors = self.closet_page(p, "#film/12-angry-men", [], init_extra=self.SLOW + "window.__fail.closets = 1; window.__failMsg = 'closets unavailable';")
            page.wait_for_selector(".closet-toggle-msg:has-text('closets unavailable')")
            self.assertIn("retry", page.locator(".closet-toggle").inner_text().lower())
            self.assertTrue(page.locator(".closet-toggle").is_enabled())
            page.click(".closet-toggle")
            page.wait_for_function("document.querySelector('.closet-toggle').textContent.includes('Add to my closet')")
            self.assertEqual(page.locator(".closet-toggle-msg").inner_text(), "")
            self.assertEqual(errors, [])
            browser.close()

    def test_a_failed_load_on_the_closet_tab_offers_a_retry(self):
        with sync_playwright() as p:
            browser, page, errors = self.closet_page(p, "#closet", ["12-angry-men"], init_extra=self.SLOW + "window.__fail.closets = 1; window.__failMsg = 'closets unavailable';")
            page.wait_for_selector(".club-error:has-text('closets unavailable')")
            page.click("button:has-text('Retry')")
            page.wait_for_selector("#main h3:has-text('My picks')")
            self.assertEqual(errors, [])
            browser.close()

    def test_my_closet_without_a_host_explains_itself(self):
        with sync_playwright() as p:
            browser, page, errors = self.page(p)
            page.evaluate("location.hash = '#closet'")
            page.wait_for_selector("text=Closets keep shared state on the Pages host")
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
