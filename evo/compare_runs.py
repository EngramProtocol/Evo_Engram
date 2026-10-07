#!/usr/bin/env python3
"""So gate 3c (03 bản mới) với gate 3b (03 bản cũ) trên cùng seed và cùng tham số.
Mọi nhánh có ở cả hai lượt phải ra đúng từng số ở reach, final, nodes, cand, moved và ở
rerank với R <= kappa; rerank_nokappa của bản mới phải trùng rerank của bản cũ ở mọi R.
In thêm ảnh hưởng của việc áp kappa ở R > kappa, đo trên dữ liệu thật."""
import json, glob, os, sys
import numpy as np

new_pat = sys.argv[1] if len(sys.argv) > 1 else "probeD_*_g3c.json"
new_suffix, old_suffix = "_g3c.json", "_Rfine.json"
bad, checked, kappa_eff = 0, 0, {}
for fn in sorted(glob.glob(new_pat)):
    fo = fn.replace(new_suffix, old_suffix)
    if not os.path.exists(fo):
        print(f"  không có {fo} để so")
        continue
    n, o = json.load(open(fn)), json.load(open(fo))
    kap = n["argv"]["kappa"]
    N = {r["name"]: r for r in n["results"]}
    for ro in o["results"]:
        arm, rn = ro["name"], N.get(ro["name"])
        if rn is None:
            bad += 1
            print(f"  THIẾU {arm} trong {fn}")
            continue
        for f in ("reach_r5", "final_r5", "nodes", "cand", "moved"):
            checked += 1
            if abs(ro[f] - rn[f]) > 1e-9:
                bad += 1
                print(f"  LỆCH {fn} {arm} {f}: {ro[f]} -> {rn[f]}")
        for R, v in ro.get("rerank", {}).items():
            checked += 1
            if abs(v - rn["rerank_nokappa"][R]) > 1e-9:
                bad += 1
                print(f"  LỆCH {fn} {arm} rerank_nokappa R{R}: {v} -> {rn['rerank_nokappa'][R]}")
            if int(R) <= kap:
                checked += 1
                if abs(v - rn["rerank"][R]) > 1e-9:
                    bad += 1
                    print(f"  LỆCH {fn} {arm} rerank R{R}: {v} -> {rn['rerank'][R]}")
    for r in n["results"]:
        for R in r["rerank"]:
            if int(R) > kap:
                kappa_eff.setdefault(int(R), []).append(r["rerank"][R] - r["rerank_nokappa"][R])

print(f"SO VỚI GATE 3B: {checked} giá trị, {bad} lệch -> "
      f"{'KHỚP' if bad == 0 and checked else 'CÓ LỆCH hoặc không có gì để so, gửi tôi các dòng trên'}")
for R, v in sorted(kappa_eff.items()):
    v = np.asarray(v)
    print(f"Ảnh hưởng của kappa ở R={R} (áp kappa trừ không áp), mọi nhánh mọi seed: "
          f"trung bình {v.mean():+.2f}, lớn nhất {np.abs(v).max():.2f} điểm")
