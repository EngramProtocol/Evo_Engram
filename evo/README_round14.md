# Đợt 14: C3 trên khoá SRP gốc, xác nhận drain trên seed mới, và các phép đo bổ sung theo bản rà soát bản thảo

Bản rà soát bản thảo ngày 13/11 (`Ra_soat_ban_thao_Evo_Engram_v5_13_11.md`, mục 3 và 5) nêu các chỗ mà phản biện dễ hỏi
và không trả lời được bằng số đã có. Đợt này đo các chỗ đó. Giả thuyết, ngưỡng và cách đọc nằm ở `PREREG_round14.md`, chốt
ở tag `evo-r14-prereg` trước khi chạy. Không cần GPU, không nhúng lại, không đổi số nào của các đợt trước.

| pha | câu hỏi của phản biện | nội dung | số job | thời gian ước tính (P = 4) |
|---|---|---|---|---|
| R | | kiểm hồi quy: chạy lại một job dòng 3.000 lượt của đợt 13 (code 100k, bge-base, seed 26); 10 run phải trùng từng số | 1 | 12 phút |
| U | Quy tắc qf chọn SRP cho bge-base và e5-large, nhưng C3 chỉ được đo trên placement học. Trên SRP thì sao? (P2) | C3 trên khoá SRP gốc: code 100k, bge-base và e5-large, seed 26 đến 35; static, lazy, lazy+delay, k1, lazy+keep, full, drain (H24) | 20 | 15 phút (bge-base), 23 phút (e5-large) mỗi job; khoảng 1,6 giờ |
| C | Con số chính "drain hơn rebuild 14 đến 26 điểm" là thăm dò. (P5) | lặp lại migrate tới khi xong của đợt 11 trên seed mới 46 đến 55: code 20k và SciFact, 5 model, 20 ô (H22) | 100 | 3 đến 5 phút (code 20k), 1 đến 2 phút (SciFact) mỗi job; khoảng 1,2 giờ |
| D | Drain trên dòng 3.000 lượt mới có bge-base. | drain cho e5-large, Arctic, MiniLM trên cùng seed với Bảng 7 và Bảng 10, tự so với đợt 11 (H23) | 30 | 11 đến 17 phút mỗi job; khoảng 1,7 giờ |
| F | Churn chỉ chạy với k1. | churn và lỗi peer của đợt 11, thêm lazy+keep và drain: 3 model, seed 26 đến 28 (thăm dò) | 9 | 25 phút mỗi job; khoảng 1 giờ |
| B | Dual đọc hai epoch, full đọc một. Ở cùng số peer thì sao? (P4) | full với T = 16 probe trên dòng của Bảng 10: bge-base, seed 26 đến 35 (thăm dò) | 10 | 8 đến 12 phút mỗi job; khoảng 30 phút |
| O | Mọi thiết lập có nhiều nhất 2 object mỗi peer. (P3) | placement của code 100k trên 5.000 peer (khoảng 20 object mỗi peer): 5 không gian, seed 26 đến 28 (thăm dò) | 15 | 20 đến 45 phút mỗi job, ước lượng kém chắc nhất; khoảng 2 giờ |

Tổng 185 job, ra 185 file json. Với 4 job song song trên node-dal-02, ước tính 7 đến 9 giờ. Thứ tự chạy là R và U, rồi C,
D, F, B, O: hai pha có đăng ký trước quan trọng nhất (H24, H22) xong sau khoảng 3 giờ.

Cơ sở của ước tính: job SRP của đợt 8 chạy 18 run trong 18 đến 54 phút, trong đó phần dựng index 8 đến 11 phút, đợt này 7
run mỗi job; job migrate tới khi xong của đợt 11 chạy 21 run trong 4 đến 8 phút (code 20k) và 2 phút (SciFact), đợt này 13
run; job dòng của đợt 13 (10 run, bge-base) mất 9 đến 14 phút; job churn của đợt 11 (11 run) mất 14 đến 24 phút, đợt này
15 run; job placement của đợt 11 ở 50.000 peer mất 77 đến 97 phút với model 768 và 1.024 chiều, trong đó 9
đến 17 phút là chấm ADC (không phụ thuộc số peer) và phần lớn còn lại là định tuyến tới 50.000 peer; ở 5.000 peer phần
định tuyến ngắn đi nhiều nhưng mỗi peer giữ nhiều record hơn, nên thời gian của pha O chưa đo được trước.

## Thay đổi code (tag `evo-r14-prereg`)

- **Không sửa bộ mô phỏng.** `11_probe_safe.py`, `10_probe_placement.py`, `me_common.py`, `rerun_prev.py`, `src/` giữ đúng
  như tag `evo-r13-prereg` (cùng SHA-256). Mọi thứ đợt này cần đã có sẵn:
  - khoá SRP gốc cho epoch mới: `--e1-place u` (không dùng `--e1-cap`);
  - drain trên dòng không có hạn chót: `lazyVbgDinf` đứng sau `lazy` và `lazyD` trong `--policies` (đợt 13); cũng chạy được
    trong `--churn-policies`;
  - full ở ngân sách gấp đôi: `--policies full --probes 16`;
  - overlay nhỏ hơn cho phép đo placement: `--nodes 5000`.
- **Thêm mới:** `PREREG_round14.md`, `run_round14.sh`, `analyze_r14.py`, `README_round14.md`, `SHA256SUMS_round14`.
- `run_round14.sh` có hai điểm mới so với các driver trước:
  - `SKIP_DONE=1` bỏ qua job đã có file kết quả đọc được, để chạy tiếp sau khi bị ngắt;
  - khoá `evo/r14_logs/run.pid`: lần gọi thứ hai khi lần đầu còn chạy sẽ tự dừng, vì nó sẽ ghi đè danh sách job mà lần đầu
    đang đọc. Muốn xem kết quả tạm thì chạy `python3 evo/analyze_r14.py` (chỉ đọc).

## Mỗi pha trả lời điều gì

**U và H24.** Trên code 100k, quy tắc H19 chọn SRP cho bge-base và e5-large. Pha U chạy đủ bộ chính sách của C3 trên chính
khoá SRP đó, cùng seed, cùng overlay, cùng dòng truy vấn với các lần chạy placement học. Kết quả cho biết ba điều: giữ đường
cũ có làm kém đi trên SRP không (H24a, H24b); drain còn hơn không migrate bao nhiêu (H24c); và lợi ích của đường cũ có nhỏ
hơn trên SRP như Mục 6.3.4 của bản thảo đang lập luận hay không (H24d đến H24f, với phần mất đường là cơ chế). Dù kết quả
theo hướng nào, câu "remains open" ở Mục 6.3.4 được thay bằng số.

**C và H22.** Đúng 20 ô và đúng cấu hình của đợt 11, trên 10 seed chưa dùng, với ngưỡng đặt từ đợt 11. Nếu đạt, tóm tắt và
Mục 6.3.3 được viết là "xác nhận trong một lần nhân bản có đăng ký trước" thay cho "thăm dò". Đây là nhân bản trên cùng
corpus và model, không phải bằng chứng trên dữ liệu mới.

**D và H23.** Bảng 7 và Bảng 10 có dòng drain cho cả bốn model đích trên code 100k. Mỗi job tự so các run cũ với file đợt
11 cùng seed, nên các dòng static, lazy, k1 của bảng không đổi một số nào.

**F.** Số bản ghi sửa và keep-alive của drain so với static, và mức giảm của giữ riêng dưới churn và dưới lỗi 30% peer. Mục
6.4 của bản thảo hiện ghi "we did not repeat the churn runs with drain".

**B.** Một dòng tham chiếu cho Bảng 10: index hoàn chỉnh khi được hỏi cùng số peer với hai epoch, trên đúng các query của
bảng. Bản v6 hiện lấy số này từ lưới placement (tập query và seed khác).

**O.** Cùng khoá, cùng seed, chỉ đổi overlay từ 50.000 xuống 5.000 peer. Cho biết thứ tự giữa khoá học, khoá ngẫu nhiên đã
trừ tâm và SRP gốc có giữ nguyên khi mỗi peer giữ khoảng 20 object hay không, và quy tắc qf có còn đoán đúng không.

## Chạy thử

Đã chạy thử trên dữ liệu giả của đợt 11, và cho analyze đọc số thật của các đợt trước ở những chỗ có sẵn:

- **Analyze trên số thật.** Đổi tên file thật của đợt trước thành tên file của đợt 14 rồi cho `analyze_r14.py` đọc:
  - 100 file migrate tới khi xong của đợt 11 (seed 26 đến 35) làm pha C: tính lại đúng các khoảng của bản thảo (drain hơn
    rebuild 14,5 đến 26,3; hơn lazy+bg 1,6 đến 7,9 về diện tích và 6,2 đến 14,4 về rerank; hơn static 16,3 đến 28,9; hơn bg
    8,7 đến 16,0; so với full từ −6,6 đến +5,6; byte đỉnh 1,72 đến 2,80 lần so với 1,36 đến 1,90 của rebuild; lượt xong 52
    đến 77% của T so với 28 đến 50% của lazy+bg). Trên chính số đợt 11, cả 100 tiêu chí của H22 đều đạt; điều này là hiển
    nhiên vì ngưỡng đặt từ đó, và chỉ cho thấy analyze chấm đúng.
  - 10 file dòng của đợt 13 (bge-base) làm pha D: bảng in ra trùng Bảng 10 của bản thảo (drain: giữ riêng 50,4, rerank
    trên dòng 65,3, payload 3,0, dual cuối 37,3%, record đỉnh 137,3%, byte đỉnh 796) và trùng các hiệu của báo cáo đợt 13
    (drain − k1 +1,42 và +5,83).
  - 15 file SRP và 15 file placement học của đợt 8 (seed 6 đến 10, chưa có drain) làm pha U và phía "học": bảng hiệu in
    đúng +3,56 và +1,08 (k1 − lazy, giữ riêng) của Mục 6.3.4, và phần mô tả in hiệu của hiệu cho k1 − lazy ghi ở
    `PREREG_round14.md`. Các tiêu chí H24 khi đó ghi `KHÔNG ĐẠT` vì thiếu run drain, đúng như thiết kế.
  - 9 file churn của đợt 11 làm pha F: tỉ số của k1 so với static là 1,151 đến 1,178 (bản ghi sửa) và 1,156 đến 1,186
    (keep-alive). Gộp với đợt 9, Mục 6.5 của bản v6 ghi 15,1 đến 18,1% và 15,6 đến 19,1%.
  - 15 file `probeP11` của code 100k cho phía 50.000 peer của pha O: in đúng các số của Bảng S27.
- **Cả `run_round14.sh` trên dữ liệu giả** (25 job: R 1, U 4, C 8, D 6, F 2, B 2, O 2; overlay 3.000 và 1.500 peer, dòng
  600 và 300 lượt): mọi job thoát mã 0.
  - Pha R: 1.923 giá trị trùng lượt chạy thử của đợt 13, đủ 10/10 run.
  - Pha D: 4/4 file có file cũ trùng lượt chạy thử của đợt 11 ở 6.808 giá trị; 2 file của một model không có file cũ được
    ghi là "không có file cũ để so".
  - Pha F: 2/2 file trùng file churn chạy thử của đợt 11 ở 4.362 giá trị, tức thêm lazy+keep và drain vào
    `--churn-policies` không đổi số nào của năm chính sách cũ.
  - Pha B: index native ở T = 16 trùng điểm (L = 5, T = 16) của lưới placement; cùng 4 file pha D và F có file
    `probeP11` chạy thử là 5/5 file `KHỚP`.
  - Pha U: 4/4 file ghi `e1_place = u`, không cap; cả 7 chính sách chạy, drain không retire lần nào (30/30 run có drain
    trên mọi pha).
  - Pha C: 192/192 checkpoint sau lượt xong trùng full, 56/56 checkpoint của rebuild trước lượt xong trùng static.
  - Pha O (300 peer so với 3.000 peer): 50/50 thống kê bit trùng file `probeP11` chạy thử.
- **Chạy tiếp và khoá.** `SKIP_DONE=1` trên thư mục đã chạy xong: bỏ qua 25/25 job, analyze cho lại đúng kết quả cũ. Khi
  `run.pid` trỏ tới một tiến trình còn sống, lần gọi thứ hai dừng với mã 1 và không đụng tới danh sách job; khi `run.pid`
  trỏ tới tiến trình đã chết, script chạy bình thường và xoá khoá khi xong.
- **Dry run với cấu hình thật** (python giả, tên file thật của các đợt trước): 185 job (R và U 21, C 100, D 30, F 9, B 10,
  O 15). So từng tham số với lệnh thật trong log của các đợt trước: lệnh pha C chỉ khác lệnh của đợt 11 ở seed, danh
  sách chính sách, `--check-10` và `--out`; lệnh pha D chỉ khác lệnh pha D của đợt 13 ở model và tên file; lệnh pha F chỉ
  khác lệnh churn của đợt 11 ở `--churn-policies`, `--check-prev` và `--out`; lệnh pha O chỉ khác lệnh placement của đợt
  11 ở `--nodes`, `--variants` và `--out`.
- `analyze_r14.py` biên dịch được với Python 3.11.

Trừ mục dùng số thật, số ở lượt chạy thử không có ý nghĩa, vì dữ liệu giả không phản ánh dữ liệu thật.

## Các bước

**Trên laptop:**

```bash
cd Evo_Engram
git checkout main && git pull
git log --oneline -1                     # phải là: 28c15d0 evo: dot 13, qf trien khai duoc, ...
git am ~/Downloads/0001-evo-dot-14*.patch
sha256sum -c evo/SHA256SUMS_round14      # 12 dòng OK (máy Mac: shasum -a 256 -c ...)
git tag -a evo-r14-prereg -m "dot 14: C3 tren khoa SRP goc, xac nhan drain tren seed moi, drain tren dong cho moi model"
git push origin main --tags
```

**Trên server** (mọi lệnh chạy trong thư mục repo):

```bash
cd ~/Evo_Engram
git status --short | grep -v '^??'       # không in gì
git fetch origin --tags && git checkout evo-r14-prereg
git describe --tags                      # evo-r14-prereg
sha256sum -c evo/SHA256SUMS_round14
ls probeV13_code100kfq_bgebase_s{26..35}_cap16.json | wc -l                        # 10 (đợt 13)
ls probeV11_code100kfq_{e5large,arctic,minilm}_s{26..35}_cap16.json | wc -l        # 30 (đợt 11)
ls probeV11C_code100kfq_{bgebase,e5large,arctic}_s{26..28}_cap16.json | wc -l      # 9 (đợt 11)
ls probeP11_code100kfq_{bgebase,e5large,arctic,m0,minilm}_s{26..28}.json | wc -l   # 15 (đợt 11)
ls probeQ13_A11_code100kfq_*.json | wc -l                                          # 15 (đợt 13)
[ -f venv/bin/activate ] && source venv/bin/activate
tmux new -s round14 -d "bash ~/Evo_Engram/evo/run_round14.sh"
```

Thiếu file của đợt trước nào thì job tương ứng vẫn chạy nhưng không tự so, và dòng `THIẾU` nằm trong
`evo/r14_logs/jobs.log`; analyze ghi số file không có file cũ để so. Riêng H24d đến H24f của bge-base cần 10 file
`probeV13_code100kfq_bgebase_*` của đợt 13.

Muốn có H24 và H22 trước rồi mới chạy phần còn lại:

```bash
tmux new -s round14 -d "PHASES='R U C' bash ~/Evo_Engram/evo/run_round14.sh"
# khi xong:
tmux new -s round14b -d "PHASES='D F B O' bash ~/Evo_Engram/evo/run_round14.sh"
```

Nếu phiên tmux bị ngắt giữa chừng, chạy lại với `SKIP_DONE=1` (giữ nguyên `PHASES` nếu có):

```bash
tmux new -s round14 -d "SKIP_DONE=1 bash ~/Evo_Engram/evo/run_round14.sh"
```

**Kiểm trong lúc chạy.**

1. Khoảng 10 giây sau:

   ```bash
   head -8 evo/r14_logs/jobs.log
   ```

   Phải có `NCPU=8  P=4`, `numpy ...`, `HEAD = tag evo-r14-prereg`, và dòng
   `đợt 14: 21 job ở R, U; 100 ở C; 30 ở D; 9 ở F; 10 ở B; 15 ở O; bỏ qua 0 job đã có file. P=4`; không có `DỪNG` hay
   `THIẾU`.

2. Sau khoảng 15 phút, job hồi quy xong:

   ```bash
   grep ">>>" evo/r14_logs/r14_rep.log
   ```

   Phải có một dòng `so với lượt cũ (...): ... giá trị, KHỚP` và dòng `rerun_prev: lượt mới có đủ 10/10 run của lượt cũ`.
   Nếu có `LỆCH`, dừng lại và báo em: khi đó môi trường không cho lại số của đợt 13.

3. Khi pha D bắt đầu có job xong (sau khoảng 3 giờ):

   ```bash
   grep -H "so với lượt cũ\|    lệch:" evo/r14_logs/d14_*.log
   ```

   Mỗi job một dòng kết thúc bằng `KHỚP`.

4. Tiến độ, lỗi và kết quả tạm, xem lúc nào cũng được:

   ```bash
   grep -c "mã thoát" evo/r14_logs/jobs.log         # số job đã xong, trên 185
   grep "mã thoát [1-9]" evo/r14_logs/jobs.log      # job lỗi, phải không in gì
   tail -3 evo/r14_logs/jobs.log
   python3 evo/analyze_r14.py > /tmp/r14_tam.txt; sed -n '/^TÓM TẮT/,/Tổng:/p' /tmp/r14_tam.txt
   ```

   Ở kết quả tạm, ô chưa đủ seed được ghi `KHÔNG ĐẠT ... (THIẾU SEED ...)`; chỉ đọc khi pha tương ứng đã xong.

**Khi xong** (dòng cuối `jobs.log` là `XONG ĐỢT 14 ...`):

```bash
cd ~/Evo_Engram
grep -c "mã thoát" evo/r14_logs/jobs.log         # 185
grep "mã thoát [1-9]" evo/r14_logs/jobs.log      # không in gì
sed -n '/^TÓM TẮT/,/Tổng:/p' evo/round14_all.txt
sed -n '/^Tự kiểm/,/   số file/p' evo/round14_all.txt
tar czf ~/evo_round14_results.tar.gz probeV14*.json probeVR14_*.json probeP14_*.json evo/r14_logs evo/round14_all.txt
tar tzf ~/evo_round14_results.tar.gz | grep -c json   # 185
sha256sum ~/evo_round14_results.tar.gz
```

Phần tự kiểm phải cho: pha R `KHỚP`, đủ 10/10 run của lượt cũ; pha D 30/30 file `KHỚP` với đợt 11; pha F 9/9 file `KHỚP`
với file churn của đợt 11; placement trong 11 so với `probeP11` 21/21 file `KHỚP` (9 của D, 9 của F, 3 của B); cách đặt
record E1 đúng ở 20/20 và 149/149 file; drain không retire ở mọi run; pha C trùng full sau lượt xong và trùng static trước
khi rebuild xong ở mọi checkpoint; thống kê bit của pha O trùng `probeP11` ở mọi giá trị; số file U 20/20, C 100/100, D
30/30, F 9/9, B 10/10, O 15/15, R 1/1.

Lấy file về laptop (chạy trên laptop, một đích duy nhất):

```bash
scp research@103.67.203.71:~/evo_round14_results.tar.gz ~/Downloads/
```
