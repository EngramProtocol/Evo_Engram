# E8. Mapping baselines

map-all and map-keep map every legacy object into the new space with the adapter at t = 0 and publish it under E₁ keys, which approximates the FastFill family; query-driven re-embedding later replaces the mapped records. They use our adapter rather than a separately learned transformation and replace records in query order rather than by uncertainty, so they do not reproduce FastFill itself.

| | |
|---|---|
| In the paper | Results, last paragraph of "Keeping the old path pays off when a query reaches a small part of the corpus"; Methods, "Migration policies and baselines" |
| Rounds and hypotheses | 8 and 9 (exploratory, with uncapped learned placement) |
| Analysis scripts | `python3 evo/analyze_r8.py`, `python3 evo/analyze_r9.py` |

## Results

Finally, map-all and map-keep, run in rounds 8 and 9 on uncapped learned placement, show that mapping every object up front is no substitute for re-embedding in this setting. map-all was already below static at t = 0, and dual migration exceeded it by 10.1 to 14.3 points on code 100k and by 12.2 to 31.5 points on the other corpora. map-keep, which contacts as many peers as dual migration and doubles storage from the start, was below dual migration in all nine corpus and model pairs, by 3.0 to 31.2 points, while fetching 1.4 to 4.2 times as many payloads ([Table E8.1](#table-e81) and the notes below).

## Notes

### Mapping baselines

The mapped vectors had a cosine of 0.86 to 0.94 with the true embeddings on code 100k, yet map-all was already below static at t = 0 (33.8 against 38.9 for bge-base, 24.2 against 29.6 for e5-large and 14.4 against 18.6 for Arctic). map-all removes E₀ at once, while map-keep keeps it. Because both baselines use our adapter rather than a separately learned transformation, they do not show that FastFill itself would do worse ([Table E8.1](#table-e81)).

## Tables

### Table E8.1

Mapping every object first (rounds 8 and 9, exploratory, `itq_q`, 10 seeds). Held-out final R@5 at the end of the stream; payload fetches per query on the query path. map-keep contacts as many peers as dual migration (1,195 to 1,197 on code 100k).

| Corpus | Model | Dual / map-keep / map-all | Dual − map-keep | Payload, dual / map-keep |
|---|---|---|---|---|
| code 100k | bge-base | 48.9 / 45.9 / 36.3 | +3.0 [1.2, 4.9] | 4.0 / 13.4 |
|  | e5-large | 36.3 / 21.8 / 22.1 | +14.6 [13.0, 16.1] | 3.9 / 16.3 |
|  | Arctic | 27.3 / 23.5 / 17.2 | +3.8 [2.4, 5.1] | 3.7 / 15.3 |
| code 20k | bge-base | 65.3 / 59.0 / 51.6 | +6.3 [4.5, 8.1] | 8.4 / 14.8 |
|  | e5-large | 50.5 / 37.6 / 37.0 | +12.9 [7.3, 18.5] | 7.9 / 15.8 |
|  | Arctic | 47.4 / 44.2 / 35.2 | +3.2 [1.3, 5.1] | 8.1 / 15.7 |
| SciFact | bge-base | 67.1 / 56.7 / 52.2 | +10.3 [8.7, 12.0] | 12.4 / 17.3 |
|  | e5-large | 55.2 / 24.0 / 23.7 | +31.2 [28.7, 33.7] | 12.5 / 19.5 |
|  | Arctic | 53.7 / 47.2 / 40.9 | +6.5 [2.5, 10.6] | 12.5 / 17.5 |
