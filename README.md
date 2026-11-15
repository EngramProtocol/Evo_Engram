# Evo-Engram

Code for the experiments in the manuscript *Coordinating record placement and retirement limits recall loss
when a decentralized semantic index changes its embedding model*, by Nam-Khanh Tran, Mau-Tra Nguyen and
Binh Minh Nguyen.

In a semantic distributed hash table (DHT), the embedding of an object decides both how its index records
score and which peers store them. When the embedding model is replaced, re-embedding an object moves its
records, and a record that was published correctly can still be missed by later queries. Evo-Engram is a
migration design for this setting in which clients run only the new model $M_1$. It has three parts:

- **Collision model (C1).** From a re-embedded sample $S$ of the corpus and a sample of queries, it estimates
  how unevenly sign random projection (SRP) keys will load the peers, and the query bucket fraction $q_f$,
  the share of the corpus that falls into the bucket of a query's own key. A threshold on $q_f$ chooses
  between the original SRP keys and learned placement.
- **Learned placement with a load cap (C2).** The keys of the new epoch are learned on the same sample (ITQ
  with median thresholds). Each peer takes at most 16 times the mean load of a table, and an overflowing
  record goes to another of the $K = 20$ peers closest to its key, so keys, routing and the number of
  contacted peers stay unchanged.
- **Dual migration (C3).** The legacy record of a re-embedded object is kept, with the new PQ code attached,
  until the legacy epoch is drained, while the rest of the corpus is migrated in the background. Rules that
  retire legacy records earlier, after sightings through the new keys, are evaluated against it.

A query adapter, through which $M_1$ queries reach legacy peers and legacy peers score their records, and a
probabilistic rule (PROB) that merges the candidate lists of the two index epochs come from the first version
of the design, evaluated in rounds 4 to 6. The current design uses them as infrastructure.

All results come from simulation. The repository contains the retrieval probes, the placement and migration
simulators, a discrete-event Kademlia overlay simulator, the data preparation scripts, the preregistration
and checksum manifest of each evaluation round, and the analysis scripts that print the numbers reported in
the manuscript.

## Layout

```
evo/        Evo-Engram experiments: probes, simulators, run scripts, analysis scripts,
            preregistrations, round notes and checksum manifests
prepare/    corpus construction and embedding (CodeSearchNet, SciFact, fresh queries, paraphrases)
src/        discrete-event Kademlia overlay (SimPy): network, node and routing models
data/       corpora, embeddings, ground truth and PQ codebooks (not in git, see "Data")
```

The other files at the top level (`main_simulation*.py`, `run_*.sh`, `analyze_*.py`, figures) come from the
overlay-simulator project from which `src/` was taken (tag `base-v1.0-cc`); its documentation is kept in
`README_vengram_base.md`. They are not needed for the Evo-Engram results. `README_round4.md` and the
top-level `SHA256SUMS_*` files are historical notes and checksum lists of the round-4 code package; two of
these lists predate the final paraphrase prompt and no longer match `prepare/04_evo_colab_embed.py`.

Code comments, log messages, the round notes (`evo/README_round*.md`, `evo/RUN.md`) and the preregistrations
(`evo/PREREG_round*.md`) are in Vietnamese. This README summarizes them, the manuscript describes the
hypotheses and their pass criteria in English, and the section "Reading the logs" translates the status
words that the scripts print.

### Scripts in `evo/`

| script | role | output |
|---|---|---|
| `01_embed_m1.py` | embeds a corpus and its queries with a target model $M_1$ and computes $M_1$ ground truth | `data/<ds>_<tag>_*` |
| `02_probe_bridge.py`, `03_probe_query_adapter.py`, `03b_probe_norm.py`, `04_probe_multiepoch.py` | development gates; their functions are imported by the later probes | `probeC_*`, `probeD_*`, `probeE_*`, `probeF_*` |
| `03c_probe_holdout.py` | legacy-index compatibility on held-out queries, linear and MLP adapters (round 4) | `probeH_*.json` |
| `04b_probe_multiepoch2.py` | fixed migration states $f$, all fusion rules, adapter refitting (round 4) | `probeG_*.json` |
| `05_bench_cpu.py` | CPU time and memory of query encoding, adapter and payload re-embedding | `bench_<tag>.json` |
| `06_probe_lazy.py` | Zipf query streams with static, lazy and background migration, re-indexer limits, paraphrase workload (round 4) | `probeL_*.json`, `probeLR_*.json` |
| `07_assemble_data.py` | checks the outputs of `prepare/04_evo_colab_embed.py` and assembles them into `data/` | `data/code100k_<tag>_*`, `data/code100kfq_*`, `data/*_arctic_*`, `data/*_para_*`, `data/MANIFEST_round4.sha256` |
| `08_sim_evo.py` | network and computation costs in the overlay simulator (cost-accounting mode) | `probeS_*.json` |
| `09_sim_e2e.py` | recall computed from the peer sets returned by simulated iterative lookups; schedule replay (rounds 5 and 6) | `probeE2E_*.json`, `probeE2F_*.json` |
| `10_probe_placement.py` | native index of one epoch under each placement (SRP, centered SRP, PCA, ITQ, each with or without a load cap) over a grid of tables and probes, with per-peer storage and query load; with `--aniso-only 1`, the collision model alone (C1, C2; rounds 7 to 12 and 14) | `probeP*.json`, `probeA*.json` |
| `11_probe_safe.py` | migration policies on a query stream or until the migration completes, optionally with churn and peer failures (C3; rounds 7 to 15) | `probeV*.json` |
| `12_diag_itq.py` | diagnosis of the hot spot of ITQ placement (round 9) | `diagITQ_*.json` |
| `13_qf_deployable.py` | $p$ and $q_f$ re-estimated from the sample $S$ and the validation queries only (round 13) | `probeQ13_*.json` |
| `13_lookup_rank.py` | reach of iterative lookups by XOR rank among the $K$ peers closest to a key (round 13) | `probeL13_*.json` |
| `rerun_prev.py` | reruns a job of an earlier round with the current code, from the arguments stored in its result file, and compares every number (rounds 11 to 15) | |
| `me_common.py` | shared code: fusion rules, calibration, cross-fitting, adapters | |
| `run_round*.sh`, `analyze_*.py` | run script and analysis script of each round (see "Versions" and "Mapping to the manuscript") | `evo/r<N>_logs/`, `evo/round<N>_all.txt` |

The probes print self-checks on lines that start with `>>>`; the run scripts collect these lines, together
with any mismatch, into `evo/round<N>_all.txt`.

### Names in file names and logs

| kind | name in the code | meaning |
|---|---|---|
| corpus | `code100kfq` | 100,000 CodeSearchNet functions with the 500 fresh queries (code 100k in the manuscript) |
| | `code100k` | the same corpus with the development queries |
| | `code` | 20,000 CodeSearchNet functions (code 20k) |
| | `scifact` | SciFact, 5,183 abstracts |
| model | `m0` | legacy model $M_0$, `BAAI/bge-large-en-v1.5` |
| | `bgebase`, `e5large`, `arctic`, `gtebase`, `minilm`, `mpnet`, `arcticxs`, `bgesmall`, `gtesmall`, `e5small` | target models $M_1$ (see "Requirements") |
| placement | `srp`, or `u` for the new epoch in `11_probe_safe.py` | original SRP keys, no centering |
| | `srp_c`, `pca_q`, `itq_q` | centered SRP; PCA with a random rotation; ITQ (learned placement) |
| | `itq<k>_q` | ITQ on $k$ principal components, 63 bits kept |
| | `<v>+cap<m>`, `_cap<m>` in file names | placement `<v>` with each peer capped at $m$ times the mean load of a table |

Migration policies, as named in the manuscript (Supplementary Table S50) and in the code:

| manuscript | code |
|---|---|
| static, full, rebuild, lazy, bg | `static`, `full`, `rebuild`, `lazy`, `bg` |
| lazy+bg, map-all, map-keep | `lazybg`, `mapall`, `mapkeep` |
| dual migration with rule drain | `lazyVbgDinf` |
| dual migration with rules k1, k2, k3 | `lazyVbgD`, `lazyVbgDk2`, `lazyVbgDk3` |
| dual migration with rules u2, v2, uv2, uv3 | `lazyVbgDu2`, `lazyVbgDv2`, `lazyVbgDuv2`, `lazyVbgDuv3` |
| ablation variants: lazy+delay, dual with background retired, dual without attached code, lazy+keep | `lazyV1`, `lazyVbg`, `lazyVbgD_adp`, `lazyD` |

## Versions

Each evaluation round is frozen at a tag. The run script of a round stops if a file listed in the round's
checksum manifest has changed. Round `<N>` has the run script `evo/run_round<N>.sh` and the manifest
`evo/SHA256SUMS_round<N>`; rounds 5 to 15 have a note `evo/README_round<N>.md`; and the confirmatory rounds
have a preregistration `evo/PREREG_round<N>.md`, committed with the tag before any job of the round was run.
From round 8 on, each round includes a regression phase R that reruns jobs of an earlier round with the new
code and requires every number to match.

| tag | commit | round | content | criteria met |
|---|---|---|---|---|
| `base-v1.0-cc` | `4c290c8` | | overlay simulator before any Evo-Engram code | |
| `evo-confirm-v1` | `20e303e` | 4 | confirmatory evaluation of the supporting components (adapter, fusion rule, refitting, lazy order) and its exploratory parts | 15/20 |
| `evo-r5-v1` | `84453a2` | 5 | exploratory: adapters fitted on PQ reconstructions; recall under simulated iterative lookups | |
| `evo-r6-v1` | `e1cd33d` | 6 | exploratory: migration schedule replay, seven more bge-base seeds, PQ adapters with simulated lookups | |
| `evo-r7-pilot` | `56a2ac1` | 7 | exploratory pilot of C1 to C3: collision model, placement study, retirement after confirmation | |
| `evo-r7b-pilot` | `0aff9cd` | 7b | exploratory pilot: equal re-embedding budget, migration on learned placement, angular collision formula | |
| `evo-r8-prereg` | `50cb7ce` | 8 | H1 to H5: C1 on three corpora, C2 and C3 on code 100k; baselines full and map-all | 19/20 |
| `evo-r9-prereg` | `9c9fd5c` | 9 | H6 to H8: C3 on code 20k and SciFact; exploratory: churn and peer failures, map-keep, the ITQ hot spot | 18/24 |
| `evo-r10-prereg` | `08fcb1d` | 10 | H9, H10: load cap, C3 on capped placement; exploratory: migration to completion | 19/19 |
| `evo-r11-prereg` | `74a5cf8` | 11 | H11 to H17: C3 ablation, completion against rebuild and draining, mechanism of C2, two new model families, payload | 85/109 |
| `evo-r11-fix1` | `a5fce21` | 11 | amendment 1 of round 11: embeddings computed in float32, because the `thenlper/gte-base` checkpoint is stored in float16 (section 5 of `evo/PREREG_round11.md`) | |
| `evo-r12-prereg` | `b420492` | 12 | H18 to H21: stronger retirement evidence, placement rule on $q_f$, C1 and C2 on five new models | 52/63 |
| `evo-r13-prereg` | `28c15d0` | 13 | exploratory: $p$ and $q_f$ estimated from $S$ and the validation queries, lookup reach by XOR rank, cost of drain on the code 100k stream | |
| `evo-r14-prereg` | `fa53949` | 14 | H22 to H24: drain to completion on new seeds, drain on the stream for three more models, C3 on the original SRP keys; exploratory: full with the peers of two epochs, churn with drain, 5,000 peers | 130/130 |
| `evo-r15-prereg` | `fd561ec` | 15 | H25: C3 to completion on the original SRP keys; exploratory: two more models, equal progress, a background twice as fast | 68/68 |

Round 4 numbers its hypotheses H1 to H4 in `evo/PREREG_round4.md`; the manuscript calls them S1 to S4 to keep
them apart from H1 to H25 of rounds 8 to 15. Round 13 is exploratory and has no preregistration, although
its tag carries the same suffix as the others; the rules for reading its results were fixed in
`evo/README_round13.md` at the tag, before the run.

The tags `evo-r5-v1` and `evo-r6-v1` were re-created on 22 October 2026 after the commit messages were edited.
The run logs of rounds 5 and 6 therefore show the earlier commits `1f60f31` and `19c1933`; the files are
identical, and the manifests pass at the current tags.

The development rounds that precede the confirmatory evaluation (`evo/run_gate*.sh`, `evo/run_round2.sh`,
`evo/run_round3.sh`, `evo/run_round3b.sh`) were run before the code was frozen and are not tagged.

## Requirements

The reported runs used one CPU server with 4 cores and 31 GB of memory, with Python 3 and the packages
below. No GPU is required; the embedding steps can use one.

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt                 # numpy, faiss-cpu, simpy: probes and simulator
pip install torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu   # CPU build, as in the runs
pip install -r requirements-embed.txt           # transformers, sentence-transformers, ...: embedding only
```

`requirements-embed.txt` pins the versions recorded in the round-4 log (torch 2.14.0 CPU build, transformers
5.17.0, sentence-transformers 6.1.0). If `faiss` is missing, the probes fall back to a NumPy k-means that is
only suitable for smoke tests.

Models are public Hugging Face checkpoints. The revisions present in the server's model cache on
19 October 2026 were:

| role | model | revision |
|---|---|---|
| $M_0$ (legacy) | `BAAI/bge-large-en-v1.5` | `d4aa6901d3a41ba39fb536a557fa166f842b0e09` |
| $M_1$ | `BAAI/bge-base-en-v1.5` | `a5beb1e3e68b9ab74eb54cfd186867f64f240e1a` |
| $M_1$ | `intfloat/e5-large-v2` | `f169b11e22de13617baa190a028a32f3493550b6` |
| $M_1$ | `Snowflake/snowflake-arctic-embed-m-v1.5` | `e58a8f756156a1293d763f17e3aae643474e9b8a` |
| paraphrases | `Qwen/Qwen2.5-3B-Instruct` | `aa8e72537993ba99e69dfaafa59ed015b17504d1` |

The cache held one snapshot of each model, which is very likely the one used for embedding, but the logs do
not record the revision at embedding time. Rounds 11 and 12 added seven target models, which their run
scripts embed (see "Data"); their revisions were not recorded:

| round | tag | model |
|---|---|---|
| 11 | `minilm` | `sentence-transformers/all-MiniLM-L6-v2` |
| 11 | `gtebase` | `thenlper/gte-base` |
| 12 | `e5small` | `intfloat/e5-small-v2` |
| 12 | `gtesmall` | `thenlper/gte-small` |
| 12 | `bgesmall` | `BAAI/bge-small-en-v1.5` |
| 12 | `mpnet` | `sentence-transformers/all-mpnet-base-v2` |
| 12 | `arcticxs` | `Snowflake/snowflake-arctic-embed-xs` |

The shell scripts assume that the repository is checked out at `~/Evo_Engram`. The run scripts of rounds 4
to 15 accept `EVO_ROOT=<path>`; the others (`run_embed*.sh`, `run_round2.sh`, `run_round3*.sh`,
`run_gate*.sh`) change to `~/Evo_Engram` unconditionally. The commands below set `EVO_ROOT` and call the
Python scripts directly where possible.

## Data

Corpora, embeddings, ground truth, query sets, paraphrases and PQ codebooks are not redistributed; the
largest embedding matrices exceed GitHub's file-size limit. All of them are rebuilt from public sources,
CodeSearchNet (`code-search-net/code_search_net` on Hugging Face) and SciFact (`BeIR/scifact`). The steps
compare their outputs with what earlier steps wrote. k-means and model inference are not bit-exact across
machines, so a rebuild reproduces the reported numbers closely but not exactly; the original artifacts are
available from the corresponding author on request.

1. **Legacy corpora and $M_0$ index.** Run `prepare/01_build_corpora.ipynb` and then
   `prepare/02_extend_weakscaling.ipynb` (written for Colab, about 2 h on a T4 GPU; see `prepare/README.md`
   for running them elsewhere, the corpus rules and the fixed settings, seed 20235956). They write the
   CodeSearchNet 20k and 100k corpora and SciFact with $M_0$ embeddings and exact top-10 ground truth to the
   notebook's output directory; copy those files into `data/`. The notebooks build the $m = 512$ PQ codebook
   only for the 50k and 100k corpora. Build it for the 20k corpus and SciFact with:

   ```bash
   python3 prepare/03_build_pq.py --data-dir data --corpus code
   python3 prepare/03_build_pq.py --data-dir data --corpus scifact
   ```

2. **$M_1$ embeddings of the 20k corpus and SciFact** for bge-base and e5-large:

   ```bash
   for d in code scifact; do
     python3 evo/01_embed_m1.py --dataset $d --model BAAI/bge-base-en-v1.5 --tag bgebase --device cpu
     python3 evo/01_embed_m1.py --dataset $d --model intfloat/e5-large-v2  --tag e5large --device cpu
   done
   ```

3. **CPU benchmarks** used by the cost simulations (run alone, so that timings are not disturbed):

   ```bash
   python3 evo/05_bench_cpu.py --m1 BAAI/bge-base-en-v1.5 --tag bgebase
   python3 evo/05_bench_cpu.py --m1 intfloat/e5-large-v2  --tag e5large
   ```

   `bench_arctic.json` is produced by `evo/run_round4.sh` itself.

4. **Confirmatory data.** `prepare/04_evo_colab_embed.py` recovers the docstrings of the 100k corpus, selects
   500 fresh CodeSearchNet queries (seed 20261010), embeds the corpus and queries with the three $M_1$ models,
   embeds SciFact with Arctic, and generates five paraphrases for 300 evaluation queries with
   Qwen2.5-3B-Instruct (greedy decoding, plus one seeded sampled generation when fewer than five paraphrases
   pass the filter). `evo/07_assemble_data.py` checks these outputs against `data/` and writes the
   `code100kfq_*` (fresh queries), `*_arctic_*` and `*_para_*` files; `data/MANIFEST_round4.sha256` lists
   everything it wrote. `evo/run_round4_all.sh` chains both steps and then runs round 4:

   ```bash
   git checkout evo-confirm-v1
   EVO_ROOT=$PWD VD=$PWD/data OUT=$HOME/evo_out SKIP_R4=1 bash evo/run_round4_all.sh
   ```

   With `SKIP_R4=1` it stops after assembling the data. The embedding step took about a day on the 4-core
   server and resumes where it stopped; it can also run on Colab (see the header of
   `prepare/04_evo_colab_embed.py`). In the reported runs `VD` was a separate copy of the step-1 files linked
   into `data/`; pointing it at `data/` itself is also supported.

5. **Models added in rounds 11 and 12.** Phase E of `evo/run_round11.sh` and `evo/run_round12.sh` embeds the
   corpora with the new models through `evo/01_embed_m1.py` and skips pairs whose files are already in
   `data/`: MiniLM on code 100k, code 20k and SciFact and gte-base on code 20k and SciFact in round 11, and
   the five models of round 12 on code 20k and SciFact. This phase needs `requirements-embed.txt` and access
   to the Hugging Face Hub.

Steps 1 to 4 provide every input of rounds 4 to 10. In rounds 7 to 15, jobs whose inputs are missing are
skipped and logged as `bỏ qua` (skipped), so check the job counts given below.

## Running the experiments

Result files are written to the repository root and are not tracked by git; logs and summaries go to `evo/`.
Run each round under `tmux` or `nohup`, in the same checkout, and in the order of the tables below: the
self-checks and regression phases read the result files of earlier rounds from the repository root, and
round 13 re-estimates the collision quantities from the files of rounds 11 and 12, while round 15 compares
with the learned-placement runs of round 14. The header of each run script lists the files it needs.

### Rounds 3 to 6

`P=<n>` sets the number of parallel jobs (default 2 in rounds 4 and 5, 4 in round 6; round 5 uses `PB` for its
simulator phase).

| step | commands | outputs | time on the 4-core server |
|---|---|---|---|
| development round 3 and 3b | `git checkout evo-confirm-v1 && bash evo/run_round3.sh && bash evo/run_round3b.sh` | development `probeG_`, `probeH_`, `probeL_<tag>_s<seed>_ku.json` | not recorded |
| round 4, confirmatory | `git checkout evo-confirm-v1 && EVO_ROOT=$PWD bash evo/run_round4.sh` | `probeH_`, `probeG_`, `probeL_`, `probeLR_`, `probeS_*.json`; `evo/round4_all.txt` | 6.4 h |
| round 5 | `git checkout evo-r5-v1 && EVO_ROOT=$PWD bash evo/run_round5.sh` | `*_pq.json`, `probeE2E_*.json`; `evo/round5_all.txt` | 5.4 h |
| round 6 | `git checkout evo-r6-v1 && EVO_ROOT=$PWD bash evo/run_round6.sh` | `probeE2F_*.json`, `probeE2E_*_pq.json`; `evo/round6_all.txt` | 5.6 h |

Round 4 is also started by `evo/run_round4_all.sh` when `SKIP_R4` is not set; do not run it twice.
Rounds 5 and 6 use the outputs of the earlier rounds for their self-checks and stop if they are missing; round 5
also needs the development outputs `probeG_bgebase_s{20235956,1,2}.json`. The development round scripts are
kept as they were run. At `evo-confirm-v1` the probe versions they check match, and they warn about missing
gate outputs (`probeE_*`, `probeF_*`), which only disables some of their self-checks. They change to
`~/Evo_Engram`, and their output has not been re-verified against the original development runs.

### Rounds 7 to 15

Each round is run at its tag with `git checkout <tag> && EVO_ROOT=$PWD bash evo/run_round<N>.sh`. The run
script ends with the analysis of the round and writes the summary to `evo/round<N>_all.txt`.

| round | tag | outputs | jobs | estimated time |
|---|---|---|---|---|
| 7 | `evo-r7-pilot` | `probeP_*`, `probeV_*` | 47 | 6 to 8 h |
| 7b | `evo-r7b-pilot` | `probeVB_*`, `probeA_*`, `probeL_code100kfq_e5large_s3_ku_r7b.json` | 31 | 2 h |
| 8 | `evo-r8-prereg` | `probeVR_*`, `probeV8_*`, `probeP_*` and `probeA_*` for seeds 6 to 8 | 119 | 6 to 7 h |
| 9 | `evo-r9-prereg` | `probeVR9*`, `probeV9X_*`, `probeV9_*`, `probeP9_*`, `diagITQ_*` | 116 | 5 h |
| 10 | `evo-r10-prereg` | `probePR10_*`, `probeVR10_*`, `probeP10_*`, `probeV10_*`, `probeV10F_*` | 104 | 5 to 6 h |
| 11 | `evo-r11-fix1` | `probePR11_*`, `probeVR11*`, `probeA11_*`, `probeP11_*`, `probeV11_*`, `probeV11F_*`, `probeV11G_*`, `probeV11C_*` | 319 | 10 to 14 h |
| 12 | `evo-r12-prereg` | `probeVR12*`, `probeA12_*`, `probeP12_*`, `probeV12F_*` | 244 | 3 to 4 h |
| 13 | `evo-r13-prereg` | `probeVR13F_*`, `probeV13_*`, `probeQ13_*`, `probeL13_*` | 138 | 1 to 1.5 h |
| 14 | `evo-r14-prereg` | `probeVR14_*`, `probeV14U_*`, `probeV14F_*`, `probeV14_*`, `probeV14C_*`, `probeV14B_*`, `probeP14_*` | 185 | 7 to 9 h |
| 15 | `evo-r15-prereg` | `probeVR15_*`, `probeV15U_*` | 101 | 1 to 2 h |

The times are the estimates written in the round notes before each run, with four parallel jobs.

- `P=<n>` sets the number of parallel jobs (default 4), and `PHASES="..."` runs only some phases; the
  phases are listed in the header of each run script. From round 11 on, `PHASES=S` reruns only the analysis
  and rebuilds `evo/round<N>_all.txt`.
- Round 11 is run at `evo-r11-fix1` with `NTE=<number of cores>`:
  `git checkout evo-r11-fix1 && EVO_ROOT=$PWD NTE=4 bash evo/run_round11.sh`. The script then warns that
  HEAD is not at `evo-r11-prereg`, which is expected; the manifest check passes at this tag. Without `NTE`,
  the embedding phase runs on one thread, because the script counts the cores after setting
  `OMP_NUM_THREADS=1` (section 5 of `evo/PREREG_round11.md`).
- Rounds 14 and 15 resume an interrupted run with `SKIP_DONE=1` and refuse to start while another run of
  the same round is alive.
- From round 11 on, every job command is appended to `evo/r<N>_logs/all_jobs.txt`, so a single job can be
  rerun exactly; the round notes show how.

## Reading the logs

| printed | meaning |
|---|---|
| `ĐẠT`, `KHÔNG ĐẠT`, `KHÔNG CHẠY` | criterion met, not met, not run |
| `TÓM TẮT ĐÁNH GIÁ` | summary of the preregistered criteria |
| `THĂM DÒ` | exploratory analysis |
| `ĐỌC` | reading of an exploratory result under rules fixed before the run |
| `Tự kiểm` | self-checks |
| `KHỚP`, `LỆCH`, `lệch` | match, mismatch |
| `THIẾU`, `bỏ qua` | missing file, skipped |
| `CẢNH BÁO`, `DỪNG` | warning, stopped |
| `mã thoát`, `XONG` | exit code, finished |
| `đợt`, `pha` | round, phase |

## Mapping to the manuscript

Figure and table numbers refer to the submitted manuscript and its Supplementary Information. After the runs,
return to the branch head (`git checkout main`) and run the analysis scripts in the repository root. The
analysis scripts of rounds 7 to 15 on `main` are identical to those at the round tags. They read the result
files of their round, and of earlier rounds where they compare. From round 8 on, they take the seed and model
lists from the same environment variables as the run scripts, with the values of the round as defaults, so
files of other rounds with the same prefix are not mixed in. Figures 2 to 4 and Supplementary Figures S1 to
S3 plot values printed by these scripts.

### Contributions C1 to C3 (rounds 7 to 15)

| round | command | manuscript |
|---|---|---|
| 7, 7b | `python3 evo/analyze_r7.py`, `python3 evo/analyze_r7b.py`, run before round 8, which writes `probeP_*` and `probeA_*` files for seeds 6 to 8 that these scripts would also read | pilots, listed in Supplementary Table S51 |
| 8 | `python3 evo/analyze_r8.py` | H1 to H5: collision model on three corpora (Supplementary Table S1); learned placement against SRP (Table 1, Supplementary Table S2); C3 and map-all on code 100k (Results; Supplementary Tables S6, S8) |
| 9 | `python3 evo/analyze_r9.py` | H6 to H8: C3 on code 20k and SciFact (Supplementary Table S7); map-keep (Supplementary Table S8); churn and peer failures (Supplementary Table S12); ITQ on more components (Supplementary Table S3) |
| 10 | `python3 evo/analyze_r10.py` | H9, H10: load cap (Table 1, Supplementary Table S2); C3 on capped placement (Supplementary Table S6) |
| 11 | `python3 evo/analyze_r11.py` | H11: each part of dual migration (Table 2) and stream costs (Table 4); H12: completion against rebuild and draining (Supplementary Table S9); H13 to H16: mechanism of C2, C1 on new pairs and the new model families (Table 1, Supplementary Tables S1, S4); placements at equal probes (Supplementary Table S27); H17 and payload by query repetition (Supplementary Tables S11, S43); churn (Supplementary Table S12); lost paths and negative flips (Supplementary Table S48); the pairs from which the placement rule was derived (Fig. 2b) |
| 12 | `python3 evo/analyze_r12.py` | H18: retirement rules (Fig. 3, Supplementary Tables S10, S45); H19: placement rule (Fig. 2b, Table 1, Supplementary Table S5); H20, H21: C2 and C1 on five new models (Table 1, Supplementary Tables S1, S4, S49) |
| 13 | `python3 evo/analyze_r13.py` | collision quantities estimated from $S$ and the validation queries (Fig. 2a, Table 1, Supplementary Table S1); lookup reach by XOR rank (Supplementary Table S26); drain on the code 100k stream (Table 4, Supplementary Tables S43, S48) |
| 14 | `python3 evo/analyze_r14.py` | H22: drain to completion on new seeds (Supplementary Table S31); H23 (Supplementary Tables S28, S29); H24: C3 on the original SRP keys (Supplementary Tables S30, S42); full with 16 probes per table (Table 4); churn with drain (Supplementary Table S32); 5,000 peers (Supplementary Table S33); drain in Supplementary Table S48 |
| 15 | `python3 evo/analyze_r15.py` | H25 (Table 3, Supplementary Tables S34, S35); the old path against $q_f$ (Fig. 4, Supplementary Table S41); every policy (Supplementary Tables S36, S37); equal progress and a faster background (Supplementary Tables S38, S39); Arctic and MiniLM (Supplementary Table S40) |

### Supporting components (rounds 4 to 6)

The quoted patterns keep the full-embedding results, the PQ-adapter results (`*_pq.json`) and the
development results apart; the scripts average every file that matches.

| manuscript | command |
|---|---|
| model transitions (angle, top-5 overlap); fresh-query and paraphrase statistics | printed by `evo/07_assemble_data.py` (`evo/assemble_round4.log`) and `prepare/04_evo_colab_embed.py` (`$OUT/log_colab.txt`, `$OUT/fresh_queries.json`) |
| outcomes against the preregistered criteria S1 to S4 (Supplementary Table S44) | `python3 evo/analyze_prereg.py` |
| S1: adapter versus dual encoder on held-out queries (Supplementary Table S13) | `python3 evo/analyze_03.py "probeH_code100kfq_*_ho1.json"` and `python3 evo/analyze_03.py "probeH_arctic_*_ho1.json" "probeH_scifact_arctic_*_ho1.json"` |
| S2, S3: recall versus migrated fraction, multi-epoch outcomes, fusion baselines (PROB, RRF, CAL, SD, PROP), native index against the legacy path (Supplementary Fig. S1, Tables S14, S15, S17) | `python3 evo/analyze_04b.py "probeG_code100kfq_*_s[0-9].json"` and `python3 evo/analyze_04b.py "probeG_arctic_s[0-9].json" "probeG_scifact_arctic_s[0-9].json"`; development rows: `python3 evo/analyze_04b.py "probeG_bgebase_s*.json" "probeG_e5large_s*.json"` |
| adapters fitted on PQ reconstructions (Supplementary Methods) | `python3 evo/analyze_r5.py a` |
| S4: Zipf stream and recall over the stream (Supplementary Table S16, Fig. S2) | `python3 evo/analyze_06.py "probeL_code100kfq_*_ku.json"` and `python3 evo/analyze_06.py "probeL_arctic_*_ku.json" "probeL_scifact_arctic_*_ku.json"` |
| paraphrase workload, re-indexer limits (Supplementary Tables S18, S19) | `python3 evo/analyze_06b.py "probeLR_*.json"` |
| simulated network and computation costs, fixed states and stream (Supplementary Tables S20, S21) | `python3 evo/analyze_08.py "probeS_*.json"` |
| client CPU time and model memory (Supplementary Methods) | `bench_<tag>.json` (written by `evo/05_bench_cpu.py`) |
| recall under simulated iterative lookup, fixed states and stream (Supplementary Tables S22, S23) | `python3 evo/analyze_r5.py b`, run before round 6 or in a directory that holds only `probeE2E_*[0-9].json` (round 6 adds `probeE2E_*_pq.json`, which this script would also average) |
| schedule replay, ten bge-base seeds, PQ adapters with simulated lookups (Supplementary Table S24) | `python3 evo/analyze_r6.py` |
| first-order accounting of lazy versus background migration (Supplementary Table S25, Fig. S3) | `python3 evo/analyze_accounting.py` |

The development-corpus rows come from several sources: the native-index and accounting rows from the
development rounds (`probeG_<tag>_s<seed>.json`, `probeL_<tag>_s<seed>_ku.json`), the 20k cost rows from the
round-4 files `probeS_bgebase_s*.json`, the paraphrase and re-indexer tables from the round-4 files
`probeLR_*.json`, and the 20k rows of the simulated-lookup tables from the round-5 files
`probeE2E_bgebase_s*.json`.

## License

The code is released under the MIT License (see `LICENSE`). The datasets and models used in the experiments
are not part of this repository and remain under their own licenses.

## Citation

If you use this code, please cite the manuscript; the reference will be added here once it is published.
To cite the code itself, use the metadata in `CITATION.cff`, which GitHub shows under "Cite this repository".
