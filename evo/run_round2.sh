#!/bin/bash
# Đợt 2: (1) probe 04 multi-epoch trên CodeSearchNet, (2) quét cỡ mẫu học adapter trên CodeSearchNet,
# (3) gate 3d và probe 04 trên SciFact, tự đợi tới khi bước nhúng SciFact (tmux embsf) xong.
# Không ghi đè kết quả các đợt trước.
# Chạy: tmux new -s round2 -d "bash ~/Evo_Engram/evo/run_round2.sh"
cd ~/Evo_Engram && source venv/bin/activate
export OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4   # chừa CPU cho bước nhúng chạy song song
SEEDS="20235956 1 2"
TAGS="bgebase e5large"
F="grep --line-buffered -v WARNING.clustering"

# (1) probe 04 trên CodeSearchNet; cần probeE_<tag>_s<seed>.json của gate 3d để tự kiểm ở f = 0
for s in $SEEDS; do for tag in $TAGS; do
  python3 evo/04_probe_multiepoch.py --tag $tag --seed $s 2>&1 | $F | tee evo/r2_p04_code_${tag}_s${s}.log
done; done
python3 evo/analyze_04.py "probeF_bgebase_*.json" "probeF_e5large_*.json" 2>&1 | tee evo/r2_summary_p04_code.txt

# (2) cỡ mẫu học adapter trên CodeSearchNet: 500, 1.000, 5.000 document (2.000 đã có ở gate 3d)
for fr in 0.025 0.05 0.25; do for s in $SEEDS; do for tag in $TAGS; do
  python3 evo/03b_probe_norm.py --tag $tag --seed $s --frac $fr --out probeE_${tag}_s${s}_f${fr}.json \
      2>&1 | $F | tee evo/r2_p03b_code_${tag}_s${s}_f${fr}.log
done; done; done
python3 evo/analyze_03.py "probeE_bgebase_*.json" "probeE_e5large_*.json" 2>&1 | tee evo/r2_summary_sample_code.txt

# (3) SciFact: đợi bước nhúng xong (hoặc tmux embsf đã dừng)
while { [ ! -f data/scifact_bgebase_ground_truth.json ] || [ ! -f data/scifact_e5large_ground_truth.json ]; } \
      && tmux has-session -t embsf 2>/dev/null; do sleep 60; done
for tag in $TAGS; do
  if [ ! -f data/scifact_${tag}_ground_truth.json ]; then
    echo "KHÔNG CÓ EMBEDDING SCIFACT CHO $tag, bỏ qua (xem evo/embed_scifact_${tag}.log)" | tee -a evo/r2_summary_scifact.txt
    continue
  fi
  for s in $SEEDS; do
    python3 evo/03b_probe_norm.py --dataset scifact --tag $tag --seed $s \
        2>&1 | $F | tee evo/r2_p03b_scifact_${tag}_s${s}.log
    python3 evo/03b_probe_norm.py --dataset scifact --tag $tag --seed $s --frac 0.386 \
        --out probeE_scifact_${tag}_s${s}_f0.386.json 2>&1 | $F | tee evo/r2_p03b_scifact_${tag}_s${s}_f0.386.log
    python3 evo/04_probe_multiepoch.py --dataset scifact --tag $tag --seed $s \
        2>&1 | $F | tee evo/r2_p04_scifact_${tag}_s${s}.log
  done
done
{ python3 evo/analyze_03.py "probeE_scifact_*.json"; echo; python3 evo/analyze_04.py "probeF_scifact_*.json"; } \
    2>&1 | tee -a evo/r2_summary_scifact.txt
echo "XONG DOT 2" | tee -a evo/r2_summary_scifact.txt
