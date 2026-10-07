#!/usr/bin/env python3
"""
03_probe_query_adapter.py  —  CHẠY TRÊN node-dal-02 (CPU).

GATE: query của mô hình mới M1 có dùng hiệu quả được trên chỉ mục cũ E0 hay
không. Toàn bộ index, anchor và PQ code giữ nguyên ở E0; chỉ query đi qua một
adapter M1 -> M0 rồi chạy lại đúng pipeline V-Engram của E0.

Nhánh (mọi nhánh dùng cùng một chỉ mục E0, trừ oracle):
  no_adapter         query M1 thô vào E0 (chỉ khi d0 == d1)          sàn
  dual_encode        query mã hoá bằng chính M0 (client giữ cả M0)    baseline chính
  oracle_full        chỉ mục native E1 (trần tuyệt đối)
  A_doc_procrustes   adapter khớp trên cặp document (E1[S] -> E0[S])
  A_doc_ridge
  A_qry_procrustes   adapter khớp trên cặp query (Q1 -> Q0), tập query KHÔNG dùng để đánh giá
  A_qry_ridge
  A_gt_doc_ridge     adapter hướng truy hồi: A(e1_i) ~ trung bình E0 của láng giềng M1 của i
  A_gt_qry_ridge     adapter hướng truy hồi trên tập query huấn luyện

Mỗi nhánh báo cáo: reach, final (ADC trong E0), final sau rerank với R payload,
số node chạm (= số ADC RPC), số ứng viên reachable, số ứng viên chuyển qua mạng
sau cắt top-kappa tại node, số payload phải tải.

Kiểm tra tái lập: dual_encode và oracle_full phải ra đúng số của
02_probe_bridge.py --cb-train full cùng seed.

CHẠY:
    python3 evo/03_probe_query_adapter.py --tag bgebase --seed 20235956
    python3 evo/03_probe_query_adapter.py --tag e5large --seed 20235956
"""
import argparse, importlib.util, json, os, random, time
import numpy as np
np.seterr(invalid='ignore', divide='ignore')

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("pb", os.path.join(_here, "02_probe_bridge.py"))
pb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pb)
log, l2norm, angles_deg = pb.log, pb.l2norm, pb.angles_deg

# mốc của lần chạy gate trước (cb_train=full, seed 20235956, nq=300) để tự kiểm tái lập
EXPECTED = {
    ("bgebase", 20235956): {"dual_encode": (84.2, 53.1), "oracle_full": (85.7, 83.7),
                            "dual_rerank50": 80.4},
    ("e5large", 20235956): {"dual_encode": (82.9, 48.0), "oracle_full": (98.4, 93.9),
                            "dual_rerank50": 74.9},
}


# ----------------------------------------------------------------- adapter
def fit_ridge_cv(X, Y, seed, lams):
    """Chọn lambda trên 20% validation tách từ tập huấn luyện, khớp lại trên toàn bộ."""
    rng = np.random.RandomState(seed + 11)
    idx = rng.permutation(len(X))
    cut = max(1, int(0.8 * len(X)))
    tr, va = idx[:cut], idx[cut:]
    Xd, Yd = X.astype(np.float64), Y.astype(np.float64)
    best, best_lam = None, None
    for lam in lams:
        W = pb.fit_ridge(Xd[tr], Yd[tr], lam)
        err = angles_deg(Xd[va] @ W, Yd[va]).mean()
        if best is None or err < best:
            best, best_lam = err, lam
    return pb.fit_ridge(Xd, Yd, best_lam), best_lam, float(best)


def gt_targets(src_m1, E1, E0, k, exclude_self_idx=None, chunk=256):
    """Đích hướng truy hồi: trung bình E0 của k láng giềng gần nhất theo M1."""
    T = np.empty((len(src_m1), E0.shape[1]), dtype=np.float32)
    for s in range(0, len(src_m1), chunk):
        sim = src_m1[s:s + chunk] @ E1.T
        if exclude_self_idx is not None:
            rows = np.arange(min(chunk, len(src_m1) - s))
            sim[rows, exclude_self_idx[s:s + chunk]] = -np.inf
        nb = np.argpartition(-sim, k, axis=1)[:, :k]
        T[s:s + chunk] = E0[nb].mean(1)
    return l2norm(T)


# ----------------------------------------------------------------- truy hồi trên E0
def retrieve(qv, anchors, P_list, codes, cb, nid, gt5, K, T, cbits, load,
             kappa, rerank_vecs, rerank_q, Rs):
    """Một lượt truy hồi; trả về chỉ số trung bình và final cho từng R."""
    NQ = qv.shape[0]
    pk = pb.probe_keys_for(qv, P_list, T, cbits)
    m = cb.shape[0]
    reach_hit = np.zeros(NQ); final_hit = np.zeros(NQ)
    rr_hit = {R: np.zeros(NQ) for R in Rs}
    n_nodes = np.zeros(NQ); n_reach = np.zeros(NQ); n_moved = np.zeros(NQ)

    for qi in range(NQ):
        keys = np.concatenate([pk[l][qi] for l in range(len(P_list))])
        touched = np.unique(pb.knn_nodes(keys, nid, K))
        mask = np.zeros(len(nid), dtype=bool); mask[touched] = True
        reach = np.flatnonzero(mask[anchors].any(0))
        g = set(gt5[qi].tolist())
        n_nodes[qi] = len(touched)
        n_reach[qi] = len(reach)
        n_moved[qi] = np.minimum(load[touched], kappa).sum()
        reach_hit[qi] = len(set(reach.tolist()) & g) / 5.0
        if len(reach) == 0:
            continue
        lut = pb.adc_lut(qv[qi], cb)
        dist = lut[np.arange(m)[None, :], codes[reach]].sum(1)
        order = reach[np.argsort(dist)]
        final_hit[qi] = len(set(order[:5].tolist()) & g) / 5.0
        for R in Rs:
            cand = order[:R]
            sim = rerank_vecs[cand] @ rerank_q[qi]
            top = cand[np.argsort(-sim)[:5]]
            rr_hit[R][qi] = len(set(top.tolist()) & g) / 5.0

    return dict(reach_r5=100 * reach_hit.mean(), final_r5=100 * final_hit.mean(),
                rerank={str(R): 100 * rr_hit[R].mean() for R in Rs},
                nodes=float(n_nodes.mean()), cand=float(n_reach.mean()),
                moved=float(n_moved.mean()))


def nn_overlap(qv, E, gt5, k=5):
    hits = []
    for s in range(0, len(qv), 64):
        sim = qv[s:s + 64] @ E.T
        idx = np.argpartition(-sim, k, axis=1)[:, :k]
        for r in range(idx.shape[0]):
            hits.append(len(set(idx[r].tolist()) & set(gt5[s + r].tolist())) / 5.0)
    return 100 * float(np.mean(hits))


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--seed", type=int, default=20235956)
    ap.add_argument("--nodes", type=int, default=10000)
    ap.add_argument("--nq", type=int, default=300, help="query đánh giá = nq query ĐẦU")
    ap.add_argument("--tables", type=int, default=5)
    ap.add_argument("--k-query", type=int, default=20)
    ap.add_argument("--probes", type=int, default=8)
    ap.add_argument("--cbits", type=int, default=16)
    ap.add_argument("--dsub", type=int, default=2)
    ap.add_argument("--kappa", type=int, default=30)
    ap.add_argument("--frac", type=float, default=0.10, help="tỉ lệ document đã nhúng lại bằng M1")
    ap.add_argument("--gt-k", type=int, default=5)
    ap.add_argument("--rerank", default="10,20,50")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    t0 = time.time()
    D = a.data_dir
    Rs = [int(x) for x in a.rerank.split(",")]

    E0 = np.load(f"{D}/code_corpus_embeddings.npy").astype(np.float32)
    Q0 = np.load(f"{D}/code_query_embeddings.npy").astype(np.float32)
    cb0 = np.load(f"{D}/code_pq_codebook_m512.npy").astype(np.float32)
    cd0 = np.load(f"{D}/code_pq_codes_m512.npy")
    E1 = np.load(f"{D}/code_{a.tag}_corpus_embeddings.npy").astype(np.float32)
    Q1 = np.load(f"{D}/code_{a.tag}_query_embeddings.npy").astype(np.float32)
    gt1 = json.load(open(f"{D}/code_{a.tag}_ground_truth.json"))
    N, d0 = E0.shape; d1 = E1.shape[1]; NQall = len(gt1)
    assert E1.shape[0] == N and Q1.shape[0] == Q0.shape[0] == NQall
    m1 = d1 // a.dsub

    ev = np.arange(a.nq)                       # tập đánh giá: nq query đầu
    trq = np.arange(a.nq, NQall)               # tập huấn luyện adapter phía query
    gt5_all = [np.array([int(r["index"]) for r in g["top_5_results"][:5]]) for g in gt1]
    gt5 = [gt5_all[i] for i in ev]

    log("=" * 78)
    log(f"tag={a.tag} seed={a.seed}  d0={d0} d1={d1}  N={N} nodes={a.nodes}")
    log(f"đánh giá {len(ev)} query | huấn luyện adapter phía query {len(trq)} query "
        f"(tách rời) | document mẫu f={a.frac:.0%}")

    rnd = random.Random(a.seed)
    nid = np.array([rnd.getrandbits(63) for _ in range(a.nodes)], dtype=np.int64)
    P0 = pb.gen_proj(a.seed, d0, a.tables)
    P1 = pb.gen_proj(a.seed, d1, a.tables)
    perm = np.random.RandomState(a.seed).permutation(N)
    S = perm[:max(a.tables * 20, int(round(a.frac * N)))]
    rest = perm[len(S):]

    # chỉ mục E0 dùng chung cho mọi nhánh phía E0: anchor từ v0 gốc của writer, PQ code gốc
    anchors0 = pb.build_index(E0, P0, nid)
    load0 = np.bincount(anchors0.ravel(), minlength=a.nodes)
    common = dict(anchors=anchors0, P_list=P0, codes=cd0, cb=cb0, nid=nid, gt5=gt5,
                  K=a.k_query, T=a.probes, cbits=a.cbits, load=load0,
                  kappa=a.kappa, rerank_vecs=E1, rerank_q=Q1[ev], Rs=Rs)

    results, diag = [], {}

    def arm(name, qv, note, extra=None):
        r = retrieve(qv, **common)
        r.update(name=name, note=note, nn_overlap=nn_overlap(qv, E0, gt5))
        r["q_angle_to_q0"] = float(angles_deg(qv, Q0[ev]).mean())
        if extra:
            r.update(extra)
        results.append(r)
        rr = "  ".join(f"R{R}={r['rerank'][str(R)]:5.1f}" for R in Rs)
        log(f"  {name:18s} reach={r['reach_r5']:5.1f} final={r['final_r5']:5.1f} | {rr} | "
            f"góc→q0={r['q_angle_to_q0']:5.2f}° nodes={r['nodes']:.0f} "
            f"cand={r['cand']:.0f} moved={r['moved']:.0f}")
        return r

    log("\n--- MỐC ---")
    if d0 == d1:
        arm("no_adapter", l2norm(Q1[ev]), "query M1 thô vào E0 (sàn)")
    arm("dual_encode", Q0[ev], "client giữ M0")

    cb1 = pb.pq_train(E1, m1, a.seed)
    cd1 = pb.pq_encode(E1, cb1)
    anchors1 = pb.build_index(E1, P1, nid)
    load1 = np.bincount(anchors1.ravel(), minlength=a.nodes)
    ro = retrieve(l2norm(Q1[ev]), anchors1, P1, cd1, cb1, nid, gt5, a.k_query, a.probes,
                  a.cbits, load1, a.kappa, E1, Q1[ev], Rs)
    ro.update(name="oracle_full", note="chỉ mục native E1 (trần tuyệt đối)",
              nn_overlap=float("nan"), q_angle_to_q0=float("nan"))
    results.append(ro)
    log(f"  {'oracle_full':18s} reach={ro['reach_r5']:5.1f} final={ro['final_r5']:5.1f} | "
        f"nodes={ro['nodes']:.0f} cand={ro['cand']:.0f} moved={ro['moved']:.0f}")

    exp = EXPECTED.get((a.tag, a.seed))
    if exp and a.nq == 300 and a.nodes == 10000:
        de = next(r for r in results if r["name"] == "dual_encode")
        ok = (abs(de["reach_r5"] - exp["dual_encode"][0]) < 0.15 and
              abs(de["final_r5"] - exp["dual_encode"][1]) < 0.15 and
              abs(ro["final_r5"] - exp["oracle_full"][1]) < 0.15 and
              ("50" not in de["rerank"] or abs(de["rerank"]["50"] - exp["dual_rerank50"]) < 0.15))
        log(f"  >>> TÁI LẬP gate trước: {'KHỚP' if ok else 'LỆCH - dừng lại kiểm tra'}")
        diag["reproduced"] = bool(ok)

    # ---------------- adapter khớp trên cặp document
    log("\n--- ADAPTER KHỚP TRÊN CẶP DOCUMENT (E1[S] -> E0[S]) ---")
    Wp = pb.fit_procrustes(E1[S].astype(np.float64), E0[S].astype(np.float64))
    Wr, lam_dr, _ = fit_ridge_cv(E1[S], E0[S], a.seed, (1e-3, 1e-2, 1e-1, 1.0, 10.0))
    for nm, W, lam in (("A_doc_procrustes", Wp, None), ("A_doc_ridge", Wr, lam_dr)):
        ang_doc = float(angles_deg(E1[rest] @ W, E0[rest]).mean())   # document ngoài S
        ang_qry = float(angles_deg(Q1[ev] @ W, Q0[ev]).mean())       # query đánh giá
        arm(nm, l2norm(Q1[ev] @ W), "khớp trên document",
            dict(lam=lam, resid_doc=ang_doc, resid_qry=ang_qry))
        log(f"      phần dư: document ngoài mẫu {ang_doc:5.2f}°  |  query {ang_qry:5.2f}°"
            f"  (chênh = độ lệch hình học query/document)")

    # ---------------- adapter khớp trên cặp query
    log(f"\n--- ADAPTER KHỚP TRÊN CẶP QUERY ({len(trq)} query huấn luyện -> {d0} chiều) ---")
    if len(trq) < d1:
        log(f"    CẢNH BÁO: {len(trq)} mẫu < {d1} chiều, ma trận thiếu xác định; "
            f"procrustes chỉ xác định trên không gian con {len(trq)} chiều")
    Wqp = pb.fit_procrustes(Q1[trq].astype(np.float64), Q0[trq].astype(np.float64))
    Wqr, lam_qr, _ = fit_ridge_cv(Q1[trq], Q0[trq], a.seed,
                                  (1e-2, 1e-1, 1.0, 10.0, 100.0, 1000.0))
    for nm, W, lam in (("A_qry_procrustes", Wqp, None), ("A_qry_ridge", Wqr, lam_qr)):
        arm(nm, l2norm(Q1[ev] @ W), "khớp trên query", dict(lam=lam))

    # ---------------- adapter hướng truy hồi
    log(f"\n--- ADAPTER HƯỚNG TRUY HỒI (đích = trung bình E0 của top-{a.gt_k} láng giềng M1) ---")
    Tdoc = gt_targets(E1[S], E1, E0, a.gt_k, exclude_self_idx=S)
    Wgd, lam_gd, _ = fit_ridge_cv(E1[S], Tdoc, a.seed, (1e-3, 1e-2, 1e-1, 1.0, 10.0))
    arm("A_gt_doc_ridge", l2norm(Q1[ev] @ Wgd), "document làm pseudo-query", dict(lam=lam_gd))
    Tq = l2norm(np.stack([E0[gt5_all[i]].mean(0) for i in trq]).astype(np.float32))
    Wgq, lam_gq, _ = fit_ridge_cv(Q1[trq], Tq, a.seed, (1e-2, 1e-1, 1.0, 10.0, 100.0, 1000.0))
    arm("A_gt_qry_ridge", l2norm(Q1[ev] @ Wgq), "query huấn luyện", dict(lam=lam_gq))

    # ---------------- tổng kết
    get = lambda n: next(r for r in results if r["name"] == n)
    de, orc = get("dual_encode"), get("oracle_full")
    floor = get("no_adapter") if d0 == d1 else None
    ads = [r for r in results if r["name"].startswith("A_")]
    best_reach = max(ads, key=lambda r: r["reach_r5"])
    best_fin = max(ads, key=lambda r: r["final_r5"])
    Rmax = str(max(Rs))
    best_rr = max(ads, key=lambda r: r["rerank"][Rmax])

    log("\n" + "=" * 78)
    log(f"TRẦN oracle_full final={orc['final_r5']:.1f}   "
        f"dual_encode reach={de['reach_r5']:.1f} final={de['final_r5']:.1f} "
        f"rerank@{Rmax}={de['rerank'][Rmax]:.1f}"
        + (f"   SÀN no_adapter reach={floor['reach_r5']:.1f}" if floor else ""))
    log(f"Adapter reach tốt nhất : {best_reach['reach_r5']:.1f}  ({best_reach['name']})  "
        f"chênh dual {best_reach['reach_r5'] - de['reach_r5']:+.1f}")
    log(f"Adapter final tốt nhất : {best_fin['final_r5']:.1f}  ({best_fin['name']})  "
        f"chênh dual {best_fin['final_r5'] - de['final_r5']:+.1f}")
    log(f"Adapter rerank@{Rmax} tốt nhất: {best_rr['rerank'][Rmax]:.1f}  ({best_rr['name']})  "
        f"chênh dual_rerank {best_rr['rerank'][Rmax] - de['rerank'][Rmax]:+.1f}")
    log("\nTIÊU CHÍ GATE (chốt trước):")
    log("  ĐẠT  : adapter+rerank không thấp hơn dual_rerank quá 5 điểm ở cùng R, VÀ reach không thấp hơn dual quá 5 điểm")
    log("  TRƯỢT: reach adapter tốt nhất thấp hơn dual quá 15 điểm trên cả hai cặp mô hình")
    log("  VƯỢT DUAL: adapter có final > dual_encode -> query M1 qua adapter dùng chỉ mục cũ tốt hơn cả chính M0")

    out = a.out or f"probeD_{a.tag}_s{a.seed}.json"
    json.dump(dict(argv=vars(a), d0=d0, d1=d1, n_train_query=int(len(trq)),
                   n_sample_doc=int(len(S)), diag=diag, results=results),
              open(out, "w"), indent=1)
    log(f"\n-> {out}   ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
