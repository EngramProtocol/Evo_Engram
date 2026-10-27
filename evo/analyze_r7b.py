#!/usr/bin/env python3
"""
analyze_r7b.py  —  tổng hợp đợt 7b (thăm dò). Đọc ở thư mục hiện tại:
  probeA_*.json                          (10 --aniso-only, pha C)
  probeP_*.json                          (đợt 7, để lấy tải lưu trữ đo được khi tương quan với dự đoán)
  probeVB_code100kfq_<tag>_s<seed>_u.json, ..._itq_q.json   (11, pha A và B)
  probeL_code100kfq_e5large_s<seed>_ku_r7b.json, probeL_code100kfq_e5large_s<seed>_ku.json, probeV_code100kfq_e5large_s<seed>.json
                                         (pha D: 06 hiện tại so với đợt 4 và với 11 của đợt 7)

Phần 1. Mô hình dị hướng: xác suất trùng bucket 16 bit giữa hai document, dự đoán theo trường trung bình và theo công
        thức góc chính xác E[(1 − theta/pi)^16], so với đo thật; tương quan hạng với tải của 1% peer nóng nhất.
Phần 2. Migrate cùng ngân sách (khoá E1 như bài): bảng chính sách, hiệu so với lazy và static theo seed.
Phần 3. Migrate trên placement học (itq_q): như phần 2, thêm so sánh từng chính sách giữa hai cách đặt record E1.
Phần 4. Chẩn đoán 'moved' và tự kiểm.
"""
import glob, json, math, os, sys
from collections import defaultdict
import numpy as np


def ms(v):
    v = [x for x in v if x is not None and x == x]
    if not v:
        return "   n/a    "
    return f"{np.mean(v):6.1f}±{np.std(v, ddof=1) if len(v) > 1 else 0:4.1f}"


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3:
        return float("nan")
    rx, ry = np.argsort(np.argsort(x)), np.argsort(np.argsort(y))
    return float(np.corrcoef(rx, ry)[0, 1])


def load(pat):
    out = []
    for fn in sorted(glob.glob(pat)):
        try:
            out.append((fn, json.load(open(fn))))
        except Exception as e:
            print(f"*** không đọc được {fn}: {e}")
    return out


def part1():
    A = load("probeA_*.json")
    print("=" * 110)
    print("PHẦN 1. Xác suất hai document ngẫu nhiên trùng bucket 16 bit của SRP (bảng đầu đến bảng 5, TB)")
    print("        TT = trường trung bình (cos TB), góc = E[(1 − theta/pi)^16] trên cặp ngẫu nhiên, đo = đếm trên toàn corpus")
    print("=" * 110)
    if not A:
        print("(không có probeA_*.json)\n")
        return
    P = {}
    for fn, d in load("probeP_*.json"):
        a = d["argv"]
        tag = a["tag"] if a.get("space", "m1") == "m1" else "m0"
        v = d["variants"].get("srp")
        if v is not None and "5" in v["results"]:
            P.setdefault((a["dataset"], tag), []).append(100 * v["results"]["5"]["storage"]["top1pct_share"])
    rows = []
    print(f"{'dataset':11s} {'model':8s} {'cos TB':>7s} {'TT':>9s} {'góc':>9s} {'đo':>9s} {'góc/đo':>7s} {'TT/đo':>7s} "
          f"{'trừ tâm góc':>12s} {'trừ tâm đo':>11s} {'query: dự đoán':>15s} {'query: đo':>10s} {'gần trùng':>10s} {'top1% peer':>11s}")
    for fn, d in A:
        a, e = d["argv"], d["ext"]
        tag = a["tag"] if a.get("space", "m1") == "m1" else "m0"
        top1 = P.get((a["dataset"], tag))
        top1 = float(np.mean(top1)) if top1 else float("nan")
        rows.append((a["dataset"], tag, d["aniso"]["mean_pair_cos"], e["coll_pred_meanfield"], e["coll_pred_exact_u"],
                     e["coll_meas_u"], e["coll_pred_exact_c"], e["coll_meas_c"], e["qfrac_pred_u"], e["qfrac_meas_u"],
                     e["near_dup_frac_u"], top1))
    rows.sort()
    for r in rows:
        print(f"{r[0]:11s} {r[1]:8s} {r[2]:7.3f} {r[3]:9.2e} {r[4]:9.2e} {r[5]:9.2e} {r[4] / max(r[5], 1e-12):7.2f} "
              f"{r[3] / max(r[5], 1e-12):7.2f} {r[6]:12.2e} {r[7]:11.2e} {100 * r[8]:14.3f}% {100 * r[9]:9.3f}% "
              f"{100 * r[10]:9.3f}% {r[11]:10.1f}%")
    tt, ex, me, t1 = [r[3] for r in rows], [r[4] for r in rows], [r[5] for r in rows], [r[11] for r in rows]
    ok = [i for i, x in enumerate(t1) if x == x]
    print(f"Spearman với xác suất đo: TT {spearman(tt, me):+.2f}, góc {spearman(ex, me):+.2f} (n = {len(rows)})")
    if ok:
        print(f"Spearman với top1% peer (đợt 7): TT {spearman([tt[i] for i in ok], [t1[i] for i in ok]):+.2f}, "
              f"góc {spearman([ex[i] for i in ok], [t1[i] for i in ok]):+.2f}, đo {spearman([me[i] for i in ok], [t1[i] for i in ok]):+.2f} "
              f"(n = {len(ok)})")
    lr = [abs(math.log10(r[4] / r[5])) for r in rows if r[5] > 0]
    lt = [abs(math.log10(r[3] / r[5])) for r in rows if r[5] > 0]
    print(f"Sai số log10 TB so với đo: TT {np.mean(lt):.2f}, góc {np.mean(lr):.2f}")
    for ds in sorted({r[0] for r in rows}):
        rr = [r for r in rows if r[0] == ds]
        o_ex = [r[1] for r in sorted(rr, key=lambda r: -r[4])]
        o_me = [r[1] for r in sorted(rr, key=lambda r: -r[5])]
        o_t1 = [r[1] for r in sorted(rr, key=lambda r: -r[11]) if r[11] == r[11]]
        print(f"  {ds}: lệch nhất theo góc {o_ex}; theo đo {o_me}; theo top1% peer {o_t1}")
    print()


POL = ["static", "lazy", "bg", "lazyD", "lazyV1", "bgV1", "lazyVbg", "lazyVbgD"]


def runs_of(place):
    by = defaultdict(lambda: defaultdict(dict))        # (tag, z) -> policy -> seed -> run
    for fn, d in load(f"probeVB_code100kfq_*_s*_{place}.json"):
        a = d["argv"]
        for k, r in d["runs"].items():
            by[(a["tag"], r["zipf"])][r["policy"]][a["seed"]] = r
    return by


def table(by, title):
    print("=" * 110)
    print(title)
    print("        dòng = 3.000 lượt; giữ = 100 query giữ riêng ở t cuối; gold = hàm gốc trong top-5 sau rerank;")
    print("        chấm = record các peer được hỏi phải chấm mỗi truy vấn; dual = % object có cả hai bản cuối dòng")
    print("=" * 110)
    if not by:
        print("(không có file)\n")
        return
    for (tag, z) in sorted(by):
        pol = by[(tag, z)]
        print(f"\n--- {tag}, Zipf s = {z:g}")
        print(f"{'chính sách':10s} {'dòng final':>11s} {'dòng rr':>11s} {'dòng gold':>11s} {'giữ final':>11s} {'giữ rr':>11s} "
              f"{'giữ gold':>11s} {'tải/q':>6s} {'mới/q':>6s} {'f cuối':>7s} {'dual':>6s} {'chấm/q':>8s}")
        for p in sorted(pol, key=lambda x: POL.index(x) if x in POL else 99):
            rs = list(pol[p].values())
            tl = str(max(int(k) for k in rs[0]["snapshots"]))
            T = lambda m: ms([r["totals"].get(m) for r in rs])
            H = lambda m: ms([r["snapshots"][tl].get(m) for r in rs])
            print(f"{p:10s} {T('final')} {T('rr')} {T('gold_rr')} {H('final')} {H('rr')} {H('gold_rr')} "
                  f"{np.mean([r['totals']['fetch'] for r in rs]):6.1f} {np.mean([r['totals']['new'] for r in rs]):6.2f} "
                  f"{100 * np.mean([r['totals']['f_end'] for r in rs]):6.1f}% {np.mean([r['totals']['dual_end'] for r in rs]):5.1f}% "
                  f"{np.mean([r['totals'].get('scan', float('nan')) for r in rs]):8.0f}")
        for a_, b_ in (("lazyVbg", "lazy"), ("lazyVbgD", "lazy"), ("lazyVbgD", "lazyVbg"), ("lazy", "static"),
                       ("lazyVbg", "static"), ("lazyVbgD", "static"), ("lazyV1", "bgV1")):
            if a_ not in pol or b_ not in pol:
                continue
            ss = sorted(set(pol[a_]) & set(pol[b_]))
            cells = []
            for kind, m in (("t", "final"), ("t", "rr"), ("t", "gold_rr"), ("s", "final"), ("s", "rr"), ("s", "gold_rr")):
                dv = []
                for s in ss:
                    ra, rb = pol[a_][s], pol[b_][s]
                    tl = str(max(int(k) for k in ra["snapshots"]))
                    va = ra["totals"][m] if kind == "t" else ra["snapshots"][tl][m]
                    vb = rb["totals"][m] if kind == "t" else rb["snapshots"][tl][m]
                    dv.append(va - vb)
                lab = ("dòng" if kind == "t" else "giữ") + "-" + m
                dv = [x for x in dv if x == x]
                cells.append(f"{lab}:{np.mean(dv):+5.1f}({sum(x < -1 for x in dv)}/{len(dv)})" if dv else f"{lab}: n/a")
            print(f"   {a_} − {b_:7s} " + "  ".join(cells))
    print("   (số trong ngoặc: số seed mà hiệu nhỏ hơn −1 điểm)\n")


def part3_cross(bu, bi):
    if not bu or not bi:
        return
    print("--- cùng chính sách, đặt E1 itq_q trừ đặt E1 u (TB theo seed; dòng final, giữ final, chấm/q tỉ lệ)")
    for key in sorted(set(bu) & set(bi)):
        tag, z = key
        cells = []
        for p in ("static", "lazy", "lazyV1", "lazyVbg", "lazyVbgD"):
            if p in bu[key] and p in bi[key]:
                ss = sorted(set(bu[key][p]) & set(bi[key][p]))
                df = [bi[key][p][s]["totals"]["final"] - bu[key][p][s]["totals"]["final"] for s in ss]
                tl = str(max(int(k) for k in bi[key][p][ss[0]]["snapshots"]))
                dh = [bi[key][p][s]["snapshots"][tl]["final"] - bu[key][p][s]["snapshots"][tl]["final"] for s in ss]
                sr = [bi[key][p][s]["totals"].get("scan", float("nan")) / max(1e-9, bu[key][p][s]["totals"].get("scan", float("nan")))
                      for s in ss]
                cells.append(f"{p}: {np.mean(df):+5.1f}/{np.mean(dh):+5.1f} x{np.nanmean(sr):.2f}")
        print(f"   {tag:8s} z{z:g}  " + "  ".join(cells))
    print()


def part4():
    print("=" * 110)
    print("PHẦN 4. Tự kiểm và chẩn đoán")
    print("=" * 110)
    for fn, d in load("probeVB_*.json"):
        c6, c10 = d.get("check_06"), d.get("check_10")
        s6 = ("—" if not c6 else f"06: {c6['n']} giá trị, {'KHỚP' if c6['bad'] == 0 and c6['n'] > 0 else str(c6['bad']) + ' LỆCH ' + str(c6.get('diffs', [])[:3])}")
        s10 = ("—" if not c10 else f"10: {c10['n']} giá trị, {'KHỚP' if c10['bad'] == 0 else str(c10['bad']) + ' LỆCH ' + str(c10.get('diffs'))}")
        print(f"{os.path.basename(fn):48s} {s6}   {s10}   numpy {d.get('numpy')}")
    for fn, d in load("probeL_code100kfq_e5large_s*_ku_r7b.json"):
        s = d["argv"]["seed"]
        f4, f7 = f"probeL_code100kfq_e5large_s{s}_ku.json", f"probeV_code100kfq_e5large_s{s}.json"
        print(f"\n06 hiện tại ({os.path.basename(fn)}): check_3b = {d.get('check_3b')}")
        for ref, lab in ((f4, "đợt 4"), (f7, "11 đợt 7")):
            if not os.path.exists(ref):
                print(f"   không có {ref}"); continue
            R = json.load(open(ref))
            diffs, n = [], 0
            for pol in ("static", "lazy", "bg"):
                for z in ("1", "0"):
                    k = f"z{z}|PROB|{pol}"
                    if k not in d["runs"] or k not in R["runs"]:
                        continue
                    a_, b_ = d["runs"][k], R["runs"][k]
                    for kk in ("final", "rr", "fetch", "new", "nodes", "moved", "f_end", "gtE1"):
                        if kk in a_["totals"] and kk in b_["totals"]:
                            n += 1
                            if abs(a_["totals"][kk] - b_["totals"][kk]) > 1e-9:
                                diffs.append((k, kk, b_["totals"][kk], a_["totals"][kk]))
                    for wi, (x, y) in enumerate(zip(a_["windows"], b_["windows"])):
                        for kk in ("final", "rr", "fetch", "new", "moved", "nodes"):
                            n += 1
                            if abs(x[kk] - y[kk]) > 1e-9:
                                diffs.append((k, f"w{wi}", kk, y[kk], x[kk]))
            print(f"   06 hiện tại so với {lab} ({ref}): {n} giá trị, {len(diffs)} khác " + (str(diffs[:6]) if diffs else ""))
    print()


def main():
    part1()
    bu, bi = runs_of("u"), runs_of("itq_q")
    table(bu, "PHẦN 2. Migrate cùng ngân sách với lazy, khoá E1 như bài (u), code100kfq, PROB: TB ± độ lệch chuẩn theo seed")
    table(bi, "PHẦN 3. Migrate trên placement học (E1 đặt bằng itq_q), code100kfq, PROB")
    part3_cross(bu, bi)
    part4()


if __name__ == "__main__":
    main()
