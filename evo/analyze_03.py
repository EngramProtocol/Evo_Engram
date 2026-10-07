#!/usr/bin/env python3
"""Tổng hợp probeD_*_Rfine.json qua nhiều seed: chênh lệch ghép cặp adapter - dual,
số payload adapter cần để bằng dual, biến thể chọn theo validation, và chẩn đoán
xếp hạng (nn / exact / ip / l2). Không dùng scipy."""
import json, glob, sys
import numpy as np

pat = sys.argv[1] if len(sys.argv) > 1 else "probeD_*_Rfine.json"
runs = {}
for f in sorted(glob.glob(pat)):
    d = json.load(open(f))
    runs.setdefault(d["argv"]["tag"], []).append(
        (d["argv"]["seed"], {r["name"]: r for r in d["results"]}, d.get("diag", {})))
if not runs:
    sys.exit(f"không thấy file nào khớp {pat}")


def r_needed(Rs, curve, target):
    c = np.asarray(curve, float)
    for i in range(len(Rs) - 1):
        if c[i] <= target <= c[i + 1] and c[i + 1] > c[i]:
            t = (target - c[i]) / (c[i + 1] - c[i])
            return float(np.exp(np.log(Rs[i]) + t * (np.log(Rs[i + 1]) - np.log(Rs[i]))))
    return None


def ms(x):
    x = np.asarray(x, float)
    sd = x.std(ddof=1) if len(x) > 1 else float("nan")
    return f"{x.mean():+6.1f} ± {sd:4.1f}"


def mult_line(rr, arm_of, Rs):
    """arm_of(seed_index) -> tên nhánh của seed đó (cho phép mỗi seed chọn nhánh khác nhau)."""
    out = []
    for r in Rs:
        need, below, above = [], 0, 0
        for i, (_, R, _) in enumerate(rr):
            arm = arm_of(i)
            curve = [R[arm]["rerank"][str(x)] for x in Rs]
            tgt = R["dual_encode"]["rerank"][str(r)]
            if tgt <= curve[0]:
                below += 1          # adapter đã bằng/hơn dual ngay ở R nhỏ nhất
            elif tgt > max(curve):
                above += 1          # adapter không đạt tới trong khoảng R đo
            else:
                n = r_needed(Rs, curve, tgt)
                if n is not None:
                    need.append(n / r)
        txt = f"x{np.mean(need):.2f}" if need else ""
        if below: txt += f" [{below} seed <=R{Rs[0]}]"
        if above: txt += f" [{above} seed >R{Rs[-1]}]"
        out.append(f"R{r}:{txt or '-'}")
    return "      payload cần để bằng dual: " + "  ".join(out)


def diff_lines(rr, arm_of, Rs, label):
    print(f"  {label:18s} reach {ms([R[arm_of(i)]['reach_r5'] - R['dual_encode']['reach_r5'] for i, (_, R, _) in enumerate(rr)])}"
          f"   final {ms([R[arm_of(i)]['final_r5'] - R['dual_encode']['final_r5'] for i, (_, R, _) in enumerate(rr)])}")
    print("      rerank " + "  ".join(
        f"R{r}:{ms([R[arm_of(i)]['rerank'][str(r)] - R['dual_encode']['rerank'][str(r)] for i, (_, R, _) in enumerate(rr)])}"
        for r in Rs))
    print(mult_line(rr, arm_of, Rs))


for tag, rr in runs.items():
    seeds = [s for s, _, _ in rr]
    Rs = sorted({int(k) for _, R, _ in rr for k in R["dual_encode"]["rerank"]})
    print("=" * 84)
    print(f"{tag}   seed = {seeds}   (chênh = adapter - dual, ghép cặp theo seed, mean ± sd)")
    mean = lambda arm, key: np.mean([R[arm][key] for _, R, _ in rr])
    print(f"  dual   reach {mean('dual_encode', 'reach_r5'):5.1f}  final {mean('dual_encode', 'final_r5'):5.1f}  rerank "
          + "  ".join(f"R{r}={np.mean([R['dual_encode']['rerank'][str(r)] for _, R, _ in rr]):5.1f}" for r in Rs))
    arms = [n for n in rr[0][1] if n.startswith("A_")]
    for arm in arms:
        diff_lines(rr, lambda i, arm=arm: arm, Rs, arm)

    # biến thể chọn trên validation, mỗi seed tự chọn
    sel = [dg.get("val", {}).get("selected") for _, _, dg in rr]
    if all(sel):
        print(f"\n  CHỌN THEO VALIDATION (mỗi seed tự chọn): {sel}")
        diff_lines(rr, lambda i: sel[i], Rs, "-> nhánh được chọn")
        vR = rr[0][2]["val"]["R"]
        print(f"      validation rerank@{vR} (mean qua seed): dual "
              f"{np.mean([dg['val']['dual']['rerank'] for _, _, dg in rr]):5.1f} | " + "  ".join(
                  f"{a}={np.mean([dg['val']['arms'][a]['rerank'] for _, _, dg in rr]):5.1f}"
                  for a in rr[0][2]["val"]["arms"]))

    # chẩn đoán xếp hạng
    keys = ("nn_overlap", "final_exact", "final_ip", "final_r5")
    if all(k in rr[0][1]["dual_encode"] for k in keys):
        print("\n  CHẨN ĐOÁN (mean qua seed): nn = toàn corpus không PQ | exact = reachable không PQ"
              " | ip = ADC tích vô hướng | l2 = final")
        print(f"  {'nhánh':18s}    nn  exact     ip     l2")
        for arm in ["dual_encode", "oracle_full"] + (["no_adapter"] if "no_adapter" in rr[0][1] else []) + arms:
            print(f"  {arm:18s} " + "  ".join(f"{mean(arm, k):5.1f}" for k in keys))
