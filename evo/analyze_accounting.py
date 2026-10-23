#!/usr/bin/env python3
"""Post-hoc first-order accounting of lazy versus background migration (Discussion, Eq. (accounting)).

For each configuration this script reads the Zipf(1) stream results of 06_probe_lazy.py (probeL_*_ku.json) and
the fixed-state results of 04b_probe_multiepoch2.py (probeG_*.json) for the same seeds, and prints

  g_lazy, g_bg   mean share of an arriving query's exact top-5 objects already in E1 (PROB fusion)
  N              recall of the fully native index (E1ONLY at f = 1)
  L              recall of the legacy adapter path (AD_PROB at f = 0)
  measured       lazy minus background recall in the stream
  predicted      g_lazy N - (g_bg N + (1 - g_bg) L)

for final R@5 and rerank@20, plus the per-policy predictions (Q_lazy = g_lazy N, Q_bg = g_bg N + (1 - g_bg) L)
against the measured recall. The accounting was developed after the results were observed; it is an
interpretation, not a preregistered test.

Run in the directory that holds the result files:
    python3 evo/analyze_accounting.py
Configurations are (label, file prefix, M1 tag, seeds); missing files are reported and skipped.
"""
import json, os, sys
import numpy as np

CONFIGS = [
    ("20k, bge-base (dev.)", "", "bgebase", (20235956, 1, 2)),
    ("20k, e5-large (dev.)", "", "e5large", (20235956, 1, 2)),
    ("100k, bge-base", "code100kfq_", "bgebase", (3, 4, 5)),
    ("100k, e5-large", "code100kfq_", "e5large", (3, 4, 5)),
    ("100k, arctic", "code100kfq_", "arctic", (3, 4, 5)),
    ("20k, arctic", "", "arctic", (3, 4, 5)),
    ("SciFact, arctic", "scifact_", "arctic", (3, 4, 5)),
]
METRICS = (("final", "final_r5", None), ("rr", "rerank", "20"))


def load(fn):
    return json.load(open(fn)) if os.path.exists(fn) else None


def g_share(run):
    w = run["windows"]
    return float(np.mean([x["gtE1"] for x in w])) / (100.0 if max(x["gtE1"] for x in w) > 1.0 else 1.0)


def fixed(G, f, arm, key, sub):
    r = G["results"][f][arm]
    return r[key][sub] if sub else r[key]


def main():
    print(__doc__.split("\n")[0])
    print(f"{'configuration':22s} {'g_lazy/g_bg':>12s} {'final meas/pred':>16s} {'rr meas/pred':>16s}   per policy "
          "(lazy pred/meas, bg pred/meas; final | rr)")
    for label, pre, tag, seeds in CONFIGS:
        L6 = [load(f"probeL_{pre}{tag}_s{s}_ku.json") for s in seeds]
        GG = [load(f"probeG_{pre}{tag}_s{s}.json") for s in seeds]
        if any(x is None for x in L6 + GG):
            miss = [f"probeL_{pre}{tag}_s{s}_ku.json" for s, x in zip(seeds, L6) if x is None]
            miss += [f"probeG_{pre}{tag}_s{s}.json" for s, x in zip(seeds, GG) if x is None]
            print(f"{label:22s} missing: {', '.join(miss)}")
            continue
        gl = np.mean([g_share(d["runs"]["z1|PROB|lazy"]) for d in L6])
        gb = np.mean([g_share(d["runs"]["z1|PROB|bg"]) for d in L6])
        cells, pol = [], []
        for m, key, sub in METRICS:
            N = np.mean([fixed(G, max(G["results"], key=float), "E1ONLY", key, sub) for G in GG])
            Lp = np.mean([fixed(G, min(G["results"], key=float), "AD_PROB", key, sub) for G in GG])
            ql_m = np.mean([d["runs"]["z1|PROB|lazy"]["totals"][m] for d in L6])
            qb_m = np.mean([d["runs"]["z1|PROB|bg"]["totals"][m] for d in L6])
            ql_p, qb_p = gl * N, gb * N + (1 - gb) * Lp
            cells.append(f"{ql_m - qb_m:+7.1f} /{ql_p - qb_p:+6.1f}")
            pol.append(f"{ql_p:5.1f}/{ql_m:5.1f}, {qb_p:5.1f}/{qb_m:5.1f}")
        print(f"{label:22s} {gl:5.2f} / {gb:4.2f} {cells[0]:>16s} {cells[1]:>16s}   {pol[0]} | {pol[1]}")


if __name__ == "__main__":
    sys.exit(main())
