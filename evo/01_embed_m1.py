#!/usr/bin/env python3
"""
01_embed_m1.py  —  CHẠY TRÊN COLAB (GPU T4), không chạy trên node-dal-02.

Nhúng CodeSearchNet 20k bằng model thứ hai (M1) và tính ground truth trong
không gian M1. Thứ tự dòng khớp tuyệt đối với code_corpus_embeddings.npy của M0.

CẦN UPLOAD LÊN COLAB:
    data/code_corpus_texts.json      (11 MB)
    data/code_ground_truth.json      (1.8 MB — chỉ lấy query_text)

CHẠY:
    !pip -q install sentence-transformers
    !python 01_embed_m1.py --model BAAI/bge-base-en-v1.5   --tag bgebase
    !python 01_embed_m1.py --model intfloat/e5-large-v2    --tag e5large

TẢI VỀ (đặt vào data/ trên node-dal-02):
    code_<tag>_corpus_embeddings.npy
    code_<tag>_query_embeddings.npy
    code_<tag>_ground_truth.json
"""
import argparse, json, os
import numpy as np

# prefix mặc định theo họ model. bge-large gốc KHÔNG dùng instruction (theo
# đúng bản V-Engram), nên bge-base cũng để trống cho nhất quán. e5 thì bắt
# buộc có prefix, bỏ đi là tụt chất lượng rõ rệt.
DEFAULT_PREFIX = {
    "bge":  ("", ""),                      # (query, passage)
    "e5":   ("query: ", "passage: "),
    "gte":  ("", ""),
}


def pick_prefix(model_name, override_q, override_p):
    if override_q is not None or override_p is not None:
        return (override_q or ""), (override_p or "")
    low = model_name.lower()
    for k, v in DEFAULT_PREFIX.items():
        if k in low:
            return v
    return "", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", required=True, help="hậu tố file, vd bgebase")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--max-seq", type=int, default=512)
    ap.add_argument("--query-prefix", default=None)
    ap.add_argument("--passage-prefix", default=None)
    a = ap.parse_args()

    from sentence_transformers import SentenceTransformer

    corpus_path = os.path.join(a.data_dir, "code_corpus_texts.json")
    gt0_path = os.path.join(a.data_dir, "code_ground_truth.json")
    texts = json.load(open(corpus_path))
    gt0 = json.load(open(gt0_path))

    # corpus_texts có thể là list[str] hoặc list[dict]; chấp nhận cả hai
    if texts and isinstance(texts[0], dict):
        key = next(k for k in ("text", "body", "document", "content")
                   if k in texts[0])
        texts = [t[key] for t in texts]
    queries = [g["query_text"] for g in gt0]

    print(f"corpus={len(texts)}  queries={len(queries)}")
    assert len(texts) == 20000, f"corpus phải 20000 dòng, đang là {len(texts)}"
    assert len(queries) == 500, f"query phải 500, đang là {len(queries)}"

    qp, pp = pick_prefix(a.model, a.query_prefix, a.passage_prefix)
    print(f"model={a.model}\nquery_prefix={qp!r}  passage_prefix={pp!r}")

    m = SentenceTransformer(a.model)
    m.max_seq_length = a.max_seq

    E = m.encode([pp + t for t in texts], batch_size=a.batch,
                 normalize_embeddings=True, show_progress_bar=True,
                 convert_to_numpy=True).astype(np.float32)
    Q = m.encode([qp + q for q in queries], batch_size=a.batch,
                 normalize_embeddings=True, show_progress_bar=True,
                 convert_to_numpy=True).astype(np.float32)

    # kiểm tra chuẩn hoá, cùng tiêu chí đã dùng cho M0
    for nm, X in (("corpus", E), ("query", Q)):
        n = np.linalg.norm(X, axis=1)
        print(f"{nm}: shape={X.shape} norm[{n.min():.5f},{n.max():.5f}]")
        assert abs(n.mean() - 1.0) < 1e-4, "embedding chưa chuẩn hoá L2"

    # ground truth ĐÚNG trong không gian M1 (exact inner product, chunked)
    print("tính ground truth M1 ...")
    top10 = np.empty((len(Q), 10), dtype=np.int64)
    for s in range(0, len(Q), 64):
        sim = Q[s:s + 64] @ E.T                       # (b, N)
        idx = np.argpartition(-sim, 10, axis=1)[:, :10]
        ordr = np.argsort(-np.take_along_axis(sim, idx, 1), axis=1)
        top10[s:s + 64] = np.take_along_axis(idx, ordr, 1)

    gt1 = []
    for i, g in enumerate(gt0):
        gt1.append({
            "query_id": g["query_id"],
            "query_text": g["query_text"],
            "top_5_results": [{"index": int(j)} for j in top10[i, :5]],
            "top_10_results": [{"index": int(j)} for j in top10[i]],
        })

    # góc trung bình tới láng giềng thật, để so với 43,38 độ của M0
    ang = []
    for i in range(len(Q)):
        c = np.clip(E[top10[i, :5]] @ Q[i], -1, 1)
        ang.append(np.degrees(np.arccos(c)).mean())
    print(f"angle_mean tới top-5 (M1) = {np.mean(ang):.2f}°   (M0 = 43.38°)")

    d = a.data_dir
    np.save(f"{d}/code_{a.tag}_corpus_embeddings.npy", E)
    np.save(f"{d}/code_{a.tag}_query_embeddings.npy", Q)
    json.dump(gt1, open(f"{d}/code_{a.tag}_ground_truth.json", "w"))

    # bao nhiêu phần ground truth trùng với M0 — cho biết hai model khác nhau
    # tới mức nào, một con số nên báo cáo trong bài
    ov = np.mean([
        len(set(int(r["index"]) for r in gt0[i]["top_5_results"][:5]) &
            set(top10[i, :5].tolist())) / 5.0
        for i in range(len(Q))])
    print(f"\nGT overlap M0 vs M1 (top-5): {100*ov:.1f}%")
    print(f"đã ghi 3 file với tag '{a.tag}' vào {d}/")


if __name__ == "__main__":
    main()
