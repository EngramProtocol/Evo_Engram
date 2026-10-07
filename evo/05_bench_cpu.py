#!/usr/bin/env python3
"""
05_bench_cpu.py  —  CHẠY TRÊN node-dal-02 (CPU), SAU KHI gate 3b đã chạy xong.
Chạy song song với gate khác sẽ tranh CPU và làm sai số đo.

Gate 3 mới đo chi phí mạng (node chạm, ứng viên, payload). Script này đo phần
chi phí phía client mà thầy yêu cầu (CPU/latency) và phần bộ nhớ mô hình:
  - thời gian mã hoá MỘT query (batch 1) bằng M0 và bằng M1
  - thời gian nhân adapter d1 x d0 cho một query
  - thời gian mã hoá R payload thật (document lấy ngẫu nhiên từ corpus) bằng M1,
    tức chi phí bước rerank, với R theo lưới của gate 3b
  - bộ nhớ trọng số của từng mô hình (số tham số x 4 byte, fp32) và thời gian nạp

Chi phí CPU phía client cho mỗi query:
  dual + rerank@R     = query(M0) + query(M1) + payload(R)
  adapter + rerank@R  = query(M1) + adapter   + payload(R)

CHẠY:
    python3 evo/05_bench_cpu.py --m1 BAAI/bge-base-en-v1.5 --tag bgebase
    python3 evo/05_bench_cpu.py --m1 intfloat/e5-large-v2  --tag e5large
"""
import argparse, gc, importlib.util, json, os, time
import numpy as np

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("em", os.path.join(_here, "01_embed_m1.py"))
em = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(em)          # chỉ để dùng lại pick_prefix, không chạy main


def load_model(name):
    """Nạp hai lần: lần đầu có thể phải tải về nên không tính giờ, lần hai mới đo."""
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(name, device="cpu")
    del m
    gc.collect()
    t = time.perf_counter()
    m = SentenceTransformer(name, device="cpu")
    return m, time.perf_counter() - t


def n_params(m):
    return int(sum(p.numel() for p in m.parameters()))


def query_latency(m, prefix, queries):
    enc = lambda q: m.encode([prefix + q], batch_size=1, normalize_embeddings=True,
                             convert_to_numpy=True, show_progress_bar=False)
    for q in queries[:3]:                                    # khởi động, không tính
        enc(q)
    ts = []
    for q in queries:
        t = time.perf_counter()
        enc(q)
        ts.append(time.perf_counter() - t)
    return 1000 * float(np.median(ts)), 1000 * float(np.percentile(ts, 90))


def payload_seconds(m, prefix, texts, R, reps, batch, rng):
    ts = []
    for _ in range(reps):
        idx = rng.choice(len(texts), R, replace=False)
        docs = [prefix + texts[i] for i in idx]
        t = time.perf_counter()
        m.encode(docs, batch_size=min(batch, R), normalize_embeddings=True,
                 convert_to_numpy=True, show_progress_bar=False)
        ts.append(time.perf_counter() - t)
    return float(np.median(ts))


def adapter_us(d1, d0, reps=2000):
    W = (np.random.RandomState(0).randn(d1, d0) / np.sqrt(d1)).astype(np.float32)
    q = np.random.RandomState(1).randn(d1).astype(np.float32)
    ts = []
    for _ in range(reps):
        t = time.perf_counter()
        v = q @ W
        v /= np.linalg.norm(v)
        ts.append(time.perf_counter() - t)
    return 1e6 * float(np.median(ts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--m0", default="BAAI/bge-large-en-v1.5")
    ap.add_argument("--m1", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--nq", type=int, default=30, help="số query đo latency, mỗi lần 1 query")
    ap.add_argument("--R", default="5,10,20,50,100")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--threads", type=int, default=0, help="0 = để torch tự chọn")
    ap.add_argument("--seed", type=int, default=20235956)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    Rs = [int(x) for x in a.R.split(",")]

    import torch
    if a.threads:
        torch.set_num_threads(a.threads)

    texts = json.load(open(os.path.join(a.data_dir, "code_corpus_texts.json")))
    if texts and isinstance(texts[0], dict):
        key = next(k for k in ("text", "body", "document", "content") if k in texts[0])
        texts = [t[key] for t in texts]
    gt0 = json.load(open(os.path.join(a.data_dir, "code_ground_truth.json")))
    queries = [g["query_text"] for g in gt0][:a.nq]

    print(f"tag={a.tag}  cpu_count={os.cpu_count()}  torch_threads={torch.get_num_threads()}  "
          f"{a.nq} query, payload R={Rs}, {a.reps} lần/điểm", flush=True)

    rows = {}
    for role, name in (("M0", a.m0), ("M1", a.m1)):
        qp, pp = em.pick_prefix(name, None, None)
        if role == "M0":
            qp, pp = "", ""          # M0 của V-Engram mã hoá không dùng instruction
        m, load_s = load_model(name)
        d = int(m.get_sentence_embedding_dimension())
        npar = n_params(m)
        q_med, q_p90 = query_latency(m, qp, queries)
        row = dict(model=name, dim=d, params=npar, mem_mib=npar * 4 / 2**20,
                   load_s=load_s, query_ms_median=q_med, query_ms_p90=q_p90,
                   query_prefix=qp, passage_prefix=pp)
        print(f"  {role} {name:28s} dim={d:4d}  tham số={npar/1e6:6.1f} M  "
              f"fp32={row['mem_mib']:6.0f} MiB  nạp={load_s:5.1f} s  "
              f"1 query: {q_med:6.1f} ms (p90 {q_p90:6.1f})", flush=True)
        if role == "M1":
            rng = np.random.RandomState(a.seed)
            pay = {}
            for R in Rs:
                pay[str(R)] = payload_seconds(m, pp, texts, R, a.reps, a.batch, rng)
                print(f"      payload M1 R={R:3d}: {pay[str(R)]:7.2f} s  "
                      f"({R / pay[str(R)]:5.1f} doc/s)", flush=True)
            row["payload_s"] = pay
        rows[role] = row
        del m
        gc.collect()

    d0, d1 = rows["M0"]["dim"], rows["M1"]["dim"]
    ad = adapter_us(d1, d0)
    rows["adapter"] = dict(shape=[d1, d0], mem_mib=d1 * d0 * 4 / 2**20, us_median=ad)
    print(f"  adapter {d1}x{d0}: {rows['adapter']['mem_mib']:.1f} MiB, {ad:.1f} µs mỗi query")

    q0 = rows["M0"]["query_ms_median"] / 1000
    q1 = rows["M1"]["query_ms_median"] / 1000
    pay = rows["M1"]["payload_s"]
    print("\nCPU phía client mỗi query, cùng R (giây):")
    print("     R   dual+rerank   adapter+rerank   dual - adapter")
    for R in Rs:
        du = q0 + q1 + pay[str(R)]
        adr = q1 + ad / 1e6 + pay[str(R)]
        print(f"  {R:4d}   {du:10.2f}   {adr:13.2f}   {du - adr:12.3f}")
    print(f"\nBộ nhớ mô hình client giữ: dual = M0 + M1 = "
          f"{rows['M0']['mem_mib'] + rows['M1']['mem_mib']:.0f} MiB ; "
          f"adapter = M1 + adapter = {rows['M1']['mem_mib'] + rows['adapter']['mem_mib']:.0f} MiB")

    out = a.out or f"bench_{a.tag}.json"
    json.dump(dict(argv=vars(a), cpu_count=os.cpu_count(),
                   torch_threads=int(torch.get_num_threads()), rows=rows),
              open(out, "w"), indent=1)
    print(f"-> {out}")


if __name__ == "__main__":
    main()
