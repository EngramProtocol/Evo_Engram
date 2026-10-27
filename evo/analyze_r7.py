#!/usr/bin/env python3
"""
analyze_r7.py  —  tổng hợp đợt 7 (thăm dò). Đọc probeP_*.json (10_probe_placement.py) và probeV_*.json
(11_probe_safe.py) ở thư mục hiện tại, hoặc theo mẫu glob truyền vào.

Phần 1. Mô hình dị hướng: cosine TB giữa document, bucket 16 bit hiệu dụng dự đoán và đo được (SRP như bài),
        tải lưu trữ (phần của 1% peer tải cao nhất, max, tỉ lệ peer rỗng); tương quan hạng Spearman.
Phần 2. Placement trên code100kfq: recall (so với kNN chính xác của M1, và gold = hàm gốc của query), ứng viên,
        peer, tải ở các điểm (L, T) chính, TB theo seed.
Phần 3. So ở cùng chi phí: final R@5 và rerank@20 của từng biến thể nội suy (log-tuyến tính theo số ứng viên,
        trên đường biên Pareto qua mọi (L, T)) tại số ứng viên của SRP như bài ở L = 5, T = 8; tương tự theo số peer.
Phần 4. Migrate an toàn: từng chính sách, TB ± độ lệch chuẩn theo seed; hiệu lazyV1 − lazy, lazyV1 − bgV1 theo seed.
Phần 5. Tự kiểm ghi trong file.
"""
import glob, json, sys
from collections import defaultdict
import numpy as np


def load(pat):
    out = []
    for fn in sorted(glob.glob(pat)):
        try:
            out.append((fn, json.load(open(fn))))
        except Exception as e:
            print(f"*** không đọc được {fn}: {e}")
    return out


def ms(v):
    v = [x for x in v if x == x]
    if not v:
        return "   n/a    "
    return f"{np.mean(v):6.1f}±{np.std(v, ddof=1) if len(v) > 1 else 0:4.1f}"


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3:
        return float("nan")
    rx, ry = np.argsort(np.argsort(x)), np.argsort(np.argsort(y))
    return float(np.corrcoef(rx, ry)[0, 1])


def frontier(points):
    """points: [(cost, value)] -> đường biên Pareto tăng theo cost (giá trị tốt nhất đạt được với cost <= c)."""
    pts = sorted(points)
    out, best = [], -1e9
    for c, v in pts:
        if v > best:
            out.append((c, v)); best = v
    return out


def interp(front, c):
    """Nội suy log-tuyến tính theo cost; ngoài khoảng thì None (không ngoại suy)."""
    if not front:
        return None
    cs = [p[0] for p in front]
    if c < cs[0] or c > cs[-1] * 1.0000001:
        return None if c < cs[0] else front[-1][1]
    for (c0, v0), (c1, v1) in zip(front, front[1:]):
        if c0 <= c <= c1:
            if c1 == c0:
                return max(v0, v1)
            w = (np.log(c) - np.log(c0)) / (np.log(c1) - np.log(c0))
            return v0 + w * (v1 - v0)
    return front[-1][1]


def name_of(d):
    a = d["argv"]
    return a["dataset"], (a["tag"] if a.get("space", "m1") == "m1" else "m0"), a["seed"]


def part_placement(files):
    if not files:
        print("(không có probeP_*.json)\n")
        return
    print("=" * 100)
    print("PHẦN 1. Độ dị hướng và tải lưu trữ của SRP như bài (L = 5)")
    print("=" * 100)
    rows = defaultdict(list)
    for fn, d in files:
        ds, tag, s = name_of(d)
        v = d["variants"].get("srp")
        if v is None:
            continue
        st = v["results"]["5"]["storage"]
        rows[(ds, tag)].append(dict(c=d["aniso"]["mean_pair_cos"], pred=d["aniso"]["eff_buckets16_pred"],
                                    eff=v["bits"]["eff_buckets16"], top1=100 * st["top1pct_share"], mx=st["max"],
                                    empty=100 * st["empty_frac"], gini=st["gini"], N=d["N"],
                                    nodes=d["argv"]["nodes"]))
    print(f"{'dataset':11s} {'model':8s} {'seed':>4s} {'cos TB':>7s} {'bucket dự đoán':>15s} {'bucket đo':>10s} "
          f"{'top1% peer':>11s} {'max':>7s} {'rỗng':>6s} {'Gini':>5s}")
    X, Y, Z = [], [], []
    for (ds, tag), rr in sorted(rows.items()):
        m = {k: float(np.mean([r[k] for r in rr])) for k in rr[0]}
        print(f"{ds:11s} {tag:8s} {len(rr):4d} {m['c']:7.3f} {m['pred']:15,.0f} {m['eff']:10,.0f} {m['top1']:10.1f}% "
              f"{m['mx']:7.0f} {m['empty']:5.0f}% {m['gini']:5.2f}")
        X.append(m["pred"]); Y.append(m["eff"]); Z.append(m["top1"])
    print(f"Spearman(bucket dự đoán, bucket đo) = {spearman(X, Y):+.2f}; "
          f"Spearman(bucket dự đoán, top1% peer) = {spearman(X, Z):+.2f}; n = {len(X)} cặp (dataset, model)")
    print("Lưu ý: số bucket hiệu dụng phụ thuộc N (corpus nhỏ không đạt 65.536); so trong cùng dataset là chắc nhất.\n")

    print("=" * 100)
    print("PHẦN 2. Placement native, code100kfq: TB theo seed (final R@5 trước rerank, rerank@20, ứng viên, peer hỏi)")
    print("=" * 100)
    by = defaultdict(lambda: defaultdict(list))
    for fn, d in files:
        ds, tag, s = name_of(d)
        if ds != "code100kfq":
            continue
        for vn, v in d["variants"].items():
            by[tag][vn].append(v)
    pts = [("5", "8"), ("5", "16"), ("10", "4"), ("10", "8")]
    for tag in sorted(by):
        print(f"\n--- {tag}")
        print(f"{'biến thể':8s} {'(L,T)':>7s} {'final':>11s} {'rr20':>11s} {'gold@5':>11s} {'gold rr':>11s} "
              f"{'ứng viên':>9s} {'peer':>6s} {'top1% lưu trữ':>14s} {'max lưu trữ':>12s} {'top1% lượt hỏi':>15s} "
              f"{'top1% công việc':>16s}")
        for vn in sorted(by[tag], key=lambda x: ["srp", "srp_c", "srp_cq", "pca_q", "itq_d", "itq_q"].index(x)
                         if x in ["srp", "srp_c", "srp_cq", "pca_q", "itq_d", "itq_q"] else 99):
            vs = by[tag][vn]
            for L, T in pts:
                if L not in vs[0]["results"] or T not in vs[0]["results"][L]:
                    continue
                r = [v["results"][L][T] for v in vs]; st = [v["results"][L]["storage"] for v in vs]
                gf = [x.get("gold_final5") for x in r]; gr = [x.get("gold_rr20") for x in r]
                gf = ms([x for x in gf if x is not None]); gr = ms([x for x in gr if x is not None])
                print(f"{vn:8s} {('(' + L + ',' + T + ')'):>7s} {ms([x['final_r5'] for x in r])} {ms([x['rr20'] for x in r])} "
                      f"{gf} {gr} "
                      f"{np.mean([x['cand'] for x in r]):9.0f} {np.mean([x['nodes'] for x in r]):6.0f} "
                      f"{100 * np.mean([x['top1pct_share'] for x in st]):13.1f}% {np.mean([x['max'] for x in st]):12.0f} "
                      f"{100 * np.mean([x['qload']['top1pct_share'] for x in r]):14.1f}% "
                      f"{100 * np.mean([x['work']['top1pct_share'] for x in r]):15.1f}%")

    print("\n" + "=" * 100)
    print("PHẦN 3. Cùng chi phí: giá trị nội suy trên đường biên Pareto (mọi L, T) tại chi phí của srp (L=5, T=8),")
    print("        trừ giá trị của đường biên srp ở cùng chi phí; TB ± độ lệch chuẩn theo seed; 'ngoài' = không đạt mức chi phí đó")
    print("=" * 100)
    for ds in sorted({name_of(d)[0] for _, d in files}):
        per = defaultdict(lambda: defaultdict(list))
        for fn, d in files:
            dds, tag, s = name_of(d)
            if dds != ds or "srp" not in d["variants"] or "8" not in d["variants"]["srp"]["results"]["5"]:
                continue
            ref = d["variants"]["srp"]["results"]["5"]["8"]

            def front_of(v, cost, met):
                return frontier([(v["results"][L][T][cost], v["results"][L][T][met]) for L in v["results"]
                                 for T in v["results"][L] if T != "storage"])
            for vn, v in d["variants"].items():
                for cost in ("cand", "nodes"):
                    for met in ("final_r5", "rr20"):
                        base = interp(front_of(d["variants"]["srp"], cost, met), ref[cost])   # biên của srp, >= điểm (5, 8)
                        val = interp(front_of(v, cost, met), ref[cost])
                        per[(tag, vn)][(cost, met)].append(float("nan") if val is None else val - base)
        if not per:
            continue
        print(f"\n--- {ds}   (đơn vị: điểm phần trăm so với srp L=5 T=8)")
        print(f"{'model':8s} {'biến thể':8s} {'Δfinal @ứng viên':>17s} {'Δrr20 @ứng viên':>16s} {'Δfinal @peer':>13s} "
              f"{'Δrr20 @peer':>12s}")
        for (tag, vn), m in sorted(per.items()):
            if vn == "srp":
                continue
            def f(k):
                v = m[k]; ok = [x for x in v if x == x]
                return (ms(ok) if len(ok) == len(v) else (ms(ok) + f" ({len(v) - len(ok)} ngoài)" if ok else "  ngoài   "))
            print(f"{tag:8s} {vn:8s} {f(('cand', 'final_r5')):>17s} {f(('cand', 'rr20')):>16s} "
                  f"{f(('nodes', 'final_r5')):>13s} {f(('nodes', 'rr20')):>12s}")
    print()


def part_safe(files):
    if not files:
        print("(không có probeV_*.json)\n")
        return
    print("=" * 100)
    print("PHẦN 4. Migrate an toàn (code100kfq, PROB, khoá E1 không trừ tâm): TB ± độ lệch chuẩn theo seed")
    print("        final, rr = cả dòng 3.000 lượt; giữ riêng = 100 query giữ riêng ở t = 3.000 (final/rerank);")
    print("        dual = % object có cả bản E0 và E1 cuối dòng (lưu trữ thừa); E0 còn = % record E0 còn hoạt động")
    print("=" * 100)
    main_files = [(fn, d) for fn, d in files if not (fn.endswith("_dsadapter.json") or fn.endswith("_shared.json"))]
    by = defaultdict(lambda: defaultdict(list))
    for fn, d in main_files:
        tag = d["argv"]["tag"]
        for k, r in d["runs"].items():
            by[(tag, r["zipf"])][r["policy"]].append((d["argv"]["seed"], r))
    order = ["static", "lazy", "bg", "lazyD", "lazyV1", "lazyV2", "bgV1", "bgV2"]
    for (tag, z) in sorted(by):
        print(f"\n--- {tag}, Zipf s = {z:g}")
        print(f"{'chính sách':10s} {'n':>2s} {'final':>11s} {'rr':>11s} {'giữ riêng final':>16s} {'giữ riêng rr':>13s} "
              f"{'gold rr':>11s} {'tải/q':>6s} {'mới/q':>6s} {'f cuối':>7s} {'dual':>6s} {'E0 còn':>7s} {'dual từ E0/q':>13s}")
        pol = by[(tag, z)]
        for p in sorted(pol, key=lambda x: order.index(x) if x in order else 99):
            rs = [r for _, r in pol[p]]
            tl = str(max(int(k) for k in rs[0]["snapshots"]))
            print(f"{p:10s} {len(rs):2d} {ms([r['totals']['final'] for r in rs])} {ms([r['totals']['rr'] for r in rs])} "
                  f"{ms([r['snapshots'][tl]['final'] for r in rs]):>16s} {ms([r['snapshots'][tl]['rr'] for r in rs]):>13s} "
                  f"{ms([r['totals'].get('gold_rr', float('nan')) for r in rs])} "
                  f"{np.mean([r['totals']['fetch'] for r in rs]):6.1f} {np.mean([r['totals']['new'] for r in rs]):6.2f} "
                  f"{100 * np.mean([r['totals']['f_end'] for r in rs]):6.1f}% {np.mean([r['totals']['dual_end'] for r in rs]):5.1f}% "
                  f"{np.mean([r['totals']['act0_end'] for r in rs]):6.1f}% "
                  f"{np.mean([r['totals'].get('dual_from_e0', float('nan')) for r in rs]):13.1f}")
        for a_, b_ in (("lazyV1", "lazy"), ("lazyV1", "bgV1"), ("lazyD", "lazy"), ("lazyV2", "lazyV1")):
            if a_ in pol and b_ in pol:
                A, B = dict(pol[a_]), dict(pol[b_])
                ss = sorted(set(A) & set(B))
                for met, lab in (("final", "final"), ("rr", "rr")):
                    dv = [A[s]["totals"][met] - B[s]["totals"][met] for s in ss]
                    tl = str(max(int(k) for k in A[ss[0]]["snapshots"]))
                    dh = [A[s]["snapshots"][tl][met] - B[s]["snapshots"][tl][met] for s in ss]
                    print(f"   {a_} − {b_:6s} {lab:5s}: dòng {ms(dv)} (dương {sum(x > 0 for x in dv)}/{len(dv)}), "
                          f"giữ riêng {ms(dh)} (dương {sum(x > 0 for x in dh)}/{len(dh)})")
    abl = [(fn, d) for fn, d in files if fn.endswith("_dsadapter.json") or fn.endswith("_shared.json")]
    if abl:
        print("\n--- ablation (Arctic, Zipf 1): cách chấm và cách tính chỗ của object dual")
        ref = {d["argv"]["seed"]: d for fn, d in main_files if d["argv"]["tag"] == "arctic"}
        for fn, d in abl:
            s = d["argv"]["seed"]
            lab = "dual-score adapter" if fn.endswith("_dsadapter.json") else "dual-slots shared"
            for k, r in sorted(d["runs"].items()):
                base = ref.get(s, {}).get("runs", {}).get(k)
                extra = (f"  (mặc định: final {base['totals']['final']:5.1f} rr {base['totals']['rr']:5.1f})"
                         if base else "")
                print(f"   {lab:18s} s{s} {r['policy']:7s} final {r['totals']['final']:5.1f} rr {r['totals']['rr']:5.1f} "
                      f"f cuối {100 * r['totals']['f_end']:5.1f}% dual {r['totals']['dual_end']:5.1f}%{extra}")
    print()


def part_checks(P, V):
    print("=" * 100)
    print("PHẦN 5. Tự kiểm ghi trong file")
    print("=" * 100)
    for fn, d in P:
        c = d.get("check")
        print(f"{fn:55s} " + ("không có file 04b cùng tham số" if not c else
                               f"{c['n']} giá trị, {'KHỚP' if c['bad'] == 0 and c['n'] > 0 else str(c['bad']) + ' LỆCH'}"))
    for fn, d in V:
        c = d.get("check_06")
        print(f"{fn:55s} " + ("không có file 06" if not c else
                               f"{c['n']} giá trị, {'KHỚP' if c['bad'] == 0 and c['n'] > 0 else str(c['bad']) + ' LỆCH'}"))


def main():
    pp = sys.argv[1] if len(sys.argv) > 1 else "probeP_*.json"
    pv = sys.argv[2] if len(sys.argv) > 2 else "probeV_*.json"
    P, V = load(pp), load(pv)
    part_placement(P)
    part_safe(V)
    part_checks(P, V)


if __name__ == "__main__":
    main()
