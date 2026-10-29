#!/usr/bin/env python3
"""
11_probe_safe.py  —  ĐỢT 7 (thăm dò, chưa đăng ký trước). Migrate an toàn: công bố record E1 nhưng chỉ
retire record E0 khi index native đã tự tìm lại được object đó (verify-then-retire).

Vấn đề cần trả lời: lazy migration của bài retire record E0 ngay khi công bố E1. Khi index native kém
(khoá SRP không trừ tâm dồn record vào ít peer, Arctic) record vừa chuyển có thể không còn được tìm thấy qua
khoá E1, nên reach và rerank giảm so với lúc record còn ở E0. Ở đây một object có thể tạm nằm ở cả hai epoch
(dual): phía E0 vẫn trả record cũ, phía E1 trả record mới, danh sách gộp bỏ bản trùng. Mỗi lần một
truy vấn thấy object dual qua khoá E1 trong danh sách native của chính nó, client gửi một xác nhận; đủ c
xác nhận thì re-indexer retire bản E0. Tính chất giữ được: object không mất đường tìm cũ trước khi đường mới
đã được c truy vấn độc lập dùng thành công.

Thiết lập giữ đúng 06_probe_lazy.py (khoá E1 'u', adapter A_split_norm học trên S, gộp PROB, dòng Zipf
3.000 lượt trên 200 query, 100 query giữ riêng, re-indexer không giới hạn). Chính sách:
  static   không migrate
  lazy     như bài: công bố record E0 vừa tải trong pool rồi retire ngay
  bg       nền ngẫu nhiên, cùng số record công bố với lazy
  lazyD    công bố nhưng không bao giờ retire (hai epoch chồng nhau): cận trên của recall, chi phí lưu trữ lớn nhất
  lazyV<c> công bố, retire bản E0 sau c xác nhận native (c trong --confirms)
  bgV<c>   nền ngẫu nhiên, cùng số record công bố với lazyV<c>, retire ngay
Khi công bố bản E1, re-indexer ghi thêm mã PQ E1 vào record E0 cũ (nâng cấp tại chỗ, peer E0 không đổi).
Peer E0 vẫn xếp hạng bằng mã E0 và adapter như cũ, nhưng trả kèm mã E1, nên client chấm object dual bằng
ADC native dù tìm thấy qua khoá nào (--dual-score e1code, mặc định); --dual-score adapter giữ điểm adapter
cho bản E0 (chỉ bỏ bản trùng với danh sách native) để so sánh.
Rerank theo quy ước dòng truy vấn của 06: record chỉ có ở E0 được tải payload và chấm cosine M1 thật; record
có điểm ADC native giữ điểm đó. Xác nhận chỉ tính khi object được tìm thấy qua khoá E1.

Phía E0 khi có object dual (--dual-slots bonus, mặc định): object dual không chiếm chỗ trong Rk record E0;
client đọc tiếp danh sách E0 (tối đa --bonus-mult x R vị trí, vẫn giới hạn kappa mỗi peer) tới khi đủ Rk record
chỉ có ở E0, các object dual gặp trên đường là phần thêm. --dual-slots shared tính chúng như record thường.

Đo thêm so với 06: tỉ lệ object dual (lưu trữ E0 thừa) cuối dòng và trung bình, tỉ lệ E0 còn hoạt động,
số xác nhận, số retire, số object dual nhận từ phía E0 mỗi truy vấn (byte trả về thêm), số record các peer được
hỏi phải chấm mỗi truy vấn (scan, cả hai phía); nếu GT của M0 có
source_corpus_index (code100kfq): tỉ lệ hàm gốc của query nằm trong top-5 trước và sau rerank (gold_final, gold_rr).

Tự kiểm: static, lazy, bg (Zipf 1, PROB) phải trùng từng số với probeL_<pre><tag>_s<seed>_ku.json của 06
(totals và cửa sổ) nếu file có ở thư mục hiện tại. Chỉ chạy khi --e1-place u; khi lệch, in tối đa 10 giá trị lệch.

Bổ sung đợt 7b:
  lazyVbg   lazyV<c> (c = số đầu của --confirms) cộng migrate nền ngẫu nhiên, record nền retire ngay như bg. Tốc độ
            nền chọn để tổng số record công bố bằng của lazy: (số record lazy công bố − số record lazyV<c> công bố)
            / độ dài dòng. So với lazy ở cùng ngân sách nhúng lại.
  lazyVbgD  như lazyVbg nhưng record nền cũng công bố dạng dual (giữ bản E0, nâng cấp mã E1 tại chỗ) và chỉ retire
            sau c xác nhận native, như record do truy vấn kéo về.
  --e1-place u | itq_q | pca_q | srp_cq: cách đặt record của epoch E1. u là SRP không trừ tâm như bài (mặc định,
            giữ đúng từng số đợt 7). Các cách còn lại dùng đúng hàm của 10_probe_placement.py, học trên mẫu S. Với
            cách học, tự kiểm index native ở f = 1 (300 query đánh giá, L = 5, T = 8) phải trùng biến thể cùng tên
            trong probeP_<pre><tag>_s<seed>.json của đợt 7 (reach, final, rerank@20, ứng viên, peer).

Bổ sung đợt 8 (hai baseline, mặc định giữ đúng từng số đợt 7b cho các chính sách cũ):
  full      dựng lại toàn bộ index: mọi object có record E1 thật từ đầu, E0 gỡ hết. Cận trên, tốn 100% ngân sách
            nhúng lại ngay từ đầu (ghi ở reembed_t0).
  mapall    map-and-republish kiểu FastFill: ở t = 0 re-indexer công bố cho mọi object ngoài S một record E1 dựng từ
            vector ánh xạ qua adapter, v = chuẩn hoá(c0 W_f) với c0 là bản tái tạo PQ của record E0, đặt bằng chính
            placement E1 và mã hoá bằng codebook E1; E0 gỡ hết (ghi republish_t0, không nhúng lại). Client coi record
            ánh xạ là gần đúng: record ánh xạ nằm trong pool rerank được tải payload, chấm cosine M1 thật, và re-indexer
            thay bằng record E1 thật (cùng quy tắc với lazy). Mỗi peer trả top-kappa trên cả hai loại record.
  --check-prev FILE  so mọi run có trong FILE (totals, cửa sổ, snapshot) với run cùng tên ở lượt này, để chắc code mới
            không đổi kết quả các chính sách cũ.

Bổ sung đợt 9 (mặc định tắt; khi tắt, mọi chính sách cũ giữ đúng từng số đợt 8):
  mapkeep   như mapall nhưng giữ index E0 tới khi object được thay bằng record E1 thật, nên mỗi truy vấn hỏi cả hai
            epoch như lazyVbgD. Object đã thấy qua phía E1 (record thật hoặc record ánh xạ) bị bỏ khỏi danh sách E0, và
            phía E0 đọc tiếp tới đủ R record chỉ có ở E0 (như --dual-slots bonus). Record trong pool không có điểm ADC
            native được tải payload và chấm cosine M1 thật; re-indexer thay nó bằng record E1 thật và retire bản E0 ngay.
  churn     theo engine churn của V-Engram (main_churn_engine.py): phiên Weibull (hình dạng --weibull-shape, trung vị
            --median-session phút), node rời mạng mất mọi record nó giữ, node mới thay chỗ với bộ nhớ rỗng; sửa chữa
            lười mỗi --repair-every phút ghi lại các bản đã mất của record còn hoạt động và gửi keep-alive cho bản còn
            sống. Khác engine của V-Engram ở một điểm: node mới giữ đúng vị trí của node cũ trong không gian khoá, nên
            định tuyến và vị trí đặt record không đổi, churn chỉ tác động qua bản ghi bị mất. Truy vấn hỏi K peer gần
            nhất của mỗi khoá probe, nên node mới vào gần khoá chỉ đẩy anchor cũ xuống một hạng; phần mất dữ liệu là
            phần chính. --churn-min: cả dòng truy vấn ứng với bao nhiêu phút (0 = không churn liên tục). Thời gian còn
            lại của phiên ban đầu lấy từ phân phối dừng (hình dạng 0,5: lambda·U², U ~ Gamma(2, 1)), nên không cần
            warm-up. Lần sửa thứ j ở phút (j + --repair-phase)·chu kỳ, để snapshot không rơi đúng lúc vừa sửa xong.
  lỗi peer  --fail-at t --fail-frac f: ngay trước lượt t, một phần f số node hỏng cùng lúc (mất dữ liệu như rời mạng).
            Lịch churn và lỗi chỉ phụ thuộc seed, nên mọi chính sách trong một job thấy đúng cùng một chuỗi sự kiện.
            Khi bật churn hoặc lỗi, đo thêm ở mỗi snapshot: phần object còn ít nhất một bản ở E0 (alive0) và ở E1
            (aliveK), phần corpus mất mọi đường tìm (lost_obj: không còn bản nào ở epoch nào); và trong totals: số bản
            ghi được sửa và số keep-alive mỗi truy vấn, tổng số lượt node rời mạng.
  --churn-sets 'tên:khoá=giá trị,...;...' chạy thêm các cấu hình churn trong cùng job sau cấu hình chính, dùng chung
            phần dựng index và định tuyến (tốn phần lớn thời gian của job); run ghi tên 'z<z>|PROB|<chính sách>|<tên>',
            chính sách lấy từ --churn-policies, Zipf từ --churn-zipf.

CHẠY: python3 evo/11_probe_safe.py --tag arctic --dataset code100kfq --seed 3 --nodes 50000 --frac 0.02
"""
import argparse, importlib.util, json, os, random, time
import numpy as np
import me_common as mc

_here = os.path.dirname(os.path.abspath(__file__))
_sp10 = importlib.util.spec_from_file_location("p10", os.path.join(_here, "10_probe_placement.py"))
p10 = importlib.util.module_from_spec(_sp10)
_sp10.loader.exec_module(p10)

np.seterr(invalid='ignore', divide='ignore')
q3, pb = mc.q3, mc.pb
log, l2norm = mc.log, mc.l2norm


# ----------------------------------------------------------------- churn (đợt 9)
def churn_schedule(a):
    """-> (deps, reps): deps[t] = các node rời mạng ngay trước lượt t (gồm cả sự cố đồng loạt), reps = các lượt t có
    sửa chữa ngay trước lượt đó. Chỉ phụ thuộc seed và tham số churn."""
    deps, reps = {}, set()
    if a.churn_min > 0:
        rng = np.random.RandomState(a.seed + 61)
        k = float(a.weibull_shape)
        lam = a.median_session / (np.log(2) ** (1.0 / k))
        dt = a.churn_min * a.churn_step / a.stream
        if abs(k - 0.5) < 1e-12:
            rem = lam * rng.gamma(2.0, 1.0, size=a.nodes) ** 2       # thời gian còn lại ở trạng thái dừng
        else:                                                        # hình dạng khác: warm-up một trung vị phiên
            rem = lam * rng.weibull(k, size=a.nodes)
            for _ in range(int(np.ceil(a.median_session / dt))):
                rem -= dt
                d_ = np.flatnonzero(rem <= 0)
                rem[d_] = lam * rng.weibull(k, size=len(d_))
        for t in range(a.churn_step, a.stream + 1, a.churn_step):
            rem -= dt
            dead = np.flatnonzero(rem <= 0)
            if len(dead):
                rem[dead] = lam * rng.weibull(k, size=len(dead))     # như V-Engram: phiên mới bắt đầu ở mốc bước
                deps[t] = dead.astype(np.int64)
        if a.repair_every > 0:
            j = 0
            while True:
                t = int(round((j + a.repair_phase) * a.repair_every / a.churn_min * a.stream))
                if t > a.stream:
                    break
                reps.add(t); j += 1
    if a.fail_at >= 0:
        rs = np.random.RandomState(a.seed + 67)
        f = rs.choice(a.nodes, size=int(round(a.fail_frac * a.nodes)), replace=False).astype(np.int64)
        deps[a.fail_at] = np.union1d(deps.get(a.fail_at, np.zeros(0, np.int64)), f)
    return deps, reps


CHURN_KEYS = dict(churn_min=float, median_session=float, weibull_shape=float, repair_every=float, repair_phase=float,
                  churn_step=int, fail_at=int, fail_frac=float)
CHURN_DEFAULTS = dict(churn_min=0.0, median_session=120.0, weibull_shape=0.5, repair_every=0.0, repair_phase=0.5,
                      churn_step=10, fail_at=-1, fail_frac=0.2)


def parse_churn_sets(s):
    """'ch:churn_min=720,median_session=120,repair_every=60;fail:fail_at=1500,fail_frac=0.3' -> [(tên, tham số)].
    Mỗi cấu hình bắt đầu từ giá trị mặc định của các tham số churn, không kế thừa cấu hình chính."""
    out = []
    for part in [x for x in (s or "").split(";") if x.strip()]:
        name, _, kv = part.partition(":")
        d = dict(CHURN_DEFAULTS)
        for item in [y for y in kv.split(",") if y.strip()]:
            k, _, v = item.partition("=")
            k = k.strip()
            if k not in CHURN_KEYS:
                raise SystemExit(f"--churn-sets: tham số lạ '{k}'")
            d[k] = CHURN_KEYS[k](v)
        out.append((name.strip(), d))
    return out


def placement_index(anchors, n_nodes):
    """CSR: node -> vị trí phẳng trong anchors (L x N) của các bản ghi đặt ở node đó."""
    flat = anchors.ravel()
    order = np.argsort(flat, kind="stable")
    starts = np.searchsorted(flat[order], np.arange(n_nodes + 1))
    return order, starts


def placements_at(idx, nodes, n_cols):
    order, starts = idx
    parts = [order[starts[x]:starts[x + 1]] for x in nodes.tolist()]
    pos = np.concatenate(parts) if parts else np.zeros(0, np.int64)
    return pos // n_cols, pos % n_cols                                # (bảng, object)


def kappa_positions_lost(order, anchors, mask, kappa, need, lost):
    """Như mc.kappa_positions nhưng một node chỉ tính cho object nếu bản ghi của object ở node đó chưa mất."""
    if need <= kappa:
        return np.arange(min(need, len(order)))
    cnt, out = {}, []
    for p, doc in enumerate(order.tolist()):
        ok = False
        col, lc = anchors[:, doc], lost[:, doc]
        for n in set(col[~lc].tolist()):
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


def ranked_lost(s, active, lost, kappa, need):
    """Như Side2.ranked (ngân sách đầy đủ) nhưng bỏ bản ghi đã mất: object chỉ reachable nếu còn ít nhất một bản ghi
    chưa mất ở một node được hỏi. lost None thì gọi đúng Side2.ranked, nên khi tắt churn kết quả không đổi."""
    if lost is None:
        return s.ranked(active, kappa, need)
    touched, mask, _ = s.budget(None)
    if getattr(s, "_tp", None) is None:
        s._tp = mask[s.anchors[:, s.reach]]                           # (L, |reach|): bản ghi nằm ở node được hỏi
    ok = active[s.reach] & (s._tp & ~lost[:, s.reach]).any(0)
    r, k, x = s.reach[ok], s.key[ok], s.x[ok]
    o = np.argsort(-k)
    order = r[o]
    pos = kappa_positions_lost(order, s.anchors, mask, kappa, need, lost)
    return len(r), order[pos], x[o][pos]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--dataset", default="code100kfq")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--nodes", type=int, default=50000)
    ap.add_argument("--nq", type=int, default=300)
    ap.add_argument("--tables", type=int, default=5)
    ap.add_argument("--k-query", type=int, default=20)
    ap.add_argument("--probes", type=int, default=8)
    ap.add_argument("--cbits", type=int, default=16)
    ap.add_argument("--dsub", type=int, default=2)
    ap.add_argument("--kappa", type=int, default=30)
    ap.add_argument("--frac", type=float, default=0.02)
    ap.add_argument("--cal-top", type=int, default=30)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--stream", type=int, default=3000)
    ap.add_argument("--zipf", default="1.0,0")
    ap.add_argument("--n-heldout", type=int, default=100)
    ap.add_argument("--R", type=int, default=20)
    ap.add_argument("--window", type=int, default=150)
    ap.add_argument("--checkpoints", default="0,150,300,600,1000,1500,2000,3000")
    ap.add_argument("--policies", default="static,lazy,bg,lazyD,lazyV,bgV")
    ap.add_argument("--confirms", default="1,2")
    ap.add_argument("--dual-score", default="e1code", choices=["e1code", "adapter"],
                    help="cách chấm bản E0 của object dual: e1code = peer E0 trả kèm mã E1, adapter = điểm adapter")
    ap.add_argument("--dual-slots", default="bonus", choices=["bonus", "shared"],
                    help="bonus: object dual từ phía E0 không tính vào Rk record E0; shared: tính như record thường")
    ap.add_argument("--bonus-mult", type=int, default=3, help="phía E0 đọc tối đa bonus_mult x R vị trí")
    ap.add_argument("--e1-place", default="u", choices=["u", "itq_q", "pca_q", "srp_cq"],
                    help="cách đặt record E1: u = SRP không trừ tâm như bài; còn lại như 10_probe_placement.py")
    ap.add_argument("--k-pca", type=int, default=128)
    ap.add_argument("--itq-iters", type=int, default=50)
    ap.add_argument("--check-10", default="auto", help="probeP của đợt 7 để tự kiểm placement học; none = bỏ")
    ap.add_argument("--check-06", default="auto")
    ap.add_argument("--check-prev", default="none", help="file kết quả cũ của 11 để so từng số các run trùng tên")
    ap.add_argument("--churn-min", type=float, default=0.0, help="cả dòng truy vấn ứng với bao nhiêu phút; 0 = không churn")
    ap.add_argument("--median-session", type=float, default=120.0, help="trung vị phiên (phút), như V-Engram")
    ap.add_argument("--weibull-shape", type=float, default=0.5)
    ap.add_argument("--repair-every", type=float, default=0.0, help="chu kỳ sửa chữa (phút); 0 = không sửa")
    ap.add_argument("--repair-phase", type=float, default=0.5, help="lần sửa thứ j ở phút (j + phase) x chu kỳ")
    ap.add_argument("--churn-step", type=int, default=10, help="số lượt truy vấn giữa hai bước churn")
    ap.add_argument("--fail-at", type=int, default=-1, help="lượt truy vấn có sự cố đồng loạt; -1 = không")
    ap.add_argument("--fail-frac", type=float, default=0.2, help="phần node hỏng trong sự cố đồng loạt")
    ap.add_argument("--churn-sets", default="",
                    help="cấu hình churn bổ sung chạy trong cùng job, ví dụ 'ch:churn_min=720,median_session=120,"
                         "repair_every=60;fail:fail_at=1500,fail_frac=0.3'; tên run thêm '|<tên cấu hình>'")
    ap.add_argument("--churn-policies", default="", help="chính sách cho --churn-sets (mặc định như --policies)")
    ap.add_argument("--churn-zipf", default="", help="Zipf cho --churn-sets (mặc định như --zipf)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    t0 = time.time()
    D, ds = a.data_dir, a.dataset
    T = a.probes
    zipfs = [float(z) for z in a.zipf.split(",")]
    confirms = [int(c) for c in a.confirms.split(",") if c]
    cps = sorted({int(c) for c in a.checkpoints.split(",") if int(c) <= a.stream} | {0, a.stream})

    E0 = np.load(f"{D}/{ds}_corpus_embeddings.npy").astype(np.float32)
    cb0 = np.load(f"{D}/{ds}_pq_codebook_m512.npy").astype(np.float32)
    cd0 = np.load(f"{D}/{ds}_pq_codes_m512.npy")
    E1 = np.load(f"{D}/{ds}_{a.tag}_corpus_embeddings.npy").astype(np.float32)
    Q1 = np.load(f"{D}/{ds}_{a.tag}_query_embeddings.npy").astype(np.float32)
    gt1 = json.load(open(f"{D}/{ds}_{a.tag}_ground_truth.json"))
    N, d0 = E0.shape; d1 = E1.shape[1]; NQall = len(gt1)
    m1 = d1 // a.dsub
    ev, trq = np.arange(a.nq), np.arange(a.nq, NQall)
    gt5_all = [np.array([int(r["index"]) for r in g["top_5_results"][:5]]) for g in gt1]
    gold = None                                          # hàm gốc của query (nhãn liên quan theo tác vụ), nếu có
    fgold = f"{D}/{ds}_ground_truth.json"
    if os.path.exists(fgold):
        g0 = json.load(open(fgold))
        if len(g0) >= a.nq and all("source_corpus_index" in g0[i] for i in range(a.nq)):
            gold = np.array([int(g0[i]["source_corpus_index"]) for i in range(a.nq)], dtype=np.int64)

    rnd = random.Random(a.seed)
    nid = np.array([rnd.getrandbits(63) for _ in range(a.nodes)], dtype=np.int64)
    P0 = pb.gen_proj(a.seed, d0, a.tables)
    P1 = pb.gen_proj(a.seed, d1, a.tables)
    perm = np.random.RandomState(a.seed).permutation(N)
    nS = max(a.tables * 20, int(round(a.frac * N)))
    S = perm[:nS]
    log("=" * 78)
    log(f"[11] dataset={ds} tag={a.tag} seed={a.seed} N={N} S={nS} dòng={a.stream} zipf={zipfs} R={a.R} "
        f"chính sách={a.policies} xác nhận={confirms} đặt E1={a.e1_place}  (numpy {np.__version__})")

    # ---------------- adapter, PQ E1, chỉ mục: đúng như 06 với khoá E1 'u'
    m0 = cb0.shape[0]
    C0 = cb0[np.arange(m0)[None, :], cd0].reshape(N, d0).astype(np.float32)
    Wr, _, _ = q3.fit_ridge_cv(E1[S], E0[S], a.seed, (1e-3, 1e-2, 1e-1, 1.0, 10.0))
    Wf, _ = pb.fit_bridge(E0[S], E1[S], "ridge", a.seed)
    WfT = np.ascontiguousarray(Wf.T)
    n_i = np.linalg.norm(C0 @ Wf, axis=1)
    cb1 = pb.pq_train(E1[S], m1, a.seed)
    cd1 = pb.pq_encode(E1, cb1)
    anchors0 = pb.build_index(E0, P0, nid)
    q1all = l2norm(Q1[ev])
    if a.e1_place == "u":
        anchorsK = pb.build_index(E1, P1, nid)
        NK = mc.route_keys(q1all, P1, nid, a.k_query, T, a.cbits)
    else:
        # placement học trên S, đúng hàm của 10 (bảng đầu của Lmax lớn trùng Lmax nhỏ)
        mu_d = E1[S].mean(0).astype(np.float32)
        mu_q = Q1[trq].mean(0).astype(np.float32) if len(trq) else mu_d
        PV = p10.make_variant(a.e1_place, E1[S], a.tables, a.seed, P1, mu_d, mu_q, a.k_pca, a.itq_iters)
        anchorsK = np.stack([pb.nearest_node(p10.pack(p10.doc_bits(E1, W, t, PV["cd"])), nid)
                             for W, t in zip(PV["W"], PV["t"])])
        keys = np.stack(p10.probe_keys(q1all, PV["W"], PV["t"], PV["cq"], T, a.cbits), axis=1)
        NK = pb.knn_nodes(keys.reshape(-1), nid, a.k_query).reshape(len(ev), a.tables, T, a.k_query)
    stK = mc.load_stats(anchorsK, a.nodes)
    log(f"tải lưu trữ E1 ({a.e1_place}, khi mọi record ở E1): max={stK['max']} rỗng={100 * stK['empty_frac']:.0f}% "
        f"top1%={100 * stK['top1pct_share']:.1f}%")
    Xcf, _ = mc.crossfit_adapter_x(E0, E1, C0, cb0, cd0, Q1[trq], S, S, a.folds, a.seed)
    Ycf = mc.e1_scores(Q1[trq], cb1, cd1, S)
    ols_ad = mc.ols_top(list(Xcf), list(Ycf), a.cal_top)
    sig1 = mc.sigma_e1(Q1[trq], E1, cb1, cd1, S, a.cal_top)
    cal = dict(cal_a=None, cal_b=None, ols=ols_ad, sig1=sig1)
    log(f"hiệu chỉnh cross-fit: a={ols_ad['a']:.3f} b={ols_ad['b']:+.3f} sigma0={ols_ad['sig']:.4f} "
        f"r={ols_ad['r']:.3f}; sigma1={sig1:.4f}")

    sides_K = [mc.Side2(NK[i], anchorsK, a.nodes,
                        (lambda r, i=i: (-mc.adc_l2(q1all[i], cb1, cd1[r]), mc.adc_ip(q1all[i], cb1, cd1[r]))))
               for i in range(len(ev))]
    qr0 = l2norm(Q1[ev] @ Wr)
    qk = l2norm(Q1[ev] @ WfT); qkn = np.linalg.norm(Q1[ev] @ WfT, axis=1)
    NA = mc.route_keys(qr0, P0, nid, a.k_query, T, a.cbits)

    def fa(i):
        def f(r):
            k = mc.adc_ip(qk[i], cb0, cd0[r]) / n_i[r]
            return k, k * qkn[i]
        return f
    sides_A = [mc.Side2(NA[i], anchors0, a.nodes, fa(i)) for i in range(len(ev))]
    log(f"định tuyến và chấm điểm xong ({time.time() - t0:.0f}s)")

    # ---------------- baseline map-and-republish: record E1 ánh xạ cho mọi object, cùng placement E1
    pols_req = a.policies.split(",")
    sides_KM, anchorsM = None, None
    if "mapall" in pols_req or "mapkeep" in pols_req:
        Mv = l2norm(C0 @ Wf).astype(np.float32)
        cdM = pb.pq_encode(Mv, cb1)
        if a.e1_place == "u":
            anchorsM = pb.build_index(Mv, P1, nid)
        else:
            anchorsM = np.stack([pb.nearest_node(p10.pack(p10.doc_bits(Mv, W, t, PV["cd"])), nid)
                                 for W, t in zip(PV["W"], PV["t"])])
        anchorsKM = np.concatenate([anchorsK, anchorsM], axis=1)     # id < N: record thật, id >= N: record ánh xạ
        cdKM = np.concatenate([cd1, cdM], axis=0)
        sides_KM = [mc.Side2(NK[i], anchorsKM, a.nodes,
                             (lambda r, i=i: (-mc.adc_l2(q1all[i], cb1, cdKM[r]), mc.adc_ip(q1all[i], cb1, cdKM[r]))))
                    for i in range(len(ev))]
        cosm = float(np.mean((l2norm(E1) * Mv).sum(1)))
        log(f"map-and-republish: cos TB giữa vector ánh xạ và embedding E1 thật = {cosm:.3f} ({time.time() - t0:.0f}s)")

    # ---------------- tự kiểm placement học với 10 (index native ở f = 1, như E1ONLY)
    pre = "" if ds == "code" else f"{ds}_"
    check10, nat1 = None, None
    if a.e1_place != "u":
        allon = np.ones(N, dtype=bool)
        acc = dict(reach=[], final=[], rr=[], cand=[], nodes=[])
        for i in range(len(ev)):
            g = set(gt5_all[ev[i]].tolist())
            n_, lst_, _ = sides_K[i].ranked(allon, a.kappa, 20)
            acc["reach"].append(len(set(sides_K[i].reach_set().tolist()) & g) / 5.0)
            acc["final"].append(len(set(lst_[:5].tolist()) & g) / 5.0)
            acc["rr"].append(mc.rerank_hits(lst_[:20], E1, q1all[i], g))
            acc["cand"].append(n_); acc["nodes"].append(len(sides_K[i].touched()))
        nat1 = dict(reach_r5=100 * float(np.mean(acc["reach"])), final_r5=100 * float(np.mean(acc["final"])),
                    rr20=100 * float(np.mean(acc["rr"])), cand=float(np.mean(acc["cand"])),
                    nodes=float(np.mean(acc["nodes"])))
        log(f"index native {a.e1_place} ở f = 1: reach={nat1['reach_r5']:.1f} final={nat1['final_r5']:.1f} "
            f"rr20={nat1['rr20']:.1f} ứng viên={nat1['cand']:.0f} peer={nat1['nodes']:.0f}")
        f10 = f"probeP_{pre}{a.tag}_s{a.seed}.json" if a.check_10 == "auto" else a.check_10
        if f10 != "none" and os.path.exists(f10):
            P = json.load(open(f10))
            same = all(P["argv"].get(k) == v for k, v in (("nodes", a.nodes), ("nq", a.nq), ("frac", a.frac),
                                                          ("k_query", a.k_query), ("kappa", a.kappa), ("cbits", a.cbits),
                                                          ("dsub", a.dsub), ("k_pca", a.k_pca), ("itq_iters", a.itq_iters)))
            r10 = P["variants"].get(a.e1_place, {}).get("results", {}).get(str(a.tables), {}).get(str(T))
            if same and r10 is not None:
                bad10 = [(k, r10[k], nat1[k]) for k in nat1 if abs(r10[k] - nat1[k]) > 1e-9]
                check10 = dict(file=f10, n=len(nat1), bad=len(bad10), diffs=bad10)
                log(f">>> placement {a.e1_place} so với 10 ({f10}, L={a.tables}, T={T}): {len(nat1)} giá trị, "
                    f"{'KHỚP' if not bad10 else f'{len(bad10)} LỆCH {bad10}'}")
            else:
                log(f">>> không tự kiểm được placement với {f10} (tham số khác hoặc thiếu biến thể)")
        else:
            log(f">>> bỏ qua tự kiểm placement với 10 ({f10} không có)")

    rng = np.random.RandomState(a.seed + 41)
    order = rng.permutation(len(ev))
    pool_q = order[:len(ev) - a.n_heldout]
    held_q = order[len(ev) - a.n_heldout:]
    bg_order = perm[nS:]
    Rk = a.R

    # ---------------- churn và lỗi peer (đợt 9): lịch sự kiện dùng chung cho mọi chính sách của một cấu hình
    LS = dict(L0=None, LK=None, LM=None, LKM=None)               # bản ghi đã mất của run đang chạy, (L, N) mỗi phía
    IX = {}

    def setup_churn(ac):
        """-> (churn_on, ev_pos, reps, churn_info) cho các tham số churn trong ac."""
        on = ac.churn_min > 0 or ac.fail_at >= 0
        if not on:
            return False, {}, set(), None
        if not IX:
            IX["0"] = placement_index(anchors0, a.nodes)
            IX["K"] = placement_index(anchorsK, a.nodes)
            IX["M"] = placement_index(anchorsM, a.nodes) if anchorsM is not None else None
        deps, rp = churn_schedule(ac)
        evp = {}
        for t_, dn in deps.items():
            evp[t_] = (len(dn), placements_at(IX["0"], dn, N), placements_at(IX["K"], dn, N),
                       placements_at(IX["M"], dn, N) if IX["M"] is not None else None)
        ndep = int(sum(len(v) for v in deps.values()))
        info = dict(churn_min=ac.churn_min, median_session=ac.median_session, weibull_shape=ac.weibull_shape,
                    repair_every=ac.repair_every, repair_phase=ac.repair_phase, churn_step=ac.churn_step,
                    fail_at=ac.fail_at, fail_frac=ac.fail_frac, departures=ndep, n_events=len(deps),
                    repair_ts=sorted(rp), model="vị trí node giữ nguyên, chỉ mất bản ghi")
        log(f"churn: {ndep} lượt node rời mạng hoặc hỏng ({100 * ndep / a.nodes:.0f}% số node) qua {len(deps)} sự kiện, "
            f"{len(rp)} lần sửa {sorted(rp)[:8]}{' ...' if len(rp) > 8 else ''}")
        return True, evp, rp, info

    churn_on, ev_pos, reps, churn_info = setup_churn(a)

    def one_query(qi, act0, inE1):
        """-> final, rerank, record được tải payload, nodes, moved, danh sách native, gợi ý (record chỉ có ở E0)."""
        sA, sK, gq, q1v = sides_A[qi], sides_K[qi], gt5_all[ev[qi]], Q1[ev[qi]]
        has0, has1 = bool(act0.any()), bool(inE1.any())
        share1 = float(inE1.mean())
        dual_any = bool((act0 & inE1).any())
        if dual_any and a.dual_slots == "bonus":
            # object dual không chiếm chỗ: client đọc tiếp danh sách E0 tới khi đủ Rk record chỉ có ở E0
            n0, l0, x0 = ranked_lost(sA, act0, LS["L0"], a.kappa, a.bonus_mult * Rk)
            l0, x0 = np.asarray(l0, dtype=np.int64), np.asarray(x0)
            only = ~inE1[l0]
            cut = len(l0) if only.sum() < Rk else int(np.flatnonzero(only)[Rk - 1]) + 1
            l0, x0 = l0[:cut], x0[:cut]
        else:
            n0, l0, x0 = ranked_lost(sA, act0, LS["L0"], a.kappa, Rk)
        n1, l1, y1 = ranked_lost(sK, inE1, LS["LK"], a.kappa, Rk)
        l0, x0 = np.asarray(l0, dtype=np.int64), np.asarray(x0)
        l1f = np.asarray(l1, dtype=np.int64)              # danh sách tìm được qua khoá E1 (dùng để xác nhận)
        ex_all = l0[inE1[l0]] if len(l0) else l0          # object dual nhận từ phía E0 (thêm byte trả về)
        if len(l0):
            dm = inE1[l0]                                 # object dual trả về từ phía E0
            if dm.any():
                ex = l0[dm & ~np.isin(l0, l1f)]
                if a.dual_score == "e1code" and len(ex):
                    # peer E0 giữ thêm mã PQ E1 của record đã nâng cấp: client chấm ADC native như phía E1
                    q1n = q1all[qi]
                    kk = np.concatenate([-mc.adc_l2(q1n, cb1, cd1[l1f]), -mc.adc_l2(q1n, cb1, cd1[ex])])
                    yy = np.concatenate([np.asarray(y1), mc.adc_ip(q1n, cb1, cd1[ex])])
                    ids = np.concatenate([l1f, ex])
                    o = np.argsort(-kk, kind="stable")
                    l1, y1 = ids[o], yy[o]
                    l0, x0 = l0[~dm], x0[~dm]
                elif a.dual_score == "e1code":
                    l0, x0 = l0[~dm], x0[~dm]
                else:                                     # adapter: bản E0 giữ điểm adapter, bỏ bản trùng với native
                    keep = ~np.isin(l0, l1f)
                    l0, x0 = l0[keep], x0[keep]
        lst = mc.fuse("PROB", l0, x0, l1, y1, Rk, 1.0 - share1, share1, cal)
        g = set(np.asarray(gq).tolist())
        fin = len(set(lst[:5].tolist()) & g) / 5.0
        pool = np.asarray(lst[:Rk], dtype=np.int64)
        nat = inE1[pool] & np.isin(pool, l1)             # có điểm ADC native (qua khoá E1 hoặc mã E1 ở peer E0)
        fet = ~nat                                       # phải tải payload và nhúng lại
        sc = np.full(len(pool), -np.inf, dtype=np.float64)
        if fet.any():
            sc[fet] = E1[pool[fet]] @ q1v
        if nat.any():
            ymap = dict(zip(np.asarray(l1).tolist(), np.asarray(y1).tolist()))
            sc[nat] = [ymap[x] for x in pool[nat].tolist()]
        ordr = np.argsort(-sc, kind="stable")
        top = pool[ordr[:5]]
        rr = len(set(top.tolist()) & g) / 5.0
        if gold is not None:
            gq0 = int(gold[ev[qi]])
            gfr = (float(gq0 in set(lst[:5].tolist())), float(gq0 in set(top.tolist())))
        else:
            gfr = (float("nan"), float("nan"))
        tA, tK = sA.touched(), sK.touched()
        nodes = (len(tA) if has0 else 0) + (len(tK) if has1 else 0)
        moved = ((np.minimum(load["0"][tA], a.kappa).sum() if has0 else 0)
                 + (np.minimum(load["K"][tK], a.kappa).sum() if has1 else 0))
        hints = pool[fet & ~inE1[pool]]
        nbonus = int(len(ex_all))
        scan = (n0 if has0 else 0) + (n1 if has1 else 0)   # record còn hoạt động mà các peer được hỏi phải chấm
        return fin, rr, pool[fet], nodes, int(moved), l1f, hints, nbonus, gfr, int(scan)

    def one_query_map(qi, inE1, mapped):
        """mapall: chỉ còn phía E1 (record thật và record ánh xạ trên cùng placement). Cùng kiểu trả về với one_query."""
        sKM, gq, q1v = sides_KM[qi], gt5_all[ev[qi]], Q1[ev[qi]]
        n1, l, y = ranked_lost(sKM, np.concatenate([inE1, mapped]), LS["LKM"], a.kappa, Rk)
        l, y = np.asarray(l, dtype=np.int64), np.asarray(y, dtype=np.float64)
        ism = l >= N
        lst = np.where(ism, l - N, l)
        g = set(np.asarray(gq).tolist())
        fin = len(set(lst[:5].tolist()) & g) / 5.0
        pool, fet = lst[:Rk], ism[:Rk]
        sc = y[:Rk].copy()
        if fet.any():
            sc[fet] = E1[pool[fet]] @ q1v                # record ánh xạ: tải payload, chấm cosine M1 thật
        ordr = np.argsort(-sc, kind="stable")
        top = pool[ordr[:5]]
        rr = len(set(top.tolist()) & g) / 5.0
        if gold is not None:
            gq0 = int(gold[ev[qi]])
            gfr = (float(gq0 in set(lst[:5].tolist())), float(gq0 in set(top.tolist())))
        else:
            gfr = (float("nan"), float("nan"))
        tK = sKM.touched()
        moved = np.minimum(load["K"][tK], a.kappa).sum()
        return (fin, rr, pool[fet], len(tK), int(moved), np.zeros(0, dtype=np.int64), pool[fet], 0, gfr, int(n1))

    def one_query_mapkeep(qi, act0, inE1, mapped):
        """mapkeep: phía E1 gồm record thật và record ánh xạ (như mapall), phía E0 còn hoạt động tới khi object được
        thay. Object thấy qua phía E1 bị bỏ khỏi danh sách E0; phía E0 đọc tiếp tới đủ Rk record. Cùng kiểu trả về."""
        sA, sKM, gq, q1v = sides_A[qi], sides_KM[qi], gt5_all[ev[qi]], Q1[ev[qi]]
        has0 = bool(act0.any())
        n1, lv, y1 = ranked_lost(sKM, np.concatenate([inE1, mapped]), LS["LKM"], a.kappa, Rk)
        lv, y1 = np.asarray(lv, dtype=np.int64), np.asarray(y1, dtype=np.float64)
        ism = lv >= N
        l1 = np.where(ism, lv - N, lv)
        n0, l0, x0 = ranked_lost(sA, act0, LS["L0"], a.kappa, a.bonus_mult * Rk)
        l0, x0 = np.asarray(l0, dtype=np.int64), np.asarray(x0)
        if len(l0):
            keep = ~np.isin(l0, l1)
            l0, x0 = l0[keep][:Rk], x0[keep][:Rk]
        share1 = float((inE1 | mapped).mean())
        lst = mc.fuse("PROB", l0, x0, l1, y1, Rk, 1.0 - share1, share1, cal)
        g = set(np.asarray(gq).tolist())
        fin = len(set(lst[:5].tolist()) & g) / 5.0
        pool = np.asarray(lst[:Rk], dtype=np.int64)
        natl = l1[~ism]                                  # record E1 thật tìm qua khoá E1: có điểm ADC native
        nat = np.isin(pool, natl)
        fet = ~nat
        sc = np.full(len(pool), -np.inf, dtype=np.float64)
        if fet.any():
            sc[fet] = E1[pool[fet]] @ q1v
        if nat.any():
            ymap = dict(zip(natl.tolist(), y1[~ism].tolist()))
            sc[nat] = [ymap[x] for x in pool[nat].tolist()]
        ordr = np.argsort(-sc, kind="stable")
        top = pool[ordr[:5]]
        rr = len(set(top.tolist()) & g) / 5.0
        if gold is not None:
            gq0 = int(gold[ev[qi]])
            gfr = (float(gq0 in set(lst[:5].tolist())), float(gq0 in set(top.tolist())))
        else:
            gfr = (float("nan"), float("nan"))
        tA, tK = sA.touched(), sKM.touched()
        nodes = (len(tA) if has0 else 0) + len(tK)
        moved = ((np.minimum(load["0"][tA], a.kappa).sum() if has0 else 0) + np.minimum(load["K"][tK], a.kappa).sum())
        hints = pool[fet & ~inE1[pool]]
        scan = (n0 if has0 else 0) + n1
        return fin, rr, pool[fet], nodes, int(moved), np.zeros(0, dtype=np.int64), hints, 0, gfr, int(scan)

    load = {}

    def publish(docs, inE1, act0, retire):
        docs = np.asarray([x for x in np.unique(docs) if not inE1[x]], dtype=np.int64)
        if len(docs):
            inE1[docs] = True
            np.add.at(load["K"], anchorsK[:, docs].ravel(), 1)
            if LS["LK"] is not None:
                LS["LK"][:, docs] = False                # bản E1 vừa công bố nằm ở node đang sống
            if retire:
                retire_e0(docs, act0)
        return docs

    def retire_e0(docs, act0):
        docs = np.asarray([x for x in np.unique(docs) if act0[x]], dtype=np.int64)
        if len(docs):
            act0[docs] = False
            np.subtract.at(load["0"], anchors0[:, docs].ravel(), 1)
        return docs

    def simulate(stream, policy, bg_rate=0.0, confirm=0):
        inE1 = np.zeros(N, dtype=bool); inE1[S] = True
        act0 = ~inE1
        mapped = np.zeros(N, dtype=bool)
        if policy == "full":                             # dựng lại toàn bộ: mọi record E1 thật, E0 gỡ hết
            inE1[:] = True; act0[:] = False
        elif policy == "mapall":                         # map-and-republish: record ánh xạ cho mọi object ngoài S
            mapped = ~inE1; act0[:] = False
        elif policy == "mapkeep":                        # như mapall nhưng giữ E0 tới khi object được thay
            mapped = ~inE1
        maplike = policy in ("mapall", "mapkeep")
        load["0"] = np.bincount(anchors0[:, act0].ravel(), minlength=a.nodes)
        load["K"] = np.bincount(anchorsK[:, inE1].ravel(), minlength=a.nodes)
        if maplike:
            load["K"] = load["K"] + np.bincount(anchorsM[:, mapped].ravel(), minlength=a.nodes)
        for k_ in LS:
            LS[k_] = None
        if churn_on:                                     # mọi bản ghi còn nguyên lúc t = 0
            LS["L0"] = np.zeros((a.tables, N), dtype=bool)
            if maplike:
                LS["LKM"] = np.zeros((a.tables, 2 * N), dtype=bool)
                LS["LK"], LS["LM"] = LS["LKM"][:, :N], LS["LKM"][:, N:]
            else:
                LS["LK"] = np.zeros((a.tables, N), dtype=bool)
        cst = dict(repair_w=0, keepalive=0, dep=0, lost_max=0.0)

        def qfun(qi):
            if policy == "mapall":
                return one_query_map(qi, inE1, mapped)
            if policy == "mapkeep":
                return one_query_mapkeep(qi, act0, inE1, mapped)
            return one_query(qi, act0, inE1)

        def churn_tick(t):
            """Sự kiện churn trước lượt t: node rời mạng hoặc hỏng mất bản ghi, rồi sửa chữa nếu tới chu kỳ."""
            e = ev_pos.get(t)
            if e is not None:
                cst["dep"] += e[0]
                (t0_, d0_), (tK_, dK_) = e[1], e[2]
                LS["L0"][t0_, d0_] = True
                LS["LK"][tK_, dK_] = True
                if LS["LM"] is not None and e[3] is not None:
                    LS["LM"][e[3][0], e[3][1]] = True
            if t in reps:
                for lost, actv in ((LS["L0"], act0), (LS["LK"], inE1), (LS["LM"], mapped)):
                    if lost is None or not actv.any():
                        continue
                    sub = lost[:, actv]
                    nl = int(sub.sum())
                    cst["repair_w"] += nl; cst["keepalive"] += int(sub.size) - nl
                    lost[:, actv] = False

        def churn_snap():
            p0 = act0 & (~LS["L0"]).any(0)
            pK = inE1 & (~LS["LK"]).any(0)
            pM = (mapped & (~LS["LM"]).any(0)) if LS["LM"] is not None else np.zeros(N, dtype=bool)
            lo = 100 * float((~(p0 | pK | pM)).mean())
            cst["lost_max"] = max(cst["lost_max"], lo)
            return dict(alive0=100 * float(p0.sum()) / max(1, int(act0.sum())),
                        aliveK=100 * float(pK.sum()) / max(1, int(inE1.sum())), lost_obj=lo)
        conf = np.zeros(N, dtype=np.int32)
        seen = np.zeros(len(ev), dtype=bool)
        ptr, accb = 0, 0.0
        rec = {k: [] for k in ("final", "rr", "fetch", "new", "nodes", "moved", "f", "rep", "gtE1",
                               "rep_exact", "qlen", "dual", "act0", "conf", "retired", "bonus", "gf", "gr", "scan",
                               "mapped")}
        snaps = {}
        lazyish = policy in ("lazy", "lazyD") or policy.startswith("lazyV")
        for t in range(len(stream) + 1):
            if churn_on:
                churn_tick(t)
            if t in cps:
                hs = [qfun(h) for h in held_q]
                snaps[str(t)] = dict(final=100 * np.mean([h[0] for h in hs]), rr=100 * np.mean([h[1] for h in hs]),
                                     f=float(inE1.mean()), dual=float((inE1 & act0).mean()),
                                     gold_final=100 * float(np.mean([h[8][0] for h in hs])),
                                     gold_rr=100 * float(np.mean([h[8][1] for h in hs])),
                                     scan=float(np.mean([h[9] for h in hs])), mapped=float(mapped.mean()))
                if churn_on:
                    snaps[str(t)].update(churn_snap())
            if t == len(stream):
                break
            qi = int(stream[t])
            gq = gt5_all[ev[qi]]
            gtE1 = float(inE1[np.asarray(gq)].mean())
            fin, rr, fetched, nodes, moved, l1, hints, nbonus, gfr, scan = qfun(qi)
            new, nconf, nret = 0, 0, 0
            if maplike:                                  # re-indexer thay record ánh xạ vừa tải bằng record E1 thật
                docs = np.asarray([x for x in np.unique(hints) if mapped[x]], dtype=np.int64)
                if len(docs):
                    mapped[docs] = False; inE1[docs] = True
                    np.subtract.at(load["K"], anchorsM[:, docs].ravel(), 1)
                    np.add.at(load["K"], anchorsK[:, docs].ravel(), 1)
                    if LS["LK"] is not None:
                        LS["LK"][:, docs] = False
                    if policy == "mapkeep":              # bản E0 retire khi đã có record E1 thật
                        retire_e0(docs, act0)
                new += len(docs)
            if lazyish:
                if policy.startswith("lazyV"):
                    dl = l1[inE1[l1] & act0[l1]]          # object dual mà native vừa tìm thấy
                    if len(dl):
                        conf[dl] += 1; nconf = len(dl)
                        nret = len(retire_e0(dl[conf[dl] >= confirm], act0))
                mg = publish(hints if policy != "lazy" else fetched, inE1, act0, retire=(policy == "lazy"))
                new += len(mg)
            if policy in ("bg", "bgV", "lazyVbg", "lazyVbgD"):
                accb += bg_rate
                k = int(accb); accb -= k
                take = []
                while len(take) < k and ptr < len(bg_order):
                    x = int(bg_order[ptr]); ptr += 1
                    if not inE1[x]:
                        take.append(x)
                new += len(publish(take, inE1, act0, retire=(policy != "lazyVbgD")))
            for kk, v in (("final", fin), ("rr", rr), ("fetch", len(fetched)), ("new", new), ("nodes", nodes),
                          ("moved", moved), ("f", float(inE1.mean())), ("rep", bool(seen[qi])), ("gtE1", gtE1),
                          ("rep_exact", bool(seen[qi])), ("qlen", 0), ("dual", float((inE1 & act0).mean())),
                          ("act0", float(act0.mean())), ("conf", nconf), ("retired", nret), ("bonus", nbonus),
                          ("gf", gfr[0]), ("gr", gfr[1]), ("scan", scan), ("mapped", float(mapped.mean()))):
                rec[kk].append(v)
            seen[qi] = True
        if churn_on:
            ns = max(1, len(stream))
            rec["_churn"] = dict(repair_w=cst["repair_w"] / ns, keepalive=cst["keepalive"] / ns, departures=cst["dep"],
                                 lost_obj_end=snaps[str(max(int(k) for k in snaps))].get("lost_obj", float("nan")),
                                 lost_obj_max=cst["lost_max"])
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
                            moved=float(np.mean(rec["moved"][sl])), gtE1=100 * float(np.mean(rec["gtE1"][sl])),
                            dual=100 * float(rec["dual"][e - 1])))
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
                    gtE1=100 * float(np.mean(rec["gtE1"])),
                    dual_end=100 * float(rec["dual"][-1]), dual_mean=100 * float(np.mean(rec["dual"])),
                    act0_end=100 * float(rec["act0"][-1]), conf_total=int(np.sum(rec["conf"])),
                    retired_total=int(np.sum(rec["retired"])), dual_from_e0=float(np.mean(rec["bonus"])),
                    gold_final=100 * float(np.mean(rec["gf"])), gold_rr=100 * float(np.mean(rec["gr"])),
                    scan=float(np.mean(rec["scan"])), mapped_end=100 * float(rec["mapped"][-1]))

    out = dict(argv=vars(a), N=int(N), n_sample=int(nS), cal=ols_ad, sig1=sig1, runs={}, check_06=None,
               check_10=check10, native_f1=nat1, numpy=np.__version__, e1_storage=stK)
    if churn_on:
        out["churn"] = churn_info
    def run_set(zl, pols, suffix):
        """Chạy mọi chính sách trong pols cho từng Zipf trong zl với trạng thái churn hiện tại; tên run thêm suffix."""
        for z in zl:
            ranks = np.random.RandomState(a.seed + 43).permutation(len(pool_q))
            p = 1.0 / (ranks + 1.0) ** z
            p /= p.sum()
            stream = pool_q[np.random.RandomState(a.seed + 47 + int(1000 * z)).choice(len(pool_q), size=a.stream, p=p)]
            log(f"\n=== Zipf s = {z:g}" + (f"   [cấu hình churn {suffix[1:]}]" if suffix else ""))
            done = {}
            plan = []
            for pol in pols:
                if pol == "lazyV":
                    plan += [(f"lazyV{c}", "lazyV", c, None) for c in confirms]
                elif pol == "bgV":
                    plan += [(f"bgV{c}", "bgV", 0, f"lazyV{c}") for c in confirms]
                elif pol == "bg":
                    plan.append(("bg", "bg", 0, "lazy"))
                elif pol in ("lazyVbg", "lazyVbgD"):
                    plan.append((pol, pol, confirms[0], ("lazy", f"lazyV{confirms[0]}")))
                else:
                    plan.append((pol, pol, 0, None))
            for name, pol, c, need in plan:
                rate = 0.0
                if isinstance(need, tuple):                   # lazyVbg: bù cho đủ số record lazy công bố
                    if any(x not in done for x in need):
                        log(f"  ({name} cần {need}) bỏ qua"); continue
                    rate = max(0.0, (done[need[0]]["f"][-1] - done[need[1]]["f"][-1]) * N / a.stream)
                elif need is not None:
                    if need not in done:
                        log(f"  ({name} cần {need}) bỏ qua"); continue
                    rate = (done[need]["f"][-1] * N - nS) / a.stream
                pol_run = f"lazyV{c}" if pol == "lazyV" else pol
                rec, snaps = simulate(stream, pol_run, rate, confirm=c)
                done[name] = rec
                tt = totals(rec); tt["bg_rate"] = rate
                if pol == "full":
                    tt["reembed_t0"] = int(N - nS)
                if pol in ("mapall", "mapkeep"):
                    tt["republish_t0"] = int(N - nS)
                if "_churn" in rec:
                    tt.update(rec["_churn"])
                w = windows(rec, a.window)
                out["runs"][f"z{z:g}|PROB|{name}{suffix}"] = dict(zipf=z, policy=name, totals=tt, windows=w,
                                                                  snapshots=snaps)
                log(f"  {name:7s} final={tt['final']:5.1f} rerank={tt['rr']:5.1f} tải/query={tt['fetch']:4.1f} "
                    f"record mới/query={tt['new']:4.2f} f cuối={100 * tt['f_end']:4.1f}% dual cuối={tt['dual_end']:4.1f}% "
                    f"(TB {tt['dual_mean']:4.1f}%) E0 còn={tt['act0_end']:4.1f}% xác nhận={tt['conf_total']} "
                    f"retire={tt['retired_total']} dual từ E0/query={tt['dual_from_e0']:4.1f} chấm/query={tt['scan']:7.0f}  "
                    f"[{time.time() - t0:.0f}s]")
                log("     giữ riêng " + " ".join(f"t{k2}:{v['final']:4.1f}/{v['rr']:4.1f}" for k2, v in snaps.items()))
                if "_churn" in rec:
                    c_ = rec["_churn"]
                    log(f"     churn: ghi sửa {c_['repair_w']:.1f}/query, keep-alive {c_['keepalive']:.0f}/query, "
                        f"mất mọi đường cuối dòng {c_['lost_obj_end']:.2f}% (lớn nhất {c_['lost_obj_max']:.2f}%), "
                        "E0 còn bản " + " ".join(f"t{k2}:{v['alive0']:.1f}" for k2, v in snaps.items()))

    run_set(zipfs, a.policies.split(","), "")
    # cấu hình churn bổ sung trong cùng job (đợt 9): dùng chung phần dựng index và định tuyến ở trên
    csets = parse_churn_sets(a.churn_sets)
    if csets:
        out["churn_sets"] = {}
        cpols = (a.churn_policies or a.policies).split(",")
        czipf = [float(z) for z in (a.churn_zipf or a.zipf).split(",")]
        for cname, cd in csets:
            ac = argparse.Namespace(**{**vars(a), **cd})
            churn_on, ev_pos, reps, info_c = setup_churn(ac)
            out["churn_sets"][cname] = info_c
            run_set(czipf, cpols, "|" + cname)
        churn_on, ev_pos, reps, _ = setup_churn(a)

    # ---------------- tự kiểm với 06
    f06 = (f"probeL_{pre}{a.tag}_s{a.seed}_ku.json" if a.check_06 == "auto" else a.check_06)
    if a.e1_place != "u":
        log(">>> bỏ qua tự kiểm với 06 (placement E1 khác bài)")
    elif f06 != "none" and os.path.exists(f06):
        old = json.load(open(f06))
        n, bad = 0, 0
        diffs = []

        def isbad(x, y):
            return not (abs(x - y) <= 1e-9 or (x != x and y != y))
        for pol in ("static", "lazy", "bg"):
            for z in zipfs:
                k = f"z{z:g}|PROB|{pol}"
                if k in old.get("runs", {}) and k in out["runs"]:
                    r, nw = old["runs"][k], out["runs"][k]
                    for kk, v in r["totals"].items():
                        if kk in nw["totals"] and kk not in ("qlen_mean", "qlen_end"):
                            n += 1
                            if isbad(nw["totals"][kk], v):
                                bad += 1; diffs.append((k, "totals", kk, v, nw["totals"][kk]))
                    for wi, (x, y) in enumerate(zip(r["windows"], nw["windows"])):
                        for kk in ("final", "rr", "fetch", "new", "f", "gtE1"):
                            n += 1
                            if isbad(x[kk], y[kk]):
                                bad += 1; diffs.append((k, f"window{wi}", kk, x[kk], y[kk]))
                    for t_, sv in r.get("snapshots", {}).items():
                        if t_ in nw["snapshots"]:
                            for kk in ("final", "rr", "f"):
                                n += 1
                                if isbad(sv[kk], nw["snapshots"][t_][kk]):
                                    bad += 1; diffs.append((k, f"snap{t_}", kk, sv[kk], nw["snapshots"][t_][kk]))
        out["check_06"] = dict(file=f06, n=n, bad=int(bad), diffs=diffs[:10])
        log(f">>> so với 06 ({f06}): {n} giá trị, {'KHỚP' if bad == 0 and n > 0 else f'{bad} LỆCH'}")
        for dd in diffs[:10]:
            log(f"    lệch: {dd}")
    else:
        log(f">>> bỏ qua tự kiểm với 06 ({f06} không có)")

    # ---------------- tự kiểm với một lượt cũ của chính 11
    out["check_prev"] = None
    if a.check_prev != "none":
        if os.path.exists(a.check_prev):
            old = json.load(open(a.check_prev))
            n, bad, diffs = 0, 0, []

            def isbad2(x, y):
                if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    return not (abs(x - y) <= 1e-9 or (x != x and y != y))
                return x != y
            for k, r in old.get("runs", {}).items():
                if k not in out["runs"]:
                    continue
                nw = out["runs"][k]
                parts = [("totals", r["totals"], nw["totals"])]
                parts += [(f"window{wi}", x, y) for wi, (x, y) in enumerate(zip(r["windows"], nw["windows"]))]
                parts += [(f"snap{t_}", sv, nw["snapshots"].get(t_, {})) for t_, sv in r.get("snapshots", {}).items()]
                for lab, x, y in parts:
                    for kk, v in x.items():
                        if kk in y:
                            n += 1
                            if isbad2(v, y[kk]):
                                bad += 1; diffs.append((k, lab, kk, v, y[kk]))
            out["check_prev"] = dict(file=a.check_prev, n=n, bad=int(bad), diffs=diffs[:10])
            log(f">>> so với lượt cũ ({a.check_prev}): {n} giá trị, {'KHỚP' if bad == 0 and n > 0 else f'{bad} LỆCH'}")
            for dd in diffs[:10]:
                log(f"    lệch: {dd}")
        else:
            log(f">>> không có {a.check_prev} để so với lượt cũ")

    fn = a.out or f"probeV_{pre}{a.tag}_s{a.seed}.json"
    json.dump(out, open(fn, "w"), indent=1)
    log(f"\n-> {fn}   ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
