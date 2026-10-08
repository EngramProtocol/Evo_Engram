#!/usr/bin/env python3
"""Tổng hợp probeF_*.json (probe 04, multi-epoch) qua nhiều seed. Không dùng scipy.
In cho mỗi (dataset, cặp mô hình): theo từng tỉ lệ đã migrate f, final R@5 và rerank@20 của
các cách gộp, chi phí tra cứu, và chênh lệch ghép cặp giữa các cách gộp."""
import json, glob, sys
import numpy as np

pats = sys.argv[1:] or ["probeF_*.json"]
runs = {}
for f in sorted({x for p in pats for x in glob.glob(p)}):
    d = json.load(open(f))
    av = d["argv"]
    key = (av.get("dataset", "code"), av["tag"], round(float(av.get("frac", 0.10)), 4))
    runs.setdefault(key, []).append(d)
if not runs:
    sys.exit(f"không thấy file nào khớp {pats}")

METHODS = ["AD_RRF", "AD_CAL", "DU_RRF", "DU_CAL", "E1ONLY"]


def ms(x):
    x = np.asarray(x, float)
    sd = x.std(ddof=1) if len(x) > 1 else float("nan")
    return f"{x.mean():5.1f}±{sd:3.1f}"


def dms(x):
    x = np.asarray(x, float)
    sd = x.std(ddof=1) if len(x) > 1 else float("nan")
    return f"{x.mean():+5.1f}±{sd:3.1f}"


for (dset, tag, frac), rr in sorted(runs.items()):
    seeds = [d["argv"]["seed"] for d in rr]
    fs = sorted(rr[0]["results"], key=float)
    Rs = sorted(int(R) for R in rr[0]["results"][fs[0]]["AD_RRF"]["rerank"])
    print("=" * 112)
    print(f"{dset} / {tag} / mẫu S {frac:.1%}   seed = {seeds}   (mean ± sd qua seed)")
    cal = np.array([d["cal"]["adapter"] for d in rr]); cald = np.array([d["cal"]["dual"] for d in rr])
    print(f"  hiệu chỉnh CAL: adapter a={cal[:, 0].mean():.3f} b={cal[:, 1].mean():+.3f} r={cal[:, 2].mean():.3f}"
          f" | dual a={cald[:, 0].mean():.3f} b={cald[:, 1].mean():+.3f} r={cald[:, 2].mean():.3f}")
    g = lambda f, m, k, R=None: [d["results"][f][m]["rerank"][str(R)] if R else d["results"][f][m][k] for d in rr]
    for metric, R in (("final_r5", None), ("rerank", 20)):
        lab = "final R@5" if R is None else f"rerank@{R}"
        print(f"\n  {lab}")
        print("   f     " + "".join(f"{m:>12s}" for m in METHODS))
        for f in fs:
            print(f"  {float(f):4.0%}   " + "".join(f"{ms(g(f, m, metric, R)):>12s}" for m in METHODS))
    print("\n  chênh ghép cặp (final R@5 | rerank@20)")
    print("   f      AD_CAL-DU_CAL      AD_CAL-AD_RRF      AD_RRF-DU_RRF")
    for f in fs:
        line = f"  {float(f):4.0%}  "
        for m1, m2 in (("AD_CAL", "DU_CAL"), ("AD_CAL", "AD_RRF"), ("AD_RRF", "DU_RRF")):
            a1 = np.subtract(g(f, m1, "final_r5"), g(f, m2, "final_r5"))
            a2 = np.subtract(g(f, m1, "rerank", 20), g(f, m2, "rerank", 20))
            line += f"  {dms(a1)}|{dms(a2)}"
        print(line)
    print("\n  chi phí mỗi truy vấn (nhánh adapter)  và  tỉ lệ top-5 lấy từ E0")
    print("   f      node bị chạm   ứng viên chuyển   top5 từ E0: AD_RRF  AD_CAL")
    for f in fs:
        print(f"  {float(f):4.0%}   {np.mean(g(f, 'AD_CAL', 'nodes')):10.0f}   {np.mean(g(f, 'AD_CAL', 'moved')):13.0f}"
              f"   {100 * np.mean(g(f, 'AD_RRF', 'e0_share_top5')):16.0f}%  {100 * np.mean(g(f, 'AD_CAL', 'e0_share_top5')):5.0f}%")
