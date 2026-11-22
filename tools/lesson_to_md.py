#!/usr/bin/env python3
"""Convert a datadriven.io lesson page into a local Markdown file.

Usage:
    .venv/bin/python tools/lesson_to_md.py <lesson-url-or-slug> [out_dir] [--screenshots]

markdownify does the HTML -> Markdown work. The rules below only cover this
site's custom blocks (code tables, stat callouts, tips, the pipeline diagram).
--screenshots needs playwright (see screenshot_diagrams) and saves the
pipeline diagram as an image next to the Markdown.

For personal study use. The output folder comes from tools/topics.json, which maps each lesson slug
(tier suffix dropped) to its topic folder under lessons/, matching the site's UI cards. A slug missing
from the map stops the script: add an entry, or pass out_dir explicitly to override.
"""
import base64
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

from bs4 import BeautifulSoup
from bs4.builder import HTMLParserTreeBuilder
from markdownify import markdownify

BASE = "https://datadriven.io/learn/"
# The Pipeline Architecture exercises are not in the lesson HTML; the page loads them from here.
CHALLENGES_URL = "https://datadriven.io/proxy/challenges/"
# Visual blocks that plain text can't represent; each is saved as a screenshot.
DIAGRAM_LABELS = {"pipeline_diagram": "Pipeline diagram", "schema_diagram": "Schema diagram"}
DIAGRAM_SELECTOR = ", ".join(f'[data-note-block-type="{k}"]' for k in DIAGRAM_LABELS)
NOISE = ["script", "style", "nav", "footer", "button", "svg", "canvas", "head"]

# Block types with a custom rule below, plus ones markdownify handles well as-is.
# Anything else triggers a warning so a new rule can be added.
CUSTOM_BLOCKS = {
    "static_code", "big_number", "tip", "callout", "fun_fact", "key_takeaways",
    "synthesis", "icon_list", "info_list", *DIAGRAM_LABELS,
    "multiple_choice", "schema_story", "best_practices", "comparison", "placed_challenge",
    "executable_spark", "executable_python", "executable_sql", "regex_cards", "sql_switcher",
}
# Runnable cells: block type -> how the run control is found. Spark has a "Run" button and draws its
# output with JavaScript; Python cells have a ">>>" button that reveals the output the page already holds.
CELL_KINDS = ("executable_spark", "executable_python", "executable_sql")
CELL_FENCE = {"executable_spark": "python", "executable_python": "python", "executable_sql": "sql"}
# Interactive exercise with no answers in the page, so what's left is a dangling question.
# Dropped. (multiple_choice used to be here; its answers ARE in the page's embedded JSON.)
# placed_challenge: empty stub for Airflow exercises; sql_parsons: a drag-the-tiles exercise (Learn SQL), left out with the SQL exercises
SKIPPED_BLOCKS = {"schema_story", "placed_challenge", "sql_parsons"}
GENERIC_BLOCKS = {
    "lesson_title", "learning_objectives", "section_header", "h3", "body_text",
    "rich_text", "static_table", "side_by_side_tables", "comparison",
    "note_text", "rich_info_list", "h4", "full_width",
}


# Animation players: every "*_animation" block, plus table_visualization (Learn SQL, aggregating_beginner),
# which is the same player under another block type name.
ANIMATION_RE = re.compile(r"(_animation|^table_visualization)$")
ANIMATION_SELECTOR = '[data-note-block-type$="_animation"], [data-note-block-type="table_visualization"]'


def block_type(tag):
    return tag.get("data-note-block-type")


def parse(html):
    """Parse HTML, keeping whitespace inside table cells.

    The site indents code with a whitespace-only <span> and CSS (white-space: pre),
    not a <pre> tag, and BeautifulSoup would collapse those spans to one space.
    """
    builder = HTMLParserTreeBuilder()
    builder.preserve_whitespace_tags = set(builder.preserve_whitespace_tags) | {"td"}
    return BeautifulSoup(html, builder=builder)


def load_drops(slug):
    """Text prefixes of blocks to drop from this lesson when its exercises are left out, from
    tools/drops.json: prose or headings that only introduce an exercise ("The drill below ...").
    Kept by hand, one entry per block, so nothing is deleted by pattern."""
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "drops.json")) as f:
        return json.load(f).get(slug, [])


def clean(soup):
    # "Official <Tool> resources" panel (logo, quote, doc buttons, link table) ends every tool lesson
    for panel in soup.select("[data-tool-partner-panel]"):
        panel.decompose()
    for t in soup.select(".sr-only"):
        t.decompose()
    # the row above the title (level, minutes, challenge count, tool logo): the level is in the
    # title, the exercises live in their own folders, so the lesson starts at its title
    for h1 in soup.find_all("h1"):
        row = h1.find_previous_sibling("div")
        if row is not None and row.select_one(".mini-bars"):
            row.decompose()
    # decorative "//" that sits beside some headings
    for span in soup.find_all("span"):
        if span.get_text(strip=True) == "//" and not span.find_parent("td"):
            span.decompose()
    for t in soup(NOISE):
        t.decompose()
    # decorative icons and logos carry no content
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "data_icons" in src or "logo" in src:
            img.decompose()
    # the site puts a triangle in each list item; markdown adds its own bullet
    for text in soup.find_all(string=lambda s: s and s.lstrip().startswith("▸")):
        text.replace_with(text.lstrip().lstrip("▸").lstrip())


def code_block(soup, block):
    """Code arrives as a table with the code in the last column."""
    lines = [tr.find_all("td")[-1].get_text() for tr in block.find_all("tr") if tr.find_all("td")]
    pre = soup.new_tag("pre")
    code = soup.new_tag("code", attrs={"class": "language-sql"})
    code.string = "\n".join(lines)
    pre.append(code)
    block.replace_with(pre)


def big_numbers(soup, block):
    """Pair each figure with its caption: '- **400 GB** - scanned per day'."""
    ul = soup.new_tag("ul")
    for card in block.select("div.text-2xl"):
        figure, caption = card.get_text(strip=True), card.find_next_sibling("div")
        li = soup.new_tag("li")
        li.append(BeautifulSoup(f"<strong>{figure}</strong> — {caption.get_text(strip=True) if caption else ''}", "html.parser"))
        ul.append(li)
    block.replace_with(ul)


def callout(soup, block, label=None):
    quote = soup.new_tag("blockquote")
    if label:
        # the site already prints the label inside the box; bold it, don't repeat it
        existing = block.find(string=lambda s: s and s.strip().upper() == label)
        if existing:
            existing.replace_with(BeautifulSoup(f"<strong>{label}</strong>", "html.parser"))
        else:
            p = soup.new_tag("p")
            p.append(BeautifulSoup(f"<strong>{label}</strong>", "html.parser"))
            quote.append(p)
    for child in list(block.children):
        quote.append(child.extract())
    block.replace_with(quote)


def bullet_section(soup, block):
    """Key takeaways / putting it all together: a titled section of bullets.

    The site draws the bullets on a canvas, so the HTML has plain divs, not
    list items. Items are the long outermost spans; the title is the short
    all-caps span (with any decorative arrows removed).
    """
    title, items = None, []
    for span in block.find_all("span"):
        text = span.get_text(" ", strip=True).replace("❯", "").strip()
        if span.find_parent("span") or span.find("div") or not text:
            continue
        if len(text) >= 40:
            items.append(text)
        elif text.isupper() and not title:
            title = text.title()
    section = soup.new_tag("div")
    heading = soup.new_tag("h2")
    heading.string = title or "Summary"
    section.append(heading)
    intro = block.find("p")
    if intro:
        intro.string = intro.get_text(strip=True).removeprefix(">").strip()
        section.append(intro.extract())
    ul = soup.new_tag("ul")
    for text in items:
        li = soup.new_tag("li")
        li.string = text
        ul.append(li)
    section.append(ul)
    block.replace_with(section)


def info_list(soup, block):
    """Rows of label, optional gray tag, description, as sibling spans.

    The site makes the label bold and the tag gray with styling alone, so the
    spans fuse into one run of text. Rebuild each row as: **label** *tag*, then
    the description on its own line. One-span rows are plain text and stay as is.
    """
    for li in block.find_all("li"):
        parts = [s.get_text(" ", strip=True) for s in li.find_all("span")
                 if s.get_text(strip=True) and not s.find("span")]
        if len(parts) < 2:
            continue
        label, *tag, description = parts
        strong = soup.new_tag("strong")
        strong.string = label
        li.clear()
        li.append(strong)
        if tag:
            em = soup.new_tag("em")
            em.string = " ".join(tag)
            li.append(" ")
            li.append(em)
        li.append(soup.new_tag("br"))
        li.append(description)


def icon_list(soup, block):
    """Rows of a decorative icon plus a sentence: the icon is dropped (clean()
    removes it), and each row's text becomes a bullet. The HTML has no list tags."""
    ul = soup.new_tag("ul")
    for div in block.find_all("div"):
        text = div.get_text(" ", strip=True)
        if text and not div.find("div"):
            li = soup.new_tag("li")
            li.string = text
            ul.append(li)
    block.replace_with(ul)


def diagram(soup, block, image_name, number):
    label = DIAGRAM_LABELS[block_type(block)]
    if image_name:
        p = soup.new_tag("p")
        p.append(soup.new_tag("img", src=f"_images/{image_name}", alt=f"{label} {number}"))
        block.replace_with(p)
    else:
        note = soup.new_tag("p")
        note.string = f"[{label}: not captured. Re-run with --screenshots]"
        block.replace_with(note)


MC_TOKEN = "@@MULTIPLE-CHOICE-{}@@"


def question_key(text):
    """Match key for a question: inline code is rendered without its quote marks
    (JSON has DATE '2026-04-22', the page shows DATE 2026-04-22), so drop quotes,
    backticks and whitespace before comparing."""
    return re.sub(r"[\s'\"`]", "", text)


def embedded_questions(html):
    """{question text: question dict} for every multiple_choice block in the page's JSON.

    The page is a Next.js app: lesson data sits in self.__next_f.push([1, "<chunk>"])
    script strings. The rendered options are buttons with no correct-answer marker, but
    the JSON holds is_correct and an explanation per option.
    """
    chunks = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', html)
    text = "".join(json.loads(c) for c in chunks)
    decoder, found = json.JSONDecoder(), {}
    # Key order varies (a question with a code snippet has "code" before "type"), so
    # "type" is not always the first key. Walk back from each marker to the "{" that
    # opens a block object which decodes and holds this type.
    for m in re.finditer(r'"type":"multiple_choice"', text):
        start = m.start()
        for _ in range(300):
            start = text.rfind("{", 0, start)
            if start < 0:
                break
            try:
                q, end = decoder.raw_decode(text, start)
            except ValueError:
                continue
            if isinstance(q, dict) and q.get("type") == "multiple_choice" and "question" in q:
                found[question_key(q["question"])] = q
                break
    return found


def multiple_choice_markdown(q):
    """Question, lettered options, then a closed <details> with the answer and why the rest are wrong."""
    opts = [(chr(ord("A") + i), o) for i, o in enumerate(q["options"])]
    lines = [f"**{q['question']}**", ""]
    if q.get("code"):
        lines += [f"```{q.get('language', '')}", q["code"], "```", ""]
    lines += [f"- **{letter}.** {o['text']}" for letter, o in opts]
    lines += ["", "<details>", "<summary>Solution</summary>", ""]
    for letter, o in opts:
        if o.get("is_correct"):
            lines += [f"**{letter}.** {o['text']}", ""]
            if o.get("explanation"):
                lines += [o["explanation"], ""]
    wrong = [(letter, o) for letter, o in opts if not o.get("is_correct")]
    if wrong:
        lines += ["**Why the others are wrong**", ""]
        lines += [f"- **{letter}.** {o.get('explanation') or o['text']}" for letter, o in wrong]
        lines.append("")
    lines.append("</details>")
    return "\n".join(lines)


def tick_cross(soup, block, tokens):
    """A tick/cross pair (Do and Don't, or any two labelled lists) as one table.

    The two labels are the headers and each side's bullets sit in one cell, joined by line
    breaks. Cells cannot hold real lists, so the bullet is a character; a long bullet that
    wraps goes back to the left edge. Built here as Markdown (swapped in after markdownify)
    because a line break inside a cell would otherwise end the table row.
    """
    sides = []
    for ul in block.find_all("ul"):
        head = ul.find_previous_sibling("div")
        spans = head.find_all("span", recursive=False) if head else []
        if len(spans) < 2:
            return  # a shape we haven't seen: leave it to the generic conversion
        items = []
        for li in ul.find_all("li", recursive=False):
            text = markdownify(li.find_all("span", recursive=False)[-1].decode_contents(),
                               escape_underscores=False)
            items.append("• " + " ".join(text.split()).replace("|", "\\|"))
        sides.append((f"{spans[0].get_text(strip=True)} {spans[1].get_text(strip=True)}", items))
    if len(sides) != 2:
        return
    token = f"@@TICK-CROSS-{len(tokens)}@@"
    tokens[token] = ("| " + " | ".join(h.replace("|", "\\|") for h, _ in sides) + " |\n| --- | --- |\n| "
                     + " | ".join("<br><br>".join(items) for _, items in sides) + " |")
    marker = soup.new_tag("p")
    marker.string = token
    block.replace_with(marker)


def spark_cell(soup, block, tokens, image_name, number, lang="python"):
    """A runnable PySpark cell: a screenshot of the cell after Run (tables, code and output), then the
    code as a ```python fence. The page draws the editor and result with JavaScript, so the image
    can only be a screenshot (see record_cells); the fence keeps the code as text, because long
    lines scroll sideways in the screenshot. Built as Markdown and swapped in after markdownify.
    """
    pre = block.find("pre")
    if pre:
        code = pre.get_text().strip("\n")
    elif block.find("table"):  # Python cells: one table row per line, code in the last cell
        code = "\n".join(tr.find_all("td")[-1].get_text() for tr in block.find("table").find_all("tr")
                         if tr.find_all("td")).strip("\n")
    else:
        code = block.get_text().strip("\n")
    shot = (f"![Run output {number}](_images/{image_name})" if image_name
            else f"[Run output {number}: not captured. Re-run with --screenshots]")
    token = f"@@SPARK-CELL-{len(tokens)}@@"
    tokens[token] = f"{shot}\n\n```{lang}\n{code}\n```"
    marker = soup.new_tag("p")
    marker.string = token
    block.replace_with(marker)


def switcher_panel(html):
    """Parse the HTML of one sql_switcher block in one tab state into
    {"caption", "sql", "result"}. The block holds the tab bar, one caption div, one code table
    (a row per line, code in the last cell) and a Result table (rendered in the DOM even while it
    is collapsed on the page). `result` is a list of rows (header first), or [] if there is none."""
    soup = parse(html)  # keeps the indentation spans of the code cells
    content = soup.find(attrs={"data-note-content": True}) or soup
    caption = ""
    tables = soup.find_all("table")
    code_table = next((t for t in tables if t.find("td", attrs={"data-ln": True})), None)
    if code_table is None:
        print("warning: sql_switcher panel has no code table; fields left empty", file=sys.stderr)
        return {"caption": "", "sql": "", "result": []}
    sql = "\n".join(tr.find_all("td")[-1].get_text() for tr in code_table.find_all("tr")
                    if tr.find_all("td")).strip("\n")
    # the caption is the first plain text div (no tab buttons, tables or nested divs): it sits between the
    # tab bar and the code; the saved HTML has no buttons (clean() drops them), the live one does
    for el in content.find_all("div"):
        if el.find(["div", "table", "button"]) or el.find_parent("table"):
            continue
        text = " ".join(el.get_text(" ").split())
        if text:
            caption = text
            break
    result = []
    result_table = next((t for t in tables if t is not code_table and t.find("th")), None)
    if result_table:
        result = [[" ".join(c.get_text(" ").split()) for c in tr.find_all(["th", "td"])]
                  for tr in result_table.find_all("tr")]
    return {"caption": caption, "sql": sql, "result": result}


def switcher_markdown(tabs):
    """Option B (owner decision): every tab stays as text and gets a screenshot. A bold label with the
    tab's name, its caption, one 2x screenshot of the tab panel (tab bar, caption, code and the revealed
    result table, see sql_switcher_tabs), then its SQL as a ```sql fence, the same "screenshot + fence" pair
    as an executable_sql cell. `tabs` is [{"name", "caption", "sql", "result", "image"}] in tab order
    (switcher_panel plus the tab button's name; "image" is the file name in _images, or None). A tab with
    no image (run without --screenshots) falls back to Option A: its result as text after the fence."""
    parts = []
    for t in tabs:
        part = [f"**{t['name']}**"]
        if t["caption"]:
            part.append(t["caption"])
        if t.get("image"):
            part.append(f"![{t['name']} result](_images/{t['image']})")
        part.append(f"```sql\n{t['sql']}\n```")
        if t["result"] and not t.get("image"):
            rows = "\n".join(" | ".join(r) for r in t["result"])
            part.append(f"Result:\n\n```\n{rows}\n```")
        parts.append("\n\n".join(part))
    return "\n\n".join(parts)


def sql_switcher_tabs(url, out_dir=None, slug=None):
    """Click every tab of every sql_switcher block on the live page and return, per block, the list of
    {"name", "caption", "sql", "result", "image"}. The saved page HTML holds only the first tab's panel, so
    the other tabs exist only after a click. Returns [] without playwright.

    With out_dir (the --screenshots run), each tab is also shot: after the tab click the "Show result" button
    is pressed exactly as for an executable_sql cell (_click_run; a tab switch collapses the result again, so
    it is pressed for every tab) and the whole block, tab bar, caption, code and result table, is saved at 2x as
    <slug>_switcher_<block>_<tab>.png (both numbers from 1). A tab whose shot fails has image None."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed; tab panels not captured", file=sys.stderr)
        return []
    img_dir = os.path.join(out_dir, "_images") if out_dir else None
    if img_dir:
        os.makedirs(img_dir, exist_ok=True)
    out = []
    with sync_playwright() as p:
      browser = p.chromium.launch()
      try:
        page = browser.new_page(viewport={"width": 1000, "height": 900},
                                color_scheme="light", device_scale_factor=2)
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        blocks = page.locator('[data-note-block-type="sql_switcher"]')
        for i in range(blocks.count()):
            block = blocks.nth(i)
            block.scroll_into_view_if_needed()
            # the 3 icon buttons have a title; tabs do not. Click by position: has_text would match substrings
            tab_buttons = block.locator("button").evaluate_all(
                "els => els.map((e, i) => [i, !e.title && !e.getAttribute('aria-label'), e.innerText.trim()])"
                ".filter(t => t[1]).map(t => [t[0], t[2]])")
            tabs = []
            for k, (idx, n) in enumerate(tab_buttons):
                block.locator("button").nth(idx).click()
                page.wait_for_timeout(350)
                tab = {"name": n, **switcher_panel(block.evaluate("e => e.outerHTML")), "image": None}
                if img_dir:
                    try:
                        _click_run(page, block, "executable_sql")
                        page.evaluate(_HIDE_FIXED)
                        name = f"{slug}_switcher_{i + 1}_{k + 1}.png"
                        block.screenshot(path=os.path.join(img_dir, name))
                        tab["image"] = name
                    except Exception as e:
                        print(f"warning: switcher {i + 1} tab {k + 1} ({n!r}) not captured: {e}", file=sys.stderr)
                tabs.append(tab)
            out.append(tabs)
      finally:
        browser.close()
    return out


def regex_cards(soup, block, tokens, image_name, number):
    """Regex example cards (python_strings_advanced): a screenshot of the stacked cards as the UI draws
    them, then the text of each card (pattern, description, example -> match) so it stays searchable."""
    shot = (f"![Regex examples](_images/{image_name})" if image_name
            else "[Regex examples: not captured. Re-run with --screenshots]")
    items = []
    for card in block.find_all("code"):
        body = card.find_parent("div", class_=lambda c: c and "flex-1" in c)
        if body is None:
            continue
        desc = body.find("p")
        spans = [sp.get_text(strip=True) for sp in body.find_all("span")]
        example = f"`{spans[0]}` -> `{spans[-1]}`" if len(spans) >= 3 else ""
        items.append(f"- `{card.get_text(strip=True)}`: {desc.get_text(' ', strip=True) if desc else ''}"
                     + (f" Example: {example}" if example else ""))
    token = f"@@REGEX-CARDS-{len(tokens)}@@"
    tokens[token] = shot + "\n\n" + "\n".join(items)
    marker = soup.new_tag("p")
    marker.string = token
    block.replace_with(marker)


def animation_info(html):
    """Each animation block in page order: its mode labels and the caption under the player.

    Read before clean() strips the buttons. A block with toggles (Query-based / Log-based)
    has one radio button per mode; the caption is a paragraph right after the player.
    """
    soup = parse(html)
    out = []
    for block in soup.find_all(attrs={"data-note-block-type": ANIMATION_RE}):
        labels = [b.get_text(strip=True) for b in block.find_all("button", attrs={"role": "radio"})]
        caption = ""
        for para in block.find_all("p"):
            before = para.find_previous_sibling()
            if before is not None and before.find("button"):
                caption = " ".join(para.get_text().split())
                break
        out.append({"labels": labels, "caption": caption})
    return out


def animation(soup, block, tokens, info, files):
    """An animation block as its video URL(s) (or still images), one per mode, and the caption as plain text.

    The playback is drawn by JavaScript, so it can only be a recording (see record_animations).
    Built as Markdown and swapped in after markdownify.
    """
    parts = []
    for label, name in files or []:
        if name.endswith(".mp4"):  # uploaded (upload_animation); a bare URL on its own line renders as a video
            shown = json.load(open(URLS_FILE)).get(name, name)  # already uploaded by main() before the Markdown is written
        else:
            shown = f"![{label or 'Animation'}](_images/{name})"
        parts.append((f"**{label}**\n\n" if label else "") + shown)
    if not parts:
        parts.append("[Animation: not captured. Re-run with --screenshots]")
    if info.get("caption"):
        parts.append(f"*{info['caption']}*")
    token = f"@@ANIMATION-{len(tokens)}@@"
    tokens[token] = "\n\n".join(parts)
    marker = soup.new_tag("p")
    marker.string = token
    block.replace_with(marker)


def convert(html, diagram_images=(), exercises=(), animations=None, drop_exercise_refs=False, drops=(), cells=(), regex_images=(), switchers=()):
    """diagram_images: screenshot file names, in page order, one per diagram block.
    drop_exercise_refs: the exercises are left out, so drop the blocks listed in `drops`
    (text prefixes from tools/drops.json) that only introduce one; an entry that matches
    nothing prints a warning.
    switchers: per sql_switcher block in page order, its tabs (sql_switcher_tabs); empty means first tab only.
    cells: {block kind: file names of its run-output screenshots, in page order} (record_cells, one call per kind;
    a plain list is taken for every kind); empty without --screenshots.
    exercises: [(anchor block id or None, markdown)]; each goes right after its anchor block,
    and the ones with no anchor are returned by the caller to append."""
    dropped = set()
    animation_infos = animation_info(html)
    soup = parse(html)
    clean(soup)
    tokens = {}
    for i, (anchor, md_text) in enumerate(exercises):
        block = soup.find(attrs={"data-note-block": anchor}) if anchor else None
        if block is None:
            print("warning: exercise position not found in the page; it goes at the end", file=sys.stderr)
            tokens[None] = tokens.get(None, "") + "\n\n" + md_text
            continue
        p = soup.new_tag("p")
        p.string = EXERCISE_TOKEN.format(i)
        block.insert_after(p)
        tokens[EXERCISE_TOKEN.format(i)] = md_text
    diagrams_seen = animations_seen = cells_seen = regex_seen = switchers_seen = 0
    kind_seen = dict.fromkeys(CELL_KINDS, 0)  # per kind: each kind has its own list of screenshots
    questions = embedded_questions(html)
    for block in soup.find_all(attrs={"data-note-block-type": True}):
        kind = block_type(block)
        if kind not in CUSTOM_BLOCKS | GENERIC_BLOCKS | SKIPPED_BLOCKS and not ANIMATION_RE.search(kind):
            print(f"warning: no rule for block type '{kind}'; used generic conversion",
                  file=sys.stderr)
        if kind in SKIPPED_BLOCKS:
            block.decompose()
        elif drop_exercise_refs and any(
                " ".join(block.get_text(" ").split()).startswith(d) for d in drops):
            hit = next(d for d in drops if " ".join(block.get_text(" ").split()).startswith(d))
            dropped.add(hit)
            block.decompose()
        elif kind == "multiple_choice":
            p_el = block.find("p")
            q = questions.get(question_key(p_el.get_text())) if p_el else None
            if q is None:
                print("warning: multiple_choice answers not found in the page; block dropped",
                      file=sys.stderr)
                block.decompose()
                continue
            token = MC_TOKEN.format(len(tokens))
            tokens[token] = multiple_choice_markdown(q)
            new = soup.new_tag("p")
            new.string = token
            block.replace_with(new)
        elif kind == "regex_cards":
            name = regex_images[regex_seen] if regex_seen < len(regex_images) else None
            regex_seen += 1
            regex_cards(soup, block, tokens, name, regex_seen)
        elif kind in CELL_KINDS:
            names = cells.get(kind, []) if isinstance(cells, dict) else cells
            name = names[kind_seen[kind]] if kind_seen[kind] < len(names) else None
            kind_seen[kind] += 1
            cells_seen += 1
            spark_cell(soup, block, tokens, name, cells_seen, CELL_FENCE[kind])
        elif kind == "sql_switcher":
            tabs = switchers[switchers_seen] if switchers_seen < len(switchers) else None
            switchers_seen += 1
            if not tabs:  # no live capture: the saved HTML holds the first tab only
                print("warning: sql_switcher tabs not captured; first tab only", file=sys.stderr)
                tabs = [{"name": "Tab 1", **switcher_panel(str(block))}]
            token = f"@@SWITCHER-{len(tokens)}@@"
            tokens[token] = switcher_markdown(tabs)
            marker = soup.new_tag("p")
            marker.string = token
            block.replace_with(marker)
        elif kind == "static_code":
            code_block(soup, block)
        elif kind == "big_number":
            big_numbers(soup, block)
        elif kind == "tip":
            callout(soup, block, "TIP")
        elif kind in ("callout", "fun_fact"):
            callout(soup, block)
        elif kind in ("key_takeaways", "synthesis"):
            bullet_section(soup, block)
        elif kind == "icon_list":
            icon_list(soup, block)
        elif kind == "info_list":
            info_list(soup, block)
        elif kind in ("best_practices", "comparison"):
            tick_cross(soup, block, tokens)
        elif ANIMATION_RE.search(kind):
            info = animation_infos[animations_seen] if animations_seen < len(animation_infos) else {}
            animation(soup, block, tokens, info, (animations or {}).get(animations_seen))
            animations_seen += 1
        elif kind in DIAGRAM_LABELS:
            name = diagram_images[diagrams_seen] if diagrams_seen < len(diagram_images) else None
            diagrams_seen += 1
            diagram(soup, block, name, diagrams_seen)
    # the site italicizes with an inline style, not <em>; follow the style so any
    # lesson that uses it is handled, not just specific paragraphs
    for tag in soup.find_all(style=re.compile(r"font-style:\s*italic")):
        if tag.find_parent("em") or not tag.get_text(strip=True):
            continue
        em = soup.new_tag("em")
        for child in list(tag.contents):
            em.append(child.extract())
        tag.append(em)
    # star ratings are canvas-drawn by JS; the bare labels carry no content
    for div in soup.find_all("div"):
        if div.get_text(strip=True) in ("Daily Life", "Interviews") and not div.find("div"):
            div.decompose()
    # Text that starts with ">" (e.g. Airflow's ">> reads as 'then'") would become a Markdown
    # blockquote; escape it. Code is left alone, and the quotes the converter builds are
    # <blockquote> tags, not text, so they are unaffected.
    for text in soup.find_all(string=re.compile(r"^\s*>")):
        # only where a line starts: first text of a paragraph, list item or div (table cells and
        # text after other inline tags are not line starts, so ">=" there stays as it is)
        if text.find_parent(["code", "pre", "script", "style"]) or not starts_line(text):
            continue
        text.replace_with(re.sub(r"^(\s*)((?:>\s*)+)",
                                 lambda m: m.group(1) + "".join("\\>" for _ in m.group(2).replace(" ", "")), str(text)))
    # A literal "|" in a table cell (e.g. the set operator in "a | b", also inside code) would
    # split the cell and break the row; GFM needs "\|" there, and reads it as "|" in code too.
    for cell_tag in soup.find_all(["td", "th"]):
        for text in cell_tag.find_all(string=lambda s: "|" in s):
            text.replace_with(re.sub(r"(?<!\\)\|", r"\\|", str(text)))
    # escape_underscores=False keeps names like fare_amount readable
    # BACKSLASH line breaks survive the per-line rstrip in add_section_breaks;
    # the default two trailing spaces would not
    md = markdownify(str(soup), heading_style="ATX", bullets="-", code_language="sql",
                     escape_underscores=False, newline_style="BACKSLASH")
    for token, text in tokens.items():
        if token:
            md = md.replace(token, text)
    md = md.rstrip("\n") + (tokens[None] if None in tokens else "") + "\n"
    if drop_exercise_refs:
        for d in drops:
            if d not in dropped:
                print(f"warning: tools/drops.json entry matched nothing: {d!r}", file=sys.stderr)
    return add_section_breaks(md)


def starts_line(text):
    """True if this text is the very first thing in its paragraph, list item or div, even
    when wrapped in inline tags (the site styles inline code as a span, not <code>)."""
    node = text
    while True:
        prev = node.previous_sibling
        if prev is not None and (not isinstance(prev, str) or prev.strip()):
            return False
        node = node.parent
        if node is None:
            return False
        if node.name in ("p", "li", "div", "blockquote"):
            return True
        if node.name not in ("span", "strong", "em", "b", "i", "a"):
            return False  # table cells etc.: the line starts with the pipe, not this text


def add_section_breaks(md):
    """A gap and a rule above each section (##), a gap above each mini header (###).

    Blank lines alone collapse in Markdown, so the breaks must be visible.
    Nothing goes below a section header: a mini header right after one gets no gap.
    """
    out, in_code, last_heading = [], False, 0
    for line in (l.rstrip() for l in md.splitlines()):
        if line.startswith("```"):
            in_code = not in_code
        if not in_code and out:
            if line.startswith("## "):
                out += ["", "<br>", "", "---", ""]
            elif line.startswith("### ") and last_heading != 2:
                out += ["", "<br>", ""]
        if not in_code and line.strip():
            last_heading = 2 if line.startswith("## ") else 3 if line.startswith("### ") else 0
        out.append(line)
    return "\n".join(out).strip() + "\n"


# --- Pipeline Architecture exercises -------------------------------------------------
# A lesson can hold one or more exercise widgets (1-6 exercises in all): task, optional
# starting canvas, solution walkthrough. The widget is drawn by the browser and its
# content comes from a JSON endpoint, so there is nothing to scroll or click.

MERMAID_SHAPES = {  # node_type -> (open, close)
    "source": ("[(", ")]"), "storage": ("[(", ")]"), "transform": ("[", "]"),
    "consumer": ("([", "])"), "quality": ("{{", "}}"), "queue": ("[/", "/]"),
}
EXERCISE_TOKEN = "@@PIPELINE-ARCHITECTURE-{}@@"


def fetch_challenges(slug):
    """The lesson's exercises in order, or [] if it has none or the request fails."""
    req = urllib.request.Request(CHALLENGES_URL + slug, headers={"User-Agent": "lesson-to-md/1.0"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    except Exception as e:  # network, 404 or not JSON: the lesson text is still fine without them
        print(f"warning: no Pipeline Architecture exercises fetched ({e})", file=sys.stderr)
        return []
    return sorted(data.get("challenges", []), key=lambda c: c.get("order_index", 0))


def exercise_groups(url, challenges):
    """Split the exercises into one group per widget, each with the id of the lesson
    block it follows (None = no position known, goes at the end).

    The widget is missing from the downloaded HTML, so a browser pass reads where it sits
    and how many exercises it holds (data-challenge-ids). Needs playwright.
    """
    fallback = [(None, challenges)]
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1000, "height": 900})
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            widgets = page.evaluate("""() => {
                const out = []; let prev = null;
                for (const e of document.querySelectorAll('[data-note-block]')) {
                    if (e.getAttribute('data-note-block-type') === 'schema') {
                        const c = e.matches('[data-challenge-ids]') ? e : e.querySelector('[data-challenge-ids]');
                        const ids = c ? (c.getAttribute('data-challenge-ids') || '').trim().split(/\\s+/).filter(Boolean) : [];
                        out.push({anchor: prev, count: ids.length});
                    } else prev = e.getAttribute('data-note-block');
                }
                return out; }""")
            browser.close()
    except Exception as e:
        print(f"warning: could not place the exercises ({e}); they go at the end", file=sys.stderr)
        return fallback
    if sum(w["count"] for w in widgets) != len(challenges):
        print("warning: widget exercise counts do not match the data; exercises go at the end",
              file=sys.stderr)
        return fallback
    groups, i = [], 0
    for w in widgets:
        groups.append((w["anchor"], challenges[i:i + w["count"]]))
        i += w["count"]
    return groups


# Extra node fields the site shows as small label boxes (e.g. SLA | < 30s) -> their label.
NODE_EXTRAS = {
    "slaFreshness": "SLA", "sla_freshness": "SLA", "parallelism": "Partitions",
    "monitorAlert": "Alert", "idempotencyStrategy": "Idempotency",
    "backfillStrategy": "Backfill", "errorAction": "On error",
    "retryCount": "Retries", "retryBackoff": "Backoff",
}


def mermaid_text(t):
    """Escape text for a quoted Mermaid label; < and > are written as entity codes."""
    return str(t).replace('"', "#quot;").replace("<", "#60;").replace(">", "#62;")


def mermaid(block):
    """A solution diagram (nodes + edges, optional layers) as a Mermaid flowchart."""
    ids = {n["name"]: f"n{i}" for i, n in enumerate(block.get("nodes", []))}
    q = mermaid_text

    def node(n):
        # The site splits tech_label at commas: the first part is the caption above the
        # name (Kafka, Spark), the rest are small tags below. Extra fields such as an SLA
        # become small labels too. Mermaid has no label boxes, so tags and values go on one
        # extra line inside the node. With no tech_label the caption is the node type.
        parts = [x.strip() for x in (n.get("tech_label") or n.get("node_type") or "").split(",")]
        extras = parts[1:] + [f"{label}: {n[key]}" for key, label in NODE_EXTRAS.items() if key in n]
        label = f"{q(n['name'])}<br/>({q(parts[0])})"
        if extras:
            label += "<br/>" + q(" · ".join(extras))
        o, c = MERMAID_SHAPES.get(n.get("node_type"), ("[", "]"))
        return f'{ids[n["name"]]}{o}"{label}"{c}'

    by_name = {n["name"]: n for n in block.get("nodes", [])}
    lines, placed = ["```mermaid", "flowchart LR"], set()
    for i, layer in enumerate(block.get("layers") or []):
        members = [n for n in layer.get("node_names", []) if n in by_name and n not in placed]
        if not members:
            continue
        lines.append(f'    subgraph L{i}["{q(layer["name"])}"]')
        lines += [f"        {node(by_name[n])}" for n in members]
        lines.append("    end")
        placed.update(members)
    lines += [f"    {node(n)}" for n in block.get("nodes", []) if n["name"] not in placed]
    for e in block.get("edges", []):
        if e["from"] in ids and e["to"] in ids:
            label = f'|"{e["label"]}"|' if e.get("label") else ""
            lines.append(f"    {ids[e['from']]} -->{label} {ids[e['to']]}")
    lines.append("```")
    return "\n".join(lines)


def cell(text):
    return (text or "").replace("|", "\\|").replace("\n", "<br>")


def solution_block(b, image=None):
    """One solution block as Markdown, or None for blocks that add nothing (dividers)."""
    kind = b.get("blockType")
    if kind == "heading":
        return f"#### {b['blockText']}"
    if kind == "paragraph":
        return b["blockText"]
    if kind == "divider":
        return None
    if kind == "step":  # numbered item with the body indented under it
        body = b["body"].replace("\n", "\n   ")
        return f"{b['number']}. **{b['title']}**\n\n   {body}"
    if kind == "callout":  # one-column table: category and title on top, text below
        label = (b.get("variant") or "note").replace("_", " ").capitalize()
        return f"| {cell(label + ': ' + b['title'])} |\n| --- |\n| {cell(b['body'])} |"
    if kind == "comparison":  # the site draws a cross on the left and a tick on the right
        return (f"| ✕ {cell(b['left_label'])} | ✓ {cell(b['right_label'])} |\n| --- | --- |\n"
                f"| {cell(b['left_body'])} | {cell(b['right_body'])} |")
    if kind == "pipeline_diagram":
        return mermaid(b) + (f"\n\n*{b['caption']}*" if b.get("caption") else "")
    if kind == "follow_up":
        items = []
        for i, q in enumerate(b["questions"], 1):
            items.append(f"{i}. {q['question']}" + (f"\\\n   *{q['context']}*" if q.get("context") else ""))
        return "**Follow-up questions**\n\n" + "\n".join(items)
    if kind == "schema_diagram":  # tables and relationships: drawn by the site, so it is a screenshot
        out = (f"![Schema diagram](_images/{image})" if image
               else "[Schema diagram: not captured. Re-run with --screenshots]")
        return out + (f"\n\n*{b['caption']}*" if b.get("caption") else "")
    if kind == "code":
        out = (f"**{b['title']}**\n\n" if b.get("title") else "")
        out += f"```{b.get('language') or ''}\n{b['code']}\n```"
        return out + (f"\n\n*{b['caption']}*" if b.get("caption") else "")
    print(f"warning: no rule for Pipeline Architecture solution block '{kind}'; "
          "printed its text fields", file=sys.stderr)
    return "\n\n".join(str(v) for k, v in b.items() if k != "blockType" and isinstance(v, str)) or None


def exercises_markdown(challenges, images=None, start=0):
    """One exercise section (titled as the site does): task, starting canvas, solution.

    images: {exercise number in the lesson: screenshot file name}; start: how many
    exercises of earlier widgets come before these.
    """
    domain = ((challenges[0].get("deep_dive") or {}).get("domain") or "pipeline_architecture")
    out = ["## " + domain.replace("_", " ").title()]
    for n, c in enumerate(challenges, 1):
        out += [f"### Exercise {n} of {len(challenges)}", f"**● TASK**\n\n{c['prompt']}"]
        nodes = (c.get("config") or {}).get("provided_pipeline_nodes") or []
        if nodes:
            rows = [f"- {x['name']} (" + ", ".join(p for p in (x.get("node_type"), x.get("tech_label")) if p) + ")"
                    for x in nodes]
            out.append("**Starting canvas** (already placed for you):\n\n" + "\n".join(rows))
        # The solution is folded away until clicked, so an exercise reads as its task first.
        # The blank line after <summary> is what lets Markdown render inside the fold.
        out.append("<details>\n<summary><strong>Solution</strong></summary>")
        out += [m for m in (solution_block(b, (images or {}).get(start + n))
                            for b in (c.get("deep_dive") or {}).get("blocks") or []) if m]
        out.append("</details>")
    return "\n\n".join(out)


# --- Airflow exercises (tools/airflow lessons) ----------------------------------------
# Same endpoint as above, challenge_type "airflow". Only the dag_repair form (fix the DAG
# file) is converted; see the note above airflow_widgets for what is left out and why. The
# page's live editor + Airflow UI becomes: task, starter file, the deployed Grid/Graph, then a
# folded solution (graph after the fix, what changes, canonical code, walkthrough).


# The Airflow exercises are badly made (grid/run-naming forms are buggy, Run/Submit need a
# login), so none go into the Markdown. Animations are unaffected. Set True to bring back the
# repair-the-DAG conversion below.
INCLUDE_AIRFLOW_EXERCISES = False
# The dbt, Kafka, Spark and Python exercises (challenge_type "dbt" / "kafka"; their own forms such as
# compile_it or read_the_tape, not Airflow's) are left out the same way. There is no
# conversion code for them: to bring them back, one has to be written. Animations are kept.
SKIPPED_TOOL_EXERCISES = {"dbt", "kafka", "spark", "python", "sql"}


def challenge_path(c):
    sc = c["config"].get("scenario") or {}
    files = sc.get("files") or []
    return sc.get("file") or (files[0]["path"] if files else "dag.py")


# Only repair-the-DAG exercises (config.form "dag_repair", widget dr-widget) are converted.
# Every other Airflow exercise form is left out on purpose (see BLOCK-TYPES.md): grid_match
# (gm-root), the run-naming timeline widget, and any other. They are decided by form and
# widget, never by where their sentence lands, because the site sometimes draws a widget's
# sentence outside its frame. The widget is drawn by the browser: file, then the Grid/Graph of
# the DEPLOYED starter. A pane is only captured when it holds something: Grid needs cells,
# Graph needs nodes or an import error.
_AF_ANCHOR = """(root) => { let anchor = null;
    for (const b of document.querySelectorAll('[data-note-block]')) {
        const pos = b.compareDocumentPosition(root);
        if (!(pos & 4) || (pos & 16)) continue;   // keep blocks that come before root, not its parents
        const id = b.getAttribute('data-note-block');
        if (/^[si]\\|/.test(id)) anchor = id; }
    return anchor; }"""


def airflow_widgets(url, out_dir, slug, shoot):
    """Each Airflow widget in page order: {path, anchor, shots: {key: (caption, file)}}."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed; Airflow exercises go at the end", file=sys.stderr)
        return []
    img_dir = os.path.join(out_dir, "_images")
    os.makedirs(img_dir, exist_ok=True)
    widgets = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 1000},
                                color_scheme="light", device_scale_factor=2)
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        roots = page.locator('[data-testid="dr-widget"]')  # repair-the-DAG widgets only
        for i in range(roots.count()):
            root = roots.nth(i)
            root.scroll_into_view_if_needed()
            page.wait_for_timeout(500)
            header = root.locator('[data-testid="af-file-header"]').first.inner_text()
            m = re.search(r"dags/[\w./-]+\.py", header)
            shots = {}

            def snap(key, caption, loc):
                if not shoot:
                    return
                name = f"{slug}_ex{i + 1}_{key}.png"
                path = os.path.join(img_dir, name)
                loc.first.screenshot(path=path)
                with open(path, "rb") as fh:  # PNG header: width at bytes 16-20
                    pixels = int.from_bytes(fh.read(24)[16:20], "big")
                shots[key] = (caption, name, round(pixels / 2.5))  # shown 2.5x smaller than full size

            def click(text):
                root.get_by_text(re.compile(rf"^{text}$", re.I)).first.click()
                page.wait_for_timeout(600)

            grid = root.locator('[data-testid="dr-grid-page"]')
            graph = root.locator('[data-testid="dr-graph-page"]')
            click("Grid")
            if grid.locator('[data-testid="af-cell"]').count():
                snap("grid", "Grid, deployed (your starter code)", grid)
            click("Graph")
            if graph.locator('[data-testid="af-graph-node"], [data-testid="af-import-errors"]').count():
                snap("graph", "Graph, deployed (your starter code)", graph)
            widgets.append({"path": m.group(0) if m else None,
                            "anchor": root.evaluate(_AF_ANCHOR), "shots": shots})
        browser.close()
    return widgets


SHOT_ORDER = ["grid", "graph"]


GRAPH_STYLES = {"success": "fill:#0a3d12,stroke:#2ea043,color:#fff", "failed": "fill:#4d1010,stroke:#f85149,color:#fff",
                "upstream_failed": "fill:#4d2f08,stroke:#f0883e,color:#fff", "running": "fill:#0b3a4a,stroke:#39c5cf,color:#fff"}


def dag_edges(source):
    """Edges from the `>>` lines of a DAG file: [a, b] >> c, a >> [b, c], and chains of them.

    Variables are mapped to their task_id (o = BashOperator(task_id="pull_orders") makes `o`
    mean pull_orders), so the edges name tasks, not variables."""
    names = {v: t for v, t in re.findall(r'(\w+)\s*=\s*\w+Operator\(\s*task_id="(\w+)"', source)}
    edges = []
    for line in source.splitlines():
        if ">>" not in line or "=" in line or "(" in line:  # assignments and calls are not edge lines
            continue
        groups = [[names.get(t.strip(), t.strip()) for t in seg.strip().strip("[]").split(",") if t.strip()]
                  for seg in line.split(">>")]
        for left, right in zip(groups, groups[1:]):
            edges += [(a, b) for a in left for b in right]
    return edges


def taskflow_edges(source):
    """(edges, task names) for TaskFlow files: an edge wherever one task's result is passed
    to another, as in summarize(count_rows(find_file())) or x = a(); b(x)."""
    import ast
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], set()

    def is_task(d):
        d = d.func if isinstance(d, ast.Call) else d
        return (isinstance(d, ast.Name) and d.id == "task") or (isinstance(d, ast.Attribute) and d.value.__class__ is ast.Name and d.value.id == "task")
    tasks = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and any(is_task(d) for d in n.decorator_list)}
    results, edges = {}, []

    def produced(node):  # task names whose result this expression holds
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in tasks:
            for arg in list(node.args) + [k.value for k in node.keywords]:
                edges.extend((u, node.func.id) for u in produced(arg))
            return [node.func.id]
        if isinstance(node, ast.Name):
            return results.get(node.id, [])
        if isinstance(node, (ast.Tuple, ast.List)):
            return [t for e in node.elts for t in produced(e)]
        return []
    for st in sorted((n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.Expr))), key=lambda n: n.lineno):
        if isinstance(st, ast.Assign):
            tgt, val = st.targets[0], st.value
            if isinstance(tgt, ast.Tuple) and isinstance(val, ast.Tuple) and len(tgt.elts) == len(val.elts):
                for t, v in zip(tgt.elts, val.elts):
                    if isinstance(t, ast.Name):
                        results[t.id] = produced(v)
            elif isinstance(tgt, ast.Name):
                results[tgt.id] = produced(val)
        else:
            produced(st.value)
    return list(dict.fromkeys(edges)), tasks


def solution_graphs(c):
    """One Mermaid graph per expected run (task boxes coloured by state), or None if the
    solution has no `>>` lines to draw (e.g. TaskFlow calls) or no expected states."""
    runs = ((c["config"].get("scenario") or {}).get("expect") or {}).get("runs") or []
    source = ((c.get("deep_dive") or {}).get("reference") or {}).get("source") or ""
    flow_edges, flow_tasks = taskflow_edges(source)
    edges = dag_edges(source) + flow_edges
    if not runs or not edges:
        return None
    # operator class shown under each task name: from the solution code (BashOperator(task_id="x")),
    # else from the parsed starter file's task list
    operators = {t: op for op, t in re.findall(r'(\w+Operator)\(\s*task_id="(\w+)"', source)}
    operators.update({t: "_PythonDecoratedOperator" for t in flow_tasks})  # @task functions
    for f in (c["config"].get("scenario") or {}).get("files") or []:
        for dag in (f.get("description") or {}).get("dags") or []:
            for task in dag.get("tasks") or []:
                operators.setdefault(task["taskId"], task.get("operator"))
    out = []
    for i, run in enumerate(runs, 1):
        lines = ["```mermaid", "flowchart TB"]
        for t, state in run["tasks"].items():
            op = f"<br/>{operators[t]}" if operators.get(t) else ""
            lines.append(f'    {t}["{t}{op}<br/>{state}"]:::{state}')
        lines += [f"    {a} --> {b}" for a, b in edges]
        lines += [f"    classDef {s} {css}" for s, css in GRAPH_STYLES.items()]
        lines.append("```")
        out.append((f"*Run {i} of {len(runs)}*\n\n" if len(runs) > 1 else "") + "\n".join(lines))
    return "\n\n".join(out)


def airflow_exercise_markdown(c, n, total, shots):
    cfg, sc = c["config"], c["config"].get("scenario") or {}
    out = [f"### Exercise {n} of {total}: Repair the DAG", f"**● TASK**\n\n{c['prompt']}"]
    files = sc.get("files") or []
    starter = (cfg.get("starter") or {}).get("source") or (files[0]["source"] if files else "")
    out.append(f"**Starter** — `{challenge_path(c)}`\n\n```python\n{starter}\n```")
    if shots:  # panes the page really shows, as the page draws them
        out += [f'**{shots[k][0]}**\n\n<img src="_images/{shots[k][1]}" alt="{shots[k][0]}" width="{shots[k][2]}">'
                for k in SHOT_ORDER if k in shots]
    out.append("<details>\n<summary><strong>Solution</strong></summary>")
    # The site only draws the graph after a correct fix once the code is Run, and Run needs a
    # login, so it is drawn here from the solution's `>>` lines and the expected task states.
    graphs = solution_graphs(c)
    if graphs:
        out.append("**Graph after the fix** (drawn from the solution code and the expected task states)\n\n" + graphs)
    # what the fix changes, so a small edit is easy to spot
    fixed = ((c.get("deep_dive") or {}).get("reference") or {}).get("source") or ""
    changes = [l for l in difflib.unified_diff(starter.splitlines(), fixed.splitlines(), lineterm="", n=1)
               if not l.startswith(("---", "+++", "@@"))]
    if changes:
        out.append("**What changes** (`-` starter, `+` solution)\n\n```diff\n" + "\n".join(changes) + "\n```")
    out += [m for m in (solution_block(b) for b in (c.get("deep_dive") or {}).get("blocks") or []) if m]
    out.append("</details>")
    return "\n\n".join(out)


def airflow_sections(url, out_dir, slug, challenges):
    """[(anchor block id or None, markdown)]: each exercise where the page puts it."""
    widgets = airflow_widgets(url, out_dir, slug, "--screenshots" in sys.argv)
    by_path = {challenge_path(c): c for c in challenges}
    ordered = [(w, by_path.get(w["path"])) for w in widgets]
    if len(ordered) != len(challenges) or any(c is None for _, c in ordered):
        print("warning: Airflow widgets do not match the data; exercises go at the end", file=sys.stderr)
        return [(None, "\n\n".join(airflow_exercise_markdown(c, n, len(challenges), {})
                                   for n, c in enumerate(challenges, 1)))]
    sections = []
    for n, (w, c) in enumerate(ordered, 1):
        md = airflow_exercise_markdown(c, n, len(ordered), w["shots"])
        if sections and sections[-1][0] == w["anchor"]:  # same spot: keep them in order
            sections[-1] = (w["anchor"], sections[-1][1] + "\n\n" + md)
        else:
            sections.append((w["anchor"], md))
    return sections


# Taking a solution's schema diagram: it sits in a scrolling box inside a widget (one
# page can hold several widgets, some with tabs). The diagram is found by its content, the
# smallest element holding every table and column name, and Playwright scrolls to it.
_FIND = """([el, names]) => { let n = el; while (n && n.parentElement) { n = n.parentElement;
    const t = n.innerText || ''; if (names.every(x => t.includes(x)) && n.getBoundingClientRect().width > 300) return n; }
    return null; }"""
_CLIPPED = """(el) => { const r = el.getBoundingClientRect(); let n = el.parentElement;
    while (n && n !== document.body) { const s = getComputedStyle(n);
        if (/(auto|scroll|hidden)/.test(s.overflowY)) { const p = n.getBoundingClientRect();
            if (r.top < p.top - 1 || r.bottom > p.bottom + 1) return true; } n = n.parentElement; }
    return false; }"""
_UNCLIP = """(el) => { let n = el.parentElement; while (n && n !== document.body) {
    if (/(auto|scroll|hidden)/.test(getComputedStyle(n).overflowY)) {
        n.style.overflow = 'visible'; n.style.maxHeight = 'none'; n.style.height = 'auto'; } n = n.parentElement; } }"""
_HIDE_FIXED = """() => { for (const e of document.querySelectorAll('body *')) {
    const p = getComputedStyle(e).position, r = e.getBoundingClientRect();
    if ((p === 'fixed' || p === 'sticky') && r.top <= 5 && r.height < 140) e.style.visibility = 'hidden'; } }"""


def screenshot_schema_diagrams(url, out_dir, slug, challenges):
    """Save each exercise's solution schema diagram as <slug>_exercise_<n>_schema.png.

    Returns {exercise number: file name}; exercises without a schema diagram are skipped.
    """
    wanted = {}
    for n, c in enumerate(challenges, 1):
        for b in (c.get("deep_dive") or {}).get("blocks") or []:
            if b.get("blockType") == "schema_diagram":
                names = [t["name"] for t in b["tables"]]
                wanted[n] = names + [col["name"] for t in b["tables"] for col in t["columns"]], names[0]
    if not wanted:
        return {}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed", file=sys.stderr)
        return {}
    img_dir = os.path.join(out_dir, "_images")
    os.makedirs(img_dir, exist_ok=True)
    saved = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 1000},
                                color_scheme="dark", device_scale_factor=2)

        def open_page():
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            roots = page.locator("[data-challenge-ids]")
            return roots, [len((roots.nth(i).get_attribute("data-challenge-ids") or "").split())
                           for i in range(roots.count())]

        sizes = open_page()[1]
        if sum(sizes) != len(challenges):
            print("warning: widget exercise counts do not match the data; "
                  "schema diagrams not captured", file=sys.stderr)
            browser.close()
            return {}
        for n, (needles, first_name) in wanted.items():
            roots, _ = open_page()  # a fresh page each time keeps one exercise's state out of the next
            w, tab = 0, n - 1
            while tab >= sizes[w]:
                tab -= sizes[w]
                w += 1
            root = roots.nth(w)
            root.scroll_into_view_if_needed()
            if sizes[w] > 1:
                root.locator("button[role=tab]").nth(tab).click()
                page.wait_for_timeout(1500)
            solution = root.get_by_role("button", name="Solution").first
            solution.scroll_into_view_if_needed()
            solution.click()
            page.wait_for_timeout(600)
            gate = page.get_by_role("button", name="Show the solution")
            if gate.count():
                gate.first.click()
                page.wait_for_timeout(2500)
            best, best_area = None, None
            candidates = root.get_by_text(first_name, exact=True)
            for i in range(candidates.count()):  # the name also appears in prose: take the tightest container
                el = page.evaluate_handle(_FIND, [candidates.nth(i).element_handle(), needles]).as_element()
                if el:
                    box = el.bounding_box()
                    if best is None or box["width"] * box["height"] < best_area:
                        best, best_area = el, box["width"] * box["height"]
            if best is None:
                print(f"warning: schema diagram for exercise {n} not found on the page", file=sys.stderr)
                continue
            page.evaluate(_HIDE_FIXED)
            best.scroll_into_view_if_needed()
            page.wait_for_timeout(1000)
            if page.evaluate(_CLIPPED, best):  # taller than its scrolling box: lift the limit and retry
                page.evaluate(_UNCLIP, best)
                best.scroll_into_view_if_needed()
                page.wait_for_timeout(1000)
            name = f"{slug}_exercise_{n}_schema.png"
            best.screenshot(path=os.path.join(img_dir, name))
            saved[n] = name
        browser.close()
    return saved


# Animations (sql_animation, kafka_animation, pipeline_animation ...): a player that plays by
# itself once scrolled into view, with a step counter ("3/9") and sometimes mode toggles.
# Each mode is recorded with Playwright's video recorder (real speed; see record_animation) as an MP4 of the
# player alone (a GIF of these players was 5 to 10 MB), kept outside the repo in ANIM_DIR and
# uploaded as a GitHub user-attachments asset; GitHub shows a bare asset URL on its own line as a video
# player. tools/animation_urls.json maps each recording's name to its URL so a re-run reuses it.
ANIM_DIR = os.environ.get("ANIM_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".animations")
URLS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "animation_urls.json")
REPO = "Dulain-Willis/data-eng-knowledge"
ANIM_STATS = {}
_HIDE_PINNED = """() => { for (const e of document.querySelectorAll('body *')) {
    const p = getComputedStyle(e).position;
    if ((p === 'fixed' || p === 'sticky') && e.getBoundingClientRect().height < 140) e.style.visibility = 'hidden'; } }"""
_STEP = re.compile(r"(\d+)\s*/\s*(\d+)")
_PLAYER_BOX = """(block) => { const bs = [...block.querySelectorAll('button')]; if (!bs.length) return null;
    let a = bs[0]; while (a && !bs.every(b => a.contains(b))) a = a.parentElement;
    const r = a.getBoundingClientRect(); return {x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height}; }"""


def upload_animation(name, force=False):
    """Upload ANIM_DIR/<name> as a user-attachments asset (undocumented GitHub endpoint), remember its URL
    in tools/animation_urls.json and return it. Needs `gh auth login`. The token goes to curl through a
    mode-600 config file (never on the command line, where `ps` could show it) that is deleted afterwards."""
    import fcntl  # several converter runs may upload at once: serialize the read-modify-write of the URL file
    lock = open(URLS_FILE + ".lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        return _upload_animation(name, force)
    finally:
        lock.close()


def _upload_animation(name, force):
    urls = json.load(open(URLS_FILE)) if os.path.exists(URLS_FILE) else {}
    if force or name not in urls:  # force: upload a re-recorded file as a NEW asset
        tok = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
        rid = subprocess.run(["gh", "api", f"repos/{REPO}", "--jq", ".id"], capture_output=True, text=True,
                             check=True).stdout.strip()
        fd, cfg = tempfile.mkstemp(suffix=".curlrc")  # mkstemp creates the file with mode 600
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(f'header = "Authorization: Bearer {tok}"\n')
            res = subprocess.run(["curl", "-s", "-K", cfg, "-X", "POST",
                                  "-H", "Accept: application/json", "-H", "Content-Type: video/mp4",
                                  "--data-binary", "@" + os.path.join(ANIM_DIR, name),
                                  f"https://uploads.github.com/user-attachments/assets?name={name}"
                                  f"&content_type=video/mp4&repository_id={rid}"],
                                 capture_output=True, text=True, check=True).stdout
        finally:
            os.remove(cfg)
        urls[name] = json.loads(res)["url"]
        with open(URLS_FILE, "w") as fh:
            json.dump(dict(sorted(urls.items())), fh, indent=1)
            fh.write("\n")
    return urls[name]


def _media_stats(path):
    """(duration in seconds, distinct frames per second) of a video; distinct = frames mpdecimate keeps."""
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                               capture_output=True, text=True, check=True).stdout)
    out = subprocess.run(["ffmpeg", "-i", path, "-vf", "mpdecimate,showinfo", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return dur, out.count("pts_time") / dur


def _max_gap(path):
    """Longest stretch (s) in a video between two distinct frames (frames mpdecimate keeps): a frozen video."""
    out = subprocess.run(["ffmpeg", "-i", path, "-vf", "mpdecimate,showinfo", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    ts = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", out)]
    return max((b - a for a, b in zip(ts, ts[1:])), default=0.0)


def _start_corr(path):
    """Python player START CHECK by content: the code panel (top left of the crop) does not change while the
    player plays, so frame 0 must look like the frames 1.2 s and 2.4 s later (Pearson correlation of the top of
    the panel, about 0.95 for the same panel, about 0 when frame 0 shows page text or a shifted layout)."""
    W = 1600

    def region(t):
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(t), "-i", path, "-frames:v", "1",
                              "-vf", f"scale={W}:-2", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                             capture_output=True, stdin=subprocess.DEVNULL).stdout
        return [raw[y * W + x] for y in range(14, min(175, len(raw) // W), 2) for x in range(30, 620, 2)]

    def corr(a, b):
        n = len(a)
        if not n or n != len(b):
            return 0.0
        ma, mb = sum(a) / n, sum(b) / n
        sab = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        saa, sbb = sum((x - ma) ** 2 for x in a), sum((y - mb) ** 2 for y in b)
        return sab / ((saa * sbb) ** 0.5 or 1)

    first = region(0)
    return min(corr(first, region(t)) for t in (1.2, 2.4))


def _wait_idle(block, page, began, cap=150):
    """Finish detector for a player with no step counter: its markup has not changed for 4 seconds
    (the cap is generous). Returns the time of the last change, plus nothing else to trim."""
    last, changed = None, time.monotonic()
    while time.monotonic() - began < cap:
        sig = block.evaluate("b => b.innerHTML.length + ':' + b.querySelectorAll('*').length + ':' + "
                             "[...b.querySelectorAll('[style]')].map(e => e.getAttribute('style')).join('|').length")
        sig = hash(sig + block.inner_text())
        if sig != last:
            last, changed = sig, time.monotonic()
        elif time.monotonic() - changed >= 4:
            break
        page.wait_for_timeout(250)
    return changed + 1.5


# The START CHECK. A video must open on the first frame where the player is really on screen: its own
# title-bar dots (red, yellow, green) at the exact spot the DOM puts them inside the player box, and its
# step counter reading "1/N". Dots elsewhere in the frame (a code block of the article has the same
# three dots) do not count. Geometry comes from the DOM while recording (_GEOM_JS); every number in it
# is relative to the player box and scales with the box width, so it works at any video size.
_GEOM_JS = """(block) => {
  const bs = [...block.querySelectorAll('button')]; if (!bs.length) return null;
  let a = bs[0]; while (a && !bs.every(b => a.contains(b))) a = a.parentElement;
  const r = a.getBoundingClientRect();
  const want = {red: 'rgb(255, 95, 87)', yellow: 'rgb(255, 189, 46)', green: 'rgb(40, 201, 64)'};
  const dots = {};
  for (const e of a.querySelectorAll('span')) {
    const q = e.getBoundingClientRect(), c = getComputedStyle(e).backgroundColor;
    for (const k in want) if (c === want[k] && q.width >= 6 && q.width <= 32 && !dots[k])
      dots[k] = [q.x - r.x + q.width / 2, q.y - r.y + q.height / 2, q.width];
  }
  let counter = null;
  for (const e of a.querySelectorAll('*')) {
    if (e.children.length) continue;
    const t = e.textContent.trim();
    if (/^\\d+\\s*\\/\\s*\\d+$/.test(t)) {
      const n = e.firstChild, i = n.textContent.indexOf(t[0]), rg = document.createRange();
      rg.setStart(n, i); rg.setEnd(n, i + 1);
      const c = rg.getBoundingClientRect();
      const q = e.getBoundingClientRect();
      counter = {text: t, first: [c.x - r.x, c.y - r.y, c.width, c.height],
                 rect: [q.x - r.x, q.y - r.y, q.right - r.x, q.bottom - r.y]};
    }
  }
  return {x: r.x, y: r.y, w: r.width, h: r.height, dots, counter};
}"""
_DOT_RGB = {"red": (255, 95, 87), "yellow": (255, 189, 46), "green": (40, 201, 64)}
DOT_TOL = 90  # max colour distance of a title-bar dot (fade-in frames are a little dim)
_ONE_W, _ONE_H = 12, 18
# Template of the digit "1" in the step counter (mean of the counters of the first 75 reviewed videos),
# 0..1 luminance, rows top to bottom.
_ONE = [
    [.10,.10,.10,.11,.11,.10,.10,.10,.10,.10,.10,.10],
    [.10,.10,.10,.09,.08,.24,.41,.18,.09,.11,.10,.10],
    [.10,.10,.13,.30,.32,.57,.73,.21,.10,.11,.10,.11],
    [.09,.09,.19,.56,.62,.76,.77,.21,.10,.12,.10,.10],
    [.10,.10,.15,.33,.33,.58,.75,.21,.10,.11,.10,.09],
    [.10,.10,.10,.14,.11,.46,.78,.21,.08,.11,.11,.11],
    [.10,.10,.10,.11,.09,.43,.76,.21,.09,.11,.11,.11],
    [.10,.10,.10,.12,.10,.43,.75,.20,.10,.12,.10,.11],
    [.10,.10,.11,.12,.08,.42,.75,.20,.09,.12,.10,.11],
    [.11,.11,.14,.18,.14,.44,.76,.25,.15,.13,.10,.11],
    [.10,.10,.39,.65,.63,.77,.90,.67,.62,.33,.10,.09],
    [.10,.10,.36,.54,.54,.56,.58,.54,.54,.28,.09,.12],
    [.10,.11,.17,.20,.20,.18,.19,.19,.19,.15,.08,.21],
    [.10,.11,.11,.11,.10,.10,.10,.10,.10,.10,.10,.16],
    [.10,.10,.10,.10,.10,.10,.10,.10,.10,.10,.10,.11],
    [.10,.10,.10,.10,.10,.10,.10,.10,.10,.10,.10,.11],
    [.10,.10,.10,.10,.10,.10,.10,.10,.10,.10,.10,.10],
    [.10,.10,.10,.10,.10,.10,.10,.10,.10,.10,.10,.10],
]


def _video_size(path):
    w, h = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                           "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout.strip().split(",")
    return int(w), int(h)


def _read_frames(path, count, start=0.0, native=True):
    """First `count` frames of a video from `start` as rgb24 bytes (no frame dropping or duplication)."""
    w, h = _video_size(path)
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", path, "-frames:v", str(count),
                          "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    size = w * h * 3
    return [raw[i * size:(i + 1) * size] for i in range(len(raw) // size)], w, h


def _px(frame, w, x, y):
    i = (int(y) * w + int(x)) * 3
    return frame[i], frame[i + 1], frame[i + 2]


def dots_distance(frame, w, h, geom, ox=0.0, oy=0.0, scale=None):
    """Largest colour distance of the three title-bar dots from their expected colours when the player box
    has its top-left corner at (ox, oy) in the frame; 999 if a dot would fall outside the frame."""
    s = scale or (w / geom["w"])
    worst = 0
    for name, rgb in _DOT_RGB.items():
        d = geom["dots"].get(name)
        if not d:
            return 999
        cx, cy = ox + d[0] * s, oy + d[1] * s
        if cx < 2 or cy < 2 or cx >= w - 2 or cy >= h - 2:
            return 999
        pts = [_px(frame, w, cx + i, cy + j) for i in (-1, 0, 1) for j in (-1, 0, 1)]
        avg = [sum(p[c] for p in pts) / 9 for c in range(3)]
        worst = max(worst, max(abs(avg[c] - rgb[c]) for c in range(3)))
    return worst


def _counter_patch(frame, w, h, geom, ox=0.0, oy=0.0, scale=None):
    """Luminance patch (rows of floats, _ONE_H x _ONE_W) around the counter's first character, normalised
    to 0..1 by its own min and max; None when the counter has no readable spot in the frame."""
    c = geom.get("counter")
    if not c:
        return None
    s = scale or (w / geom["w"])
    fx, fy, fw, fh = c["first"]
    x0 = int(round(ox + (fx + fw / 2) * s - _ONE_W / 2))
    y0 = int(round(oy + (fy + fh / 2) * s - _ONE_H / 2))
    if x0 < 0 or y0 < 0 or x0 + _ONE_W > w or y0 + _ONE_H > h:
        return None
    rows = [[sum(_px(frame, w, x0 + i, y0 + j)) / 3 for i in range(_ONE_W)] for j in range(_ONE_H)]
    lo = min(min(r) for r in rows)
    hi = max(max(r) for r in rows)
    if hi - lo < 25:  # nothing drawn there (yet)
        return None
    return [[(v - lo) / (hi - lo) for v in r] for r in rows]


def _corr(a, b):
    xs = [v for r in a for v in r]
    ys = [v for r in b for v in r]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / ((sxx * syy) ** 0.5 or 1)


def counter_is_one(patch):
    """Does the patch show the digit "1"? Best correlation with the template of a "1" over small shifts
    (where the glyph sits inside the counter's box differs a few px between layouts)."""
    if patch is None or _ONE is None:
        return None
    best = -1
    for dy in range(-4, 5):
        for dx in (-2, -1, 0, 1, 2):
            shifted = [[patch[min(max(j + dy, 0), _ONE_H - 1)][min(max(i + dx, 0), _ONE_W - 1)]
                        for i in range(_ONE_W)] for j in range(_ONE_H)]
            best = max(best, _corr(shifted, _ONE))
    return best


def start_check(path, geom, ox=0.0, oy=0.0, scale=None, frames=None):
    """START CHECK of a finished video (or of `frames`, a (frames, w, h) tuple, for tests). Returns
    (ok, problems). The first frame must show the player's own dots at their exact spot and a step
    counter that reads "1"; the first 3 frames must keep showing the player (no page text coming
    back), and the counter must still read "1" in them."""
    fr, w, h = frames or _read_frames(path, 8)
    problems = []
    if len(fr) < 3:
        return False, ["video has fewer than 3 frames"]
    d0 = dots_distance(fr[0], w, h, geom, ox, oy, scale)
    if d0 > DOT_TOL:
        problems.append(f"first frame is not the player: its title-bar dots are missing at the expected spot (off by {d0:.0f})")
    for i in (1, 2):
        di = dots_distance(fr[i], w, h, geom, ox, oy, scale)
        if di > DOT_TOL:
            problems.append(f"frame {i} lost the player's dots (off by {di:.0f})")
    for i in range(3):
        p = _counter_patch(fr[i], w, h, geom, ox, oy, scale)
        c = counter_is_one(p)
        if p is None and i == 0 and d0 <= DOT_TOL:
            problems.append("first frame: no step counter drawn (placeholder or blank player)")
        elif c is not None and c < 0.7:
            problems.append(f"frame {i}: step counter does not read 1 (match {c:.2f}): the player is past step 1")
    return not problems, problems


def end_check(path, geom):
    """Bottom control bar present: the last frame has the step counter drawn where the DOM had it (counted
    from the bottom of the crop, since the player can grow while it plays). `geom["counter_bottom"]`
    is that distance, taken in the DOM at the end of the playback."""
    c, cb = geom.get("counter"), geom.get("counter_bottom")
    if not c or cb is None:
        return False, ["no counter geometry to check the control bar with"]
    w, h = _video_size(path)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                               capture_output=True, text=True, check=True).stdout)
    fr, _, _ = _read_frames(path, 20, start=max(0.0, dur - 0.5))
    s = w / geom["w"]
    l, t, r, b = c["rect"]
    x0, x1 = int(l * s), int(r * s)
    y1 = int(h - cb * s)
    y0 = int(y1 - (b - t) * s)
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h or not fr:
        return False, ["control bar region is outside the video (crop cut off the bottom of the player)"]
    vals = [sum(_px(fr[-1], w, x, y)) / 3 for y in range(y0, y1) for x in range(x0, x1)]
    if max(vals) - min(vals) < 25:
        return False, ["last frame: the step counter is not visible (bottom control bar cut off?)"]
    return True, []


def _player_start_frame(webm, geom, x, y, w, h, lo, span, fps=30):
    """Time (s) of the first frame in [lo, lo+span] of the raw recording where the player is on screen:
    cropped to the player box (x, y, w, h) and scaled like the final video, its three title-bar dots are in
    their colours at the exact spot the DOM gave and its step counter reads 1. Raises if there is none (the
    caller retries the recording; no guessing from the script clock)."""
    vf = f"fps={fps},crop={w}:{h}:{x}:{y},scale=1600:-2:flags=lanczos"
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{lo:.2f}", "-t", str(span), "-i", webm,
                          "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    vw = 1600
    vh = int(round(h * 1600 / w / 2)) * 2
    size = vw * vh * 3
    for i in range(len(raw) // size):
        fr = raw[i * size:(i + 1) * size]
        if dots_distance(fr, vw, vh, geom) > DOT_TOL:
            continue
        c = counter_is_one(_counter_patch(fr, vw, vh, geom))
        if c is not None and c >= 0.7:  # the placeholder ("Preparing the animation") has the dots but no counter
            return lo + i / fps
    raise RuntimeError("the player's title-bar dots and a step counter reading 1 never showed at their expected spot in the recording")


def record_animation(browser, url, k, m, label, dest, box_css):
    """Record animation block k in mode m (label) to the MP4 `dest`; returns its stats, or None if the
    player's controls never mounted.

    Playwright's own video recorder captures the page at real speed (screenshots in a loop stall the page
    and gave slow, choppy video). The window is the player's height plus 40 px, so the player is never cut
    off; the video is 2x pixels (viewport and record size doubled, page zoom 2, so layout stays 1150 px
    wide but small text is drawn sharp). The crop is the player box; the trim runs from the moment
    the player is in view until the counter reaches its last step plus 2 seconds.
    """
    W = max(1150, int(box_css["w"]) + 48)
    H = int(-(-box_css["h"] // 1)) + 40
    with tempfile.TemporaryDirectory() as tmp:
        ctx = browser.new_context(viewport={"width": W * 2, "height": H * 2}, color_scheme="light",
                                  record_video_dir=tmp, record_video_size={"width": W * 2, "height": H * 2})
        page = ctx.new_page()
        t0 = time.monotonic()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        page.evaluate("document.documentElement.style.zoom = 2")
        page.wait_for_timeout(1000)
        block = page.locator(ANIMATION_SELECTOR).nth(k)
        # All setup happens while the player is still below the fold: the site starts playing the moment
        # the player scrolls into view, so that jump is the start of the recording (nothing of step 1 is lost).
        page.evaluate(_HIDE_PINNED)  # the pinned "Ask AI" button would sit on top of the player
        page.wait_for_timeout(300)
        gap = block.evaluate("b => b.getBoundingClientRect().top") - (page.evaluate("innerHeight") + 1500)
        page.evaluate("y => window.scrollBy({top: y, behavior: 'instant'})", gap)  # block top well below the viewport (the site loads a bit ahead of the fold)
        page.wait_for_timeout(1500)
        if m > 0:  # pick the mode while out of view; a switched mode starts paused (Airflow animations)
            block.locator("button[role=radio]").nth(m).click()
            page.wait_for_timeout(500)
        before = _STEP.findall(block.inner_text()) if block.locator("button").count() else []
        restart = bool(before) and int(before[-1][0]) > 1  # a player in the first screen at page load has played on already
        jump_mark = mark = time.monotonic()
        page.evaluate("y => window.scrollBy({top: y, behavior: 'instant'})",
                      block.evaluate("b => b.getBoundingClientRect().top") - 10)  # instant: the site may smooth-scroll
        block.locator("button").first.wait_for(state="attached", timeout=15000)
        # When does the step counter first show? A player that is mounted at once shows it within a moment;
        # one that shows "Preparing the animation" first shows it later, and step 1 starts only then.
        counter_t = None
        while time.monotonic() - jump_mark < 25:
            if _STEP.findall(block.inner_text()):
                counter_t = time.monotonic()
                break
            page.wait_for_timeout(50)
        if counter_t is None:
            raise RuntimeError("the step counter never appeared")
        preparing = counter_t - jump_mark > 0.4
        if m > 0:
            play = block.locator('button[aria-label="Play"]')
            if play.count():
                play.first.click()
        if restart:  # play it again from step 1; the recording starts at this click
            page.wait_for_timeout(700)
            block.locator('button[aria-label="Restart"]').first.click()
            mark = time.monotonic()
        elif preparing:
            mark = counter_t
        first_seen = last_seen = None
        geom = last_geom = None  # the player's own geometry (DOM, screen pixels), first taken at step 1..9
        h_max = 0
        began = mark
        while time.monotonic() - began < 170:
            steps = _STEP.findall(block.inner_text())
            now = time.monotonic()
            g = block.evaluate(_GEOM_JS)
            if g:
                h_max = max(h_max, g["h"])
                last_geom = g
                if (geom is None and len(g["dots"]) == 3 and g["counter"] and steps
                        and int(steps[-1][0]) < 10 and now - mark > 0.3):
                    geom = g
            if steps:
                first_seen = first_seen or now
                if int(steps[-1][0]) >= int(steps[-1][1]):
                    last_seen = last_seen or now
                    if now - last_seen >= 2:
                        break
            elif first_seen is None and now - began > 8:  # no counter at all: wait for the markup to settle
                last_seen = _wait_idle(block, page, began)
                first_seen = began
                break
            page.wait_for_timeout(100)
        ctx.close()
        if geom is None:
            raise RuntimeError("never saw the player's title-bar dots and step counter in the DOM")
        vids = [f for f in os.listdir(tmp) if f.endswith(".webm")]
        x, y, w = (int(round(geom[c])) for c in "xyw")
        h = int(round(max(h_max, geom["h"])))
        h -= h % 2
        if x < 0 or y < 0 or x + w > W * 2 or y + h > H * 2:
            return {"error": f"crop {x},{y},{w},{h} outside video {W * 2}x{H * 2}", "need_h": h / 2 + 60}
        # The video clock is offset from the script clock by a varying amount (up to seconds on heavy pages), so
        # find the start in the video itself: the first frame where the player is really on screen (its own
        # title-bar dots at the exact spot the DOM gave, and a step counter that reads 1). There is no fallback
        # to the script clock: no such frame means the recording is bad and is redone.
        mark_t = jump_mark - t0
        jump = _player_start_frame(os.path.join(tmp, vids[0]), geom, x, y, w, h, max(0.0, mark_t - 6), 20)
        start = jump + ((mark - jump_mark) if restart else 0)  # a restarted player starts at the click, not at the jump
        live = (last_seen - mark) if first_seen and last_seen else None
        end = start + live + 2 if live is not None else start + (time.monotonic() - mark)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
                        "-i", os.path.join(tmp, vids[0]),
                        "-vf", f"crop={w}:{h}:{x}:{y},fps=30,scale=1600:-2:flags=lanczos,format=yuv420p",
                        "-c:v", "libx264", "-crf", "20", "-movflags", "+faststart", dest], check=True)
    geom["h"] = h
    if last_geom and last_geom["counter"]:
        geom["counter_bottom"] = last_geom["h"] - last_geom["counter"]["rect"][3]
    box = {"x": x, "y": y, "w": w, "h": h}
    return {"live": live, "box": box, "crop": (x, y, w, h), "video": (W * 2, H * 2), "geom": geom}


# Per-type player rules. The Spark and dbt players (title-bar dots, "n / m" counter) use record_animation above.
# The Airflow, Kafka and pipeline players share another frame (.smv-frame: header and body, the control bar
# (.smv-bar) at its bottom) and have no dots and no usable "n / m" counter (Airflow shows a clock, Kafka
# "t = 1.3 s"), and the common ancestor of their buttons is only the 42 px control bar. For these:
#   box    the .smv-frame that holds the buttons (full player, bar included);
#   start  the first video frame where the frame's static control-bar buttons (Restart, speed) are drawn
#          like in the finished recording, i.e. the player is on screen; the site starts it on mount;
#   end    the control bar's play button turns into "Replay" (the playback is over); the tail is 2 s after.
BAR_PLAYER_TYPES = {"airflow_animation", "kafka_animation", "pipeline_animation", "python_animation"}
_BAR_BOX = """(block) => { const b = block.querySelector('button'); const f = b && b.closest('.smv-frame, .pmv');
    if (!f) return null; const r = f.getBoundingClientRect();
    return {x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height}; }"""
_BAR_GEOM_JS = """(block) => {
  const bs = [...block.querySelectorAll('button')]; const b0 = bs[0]; const f = b0 && b0.closest('.smv-frame, .pmv');
  if (!f) return null;
  const r = f.getBoundingClientRect();
  const rel = e => { if (!e) return null; const q = e.getBoundingClientRect(); return [q.x - r.x, q.y - r.y, q.width, q.height]; };
  const restart = block.querySelector('button[aria-label="Restart"]');
  const speed = bs.find(b => /^Playback speed/.test(b.getAttribute('aria-label') || ''));
  const bar = f.querySelector('.smv-bar');
  if (!restart || !speed || !bar) return null;
  return {x: r.x, y: r.y, w: r.width, h: r.height, restart: rel(restart), speed: rel(speed), bar: rel(bar),
          code: rel(f.querySelector('.pmv-code')),
          replay: !!block.querySelector('button[aria-label="Replay"]'), text: bar.innerText.replace(/\\s+/g, ' ')};
}"""
_HIDE_AFTER_PLAYER = """(block) => { const b = block.querySelector('button'); const f = b && b.closest('.smv-frame, .pmv');
  const hide = e => { e.style.visibility = 'hidden'; };
  if (f) for (let s = f.nextElementSibling; s; s = s.nextElementSibling) hide(s);   // the caption under the frame
  else block.querySelectorAll(':scope > p').forEach(hide);                          // not mounted yet
  for (let n = block; n && n !== document.body; n = n.parentElement)
    for (let s = n.nextElementSibling; s; s = s.nextElementSibling) hide(s); }"""
_PY_BAR_TOL = 20  # the Python player's controls start dimmer (fade-in) than in the last frame: a little more room
_BAR_TOL = 14  # mean colour difference (0..255) of a control-bar button between a frame and the finished recording


def _bar_region_diff(fr, ref, w, h, geom, ox=0.0, oy=0.0, scale=None, ref_geom=None):
    """Worst mean absolute colour difference, over the Restart and speed buttons, between frame `fr` (buttons
    where `geom` puts them) and `ref` (buttons where `ref_geom` puts them; default `geom`), both w x h rgb24,
    the player box with its top-left at (ox, oy). The two differ for a player that grows while it plays: its
    control bar sits lower at the end. 999 if a button is outside."""
    s = scale or (w / geom["w"])
    rg = ref_geom or geom
    worst = 0
    for key in ("restart", "speed"):
        bx, by, bw, bh = geom[key]
        rx, ry, _, _ = rg[key]
        x0, y0 = int(round(ox + bx * s)), int(round(oy + by * s))
        x1, y1 = int(round(x0 + bw * s)), int(round(y0 + bh * s))
        rx0, ry0 = int(round(ox + rx * s)), int(round(oy + ry * s))
        if x0 < 0 or y0 < 0 or x1 > w or y1 > h or rx0 < 0 or ry0 < 0 or rx0 + (x1 - x0) > w or ry0 + (y1 - y0) > h:
            return 999
        tot = 0
        for y in range(y1 - y0):
            a, b = ((y0 + y) * w + x0) * 3, ((y0 + y) * w + x1) * 3
            c = ((ry0 + y) * w + rx0) * 3
            tot += sum(abs(p - q) for p, q in zip(fr[a:b], ref[c:c + (b - a)]))
        worst = max(worst, tot / ((x1 - x0) * (y1 - y0) * 3))
    return worst


def _panel_corr(fr, ref, w, h):
    """Pearson correlation of the top of the code panel (top left of the crop, 1600 px wide frames, rgb24)
    between a frame and the reference frame: about 0.95 for the same panel, about 0 for anything else (page text)."""
    ys = range(14, min(175, h), 2)
    xs = range(30, 620, 2)
    a = [sum(fr[(y * w + x) * 3:(y * w + x) * 3 + 3]) for y in ys for x in xs]
    b = [sum(ref[(y * w + x) * 3:(y * w + x) * 3 + 3]) for y in ys for x in xs]
    n = len(a)
    if not n:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    sab = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    saa, sbb = sum((x - ma) ** 2 for x in a), sum((y - mb) ** 2 for y in b)
    return sab / ((saa * sbb) ** 0.5 or 1)


def _code_diff(fr, ref, w, h, geom):
    """Python player only (geom has the code panel): mean colour difference between frame `fr` and `ref` over the
    top of the code panel, which does not change while it plays (the page text, which can sit there in a frame
    from before the player is on screen, differs a lot). 0 for other players."""
    c = geom.get("code")
    if not c:
        return 0
    s = w / geom["w"]
    x0, y0 = int(c[0] * s), int(c[1] * s)
    x1, y1 = min(w, int((c[0] + c[2]) * s)), min(h, int((c[1] + min(c[3], 120)) * s))
    if x1 <= x0 or y1 <= y0:
        return 999
    tot = n = 0
    for y in range(y0, y1, 3):
        a, b = (y * w + x0) * 3, (y * w + x1) * 3
        tot += sum(abs(p - q) for p, q in zip(fr[a:b:7], ref[a:b:7]))
        n += len(fr[a:b:7])
    return tot / max(n, 1)


_CODE_TOL = 12


def _bar_has_buttons(ref, w, h, geom):
    """The reference frame really shows the buttons (they have some contrast), so matching them means something."""
    s = w / geom["w"]
    bx, by, bw, bh = geom["restart"]
    x0, y0, x1, y1 = (int(round(v)) for v in (bx * s, by * s, (bx + bw) * s, (by + bh) * s))
    vals = [sum(_px(ref, w, x, y)) / 3 for y in range(y0, y1) for x in range(x0, x1)]
    return bool(vals) and max(vals) - min(vals) >= 25


def _body_blank(fr, w, h, geom):
    """True if the player body (everything above the control bar) is one flat colour."""
    s = w / geom["w"]
    y1 = int(geom["bar"][1] * s)
    vals = [sum(_px(fr, w, x, y)) / 3 for y in range(0, max(y1, 1), 6) for x in range(0, w, 6)]
    return max(vals) - min(vals) < 25


def _bar_start_frame(webm, geom, x, y, w, h, lo, span, fps=30):
    """Time (s) of the first frame in [lo, lo+span] of the raw recording where the player is on screen:
    cropped like the final video, its Restart and speed buttons look like the same buttons in the last frame
    of the recording, and the next two frames still do. Raises if there is none."""
    vf = f"crop={w}:{h}:{x}:{y},scale=1600:-2:flags=lanczos"
    vw, vh = 1600, int(round(h * 1600 / w / 2)) * 2
    size = vw * vh * 3
    g0 = dict(geom, **geom.get("start", {}))  # where the buttons were when the player mounted
    ref = subprocess.run(["ffmpeg", "-loglevel", "error", "-sseof", "-0.5", "-i", webm, "-vf", vf + ",fps=30",
                          "-frames:v", "15", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True).stdout[-size:]
    if len(ref) != size or not _bar_has_buttons(ref, vw, vh, geom):
        raise RuntimeError("the last frame of the recording does not show the control bar")
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{lo:.2f}", "-t", str(span), "-i", webm,
                          "-vf", f"fps={fps}," + vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    frs = [raw[i * size:(i + 1) * size] for i in range(len(raw) // size)]
    for i in range(len(frs) - 2):
        if all(_bar_region_diff(frs[i + j], ref, vw, vh, g0, ref_geom=geom) <= geom.get("tol", _BAR_TOL)
               and (not geom.get("code") or _panel_corr(frs[i + j], ref, vw, vh) >= 0.8) for j in range(3)):
            return lo + i / fps
    raise RuntimeError("the player's control bar never showed at its expected spot in the recording")


def bar_start_check(path, geom):
    """START CHECK for a bar player: the first 3 frames already show the control bar buttons (the video does not
    open on page text or a half-mounted player) and the body is not blank."""
    fr, w, h = _read_frames(path, 8)
    if len(fr) < 3:
        return False, ["video has fewer than 3 frames"]
    ref = _read_frames(path, 1, start=max(0.0, _duration(path) - 0.5))[0]
    if not ref or not _bar_has_buttons(ref[0], w, h, geom):
        return False, ["last frame: no control bar"]
    problems = []
    g0 = dict(geom, **geom.get("start", {}))  # the control bar at the start (a growing player has it higher up)
    for i in range(3):
        d = _bar_region_diff(fr[i], ref[-1], w, h, g0, ref_geom=geom)
        if d > geom.get("tol", _BAR_TOL):
            problems.append(f"frame {i} does not show the control bar (difference {d:.0f})")
        cd = _code_diff(fr[i], ref[-1], w, h, geom)
        if cd > _CODE_TOL:
            problems.append(f"frame {i} does not show the player's code panel (difference {cd:.0f})")
    step = 7  # sampling stride in pixels: a page-text first frame turning into the player is a big jump, normal motion is not
    jump = sum(abs(a - b) for a, b in zip(fr[0][::step * 3 + 1], fr[2][::step * 3 + 1])) / len(fr[0][::step * 3 + 1])
    if jump > 5:
        problems.append(f"frame 0 is not the player (jump of {jump:.0f} to frame 2)")
    if _body_blank(fr[2], w, h, g0):
        problems.append("the player body is blank in the first frames")
    elif len(fr) >= 8:  # a half-drawn body (the player still mounting) shows much less than frame 7 does
        s = w / geom["w"]
        y1 = int(g0["bar"][1] * s)
        ink = lambda f: sum(1 for y in range(int(y1 * .12), y1, 3) for x in range(0, w, 3) if sum(_px(f, w, x, y)) / 3 > 70)
        ref_ink = ink(fr[7])
        for i in range(3):
            if ref_ink and ink(fr[i]) < 0.8 * ref_ink:
                problems.append(f"frame {i}: the player body is still half drawn")
    return not problems, problems


def bar_end_check(path, geom):
    """END CHECK for a bar player: the DOM showed "Replay" (playback finished), and the last frame shows the
    control bar and a body that is not blank."""
    w, h = _video_size(path)
    fr, _, _ = _read_frames(path, 20, start=max(0.0, _duration(path) - 0.5))
    if not fr:
        return False, ["no frames at the end"]
    problems = []
    if not geom.get("ended"):
        problems.append("the playback never reached Replay")
    if _bar_region_diff(fr[-1], fr[0], w, h, geom) > geom.get("tol", _BAR_TOL):
        problems.append("last frame: control bar changes at the end (cut off?)")
    if _body_blank(fr[-1], w, h, geom):
        problems.append("last frame: the player body is blank")
    return not problems, problems


def _duration(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                capture_output=True, text=True, check=True).stdout)


def _opening_frame_problems(path):
    """The opening-frames check of checks/animation_first_frames.py (no page text under the player, step
    counter reading 1/N), applied to a fresh recording so a bad one is retried."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "animation_first_frames", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                               "checks", "animation_first_frames.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return sorted(set(x.split(": ", 1)[1] for x in mod.problems(path)))


def record_bar_animation(browser, url, k, m, label, dest, box_css):
    """record_animation for the BAR_PLAYER_TYPES (same recorder settings: Playwright video, window = player
    height + 40, 2x via doubled viewport/record size and page zoom 2, crop + fps=30 + scale 1600 lanczos +
    libx264 crf 20, 2 s tail); only the box, the start and the end are found by the rules above."""
    W = max(1150, int(box_css["w"]) + 48)
    H = int(-(-box_css["h"] // 1)) + 40
    with tempfile.TemporaryDirectory() as tmp:
        ctx = browser.new_context(viewport={"width": W * 2, "height": H * 2}, color_scheme="light",
                                  record_video_dir=tmp, record_video_size={"width": W * 2, "height": H * 2})
        page = ctx.new_page()
        t0 = time.monotonic()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        page.evaluate("document.documentElement.style.zoom = 2")
        page.wait_for_timeout(1000)
        block = page.locator(ANIMATION_SELECTOR).nth(k)
        page.evaluate(_HIDE_PINNED)
        if block.get_attribute("data-note-block-type") == "python_animation":
            page.evaluate(_HIDE_AFTER_PLAYER, block.element_handle())  # before the jump, so no frame shows the page text
        page.wait_for_timeout(300)
        gap = block.evaluate("b => b.getBoundingClientRect().top") - (page.evaluate("innerHeight") + 1500)
        page.evaluate("y => window.scrollBy({top: y, behavior: 'instant'})", gap)
        page.wait_for_timeout(1500)
        if m > 0:  # pick the mode while out of view; a switched mode starts paused
            block.locator("button[role=radio]").nth(m).click()
            page.wait_for_timeout(500)
        jump_mark = time.monotonic()
        page.evaluate("y => window.scrollBy({top: y, behavior: 'instant'})",
                      block.evaluate("b => b.getBoundingClientRect().top") - 10)
        btype = block.get_attribute("data-note-block-type")
        if btype == "python_animation":
            # The crop is the player's finished height, but the Python player grows while it plays, so at the start
            # the page text that follows it would show below its control bar. Hide everything after the player (the
            # layout stays, only the paint goes), so the strip under the player is empty at any moment.
            page.evaluate(_HIDE_AFTER_PLAYER, block.element_handle())  # again: the player is mounted now
        geom = None
        while time.monotonic() - jump_mark < 25:  # the player is mounted once its control bar is
            geom = block.evaluate(_BAR_GEOM_JS)
            if geom:
                break
            page.wait_for_timeout(50)
        if not geom:
            raise RuntimeError("the control bar never appeared")
        start_geom = geom
        mount_t = mark = time.monotonic()
        play = block.locator('button[aria-label="Play"]')
        if btype == "python_animation" and m == 0:
            # The Python player plays by itself from its mount, and the video can show its first painted frame several
            # steps in (5/60, 3/107). Restart it and pause it at step 1, like a switched mode, so the recorded
            # playback starts at a click of ours and the first frame reads 1/N.
            block.locator('button[aria-label="Restart"]').first.click()
            page.wait_for_timeout(300)
            pause = block.locator('button[aria-label="Pause"]')
            if pause.count():
                pause.first.click()
            for _ in range(6):  # the pause can land after step 2 has begun: step back to 1
                page.wait_for_timeout(300)
                cur = block.evaluate(_BAR_GEOM_JS)
                if not cur or cur["text"].startswith("1/"):
                    break
                block.locator('button[aria-label="Previous step"]').first.click()
            else:
                raise RuntimeError("could not hold the player at step 1")
            page.wait_for_timeout(2000)
        if (m > 0 or (btype == "python_animation" and m == 0)) and play.count():  # a switched mode starts paused: the playback starts at this click
            play.first.click()
            mark = time.monotonic()
        last_geom, h_max, last_seen = geom, geom["h"], None
        while time.monotonic() - mark < 400:  # the longest Python players run about 3 minutes
            g = block.evaluate(_BAR_GEOM_JS)
            if g:
                last_geom, h_max = g, max(h_max, g["h"])
                if g["replay"] and time.monotonic() - mark > 1:
                    last_seen = time.monotonic()
                    break
            page.wait_for_timeout(100)
        if last_seen is None:
            raise RuntimeError("the playback never reached Replay")
        # Park the pointer outside the player (no hover tooltip over the caption) and nudge the page so the
        # compositor paints the final state: without this the headless video can keep showing the last
        # frame before the Pause -> Replay swap (seen on the 16-step pipeline player).
        page.mouse.move(2, 2)
        page.wait_for_timeout(300)
        page.mouse.move(6, 4)
        page.screenshot(clip={"x": 0, "y": 0, "width": 8, "height": 8})  # forces a fresh paint into the video
        page.wait_for_timeout(1700)
        g = block.evaluate(_BAR_GEOM_JS)
        if g:
            last_geom, h_max = g, max(h_max, g["h"])
        ctx.close()
        geom = dict(last_geom, h=h_max, ended=True)
        geom["start"] = {k: start_geom[k] for k in ("restart", "speed", "bar")}  # layout at mount (the player may grow)
        if btype == "python_animation":
            geom["tol"] = _PY_BAR_TOL
        vids = [f for f in os.listdir(tmp) if f.endswith(".webm")]
        x, y, w = (int(round(geom[c])) for c in "xyw")
        h = int(round(h_max))
        h -= h % 2
        if x < 0 or y < 0 or x + w > W * 2 or y + h > H * 2:
            return {"error": f"crop {x},{y},{w},{h} outside video {W * 2}x{H * 2}", "need_h": h / 2 + 60}
        webm = os.path.join(tmp, vids[0])
        pres = _bar_start_frame(webm, geom, x, y, w, h, max(0.0, (jump_mark - t0) - 1), 20)  # not before the jump: another player in view (a taller window) can look the same
        start = pres + (mark - mount_t) + float(os.environ.get("ANIM_START_NUDGE", 0))
        if btype == "python_animation" and m == 0:
            # the video clock lags the script clock by up to about a second: start well inside the 2 s paused stretch
            # at step 1 (before our Play click), not at the click, or the first frame can already be at step 2
            start = max(pres, start - 1.0)  # a stubborn player: start a frame or two later
        live = last_seen - mark
        end = start + live + 2
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", webm,
                        "-vf", f"crop={w}:{h}:{x}:{y},fps=30,scale=1600:-2:flags=lanczos,format=yuv420p",
                        "-c:v", "libx264", "-crf", "20", "-movflags", "+faststart", dest], check=True)
    geom["h"] = h
    return {"live": live, "box": {"x": x, "y": y, "w": w, "h": h}, "crop": (x, y, w, h), "video": (W * 2, H * 2), "geom": geom}


# A "static animation": an *_animation block whose player never gets controls (no steps). The site draws it
# as a plain picture and its footer reads "These tables are what the query/program reads." That is
# deliberate, so it is saved as a 2x PNG; no footer means the player probably failed to load.
STATIC_ANIMATION_FOOTER_RE = re.compile(r"These tables are what the .{1,40}? reads", re.I)


def is_static_animation(block_text):
    """True if the block's text carries the footer the site shows for a deliberate still animation."""
    return bool(STATIC_ANIMATION_FOOTER_RE.search(block_text or ""))


def record_animations(url, out_dir, slug, info, only=None):
    """Save every animation block's playback as an MP4 in ANIM_DIR: one per mode (toggle) if it has any.

    Returns {block number: [(mode label or None, file name)]}; ANIM_STATS holds per-file
    numbers. Each recording is checked (duration against the live playback time, at least 10 distinct
    frames per second) and redone up to 3 times if it fails, one at a time.
    """
    if not info:
        return {}
    if not shutil.which("ffmpeg"):
        print("warning: ffmpeg not found; animations not captured", file=sys.stderr)
        return {}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed", file=sys.stderr)
        return {}
    img_dir = os.path.join(out_dir, "_images")
    os.makedirs(img_dir, exist_ok=True)
    saved = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for k, entry in enumerate(info):
            if only is not None and k not in only:
                continue
            # Measure the player once in a throwaway window (no video, tall viewport): its size sets the
            # recording window, which must be taller than the player or the crop lands on the wrong region.
            ctx = browser.new_context(viewport={"width": 1150, "height": 1600}, color_scheme="light")
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
            block = page.locator(ANIMATION_SELECTOR).nth(k)
            block.scroll_into_view_if_needed()  # the first mode plays by itself once in view
            try:  # Spark animations mount their controls only once in view
                block.locator("button").first.wait_for(state="attached", timeout=10000)
            except Exception:
                pass
            bar = block.get_attribute("data-note-block-type") in BAR_PLAYER_TYPES
            slow = block.get_attribute("data-note-block-type") == "python_animation"
            box = block.evaluate(_BAR_BOX if bar else _PLAYER_BOX)
            if not box:
                # Static animation (see is_static_animation): after scroll + wait the site still shows no
                # player buttons, only the code and seed tables. Keep that as a still image.
                page.wait_for_timeout(5000)
                box = block.evaluate(_BAR_BOX if bar else _PLAYER_BOX)
            if not box:
                name = f"{slug}_animation_{k + 1}.png"
                page.evaluate(_HIDE_FIXED)  # the pinned "Ask AI" button would sit on top of the still
                bb = block.bounding_box()
                shot = ctx.new_cdp_session(page).send("Page.captureScreenshot", {
                    "format": "png", "captureBeyondViewport": True, "clip": {
                        "x": bb["x"], "y": bb["y"] + page.evaluate("scrollY"),
                        "width": bb["width"], "height": bb["height"], "scale": 2}})
                with open(os.path.join(img_dir, name), "wb") as fh:
                    fh.write(base64.b64decode(shot["data"]))
                static = is_static_animation(block.inner_text())
                ctx.close()
                if static:
                    print(f"static animation: {slug} animation {k + 1} has no player (no steps); saved a still image {name}")
                else:
                    print(f"WARNING: {slug} animation {k + 1} has no player controls and no 'These tables are what ... reads' "
                          f"footer: likely a recording failure, not a static animation; saved a still image {name} anyway",
                          file=sys.stderr)
                saved.setdefault(k, []).append((None, name))
                continue
            # the player can grow while it plays (captions, tables): take the largest size seen so far
            box_css = {"w": box["w"], "h": box["h"]}
            ctx.close()
            used = set()
            for m, label in enumerate(entry["labels"] or [None]):
                name = f"{slug}_animation_{k + 1}" + (f"_{re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')}"
                                                      if label else "") + ".mp4"
                while name in used:  # two modes whose labels slug alike (score >= 70 / score > 70): keep both files
                    name = name[:-4] + "-2.mp4"
                used.add(name)
                dest = os.path.join(ANIM_DIR, name)
                mode_box = dict(box_css)  # per mode: a retry's growth must not leak into the other modes
                for attempt in range(3):
                    try:
                        st = (record_bar_animation if bar else record_animation)(browser, url, k, m, label, dest, mode_box)
                    except Exception as e:  # a navigation timeout: wait and retry this one
                        print(f"  {name}: attempt {attempt + 1} failed ({type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}); retrying", file=sys.stderr)
                        time.sleep(10)
                        continue
                    if "error" in st:
                        mode_box["h"] = max(mode_box["h"], st["need_h"])
                        continue
                    dur, fps = _media_stats(dest)
                    vw, vh = _video_size(dest)
                    st.update(name=name, dur=dur, fps=fps)
                    start_ok, start_problems = (bar_start_check if bar else start_check)(dest, st["geom"])
                    end_ok, end_problems = (bar_end_check if bar else end_check)(dest, st["geom"])
                    problems = start_problems + end_problems
                    if slow:
                        # The Python player's long slow stretches change little per frame (a progress bar, one cell per
                        # step), so 10 distinct frames/s is too strict: demand motion at least 3 times a second on
                        # average and no frozen stretch longer than 2 s (a stalled recording).
                        problems += _opening_frame_problems(dest)
                        sc = _start_corr(dest)
                        if sc < 0.8:
                            problems.append(f"frame 0 is not the player's code panel (match {sc:.2f}): page text or a shifted layout")
                        gap = _max_gap(dest)
                        if fps < 3 or gap > 2.0:
                            problems.append(f"{fps:.1f} distinct frames/s, longest frozen stretch {gap:.1f} s")
                    elif fps < 10:
                        problems.append(f"only {fps:.1f} distinct frames/s")
                    # A bar player's video can end up to 1 s early (the video clock lags on a loaded machine; the
                    # finished state is still on screen and the END CHECK covers it): keep at least a 1 s tail.
                    lo = 1.0 if bar else 1.7
                    if st["live"] is not None and not (st["live"] + lo <= dur <= st["live"] + 2.3):
                        problems.append(f"duration {dur:.1f} s vs live {st['live']:.1f} s + 2 s")
                    if vw != 1600 or vh % 2:
                        problems.append(f"size {vw}x{vh}")
                    st["problems"] = problems
                    if not problems:
                        ANIM_STATS[name] = st
                        break
                    print(f"  {name}: attempt {attempt + 1} failed checks: {'; '.join(problems)}", file=sys.stderr)
                    if bar and attempt >= 1:  # a window barely taller than the player can mis-place it: give it room (the crop stays the player)
                        mode_box["h"] += 160
                else:
                    raise RuntimeError(f"{name}: could not record a passing video")
                saved.setdefault(k, []).append((label, name))
        browser.close()
    return saved


# Run-output cells are screenshotted whole after clicking Run; a cell has finished when the text
# inside it stops changing. The site pins an "Ask AI" button to the viewport, which would sit on top
# of the shot, so fixed-position elements are hidden first.
_HIDE_FIXED = """() => { for (const e of document.querySelectorAll('body *'))
  if (getComputedStyle(e).position === 'fixed') e.style.visibility = 'hidden'; }"""
_CELL_ERROR = re.compile(r"Traceback|Error\b|Exception\b", re.I)


def _click_run(page, block, kind):
    """Press the cell's run control. Spark: the "Run" button, and the output is drawn by JavaScript, so
    wait until the cell text changes and then stays quiet for 1.5 s. Python: the ">>>" button reveals the
    output the page already holds; wait until the cell grows taller. SQL: the "Show result" icon button (see below). Returns (text before, text after)."""
    before = block.inner_text()
    if kind == "executable_spark":
        block.get_by_role("button", name="Run", exact=True).click()
        began = time.monotonic()
        last, stable_since = before, None
        while time.monotonic() - began < 90:  # changed, then quiet for 1.5 s
            page.wait_for_timeout(300)
            now = block.inner_text()
            if now != last:
                last, stable_since = now, time.monotonic()
            elif stable_since and time.monotonic() - stable_since >= 1.5:
                break
        return before, last
    h0 = block.bounding_box()["height"]
    # SQL: 3 icon-only buttons, "Animate this query", "Edit and run this query" and "Show result" (the
    # table icon, third); "Show result" reveals the result the page already holds.
    label = "Show result" if kind == "executable_sql" else ">>>"
    buttons = block.get_by_role("button", name=label, exact=True)
    if buttons.count() != 1:
        print(f"warning: cell has {buttons.count()} '{label}' buttons, expected 1", file=sys.stderr)
    buttons.first.click()
    began = time.monotonic()
    grew = False
    while time.monotonic() - began < 8:  # the output panel animates open
        page.wait_for_timeout(200)
        if block.bounding_box()["height"] > h0 + 5:
            grew = True
            break
    if not grew:
        print(f"warning: cell did not grow after '{label}' (output not revealed?)", file=sys.stderr)
    page.wait_for_timeout(1200)  # let the open animation finish
    return before, block.inner_text()


def record_cells(url, out_dir, slug, count, kind="executable_spark", start=0):
    """Click the run control of every runnable cell and save the whole cell as <slug>_cell_<n>.png.

    Returns the file names in page order (None for a cell that could not be captured). Warns
    about cells that show no output or an error. See _click_run for the control each kind uses.
    """
    if not count:
        return []
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed; run-output cells not captured", file=sys.stderr)
        return []
    img_dir = os.path.join(out_dir, "_images")
    os.makedirs(img_dir, exist_ok=True)
    names = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1000, "height": 900},
                                color_scheme="light", device_scale_factor=2)
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        blocks = page.locator(f'[data-note-block-type="{kind}"]')
        if blocks.count() != count:
            print(f"warning: page has {blocks.count()} runnable cells, the HTML has {count}", file=sys.stderr)
        for i in range(min(count, blocks.count())):
            block = blocks.nth(i)
            block.scroll_into_view_if_needed()
            page.wait_for_timeout(800)
            before, last = _click_run(page, block, kind)
            result = last[len(before):] if last.startswith(before) else last
            if kind == "executable_spark" and last == before:
                print(f"warning: cell {i + 1} showed no output after Run", file=sys.stderr)
            elif kind == "executable_spark" and _CELL_ERROR.search(result):
                print(f"warning: cell {i + 1} output looks like an error: {result.strip()[:120]!r}",
                      file=sys.stderr)
            page.evaluate(_HIDE_FIXED)
            name = f"{slug}_cell_{start + i + 1}.png"  # start: cells of earlier kinds on a mixed page
            block.screenshot(path=os.path.join(img_dir, name))
            names.append(name)
        names += [None] * (count - len(names))
        browser.close()
    return names


def record_regex_cards(url, out_dir, slug, count):
    """Save each regex_cards block (the stacked pattern cards) as <slug>_regex_<n>.png at 2x."""
    if not count:
        return []
    from playwright.sync_api import sync_playwright
    img_dir = os.path.join(out_dir, "_images")
    os.makedirs(img_dir, exist_ok=True)
    names = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1000, "height": 900},
                                color_scheme="light", device_scale_factor=2)
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        blocks = page.locator('[data-note-block-type="regex_cards"]')
        for i in range(min(count, blocks.count())):
            blocks.nth(i).scroll_into_view_if_needed()
            page.wait_for_timeout(600)
            page.evaluate(_HIDE_FIXED)
            name = f"{slug}_regex_{i + 1}.png"
            blocks.nth(i).screenshot(path=os.path.join(img_dir, name))
            names.append(name)
        browser.close()
    return names + [None] * (count - len(names))


def screenshot_diagrams(url, out_dir, slug):
    """Save every pipeline diagram block as <slug>_diagram_<n>.png.

    Returns the file names in page order (empty if none or playwright is missing).
    Names include the lesson slug so lessons never overwrite each other's images.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed: .venv/bin/pip install playwright && "
              ".venv/bin/playwright install chromium", file=sys.stderr)
        return []
    img_dir = os.path.join(out_dir, "_images")
    os.makedirs(img_dir, exist_ok=True)
    names = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # same layout, 2x the pixels: sharper images without changing the page
        page = browser.new_page(viewport={"width": 1000, "height": 900},
                                color_scheme="light", device_scale_factor=2)
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        blocks = page.locator(DIAGRAM_SELECTOR)  # all diagram kinds, in page order
        for i in range(blocks.count()):
            name = f"{slug}_diagram_{i + 1}.png"
            blocks.nth(i).scroll_into_view_if_needed()
            blocks.nth(i).screenshot(path=os.path.join(img_dir, name))
            names.append(name)
        browser.close()
    return names


def topic_dir(slug):
    """lessons/<area>/<topic> for a slug, from tools/topics.json. Exits if the slug is not mapped."""
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "topics.json")) as f:
        topics = json.load(f)
    key = re.sub(r"_(beginner|intermediate|advanced)$", "", slug)
    folder = topics.get(slug) or topics.get(key)
    if not folder:
        sys.exit(f"{slug!r} is not in tools/topics.json. Add \"{key}\": \"<area>/<topic>\" "
                 "(the folder named after the lesson's card in the site's UI), then rerun.")
    return os.path.join("lessons", folder)


def restore_astral_code(html):
    """The site renders inline code one UTF-16 unit per span, so an emoji outside the BMP (a flag, say)
    reaches the HTML as two U+FFFD spans per character. The page's embedded JSON still holds the real
    character: put it back, matching each code value to its run of U+FFFD spans."""
    for m in re.finditer(r'\\"type\\":\\"python_inline_code\\",\\"value\\":\\"([^"\\]+)\\"', html):
        val = m.group(1)
        if not re.search("[\U00010000-\U0010ffff]", val):
            continue
        run = "".join("(?:<span[^>]*>\ufffd</span>){2}" if ord(c) > 0xFFFF
                      else "(?:<span[^>]*>" + re.escape(c) + "</span>)" for c in val)
        html = re.sub(run, lambda _: "<span>" + val + "</span>", html, count=1)
    return html


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    url = args[0] if args[0].startswith("http") else BASE + args[0]
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    out_dir = args[1] if len(args) > 1 else topic_dir(slug)
    req = urllib.request.Request(url, headers={"User-Agent": "lesson-to-md/1.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    html = restore_astral_code(html)
    os.makedirs(out_dir, exist_ok=True)
    images = screenshot_diagrams(url, out_dir, slug) if "--screenshots" in sys.argv else []
    animations = (record_animations(url, out_dir, slug, animation_info(html))
                  if "--screenshots" in sys.argv else {})
    for entries in animations.values():  # upload now: a failure here must not leave a half-written lesson file
        for _, name in entries:
            if name.endswith(".mp4"):
                upload_animation(name)
    soup0 = BeautifulSoup(html, "html.parser")
    cells, done = {}, 0  # every runnable kind on the page, each screenshotted with its own control
    for cell_kind in CELL_KINDS:
        n_cells = len(soup0.find_all(attrs={"data-note-block-type": cell_kind}))
        if n_cells and "--screenshots" in sys.argv:
            cells[cell_kind] = record_cells(url, out_dir, slug, n_cells, cell_kind, done)
        done += n_cells
    n_regex = len(soup0.find_all(attrs={"data-note-block-type": "regex_cards"}))
    regex_images = record_regex_cards(url, out_dir, slug, n_regex) if "--screenshots" in sys.argv else []
    switchers = (sql_switcher_tabs(url, out_dir if "--screenshots" in sys.argv else None, slug)
                 if soup0.find(attrs={"data-note-block-type": "sql_switcher"}) else [])
    path = os.path.join(out_dir, slug + ".md")
    tmp_path = path + ".tmp"  # written in full, then renamed over the lesson
    with open(tmp_path, "w", encoding="utf-8") as f:
        challenges = fetch_challenges(slug)
        drop_refs = False
        airflow = bool(challenges) and challenges[0].get("challenge_type") == "airflow"
        tool = challenges[0].get("challenge_type") if challenges else None
        if airflow and not INCLUDE_AIRFLOW_EXERCISES:
            print(f"note: {len(challenges)} Airflow exercise(s) left out "
                  f"(INCLUDE_AIRFLOW_EXERCISES is False)", file=sys.stderr)
            sections, drop_refs = [], True
        elif tool in SKIPPED_TOOL_EXERCISES:
            print(f"note: {len(challenges)} {tool} exercise(s) left out (SKIPPED_TOOL_EXERCISES)",
                  file=sys.stderr)
            sections, drop_refs = [], True
        elif airflow:
            kept = [c for c in challenges if c["config"].get("form") == "dag_repair"]
            left_out = sorted({str(c["config"].get("form")) for c in challenges if c not in kept})
            if left_out:
                print(f"note: {len(challenges) - len(kept)} Airflow exercise(s) left out on purpose "
                      f"(forms: {', '.join(left_out)})", file=sys.stderr)
            sections = airflow_sections(url, out_dir, slug, kept) if kept else []
        else:
            groups = exercise_groups(url, challenges) if challenges else []
            shots = (screenshot_schema_diagrams(url, out_dir, slug, challenges)
                     if challenges and "--screenshots" in sys.argv else {})
            sections, start = [], 0
            for anchor, group in groups:
                sections.append((anchor, exercises_markdown(group, shots, start)))
                start += len(group)
        f.write(convert(html, images, sections, animations, drop_refs,
                       load_drops(slug), cells, regex_images, switchers))
    os.replace(tmp_path, path)
    if any(os.sep + os.path.join(*d) + os.sep in os.path.abspath(path)
           for d in (("learn", "python"), ("learn", "sql"), ("interview", "sql"))):
        # Learn Python, Learn SQL, Interview SQL: exercise spots become links to placeholder files and
        # hand trims are re-applied (tools/python_exercises.json, tools/sql_exercises.json); lessons
        # without an entry are left alone
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from python_exercise_placeholders import apply_lesson
        n = apply_lesson(path)
        print(f"note: {n} exercise placeholder(s) written (python_exercise_placeholders.py)", file=sys.stderr)
    print(path)


if __name__ == "__main__":
    main()
