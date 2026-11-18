# Experiment record

This directory documents the experiments behind the manuscript *Coordinated record placement and retirement mitigate recall loss during embedding model migration in decentralized semantic indexes*, by Nam-Khanh Tran, Mau-Tra Nguyen and Binh Minh Nguyen. The paper reports the results that support its
conclusions. The pages below give, for each experiment, the question it answers, the rounds and hypotheses that test
it, the analysis scripts that reproduce it, and its complete results per cell, model and seed.

| Experiment | In the paper | Rounds |
|---|---|---|
| [E1. Collision model and choice of placement (C1)](E1_collision_model.md) | Results; Fig. 2; Table 1 | 8, 11, 12, 13 |
| [E2. Learned keys with a soft load cap (C2)](E2_learned_placement.md) | Results; Table 1; Methods | 8 to 14 |
| [E3. Retiring old records at publication](E3_retiring_at_publication.md) | Results | 8 to 11, 13, 14 |
| [E4. Each part of dual migration](E4_parts_of_dual_migration.md) | Results; Table 2 | 8 to 11, 14 |
| [E5. Migration to completion and retirement rules](E5_migration_to_completion.md) | Results; Fig. 3 | 10, 11, 12, 14 |
| [E6. Dual migration on the original SRP keys](E6_original_srp_keys.md) | Results; Table 3; Fig. 4 | 14, 15 |
| [E7. Costs, payload, churn and peer failures](E7_costs_and_churn.md) | Results; Table 4 | 9, 11, 13, 14 |
| [E8. Mapping baselines](E8_mapping_baselines.md) | Results; Methods | 8, 9 |
| [E9. Supporting components (rounds 4 to 6)](E9_supporting_components.md) | Methods | 4, 5, 6 |
| [Setup: embedding spaces, migration policies and evaluation rounds](setup.md) | Methods | all |

**Conventions.** Each round followed an internal protocol fixed before it was run (`evo/PREREG_round<N>.md`,
committed with the tag of the round). Results tested against the criteria of that protocol are called prespecified;
the other analyses are exploratory, and analyses designed after seeing the corresponding results are called post hoc.
Unless stated otherwise, values are means over seeds, recall is in percent and differences are in percentage points
of recall, and intervals are 95% t intervals over paired seeds. Code 100k, code 20k and SciFact are the corpora named
`code100kfq`, `code` and `scifact` in file names. Figures and tables numbered without a letter are those of the paper.

**Reproducing.** The repository README describes the data preparation, the run script of each round and the tag at
which it is run. After the runs, return to `main` and run the analysis scripts named on each page from the repository
root; they print the values in the tables, which are given here as printed. The scripts read the result files that
the runs write to the repository root; these files are not tracked by git. The result files of the reported runs are
archived as a separate dataset ([10.5281/zenodo.24329447](https://doi.org/10.5281/zenodo.24329447));
extracting its archives into the repository root lets the scripts run without rerunning the simulations.
