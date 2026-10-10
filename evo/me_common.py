#!/usr/bin/env python3
"""
me_common.py  —  phần dùng chung cho 04b_probe_multiepoch2.py và 06_probe_lazy.py.

  route_keys  : node của từng khoá probe, giữ theo (bảng, probe) để cắt được ngân sách probe T
  Side2       : một phía tra cứu cho một query. Điểm tính một lần trên tập reachable ứng với
                ngân sách đầy đủ; ngân sách nhỏ hơn lấy tập con, không tính lại.
  Cách gộp hai danh sách rời nhau (mỗi record chỉ ở một epoch), mọi cách đều giữ nguyên thứ tự
  bên trong từng danh sách:
    RRF   xen kẽ theo hạng (RRF k = 60 suy biến thành xen kẽ khi hai danh sách rời nhau), như 04
    CAL   so điểm E0 đã hồi quy OLS về thang E1, như 04 (hiệu chỉnh trên chính mẫu S)
    PROP  hạng toàn cục ước lượng: phần tử hạng r của partition chiếm tỉ lệ s đứng ở r / s
    SD    như CAL nhưng khớp trung bình và độ lệch chuẩn thay vì hồi quy (không co về trung bình)
    PROB  xác suất thuộc top-5 toàn cục: điểm thật của record E0 ~ N(a·x + b, sigma0), của record
          E1 ~ N(y, sigma1); ngưỡng tau của từng query giải từ tổng xác suất = 5
  Hiệu chỉnh của adapter cho SD và PROB làm theo cross-fit: mỗi document hiệu chỉnh được chấm bởi
  ánh xạ học trên phần còn lại, nên điểm không in-sample.
"""
import importlib.util, os
import numpy as np
np.seterr(invalid='ignore', divide='ignore')

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("q3", os.path.join(_here, "03_probe_query_adapter.py"))
q3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q3)
pb = q3.pb
log, l2norm = pb.log, pb.l2norm

LAMS = (1e-3, 1e-2, 1e-1, 1.0, 10.0)


# ----------------------------------------------------------------- định tuyến
def route_keys(qv, P_list, nid, K, T, cbits):
    """(Q, L, T, K): node gần nhất theo XOR của từng khoá probe. Tập node bị chạm với ngân sách
    t <= T là np.unique(nodes[q, :, :t, :]); với t = T trùng route() của 04."""
    pk = pb.probe_keys_for(qv, P_list, T, cbits)          # L phần tử (Q, T)
    keys = np.stack(pk, axis=1)                            # (Q, L, T)
    Q, L, TT = keys.shape
    return pb.knn_nodes(keys.reshape(-1), nid, K).reshape(Q, L, TT, K)


def adc_l2(q, cb, codes):
    m = cb.shape[0]
    return pb.adc_lut(q, cb)[np.arange(m)[None, :], codes].sum(1)


def adc_ip(q, cb, codes):
    m = cb.shape[0]
    lut = (q.reshape(m, -1)[:, None, :] * cb).sum(2)
    return lut[np.arange(m)[None, :], codes].sum(1)


def kappa_positions(order, anchors, mask, kappa, need):
    """Như q3.kappa_union nhưng trả về VỊ TRÍ trong `order` của các document client nhận được
    (mỗi node bị chạm chỉ trả top-kappa của nó). Giống hệt bản trong 04."""
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


class Side2:
    """Một phía tra cứu cho một query.
    score_fn(reach) -> (key, x): key là điểm xếp hạng tại node (lớn hơn là tốt hơn), x là điểm thô
    dùng khi gộp (cosine dự đoán trong không gian M1 với adapter, cosine M0 với dual, cosine ADC
    trong M1 với phía E1)."""

    def __init__(self, nodes_ltk, anchors, n_nodes, score_fn):
        self.nodes = nodes_ltk
        self.Tmax = nodes_ltk.shape[1]
        self.anchors = anchors
        self.n_nodes = n_nodes
        touched = np.unique(nodes_ltk)
        mask = np.zeros(n_nodes, dtype=bool); mask[touched] = True
        self.reach = np.flatnonzero(mask[anchors].any(0))
        self.key, self.x = score_fn(self.reach)
        self._b = {self.Tmax: (touched, mask, None)}

    def budget(self, t=None):
        t = self.Tmax if (t is None or t >= self.Tmax) else int(t)
        if t not in self._b:
            touched = np.unique(self.nodes[:, :t, :])
            mask = np.zeros(self.n_nodes, dtype=bool); mask[touched] = True
            sel = mask[self.anchors[:, self.reach]].any(0)
            self._b[t] = (touched, mask, sel)
        return self._b[t]

    def touched(self, t=None):
        return self.budget(t)[0]

    def reach_set(self, t=None):
        sel = self.budget(t)[2]
        return self.reach if sel is None else self.reach[sel]

    def ranked(self, active, kappa, need, t=None):
        """-> (số ứng viên reachable còn hoạt động, danh sách client nhận theo thứ tự, điểm x tương ứng)"""
        touched, mask, sel = self.budget(t)
        a = active[self.reach] if sel is None else (active[self.reach] & sel)
        r, k, x = self.reach[a], self.key[a], self.x[a]
        o = np.argsort(-k)
        order = r[o]
        pos = kappa_positions(order, self.anchors, mask, kappa, need)
        return len(r), order[pos], x[o][pos]


# ----------------------------------------------------------------- gộp
def interleave(l1, l0, n):
    out, i = [], 0
    while len(out) < n and (i < len(l1) or i < len(l0)):
        if i < len(l1): out.append(int(l1[i]))
        if i < len(l0) and len(out) < n: out.append(int(l0[i]))
        i += 1
    return np.asarray(out[:n], dtype=np.int64)


def merge2(l0, a0, l1, a1, n, b0=None, b1=None):
    """Gộp hai danh sách đã xếp hạng, giữ thứ tự bên trong; mỗi bước lấy đầu danh sách có khoá a
    lớn hơn, hoà thì so khoá phụ b, vẫn hoà thì E1 trước. Không có b thì trùng merge_cal của 04."""
    out, i, j = [], 0, 0
    n0, n1 = len(l0), len(l1)
    while len(out) < n and (i < n0 or j < n1):
        if j < n1 and (i >= n0 or a1[j] > a0[i]
                       or (a1[j] == a0[i] and (b0 is None or b1[j] >= b0[i]))):
            out.append(int(l1[j])); j += 1
        else:
            out.append(int(l0[i])); i += 1
    return np.asarray(out, dtype=np.int64)


def merge_prop(l0, l1, share0, share1, n):
    """Hạng toàn cục ước lượng r / s: một tập con ngẫu nhiên tỉ lệ s của corpus có phần tử hạng r
    nằm quanh hạng r / s của toàn corpus. Hai partition bằng nhau thì trùng xen kẽ."""
    k0 = -(np.arange(1, len(l0) + 1, dtype=np.float64) / max(share0, 1e-12))
    k1 = -(np.arange(1, len(l1) + 1, dtype=np.float64) / max(share1, 1e-12))
    return merge2(l0, k0, l1, k1, n)


def ncdf(z):
    """Hàm phân phối chuẩn, xấp xỉ erf Abramowitz-Stegun 7.1.26 (sai số tuyệt đối < 1.5e-7)."""
    z = np.asarray(z, dtype=np.float64)
    x = np.abs(z) / np.sqrt(2.0)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1.0 - ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t
               + 0.254829592) * t * np.exp(-x * x)
    return 0.5 * (1.0 + np.sign(z) * y)


_ZB = np.random.RandomState(20240917).standard_normal((128, 1024))   # số ngẫu nhiên chung, cố định


def prob_scores(m0, s0, m1, s1, k=5):
    """Xác suất mỗi record thuộc top-k toàn cục.
    Mô hình: điểm thật của record E0 ~ N(m0, s0^2) (m0 = a·x + b, s0 = độ lệch phần dư cross-fit),
    của record E1 ~ N(m1, s1^2) (s1 = sai số ADC, rất nhỏ). Ngưỡng tau = điểm lớn thứ k của toàn bộ
    record trong hai danh sách; phân phối của tau lấy bằng Monte Carlo 128 mẫu với số ngẫu nhiên
    cố định, rồi xấp xỉ tau ~ N(tbar, tsd^2) độc lập với từng record:
        P(record thuộc top-k) = Phi((m - tbar) / sqrt(s^2 + tsd^2)).
    Độ bất định của tau làm mềm bước nhảy của record E1 quanh ngưỡng."""
    m0 = np.asarray(m0, dtype=np.float64); m1 = np.asarray(m1, dtype=np.float64)
    n0, n1 = len(m0), len(m1)
    n = n0 + n1
    if n <= k:
        return np.ones(n0), np.ones(n1), float("nan"), 0.0
    Z = _ZB[:, :n] if n <= _ZB.shape[1] else np.random.RandomState(1).standard_normal((128, n))
    mu = np.concatenate([m0, m1])
    sd = np.concatenate([np.full(n0, s0), np.full(n1, s1)])
    Y = mu[None, :] + Z * sd[None, :]
    tau = np.partition(Y, n - k, axis=1)[:, n - k]
    tbar, tsd = float(tau.mean()), float(tau.std())
    p0 = ncdf((m0 - tbar) / np.sqrt(s0 ** 2 + tsd ** 2))
    p1 = ncdf((m1 - tbar) / np.sqrt(s1 ** 2 + tsd ** 2))
    return p0, p1, tbar, tsd


def merge_prob(l0, m0, s0, l1, m1, s1, n, k=5, diag=None):
    p0, p1, _, _ = prob_scores(m0, s0, m1, s1, k)
    if diag is not None:
        tot = p0.sum() + p1.sum()
        diag.append(float(k * p0.sum() / tot) if tot > 0 else float("nan"))
    return merge2(l0, p0, l1, p1, n, b0=np.asarray(m0, np.float64), b1=np.asarray(m1, np.float64))


def prob_fuse_p(l0, x0, l1, y1, n, cal):
    """PROB, trả thêm xác suất thuộc top-5 của từng phần tử trong danh sách gộp."""
    o = cal["ols"]
    m0 = o["a"] * np.asarray(x0, np.float64) + o["b"]
    m1 = np.asarray(y1, np.float64)
    p0, p1, _, _ = prob_scores(m0, o["sig"], m1, cal["sig1"])
    lst = merge2(l0, p0, l1, p1, n, b0=m0, b1=m1)
    pm = dict(zip(np.asarray(l0).tolist(), p0.tolist()))
    pm.update(zip(np.asarray(l1).tolist(), p1.tolist()))
    return lst, np.asarray([pm[d] for d in lst.tolist()], dtype=np.float64)


def fuse(kind, l0, x0, l1, y1, n, share0, share1, cal, diag=None):
    """kind: RRF | CAL | PROP | SD | PROB. x0: điểm thô phía E0, y1: điểm ADC phía E1.
    cal: dict hiệu chỉnh của phía E0 (a, b cho CAL lấy từ 04; ols cho SD/PROB; sig1).
    diag (list, tuỳ chọn): với PROB ghi số record E0 kỳ vọng trong top-5 theo mô hình."""
    if len(l1) == 0:
        return np.asarray(l0[:n], dtype=np.int64)
    if len(l0) == 0:
        return np.asarray(l1[:n], dtype=np.int64)
    if kind == "RRF":
        return interleave(l1, l0, n)
    if kind == "CAL":
        return merge2(l0, x0 * cal["cal_a"] + cal["cal_b"], l1, y1, n)
    if kind == "PROP":
        return merge_prop(l0, l1, share0, share1, n)
    o = cal["ols"]
    if kind == "SD":
        z = o["my"] + (o["sy"] / o["sx"]) * (np.asarray(x0, np.float64) - o["mx"])
        return merge2(l0, z, l1, np.asarray(y1, np.float64), n)
    if kind == "PROB":
        return merge_prob(l0, o["a"] * np.asarray(x0, np.float64) + o["b"], o["sig"],
                          l1, y1, cal["sig1"], n, diag=diag)
    raise ValueError(kind)


# ----------------------------------------------------------------- hiệu chỉnh
def fit_cal_04(x_rows, y_rows, top):
    """Y hệt fit_cal của 04 (float32, giữ để AD_CAL / DU_CAL tái lập đúng từng số)."""
    X, Y = [], []
    for x, y in zip(x_rows, y_rows):
        o = np.argsort(-x)[:top]
        X.append(x[o]); Y.append(y[o])
    X, Y = np.concatenate(X), np.concatenate(Y)
    A = np.stack([X, np.ones_like(X)], 1)
    a, b = np.linalg.lstsq(A, Y, rcond=None)[0]
    r = float(np.corrcoef(X, Y)[0, 1])
    return float(a), float(b), r


def ols_top(x_rows, y_rows, top):
    """Hồi quy y theo x trên vùng đầu bảng (mỗi query lấy `top` document có x cao nhất), float64.
    Trả về hệ số, độ lệch chuẩn phần dư và thống kê để khớp phương sai."""
    X, Y = [], []
    for x, y in zip(x_rows, y_rows):
        o = np.argsort(-x)[:top]
        X.append(np.asarray(x[o], np.float64)); Y.append(np.asarray(y[o], np.float64))
    X, Y = np.concatenate(X), np.concatenate(Y)
    A = np.stack([X, np.ones_like(X)], 1)
    a, b = np.linalg.lstsq(A, Y, rcond=None)[0]
    res = Y - (a * X + b)
    return dict(a=float(a), b=float(b), sig=float(max(res.std(ddof=2), 1e-6)),
                r=float(np.corrcoef(X, Y)[0, 1]), mx=float(X.mean()), sx=float(max(X.std(), 1e-9)),
                my=float(Y.mean()), sy=float(Y.std()), n=int(len(X)))


def fold_ids(n, folds, seed):
    rng = np.random.RandomState(seed + 31)
    f = np.empty(n, dtype=np.int64)
    f[rng.permutation(n)] = np.arange(n) % folds
    return f


def crossfit_adapter_x(E0, E1, C0, cb0, cd0, Qv, M, C, folds, seed):
    """Điểm adapter x = <q1·Wf^T, c_i> / ||c_i·Wf|| cho document trong C, mỗi fold của C chấm bằng Wf
    học trên M trừ chính fold đó. Trả về ma trận (len(Qv), len(C)) theo thứ tự của C."""
    fid = fold_ids(len(C), folds, seed)
    X = np.zeros((len(Qv), len(C)), dtype=np.float64)
    lam = []
    for k in range(folds):
        Ck = C[fid == k]
        if len(Ck) == 0:
            continue
        train = np.setdiff1d(M, Ck)
        Wk, lk = pb.fit_bridge(E0[train], E1[train], "ridge", seed)
        lam.append(lk)
        nk = np.linalg.norm(C0[Ck] @ Wk, axis=1)
        qh = Qv @ np.ascontiguousarray(Wk.T)
        qhn = l2norm(qh); qn = np.linalg.norm(qh, axis=1)
        cols = np.flatnonzero(fid == k)
        for i in range(len(Qv)):
            X[i, cols] = adc_ip(qhn[i], cb0, cd0[Ck]) / nk * qn[i]
    return X, lam


def e1_scores(Qv, cb1, cd1, docs):
    qv = l2norm(Qv)
    return np.stack([adc_ip(qv[i], cb1, cd1[docs]) for i in range(len(Qv))]).astype(np.float64)


def sigma_e1(Qv, E1, cb1, cd1, docs, top):
    """Độ lệch chuẩn giữa cosine ADC và cosine thật của record E1, trên vùng đầu bảng."""
    ya = e1_scores(Qv, cb1, cd1, docs)
    ye = l2norm(Qv) @ E1[docs].T
    d = []
    for i in range(len(Qv)):
        o = np.argsort(-ya[i])[:top]
        d.append(ye[i, o] - ya[i, o])
    return float(max(np.concatenate(d).std(), 1e-4))


# ----------------------------------------------------------------- phân bố tải
def load_stats(anchors, n_nodes, active=None):
    a = anchors if active is None else anchors[:, active]
    ld = np.bincount(a.ravel(), minlength=n_nodes)
    srt = np.sort(ld)[::-1]
    tot = max(1, int(ld.sum()))
    return dict(max=int(ld.max()), p99=float(np.percentile(ld, 99)), mean=float(ld.mean()),
                empty_frac=float((ld == 0).mean()),
                top1pct_share=float(srt[:max(1, n_nodes // 100)].sum() / tot))


def rerank_hits(cand, Eq, q, g, k=5):
    """Top-k theo cosine M1 thật trong `cand`, đúng cách tính của 04."""
    if len(cand) == 0:
        return 0.0
    top = cand[np.argsort(-(Eq[cand] @ q))[:k]]
    return len(set(top.tolist()) & g) / 5.0
