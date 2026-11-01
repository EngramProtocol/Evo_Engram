# Đợt 10: placement có giới hạn tải, C3 trên placement đó, migrate tới khi xong

Đợt 9 tìm ra nguồn của điểm nóng ITQ ở Arctic và cho thấy lượng object dual vẫn tăng tới cuối dòng. Đợt 10 trả lời ba
câu hỏi. Hai câu đầu có giả thuyết đăng ký trước (`PREREG_round10.md`, tag `evo-r10-prereg`); câu thứ ba là thăm dò, với
đại lượng chính chốt trước.

1. **Giới hạn tải mỗi peer có gỡ được điểm nóng mà vẫn giữ lợi thế recall của placement học không?** Mỗi peer nhận tối
   đa 16 lần mức trung bình mỗi bảng; record tràn sang peer còn chỗ trong 20 peer gần khoá nhất, là những peer truy vấn
   vốn đã hỏi. H9, chấm như H2, trên seed mới 16 đến 18.
2. **C3 có giữ trên placement đó và trên seed mới không?** H10, chấm như H3 đến H5, seed 16 đến 25.
3. **Khi cho migrate chạy tới khi xong, lưu trữ lên đỉnh bao nhiêu, bao giờ gỡ được index cũ, và chất lượng trong lúc
   migrate so với dựng lại ở nền ra sao?** Có thêm một bản lazyVbgD với trần 25% corpus cho số object dual.

| pha | nội dung | số job |
|---|---|---|
| R | kiểm hồi quy: 10 chạy lại Arctic seed 6; 11 chạy lại job đợt 8 bge-base seed 6 với mức trần rất lớn; cả hai so từng số với đợt 8 | 2 |
| A | placement code100kfq, 4 không gian × seed 16 đến 18, biến thể srp, srp_c, itq_q, itq128_q, itq_q+cap8, itq_q+cap16, itq_q+cap32 | 12 |
| B | C3 trên itq_q+cap16, code100kfq, 3 model × seed 16 đến 25, chính sách static, lazy, lazyV1, lazyVbgD, full, Zipf 1 và đều | 30 |
| C | migrate tới khi xong: code 20k (dòng 3.000, T = 1.500 và 3.000) và SciFact (dòng 800, T = 400 và 800), 3 model × seed 16 đến 25, Zipf 1 | 60 |

Tổng cộng 104 job. Pha R và A chạy trước, vì pha B tự kiểm placement có giới hạn tải với file của pha A; sau đó B và C
chạy chung. `analyze_r10.py` in ĐẠT hoặc KHÔNG ĐẠT cho H9 và H10, rồi in phần thăm dò và phần tự kiểm.

## Thay đổi code (tag `evo-r10-prereg`)

- **`10_probe_placement.py`.** Thêm biến thể `<v>+cap<m>`: dùng lại khoá và định tuyến của v, chỉ đổi vị trí record theo
  giới hạn tải (hàm `cap_place`). Ghi thêm số record bị dời ở mỗi bảng. Biến thể cũ không đổi.
- **`11_probe_safe.py`.**
  - `--e1-cap m`: placement E1 có giới hạn tải, dùng đúng hàm của 10.
  - `--bg-finish T1,T2`: migrate tới khi xong. Nền công bố theo lịch nguyên sao cho một mình nền xong trước lượt T; khi
    mọi object đã có bản E1, index E0 bị gỡ toàn bộ.
  - Thêm chính sách `lazybg` (lazy cộng nền), `rebuild` (dựng lại ở nền, chuyển index khi xong), `lazyVbgDc<p>` (lazyVbgD
    với trần p% cho số object dual).
  - Đo thêm lưu trữ mỗi lượt và lượt xong.
  - Mặc định tắt; khi tắt, mọi chính sách cũ cho đúng từng số đợt 9.
- **Thêm mới:** `PREREG_round10.md`, `analyze_r10.py`, `run_round10.sh`, `SHA256SUMS_round10`, `README_round10.md`.

Đã chạy thử trên dữ liệu giả, so với code đợt 9 chạy trên cùng dữ liệu:

- 11 không bật tính năng mới, và 11 bật `--e1-cap 1000000`: đều trùng từng số ở 3.892 giá trị.
- 10 chạy lại srp_c và itq_q: trùng ở 242 giá trị; itq_q+cap1000000 trùng itq_q ở 116 giá trị.
- Placement có giới hạn tải trong 11 trùng biến thể cùng tên của 10 (tự kiểm index native ở f = 1). Hàm `cap_place`
  trùng một bản cài tuần tự viết riêng để kiểm, trên khoá tổng hợp.
- Ở chế độ migrate tới khi xong, sau lượt xong mọi chính sách có nền trùng full ở mọi checkpoint, và rebuild trùng static
  trước lượt xong: 178 trên 178 và 56 trên 56 checkpoint.
- Đủ 16 job của `run_round10.sh` với 2 model, ít seed và dòng ngắn: mọi job thoát mã 0, mọi phép tự kiểm KHỚP.
- Dữ liệu giả không phản ánh dữ liệu thật, nên ĐẠT hay KHÔNG ĐẠT ở lượt chạy thử không có ý nghĩa.

## Các bước

**Trên laptop:**

```bash
cd Evo_Engram
git checkout main && git pull
git log --oneline -1                     # phải là: 9c9fd5c evo: dot 9, churn va loi peer khi migrate, ...
git am ~/Downloads/0001-evo-dot-10*.patch
sha256sum -c evo/SHA256SUMS_round10      # 8 dòng OK (máy Mac: shasum -a 256 -c ...)
git tag -a evo-r10-prereg -m "dot 10: gioi han tai, C3 tren placement moi, migrate toi khi xong"
git push origin main --tags
```

**Trên server** (mọi lệnh chạy trong thư mục repo):

```bash
cd ~/Evo_Engram
git status --short | grep -v '^??'       # không in gì
git fetch origin --tags && git checkout evo-r10-prereg
git describe --tags                      # evo-r10-prereg
sha256sum -c evo/SHA256SUMS_round10
ls probeP_code100kfq_arctic_s6.json probeV8_code100kfq_bgebase_s6_itq_q.json   # hai file đợt 8 phải có
tmux new -s round10 -d "bash ~/Evo_Engram/evo/run_round10.sh"
```

Khoảng 10 giây sau, xem mấy dòng đầu của log:

```bash
head -12 evo/r10_logs/jobs.log
```

Mấy dòng này phải có `numpy ...`, `HEAD = tag evo-r10-prereg`, dòng `đợt 10: 104 job ...`, và không có `DỪNG`.

Thời gian ước tính trên node-dal-02, 4 job song song: khoảng 5 đến 6 giờ. Pha R xong trong khoảng 30 phút; khi đó kiểm:

```bash
grep -H "so với lượt cũ\|    lệch:" evo/r10_logs/r10_*.log
```

Lệnh này phải in đúng 2 dòng, mỗi job một dòng, cả hai kết thúc bằng `KHỚP`.

**Khi xong** (dòng cuối `jobs.log` là `XONG ĐỢT 10 ...`):

```bash
cd ~/Evo_Engram
grep -c "mã thoát" evo/r10_logs/jobs.log         # 104
grep "mã thoát [1-9]" evo/r10_logs/jobs.log      # không in gì
tar czf ~/evo_round10_results.tar.gz probePR10_*.json probeVR10_*.json probeP10_*.json probeV10_*.json probeV10F_*.json evo/r10_logs evo/round10_all.txt
tar tzf ~/evo_round10_results.tar.gz | grep -c json   # 104
```

Gửi lại file tar.
