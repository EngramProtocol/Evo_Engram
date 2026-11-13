#!/bin/bash
# Đợt 15: C3 khi migrate tới khi xong trên khoá SRP gốc (evo/PREREG_round15.md, tag evo-r15-prereg). Không sửa bộ mô
# phỏng: 11_probe_safe.py như đợt 13 và 14. Cấu hình y như pha C của đợt 14, chỉ đổi cách đặt record E1 từ itq_q+cap16
# sang khoá SRP gốc (--e1-place u, không cap); cùng seed, nên cùng overlay, cùng mẫu S và cùng dòng truy vấn.
#   R  Kiểm hồi quy bằng rerun_prev.py trên một file migrate tới khi xong của đợt 14 (code 20k, bge-base, seed 46):
#      13 run phải trùng từng số.
#   V  Migrate tới khi xong trên khoá SRP gốc cho các model mà quy tắc H19 chọn SRP: bge-base, e5-large, gte-base; code
#      20k (T = 1.500, 3.000) và SciFact (T = 400, 800); seed 46..55; static, lazy, full, bg, lazy+bg, rebuild, k1,
#      drain.                                                                                                   (H25)
#   W  Như V cho Arctic và MiniLM, là hai model mà quy tắc chọn placement học.                              (thăm dò)
#   S  analyze_r15.py, rồi ghép evo/round15_all.txt.
# Thứ tự chạy: R và V; rồi W. Có thể dừng sau V mà vẫn có đủ H25.
# Yêu cầu: kết quả pha C của đợt 14 ở thư mục gốc repo: probeV14F_{code,scifact}_<tag>_s{46..55}_cap16.json (phía
#          placement học của H25c đến H25e, và pha R); HEAD đúng tag evo-r15-prereg. Thiếu file đợt 14 thì job vẫn chạy,
#          nhưng tiêu chí cần phía placement học của ô đó sẽ thiếu seed, và analyze ghi rõ.
# Chạy:    tmux new -s round15 -d "bash ~/Evo_Engram/evo/run_round15.sh"
# Chỉ chạy một phần: PHASES="R V" (mặc định "R V W"); PHASES=S chỉ chạy lại analyze và ghép evo/round15_all.txt.
# Chạy tiếp sau khi bị ngắt: SKIP_DONE=1 bỏ qua job đã có file kết quả đọc được.
# Xem kết quả tạm khi đang chạy: python3 evo/analyze_r15.py (chỉ đọc). Không gọi run_round15.sh lần thứ hai khi lần đầu
# chưa xong; script tự dừng nếu thấy lần chạy khác còn sống (evo/r15_logs/run.pid).
# File ra mới, không ghi đè file của đợt trước: probeVR15_* (R), probeV15U_* (V, W). Mọi dòng lệnh job của mọi lần chạy
# được ghi nối vào evo/r15_logs/all_jobs.txt (dùng khi cần chạy lại một job).
cd ${EVO_ROOT:-~/Evo_Engram} || exit 1
[ -f venv/bin/activate ] && source venv/bin/activate
NCPU=$(env -u OMP_NUM_THREADS -u OMP_THREAD_LIMIT nproc)          # đếm lõi trước khi đặt OMP_NUM_THREADS
export OPENBLAS_NUM_THREADS=${NT:-1} OMP_NUM_THREADS=${NT:-1} MKL_NUM_THREADS=${NT:-1}
inlist() { [[ " $2 " == *" $1 "* ]]; }
P=${P:-4}
PHASES=${PHASES:-"R V W"}
SKIP_DONE=${SKIP_DONE:-0}
SEEDS_V=${SEEDS_V:-"46 47 48 49 50 51 52 53 54 55"}
VTAGS=${VTAGS:-"bgebase e5large gtebase"}               # model đích mà quy tắc H19 chọn SRP trên code 20k và SciFact
WTAGS=${WTAGS:-"arctic minilm"}                         # model mà quy tắc chọn placement học (thăm dò)
HIQF=${HIQF:-"e5large gtebase"}                         # H25f: model có qf dự đoán trên 1e-2
NSMALL=${NSMALL:-10000}; FRSMALL=${FRSMALL:-0.1}
ST_CODE=${ST_CODE:-3000}; ST_SCI=${ST_SCI:-800}
FIN_CODE=${FIN_CODE:-"1500,3000"}; FIN_SCI=${FIN_SCI:-"400,800"}
CP_CODE=${CP_CODE:-"0,150,300,600,900,1200,1500,2000,2500,3000"}; CP_SCI=${CP_SCI:-"0,50,100,200,300,400,500,600,700,800"}
W_CODE=${W_CODE:-150}; W_SCI=${W_SCI:-50}
export SEEDS_V VTAGS WTAGS HIQF                         # analyze_r15.py đọc cùng các danh sách này
R_F=${R_F:-probeV14F_code_bgebase_s46_cap16.json}
X=${X:-}                                                # tham số thêm, CHỈ dùng khi chạy thử trên dữ liệu giả
POLC="static,lazy,full,bg,lazybg,rebuild,lazyVbgD,lazyVbgDinf"          # như pha C của đợt 14
L=evo/r15_logs
mkdir -p $L
JL=$L/jobs.log
F="grep --line-buffered -v WARNING.clustering"
# chỉ một lần chạy tại một thời điểm: lần chạy thứ hai sẽ ghi đè danh sách job mà lần đầu đang đọc
LOCK=$L/run.pid
if [ -s $LOCK ] && kill -0 "$(cat $LOCK)" 2>/dev/null; then
  echo "ĐANG CÓ MỘT LẦN CHẠY run_round15.sh KHÁC (pid $(cat $LOCK)), DỪNG. Xem kết quả tạm: python3 evo/analyze_r15.py" | tee -a $JL
  exit 1
fi
echo $$ > $LOCK
trap 'rm -f $LOCK' EXIT
{ echo "=== ĐỢT 15 bắt đầu $(date '+%F %T')  NCPU=$NCPU  P=$P  pha: $PHASES  SKIP_DONE=$SKIP_DONE"; free -g | head -2;
  python3 -c "import numpy; print('numpy', numpy.__version__)"; } | tee -a $JL

# ---------- 0. kiểm tra
git describe --tags --exact-match 2>/dev/null | grep -qx "evo-r15-prereg" \
  && echo "HEAD = tag evo-r15-prereg ($(git rev-parse --short HEAD))" | tee -a $JL \
  || echo "CẢNH BÁO: HEAD chưa ở tag evo-r15-prereg" | tee -a $JL
sha256sum -c evo/SHA256SUMS_round15 --quiet 2>&1 | tee -a $JL
[ "${PIPESTATUS[0]}" = "0" ] || { echo "FILE CỦA ĐỢT 15 BỊ SỬA SO VỚI SHA256SUMS_round15, DỪNG" | tee -a $JL; exit 1; }
have() {   # $1 dataset, $2 tag: đủ dữ liệu cho 11
  for f in data/$1_corpus_embeddings.npy data/$1_query_embeddings.npy data/$1_ground_truth.json \
           data/$1_pq_codebook_m512.npy data/$1_pq_codes_m512.npy \
           data/$1_$2_corpus_embeddings.npy data/$1_$2_query_embeddings.npy data/$1_$2_ground_truth.json; do
    [ -e $f ] || return 1; done
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

VU="python3 evo/11_probe_safe.py --confirms 1 --e1-place u"

srp_jobs() {   # $1 file lệnh, $2 tiền tố tên job, $3 danh sách model
  local ds t s st fin cp win o
  for ds in code scifact; do
    if [ "$ds" = "code" ]; then st=$ST_CODE; fin=$FIN_CODE; cp=$CP_CODE; win=$W_CODE; else st=$ST_SCI; fin=$FIN_SCI; cp=$CP_SCI; win=$W_SCI; fi
    for t in $3; do
      if ! have $ds $t; then echo "bỏ qua $2: thiếu dữ liệu $ds $t" | tee -a $JL; continue; fi
      for s in $SEEDS_V; do
        [ -e probeV14F_${ds}_${t}_s${s}_cap16.json ] \
          || echo "THIẾU probeV14F_${ds}_${t}_s${s}_cap16.json (đợt 14): phía placement học của ô $ds $t thiếu seed $s" | tee -a $JL
        o=probeV15U_${ds}_${t}_s$s.json
        add $1 ${2}15_${ds}_${t}_s$s $o "$VU --dataset $ds --nodes $NSMALL --frac $FRSMALL --tag $t --seed $s --policies $POLC --zipf 1.0 --stream $st --bg-finish $fin --checkpoints $cp --window $win --check-06 none --check-10 none --out $o $X"
      done
    done
  done
}

J1=$L/jobs1.txt; : > $J1          # R, V
J2=$L/jobs2.txt; : > $J2          # W
if inlist R "$PHASES"; then
  if [ -e $R_F ]; then
    o=probeVR15_$(echo $R_F | sed 's/^probeV14F_//; s/_cap16\.json$//').json
    add $J1 r15_rep $o "python3 evo/rerun_prev.py $R_F evo/11_probe_safe.py $o"
  else
    echo "bỏ qua R: thiếu $R_F (đợt 14)" | tee -a $JL
  fi
fi
inlist V "$PHASES" && srp_jobs $J1 v "$VTAGS"
inlist W "$PHASES" && srp_jobs $J2 w "$WTAGS"
echo "đợt 15: $(wc -l < $J1) job ở R, V; $(wc -l < $J2) ở W; bỏ qua $NSKIP job đã có file. P=$P" | tee -a $JL
cat $J1 $J2 >> $L/all_jobs.txt
for pair in "$J1:R, V" "$J2:W"; do
  jf=${pair%%:*}
  [ -s $jf ] || continue
  run_jobs $jf
  echo "--- xong ${pair#*:} $(date '+%F %T')" | tee -a $JL
done

# ---------- tổng hợp
python3 evo/analyze_r15.py > $L/r15_summary.txt 2>&1
{
  cat $L/r15_summary.txt
  echo "################ TỰ KIỂM (dòng >>> và lệch trong log)"
  grep -H ">>>\|    lệch:\|CẢNH BÁO" $L/*.log | sed "s#$L/##" | grep -v "bỏ qua"
  echo "################ LỖI"
  grep -H "Traceback\|Error\|LỆCH\|DỪNG\|THIẾU\|\*\*\*" $L/*.log | sed "s#$L/##" | head -60
  echo "################ THỜI GIAN"
  cat $JL
} > evo/round15_all.txt
echo "XONG ĐỢT 15 $(date '+%F %T')" | tee -a $JL evo/round15_all.txt
