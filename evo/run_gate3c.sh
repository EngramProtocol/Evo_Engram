#!/bin/bash
# Gate 3c: chạy 03 bản mới (3 nhánh mới, chọn trên validation, chẩn đoán xếp hạng,
# rerank theo top-kappa từng node) trên 3 seed x 2 cặp. Không ghi đè kết quả gate 3b.
# Chạy: tmux new -s gate3c -d "bash ~/Evo_Engram/evo/run_gate3c.sh"
cd ~/Evo_Engram && source venv/bin/activate
for s in 20235956 1 2; do
  for tag in bgebase e5large; do
    python3 evo/03_probe_query_adapter.py --tag $tag --seed $s \
        --rerank 5,10,15,20,30,50,100 --out probeD_${tag}_s${s}_g3c.json \
        2>&1 | grep --line-buffered -v "WARNING clustering" | tee evo/gate3c_${tag}_s${s}.log
  done
done
{ python3 evo/analyze_03.py "probeD_*_g3c.json"; echo; python3 evo/compare_runs.py; } 2>&1 \
    | tee evo/gate3c_summary.txt
echo "XONG GATE 3C" | tee -a evo/gate3c_summary.txt
