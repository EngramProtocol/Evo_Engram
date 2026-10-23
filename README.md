# Evo-Engram

Code for the experiments in *Evo-Engram: Backward-Compatible Embedding-Model Migration for Decentralized
Semantic Search*.

Evo-Engram keeps a semantic distributed hash table searchable while its records are re-embedded with a new
model. Queries encoded with the new model $M_1$ reach legacy records through a backward routing map, storing
peers score legacy records with a forward map and a per-record normalization factor, candidate lists from the
two index epochs are merged with probability-calibrated fusion (PROB), and an authorized re-indexer migrates
records in the order suggested by query workloads.

The repository contains the retrieval probes that compute recall for every configuration, a discrete-event
Kademlia overlay simulator used for network costs and for recall under simulated iterative lookups, the
data-preparation scripts, the preregistration of the confirmatory evaluation, and the analysis scripts that
print the numbers reported in the article.

## Layout

```
evo/        Evo-Engram experiments: probes, simulator drivers, run scripts, analysis scripts,
            preregistration and checksum manifests
prepare/    corpus construction and embedding (CodeSearchNet, SciFact, fresh queries, paraphrases)
src/        discrete-event Kademlia overlay (SimPy): network, node and routing models
data/       corpora, embeddings, ground truth and PQ codebooks (not in git, see "Data")
```

The other files at the top level (`main_simulation*.py`, `run_*.sh`, `analyze_*.py`, figures) come from the
overlay-simulator project from which `src/` was taken (tag `base-v1.0-cc`); its documentation is kept in
`README_vengram_base.md`. They are not needed for the Evo-Engram results. `README_round4.md` and the
top-level `SHA256SUMS_*` files are historical notes and checksum lists of the round-4 code package; two of
these lists predate the final paraphrase prompt and no longer match `prepare/04_evo_colab_embed.py`.

### Scripts in `evo/`

| script | role | output |
|---|---|---|
| `01_embed_m1.py` | embeds a corpus and its queries with a target model $M_1$ and computes $M_1$ ground truth | `data/<ds>_<tag>_*` |
| `02_probe_bridge.py`, `03_probe_query_adapter.py`, `03b_probe_norm.py`, `04_probe_multiepoch.py` | development gates; their functions are imported by the later probes | `probeC_*`, `probeD_*`, `probeE_*`, `probeF_*` |
| `03c_probe_holdout.py` | legacy-index compatibility on held-out queries (H1), linear and MLP adapters | `probeH_*.json` |
| `04b_probe_multiepoch2.py` | fixed migration states $f$, all fusion rules, adapter refitting (H2, H3) | `probeG_*.json` |
| `05_bench_cpu.py` | CPU time and memory of query encoding, adapter and payload re-embedding | `bench_<tag>.json` |
| `06_probe_lazy.py` | Zipf query streams with static, lazy and background migration (H4), re-indexer limits, paraphrase workload | `probeL_*.json`, `probeLR_*.json` |
| `07_assemble_data.py` | checks the outputs of `prepare/04_evo_colab_embed.py` and assembles them into `data/` | `data/code100k_<tag>_*`, `data/code100kfq_*`, `data/*_arctic_*`, `data/*_para_*`, `data/MANIFEST_round4.sha256` |
| `08_sim_evo.py` | network and computation costs in the overlay simulator (cost-accounting mode) | `probeS_*.json` |
| `09_sim_e2e.py` | recall computed from the peer sets returned by simulated iterative lookups; schedule replay | `probeE2E_*.json`, `probeE2F_*.json` |
| `me_common.py` | shared code: fusion rules, calibration, cross-fitting, adapters | |

Code comments, log messages and the round notes (`README_round*.md`, `RUN.md`) are in Vietnamese. The probes
used in the article (`03c`, `04b`, `06`, `08`, `09`) print self-checks on lines that start with `>>>`; the
round scripts collect these lines into `evo/round*_all.txt`.

## Versions

Each experiment round is frozen at a tag. The run script of a round stops if a file listed in the round's
checksum manifest has changed.

| tag | commit | content | run script | manifest |
|---|---|---|---|---|
| `evo-confirm-v1` | `20e303e` | preregistered confirmatory evaluation (round 4) and its exploratory parts | `evo/run_round4.sh` | `evo/SHA256SUMS_round4` (11 files: probes, `me_common.py`, `08_sim_evo.py`, preregistration, scoring and run script) |
| `evo-r5-v1` | `84453a2` | adapters fitted on PQ reconstructions; recall under simulated iterative lookups (round 5) | `evo/run_round5.sh` | `evo/SHA256SUMS_round5` (16 files, including `src/`) |
| `evo-r6-v1` | `e1cd33d` | migration-schedule replay, seven additional bge-base seeds, PQ adapters with simulated lookups (round 6) | `evo/run_round6.sh` | `evo/SHA256SUMS_round6` (16 files, including `src/`) |
| `base-v1.0-cc` | `4c290c8` | overlay simulator before any Evo-Engram code | | |

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
not record the revision at embedding time.

The shell scripts assume that the repository is checked out at `~/Evo_Engram`. The round-4 to round-6 scripts
accept `EVO_ROOT=<path>`; the others (`run_embed*.sh`, `run_round2.sh`, `run_round3*.sh`, `run_gate*.sh`)
change to `~/Evo_Engram` unconditionally. The commands below set `EVO_ROOT` and call the Python scripts
directly where possible.

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

## Running the experiments

Result files are written to the repository root and are not tracked by git; logs and summaries go to `evo/`.
Run each round under `tmux` or `nohup`. `P=<n>` sets the number of parallel jobs (default 2 in rounds 4
and 5, 4 in round 6; round 5 uses `PB` for its simulator phase).

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

The preregistered hypotheses and pass criteria are in `evo/PREREG_round4.md` and are scored by
`evo/analyze_prereg.py`.

## Mapping to the article

After the runs, return to the branch head (`git checkout main`), which holds this README and
`evo/analyze_accounting.py`, and run the analysis scripts in the repository root. The quoted patterns keep
the full-embedding results, the PQ-adapter results (`*_pq.json`) and the development results apart; the
scripts average every file that matches.

| article | command |
|---|---|
| model transitions (angle, top-5 overlap); fresh-query and paraphrase statistics | printed by `evo/07_assemble_data.py` (`evo/assemble_round4.log`) and `prepare/04_evo_colab_embed.py` (`$OUT/log_colab.txt`, `$OUT/fresh_queries.json`) |
| outcomes against the preregistered criteria (H1 to H4) | `python3 evo/analyze_prereg.py` |
| H1: adapter versus dual encoder on held-out queries | `python3 evo/analyze_03.py "probeH_code100kfq_*_ho1.json"` and `python3 evo/analyze_03.py "probeH_arctic_*_ho1.json" "probeH_scifact_arctic_*_ho1.json"` |
| H2, H3: recall versus migrated fraction, multi-epoch outcomes, fusion baselines (PROB, RRF, CAL, SD, PROP), native index against the legacy path | `python3 evo/analyze_04b.py "probeG_code100kfq_*_s[0-9].json"` and `python3 evo/analyze_04b.py "probeG_arctic_s[0-9].json" "probeG_scifact_arctic_s[0-9].json"`; development rows: `python3 evo/analyze_04b.py "probeG_bgebase_s*.json" "probeG_e5large_s*.json"` |
| adapters fitted on PQ reconstructions | `python3 evo/analyze_r5.py a` |
| H4: Zipf stream and recall over the stream | `python3 evo/analyze_06.py "probeL_code100kfq_*_ku.json"` and `python3 evo/analyze_06.py "probeL_arctic_*_ku.json" "probeL_scifact_arctic_*_ku.json"` |
| paraphrase workload, re-indexer limits (supplementary) | `python3 evo/analyze_06b.py "probeLR_*.json"` |
| simulated network and computation costs, fixed states and stream | `python3 evo/analyze_08.py "probeS_*.json"` |
| client CPU time and model memory | `bench_<tag>.json` (written by `evo/05_bench_cpu.py`) |
| recall under simulated iterative lookup, fixed states and stream | `python3 evo/analyze_r5.py b`, run before round 6 or in a directory that holds only `probeE2E_*[0-9].json` (round 6 adds `probeE2E_*_pq.json`, which this script would also average) |
| schedule replay, ten bge-base seeds, PQ adapters with simulated lookups | `python3 evo/analyze_r6.py` |
| first-order accounting of lazy versus background migration (Discussion) | `python3 evo/analyze_accounting.py` |

The development-corpus rows come from several sources: the native-index and accounting rows from the
development rounds (`probeG_<tag>_s<seed>.json`, `probeL_<tag>_s<seed>_ku.json`), the 20k cost rows from the
round-4 files `probeS_bgebase_s*.json`, the paraphrase and re-indexer tables from the round-4 files
`probeLR_*.json`, and the 20k rows of the simulated-lookup tables from the round-5 files
`probeE2E_bgebase_s*.json`. The two figures of recall against the migrated fraction and over the stream were
drawn from the per-fraction and per-window values printed by `evo/analyze_04b.py` and `evo/analyze_06.py`.

## Citation

If you use this code, please cite the article. Citation details will be added on publication.
