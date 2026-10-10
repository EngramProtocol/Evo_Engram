#!/usr/bin/env python3
"""
04_evo_colab_embed.py  —  CHẠY TRÊN SERVER (CPU) HOẶC COLAB (GPU). Toàn bộ phần nhúng của đợt 4.
Trên server dùng qua evo/run_round4_all.sh (nhúng -> lắp dữ liệu -> chạy đợt 4 trong một lệnh).

Các bước, mỗi bước bỏ qua phần đã có trong --out nên chạy lại được sau khi Colab ngắt:

  docs     Khôi phục docstring cho 100.000 hàm của code100k bằng cách chạy lại ĐÚNG quy tắc dựng corpus của
           V-Engram (prepare/01 và 02) trên parquet CodeSearchNet, rồi so từng chuỗi với code100k_corpus_texts.json.
           Chọn 500 query mới (câu đầu docstring) từ các hàm ở dòng 20.000 đến 99.999 bằng seed cố định.
           Kiểm: tái lập khớp 100%, query không trùng corpus, không trùng 500 query cũ, không trùng nhau.
  corpus   Nhúng corpus code100k bằng M1: bge-base và e5-large chỉ nhúng phần 80k mới (20k đầu đã có trên
           server) cộng 64 dòng đầu để đối chiếu; arctic nhúng toàn bộ 100k (20k đầu dùng luôn cho code 20k).
           Nhúng SciFact bằng arctic. Ghi theo khối 10.000 dòng.
  query    Nhúng query: 500 query mới bằng M0 và ba M1; 500 query cũ của code và SciFact bằng arctic;
           64 document và 32 query bằng M0 để server đối chiếu với embedding M0 đã lưu.
  para     Sinh 5 paraphrase cho 300 query đánh giá của code và SciFact bằng LLM mở (giải mã tham lam,
           tái lập được), lọc theo quy tắc cố định, lưu cả đầu ra thô.
  paraemb  Nhúng paraphrase bằng ba M1.

CÁCH CHẠY TRÊN COLAB (Runtime -> T4 GPU):
    from google.colab import drive; drive.mount('/content/drive')
    !pip -q install sentence-transformers pyarrow
    !python /content/drive/MyDrive/evo_in/04_evo_colab_embed.py \
        --in /content/drive/MyDrive/evo_in --out /content/drive/MyDrive/evo_out
  Thư mục --in cần 4 file lấy từ server: code100k_corpus_texts.json, code100k_ground_truth.json,
  scifact_corpus_texts.json, scifact_ground_truth.json.

THỬ TRÊN MÁY KHÔNG GPU, KHÔNG MẠNG: --fake (model giả, parquet giả, LLM giả) chỉ để kiểm logic.
"""
import argparse, glob, hashlib, json, os, random, re, sys, time

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
import numpy as np

MODELS = {   # tag: (model id, query prefix, passage prefix)
    "m0": ("BAAI/bge-large-en-v1.5", "", ""),
    "bgebase": ("BAAI/bge-base-en-v1.5", "", ""),
    "e5large": ("intfloat/e5-large-v2", "query: ", "passage: "),
    "arctic": ("Snowflake/snowflake-arctic-embed-m-v1.5",
               "Represent this sentence for searching relevant passages: ", ""),
}
M1_TAGS = ["bgebase", "e5large", "arctic"]
PREFIX_DONE = {"bgebase", "e5large"}     # 20k đầu của code100k đã có trên server cho hai tag này
N_OLD = 20000
CHUNK = 10000
FRESH_SEED = 20261010
N_FRESH = 500
N_PARA_Q = 300                            # paraphrase cho 300 query đánh giá
K_PARA = 5
LLM_DEFAULT = "Qwen/Qwen2.5-3B-Instruct"

PROMPTS = {
    "code": ("The following one-sentence description of a Python function is used as a search query in a code "
             "search engine:\n\n\"{q}\"\n\nWrite 5 different ways a developer could phrase a search for the same "
             "function. Keep the meaning and the level of detail; change the wording and the sentence structure. "
             "Do not add details that are not in the original and do not write code. Output exactly 5 lines, one "
             "query per line, without numbering or quotation marks."),
    "scifact": ("The following scientific claim is used as a search query to find research abstracts that support "
                "or refute it:\n\n\"{q}\"\n\nWrite 5 paraphrases of this claim that keep the same scientific "
                "meaning (same entities, same direction of effect, same conditions) but use different wording and "
                "sentence structure. Do not add or remove information. Output exactly 5 lines, one paraphrase per "
                "line, without numbering or quotation marks."),
}


def log(msg, out=None):
    print(msg, flush=True)
    if out:
        with open(os.path.join(out, "log_colab.txt"), "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16]


# ----------------------------------------------------------------- quy tắc dựng corpus của V-Engram (nguyên văn)
def strip_docstring(code_str, doc_str):
    if doc_str and doc_str.strip() and doc_str.strip() in code_str:
        return code_str.replace(doc_str.strip(), ' ', 1), True
    stripped = re.sub(r'("""|\'\'\')(.*?)(\1)', ' ', code_str, count=1, flags=re.DOTALL)
    return stripped, (stripped != code_str)


def first_sentence(doc):
    doc = re.sub(r'\s+', ' ', str(doc)).strip()
    m = re.split(r'(?<=[.!?])\s', doc)
    return (m[0] if m else doc)[:200]


def admit(row):
    """-> (code_wo, doc) nếu hàm được nhận theo quy tắc V-Engram, ngược lại None. Chưa xét trùng."""
    code = row.get('func_code_string') or ''
    doc = row.get('func_documentation_string') or ''
    if len(doc.split()) < 5:
        return None
    code_wo, _ = strip_docstring(code, doc)
    code_wo = re.sub(r'\s+', ' ', code_wo).strip()
    if len(code_wo) < 40:
        return None
    return code_wo, doc


# ----------------------------------------------------------------- nguồn parquet (thật hoặc giả)
class ParquetSource:
    def __init__(self, fake_dir=None):
        self.fake_dir = fake_dir

    def files(self):
        if self.fake_dir:
            return sorted(os.path.basename(p) for p in glob.glob(os.path.join(self.fake_dir, "*.json")))
        from huggingface_hub import list_repo_files
        return list_repo_files('code-search-net/code_search_net', repo_type='dataset')

    def rows(self, fname):
        if self.fake_dir:
            return json.load(open(os.path.join(self.fake_dir, fname)))
        import pandas as pd
        from huggingface_hub import hf_hub_download
        fp = hf_hub_download(repo_id='code-search-net/code_search_net', filename=fname, repo_type='dataset')
        return pd.read_parquet(fp).to_dict('records')


def step_docs(a, out):
    fq = os.path.join(out, "fresh_queries.json")
    fd = os.path.join(out, "code100k_docstrings.json")
    if os.path.exists(fq) and os.path.exists(fd):
        log("[docs] đã có, bỏ qua", out); return
    texts = json.load(open(os.path.join(a.inp, "code100k_corpus_texts.json")))
    gt_old = json.load(open(os.path.join(a.inp, "code100k_ground_truth.json")))
    old_q = [g["query_text"] for g in gt_old]
    N = len(texts)
    log(f"[docs] code100k có {N:,} document, {len(old_q)} query cũ", out)
    src = ParquetSource(a.fake_parquet)
    files = src.files()
    ext = '.json' if a.fake_parquet else '.parquet'
    train_files = [f for f in files if f.endswith(ext) and 'train' in f.lower() and 'python' in f.lower()]
    log(f"[docs] {len(train_files)} file train/python; file đầu theo thứ tự repo: {train_files[0] if train_files else None}",
        out)
    assert train_files, "không thấy parquet train/python"

    # Pha 1, đúng prepare/01: chỉ file đầu tiên theo thứ tự list_repo_files, dừng ở 20.000
    rec_t, rec_d, seen = [], [], set()
    for row in src.rows(train_files[0]):
        r = admit(row)
        if r is None or r[0] in seen:
            continue
        seen.add(r[0]); rec_t.append(r[0]); rec_d.append(r[1])
        if len(rec_t) >= N_OLD:
            break
    n1 = len(rec_t)
    # Pha 2, đúng prepare/02: các file theo thứ tự sắp xếp, loại trùng với mọi chuỗi đã nhận
    for fname in sorted(train_files):
        if len(rec_t) >= N:
            break
        for row in src.rows(fname):
            if len(rec_t) >= N:
                break
            r = admit(row)
            if r is None or r[0] in seen:
                continue
            seen.add(r[0]); rec_t.append(r[0]); rec_d.append(r[1])
    exact = (len(rec_t) == N) and all(x == y for x, y in zip(rec_t, texts))
    n_eq = sum(1 for x, y in zip(rec_t, texts) if x == y)
    log(f"[docs] tái lập: pha 1 = {n1:,}, tổng = {len(rec_t):,}; khớp vị trí {n_eq:,}/{N:,}; KHỚP TOÀN BỘ = {exact}", out)
    docs = rec_d if exact else None
    if not exact:
        # dự phòng: ánh xạ chuỗi -> docstring lần gặp đầu, quét lại toàn bộ theo thứ tự sắp xếp
        log("[docs] không khớp toàn bộ, chuyển sang ánh xạ chuỗi -> docstring", out)
        mp = {}
        for t, d in zip(rec_t, rec_d):
            mp.setdefault(t, d)
        for fname in sorted(train_files):
            for row in src.rows(fname):
                r = admit(row)
                if r is not None:
                    mp.setdefault(r[0], r[1])
        docs = [mp.get(t) for t in texts]
        cov = sum(d is not None for d in docs)
        log(f"[docs] ánh xạ phủ {cov:,}/{N:,} document", out)

    # chọn query mới
    old_set = set(old_q)
    text_set = set(texts)
    cand, seen_q, n_leak, n_old, n_dup = [], set(), 0, 0, 0
    for i in range(N_OLD, N):
        if docs[i] is None:
            continue
        q = first_sentence(docs[i])
        if len(q.split()) < 4:
            continue
        if q in text_set:
            n_leak += 1; continue
        if q in old_set:
            n_old += 1; continue
        if q in seen_q:
            n_dup += 1; continue
        seen_q.add(q); cand.append(i)
    rows = random.Random(FRESH_SEED).sample(cand, N_FRESH)
    fresh = [first_sentence(docs[i]) for i in rows]
    check = dict(exact_rebuild=bool(exact), n_match=int(n_eq), N=N, n_candidates=len(cand), n_leak_removed=n_leak,
                 n_old_removed=n_old, n_dup_removed=n_dup, seed=FRESH_SEED,
                 leak_after=int(sum(q in text_set for q in fresh)), old_after=int(sum(q in old_set for q in fresh)))
    log(f"[docs] ứng viên {len(cand):,} (bỏ {n_leak} trùng corpus, {n_old} trùng query cũ, {n_dup} trùng nhau); "
        f"đã chọn {len(rows)} query, seed {FRESH_SEED}", out)
    log("[docs] 5 query mới mẫu: " + " | ".join(q[:70] for q in fresh[:5]), out)
    json.dump(dict(rows=[int(i) for i in rows], texts=fresh, check=check), open(fq, "w"), ensure_ascii=False, indent=1)
    json.dump(docs, open(fd, "w"), ensure_ascii=False)


# ----------------------------------------------------------------- mô hình nhúng
class FakeST:
    """Mô hình giả cho --fake: vector ổn định theo băm của văn bản, cộng phần chung theo từ để có láng giềng."""
    def __init__(self, name, dim):
        self.name, self.dim = name, dim
        self.max_seq_length = 512
        self.device = "cpu"

    def encode(self, xs, batch_size=32, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False):
        out = np.zeros((len(xs), self.dim), np.float32)
        for i, x in enumerate(xs):
            for w in str(x).lower().split()[:64]:
                h = int(hashlib.md5((self.name + w).encode()).hexdigest()[:8], 16)
                out[i] += np.random.RandomState(h).randn(self.dim).astype(np.float32)
        out /= np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)
        return out


_CACHE = {}


def get_model(a, tag):
    if tag in _CACHE:
        return _CACHE[tag]
    if _CACHE:                    # giữ một model trên GPU mỗi lúc
        _CACHE.clear()
        import gc; gc.collect()
        try:
            import torch; torch.cuda.empty_cache()
        except Exception:
            pass
    name = MODELS[tag][0]
    if a.fake:
        m = FakeST(name, {"m0": 1024, "bgebase": 768, "e5large": 1024, "arctic": 768}[tag])
    else:
        import torch
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(name, device="cuda" if torch.cuda.is_available() else "cpu")
    _CACHE[tag] = m
    return m


def enc(a, tag, texts, kind, bs=None):
    """kind = 'q' hoặc 'p' (query / passage). Trả về float32, chuẩn hoá L2."""
    m = get_model(a, tag)
    pre = MODELS[tag][1] if kind == "q" else MODELS[tag][2]
    X = m.encode([pre + t for t in texts], batch_size=bs or a.batch, normalize_embeddings=True,
                 convert_to_numpy=True, show_progress_bar=False)
    X = np.ascontiguousarray(X, dtype=np.float32)
    nrm = np.linalg.norm(X, axis=1)
    assert np.all(np.abs(nrm - 1) < 1e-3), f"{tag}: chưa chuẩn hoá"
    return X


def step_corpus(a, out):
    texts = json.load(open(os.path.join(a.inp, "code100k_corpus_texts.json")))
    N = len(texts)
    sci = json.load(open(os.path.join(a.inp, "scifact_corpus_texts.json")))
    od = os.path.join(out, "emb"); os.makedirs(od, exist_ok=True)
    for tag in M1_TAGS:
        start = N_OLD if tag in PREFIX_DONE else 0
        head = os.path.join(od, f"code100k_{tag}_head64.npy")
        if tag in PREFIX_DONE and not os.path.exists(head):
            np.save(head, enc(a, tag, texts[:64], "p"))
        have = {}
        for p_ in glob.glob(os.path.join(od, f"code100k_{tag}_rows*_*.npy")):
            s_, e_ = (int(x) for x in os.path.basename(p_)[len(f"code100k_{tag}_rows"):-4].split("_"))
            have[s_] = e_
        s = start
        while s < N:
            if s in have:                     # khối đã có (kể cả khối cỡ khác từ lần chạy trước)
                s = have[s]; continue
            nxt = min([x for x in have if x > s] + [N])
            e = min(nxt, s + CHUNK)
            fn = os.path.join(od, f"code100k_{tag}_rows{s:06d}_{e:06d}.npy")
            t0 = time.time()
            X = enc(a, tag, texts[s:e], "p")
            np.save(fn + ".tmp.npy", X); os.replace(fn + ".tmp.npy", fn)
            rate = (e - s) / (time.time() - t0 + 1e-9)
            log(f"[corpus] {tag} dòng {s:,}-{e:,}: {X.shape} {time.time() - t0:.0f}s ({rate:.1f} doc/s, "
                f"còn {(N - e) / max(rate, 1e-9) / 3600:.1f} giờ cho {tag})", out)
            s = e
    fs = os.path.join(od, "scifact_arctic_corpus.npy")
    if not os.path.exists(fs):
        t0 = time.time()
        np.save(fs, enc(a, "arctic", sci, "p"))
        log(f"[corpus] arctic SciFact {len(sci):,} abstract {time.time() - t0:.0f}s", out)


def step_query(a, out):
    od = os.path.join(out, "q"); os.makedirs(od, exist_ok=True)
    fresh = json.load(open(os.path.join(out, "fresh_queries.json")))["texts"]
    old = [g["query_text"] for g in json.load(open(os.path.join(a.inp, "code100k_ground_truth.json")))]
    sciq = [g["query_text"] for g in json.load(open(os.path.join(a.inp, "scifact_ground_truth.json")))]
    texts = json.load(open(os.path.join(a.inp, "code100k_corpus_texts.json")))
    chk_rows = np.sort(np.random.RandomState(0).choice(len(texts), 64, replace=False))
    jobs = [("fresh", "m0", fresh), ("codeold_chk32", "m0", old[:32]), ("scifact_chk32", "m0", sciq[:32])]
    for tag in M1_TAGS:
        jobs.append(("fresh", tag, fresh))
    jobs += [("codeold", "arctic", old), ("scifact", "arctic", sciq)]
    for tag in PREFIX_DONE:
        jobs.append(("codeold_chk32", tag, old[:32]))
    for nm, tag, xs in jobs:
        fn = os.path.join(od, f"{nm}_{tag}.npy")
        if not os.path.exists(fn):
            np.save(fn, enc(a, tag, xs, "q"))
            log(f"[query] {nm} {tag}: {len(xs)}", out)
    fn = os.path.join(od, "code100k_m0_docchk64.npy")
    if not os.path.exists(fn):
        np.save(fn, enc(a, "m0", [texts[i] for i in chk_rows], "p"))
        json.dump([int(i) for i in chk_rows], open(os.path.join(od, "code100k_m0_docchk64_rows.json"), "w"))
        log("[query] 64 document kiểm M0", out)


# ----------------------------------------------------------------- paraphrase
_STRIP = re.compile(r'^\s*(?:[-*•]|\(?\d+[.)]|[a-eA-E][.)])\s*')


def norm_txt(s):
    return re.sub(r'[^a-z0-9 ]+', '', re.sub(r'\s+', ' ', s.lower())).strip()


def parse_para(raw, orig):
    """Quy tắc lọc cố định: bỏ đánh số và ngoặc kép; bỏ dòng rỗng, trùng câu gốc, trùng nhau, dưới 3 từ,
    hoặc dài hơn 3 lần câu gốc cộng 10 từ."""
    out, seen = [], {norm_txt(orig)}
    lim = 3 * len(orig.split()) + 10
    for ln in raw.split("\n"):
        s = _STRIP.sub("", ln).strip().strip('"“”\'').strip()
        if not s or len(s.split()) < 3 or len(s.split()) > lim:
            continue
        k = norm_txt(s)
        if not k or k in seen:
            continue
        seen.add(k); out.append(s)
    return out


class FakeLLM:
    def generate(self, prompts, sample=False, seed=0):
        res = []
        for p in prompts:
            q = re.search(r'"(.*)"', p, re.S).group(1)
            w = q.split()
            vs = [" ".join(w[i:] + w[:i]) for i in range(1, 7)]
            if sample:
                vs = [v + " please" for v in vs]
            res.append("\n".join(f"{j + 1}. {v}" for j, v in enumerate(vs)))
        return res


class HFLLM:
    def __init__(self, name):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(name)
        self.tok.padding_side = "left"
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        self.dev = "cuda" if torch.cuda.is_available() else "cpu"
        dt = torch.float16 if self.dev == "cuda" else torch.float32
        self.model = AutoModelForCausalLM.from_pretrained(name, torch_dtype=dt).to(self.dev)
        self.model.eval()

    def generate(self, prompts, sample=False, seed=0):
        msgs = [[{"role": "user", "content": p}] for p in prompts]
        txt = [self.tok.apply_chat_template(m, tokenize=False, add_generation_prompt=True) for m in msgs]
        b = self.tok(txt, return_tensors="pt", padding=True).to(self.dev)
        kw = dict(max_new_tokens=400, pad_token_id=self.tok.pad_token_id)
        if sample:
            self.torch.manual_seed(seed)
            kw.update(do_sample=True, temperature=0.8, top_p=0.95)
        else:
            kw.update(do_sample=False)
        with self.torch.no_grad():
            o = self.model.generate(**b, **kw)
        return self.tok.batch_decode(o[:, b["input_ids"].shape[1]:], skip_special_tokens=True)


def step_para(a, out):
    od = os.path.join(out, "para"); os.makedirs(od, exist_ok=True)
    todo = [ds for ds in ("code", "scifact") if not os.path.exists(os.path.join(od, f"{ds}_paraphrases.json"))]
    if not todo:
        log("[para] đã có, bỏ qua", out); return
    llm = FakeLLM() if a.fake else HFLLM(a.llm)
    src = {"code": "code100k_ground_truth.json", "scifact": "scifact_ground_truth.json"}
    for ds in todo:
        qs = [g["query_text"] for g in json.load(open(os.path.join(a.inp, src[ds])))][:N_PARA_Q]
        raws, paras = [], []
        fpart = os.path.join(od, f"{ds}_paraphrases_partial.json")
        if os.path.exists(fpart):                 # tiếp tục sau khi bị ngắt
            pp = json.load(open(fpart))
            raws, paras = pp["raws"], pp["paras"]
            log(f"[para] {ds}: tiếp tục từ {len(paras)}/{len(qs)}", out)
        t0 = time.time()
        for s in range(len(paras), len(qs), a.llm_batch):
            batch = qs[s:s + a.llm_batch]
            outs = llm.generate([PROMPTS[ds].format(q=q) for q in batch])
            for j, (q, r) in enumerate(zip(batch, outs)):
                ps = parse_para(r, q)
                extra = ""
                if len(ps) < K_PARA:       # thiếu thì sinh thêm một lần, lấy mẫu có seed cố định
                    extra = llm.generate([PROMPTS[ds].format(q=q)], sample=True, seed=1000 + s + j)[0]
                    for p in parse_para(extra, q):
                        if norm_txt(p) not in {norm_txt(x) for x in ps}:
                            ps.append(p)
                raws.append({"query": q, "raw": r, "raw_extra": extra})
                paras.append(ps[:K_PARA])
            json.dump(dict(raws=raws, paras=paras), open(fpart, "w"), ensure_ascii=False)
            log(f"[para] {ds} {min(len(qs), s + a.llm_batch)}/{len(qs)}  {time.time() - t0:.0f}s", out)
        nk = [len(p) for p in paras]
        log(f"[para] {ds}: trung bình {np.mean(nk):.2f} paraphrase/query, đủ 5: {sum(k == K_PARA for k in nk)}/{len(nk)}",
            out)
        log(f"[para] mẫu: {qs[0]!r} -> {paras[0][:2]}", out)
        json.dump(dict(llm=a.llm if not a.fake else "fake", k=K_PARA, prompt=PROMPTS[ds], queries=qs,
                       paraphrases=paras), open(os.path.join(od, f"{ds}_paraphrases.json"), "w"),
                  ensure_ascii=False, indent=1)
        json.dump(raws, open(os.path.join(od, f"{ds}_paraphrases_raw.json"), "w"), ensure_ascii=False, indent=1)
    del llm
    try:
        import torch; torch.cuda.empty_cache()
    except Exception:
        pass


def step_paraemb(a, out):
    od = os.path.join(out, "para")
    for ds in ("code", "scifact"):
        P = json.load(open(os.path.join(od, f"{ds}_paraphrases.json")))["paraphrases"]
        flat = [(i, j, p) for i, ps in enumerate(P) for j, p in enumerate(ps)]
        mask = np.zeros((len(P), K_PARA), dtype=bool)
        for i, j, _ in flat:
            mask[i, j] = True
        np.save(os.path.join(od, f"{ds}_para_mask.npy"), mask)
        for tag in M1_TAGS:
            fn = os.path.join(od, f"{ds}_{tag}_para.npy")
            if os.path.exists(fn):
                continue
            X = enc(a, tag, [p for _, _, p in flat], "q")
            Y = np.zeros((len(P), K_PARA, X.shape[1]), np.float32)
            for (i, j, _), x in zip(flat, X):
                Y[i, j] = x
            np.save(fn, Y)
            log(f"[paraemb] {ds} {tag}: {len(flat)} paraphrase", out)


def write_manifest(out):
    rows = []
    for p in sorted(glob.glob(os.path.join(out, "**", "*"), recursive=True)):
        if os.path.isfile(p) and not p.endswith((".tmp.npy",)) and os.path.basename(p) != "MANIFEST_colab.txt":
            rows.append(f"{sha(p)}  {os.path.getsize(p):>12}  {os.path.relpath(p, out)}")
    open(os.path.join(out, "MANIFEST_colab.txt"), "w").write("\n".join(rows) + "\n")
    log(f"[xong] MANIFEST_colab.txt: {len(rows)} file", out)


def main():
    global N_OLD, CHUNK, N_FRESH, N_PARA_Q
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--steps", default="docs,query,para,paraemb,corpus",
                    help="bước rẻ chạy trước để lỗi (nếu có) lộ sớm; nhúng corpus nặng nhất để cuối")
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--llm", default=LLM_DEFAULT)
    ap.add_argument("--llm-batch", type=int, default=16)
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--fake-parquet", default=None)
    ap.add_argument("--n-old", type=int, default=N_OLD, help="chỉ đổi khi thử với dữ liệu giả")
    ap.add_argument("--chunk", type=int, default=0, help="0 = tự chọn: 10.000 dòng trên GPU, 2.000 trên CPU")
    ap.add_argument("--n-fresh", type=int, default=N_FRESH)
    ap.add_argument("--n-para", type=int, default=N_PARA_Q)
    a = ap.parse_args()
    N_OLD, N_FRESH, N_PARA_Q = a.n_old, a.n_fresh, a.n_para
    try:
        import torch
        _gpu = torch.cuda.is_available()
    except Exception:
        _gpu = False
    CHUNK = a.chunk if a.chunk > 0 else (10000 if _gpu else 2000)
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    if not a.fake:
        import torch
        log(f"thiết bị: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else f'CPU, {torch.get_num_threads()} luồng'}"
            f"  khối corpus = {CHUNK} dòng", a.out)
    for st in a.steps.split(","):
        log(f"===== bước {st}  ({time.time() - t0:.0f}s)", a.out)
        {"docs": step_docs, "corpus": step_corpus, "query": step_query, "para": step_para,
         "paraemb": step_paraemb}[st](a, a.out)
    write_manifest(a.out)
    log(f"XONG TOÀN BỘ ({time.time() - t0:.0f}s). Tải thư mục {a.out} về máy rồi scp lên server.", a.out)


if __name__ == "__main__":
    main()
