# Đợt 12: phép xác minh mạnh hơn cho C3, quy tắc chọn placement theo qf, C1 và C2 trên năm model mới

Đợt 12 làm ba việc mà báo cáo đợt 11 (mục 13) đề xuất. Mọi giả thuyết và cách chấm nằm trong `PREREG_round12.md` (tag
`evo-r12-prereg`); `analyze_r12.py` in ĐẠT, KHÔNG ĐẠT hoặc KHÔNG CHẠY cho từng tiêu chí, rồi in phần thăm dò và phần tự
kiểm. Thầy chưa duyệt đề xuất này; nhóm chạy trước, và nếu thầy đổi ngưỡng hay định nghĩa sau khi xem số thì phần đổi
được báo cáo là thăm dò.

1. **C3: một phép xác minh mạnh hơn có giữ được chất lượng của drain mà vẫn bớt byte không?** Đợt 11 thấy retire sau một
   lần thấy kém drain, phần lớn vì một lần thấy chưa phải bằng chứng đủ, và vì code đếm cả các lần cùng một query lặp lại.
   Đợt này thêm ba quy tắc: chỉ đếm query khác nhau (`lazyVbgDu<c>`), veto khi đường cũ còn đưa object tới client mà đường
   mới thì không (`lazyVbgDv<c>`), và cả hai (`lazyVbgDuv<c>`). Mọi chính sách gỡ E0 đúng ở lượt T (`--finish-drop T`), nên
   hiệu giữa chúng chỉ còn do quy tắc retire (H18).
2. **Quy tắc chọn placement theo qf có đúng trên cặp chưa dùng không?** Đợt 11 thấy, sau khi xem số, rằng ở cùng số peer
   SRP gốc hơn itq_q+cap16 khi qf lớn và thua khi qf nhỏ. Đợt này kiểm trước quy tắc đó trên 10 cặp mới, với qf do C1 dự
   đoán (H19), cùng C2 (H20) và C1 (H21) trên các cặp mới.
3. **Sửa lỗi số luồng của pha nhúng.**

| pha | nội dung | số job | thời gian ước tính |
|---|---|---|---|
| R | kiểm hồi quy: chạy lại 2 job đợt 11 (seed 26) bằng code mới, có xen chính sách mới; phải trùng từng số | 2 | 40 phút |
| A | dị hướng và placement (srp, srp+cap16, srp_c+cap16, itq_q, itq_q+cap16), code 20k và SciFact × 6 không gian cũ × seed 36 đến 38 | 72 | chạy cùng R |
| C | C3, gỡ E0 đúng ở lượt T: code 20k (T = 1.500, 3.000) và SciFact (T = 400, 800), 5 model × seed 36 đến 45 | 100 | 2 giờ |
| E | nhúng 5 model mới trên code 20k và SciFact, từng job một, chạy song song với R, A, C | 10 | 1 đến 2 giờ, nằm trong R, A, C |
| N | như A cho 10 cặp mới, sau E | 60 | 15 phút |

Tổng cộng 244 job, ra 234 file json (pha E chỉ ghi vào `data/`). Ước tính trên node-dal-02 với 4 job song song và 4 luồng
cho pha nhúng, dựa trên thời gian thật của các job cùng loại ở đợt 11: tổng khoảng 3 đến 4 giờ. Phần khó đoán nhất vẫn là
pha nhúng; log của mỗi job nhúng in tốc độ đo được và thời gian dự kiến ngay đầu job.

Năm model mới: e5-small-v2 (`e5small`), gte-small (`gtesmall`), bge-small-en-v1.5 (`bgesmall`), all-mpnet-base-v2
(`mpnet`, 768 chiều) và snowflake-arctic-embed-xs (`arcticxs`); trừ mpnet, cả bốn đều 384 chiều. Đợt này không dùng
code100kfq.

## Thay đổi code (tag `evo-r12-prereg`)

- **`11_probe_safe.py`.**
  - Chính sách mới `lazyVbgDu<c>`, `lazyVbgDv<c>`, `lazyVbgDuv<c>` (c tối đa 3 khi đếm query khác nhau). Chỉ chạy với
    `--bg-finish`, như `lazyVbgDk<c>`. Bộ đếm nằm trong hàm `retire_ready`.
  - Tham số `--finish-drop done | T`. Mặc định `done` giữ đúng cách của đợt 10 và 11 (gỡ E0 ở lượt xong); `T` gỡ đúng ở
    lượt T cho mọi chính sách có nền.
  - Đo thêm: `vetoes`, `conf_distinct`, `t_drop`, `confirm_kind`, `finish_drop`.
  - Sửa phần mô tả ở đầu file: chữ "c truy vấn độc lập" là không chính xác, vì code đếm cả các lần một query lặp lại.
  - Mặc định không đổi gì: khi không dùng chính sách mới và để `--finish-drop done`, mọi chính sách cũ cho đúng từng số
    đợt 11.
- **`run_round12.sh`.** Đếm số lõi trước khi đặt `OMP_NUM_THREADS=1` (đợt 11 đếm sau nên pha nhúng chạy 1 luồng). Pha E
  chạy nền song song với R, A, C, mỗi job nhúng dùng NTE = số lõi − P luồng (mặc định 8 − 4 = 4); `EPAR=0` cho chạy E sau C
  như đợt 11, khi đó NTE mặc định là mọi lõi. Hàm chạy job chỉ đếm và chờ job của chính nó, nên pha E chạy nền không chiếm
  chỗ của P job kia.
- **Thêm mới:** `PREREG_round12.md`, `analyze_r12.py`, `run_round12.sh`, `SHA256SUMS_round12`, `README_round12.md`.
  `10_probe_placement.py`, `01_embed_m1.py`, `rerun_prev.py` không đổi.

Đã chạy thử trên dữ liệu giả (cùng bộ dữ liệu giả của đợt 11):

- **Hồi quy với đợt 11.** Chạy lại 3 job của lượt chạy thử đợt 11 bằng `rerun_prev.py`: migrate tới khi xong có xen
  lazyVbgDu2, lazyVbgDuv2, lazyVbgDv2 trùng từng số ở 3.994 giá trị (đủ 21/21 run); C3 trên code100kfq trùng ở 3.782 giá
  trị (20/20 run); churn và lỗi peer trùng ở 2.181 giá trị (11/11 run).
- **Hồi quy với đợt 9**, cho các chính sách pha R không phủ (bg, bgV1, lazyVbg, mapall, mapkeep, churn): trùng ở 2.346 và
  7.416 giá trị (20/20 và 18/18 run).
- **Bộ đếm xác nhận.** Hàm `retire_ready` qua 9 nhóm ca viết tay, và trùng với một cài đặt tham chiếu bằng tập hợp Python
  trên 4.800 dãy ngẫu nhiên (c = 1, 2, 3; có và không đếm query khác nhau; có và không veto).
- **Tương đương.** Trên một job giả: u1, v1, uv1 cho đúng từng số như k1 (lazyVbgD); v với ngưỡng không bao giờ đạt cho
  đúng từng số như drain, trừ số veto; với `--finish-drop done` thì `t_drop` = −1, với `T` thì `t_drop` = T và mọi
  checkpoint từ T trở đi trùng full.
- **Cả `run_round12.sh`** với 5 model của pha C, 6 không gian cũ, 5 model mới, ít seed và dòng ngắn (76 job): mọi job thoát
  mã 0. Pha E dùng một bản giả của `sentence_transformers`: với bge-large nó trả đúng embedding M0 đã lưu, nên bước tự kiểm
  văn bản của `01_embed_m1.py` chạy thật; prefix đúng theo họ (e5: `query: `, `passage: `; Arctic: instruction cho query;
  bge, gte, mpnet: không có). Tự kiểm: pha R KHỚP (3.782 và 3.994 giá trị, đủ 20/20 và 21/21 run); placement trong 11
  trùng 10 ở 10/10 file; gỡ E0 đúng lượt T ở 360/360 run; checkpoint từ T trở đi trùng full 810/810; drain không retire
  40/40; quy tắc k, u không có veto 360/360; loại quy tắc và ngưỡng đúng tên 280/280; nhúng lại do truy vấn cộng do nền
  bằng `new` 400/400.
- `PHASES=S` chỉ ghép lại phần tổng hợp, không chạy job nào, và cho đúng phần analyze như lượt chạy đầy đủ.
  `PHASES='E N'` sau khi xoá dữ liệu của hai model mới chỉ chạy 4 job nhúng của hai model đó, mỗi job dùng mọi lõi, rồi
  chạy N. `EPAR=0` chạy E sau C.
- **Analyze khi thiếu dữ liệu.** Bỏ hết file của một model mới thì H20 của model đó và các tiêu chí gộp H19, H21 ghi KHÔNG
  CHẠY (11 tiêu chí); với thư mục rỗng, analyze đếm đúng 63 tiêu chí.
- **Tính lại độc lập** các hiệu của H18 ở một ô, Δ_peer và hiệu của H20a ở một cặp, bằng một cài đặt riêng: trùng.
- **Dry run với cấu hình thật** (python giả): 74 job ở R, A; 100 ở C; 10 ở E; 60 ở N; tổng 244 job, 234 file json (66
  dị hướng, 66 placement, 100 C3, 2 pha R); 30 job C3 có tự kiểm placement.

Dữ liệu giả không phản ánh dữ liệu thật, nên ĐẠT hay KHÔNG ĐẠT ở lượt chạy thử không có ý nghĩa.

## Các bước

**Trên laptop:**

```bash
cd Evo_Engram
git checkout main && git pull
git log --oneline -1                     # phải là: a5fce21 evo: dot 11, sua 1: ep float32 khi nhung ...
git am ~/Downloads/0001-evo-dot-12*.patch
sha256sum -c evo/SHA256SUMS_round12      # 10 dòng OK (máy Mac: shasum -a 256 -c ...)
git tag -a evo-r12-prereg -m "dot 12: xac minh manh hon cho C3, quy tac qf, nam model moi"
git push origin main --tags
```

**Trên server** (mọi lệnh chạy trong thư mục repo):

```bash
cd ~/Evo_Engram
git status --short | grep -v '^??'       # không in gì
git fetch origin --tags && git checkout evo-r12-prereg
git describe --tags                      # evo-r12-prereg
sha256sum -c evo/SHA256SUMS_round12
ls probeV11F_code_bgebase_s26_cap16.json probeV11_code100kfq_bgebase_s26_cap16.json   # hai file đợt 11 phải có
ls data/code_gtebase_corpus_embeddings.npy data/scifact_minilm_corpus_embeddings.npy  # dữ liệu model của đợt 11
```

Trước khi chạy, kiểm server tải được năm model mới và M0 mà bước tự kiểm của pha E dùng (vài phút, chỉ một lần; model
lưu vào cache của Hugging Face):

```bash
[ -f venv/bin/activate ] && source venv/bin/activate
python3 -c "from sentence_transformers import SentenceTransformer as S; [S(m, device='cpu') for m in ('intfloat/e5-small-v2', 'thenlper/gte-small', 'BAAI/bge-small-en-v1.5', 'sentence-transformers/all-mpnet-base-v2', 'Snowflake/snowflake-arctic-embed-xs', 'BAAI/bge-large-en-v1.5')]; print('TẢI MODEL OK')"
```

Nếu lệnh in `TẢI MODEL OK`, chạy cả đợt:

```bash
tmux new -s round12 -d "bash ~/Evo_Engram/evo/run_round12.sh"
```

Nếu không tải được model, vẫn chạy được mọi pha không cần model mới, rồi chạy nốt khi tải được (biến `PHASES` phải nằm
trong dấu nháy kép như dưới đây thì tmux mới nhận):

```bash
tmux new -s round12 -d "PHASES='R A C' bash ~/Evo_Engram/evo/run_round12.sh"
# sau khi lượt trên xong và đã tải được model:
tmux new -s round12n -d "PHASES='E N' bash ~/Evo_Engram/evo/run_round12.sh"
```

Lượt `PHASES='E N'` không có pha nào chạy cùng, nên mỗi job nhúng tự dùng mọi lõi.

**Kiểm trong lúc chạy.**

1. Khoảng 10 giây sau:

   ```bash
   head -8 evo/r12_logs/jobs.log
   ```

   Phải có `NCPU=8  P=4  NTE=4  EPAR=1`, `numpy ...`, `HEAD = tag evo-r12-prereg`, dòng `đợt 12: 74 job ở R, A; 100 job
   ở C; 10 job nhúng ở E (song song với R, A, C, 4 luồng); ...`, và không có `DỪNG`. NCPU phải là số lõi thật của máy
   (8), không phải 1.

2. Pha E: mỗi job nhúng in các dòng tự kiểm văn bản với M0 (document rồi query), rồi tốc độ đo được:

   ```bash
   grep "e12_" evo/r12_logs/jobs.log
   grep -h "dataset=\|tốc độ đo được\|tự kiểm\|dùng cách dựng\|dtype=\|GT overlap\|đã ghi" evo/r12_logs/e12_*.log
   ```

   Dòng `device=cpu  max_seq=...  dtype=torch.float32` phải có `float32`. Nếu cosine tự kiểm dưới 0,999 thì job tự dừng
   với mã thoát khác 0; job nhúng nào lỗi thì cặp đó ở pha N tự bỏ qua và analyze ghi KHÔNG CHẠY cho tiêu chí tương ứng.

3. Sau khoảng 40 phút, pha R xong:

   ```bash
   grep -H "so với lượt cũ\|    lệch:\|rerun_prev: " evo/r12_logs/r12_*.log | grep -v "rerun_prev: python3"
   ```

   Phải in đúng 4 dòng, mỗi job hai dòng: một dòng kết thúc bằng `KHỚP`, một dòng `lượt mới có đủ 20/20` hoặc `21/21`.
   Nếu có dòng `LỆCH`, `lệch:` hay `THIẾU`, báo em ngay; theo đăng ký trước, khi đó cả đợt chỉ còn giá trị thăm dò.

4. Tiến độ và lỗi, xem lúc nào cũng được:

   ```bash
   grep -c "mã thoát" evo/r12_logs/jobs.log         # số job đã xong
   grep "mã thoát [1-9]" evo/r12_logs/jobs.log      # job lỗi, phải không in gì
   tail -3 evo/r12_logs/jobs.log
   ```

**Khi xong** (dòng cuối `jobs.log` là `XONG ĐỢT 12 ...`):

```bash
cd ~/Evo_Engram
grep -c "mã thoát" evo/r12_logs/jobs.log         # 244
grep "mã thoát [1-9]" evo/r12_logs/jobs.log      # không in gì
sed -n '/TÓM TẮT ĐÁNH GIÁ/,/Tổng:/p' evo/round12_all.txt | tail -6
sed -n '/^Tự kiểm/,/số file/p' evo/round12_all.txt
tar czf ~/evo_round12_results.tar.gz probeVR12*.json probeA12_*.json probeP12_*.json probeV12F_*.json \
    evo/r12_logs evo/round12_all.txt
tar tzf ~/evo_round12_results.tar.gz | grep -c json   # 234
```

Hai lệnh `sed` in phần tóm tắt (số tiêu chí đạt, không đạt, không chạy theo từng giả thuyết, tổng 63 tiêu chí) và phần tự
kiểm. Phần tự kiểm phải cho:

- 2 file của pha R đều `KHỚP`, đủ 20/20 và 21/21 run của lượt cũ;
- placement trong 11 trùng 10: 30/30 file KHỚP (các job C3 có seed 36 đến 38);
- pha C: gỡ E0 ở đúng lượt T 1800/1800 run, `--finish-drop T` 1800/1800 run, checkpoint từ T trở đi trùng full 4950/4950,
  drain không retire trước lúc gỡ 200/200, quy tắc k, u không có veto 1800/1800, loại quy tắc và ngưỡng đúng tên 1400/1400,
  nhúng lại do truy vấn + do nền = new 2000/2000 run;
- số file: dị hướng 66/66, placement 66/66, C3 100/100, pha R 2/2.

Lấy file về laptop (thay `node-dal-02` bằng tên máy anh vẫn dùng để ssh):

```bash
scp node-dal-02:~/evo_round12_results.tar.gz ~/Downloads/
```

Rồi gửi lại file tar.

**Nếu một job lỗi.** Chạy lại nguyên trạng đúng dòng lệnh của job đó, lấy từ `evo/r12_logs/all_jobs.txt` (file này giữ
dòng lệnh của mọi job qua mọi lần chạy), với cùng môi trường như script, rồi ghép lại phần tổng hợp. Ví dụ với job
`f12_code_bgebase_s40`:

```bash
cd ~/Evo_Engram
[ -f venv/bin/activate ] && source venv/bin/activate
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
grep -h "^f12_code_bgebase_s40|" evo/r12_logs/all_jobs.txt | tail -1 | cut -d'|' -f2- | bash -o pipefail \
    > evo/r12_logs/f12_code_bgebase_s40.log 2>&1; echo "mã thoát $?"
PHASES=S bash evo/run_round12.sh        # chỉ chạy lại analyze và ghép evo/round12_all.txt, không chạy job nào
```

Với job nhúng (`e12_*`), bỏ dòng `export` vì job đó tự đặt số luồng.
