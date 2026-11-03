# Đợt 11: ablation C3, migrate tới khi xong, cơ chế C2, điều kiện vận hành của payload, model mới

Đợt 11 làm theo góp ý của thầy sau đợt 10. Mọi giả thuyết và cách chấm nằm trong `PREREG_round11.md` (tag
`evo-r11-prereg`); `analyze_r11.py` in ĐẠT, KHÔNG ĐẠT hoặc KHÔNG CHẠY cho từng tiêu chí, rồi in phần thăm dò và phần tự
kiểm. Đợt này trả lời sáu câu hỏi:

1. **Ba thành phần của C3 đóng góp riêng bao nhiêu?** Retire trễ trên đường truy vấn kéo về, mã PQ E1 gắn tại chỗ, retire
   trễ trên đường nền, và migrate nền với phần ngân sách tiết kiệm được (H11).
2. **Khi migrate tới khi xong, verify-then-retire đứng ở đâu giữa hai cách làm ở hai đầu?** Một đầu là retire ngay với
   cùng lịch nền (lazybg), đầu kia là giữ cả epoch cũ tới khi xong (lazyVbgDinf). Tính đủ chi phí: peer phải hỏi, record
   phải chấm, payload, nhúng lại, lưu trữ theo record và theo byte (H12, E1).
3. **C2 khác ở cơ chế nào?** Khoá học so với khoá ngẫu nhiên đã trừ tâm ở cùng số ứng viên, cả hai có giới hạn tải;
   giới hạn tải có làm mất recall không; chỉ giới hạn tải cho SRP thì có đủ không (H13, E8).
4. **Mô hình dị hướng của C1 có đúng trên cặp mới không?** (H14)
5. **Kết quả có giữ trên model mới không?** Hai model khác họ, chưa từng dùng: gte-base (768 chiều) và all-MiniLM-L6-v2
   (384 chiều) (H14 đến H16).
6. **Tiết kiệm payload phụ thuộc gì?** Kiểm trước dự đoán rút ra từ việc H8 không đạt ở đợt 9: với dòng 3.000 lượt, code
   20k và SciFact cũng đạt tỉ lệ payload không quá 1/3 (H17); tách payload theo số lần query lặp lại (E2).

| pha | nội dung | số job | thời gian ước tính |
|---|---|---|---|
| R | kiểm hồi quy: chạy lại 3 job đợt 10 bằng code mới, có xen chính sách mới; phải trùng từng số | 3 | 30 phút |
| A | dị hướng và placement (srp, srp_c, pca_q, itq_q, có và không cap16), 3 corpus × 4 không gian cũ × seed 26 đến 28 | 72 | |
| B | ablation C3 trên code100kfq, itq_q+cap16, 3 model × seed 26 đến 35, Zipf 1 và đều | 30 | |
| C | migrate tới khi xong: code 20k (T = 1.500, 3.000) và SciFact (T = 400, 800), 3 model × seed 26 đến 35 | 60 | |
| G | payload theo độ dài dòng: code 20k (600, 3.000 lượt), SciFact (155, 3.000 lượt), 3 model × seed 26 đến 30 | 60 | |
| F | churn và lỗi peer trên itq_q+cap16, code100kfq, 3 model × seed 26 đến 28 | 9 | |
| E | nhúng model mới: MiniLM trên code100kfq, code 20k, SciFact; gte-base trên code 20k, SciFact | 5 | 1 đến 5 giờ |
| N | như A, B, C cho model mới: 5 cặp dị hướng và placement; C3 MiniLM trên code100kfq; migrate tới khi xong cho 2 model | 80 | |

Tổng cộng 319 job, ra 314 file json (pha E chỉ ghi vào `data/`). Thứ tự chạy: R và A; rồi B, C, G, F; rồi E, từng job
một vì mỗi job nhúng dùng mọi lõi; rồi phần A của N; rồi phần B, C của N. Ước tính trên node-dal-02 với 4 job song song,
dựa trên thời gian thật của các job đợt 10: R và A khoảng 2 giờ, B, C, G, F khoảng 5 giờ, E khoảng 1 đến 5 giờ, N khoảng
2 giờ; tổng khoảng 10 đến 14 giờ. Phần khó đoán nhất là nhúng gte-base trên code 20k: log của job in tốc độ đo được và
thời gian dự kiến ngay đầu job.

Không nhúng gte-base trên code100kfq vì 100.000 hàm code với model cỡ base trên 4 lõi CPU tốn quá lâu; MiniLM nhỏ hơn
nhiều nên chạy được cả code100kfq.

## Thay đổi code (tag `evo-r11-prereg`)

- **`11_probe_safe.py`.**
  - Chính sách mới `lazyVbgDk<c>` (lazyVbgD với c xác nhận) và `lazyVbgDinf` (không retire bản E0 nào trước khi xong;
    xong thì gỡ cả index E0 một lần). Chỉ chạy với `--bg-finish`.
  - Hậu tố `_adp`: chạy chính sách với điểm adapter cho bản E0 của object dual, tức bỏ mã E1 gắn tại chỗ, trong cùng job
    với chính sách gốc. Phần dựng index và định tuyến chiếm phần lớn thời gian của job, nên làm thế tiết kiệm khoảng
    10 phút mỗi job ở code100kfq.
  - Đo thêm: byte lưu trữ mỗi object (metadata 0 và 64 byte mỗi record); phần top-5 thật còn đường tìm và phần mất đường
    vì retire; số object đúng của từng query giữ riêng; payload, final, rerank theo lần xuất hiện của query, theo cả dòng
    và theo cửa sổ; số lần nhúng lại tách theo do truy vấn và do nền, kể cả bản E1 mà rebuild dựng ở nền.
  - Mặc định không đổi gì: khi không dùng chính sách hay hậu tố mới, mọi chính sách cũ cho đúng từng số đợt 10.
- **`10_probe_placement.py`.** Ghi thêm số record phải vào peer đầy vì cả K peer đều đầy; vị trí đặt không đổi. Hậu tố
  `+cap<m>` vốn dùng được với mọi biến thể từ đợt 10; đợt này lần đầu dùng nó với srp, srp_c và pca_q.
- **Thêm mới:** `rerun_prev.py` (chạy lại một job cũ với đúng tham số trong file kết quả cũ, rồi kiểm lượt mới có đủ mọi
  run của lượt cũ; dùng cho pha R), `PREREG_round11.md`, `analyze_r11.py`, `run_round11.sh`, `SHA256SUMS_round11`,
  `README_round11.md`.

Đã chạy thử trên dữ liệu giả (cùng bộ dữ liệu giả của đợt 10, thêm hai tag giả 768 và 384 chiều cho model mới):

- Hồi quy với đợt 10: chạy lại 3 job của lượt chạy thử đợt 10 bằng `rerun_prev.py`, có xen chính sách mới: trùng từng số
  ở 488, 4.232 và 1.831 giá trị, đủ 4/4 biến thể, 10/10 và 13/13 run.
- Hồi quy với đợt 9, cho các chính sách pha R không phủ (bg, bgV1, lazyVbg, mapall, mapkeep, churn và lỗi peer): chạy lại
  3 job của lượt chạy thử đợt 9, trùng từng số ở 2.346, 7.416 và 2.091 giá trị.
- Hậu tố `_adp`: một job chạy cả chính sách gốc lẫn bản `_adp` cho đúng từng số như hai job riêng (một job mặc định, một
  job `--dual-score adapter`): 5.738 và 2.390 giá trị ở C3 trên code100kfq, 3.028 và 3.028 giá trị ở chế độ migrate tới
  khi xong.
- Model 384 chiều chạy được ở cả 10 và 11.
- Đủ 71 job của `run_round11.sh` với 2 model cũ, 2 model mới giả, ít seed và dòng ngắn: mọi job thoát mã 0. Tự kiểm:
  placement itq_q+cap16 trong 11 trùng 10 ở 21/21 file; cách chấm object dual đúng hậu tố ở 702/702 run; nhúng lại do
  truy vấn cộng do nền bằng `new` ở 670/670 run, rebuild dựng đủ N − |S| bản ở 32/32 run; sau lượt xong trùng full ở
  755/755 checkpoint; rebuild trùng static trước lượt xong ở 118/118 checkpoint; lazyVbgDinf không retire trước khi xong
  ở 34/34 run; ngưỡng k đúng ở 66/66 run. `PHASES=S` chỉ ghép lại phần tổng hợp, không chạy job nào.
- Analyze chạy được khi thiếu dữ liệu: bỏ hết file của một model mới thì các tiêu chí của model đó, và H14a đến H14c,
  ghi KHÔNG CHẠY; với thư mục rỗng và cấu hình mặc định, analyze đếm đúng 109 tiêu chí.
- Một lượt rà soát độc lập (dry run với cấu hình thật, python giả) đếm đúng 75, 159, 5, 30 và 50 job ở các nhóm, 314
  file json, và 87 file có tự kiểm placement.

Dữ liệu giả không phản ánh dữ liệu thật, nên ĐẠT hay KHÔNG ĐẠT ở lượt chạy thử không có ý nghĩa.

## Các bước

**Trên laptop:**

```bash
cd Evo_Engram
git checkout main && git pull
git log --oneline -1                     # phải là: 08fcb1d evo: dot 10, gioi han tai cho placement hoc, ...
git am ~/Downloads/0001-evo-dot-11*.patch
sha256sum -c evo/SHA256SUMS_round11      # 10 dòng OK (máy Mac: shasum -a 256 -c ...)
git tag -a evo-r11-prereg -m "dot 11: ablation C3, migrate toi khi xong, co che C2, model moi"
git push origin main --tags
```

**Trên server** (mọi lệnh chạy trong thư mục repo):

```bash
cd ~/Evo_Engram
git status --short | grep -v '^??'       # không in gì
git fetch origin --tags && git checkout evo-r11-prereg
git describe --tags                      # evo-r11-prereg
sha256sum -c evo/SHA256SUMS_round11
ls probeP10_code100kfq_arctic_s16.json probeV10_code100kfq_bgebase_s16_itq_q_cap16.json \
   probeV10F_code_bgebase_s16_itq_q.json # ba file đợt 10 phải có
```

Trước khi chạy, kiểm server tải được hai model mới và M0 mà bước tự kiểm của pha E dùng (vài phút, chỉ một lần; model
lưu vào cache của Hugging Face):

```bash
[ -f venv/bin/activate ] && source venv/bin/activate
python3 -c "from sentence_transformers import SentenceTransformer as S; [S(m, device='cpu') for m in ('sentence-transformers/all-MiniLM-L6-v2', 'thenlper/gte-base', 'BAAI/bge-large-en-v1.5')]; print('TẢI MODEL OK')"
```

Nếu lệnh in `TẢI MODEL OK`, chạy cả đợt:

```bash
tmux new -s round11 -d "bash ~/Evo_Engram/evo/run_round11.sh"
```

Nếu không tải được model, vẫn chạy được mọi pha không cần model mới, rồi chạy nốt khi tải được (biến `PHASES` phải nằm
trong dấu nháy kép như dưới đây thì tmux mới nhận):

```bash
tmux new -s round11 -d "PHASES='R A B C G F' bash ~/Evo_Engram/evo/run_round11.sh"
# sau khi lượt trên xong và đã tải được model:
tmux new -s round11n -d "PHASES='E N' bash ~/Evo_Engram/evo/run_round11.sh"
```

**Kiểm trong lúc chạy.**

1. Khoảng 10 giây sau:

   ```bash
   head -14 evo/r11_logs/jobs.log
   ```

   Phải có `numpy ...`, `HEAD = tag evo-r11-prereg`, dòng `đợt 11: 75 job ở R, A; 159 job ở B, C, G, F; 5 job nhúng ở
   E; ...`, và không có `DỪNG`.

2. Sau khoảng 30 phút, pha R xong:

   ```bash
   grep -H "so với lượt cũ\|    lệch:\|rerun_prev: " evo/r11_logs/r11_*.log | grep -v "rerun_prev: python3"
   ```

   Phải in đúng 6 dòng, mỗi job hai dòng: một dòng kết thúc bằng `KHỚP`, một dòng `lượt mới có đủ n/n ...`. Nếu có dòng
   `LỆCH`, `lệch:` hay `THIẾU`, báo em ngay; theo đăng ký trước, khi đó cả đợt chỉ còn giá trị thăm dò.

3. Tiến độ và lỗi, xem lúc nào cũng được:

   ```bash
   grep -c "mã thoát" evo/r11_logs/jobs.log         # số job đã xong
   grep "mã thoát [1-9]" evo/r11_logs/jobs.log      # job lỗi, phải không in gì
   tail -3 evo/r11_logs/jobs.log
   ```

4. Pha E (bắt đầu sau khoảng 7 giờ). Dòng `--- xong B, C, G, F` xuất hiện trong `jobs.log` thì pha E bắt đầu:

   ```bash
   grep -h "dataset=\|tốc độ đo được\|tự kiểm\|dùng cách dựng\|GT overlap\|đã ghi" evo/r11_logs/e11_*.log
   tail -c 300 evo/r11_logs/e11_*.log               # thanh tiến độ của job đang chạy
   ```

   Mỗi job in các dòng tự kiểm văn bản với M0 (document rồi query); nếu cosine trung bình dưới 0,999 thì job tự dừng với
   mã thoát khác 0. Sau đó có dòng `tốc độ đo được: ... doc/s -> dự kiến ... phút`, và khi xong có dòng `đã ghi 3 file`.
   Job nhúng nào lỗi thì các phần của cặp đó ở pha N tự bỏ qua, và analyze ghi KHÔNG CHẠY cho tiêu chí tương ứng.

5. Muốn em xem sớm phần không cần model mới: khi `jobs.log` có dòng `--- xong B, C, G, F`, chạy lệnh `tar` ở mục dưới
   rồi gửi em trước. Lúc đó chưa có `evo/round11_all.txt` nên tar báo thiếu file này, không sao; các số đếm cũng chưa
   đủ. Các pha còn lại vẫn chạy tiếp; xong thì đóng gói lại lần nữa.

**Khi xong** (dòng cuối `jobs.log` là `XONG ĐỢT 11 ...`):

```bash
cd ~/Evo_Engram
grep -c "mã thoát" evo/r11_logs/jobs.log         # 319
grep "mã thoát [1-9]" evo/r11_logs/jobs.log      # không in gì
sed -n '/TÓM TẮT ĐÁNH GIÁ/,/Tổng:/p' evo/round11_all.txt | tail -8
sed -n '/^Tự kiểm/,/số file/p' evo/round11_all.txt
tar czf ~/evo_round11_results.tar.gz probePR11_*.json probeVR11*.json probeA11_*.json probeP11_*.json probeV11*.json \
    evo/r11_logs evo/round11_all.txt
tar tzf ~/evo_round11_results.tar.gz | grep -c json   # 314
```

Hai lệnh `sed` in phần tóm tắt (số tiêu chí đạt, không đạt, không chạy theo từng giả thuyết) và phần tự kiểm. Phần tự
kiểm phải cho:

- 3 file của pha R đều `KHỚP`;
- placement trong 11 trùng 10: 87/87 file KHỚP (các job C3 có seed 26 đến 28);
- cách chấm object dual đúng theo hậu tố `_adp` ở mọi run;
- nhúng lại do truy vấn cộng do nền bằng `new` ở mọi run, và rebuild dựng đủ N − |S| bản ở mọi run;
- migrate tới khi xong: mọi checkpoint sau lượt xong trùng full, rebuild trùng static trước lượt xong, lazyVbgDinf không
  retire trước khi xong, ngưỡng k đúng;
- số file: dị hướng 51, placement 51, C3 code100kfq 40, migrate tới khi xong 100, độ dài dòng 60, churn 9.

Lấy file về laptop (thay `node-dal-02` bằng tên máy anh vẫn dùng để ssh):

```bash
scp node-dal-02:~/evo_round11_results.tar.gz ~/Downloads/
```

Rồi gửi lại file tar.

**Nếu một job lỗi.** Chạy lại nguyên trạng đúng dòng lệnh của job đó, lấy từ `evo/r11_logs/all_jobs.txt` (file này giữ
dòng lệnh của mọi job qua mọi lần chạy), với cùng môi trường như script, rồi ghép lại phần tổng hợp. Ví dụ với job
`v11_bgebase_s27`:

```bash
cd ~/Evo_Engram
[ -f venv/bin/activate ] && source venv/bin/activate
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
grep -h "^v11_bgebase_s27|" evo/r11_logs/all_jobs.txt | tail -1 | cut -d'|' -f2- | bash -o pipefail \
    > evo/r11_logs/v11_bgebase_s27.log 2>&1; echo "mã thoát $?"
PHASES=S bash evo/run_round11.sh        # chỉ chạy lại analyze và ghép evo/round11_all.txt, không chạy job nào
```

Với job nhúng (`e11_*`), bỏ dòng `export` vì job đó tự đặt số luồng.
