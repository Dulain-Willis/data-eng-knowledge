"""Learn Python exercise placeholders.

The Learn Python lessons are converted without their exercises (the real ones are not mapped
yet). Each spot where an exercise sat gets a link to a PLACEHOLDER file in the lesson's
_exercises/ folder, and the text that only referred to the exercise ("The drill below ...",
"Capstone: ...") lives in that placeholder instead of the lesson body.

The spots and the moved text are kept by hand in tools/python_exercises.json and, for Learn SQL
and the one Interview SQL lesson, tools/sql_exercises.json ({slug: [exercise, ...]}; same format). lesson_to_md.py calls apply_lesson() after it writes a Learn Python
lesson, so a re-run of the converter reproduces the committed result; it can also be run on its
own (idempotent):  python3 tools/python_exercise_placeholders.py [lessons/learn/python]

Exercise fields (all optional except name and moved):
  name          link text and placeholder title
  heading       exact heading line the exercise sat under; heading_nth picks the n-th match (0-based)
  heading_new   new heading line (null: the heading goes away, it was only "Practice"/"Capstone")
  before/after  prefix of the block the link goes before / after (default: where the heading was)
  trim          [[find, replace]] edits to the lesson text, for sentences cut out of longer paragraphs
  trim_only     true: the entry only carries trims (no placement, no placeholder; keep it last)
  moved         text moved into the placeholder (dropped blocks and trimmed sentences; [] when the
                trimmed words are partial edits of text that stays in the lesson)
  empty_note    placeholder sentence used when moved is empty (default: the spot was a heading only)
Headings that are left over ("### Practice", "### Practice: x", "### Capstone: x") get the same
rule: the word goes, a bare heading is removed.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC_FILES = [os.path.join(HERE, "python_exercises.json"), os.path.join(HERE, "sql_exercises.json")]
LEFTOVER = re.compile(r"^(#{2,6}) (?:Practice|Capstones?)(?:: (.+))?$")


def parse_blocks(text):
    """[[block text, separator that follows it]]: blocks end at a blank line outside a code fence."""
    blocks, cur, blanks, fence = [], [], 0, False
    for line in text.rstrip("\n").split("\n"):
        if not fence and not line.strip():
            if cur:
                blocks.append(["\n".join(cur), ""])
                cur = []
            blanks += 1
            continue
        if not cur and blocks:
            blocks[-1][1] = "\n" * (blanks + 1)
        blanks = 0
        if line.startswith("```"):
            fence = not fence
        cur.append(line)
    if cur:
        blocks.append(["\n".join(cur), ""])
    return blocks


def join_blocks(blocks):
    return "".join(b + sep for b, sep in blocks) + "\n"


def find_block(blocks, prefix, what):
    hits = [i for i, (b, _) in enumerate(blocks) if b.startswith(prefix)]
    if len(hits) != 1:
        raise ValueError(f"{what}: {prefix!r} matches {len(hits)} blocks")
    return hits[0]


def lesson_title(text):
    m = re.search(r"^# (.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def placeholder_text(slug, title, ex):
    moved = [m for m in ex["moved"] if m]
    out = [f"# {title} - {ex['name']} (placeholder)", "",
           f"Lesson: [{slug}.md](../{slug}.md)", "",
           "> **Placeholder.** The real exercise for this spot is not mapped yet. "
           "The lesson links here where the exercise sat; the text below only referred to the "
           "exercise, so it was moved here from the lesson. Replace this file with the exercise "
           "when it is mapped.", ""]
    if moved:
        out += ["## Text moved from the lesson", ""]
        for m in moved:
            out += [m, ""]
    else:
        out += [ex.get("empty_note") or "No lesson text was moved here: the spot was a heading only.", ""]
    return "\n".join(out)


def load_spec():
    """All exercise specs by lesson slug (Python, Learn SQL and the one Interview SQL lesson)."""
    spec = {}
    for p in SPEC_FILES:
        with open(p, encoding="utf-8") as f:
            spec.update(json.load(f))
    return spec


def apply_lesson(path, exercises=None):
    """Rewrite one lesson file and write its placeholders. Returns the number of exercises placed."""
    slug = os.path.basename(path)[:-3]
    if exercises is None:
        exercises = load_spec().get(slug, [])
    if not exercises:
        return 0  # no entry for this lesson: leave the file alone
    text = open(path, encoding="utf-8").read()
    title = lesson_title(text)
    folder = os.path.join(os.path.dirname(path), "_exercises")
    placed = 0
    for n, ex in enumerate(exercises, 1):
        # once the exercise is placed its trims have run (a heading may have been renamed since)
        placed_already = (not ex.get("trim_only")
                          and f"Exercise: [{ex['name']}](_exercises/{slug}_exercise_{n}.md)" in text)
        for find, repl in ex.get("trim", []):
            if find not in text and repl and repl not in text and not placed_already:
                raise ValueError(f"{slug}: trim text not found (neither old nor new): {find!r}")
            text = text.replace(find, repl)
    blocks = parse_blocks(text)
    # positions are found on the untouched block list, then edited from the end backwards
    ops = []  # (index, kind, new blocks)
    for n, ex in enumerate(exercises, 1):
        if ex.get("trim_only"):
            continue  # sentence trims only, no placeholder
        rel = f"_exercises/{slug}_exercise_{n}.md"
        link = f"Exercise: [{ex['name']}]({rel})"
        if any(link in b for b, _ in blocks):
            continue  # already placed
        what = f"{slug} exercise {n}"
        hi = None
        if "heading" in ex:
            hits = [i for i, (b, _) in enumerate(blocks) if b == ex["heading"]]
            hi = hits[ex.get("heading_nth", 0)]
        new_heading = ex.get("heading_new")
        if "before" in ex:
            ai = find_block(blocks, ex["before"], what)
            ops.append((ai, "insert_before", ([new_heading] if new_heading and hi is None else []) + [link]))
            if hi is not None:
                ops.append((hi, "replace", [new_heading] if new_heading else []))
        elif "after" in ex:
            ai = find_block(blocks, ex["after"], what)
            ops.append((ai, "insert_after", ([new_heading] if new_heading and hi is None else []) + [link]))
            if hi is not None:
                ops.append((hi, "replace", [new_heading] if new_heading else []))
        elif hi is not None:
            ops.append((hi, "replace", ([new_heading] if new_heading else []) + [link]))
        else:
            raise ValueError(f"{what}: no heading, before or after")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, f"{slug}_exercise_{n}.md"), "w", encoding="utf-8") as f:
            f.write(placeholder_text(slug, title, ex))
        placed += 1
    order = {"replace": 0, "insert_after": 1, "insert_before": 1}
    for idx, kind, new in sorted(ops, key=lambda o: (-o[0], order[o[1]])):
        sep = "\n\n"
        if kind == "replace":
            sepafter = blocks[idx][1]
            blocks[idx:idx + 1] = [[b, sep] for b in new[:-1]] + ([[new[-1], sepafter]] if new else [])
        elif kind == "insert_before":
            blocks[idx:idx] = [[b, sep] for b in new]
        else:
            sepafter = blocks[idx][1]
            blocks[idx][1] = sep
            blocks[idx + 1:idx + 1] = [[b, sep] for b in new[:-1]] + [[new[-1], sepafter]]
    # leftover "Practice" / "Capstone" headings: drop the word, remove a bare heading
    out = []
    for b, sep in blocks:
        m = LEFTOVER.match(b)
        if m:
            if m.group(2):
                name = m.group(2)
                out.append([f"{m.group(1)} {name[0].upper()}{name[1:]}", sep])
            continue
        out.append([b, sep])
    blocks = out
    with open(path, "w", encoding="utf-8") as f:
        f.write(join_blocks(blocks))
    return placed


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else None
    spec = load_spec()
    total = 0
    roots = [root] if len(sys.argv) > 1 else [
        os.path.join(HERE, "..", "lessons", "learn", "python"),
        os.path.join(HERE, "..", "lessons", "learn", "sql"),
        os.path.join(HERE, "..", "lessons", "interview", "sql")]
    for root in roots:
        for d, _, files in sorted(os.walk(root)):
            for name in sorted(files):
                if name.endswith(".md") and os.path.basename(d) != "_exercises" and name[:-3] in spec:
                    total += apply_lesson(os.path.join(d, name), spec[name[:-3]])
    print(f"{total} placeholder(s) written")


if __name__ == "__main__":
    main()
