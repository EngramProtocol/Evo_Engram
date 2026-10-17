#!/usr/bin/env python3
"""Tổng hợp đợt 5 (thăm dò, sau góp ý của thầy). Chạy ở thư mục chứa các file probe*.json.

  A. Cặp học adapter từ bản tái tạo PQ (--pair-src pq): chấm lại H1 đến H4 bằng đúng hàm của
     analyze_prereg.py trên file *_pq.json, đặt cạnh kết quả exact của đợt 4.
  B. Recall từ lookup lặp thật (09_sim_e2e.py, probeE2E_*.json): trạng thái cố định và dòng vòng kín,
     oracle (probe) so với lookup thật, ghép cặp theo seed.
"""
import glob, importlib.util, json, os, sys
import numpy as np

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("ap4", os.path.join(_here, "analyze_prereg.py"))
ap4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ap4)
_load_exact = ap4.load


def with_suffix(sfx):
    ap4.load = (lambda fn: _load_exact(fn)) if not sfx else (lambda fn: _load_exact(fn.replace(".json", f"{sfx}.json")))


def fmt(x, w=6, p=1, sign=True):
    if x is None or (isinstance(x, float) and x != x):
        return " " * (w - 1) + "-"
    return f"{x:+{w}.{p}f}" if sign else f"{x:{w}.{p}f}"


def part_a():
    print("#" * 100)
    print("A. ADAPTER HỌC TỪ BẢN TÁI TẠO PQ (re-indexer đọc c_o từ record E0; không cần embedding M0 đầy đủ)")
    print("   mỗi ô: exact (đợt 4) | pq (đợt 5); cùng seed 3 4 5, cùng tiêu chí của PREREG_round4.md")
    pair = {}
    for fn in sorted(glob.glob("probeG_*_pq.json")):
        d = json.load(open(fn))
        if "pair" in d:
            pair.setdefault(d["argv"]["dataset"], []).append(d["pair"])
    for ds, v in sorted(pair.items()):
        print(f"   {ds}: cos(e_o, c_o) trung bình {np.mean([x['cos_mean'] for x in v]):.5f}, nhỏ nhất "
              f"{np.min([x['cos_min'] for x in v]):.5f}; sai số tương đối TB {np.mean([x['rel_err_mean'] for x in v]):.4f}")
    hdr = (f"{'cặp':24s} {'H1 tệ nhất':>17s} {'H2 PROB−RRF f10':>17s} {'H2 bước xấu nhất':>17s} "
           f"{'H3 ADR−AD f50':>17s} {'H4 lazy−bg':>17s}")
    print(hdr)
    rows = {}
    verdicts = {}
    for sfx in ("", "_pq"):
        with_suffix(sfx)
        for ds, tags, fracs, prim in ap4.CONF:
            for tag in tags:
                ok1, o1, _ = ap4.h1(ds, tag, [prim], prim)
                ok2, ok3, i23 = ap4.h23(ds, tag)
                ok4, i4 = ap4.h4(ds, tag)
                key = f"{ds}/{tag}"
                rows.setdefault(key, {})[sfx or "exact"] = dict(
                    h1=(o1.get(prim) or {}).get("worst"), h2a=i23.get("prob_minus_rrf_f10"), h2b=i23.get("worst_step"),
                    h3=i23.get("refit_minus_ad_f50"), h4=i4.get("lazy_minus_bg_final"),
                    fetch=(i4.get("fetch_lazy"), i4.get("fetch_static")))
                verdicts.setdefault(key, {})[sfx or "exact"] = (ok1, ok2, ok3, ok4)
    with_suffix("")
    for key, r in rows.items():
        e, q = r.get("exact", {}), r.get("_pq", {})
        cell = lambda k: f"{fmt(e.get(k))} |{fmt(q.get(k))}  "
        print(f"{key:24s} " + " ".join(f"{cell(k):>17s}" for k in ("h1", "h2a", "h2b", "h3", "h4")))
    print(f"\n{'cặp':24s} {'H1':>22s} {'H2':>22s} {'H3':>22s} {'H4':>22s}   (exact | pq)")
    for key, v in verdicts.items():
        e, q = v.get("exact", (None,) * 4), v.get("_pq", (None,) * 4)
        print(f"{key:24s} " + " ".join(f"{ap4.verdict(a) + ' | ' + ap4.verdict(b):>22s}" for a, b in zip(e, q)))
    # chi tiết H3 theo f: ADR_PROB pq so với exact
    print("\n   ADR_PROB final@5 theo f (TB 3 seed), exact | pq:")
    for ds, tags, _, _ in ap4.CONF:
        for tag in tags:
            pre = ap4.pre(ds)
            E = [_load_exact(f"probeG_{pre}{tag}_s{s}.json") for s in ap4.SEEDS]
            Q = [_load_exact(f"probeG_{pre}{tag}_s{s}_pq.json") for s in ap4.SEEDS]
            if any(x is None for x in E + Q):
                continue
            fs = sorted((k for k in E[0]["results"] if not k.startswith("_")), key=float)
            line = []
            for f in fs:
                me = np.mean([x["results"][f]["ADR_PROB"]["final_r5"] for x in E])
                mq = np.mean([x["results"][f]["ADR_PROB"]["final_r5"] for x in Q])
                ad = np.mean([x["results"][f]["AD_PROB"]["final_r5"] for x in Q])
                line.append(f"f={f}: {me:5.1f}|{mq:5.1f} (AD pq {ad:5.1f})")
            print(f"   {ds}/{tag}: " + "  ".join(line))
            chk = [x.get("checks", {}).get("nonadapter_vs_exact") for x in Q]
            print(f"      tự kiểm nhánh không dùng adapter: " + ", ".join(
                "thiếu" if c is None else f"{c['n']} giá trị {'KHỚP' if c['bad'] == 0 else str(c['bad']) + ' LỆCH'}" for c in chk))


def part_b():
    print("\n" + "#" * 100)
    print("B. RECALL ĐO TỪ LOOKUP LẶP THẬT (09_sim_e2e.py): oracle = tập K node XOR-gần nhất của probe,")
    print("   thật = tập node Ripple Search trả về trong SimPy. TB theo seed; ± là độ lệch chuẩn giữa các seed.")
    files = sorted(glob.glob("probeE2E_*.json"))
    if not files:
        print("   chưa có probeE2E_*.json"); return
    groups = {}
    for fn in files:
        d = json.load(open(fn))
        a = d["argv"]
        groups.setdefault((a["dataset"], a["tag"], a["nodes"]), []).append(d)
    for (ds, tag, nodes), G in sorted(groups.items()):
        seeds = [g["argv"]["seed"] for g in G]
        print("=" * 100)
        print(f"{ds} / {tag}, {nodes} node, seed {seeds}")
        for g in G:
            c = g["checks"]
            print("   tự kiểm seed {}: ".format(g["argv"]["seed"]) + "; ".join(
                f"{k} {v['n']} giá trị {'KHỚP' if v['bad'] == 0 else str(v['bad']) + ' LỆCH'}" for k, v in c.items()))
        print(f"   {'trạng thái':10s} {'final oracle':>13s} {'final thật':>11s} {'chênh':>12s} {'R20 oracle':>11s} "
              f"{'R20 thật':>9s} {'chênh':>12s} {'reach o/t':>12s} {'tìm lại node':>18s} {'RPC':>7s} {'p50 (s)':>8s}")
        for nm in G[0]["fixed"]:
            X = [g["fixed"][nm] for g in G]
            m = lambda f: float(np.mean([f(x) for x in X]))
            sd = lambda f: float(np.std([f(x) for x in X], ddof=1)) if len(X) > 1 else 0.0
            rec = {k: m(lambda x, k=k: 100 * x["recovery"][k]["found_frac"]) for k in X[0]["recovery"]}
            cost = [x["cost"] for x in X if x["cost"]]
            print(f"   {nm:10s} {m(lambda x: x['oracle']['final_r5']):13.1f} {m(lambda x: x['sim']['final_r5']):11.1f} "
                  f"{m(lambda x: x['diff']['final_mean']):+6.1f}±{sd(lambda x: x['diff']['final_mean']):4.1f} "
                  f"{m(lambda x: x['oracle']['rr']):11.1f} {m(lambda x: x['sim']['rr']):9.1f} "
                  f"{m(lambda x: x['diff']['rr_mean']):+6.1f}±{sd(lambda x: x['diff']['rr_mean']):4.1f} "
                  f"{m(lambda x: x['oracle']['reach']):5.1f}/{m(lambda x: x['sim']['reach']):5.1f} "
                  f"{' '.join(f'{k}={v:.0f}%' for k, v in rec.items()):>18s} "
                  + (f"{np.mean([c['rpc_total'] for c in cost]):7.0f} {np.mean([c['lat_total_ms_p50'] for c in cost]) / 1000:8.2f}"
                     if cost else ""))
        S = [g["stream"] for g in G if g.get("stream")]
        if not S:
            continue
        pols = list(S[0]["runs"])
        print(f"   dòng Zipf({S[0]['zipf']:g}) {S[0]['length']} lượt, vòng kín:")
        print(f"   {'chính sách':10s} {'final o/t':>13s} {'R20 o/t':>13s} {'payload o/t':>12s} {'f cuối o/t':>12s} "
              f"{'GT ở E1 t':>10s} {'RPC client':>11s} {'p50 (s)':>8s} {'RPC re-idx':>11s}")
        for pol in pols:
            X = [s["runs"][pol] for s in S if pol in s["runs"]]
            o = lambda k: float(np.mean([x["oracle"]["totals"][k] for x in X]))
            t = lambda k: float(np.mean([x["sim"]["totals"][k] for x in X]))
            cl = [x["sim"].get("client") for x in X if x["sim"].get("client")]
            print(f"   {pol:10s} {o('final'):6.1f}/{t('final'):5.1f} {o('rr'):6.1f}/{t('rr'):5.1f} "
                  f"{o('fetch'):5.1f}/{t('fetch'):5.1f} {100 * o('f_end'):5.1f}/{100 * t('f_end'):5.1f} {t('gtE1'):10.1f} "
                  + (f"{np.mean([c['rpc_total'] for c in cl]):11.0f} {np.mean([c['lat_total_ms_p50'] for c in cl]) / 1000:8.2f}"
                     if cl else " " * 20)
                  + f" {np.mean([x['sim']['reindexer_rpc_per_query'] for x in X]):11.0f}")
        if all(p in pols for p in ("lazy", "bg")):
            for mode, lab in (("oracle", "oracle"), ("sim", "thật")):
                df = [s["runs"]["lazy"][mode]["totals"]["final"] - s["runs"]["bg"][mode]["totals"]["final"] for s in S]
                dr = [s["runs"]["lazy"][mode]["totals"]["rr"] - s["runs"]["bg"][mode]["totals"]["rr"] for s in S]
                print(f"   lazy − bg ({lab:6s}): final {np.mean(df):+5.1f} (seed: {', '.join(f'{x:+.1f}' for x in df)})"
                      f"   rerank {np.mean(dr):+5.1f} (seed: {', '.join(f'{x:+.1f}' for x in dr)})")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "ab"
    if "a" in what:
        part_a()
    if "b" in what:
        part_b()
