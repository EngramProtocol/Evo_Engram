#!/usr/bin/env python3
"""
analyze_r15.py: đánh giá đợt 15 theo đúng evo/PREREG_round15.md (H25), rồi in phần thăm dò E1 đến E5 và tự kiểm.
Đọc ở thư mục hiện tại (thư mục gốc repo), hoặc ở THƯ_MỤC nếu có tham số:
  probeV15U_<ds>_<tag>_s<seed>.json            pha V, W: migrate tới khi xong trên khoá SRP gốc (--e1-place u, không cap)
  probeV14F_<ds>_<tag>_s<seed>_cap16.json      pha C của đợt 14: cùng ô, cùng seed, placement học (itq_q+cap16)
  probeVR15_*.json                             pha R
Danh sách seed và model lấy từ biến môi trường do run_round15.sh đặt (mặc định đúng như đăng ký trước).
  python3 evo/analyze_r15.py [THƯ_MỤC]
"""
import glob, json, math, os, sys
from collections import defaultdict
import numpy as np

envl = lambda k, d: os.environ.get(k, d).split()
envi = lambda k, d: [int(x) for x in envl(k, d)]
SEEDS_V = envi("SEEDS_V", "46 47 48 49 50 51 52 53 54 55")
VTAGS = envl("VTAGS", "bgebase e5large gtebase")            # model mà quy tắc H19 chọn SRP trên code 20k và SciFact
WTAGS = envl("WTAGS", "arctic minilm")                      # thăm dò: model mà quy tắc chọn placement học
HIQF = envl("HIQF", "e5large gtebase")                      # H25f: model có qf dự đoán trên 1e-2
DSETS = ("code", "scifact")
# qf dự đoán từ mẫu S và query validation (Bảng S1 của bản thảo; đợt 13 trên file probeA của đợt 12, seed 36 đến 38)
QF_S = {("code", "bgebase"): 1.30e-3, ("code", "e5large"): 1.60e-2, ("code", "gtebase"): 1.24e-2,
        ("code", "arctic"): 1.51e-4, ("code", "minilm"): 5.00e-5,
        ("scifact", "bgebase"): 2.18e-3, ("scifact", "e5large"): 1.43e-2, ("scifact", "gtebase"): 1.32e-2,
        ("scifact", "arctic"): 6.20e-5, ("scifact", "minilm"): 8.24e-5}
QF_HI, QF_LO = 8e-4, 2e-4
TCRIT = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
         11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086}
K1, DRAIN = "lazyVbgD", "lazyVbgDinf"
BGP = ("bg", "lazybg", "rebuild", K1, DRAIN)                # chính sách có nền (tên run có hậu tố |T<T>)
CPOL = [("static", "static"), ("lazy", "lazy"), ("full", "full"), ("bg", "bg"), ("lazybg", "lazy+bg"),
        ("rebuild", "rebuild"), (K1, "k1"), (DRAIN, "drain")]
NEED = ("static", "full", "bg", "lazybg", "rebuild", K1, DRAIN)
FQ = (0.3, 0.5, 0.7)                                        # E2: phần object đã có record E1
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


def cis(v, p=2):
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


def thr_s(thr):
    return "0" if thr == 0 else f"{thr:+g}".replace("-", "−")


def crit_lo(name, ss, v, thr, nseed, what):
    """Tiêu chí 'cận dưới KTC lớn hơn thr', chỉ đạt khi đủ nseed seed."""
    lo = ci(v)[1]
    full = len(ss) == nseed
    verdict(name, full and lo > thr, f"{what}: {cis(v)}, n = {len(ss)}" + ("" if full else f" (THIẾU SEED, cần {nseed})")
            + f"; cần cận dưới > {thr_s(thr)}")
    return full and lo > thr


def crit_hi(name, ss, v, thr, nseed, what):
    """Tiêu chí 'cận trên KTC nhỏ hơn thr', chỉ đạt khi đủ nseed seed."""
    hi = ci(v)[2]
    full = len(ss) == nseed
    verdict(name, full and hi < thr, f"{what}: {cis(v)}, n = {len(ss)}" + ("" if full else f" (THIẾU SEED, cần {nseed})")
            + f"; cần cận trên < {thr_s(thr)}")
    return full and hi < thr


def area(snaps, T, key="final"):
    """Trung bình của một đại lượng ở checkpoint trên [0, T], hình thang qua các checkpoint <= T."""
    cs = sorted(int(c) for c in snaps if int(c) <= T)
    if len(cs) < 2 or cs[-1] != T or any(key not in snaps[str(c)] for c in cs):
        return NAN
    v = [snaps[str(c)][key] for c in cs]
    return float(sum((cs[i + 1] - cs[i]) * (v[i] + v[i + 1]) / 2 for i in range(len(cs) - 1)) / T)


def win_mean(r, T, key):
    """Trung bình theo lượt của một đại lượng cửa sổ trên các cửa sổ kết thúc trước hoặc đúng T."""
    ws = [w for w in r["windows"] if w["t_end"] <= T]
    if not ws or any(key not in w for w in ws):
        return NAN
    lens = np.diff([0] + [w["t_end"] for w in ws])
    return float(np.sum([w[key] * n for w, n in zip(ws, lens)]) / np.sum(lens))


def lost_mid(r, T):
    """Mất đường: lost_retire trung bình trên các checkpoint trong (0, T), như E3 của đợt 12."""
    v = [sv.get("lost_retire", NAN) for c, sv in r["snapshots"].items() if 0 < int(c) < T]
    return nmean(v)


def at_f(r, f0):
    """Final giữ riêng nội suy tuyến tính theo f (phần object đã có record E1) tại f0, trên đoạn f đang tăng."""
    cs = sorted(int(c) for c in r["snapshots"])
    p = [(r["snapshots"][str(c)]["f"], r["snapshots"][str(c)]["final"]) for c in cs]
    for (f1, v1), (f2, v2) in zip(p, p[1:]):
        if f1 <= f0 <= f2 and f2 > f1:
            return v1 + (v2 - v1) * (f0 - f1) / (f2 - f1)
    return NAN


def spearman(x, y):
    """Tương quan hạng Spearman (hạng trung bình khi trùng)."""
    def rank(v):
        v = np.asarray(v, dtype=float)
        o = np.argsort(v, kind="mergesort")
        r = np.empty(len(v))
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[o[j + 1]] == v[o[i]]:
                j += 1
            r[o[i:j + 1]] = (i + j) / 2.0 + 1
            i = j + 1
        return r
    if len(x) < 3:
        return NAN
    a, b = rank(x), rank(y)
    if a.std() == 0 or b.std() == 0:
        return NAN
    return float(np.corrcoef(a, b)[0, 1])


# ----------------------------------------------------------------- nạp file
def files_u(ds, t):
    return {s: d for s in SEEDS_V for d in [jl(f"probeV15U_{ds}_{t}_s{s}.json")] if d}


def files_l(ds, t):
    return {s: d for s in SEEDS_V for d in [jl(f"probeV14F_{ds}_{t}_s{s}_cap16.json")] if d}


def ts_of(F, ds):
    for d in F.values():
        if d.get("bg_finish"):
            return [int(x) for x in d["bg_finish"]]
    return [1500, 3000] if ds == "code" else [400, 800]


def run_of(d, p, T):
    return d["runs"].get(f"z1|PROB|{p}|T{T}" if p in BGP else f"z1|PROB|{p}")


def side(F, T):
    """Một placement, một ô: mỗi đại lượng là {chính sách: {seed: giá trị}}, trên các seed có đủ mọi chính sách."""
    ss = [s for s in sorted(F) if all(run_of(F[s], p, T) for p in NEED)]
    g = lambda s, p: run_of(F[s], p, T)
    q = lambda fn: {p: {s: fn(g(s, p)) for s in ss} for p in NEED}
    return dict(ss=ss, g=g,
                A=q(lambda r: area(r["snapshots"], T)), R=q(lambda r: win_mean(r, T, "rr")), Lm=q(lambda r: lost_mid(r, T)),
                pay=q(lambda r: win_mean(r, T, "fetch")), peer=q(lambda r: win_mean(r, T, "nodes")),
                scan=q(lambda r: area(r["snapshots"], T, "scan")),
                pk=q(lambda r: r["totals"]["bytes_peak_m0"] / max(1e-9, r["totals"]["bytes_t0_m0"])),
                done=q(lambda r: 100.0 * r["totals"]["t_done"] / T if r["totals"].get("t_done", -1) >= 0 else NAN))


def dpair(X, a, b, ss=None):
    """Hiệu ghép theo seed X[a] − X[b] trên các seed ss (mặc định: mọi seed của X[a])."""
    ss = sorted(X[a]) if ss is None else ss
    return [X[a][s] - X[b][s] for s in ss]


def cell_of(ds, t, T):
    U, Lr = side(files_u(ds, t), T), side(files_l(ds, t), T)
    both = [s for s in U["ss"] if s in Lr["ss"]]
    c = dict(ds=ds, t=t, T=T, U=U, L=Lr, both=both, n=len(U["ss"]), nb=len(both))
    c["reb_a"] = dpair(U["A"], DRAIN, "rebuild")
    c["st_a"] = dpair(U["A"], DRAIN, "static")
    c["lbg_a"] = dpair(U["A"], DRAIN, "lazybg")
    c["lbg_r"] = dpair(U["R"], DRAIN, "lazybg")
    c["did_a"] = [x - y for x, y in zip(dpair(Lr["A"], DRAIN, "lazybg", both), dpair(U["A"], DRAIN, "lazybg", both))]
    c["did_r"] = [x - y for x, y in zip(dpair(Lr["R"], DRAIN, "lazybg", both), dpair(U["R"], DRAIN, "lazybg", both))]
    c["lost"] = [Lr["Lm"]["lazybg"][s] - U["Lm"]["lazybg"][s] for s in both]
    c["l_lbg_a"] = dpair(Lr["A"], DRAIN, "lazybg")
    c["l_lbg_r"] = dpair(Lr["R"], DRAIN, "lazybg")
    return c


def cells_of(tags):
    out = []
    for ds in DSETS:
        for t in tags:
            Ts = ts_of(files_u(ds, t) or files_l(ds, t), ds)
            out += [cell_of(ds, t, T) for T in Ts]
    return out


def name_of(c):
    return f"{c['ds']} {c['t']} T={c['T']}"


def read3(v):
    """Cách đọc ba mức của một hiệu drain − lazy+bg."""
    m, lo, hi, n = ci(v)
    if n < 2:
        return "chưa đủ dữ liệu"
    return "dual có lợi" if lo > 0 else ("lazy+bg tốt hơn" if hi < 0 else "lazy+bg gần đủ")


# ----------------------------------------------------------------- H25
def h25(cells):
    head(f"H25. C3 khi migrate tới khi xong trên khoá SRP gốc (--e1-place u, không cap): code 20k và SciFact, 10.000 peer, "
         f"Zipf 1, gỡ E0 khi xong, seed {SEEDS_V}. 'Học' = cùng ô, cùng seed với itq_q+cap16 (pha C của đợt 14). Hiệu ghép "
         f"theo seed, TB [KTC 95%]; diện tích trên [0, T], rerank trên [0, T), mất đường trên các checkpoint trong (0, T).")
    n = len(SEEDS_V)
    for c in cells:
        nm = name_of(c)
        U = c["U"]
        qf = QF_S.get((c["ds"], c["t"]), NAN)
        print(f"\n   {nm:24s} qf dự đoán {qf:.2e}; SRP {c['n']}/{n} seed, học {len(c['L']['ss'])}/{n} seed")
        print(f"      SRP: drain − rebuild {cis(c['reb_a'])}  − static {cis(c['st_a'])}  − lazy+bg: diện tích {cis(c['lbg_a'])} "
              f"rerank {cis(c['lbg_r'])}")
        print(f"      học: drain − lazy+bg: diện tích {cis(c['l_lbg_a'])} rerank {cis(c['l_lbg_r'])}; mất đường của lazy+bg: SRP "
              f"{ms(list(U['Lm']['lazybg'].values()), 5, 2)}%, học {ms(list(c['L']['Lm']['lazybg'].values()), 5, 2)}%")
        crit_lo(f"H25a {nm}", U["ss"], c["reb_a"], 10, n, "SRP, drain − rebuild, diện tích")
        crit_lo(f"H25b {nm}", U["ss"], c["st_a"], 10, n, "SRP, drain − static, diện tích")
        crit_lo(f"H25c {nm}", c["both"], c["did_a"], 0, n, "(drain − lazy+bg) học − SRP, diện tích")
        crit_lo(f"H25d {nm}", c["both"], c["did_r"], 0, n, "(drain − lazy+bg) học − SRP, rerank")
        crit_lo(f"H25e {nm}", c["both"], c["lost"], 0, n, "mất đường của lazy+bg, học − SRP")
        if c["t"] in HIQF:
            crit_hi(f"H25f {nm}", U["ss"], c["lbg_a"], 1, n, "SRP, drain − lazy+bg, diện tích")
        if c["n"]:
            print(f"   ĐỌC ({nm}): trên khoá SRP, drain − lazy+bg: diện tích {read3(c['lbg_a'])}; rerank {read3(c['lbg_r'])}")
    ok = [c for c in cells if c["n"]]
    if ok:
        print(f"\n   Khoảng qua {len(ok)}/{len(cells)} ô có dữ liệu (TB theo seed của mỗi ô), trên khoá SRP; trong ngoặc là cùng "
              f"các ô với placement học (đợt 14):")
        for key, lab, lkey in (("reb_a", "drain − rebuild, diện tích", ("A", "rebuild")), ("st_a", "drain − static, diện tích", ("A", "static")),
                               ("lbg_a", "drain − lazy+bg, diện tích", ("A", "lazybg")), ("lbg_r", "drain − lazy+bg, rerank", ("R", "lazybg"))):
            m = [nmean(c[key]) for c in ok]
            lows = [x for x in (ci(c[key])[1] for c in ok) if x == x]
            his = [x for x in (ci(c[key])[2] for c in ok) if x == x]
            lm = [nmean(dpair(c["L"][lkey[0]], DRAIN, lkey[1])) for c in ok if c["L"]["ss"]]
            print(f"   {lab:28s} {rng(m):18s} (cận dưới nhỏ nhất {min(lows) if lows else NAN:+.2f}; cận dưới > 0 ở "
                  f"{sum(1 for x in lows if x > 0)}/{len(ok)} ô, cận trên < 0 ở {sum(1 for x in his if x < 0)}/{len(ok)} ô)   "
                  f"(học: {rng(lm)})")
        for key, lab in (("did_a", "(drain − lazy+bg) học − SRP, diện tích"), ("did_r", "(drain − lazy+bg) học − SRP, rerank"),
                         ("lost", "mất đường của lazy+bg, học − SRP")):
            m = [nmean(c[key]) for c in ok if c["nb"]]
            lows = [x for x in (ci(c[key])[1] for c in ok if c["nb"]) if x == x]
            print(f"   {lab:40s} {rng(m):18s} (cận dưới nhỏ nhất {min(lows) if lows else NAN:+.2f}; cận dưới > 0 ở "
                  f"{sum(1 for x in lows if x > 0)}/{len(ok)} ô)")
    print()


def summary():
    head("TÓM TẮT ĐÁNH GIÁ ĐĂNG KÝ TRƯỚC (H25)")
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
    n_ok = sum(1 for _, st, _ in VERDICT if st == "ĐẠT")
    print(f"   Tổng: {n_ok} trên {len(VERDICT)} tiêu chí đạt (đăng ký trước: 68 tiêu chí)\n")


# ----------------------------------------------------------------- thăm dò
def e1(cells, title):
    head(title + " Mọi chính sách của mỗi ô trên khoá SRP, cạnh placement học (đợt 14): diện tích [0, T]; rerank, payload, "
         "peer là TB trên các cửa sổ trong [0, T); ứng viên là TB trên các checkpoint trong [0, T] (query giữ riêng); byte "
         "đỉnh so với mức đầu (mã PQ, metadata 0); lượt xong so với T; mất đường trên các checkpoint trong (0, T)")
    for c in cells:
        if not c["n"] and not c["L"]["ss"]:
            continue
        print(f"\n--- {name_of(c)}: SRP n = {c['n']} seed, học n = {len(c['L']['ss'])} seed")
        print(f"   {'chính sách':10s} | {'SRP: diện tích':>14s} {'rerank':>6s} {'payload':>7s} {'peer':>6s} {'ứng viên':>8s} "
              f"{'byte đỉnh':>9s} {'xong/T %':>8s} {'mất %':>6s} | {'học: diện tích':>14s} {'rerank':>6s} {'payload':>7s} "
              f"{'peer':>6s} {'ứng viên':>8s} {'byte đỉnh':>9s} {'xong/T %':>8s} {'mất %':>6s}")
        for p, lab in CPOL:
            row = f"   {lab:10s} |"
            for X in (c["U"], c["L"]):
                if p == "lazy":                      # lazy không thuộc NEED: đọc thẳng từ file
                    rs = [r for r in (X["g"](s, "lazy") for s in X["ss"]) if r]
                    v = dict(A=[area(r["snapshots"], c["T"]) for r in rs], R=[win_mean(r, c["T"], "rr") for r in rs],
                             pay=[win_mean(r, c["T"], "fetch") for r in rs], peer=[win_mean(r, c["T"], "nodes") for r in rs],
                             scan=[area(r["snapshots"], c["T"], "scan") for r in rs],
                             pk=[r["totals"]["bytes_peak_m0"] / max(1e-9, r["totals"]["bytes_t0_m0"]) for r in rs],
                             done=[100.0 * r["totals"]["t_done"] / c["T"] for r in rs if r["totals"].get("t_done", -1) >= 0],
                             Lm=[lost_mid(r, c["T"]) for r in rs])
                else:
                    v = {k: list(X[k][p].values()) for k in ("A", "R", "pay", "peer", "scan", "pk", "done", "Lm")}
                row += (f" {ms(v['A'], 14, 2)} {ms(v['R'], 6, 2)} {ms(v['pay'], 7, 2)} {ms(v['peer'], 6, 0)} {ms(v['scan'], 8, 0)} "
                        f"{ms(v['pk'], 9, 2)} {ms(v['done'], 8, 0)} {ms(v['Lm'], 6, 2)} |")
            print(row)
        if c["n"]:
            U = c["U"]
            print("   hiệu ghép trên SRP, diện tích: " + "; ".join(
                f"{lab} {cis(dpair(U['A'], a, b))}" for lab, a, b in (("drain − bg", DRAIN, "bg"), ("drain − k1", DRAIN, K1),
                                                                    ("drain − full", DRAIN, "full"), ("lazy+bg − rebuild", "lazybg", "rebuild"),
                                                                    ("lazy+bg − static", "lazybg", "static"))))
            print("   hiệu ghép trên SRP, rerank: " + "; ".join(
                f"{lab} {cis(dpair(U['R'], a, b))}" for lab, a, b in (("drain − k1", DRAIN, K1), ("drain − rebuild", DRAIN, "rebuild"),
                                                                    ("drain − static", DRAIN, "static"))))
    print()


def e2(cells):
    head(f"THĂM DÒ E2. Cùng tiến độ: final giữ riêng nội suy theo phần object đã có record E1 (f, gồm cả mẫu S) tại f = "
         f"{', '.join(str(x) for x in FQ)}; drain − lazy+bg ghép theo seed, trên khoá SRP và trên placement học. Phép so này bỏ "
         f"khác biệt về tốc độ migrate giữa hai chính sách.")
    for c in cells:
        if not c["n"]:
            continue
        row = f"   {name_of(c):24s}"
        for lab, X in (("SRP", c["U"]), ("học", c["L"])):
            parts = []
            for f0 in FQ:
                v = [at_f(X["g"](s, DRAIN), f0) - at_f(X["g"](s, "lazybg"), f0) for s in X["ss"]]
                parts.append(f"f={f0:g}: {cis(v, 1)}")
            row += f"  {lab}: " + "  ".join(parts) + " |"
        print(row)
    print()


def e3(tags):
    head("THĂM DÒ E3. Cùng cỡ tốc độ: drain với nền của hạn chót ngắn (T nhỏ) so với lazy+bg với nền của hạn chót dài (T lớn), "
         "cả hai tính trên [0, T lớn]; drain − lazy+bg ghép theo seed. Nền của drain khi đó nhanh gấp đôi.")
    for ds in DSETS:
        for t in tags:
            row = f"   {ds} {t:8s}"
            for lab, F in (("SRP", files_u(ds, t)), ("học", files_l(ds, t))):
                if not F:
                    row += f"  {lab}: chưa có file |"
                    continue
                Ts = ts_of(F, ds)
                Ta, Tb = min(Ts), max(Ts)
                ss = [s for s in sorted(F) if run_of(F[s], DRAIN, Ta) and run_of(F[s], "lazybg", Tb) and run_of(F[s], DRAIN, Tb)]
                da = [area(run_of(F[s], DRAIN, Ta)["snapshots"], Tb) - area(run_of(F[s], "lazybg", Tb)["snapshots"], Tb) for s in ss]
                dr = [win_mean(run_of(F[s], DRAIN, Ta), Tb, "rr") - win_mean(run_of(F[s], "lazybg", Tb), Tb, "rr") for s in ss]
                dn = lambda p, T: nmean([100.0 * run_of(F[s], p, T)["totals"]["t_done"] / Tb for s in ss
                                         if run_of(F[s], p, T)["totals"].get("t_done", -1) >= 0])
                row += (f"  {lab} (n={len(ss)}): drain|T{Ta} − lazy+bg|T{Tb} trên [0, {Tb}]: diện tích {cis(da)} rerank {cis(dr)}; "
                        f"xong ở {dn(DRAIN, Ta):.0f}% so với {dn('lazybg', Tb):.0f}% của T lớn |")
            print(row)
    print()


def e5(cv, cw):
    head("THĂM DÒ E5. Lợi ích của việc giữ đường cũ theo qf dự đoán, trên các cặp (corpus, model) có đủ dữ liệu: TB qua hai "
         "hạn chót của drain − lazy+bg trên khoá SRP (diện tích, rerank) và của hiệu của hiệu (học − SRP)")
    rows = []
    for ds in DSETS:
        for t in VTAGS + WTAGS:
            cs = [c for c in cv + cw if c["ds"] == ds and c["t"] == t and c["n"]]
            if not cs:
                continue
            qf = QF_S.get((ds, t), NAN)
            rows.append((qf, ds, t, nmean([nmean(c["lbg_a"]) for c in cs]), nmean([nmean(c["lbg_r"]) for c in cs]),
                         nmean([nmean(c["did_a"]) for c in cs]), nmean([nmean(c["did_r"]) for c in cs]),
                         nmean([nmean(list(c["U"]["Lm"]["lazybg"].values())) for c in cs]),
                         nmean([nmean(list(c["L"]["Lm"]["lazybg"].values())) for c in cs])))
    rows.sort()
    print(f"   {'corpus':8s} {'model':8s} {'qf dự đoán':>10s} {'nhóm':>5s} {'SRP: diện tích':>14s} {'SRP: rerank':>11s} "
          f"{'HcH diện tích':>13s} {'HcH rerank':>10s} {'mất đường lazy+bg: SRP':>22s} {'học':>6s}")
    for qf, ds, t, a, r, da, dr, lu, ll in rows:
        g = "lớn" if qf >= QF_HI else ("nhỏ" if qf <= QF_LO else "giữa")
        print(f"   {ds:8s} {t:8s} {qf:10.2e} {g:>5s} {a:+14.2f} {r:+11.2f} {da:+13.2f} {dr:+10.2f} {lu:22.2f} {ll:6.2f}")
    if len(rows) >= 3:
        lq = [math.log10(x[0]) for x in rows]
        print(f"\n   Spearman giữa qf dự đoán và: drain − lazy+bg trên SRP, diện tích {spearman(lq, [x[3] for x in rows]):+.3f}; "
              f"rerank {spearman(lq, [x[4] for x in rows]):+.3f}; hiệu của hiệu, diện tích {spearman(lq, [x[5] for x in rows]):+.3f}; "
              f"rerank {spearman(lq, [x[6] for x in rows]):+.3f}; mất đường của lazy+bg trên SRP {spearman(lq, [x[7] for x in rows]):+.3f} "
              f"(n = {len(rows)} cặp)")
    print()


# ----------------------------------------------------------------- tự kiểm
SAME_ARGV = ("dataset", "tag", "seed", "nodes", "nq", "tables", "k_query", "probes", "cbits", "dsub", "kappa", "frac",
             "stream", "zipf", "n_heldout", "R", "window", "checkpoints", "policies", "confirms", "dual_score", "dual_slots",
             "bonus_mult", "bg_finish", "finish_drop", "bytes_meta")


def checks():
    head("Tự kiểm")
    fr = gl("probeVR15*.json")
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
            print(f"   R: {fn}: không có kết quả so với đợt 14")
    if not fr:
        print("   R: chưa có file")
    fu = gl("probeV15U_*.json")
    bad_u = [fn for fn in fu if jl(fn) and (jl(fn)["argv"]["e1_place"] != "u" or jl(fn)["argv"]["e1_cap"] > 0)]
    print(f"   cách đặt record E1: ghi u, không cap ở {len(fu) - len(bad_u)}/{len(fu)} file" + (f"; SAI: {bad_u[:5]}" if bad_u else ""))
    # chỉ khác cách đặt record: tham số còn lại và dòng truy vấn trùng file placement học cùng ô, cùng seed
    n_have = n_pair = n_arg = n_str = n_ns = n_name = 0
    bad = []
    for ds in DSETS:
        for t in VTAGS + WTAGS:
            for s in SEEDS_V:
                fn = f"probeV15U_{ds}_{t}_s{s}.json"
                d = jl(fn)
                if not d:
                    continue
                n_have += 1
                a = d["argv"]
                name_ok = a.get("dataset") == ds and a.get("tag") == t and a.get("seed") == s
                n_name += name_ok
                o = jl(f"probeV14F_{ds}_{t}_s{s}_cap16.json")
                if not o:
                    if not name_ok:
                        bad.append((fn, "tham số không khớp tên file"))
                    continue
                n_pair += 1
                diff = [k for k in SAME_ARGV if a.get(k) != o["argv"].get(k)]
                n_arg += not diff
                k0 = "z1|PROB|static"
                rc = lambda x: x["runs"][k0]["totals"].get("rep_curve", {}).get("n") if k0 in x["runs"] else None
                nr = lambda x: [w.get("n_rep") for w in x["runs"][k0]["windows"]] if k0 in x["runs"] else None
                same_stream = rc(d) is not None and rc(d) == rc(o) and nr(d) == nr(o)
                n_str += bool(same_stream)
                same_ns = d["N"] == o["N"] and d["n_sample"] == o["n_sample"] and sorted(d["runs"]) == sorted(o["runs"])
                n_ns += bool(same_ns)
                if diff or not same_stream or not same_ns or not name_ok:
                    bad.append((fn, diff, bool(same_stream), bool(same_ns), bool(name_ok)))
    print(f"   so với file placement học cùng ô, cùng seed (đợt 14): {n_pair}/{n_have} file có file để so; dataset, model, seed "
          f"trong file khớp tên file ở {n_name}/{n_have}; tham số trùng (trừ cách đặt record) ở {n_arg}/{n_pair}; dòng truy vấn "
          f"trùng (số lượt theo lần xuất hiện, số lượt lặp mỗi cửa sổ) ở {n_str}/{n_pair}; N, |S| và tên các run trùng ở "
          f"{n_ns}/{n_pair}" + (f"; LỆCH: {bad[:3]}" if bad else ""))
    # drain không retire; nhúng lại do truy vấn + do nền = new; rebuild dựng đủ
    n_inf = bad_inf = n_emb = bad_emb = n_rb = bad_rb = 0
    n_post = bad_post = n_pre = bad_pre = 0
    for fn in fu:
        d = jl(fn)
        if not d:
            continue
        fl, stc = d["runs"].get("z1|PROB|full"), d["runs"].get("z1|PROB|static")
        for k, r in d["runs"].items():
            pol, tt = k.split("|")[2], r["totals"]
            if pol == DRAIN:
                n_inf += 1
                bad_inf += tt.get("retired_total", 0) != 0
            if "emb_q" in tt:
                if pol == "rebuild":
                    if tt.get("t_done", -1) >= 0:
                        n_rb += 1
                        bad_rb += abs(tt["emb_bg"] * d["argv"]["stream"] - (d["N"] - d["n_sample"])) > 1e-6
                else:
                    n_emb += 1
                    bad_emb += abs(tt["emb_q"] + tt["emb_bg"] - tt["new"]) > 1e-9
            if "|T" not in k or not fl:
                continue
            td = tt.get("t_done", -1)
            for c, sv in r["snapshots"].items():
                if td >= 0 and int(c) >= td:
                    n_post += 1
                    bad_post += any(abs(sv[m] - fl["snapshots"][c][m]) > 1e-9 for m in ("final", "rr"))
                elif pol == "rebuild" and stc:
                    n_pre += 1
                    bad_pre += any(abs(sv[m] - stc["snapshots"][c][m]) > 1e-9 for m in ("final", "rr"))
    print(f"   drain không retire bản E0 nào trước khi gỡ: {n_inf - bad_inf}/{n_inf} run; nhúng lại do truy vấn + do nền = new: "
          f"{n_emb - bad_emb}/{n_emb} run; rebuild dựng đủ N − |S| bản ở nền: {n_rb - bad_rb}/{n_rb} run")
    print(f"   checkpoint sau lượt xong trùng full {n_post - bad_post}/{n_post}; rebuild trước lượt xong trùng static "
          f"{n_pre - bad_pre}/{n_pre}")
    nv = sum(1 for ds in DSETS for t in VTAGS for s in SEEDS_V if jl(f"probeV15U_{ds}_{t}_s{s}.json"))
    nw = sum(1 for ds in DSETS for t in WTAGS for s in SEEDS_V if jl(f"probeV15U_{ds}_{t}_s{s}.json"))
    nl = sum(1 for ds in DSETS for t in VTAGS + WTAGS for s in SEEDS_V if jl(f"probeV14F_{ds}_{t}_s{s}_cap16.json"))
    print(f"   số file: V {nv}/{len(DSETS) * len(VTAGS) * len(SEEDS_V)}, W {nw}/{len(DSETS) * len(WTAGS) * len(SEEDS_V)}, "
          f"R {len(fr)}/1; file placement học của đợt 14: {nl}/{len(DSETS) * len(VTAGS + WTAGS) * len(SEEDS_V)}")
    print()


def main():
    cv = cells_of(VTAGS)
    h25(cv)
    summary()
    e1(cv, "THĂM DÒ E1.")
    e2(cv)
    e3(VTAGS)
    cw = cells_of(WTAGS)
    e1(cw, "THĂM DÒ E4. Pha W: model mà quy tắc chọn placement học (không chấm).")
    if any(c["n"] for c in cw):
        print("   Pha W, hiệu ghép theo seed trên khoá SRP và hiệu của hiệu (không chấm):")
        for c in cw:
            if c["n"]:
                print(f"   {name_of(c):24s} SRP: drain − lazy+bg diện tích {cis(c['lbg_a'])} rerank {cis(c['lbg_r'])}; drain − rebuild "
                      f"{cis(c['reb_a'])}; học − SRP: diện tích {cis(c['did_a'])} rerank {cis(c['did_r'])}; mất đường {cis(c['lost'])}")
        print()
        e2(cw)
        e3(WTAGS)
    e5(cv, cw)
    checks()


if __name__ == "__main__":
    main()
