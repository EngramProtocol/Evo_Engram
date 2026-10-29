#!/usr/bin/env python3
"""
12_diag_itq.py  —  ĐỢT 9 (thăm dò). Chẩn đoán điểm nóng của placement học itq_q.

Đợt 8: với Arctic trên code100kfq, peer nặng nhất của itq_q giữ 1.271 đến 1.296 record ở mọi seed, trong khi SRP trừ
tâm giữ 114 đến 258 và PCA 187 đến 475. Script này dựng đúng placement của 10_probe_placement.py (make_variant, cùng S,
cùng node, cùng seed) cho các biến thể trong --variants, rồi đo:
  - tải theo peer gộp L bảng (như 10) và phần của từng bảng ở peer nặng nhất;
  - nhóm khoá 63 bit lớn nhất của từng bảng (các object có khoá trùng hệt nhau), và độ trùng của các nhóm đó giữa
    các bảng (Jaccard);
  - với các object ở peer nặng nhất: cosine trung bình giữa chúng, cosine với tâm document, phần năng lượng sau trừ
    tâm nằm ngoài k thành phần chính của S (k = 63, 128, 256) so với cả corpus; độ dài văn bản và vài đoạn đầu nếu có
    <dataset>_corpus_texts.json (hoặc code100k_corpus_texts.json).
Ghi diagITQ_<pre><tag>_s<seed>.json. Không chấm recall (phần đó do 10 với biến thể itq<k>_q).

CHẠY: python3 evo/12_diag_itq.py --dataset code100kfq --tag arctic --seed 6 --nodes 50000 --frac 0.02
"""
import argparse, importlib.util, json, os, random, time
import numpy as np
import me_common as mc

_here = os.path.dirname(os.path.abspath(__file__))
_sp10 = importlib.util.spec_from_file_location("p10", os.path.join(_here, "10_probe_placement.py"))
p10 = importlib.util.module_from_spec(_sp10)
_sp10.loader.exec_module(p10)
pb, log, l2norm = mc.pb, mc.log, mc.l2norm


def texts_of(D, ds, N):
    for fn in (f"{D}/{ds}_corpus_texts.json", f"{D}/code100k_corpus_texts.json"):
        if os.path.exists(fn):
            raw = json.load(open(fn))
            if len(raw) < N:
                continue
            out = []
            for r in raw[:N]:
                if isinstance(r, str):
                    out.append(r)
                elif isinstance(r, dict):
                    v = next((r[k] for k in ("text", "code", "content", "body", "document", "title") if k in r), "")
                    out.append(str(v))
                else:
                    out.append(str(r))
            return out, fn
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--space", default="m1", choices=["m1", "m0"])
    ap.add_argument("--dataset", default="code100kfq")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--seed", type=int, default=6)
    ap.add_argument("--nodes", type=int, default=50000)
    ap.add_argument("--nq", type=int, default=300)
    ap.add_argument("--frac", type=float, default=0.02)
    ap.add_argument("--tables", type=int, default=5)
    ap.add_argument("--tables-ref", type=int, default=5)
    ap.add_argument("--variants", default="itq_q,itq128_q,itq256_q,srp_c")
    ap.add_argument("--k-pca", type=int, default=128)
    ap.add_argument("--itq-iters", type=int, default=50)
    ap.add_argument("--pairs", type=int, default=20000)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    t0 = time.time()
    D, ds = a.data_dir, a.dataset
    if a.space == "m1":
        E = np.load(f"{D}/{ds}_{a.tag}_corpus_embeddings.npy").astype(np.float32)
        Qall = np.load(f"{D}/{ds}_{a.tag}_query_embeddings.npy").astype(np.float32)
    else:
        E = np.load(f"{D}/{ds}_corpus_embeddings.npy").astype(np.float32)
        Qall = np.load(f"{D}/{ds}_query_embeddings.npy").astype(np.float32)
    tag = a.tag if a.space == "m1" else "m0"
    N, d = E.shape
    trq = np.arange(a.nq, len(Qall))
    # đúng các bước của 10: node, siêu phẳng ngẫu nhiên, mẫu S, tâm
    rnd = random.Random(a.seed)
    nid = np.array([rnd.getrandbits(63) for _ in range(a.nodes)], dtype=np.int64)
    P_rand = pb.gen_proj(a.seed, d, a.tables)
    perm = np.random.RandomState(a.seed).permutation(N)
    nS = max(a.tables_ref * 20, int(round(a.frac * N)))
    S = perm[:nS]
    mu_d = E[S].mean(0).astype(np.float32)
    mu_q = Qall[trq].mean(0).astype(np.float32) if len(trq) else mu_d
    log(f"[12] dataset={ds} space={a.space} tag={tag} seed={a.seed} N={N} d={d} S={nS} nodes={a.nodes} "
        f"biến thể={a.variants}  (numpy {np.__version__})")
    Xc_S = E[S] - mu_d
    _, sv, Vt = np.linalg.svd(Xc_S, full_matrices=False)
    rs = np.random.RandomState(a.seed + 5)
    samp = rs.choice(N, size=min(N, 5000), replace=False)
    mud_n = mu_d / max(1e-12, float(np.linalg.norm(mu_d)))

    def out_energy(idx):
        Xc = E[idx] - mu_d
        tot = (Xc ** 2).sum(1)
        res = {}
        for k in (63, 128, 256):
            kk = min(k, Vt.shape[0])
            pr = Xc @ Vt[:kk].T
            res[str(k)] = float(np.mean(1.0 - (pr ** 2).sum(1) / np.maximum(tot, 1e-12)))
        return res

    def pair_cos(idx, m):
        if len(idx) < 2:
            return float("nan")
        i1, i2 = rs.choice(idx, size=m), rs.choice(idx, size=m)
        ok = i1 != i2
        En = l2norm(E)
        return float(np.mean((En[i1[ok]] * En[i2[ok]]).sum(1)))

    base = dict(out_energy=out_energy(samp), pair_cos=pair_cos(samp, a.pairs),
                cos_mu=float(np.mean(l2norm(E[samp]) @ mud_n)))
    log(f"corpus (mẫu 5.000): năng lượng ngoài 63/128/256 TP = "
        f"{base['out_energy']['63']:.3f}/{base['out_energy']['128']:.3f}/{base['out_energy']['256']:.3f}, "
        f"cos TB giữa object {base['pair_cos']:.3f}, cos với tâm {base['cos_mu']:.3f}")
    texts, tfile = texts_of(D, ds, N)
    out = dict(argv=vars(a), N=int(N), d=int(d), nS=int(nS), corpus=base, texts_file=tfile, variants={},
               numpy=np.__version__)
    for vn in a.variants.split(","):
        tv = time.time()
        V = p10.make_variant(vn, E[S], a.tables, a.seed, P_rand, mu_d, mu_q, a.k_pca, a.itq_iters)
        keys = np.stack([p10.pack(p10.doc_bits(E, W, t, V["cd"])) for W, t in zip(V["W"], V["t"])])   # (L, N)
        anchors = np.stack([pb.nearest_node(k_, nid) for k_ in keys])
        ld = np.bincount(anchors.ravel(), minlength=a.nodes)
        hot = int(np.argmax(ld))
        per_tab = [int((anchors[t] == hot).sum()) for t in range(a.tables)]
        groups = []
        for t in range(a.tables):
            u, inv, cnt = np.unique(keys[t], return_inverse=True, return_counts=True)
            g = int(np.argmax(cnt))
            groups.append(np.flatnonzero(inv == g))
        jac = [[len(np.intersect1d(x, y)) / max(1, len(np.union1d(x, y))) for y in groups] for x in groups]
        hot_docs = np.unique(np.concatenate([np.flatnonzero(anchors[t] == hot) for t in range(a.tables)]))
        tmax = int(np.argmax(per_tab))
        hd_t = np.flatnonzero(anchors[tmax] == hot)
        same_key = int(np.unique(keys[tmax][hd_t]).size) if len(hd_t) else 0
        info = dict(max=int(ld.max()), hot_node=hot, per_table_at_hot=per_tab, hot_docs=int(len(hot_docs)),
                    hot_table=tmax, hot_table_docs=int(len(hd_t)), hot_table_distinct_keys=same_key,
                    top_group_sizes=[int(len(x)) for x in groups],
                    top_group_jaccard=[[round(v, 3) for v in row] for row in jac],
                    top_group_in_hot=[int(np.isin(x, hot_docs).sum()) for x in groups])
        if len(hd_t) >= 2:
            info.update(hot_out_energy=out_energy(hd_t), hot_pair_cos=pair_cos(hd_t, min(a.pairs, 20 * len(hd_t))),
                        hot_cos_mu=float(np.mean(l2norm(E[hd_t]) @ mud_n)))
            if texts is not None:
                lens = np.array([len(texts[i]) for i in hd_t])
                info.update(hot_text_len_median=float(np.median(lens)),
                            corpus_text_len_median=float(np.median([len(texts[i]) for i in samp])),
                            hot_text_examples=[texts[i][:160] for i in hd_t[:8].tolist()],
                            hot_text_distinct=int(len(set(texts[i] for i in hd_t))))
        out["variants"][vn] = info
        log(f"[{vn}] tải tối đa {info['max']} ở node {hot}; theo bảng {per_tab}; nhóm khoá lớn nhất mỗi bảng "
            f"{info['top_group_sizes']}; bảng {tmax}: {len(hd_t)} object, {same_key} khoá khác nhau  "
            f"({time.time() - tv:.0f}s)")
        if "hot_out_energy" in info:
            log(f"      object ở peer nóng: năng lượng ngoài 63/128/256 TP = {info['hot_out_energy']['63']:.3f}/"
                f"{info['hot_out_energy']['128']:.3f}/{info['hot_out_energy']['256']:.3f}, cos TB giữa chúng "
                f"{info['hot_pair_cos']:.3f}, cos với tâm {info['hot_cos_mu']:.3f}"
                + (f", độ dài văn bản trung vị {info['hot_text_len_median']:.0f} (corpus "
                   f"{info['corpus_text_len_median']:.0f}), {info['hot_text_distinct']} văn bản khác nhau"
                   if "hot_text_len_median" in info else ""))
    pre = "" if ds == "code" else f"{ds}_"
    fn = a.out or f"diagITQ_{pre}{tag}_s{a.seed}.json"
    json.dump(out, open(fn, "w"), indent=1, ensure_ascii=False)
    log(f"\n-> {fn}   ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
