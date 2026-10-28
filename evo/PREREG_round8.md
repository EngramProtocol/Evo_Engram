# Evo-Engram, đợt 8: đăng ký trước cho phần đánh giá xác nhận

Ngày ghi: 28/10/2026. File này được commit cùng tag `evo-r8-prereg` TRƯỚC khi chạy bất kỳ job nào của đợt 8.
Kết quả được đánh giá theo đúng các tiêu chí dưới đây bằng `evo/analyze_r8.py`, cũng commit cùng tag. Mọi kết quả
đều được báo cáo, kể cả khi không đạt.

Giả thuyết và ngưỡng lấy từ báo cáo ngày 27/10/2026 gửi thầy (mục 7). Lúc ghi file này thầy chưa duyệt. Nếu sau khi
xem kết quả thầy đổi ngưỡng hay định nghĩa, phần thay đổi được báo cáo là thăm dò, không phải xác nhận.

## 1. Phần đóng băng

Thuật toán và tham số không đổi sau tag. Mã nguồn đóng băng là các file trong `SHA256SUMS_round8`.

- **Overlay và tra cứu như các đợt trước.** L = 5 bảng, T = 8 probe, K = 20 peer mỗi khoá, 16 bit đầu dùng để
  lật bit probe, κ = 30, pool rerank R = 20.
  - PQ E0 có m = 512.
  - PQ E1 có m1 = d1 / 2, học trên mẫu S.
  - Mẫu S là 2% corpus (2.000 object), đã nhúng lại bằng M1 và công bố ở E1 từ đầu.
- **Phía E0 dùng adapter A_split_norm, gộp hai epoch bằng PROB, hiệu chỉnh cross-fit**, như đợt 4 đến 7b.
- **Placement của epoch E1.**
  - Cấu hình chính là `itq_q`: trừ trung bình document trên S. ITQ được học trên 63 thành phần chính của S, 50 vòng
    lặp, mỗi bảng khởi tạo và hoán vị bit riêng. Mỗi bit có ngưỡng trung vị trên S. Query trừ trung bình query.
  - Cấu hình phụ là `u`, tức khoá SRP không trừ tâm của bài.
- **Chính sách migrate**, định nghĩa đúng như `11_probe_safe.py`:
  - static, lazy, bg (cùng số record với lazy);
  - lazyV1 (retire bản E0 sau 1 xác nhận native), bgV1;
  - lazyVbg, lazyVbgD.
    - Cả hai là lazyV1 cộng migrate nền, với tổng số record công bố bằng của lazy.
    - Với lazyVbg, record nền retire ngay.
    - Với lazyVbgD, record nền cũng công bố dạng dual và chỉ retire sau xác nhận.
  - full (dựng lại toàn bộ index).
  - mapall (map-and-republish kiểu FastFill).
  - Object dual dùng mã E1 ghi tại chỗ ở peer E0 (`--dual-score e1code`). Chúng không chiếm chỗ trong R record E0
    (`--dual-slots bonus`).
- **Dòng truy vấn.** 3.000 lượt trên 200 query của tập đánh giá, cộng 100 query giữ riêng. Zipf s = 1 là workload
  chính, phân phối đều là workload phụ. Rerank theo quy ước dòng truy vấn: record có điểm ADC native giữ điểm đó,
  record khác được tải payload và chấm cosine M1 thật.
- **Placement study (`10_probe_placement.py`).**
  - Biến thể: srp, srp_c, srp_cq, pca_q, itq_d, itq_q.
  - L thuộc {5, 10}, T thuộc {2, 4, 8, 16}. Ứng viên là record còn hoạt động ở các peer được hỏi.

## 2. Dữ liệu và seed

- **code100kfq**, overlay 50.000 node, ba model M1: bge-base-en-v1.5, e5-large-v2, snowflake-arctic-embed-m-v1.5.
  M0 là index cũ.
- **Seed mới.** Đợt 7 và 7b chỉ dùng seed 3, 4, 5.
  - Seed 6 đến 12 từng dùng ở đợt 6 cho bge-base với `09_sim_e2e.py`, nhưng chỉ cho lazy và bg, khoá E1 u. Seed đó
    chưa từng dùng với chính sách mới hay placement học.
  - Phần migrate trên placement học dùng seed 6 đến 15 (10 seed). Trên khoá của bài dùng seed 6 đến 10.
  - Placement study và mô hình dị hướng dùng seed 6, 7, 8.
- **Code 20k và SciFact** (overlay 10.000 node, S = 10%) chỉ dùng cho H1 và phần thăm dò của C2.

## 3. Giả thuyết và tiêu chí đạt

Với các giả thuyết theo model, tiêu chí phải đạt riêng cho từng model. Khoảng tin cậy 95% lấy theo phân phối t trên
hiệu ghép cặp theo seed.

- **H1, mô hình dị hướng.** Lấy 12 cặp gồm 3 dataset × {bge-base, e5-large, Arctic, M0}. Với mỗi cặp:
  - p là xác suất hai document ngẫu nhiên trùng bucket 16 bit, dự đoán bằng công thức góc E[(1 − θ/π)^16];
  - q là xác suất đó đếm thật trên toàn corpus;
  - t là phần tải của 1% peer nóng nhất với SRP ở L = 5.

  Cả ba đại lượng lấy trung bình qua seed 6 đến 8. Đạt khi:
  - tương quan hạng Spearman giữa p và t ít nhất 0,8;
  - trung bình |log10(p / q)| không quá 0,2.
- **H2, placement học (code100kfq).** Với mỗi seed, đặt c* là số ứng viên mỗi truy vấn của srp ở (L = 5, T = 8).
  - F_v(c) là đường biên Pareto của final R@5 theo số ứng viên của biến thể v, trên 8 điểm (L, T), nội suy tuyến
    tính theo log số ứng viên. Nếu c vượt mức lớn nhất của v thì lấy giá trị tốt nhất của v, không ngoại suy.
  - Đạt khi trung bình theo seed của F_itq_q(c*) − F_srp(c*) ít nhất 3 điểm, với Arctic, bge-base và M0.
  - Đồng thời, ở L = 5, trung bình theo seed của tỉ lệ (record tối đa một peer của srp) / (của itq_q) ít nhất 3, với
    cả bốn không gian, gồm cả e5-large.
- **H3, migrate an toàn hơn lazy cùng ngân sách.** Trên placement học, workload Zipf 1, lấy hiệu
  lazyVbgD − lazy của final R@5 trên query giữ riêng ở cuối dòng (t = 3.000). Đạt khi cận dưới khoảng tin cậy 95%
  qua seed 6 đến 15 lớn hơn 0.
- **H4, an toàn so với không migrate.** Cùng thiết lập với H3. Đạt khi cả hai điều kiện đều thoả:
  - (a) trung bình của lazyVbgD − static về final R@5 trên query giữ riêng ít nhất 3 điểm;
  - (b) lazy − static về rerank@20 trên dòng truy vấn có cận trên khoảng tin cậy 95% nhỏ hơn 0, tức lỗi của lazy
    lặp lại.
- **H5, chi phí.** Cùng thiết lập với H3. Đạt khi cả hai điều kiện đều thoả:
  - trung bình tỉ lệ object dual cuối dòng của lazyVbgD không quá 40% corpus;
  - trung bình theo seed của (payload tải mỗi truy vấn của lazyVbgD) / (của lazy) không quá 1/3.

## 4. Quy tắc

- Không thêm chính sách, tham số hay biến thể mới dựa trên kết quả đợt 8.
- Job lỗi kỹ thuật thì chạy lại nguyên trạng.
- Nếu phải sửa lỗi code thì ghi diff và lý do vào file này, kèm commit mới. Mọi kết quả trước lần sửa vẫn được giữ.
- Pha R chạy lại hai job của đợt 7b (`--check-prev`) để chắc code mới không đổi kết quả các chính sách cũ. Nếu pha R
  lệch, toàn bộ đợt 8 chỉ còn giá trị thăm dò cho tới khi tìm ra nguyên nhân.

## 5. Phần thăm dò, không thuộc đăng ký trước

- Khoá của bài (u) với mọi chính sách.
- Hai baseline full và mapall, và lazyVbg.
- Chỉ số gold (hàm gốc của query trong top-5).
- Workload đều.
- Code 20k và SciFact cho C2.
- Số record phải chấm mỗi truy vấn, và số object dual nhận từ phía E0.
