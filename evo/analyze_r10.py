#!/usr/bin/env python3
"""
analyze_r10.py  —  đánh giá đợt 10 theo đúng evo/PREREG_round10.md (H9, H10), rồi in phần thăm dò: placement trên seed mới
(E1), C3 trên placement có giới hạn tải (E2), migrate tới khi xong (E3), và tự kiểm.
Đọc ở thư mục hiện tại (thư mục gốc repo):
  probeP10_code100kfq_<space>_s<seed>.json               (pha A, SEEDS_A)
  probeV10_code100kfq_<tag>_s<seed>_itq_q_cap16.json     (pha B, SEEDS_B)
  probeV10F_<ds>_<tag>_s<seed>_itq_q.json                (pha C, ds = code, scifact; SEEDS_C)
  probePR10_*.json, probeVR10_*.json                     (pha R)
  probeV8_code100kfq_<tag>_s<seed>_itq_q.json            (đợt 8, chỉ để tham khảo ở E2)
"""
import glob, json, math, os
from collections import defaultdict
import numpy as np

env = lambda k, d: [int(x) for x in os.environ.get(k, d).split()]
SEEDS_A = env("SEEDS_A", "16 17 18")
SEEDS_B = env("SEEDS_B", "16 17 18 19 20 21 22 23 24 25")
SEEDS_C = env("SEEDS_C", "16 17 18 19 20 21 22 23 24 25")
SEEDS_8 = env("SEEDS_8", "6 7 8 9 10 11 12 13 14 15")
TAGS = os.environ.get("TAGS", "bgebase e5large arctic").split()
SPACES = os.environ.get("SPACES", "bgebase e5large arctic m0").split()
CAPV = os.environ.get("CAPV", "itq_q+cap16")
TCRIT = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
         11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086}
VERDICT = []
LINE = "=" * 110


def jl(fn):
    if not os.path.exists(fn):
        return None
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
        return "    n/a   "
    return f"{np.mean(v):6.1f}±{np.std(v, ddof=1) if len(v) > 1 else 0:4.1f}"


def cis(v):
    m, lo, hi, n = ci(v)
    return f"{m:+5.1f}[{lo:+.1f},{hi:+.1f}]" if n else "   n/a   "


def frontier(points):
    pts = sorted(points)
    out, best = [], -1e9
    for c, v in pts:
        if v > best:
            out.append((c, v)); best = v
    return out


def interp(front, c):
    if not front or c < front[0][0]:
        return None
    for (c0, v0), (c1, v1) in zip(front, front[1:]):
        if c0 <= c <= c1:
            if c1 == c0:
                return max(v0, v1)
            w = (math.log(c) - math.log(c0)) / (math.log(c1) - math.log(c0))
            return v0 + w * (v1 - v0)
    return front[-1][1]


def pts(v, x="cand", y="final_r5"):
    return [(v["results"][L][T][x], v["results"][L][T][y]) for L in v["results"] for T in v["results"][L] if T != "storage"]


def verdict(name, ok, detail):
    VERDICT.append((name, ok, detail))
    print(f"   {'ĐẠT ' if ok else 'KHÔNG ĐẠT'}  {name}: {detail}")


def snap_end(r):
    return r["snapshots"][str(max(int(k) for k in r["snapshots"]))]


def place_row(vs, vi):
    """So biến thể vi với srp (vs) theo cách tính của H2, cùng các thước đo tải."""
    c = vs["results"]["5"]["8"]["cand"]
    fi, fs = interp(frontier(pts(vi)), c), interp(frontier(pts(vs)), c)
    gi, gs = interp(frontier(pts(vi, "cand", "gold_rr20")), c), interp(frontier(pts(vs, "cand", "gold_rr20")), c)
    nd = vs["results"]["5"]["8"]["nodes"]
    pi, ps = interp(frontier(pts(vi, "nodes")), nd), interp(frontier(pts(vs, "nodes")), nd)
    st, st0 = vi["results"]["5"]["storage"], vs["results"]["5"]["storage"]
    q58 = vi["results"]["5"]["8"]
    return dict(df=(fi - fs) if fi is not None and fs is not None else float("nan"),
                dg=(gi - gs) if gi is not None and gs is not None else float("nan"),
                dp=(pi - ps) if pi is not None and ps is not None else float("nan"),
                ratio=st0["max"] / max(1, st["max"]), mx=st["max"], p99=st["p99"], top1=100 * st["top1pct_share"],
                ql=100 * q58["qload"]["max_frac"], fin58=q58["final_r5"], cand58=q58["cand"], nodes58=q58["nodes"],
                moved=(100 * vi["cap"]["moved_frac_L5"]) if "cap" in vi else 0.0)


# ----------------------------------------------------------------- H9 (pha A)
def h9():
    print(LINE)
    print(f"H9. Placement có giới hạn tải {CAPV} trên code100kfq, seed {SEEDS_A}: hiệu final tại số ứng viên của srp (L=5, T=8); "
          "tỉ lệ tải tối đa ở L=5")
    print(LINE)
    for t in ["arctic", "bgebase", "m0", "e5large"]:
        if t not in SPACES:
            continue
        dl, rat = [], []
        for s in SEEDS_A:
            d = jl(f"probeP10_code100kfq_{t}_s{s}.json")
            if not d or "srp" not in d["variants"] or CAPV not in d["variants"]:
                continue
            r = place_row(d["variants"]["srp"], d["variants"][CAPV])
            dl.append(r["df"]); rat.append(r["ratio"])
        m = float(np.nanmean(dl)) if dl else float("nan")
        rr = float(np.mean(rat)) if rat else float("nan")
        print(f"   {t:8s} n={len(dl)}  Δfinal tại ứng viên của srp = {m:+.2f} (theo seed {[round(x, 1) for x in dl]}); "
              f"tỉ lệ tải tối đa srp/{CAPV} ở L=5 = {rr:.1f} (theo seed {[round(x, 1) for x in rat]})")
        if t != "e5large":
            verdict(f"H9a recall {t}", len(dl) == len(SEEDS_A) and m >= 3, f"Δ = {m:+.2f} (cần >= +3)")
        verdict(f"H9b tải {t}", len(rat) == len(SEEDS_A) and rr >= 3, f"tỉ lệ = {rr:.1f} (cần >= 3)")
    print()


# ----------------------------------------------------------------- H10 (pha B)
def runs_b(t, seeds):
    out = {}
    for s in seeds:
        d = jl(f"probeV10_code100kfq_{t}_s{s}_itq_q_cap16.json")
        if d:
            out[s] = {k: v for k, v in d["runs"].items() if k.count("|") == 2}
    return out


def h10():
    print(LINE)
    print(f"H10. C3 trên placement {CAPV}, code100kfq, Zipf 1, seed {SEEDS_B} (KTC 95% theo t, ghép cặp)")
    print(LINE)
    for t in TAGS:
        R = runs_b(t, SEEDS_B)
        ss = sorted(s for s in R if all(f"z1|PROB|{p}" in R[s] for p in ("static", "lazy", "lazyVbgD")))
        if len(ss) < len(SEEDS_B):
            print(f"*** {t}: chỉ có {len(ss)} trên {len(SEEDS_B)} seed")
        if not ss:
            continue
        g = lambda s, p: R[s][f"z1|PROB|{p}"]
        da = [snap_end(g(s, "lazyVbgD"))["final"] - snap_end(g(s, "lazy"))["final"] for s in ss]
        db = [snap_end(g(s, "lazyVbgD"))["final"] - snap_end(g(s, "static"))["final"] for s in ss]
        dc = [g(s, "lazy")["totals"]["rr"] - g(s, "static")["totals"]["rr"] for s in ss]
        dual = [g(s, "lazyVbgD")["totals"]["dual_end"] for s in ss]
        fr = [g(s, "lazyVbgD")["totals"]["fetch"] / max(1e-9, g(s, "lazy")["totals"]["fetch"]) for s in ss]
        ma, loa, hia, na = ci(da); mb = ci(db); mc_, loc, hic, _ = ci(dc)
        print(f"\n   --- {t} (n = {na} seed)")
        print(f"   lazyVbgD − lazy, final giữ riêng: TB {ma:+.2f}, KTC [{loa:+.2f}, {hia:+.2f}], dương ở "
              f"{sum(x > 0 for x in da)}/{len(da)} seed")
        print(f"   lazyVbgD − static, final giữ riêng: TB {mb[0]:+.2f}, KTC [{mb[1]:+.2f}, {mb[2]:+.2f}]")
        print(f"   lazy − static, rerank trên dòng: TB {mc_:+.2f}, KTC [{loc:+.2f}, {hic:+.2f}]")
        print(f"   dual cuối dòng của lazyVbgD: TB {np.mean(dual):.1f}%; payload lazyVbgD / lazy: TB {np.mean(fr):.3f}")
        full = na == len(SEEDS_B)
        verdict(f"H10a {t}", full and loa > 0, f"cận dưới KTC {loa:+.2f} (cần > 0)")
        verdict(f"H10b {t}", full and mb[0] >= 3, f"TB {mb[0]:+.2f} (cần >= +3)")
        verdict(f"H10c {t}", full and hic < 0, f"cận trên KTC {hic:+.2f} (cần < 0)")
        verdict(f"H10d {t}", full and np.mean(dual) <= 40 and np.mean(fr) <= 1 / 3,
                f"dual {np.mean(dual):.1f}% (cần <= 40), payload {np.mean(fr):.3f} (cần <= 0,333)")
    print()


# ----------------------------------------------------------------- E1 (pha A)
def explore_place():
    print(LINE)
    print(f"THĂM DÒ E1. Placement trên seed mới (pha A), code100kfq, seed {SEEDS_A}. So với srp như H2: Δfinal và Δgold tại số "
          "ứng viên của srp (L=5, T=8), Δfinal tại số peer của srp; tải ở L=5")
    print(LINE)
    V = ("srp_c", "itq_q", "itq128_q", "itq_q+cap8", "itq_q+cap16", "itq_q+cap32")
    for t in SPACES:
        rows = defaultdict(list)
        srp_rows = []
        for s in SEEDS_A:
            d = jl(f"probeP10_code100kfq_{t}_s{s}.json")
            if not d or "srp" not in d["variants"]:
                continue
            vs = d["variants"]["srp"]
            st0 = vs["results"]["5"]["storage"]
            srp_rows.append(dict(mx=st0["max"], top1=100 * st0["top1pct_share"], fin58=vs["results"]["5"]["8"]["final_r5"],
                                 cand58=vs["results"]["5"]["8"]["cand"], nodes58=vs["results"]["5"]["8"]["nodes"]))
            for vn in V:
                if vn in d["variants"]:
                    rows[vn].append(place_row(vs, d["variants"][vn]))
        if not srp_rows:
            continue
        f0 = lambda k: float(np.mean([x[k] for x in srp_rows]))
        print(f"\n--- {t}: srp (5,8) final {f0('fin58'):5.1f}, ứng viên {f0('cand58'):7.0f}, peer {f0('nodes58'):5.0f}; "
              f"record tối đa {[x['mx'] for x in srp_rows]}, 1% peer giữ {f0('top1'):4.1f}%")
        for vn in V:
            r = rows.get(vn)
            if not r:
                continue
            f = lambda k: float(np.nanmean([x[k] for x in r]))
            print(f"   {vn:12s} n={len(r)} Δfinal {f('df'):+6.2f}  Δgold {f('dg'):+6.2f}  Δfinal cùng số peer {f('dp'):+6.2f}  "
                  f"tỉ lệ tải {f('ratio'):6.1f} (theo seed {[round(x['ratio'], 1) for x in r]})  record tối đa "
                  f"{[x['mx'] for x in r]}  p99 {f('p99'):5.1f}  1% peer giữ {f('top1'):4.1f}%  peer nóng nhất nhận "
                  f"{f('ql'):4.1f}% query  (5,8): final {f('fin58'):5.1f}, ứng viên {f('cand58'):7.0f}  dời {f('moved'):5.2f}%")
    print()


# ----------------------------------------------------------------- E2 (pha B)
POLB = ["static", "lazy", "lazyV1", "lazyVbgD", "full"]
PAIRSB = (("lazyVbgD", "lazy"), ("lazyVbgD", "static"), ("full", "lazyVbgD"), ("lazy", "static"))


def policy_table(R, z, pols, pairs):
    print(f"{'chính sách':10s} {'dòng final':>11s} {'dòng rr':>11s} {'dòng gold':>11s} {'giữ final':>11s} {'giữ rr':>11s} "
          f"{'giữ gold':>11s} {'tải/q':>6s} {'mới/q':>6s} {'f cuối':>7s} {'dual':>6s} {'peer/q':>7s} {'chấm/q':>8s}")
    for p in pols:
        xs = [R[s][f"z{z}|PROB|{p}"] for s in R if f"z{z}|PROB|{p}" in R[s]]
        if not xs:
            continue
        T_ = lambda m: ms([x["totals"].get(m) for x in xs])
        H_ = lambda m: ms([snap_end(x).get(m) for x in xs])
        print(f"{p:10s} {T_('final')} {T_('rr')} {T_('gold_rr')} {H_('final')} {H_('rr')} {H_('gold_rr')} "
              f"{np.mean([x['totals']['fetch'] for x in xs]):6.1f} {np.mean([x['totals']['new'] for x in xs]):6.2f} "
              f"{100 * np.mean([x['totals']['f_end'] for x in xs]):6.1f}% {np.mean([x['totals']['dual_end'] for x in xs]):5.1f}% "
              f"{np.mean([x['totals']['nodes'] for x in xs]):7.0f} {np.mean([x['totals'].get('scan', float('nan')) for x in xs]):8.0f}")
    for a_, b_ in pairs:
        cells = []
        for kind, m in (("t", "final"), ("t", "rr"), ("t", "gold_rr"), ("s", "final"), ("s", "rr"), ("s", "gold_rr")):
            dv = []
            for s in R:
                ka, kb = f"z{z}|PROB|{a_}", f"z{z}|PROB|{b_}"
                if ka in R[s] and kb in R[s]:
                    va = R[s][ka]["totals"][m] if kind == "t" else snap_end(R[s][ka])[m]
                    vb = R[s][kb]["totals"][m] if kind == "t" else snap_end(R[s][kb])[m]
                    if va == va and vb == vb:
                        dv.append(va - vb)
            if dv:
                cells.append(f"{('dòng' if kind == 't' else 'giữ')}-{m}:{cis(dv)}")
        if cells:
            print(f"   {a_} − {b_:8s} " + "  ".join(cells))


def cells(Rt, pols=("static", "lazy", "lazyVbgD")):
    """Đếm ô như đợt 8: model × workload × 6 chỉ số, ngưỡng 1 điểm."""
    c = dict(n=0, lazy_lt_static=0, V_gt_lazy=0, V_lt_static=0)
    low = []
    for t, R in Rt.items():
        for z in ("1", "0"):
            for kind, m in (("t", "final"), ("t", "rr"), ("t", "gold_rr"), ("s", "final"), ("s", "rr"), ("s", "gold_rr")):
                vals = {}
                for p in pols:
                    xs = [R[s][f"z{z}|PROB|{p}"] for s in R if f"z{z}|PROB|{p}" in R[s]]
                    if xs:
                        vals[p] = float(np.mean([x["totals"][m] if kind == "t" else snap_end(x)[m] for x in xs]))
                if len(vals) < 3 or any(v != v for v in vals.values()):
                    continue
                c["n"] += 1
                c["lazy_lt_static"] += vals["lazy"] < vals["static"] - 1
                c["V_gt_lazy"] += vals["lazyVbgD"] > vals["lazy"] + 1
                c["V_lt_static"] += vals["lazyVbgD"] < vals["static"] - 1
                if vals["lazyVbgD"] < vals["static"] - 1:
                    low.append((t, z, ("dòng" if kind == "t" else "giữ") + "-" + m, round(vals["lazyVbgD"] - vals["static"], 2)))
    return c, low


def explore_b():
    print(LINE)
    print(f"THĂM DÒ E2. C3 trên placement {CAPV} (pha B), code100kfq, seed {SEEDS_B}; dòng cuối mỗi model là đợt 8 (itq_q không "
          f"trần, seed {SEEDS_8}) chỉ để tham khảo")
    print(LINE)
    Rt = {}
    for t in TAGS:
        R = runs_b(t, SEEDS_B)
        if not R:
            continue
        Rt[t] = R
        for z in ("1", "0"):
            print(f"\n--- {t}, Zipf {z}, n = {len(R)} seed")
            policy_table(R, z, POLB, PAIRSB)
        B = {}
        for s in SEEDS_8:
            d = jl(f"probeV8_code100kfq_{t}_s{s}_itq_q.json")
            if d:
                B[s] = d["runs"]
        if B:
            for p in ("static", "lazy", "lazyVbgD", "full"):
                xs = [B[s][f"z1|PROB|{p}"] for s in B if f"z1|PROB|{p}" in B[s]]
                if xs:
                    print(f"   [đợt 8, Zipf 1] {p:9s} giữ final {ms([snap_end(x)['final'] for x in xs])}  dòng rr "
                          f"{ms([x['totals']['rr'] for x in xs])}  tải/q {np.mean([x['totals']['fetch'] for x in xs]):5.1f}")
    if Rt:
        c, low = cells(Rt)
        print(f"\n   Đếm ô (model × workload × 6 chỉ số, ngưỡng 1 điểm): lazy kém static ở {c['lazy_lt_static']}/{c['n']}; "
              f"lazyVbgD hơn lazy ở {c['V_gt_lazy']}/{c['n']}; lazyVbgD kém static ở {c['V_lt_static']}/{c['n']} {low}")
    print()


# ----------------------------------------------------------------- E3 (pha C)
FPOL = ["bg", "lazybg", "rebuild", "lazyVbgD", "lazyVbgDc25"]


def area(snaps, T):
    """Trung bình final giữ riêng trên [0, T], hình thang qua các checkpoint <= T."""
    cs = sorted(int(c) for c in snaps if int(c) <= T)
    if len(cs) < 2 or cs[-1] != T:
        return float("nan")
    v = [snaps[str(c)]["final"] for c in cs]
    return float(sum((cs[i + 1] - cs[i]) * (v[i] + v[i + 1]) / 2 for i in range(len(cs) - 1)) / T)


def win_mean(r, T, key):
    """Trung bình theo lượt của một đại lượng cửa sổ trên các cửa sổ kết thúc trước hoặc đúng T."""
    ws = [w for w in r["windows"] if w["t_end"] <= T]
    if not ws:
        return float("nan")
    lens = np.diff([0] + [w["t_end"] for w in ws])
    return float(np.sum([w[key] * n for w, n in zip(ws, lens)]) / np.sum(lens))


def explore_finish():
    print(LINE)
    print(f"THĂM DÒ E3. Migrate tới khi xong (pha C), placement itq_q, Zipf 1, seed {SEEDS_C}")
    print("   giữ@[0,T] = trung bình final giữ riêng trên [0, T] (hình thang); dòng = final và rerank trên dòng trong [0, T); "
          "lưu trữ = (E0 + E1 + bản đang dựng) / N")
    print(LINE)
    for ds in ("code", "scifact"):
        for t in TAGS:
            R = {}
            for s in SEEDS_C:
                d = jl(f"probeV10F_{ds}_{t}_s{s}_itq_q.json")
                if d:
                    R[s] = d
            if not R:
                continue
            d0 = R[min(R)]
            Ts = d0.get("bg_finish", [])
            print(f"\n--- {ds} {t}, n = {len(R)} seed, dòng {d0['argv']['stream']} lượt, N = {d0['N']}")
            for p in ("static", "lazy", "full"):
                xs = [R[s]["runs"].get(f"z1|PROB|{p}") for s in R]
                xs = [x for x in xs if x]
                if xs:
                    tdn = [x["totals"].get("t_done", -1) for x in xs]
                    print(f"   {p:12s} giữ cuối {ms([snap_end(x)['final'] for x in xs])}  dòng final {ms([x['totals']['final'] for x in xs])}"
                          f"  xong {sum(1 for v in tdn if v >= 0)}/{len(tdn)} seed"
                          + (f" (lượt TB {np.mean([v for v in tdn if v >= 0]):.0f})" if any(v >= 0 for v in tdn) else ""))
            for T in Ts:
                print(f"   T = {T}:")
                A = defaultdict(dict)
                for p in FPOL + ["static", "full"]:
                    for s in R:
                        key = f"z1|PROB|{p}|T{T}" if p in FPOL else f"z1|PROB|{p}"
                        r = R[s]["runs"].get(key)
                        if r:
                            A[p][s] = r
                for p in FPOL:
                    xs = A[p]
                    if not xs:
                        continue
                    tdn = [x["totals"].get("t_done", -1) for x in xs.values()]
                    ar = [area(x["snapshots"], T) for x in xs.values()]
                    print(f"      {p:12s} xong lượt {np.mean(tdn):7.0f} [{min(tdn)}, {max(tdn)}]  lưu trữ đỉnh "
                          f"{np.mean([x['totals']['store_peak'] for x in xs.values()]):5.1f}% TB "
                          f"{np.mean([x['totals']['store_mean'] for x in xs.values()]):5.1f}%  dual đỉnh "
                          f"{np.mean([x['totals']['dual_peak'] for x in xs.values()]):5.1f}%  giữ@[0,T] {ms(ar)}  dòng final "
                          f"{ms([win_mean(x, T, 'final') for x in xs.values()])} rr {ms([win_mean(x, T, 'rr') for x in xs.values()])}  "
                          f"tải/q {np.mean([win_mean(x, T, 'fetch') for x in xs.values()]):5.1f}  mới/q "
                          f"{np.mean([win_mean(x, T, 'new') for x in xs.values()]):5.2f}  retire do trần "
                          f"{np.mean([x['totals'].get('cap_retired', 0) for x in xs.values()]):7.0f}  gỡ E0 khi xong "
                          f"{np.mean([x['totals'].get('e0_dropped', 0) for x in xs.values()]):7.0f}")
                for p in ("static", "full"):
                    if A[p]:
                        print(f"      {p:12s} giữ@[0,T] {ms([area(x['snapshots'], T) for x in A[p].values()])}")
                for a_, b_ in (("lazyVbgD", "lazybg"), ("lazyVbgD", "rebuild"), ("lazyVbgDc25", "lazyVbgD"),
                               ("lazyVbgDc25", "lazybg"), ("lazybg", "rebuild"), ("lazyVbgD", "static")):
                    dv = [area(A[a_][s]["snapshots"], T) - area(A[b_][s]["snapshots"], T)
                          for s in R if s in A[a_] and s in A[b_]]
                    dw = [win_mean(A[a_][s], T, "final") - win_mean(A[b_][s], T, "final")
                          for s in R if s in A[a_] and s in A[b_]]
                    if dv:
                        print(f"      {a_} − {b_:9s} giữ@[0,T] {cis(dv)}   dòng final {cis(dw)}")
                cps = sorted(int(c) for c in A["lazyVbgD"][min(A["lazyVbgD"])]["snapshots"]) if A["lazyVbgD"] else []
                for p in ("rebuild", "lazybg", "lazyVbgD", "lazyVbgDc25"):
                    if A[p]:
                        traj = [np.mean([A[p][s]["snapshots"][str(c)]["final"] for s in A[p]]) for c in cps]
                        print(f"      quỹ đạo giữ {p:12s} " + " ".join(f"t{c}:{v:4.1f}" for c, v in zip(cps, traj)))
                if A["lazyVbgD"]:
                    st = [np.mean([100 * A["lazyVbgD"][s]["snapshots"][str(c)].get("store", float("nan")) for s in A["lazyVbgD"]])
                          for c in cps]
                    print(f"      lưu trữ lazyVbgD (%)  " + " ".join(f"t{c}:{v:5.1f}" for c, v in zip(cps, st)))
    print()


# ----------------------------------------------------------------- tự kiểm
def checks():
    print(LINE)
    print("Tự kiểm")
    print(LINE)

    def show(fn, c, nm):
        print(f"   {fn:52s} {nm}: {c['n']} giá trị, "
              f"{'KHỚP' if c['bad'] == 0 and c['n'] > 0 else str(c['bad']) + ' LỆCH ' + str(c.get('diffs', [])[:3])}")
    for fn in sorted(glob.glob("probePR10_*.json")) + sorted(glob.glob("probeVR10_*.json")):
        d = jl(fn)
        if d and d.get("check_prev"):
            show(fn, d["check_prev"], "check_prev")
    for fn in sorted(glob.glob("probePR10_*.json")):
        d = jl(fn)
        if not d:
            continue
        va, vb = d["variants"].get("itq_q"), d["variants"].get("itq_q+cap1000000")
        if va and vb:
            n, bad = 0, 0

            def walk(x, y):
                nonlocal n, bad
                if isinstance(x, dict):
                    for k, v in x.items():
                        if isinstance(y, dict) and k in y:
                            walk(v, y[k])
                elif isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    n += 1
                    bad += not (abs(x - y) <= 1e-9 or (x != x and y != y))
            walk(va["results"], vb["results"])
            print(f"   {fn:52s} itq_q+cap1000000 so với itq_q: {n} giá trị, {'KHỚP' if bad == 0 and n > 0 else f'{bad} LỆCH'}; "
                  f"dời {sum(vb['cap']['moved'])} record")
    n_ok, n_tot = 0, 0
    for fn in sorted(glob.glob("probeV10_code100kfq_*_itq_q_cap16.json")):
        d = jl(fn)
        if d and d.get("check_10"):
            n_tot += 1
            c = d["check_10"]
            if c["bad"] == 0 and c["n"] > 0:
                n_ok += 1
            else:
                show(fn, c, "check_10")
    print(f"   pha B: placement {CAPV} trong 11 so với 10 (seed có file của pha A): {n_ok}/{n_tot} file KHỚP")
    # pha C: sau lượt xong, mọi chính sách có nền trùng full; trước lượt xong, rebuild trùng static
    n_post, bad_post, n_pre, bad_pre = 0, 0, 0, 0
    for fn in sorted(glob.glob("probeV10F_*_itq_q.json")):
        d = jl(fn)
        if not d:
            continue
        runs = d["runs"]
        fu, stc = runs.get("z1|PROB|full"), runs.get("z1|PROB|static")
        for k, r in runs.items():
            if "|T" not in k or not fu:
                continue
            td = r["totals"].get("t_done", -1)
            for c, sv in r["snapshots"].items():
                if td >= 0 and int(c) >= td:
                    n_post += 1
                    bad_post += any(abs(sv[m] - fu["snapshots"][c][m]) > 1e-9 for m in ("final", "rr"))
                elif k.split("|")[2] == "rebuild" and stc:
                    n_pre += 1
                    bad_pre += any(abs(sv[m] - stc["snapshots"][c][m]) > 1e-9 for m in ("final", "rr"))
    print(f"   pha C: checkpoint sau lượt xong trùng full: {n_post - bad_post}/{n_post}; rebuild trước lượt xong trùng static: "
          f"{n_pre - bad_pre}/{n_pre}")
    print()


def main():
    h9()
    h10()
    print(LINE)
    print("TÓM TẮT ĐÁNH GIÁ ĐĂNG KÝ TRƯỚC (H9, H10)")
    print(LINE)
    for nm, ok, det in VERDICT:
        print(f"   {'ĐẠT ' if ok else 'KHÔNG ĐẠT'}  {nm:22s} {det}")
    print(f"   Tổng: {sum(1 for _, ok, _ in VERDICT if ok)} trên {len(VERDICT)} tiêu chí đạt\n")
    explore_place()
    explore_b()
    explore_finish()
    checks()


if __name__ == "__main__":
    main()
