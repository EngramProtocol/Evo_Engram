#!/usr/bin/env python3
"""
09_sim_e2e.py  —  CHẠY TRÊN node-dal-02 (CPU), từ thư mục gốc repo (cần src/ của V-Engram). Đợt 5.

Góp ý của thầy: simulator 08 đo chi phí của lookup lặp thật nhưng recall vẫn lấy từ probe, mà probe giả định
mỗi khoá probe chạm đúng K node XOR-gần nhất (lookup mô phỏng chỉ tìm lại 77 đến 88% tập đó). Script này đo
recall từ CHÍNH tập node mà Ripple Search trong SimPy trả về:

  khám phá   mỗi khoá probe chạy iterative_find_k_closest_nodes của src/routing.py từ một node gốc ngẫu nhiên
             (như 08); tập node chạm của một phía = hợp các node trả về
  ứng viên   mỗi node chạm chấm ADC trên record của nó (record nằm ở anchor như probe) và trả top-kappa;
             client gộp hai phía bằng PROB, đúng hàm của 04b/06
  recall     final@5 và rerank@20 tính trên danh sách đó; payload phải tải là record E0 trong pool rerank
             THẬT (không phải pool của probe), nên chi phí payload cũng đi theo lookup thật

Hai phần:
  A. trạng thái cố định f ∈ --fmig, như bảng chi phí của 08: DU (dual), AD (adapter + E1, PROB), E1 ở f = 1.
     Mỗi query đánh giá (--nq-sim) đo cả recall theo probe (oracle) lẫn theo lookup thật, ghép cặp.
     Payload chỉ mô phỏng cho --nq-pay query đầu (như 08) để giữ thời gian chạy.
  B. dòng Zipf vòng kín (--stream > 0): static, lazy, bg như 06 (re-indexer không giới hạn, gộp PROB, khoá
     E1 u). Mỗi lượt truy vấn chạy lookup thật, gợi ý migrate lấy từ pool THẬT, nên thứ tự migrate cũng đi theo
     lookup thật. bg migrate cùng số record với lazy của chính chế độ đó. Chi phí client mô phỏng mỗi
     --pay-every lượt, chi phí re-indexer mỗi record như 08.

Tự kiểm:
  (1) chất lượng oracle ở mọi trạng thái cố định trùng probeG (04b) như 08
  (2) dựng lại danh sách từ tập node của oracle qua đúng đường "lookup thật" phải trùng oracle từng query
      (--selfcheck-n query đầu mỗi trạng thái): kiểm phần dựng ứng viên, cache điểm, kappa và PROB
  (3) dòng vòng kín chạy với tập node oracle phải trùng 06 (probeL_/probeLR_ cùng seed): final, rerank, số
      payload, số record mới, f cuối, nodes, moved

Bổ sung đợt 6 (mặc định giữ đúng từng số của đợt 5, tự kiểm (5) với probeE2E_ của đợt 5 nếu có):
  --pair-src pq   adapter học trên bản tái tạo PQ c_o như 04b/06 --pair-src pq (cấu hình triển khai đầy đủ: cặp
                  học từ PQ cộng lookup thật); tự kiểm (1) với probeG_..._pq.json, (3) với probeL_..._ku_pq.json
  --factorial 1   tách lookup và lịch migrate: với lazy và bg, phát lại lịch migrate của lượt probe rồi đo bằng
                  lookup thật, và phát lại lịch migrate của lượt lookup thật rồi đo bằng probe. Tự kiểm (4): phát
                  lại lịch probe và đo bằng probe phải trùng chính lượt probe; (4b) số record mới, f cuối và tỉ lệ
                  GT ở E1 chỉ phụ thuộc lịch nên mỗi lượt phát lại phải trùng lượt gốc của lịch đó. File ra probeE2F_...
  --noise-replay 1  thêm một lượt phát lại lịch của lookup thật và đo lại bằng lookup thật (node gốc ngẫu nhiên
                  khác): chênh với lượt gốc là nhiễu của chính lookup, làm mốc để đọc các ô của bảng 2x2
  --fixed 0       bỏ phần A (dùng cho seed thêm, chỉ cần dòng)

CHẠY: python3 evo/09_sim_e2e.py --tag bgebase --seed 20235956
      python3 evo/09_sim_e2e.py --dataset code100kfq --tag bgebase --seed 3 --nodes 50000 --frac 0.02 --stream 0
"""
import argparse, importlib.util, json, os, random, sys, time

import numpy as np

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("m8", os.path.join(_here, "08_sim_evo.py"))
m8 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m8)
mc, q3, pb = m8.mc, m8.q3, m8.pb
log, l2norm = m8.log, m8.l2norm
B_FIND, B_ADC_REQ, B_CAND, B_GET_REQ = m8.B_FIND, m8.B_ADC_REQ, m8.B_CAND, m8.B_GET_REQ
np.seterr(invalid='ignore', divide='ignore')


class NetE2E(m8.Net):
    """Overlay của 08, thêm một truy vấn mà danh sách ứng viên dựng từ tập node lookup thật trả về."""

    def probe_obs(self, key, origin, contacted, acc, k):
        nodes, hops, rpcs = self.walk(key, origin, k)
        for _ in range(hops):
            yield self.env.timeout(self.rtt())
        acc["find_rpc"] += rpcs; acc["rounds"] += hops
        new = [n for n in nodes if n.node_id not in contacted]
        for n in new:
            contacted.add(n.node_id)
        if new:
            yield self.env.all_of([self.env.process(self._adc(acc)) for _ in new])

    def query_obs(self, side_keys, decide, sizes, acc, k, pay):
        env = self.env
        origin = self.rng.choice(self.nodes)
        t0 = env.now
        procs, cont = [], []
        for keys in side_keys:
            c = set()
            cont.append(c)
            procs += [env.process(self.probe_obs(kk, origin, c, acc, k)) for kk in keys]
        if procs:
            yield env.all_of(procs)
        acc["t_disc"] = env.now - t0
        found = [np.fromiter((self.idx[x] for x in c), dtype=np.int64, count=len(c)) for c in cont]
        fetched = decide(found)
        t1 = env.now
        if pay and len(fetched):
            yield env.all_of([env.process(self.fetch(int(d), sizes[int(d)], origin, acc)) for d in fetched])
        acc["t_pay"] = env.now - t1

    def run_obs(self, side_keys, decide, sizes, k, pay):
        acc = dict(find_rpc=0, rounds=0, adc_rpc=0, pay_find_rpc=0, pay_rounds=0, get_rpc=0, pay_bytes_data=0,
                   shard_miss=0, objects=0, obj_fail=0, t_disc=0.0, t_pay=0.0)
        p = self.env.process(self.query_obs(side_keys, decide, sizes, acc, k, pay))
        self.env.run(until=p)
        return acc


class ScoreCache:
    """Điểm (key, x) của từng document cho một (phía, query), khởi đầu từ tập reachable của probe, tính thêm
    khi lookup thật chạm node ngoài tập đó. Điểm từng document không phụ thuộc lô tính nên trùng đúng probe."""

    def __init__(self, N):
        self.N, self.d = N, {}

    def fn(self, name, qi, oracle_side, base):
        ent = self.d.get((name, qi))
        if ent is None:
            known = np.zeros(self.N, dtype=bool)
            K = np.zeros(self.N, dtype=oracle_side.key.dtype)
            X = np.zeros(self.N, dtype=oracle_side.x.dtype)
            known[oracle_side.reach] = True
            K[oracle_side.reach] = oracle_side.key
            X[oracle_side.reach] = oracle_side.x
            ent = self.d[(name, qi)] = (known, K, X)
        known, K, X = ent

        def f(r):
            miss = r[~known[r]]
            if len(miss):
                k2, x2 = base(miss)
                K[miss] = k2; X[miss] = x2; known[miss] = True
            return K[r], X[r]
        return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--dataset", default="code")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--seed", type=int, default=20235956)
    ap.add_argument("--nodes", type=int, default=10000)
    ap.add_argument("--nq", type=int, default=300)
    ap.add_argument("--nq-sim", type=int, default=300, help="số query đánh giá đầu tiên đo recall bằng lookup thật")
    ap.add_argument("--nq-pay", type=int, default=100, help="trong đó số query mô phỏng cả tải payload (như 08)")
    ap.add_argument("--tables", type=int, default=5)
    ap.add_argument("--k-query", type=int, default=20)
    ap.add_argument("--probes", type=int, default=8)
    ap.add_argument("--cbits", type=int, default=16)
    ap.add_argument("--dsub", type=int, default=2)
    ap.add_argument("--kappa", type=int, default=30)
    ap.add_argument("--frac", type=float, default=0.10)
    ap.add_argument("--fmig", default="0,0.1,0.5,0.9,1.0")
    ap.add_argument("--R", type=int, default=20)
    ap.add_argument("--need", type=int, default=100)
    ap.add_argument("--cal-top", type=int, default=30)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--r-max", type=int, default=20)
    ap.add_argument("--bench", default=None)
    ap.add_argument("--selfcheck-n", type=int, default=30)
    ap.add_argument("--stream", type=int, default=3000, help="độ dài dòng vòng kín; 0 = bỏ phần B")
    ap.add_argument("--zipf", type=float, default=1.0)
    ap.add_argument("--n-heldout", type=int, default=100)
    ap.add_argument("--policies", default="static,lazy,bg")
    ap.add_argument("--pay-every", type=int, default=10)
    ap.add_argument("--window", type=int, default=150)
    ap.add_argument("--reindex-sample", type=int, default=150)
    ap.add_argument("--check-l", default="auto", help="file 06 để tự kiểm dòng oracle; auto = tên mặc định; none = bỏ")
    ap.add_argument("--pair-src", default="exact", choices=["exact", "pq"],
                    help="vế M0 của cặp học adapter: exact = embedding M0 đầy đủ, pq = bản tái tạo PQ của record E0")
    ap.add_argument("--fixed", type=int, default=1, help="1 = chạy phần A (trạng thái cố định)")
    ap.add_argument("--factorial", type=int, default=0, help="1 = phát lại chéo lịch migrate và cách đo (đợt 6)")
    ap.add_argument("--noise-replay", type=int, default=0, help="1 = thêm lượt lịch thật + đo thật lần hai (mốc nhiễu)")
    ap.add_argument("--check-e2e", default="auto", help="file probeE2E_ đợt 5 để tự kiểm (5); auto = tên mặc định; none = bỏ")
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
    bench = m8.load_bench(a.bench or f"bench_{a.tag}.json", a.tag)
    log("=" * 78)
    log(f"[09] dataset={ds} tag={a.tag} seed={a.seed} N={N} nodes={a.nodes}  nq-sim={a.nq_sim} nq-pay={a.nq_pay} "
        f"dòng={a.stream}  bench: {bench['src']}")

    # ---------------- pipeline y hệt 08 (adapter học trên S, PQ E1, hiệu chỉnh PROB)
    rnd = random.Random(a.seed)
    nid = np.array([rnd.getrandbits(63) for _ in range(a.nodes)], dtype=np.int64)
    P0 = pb.gen_proj(a.seed, d0, a.tables)
    P1 = pb.gen_proj(a.seed, d1, a.tables)
    perm = np.random.RandomState(a.seed).permutation(N)
    nS = max(a.tables * 20, int(round(a.frac * N)))
    S = perm[:nS]
    C0 = cb0[np.arange(cb0.shape[0])[None, :], cd0].reshape(N, d0).astype(np.float32)
    X0 = E0 if a.pair_src == "exact" else C0          # vế M0 của cặp học (đợt 6: pq)
    Wr, _, _ = q3.fit_ridge_cv(E1[S], X0[S], a.seed, (1e-3, 1e-2, 1e-1, 1.0, 10.0))
    Wf, _ = pb.fit_bridge(X0[S], E1[S], "ridge", a.seed)
    WfT = np.ascontiguousarray(Wf.T)
    n_i = np.linalg.norm(C0 @ Wf, axis=1)
    cb1 = pb.pq_train(E1[S], m1, a.seed)
    cd1 = pb.pq_encode(E1, cb1)
    anchors0 = pb.build_index(E0, P0, nid)
    anchors1 = pb.build_index(E1, P1, nid)
    xd, y = [], []
    qv1 = l2norm(Q1[trq])
    for i in range(len(trq)):
        y.append(mc.adc_ip(qv1[i], cb1, cd1[S]))
        xd.append(mc.adc_ip(Q0[trq][i], cb0, cd0[S]))
    Xcf, _ = mc.crossfit_adapter_x(X0, E1, C0, cb0, cd0, Q1[trq], S, S, a.folds, a.seed)
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
        pk = pb.probe_keys_for(qv, PL, T, a.cbits)
        keys[nm] = np.stack(pk, axis=1).reshape(len(ev), -1)
    score = dict(
        A=[(lambda r, i=i: ((lambda k: (k, k * qkn[i]))(mc.adc_ip(qk[i], cb0, cd0[r]) / n_i[r]))) for i in range(len(ev))],
        D=[(lambda r, i=i: (-mc.adc_l2(q0[i], cb0, cd0[r]), mc.adc_ip(q0[i], cb0, cd0[r]))) for i in range(len(ev))],
        U=[(lambda r, i=i: (-mc.adc_l2(q1[i], cb1, cd1[r]), mc.adc_ip(q1[i], cb1, cd1[r]))) for i in range(len(ev))])
    anch = dict(A=anchors0, D=anchors0, U=anchors1)
    NN = dict(A=NA, D=ND, U=NU)
    sides = {nm: [mc.Side2(NN[nm][i], anch[nm], a.nodes, score[nm][i]) for i in range(len(ev))] for nm in ("A", "D", "U")}
    cache = ScoreCache(N)
    empty = np.zeros(0, dtype=np.int64)

    def obs_side(nm, qi, found):
        """Side2 dựng từ tập node mà lookup thật trả về (một 'probe' gồm đúng các node đó)."""
        return mc.Side2(np.asarray(found, dtype=np.int64).reshape(1, 1, -1), anch[nm], a.nodes,
                        cache.fn(nm, qi, sides[nm][qi], score[nm][qi]))

    log(f"pipeline xong ({time.time() - t0:.0f}s)")

    # ---------------- A. trạng thái cố định
    def state(f):
        nM = int(round(f * N))
        inE1 = np.zeros(N, dtype=bool); inE1[perm[:nM]] = True
        return dict(nM=nM, inE1=inE1, act=(~inE1, inE1), has=(bool((~inE1).any()), bool(inE1.any())),
                    load={"E0": np.bincount(anchors0[:, ~inE1].ravel(), minlength=a.nodes),
                          "U": np.bincount(anchors1[:, inE1].ravel(), minlength=a.nodes)},
                    share1=nM / N, share0=1.0 - nM / N)

    def side_names(st, arm):
        s0 = {"AD": "A", "DU": "D", "E1": None}[arm]
        return (["U"] if st["has"][1] else []) + ([s0] if (s0 is not None and st["has"][0]) else [])

    def assemble(qi, st, arm, sd):
        """Đúng one() của 08, với sd = {tên phía: Side2} (oracle hoặc dựng từ lookup thật)."""
        s0 = {"AD": "A", "DU": "D", "E1": None}[arm]
        out = dict(moved=0, nodes=0)
        l1 = x1 = None
        garr = gt5_all[ev[qi]]
        hits = 0
        if st["has"][1]:
            n, l1, x1 = sd["U"].ranked(st["act"][1], kap, NEED)
            tch = sd["U"].touched()
            out["moved"] += int(np.minimum(st["load"]["U"][tch], kap).sum()); out["nodes"] += len(tch)
            hits += int((np.isin(garr, sd["U"].reach) & st["act"][1][garr]).sum())
        if s0 is not None and st["has"][0]:
            n0, l0, x0 = sd[s0].ranked(st["act"][0], kap, NEED)
            tch = sd[s0].touched()
            out["moved"] += int(np.minimum(st["load"]["E0"][tch], kap).sum()); out["nodes"] += len(tch)
            hits += int((np.isin(garr, sd[s0].reach) & st["act"][0][garr]).sum())
            lst = mc.fuse("PROB", l0, x0, l1 if l1 is not None else np.zeros(0, np.int64),
                          x1 if x1 is not None else np.zeros(0), NEED, st["share0"], st["share1"], cals[arm])
        else:
            lst = np.asarray(l1[:NEED], dtype=np.int64)
        g = set(garr.tolist())
        out["final"] = len(set(lst[:5].tolist()) & g) / 5.0
        out["rr"] = mc.rerank_hits(lst[:R], E1, Q1[ev[qi]], g)
        out["reach"] = hits / 5.0
        pool = lst[:R]
        out["fetched"] = pool[~st["inE1"][pool]]
        return out

    def client_row(acc, n_fetch, moved, dual, n_hint=0):
        """Như client_row của 08."""
        enc = bench["m1_q"] + (bench["m0_q"] if dual else 0.0)
        emb = m8.pay_seconds(bench, n_fetch)
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

    def recov(found, oracle_side):
        tru = oracle_side.touched()
        return (len(np.intersect1d(found, tru, assume_unique=True)) / max(1, len(tru)),
                len(found) / max(1, len(tru)))

    scen = []
    for f in fgrid:
        scen += [("DU", f), ("AD", f)] if f < 1 else [("E1", f)]
    nsim = min(a.nq_sim, len(ev))
    oracle, checks = {}, {}
    scen_run = scen if a.fixed else []
    sfx = "" if a.pair_src == "exact" else "_pq"
    for arm, f in scen_run:
        st = state(f)
        nm = f"{arm}|{f:g}"
        oracle[nm] = [assemble(qi, st, arm, {k: sides[k][qi] for k in side_names(st, arm)}) for qi in range(len(ev))]
    # (1) oracle khớp 04b
    pre = "" if ds == "code" else f"{ds}_"
    fG = f"probeG_{pre}{a.tag}_s{a.seed}{sfx}.json"
    try:
        G = json.load(open(fG))["results"] if os.path.exists(fG) else None
    except Exception as e:                                   # tự kiểm không được làm hỏng lượt chạy
        log(f"*** không đọc được {fG}: {e}"); G = None
    if a.fixed and G is not None:
        n, bad = 0, 0
        for arm, f in scen:
            fk = f"{f:g}"
            if fk not in G:
                continue
            ref = G[fk][{"DU": "DU_PROB", "AD": "AD_PROB", "E1": "E1ONLY"}[arm]]
            ref = dict(ref, fetch=ref.get("fetch", {}), rerank=ref.get("rerank", {}))
            tr = oracle[f"{arm}|{fk}"]
            mine = dict(final_r5=100 * np.mean([t["final"] for t in tr]), rr=100 * np.mean([t["rr"] for t in tr]),
                        fetch=float(np.mean([len(t["fetched"]) for t in tr])), reach=100 * np.mean([t["reach"] for t in tr]),
                        nodes=float(np.mean([t["nodes"] for t in tr])), moved=float(np.mean([t["moved"] for t in tr])))
            for k1, k2 in (("final_r5", ref.get("final_r5")), ("rr", ref["rerank"].get(str(R))), ("reach", ref.get("reach_r5")),
                           ("fetch", ref["fetch"].get(str(R))), ("nodes", ref["nodes"]), ("moved", ref["moved"])):
                if k2 is None:
                    continue
                n += 1; bad += abs(mine[k1] - k2) > 1e-6
        checks["oracle_vs_04b"] = dict(file=fG, n=n, bad=int(bad))
        log(f">>> (1) chất lượng oracle so với 04b ({fG}): {n} giá trị, {'KHỚP' if bad == 0 else f'{bad} LỆCH'}")
    else:
        log(f">>> (1) chưa có {fG}, bỏ qua tự kiểm với 04b")
    # (2) đường dựng từ tập node, chạy với tập node của oracle, phải trùng oracle
    n, bad = 0, 0
    for arm, f in scen_run:
        st = state(f)
        for qi in range(min(a.selfcheck_n, len(ev))):
            sd = {k: obs_side(k, qi, sides[k][qi].touched()) for k in side_names(st, arm)}
            mine, ref = assemble(qi, st, arm, sd), oracle[f"{arm}|{f:g}"][qi]
            for k in ("final", "rr", "reach", "nodes", "moved"):
                n += 1; bad += mine[k] != ref[k]
            n += 1; bad += not np.array_equal(mine["fetched"], ref["fetched"])
    if a.fixed:
        checks["rebuild_from_oracle_nodes"] = dict(n=n, bad=int(bad))
        log(f">>> (2) dựng lại từ tập node oracle so với oracle: {n} giá trị, {'KHỚP' if bad == 0 else f'{bad} LỆCH'}")

    net = NetE2E(nid, a.seed, rmax=a.r_max)
    res_A = {}
    for arm, f in scen_run:
        st = state(f)
        nm = f"{arm}|{f:g}"
        names = side_names(st, arm)
        per_q, rows = [], []
        for qi in range(nsim):
            box = {}

            def decide(found, qi=qi):
                sd = {k: obs_side(k, qi, fd) for k, fd in zip(names, found)}
                o = assemble(qi, st, arm, sd)
                o["recov"] = {k: recov(fd, sides[k][qi]) for k, fd in zip(names, found)}
                box["o"] = o
                return o["fetched"]
            pay = qi < a.nq_pay
            acc = net.run_obs([keys[k][qi] for k in names], decide, sizes, a.k_query, pay)
            o, orc = box["o"], oracle[nm][qi]
            per_q.append(dict(final_o=orc["final"], rr_o=orc["rr"], reach_o=orc["reach"], fetch_o=len(orc["fetched"]),
                              final=o["final"], rr=o["rr"], reach=o["reach"], fetch=len(o["fetched"]),
                              nodes=o["nodes"], moved=o["moved"], recov=o["recov"]))
            if pay:
                rows.append(client_row(acc, len(o["fetched"]), o["moved"], arm == "DU"))
        P = {k: np.asarray([p[k] for p in per_q], dtype=float) for k in ("final_o", "rr_o", "reach_o", "fetch_o",
                                                                          "final", "rr", "reach", "fetch")}
        rec = {k: dict(found_frac=float(np.mean([p["recov"][k][0] for p in per_q])),
                       size_ratio=float(np.mean([p["recov"][k][1] for p in per_q]))) for k in names}
        dfin, drr = 100 * (P["final"] - P["final_o"]), 100 * (P["rr"] - P["rr_o"])
        res_A[nm] = dict(
            n=nsim, oracle=dict(final_r5=100 * P["final_o"].mean(), rr=100 * P["rr_o"].mean(),
                                reach=100 * P["reach_o"].mean(), fetch=float(P["fetch_o"].mean())),
            sim=dict(final_r5=100 * P["final"].mean(), rr=100 * P["rr"].mean(), reach=100 * P["reach"].mean(),
                     fetch=float(P["fetch"].mean())),
            diff=dict(final_mean=float(dfin.mean()), final_se=float(dfin.std(ddof=1) / np.sqrt(nsim)) if nsim > 1 else 0.0,
                      rr_mean=float(drr.mean()), rr_se=float(drr.std(ddof=1) / np.sqrt(nsim)) if nsim > 1 else 0.0),
            recovery=rec, cost=(m8.summarize(rows) if rows else None),
            per_query=dict(final_o=P["final_o"].tolist(), final=P["final"].tolist(),
                           rr_o=P["rr_o"].tolist(), rr=P["rr"].tolist()))
        r = res_A[nm]
        c = r["cost"] or {}
        log(f"  {nm:8s} final oracle={r['oracle']['final_r5']:5.1f} thật={r['sim']['final_r5']:5.1f} "
            f"({r['diff']['final_mean']:+5.1f}±{r['diff']['final_se']:.1f})  R{R} oracle={r['oracle']['rr']:5.1f} "
            f"thật={r['sim']['rr']:5.1f} ({r['diff']['rr_mean']:+5.1f}±{r['diff']['rr_se']:.1f})  reach "
            f"{r['oracle']['reach']:5.1f}->{r['sim']['reach']:5.1f}  tìm lại node: "
            + " ".join(f"{k}={100 * v['found_frac']:.0f}%" for k, v in rec.items())
            + (f" | RPC={c['rpc_total']:7.0f} payload={c['payloads']:4.1f} p50={c['lat_total_ms_p50'] / 1000:5.2f}s"
               if c else "") + f"  [{time.time() - t0:.0f}s]")

    # ---------------- chi phí re-indexer mỗi record (đúng cách của 08)
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
                   kb=(racc["pay_find_rpc"] * B_FIND + racc["get_rpc"] * B_GET_REQ + racc["pay_bytes_data"]
                       + racc["w_find_rpc"] * B_FIND + racc["w_bytes"]) / ns / 1024,
                   cpu_s=bench["pay"][20] / 20.0)
    log(f"re-indexer, mỗi record: RPC={per_rec['rpc']:.0f} KB={per_rec['kb']:.1f} CPU={per_rec['cpu_s']:.2f}s")

    out = dict(argv=vars(a), N=int(N), nS=int(nS), bench=bench, checks=checks, fixed=res_A,
               reindex_per_record=per_rec, stream=None)

    # ---------------- B. dòng Zipf vòng kín (như 06: gộp PROB, khoá E1 u, re-indexer không giới hạn)
    if a.stream > 0:
        Rk = R
        cal = cals["AD"]
        rng = np.random.RandomState(a.seed + 41)
        order = rng.permutation(len(ev))
        pool_q = order[:len(ev) - a.n_heldout]
        bg_order = perm[nS:]
        z = a.zipf
        ranks = np.random.RandomState(a.seed + 43).permutation(len(pool_q))
        pz = 1.0 / (ranks + 1.0) ** z
        pz /= pz.sum()
        stream = pool_q[np.random.RandomState(a.seed + 47 + int(1000 * z)).choice(len(pool_q), size=a.stream, p=pz)]

        def one_query(qi, sA, sK, inE1, load0, loadK):
            """Đúng one_query của 06 (gộp PROB, không có biến thể paraphrase)."""
            q1v = Q1[ev[qi]]
            gq = gt5_all[ev[qi]]
            act0, act1 = ~inE1, inE1
            has0, has1 = bool(act0.any()), bool(act1.any())
            share1 = float(inE1.mean())
            _, l0, x0 = sA.ranked(act0, kap, Rk)
            _, l1, y1 = sK.ranked(act1, kap, Rk)
            lst = mc.fuse("PROB", l0, x0, l1, y1, Rk, 1.0 - share1, share1, cal)
            g = set(np.asarray(gq).tolist())
            fin = len(set(lst[:5].tolist()) & g) / 5.0
            pool = lst[:Rk]
            e0m = ~inE1[pool]
            keep = np.ones(len(pool), dtype=bool)
            sc = np.full(len(pool), -np.inf, dtype=np.float64)
            if e0m.any():
                sc[e0m] = E1[pool[e0m]] @ q1v
            e1m = inE1[pool]
            if e1m.any():
                ymap = dict(zip(l1.tolist(), y1.tolist()))
                sc[e1m] = [ymap[d] for d in pool[e1m].tolist()]
            ordr = np.argsort(-sc, kind="stable")
            ordr = np.concatenate([ordr[keep[ordr]], np.flatnonzero(~keep)])
            top = pool[ordr[:5]]
            rr = len(set(top.tolist()) & g) / 5.0
            tA, tK = sA.touched(), sK.touched()
            nodes = (len(tA) if has0 else 0) + (len(tK) if has1 else 0)
            moved = ((np.minimum(load0[tA], kap).sum() if has0 else 0)
                     + (np.minimum(loadK[tK], kap).sum() if has1 else 0))
            return fin, rr, pool[e0m], nodes, int(moved)

        def migrate(docs, inE1, load0, loadK):
            docs = np.asarray([d for d in np.unique(docs) if not inE1[d]], dtype=np.int64)
            if len(docs):
                inE1[docs] = True
                np.subtract.at(load0, anchors0[:, docs].ravel(), 1)
                np.add.at(loadK, anchors1[:, docs].ravel(), 1)
            return docs

        def run_stream(policy, bg_rate, mode, sched=None, pay_cost=True):
            """sched: danh sách record migrate ở từng lượt (phát lại một lịch có sẵn thay cho chính sách)."""
            inE1 = np.zeros(N, dtype=bool); inE1[S] = True
            load0 = np.bincount(anchors0[:, ~inE1].ravel(), minlength=a.nodes)
            loadK = np.bincount(anchors1[:, inE1].ravel(), minlength=a.nodes)
            ptr, accb = 0, 0.0
            rec = {k: [] for k in ("final", "rr", "fetch", "new", "nodes", "moved", "f", "gtE1", "recA", "recK", "mig")}
            rows = []
            for t in range(len(stream)):
                qi = int(stream[t])
                gq = gt5_all[ev[qi]]
                rec["gtE1"].append(float(inE1[np.asarray(gq)].mean()))
                h0, h1 = bool((~inE1).any()), bool(inE1.any())
                if mode == "oracle":
                    fin, rr, fetched, nodes, moved = one_query(qi, sides["A"][qi], sides["U"][qi], inE1, load0, loadK)
                    rA = rK = 1.0
                else:
                    names = (["A"] if h0 else []) + (["U"] if h1 else [])
                    box = {}

                    def decide(found, qi=qi, names=names):
                        fd = dict(zip(names, found))
                        sA = obs_side("A", qi, fd.get("A", empty))
                        sK = obs_side("U", qi, fd.get("U", empty))
                        box["r"] = one_query(qi, sA, sK, inE1, load0, loadK)
                        box["rA"] = recov(fd["A"], sides["A"][qi])[0] if "A" in fd else float("nan")
                        box["rK"] = recov(fd["U"], sides["U"][qi])[0] if "U" in fd else float("nan")
                        return box["r"][2]
                    pay = pay_cost and (t % a.pay_every == 0)
                    acc = net.run_obs([keys[k][qi] for k in names], decide, sizes, a.k_query, pay)
                    fin, rr, fetched, nodes, moved = box["r"]
                    rA, rK = box["rA"], box["rK"]
                    if pay:
                        r_ = client_row(acc, len(fetched), moved, False, len(fetched) if policy == "lazy" else 0)
                        r_["t"] = t
                        rows.append(r_)
                new = 0
                migs = []
                if sched is not None:
                    mg = migrate(sched[t], inE1, load0, loadK); new += len(mg); migs.append(mg)
                else:
                    if policy == "lazy":
                        mg = migrate(fetched, inE1, load0, loadK); new += len(mg); migs.append(mg)
                    if policy == "bg":
                        accb += bg_rate
                        k = int(accb); accb -= k
                        take = []
                        while len(take) < k and ptr < len(bg_order):
                            d = int(bg_order[ptr]); ptr += 1
                            if not inE1[d]:
                                take.append(d)
                        mg = migrate(take, inE1, load0, loadK); new += len(mg); migs.append(mg)
                rec["mig"].append(np.concatenate(migs) if migs else empty)
                for kk, v in (("final", fin), ("rr", rr), ("fetch", len(fetched)), ("new", new), ("nodes", nodes),
                              ("moved", moved), ("f", float(inE1.mean())), ("recA", rA), ("recK", rK)):
                    rec[kk].append(v)
            return rec, rows

        def totals(rec):
            return dict(final=100 * float(np.mean(rec["final"])), rr=100 * float(np.mean(rec["rr"])),
                        fetch=float(np.mean(rec["fetch"])), new=float(np.mean(rec["new"])),
                        nodes=float(np.mean(rec["nodes"])), moved=float(np.mean(rec["moved"])),
                        f_end=float(rec["f"][-1]), gtE1=100 * float(np.mean(rec["gtE1"])),
                        found_A=float(np.nanmean(rec["recA"])), found_K=float(np.nanmean(rec["recK"])))

        def windows(rec, W):
            outw = []
            for s0 in range(0, len(rec["final"]), W):
                sl = slice(s0, min(len(rec["final"]), s0 + W))
                outw.append(dict(t_end=sl.stop, f=rec["f"][sl.stop - 1], final=100 * float(np.mean(rec["final"][sl])),
                                 rr=100 * float(np.mean(rec["rr"][sl])), fetch=float(np.mean(rec["fetch"][sl])),
                                 gtE1=100 * float(np.mean(rec["gtE1"][sl]))))
            return outw

        pols = [p for p in ("static", "lazy", "bg") if p in a.policies.split(",")]
        stream_out = {}
        done_by = {}
        for mode in ("oracle", "sim"):
            done = done_by.setdefault(mode, {})
            for pol in pols:
                rate = 0.0
                if pol == "bg":
                    if "lazy" not in done:
                        log("  (bg cần lazy chạy trước) bỏ qua"); continue
                    rate = (done["lazy"]["f"][-1] * N - nS) / len(stream)
                tt0 = time.time()
                rec, rows = run_stream(pol, rate, mode)
                done[pol] = rec
                tt = totals(rec)
                entry = stream_out.setdefault(pol, {})
                entry[mode] = dict(totals=tt, windows=windows(rec, a.window), bg_rate=rate)
                if mode == "oracle" and a.factorial:
                    entry["oracle"]["per_arrival"] = dict(final=rec["final"], rr=rec["rr"])
                if mode == "sim":
                    migr = np.asarray(rec["new"], dtype=float)
                    entry["sim"]["client"] = m8.summarize([{k: v for k, v in r_.items() if k != "t"} for r_ in rows]) if rows else None
                    entry["sim"]["reindexer_rpc_per_query"] = float(migr.mean()) * per_rec["rpc"]
                    entry["sim"]["reindexer_kb_per_query"] = float(migr.mean()) * per_rec["kb"]
                    entry["sim"]["reindexer_cpu_s_per_query"] = float(migr.mean()) * per_rec["cpu_s"]
                    entry["sim"]["per_arrival"] = dict(final=rec["final"], rr=rec["rr"])
                c = entry[mode].get("client") or {}
                log(f"  dòng {mode:6s} {pol:6s} final={tt['final']:5.1f} rerank={tt['rr']:5.1f} tải={tt['fetch']:4.1f} "
                    f"mới={tt['new']:4.2f} f cuối={100 * tt['f_end']:4.1f}% GT ở E1={tt['gtE1']:4.1f}%"
                    + (f" tìm lại node A={100 * tt['found_A']:.0f}% E1={100 * tt['found_K']:.0f}%" if mode == "sim" else "")
                    + (f" | RPC={c['rpc_total']:7.0f} p50={c['lat_total_ms_p50'] / 1000:5.2f}s" if c else "")
                    + f"  ({time.time() - tt0:.0f}s)")
        # ---------------- đợt 6: phát lại chéo lịch migrate và cách đo
        if a.factorial:
            for pol in [p for p in ("lazy", "bg") if p in done_by.get("oracle", {}) and p in done_by.get("sim", {})]:
                entry = stream_out[pol]
                rc, _ = run_stream(pol, 0.0, "oracle", sched=done_by["oracle"][pol]["mig"])
                tc, tr_ = totals(rc), entry["oracle"]["totals"]
                ks = ("final", "rr", "fetch", "new", "f_end", "nodes", "moved", "gtE1")
                bad = sum(abs(tc[k] - tr_[k]) > 1e-9 for k in ks)
                checks.setdefault("replay_identity", {})[pol] = dict(n=len(ks), bad=int(bad))
                log(f">>> (4) {pol}: phát lại lịch probe, đo bằng probe, so với lượt probe: {len(ks)} giá trị, "
                    f"{'KHỚP' if bad == 0 else f'{bad} LỆCH'}")
                tt0 = time.time()
                reps = dict(sched_probe_eval_lookup=("oracle", "sim"), sched_lookup_eval_probe=("sim", "oracle"))
                if a.noise_replay:
                    reps["sched_lookup_eval_lookup_again"] = ("sim", "sim")
                entry["replay"] = {}
                n4, bad4 = 0, 0
                for nm_r, (src, ev_mode) in reps.items():
                    rr_, _ = run_stream(pol, 0.0, ev_mode, sched=done_by[src][pol]["mig"], pay_cost=False)
                    tr2 = totals(rr_)
                    entry["replay"][nm_r] = dict(totals=tr2, windows=windows(rr_, a.window),
                                                 per_arrival=dict(final=rr_["final"], rr=rr_["rr"]))
                    ref2 = entry[src]["totals"]
                    for k in ("new", "f_end", "gtE1"):
                        n4 += 1; bad4 += abs(tr2[k] - ref2[k]) > 1e-9
                    log(f"  phát lại {pol:4s} lịch {'probe' if src == 'oracle' else 'thật':5s} đo "
                        f"{'probe' if ev_mode == 'oracle' else 'thật':5s}: final={tr2['final']:5.1f} rerank={tr2['rr']:5.1f} "
                        f"GT ở E1={tr2['gtE1']:4.1f}%  ({time.time() - tt0:.0f}s)")
                checks.setdefault("replay_schedule", {})[pol] = dict(n=n4, bad=int(bad4))
                log(f">>> (4b) {pol}: số mới, f cuối, GT ở E1 của các lượt phát lại so với lượt gốc của lịch: {n4} giá trị, "
                    f"{'KHỚP' if bad4 == 0 else f'{bad4} LỆCH'}")
        # (3) dòng oracle khớp 06
        f6 = None
        if a.check_l != "none":
            if a.check_l != "auto":
                f6 = a.check_l
            else:
                for cand in (f"probeL_{pre}{a.tag}_s{a.seed}_ku{sfx}.json", f"probeLR_{pre}{a.tag}_s{a.seed}{sfx}.json"):
                    if os.path.exists(cand):
                        f6 = cand; break
        if f6 and os.path.exists(f6):
            try:
                L6 = json.load(open(f6))
                g6 = L6["argv"].get
                okarg = (g6("frac") == a.frac and g6("nodes") == a.nodes and g6("stream") == a.stream
                         and g6("nq") == a.nq and g6("n_heldout", 100) == a.n_heldout and g6("R", 20) == R
                         and g6("e1_key", "u") == "u" and g6("seed") == a.seed)
                n, bad = 0, 0
                for pol in pols:
                    k6 = f"z{z:g}|PROB|{pol}"
                    if not okarg or k6 not in L6["runs"] or "oracle" not in stream_out.get(pol, {}):
                        continue
                    o6, mine = L6["runs"][k6]["totals"], stream_out[pol]["oracle"]["totals"]
                    for kk in ("final", "rr", "fetch", "new", "f_end", "nodes", "moved"):
                        if kk in o6:
                            n += 1; bad += abs(o6[kk] - mine[kk]) > 1e-9
                checks["stream_oracle_vs_06"] = dict(file=f6, n=n, bad=int(bad))
                log(f">>> (3) dòng vòng kín với tập node oracle so với 06 ({f6}): {n} giá trị, "
                    f"{'KHỚP' if bad == 0 and n > 0 else f'{bad} LỆCH' if n else 'KHÔNG SO ĐƯỢC (khác tham số)'}")
            except Exception as e:
                log(f"*** tự kiểm (3) với {f6} lỗi: {e}")
        else:
            log(">>> (3) không có file 06 để tự kiểm dòng oracle")
        out["stream"] = dict(zipf=z, length=len(stream), runs=stream_out)

    base = "probeE2F" if a.factorial else "probeE2E"
    fn = a.out or f"{base}_{pre}{a.tag}_s{a.seed}{sfx}.json"
    # (5) so với lượt đợt 5 cùng seed (cùng chuỗi ngẫu nhiên nếu phần A và tham số giống hệt)
    fE = None if a.check_e2e == "none" else (a.check_e2e if a.check_e2e != "auto" else f"probeE2E_{pre}{a.tag}_s{a.seed}{sfx}.json")
    if fE and os.path.exists(fE) and os.path.abspath(fE) != os.path.abspath(fn):
        try:
            Q = json.load(open(fE))
            same = all(Q["argv"].get(k) == getattr(a, k) for k in (
                "dataset", "tag", "seed", "nodes", "frac", "nq", "nq_sim", "nq_pay", "fmig", "stream", "zipf", "n_heldout",
                "pay_every", "policies", "selfcheck_n", "tables", "k_query", "probes", "cbits", "dsub", "kappa", "R", "need",
                "cal_top", "folds", "r_max", "reindex_sample"))
            if same and a.fixed:
                n, bad = 0, 0
                for nm_, r_ in res_A.items():
                    for side in ("oracle", "sim"):
                        for k in ("final_r5", "rr", "reach", "fetch"):
                            n += 1; bad += abs(r_[side][k] - Q["fixed"][nm_][side][k]) > 1e-9
                for pol, e_ in (out.get("stream") or {}).get("runs", {}).items():
                    for side in ("oracle", "sim"):
                        for k in ("final", "rr", "fetch", "new", "f_end", "gtE1"):
                            n += 1; bad += abs(e_[side]["totals"][k] - Q["stream"]["runs"][pol][side]["totals"][k]) > 1e-9
                checks["vs_round5"] = dict(file=fE, n=n, bad=int(bad))
                log(f">>> (5) so với đợt 5 ({fE}): {n} giá trị, {'KHỚP' if bad == 0 else f'{bad} LỆCH'}")
            else:
                log(f">>> (5) {fE} khác tham số hoặc không chạy phần A, bỏ qua")
        except Exception as e:
            log(f"*** tự kiểm (5) với {fE} lỗi: {e}")
    json.dump(out, open(fn, "w"), indent=1)
    log(f"\n-> {fn}   ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
