#!/bin/bash
# Toàn bộ đợt 4 trên server trong một lệnh, không cần Colab:
#   [1/3] nhúng bằng CPU (prepare/04_evo_colab_embed.py): khôi phục docstring + 500 query mới, query, paraphrase
#         bằng Qwen2.5-3B, nhúng paraphrase, rồi corpus code100k (bge-base, arctic, e5-large) và SciFact arctic
#   [2/3] lắp dữ liệu vào data/ (evo/07_assemble_data.py), dừng nếu đối chiếu không đạt
#   [3/3] đợt 4 (evo/run_round4.sh)
# Chạy lại được bất cứ lúc nào: phần nhúng đã xong (theo khối 2.000 dòng) được bỏ qua.
# Chạy:   tmux new -s r4all -d "bash ~/Evo_Engram/evo/run_round4_all.sh"
cd ${EVO_ROOT:-~/Evo_Engram} || exit 1
[ -f venv/bin/activate ] && source venv/bin/activate
export OPENBLAS_NUM_THREADS=${NT:-4} OMP_NUM_THREADS=${NT:-4} MKL_NUM_THREADS=${NT:-4}
VD=${VD:-$HOME/V_ENGRAM_SIMULATION/data}
OUT=${OUT:-$HOME/evo_out}
PL=evo/r4_pipeline.log
mkdir -p evo
echo "=== ĐỢT 4 TOÀN BỘ bắt đầu $(date '+%F %T')" | tee -a $PL
{ nproc; free -g | head -2; df -h ~ | tail -1; } | tee -a $PL
for f in code100k_corpus_texts.json code100k_ground_truth.json scifact_corpus_texts.json scifact_ground_truth.json; do
  [ -e "$VD/$f" ] || { echo "THIẾU $VD/$f, DỪNG" | tee -a $PL; exit 1; }
done
if [ -z "$EMBED_ARGS" ]; then
  python3 -c "import pandas, pyarrow" 2>/dev/null || pip install -q pandas pyarrow 2>&1 | tail -2 | tee -a $PL
  python3 -c "import torch, transformers, sentence_transformers as st; print('torch', torch.__version__, '| transformers', transformers.__version__, '| sentence-transformers', st.__version__, '| luồng', torch.get_num_threads())" 2>&1 | tee -a $PL
fi

echo "=== [1/3] nhúng  $(date '+%F %T')  (tiến độ: tail -3 $OUT/log_colab.txt)" | tee -a $PL
python3 prepare/04_evo_colab_embed.py --in "$VD" --out "$OUT" --batch 32 --llm-batch 8 $EMBED_ARGS >> evo/r4_embed.log 2>&1
if ! tail -1 "$OUT/log_colab.txt" 2>/dev/null | grep -q "XONG TOÀN BỘ"; then
  echo "*** NHÚNG CHƯA XONG hoặc lỗi, xem evo/r4_embed.log; sửa xong chạy lại đúng lệnh này" | tee -a $PL; exit 1
fi
grep "KHỚP TOÀN BỘ\|đủ 5" "$OUT/log_colab.txt" | tee -a $PL

echo "=== [2/3] lắp dữ liệu  $(date '+%F %T')" | tee -a $PL
python3 evo/07_assemble_data.py --colab "$OUT" --vengram-data "$VD" $ASM_ARGS > evo/assemble_round4.log 2>&1
rc=$?
grep "kiểm \|DỪNG\|CẢNH BÁO\|góc query\|XONG" evo/assemble_round4.log | tee -a $PL
[ "$rc" = "0" ] || { echo "*** LẮP DỮ LIỆU KHÔNG ĐẠT (mã $rc), xem evo/assemble_round4.log. DỪNG" | tee -a $PL; exit 1; }

[ -n "$SKIP_R4" ] && { echo "(bỏ qua đợt 4 theo SKIP_R4)" | tee -a $PL; exit 0; }
echo "=== [3/3] đợt 4  $(date '+%F %T')  (tiến độ: grep -c ^XONG evo/r4_logs/jobs.log, tổng 92)" | tee -a $PL
bash evo/run_round4.sh
echo "=== ĐỢT 4 TOÀN BỘ xong $(date '+%F %T'); kết quả: evo/round4_all.txt" | tee -a $PL
