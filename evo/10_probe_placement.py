#!/usr/bin/env python3
"""
10_probe_placement.py  —  ĐỢT 7 (thăm dò, chưa đăng ký trước). Chỉ mục native một epoch dưới các cách
đặt record (placement) khác nhau, quét ngân sách tra cứu, đo tải theo peer.

Câu hỏi:
  (1) Độ lệch tải của SRP có đi theo độ dị hướng (anisotropy) của embedding như mô hình
      a = c / (1 - c), p_bit = Phi(Z sqrt(a)) dự đoán không (c = cosine trung bình giữa hai document)?
  (2) Ở cùng chi phí (ứng viên phải chấm, peer phải hỏi), placement học trên mẫu S (re-indexer vốn phải
      đặt lại record khi migrate) có cho recall native cao hơn SRP ngẫu nhiên, và hết điểm nóng không?

Biến thể placement (mỗi bảng: W_l (d x 63), ngưỡng t_l, tâm của document và của query):
  srp     SRP Achlioptas như bài (ma trận của gen_proj, ngưỡng 0, không trừ tâm). L=5, T=8 trùng E1ONLY của 04b.
  srp_c   như srp, document và query trừ trung bình document trên S. Trùng E1ONLY_c của 04b.
  srp_cq  như srp_c nhưng query trừ trung bình query validation. Trùng E1ONLY_cq của 04b.
  pca_q   trừ tâm, chiếu lên k thành phần chính của S, quay ngẫu nhiên trực giao mỗi bảng, ngưỡng trung vị
          trên S (mỗi bit chia đôi S); query trừ trung bình query.
  itq_d   ITQ (Gong và Lazebnik) trên 63 thành phần chính, mỗi bảng khởi tạo ngẫu nhiên và hoán vị bit
          riêng, ngưỡng trung vị trên S; query trừ trung bình document.
  itq_q   như itq_d, query trừ trung bình query.
  itq<k>_q, itq<k>_d (đợt 9, thăm dò điểm nóng của ITQ): ITQ trên k thành phần chính (k >= 63) rồi giữ 63 trong k bit.
--check-prev FILE (đợt 9): so mọi số của các biến thể có trong cả FILE và lượt này (mọi L, T và tải), để chắc biến thể cũ
không đổi khi chạy lại cùng seed.
Ngân sách: L bảng trong --Ls (mặc định 5,10; bảng đầu của L lớn trùng L nhỏ), T probe mỗi bảng trong --Ts
(khoá gốc + T-1 lần lật một bit biên nhỏ nhất trong cbits bit đầu, như 04b; T <= cbits + 1), K peer XOR-gần
nhất mỗi khoá, mỗi peer trả top-kappa.
Chấm điểm: ADC trên codebook E1 học trên S (như 04b); rerank@20 cosine M1 thật cho cả 20 ứng viên
(quy ước trạng thái cố định của 04b). Ứng viên = record còn hoạt động ở các peer được hỏi.

Đo cho mỗi (biến thể, L, T): reach@5, final R@5, rerank@20, số ứng viên, số peer hỏi; nếu GT của M0 có
source_corpus_index (code100kfq): tỉ lệ hàm gốc của query nằm trong top-5 trước và sau rerank; tải lưu trữ (max,
p99, rỗng, phần của 1% peer tải cao nhất, Gini); tải truy vấn (tỉ lệ query chạm peer nóng nhất, phần
lượt hỏi của 1% peer nhận nhiều nhất); công việc ADC theo peer (record x lượt hỏi). Cho mỗi biến thể:
độ cân bằng bit, số bucket hiệu dụng của tiền tố 16 bit, xác suất query và hàng xóm GT cùng tiền tố.

--space m1 (mặc định): không gian M1 của --tag. --space m0: không gian M0 (E0, query M0, GT của M0, PQ m512
có sẵn) để đo index legacy; tag ghi là m0.

Tự kiểm: với probeG_<pre><tag>_s<seed>.json ở thư mục hiện tại, srp/srp_c/srp_cq ở L=5, T=8 phải trùng
E1ONLY/E1ONLY_c/E1ONLY_cq ở f = 1 (reach, final, rerank@20, ứng viên, số peer).

CHẠY: python3 evo/10_probe_placement.py --tag e5large --dataset code100kfq --seed 3 --nodes 50000 --frac 0.02
"""
import argparse, json, os, random, re, time
import numpy as np
import me_common as mc

np.seterr(invalid='ignore', divide='ignore')
pb = mc.pb
log, l2norm = mc.log, mc.l2norm


# ----------------------------------------------------------------- tiện ích
def gini(x):
    x = np.sort(np.asarray(x, dtype=np.float64))
    n = len(x)
    if n == 0 or x.sum() <= 0:
        return 0.0
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


def share_top(x, frac=0.01):
    x = np.sort(np.asarray(x, dtype=np.float64))[::-1]
    k = max(1, int(len(x) * frac))
    return float(x[:k].sum() / max(x.sum(), 1e-12))


def pack(bits):
    """(n, >=63) bool -> khoá 63 bit (giống pb.pack63)."""
    return pb.pack63(bits)


def ncdf(z):
    from math import erf, sqrt
    return 0.5 * (1.0 + np.vectorize(erf)(np.asarray(z) / sqrt(2.0)))


def rand_orth(rng, n, k):
    A = rng.standard_normal((n, k))
    Qm, Rm = np.linalg.qr(A)
    return (Qm * np.sign(np.diag(Rm))[None, :]).astype(np.float32)


def itq(V, iters, rng):
    """ITQ: R trực giao (c x c) cực tiểu ||sign(VR) - VR||_F."""
    c = V.shape[1]
    R = rand_orth(rng, c, c).astype(np.float64)
    V = V.astype(np.float64)
    for _ in range(iters):
        B = np.sign(V @ R); B[B == 0] = 1
        U, _, Wt = np.linalg.svd(V.T @ B)
        R = U @ Wt
    return R.astype(np.float32)


# ----------------------------------------------------------------- biến thể placement
def make_variant(name, Xs, Lmax, seed, P_rand, mu_d, mu_q, k_pca, itq_iters):
    """-> dict(W=[d x 63], t=[63], cd=tâm document, cq=tâm query)."""
    d = Xs.shape[1]
    z = np.zeros(d, dtype=np.float32)
    if name in ("srp", "srp_c", "srp_cq"):
        # giữ đủ 160 cột như build_index của 04b (pack63 lấy 63 cột đầu) để phép nhân trùng từng bit
        t0 = [np.zeros(P.shape[1], np.float32) for P in P_rand]
        c = {"srp": (z, z), "srp_c": (mu_d, mu_d), "srp_cq": (mu_d, mu_q)}[name]
        return dict(W=list(P_rand), t=t0, cd=c[0], cq=c[1])
    Xc = (Xs - mu_d).astype(np.float32)
    _, _, Vt = np.linalg.svd(Xc, full_matrices=False)
    rng = np.random.RandomState(seed + 101)
    Ws = []
    if name.startswith("pca"):
        U = Vt[:max(63, min(k_pca, Vt.shape[0]))].T.astype(np.float32)  # d x k, k >= 63
        for _ in range(Lmax):
            Ws.append(U @ rand_orth(rng, U.shape[1], 63))
    elif name.startswith("itq"):
        # itq_d, itq_q: ITQ trên 63 thành phần chính. itq<k>_d, itq<k>_q (đợt 9): ITQ trên k thành phần chính, giữ 63
        # trong k bit theo hoán vị ngẫu nhiên của bảng. Với k = 63 dãy số ngẫu nhiên dùng y hệt bản cũ.
        mk = re.match(r"itq(\d+)_", name)
        kk = 63 if mk is None else max(63, min(int(mk.group(1)), Vt.shape[0]))
        U = Vt[:kk].T.astype(np.float32)                                 # d x k
        V = Xc @ U
        for _ in range(Lmax):
            R = itq(V, itq_iters, rng)
            Ws.append((U @ R)[:, rng.permutation(kk)[:63]])
    else:
        raise ValueError(name)
    ts = [np.median(Xc @ W, axis=0).astype(np.float32) for W in Ws]
    return dict(W=Ws, t=ts, cd=mu_d, cq=(mu_q if name.endswith("_q") else mu_d))


def doc_bits(X, W, t, c):
    return ((X - c) @ W) > t


def probe_keys(Qv, W_list, t_list, c, T, cbits):
    """[L][Q, T] khoá; như pb.probe_keys_for nhưng có tâm và ngưỡng (biên = |chiếu - ngưỡng|)."""
    out = []
    for W, t in zip(W_list, t_list):
        PR = (Qv - c) @ W - t
        base = pack(PR > 0)
        weak = np.argsort(np.abs(PR[:, :cbits]), axis=1)[:, :T - 1]
        ks = np.empty((len(Qv), T), dtype=np.int64)
        ks[:, 0] = base
        for j in range(T - 1):
            ks[:, j + 1] = base ^ (np.int64(1) << (62 - weak[:, j]).astype(np.int64))
        out.append(ks)
    return out


def prefix16(bits):
    k = np.zeros(bits.shape[0], dtype=np.int64)
    for j in range(16):
        k = (k << np.int64(1)) | bits[:, j].astype(np.int64)
    return k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="M1 (bgebase, e5large, arctic); bỏ qua khi --space m0")
    ap.add_argument("--space", default="m1", choices=["m1", "m0"])
    ap.add_argument("--dataset", default="code100kfq")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--nodes", type=int, default=50000)
    ap.add_argument("--nq", type=int, default=300)
    ap.add_argument("--k-query", type=int, default=20)
    ap.add_argument("--cbits", type=int, default=16)
    ap.add_argument("--dsub", type=int, default=2)
    ap.add_argument("--kappa", type=int, default=30)
    ap.add_argument("--frac", type=float, default=0.02, help="mẫu S, chọn giống 04b")
    ap.add_argument("--tables-ref", type=int, default=5, help="số bảng của 04b, chỉ để chọn S giống 04b")
    ap.add_argument("--variants", default="srp,srp_c,srp_cq,pca_q,itq_d,itq_q")
    ap.add_argument("--Ls", default="5,10")
    ap.add_argument("--Ts", default="2,4,8,16")
    ap.add_argument("--k-pca", type=int, default=128)
    ap.add_argument("--itq-iters", type=int, default=50)
    ap.add_argument("--pairs", type=int, default=5000, help="số cặp document ngẫu nhiên để đo cosine trung bình")
    ap.add_argument("--aniso-only", type=int, default=0,
                    help="1: chỉ đo độ dị hướng, xác suất trùng bucket 16 bit dự đoán (trường trung bình và công thức góc "
                         "chính xác) và đo thật, rồi ghi probeA_*.json; không dựng index, không chấm điểm")
    ap.add_argument("--aniso-pairs", type=int, default=200000, help="số cặp document cho công thức góc ở --aniso-only")
    ap.add_argument("--check-prev", default="none", help="probeP cũ cùng seed để so từng số các biến thể trùng tên")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    t0 = time.time()
    D, ds = a.data_dir, a.dataset
    Ls = sorted(int(x) for x in a.Ls.split(",")); Lmax = Ls[-1]
    Ts = sorted(int(x) for x in a.Ts.split(",")); Tmax = Ts[-1]
    assert Tmax <= a.cbits + 1, "T phải <= cbits + 1 (mỗi probe lật đúng một bit)"
    variants = a.variants.split(",")
    tag = a.tag if a.space == "m1" else "m0"

    if a.space == "m1":
        E = np.load(f"{D}/{ds}_{a.tag}_corpus_embeddings.npy").astype(np.float32)
        Qall = np.load(f"{D}/{ds}_{a.tag}_query_embeddings.npy").astype(np.float32)
        gt = json.load(open(f"{D}/{ds}_{a.tag}_ground_truth.json"))
    else:
        E = np.load(f"{D}/{ds}_corpus_embeddings.npy").astype(np.float32)
        Qall = np.load(f"{D}/{ds}_query_embeddings.npy").astype(np.float32)
        gt = json.load(open(f"{D}/{ds}_ground_truth.json"))
    N, d = E.shape; NQall = len(gt)
    ev, trq = np.arange(a.nq), np.arange(a.nq, NQall)
    gt5 = [np.array([int(r["index"]) for r in g["top_5_results"][:5]]) for g in gt]
    # nhãn liên quan theo tác vụ (nếu có): hàm gốc mà query được viết từ đó, lưu trong GT của M0 (07_assemble_data)
    gold = None
    fgold = f"{D}/{ds}_ground_truth.json"
    if os.path.exists(fgold):
        g0 = json.load(open(fgold))
        if len(g0) >= a.nq and all("source_corpus_index" in g0[i] for i in range(a.nq)):
            gold = np.array([int(g0[i]["source_corpus_index"]) for i in range(a.nq)], dtype=np.int64)

    rnd = random.Random(a.seed)
    nid = np.array([rnd.getrandbits(63) for _ in range(a.nodes)], dtype=np.int64)
    P_rand = pb.gen_proj(a.seed, d, Lmax)
    perm = np.random.RandomState(a.seed).permutation(N)
    nS = max(a.tables_ref * 20, int(round(a.frac * N)))
    S = perm[:nS]
    mu_d = E[S].mean(0).astype(np.float32)
    mu_q = Qall[trq].mean(0).astype(np.float32) if len(trq) else mu_d
    log("=" * 78)
    log(f"[10] dataset={ds} space={a.space} tag={tag} seed={a.seed} N={N} d={d} nodes={a.nodes} S={nS} "
        f"Ls={Ls} Ts={Ts} K={a.k_query} kappa={a.kappa} biến thể={variants}  (numpy {np.__version__})")

    # ---------------- độ dị hướng và dự đoán của mô hình bit lệch
    rs = np.random.RandomState(a.seed + 7)
    i1, i2 = rs.randint(N, size=a.pairs), rs.randint(N, size=a.pairs)
    En = l2norm(E)
    cbar = float(np.mean((En[i1] * En[i2]).sum(1)[i1 != i2]))
    an = cbar / max(1e-6, 1.0 - cbar)
    Z = rs.standard_normal(20000)
    pz = ncdf(Z * np.sqrt(max(an, 0.0)))
    col_pred = float(np.mean(pz ** 2 + (1 - pz) ** 2))
    aniso = dict(mu_d_norm=float(np.linalg.norm(mu_d)), mu_q_norm=float(np.linalg.norm(mu_q)),
                 cos_mu=float(mu_d @ mu_q / max(1e-9, np.linalg.norm(mu_d) * np.linalg.norm(mu_q))),
                 mean_pair_cos=cbar, a=an, bit_collision_pred=col_pred,
                 eff_buckets16_pred=float(col_pred ** -16))
    log(f"dị hướng: |mu_d|={aniso['mu_d_norm']:.3f} |mu_q|={aniso['mu_q_norm']:.3f} cos(mu_d,mu_q)={aniso['cos_mu']:.3f} "
        f"cos TB giữa document={cbar:.3f} a={an:.2f} -> va chạm/bit dự đoán={col_pred:.3f}, "
        f"bucket 16 bit hiệu dụng dự đoán={aniso['eff_buckets16_pred']:,.0f}")
    pre = "" if ds == "code" else f"{ds}_"

    if a.aniso_only:
        # Với siêu phẳng Gauss độc lập qua gốc, hai vector góc theta trùng một bit với xác suất 1 - theta/pi
        # (Goemans-Williamson), nên trùng cả k bit với xác suất (1 - theta/pi)^k. Kỳ vọng trên cặp document ngẫu
        # nhiên là xác suất trùng bucket k bit; nghịch đảo là số bucket hiệu dụng. Mô hình trường trung bình ở trên
        # thay phân bố góc bằng một vector trung bình chung cộng phần dư đẳng hướng.
        K16 = 16
        rs2 = np.random.RandomState(a.seed + 11)
        Ec = l2norm(E - mu_d)

        def pair_pred(X):
            tot, cnt, near = 0.0, 0, 0
            left = a.aniso_pairs
            while left > 0:
                m = min(20000, left); left -= m
                j1, j2 = rs2.randint(N, size=m), rs2.randint(N, size=m)
                ok = j1 != j2
                c = np.clip((X[j1[ok]] * X[j2[ok]]).sum(1), -1.0, 1.0)
                tot += float(((1.0 - np.arccos(c) / np.pi) ** K16).sum()); cnt += int(ok.sum())
                near += int((c > 0.99).sum())
            return tot / cnt, near / cnt

        def meas_coll(Xproj):
            keys = prefix16(Xproj[:, :K16] > 0)
            _, cnt = np.unique(keys, return_counts=True)
            return float((cnt * (cnt - 1.0)).sum() / (N * (N - 1.0))), keys

        def q_pred(Qn, X):
            v = []
            for i in range(0, len(Qn), 50):
                c = np.clip(Qn[i:i + 50] @ X.T, -1.0, 1.0)
                v.append(((1.0 - np.arccos(c) / np.pi) ** K16).mean(1))
            return float(np.concatenate(v).mean())

        qn = l2norm(Qall[ev])
        qc = l2norm(qn - mu_d)                                     # khoá query trừ tâm như 04b: q chuẩn hoá rồi trừ mu_d
        ext = dict(pairs=a.aniso_pairs, k=K16, coll_pred_meanfield=float(col_pred ** K16))
        ext["coll_pred_exact_u"], ext["near_dup_frac_u"] = pair_pred(En)
        ext["coll_pred_exact_c"], ext["near_dup_frac_c"] = pair_pred(Ec)
        ext["qfrac_pred_u"], ext["qfrac_pred_c"] = q_pred(qn, En), q_pred(qc, Ec)
        mu_, mc_, qu_, qc_ = [], [], [], []
        for P in P_rand[:a.tables_ref]:
            cu, ku = meas_coll(E @ P)
            cc, kc = meas_coll((E - mu_d) @ P)
            mu_.append(cu); mc_.append(cc)
            # tỉ lệ corpus nằm cùng bucket 16 bit với khoá gốc của query (cùng phía tâm)
            kq_u = prefix16((qn @ P)[:, :K16] > 0); kq_c = prefix16(((qn - mu_d) @ P)[:, :K16] > 0)
            uu, cu_ = np.unique(ku, return_counts=True); mu_map = dict(zip(uu.tolist(), cu_.tolist()))
            uc, cc_ = np.unique(kc, return_counts=True); mc_map = dict(zip(uc.tolist(), cc_.tolist()))
            qu_.append(float(np.mean([mu_map.get(int(x), 0) for x in kq_u]) / N))
            qc_.append(float(np.mean([mc_map.get(int(x), 0) for x in kq_c]) / N))
        ext.update(coll_meas_u=float(np.mean(mu_)), coll_meas_u_tables=mu_, coll_meas_c=float(np.mean(mc_)),
                   coll_meas_c_tables=mc_, qfrac_meas_u=float(np.mean(qu_)), qfrac_meas_c=float(np.mean(qc_)))
        log(f"trùng bucket 16 bit giữa hai document: trường trung bình {ext['coll_pred_meanfield']:.2e}, "
            f"công thức góc {ext['coll_pred_exact_u']:.2e}, đo thật {ext['coll_meas_u']:.2e} "
            f"(bucket hiệu dụng {1 / ext['coll_pred_meanfield']:,.0f} / {1 / ext['coll_pred_exact_u']:,.0f} / "
            f"{1 / max(ext['coll_meas_u'], 1e-12):,.0f}); cặp gần trùng (cos > 0,99) {100 * ext['near_dup_frac_u']:.3f}%")
        log(f"  trừ tâm: công thức góc {ext['coll_pred_exact_c']:.2e}, đo thật {ext['coll_meas_c']:.2e}")
        log(f"  phần corpus cùng bucket 16 bit với query: dự đoán {100 * ext['qfrac_pred_u']:.3f}%, đo {100 * ext['qfrac_meas_u']:.3f}% "
            f"(trừ tâm: {100 * ext['qfrac_pred_c']:.4f}% / {100 * ext['qfrac_meas_c']:.4f}%)")
        fa_ = a.out or f"probeA_{pre}{tag}_s{a.seed}.json"
        json.dump(dict(argv=vars(a), N=int(N), d=int(d), nS=int(nS), aniso=aniso, ext=ext, numpy=np.__version__),
                  open(fa_, "w"), indent=1)
        log(f"\n-> {fa_}   ({time.time() - t0:.0f}s)")
        return

    if a.space == "m1":
        cb = pb.pq_train(E[S], d // a.dsub, a.seed)
        cd = pb.pq_encode(E, cb)
    else:
        cb = np.load(f"{D}/{ds}_pq_codebook_m512.npy").astype(np.float32)
        cd = np.load(f"{D}/{ds}_pq_codes_m512.npy")

    # ---------------- điểm ADC của mọi document cho từng query đánh giá (dùng chung cho mọi biến thể)
    qv = l2norm(Qall[ev])
    k0, x0 = -mc.adc_l2(qv[0], cb, cd), mc.adc_ip(qv[0], cb, cd)
    Kall = np.empty((len(ev), N), dtype=k0.dtype)               # giữ đúng kiểu của 04b để thứ tự trùng
    Xall = np.empty((len(ev), N), dtype=x0.dtype)
    for i in range(len(ev)):
        Kall[i] = -mc.adc_l2(qv[i], cb, cd)
        Xall[i] = mc.adc_ip(qv[i], cb, cd)
    log(f"điểm ADC xong ({time.time() - t0:.0f}s)")

    allon = np.ones(N, dtype=bool)
    out = dict(argv=vars(a), N=int(N), d=int(d), nS=int(nS), aniso=aniso, variants={}, check=None,
               gold_oracle5=(None if gold is None else 100 * float(np.mean([gold[i] in set(gt5[i].tolist()) for i in ev]))))
    if gold is not None:
        log(f"nhãn hàm gốc có cho {a.nq} query; hàm gốc nằm trong top-5 chính xác của không gian này: {out['gold_oracle5']:.1f}%")
    for vn in variants:
        tv = time.time()
        if not vn.startswith("srp") and (d < 63 or nS < 63):
            log(f"[{vn}] bỏ qua: cần d >= 63 và |S| >= 63 (d={d}, |S|={nS})"); continue
        V = make_variant(vn, E[S], Lmax, a.seed, P_rand, mu_d, mu_q, a.k_pca, a.itq_iters)
        bits0 = doc_bits(E, V["W"][0], V["t"][0], V["cd"])
        p1 = bits0[:, :16].mean(0)
        pre_d = prefix16(bits0)
        _, cnt = np.unique(pre_d, return_counts=True)
        pr = cnt / cnt.sum()
        qb = (qv - V["cq"]) @ V["W"][0] - V["t"][0] > 0
        pre_q = prefix16(qb)
        nn_same = float(np.mean([np.mean(pre_d[gt5[ev[i]]] == pre_q[i]) for i in range(len(ev))]))
        rnd_same = float(np.mean(pre_d[i1] == pre_d[i2]))
        bitstats = dict(bias16=float(np.mean(np.abs(p1 - 0.5))), eff_buckets16=float(1.0 / (pr ** 2).sum()),
                        pair_collision16=float((pr ** 2).sum()), nn_same16=nn_same, rand_same16=rnd_same)
        anchors = np.stack([pb.nearest_node(pack(doc_bits(E, W, t, V["cd"])), nid) for W, t in zip(V["W"], V["t"])])
        pk = probe_keys(qv, V["W"], V["t"], V["cq"], Tmax, a.cbits)
        keys = np.stack(pk, axis=1)                                     # (Q, Lmax, Tmax)
        Q_, L_, T_ = keys.shape
        nodes = pb.knn_nodes(keys.reshape(-1), nid, a.k_query).reshape(Q_, L_, T_, a.k_query)
        log(f"[{vn}] index và định tuyến xong ({time.time() - tv:.0f}s)  bit lệch TB={bitstats['bias16']:.3f} "
            f"bucket16 hiệu dụng={bitstats['eff_buckets16']:,.0f} hàng xóm cùng tiền tố={100 * nn_same:.1f}% "
            f"(ngẫu nhiên {100 * rnd_same:.2f}%)")
        res = {}
        for L in Ls:
            anc = anchors[:L]
            ld = np.bincount(anc.ravel(), minlength=a.nodes)
            st = mc.load_stats(anc, a.nodes); st["gini"] = gini(ld)
            acc = {t: dict(reach=[], final=[], rr=[], cand=[], nodes=[], gf=[], gr=[]) for t in Ts}
            contacts = {t: np.zeros(a.nodes, dtype=np.int64) for t in Ts}
            for qi in range(len(ev)):
                g = set(gt5[ev[qi]].tolist())
                sd = mc.Side2(nodes[qi, :L], anc, a.nodes, (lambda r, qi=qi: (Kall[qi][r], Xall[qi][r])))
                for t in Ts:
                    n, lst, _ = sd.ranked(allon, a.kappa, 20, t)
                    tch = sd.touched(t)
                    A = acc[t]
                    A["reach"].append(len(set(sd.reach_set(t).tolist()) & g) / 5.0)
                    A["final"].append(len(set(lst[:5].tolist()) & g) / 5.0)
                    A["rr"].append(mc.rerank_hits(lst[:20], E, qv[qi], g))
                    if gold is not None:
                        c20 = lst[:20]
                        top = c20[np.argsort(-(E[c20] @ qv[qi]))[:5]] if len(c20) else c20
                        A["gf"].append(float(gold[ev[qi]] in set(lst[:5].tolist())))
                        A["gr"].append(float(gold[ev[qi]] in set(top.tolist())))
                    A["cand"].append(n); A["nodes"].append(len(tch))
                    contacts[t][tch] += 1
            rL = dict(storage=st)
            for t in Ts:
                A = acc[t]; c = contacts[t]; work = c * ld
                rL[str(t)] = dict(reach_r5=100 * float(np.mean(A["reach"])), final_r5=100 * float(np.mean(A["final"])),
                                  rr20=100 * float(np.mean(A["rr"])), cand=float(np.mean(A["cand"])),
                                  gold_final5=(100 * float(np.mean(A["gf"])) if A["gf"] else None),
                                  gold_rr20=(100 * float(np.mean(A["gr"])) if A["gr"] else None),
                                  nodes=float(np.mean(A["nodes"])),
                                  qload=dict(max_frac=float(c.max() / len(ev)), top1pct_share=share_top(c),
                                             gini=gini(c)),
                                  work=dict(max=float(work.max()), top1pct_share=share_top(work),
                                            total_per_query=float(work.sum() / len(ev))))
            res[str(L)] = rL
            log(f"[{vn}] L={L:2d} lưu trữ: max={st['max']} rỗng={100 * st['empty_frac']:.0f}% "
                f"top1%={100 * st['top1pct_share']:.1f}% Gini={st['gini']:.2f}")
            for t in Ts:
                r = rL[str(t)]
                log(f"      T={t:2d} reach={r['reach_r5']:5.1f} final={r['final_r5']:5.1f} rr20={r['rr20']:5.1f} "
                    f"ứng viên={r['cand']:8.0f} peer={r['nodes']:5.0f} peer nóng nhất chạm {100 * r['qload']['max_frac']:5.1f}% query, "
                    f"top1% peer nhận {100 * r['qload']['top1pct_share']:4.1f}% lượt hỏi, "
                    f"công việc top1%={100 * r['work']['top1pct_share']:4.1f}%")
        out["variants"][vn] = dict(bits=bitstats, results=res)
        log(f"[{vn}] xong ({time.time() - tv:.0f}s, tổng {time.time() - t0:.0f}s)")

    # ---------------- tự kiểm với 04b
    fG = f"probeG_{pre}{a.tag}_s{a.seed}.json"
    if a.space == "m1" and os.path.exists(fG) and 5 in Ls and 8 in Ts:
        G = json.load(open(fG))
        same = all(G["argv"].get(k) == v for k, v in (("nodes", a.nodes), ("probes", 8), ("tables", 5), ("nq", a.nq),
                                                         ("frac", a.frac), ("k_query", a.k_query), ("kappa", a.kappa),
                                                         ("cbits", a.cbits), ("dsub", a.dsub)))
        if same:
            f1 = max(G["results"], key=float)
            bad, n = 0, 0
            for vn, arm in (("srp", "E1ONLY"), ("srp_c", "E1ONLY_c"), ("srp_cq", "E1ONLY_cq")):
                if vn not in out["variants"] or arm not in G["results"][f1]:
                    continue
                new, o = out["variants"][vn]["results"]["5"]["8"], G["results"][f1][arm]
                for kn, ko in (("reach_r5", "reach_r5"), ("final_r5", "final_r5"), ("cand", "cand"), ("nodes", "nodes")):
                    n += 1; bad += abs(new[kn] - o[ko]) > 1e-9
                n += 1; bad += abs(new["rr20"] - o["rerank"]["20"]) > 1e-9
            out["check"] = dict(file=fG, n=n, bad=int(bad))
            log(f">>> so với 04b ({fG}, f = {f1}): {n} giá trị, {'KHỚP' if bad == 0 and n > 0 else f'{bad} LỆCH'}")
        else:
            log(f">>> không tự kiểm được: tham số của {fG} khác")
    else:
        log(">>> bỏ qua tự kiểm với 04b (không có file hoặc không phải space m1, L=5, T=8)")

    out["check_prev"] = None
    if a.check_prev != "none":
        if os.path.exists(a.check_prev):
            old = json.load(open(a.check_prev))
            n, bad, diffs = 0, 0, []

            def walk(x, y, path):
                nonlocal n, bad
                if isinstance(x, dict):
                    for kk_, vv in x.items():
                        if isinstance(y, dict) and kk_ in y:
                            walk(vv, y[kk_], path + [kk_])
                elif isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    n += 1
                    if not (abs(x - y) <= 1e-9 or (x != x and y != y)):
                        bad += 1; diffs.append(("/".join(path), x, y))
            for vn in out["variants"]:
                if vn in old.get("variants", {}):
                    walk(old["variants"][vn], out["variants"][vn], [vn])
            out["check_prev"] = dict(file=a.check_prev, n=n, bad=int(bad), diffs=diffs[:10])
            log(f">>> so với lượt cũ ({a.check_prev}): {n} giá trị, {'KHỚP' if bad == 0 and n > 0 else f'{bad} LỆCH'}")
            for dd in diffs[:10]:
                log(f"    lệch: {dd}")
        else:
            log(f">>> không có {a.check_prev} để so với lượt cũ")

    fn = a.out or f"probeP_{pre}{tag}_s{a.seed}.json"
    json.dump(out, open(fn, "w"), indent=1)
    log(f"\n-> {fn}   ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
