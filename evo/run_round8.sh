#!/bin/bash
# Đợt 8: đánh giá xác nhận, đăng ký trước trong evo/PREREG_round8.md (tag evo-r8-prereg).
#   R  Chạy lại hai job đợt 7b (bge-base itq_q seed 3, Arctic u seed 3) và so từng số (--check-prev).
#   A  Migrate trên placement học itq_q: code100kfq x 3 cặp x seed 6..15, chính sách static, lazy, bg, lazyV1, bgV1,
#      lazyVbg, lazyVbgD, full, mapall; Zipf 1 và đều. (H3, H4, H5)
#   B  Như A với khoá của bài (u), seed 6..10. (thăm dò)
#   C  Placement study: code100kfq x {bge-base, e5-large, Arctic, M0} x seed 6..8 đủ biến thể (H2);
#      code 20k và SciFact x 4 không gian x seed 6..8, L = 5 (cho H1 và thăm dò).
#   D  Mô hình dị hướng (10 --aniso-only 1): 3 dataset x 4 không gian x seed 6..8. (H1)
# Yêu cầu: kết quả đợt 7b (probeVB_*) và đợt 7 (probeP_code100kfq_*_s3.json) và đợt 4 (probeL_*_ku.json) ở thư mục gốc
#          repo; HEAD đúng tag evo-r8-prereg.
# Chạy:    tmux new -s round8 -d "bash ~/Evo_Engram/evo/run_round8.sh"
# File ra mới: probeVR_* (R), probeV8_* (A, B), probeP_* và probeA_* với seed 6..8 (C, D). Không ghi đè file cũ.
# Chỉ chạy một phần: PHASES="R A" (mặc định "R A B C D").
cd ${EVO_ROOT:-~/Evo_Engram} || exit 1
[ -f venv/bin/activate ] && source venv/bin/activate
export OPENBLAS_NUM_THREADS=${NT:-1} OMP_NUM_THREADS=${NT:-1} MKL_NUM_THREADS=${NT:-1}
P=${P:-4}
PHASES=${PHASES:-"R A B C D"}
SEEDS_A=${SEEDS_A:-"6 7 8 9 10 11 12 13 14 15"}
SEEDS_B=${SEEDS_B:-"6 7 8 9 10"}
SEEDS_C=${SEEDS_C:-"6 7 8"}
TAGS=${TAGS:-"bgebase e5large arctic"}
RTAG_ITQ=${RTAG_ITQ:-bgebase}; RTAG_U=${RTAG_U:-arctic}
export SEEDS_A SEEDS_B SEEDS_C TAGS               # analyze_r8.py đọc cùng danh sách seed
N100=${N100:-50000}
NSMALL=${NSMALL:-10000}
X=${X:-}; XB=${XB:-}; XC=${XC:-}   # tham số thêm, CHỈ dùng khi chạy thử trên dữ liệu giả
L=evo/r8_logs
mkdir -p $L
JL=$L/jobs.log
F="grep --line-buffered -v WARNING.clustering"
{ echo "=== ĐỢT 8 bắt đầu $(date '+%F %T')  P=$P  pha: $PHASES"; free -g | head -2;
  python3 -c "import numpy; print('numpy', numpy.__version__)"; } | tee -a $JL

# ---------- 0. kiểm tra
git describe --tags --exact-match 2>/dev/null | grep -qx "evo-r8-prereg" \
  && echo "HEAD = tag evo-r8-prereg ($(git rev-parse --short HEAD))" | tee -a $JL \
  || echo "CẢNH BÁO: HEAD chưa ở tag evo-r8-prereg" | tee -a $JL
sha256sum -c evo/SHA256SUMS_round8 --quiet 2>&1 | tee -a $JL
[ "${PIPESTATUS[0]}" = "0" ] || { echo "FILE CỦA ĐỢT 8 BỊ SỬA SO VỚI SHA256SUMS_round8, DỪNG" | tee -a $JL; exit 1; }
miss=0
if [[ " $PHASES " == *" R "* ]]; then
  for f in probeVB_code100kfq_${RTAG_ITQ}_s3_itq_q.json probeVB_code100kfq_${RTAG_U}_s3_u.json \
           probeP_code100kfq_${RTAG_ITQ}_s3.json probeL_code100kfq_${RTAG_U}_s3_ku.json; do
    [ -e $f ] || { echo "THIẾU $f (kết quả đợt 4, 7 hoặc 7b, cần cho pha R)" | tee -a $JL; miss=1; }; done
fi
[ "$miss" = "0" ] || { echo "THIẾU FILE, DỪNG" | tee -a $JL; exit 1; }
have() {   # $1 dataset, $2 tag hoặc m0
  if [ "$2" = "m0" ]; then
    for f in data/$1_corpus_embeddings.npy data/$1_query_embeddings.npy data/$1_ground_truth.json \
             data/$1_pq_codebook_m512.npy data/$1_pq_codes_m512.npy; do [ -e $f ] || return 1; done
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
POL8="static,lazy,bg,lazyV,bgV,lazyVbg,lazyVbgD,full,mapall"
PP="python3 evo/10_probe_placement.py"
if [[ " $PHASES " == *" R "* ]]; then
  echo "r_itq_${RTAG_ITQ}_s3|$V --tag $RTAG_ITQ --seed 3 --e1-place itq_q --policies static,lazy,bg,lazyD,lazyV,bgV,lazyVbg,lazyVbgD --check-prev probeVB_code100kfq_${RTAG_ITQ}_s3_itq_q.json --out probeVR_code100kfq_${RTAG_ITQ}_s3_itq_q.json $X $XB 2>&1 | $F" >> $J
  echo "r_u_${RTAG_U}_s3|$V --tag $RTAG_U --seed 3 --policies static,lazy,bg,lazyV,bgV,lazyVbg,lazyVbgD --check-prev probeVB_code100kfq_${RTAG_U}_s3_u.json --out probeVR_code100kfq_${RTAG_U}_s3_u.json $X $XB 2>&1 | $F" >> $J
fi
if [[ " $PHASES " == *" A "* ]]; then
  for s in $SEEDS_A; do for t in $TAGS; do
    echo "v8_itq_${t}_s${s}|$V --tag $t --seed $s --e1-place itq_q --policies $POL8 --check-10 none --out probeV8_code100kfq_${t}_s${s}_itq_q.json $X $XB 2>&1 | $F" >> $J
  done; done
fi
if [[ " $PHASES " == *" C "* ]]; then
  for t in $TAGS m0; do for s in $SEEDS_C; do
    sp=$([ "$t" = "m0" ] && echo "--space m0" || echo "")
    echo "p8_code100kfq_${t}_s${s}|$PP --dataset code100kfq --tag $t $sp --seed $s --nodes $N100 --frac 0.02 $X 2>&1 | $F" >> $J
  done; done
fi
if [[ " $PHASES " == *" B "* ]]; then
  for s in $SEEDS_B; do for t in $TAGS; do
    echo "v8_u_${t}_s${s}|$V --tag $t --seed $s --policies $POL8 --check-06 none --out probeV8_code100kfq_${t}_s${s}_u.json $X $XB 2>&1 | $F" >> $J
  done; done
fi
if [[ " $PHASES " == *" C "* ]]; then
  for ds in code scifact; do for t in $TAGS m0; do
    if ! have $ds $t; then echo "bỏ qua C: thiếu dữ liệu $ds $t" | tee -a $JL; continue; fi
    for s in $SEEDS_C; do
      sp=$([ "$t" = "m0" ] && echo "--space m0" || echo "")
      echo "p8_${ds}_${t}_s${s}|$PP --dataset $ds --tag $t $sp --seed $s --nodes $NSMALL --frac 0.1 --Ls 5 --variants srp,srp_c,srp_cq,pca_q,itq_q $X $XC 2>&1 | $F" >> $J
    done
  done; done
fi
if [[ " $PHASES " == *" D "* ]]; then
  for ds in code100kfq code scifact; do for t in $TAGS m0; do
    if ! have $ds $t; then echo "bỏ qua D: thiếu dữ liệu $ds $t" | tee -a $JL; continue; fi
    sp=$([ "$t" = "m0" ] && echo "--space m0" || echo "")
    if [ "$ds" = "code100kfq" ]; then nn=$N100; fr=0.02; else nn=$NSMALL; fr=0.1; fi
    for s in $SEEDS_C; do
      echo "a8_${ds}_${t}_s${s}|$PP --aniso-only 1 --dataset $ds --tag $t $sp --seed $s --nodes $nn --frac $fr $X $XC 2>&1 | $F" >> $J
    done
  done; done
fi
echo "đợt 8: $(wc -l < $J) job, P=$P" | tee -a $JL
run_jobs $J

# ---------- tổng hợp
python3 evo/analyze_r8.py > evo/r8_summary.txt 2>&1
{
  cat evo/r8_summary.txt
  echo "################ TỰ KIỂM (dòng >>> và lệch trong log)"
  grep -H ">>>\|    lệch:" $L/*.log | sed "s#$L/##" | grep -v "bỏ qua"
  echo "################ LỖI"
  grep -H "Traceback\|Error\|LỆCH\|DỪNG\|\*\*\*" $L/*.log | sed "s#$L/##" | head -60
  echo "################ THỜI GIAN"
  cat $JL
} > evo/round8_all.txt
echo "XONG ĐỢT 8 $(date '+%F %T')" | tee -a $JL evo/round8_all.txt
