#!/usr/bin/env python3
"""
analyze_r12.py  —  đánh giá đợt 12 theo đúng evo/PREREG_round12.md (H18 đến H21), rồi in phần thăm dò E1 đến E7 và tự
kiểm. Đọc ở thư mục hiện tại (thư mục gốc repo):
  probeA12_<ds>_<space>_s<seed>.json, probeP12_<ds>_<space>_s<seed>.json   (pha A và N, SEEDS_A)
  probeV12F_<ds>_<tag>_s<seed>_cap16.json                                  (pha C, SEEDS_C)
  probeVR12F_*.json, probeVR12_*.json                                       (pha R)
  evo/r12_logs/e12_*.log, evo/r12_logs/jobs.log                             (pha E, chỉ cho E7)
Danh sách seed, model, không gian lấy từ biến môi trường do run_round12.sh đặt (mặc định đúng như đăng ký trước).
"""
import glob, json, math, os, re
from collections import defaultdict
import numpy as np

envl = lambda k, d: os.environ.get(k, d).split()
envi = lambda k, d: [int(x) for x in envl(k, d)]
SEEDS_A = envi("SEEDS_A", "36 37 38")
SEEDS_C = envi("SEEDS_C", "36 37 38 39 40 41 42 43 44 45")
SPACES = envl("SPACES", "bgebase e5large arctic m0 minilm gtebase")       # 12 cặp cũ: 6 không gian × 2 corpus
CTAGS = envl("CTAGS", "bgebase e5large arctic gtebase minilm")            # model của pha C
HTAGS = envl("HTAGS", "bgebase e5large arctic")                           # model của H18
NEWTAGS = envl("NEWTAGS", "e5small gtesmall bgesmall mpnet arcticxs")     # 5 model mới
LOGDIR = os.environ.get("R12_LOGS", "evo/r12_logs")
DSETS = ("code", "scifact")
QF_HI, QF_LO = 8e-4, 2e-4
K1, DRAIN, UV2 = "lazyVbgD", "lazyVbgDinf", "lazyVbgDuv2"
FPOL = ["lazybg", "lazyVbgD", "lazyVbgDk2", "lazyVbgDk3", "lazyVbgDu2", "lazyVbgDv2", "lazyVbgDuv2", "lazyVbgDuv3",
        "lazyVbgDinf"]
SHORT = {"lazybg": "lazybg", "lazyVbgD": "k1", "lazyVbgDk2": "k2", "lazyVbgDk3": "k3", "lazyVbgDu2": "u2",
         "lazyVbgDv2": "v2", "lazyVbgDuv2": "uv2", "lazyVbgDuv3": "uv3", "lazyVbgDinf": "drain", "static": "static",
         "full": "full"}
KC_RE = re.compile(r"^lazyVbgD(?:(k|uv|u|v)(\d+)|(inf))$")
TCRIT = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
         11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086}
LADDER = ["srp", "srp+cap16", "srp_c+cap16", "itq_q", "itq_q+cap16"]
VERDICT = []
LINE = "=" * 118
_cache = {}
NAN = float("nan")


def jl(fn):
    if fn in _cache:
        return _cache[fn]
    d = None
    if os.path.exists(fn):
        try:
            d = json.load(open(fn))
        except Exception as e:
            print(f"*** không đọc được {fn}: {e}")
    _cache[fn] = d
    return d


def ci(v):
    v = np.asarray([x for x in v if x is not None and x == x], dtype=float)
    n = len(v)
    if n == 0:
        return NAN, NAN, NAN, 0
    m = float(v.mean())
    if n == 1:
        return m, NAN, NAN, 1
    h = TCRIT.get(n - 1, 1.96) * float(v.std(ddof=1)) / math.sqrt(n)
    return m, m - h, m + h, n


def ms(v, w=6, p=1):
    v = [x for x in v if x is not None and x == x]
    if not v:
        return " " * (w - 3) + "n/a"
    return f"{np.mean(v):{w}.{p}f}"


def cis(v, p=1):
    m, lo, hi, n = ci(v)
    if n == 0:
        return "n/a"
    if n == 1:
        return f"{m:+.{p}f}"
    return f"{m:+.{p}f}[{lo:+.{p}f},{hi:+.{p}f}]"


def nmean(v):
    v = [x for x in v if x is not None and x == x]
    return float(np.mean(v)) if v else NAN


def verdict(name, ok, detail, ran=True):
    st = "KHÔNG CHẠY" if not ran else ("ĐẠT" if ok else "KHÔNG ĐẠT")
    VERDICT.append((name, st, detail))
    print(f"   {st:10s} {name}: {detail}")


def head(title):
    print(LINE)
    print(title)
    print(LINE)


def frontier(points):
    out, best = [], -1e9
    for c, v in sorted(points):
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


def at_ref(d, va, vb, vref, x="cand"):
    """F_va(c) − F_vb(c) với c là số ứng viên (hoặc số peer) của vref ở (L = 5, T = 8)."""
    V = d["variants"]
    if va not in V or vb not in V or vref not in V:
        return NAN
    c = V[vref]["results"]["5"]["8"][x]
    fa, fb = interp(frontier(pts(V[va], x)), c), interp(frontier(pts(V[vb], x)), c)
    return NAN if fa is None or fb is None else fa - fb


def area(snaps, T):
    """Trung bình final giữ riêng trên [0, T], hình thang qua các checkpoint <= T."""
    cs = sorted(int(c) for c in snaps if int(c) <= T)
    if len(cs) < 2 or cs[-1] != T:
        return NAN
    v = [snaps[str(c)]["final"] for c in cs]
    return float(sum((cs[i + 1] - cs[i]) * (v[i] + v[i + 1]) / 2 for i in range(len(cs) - 1)) / T)


def win_mean(r, T, key):
    """Trung bình theo lượt của một đại lượng cửa sổ trên các cửa sổ kết thúc trước hoặc đúng T."""
    ws = [w for w in r["windows"] if w["t_end"] <= T]
    if not ws or any(key not in w for w in ws):
        return NAN
    lens = np.diff([0] + [w["t_end"] for w in ws])
    return float(np.sum([w[key] * n for w, n in zip(ws, lens)]) / np.sum(lens))


def spearman(a, b):
    ok = [(x, y) for x, y in zip(a, b) if x == x and y == y]
    if len(ok) < 3:
        return NAN
    a, b = np.asarray([x for x, _ in ok], dtype=float), np.asarray([y for _, y in ok], dtype=float)
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])


def hits(s):
    return np.asarray([int(c) for c in s], dtype=int) if isinstance(s, str) else np.asarray(s, dtype=int)


def lg(a, b):
    return abs(math.log10(a / b)) if (a == a and b == b and a > 0 and b > 0) else NAN


# ----------------------------------------------------------------- nạp dữ liệu
def files_f(ds, t):
    return {s: d for s in SEEDS_C for d in [jl(f"probeV12F_{ds}_{t}_s{s}_cap16.json")] if d}


def ts_of(F, ds):
    for d in F.values():
        if d.get("bg_finish"):
            return [int(x) for x in d["bg_finish"]]
    return [1500, 3000] if ds == "code" else [400, 800]


def run_of(d, p, T):
    """Run của chính sách p ở ô T (chính sách không có nền dùng run không hậu tố)."""
    return d["runs"].get(f"z1|PROB|{p}|T{T}" if p in FPOL else f"z1|PROB|{p}")


def ret_before(d, p, r):
    """Phần object ngoài S đã mất bản E0 trước lúc gỡ cả index E0 (retire ngay hay retire sau xác nhận), tính bằng
    1 − (số bản E0 gỡ lúc gỡ index) / (N − |S|)."""
    tt = r["totals"]
    if tt.get("t_drop", -1) < 0 and tt.get("t_done", -1) < 0:
        return NAN
    return 100 * (1 - tt["e0_dropped"] / max(1, d["N"] - d["n_sample"]))


# ----------------------------------------------------------------- H18 (và E4)
def c3_cell(F, T):
    """Hiệu ghép cặp của H18 ở một ô."""
    ss = [s for s in sorted(F) if all(run_of(F[s], p, T) for p in (UV2, DRAIN, K1))]
    g = lambda s, p: run_of(F[s], p, T)
    bp = lambda s, p: g(s, p)["totals"]["bytes_peak_m0"]
    return dict(
        n=len(ss), ss=ss,
        area_d=[area(g(s, UV2)["snapshots"], T) - area(g(s, DRAIN)["snapshots"], T) for s in ss],
        rr_d=[win_mean(g(s, UV2), T, "rr") - win_mean(g(s, DRAIN), T, "rr") for s in ss],
        bytes_d=[bp(s, UV2) - bp(s, DRAIN) for s in ss],
        save_d=[100 * (bp(s, DRAIN) - bp(s, UV2)) / bp(s, DRAIN) for s in ss],
        rr_k=[win_mean(g(s, UV2), T, "rr") - win_mean(g(s, K1), T, "rr") for s in ss],
        area_k=[area(g(s, UV2)["snapshots"], T) - area(g(s, K1)["snapshots"], T) for s in ss])


def print_c3_cell(cell, c):
    print(f"   {cell:26s} n={c['n']:2d}  uv2−drain diện tích {cis(c['area_d'], 2):22s} rerank {cis(c['rr_d'], 2):22s} "
          f"byte đỉnh {cis(c['bytes_d'], 0):18s} (tiết kiệm {nmean(c['save_d']):5.2f}%) | uv2−k1 rerank "
          f"{cis(c['rr_k'], 2):22s} diện tích {cis(c['area_k'], 2)}")


def h18():
    head(f"H18. C3 với phép xác minh mạnh hơn, itq_q+cap16, Zipf 1, gỡ E0 đúng ở lượt T, seed {SEEDS_C}: uv2 = lazyVbgDuv2, "
         "drain = lazyVbgDinf, k1 = lazyVbgD; diện tích [0, T]; rerank [0, T); byte đỉnh mỗi object (metadata 0)")
    for ds in DSETS:
        for t in HTAGS:
            F = files_f(ds, t)
            for T in ts_of(F, ds):
                c = c3_cell(F, T)
                full = c["n"] == len(SEEDS_C)
                cell = f"{ds} {t} T={T}"
                print_c3_cell(cell, c)
                lo1, lo2 = ci(c["area_d"])[1], ci(c["rr_d"])[1]
                okA = full and lo1 > -1 and lo2 > -1
                sv = nmean(c["save_d"])
                rd = ("" if not okA else (" -> an toàn nhưng tiết kiệm ít (< 5%), cấu hình chính là drain" if not sv >= 5
                                          else " -> an toàn và tiết kiệm từ 5% trở lên"))
                verdict(f"H18a {cell}", okA, f"cận dưới KTC diện tích {lo1:+.2f}, rerank {lo2:+.2f} (cần > −1){rd}")
                hi = ci(c["bytes_d"])[2]
                verdict(f"H18b {cell}", full and hi < 0, f"cận trên KTC byte đỉnh {hi:+.1f} (cần < 0); tiết kiệm TB {sv:.2f}%")
                lo3 = ci(c["rr_k"])[1]
                verdict(f"H18c {cell}", full and lo3 > 0, f"cận dưới KTC rerank uv2 − k1 {lo3:+.2f} (cần > 0)")
    print()


# ----------------------------------------------------------------- H19, H20, H21 (và E5, E6)
def pair_rows():
    rows = []
    for ds in DSETS:
        for sp in SPACES + NEWTAGS:
            A = [d["ext"] for s in SEEDS_A for d in [jl(f"probeA12_{ds}_{sp}_s{s}.json")] if d]
            P = [d for s in SEEDS_A for d in [jl(f"probeP12_{ds}_{sp}_s{s}.json")] if d]
            r = dict(ds=ds, sp=sp, new=sp in NEWTAGS, nA=len(A), nP=len(P), p=NAN, q=NAN, mf=NAN, qp=NAN, qm=NAN, t=NAN,
                     dpeer=NAN, dpeer_s=[], dcand=NAN, dcap=NAN, P=P)
            if A:
                m = lambda k: float(np.mean([e[k] for e in A]))
                r.update(p=m("coll_pred_exact_u"), q=m("coll_meas_u"), mf=m("coll_pred_meanfield"), qp=m("qfrac_pred_u"),
                         qm=m("qfrac_meas_u"))
            if P:
                st = [d["variants"]["srp"]["results"]["5"]["storage"]["top1pct_share"] for d in P if "srp" in d["variants"]]
                r["t"] = 100 * float(np.mean(st)) if st else NAN
                r["dpeer_s"] = [at_ref(d, "srp", "itq_q+cap16", "srp_c+cap16", "nodes") for d in P]
                r["dpeer"] = nmean(r["dpeer_s"])
                r["dcand"] = nmean([at_ref(d, "itq_q+cap16", "srp_c+cap16", "srp_c+cap16") for d in P])
                r["dcap"] = nmean([at_ref(d, "itq_q+cap16", "itq_q", "itq_q") for d in P])
            r["present"] = bool(A) and bool(P)
            r["complete"] = len(A) == len(SEEDS_A) and len(P) == len(SEEDS_A)
            r["group"] = ("lớn" if r["qp"] >= QF_HI else ("nhỏ" if r["qp"] <= QF_LO else "giữa")) if r["qp"] == r["qp"] else "?"
            rows.append(r)
    return rows


def h19_h21(rows):
    new = [r for r in rows if r["new"]]
    old = [r for r in rows if not r["new"]]
    miss = sorted({r["sp"] for r in new if not r["present"]})
    ran = not miss
    note = "" if ran else f" (thiếu cặp của model {miss}; số trên chỉ là thăm dò)"
    oldn = sum(1 for r in old if r["present"])
    n_old_exp = len(SPACES) * len(DSETS)
    newp = [r for r in new if r["present"]]
    allp = [r for r in rows if r["present"]]

    head(f"H19. Quy tắc chọn placement theo qf dự đoán, seed {SEEDS_A}: Δ_peer = F_srp − F_itq_q+cap16 tại số peer của "
         f"srp_c+cap16 ở (5,8); nhóm lớn: qf dự đoán >= {QF_HI:g}; nhóm nhỏ: <= {QF_LO:g}")
    print(f"   {'dataset':8s} {'model':9s} {'qf dự đoán':>10s} {'qf đo':>9s} {'nhóm':>5s} {'Δ_peer':>8s}  theo seed")
    for r in sorted(newp, key=lambda r: r["qp"]):
        print(f"   {r['ds']:8s} {r['sp']:9s} {r['qp']:10.2e} {r['qm']:9.2e} {r['group']:>5s} {r['dpeer']:+8.2f}  "
              f"{[round(x, 2) for x in r['dpeer_s']]}")
    hi = [r for r in newp if r["group"] == "lớn"]
    lo = [r for r in newp if r["group"] == "nhỏ"]
    okA = bool(hi) and all(r["dpeer"] > 0 for r in hi)
    okB = bool(lo) and all(r["dpeer"] < 1 for r in lo)
    verdict("H19a", ran and okA, f"{len(hi)} cặp nhóm lớn, Δ_peer nhỏ nhất "
            f"{min([r['dpeer'] for r in hi], default=NAN):+.2f} (cần mọi cặp > 0){note}", ran and bool(hi))
    verdict("H19b", ran and okB, f"{len(lo)} cặp nhóm nhỏ, Δ_peer lớn nhất "
            f"{max([r['dpeer'] for r in lo], default=NAN):+.2f} (cần mọi cặp < +1){note}", ran and bool(lo))
    rho_n = spearman([r["qp"] for r in newp], [r["dpeer"] for r in newp])
    rho_a = spearman([r["qp"] for r in allp], [r["dpeer"] for r in allp])
    verdict("H19c", ran and rho_n >= 0.6, f"Spearman {rho_n:+.3f} trên {len(newp)}/{len(new)} cặp mới (cần >= 0,6){note}", ran)
    verdict("H19d", ran and oldn == n_old_exp and rho_a >= 0.8,
            f"Spearman {rho_a:+.3f} trên {len(allp)} cặp (cần >= 0,8, đủ {n_old_exp} cặp cũ và {len(new)} cặp mới; có "
            f"{oldn} cặp cũ){note}", ran)
    mid = [r for r in newp if r["group"] == "giữa"]
    if mid:
        print("   cặp mới giữa hai ngưỡng (không dự đoán): " + ", ".join(f"{r['ds']} {r['sp']} qf {r['qp']:.2e} Δ_peer "
                                                                       f"{r['dpeer']:+.2f}" for r in mid))
    print()

    head(f"H20. C2 trên 10 cặp mới, seed {SEEDS_A}: hiệu final tại cùng số ứng viên (biên Pareto, nội suy log)")
    for ds in DSETS:
        for sp in NEWTAGS:
            r = next(x for x in rows if x["ds"] == ds and x["sp"] == sp)
            ranp, full = bool(r["nP"]), r["nP"] == len(SEEDS_A)
            print(f"   {ds:8s} {sp:9s} n={r['nP']}  itq_q+cap16 − srp_c+cap16 tại ứng viên của srp_c+cap16: {r['dcand']:+6.2f};  "
                  f"itq_q+cap16 − itq_q tại ứng viên của itq_q: {r['dcap']:+6.2f}")
            verdict(f"H20a {ds} {sp}", full and r["dcand"] >= 5, f"Δ = {r['dcand']:+.2f} (cần >= +5)", ranp)
            verdict(f"H20b {ds} {sp}", full and r["dcap"] >= -1, f"Δ = {r['dcap']:+.2f} (cần >= −1)", ranp)
    print()

    head(f"H21. Mô hình dị hướng (C1), TB seed {SEEDS_A}; p, q: trùng bucket 16 bit giữa hai document (dự đoán góc, đo); qf: "
         "phần corpus cùng bucket với query (dự đoán, đo); t: phần tải của 1% peer với srp ở L=5")
    print(f"{'dataset':8s} {'không gian':10s} {'p':>9s} {'q':>9s} {'|log p/q|':>9s} {'TT':>9s} {'|log TT/q|':>10s} "
          f"{'qf dự đoán':>10s} {'qf đo':>9s} {'|log|':>6s} {'t':>7s}  n  mới")
    for r in allp:
        print(f"{r['ds']:8s} {r['sp']:10s} {r['p']:9.2e} {r['q']:9.2e} {lg(r['p'], r['q']):9.2f} {r['mf']:9.2e} "
              f"{lg(r['mf'], r['q']):10.2f} {r['qp']:10.2e} {r['qm']:9.2e} {lg(r['qp'], r['qm']):6.2f} {r['t']:6.1f}% "
              f"{r['nA']}/{r['nP']} {'x' if r['new'] else ''}")
    e_a = nmean([lg(r["p"], r["q"]) for r in newp]) if newp else NAN
    e_b = nmean([lg(r["qp"], r["qm"]) for r in newp]) if newp else NAN
    rho = spearman([r["p"] for r in allp], [r["t"] for r in allp])
    print(f"   sai số log10 TB trên mọi cặp: p/q {nmean([lg(r['p'], r['q']) for r in allp]):.3f}, qf "
          f"{nmean([lg(r['qp'], r['qm']) for r in allp]):.3f}; cặp cũ: p/q {nmean([lg(r['p'], r['q']) for r in old if r['present']]):.3f}")
    verdict("H21a", ran and e_a <= 0.2, f"sai số log10 TB {e_a:.3f} trên {len(newp)}/{len(new)} cặp mới (cần <= 0,2){note}", ran)
    verdict("H21b", ran and e_b <= 0.2, f"sai số log10 TB {e_b:.3f} trên {len(newp)}/{len(new)} cặp mới (cần <= 0,2){note}", ran)
    verdict("H21c", ran and oldn == n_old_exp and rho >= 0.8,
            f"Spearman {rho:+.3f} trên {len(allp)} cặp (cần >= 0,8, đủ {n_old_exp} cặp cũ; có {oldn}){note}", ran)
    print()


# ----------------------------------------------------------------- E1, E2, E4: C3
def e1():
    head("THĂM DÒ E1. Đường đánh đổi của C3, gỡ E0 đúng ở lượt T, itq_q+cap16, Zipf 1. diện tích = TB final giữ riêng trên "
         "[0, T]; rr, tải, nhúng (do truy vấn, do nền), peer, chấm = TB trên các cửa sổ trong [0, T); lưu trữ và byte tính "
         "trên cả dòng; retire trước = phần object ngoài S đã gỡ bản E0 trước lượt T; thấy = số lần thấy, mới = số lần thấy "
         "từ query mới (u, uv); Δ = hiệu ghép cặp với drain, và rr với k1")
    for ds in DSETS:
        for t in CTAGS:
            F = files_f(ds, t)
            if not F:
                continue
            d0 = F[min(F)]
            print(f"\n--- {ds} {t}, n = {len(F)} seed, dòng {d0['argv']['stream']} lượt, N = {d0['N']}")
            for T in ts_of(F, ds):
                print(f"   T = {T}")
                print(f"   {'chính sách':10s} {'xong':>5s} {'diện tích':>9s} {'rr':>6s} {'tải/q':>6s} {'nhúng q':>7s} "
                      f"{'nhúng nền':>9s} {'peer/q':>6s} {'chấm/q':>7s} {'lưu đỉnh':>8s} {'B đỉnh':>6s} {'B TB':>6s} "
                      f"{'B64 đỉnh':>8s} {'retire trước':>12s} {'thấy':>7s} {'mới':>6s} {'veto':>7s} {'Δ diện tích':>18s} "
                      f"{'Δ rr':>18s} {'Δ B đỉnh':>16s} {'Δ rr với k1':>18s}")
                ref = {s: run_of(F[s], DRAIN, T) for s in F}
                rk1 = {s: run_of(F[s], K1, T) for s in F}
                for p in ["static", "full"] + FPOL:
                    xs = {s: run_of(F[s], p, T) for s in F if run_of(F[s], p, T)}
                    if not xs:
                        continue
                    v = list(xs.values())
                    tot = lambda k: [x["totals"].get(k, NAN) for x in v]
                    ret = [ret_before(F[s], p, xs[s]) for s in xs] if p in FPOL else [NAN]
                    da = [area(xs[s]["snapshots"], T) - area(ref[s]["snapshots"], T) for s in xs if ref.get(s)]
                    dr = [win_mean(xs[s], T, "rr") - win_mean(ref[s], T, "rr") for s in xs if ref.get(s)]
                    db = [xs[s]["totals"]["bytes_peak_m0"] - ref[s]["totals"]["bytes_peak_m0"] for s in xs if ref.get(s)]
                    dk = [win_mean(xs[s], T, "rr") - win_mean(rk1[s], T, "rr") for s in xs if rk1.get(s)]
                    tdn = [x if x >= 0 else NAN for x in tot("t_done")]
                    print(f"   {SHORT.get(p, p):10s} {ms(tdn, 5, 0)} {ms([area(x['snapshots'], T) for x in v], 9)} "
                          f"{ms([win_mean(x, T, 'rr') for x in v])} {ms([win_mean(x, T, 'fetch') for x in v], 6, 2)} "
                          f"{ms([win_mean(x, T, 'emb_q') for x in v], 7, 2)} {ms([win_mean(x, T, 'emb_bg') for x in v], 9, 2)} "
                          f"{ms([win_mean(x, T, 'nodes') for x in v], 6, 0)} {ms(tot('scan'), 7, 0)} "
                          f"{ms(tot('store_peak'), 8)} {ms(tot('bytes_peak_m0'), 6, 0)} {ms(tot('bytes_mean_m0'), 6, 0)} "
                          f"{ms(tot('bytes_peak_m64'), 8, 0)} {(ms(ret, 11) + '%') if p in FPOL else ' ' * 9 + 'n/a':>12s} "
                          f"{ms(tot('conf_total'), 7, 0)} {ms(tot('conf_distinct'), 6, 0)} {ms(tot('vetoes'), 7, 0)} "
                          f"{cis(da, 2) if p != DRAIN else '':>18s} {cis(dr, 2) if p != DRAIN else '':>18s} "
                          f"{cis(db, 0) if p != DRAIN else '':>16s} {cis(dk, 2) if p != K1 else '':>18s}")
    print()


def e2():
    head("THĂM DÒ E2. Riêng pha 1: k1 − drain khi cả hai gỡ E0 đúng ở lượt T (ghép cặp theo seed)")
    for ds in DSETS:
        for t in CTAGS:
            F = files_f(ds, t)
            for T in ts_of(F, ds) if F else []:
                ss = [s for s in sorted(F) if run_of(F[s], K1, T) and run_of(F[s], DRAIN, T)]
                if not ss:
                    continue
                g = lambda s, p: run_of(F[s], p, T)
                da = [area(g(s, K1)["snapshots"], T) - area(g(s, DRAIN)["snapshots"], T) for s in ss]
                dr = [win_mean(g(s, K1), T, "rr") - win_mean(g(s, DRAIN), T, "rr") for s in ss]
                db = [100 * (g(s, DRAIN)["totals"]["bytes_peak_m0"] - g(s, K1)["totals"]["bytes_peak_m0"])
                      / g(s, DRAIN)["totals"]["bytes_peak_m0"] for s in ss]
                print(f"   {ds:8s} {t:9s} T={T:5d} n={len(ss):2d}  diện tích {cis(da, 2):24s} rerank {cis(dr, 2):24s} "
                      f"byte đỉnh thấp hơn drain {nmean(db):5.1f}%")
    print()


def e3():
    head("THĂM DÒ E3. Mất đường vì retire (lost_retire, TB và lớn nhất) và còn đường tìm (reach_any, thấp nhất) qua các "
         "checkpoint trong (0, T), % vị trí top-5 thật; negative flip so với drain (% query giữ riêng có ít object đúng "
         "trong top-5 hơn drain ở cùng checkpoint, 'TB / lớn nhất' qua các checkpoint trong (0, T))")

    def nfr(xs, ref, c, key):
        worse, n = 0, 0
        for s in xs:
            if s in ref and str(c) in xs[s]["snapshots"] and str(c) in ref[s]["snapshots"]:
                a, b = hits(xs[s]["snapshots"][str(c)][key]), hits(ref[s]["snapshots"][str(c)][key])
                worse += int((a < b).sum()); n += len(a)
        return 100 * worse / n if n else NAN
    for ds in DSETS:
        for t in CTAGS:
            F = files_f(ds, t)
            for T in ts_of(F, ds) if F else []:
                ref = {s: run_of(F[s], DRAIN, T) for s in F if run_of(F[s], DRAIN, T)}
                print(f"\n--- {ds} {t} T={T}")
                for p in FPOL:
                    xs = {s: run_of(F[s], p, T) for s in F if run_of(F[s], p, T)}
                    if not xs:
                        continue
                    cps = sorted(int(c) for c in next(iter(xs.values()))["snapshots"] if 0 < int(c) < T)
                    lr = [nmean([xs[s]["snapshots"][str(c)].get("lost_retire", NAN) for s in xs]) for c in cps]
                    ra = [nmean([xs[s]["snapshots"][str(c)].get("reach_any", NAN) for s in xs]) for c in cps]
                    fl = {k: [nfr(xs, ref, c, k) for c in cps] for k in ("fin_hits", "rr_hits")}
                    st = lambda v: f"{nmean(v):5.2f} / {max([x for x in v if x == x], default=NAN):5.2f}"
                    print(f"   {SHORT[p]:7s} lost_retire {st(lr)}%  reach_any thấp nhất {min([x for x in ra if x == x], default=NAN):5.1f}%"
                          f"  flip so với drain: final {st(fl['fin_hits'])}  rerank {st(fl['rr_hits'])}")
    print()


def e4():
    head(f"THĂM DÒ E4. Các hiệu của H18 cho model không thuộc H18 ({[t for t in CTAGS if t not in HTAGS]}), không chấm ngưỡng")
    for ds in DSETS:
        for t in [x for x in CTAGS if x not in HTAGS]:
            F = files_f(ds, t)
            for T in ts_of(F, ds) if F else []:
                print_c3_cell(f"{ds} {t} T={T}", c3_cell(F, T))
    print()


# ----------------------------------------------------------------- E5, E6: C1, C2 trên 22 cặp
def e5(rows):
    head(f"THĂM DÒ E5. Bậc thang C2 trên 22 cặp, seed {SEEDS_A}. Δ ứng viên / Δ peer: final so với srp_c+cap16 tại số ứng viên "
         "/ số peer của srp_c+cap16 ở (5,8); tải ở L=5: tối đa, p99, phần của 1% peer, Gini; truy vấn tới peer nóng nhất và "
         "công việc chấm lớn nhất ở (5,8); dời và vào peer đầy: % record ở 5 bảng đầu")
    for r in rows:
        D = r["P"]
        if not D:
            continue
        print(f"\n--- {r['ds']} {r['sp']}{' (mới)' if r['new'] else ''}, n = {len(D)} seed; qf dự đoán {r['qp']:.2e} "
              f"(nhóm {r['group']}); (5,8) của srp_c+cap16: ứng viên "
              f"{ms([d['variants']['srp_c+cap16']['results']['5']['8']['cand'] for d in D if 'srp_c+cap16' in d['variants']], 6, 0)}, "
              f"peer {ms([d['variants']['srp_c+cap16']['results']['5']['8']['nodes'] for d in D if 'srp_c+cap16' in d['variants']], 6, 0)}")
        for v in LADDER:
            Dv = [d for d in D if v in d["variants"]]
            if not Dv:
                continue
            R5 = lambda d: d["variants"][v]["results"]["5"]
            cap = lambda d, k: 100 * d["variants"][v].get("cap", {}).get(k, 0.0)
            print(f"   {v:12s} Δ ứng viên {ms([at_ref(d, v, 'srp_c+cap16', 'srp_c+cap16') for d in Dv], 6, 2)}  Δ peer "
                  f"{ms([at_ref(d, v, 'srp_c+cap16', 'srp_c+cap16', 'nodes') for d in Dv], 6, 2)}  (5,8): final "
                  f"{ms([R5(d)['8']['final_r5'] for d in Dv])} ứng viên {ms([R5(d)['8']['cand'] for d in Dv], 7, 0)} peer "
                  f"{ms([R5(d)['8']['nodes'] for d in Dv], 6, 0)}  tải tối đa {ms([R5(d)['storage']['max'] for d in Dv], 6, 0)} "
                  f"p99 {ms([R5(d)['storage']['p99'] for d in Dv], 5, 0)} 1% peer "
                  f"{ms([100 * R5(d)['storage']['top1pct_share'] for d in Dv], 5)}% Gini {ms([R5(d)['storage']['gini'] for d in Dv], 4, 2)}"
                  f"  truy vấn tới peer nóng nhất {ms([100 * R5(d)['8']['qload']['max_frac'] for d in Dv], 5)}%  công việc lớn nhất "
                  f"{ms([R5(d)['8']['work']['max'] for d in Dv], 8, 0)}  dời {ms([cap(d, 'moved_frac_L5') for d in Dv], 5, 2)}%  "
                  f"vào peer đầy {ms([cap(d, 'fallback_frac_L5') for d in Dv], 5, 2)}%")
    print()


def e6(rows):
    head("THĂM DÒ E6. Quy tắc qf như một bộ phân loại: khuyến nghị theo qf dự đoán (SRP khi >= 8e-4, placement học khi <= 2e-4), "
         "biến thể tốt hơn ở cùng số peer (Δ_peer), và công việc chấm của peer nặng nhất ở (5,8), srp / itq_q+cap16")
    tally = defaultdict(lambda: [0, 0, 0])
    for r in sorted([x for x in rows if x["present"]], key=lambda x: x["qp"]):
        rec = {"lớn": "SRP", "nhỏ": "học", "giữa": "chưa kết luận"}.get(r["group"], "?")
        better = "SRP" if r["dpeer"] > 0 else ("học" if r["dpeer"] == r["dpeer"] else "?")
        wr = [d["variants"]["srp"]["results"]["5"]["8"]["work"]["max"]
              / max(1e-9, d["variants"]["itq_q+cap16"]["results"]["5"]["8"]["work"]["max"])
              for d in r["P"] if "srp" in d["variants"] and "itq_q+cap16" in d["variants"]]
        hit = rec in ("SRP", "học") and rec == better
        k_ = "mới" if r["new"] else "cũ"
        if rec in ("SRP", "học"):
            tally[k_][0] += 1; tally[k_][1] += hit
        else:
            tally[k_][2] += 1
        print(f"   {r['ds']:8s} {r['sp']:9s} {'mới' if r['new'] else 'cũ ':3s} qf dự đoán {r['qp']:9.2e}  khuyến nghị "
              f"{rec:14s} tốt hơn ở cùng số peer {better:4s} (Δ_peer {r['dpeer']:+6.2f})  công việc lớn nhất srp / itq_q+cap16 "
              f"{nmean(wr):8.1f} lần")
    for k_ in ("cũ", "mới"):
        a, b, c = tally[k_]
        print(f"   cặp {k_}: quy tắc khuyến nghị ở {a} cặp, đúng {b}; {c} cặp chưa kết luận")
    print()


def e7():
    head("THĂM DÒ E7. Pha nhúng: tốc độ đo được, thời gian, overlap GT top-5 giữa M0 và M1, góc TB tới top-5 (M1)")
    durs = {}
    jfn = os.path.join(LOGDIR, "jobs.log")
    if os.path.exists(jfn):
        for line in open(jfn, encoding="utf-8", errors="replace"):
            m = re.match(r"XONG\s+\S+\s+(e12_\S+)\s+\((\d+)s, mã thoát (\d+)\)", line)
            if m:
                durs[m.group(1)] = (int(m.group(2)), int(m.group(3)))
    fns = sorted(glob.glob(os.path.join(LOGDIR, "e12_*.log")))
    if not fns:
        print("   không có log của pha E (dữ liệu có sẵn, hoặc chưa chạy)")
    pats = dict(rate=r"tốc độ đo được: ([\d.]+) doc/s", dtype=r"dtype=(\S+)", seq=r"max_seq=(\d+)",
                ov=r"GT overlap M0 vs M1 \(top-5\): ([\d.]+)%", ang=r"angle_mean tới top-5 \(M1\) = ([\d.]+)",
                qp=r"query_prefix=(.*?)  passage")
    for fn in fns:
        txt = open(fn, encoding="utf-8", errors="replace").read()
        g = {k: (re.search(p, txt).group(1) if re.search(p, txt) else "n/a") for k, p in pats.items()}
        nm = os.path.basename(fn)[:-4]
        du = durs.get(nm, ("n/a", "n/a"))
        print(f"   {nm:24s} {g['rate']:>6s} doc/s  thời gian {du[0]}s  mã thoát {du[1]}  dtype {g['dtype']}  max_seq "
              f"{g['seq']}  overlap {g['ov']}%  góc {g['ang']}  prefix query {g['qp']}")
    print()


# ----------------------------------------------------------------- tự kiểm
def checks():
    head("Tự kiểm")

    def show(fn, c, nm):
        print(f"   {fn:58s} {nm}: {c['n']} giá trị, "
              f"{'KHỚP' if c['bad'] == 0 and c['n'] > 0 else str(c['bad']) + ' LỆCH ' + str(c.get('diffs', [])[:3])}")
    fr = sorted(glob.glob("probeVR12*.json"))
    for fn in fr:
        d = jl(fn)
        if d and d.get("check_prev"):
            show(fn, d["check_prev"], "so với đợt 11")
            old = jl(d["check_prev"]["file"])
            if old:
                miss = [k for k in old["runs"] if k not in d["runs"]]
                print(f"   {'':58s} đủ {len(old['runs']) - len(miss)}/{len(old['runs'])} run của lượt cũ")
        elif d:
            print(f"   {fn:58s} không có kết quả so với đợt 11")
    if not fr:
        print("   pha R: chưa có file")
    n_ok = n_tot = 0
    for fn in sorted(glob.glob("probeV12F_*_cap16.json")):
        d = jl(fn)
        if d and d.get("check_10"):
            n_tot += 1
            c = d["check_10"]
            if c["bad"] == 0 and c["n"] > 0:
                n_ok += 1
            else:
                show(fn, c, "check_10")
    print(f"   placement itq_q+cap16 trong 11 so với 10 (seed có file của pha A): {n_ok}/{n_tot} file KHỚP")
    cnt = defaultdict(lambda: [0, 0])
    for fn in sorted(glob.glob("probeV12F_*_cap16.json")):
        d = jl(fn)
        if not d:
            continue
        runs = d["runs"]
        fu = runs.get("z1|PROB|full")
        for k, r in runs.items():
            pol = k.split("|")[2]
            tt = r["totals"]
            if "emb_q" in tt:
                cnt["emb"][0] += 1; cnt["emb"][1] += abs(tt["emb_q"] + tt["emb_bg"] - tt["new"]) > 1e-9
            m = re.search(r"\|T(\d+)$", k)
            if not m:
                continue
            T = int(m.group(1))
            cnt["mode"][0] += 1; cnt["mode"][1] += tt.get("finish_drop") != "T"
            cnt["tdrop"][0] += 1; cnt["tdrop"][1] += tt.get("t_drop") != T
            if fu:
                for c, sv in r["snapshots"].items():
                    if int(c) >= T:
                        cnt["post"][0] += 1
                        cnt["post"][1] += any(sv[x] != fu["snapshots"][c][x] for x in ("final", "rr", "fin_hits", "rr_hits"))
            mk = KC_RE.match(pol)
            if pol == DRAIN:
                cnt["drain"][0] += 1; cnt["drain"][1] += tt["retired_total"] != 0
            kind = ("k" if mk.group(3) else mk.group(1)) if mk else "k"
            cnt["veto"][0] += 1; cnt["veto"][1] += (kind in ("k", "u")) and tt.get("vetoes", 0) != 0
            if mk:
                want = 10 ** 9 if mk.group(3) else int(mk.group(2))
                cnt["kind"][0] += 1; cnt["kind"][1] += tt.get("confirm_kind") != kind or tt.get("confirm_k") != want
    f = lambda k: f"{cnt[k][0] - cnt[k][1]}/{cnt[k][0]}"
    print(f"   pha C: gỡ E0 ở đúng lượt T {f('tdrop')} run, --finish-drop T {f('mode')} run; checkpoint từ T trở đi trùng full "
          f"{f('post')}; drain không retire trước lúc gỡ {f('drain')}; quy tắc k, u không có veto {f('veto')}; "
          f"loại quy tắc và ngưỡng đúng tên {f('kind')}; nhúng lại do truy vấn + do nền = new {f('emb')} run")
    n_a, n_p = len(glob.glob("probeA12_*.json")), len(glob.glob("probeP12_*.json"))
    n_f = len(glob.glob("probeV12F_*_cap16.json"))
    exp_ap = (len(SPACES) + len(NEWTAGS)) * len(DSETS) * len(SEEDS_A)
    exp_f = len(CTAGS) * len(DSETS) * len(SEEDS_C)
    print(f"   số file: dị hướng {n_a}/{exp_ap}, placement {n_p}/{exp_ap}, C3 {n_f}/{exp_f}, pha R {len(fr)}/2")
    print()


def main():
    h18()
    rows = pair_rows()
    h19_h21(rows)
    head("TÓM TẮT ĐÁNH GIÁ ĐĂNG KÝ TRƯỚC (H18 đến H21)")
    groups = defaultdict(lambda: [0, 0, 0])
    for nm, st, det in VERDICT:
        print(f"   {st:10s} {nm:30s} {det}")
        g = re.match(r"H\d+", nm).group(0)
        groups[g][0] += st == "ĐẠT"; groups[g][1] += st == "KHÔNG ĐẠT"; groups[g][2] += st == "KHÔNG CHẠY"
    for g in sorted(groups, key=lambda x: int(x[1:])):
        a, b, c = groups[g]
        print(f"   {g}: {a} đạt, {b} không đạt" + (f", {c} không chạy" if c else ""))
    n_ok = sum(1 for _, st, _ in VERDICT if st == "ĐẠT")
    n_run = sum(1 for _, st, _ in VERDICT if st != "KHÔNG CHẠY")
    print(f"   Tổng: {n_ok} trên {n_run} tiêu chí đã chạy đạt; {len(VERDICT) - n_run} tiêu chí không chạy; "
          f"tổng số tiêu chí {len(VERDICT)}\n")
    e1()
    e2()
    e3()
    e4()
    e5(rows)
    e6(rows)
    e7()
    checks()


if __name__ == "__main__":
    main()
