# Đợt 8: đánh giá xác nhận cho hướng mới

Đợt 7 và 7b là pilot, mỗi cấu hình 3 seed. Hai đợt này cho thấy ba đóng góp có thể giữ được:

- C1, mô hình dị hướng cho độ lệch tải của khoá SRP;
- C2, placement học theo epoch;
- C3, migrate an toàn kiểu verify-then-retire.

Đợt 8 kiểm lại cả ba trên seed mới, với giả thuyết và ngưỡng chốt trước trong `PREREG_round8.md`. File này commit
cùng tag `evo-r8-prereg` trước khi chạy. Đợt 8 cũng thêm hai baseline mà reviewer chắc chắn hỏi:

- `full`: dựng lại toàn bộ index;
- `mapall`: map-and-republish kiểu FastFill.

Giả thuyết lấy từ báo cáo ngày 27/10 gửi thầy. Lúc chạy thầy chưa duyệt. Nếu sau này thầy đổi ngưỡng, phần đổi được
báo cáo là thăm dò.

Các pha:

| pha | nội dung | số job |
|---|---|---|
| R | chạy lại 2 job đợt 7b bằng code mới, so từng số | 2 |
| A | migrate trên placement học itq_q, 3 model × seed 6 đến 15, 9 chính sách (H3, H4, H5) | 30 |
| B | như A với khoá của bài, seed 6 đến 10 (thăm dò) | 15 |
| C | placement study code100kfq × 4 không gian × seed 6 đến 8 (H2); code 20k và SciFact, L = 5 | 12 + 24 |
| D | mô hình dị hướng, 3 dataset × 4 không gian × seed 6 đến 8 (H1) | 36 |

Tổng cộng 119 job. `analyze_r8.py` in ĐẠT hoặc KHÔNG ĐẠT cho từng tiêu chí, rồi in phần thăm dò.

## Thay đổi code (tag `evo-r8-prereg`)

- **`11_probe_safe.py`.**
  - Thêm chính sách `full` và `mapall`.
  - Thêm `--check-prev FILE`, so từng số mọi run trùng tên với một lượt cũ.
  - Ghi thống kê index native ở f = 1 (`native_f1`) để đối chiếu với `10` sau khi chạy.
  - Các chính sách cũ giữ đúng từng số đợt 7b.
- **Thêm mới:** `PREREG_round8.md`, `analyze_r8.py`, `run_round8.sh`, `SHA256SUMS_round8`, `README_round8.md`.
- **Các file khác:** không đổi. `10_probe_placement.py` giữ nguyên như đợt 7b.

Đã chạy thử đủ 46 job trên dữ liệu giả, với 2 model, ít seed và Arctic thay bằng bge-base ở pha R. Mọi job thoát
mã 0. Pha R khớp đợt 7b ở 2.272 và 1.988 giá trị. Placement trong `11` khớp `10`. Dữ liệu giả gần đẳng hướng,
nên kết quả ĐẠT hay KHÔNG ĐẠT của lượt chạy thử không nói gì về dữ liệu thật.

## Các bước

**Trên laptop:**

```bash
cd Evo_Engram
git checkout main && git pull
git log --oneline -1                     # phải là: ... evo: dot 7b, migrate cung ngan sach voi lazy ...
git am ~/Downloads/0001-evo-dot-8*.patch
sha256sum -c evo/SHA256SUMS_round8       # 8 dòng OK (máy Mac: shasum -a 256 -c ...)
git tag -a evo-r8-prereg -m "dot 8: dang ky truoc, danh gia xac nhan"
git push origin main --tags
```

**Trên server:**

```bash
cd ~/Evo_Engram
git status --short | grep -v '^??'       # không in gì
git fetch origin --tags && git checkout evo-r8-prereg
sha256sum -c evo/SHA256SUMS_round8
ls probeVB_code100kfq_bgebase_s3_itq_q.json probeVB_code100kfq_arctic_s3_u.json probeP_code100kfq_bgebase_s3.json probeL_code100kfq_arctic_s3_ku.json   # đủ 4 file
tmux new -s round8 -d "bash ~/Evo_Engram/evo/run_round8.sh"
sleep 10; head -12 evo/r8_logs/jobs.log
```

Mấy dòng đầu phải có `numpy ...`, `HEAD = tag evo-r8-prereg`, không có `DỪNG`, và có dòng `đợt 8: 119 job, P=4`.

Thời gian ước tính trên node-dal-02, 4 job song song: khoảng 6 đến 7 giờ. Pha R chạy đầu tiên, khoảng 20 phút sau
khi bắt đầu đã có kết quả so từng số. Muốn biết sớm code có giữ đúng các chính sách cũ không:

```bash
grep -H ">>>\|    lệch:" evo/r8_logs/r_*.log
```

Lệnh này phải in 4 dòng `KHỚP`: hai dòng `so với lượt cũ`, một dòng `placement itq_q so với 10`, một dòng
`so với 06`.

**Khi xong** (dòng cuối `jobs.log` là `XONG ĐỢT 8 ...`):

```bash
cd ~/Evo_Engram
grep -c "mã thoát" evo/r8_logs/jobs.log         # 119
grep "mã thoát [1-9]" evo/r8_logs/jobs.log      # không in gì
tar czf ~/evo_round8_results.tar.gz probeVR_*.json probeV8_*.json probeP_*_s6.json probeP_*_s7.json probeP_*_s8.json probeA_*_s6.json probeA_*_s7.json probeA_*_s8.json evo/r8_logs evo/round8_all.txt
tar tzf ~/evo_round8_results.tar.gz | grep -c json   # 119
```

Gửi lại `evo/round8_all.txt` và file tar.
