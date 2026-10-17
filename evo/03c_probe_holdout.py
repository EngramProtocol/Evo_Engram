#!/usr/bin/env python3
"""
03c_probe_holdout.py  —  CHẠY TRÊN node-dal-02 (CPU). Kiểm lại gate 3 ở chế độ holdout, thêm baseline MLP.

(1) Holdout. Ở 03b, mẫu S (dùng học adapter) vẫn nằm trong E0 lúc đánh giá, nên adapter được chấm cả
    trên document nó đã học. Trong triển khai thật, S đã migrate sang E1 và adapter chỉ phục vụ document
    chưa thấy. Với --holdout 1, S bị loại khỏi chỉ mục E0; ground truth tính lại là top-5 theo M1 trong
    phần còn lại; dual và mọi adapter đánh giá trên cùng chỉ mục đã loại S (so sánh ghép cặp vẫn công bằng).
(2) Baseline MLP theo kiểu Drift-Adapter (Vejendla, EMNLP 2025): ánh xạ query M1 -> M0 bằng
        g(q) = q·W_ridge + W2·GELU(q·W1 + b1) + b2
    (ridge cố định, residual MLP một lớp ẩn 256 chiều), học trên cặp (E1[S], E0[S]) với mất mát cosine,
    Adam, weight decay; số epoch chọn bằng dừng sớm trên 20% S, rồi học lại trên toàn S đúng số epoch đó.
    Hai cách dùng:
      A_mlp             một ánh xạ cho cả định tuyến lẫn xếp hạng, đúng cách Drift-Adapter dùng
      A_mlp_split_norm  MLP chỉ để định tuyến; xếp hạng như A_split_norm (chuyển vị ridge xuôi, chia n_i)
Nhánh: dual_encode, A_doc_ridge, A_split_norm, A_mlp, A_mlp_split_norm; chọn biến thể trên validation như 03b.

Tự kiểm: --holdout 0 với frac 0.10: dual_encode, A_doc_ridge, A_split_norm phải khớp đúng từng số của
probeE (gate 3d) cùng seed. Ground truth tính lại trên toàn corpus phải trùng file ground truth.

Đợt 5: --pair-src pq học Wr, Wf (và MLP nếu bật) trên cặp (E1[S], c_S), với c_S là bản tái tạo PQ của
record E0 thay cho embedding M0 đầy đủ. Chỉ mục E0, dual và mọi phép chấm điểm giữ nguyên; mặc định exact
giữ đúng từng số của đợt 4. Tự kiểm: dual_encode phải trùng file exact cùng seed và cùng frac.

CHẠY: python3 evo/03c_probe_holdout.py --tag bgebase --seed 20235956 --frac 0.10 --holdout 1
"""
import argparse, importlib.util, json, os, random, time
import numpy as np
np.seterr(invalid='ignore', divide='ignore', over='ignore')

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("p3b", os.path.join(_here, "03b_probe_norm.py"))
p3b = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p3b)
q3, pb = p3b.q3, p3b.pb
log, l2norm, angles_deg = pb.log, pb.l2norm, pb.angles_deg
LAMS = (1e-3, 1e-2, 1e-1, 1.0, 10.0)
_C = np.float32(np.sqrt(2.0 / np.pi))


# ----------------------------------------------------------------- MLP (numpy)
def _gelu(z):
    t = np.tanh(_C * (z + np.float32(0.044715) * z ** 3))
    return np.float32(0.5) * z * (1 + t), t


def _gelu_grad(z, t):
    return (np.float32(0.5) * (1 + t)
            + np.float32(0.5) * z * (1 - t * t) * _C * (1 + np.float32(3 * 0.044715) * z * z))


def _mean_angle(O, Y):
    return float(angles_deg(O, Y).mean())


def train_residual_mlp(X, Y, W_lin, hidden, epochs, lr, wd, batch, seed, Xva=None, Yva=None, patience=15):
    """Residual MLP trên nền ánh xạ tuyến tính cố định W_lin, mất mát 1 - cos. Có (Xva, Yva) thì dừng sớm
    theo góc trung bình trên tập đó và trả về tham số tốt nhất; không có thì chạy đủ `epochs`."""
    rng = np.random.RandomState(seed)
    X = X.astype(np.float32); Y = l2norm(Y.astype(np.float32))
    W_lin = W_lin.astype(np.float32)
    d_in, d_out = W_lin.shape
    W1 = (rng.randn(d_in, hidden) * np.sqrt(2.0 / d_in)).astype(np.float32)
    b1 = np.zeros(hidden, np.float32); W2 = np.zeros((hidden, d_out), np.float32); b2 = np.zeros(d_out, np.float32)
    P = [W1, b1, W2, b2]
    Mo = [np.zeros_like(p) for p in P]; Ve = [np.zeros_like(p) for p in P]
    base = X @ W_lin
    has_val = Xva is not None
    if has_val:
        Xva = Xva.astype(np.float32); Yva = l2norm(Yva.astype(np.float32)); base_va = Xva @ W_lin

    def pred_va():
        H, _ = _gelu(Xva @ W1 + b1)
        return base_va + H @ W2 + b2

    a0 = _mean_angle(base_va, Yva) if has_val else float("nan")
    best, best_ep, best_P, bad = a0, 0, [p.copy() for p in P], 0
    step, ep = 0, 0
    for ep in range(1, epochs + 1):
        idx = rng.permutation(len(X))
        for s in range(0, len(X), batch):
            b = idx[s:s + batch]
            Xb, Yb = X[b], Y[b]
            Z = Xb @ W1 + b1
            H, t = _gelu(Z)
            O = base[b] + H @ W2 + b2
            no = np.maximum(np.linalg.norm(O, axis=1, keepdims=True), 1e-6)
            cos = (O * Yb).sum(1, keepdims=True) / no
            dO = -(Yb / no - cos * O / (no * no)) / np.float32(len(b))
            gW2 = H.T @ dO + wd * W2; gb2 = dO.sum(0)
            dZ = (dO @ W2.T) * _gelu_grad(Z, t)
            gW1 = Xb.T @ dZ + wd * W1; gb1 = dZ.sum(0)
            step += 1
            for p, g, mo, ve in zip(P, (gW1, gb1, gW2, gb2), Mo, Ve):
                mo *= 0.9; mo += 0.1 * g
                ve *= 0.999; ve += 0.001 * g * g
                p -= lr * (mo / (1 - 0.9 ** step)) / (np.sqrt(ve / (1 - 0.999 ** step)) + 1e-8)
        if has_val:
            va = _mean_angle(pred_va(), Yva)
            if va < best - 1e-4:
                best, best_ep, best_P, bad = va, ep, [p.copy() for p in P], 0
            else:
                bad += 1
                if bad >= patience:
                    break
    if not has_val:
        best_P, best_ep = [p.copy() for p in P], ep
    return best_P, dict(best_epoch=int(best_ep), val_angle=best, ridge_val_angle=a0, epochs_run=int(ep))


def mlp_apply(Q, W_lin, Pm):
    W1, b1, W2, b2 = Pm
    H, _ = _gelu(Q.astype(np.float32) @ W1 + b1)
    return Q.astype(np.float32) @ W_lin.astype(np.float32) + H @ W2 + b2


def fit_mlp_adapter(E1s, E0s, Wr_all, a):
    """Chọn learning rate và số epoch trên 20% S (ridge học trên 80%), rồi học lại residual trên toàn S với
    ridge Wr_all, đúng learning rate và số epoch đã chọn. Không lr nào hơn ridge thì MLP = ridge."""
    rng = np.random.RandomState(a.seed + 23)
    idx = rng.permutation(len(E1s))
    cut = max(1, int(0.8 * len(idx)))
    tr, va = idx[:cut], idx[cut:]
    W_tr, _, _ = q3.fit_ridge_cv(E1s[tr], E0s[tr], a.seed, LAMS)
    lrs = [float(x) for x in str(a.mlp_lrs).split(",")]
    grid = {}
    for lr in lrs:
        _, inf = train_residual_mlp(E1s[tr], E0s[tr], W_tr, a.mlp_hidden, a.mlp_epochs, lr, a.mlp_wd,
                                    a.mlp_batch, a.seed, E1s[va], E0s[va], a.mlp_patience)
        grid[f"{lr:g}"] = inf
    best_lr = min(lrs, key=lambda lr: grid[f"{lr:g}"]["val_angle"])
    info = dict(grid[f"{best_lr:g}"])
    info["lr"] = best_lr
    info["grid"] = {k: dict(best_epoch=v["best_epoch"], val_angle=v["val_angle"], epochs_run=v["epochs_run"])
                    for k, v in grid.items()}
    E = info["best_epoch"]
    if E == 0:
        Pm = [np.zeros((E1s.shape[1], a.mlp_hidden), np.float32), np.zeros(a.mlp_hidden, np.float32),
              np.zeros((a.mlp_hidden, E0s.shape[1]), np.float32), np.zeros(E0s.shape[1], np.float32)]
    else:
        Pm, _ = train_residual_mlp(E1s, E0s, Wr_all, a.mlp_hidden, E, best_lr, a.mlp_wd, a.mlp_batch, a.seed)
    info["train_angle_ridge"] = _mean_angle(E1s @ Wr_all, E0s)
    info["train_angle_mlp"] = _mean_angle(mlp_apply(E1s, Wr_all, Pm), E0s)
    return Pm, info


# ----------------------------------------------------------------- main
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
    ap.add_argument("--frac", type=float, default=0.10)
    ap.add_argument("--holdout", type=int, default=1)
    ap.add_argument("--mlp", type=int, default=1)
    ap.add_argument("--mlp-hidden", type=int, default=256)
    ap.add_argument("--mlp-epochs", type=int, default=200)
    ap.add_argument("--mlp-lrs", default="1e-3", help="lưới learning rate, chọn theo góc trên 20%% S")
    ap.add_argument("--mlp-wd", type=float, default=1e-4)
    ap.add_argument("--mlp-batch", type=int, default=128)
    ap.add_argument("--mlp-patience", type=int, default=15)
    ap.add_argument("--rerank", default="5,10,15,20,30,50,100")
    ap.add_argument("--pair-src", default="exact", choices=["exact", "pq"],
                    help="vế M0 của cặp học adapter: exact = embedding M0 đầy đủ (đợt 4), pq = bản tái tạo PQ của record E0")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    t0 = time.time()
    D, ds = a.data_dir, a.dataset
    Rs = [int(x) for x in a.rerank.split(",")]

    E0 = np.load(f"{D}/{ds}_corpus_embeddings.npy").astype(np.float32)
    Q0 = np.load(f"{D}/{ds}_query_embeddings.npy").astype(np.float32)
    cb0 = np.load(f"{D}/{ds}_pq_codebook_m512.npy").astype(np.float32)
    cd0 = np.load(f"{D}/{ds}_pq_codes_m512.npy")
    E1 = np.load(f"{D}/{ds}_{a.tag}_corpus_embeddings.npy").astype(np.float32)
    Q1 = np.load(f"{D}/{ds}_{a.tag}_query_embeddings.npy").astype(np.float32)
    gt1 = json.load(open(f"{D}/{ds}_{a.tag}_ground_truth.json"))
    N, d0 = E0.shape; d1 = E1.shape[1]; NQall = len(gt1)
    ev, trq = np.arange(a.nq), np.arange(a.nq, NQall)
    gt5_json = [np.array([int(r["index"]) for r in g["top_5_results"][:5]]) for g in gt1]

    rnd = random.Random(a.seed)
    nid = np.array([rnd.getrandbits(63) for _ in range(a.nodes)], dtype=np.int64)
    P0 = pb.gen_proj(a.seed, d0, a.tables)
    perm = np.random.RandomState(a.seed).permutation(N)
    S = perm[:max(a.tables * 20, int(round(a.frac * N)))]
    log("=" * 78)
    log(f"[03c] dataset={ds} tag={a.tag} seed={a.seed}  N={N}  mẫu S={len(S)} ({a.frac:.1%})  "
        f"holdout={a.holdout}  mlp={a.mlp}  cặp học: {a.pair_src}")

    # ground truth tính lại trên toàn corpus phải trùng file
    def top5(Qm, Em):
        out = []
        for s in range(0, len(Qm), 64):
            sim = l2norm(Qm[s:s + 64]) @ Em.T
            idx = np.argpartition(-sim, 5, axis=1)[:, :5]
            out.extend(idx[r][np.argsort(-sim[r, idx[r]])] for r in range(len(idx)))
        return out
    gt_full = top5(Q1, E1)
    agree = float(np.mean([set(x.tolist()) == set(y.tolist()) for x, y in zip(gt_full, gt5_json)]))
    log(f"ground truth tính lại trên toàn corpus trùng file: {100 * agree:.1f}% query"
        + ("" if agree >= 0.99 else "   <-- THẤP, kiểm tra lại định nghĩa ground truth"))

    # ánh xạ học trên S (y hệt 03b); đợt 5: vế M0 có thể là bản tái tạo PQ
    if a.pair_src == "exact":
        X0S = E0[S]
    else:
        X0S = cb0[np.arange(cb0.shape[0])[None, :], cd0[S]].reshape(len(S), d0).astype(np.float32)
    pcos = (E0[S] * X0S).sum(1) / np.linalg.norm(E0[S], axis=1) / np.linalg.norm(X0S, axis=1)
    pair_info = dict(src=a.pair_src, cos_mean_S=float(pcos.mean()), cos_min_S=float(pcos.min()))
    Wr, lam_dr, _ = q3.fit_ridge_cv(E1[S], X0S, a.seed, LAMS)
    Wf, lam_f = pb.fit_bridge(X0S, E1[S], "ridge", a.seed)
    WfT = np.ascontiguousarray(Wf.T)
    mlp_info = None
    if a.mlp:
        tm = time.time()
        Pm, mlp_info = fit_mlp_adapter(E1[S], X0S, Wr, a)
        log("MLP lưới lr: " + "  ".join(f"lr={k}: epoch {v['best_epoch']}/{v['epochs_run']} góc {v['val_angle']:.2f}°"
                                        for k, v in mlp_info["grid"].items()))
        log(f"MLP: lr chọn {mlp_info['lr']:g}, epoch tốt nhất {mlp_info['best_epoch']} (chạy {mlp_info['epochs_run']}); góc validation "
            f"ridge {mlp_info['ridge_val_angle']:.2f}° -> MLP {mlp_info['val_angle']:.2f}°; góc trên S "
            f"ridge {mlp_info['train_angle_ridge']:.2f}° -> MLP {mlp_info['train_angle_mlp']:.2f}°  ({time.time() - tm:.0f}s)")

    # chỉ mục E0 (bỏ S nếu holdout)
    if a.holdout:
        keep = np.setdiff1d(np.arange(N), S)
        E0k, cd0k, E1k = E0[keep], cd0[keep], E1[keep]
        gt5_all = top5(Q1, E1k)
    else:
        keep = np.arange(N)
        E0k, cd0k, E1k = E0, cd0, E1
        gt5_all = gt5_json
    Nk = len(keep)
    gt5 = [gt5_all[i] for i in ev]
    anchors0 = pb.build_index(E0k, P0, nid)
    load0 = np.bincount(anchors0.ravel(), minlength=a.nodes)
    m0 = cb0.shape[0]
    C0 = cb0[np.arange(m0)[None, :], cd0k].reshape(Nk, d0).astype(np.float32)
    div_pq = np.linalg.norm(C0 @ Wf, axis=1)
    div_ex = np.linalg.norm(E0k @ Wf, axis=1)
    common = dict(anchors=anchors0, P_list=P0, codes=cd0k, cb=cb0, nid=nid, gt5=gt5,
                  K=a.k_query, T=a.probes, cbits=a.cbits, load=load0,
                  kappa=a.kappa, rerank_vecs=E1k, rerank_q=Q1[ev], Rs=Rs, exact_vecs=E0k)
    log(f"chỉ mục E0: {Nk} record  ({time.time() - t0:.0f}s)")

    results = []

    def show(r):
        rr = "  ".join(f"R{R}={r['rerank'][str(R)]:5.1f}" for R in Rs)
        log(f"  {r['name']:18s} reach={r['reach_r5']:5.1f} final={r['final_r5']:5.1f} | {rr} | "
            f"nodes={r['nodes']:.0f} cand={r['cand']:.0f} moved={r['moved']:.0f}")

    def arm(name, route, rank=None):
        r = q3.retrieve(route, rank_qv=rank, **common)
        r.update(name=name, nn_overlap=q3.nn_overlap(route if rank is None else rank, E0k, gt5))
        results.append(r); show(r)

    def arm_norm(name, route):
        r = p3b.retrieve_norm(route, l2norm(Q1[ev] @ WfT), div_pq, div_exact=div_ex, **common)
        r.update(name=name); results.append(r); show(r)

    qmlp = l2norm(mlp_apply(Q1, Wr, Pm)) if a.mlp else None
    log("")
    arm("dual_encode", Q0[ev])
    arm("A_doc_ridge", l2norm(Q1[ev] @ Wr))
    arm_norm("A_split_norm", l2norm(Q1[ev] @ Wr))
    if a.mlp:
        arm("A_mlp", qmlp[ev])
        arm_norm("A_mlp_split_norm", qmlp[ev])

    # ---------------- tự kiểm với gate 3d
    checks = {}
    pre = "" if ds == "code" else f"{ds}_"
    f3d = f"probeE_{pre}{a.tag}_s{a.seed}.json"
    if a.pair_src == "exact" and not a.holdout and os.path.exists(f3d) and abs(json.load(open(f3d))["argv"]["frac"] - a.frac) < 1e-9:
        old = {r["name"]: r for r in json.load(open(f3d))["results"]}
        bad, n = 0, 0
        for r in results:
            o = old.get(r["name"])
            if o is None:
                continue
            for k in ("reach_r5", "final_r5", "final_ip", "final_exact", "nn_overlap", "nodes", "cand", "moved"):
                n += 1; bad += abs(o[k] - r[k]) > 1e-9
            for R in r["rerank"]:
                if R in o["rerank"]:
                    n += 1; bad += abs(o["rerank"][R] - r["rerank"][R]) > 1e-9
        checks["gate3d"] = dict(n=n, bad=int(bad))
        log(f"\n  >>> dual_encode / A_doc_ridge / A_split_norm so với gate 3d ({f3d}): {n} giá trị, "
            f"{'KHỚP' if bad == 0 else f'{bad} LỆCH'}")

    # ---------------- chọn trên validation
    vR = 20
    vcommon = dict(common, gt5=[gt5_all[i] for i in trq], rerank_q=Q1[trq], Rs=[vR], exact_vecs=None)
    log(f"\n--- CHỌN TRÊN VALIDATION ({len(trq)} query, rerank@{vR}) ---")
    vd = q3.retrieve(Q0[trq], **vcommon)
    val = {}
    cand = [("A_doc_ridge", l2norm(Q1[trq] @ Wr), False), ("A_split_norm", l2norm(Q1[trq] @ Wr), True)]
    if a.mlp:
        cand += [("A_mlp", qmlp[trq], False), ("A_mlp_split_norm", qmlp[trq], True)]
    for nm, qr, norm in cand:
        rv = (p3b.retrieve_norm(qr, l2norm(Q1[trq] @ WfT), div_pq, **vcommon) if norm
              else q3.retrieve(qr, **vcommon))
        val[nm] = dict(reach=rv["reach_r5"], final=rv["final_r5"], rerank=rv["rerank"][str(vR)])
        log(f"  {nm:18s} val final={val[nm]['final']:5.1f} R{vR}={val[nm]['rerank']:5.1f}")
    log(f"  {'dual_encode':18s} val final={vd['final_r5']:5.1f} R{vR}={vd['rerank'][str(vR)]:5.1f}")
    sel = max(val, key=lambda k: val[k]["rerank"])
    log(f"  -> chọn {sel}")
    diag = dict(val=dict(R=vR, n=int(len(trq)), selected=sel, arms=val,
                         dual=dict(reach=vd["reach_r5"], final=vd["final_r5"], rerank=vd["rerank"][str(vR)])),
                lam_r=lam_dr, lam_f=lam_f, mlp=mlp_info, gt_agree=agree, n_index=int(Nk))

    de = results[0]
    log("\nchênh so với dual (final | rerank R10 R20 R50):")
    for r in results[1:]:
        log(f"  {r['name']:18s} {r['final_r5'] - de['final_r5']:+5.1f} | " + " ".join(
            f"{r['rerank'][str(R)] - de['rerank'][str(R)]:+5.1f}" for R in (10, 20, 50) if str(R) in r["rerank"]))

    sfx = "" if a.pair_src == "exact" else "_pq"
    fex = f"probeH_{pre}{a.tag}_s{a.seed}_f{a.frac:g}_ho{a.holdout}.json"
    if a.pair_src != "exact" and os.path.exists(fex):
        ex = json.load(open(fex))
        o = {r["name"]: r for r in ex["results"]}.get("dual_encode")
        r = results[0]
        if o is not None and ex["argv"]["nodes"] == a.nodes and ex["argv"]["nq"] == a.nq:
            n, bad = 0, 0
            for k in ("reach_r5", "final_r5", "nodes", "cand", "moved"):
                n += 1; bad += abs(o[k] - r[k]) > 1e-9
            for R in r["rerank"]:
                if R in o["rerank"]:
                    n += 1; bad += abs(o["rerank"][R] - r["rerank"][R]) > 1e-9
            checks["dual_vs_exact"] = dict(file=fex, n=n, bad=int(bad))
            log(f"  >>> dual_encode so với bản exact ({fex}): {n} giá trị, {'KHỚP' if bad == 0 else f'{bad} LỆCH'}")
    out = a.out or f"probeH_{pre}{a.tag}_s{a.seed}_f{a.frac:g}_ho{a.holdout}{sfx}.json"
    json.dump(dict(argv=vars(a), d0=d0, d1=d1, n_sample_doc=int(len(S)), pair=pair_info, diag=diag, checks=checks,
                   results=results), open(out, "w"), indent=1)
    log(f"\n-> {out}   ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
