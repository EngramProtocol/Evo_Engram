#!/usr/bin/env python3
"""
rerun_prev.py  —  ĐỢT 11, pha R. Chạy lại một job cũ của 10_probe_placement.py hoặc 11_probe_safe.py bằng code hiện tại,
với đúng tham số đã ghi trong file kết quả cũ (trường argv), rồi so từng số với file cũ (--check-prev).

  python3 evo/rerun_prev.py CŨ.json SCRIPT MỚI.json [--set khoá=giá_trị ...]

--set đổi một tham số so với lượt cũ, ví dụ --set policies=static,lazy,lazyV,lazyV_adp (thêm chính sách xen vào giữa để
kiểm rằng chính sách mới không làm đổi số của chính sách cũ) hoặc --set variants=srp,itq_q. Tham số out, check_prev,
check_10 không lấy từ lượt cũ: out là MỚI.json, check_prev là CŨ.json, check_10 là none (chỉ với 11). Tham số mới của
đợt 11 không có trong argv cũ nên giữ mặc định, mà mặc định không đổi số cũ.

Sau khi chạy, kiểm thêm rằng lượt mới có đủ mọi run (11) hoặc mọi biến thể được yêu cầu (10) của lượt cũ, vì --check-prev
chỉ so các tên có ở cả hai file. Thiếu tên nào thì in THIẾU và thoát mã 3.
"""
import json, subprocess, sys


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    old, script, new = sys.argv[1:4]
    sets = {}
    rest = sys.argv[4:]
    while rest:
        if rest[0] != "--set" or len(rest) < 2 or "=" not in rest[1]:
            sys.exit(f"không hiểu tham số {rest[:2]}")
        k, v = rest[1].split("=", 1)
        sets[k.replace("-", "_")] = v
        rest = rest[2:]
    argv = dict(json.load(open(old))["argv"])
    for k in sets:
        if k not in argv:
            sys.exit(f"--set {k}: lượt cũ không có tham số này")
    argv.update(sets)
    cmd = ["python3", script]
    for k, v in argv.items():
        if k in ("out", "check_prev", "check_10") or v is None:
            continue
        cmd += ["--" + k.replace("_", "-"), str(v)]
    cmd += ["--check-prev", old, "--out", new]
    if "11_probe_safe" in script:
        cmd += ["--check-10", "none"]
    print("rerun_prev:", " ".join(cmd), flush=True)
    rc = subprocess.call(cmd)
    if rc != 0:
        sys.exit(rc)
    o, n = json.load(open(old)), json.load(open(new))
    if "runs" in o:
        want = list(o["runs"])
        miss = [k for k in want if k not in n.get("runs", {})]
        what = "run"
    else:
        req = set(str(argv.get("variants", "")).split(","))
        want = [v for v in o.get("variants", {}) if v in req]
        miss = [v for v in want if v not in n.get("variants", {})]
        what = "biến thể"
    if miss:
        print(f">>> rerun_prev: THIẾU {len(miss)}/{len(want)} {what} của lượt cũ trong lượt mới: {miss[:10]}", flush=True)
        sys.exit(3)
    print(f">>> rerun_prev: lượt mới có đủ {len(want)}/{len(want)} {what} của lượt cũ", flush=True)


if __name__ == "__main__":
    main()
