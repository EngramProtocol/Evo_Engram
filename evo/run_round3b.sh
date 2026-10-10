#!/bin/bash
# Đợt 3b: (1) lazy migration chạy lại với khoá E1 gốc (u), vì đợt 3 cho thấy khoá trừ trung bình làm recall
# của chỉ mục E1 sụt mạnh và kéo theo cả thí nghiệm lazy; (2) baseline MLP với lưới learning rate, vì ở
# đợt 3 MLP không lần nào hơn ridge với lr = 1e-3 nên chưa kết luận được.
# Không ghi đè kết quả đợt 3: file mới là probeL_*_ku.json và probeHM_*.json.
# Chạy:   tmux new -s round3b -d "bash ~/Evo_Engram/evo/run_round3b.sh"
cd ~/Evo_Engram && source venv/bin/activate
export OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
P=${P:-2}
SEEDS="20235956 1 2"
TAGS="bgebase e5large"
L=evo/r3b_logs
mkdir -p $L
JL=$L/jobs.log
F="grep --line-buffered -v WARNING.clustering"
echo "=== ĐỢT 3b bắt đầu $(date '+%F %T')  P=$P" | tee $JL

for pair in 02_probe_bridge.py:a9a0fbdd 03_probe_query_adapter.py:6d39e918 03b_probe_norm.py:ea80320d \
            04_probe_multiepoch.py:60aadb66 04b_probe_multiepoch2.py:d579493c me_common.py:cdf84f3e; do
  f=${pair%%:*}; want=${pair##*:}
  got=$(sha256sum evo/$f 2>/dev/null | cut -c1-8)
  [ "$got" = "$want" ] || echo "CẢNH BÁO: evo/$f có sha $got, bản đã kiểm là $want" | tee -a $JL
done

run_jobs() {
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
for ds in code scifact; do for tag in $TAGS; do for s in $SEEDS; do
  echo "l_${ds}_${tag}_s${s}|python3 evo/06_probe_lazy.py --dataset $ds --tag $tag --seed $s --e1-key u 2>&1 | $F" >> $J
done; done; done
for tag in $TAGS; do for s in $SEEDS; do
  for fr in 0.10 0.25; do
    echo "hm_code_${tag}_s${s}_f${fr}|python3 evo/03c_probe_holdout.py --tag $tag --seed $s --frac $fr --holdout 1 --mlp-lrs 3e-5,1e-4,3e-4,1e-3 --mlp-patience 20 --out probeHM_${tag}_s${s}_f${fr}.json 2>&1 | $F" >> $J
  done
  for fr in 0.10 0.386; do
    echo "hm_scifact_${tag}_s${s}_f${fr}|python3 evo/03c_probe_holdout.py --dataset scifact --tag $tag --seed $s --frac $fr --holdout 1 --mlp-lrs 3e-5,1e-4,3e-4,1e-3 --mlp-patience 20 --out probeHM_scifact_${tag}_s${s}_f${fr}.json 2>&1 | $F" >> $J
  done
done; done
echo "$(wc -l < $J) job" | tee -a $JL
run_jobs $J

python3 evo/analyze_06.py "probeL_bgebase_*_ku.json" "probeL_e5large_*_ku.json" > evo/r3b_summary_06_code.txt 2>&1
python3 evo/analyze_06.py "probeL_scifact_*_ku.json" > evo/r3b_summary_06_scifact.txt 2>&1
python3 evo/analyze_03.py "probeHM_bgebase_*.json" "probeHM_e5large_*.json" > evo/r3b_summary_mlp_code.txt 2>&1
python3 evo/analyze_03.py "probeHM_scifact_*.json" > evo/r3b_summary_mlp_scifact.txt 2>&1
{
  for f in 06_code 06_scifact mlp_code mlp_scifact; do
    echo "################ r3b_summary_$f"; cat evo/r3b_summary_$f.txt; echo
  done
  echo "################ TỰ KIỂM"
  grep -H ">>>" $L/*.log | sed "s#$L/##"
  echo "################ LỖI"
  grep -H "Traceback\|Error\|CẢNH BÁO" $L/*.log | sed "s#$L/##" | head -50
  echo "################ MLP"
  grep -H "^MLP" $L/hm_*.log | sed "s#$L/##"
  echo "################ THỜI GIAN"
  cat $JL
} > evo/round3b_all.txt
echo "XONG ĐỢT 3b $(date '+%F %T')" | tee -a $JL evo/round3b_all.txt
