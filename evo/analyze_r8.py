#!/usr/bin/env python3
"""
analyze_r8.py  —  đánh giá đợt 8 theo đúng evo/PREREG_round8.md, rồi in phần thăm dò. Đọc ở thư mục hiện tại:
  probeA_*_s<seed>.json, probeP_*_s<seed>.json        (seed của pha C, D: SEEDS_C, mặc định 6 7 8)
  probeV8_code100kfq_<tag>_s<seed>_itq_q.json         (pha A, SEEDS_A, mặc định 6..15)
  probeV8_code100kfq_<tag>_s<seed>_u.json             (pha B, SEEDS_B, mặc định 6..10)
  probeVR_*.json                                      (pha R)
Seed lấy từ biến môi trường giống run_round8.sh để file của các đợt trước (seed 3, 4, 5) không lẫn vào.
"""
import glob, json, math, os
from collections import defaultdict
import numpy as np

SEEDS_A = [int(x) for x in os.environ.get("SEEDS_A", "6 7 8 9 10 11 12 13 14 15").split()]
SEEDS_B = [int(x) for x in os.environ.get("SEEDS_B", "6 7 8 9 10").split()]
SEEDS_C = [int(x) for x in os.environ.get("SEEDS_C", "6 7 8").split()]
TAGS = os.environ.get("TAGS", "bgebase e5large arctic").split()
TCRIT = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
         11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086}
VERDICT = []


def jl(fn):
    try:
        return json.load(open(fn))
    except Exception as e:
        print(f"*** không đọc được {fn}: {e}")
        return None


def ci(v):
    v = np.asarray([x for x in v if x == x], dtype=float)
    n = len(v)
    if n == 0:
        return float("nan"), float("nan"), float("nan"), 0
    m = float(v.mean())
    if n == 1:
        return m, float("nan"), float("nan"), 1
    h = TCRIT.get(n - 1, 1.96) * float(v.std(ddof=1)) / math.sqrt(n)
    return m, m - h, m + h, n


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


def frontier(points):
    pts = sorted(points)
    out, best = [], -1e9
    for c, v in pts:
        if v > best:
            out.append((c, v)); best = v
    return out


def interp(front, c):
    if not front:
        return None
    if c < front[0][0]:
        return None
    for (c0, v0), (c1, v1) in zip(front, front[1:]):
        if c0 <= c <= c1:
            if c1 == c0:
                return max(v0, v1)
            w = (math.log(c) - math.log(c0)) / (math.log(c1) - math.log(c0))
            return v0 + w * (v1 - v0)
    return front[-1][1]


def verdict(name, ok, detail):
    VERDICT.append((name, ok, detail))
    print(f"   {'ĐẠT ' if ok else 'KHÔNG ĐẠT'}  {name}: {detail}")


def tag_of(d):
    a = d["argv"]
    return a["tag"] if a.get("space", "m1") == "m1" else "m0"


# ----------------------------------------------------------------- H1
def h1():
    print("=" * 110)
    print(f"H1. Mô hình dị hướng: 12 cặp (dataset, không gian), TB seed {SEEDS_C}")
    print("=" * 110)
    A, P = defaultdict(list), defaultdict(list)
    for fn in glob.glob("probeA_*.json"):
        d = jl(fn)
        if d and d["argv"]["seed"] in SEEDS_C:
            A[(d["argv"]["dataset"], tag_of(d))].append(d["ext"])
    for fn in glob.glob("probeP_*.json"):
        d = jl(fn)
        if d and d["argv"]["seed"] in SEEDS_C and "srp" in d["variants"] and "5" in d["variants"]["srp"]["results"]:
            P[(d["argv"]["dataset"], tag_of(d))].append(d["variants"]["srp"]["results"]["5"]["storage"])
    rows = []
    for k in sorted(A):
        if k not in P:
            continue
        p = float(np.mean([e["coll_pred_exact_u"] for e in A[k]]))
        q = float(np.mean([e["coll_meas_u"] for e in A[k]]))
        t = 100 * float(np.mean([s["top1pct_share"] for s in P[k]]))
        mf = float(np.mean([e["coll_pred_meanfield"] for e in A[k]]))
        rows.append((k[0], k[1], p, q, t, mf, len(A[k]), len(P[k])))
    print(f"{'dataset':11s} {'không gian':10s} {'dự đoán góc':>12s} {'TT':>9s} {'đo':>9s} {'|log10 p/q|':>12s} {'top1% peer':>11s} {'n':>5s}")
    for r in rows:
        print(f"{r[0]:11s} {r[1]:10s} {r[2]:12.2e} {r[5]:9.2e} {r[3]:9.2e} {abs(math.log10(r[2] / r[3])):12.2f} {r[4]:10.1f}% {r[6]}/{r[7]}")
    if len(rows) < 12:
        print(f"*** chỉ có {len(rows)} cặp đủ dữ liệu (cần 12)")
    rho = spearman([r[2] for r in rows], [r[4] for r in rows])
    err = float(np.mean([abs(math.log10(r[2] / r[3])) for r in rows])) if rows else float("nan")
    rho_mf = spearman([r[5] for r in rows], [r[4] for r in rows])
    print(f"   Spearman(dự đoán góc, top1%) = {rho:+.3f}; trường trung bình: {rho_mf:+.3f}; sai số log10 TB = {err:.3f}")
    verdict("H1", len(rows) == 12 and rho >= 0.8 and err <= 0.2,
            f"n={len(rows)} cặp, Spearman {rho:+.3f} (cần >= 0,8), sai số log10 TB {err:.3f} (cần <= 0,2)")
    print()


# ----------------------------------------------------------------- H2
def h2():
    print("=" * 110)
    print(f"H2. Placement học trên code100kfq, seed {SEEDS_C}: hiệu tại số ứng viên của srp (L=5, T=8); tỉ lệ tải tối đa ở L=5")
    print("=" * 110)
    by = defaultdict(list)
    for fn in glob.glob("probeP_code100kfq_*.json"):
        d = jl(fn)
        if d and d["argv"]["seed"] in SEEDS_C:
            by[tag_of(d)].append(d)

    def front_of(v):
        return frontier([(v["results"][L][T]["cand"], v["results"][L][T]["final_r5"]) for L in v["results"]
                         for T in v["results"][L] if T != "storage"])
    for tag in ["arctic", "bgebase", "m0", "e5large"]:
        ds_ = by.get(tag, [])
        dl, rat = [], []
        for d in ds_:
            vs, vi = d["variants"].get("srp"), d["variants"].get("itq_q")
            if vs is None or vi is None:
                continue
            c = vs["results"]["5"]["8"]["cand"]
            fi, fs = interp(front_of(vi), c), interp(front_of(vs), c)
            dl.append(float("nan") if fi is None or fs is None else fi - fs)
            rat.append(vs["results"]["5"]["storage"]["max"] / max(1, vi["results"]["5"]["storage"]["max"]))
        m = float(np.nanmean(dl)) if dl else float("nan")
        r = float(np.mean(rat)) if rat else float("nan")
        print(f"   {tag:8s} n={len(dl)}  Δfinal tại ứng viên của srp = {m:+.2f} (theo seed {[round(x, 1) for x in dl]}); "
              f"tỉ lệ tải tối đa srp/itq_q ở L=5 = {r:.1f}")
        if tag != "e5large":
            verdict(f"H2 recall {tag}", len(dl) == len(SEEDS_C) and m >= 3, f"Δ = {m:+.2f} (cần >= +3)")
        verdict(f"H2 tải {tag}", len(rat) == len(SEEDS_C) and r >= 3, f"tỉ lệ = {r:.1f} (cần >= 3)")
    print()


# ----------------------------------------------------------------- H3 đến H5
def runs8(place, seeds):
    R = defaultdict(dict)                                 # tag -> seed -> runs
    for t in TAGS:
        for s in seeds:
            fn = f"probeV8_code100kfq_{t}_s{s}_{place}.json"
            if os.path.exists(fn):
                d = jl(fn)
                if d:
                    R[t][s] = d["runs"]
    return R


def snap_end(r):
    return r["snapshots"][str(max(int(k) for k in r["snapshots"]))]


def h345():
    print("=" * 110)
    print(f"H3 đến H5. Migrate trên placement học itq_q, Zipf 1, seed {SEEDS_A} (KTC 95% theo t trên hiệu ghép cặp)")
    print("=" * 110)
    R = runs8("itq_q", SEEDS_A)
    for t in TAGS:
        rs = R.get(t, {})
        ss = sorted(s for s in rs if all(f"z1|PROB|{p}" in rs[s] for p in ("static", "lazy", "lazyVbgD")))
        if len(ss) < len(SEEDS_A):
            print(f"*** {t}: chỉ có {len(ss)} trên {len(SEEDS_A)} seed")
        g = lambda s, p: rs[s][f"z1|PROB|{p}"]
        d3 = [snap_end(g(s, "lazyVbgD"))["final"] - snap_end(g(s, "lazy"))["final"] for s in ss]
        d4a = [snap_end(g(s, "lazyVbgD"))["final"] - snap_end(g(s, "static"))["final"] for s in ss]
        d4b = [g(s, "lazy")["totals"]["rr"] - g(s, "static")["totals"]["rr"] for s in ss]
        dual = [g(s, "lazyVbgD")["totals"]["dual_end"] for s in ss]
        fr = [g(s, "lazyVbgD")["totals"]["fetch"] / max(1e-9, g(s, "lazy")["totals"]["fetch"]) for s in ss]
        m3, lo3, hi3, n3 = ci(d3); m4a = ci(d4a); m4b, lo4b, hi4b, _ = ci(d4b)
        print(f"\n   --- {t} (n = {n3} seed)")
        print(f"   lazyVbgD − lazy, final giữ riêng: TB {m3:+.2f}, KTC [{lo3:+.2f}, {hi3:+.2f}]")
        print(f"   lazyVbgD − static, final giữ riêng: TB {m4a[0]:+.2f}, KTC [{m4a[1]:+.2f}, {m4a[2]:+.2f}]")
        print(f"   lazy − static, rerank trên dòng: TB {m4b:+.2f}, KTC [{lo4b:+.2f}, {hi4b:+.2f}]")
        print(f"   dual cuối dòng của lazyVbgD: TB {np.mean(dual):.1f}%; payload lazyVbgD / lazy: TB {np.mean(fr):.3f}")
        full = n3 == len(SEEDS_A)
        verdict(f"H3 {t}", full and lo3 > 0, f"cận dưới KTC {lo3:+.2f} (cần > 0)")
        verdict(f"H4a {t}", full and m4a[0] >= 3, f"TB {m4a[0]:+.2f} (cần >= +3)")
        verdict(f"H4b {t}", full and hi4b < 0, f"cận trên KTC {hi4b:+.2f} (cần < 0)")
        verdict(f"H5 {t}", full and np.mean(dual) <= 40 and np.mean(fr) <= 1 / 3,
                f"dual {np.mean(dual):.1f}% (cần <= 40), payload {np.mean(fr):.3f} (cần <= 0,333)")
    print()


# ----------------------------------------------------------------- thăm dò
POL = ["static", "lazy", "bg", "lazyV1", "bgV1", "lazyVbg", "lazyVbgD", "full", "mapall"]


def explore(place, seeds, title):
    R = runs8(place, seeds)
    print("=" * 110)
    print(title)
    print("        dòng = 3.000 lượt; giữ = query giữ riêng ở cuối dòng; gold = hàm gốc trong top-5 sau rerank")
    print("=" * 110)
    for z in ("1", "0"):
        for t in TAGS:
            rs = R.get(t, {})
            if not rs:
                continue
            print(f"\n--- {t}, Zipf {z}, n = {len(rs)} seed")
            print(f"{'chính sách':10s} {'dòng final':>11s} {'dòng rr':>11s} {'dòng gold':>11s} {'giữ final':>11s} {'giữ rr':>11s} "
                  f"{'giữ gold':>11s} {'tải/q':>6s} {'mới/q':>6s} {'f cuối':>7s} {'dual':>6s} {'chấm/q':>8s}")
            for p in POL:
                xs = [rs[s][f"z{z}|PROB|{p}"] for s in rs if f"z{z}|PROB|{p}" in rs[s]]
                if not xs:
                    continue
                T_ = lambda m: ms([x["totals"].get(m) for x in xs])
                H_ = lambda m: ms([snap_end(x).get(m) for x in xs])
                print(f"{p:10s} {T_('final')} {T_('rr')} {T_('gold_rr')} {H_('final')} {H_('rr')} {H_('gold_rr')} "
                      f"{np.mean([x['totals']['fetch'] for x in xs]):6.1f} {np.mean([x['totals']['new'] for x in xs]):6.2f} "
                      f"{100 * np.mean([x['totals']['f_end'] for x in xs]):6.1f}% {np.mean([x['totals']['dual_end'] for x in xs]):5.1f}% "
                      f"{np.mean([x['totals'].get('scan', float('nan')) for x in xs]):8.0f}")
            for a_, b_ in (("lazyVbgD", "lazy"), ("lazyVbgD", "static"), ("lazyVbgD", "mapall"), ("mapall", "lazy"),
                           ("full", "lazyVbgD"), ("lazy", "static"), ("lazyVbgD", "bg"), ("lazyVbgD", "lazyVbg")):
                cells = []
                for kind, m in (("t", "final"), ("t", "rr"), ("t", "gold_rr"), ("s", "final"), ("s", "rr"), ("s", "gold_rr")):
                    dv = []
                    for s in rs:
                        ka, kb = f"z{z}|PROB|{a_}", f"z{z}|PROB|{b_}"
                        if ka in rs[s] and kb in rs[s]:
                            va = rs[s][ka]["totals"][m] if kind == "t" else snap_end(rs[s][ka])[m]
                            vb = rs[s][kb]["totals"][m] if kind == "t" else snap_end(rs[s][kb])[m]
                            if va == va and vb == vb:
                                dv.append(va - vb)
                    lab = ("dòng" if kind == "t" else "giữ") + "-" + m
                    if dv:
                        mm, lo, hi, n = ci(dv)
                        cells.append(f"{lab}:{mm:+5.1f}[{lo:+.1f},{hi:+.1f}]")
                if cells:
                    print(f"   {a_} − {b_:8s} " + "  ".join(cells))
    print()


def explore_c2_small():
    print("=" * 110)
    print(f"Thăm dò C2 trên code 20k và SciFact (L = 5), seed {SEEDS_C}: hiệu tại số ứng viên của srp (5, 8)")
    print("=" * 110)
    by = defaultdict(list)
    for fn in glob.glob("probeP_*.json"):
        d = jl(fn)
        if d and d["argv"]["seed"] in SEEDS_C and d["argv"]["dataset"] in ("code", "scifact"):
            by[(d["argv"]["dataset"], tag_of(d))].append(d)
    for k in sorted(by):
        dl, rat = [], []
        for d in by[k]:
            vs, vi = d["variants"].get("srp"), d["variants"].get("itq_q")
            if vs is None or vi is None:
                continue
            fo = lambda v: frontier([(v["results"][L][T]["cand"], v["results"][L][T]["final_r5"]) for L in v["results"]
                                     for T in v["results"][L] if T != "storage"])
            c = vs["results"]["5"]["8"]["cand"]
            fi, fs = interp(fo(vi), c), interp(fo(vs), c)
            dl.append(float("nan") if fi is None or fs is None else fi - fs)
            rat.append(vs["results"]["5"]["storage"]["max"] / max(1, vi["results"]["5"]["storage"]["max"]))
        print(f"   {k[0]:8s} {k[1]:8s} n={len(dl)} Δfinal {np.nanmean(dl):+6.2f}  tỉ lệ tải tối đa {np.mean(rat):5.1f}")
    print()


def checks():
    print("=" * 110)
    print("Tự kiểm")
    print("=" * 110)
    for fn in sorted(glob.glob("probeVR_*.json")):
        d = jl(fn)
        if not d:
            continue
        for nm in ("check_prev", "check_10", "check_06"):
            c = d.get(nm)
            if c:
                print(f"   {fn:45s} {nm}: {c['n']} giá trị, {'KHỚP' if c['bad'] == 0 and c['n'] > 0 else str(c['bad']) + ' LỆCH ' + str(c.get('diffs', [])[:3])}")
    # placement học trong 11 so với 10 cùng seed (offline)
    n, bad = 0, []
    for t in TAGS:
        for s in SEEDS_C:
            fv, fp = f"probeV8_code100kfq_{t}_s{s}_itq_q.json", f"probeP_code100kfq_{t}_s{s}.json"
            if os.path.exists(fv) and os.path.exists(fp):
                v, p = jl(fv), jl(fp)
                if not v or not p or v.get("native_f1") is None:
                    continue
                r10 = p["variants"]["itq_q"]["results"]["5"]["8"]
                for k, x in v["native_f1"].items():
                    n += 1
                    if abs(x - r10[k]) > 1e-9:
                        bad.append((t, s, k, r10[k], x))
    print(f"   placement itq_q trong 11 so với 10 (f = 1, L = 5, T = 8): {n} giá trị, {'KHỚP' if not bad and n else str(len(bad)) + ' LỆCH ' + str(bad[:4])}")
    print()


def main():
    h1()
    h2()
    h345()
    print("=" * 110)
    print("TÓM TẮT ĐÁNH GIÁ XÁC NHẬN")
    print("=" * 110)
    for nm, ok, det in VERDICT:
        print(f"   {'ĐẠT ' if ok else 'KHÔNG ĐẠT'}  {nm:22s} {det}")
    print(f"   Tổng: {sum(1 for _, ok, _ in VERDICT if ok)} trên {len(VERDICT)} tiêu chí đạt\n")
    explore("itq_q", SEEDS_A, f"THĂM DÒ. Mọi chính sách trên placement học itq_q, seed {SEEDS_A} (TB ± độ lệch chuẩn; hiệu kèm KTC 95%)")
    explore("u", SEEDS_B, f"THĂM DÒ. Mọi chính sách trên khoá của bài (u), seed {SEEDS_B}")
    explore_c2_small()
    checks()


if __name__ == "__main__":
    main()
