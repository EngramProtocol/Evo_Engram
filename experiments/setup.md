# Setup: embedding spaces, migration policies and evaluation rounds

These tables complete the Methods of the paper. The repository README gives the model checkpoints and the names used in file names and logs.

## Embedding spaces

Embedding spaces. Top 1%: share of records held by the 1% most loaded peers under SRP placement with L = 5, as the range over code 20k and SciFact (seeds 36 to 38). The last column marks the contributions evaluated on each space.

| Space | Family | Dim. | Corpora | Top 1% (%) | Used for |
|---|---|---|---|---|---|
| M₀ (bge-large) (Xiao et al. 2024) | BGE | 1024 | all | 21.7 to 36.2 | legacy; C1, C2 |
| bge-base (Xiao et al. 2024) | BGE | 768 | all | 25.3 to 27.1 | C1 to C3 |
| e5-large (Wang et al. 2022) | E5 | 1024 | all | 60.9 to 61.5 | C1 to C3 |
| Arctic (Merrick et al. 2024) | Arctic | 768 | all | 8.7 to 25.9 | C1 to C3 |
| gte-base (Li et al. 2023) | GTE | 768 | 20k, SciFact | 45.7 to 48.7 | C1 to C3 |
| MiniLM (Wang et al. 2020; Reimers and Gurevych 2019) | MiniLM | 384 | all | 9.1 to 10.5 | C1 to C3 |
| mpnet (Song et al. 2020; Reimers and Gurevych 2019) | MPNet | 768 | 20k, SciFact | 9.2 to 10.0 | C1, C2 |
| arctic-xs (Merrick et al. 2024) | Arctic | 384 | 20k, SciFact | 32.3 to 45.7 | C1, C2 |
| bge-small (Xiao et al. 2024) | BGE | 384 | 20k, SciFact | 30.5 to 40.5 | C1, C2 |
| gte-small (Li et al. 2023) | GTE | 384 | 20k, SciFact | 50.3 to 54.1 | C1, C2 |
| e5-small (Wang et al. 2022) | E5 | 384 | 20k, SciFact | 55.3 to 62.6 | C1, C2 |

## Migration policies

Migration policies. Repository names identify the runs in the released code.

| Policy | Re-embedding order | Legacy record of a re-embedded object | Repository name |
|---|---|---|---|
| static | none | kept | `static` |
| full | all objects at t = 0 | removed at t = 0 | `full` |
| rebuild | background, separate index | kept until the switch at completion | `rebuild` |
| lazy | hints | retired at publication | `lazy` |
| bg | background | retired at publication | `bg` |
| lazy+bg | hints and background | retired at publication | `lazybg` |
| map-all | mapped records at t = 0, then hints | removed at t = 0 | `mapall` |
| map-keep | mapped records at t = 0, then hints | kept until replaced | `mapkeep` |
| Dual migration | hints and background, dual | kept with the E₁ code attached until the retirement rule or the drop | `lazyVbgD` family |
| rule drain |  | not retired before the drop | `lazyVbgDinf` |
| rules k1, k2, k3 |  | after 1, 2 or 3 sightings, repeats counted | `lazyVbgD`, `… k2`, `… k3` |
| rule u2 |  | after sightings by 2 distinct queries | `lazyVbgDu2` |
| rules v2, uv2, uv3 |  | as k2, u2, u3, with a veto resetting the count | `lazyVbgDv2`, `… uv2`, `… uv3` |
| **Ablation variants (rule k1 where a rule applies)** |  |  |  |
| lazy+delay | hints | kept with the code attached until one sighting | `lazyV1` |
| dual, background retired | hints and background | hinted objects dual; background objects retired at publication | `lazyVbg` |
| dual, no attached code | hints and background, dual | kept and scored by the adapter | `lazyVbgD_adp` |
| lazy+keep | hints | kept with the code attached, never retired | `lazyD` |

## Evaluation rounds

Evaluation rounds. Exploratory analyses within rounds with prespecified protocols are labeled as such in the text.

| Round | Tag | Seeds | Questions | Criteria met |
|---|---|---|---|---|
| 4 | `evo-confirm-v1` | 3 to 5 | supporting components S1 to S4 (adapter, fusion, refitting, lazy order) | 15/20 |
| 5, 6 | `evo-r5-v1`, `evo-r6-v1` | 3 to 12 | exploratory: PQ-reconstruction adapters, iterative lookup, schedule replay |  |
| 7, 7b | `evo-r7-pilot`, `evo-r7b-pilot` | 3 to 5 | exploratory pilot of C1 to C3 |  |
| 8 | `evo-r8-prereg` | 6 to 15 | H1 to H5: C1 on three corpora; C2 and C3 on code 100k | 19/20 |
| 9 | `evo-r9-prereg` | 6 to 15 | H6 to H8: C3 on code 20k and SciFact; churn, map-keep and the ITQ hot spot (exploratory) | 18/24 |
| 10 | `evo-r10-prereg` | 16 to 25 | H9 to H10: load cap and C3 on capped placement; completion (exploratory) | 19/19 |
| 11 | `evo-r11-prereg` | 26 to 35 | H11 to H17: C3 ablation, completion against both ends, C2 mechanism, two new families, payload | 85/109 |
| 12 | `evo-r12-prereg` | 36 to 45 | H18 to H21: stronger retirement evidence, q_f rule, five new models | 52/63 |
| 13 | `evo-r13-prereg` | 6 to 8, 26 to 38 | exploratory: p and q_f re-estimated from S and validation queries; lookup reach by XOR rank (overlay seeds 1 to 5); costs of drain on the stream |  |
| 14 | `evo-r14-prereg` | 26 to 35, 46 to 55 | H22 to H24: drain to completion on new seeds, drain on the stream for three more models, C3 on the original SRP keys; full with the peers of two epochs, churn with drain and 5,000 peers (exploratory) | 130/130 |
| 15 | `evo-r15-prereg` | 46 to 55 | H25: C3 to completion on the original SRP keys for three models; two further models, equal progress and a doubled background (exploratory) | 68/68 |

## Notes on the rounds

Round 14 (tag `evo-r14-prereg`) tested three prespecified hypotheses, H22 to H24, with 130 criteria, all of which were met, and added three exploratory measurements. The simulator was not changed.

In round 11 the thread count of the embedding phase was set incorrectly, which affected only the running time.
