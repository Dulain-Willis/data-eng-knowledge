#!/usr/bin/env python3
"""Re-record chosen animation blocks with the converter's recorder (record_animations) as MP4s.

Usage:
    ANIM_DIR=~/animation-mp4s .venv/bin/python tools/rerecord_animations.py <lesson_slug>:<n> [...]

<lesson_slug> is the page slug with its tier (kafka_the_log_beginner), <n> the 1-based animation number
on the page (the number in the GIF's file name). Every mode (toggle) of that animation is recorded.
Nothing is uploaded and no lesson file is touched: the MP4s land in ANIM_DIR (default ~/animation-mp4s).
"""
import os
import sys
import tempfile
import urllib.request

os.environ.setdefault("ANIM_DIR", os.path.expanduser("~/animation-mp4s"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lesson_to_md as c  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    failed = []
    for spec in sys.argv[1:]:
        slug, n = spec.rsplit(":", 1)
        url = c.BASE + slug
        html = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "lesson-to-md/1.0"}),
                                      timeout=30).read().decode("utf-8", "ignore")
        info = c.animation_info(html)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                saved = c.record_animations(url, tmp, slug, info, only={int(n) - 1})
        except RuntimeError as e:  # keep going; the failed ones are listed at the end
            print(f"FAILED {spec}: {e}", file=sys.stderr)
            failed.append(spec)
            continue
        for entries in saved.values():
            for label, name in entries:
                print(os.path.join(c.ANIM_DIR, name))
    if failed:
        sys.exit(f"could not record: {' '.join(failed)}")


if __name__ == "__main__":
    main()
