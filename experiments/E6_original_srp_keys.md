# E6. Dual migration on the original SRP keys

This experiment repeats the query stream and the runs to completion with the native epoch on the original SRP keys, without centering and without a load cap, for the models whose q_f favors SRP. It measures how the value of keeping the legacy path changes with the selectivity of the new placement.

| | |
|---|---|
| In the paper | Results, "Keeping the old path pays off when a query reaches a small part of the corpus"; Table 3; Fig. 4 |
| Rounds and hypotheses | 14 (H24), 15 (H25; Arctic and MiniLM, equal progress and a faster background are exploratory) |
| Analysis scripts | `python3 evo/analyze_r14.py`, `python3 evo/analyze_r15.py` |

## Results

Round 15 (tag `evo-r15-prereg`) repeated the runs to completion of round 14 with the native epoch on the original SRP keys, without centering and without a load cap, and changed nothing else: code 20k and SciFact, 10,000 peers, a sample of 10%, Zipf(1), two deadlines per corpus, eight policies, seeds 46 to 55, and E₀ dropped when each policy completes. The simulator was not changed, and a rerun of one job of round 14 reproduced its 7,240 values. H25 was scored on the three target models for which the rule on q_f selects SRP on both corpora (bge-base, e5-large and gte-base; 12 cells, 68 criteria, all met). Arctic and MiniLM, for which the rule selects learned placement, were run in the same way without criteria. The learned side of every comparison comes from round 14 ([Table E5.3](E5_migration_to_completion.md#table-e53)) and was known when the criteria were fixed.

The first condition is the selectivity of the new placement. Round 14 tested it by repeating the stream experiment on the original SRP keys for bge-base and e5-large, the two target models on code 100k for which the placement rule favors SRP, with the seeds, overlays and query streams of the runs on learned placement (H24, prespecified, all twelve criteria met; [Table E6.1](#table-e61) and [Table E6.10](#table-e610) and the notes below). Under SRP, retirement at publication cut off fewer results, 7.3% (bge-base) and 2.4% (e5-large) of the true top-five results at the end of the stream against 11.3 and 14.8% under learned placement (H24f), and the gain of drain over lazy shrank with it, by 2.8 and 7.1 points of held-out recall and by 6.8 and 17.5 points of stream rerank (H24d and H24e). For bge-base, drain was still 4.9 points above lazy on held-out queries and 14.1 points above it in stream rerank. For e5-large, whose complete SRP index scores about 67,000 candidates per query, a record that has just moved is almost always found again, and drain was not significantly better than lazy. In neither case was drain worse (H24a and H24b), and it exceeded static by 12.6 and 14.9 points on held-out queries (H24c). At the end of this stream the migration was far from finished: drain reached 51.2 and 44.3% on held-out queries, against 66.3 and 85.8% for the complete SRP index.

Round 15 therefore followed the migration on SRP keys to completion (H25, prespecified, all 68 criteria met; Table 3 of the paper and [Table E6.2](#table-e62) to [Table E6.5](#table-e65)). It repeated the runs of round 14 for bge-base, e5-large and gte-base, the three target models for which the rule favors SRP on both code 20k and SciFact, and changed only the placement of the new epoch, so that each of the twelve cells shares its seeds, overlays, samples and query streams with the same cell under learned placement. Migrating gradually remained far better than leaving the old index in service: the area of drain was 18.1 to 33.1 points above that of rebuild and 20.8 to 37.0 points above that of static, with a smallest lower bound of 16.6 points against a required 10 (H25a and H25b). The comparison with retirement at publication changed in the direction that the first condition predicts. lazy+bg lost 1.4 to 10.2% of the true top-five results on SRP keys, against 13.8 to 23.8% under learned placement (H25e), and the advantage of drain over lazy+bg was smaller than under learned placement by 2.8 to 10.8 points of area and by 4.2 to 12.3 points of stream rerank (H25c and H25d). For e5-large and gte-base, whose predicted q_f exceeds 10⁻², nothing of the advantage remained: in all eight cells the area of drain was lower than that of lazy+bg, by 2.1 to 6.3 points with every interval below zero, where H25f had required only an upper bound below +1, while stream rerank differed by at most 1.0 point, with an interval that excluded zero only in the two cells of gte-base on code 20k. For bge-base, with a predicted q_f of 1.3 and 2.2×10⁻³, the two policies were close in area, with drain 0.5 to 1.4 points higher and the difference significant in the two SciFact cells, and drain kept an advantage of 3.0 to 5.7 points of stream rerank in all four cells.

That lazy+bg can end up ahead is a matter of timing. Both policies follow the same background schedule, but queries triggered the re-embedding of 50 to 72% of the objects outside S under lazy+bg and of 24 to 47% under drain, so that lazy+bg completed at 28 to 51% of t_end and drain at 53 to 76%, under either placement. What an early completion is worth depends on the placement. Under learned placement the dual state reads two epochs and ends above the complete index: when 85% of the objects had an E₁ record, the held-out recall of drain was 5.9 to 12.4 points higher than that of full (post hoc), so finishing later costs nothing. On SRP keys the complete index scores 46 to 55% of the corpus per query for bge-base and 81 to 87% for e5-large and gte-base, against 23 to 24% under learned placement; at the same stage drain was still 2.5 to 2.9 points above the complete index for bge-base but 6.4 to 8.0 points below it for the other two models, for which every arrival before completion is therefore a loss. Two exploratory comparisons separate the timing from the old path ([Table E6.6](#table-e66) and [Table E6.7](#table-e67)). At equal progress drain was not behind: when half of the objects had an E₁ record, its held-out recall was 4.0 to 4.6 points above that of lazy+bg for bge-base and 0.1 to 0.9 points above it for the other two models, where six of the eight intervals included zero. With a background twice as fast, drain was 1.2 and 1.5 points of area ahead for bge-base and within −0.3 to +0.5 points for the other two models. The runs to completion therefore do not equalize the rate of re-embedding: for e5-large and gte-base they show that the old path no longer pays for its storage, not that keeping it lowers quality at a given state of the migration.

We therefore use drain with learned placement, which is our default. On SRP keys the answer depends on how concentrated the space is. For a predicted q_f above 10⁻², retiring at publication with background migration was sufficient: it needed no storage beyond the initial level, whereas drain peaked at 2.4 to 2.8 times that level in PQ code bytes, and it reached the complete index sooner. For bge-base, drain still served the queries of the stream better at about the same area, so the choice depends on whether storage is short. These are also the spaces in which SRP keys concentrate the load: with every record on its SRP keys, the 1% most loaded peers held 50 to 63% of the records for e5-large and gte-base and 25 and 33% for bge-base, and the complete index scored 2.0 to 3.8 times as many candidates per query as under learned placement. This is why every migrating policy reaches a higher area on SRP keys than under learned placement for these models ([Table E6.4](#table-e64) and [Table E6.5](#table-e65)), and it is the trade described under Learned placement (C2).

The same runs for Arctic and MiniLM, for which the rule selects learned placement, show the other end of the range (round 15, exploratory; [Table E6.8](#table-e68) and [Table E6.9](#table-e69)). On SRP keys lazy+bg lost 17.2 to 34.8% of the true top-five results for these models, more than under learned placement, and drain exceeded it by 5.1 to 10.6 points of area and by 8.9 to 17.4 points of stream rerank in all eight cells. Over the ten corpus and model pairs, the advantage of drain over lazy+bg on SRP keys fell as the predicted q_f grew (Fig. 4 of the paper), with a rank correlation of −0.89 for area and −0.83 for stream rerank, whereas under learned placement it showed no relation with q_f (+0.03 and −0.08, post hoc). Keeping the old path thus pays off when a query reaches a small part of the corpus through its own keys. Learned placement brings this about for every model and SRP only for a small q_f, so the quantity that C1 predicts tells which case applies.

The second condition is how useful the legacy index still is to the new model. For MiniLM on code 100k (H16, with rule k1), dual migration was 10.8 points above static (H16b met) and above lazy by 8.4 points of stream final recall and 8.2 points of stream rerank, but on held-out queries it was only 1.4 points above lazy, with an interval from −0.4 to 3.2 (H16a not met), and lazy was not significantly below static in stream rerank (H16c not met). With drain on the same seeds the held-out gain over lazy was significant but still small, at 2.6 points (interval 1.0 to 4.2; H23a), against 7.8 to 8.6 points for the other three models. The legacy index serves MiniLM poorly: static kept 36% of the final recall of full, against 60 to 72% for the three original models, and the top fives of M₀ and MiniLM overlap by only 36 to 46%. For gte-base, whose top fives overlap with those of M₀ by 55 to 58%, rule k1 beat lazy+bg in all four completion cells, by 1.2 to 3.1 points of area and 3.1 to 7.3 points of stream rerank. The ratio between static and full on the sample S would be a cheap indicator of this condition, but we have not tested it as a predictor.

## Notes

### The stream on the original SRP keys

[Table E6.10](#table-e610) gives the paired differences of H24. For bge-base, lazy was still 5.8 points below static in stream rerank on SRP keys. For e5-large, lazy was 11.0 points above static in stream rerank, whereas it is below static under learned placement. An exploratory run in round 8, with rule k1 and five seeds, had pointed the same way as round 15: on SRP keys, dual migration beat lazy clearly only for Arctic, by 7.5 points (95% interval 4.3 to 10.8).

## Tables

### Table E6.1

End of the 3,000-arrival stream on code 100k with the native epoch on the original SRP keys, without centering and without a load cap (round 14, H24; Zipf(1), seeds 26 to 35; the seeds, overlays and query streams of the runs on learned placement). Columns as in [Table E4.1](E4_parts_of_dual_migration.md#table-e41), followed by the contacted peers and scored candidates per query. With every record in E₁, the most loaded peer would hold 2,410 records for bge-base and 17,308 for e5-large, against 117 and 111 under learned placement with the cap and a mean of 10; the 1% most loaded peers would hold 32.2 and 78.3% of the records, and 40 and 84% of the peers none. [Table E6.10](#table-e610) gives the six criteria of H24 with their intervals.

| Policy | Held-out final | Stream rerank | Payload | Re-embed. query + bg | Dual at end (%) | Peak records (%) | Peak bytes per object and table | Lost (%) | Flips (%) | Peers | Candidates |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **bge-base** |  |  |  |  |  |  |  |  |  |  |  |
| static | 38.5 | 57.1 | 19.6 | 0 + 0 | 0 | 100 | 509 | 0 |  | 1,186 | 25,998 |
| lazy | 46.2 | 51.2 | 12.3 | 12.3 + 0 | 0 | 100 | 509 | 7.3 | 16.3 | 1,186 | 24,421 |
| lazy+delay | 41.5 | 57.0 | 4.5 | 4.5 + 0 | 8.7 | 108.7 | 570 | 1.3 | 4.5 | 1,186 | 27,078 |
| lazy+keep | 41.1 | 62.0 | 3.3 | 3.3 + 0 | 9.8 | 109.8 | 585 | 0 | 0.9 | 1,186 | 27,567 |
| dual (k1) | 50.1 | 61.1 | 4.1 | 4.1 + 7.8 | 29.9 | 129.9 | 732 | 1.4 | 4.4 | 1,186 | 29,419 |
| dual (drain) | 51.2 | 65.3 | 3.0 | 3.0 + 9.1 | 36.3 | 136.3 | 788 | 0 | 2.3 | 1,186 | 30,521 |
| full | 66.3 | 68.0 | 0 | all at t = 0 | 0 | 100 | 384 | 19.2 | 23.8 | 587 | 22,184 |
| **e5-large** |  |  |  |  |  |  |  |  |  |  |  |
| static | 29.5 | 45.5 | 18.9 | 0 + 0 | 0 | 100 | 512 | 0 |  | 1,193 | 28,057 |
| lazy | 43.4 | 56.5 | 12.2 | 12.2 + 0 | 0 | 100 | 512 | 2.4 | 4.4 | 1,193 | 34,725 |
| lazy+delay | 31.9 | 55.7 | 4.5 | 4.5 + 0 | 8.4 | 108.4 | 598 | 0.4 | 2.3 | 1,193 | 33,003 |
| lazy+keep | 30.8 | 55.0 | 3.2 | 3.2 + 0 | 9.7 | 109.7 | 611 | 0 | 1.9 | 1,193 | 32,663 |
| dual (k1) | 43.4 | 59.4 | 4.0 | 4.0 + 7.7 | 29.4 | 129.4 | 813 | 0.5 | 1.8 | 1,193 | 40,229 |
| dual (drain) | 44.3 | 59.3 | 3.0 | 3.0 + 8.9 | 35.9 | 135.9 | 879 | 0 | 1.6 | 1,193 | 41,438 |
| full | 85.8 | 81.0 | 0 | all at t = 0 | 0 | 100 | 512 | 5.8 | 5.7 | 593 | 67,211 |

### Table E6.2

Migration to completion on the original SRP keys, per cell (round 15, H25; seeds 46 to 55, ten seeds per cell). Paired differences in points with 95% intervals. Area: mean held-out final R@5 over [0,t_end]; stream rerank over [0,t_end). Required: a lower bound above 10 (a, b) and, for e5-large and gte-base, an upper bound below +1 (f); all 32 criteria of these three kinds were met. The last two columns are outside the criteria. Over the twelve cells, drain − full in area was −18.7 to −3.0 (every interval below zero), drain − bg was +7.9 to +16.4, and lazy+bg − rebuild was +17.5 to +38.9.

| Cell |  | drain − rebuild area (a) | drain − static area (b) | drain − lazy+bg area (f) | drain − lazy+bg stream rerank | drain − k1 area |
|---|---|---|---|---|---|---|
| code 20k, bge-base | t_end = 1,500 | +18.09 [16.56, 19.62] | +20.83 [19.00, 22.66] | +0.54 [−0.38, 1.46] | +5.71 [3.32, 8.11] | −0.10 [−0.44, 0.25] |
|  | t_end = 3,000 | +21.22 [19.72, 22.71] | +23.50 [21.75, 25.24] | +0.58 [−0.63, 1.79] | +4.83 [2.47, 7.19] | +1.08 [0.41, 1.75] |
| code 20k, e5-large | t_end = 1,500 | +28.72 [26.12, 31.32] | +34.00 [30.94, 37.05] | −4.34 [−5.20, −3.47] | +0.01 [−2.13, 2.15] | −0.96 [−1.18, −0.75] |
|  | t_end = 3,000 | +32.60 [29.83, 35.37] | +36.99 [33.84, 40.15] | −6.28 [−7.28, −5.28] | −0.56 [−2.55, 1.44] | −1.52 [−1.98, −1.07] |
| code 20k, gte-base | t_end = 1,500 | +21.13 [19.98, 22.28] | +25.04 [23.71, 26.37] | −3.45 [−4.02, −2.87] | −0.53 [−1.05, −0.01] | −0.95 [−1.18, −0.72] |
|  | t_end = 3,000 | +24.24 [23.08, 25.41] | +27.50 [26.18, 28.82] | −4.83 [−5.54, −4.12] | −1.04 [−1.57, −0.51] | −1.22 [−1.62, −0.83] |
| SciFact, bge-base | t_end = 400 | +18.88 [17.06, 20.70] | +22.38 [20.15, 24.61] | +1.38 [0.29, 2.47] | +3.62 [2.39, 4.85] | +0.23 [−0.12, 0.57] |
|  | t_end = 800 | +23.23 [21.01, 25.44] | +24.98 [22.56, 27.39] | +1.32 [0.16, 2.47] | +2.98 [1.83, 4.14] | +1.01 [0.34, 1.68] |
| SciFact, e5-large | t_end = 400 | +26.37 [25.29, 27.45] | +32.05 [30.76, 33.34] | −2.14 [−2.89, −1.38] | −0.72 [−2.10, 0.67] | −0.80 [−0.99, −0.60] |
|  | t_end = 800 | +33.11 [31.69, 34.53] | +35.95 [34.42, 37.48] | −2.35 [−3.02, −1.67] | −0.60 [−1.75, 0.55] | −0.98 [−1.31, −0.64] |
| SciFact, gte-base | t_end = 400 | +22.73 [21.69, 23.76] | +27.62 [26.37, 28.87] | −2.15 [−2.64, −1.65] | −0.28 [−0.94, 0.39] | −0.67 [−0.92, −0.43] |
|  | t_end = 800 | +28.44 [27.21, 29.67] | +30.89 [29.55, 32.24] | −2.22 [−2.80, −1.63] | −0.45 [−1.01, 0.12] | −0.82 [−1.17, −0.47] |

### Table E6.3

Learned placement against the original SRP keys in the runs to completion, per cell (round 15, H25c to H25e; the same seeds, overlays, samples and query streams under both placements). Gain: drain − lazy+bg; the table gives the gain under learned placement minus the gain on SRP keys, in area and in stream rerank, with 95% intervals over the ten paired seeds. Lost: share of the true top-five results of held-out queries that lazy+bg left without a path, averaged over the checkpoints in (0,t_end). Every criterion required a lower bound above 0; all 36 were met. [Table E5.3](E5_migration_to_completion.md#table-e53) gives the gain under learned placement itself.

| Cell |  | Predicted q_f | Gain, learned − SRP area (c) | Gain, learned − SRP stream rerank (d) | Lost (%) SRP | Lost (%) learned | Lost, learned − SRP (e) |
|---|---|---|---|---|---|---|---|
| code 20k, bge-base | t_end = 1,500 | 1.30×10⁻³ | +3.12 [1.78, 4.47] | +4.76 [2.46, 7.07] | 8.54 | 14.00 | +5.46 [3.17, 7.75] |
|  | t_end = 3,000 |  | +4.24 [2.52, 5.97] | +4.55 [2.36, 6.74] | 9.22 | 15.18 | +5.96 [3.52, 8.41] |
| code 20k, e5-large | t_end = 1,500 | 1.60×10⁻² | +7.95 [6.93, 8.97] | +12.31 [9.52, 15.10] | 1.62 | 16.90 | +15.28 [13.23, 17.33] |
|  | t_end = 3,000 |  | +10.75 [9.50, 12.01] | +11.75 [9.10, 14.39] | 1.76 | 18.40 | +16.63 [14.42, 18.84] |
| code 20k, gte-base | t_end = 1,500 | 1.24×10⁻² | +7.08 [6.20, 7.95] | +10.31 [8.35, 12.27] | 1.39 | 13.75 | +12.36 [10.93, 13.79] |
|  | t_end = 3,000 |  | +9.53 [8.41, 10.64] | +9.69 [7.92, 11.46] | 1.51 | 14.99 | +13.48 [11.94, 15.02] |
| SciFact, bge-base | t_end = 400 | 2.18×10⁻³ | +2.75 [1.70, 3.80] | +4.54 [2.72, 6.35] | 9.07 | 15.40 | +6.33 [3.92, 8.73] |
|  | t_end = 800 |  | +3.03 [2.08, 3.99] | +4.20 [2.56, 5.83] | 10.18 | 17.30 | +7.13 [4.46, 9.80] |
| SciFact, e5-large | t_end = 400 | 1.43×10⁻² | +7.26 [6.24, 8.27] | +8.82 [7.18, 10.45] | 3.00 | 20.97 | +17.97 [15.63, 20.31] |
|  | t_end = 800 |  | +7.73 [6.66, 8.81] | +7.94 [6.46, 9.41] | 3.36 | 23.84 | +20.48 [17.88, 23.08] |
| SciFact, gte-base | t_end = 400 | 1.32×10⁻² | +4.71 [4.23, 5.18] | +6.98 [4.91, 9.05] | 2.57 | 14.32 | +11.75 [10.48, 13.02] |
|  | t_end = 800 |  | +5.09 [4.47, 5.71] | +6.42 [4.79, 8.04] | 2.92 | 16.27 | +13.35 [11.83, 14.86] |

### Table E6.4

Every policy in the runs to completion on the original SRP keys, code 20k with t_end = 1,500 (round 15, ten seeds), next to the same cell under learned placement (round 14). Area: mean held-out final R@5 over [0,t_end]. Stream rerank, payload fetches and contacted peers are per arriving query over [0,t_end). Candidates: scored candidates per held-out query, averaged over [0,t_end]. Done: arrival at which the policy has migrated every object, as a share of t_end; it is not given for lazy, which has no background and no deadline. Peak: peak PQ code bytes relative to the initial level. Lost: lost-path share over the checkpoints in (0,t_end); once a policy has dropped E₀, this is the share of results that the legacy index reached and the complete native index does not. With every record on its SRP keys, the 1% most loaded peers hold 25.2, 62.9 and 53.2% of the records (bge-base, e5-large, gte-base), and the most loaded peer holds 879, 4,622 and 3,683 records against a mean of 10. The longer deadline is in the released output of the round.

| Policy | SRP keys · Area | SRP keys · Stream rerank | SRP keys · Payload | SRP keys · Peers | SRP keys · Candi- dates | SRP keys · Done (%) | SRP keys · Peak | SRP keys · Lost (%) | Learned keys · Area | Learned keys · Stream rerank | Learned keys · Candi- dates | Learned keys · Lost (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **bge-base** |  |  |  |  |  |  |  |  |  |  |  |  |
| static | 53.7 | 73.7 | 18.75 | 983 | 9,699 |  | 1.00 | 0 | 53.2 | 72.0 | 9,244 | 0 |
| lazy | 67.8 | 75.5 | 11.69 | 983 | 9,293 |  | 1.00 | 5.9 | 61.9 | 66.1 | 6,568 | 10.1 |
| bg | 65.7 | 78.7 | 15.28 | 983 | 9,415 | 100 | 1.00 | 5.1 | 60.6 | 72.3 | 6,929 | 8.2 |
| lazy+bg | 74.0 | 78.9 | 6.25 | 728 | 9,245 | 48 | 1.00 | 8.5 | 66.0 | 68.3 | 5,684 | 14.0 |
| rebuild | 56.5 | 73.7 | 18.75 | 983 | 9,643 | 100 | 1.69 | 0 | 54.9 | 72.0 | 8,781 | 0 |
| dual (k1) | 74.7 | 82.6 | 3.58 | 837 | 12,039 | 70 | 2.10 | 3.6 | 69.3 | 75.2 | 8,793 | 5.8 |
| dual (drain) | 74.6 | 84.6 | 2.98 | 861 | 12,535 | 75 | 2.38 | 2.4 | 69.7 | 78.8 | 9,376 | 3.8 |
| full | 81.1 | 81.9 | 0 | 493 | 9,138 |  | 1.00 | 11.9 | 70.7 | 70.1 | 4,618 | 19.2 |
| **e5-large** |  |  |  |  |  |  |  |  |  |  |  |  |
| static | 38.6 | 68.5 | 16.43 | 972 | 10,816 |  | 1.00 | 0 | 39.6 | 65.4 | 9,535 | 0 |
| lazy | 62.7 | 81.2 | 10.98 | 972 | 13,962 |  | 1.00 | 1.1 | 49.8 | 59.6 | 6,776 | 11.7 |
| bg | 62.4 | 80.7 | 13.62 | 972 | 14,087 | 100 | 1.00 | 1.0 | 49.3 | 64.8 | 7,055 | 10.1 |
| lazy+bg | 76.9 | 85.7 | 5.94 | 731 | 15,675 | 51 | 1.00 | 1.6 | 57.2 | 62.3 | 5,756 | 16.9 |
| rebuild | 43.9 | 68.5 | 16.43 | 972 | 11,470 | 100 | 1.90 | 0 | 42.2 | 65.4 | 9,039 | 0 |
| dual (k1) | 73.5 | 85.7 | 3.39 | 834 | 17,988 | 72 | 2.47 | 0.7 | 60.4 | 70.7 | 8,916 | 6.9 |
| dual (drain) | 72.6 | 85.7 | 2.83 | 857 | 18,362 | 76 | 2.80 | 0.5 | 60.8 | 74.6 | 9,524 | 4.8 |
| full | 91.3 | 89.9 | 0 | 485 | 17,357 |  | 1.00 | 2.3 | 64.9 | 64.5 | 4,577 | 23.8 |
| **gte-base** |  |  |  |  |  |  |  |  |  |  |  |  |
| static | 54.3 | 77.1 | 18.50 | 979 | 10,828 |  | 1.00 | 0 | 52.9 | 75.5 | 9,673 | 0 |
| lazy | 73.3 | 85.8 | 11.21 | 979 | 13,500 |  | 1.00 | 0.9 | 62.7 | 68.7 | 6,822 | 9.5 |
| bg | 71.4 | 84.8 | 14.90 | 979 | 13,486 | 100 | 1.00 | 0.8 | 61.1 | 74.4 | 7,157 | 8.2 |
| lazy+bg | 82.8 | 88.7 | 6.05 | 731 | 14,818 | 50 | 1.00 | 1.4 | 66.9 | 71.0 | 5,819 | 13.8 |
| rebuild | 58.2 | 77.1 | 18.50 | 979 | 11,360 | 100 | 1.69 | 0 | 54.8 | 75.5 | 9,170 | 0 |
| dual (k1) | 80.3 | 88.3 | 3.54 | 834 | 17,316 | 71 | 2.10 | 0.6 | 70.3 | 77.9 | 9,067 | 5.7 |
| dual (drain) | 79.3 | 88.1 | 2.96 | 858 | 17,714 | 75 | 2.38 | 0.4 | 70.5 | 80.8 | 9,689 | 3.9 |
| full | 93.4 | 91.8 | 0 | 487 | 16,148 |  | 1.00 | 2.0 | 71.9 | 72.9 | 4,643 | 19.5 |

### Table E6.5

As [Table E6.4](#table-e64) for SciFact with t_end = 400. With every record on its SRP keys, the 1% most loaded peers hold 32.9, 59.2 and 50.2% of the records (bge-base, e5-large, gte-base), and the most loaded peer holds 382, 1,145 and 912 records against a mean of 2.6.

| Policy | SRP keys · Area | SRP keys · Stream rerank | SRP keys · Payload | SRP keys · Peers | SRP keys · Candi- dates | SRP keys · Done (%) | SRP keys · Peak | SRP keys · Lost (%) | Learned keys · Area | Learned keys · Stream rerank | Learned keys · Candi- dates | Learned keys · Lost (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **bge-base** |  |  |  |  |  |  |  |  |  |  |  |  |
| static | 53.2 | 74.7 | 18.54 | 974 | 3,122 |  | 1.00 | 0 | 52.8 | 74.1 | 2,959 | 0 |
| lazy | 69.8 | 79.2 | 11.65 | 966 | 2,939 |  | 1.00 | 7.0 | 63.2 | 69.9 | 1,900 | 12.5 |
| bg | 64.9 | 79.3 | 15.56 | 974 | 2,987 | 100 | 1.00 | 4.9 | 60.4 | 74.0 | 2,109 | 8.0 |
| lazy+bg | 74.2 | 80.7 | 6.40 | 707 | 2,908 | 45 | 1.00 | 9.1 | 66.8 | 71.1 | 1,636 | 15.4 |
| rebuild | 56.7 | 74.7 | 18.54 | 974 | 3,088 | 100 | 1.69 | 0 | 55.2 | 74.1 | 2,747 | 0 |
| dual (k1) | 75.4 | 82.9 | 4.80 | 773 | 3,672 | 59 | 1.95 | 5.0 | 69.9 | 75.8 | 2,450 | 8.5 |
| dual (drain) | 75.6 | 84.3 | 4.15 | 801 | 3,892 | 65 | 2.38 | 3.0 | 70.9 | 79.2 | 2,705 | 5.1 |
| full | 81.2 | 82.5 | 0 | 485 | 2,852 |  | 1.00 | 12.0 | 71.6 | 71.8 | 1,256 | 20.4 |
| **e5-large** |  |  |  |  |  |  |  |  |  |  |  |  |
| static | 42.3 | 66.9 | 17.71 | 977 | 3,627 |  | 1.00 | 0 | 42.6 | 64.7 | 3,305 | 0 |
| lazy | 68.7 | 82.1 | 11.66 | 925 | 4,069 |  | 1.00 | 2.2 | 53.9 | 62.9 | 1,991 | 16.2 |
| bg | 62.1 | 77.8 | 15.35 | 977 | 4,025 | 100 | 1.00 | 1.8 | 50.6 | 65.6 | 2,265 | 11.7 |
| lazy+bg | 76.5 | 84.1 | 6.48 | 705 | 4,230 | 45 | 1.00 | 3.0 | 57.4 | 63.4 | 1,689 | 21.0 |
| rebuild | 48.0 | 66.9 | 17.71 | 977 | 3,726 | 100 | 1.90 | 0 | 45.2 | 64.7 | 3,045 | 0 |
| dual (k1) | 75.2 | 83.7 | 4.78 | 777 | 5,038 | 59 | 2.31 | 1.6 | 61.3 | 68.4 | 2,611 | 11.5 |
| dual (drain) | 74.4 | 83.4 | 4.21 | 801 | 5,269 | 64 | 2.80 | 1.0 | 62.5 | 71.5 | 2,899 | 7.1 |
| full | 87.8 | 87.1 | 0 | 488 | 4,420 |  | 1.00 | 4.0 | 62.9 | 63.4 | 1,224 | 28.5 |
| **gte-base** |  |  |  |  |  |  |  |  |  |  |  |  |
| static | 51.1 | 73.0 | 18.65 | 974 | 3,606 |  | 1.00 | 0 | 50.0 | 72.5 | 3,306 | 0 |
| lazy | 73.4 | 83.7 | 11.64 | 974 | 3,937 |  | 1.00 | 1.9 | 63.4 | 70.0 | 2,015 | 10.9 |
| bg | 68.1 | 82.4 | 15.49 | 974 | 3,916 | 100 | 1.00 | 1.4 | 60.9 | 73.1 | 2,271 | 7.5 |
| lazy+bg | 80.9 | 86.3 | 6.39 | 706 | 4,075 | 45 | 1.00 | 2.6 | 68.0 | 71.6 | 1,696 | 14.3 |
| rebuild | 56.0 | 73.0 | 18.65 | 974 | 3,684 | 100 | 1.69 | 0 | 53.0 | 72.5 | 3,047 | 0 |
| dual (k1) | 79.4 | 86.2 | 4.74 | 775 | 4,891 | 59 | 1.94 | 1.4 | 70.1 | 76.0 | 2,616 | 7.5 |
| dual (drain) | 78.7 | 86.1 | 4.14 | 801 | 5,125 | 65 | 2.38 | 0.9 | 70.6 | 78.3 | 2,906 | 4.9 |
| full | 90.3 | 89.7 | 0 | 483 | 4,225 |  | 1.00 | 3.5 | 73.7 | 72.9 | 1,235 | 19.5 |

### Table E6.6

drain against lazy+bg at equal progress (round 15, exploratory). Held-out final R@5 is interpolated linearly between checkpoints at the points where 30, 50 and 70% of the objects have an E₁ record (the sample S included); the table gives drain − lazy+bg, paired by seed, with 95% intervals on SRP keys and means under learned placement. This comparison removes the difference in migration speed between the two policies. The last column gives the held-out final R@5 of drain when 85% of the objects are migrated minus that of the complete index (full), on SRP keys and under learned placement (post hoc). The last four pairs of rows are the models for which the placement rule selects learned placement.

| Cell |  | drain − lazy+bg, SRP keys · 30% migrated | drain − lazy+bg, SRP keys · 50% migrated | drain − lazy+bg, SRP keys · 70% migrated | drain − lazy+bg learned keys · 30 / 50 / 70% | drain − full at 85% · SRP / learned |
|---|---|---|---|---|---|---|
| code 20k, bge-base | t_end = 1,500 | +1.77 [1.10, 2.43] | +4.06 [3.20, 4.93] | +6.28 [4.80, 7.77] | +3.2 / +6.6 / +10.3 | +2.9 / +9.7 |
|  | t_end = 3,000 | +1.88 [1.10, 2.66] | +3.96 [2.93, 4.99] | +6.04 [4.51, 7.58] | +3.2 / +6.8 / +10.3 | +2.7 / +9.8 |
| code 20k, e5-large | t_end = 1,500 | +0.62 [0.11, 1.13] | +0.77 [−0.60, 2.14] | +1.75 [−0.14, 3.64] | +3.6 / +7.8 / +12.5 | −8.0 / +9.8 |
|  | t_end = 3,000 | +0.34 [−0.68, 1.36] | +0.54 [−0.70, 1.77] | +2.57 [0.23, 4.91] | +3.4 / +7.4 / +13.5 | −8.0 / +10.3 |
| code 20k, gte-base | t_end = 1,500 | +0.17 [−0.41, 0.75] | +0.80 [0.12, 1.49] | +0.98 [0.03, 1.93] | +2.4 / +6.6 / +10.5 | −7.0 / +9.8 |
|  | t_end = 3,000 | +0.34 [−0.14, 0.82] | +0.13 [−0.30, 0.56] | +0.31 [−0.91, 1.52] | +2.7 / +5.9 / +10.2 | −7.1 / +9.8 |
| SciFact, bge-base | t_end = 400 | +1.91 [1.28, 2.54] | +4.09 [2.68, 5.50] | +6.52 [4.32, 8.72] | +3.1 / +6.8 / +10.9 | +2.5 / +9.7 |
|  | t_end = 800 | +2.02 [1.43, 2.61] | +4.63 [3.14, 6.11] | +6.46 [4.32, 8.59] | +3.1 / +7.6 / +11.1 | +2.8 / +10.2 |
| SciFact, e5-large | t_end = 400 | +0.43 [−0.06, 0.92] | +0.80 [−0.19, 1.78] | +1.36 [0.07, 2.64] | +3.1 / +7.9 / +13.4 | −6.8 / +12.4 |
|  | t_end = 800 | +0.39 [−0.06, 0.85] | +0.79 [−0.29, 1.86] | +1.83 [0.45, 3.21] | +3.3 / +8.7 / +13.8 | −7.0 / +12.4 |
| SciFact, gte-base | t_end = 400 | +0.62 [0.07, 1.16] | +0.33 [−0.35, 1.00] | +0.63 [−0.10, 1.37] | +2.4 / +4.8 / +8.1 | −6.7 / +5.9 |
|  | t_end = 800 | +0.35 [−0.24, 0.94] | +0.90 [0.02, 1.78] | +1.42 [0.21, 2.62] | +2.4 / +5.5 / +8.9 | −6.4 / +6.4 |
| code 20k, Arctic | t_end = 1,500 | +4.94 [3.91, 5.97] | +10.52 [9.29, 11.76] | +16.43 [14.90, 17.97] | +4.0 / +8.5 / +13.1 | +17.7 / +11.9 |
|  | t_end = 3,000 | +5.29 [4.28, 6.31] | +10.82 [9.04, 12.61] | +16.81 [14.72, 18.91] | +4.2 / +9.2 / +13.9 | +18.3 / +12.2 |
| code 20k, MiniLM | t_end = 1,500 | +3.92 [3.07, 4.76] | +9.21 [7.92, 10.51] | +14.17 [12.64, 15.70] | +3.2 / +6.1 / +9.4 | +13.0 / +5.3 |
|  | t_end = 3,000 | +4.14 [3.38, 4.90] | +9.24 [7.99, 10.48] | +14.77 [12.86, 16.67] | +3.2 / +6.2 / +9.7 | +13.4 / +5.7 |
| SciFact, Arctic | t_end = 400 | +5.84 [5.01, 6.66] | +13.14 [11.76, 14.52] | +20.93 [19.25, 22.61] | +4.3 / +10.6 / +16.7 | +25.4 / +17.9 |
|  | t_end = 800 | +5.61 [4.77, 6.46] | +13.61 [12.16, 15.07] | +21.50 [19.35, 23.65] | +4.5 / +10.6 / +16.8 | +25.6 / +18.1 |
| SciFact, MiniLM | t_end = 400 | +3.22 [2.47, 3.98] | +8.03 [6.91, 9.15] | +14.11 [13.06, 15.17] | +2.7 / +5.9 / +10.3 | +13.4 / +6.4 |
|  | t_end = 800 | +3.35 [2.81, 3.90] | +8.41 [7.44, 9.38] | +14.17 [12.11, 16.23] | +2.5 / +6.3 / +10.4 | +14.2 / +6.8 |

### Table E6.7

drain with a background twice as fast against lazy+bg (round 15, exploratory). drain runs with the background rate of the shorter deadline and lazy+bg with that of the longer one, and both are evaluated over the longer deadline ([0,3,000] on code 20k, [0,800] on SciFact). Paired differences drain − lazy+bg in points with 95% intervals. Done: arrival of completion as a share of the longer deadline, drain / lazy+bg.

| Pair | SRP keys · Area | SRP keys · Stream rerank | SRP keys · Done (%) | Learned keys · Area | Learned keys · Stream rerank | Learned keys · Done (%) |
|---|---|---|---|---|---|---|
| code 20k, bge-base | +1.17 [0.80, 1.54] | +3.37 [2.31, 4.44] | 38 / 33 | +2.50 [2.03, 2.97] | +5.58 [4.15, 7.01] | 38 / 32 |
| code 20k, e5-large | +0.10 [−0.45, 0.64] | +0.69 [−0.42, 1.79] | 38 / 35 | +2.97 [2.71, 3.23] | +6.60 [5.29, 7.90] | 38 / 33 |
| code 20k, gte-base | −0.27 [−0.54, −0.01] | +0.18 [−0.11, 0.47] | 38 / 34 | +2.42 [2.01, 2.83] | +5.25 [4.24, 6.25] | 38 / 33 |
| SciFact, bge-base | +1.53 [1.06, 2.00] | +2.07 [1.51, 2.63] | 32 / 30 | +2.65 [2.33, 2.96] | +4.26 [3.47, 5.05] | 32 / 29 |
| SciFact, e5-large | +0.45 [0.16, 0.75] | −0.01 [−0.73, 0.72] | 32 / 29 | +3.25 [2.96, 3.53] | +4.15 [3.05, 5.24] | 32 / 28 |
| SciFact, gte-base | +0.29 [0.03, 0.55] | +0.34 [−0.08, 0.75] | 32 / 30 | +2.08 [1.85, 2.31] | +3.63 [2.60, 4.66] | 32 / 29 |
| code 20k, Arctic | +3.94 [3.36, 4.53] | +8.78 [6.54, 11.01] | 38 / 30 | +2.86 [2.51, 3.21] | +7.51 [6.80, 8.22] | 38 / 30 |
| code 20k, MiniLM | +3.27 [2.90, 3.65] | +7.87 [6.16, 9.58] | 38 / 31 | +1.79 [1.49, 2.10] | +4.96 [3.51, 6.41] | 38 / 31 |
| SciFact, Arctic | +5.23 [4.82, 5.65] | +8.73 [7.51, 9.96] | 32 / 28 | +4.02 [3.54, 4.51] | +6.39 [5.28, 7.49] | 32 / 28 |
| SciFact, MiniLM | +3.37 [2.98, 3.76] | +5.52 [4.21, 6.83] | 31 / 28 | +2.42 [2.09, 2.75] | +3.73 [3.16, 4.29] | 32 / 28 |

### Table E6.8

Migration to completion on the original SRP keys for Arctic and MiniLM, for which the placement rule selects learned placement (round 15, exploratory, no criteria; ten seeds per cell). Paired differences in points with 95% intervals; gain is drain − lazy+bg, and lost is the lost-path share of lazy+bg over (0,t_end). For these models the gain is larger on SRP keys than under learned placement, and lazy+bg cuts off more results on SRP keys. Over the eight cells on SRP keys, drain − rebuild in area was +14.0 to +23.0 and drain − k1 in area was +1.0 to +5.8, with every interval above zero.

| Cell |  | Gain on SRP area | Gain on SRP stream rerank | Gain, learned − SRP area | Gain, learned − SRP stream rerank | Lost (%) SRP / learned |
|---|---|---|---|---|---|---|
| code 20k, Arctic | t_end = 1,500 | +6.92 [5.59, 8.26] | +16.91 [12.36, 21.46] | −2.73 [−3.82, −1.64] | −2.72 [−6.89, 1.45] | 23.7 / 19.9 |
|  | t_end = 3,000 | +9.11 [7.13, 11.09] | +15.65 [11.34, 19.96] | −3.65 [−5.17, −2.14] | −2.53 [−6.59, 1.53] | 25.7 / 21.5 |
| code 20k, MiniLM | t_end = 1,500 | +5.06 [4.13, 5.99] | +14.71 [11.01, 18.41] | −3.63 [−4.76, −2.50] | −6.27 [−10.79, −1.75] | 17.2 / 12.3 |
|  | t_end = 3,000 | +6.51 [5.42, 7.60] | +13.23 [9.64, 16.82] | −4.83 [−6.33, −3.33] | −6.09 [−10.20, −1.99] | 18.6 / 13.3 |
| SciFact, Arctic | t_end = 400 | +10.10 [9.17, 11.02] | +17.45 [14.96, 19.93] | −2.81 [−3.70, −1.92] | −4.96 [−6.64, −3.27] | 30.9 / 25.6 |
|  | t_end = 800 | +10.62 [9.66, 11.58] | +15.30 [13.22, 17.37] | −3.14 [−4.02, −2.26] | −4.45 [−6.04, −2.85] | 34.8 / 28.9 |
| SciFact, MiniLM | t_end = 400 | +5.54 [4.72, 6.36] | +10.65 [8.04, 13.26] | −2.48 [−3.36, −1.60] | −3.75 [−5.98, −1.51] | 22.6 / 18.0 |
|  | t_end = 800 | +5.57 [4.23, 6.90] | +8.93 [6.96, 10.90] | −2.72 [−3.72, −1.72] | −3.04 [−4.63, −1.44] | 25.7 / 20.4 |

### Table E6.9

The ten corpus and model pairs of round 15 ordered by the predicted query bucket fraction (means over two deadlines and ten seeds; the data of Fig. 4 of the paper). Scored: share of the corpus that the complete index scores per held-out query. Lost: lost-path share of lazy+bg over (0,t_end). Gain: drain − lazy+bg in points. Rule: the placement that the prespecified rule on q_f selects. Spearman rank correlations with the predicted q_f over the ten pairs (exploratory): gain on SRP keys, −0.89 in area and −0.83 in stream rerank; lost paths on SRP keys, −0.82; gain under learned placement, +0.03 and −0.08; lost paths under learned placement, +0.04 (the three values for learned placement are post hoc). Over the 20 cells without averaging, the correlations on SRP keys are −0.86, −0.85 and −0.82.

| Pair | Predicted q_f | Rule | Scored (%) · SRP | Scored (%) · learned | Lost (%) · SRP | Lost (%) · learned | Gain, area · SRP | Gain, area · learned | Gain, stream rerank · SRP | Gain, stream rerank · learned |
|---|---|---|---|---|---|---|---|---|---|---|
| code 20k, MiniLM | 5.00×10⁻⁵ | learned | 24.4 | 22.8 | 17.9 | 12.8 | +5.79 | +1.56 | +13.97 | +7.79 |
| SciFact, Arctic | 6.20×10⁻⁵ | learned | 26.2 | 23.5 | 32.8 | 27.3 | +10.36 | +7.38 | +16.37 | +11.67 |
| SciFact, MiniLM | 8.24×10⁻⁵ | learned | 25.5 | 23.4 | 24.1 | 19.2 | +5.55 | +2.95 | +9.79 | +6.40 |
| code 20k, Arctic | 1.51×10⁻⁴ | learned | 30.9 | 22.7 | 24.7 | 20.7 | +8.02 | +4.82 | +16.28 | +13.66 |
| code 20k, bge-base | 1.30×10⁻³ | SRP | 45.7 | 23.1 | 8.9 | 14.6 | +0.56 | +4.25 | +5.27 | +9.93 |
| SciFact, bge-base | 2.18×10⁻³ | SRP | 55.0 | 24.2 | 9.6 | 16.3 | +1.35 | +4.24 | +3.30 | +7.67 |
| code 20k, gte-base | 1.24×10⁻² | SRP | 80.7 | 23.2 | 1.5 | 14.4 | −4.14 | +4.16 | −0.79 | +9.22 |
| SciFact, gte-base | 1.32×10⁻² | SRP | 81.5 | 23.8 | 2.7 | 15.3 | −2.18 | +2.72 | −0.36 | +6.34 |
| SciFact, e5-large | 1.43×10⁻² | SRP | 85.3 | 23.6 | 3.2 | 22.4 | −2.24 | +5.25 | −0.66 | +7.72 |
| code 20k, e5-large | 1.60×10⁻² | SRP | 86.8 | 22.9 | 1.7 | 17.6 | −5.31 | +4.04 | −0.27 | +11.76 |

### Table E6.10

Dual migration on the original SRP keys (H24, round 14; code 100k, Zipf(1), 3,000 arrivals, seeds 26 to 35). Learned: `itq_q+cap16` with the same seeds, overlays and query streams. Differences are in points with 95% intervals. Lost paths are shares of the true top-five results of held-out queries at the end of the stream. The criteria required a lower bound above −1 (H24a, H24b), above 5 (H24c) and above 0 (H24d to H24f).

| Quantity | bge-base | e5-large |
|---|---|---|
| Lost paths under lazy (%), SRP / learned | 7.3 / 11.3 | 2.4 / 14.8 |
| learned − SRP (H24f) | +3.96 [2.23, 5.69] | +12.42 [9.94, 14.90] |
| drain − lazy on SRP, held-out final (H24a) | +4.92 [2.65, 7.19] | +0.96 [−0.88, 2.80] |
| drain − lazy on SRP, stream rerank (H24b) | +14.12 [9.85, 18.39] | +2.74 [−0.72, 6.20] |
| drain − lazy, learned, held-out final | +7.76 [5.73, 9.79] | +8.04 [5.50, 10.58] |
| drain − lazy, learned, stream rerank | +20.95 [18.44, 23.45] | +20.28 [16.41, 24.14] |
| learned − SRP, held-out final (H24e) | +2.84 [0.77, 4.91] | +7.08 [5.16, 9.00] |
| learned − SRP, stream rerank (H24d) | +6.83 [2.44, 11.21] | +17.54 [13.24, 21.84] |
| drain − static on SRP, held-out final (H24c) | +12.64 [11.12, 14.16] | +14.86 [13.23, 16.49] |
| Held-out final on SRP: static / lazy / drain / full | 38.5 / 46.2 / 51.2 / 66.3 | 29.5 / 43.4 / 44.3 / 85.8 |
| Stream rerank on SRP: static / lazy / drain / full | 57.1 / 51.2 / 65.3 / 68.0 | 45.5 / 56.5 / 59.3 / 81.0 |
| Candidates per query on SRP: drain / full | 30,521 / 22,184 | 41,438 / 67,211 |
