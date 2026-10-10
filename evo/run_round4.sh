#!/bin/bash
# Đợt 4: đánh giá xác nhận (đăng ký trước trong evo/PREREG_round4.md) và ba phần thăm dò.
#   A  holdout (03c) và multi-epoch (04b): code100kfq x 3 cặp; cặp mới arctic trên code 20k và SciFact; seed 3 4 5
#   B  lazy (06) cho cùng các cấu hình trên; lazy dưới trust model re-indexer + workload paraphrase
#      (code 20k và SciFact, bge-base và e5-large, seed như đợt 3b để so ghép cặp với lặp nguyên văn)
#   C  mô phỏng chi phí end-to-end (08) trong simulator SimPy của V-Engram
# Yêu cầu: đã chạy evo/07_assemble_data.py; HEAD đúng tag evo-confirm-v1.
# Chạy:   tmux new -s round4 -d "bash ~/Evo_Engram/evo/run_round4.sh"
# Không ghi đè kết quả các đợt trước (seed mới, tên file mới probeLR_/probeS_).
cd ${EVO_ROOT:-~/Evo_Engram} || exit 1
[ -f venv/bin/activate ] && source venv/bin/activate
export OPENBLAS_NUM_THREADS=${NT:-4} OMP_NUM_THREADS=${NT:-4} MKL_NUM_THREADS=${NT:-4}
P=${P:-2}
CSEEDS=${CSEEDS:-"3 4 5"}          # seed xác nhận
ESEEDS=${ESEEDS:-"20235956 1 2"}   # seed của phần thăm dò (trùng đợt 3b)
N100=${N100:-50000}                # số node overlay cho code100kfq
X=${X:-}; XL=${XL:-}; XS=${XS:-}   # tham số thêm, CHỈ dùng khi chạy thử trên dữ liệu giả
L=evo/r4_logs
mkdir -p $L
JL=$L/jobs.log
F="grep --line-buffered -v WARNING.clustering"
{ echo "=== ĐỢT 4 bắt đầu $(date '+%F %T')  P=$P  seed xác nhận: $CSEEDS"; nproc; free -g | head -2; } | tee $JL

# ---------- 0. kiểm tra
git describe --tags --exact-match 2>/dev/null | grep -qx "evo-confirm-v1" \
  && echo "HEAD = tag evo-confirm-v1 ($(git rev-parse --short HEAD))" | tee -a $JL \
  || echo "CẢNH BÁO: HEAD chưa ở tag evo-confirm-v1" | tee -a $JL
sha256sum -c evo/SHA256SUMS_round4 --quiet 2>&1 | tee -a $JL
[ "${PIPESTATUS[0]}" = "0" ] || { echo "FILE ĐÓNG BĂNG BỊ SỬA SO VỚI SHA256SUMS_round4, DỪNG" | tee -a $JL; exit 1; }
miss=0
for t in bgebase e5large arctic; do
  for f in code100kfq_${t}_corpus_embeddings.npy code100kfq_${t}_query_embeddings.npy code100kfq_${t}_ground_truth.json; do
    [ -e data/$f ] || { echo "THIẾU data/$f" | tee -a $JL; miss=1; }; done; done
for f in code100kfq_corpus_embeddings.npy code100kfq_query_embeddings.npy code100kfq_pq_codebook_m512.npy \
         code100kfq_pq_codes_m512.npy code_arctic_ground_truth.json scifact_arctic_ground_truth.json \
         code_bgebase_para_embeddings.npy scifact_e5large_para_ground_truth.json code_para_mask.npy; do
  [ -e data/$f ] || { echo "THIẾU data/$f" | tee -a $JL; miss=1; }; done
[ -d src ] || { echo "THIẾU src/ của V-Engram (cần cho 08)" | tee -a $JL; miss=1; }
[ "$miss" = "0" ] || { echo "THIẾU DỮ LIỆU, chạy evo/07_assemble_data.py trước. DỪNG" | tee -a $JL; exit 1; }

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

# ---------- 1. đo CPU nhúng của arctic (chạy một mình để số đo không bị tranh CPU)
if [ -z "$SKIP_BENCH" ] && [ ! -f bench_arctic.json ]; then
  echo "BẮT ĐẦU $(date +%T) bench_arctic" >> $JL
  python3 evo/05_bench_cpu.py --m1 Snowflake/snowflake-arctic-embed-m-v1.5 --tag arctic > $L/bench_arctic.log 2>&1
  echo "XONG    $(date +%T) bench_arctic (mã thoát $?)" >> $JL
fi

# ---------- 2. pha A: holdout + multi-epoch
A=$L/phaseA.txt; : > $A
for t in bgebase e5large arctic; do for s in $CSEEDS; do
  echo "g_code100kfq_${t}_s${s}|python3 evo/04b_probe_multiepoch2.py --dataset code100kfq --tag $t --seed $s --nodes $N100 --frac 0.02 --fmig 0,0.02,0.1,0.2,0.5,0.9,1.0 $X 2>&1 | $F" >> $A
done; done
for s in $CSEEDS; do
  echo "g_code_arctic_s${s}|python3 evo/04b_probe_multiepoch2.py --tag arctic --seed $s $X 2>&1 | $F" >> $A
  echo "g_scifact_arctic_s${s}|python3 evo/04b_probe_multiepoch2.py --dataset scifact --tag arctic --seed $s $X 2>&1 | $F" >> $A
done
H="--holdout 1 --mlp-lrs 3e-5,1e-4,3e-4,1e-3 --mlp-patience 20"
for t in bgebase e5large arctic; do for s in $CSEEDS; do for fr in 0.01 0.02 0.05; do
  echo "h_code100kfq_${t}_s${s}_f${fr}|python3 evo/03c_probe_holdout.py --dataset code100kfq --tag $t --seed $s --nodes $N100 --frac $fr $H $X 2>&1 | $F" >> $A
done; done; done
for s in $CSEEDS; do
  for fr in 0.05 0.10 0.25; do
    echo "h_code_arctic_s${s}_f${fr}|python3 evo/03c_probe_holdout.py --tag arctic --seed $s --frac $fr $H $X 2>&1 | $F" >> $A
  done
  for fr in 0.10 0.386; do
    echo "h_scifact_arctic_s${s}_f${fr}|python3 evo/03c_probe_holdout.py --dataset scifact --tag arctic --seed $s --frac $fr $H $X 2>&1 | $F" >> $A
  done
done
echo "pha A: $(wc -l < $A) job" | tee -a $JL
run_jobs $A

# ---------- 3. pha B: lazy (xác nhận) + lazy dưới re-indexer và paraphrase (thăm dò)
TR="z1|PROB|static,z1|PROB|lazy,z1|PROB|bg"
B=$L/phaseB.txt; : > $B
for t in bgebase e5large arctic; do for s in $CSEEDS; do
  echo "l_code100kfq_${t}_s${s}|python3 evo/06_probe_lazy.py --dataset code100kfq --tag $t --seed $s --nodes $N100 --frac 0.02 --check-3b none --trace-runs '$TR' $X $XL 2>&1 | $F" >> $B
done; done
for s in $CSEEDS; do
  echo "l_code_arctic_s${s}|python3 evo/06_probe_lazy.py --tag arctic --seed $s --check-3b none $X $XL 2>&1 | $F" >> $B
  echo "l_scifact_arctic_s${s}|python3 evo/06_probe_lazy.py --dataset scifact --tag arctic --seed $s --check-3b none $X $XL 2>&1 | $F" >> $B
done
RX="--zipf 1.0 --fusions PROB --workloads verbatim,para --reindex inf:0,3:0,1:0,inf:150,inf:600"
TRX="$TR,z1|PROB|lazy|r3:0,z1|PROB|bg|r3:0"
for ds in code scifact; do for t in bgebase e5large; do for s in $ESEEDS; do
  pre=""; [ "$ds" = "code" ] || pre="${ds}_"
  echo "lr_${ds}_${t}_s${s}|python3 evo/06_probe_lazy.py --dataset $ds --tag $t --seed $s $RX --trace-runs '$TRX' --out probeLR_${pre}${t}_s${s}.json $X $XL 2>&1 | $F" >> $B
done; done; done
echo "pha B: $(wc -l < $B) job" | tee -a $JL
run_jobs $B

# ---------- 4. pha C: mô phỏng chi phí end-to-end
C=$L/phaseC.txt; : > $C
for ds in code scifact; do for t in bgebase e5large; do
  pre=""; [ "$ds" = "code" ] || pre="${ds}_"
  s0=${ESEEDS%% *}
  echo "s_${ds}_${t}_s${s0}|python3 evo/08_sim_evo.py --dataset $ds --tag $t --seed $s0 --lazy-trace probeLR_${pre}${t}_s${s0}_trace.json $X $XS 2>&1 | $F" >> $C
done; done
for s in ${ESEEDS#* }; do
  echo "s_code_bgebase_s${s}|python3 evo/08_sim_evo.py --tag bgebase --seed $s --lazy-trace probeLR_bgebase_s${s}_trace.json $X $XS 2>&1 | $F" >> $C
done
s1=${CSEEDS%% *}
echo "s_code100kfq_bgebase_s${s1}|python3 evo/08_sim_evo.py --dataset code100kfq --tag bgebase --seed $s1 --nodes $N100 --frac 0.02 --lazy-trace probeL_code100kfq_bgebase_s${s1}_ku_trace.json $X $XS 2>&1 | $F" >> $C
echo "pha C: $(wc -l < $C) job" | tee -a $JL
run_jobs $C

# ---------- 5. tổng hợp
S=evo/r4_summary
python3 evo/analyze_prereg.py > ${S}_prereg.txt 2>&1
python3 evo/analyze_03.py "probeH_code100kfq_*_ho1.json" > ${S}_holdout_code100kfq.txt 2>&1
python3 evo/analyze_03.py "probeH_arctic_*_ho1.json" "probeH_scifact_arctic_*_ho1.json" > ${S}_holdout_arctic.txt 2>&1
python3 evo/analyze_04b.py "probeG_code100kfq_*.json" > ${S}_04b_code100kfq.txt 2>&1
python3 evo/analyze_04b.py "probeG_arctic_*.json" "probeG_scifact_arctic_*.json" > ${S}_04b_arctic.txt 2>&1
python3 evo/analyze_06.py "probeL_code100kfq_*_ku.json" > ${S}_06_code100kfq.txt 2>&1
python3 evo/analyze_06.py "probeL_arctic_*_ku.json" "probeL_scifact_arctic_*_ku.json" > ${S}_06_arctic.txt 2>&1
python3 evo/analyze_06b.py "probeLR_*.json" > ${S}_06b_reindex_para.txt 2>&1
python3 evo/analyze_08.py "probeS_*.json" > ${S}_08_sim.txt 2>&1
{
  for f in prereg holdout_code100kfq holdout_arctic 04b_code100kfq 04b_arctic 06_code100kfq 06_arctic \
           06b_reindex_para 08_sim; do
    echo "################ r4_summary_$f"; cat ${S}_$f.txt; echo
  done
  echo "################ BENCH ARCTIC"; [ -f $L/bench_arctic.log ] && grep -v "Loading weights\|Warning\|FutureWarning\|get_sentence" $L/bench_arctic.log
  echo "################ TỰ KIỂM (dòng >>> trong log)"
  grep -H ">>>" $L/*.log | sed "s#$L/##"
  echo "################ LỖI"
  grep -H "Traceback\|Error\|LỆCH\|DỪNG\|\*\*\*" $L/*.log | sed "s#$L/##" | head -60
  echo "################ MLP"
  grep -H "^MLP" $L/h_*.log | sed "s#$L/##"
  echo "################ THỜI GIAN"
  cat $JL
} > evo/round4_all.txt
echo "XONG ĐỢT 4 $(date '+%F %T')" | tee -a $JL evo/round4_all.txt
