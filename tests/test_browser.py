import json, pathlib, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


@unittest.skipIf(sync_playwright is None, "playwright not installed")
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
            for view in ("browse", "visitors", "recommend"):
                page.goto((ROOT / "dist/index.html").as_uri() + f"#{view}")
                page.wait_for_timeout(300)
                self.assertGreater(len(page.inner_text("#app")), 100, view)
            self.assertEqual(errors, [])
            browser.close()


if __name__ == "__main__":
    unittest.main()
