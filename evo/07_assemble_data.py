#!/usr/bin/env python3
"""
07_assemble_data.py  —  CHẠY TRÊN node-dal-02 (CPU), sau khi đã chép thư mục kết quả Colab (evo_out) lên server.

Lắp dữ liệu đợt 4 vào data/ theo đúng quy ước tên file mà các probe đang đọc, không sửa probe nào:

  code100k_<tag>_*      corpus 100k, 500 query cũ; tag = bgebase, e5large, arctic
  code100kfq_*          corpus 100k (symlink), 500 query MỚI chọn trên Colab: bộ dùng cho confirmatory
  code_arctic_*         corpus 20k = 20.000 dòng đầu của code100k (prefix byte-for-byte), query cũ
  scifact_arctic_*      SciFact với arctic
  <ds>_<tag>_para_*     paraphrase của 300 query đánh giá (ds = code, scifact) và ground truth M1 của chúng

Trước khi ghi bất cứ thứ gì, đối chiếu đường Colab với dữ liệu đang có trên server:
  - 64 document code100k (gồm cả phần 80k mới) mã hoá lại bằng M0 trên Colab phải trùng embedding M0 đã lưu
  - 32 query cũ (code, SciFact) mã hoá bằng M0, và bằng bge-base / e5-large, phải trùng file đã có
  - 64 dòng đầu corpus mã hoá bằng bge-base / e5-large trên Colab phải trùng phần 20k đã có
  - 20.000 chuỗi đầu của code100k phải trùng nguyên văn corpus code 20k
Ngưỡng: cosine nhỏ nhất >= 0.999. Sai một mục là dừng, không ghi file nào.

Không bao giờ ghi qua symlink (data/ của Evo_Engram có symlink sang repo V-Engram đã chốt).

CHẠY:  python3 evo/07_assemble_data.py --colab ~/evo_out 2>&1 | tee evo/assemble_round4.log
"""
import argparse, glob, hashlib, json, os, sys, time
import numpy as np

TAGS = ["bgebase", "e5large", "arctic"]
PREFIX_DONE = ["bgebase", "e5large"]
N_OLD = 20000
WRITTEN = []


def log(m):
    print(m, flush=True)


def die(m):
    log("*** DỪNG: " + m)
    sys.exit(1)


def P(D, *names):
    return os.path.join(D, *names)


def safe_target(path):
    if os.path.islink(path):
        die(f"{path} là symlink, không ghi đè (tránh ghi sang repo V-Engram)")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def save_npy(path, X):
    safe_target(path)
    np.save(path, np.ascontiguousarray(X, dtype=np.float32))
    WRITTEN.append(path)


def save_json(path, obj):
    safe_target(path)
    json.dump(obj, open(path, "w"), ensure_ascii=False)
    WRITTEN.append(path)


def link(dst, src):
    """dst trong data/ trỏ tới file thật của src (đi qua symlink nếu src là symlink)."""
    real = os.path.realpath(src)
    if not os.path.exists(real):
        die(f"thiếu {src}")
    if os.path.lexists(dst):
        if os.path.islink(dst) and os.path.realpath(dst) == real:
            return
        if os.path.islink(dst):
            os.remove(dst)
        else:
            die(f"{dst} đã tồn tại và không phải symlink tới {real}")
    os.symlink(real, dst)
    WRITTEN.append(dst)


def cos_rows(A, B):
    A = np.asarray(A, np.float64); B = np.asarray(B, np.float64)
    return np.sum(A * B, 1) / (np.linalg.norm(A, axis=1) * np.linalg.norm(B, axis=1))


def check(name, A, B, thr=0.999):
    c = cos_rows(A, B)
    ok = c.min() >= thr
    log(f"  kiểm {name:42s} n={len(c):3d} cos tb={c.mean():.6f} nhỏ nhất={c.min():.6f}  {'ĐẠT' if ok else 'HỎNG'}")
    return ok


def topk(Q, E, k=10, bs=64):
    out = np.empty((len(Q), k), np.int64); sims = np.empty((len(Q), k), np.float32)
    for s in range(0, len(Q), bs):
        S = Q[s:s + bs] @ E.T
        ix = np.argpartition(-S, k, axis=1)[:, :k]
        v = np.take_along_axis(S, ix, 1)
        o = np.argsort(-v, axis=1, kind="stable")
        out[s:s + bs] = np.take_along_axis(ix, o, 1)
        sims[s:s + bs] = np.take_along_axis(v, o, 1)
    return out, sims


def gt_json(top, sims, texts, extra=None):
    res = []
    for i in range(len(top)):
        g = {"query_id": i + 1, "query_text": texts[i] if texts is not None else None,
             "top_5_results": [{"index": int(j), "cosine_similarity": float(s)} for j, s in zip(top[i, :5], sims[i, :5])],
             "top_10_results": [{"index": int(j), "cosine_similarity": float(s)} for j, s in zip(top[i], sims[i])]}
        if extra is not None:
            g.update(extra[i])
        res.append(g)
    return res


def angle5(Q, E, top):
    return float(np.mean([np.degrees(np.arccos(np.clip(E[top[i, :5]] @ Q[i], -1, 1))).mean() for i in range(len(Q))]))


def overlap5(ta, tb):
    return 100 * float(np.mean([len(set(ta[i, :5].tolist()) & set(tb[i, :5].tolist())) / 5.0 for i in range(len(ta))]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--colab", required=True, help="thư mục evo_out tải từ Colab")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--vengram-data", default=os.path.expanduser("~/V_ENGRAM_SIMULATION/data"))
    ap.add_argument("--n-old", type=int, default=N_OLD)
    a = ap.parse_args()
    t0 = time.time()
    D, C = a.data_dir, a.colab
    os.makedirs(D, exist_ok=True)

    # ---------------- 0. symlink code100k_* của V-Engram nếu data/ chưa có
    for f in sorted(glob.glob(os.path.join(a.vengram_data, "code100k_*"))):
        dst = P(D, os.path.basename(f))
        if not os.path.lexists(dst):
            os.symlink(os.path.realpath(f), dst); log(f"symlink {dst} -> {os.path.realpath(f)}")
    need = ["code100k_corpus_embeddings.npy", "code100k_query_embeddings.npy", "code100k_pq_codebook_m512.npy",
            "code100k_pq_codes_m512.npy", "code100k_corpus_texts.json", "code100k_ground_truth.json",
            "code_corpus_texts.json", "code_query_embeddings.npy", "scifact_corpus_embeddings.npy",
            "scifact_query_embeddings.npy", "scifact_corpus_texts.json", "scifact_ground_truth.json"]
    need += [f"code_{t}_{k}_embeddings.npy" for t in PREFIX_DONE for k in ("corpus", "query")]
    need += [f"code_{t}_ground_truth.json" for t in PREFIX_DONE] + [f"scifact_{t}_ground_truth.json" for t in PREFIX_DONE]
    miss = [f for f in need if not os.path.exists(P(D, f))]
    if miss:
        die("data/ thiếu: " + ", ".join(miss))
    fq = json.load(open(P(C, "fresh_queries.json")))
    log(f"Colab: tái lập corpus khớp toàn bộ = {fq['check']['exact_rebuild']}  ({fq['check']})")
    if not fq["check"]["exact_rebuild"]:
        log("  CẢNH BÁO: docstring lấy theo ánh xạ chuỗi, không phải tái lập nguyên vẹn; ghi rõ trong báo cáo")

    # ---------------- 1. đối chiếu đường Colab với server (chưa ghi gì)
    log("\n== ĐỐI CHIẾU COLAB VỚI SERVER")
    E0 = np.load(P(D, "code100k_corpus_embeddings.npy"), mmap_mode="r")
    Q0 = np.load(P(D, "code100k_query_embeddings.npy"))
    texts100 = json.load(open(P(D, "code100k_corpus_texts.json")))
    texts20 = json.load(open(P(D, "code_corpus_texts.json")))
    N = len(texts100); n_old = a.n_old
    ok = True
    if len(texts20) != n_old or texts100[:n_old] != texts20:
        log("  HỎNG: 20.000 chuỗi đầu của code100k không trùng corpus code"); ok = False
    else:
        log(f"  kiểm {'20k chuỗi đầu code100k == corpus code':42s} ĐẠT")
    if not np.array_equal(Q0, np.load(P(D, "code_query_embeddings.npy"))):
        log("  HỎNG: query M0 của code100k khác code"); ok = False
    rows = json.load(open(P(C, "q", "code100k_m0_docchk64_rows.json")))
    log(f"  (64 document kiểm M0: {sum(r >= n_old for r in rows)} dòng nằm trong phần mới)")
    ok &= check("M0 64 document code100k (Colab vs đã lưu)", np.load(P(C, "q", "code100k_m0_docchk64.npy")),
                np.asarray(E0[rows]))
    ok &= check("M0 32 query code (Colab vs đã lưu)", np.load(P(C, "q", "codeold_chk32_m0.npy")), Q0[:32])
    ok &= check("M0 32 query SciFact (Colab vs đã lưu)", np.load(P(C, "q", "scifact_chk32_m0.npy")),
                np.load(P(D, "scifact_query_embeddings.npy"))[:32])
    for t in PREFIX_DONE:
        ok &= check(f"{t} 32 query code (Colab vs đã lưu)", np.load(P(C, "q", f"codeold_chk32_{t}.npy")),
                    np.load(P(D, f"code_{t}_query_embeddings.npy"))[:32])
        ok &= check(f"{t} 64 document đầu (Colab vs đã lưu)", np.load(P(C, "emb", f"code100k_{t}_head64.npy")),
                    np.load(P(D, f"code_{t}_corpus_embeddings.npy"), mmap_mode="r")[:64])
    if not ok:
        die("đối chiếu không đạt, không ghi file nào")

    # ---------------- 2. corpus M1 của code100k
    log("\n== CORPUS M1")
    E1 = {}
    for t in TAGS:
        parts = sorted(glob.glob(P(C, "emb", f"code100k_{t}_rows*_*.npy")))
        spans = [tuple(int(x) for x in os.path.basename(p)[len(f"code100k_{t}_rows"):-4].split("_")) for p in parts]
        start = n_old if t in PREFIX_DONE else 0
        pos = start
        for s, e in spans:
            if s != pos:
                die(f"{t}: khối Colab không liền mạch ở dòng {pos} (gặp {s})")
            pos = e
        if pos != N:
            die(f"{t}: khối Colab dừng ở dòng {pos}, cần {N}")
        blocks = [np.load(p) for p in parts]
        if t in PREFIX_DONE:
            blocks = [np.load(P(D, f"code_{t}_corpus_embeddings.npy"))] + blocks
        X = np.concatenate(blocks, 0).astype(np.float32)
        nrm = np.linalg.norm(X, axis=1)
        if X.shape[0] != N or np.abs(nrm - 1).max() > 1e-3:
            die(f"{t}: corpus sai kích thước hoặc chưa chuẩn hoá ({X.shape})")
        save_npy(P(D, f"code100k_{t}_corpus_embeddings.npy"), X)
        E1[t] = X
        log(f"  code100k_{t}_corpus_embeddings.npy  {X.shape}")
    save_npy(P(D, "code_arctic_corpus_embeddings.npy"), E1["arctic"][:n_old])
    Esa = np.load(P(C, "emb", "scifact_arctic_corpus.npy"))
    save_npy(P(D, "scifact_arctic_corpus_embeddings.npy"), Esa)

    # ---------------- 3. query + ground truth M1 (query cũ)
    log("\n== QUERY CŨ VÀ GROUND TRUTH M1")
    gt0_100 = json.load(open(P(D, "code100k_ground_truth.json")))
    old_txt = [g["query_text"] for g in gt0_100]
    top0_100 = np.array([[int(r["index"]) for r in g["top_5_results"][:5]] for g in gt0_100])
    sets = []
    for t in TAGS:
        Qt = (np.load(P(D, f"code_{t}_query_embeddings.npy")) if t in PREFIX_DONE
              else np.load(P(C, "q", "codeold_arctic.npy")))
        save_npy(P(D, f"code100k_{t}_query_embeddings.npy"), Qt)
        sets.append(("code100k", t, Qt, E1[t], old_txt, top0_100))
    Qa = np.load(P(C, "q", "codeold_arctic.npy"))
    save_npy(P(D, "code_arctic_query_embeddings.npy"), Qa)
    gt0_20 = json.load(open(P(D, "code_ground_truth.json"))) if os.path.exists(P(D, "code_ground_truth.json")) else None
    top0_20 = (np.array([[int(r["index"]) for r in g["top_5_results"][:5]] for g in gt0_20]) if gt0_20 else None)
    sets.append(("code", "arctic", Qa, E1["arctic"][:n_old], old_txt, top0_20))
    gts = json.load(open(P(D, "scifact_ground_truth.json")))
    top0_sf = np.array([[int(r["index"]) for r in g["top_5_results"][:5]] for g in gts])
    Qsa = np.load(P(C, "q", "scifact_arctic.npy"))
    save_npy(P(D, "scifact_arctic_query_embeddings.npy"), Qsa)
    sets.append(("scifact", "arctic", Qsa, Esa, [g["query_text"] for g in gts], top0_sf))
    for ds, t, Qt, Et, txt, top0 in sets:
        top, sims = topk(Qt, Et)
        save_json(P(D, f"{ds}_{t}_ground_truth.json"), gt_json(top, sims, txt))
        ov = overlap5(top0, top) if top0 is not None else float("nan")
        log(f"  {ds:9s} {t:8s} góc tới top-5 = {angle5(Qt, Et, top):5.2f}°   GT trùng M0 (top-5) = {ov:5.1f}%")
    # đối chiếu: GT bge-base / e5 của code 20k tính lại phải trùng file cũ
    for t in PREFIX_DONE:
        old = json.load(open(P(D, f"code_{t}_ground_truth.json")))
        topo = np.array([[int(r["index"]) for r in g["top_5_results"][:5]] for g in old])
        topn, _ = topk(np.load(P(D, f"code_{t}_query_embeddings.npy")),
                       np.load(P(D, f"code_{t}_corpus_embeddings.npy")))
        log(f"  kiểm GT code {t} tính lại == file đợt trước: {overlap5(topo, topn):.2f}% (phải 100)")

    # ---------------- 4. bộ query mới code100kfq
    log("\n== BỘ QUERY MỚI code100kfq")
    ds = "code100kfq"
    for suf in ("corpus_embeddings.npy", "pq_codebook_m512.npy", "pq_codes_m512.npy", "corpus_texts.json"):
        link(P(D, f"{ds}_{suf}"), P(D, f"code100k_{suf}"))
    fr_txt, fr_rows = fq["texts"], fq["rows"]
    Qf0 = np.load(P(C, "q", "fresh_m0.npy"))
    save_npy(P(D, f"{ds}_query_embeddings.npy"), Qf0)
    E0a = np.asarray(E0)
    topf0, simf0 = topk(Qf0, E0a)
    src_in = [int(fr_rows[i]) in set(topf0[i].tolist()) for i in range(len(fr_rows))]
    extra = [{"source_corpus_index": int(fr_rows[i]), "source_in_gt10": bool(src_in[i])} for i in range(len(fr_rows))]
    save_json(P(D, f"{ds}_ground_truth.json"), gt_json(topf0, simf0, fr_txt, extra))
    old_src = [g.get("source_corpus_index", -1) for g in gt0_100]
    old_in = [s in set(int(r["index"]) for r in g["top_10_results"]) for s, g in zip(old_src, gt0_100)]
    ang_new, ang_old = angle5(Qf0, E0a, topf0), angle5(Q0, E0a, top0_100)
    log(f"  M0: góc query -> GT5: mới {ang_new:.1f}°  cũ {ang_old:.1f}°   "
        f"document gốc trong GT10: mới {100 * np.mean(src_in):.1f}%  cũ {100 * np.mean(old_in):.1f}%")
    if ang_new < 35:
        log("  CẢNH BÁO: góc nhỏ bất thường, nghi query còn nằm trong document")
    for t in TAGS:
        link(P(D, f"{ds}_{t}_corpus_embeddings.npy"), P(D, f"code100k_{t}_corpus_embeddings.npy"))
        Qft = np.load(P(C, "q", f"fresh_{t}.npy"))
        save_npy(P(D, f"{ds}_{t}_query_embeddings.npy"), Qft)
        top, sims = topk(Qft, E1[t])
        save_json(P(D, f"{ds}_{t}_ground_truth.json"), gt_json(top, sims, fr_txt))
        log(f"  {ds} {t:8s} góc tới top-5 = {angle5(Qft, E1[t], top):5.2f}°   GT trùng M0 (top-5) = "
            f"{overlap5(topf0, top):5.1f}%")

    # ---------------- 5. paraphrase
    log("\n== PARAPHRASE")
    for dsn, corp in (("code", "code"), ("scifact", "scifact")):
        meta = json.load(open(P(C, "para", f"{dsn}_paraphrases.json")))
        save_json(P(D, f"{dsn}_paraphrases.json"), meta)
        mask = np.load(P(C, "para", f"{dsn}_para_mask.npy"))
        safe_target(P(D, f"{dsn}_para_mask.npy")); np.save(P(D, f"{dsn}_para_mask.npy"), mask)
        WRITTEN.append(P(D, f"{dsn}_para_mask.npy"))
        nq, K = mask.shape
        log(f"  {dsn}: {nq} query, {mask.sum()} paraphrase (đủ {K}: {int((mask.sum(1) == K).sum())}), LLM = {meta['llm']}")
        for t in TAGS:
            Ec = (E1[t][:n_old] if (dsn == "code" and t == "arctic") else
                  Esa if (dsn == "scifact" and t == "arctic") else
                  np.load(P(D, f"{corp}_{t}_corpus_embeddings.npy")))
            Qo = (Qa if (dsn == "code" and t == "arctic") else Qsa if (dsn == "scifact" and t == "arctic")
                  else np.load(P(D, f"{corp}_{t}_query_embeddings.npy")))[:nq]
            Pe = np.load(P(C, "para", f"{dsn}_{t}_para.npy"))
            save_npy(P(D, f"{dsn}_{t}_para_embeddings.npy"), Pe)
            flat = Pe[mask]
            top, _ = topk(flat, Ec, k=5)
            G = np.full((nq, K, 5), -1, np.int64); G[mask] = top
            save_json(P(D, f"{dsn}_{t}_para_ground_truth.json"),
                      [[(G[i, j].tolist() if mask[i, j] else None) for j in range(K)] for i in range(nq)])
            topo, _ = topk(Qo, Ec, k=5)
            qi = np.nonzero(mask)[0]
            cs = np.sum(flat * Qo[qi], 1)
            ov = np.array([len(set(G[i, j].tolist()) & set(topo[i].tolist())) / 5.0 for i, j in zip(*np.nonzero(mask))])
            log(f"    {t:8s} cos(paraphrase, gốc) tb={cs.mean():.3f} p10={np.percentile(cs, 10):.3f}   "
                f"GT top-5 trùng gốc tb={100 * ov.mean():.1f}%  bằng 0: {100 * np.mean(ov == 0):.1f}%")

    # ---------------- 6. manifest
    rows_m = []
    for p in WRITTEN:
        rp = os.path.realpath(p)
        h = hashlib.sha256()
        with open(rp, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        rows_m.append(f"{h.hexdigest()}  {p}{'  -> ' + rp if os.path.islink(p) else ''}")
    mf = P(D, "MANIFEST_round4.sha256")
    safe_target(mf)
    open(mf, "w").write("\n".join(rows_m) + "\n")
    log(f"\nXONG: ghi {len(WRITTEN)} file, danh sách và sha256 ở {mf}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
