# Evo-Engram, đợt 4: đăng ký trước cho phần đánh giá xác nhận

Ngày ghi: 10/10/2026. File này được commit cùng tag `evo-confirm-v1` TRƯỚC khi chạy bất kỳ job nào của
đợt 4. Kết quả đánh giá theo đúng các tiêu chí dưới đây bằng `evo/analyze_prereg.py`, cũng commit cùng
tag. Mọi kết quả được báo cáo, kể cả khi không đạt.

## 1. Phần đóng băng

Thuật toán và tham số không đổi sau tag. Mã nguồn đóng băng là các file trong `SHA256SUMS_round4`.

- Query adapter A_split_norm. Định tuyến bằng khoá SRP của q1·W_r, với W_r là ridge M1 -> M0, chọn λ
  bằng 5-fold CV trên {1e-3, 1e-2, 1e-1, 1, 10}. Xếp hạng tại node bằng <q1·W_f^T, c_i> / n_i, với W_f là
  ridge M0 -> M1, c_i là vector tái tạo từ PQ code E0, n_i = ||c_i·W_f||.
- Gộp hai epoch PROB. Hiệu chỉnh cross-fit OLS trên top-30, phần dư làm độ lệch. Ngưỡng top-5 lấy bằng
  Monte Carlo 128 mẫu cố định. Khoá E1 là khoá SRP gốc (u). Mỗi epoch dùng đủ T = 8 probe.
- Học lại adapter trên phần đã migrate (ADR), với cùng quy trình.
- Lazy migration với pool rerank R = 20. Mọi record E0 trong pool được migrate. Migrate nền (bg) dùng
  cùng tổng số record.
- Overlay: L = 5, T = 8, K = 20, c = 16, κ = 30, r = 1. PQ E0 với m = 512, d_sub = 2. PQ E1 với
  m1 = d1 / 2, học trên mẫu S.

## 2. Dữ liệu, cặp mô hình, seed

- Bộ chính: `code100kfq`.
  - Corpus là CodeSearchNet Python 100.000 hàm, đúng corpus weak scaling của V-Engram.
  - Query là 500 câu đầu docstring chọn bằng seed 20261010 từ các hàm ở dòng 20.000 đến 99.999. Bộ
    query này chưa từng dùng trong lúc phát triển. 300 query đầu dùng để đánh giá, 200 query cuối dùng
    cho validation.
  - Overlay có 50.000 node, giữ tỉ lệ 2 object mỗi node như weak scaling của V-Engram.
  - Docstring được khôi phục bằng cách chạy lại quy tắc dựng corpus của V-Engram trên parquet gốc. Nếu
    phép tái lập không khớp toàn bộ 100.000 chuỗi thì bộ query vẫn dùng, docstring lấy theo ánh xạ
    chuỗi -> docstring, và điều này được ghi rõ trong báo cáo.
- Cặp mô hình. M0 là bge-large-en-v1.5 (chỉ mục cũ). M1 lấy một trong ba mô hình:
  - bge-base-en-v1.5;
  - e5-large-v2;
  - snowflake-arctic-embed-m-v1.5, cặp mới, chưa dùng trong lúc phát triển.
- Bộ phụ chỉ cho cặp mới: `code` (20k) và `scifact` (5.183), với query gốc, overlay 10.000 node.
- Seed 3, 4 và 5. Lúc phát triển đã dùng 20235956, 1 và 2.
- Cỡ mẫu học adapter khi đánh giá holdout. Mẫu học bị loại khỏi E0 và ground truth được tính lại.
  - code100kfq: 1.000, 2.000 và 5.000.
  - code: 1.000, 2.000 và 5.000.
  - scifact: 518 và 2.000.
- Cỡ mẫu S cho multi-epoch và lazy: 2.000 ở code100kfq (2%), 10% ở code và scifact.

## 3. Giả thuyết và tiêu chí đạt

Mỗi tiêu chí xét riêng cho từng cặp (bộ dữ liệu, M1). Đại lượng dùng là trung bình ghép cặp qua 3 seed.
R thuộc {5, 10, 15, 20, 30, 50, 100}. R = 5 chính là final R@5.

- **H1, tương thích chỉ mục cũ (holdout).** Với cỡ mẫu chính, min theo R của (A_split_norm − dual
  encoder) ≥ −5,0 điểm.
  - Cỡ mẫu chính là 5.000 ở code100kfq và code, 2.000 ở scifact.
  - Báo cáo thêm cỡ mẫu nhỏ nhất thoả tiêu chí.
  - Nhánh so sánh cố định là A_split_norm. Nhánh chọn trên validation chỉ dùng để tham khảo.
- **H2, gộp hai epoch.** Hai điều kiện:
  - ở f = 10%, final R@5 của AD_PROB lớn hơn AD_RRF;
  - rerank@20 của AD_PROB không giảm quá 1,0 điểm ở bất kỳ bước nào trên lưới f.
- **H3, học lại.** Ở f = 50%, final R@5 của ADR_PROB ≥ AD_PROB.
- **H4, lazy migration (Zipf s = 1, gộp PROB).** Hai điều kiện:
  - final R@5 trung bình trên dòng truy vấn của lazy lớn hơn bg cùng số record;
  - số payload mỗi truy vấn của lazy nhỏ hơn static.

## 4. Quy tắc

- Không thêm nhánh, tham số hay cách gộp mới dựa trên kết quả đợt 4.
- Job lỗi kỹ thuật thì chạy lại nguyên trạng.
- Nếu phải sửa lỗi code thì ghi diff và lý do vào file này, kèm commit mới. Mọi kết quả trước lần sửa
  vẫn được giữ.

## 5. Phần thăm dò, không thuộc đăng ký trước

Các phần sau báo cáo riêng, không dùng để kết luận xác nhận:

- workload paraphrase cho lazy migration;
- re-indexer có công suất và độ trễ (trust model chỉ authorized re-indexer được công bố record E1);
- mô phỏng chi phí end-to-end trong simulator SimPy của V-Engram;
- baseline MLP.
