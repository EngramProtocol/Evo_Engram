#!/usr/bin/env python3
"""
analyze_r14.py  —  đánh giá đợt 14 theo đúng evo/PREREG_round14.md (H22 đến H24), rồi in phần thăm dò E1 đến E6 và tự
kiểm. Đọc ở thư mục hiện tại (thư mục gốc repo), hoặc ở THƯ_MỤC nếu có tham số:
  probeV14U_code100kfq_<tag>_s<seed>.json                     pha U: dòng 3.000 lượt của code 100k, khoá SRP gốc
  probeV14F_<ds>_<tag>_s<seed>_cap16.json                     pha C: migrate tới khi xong, seed mới
  probeV14_code100kfq_<tag>_s<seed>_cap16.json                pha D: dòng 3.000 lượt, placement học, có drain
  probeV13_code100kfq_bgebase_s<seed>_cap16.json              đợt 13: như pha D, cho bge-base
  probeV14C_code100kfq_<tag>_s<seed>_cap16.json               pha F: churn và lỗi peer có drain
  probeV14B_code100kfq_<tag>_s<seed>_cap16_T<probe>.json      pha B: full ở T = 16
  probeP14_code100kfq_<space>_s<seed>_n<peer>.json            pha O; so với probeP11_code100kfq_*, probeQ13_A11_code100kfq_*
  probeVR14_*.json                                            pha R
Danh sách seed và model lấy từ biến môi trường do run_round14.sh đặt (mặc định đúng như đăng ký trước).
  python3 evo/analyze_r14.py [THƯ_MỤC]
"""
import glob, json, math, os, sys
from collections import defaultdict
import numpy as np

envl = lambda k, d: os.environ.get(k, d).split()
envi = lambda k, d: [int(x) for x in envl(k, d)]
S10 = "26 27 28 29 30 31 32 33 34 35"
SEEDS_U = envi("SEEDS_U", S10)
SEEDS_C = envi("SEEDS_C", "46 47 48 49 50 51 52 53 54 55")
SEEDS_D = envi("SEEDS_D", S10)
SEEDS_F = envi("SEEDS_F", "26 27 28")
SEEDS_B = envi("SEEDS_B", S10)
SEEDS_O = envi("SEEDS_O", "26 27 28")
UTAGS = envl("UTAGS", "bgebase e5large")
CTAGS = envl("CTAGS", "bgebase e5large arctic gtebase minilm")
DTAGS = envl("DTAGS", "e5large arctic minilm")
FTAGS = envl("FTAGS", "bgebase e5large arctic")
BTAGS = envl("BTAGS", "bgebase")
OSPACES = envl("OSPACES", "bgebase e5large arctic m0 minilm")
ONODES = int(os.environ.get("ONODES", "5000"))
BPROBES = int(os.environ.get("BPROBES", "16"))
QF_HI, QF_LO = 8e-4, 2e-4
TCRIT = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
         11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086}
K1, DRAIN = "lazyVbgD", "lazyVbgDinf"
# Bảng 10 của bản thảo, thêm lazy+keep và drain (như analyze_r13.py)
TAB10 = [("static", "static"), ("lazy", "lazy"), ("lazyV1", "lazy+delay"), ("lazyVbg", "dual, bg retired"),
         ("lazyVbgD_adp", "dual, no code"), ("lazyVbgD", "dual (k1)"), ("lazyD", "lazy+keep"),
         ("lazyVbgDinf", "dual (drain)"), ("full", "full")]
BGP = ("bg", "lazybg", "rebuild", K1, DRAIN)                       # chính sách có nền của pha C (tên run có hậu tố |T<T>)
CPOL = [("static", "static"), ("lazy", "lazy"), ("full", "full"), ("bg", "bg"), ("lazybg", "lazy+bg"),
        ("rebuild", "rebuild"), (K1, "k1"), (DRAIN, "drain")]
# khoảng qua 20 ô của đợt 11 (seed 26 đến 35), để đặt cạnh khoảng của đợt 14
R11 = dict(reb_a=(14.5, 26.3), lbg_a=(1.6, 7.9), lbg_r=(6.2, 14.4), st_a=(16.3, 28.9), bg_a=(8.7, 16.0),
           full_a=(-6.6, 5.6), k1_a=(0.3, 4.3), k1_r=(2.8, 6.8), reb_r=(0.5, 19.5))
VERDICT = []
LINE = "=" * 118
NAN = float("nan")
BASE = sys.argv[1] if len(sys.argv) > 1 else "."
_cache = {}


def gl(pat):
    """Tên file (không kèm thư mục) khớp mẫu trong BASE."""
    return sorted(os.path.basename(x) for x in glob.glob(os.path.join(BASE, pat)))


def jl(fn):
    if fn in _cache:
        return _cache[fn]
    d = None
    path = os.path.join(BASE, fn)
    if os.path.exists(path):
        try:
            d = json.load(open(path))
        except Exception as e:
            print(f"*** không đọc được {fn}: {e}")
    _cache[fn] = d
    return d


def head(title):
    print(LINE)
    print(title)
    print(LINE)


def nmean(v):
    v = [x for x in v if x is not None and x == x]
    return float(np.mean(v)) if v else NAN


def ms(v, w=6, p=1):
    v = [x for x in v if x is not None and x == x]
    return f"{np.mean(v):{w}.{p}f}" if v else " " * (w - 3) + "n/a"


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


def cis(v, p=1):
    m, lo, hi, n = ci(v)
    if n == 0:
        return "n/a"
    if n == 1:
        return f"{m:+.{p}f}"
    return f"{m:+.{p}f} [{lo:+.{p}f}, {hi:+.{p}f}]"


def rng(v, p=1):
    v = [x for x in v if x is not None and x == x]
    return f"{min(v):+.{p}f} đến {max(v):+.{p}f}" if v else "n/a"


def verdict(name, ok, detail, ran=True):
    st = "KHÔNG CHẠY" if not ran else ("ĐẠT" if ok else "KHÔNG ĐẠT")
    VERDICT.append((name, st, detail))
    print(f"   {st:10s} {name}: {detail}")


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
    """F_va(c) − F_vb(c) với c là số ứng viên (hoặc số peer) của vref ở (L = 5, T = 8); như analyze_r12.py."""
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


def hits(s):
    return np.asarray([int(c) for c in s], dtype=int) if isinstance(s, str) else np.asarray(s, dtype=int)


def snap_end(r):
    s = r["snapshots"]
    return s[str(max(int(k) for k in s))] if s else {}


def flips(xs, ref, key="rr_hits"):
    """% query giữ riêng có ít object đúng hơn ref ở checkpoint cuối, gộp qua seed."""
    worse = n = 0
    for s in xs:
        if s in ref:
            a, b = hits(snap_end(xs[s]).get(key, "")), hits(snap_end(ref[s]).get(key, ""))
            if len(a) and len(a) == len(b):
                worse += int((a < b).sum()); n += len(a)
    return 100 * worse / n if n else NAN


# ----------------------------------------------------------------- nạp dữ liệu của dòng 3.000 lượt
def usable(d):
    """File có tự kiểm với đợt trước LỆCH thì không dùng để chấm."""
    return bool(d) and not (d.get("check_prev") or {}).get("bad")


def learned(t, seeds):
    """Dòng code 100k với placement học: file pha D của đợt 14 nếu có, không thì file đợt 13. -> {seed: file}."""
    out = {}
    for s in seeds:
        for fn in (f"probeV14_code100kfq_{t}_s{s}_cap16.json", f"probeV13_code100kfq_{t}_s{s}_cap16.json"):
            d = jl(fn)
            if usable(d):
                out[s] = d
                break
    return out


def srp(t):
    return {s: d for s in SEEDS_U for d in [jl(f"probeV14U_code100kfq_{t}_s{s}.json")] if d}


def runs(F, p, suffix=""):
    k = f"z1|PROB|{p}{suffix}"
    return {s: d["runs"][k] for s, d in F.items() if k in d["runs"]}


hf = lambda r: snap_end(r).get("final", NAN)                      # giữ riêng: final của query giữ riêng ở checkpoint cuối
srr = lambda r: r["totals"].get("rr", NAN)                        # rerank trên dòng
lost = lambda r: snap_end(r).get("lost_retire", NAN)              # mất đường ở checkpoint cuối


def pdiff(A, B, f):
    """Hiệu ghép theo seed f(A) − f(B) trên các seed có ở cả hai. -> (seed, hiệu)."""
    ss = [s for s in sorted(A) if s in B]
    return ss, [f(A[s]) - f(B[s]) for s in ss]


def did(La, Lb, Ua, Ub, f):
    """Hiệu của hiệu: (f(La) − f(Lb)) trên placement học trừ (f(Ua) − f(Ub)) trên SRP, ghép theo seed."""
    ss = [s for s in sorted(La) if s in Lb and s in Ua and s in Ub]
    return ss, [(f(La[s]) - f(Lb[s])) - (f(Ua[s]) - f(Ub[s])) for s in ss]


def crit(name, ss, v, thr, nseed, what, p=2):
    """Tiêu chí dạng 'cận dưới KTC lớn hơn thr', chỉ đạt khi đủ nseed seed."""
    lo = ci(v)[1]
    full = len(ss) == nseed
    thr_s = "0" if thr == 0 else f"{thr:+g}".replace("-", "−")
    verdict(name, full and lo > thr, f"{what}: {cis(v, p)}, n = {len(ss)}" + ("" if full else f" (THIẾU SEED, cần {nseed})")
            + f"; cần cận dưới > {thr_s}")
    return full and lo > thr


def stream_table(F, pols=TAB10):
    st = runs(F, "static")
    print(f"   {'chính sách':16s} {'n':>2s} {'giữ riêng':>9s} {'dòng':>6s} {'tải':>5s} {'nhúng q + nền':>13s} {'dual':>5s} "
          f"{'record':>6s} {'byte':>5s} {'(+64)':>6s} {'peer':>6s} {'ứng viên':>8s} {'dual E0/q':>9s} {'mất':>5s} "
          f"{'xấu hơn':>7s} {'nền/lượt':>8s}")
    for p, lab in pols:
        X = runs(F, p)
        if not X:
            continue
        T = lambda k: [x["totals"].get(k, NAN) for x in X.values()]
        E = lambda k: [snap_end(x).get(k, NAN) for x in X.values()]
        print(f"   {lab:16s} {len(X):2d} {ms(E('final'), 9)} {ms(T('rr'))} {ms(T('fetch'), 5)} "
              f"{ms(T('emb_q'), 5)} + {ms(T('emb_bg'), 5)} {ms(T('dual_end'), 5)} {ms(T('store_peak'), 6)} "
              f"{ms(T('bytes_peak_m0'), 5, 0)} {ms(T('bytes_peak_m64'), 6, 0)} {ms(T('nodes'), 6, 0)} {ms(T('scan'), 8, 0)} "
              f"{ms(T('dual_from_e0'), 9)} {ms(E('lost_retire'), 5, 2)} {flips(X, st):7.1f} {ms(T('bg_rate'), 8, 2)}")


def stream_diffs(F, pairs):
    print("   Hiệu ghép theo seed, TB [KTC 95%]:")
    for lab, a, b in pairs:
        A, B = runs(F, a), runs(F, b)
        ss, d1 = pdiff(A, B, hf)
        if not ss:
            continue
        _, d2 = pdiff(A, B, srr)
        _, d3 = pdiff(A, B, lambda r: r["totals"].get("fetch", NAN))
        _, d4 = pdiff(A, B, lambda r: r["totals"].get("store_peak", NAN))
        _, d5 = pdiff(A, B, lambda r: r["totals"].get("bytes_peak_m0", NAN))
        print(f"   {lab:18s} n={len(ss):2d}  giữ riêng {cis(d1, 2):24s} dòng {cis(d2, 2):24s} tải {cis(d3, 2):22s} "
              f"record đỉnh {cis(d4):20s} byte đỉnh {cis(d5, 0)}")


SPAIRS = [("drain − lazy", DRAIN, "lazy"), ("drain − static", DRAIN, "static"), ("drain − k1", DRAIN, K1),
          ("drain − lazy+keep", DRAIN, "lazyD"), ("drain − full", DRAIN, "full"), ("k1 − lazy", K1, "lazy"),
          ("lazy − static", "lazy", "static"), ("lazy+delay − lazy", "lazyV1", "lazy")]


def pay_dual(F):
    """Phần dual ở cuối dòng và tỉ lệ payload trên đường truy vấn so với lazy, cho k1 và drain (cận của H5, H10d đặt cho k1)."""
    lz = runs(F, "lazy")
    out = []
    for p, lab in ((K1, "k1"), (DRAIN, "drain")):
        X = runs(F, p)
        ss = [s for s in sorted(X) if s in lz]
        if not ss:
            continue
        ratio = [X[s]["totals"]["fetch"] / max(1e-9, lz[s]["totals"]["fetch"]) for s in ss]
        dual = [X[s]["totals"].get("dual_end", NAN) for s in ss]
        out.append(f"{lab}: dual cuối TB {nmean(dual):.1f}% (lớn nhất {max(dual):.1f}%), payload / lazy TB {nmean(ratio):.3f} "
                   f"(lớn nhất {max(ratio):.3f})")
    return "; ".join(out)


# ----------------------------------------------------------------- H24 và E1: C3 trên khoá SRP gốc
def h24():
    head(f"H24. C3 trên khoá SRP gốc (--e1-place u, không cap): code 100k, 50.000 peer, Zipf 1, dòng 3.000 lượt, seed "
         f"{SEEDS_U}. 'Học' = cùng model, cùng seed với itq_q+cap16 (đợt 13 cho bge-base, pha D cho model khác). Cột như "
         f"Bảng 10 của bản thảo.")
    for t in UTAGS:
        U, Lr = srp(t), learned(t, SEEDS_U)
        print(f"\n--- {t}: khoá SRP gốc, {len(U)}/{len(SEEDS_U)} seed có file; placement học {len(Lr)}/{len(SEEDS_U)} seed")
        if not U:
            for c, w in zip("abcdef", ("drain − lazy, giữ riêng", "drain − lazy, dòng", "drain − static, giữ riêng",
                                       "hiệu của hiệu, dòng", "hiệu của hiệu, giữ riêng", "mất đường của lazy, học − SRP")):
                verdict(f"H24{c} {t}", False, f"{w}: chưa có file của pha U")
            continue
        st = [d.get("e1_storage", {}) for d in U.values()]
        print(f"   tải lưu trữ E1 khi mọi record ở E1 (SRP): peer nặng nhất {ms([x.get('max') for x in st], 7, 0)} record "
              f"(TB mỗi peer {ms([x.get('mean') for x in st], 4)}), 1% peer nặng nhất giữ "
              f"{100 * nmean([x.get('top1pct_share') for x in st]):.1f}%, peer rỗng {100 * nmean([x.get('empty_frac') for x in st]):.0f}%")
        print("   [khoá SRP gốc]")
        stream_table(U)
        if Lr:
            print("   [placement học, cùng seed]")
            stream_table({s: d for s, d in Lr.items() if s in U})
        print("   [khoá SRP gốc]")
        stream_diffs(U, SPAIRS)
        Ud, Ul, Us, Uk = runs(U, DRAIN), runs(U, "lazy"), runs(U, "static"), runs(U, K1)
        Ld, Ll, Lk = runs(Lr, DRAIN), runs(Lr, "lazy"), runs(Lr, K1)
        n = len(SEEDS_U)
        ss, va = pdiff(Ud, Ul, hf)
        crit(f"H24a {t}", ss, va, -1, n, "SRP, drain − lazy, giữ riêng")
        ss, vb = pdiff(Ud, Ul, srr)
        crit(f"H24b {t}", ss, vb, -1, n, "SRP, drain − lazy, rerank trên dòng")
        ss, v = pdiff(Ud, Us, hf)
        crit(f"H24c {t}", ss, v, 5, n, "SRP, drain − static, giữ riêng")
        ss, vd = did(Ld, Ll, Ud, Ul, srr)
        crit(f"H24d {t}", ss, vd, 0, n, "(drain − lazy) học − SRP, rerank trên dòng")
        ss, ve = did(Ld, Ll, Ud, Ul, hf)
        crit(f"H24e {t}", ss, ve, 0, n, "(drain − lazy) học − SRP, giữ riêng")
        ss, vf = pdiff(Ll, Ul, lost)
        crit(f"H24f {t}", ss, vf, 0, n, "mất đường của lazy, học − SRP")
        # mô tả theo cách đọc định trước, không phải tiêu chí
        sl, vl = pdiff(Ld, Ll, hf)
        _, vl2 = pdiff(Ld, Ll, srr)
        print(f"   mô tả: drain − lazy trên placement học, giữ riêng {cis(vl, 2)}, dòng {cis(vl2, 2)} (n = {len(sl)}); "
              f"mất đường của lazy: SRP {ms([lost(x) for x in Ul.values()], 5, 2)}%, học {ms([lost(x) for x in Ll.values()], 5, 2)}%")
        ss, vk = did(Lk, Ll, Uk, Ul, hf)
        _, vk2 = did(Lk, Ll, Uk, Ul, srr)
        print(f"   mô tả: hiệu của hiệu cho k1 − lazy (học − SRP): giữ riêng {cis(vk, 2)}, dòng {cis(vk2, 2)} (n = {len(ss)})")
        pos = [nm for nm, v in (("giữ riêng", va), ("rerank trên dòng", vb)) if ci(v)[1] > 0]
        if not va:
            print(f"   ĐỌC ({t}): chưa có run drain và lazy trên khoá SRP, chưa đọc được.")
            continue
        if len(pos) == 2:
            msg = "bài nói dual migration cũng có lợi trên khoá SRP ở cả hai độ đo."
        elif pos:
            msg = f"bài nói dual migration cũng có lợi trên khoá SRP ở {pos[0]}; ở độ đo còn lại lazy đã gần đủ."
        else:
            msg = "bài nói trên khoá SRP lazy đã gần đủ cho model này ở cả hai độ đo."
        print(f"   ĐỌC ({t}): trên khoá SRP, drain − lazy có cận dưới KTC > 0 ở {len(pos)}/2 độ đo "
              f"({', '.join(pos) if pos else 'không độ đo nào'}): {msg}")
    print()


# ----------------------------------------------------------------- H22 và E3: migrate tới khi xong trên seed mới
def files_c(ds, t):
    return {s: d for s in SEEDS_C for d in [jl(f"probeV14F_{ds}_{t}_s{s}_cap16.json")] if d}


def ts_of(F, ds):
    for d in F.values():
        if d.get("bg_finish"):
            return [int(x) for x in d["bg_finish"]]
    return [1500, 3000] if ds == "code" else [400, 800]


def run_of(d, p, T):
    return d["runs"].get(f"z1|PROB|{p}|T{T}" if p in BGP else f"z1|PROB|{p}")


def c_cell(F, T):
    need = ("static", "full", "bg", "lazybg", "rebuild", K1, DRAIN)
    ss = [s for s in sorted(F) if all(run_of(F[s], p, T) for p in need)]
    g = lambda s, p: run_of(F[s], p, T)
    A = {p: [area(g(s, p)["snapshots"], T) for s in ss] for p in need}
    R = {p: [win_mean(g(s, p), T, "rr") for s in ss] for p in need}
    d = lambda X, a, b: [x - y for x, y in zip(X[a], X[b])]
    tt = lambda s, p, k: g(s, p)["totals"].get(k, NAN)
    out = dict(n=len(ss), ss=ss, reb_a=d(A, DRAIN, "rebuild"), lbg_a=d(A, DRAIN, "lazybg"), lbg_r=d(R, DRAIN, "lazybg"),
               st_a=d(A, DRAIN, "static"), bg_a=d(A, DRAIN, "bg"), k1_a=d(A, DRAIN, K1), k1_r=d(R, DRAIN, K1),
               full_a=d(A, DRAIN, "full"), reb_r=d(R, DRAIN, "rebuild"))
    out["pk"] = {p: nmean([tt(s, p, "bytes_peak_m0") / max(1e-9, tt(s, p, "bytes_t0_m0")) for s in ss])
                 for p in (DRAIN, K1, "rebuild", "lazybg")}
    out["pk_more"] = [tt(s, DRAIN, "bytes_peak_m0") - tt(s, "rebuild", "bytes_peak_m0") for s in ss]
    out["done"] = {p: nmean([100.0 * tt(s, p, "t_done") / T for s in ss if tt(s, p, "t_done") >= 0])
                   for p in ("lazybg", K1, DRAIN)}
    return out


def h22():
    head(f"H22. Xác nhận drain khi migrate tới khi xong, seed mới {SEEDS_C}, itq_q+cap16, Zipf 1, gỡ E0 khi xong (như đợt "
         f"11). Hiệu ghép theo seed, TB [KTC 95%]; diện tích trên [0, T], rerank trên [0, T).")
    cells = {}
    for ds in ("code", "scifact"):
        for t in CTAGS:
            F = files_c(ds, t)
            for T in ts_of(F, ds):
                c = c_cell(F, T)
                cell = f"{ds} {t} T={T}"
                cells[cell] = c
                print(f"\n   {cell:26s} n={c['n']:2d}  drain − rebuild {cis(c['reb_a'], 2):22s} − lazy+bg: diện tích "
                      f"{cis(c['lbg_a'], 2):22s} rerank {cis(c['lbg_r'], 2):22s} − static {cis(c['st_a'], 2):22s} − bg "
                      f"{cis(c['bg_a'], 2)}")
                n = len(SEEDS_C)
                crit(f"H22a {cell}", c["ss"], c["reb_a"], 10, n, "drain − rebuild, diện tích")
                crit(f"H22b {cell}", c["ss"], c["lbg_a"], 0, n, "drain − lazy+bg, diện tích")
                crit(f"H22c {cell}", c["ss"], c["lbg_r"], 0, n, "drain − lazy+bg, rerank")
                crit(f"H22d {cell}", c["ss"], c["st_a"], 10, n, "drain − static, diện tích")
                crit(f"H22e {cell}", c["ss"], c["bg_a"], 5, n, "drain − bg, diện tích")
    ok = [c for c in cells.values() if c["n"]]
    print(f"\n   Khoảng qua {len(ok)}/{len(cells)} ô có dữ liệu (TB theo seed của mỗi ô), cạnh khoảng của đợt 11 (seed 26 đến 35):")
    for key, lab in (("reb_a", "drain − rebuild, diện tích"), ("lbg_a", "drain − lazy+bg, diện tích"),
                     ("lbg_r", "drain − lazy+bg, rerank"), ("st_a", "drain − static, diện tích"),
                     ("bg_a", "drain − bg, diện tích"), ("full_a", "drain − full, diện tích"),
                     ("k1_a", "drain − k1, diện tích"), ("k1_r", "drain − k1, rerank"),
                     ("reb_r", "drain − rebuild, rerank")):
        m = [nmean(c[key]) for c in ok]
        lows = [x for x in (ci(c[key])[1] for c in ok) if x == x]
        low = min(lows) if lows else NAN
        print(f"   {lab:28s} đợt 14: {rng(m):18s} (cận dưới KTC nhỏ nhất {low:+.2f}, "
              f"{sum(1 for x in lows if x > 0)}/{len(ok)} ô có cận dưới > 0)   đợt 11: {R11[key][0]:+.1f} đến {R11[key][1]:+.1f}")
    if ok:
        pk = lambda p: [c["pk"][p] for c in ok]
        dn = lambda p: [c["done"][p] for c in ok]
        more = sum(1 for c in ok if nmean(c["pk_more"]) > 0)
        print(f"   byte đỉnh so với mức đầu (mã PQ): drain {min(pk(DRAIN)):.2f} đến {max(pk(DRAIN)):.2f} lần, k1 "
              f"{min(pk(K1)):.2f} đến {max(pk(K1)):.2f}, rebuild {min(pk('rebuild')):.2f} đến {max(pk('rebuild')):.2f}, "
              f"lazy+bg {min(pk('lazybg')):.2f} đến {max(pk('lazybg')):.2f}; drain hơn rebuild về byte đỉnh ở {more}/{len(ok)} ô "
              f"(đợt 11: 1.72 đến 2.80; rebuild 1.36 đến 1.90; 20/20 ô)")
        print(f"   lượt xong so với T: lazy+bg {min(dn('lazybg')):.0f}% đến {max(dn('lazybg')):.0f}%, k1 {min(dn(K1)):.0f}% đến "
              f"{max(dn(K1)):.0f}%, drain {min(dn(DRAIN)):.0f}% đến {max(dn(DRAIN)):.0f}% (đợt 11: lazy+bg 28 đến 50%, "
              f"drain 52 đến 77%)")
    print()
    return cells


def e3():
    head("THĂM DÒ E3. Migrate tới khi xong (pha C), mọi chính sách của mỗi ô: diện tích [0, T]; rerank, payload, peer là TB "
         "trên các cửa sổ trong [0, T); byte đỉnh so với mức đầu (mã PQ, metadata 0); lượt xong so với T")
    for ds in ("code", "scifact"):
        for t in CTAGS:
            F = files_c(ds, t)
            if not F:
                continue
            for T in ts_of(F, ds):
                print(f"\n--- {ds} {t} T={T}, n = {len(F)} seed")
                print(f"   {'chính sách':10s} {'diện tích':>9s} {'rerank':>6s} {'payload':>7s} {'peer':>6s} {'byte đỉnh':>9s} "
                      f"{'xong/T %':>8s}")
                for p, lab in CPOL:
                    xs = [r for r in (run_of(d, p, T) for d in F.values()) if r]
                    if not xs:
                        continue
                    td = [100.0 * x["totals"]["t_done"] / T for x in xs if x["totals"].get("t_done", -1) >= 0]
                    print(f"   {lab:10s} {ms([area(x['snapshots'], T) for x in xs], 9, 2)} "
                          f"{ms([win_mean(x, T, 'rr') for x in xs], 6, 2)} {ms([win_mean(x, T, 'fetch') for x in xs], 7, 2)} "
                          f"{ms([win_mean(x, T, 'nodes') for x in xs], 6, 0)} "
                          f"{ms([x['totals']['bytes_peak_m0'] / max(1e-9, x['totals']['bytes_t0_m0']) for x in xs], 9, 2)} "
                          f"{ms(td, 8, 0)}")
    print()


# ----------------------------------------------------------------- H23 và E2: drain trên dòng, placement học
def h23():
    head(f"H23. Drain trên dòng 3.000 lượt của code 100k với placement học (itq_q+cap16, 50.000 peer, Zipf 1), seed "
         f"{SEEDS_D}. Số của static, lazy, k1 trên các seed này đã có từ đợt 11; drain là phần mới. Cột như Bảng 10.")
    ref = learned("bgebase", SEEDS_D)
    if ref and "bgebase" not in DTAGS:
        print(f"\n--- bgebase (đợt 13, để đối chiếu, không chấm), n = {len(ref)} seed")
        stream_diffs(ref, SPAIRS[:3])
        print(f"   {pay_dual(ref)}")
    for t in DTAGS:
        F0 = {s: d for s in SEEDS_D for d in [jl(f"probeV14_code100kfq_{t}_s{s}_cap16.json")] if d}
        F = {s: d for s, d in F0.items() if usable(d)}
        print(f"\n--- {t}: {len(F)}/{len(SEEDS_D)} seed dùng được" + (f"; bỏ seed {sorted(set(F0) - set(F))} vì tự kiểm với đợt 11 LỆCH"
                                                                    if len(F) < len(F0) else ""))
        if F:
            stream_table(F)
            stream_diffs(F, SPAIRS)
            print(f"   {pay_dual(F)}")
        dr, lz, st, k1 = runs(F, DRAIN), runs(F, "lazy"), runs(F, "static"), runs(F, K1)
        n = len(SEEDS_D)
        ss, v = pdiff(dr, lz, hf)
        crit(f"H23a {t}", ss, v, 0, n, "drain − lazy, giữ riêng")
        ss, v = pdiff(dr, lz, srr)
        crit(f"H23b {t}", ss, v, 5, n, "drain − lazy, rerank trên dòng")
        ss, v = pdiff(dr, st, hf)
        crit(f"H23c {t}", ss, v, 3, n, "drain − static, giữ riêng")
        ss, v = pdiff(dr, st, srr)
        crit(f"H23d {t}", ss, v, 0, n, "drain − static, rerank trên dòng")
        ss, v = pdiff(dr, k1, srr)
        crit(f"H23e {t}", ss, v, 0, n, "drain − k1, rerank trên dòng")
        ss, v = pdiff(dr, k1, hf)
        crit(f"H23f {t}", ss, v, -1, n, "drain − k1, giữ riêng")
        if dr and k1:
            print(f"   k1 xấu hơn drain ở cuối: rerank {flips(k1, dr):.1f}% query giữ riêng, final {flips(k1, dr, 'fin_hits'):.1f}%; "
                  f"drain xấu hơn k1: rerank {flips(dr, k1):.1f}%, final {flips(dr, k1, 'fin_hits'):.1f}%")
    print()


# ----------------------------------------------------------------- E4: full ở cùng số peer
def e4():
    head(f"THĂM DÒ E4. Full ở T = {BPROBES} probe (cùng số peer với hai epoch) trên dòng của Bảng 10: code 100k, itq_q+cap16, "
         f"Zipf 1, seed {SEEDS_B}")
    for t in BTAGS:
        FB = {s: d for s in SEEDS_B for d in [jl(f"probeV14B_code100kfq_{t}_s{s}_cap16_T{BPROBES}.json")] if d}
        if not FB:
            print(f"   {t}: chưa có file")
            continue
        Lr = learned(t, SEEDS_B)
        fb = runs(FB, "full")
        nat = [d.get("native_f1") or {} for d in FB.values()]
        print(f"\n--- {t}, n = {len(fb)} seed; index native ở f = 1 trên 300 query đánh giá, T = {BPROBES}: final "
              f"{ms([x.get('final_r5') for x in nat])}, rerank@20 {ms([x.get('rr20') for x in nat])}, ứng viên "
              f"{ms([x.get('cand') for x in nat], 7, 0)}, peer {ms([x.get('nodes') for x in nat], 6, 0)}")
        print(f"   {'chính sách':18s} {'n':>2s} {'giữ riêng':>9s} {'dòng':>6s} {'final dòng':>10s} {'peer':>6s} {'ứng viên':>8s}")
        rows = [(f"full, T = {BPROBES}", fb)] + [(lab, runs(Lr, p)) for p, lab in (("full", "full, T = 8"), (DRAIN, "dual (drain)"),
                                                                                (K1, "dual (k1)"), ("static", "static"))]
        for lab, X in rows:
            if not X:
                continue
            T = lambda k: [x["totals"].get(k, NAN) for x in X.values()]
            print(f"   {lab:18s} {len(X):2d} {ms([hf(x) for x in X.values()], 9)} {ms(T('rr'))} {ms(T('final'), 10)} "
                  f"{ms(T('nodes'), 6, 0)} {ms(T('scan'), 8, 0)}")
        for lab, p in (("drain − full(T16)", DRAIN), ("k1 − full(T16)", K1), ("full(T8) − full(T16)", "full")):
            A = runs(Lr, p)
            ss, d1 = pdiff(A, fb, hf)
            _, d2 = pdiff(A, fb, srr)
            if ss:
                print(f"   {lab:22s} n={len(ss):2d}  giữ riêng {cis(d1, 2):24s} dòng {cis(d2, 2)}")
    print()


# ----------------------------------------------------------------- E5: churn và lỗi peer có drain
FPOL = [("static", "static"), ("lazy", "lazy"), ("lazyV1", "lazy+delay"), (K1, "k1"), ("lazyD", "lazy+keep"),
        (DRAIN, "drain"), ("full", "full")]


def e5():
    head(f"THĂM DÒ E5. Churn (ch) và lỗi 30% peer không sửa (fail) trên itq_q+cap16, code 100k, Zipf 1, seed {SEEDS_F}. mất "
         f"so với không churn = giữ riêng cuối dòng của cùng seed không churn (file dòng của pha D hoặc đợt 13) trừ giữ riêng "
         f"cuối dòng có churn")
    for t in FTAGS:
        F = {s: d for s in SEEDS_F for d in [jl(f"probeV14C_code100kfq_{t}_s{s}_cap16.json")] if d}
        if not F:
            print(f"   {t}: chưa có file")
            continue
        Lr = learned(t, SEEDS_F)
        if not Lr:                                    # model không có ở pha D (hoặc chưa chạy): dùng file ablation của đợt 11
            Lr = {s: d for s in SEEDS_F for d in [jl(f"probeV11_code100kfq_{t}_s{s}_cap16.json")] if d}
        print(f"\n--- {t}, n = {len(F)} seed")
        for cname in ("ch", "fail"):
            st = runs(F, "static", f"|{cname}")
            print(f"   {cname:4s} {'chính sách':10s} {'giữ riêng':>9s} {'dòng':>6s} {'mất so với không churn':>22s} "
                  f"{'mất mọi đường %':>15s} {'(lớn nhất)':>10s} {'ghi sửa/q':>9s} {'so static':>9s} {'keep-alive/q':>12s} "
                  f"{'so static':>9s}")
            for p, lab in FPOL:
                X = runs(F, p, f"|{cname}")
                if not X:
                    continue
                T = lambda k: [x["totals"].get(k, NAN) for x in X.values()]
                N0 = runs(Lr, p)
                dl = [hf(N0[s]) - hf(X[s]) for s in sorted(X) if s in N0]

                def rat(k):                              # tỉ số của hai trung bình qua seed, như bản thảo
                    cs = [s for s in X if s in st and k in X[s]["totals"] and k in st[s]["totals"]]
                    den = nmean([st[s]["totals"][k] for s in cs])
                    return nmean([X[s]["totals"][k] for s in cs]) / den if den == den and den > 0 else NAN
                print(f"   {cname:4s} {lab:10s} {ms([hf(x) for x in X.values()], 9)} {ms(T('rr'))} "
                      f"{(cis(dl, 2) if dl else 'n/a'):>22s} {ms(T('lost_obj_end'), 15, 3)} {ms(T('lost_obj_max'), 10, 3)} "
                      f"{ms(T('repair_w'), 9, 1)} {rat('repair_w'):9.3f} {ms(T('keepalive'), 12, 0)} {rat('keepalive'):9.3f}")
            dr = runs(F, DRAIN, f"|{cname}")
            for lab, p in (("drain − k1", K1), ("drain − lazy", "lazy"), ("drain − static", "static"), ("drain − full", "full")):
                ss, d1 = pdiff(dr, runs(F, p, f"|{cname}"), hf)
                if ss:
                    _, d2 = pdiff(dr, runs(F, p, f"|{cname}"), srr)
                    print(f"        {lab:15s} n={len(ss)}  giữ riêng {cis(d1, 2):24s} dòng {cis(d2, 2)}")
    print()


# ----------------------------------------------------------------- E6: độ nhạy theo số object mỗi peer
OVARS = ["srp", "srp+cap16", "srp_c+cap16", "itq_q", "itq_q+cap16"]


def grp(qf):
    if qf != qf:
        return "?"
    return "lớn" if qf >= QF_HI else ("nhỏ" if qf <= QF_LO else "giữa")


def qf_of(sp):
    """qf triển khai được của không gian trên code 100k (đợt 13); thiếu thì lấy qf dự đoán cũ của probeA11."""
    v = [d["deploy"]["qf_S_val_u"] for s in SEEDS_O for d in [jl(f"probeQ13_A11_code100kfq_{sp}_s{s}.json")] if d]
    if v:
        return nmean(v), "S"
    v = [d["ext"]["qfrac_pred_u"] for s in SEEDS_O for d in [jl(f"probeA11_code100kfq_{sp}_s{s}.json")] if d]
    return (nmean(v), "cũ") if v else (NAN, "?")


def o_stats(D):
    f = lambda va, vb, vr, x: nmean([at_ref(d, va, vb, vr, x) for d in D])
    return dict(n=len(D), nodes=sorted({int(d["argv"]["nodes"]) for d in D}), obj=nmean([d["N"] / d["argv"]["nodes"] for d in D]),
                c2=f("itq_q+cap16", "srp_c+cap16", "srp_c+cap16", "cand"), cap=f("itq_q+cap16", "itq_q", "itq_q", "cand"),
                dpeer=f("srp", "itq_q+cap16", "srp_c+cap16", "nodes"))


def e6():
    head(f"THĂM DÒ E6. Độ nhạy theo số object mỗi peer: placement của code 100k trên {ONODES:,} peer (pha O), cạnh số của đợt "
         f"11 ở 50.000 peer; cùng seed {SEEDS_O}, cùng khoá, chỉ khác overlay. Δ_ứng viên = F_itq_q+cap16 − F_srp_c+cap16 tại "
         f"số ứng viên của srp_c+cap16 ở (5,8); cap = F_itq_q+cap16 − F_itq_q tại số ứng viên của itq_q ở (5,8); Δ_peer = "
         f"F_srp − F_itq_q+cap16 tại số peer của srp_c+cap16 ở (5,8), dương là SRP gốc tốt hơn ở cùng số peer")
    rows = []
    for sp in OSPACES:
        Dn = [d for s in SEEDS_O for d in [jl(f"probeP14_code100kfq_{sp}_s{s}_n{ONODES}.json")] if d]
        Dr = [d for s in SEEDS_O for d in [jl(f"probeP11_code100kfq_{sp}_s{s}.json")] if d]
        rows.append((sp, qf_of(sp), Dn, Dr))
    print(f"   {'không gian':10s} {'qf':>9s} {'nhóm':>5s} | {ONODES:>6,d} peer: {'n':>1s} {'obj/peer':>8s} {'Δ_ứng viên':>10s} "
          f"{'cap':>6s} {'Δ_peer':>7s} {'tốt hơn':>7s} | đợt 11: {'n':>1s} {'obj/peer':>8s} {'Δ_ứng viên':>10s} {'cap':>6s} "
          f"{'Δ_peer':>7s} {'tốt hơn':>7s}")
    agree = same = dec = 0
    c2_pos = 0
    for sp, (qf, src), Dn, Dr in rows:
        a, b = o_stats(Dn) if Dn else None, o_stats(Dr) if Dr else None
        bet = lambda x: "SRP" if x > 0 else ("học" if x == x else "?")
        cell = lambda x: (f"{x['n']:1d} {x['obj']:8.1f} {x['c2']:+10.2f} {x['cap']:+6.2f} {x['dpeer']:+7.2f} {bet(x['dpeer']):>7s}"
                          if x else f"{'chưa có file':>44s}")
        print(f"   {sp:10s} {qf:9.2e} {grp(qf):>5s} | {'':12s} {cell(a)} | {'':7s} {cell(b)}")
        if a:
            c2_pos += a["c2"] >= 5
            if grp(qf) in ("lớn", "nhỏ"):
                dec += 1
                agree += {"lớn": "SRP", "nhỏ": "học"}[grp(qf)] == bet(a["dpeer"])
            if b:
                same += bet(a["dpeer"]) == bet(b["dpeer"])
    have = [r for r in rows if r[2]]
    for sp, _, Dn, Dr in rows:
        for lab, D in ((f"{ONODES:,} peer", Dn), ("đợt 11", Dr)):
            if not D:
                continue
            print(f"\n--- {sp}, {lab} ({sorted({int(d['argv']['nodes']) for d in D})} peer, n = {len(D)}), ở (L = 5, T = 8)")
            print(f"   {'biến thể':12s} {'final':>6s} {'rr@20':>6s} {'ứng viên':>8s} {'peer':>6s} {'q tới peer nóng nhất %':>22s} "
                  f"{'1% peer giữ %':>13s} {'tải max/TB':>10s} {'bị dời %':>8s} {'vào peer đầy %':>14s}")
            for v in OVARS:
                X = [d["variants"][v] for d in D if v in d["variants"]]
                if not X:
                    continue
                r58 = lambda k: [x["results"]["5"]["8"][k] for x in X]
                stg = [x["results"]["5"]["storage"] for x in X]
                cap = [x.get("cap") for x in X if x.get("cap")]
                print(f"   {v:12s} {ms(r58('final_r5'))} {ms(r58('rr20'))} {ms(r58('cand'), 8, 0)} {ms(r58('nodes'), 6, 0)} "
                      f"{ms([100 * x['results']['5']['8']['qload']['max_frac'] for x in X], 22)} "
                      f"{ms([100 * s['top1pct_share'] for s in stg], 13)} {ms([s['max'] / max(1e-9, s['mean']) for s in stg], 10)} "
                      f"{ms([100 * c['moved_frac_L5'] for c in cap], 8, 2)} {ms([100 * c['fallback_frac_L5'] for c in cap], 14, 2)}")
    if have:
        print(f"\n   ĐỌC (thăm dò): ở {ONODES:,} peer, khoá học có cap hơn khoá ngẫu nhiên đã trừ tâm có cap ít nhất 5 điểm ở cùng số "
              f"ứng viên tại {c2_pos}/{len(have)} không gian; quy tắc qf (ngưỡng của 16 bit, không đổi) đoán đúng biến thể tốt hơn ở "
              f"cùng số peer tại {agree}/{dec} không gian có nhóm; biến thể tốt hơn ở cùng số peer trùng với 50.000 peer tại "
              f"{same}/{sum(1 for r in have if r[3])} không gian.")
    print()


# ----------------------------------------------------------------- tự kiểm
def checks():
    head("Tự kiểm")
    fr = gl("probeVR14*.json")
    for fn in fr:
        d = jl(fn)
        c = (d or {}).get("check_prev")
        if c:
            old = jl(c["file"])
            miss = [k for k in (old or {}).get("runs", {}) if k not in d["runs"]]
            print(f"   R: {fn}: {c['n']} giá trị so với {c['file']}, "
                  f"{'KHỚP' if c['bad'] == 0 and c['n'] > 0 else str(c['bad']) + ' LỆCH ' + str(c.get('diffs', [])[:3])}; "
                  f"đủ {len((old or {}).get('runs', {})) - len(miss)}/{len((old or {}).get('runs', {}))} run của lượt cũ")
        elif d:
            print(f"   R: {fn}: không có kết quả so với đợt 13")
    if not fr:
        print("   R: chưa có file")

    def prev_check(pat, lab, what):
        files = gl(pat)
        ok = tot = nv = noprev = 0
        for fn in files:
            d = jl(fn)
            if not d:
                continue
            c = d.get("check_prev")
            if not c:
                noprev += 1
                continue
            tot += 1; nv += c["n"]
            if c["bad"] == 0 and c["n"] > 0:
                ok += 1
            else:
                print(f"   {lab} {fn}: {c['bad']} LỆCH trên {c['n']} giá trị, ví dụ {c.get('diffs', [])[:3]}")
        print(f"   {lab}: {ok}/{tot} file KHỚP từng số với {what} ở các run trùng tên ({nv} giá trị)"
              + (f"; {noprev} file không có file cũ để so" if noprev else ""))
    prev_check("probeV14_code100kfq_*_cap16.json", "D", "đợt 11")
    prev_check("probeV14C_code100kfq_*_cap16.json", "F", "file churn của đợt 11")
    pats = ["probeV14_code100kfq_*_cap16.json", "probeV14C_code100kfq_*_cap16.json", "probeV14B_code100kfq_*.json"]
    n_ok = n_tot = 0
    for pat in pats:
        for fn in gl(pat):
            c = (jl(fn) or {}).get("check_10")
            if c:
                n_tot += 1
                if c["bad"] == 0 and c["n"] > 0:
                    n_ok += 1
                else:
                    print(f"   {fn}: placement so với probeP11 LỆCH {c.get('diffs')}")
    print(f"   placement itq_q+cap16 trong 11 so với probeP11 (pha D, F, B; seed có file): {n_ok}/{n_tot} file KHỚP")
    # cách đặt record E1 đúng theo pha
    bad_u = [fn for fn in gl("probeV14U_*.json") if jl(fn) and (jl(fn)["argv"]["e1_place"] != "u" or jl(fn)["argv"]["e1_cap"] > 0)]
    lp = gl("probeV14_code100kfq_*.json") + gl("probeV14F_*.json") + gl("probeV14C_*.json") + gl("probeV14B_*.json")
    bad_l = [fn for fn in lp if jl(fn) and (jl(fn)["argv"]["e1_place"] != "itq_q" or jl(fn)["argv"]["e1_cap"] != 16)]
    bad_b = [fn for fn in gl("probeV14B_*.json") if jl(fn) and jl(fn)["argv"]["probes"] != BPROBES]
    print(f"   cách đặt record E1: pha U ghi u, không cap ở {len(gl('probeV14U_*.json')) - len(bad_u)}/{len(gl('probeV14U_*.json'))} "
          f"file; pha D, C, F, B ghi itq_q, cap 16 ở {len(lp) - len(bad_l)}/{len(lp)} file; pha B ghi probes = {BPROBES} ở "
          f"{len(gl('probeV14B_*.json')) - len(bad_b)}/{len(gl('probeV14B_*.json'))} file")
    # drain không retire; nhúng lại do truy vấn + do nền = new
    n_inf = bad_inf = n_emb = bad_emb = n_rb = bad_rb = 0
    allv = gl("probeV14U_*.json") + lp
    for fn in allv:
        d = jl(fn)
        if not d:
            continue
        for k, r in d["runs"].items():
            pol, tt = k.split("|")[2], r["totals"]
            if pol == DRAIN:
                n_inf += 1
                bad_inf += tt.get("retired_total", 0) != 0
            if "emb_q" not in tt:
                continue
            if pol == "rebuild":
                if tt.get("t_done", -1) >= 0:
                    n_rb += 1
                    bad_rb += abs(tt["emb_bg"] * d["argv"]["stream"] - (d["N"] - d["n_sample"])) > 1e-6
            else:
                n_emb += 1
                bad_emb += abs(tt["emb_q"] + tt["emb_bg"] - tt["new"]) > 1e-9
    print(f"   drain không retire bản E0 nào trước khi gỡ: {n_inf - bad_inf}/{n_inf} run; nhúng lại do truy vấn + do nền = new: "
          f"{n_emb - bad_emb}/{n_emb} run; rebuild dựng đủ N − |S| bản ở nền: {n_rb - bad_rb}/{n_rb} run")
    # pha C: checkpoint sau lượt xong trùng full, rebuild trước lượt xong trùng static
    n_post = bad_post = n_pre = bad_pre = 0
    for fn in gl("probeV14F_*_cap16.json"):
        d = jl(fn)
        if not d:
            continue
        fu, stc = d["runs"].get("z1|PROB|full"), d["runs"].get("z1|PROB|static")
        for k, r in d["runs"].items():
            if "|T" not in k or not fu:
                continue
            pol, td = k.split("|")[2], r["totals"].get("t_done", -1)
            for c, sv in r["snapshots"].items():
                if td >= 0 and int(c) >= td:
                    n_post += 1
                    bad_post += any(abs(sv[m] - fu["snapshots"][c][m]) > 1e-9 for m in ("final", "rr"))
                elif pol == "rebuild" and stc:
                    n_pre += 1
                    bad_pre += any(abs(sv[m] - stc["snapshots"][c][m]) > 1e-9 for m in ("final", "rr"))
    print(f"   pha C: checkpoint sau lượt xong trùng full {n_post - bad_post}/{n_post}; rebuild trước lượt xong trùng static "
          f"{n_pre - bad_pre}/{n_pre}")
    # pha O: thống kê bit của mỗi biến thể không phụ thuộc số peer, phải trùng probeP11 cùng seed
    n_bit = bad_bit = n_cmp = 0
    for sp in OSPACES:
        for s in SEEDS_O:
            a, b = jl(f"probeP14_code100kfq_{sp}_s{s}_n{ONODES}.json"), jl(f"probeP11_code100kfq_{sp}_s{s}.json")
            if not a or not b:
                continue
            n_cmp += 1
            for v in a["variants"]:
                if v in b["variants"]:
                    for kk, x in a["variants"][v]["bits"].items():
                        n_bit += 1
                        bad_bit += abs(x - b["variants"][v]["bits"].get(kk, NAN)) > 1e-12
    print(f"   pha O: thống kê bit trùng probeP11 cùng seed: {n_bit - bad_bit}/{n_bit} giá trị trên {n_cmp} cặp file")
    cnt = [("U", "probeV14U_*.json", len(UTAGS) * len(SEEDS_U)), ("C", "probeV14F_*_cap16.json", 2 * len(CTAGS) * len(SEEDS_C)),
           ("D", "probeV14_code100kfq_*_cap16.json", len(DTAGS) * len(SEEDS_D)),
           ("F", "probeV14C_*_cap16.json", len(FTAGS) * len(SEEDS_F)), ("B", "probeV14B_*.json", len(BTAGS) * len(SEEDS_B)),
           ("O", "probeP14_*.json", len(OSPACES) * len(SEEDS_O)), ("R", "probeVR14*.json", 1)]
    print("   số file: " + ", ".join(f"{k} {len(gl(p))}/{n}" for k, p, n in cnt))
    print()


def summary():
    head("TÓM TẮT ĐÁNH GIÁ ĐĂNG KÝ TRƯỚC (H22 đến H24)")
    groups = defaultdict(lambda: [0, 0, []])
    for nm, st, det in VERDICT:
        g = nm.split()[0]
        groups[g][0] += st == "ĐẠT"
        groups[g][1] += 1
        if st != "ĐẠT":
            groups[g][2].append(nm[len(g) + 1:])
    for g in sorted(groups):
        a, n, bad = groups[g]
        print(f"   {g}: {a}/{n} đạt" + (f"; không đạt: {', '.join(bad)}" if bad else ""))
    for h in ("H22", "H23", "H24"):
        a = sum(v[0] for g, v in groups.items() if g.startswith(h))
        n = sum(v[1] for g, v in groups.items() if g.startswith(h))
        print(f"   {h}: {a} trên {n} tiêu chí đạt")
    n_ok = sum(1 for _, st, _ in VERDICT if st == "ĐẠT")
    print(f"   Tổng: {n_ok} trên {len(VERDICT)} tiêu chí đạt (đăng ký trước: 130 tiêu chí)\n")


def main():
    h24()
    h22()
    h23()
    summary()
    e3()
    e4()
    e5()
    e6()
    checks()


if __name__ == "__main__":
    main()
