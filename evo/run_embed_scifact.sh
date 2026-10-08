#!/bin/bash
# Nhúng SciFact (5.183 abstract, 500 claim) bằng hai mô hình M1, khoảng 1,5 đến 2,5 giờ CPU.
# Chạy: tmux new -s embsf -d "bash ~/Evo_Engram/evo/run_embed_scifact.sh"
cd ~/Evo_Engram && source venv/bin/activate
# bổ sung symlink tới dữ liệu SciFact gốc nếu data/ của Evo_Engram chưa có (không sửa gì repo cũ)
for f in ~/V_ENGRAM_SIMULATION/data/scifact_*; do
  [ -e "data/$(basename "$f")" ] || ln -s "$f" data/
done
python3 evo/01_embed_m1.py --dataset scifact --model BAAI/bge-base-en-v1.5 --tag bgebase --device cpu \
    2>&1 | tee evo/embed_scifact_bgebase.log
python3 evo/01_embed_m1.py --dataset scifact --model intfloat/e5-large-v2 --tag e5large --device cpu \
    2>&1 | tee evo/embed_scifact_e5large.log
echo "XONG NHUNG SCIFACT" | tee -a evo/embed_scifact_e5large.log
