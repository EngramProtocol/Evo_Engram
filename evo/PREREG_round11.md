# Evo-Engram, đợt 11: đăng ký trước cho ablation C3, migrate tới khi xong, cơ chế C2, điều kiện vận hành của payload và khái quát hoá sang model mới

Ngày ghi: 3/11/2026. File này được commit cùng tag `evo-r11-prereg` TRƯỚC khi chạy bất kỳ job nào của đợt 11. Kết quả
được chấm bằng `evo/analyze_r11.py`, cũng commit cùng tag. Mọi kết quả đều được báo cáo, kể cả khi không đạt. Lúc ghi
file này thầy chưa duyệt; nếu sau khi xem kết quả thầy đổi ngưỡng hay định nghĩa, phần thay đổi được báo cáo là thăm dò.

Góp ý của thầy sau đợt 10 dẫn tới năm việc của đợt 11:

1. Tách tác động riêng của retire trễ (verify-then-retire), mã PQ E1 gắn tại chỗ và migrate nền trong C3 (H11).
2. Đưa phần migrate tới khi xong vào bài chính, so với hai cách làm ở hai đầu: retire ngay và giữ cả epoch cũ tới khi
   xong; tính đủ chi phí (H12 và phần thăm dò E1).
3. Chỉ ra C2 khác ở cơ chế nào: khoá học so với khoá ngẫu nhiên đã trừ tâm ở cùng chi phí tra cứu, giới hạn tải không làm
   mất recall (H13); mô hình dị hướng của C1 trên thêm cặp (H14).
4. Tách nhân bản trên seed mới với khái quát hoá: H11, H12, H13 dùng corpus và model đã dùng ở các đợt trước, trên seed
   mới; H15 đưa C2 sang hai corpus khác và hai model chưa từng dùng; H14a, H14c và H16 chỉ dùng hai model mới.
5. Phân tích H8 như một điều kiện vận hành của phần tiết kiệm payload: kiểm trước một dự đoán (H17) và tách payload theo
   số lần một query lặp lại (E2).

## 1. Phần đóng băng

- Mã nguồn đóng băng là các file trong `SHA256SUMS_round11`. Khi không dùng chính sách hay hậu tố mới, mọi chính sách và
  biến thể cũ cho đúng từng số đợt 8 đến 10; pha R kiểm lại điều này trên dữ liệu thật.
- Overlay, tra cứu, adapter, gộp PROB, placement itq_q và định nghĩa các chính sách cũ giữ như `PREREG_round8.md` mục 1;
  placement có giới hạn tải giữ như `PREREG_round10.md` mục 1.
- **Placement E1 của mọi thí nghiệm C3 là itq_q+cap16**, cấu hình chính của đợt 10, kể cả phần migrate tới khi xong (đợt
  10 dùng itq_q không trần cho phần này).
- mapall và mapkeep không chạy lại: trong code hiện tại, giới hạn tải chỉ áp cho record E1 thật, record ánh xạ của hai
  baseline này vẫn đặt theo itq_q không trần, nên so trên itq_q+cap16 sẽ không cùng cấu hình. Số của chúng lấy từ đợt 8
  và 9 (itq_q không trần, seed 6 đến 15).
- **Phần mới trong code** (định nghĩa đầy đủ ở đầu `11_probe_safe.py` và `10_probe_placement.py`):
  - `lazyVbgDk<c>`: lazyVbgD với ngưỡng c xác nhận native. Đợt 11 dùng c = 2 và 3.
  - `lazyVbgDinf`: lazyVbgD không bao giờ retire bản E0 trước khi xong; khi mọi object đã có bản E1 thì gỡ cả index E0
    một lần. Đây là cách giữ cả hai epoch tới khi xong (drain).
  - Hậu tố `_adp`: chạy chính sách với điểm adapter cho bản E0 của object dual, tức bỏ mã PQ E1 gắn tại chỗ (và bỏ byte
    của nó), trong cùng job với chính sách gốc. Ngân sách nền của `lazyVbgD_adp` ghép với `lazyV1_adp` như lazyVbgD ghép
    với lazyV1.
  - Đo thêm: byte lưu trữ mỗi object (metadata 0 và 64 byte mỗi record); `reach_any` và `lost_retire` (phần vị trí của
    top-5 thật còn tới được qua ít nhất một đường, và phần mất đường vì retire); số object đúng của từng query giữ riêng
    (để tính negative flip); payload, final và rerank theo lần xuất hiện của query (`rep_curve`, `rep_win`); số lần nhúng
    lại mỗi lượt tách theo do truy vấn và do nền, kể cả bản E1 mà rebuild dựng ở nền (`emb_q`, `emb_bg`).
  - `10_probe_placement.py`: ghi thêm số record phải vào peer đầy vì cả K peer đều đầy. Hậu tố `+cap<m>` (có từ đợt 10)
    lần đầu được dùng với srp, srp_c và pca_q.
- **Hai model mới**, chọn trước khi có kết quả nào với chúng, khác họ với ba model đã dùng (bge, e5, arctic):
  - gte-base (`thenlper/gte-base`, 768 chiều, tag `gtebase`);
  - all-MiniLM-L6-v2 (`sentence-transformers/all-MiniLM-L6-v2`, 384 chiều, tag `minilm`).

  Cả hai được nhúng trên server bằng `01_embed_m1.py`, có tự kiểm văn bản tái tạo đúng embedding M0. MiniLM nhúng trên
  code100kfq, code 20k và SciFact; gte-base chỉ trên code 20k và SciFact, vì nhúng 100.000 hàm code bằng model cỡ base
  trên 4 lõi CPU tốn quá lâu. M0 vẫn là bge-large-en-v1.5.
- **Seed mới**: 26, 27, 28 cho placement, mô hình dị hướng và churn; 26 đến 35 cho C3; 26 đến 30 cho H17.
- **Thiết lập**:
  - code100kfq: overlay 50.000 node, S = 2%, dòng 3.000 lượt trên 200 query, 100 query giữ riêng, Zipf 1 (chính) và
    đều.
  - code 20k và SciFact: overlay 10.000 node, S = 10%.
  - Migrate tới khi xong: code 20k dòng 3.000 lượt với T = 1.500 và 3.000; SciFact dòng 800 lượt với T = 400 và 800;
    Zipf 1; checkpoint như đợt 10.

## 2. Giả thuyết và tiêu chí đạt

Khoảng tin cậy 95% (KTC) lấy theo phân phối t trên hiệu ghép cặp qua seed. Mỗi tiêu chí phải đạt riêng cho từng ô (model,
hoặc corpus × model × T). Ký hiệu:

- **final giữ riêng**: final R@5 trên 100 query giữ riêng ở cuối dòng;
- **rerank trên dòng**: rerank@20 trung bình trên dòng truy vấn;
- **final trên dòng**: final R@5 trung bình trên dòng;
- **payload**: số record phải tải payload mỗi truy vấn;
- **diện tích [0, T]**: trung bình final giữ riêng trên [0, T], hình thang qua các checkpoint, như đợt 10;
- **rerank [0, T)**: rerank@20 trung bình trên các cửa sổ của dòng kết thúc trước hoặc đúng lượt T.

**H11, ablation C3.** code100kfq, itq_q+cap16, 3 model {bge-base, e5-large, Arctic}, seed 26 đến 35, Zipf 1. Ngân sách
nhúng lại của lazyVbg và lazyVbgD ghép với lazy như đợt 7b.

- H11a, retire trễ trên đường do truy vấn kéo về: lazyV1 − lazy về rerank trên dòng, cận dưới KTC lớn hơn 0.
- H11b, mã PQ E1 gắn tại chỗ: trung bình theo seed của (payload của lazyVbgD) / (của lazyVbgD_adp) không quá 1/2, và
  lazyVbgD − lazyVbgD_adp về final trên dòng có cận dưới KTC lớn hơn 0.
- H11c, retire trễ trên đường nền: lazyVbgD − lazyVbg về final giữ riêng, cận dưới KTC lớn hơn 0.
- H11d, migrate nền với phần ngân sách tiết kiệm được: lazyVbgD − lazyV1 về final giữ riêng, cận dưới KTC lớn hơn 0.

**H12, migrate tới khi xong.** 12 ô: 3 model × {code 20k với T = 1.500 và 3.000, SciFact với T = 400 và 800}, seed 26
đến 35.

- H12a, không kém việc giữ cả epoch cũ tới khi xong: lazyVbgD − lazyVbgDinf có cận dưới KTC lớn hơn −1 điểm ở cả diện
  tích [0, T] lẫn rerank [0, T).
- H12b, lưu trữ: lazyVbgD − lazyVbgDinf về byte đỉnh mỗi object (metadata 0) có cận trên KTC nhỏ hơn 0.
- H12c, hơn retire ngay với cùng lịch nền: lazyVbgD − lazybg có cận dưới KTC lớn hơn 0 ở cả diện tích [0, T] lẫn
  rerank [0, T).

**H13, cơ chế C2.** code100kfq, 4 không gian {bge-base, e5-large, Arctic, M0}, seed 26 đến 28. F_v(c) là đường biên
Pareto của final R@5 theo số ứng viên của biến thể v trên 8 điểm (L, T), nội suy tuyến tính theo log số ứng viên, không
ngoại suy, như H2.

- H13a, khoá học so với khoá ngẫu nhiên đã trừ tâm, cả hai có giới hạn tải: với c là số ứng viên của srp_c+cap16 ở
  (L = 5, T = 8), trung bình theo seed của F_itq_q+cap16(c) − F_srp_c+cap16(c) ít nhất +5 điểm.
- H13b, giới hạn tải không làm mất recall: với c là số ứng viên của itq_q ở (5, 8), trung bình theo seed của
  F_itq_q+cap16(c) − F_itq_q(c) ít nhất −1 điểm.

**H14, mô hình dị hướng (C1).** Tính như H1 của đợt 8, lấy trung bình qua seed 26 đến 28. Cặp mới là 5 cặp có model mới:
gte-base × {code 20k, SciFact}, MiniLM × {code100kfq, code 20k, SciFact}.

- H14a: trên 5 cặp mới, trung bình |log10(p / q)| không quá 0,2, với p là xác suất hai document trùng bucket 16 bit dự
  đoán bằng công thức góc, q là xác suất đó đo thật.
- H14b: trên cả 17 cặp (12 cặp cũ đo lại với seed mới và 5 cặp mới), Spearman giữa p và phần tải của 1% peer nóng nhất
  với srp ở L = 5 ít nhất 0,8.
- H14c: trên 5 cặp mới, trung bình |log10| của tỉ số giữa phần corpus cùng bucket 16 bit với query, dự đoán và đo thật,
  không quá 0,2.

**H15, C2 trên corpus và model khác.** 13 ô: code 20k và SciFact với 6 không gian {bge-base, e5-large, Arctic, M0,
gte-base, MiniLM}, và code100kfq với MiniLM; seed 26 đến 28. Trong đó 5 ô có model mới là phần khái quát hoá thuần.

- H15a: như H13a.
- H15b: như H13b.

**H16, C3 trên model mới.**

- H16a đến H16d: H10a đến H10d của đợt 10, cho MiniLM trên code100kfq, itq_q+cap16, seed 26 đến 35, Zipf 1:
  - H16a: lazyVbgD − lazy về final giữ riêng, cận dưới KTC lớn hơn 0;
  - H16b: lazyVbgD − static về final giữ riêng, trung bình ít nhất 3 điểm;
  - H16c: lazy − static về rerank trên dòng, cận trên KTC nhỏ hơn 0;
  - H16d: dual cuối dòng của lazyVbgD trung bình không quá 40%, và trung bình theo seed của (payload của lazyVbgD) /
    (của lazy) không quá 1/3.
- H16e: H12c cho gte-base và MiniLM, 8 ô: 2 model × {code 20k với T = 1.500 và 3.000, SciFact với T = 400 và 800}.

**H17, điều kiện vận hành của payload.** Đợt 9 thấy H8 (payload của lazyVbgD không quá 1/3 của lazy) không đạt trên code
20k và SciFact, và giải thích là phần tiết kiệm đến qua các truy vấn lặp lại, nên phụ thuộc số lượt truy vấn đã phục vụ.
H17 kiểm trước dự đoán đó. Thiết lập như H8 của đợt 9 (lazyVbgD ghép ngân sách với lazy như đợt 8; thêm static, lazyV1,
full, lazyV1_adp, lazyVbgD_adp cho phần thăm dò), nhưng placement itq_q+cap16, seed 26 đến 30, và mỗi seed chạy hai độ
dài dòng: dòng ngắn của đợt 9 (600 lượt cho code 20k, 155 cho SciFact) và dòng 3.000 lượt. Ô là corpus × model với 3
model đã dùng, 6 ô, Zipf 1; workload đều là thăm dò.

- H17a: ở dòng 3.000 lượt, trung bình theo seed của (payload của lazyVbgD) / (của lazy) không quá 1/3.
- H17b: tỉ lệ đó ở dòng 3.000 lượt trừ ở dòng ngắn, ghép cặp theo seed, có cận trên KTC nhỏ hơn 0.

Tổng cộng 109 tiêu chí: H11 có 12 (4 × 3 model), H12 có 36 (3 × 12 ô), H13 có 8 (2 × 4 không gian), H14 có 3, H15 có 26
(2 × 13 ô), H16 có 12 (4 cho MiniLM và 8 ô của H16e), H17 có 12 (2 × 6 ô).

Nếu model mới nào không nhúng được (ví dụ server không tải được model), các tiêu chí của model đó ghi là KHÔNG CHẠY, không
tính là đạt hay không đạt, và báo cáo nói rõ. H14a, H14b, H14c gộp các cặp của cả hai model mới, nên khi đó cả ba cũng ghi
là KHÔNG CHẠY; số tính trên các cặp còn lại chỉ là thăm dò. Ô của model cũ thiếu dữ liệu thì ghi là KHÔNG ĐẠT, và job
thiếu được chạy lại theo mục 4.

**Cách đọc định trước:**

- Nếu H11b chỉ đạt phần payload, bài chỉ nói mã E1 gắn tại chỗ giảm payload, không nói nó tăng chất lượng.
- Nếu H12a không đạt ở ô nào, bài không nói retire sau 1 xác nhận là không kém giữ cả epoch cũ ở ô đó; kết quả k = 2, 3
  chỉ là thăm dò.
- Nếu H13a hay H15a không đạt ở không gian nào, bài không nói khoá học tốt hơn khoá ngẫu nhiên đã trừ tâm ở không gian đó.
- Nếu H17a không đạt, bài nói tiết kiệm payload phụ thuộc cả cỡ corpus, không chỉ số lượt truy vấn.

## 3. Phần thăm dò, kế hoạch phân tích chốt trước

Phần này không có ngưỡng. Đại lượng chính chốt trước để tránh chọn số sau khi xem kết quả.

- **E1. Chi phí đầy đủ.** Với mọi chính sách của H11, H12 và H16, mỗi truy vấn: số peer phải hỏi, số record các peer
  phải chấm, số record tải payload, số lần nhúng lại (do truy vấn và do nền), số object dual trả về từ phía E0. Lưu trữ:
  đỉnh và trung bình theo record và theo byte (metadata 0 và 64), byte lúc đầu, lượt xong, số xác nhận, số retire trước
  khi xong, số bản E0 gỡ khi xong. Bảng đặt mọi chính sách cạnh nhau, kể cả các chỉ số lazyVbgD kém hơn.
- **E2. Payload theo số lần lặp.** Payload, final và rerank theo lần xuất hiện k của query (k = 1, 2, 3 đến 5, 6 trở
  lên), cho lazy, lazyV1, lazyVbgD, lazyVbgD_adp:
  - gộp cả dòng;
  - trong cùng cửa sổ thời gian, để tách số lần lặp khỏi tiến độ migrate;
  - trên mọi corpus và độ dài dòng (pha B, C, G);
  - tỉ lệ payload cộng dồn theo số lượt đã phục vụ;
  - tỉ lệ payload cả dòng dự đoán từ tỉ lệ theo lớp k nhân với cơ cấu lớp k của workload, so với tỉ lệ đo thật.
- **E3. Negative flip.** Phần query giữ riêng có số object đúng trong top-5 thấp hơn static, và thấp hơn full, ở cùng
  checkpoint, với final và rerank, cho mọi chính sách; ghi giá trị ở checkpoint cuối, trung bình và lớn nhất qua các
  checkpoint sau lượt 0 (với migrate tới khi xong: các checkpoint trong (0, T]).
- **E4. Mất đường tìm vì retire.** `lost_retire` và `reach_any` theo thời gian cho lazy, lazyV1, lazyVbg, lazyVbgD,
  lazybg, lazyVbgDk2, lazyVbgDk3, lazyVbgDinf.
- **E5. Ngưỡng xác nhận.** k = 1, 2, 3 và không bao giờ: diện tích [0, T], rerank [0, T), byte đỉnh và trung bình, lượt
  xong, phần object retire trước khi xong.
- **E6. Churn trên itq_q+cap16.** code100kfq, 3 model, seed 26 đến 28, hai cấu hình churn của đợt 9; đại lượng như đợt 9.
- **E7. C1 thêm.** Công thức trường trung bình so với công thức góc; dự đoán phần corpus cùng bucket với query trên cả 17
  cặp.
- **E8. Bậc thang cơ chế C2.** srp, srp_c, pca_q, itq_q, mỗi biến thể có và không có cap16, trên mọi ô của H13 và H15:
  recall tại cùng số ứng viên và tại cùng số peer, tải lưu trữ (tối đa, p99, phần của 1% peer, Gini), tải truy vấn (phần
  truy vấn tới peer nóng nhất), công việc chấm điểm theo peer, phần record bị dời và phần phải vào peer đầy. Riêng
  srp+cap16 trả lời câu "chỉ cần giới hạn tải cho SRP là đủ không".
- **E9. Model mới và workload đều.** Mọi bảng của E1 đến E5 cho gte-base và MiniLM; các hiệu của H11 cho MiniLM, và cho
  mọi model ở workload đều.

## 4. Quy tắc

- Không thêm chính sách, tham số hay biến thể mới dựa trên kết quả đợt 11.
- Job lỗi kỹ thuật thì chạy lại nguyên trạng.
- Nếu phải sửa lỗi code thì ghi diff và lý do vào file này, kèm commit mới. Mọi kết quả trước lần sửa vẫn được giữ.
- Pha R chạy trước, trên dữ liệu thật, bằng `rerun_prev.py` (đọc đúng tham số trong file kết quả cũ):
  - `10_probe_placement.py` chạy lại Arctic seed 16 của đợt 10 với srp, srp_c, itq_q, itq_q+cap16: phải trùng từng số.
  - `11_probe_safe.py` chạy lại bge-base seed 16, itq_q+cap16 của đợt 10, có xen thêm lazyV_adp và lazyVbgD_adp: các run
    của đợt 10 phải trùng từng số.
  - `11_probe_safe.py` chạy lại code 20k bge-base seed 16 ở chế độ migrate tới khi xong của đợt 10, có xen thêm
    lazyVbgD_adp, lazyVbgDk2, lazyVbgDinf: các run của đợt 10 phải trùng từng số.
  - Ở cả ba job, lượt mới phải có đủ mọi run (hoặc mọi biến thể được yêu cầu) của lượt cũ; thiếu thì job thoát mã 3.
  - Nếu pha R lệch, toàn bộ đợt 11 chỉ còn giá trị thăm dò cho tới khi tìm ra nguyên nhân.
- Tự kiểm trong lúc chạy: placement itq_q+cap16 trong 11 phải trùng biến thể cùng tên của 10 với seed 26 đến 28; sau lượt
  xong, mọi chính sách có nền phải trùng full ở mọi checkpoint; trước lượt xong, rebuild phải trùng static;
  lazyVbgDinf không retire bản E0 nào trước khi xong; số lần nhúng lại do truy vấn cộng do nền bằng `new` (trừ rebuild),
  và rebuild dựng đủ N − |S| bản ở nền.

## 5. Sửa đổi sau khi bắt đầu chạy

**Sửa 1 (5/11/2026, tag `evo-r11-fix1`).** Job nhúng gte-base trên code 20k chạy 27,6 giờ rồi dừng ở bước tự kiểm cuối
của `01_embed_m1.py`: độ dài các vector corpus nằm trong [0,99951; 1,00049], trung bình lệch 1 quá ngưỡng 1e-4, nên
script không ghi file nào.

- Nguyên nhân: checkpoint `thenlper/gte-base` lưu ở float16, và bản transformers trên server nạp model theo kiểu dữ liệu
  của checkpoint. Toàn bộ phép tính vì thế chạy float16 trên CPU, chậm khoảng 15 lần so với float32, và sai số làm tròn
  của float16 (cỡ 5e-4) vượt ngưỡng kiểm. MiniLM và bge-large lưu ở float32 nên không bị; embedding MiniLM đã ghi giữ
  nguyên.
- Diff: `01_embed_m1.py` gọi `.float()` ngay sau khi nạp cả model M0 (dùng để tự kiểm) lẫn model M1, và in thêm kiểu dữ
  liệu ở dòng `device=... max_seq=... dtype=...`. Không file probe, analyze hay run nào đổi.
- Job gte-base trên SciFact đang chạy bằng code cũ (cùng lỗi) bị dừng. Hai job nhúng gte-base chạy lại bằng code đã sửa,
  với `NTE=4` (xem lỗi dưới), rồi chạy pha N. Kết quả của 237 job đã xong (R, A, B, C, G, F và ba job nhúng MiniLM)
  giữ nguyên.
- Lỗi đã biết, không sửa trong đợt này: `run_round11.sh` tính NTE bằng `nproc` sau khi đã đặt `OMP_NUM_THREADS=1`, mà
  `nproc` đọc biến này, nên pha nhúng chạy 1 luồng. Lượt chạy lại truyền `NTE=4`. Sẽ sửa trong script đợt sau.
