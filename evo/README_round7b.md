# Đợt 7b: thăm dò tiếp sau đợt 7

Đợt 7 cho ba kết quả:

- **C1 (mô hình dị hướng) đạt.** Spearman giữa bucket dự đoán và tải của 1% peer nóng nhất là −0,85 trên 12 cặp
  (dataset, model).
- **C2 (placement học) đạt.** So ở cùng số record phải chấm, ITQ hơn SRP của bài ở 3 trên 4 không gian nhúng.
  Record tối đa mỗi peer giảm 4 đến 22 lần.
- **C3 (verify-then-retire) mới đạt một phần.** lazyD không bao giờ kém static. Nếu cùng số record công bố,
  lazyV1 hơn bg ở cả ba model. Nhưng lazyV1 công bố ít hơn lazy 2,6 lần. Vì vậy với query giữ riêng nó kém lazy:
  10 điểm ở e5-large, 5 điểm ở bge-base.

Đợt 7b trả lời bốn câu hỏi còn lại. Vẫn là pilot chưa đăng ký trước.

**A. Cùng ngân sách nhúng lại với lazy, migrate an toàn có hơn lazy không?** Có hai chính sách mới:

- `lazyVbg`: lazyV1 cộng migrate nền ngẫu nhiên, record nền retire ngay như bg.
- `lazyVbgD`: như lazyVbg, nhưng record nền cũng công bố dạng dual và chỉ retire sau xác nhận.

Tốc độ nền được chọn để tổng số record công bố bằng của lazy. Chạy trên code100kfq × 3 model × seed 3 4 5, Zipf 1
và đều.

**B. Khi epoch E1 dùng placement học, kết luận về migrate có đổi không?** Khoá SRP không trừ tâm của bài đạt recall
native cao nhờ peer nóng. Ở e5-large, mỗi truy vấn chấm từ 48% đến 97% corpus. Bài đã đề xuất placement học cho
epoch mới, nên phần migrate cũng phải chạy trên placement đó. Pha B dùng `--e1-place itq_q`: ITQ học trên S,
ngưỡng trung vị, query trừ tâm query. Chạy đủ các chính sách và thêm lazyD.

**C. Công thức góc chính xác có dự đoán độ lệch tải tốt hơn mô hình trường trung bình không?** Với siêu phẳng Gauss
qua gốc, hai vector góc θ trùng một bit với xác suất 1 − θ/π. Vậy chúng trùng bucket 16 bit với xác suất
E[(1 − θ/π)^16]. Mô hình trường trung bình chỉ dùng cosine trung bình. `10 --aniso-only 1` tính cả hai dự đoán trên
200.000 cặp document và đếm xác suất trùng thật trên toàn corpus, có và không trừ tâm. Chạy cho 12 cặp
(dataset, model).

**D. Chênh lệch nhỏ của `moved` ở đợt 7 đến từ đâu?** Đợt 7 có hai loại chênh:

- `11` lệch 1 giá trị `moved` so với 06 đợt 4, ở 4 trên 9 job. Lệch nằm trong 1 hoặc 2 cửa sổ 150 truy vấn, mỗi
  cửa sổ vài record. Mọi số chất lượng và số record mới đều trùng.
- `10` lệch số ứng viên 1/300 ở một job.

Pha D chạy lại 06 hiện tại cho e5-large seed 3 rồi so với cả file đợt 4 và `11` đợt 7. Nếu 06 hiện tại cũng lệch
đợt 4 nhưng trùng `11`, chênh lệch đến từ môi trường, chẳng hạn bản numpy xếp các điểm hoà khác đi, chứ không phải
từ `11`. Các log mới in phiên bản numpy.

## Thay đổi code (tag `evo-r7b-pilot`)

- **`11_probe_safe.py`.**
  - Thêm `--e1-place u|itq_q|pca_q|srp_cq`. Mặc định `u` giữ đúng từng số đợt 7.
  - Thêm hai chính sách `lazyVbg` và `lazyVbgD`.
  - Thêm số record các peer phải chấm mỗi truy vấn (`scan`).
  - Khi tự kiểm lệch, in tối đa 10 giá trị lệch.
  - Tự kiểm placement học với `probeP_*` đợt 7.
- **`10_probe_placement.py`.** Thêm `--aniso-only 1`, ghi `probeA_*.json`. Mặc định giữ nguyên đợt 7.
- **Thêm mới:** `analyze_r7b.py`, `run_round7b.sh`, `SHA256SUMS_round7b`, `README_round7b.md`.
- **Các file khác:** không đổi. `SHA256SUMS_round7` không còn khớp với `10` và `11` mới. Muốn chạy lại đợt 7 thì
  checkout tag `evo-r7-pilot`.

Đã chạy thử đủ 22 job trên dữ liệu giả. Dữ liệu giả có 2 model vì Arctic giả chỉ 48 chiều. Mọi job thoát mã 0.
Pha A khớp 06 ở 372 giá trị mỗi job. Pha B khớp `10` ở 5 giá trị mỗi job. Ở pha D, 06 hiện tại khớp file giả của
đợt 4 và khớp `11`.

## Các bước

**Trên laptop:**

```bash
cd Evo_Engram
git checkout main && git pull
git log --oneline -1                     # phải là: ... evo: dot 7, tham do placement hoc va migrate an toan ...
git am ~/Downloads/0001-evo-dot-7b*.patch
sha256sum -c evo/SHA256SUMS_round7b      # 9 dòng OK (máy Mac: shasum -a 256 -c ...)
git tag -a evo-r7b-pilot -m "dot 7b: migrate cung ngan sach, placement hoc, cong thuc goc"
git push origin main --tags
```

**Trên server:**

```bash
cd ~/Evo_Engram
git status --short | grep -v '^??'       # không in gì
git fetch origin --tags && git checkout evo-r7b-pilot
sha256sum -c evo/SHA256SUMS_round7b
ls probeP_code100kfq_{bgebase,e5large,arctic}_s{3,4,5}.json probeL_code100kfq_{bgebase,e5large,arctic}_s{3,4,5}_ku.json | wc -l   # 18
tmux new -s round7b -d "bash ~/Evo_Engram/evo/run_round7b.sh"
sleep 10; head -12 evo/r7b_logs/jobs.log
```

Mấy dòng đầu phải có `numpy ...`, `HEAD = tag evo-r7b-pilot`, không có `DỪNG`, và có dòng `đợt 7b: 31 job, P=4`.
31 job gồm 9 của pha A, 9 của B, 12 của C và 1 của D.

Thời gian ước tính trên node-dal-02, 4 job song song:

| pha | số job | mỗi job |
|---|---|---|
| B | 9 | khoảng 25 đến 30 phút |
| A | 9 | khoảng 20 phút |
| D | 1 | khoảng 20 phút |
| C | 12 | vài phút |

Tổng cộng khoảng 2 giờ.

**Khi xong** (dòng cuối `jobs.log` là `XONG ĐỢT 7b ...`):

```bash
cd ~/Evo_Engram
grep -c "mã thoát" evo/r7b_logs/jobs.log         # 31
grep "mã thoát [1-9]" evo/r7b_logs/jobs.log      # không in gì
tar czf ~/evo_round7b_results.tar.gz probeVB_*.json probeA_*.json probeL_code100kfq_e5large_s3_ku_r7b.json evo/r7b_logs evo/round7b_all.txt
tar tzf ~/evo_round7b_results.tar.gz | grep -c json   # 31
```

Gửi lại `evo/round7b_all.txt` và file tar.
