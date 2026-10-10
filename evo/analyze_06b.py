#!/usr/bin/env python3
"""Tổng hợp probeLR_*.json (06 với --workloads verbatim,para và --reindex): lazy dưới trust model
re-indexer (công suất, độ trễ) và workload paraphrase. Trung bình qua seed, chênh ghép cặp."""
import json, glob, sys
import numpy as np

pats = sys.argv[1:] or ["probeLR_*.json"]
runs = {}
for f in sorted({x for p in pats for x in glob.glob(p)}):
    if f.endswith("_trace.json"):
        continue
    d = json.load(open(f))
    runs.setdefault((d["argv"].get("dataset", "code"), d["argv"]["tag"]), []).append(d)
if not runs:
    sys.exit(f"không thấy file nào khớp {pats}")


def ms(x, sign=False):
    x = np.asarray(x, float)
    sd = x.std(ddof=1) if len(x) > 1 else float("nan")
    return f"{x.mean():+5.1f}±{sd:3.1f}" if sign else f"{x.mean():5.1f}±{sd:3.1f}"


for (ds, tag), rr in sorted(runs.items()):
    a0 = rr[0]["argv"]
    print("=" * 110)
    print(f"{ds} / {tag}  seed={[d['argv']['seed'] for d in rr]}  dòng={a0['stream']} R={a0['R']}  re-indexer={a0['reindex']}"
          f"  workload={a0['workloads']}")
    print("  tự kiểm với đợt 3b: " + "; ".join(
        f"s{d['argv']['seed']}: " + (f"{d['check_3b']['n']} giá trị, {'KHỚP' if d['check_3b']['bad'] == 0 else str(d['check_3b']['bad']) + ' LỆCH'}"
                                     if d.get("check_3b") else "không có") for d in rr))
    pi = [d.get("para_info") for d in rr]
    if all(pi):
        print(f"  paraphrase: {pi[0]['n_var']} biến thể; GT top-5 của paraphrase trùng GT câu gốc "
              f"{np.mean([p['gt_overlap_with_orig'] for p in pi]):.1f}%")
    zs = sorted({r["zipf"] for r in rr[0]["runs"].values()})
    for wl in a0["workloads"].split(","):
        for z in zs:
            for fus in a0["fusions"].split(","):
                pref = "" if wl == "verbatim" else f"{wl}|"
                base = f"{pref}z{z:g}|{fus}"
                if f"{base}|lazy" not in rr[0]["runs"]:
                    continue
                print(f"\n  [{wl}] Zipf {z:g}, {fus}:  final | rerank | payload/q | record mới/q | f cuối | hàng đợi TB")
                for pol in ("static", "lazy", "bg", "lazybg", "bg2"):
                    k = f"{base}|{pol}"
                    if k not in rr[0]["runs"]:
                        continue
                    T = [d["runs"][k]["totals"] for d in rr]
                    print(f"    {pol:8s} inf:0   {ms([t['final'] for t in T])} | {ms([t['rr'] for t in T])} | "
                          f"{np.mean([t['fetch'] for t in T]):5.1f} | {np.mean([t['new'] for t in T]):5.2f} | "
                          f"{100 * np.mean([t['f_end'] for t in T]):5.1f}% | {np.mean([t.get('qlen_mean', 0) for t in T]):6.0f}")
                for sp in a0["reindex"].split(","):
                    if sp == "inf:0":
                        continue
                    for pol in ("lazy", "bg"):
                        k = f"{base}|{pol}|r{sp}"
                        if k not in rr[0]["runs"]:
                            continue
                        T = [d["runs"][k]["totals"] for d in rr]
                        print(f"    {pol:8s} {sp:7s} {ms([t['final'] for t in T])} | {ms([t['rr'] for t in T])} | "
                              f"{np.mean([t['fetch'] for t in T]):5.1f} | {np.mean([t['new'] for t in T]):5.2f} | "
                              f"{100 * np.mean([t['f_end'] for t in T]):5.1f}% | {np.mean([t.get('qlen_mean', 0) for t in T]):6.0f}")
                print("    chênh ghép cặp lazy − bg (final | rerank) theo cấu hình re-indexer:")
                for sp in a0["reindex"].split(","):
                    suf = "" if sp == "inf:0" else f"|r{sp}"
                    kl, kb = f"{base}|lazy{suf}", f"{base}|bg{suf}"
                    if kl in rr[0]["runs"] and kb in rr[0]["runs"]:
                        print(f"      {sp:8s} {ms([d['runs'][kl]['totals']['final'] - d['runs'][kb]['totals']['final'] for d in rr], True)} | "
                              f"{ms([d['runs'][kl]['totals']['rr'] - d['runs'][kb]['totals']['rr'] for d in rr], True)}")
                kl = f"{base}|lazy"
                T = [d["runs"][kl]["totals"] for d in rr]
                if "final_rep_newvar" in T[0]:
                    print(f"    lazy inf:0: lần đầu final {ms([t['final_first'] for t in T])}; lặp lại nguyên văn "
                          f"{ms([t['final_rep_exact'] for t in T])} ({np.mean([t['rep_exact_share'] for t in T]):.0f}% lượt); "
                          f"lặp intent bằng cách hỏi mới {ms([t['final_rep_newvar'] for t in T])}")
                    Ts = [d["runs"][f"{base}|static"]["totals"] for d in rr]
                    print(f"    static    : lần đầu final {ms([t['final_first'] for t in Ts])}; lặp lại nguyên văn "
                          f"{ms([t['final_rep_exact'] for t in Ts])}; lặp intent bằng cách hỏi mới {ms([t['final_rep_newvar'] for t in Ts])}")
                snaps = [d["runs"][kl]["snapshots"] for d in rr]
                print("    lazy, 100 query giữ riêng (final/rerank, f): " + "  ".join(
                    f"t{k}:{np.mean([s[k]['final'] for s in snaps]):4.1f}/{np.mean([s[k]['rr'] for s in snaps]):4.1f}"
                    f"({100 * np.mean([s[k]['f'] for s in snaps]):.0f}%)" for k in snaps[0]))
