#!/usr/bin/env python3
"""
06_probe_lazy.py  —  CHẠY TRÊN node-dal-02 (CPU). Lazy migration theo phân phối truy cập Zipf (mục 6
của nhận xét).

Ý tưởng: bước rerank đã phải tải R payload và nhúng lại bằng M1. Đó đúng là phần việc cần để tạo
record native E1. Lazy migration công bố luôn các record này: mỗi document E0 nằm trong pool rerank
được nhúng lại (vốn đã phải làm) rồi chuyển sang E1. Document được truy cập nhiều sẽ migrate trước.

Thiết lập, giữ đúng 04b:
  - mẫu S (10%) đã nhúng lại để học adapter và đã công bố ở E1 từ đầu (f ban đầu = |S|/N)
  - phía E0: A_split_norm học trên S; phía E1: chỉ mục native, khoá SRP trừ trung bình
    (biến thể c hay cq chọn trên validation như 04b)
  - gộp: PROP và PROB (me_common.py)
Dòng truy vấn: 300 query đánh giá chia ngẫu nhiên theo seed thành 200 query "nóng" (sinh dòng truy vấn)
và 100 query giữ riêng (không bao giờ được hỏi, chỉ đo ở các mốc). Độ phổ biến Zipf với số mũ s trên
200 query nóng theo thứ hạng ngẫu nhiên; s = 0 là phân phối đều (đối chứng).
Mỗi bước: gộp hai danh sách, final = top-5 của danh sách gộp; rerank: pool = R đầu danh sách, record
E0 trong pool được tải và nhúng lại (cosine M1 thật), record E1 dùng luôn cosine ADC (không tải),
top-5 theo các điểm đó.
Chính sách:
  static  không migrate thêm (vẫn phải tải và nhúng R payload mỗi lần rerank, rồi bỏ đi)
  lazy    công bố mọi record E0 vừa nhúng lại trong pool sang E1
  bg      migrate nền ngẫu nhiên, cùng tổng số record mà lazy đã công bố (cùng chi phí nhúng lại)
  lazybg  lazy cộng migrate nền ngẫu nhiên với tốc độ bằng tốc độ của lazy (thiết kế dùng thật: lazy cho
          document nóng, nền để hoàn tất)
  bg2     chỉ migrate nền, cùng tổng số record với lazybg
Đo theo cửa sổ: final, rerank, số payload phải tải, số record mới, tỉ lệ đã migrate, số node, ứng viên
chuyển, và tách truy vấn lặp lại với truy vấn lần đầu. Ở các mốc: chất lượng trên 100 query giữ riêng.

Tự kiểm: ở t = 0 (M = S), trên cả 300 query đánh giá, hai nhánh ADc*_PROP và ADc*_PROB phải trùng
từng số với 04b (probeG_...json) ở f = |S|/N.

Bổ sung đợt 4 (mặc định giữ nguyên hành vi đợt 3b, tự kiểm với probeL_..._ku.json của 3b nếu có):
  --reindex cap:delay,...   trust model "chỉ authorized re-indexer được công bố record E1". Client chỉ gửi ID
                            document E0 vừa tải trong pool (gợi ý); re-indexer xếp hàng FIFO, mỗi truy vấn xử lý
                            tối đa cap record có gợi ý cũ hơn delay truy vấn, tự tải và nhúng lại rồi công bố.
                            inf:0 trùng lazy đợt 3b. Với mỗi cấu hình khác inf:0 chạy lazy và bg cùng số record.
  --workloads verbatim,para para: dòng truy vấn chọn intent theo Zipf như cũ, rồi bốc ngẫu nhiên một trong các
                            paraphrase của query đó (không dùng câu gốc). Ground truth của mỗi lượt là top-5 M1
                            của chính câu paraphrase. Query giữ riêng vẫn là câu gốc.

CHẠY: python3 evo/06_probe_lazy.py --tag bgebase --seed 20235956
"""
import argparse, collections, importlib.util, json, os, random, time
import numpy as np
import me_common as mc

np.seterr(invalid='ignore', divide='ignore')
q3, pb = mc.q3, mc.pb
log, l2norm = mc.log, mc.l2norm

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("m4b", os.path.join(_here, "04b_probe_multiepoch2.py"))
m4b = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m4b)


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
    ap.add_argument("--cal-top", type=int, default=30)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--stream", type=int, default=3000, help="số truy vấn trong dòng")
    ap.add_argument("--zipf", default="1.0,0", help="số mũ Zipf, 0 = đều")
    ap.add_argument("--n-heldout", type=int, default=100)
    ap.add_argument("--R", type=int, default=20, help="kích thước pool rerank")
    ap.add_argument("--window", type=int, default=150)
    ap.add_argument("--checkpoints", default="0,150,300,600,1000,1500,2000,3000")
    ap.add_argument("--fusions", default="PROP,PROB",
                    help="thêm PROBA = PROB nhưng chỉ tải và nhúng lại record E0 có xác suất thuộc top-5 >= --eps "
                         "(chạy thử cho thấy cắt quá tay, không dùng mặc định)")
    ap.add_argument("--eps", type=float, default=0.005)
    ap.add_argument("--policies", default="static,lazy,bg,lazybg,bg2")
    ap.add_argument("--e1-key", default="u", choices=["u", "auto", "c", "cq"],
                    help="u = khoá SRP như chỉ mục native gốc (mặc định từ đợt 3b, vì trừ trung bình làm recall sụt);"
                         " auto = chọn c/cq trên validation như 04b")
    ap.add_argument("--rerank-check", default="5,10,20,50,100", help="các R của 04b, chỉ để tự kiểm")
    ap.add_argument("--reindex", default="inf:0", help="danh sách cap:delay của re-indexer; inf:0 = lazy đợt 3b")
    ap.add_argument("--workloads", default="verbatim", help="verbatim, para (cách nhau dấu phẩy)")
    ap.add_argument("--check-3b", default="auto", help="file probeL đợt 3b để tự kiểm; auto = tên mặc định; none = bỏ")
    ap.add_argument("--trace-runs", default="", help="khoá run cần ghi vết từng truy vấn cho 08_sim_evo, vd z1|PROB|lazy")
    ap.add_argument("--trace-out", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    t0 = time.time()
    D, ds = a.data_dir, a.dataset
    T = a.probes
    fusions = a.fusions.split(",")
    policies = a.policies.split(",")
    zipfs = [float(z) for z in a.zipf.split(",")]
    cps = sorted({int(c) for c in a.checkpoints.split(",") if int(c) <= a.stream} | {0, a.stream})

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
    gt5_all = [np.array([int(r["index"]) for r in g["top_5_results"][:5]]) for g in gt1]

    rnd = random.Random(a.seed)
    nid = np.array([rnd.getrandbits(63) for _ in range(a.nodes)], dtype=np.int64)
    P0 = pb.gen_proj(a.seed, d0, a.tables)
    P1 = pb.gen_proj(a.seed, d1, a.tables)
    perm = np.random.RandomState(a.seed).permutation(N)
    nS = max(a.tables * 20, int(round(a.frac * N)))
    S = perm[:nS]
    log("=" * 78)
    log(f"[06] dataset={ds} tag={a.tag} seed={a.seed}  N={N}  S={nS} ({nS / N:.1%})  dòng={a.stream} "
        f"zipf={zipfs}  R={a.R}  gộp={fusions}  chính sách={policies}")

    # ---------------- adapter, PQ E1, chỉ mục (giống 04b)
    Wr, _, _ = q3.fit_ridge_cv(E1[S], E0[S], a.seed, (1e-3, 1e-2, 1e-1, 1.0, 10.0))
    Wf, _ = pb.fit_bridge(E0[S], E1[S], "ridge", a.seed)
    WfT = np.ascontiguousarray(Wf.T)
    m0 = cb0.shape[0]
    C0 = cb0[np.arange(m0)[None, :], cd0].reshape(N, d0).astype(np.float32)
    n_i = np.linalg.norm(C0 @ Wf, axis=1)
    cb1 = pb.pq_train(E1[S], m1, a.seed)
    cd1 = pb.pq_encode(E1, cb1)
    anchors0 = pb.build_index(E0, P0, nid)
    mu_d = E1[S].mean(0).astype(np.float32)
    mu_q = Q1[trq].mean(0).astype(np.float32)
    anchorsK = (pb.build_index(E1, P1, nid) if a.e1_key == "u" else pb.build_index(E1 - mu_d, P1, nid))

    Xcf, _ = mc.crossfit_adapter_x(E0, E1, C0, cb0, cd0, Q1[trq], S, S, a.folds, a.seed)
    Ycf = mc.e1_scores(Q1[trq], cb1, cd1, S)
    ols_ad = mc.ols_top(list(Xcf), list(Ycf), a.cal_top)
    sig1 = mc.sigma_e1(Q1[trq], E1, cb1, cd1, S, a.cal_top)
    cal = dict(cal_a=None, cal_b=None, ols=ols_ad, sig1=sig1)
    log(f"hiệu chỉnh cross-fit: a={ols_ad['a']:.3f} b={ols_ad['b']:+.3f} sigma0={ols_ad['sig']:.4f} "
        f"r={ols_ad['r']:.3f}; sigma1={sig1:.4f}")

    def e1_side_vec(Qv, center):
        q1 = l2norm(Qv)
        NK = mc.route_keys(q1 - center, P1, nid, a.k_query, T, a.cbits)
        return [mc.Side2(NK[i], anchorsK, a.nodes,
                         (lambda r, i=i: (-mc.adc_l2(q1[i], cb1, cd1[r]), mc.adc_ip(q1[i], cb1, cd1[r]))))
                for i in range(len(Qv))]

    def e1_side(qidx, center):
        return e1_side_vec(Q1[qidx], center)

    # ---------------- chọn biến thể khoá E1 trên validation (giống 04b: E1ONLY ở f = 1)
    if a.e1_key == "auto":
        allon = np.ones(N, dtype=bool)
        sc = {}
        for nm, cen in (("c", mu_d), ("cq", mu_q)):
            sv = e1_side(trq, cen)
            sc[nm] = 100 * np.mean([len(set(sv[i].ranked(allon, a.kappa, 5)[1][:5].tolist())
                                        & set(gt5_all[trq[i]].tolist())) / 5.0 for i in range(len(trq))])
        key = "c" if sc["c"] >= sc["cq"] else "cq"
        log(f"validation E1ONLY ở f = 1: c={sc['c']:.1f} cq={sc['cq']:.1f} -> khoá E1: {key}")
    else:
        key, sc = a.e1_key, {}
    center = {"c": mu_d, "cq": mu_q, "u": np.zeros_like(mu_d)}[key]
    sideK = {"c": "C", "cq": "Q", "u": "U"}[key]

    # ---------------- phía E0 (adapter) và phía E1 cho 300 query đánh giá
    def a_side_vec(Qv):
        qr0 = l2norm(Qv @ Wr)
        qk = l2norm(Qv @ WfT); qkn = np.linalg.norm(Qv @ WfT, axis=1)
        NA = mc.route_keys(qr0, P0, nid, a.k_query, T, a.cbits)

        def fa(i):
            def f(r):
                k = mc.adc_ip(qk[i], cb0, cd0[r]) / n_i[r]
                return k, k * qkn[i]
            return f
        return [mc.Side2(NA[i], anchors0, a.nodes, fa(i)) for i in range(len(Qv))]
    sides_A = a_side_vec(Q1[ev])
    sides_K = e1_side(ev, center)
    log(f"định tuyến và chấm điểm xong ({time.time() - t0:.0f}s)")

    # ---------------- tự kiểm với 04b ở t = 0 (M = S), 300 query, cách đo của 04b
    Rs_chk = [int(x) for x in a.rerank_check.split(",")]
    inE1_0 = np.zeros(N, dtype=bool); inE1_0[S] = True
    st0 = dict(nM=nS, inE1=inE1_0, act=(~inE1_0, inE1_0), has=(True, True),
               load={"E0": np.bincount(anchors0[:, ~inE1_0].ravel(), minlength=a.nodes),
                     sideK: np.bincount(anchorsK[:, inE1_0].ravel(), minlength=a.nodes)},
               share1=nS / N, share0=1.0 - nS / N, T=T, T0=T, T1=T, Kstar=sideK)
    akey = "" if key == "u" else key
    arms_chk = [f"AD{akey}_{k}" for k in fusions if f"AD{akey}_{k}" in m4b.SPEC]
    res0, _ = m4b.evaluate(arms_chk, {"A": sides_A, sideK: sides_K}, [gt5_all[i] for i in ev], Q1[ev], st0,
                           {"AD": cal}, a.kappa, Rs_chk, E1)
    pre = "" if ds == "code" else f"{ds}_"
    fG = f"probeG_{pre}{a.tag}_s{a.seed}.json"
    check = None
    if os.path.exists(fG):
        G = json.load(open(fG))
        fS = next((k for k in G["results"] if int(round(float(k) * N)) == nS), None)
        if fS is not None and (key == "u" or G.get("Kstar") == key):
            bad, n = 0, 0
            for m in arms_chk:
                new, o = res0[m], G["results"][fS][m]
                for kk in ("reach_r5", "final_r5", "nodes", "cand", "moved", "e0_share_top5"):
                    n += 1; bad += abs(new[kk] - o[kk]) > 1e-9
                for R in new["rerank"]:
                    n += 1; bad += abs(new["rerank"][R] - o["rerank"][R]) > 1e-9
            check = dict(n=n, bad=int(bad))
            log(f">>> t = 0 so với 04b ({fG}, f = {fS}, nhánh {arms_chk}): {n} giá trị, "
                f"{'KHỚP' if bad == 0 else f'{bad} LỆCH'}")
        else:
            log(f">>> không tự kiểm được với {fG} (khoá E1 của 04b: {G.get('Kstar')}, ở đây: {key})")
    else:
        log(f">>> chưa có {fG}, bỏ qua tự kiểm với 04b")

    # ---------------- dòng truy vấn
    rng = np.random.RandomState(a.seed + 41)
    order = rng.permutation(len(ev))
    pool_q = order[:len(ev) - a.n_heldout]
    held_q = order[len(ev) - a.n_heldout:]
    bg_order = perm[nS:]
    Rk = a.R

    def one_query(qi, inE1, load0, loadK, fus, var=None):
        """-> (final, rerank, danh sách record E0 đã tải, nodes, moved). var = chỉ số paraphrase (workload para)."""
        if var is None:
            sA, sK, gq, q1v = sides_A[qi], sides_K[qi], gt5_all[ev[qi]], Q1[ev[qi]]
        else:
            sA, sK, gq, q1v = VA[var], VK[var], VG[var], VQ[var]
        act0, act1 = ~inE1, inE1
        has0, has1 = bool(act0.any()), bool(act1.any())
        share1 = float(inE1.mean())
        _, l0, x0 = sA.ranked(act0, a.kappa, Rk)
        _, l1, y1 = sK.ranked(act1, a.kappa, Rk)
        if fus == "PROBA":
            if len(l0) and len(l1):
                lst, pp = mc.prob_fuse_p(l0, x0, l1, y1, Rk, cal)
            else:
                lst = np.asarray((l0 if len(l0) else l1)[:Rk], dtype=np.int64)
                pp = np.ones(len(lst))
        else:
            lst = mc.fuse(fus, l0, x0, l1, y1, Rk, 1.0 - share1, share1, cal)
        g = set(np.asarray(gq).tolist())
        fin = len(set(lst[:5].tolist()) & g) / 5.0
        pool = lst[:Rk]
        e0m = ~inE1[pool]
        if fus == "PROBA":
            e0m = e0m & (pp[:len(pool)] >= a.eps)        # chỉ tải record E0 còn khả năng vào top-5
            keep = e0m | inE1[pool]
        else:
            keep = np.ones(len(pool), dtype=bool)
        sc = np.full(len(pool), -np.inf, dtype=np.float64)
        if e0m.any():
            sc[e0m] = E1[pool[e0m]] @ q1v
        e1m = inE1[pool]
        if e1m.any():
            ymap = dict(zip(l1.tolist(), y1.tolist()))
            sc[e1m] = [ymap[d] for d in pool[e1m].tolist()]
        ordr = np.argsort(-sc, kind="stable")
        ordr = np.concatenate([ordr[keep[ordr]], np.flatnonzero(~keep)])   # record không tải xếp sau, theo thứ tự gộp
        top = pool[ordr[:5]]
        rr = len(set(top.tolist()) & g) / 5.0
        tA, tK = sA.touched(), sK.touched()
        nodes = (len(tA) if has0 else 0) + (len(tK) if has1 else 0)
        moved = ((np.minimum(load0[tA], a.kappa).sum() if has0 else 0)
                 + (np.minimum(loadK[tK], a.kappa).sum() if has1 else 0))
        return fin, rr, pool[e0m], nodes, int(moved)

    def migrate(docs, inE1, load0, loadK):
        docs = np.asarray([d for d in np.unique(docs) if not inE1[d]], dtype=np.int64)
        if len(docs):
            inE1[docs] = True
            np.subtract.at(load0, anchors0[:, docs].ravel(), 1)
            np.add.at(loadK, anchorsK[:, docs].ravel(), 1)
        return docs

    def simulate(stream, fus, policy, bg_rate=0.0, cap=None, delay=0, svar=None, trace=None):
        inE1 = np.zeros(N, dtype=bool); inE1[S] = True
        load0 = np.bincount(anchors0[:, ~inE1].ravel(), minlength=a.nodes)
        loadK = np.bincount(anchorsK[:, inE1].ravel(), minlength=a.nodes)
        seen = np.zeros(len(ev), dtype=bool)
        seen_v = set()
        ptr, accb = 0, 0.0
        direct = (cap is None and delay == 0)            # đúng lazy đợt 3b
        queue, queued, accc = collections.deque(), np.zeros(N, dtype=bool), 0.0
        rec = {k: [] for k in ("final", "rr", "fetch", "new", "nodes", "moved", "f", "rep", "gtE1", "rep_exact",
                               "qlen")}
        snaps = {}
        for t in range(len(stream) + 1):
            if t in cps:
                hs = [one_query(h, inE1, load0, loadK, fus) for h in held_q]
                snaps[str(t)] = dict(final=100 * np.mean([h[0] for h in hs]), rr=100 * np.mean([h[1] for h in hs]),
                                     f=float(inE1.mean()))
            if t == len(stream):
                break
            qi = int(stream[t])
            var = None if svar is None else (int(svar[t]) if svar[t] >= 0 else None)
            gq = gt5_all[ev[qi]] if var is None else VG[var]
            gtE1 = float(inE1[np.asarray(gq)].mean())
            h0, h1 = bool((~inE1).any()), bool(inE1.any())
            fin, rr, fetched, nodes, moved = one_query(qi, inE1, load0, loadK, fus, var)
            new = 0
            migs = []
            if policy in ("lazy", "lazybg"):
                if direct:
                    mg = migrate(fetched, inE1, load0, loadK); new += len(mg); migs.append(mg)
                else:
                    for d in np.unique(fetched).tolist():
                        if not inE1[d] and not queued[d]:
                            queue.append((t, d)); queued[d] = True
                    if cap is None:
                        budget = len(queue)
                    else:
                        accc += cap
                        budget = int(accc); accc -= budget
                    take = []
                    while queue and len(take) < budget and queue[0][0] <= t - delay:
                        take.append(queue.popleft()[1])
                    for d in take:
                        queued[d] = False
                    mg = migrate(take, inE1, load0, loadK); new += len(mg); migs.append(mg)
            if policy in ("bg", "bg2", "lazybg"):
                accb += bg_rate
                k = int(accb); accb -= k
                take = []
                while len(take) < k and ptr < len(bg_order):
                    d = int(bg_order[ptr]); ptr += 1
                    if not inE1[d]:
                        take.append(d)
                mg = migrate(take, inE1, load0, loadK); new += len(mg); migs.append(mg)
            vkey = (qi, var)
            for kk, v in (("final", fin), ("rr", rr), ("fetch", len(fetched)), ("new", new), ("nodes", nodes),
                          ("moved", moved), ("f", float(inE1.mean())), ("rep", bool(seen[qi])), ("gtE1", gtE1),
                          ("rep_exact", vkey in seen_v), ("qlen", len(queue))):
                rec[kk].append(v)
            seen[qi] = True
            seen_v.add(vkey)
            if trace is not None:
                trace.append(dict(q=int(ev[qi]), qi=int(qi), v=(-1 if var is None else int(var)), h0=h0, h1=h1,
                                  fe=[int(x) for x in np.asarray(fetched).tolist()],
                                  mi=[int(x) for m_ in migs for x in np.asarray(m_).tolist()], mv=int(moved)))
        return rec, snaps

    def windows(rec, W):
        out = []
        n = len(rec["final"])
        for s in range(0, n, W):
            e = min(n, s + W)
            sl = slice(s, e)
            rep = np.asarray(rec["rep"][sl], dtype=bool)
            fin = np.asarray(rec["final"][sl]); rr = np.asarray(rec["rr"][sl])
            out.append(dict(t_end=e, f=rec["f"][e - 1], final=100 * fin.mean(), rr=100 * rr.mean(),
                            final_rep=(100 * fin[rep].mean()) if rep.any() else float("nan"),
                            rr_rep=(100 * rr[rep].mean()) if rep.any() else float("nan"),
                            final_new=(100 * fin[~rep].mean()) if (~rep).any() else float("nan"),
                            rr_new=(100 * rr[~rep].mean()) if (~rep).any() else float("nan"),
                            n_rep=int(rep.sum()), fetch=float(np.mean(rec["fetch"][sl])),
                            new=float(np.mean(rec["new"][sl])), nodes=float(np.mean(rec["nodes"][sl])),
                            moved=float(np.mean(rec["moved"][sl])), gtE1=100 * float(np.mean(rec["gtE1"][sl]))))
        return out

    def totals(rec):
        rep = np.asarray(rec["rep"], dtype=bool); rx = np.asarray(rec["rep_exact"], dtype=bool)
        fin = np.asarray(rec["final"]); rr = np.asarray(rec["rr"])
        sub = lambda m, x: (100 * float(x[m].mean())) if m.any() else float("nan")
        return dict(final=100 * float(np.mean(rec["final"])), rr=100 * float(np.mean(rec["rr"])),
                    fetch=float(np.mean(rec["fetch"])), new=float(np.mean(rec["new"])),
                    nodes=float(np.mean(rec["nodes"])), moved=float(np.mean(rec["moved"])),
                    f_end=float(rec["f"][-1]),
                    rep_share=100 * float(rep.mean()), rep_exact_share=100 * float(rx.mean()),
                    final_first=sub(~rep, fin), rr_first=sub(~rep, rr),
                    final_rep_exact=sub(rx, fin), rr_rep_exact=sub(rx, rr),
                    final_rep_newvar=sub(rep & ~rx, fin), rr_rep_newvar=sub(rep & ~rx, rr),
                    qlen_mean=float(np.mean(rec["qlen"])), qlen_end=int(rec["qlen"][-1]))

    # ---------------- paraphrase (workload para)
    workloads = a.workloads.split(",")
    VA = VK = VG = VQ = None
    var_of = {}
    rows_v = []
    para_info = None
    if "para" in workloads:
        Pe = np.load(f"{D}/{ds}_{a.tag}_para_embeddings.npy").astype(np.float32)
        Pm = np.load(f"{D}/{ds}_para_mask.npy")
        PG = json.load(open(f"{D}/{ds}_{a.tag}_para_ground_truth.json"))
        for qi in range(len(ev)):
            q = int(ev[qi])
            if q >= len(Pm):
                continue
            for j in np.flatnonzero(Pm[q]).tolist():
                var_of.setdefault(qi, []).append(len(rows_v))
                rows_v.append((q, j))
        VQ = np.stack([Pe[q, j] for q, j in rows_v]).astype(np.float32)
        VG = [np.asarray(PG[q][j], dtype=np.int64) for q, j in rows_v]
        VA = a_side_vec(VQ)
        VK = e1_side_vec(VQ, center)
        ov = [len(set(VG[v].tolist()) & set(gt5_all[q].tolist())) / 5.0 for v, (q, j) in enumerate(rows_v)]
        para_info = dict(n_var=len(rows_v), n_query_with_var=len(var_of), gt_overlap_with_orig=100 * float(np.mean(ov)))
        log(f"paraphrase: {len(rows_v)} biến thể cho {len(var_of)}/{len(ev)} query; GT top-5 trùng câu gốc "
            f"{para_info['gt_overlap_with_orig']:.1f}%  ({time.time() - t0:.0f}s)")

    specs = []
    for sp in a.reindex.split(","):
        c, d = sp.split(":")
        specs.append((None if c == "inf" else float(c), int(d), sp))

    out = dict(argv=vars(a), n_sample=int(nS), N=int(N), e1_key=key, e1_key_val=sc, cal=ols_ad, sig1=sig1,
               check_04b=check, t0=res0, para_info=para_info, runs={})
    trace_keys = set(x for x in a.trace_runs.split(",") if x)
    traces = {}
    for wl in workloads:
        for z in zipfs:
            ranks = np.random.RandomState(a.seed + 43).permutation(len(pool_q))
            p = 1.0 / (ranks + 1.0) ** z
            p /= p.sum()
            stream = pool_q[np.random.RandomState(a.seed + 47 + int(1000 * z)).choice(len(pool_q), size=a.stream, p=p)]
            svar = None
            if wl == "para":
                rv = np.random.RandomState(a.seed + 53 + int(1000 * z))
                svar = np.array([(var_of[int(qi)][rv.randint(len(var_of[int(qi)]))] if int(qi) in var_of else -1)
                                 for qi in stream], dtype=np.int64)
            top10 = float(np.sort(p)[::-1][:10].sum())
            ndist = int(len(np.unique(stream)))
            log(f"\n=== [{wl}] Zipf s = {z:g}: 10 query phổ biến nhất chiếm {100 * top10:.0f}% lưu lượng; "
                f"{ndist}/{len(pool_q)} query nóng xuất hiện trong dòng")
            for fus in fusions:
                for cap, dly, spn in specs:
                    default = (cap is None and dly == 0)
                    pols = policies if default else [x for x in ("lazy", "bg") if x in policies]
                    done = {}
                    for pol in pols:
                        rate = 0.0
                        need = {"bg": "lazy", "lazybg": "lazy", "bg2": "lazybg"}.get(pol)
                        if need is not None:
                            if need not in done:
                                log(f"  ({pol} cần chạy {need} trước) bỏ qua"); continue
                            rate = (done[need][0]["f"][-1] * N - nS) / a.stream   # bg/bg2: cùng tổng số record;
                                                                                  # lazybg: nền bằng tốc độ của lazy
                        k = f"z{z:g}|{fus}|{pol}"
                        if wl != "verbatim":
                            k = f"{wl}|" + k
                        if not default:
                            k += f"|r{spn}"
                        tr = [] if k in trace_keys else None
                        rec, snaps = simulate(stream, fus, pol, rate, cap=cap, delay=dly, svar=svar, trace=tr)
                        if tr is not None:
                            traces[k] = tr
                        done[pol] = (rec, snaps)
                        tt = totals(rec)
                        tt["distinct_queries"] = ndist
                        tt["bg_rate"] = rate
                        w = windows(rec, a.window)
                        out["runs"][k] = dict(zipf=z, fusion=fus, policy=pol, workload=wl, reindex=spn, totals=tt,
                                              windows=w, snapshots=snaps, top10_share=top10)
                        log(f"  {fus:4s} {pol:6s} r{spn:7s} final={tt['final']:5.1f} rerank={tt['rr']:5.1f} | "
                            f"tải/query={tt['fetch']:4.1f} record mới/query={tt['new']:4.1f} f cuối={100 * tt['f_end']:4.1f}% "
                            f"hàng đợi tb={tt['qlen_mean']:6.0f} nodes={tt['nodes']:4.0f} moved={tt['moved']:5.0f}  "
                            f"[{time.time() - t0:.0f}s]")
                        log("     cửa sổ  " + " ".join(f"{x['final']:5.1f}/{x['rr']:5.1f}" for x in w))
                        log("     giữ riêng " + " ".join(f"t{k2}:{v['final']:4.1f}/{v['rr']:4.1f}" for k2, v in snaps.items()))

    # ---------------- tự kiểm với lazy đợt 3b
    f3b = None if a.check_3b == "none" else (a.check_3b if a.check_3b != "auto" else
                                             (f"probeL_{pre}{a.tag}_s{a.seed}_ku.json" if key == "u" else
                                              f"probeL_{pre}{a.tag}_s{a.seed}.json"))
    fn = a.out or (f"probeL_{pre}{a.tag}_s{a.seed}.json" if key != "u" else f"probeL_{pre}{a.tag}_s{a.seed}_ku.json")
    out["check_3b"] = None
    if f3b and os.path.exists(f3b) and os.path.abspath(f3b) != os.path.abspath(fn):
        old = json.load(open(f3b))
        n, bad = 0, 0
        for k, r in old.get("runs", {}).items():
            if k in out["runs"]:
                for kk, v in r["totals"].items():
                    if kk in out["runs"][k]["totals"]:
                        n += 1; bad += abs(out["runs"][k]["totals"][kk] - v) > 1e-9
                for x, y in zip(r["windows"], out["runs"][k]["windows"]):
                    for kk in ("final", "rr", "fetch", "new", "f"):
                        n += 1; bad += not (abs(x[kk] - y[kk]) <= 1e-9 or (x[kk] != x[kk] and y[kk] != y[kk]))
        out["check_3b"] = dict(file=f3b, n=n, bad=int(bad))
        log(f">>> so với đợt 3b ({f3b}): {n} giá trị, {'KHỚP' if bad == 0 and n > 0 else f'{bad} LỆCH'}")
    elif f3b:
        log(f">>> không tự kiểm với đợt 3b ({f3b} không có hoặc trùng file ra)")

    json.dump(out, open(fn, "w"), indent=1)
    if trace_keys:
        ftr = a.trace_out or fn.replace(".json", "_trace.json")
        miss = sorted(trace_keys - set(traces))
        json.dump(dict(argv=vars(a), N=int(N), nS=int(nS), S=[int(x) for x in S], traces=traces,
                       vars=([] if VQ is None else [[int(q), int(j)] for q, j in rows_v])), open(ftr, "w"))
        log(f"-> vết {sorted(traces)} ghi vào {ftr}" + (f"; KHÔNG có run {miss}" if miss else ""))
    log(f"\n-> {fn}   ({time.time() - t0:.0f}s)")

if __name__ == "__main__":
    main()
