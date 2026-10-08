import json, pathlib, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
from playwright.sync_api import sync_playwright  # required: see README.md


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


if __name__ == "__main__":
    unittest.main()
