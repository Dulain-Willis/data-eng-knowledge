"""Checks that no lesson starts with the level/minutes/challenges line.

  python3 checks/no_meta_first_line.py            # scan lessons/ only
  python3 checks/no_meta_first_line.py page.html  # also run the converter on saved lesson pages

Exit status 1 if any lesson, or any converter output, starts with that line.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# "Advanced·Spark · 35 min · 11 challenges", also with the tool-logo link in place of the area
META = re.compile(r"^(Beginner|Intermediate|Advanced)\s*·.*\bmin\b.*\bchallenges?\b")


def has_meta_line(text):
    return bool(META.match(text.split("\n", 1)[0]))


def main():
    bad = []
    for base, _, names in os.walk(os.path.join(ROOT, "lessons")):
        for n in names:
            if n.endswith(".md"):
                p = os.path.join(base, n)
                with open(p, encoding="utf-8") as f:
                    if has_meta_line(f.readline()):
                        bad.append(os.path.relpath(p, ROOT))
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    for page in sys.argv[1:]:
        import lesson_to_md
        with open(page, encoding="utf-8") as f:
            if has_meta_line(lesson_to_md.convert(f.read())):
                bad.append("converter output for " + page)
    for b in bad:
        print("starts with the meta line:", b)
    print(f"{len(bad)} failing")
    sys.exit(1 if bad else 0)


main()
