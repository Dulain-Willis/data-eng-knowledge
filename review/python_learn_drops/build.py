"""Builds README.md (the review page) from places.json + decisions.py. Converted Markdown comes from
tools/lesson_to_md.py's convert() run on the live page HTML (exercises left out); drop prefixes are
taken from that Markdown and checked against the converter's own matching."""
import json, os, re, sys, io, contextlib, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools")); sys.path.insert(0, HERE)
import lesson_to_md as c
from decisions import D
from bs4 import BeautifulSoup

places = json.load(open(os.path.join(HERE, "places.json")))
norm = lambda t: " ".join(t.split())
key = lambda t: re.sub(r"[\s`*]", "", t)
cache = {}

def load(slug):
    if slug not in cache:
        req = urllib.request.Request(c.BASE + slug, headers={"User-Agent": "lesson-to-md/1.0"})
        html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "ignore")
        with contextlib.redirect_stderr(io.StringIO()):
            md = c.convert(html, [], [], {}, False, [], [])
        blocks = BeautifulSoup(html, "html.parser").find_all(attrs={"data-note-block-type": True})
        cache[slug] = (html, md, [(b["data-note-block-type"], norm(b.get_text(" "))) for b in blocks])
    return cache[slug]

def chunks(md):
    out, cur, fence = [], [], False
    for l in md.split("\n"):
        if l.startswith("```"): fence = not fence
        if not l.strip() and not fence:
            if cur: out.append("\n".join(cur)); cur = []
        else: cur.append(l)
    if cur: out.append("\n".join(cur))
    return [x for x in out if x.strip() not in ("<br>", "---")]

def plain(t): return re.sub(r"^(#+ |> )", "", t.replace("`", "").replace("**", "")).replace("\\", "")

def md_chunk(p):
    html, md, info = load(p["lesson"])
    ch = chunks(md)
    b = info[p["idx"]]
    if p["mode"] == "mid": pre = key(p["prefix"])[:40]
    else: pre = key(b[1])[:40]
    hits = [i for i, x in enumerate(ch) if not x.startswith("|") and
            (key(re.sub(r"^#+ ", "", x)).startswith(pre) if p["mode"] == "start" else pre in key(x))]
    k = sum(1 for q in info[:p["idx"]] if q == b)  # n-th identical block (the repeated "Practice" h3s)
    return ch, hits[min(k, len(hits) - 1)]

def make_prefix(p, chunk):
    """Longest leading run of the converted Markdown text that the converter's own matcher accepts."""
    html, md, info = load(p["lesson"])
    mdt = norm(plain(chunk)); htm = norm(info[p["idx"]][1])
    n = 0
    while n < min(len(mdt), len(htm)) and mdt[n] == htm[n]: n += 1
    common = mdt[:n]
    if len(common) <= 60: return common.rstrip()
    return common[:60].rsplit(" ", 1)[0].rstrip()

def trunc(t, n):
    t = t.strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " ..."

def quote(t, n=700):
    return "\n".join("> " + l if l else ">" for l in trunc(t, n).split("\n"))

rows = []
for n, p in enumerate(places, 1):
    html, md, info = load(p["lesson"])
    ch, i = md_chunk(p)
    tgt = ch[i]
    default, why, cut = D[n]
    if cut: assert cut in tgt, (n, cut, tgt)
    prefix = make_prefix(p, tgt)
    matches = sum(1 for t, tx in info if t not in ("section_header", "lesson_title") and tx.startswith(prefix))
    # confirm with the converter itself: the block disappears from the Markdown when the prefix is a drop
    with contextlib.redirect_stderr(io.StringIO()):
        md2 = c.convert(html, [], [], {}, True, [prefix], [])
    gone = tgt not in chunks(md2)
    if p["mode"] == "mid":
        pnote = "n/a, the sentence is the tail of a longer paragraph: a prefix would drop the whole paragraph, so trim by hand"
    elif default == "trim":
        pnote = f"`{prefix}` (would drop the whole block, so for a trim edit the Markdown by hand instead)"
    else:
        pnote = f"`{prefix}`"
        if matches != 1 and default == "drop": pnote += f" **(matches {matches} blocks in this lesson and drops.json drops them all: fine only if all {matches} are drops)**"
        if not gone: pnote += " **(converter did not remove the block; check)**"
    first = re.split(r"(?<=[.!?:]) ", plain(tgt))[0]
    sentence = cut or (first if not tgt.startswith("#") else plain(tgt))
    prv = ch[i - 1] if i else "(start of lesson)"
    nxt = ch[i + 1] if i + 1 < len(ch) else "(end of lesson)"
    rows.append(dict(n=n, p=p, default=default, why=why, cut=cut, pnote=pnote, sentence=sentence,
                     prv=prv, tgt=tgt, nxt=nxt, ok=(p["mode"] == "mid" or (gone and (matches == 1 or tgt.startswith("###"))))))

out = ["# Learn Python: drop / keep / trim decisions (ticket #18, parent spec #10)", "",
"> **NEVER MERGE.** Temporary review PR (branch `review-python-learn-drops`). It exists so the owner can look at the pictures and decide; close it afterwards. If it were ever merged it would need a squash that removes this folder.", "",
f"{len(rows)} places from the HANDOFF section 7 lists (32 definite, 24 needs-a-skim). For each: the live page with the target block outlined in red, one block before and one after (2x, 1100px wide, taken from the live site, where exercise widgets show as rendered), the converted Markdown around it, and a **proposed default**. The proposals are only proposals: tick one box per place. Decisions are recorded by ticking the box and saying so on the PR; then the \"drop\" ones go into `tools/drops.json` and the \"trim\" ones are hand-edited.", "",
"How the numbers fit together: the Markdown is what `tools/lesson_to_md.py` produces for the lesson with the exercises left out (exercise widgets are not in it, multiple-choice blocks are). Drop prefixes come from that Markdown and were checked with the converter's own matcher; `drops.json` matches a block-start prefix against every block of the lesson, and removes the whole block.", "",
"## Index", "", "| # | Lesson | Group | Place | Proposed |", "| --- | --- | --- | --- | --- |"]
for r in rows:
    p = r["p"]
    out.append(f"| [{r['n']}](#place-{r['n']}) | `{p['lesson']}` | {p['group'].lower()} | {p['section']}: {p['sub'] if not p['sub'].startswith('(none') else 'Practice'} | **{r['default']}** |")
for r in rows:
    p = r["p"]
    sub = p["sub"] if not p["sub"].startswith("(none") else "(none; the h3 \"Practice\" of this section)"
    out += ["", f"## Place {r['n']}", "",
      f"- Lesson slug: `{p['lesson']}` (https://datadriven.io/learn/{p['lesson']})",
      f"- Group: {p['group']} | Section: {p['section']} | Sub-heading: {sub}",
      f"- The sentence: `{r['sentence']}`",
      f"- Drop prefix (from the converted Markdown): {r['pnote']}",
      "", "Converted Markdown (block before, target, block after):", "",
      quote(r["prv"], 350), ">", "> **TARGET**", quote(r["tgt"], 900), ">", quote(r["nxt"], 350), "",
      f"![place {r['n']}](img/{r['n']:02d}_{p['lesson']}.png)", "",
      f"- Proposed default: **{r['default']}**. {r['why']}", "",
      "- Decision (owner): [ ] drop   [ ] keep   [ ] trim"]
    if r["cut"]: out.insert(len(out) - 2, f"- Trim would cut: `{r['cut']}`")
open(os.path.join(HERE, "README.md"), "w").write("\n".join(out) + "\n")
bad = [r["n"] for r in rows if not r["ok"]]
from collections import Counter
print(Counter(r["default"] for r in rows), "check:", bad)
