# E3. Retiring old records at publication

Under lazy, the legacy record of an object is retired as soon as the re-embedded object is published in the new epoch. This experiment measures what this costs against not migrating (static) and against dual migration, and how many of the true top-five results of held-out queries lose every path through retirement (lost paths).

| | |
|---|---|
| In the paper | Results, "Retiring old records at publication cuts off results" |
| Rounds and hypotheses | 8 (H4b), 9 (H7b), 10 (H10c); lost paths from rounds 11, 13 and 14 |
| Analysis scripts | `python3 evo/analyze_r8.py`, `python3 evo/analyze_r9.py`, `python3 evo/analyze_r10.py`, `python3 evo/analyze_r11.py`, `python3 evo/analyze_r13.py`, `python3 evo/analyze_r14.py` |

## Results

Retiring each legacy record as soon as its replacement was published made reranked recall on the query stream worse than not migrating at all. On code 100k, lazy was 15.0, 9.7 and 8.9 points below static for bge-base, e5-large and Arctic in round 8, and 15.0, 12.1 and 8.7 points below on new seeds with capped placement in round 10; on code 20k and SciFact the gap was 4.8 to 9.7 points (round 9). In all twelve prespecified tests the upper end of the 95% interval was below zero (H4b, H7b, H10c).

[Table E3.3](#table-e33) shows where the loss comes from. At the end of the stream on code 100k, 6.2 to 17.3% of the true top-five results of held-out queries had lost their path through retirement: their legacy record was gone, and the native index did not return them. Waiting for one sighting before retiring reduced this share by a factor of five to eight, and never retiring removed it. Switching to the complete native index, as full does, left 16.7 to 33.1% of the results that the legacy index had reached out of reach, which is the change in findability caused by the new placement alone. The negative flips show the same pattern query by query: lazy made the reranked results of 13.0 to 28.9% of the held-out queries worse than under static, against 0.2 to 2.4% with drain. On the original SRP keys retirement cut off fewer results (see [E6](E6_original_srp_keys.md)).

## Tables

### Table E3.1

End of the 3,000-arrival stream on code 100k (Zipf(1), 10 seeds; dual migration with rule k1). Re-embedded: objects outside S re-embedded, as a share of full; map-all additionally publishes 98,000 mapped records at t = 0.

| Model | Policy | Round 8, `itq_q`, seeds 6 to 15 · Held-out final | Round 8, `itq_q`, seeds 6 to 15 · Stream rerank | Round 8, `itq_q`, seeds 6 to 15 · Re-emb. (%) | Round 8, `itq_q`, seeds 6 to 15 · Payload | Round 8, `itq_q`, seeds 6 to 15 · Dual (%) | Round 10, `itq_q+cap16`, seeds 16 to 25 · Held-out final | Round 10, `itq_q+cap16`, seeds 16 to 25 · Stream rerank | Round 10, `itq_q+cap16`, seeds 16 to 25 · Re-emb. (%) | Round 10, `itq_q+cap16`, seeds 16 to 25 · Payload | Round 10, `itq_q+cap16`, seeds 16 to 25 · Dual (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bge-base | static | 38.9 | 57.1 | 0 | 19.7 | 0 | 39.7 | 54.6 | 0 | 19.8 | 0 |
|  | lazy | 42.8 | 42.1 | 40 | 12.9 | 0 | 42.6 | 39.6 | 40 | 12.9 | 0 |
|  | dual | 48.9 | 57.2 | 38 | 4.0 | 31.6 | 49.8 | 56.3 | 38 | 4.0 | 31.6 |
|  | full | 54.3 | 57.5 | 100 | 0 | 0 | 53.8 | 52.5 | 100 | 0 | 0 |
|  | map-all | 36.3 | 39.7 | 14 | 4.6 | 0 |  |  |  |  |  |
| e5-large | static | 29.6 | 45.2 | 0 | 19.5 | 0 | 29.3 | 45.3 | 0 | 19.4 | 0 |
|  | lazy | 28.6 | 35.5 | 41 | 13.4 | 0 | 30.3 | 33.2 | 40 | 13.2 | 0 |
|  | dual | 36.3 | 51.0 | 39 | 3.9 | 32.6 | 35.3 | 48.9 | 39 | 3.9 | 32.2 |
|  | full | 43.2 | 47.3 | 100 | 0 | 0 | 44.0 | 45.4 | 100 | 0 | 0 |
|  | map-all | 22.1 | 29.7 | 39 | 12.6 | 0 |  |  |  |  |  |
| Arctic | static | 18.6 | 29.8 | 0 | 19.5 | 0 | 19.9 | 29.9 | 0 | 19.5 | 0 |
|  | lazy | 20.6 | 20.9 | 44 | 14.4 | 0 | 22.2 | 21.2 | 44 | 14.4 | 0 |
|  | dual | 27.3 | 36.5 | 42 | 3.7 | 35.3 | 29.4 | 36.2 | 42 | 3.8 | 35.2 |
|  | full | 30.8 | 32.1 | 100 | 0 | 0 | 31.7 | 31.9 | 100 | 0 | 0 |
|  | map-all | 17.2 | 17.3 | 17 | 5.6 | 0 |  |  |  |  |  |

### Table E3.2

Dual migration (rule k1) on code 20k and SciFact (round 9, `itq_q`, Zipf(1), 10 seeds; streams of 600 and 155 arrivals). Held-out final R@5 at the end of the stream; difference with 95% interval.

| Corpus | Model | static | lazy | Dual | full | Dual − lazy | Payload lazy / dual | Dual at end (%) |
|---|---|---|---|---|---|---|---|---|
| code 20k | bge-base | 52.6 | 60.5 | 65.3 | 69.7 | +4.9 [4.2, 5.5] | 14.0 / 8.4 | 30.1 |
|  | e5-large | 39.2 | 45.8 | 50.5 | 65.1 | +4.8 [3.3, 6.2] | 13.1 / 7.9 | 27.9 |
|  | Arctic | 31.3 | 41.2 | 47.4 | 54.3 | +6.2 [4.9, 7.4] | 14.8 / 8.1 | 32.1 |
| SciFact | bge-base | 52.6 | 61.9 | 67.1 | 72.0 | +5.2 [4.2, 6.1] | 15.6 / 12.4 | 29.3 |
|  | e5-large | 41.5 | 50.5 | 55.2 | 64.0 | +4.7 [3.6, 5.8] | 15.8 / 12.5 | 30.0 |
|  | Arctic | 38.8 | 47.1 | 53.7 | 58.0 | +6.6 [5.1, 8.1] | 16.1 / 12.5 | 30.2 |

### Table E3.3

Lost paths and negative flips at the end of the 3,000-arrival stream on code 100k (`itq_q+cap16`, ten seeds; round 11, and rounds 13 and 14 for drain; exploratory). Ranges are over bge-base, e5-large, Arctic and MiniLM. Lost: share of the true top-five results of held-out queries left without a path by retirement; for full, share of the results reached by the legacy index that the native index does not reach. Flips: share of held-out queries whose top five holds fewer true neighbors than under static.

| Policy | Lost (%) | Flips after reranking (%) | Flips before reranking (%) |
|---|---|---|---|
| lazy | 7.1 to 17.3 | 13.0 to 28.9 | 14.6 to 29.6 |
| bg | 6.2 to 14.5 |  |  |
| dual, background retired | 4.9 to 12.1 |  |  |
| lazy+delay | 1.3 to 2.5 |  |  |
| dual migration, k1 | 1.4 to 3.0 | 3.7 to 6.4 | 10.0 to 18.6 |
| dual migration, drain | 0 | 0.2 to 2.4 | 8.3 to 15.6 |
| lazy+keep | 0 | 0.5 to 1.0 |  |
| full | 16.7 to 33.1 | 15.6 to 41.5 | 8.2 to 24.0 |
