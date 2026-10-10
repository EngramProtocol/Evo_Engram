#!/usr/bin/env python3
"""Chấm các giả thuyết đăng ký trước của đợt 4 (evo/PREREG_round4.md). Commit cùng tag evo-confirm-v1,
không sửa sau khi có kết quả. Đọc probeH (03c), probeG (04b), probeL (06) ở thư mục hiện tại."""
import json, os, sys
import numpy as np

SEEDS = [3, 4, 5]
CONF = [   # (dataset, các tag, cỡ mẫu holdout, cỡ mẫu chính của H1)
    ("code100kfq", ["bgebase", "e5large", "arctic"], [0.01, 0.02, 0.05], 0.05),
    ("code", ["arctic"], [0.05, 0.10, 0.25], 0.25),
    ("scifact", ["arctic"], [0.10, 0.386], 0.386),
]
TOL_MONO = 1.0
MARGIN_H1 = -5.0


def pre(ds):
    return "" if ds == "code" else f"{ds}_"


def load(fn):
    return json.load(open(fn)) if os.path.exists(fn) else None


def verdict(ok):
    return "ĐẠT" if ok is True else ("KHÔNG ĐẠT" if ok is False else "THIẾU DỮ LIỆU")


def h1(ds, tag, fracs, prim):
    out = {}
    for fr in fracs:
        rows = []
        for s in SEEDS:
            d = load(f"probeH_{pre(ds)}{tag}_s{s}_f{fr:g}_ho1.json")
            if d is None:
                rows = None; break
            R = {r["name"]: r for r in d["results"]}
            rows.append({k: R["A_split_norm"]["rerank"][k] - R["dual_encode"]["rerank"][k]
                         for k in R["dual_encode"]["rerank"]})
        if rows is None:
            out[fr] = None; continue
        ks = sorted(rows[0], key=int)
        mean = {k: float(np.mean([r[k] for r in rows])) for k in ks}
        n = load(f"probeH_{pre(ds)}{tag}_s{SEEDS[0]}_f{fr:g}_ho1.json").get("n_sample_doc")
        out[fr] = dict(by_R=mean, worst=min(mean.values()), n=n)
    p = out.get(prim)
    ok = None if p is None else bool(p["worst"] >= MARGIN_H1)
    passing = [fr for fr in fracs if out.get(fr) is not None and out[fr]["worst"] >= MARGIN_H1]
    return ok, out, (min(passing) if passing else None)


def h23(ds, tag):
    G = [load(f"probeG_{pre(ds)}{tag}_s{s}.json") for s in SEEDS]
    if any(g is None for g in G):
        return None, None, {}
    res = [g["results"] for g in G]
    info = {}
    d10 = [r["0.1"]["AD_PROB"]["final_r5"] - r["0.1"]["AD_RRF"]["final_r5"] for r in res] if all("0.1" in r for r in res) else None
    fs = sorted((k for k in res[0] if not k.startswith("_")), key=float)
    ser = [float(np.mean([r[k]["AD_PROB"]["rerank"]["20"] for r in res])) for k in fs]
    steps = np.diff(ser)
    info["prob_minus_rrf_f10"] = None if d10 is None else float(np.mean(d10))
    info["rerank20_series"] = dict(zip(fs, [round(x, 2) for x in ser]))
    info["worst_step"] = float(steps.min()) if len(steps) else float("nan")
    ok2 = None if d10 is None else bool(np.mean(d10) > 0 and info["worst_step"] >= -TOL_MONO)
    d50 = [r["0.5"]["ADR_PROB"]["final_r5"] - r["0.5"]["AD_PROB"]["final_r5"] for r in res] if all("0.5" in r for r in res) else None
    info["refit_minus_ad_f50"] = None if d50 is None else float(np.mean(d50))
    ok3 = None if d50 is None else bool(np.mean(d50) >= 0)
    return ok2, ok3, info


def h4(ds, tag):
    L = [load(f"probeL_{pre(ds)}{tag}_s{s}_ku.json") for s in SEEDS]
    if any(x is None for x in L):
        return None, {}
    try:
        lz = [x["runs"]["z1|PROB|lazy"]["totals"] for x in L]
        bg = [x["runs"]["z1|PROB|bg"]["totals"] for x in L]
        st = [x["runs"]["z1|PROB|static"]["totals"] for x in L]
    except KeyError:
        return None, {}
    dq = float(np.mean([a["final"] - b["final"] for a, b in zip(lz, bg)]))
    fl, fs = float(np.mean([a["fetch"] for a in lz])), float(np.mean([a["fetch"] for a in st]))
    return bool(dq > 0 and fl < fs), dict(lazy_minus_bg_final=dq, fetch_lazy=fl, fetch_static=fs,
                                          lazy_final=float(np.mean([a["final"] for a in lz])),
                                          bg_final=float(np.mean([a["final"] for a in bg])))


def main():
    print("ĐÁNH GIÁ XÁC NHẬN, ĐỢT 4 (tiêu chí trong evo/PREREG_round4.md; seed", SEEDS, ")")
    allres = {}
    for ds, tags, fracs, prim in CONF:
        for tag in tags:
            print("=" * 100)
            print(f"{ds} / {tag}")
            ok1, o1, minpass = h1(ds, tag, fracs, prim)
            for fr in fracs:
                r = o1.get(fr)
                if r is None:
                    print(f"  H1 mẫu {fr:g}: THIẾU"); continue
                print(f"  H1 mẫu {fr:g} (n={r['n']}): A_split_norm − dual theo R: "
                      + "  ".join(f"R{k}:{v:+5.1f}" for k, v in r["by_R"].items()) + f"   tệ nhất {r['worst']:+5.1f}")
            print(f"  -> H1 (mẫu chính {prim:g}, ngưỡng {MARGIN_H1:+.0f}): {verdict(ok1)};  "
                  f"cỡ mẫu nhỏ nhất đạt: {minpass if minpass is not None else 'không có'}")
            ok2, ok3, i23 = h23(ds, tag)
            if i23:
                print(f"  H2: AD_PROB − AD_RRF ở f = 10%: {i23['prob_minus_rrf_f10']:+5.1f};  rerank@20 AD_PROB theo f: "
                      f"{i23['rerank20_series']}; bước giảm lớn nhất {i23['worst_step']:+5.2f}")
                print(f"  H3: ADR_PROB − AD_PROB ở f = 50%: {i23['refit_minus_ad_f50']:+5.1f}"
                      if i23.get("refit_minus_ad_f50") is not None else "  H3: THIẾU")
            print(f"  -> H2: {verdict(ok2)};  H3: {verdict(ok3)}")
            ok4, i4 = h4(ds, tag)
            if i4:
                print(f"  H4: lazy final {i4['lazy_final']:5.1f} vs bg {i4['bg_final']:5.1f} (chênh {i4['lazy_minus_bg_final']:+5.1f}); "
                      f"payload/truy vấn lazy {i4['fetch_lazy']:4.1f} vs static {i4['fetch_static']:4.1f}")
            print(f"  -> H4: {verdict(ok4)}")
            allres[f"{ds}/{tag}"] = dict(H1=ok1, H2=ok2, H3=ok3, H4=ok4, h1=o1, h1_min_pass=minpass, h23=i23, h4=i4)
    print("=" * 100)
    print(f"{'cặp':24s} {'H1':>14s} {'H2':>14s} {'H3':>14s} {'H4':>14s}")
    for k, v in allres.items():
        print(f"{k:24s} " + " ".join(f"{verdict(v[h]):>14s}" for h in ("H1", "H2", "H3", "H4")))
    json.dump(allres, open("prereg_round4_result.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
