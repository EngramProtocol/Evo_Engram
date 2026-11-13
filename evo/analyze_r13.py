#!/usr/bin/env python3
"""
analyze_r13.py  —  tổng hợp đợt 13 (evo/README_round13.md), theo ba nhận xét của thầy về bản thảo C1 đến C3. Đọc ở thư
mục hiện tại (thư mục gốc repo):
  probeQ13_A11_*.json, probeQ13_A12_*.json         pha Q: p, qf theo bộ ước lượng cũ và bộ ước lượng triển khai được
  probeP11_*.json, probeP12_*.json                 đợt 11, 12: Δ_peer của quy tắc qf
  probeV13_code100kfq_bgebase_s<seed>_cap16.json   pha D (drain trên dòng 3.000 lượt của code 100k)
  probeVR13F_*.json                                pha R
  probeL13_n<nodes>_s<seed>.json                   pha L (lookup lặp)
Cách đọc từng phần đã ghi trước trong README_round13.md; script in dòng ĐỌC theo đúng cách đó. Số ghi ở cột "bản thảo"
là số của bản thảo C1 đến C3, để thấy bộ ước lượng cũ được tính lại đúng.
  python3 evo/analyze_r13.py [THƯ_MỤC]        (mặc định thư mục hiện tại)
"""
import glob, json, math, os, re, sys
from collections import defaultdict
import numpy as np

envl = lambda k, d: os.environ.get(k, d).split()
SEEDS_D = [int(x) for x in envl("SEEDS_D", "26 27 28 29 30 31 32 33 34 35")]
OLD12 = envl("SPACES", "bgebase e5large arctic m0 minilm gtebase")      # 12 cặp cũ của đợt 12 (6 không gian × 2 corpus)
NEW12 = envl("NEWTAGS", "e5small gtesmall bgesmall mpnet arcticxs")      # 10 cặp mới của đợt 12
NEW11 = {("code", "minilm"), ("code", "gtebase"), ("scifact", "minilm"), ("scifact", "gtebase"), ("code100kfq", "minilm")}
QF_HI, QF_LO = 8e-4, 2e-4
PAPER = {"r12new": (0.062, 0.063), "r12": (0.079, 0.077), "r11new": (0.106, 0.102)}   # sai số log10 TB của p, qf
TCRIT = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
         11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086}
# Bảng 10 của bản thảo, thêm lazy+keep và drain
TAB10 = [("static", "static"), ("lazy", "lazy"), ("lazyV1", "lazy+delay"), ("lazyVbg", "dual, bg retired"),
         ("lazyVbgD_adp", "dual, no code"), ("lazyVbgD", "dual (k1)"), ("lazyD", "lazy+keep"),
         ("lazyVbgDinf", "dual (drain)"), ("full", "full")]
K1, DRAIN = "lazyVbgD", "lazyVbgDinf"
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


def lg(a, b):
    return abs(math.log10(a / b)) if (a == a and b == b and a > 0 and b > 0) else NAN


def slg(a, b):
    return math.log10(a / b) if (a == a and b == b and a > 0 and b > 0) else NAN


def spearman(a, b):
    ok = [(x, y) for x, y in zip(a, b) if x == x and y == y]
    if len(ok) < 3:
        return NAN
    a, b = np.asarray([x for x, _ in ok], dtype=float), np.asarray([y for _, y in ok], dtype=float)
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])


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


def hits(s):
    return np.asarray([int(c) for c in s], dtype=int) if isinstance(s, str) else np.asarray(s, dtype=int)


def grp(qf):
    if qf != qf:
        return "?"
    return "lớn" if qf >= QF_HI else ("nhỏ" if qf <= QF_LO else "giữa")


def rec_of(g):
    return {"lớn": "SRP", "nhỏ": "học"}.get(g, "chưa")


def better_of(dp):
    return "SRP" if dp > 0 else ("học" if dp == dp else "?")


# ----------------------------------------------------------------- Q: C1 và quy tắc qf
def q_rows():
    by = defaultdict(list)
    for fn in gl("probeQ13_*.json"):
        d = jl(fn)
        m = re.match(r"probeA(\d+)_", (d or {}).get("src", ""))
        if not m:
            continue
        by[(int(m.group(1)), d["dataset"], d["space"])].append(d)
    rows = []
    for (rd, ds, sp), L in sorted(by.items()):
        f = lambda g, k: nmean([x.get(g, {}).get(k, NAN) for x in L])
        seeds = sorted(int(x["seed"]) for x in L)
        r = dict(rd=rd, ds=ds, sp=sp, n=len(L), seeds=seeds, bad=sum(int(x.get("check_bad", 0)) for x in L),
                 nchk=sum(len(x.get("check", {})) for x in L), n_val=sorted({x.get("n_val") for x in L}),
                 nS=sorted({x.get("nS") for x in L}),
                 p_old=f("full", "p_u"), p_S=f("deploy", "p_S_u"), q=f("measured", "coll_meas_u"), mf_S=f("deploy", "pmf_S_u"),
                 qf_old=f("full", "qf_ev_u"), qf_S=f("deploy", "qf_S_val_u"), qf_m=f("measured", "qfrac_meas_u"),
                 qf_Sev=f("decomp", "qf_S_ev_u"), qf_fv=f("decomp", "qf_full_val_u"), cbar=f("deploy", "cbar_S"))
        r["new"] = (rd == 12 and sp in NEW12) or (rd == 11 and (ds, sp) in NEW11)
        P = [d for s in seeds for d in [jl(f"probeP{rd}_{ds}_{sp}_s{s}.json")] if d]
        r["dpeer_s"] = [at_ref(d, "srp", "itq_q+cap16", "srp_c+cap16", "nodes") for d in P]
        r["dpeer"], r["nP"] = nmean(r["dpeer_s"]), len(P)
        rows.append(r)
    return rows


def q_groups(rows):
    return [
        ("đợt 12, 10 cặp mới", "r12new", [r for r in rows if r["rd"] == 12 and r["new"]], 10),
        ("đợt 12, 12 cặp cũ", None, [r for r in rows if r["rd"] == 12 and not r["new"]], 12),
        ("đợt 12, 22 cặp", "r12", [r for r in rows if r["rd"] == 12], 22),
        ("code 100k, 5 cặp (đợt 11)", None, [r for r in rows if r["rd"] == 11 and r["ds"] == "code100kfq"], 5),
        ("27 cặp (22 của đợt 12, 5 code 100k)", None,
         [r for r in rows if r["rd"] == 12 or (r["rd"] == 11 and r["ds"] == "code100kfq")], 27),
        ("đợt 11, 5 cặp mới", "r11new", [r for r in rows if r["rd"] == 11 and r["new"]], 5),
        ("đợt 11, 17 cặp", None, [r for r in rows if r["rd"] == 11], 17),
    ]


def q_c1(rows):
    head("Q1. C1 với bộ ước lượng triển khai được. p: trùng bucket 16 bit giữa hai document; qf: phần corpus cùng bucket với "
         "query. cũ: 200.000 cặp trên toàn corpus, 300 query đánh giá với toàn corpus; S: mọi cặp trong mẫu S, 200 query "
         "validation với S; đo: chiếu thật của hệ thống trên toàn corpus, 300 query đánh giá. TB theo seed, rồi |log10|.")
    print(f"{'đợt':>3s} {'dataset':10s} {'không gian':10s} {'n':>2s} {'p cũ':>9s} {'p S':>9s} {'p đo':>9s} {'|lg| cũ':>7s} "
          f"{'|lg| S':>6s} {'qf cũ':>9s} {'qf S':>9s} {'qf đo':>9s} {'|lg| cũ':>7s} {'|lg| S':>6s}   tách qf: "
          f"{'q.đánh giá×S':>12s} {'q.val×toàn':>10s}")
    for r in sorted(rows, key=lambda r: (r["rd"], r["ds"], r["sp"])):
        print(f"{r['rd']:3d} {r['ds']:10s} {r['sp']:10s} {r['n']:2d} {r['p_old']:9.2e} {r['p_S']:9.2e} {r['q']:9.2e} "
              f"{lg(r['p_old'], r['q']):7.3f} {lg(r['p_S'], r['q']):6.3f} {r['qf_old']:9.2e} {r['qf_S']:9.2e} "
              f"{r['qf_m']:9.2e} {lg(r['qf_old'], r['qf_m']):7.3f} {lg(r['qf_S'], r['qf_m']):6.3f}   "
              f"{r['qf_Sev']:12.2e} {r['qf_fv']:10.2e}{'  mới' if r['new'] else ''}")
    print()
    print(f"   {'nhóm':38s} {'số cặp':>7s} {'p cũ':>6s} {'p S':>6s} {'TT S':>6s} {'qf cũ':>6s} {'qf S':>6s}  "
          f"{'lệch dấu p S':>12s} {'lệch dấu qf S':>13s} {'lớn nhất p S / qf S':>20s}  bản thảo (p, qf)")
    out = {}
    for name, key, R, nexp in q_groups(rows):
        e = lambda a, b: nmean([lg(r[a], r[b]) for r in R])
        sb = lambda a, b: nmean([slg(r[a], r[b]) for r in R])
        mx = lambda a, b: max([lg(r[a], r[b]) for r in R], default=NAN)
        out[name] = dict(n=len(R), p_old=e("p_old", "q"), p_S=e("p_S", "q"), qf_old=e("qf_old", "qf_m"), qf_S=e("qf_S", "qf_m"))
        pap = PAPER.get(key)
        print(f"   {name:38s} {len(R):3d}/{nexp:<3d} {e('p_old', 'q'):6.3f} {e('p_S', 'q'):6.3f} {e('mf_S', 'q'):6.3f} "
              f"{e('qf_old', 'qf_m'):6.3f} {e('qf_S', 'qf_m'):6.3f}  {sb('p_S', 'q'):+12.3f} {sb('qf_S', 'qf_m'):+13.3f} "
              f"{mx('p_S', 'q'):9.3f} / {mx('qf_S', 'qf_m'):.3f}   "
              + (f"{pap[0]:.3f}, {pap[1]:.3f}" if pap else ""))
    print("   (TT S: dạng trường trung bình (1 − arccos(cbar_S)/π)^16 với cosine TB trên S; lệch dấu: TB log10(dự đoán/đo), "
          "dương là đoán cao)")
    rS = [r for r in rows if r["rd"] == 12]
    print(f"   Spearman trên {len(rS)} cặp đợt 12: p S với p đo {spearman([r['p_S'] for r in rS], [r['q'] for r in rS]):+.3f}, "
          f"qf S với qf đo {spearman([r['qf_S'] for r in rS], [r['qf_m'] for r in rS]):+.3f}")
    new = [r for r in rows if r["rd"] == 12 and r["new"]]
    full = len(new) == 10
    eS = out["đợt 12, 10 cặp mới"]
    if not full:
        print(f"   ĐỌC (C1): thiếu cặp mới của đợt 12 ({len(new)}/10), chưa đọc được.")
    else:
        ok = eS["p_S"] <= 0.2 and eS["qf_S"] <= 0.2
        print(f"   ĐỌC (C1): trên 10 cặp mới, sai số log10 TB với bộ ước lượng triển khai được là {eS['p_S']:.3f} (p) và "
              f"{eS['qf_S']:.3f} (qf), so với {eS['p_old']:.3f} và {eS['qf_old']:.3f} của bộ ước lượng cũ; "
              + ("cả hai không quá ngưỡng 0,2 của H21: bản thảo dùng bộ ước lượng này làm cách tính chính ở Mục 4.3, "
                 "báo sai số mới ở Mục 6.1 và Bảng S1, và ghi rằng số cũ dùng query đánh giá."
                 if ok else "VƯỢT ngưỡng 0,2 của H21: bản thảo báo cả hai, nói rõ phần lệch đến từ mẫu S hay từ tập query "
                 "(cột tách), và coi số cũ là kết quả có rò rỉ."))
    print()
    return out


def q_h19(rows):
    R = [r for r in rows if r["rd"] == 12]
    head(f"Q2. H19 chấm lại với qf triển khai được (qf S), 22 cặp đợt 12. Δ_peer = F_srp − F_itq_q+cap16 tại số peer của "
         f"srp_c+cap16 ở (5,8) (probeP12, không đổi); nhóm lớn: qf >= {QF_HI:g}, nhỏ: qf <= {QF_LO:g}")
    print(f"   {'dataset':8s} {'không gian':10s} {'qf cũ':>9s} {'qf S':>9s} {'qf đo':>9s} {'nhóm cũ':>7s} {'nhóm S':>6s} "
          f"{'Δ_peer':>7s}  khuyến nghị S / tốt hơn   theo seed")
    for r in sorted(R, key=lambda r: r["qf_S"]):
        go, gs = grp(r["qf_old"]), grp(r["qf_S"])
        print(f"   {r['ds']:8s} {r['sp']:10s} {r['qf_old']:9.2e} {r['qf_S']:9.2e} {r['qf_m']:9.2e} {go:>7s} {gs:>6s} "
              f"{r['dpeer']:+7.2f}  {rec_of(gs):5s} / {better_of(r['dpeer']):4s}   {[round(x, 2) for x in r['dpeer_s']]}"
              f"{'  mới' if r['new'] else ''}{'  ĐỔI NHÓM' if go != gs else ''}")
    new = [r for r in R if r["new"]]
    res = {}
    for lab, key in (("cũ (bản thảo)", "qf_old"), ("triển khai được", "qf_S")):
        hi = [r for r in new if grp(r[key]) == "lớn"]
        lo = [r for r in new if grp(r[key]) == "nhỏ"]
        mid = [r for r in new if grp(r[key]) not in ("lớn", "nhỏ")]
        okA = bool(hi) and all(r["dpeer"] > 0 for r in hi)
        okB = bool(lo) and all(r["dpeer"] < 1 for r in lo)
        rho_n = spearman([r[key] for r in new], [r["dpeer"] for r in new])
        rho_a = spearman([r[key] for r in R], [r["dpeer"] for r in R])
        right = lambda S: sum(1 for r in S if rec_of(grp(r[key])) == better_of(r["dpeer"]))
        dec = lambda S: sum(1 for r in S if grp(r[key]) in ("lớn", "nhỏ"))
        res[key] = dict(okA=okA, okB=okB, rho_n=rho_n, rho_a=rho_a, mid=len(mid))
        print(f"   qf {lab:16s}: H19a {'ĐẠT' if okA else 'KHÔNG ĐẠT'} ({len(hi)} cặp lớn, Δ_peer nhỏ nhất "
              f"{min([r['dpeer'] for r in hi], default=NAN):+.2f}); H19b {'ĐẠT' if okB else 'KHÔNG ĐẠT'} ({len(lo)} cặp nhỏ, "
              f"Δ_peer lớn nhất {max([r['dpeer'] for r in lo], default=NAN):+.2f}); H19c Spearman {rho_n:+.3f} "
              f"({'ĐẠT' if rho_n >= 0.6 else 'KHÔNG ĐẠT'}); H19d Spearman {rho_a:+.3f} trên {len(R)} cặp "
              f"({'ĐẠT' if rho_a >= 0.8 and len(R) == 22 else 'KHÔNG ĐẠT'}); khuyến nghị đúng {right(new)}/{dec(new)} cặp mới, "
              f"{right(R)}/{dec(R)} cặp; {len(mid)} cặp mới giữa hai ngưỡng")
    for lab, key in (("p cũ", "p_old"), ("p S", "p_S")):
        right = sum(1 for r in R if rec_of(grp(r[key])) == better_of(r["dpeer"]))
        dec = sum(1 for r in R if grp(r[key]) in ("lớn", "nhỏ"))
        print(f"   so sánh, quy tắc theo {lab} với cùng ngưỡng: khuyến nghị đúng {right}/{dec} cặp; Spearman với Δ_peer "
              f"{spearman([r[key] for r in R], [r['dpeer'] for r in R]):+.3f} trên {len(R)} cặp")
    ch_new = [r for r in new if grp(r["qf_S"]) != grp(r["qf_old"])]
    ch_all = [r for r in R if grp(r["qf_S"]) != grp(r["qf_old"])]
    if len(new) < 10 or any(r["nP"] == 0 for r in new):
        print(f"   ĐỌC (H19): thiếu dữ liệu ({len(new)}/10 cặp mới có probeQ13; cặp thiếu probeP12: "
              f"{[r['ds'] + ' ' + r['sp'] for r in new if r['nP'] == 0]}), chưa đọc được.")
    elif not ch_new:
        print(f"   ĐỌC (H19): cả 10 cặp mới giữ nguyên nhóm khi dùng qf triển khai được ({len(ch_all)} cặp đổi nhóm trên "
              f"22 cặp). Bản thảo ghi: chấm lại sau (post hoc) bằng bộ ước lượng chỉ dùng S và query validation cho cùng "
              f"quyết định ở cả 10 cặp; kết quả kiểm trước của H19 giữ nguyên.")
    else:
        print(f"   ĐỌC (H19): {len(ch_new)} cặp mới ĐỔI NHÓM ({', '.join(r['ds'] + ' ' + r['sp'] for r in ch_new)}). "
              f"Quy tắc qf được ghi là thăm dò; bản thảo báo số cặp đổi và kết quả với qf triển khai được.")
    print()
    # thăm dò: các cặp của đợt 11 (gồm code 100k ở 50.000 peer), probeP11
    R11 = [r for r in rows if r["rd"] == 11]
    if R11:
        head("Q3. THĂM DÒ. Như Q2 cho 17 cặp của đợt 11 (seed 26 đến 28; code 100k ở 50.000 peer), Δ_peer từ probeP11. Quy tắc "
             "được đặt ra sau khi xem các cặp này, nên đây không phải kiểm trước.")
        for r in sorted(R11, key=lambda r: r["qf_S"]):
            go, gs = grp(r["qf_old"]), grp(r["qf_S"])
            print(f"   {r['ds']:10s} {r['sp']:10s} qf cũ {r['qf_old']:9.2e} qf S {r['qf_S']:9.2e} qf đo {r['qf_m']:9.2e} "
                  f"nhóm {go:>4s} -> {gs:>4s}  Δ_peer {r['dpeer']:+7.2f} (n={r['nP']})  {rec_of(gs):5s} / "
                  f"{better_of(r['dpeer']):4s}{'  ĐỔI NHÓM' if go != gs else ''}")
        for lab, key in (("qf cũ", "qf_old"), ("qf S", "qf_S")):
            right = sum(1 for r in R11 if rec_of(grp(r[key])) == better_of(r["dpeer"]))
            dec = sum(1 for r in R11 if grp(r[key]) in ("lớn", "nhỏ"))
            print(f"   {lab}: khuyến nghị đúng {right}/{dec} cặp; Spearman với Δ_peer "
                  f"{spearman([r[key] for r in R11], [r['dpeer'] for r in R11]):+.3f} trên {len(R11)} cặp")
        print()
    return res


# ----------------------------------------------------------------- D: drain trên dòng 3.000 lượt của code 100k
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


def d_drain():
    F0 = {s: d for s in SEEDS_D for d in [jl(f"probeV13_code100kfq_bgebase_s{s}_cap16.json")] if d}
    F = {s: d for s, d in F0.items() if not (d.get("check_prev") or {}).get("bad")}   # tự kiểm LỆCH: không dùng
    head(f"D. Drain trên dòng 3.000 lượt của code 100k (bge-base, itq_q+cap16, Zipf 1, 50.000 peer), seed có file: "
         f"{sorted(F)} ({len(F)}/{len(SEEDS_D)}). Cột như Bảng 10 của bản thảo: giữ riêng = final của query giữ riêng ở "
         f"checkpoint cuối; dòng = rerank TB trên dòng; tải = payload trên đường truy vấn mỗi lượt; nhúng = do truy vấn + do "
         f"nền mỗi lượt; dual, record: % ở cuối, % đỉnh; byte: đỉnh mỗi object và bảng, mã PQ (thêm 64 byte metadata); "
         f"peer, ứng viên mỗi truy vấn; mất: % top-5 thật mất đường do retire ở cuối; xấu hơn: % query giữ riêng có rerank "
         f"top-5 kém static ở cuối")
    if len(F) < len(F0):
        print(f"   bỏ seed {sorted(set(F0) - set(F))}: tự kiểm với đợt 11 LỆCH")
    if not F:
        print("   chưa có file\n")
        return
    run = lambda p: {s: d["runs"][f"z1|PROB|{p}"] for s, d in F.items() if f"z1|PROB|{p}" in d["runs"]}
    st = run("static")
    print(f"   {'chính sách':16s} {'n':>2s} {'giữ riêng':>9s} {'dòng':>6s} {'tải':>5s} {'nhúng q + nền':>13s} {'dual':>5s} "
          f"{'record':>6s} {'byte':>5s} {'(+64)':>6s} {'peer':>6s} {'ứng viên':>8s} {'dual E0/q':>9s} {'mất':>5s} "
          f"{'xấu hơn':>7s} {'nền/lượt':>8s}")
    for p, lab in TAB10:
        X = run(p)
        if not X:
            print(f"   {lab:16s}  0  (không có run {p})")
            continue
        T = lambda k: [x["totals"].get(k, NAN) for x in X.values()]
        E = lambda k: [snap_end(x).get(k, NAN) for x in X.values()]
        print(f"   {lab:16s} {len(X):2d} {ms(E('final'), 9)} {ms(T('rr'))} {ms(T('fetch'), 5)} "
              f"{ms(T('emb_q'), 5)} + {ms(T('emb_bg'), 5)} {ms(T('dual_end'), 5)} {ms(T('store_peak'), 6)} "
              f"{ms(T('bytes_peak_m0'), 5, 0)} {ms(T('bytes_peak_m64'), 6, 0)} {ms(T('nodes'), 6, 0)} {ms(T('scan'), 8, 0)} "
              f"{ms(T('dual_from_e0'), 9)} {ms(E('lost_retire'), 5, 2)} {flips(X, st):7.1f} {ms(T('bg_rate'), 8, 2)}")
    k1, dr, lz, lk, fu = run(K1), run(DRAIN), run("lazy"), run("lazyD"), run("full")
    print("\n   Hiệu ghép theo seed, TB [khoảng tin cậy 95%]:")
    for lab, ref in (("drain − k1", k1), ("drain − lazy", lz), ("drain − static", st), ("drain − lazy+keep", lk),
                     ("drain − full", fu)):
        ss = [s for s in dr if s in ref]
        dE = lambda k: [snap_end(dr[s]).get(k, NAN) - snap_end(ref[s]).get(k, NAN) for s in ss]
        dT = lambda k: [dr[s]["totals"].get(k, NAN) - ref[s]["totals"].get(k, NAN) for s in ss]
        print(f"   {lab:18s} n={len(ss):2d}  giữ riêng {cis(dE('final'))}  dòng {cis(dT('rr'))}  tải {cis(dT('fetch'), 2)}  "
              f"record đỉnh {cis(dT('store_peak'))}  byte đỉnh {cis(dT('bytes_peak_m0'), 0)}")
    if dr and k1:
        print(f"   k1 xấu hơn drain ở cuối: rerank {flips(k1, dr):.1f}% query giữ riêng, final {flips(k1, dr, 'fin_hits'):.1f}%; "
              f"drain xấu hơn k1: rerank {flips(dr, k1):.1f}%, final {flips(dr, k1, 'fin_hits'):.1f}%")
        tot = lambda X: [x["totals"]["emb_q"] + x["totals"]["emb_bg"] for x in X.values()]
        print(f"   ngân sách nhúng lại mỗi lượt (do truy vấn + do nền): lazy {ms(tot(lz), 5, 2)}, k1 {ms(tot(k1), 5, 2)}, "
              f"drain {ms(tot(dr), 5, 2)}; retire của drain trên cả dòng: "
              f"{sum(x['totals'].get('retired_total', 0) for x in dr.values())} (phải là 0)")
        print(f"   ĐỌC (C3): Bảng 10 thêm dòng drain (và lazy+keep) từ {len(dr)} seed, giữ dòng k1; bản thảo báo TB và khoảng "
              f"tin cậy của hiệu drain − k1 ở trên, và đoạn đầu Mục 6.4 nói chi phí của drain.")
    print()


# ----------------------------------------------------------------- L: lookup lặp
def l_lookup():
    """P(r) = xác suất lookup lặp tìm thấy peer hạng r (theo XOR) trong K peer gần khoá nhất, TB các seed (gộp lookup).
    Độ chênh: hạng 1 trừ hạng thấp nhất (mọi r), và hạng 1 trừ TB 5 hạng xa nhất (16 .. 20 với K = 20). Record tràn vào peer
    có chỗ đầu tiên theo thứ tự XOR, nên phần lớn nằm ở hạng gần; dùng 5 hạng xa nhất vẫn là chặn trên, mà không bị nhiễu
    của phép lấy min trên 19 hạng kéo xuống."""
    by = defaultdict(list)
    for fn in gl("probeL13_n*_s*.json"):
        d = jl(fn)
        if d:
            by[int(d["n_nodes"])].append(d)
    head("L. Lookup lặp (alpha 3, K 20, tối đa 20 vòng, STOP_RULE stable, FRONTIER_SCOPE all) tới khoá ngẫu nhiên: phần K peer "
         "gần khoá nhất (XOR) mà lookup tìm được, và xác suất tìm thấy peer theo hạng XOR")
    if not by:
        print("   chưa có file\n")
        return {}
    res = {}
    for n in sorted(by):
        D = by[n]
        K = len(D[0]["p_rank"])
        nl = sum(int(d["argv"]["lookups"]) for d in D)
        pr = np.array([d["p_rank"] for d in D], dtype=float)
        w = np.array([int(d["argv"]["lookups"]) for d in D], dtype=float)
        m = (pr * w[:, None]).sum(0) / w.sum()                     # gộp mọi lookup của các seed
        far = slice(max(1, K - 5), K)
        drop_min = float(m[0] - m[1:].min()) if K > 1 else NAN
        drop_far = float(m[0] - m[far].mean()) if K > 1 else NAN
        res[n] = dict(p1=float(m[0]), drop_min=drop_min, drop_far=drop_far, share=nmean([d["share_mean"] for d in D]))
        rng = lambda k: f"{100 * nmean([d[k] for d in D]):5.1f}% [{100 * min(d[k] for d in D):.1f}, {100 * max(d[k] for d in D):.1f}]"
        print(f"   {n:,} peer, {len(D)} seed, {nl} lookup: tìm được {rng('share_mean')} của {K} peer gần nhất; đủ {K}: "
              f"{rng('share_all')}; không peer nào: {rng('share_none')}; một phần: {rng('share_part')} (khi đó TB "
              f"{100 * nmean([d['share_mean_part'] for d in D if d.get('share_mean_part') is not None]):.1f}%); bước TB "
              f"{nmean([d['hops_mean'] for d in D]):.2f}, RPC TB {nmean([d['rpcs_mean'] for d in D]):.1f}")
        print("      P(tìm thấy | hạng r), r = 1 .. %d: %s" % (K, " ".join(f"{100 * x:.1f}" for x in m)))
        pa = [d["p_rank_given_any"] for d in D if d.get("p_rank_given_any")]
        if pa:
            print("      như trên, chỉ lookup tìm được ít nhất một peer: %s" %
                  " ".join(f"{100 * x:.1f}" for x in np.mean(np.array(pa, dtype=float), 0)))
        per_seed = [float(x[0] - x[far].mean()) for x in pr]
        print(f"      hạng 1 trừ hạng thấp nhất: {100 * drop_min:+.2f} điểm; hạng 1 trừ TB hạng {far.start + 1} .. {K}: "
              f"{100 * drop_far:+.2f} điểm (theo seed: {cis([100 * x for x in per_seed], 2)}); TB hạng 2 .. {K}: "
              f"{100 * float(m[1:].mean()):.1f}% (hạng 1: {100 * float(m[0]):.1f}%)")
    # chặn trên phần record mất thêm do giới hạn tải: record dời tới peer hạng r > 1 mất thêm P(1) − P(r)
    rows = []
    for fn in gl("probeP1[12]_*.json"):
        d = jl(fn)
        v = (d or {}).get("variants", {}).get("itq_q+cap16")
        if not v or "cap" not in v:
            continue
        n = int(d["argv"]["nodes"])
        if n in res:
            rows.append((fn, n, float(v["cap"].get("moved_frac_L5", NAN))))
    if rows:
        bf = [100 * mv * max(0.0, res[n]["drop_far"]) for _, n, mv in rows]
        bm = [100 * mv * max(0.0, res[n]["drop_min"]) for _, n, mv in rows]
        i, j = int(np.nanargmax(bf)), int(np.nanargmax(bm))
        mv_all = [100 * mv for _, _, mv in rows]
        print(f"   Record bị dời vì giới hạn tải (itq_q+cap16, {len(rows)} file probeP11/12 cùng số peer): TB {nmean(mv_all):.2f}%, "
              f"lớn nhất {max(mv_all):.2f}%. Phần record mất thêm, chặn trên = phần bị dời × (P hạng 1 − TB 5 hạng xa nhất): "
              f"TB {nmean(bf):.4f}%, lớn nhất {bf[i]:.4f}% ({rows[i][0]}); nếu dùng hạng thấp nhất: lớn nhất {bm[j]:.4f}% "
              f"({rows[j][0]})")
        flat = all(res[n]["drop_min"] <= 0.03 for n in res)
        drops = ", ".join(f"{n:,} peer: {100 * res[n]['drop_min']:+.2f}" for n in sorted(res))
        if flat and bf[i] < 0.1:
            print(f"   ĐỌC (C2): P(r) chênh với P(1) không quá 3 điểm ở mọi hạng ({drops}) và chặn trên {bf[i]:.4f}% < 0,1% "
                  f"record: bản thảo sửa câu ở Mục 4.4 (lookup lặp tìm peer ở hạng xa với gần cùng xác suất như peer gần nhất, "
                  f"nên giới hạn tải không làm record tràn khó tìm hơn đáng kể); bảng P(r) vào Supplementary.")
        else:
            print(f"   ĐỌC (C2): P(r) chênh quá 3 điểm ({drops}) hoặc chặn trên {bf[i]:.4f}% không dưới 0,1% record: bản thảo "
                  f"báo phần mất thêm như một chi phí của giới hạn tải.")
    else:
        print(f"   không có file probeP11/12 (itq_q+cap16) cùng số peer với pha L ({sorted(res)}) để tính chặn trên")
    print()
    return res


# ----------------------------------------------------------------- tự kiểm
def checks(rows):
    head("Tự kiểm")
    files = gl("probeQ13_*.json")
    bad = [(fn, jl(fn).get("check_bad")) for fn in files if jl(fn) and jl(fn).get("check_bad")]
    nchk = sum(len(jl(fn).get("check", {})) for fn in files if jl(fn))
    print(f"   Q: {len(files)} file (đợt 11: 51, đợt 12: 66); dựng lại bộ ước lượng cũ: {nchk} số so với probeA, "
          f"{('KHỚP' if nchk else 'chưa so') if not bad else str(len(bad)) + ' file LỆCH ' + str(bad[:5])}")
    nval = sorted({v for r in rows for v in r["n_val"]})
    print(f"   Q: số query validation mỗi file {nval} (cần 200); số cặp đủ seed: "
          f"{sum(1 for r in rows if r['n'] == 3)}/{len(rows)}; cặp thiếu probeP: "
          f"{[r['ds'] + ' ' + r['sp'] + ' đợt ' + str(r['rd']) for r in rows if r['nP'] < r['n']]}")
    for fn in gl("probeVR13*.json"):
        d = jl(fn)
        c = (d or {}).get("check_prev")
        if c:
            old = jl(c["file"])
            miss = [k for k in (old or {}).get("runs", {}) if k not in d["runs"]]
            print(f"   R: {fn}: {c['n']} giá trị so với {c['file']}, "
                  f"{'KHỚP' if c['bad'] == 0 and c['n'] > 0 else str(c['bad']) + ' LỆCH ' + str(c.get('diffs', [])[:3])}; "
                  f"đủ {len((old or {}).get('runs', {})) - len(miss)}/{len((old or {}).get('runs', {}))} run của lượt cũ")
    if not gl("probeVR13*.json"):
        print("   R: chưa có file")
    n_ok = n_tot = nv = 0
    for s in SEEDS_D:
        d = jl(f"probeV13_code100kfq_bgebase_s{s}_cap16.json")
        if not d:
            continue
        c = d.get("check_prev")
        if not c:
            print(f"   D seed {s}: không so được với đợt 11")
            continue
        n_tot += 1; nv += c["n"]
        if c["bad"] == 0 and c["n"] > 0:
            n_ok += 1
        else:
            print(f"   D seed {s}: {c['bad']} LỆCH trên {c['n']} giá trị, ví dụ {c.get('diffs', [])[:3]}")
        c10 = d.get("check_10")
        if c10 and c10.get("bad"):
            print(f"   D seed {s}: placement so với probeP11 LỆCH {c10.get('diffs')}")
    print(f"   D: {n_ok}/{n_tot} file KHỚP từng số với đợt 11 ở các run trùng tên ({nv} giá trị)")
    print()


def main():
    rows = q_rows()
    q_c1(rows)
    q_h19(rows)
    d_drain()
    l_lookup()
    checks(rows)


if __name__ == "__main__":
    main()
