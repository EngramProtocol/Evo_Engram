#!/bin/bash
# Đợt 12: phép xác minh mạnh hơn cho C3, kiểm trước quy tắc chọn placement theo qf, C1 và C2 trên năm model mới
# (evo/PREREG_round12.md, tag evo-r12-prereg).
#   R  Kiểm hồi quy bằng rerun_prev.py trên 2 file đợt 11 (seed 26): migrate tới khi xong code 20k bge-base, có xen ba
#      chính sách mới; C3 bge-base trên code100kfq. Các run của đợt 11 phải trùng từng số.
#   A  C1, C2 cho 6 không gian cũ trên code 20k và SciFact, seed 36..38: dị hướng (--aniso-only) và placement srp,
#      srp+cap16, srp_c+cap16, itq_q, itq_q+cap16.                                                  (H19d, H21c)
#   C  C3 với phép xác minh mạnh hơn: migrate tới khi xong, gỡ E0 đúng ở lượt T, code 20k (dòng 3.000, T = 1.500,
#      3.000) và SciFact (dòng 800, T = 400, 800), 5 model × seed 36..45, Zipf 1.                     (H18)
#   E  Nhúng 5 model mới trên code 20k và SciFact bằng 01_embed_m1.py, từng job một, mỗi job NTE luồng. Mặc định
#      (EPAR=1) chạy song song với R, A, C; EPAR=0 thì chạy sau C như đợt 11. Bỏ qua cặp đã có dữ liệu.
#   N  Như A cho 10 cặp mới, sau khi E xong.                                                         (H19, H20, H21)
# Yêu cầu: probeV11F_code_bgebase_s26_cap16.json, probeV11_code100kfq_bgebase_s26_cap16.json của đợt 11 ở thư mục gốc
#          repo; HEAD đúng tag evo-r12-prereg.
# Chạy:    tmux new -s round12 -d "bash ~/Evo_Engram/evo/run_round12.sh"
# Chỉ chạy một phần: PHASES="R A" (mặc định "R A C E N"); PHASES=S chỉ chạy lại analyze và ghép evo/round12_all.txt.
# File ra mới, không ghi đè file cũ: probeVR12*_ (R), probeA12_*, probeP12_* (A, N), probeV12F_* (C). Mọi dòng lệnh job của
# mọi lần chạy được ghi nối vào evo/r12_logs/all_jobs.txt (dùng khi cần chạy lại một job).
cd ${EVO_ROOT:-~/Evo_Engram} || exit 1
[ -f venv/bin/activate ] && source venv/bin/activate
# đợt 12, sửa lỗi của đợt 11: nproc đọc OMP_NUM_THREADS, nên phải đếm lõi trước khi đặt biến này (và bỏ nó khi đếm)
NCPU=$(env -u OMP_NUM_THREADS -u OMP_THREAD_LIMIT nproc)
export OPENBLAS_NUM_THREADS=${NT:-1} OMP_NUM_THREADS=${NT:-1} MKL_NUM_THREADS=${NT:-1}
inlist() { [[ " $2 " == *" $1 "* ]]; }
P=${P:-4}
PHASES=${PHASES:-"R A C E N"}
EPAR=${EPAR:-1}                             # 1: pha E chạy song song với R, A, C; 0: chạy sau C
# số luồng mỗi job nhúng: khi E chạy cùng các pha khác thì chừa P lõi cho P job đó, còn không thì dùng mọi lõi
if [ "$EPAR" = "1" ] && { inlist R "$PHASES" || inlist A "$PHASES" || inlist C "$PHASES"; }; then
  NTE=${NTE:-$(( NCPU > P ? NCPU - P : 1 ))}; EMODE="song song với R, A, C"
else
  NTE=${NTE:-$NCPU}; EMODE="không chạy cùng pha nào"
fi
SEEDS_A=${SEEDS_A:-"36 37 38"}
SEEDS_C=${SEEDS_C:-"36 37 38 39 40 41 42 43 44 45"}
SPACES=${SPACES:-"bgebase e5large arctic m0 minilm gtebase"}     # không gian cũ của pha A (12 cặp cũ)
CTAGS=${CTAGS:-"bgebase e5large arctic gtebase minilm"}          # model của pha C; 3 model đầu là H18
HTAGS=${HTAGS:-"bgebase e5large arctic"}
NEWTAGS=${NEWTAGS:-"arcticxs e5small bgesmall gtesmall mpnet"}   # thứ tự nhúng: nhanh trước
declare -A MODEL=([e5small]="intfloat/e5-small-v2" [gtesmall]="thenlper/gte-small" [bgesmall]="BAAI/bge-small-en-v1.5"
                  [mpnet]="sentence-transformers/all-mpnet-base-v2" [arcticxs]="Snowflake/snowflake-arctic-embed-xs")
NSMALL=${NSMALL:-10000}; FRSMALL=${FRSMALL:-0.1}
ST_CODE=${ST_CODE:-3000}; ST_SCI=${ST_SCI:-800}
FIN_CODE=${FIN_CODE:-"1500,3000"}; FIN_SCI=${FIN_SCI:-"400,800"}
CP_CODE=${CP_CODE:-"0,150,300,600,900,1200,1500,2000,2500,3000"}; CP_SCI=${CP_SCI:-"0,50,100,200,300,400,500,600,700,800"}
W_CODE=${W_CODE:-150}; W_SCI=${W_SCI:-50}
export SEEDS_A SEEDS_C SPACES CTAGS HTAGS NEWTAGS      # analyze_r12.py đọc cùng các danh sách này
R_F=${R_F:-probeV11F_code_bgebase_s26_cap16.json}
R_B=${R_B:-probeV11_code100kfq_bgebase_s26_cap16.json}
X=${X:-}; XP=${XP:-}; XE=${XE:-}            # tham số thêm, CHỈ dùng khi chạy thử trên dữ liệu giả
VARS12="srp,srp+cap16,srp_c+cap16,itq_q,itq_q+cap16"
POLC12="static,full,lazybg,lazyVbgD,lazyVbgDk2,lazyVbgDk3,lazyVbgDu2,lazyVbgDv2,lazyVbgDuv2,lazyVbgDuv3,lazyVbgDinf"
POLR12="static,lazy,full,bg,lazybg,rebuild,lazyVbg,lazyVbgD,lazyVbgD_adp,lazyVbgDu2,lazyVbgDk2,lazyVbgDuv2,lazyVbgDk3,lazyVbgDv2,lazyVbgDinf"
L=evo/r12_logs
mkdir -p $L
JL=$L/jobs.log
F="grep --line-buffered -v WARNING.clustering"
{ echo "=== ĐỢT 12 bắt đầu $(date '+%F %T')  NCPU=$NCPU  P=$P  NTE=$NTE  EPAR=$EPAR  pha: $PHASES"; free -g | head -2;
  python3 -c "import numpy; print('numpy', numpy.__version__)"; } | tee -a $JL

# ---------- 0. kiểm tra
git describe --tags --exact-match 2>/dev/null | grep -qx "evo-r12-prereg" \
  && echo "HEAD = tag evo-r12-prereg ($(git rev-parse --short HEAD))" | tee -a $JL \
  || echo "CẢNH BÁO: HEAD chưa ở tag evo-r12-prereg" | tee -a $JL
sha256sum -c evo/SHA256SUMS_round12 --quiet 2>&1 | tee -a $JL
[ "${PIPESTATUS[0]}" = "0" ] || { echo "FILE CỦA ĐỢT 12 BỊ SỬA SO VỚI SHA256SUMS_round12, DỪNG" | tee -a $JL; exit 1; }
if inlist R "$PHASES"; then
  miss=0
  for f in $R_F $R_B; do [ -e $f ] || { echo "THIẾU $f (kết quả đợt 11)" | tee -a $JL; miss=1; }; done
  [ "$miss" = "0" ] || { echo "THIẾU FILE, DỪNG" | tee -a $JL; exit 1; }
fi
have() {   # $1 dataset, $2 tag (m0 = không gian M0): đủ dữ liệu cho 10 và 11
  for f in data/$1_corpus_embeddings.npy data/$1_query_embeddings.npy data/$1_ground_truth.json \
           data/$1_pq_codebook_m512.npy data/$1_pq_codes_m512.npy; do [ -e $f ] || return 1; done
  [ "$2" = "m0" ] && return 0
  for f in data/$1_$2_corpus_embeddings.npy data/$1_$2_query_embeddings.npy data/$1_$2_ground_truth.json; do
    [ -e $f ] || return 1; done
}
nodes_of() { echo "--nodes $NSMALL --frac $FRSMALL"; }
c10_of() {   # $1 dataset, $2 tag, $3 seed: file placement của pha A để 11 tự kiểm, hoặc none
  inlist $3 "$SEEDS_A" && echo "probeP12_$1_$2_s$3.json" || echo none
}

run_jobs() {   # $1: file lệnh, mỗi dòng "tên|lệnh"; $2: số job song song (mặc định P). Chỉ đếm và chờ job của chính lần
               # gọi này, nên pha E chạy nền không chiếm chỗ của các pha khác.
  local par=${2:-$P} name cmd p pids=() live
  while IFS='|' read -r name cmd; do
    [ -z "$name" ] && continue
    while :; do
      live=()
      for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null && live+=("$p"); done
      pids=("${live[@]}")
      [ "${#pids[@]}" -lt "$par" ] && break
      sleep 2
    done
    ( t0=$(date +%s); echo "BẮT ĐẦU $(date +%T) $name" >> $JL
      bash -o pipefail -c "$cmd" > $L/$name.log 2>&1; rc=$?
      echo "XONG    $(date +%T) $name  ($(( $(date +%s) - t0 ))s, mã thoát $rc)" >> $JL ) &
    pids+=($!)
  done < "$1"
  for p in "${pids[@]}"; do wait "$p" 2>/dev/null; done
}

PP="python3 evo/10_probe_placement.py"
V11="python3 evo/11_probe_safe.py --confirms 1 --e1-place itq_q --e1-cap 16"

add_place() {   # $1 file lệnh, $2 dataset, $3 tag hoặc m0: dị hướng và placement cho mọi seed của pha A
  local sp=""; [ "$3" = "m0" ] && sp="--space m0"
  for s in $SEEDS_A; do
    echo "a12_$2_$3_s$s|$PP --dataset $2 --tag $3 $sp --seed $s $(nodes_of $2) --aniso-only 1 --out probeA12_$2_$3_s$s.json $XP 2>&1 | $F" >> $1
    echo "p12_$2_$3_s$s|$PP --dataset $2 --tag $3 $sp --seed $s $(nodes_of $2) --variants $VARS12 --out probeP12_$2_$3_s$s.json $XP 2>&1 | $F" >> $1
  done
}
add_fin() {     # $1 file lệnh, $2 dataset (code, scifact), $3 tag: C3, gỡ E0 đúng ở lượt T, mọi seed của pha C
  local st fin cp win
  if [ "$2" = "code" ]; then st=$ST_CODE; fin=$FIN_CODE; cp=$CP_CODE; win=$W_CODE; else st=$ST_SCI; fin=$FIN_SCI; cp=$CP_SCI; win=$W_SCI; fi
  for s in $SEEDS_C; do
    echo "f12_$2_$3_s$s|$V11 --dataset $2 $(nodes_of $2) --tag $3 --seed $s --policies $POLC12 --zipf 1.0 --stream $st --bg-finish $fin --finish-drop T --checkpoints $cp --window $win --check-10 $(c10_of $2 $3 $s) --out probeV12F_$2_$3_s${s}_cap16.json $X 2>&1 | $F" >> $1
  done
}

J1=$L/jobs1.txt; : > $J1          # R, A
J2=$L/jobs2.txt; : > $J2          # C
JE=$L/jobsE.txt; : > $JE          # E
J3=$L/jobs3.txt; : > $J3          # N
if inlist R "$PHASES"; then
  echo "r12_rep|python3 evo/rerun_prev.py $R_B evo/11_probe_safe.py probeVR12_code100kfq_bgebase_s26.json 2>&1 | $F" >> $J1
  echo "r12_repf|python3 evo/rerun_prev.py $R_F evo/11_probe_safe.py probeVR12F_code_bgebase_s26.json --set policies=$POLR12 2>&1 | $F" >> $J1
fi
if inlist A "$PHASES"; then
  for ds in code scifact; do for t in $SPACES; do
    if ! have $ds $t; then echo "bỏ qua A: thiếu dữ liệu $ds $t" | tee -a $JL; continue; fi
    add_place $J1 $ds $t
  done; done
fi
if inlist C "$PHASES"; then
  for ds in code scifact; do for t in $CTAGS; do
    if ! have $ds $t; then echo "bỏ qua C: thiếu dữ liệu $ds $t" | tee -a $JL; continue; fi
    add_fin $J2 $ds $t
  done; done
fi
if inlist E "$PHASES"; then
  for t in $NEWTAGS; do for ds in code scifact; do
    if have $ds $t; then echo "E: đã có dữ liệu $ds $t, không nhúng lại" | tee -a $JL; continue; fi
    echo "e12_${ds}_$t|env OMP_NUM_THREADS=$NTE MKL_NUM_THREADS=$NTE OPENBLAS_NUM_THREADS=$NTE python3 evo/01_embed_m1.py --dataset $ds --model ${MODEL[$t]} --tag $t --device cpu $XE 2>&1 | tr '\r' '\n'" >> $JE
  done; done
fi
echo "đợt 12: $(wc -l < $J1) job ở R, A; $(wc -l < $J2) job ở C; $(wc -l < $JE) job nhúng ở E ($EMODE, $NTE luồng); phần N lập sau E. P=$P" | tee -a $JL
cat $J1 $J2 $JE >> $L/all_jobs.txt
EPID=
if [ -s $JE ] && [ "$EPAR" = "1" ]; then
  ( run_jobs $JE 1; echo "--- xong E $(date '+%F %T')" | tee -a $JL ) &
  EPID=$!
fi
run_jobs $J1
echo "--- xong R, A $(date '+%F %T')" | tee -a $JL
run_jobs $J2
echo "--- xong C $(date '+%F %T')" | tee -a $JL
if [ -n "$EPID" ]; then
  echo "chờ pha E ..." | tee -a $JL
  wait $EPID
elif [ -s $JE ]; then
  run_jobs $JE 1
  echo "--- xong E $(date '+%F %T')" | tee -a $JL
fi
if inlist N "$PHASES"; then
  for t in $NEWTAGS; do for ds in code scifact; do
    if ! have $ds $t; then echo "bỏ qua N: thiếu dữ liệu $ds $t" | tee -a $JL; continue; fi
    add_place $J3 $ds $t
  done; done
  echo "phần N: $(wc -l < $J3) job dị hướng và placement" | tee -a $JL
  cat $J3 >> $L/all_jobs.txt
  run_jobs $J3
  echo "--- xong N $(date '+%F %T')" | tee -a $JL
fi

# ---------- tổng hợp
R12_LOGS=$L python3 evo/analyze_r12.py > $L/r12_summary.txt 2>&1
{
  cat $L/r12_summary.txt
  echo "################ TỰ KIỂM (dòng >>> và lệch trong log)"
  grep -H ">>>\|    lệch:\|CẢNH BÁO" $L/*.log | sed "s#$L/##" | grep -v "bỏ qua"
  echo "################ LỖI"
  grep -H "Traceback\|Error\|LỆCH\|DỪNG\|\*\*\*" $L/*.log | sed "s#$L/##" | head -60
  echo "################ THỜI GIAN"
  cat $JL
} > evo/round12_all.txt
echo "XONG ĐỢT 12 $(date '+%F %T')" | tee -a $JL evo/round12_all.txt
