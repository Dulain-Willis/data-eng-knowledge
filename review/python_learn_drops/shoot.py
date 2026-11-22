"""Review helper: screenshot each Learn Python place (target block outlined, one block before and
after, 2x) from the live site. Reads places.json (written by the page builder). Throwaway tooling
for the never-merged review PR; run with the repo .venv python."""
import json, sys, os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
places = json.load(open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "places.json")))
MAXSIDE = 650  # css px kept of the neighbouring block on each side

TOP = """() => [...document.querySelectorAll('[data-note-block-type]')]
  .filter(e => !e.parentElement.closest('[data-note-block-type]'))"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1100, "height": 900}, device_scale_factor=2)
    by_lesson = {}
    for n, pl in enumerate(places, 1):
        by_lesson.setdefault(pl["lesson"], []).append((n, pl))
    for lesson, items in by_lesson.items():
        page.goto("https://datadriven.io/learn/" + lesson, wait_until="domcontentloaded")
        page.wait_for_selector("[data-note-block-type]", timeout=60000)
        page.wait_for_timeout(5000)
        # hide the sticky site header and other fixed overlays so they do not cover the blocks
        page.evaluate("""() => document.querySelectorAll('body *').forEach(e => {
            const p = getComputedStyle(e).position;
            if (p === 'fixed' || p === 'sticky') e.style.setProperty('visibility', 'hidden', 'important'); })""")
        handle = page.evaluate_handle(TOP)
        types = page.evaluate("els => els.map(e => e.getAttribute('data-note-block-type'))", handle)
        # the live page has extra top-level 'python' exercise blocks the static HTML lacks: align without them
        live_idx = [k for k, t in enumerate(types) if t != "python"]
        for n, pl in items:
            i = live_idx[pl["idx"]]
            assert types[i] == pl["btype"], (lesson, i, types[i], pl["btype"])
            boxes = page.evaluate("""([els, i]) => els.slice(Math.max(0,i-1), i+2).map(e => {
                e.scrollIntoView({block:'center'}); const r = e.getBoundingClientRect();
                return {y: r.top + scrollY, h: r.height}; })""", [handle, i])
            # re-measure after scrolling (lazy content can shift layout)
            page.wait_for_timeout(700)
            boxes = page.evaluate("""([els, i]) => els.slice(Math.max(0,i-1), i+2).map(e => {
                const r = e.getBoundingClientRect(); return {y: r.top + scrollY, h: r.height}; })""", [handle, i])
            has_prev = i > 0
            tgt = boxes[1] if has_prev else boxes[0]
            nxt = boxes[2] if len(boxes) > (2 if has_prev else 1) else None
            prv = boxes[0] if has_prev else None
            top = tgt["y"] - 14
            if prv:
                top = max(prv["y"] - 8, tgt["y"] - MAXSIDE - 14) if prv["h"] > MAXSIDE else prv["y"] - 8
            bottom = tgt["y"] + tgt["h"] + 14
            if nxt:
                bottom = min(nxt["y"] + nxt["h"] + 8, tgt["y"] + tgt["h"] + MAXSIDE + 14)
            page.evaluate("""([els, i]) => { const e = els[i]; e.dataset.oldOutline = e.style.outline;
                e.style.outline = '4px solid #e00'; e.style.outlineOffset = '4px'; }""", [handle, i])
            out = os.path.join(HERE, "img", f"{n:02d}_{lesson}.png")
            page.screenshot(path=out, full_page=True,
                            clip={"x": 0, "y": max(0, top), "width": 1100, "height": bottom - max(0, top)})
            page.evaluate("""([els, i]) => { els[i].style.outline = els[i].dataset.oldOutline || ''; }""", [handle, i])
            print(n, lesson, out, round(bottom - top), flush=True)
    browser.close()
