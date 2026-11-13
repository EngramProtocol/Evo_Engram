#!/bin/bash
# Đợt 13: ba phép đo theo nhận xét của thầy về bản thảo C1 đến C3 (evo/README_round13.md, tag evo-r13-prereg).
#   R  Kiểm hồi quy bằng rerun_prev.py trên một file migrate tới khi xong của đợt 12 (code 20k bge-base, seed 36, có
#      lazyVbgDinf với --bg-finish): sửa đổi của 11_probe_safe.py không được đổi số nào của các run đó.
#   D  Drain (lazyVbgDinf) trên dòng 3.000 lượt của code 100k, đúng cấu hình ablation của đợt 11 (bge-base, itq_q+cap16,
#      Zipf 1, seed 26..35), chạy cùng các chính sách của Bảng 10. Mỗi job tự so các run trùng tên với file đợt 11 cùng
#      seed (--check-prev), nên số của static, lazy, lazy+delay, k1, ... phải trùng từng số với đợt 11.
#   Q  C1 với bộ ước lượng triển khai được (chỉ mẫu S và 200 query validation): 13_qf_deployable.py trên mọi file
#      probeA11_*, probeA12_* ở thư mục gốc repo (51 + 66 file). Chỉ đọc embedding, mỗi job vài giây tới một phút.
#   L  Lookup lặp: xác suất tìm thấy peer theo hạng XOR (13_lookup_rank.py), 50.000 và 10.000 peer, seed 1..5, 5.000
#      lookup mỗi job. Không cần embedding.
#   S  analyze_r13.py, rồi ghép evo/round13_all.txt.
# Yêu cầu: kết quả đợt 11 và 12 ở thư mục gốc repo: probeV11_code100kfq_bgebase_s{26..35}_cap16.json,
#          probeV12F_code_bgebase_s36_cap16.json, probeA11_*, probeA12_*, probeP11_*, probeP12_*; HEAD đúng tag
#          evo-r13-prereg.
# Chạy:    tmux new -s round13 -d "bash ~/Evo_Engram/evo/run_round13.sh"
# Chỉ chạy một phần: PHASES="Q L" (mặc định "R D Q L"); PHASES=S chỉ chạy lại analyze và ghép evo/round13_all.txt.
# File ra mới, không ghi đè file của đợt trước: probeVR13F_* (R), probeV13_* (D), probeQ13_* (Q), probeL13_* (L). Mọi dòng
# lệnh job của mọi lần chạy được ghi nối vào evo/r13_logs/all_jobs.txt (dùng khi cần chạy lại một job).
cd ${EVO_ROOT:-~/Evo_Engram} || exit 1
[ -f venv/bin/activate ] && source venv/bin/activate
NCPU=$(env -u OMP_NUM_THREADS -u OMP_THREAD_LIMIT nproc)          # đếm lõi trước khi đặt OMP_NUM_THREADS
export OPENBLAS_NUM_THREADS=${NT:-1} OMP_NUM_THREADS=${NT:-1} MKL_NUM_THREADS=${NT:-1}
inlist() { [[ " $2 " == *" $1 "* ]]; }
P=${P:-4}
PHASES=${PHASES:-"R D Q L"}
SEEDS_D=${SEEDS_D:-"26 27 28 29 30 31 32 33 34 35"}
SEEDS_L50=${SEEDS_L50:-"1 2 3 4 5"}
SEEDS_L10=${SEEDS_L10:-"1 2 3 4 5"}
NLOOK=${NLOOK:-5000}
export SEEDS_D                                       # analyze_r13.py đọc cùng danh sách này
R_F=${R_F:-probeV12F_code_bgebase_s36_cap16.json}
X=${X:-}                                             # tham số thêm, CHỈ dùng khi chạy thử trên dữ liệu giả
# Bảng 10 (đợt 11): static, lazy, lazy+delay (lazyV1), dual bg retired (lazyVbg), dual no code (lazyVbgD_adp), k1
# (lazyVbgD), full; thêm lazy+keep (lazyD) và drain (lazyVbgDinf). lazyV_adp cần cho ngân sách của lazyVbgD_adp; drain
# ghép ngân sách với lazy và lazyD nên phải đứng sau hai chính sách đó.
POLD="static,lazy,lazyV,lazyV_adp,lazyVbg,lazyVbgD,lazyVbgD_adp,lazyD,full,lazyVbgDinf"
L=evo/r13_logs
mkdir -p $L
JL=$L/jobs.log
F="grep --line-buffered -v WARNING.clustering"
{ echo "=== ĐỢT 13 bắt đầu $(date '+%F %T')  NCPU=$NCPU  P=$P  pha: $PHASES"; free -g | head -2;
  python3 -c "import numpy; print('numpy', numpy.__version__)"; } | tee -a $JL

# ---------- 0. kiểm tra
git describe --tags --exact-match 2>/dev/null | grep -qx "evo-r13-prereg" \
  && echo "HEAD = tag evo-r13-prereg ($(git rev-parse --short HEAD))" | tee -a $JL \
  || echo "CẢNH BÁO: HEAD chưa ở tag evo-r13-prereg" | tee -a $JL
sha256sum -c evo/SHA256SUMS_round13 --quiet 2>&1 | tee -a $JL
[ "${PIPESTATUS[0]}" = "0" ] || { echo "FILE CỦA ĐỢT 13 BỊ SỬA SO VỚI SHA256SUMS_round13, DỪNG" | tee -a $JL; exit 1; }

run_jobs() {   # $1: file lệnh, mỗi dòng "tên|lệnh"; $2: số job song song (mặc định P)
  local par=${2:-$P} name cmd p pids=() live
  while IFS='|' read -r name cmd; do
    [ -z "$name" ] && continue
    while :; do
      live=()
      for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null && live+=("$p"); done
      pids=("${live[@]}")
      [ "${#pids[@]}" -lt "$par" ] && break
      sleep 2
    done
    ( t0=$(date +%s); echo "BẮT ĐẦU $(date +%T) $name" >> $JL
      bash -o pipefail -c "$cmd" > $L/$name.log 2>&1; rc=$?
      echo "XONG    $(date +%T) $name  ($(( $(date +%s) - t0 ))s, mã thoát $rc)" >> $JL ) &
    pids+=($!)
  done < "$1"
  for p in "${pids[@]}"; do wait "$p" 2>/dev/null; done
}

V11="python3 evo/11_probe_safe.py --confirms 1 --e1-place itq_q --e1-cap 16"
J=$L/jobs1.txt; : > $J          # job dài trước (D, R), rồi L, rồi Q
if inlist D "$PHASES"; then
  for s in $SEEDS_D; do
    prev=probeV11_code100kfq_bgebase_s${s}_cap16.json
    if [ ! -e $prev ]; then echo "THIẾU $prev (đợt 11): job seed $s chạy không tự so" | tee -a $JL; prev=none; fi
    c10=probeP11_code100kfq_bgebase_s$s.json; [ -e $c10 ] || c10=none     # như đợt 11: tự kiểm placement khi có file
    echo "d13_s$s|$V11 --dataset code100kfq --nodes 50000 --frac 0.02 --tag bgebase --seed $s --policies $POLD --zipf 1.0 --check-10 $c10 --check-prev $prev --out probeV13_code100kfq_bgebase_s${s}_cap16.json $X 2>&1 | $F" >> $J
  done
fi
if inlist R "$PHASES"; then
  if [ -e $R_F ]; then
    echo "r13_repf|python3 evo/rerun_prev.py $R_F evo/11_probe_safe.py probeVR13F_code_bgebase_s36.json 2>&1 | $F" >> $J
  else
    echo "bỏ qua R: thiếu $R_F (đợt 12)" | tee -a $JL
  fi
fi
if inlist L "$PHASES"; then
  for s in $SEEDS_L50; do
    echo "l13_n50000_s$s|python3 evo/13_lookup_rank.py --nodes 50000 --lookups $NLOOK --seed $s --out probeL13_n50000_s$s.json" >> $J
  done
  for s in $SEEDS_L10; do
    echo "l13_n10000_s$s|python3 evo/13_lookup_rank.py --nodes 10000 --lookups $NLOOK --seed $s --out probeL13_n10000_s$s.json" >> $J
  done
fi
if inlist Q "$PHASES"; then
  nq=0
  for f in probeA11_*.json probeA12_*.json; do
    [ -e "$f" ] || continue
    b=${f%.json}; r=${b%%_*}; r=${r#probe}             # probeA11_code_bgebase_s26 -> A11, code_bgebase_s26
    echo "q13_${r}_${b#*_}|python3 evo/13_qf_deployable.py $f --out probeQ13_${r}_${b#*_}.json" >> $J
    nq=$((nq + 1))
  done
  echo "Q: $nq file probeA (đợt 11: 51 file, đợt 12: 66 file)" | tee -a $JL
fi
echo "đợt 13: $(wc -l < $J) job, P=$P" | tee -a $JL
cat $J >> $L/all_jobs.txt
run_jobs $J
echo "--- xong $(date '+%F %T')" | tee -a $JL

# ---------- tổng hợp
python3 evo/analyze_r13.py > $L/r13_summary.txt 2>&1
{
  cat $L/r13_summary.txt
  echo "################ TỰ KIỂM (dòng >>> và lệch trong log)"
  grep -H ">>>\|    lệch:\|CẢNH BÁO" $L/*.log | sed "s#$L/##" | grep -v "bỏ qua"
  echo "pha Q: dựng lại bộ ước lượng cũ đúng từng số ở $(grep -l 'số trùng (đúng từng số)' $L/q13_*.log 2>/dev/null | wc -l)" \
       "trên $(ls $L/q13_*.log 2>/dev/null | wc -l) job"
  echo "################ LỖI"
  grep -H "Traceback\|Error\|LỆCH\|DỪNG\|THIẾU\|\*\*\*" $L/*.log | sed "s#$L/##" | head -60
  echo "################ THỜI GIAN"
  cat $JL
} > evo/round13_all.txt
echo "XONG ĐỢT 13 $(date '+%F %T')" | tee -a $JL evo/round13_all.txt
