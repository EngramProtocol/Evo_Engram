#!/bin/bash
# Đợt 9: churn và lỗi peer trong lúc migrate, C3 trên hai corpus mới, mapkeep, điểm nóng ITQ (evo/PREREG_round9.md,
# tag evo-r9-prereg). Placement E1 của mọi job migrate là itq_q như đợt 8.
#   R  Kiểm hồi quy: chạy lại một job đợt 8 bằng code mới (so từng số với probeV8), và một job bật đường code churn nhưng
#      không có node nào rời mạng (phải ra đúng số đợt 8).
#   A  code100kfq, 3 model x seed 6..15, mỗi job một lần dựng index rồi chạy:
#        - không churn: static (so từng số với đợt 8) và mapkeep, Zipf 1 và đều;
#        - với seed 6..10 thêm hai cấu hình churn, Zipf 1, chính sách static, lazy, lazyV1, lazyVbgD, full, mapall,
#          mapkeep: "ch" = phiên Weibull trung vị 120 phút, dòng 720 phút, sửa mỗi 60 phút; "fail" = 30% node hỏng
#          cùng lúc ngay trước lượt 1.500, không sửa. (thăm dò)
#   B  C3 trên code 20k và SciFact (overlay 10.000 node, S = 10%), 3 model x seed 6..15, đủ chính sách đợt 8 thêm
#      mapkeep, Zipf 1 và đều. Dòng dài 3.000 x N / 100.000 lượt (600 và 155). (H6, H7, H8)
#   D  Placement study code100kfq x 4 không gian x seed 6..8 với itq_q, itq128_q, itq256_q; itq_q so từng số với đợt 8.
#   E  Chẩn đoán điểm nóng ITQ (12_diag_itq.py), code100kfq x 4 không gian x seed 6..8.
# Yêu cầu: kết quả đợt 8 (probeV8_*, probeP_*_s6..8) ở thư mục gốc repo; HEAD đúng tag evo-r9-prereg.
# Chạy:    tmux new -s round9 -d "bash ~/Evo_Engram/evo/run_round9.sh"
# File ra mới: probeVR9_* (R), probeV9X_* (A), probeV9_code_*, probeV9_scifact_* (B), probeP9_* (D), diagITQ_* (E).
#              Không ghi đè file cũ. Chỉ chạy một phần: PHASES="R A" (mặc định "R A B D E").
cd ${EVO_ROOT:-~/Evo_Engram} || exit 1
[ -f venv/bin/activate ] && source venv/bin/activate
export OPENBLAS_NUM_THREADS=${NT:-1} OMP_NUM_THREADS=${NT:-1} MKL_NUM_THREADS=${NT:-1}
P=${P:-4}
PHASES=${PHASES:-"R A B D E"}
SEEDS_A=${SEEDS_A:-"6 7 8 9 10"}                     # seed có thêm hai cấu hình churn
SEEDS_B=${SEEDS_B:-"6 7 8 9 10 11 12 13 14 15"}
SEEDS_C=${SEEDS_C:-"6 7 8 9 10 11 12 13 14 15"}      # seed của pha A (không churn: static, mapkeep)
SEEDS_D=${SEEDS_D:-"6 7 8"}
TAGS=${TAGS:-"bgebase e5large arctic"}
SPACES=${SPACES:-"bgebase e5large arctic m0"}
export SEEDS_A SEEDS_B SEEDS_C SEEDS_D TAGS SPACES         # analyze_r9.py đọc cùng danh sách
N100=${N100:-50000}; NSMALL=${NSMALL:-10000}
FR100=${FR100:-0.02}; FRSMALL=${FRSMALL:-0.1}
ST_CODE=${ST_CODE:-600}; ST_SCI=${ST_SCI:-155}
X=${X:-}; XB=${XB:-}                   # tham số thêm, CHỈ dùng khi chạy thử trên dữ liệu giả
L=evo/r9_logs
mkdir -p $L
JL=$L/jobs.log
F="grep --line-buffered -v WARNING.clustering"
{ echo "=== ĐỢT 9 bắt đầu $(date '+%F %T')  P=$P  pha: $PHASES"; free -g | head -2;
  python3 -c "import numpy; print('numpy', numpy.__version__)"; } | tee -a $JL

# ---------- 0. kiểm tra
git describe --tags --exact-match 2>/dev/null | grep -qx "evo-r9-prereg" \
  && echo "HEAD = tag evo-r9-prereg ($(git rev-parse --short HEAD))" | tee -a $JL \
  || echo "CẢNH BÁO: HEAD chưa ở tag evo-r9-prereg" | tee -a $JL
sha256sum -c evo/SHA256SUMS_round9 --quiet 2>&1 | tee -a $JL
[ "${PIPESTATUS[0]}" = "0" ] || { echo "FILE CỦA ĐỢT 9 BỊ SỬA SO VỚI SHA256SUMS_round9, DỪNG" | tee -a $JL; exit 1; }
miss=0
for t in $TAGS; do for s in $SEEDS_C; do
  f=probeV8_code100kfq_${t}_s${s}_itq_q.json; [ -e $f ] || { echo "THIẾU $f (kết quả đợt 8)" | tee -a $JL; miss=1; }
done; done
for t in $SPACES; do for s in $SEEDS_D; do
  f=probeP_code100kfq_${t}_s${s}.json; [ -e $f ] || { echo "THIẾU $f (kết quả đợt 8)" | tee -a $JL; miss=1; }
done; done
[ "$miss" = "0" ] || { echo "THIẾU FILE, DỪNG" | tee -a $JL; exit 1; }
have() {   # $1 dataset, $2 tag
  for f in data/$1_corpus_embeddings.npy data/$1_pq_codebook_m512.npy data/$1_pq_codes_m512.npy \
           data/$1_$2_corpus_embeddings.npy data/$1_$2_query_embeddings.npy data/$1_$2_ground_truth.json; do
    [ -e $f ] || return 1; done
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
V="python3 evo/11_probe_safe.py --dataset code100kfq --nodes $N100 --frac $FR100 --confirms 1 --e1-place itq_q"
POLC="static,lazy,lazyV,lazyVbgD,full,mapall,mapkeep"
POL9="static,lazy,bg,lazyV,bgV,lazyVbg,lazyVbgD,full,mapall,mapkeep"
CSETS="ch:churn_min=720,median_session=120,repair_every=60;fail:fail_at=1500,fail_frac=0.3"
PP="python3 evo/10_probe_placement.py"
RT1=$(echo $TAGS | cut -d' ' -f1); RT2=$(echo $TAGS | awk '{print $NF}'); RS=$(echo $SEEDS_A | cut -d' ' -f1)
if [[ " $PHASES " == *" R "* ]]; then
  echo "r9_rep_${RT1}_s${RS}|$V --tag $RT1 --seed $RS --policies static,lazy,lazyV,lazyVbgD,full,mapall --check-10 none --check-prev probeV8_code100kfq_${RT1}_s${RS}_itq_q.json --out probeVR9_code100kfq_${RT1}_s${RS}_itq_q.json $X $XB 2>&1 | $F" >> $J
  echo "r9_noop_${RT2}_s${RS}|$V --tag $RT2 --seed $RS --policies static,lazy,lazyV,lazyVbgD,mapall --zipf 1.0 --churn-min 720 --median-session 1e12 --repair-every 60 --check-10 none --check-prev probeV8_code100kfq_${RT2}_s${RS}_itq_q.json --out probeVR9noop_code100kfq_${RT2}_s${RS}_itq_q.json $X $XB 2>&1 | $F" >> $J
fi
if [[ " $PHASES " == *" A "* ]]; then
  for s in $SEEDS_C; do for t in $TAGS; do
    cs=""; [[ " $SEEDS_A " == *" $s "* ]] && cs="--churn-sets '$CSETS' --churn-policies $POLC --churn-zipf 1.0"
    echo "v9x_${t}_s${s}|$V --tag $t --seed $s --policies static,mapkeep $cs --check-10 none --check-prev probeV8_code100kfq_${t}_s${s}_itq_q.json --out probeV9X_code100kfq_${t}_s${s}_itq_q.json $X $XB 2>&1 | $F" >> $J
  done; done
fi
if [[ " $PHASES " == *" B "* ]]; then
  for ds in code scifact; do for t in $TAGS; do
    if ! have $ds $t; then echo "bỏ qua B: thiếu dữ liệu $ds $t" | tee -a $JL; continue; fi
    if [ "$ds" = "code" ]; then st=$ST_CODE; cpz="0,150,300,600"; win=150; else st=$ST_SCI; cpz="0,50,100,155"; win=50; fi
    for s in $SEEDS_B; do
      echo "v9s_${ds}_${t}_s${s}|python3 evo/11_probe_safe.py --dataset $ds --nodes $NSMALL --frac $FRSMALL --confirms 1 --e1-place itq_q --tag $t --seed $s --policies $POL9 --stream $st --checkpoints $cpz --window $win --out probeV9_${ds}_${t}_s${s}_itq_q.json $X 2>&1 | $F" >> $J
    done
  done; done
fi
if [[ " $PHASES " == *" D "* ]]; then
  for t in $SPACES; do for s in $SEEDS_D; do
    sp=$([ "$t" = "m0" ] && echo "--space m0" || echo "")
    echo "p9_${t}_s${s}|$PP --dataset code100kfq --tag $t $sp --seed $s --nodes $N100 --frac $FR100 --variants itq_q,itq128_q,itq256_q --check-prev probeP_code100kfq_${t}_s${s}.json --out probeP9_code100kfq_${t}_s${s}.json $X 2>&1 | $F" >> $J
  done; done
fi
if [[ " $PHASES " == *" E "* ]]; then
  for t in $SPACES; do for s in $SEEDS_D; do
    sp=$([ "$t" = "m0" ] && echo "--space m0" || echo "")
    echo "d9_${t}_s${s}|python3 evo/12_diag_itq.py --dataset code100kfq --tag $t $sp --seed $s --nodes $N100 --frac $FR100 $X 2>&1 | $F" >> $J
  done; done
fi
echo "đợt 9: $(wc -l < $J) job, P=$P" | tee -a $JL
run_jobs $J

# ---------- tổng hợp
python3 evo/analyze_r9.py > evo/r9_logs/r9_summary.txt 2>&1
{
  cat evo/r9_logs/r9_summary.txt
  echo "################ TỰ KIỂM (dòng >>> và lệch trong log)"
  grep -H ">>>\|    lệch:" $L/*.log | sed "s#$L/##" | grep -v "bỏ qua"
  echo "################ LỖI"
  grep -H "Traceback\|Error\|LỆCH\|DỪNG\|\*\*\*" $L/*.log | sed "s#$L/##" | head -60
  echo "################ THỜI GIAN"
  cat $JL
} > evo/round9_all.txt
echo "XONG ĐỢT 9 $(date '+%F %T')" | tee -a $JL evo/round9_all.txt
