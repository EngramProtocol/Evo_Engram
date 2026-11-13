#!/bin/bash
# Đợt 14: C3 trên khoá SRP gốc, xác nhận drain trên seed mới, drain trên dòng cho mọi model, và ba phép đo thăm dò
# (evo/PREREG_round14.md, tag evo-r14-prereg). Không sửa bộ mô phỏng: 11_probe_safe.py và 10_probe_placement.py như đợt 13.
#   R  Kiểm hồi quy bằng rerun_prev.py trên một file dòng 3.000 lượt của đợt 13 (code 100k, bge-base, seed 26, có drain):
#      10 run phải trùng từng số.
#   U  C3 trên khoá SRP gốc (--e1-place u, không cap): code 100k, bge-base và e5-large, seed 26..35, Zipf 1, dòng 3.000
#      lượt; static, lazy, lazy+delay, k1, lazy+keep, full, drain.                                              (H24)
#   C  Migrate tới khi xong trên seed mới 46..55, đúng cấu hình đợt 11 (gỡ E0 khi xong): code 20k (T = 1.500, 3.000) và
#      SciFact (T = 400, 800), 5 model; static, lazy, full, bg, lazy+bg, rebuild, k1, drain.                     (H22)
#   D  Drain trên dòng 3.000 lượt của code 100k với placement học cho e5-large, Arctic, MiniLM, seed 26..35, cùng các
#      chính sách của pha D đợt 13. Mỗi job tự so các run trùng tên với file đợt 11 cùng seed (--check-prev).   (H23)
#   F  Churn và lỗi peer như đợt 11, thêm lazy+keep và drain: code 100k, 3 model, seed 26..28; tự so với file churn của
#      đợt 11.                                                                                                (thăm dò)
#   B  Full ở T = 16 probe (cùng số peer với hai epoch) trên dòng của Bảng 10: bge-base, seed 26..35.         (thăm dò)
#   O  Độ nhạy theo số object mỗi peer: placement của code 100k trên 5.000 peer, 5 không gian, seed 26..28.   (thăm dò)
#   S  analyze_r14.py, rồi ghép evo/round14_all.txt.
# Thứ tự chạy: R và U; rồi C; D; F; B; O. Pha quan trọng chạy trước, nên có thể dừng sớm mà vẫn có H24 và H22.
# Yêu cầu: kết quả các đợt trước ở thư mục gốc repo: probeV13_code100kfq_bgebase_s{26..35}_cap16.json (R, H24, B),
#          probeV11_code100kfq_{e5large,arctic,minilm}_s{26..35}_cap16.json (D), probeV11C_code100kfq_*_s{26..28}_cap16.json
#          (F), probeP11_code100kfq_*_s{26..28}.json (D, B, F, O), probeQ13_A11_code100kfq_*.json (O); HEAD đúng tag
#          evo-r14-prereg. Thiếu file cũ thì job vẫn chạy nhưng không tự so, và analyze ghi rõ.
# Chạy:    tmux new -s round14 -d "bash ~/Evo_Engram/evo/run_round14.sh"
# Chỉ chạy một phần: PHASES="R U C" (mặc định "R U C D F B O"); PHASES=S chỉ chạy lại analyze và ghép evo/round14_all.txt.
# Chạy tiếp sau khi bị ngắt: SKIP_DONE=1 bỏ qua job đã có file kết quả đọc được.
# Xem kết quả tạm khi đang chạy: python3 evo/analyze_r14.py (chỉ đọc). Không gọi run_round14.sh lần thứ hai khi lần đầu
# chưa xong; script tự dừng nếu thấy lần chạy khác còn sống (evo/r14_logs/run.pid).
# File ra mới, không ghi đè file của đợt trước: probeVR14_* (R), probeV14U_* (U), probeV14F_* (C), probeV14_* (D),
# probeV14C_* (F), probeV14B_* (B), probeP14_* (O). Mọi dòng lệnh job của mọi lần chạy được ghi nối vào
# evo/r14_logs/all_jobs.txt (dùng khi cần chạy lại một job).
cd ${EVO_ROOT:-~/Evo_Engram} || exit 1
[ -f venv/bin/activate ] && source venv/bin/activate
NCPU=$(env -u OMP_NUM_THREADS -u OMP_THREAD_LIMIT nproc)          # đếm lõi trước khi đặt OMP_NUM_THREADS
export OPENBLAS_NUM_THREADS=${NT:-1} OMP_NUM_THREADS=${NT:-1} MKL_NUM_THREADS=${NT:-1}
inlist() { [[ " $2 " == *" $1 "* ]]; }
P=${P:-4}
PHASES=${PHASES:-"R U C D F B O"}
SKIP_DONE=${SKIP_DONE:-0}
SEEDS_U=${SEEDS_U:-"26 27 28 29 30 31 32 33 34 35"}
SEEDS_C=${SEEDS_C:-"46 47 48 49 50 51 52 53 54 55"}
SEEDS_D=${SEEDS_D:-"26 27 28 29 30 31 32 33 34 35"}
SEEDS_F=${SEEDS_F:-"26 27 28"}
SEEDS_B=${SEEDS_B:-"26 27 28 29 30 31 32 33 34 35"}
SEEDS_O=${SEEDS_O:-"26 27 28"}
UTAGS=${UTAGS:-"bgebase e5large"}                       # model đích trên code 100k mà quy tắc H19 chọn SRP
CTAGS=${CTAGS:-"bgebase e5large arctic gtebase minilm"}
DTAGS=${DTAGS:-"e5large arctic minilm"}                 # bge-base đã có ở đợt 13
FTAGS=${FTAGS:-"bgebase e5large arctic"}
BTAGS=${BTAGS:-"bgebase"}
OSPACES=${OSPACES:-"bgebase e5large arctic m0 minilm"}
ONODES=${ONODES:-5000}
BPROBES=${BPROBES:-16}
N100=${N100:-50000}; NSMALL=${NSMALL:-10000}
FR100=${FR100:-0.02}; FRSMALL=${FRSMALL:-0.1}
ST_CODE=${ST_CODE:-3000}; ST_SCI=${ST_SCI:-800}
FIN_CODE=${FIN_CODE:-"1500,3000"}; FIN_SCI=${FIN_SCI:-"400,800"}
CP_CODE=${CP_CODE:-"0,150,300,600,900,1200,1500,2000,2500,3000"}; CP_SCI=${CP_SCI:-"0,50,100,200,300,400,500,600,700,800"}
W_CODE=${W_CODE:-150}; W_SCI=${W_SCI:-50}
CSETS=${CSETS:-"ch:churn_min=720,median_session=120,repair_every=60;fail:fail_at=1500,fail_frac=0.3"}
export SEEDS_U SEEDS_C SEEDS_D SEEDS_F SEEDS_B SEEDS_O UTAGS CTAGS DTAGS FTAGS BTAGS OSPACES ONODES BPROBES
#        (analyze_r14.py đọc cùng các danh sách này)
R_F=${R_F:-probeV13_code100kfq_bgebase_s26_cap16.json}
X=${X:-}; XB=${XB:-}; XP=${XP:-}             # tham số thêm, CHỈ dùng khi chạy thử trên dữ liệu giả
POLU="static,lazy,lazyV,lazyVbgD,lazyD,full,lazyVbgDinf"                 # drain ghép ngân sách với lazy và lazyD
POLC="static,lazy,full,bg,lazybg,rebuild,lazyVbgD,lazyVbgDinf"
POLD="static,lazy,lazyV,lazyV_adp,lazyVbg,lazyVbgD,lazyVbgD_adp,lazyD,full,lazyVbgDinf"   # như pha D của đợt 13
POLF="static,lazy,lazyV,lazyVbgD,lazyD,lazyVbgDinf,full"
VARSO="srp,srp+cap16,srp_c+cap16,itq_q,itq_q+cap16"
L=evo/r14_logs
mkdir -p $L
JL=$L/jobs.log
F="grep --line-buffered -v WARNING.clustering"
# chỉ một lần chạy tại một thời điểm: lần chạy thứ hai sẽ ghi đè danh sách job mà lần đầu đang đọc
LOCK=$L/run.pid
if [ -s $LOCK ] && kill -0 "$(cat $LOCK)" 2>/dev/null; then
  echo "ĐANG CÓ MỘT LẦN CHẠY run_round14.sh KHÁC (pid $(cat $LOCK)), DỪNG. Xem kết quả tạm: python3 evo/analyze_r14.py" | tee -a $JL
  exit 1
fi
echo $$ > $LOCK
trap 'rm -f $LOCK' EXIT
{ echo "=== ĐỢT 14 bắt đầu $(date '+%F %T')  NCPU=$NCPU  P=$P  pha: $PHASES  SKIP_DONE=$SKIP_DONE"; free -g | head -2;
  python3 -c "import numpy; print('numpy', numpy.__version__)"; } | tee -a $JL

# ---------- 0. kiểm tra
git describe --tags --exact-match 2>/dev/null | grep -qx "evo-r14-prereg" \
  && echo "HEAD = tag evo-r14-prereg ($(git rev-parse --short HEAD))" | tee -a $JL \
  || echo "CẢNH BÁO: HEAD chưa ở tag evo-r14-prereg" | tee -a $JL
sha256sum -c evo/SHA256SUMS_round14 --quiet 2>&1 | tee -a $JL
[ "${PIPESTATUS[0]}" = "0" ] || { echo "FILE CỦA ĐỢT 14 BỊ SỬA SO VỚI SHA256SUMS_round14, DỪNG" | tee -a $JL; exit 1; }
have() {   # $1 dataset, $2 tag (m0 = không gian M0): đủ dữ liệu cho 10 và 11
  for f in data/$1_corpus_embeddings.npy data/$1_query_embeddings.npy data/$1_ground_truth.json \
           data/$1_pq_codebook_m512.npy data/$1_pq_codes_m512.npy; do [ -e $f ] || return 1; done
  [ "$2" = "m0" ] && return 0
  for f in data/$1_$2_corpus_embeddings.npy data/$1_$2_query_embeddings.npy data/$1_$2_ground_truth.json; do
    [ -e $f ] || return 1; done
}
nodes_of() { [ "$1" = "code100kfq" ] && echo "--nodes $N100 --frac $FR100" || echo "--nodes $NSMALL --frac $FRSMALL"; }
c10_of() {   # $1 tag, $2 seed: file placement của đợt 11 trên code 100k để 11 tự kiểm, hoặc none
  [ -e probeP11_code100kfq_$1_s$2.json ] && echo "probeP11_code100kfq_$1_s$2.json" || echo none
}
prev_of() {  # $1 file kết quả cũ cùng seed, $2 tên job: có thì trả tên file, không thì cảnh báo và trả none
  if [ -e "$1" ]; then echo "$1"; else echo "THIẾU $1: job $2 chạy không tự so" | tee -a $JL >&2; echo none; fi
}
NSKIP=0
add() {      # $1 file lệnh, $2 tên job, $3 file ra, $4 lệnh: ghi "tên|lệnh"; SKIP_DONE=1 thì bỏ job đã có file ra đọc được
  if [ "$SKIP_DONE" = "1" ] && [ -s "$3" ] && python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$3" 2>/dev/null; then
    NSKIP=$((NSKIP + 1)); return 0
  fi
  echo "$2|$4 2>&1 | $F" >> $1
}

run_jobs() {   # $1: file lệnh, mỗi dòng "tên|lệnh"; $2: số job song song (mặc định P)
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
VU="python3 evo/11_probe_safe.py --confirms 1 --e1-place u"
N1="$(nodes_of code100kfq)"

J1=$L/jobs1.txt; : > $J1          # R, U
J2=$L/jobs2.txt; : > $J2          # C
J3=$L/jobs3.txt; : > $J3          # D
J4=$L/jobs4.txt; : > $J4          # F
J5=$L/jobs5.txt; : > $J5          # B
J6=$L/jobs6.txt; : > $J6          # O
if inlist R "$PHASES"; then
  if [ -e $R_F ]; then
    o=probeVR14_code100kfq_bgebase_s26.json
    add $J1 r14_rep $o "python3 evo/rerun_prev.py $R_F evo/11_probe_safe.py $o"
  else
    echo "bỏ qua R: thiếu $R_F (đợt 13)" | tee -a $JL
  fi
fi
if inlist U "$PHASES"; then
  for t in $UTAGS; do
    if ! have code100kfq $t; then echo "bỏ qua U: thiếu dữ liệu code100kfq $t" | tee -a $JL; continue; fi
    for s in $SEEDS_U; do
      [ -e probeV13_code100kfq_${t}_s${s}_cap16.json ] || inlist $t "$DTAGS" \
        || echo "THIẾU probeV13_code100kfq_${t}_s${s}_cap16.json (đợt 13): H24d đến H24f của $t thiếu seed $s" | tee -a $JL
      o=probeV14U_code100kfq_${t}_s$s.json
      add $J1 u14_${t}_s$s $o "$VU --dataset code100kfq $N1 --tag $t --seed $s --policies $POLU --zipf 1.0 --check-06 none --check-10 none --out $o $X $XB"
    done
  done
fi
if inlist C "$PHASES"; then
  for ds in code scifact; do
    if [ "$ds" = "code" ]; then st=$ST_CODE; fin=$FIN_CODE; cp=$CP_CODE; win=$W_CODE; else st=$ST_SCI; fin=$FIN_SCI; cp=$CP_SCI; win=$W_SCI; fi
    for t in $CTAGS; do
      if ! have $ds $t; then echo "bỏ qua C: thiếu dữ liệu $ds $t" | tee -a $JL; continue; fi
      for s in $SEEDS_C; do
        o=probeV14F_${ds}_${t}_s${s}_cap16.json
        add $J2 f14_${ds}_${t}_s$s $o "$V11 --dataset $ds $(nodes_of $ds) --tag $t --seed $s --policies $POLC --zipf 1.0 --stream $st --bg-finish $fin --checkpoints $cp --window $win --check-10 none --out $o $X"
      done
    done
  done
fi
if inlist D "$PHASES"; then
  for t in $DTAGS; do
    if ! have code100kfq $t; then echo "bỏ qua D: thiếu dữ liệu code100kfq $t" | tee -a $JL; continue; fi
    for s in $SEEDS_D; do
      prev=$(prev_of probeV11_code100kfq_${t}_s${s}_cap16.json d14_${t}_s$s)
      o=probeV14_code100kfq_${t}_s${s}_cap16.json
      add $J3 d14_${t}_s$s $o "$V11 --dataset code100kfq $N1 --tag $t --seed $s --policies $POLD --zipf 1.0 --check-10 $(c10_of $t $s) --check-prev $prev --out $o $X $XB"
    done
  done
fi
if inlist F "$PHASES"; then
  for t in $FTAGS; do
    if ! have code100kfq $t; then echo "bỏ qua F: thiếu dữ liệu code100kfq $t" | tee -a $JL; continue; fi
    for s in $SEEDS_F; do
      prev=$(prev_of probeV11C_code100kfq_${t}_s${s}_cap16.json c14_${t}_s$s)
      o=probeV14C_code100kfq_${t}_s${s}_cap16.json
      add $J4 c14_${t}_s$s $o "$V11 --dataset code100kfq $N1 --tag $t --seed $s --policies static --zipf 1.0 --churn-sets '$CSETS' --churn-policies $POLF --churn-zipf 1.0 --check-10 $(c10_of $t $s) --check-prev $prev --out $o $X $XB"
    done
  done
fi
if inlist B "$PHASES"; then
  for t in $BTAGS; do
    if ! have code100kfq $t; then echo "bỏ qua B: thiếu dữ liệu code100kfq $t" | tee -a $JL; continue; fi
    for s in $SEEDS_B; do
      o=probeV14B_code100kfq_${t}_s${s}_cap16_T$BPROBES.json
      add $J5 b14_${t}_s$s $o "$V11 --dataset code100kfq $N1 --tag $t --seed $s --policies full --zipf 1.0 --probes $BPROBES --check-10 $(c10_of $t $s) --out $o $X $XB"
    done
  done
fi
if inlist O "$PHASES"; then
  for sp in $OSPACES; do
    if ! have code100kfq $sp; then echo "bỏ qua O: thiếu dữ liệu code100kfq $sp" | tee -a $JL; continue; fi
    spo=""; [ "$sp" = "m0" ] && spo="--space m0"
    for s in $SEEDS_O; do
      o=probeP14_code100kfq_${sp}_s${s}_n$ONODES.json
      add $J6 o14_${sp}_s$s $o "$PP --dataset code100kfq --tag $sp $spo --seed $s --nodes $ONODES --frac $FR100 --variants $VARSO --out $o $XP"
    done
  done
fi
echo "đợt 14: $(wc -l < $J1) job ở R, U; $(wc -l < $J2) ở C; $(wc -l < $J3) ở D; $(wc -l < $J4) ở F; $(wc -l < $J5) ở B; $(wc -l < $J6) ở O; bỏ qua $NSKIP job đã có file. P=$P" | tee -a $JL
cat $J1 $J2 $J3 $J4 $J5 $J6 >> $L/all_jobs.txt
for pair in "$J1:R, U" "$J2:C" "$J3:D" "$J4:F" "$J5:B" "$J6:O"; do
  jf=${pair%%:*}
  [ -s $jf ] || continue
  run_jobs $jf
  echo "--- xong ${pair#*:} $(date '+%F %T')" | tee -a $JL
done

# ---------- tổng hợp
python3 evo/analyze_r14.py > $L/r14_summary.txt 2>&1
{
  cat $L/r14_summary.txt
  echo "################ TỰ KIỂM (dòng >>> và lệch trong log)"
  grep -H ">>>\|    lệch:\|CẢNH BÁO" $L/*.log | sed "s#$L/##" | grep -v "bỏ qua"
  echo "################ LỖI"
  grep -H "Traceback\|Error\|LỆCH\|DỪNG\|THIẾU\|\*\*\*" $L/*.log | sed "s#$L/##" | head -60
  echo "################ THỜI GIAN"
  cat $JL
} > evo/round14_all.txt
echo "XONG ĐỢT 14 $(date '+%F %T')" | tee -a $JL evo/round14_all.txt
