# Complex Data: Advanced - Long tracks by id (placeholder)

Lesson: [complex_data_advanced.md](../complex_data_advanced.md)

> **Placeholder.** The real exercise for this spot is not mapped yet. The lesson links here where the exercise sat; the text below only referred to the exercise, so it was moved here from the lesson. Replace this file with the exercise when it is mapped.

## Text moved from the lesson

The `playlists` table has `playlist_id`, `track_ids` and `durations_sec`, with matching positions in the 2 arrays. Build a query that returns a row per playlist with an array of the track ids whose duration exceeds 180 seconds.

The final query combines the lesson: 2 parallel arrays, a pairing lambda, a filter and no UNNEST. For each playlist it returns the ids of tracks longer than 180 seconds as an array; on playlists 101 and 102 that is `['t9', 't7']` and `['t2', 't8']`.
