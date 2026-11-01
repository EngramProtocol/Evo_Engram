# Evo-Engram, đợt 10: đăng ký trước cho placement có giới hạn tải (C2) và C3 trên placement đó, kèm kế hoạch phân tích phần migrate tới khi xong

Ngày ghi: 1/11/2026. File này được commit cùng tag `evo-r10-prereg` TRƯỚC khi chạy bất kỳ job nào của đợt 10. Kết quả
được chấm bằng `evo/analyze_r10.py`, cũng commit cùng tag. Mọi kết quả đều được báo cáo, kể cả khi không đạt. Lúc ghi
file này thầy chưa duyệt; nếu sau khi xem kết quả thầy đổi ngưỡng hay định nghĩa, phần thay đổi được báo cáo là thăm dò.

Đợt 8 xác nhận C1, C3 và phần recall của C2. Tiêu chí tải của C2 (H2) không đạt ở Arctic. Đợt 9 tìm ra nguồn: một cụm
khoảng 1.270 object nằm lệch khỏi tâm corpus, mà ITQ gán hàng trăm đến hơn một nghìn object của nó cùng một khoá ở mỗi
bảng, nên cả cụm dồn vào một peer; dùng nhiều thành phần chính hơn không sửa được. Đợt 9 cũng cho thấy lượng object dual
của lazyVbgD vẫn tăng tới cuối dòng, nên đỉnh lưu trữ chưa đo được. Đợt 10 làm hai việc:

1. Thêm giới hạn tải vào placement học, kiểm lại tiêu chí của H2 (H9) và kiểm lại C3 trên placement mới (H10), đều trên
   seed chưa dùng ở đợt nào.
2. Cho migrate chạy tới khi xong để đo đỉnh lưu trữ, thời điểm gỡ được index cũ, và chất lượng trong lúc migrate so với
   dựng lại ở nền. Phần này là thăm dò, với đại lượng chính chốt trước ở mục 3.

## 1. Phần đóng băng

- Mã nguồn đóng băng là các file trong `SHA256SUMS_round10`. Khi tắt các tính năng mới (mặc định), mọi chính sách và biến
  thể cũ cho đúng từng số đợt 8 và 9; pha R kiểm lại điều này trên dữ liệu thật.
- Overlay, tra cứu, adapter, gộp PROB, placement itq_q và định nghĩa các chính sách cũ giữ như `PREREG_round8.md` mục 1.
- **Placement có giới hạn tải** (`cap_place` trong `10_probe_placement.py`, dùng chung cho `11_probe_safe.py`):
  - Ở mỗi bảng, mỗi peer nhận tối đa c = ceil(m · N / số node) record, tức m lần mức trung bình của một bảng.
  - Object đến theo một thứ tự ngẫu nhiên cố định theo seed. Trước hết mỗi peer nhận các record mà nó là peer XOR-gần khoá
    nhất, theo thứ tự đến, tới khi đủ c. Record bị tràn, cũng theo thứ tự đến, đi tới peer đầu tiên còn chỗ trong K = 20
    peer XOR-gần khoá nhất, xếp theo khoảng cách; nếu cả K peer đều đầy thì tới peer ít tải nhất trong K peer đó.
  - Truy vấn vốn hỏi đủ K = 20 peer gần nhất của mỗi khoá probe, nên khoá, ngưỡng, định tuyến và số peer phải hỏi không
    đổi; chỉ vị trí record đổi.
  - **Cấu hình chính: itq_q+cap16**, tức m = 16, là 32 record mỗi peer mỗi bảng ở code100kfq. Em chọn mức này trước khi
    chạy: ở đợt 8, tải p99 của itq_q là 49 đến 51 record mỗi peer trên cả 5 bảng, tức khoảng 10 record mỗi bảng, còn
    điểm nóng là vài trăm đến hơn một nghìn record. Mức 32 nằm giữa hai mức đó. m = 8 và m = 32 chỉ chạy làm phân tích độ
    nhạy, không dùng để chọn cấu hình.
- **Seed mới:** 16, 17, 18 cho placement; 16 đến 25 cho C3 và cho phần migrate tới khi xong.

## 2. Giả thuyết và tiêu chí đạt

Khoảng tin cậy 95% lấy theo phân phối t trên hiệu ghép cặp qua seed. Với các giả thuyết theo không gian hay model, tiêu
chí phải đạt riêng cho từng không gian hay model.

- **H9, placement có giới hạn tải (C2), như H2.** code100kfq, 4 không gian {bge-base, e5-large, Arctic, M0}, seed 16 đến
  18. Với mỗi seed, c* là số ứng viên mỗi truy vấn của srp ở (L = 5, T = 8). F_v(c) là đường biên Pareto của final R@5
  theo số ứng viên của biến thể v trên 8 điểm (L, T), nội suy tuyến tính theo log số ứng viên; nếu c vượt mức lớn nhất
  của v thì lấy giá trị tốt nhất của v, không ngoại suy.
  - H9a: trung bình theo seed của F_itq_q+cap16(c*) − F_srp(c*) ít nhất 3 điểm, với Arctic, bge-base và M0.
  - H9b: ở L = 5, trung bình theo seed của tỉ lệ (record tối đa một peer của srp) / (của itq_q+cap16) ít nhất 3, với cả
    bốn không gian.
- **H10, C3 trên placement có giới hạn tải, như H3 đến H5.** code100kfq, placement E1 itq_q+cap16 (`--e1-place itq_q
  --e1-cap 16`), 3 model {bge-base, e5-large, Arctic}, seed 16 đến 25, workload Zipf 1, dòng 3.000 lượt như đợt 8.
  - H10a, như H3: lazyVbgD − lazy về final R@5 trên query giữ riêng ở cuối dòng, cận dưới KTC lớn hơn 0.
  - H10b, như H4a: lazyVbgD − static về final giữ riêng, trung bình ít nhất 3 điểm.
  - H10c, như H4b: lazy − static về rerank@20 trên dòng truy vấn, cận trên KTC nhỏ hơn 0.
  - H10d, như H5: trung bình tỉ lệ object dual cuối dòng của lazyVbgD không quá 40%, và trung bình theo seed của
    (payload mỗi truy vấn của lazyVbgD) / (của lazy) không quá 1/3. Dòng dài đúng như đợt 8 nên tiêu chí payload áp dụng
    được.

Tổng cộng 19 tiêu chí: H9 có 7 (3 recall, 4 tải), H10 có 12 (4 loại × 3 model).

## 3. Phần thăm dò, kế hoạch phân tích chốt trước

Phần này không có ngưỡng. Các đại lượng chính được chốt trước để tránh chọn số sau khi xem kết quả.

- **E1. Placement trên seed mới (pha A).** srp, srp_c, itq_q, itq128_q, itq_q+cap8, itq_q+cap16, itq_q+cap32, tính theo
  đúng cách của H2, seed 16 đến 18:
  - H2 của itq_q có lặp lại không, nhất là tiêu chí tải ở Arctic;
  - itq128_q, biến thể đợt 9 thấy sát ngưỡng sau khi xem số, có đạt lại không;
  - H9 nhạy thế nào với mức trần; số record bị dời ở mỗi mức; tải p99, phần record của 1% peer, phần truy vấn đến peer
    nóng nhất; recall khi cùng số peer phải hỏi.
- **E2. C3 trên placement có giới hạn tải (pha B).** Workload đều; full; đếm ô như đợt 8; so với đợt 8 (không trần, seed
  6 đến 15) chỉ để tham khảo vì khác seed.
- **E3. Migrate tới khi xong (pha C).** Code 20k (dòng 3.000 lượt, T = 1.500 hoặc 3.000) và SciFact (dòng 800 lượt,
  T = 400 hoặc 800), overlay 10.000 node, S = 10%, 3 model, seed 16 đến 25, Zipf 1, placement itq_q, `--bg-finish`.
  - Với mỗi T, nền công bố theo lịch nguyên sao cho một mình nền xong trước lượt T. Khi mọi object đã có bản E1, index E0
    bị gỡ toàn bộ.
  - Chính sách: static, lazy, full (chạy một lần); bg, lazybg, rebuild, lazyVbgD, lazyVbgDc25 (mỗi T). rebuild là dựng
    lại ở nền theo cùng lịch, truy vấn dùng index cũ tới khi dựng xong rồi chuyển hẳn sang index mới. lazyVbgDc25 là
    lazyVbgD với trần 25% corpus cho số object dual.
  - Đại lượng chính:
    - lượt xong (t_done);
    - lưu trữ đỉnh và trung bình, tính bằng (record E0 còn hoạt động + record E1, kể cả bản đang dựng của rebuild) / N;
      dual đỉnh;
    - final giữ riêng ở các checkpoint, và trung bình của nó trên [0, T] tính bằng hình thang qua các checkpoint;
    - final và rerank trên dòng, payload mỗi truy vấn, trong [0, T);
    - các hiệu lazyVbgD − lazybg, lazyVbgD − rebuild, lazyVbgDc25 − lazyVbgD về trung bình final giữ riêng trên [0, T].
  - Tự kiểm: sau lượt xong, final giữ riêng của mọi chính sách có nền phải trùng full ở mọi checkpoint; trước lượt xong,
    rebuild phải trùng static.

## 4. Quy tắc

- Không thêm chính sách, tham số hay biến thể mới dựa trên kết quả đợt 10.
- Job lỗi kỹ thuật thì chạy lại nguyên trạng.
- Nếu phải sửa lỗi code thì ghi diff và lý do vào file này, kèm commit mới. Mọi kết quả trước lần sửa vẫn được giữ.
- Pha R chạy trước, trên dữ liệu thật:
  - `10_probe_placement.py` chạy lại Arctic, seed 6 với srp_c, itq_q và itq_q+cap1000000. srp_c và itq_q phải trùng từng
    số đợt 8 (`--check-prev`); itq_q+cap1000000 có mức trần đủ lớn để không peer nào tràn, nên phải trùng itq_q trong
    cùng file.
  - `11_probe_safe.py` chạy lại một job đợt 8 (bge-base, seed 6, itq_q) với `--e1-cap 1000000`: mọi run phải trùng từng số
    đợt 8 (`--check-prev`).
  - Nếu pha R lệch, toàn bộ đợt 10 chỉ còn giá trị thăm dò cho tới khi tìm ra nguyên nhân.
