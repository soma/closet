import io, json, pathlib, sys, tempfile, unittest

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import make_posters as mp  # noqa: E402


def png(w, h, color=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


class Thumbnails(unittest.TestCase):
    def test_every_aspect_ends_up_160_by_240_from_the_centre(self):
        for size in ((1200, 675), (500, 750), (300, 900), (160, 240)):
            self.assertEqual(mp.thumb(png(*size)).size, (160, 240), size)
        wide = Image.new("RGB", (1200, 675), (0, 0, 255))
        wide.paste((255, 0, 0), (375, 0, 825, 675))            # the centre 450px, what a 2:3 frame shows
        out = mp.thumb(self.to_bytes(wide))
        self.assertGreater(out.getpixel((2, 120))[0], 200)       # left edge is already the red centre
        self.assertLess(out.getpixel((2, 120))[2], 60)

    @staticmethod
    def to_bytes(im):
        buf = io.BytesIO()
        im.save(buf, "PNG")
        return buf.getvalue()


class Packing(unittest.TestCase):
    def test_slots_run_left_to_right_then_down_then_to_the_next_sheet(self):
        with tempfile.TemporaryDirectory() as d:
            cache = pathlib.Path(d)
            (cache / "thumbs").mkdir()
            items = [(f"f{i}", "u") for i in range(66)]
            for slug, _ in items[:65]:                                # f65 has no thumbnail: left out
                Image.new("RGB", (160, 240), (1, 2, 3)).save(cache / "thumbs" / f"{slug}.png")
            result = mp.pack(items, cache)
            m = result["map"]
            self.assertEqual((result["cols"], result["rows"]), (8, 8))
            self.assertEqual([m["f0"], m["f7"], m["f8"], m["f63"], m["f64"]], [[0, 0, 0], [0, 7, 0], [0, 0, 1], [0, 7, 7], [1, 0, 0]])
            self.assertNotIn("f65", m)
            sheets = sorted(p.name for p in (cache / "sheets").iterdir())
            self.assertEqual(sheets, ["sheet-00.webp", "sheet-01.webp"])
            with Image.open(cache / "sheets/sheet-00.webp") as sheet:
                self.assertEqual(sheet.size, (1280, 1920))


def thumbs(cache, slugs):
    (cache / "thumbs").mkdir(exist_ok=True)
    for i, s in enumerate(slugs):
        Image.new("RGB", (160, 240), (i % 250, 5, 5)).save(cache / "thumbs" / f"{s}.png")


class StablePacking(unittest.TestCase):
    def test_existing_posters_keep_their_slots_and_new_ones_take_the_lowest_free_ones(self):
        with tempfile.TemporaryDirectory() as d:
            cache = pathlib.Path(d)
            first = [f"f{i}" for i in range(10)]
            thumbs(cache, first + ["a0", "z9"])
            before = mp.pack([(s, "u") for s in first], cache)
            # an update inserts a0 alphabetically first, drops f3, adds z9 last
            items = [("a0", "u")] + [(s, "u") for s in first if s != "f3"] + [("z9", "u")]
            after = mp.pack(items, cache, previous=before)
            for s in first:
                if s != "f3":
                    self.assertEqual(after["map"][s], before["map"][s], s)
            self.assertNotIn("f3", after["map"])
            self.assertEqual(after["map"]["a0"], before["map"]["f3"], "the freed slot is reused first")
            self.assertEqual(after["map"]["z9"], [0, 2, 1], "then the next free one after the last used slot")

    def test_unchanged_sheets_stay_byte_identical_when_only_a_later_sheet_gains_posters(self):
        with tempfile.TemporaryDirectory() as d:
            cache = pathlib.Path(d)
            slugs = [f"f{i}" for i in range(70)]
            thumbs(cache, slugs)
            items = [(s, "u") for s in slugs]
            first = mp.pack(items[:64], cache)
            hashes = json.loads((cache / "sheets.json").read_text())
            self.assertEqual(sorted(hashes), ["sheet-00.webp"])
            mp.pack(items, cache, previous=first)
            again = json.loads((cache / "sheets.json").read_text())
            self.assertEqual(sorted(again), ["sheet-00.webp", "sheet-01.webp"])
            self.assertEqual(again["sheet-00.webp"], hashes["sheet-00.webp"], "sheet 0 did not change")

    def test_a_different_geometry_ignores_the_old_map(self):
        got = mp.assign(["a", "b"], {"cols": 3, "rows": 3, "map": {"b": [0, 2, 2]}})
        self.assertEqual(got, {"a": [0, 0, 0], "b": [0, 1, 0]})


class Fetching(unittest.TestCase):
    def test_blocked_stops_but_keeps_earlier_thumbnails_and_reruns_skip_them(self):
        with tempfile.TemporaryDirectory() as d:
            cache = pathlib.Path(d)
            calls = []
            def get(url):
                calls.append(url)
                if url == "u3":
                    raise mp.Blocked("403")
                return png(300, 450)
            items = [(f"f{i}", f"u{i}") for i in range(1, 6)]
            with self.assertRaises(mp.Blocked):
                mp.fetch_thumbs(items, 0, cache, get)
            self.assertEqual(sorted(p.name for p in (cache / "thumbs").iterdir()), ["f1.png", "f2.png"])
            calls.clear()
            get2 = lambda url: calls.append(url) or png(300, 450)
            mp.fetch_thumbs(items, 0, cache, get2)
            self.assertEqual(calls, ["u3", "u4", "u5"], "finished thumbnails are not downloaded again")

    def test_one_bad_image_is_reported_and_the_run_continues(self):
        with tempfile.TemporaryDirectory() as d:
            cache = pathlib.Path(d)
            get = lambda url: b"not an image" if url == "u2" else png(300, 450)
            failed = mp.fetch_thumbs([("f1", "u1"), ("f2", "u2"), ("f3", "u3")], 0, cache, get)
            self.assertEqual([s for s, _ in failed], ["f2"])
            self.assertTrue((cache / "thumbs/f3.png").exists())


if __name__ == "__main__":
    unittest.main()
