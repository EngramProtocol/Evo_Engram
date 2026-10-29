#!/usr/bin/env python3
"""
analyze_r9.py  —  đánh giá đợt 9 theo đúng evo/PREREG_round9.md (H6 đến H8), rồi in phần thăm dò:
churn và lỗi peer (pha A), mapkeep không churn (pha A), placement itq<k> (pha D), chẩn đoán điểm nóng ITQ (pha E) và tự kiểm.
Đọc ở thư mục hiện tại (thư mục gốc repo), cùng kết quả đợt 8 (probeV8_*, probeP_*):
  probeV9_<ds>_<tag>_s<seed>_itq_q.json          (pha B, ds = code, scifact; SEEDS_B)
  probeV9X_code100kfq_<tag>_s<seed>_itq_q.json   (pha A, SEEDS_C): run không churn 'z<z>|PROB|<p>' (static, mapkeep)
                                                  và, với SEEDS_A, run churn 'z1|PROB|<p>|<cfg>' (cfg = ch, fail)
  probeP9_code100kfq_<space>_s<seed>.json         (pha D, SEEDS_D)
  diagITQ_code100kfq_<space>_s<seed>.json         (pha E, SEEDS_D)
  probeVR9_*.json, probeVR9noop_*.json            (pha R)
"""
import glob, json, math, os
from collections import defaultdict
import numpy as np

env = lambda k, d: [int(x) for x in os.environ.get(k, d).split()]
SEEDS_A = env("SEEDS_A", "6 7 8 9 10")
SEEDS_B = env("SEEDS_B", "6 7 8 9 10 11 12 13 14 15")
SEEDS_C = env("SEEDS_C", "6 7 8 9 10 11 12 13 14 15")
SEEDS_D = env("SEEDS_D", "6 7 8")
TAGS = os.environ.get("TAGS", "bgebase e5large arctic").split()
SPACES = os.environ.get("SPACES", "bgebase e5large arctic m0").split()
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


def verdict(name, ok, detail):
    VERDICT.append((name, ok, detail))
    print(f"   {'ĐẠT ' if ok else 'KHÔNG ĐẠT'}  {name}: {detail}")


def snap_end(r):
    return r["snapshots"][str(max(int(k) for k in r["snapshots"]))]


def snap_at(r, t):
    return r["snapshots"].get(str(t))


def runs_of(pattern, seeds, cfg=None):
    """seed -> runs. cfg None: chỉ run không có hậu tố cấu hình; cfg 'ch': run 'z|PROB|p|ch' đổi tên thành 'z|PROB|p'."""
    out = {}
    for s in seeds:
        d = jl(pattern.format(s=s))
        if not d:
            continue
        if cfg is None:
            r = {k: v for k, v in d["runs"].items() if k.count("|") == 2}
        else:
            r = {k[:-len(cfg) - 1]: v for k, v in d["runs"].items() if k.endswith("|" + cfg) and k.count("|") == 3}
        if r:
            out[s] = r
    return out


# ----------------------------------------------------------------- H6 đến H8 (pha B)
def h678():
    print(LINE)
    print(f"H6 đến H8. C3 trên code 20k và SciFact, placement itq_q, Zipf 1, seed {SEEDS_B} (KTC 95% theo t, ghép cặp)")
    print(LINE)
    for ds in ("code", "scifact"):
        for t in TAGS:
            R = runs_of(f"probeV9_{ds}_{t}_s{{s}}_itq_q.json", SEEDS_B)
            ss = sorted(s for s in R if all(f"z1|PROB|{p}" in R[s] for p in ("static", "lazy", "lazyVbgD")))
            lab = f"{ds} {t}"
            if len(ss) < len(SEEDS_B):
                print(f"*** {lab}: chỉ có {len(ss)} trên {len(SEEDS_B)} seed")
            if not ss:
                continue
            g = lambda s, p: R[s][f"z1|PROB|{p}"]
            d6 = [snap_end(g(s, "lazyVbgD"))["final"] - snap_end(g(s, "lazy"))["final"] for s in ss]
            d7a = [snap_end(g(s, "lazyVbgD"))["final"] - snap_end(g(s, "static"))["final"] for s in ss]
            d7b = [g(s, "lazy")["totals"]["rr"] - g(s, "static")["totals"]["rr"] for s in ss]
            fr = [g(s, "lazyVbgD")["totals"]["fetch"] / max(1e-9, g(s, "lazy")["totals"]["fetch"]) for s in ss]
            dual = [g(s, "lazyVbgD")["totals"]["dual_end"] for s in ss]
            fe = [100 * g(s, "lazy")["totals"]["f_end"] for s in ss]
            m6, lo6, hi6, n6 = ci(d6); m7a = ci(d7a); m7b, lo7b, hi7b, _ = ci(d7b)
            print(f"\n   --- {lab} (n = {n6} seed); f cuối của lazy TB {np.mean(fe):.1f}%, dual cuối của lazyVbgD "
                  f"TB {np.mean(dual):.1f}% (thăm dò)")
            print(f"   lazyVbgD − lazy, final giữ riêng: TB {m6:+.2f}, KTC [{lo6:+.2f}, {hi6:+.2f}], dương ở "
                  f"{sum(x > 0 for x in d6)}/{len(d6)} seed")
            print(f"   lazyVbgD − static, final giữ riêng: TB {m7a[0]:+.2f}, KTC [{m7a[1]:+.2f}, {m7a[2]:+.2f}]")
            print(f"   lazy − static, rerank trên dòng: TB {m7b:+.2f}, KTC [{lo7b:+.2f}, {hi7b:+.2f}]")
            print(f"   payload lazyVbgD / lazy: TB {np.mean(fr):.3f}")
            full = n6 == len(SEEDS_B)
            verdict(f"H6 {lab}", full and lo6 > 0, f"cận dưới KTC {lo6:+.2f} (cần > 0)")
            verdict(f"H7a {lab}", full and m7a[0] >= 3, f"TB {m7a[0]:+.2f} (cần >= +3)")
            verdict(f"H7b {lab}", full and hi7b < 0, f"cận trên KTC {hi7b:+.2f} (cần < 0)")
            verdict(f"H8 {lab}", full and np.mean(fr) <= 1 / 3, f"payload {np.mean(fr):.3f} (cần <= 0,333)")
    print()


# ----------------------------------------------------------------- bảng chính sách dùng chung
POL = ["static", "lazy", "bg", "lazyV1", "bgV1", "lazyVbg", "lazyVbgD", "full", "mapall", "mapkeep"]
PAIRS = (("lazyVbgD", "lazy"), ("lazyVbgD", "static"), ("lazyVbgD", "mapkeep"), ("mapkeep", "mapall"),
         ("mapkeep", "static"), ("full", "lazyVbgD"), ("lazy", "static"))


def policy_table(R, z, pols=POL, pairs=PAIRS, extra=False):
    print(f"{'chính sách':10s} {'dòng final':>11s} {'dòng rr':>11s} {'dòng gold':>11s} {'giữ final':>11s} {'giữ rr':>11s} "
          f"{'giữ gold':>11s} {'tải/q':>6s} {'mới/q':>6s} {'f cuối':>7s} {'dual':>6s} {'peer/q':>7s} {'chấm/q':>8s}"
          + (f" {'mất đường':>9s} {'sửa/q':>6s} {'k-a/q':>6s}" if extra else ""))
    for p in pols:
        xs = [R[s][f"z{z}|PROB|{p}"] for s in R if f"z{z}|PROB|{p}" in R[s]]
        if not xs:
            continue
        T_ = lambda m: ms([x["totals"].get(m) for x in xs])
        H_ = lambda m: ms([snap_end(x).get(m) for x in xs])
        line = (f"{p:10s} {T_('final')} {T_('rr')} {T_('gold_rr')} {H_('final')} {H_('rr')} {H_('gold_rr')} "
                f"{np.mean([x['totals']['fetch'] for x in xs]):6.1f} {np.mean([x['totals']['new'] for x in xs]):6.2f} "
                f"{100 * np.mean([x['totals']['f_end'] for x in xs]):6.1f}% {np.mean([x['totals']['dual_end'] for x in xs]):5.1f}% "
                f"{np.mean([x['totals']['nodes'] for x in xs]):7.0f} {np.mean([x['totals'].get('scan', float('nan')) for x in xs]):8.0f}")
        if extra:
            line += (f" {np.mean([x['totals'].get('lost_obj_end', float('nan')) for x in xs]):8.2f}%"
                     f" {np.mean([x['totals'].get('repair_w', float('nan')) for x in xs]):6.1f}"
                     f" {np.mean([x['totals'].get('keepalive', float('nan')) for x in xs]):6.0f}")
        print(line)
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


def explore_small():
    print(LINE)
    print(f"THĂM DÒ. C3 trên code 20k và SciFact, mọi chính sách (pha B), seed {SEEDS_B}")
    print("        dòng = cả dòng truy vấn; giữ = query giữ riêng ở cuối dòng; gold = NaN nếu dataset không có nhãn hàm gốc")
    print(LINE)
    for ds in ("code", "scifact"):
        for z in ("1", "0"):
            for t in TAGS:
                R = runs_of(f"probeV9_{ds}_{t}_s{{s}}_itq_q.json", SEEDS_B)
                if not R:
                    continue
                print(f"\n--- {ds} {t}, Zipf {z}, n = {len(R)} seed")
                policy_table(R, z)
    print()


# ----------------------------------------------------------------- churn (pha A)
def explore_churn():
    print(LINE)
    print(f"THĂM DÒ. Churn và lỗi peer trong lúc migrate (pha A), code100kfq, itq_q, Zipf 1, seed {SEEDS_A}")
    print("   ch   = phiên Weibull 0,5 trung vị 120 phút, dòng 720 phút, sửa mỗi 60 phút (lần đầu ở phút 30)")
    print("   fail = 30% node hỏng cùng lúc ngay trước lượt 1.500, không sửa")
    print("   'không churn' = đúng seed đó ở đợt 8 (probeV8); mapkeep không churn lấy từ chính job đó (probeV9X)")
    print(LINE)
    for cfg in ("ch", "fail"):
        for t in TAGS:
            R = runs_of(f"probeV9X_code100kfq_{t}_s{{s}}_itq_q.json", SEEDS_A, cfg=cfg)
            if not R:
                continue
            B = runs_of(f"probeV8_code100kfq_{t}_s{{s}}_itq_q.json", SEEDS_A)
            K = runs_of(f"probeV9X_code100kfq_{t}_s{{s}}_itq_q.json", SEEDS_A)
            for s in B:
                if s in K and "z1|PROB|mapkeep" in K[s]:
                    B[s] = dict(B[s]); B[s]["z1|PROB|mapkeep"] = K[s]["z1|PROB|mapkeep"]
            d0 = jl(f"probeV9X_code100kfq_{t}_s{min(R)}_itq_q.json")
            info = (d0.get("churn_sets") or {}).get(cfg) or {} if d0 else {}
            print(f"\n--- {cfg} {t}, n = {len(R)} seed; seed {min(R)}: {info.get('departures')} lượt node rời mạng hoặc hỏng, "
                  f"{len(info.get('repair_ts', []))} lần sửa")
            policy_table(R, "1", pols=["static", "lazy", "lazyV1", "lazyVbgD", "full", "mapall", "mapkeep"],
                         pairs=(("lazyVbgD", "lazy"), ("lazyVbgD", "static"), ("lazyVbgD", "mapkeep"),
                                ("lazyVbgD", "mapall"), ("full", "lazyVbgD"), ("lazy", "static")), extra=True)
            print("   thiệt hại do churn (có churn − không churn, cùng seed), final giữ riêng cuối dòng và rerank trên dòng:")
            for p in ("static", "lazy", "lazyV1", "lazyVbgD", "full", "mapall", "mapkeep"):
                dv = [snap_end(R[s][f"z1|PROB|{p}"])["final"] - snap_end(B[s][f"z1|PROB|{p}"])["final"]
                      for s in R if s in B and f"z1|PROB|{p}" in R[s] and f"z1|PROB|{p}" in B[s]]
                dr = [R[s][f"z1|PROB|{p}"]["totals"]["rr"] - B[s][f"z1|PROB|{p}"]["totals"]["rr"]
                      for s in R if s in B and f"z1|PROB|{p}" in R[s] and f"z1|PROB|{p}" in B[s]]
                if dv:
                    print(f"      {p:9s} giữ-final {cis(dv)}   dòng-rr {cis(dr)}   (n = {len(dv)})")
            cps = sorted(int(x) for x in R[min(R)]["z1|PROB|static"]["snapshots"])
            print("   quỹ đạo final giữ riêng (có churn); mất mọi đường (%) của lazy / lazyVbgD:")
            for p in ("static", "lazy", "lazyVbgD", "full", "mapkeep"):
                traj = [np.mean([R[s][f"z1|PROB|{p}"]["snapshots"][str(c)]["final"] for s in R if f"z1|PROB|{p}" in R[s]])
                        for c in cps]
                print(f"      {p:9s} " + " ".join(f"t{c}:{v:4.1f}" for c, v in zip(cps, traj)))
            for p in ("lazy", "lazyVbgD"):
                traj = [np.mean([R[s][f"z1|PROB|{p}"]["snapshots"][str(c)].get("lost_obj", float("nan")) for s in R])
                        for c in cps]
                print(f"      mất đường {p:9s} " + " ".join(f"t{c}:{v:5.2f}" for c, v in zip(cps, traj)))
            if cfg == "fail":
                for p_a, p_b in (("lazyVbgD", "lazy"), ("lazyVbgD", "static"), ("lazyVbgD", "mapkeep")):
                    cells = []
                    for c in (1000, 1500, 2000, 3000):
                        dv = [R[s][f"z1|PROB|{p_a}"]["snapshots"][str(c)]["final"] - R[s][f"z1|PROB|{p_b}"]["snapshots"][str(c)]["final"]
                              for s in R if str(c) in R[s][f"z1|PROB|{p_a}"]["snapshots"]]
                        cells.append(f"t{c}:{cis(dv)}")
                    print(f"   giữ-final {p_a} − {p_b}: " + "  ".join(cells))
    print()


# ----------------------------------------------------------------- mapkeep không churn (pha A)
def explore_mapkeep():
    print(LINE)
    print(f"THĂM DÒ. mapkeep trên code100kfq không churn (pha A), seed {SEEDS_C}; các chính sách khác lấy từ đợt 8 cùng seed")
    print(LINE)
    for z in ("1", "0"):
        for t in TAGS:
            B = runs_of(f"probeV8_code100kfq_{t}_s{{s}}_itq_q.json", SEEDS_C)
            K = runs_of(f"probeV9X_code100kfq_{t}_s{{s}}_itq_q.json", SEEDS_C)
            R = {}
            for s in K:
                if s in B and f"z{z}|PROB|mapkeep" in K[s]:
                    R[s] = dict(B[s]); R[s][f"z{z}|PROB|mapkeep"] = K[s][f"z{z}|PROB|mapkeep"]
            if not R:
                continue
            print(f"\n--- {t}, Zipf {z}, n = {len(R)} seed")
            policy_table(R, z, pols=["static", "lazy", "lazyVbgD", "full", "mapall", "mapkeep"],
                         pairs=(("lazyVbgD", "mapkeep"), ("mapkeep", "mapall"), ("mapkeep", "static"),
                                ("mapkeep", "lazy"), ("full", "mapkeep")))
    print()


# ----------------------------------------------------------------- placement itq<k> (pha D)
def explore_itqk():
    print(LINE)
    print(f"THĂM DÒ. ITQ trên k thành phần chính (pha D), code100kfq, seed {SEEDS_D}: hiệu final tại số ứng viên của srp "
          "(L=5, T=8), tải ở L=5")
    print(LINE)
    V = ("itq_q", "itq128_q", "itq256_q")

    def pts(v, x="cand", y="final_r5"):
        return [(v["results"][L][T][x], v["results"][L][T][y]) for L in v["results"] for T in v["results"][L] if T != "storage"]
    for t in SPACES:
        rows = defaultdict(list)
        for s in SEEDS_D:
            p8, p9 = jl(f"probeP_code100kfq_{t}_s{s}.json"), jl(f"probeP9_code100kfq_{t}_s{s}.json")
            if not p8 or not p9 or "srp" not in p8["variants"]:
                continue
            vs = p8["variants"]["srp"]
            c = vs["results"]["5"]["8"]["cand"]
            fs = interp(frontier(pts(vs)), c)
            gs = interp(frontier(pts(vs, "cand", "gold_rr20")), c)
            for vn in V:
                vi = p9["variants"].get(vn)
                if vi is None:
                    continue
                fi = interp(frontier(pts(vi)), c)
                gi = interp(frontier(pts(vi, "cand", "gold_rr20")), c)
                st, st0 = vi["results"]["5"]["storage"], vs["results"]["5"]["storage"]
                q58 = vi["results"]["5"]["8"]
                rows[vn].append(dict(df=(fi - fs) if fi is not None and fs is not None else float("nan"),
                                     dg=(gi - gs) if gi is not None and gs is not None else float("nan"),
                                     ratio=st0["max"] / max(1, st["max"]), mx=st["max"], top1=100 * st["top1pct_share"],
                                     ql=100 * q58["qload"]["max_frac"], fin58=q58["final_r5"], cand58=q58["cand"]))
        print(f"\n--- {t}")
        for vn in V:
            r = rows.get(vn)
            if not r:
                continue
            f = lambda k: float(np.nanmean([x[k] for x in r]))
            print(f"   {vn:9s} n={len(r)} Δfinal {f('df'):+6.2f}  Δgold {f('dg'):+6.2f}  tỉ lệ tải tối đa srp/biến thể "
                  f"{f('ratio'):5.1f} (theo seed {[round(x['ratio'], 1) for x in r]})  record tối đa {[x['mx'] for x in r]}  "
                  f"1% peer giữ {f('top1'):4.1f}%  peer nóng nhất nhận {f('ql'):4.1f}% query  (5,8): final {f('fin58'):5.1f}, "
                  f"ứng viên {f('cand58'):7.0f}")
    print()


# ----------------------------------------------------------------- chẩn đoán (pha E)
def explore_diag():
    print(LINE)
    print(f"THĂM DÒ. Chẩn đoán điểm nóng ITQ (pha E), code100kfq, L = 5, seed {SEEDS_D}")
    print(LINE)
    for t in SPACES:
        for s in SEEDS_D:
            d = jl(f"diagITQ_code100kfq_{t}_s{s}.json")
            if not d:
                continue
            c = d["corpus"]
            print(f"\n--- {t} s{s}: corpus năng lượng ngoài 63/128/256 TP {c['out_energy']['63']:.3f}/"
                  f"{c['out_energy']['128']:.3f}/{c['out_energy']['256']:.3f}, cos TB {c['pair_cos']:.3f}")
            for vn, v in d["variants"].items():
                line = (f"   {vn:9s} max {v['max']:6d}  theo bảng ở peer nóng {v['per_table_at_hot']}  nhóm khoá lớn nhất "
                        f"{v['top_group_sizes']}  bảng {v['hot_table']}: {v['hot_table_docs']} object, "
                        f"{v['hot_table_distinct_keys']} khoá khác nhau")
                if "hot_out_energy" in v:
                    e = v["hot_out_energy"]
                    line += (f"; ngoài 63/128/256 TP {e['63']:.3f}/{e['128']:.3f}/{e['256']:.3f}, cos TB {v['hot_pair_cos']:.3f}")
                if "hot_text_len_median" in v:
                    line += (f"; độ dài trung vị {v['hot_text_len_median']:.0f} (corpus {v['corpus_text_len_median']:.0f}), "
                             f"{v['hot_text_distinct']} văn bản khác nhau")
                print(line)
            if t == "arctic" and s == SEEDS_D[0]:
                v = d["variants"].get("itq_q", {})
                for i, x in enumerate(v.get("hot_text_examples", [])[:6]):
                    print(f"      ví dụ {i}: {x[:120]!r}")
    print()


# ----------------------------------------------------------------- tự kiểm
def checks():
    print(LINE)
    print("Tự kiểm")
    print(LINE)

    def show(fn, d, keys):
        for nm in keys:
            c = d.get(nm)
            if c:
                print(f"   {fn:52s} {nm}: {c['n']} giá trị, "
                      f"{'KHỚP' if c['bad'] == 0 and c['n'] > 0 else str(c['bad']) + ' LỆCH ' + str(c.get('diffs', [])[:3])}")
    for fn in sorted(glob.glob("probeVR9*.json")):
        d = jl(fn)
        if d:
            show(fn, d, ("check_prev",))
    n_ok, n_bad, n_tot = 0, 0, 0
    for fn in sorted(glob.glob("probeV9X_code100kfq_*_itq_q.json")):
        d = jl(fn)
        if d and d.get("check_prev"):
            n_tot += 1
            c = d["check_prev"]
            if c["bad"] == 0 and c["n"] > 0:
                n_ok += 1
            else:
                n_bad += 1; show(fn, d, ("check_prev",))
    print(f"   pha A: static không churn so với đợt 8 cùng seed: {n_ok}/{n_tot} file KHỚP")
    n_ok, n_tot = 0, 0
    for fn in sorted(glob.glob("probeV9_*_itq_q.json")):
        d = jl(fn)
        if d and d.get("check_10"):
            n_tot += 1
            c = d["check_10"]
            if c["bad"] == 0 and c["n"] > 0:
                n_ok += 1
            else:
                show(fn, d, ("check_10",))
    print(f"   pha B: placement itq_q trong 11 so với 10 của đợt 8 (seed có file): {n_ok}/{n_tot} file KHỚP")
    n_ok, n_tot = 0, 0
    for fn in sorted(glob.glob("probeP9_*.json")):
        d = jl(fn)
        if d and d.get("check_prev"):
            n_tot += 1
            c = d["check_prev"]
            if c["bad"] == 0 and c["n"] > 0:
                n_ok += 1
            else:
                show(fn, d, ("check_prev",))
    print(f"   pha D: itq_q so với đợt 8 cùng seed: {n_ok}/{n_tot} file KHỚP")
    print()


def main():
    h678()
    print(LINE)
    print("TÓM TẮT ĐÁNH GIÁ ĐĂNG KÝ TRƯỚC (H6 đến H8)")
    print(LINE)
    for nm, ok, det in VERDICT:
        print(f"   {'ĐẠT ' if ok else 'KHÔNG ĐẠT'}  {nm:22s} {det}")
    print(f"   Tổng: {sum(1 for _, ok, _ in VERDICT if ok)} trên {len(VERDICT)} tiêu chí đạt\n")
    explore_churn()
    explore_mapkeep()
    explore_small()
    explore_itqk()
    explore_diag()
    checks()


if __name__ == "__main__":
    main()
