#!/usr/bin/env python3
"""
08_sim_evo.py  —  CHẠY TRÊN node-dal-02 (CPU), từ thư mục gốc repo (cần src/ của V-Engram).

Đo chi phí end-to-end của pipeline Evo-Engram trong mô phỏng sự kiện rời rạc của V-Engram: overlay
Kademlia k-bucket dựng bằng gia nhập tuần tự (BOOTSTRAP=join), Ripple Search của src/routing.py
(STOP_RULE=stable, FRONTIER_SCOPE=all, alpha=3, R_max=20), RTT ~ N(50, 15) ms, payload chia RS(30,20)
đặt tất định theo khoá HMAC (PLACEMENT_MODE=deterministic, PLACEMENT_K=20), đúng cấu hình bảng chi phí
của bài V-Engram. Định danh node là đúng 10.000 định danh 63 bit mà các probe dùng, nên khoá probe của
probe và của mô phỏng trỏ về cùng vùng overlay.

Chất lượng (final, rerank) KHÔNG đo lại ở đây: lấy từ đúng pipeline của 04b/06 và tự kiểm khớp từng số
với probeG (04b). Mô phỏng chỉ thêm phần chi phí:
  - định tuyến: số vòng, FIND_NODE RPC, byte (160 byte mỗi RPC như V-Engram)
  - ADC: một RPC mỗi node mới chạm mỗi chỉ mục (512 byte yêu cầu), ứng viên trả về 24 byte mỗi cái
  - payload: mỗi document E0 trong pool rerank tải 20 shard song song (thiếu thì lấy thêm từ 30),
    mỗi shard một lookup + GET, kích thước thật = độ dài văn bản UTF-8 / 20
  - CPU phía client: mã hoá query (M1, dual thêm M0) và nhúng lại payload, theo số đo 05_bench_cpu trên
    chính node-dal-02 (bench_<tag>.json)
  - ghi khi migrate (trust model: chỉ re-indexer được công bố): re-indexer tải payload, nhúng lại, ghi
    record E1 tại L anchor (lookup + STORE), xoá bản E0 tại L anchor (lookup + DELETE); client gửi gợi ý
    một RPC mỗi truy vấn khi có document E0 trong pool (chính sách lazy)
  - độ trễ: mã hoá + khám phá (probe chậm nhất) + tải payload (shard chậm nhất) + nhúng lại

Hai phần:
  A. trạng thái cố định f ∈ --fmig: dual-rerank (DU), adapter (AD) gộp PROB với E1, native E1 ở f = 1
  B. dòng lazy (tuỳ chọn, --lazy-trace từ 06 --trace-runs): phát lại mỗi --lazy-every truy vấn, cộng chi phí
     re-indexer theo số record migrate thực tế

CHẠY: python3 evo/08_sim_evo.py --tag bgebase --seed 20235956 --lazy-trace probeLR_bgebase_s20235956_trace.json
"""
import argparse, importlib.util, json, math, os, random, sys, time

os.environ.setdefault("STOP_RULE", "stable")
os.environ.setdefault("FRONTIER_SCOPE", "all")
os.environ.setdefault("MEASURE_OVERLAP", "0")
import numpy as np

_here = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_here)
sys.path.insert(0, ROOT)
sys.path.insert(0, _here)
import simpy                                    # noqa: E402
from src.node import VEngramNode                # noqa: E402
from src import routing as RT                   # noqa: E402
import me_common as mc                          # noqa: E402

np.seterr(invalid='ignore', divide='ignore')
q3, pb = mc.q3, mc.pb
log, l2norm = mc.log, mc.l2norm
_spec = importlib.util.spec_from_file_location("m4b", os.path.join(_here, "04b_probe_multiepoch2.py"))
m4b = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m4b)

B_FIND, B_ADC_REQ, B_CAND, B_GET_REQ, B_SHARD_HDR, B_SIG, B_TAG = 160, 512, 24, 32, 32, 64, 32
MASK63 = (1 << 63) - 1

# số đo 05_bench_cpu trên node-dal-02 (gate 3b), chỉ dùng khi thiếu file bench
BENCH_FALLBACK = {
    "bgebase": dict(m0_q=0.1309, m1_q=0.0447, pay={5: 1.96, 10: 3.72, 20: 7.63, 50: 14.04, 100: 19.74}),
    "e5large": dict(m0_q=0.1407, m1_q=0.1399, pay={5: 6.50, 10: 12.78, 20: 27.07, 50: 48.32, 100: 68.17}),
}


def load_bench(path, tag):
    if path and os.path.exists(path):
        b = json.load(open(path))["rows"]
        return dict(m0_q=b["M0"]["query_ms_median"] / 1000, m1_q=b["M1"]["query_ms_median"] / 1000,
                    pay={int(k): float(v) for k, v in b["M1"]["payload_s"].items()}, src=path)
    if tag in BENCH_FALLBACK:
        d = dict(BENCH_FALLBACK[tag]); d["src"] = "fallback gate 3b"
        return d
    d = dict(BENCH_FALLBACK["bgebase"]); d["src"] = "fallback bgebase (THIẾU bench cho tag này)"
    return d


def pay_seconds(bench, n):
    if n <= 0:
        return 0.0
    xs = [0] + sorted(bench["pay"]); ys = [0.0] + [bench["pay"][k] for k in sorted(bench["pay"])]
    if n >= xs[-1]:
        return ys[-1] * n / xs[-1]
    return float(np.interp(n, xs, ys))


# ----------------------------------------------------------------- overlay và các tiến trình SimPy
class Net:
    def __init__(self, nid, seed, kb=20, alpha=3, rmax=20, place_k=20):
        self.env = simpy.Environment()
        self.rng = random.Random(seed + 101)
        self.alpha, self.rmax, self.kb, self.place_k = alpha, rmax, kb, place_k
        self.nid = nid
        self.nodes = [VEngramNode(self.env, int(x)) for x in nid.tolist()]
        t0 = time.time()
        srt = sorted(self.nodes, key=lambda n: n.node_id)          # đúng src/network.bootstrap_network
        joined = [srt[0]]
        for node in srt[1:]:
            boot = self.rng.choice(joined)
            node.kb_add(boot, kb); boot.kb_add(node, kb)
            found, _h, _r = RT.iterative_find_k_closest_nodes(node.node_id, boot, alpha=alpha, k=kb, max_rounds=rmax)
            for peer in found:
                node.kb_add(peer, kb); peer.kb_add(node, kb)
            joined.append(node)
        for node in srt:                                              # một vòng refresh
            boot = self.rng.choice(srt)
            found, _h, _r = RT.iterative_find_k_closest_nodes(node.node_id, boot, alpha=alpha, k=kb, max_rounds=rmax)
            for peer in found:
                node.kb_add(peer, kb)
        for node in self.nodes:
            node.routing_table = set(p for b in node.kbuckets.values() for p in b)
        sz = [len(n.routing_table) for n in self.nodes]
        self.idx = {n.node_id: i for i, n in enumerate(self.nodes)}
        log(f"overlay {len(self.nodes)} node (k-bucket {kb}, join): contact/peer TB {np.mean(sz):.0f} "
            f"[{min(sz)}, {max(sz)}]  ({time.time() - t0:.0f}s)")
        self.holder = {}

    def rtt(self):
        return max(1.0, self.rng.normalvariate(50, 15))

    def walk(self, key, origin, k):
        nodes, hops, rpcs = RT.iterative_find_k_closest_nodes(int(key), origin, alpha=self.alpha, k=k,
                                                              max_rounds=self.rmax)
        return nodes, hops, rpcs

    # -- khám phá: một probe = lookup + ADC trên node mới
    def probe(self, key, origin, contacted, acc, k, ov=None):
        nodes, hops, rpcs = self.walk(key, origin, k)
        for _ in range(hops):
            yield self.env.timeout(self.rtt())
        acc["find_rpc"] += rpcs; acc["rounds"] += hops
        if ov is not None:
            tru = set(pb.knn_nodes(np.array([key], dtype=np.int64), self.nid, k)[0].tolist())
            ov.append(len(tru & {self.idx[n.node_id] for n in nodes}) / float(k))
        new = [n for n in nodes if n.node_id not in contacted]
        for n in new:
            contacted.add(n.node_id)
        if new:
            yield self.env.all_of([self.env.process(self._adc(acc)) for _ in new])

    def _adc(self, acc):
        yield self.env.timeout(self.rtt())
        acc["adc_rpc"] += 1

    # -- payload: RS(30,20), 20 shard song song, thiếu thì lấy tiếp shard 20..29
    def holder_of(self, doc, s):
        kk = (doc, s)
        if kk not in self.holder:
            pk = RT.generate_placement_key(f"doc_{doc}", s) & MASK63
            self.holder[kk] = (pk, int(pb.nearest_node(np.array([pk], dtype=np.int64), self.nid)[0]))
        return self.holder[kk]

    def shard(self, doc, s, origin, acc, sbytes, got):
        pk, h = self.holder_of(doc, s)
        nodes, hops, rpcs = self.walk(pk, origin, self.place_k)
        for _ in range(hops):
            yield self.env.timeout(self.rtt())
        acc["pay_find_rpc"] += rpcs; acc["pay_rounds"] += hops
        ids = [self.idx[n.node_id] for n in nodes]
        depth = ids.index(h) + 1 if h in ids else len(ids)
        for _ in range(depth):
            yield self.env.timeout(self.rtt() + self.rng.uniform(2, 8))
            acc["get_rpc"] += 1
        if h in ids:
            acc["pay_bytes_data"] += sbytes; got.append(1)
        else:
            acc["shard_miss"] += 1

    def fetch(self, doc, size, origin, acc):
        sb = int(math.ceil(size / 20.0)) + B_SHARD_HDR
        got = []
        yield self.env.all_of([self.env.process(self.shard(doc, s, origin, acc, sb, got)) for s in range(20)])
        if len(got) < 20:
            extra = list(range(20, 20 + min(10, 20 - len(got) + 2)))
            yield self.env.all_of([self.env.process(self.shard(doc, s, origin, acc, sb, got)) for s in extra])
        acc["objects"] += 1
        acc["obj_fail"] += int(len(got) < 20)

    # -- một truy vấn phía client
    def query(self, sides, fetched, sizes, acc, k_query, ov=None):
        env = self.env
        origin = self.rng.choice(self.nodes)
        t0 = env.now
        procs = []
        for keys in sides:
            contacted = set()
            procs += [env.process(self.probe(kk, origin, contacted, acc, k_query, ov)) for kk in keys]
        if procs:
            yield env.all_of(procs)
        acc["t_disc"] = env.now - t0
        t1 = env.now
        if len(fetched):
            yield env.all_of([env.process(self.fetch(int(d), sizes[int(d)], origin, acc)) for d in fetched])
        acc["t_pay"] = env.now - t1

    def run_query(self, sides, fetched, sizes, k_query, ov=None):
        acc = dict(find_rpc=0, rounds=0, adc_rpc=0, pay_find_rpc=0, pay_rounds=0, get_rpc=0, pay_bytes_data=0,
                   shard_miss=0, objects=0, obj_fail=0, t_disc=0.0, t_pay=0.0)
        p = self.env.process(self.query(sides, fetched, sizes, acc, k_query, ov))
        self.env.run(until=p)
        return acc

    # -- re-indexer: tải payload, công bố record E1 tại L anchor, xoá bản E0 tại L anchor
    def reindex_one(self, doc, size, keys1, keys0, origin, acc, m1_bytes):
        env = self.env
        t0 = env.now
        yield env.process(self.fetch(doc, size, origin, acc))
        acc["t_fetch"] += env.now - t0

        def put(key, nbytes, kind):
            nodes, hops, rpcs = self.walk(key, origin, 1)
            for _ in range(hops):
                yield env.timeout(self.rtt())
            acc["w_find_rpc"] += rpcs
            yield env.timeout(self.rtt())
            acc[kind] += 1; acc["w_bytes"] += nbytes
        t1 = env.now
        yield env.all_of([env.process(put(k, m1_bytes + B_SIG + B_TAG, "store_rpc")) for k in keys1] +
                         [env.process(put(k, B_TAG + B_SIG, "delete_rpc")) for k in keys0])
        acc["t_write"] += env.now - t1


def summarize(rows):
    out = {}
    for k in rows[0]:
        v = np.asarray([r[k] for r in rows], dtype=float)
        out[k] = float(v.mean())
        if k.startswith("lat"):
            out[k + "_p50"] = float(np.percentile(v, 50)); out[k + "_p95"] = float(np.percentile(v, 95))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--dataset", default="code")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--seed", type=int, default=20235956)
    ap.add_argument("--nodes", type=int, default=10000)
    ap.add_argument("--nq", type=int, default=300)
    ap.add_argument("--nq-sim", type=int, default=100, help="số query đánh giá đầu tiên đưa vào mô phỏng chi phí")
    ap.add_argument("--tables", type=int, default=5)
    ap.add_argument("--k-query", type=int, default=20)
    ap.add_argument("--probes", type=int, default=8)
    ap.add_argument("--cbits", type=int, default=16)
    ap.add_argument("--dsub", type=int, default=2)
    ap.add_argument("--kappa", type=int, default=30)
    ap.add_argument("--frac", type=float, default=0.10)
    ap.add_argument("--fmig", default="0,0.1,0.5,0.9,1.0")
    ap.add_argument("--R", type=int, default=20)
    ap.add_argument("--need", type=int, default=100, help="độ dài danh sách mỗi phía, bằng max R của 04b để PROB trùng 04b")
    ap.add_argument("--cal-top", type=int, default=30)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--r-max", type=int, default=20)
    ap.add_argument("--bench", default=None, help="bench_<tag>.json của 05_bench_cpu; mặc định tìm bench_<tag>.json")
    ap.add_argument("--lazy-trace", default=None)
    ap.add_argument("--lazy-every", type=int, default=10)
    ap.add_argument("--lazy-window", type=int, default=300)
    ap.add_argument("--reindex-sample", type=int, default=150)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    t0 = time.time()
    D, ds = a.data_dir, a.dataset
    T, R, kap = a.probes, a.R, a.kappa
    NEED = max(a.need, R, 5)
    fgrid = [float(x) for x in a.fmig.split(",")]
    random.seed(a.seed)

    E0 = np.load(f"{D}/{ds}_corpus_embeddings.npy").astype(np.float32)
    Q0 = np.load(f"{D}/{ds}_query_embeddings.npy").astype(np.float32)
    cb0 = np.load(f"{D}/{ds}_pq_codebook_m512.npy").astype(np.float32)
    cd0 = np.load(f"{D}/{ds}_pq_codes_m512.npy")
    E1 = np.load(f"{D}/{ds}_{a.tag}_corpus_embeddings.npy").astype(np.float32)
    Q1 = np.load(f"{D}/{ds}_{a.tag}_query_embeddings.npy").astype(np.float32)
    gt1 = json.load(open(f"{D}/{ds}_{a.tag}_ground_truth.json"))
    texts = json.load(open(f"{D}/{ds}_corpus_texts.json"))
    sizes = np.array([len(str(t).encode("utf-8")) for t in texts], dtype=np.int64)
    N, d0 = E0.shape; d1 = E1.shape[1]; NQall = len(gt1)
    m1 = d1 // a.dsub
    ev, trq = np.arange(a.nq), np.arange(a.nq, NQall)
    gt5_all = [np.array([int(r["index"]) for r in g["top_5_results"][:5]]) for g in gt1]
    bench = load_bench(a.bench or f"bench_{a.tag}.json", a.tag)
    log("=" * 78)
    log(f"[08] dataset={ds} tag={a.tag} seed={a.seed} N={N} nodes={a.nodes}  payload TB {sizes.mean():.0f} byte "
        f"(p95 {np.percentile(sizes, 95):.0f})  bench: {bench['src']}")

    # ---------------- pipeline giống 04b (adapter học trên S, PQ E1, hiệu chỉnh PROB)
    rnd = random.Random(a.seed)
    nid = np.array([rnd.getrandbits(63) for _ in range(a.nodes)], dtype=np.int64)
    P0 = pb.gen_proj(a.seed, d0, a.tables)
    P1 = pb.gen_proj(a.seed, d1, a.tables)
    perm = np.random.RandomState(a.seed).permutation(N)
    nS = max(a.tables * 20, int(round(a.frac * N)))
    S = perm[:nS]
    Wr, _, _ = q3.fit_ridge_cv(E1[S], E0[S], a.seed, (1e-3, 1e-2, 1e-1, 1.0, 10.0))
    Wf, _ = pb.fit_bridge(E0[S], E1[S], "ridge", a.seed)
    WfT = np.ascontiguousarray(Wf.T)
    C0 = cb0[np.arange(cb0.shape[0])[None, :], cd0].reshape(N, d0).astype(np.float32)
    n_i = np.linalg.norm(C0 @ Wf, axis=1)
    cb1 = pb.pq_train(E1[S], m1, a.seed)
    cd1 = pb.pq_encode(E1, cb1)
    anchors0 = pb.build_index(E0, P0, nid)
    anchors1 = pb.build_index(E1, P1, nid)
    qhat = Q1[trq] @ WfT
    xd, y = [], []
    qv1 = l2norm(Q1[trq])
    for i in range(len(trq)):
        y.append(mc.adc_ip(qv1[i], cb1, cd1[S]))
        xd.append(mc.adc_ip(Q0[trq][i], cb0, cd0[S]))
    Xcf, _ = mc.crossfit_adapter_x(E0, E1, C0, cb0, cd0, Q1[trq], S, S, a.folds, a.seed)
    Ycf = mc.e1_scores(Q1[trq], cb1, cd1, S)
    sig1 = mc.sigma_e1(Q1[trq], E1, cb1, cd1, S, a.cal_top)
    cals = dict(AD=dict(cal_a=None, cal_b=None, ols=mc.ols_top(list(Xcf), list(Ycf), a.cal_top), sig1=sig1),
                DU=dict(cal_a=None, cal_b=None, ols=mc.ols_top(xd, y, a.cal_top), sig1=sig1))

    q1 = l2norm(Q1[ev]); qr0 = l2norm(Q1[ev] @ Wr)
    qk = l2norm(Q1[ev] @ WfT); qkn = np.linalg.norm(Q1[ev] @ WfT, axis=1)
    q0 = Q0[ev]
    NA = mc.route_keys(qr0, P0, nid, a.k_query, T, a.cbits)
    ND = mc.route_keys(q0, P0, nid, a.k_query, T, a.cbits)
    NU = mc.route_keys(q1, P1, nid, a.k_query, T, a.cbits)
    keys = {}
    for nm, qv, PL in (("A", qr0, P0), ("D", q0, P0), ("U", q1, P1)):
        pk = pb.probe_keys_for(qv, PL, T, a.cbits)                  # L x (Q, T)
        keys[nm] = np.stack(pk, axis=1).reshape(len(ev), -1)         # (Q, L*T)
    sides = dict(A=[], D=[], U=[])
    for i in range(len(ev)):
        sides["A"].append(mc.Side2(NA[i], anchors0, a.nodes,
                                   (lambda r, i=i: ((lambda k: (k, k * qkn[i]))(mc.adc_ip(qk[i], cb0, cd0[r]) / n_i[r])))))
        sides["D"].append(mc.Side2(ND[i], anchors0, a.nodes,
                                   (lambda r, i=i: (-mc.adc_l2(q0[i], cb0, cd0[r]), mc.adc_ip(q0[i], cb0, cd0[r])))))
        sides["U"].append(mc.Side2(NU[i], anchors1, a.nodes,
                                   (lambda r, i=i: (-mc.adc_l2(q1[i], cb1, cd1[r]), mc.adc_ip(q1[i], cb1, cd1[r])))))
    log(f"pipeline xong ({time.time() - t0:.0f}s)")

    # ---------------- A. trạng thái cố định: vết từng query, chất lượng tự kiểm với 04b
    def state(f):
        nM = int(round(f * N))
        inE1 = np.zeros(N, dtype=bool); inE1[perm[:nM]] = True
        return dict(nM=nM, inE1=inE1, act=(~inE1, inE1), has=(bool((~inE1).any()), bool(inE1.any())),
                    load={"E0": np.bincount(anchors0[:, ~inE1].ravel(), minlength=a.nodes),
                          "U": np.bincount(anchors1[:, inE1].ravel(), minlength=a.nodes)},
                    share1=nM / N, share0=1.0 - nM / N)

    def one(qi, st, arm):
        side0 = {"AD": "A", "DU": "D", "E1": None}[arm]
        out = dict(sides=[], moved=0, nodes=0)
        l1 = x1 = None
        if st["has"][1]:
            n, l1, x1 = sides["U"][qi].ranked(st["act"][1], kap, NEED)
            tch = sides["U"][qi].touched()
            out["moved"] += int(np.minimum(st["load"]["U"][tch], kap).sum()); out["nodes"] += len(tch)
            out["sides"].append(keys["U"][qi])
        if side0 is not None and st["has"][0]:
            n0, l0, x0 = sides[side0][qi].ranked(st["act"][0], kap, NEED)
            tch = sides[side0][qi].touched()
            out["moved"] += int(np.minimum(st["load"]["E0"][tch], kap).sum()); out["nodes"] += len(tch)
            out["sides"].append(keys[side0][qi])
            lst = mc.fuse("PROB", l0, x0, l1 if l1 is not None else np.zeros(0, np.int64),
                          x1 if x1 is not None else np.zeros(0), NEED, st["share0"], st["share1"], cals[arm])
        else:
            lst = np.asarray(l1[:NEED], dtype=np.int64)
        g = set(gt5_all[ev[qi]].tolist())
        out["final"] = len(set(lst[:5].tolist()) & g) / 5.0
        out["rr"] = mc.rerank_hits(lst[:R], E1, Q1[ev[qi]], g)
        pool = lst[:R]
        out["fetched"] = pool[~st["inE1"][pool]]
        return out

    scen = []
    for f in fgrid:
        if f < 1:
            scen += [("DU", f), ("AD", f)]
        else:
            scen.append(("E1", f))
    traces, qual = {}, {}
    for arm, f in scen:
        st = state(f)
        tr = [one(qi, st, arm) for qi in range(len(ev))]
        nm = f"{arm}|{f:g}"
        traces[nm] = tr
        qual[nm] = dict(final_r5=100 * np.mean([t["final"] for t in tr]), rr=100 * np.mean([t["rr"] for t in tr]),
                        fetch=float(np.mean([len(t["fetched"]) for t in tr])),
                        nodes=float(np.mean([t["nodes"] for t in tr])), moved=float(np.mean([t["moved"] for t in tr])))
        log(f"  {nm:8s} final={qual[nm]['final_r5']:5.1f} R{R}={qual[nm]['rr']:5.1f} tải={qual[nm]['fetch']:4.1f} "
            f"nodes={qual[nm]['nodes']:4.0f} moved={qual[nm]['moved']:5.0f}")
    pre = "" if ds == "code" else f"{ds}_"
    fG = f"probeG_{pre}{a.tag}_s{a.seed}.json"
    check = None
    if os.path.exists(fG):
        G = json.load(open(fG))["results"]
        n, bad = 0, 0
        for arm, f in scen:
            fk = f"{f:g}"
            if fk not in G:
                continue
            ref = G[fk][{"DU": "DU_PROB", "AD": "AD_PROB", "E1": "E1ONLY"}[arm]]
            mine = qual[f"{arm}|{fk}"]
            for k1, k2 in (("final_r5", ref["final_r5"]), ("rr", ref["rerank"].get(str(R))),
                           ("fetch", ref["fetch"].get(str(R))), ("nodes", ref["nodes"]), ("moved", ref["moved"])):
                if k2 is None:
                    continue
                n += 1; bad += abs(mine[k1] - k2) > 1e-6
        check = dict(file=fG, n=n, bad=int(bad))
        log(f">>> chất lượng và vết so với 04b ({fG}): {n} giá trị, {'KHỚP' if bad == 0 else f'{bad} LỆCH'}")
    else:
        log(f">>> chưa có {fG}, bỏ qua tự kiểm chất lượng")

    # ---------------- overlay + mô phỏng chi phí
    net = Net(nid, a.seed, rmax=a.r_max)
    nsim = min(a.nq_sim, len(ev))

    def client_row(acc, n_fetch, moved, dual, n_hint=0):
        enc = bench["m1_q"] + (bench["m0_q"] if dual else 0.0)
        emb = pay_seconds(bench, n_fetch)
        disc_b = acc["find_rpc"] * B_FIND + acc["adc_rpc"] * B_ADC_REQ + moved * B_CAND
        pay_b = acc["pay_find_rpc"] * B_FIND + acc["get_rpc"] * B_GET_REQ + acc["pay_bytes_data"]
        return dict(rpc_find=acc["find_rpc"], rpc_adc=acc["adc_rpc"], rounds=acc["rounds"],
                    rpc_pay=acc["pay_find_rpc"] + acc["get_rpc"], rpc_hint=int(n_hint > 0),
                    rpc_total=acc["find_rpc"] + acc["adc_rpc"] + acc["pay_find_rpc"] + acc["get_rpc"] + int(n_hint > 0),
                    kb_disc=disc_b / 1024, kb_pay=pay_b / 1024, kb_hint=(16 + 8 * n_hint) / 1024 if n_hint else 0.0,
                    kb_total=(disc_b + pay_b + ((16 + 8 * n_hint) if n_hint else 0)) / 1024,
                    payloads=n_fetch, obj_fail=acc["obj_fail"], cpu_s=enc + emb,
                    lat_disc_ms=acc["t_disc"], lat_pay_ms=acc["t_pay"],
                    lat_nopay_ms=enc * 1000 + acc["t_disc"],
                    lat_total_ms=enc * 1000 + acc["t_disc"] + acc["t_pay"] + emb * 1000)

    res_A, ovl = {}, []
    for nm, tr in traces.items():
        dual = nm.startswith("DU")
        rows = []
        for qi in range(nsim):
            t = tr[qi]
            acc = net.run_query(t["sides"], t["fetched"], sizes, a.k_query, ovl if qi < 10 else None)
            rows.append(client_row(acc, len(t["fetched"]), t["moved"], dual))
        res_A[nm] = dict(quality=qual[nm], cost=summarize(rows))
        c = res_A[nm]["cost"]
        log(f"  {nm:8s} RPC={c['rpc_total']:7.0f} (find {c['rpc_find']:5.0f}, ADC {c['rpc_adc']:4.0f}, payload "
            f"{c['rpc_pay']:6.0f})  KB={c['kb_total']:7.1f}  payload={c['payloads']:4.1f}  CPU={c['cpu_s']:5.2f}s  "
            f"trễ p50={c['lat_total_ms_p50'] / 1000:5.2f}s p95={c['lat_total_ms_p95'] / 1000:5.2f}s "
            f"(không rerank {c['lat_nopay_ms_p50']:4.0f}ms)  [{time.time() - t0:.0f}s]")
    log(f"  lookup mô phỏng tìm lại {100 * np.mean(ovl):.1f}% tập K node XOR-gần nhất mà probe dùng")

    # ---------------- chi phí re-indexer mỗi record (mẫu)
    rng_s = np.random.RandomState(a.seed + 7)
    samp = rng_s.choice(np.setdiff1d(np.arange(N), S), size=min(a.reindex_sample, N - nS), replace=False)
    origin_r = net.nodes[int(rng_s.randint(len(net.nodes)))]
    k1 = np.stack([pb.pack63(E1[samp] @ P > 0) for P in P1], 1)
    k0 = np.stack([pb.pack63(E0[samp] @ P > 0) for P in P0], 1)
    racc = dict(find_rpc=0, rounds=0, adc_rpc=0, pay_find_rpc=0, pay_rounds=0, get_rpc=0, pay_bytes_data=0,
                shard_miss=0, objects=0, obj_fail=0, w_find_rpc=0, store_rpc=0, delete_rpc=0, w_bytes=0,
                t_fetch=0.0, t_write=0.0)
    for j, d in enumerate(samp.tolist()):
        p = net.env.process(net.reindex_one(d, int(sizes[d]), k1[j].tolist(), k0[j].tolist(), origin_r, racc, m1))
        net.env.run(until=p)
    ns = len(samp)
    per_rec = dict(rpc=(racc["pay_find_rpc"] + racc["get_rpc"] + racc["w_find_rpc"] + racc["store_rpc"]
                        + racc["delete_rpc"]) / ns,
                   rpc_write=(racc["w_find_rpc"] + racc["store_rpc"] + racc["delete_rpc"]) / ns,
                   store=racc["store_rpc"] / ns, delete=racc["delete_rpc"] / ns,
                   kb=(racc["pay_find_rpc"] * B_FIND + racc["get_rpc"] * B_GET_REQ + racc["pay_bytes_data"]
                       + racc["w_find_rpc"] * B_FIND + racc["w_bytes"]) / ns / 1024,
                   cpu_s=bench["pay"][20] / 20.0, t_fetch_ms=racc["t_fetch"] / ns, t_write_ms=racc["t_write"] / ns)
    log(f"re-indexer, mỗi record: RPC={per_rec['rpc']:.0f} (ghi {per_rec['rpc_write']:.0f}: {per_rec['store']:.0f} STORE, "
        f"{per_rec['delete']:.0f} DELETE) KB={per_rec['kb']:.1f} CPU={per_rec['cpu_s']:.2f}s "
        f"thời gian tải {per_rec['t_fetch_ms']:.0f}ms ghi {per_rec['t_write_ms']:.0f}ms")

    out = dict(argv=vars(a), N=int(N), nS=int(nS), bench=bench, check_04b=check, scenarios=res_A,
               reindex_per_record=per_rec, walk_overlap=float(np.mean(ovl)), payload_bytes_mean=float(sizes.mean()),
               lazy=None)

    # ---------------- B. phát lại dòng lazy từ vết của 06
    if a.lazy_trace and os.path.exists(a.lazy_trace):
        LT = json.load(open(a.lazy_trace))
        if int(LT["argv"]["seed"]) != a.seed or LT["argv"]["tag"] != a.tag or LT["argv"].get("dataset", "code") != ds:
            log(f"*** vết {a.lazy_trace} không cùng seed/tag/dataset, bỏ qua phần B")
        else:
            lazy = {}
            for key, tr in sorted(LT["traces"].items()):
                if key.startswith("para|"):
                    continue                               # khoá probe của paraphrase không dựng ở đây
                pol = key.split("|")[2]
                rows, wins = [], []
                for t in range(0, len(tr), a.lazy_every):
                    s = tr[t]
                    qi = s["qi"]
                    sd = ([keys["A"][qi]] if s["h0"] else []) + ([keys["U"][qi]] if s["h1"] else [])
                    acc = net.run_query(sd, np.asarray(s["fe"], dtype=np.int64), sizes, a.k_query)
                    nh = len(s["fe"]) if pol.startswith("lazy") else 0
                    r_ = client_row(acc, len(s["fe"]), s["mv"], False, nh)
                    r_["t"] = t
                    rows.append(r_)
                migr = np.array([len(s["mi"]) for s in tr], dtype=float)
                W = a.lazy_window
                for w0 in range(0, len(tr), W):
                    rw = [r_ for r_ in rows if w0 <= r_["t"] < w0 + W]
                    mw = float(migr[w0:w0 + W].mean())
                    sm = summarize([{k: v for k, v in r_.items() if k != "t"} for r_ in rw])
                    wins.append(dict(t_end=min(len(tr), w0 + W), client=sm, migrated_per_query=mw,
                                     reindexer_rpc_per_query=mw * per_rec["rpc"],
                                     reindexer_kb_per_query=mw * per_rec["kb"],
                                     reindexer_cpu_s_per_query=mw * per_rec["cpu_s"]))
                tot = summarize([{k: v for k, v in r_.items() if k != "t"} for r_ in rows])
                lazy[key] = dict(policy=pol, client=tot, windows=wins, migrated_total=int(migr.sum()),
                                 reindexer_rpc_per_query=float(migr.mean()) * per_rec["rpc"],
                                 reindexer_kb_per_query=float(migr.mean()) * per_rec["kb"],
                                 reindexer_cpu_s_per_query=float(migr.mean()) * per_rec["cpu_s"])
                c = tot
                log(f"  lazy {key:22s} client: RPC={c['rpc_total']:7.0f} KB={c['kb_total']:7.1f} payload={c['payloads']:4.1f} "
                    f"CPU={c['cpu_s']:5.2f}s trễ p50={c['lat_total_ms_p50'] / 1000:5.2f}s | re-indexer/truy vấn: "
                    f"{lazy[key]['reindexer_rpc_per_query']:6.0f} RPC {lazy[key]['reindexer_cpu_s_per_query']:5.2f}s CPU "
                    f"(migrate {migr.sum():.0f} record)  [{time.time() - t0:.0f}s]")
            out["lazy"] = lazy

    fn = a.out or f"probeS_{pre}{a.tag}_s{a.seed}.json"
    json.dump(out, open(fn, "w"), indent=1)
    log(f"\n-> {fn}   ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
