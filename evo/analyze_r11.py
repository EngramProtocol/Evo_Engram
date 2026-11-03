#!/usr/bin/env python3
"""
analyze_r11.py  —  đánh giá đợt 11 theo đúng evo/PREREG_round11.md (H11 đến H17), rồi in phần thăm dò E1 đến E9 và tự
kiểm. Đọc ở thư mục hiện tại (thư mục gốc repo):
  probeA11_<ds>_<space>_s<seed>.json, probeP11_<ds>_<space>_s<seed>.json   (pha A và N, SEEDS_A)
  probeV11_code100kfq_<tag>_s<seed>_cap16.json                             (pha B và N, SEEDS_B)
  probeV11F_<ds>_<tag>_s<seed>_cap16.json                                  (pha C và N, SEEDS_C)
  probeV11G_<ds>_<tag>_s<seed>_L<len>_cap16.json                           (pha G, SEEDS_G)
  probeV11C_code100kfq_<tag>_s<seed>_cap16.json                            (pha F, SEEDS_F)
  probePR11_*.json, probeVR11*.json                                         (pha R)
Danh sách seed, model, không gian lấy từ biến môi trường do run_round11.sh đặt (mặc định đúng như đăng ký trước).
"""
import glob, json, math, os
from collections import defaultdict
import numpy as np

envl = lambda k, d: os.environ.get(k, d).split()
envi = lambda k, d: [int(x) for x in envl(k, d)]
SEEDS_A = envi("SEEDS_A", "26 27 28")
SEEDS_B = envi("SEEDS_B", "26 27 28 29 30 31 32 33 34 35")
SEEDS_C = envi("SEEDS_C", "26 27 28 29 30 31 32 33 34 35")
SEEDS_G = envi("SEEDS_G", "26 27 28 29 30")
SEEDS_F = envi("SEEDS_F", "26 27 28")
TAGS = envl("TAGS", "bgebase e5large arctic")
SPACES = envl("SPACES", "bgebase e5large arctic m0")
NEWTAGS = envl("NEWTAGS", "minilm gtebase")
NEW_ON_100K = envl("NEW_ON_100K", "minilm")                 # model mới có nhúng code100kfq
GL = {"code": envi("GL_CODE", "600 3000"), "scifact": envi("GL_SCI", "155 3000")}
TCRIT = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
         11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086}
CLS = ("k1", "k2", "k3", "k6")
CLSN = {"k1": "lần 1", "k2": "lần 2", "k3": "lần 3-5", "k6": "lần 6+"}
VERDICT = []
LINE = "=" * 118
_cache = {}


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
        return float("nan"), float("nan"), float("nan"), 0
    m = float(v.mean())
    if n == 1:
        return m, float("nan"), float("nan"), 1
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


def verdict(name, ok, detail, ran=True):
    st = "KHÔNG CHẠY" if not ran else ("ĐẠT" if ok else "KHÔNG ĐẠT")
    VERDICT.append((name, st, detail))
    print(f"   {st:10s} {name}: {detail}")


def head(title):
    print(LINE)
    print(title)
    print(LINE)


def snap_end(r):
    return r["snapshots"][str(max(int(k) for k in r["snapshots"]))]


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
        return float("nan")
    c = V[vref]["results"]["5"]["8"][x]
    fa, fb = interp(frontier(pts(V[va], x)), c), interp(frontier(pts(V[vb], x)), c)
    return float("nan") if fa is None or fb is None else fa - fb


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
    if not ws or any(key not in w for w in ws):
        return float("nan")
    lens = np.diff([0] + [w["t_end"] for w in ws])
    return float(np.sum([w[key] * n for w, n in zip(ws, lens)]) / np.sum(lens))


def spearman(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if len(a) < 3:
        return float("nan")
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])


def hits(s):
    return np.asarray([int(c) for c in s], dtype=int) if isinstance(s, str) else np.asarray(s, dtype=int)


# ----------------------------------------------------------------- nạp dữ liệu
def runs_b(t):
    return {s: d["runs"] for s in SEEDS_B for d in [jl(f"probeV11_code100kfq_{t}_s{s}_cap16.json")] if d}


def stream_b(t):
    """Độ dài dòng của các job pha B (đọc từ argv)."""
    for s in SEEDS_B:
        d = jl(f"probeV11_code100kfq_{t}_s{s}_cap16.json")
        if d:
            return int(d["argv"]["stream"])
    return 3000


def files_f(ds, t):
    return {s: d for s in SEEDS_C for d in [jl(f"probeV11F_{ds}_{t}_s{s}_cap16.json")] if d}


def files_g(ds, t, ln):
    return {s: d for s in SEEDS_G for d in [jl(f"probeV11G_{ds}_{t}_s{s}_L{ln}_cap16.json")] if d}


def ts_of(F, ds):
    for d in F.values():
        if d.get("bg_finish"):
            return [int(x) for x in d["bg_finish"]]
    return [1500, 3000] if ds == "code" else [400, 800]


# ----------------------------------------------------------------- H11 (và E9 cho model mới)
def ablation(t, z="1"):
    """Các hiệu của H11 cho một model, ghép cặp theo seed."""
    need = ("lazy", "lazyV1", "lazyVbg", "lazyVbgD", "lazyVbgD_adp")
    R = runs_b(t)
    ss = [s for s in sorted(R) if all(f"z{z}|PROB|{p}" in R[s] for p in need)]
    g = lambda s, p: R[s][f"z{z}|PROB|{p}"]
    return dict(
        ss=ss,
        a=[g(s, "lazyV1")["totals"]["rr"] - g(s, "lazy")["totals"]["rr"] for s in ss],
        b1=[g(s, "lazyVbgD")["totals"]["fetch"] / max(1e-9, g(s, "lazyVbgD_adp")["totals"]["fetch"]) for s in ss],
        b2=[g(s, "lazyVbgD")["totals"]["final"] - g(s, "lazyVbgD_adp")["totals"]["final"] for s in ss],
        c=[snap_end(g(s, "lazyVbgD"))["final"] - snap_end(g(s, "lazyVbg"))["final"] for s in ss],
        d=[snap_end(g(s, "lazyVbgD"))["final"] - snap_end(g(s, "lazyV1"))["final"] for s in ss])


def print_ablation(t, x, label):
    print(f"\n   --- {t}, {label} (n = {len(x['ss'])} seed)")
    print(f"   lazyV1 − lazy, rerank trên dòng: {cis(x['a'], 2)}")
    print(f"   payload lazyVbgD / lazyVbgD_adp: TB {np.mean(x['b1']) if x['b1'] else float('nan'):.3f} (theo seed "
          f"{[round(v, 2) for v in x['b1']]}); lazyVbgD − lazyVbgD_adp, final trên dòng: {cis(x['b2'], 2)}")
    print(f"   lazyVbgD − lazyVbg, final giữ riêng: {cis(x['c'], 2)}")
    print(f"   lazyVbgD − lazyV1, final giữ riêng: {cis(x['d'], 2)}")


def h11():
    head(f"H11. Ablation C3 trên code100kfq, itq_q+cap16, Zipf 1, seed {SEEDS_B} (KTC 95% theo t, ghép cặp)")
    for t in TAGS:
        x = ablation(t)
        ss, a, b1, b2, c, d = x["ss"], x["a"], x["b1"], x["b2"], x["c"], x["d"]
        ran = bool(ss) or t not in NEWTAGS          # KHÔNG CHẠY chỉ dành cho model mới chưa nhúng được
        full = len(ss) == len(SEEDS_B)
        print_ablation(t, x, "Zipf 1" + ("" if full else ", THIẾU SEED"))
        verdict(f"H11a {t}", full and ci(a)[1] > 0, f"cận dưới KTC {ci(a)[1]:+.2f} (cần > 0)", ran)
        verdict(f"H11b {t}", full and np.mean(b1) <= 0.5 and ci(b2)[1] > 0,
                f"payload {np.mean(b1) if b1 else float('nan'):.3f} (cần <= 0,5), cận dưới KTC final trên dòng "
                f"{ci(b2)[1]:+.2f} (cần > 0)", ran)
        verdict(f"H11c {t}", full and ci(c)[1] > 0, f"cận dưới KTC {ci(c)[1]:+.2f} (cần > 0)", ran)
        verdict(f"H11d {t}", full and ci(d)[1] > 0, f"cận dưới KTC {ci(d)[1]:+.2f} (cần > 0)", ran)
    print()


# ----------------------------------------------------------------- H12, H16e
def fin_cell(ds, t, T, F):
    """Hiệu ghép cặp ở một ô migrate tới khi xong."""
    key = lambda p: f"z1|PROB|{p}|T{T}"
    ss = [s for s in sorted(F) if all(key(p) in F[s]["runs"] for p in ("lazyVbgD", "lazyVbgDinf", "lazybg"))]
    g = lambda s, p: F[s]["runs"][key(p)]
    out = dict(n=len(ss))
    for b in ("lazyVbgDinf", "lazybg"):
        out[f"area_{b}"] = [area(g(s, "lazyVbgD")["snapshots"], T) - area(g(s, b)["snapshots"], T) for s in ss]
        out[f"rr_{b}"] = [win_mean(g(s, "lazyVbgD"), T, "rr") - win_mean(g(s, b), T, "rr") for s in ss]
    out["bytes_inf"] = [g(s, "lazyVbgD")["totals"]["bytes_peak_m0"] - g(s, "lazyVbgDinf")["totals"]["bytes_peak_m0"]
                        for s in ss]
    return out


def h12(tags, label, parts):
    for ds in ("code", "scifact"):
        for t in tags:
            F = files_f(ds, t)
            for T in ts_of(F, ds):
                c = fin_cell(ds, t, T, F)
                ran, full = c["n"] > 0 or t not in NEWTAGS, c["n"] == len(SEEDS_C)
                cell = f"{ds} {t} T={T}"
                print(f"   {cell:26s} n={c['n']:2d}  D−Dinf diện tích {cis(c['area_lazyVbgDinf'], 2):22s} rerank "
                      f"{cis(c['rr_lazyVbgDinf'], 2):22s} byte đỉnh {cis(c['bytes_inf'], 0):18s} | D−lazybg diện tích "
                      f"{cis(c['area_lazybg'], 2):22s} rerank {cis(c['rr_lazybg'], 2)}")
                if "a" in parts:
                    lo1, lo2 = ci(c["area_lazyVbgDinf"])[1], ci(c["rr_lazyVbgDinf"])[1]
                    verdict(f"{label}a {cell}", full and lo1 > -1 and lo2 > -1,
                            f"cận dưới KTC diện tích {lo1:+.2f}, rerank {lo2:+.2f} (cần > −1)", ran)
                if "b" in parts:
                    hi = ci(c["bytes_inf"])[2]
                    verdict(f"{label}b {cell}", full and hi < 0, f"cận trên KTC byte đỉnh {hi:+.1f} (cần < 0)", ran)
                if "c" in parts:
                    lo1, lo2 = ci(c["area_lazybg"])[1], ci(c["rr_lazybg"])[1]
                    verdict(f"{label}{'c' if label == 'H12' else ''} {cell}", full and lo1 > 0 and lo2 > 0,
                            f"cận dưới KTC diện tích {lo1:+.2f}, rerank {lo2:+.2f} (cần > 0)", ran)


# ----------------------------------------------------------------- H13, H15
def c2_cell(ds, sp):
    rows = []
    for s in SEEDS_A:
        d = jl(f"probeP11_{ds}_{sp}_s{s}.json")
        if d:
            rows.append(dict(seed=s, a=at_ref(d, "itq_q+cap16", "srp_c+cap16", "srp_c+cap16"),
                             b=at_ref(d, "itq_q+cap16", "itq_q", "itq_q")))
    return rows


def c2_verdicts(label, cells):
    for ds, sp in cells:
        rows = c2_cell(ds, sp)
        ran, full = bool(rows) or sp not in NEWTAGS, len(rows) == len(SEEDS_A)
        a = [r["a"] for r in rows]; b = [r["b"] for r in rows]
        ma = float(np.mean(a)) if a else float("nan"); mb = float(np.mean(b)) if b else float("nan")
        print(f"   {ds:10s} {sp:8s} n={len(rows)}  itq_q+cap16 − srp_c+cap16 tại ứng viên của srp_c+cap16: {ma:+6.2f} "
              f"(theo seed {[round(x, 1) for x in a]});  itq_q+cap16 − itq_q tại ứng viên của itq_q: {mb:+6.2f}")
        verdict(f"{label}a {ds} {sp}", full and ma >= 5, f"Δ = {ma:+.2f} (cần >= +5)", ran)
        verdict(f"{label}b {ds} {sp}", full and mb >= -1, f"Δ = {mb:+.2f} (cần >= −1)", ran)


def h13():
    head(f"H13. Cơ chế C2 trên code100kfq, seed {SEEDS_A}: hiệu final tại cùng số ứng viên (biên Pareto, nội suy log)")
    c2_verdicts("H13", [("code100kfq", sp) for sp in SPACES])
    print()


def h15_cells():
    return [(ds, sp) for ds in ("code", "scifact") for sp in SPACES + NEWTAGS] + [("code100kfq", t) for t in NEW_ON_100K]


def h15():
    head(f"H15. C2 trên corpus và model khác, seed {SEEDS_A} (ô có model mới: {NEWTAGS})")
    c2_verdicts("H15", h15_cells())
    print()


# ----------------------------------------------------------------- H14 (và E7)
def aniso_rows():
    rows = []
    for ds in ("code100kfq", "code", "scifact"):
        for sp in SPACES + NEWTAGS:
            A = [d["ext"] for s in SEEDS_A for d in [jl(f"probeA11_{ds}_{sp}_s{s}.json")] if d]
            P = [d["variants"]["srp"]["results"]["5"]["storage"] for s in SEEDS_A
                 for d in [jl(f"probeP11_{ds}_{sp}_s{s}.json")] if d and "srp" in d["variants"]]
            if not A or not P:
                continue
            m = lambda k: float(np.mean([e[k] for e in A]))
            rows.append(dict(ds=ds, sp=sp, new=sp in NEWTAGS, p=m("coll_pred_exact_u"), q=m("coll_meas_u"),
                             mf=m("coll_pred_meanfield"), qp=m("qfrac_pred_u"), qm=m("qfrac_meas_u"),
                             t=100 * float(np.mean([s_["top1pct_share"] for s_ in P])), nA=len(A), nP=len(P)))
    return rows


def h14():
    head(f"H14. Mô hình dị hướng, TB seed {SEEDS_A}; p, q: trùng bucket 16 bit giữa hai document (dự đoán góc, đo); qf: phần "
         "corpus cùng bucket với query (dự đoán, đo); t: phần tải của 1% peer với srp ở L=5")
    rows = aniso_rows()
    print(f"{'dataset':11s} {'không gian':10s} {'p':>9s} {'q':>9s} {'|log p/q|':>9s} {'TT':>9s} {'|log TT/q|':>10s} "
          f"{'qf dự đoán':>10s} {'qf đo':>9s} {'|log|':>6s} {'t':>7s}  n  mới")
    for r in rows:
        print(f"{r['ds']:11s} {r['sp']:10s} {r['p']:9.2e} {r['q']:9.2e} {abs(math.log10(r['p'] / r['q'])):9.2f} "
              f"{r['mf']:9.2e} {abs(math.log10(r['mf'] / r['q'])):10.2f} {r['qp']:10.2e} {r['qm']:9.2e} "
              f"{abs(math.log10(r['qp'] / r['qm'])):6.2f} {r['t']:6.1f}% {r['nA']}/{r['nP']} {'x' if r['new'] else ''}")
    new = [r for r in rows if r["new"]]
    old = [r for r in rows if not r["new"]]
    # cặp mới theo đăng ký trước: mỗi model mới trên các corpus nó được nhúng (run_round11.sh đặt EMB_<tag>)
    exp_new = [(ds, t) for t in NEWTAGS for ds in envl("EMB_" + t, "code100kfq code scifact" if t == "minilm"
                                                        else "code scifact")]
    have_ = {(r["ds"], r["sp"]) for r in rows}
    miss_models = sorted({t for ds, t in exp_new if (ds, t) not in have_})
    ran = not miss_models                      # thiếu cặp của model mới nào thì cả ba tiêu chí gộp là KHÔNG CHẠY
    n_old_exp = 3 * len(SPACES)
    e_a = float(np.mean([abs(math.log10(r["p"] / r["q"])) for r in new])) if new else float("nan")
    e_c = float(np.mean([abs(math.log10(r["qp"] / r["qm"])) for r in new])) if new else float("nan")
    rho = spearman([r["p"] for r in rows], [r["t"] for r in rows])
    rho_mf = spearman([r["mf"] for r in rows], [r["t"] for r in rows])
    print(f"   Spearman(p, t) trên {len(rows)} cặp = {rho:+.3f} (trường trung bình: {rho_mf:+.3f}); "
          f"sai số log10 TB trên mọi cặp: p/q {np.mean([abs(math.log10(r['p'] / r['q'])) for r in rows]) if rows else float('nan'):.3f}, "
          f"qf {np.mean([abs(math.log10(r['qp'] / r['qm'])) for r in rows]) if rows else float('nan'):.3f}")
    note = "" if ran else f" (thiếu cặp của model {miss_models}; số trên chỉ là thăm dò)"
    verdict("H14a", ran and e_a <= 0.2, f"sai số log10 TB {e_a:.3f} trên {len(new)}/{len(exp_new)} cặp mới (cần <= 0,2){note}",
            ran)
    verdict("H14b", ran and len(old) == n_old_exp and rho >= 0.8,
            f"Spearman {rho:+.3f} trên {len(rows)} cặp (cần >= 0,8, đủ {n_old_exp} cặp cũ và {len(exp_new)} cặp mới; "
            f"có {len(old)} cặp cũ){note}", ran)
    verdict("H14c", ran and e_c <= 0.2, f"sai số log10 TB {e_c:.3f} trên {len(new)}/{len(exp_new)} cặp mới (cần <= 0,2){note}",
            ran)
    print()


# ----------------------------------------------------------------- H16a-d
def h16():
    head(f"H16. C3 trên model mới. a-d: H10a-d cho {NEW_ON_100K} trên code100kfq, itq_q+cap16, Zipf 1, seed {SEEDS_B}; "
         "e: H12c cho model mới")
    for t in NEW_ON_100K:
        R = runs_b(t)
        ss = [s for s in sorted(R) if all(f"z1|PROB|{p}" in R[s] for p in ("static", "lazy", "lazyVbgD"))]
        ran, full = bool(ss), len(ss) == len(SEEDS_B)
        g = lambda s, p: R[s][f"z1|PROB|{p}"]
        da = [snap_end(g(s, "lazyVbgD"))["final"] - snap_end(g(s, "lazy"))["final"] for s in ss]
        db = [snap_end(g(s, "lazyVbgD"))["final"] - snap_end(g(s, "static"))["final"] for s in ss]
        dc = [g(s, "lazy")["totals"]["rr"] - g(s, "static")["totals"]["rr"] for s in ss]
        dual = [g(s, "lazyVbgD")["totals"]["dual_end"] for s in ss]
        fr = [g(s, "lazyVbgD")["totals"]["fetch"] / max(1e-9, g(s, "lazy")["totals"]["fetch"]) for s in ss]
        print(f"\n   --- {t} (n = {len(ss)} seed)")
        print(f"   lazyVbgD − lazy, final giữ riêng: {cis(da, 2)}; lazyVbgD − static: {cis(db, 2)}; lazy − static, rerank "
              f"trên dòng: {cis(dc, 2)}; dual cuối {np.mean(dual) if dual else float('nan'):.1f}%; payload lazyVbgD / lazy "
              f"{np.mean(fr) if fr else float('nan'):.3f}")
        verdict(f"H16a {t}", full and ci(da)[1] > 0, f"cận dưới KTC {ci(da)[1]:+.2f} (cần > 0)", ran)
        verdict(f"H16b {t}", full and ci(db)[0] >= 3, f"TB {ci(db)[0]:+.2f} (cần >= +3)", ran)
        verdict(f"H16c {t}", full and ci(dc)[2] < 0, f"cận trên KTC {ci(dc)[2]:+.2f} (cần < 0)", ran)
        verdict(f"H16d {t}", full and np.mean(dual) <= 40 and np.mean(fr) <= 1 / 3,
                f"dual {np.mean(dual) if dual else float('nan'):.1f}% (cần <= 40), payload "
                f"{np.mean(fr) if fr else float('nan'):.3f} (cần <= 0,333)", ran)
    print(f"\n   --- H16e (như H12c), seed {SEEDS_C}")
    h12(NEWTAGS, "H16e", "c")
    print()


# ----------------------------------------------------------------- H17
def g_ratio(F, z="1"):
    out = {}
    for s, d in F.items():
        r = d["runs"]
        kd, kl = f"z{z}|PROB|lazyVbgD", f"z{z}|PROB|lazy"
        if kd in r and kl in r:
            out[s] = r[kd]["totals"]["fetch"] / max(1e-9, r[kl]["totals"]["fetch"])
    return out


def h17():
    head(f"H17. Payload lazyVbgD / lazy theo độ dài dòng, itq_q+cap16, Zipf 1, seed {SEEDS_G}")
    for ds in ("code", "scifact"):
        lo_, hi_ = min(GL[ds]), max(GL[ds])
        for t in TAGS:
            rs, rl = g_ratio(files_g(ds, t, lo_)), g_ratio(files_g(ds, t, hi_))
            ss = sorted(set(rs) & set(rl))
            ran, full = bool(rl) or t not in NEWTAGS, len(ss) == len(SEEDS_G) and len(rl) == len(SEEDS_G)
            dl = [rl[s] - rs[s] for s in ss]
            ml = float(np.mean(list(rl.values()))) if rl else float("nan")
            print(f"   {ds:8s} {t:8s} dòng {lo_}: {np.mean(list(rs.values())) if rs else float('nan'):.3f}  dòng {hi_}: {ml:.3f}  "
                  f"hiệu ghép cặp {cis(dl, 3)}  (theo seed, dòng dài: {[round(rl[s], 3) for s in sorted(rl)]})")
            verdict(f"H17a {ds} {t}", full and ml <= 1 / 3, f"tỉ lệ ở dòng {hi_} lượt {ml:.3f} (cần <= 0,333)", ran)
            verdict(f"H17b {ds} {t}", full and ci(dl)[2] < 0, f"cận trên KTC hiệu {ci(dl)[2]:+.3f} (cần < 0)", ran)
    print()


# ----------------------------------------------------------------- E1: chi phí
COLS_B = ["static", "lazy", "lazyV1", "lazyV1_adp", "lazyVbg", "lazyVbgD", "lazyVbgD_adp", "lazyD", "bg", "full"]


def e1_b():
    head("THĂM DÒ E1. Chi phí mỗi truy vấn và lưu trữ, ablation C3 trên code100kfq (pha B và N). Cột: final và rerank trên "
         "dòng, final và rerank giữ riêng cuối dòng, payload, nhúng lại do truy vấn và do nền, peer hỏi, record peer phải "
         "chấm, object dual trả từ phía E0, dual cuối, lưu trữ đỉnh/TB theo record, byte đỉnh/TB (metadata 0), byte đỉnh "
         "(metadata 64), số xác nhận, số retire")
    for t in TAGS + NEW_ON_100K:
        R = runs_b(t)
        if not R:
            continue
        for z in ("1", "0"):
            print(f"\n--- {t}, Zipf {z}, n = {len(R)} seed")
            print(f"{'chính sách':13s} {'d.final':>7s} {'d.rr':>6s} {'g.final':>7s} {'g.rr':>6s} {'tải/q':>6s} {'nhúng q':>7s} "
                  f"{'nhúng nền':>9s} {'peer/q':>6s} {'chấm/q':>7s} {'dualE0':>6s} {'dual%':>6s} {'lưu đỉnh':>8s} {'lưu TB':>6s} "
                  f"{'B đỉnh':>6s} {'B TB':>6s} {'B64 đỉnh':>8s} {'xác nhận':>8s} {'retire':>7s}")
            for p in COLS_B:
                xs = [R[s][f"z{z}|PROB|{p}"] for s in R if f"z{z}|PROB|{p}" in R[s]]
                if not xs:
                    continue
                T_ = lambda k, w=6, pr=1: ms([x["totals"].get(k) for x in xs], w, pr)
                H_ = lambda k: ms([snap_end(x).get(k) for x in xs], 7)
                print(f"{p:13s} {T_('final', 7)} {T_('rr')} {H_('final')} {ms([snap_end(x).get('rr') for x in xs])} "
                      f"{T_('fetch', 6, 2)} {T_('emb_q', 7, 2)} {T_('emb_bg', 9, 2)} {T_('nodes', 6, 0)} {T_('scan', 7, 0)} "
                      f"{T_('dual_from_e0', 6, 1)} {T_('dual_end')} {T_('store_peak', 8)} {T_('store_mean')} "
                      f"{T_('bytes_peak_m0', 6, 0)} {T_('bytes_mean_m0', 6, 0)} {T_('bytes_peak_m64', 8, 0)} "
                      f"{T_('conf_total', 8, 0)} {T_('retired_total', 7, 0)}")
    print()


FPOL = ["bg", "lazybg", "rebuild", "lazyVbg", "lazyVbgD", "lazyVbgD_adp", "lazyVbgDk2", "lazyVbgDk3", "lazyVbgDinf"]


def ret_before(d, p, r):
    """Phần object ngoài S đã mất bản E0 trước lượt xong (retire ngay, retire sau xác nhận, hay do trần), tính bằng
    1 − (số bản E0 còn lại bị gỡ khi xong) / (N − |S|). rebuild giữ index cũ tới lúc chuyển nên là 0."""
    if p == "rebuild":
        return 0.0
    if r["totals"].get("t_done", -1) < 0:
        return float("nan")
    return 100 * (1 - r["totals"]["e0_dropped"] / max(1, d["N"] - d["n_sample"]))


def e1_c():
    head("THĂM DÒ E1 (tiếp). Migrate tới khi xong (pha C và N), itq_q+cap16, Zipf 1. diện tích = TB final giữ riêng trên [0, T]; "
         "rr, tải, nhúng (do truy vấn, do nền, kể cả bản rebuild dựng ở nền), peer = TB trên các cửa sổ trong [0, T); lưu trữ "
         "và byte tính trên cả dòng; retire trước = phần object ngoài S đã gỡ bản E0 trước lượt xong, kể cả retire ngay; "
         "gỡ khi xong = số bản E0 gỡ một lần lúc xong; Δ = hiệu ghép cặp với lazyVbgD")
    for ds in ("code", "scifact"):
        for t in TAGS + NEWTAGS:
            F = files_f(ds, t)
            if not F:
                continue
            d0 = F[min(F)]
            print(f"\n--- {ds} {t}, n = {len(F)} seed, dòng {d0['argv']['stream']} lượt, N = {d0['N']}")
            for T in ts_of(F, ds):
                print(f"   T = {T}")
                print(f"   {'chính sách':13s} {'xong':>6s} {'diện tích':>9s} {'rr':>6s} {'tải/q':>6s} {'nhúng q':>7s} "
                      f"{'nhúng nền':>9s} {'peer/q':>6s} {'lưu đỉnh':>8s} {'lưu TB':>6s} {'B đầu':>6s} {'B đỉnh':>6s} {'B TB':>6s} "
                      f"{'B64 đỉnh':>8s} {'xác nhận':>8s} {'retire trước':>12s} {'gỡ khi xong':>11s} {'Δ diện tích':>16s} "
                      f"{'Δ rr':>16s}")
                ref = {s: F[s]["runs"].get(f"z1|PROB|lazyVbgD|T{T}") for s in F}
                for p in ["static", "lazy", "full"] + FPOL:
                    key = f"z1|PROB|{p}|T{T}" if p in FPOL else f"z1|PROB|{p}"
                    xs = {s: F[s]["runs"][key] for s in F if key in F[s]["runs"]}
                    if not xs:
                        continue
                    v = list(xs.values())
                    tot = lambda k: [x["totals"].get(k, float("nan")) for x in v]
                    ret = [ret_before(F[s], p, xs[s]) if p in FPOL else float("nan") for s in xs]
                    rs_ = (ms(ret, 11) + "%") if p in FPOL else " " * 9 + "n/a"
                    da = [area(xs[s]["snapshots"], T) - area(ref[s]["snapshots"], T) for s in xs if ref.get(s)]
                    dr = [win_mean(xs[s], T, "rr") - win_mean(ref[s], T, "rr") for s in xs if ref.get(s)]
                    tdn = [x if x >= 0 else float("nan") for x in tot("t_done")]
                    print(f"   {p:13s} {ms(tdn, 6, 0)} {ms([area(x['snapshots'], T) for x in v], 9)} "
                          f"{ms([win_mean(x, T, 'rr') for x in v])} {ms([win_mean(x, T, 'fetch') for x in v], 6, 2)} "
                          f"{ms([win_mean(x, T, 'emb_q') for x in v], 7, 2)} {ms([win_mean(x, T, 'emb_bg') for x in v], 9, 2)} "
                          f"{ms([win_mean(x, T, 'nodes') for x in v], 6, 0)} "
                          f"{ms(tot('store_peak'), 8)} {ms(tot('store_mean'))} {ms(tot('bytes_t0_m0'), 6, 0)} "
                          f"{ms(tot('bytes_peak_m0'), 6, 0)} {ms(tot('bytes_mean_m0'), 6, 0)} {ms(tot('bytes_peak_m64'), 8, 0)} "
                          f"{ms(tot('conf_total'), 8, 0)} {rs_:>12s} {ms(tot('e0_dropped'), 11, 0)} "
                          f"{cis(da, 2) if p != 'lazyVbgD' else '':>16s} {cis(dr, 2) if p != 'lazyVbgD' else '':>16s}")
    print()


# ----------------------------------------------------------------- E2: payload theo số lần lặp
def cls_sum(r, t_from=0):
    """Tổng [số lượt, payload, final, rerank] theo lớp lần xuất hiện, trên các cửa sổ bắt đầu từ lượt t_from."""
    out = {c: np.zeros(4) for c in CLS}
    prev = 0
    for w in r["totals"].get("rep_win", []):
        if prev >= t_from:
            for c in CLS:
                out[c] += np.asarray(w[c], dtype=float)
        prev = w["t_end"]
    return out


def pay_by_class(xs, t_from=0):
    """Payload mỗi lượt theo lớp, gộp qua seed."""
    tot = {c: np.zeros(4) for c in CLS}
    for x in xs:
        cs = cls_sum(x, t_from)
        for c in CLS:
            tot[c] += cs[c]
    return {c: (tot[c][1] / tot[c][0] if tot[c][0] > 0 else float("nan"), int(tot[c][0])) for c in CLS}


def rep_pair(xs, t_from=0):
    """(lần đầu, lặp lại) payload mỗi lượt, gộp qua seed."""
    tot = {c: np.zeros(4) for c in CLS}
    for x in xs:
        cs = cls_sum(x, t_from)
        for c in CLS:
            tot[c] += cs[c]
    rep = tot["k2"] + tot["k3"] + tot["k6"]
    f1 = tot["k1"][1] / tot["k1"][0] if tot["k1"][0] > 0 else float("nan")
    fr = rep[1] / rep[0] if rep[0] > 0 else float("nan")
    return f1, fr, int(tot["k1"][0]), int(rep[0])


def cum_ratio(xd, xl, upto):
    """Tỉ lệ payload cộng dồn lazyVbgD / lazy tới lượt upto (từ cửa sổ), gộp qua seed."""
    nd = sum(w["fetch"] * (w["t_end"] - p) for x in xd for p, w in zip([0] + [v["t_end"] for v in x["windows"]], x["windows"])
             if w["t_end"] <= upto)
    nl = sum(w["fetch"] * (w["t_end"] - p) for x in xl for p, w in zip([0] + [v["t_end"] for v in x["windows"]], x["windows"])
             if w["t_end"] <= upto)
    return nd / nl if nl > 0 else float("nan")


def e2():
    head("THĂM DÒ E2. Payload theo số lần một query đã xuất hiện trên dòng (k). Gộp mọi seed. 'nửa sau' = chỉ các cửa sổ ở "
         "nửa sau dòng, để so lần đầu với lặp lại trong cùng khoảng thời gian")
    ref = {}                                                   # payload theo lớp trên code100kfq Zipf 1, dùng để dự đoán

    def block(name, runs_by_seed, z, stream):
        get = lambda p: [R[f"z{z}|PROB|{p}"] for R in runs_by_seed.values() if f"z{z}|PROB|{p}" in R]
        xl, xd = get("lazy"), get("lazyVbgD")
        if not xl or not xd:
            return None
        print(f"\n--- {name}, Zipf {z}, dòng {stream} lượt, n = {len(xl)} seed")
        for p in ("lazy", "lazyV1", "lazyV1_adp", "lazyVbgD", "lazyVbgD_adp"):
            xs = get(p)
            if not xs:
                continue
            pc = pay_by_class(xs)
            f1, fr, n1, nr = rep_pair(xs, stream // 2)
            print(f"   {p:13s} payload/lượt theo lớp: " + "  ".join(f"{CLSN[c]} {pc[c][0]:6.2f} (n {pc[c][1]:6d})" for c in CLS)
                  + f"   | nửa sau: lần 1 {f1:6.2f} (n {n1}), lặp lại {fr:6.2f} (n {nr})")
        pl, pd = pay_by_class(xl), pay_by_class(xd)
        print("   tỉ lệ lazyVbgD / lazy theo lớp: " + "  ".join(f"{CLSN[c]} {pd[c][0] / pl[c][0] if pl[c][0] else float('nan'):.3f}"
                                                         for c in CLS))
        a1, ar, _, _ = rep_pair(xd, stream // 2); b1, br, _, _ = rep_pair(xl, stream // 2)
        print(f"   nửa sau, tỉ lệ lazyVbgD / lazy: lần 1 {a1 / b1 if b1 else float('nan'):.3f}, lặp lại {ar / br if br else float('nan'):.3f}")
        marks = [m for m in (150, 300, 600, 1000, 1500, 2000, 3000) if m <= stream]
        print("   tỉ lệ payload cộng dồn: " + "  ".join(f"t{m}: {cum_ratio(xd, xl, m):.3f}" for m in marks))
        return pl, pd

    for t in TAGS + NEW_ON_100K:
        R = runs_b(t)
        if not R:
            continue
        for z in ("1", "0"):
            out = block(f"code100kfq {t} (pha B)", R, z, stream_b(t))
            if out and z == "1":
                ref[t] = out
    for ds in ("code", "scifact"):
        for t in TAGS:
            for ln in GL[ds]:
                Fg = files_g(ds, t, ln)
                if not Fg:
                    continue
                Rg = {s: d["runs"] for s, d in Fg.items()}
                for z in ("1", "0"):
                    block(f"{ds} {t} (pha G)", Rg, z, ln)
                # dự đoán tỉ lệ cả dòng từ payload theo lớp của code100kfq (Zipf 1) và cơ cấu lớp của dòng này
                if t in ref:
                    pl, pd = ref[t]
                    pr, ob = [], []
                    for s, R_ in Rg.items():
                        if "z1|PROB|lazy" not in R_ or "z1|PROB|lazyVbgD" not in R_:
                            continue
                        cs = cls_sum(R_["z1|PROB|lazy"])
                        num = sum(cs[c][0] * pd[c][0] for c in CLS if pd[c][0] == pd[c][0])
                        den = sum(cs[c][0] * pl[c][0] for c in CLS if pl[c][0] == pl[c][0])
                        pr.append(num / den if den else float("nan"))
                        ob.append(R_["z1|PROB|lazyVbgD"]["totals"]["fetch"] / max(1e-9, R_["z1|PROB|lazy"]["totals"]["fetch"]))
                    if pr:
                        print(f"   {ds} {t} dòng {ln}: tỉ lệ dự đoán từ code100kfq {np.mean(pr):.3f}, đo {np.mean(ob):.3f}")
    for ds in ("code", "scifact"):
        for t in TAGS + NEWTAGS:
            F = files_f(ds, t)
            if not F:
                continue
            for T in ts_of(F, ds):
                xl = [d["runs"]["z1|PROB|lazy"] for d in F.values() if "z1|PROB|lazy" in d["runs"]]
                xd = [d["runs"][f"z1|PROB|lazyVbgD|T{T}"] for d in F.values() if f"z1|PROB|lazyVbgD|T{T}" in d["runs"]]
                if xl and xd:
                    pl, pd = pay_by_class(xl), pay_by_class(xd)
                    print(f"   migrate tới khi xong {ds} {t} T={T}: tỉ lệ lazyVbgD / lazy theo lớp "
                          + "  ".join(f"{CLSN[c]} {pd[c][0] / pl[c][0] if pl[c][0] else float('nan'):.3f}" for c in CLS)
                          + f"; cộng dồn tới T: {cum_ratio(xd, xl, T):.3f}")
    print()


# ----------------------------------------------------------------- E3, E4: negative flip, mất đường tìm
def nfr(xs, ref, t, key):
    """Phần query giữ riêng có số object đúng thấp hơn ref ở checkpoint t, gộp qua seed."""
    worse, n = 0, 0
    for s in xs:
        if s in ref and str(t) in xs[s]["snapshots"] and str(t) in ref[s]["snapshots"]:
            a, b = hits(xs[s]["snapshots"][str(t)][key]), hits(ref[s]["snapshots"][str(t)][key])
            worse += int((a < b).sum()); n += len(a)
    return 100 * worse / n if n else float("nan")


def flip_stats(xs, ref, cps):
    """(cuối, TB, lớn nhất) của negative flip qua các checkpoint cps, cho final và rerank."""
    out = {}
    for key in ("fin_hits", "rr_hits"):
        v = [nfr(xs, ref, c, key) for c in cps]
        out[key] = (v[-1] if v else float("nan"), float(np.nanmean(v)) if v else float("nan"),
                    float(np.nanmax(v)) if v else float("nan"))
    return out


def fmt_flip(f):
    return (f"final {f['fin_hits'][0]:5.1f} / {f['fin_hits'][1]:5.1f} / {f['fin_hits'][2]:5.1f}  rerank "
            f"{f['rr_hits'][0]:5.1f} / {f['rr_hits'][1]:5.1f} / {f['rr_hits'][2]:5.1f}")


def e3_e4():
    head("THĂM DÒ E3, E4. Negative flip: % query giữ riêng có ít object đúng trong top-5 hơn static (hoặc full) ở cùng "
         "checkpoint, ghi 'cuối / TB / lớn nhất' qua các checkpoint t > 0 (với migrate tới khi xong: t trong (0, T]). Mất đường "
         "vì retire (lost_retire) và còn đường tìm (reach_any), % vị trí top-5 thật")
    for t in TAGS + NEW_ON_100K:
        R = runs_b(t)
        if not R:
            continue
        for z in ("1",):
            g = lambda p: {s: R[s][f"z{z}|PROB|{p}"] for s in R if f"z{z}|PROB|{p}" in R[s]}
            st, fu = g("static"), g("full")
            if not st:
                continue
            cps = sorted(int(k) for k in next(iter(st.values()))["snapshots"] if int(k) > 0)
            print(f"\n--- code100kfq {t}, Zipf {z}, checkpoint {cps}")
            for p in COLS_B:
                xs = g(p)
                if not xs:
                    continue
                print(f"   {p:13s} so với static: {fmt_flip(flip_stats(xs, st, cps))}   so với full: "
                      f"{fmt_flip(flip_stats(xs, fu, cps))}   lost_retire cuối "
                      f"{ms([snap_end(x).get('lost_retire') for x in xs.values()], 5, 2)}%  reach_any cuối "
                      f"{ms([snap_end(x).get('reach_any') for x in xs.values()], 5, 1)}%")
    for ds in ("code", "scifact"):
        for t in TAGS + NEWTAGS:
            F = files_f(ds, t)
            if not F:
                continue
            st = {s: d["runs"]["z1|PROB|static"] for s, d in F.items() if "z1|PROB|static" in d["runs"]}
            fu = {s: d["runs"]["z1|PROB|full"] for s, d in F.items() if "z1|PROB|full" in d["runs"]}
            for T in ts_of(F, ds):
                print(f"\n--- migrate tới khi xong {ds} {t} T={T}: lost_retire TB và lớn nhất, reach_any thấp nhất, qua "
                      "checkpoint trong (0, T]")
                for p in ["lazy"] + FPOL:
                    key = f"z1|PROB|{p}|T{T}" if p in FPOL else f"z1|PROB|{p}"
                    xs = {s: d["runs"][key] for s, d in F.items() if key in d["runs"]}
                    if not xs:
                        continue
                    cps = sorted(int(c) for c in next(iter(xs.values()))["snapshots"] if 0 < int(c) <= T)
                    lr = [np.mean([xs[s]["snapshots"][str(c)].get("lost_retire", float("nan")) for s in xs]) for c in cps]
                    ra = [np.mean([xs[s]["snapshots"][str(c)].get("reach_any", float("nan")) for s in xs]) for c in cps]
                    print(f"   {p:13s} so với static: {fmt_flip(flip_stats(xs, st, cps))}   so với full: "
                          f"{fmt_flip(flip_stats(xs, fu, cps))}   lost_retire {np.nanmean(lr):5.2f}% / {np.nanmax(lr):5.2f}%  "
                          f"reach_any thấp nhất {np.nanmin(ra):5.1f}%")
    print()


# ----------------------------------------------------------------- E5: ngưỡng xác nhận
def e5():
    head("THĂM DÒ E5. Ngưỡng xác nhận k = 1 (lazyVbgD), 2, 3, không bao giờ (inf); Δ so với k = 1, ghép cặp")
    for ds in ("code", "scifact"):
        for t in TAGS + NEWTAGS:
            F = files_f(ds, t)
            if not F:
                continue
            for T in ts_of(F, ds):
                g = lambda p: {s: d["runs"][f"z1|PROB|{p}|T{T}"] for s, d in F.items() if f"z1|PROB|{p}|T{T}" in d["runs"]}
                k1 = g("lazyVbgD")
                if not k1:
                    continue
                print(f"\n--- {ds} {t} T={T}")
                for p in ("lazyVbgD", "lazyVbgDk2", "lazyVbgDk3", "lazyVbgDinf"):
                    xs = g(p)
                    if not xs:
                        continue
                    da = [area(xs[s]["snapshots"], T) - area(k1[s]["snapshots"], T) for s in xs if s in k1]
                    dr = [win_mean(xs[s], T, "rr") - win_mean(k1[s], T, "rr") for s in xs if s in k1]
                    db = [xs[s]["totals"]["bytes_peak_m0"] - k1[s]["totals"]["bytes_peak_m0"] for s in xs if s in k1]
                    dm = [xs[s]["totals"]["bytes_mean_m0"] - k1[s]["totals"]["bytes_mean_m0"] for s in xs if s in k1]
                    v = list(xs.values())
                    ret = [ret_before(F[s], p, xs[s]) for s in xs]
                    kk = v[0]["totals"].get("confirm_k", 1)
                    print(f"   {p:12s} diện tích {ms([area(x['snapshots'], T) for x in v])} (Δ {cis(da, 2)})  rr "
                          f"{ms([win_mean(x, T, 'rr') for x in v])} (Δ {cis(dr, 2)})  byte đỉnh "
                          f"{ms([x['totals']['bytes_peak_m0'] for x in v], 6, 0)} (Δ {cis(db, 0)})  byte TB "
                          f"{ms([x['totals']['bytes_mean_m0'] for x in v], 6, 0)} (Δ {cis(dm, 0)})  xong lượt "
                          f"{ms([x['totals']['t_done'] for x in v], 6, 0)}  retire trước khi xong {ms(ret, 5)}%  k = "
                          f"{'không bao giờ' if kk >= 10 ** 9 else kk}")
    print()


# ----------------------------------------------------------------- E6: churn
def e6():
    head(f"THĂM DÒ E6. Churn và lỗi peer trên itq_q+cap16, code100kfq, Zipf 1, seed {SEEDS_F}")
    for t in TAGS:
        F = {s: d for s in SEEDS_F for d in [jl(f"probeV11C_code100kfq_{t}_s{s}_cap16.json")] if d}
        if not F:
            continue
        print(f"\n--- {t}, n = {len(F)} seed")
        for cname in ("ch", "fail"):
            for p in ("static", "lazy", "lazyV1", "lazyVbgD", "full"):
                xs = [d["runs"][f"z1|PROB|{p}|{cname}"] for d in F.values() if f"z1|PROB|{p}|{cname}" in d["runs"]]
                if not xs:
                    continue
                T_ = lambda k, w=6, pr=1: ms([x["totals"].get(k) for x in xs], w, pr)
                print(f"   {cname:4s} {p:9s} giữ riêng cuối {ms([snap_end(x)['final'] for x in xs])}  rerank trên dòng {T_('rr')}  "
                      f"mất mọi đường cuối {T_('lost_obj_end', 5, 2)}% (lớn nhất {T_('lost_obj_max', 5, 2)}%)  ghi sửa/q "
                      f"{T_('repair_w', 6, 1)}  keep-alive/q {T_('keepalive', 7, 0)}")
        st0 = [d["runs"]["z1|PROB|static"] for d in F.values() if "z1|PROB|static" in d["runs"]]
        if st0:
            print(f"   không churn static: giữ riêng cuối {ms([snap_end(x)['final'] for x in st0])}")
    print()


# ----------------------------------------------------------------- E8: bậc thang C2
LADDER = ["srp", "srp+cap16", "srp_c", "srp_c+cap16", "pca_q", "pca_q+cap16", "itq_q", "itq_q+cap16"]


def e8():
    head(f"THĂM DÒ E8. Bậc thang cơ chế C2, seed {SEEDS_A}. Δ ứng viên / Δ peer: final so với srp_c+cap16 tại số ứng viên / số "
         "peer của srp_c+cap16 ở (5,8); tải ở L=5 (tổng 5 bảng): tối đa, p99, phần của 1% peer, Gini; truy vấn tới peer nóng "
         "nhất và công việc chấm lớn nhất ở (5,8); dời và vào peer đầy: % record ở 5 bảng đầu")
    for ds in ("code100kfq", "code", "scifact"):
        for sp in SPACES + NEWTAGS:
            D = [d for s in SEEDS_A for d in [jl(f"probeP11_{ds}_{sp}_s{s}.json")] if d]
            if not D:
                continue
            print(f"\n--- {ds} {sp}, n = {len(D)} seed; (5,8) của srp_c+cap16: ứng viên "
                  f"{ms([d['variants']['srp_c+cap16']['results']['5']['8']['cand'] for d in D if 'srp_c+cap16' in d['variants']], 6, 0)}, "
                  f"final {ms([d['variants']['srp_c+cap16']['results']['5']['8']['final_r5'] for d in D if 'srp_c+cap16' in d['variants']])}")
            for v in LADDER:
                Dv = [d for d in D if v in d["variants"]]
                if not Dv:
                    continue
                R5 = lambda d: d["variants"][v]["results"]["5"]
                cap = lambda d, k: 100 * d["variants"][v].get("cap", {}).get(k, 0.0)
                print(f"   {v:12s} Δ ứng viên {ms([at_ref(d, v, 'srp_c+cap16', 'srp_c+cap16') for d in Dv], 6, 2)}  Δ peer "
                      f"{ms([at_ref(d, v, 'srp_c+cap16', 'srp_c+cap16', 'nodes') for d in Dv], 6, 2)}  (5,8): final "
                      f"{ms([R5(d)['8']['final_r5'] for d in Dv])} ứng viên {ms([R5(d)['8']['cand'] for d in Dv], 7, 0)}  tải tối đa "
                      f"{ms([R5(d)['storage']['max'] for d in Dv], 6, 0)} p99 {ms([R5(d)['storage']['p99'] for d in Dv], 5, 0)} "
                      f"1% peer {ms([100 * R5(d)['storage']['top1pct_share'] for d in Dv], 5)}% Gini "
                      f"{ms([R5(d)['storage']['gini'] for d in Dv], 4, 2)}  truy vấn tới peer nóng nhất "
                      f"{ms([100 * R5(d)['8']['qload']['max_frac'] for d in Dv], 5)}%  công việc lớn nhất "
                      f"{ms([R5(d)['8']['work']['max'] for d in Dv], 8, 0)}  dời {ms([cap(d, 'moved_frac_L5') for d in Dv], 5, 2)}%  "
                      f"vào peer đầy {ms([cap(d, 'fallback_frac_L5') for d in Dv], 5, 2)}%")
    print()


# ----------------------------------------------------------------- E9: model mới
def e9():
    head(f"THĂM DÒ E9. Ablation C3 (các hiệu của H11) cho model mới trên code100kfq {NEW_ON_100K}, và cho mọi model ở workload "
         "đều; không chấm ngưỡng. Các bảng E1 đến E5 ở trên đã gồm model mới")
    for t in NEW_ON_100K:
        x = ablation(t)
        if x["ss"]:
            print_ablation(t, x, "Zipf 1")
    for t in TAGS + NEW_ON_100K:
        x = ablation(t, "0")
        if x["ss"]:
            print_ablation(t, x, "workload đều")
    print()


# ----------------------------------------------------------------- tự kiểm
def checks():
    head("Tự kiểm")

    def show(fn, c, nm):
        print(f"   {fn:58s} {nm}: {c['n']} giá trị, "
              f"{'KHỚP' if c['bad'] == 0 and c['n'] > 0 else str(c['bad']) + ' LỆCH ' + str(c.get('diffs', [])[:3])}")
    fr = sorted(glob.glob("probePR11_*.json")) + sorted(glob.glob("probeVR11*.json"))
    for fn in fr:
        d = jl(fn)
        if d and d.get("check_prev"):
            show(fn, d["check_prev"], "so với đợt 10")
        elif d:
            print(f"   {fn:58s} không có kết quả so với đợt 10")
    if not fr:
        print("   pha R: chưa có file")
    pats = ["probeV11_*_cap16.json", "probeV11F_*_cap16.json", "probeV11G_*_cap16.json", "probeV11C_*_cap16.json"]
    n_ok = n_tot = 0
    for pat in pats:
        for fn in sorted(glob.glob(pat)):
            d = jl(fn)
            if d and d.get("check_10"):
                n_tot += 1
                c = d["check_10"]
                if c["bad"] == 0 and c["n"] > 0:
                    n_ok += 1
                else:
                    show(fn, c, "check_10")
    print(f"   placement itq_q+cap16 trong 11 so với 10 (seed có file của pha A): {n_ok}/{n_tot} file KHỚP")
    bad_mode = n_mode = 0
    for pat in pats:
        for fn in sorted(glob.glob(pat)):
            d = jl(fn)
            if not d:
                continue
            for k, r in d["runs"].items():
                n_mode += 1
                want = "adapter" if k.split("|")[2].endswith("_adp") else d["argv"]["dual_score"]
                bad_mode += r["totals"].get("dual_score") != want
    print(f"   cách chấm object dual đúng theo hậu tố _adp: {n_mode - bad_mode}/{n_mode} run")
    n_emb = bad_emb = n_rb = bad_rb = 0
    for pat in pats:
        for fn in sorted(glob.glob(pat)):
            d = jl(fn)
            if not d:
                continue
            for k, r in d["runs"].items():
                tt = r["totals"]
                if "emb_q" not in tt:
                    continue
                if k.split("|")[2] == "rebuild":       # bản dựng ở nền: tổng đúng bằng N − |S| nếu dựng xong
                    if tt.get("t_done", -1) >= 0:
                        n_rb += 1
                        bad_rb += abs(tt["emb_bg"] * d["argv"]["stream"] - (d["N"] - d["n_sample"])) > 1e-6
                else:
                    n_emb += 1
                    bad_emb += abs(tt["emb_q"] + tt["emb_bg"] - tt["new"]) > 1e-9
    print(f"   nhúng lại do truy vấn + do nền = new: {n_emb - bad_emb}/{n_emb} run; rebuild dựng đủ N − |S| bản ở nền: "
          f"{n_rb - bad_rb}/{n_rb} run")
    n_post = bad_post = n_pre = bad_pre = n_inf = bad_inf = n_k = bad_k = 0
    for fn in sorted(glob.glob("probeV11F_*_cap16.json")) + sorted(glob.glob("probeVR11F_*.json")):
        d = jl(fn)
        if not d:
            continue
        runs = d["runs"]
        fu, stc = runs.get("z1|PROB|full"), runs.get("z1|PROB|static")
        for k, r in runs.items():
            if "|T" not in k or not fu:
                continue
            pol = k.split("|")[2]
            td = r["totals"].get("t_done", -1)
            for c, sv in r["snapshots"].items():
                if td >= 0 and int(c) >= td:
                    n_post += 1
                    bad_post += any(abs(sv[m] - fu["snapshots"][c][m]) > 1e-9 for m in ("final", "rr"))
                elif pol == "rebuild" and stc:
                    n_pre += 1
                    bad_pre += any(abs(sv[m] - stc["snapshots"][c][m]) > 1e-9 for m in ("final", "rr"))
            if pol.startswith("lazyVbgDinf"):
                n_inf += 1
                bad_inf += r["totals"]["retired_total"] != 0
            if pol.startswith("lazyVbgDk"):
                n_k += 1
                bad_k += r["totals"].get("confirm_k") != int(pol[len("lazyVbgDk"):].split("_")[0])
    print(f"   migrate tới khi xong: checkpoint sau lượt xong trùng full {n_post - bad_post}/{n_post}; rebuild trước lượt xong "
          f"trùng static {n_pre - bad_pre}/{n_pre}; lazyVbgDinf không retire trước khi xong {n_inf - bad_inf}/{n_inf}; "
          f"ngưỡng k đúng {n_k - bad_k}/{n_k}")
    cnt = dict(A=len(glob.glob("probeA11_*.json")), P=len(glob.glob("probeP11_*.json")),
               B=len(glob.glob("probeV11_code100kfq_*_cap16.json")), C=len(glob.glob("probeV11F_*_cap16.json")),
               G=len(glob.glob("probeV11G_*_cap16.json")), F=len(glob.glob("probeV11C_*_cap16.json")))
    print(f"   số file: dị hướng {cnt['A']}, placement {cnt['P']}, C3 code100kfq {cnt['B']}, migrate tới khi xong {cnt['C']}, "
          f"độ dài dòng {cnt['G']}, churn {cnt['F']}")
    print()


def main():
    h11()
    head(f"H12. Migrate tới khi xong, itq_q+cap16, Zipf 1, seed {SEEDS_C}: D = lazyVbgD; diện tích [0, T]; rerank [0, T); "
         "byte đỉnh mỗi object (metadata 0)")
    h12(TAGS, "H12", "abc")
    print()
    h13()
    h14()
    h15()
    h16()
    h17()
    head("TÓM TẮT ĐÁNH GIÁ ĐĂNG KÝ TRƯỚC (H11 đến H17)")
    groups = defaultdict(lambda: [0, 0, 0])
    for nm, st, det in VERDICT:
        print(f"   {st:10s} {nm:34s} {det}")
        g = nm.split()[0].rstrip("abcde") if nm.split()[0][:3] != "H16" else "H16"
        groups[g][0] += st == "ĐẠT"; groups[g][1] += st == "KHÔNG ĐẠT"; groups[g][2] += st == "KHÔNG CHẠY"
    for g in sorted(groups, key=lambda x: int(x[1:])):
        a, b, c = groups[g]
        print(f"   {g}: {a} đạt, {b} không đạt" + (f", {c} không chạy" if c else ""))
    n_ok = sum(1 for _, st, _ in VERDICT if st == "ĐẠT")
    n_run = sum(1 for _, st, _ in VERDICT if st != "KHÔNG CHẠY")
    print(f"   Tổng: {n_ok} trên {n_run} tiêu chí đã chạy đạt; {len(VERDICT) - n_run} tiêu chí không chạy; "
          f"tổng số tiêu chí {len(VERDICT)}\n")
    e1_b()
    e1_c()
    e2()
    e3_e4()
    e5()
    e6()
    e8()
    e9()
    checks()


if __name__ == "__main__":
    main()
