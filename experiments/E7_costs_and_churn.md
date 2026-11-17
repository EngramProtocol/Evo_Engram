# E7. Costs, payload, churn and peer failures

This experiment records what the two epochs cost: contacted peers, scored candidates, stored records and bytes, payload fetches on the query path and background re-embeddings. It also runs the policies under churn with lazy repair and after a sudden failure of part of the overlay.

| | |
|---|---|
| In the paper | Results, "Costs"; Table 4 |
| Rounds and hypotheses | 9 (H8; churn and peer failures, exploratory), 11 (H17), 13 (drain on the code 100k stream), 14 (full with 16 probes per table; churn with drain, exploratory) |
| Analysis scripts | `python3 evo/analyze_r9.py`, `python3 evo/analyze_r11.py`, `python3 evo/analyze_r13.py`, `python3 evo/analyze_r14.py` |

## Results

The gains of dual migration come with costs that a deployment has to accept (Table 4 of the paper, for the stream on code 100k). While both epochs are active, every query contacts the peers of both, 1,197 peers against 598 for full, as static and lazy also do, and scores about 26,000 (k1) to 27,000 (drain) candidates against 6,389. Storage grows as well: at the end of the 3,000-arrival stream, 37.3% of the objects were dual under drain and the record count stood at 137% of its initial level, against 30.9% and 131% under k1, and in the runs to completion of round 12 the record count peaked at 190% under drain and at 159 to 174% under k1. Legacy peers return the codes of about 50 dual objects per query under k1, 19 to 26 KB depending on the model, and about 53 under drain, 20 KB for bge-base. Retiring after one sighting saves only part of this storage before completion: relative to drain, k1 kept 6.4 points fewer records and 57 fewer bytes per object and table at the peak, at a cost of 1.4 points of held-out recall (95% interval 0.6 to 2.2) and 5.8 points of stream rerank (2.9 to 8.7; exploratory, round 13), and of 1.2 to 1.9 and 4.9 to 8.2 points for the other three models (H23; see [E4](E4_parts_of_dual_migration.md)).

The payload numbers need care, because background re-embedding also fetches payloads, only outside the query path. Counting both paths, drain fetched 12.4 payloads per arrival, k1 12.2 and lazy 12.7; what changed is that two thirds (k1) to three quarters (drain) of the fetches moved from the clients to the re-indexer. Only the attached code removes fetches outright: without it, dual migration fetched 15.6+10.5 = 26.1 payloads per arrival, because dual objects found through the legacy path had to be fetched for reranking. With about 800 requests per payload on 50,000 peers, lookups included (Methods of the paper), the query path on code 100k carries about 6,900 (k1) to 7,700 (drain) fewer requests per query than under lazy. In the network simulation of the original design, a query that reranked 20 fetched payloads took 11 to 12 s at the median, against 0.7 to 0.8 s without the fetches ([Table E9.8](E9_supporting_components.md#table-e98) and [Table E9.9](E9_supporting_components.md#table-e99)), so the payloads that a policy leaves on the query path dominate its response time.

On code 100k this saving met the prespecified bounds, at most 40% of dual objects and at most one third of the payloads of lazy, which were set for rule k1: dual objects made up 31.6 to 35.3% of the corpus at the end of the stream, and dual migration fetched 0.26 to 0.31 times the payloads of lazy on the query path (H5 and H10d; 31.5% and 0.300 for MiniLM, H16d). Measured against the same bounds (exploratory), drain met the payload bound for all four models, with 0.20 to 0.24 times the payloads of lazy, and the storage bound for three of them, with 37.3, 38.8 and 38.3% of dual objects at the end for bge-base, e5-large and MiniLM; it exceeded it for Arctic, with 42.1% ([Table E4.1](E4_parts_of_dual_migration.md#table-e41)). The bound of one third failed on code 20k and SciFact (H8, none of six, with ratios of 0.55 to 0.80) and again on longer streams (H17, three of twelve criteria met), because the saving comes from repeated queries: on code 100k the ratio was 0.98 for the first occurrence of a query and 0.02 to 0.04 from the sixth onward ([Table E7.1](#table-e71) and [Table E7.4](#table-e74) and the notes below). On a small corpus with a long stream, lazy re-embeds the whole corpus before the stream ends, so little is left to save. In the runs to completion, the cumulative ratio up to t_end was 0.28 to 0.31 on code 20k with t_end = 1,500, 0.37 to 0.39 with t_end = 3,000 and 0.41 to 0.56 on SciFact.

We also replayed the stream under churn (exploratory): with rule k1 in round 9 on uncapped placement (seeds 6 to 10) and in round 11 on capped placement (seeds 26 to 28), and with drain in round 14 on the runs of round 11 ([Table E7.2](#table-e72) and [Table E7.3](#table-e73) and the notes below). With lazy repair, no policy lost more than 2.0 points of held-out recall, and no more than two objects were without any path at a checkpoint. Because it keeps more records alive, dual migration wrote 15.1 to 18.1% more repairs and sent 15.6 to 19.1% more keep-alives than static with rule k1, and 19.2 to 22.2% and 19.5 to 22.9% more with drain. A sudden failure of 30% of the nodes, without repair, was harder: policies lost 2.4 to 11.4 points at the moment of failure, and by the end of the stream full had lost 7.5 to 11.4 points, dual migration with rule k1 3.3 to 6.2 and drain 3.6 to 5.9. Because dual objects have records in both epochs, fewer objects were left without a path, 0.14 to 0.19% of the corpus against 0.22 to 0.26% under the policies with a single set of records, and after the failure dual migration remained 5.5 to 7.7 points above lazy and 6.0 to 10.3 points above static.

## Notes

### Costs

With 64 bytes of metadata per record, drain peaked at 884 bytes per object and table on the stream, k1 at 823 and static at 573. Retiring earlier saves little storage without background migration as well: lazy+keep, which never retires, peaked at 109.8% of the records against 108.7% for lazy+delay, and its stream rerank was 7.0 points higher. [Table E7.4](#table-e74) gives the payload fetches on the query path per corpus and stream length. On code 100k the ratio of the fetches under dual migration to those under lazy was 0.98 for the first occurrence of a query, 0.92 to 0.94 for the second, 0.68 to 0.83 for the third to fifth and 0.02 to 0.04 from the sixth onward, and first occurrences in the second half of the stream still had 0.96 to 0.99 ([Table E7.1](#table-e71)). On a small corpus with a long stream the matched budget leaves almost no background work (0.07 objects per arrival on SciFact with 3,000 arrivals).

### Churn and peer failures

We replayed the stream under churn, with rule k1 for dual migration, in round 9 on uncapped placement with seeds 6 to 10 and in round 11 on capped placement with seeds 26 to 28; both analyses are exploratory. With lazy repair, no policy lost more than 2.0 points of held-out recall, the differences between policies changed by about one point at most, and no more than two objects were without any path at a checkpoint. Over the two rounds, dual migration wrote 15.1 to 18.1% more repairs and sent 15.6 to 19.1% more keep-alives than static, because it keeps more records alive. A sudden failure of 30% of the nodes, without repair, was harder. Policies lost 2.4 to 11.4 points at the moment of failure, and by the end of the stream full had lost 7.5 to 11.4 points and dual migration 3.3 to 6.2. Because dual objects have records in both epochs, only 0.16 to 0.19% of the corpus was left without a path under dual migration, against 0.22 to 0.26% under the policies with a single set of records. Dual migration remained 5.5 to 7.4 points above lazy and 6.0 to 10.3 points above static, and in round 9 its gap to full was no longer significant. Round 14 repeated the runs of round 11 with drain (seeds 26 to 28, exploratory; [Table E7.3](#table-e73)). Under churn drain lost 0.3 to 0.6 points of held-out recall, wrote 19.2 to 22.2% more repairs and sent 19.5 to 22.9% more keep-alives than static, and stayed 0.7 to 1.7 points above rule k1 on held-out queries and 6.2 to 8.4 points above it in stream rerank. After the failure of 30% of the nodes it lost 3.6 to 5.9 points, about as much as rule k1 (3.4 to 6.2), and 0.14 to 0.16% of the corpus was left without a path, against 0.16 to 0.17% under k1 and 0.23 to 0.25% under static, lazy and full. drain remained 6.5 to 7.7 points above lazy and 7.4 to 9.5 points above static. Replacement nodes keep the identifiers of the nodes they replace, so the handover of records between nodes is not modeled ([Table E7.2](#table-e72)).

## Tables

### Table E7.1

Where the payload saving comes from (round 11, Zipf(1)). Top: ratio of payload fetches on the query path, dual migration over lazy, by the occurrence of a query in the stream (code 100k, four models). Bottom: ratio predicted from the occurrence mix of each stream against the measured ratio (bge-base).

| Occurrence of the query | Ratio |
|---|---|
| first | 0.98 |
| second | 0.92 to 0.94 |
| third to fifth | 0.68 to 0.83 |
| sixth or later | 0.02 to 0.04 |
| first occurrence, second half of the stream | 0.96 to 0.99 |
| repeated, second half of the stream | 0.10 to 0.15 |
| Stream | Predicted / measured |
| code 20k, 600 arrivals | 0.581 / 0.582 |
| SciFact, 155 arrivals | 0.791 / 0.789 |
| code 20k, 3,000 arrivals (lazy completes) | 0.264 to 0.321 / 0.457 to 0.498 |
| SciFact, 3,000 arrivals (lazy completes) | 0.264 to 0.321 / 0.921 to 0.955 |

### Table E7.2

Churn and peer failures (exploratory; code 100k, Zipf(1); bge-base / e5-large / Arctic). Held-out final R@5 at the end of the stream, in points. Damage: difference from the same seeds without churn. Churn: Weibull sessions with lazy repair; failure: 30% of the nodes at arrival 1,500, no repair.

|  | Round 9, `itq_q`, seeds 6 to 10 · no churn | Round 9, `itq_q`, seeds 6 to 10 · churn | Round 9, `itq_q`, seeds 6 to 10 · failure | Round 11, `itq_q+cap16`, seeds 26 to 28 · churn | Round 11, `itq_q+cap16`, seeds 26 to 28 · failure |
|---|---|---|---|---|---|
| Dual − lazy | +6.1/+8.0/+7.0 | +6.4/+8.4/+6.7 | +5.8/+7.4/+6.3 | +5.7/+4.9/+8.5 | +5.9/+5.5/+6.3 |
| Dual − static | +9.7/+6.6/+8.9 | +9.8/+6.7/+8.6 | +10.3/+7.1/+8.0 | +9.5/+5.9/+11.3 | +9.0/+6.0/+7.4 |
| full − dual | +5.7/+8.0/+3.8 | +5.0/+7.0/+3.4 | +0.2/+3.0/−1.4 | +4.8/+6.3/+1.9 | +0.9/+1.9/−0.8 |
| Damage, dual |  | −0.8/−0.8/−0.8 | −5.9/−4.2/−3.3 | −0.9/−0.7/−0.4 | −6.2/−3.4/−4.4 |
| Damage, full |  | −1.5/−1.7/−1.3 | −11.4/−9.2/−8.6 | −1.5/−2.0/−0.8 | −10.7/−9.1/−7.5 |

### Table E7.3

Churn and peer failures with drain (round 14, exploratory; code 100k, `itq_q+cap16`, Zipf(1), seeds 26 to 28; bge-base / e5-large / Arctic). Differences are in points of held-out final R@5 at the end of the stream unless stated otherwise. Damage: difference from the same seeds without churn. Churn: Weibull sessions with lazy repair; failure: 30% of the nodes at arrival 1,500, no repair. Repair writes and keep-alives are ratios to static. The runs of k1, full, static and lazy reproduce those of round 11 value for value.

|  | Churn | Failure |
|---|---|---|
| Held-out final, drain | 46.0/35.1/28.4 | 40.6/32.1/24.5 |
| Stream rerank, drain | 66.3/54.8/40.0 | 63.8/52.1/36.8 |
| drain − lazy | +6.4/+6.6/+9.7 | +6.5/+6.9/+7.7 |
| drain − static | +10.2/+7.6/+12.5 | +9.5/+7.4/+8.7 |
| full − drain | +4.1/+4.6/+0.7 | +0.4/+0.5/−2.1 |
| drain − k1 | +0.7/+1.7/+1.2 | +0.5/+1.4/+1.3 |
| drain − k1, stream rerank | +6.2/+8.4/+7.2 | +7.1/+8.4/+9.1 |
| Damage, drain | −0.5/−0.6/−0.3 | −5.9/−3.6/−4.2 |
| Damage, k1 | −0.9/−0.7/−0.4 | −6.2/−3.4/−4.4 |
| Damage, full | −1.5/−2.0/−0.8 | −10.7/−9.1/−7.5 |
| Damage, static | −0.7/−0.4/−0.3 | −5.4/−3.2/−0.5 |
| Damage, lazy | −1.1/−0.9/−0.6 | −6.5/−4.1/−2.4 |
| Repair writes, drain | 1.192/1.209/1.222 |  |
| Repair writes, k1 | 1.151/1.166/1.178 |  |
| Keep-alives, drain | 1.195/1.214/1.229 |  |
| Keep-alives, k1 | 1.156/1.173/1.186 |  |
| Corpus without a path at the end (%), drain | below 0.001 | 0.161/0.147/0.137 |
| k1 | below 0.001 | 0.171/0.161/0.157 |
| static | below 0.001 | 0.232/0.229/0.227 |
| lazy | below 0.001 | 0.246/0.226/0.242 |
| full | below 0.001 | 0.242/0.237/0.249 |

### Table E7.4

Payload fetches per query on the query path for bge-base under Zipf(1) (round 11; dual migration with rule k1). The last column gives the arrival at which lazy itself has re-embedded every object outside S, taken from the runs to completion on the same corpus (range over five models). On the code 100k stream, drain fetched 3.05 payloads per query, a ratio of 0.24 (round 13).

| Corpus (objects) | Stream | lazy | Dual (k1) | Difference | Ratio | lazy complete at |
|---|---|---|---|---|---|---|
| code 100k (100,000) | 3,000 | 12.66 | 4.06 | 8.61 | 0.32 | not reached |
| code 20k (20,000) | 600 | 14.05 | 8.18 | 5.88 | 0.58 | not reached |
| code 20k | 3,000 | 6.00 | 2.99 | 3.01 | 0.50 | 1,350 to 1,945 |
| SciFact (5,183) | 155 | 15.59 | 12.30 | 3.29 | 0.79 | not reached |
| SciFact | 3,000 | 1.55 | 1.45 | 0.10 | 0.94 | 339 to 488 |
