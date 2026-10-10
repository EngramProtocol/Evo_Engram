#!/usr/bin/env python3
"""Tổng hợp probeL_*.json (06, lazy migration) qua nhiều seed. Không dùng scipy.
Cho mỗi (dataset, cặp mô hình) và mỗi số mũ Zipf: tổng kết từng chính sách (static, lazy, bg) với từng
cách gộp; chênh ghép cặp lazy - static và lazy - bg; quỹ đạo theo cửa sổ; truy vấn lặp lại và lần đầu;
chất lượng trên 100 query giữ riêng ở các mốc."""
import json, glob, sys
import numpy as np

pats = sys.argv[1:] or ["probeL_*.json"]
runs = {}
for f in sorted({x for p in pats for x in glob.glob(p)}):
    d = json.load(open(f))
    av = d["argv"]
    runs.setdefault((av.get("dataset", "code"), av["tag"]), []).append(d)
if not runs:
    sys.exit(f"không thấy file nào khớp {pats}")


def ms(x, sign=False):
    x = np.asarray(x, float)
    sd = x.std(ddof=1) if len(x) > 1 else float("nan")
    return (f"{x.mean():+5.1f}±{sd:3.1f}" if sign else f"{x.mean():5.1f}±{sd:3.1f}")


for (dset, tag), rr in sorted(runs.items()):
    seeds = [d["argv"]["seed"] for d in rr]
    print("=" * 112)
    a0 = rr[0]["argv"]
    print(f"{dset} / {tag}   seed = {seeds}   dòng={a0['stream']} R={a0['R']} cửa sổ={a0['window']}  N={rr[0]['N']}"
          f"  S={rr[0]['n_sample']}  khoá E1={[d['e1_key'] for d in rr]}")
    print("  tự kiểm t = 0 với 04b: " + " | ".join(
        f"s{s}: " + (f"{c['n']} giá trị {'KHỚP' if c['bad'] == 0 else str(c['bad']) + ' LỆCH'}" if c else "không có")
        for s, c in zip(seeds, [d.get("check_04b") for d in rr])))
    keys = list(rr[0]["runs"])
    zs = sorted({rr[0]["runs"][k]["zipf"] for k in keys}, reverse=True)
    fus = list(dict.fromkeys(rr[0]["runs"][k]["fusion"] for k in keys))
    pols = list(dict.fromkeys(rr[0]["runs"][k]["policy"] for k in keys))
    for z in zs:
        top10 = rr[0]["runs"][f"z{z:g}|{fus[0]}|{pols[0]}"]["top10_share"]
        dq = [d["runs"][f"z{z:g}|{fus[0]}|{pols[0]}"]["totals"]["distinct_queries"] for d in rr]
        print(f"\n  --- Zipf s = {z:g}: 10 query nóng nhất chiếm {100 * top10:.0f}% lưu lượng; số query khác nhau "
              f"trong dòng {dq}")
        print("   gộp  chính sách     final        rerank     tải/query   record mới/q   f cuối     node    moved")
        for fu in fus:
            for po in pols:
                k = f"z{z:g}|{fu}|{po}"
                if k not in rr[0]["runs"]:
                    continue
                T = [d["runs"][k]["totals"] for d in rr]
                print(f"   {fu:5s} {po:7s}  {ms([t['final'] for t in T])}  {ms([t['rr'] for t in T])}"
                      f"   {np.mean([t['fetch'] for t in T]):6.1f}     {np.mean([t['new'] for t in T]):7.2f}"
                      f"     {100 * np.mean([t['f_end'] for t in T]):5.1f}%  {np.mean([t['nodes'] for t in T]):6.0f}"
                      f"  {np.mean([t['moved'] for t in T]):6.0f}")
        print("   chênh ghép cặp (final | rerank):")
        for fu in fus:
            line = f"   {fu:5s} "
            for p1, p2 in (("lazy", "static"), ("lazy", "bg"), ("bg", "static"), ("lazybg", "bg2")):
                k1, k2 = f"z{z:g}|{fu}|{p1}", f"z{z:g}|{fu}|{p2}"
                if k1 in rr[0]["runs"] and k2 in rr[0]["runs"]:
                    a1 = [d["runs"][k1]["totals"]["final"] - d["runs"][k2]["totals"]["final"] for d in rr]
                    a2 = [d["runs"][k1]["totals"]["rr"] - d["runs"][k2]["totals"]["rr"] for d in rr]
                    line += f"  {p1}-{p2}: {ms(a1, True)}|{ms(a2, True)}"
            print(line)
        # truy vấn lặp lại / lần đầu
        print("   truy vấn lặp lại và lần đầu, cả dòng (final | rerank):")
        for fu in fus:
            for po in pols:
                k = f"z{z:g}|{fu}|{po}"
                if k not in rr[0]["runs"]:
                    continue
                rep_f, rep_r, new_f, new_r = [], [], [], []
                for d in rr:
                    W = d["runs"][k]["windows"]
                    n_tot = sum(w["t_end"] - (W[i - 1]["t_end"] if i else 0) for i, w in enumerate(W))
                    nr = np.array([w["n_rep"] for w in W], float)
                    nn = np.array([w["t_end"] - (W[i - 1]["t_end"] if i else 0) for i, w in enumerate(W)], float) - nr
                    fr = np.nan_to_num([w["final_rep"] for w in W]); rr_ = np.nan_to_num([w["rr_rep"] for w in W])
                    fn = np.nan_to_num([w["final_new"] for w in W]); rn = np.nan_to_num([w["rr_new"] for w in W])
                    rep_f.append((fr * nr).sum() / max(1, nr.sum())); rep_r.append((rr_ * nr).sum() / max(1, nr.sum()))
                    new_f.append((fn * nn).sum() / max(1, nn.sum())); new_r.append((rn * nn).sum() / max(1, nn.sum()))
                print(f"   {fu:5s} {po:7s} lặp lại {ms(rep_f)} | {ms(rep_r)}    lần đầu {ms(new_f)} | {ms(new_r)}")
        # quỹ đạo
        for fu in fus:
            ks = [f"z{z:g}|{fu}|{po}" for po in pols if f"z{z:g}|{fu}|{po}" in rr[0]["runs"]]
            W0 = rr[0]["runs"][ks[0]]["windows"]
            step = max(1, len(W0) // 10)
            print(f"   quỹ đạo, gộp {fu} (mỗi ô: f% final/rerank tải/q; trung bình qua seed):")
            print("     t    " + "".join(f"{k.split('|')[2]:>26s}" for k in ks))
            for i in list(range(0, len(W0), step)) + ([len(W0) - 1] if (len(W0) - 1) % step else []):
                cells = []
                for k in ks:
                    w = [d["runs"][k]["windows"][i] for d in rr]
                    cells.append(f"{100 * np.mean([x['f'] for x in w]):5.1f}% {np.mean([x['final'] for x in w]):4.1f}/"
                                 f"{np.mean([x['rr'] for x in w]):4.1f} {np.mean([x['fetch'] for x in w]):4.1f}")
                print(f"   {W0[i]['t_end']:5d}  " + "".join(f"{c:>26s}" for c in cells))
            print(f"   {rr[0]['argv']['n_heldout']} query giữ riêng (final/rerank, f):")
            for k in ks:
                sn = rr[0]["runs"][k]["snapshots"]
                print(f"     {k.split('|')[2]:7s} " + "  ".join(
                    f"t{t}:{np.mean([d['runs'][k]['snapshots'][t]['final'] for d in rr]):4.1f}/"
                    f"{np.mean([d['runs'][k]['snapshots'][t]['rr'] for d in rr]):4.1f}"
                    f"({100 * np.mean([d['runs'][k]['snapshots'][t]['f'] for d in rr]):.0f}%)" for t in sn))
