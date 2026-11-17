# E1. Collision model and choice of placement (C1)

The collision model estimates, from the re-embedded sample S and a sample of queries, how unevenly SRP keys will load the peers (the document collision probability p) and what share of the corpus falls into the bucket of a query's own key (the query bucket fraction q_f). This experiment compares both estimates with the measured load and tests the rule that chooses between the original SRP keys and learned placement from q_f.

| | |
|---|---|
| In the paper | Results, "A collision model predicts peer load and the better placement"; Fig. 2; Table 1 |
| Rounds and hypotheses | 8 (H1), 11 (H14), 12 (H19, H21); 13 (re-estimation from S and the validation queries, post hoc) |
| Analysis scripts | `python3 evo/analyze_r8.py`, `python3 evo/analyze_r11.py`, `python3 evo/analyze_r12.py`, `python3 evo/analyze_r13.py` |

## Results

The collision model passed all of its prespecified criteria, a mean error of at most 0.2 in log10 and a rank correlation of at least 0.8 with peer load, in three rounds (Fig. 2a of the paper; [Table E1.1](#table-e11)). Round 8 repeated the pilot on new seeds: over 12 pairs of four spaces and three corpora, the mean error of p was 0.080 (at most 0.13), and the Spearman correlation between p and the share of records on the 1% most loaded peers was +0.916. Round 11 added two model families, with mean errors of 0.106 for p and 0.102 for q_f on the five new pairs and a correlation of +0.963 over all 17 pairs, and round 12 five more models, with mean errors of 0.062 and 0.063 on the ten new pairs and a correlation of +0.991 over 22 pairs.

These tests used the earlier estimator, which drew on the evaluation queries and on the whole corpus. Re-estimated post hoc from S and the validation queries only, as a deployment could (Methods of the paper), the predictions moved by 0.004 in log10 on average for p (at most 0.018) and by 0.007 for q_f (at most 0.035) over the 51 pairs of rounds 8, 11 and 12. The mean error of p stayed at 0.080 (at most 0.13) in round 8, and the mean errors became 0.110 for p and 0.098 for q_f on the five new pairs of round 11 and 0.063 and 0.068 on the ten new pairs of round 12; the rank correlation with peer load was +0.902 in round 8, against +0.916, and unchanged in rounds 11 and 12. Fig. 2 of the paper and [Table E1.1](#table-e11) use these deployable estimates. All of these errors refer to means over three seeds, as prespecified; since p and q_f are expectations over the random projections, a single seed with its five tables deviated from the prediction by 0.19 in log10 on average over the ten new pairs of round 12.

Over the 22 pairs of round 12, the mean error of the deployable estimates was 0.081 for p and 0.080 for q_f, against 0.079 and 0.077 with the earlier estimator, with p overestimated in 14 pairs and underestimated in 7 (one tie); the largest miss was M₀ on SciFact, predicted at 3.64×10⁻³ against a measured 6.93×10⁻³. These errors are small compared with the range the model has to cover: the measured collision probabilities span more than two orders of magnitude, from 9.3×10⁻⁵ for Arctic on SciFact to 3.3×10⁻² for e5-small on code 20k, where SRP leaves about 30 effectively occupied buckets out of 65,536. The model also holds at the isotropic end of this range: after centering, the predicted and measured values of p in round 8 were 2.3 to 3.3×10⁻⁵ and 2.3 to 3.5×10⁻⁵, close to the value 1/65,536 ≈ 1.5×10⁻⁵ of a uniform assignment to the 65,536 prefixes. The mean-field form, which needs only the mean cosine over S, ranks the pairs almost as well (Spearman +0.916, +0.963 and +0.988 in rounds 8, 11 and 12) but loses accuracy on nearly isotropic spaces, with errors of 0.24 to 0.31 for MiniLM, so we use the angular form throughout.

The query-side term matters because queries need not look like documents. On code 20k, Arctic has p = 2.64×10⁻³ but a predicted q_f of only 1.51×10⁻⁴, because its queries, which carry an instruction prefix, point away from the documents (Methods of the paper). The smaller arctic-xs model of the same family, with the same instruction, has a predicted q_f of 1.56×10⁻³ and 1.78×10⁻³ on the two corpora, 10 to 30 times that of Arctic. The family of a model does not reveal how it will place records, so the geometry has to be measured on a sample, which is what C1 provides.

## Tables

### Table E1.1

Collision model per corpus and space. Code 20k and SciFact: round 12, seeds 36 to 38 (new: first used in round 12). Code 100k: rounds 8 (seeds 6 to 8) and 11 (MiniLM, seeds 26 to 28). p: collision probability of two distinct documents on the first 16 bits, predicted with the angular formula and measured on the keys of the system; MF: mean-field prediction; q_f: share of the corpus in the bucket of a query's own key; Top 1%: share of records on the 1% most loaded peers under SRP with L = 5. Predicted: estimated from the sample S (all pairs of objects in S for p, the 200 validation queries against S for q_f, the mean cosine over S for MF), as described for the collision model in the Methods of the paper (post hoc, round 13). Earlier: the estimator of the prespecified tests, with 200,000 random pairs from the whole corpus for p and the 300 evaluation queries for q_f. Errors are |log₁₀(predicted/measured)| for the estimates from S.

| Corpus | Space | p predicted | p earlier | p measured | Error | MF | q_f predicted | q_f earlier | q_f measured | Error | Top 1% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| code 20k | bge-base | 1.77e-3 | 1.77e-3 | 1.77e-3 | 0.00 | 1.53e-3 | 1.30e-3 | 1.33e-3 | 1.32e-3 | 0.00 | 25.3 |
|  | e5-large | 2.35e-2 | 2.35e-2 | 1.83e-2 | 0.11 | 2.29e-2 | 1.60e-2 | 1.60e-2 | 1.26e-2 | 0.11 | 60.9 |
|  | Arctic | 2.64e-3 | 2.64e-3 | 2.21e-3 | 0.08 | 2.09e-3 | 1.51e-4 | 1.47e-4 | 1.13e-4 | 0.13 | 25.9 |
|  | M₀ | 1.46e-3 | 1.46e-3 | 1.33e-3 | 0.04 | 1.27e-3 | 1.23e-3 | 1.25e-3 | 1.02e-3 | 0.08 | 21.7 |
|  | MiniLM | 1.73e-4 | 1.74e-4 | 2.21e-4 | 0.11 | 1.10e-4 | 5.00e-5 | 5.06e-5 | 5.24e-5 | 0.02 | 10.5 |
|  | gte-base | 1.42e-2 | 1.42e-2 | 9.90e-3 | 0.16 | 1.35e-2 | 1.24e-2 | 1.25e-2 | 8.11e-3 | 0.18 | 48.7 |
|  | arctic-xs (new) | 1.07e-2 | 1.07e-2 | 7.43e-3 | 0.16 | 9.66e-3 | 1.56e-3 | 1.50e-3 | 1.06e-3 | 0.17 | 45.7 |
|  | e5-small (new) | 3.52e-2 | 3.51e-2 | 3.28e-2 | 0.03 | 3.42e-2 | 2.13e-2 | 2.15e-2 | 2.21e-2 | 0.02 | 62.6 |
|  | bge-small (new) | 2.94e-3 | 2.93e-3 | 2.63e-3 | 0.05 | 2.55e-3 | 2.09e-3 | 2.11e-3 | 1.78e-3 | 0.07 | 30.5 |
|  | gte-small (new) | 1.63e-2 | 1.62e-2 | 1.67e-2 | 0.01 | 1.54e-2 | 1.45e-2 | 1.46e-2 | 1.53e-2 | 0.02 | 50.3 |
|  | mpnet (new) | 1.61e-4 | 1.62e-4 | 1.75e-4 | 0.04 | 9.96e-5 | 5.05e-5 | 5.08e-5 | 5.38e-5 | 0.03 | 10.0 |
| SciFact | bge-base | 3.32e-3 | 3.41e-3 | 2.72e-3 | 0.09 | 2.78e-3 | 2.18e-3 | 2.23e-3 | 1.72e-3 | 0.10 | 27.1 |
|  | e5-large | 1.81e-2 | 1.83e-2 | 1.93e-2 | 0.03 | 1.73e-2 | 1.43e-2 | 1.44e-2 | 1.43e-2 | 0.00 | 61.5 |
|  | Arctic | 1.07e-4 | 1.03e-4 | 9.27e-5 | 0.06 | 7.56e-5 | 6.20e-5 | 6.19e-5 | 5.94e-5 | 0.02 | 8.7 |
|  | M₀ | 3.64e-3 | 3.72e-3 | 6.93e-3 | 0.28 | 3.07e-3 | 2.21e-3 | 2.22e-3 | 3.96e-3 | 0.25 | 36.2 |
|  | MiniLM | 1.23e-4 | 1.22e-4 | 1.11e-4 | 0.04 | 5.42e-5 | 8.24e-5 | 8.01e-5 | 7.60e-5 | 0.03 | 9.1 |
|  | gte-base | 1.21e-2 | 1.21e-2 | 8.60e-3 | 0.15 | 1.13e-2 | 1.32e-2 | 1.32e-2 | 9.49e-3 | 0.14 | 45.7 |
|  | arctic-xs (new) | 3.25e-3 | 3.26e-3 | 2.99e-3 | 0.04 | 2.65e-3 | 1.78e-3 | 1.77e-3 | 1.61e-3 | 0.04 | 32.3 |
|  | e5-small (new) | 2.85e-2 | 2.90e-2 | 2.68e-2 | 0.03 | 2.73e-2 | 2.07e-2 | 2.07e-2 | 2.42e-2 | 0.07 | 55.3 |
|  | bge-small (new) | 5.46e-3 | 5.60e-3 | 6.28e-3 | 0.06 | 4.57e-3 | 3.84e-3 | 3.89e-3 | 3.90e-3 | 0.01 | 40.5 |
|  | gte-small (new) | 1.51e-2 | 1.52e-2 | 2.36e-2 | 0.19 | 1.40e-2 | 1.59e-2 | 1.60e-2 | 2.49e-2 | 0.20 | 54.1 |
|  | mpnet (new) | 1.33e-4 | 1.30e-4 | 1.23e-4 | 0.03 | 5.45e-5 | 1.02e-4 | 9.89e-5 | 8.90e-5 | 0.06 | 9.2 |
| code 100k | M₀ | 1.46e-3 | 1.47e-3 | 1.08e-3 | 0.13 | 1.28e-3 | 1.25e-3 | 1.30e-3 | 8.74e-4 | 0.16 | 30.3 |
|  | bge-base | 1.79e-3 | 1.80e-3 | 1.42e-3 | 0.10 | 1.56e-3 | 1.35e-3 | 1.37e-3 | 1.00e-3 | 0.13 | 34.1 |
|  | e5-large | 2.36e-2 | 2.36e-2 | 2.61e-2 | 0.04 | 2.30e-2 | 1.62e-2 | 1.62e-2 | 1.81e-2 | 0.05 | 83.2 |
|  | Arctic | 2.54e-3 | 2.49e-3 | 2.14e-3 | 0.07 | 2.01e-3 | 1.58e-4 | 1.46e-4 | 2.21e-4 | 0.15 | 39.3 |
|  | MiniLM | 1.69e-4 | 1.69e-4 | 1.90e-4 | 0.05 | 1.10e-4 | 5.32e-5 | 4.93e-5 | 5.66e-5 | 0.03 | 13.5 |

### Table E1.2

Placement rule on the predicted query bucket fraction (round 12, seeds 36 to 38). Difference: final R@5 of SRP minus `itq_q+cap16` at the contacted peers of `srp_c+cap16` at (L,T) = (5,8). Work ratio: scoring work of the busiest peer under SRP divided by that under `itq_q+cap16`. Rule: SRP when the predicted q_f ≥ 8×10⁻⁴, learned placement when ≤ 2×10⁻⁴. Predicted q_f: the earlier estimator, which the prespecified test used (300 evaluation queries against the whole corpus), and the post hoc estimate from S and the 200 validation queries (round 13); both put every pair in the same group.

| Corpus | Space | Predicted q_f earlier | Predicted q_f from S | Difference | Per seed | Work ratio | Rule correct |
|---|---|---|---|---|---|---|---|
| code 20k | MiniLM | 5.06e-5 | 5.00e-5 | −12.80 |  | 3.6 | yes |
| code 20k | mpnet (new) | 5.08e-5 | 5.05e-5 | −11.16 | −4.36, −15.53, −13.58 | 2.5 | yes |
| SciFact | Arctic | 6.19e-5 | 6.20e-5 | −0.84 |  | 2.9 | yes |
| SciFact | MiniLM | 8.01e-5 | 8.24e-5 | −6.86 |  | 2.7 | yes |
| SciFact | mpnet (new) | 9.89e-5 | 1.02e-4 | −9.83 | −13.45, −6.01, −10.04 | 3.3 | yes |
| code 20k | Arctic | 1.47e-4 | 1.51e-4 | −5.97 |  | 12.8 | yes |
| code 20k | M₀ | 1.25e-3 | 1.23e-3 | +8.89 |  | 49.7 | yes |
| code 20k | bge-base | 1.33e-3 | 1.30e-3 | +13.48 |  | 37.9 | yes |
| code 20k | arctic-xs (new) | 1.50e-3 | 1.56e-3 | +5.97 | +5.09, +1.43, +11.37 | 65.9 | yes |
| SciFact | arctic-xs (new) | 1.77e-3 | 1.78e-3 | +17.16 | +18.23, +19.71, +13.54 | 43.9 | yes |
| code 20k | bge-small (new) | 2.11e-3 | 2.09e-3 | +14.37 | +11.84, +13.62, +17.66 | 38.8 | yes |
| SciFact | M₀ | 2.22e-3 | 2.21e-3 | +12.25 |  | 63.9 | yes |
| SciFact | bge-base | 2.23e-3 | 2.18e-3 | +13.36 |  | 51.7 | yes |
| SciFact | bge-small (new) | 3.89e-3 | 3.84e-3 | +15.60 | +16.72, +17.58, +12.49 | 124.5 | yes |
| code 20k | gte-base | 1.25e-2 | 1.24e-2 | +19.40 |  | 212.0 | yes |
| SciFact | gte-base | 1.32e-2 | 1.32e-2 | +19.46 |  | 136.1 | yes |
| SciFact | e5-large | 1.44e-2 | 1.43e-2 | +21.67 |  | 240.9 | yes |
| code 20k | gte-small (new) | 1.46e-2 | 1.45e-2 | +19.16 | +17.32, +21.60, +18.58 | 476.0 | yes |
| SciFact | gte-small (new) | 1.60e-2 | 1.59e-2 | +20.90 | +20.63, +21.44, +20.62 | 408.8 | yes |
| code 20k | e5-large | 1.60e-2 | 1.60e-2 | +26.59 |  | 329.2 | yes |
| SciFact | e5-small (new) | 2.07e-2 | 2.07e-2 | +30.08 | +32.73, +29.47, +28.04 | 430.5 | yes |
| code 20k | e5-small (new) | 2.15e-2 | 2.13e-2 | +31.29 | +31.42, +32.57, +29.87 | 389.1 | yes |
