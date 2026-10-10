#!/usr/bin/env python3
"""Tổng hợp probeS_*.json (08_sim_evo): chi phí end-to-end theo kịch bản, chi phí re-indexer, dòng lazy."""
import json, glob, sys
import numpy as np

pats = sys.argv[1:] or ["probeS_*.json"]
runs = {}
for f in sorted({x for p in pats for x in glob.glob(p)}):
    d = json.load(open(f))
    runs.setdefault((d["argv"].get("dataset", "code"), d["argv"]["tag"], d["argv"]["nodes"]), []).append(d)
if not runs:
    sys.exit(f"không thấy file nào khớp {pats}")
M = lambda xs: float(np.mean(xs))

for (ds, tag, nodes), rr in sorted(runs.items()):
    print("=" * 128)
    print(f"{ds} / {tag}  node={nodes}  seed={[d['argv']['seed'] for d in rr]}  query mô phỏng={rr[0]['argv']['nq_sim']}"
          f"  payload TB={rr[0]['payload_bytes_mean']:.0f} byte  bench={rr[0]['bench']['src']}")
    print("  tự kiểm chất lượng với 04b: " + "; ".join(
        f"s{d['argv']['seed']}: " + (f"{d['check_04b']['n']} giá trị, {'KHỚP' if d['check_04b']['bad'] == 0 else str(d['check_04b']['bad']) + ' LỆCH'}"
                                     if d.get("check_04b") else "không có") for d in rr)
          + f";  lookup mô phỏng tìm lại {100 * M([d['walk_overlap'] for d in rr]):.1f}% tập node của probe")
    print(f"  {'kịch bản':9s} {'final':>6s} {'R20':>6s} | {'RPC':>7s} {'find':>6s} {'ADC':>5s} {'payload':>7s} | "
          f"{'KB':>7s} | {'tải':>5s} {'CPU s':>6s} | {'trễ p50':>8s} {'p95':>6s} {'không rerank':>12s}")
    for sc in rr[0]["scenarios"]:
        Q = [d["scenarios"][sc]["quality"] for d in rr]
        C = [d["scenarios"][sc]["cost"] for d in rr]
        print(f"  {sc:9s} {M([q['final_r5'] for q in Q]):6.1f} {M([q['rr'] for q in Q]):6.1f} | "
              f"{M([c['rpc_total'] for c in C]):7.0f} {M([c['rpc_find'] for c in C]):6.0f} {M([c['rpc_adc'] for c in C]):5.0f} "
              f"{M([c['rpc_pay'] for c in C]):7.0f} | {M([c['kb_total'] for c in C]):7.1f} | {M([c['payloads'] for c in C]):5.1f} "
              f"{M([c['cpu_s'] for c in C]):6.2f} | {M([c['lat_total_ms_p50'] for c in C]) / 1000:7.2f}s "
              f"{M([c['lat_total_ms_p95'] for c in C]) / 1000:5.2f}s {M([c['lat_nopay_ms_p50'] for c in C]):10.0f}ms")
    P = [d["reindex_per_record"] for d in rr]
    print(f"  re-indexer mỗi record: {M([p['rpc'] for p in P]):.0f} RPC (ghi {M([p['rpc_write'] for p in P]):.0f}), "
          f"{M([p['kb'] for p in P]):.1f} KB, CPU {M([p['cpu_s'] for p in P]):.2f} s, tải {M([p['t_fetch_ms'] for p in P]):.0f} ms, "
          f"ghi {M([p['t_write_ms'] for p in P]):.0f} ms")
    lz = [d.get("lazy") for d in rr if d.get("lazy")]
    if lz:
        print(f"  DÒNG LAZY ({len(lz)} seed), mỗi truy vấn:  client RPC | KB | payload | CPU s | trễ p50 / p95 || "
              f"re-indexer RPC | CPU s | record migrate")
        for k in lz[0]:
            C = [x[k]["client"] for x in lz if k in x]
            X = [x[k] for x in lz if k in x]
            print(f"    {k:24s} {M([c['rpc_total'] for c in C]):7.0f} | {M([c['kb_total'] for c in C]):7.1f} | "
                  f"{M([c['payloads'] for c in C]):5.1f} | {M([c['cpu_s'] for c in C]):5.2f} | "
                  f"{M([c['lat_total_ms_p50'] for c in C]) / 1000:5.2f}s / {M([c['lat_total_ms_p95'] for c in C]) / 1000:5.2f}s || "
                  f"{M([x['reindexer_rpc_per_query'] for x in X]):6.0f} | {M([x['reindexer_cpu_s_per_query'] for x in X]):5.2f} | "
                  f"{M([x['migrated_total'] for x in X]):7.0f}")
            W = [x[k]["windows"] for x in lz if k in x]
            print("       theo cửa sổ (client RPC / trễ p50 s / payload): " + "  ".join(
                f"t{W[0][i]['t_end']}:{M([w[i]['client']['rpc_total'] for w in W]):.0f}/"
                f"{M([w[i]['client']['lat_total_ms_p50'] for w in W]) / 1000:.1f}/{M([w[i]['client']['payloads'] for w in W]):.1f}"
                for i in range(len(W[0]))))
