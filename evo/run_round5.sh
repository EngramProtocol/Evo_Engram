#!/bin/bash
# Đợt 5: thăm dò sau góp ý của thầy (không thuộc đánh giá xác nhận; thuật toán giữ nguyên).
#   A  ADR không cần embedding M0 đầy đủ: học Wr, Wf và hiệu chỉnh PROB trên bản tái tạo PQ c_o của record E0
#      (--pair-src pq) ở 04b, 03c, 06; chấm lại H1 đến H4 bằng đúng hàm của analyze_prereg.py.
#      Cấu hình y hệt đợt 4: code100kfq x 3 cặp, arctic trên code 20k và SciFact, seed 3 4 5.
#   B  Recall đo thẳng từ lookup lặp thật trong SimPy (09_sim_e2e.py): trạng thái cố định f = 0, 0.1, 0.5, 0.9, 1
#      và dòng Zipf(1) 3.000 lượt vòng kín (static, lazy, bg). Code 20k bge-base (3 seed phát triển, như bảng chi
#      phí của bài) và code100kfq x 3 cặp x seed 3 4 5 (50.000 node).
# Yêu cầu: đã có kết quả đợt 4 ở thư mục gốc repo (probeG_, probeH_, probeL_, probeLR_ dùng để tự kiểm);
#          HEAD đúng tag evo-r5-v1.
# Chạy:    tmux new -s round5 -d "bash ~/Evo_Engram/evo/run_round5.sh"
# Không ghi đè kết quả đợt trước: file mới có hậu tố _pq hoặc tên probeE2E_.
# Chỉ chạy một phần: PHASES="A" hoặc PHASES="B" (mặc định "A B").
cd ${EVO_ROOT:-~/Evo_Engram} || exit 1
[ -f venv/bin/activate ] && source venv/bin/activate
export OPENBLAS_NUM_THREADS=${NT:-4} OMP_NUM_THREADS=${NT:-4} MKL_NUM_THREADS=${NT:-4}
P=${P:-2}                          # pha A: 04b/03c/06 dùng BLAS nhiều, 2 job x 4 luồng như đợt 4
PB=${PB:-4}                        # pha B: 09 chủ yếu là SimPy một luồng, 4 job x 1 luồng
PHASES=${PHASES:-"A B"}
CSEEDS=${CSEEDS:-"3 4 5"}
ESEEDS=${ESEEDS:-"20235956 1 2"}
N100=${N100:-50000}
X=${X:-}; XL=${XL:-}; XB=${XB:-} # tham số thêm (X: mọi script, XL: 06, XB: 09), CHỈ dùng khi chạy thử trên dữ liệu giả
L=evo/r5_logs
mkdir -p $L
JL=$L/jobs.log
F="grep --line-buffered -v WARNING.clustering"
{ echo "=== ĐỢT 5 bắt đầu $(date '+%F %T')  P=$P  pha: $PHASES"; nproc; free -g | head -2; } | tee -a $JL

# ---------- 0. kiểm tra
git describe --tags --exact-match 2>/dev/null | grep -qx "evo-r5-v1" \
  && echo "HEAD = tag evo-r5-v1 ($(git rev-parse --short HEAD))" | tee -a $JL \
  || echo "CẢNH BÁO: HEAD chưa ở tag evo-r5-v1" | tee -a $JL
sha256sum -c evo/SHA256SUMS_round5 --quiet 2>&1 | tee -a $JL
[ "${PIPESTATUS[0]}" = "0" ] || { echo "FILE CỦA ĐỢT 5 BỊ SỬA SO VỚI SHA256SUMS_round5, DỪNG" | tee -a $JL; exit 1; }
miss=0
for t in bgebase e5large arctic; do for s in $CSEEDS; do
  for f in probeG_code100kfq_${t}_s${s}.json probeL_code100kfq_${t}_s${s}_ku.json; do
    [ -e $f ] || { echo "THIẾU $f (kết quả đợt 4, cần để tự kiểm)" | tee -a $JL; miss=1; }; done; done; done
for s in $ESEEDS; do
  [ -e probeG_bgebase_s${s}.json ] || { echo "THIẾU probeG_bgebase_s${s}.json (đợt 3, cần để tự kiểm 09)" | tee -a $JL; miss=1; }
done
[ -d src ] || { echo "THIẾU src/ của V-Engram" | tee -a $JL; miss=1; }
[ "$miss" = "0" ] || { echo "THIẾU FILE, DỪNG" | tee -a $JL; exit 1; }

# phiên bản model trong cache Hugging Face trên máy này (cho phần Data availability của bài)
{
  echo "# snapshot Hugging Face trong cache của node-dal-02, $(date '+%F')"
  for m in BAAI--bge-large-en-v1.5 BAAI--bge-base-en-v1.5 intfloat--e5-large-v2 \
           Snowflake--snowflake-arctic-embed-m-v1.5 Qwen--Qwen2.5-3B-Instruct; do
    d=${HF_HOME:-$HOME/.cache/huggingface}/hub/models--$m
    if [ -f $d/refs/main ]; then echo "${m/--//}  $(cat $d/refs/main)  (snapshots: $(ls $d/snapshots 2>/dev/null | tr '\n' ' '))"
    else echo "${m/--//}  KHÔNG THẤY TRONG CACHE ($d)"; fi
  done
} > evo/r5_model_revisions.txt
cat evo/r5_model_revisions.txt | tee -a $JL

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

if [[ " $PHASES " == *" A "* ]]; then
  # ---------- A1. 04b với cặp học PQ (06 cần file này để tự kiểm nên chạy trước)
  A=$L/phaseA1.txt; : > $A
  for t in bgebase e5large arctic; do for s in $CSEEDS; do
    echo "gq_code100kfq_${t}_s${s}|python3 evo/04b_probe_multiepoch2.py --pair-src pq --dataset code100kfq --tag $t --seed $s --nodes $N100 --frac 0.02 --fmig 0,0.02,0.1,0.2,0.5,0.9,1.0 $X 2>&1 | $F" >> $A
  done; done
  for s in $CSEEDS; do
    echo "gq_code_arctic_s${s}|python3 evo/04b_probe_multiepoch2.py --pair-src pq --tag arctic --seed $s $X 2>&1 | $F" >> $A
    echo "gq_scifact_arctic_s${s}|python3 evo/04b_probe_multiepoch2.py --pair-src pq --dataset scifact --tag arctic --seed $s $X 2>&1 | $F" >> $A
  done
  echo "pha A1: $(wc -l < $A) job" | tee -a $JL
  run_jobs $A
  # ---------- A2. 03c holdout ở cỡ mẫu chính của H1 (không MLP) và 06 lazy, cặp học PQ
  A=$L/phaseA2.txt; : > $A
  for t in bgebase e5large arctic; do for s in $CSEEDS; do
    echo "hq_code100kfq_${t}_s${s}_f0.05|python3 evo/03c_probe_holdout.py --pair-src pq --mlp 0 --holdout 1 --dataset code100kfq --tag $t --seed $s --nodes $N100 --frac 0.05 $X 2>&1 | $F" >> $A
  done; done
  for s in $CSEEDS; do
    echo "hq_code_arctic_s${s}_f0.25|python3 evo/03c_probe_holdout.py --pair-src pq --mlp 0 --holdout 1 --tag arctic --seed $s --frac 0.25 $X 2>&1 | $F" >> $A
    echo "hq_scifact_arctic_s${s}_f0.386|python3 evo/03c_probe_holdout.py --pair-src pq --mlp 0 --holdout 1 --dataset scifact --tag arctic --seed $s --frac 0.386 $X 2>&1 | $F" >> $A
  done
  for t in bgebase e5large arctic; do for s in $CSEEDS; do
    echo "lq_code100kfq_${t}_s${s}|python3 evo/06_probe_lazy.py --pair-src pq --dataset code100kfq --tag $t --seed $s --nodes $N100 --frac 0.02 --check-3b none $X $XL 2>&1 | $F" >> $A
  done; done
  for s in $CSEEDS; do
    echo "lq_code_arctic_s${s}|python3 evo/06_probe_lazy.py --pair-src pq --tag arctic --seed $s --check-3b none $X $XL 2>&1 | $F" >> $A
    echo "lq_scifact_arctic_s${s}|python3 evo/06_probe_lazy.py --pair-src pq --dataset scifact --tag arctic --seed $s --check-3b none $X $XL 2>&1 | $F" >> $A
  done
  echo "pha A2: $(wc -l < $A) job" | tee -a $JL
  run_jobs $A
fi

if [[ " $PHASES " == *" B "* ]]; then
  # ---------- B. recall từ lookup thật (09). Job 100k chạy trước vì lâu nhất.
  B=$L/phaseB.txt; : > $B
  for t in bgebase e5large arctic; do for s in $CSEEDS; do
    echo "e_code100kfq_${t}_s${s}|python3 evo/09_sim_e2e.py --dataset code100kfq --tag $t --seed $s --nodes $N100 --frac 0.02 $X $XB 2>&1 | $F" >> $B
  done; done
  for s in $ESEEDS; do
    echo "e_code_bgebase_s${s}|python3 evo/09_sim_e2e.py --tag bgebase --seed $s $X $XB 2>&1 | $F" >> $B
  done
  echo "pha B: $(wc -l < $B) job, P=$PB" | tee -a $JL
  ( export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1; P=$PB; run_jobs $B )
fi

# ---------- tổng hợp
python3 evo/analyze_r5.py > evo/r5_summary.txt 2>&1
{
  cat evo/r5_summary.txt
  echo; echo "################ PHIÊN BẢN MODEL"; cat evo/r5_model_revisions.txt
  echo "################ TỰ KIỂM (dòng >>> trong log)"
  grep -H ">>>" $L/*.log | sed "s#$L/##"
  echo "################ LỖI"
  grep -H "Traceback\|Error\|LỆCH\|DỪNG\|\*\*\*" $L/*.log | sed "s#$L/##" | head -60
  echo "################ THỜI GIAN"
  cat $JL
} > evo/round5_all.txt
echo "XONG ĐỢT 5 $(date '+%F %T')" | tee -a $JL evo/round5_all.txt
