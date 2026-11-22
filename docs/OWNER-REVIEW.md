# Owner review list (spec #10)

Everything the agents left for you to decide or look at. Nothing here blocked the work; each item has a default that was applied, so changing it later is cheap. Add new items at the bottom of the right section; strike items when decided.

## Decisions pending

1. **Two blank Kafka animations (#14/#15).** `kafka_producers_advanced_animation_2_6-partitions` and `kafka_the_log_intermediate_animation_1_orders-v2-6-partitions`. On the live site the 6-partition mode draws only the producer card and caption, so the recording is blank. *Default applied:* the two GIFs stay in the lessons (the only GIFs left). Options: keep as-is, drop the 6-partition mode, or report it to the site.
2. **Side-edge cuts (#14).** 11 animations have a card or table cut at a side edge that comes from the site's own layout (8 Kafka: consumer_groups_intermediate x4, in_the_pipeline_advanced x2, in_the_pipeline_beginner x2; 2 dbt: models_advanced_animation_2, models_intermediate_animation_1; plus kafka_in_the_pipeline_intermediate_animation_2). *Default applied:* converted as they are. Same question as the 24 Spark ones: accept or not.
3. **Learn Python drop / keep / trim (#18).** Review page: PR #25 (`review/python_learn_drops/README.md`), 56 places. *Default applied in `ticket-19`:* proposed defaults, 27 drop (marked group in `tools/drops.json`), 21 keep, 8 hand trims (own commit "Learn Python hand trims (pending owner decision, see PR #25)"). Place 36 also got a one-word edit ("on it" removed). Tell me which places to change.
4. **Learn SQL tabbed examples (#20 -> #22).** Review page: PR #24 (`review/sql_learn_tabs/README.md`). 58 tabbed blocks, 152 tabs. Options A (heading + code per tab + result text, recommended), B (A + screenshot per tab, ~17 MB), C (first tab only), D (one merged block). *Default applied:* none yet; #21 keeps first tab only, #22 applies your choice.
5. **Odd-looking Learn SQL sentences (#21).** Kept in the lessons, undecided: `data_types_beginner` ("A quantity of 3 at a price of 19.99"), `aggregating_beginner` ("SUM(profit) and AVG(profit)"), `complex_data_advanced` ("Capstone: long tracks by id" heading and follow-up), `query_structure_beginner` ("List those names after SELECT"), `query_structure_advanced` (headingless sentence left after a drop). A screenshot PR will be made for these.

## Things to look at

- **Spark PR #8 was merged as a merge commit, not a squash**, so its old GIF blobs are in history (repo ~714 MB stored). Left alone as instructed (no history rewrite).
- **Spark `spark_storage_formats_advanced_animation_1`** ends at step 10/19 with the diagram zoomed out (pre-existing, not touched).
- **Interview Python videos (#16):** an independent review found about 7 of 84 sampled videos with page text under the player at frame 0 and 2 not starting at step 1. Fix branch `fix-16-frames` (re-records bad ones, adds a frame-0 check). Status: in progress; see the final report.
- **Learn Python animations (#19)** were recorded with the recorder from before that fix; they are to be frame-0 checked once the fix lands.
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
