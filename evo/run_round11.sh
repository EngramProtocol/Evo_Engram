#!/bin/bash
# Đợt 11: ablation C3, migrate tới khi xong, cơ chế C2, điều kiện vận hành của payload, model mới
# (evo/PREREG_round11.md, tag evo-r11-prereg).
#   R  Kiểm hồi quy bằng rerun_prev.py trên 3 file đợt 10: placement Arctic s16; C3 bge-base s16 itq_q+cap16 có xen
#      lazyV_adp, lazyVbgD_adp; migrate tới khi xong code 20k bge-base s16 có xen chính sách mới. Phải trùng từng số.
#   A  C1, C2 với 4 không gian cũ trên code100kfq, code 20k, SciFact, seed 26..28: dị hướng (--aniso-only) và placement
#      srp, srp_c, pca_q, itq_q, mỗi biến thể có và không có cap16.                                    (H13, H14, H15)
#   B  Ablation C3: code100kfq, itq_q+cap16, 3 model x seed 26..35, Zipf 1 và đều.                    (H11)
#   C  Migrate tới khi xong: code 20k (dòng 3.000, T = 1.500, 3.000), SciFact (dòng 800, T = 400, 800), 3 model x
#      seed 26..35, Zipf 1.                                                                             (H12)
#   G  Payload theo độ dài dòng: code 20k (600, 3.000 lượt), SciFact (155, 3.000 lượt), 3 model x seed 26..30. (H17)
#   F  Churn và lỗi peer trên itq_q+cap16: code100kfq, 3 model x seed 26..28.                          (thăm dò)
#   E  Nhúng hai model mới bằng 01_embed_m1.py, lần lượt từng job, mỗi job dùng mọi lõi: MiniLM trên code100kfq, code
#      20k, SciFact; gte-base trên code 20k, SciFact. Bỏ qua cặp đã có dữ liệu.
#   N  Như A, B, C cho model mới, sau E: dị hướng và placement 5 cặp mới; C3 MiniLM trên code100kfq; migrate tới khi
#      xong cho gte-base và MiniLM.                                                                     (H14, H15, H16)
# Thứ tự: R và A; rồi B, C, G, F; rồi E; rồi phần A của N; rồi phần B, C của N.
# Yêu cầu: probeP10_code100kfq_arctic_s16.json, probeV10_code100kfq_bgebase_s16_itq_q_cap16.json,
#          probeV10F_code_bgebase_s16_itq_q.json của đợt 10 ở thư mục gốc repo; HEAD đúng tag evo-r11-prereg.
# Chạy:    tmux new -s round11 -d "bash ~/Evo_Engram/evo/run_round11.sh"
# Chỉ chạy một phần: PHASES="R A" (mặc định "R A B C G F E N"); PHASES=S chỉ chạy lại analyze và ghép evo/round11_all.txt.
# File ra mới, không ghi đè file cũ: probePR11_*, probeVR11*_ (R), probeA11_*, probeP11_* (A, N), probeV11_* (B, N),
# probeV11F_* (C, N), probeV11G_* (G), probeV11C_* (F). Mọi dòng lệnh job của mọi lần chạy được ghi nối vào
# evo/r11_logs/all_jobs.txt (dùng khi cần chạy lại một job).
cd ${EVO_ROOT:-~/Evo_Engram} || exit 1
[ -f venv/bin/activate ] && source venv/bin/activate
export OPENBLAS_NUM_THREADS=${NT:-1} OMP_NUM_THREADS=${NT:-1} MKL_NUM_THREADS=${NT:-1}
P=${P:-4}
NTE=${NTE:-$(nproc)}                        # số luồng cho mỗi job nhúng ở pha E
PHASES=${PHASES:-"R A B C G F E N"}
SEEDS_A=${SEEDS_A:-"26 27 28"}
SEEDS_B=${SEEDS_B:-"26 27 28 29 30 31 32 33 34 35"}
SEEDS_C=${SEEDS_C:-"26 27 28 29 30 31 32 33 34 35"}
SEEDS_G=${SEEDS_G:-"26 27 28 29 30"}
SEEDS_F=${SEEDS_F:-"26 27 28"}
TAGS=${TAGS:-"bgebase e5large arctic"}
SPACES=${SPACES:-"bgebase e5large arctic m0"}
NEWTAGS=${NEWTAGS:-"minilm gtebase"}
declare -A MODEL=([minilm]="sentence-transformers/all-MiniLM-L6-v2" [gtebase]="thenlper/gte-base")
declare -A EMBDS=([minilm]="code100kfq code scifact" [gtebase]="code scifact")
EMB_minilm=${EMBDS[minilm]}; EMB_gtebase=${EMBDS[gtebase]}
NEW_ON_100K=$(for t in $NEWTAGS; do [[ " ${EMBDS[$t]} " == *" code100kfq "* ]] && echo -n "$t "; done)
N100=${N100:-50000}; NSMALL=${NSMALL:-10000}
FR100=${FR100:-0.02}; FRSMALL=${FRSMALL:-0.1}
ST_CODE=${ST_CODE:-3000}; ST_SCI=${ST_SCI:-800}
FIN_CODE=${FIN_CODE:-"1500,3000"}; FIN_SCI=${FIN_SCI:-"400,800"}
CP_CODE=${CP_CODE:-"0,150,300,600,900,1200,1500,2000,2500,3000"}; CP_SCI=${CP_SCI:-"0,50,100,200,300,400,500,600,700,800"}
W_CODE=${W_CODE:-150}; W_SCI=${W_SCI:-50}
GL_CODE=${GL_CODE:-"600 3000"}; GL_SCI=${GL_SCI:-"155 3000"}
export SEEDS_A SEEDS_B SEEDS_C SEEDS_G SEEDS_F TAGS SPACES NEWTAGS NEW_ON_100K EMB_minilm EMB_gtebase GL_CODE GL_SCI
#        (analyze_r11.py đọc cùng các danh sách này)
CSETS=${CSETS:-"ch:churn_min=720,median_session=120,repair_every=60;fail:fail_at=1500,fail_frac=0.3"}
R_P=${R_P:-probeP10_code100kfq_arctic_s16.json}
R_V=${R_V:-probeV10_code100kfq_bgebase_s16_itq_q_cap16.json}
R_F=${R_F:-probeV10F_code_bgebase_s16_itq_q.json}
X=${X:-}; XB=${XB:-}; XP=${XP:-}; XE=${XE:-}    # tham số thêm, CHỈ dùng khi chạy thử trên dữ liệu giả
VARS="srp,srp_c,pca_q,itq_q,srp+cap16,srp_c+cap16,pca_q+cap16,itq_q+cap16"
POLB="static,lazy,lazyV,lazyV_adp,lazyVbg,lazyVbgD,lazyVbgD_adp,lazyD,bg,full"
POLC="static,lazy,full,bg,lazybg,rebuild,lazyVbg,lazyVbgD,lazyVbgD_adp,lazyVbgDk2,lazyVbgDk3,lazyVbgDinf"
POLG="static,lazy,lazyV,lazyV_adp,lazyVbgD,lazyVbgD_adp,full"
POLF="static,lazy,lazyV,lazyVbgD,full"
L=evo/r11_logs
mkdir -p $L
JL=$L/jobs.log
F="grep --line-buffered -v WARNING.clustering"
{ echo "=== ĐỢT 11 bắt đầu $(date '+%F %T')  P=$P  NTE=$NTE  pha: $PHASES"; free -g | head -2;
  python3 -c "import numpy; print('numpy', numpy.__version__)"; } | tee -a $JL

# ---------- 0. kiểm tra
git describe --tags --exact-match 2>/dev/null | grep -qx "evo-r11-prereg" \
  && echo "HEAD = tag evo-r11-prereg ($(git rev-parse --short HEAD))" | tee -a $JL \
  || echo "CẢNH BÁO: HEAD chưa ở tag evo-r11-prereg" | tee -a $JL
sha256sum -c evo/SHA256SUMS_round11 --quiet 2>&1 | tee -a $JL
[ "${PIPESTATUS[0]}" = "0" ] || { echo "FILE CỦA ĐỢT 11 BỊ SỬA SO VỚI SHA256SUMS_round11, DỪNG" | tee -a $JL; exit 1; }
if [[ " $PHASES " == *" R "* ]]; then
  miss=0
  for f in $R_P $R_V $R_F; do [ -e $f ] || { echo "THIẾU $f (kết quả đợt 10)" | tee -a $JL; miss=1; }; done
  [ "$miss" = "0" ] || { echo "THIẾU FILE, DỪNG" | tee -a $JL; exit 1; }
fi
have() {   # $1 dataset, $2 tag (m0 = không gian M0): đủ dữ liệu cho 10 và 11
  for f in data/$1_corpus_embeddings.npy data/$1_query_embeddings.npy data/$1_ground_truth.json \
           data/$1_pq_codebook_m512.npy data/$1_pq_codes_m512.npy; do [ -e $f ] || return 1; done
  [ "$2" = "m0" ] && return 0
  for f in data/$1_$2_corpus_embeddings.npy data/$1_$2_query_embeddings.npy data/$1_$2_ground_truth.json; do
    [ -e $f ] || return 1; done
}
nodes_of() { [ "$1" = "code100kfq" ] && echo "--nodes $N100 --frac $FR100" || echo "--nodes $NSMALL --frac $FRSMALL"; }
c10_of() {   # $1 dataset, $2 tag, $3 seed: file placement của pha A để 11 tự kiểm, hoặc none
  [[ " $SEEDS_A " == *" $3 "* ]] && echo "probeP11_$1_$2_s$3.json" || echo none
}
inlist() { [[ " $2 " == *" $1 "* ]]; }

run_jobs() {   # $1: file lệnh, mỗi dòng "tên|lệnh"; $2: số job song song (mặc định P)
  local par=${2:-$P}
  while IFS='|' read -r name cmd; do
    [ -z "$name" ] && continue
    while [ "$(jobs -rp | wc -l)" -ge "$par" ]; do wait -n; done
    ( t0=$(date +%s); echo "BẮT ĐẦU $(date +%T) $name" >> $JL
      bash -o pipefail -c "$cmd" > $L/$name.log 2>&1; rc=$?
      echo "XONG    $(date +%T) $name  ($(( $(date +%s) - t0 ))s, mã thoát $rc)" >> $JL ) &
  done < "$1"
  wait
}

PP="python3 evo/10_probe_placement.py"
V11="python3 evo/11_probe_safe.py --confirms 1 --e1-place itq_q --e1-cap 16"

add_place() {   # $1 file lệnh, $2 dataset, $3 tag hoặc m0: dị hướng và placement cho mọi seed của pha A
  local sp=""; [ "$3" = "m0" ] && sp="--space m0"
  for s in $SEEDS_A; do
    echo "a11_$2_$3_s$s|$PP --dataset $2 --tag $3 $sp --seed $s $(nodes_of $2) --aniso-only 1 --out probeA11_$2_$3_s$s.json $XP 2>&1 | $F" >> $1
    echo "p11_$2_$3_s$s|$PP --dataset $2 --tag $3 $sp --seed $s $(nodes_of $2) --variants $VARS --out probeP11_$2_$3_s$s.json $XP 2>&1 | $F" >> $1
  done
}
add_c3() {      # $1 file lệnh, $2 tag: ablation C3 trên code100kfq cho mọi seed của pha B
  for s in $SEEDS_B; do
    echo "v11_$2_s$s|$V11 --dataset code100kfq $(nodes_of code100kfq) --tag $2 --seed $s --policies $POLB --check-10 $(c10_of code100kfq $2 $s) --out probeV11_code100kfq_$2_s${s}_cap16.json $X $XB 2>&1 | $F" >> $1
  done
}
add_fin() {     # $1 file lệnh, $2 dataset (code, scifact), $3 tag: migrate tới khi xong cho mọi seed của pha C
  local st fin cp win
  if [ "$2" = "code" ]; then st=$ST_CODE; fin=$FIN_CODE; cp=$CP_CODE; win=$W_CODE; else st=$ST_SCI; fin=$FIN_SCI; cp=$CP_SCI; win=$W_SCI; fi
  for s in $SEEDS_C; do
    echo "f11_$2_$3_s$s|$V11 --dataset $2 $(nodes_of $2) --tag $3 --seed $s --policies $POLC --zipf 1.0 --stream $st --bg-finish $fin --checkpoints $cp --window $win --check-10 $(c10_of $2 $3 $s) --out probeV11F_$2_$3_s${s}_cap16.json $X 2>&1 | $F" >> $1
  done
}

J1=$L/jobs1.txt; : > $J1          # R, A
J2=$L/jobs2.txt; : > $J2          # B, C, G, F
JE=$L/jobsE.txt; : > $JE          # E
J3=$L/jobs3.txt; : > $J3          # N: dị hướng và placement của model mới
J4=$L/jobs4.txt; : > $J4          # N: C3 và migrate tới khi xong của model mới
if inlist R "$PHASES"; then
  echo "r11_prep|python3 evo/rerun_prev.py $R_P evo/10_probe_placement.py probePR11_code100kfq_arctic_s16.json --set variants=srp,srp_c,itq_q,itq_q+cap16 2>&1 | $F" >> $J1
  echo "r11_rep|python3 evo/rerun_prev.py $R_V evo/11_probe_safe.py probeVR11_code100kfq_bgebase_s16_cap16.json --set policies=static,lazy,lazyV,lazyV_adp,lazyVbgD,lazyVbgD_adp,full 2>&1 | $F" >> $J1
  echo "r11_repf|python3 evo/rerun_prev.py $R_F evo/11_probe_safe.py probeVR11F_code_bgebase_s16.json --set policies=static,lazy,full,bg,lazybg,rebuild,lazyVbgD,lazyVbgD_adp,lazyVbgDk2,lazyVbgDinf,lazyVbgDc25 2>&1 | $F" >> $J1
fi
if inlist A "$PHASES"; then
  for ds in code100kfq code scifact; do for t in $SPACES; do
    if ! have $ds $t; then echo "bỏ qua A: thiếu dữ liệu $ds $t" | tee -a $JL; continue; fi
    add_place $J1 $ds $t
  done; done
fi
if inlist B "$PHASES"; then
  for t in $TAGS; do
    if ! have code100kfq $t; then echo "bỏ qua B: thiếu dữ liệu code100kfq $t" | tee -a $JL; continue; fi
    add_c3 $J2 $t
  done
fi
if inlist C "$PHASES"; then
  for ds in code scifact; do for t in $TAGS; do
    if ! have $ds $t; then echo "bỏ qua C: thiếu dữ liệu $ds $t" | tee -a $JL; continue; fi
    add_fin $J2 $ds $t
  done; done
fi
if inlist G "$PHASES"; then
  for ds in code scifact; do for t in $TAGS; do
    if ! have $ds $t; then echo "bỏ qua G: thiếu dữ liệu $ds $t" | tee -a $JL; continue; fi
    if [ "$ds" = "code" ]; then lens=$GL_CODE; win=$W_CODE; else lens=$GL_SCI; win=$W_SCI; fi
    for s in $SEEDS_G; do for len in $lens; do
      cp="0,$((len / 4)),$((len / 2)),$((3 * len / 4)),$len"
      echo "g11_${ds}_${t}_s${s}_L$len|$V11 --dataset $ds $(nodes_of $ds) --tag $t --seed $s --policies $POLG --stream $len --checkpoints $cp --window $win --check-10 $(c10_of $ds $t $s) --out probeV11G_${ds}_${t}_s${s}_L${len}_cap16.json $X 2>&1 | $F" >> $J2
    done; done
  done; done
fi
if inlist F "$PHASES"; then
  for t in $TAGS; do
    if ! have code100kfq $t; then echo "bỏ qua F: thiếu dữ liệu code100kfq $t" | tee -a $JL; continue; fi
    for s in $SEEDS_F; do
      echo "c11_${t}_s$s|$V11 --dataset code100kfq $(nodes_of code100kfq) --tag $t --seed $s --policies static --zipf 1.0 --churn-sets '$CSETS' --churn-policies $POLF --churn-zipf 1.0 --check-10 $(c10_of code100kfq $t $s) --out probeV11C_code100kfq_${t}_s${s}_cap16.json $X $XB 2>&1 | $F" >> $J2
    done
  done
fi
if inlist E "$PHASES"; then
  for t in $NEWTAGS; do for ds in ${EMBDS[$t]}; do
    if have $ds $t; then echo "E: đã có dữ liệu $ds $t, không nhúng lại" | tee -a $JL; continue; fi
    echo "e11_${ds}_$t|env OMP_NUM_THREADS=$NTE MKL_NUM_THREADS=$NTE OPENBLAS_NUM_THREADS=$NTE python3 evo/01_embed_m1.py --dataset $ds --model ${MODEL[$t]} --tag $t --device cpu $XE 2>&1 | tr '\r' '\n'" >> $JE
  done; done
fi
echo "đợt 11: $(wc -l < $J1) job ở R, A; $(wc -l < $J2) job ở B, C, G, F; $(wc -l < $JE) job nhúng ở E; phần N lập sau E. P=$P" | tee -a $JL
cat $J1 $J2 $JE >> $L/all_jobs.txt
run_jobs $J1
echo "--- xong R, A $(date '+%F %T')" | tee -a $JL
run_jobs $J2
echo "--- xong B, C, G, F $(date '+%F %T')" | tee -a $JL
run_jobs $JE 1
echo "--- xong E $(date '+%F %T')" | tee -a $JL
if inlist N "$PHASES"; then
  for t in $NEWTAGS; do for ds in ${EMBDS[$t]}; do
    if ! have $ds $t; then echo "bỏ qua N: thiếu dữ liệu $ds $t" | tee -a $JL; continue; fi
    add_place $J3 $ds $t
    if [ "$ds" = "code100kfq" ]; then add_c3 $J4 $t; else add_fin $J4 $ds $t; fi
  done; done
  echo "phần N: $(wc -l < $J3) job dị hướng và placement, $(wc -l < $J4) job C3 và migrate tới khi xong" | tee -a $JL
  cat $J3 $J4 >> $L/all_jobs.txt
  run_jobs $J3
  echo "--- xong phần A của N $(date '+%F %T')" | tee -a $JL
  run_jobs $J4
  echo "--- xong N $(date '+%F %T')" | tee -a $JL
fi

# ---------- tổng hợp
python3 evo/analyze_r11.py > $L/r11_summary.txt 2>&1
{
  cat $L/r11_summary.txt
  echo "################ TỰ KIỂM (dòng >>> và lệch trong log)"
  grep -H ">>>\|    lệch:" $L/*.log | sed "s#$L/##" | grep -v "bỏ qua"
  echo "################ LỖI"
  grep -H "Traceback\|Error\|LỆCH\|DỪNG\|\*\*\*" $L/*.log | sed "s#$L/##" | head -60
  echo "################ THỜI GIAN"
  cat $JL
} > evo/round11_all.txt
echo "XONG ĐỢT 11 $(date '+%F %T')" | tee -a $JL evo/round11_all.txt
