# Known issues

- `kafka_producers_advanced_animation_2_6-partitions` and `kafka_the_log_intermediate_animation_1_orders-v2-6-partitions`: the live site's 6-partition mode does not animate (only the captions change). Recorded as-is as MP4s. If the site is fixed, re-record with `tools/rerecord_animations.py` and upload with `upload_animation(name, force=True)`.
- Side-edge cuts (site's own layout; recorded as-is), checked on the final frames. Right-hand table/card clipped:
  - `kafka_consumer_groups_intermediate` animation_2 "c1 never commits": ledger header reads "4 ro" and the FROM column is cut. Animation_1 "commit after the write" and animation_4 (both tabs): table cells cut at the right edge.
  - `kafka_in_the_pipeline_advanced` animation_1 (both tabs): row count in table headers cut ("0 rou").
  - `kafka_in_the_pipeline_beginner` animation_1 (both tabs): row count cut. Animation_2 (both tabs): "0 rows" touches the edge.
  - `kafka_in_the_pipeline_intermediate` animation_2: row count in table headers cut.
  - `dbt_models_advanced` animation_2 and `dbt_models_intermediate` animation_1: right-hand table columns cut.
