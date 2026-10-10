#!/bin/bash
# Đợt 3: (A) multi-epoch bản 2 (04b) và holdout + baseline MLP (03c); (B) lazy migration theo Zipf (06).
# Pha B cần kết quả 04b của pha A (để tự kiểm), nên chạy sau. Không ghi đè kết quả các đợt trước.
# Chạy:   tmux new -s round3 -d "bash ~/Evo_Engram/evo/run_round3.sh"
# Số job song song: P (mặc định 2, mỗi job 4 luồng BLAS, đúng thiết lập của đợt 2).
cd ~/Evo_Engram && source venv/bin/activate
export OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
P=${P:-2}
SEEDS="20235956 1 2"
TAGS="bgebase e5large"
L=evo/r3_logs
mkdir -p $L
JL=$L/jobs.log
F="grep --line-buffered -v WARNING.clustering"

{ echo "=== ĐỢT 3 bắt đầu $(date '+%F %T')  P=$P"; nproc; free -g | head -2; } | tee $JL

# ---------- các file đợt trước mà đợt 3 import phải đúng bản đã kiểm
for pair in 02_probe_bridge.py:a9a0fbdd 03_probe_query_adapter.py:6d39e918 03b_probe_norm.py:ea80320d \
            04_probe_multiepoch.py:60aadb66; do
  f=${pair%%:*}; want=${pair##*:}
  got=$(sha256sum evo/$f 2>/dev/null | cut -c1-8)
  [ "$got" = "$want" ] || echo "CẢNH BÁO: evo/$f có sha $got, bản đã kiểm là $want" | tee -a $JL
done

# ---------- kiểm tra đầu vào cho tự kiểm
miss=0
for tag in $TAGS; do for s in $SEEDS; do
  for f in probeE_${tag}_s${s}.json probeF_${tag}_s${s}.json probeE_scifact_${tag}_s${s}.json probeF_scifact_${tag}_s${s}.json; do
    [ -f "$f" ] || { echo "THIẾU $f (tự kiểm sẽ bị bỏ qua)" | tee -a $JL; miss=1; }
  done
done; done
for tag in $TAGS; do
  [ -f data/scifact_${tag}_ground_truth.json ] || { echo "THIẾU data/scifact_${tag}_ground_truth.json, DỪNG"; exit 1; }
done

run_jobs() {   # $1: file lệnh, mỗi dòng "tên|lệnh"; chạy song song tối đa $P job
  while IFS='|' read -r name cmd; do
    [ -z "$name" ] && continue
    while [ "$(jobs -rp | wc -l)" -ge "$P" ]; do wait -n; done
    ( t0=$(date +%s); echo "BẮT ĐẦU $(date +%T) $name" >> $JL
      bash -o pipefail -c "$cmd" > $L/$name.log 2>&1; rc=$?
      echo "XONG    $(date +%T) $name  ($(( $(date +%s) - t0 ))s, mã thoát $rc)" >> $JL ) &
  done < "$1"
  wait
}

# ---------- pha A
A=$L/phaseA.txt; : > $A
for ds in code scifact; do for tag in $TAGS; do for s in $SEEDS; do
  echo "g_${ds}_${tag}_s${s}|python3 evo/04b_probe_multiepoch2.py --dataset $ds --tag $tag --seed $s 2>&1 | $F" >> $A
done; done; done
for tag in $TAGS; do
  echo "h_code_${tag}_s20235956_f0.1_ho0|python3 evo/03c_probe_holdout.py --tag $tag --seed 20235956 --frac 0.10 --holdout 0 2>&1 | $F" >> $A
  echo "h_scifact_${tag}_s20235956_f0.1_ho0|python3 evo/03c_probe_holdout.py --dataset scifact --tag $tag --seed 20235956 --frac 0.10 --holdout 0 2>&1 | $F" >> $A
  for s in $SEEDS; do
    for fr in 0.05 0.10 0.25; do
      echo "h_code_${tag}_s${s}_f${fr}_ho1|python3 evo/03c_probe_holdout.py --tag $tag --seed $s --frac $fr --holdout 1 2>&1 | $F" >> $A
    done
    for fr in 0.10 0.386; do
      echo "h_scifact_${tag}_s${s}_f${fr}_ho1|python3 evo/03c_probe_holdout.py --dataset scifact --tag $tag --seed $s --frac $fr --holdout 1 2>&1 | $F" >> $A
    done
  done
done
echo "pha A: $(wc -l < $A) job" | tee -a $JL
run_jobs $A

# ---------- pha B
B=$L/phaseB.txt; : > $B
for ds in code scifact; do for tag in $TAGS; do for s in $SEEDS; do
  echo "l_${ds}_${tag}_s${s}|python3 evo/06_probe_lazy.py --dataset $ds --tag $tag --seed $s 2>&1 | $F" >> $B
done; done; done
echo "pha B: $(wc -l < $B) job" | tee -a $JL
run_jobs $B

# ---------- tổng hợp
python3 evo/analyze_04b.py "probeG_bgebase_*.json" "probeG_e5large_*.json" > evo/r3_summary_04b_code.txt 2>&1
python3 evo/analyze_04b.py "probeG_scifact_*.json" > evo/r3_summary_04b_scifact.txt 2>&1
python3 evo/analyze_06.py "probeL_bgebase_*.json" "probeL_e5large_*.json" > evo/r3_summary_06_code.txt 2>&1
python3 evo/analyze_06.py "probeL_scifact_*.json" > evo/r3_summary_06_scifact.txt 2>&1
python3 evo/analyze_03.py "probeH_bgebase_*_ho1.json" "probeH_e5large_*_ho1.json" > evo/r3_summary_holdout_code.txt 2>&1
python3 evo/analyze_03.py "probeH_scifact_*_ho1.json" > evo/r3_summary_holdout_scifact.txt 2>&1
{
  for f in 04b_code 04b_scifact 06_code 06_scifact holdout_code holdout_scifact; do
    echo "################ r3_summary_$f"; cat evo/r3_summary_$f.txt; echo
  done
  echo "################ TỰ KIỂM (dòng >>> trong log)"
  grep -H ">>>" $L/*.log | sed "s#$L/##"
  echo "################ CẢNH BÁO"
  grep -H -i "Traceback\|Error\|LỆCH\|THẤP" $L/*.log | sed "s#$L/##" | head -50
  echo "################ MLP"
  grep -H "^MLP:" $L/h_*.log | sed "s#$L/##"
  echo "################ THỜI GIAN"
  cat $JL
} > evo/round3_all.txt
echo "XONG ĐỢT 3 $(date '+%F %T')" | tee -a $JL evo/round3_all.txt
