#!/usr/bin/env python3
"""
13_lookup_rank.py  —  đợt 13, theo nhận xét của thầy về C2 (record tràn và lookup lặp).

Giới hạn tải của C2 đặt record tràn vào một peer khác trong K peer gần khoá nhất (theo XOR). Với probe lý tưởng, client hỏi
đủ K peer đó. Với lookup lặp, client chỉ tìm được khoảng 78 đến 85% (Mục 5.3). Câu hỏi: lookup lặp có bỏ sót peer ở hạng xa
nhiều hơn peer gần nhất không, tức record tràn có khó tìm hơn record nằm ở peer gần nhất không.

Script dựng overlay đúng như Net.__init__ của 08_sim_evo.py (id ngẫu nhiên 63 bit, mỗi node join qua một node đã vào rồi
một vòng refresh, k-bucket 20) và chạy lookup lặp đúng tham số của bộ mô phỏng (alpha = 3, K = 20, tối đa 20 vòng,
STOP_RULE = stable, FRONTIER_SCOPE = all) từ một node ngẫu nhiên tới một khoá ngẫu nhiên. Với mỗi lookup, so tập trả về với
K peer gần khoá nhất thật và ghi hạng (1 .. K) nào được tìm thấy. Không cần embedding.

Ghi: p_rank[r] = xác suất tìm thấy peer hạng r; share_mean = phần K peer gần nhất tìm được; share_all, share_none,
share_part = phần lookup tìm đủ K, không tìm được peer nào trong K, tìm được một phần; p_rank_given_any = như p_rank nhưng
chỉ trên lookup tìm được ít nhất một peer trong K; hops, rpcs trung bình.

CHẠY (ở thư mục gốc repo): python3 evo/13_lookup_rank.py --nodes 50000 --lookups 5000 --seed 1 --out probeL13_n50000_s1.json
"""
import argparse, json, os, random, sys, time
os.environ.setdefault("STOP_RULE", "stable")
os.environ.setdefault("FRONTIER_SCOPE", "all")
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import simpy                                    # noqa: E402
from src.node import VEngramNode                # noqa: E402
from src import routing as RT                   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", type=int, default=50000)
    ap.add_argument("--lookups", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--alpha", type=int, default=3)
    ap.add_argument("--rmax", type=int, default=20)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    K, t0 = a.k, time.time()
    rnd = random.Random(a.seed)
    ids = sorted({rnd.getrandbits(63) for _ in range(a.nodes)})
    env = simpy.Environment()
    rng = random.Random(a.seed + 101)
    nodes = [VEngramNode(env, int(x)) for x in ids]
    srt = sorted(nodes, key=lambda n: n.node_id)          # như 08_sim_evo.Net.__init__ (đúng src/network.bootstrap_network)
    joined = [srt[0]]
    for node in srt[1:]:
        boot = rng.choice(joined)
        node.kb_add(boot, K); boot.kb_add(node, K)
        found, _h, _r = RT.iterative_find_k_closest_nodes(node.node_id, boot, alpha=a.alpha, k=K, max_rounds=a.rmax)
        for peer in found:
            node.kb_add(peer, K); peer.kb_add(node, K)
        joined.append(node)
    for node in srt:                                      # một vòng refresh
        boot = rng.choice(srt)
        found, _h, _r = RT.iterative_find_k_closest_nodes(node.node_id, boot, alpha=a.alpha, k=K, max_rounds=a.rmax)
        for peer in found:
            node.kb_add(peer, K)
    for node in nodes:
        node.routing_table = set(p for b in node.kbuckets.values() for p in b)
    t_build = time.time() - t0
    print(f"[13l] overlay {len(nodes)} node dựng trong {t_build:.0f}s, STOP_RULE={RT.STOP_RULE}, "
          f"FRONTIER_SCOPE={RT.FRONTIER_SCOPE}", flush=True)

    arr = np.array([n.node_id for n in nodes], dtype=np.uint64)
    qrng = np.random.RandomState(a.seed + 7)
    got = np.zeros((a.lookups, K), dtype=bool)
    hops = rpcs = 0
    for q in range(a.lookups):
        key = int(qrng.randint(0, 2 ** 63 - 1, dtype=np.int64))
        true = arr[np.argsort(arr ^ np.uint64(key))[:K]]
        origin = nodes[rng.randrange(len(nodes))]
        found, h, r = RT.iterative_find_k_closest_nodes(key, origin, alpha=a.alpha, k=K, max_rounds=a.rmax)
        fs = {int(p.node_id) for p in found}
        got[q] = [int(t) in fs for t in true]
        hops += h; rpcs += r
    share = got.mean(1)
    anyf = share > 0
    out = dict(argv=vars(a), n_nodes=len(nodes), build_sec=round(t_build, 1), stop_rule=RT.STOP_RULE,
               frontier_scope=RT.FRONTIER_SCOPE,
               p_rank=[float(x) for x in got.mean(0)],
               p_rank_given_any=[float(x) for x in got[anyf].mean(0)] if anyf.any() else [],
               share_mean=float(share.mean()), share_all=float((share == 1).mean()), share_none=float((share == 0).mean()),
               share_part=float(((share > 0) & (share < 1)).mean()),
               share_mean_part=float(share[(share > 0) & (share < 1)].mean()) if ((share > 0) & (share < 1)).any() else None,
               hops_mean=hops / a.lookups, rpcs_mean=rpcs / a.lookups, sec=round(time.time() - t0, 1))
    print(f"   {a.lookups} lookup: tìm được {100 * out['share_mean']:.1f}% của {K} peer gần nhất; đủ {K}: "
          f"{100 * out['share_all']:.1f}%, không peer nào: {100 * out['share_none']:.1f}%, một phần: "
          f"{100 * out['share_part']:.1f}%")
    print("   P(tìm thấy | hạng r), r = 1 .. %d: %s" % (K, " ".join(f"{100 * x:.1f}" for x in out["p_rank"])))
    fo = a.out or f"probeL13_n{a.nodes}_s{a.seed}.json"
    json.dump(out, open(fo, "w"), indent=1)
    print(f"   ghi {fo} ({out['sec']}s)")


if __name__ == "__main__":
    main()
