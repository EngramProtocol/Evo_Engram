#!/usr/bin/env python3
"""
02_probe_bridge.py  —  CHẠY TRÊN node-dal-02 (CPU, không cần GPU).

GATE quyết định: ánh xạ tuyến tính tính trên vector tái tạo từ PQ code của M0
có giữ đủ cấu trúc lân cận để sinh semantic key và PQ code trong không gian M1
hay không.

Đo đúng chuỗi: vector error -> NN overlap -> key/peer overlap -> Final R@5,
trên các nhánh:

  null_random          khoá ngẫu nhiên (sàn)
  no_migration         record ở E0, query M1 (chỉ khi d0 == d1)
  dual_encode          record ở E0, query M0  [BASELINE BẮT BUỘC]
  dual_encode_rerank   như trên + fetch top-R rồi rerank bằng M1 thật
  derived_true_v0      derived record từ v0 THẬT      (tách lỗi ánh xạ)
  derived_pq_v0        derived record từ v0 TÁI TẠO   [ĐỀ XUẤT]
  hybrid               native cho mẫu S, derived cho phần còn lại
  oracle_full          toàn bộ native E1 (trần)

Mẫu S (tỉ lệ f) vừa là tập huấn luyện bridge vừa là phần đã re-embed, nên f
chính là ngân sách migration. Không dùng scipy.

CHẠY:
    python3 02_probe_bridge.py --tag e5large  --mode gate  --seed 20235956
    python3 02_probe_bridge.py --tag e5large  --mode curve --seed 20235956
"""
import argparse, json, os, random, sys, time
import numpy as np
np.seterr(invalid='ignore', divide='ignore')

# ----------------------------------------------------------------- tiện ích
def log(*a):
    print(*a, flush=True)


def spearman(x, y):
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    return float(np.corrcoef(rx, ry)[0, 1])


def angles_deg(A, B):
    """Góc giữa từng cặp hàng của A và B (đã hoặc chưa chuẩn hoá)."""
    a = A / np.maximum(np.linalg.norm(A, axis=1, keepdims=True), 1e-12)
    b = B / np.maximum(np.linalg.norm(B, axis=1, keepdims=True), 1e-12)
    c = np.clip((a * b).sum(1), -1.0, 1.0)
    return np.degrees(np.arccos(c))


def l2norm(X):
    return X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)


# ----------------------------------------------------------------- chiếu SRP
def gen_proj(seed, d, L, bits=160):
    """Khớp src/routing.generate_lsh_projections: Achlioptas thưa, chuẩn hoá cột."""
    rng = np.random.RandomState(seed)
    out = []
    for _ in range(L):
        M = rng.choice([0, 1, -1], size=(d, bits),
                       p=[2 / 3, 1 / 6, 1 / 6]).astype(np.float32)
        nrm = np.linalg.norm(M, axis=0, keepdims=True)
        nrm[nrm == 0] = 1.0
        out.append(M / nrm)
    return out


def pack63(bits):
    """(N,160) bool -> khoá int64 từ 63 bit đầu (khớp FastNetwork.key63)."""
    k = np.zeros(bits.shape[0], dtype=np.int64)
    for j in range(63):
        k = (k << np.int64(1)) | bits[:, j].astype(np.int64)
    return k


def nearest_node(keys, nid, chunk=512):
    out = np.empty(len(keys), dtype=np.int32)
    for s in range(0, len(keys), chunk):
        out[s:s + chunk] = np.argmin(
            np.bitwise_xor(nid[None, :], keys[s:s + chunk, None]), axis=1)
    return out


def knn_nodes(keys, nid, K, chunk=256):
    """Trả về (len(keys), K) chỉ số node gần nhất theo XOR."""
    out = np.empty((len(keys), K), dtype=np.int32)
    for s in range(0, len(keys), chunk):
        d = np.bitwise_xor(nid[None, :], keys[s:s + chunk, None])
        out[s:s + chunk] = np.argpartition(d, K - 1, axis=1)[:, :K]
    return out


def probe_keys_for(qvecs, P_list, T, cbits):
    """[L][Q, T] khoá: khoá gốc + (T-1) biến thể lật bit biên nhỏ nhất."""
    per_table = []
    for P in P_list:
        PR = qvecs @ P                       # (Q,160)
        base = pack63(PR > 0)
        weak = np.argsort(np.abs(PR[:, :cbits]), axis=1)[:, :T - 1]
        ks = np.empty((len(qvecs), T), dtype=np.int64)
        ks[:, 0] = base
        for t in range(T - 1):
            ks[:, t + 1] = base ^ (np.int64(1) << (62 - weak[:, t]).astype(np.int64))
        per_table.append(ks)
    return per_table


# ----------------------------------------------------------------- PQ
def pq_train(X, m, seed, ksub=256, iters=20):
    n, d = X.shape
    assert d % m == 0, f"d={d} không chia hết cho m={m}"
    dsub = d // m
    try:
        import faiss
        pq = faiss.ProductQuantizer(d, m, 8)
        pq.cp.seed = int(seed) % (2 ** 31 - 1)
        pq.train(np.ascontiguousarray(X.astype(np.float32)))
        cb = faiss.vector_to_array(pq.centroids).reshape(m, ksub, dsub)
        return cb.astype(np.float32)
    except ImportError:
        log("    [faiss THIẾU -> k-means numpy, chỉ dùng khi chạy thử]")
    rng = np.random.RandomState(seed)
    Xs = X.reshape(n, m, dsub)
    cb = np.empty((m, ksub, dsub), dtype=np.float32)
    for j in range(m):
        pts = Xs[:, j, :]
        c = pts[rng.choice(n, min(ksub, n), replace=False)].copy()
        if len(c) < ksub:
            c = np.vstack([c, np.repeat(c[:1], ksub - len(c), 0)])
        for _ in range(iters):
            dist = (pts ** 2).sum(1)[:, None] - 2 * pts @ c.T + (c ** 2).sum(1)
            lab = np.argmin(dist, axis=1)
            for q in range(ksub):
                sel = lab == q
                if sel.any():
                    c[q] = pts[sel].mean(0)
        cb[j] = c
    return cb


def pq_encode(X, cb):
    n, d = X.shape
    m, ksub, dsub = cb.shape
    Xs = X.reshape(n, m, dsub)
    codes = np.empty((n, m), dtype=np.uint8)
    for j in range(m):
        pts = Xs[:, j, :]
        c = cb[j]
        dist = -2 * (pts @ c.T) + (c ** 2).sum(1)[None, :]
        codes[:, j] = np.argmin(dist, axis=1).astype(np.uint8)
    return codes


def adc_lut(q, cb):
    m, ksub, dsub = cb.shape
    qs = q.reshape(m, dsub)
    return ((qs[:, None, :] - cb) ** 2).sum(2)        # (m, ksub)


# ----------------------------------------------------------------- bridge
def fit_procrustes(X, Y):
    """min ||X W - Y||_F, W bán trực giao. Chấp nhận d0 != d1."""
    U, _, Vt = np.linalg.svd(X.T @ Y, full_matrices=False)
    return (U @ Vt).astype(np.float32)


def fit_ridge(X, Y, lam):
    d = X.shape[1]
    A = X.T @ X + lam * np.eye(d, dtype=np.float64)
    return np.linalg.solve(A, X.T @ Y).astype(np.float32)


def fit_bridge(X, Y, method, seed, lams=(1e-3, 1e-2, 1e-1, 1.0, 10.0)):
    """Chọn lam bằng tập validation tách từ chính S, rồi khớp lại trên toàn S."""
    if method == "procrustes":
        return fit_procrustes(X.astype(np.float64), Y.astype(np.float64)), None
    rng = np.random.RandomState(seed + 7)
    idx = rng.permutation(len(X))
    cut = max(1, int(0.8 * len(X)))
    tr, va = idx[:cut], idx[cut:]
    if len(va) == 0:
        tr, va = idx, idx
    best, best_lam = None, None
    Xd, Yd = X.astype(np.float64), Y.astype(np.float64)
    for lam in lams:
        W = fit_ridge(Xd[tr], Yd[tr], lam)
        err = angles_deg(Xd[va] @ W, Yd[va]).mean()
        if best is None or err < best:
            best, best_lam = err, lam
    return fit_ridge(Xd, Yd, best_lam), best_lam


# ----------------------------------------------------------------- pipeline
def build_index(rec_vecs, P_list, nid):
    """anchors[l, i] = node giữ record của object i theo bảng l."""
    return np.stack([nearest_node(pack63(rec_vecs @ P > 0), nid)
                     for P in P_list])


def run_arm(name, rec_vecs, P_list, q_vecs, codes, cb, nid, gt5,
            K, T, cbits, rerank_vecs=None, rerank_q=None, rerank_R=50,
            note=""):
    N = rec_vecs.shape[0]
    NQ = q_vecs.shape[0]
    anchors = build_index(rec_vecs, P_list, nid)
    pk = probe_keys_for(q_vecs, P_list, T, cbits)

    reach_hit = np.zeros(NQ)
    final_hit = np.zeros(NQ)
    n_reach = np.zeros(NQ)
    n_nodes = np.zeros(NQ)

    for qi in range(NQ):
        keys = np.concatenate([pk[l][qi] for l in range(len(P_list))])
        touched = np.unique(knn_nodes(keys, nid, K))
        mask = np.zeros(len(nid), dtype=bool)
        mask[touched] = True
        reach = np.flatnonzero(mask[anchors].any(0))
        n_reach[qi] = len(reach)
        n_nodes[qi] = len(touched)
        g = gt5[qi]
        reach_hit[qi] = len(set(reach.tolist()) & set(g.tolist())) / len(g)
        if len(reach) == 0:
            continue
        lut = adc_lut(q_vecs[qi], cb)
        m = cb.shape[0]
        dist = lut[np.arange(m)[None, :], codes[reach]].sum(1)
        if rerank_vecs is None:
            top = reach[np.argsort(dist)[:5]]
        else:
            cand = reach[np.argsort(dist)[:rerank_R]]
            sim = rerank_vecs[cand] @ rerank_q[qi]
            top = cand[np.argsort(-sim)[:5]]
        final_hit[qi] = len(set(top.tolist()) & set(g.tolist())) / len(g)

    return dict(name=name, note=note,
                reach_r5=100 * reach_hit.mean(),
                final_r5=100 * final_hit.mean(),
                cand=float(n_reach.mean()),
                nodes=float(n_nodes.mean()))


def placement_fidelity(rec_vecs, true_vecs, P_list, nid, K):
    """Khoá derived có rơi đúng chỗ khoá native không."""
    exact, within = [], []
    for P in P_list:
        kd = pack63(rec_vecs @ P > 0)
        kt = pack63(true_vecs @ P > 0)
        ad = nearest_node(kd, nid)
        at = nearest_node(kt, nid)
        exact.append((ad == at).mean())
        nb = knn_nodes(kt, nid, K)
        within.append((nb == ad[:, None]).any(1).mean())
    return 100 * np.mean(exact), 100 * np.mean(within)


def nn_overlap(rec_vecs, q_vecs, gt5, k=5):
    """Trùng khớp top-k thuần embedding, chưa qua DHT và chưa qua PQ."""
    hits = []
    for s in range(0, len(q_vecs), 64):
        sim = q_vecs[s:s + 64] @ rec_vecs.T
        idx = np.argpartition(-sim, k, axis=1)[:, :k]
        for r in range(idx.shape[0]):
            g = gt5[s + r]
            hits.append(len(set(idx[r].tolist()) & set(g.tolist())) / len(g))
    return 100 * np.mean(hits)


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="tag của M1, vd e5large")
    ap.add_argument("--mode", choices=["gate", "curve"], default="gate")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--seed", type=int, default=20235956)
    ap.add_argument("--nodes", type=int, default=10000)
    ap.add_argument("--nq", type=int, default=300)
    ap.add_argument("--tables", type=int, default=5)
    ap.add_argument("--k-query", type=int, default=20)
    ap.add_argument("--probes", type=int, default=8)
    ap.add_argument("--cbits", type=int, default=16)
    ap.add_argument("--dsub", type=int, default=2)
    ap.add_argument("--frac", type=float, default=0.10,
                    help="tỉ lệ mẫu S đã re-embed (mode gate)")
    ap.add_argument("--fracs", default="0.01,0.02,0.05,0.10,0.20,0.50,1.00")
    ap.add_argument("--bridge", choices=["procrustes", "ridge", "both"],
                    default="both")
    ap.add_argument("--cb-train", choices=["sample", "full"], default="sample")
    ap.add_argument("--rerank-R", type=int, default=50)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    D = a.data_dir
    t0 = time.time()

    # ---------- nạp ----------
    E0 = np.load(f"{D}/code_corpus_embeddings.npy").astype(np.float32)
    Q0 = np.load(f"{D}/code_query_embeddings.npy").astype(np.float32)
    cb0 = np.load(f"{D}/code_pq_codebook_m512.npy").astype(np.float32)
    cd0 = np.load(f"{D}/code_pq_codes_m512.npy")
    E1 = np.load(f"{D}/code_{a.tag}_corpus_embeddings.npy").astype(np.float32)
    Q1 = np.load(f"{D}/code_{a.tag}_query_embeddings.npy").astype(np.float32)
    gt1j = json.load(open(f"{D}/code_{a.tag}_ground_truth.json"))

    N, d0 = E0.shape
    d1 = E1.shape[1]
    assert E1.shape[0] == N, "corpus M0 và M1 lệch số dòng"
    assert d1 % a.dsub == 0, f"d1={d1} không chia hết cho dsub={a.dsub}"
    m1 = d1 // a.dsub
    gt5 = [np.array([int(r["index"]) for r in g["top_5_results"][:5]])
           for g in gt1j][:a.nq]

    log("=" * 74)
    log(f"tag={a.tag}  seed={a.seed}  mode={a.mode}")
    log(f"M0 d={d0} m={cb0.shape[0]} ({cb0.shape[0]} byte/obj)   "
        f"M1 d={d1} m={m1} ({m1} byte/obj)")
    log(f"N={N}  nodes={a.nodes}  nq={a.nq}  L={a.tables} K={a.k_query} "
        f"T={a.probes} c={a.cbits}")

    # ---------- v0 tái tạo từ PQ ----------
    m0 = cb0.shape[0]
    V0h = l2norm(cb0[np.arange(m0)[None, :], cd0].reshape(N, d0).astype(np.float32))
    th = angles_deg(E0, V0h)
    log(f"lệch góc v0 vs v0_hat: mean={th.mean():.3f}°  p95={np.percentile(th,95):.3f}°"
        f"   (mốc đã biết: 3.724°)")

    # ---------- overlap ground truth M0 vs M1 ----------
    gt0j = json.load(open(f"{D}/code_ground_truth.json"))
    ov01 = np.mean([len(set(int(r['index']) for r in gt0j[i]['top_5_results'][:5])
                        & set(gt5[i].tolist())) / 5.0 for i in range(a.nq)])
    log(f"GT overlap M0 vs M1 (top-5): {100*ov01:.1f}%  "
        f"(thấp = hai model thật sự khác nhau)")

    # ---------- overlay ----------
    rnd = random.Random(a.seed)
    nid = np.array([rnd.getrandbits(63) for _ in range(a.nodes)], dtype=np.int64)
    P0 = gen_proj(a.seed, d0, a.tables)
    P1 = gen_proj(a.seed, d1, a.tables)

    rng = np.random.RandomState(a.seed)
    perm = rng.permutation(N)

    methods = ["procrustes", "ridge"] if a.bridge == "both" else [a.bridge]
    fracs = [a.frac] if a.mode == "gate" else [float(x) for x in a.fracs.split(",")]
    results = []

    # ---------- các nhánh KHÔNG phụ thuộc f ----------
    log("\n" + "-" * 74)
    log("NHÁNH THAM CHIẾU (không phụ thuộc ngân sách migration)")
    ref = []

    rkeys = np.random.RandomState(a.seed + 1).randint(
        0, 2 ** 62, size=(a.nq, a.tables * a.probes)).astype(np.int64)
    rh = np.zeros(a.nq)
    anc_null = build_index(E1, P1, nid)
    for qi in range(a.nq):
        touched = np.unique(knn_nodes(rkeys[qi], nid, a.k_query))
        mask = np.zeros(a.nodes, dtype=bool); mask[touched] = True
        reach = np.flatnonzero(mask[anc_null].any(0))
        rh[qi] = len(set(reach.tolist()) & set(gt5[qi].tolist())) / 5.0
    ref.append(dict(name="null_random", note="khoá ngẫu nhiên (sàn)",
                    reach_r5=100 * rh.mean(), final_r5=float("nan"),
                    cand=float("nan"), nodes=float("nan")))

    ref.append(run_arm("dual_encode", E0, P0, Q0[:a.nq], cd0, cb0, nid, gt5,
                       a.k_query, a.probes, a.cbits,
                       note="giữ M0+M1, query bằng M0, KHÔNG migrate"))
    ref.append(run_arm("dual_encode_rerank", E0, P0, Q0[:a.nq], cd0, cb0, nid,
                       gt5, a.k_query, a.probes, a.cbits,
                       rerank_vecs=E1, rerank_q=Q1[:a.nq], rerank_R=a.rerank_R,
                       note=f"như trên + fetch {a.rerank_R} payload/query rồi rerank bằng M1"))
    if d0 == d1:
        ref.append(run_arm("no_migration", E0, P0, Q1[:a.nq], cd0, cb0, nid,
                           gt5, a.k_query, a.probes, a.cbits,
                           note="record ở E0, query M1, không bridge"))

    cb1_full = pq_train(E1, m1, a.seed)
    cd1_full = pq_encode(E1, cb1_full)
    ref.append(run_arm("oracle_full", E1, P1, Q1[:a.nq], cd1_full, cb1_full,
                       nid, gt5, a.k_query, a.probes, a.cbits,
                       note="toàn bộ native E1 (trần)"))

    for r in ref:
        log(f"  {r['name']:20s} reach={r['reach_r5']:5.1f}%  "
            f"final={r['final_r5']:5.1f}%   {r['note']}")
    results += ref

    # ---------- nhánh phụ thuộc f ----------
    for f in fracs:
        nS = max(a.tables * 20, int(round(f * N)))
        S = perm[:nS]
        rest = perm[nS:]
        log("\n" + "-" * 74)
        log(f"NGÂN SÁCH f={f:.2%}  ->  |S|={nS} object đã re-embed bằng M1")

        cb1 = cb1_full if (a.cb_train == "full" or nS < 2000) else \
            pq_train(E1[S], m1, a.seed)
        if a.cb_train == "sample" and nS < 2000:
            log("    (|S| < 2000 -> codebook1 huấn luyện trên toàn E1, ghi rõ khi báo cáo)")

        for meth in methods:
            Wt, lam_t = fit_bridge(E0[S], E1[S], meth, a.seed)
            Wh, lam_h = fit_bridge(V0h[S], E1[S], meth, a.seed)

            Rt = l2norm((E0 @ Wt).astype(np.float32))
            Rh = l2norm((V0h @ Wh).astype(np.float32))

            # 1. vector error (chỉ trên phần NGOÀI S = phần thật sự derived)
            if len(rest) == 0:                       # f = 100%, không còn gì để dẫn xuất
                at = ah = np.array([np.nan])
            else:
                at = angles_deg(Rt[rest], E1[rest])
                ah = angles_deg(Rh[rest], E1[rest])
            # 2. NN overlap thuần embedding
            nt = nn_overlap(Rt, Q1[:a.nq], gt5)
            nh = nn_overlap(Rh, Q1[:a.nq], gt5)
            # 3. placement fidelity
            et, wt_ = placement_fidelity(Rt, E1, P1, nid, a.k_query)
            eh, wh_ = placement_fidelity(Rh, E1, P1, nid, a.k_query)

            lamtxt = "" if lam_h is None else f" lam={lam_h:g}"
            log(f"\n  [{meth}{lamtxt}]")
            log(f"    (1) góc tới v1 thật, trên phần derived:"
                f"  từ v0 thật {at.mean():6.2f}°   từ v0 tái tạo {ah.mean():6.2f}°")
            log(f"    (2) NN overlap top-5 thuần embedding:"
                f"   từ v0 thật {nt:5.1f}%   từ v0 tái tạo {nh:5.1f}%")
            log(f"    (3) anchor trùng khít:"
                f"               từ v0 thật {et:5.1f}%   từ v0 tái tạo {eh:5.1f}%")
            log(f"        anchor nằm trong K={a.k_query} peer:"
                f"     từ v0 thật {wt_:5.1f}%   từ v0 tái tạo {wh_:5.1f}%")

            arms = []
            arms.append(run_arm(f"derived_true_v0/{meth}", Rt, P1, Q1[:a.nq],
                                pq_encode(Rt, cb1), cb1, nid, gt5,
                                a.k_query, a.probes, a.cbits,
                                note="tách lỗi ánh xạ khỏi lỗi lượng tử hoá"))
            arms.append(run_arm(f"derived_pq_v0/{meth}", Rh, P1, Q1[:a.nq],
                                pq_encode(Rh, cb1), cb1, nid, gt5,
                                a.k_query, a.probes, a.cbits,
                                note="ĐỀ XUẤT: peer tự dẫn xuất, không cần plaintext"))

            Hyb = Rh.copy(); Hyb[S] = E1[S]
            arms.append(run_arm(f"hybrid/{meth}", Hyb, P1, Q1[:a.nq],
                                pq_encode(Hyb, cb1), cb1, nid, gt5,
                                a.k_query, a.probes, a.cbits,
                                note=f"native cho {nS} object, derived cho {N-nS}"))

            for r in arms:
                r.update(frac=f, n_sample=nS, method=meth,
                         ang_true=float(at.mean()), ang_pq=float(ah.mean()),
                         nn_true=nt, nn_pq=nh,
                         anchor_exact_true=et, anchor_exact_pq=eh,
                         anchor_withinK_true=wt_, anchor_withinK_pq=wh_)
                log(f"    (4) {r['name']:28s} reach={r['reach_r5']:5.1f}%  "
                    f"final={r['final_r5']:5.1f}%  cand={r['cand']:.0f}")
            results += arms

    # ---------- tổng kết ----------
    log("\n" + "=" * 74)
    orc = next(r['final_r5'] for r in results if r['name'] == 'oracle_full')
    due = next(r['final_r5'] for r in results if r['name'] == 'dual_encode')
    log(f"TRẦN oracle_full = {orc:.1f}%      BASELINE dual_encode = {due:.1f}%")
    best = [r for r in results if r['name'].startswith('derived_pq_v0')]
    if best:
        b = max(best, key=lambda r: r['final_r5'])
        log(f"ĐỀ XUẤT tốt nhất = {b['final_r5']:.1f}%  ({b['name']}, f={b['frac']:.0%})")
        log(f"  lấp được {100*(b['final_r5']-due)/max(orc-due,1e-9):.0f}% "
            f"khoảng cách giữa baseline và trần")
        wk = max((r['anchor_withinK_pq'] for r in results
                  if 'anchor_withinK_pq' in r), default=float('nan'))
        log(f"\nNGƯỠNG GATE — anchor trong K peer (từ v0 tái tạo) = {wk:.1f}%")
        log("  > 60%  -> cơ chế đứng, tiến hành theo trục model")
        log("  < 40%  -> quay về phương án bài chọn ma trận chiếu")

    out = a.out or f"probeC_{a.tag}_{a.mode}_s{a.seed}.json"
    json.dump(dict(argv=vars(a), d0=d0, d1=d1, m1=m1,
                   pq_angle=float(th.mean()), gt_overlap_m0m1=float(ov01),
                   results=results), open(out, "w"), indent=1)
    log(f"\n-> {out}   ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
