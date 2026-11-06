# Evo-Engram, đợt 12: đăng ký trước cho phép xác minh mạnh hơn của C3 và quy tắc chọn placement theo qf của C1, C2

Ngày ghi: 6/11/2026. File này được commit cùng tag `evo-r12-prereg` TRƯỚC khi chạy bất kỳ job nào của đợt 12. Kết quả
được chấm bằng `evo/analyze_r12.py`, cũng commit cùng tag. Mọi kết quả đều được báo cáo, kể cả khi không đạt. Lúc ghi
file này thầy chưa duyệt đề xuất đợt 12 trong báo cáo đợt 11 (mục 13); nhóm quyết định chạy trước. Nếu sau khi xem kết quả
thầy đổi ngưỡng hay định nghĩa, phần thay đổi được báo cáo là thăm dò.

Đợt 11 để lại ba việc, đợt 12 làm cả ba:

1. **C3: retire sau một xác nhận kém giữ cả epoch cũ tới khi xong (H12a không đạt ở 12/12 ô).** Phân tích sau khi xem số
   cho thấy hai nguyên nhân. Một là pha 1: trong lúc cả hai epoch còn phục vụ, retire sau một lần thấy làm mất 2,2% đến
   9,3% vị trí top-5 thật và rerank trên dòng thấp hơn drain 3,0 đến 9,8 điểm. Hai là pha 2: chính sách xong sớm hơn thì
   gỡ E0 sớm hơn, nên sớm rơi về mức của full. Ngoài ra code đếm mọi lần thấy, kể cả khi cùng một query lặp lại, nên với
   Zipf, ngưỡng 2 hay 3 chủ yếu làm chậm việc retire chứ chưa thêm bằng chứng độc lập. Đợt 12 kiểm một phép xác minh mạnh
   hơn (chỉ đếm query khác nhau, và có veto), so ở cùng thời điểm gỡ E0 để bỏ hẳn nguyên nhân thứ hai (H18).
2. **C2: quan sát về qf và số peer (báo cáo đợt 11, mục 7.3) mới là thăm dò sau khi xem số trên 17 ô.** Ở cùng số peer,
   SRP gốc hơn itq_q+cap16 khi phần corpus nằm cùng bucket với query (qf) lớn, và thua khi qf nhỏ. Đợt 12 kiểm trước quy
   tắc này trên 10 cặp chưa dùng, với qf lấy từ dự đoán của C1 chứ không phải đo, tức là quy tắc mà người vận hành áp
   được trước khi migrate (H19). C1 và C2 trên các cặp mới là H20 và H21.
3. **Lỗi số luồng của pha nhúng** (`nproc` đọc `OMP_NUM_THREADS=1`) được sửa trong `run_round12.sh`.

Tách nhân bản với khái quát hoá: H18 dùng ba model đã dùng (bge-base, e5-large, Arctic) trên seed mới, nhưng phép xác minh
là mới; gte-base và MiniLM ở phần C3 chỉ là thăm dò. H19 đến H21 chấm trên 10 cặp mới; 12 cặp cũ đo lại với seed mới chỉ
vào H19d và H21c.

## 1. Phần đóng băng

- Mã nguồn đóng băng là các file trong `SHA256SUMS_round12`. Khi không dùng chính sách mới và để `--finish-drop done` (mặc
  định), mọi chính sách cũ cho đúng từng số đợt 11; pha R kiểm lại điều này trên dữ liệu thật.
- Overlay, tra cứu, adapter, gộp PROB, placement và định nghĩa các chính sách cũ giữ như `PREREG_round11.md` mục 1.
  Placement E1 của mọi thí nghiệm C3 là itq_q+cap16.
- **Định nghĩa.** Một *lần thấy* là một truy vấn của dòng có object dual trong danh sách native phía E1 của nó; đây đúng
  là "xác nhận" của các đợt 7 đến 11. Một *veto* là một truy vấn của dòng có object dual trong danh sách phía E0 (đã cắt
  như `--dual-slots bonus`) mà không có object đó trong danh sách native phía E1: đường cũ còn đưa object tới client, đường
  mới thì không.
- **Phần mới trong code** (định nghĩa đầy đủ ở đầu `11_probe_safe.py`):
  - `lazyVbgDu<c>`: retire bản E0 khi object đã được thấy bởi c query khác nhau; một query lặp lại chỉ tính một lần.
    c tối đa 3.
  - `lazyVbgDv<c>`: như `lazyVbgDk<c>` (đếm mọi lần thấy), nhưng mỗi veto đưa bộ đếm của object về 0.
  - `lazyVbgDuv<c>`: đếm query khác nhau, và mỗi veto xoá bộ đếm cùng danh sách query đã đếm. c tối đa 3.
  - `--finish-drop T`: mọi chính sách có nền gỡ cả index E0 đúng ở lượt T của `--bg-finish` (sau truy vấn thứ T), thay
    vì ở lượt xong. Nền một mình xong trước T, nên tới T mọi object đều có bản E1. Giữa lượt xong và T, các chính sách họ
    lazyVbgD vẫn nhận lần thấy, veto và retire như trước. Như vậy mọi chính sách so ở cùng thời điểm gỡ E0, và hiệu giữa
    chúng chỉ còn do quy tắc retire.
  - Đo thêm: số veto, số lần thấy từ query mới (chỉ với u, uv), lượt gỡ E0 (`t_drop`), loại quy tắc (`confirm_kind`).
- **Năm model mới**, chọn trước khi có kết quả nào với chúng, nhỏ để nhúng nhanh trên CPU:
  - e5-small-v2 (`intfloat/e5-small-v2`, 384 chiều, tag `e5small`);
  - gte-small (`thenlper/gte-small`, 384 chiều, tag `gtesmall`);
  - bge-small-en-v1.5 (`BAAI/bge-small-en-v1.5`, 384 chiều, tag `bgesmall`);
  - all-mpnet-base-v2 (`sentence-transformers/all-mpnet-base-v2`, 768 chiều, tag `mpnet`);
  - snowflake-arctic-embed-xs (`Snowflake/snowflake-arctic-embed-xs`, 384 chiều, tag `arcticxs`).

  Bốn model đầu cùng họ với một model đã dùng (e5, gte, bge, Arctic) nhưng khác cỡ và khác trọng số; mpnet là họ mới. Vì
  thế H19 kiểm quy tắc qf chủ yếu qua các cỡ model trong cùng họ, chỉ một phần qua họ mới; báo cáo sẽ nói rõ. Cả năm được
  nhúng trên code 20k và SciFact bằng `01_embed_m1.py`, có tự kiểm văn bản tái tạo đúng embedding M0, với prefix theo họ
  như các đợt trước (e5: `query: `, `passage: `; Arctic: instruction cho query; bge, gte, mpnet: không prefix). M0 vẫn là
  bge-large-en-v1.5.
- **Seed mới**: 36, 37, 38 cho placement và mô hình dị hướng; 36 đến 45 cho C3.
- **Thiết lập**:
  - code 20k và SciFact: overlay 10.000 node, S = 10%. Đợt này không dùng code100kfq.
  - C3: dòng Zipf 1; code 20k dòng 3.000 lượt với T = 1.500 và 3.000; SciFact dòng 800 lượt với T = 400 và 800;
    checkpoint và cửa sổ như đợt 11; `--finish-drop T`.
  - Placement: srp, srp+cap16, srp_c+cap16, itq_q, itq_q+cap16, mỗi biến thể trên 8 điểm (L, T) như đợt 11.

## 2. Giả thuyết và tiêu chí đạt

Khoảng tin cậy 95% (KTC) lấy theo phân phối t trên hiệu ghép cặp qua seed. Ký hiệu:

- **k1** = lazyVbgD (một lần thấy), **drain** = lazyVbgDinf (không retire trước lúc gỡ E0), **uv2** = lazyVbgDuv2;
- **diện tích [0, T]**: trung bình final giữ riêng trên [0, T], hình thang qua các checkpoint, như đợt 11;
- **rerank [0, T)**: rerank@20 trung bình trên các cửa sổ của dòng kết thúc trước hoặc đúng lượt T;
- **byte đỉnh**: byte lưu trữ đỉnh mỗi object, metadata 0 (`bytes_peak_m0`);
- **F_v^x(c)**: đường biên Pareto của final R@5 theo x (số ứng viên hoặc số peer) của biến thể v trên 8 điểm (L, T), nội
  suy tuyến tính theo log x, không ngoại suy, như H13 của đợt 11;
- **Δ_peer** của một cặp: trung bình theo seed 36 đến 38 của F_srp^peer(c) − F_itq_q+cap16^peer(c), với c là số peer của
  srp_c+cap16 ở (L = 5, T = 8). Số dương nghĩa là SRP gốc tốt hơn ở cùng số peer;
- **qf dự đoán** của một cặp: trung bình theo seed 36 đến 38 của phần corpus dự đoán nằm cùng bucket 16 bit với query, tính
  bằng công thức của H14c đợt 11 (`qfrac_pred_u`), không dùng giá trị đo.

**H18, C3 với phép xác minh mạnh hơn.** 12 ô: 3 model {bge-base, e5-large, Arctic} × {code 20k với T = 1.500 và 3.000,
SciFact với T = 400 và 800}, seed 36 đến 45, `--finish-drop T`.

- H18a, không kém drain: uv2 − drain có cận dưới KTC lớn hơn −1 điểm ở cả diện tích [0, T] lẫn rerank [0, T).
- H18b, lưu trữ: uv2 − drain về byte đỉnh có cận trên KTC nhỏ hơn 0.
- H18c, sửa được chỗ hỏng của k1: uv2 − k1 về rerank [0, T) có cận dưới KTC lớn hơn 0.

**H19, quy tắc chọn placement theo qf dự đoán (C1 và C2).** 10 cặp mới: 5 model mới × {code 20k, SciFact}. Nhóm qf lớn
là các cặp mới có qf dự đoán ít nhất 8e-4; nhóm qf nhỏ là các cặp mới có qf dự đoán không quá 2e-4. Hai ngưỡng nằm trong
khoảng trống giữa hai nhóm của đợt 11 (qf dự đoán 1,47e-4 và 1,25e-3). Cặp nằm giữa hai ngưỡng không được dự đoán và chỉ
báo cáo.

- H19a: mọi cặp của nhóm qf lớn có Δ_peer > 0.
- H19b: mọi cặp của nhóm qf nhỏ có Δ_peer < +1.
- H19c: Spearman giữa qf dự đoán và Δ_peer trên 10 cặp mới ít nhất 0,6.
- H19d: Spearman đó trên 22 cặp (12 cặp cũ: bge-base, e5-large, Arctic, M0, MiniLM, gte-base × {code 20k, SciFact}, đo
  lại với seed 36 đến 38; và 10 cặp mới) ít nhất 0,8.

Nhóm nào rỗng thì tiêu chí của nhóm đó ghi là KHÔNG CHẠY. Cặp trong một nhóm mà Δ_peer không xác định (đường biên không
phủ c) tính là không thoả.

**H20, C2 trên cặp mới.** Như H15 của đợt 11, cho từng cặp trong 10 cặp mới, seed 36 đến 38:

- H20a: trung bình theo seed của F_itq_q+cap16^ứng viên(c) − F_srp_c+cap16^ứng viên(c), với c là số ứng viên của
  srp_c+cap16 ở (5, 8), ít nhất +5 điểm.
- H20b: trung bình theo seed của F_itq_q+cap16^ứng viên(c) − F_itq_q^ứng viên(c), với c là số ứng viên của itq_q ở (5, 8),
  ít nhất −1 điểm.

**H21, mô hình dị hướng (C1) trên cặp mới.** Tính như H14 của đợt 11, trung bình qua seed 36 đến 38:

- H21a: trên 10 cặp mới, trung bình |log10(p / q)| không quá 0,2 (p: xác suất hai document trùng bucket 16 bit dự đoán
  bằng công thức góc; q: đo thật).
- H21b: trên 10 cặp mới, trung bình |log10(qf dự đoán / qf đo)| không quá 0,2.
- H21c: trên 22 cặp, Spearman giữa p và phần tải của 1% peer nóng nhất với srp ở L = 5 ít nhất 0,8.

Tổng cộng 63 tiêu chí: H18 có 36 (3 × 12 ô), H19 có 4, H20 có 20 (2 × 10 cặp), H21 có 3.

Nếu model mới nào không nhúng được, các tiêu chí của cặp đó (H20) ghi là KHÔNG CHẠY; H19a đến H19d, H21a đến H21c gộp các
cặp mới nên khi đó cũng ghi là KHÔNG CHẠY, và số tính trên các cặp còn lại chỉ là thăm dò. Ô hay cặp của model cũ thiếu dữ
liệu thì ghi là KHÔNG ĐẠT, và job thiếu được chạy lại theo mục 4.

**Cách đọc định trước:**

- H18a đạt ở một ô nhưng byte đỉnh của uv2 thấp hơn drain chưa tới 5% (trung bình theo seed của (drain − uv2) / drain): ở
  ô đó, bài nói phép xác minh an toàn nhưng tiết kiệm ít, và cấu hình chính của C3 là drain.
- H18a đạt và tiết kiệm từ 5% trở lên: bài trình bày uv2 là cách gỡ sớm không làm giảm chất lượng so với drain ở ô đó.
- H18a không đạt ở ô nào: bài không nói phép xác minh không kém drain ở ô đó; C3 giữ cách trình bày của đợt 11 (ngưỡng là
  nút chỉnh giữa byte và chất lượng, drain là đầu an toàn).
- H18c đạt thì bài nói được cơ chế: chỉ đếm query khác nhau và veto sửa được phần rerank mà k1 mất.
- H19a và H19b cùng đạt: bài nêu quy tắc chọn placement theo qf dự đoán (SRP gốc khi qf ≥ 8e-4, placement học khi qf ≤ 2e-4,
  giữa hai ngưỡng thì chưa kết luận). Chỉ H19c, H19d đạt: bài chỉ nói qf xếp thứ tự lợi thế của SRP, không nêu ngưỡng. H19a
  hay H19b không đạt: quan sát về qf vẫn là thăm dò.
- H20a không đạt ở cặp nào: bài không nói khoá học tốt hơn khoá ngẫu nhiên đã trừ tâm ở cặp đó.
- H21 không đạt: bài giới hạn tuyên bố về độ chính xác của C1 vào các cặp đã kiểm ở đợt 8 đến 11.

**Dự đoán trước khi chạy** (để sau này đối chiếu, không dùng để chấm): H18c khoảng 85% mỗi ô; H18b khoảng 90% mỗi ô, nhưng
tiết kiệm có thể dưới 5% vì uv2 chỉ retire được object mà ít nhất hai query khác nhau của dòng đã thấy; H18a khoảng 50% mỗi
ô, và khả năng đạt cả 12 ô thấp (khoảng 20%). H19a khoảng 85%, H19b khoảng 70%, H19c khoảng 75%, H19d khoảng 65%. H20a
khoảng 90% mỗi cặp, H20b khoảng 95% mỗi cặp. H21a và H21b khoảng 75%, H21c khoảng 90%.

## 3. Phần thăm dò, kế hoạch phân tích chốt trước

Phần này không có ngưỡng.

- **E1. Đường đánh đổi của C3 ở cùng thời điểm gỡ E0.** Với mỗi ô của pha C (20 ô: 5 model × 4), mọi chính sách (static,
  full, lazybg, k1, k2, k3, u2, v2, uv2, uv3, drain): diện tích [0, T], rerank [0, T), payload, nhúng lại do truy vấn và do
  nền, peer và record phải chấm mỗi truy vấn trên [0, T); byte đỉnh và trung bình (metadata 0 và 64), lưu trữ đỉnh theo
  record; phần object ngoài S retire trước lúc gỡ E0; số lần thấy, số lần thấy từ query mới, số veto; lượt xong; hiệu ghép
  cặp với drain và với k1 (diện tích, rerank, byte đỉnh) kèm KTC.
- **E2. Riêng pha 1.** k1 − drain ở cùng thời điểm gỡ E0, mỗi ô: đo trực tiếp phần mà đợt 11 chỉ tách được sau khi xem số.
- **E3. Mất đường tìm và negative flip.** `lost_retire` trung bình và lớn nhất qua các checkpoint trong (0, T),
  `reach_any` thấp nhất; negative flip so với drain (phần query giữ riêng có ít object đúng trong top-5 hơn drain ở cùng
  checkpoint), cho mọi chính sách họ lazyVbgD.
- **E4. C3 trên gte-base và MiniLM.** Các hiệu của H18 cho 8 ô của hai model này, không chấm ngưỡng.
- **E5. Bảng C1, C2 trên 22 cặp.** p, q, qf dự đoán và đo, phần tải của 1% peer, Δ_peer, hiệu ở cùng số ứng viên; bậc
  thang srp, srp+cap16, srp_c+cap16, itq_q, itq_q+cap16: hiệu so với srp_c+cap16 ở cùng số ứng viên và cùng số peer, tải lưu
  trữ (tối đa, p99, phần của 1% peer, Gini), phần truy vấn tới peer nóng nhất, công việc chấm lớn nhất, phần record bị dời
  và phải vào peer đầy.
- **E6. Quy tắc qf như một bộ phân loại.** Với mỗi cặp: khuyến nghị của quy tắc (SRP, placement học, hay chưa kết luận),
  biến thể thật sự tốt hơn ở cùng số peer, và cái giá của SRP về công việc chấm của peer nặng nhất (lần itq_q+cap16).
- **E7. Pha nhúng.** Tốc độ đo được, thời gian, overlap GT giữa M0 và M1 của từng model mới.

## 4. Quy tắc

- Không thêm chính sách, tham số hay biến thể mới dựa trên kết quả đợt 12.
- Job lỗi kỹ thuật thì chạy lại nguyên trạng.
- Nếu phải sửa lỗi code thì ghi diff và lý do vào mục 5 của file này, kèm commit mới. Mọi kết quả trước lần sửa vẫn được
  giữ.
- Pha R chạy trước, trên dữ liệu thật, bằng `rerun_prev.py` (đọc đúng tham số trong file kết quả cũ):
  - `11_probe_safe.py` chạy lại code 20k bge-base seed 26 ở chế độ migrate tới khi xong của đợt 11, có xen thêm
    lazyVbgDu2, lazyVbgDuv2, lazyVbgDv2: 21 run của đợt 11 phải trùng từng số.
  - `11_probe_safe.py` chạy lại C3 bge-base seed 26 trên code100kfq của đợt 11: 20 run phải trùng từng số.
  - Ở cả hai job, lượt mới phải có đủ mọi run của lượt cũ; thiếu thì job thoát mã 3.
  - Nếu pha R lệch, toàn bộ đợt 12 chỉ còn giá trị thăm dò cho tới khi tìm ra nguyên nhân.
- Tự kiểm trong lúc chạy và trong analyze:
  - placement itq_q+cap16 trong 11 trùng biến thể cùng tên của 10 với seed 36 đến 38 (30 file);
  - mọi run có nền của pha C có `t_drop` = T, và mọi checkpoint từ T trở đi trùng full;
  - drain không retire bản E0 nào trước lúc gỡ;
  - quy tắc k và u không có veto; `confirm_kind` và `confirm_k` đúng tên chính sách;
  - nhúng lại do truy vấn cộng do nền bằng `new`.

## 5. Sửa đổi sau khi bắt đầu chạy

Chưa có.
