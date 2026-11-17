# E5. Migration to completion and retirement rules

Here the migration runs until every object has a record in the new epoch E₁. The experiment compares drain, which retires no legacy record before E₀ is dropped, with a blue-green rebuild, with lazy+bg, with static and with the idealized full, and it measures what earlier retirement rules save in storage and cost in recall.

| | |
|---|---|
| In the paper | Results, "Draining the old epoch outperforms rebuilding, and earlier retirement trades quality for storage"; Fig. 3 |
| Rounds and hypotheses | 10 (exploratory), 11 (H12), 12 (H18), 14 (H22) |
| Analysis scripts | `python3 evo/analyze_r10.py`, `python3 evo/analyze_r11.py`, `python3 evo/analyze_r12.py`, `python3 evo/analyze_r14.py` |

## Results

A real migration has to end, so we also ran it until every object had an E₁ record, on code 20k and SciFact with two deadlines each and five target models under learned placement: 20 cells of ten seeds each, of which the twelve with the original models were tested with prespecified criteria. In round 11 each policy dropped E₀ as soon as it had migrated everything. In round 12 all policies dropped E₀ exactly at the deadline t_end, so that the comparison between retirement rules does not depend on when the drop happens. Round 14 repeated the setting of round 11 on new seeds.

Over the 20 cells, drain outperformed the simpler ways of migrating. These comparisons were exploratory in round 11, so round 14 repeated them on new seeds with thresholds fixed in advance (H22; [Table E5.3](#table-e53)). All 100 criteria were met, and the two rounds gave nearly the same ranges; we give those of round 14 first and those of round 11 in parentheses. The area of drain was 14.7 to 26.6 points (14.5 to 26.3) higher than that of the blue-green rebuild; the criterion required the lower end of every interval to exceed 10 points, and the smallest was 13.7. Against lazy+bg the area was 1.4 to 7.5 points (1.6 to 7.9) higher and the stream rerank 5.9 to 14.2 points (6.2 to 14.4) higher. Against static and bg the margins were 16.5 to 29.1 (16.3 to 28.9) and 9.0 to 16.2 points (8.7 to 16.0), and against the idealized full the area ranged from 6.8 points lower to 5.3 points higher (6.6 lower to 5.6 higher). Round 14 is a replication on the same corpora and models: it shows that these margins do not depend on the seeds and does not extend them to other data. The part on when dual migration helps repeats the runs on the original SRP keys, where the comparison with lazy+bg comes out differently. The earlier prespecified comparison, between rule k1 and lazy+bg, met its criterion in all twelve original-model cells (H12c) and in seven of the eight cells with new models (H16e). In a further check in round 10 (post hoc), rebuild received a background twice as fast as that of dual migration, and dual migration with rule k1 still came out 6.9 to 8.9 points ahead in all six pairs and for every seed. The cost of drain is storage: counted in PQ code bytes, its peak was 1.72 to 2.80 times the initial level, against 1.36 to 1.90 times for rebuild and no increase for lazy+bg, and it exceeded the peak of rebuild in all 20 cells of both rounds. lazy+bg also finished first, at 28 to 50% of t_end, against 52 to 77% for drain.

Retiring earlier recovers part of this storage. Fig. 3 of the paper shows what it costs when all rules drop E₀ at the same time, and [Table E5.4](#table-e54) gives one cell in full: every rule that retired before the drop lost quality. With one sighting (k1), area fell by 0.67 to 6.78 points and stream rerank by 1.39 to 9.66 points relative to drain, with intervals below zero in 19 of 20 cells for both measures, while peak bytes fell by 11.7 to 26.0%. One sighting had already failed the prespecified margin of one point against drain in all twelve cells of round 11 (H12a). For round 12 we therefore required sightings by two distinct queries and reset the count whenever a query found the object through E₀ but not through E₁ (uv2). This stronger rule met the margin in only one of the twelve prespecified cells (H18a), where it saved 1.98% of peak bytes; it saved 1.98 to 6.33% in all twelve cells (H18b) and exceeded k1 in stream rerank by 2.96 to 8.12 points (H18c), mainly because it retired three to six times fewer objects. Across all 20 cells and seven rules, only two cases stayed within the margin while saving at least 5% of peak bytes, both with rule v2 on MiniLM. The frontier thus runs from uv3, which saved 0.3 to 2.0% at a cost of at most 0.89 points of area and 0.85 points of rerank, to k1. A cap on the number of dual objects also bounds storage, but in an exploratory test it retired 47 to 58% of the objects outside S without any sighting (see the notes below).

To see which kind of evidence helps, we compared each rule with the curve through drain, k3, k2 and k1 at the same byte saving (post hoc, over the 20 cells). The veto helped only the queries that produced it: under rule v2, stream rerank lay above the curve in all 20 cells, by 1.17 points on average (0.22 to 2.38), but held-out recall did not (on average +0.03, positive in 12 of 20 cells). Counting distinct queries mostly meant retiring fewer objects, and at its own saving u2 lay below the curve in stream rerank in 18 of 20 cells. On held-out queries every sighting rule stayed within 0.31 points of the curve, so the quality for unseen queries depended on how many objects were retired rather than on which ones. We therefore use drain as the main configuration and treat the retirement rules as a storage setting whose costs are those of Fig. 3 of the paper ([Table E5.1](#table-e51), [Table E5.2](#table-e52) and [Table E5.4](#table-e54) and the notes below).

## Notes

### Retirement rules

[Table E5.4](#table-e54) gives one cell of round 12 with every retirement rule, [Table E5.1](#table-e51) one cell of round 11 with the ranges over all cells, and [Table E5.2](#table-e52) the twelve cells of H18. A cap on the number of dual objects is another way to bound storage. In an exploratory test in round 10, a cap of 25% of the corpus held the peak at 125% of the initial record count and cost 0.8 to 2.3 points of area relative to rule k1. The price was that 47 to 58% of the objects outside S were retired without any sighting, and stream rerank fell below that of static in 8 of 12 cells. Vetoes were frequent. In the cell of [Table E5.4](#table-e54), an arriving query under uv2 met on average 45 dual objects that the legacy side returned and the native side did not, while about 17 dual objects per query were seen through E₁.

## Tables

### Table E5.1

Migration to completion with E₀ dropped when each policy completes (round 11; code 20k, bge-base, t_end = 1,500, 10 seeds). Area: mean held-out final R@5 over [0,t_end]; stream rerank over [0,t_end); payload, background re-embeddings and peers per arrival; bytes: peak PQ code bytes per object and table without metadata; retired: objects outside S whose E₀ record was retired before the drop. Over all 20 cells (five models, two corpora, two deadlines), relative to rule k1: rebuild −24.4 to −13.9 points of area, lazy+bg −5.9 to +0.04, the variant without attached code −6.7 to −2.9, k2 −0.05 to +1.4, k3 −0.03 to +3.3 and drain +0.25 to +4.3; peak bytes relative to the initial level: rebuild 1.36 to 1.90, k1 1.28 to 2.47, drain 1.72 to 2.80.

| Policy | Completes at | Area | Stream rerank | Payload | Background re-embed. | Peers | Peak storage (% records) | Peak bytes per object and table | Retired (%) |
|---|---|---|---|---|---|---|---|---|---|
| static | never | 52.9 | 75.2 | 19.02 | 0 | 972 | 100 | 499 |  |
| rebuild | 1,500 | 54.8 | 75.2 | 19.02 | 12.00 | 972 | 190 | 845 |  |
| bg | 1,500 | 61.6 | 74.5 | 15.76 | 12.00 | 972 | 100 | 499 | 100 |
| lazy | 1,799 | 62.4 | 68.4 | 11.80 | 0 | 972 | 100 | 499 | 100 |
| lazy+bg | 715 | 67.0 | 70.6 | 6.29 | 5.71 | 720 | 100 | 499 | 100 |
| dual, no attached code | 1,246 | 66.0 | 76.6 | 12.45 | 9.96 | 891 | 173.0 | 758 | 18.8 |
| dual, k1 | 1,050 | 70.2 | 77.4 | 3.60 | 8.40 | 828 | 173.9 | 1,046 | 17.9 |
| dual, k2 | 1,078 | 70.4 | 78.8 | 3.38 | 8.62 | 837 | 180.5 | 1,105 | 10.6 |
| dual, k3 | 1,092 | 70.6 | 79.9 | 3.26 | 8.74 | 841 | 183.3 | 1,131 | 7.4 |
| dual, drain | 1,126 | 70.5 | 81.5 | 3.00 | 9.00 | 852 | 190 | 1,190 | 0 |
| full | 0 | 72.0 | 72.1 | 0 | 0 | 490 | 100 | 384 |  |

### Table E5.2

Rule uv2 against drain and k1 with E₀ dropped at t_end for all policies (round 12, H18, 10 seeds per cell; differences with 95% intervals). Criteria: (a) both lower bounds against drain above −1; (b) peak bytes below drain; (c) stream rerank above k1.

| Cell |  | uv2 − drain, area | uv2 − drain, stream rerank | Bytes saved | uv2 − k1, stream rerank | a / b / c |
|---|---|---|---|---|---|---|
| code 20k, bge-base | t_end = 1,500 | −0.22 [−0.42, −0.02] | −0.48 [−0.93, −0.04] | 1.98% | +3.03 [1.98, 4.08] | yes / yes / yes |
|  | t_end = 3,000 | −0.10 [−0.32, +0.11] | −0.63 [−1.13, −0.12] | 2.66% | +3.94 [2.64, 5.24] | no / yes / yes |
| code 20k, e5-large | t_end = 1,500 | −0.23 [−0.59, +0.12] | −1.49 [−3.14, +0.16] | 1.98% | +3.97 [2.32, 5.62] | no / yes / yes |
|  | t_end = 3,000 | −0.07 [−0.44, +0.29] | −1.75 [−3.41, −0.08] | 2.65% | +5.12 [3.07, 7.16] | no / yes / yes |
| code 20k, Arctic | t_end = 1,500 | −0.18 [−0.41, +0.05] | −0.61 [−1.11, −0.11] | 2.05% | +5.22 [2.18, 8.25] | no / yes / yes |
|  | t_end = 3,000 | −0.23 [−0.52, +0.05] | −0.95 [−1.57, −0.33] | 2.78% | +5.82 [2.99, 8.66] | no / yes / yes |
| SciFact, bge-base | t_end = 400 | −0.60 [−0.85, −0.35] | −0.89 [−1.42, −0.35] | 4.42% | +4.33 [2.38, 6.29] | no / yes / yes |
|  | t_end = 800 | −1.38 [−1.78, −0.97] | −1.68 [−2.46, −0.90] | 6.24% | +4.89 [2.56, 7.22] | no / yes / yes |
| SciFact, e5-large | t_end = 400 | −0.98 [−1.38, −0.59] | −0.74 [−2.02, +0.53] | 4.37% | +2.96 [0.24, 5.68] | no / yes / yes |
|  | t_end = 800 | −1.83 [−2.27, −1.39] | −1.25 [−2.59, +0.10] | 6.19% | +4.15 [1.50, 6.80] | no / yes / yes |
| SciFact, Arctic | t_end = 400 | −1.21 [−1.59, −0.84] | −0.46 [−1.58, +0.66] | 4.44% | +6.03 [4.61, 7.45] | no / yes / yes |
|  | t_end = 800 | −2.31 [−2.79, −1.83] | −1.54 [−2.74, −0.34] | 6.33% | +8.12 [6.66, 9.59] | no / yes / yes |

### Table E5.3

Replication of the comparisons of drain in the runs to completion (round 14, H22; seeds 46 to 55, ten seeds per cell; E₀ dropped when each policy completes, as in round 11). Paired differences in points with 95% intervals. Area: mean held-out final R@5 over [0,t_end]; stream rerank over [0,t_end). Required lower bounds: above 10 (a, d), above 0 (b, c) and above 5 (e); all 100 criteria were met. Outside the criteria, over the 20 cells: drain − full, area, −6.8 to +5.3; drain − k1, area +0.3 to +4.2 (lower bound above 0 in 17 cells) and stream rerank +2.4 to +5.9 (20 cells); drain − rebuild, stream rerank, +4.3 to +16.9 (20 cells).

| Cell |  | drain − rebuild area (a) | drain − lazy+bg area (b) | drain − lazy+bg stream rerank (c) | drain − static area (d) | drain − bg area (e) |
|---|---|---|---|---|---|---|
| code 20k, bge-base | t_end = 1,500 | +14.75 [13.70, 15.79] | +3.67 [2.68, 4.66] | +10.47 [7.46, 13.49] | +16.50 [15.24, 17.75] | +9.04 [8.55, 9.53] |
|  | t_end = 3,000 | +17.87 [16.79, 18.95] | +4.83 [3.51, 6.14] | +9.38 [6.56, 12.21] | +19.33 [18.07, 20.58] | +11.78 [11.27, 12.30] |
| code 20k, e5-large | t_end = 1,500 | +18.67 [16.84, 20.50] | +3.61 [2.80, 4.43] | +12.32 [9.67, 14.97] | +21.20 [18.97, 23.43] | +11.54 [10.48, 12.60] |
|  | t_end = 3,000 | +22.64 [20.74, 24.53] | +4.48 [3.35, 5.61] | +11.19 [8.53, 13.86] | +24.75 [22.51, 26.98] | +15.11 [13.89, 16.33] |
| code 20k, Arctic | t_end = 1,500 | +19.32 [18.57, 20.08] | +4.19 [3.45, 4.93] | +14.19 [12.87, 15.52] | +21.66 [20.71, 22.61] | +11.18 [10.59, 11.77] |
|  | t_end = 3,000 | +23.18 [22.52, 23.83] | +5.46 [4.39, 6.52] | +13.12 [11.89, 14.35] | +25.13 [24.32, 25.93] | +14.63 [13.92, 15.35] |
| code 20k, gte-base | t_end = 1,500 | +15.74 [14.38, 17.10] | +3.63 [2.78, 4.47] | +9.78 [7.81, 11.74] | +17.64 [16.01, 19.27] | +9.46 [8.51, 10.40] |
|  | t_end = 3,000 | +19.01 [17.61, 20.41] | +4.69 [3.65, 5.73] | +8.65 [6.79, 10.52] | +20.60 [18.96, 22.23] | +12.28 [11.40, 13.16] |
| code 20k, MiniLM | t_end = 1,500 | +22.56 [21.56, 23.57] | +1.43 [0.73, 2.14] | +8.44 [5.36, 11.51] | +25.83 [24.71, 26.96] | +11.32 [10.72, 11.92] |
|  | t_end = 3,000 | +26.42 [25.43, 27.41] | +1.68 [0.98, 2.38] | +7.14 [4.40, 9.88] | +29.15 [28.05, 30.24] | +14.64 [14.03, 15.26] |
| SciFact, bge-base | t_end = 400 | +15.74 [14.67, 16.81] | +4.13 [3.39, 4.88] | +8.15 [6.44, 9.87] | +18.08 [16.80, 19.37] | +10.51 [10.01, 11.02] |
|  | t_end = 800 | +18.95 [17.65, 20.25] | +4.35 [3.54, 5.16] | +7.18 [5.78, 8.57] | +20.12 [18.71, 21.52] | +12.56 [11.96, 13.16] |
| SciFact, e5-large | t_end = 400 | +17.36 [15.99, 18.72] | +5.12 [4.47, 5.77] | +8.10 [5.80, 10.40] | +19.89 [18.21, 21.56] | +11.92 [11.03, 12.81] |
|  | t_end = 800 | +20.95 [19.24, 22.65] | +5.39 [4.69, 6.08] | +7.33 [5.35, 9.32] | +22.21 [20.35, 24.07] | +14.33 [13.33, 15.33] |
| SciFact, Arctic | t_end = 400 | +16.75 [15.24, 18.27] | +7.28 [6.40, 8.17] | +12.49 [10.16, 14.82] | +18.62 [16.79, 20.45] | +11.91 [11.07, 12.74] |
|  | t_end = 800 | +19.28 [17.54, 21.02] | +7.48 [6.56, 8.39] | +10.85 [8.93, 12.77] | +20.21 [18.30, 22.12] | +13.44 [12.54, 14.34] |
| SciFact, gte-base | t_end = 400 | +17.65 [16.83, 18.46] | +2.56 [2.16, 2.96] | +6.71 [4.63, 8.78] | +20.61 [19.67, 21.55] | +9.68 [9.09, 10.26] |
|  | t_end = 800 | +21.45 [20.48, 22.43] | +2.87 [2.34, 3.40] | +5.97 [4.23, 7.71] | +22.93 [21.89, 23.97] | +12.16 [11.37, 12.96] |
| SciFact, MiniLM | t_end = 400 | +21.83 [20.61, 23.06] | +3.06 [2.17, 3.95] | +6.90 [5.84, 7.97] | +25.66 [24.14, 27.18] | +13.36 [12.44, 14.28] |
|  | t_end = 800 | +26.65 [25.07, 28.23] | +2.85 [1.94, 3.76] | +5.89 [4.89, 6.90] | +28.56 [26.83, 30.28] | +16.22 [15.19, 17.26] |

### Table E5.4

Migration to completion on code 20k with bge-base and t_end = 1,500 (round 12, ten seeds); every policy with background migration drops E₀ at t_end. Retired: objects outside S retired before the drop. Saving: reduction of peak bytes relative to drain. Peak bytes: PQ code bytes per object and table without metadata; with 64 bytes of metadata per record, drain, k1 and static peak at 1,312, 1,159 and 563 bytes. Lost and Worse: lost-path share and share of held-out queries worse than under drain, averaged over (0,t_end). Payload fetches and background re-embeddings are per arrival over [0,t_end). Policies that read both epochs contact 972 peers per query, against 486 for full and an average of 719 for lazy+bg, which completes early.

| Policy | Retired (%) | Peak bytes per object and table | Saving (%) | Area | Stream rerank | Lost (%) | Worse (%) | Payload fetches | Background re-embed. |
|---|---|---|---|---|---|---|---|---|---|
| static |  | 499 |  | 53.1 | 72.1 |  |  | 19.00 | 0 |
| full |  | 384 |  | 69.2 | 69.2 | 21.0 |  | 0 | 0 |
| lazy+bg | 100 | 499 | 58.1 | 65.1 | 67.7 | 15.1 | 36.0 | 6.26 | 5.74 |
| k1 | 20.1 | 1,048 | 12.0 | 72.0 | 78.1 | 2.76 | 10.4 | 3.58 | 8.42 |
| k2 | 13.1 | 1,105 | 7.1 | 72.5 | 80.0 | 1.48 | 6.2 | 3.36 | 8.64 |
| k3 | 9.6 | 1,132 | 4.9 | 72.7 | 80.5 | 1.03 | 4.4 | 3.25 | 8.75 |
| v2 | 11.5 | 1,115 | 6.3 | 72.6 | 80.8 | 1.21 | 5.2 | 3.30 | 8.70 |
| u2 | 3.9 | 1,162 | 2.4 | 72.9 | 80.5 | 0.65 | 2.6 | 3.15 | 8.85 |
| uv2 | 3.3 | 1,167 | 2.0 | 73.0 | 81.1 | 0.53 | 2.1 | 3.12 | 8.88 |
| uv3 | 0.6 | 1,186 | 0.3 | 73.1 | 81.6 | 0.11 | 0.5 | 3.02 | 8.98 |
| drain | 0 | 1,190 |  | 73.2 | 81.6 | 0 | 0 | 3.00 | 9.00 |
