#!/usr/bin/env python3
"""Tổng hợp đợt 6 (thăm dò, sau góp ý của thầy). Chạy ở thư mục chứa các file probe*.json.

  A. Bảng 2x2 (probeE2F_*.json): lịch migrate từ probe hoặc từ lookup thật, recall đo bằng probe hoặc lookup thật,
     cho lazy, bg và lazy − bg; tách phần do cách đo và phần do lịch; mốc nhiễu từ lượt lịch thật + đo thật lần hai.
  B. bge-base 100k theo seed: lazy − bg ở bốn ô, trung bình, độ lệch chuẩn, khoảng tin cậy 95% theo t, số seed
     dương/âm và kiểm định dấu hai phía.
  C. Tích hợp adapter học từ PQ + lookup thật (probeE2E_*_pq.json) đặt cạnh adapter học từ M0 đầy đủ (đợt 5).
"""
import glob, json, math, os, sys
import numpy as np

T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 19: 2.093, 29: 2.045}
CELLS = (("PP", "lịch probe, đo probe"), ("PL", "lịch probe, đo thật"), ("LP", "lịch thật, đo probe"),
         ("LL", "lịch thật, đo thật"), ("LL2", "lịch thật, đo thật lần 2"))


def t975(df):
    if df in T975:
        return T975[df]
    k = max(x for x in T975 if x <= df) if df > 1 else 1
    return T975[k]


def load(fn):
    try:
        return json.load(open(fn)) if os.path.exists(fn) else None
    except Exception as e:
        print(f"*** không đọc được {fn}: {e}")
        return None


def cell(run, c):
    """totals của một chính sách ở ô c (None nếu không có)."""
    if run is None:
        return None
    if c == "PP":
        return run.get("oracle", {}).get("totals")
    if c == "LL":
        return run.get("sim", {}).get("totals")
    key = dict(PL="sched_probe_eval_lookup", LP="sched_lookup_eval_probe", LL2="sched_lookup_eval_lookup_again")[c]
    return (run.get("replay", {}).get(key) or {}).get("totals")


def val(d, pol, c, k):
    if d is None or not d.get("stream"):
        return float("nan")
    runs = d["stream"]["runs"]
    if pol == "lazy-bg":
        a, b = cell(runs.get("lazy"), c), cell(runs.get("bg"), c)
        return float("nan") if a is None or b is None else a[k] - b[k]
    x = cell(runs.get(pol), c)
    return float("nan") if x is None else x[k]


def stats(v):
    v = np.asarray([x for x in v if x == x], dtype=float)
    n = len(v)
    if n == 0:
        return dict(n=0, mean=float("nan"), sd=float("nan"), lo=float("nan"), hi=float("nan"), pos=0, neg=0, p=float("nan"))
    m = float(v.mean())
    sd = float(v.std(ddof=1)) if n > 1 else float("nan")
    h = t975(n - 1) * sd / math.sqrt(n) if n > 1 else float("nan")
    pos, neg = int((v > 0).sum()), int((v < 0).sum())
    k, nn = min(pos, neg), pos + neg
    p = min(1.0, 2 * sum(math.comb(nn, i) for i in range(k + 1)) / 2 ** nn) if nn else float("nan")
    return dict(n=n, mean=m, sd=sd, lo=m - h, hi=m + h, pos=pos, neg=neg, p=p)


def f1(x, w=6, sign=True):
    if x is None or x != x:
        return " " * (w - 1) + "-"
    return f"{x:+{w}.1f}" if sign else f"{x:{w}.1f}"


def checks_line(d):
    c = d.get("checks", {})
    out = []
    for k, v in c.items():
        if isinstance(v, dict) and "n" in v:
            out.append(f"{k} {v['n']} {'KHỚP' if v['bad'] == 0 else str(v['bad']) + ' LỆCH'}")
        elif isinstance(v, dict):
            out.append(f"{k} " + ",".join(f"{p}:{x['n']} {'KHỚP' if x['bad'] == 0 else str(x['bad']) + ' LỆCH'}"
                                          for p, x in v.items()))
    return "; ".join(out)


def files_f(tag):
    """{seed: probeE2F} của code100kfq/tag."""
    out = {}
    for fn in glob.glob(f"probeE2F_code100kfq_{tag}_s*.json"):
        if fn.endswith("_pq.json"):
            continue
        d = load(fn)
        if d and d.get("stream"):
            out[int(d["argv"]["seed"])] = d
    return dict(sorted(out.items()))


def part_a(tags, seeds_a):
    print("#" * 110)
    print("A. BẢNG 2x2: LỊCH MIGRATE (probe | lookup thật) x CÁCH ĐO RECALL (probe | lookup thật), code100kfq, 50.000 node")
    print("   PP = lượt probe của đợt 5 (= 06), LL = lượt lookup thật của đợt 5, PL và LP = phát lại chéo, LL2 = mốc nhiễu.")
    print("   TB theo seed; trong ngoặc là từng seed.")
    for tag in tags:
        F = {s: d for s, d in files_f(tag).items() if s in seeds_a}
        if not F:
            print(f"\n   {tag}: chưa có probeE2F_code100kfq_{tag}_s*.json"); continue
        S = list(F)
        print("=" * 110)
        print(f"code100kfq / {tag}, seed {S}")
        for s, d in F.items():
            print(f"   tự kiểm seed {s}: {checks_line(d)}")
        for k, lab in (("final", "final@5"), ("rr", "rerank@20")):
            print(f"   {lab:10s} " + " ".join(f"{c:>8s}" for c, _ in CELLS))
            for pol in ("lazy", "bg", "lazy-bg"):
                means = [np.nanmean([val(d, pol, c, k) for d in F.values()]) for c, _ in CELLS]
                print(f"   {pol:10s} " + " ".join(f1(m, 8, sign=(pol == 'lazy-bg')) for m in means))
            for pol in ("lazy-bg",):
                for c, lab2 in CELLS:
                    v = [val(d, pol, c, k) for d in F.values()]
                    print(f"      {pol} {c:4s} ({lab2:26s}): " + ", ".join(f1(x, 5) for x in v))
            # tách phần
            print(f"   tách phần ({lab}), TB seed; ngoặc vuông là lazy − bg từng seed:")
            print(f"      {'':40s} {'lazy':>6s} {'bg':>6s} {'lazy−bg':>8s}")
            parts = (("đo thật − đo probe, cùng lịch probe", lambda g: g("PL") - g("PP")),
                     ("đo thật − đo probe, cùng lịch thật", lambda g: g("LL") - g("LP")),
                     ("lịch thật − lịch probe, cùng đo probe", lambda g: g("LP") - g("PP")),
                     ("lịch thật − lịch probe, cùng đo thật", lambda g: g("LL") - g("PL")),
                     ("tương tác", lambda g: (g("LL") - g("LP")) - (g("PL") - g("PP"))),
                     ("nhiễu lookup LL2 − LL", lambda g: g("LL2") - g("LL")))
            for nm, fn_ in parts:
                xs = {pol: fn_(lambda c, pol=pol: np.asarray([val(d, pol, c, k) for d in F.values()]))
                      for pol in ("lazy", "bg", "lazy-bg")}
                print(f"      {nm:40s} {f1(np.nanmean(xs['lazy']))} {f1(np.nanmean(xs['bg']))} "
                      f"{f1(np.nanmean(xs['lazy-bg']), 8)}  [{', '.join(f1(y, 4) for y in xs['lazy-bg'])}]"
                      + (f"  TB |LL2 − LL|: lazy {np.nanmean(np.abs(xs['lazy'])):.1f}, bg {np.nanmean(np.abs(xs['bg'])):.1f}, "
                         f"lazy−bg {np.nanmean(np.abs(xs['lazy-bg'])):.1f}" if nm.startswith("nhiễu") else ""))
        print("   GT top-5 đã ở E1 trung bình theo lượt (chỉ phụ thuộc lịch):")
        for pol in ("lazy", "bg"):
            gp = [val(d, pol, "PP", "gtE1") for d in F.values()]
            gl = [val(d, pol, "LL", "gtE1") for d in F.values()]
            fp = [100 * val(d, pol, "PP", "f_end") for d in F.values()]
            fl = [100 * val(d, pol, "LL", "f_end") for d in F.values()]
            print(f"      {pol:4s} lịch probe {np.nanmean(gp):5.1f}% (f cuối {np.nanmean(fp):4.1f}%) | lịch thật "
                  f"{np.nanmean(gl):5.1f}% (f cuối {np.nanmean(fl):4.1f}%)   từng seed: "
                  + ", ".join(f"{a:.1f}->{b:.1f}" for a, b in zip(gp, gl)))
        print("   tìm lại node của lookup thật (A | E1), TB seed:")
        for pol in ("lazy", "bg"):
            for c in ("PL", "LL", "LL2"):
                fa = np.nanmean([100 * val(d, pol, c, "found_A") for d in F.values()])
                fk = np.nanmean([100 * val(d, pol, c, "found_K") for d in F.values()])
                print(f"      {pol:4s} {c:4s}: {fa:4.0f}% | {fk:4.0f}%")


def part_b(btags):
    print("\n" + "#" * 110)
    print("B. lazy − bg THEO SEED, code100kfq, 50.000 node (seed 3 4 5 từ pha A, các seed khác từ pha B)")
    for tag in btags:
        F = files_f(tag)
        if not F:
            print(f"   {tag}: chưa có file"); continue
        print("=" * 110)
        print(f"code100kfq / {tag}, {len(F)} seed: {list(F)}")
        for s, d in F.items():
            if s not in (3, 4, 5):
                print(f"   tự kiểm seed {s}: {checks_line(d)}")
        for k, lab in (("final", "final@5"), ("rr", "rerank@20")):
            print(f"   {lab}: {'seed':>6s} " + " ".join(f"{c:>7s}" for c, _ in CELLS[:4]))
            for s, d in F.items():
                print(f"   {'':9s}{s:6d} " + " ".join(f1(val(d, 'lazy-bg', c, k), 7) for c, _ in CELLS[:4]))
            for c, lab2 in CELLS[:4]:
                st = stats([val(d, "lazy-bg", c, k) for d in F.values()])
                print(f"   {lab:9s} {c:3s} ({lab2:21s}) n={st['n']:2d} TB {f1(st['mean'], 5)}  sd {f1(st['sd'], 4, False)}  "
                      f"KTC95% [{f1(st['lo'], 5)}, {f1(st['hi'], 5)}]  dương {st['pos']} âm {st['neg']}  "
                      f"kiểm định dấu p={st['p']:.3f}")
            st = stats([val(d, "lazy-bg", "LL", k) - val(d, "lazy-bg", "PP", k) for d in F.values()])
            print(f"   {lab:9s} LL − PP của lazy − bg: TB {f1(st['mean'], 5)} KTC95% [{f1(st['lo'], 5)}, {f1(st['hi'], 5)}] "
                  f"dương {st['pos']} âm {st['neg']}")


def part_c(tags, seeds_c):
    print("\n" + "#" * 110)
    print("C. TÍCH HỢP: ADAPTER HỌC TỪ BẢN TÁI TẠO PQ + RECALL TỪ LOOKUP THẬT (probeE2E_*_pq.json), so với adapter học")
    print("   từ M0 đầy đủ (probeE2E_*.json của đợt 5). Mỗi ô: exact | pq | pq − exact, TB seed.")
    print("   DU và E1 không dùng adapter nên cột oracle phải trùng nhau; ở cột thật, chênh của DU và E1 chỉ là nhiễu")
    print("   lookup (chuỗi node gốc ngẫu nhiên lệch đi sau nhánh AD đầu tiên), dùng làm mốc khi đọc chênh của AD.")
    for tag in tags:
        E = {s: load(f"probeE2E_code100kfq_{tag}_s{s}.json") for s in seeds_c}
        Q = {s: load(f"probeE2E_code100kfq_{tag}_s{s}_pq.json") for s in seeds_c}
        ok = [s for s in seeds_c if E[s] and Q[s]]
        print("=" * 110)
        if not ok:
            print(f"code100kfq / {tag}: thiếu file (exact có {[s for s in seeds_c if E[s]]}, pq có {[s for s in seeds_c if Q[s]]})")
            continue
        print(f"code100kfq / {tag}, seed {ok}")
        for s in ok:
            print(f"   tự kiểm pq seed {s}: {checks_line(Q[s])}")
        print(f"   {'trạng thái':10s} {'final thật':>24s} {'R20 thật':>24s} {'final oracle':>24s} {'R20 oracle':>24s} "
              f"{'lookup − oracle (pq) final / R20':>34s}")
        for nm in Q[ok[0]]["fixed"]:
            def trip(side, k):
                e = np.mean([E[s]["fixed"][nm][side][k] for s in ok])
                q = np.mean([Q[s]["fixed"][nm][side][k] for s in ok])
                return f"{e:6.1f} |{q:6.1f} |{q - e:+5.1f}"
            dq = np.mean([Q[s]["fixed"][nm]["diff"]["final_mean"] for s in ok])
            dr = np.mean([Q[s]["fixed"][nm]["diff"]["rr_mean"] for s in ok])
            print(f"   {nm:10s} {trip('sim', 'final_r5'):>24s} {trip('sim', 'rr'):>24s} {trip('oracle', 'final_r5'):>24s} "
                  f"{trip('oracle', 'rr'):>24s} {dq:+15.1f} / {dr:+5.1f}")
        if all(Q[s].get("stream") and E[s].get("stream") for s in ok):
            print("   dòng vòng kín, lookup thật (sim) | probe (oracle):")
            for pol in ("static", "lazy", "bg", "lazy-bg"):
                parts = []
                for mode, c in (("thật", "LL"), ("probe", "PP")):
                    for k in ("final", "rr"):
                        e = [val(E[s], pol, c, k) for s in ok]
                        q = [val(Q[s], pol, c, k) for s in ok]
                        parts.append(f"{mode} {k:5s} {np.mean(e):6.1f} |{np.mean(q):6.1f} |{np.mean(q) - np.mean(e):+5.1f}")
                print(f"   {pol:8s} " + "   ".join(parts))
            for k in ("final", "rr"):
                q = [val(Q[s], "lazy-bg", "LL", k) for s in ok]
                print(f"   lazy − bg pq, lookup thật, {k}: từng seed " + ", ".join(f1(x, 5) for x in q))


if __name__ == "__main__":
    tags = os.environ.get("TAGS", "bgebase e5large arctic").split()
    btags = os.environ.get("BTAGS", "bgebase").split()
    cseeds = [int(x) for x in os.environ.get("CSEEDS", "3 4 5").split()]
    what = sys.argv[1] if len(sys.argv) > 1 else "abc"
    if "a" in what:
        part_a(tags, cseeds)
    if "b" in what:
        part_b(btags)
    if "c" in what:
        part_c(tags, cseeds)
