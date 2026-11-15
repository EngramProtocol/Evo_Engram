# Đợt 15: C3 khi migrate tới khi xong trên khoá SRP gốc

Đợt 14 đo C3 trên khoá SRP gốc chỉ trên dòng 3.000 lượt của code 100k (H24). Bản thảo v7 vì thế ghi ở Limitations rằng
trên SRP, C3 mới được thử trên dòng có ngân sách cố định, chưa tới khi xong. Đợt này chạy đúng thí nghiệm migrate tới khi
xong của pha C đợt 14, chỉ đổi cách đặt record E1 sang khoá SRP gốc. Giả thuyết, ngưỡng và cách đọc nằm ở
`PREREG_round15.md`, chốt ở tag `evo-r15-prereg` trước khi chạy. Không cần GPU, không nhúng lại, không đổi số nào của các
đợt trước.

| pha | nội dung | số job | thời gian ước tính (P = 4) |
|---|---|---|---|
| R | kiểm hồi quy: chạy lại một job migrate tới khi xong của đợt 14 (code 20k, bge-base, seed 46); 13 run phải trùng từng số | 1 | 4 phút |
| V | migrate tới khi xong trên khoá SRP gốc cho ba model mà quy tắc qf chọn SRP: bge-base, e5-large, gte-base; code 20k (T = 1.500, 3.000) và SciFact (T = 400, 800); seed 46 đến 55; 8 chính sách (H25) | 60 | 3 đến 6 phút (code 20k), 1 đến 2 phút (SciFact) mỗi job; khoảng 45 phút |
| W | như V cho Arctic và MiniLM, là hai model mà quy tắc chọn placement học (thăm dò) | 40 | khoảng 30 phút |

Tổng 101 job, ra 101 file json. Với 4 job song song trên node-dal-02, ước tính 1 đến 2 giờ. Thứ tự chạy là R và V, rồi W:
phần có đăng ký trước xong trước.

Cơ sở của ước tính: job pha C của đợt 14 (cùng cấu hình, placement học) mất 143 đến 253 giây với code 20k và 47 đến 77 giây
với SciFact. Trên khoá SRP mỗi truy vấn chấm nhiều ứng viên hơn; ở đợt 14, mỗi run trên SRP của code 100k chậm hơn run
tương ứng trên placement học khoảng 1,3 đến 1,5 lần.

## Thay đổi code (tag `evo-r15-prereg`)

- **Không sửa bộ mô phỏng.** `11_probe_safe.py`, `10_probe_placement.py`, `me_common.py`, `rerun_prev.py`, `src/` giữ đúng
  như tag `evo-r14-prereg` (cùng SHA-256). Thứ đợt này cần đã có sẵn: khoá SRP gốc cho epoch mới (`--e1-place u`, không
  dùng `--e1-cap`) chạy được cùng `--bg-finish`.
- **Thêm mới:** `PREREG_round15.md`, `run_round15.sh`, `analyze_r15.py`, `README_round15.md`, `SHA256SUMS_round15`.
- `run_round15.sh` giữ hai điểm của driver đợt 14: `SKIP_DONE=1` để chạy tiếp sau khi bị ngắt, và khoá
  `evo/r15_logs/run.pid` để lần gọi thứ hai tự dừng khi lần đầu còn chạy.

## Đợt này trả lời điều gì

Dòng lệnh của pha V và W chỉ khác dòng lệnh pha C của đợt 14 ở ba chỗ: `--e1-place u` thay cho `--e1-place itq_q
--e1-cap 16`, thêm `--check-06 none`, và tên file ra. Cùng seed 46 đến 55, nên cùng overlay, cùng mẫu S, cùng query giữ
riêng và cùng dòng truy vấn với các lần chạy placement học đã có. Mỗi ô vì thế có hai phía ghép cặp theo seed.

- **H25a, H25b.** Trên khoá SRP, drain có còn hơn rebuild và hơn không migrate cho tới khi xong không. Nếu đạt, vế "on the
  fixed-budget stream only, not to completion" ở Limitations của bản thảo được bỏ.
- **H25c đến H25e.** Phần lợi của việc giữ đường cũ so với retire lúc publish có nhỏ hơn trên SRP khi migrate tới khi xong
  không, với phần mất đường là cơ chế. Đây là điều kiện thứ nhất của Mục 6.3.4, lần này cho thí nghiệm tới khi xong.
- **H25f.** Với e5-large và gte-base, là hai không gian tập trung mạnh, em dự đoán retire lúc publish kèm nền (lazy+bg)
  không kém drain trên SRP. Nếu đạt, bài đổi khuyến nghị: drain cho placement học, lazy+bg là đủ trên khoá SRP ở không
  gian tập trung mạnh. Đây là kết quả có thể không thuận cho drain; nó thu hẹp phạm vi của C3 về đúng placement mặc định
  của bài, và khớp với lập luận của Mục 6.3.4.
- **Thăm dò.** Bảng mọi chính sách trên SRP cạnh placement học (E1); so ở cùng tiến độ migrate (E2) và ở cùng cỡ tốc độ
  (E3), để tách phần do lazy+bg xong sớm hơn; Arctic và MiniLM trên SRP (E4); quan hệ với qf trên 10 cặp (E5).

## Chạy thử

- **Analyze trên số thật.** Lấy 100 file pha C của đợt 14 làm phía placement học, và lấy 100 file migrate tới khi xong của
  đợt 11 (seed 26 đến 35, cũng là placement học) đổi tên thành file SRP của seed 46 đến 55. Khi đó:
  - bảng của ô code 20k, bge-base, T = 1.500 ở phía "SRP" in lại đúng Bảng S9 của bản thảo (static 52,9; rebuild 54,8; bg
    61,6; lazy 62,4; lazy+bg 67,0; k1 70,2; drain 70,5; full 72,0; byte đỉnh của drain 2,38 lần; drain xong ở 75% của T);
  - H25a và H25b đạt 12/12, còn H25c đến H25f gần như không đạt (25 trên 68 tiêu chí), đúng như phải thế khi cả hai phía
    đều là placement học: hiệu của hiệu nằm quanh 0. Analyze vì vậy không tự cho đạt;
  - tự kiểm báo đúng các chỗ sai cố ý: 0/100 file ghi `e1_place = u`, và tham số lẫn dòng truy vấn không trùng file cùng
    tên của đợt 14.
- **Chấm lại độc lập.** Một script viết riêng tính lại cả 68 tiêu chí trên bộ file nói trên: cùng kết luận ở 68/68 tiêu
  chí; số trùng tới hai chữ số thập phân, trừ hai cận KTC lệch 0,01 do bảng t làm tròn khác nhau.
- **Cả `run_round15.sh` trên dữ liệu giả** (21 job: R 1, V 12, W 8; overlay 1.500 peer, dòng 600 và 300 lượt, seed 46 và
  47), với phía placement học sinh bằng `run_round14.sh` trên cùng dữ liệu giả: mọi job thoát mã 0.
  - Pha R: 2.521 giá trị trùng lượt chạy thử của đợt 14, đủ 13/13 run.
  - 20/20 file ghi `e1_place = u`, không cap. So với file placement học cùng ô, cùng seed: tham số trùng (trừ cách đặt
    record) ở 20/20, dòng truy vấn trùng ở 20/20, N, |S| và tên các run trùng ở 20/20.
  - Drain không retire ở 40/40 run; 468/468 checkpoint sau lượt xong trùng full; 140/140 checkpoint của rebuild trước
    lượt xong trùng static.
- **Chạy tiếp, khoá và kiểm file.** `SKIP_DONE=1` trên thư mục đã chạy xong: bỏ qua 21/21 job, analyze cho lại đúng kết
  quả cũ. Khi `run.pid` trỏ tới một tiến trình còn sống, lần gọi thứ hai dừng với mã 1; khi nó trỏ tới tiến trình đã chết,
  script chạy bình thường và xoá khoá khi xong. Sửa một file có trong `SHA256SUMS_round15` thì script dừng trước khi chạy
  job nào.
- **Dry run với cấu hình thật** (python giả): 101 job (R 1, V 60, W 40). Dòng lệnh pha V so với dòng lệnh thật của pha C
  đợt 14 trong log server chỉ khác ở `--e1-place`, `--e1-cap`, `--check-06` và `--out`.
- `analyze_r15.py` biên dịch được với Python 3.11.

Số ở lượt chạy thử trên dữ liệu giả không có ý nghĩa, vì dữ liệu giả không phản ánh dữ liệu thật.

## Các bước

**Trên laptop:**

```bash
cd Evo_Engram
git checkout main && git pull
git log --oneline -1                     # phải là: fa53949 evo: dot 14, C3 tren khoa SRP goc, ...
git am ~/Downloads/0001-evo-dot-15*.patch
sha256sum -c evo/SHA256SUMS_round15      # 12 dòng OK (máy Mac: shasum -a 256 -c ...)
git tag -a evo-r15-prereg -m "dot 15: C3 khi migrate toi khi xong tren khoa SRP goc"
git push origin main --tags
```

**Trên server** (mọi lệnh chạy trong thư mục repo):

```bash
cd ~/Evo_Engram
git status --short | grep -v '^??'       # không in gì
git fetch origin --tags && git checkout evo-r15-prereg
git describe --tags                      # evo-r15-prereg
sha256sum -c evo/SHA256SUMS_round15
ls probeV14F_{code,scifact}_{bgebase,e5large,gtebase,arctic,minilm}_s{46..55}_cap16.json | wc -l   # 100 (đợt 14)
[ -f venv/bin/activate ] && source venv/bin/activate
tmux new -s round15 -d "bash ~/Evo_Engram/evo/run_round15.sh"
```

Thiếu file nào của đợt 14 thì job tương ứng vẫn chạy, nhưng H25c đến H25e của ô đó sẽ thiếu seed, và dòng `THIẾU` nằm
trong `evo/r15_logs/jobs.log`.

Nếu phiên tmux bị ngắt giữa chừng, chạy lại với `SKIP_DONE=1`:

```bash
tmux new -s round15 -d "SKIP_DONE=1 bash ~/Evo_Engram/evo/run_round15.sh"
```

**Kiểm trong lúc chạy.**

1. Khoảng 10 giây sau:

   ```bash
   head -8 evo/r15_logs/jobs.log
   ```

   Phải có `NCPU=8  P=4`, `numpy ...`, `HEAD = tag evo-r15-prereg`, và dòng
   `đợt 15: 61 job ở R, V; 40 ở W; bỏ qua 0 job đã có file. P=4`; không có `DỪNG` hay `THIẾU`.

2. Sau khoảng 5 phút, job hồi quy xong:

   ```bash
   grep ">>>" evo/r15_logs/r15_rep.log
   ```

   Phải có một dòng `so với lượt cũ (...): ... giá trị, KHỚP` và dòng `rerun_prev: lượt mới có đủ 13/13 run của lượt cũ`.
   Nếu có `LỆCH`, dừng lại và báo em: khi đó môi trường không cho lại số của đợt 14.

3. Tiến độ, lỗi và kết quả tạm, xem lúc nào cũng được:

   ```bash
   grep -c "mã thoát" evo/r15_logs/jobs.log         # số job đã xong, trên 101
   grep "mã thoát [1-9]" evo/r15_logs/jobs.log      # job lỗi, phải không in gì
   tail -3 evo/r15_logs/jobs.log
   python3 evo/analyze_r15.py > /tmp/r15_tam.txt; sed -n '/^TÓM TẮT/,/Tổng:/p' /tmp/r15_tam.txt
   ```

   Ở kết quả tạm, ô chưa đủ seed được ghi `KHÔNG ĐẠT ... (THIẾU SEED ...)`; chỉ đọc khi pha V đã xong.

**Khi xong** (dòng cuối `jobs.log` là `XONG ĐỢT 15 ...`):

```bash
cd ~/Evo_Engram
grep -c "mã thoát" evo/r15_logs/jobs.log         # 101
grep "mã thoát [1-9]" evo/r15_logs/jobs.log      # không in gì
sed -n '/^TÓM TẮT/,/Tổng:/p' evo/round15_all.txt
sed -n '/^Tự kiểm/,/   số file/p' evo/round15_all.txt
tar czf ~/evo_round15_results.tar.gz probeV15U_*.json probeVR15_*.json evo/r15_logs evo/round15_all.txt
tar tzf ~/evo_round15_results.tar.gz | grep -c json   # 101
sha256sum ~/evo_round15_results.tar.gz
```

Phần tự kiểm phải cho: pha R `KHỚP`, đủ 13/13 run của lượt cũ; 100/100 file ghi `e1_place = u`, không cap; so với file
placement học cùng ô, cùng seed: 100/100 file có file để so, và tham số, dòng truy vấn, N, |S|, tên các run đều trùng ở
100/100; drain không retire ở mọi run; mọi checkpoint sau lượt xong trùng full và rebuild trước lượt xong trùng static; số
file V 60/60, W 40/40, R 1/1, file placement học của đợt 14 100/100.

Lấy file về laptop (chạy trên laptop, một đích duy nhất):

```bash
scp <server>:~/evo_round15_results.tar.gz ~/Downloads/
```
