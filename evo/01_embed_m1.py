#!/usr/bin/env python3
"""
01_embed_m1.py  —  CHẠY TRÊN node-dal-02 (CPU).

Nhúng corpus và query của một bộ dữ liệu bằng mô hình thứ hai M1, rồi tính ground truth
trong không gian M1. Thứ tự dòng khớp tuyệt đối với embedding M0 đã có trong data/.

Trước khi nhúng, script tự kiểm rằng văn bản đưa vào M1 đúng là văn bản đã dùng để tạo
embedding M0: mã hoá lại vài document và query bằng M0, so với embedding M0 đã lưu
(cosine phải >= 0.999). Nếu corpus_texts là list[dict], script thử các cách ghép
title/text và chỉ chọn cách tái tạo đúng embedding M0.

CẦN TRONG data/:
    <dataset>_corpus_texts.json, <dataset>_ground_truth.json,
    <dataset>_corpus_embeddings.npy, <dataset>_query_embeddings.npy   (của M0)

CHẠY:
    python3 evo/01_embed_m1.py --dataset scifact --model BAAI/bge-base-en-v1.5 --tag bgebase --device cpu
    python3 evo/01_embed_m1.py --dataset scifact --model intfloat/e5-large-v2  --tag e5large --device cpu

GHI RA data/:
    <dataset>_<tag>_corpus_embeddings.npy, <dataset>_<tag>_query_embeddings.npy,
    <dataset>_<tag>_ground_truth.json
"""
import argparse, json, os, sys, time
import numpy as np

# prefix theo họ model. bge-large gốc KHÔNG dùng instruction (đúng bản V-Engram), nên
# bge-base cũng để trống cho nhất quán. e5 bắt buộc có prefix.
DEFAULT_PREFIX = {
    "bge": ("", ""),                      # (query, passage)
    "e5": ("query: ", "passage: "),
    "gte": ("", ""),
}


def pick_prefix(model_name, override_q, override_p):
    if override_q is not None or override_p is not None:
        return (override_q or ""), (override_p or "")
    low = model_name.lower()
    for k, v in DEFAULT_PREFIX.items():
        if k in low:
            return v
    return "", ""


def text_candidates(rec):
    """Các cách dựng văn bản từ một record dạng dict, theo thứ tự thử."""
    out = []
    for k in ("text", "body", "document", "content", "abstract"):
        if k in rec and isinstance(rec[k], str):
            out.append((k, lambda r, k=k: r[k]))
            if "title" in rec:
                for sep, nm in ((" ", "space"), (". ", "dot"), ("\n", "newline"), (": ", "colon")):
                    out.append((f"title+{nm}+{k}",
                                lambda r, k=k, sep=sep: (r.get("title") or "") + sep + r[k]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="code", help="tiền tố file trong data/: code, scifact, squad ...")
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", required=True, help="hậu tố file, vd bgebase")
    ap.add_argument("--m0", default="BAAI/bge-large-en-v1.5", help="mô hình đã tạo embedding M0")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--max-seq", type=int, default=0, help="0 = giữ mặc định của model")
    ap.add_argument("--device", default=None, help="cpu | cuda | None = tự chọn")
    ap.add_argument("--query-prefix", default=None)
    ap.add_argument("--passage-prefix", default=None)
    ap.add_argument("--n-check", type=int, default=16, help="số document/query dùng để tự kiểm với M0")
    a = ap.parse_args()

    from sentence_transformers import SentenceTransformer
    d, ds = a.data_dir, a.dataset
    raw = json.load(open(os.path.join(d, f"{ds}_corpus_texts.json")))
    gt0 = json.load(open(os.path.join(d, f"{ds}_ground_truth.json")))
    E0 = np.load(os.path.join(d, f"{ds}_corpus_embeddings.npy"), mmap_mode="r")
    Q0 = np.load(os.path.join(d, f"{ds}_query_embeddings.npy"), mmap_mode="r")
    qkey = next((k for k in ("query_text", "query", "text", "claim") if k in gt0[0]), None)
    if qkey is None:
        sys.exit(f"không thấy trường query trong ground truth, các khoá: {list(gt0[0])}")
    queries = [g[qkey] for g in gt0]
    print(f"dataset={ds}  corpus={len(raw)}  queries={len(queries)}  "
          f"(M0: {E0.shape[0]} x {E0.shape[1]}, {Q0.shape[0]} query)")
    assert len(raw) == E0.shape[0], "số document không khớp embedding M0"
    assert len(queries) == Q0.shape[0], "số query không khớp embedding M0"

    # ---------- tự kiểm văn bản với M0
    rng = np.random.RandomState(0)
    idx = rng.choice(len(raw), min(a.n_check, len(raw)), replace=False)
    qidx = rng.choice(len(queries), min(a.n_check, len(queries)), replace=False)
    m0 = SentenceTransformer(a.m0, device=a.device)
    enc0 = lambda xs: m0.encode(xs, batch_size=16, normalize_embeddings=True,
                                convert_to_numpy=True, show_progress_bar=False)
    if isinstance(raw[0], str):
        cands = [("chuỗi gốc", lambda r: r)]
    elif isinstance(raw[0], dict):
        cands = text_candidates(raw[0])
        if not cands:
            sys.exit(f"corpus_texts là list[dict] nhưng không có trường văn bản quen thuộc: {list(raw[0])}")
    else:
        sys.exit(f"không hiểu định dạng corpus_texts: {type(raw[0])}")
    best = None
    for name, fn in cands:
        try:
            V = enc0([fn(raw[i]) for i in idx])
        except Exception as ex:
            print(f"  bỏ qua cách dựng '{name}': {ex}")
            continue
        cos = float(np.mean(np.sum(V * np.asarray(E0[idx]), 1)))
        print(f"  tự kiểm document, cách dựng '{name}': cosine trung bình với M0 đã lưu = {cos:.5f}")
        if best is None or cos > best[1]:
            best = (name, cos, fn)
        if cos > 0.9995:
            break
    if best is None or best[1] < 0.999:
        sys.exit("không tái tạo được embedding M0 từ văn bản, dừng để tránh nhúng sai đầu vào")
    build = best[2]
    qcos = float(np.mean(np.sum(enc0([queries[i] for i in qidx]) * np.asarray(Q0[qidx]), 1)))
    print(f"  tự kiểm query: cosine trung bình với M0 đã lưu = {qcos:.5f}")
    if qcos < 0.999:
        sys.exit("query trong ground truth không tái tạo được embedding query M0, dừng lại")
    print(f"  -> dùng cách dựng document '{best[0]}'")
    del m0
    texts = [build(r) for r in raw]

    # ---------- nhúng bằng M1
    qp, pp = pick_prefix(a.model, a.query_prefix, a.passage_prefix)
    print(f"model={a.model}\nquery_prefix={qp!r}  passage_prefix={pp!r}")
    m = SentenceTransformer(a.model, device=a.device)
    if a.max_seq:
        m.max_seq_length = a.max_seq
    dev = str(m.device)
    print(f"device={dev}  max_seq={m.max_seq_length}")
    if dev.startswith("cpu"):
        n = min(200, len(texts))
        s = time.time()
        m.encode([pp + t for t in texts[:n]], batch_size=a.batch, normalize_embeddings=True,
                 convert_to_numpy=True, show_progress_bar=False)
        rate = n / (time.time() - s)
        print(f"tốc độ đo được: {rate:.1f} doc/s  ->  dự kiến "
              f"{(len(texts) + len(queries)) / rate / 60:.0f} phút cho toàn bộ", flush=True)

    E = m.encode([pp + t for t in texts], batch_size=a.batch, normalize_embeddings=True,
                 show_progress_bar=True, convert_to_numpy=True).astype(np.float32)
    Q = m.encode([qp + q for q in queries], batch_size=a.batch, normalize_embeddings=True,
                 show_progress_bar=True, convert_to_numpy=True).astype(np.float32)
    for nm, X in (("corpus", E), ("query", Q)):
        nrm = np.linalg.norm(X, axis=1)
        print(f"{nm}: shape={X.shape} norm[{nrm.min():.5f},{nrm.max():.5f}]")
        assert abs(nrm.mean() - 1.0) < 1e-4, "embedding chưa chuẩn hoá L2"

    # ---------- ground truth đúng trong không gian M1
    print("tính ground truth M1 ...")
    top10 = np.empty((len(Q), 10), dtype=np.int64)
    for s in range(0, len(Q), 64):
        sim = Q[s:s + 64] @ E.T
        ix = np.argpartition(-sim, 10, axis=1)[:, :10]
        ordr = np.argsort(-np.take_along_axis(sim, ix, 1), axis=1)
        top10[s:s + 64] = np.take_along_axis(ix, ordr, 1)
    gt1 = [{"query_id": g.get("query_id", i), "query_text": queries[i],
            "top_5_results": [{"index": int(j)} for j in top10[i, :5]],
            "top_10_results": [{"index": int(j)} for j in top10[i]]} for i, g in enumerate(gt0)]
    ang = [np.degrees(np.arccos(np.clip(E[top10[i, :5]] @ Q[i], -1, 1))).mean() for i in range(len(Q))]
    print(f"angle_mean tới top-5 (M1) = {np.mean(ang):.2f}°")

    np.save(f"{d}/{ds}_{a.tag}_corpus_embeddings.npy", E)
    np.save(f"{d}/{ds}_{a.tag}_query_embeddings.npy", Q)
    json.dump(gt1, open(f"{d}/{ds}_{a.tag}_ground_truth.json", "w"))
    ov = np.mean([len(set(int(r["index"]) for r in gt0[i]["top_5_results"][:5]) &
                      set(top10[i, :5].tolist())) / 5.0 for i in range(len(Q))])
    print(f"\nGT overlap M0 vs M1 (top-5): {100 * ov:.1f}%")
    print(f"đã ghi 3 file với tiền tố '{ds}_{a.tag}' vào {d}/")


if __name__ == "__main__":
    main()
