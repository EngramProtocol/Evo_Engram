#!/bin/bash
# Gate 3b: xác nhận gate 3 trên 3 seed x 2 cặp mô hình với lưới R mịn, rồi đo CPU phía client.
# Chạy: tmux new -s gate3b -d "bash ~/Evo_Engram/evo/run_gate3b.sh"
# Xem:  tail -n 5 ~/Evo_Engram/evo/gate3b_*.log
cd ~/Evo_Engram && source venv/bin/activate
for s in 20235956 1 2; do
  for tag in bgebase e5large; do
    python3 evo/03_probe_query_adapter.py --tag $tag --seed $s \
        --rerank 5,10,15,20,30,50,100 --out probeD_${tag}_s${s}_Rfine.json \
        2>&1 | grep --line-buffered -v "WARNING clustering" | tee evo/gate3b_${tag}_s${s}.log
  done
done
python3 evo/analyze_03.py "probeD_*_Rfine.json" 2>&1 | tee evo/gate3b_summary.txt
# đo CPU sau cùng, khi không còn gì chạy song song
python3 evo/05_bench_cpu.py --m1 BAAI/bge-base-en-v1.5 --tag bgebase 2>&1 | tee evo/gate3b_bench_bgebase.log
python3 evo/05_bench_cpu.py --m1 intfloat/e5-large-v2  --tag e5large 2>&1 | tee evo/gate3b_bench_e5large.log
echo "XONG GATE 3B" | tee -a evo/gate3b_summary.txt
