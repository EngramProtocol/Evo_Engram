#!/usr/bin/env python3
"""
04_probe_multiepoch.py  —  CHẠY TRÊN node-dal-02 (CPU). Probe multi-epoch theo mục 5 của nhận xét.

Một phần corpus đã migrate thành record native E1, phần còn lại vẫn là record E0. Query mã hoá bằng M1.
  Phần E0 : định tuyến bằng q1·Wr, node chấm <q1·Wf^T, c_i> / n_i  (A_split_norm của gate 3d)
  Phần E1 : định tuyến và xếp hạng native trong E1 (khoá SRP từ q1, ADC L2 trên PQ code E1)
Gộp hai danh sách (mỗi record chỉ nằm ở một epoch):
  RRF    : điểm 1/(k + hạng), k = 60, đúng đề xuất trong nhận xét. Hai danh sách rời nhau nên RRF
           thành xen kẽ theo hạng; hoà hạng thì E1 đứng trước.
  CAL    : gộp theo điểm đã hiệu chỉnh. Điểm phía E0 là cosine dự đoán trong không gian M1; được đưa
           về thang điểm E1 bằng hồi quy tuyến tính y = a·x + b, học trên mẫu S với query validation
           (x = điểm E0 của document trong S, y = điểm E1 native của chính document đó).
  E1ONLY : chỉ phần E1, để thấy vì sao vẫn phải truy vấn E0.
Baseline: phần E0 dùng dual encoder (query M0, ADC L2) thay vì adapter, gộp bằng RRF và CAL.

Tập đã migrate: mẫu S (object dùng học adapter, vốn đã nhúng lại bằng M1) rồi tới các object khác
theo thứ tự ngẫu nhiên cố định theo seed, cho tới tỉ lệ f. f = 0 là chưa công bố record E1 nào,
đúng thiết lập gate 3: ở f = 0 nhánh adapter phải ra đúng A_split_norm của gate 3d và nhánh dual phải
ra đúng dual_encode (tự kiểm nếu có probeE_<tag>_s<seed>.json). Codebook PQ của E1 học trên E1[S] và
giữ cố định trong cả epoch.

Chi phí: số node bị chạm là tổng hai lần tra cứu (E0 và E1) khi cả hai epoch còn dữ liệu.

CHẠY: python3 evo/04_probe_multiepoch.py --tag bgebase --seed 20235956
"""
import argparse, importlib.util, json, os, random, time
import numpy as np
np.seterr(invalid='ignore', divide='ignore')

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("q3", os.path.join(_here, "03_probe_query_adapter.py"))
q3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q3)
pb = q3.pb
log, l2norm = pb.log, pb.l2norm

METHODS = ["AD_RRF", "AD_CAL", "DU_RRF", "DU_CAL", "E1ONLY"]


def route(qv, P_list, nid, K, T, cbits):
    pk = pb.probe_keys_for(qv, P_list, T, cbits)
    return [np.unique(pb.knn_nodes(np.concatenate([pk[l][qi] for l in range(len(P_list))]), nid, K))
            for qi in range(qv.shape[0])]


def adc_l2(q, cb, codes):
    m = cb.shape[0]
    return pb.adc_lut(q, cb)[np.arange(m)[None, :], codes].sum(1)


def adc_ip(q, cb, codes):
    m = cb.shape[0]
    lut = (q.reshape(m, -1)[:, None, :] * cb).sum(2)
    return lut[np.arange(m)[None, :], codes].sum(1)


def kappa_positions(order, anchors, mask, kappa, need):
    """Như q3.kappa_union nhưng trả về VỊ TRÍ trong `order` của các document client nhận được
    (mỗi node bị chạm chỉ trả top-kappa của nó). order[kết quả] trùng q3.kappa_union."""
    if need <= kappa:
        return np.arange(min(need, len(order)))
    cnt, out = {}, []
    for p, doc in enumerate(order.tolist()):
        ok = False
        for n in set(anchors[:, doc].tolist()):
            if not mask[n]:
                continue
            c = cnt.get(n, 0)
            if c < kappa:
                ok = True
            cnt[n] = c + 1
        if ok:
            out.append(p)
            if len(out) >= need:
                break
    return np.asarray(out, dtype=np.int64)


class Side:
    """Một phía tra cứu cho một query: tập node bị chạm, toàn bộ document neo tại đó và điểm của chúng.
    key: điểm xếp hạng tại node (càng lớn càng tốt); cal: điểm dùng khi gộp CAL."""
    def __init__(self, touched, anchors, n_nodes, n_docs, rank_key_fn, cal_fn):
        self.touched = touched
        self.mask = np.zeros(n_nodes, dtype=bool); self.mask[touched] = True
        self.reach = np.flatnonzero(self.mask[anchors].any(0))
        self.rmask = np.zeros(n_docs, dtype=bool); self.rmask[self.reach] = True
        self.key = rank_key_fn(self.reach)
        self.cal = cal_fn(self.reach)

    def ranked(self, active, anchors, kappa, need):
        sel = active[self.reach]
        r, k, c = self.reach[sel], self.key[sel], self.cal[sel]
        o = np.argsort(-k)
        order = r[o]
        pos = kappa_positions(order, anchors, self.mask, kappa, need)
        return len(r), order[pos], c[o][pos]


def interleave(l1, l0, n):
    out, i = [], 0
    while len(out) < n and (i < len(l1) or i < len(l0)):
        if i < len(l1): out.append(int(l1[i]))
        if i < len(l0) and len(out) < n: out.append(int(l0[i]))
        i += 1
    return np.asarray(out[:n], dtype=np.int64)


def merge_cal(l0, s0, l1, s1, n):
    """Gộp hai danh sách đã xếp hạng, giữ nguyên thứ tự bên trong mỗi danh sách; ở mỗi bước lấy
    phần tử đầu có điểm hiệu chỉnh cao hơn (hoà thì E1 trước). Điểm chỉ quyết định phân bổ giữa
    hai epoch, không xếp lại thứ tự native của từng epoch."""
    out, i, j = [], 0, 0
    while len(out) < n and (i < len(l0) or j < len(l1)):
        if j < len(l1) and (i >= len(l0) or s1[j] >= s0[i]):
            out.append(int(l1[j])); j += 1
        else:
            out.append(int(l0[i])); i += 1
    return np.asarray(out, dtype=np.int64)


def fit_cal(x_rows, y_rows, top):
    """Hồi quy y theo x trên vùng đầu bảng: mỗi query lấy `top` document có x cao nhất."""
    X, Y = [], []
    for x, y in zip(x_rows, y_rows):
        o = np.argsort(-x)[:top]
        X.append(x[o]); Y.append(y[o])
    X, Y = np.concatenate(X), np.concatenate(Y)
    A = np.stack([X, np.ones_like(X)], 1)
    a, b = np.linalg.lstsq(A, Y, rcond=None)[0]
    r = float(np.corrcoef(X, Y)[0, 1])
    return float(a), float(b), r


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
    ap.add_argument("--frac", type=float, default=0.10, help="mẫu S dùng học adapter (đã nhúng lại bằng M1)")
    ap.add_argument("--fmig", default="0,0.1,0.2,0.3,0.5,0.7,0.9,1.0", help="tỉ lệ corpus đã có record E1")
    ap.add_argument("--rerank", default="5,10,20,50,100")
    ap.add_argument("--cal-top", type=int, default=30)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    t0 = time.time()
    D, ds = a.data_dir, a.dataset
    Rs = [int(x) for x in a.rerank.split(",")]
    Rmax = max(Rs)
    fgrid = [float(x) for x in a.fmig.split(",")]

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
    assert len(trq) > 0, "cần query ngoài tập đánh giá để hiệu chỉnh CAL"
    gt5_all = [np.array([int(r["index"]) for r in g["top_5_results"][:5]]) for g in gt1]

    rnd = random.Random(a.seed)
    nid = np.array([rnd.getrandbits(63) for _ in range(a.nodes)], dtype=np.int64)
    P0 = pb.gen_proj(a.seed, d0, a.tables)
    P1 = pb.gen_proj(a.seed, d1, a.tables)
    perm = np.random.RandomState(a.seed).permutation(N)
    nS = max(a.tables * 20, int(round(a.frac * N)))
    S = perm[:nS]
    mig_order = perm                       # S trước, sau đó các object còn lại theo cùng hoán vị
    log("=" * 78)
    log(f"dataset={ds} tag={a.tag} seed={a.seed}  N={N} nodes={a.nodes}  mẫu S={nS} ({nS / N:.1%})  f={fgrid}")

    # adapter như gate 3d
    Wr, _, _ = q3.fit_ridge_cv(E1[S], E0[S], a.seed, (1e-3, 1e-2, 1e-1, 1.0, 10.0))
    Wf, _ = pb.fit_bridge(E0[S], E1[S], "ridge", a.seed)
    WfT = np.ascontiguousarray(Wf.T)
    m0 = cb0.shape[0]
    C0 = cb0[np.arange(m0)[None, :], cd0].reshape(N, d0).astype(np.float32)
    n_i = np.linalg.norm(C0 @ Wf, axis=1)

    # E1: codebook học trên E1[S], cố định trong epoch
    cb1 = pb.pq_train(E1[S], m1, a.seed)
    cd1 = pb.pq_encode(E1, cb1)
    anchors0 = pb.build_index(E0, P0, nid)
    anchors1 = pb.build_index(E1, P1, nid)

    # ---------------- hiệu chỉnh CAL trên validation, chỉ dùng document trong S
    qv1 = l2norm(Q1[trq]); qhat = Q1[trq] @ WfT; qhn = l2norm(qhat)
    qnorm = np.linalg.norm(qhat, axis=1)
    xa, xd, y = [], [], []
    for i in range(len(trq)):
        y.append(adc_ip(qv1[i], cb1, cd1[S]))
        xa.append(adc_ip(qhn[i], cb0, cd0[S]) / n_i[S] * qnorm[i])
        xd.append(adc_ip(Q0[trq][i], cb0, cd0[S]))
    ca, cb_, cr = fit_cal(xa, y, a.cal_top)
    da, db, dr = fit_cal(xd, y, a.cal_top)
    log(f"hiệu chỉnh CAL (validation {len(trq)} query x top-{a.cal_top} trong S): "
        f"adapter y = {ca:.3f}·x + {cb_:+.3f} (r={cr:.3f}); dual y = {da:.3f}·x + {db:+.3f} (r={dr:.3f})")

    # ---------------- định tuyến và chấm điểm một lần cho mỗi query đánh giá
    qr0 = l2norm(Q1[ev] @ Wr)                     # định tuyến phía E0 của adapter
    qk0 = l2norm(Q1[ev] @ WfT)                    # xếp hạng phía E0 (y hệt 3d)
    qk0n = np.linalg.norm(Q1[ev] @ WfT, axis=1)
    q1e = l2norm(Q1[ev])
    T0a = route(qr0, P0, nid, a.k_query, a.probes, a.cbits)
    T0d = route(Q0[ev], P0, nid, a.k_query, a.probes, a.cbits)
    T1 = route(q1e, P1, nid, a.k_query, a.probes, a.cbits)
    sides = []
    for qi in range(len(ev)):
        sa = Side(T0a[qi], anchors0, a.nodes, N,
                  lambda r, qi=qi: adc_ip(qk0[qi], cb0, cd0[r]) / n_i[r],
                  lambda r, qi=qi: (adc_ip(qk0[qi], cb0, cd0[r]) / n_i[r] * qk0n[qi]) * ca + cb_)
        sd = Side(T0d[qi], anchors0, a.nodes, N,
                  lambda r, qi=qi: -adc_l2(Q0[ev][qi], cb0, cd0[r]),
                  lambda r, qi=qi: adc_ip(Q0[ev][qi], cb0, cd0[r]) * da + db)
        s1 = Side(T1[qi], anchors1, a.nodes, N,
                  lambda r, qi=qi: -adc_l2(q1e[qi], cb1, cd1[r]),
                  lambda r, qi=qi: adc_ip(q1e[qi], cb1, cd1[r]))
        sides.append((sa, sd, s1))
    log(f"định tuyến và chấm điểm xong ({time.time() - t0:.0f}s)")

    results = {}
    for f in fgrid:
        nM = int(round(f * N))
        inE1 = np.zeros(N, dtype=bool); inE1[mig_order[:nM]] = True
        act0, act1 = ~inE1, inE1
        has0, has1 = act0.any(), act1.any()
        load0 = np.bincount(anchors0[:, act0].ravel(), minlength=a.nodes)
        load1 = np.bincount(anchors1[:, act1].ravel(), minlength=a.nodes)
        acc = {mth: dict(reach=[], final=[], R={R: [] for R in Rs}, nodes=[], cand=[], moved=[], e0share=[])
               for mth in METHODS}
        for qi in range(len(ev)):
            garr = gt5_all[ev[qi]]
            g = set(garr.tolist())
            sa, sd, s1 = sides[qi]
            ca_n, la, ka = sa.ranked(act0, anchors0, a.kappa, Rmax)
            cd_n, ld, kd = sd.ranked(act0, anchors0, a.kappa, Rmax)
            c1_n, l1, k1 = s1.ranked(act1, anchors1, a.kappa, Rmax)
            h0a = int((sa.rmask[garr] & act0[garr]).sum())
            h0d = int((sd.rmask[garr] & act0[garr]).sum())
            h1 = int((s1.rmask[garr] & act1[garr]).sum())
            n0a = len(sa.touched) if has0 else 0
            n0d = len(sd.touched) if has0 else 0
            n1 = len(s1.touched) if has1 else 0
            mv0a = np.minimum(load0[sa.touched], a.kappa).sum() if has0 else 0
            mv0d = np.minimum(load0[sd.touched], a.kappa).sum() if has0 else 0
            mv1 = np.minimum(load1[s1.touched], a.kappa).sum() if has1 else 0
            # (danh sách gộp, số GT reachable, số ứng viên reachable, node bị chạm, ứng viên chuyển)
            fused = {
                "AD_RRF": (interleave(l1, la, Rmax), h0a + h1, ca_n + c1_n, n0a + n1, mv0a + mv1),
                "AD_CAL": (merge_cal(la, ka, l1, k1, Rmax), h0a + h1, ca_n + c1_n, n0a + n1, mv0a + mv1),
                "DU_RRF": (interleave(l1, ld, Rmax), h0d + h1, cd_n + c1_n, n0d + n1, mv0d + mv1),
                "DU_CAL": (merge_cal(ld, kd, l1, k1, Rmax), h0d + h1, cd_n + c1_n, n0d + n1, mv0d + mv1),
                "E1ONLY": (l1[:Rmax], h1, c1_n, n1, mv1),
            }
            for mth, (lst, hits, nc, nn, mv) in fused.items():
                A = acc[mth]
                A["reach"].append(hits / 5.0)
                A["final"].append(len(set(lst[:5].tolist()) & g) / 5.0)
                A["e0share"].append(float(np.mean([not inE1[d] for d in lst[:5]])) if len(lst) else 0.0)
                A["nodes"].append(nn); A["moved"].append(mv)
                A["cand"].append(nc)
                for R in Rs:
                    cand = lst[:R]
                    if len(cand) == 0:
                        A["R"][R].append(0.0); continue
                    top = cand[np.argsort(-(E1[cand] @ Q1[ev[qi]]))[:5]]
                    A["R"][R].append(len(set(top.tolist()) & g) / 5.0)
        res = {}
        for mth, A in acc.items():
            res[mth] = dict(reach_r5=100 * np.mean(A["reach"]), final_r5=100 * np.mean(A["final"]),
                            rerank={str(R): 100 * np.mean(A["R"][R]) for R in Rs},
                            nodes=float(np.mean(A["nodes"])), cand=float(np.mean(A["cand"])),
                            moved=float(np.mean(A["moved"])), e0_share_top5=float(np.mean(A["e0share"])))
        results[f"{f:g}"] = res
        log(f"\n--- f = {f:.0%}  (record E1: {nM}, record E0: {N - nM})")
        for mth in METHODS:
            r = res[mth]
            rr = "  ".join(f"R{R}={r['rerank'][str(R)]:5.1f}" for R in Rs)
            log(f"  {mth:7s} reach={r['reach_r5']:5.1f} final={r['final_r5']:5.1f} | {rr} | "
                f"nodes={r['nodes']:.0f} cand={r['cand']:.0f} moved={r['moved']:.0f} "
                f"top5 từ E0={100 * r['e0_share_top5']:.0f}%")

    # ---------------- tự kiểm ở f = 0 với gate 3d
    f3d = (f"probeE_{a.tag}_s{a.seed}.json" if ds == "code" else f"probeE_{ds}_{a.tag}_s{a.seed}.json")
    if "0" in results and os.path.exists(f3d) and abs(a.frac - json.load(open(f3d))["argv"]["frac"]) < 1e-9:
        old = {r["name"]: r for r in json.load(open(f3d))["results"]}
        bad, n = 0, 0
        for mth, ref in (("AD_RRF", "A_split_norm"), ("AD_CAL", "A_split_norm"), ("DU_RRF", "dual_encode")):
            new, o = results["0"][mth], old[ref]
            for k in ("reach_r5", "final_r5", "nodes", "cand", "moved"):
                n += 1; bad += abs(new[k] - o[k]) > 1e-9
            for R in new["rerank"]:
                if R in o["rerank"]:
                    n += 1; bad += abs(new["rerank"][R] - o["rerank"][R]) > 1e-9
        log(f"\n>>> f = 0 so với gate 3d ({f3d}): {n} giá trị, "
            f"{'KHỚP' if bad == 0 else f'{bad} LỆCH, dừng lại kiểm tra'}")

    out = a.out or (f"probeF_{a.tag}_s{a.seed}.json" if ds == "code" else f"probeF_{ds}_{a.tag}_s{a.seed}.json")
    json.dump(dict(argv=vars(a), n_sample=int(nS), cal=dict(adapter=[ca, cb_, cr], dual=[da, db, dr]),
                   results=results), open(out, "w"), indent=1)
    log(f"\n-> {out}   ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
