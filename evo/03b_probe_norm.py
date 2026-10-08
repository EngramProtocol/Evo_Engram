#!/usr/bin/env python3
"""
03b_probe_norm.py  —  CHẠY TRÊN node-dal-02 (CPU). Nhánh cuối của gate 3.

Gate 3c cho thấy định tuyến tốt nhất là ridge chiều ngược (E1 -> E0), còn tín hiệu xếp hạng
tốt nhất mà 10% document đã nhúng lại mang được là ridge chiều xuôi E0 -> E1 của gate 2,
SAU KHI chuẩn hoá từng record:
        điểm_i = <q1, e0_i W> / ||e0_i W||            (NN overlap gate 2: 60.5 bge, 48.4 e5)
Không ánh xạ phía query nào tạo ra được phép chia theo từng record này, nên chuyển vị thuần
(A_fwdT_ridge, chỉ có tử số) hỏng hẳn trên e5.

Nhánh mới A_split_norm:
  định tuyến : khoá SRP từ q1·Wr (như A_doc_ridge)
  xếp hạng   : node chấm  s_i = <q1·Wf^T, c_i> / n_i ,   n_i = ||c_i · Wf||
               c_i là vector tái tạo từ PQ code E0 của record i, Wf là ridge chiều xuôi công khai.
n_i là một số thực mỗi record, node tự tính một lần từ PQ code và adapter công khai: không cần
plaintext, không đổi PQ code, không đổi chữ ký record. s_i không phụ thuộc độ dài của c_i.

Tự kiểm:
  (1) nn của A_split_norm (toàn corpus, vector gốc) phải trùng NN overlap của
      derived_true_v0/ridge ở gate 2 cùng seed: 60.5 (bge) và 48.4 (e5) với seed 20235956.
  (2) nếu có probeD_<tag>_s<seed>_g3c.json, dual_encode / A_doc_ridge / A_split phải ra
      đúng từng số như gate 3c.

CHẠY: python3 evo/03b_probe_norm.py --tag bgebase --seed 20235956
"""
import argparse, importlib.util, json, os, random, time
import numpy as np
np.seterr(invalid='ignore', divide='ignore')

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("q3", os.path.join(_here, "03_probe_query_adapter.py"))
q3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q3)
pb = q3.pb
log, l2norm, angles_deg = pb.log, pb.l2norm, pb.angles_deg

# NN overlap top-5 của derived_true_v0/ridge ở gate 2 (seed 20235956, nq 300, f 10%)
GATE2_NN = {("bgebase", 20235956): 60.5, ("e5large", 20235956): 48.4}


def retrieve_norm(qv_route, qv_rank, div_pq, anchors, P_list, codes, cb, nid, gt5, K, T,
                  cbits, load, kappa, rerank_vecs, rerank_q, Rs, exact_vecs=None,
                  div_exact=None):
    """Như q3.retrieve, nhưng thứ tự ứng viên theo điểm ADC tích vô hướng chia cho n_i
    (giảm dần). final_ip = cùng điểm nhưng KHÔNG chia n_i, để thấy riêng tác dụng của n_i.
    final_exact và nn_overlap dùng vector gốc: <q, e0_i> / ||e0_i Wf||."""
    NQ = qv_route.shape[0]
    pk = pb.probe_keys_for(qv_route, P_list, T, cbits)
    m = cb.shape[0]
    am = np.arange(m)[None, :]
    Rmax = max(Rs)
    S_ex = None
    if exact_vecs is not None:
        S_ex = (qv_rank @ exact_vecs.T) / div_exact[None, :]
    reach_hit = np.zeros(NQ); final_hit = np.zeros(NQ)
    fin_ip = np.zeros(NQ); fin_ex = np.zeros(NQ); nn = np.zeros(NQ)
    rr_hit = {R: np.zeros(NQ) for R in Rs}
    rr_all = {R: np.zeros(NQ) for R in Rs}
    n_nodes = np.zeros(NQ); n_reach = np.zeros(NQ); n_moved = np.zeros(NQ)

    for qi in range(NQ):
        g = set(gt5[qi].tolist())
        if S_ex is not None:
            top = np.argpartition(-S_ex[qi], 5)[:5]
            nn[qi] = len(set(top.tolist()) & g) / 5.0
        keys = np.concatenate([pk[l][qi] for l in range(len(P_list))])
        touched = np.unique(pb.knn_nodes(keys, nid, K))
        mask = np.zeros(len(nid), dtype=bool); mask[touched] = True
        reach = np.flatnonzero(mask[anchors].any(0))
        n_nodes[qi] = len(touched)
        n_reach[qi] = len(reach)
        n_moved[qi] = np.minimum(load[touched], kappa).sum()
        reach_hit[qi] = len(set(reach.tolist()) & g) / 5.0
        if len(reach) == 0:
            continue
        rq = qv_rank[qi]
        cr = codes[reach]
        lut_ip = (rq.reshape(m, -1)[:, None, :] * cb).sum(2)
        s_ip = lut_ip[am, cr].sum(1)
        fin_ip[qi] = len(set(reach[np.argsort(-s_ip)[:5]].tolist()) & g) / 5.0
        order = reach[np.argsort(-(s_ip / div_pq[reach]))]
        final_hit[qi] = len(set(order[:5].tolist()) & g) / 5.0
        if S_ex is not None:
            fin_ex[qi] = len(set(reach[np.argsort(-S_ex[qi, reach])[:5]].tolist()) & g) / 5.0
        korder = q3.kappa_union(order, anchors, mask, kappa, Rmax)
        for R in Rs:
            for src, acc in ((korder, rr_hit), (order, rr_all)):
                cand = src[:R]
                sim = rerank_vecs[cand] @ rerank_q[qi]
                acc[R][qi] = len(set(cand[np.argsort(-sim)[:5]].tolist()) & g) / 5.0

    has_ex = S_ex is not None
    return dict(reach_r5=100 * reach_hit.mean(), final_r5=100 * final_hit.mean(),
                final_ip=100 * fin_ip.mean(),
                final_exact=(100 * fin_ex.mean()) if has_ex else float("nan"),
                nn_overlap=(100 * nn.mean()) if has_ex else float("nan"),
                rerank={str(R): 100 * rr_hit[R].mean() for R in Rs},
                rerank_nokappa={str(R): 100 * rr_all[R].mean() for R in Rs},
                nodes=float(n_nodes.mean()), cand=float(n_reach.mean()),
                moved=float(n_moved.mean()))


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
    ap.add_argument("--frac", type=float, default=0.10)
    ap.add_argument("--rerank", default="5,10,15,20,30,50,100")
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
    ev = np.arange(a.nq)
    trq = np.arange(a.nq, NQall)
    assert len(trq) > 0, "cần query ngoài tập đánh giá để làm validation"
    gt5_all = [np.array([int(r["index"]) for r in g["top_5_results"][:5]]) for g in gt1]
    gt5 = [gt5_all[i] for i in ev]

    log("=" * 78)
    log(f"tag={a.tag} seed={a.seed}  d0={d0} d1={d1}  N={N} nodes={a.nodes}  (gate 3d)")

    rnd = random.Random(a.seed)
    nid = np.array([rnd.getrandbits(63) for _ in range(a.nodes)], dtype=np.int64)
    P0 = pb.gen_proj(a.seed, d0, a.tables)
    perm = np.random.RandomState(a.seed).permutation(N)
    S = perm[:max(a.tables * 20, int(round(a.frac * N)))]

    anchors0 = pb.build_index(E0, P0, nid)
    load0 = np.bincount(anchors0.ravel(), minlength=a.nodes)
    common = dict(anchors=anchors0, P_list=P0, codes=cd0, cb=cb0, nid=nid, gt5=gt5,
                  K=a.k_query, T=a.probes, cbits=a.cbits, load=load0,
                  kappa=a.kappa, rerank_vecs=E1, rerank_q=Q1[ev], Rs=Rs, exact_vecs=E0)

    # cùng hai ánh xạ, khớp y hệt 03 (gate 3c)
    Wr, lam_dr, _ = q3.fit_ridge_cv(E1[S], E0[S], a.seed, (1e-3, 1e-2, 1e-1, 1.0, 10.0))
    Wf, lam_f = pb.fit_bridge(E0[S], E1[S], "ridge", a.seed)
    WfT = np.ascontiguousarray(Wf.T)

    # n_i: node tự tính từ PQ code (vector tái tạo) và Wf công khai; bản vector gốc chỉ để chẩn đoán
    m0 = cb0.shape[0]
    C0 = cb0[np.arange(m0)[None, :], cd0].reshape(N, d0).astype(np.float32)
    div_pq = np.linalg.norm(C0 @ Wf, axis=1)
    div_ex = np.linalg.norm(E0 @ Wf, axis=1)
    p = np.percentile(div_pq, [5, 50, 95])
    log(f"n_i = ||c_i Wf||: p5={p[0]:.3f} trung vị={p[1]:.3f} p95={p[2]:.3f}  "
        f"(p95/p5 = {p[2] / p[0]:.2f}; càng lớn thì chuyển vị không chia n_i càng lệch)")

    results = []

    def show(r):
        rr = "  ".join(f"R{R}={r['rerank'][str(R)]:5.1f}" for R in Rs)
        log(f"  {r['name']:18s} reach={r['reach_r5']:5.1f} final={r['final_r5']:5.1f} | {rr} | "
            f"nodes={r['nodes']:.0f} cand={r['cand']:.0f} moved={r['moved']:.0f}")

    def arm(name, route, rank=None):
        r = q3.retrieve(route, rank_qv=rank, **common)
        r.update(name=name, nn_overlap=q3.nn_overlap(route if rank is None else rank, E0, gt5))
        results.append(r)
        show(r)
        return r

    log("")
    arm("dual_encode", Q0[ev])
    arm("A_doc_ridge", l2norm(Q1[ev] @ Wr))
    arm("A_split", l2norm(Q1[ev] @ Wr), l2norm(Q1[ev] @ WfT))
    rn = retrieve_norm(l2norm(Q1[ev] @ Wr), l2norm(Q1[ev] @ WfT), div_pq,
                       div_exact=div_ex, **common)
    rn.update(name="A_split_norm")
    results.append(rn)
    show(rn)

    # ---------------- tự kiểm
    exp = GATE2_NN.get((a.tag, a.seed))
    if exp is not None and a.nq == 300 and abs(a.frac - 0.10) < 1e-9:
        ok = abs(rn["nn_overlap"] - exp) < 0.15
        log(f"\n  >>> nn của A_split_norm = {rn['nn_overlap']:.1f}, gate 2 derived_true_v0/ridge = {exp:.1f}"
            f"  ->  {'KHỚP' if ok else 'LỆCH, dừng lại kiểm tra'}")
    f3c = f"probeD_{a.tag}_s{a.seed}_g3c.json"
    if os.path.exists(f3c):
        old = {r["name"]: r for r in json.load(open(f3c))["results"]}
        bad = 0
        for r in results[:3]:
            o = old.get(r["name"])
            keys = ["reach_r5", "final_r5", "final_ip", "final_exact", "nn_overlap", "nodes", "cand", "moved"]
            for k in keys:
                if o is None or abs(o[k] - r[k]) > 1e-9:
                    bad += 1
            for R in r["rerank"]:
                if o is None or abs(o["rerank"][R] - r["rerank"][R]) > 1e-9:
                    bad += 1
        log(f"  >>> dual_encode / A_doc_ridge / A_split so với gate 3c: "
            f"{'KHỚP' if bad == 0 else f'{bad} giá trị LỆCH'}")

    # ---------------- chọn trên validation, như 3c
    vR = 20
    gt5_tr = [gt5_all[i] for i in trq]
    vcommon = dict(common, gt5=gt5_tr, rerank_q=Q1[trq], Rs=[vR], exact_vecs=None)
    log(f"\n--- CHỌN BIẾN THỂ TRÊN VALIDATION ({len(trq)} query không dùng để đánh giá, rerank@{vR}) ---")
    vd = q3.retrieve(Q0[trq], **vcommon)
    val = {}
    for nm, route, rank, norm in (("A_doc_ridge", Wr, None, False), ("A_split", Wr, WfT, False),
                                  ("A_split_norm", Wr, WfT, True)):
        qr = l2norm(Q1[trq] @ route)
        qk = None if rank is None else l2norm(Q1[trq] @ rank)
        rv = (retrieve_norm(qr, qk, div_pq, **vcommon) if norm
              else q3.retrieve(qr, rank_qv=qk, **vcommon))
        val[nm] = dict(reach=rv["reach_r5"], final=rv["final_r5"], rerank=rv["rerank"][str(vR)])
    log(f"  {'dual_encode':18s} val final={vd['final_r5']:5.1f} R{vR}={vd['rerank'][str(vR)]:5.1f}")
    for nm, v in val.items():
        log(f"  {nm:18s} val final={v['final']:5.1f} R{vR}={v['rerank']:5.1f}")
    sel = max(val, key=lambda k: val[k]["rerank"])
    log(f"  -> chọn {sel}")
    diag = dict(val=dict(R=vR, n=int(len(trq)), selected=sel, arms=val,
                         dual=dict(reach=vd["reach_r5"], final=vd["final_r5"],
                                   rerank=vd["rerank"][str(vR)])),
                n_i=dict(p5=float(p[0]), p50=float(p[1]), p95=float(p[2])), lam_r=lam_dr, lam_f=lam_f)

    # ---------------- tổng kết
    de = results[0]
    sr = next(r for r in results if r["name"] == sel)
    log("\n" + "=" * 78)
    log(f"Biến thể chọn theo validation: {sel}  reach={sr['reach_r5']:.1f} ({sr['reach_r5'] - de['reach_r5']:+.1f})"
        f"  final={sr['final_r5']:.1f} ({sr['final_r5'] - de['final_r5']:+.1f})")
    log("    rerank so với dual: " + "  ".join(
        f"R{R}={sr['rerank'][str(R)]:.1f} ({sr['rerank'][str(R)] - de['rerank'][str(R)]:+.1f})" for R in Rs))
    log("\nCHẨN ĐOÁN: nn = toàn corpus không PQ | exact = reachable không PQ | "
        "ip = ADC tích vô hướng KHÔNG chia n_i (với A_split_norm) | l2 = final")
    log(f"  {'nhánh':18s}    nn  exact     ip  final")
    for r in results:
        log(f"  {r['name']:18s} {r['nn_overlap']:5.1f}  {r['final_exact']:5.1f}  "
            f"{r['final_ip']:5.1f}  {r['final_r5']:5.1f}")
    log("\nTIÊU CHÍ GATE (chốt trước): ĐẠT nếu adapter+rerank không thấp hơn dual_rerank quá 5 điểm ở cùng R"
        " và reach không thấp hơn dual quá 5 điểm; VƯỢT DUAL nếu final > dual_encode")

    out = a.out or f"probeE_{a.tag}_s{a.seed}.json"
    json.dump(dict(argv=vars(a), d0=d0, d1=d1, n_sample_doc=int(len(S)), diag=diag,
                   results=results), open(out, "w"), indent=1)
    log(f"\n-> {out}   ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
