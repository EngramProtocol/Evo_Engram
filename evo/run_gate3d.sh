#!/bin/bash
# Gate 3d: nhánh A_split_norm (định tuyến bằng ridge chiều ngược, xếp hạng bằng ridge chiều xuôi
# chia n_i theo từng record) trên 3 seed x 2 cặp. Cần các file probeD_*_g3c.json của gate 3c
# trong ~/Evo_Engram để tự kiểm. Không ghi đè kết quả 3b, 3c.
# Chạy: tmux new -s gate3d -d "bash ~/Evo_Engram/evo/run_gate3d.sh"
cd ~/Evo_Engram && source venv/bin/activate
for s in 20235956 1 2; do
  for tag in bgebase e5large; do
    python3 evo/03b_probe_norm.py --tag $tag --seed $s --out probeE_${tag}_s${s}.json \
        2>&1 | grep --line-buffered -v "WARNING clustering" | tee evo/gate3d_${tag}_s${s}.log
  done
done
python3 evo/analyze_03.py "probeE_*.json" 2>&1 | tee evo/gate3d_summary.txt
echo "XONG GATE 3D" | tee -a evo/gate3d_summary.txt
