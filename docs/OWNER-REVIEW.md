# Owner review list (spec #10)

Everything the agents left for you to decide or look at. Nothing here blocked the work; each item has a default that was applied, so changing it later is cheap. Add new items at the bottom of the right section; strike items when decided.

## Decisions pending

1. ~~Two blank Kafka animations (#14/#15).~~ **Decided:** converted to MP4 as recorded; see `docs/KNOWN-ISSUES.md`.
2. ~~**Side-edge cuts (#14).**~~ **Decided:** accepted as-is, recorded in `docs/KNOWN-ISSUES.md`. Checked on the MP4s: confirmed cut: consumer_groups_intermediate animation_2 "c1 never commits" ("4 ro"), animation_1 "commit after the write", animation_4 (both tabs); in_the_pipeline advanced, beginner and intermediate_animation_2; dbt models_advanced_animation_2 and models_intermediate_animation_1. False positives (not clipped): consumer_groups_intermediate animation_1 "commit before the work", animation_2 "c1 commits after each write", animation_3 (both tabs).
3. ~~**Learn Python drop / keep / trim (#18).**~~ **Decided:** the text that only referred to an exercise moves into a placeholder file (`lessons/learn/python/<card>/_exercises/<slug>_exercise_<n>.md`, 31 files) and the lesson links to it where the exercise sat; the words "Practice"/"Capstone" are gone from headings. Of the 56 places of PR #25: 35 moved (27 drops, 8 trims), 4 heading-only (11, 51, 52, 54), 17 kept in the lesson (listed below, owner attention). Tools: `tools/python_exercises.json` + `tools/python_exercise_placeholders.py` (run by the converter), see `docs/skipped-blocks.md`. PR #25's review page can stay. *Kept, please look (place, lesson, text, why):*
   - 10 `python_foundations_intermediate`, "The capstone pulls the 5 sections into one short script: ... Predict the traceback first, then decide the fix." Introduces the multiple-choice question that is still inline.
   - 16 `python_expressions_beginner`, "A fixed fee plus a per-item cost needs no parentheses, because `*` runs before `+`: ..." Own precedence examples (5.0 + 4 * 1.5 = 11.0).
   - 17 `python_expressions_beginner`, "Each operator needs the pair it accepts. A repeat count stands on the other side of `*` ..." Type-pairing rule with examples.
   - 18 `python_expressions_beginner`, "String operators share the same precedence. In `"-" * 3 + "x"` ..." Own examples.
   - 39 `python_loops_beginner`, "A misplaced starting line fails without an error message. ..." Debugging tip: an accumulator reset inside the body.
   - 40 `python_loops_beginner`, "A countdown reads the same way with a negative step. ..." range(9, 2, -1) worked example.
   - 41 `python_loops_beginner`, "A target such as "the first value that is at least X" turns into a condition ..." Worked while-condition example.
   - 42 `python_loops_beginner`, "Swapping `continue` for `break` turns a filter into a stop sign. ..." Worked example of the silent-wrong-total bug.
   - 43 `python_loops_beginner`, "When a printed value belongs to the wrong loop, look for a name that 2 loops share. ..." Advice about loop-variable reuse.
   - 44 `python_strings_advanced`, "The 2 repairs differ when the separator is missing. ..." split vs partition comparison.
   - 45 `python_strings_advanced`, "When only one value is a number, converting it inside the brackets is the smallest repair: ..." join/str repair with its own values.
   - 46 `python_strings_advanced`, "A pattern that quietly finds nothing is the usual sign of the backslash bug, and `len` exposes it ..." len("\b") vs len(r"\b") demonstration.
   - 47 `python_strings_advanced`, "Centering splits the padding in 2, and when the padding is odd the extra character goes on the right ..." Format-spec example.
   - 48 `python_strings_advanced`, "`len` counts code points, which is not always what a reader sees as 1 symbol. ..." Flag emoji example (2 code points, 8 bytes).
   - 49 and 50 `python_lists_advanced`, "The last problems use everything from the earlier sections. ... Trace each name to the object it points at before you answer." Introduces the multiple-choice question that is still inline (heading is now "A plan with undo" plus a placeholder link).
   - 53 `python_dictionaries_beginner`, "Real programs mix the removal tools, and the order of the calls decides what each one finds. Trace this session cleanup line by line before you run it:" Points at the run cell directly below, which is still in the lesson.
   Multiple-choice questions and run cells stay inline in all lessons (they are converted lesson content, not the removed widgets); the placeholders sit next to them. Say if you want the questions moved too.
4. **Learn SQL tabbed examples (#20 -> #22).** Review page: PR #24 (`review/sql_learn_tabs/README.md`). 58 tabbed blocks, 152 tabs. Options A (heading + code per tab + result text, recommended), B (A + screenshot per tab, ~17 MB), C (first tab only), D (one merged block). *Default applied:* Option A (see 'Applied by default' below).
5. **Odd-looking Learn SQL sentences (#21).** Kept in the lessons, undecided: `data_types_beginner` ("A quantity of 3 at a price of 19.99"), `aggregating_beginner` ("SUM(profit) and AVG(profit)"), `complex_data_advanced` ("Capstone: long tracks by id" heading and follow-up), `query_structure_beginner` ("List those names after SELECT"), `query_structure_advanced` (headingless sentence left after a drop). A screenshot PR will be made for these.

## Things to look at

- **Spark PR #8 was merged as a merge commit, not a squash**, so its old GIF blobs are in history (repo ~714 MB stored). Left alone as instructed (no history rewrite).
- **Spark `spark_storage_formats_advanced_animation_1`** ends at step 10/19 with the diagram zoomed out (pre-existing, not touched).
- **Interview Python videos (#16): fixed on `fix-16-frames`.** The first review sampled 84 videos; the frame-0 check (`checks/animation_first_frames.py`) found 91 of all 255 `py_pattern_*` videos with page text under the player or a step counter not at 1/N. All 91 were re-recorded (the recorder now hides page content, starts paused at step 1, and runs the check with retries), uploaded as new assets and swapped into the lessons and `tools/animation_urls.json`. Final check: 0 of 255 flagged (two late flags were false positives from the check, fixed in the check).
- **Learn Python animations (#19): fixed on `fix-16-frames`.** Checked all 151 `python_animation` videos; 18 were flagged (17 with the frame defect, 1 asset, `python_sets_beginner_animation_2`, was missing/unreadable). All 18 re-recorded, check-clean, uploaded as new assets and swapped; 0 of 151 flagged now.
- **Recorder limits were loosened in #16** (bar players may end up to 1 s early, wait cap 170 s -> 400 s, start check by control position). This also applies to Airflow/Kafka/pipeline players but nothing was re-recorded with it.
- **Tooltip "Replay"** covers the start of the final caption in about 20 old PASS GIFs (cosmetic, now MP4s from the recorder that moves the mouse away).
- **Four Spark and one SQL still images** (`sql_pattern_ctes_advanced` animation 1, `complex_data_advanced` animation 1): the live site never mounts the player, so a still PNG is saved.
- **Hand trim in `sql_pattern_running_totals_beginner`** (the ", which is why the capstones ... 4 different vocabularies" clause) and the Learn Python trims are Markdown edits; re-running the converter on those lessons would bring the text back.
- **MP4s are not committed.** Local copies are in `~/animation-mp4s/` only; a lost hosted asset means re-recording.
- **Temporary PRs, never merge:** #7, #9 (old), #24 (SQL tabs), #25 (Python drops). Close them when done.
- **HANDOFF.md** still exists in the repo root; the spec says to delete it at the end.

## Added after #21
- **Learn SQL hand trims** (9 cuts across 5 lessons, commit "Learn SQL hand trims" on ticket-21, listed in `docs/skipped-blocks.md`). `joins_beginner` trim of ", and the blank below is that condition" is a judgement call.
- **Learn SQL pending-decision sentences** are kept as-is (see Decisions pending #5); `complex_data_advanced` not checked for a runnable cell after the Capstone heading.

## Applied by default
- **Learn SQL tabbed examples: Option A (ticket #22, branch `ticket-22`).** The owner was away, so the recommended Option A of PR #24 was applied: all 58 blocks / 152 tabs stay as text, each tab as a bold name label, caption, ```sql fence and result as text, no per-tab screenshots. Done by splicing into the existing lessons (no re-conversion, hand trims kept) and by the converter rule `sql_switcher` (`BLOCK-TYPES.md`). Lesson prose that said "tab"/"switcher" now says "version"/"examples". *To switch:* options B (add a 2x screenshot per tab, about 17 MB), C (first tab only) and D (one merged commented code block) are described with their trade-offs in PR #24 (`review/sql_learn_tabs/README.md`). Tell me the option and the sections are regenerated from the live pages the same way (`sql_switcher_tabs`, `switcher_markdown`).

## Review notes (independent reviewers, minor)
- Folder names `lessons/learn/python/foundations` and `.../expressions` omit the "Python" that the page titles have (cosmetic; MCP layout expects card folders as is).
- The upload code in `tools/lesson_to_md.py` writes the GitHub token to a mode-600 temp curl config deleted afterwards (the method you chose; never in the repo).
- Learn SQL `filtering_intermediate` keeps the site's own caption saying "the first tab"; the other stale tab wording (4 places) was fixed by hand after the #22 review.
- Anonymous `curl` of user-attachments video URLs returns 404; they play in a logged-out browser on rendered GitHub pages.
