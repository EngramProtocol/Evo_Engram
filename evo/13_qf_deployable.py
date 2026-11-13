#!/usr/bin/env python3
"""
13_qf_deployable.py  —  đợt 13, theo nhận xét của thầy về C1 (Mục 4.3, "Estimation and assumptions").

Bộ ước lượng của đợt 8 đến 12 (`coll_pred_exact_u`, `qfrac_pred_u` trong probeA*) dùng embedding M1 của TOÀN corpus và 300
query ĐÁNH GIÁ: p lấy từ 200.000 cặp document ngẫu nhiên trên toàn corpus, qf từ 300 query đánh giá với toàn corpus. Người vận
hành không có những thứ đó khi mới nhúng lại mẫu S. Script này tính lại p và qf bằng bộ ước lượng triển khai được, chỉ dùng
mẫu S và 200 query validation, cho một file probeA đã có (đợt 11 hoặc 12). Không dựng index, không chạy lại mô phỏng: chỉ đọc
embedding.

S, tách query (300 query đánh giá đầu, phần còn lại là validation), chuẩn hoá và trừ tâm giống hệt 10_probe_placement.py:
perm = RandomState(seed).permutation(N), nS = max(tables_ref · 20, round(frac · N)), S = perm[:nS], mu_d = trung bình E[S].

Tính và ghi (u: khoá gốc, không trừ tâm; c: document trừ mu_d, query chuẩn hoá rồi trừ mu_d, như 10_probe_placement.py):
  full     dựng lại đúng bộ ước lượng cũ (cùng bộ sinh số ngẫu nhiên) để tự kiểm: p_u, p_c, qf_ev_u, qf_ev_c phải trùng số
           trong file probeA (lệch tương đối quá 1e-6 thì in LỆCH);
  deploy   p_S_u, p_S_c: trung bình (1 − θ/π)^16 trên MỌI cặp document khác nhau trong S (đủ cặp, không lấy mẫu);
           qf_S_val_u, qf_S_val_c: trung bình (1 − θ/π)^16 giữa query validation và document trong S;
           cbar_S, pmf_S_u: cosine trung bình giữa các document trong S và dự đoán trường trung bình (1 − arccos(cbar)/π)^16;
  decomp   qf_S_ev_u (query đánh giá với S) và qf_full_val_u (query validation với toàn corpus), để tách phần lệch do mẫu
           document và phần do tập query;
  measured chép các số đo thật từ file probeA (coll_meas_u, qfrac_meas_u, coll_meas_c, qfrac_meas_c).

CHẠY (ở thư mục gốc repo):
  python3 evo/13_qf_deployable.py probeA12_code_bgebase_s36.json            # ra probeQ13_A12_code_bgebase_s36.json
  python3 evo/13_qf_deployable.py probeA11_code100kfq_m0_s26.json           # ra probeQ13_A11_code100kfq_m0_s26.json
"""
import argparse, json, os, sys, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import me_common as mc                                     # noqa: E402

l2norm, log = mc.l2norm, mc.log
K16 = 16


def bucket_prob(c):
    """Xác suất hai vector có cosine c trùng 16 bit dấu dưới siêu phẳng Gauss độc lập: (1 − θ/π)^16."""
    return (1.0 - np.arccos(np.clip(c, -1.0, 1.0)) / np.pi) ** K16


def q_pred(Qn, X):
    """Như q_pred của 10_probe_placement.py: trung bình theo query của trung bình theo document."""
    v = []
    for i in range(0, len(Qn), 50):
        v.append(bucket_prob(Qn[i:i + 50] @ X.T).mean(1))
    return float(np.concatenate(v).mean()) if v else float("nan")


def all_pairs(X, block=1024):
    """Trung bình (1 − θ/π)^16 và trung bình cosine trên mọi cặp i < j của các hàng X (đủ cặp, không lấy mẫu)."""
    n = len(X)
    tot = cos_tot = 0.0
    for i0 in range(0, n, block):
        G = X[i0:i0 + block] @ X.T                             # các hàng i0 .. i0 + block với mọi hàng
        rows = np.arange(i0, min(n, i0 + block))[:, None]
        upper = np.arange(n)[None, :] > rows                    # chỉ cặp i < j
        c = G[upper].astype(np.float64)
        tot += float(bucket_prob(c).sum()); cos_tot += float(c.sum())
    npairs = n * (n - 1) / 2.0
    return tot / npairs, cos_tot / npairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("probeA", help="file probeA*_<ds>_<space>_s<seed>.json của đợt 11 hoặc 12")
    ap.add_argument("--data-dir", default=None, help="mặc định: data_dir ghi trong argv của file probeA")
    ap.add_argument("--out", default=None, help="mặc định: probeQ13_A<đợt>_<ds>_<space>_s<seed>.json")
    o = ap.parse_args()
    t0 = time.time()
    src = json.load(open(o.probeA))
    a = src["argv"]
    D = o.data_dir or a["data_dir"]
    ds, seed = a["dataset"], int(a["seed"])
    tag = a["tag"] if a["space"] == "m1" else "m0"
    if a["space"] == "m1":
        E = np.load(f"{D}/{ds}_{a['tag']}_corpus_embeddings.npy").astype(np.float32)
        Qall = np.load(f"{D}/{ds}_{a['tag']}_query_embeddings.npy").astype(np.float32)
        gt = json.load(open(f"{D}/{ds}_{a['tag']}_ground_truth.json"))
    else:
        E = np.load(f"{D}/{ds}_corpus_embeddings.npy").astype(np.float32)
        Qall = np.load(f"{D}/{ds}_query_embeddings.npy").astype(np.float32)
        gt = json.load(open(f"{D}/{ds}_ground_truth.json"))
    N, d = E.shape; NQall = len(gt)
    ev, trq = np.arange(a["nq"]), np.arange(a["nq"], NQall)
    perm = np.random.RandomState(seed).permutation(N)
    nS = max(a["tables_ref"] * 20, int(round(a["frac"] * N)))
    S = perm[:nS]
    mu_d = E[S].mean(0).astype(np.float32)
    if N != src.get("N") or nS != src.get("nS"):
        log(f"LỆCH: N, nS = {N}, {nS} nhưng file probeA ghi {src.get('N')}, {src.get('nS')}")
    log(f"[13q] {ds} {tag} seed={seed} N={N} d={d} nS={nS} query đánh giá {len(ev)}, validation {len(trq)}")

    # ---------- dựng lại bộ ước lượng cũ, cùng thứ tự rút số ngẫu nhiên như 10_probe_placement.py (--aniso-only)
    En = l2norm(E)
    Ec = l2norm(E - mu_d)
    rs2 = np.random.RandomState(seed + 11)

    def pair_pred(X):
        tot, cnt = 0.0, 0
        left = a["aniso_pairs"]
        while left > 0:
            m = min(20000, left); left -= m
            j1, j2 = rs2.randint(N, size=m), rs2.randint(N, size=m)
            ok = j1 != j2
            c = np.clip((X[j1[ok]] * X[j2[ok]]).sum(1), -1.0, 1.0)
            tot += float(((1.0 - np.arccos(c) / np.pi) ** K16).sum()); cnt += int(ok.sum())
        return tot / cnt

    qn = l2norm(Qall[ev])
    qc = l2norm(qn - mu_d)
    full = dict(p_u=pair_pred(En), p_c=pair_pred(Ec), qf_ev_u=q_pred(qn, En), qf_ev_c=q_pred(qc, Ec))
    ext = src.get("ext", {})
    old = dict(p_u="coll_pred_exact_u", p_c="coll_pred_exact_c", qf_ev_u="qfrac_pred_u", qf_ev_c="qfrac_pred_c")
    check, bad = {}, 0
    for k, ko in old.items():
        if ko in ext:
            rel = abs(full[k] - ext[ko]) / max(1e-300, abs(ext[ko]))
            check[k] = dict(new=full[k], old=ext[ko], rel=rel)
            if rel > 1e-6:
                bad += 1
                log(f"   LỆCH {k}: dựng lại {full[k]:.6e}, file probeA {ext[ko]:.6e} (tương đối {rel:.2e})")
    log(f"   tự kiểm bộ ước lượng cũ: {len(check) - bad}/{len(check)} số trùng" + ("" if bad else " (đúng từng số)"))

    # ---------- bộ ước lượng triển khai được: chỉ mẫu S và query validation
    XS, XSc = En[S], Ec[S]
    p_S_u, cbar_S = all_pairs(XS)
    p_S_c, _ = all_pairs(XSc)
    qv = l2norm(Qall[trq]) if len(trq) else np.zeros((0, d), np.float32)
    qvc = l2norm(qv - mu_d) if len(trq) else qv
    deploy = dict(p_S_u=p_S_u, p_S_c=p_S_c, qf_S_val_u=q_pred(qv, XS), qf_S_val_c=q_pred(qvc, XSc), cbar_S=cbar_S,
                  pmf_S_u=float((1.0 - np.arccos(np.clip(cbar_S, -1.0, 1.0)) / np.pi) ** K16), n_pairs_S=nS * (nS - 1) // 2)
    decomp = dict(qf_S_ev_u=q_pred(qn, XS), qf_full_val_u=q_pred(qv, En))
    measured = {k: ext[k] for k in ("coll_meas_u", "qfrac_meas_u", "coll_meas_c", "qfrac_meas_c") if k in ext}
    log("   cũ (toàn corpus, query đánh giá):  p = %.3e  qf = %.3e" % (full["p_u"], full["qf_ev_u"]))
    log("   mới (S, query validation):         p = %.3e  qf = %.3e   (cbar_S = %.3f)" %
        (deploy["p_S_u"], deploy["qf_S_val_u"], cbar_S))
    log("   tách: qf query đánh giá với S = %.3e, query validation với toàn corpus = %.3e" %
        (decomp["qf_S_ev_u"], decomp["qf_full_val_u"]))
    if measured:
        log("   đo thật:                           p = %.3e  qf = %.3e" %
            (measured.get("coll_meas_u", float("nan")), measured.get("qfrac_meas_u", float("nan"))))
    out = dict(src=os.path.basename(o.probeA), dataset=ds, space=tag, seed=seed, N=int(N), nS=int(nS), n_ev=int(len(ev)),
               n_val=int(len(trq)), check=check, check_bad=bad, full=full, deploy=deploy, decomp=decomp, measured=measured,
               numpy=np.__version__, sec=round(time.time() - t0, 1))
    b = os.path.basename(o.probeA)
    fo = o.out or f"probeQ13_{b.split('_', 1)[0][len('probe'):]}_{b.split('_', 1)[1]}"
    json.dump(out, open(fo, "w"), indent=1)
    log(f"   ghi {fo} ({out['sec']}s)")


if __name__ == "__main__":
    main()
