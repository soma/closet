#!/usr/bin/env python3
"""Does the Pages app still need staging?

    scripts/stage_status.py              exit 0 if staged and current, 1 if staging is needed
    scripts/stage_status.py --mark-staged   record the current inputs as staged

A data change can leave every count unchanged (an IMDb id filled in on an
existing film, a corrected runtime), and a staging run can fail after the data
was committed. So "needs staging" is decided by a fingerprint of everything the
Pages upload is built from, recorded after a successful staging.
"""
import argparse, hashlib, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARK = ROOT / ".cache/staged.json"
INPUTS = ["data/closet.json", "data/posters.json", "src/template.html", "src/club.js", "src/club.css", "src/server.js", "scripts/build.py"]


def fingerprint(root=ROOT):
    h = hashlib.sha1()
    for name in INPUTS:
        p = root / name
        h.update(name.encode() + b"\0" + (p.read_bytes() if p.exists() else b"-") + b"\0")
    return h.hexdigest()


def needs_staging(root=ROOT, mark=MARK):
    if not mark.exists():
        return True
    return json.loads(mark.read_text(encoding="utf-8")).get("fingerprint") != fingerprint(root)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mark-staged", action="store_true")
    args = ap.parse_args(argv)
    if args.mark_staged:
        MARK.parent.mkdir(exist_ok=True)
        MARK.write_text(json.dumps({"fingerprint": fingerprint()}) + "\n", encoding="utf-8")
        print("recorded the current build inputs as staged")
        return 0
    if needs_staging():
        print("the Pages app needs staging")
        return 1
    print("the Pages app is staged and current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
