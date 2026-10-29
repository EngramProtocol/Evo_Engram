# Evo-Engram, đợt 9: đăng ký trước cho C3 trên hai corpus mới, kèm kế hoạch phân tích phần thăm dò

Ngày ghi: 29/10/2026. File này được commit cùng tag `evo-r9-prereg` TRƯỚC khi chạy bất kỳ job nào của đợt 9. Kết quả
được chấm bằng `evo/analyze_r9.py`, cũng commit cùng tag. Mọi kết quả đều được báo cáo, kể cả khi không đạt.

Đợt 8 đã xác nhận C3 trên code100kfq với seed mới. Câu hỏi còn lại là C3 có giữ trên corpus khác không. Đợt 9 kiểm điều
đó trên code 20k và SciFact, hai corpus chưa từng dùng cho migrate trên placement học. Ngưỡng giữ đúng như H3, H4 của
đợt 8, để đây là phép kiểm tổng quát hoá chứ không phải đặt ngưỡng mới. Lúc ghi file này thầy chưa duyệt. Nếu sau khi xem
kết quả thầy đổi ngưỡng hay định nghĩa, phần thay đổi được báo cáo là thăm dò, không phải xác nhận.

## 1. Phần đóng băng

- Mã nguồn đóng băng là các file trong `SHA256SUMS_round9`. Khi tắt các tính năng mới (mặc định), mọi chính sách cũ cho
  đúng từng số đợt 8; pha R kiểm lại điều này trên dữ liệu thật.
- Overlay, tra cứu, adapter, gộp PROB, placement itq_q và định nghĩa các chính sách giữ như `PREREG_round8.md` mục 1.
  Thêm chính sách `mapkeep`, định nghĩa ở đầu `11_probe_safe.py`.
- **Code 20k và SciFact.**
  - Overlay 10.000 node, mẫu S bằng 10% corpus (2.000 và 518 object), như phần placement của đợt 7 và 8.
  - Dòng truy vấn dài 3.000 × N / 100.000 lượt, để phần corpus được migrate gần với code100kfq: 600 lượt cho code 20k,
    155 lượt cho SciFact. Vẫn 200 query trong dòng và 100 query giữ riêng. Checkpoint 0, 150, 300, 600 cho code 20k và
    0, 50, 100, 155 cho SciFact.
  - Lý do co dòng: đợt 4 chạy migrate trên hai corpus này với khoá của bài và dòng 3.000 lượt. Khi đó lazy migrate hết
    corpus trước cuối dòng (f cuối 100%), nên so ở cuối dòng không còn nghĩa.
  - Seed 6 đến 15. Chính sách như pha A của đợt 8, thêm mapkeep. Zipf 1 là workload chính, phân phối đều là phụ.

## 2. Giả thuyết và tiêu chí đạt

Có 6 cặp (corpus, model): 2 corpus × {bge-base, e5-large, Arctic}. Mỗi tiêu chí phải đạt riêng cho từng cặp. Khoảng tin
cậy 95% lấy theo phân phối t trên hiệu ghép cặp qua 10 seed. Workload Zipf 1.

- **H6, như H3.** lazyVbgD − lazy về final R@5 trên query giữ riêng ở cuối dòng: cận dưới khoảng tin cậy lớn hơn 0.
- **H7, như H4.** Đạt khi cả hai điều kiện đều thoả:
  - (a) lazyVbgD − static về final giữ riêng: trung bình ít nhất 3 điểm;
  - (b) lazy − static về rerank@20 trên dòng truy vấn: cận trên khoảng tin cậy nhỏ hơn 0.
- **H8, như phần payload của H5.** Trung bình theo seed của (payload tải mỗi truy vấn của lazyVbgD) / (của lazy) không
  quá 1/3. Phần dual cuối dòng của H5 không dùng ở đây vì nó phụ thuộc độ dài dòng, mà độ dài dòng đã được co theo cỡ
  corpus; nó chỉ được báo cáo như số thăm dò.

Tổng cộng 24 tiêu chí: H6, H7a, H7b, H8, mỗi loại 6.

## 3. Phần thăm dò, kế hoạch phân tích chốt trước

Phần này không có ngưỡng. Các đại lượng chính được chốt trước để tránh chọn số sau khi xem kết quả.

- **Churn và lỗi peer (pha A).** code100kfq, itq_q, Zipf 1, 3 model, seed 6 đến 10, chính sách static, lazy, lazyV1,
  lazyVbgD, full, mapall, mapkeep.
  - `ch`: phiên Weibull hình dạng 0,5, trung vị 120 phút như thí nghiệm churn của V-Engram; cả dòng ứng với 720 phút;
    sửa lười mỗi 60 phút, lần sửa đầu ở phút 30.
  - `fail`: 30% node hỏng cùng lúc ngay trước lượt 1.500, không sửa. 30% là mức hỏng lớn nhất V-Engram đã thử.
  - Đại lượng chính: final giữ riêng ở cuối dòng của từng chính sách, so với chính nó khi không churn cùng seed (đợt 8)
    và giữa các chính sách (lazyVbgD − lazy, − static, − mapkeep); phần corpus mất mọi đường tìm; số bản ghi được sửa và
    số keep-alive mỗi truy vấn. Riêng `fail`: thêm final giữ riêng ở lượt 1.500 và 2.000.
  - Giới hạn của mô hình: node thay thế giữ vị trí của node cũ trong không gian khoá (xem đầu `11_probe_safe.py`).
- **mapkeep (pha A, phần không churn).** code100kfq không churn, 3 model, seed 6 đến 15: lazyVbgD − mapkeep và mapkeep − mapall về final,
  rerank, gold trên query giữ riêng và trên dòng, kèm số peer và số record phải chấm mỗi truy vấn.
- **ITQ trên nhiều thành phần chính (pha D).** itq128_q và itq256_q so với srp, theo đúng cách tính của H2: hiệu final tại
  số ứng viên của srp ở L = 5, T = 8, và tỉ lệ record tối đa một peer ở L = 5. 4 không gian, seed 6 đến 8.
- **Chẩn đoán điểm nóng (pha E).** Cỡ nhóm khoá trùng hệt nhau ở từng bảng, và phần năng lượng nằm ngoài 63 thành phần
  chính của các object ở peer nóng nhất. 4 không gian, seed 6 đến 8.

## 4. Quy tắc

- Không thêm chính sách, tham số hay biến thể mới dựa trên kết quả đợt 9.
- Job lỗi kỹ thuật thì chạy lại nguyên trạng.
- Nếu phải sửa lỗi code thì ghi diff và lý do vào file này, kèm commit mới. Mọi kết quả trước lần sửa vẫn được giữ.
- Pha R chạy lại một job đợt 8 bằng code mới, và một job bật đường code churn mà không có node nào rời mạng; cả hai phải
  trùng từng số với đợt 8. Nếu pha R lệch, toàn bộ đợt 9 chỉ còn giá trị thăm dò cho tới khi tìm ra nguyên nhân.
