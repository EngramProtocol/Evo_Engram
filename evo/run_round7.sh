#!/bin/bash
# Đợt 7: thăm dò cho bản nâng cấp sau desk reject của JNCA (chưa đăng ký trước, không thuộc đánh giá xác nhận).
#   A  Placement native (10_probe_placement.py) trên code100kfq x {bge-base, e5-large, Arctic, M0} x seed 3 4 5,
#      50.000 node: SRP như bài, SRP trừ tâm, PCA và ITQ học trên mẫu S với ngưỡng trung vị; L = 5, 10 bảng,
#      T = 2, 4, 8, 16 probe; recall, số ứng viên, số peer, tải lưu trữ và tải truy vấn theo peer.
#      Tự kiểm: srp, srp_c, srp_cq ở L = 5, T = 8 trùng E1ONLY, E1ONLY_c, E1ONLY_cq của 04b đợt 4.
#   B  Migrate an toàn (11_probe_safe.py) trên code100kfq x 3 cặp x seed 3 4 5: static, lazy, bg, lazyD
#      (không retire), lazyV1, lazyV2 (retire sau 1 hoặc 2 xác nhận native), bgV1, bgV2; Zipf 1 và đều.
#      Tự kiểm: static, lazy, bg trùng probeL_*_ku.json của 06 đợt 4. Thêm 2 job ablation cho Arctic seed 3:
#      --dual-score adapter và --dual-slots shared.
#   C  Điểm kiểm tra mô hình dị hướng trên corpus nhỏ: code (20k) và SciFact x {bge-base, e5-large, Arctic, M0}
#      x seed 3 4 5, 10.000 node, frac 0.1, chỉ L = 5 (nhẹ). Tự kiểm với probeG_* đợt 3 và 4 khi có cùng seed.
# Yêu cầu: kết quả đợt 4 ở thư mục gốc repo (probeG_code100kfq_*, probeL_code100kfq_*_ku); HEAD đúng tag evo-r7-pilot.
# Chạy:    tmux new -s round7 -d "bash ~/Evo_Engram/evo/run_round7.sh"
# File ra mới: probeP_* (A, C), probeV_* (B). Không ghi đè file đợt trước.
# Chỉ chạy một phần: PHASES="A B" (mặc định "A B C").
cd ${EVO_ROOT:-~/Evo_Engram} || exit 1
[ -f venv/bin/activate ] && source venv/bin/activate
export OPENBLAS_NUM_THREADS=${NT:-1} OMP_NUM_THREADS=${NT:-1} MKL_NUM_THREADS=${NT:-1}
P=${P:-4}
PHASES=${PHASES:-"A B C"}
SEEDS=${SEEDS:-"3 4 5"}
TAGS=${TAGS:-"bgebase e5large arctic"}
N100=${N100:-50000}
NSMALL=${NSMALL:-10000}
X=${X:-}; XB=${XB:-}; XC=${XC:-}   # tham số thêm, CHỈ dùng khi chạy thử trên dữ liệu giả
L=evo/r7_logs
mkdir -p $L
JL=$L/jobs.log
F="grep --line-buffered -v WARNING.clustering"
{ echo "=== ĐỢT 7 bắt đầu $(date '+%F %T')  P=$P  pha: $PHASES"; nproc; free -g | head -2; } | tee -a $JL

# ---------- 0. kiểm tra
git describe --tags --exact-match 2>/dev/null | grep -qx "evo-r7-pilot" \
  && echo "HEAD = tag evo-r7-pilot ($(git rev-parse --short HEAD))" | tee -a $JL \
  || echo "CẢNH BÁO: HEAD chưa ở tag evo-r7-pilot" | tee -a $JL
sha256sum -c evo/SHA256SUMS_round7 --quiet 2>&1 | tee -a $JL
[ "${PIPESTATUS[0]}" = "0" ] || { echo "FILE CỦA ĐỢT 7 BỊ SỬA SO VỚI SHA256SUMS_round7, DỪNG" | tee -a $JL; exit 1; }
miss=0
for t in $TAGS; do for s in $SEEDS; do
  for f in probeG_code100kfq_${t}_s${s}.json probeL_code100kfq_${t}_s${s}_ku.json; do
    [ -e $f ] || { echo "THIẾU $f (kết quả đợt 4, cần để tự kiểm)" | tee -a $JL; miss=1; }; done; done; done
[ "$miss" = "0" ] || { echo "THIẾU FILE, DỪNG" | tee -a $JL; exit 1; }
have() {   # $1 dataset, $2 tag hoặc m0: đủ file dữ liệu chưa
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

# Một hàng đợi chung, job dài trước: B (dòng 3.000 truy vấn x 16 lượt), rồi A, rồi C
J=$L/jobs.txt; : > $J
V="python3 evo/11_probe_safe.py --dataset code100kfq --nodes $N100 --frac 0.02"
PP="python3 evo/10_probe_placement.py"
if [[ " $PHASES " == *" B "* ]]; then
  for t in $TAGS; do for s in $SEEDS; do
    echo "v_code100kfq_${t}_s${s}|$V --tag $t --seed $s $X $XB 2>&1 | $F" >> $J
  done; done
  s1=$(echo $SEEDS | cut -d' ' -f1)
  echo "va_code100kfq_arctic_s${s1}|$V --tag arctic --seed $s1 --zipf 1.0 --policies lazy,lazyD,lazyV --dual-score adapter --out probeV_code100kfq_arctic_s${s1}_dsadapter.json $X $XB 2>&1 | $F" >> $J
  echo "vs_code100kfq_arctic_s${s1}|$V --tag arctic --seed $s1 --zipf 1.0 --policies lazy,lazyD,lazyV --dual-slots shared --out probeV_code100kfq_arctic_s${s1}_shared.json $X $XB 2>&1 | $F" >> $J
fi
if [[ " $PHASES " == *" A "* ]]; then
  for t in $TAGS m0; do for s in $SEEDS; do
    sp=$([ "$t" = "m0" ] && echo "--space m0" || echo "")
    echo "p_code100kfq_${t}_s${s}|$PP --dataset code100kfq --tag $t $sp --seed $s --nodes $N100 --frac 0.02 $X 2>&1 | $F" >> $J
  done; done
fi
if [[ " $PHASES " == *" C "* ]]; then
  for ds in code scifact; do for t in $TAGS m0; do
    if ! have $ds $t; then echo "bỏ qua C: thiếu dữ liệu $ds $t" | tee -a $JL; continue; fi
    for s in $SEEDS; do
      sp=$([ "$t" = "m0" ] && echo "--space m0" || echo "")
      echo "p_${ds}_${t}_s${s}|$PP --dataset $ds --tag $t $sp --seed $s --nodes $NSMALL --frac 0.1 --Ls 5 --variants srp,srp_c,srp_cq,pca_q,itq_q $X $XC 2>&1 | $F" >> $J
    done
  done; done
fi
echo "đợt 7: $(wc -l < $J) job, P=$P" | tee -a $JL
run_jobs $J

# ---------- tổng hợp
python3 evo/analyze_r7.py > evo/r7_summary.txt 2>&1
{
  cat evo/r7_summary.txt
  echo "################ TỰ KIỂM (dòng >>> trong log)"
  grep -H ">>>" $L/*.log | sed "s#$L/##"
  echo "################ LỖI"
  grep -H "Traceback\|Error\|LỆCH\|DỪNG\|\*\*\*" $L/*.log | sed "s#$L/##" | head -60
  echo "################ THỜI GIAN"
  cat $JL
} > evo/round7_all.txt
echo "XONG ĐỢT 7 $(date '+%F %T')" | tee -a $JL evo/round7_all.txt
