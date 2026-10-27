#!/bin/bash
# Đợt 7b: thăm dò tiếp sau đợt 7 (chưa đăng ký trước, không thuộc đánh giá xác nhận).
#   A  Migrate an toàn cùng ngân sách với lazy (11_probe_safe.py, khoá E1 'u' như bài) trên code100kfq x 3 cặp x seed 3 4 5:
#      static, lazy, bg, lazyV1, bgV1, lazyVbg (lazyV1 + nền retire ngay), lazyVbgD (lazyV1 + nền dạng dual).
#      Tổng số record công bố của lazyVbg và lazyVbgD bằng của lazy. Tự kiểm static, lazy, bg với probeL_*_ku đợt 4.
#   B  Migrate trên placement học (--e1-place itq_q): epoch E1 đặt record bằng ITQ học trên S như 10. Cùng chính sách,
#      thêm lazyD. Tự kiểm index native ở f = 1 với biến thể itq_q của probeP_* đợt 7 (L = 5, T = 8).
#   C  Mô hình dị hướng bằng công thức góc chính xác (10 --aniso-only 1): code100kfq, code 20k, SciFact x {bge-base,
#      e5-large, Arctic, M0}, seed 3. Dự đoán và đo xác suất trùng bucket 16 bit, có và không trừ tâm.
#   D  Chẩn đoán: chạy lại 06 hiện tại cho e5-large seed 3 (PROB, static/lazy/bg) và so với probeL_*_ku đợt 4, để biết
#      chênh lệch nhỏ của 'moved' ở đợt 7 đến từ môi trường (numpy) hay từ 11.
# Yêu cầu: kết quả đợt 4 (probeL_code100kfq_*_ku.json) và đợt 7 (probeP_code100kfq_*.json) ở thư mục gốc repo;
#          HEAD đúng tag evo-r7b-pilot.
# Chạy:    tmux new -s round7b -d "bash ~/Evo_Engram/evo/run_round7b.sh"
# File ra mới: probeVB_* (A, B), probeA_* (C), probeL_code100kfq_e5large_s3_ku_r7b.json (D). Không ghi đè file cũ.
# Chỉ chạy một phần: PHASES="A B" (mặc định "A B C D").
cd ${EVO_ROOT:-~/Evo_Engram} || exit 1
[ -f venv/bin/activate ] && source venv/bin/activate
export OPENBLAS_NUM_THREADS=${NT:-1} OMP_NUM_THREADS=${NT:-1} MKL_NUM_THREADS=${NT:-1}
P=${P:-4}
PHASES=${PHASES:-"A B C D"}
SEEDS=${SEEDS:-"3 4 5"}
TAGS=${TAGS:-"bgebase e5large arctic"}
N100=${N100:-50000}
NSMALL=${NSMALL:-10000}
X=${X:-}; XB=${XB:-}; XC=${XC:-}; XD=${XD:-}   # tham số thêm, CHỈ dùng khi chạy thử trên dữ liệu giả
L=evo/r7b_logs
mkdir -p $L
JL=$L/jobs.log
F="grep --line-buffered -v WARNING.clustering"
{ echo "=== ĐỢT 7b bắt đầu $(date '+%F %T')  P=$P  pha: $PHASES"; free -g | head -2;
  python3 -c "import numpy; print('numpy', numpy.__version__)"; } | tee -a $JL

# ---------- 0. kiểm tra
git describe --tags --exact-match 2>/dev/null | grep -qx "evo-r7b-pilot" \
  && echo "HEAD = tag evo-r7b-pilot ($(git rev-parse --short HEAD))" | tee -a $JL \
  || echo "CẢNH BÁO: HEAD chưa ở tag evo-r7b-pilot" | tee -a $JL
sha256sum -c evo/SHA256SUMS_round7b --quiet 2>&1 | tee -a $JL
[ "${PIPESTATUS[0]}" = "0" ] || { echo "FILE CỦA ĐỢT 7b BỊ SỬA SO VỚI SHA256SUMS_round7b, DỪNG" | tee -a $JL; exit 1; }
miss=0
for t in $TAGS; do for s in $SEEDS; do
  for f in probeL_code100kfq_${t}_s${s}_ku.json probeP_code100kfq_${t}_s${s}.json; do
    [ -e $f ] || { echo "THIẾU $f (kết quả đợt 4 hoặc đợt 7, cần để tự kiểm)" | tee -a $JL; miss=1; }; done; done; done
[ "$miss" = "0" ] || { echo "THIẾU FILE, DỪNG" | tee -a $JL; exit 1; }
have() {   # $1 dataset, $2 tag hoặc m0
  if [ "$2" = "m0" ]; then
    for f in data/$1_corpus_embeddings.npy data/$1_query_embeddings.npy data/$1_ground_truth.json; do [ -e $f ] || return 1; done
  else
    for f in data/$1_$2_corpus_embeddings.npy data/$1_$2_query_embeddings.npy data/$1_$2_ground_truth.json; do
      [ -e $f ] || return 1; done
  fi
}

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

J=$L/jobs.txt; : > $J
V="python3 evo/11_probe_safe.py --dataset code100kfq --nodes $N100 --frac 0.02 --confirms 1"
PP="python3 evo/10_probe_placement.py --aniso-only 1"
s1=$(echo $SEEDS | cut -d' ' -f1)
if [[ " $PHASES " == *" B "* ]]; then
  for t in $TAGS; do for s in $SEEDS; do
    echo "vb_itq_${t}_s${s}|$V --tag $t --seed $s --e1-place itq_q --policies static,lazy,bg,lazyD,lazyV,bgV,lazyVbg,lazyVbgD --out probeVB_code100kfq_${t}_s${s}_itq_q.json $X $XB 2>&1 | $F" >> $J
  done; done
fi
if [[ " $PHASES " == *" A "* ]]; then
  for t in $TAGS; do for s in $SEEDS; do
    echo "vb_u_${t}_s${s}|$V --tag $t --seed $s --policies static,lazy,bg,lazyV,bgV,lazyVbg,lazyVbgD --out probeVB_code100kfq_${t}_s${s}_u.json $X $XB 2>&1 | $F" >> $J
  done; done
fi
if [[ " $PHASES " == *" D "* ]]; then
  echo "d_06_e5large_s${s1}|python3 evo/06_probe_lazy.py --dataset code100kfq --tag e5large --seed $s1 --nodes $N100 --frac 0.02 --fusions PROB --policies static,lazy,bg --check-3b probeL_code100kfq_e5large_s${s1}_ku.json --out probeL_code100kfq_e5large_s${s1}_ku_r7b.json $X $XD 2>&1 | $F" >> $J
fi
if [[ " $PHASES " == *" C "* ]]; then
  for ds in code100kfq code scifact; do for t in $TAGS m0; do
    if ! have $ds $t; then echo "bỏ qua C: thiếu dữ liệu $ds $t" | tee -a $JL; continue; fi
    sp=$([ "$t" = "m0" ] && echo "--space m0" || echo "")
    if [ "$ds" = "code100kfq" ]; then nn=$N100; fr=0.02; else nn=$NSMALL; fr=0.1; fi
    echo "a_${ds}_${t}_s${s1}|$PP --dataset $ds --tag $t $sp --seed $s1 --nodes $nn --frac $fr $X $XC 2>&1 | $F" >> $J
  done; done
fi
echo "đợt 7b: $(wc -l < $J) job, P=$P" | tee -a $JL
run_jobs $J

# ---------- tổng hợp
python3 evo/analyze_r7b.py > evo/r7b_summary.txt 2>&1
{
  cat evo/r7b_summary.txt
  echo "################ TỰ KIỂM (dòng >>> và lệch trong log)"
  grep -H ">>>\|    lệch:" $L/*.log | sed "s#$L/##"
  echo "################ LỖI"
  grep -H "Traceback\|Error\|LỆCH\|DỪNG\|\*\*\*" $L/*.log | sed "s#$L/##" | head -60
  echo "################ THỜI GIAN"
  cat $JL
} > evo/round7b_all.txt
echo "XONG ĐỢT 7b $(date '+%F %T')" | tee -a $JL evo/round7b_all.txt
