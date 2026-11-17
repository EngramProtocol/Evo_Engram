# E4. Each part of dual migration

Dual migration keeps the legacy record of a re-embedded object with the new code attached, migrates the rest of the corpus in the background and retires legacy records only under a rule. This experiment compares dual migration with lazy and static at the same re-embedding budget and isolates each part with ablation variants that change one part at a time.

| | |
|---|---|
| In the paper | Results, "Each part of dual migration has a distinct effect"; Table 2 |
| Rounds and hypotheses | 8 to 10 (H4a, H7a, H10b), 11 (H11, H16), 14 (H23) |
| Analysis scripts | `python3 evo/analyze_r8.py`, `python3 evo/analyze_r9.py`, `python3 evo/analyze_r10.py`, `python3 evo/analyze_r11.py`, `python3 evo/analyze_r14.py` |

## Results

With the same re-embedding budget, dual migration with rule k1 reached higher held-out recall than lazy in every prespecified comparison on the three original target models: by 6.2, 7.7 and 6.7 points on code 100k with uncapped learned placement (round 8), by 7.1, 5.0 and 7.2 points with capped placement on new seeds (round 10), and by 4.7 to 6.6 points on code 20k and SciFact (round 9), with a positive difference for all ten seeds of every pair. It was also 6.0 to 16.1 points above static (H4a, H7a, H10b). full stayed 2.3 to 8.7 points higher on code 100k (round 10), but it re-embeds 2.4 to 2.6 times as many objects at once, is modeled as an instantaneous rebuild and reads a single epoch. Given the peers of both epochs, a complete native index is further ahead on unseen queries: on the bge-base streams of Table 4 of the paper, full with T = 16 contacted 1,142 peers and reached 64.3% on held-out queries, 13.9 points above drain (95% interval 10.6 to 17.2) and 10.1 points above full with T = 8, while its stream rerank did not differ from that of drain (65.0 against 65.3; round 14, exploratory). Dual migration is therefore no substitute for a finished migration; what it provides is the quality reached while only part of the corpus has been re-embedded ([Table E3.1](E3_retiring_at_publication.md#table-e31) and [Table E3.2](E3_retiring_at_publication.md#table-e32) give every policy).

Table 2 of the paper separates the parts (H11, prespecified, all twelve criteria met), each comparison changing one part at a fixed re-embedding budget. The parts act on different things. Keeping legacy records until a sighting protects the queries that are being served: it raised stream rerank by 9.4 to 11.1 points, yet on held-out queries lazy+delay was no better than lazy (41.6 against 42.6 for bge-base). What helps unseen queries is the background migration in dual form, paid for with the re-embeddings that delayed retirement saves; it produced the largest held-out gain, 6.0 to 8.4 points. The attached code mainly lowers the cost of serving and improves its quality: it cut payload fetches on the query path to 23 to 26% of those of the variant without it, raised stream final recall by 8.2 to 11.1 points and also raised held-out recall by 2.7 to 5.2 points (exploratory). MiniLM and the uniform workload gave the same signs in all comparisons (exploratory; see the notes below).

These comparisons used rule k1. Round 14 repeated the stream with drain for e5-large, Arctic and MiniLM on the seeds of round 11 (H23, prespecified, all 18 criteria met; bge-base had been run in round 13). drain exceeded lazy by 8.0, 8.6 and 2.6 points of held-out recall and by 20.3, 21.4 and 13.1 points of stream rerank, and static by 7.7, 11.5 and 12.0 points and by 9.2, 11.8 and 10.1 points. It was also above rule k1 for all four models, by 1.2 to 1.9 points on held-out queries and by 4.9 to 8.2 points of stream rerank, with every interval above zero, so the loss from retiring after one sighting on the stream no longer rests on bge-base alone ([Table E4.1](#table-e41) and [Table E4.2](#table-e42)).

## Notes

### Parts of dual migration

In a further exploratory split, delayed retirement without the attached code accounted for 4.6 to 7.5 rerank points and the code for another 3.7 to 5.7. MiniLM and the uniform workload gave the same signs in all comparisons (exploratory), although for MiniLM the two retirement parts gained less, 4.8 points on the query path and 1.8 points in the background.

## Tables

### Table E4.1

End of the 3,000-arrival stream on code 100k under learned placement (`itq_q+cap16`, Zipf(1), seeds 26 to 35), with drain for the three models that Table 4 of the paper does not cover (round 14, H23). Columns as in that table. Lost: share of the true top-five results of held-out queries left without a path by retirement; for full, share of the results reached by the legacy index that the native index does not reach. Flips: share of held-out queries whose reranked top five holds fewer true neighbors than under static. Every policy except full contacts 1,189 to 1,193 peers per query. Payloads of drain on the query path relative to lazy: 0.229, 0.204 and 0.233 (highest seed 0.243, 0.216 and 0.253); dual objects at the end in the highest seed: 40.4, 43.5 and 40.6%.

| Policy | Held-out final | Stream rerank | Payload | Re-embed. query + bg | Dual at end (%) | Peak records (%) | Peak bytes per object and table | Lost (%) | Flips (%) |
|---|---|---|---|---|---|---|---|---|---|
| **e5-large** |  |  |  |  |  |  |  |  |  |
| static | 30.2 | 45.5 | 19.4 | 0 + 0 | 0 | 100 | 512 | 0 |  |
| lazy | 29.8 | 34.4 | 13.2 | 13.2 + 0 | 0 | 100 | 512 | 14.8 | 28.9 |
| lazy+delay | 29.9 | 45.5 | 4.4 | 4.4 + 0 | 8.6 | 108.6 | 600 | 2.4 | 7.3 |
| lazy+keep | 30.6 | 52.9 | 3.2 | 3.2 + 0 | 9.7 | 109.7 | 612 | 0 | 1.0 |
| dual, bg retired | 32.1 | 48.7 | 4.1 | 4.1 + 8.7 | 8.9 | 108.9 | 603 | 10.3 | 21.8 |
| dual, no code | 32.9 | 44.4 | 15.7 | 1.6 + 11.1 | 32.4 | 132.4 | 678 | 2.5 | 7.4 |
| dual (k1) | 35.9 | 48.8 | 3.9 | 3.9 + 8.7 | 32.2 | 132.2 | 841 | 2.6 | 6.4 |
| dual (drain) | 37.8 | 54.7 | 3.0 | 3.0 + 9.9 | 38.8 | 138.8 | 910 | 0 | 1.5 |
| full | 43.2 | 46.2 | 0 | all at t = 0 | 0 | 100 | 512 | 33.1 | 41.5 |
| **Arctic** |  |  |  |  |  |  |  |  |  |
| static | 18.8 | 31.2 | 19.4 | 0 + 0 | 0 | 100 | 509 | 0 |  |
| lazy | 21.8 | 21.5 | 14.3 | 14.3 + 0 | 0 | 100 | 509 | 17.3 | 26.3 |
| lazy+delay | 20.2 | 30.8 | 4.4 | 4.4 + 0 | 8.6 | 108.6 | 570 | 2.5 | 6.7 |
| lazy+keep | 20.8 | 40.2 | 3.2 | 3.2 + 0 | 9.5 | 109.5 | 582 | 0 | 0.5 |
| dual, bg retired | 23.3 | 34.4 | 4.0 | 4.0 + 9.9 | 8.8 | 108.8 | 540 | 12.1 | 20.7 |
| dual, no code | 23.4 | 30.8 | 16.6 | 1.5 + 12.2 | 35.2 | 135.2 | 637 | 2.7 | 6.6 |
| dual (k1) | 28.6 | 34.7 | 3.8 | 3.8 + 9.9 | 35.0 | 135.0 | 770 | 3.0 | 4.9 |
| dual (drain) | 30.3 | 42.9 | 2.9 | 2.9 + 11.1 | 42.1 | 142.1 | 833 | 0 | 0.2 |
| full | 31.2 | 33.8 | 0 | all at t = 0 | 0 | 100 | 384 | 32.2 | 36.2 |
| **MiniLM** |  |  |  |  |  |  |  |  |  |
| static | 17.2 | 26.7 | 19.2 | 0 + 0 | 0 | 100 | 506 | 0 |  |
| lazy | 26.6 | 23.8 | 13.0 | 13.0 + 0 | 0 | 100 | 506 | 7.1 | 13.0 |
| lazy+delay | 20.0 | 28.6 | 4.4 | 4.4 + 0 | 8.7 | 108.7 | 525 | 1.3 | 4.5 |
| lazy+keep | 19.6 | 33.6 | 3.3 | 3.3 + 0 | 9.8 | 109.8 | 543 | 0 | 0.7 |
| dual, bg retired | 26.2 | 31.9 | 4.1 | 4.1 + 8.5 | 9.0 | 109.0 | 506 | 4.9 | 9.0 |
| dual, no code | 26.2 | 29.5 | 15.7 | 1.5 + 10.9 | 31.7 | 131.7 | 548 | 1.3 | 3.9 |
| dual (k1) | 28.0 | 32.0 | 3.9 | 3.9 + 8.5 | 31.5 | 131.5 | 608 | 1.4 | 3.7 |
| dual (drain) | 29.2 | 36.9 | 3.0 | 3.0 + 9.7 | 38.3 | 138.3 | 653 | 0 | 0.5 |
| full | 47.7 | 45.7 | 0 | all at t = 0 | 0 | 100 | 192 | 16.7 | 15.6 |

### Table E4.2

drain against lazy, static and rule k1 at the end of the stream of [Table E4.1](#table-e41) (round 14, H23; ten seeds). Paired differences in points with 95% intervals. The criteria required a lower bound above 0 (a, d, e), above 5 (b), above 3 (c) and above −1 (f); all 18 were met. The column for bge-base comes from round 13 and was not part of H23.

| Comparison | e5-large | Arctic | MiniLM | bge-base (round 13) |
|---|---|---|---|---|
| drain − lazy, held-out final (a) | +8.04 [5.50, 10.58] | +8.58 [6.07, 11.09] | +2.62 [1.01, 4.23] | +7.76 [5.73, 9.79] |
| drain − lazy, stream rerank (b) | +20.28 [16.41, 24.14] | +21.45 [17.62, 25.28] | +13.12 [9.72, 16.53] | +20.95 [18.44, 23.45] |
| drain − static, held-out final (c) | +7.68 [6.62, 8.74] | +11.52 [10.54, 12.50] | +11.98 [10.87, 13.09] | +11.56 [9.62, 13.50] |
| drain − static, stream rerank (d) | +9.16 [7.23, 11.08] | +11.76 [8.30, 15.22] | +10.14 [8.56, 11.72] | +7.82 [6.09, 9.56] |
| drain − k1, stream rerank (e) | +5.86 [3.54, 8.18] | +8.20 [5.63, 10.77] | +4.92 [3.14, 6.70] | +5.83 [2.93, 8.73] |
| drain − k1, held-out final (f) | +1.92 [0.91, 2.93] | +1.76 [1.09, 2.43] | +1.22 [0.67, 1.77] | +1.42 [0.63, 2.21] |
