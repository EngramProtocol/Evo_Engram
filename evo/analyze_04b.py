#!/usr/bin/env python3
"""Tổng hợp probeG_*.json (04b, multi-epoch bản 2) qua nhiều seed. Không dùng scipy.
Cho mỗi (dataset, cặp mô hình): tự kiểm, hiệu chỉnh, phân bố tải; so cách gộp (đánh giá và validation);
chênh ghép cặp adapter - dual; các cải tiến (khoá E1, chia ngân sách, học lại, đầy đủ); recall từng phía;
chi phí."""
import json, glob, sys
import numpy as np

pats = sys.argv[1:] or ["probeG_*.json"]
runs = {}
for f in sorted({x for p in pats for x in glob.glob(p)}):
    d = json.load(open(f))
    av = d["argv"]
    runs.setdefault((av.get("dataset", "code"), av["tag"], round(float(av.get("frac", 0.10)), 4)), []).append(d)
if not runs:
    sys.exit(f"không thấy file nào khớp {pats}")

FUS = ["RRF", "CAL", "PROP", "SD", "PROB"]


def ms(x, sign=False):
    x = np.asarray(x, float)
    sd = x.std(ddof=1) if len(x) > 1 else float("nan")
    return (f"{x.mean():+5.1f}±{sd:3.1f}" if sign else f"{x.mean():5.1f}±{sd:3.1f}")


def get(rr, f, arm, key, R=None):
    out = []
    for d in rr:
        r = d["results"][f][arm]
        out.append(r[key][str(R)] if R is not None else r[key])
    return out


for (dset, tag, frac), rr in sorted(runs.items()):
    seeds = [d["argv"]["seed"] for d in rr]
    fs = sorted([k for k in rr[0]["results"]], key=float)
    inner = [f for f in fs if 0 < float(f) < 1]
    print("=" * 118)
    print(f"{dset} / {tag} / mẫu S {frac:.1%}   seed = {seeds}   (mean ± sd qua seed)")

    # ---- tự kiểm
    ck = [d.get("checks", {}) for d in rr]
    print("  tự kiểm: " + " | ".join(
        f"s{s}: " + ", ".join(f"{k} {v['n']} giá trị {'KHỚP' if v['bad'] == 0 else str(v['bad']) + ' LỆCH'}"
                              for k, v in c.items()) for s, c in zip(seeds, ck)))
    print(f"  khoá E1 chọn trên validation: {[d['Kstar'] for d in rr]}")

    # ---- hiệu chỉnh
    c_in = [d["cal"]["adapter_insample"] for d in rr]; c_cf = [d["cal"]["adapter_cf"] for d in rr]
    c_du = [d["cal"]["dual"] for d in rr]
    print(f"  hiệu chỉnh adapter in-sample: r={np.mean([c['r'] for c in c_in]):.3f} sigma={np.mean([c['sig'] for c in c_in]):.4f}"
          f" | cross-fit: r={np.mean([c['r'] for c in c_cf]):.3f} sigma={np.mean([c['sig'] for c in c_cf]):.4f}"
          f" a={np.mean([c['a'] for c in c_cf]):.3f} | dual: r={np.mean([c['r'] for c in c_du]):.3f}"
          f" sigma={np.mean([c['sig'] for c in c_du]):.4f} | sigma1 E1={np.mean([d['cal']['sig1'] for d in rr]):.4f}")

    # ---- tải node
    print("  tải node (toàn bộ record):  " + "   ".join(
        f"{k}: max={np.mean([d['loads'][k]['max'] for d in rr]):.0f} p99={np.mean([d['loads'][k]['p99'] for d in rr]):.0f}"
        f" rỗng={100 * np.mean([d['loads'][k]['empty_frac'] for d in rr]):.0f}%"
        f" top1%={100 * np.mean([d['loads'][k]['top1pct_share'] for d in rr]):.1f}%" for k in ("E0", "E1u", "E1c")))

    # ---- so cách gộp
    for side in ("AD", "DU"):
        for metric, R, lab in (("final_r5", None, "final R@5"), ("rerank", 20, "rerank@20")):
            print(f"\n  {side}: {lab}   (cột GT@E0 = tỉ lệ ground truth nằm ở E0)")
            print("   f    GT@E0 " + "".join(f"{side + '_' + k:>13s}" for k in FUS) + f"{'E1ONLY':>13s}")
            for f in fs:
                ge0 = 100 * np.mean([d["results"][f]["_gt_e0_share"] for d in rr])
                print(f"  {float(f):4.0%}  {ge0:4.0f}% " + "".join(
                    f"{ms(get(rr, f, f'{side}_{k}', metric, R)):>13s}" for k in FUS)
                      + f"{ms(get(rr, f, 'E1ONLY', metric, R)):>13s}")
        print(f"  {side}: tỉ lệ top-5 lấy từ E0 (%), PROB kèm tỉ lệ mô hình dự đoán")
        for f in inner:
            ge0 = 100 * np.mean([d["results"][f]["_gt_e0_share"] for d in rr])
            mp = [d["results"][f][f"{side}_PROB"].get("model_e0_top5", np.nan) for d in rr]
            print(f"  {float(f):4.0%}  GT {ge0:3.0f}%  " + "  ".join(
                f"{k}={100 * np.mean(get(rr, f, f'{side}_{k}', 'e0_share_top5')):3.0f}%" for k in FUS)
                  + f"  (mô hình PROB {100 * np.nanmean(mp):3.0f}%)")

    # ---- validation
    print("\n  VALIDATION (query ngoài tập đánh giá), trung bình các f trong (0, 1):")
    for side in ("AD", "DU"):
        for metric, R, lab in (("final_r5", None, "final"), ("rerank", 20, "R20")):
            vals = {k: [np.mean([(d["val"][f][f"{side}_{k}"][metric][str(R)] if R else d["val"][f][f"{side}_{k}"][metric])
                                 for f in inner]) for d in rr] for k in FUS}
            best = [max(FUS, key=lambda k: vals[k][i]) for i in range(len(rr))]
            print(f"   {side} {lab:5s} " + "  ".join(f"{k}={ms(vals[k])}" for k in FUS) + f"   tốt nhất mỗi seed: {best}")

    # ---- adapter vs dual
    print("\n  chênh ghép cặp (final | rerank@20)")
    print("   f      AD_PROP-DU_PROP   AD_PROB-DU_PROB   AD_PROP-AD_RRF    AD_PROB-AD_CAL    AD_PROB-AD_PROP")
    for f in fs:
        line = f"  {float(f):4.0%} "
        for m1, m2 in (("AD_PROP", "DU_PROP"), ("AD_PROB", "DU_PROB"), ("AD_PROP", "AD_RRF"),
                       ("AD_PROB", "AD_CAL"), ("AD_PROB", "AD_PROP")):
            a1 = np.subtract(get(rr, f, m1, "final_r5"), get(rr, f, m2, "final_r5"))
            a2 = np.subtract(get(rr, f, m1, "rerank", 20), get(rr, f, m2, "rerank", 20))
            line += f"  {ms(a1, True)}|{ms(a2, True)}"
        print(line)

    # ---- cải tiến
    for k in ("PROP", "PROB"):
        arms = [f"AD_{k}", f"ADc_{k}", f"ADcq_{k}", f"ADb_{k}", f"ADR_{k}", f"ADF_{k}"] + (["DUb_PROB", "DUF_PROB"] if k == "PROB" else [])
        for metric, R, lab in (("final_r5", None, "final R@5"), ("rerank", 20, "rerank@20")):
            print(f"\n  CẢI TIẾN, gộp {k}: {lab}")
            print("   f    " + "".join(f"{m:>13s}" for m in arms))
            for f in fs:
                print(f"  {float(f):4.0%}  " + "".join(f"{ms(get(rr, f, m, metric, R)):>13s}" for m in arms))
    arms = ["AD_PROB", "ADb_PROB", "ADF_PROB", "DUb_PROB", "DUF_PROB", "E1ONLY"]
    print("\n  CHI PHÍ mỗi truy vấn: node bị chạm / ứng viên chuyển / payload E0 phải tải ở R = 20")
    print("   f    " + "".join(f"{m:>22s}" for m in arms))
    for f in fs:
        print(f"  {float(f):4.0%}  " + "".join(
            f"{np.mean(get(rr, f, m, 'nodes')):7.0f}/{np.mean(get(rr, f, m, 'moved')):6.0f}/{np.mean(get(rr, f, m, 'fetch', 20)):5.1f}"
            .rjust(22) for m in arms))

    # ---- khoá E1 ở f = 1
    fl = fs[-1]
    print(f"\n  KHOÁ E1 ở f = {float(fl):.0%} (chỉ mục native đầy đủ):")
    for m in ("E1ONLY", "E1ONLY_c", "E1ONLY_cq"):
        print(f"   {m:10s} reach={ms(get(rr, fl, m, 'reach_r5'))} final={ms(get(rr, fl, m, 'final_r5'))}"
              f" R20={ms(get(rr, fl, m, 'rerank', 20))} nodes={np.mean(get(rr, fl, m, 'nodes')):.0f}"
              f" cand={np.mean(get(rr, fl, m, 'cand')):.0f} moved={np.mean(get(rr, fl, m, 'moved')):.0f}")

    # ---- recall từng phía
    print("\n  RECALL TỪNG PHÍA so với top-5 thật trong chính partition của nó (A = adapter học trên S,"
          " AR = học lại trên M, D = dual; U/C/Q = E1 khoá u/c/cq)")
    print("   f    " + "".join(f"{k:>12s}" for k in ("A", "AR", "D", "U", "C", "Q")))
    for f in fs:
        print(f"  {float(f):4.0%}  " + "".join(
            f"{ms([d['side_recall'][f].get(k, np.nan) for d in rr]):>12s}" for k in ("A", "AR", "D", "U", "C", "Q")))
    print("  (A - D ghép cặp: " + "  ".join(
        f"{float(f):.0%}:{ms(np.subtract([d['side_recall'][f]['A'] for d in rr], [d['side_recall'][f]['D'] for d in rr]), True)}"
        for f in inner) + ")")
