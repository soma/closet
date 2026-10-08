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
