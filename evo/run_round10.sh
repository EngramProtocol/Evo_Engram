#!/bin/bash
# Đợt 10: placement có giới hạn tải (C2), C3 trên placement đó, migrate tới khi xong (evo/PREREG_round10.md, tag evo-r10-prereg).
#   R  Kiểm hồi quy: 10 chạy lại Arctic seed 6 (srp_c, itq_q so từng số với đợt 8; itq_q+cap1000000 phải trùng itq_q), và 11
#      chạy lại job đợt 8 bge-base seed 6 với --e1-cap 1000000 (phải trùng từng số đợt 8).
#   A  Placement code100kfq x 4 không gian x seed 16..18: srp, srp_c, itq_q, itq128_q, itq_q+cap8, itq_q+cap16, itq_q+cap32. (H9)
#   B  C3 trên placement itq_q+cap16, code100kfq, 3 model x seed 16..25, static, lazy, lazyV1, lazyVbgD, full, Zipf 1 và đều. (H10)
#   C  Migrate tới khi xong: code 20k (dòng 3.000, T = 1.500, 3.000) và SciFact (dòng 800, T = 400, 800), overlay 10.000 node,
#      S = 10%, 3 model x seed 16..25, Zipf 1: static, lazy, full; bg, lazybg, rebuild, lazyVbgD, lazyVbgDc25 với mỗi T.
# Pha R và A chạy trước (pha B tự kiểm placement với file của pha A), rồi B và C chạy chung.
# Yêu cầu: probeP_code100kfq_arctic_s6.json và probeV8_code100kfq_bgebase_s6_itq_q.json của đợt 8 ở thư mục gốc repo; HEAD
#          đúng tag evo-r10-prereg.
# Chạy:    tmux new -s round10 -d "bash ~/Evo_Engram/evo/run_round10.sh"
# File ra mới: probePR10_*, probeVR10_* (R), probeP10_* (A), probeV10_* (B), probeV10F_* (C). Không ghi đè file cũ.
#              Chỉ chạy một phần: PHASES="R A" (mặc định "R A B C").
cd ${EVO_ROOT:-~/Evo_Engram} || exit 1
[ -f venv/bin/activate ] && source venv/bin/activate
export OPENBLAS_NUM_THREADS=${NT:-1} OMP_NUM_THREADS=${NT:-1} MKL_NUM_THREADS=${NT:-1}
P=${P:-4}
PHASES=${PHASES:-"R A B C"}
SEEDS_A=${SEEDS_A:-"16 17 18"}
SEEDS_B=${SEEDS_B:-"16 17 18 19 20 21 22 23 24 25"}
SEEDS_C=${SEEDS_C:-"16 17 18 19 20 21 22 23 24 25"}
TAGS=${TAGS:-"bgebase e5large arctic"}
SPACES=${SPACES:-"bgebase e5large arctic m0"}
export SEEDS_A SEEDS_B SEEDS_C TAGS SPACES                 # analyze_r10.py đọc cùng danh sách
RS=${RS:-6}; RT_P=${RT_P:-arctic}; RT_V=${RT_V:-bgebase}  # pha R: seed và không gian của đợt 8 dùng để so
N100=${N100:-50000}; NSMALL=${NSMALL:-10000}
FR100=${FR100:-0.02}; FRSMALL=${FRSMALL:-0.1}
ST_CODE=${ST_CODE:-3000}; ST_SCI=${ST_SCI:-800}
FIN_CODE=${FIN_CODE:-"1500,3000"}; FIN_SCI=${FIN_SCI:-"400,800"}
CP_CODE=${CP_CODE:-"0,150,300,600,900,1200,1500,2000,2500,3000"}; CP_SCI=${CP_SCI:-"0,50,100,200,300,400,500,600,700,800"}
W_CODE=${W_CODE:-150}; W_SCI=${W_SCI:-50}
X=${X:-}; XB=${XB:-}                   # tham số thêm, CHỈ dùng khi chạy thử trên dữ liệu giả
L=evo/r10_logs
mkdir -p $L
JL=$L/jobs.log
F="grep --line-buffered -v WARNING.clustering"
{ echo "=== ĐỢT 10 bắt đầu $(date '+%F %T')  P=$P  pha: $PHASES"; free -g | head -2;
  python3 -c "import numpy; print('numpy', numpy.__version__)"; } | tee -a $JL

# ---------- 0. kiểm tra
git describe --tags --exact-match 2>/dev/null | grep -qx "evo-r10-prereg" \
  && echo "HEAD = tag evo-r10-prereg ($(git rev-parse --short HEAD))" | tee -a $JL \
  || echo "CẢNH BÁO: HEAD chưa ở tag evo-r10-prereg" | tee -a $JL
sha256sum -c evo/SHA256SUMS_round10 --quiet 2>&1 | tee -a $JL
[ "${PIPESTATUS[0]}" = "0" ] || { echo "FILE CỦA ĐỢT 10 BỊ SỬA SO VỚI SHA256SUMS_round10, DỪNG" | tee -a $JL; exit 1; }
miss=0
if [[ " $PHASES " == *" R "* ]]; then
  for f in probeP_code100kfq_${RT_P}_s${RS}.json probeV8_code100kfq_${RT_V}_s${RS}_itq_q.json; do
    [ -e $f ] || { echo "THIẾU $f (kết quả đợt 8)" | tee -a $JL; miss=1; }
  done
fi
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

J1=$L/jobs1.txt; : > $J1          # pha R, A
J2=$L/jobs2.txt; : > $J2          # pha B, C (sau khi R, A xong)
PP="python3 evo/10_probe_placement.py"
V="python3 evo/11_probe_safe.py --dataset code100kfq --nodes $N100 --frac $FR100 --confirms 1 --e1-place itq_q"
VARS="srp,srp_c,itq_q,itq128_q,itq_q+cap8,itq_q+cap16,itq_q+cap32"
if [[ " $PHASES " == *" R "* ]]; then
  echo "r10_prep_${RT_P}_s${RS}|$PP --dataset code100kfq --tag $RT_P --seed $RS --nodes $N100 --frac $FR100 --variants srp_c,itq_q,itq_q+cap1000000 --check-prev probeP_code100kfq_${RT_P}_s${RS}.json --out probePR10_code100kfq_${RT_P}_s${RS}.json $X 2>&1 | $F" >> $J1
  echo "r10_rep_${RT_V}_s${RS}|$V --tag $RT_V --seed $RS --policies static,lazy,lazyV,lazyVbgD,full --e1-cap 1000000 --check-10 none --check-prev probeV8_code100kfq_${RT_V}_s${RS}_itq_q.json --out probeVR10_code100kfq_${RT_V}_s${RS}_itq_q.json $X $XB 2>&1 | $F" >> $J1
fi
if [[ " $PHASES " == *" A "* ]]; then
  for t in $SPACES; do for s in $SEEDS_A; do
    sp=$([ "$t" = "m0" ] && echo "--space m0" || echo "")
    echo "p10_${t}_s${s}|$PP --dataset code100kfq --tag $t $sp --seed $s --nodes $N100 --frac $FR100 --variants $VARS --out probeP10_code100kfq_${t}_s${s}.json $X 2>&1 | $F" >> $J1
  done; done
fi
if [[ " $PHASES " == *" B "* ]]; then
  for s in $SEEDS_B; do for t in $TAGS; do
    c10=probeP10_code100kfq_${t}_s${s}.json; [[ " $SEEDS_A " == *" $s "* ]] || c10=none
    echo "v10_${t}_s${s}|$V --tag $t --seed $s --e1-cap 16 --policies static,lazy,lazyV,lazyVbgD,full --check-10 $c10 --out probeV10_code100kfq_${t}_s${s}_itq_q_cap16.json $X $XB 2>&1 | $F" >> $J2
  done; done
fi
if [[ " $PHASES " == *" C "* ]]; then
  for ds in code scifact; do for t in $TAGS; do
    if ! have $ds $t; then echo "bỏ qua C: thiếu dữ liệu $ds $t" | tee -a $JL; continue; fi
    if [ "$ds" = "code" ]; then st=$ST_CODE; fin=$FIN_CODE; cp=$CP_CODE; win=$W_CODE; else st=$ST_SCI; fin=$FIN_SCI; cp=$CP_SCI; win=$W_SCI; fi
    for s in $SEEDS_C; do
      echo "v10f_${ds}_${t}_s${s}|python3 evo/11_probe_safe.py --dataset $ds --nodes $NSMALL --frac $FRSMALL --confirms 1 --e1-place itq_q --tag $t --seed $s --policies static,lazy,full,bg,lazybg,rebuild,lazyVbgD,lazyVbgDc25 --zipf 1.0 --stream $st --bg-finish $fin --checkpoints $cp --window $win --check-10 none --out probeV10F_${ds}_${t}_s${s}_itq_q.json $X 2>&1 | $F" >> $J2
    done
  done; done
fi
echo "đợt 10: $(( $(wc -l < $J1) + $(wc -l < $J2) )) job ($(wc -l < $J1) ở pha R, A; $(wc -l < $J2) ở pha B, C), P=$P" | tee -a $JL
run_jobs $J1
echo "--- xong pha R, A $(date '+%F %T')" | tee -a $JL
run_jobs $J2

# ---------- tổng hợp
python3 evo/analyze_r10.py > evo/r10_logs/r10_summary.txt 2>&1
{
  cat evo/r10_logs/r10_summary.txt
  echo "################ TỰ KIỂM (dòng >>> và lệch trong log)"
  grep -H ">>>\|    lệch:" $L/*.log | sed "s#$L/##" | grep -v "bỏ qua"
  echo "################ LỖI"
  grep -H "Traceback\|Error\|LỆCH\|DỪNG\|\*\*\*" $L/*.log | sed "s#$L/##" | head -60
  echo "################ THỜI GIAN"
  cat $JL
} > evo/round10_all.txt
echo "XONG ĐỢT 10 $(date '+%F %T')" | tee -a $JL evo/round10_all.txt
