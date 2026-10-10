#!/usr/bin/env python3
"""
04b_probe_multiepoch2.py  —  CHẠY TRÊN node-dal-02 (CPU). Multi-epoch bản 2, sau kết quả đợt 2.

Đợt 2 (04) cho thấy bốn vấn đề:
  1. RRF thành xen kẽ vì hai danh sách rời nhau: top-5 luôn 3 record E1 + 2 record E0 bất kể mỗi
     partition lớn bao nhiêu, sụt 10 đến 22 điểm khi hai partition lệch (f = 10%, 90%).
  2. CAL hồi quy OLS nên co điểm E0 về trung bình, gộp nghiêng hẳn về E1; lại học trên chính S.
  3. Trong lúc chuyển tiếp số node bị chạm gấp đôi.
  4. Chỉ mục native e5 gần như quét toàn bộ corpus (khoá SRP dồn về vài node).
Bản này giữ nguyên mọi thiết lập của 04 và thêm:
  gộp       PROP, SD, PROB (xem me_common.py); so trên validation
  khoá E1   u  = như 04
            c  = record và query cùng trừ vector trung bình document (tính trên E1[S])
            cq = record trừ trung bình document, query trừ trung bình query (tính trên query validation)
            Chỉ đổi khoá SRP; PQ code và cách chấm điểm giữ nguyên. Chọn c hay cq trên validation (K*).
  ngân sách khi cả hai epoch còn dữ liệu: T1 = clip(round(T·f), 1, T-1) probe mỗi bảng cho E1,
            T0 = T - T1 cho E0, để số node bị chạm xấp xỉ một lần tra cứu.
  học lại   ở mỗi f, Wr, Wf, n_i và hiệu chỉnh học lại trên toàn bộ phần đã migrate M (cross-fit).
Nhánh:
  AD_{RRF,CAL,PROP,SD,PROB}  DU_{RRF,CAL,PROP,SD,PROB}  E1ONLY     như 04, thêm 3 cách gộp
  E1ONLY_c  E1ONLY_cq  ADc_{PROP,PROB}  ADcq_{PROP,PROB}           khoá E1 trừ trung bình
  ADb_{PROP,PROB}  DUb_PROB                                         chia ngân sách probe
  ADR_{PROP,PROB}                                                   adapter học lại trên M
  ADF_{PROP,PROB}  DUF_PROB                                         học lại + khoá K* + chia ngân sách
Thêm: recall của từng phía so với top-5 thật TRONG chính partition của nó (đo adapter trên
document chưa thấy, tách khỏi bước gộp) và phân bố tải node của từng chỉ mục.

Tự kiểm:
  (1) f = 0 khớp gate 3d (probeE_...json)
  (2) AD_RRF, AD_CAL, DU_RRF, DU_CAL, E1ONLY khớp đúng từng số của probe 04 (probeF_...json) ở mọi f
  (3) ADR_* ở f = |S|/N trùng AD_*, vì khi đó M = S (đi lại toàn bộ đường học lại)

CHẠY: python3 evo/04b_probe_multiepoch2.py --tag bgebase --seed 20235956
"""
import argparse, json, os, random, time
import numpy as np
import me_common as mc

np.seterr(invalid='ignore', divide='ignore')
q3, pb = mc.q3, mc.pb
log, l2norm = mc.log, mc.l2norm

FUS = ["RRF", "CAL", "PROP", "SD", "PROB"]
# tên nhánh -> (phía E0, ngân sách E0, phía E1, ngân sách E1, cách gộp, bộ hiệu chỉnh)
# ngân sách: "T" = đủ T probe, "b" = phần chia theo f; phía E1 "K" = biến thể khoá chọn trên validation
SPEC = {}
for _k in FUS:
    SPEC[f"AD_{_k}"] = ("A", "T", "U", "T", _k, "AD")
for _k in FUS:
    SPEC[f"DU_{_k}"] = ("D", "T", "U", "T", _k, "DU")
SPEC["E1ONLY"] = (None, None, "U", "T", None, None)
SPEC["E1ONLY_c"] = (None, None, "C", "T", None, None)
SPEC["E1ONLY_cq"] = (None, None, "Q", "T", None, None)
for _k in ("PROP", "PROB"):
    SPEC[f"ADc_{_k}"] = ("A", "T", "C", "T", _k, "AD")
    SPEC[f"ADcq_{_k}"] = ("A", "T", "Q", "T", _k, "AD")
for _k in ("PROP", "PROB"):
    SPEC[f"ADb_{_k}"] = ("A", "b", "U", "b", _k, "AD")
SPEC["DUb_PROB"] = ("D", "b", "U", "b", "PROB", "DU")
for _k in ("PROP", "PROB"):
    SPEC[f"ADR_{_k}"] = ("AR", "T", "U", "T", _k, "ADR")
for _k in ("PROP", "PROB"):
    SPEC[f"ADF_{_k}"] = ("AR", "b", "K", "b", _k, "ADR")
SPEC["DUF_PROB"] = ("D", "b", "K", "b", "PROB", "DU")
ARMS_EVAL = list(SPEC)
ARMS_VAL = [m for m in ARMS_EVAL if SPEC[m][0] in (None, "A", "D") and SPEC[m][1] in (None, "T")
            and SPEC[m][2] in ("U", "C", "Q")]
OLD04 = ["AD_RRF", "AD_CAL", "DU_RRF", "DU_CAL", "E1ONLY"]


def budgets(f, T):
    if f <= 0:
        return T, 0
    if f >= 1:
        return 0, T
    t1 = int(min(T - 1, max(1, round(T * f))))
    return T - t1, t1


def evaluate(arms, sides, gts, qmat, st, cals, kappa, Rs, E1, side_recall=None):
    """Chạy các nhánh trên một tập query ở một trạng thái partition `st`.
    sides: dict khoá phía -> list Side2 theo query; gts: list mảng GT top-5; qmat: query M1 (để rerank)."""
    Rmax = max(Rs)
    acc = {m: dict(reach=[], final=[], R={R: [] for R in Rs}, F={R: [] for R in Rs}, nodes=[], cand=[],
                   moved=[], e0share=[], pexp0=[]) for m in arms}
    sr = {k: [] for k in (side_recall or {})}
    inE1 = st["inE1"]
    gtE0 = []
    for qi in range(len(gts)):
        garr = gts[qi]
        g = set(garr.tolist())
        gtE0.append(float(st["act"][0][garr].mean()))
        cache = {}

        def V(key, bud):
            sk = st["Kstar"] if key == "K" else key
            t = st["T"] if bud == "T" else (st["T0"] if sk in ("A", "D", "AR") else st["T1"])
            ck = (sk, t)
            if ck not in cache:
                part = 0 if sk in ("A", "D", "AR") else 1
                act, has = st["act"][part], st["has"][part]
                load = st["load"][sk if part == 1 else "E0"]
                side = sides[sk][qi]
                n, lst, x = side.ranked(act, kappa, Rmax, t)
                tch = side.touched(t)
                cache[ck] = dict(
                    n=n, l=lst, x=x,
                    nodes=len(tch) if has else 0,
                    moved=np.minimum(load[tch], kappa).sum() if has else 0,
                    hits=int((np.isin(garr, side.reach_set(t)) & act[garr]).sum()))
            return cache[ck]

        for m in arms:
            k0, b0, k1, b1, fus, ck = SPEC[m]
            v1 = V(k1, b1)
            if k0 is None:
                lst, hits, nc, nn, mv = v1["l"][:Rmax], v1["hits"], v1["n"], v1["nodes"], v1["moved"]
            else:
                v0 = V(k0, b0)
                lst = mc.fuse(fus, v0["l"], v0["x"], v1["l"], v1["x"], Rmax,
                              st["share0"], st["share1"], cals[ck], diag=acc[m]["pexp0"])
                hits, nc = v0["hits"] + v1["hits"], v0["n"] + v1["n"]
                nn, mv = v0["nodes"] + v1["nodes"], v0["moved"] + v1["moved"]
            A = acc[m]
            A["reach"].append(hits / 5.0)
            A["final"].append(len(set(lst[:5].tolist()) & g) / 5.0)
            A["e0share"].append(float(np.mean([not inE1[d] for d in lst[:5]])) if len(lst) else 0.0)
            A["nodes"].append(nn); A["moved"].append(mv)
            A["cand"].append(nc)
            for R in Rs:
                A["R"][R].append(mc.rerank_hits(lst[:R], E1, qmat[qi], g))
                A["F"][R].append(int((~inE1[lst[:R]]).sum()) if len(lst) else 0)

        # recall của từng phía so với top-5 thật trong partition của nó
        for key, (part, gtp) in (side_recall or {}).items():
            if key not in sides or gtp[qi] is None:
                continue
            v = V(key, "T")
            top = set(v["l"][:5].tolist())
            sr[key].append(len(top & set(gtp[qi].tolist())) / max(1, min(5, len(gtp[qi]))))

    res = {}
    for m, A in acc.items():
        res[m] = dict(reach_r5=100 * np.mean(A["reach"]), final_r5=100 * np.mean(A["final"]),
                      rerank={str(R): 100 * np.mean(A["R"][R]) for R in Rs},
                      fetch={str(R): float(np.mean(A["F"][R])) for R in Rs},
                      nodes=float(np.mean(A["nodes"])), cand=float(np.mean(A["cand"])),
                      moved=float(np.mean(A["moved"])), e0_share_top5=float(np.mean(A["e0share"])))
        if A["pexp0"]:
            res[m]["model_e0_top5"] = float(np.nanmean(A["pexp0"])) / 5.0
    res["_gt_e0_share"] = float(np.mean(gtE0))
    srr = {k: (100 * float(np.mean(v)) if v else float("nan")) for k, v in sr.items()}
    return res, srr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--dataset", default="code")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--seed", type=int, default=20235956)
    ap.add_argument("--nodes", type=int, default=10000)
    ap.add_argument("--nq", type=int, default=300)
    ap.add_argument("--tables", type=int, default=5)
    ap.add_argument("--k-query", type=int, default=20)
    ap.add_argument("--probes", type=int, default=8)
    ap.add_argument("--cbits", type=int, default=16)
    ap.add_argument("--dsub", type=int, default=2)
    ap.add_argument("--kappa", type=int, default=30)
    ap.add_argument("--frac", type=float, default=0.10, help="mẫu S dùng học adapter (đã nhúng lại bằng M1)")
    ap.add_argument("--fmig", default="0,0.1,0.2,0.3,0.5,0.7,0.9,1.0", help="tỉ lệ corpus đã có record E1")
    ap.add_argument("--rerank", default="5,10,20,50,100")
    ap.add_argument("--cal-top", type=int, default=30)
    ap.add_argument("--folds", type=int, default=5, help="số fold cross-fit khi hiệu chỉnh adapter")
    ap.add_argument("--cal-cap", type=int, default=2000, help="tối đa số document hiệu chỉnh khi học lại")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    t0 = time.time()
    D, ds = a.data_dir, a.dataset
    Rs = [int(x) for x in a.rerank.split(",")]
    Rmax = max(Rs)
    fgrid = [float(x) for x in a.fmig.split(",")]
    T = a.probes

    E0 = np.load(f"{D}/{ds}_corpus_embeddings.npy").astype(np.float32)
    Q0 = np.load(f"{D}/{ds}_query_embeddings.npy").astype(np.float32)
    cb0 = np.load(f"{D}/{ds}_pq_codebook_m512.npy").astype(np.float32)
    cd0 = np.load(f"{D}/{ds}_pq_codes_m512.npy")
    E1 = np.load(f"{D}/{ds}_{a.tag}_corpus_embeddings.npy").astype(np.float32)
    Q1 = np.load(f"{D}/{ds}_{a.tag}_query_embeddings.npy").astype(np.float32)
    gt1 = json.load(open(f"{D}/{ds}_{a.tag}_ground_truth.json"))
    N, d0 = E0.shape; d1 = E1.shape[1]; NQall = len(gt1)
    m1 = d1 // a.dsub
    ev, trq = np.arange(a.nq), np.arange(a.nq, NQall)
    assert len(trq) > 0, "cần query ngoài tập đánh giá để hiệu chỉnh và chọn trên validation"
    gt5_all = [np.array([int(r["index"]) for r in g["top_5_results"][:5]]) for g in gt1]

    rnd = random.Random(a.seed)
    nid = np.array([rnd.getrandbits(63) for _ in range(a.nodes)], dtype=np.int64)
    P0 = pb.gen_proj(a.seed, d0, a.tables)
    P1 = pb.gen_proj(a.seed, d1, a.tables)
    perm = np.random.RandomState(a.seed).permutation(N)
    nS = max(a.tables * 20, int(round(a.frac * N)))
    S = perm[:nS]
    mig_order = perm
    log("=" * 78)
    log(f"[04b] dataset={ds} tag={a.tag} seed={a.seed}  N={N} nodes={a.nodes}  mẫu S={nS} ({nS / N:.1%})  f={fgrid}")

    # ---------------- adapter như gate 3d và 04
    Wr, _, _ = q3.fit_ridge_cv(E1[S], E0[S], a.seed, (1e-3, 1e-2, 1e-1, 1.0, 10.0))
    Wf, _ = pb.fit_bridge(E0[S], E1[S], "ridge", a.seed)
    WfT = np.ascontiguousarray(Wf.T)
    m0 = cb0.shape[0]
    C0 = cb0[np.arange(m0)[None, :], cd0].reshape(N, d0).astype(np.float32)
    n_i = np.linalg.norm(C0 @ Wf, axis=1)

    cb1 = pb.pq_train(E1[S], m1, a.seed)
    cd1 = pb.pq_encode(E1, cb1)
    anchors0 = pb.build_index(E0, P0, nid)
    anchors1 = pb.build_index(E1, P1, nid)
    mu_d = E1[S].mean(0).astype(np.float32)
    mu_q = Q1[trq].mean(0).astype(np.float32)
    anchors1c = pb.build_index(E1 - mu_d, P1, nid)
    loads_all = dict(E0=mc.load_stats(anchors0, a.nodes), E1u=mc.load_stats(anchors1, a.nodes),
                     E1c=mc.load_stats(anchors1c, a.nodes))
    for k, v in loads_all.items():
        log(f"tải node {k:4s}: max={v['max']} p99={v['p99']:.0f} TB={v['mean']:.1f} "
            f"rỗng={100 * v['empty_frac']:.0f}% top1%node giữ {100 * v['top1pct_share']:.1f}% bản ghi")
    log(f"|mu_d|={np.linalg.norm(mu_d):.3f} |mu_q|={np.linalg.norm(mu_q):.3f} "
        f"cos(mu_d,mu_q)={float(mu_d @ mu_q / np.linalg.norm(mu_d) / np.linalg.norm(mu_q)):.3f}")

    # ---------------- hiệu chỉnh
    # (a) CAL đúng như 04 (validation x top-30 trong S, điểm adapter in-sample)
    qv1 = l2norm(Q1[trq]); qhat = Q1[trq] @ WfT; qhn = l2norm(qhat)
    qnorm = np.linalg.norm(qhat, axis=1)
    xa, xd, y = [], [], []
    for i in range(len(trq)):
        y.append(mc.adc_ip(qv1[i], cb1, cd1[S]))
        xa.append(mc.adc_ip(qhn[i], cb0, cd0[S]) / n_i[S] * qnorm[i])
        xd.append(mc.adc_ip(Q0[trq][i], cb0, cd0[S]))
    ca, cb_, cr = mc.fit_cal_04(xa, y, a.cal_top)
    da, db, dr = mc.fit_cal_04(xd, y, a.cal_top)
    # (b) cross-fit cho adapter: mỗi document trong S chấm bằng Wf học trên S trừ fold của nó
    Xcf, lam_cf = mc.crossfit_adapter_x(E0, E1, C0, cb0, cd0, Q1[trq], S, S, a.folds, a.seed)
    Ycf = mc.e1_scores(Q1[trq], cb1, cd1, S)
    ols_ad = mc.ols_top(list(Xcf), list(Ycf), a.cal_top)
    ols_ad_in = mc.ols_top(xa, y, a.cal_top)
    ols_du = mc.ols_top(xd, y, a.cal_top)
    sig1 = mc.sigma_e1(Q1[trq], E1, cb1, cd1, S, a.cal_top)
    cals = dict(AD=dict(cal_a=ca, cal_b=cb_, ols=ols_ad, sig1=sig1),
                DU=dict(cal_a=da, cal_b=db, ols=ols_du, sig1=sig1))
    log(f"CAL như 04: adapter y = {ca:.3f}·x {cb_:+.3f} (r={cr:.3f}); dual y = {da:.3f}·x {db:+.3f} (r={dr:.3f})")
    log(f"adapter in-sample : a={ols_ad_in['a']:.3f} b={ols_ad_in['b']:+.3f} sigma={ols_ad_in['sig']:.4f} r={ols_ad_in['r']:.3f}")
    log(f"adapter cross-fit : a={ols_ad['a']:.3f} b={ols_ad['b']:+.3f} sigma={ols_ad['sig']:.4f} r={ols_ad['r']:.3f}"
        f"  (lambda các fold: {lam_cf})")
    log(f"dual              : a={ols_du['a']:.3f} b={ols_du['b']:+.3f} sigma={ols_du['sig']:.4f} r={ols_du['r']:.3f}")
    log(f"độ lệch ADC của E1: sigma1={sig1:.4f}")

    # ---------------- định tuyến và chấm điểm (một lần cho mỗi query)
    def build_sides(qidx):
        q1 = l2norm(Q1[qidx])
        qr0 = l2norm(Q1[qidx] @ Wr)
        qk = l2norm(Q1[qidx] @ WfT); qkn = np.linalg.norm(Q1[qidx] @ WfT, axis=1)
        q0 = Q0[qidx]
        NA = mc.route_keys(qr0, P0, nid, a.k_query, T, a.cbits)
        ND = mc.route_keys(q0, P0, nid, a.k_query, T, a.cbits)
        NU = mc.route_keys(q1, P1, nid, a.k_query, T, a.cbits)
        NC = mc.route_keys(q1 - mu_d, P1, nid, a.k_query, T, a.cbits)
        NQ = mc.route_keys(q1 - mu_q, P1, nid, a.k_query, T, a.cbits)

        def fa(qi):
            def f(r):
                k = mc.adc_ip(qk[qi], cb0, cd0[r]) / n_i[r]
                return k, k * qkn[qi]
            return f

        def fd(qi):
            return lambda r: (-mc.adc_l2(q0[qi], cb0, cd0[r]), mc.adc_ip(q0[qi], cb0, cd0[r]))

        def f1(qi):
            return lambda r: (-mc.adc_l2(q1[qi], cb1, cd1[r]), mc.adc_ip(q1[qi], cb1, cd1[r]))

        sd = dict(A=[], D=[], U=[], C=[], Q=[])
        for qi in range(len(qidx)):
            sd["A"].append(mc.Side2(NA[qi], anchors0, a.nodes, fa(qi)))
            sd["D"].append(mc.Side2(ND[qi], anchors0, a.nodes, fd(qi)))
            sd["U"].append(mc.Side2(NU[qi], anchors1, a.nodes, f1(qi)))
            sd["C"].append(mc.Side2(NC[qi], anchors1c, a.nodes, f1(qi)))
            sd["Q"].append(mc.Side2(NQ[qi], anchors1c, a.nodes, f1(qi)))
        return sd

    sides_v = build_sides(trq)
    sides_e = build_sides(ev)
    log(f"định tuyến và chấm điểm xong ({time.time() - t0:.0f}s)")

    def state(f):
        nM = int(round(f * N))
        inE1 = np.zeros(N, dtype=bool); inE1[mig_order[:nM]] = True
        act0, act1 = ~inE1, inE1
        T0b, T1b = budgets(f, T)
        return dict(nM=nM, inE1=inE1, act=(act0, act1), has=(bool(act0.any()), bool(act1.any())),
                    load=dict(E0=np.bincount(anchors0[:, act0].ravel(), minlength=a.nodes),
                              U=np.bincount(anchors1[:, act1].ravel(), minlength=a.nodes),
                              C=np.bincount(anchors1c[:, act1].ravel(), minlength=a.nodes),
                              Q=np.bincount(anchors1c[:, act1].ravel(), minlength=a.nodes)),
                    share1=nM / N, share0=1.0 - nM / N, T=T, T0=T0b, T1=T1b, Kstar="C")

    # ---------------- validation: so cách gộp, chọn biến thể khoá E1
    gts_v = [gt5_all[i] for i in trq]
    val = {}
    for f in fgrid:
        st = state(f)
        val[f"{f:g}"], _ = evaluate(ARMS_VAL, sides_v, gts_v, Q1[trq], st, cals, a.kappa, Rs, E1)
    fk = f"{max(fgrid):g}"
    vc, vq = val[fk]["E1ONLY_c"]["final_r5"], val[fk]["E1ONLY_cq"]["final_r5"]
    Kstar = "C" if vc >= vq else "Q"
    log(f"\nVALIDATION ({len(trq)} query), f = {fk}: E1ONLY u={val[fk]['E1ONLY']['final_r5']:.1f}"
        f"  c={vc:.1f}  cq={vq:.1f}  ->  khoá E1 chọn: {'c' if Kstar == 'C' else 'cq'}")
    inner = [f"{f:g}" for f in fgrid if 0 < f < 1]
    for side in ("AD", "DU"):
        log(f"  validation {side}, trung bình các f giữa 0 và 1:  " + "  ".join(
            f"{k}: final={np.mean([val[f][f'{side}_{k}']['final_r5'] for f in inner]):5.1f}"
            f" R20={np.mean([val[f][f'{side}_{k}']['rerank']['20'] for f in inner]):5.1f}" for k in FUS))

    # ---------------- đánh giá
    S_ex = l2norm(Q1[ev]) @ E1.T
    results, side_rec, refit_info = {}, {}, {}
    gts_e = [gt5_all[i] for i in ev]
    for f in fgrid:
        st = state(f)
        st["Kstar"] = Kstar
        nM = st["nM"]
        sides = dict(sides_e)
        cals_f = dict(cals)
        cals_f["ADR"] = cals["AD"]
        sides["AR"] = sides_e["A"]
        if 0 < nM < N:
            M = mig_order[:nM]
            WrF, lamr, _ = q3.fit_ridge_cv(E1[M], E0[M], a.seed, mc.LAMS)
            WfF, lamf = pb.fit_bridge(E0[M], E1[M], "ridge", a.seed)
            n_iF = np.linalg.norm(C0 @ WfF, axis=1)
            Cf = M[:max(a.cal_cap, nS)]
            Xf, lamk = mc.crossfit_adapter_x(E0, E1, C0, cb0, cd0, Q1[trq], M, Cf, a.folds, a.seed)
            Yf = mc.e1_scores(Q1[trq], cb1, cd1, Cf)
            ols_f = mc.ols_top(list(Xf), list(Yf), a.cal_top)
            cals_f["ADR"] = dict(cal_a=None, cal_b=None, ols=ols_f, sig1=sig1)
            qrF = l2norm(Q1[ev] @ WrF)
            WfFT = np.ascontiguousarray(WfF.T)
            qkF = l2norm(Q1[ev] @ WfFT); qkFn = np.linalg.norm(Q1[ev] @ WfFT, axis=1)
            NAR = mc.route_keys(qrF, P0, nid, a.k_query, T, a.cbits)

            def far(qi):
                def fn(r):
                    k = mc.adc_ip(qkF[qi], cb0, cd0[r]) / n_iF[r]
                    return k, k * qkFn[qi]
                return fn
            sides["AR"] = [mc.Side2(NAR[qi], anchors0, a.nodes, far(qi)) for qi in range(len(ev))]
            refit_info[f"{f:g}"] = dict(n_train=int(nM), n_cal=int(len(Cf)), lam_r=lamr, lam_f=lamf,
                                        ols=ols_f)
        # GT trong từng partition
        gt0, gt1p = [], []
        g0 = np.flatnonzero(st["act"][0]); g1 = np.flatnonzero(st["act"][1])
        for qi in range(len(ev)):
            s = S_ex[qi]
            gt0.append(g0[np.argsort(-s[g0])[:5]] if len(g0) else None)
            gt1p.append(g1[np.argsort(-s[g1])[:5]] if len(g1) else None)
        srq = {k: (0, gt0) for k in ("A", "AR", "D")}
        srq.update({k: (1, gt1p) for k in ("U", "C", "Q")})
        res, srr = evaluate(ARMS_EVAL, sides, gts_e, Q1[ev], st, cals_f, a.kappa, Rs, E1, side_recall=srq)
        results[f"{f:g}"] = res
        side_rec[f"{f:g}"] = srr
        log(f"\n--- f = {f:.0%}  (record E1: {nM}, record E0: {N - nM}; ngân sách chia T0={st['T0']} T1={st['T1']})"
            f"  [{time.time() - t0:.0f}s]")
        log(f"  tỉ lệ ground truth nằm ở E0: {100 * res['_gt_e0_share']:.0f}%")
        for m in ARMS_EVAL:
            r = res[m]
            extra = (f" (mô hình PROB: {100 * r['model_e0_top5']:3.0f}%)" if "model_e0_top5" in r else "")
            log(f"  {m:10s} reach={r['reach_r5']:5.1f} final={r['final_r5']:5.1f} R20={r['rerank']['20']:5.1f} "
                f"R50={r['rerank']['50']:5.1f} | nodes={r['nodes']:4.0f} cand={r['cand']:6.0f} "
                f"moved={r['moved']:5.0f} top5 từ E0={100 * r['e0_share_top5']:3.0f}%{extra}")
        log("  recall từng phía trong partition của nó: " + "  ".join(
            f"{k}={v:5.1f}" for k, v in srr.items()))

    # ---------------- tự kiểm
    checks = {}
    pre = "" if ds == "code" else f"{ds}_"
    f3d = f"probeE_{pre}{a.tag}_s{a.seed}.json"
    if "0" in results and os.path.exists(f3d) and abs(a.frac - json.load(open(f3d))["argv"]["frac"]) < 1e-9:
        old = {r["name"]: r for r in json.load(open(f3d))["results"]}
        bad, n = 0, 0
        for mth, ref in (("AD_RRF", "A_split_norm"), ("AD_CAL", "A_split_norm"), ("AD_PROB", "A_split_norm"),
                         ("DU_RRF", "dual_encode"), ("DU_PROB", "dual_encode")):
            new, o = results["0"][mth], old[ref]
            for k in ("reach_r5", "final_r5", "nodes", "cand", "moved"):
                n += 1; bad += abs(new[k] - o[k]) > 1e-9
            for R in new["rerank"]:
                if R in o["rerank"]:
                    n += 1; bad += abs(new["rerank"][R] - o["rerank"][R]) > 1e-9
        checks["gate3d_f0"] = dict(n=n, bad=int(bad))
        log(f"\n>>> f = 0 so với gate 3d ({f3d}): {n} giá trị, {'KHỚP' if bad == 0 else f'{bad} LỆCH'}")
    f04 = f"probeF_{pre}{a.tag}_s{a.seed}.json"
    if os.path.exists(f04) and abs(a.frac - json.load(open(f04))["argv"].get("frac", 0.10)) < 1e-9:
        o4 = json.load(open(f04))["results"]
        bad, n = 0, 0
        for fk2, rr in results.items():
            if fk2 not in o4:
                continue
            for mth in OLD04:
                new, o = rr[mth], o4[fk2][mth]
                for k in ("reach_r5", "final_r5", "nodes", "cand", "moved", "e0_share_top5"):
                    n += 1; bad += abs(new[k] - o[k]) > 1e-9
                for R in new["rerank"]:
                    if R in o["rerank"]:
                        n += 1; bad += abs(new["rerank"][R] - o["rerank"][R]) > 1e-9
        checks["probe04"] = dict(n=n, bad=int(bad))
        log(f">>> 5 nhánh cũ so với probe 04 ({f04}), mọi f: {n} giá trị, {'KHỚP' if bad == 0 else f'{bad} LỆCH'}")
    fS = next((f"{f:g}" for f in fgrid if int(round(f * N)) == nS), None)
    if fS in results and 0 < nS < N:
        bad, n = 0, 0
        for k in ("PROP", "PROB"):
            new, o = results[fS][f"ADR_{k}"], results[fS][f"AD_{k}"]
            for kk in ("reach_r5", "final_r5", "nodes", "cand", "moved", "e0_share_top5"):
                n += 1; bad += abs(new[kk] - o[kk]) > 1e-9
            for R in new["rerank"]:
                n += 1; bad += abs(new["rerank"][R] - o["rerank"][R]) > 1e-9
        checks["refit_at_S"] = dict(n=n, bad=int(bad))
        log(f">>> ADR so với AD ở f = {nS / N:.1%} (M = S): {n} giá trị, {'KHỚP' if bad == 0 else f'{bad} LỆCH'}")

    out = a.out or f"probeG_{pre}{a.tag}_s{a.seed}.json"
    json.dump(dict(argv=vars(a), n_sample=int(nS), N=int(N), Kstar=("c" if Kstar == "C" else "cq"),
                   cal=dict(cal04=dict(adapter=[ca, cb_, cr], dual=[da, db, dr]), adapter_cf=ols_ad,
                            adapter_insample=ols_ad_in, dual=ols_du, sig1=sig1),
                   loads=loads_all, budgets={f"{f:g}": budgets(f, T) for f in fgrid},
                   val=val, results=results, side_recall=side_rec, refit=refit_info, checks=checks,
                   mu=dict(norm_d=float(np.linalg.norm(mu_d)), norm_q=float(np.linalg.norm(mu_q)))),
              open(out, "w"), indent=1)
    log(f"\n-> {out}   ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
