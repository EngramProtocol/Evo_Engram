# E2. Learned keys with a soft load cap (C2)

Learned placement fits the keys of the new epoch on the re-embedded sample (ITQ with median thresholds and separate query and document centers) and places records under a soft load cap of 16 times the mean load per table: an overflowing record goes to the first peer with free capacity among the K = 20 peers closest to its key, or to the least loaded of them when all are full. This experiment compares learned keys with centered random keys and with the original SRP keys, at equal numbers of scored candidates and of contacted peers, and measures what the cap moves, how often it is exceeded and how iterative lookups reach the peers that hold displaced records.

| | |
|---|---|
| In the paper | Results, "Learned keys with a soft load cap balance the load"; Table 1; Methods, "Learned placement with a soft load cap (C2)" |
| Rounds and hypotheses | 8 (H2), 10 (H9), 11 (H13, H15), 12 (H20); exploratory parts of rounds 9, 11, 13 and 14 |
| Analysis scripts | `python3 evo/analyze_r8.py`, `python3 evo/analyze_r9.py`, `python3 evo/analyze_r10.py`, `python3 evo/analyze_r11.py`, `python3 evo/analyze_r12.py`, `python3 evo/analyze_r13.py`, `python3 evo/analyze_r14.py` |

## Results

Table 1 of the paper collects the evidence for C2 (per space, cell and pair in [Table E2.1](#table-e21), [Table E2.3](#table-e23) and [Table E1.2](E1_collision_model.md#table-e12)). To isolate the learned keys, we compared `itq_q+cap16` with `srp_c+cap16`, which has the same centering and cap and a similar load balance (Gini coefficients of 0.46 to 0.58 against 0.42 to 0.52 in round 11), so that only the projections differ.

Learned keys won in all 27 cells, which cover 11 spaces from six families on three corpora: by 10.6 to 24.5 points at an equal number of scored candidates, against a prespecified threshold of 5 (H13a, H15a, H20a), and by 7.2 to 23.9 points at equal contacted peers in the 17 cells of round 11. The cells include e5-large, for which a comparison with the original SRP keys says little because SRP scans 50 to 82% of code 100k for every query. In an exploratory ladder of variants, principal directions instead of random ones added 5.0 to 15.0 points and the ITQ rotation another 5.9 to 11.3.

The cap was almost free: over the 27 cells it changed recall by −0.08 to +0.05 points and moved 0.4 to 3.8% of the records (H13b, H15b, H20b), and caps at 8 and 32 times the mean load on code 100k moved 4.3 to 5.3% and 0.3 to 1.4%, with recall within 0.11 points. The cap is soft: a record whose K closest peers are all full goes to the least loaded of them. Under learned keys this happened in 13 of the 132 placements of rounds 11, 12 and 14, for at most 0.66% of the records of a placement, and summed over the five tables no peer held more than 15.2 times the mean load. On the original SRP keys (exploratory, round 11) the same cap moved 2.7 to 84.5% of the records, up to 64% went to peers that were already full, and 6 to 73% of the queries still reached the most loaded peer, as without the cap, against 5 to 15% under learned keys. A cap among the closest peers spreads the load only when the keys already spread the records.

Compared with the original SRP placement, learned keys gave higher recall for the same number of scored candidates. At the point that SRP reaches with (L,T) = (5,8), they were 17.8 (Arctic), 8.7 (bge-base) and 8.3 points (M₀) higher in round 8, and 16.5, 9.2 and 7.5 points higher with the cap in round 10 (H2, H9a). For e5-large the same comparison is bounded for the reason given above; on the grid of the learned variants they stayed 8.6 to 9.3 points below it ([Table E2.1](#table-e21) and [Table E2.2](#table-e22)). With the cap, the most loaded peer under SRP held 19.8 to 112.8 times as many records as under learned placement in all four spaces (H9b). Without the cap, learned placement failed the load criterion for Arctic in both rounds, with ratios of 2.7 and 2.9 against a threshold of 3: a tight cluster of about 1,270 long functions received the same key in every table, and adding principal components did not remove it ([Table E2.2](#table-e22) and the notes below). The cap spreads this cluster over the K peers closest to its key; Arctic on code 100k also had the largest share of records placed over the cap, at most 0.66%.

Against the original SRP keys, which are neither centered nor capped, learned placement does not always win when the budget is counted in contacted peers. In round 11, SRP retrieved more at an equal number of peers in 11 of 17 cells; after the fact, all 11 had a measured q_f of at least 7.5×10⁻⁴, while the six cells in which learned placement won or tied had q_f ≤ 1.4×10⁻⁴. We turned this observation into the rule given in the Methods of the paper and tested it on ten new pairs in round 12 (H19, Fig. 2b of the paper). In the prespecified test, which used the earlier estimator, the eight pairs with a predicted q_f of at least 1.50×10⁻³ favored SRP, by 5.97 to 31.29 points, and the two pairs with a predicted q_f below 10⁻⁴, both from mpnet, favored learned placement, by 9.83 and 11.16 points. The rule was right in all 22 pairs, and the rank correlation between the predicted q_f and the difference was +0.964 on the new pairs and +0.955 overall. With the deployable estimates that Fig. 2b of the paper plots (post hoc), every pair kept its group, with the eight new SRP pairs at 1.56×10⁻³ or more and the two mpnet pairs at 1.02×10⁻⁴ or less; the rule was again right in all 22 pairs, with correlations of +0.964 and +0.954. The decision also held for each sample on its own: in all 51 pairs of rounds 8, 11 and 12, each of the three samples S, with its validation queries, put the pair in the same group, and none came closer to a threshold than a factor of 1.26. The support for the rule has limits. No pair fell between the two thresholds, so their exact positions are untested; the low-q_f side rests on three models (MiniLM, Arctic and mpnet); and the rule predicts the sign of the difference rather than its size, as code arctic-xs (+5.97, with one seed at +1.43) and SciFact Arctic (−0.84 on average, with seeds of both signs) show. A post hoc rule based on p with the same thresholds would have misclassified code Arctic, where learned placement was 5.97 points better, and p correlated less with the difference than q_f did (+0.901 against +0.955).

The size of this trade shows on code 100k, where every placement contacts about 600 peers at (L,T) = (5,8) (round 11, exploratory; [Table E2.5](#table-e25)). The original SRP keys returned 65.6, 87.9 and 61.1% of the true top five for bge-base, e5-large and M₀, against 54.4, 44.3 and 50.9% for learned keys with the cap; for Arctic and MiniLM, whose q_f is small, the order was reversed, with 22.2 and 32.3% against 31.9 and 47.2%. Where SRP wins on peers, it does so by concentrating work: in the three concentrated spaces, 19 to 59% of the queries reached the most loaded peer under SRP, against about 5% under learned keys, and a cap on the SRP keys kept most of the recall (63.9, 85.6 and 59.8%) but had to move 37 to 84% of the records and left the query load where it was. In the 16 pairs with a large q_f, the busiest peer under SRP did 37.9 to 476 times the scoring work of the busiest peer under learned placement, against 2.5 to 12.8 times where q_f is small; on the eight new pairs with a large q_f, SRP scored 2.0 to 3.7 times as many candidates per query, and 33 to 83% of the queries reached its most loaded peer, compared with 12 to 17% under learned placement (exploratory). We do not consider a placement that sends a fifth to more than half of all queries to one peer suitable for a peer-to-peer overlay, whatever it retrieves per contacted peer, and this is why learned placement is our default.

All these overlays hold at most two objects per peer on average. With code 100k on 5,000 peers, 20 objects per peer, and the same keys, seeds and 16-bit probe prefix (round 14, exploratory; [Table E2.6](#table-e26) and the notes below), the comparisons kept their direction with smaller margins. At equal candidate counts, learned keys were 10.2 to 16.6 points above centered random keys with the same cap, against 16.7 to 22.0 points on 50,000 peers, and the cap changed recall by at most 0.05 points. At equal peers, the original SRP keys stayed ahead in the three spaces with a large q_f and behind for Arctic, but for MiniLM the difference fell from 15.1 points to 1.5 in favor of learned placement, with two of three seeds slightly on the side of SRP, so the rule is not confirmed for MiniLM on this overlay. Every placement is far less selective at this density: at (L,T) = (5,8) a query contacted about 436 peers, 9% of the overlay, and scored 38% of the corpus under learned keys and 41 to 93% under SRP.

## Notes

### Hot spot of uncapped learned keys for Arctic

Without the cap, learned placement failed the load criterion for Arctic in rounds 8 and 10, with ratios of 2.7 and 2.9 against a threshold of 3. The cause was a tight cluster of about 1,270 long functions, eight of the twelve we inspected being generated setters, that lay away from the corpus mean (within-cluster cosine 0.82 against 0.53 for the corpus). In every table, 583 to 1,083 of these functions received the same 63-bit key and therefore the same peer. Adding principal components did not solve the problem: with 256 components the hot spot still held 803 to 868 records, and the recall advantage for bge-base and M₀ was gone ([Table E2.2](#table-e22)).

### Placement on 5,000 peers

At equal peers, the original SRP keys were 5.3, 13.0 and 7.7 points ahead in the three spaces with a large query bucket fraction (12.2, 43.9 and 17.5 on 50,000 peers) and 5.9 points behind for Arctic (10.8). Under SRP, 21 to 78% of the queries reached the most loaded peer, against 18 to 19% under learned keys ([Table E2.6](#table-e26)). The migration was not run at this density.

## Tables

### Table E2.1

Load and recall of learned placement on code 100k with L = 5. Top: round 8, seeds 6 to 8, without cap. Bottom: round 10, seeds 16 to 18, maximum records per peer as the range over seeds, ratio of the maxima of SRP and the variant, and difference in final R@5 from SRP at the number of candidates SRP scores at (L,T) = (5,8). For e5-large, SRP scans 50 to 82% of the corpus at that point, beyond the grid of the learned variants, so its recall comparison is bounded.

| Space | Maximum records per peer `srp` / `itq_q` | Records on 1% of peers (%) `srp` / `itq_q` | Queries reaching the hottest peer (%) `srp` / `itq_q` |
|---|---|---|---|
| e5-large | 18,275 / 770 | 83.2 / 7.6 | 59.7 / 5.2 |
| Arctic | 3,489 / 1,281 | 39.3 / 7.6 | 16.3 / 4.4 |
| bge-base | 1,938 / 314 | 34.1 / 7.0 | 25.8 / 5.2 |
| M₀ | 2,325 / 541 | 30.3 / 6.9 | 23.0 / 5.0 |

| Space | Maximum records per peer `srp` / `itq_q` / `itq_q+cap16` | Load ratio vs `srp` `itq_q` / `itq_q+cap16` | Final R@5 vs `srp` `itq_q` / `itq_q+cap16` | Records moved |
|---|---|---|---|---|
| Arctic | 2,140 to 4,589 / 1,236 to 1,283 / 102 to 128 | 2.9 / 31.8 | +16.6 / +16.5 | 2.2% |
| bge-base | 2,373 to 4,306 / 211 to 393 / 99 to 121 | 10.7 / 28.9 | +9.2 / +9.2 | 1.4% |
| M₀ | 1,732 to 2,678 / 249 to 673 / 101 to 116 | 5.3 / 19.8 | +7.5 / +7.5 | 1.3% |
| e5-large | 12,697 to 13,754 / 497 to 840 / 115 to 117 | 19.9 / 112.8 | −8.6 / −8.6 | 2.0% |

### Table E2.2

ITQ on more principal components (round 9, exploratory, code 100k, seeds 6 to 8; 63 bits kept per table). Difference in final R@5 from SRP at the candidates of SRP, and ratio of the maximum load per peer of SRP to that of the variant.

| Space | Final R@5 vs `srp` 63 / 128 / 256 components | Load ratio 63 / 128 / 256 components |
|---|---|---|
| Arctic | +17.8 / +12.1 / +8.4 | 2.7 / 3.4 / 4.1 |
| bge-base | +8.7 / +3.9 / −1.1 | 7.7 / 10.0 / 12.2 |
| M₀ | +8.3 / +3.5 / −3.2 | 4.3 / 7.8 / 15.3 |
| e5-large (bounded) | −9.3 / −12.5 / −17.4 | 23.8 / 45.5 / 112.5 |

### Table E2.3

Learned against centered random keys with the same cap: final R@5 of `itq_q+cap16` minus `srp_c+cap16` at the candidate count of `srp_c+cap16` at (L,T) = (5,8) (three-seed means; prespecified threshold +5). The cap itself changed recall by −0.08 to +0.05 points over the 27 cells.

| Space | code 100k | code 20k | SciFact | Round |
|---|---|---|---|---|
| bge-base | +20.15 | +15.99 | +24.50 | 11 |
| e5-large | +22.05 | +20.32 | +23.70 | 11 |
| Arctic | +16.69 | +18.02 | +16.58 | 11 |
| M₀ | +20.56 | +18.75 | +23.63 | 11 |
| MiniLM | +19.57 | +15.83 | +13.80 | 11 |
| gte-base |  | +15.85 | +20.89 | 11 |
| mpnet |  | +17.70 | +17.20 | 12 |
| arctic-xs |  | +10.64 | +14.28 | 12 |
| bge-small |  | +16.59 | +20.41 | 12 |
| gte-small |  | +15.43 | +15.53 | 12 |
| e5-small |  | +16.52 | +18.66 | 12 |

### Table E2.4

Reach of iterative lookups by the XOR rank of a peer among the K = 20 peers closest to the key (round 13, exploratory). Overlays are built as in the simulator described in the Methods of the paper: 63-bit identifiers, nodes that join through a node already in the overlay and then refresh once, and k-buckets of 20. Lookups follow the procedure of the simulator, with α = 3, K = 20 and at most 20 rounds. Each lookup starts at a random node and targets a random key, and its result is compared with the true K closest peers in XOR order; five overlays of each size and 5,000 lookups on each. Values are in percent unless stated otherwise, and intervals are 95% t intervals over the five overlays. Bound: share of records displaced by the cap of `itq_q+cap16` (117 placements of rounds 11 and 12, each paired with the overlays of its size) times the gap between rank 1 and the mean of ranks 16 to 20; in parentheses, with the gap to the least found rank.

|  | 10,000 peers | 50,000 peers |
|---|---|---|
| Lookups | 25,000 | 25,000 |
| Share of the K closest peers found (range over overlays) | 87.2 (86.7 to 87.6) | 77.7 (76.9 to 78.5) |
| Lookups that found all K | 72.1 | 50.0 |
| Lookups that found none of the K | 10.8 | 18.8 |
| Lookups that found some (mean share found) | 17.0 (88.6) | 31.2 (88.8) |
| Misses that come from lookups that found none | 84.7 | 84.3 |
| Found at ranks 1 to 5 | 87.7, 87.7, 87.6, 87.6, 87.7 | 78.2, 78.0, 78.1, 78.0, 78.2 |
| Found at ranks 6 to 10 | 87.6, 87.7, 87.6, 87.7, 87.6 | 78.1, 78.1, 78.2, 78.0, 78.0 |
| Found at ranks 11 to 15 | 87.5, 87.6, 87.4, 87.2, 87.0 | 77.9, 77.8, 77.7, 77.5, 77.4 |
| Found at ranks 16 to 20 | 86.7, 86.8, 86.4, 86.0, 85.9 | 77.3, 77.1, 76.8, 76.7, 76.4 |
| Rank 1 minus mean of ranks 16 to 20 (points) | 1.34 [1.02, 1.65] | 1.38 [1.21, 1.55] |
| Rank 1 minus least found rank (points) | 1.82 | 1.80 |
| Found at rank 1 and at rank 20, given that the lookup found at least one of the K | 98.3, 96.3 | 96.4, 94.1 |
| Rounds and `FIND_NODE` requests per lookup (counts) | 6.90, 20.7 | 8.25, 24.8 |
| Records displaced by the cap: mean, maximum | 1.56, 4.92 |  |
| Bound on records missed because of the cap: mean, maximum | 0.021, 0.066 (0.090) |  |

### Table E2.5

Placements at equal probes on code 100k (round 11, exploratory; seeds 26 to 28, 300 evaluation queries, 50,000 peers). Top: the original SRP keys, the same keys with the cap, and learned keys with the cap, all at (L,T) = (5,8). Final: final R@5; hottest peer: share of queries that reach the most loaded peer; moved: share of records displaced by the cap. Bottom: the learned native index (`itq_q+cap16`) at four budgets, as contacted peers followed by final R@5 and rerank@20. Values separated by slashes follow the order of the column header.

| Space | Final `srp` / `srp+cap16` / `itq_q+cap16` | Contacted peers | Scored candidates `srp` / `srp+cap16` / `itq_q+cap16` | Hottest peer (%) `srp` / `itq_q+cap16` | Moved (%) `srp+cap16` / `itq_q+cap16` |
|---|---|---|---|---|---|
| bge-base | 65.6 / 63.9 / 54.4 | 588 to 597 | 18,883 / 17,894 / 6,362 | 22.2 / 5.2 | 40.6 / 1.4 |
| e5-large | 87.9 / 85.6 / 44.3 | 597 to 603 | 68,542 / 62,352 / 6,260 | 59.4 / 4.8 | 84.5 / 2.0 |
| M₀ | 61.1 / 59.8 / 50.9 | 593 to 595 | 18,350 / 17,325 / 6,344 | 18.8 / 5.3 | 37.3 / 1.1 |
| Arctic | 22.2 / 21.8 / 31.9 | 593 to 596 | 9,900 / 9,765 / 6,178 | 15.4 / 5.1 | 47.4 / 2.2 |
| MiniLM | 32.3 / 32.2 / 47.2 | 594 to 595 | 7,210 / 7,195 / 6,243 | 6.0 / 4.9 | 11.9 / 1.6 |

| Space | (L,T) = (5,8) | (5,16) | (10,8) | (10,16) |
|---|---|---|---|---|
| bge-base | 597: 54.4 / 55.1 | 1,143: 64.5 / 65.6 | 1,185: 76.1 / 78.5 | 2,258: 84.5 / 88.0 |
| e5-large | 597: 44.3 / 44.6 | 1,144: 54.5 / 55.0 | 1,183: 68.8 / 69.9 | 2,255: 80.6 / 82.6 |
| M₀ | 595: 50.9 / 51.2 | 1,140: 61.3 / 61.7 | 1,180: 73.8 / 74.8 | 2,250: 83.3 / 85.2 |
| Arctic | 593: 31.9 / 32.0 | 1,140: 42.3 / 42.7 | 1,182: 54.0 / 55.2 | 2,255: 68.0 / 70.8 |
| MiniLM | 595: 47.2 / 47.8 | 1,141: 57.2 / 58.2 | 1,182: 70.6 / 72.6 | 2,258: 80.4 / 84.1 |

### Table E2.6

Placement of code 100k on 5,000 peers, 20 objects per peer (round 14, exploratory; seeds 26 to 28, 300 evaluation queries; the keys, seeds and 16-bit probe prefix of round 11, whose values on 50,000 peers are given for comparison). The first block uses the definitions of the prespecified placement comparisons: learned keys minus centered random keys with the same cap at equal candidates, the effect of the cap on learned keys at equal candidates, and the original SRP keys minus learned keys with the cap at equal peers. Each is a difference in final R@5 on the frontier over eight (L,T) configurations, interpolated at the candidates or the peers of a reference variant at (L,T) = (5,8). The other rows are measured at (L,T) = (5,8) on 5,000 peers, where every placement contacts 423 to 447 peers. Hottest peer: share of queries that reach the most loaded peer; top 1%: share of records on the 1% most loaded peers; moved: share of records displaced by the cap.

|  | bge-base | e5-large | M₀ | Arctic | MiniLM |
|---|---|---|---|---|---|
| **Differences in final R@5 on the frontier (points)** |  |  |  |  |  |
| learned − centered random, equal candidates, 5,000 peers | +10.2 | +16.6 | +12.4 | +14.2 | +11.8 |
| the same on 50,000 peers | +20.2 | +22.0 | +20.6 | +16.7 | +19.6 |
| cap effect, equal candidates, 5,000 peers | 0.00 | 0.00 | 0.00 | +0.05 | 0.00 |
| SRP − learned, equal peers, 5,000 peers | +5.3 | +13.0 | +7.7 | −5.9 | −1.5 |
| seed 26 | +5.5 | +15.1 | +4.8 | −7.1 | +0.5 |
| seed 27 | +6.4 | +8.0 | +7.6 | −7.8 | −5.9 |
| seed 28 | +4.0 | +15.9 | +10.7 | −2.7 | +0.8 |
| the same on 50,000 peers | +12.2 | +43.9 | +17.5 | −10.8 | −15.1 |
| **At (L,T) = (5,8) on 5,000 peers** |  |  |  |  |  |
| final R@5, `srp` | 87.4 | 93.5 | 88.4 | 63.5 | 68.6 |
| final R@5, `srp+cap16` | 87.0 | 93.3 | 87.9 | 62.7 | 68.6 |
| final R@5, `srp_c+cap16` | 71.6 | 61.5 | 69.6 | 53.5 | 66.6 |
| final R@5, `itq_q+cap16` | 82.1 | 78.1 | 82.3 | 68.2 | 78.6 |
| scored candidates, `srp` | 60,699 | 92,515 | 61,835 | 48,965 | 40,693 |
| scored candidates, `itq_q+cap16` | 37,671 | 37,451 | 37,922 | 37,524 | 37,761 |
| hottest peer (%), `srp` | 50.1 | 78.1 | 49.8 | 41.0 | 21.2 |
| hottest peer (%), `itq_q+cap16` | 18.3 | 17.7 | 17.7 | 17.6 | 18.7 |
| top 1% (%), `srp` | 19.9 | 59.9 | 19.7 | 24.0 | 10.0 |
| top 1% (%), `itq_q+cap16` | 5.2 | 5.1 | 5.4 | 5.2 | 5.2 |
| moved (%), `srp+cap16` | 27.0 | 73.1 | 24.3 | 32.1 | 5.4 |
| moved (%), `itq_q+cap16` | 0.2 | 0.5 | 0.2 | 1.0 | 0.2 |
