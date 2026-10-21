#!/bin/bash
# Đợt 6: kiểm soát lookup và lịch migrate, thêm seed bge-base, kiểm tra tích hợp PQ adapter + lookup thật
# (góp ý của thầy sau đợt 5; thăm dò, không thuộc đánh giá xác nhận; thuật toán giữ nguyên).
#   A  Bảng 2x2 trên code100kfq x 3 cặp x seed 3 4 5 (50.000 node): lịch migrate lấy từ probe hoặc từ lookup thật,
#      recall đo bằng probe hoặc bằng lookup thật, cho cả lazy và bg (09 --factorial 1). Thêm một lượt lịch thật +
#      đo thật lần hai làm mốc nhiễu (--noise-replay 1). Hai ô chéo chính là lượt đợt 5, tự kiểm (5) so từng số.
#   B  Thêm seed cho bge-base 100k (mặc định 6 đến 12, tổng 10 seed cùng A): chỉ dòng lazy và bg, có 2x2.
#   C  Tích hợp: adapter học trên bản tái tạo PQ (--pair-src pq) cộng recall đo từ lookup thật, code100kfq x 3 cặp
#      x seed 3 4 5: trạng thái cố định và dòng vòng kín. Tự kiểm (1) với probeG_*_pq, (3) với probeL_*_ku_pq.
# Yêu cầu: kết quả đợt 4 và đợt 5 ở thư mục gốc repo (probeG_, probeL_, probeE2E_ và các file _pq);
#          HEAD đúng tag evo-r6-v1.
# Chạy:    tmux new -s round6 -d "bash ~/Evo_Engram/evo/run_round6.sh"
# Không ghi đè kết quả đợt trước: file mới tên probeE2F_ (A, B) hoặc probeE2E_*_pq (C).
# Chỉ chạy một phần: PHASES="A" (mặc định "A B C"). Seed thêm: BSEEDS="6 7 8 9 10 11 12", cặp thêm: BTAGS="bgebase".
cd ${EVO_ROOT:-~/Evo_Engram} || exit 1
[ -f venv/bin/activate ] && source venv/bin/activate
# 09 chủ yếu là SimPy một luồng: 4 job x 1 luồng như pha B đợt 5
export OPENBLAS_NUM_THREADS=${NT:-1} OMP_NUM_THREADS=${NT:-1} MKL_NUM_THREADS=${NT:-1}
P=${P:-4}
PHASES=${PHASES:-"A B C"}
CSEEDS=${CSEEDS:-"3 4 5"}
BSEEDS=${BSEEDS:-"6 7 8 9 10 11 12"}
BTAGS=${BTAGS:-"bgebase"}
TAGS=${TAGS:-"bgebase e5large arctic"}
N100=${N100:-50000}
X=${X:-}; XB=${XB:-}             # tham số thêm, CHỈ dùng khi chạy thử trên dữ liệu giả
L=evo/r6_logs
mkdir -p $L
JL=$L/jobs.log
F="grep --line-buffered -v WARNING.clustering"
{ echo "=== ĐỢT 6 bắt đầu $(date '+%F %T')  P=$P  pha: $PHASES"; nproc; free -g | head -2; } | tee -a $JL

# ---------- 0. kiểm tra
git describe --tags --exact-match 2>/dev/null | grep -qx "evo-r6-v1" \
  && echo "HEAD = tag evo-r6-v1 ($(git rev-parse --short HEAD))" | tee -a $JL \
  || echo "CẢNH BÁO: HEAD chưa ở tag evo-r6-v1" | tee -a $JL
sha256sum -c evo/SHA256SUMS_round6 --quiet 2>&1 | tee -a $JL
[ "${PIPESTATUS[0]}" = "0" ] || { echo "FILE CỦA ĐỢT 6 BỊ SỬA SO VỚI SHA256SUMS_round6, DỪNG" | tee -a $JL; exit 1; }
miss=0
for t in $TAGS; do for s in $CSEEDS; do
  for f in probeG_code100kfq_${t}_s${s}.json probeL_code100kfq_${t}_s${s}_ku.json probeE2E_code100kfq_${t}_s${s}.json \
           probeG_code100kfq_${t}_s${s}_pq.json probeL_code100kfq_${t}_s${s}_ku_pq.json; do
    [ -e $f ] || { echo "THIẾU $f (kết quả đợt 4 hoặc 5, cần để tự kiểm)" | tee -a $JL; miss=1; }; done; done; done
[ -d src ] || { echo "THIẾU src/ của V-Engram" | tee -a $JL; miss=1; }
[ "$miss" = "0" ] || { echo "THIẾU FILE, DỪNG" | tee -a $JL; exit 1; }

run_jobs() {   # $1: file lệnh, mỗi dòng "tên|lệnh"
  while IFS='|' read -r name cmd; do
    [ -z "$name" ] && continue
    while [ "$(jobs -rp | wc -l)" -ge "$P" ]; do wait -n; done
    ( t0=$(date +%s); echo "BẮT ĐẦU $(date +%T) $name" >> $JL
      bash -o pipefail -c "$cmd" > $L/$name.log 2>&1; rc=$?
      echo "XONG    $(date +%T) $name  ($(( $(date +%s) - t0 ))s, mã thoát $rc)" >> $JL ) &
  done < "$1"
  wait
}

# Một hàng đợi chung, job dài trước (A khoảng 70 phút, C khoảng 47 phút, B khoảng 40 phút mỗi job trên node-dal-02)
J=$L/jobs.txt; : > $J
E="python3 evo/09_sim_e2e.py --dataset code100kfq --nodes $N100 --frac 0.02"
if [[ " $PHASES " == *" A "* ]]; then
  for t in $TAGS; do for s in $CSEEDS; do
    echo "f_code100kfq_${t}_s${s}|$E --tag $t --seed $s --factorial 1 --noise-replay 1 $X $XB 2>&1 | $F" >> $J
  done; done
fi
if [[ " $PHASES " == *" C "* ]]; then
  for t in $TAGS; do for s in $CSEEDS; do
    echo "q_code100kfq_${t}_s${s}|$E --tag $t --seed $s --pair-src pq $X $XB 2>&1 | $F" >> $J
  done; done
fi
if [[ " $PHASES " == *" B "* ]]; then
  for t in $BTAGS; do for s in $BSEEDS; do
    echo "b_code100kfq_${t}_s${s}|$E --tag $t --seed $s --factorial 1 --fixed 0 --policies lazy,bg $X $XB 2>&1 | $F" >> $J
  done; done
fi
echo "đợt 6: $(wc -l < $J) job, P=$P" | tee -a $JL
run_jobs $J

# ---------- tổng hợp
python3 evo/analyze_r6.py > evo/r6_summary.txt 2>&1
{
  cat evo/r6_summary.txt
  echo "################ TỰ KIỂM (dòng >>> trong log)"
  grep -H ">>>" $L/*.log | sed "s#$L/##"
  echo "################ LỖI"
  grep -H "Traceback\|Error\|LỆCH\|DỪNG\|\*\*\*" $L/*.log | sed "s#$L/##" | head -60
  echo "################ THỜI GIAN"
  cat $JL
} > evo/round6_all.txt
echo "XONG ĐỢT 6 $(date '+%F %T')" | tee -a $JL evo/round6_all.txt
