# Evo-Engram, đợt 14: đăng ký trước cho C3 trên khoá SRP gốc, lần xác nhận drain trên seed mới, và drain trên dòng cho mọi model

Ngày ghi: 13/11/2026. File này được commit cùng tag `evo-r14-prereg` TRƯỚC khi chạy bất kỳ job nào của đợt 14. Kết quả
được chấm bằng `evo/analyze_r14.py`, cũng commit cùng tag. Mọi kết quả đều được báo cáo, kể cả khi không đạt. Đợt này làm
theo mục 5.3 và 5.4 của bản rà soát bản thảo ngày 13/11 (`Ra_soat_ban_thao_Evo_Engram_v5_13_11.md`). Lúc ghi file này thầy
chưa duyệt; nhóm chạy trước. Nếu sau khi xem kết quả thầy đổi ngưỡng hay định nghĩa, phần thay đổi được báo cáo là thăm dò.

Bản rà soát nêu năm chỗ mà một phản biện đọc kỹ sẽ hỏi. Đợt 14 đo cả năm:

1. **C3 chưa được đo trên placement mà quy tắc qf chọn (điểm P2).** Với bge-base và e5-large trên code 100k, quy tắc H19
   chọn khoá SRP gốc, nhưng mọi thí nghiệm C3 từ đợt 10 dùng placement học. Trên khoá SRP chỉ có một lần chạy thăm dò ở đợt
   8 (5 seed, quy tắc k1): ở final giữ riêng, k1 hơn lazy +3,6 điểm (KTC −1,5 đến +8,7) với bge-base và +1,1 (−2,1 đến
   +4,3) với e5-large. Pha U chạy lại trên 10 seed, có drain (H24).
2. **Con số chính của C3 là thăm dò (điểm P5).** Ở đợt 11, drain hơn rebuild 14,5 đến 26,3 điểm diện tích trên 20 ô, nhưng
   các so sánh của drain không nằm trong đăng ký trước của đợt 11. Pha C lặp lại đúng cấu hình đó trên 10 seed chưa dùng,
   với ngưỡng chốt trước (H22).
3. **Drain trên dòng 3.000 lượt mới có bge-base (đợt 13).** Pha D chạy drain cho e5-large, Arctic và MiniLM trên cùng seed
   với Bảng 7 và Bảng 10 của bản thảo (H23).
4. **So với full, ngân sách peer không cân (điểm P4); churn chưa chạy với drain.** Pha B đo full ở T = 16 probe, tức cùng số
   peer với hai epoch, trên đúng dòng của Bảng 10. Pha F chạy lại churn và lỗi peer có drain. Cả hai là thăm dò.
5. **Chế độ tải (điểm P3).** Mọi thiết lập đã chạy có nhiều nhất 2 object mỗi peer. Pha O lặp lại phép đo placement của code
   100k trên 5.000 peer, khoảng 20 object mỗi peer. Thăm dò.

Tách nhân bản với khái quát hoá. H22 là nhân bản trên seed mới với cùng corpus và cùng model; nó không phải bằng chứng trên
dữ liệu mới, và bài sẽ ghi đúng như vậy. H23 dùng lại seed 26 đến 35: số của static, lazy và k1 trên các seed này đã biết
từ đợt 11, chỉ drain và các hiệu có drain là chưa đo. H24 là cấu hình chưa chạy với các seed này; phía placement học của
phép so trong H24d đến H24f lấy từ đợt 13 (bge-base, đã biết) và từ pha D của đợt này (e5-large).

## 1. Phần đóng băng

- Mã nguồn đóng băng là các file trong `SHA256SUMS_round14`. `11_probe_safe.py`, `10_probe_placement.py`, `me_common.py`,
  `rerun_prev.py` và `src/` giữ nguyên như tag `evo-r13-prereg`: đợt 14 không sửa bộ mô phỏng, chỉ thêm `run_round14.sh`,
  `analyze_r14.py` và hai file mô tả. Pha R kiểm trên dữ liệu thật rằng môi trường hiện tại cho lại đúng từng số của đợt 13.
- Overlay, tra cứu, adapter, gộp PROB, mã PQ, định nghĩa các chính sách và các đại lượng đo giữ như `PREREG_round11.md` mục
  1, `PREREG_round12.md` mục 1 và `README_round13.md`. Tên chính sách:
  - **static**, **lazy**, **lazy+delay** (`lazyV1`), **lazy+keep** (`lazyD`), **full**, **bg**, **lazy+bg** (`lazybg`),
    **rebuild** như các đợt trước;
  - **k1** = `lazyVbgD` (retire bản E0 sau một lần thấy); **drain** = `lazyVbgDinf` (không retire bản E0 nào trước khi gỡ
    cả epoch cũ).
- **Hai cách đặt record E1 trên code 100k:**
  - *placement học*: `--e1-place itq_q --e1-cap 16`, như mọi thí nghiệm C3 từ đợt 10;
  - *khoá SRP gốc*: `--e1-place u`, không giới hạn tải. Đây là SRP không trừ tâm của thiết kế gốc, cũng là biến thể `srp`
    của `10_probe_placement.py` và là phương án mà quy tắc H19 chọn khi qf ≥ 8e-4.
- **Dòng trên code 100k** (pha U, D, B, F): 50.000 peer, S = 2%, 200 query trong pool và 100 query giữ riêng, dòng Zipf 1
  dài 3.000 lượt, checkpoint 0, 150, 300, 600, 1.000, 1.500, 2.000, 3.000, cửa sổ 150 lượt, `--confirms 1`. Ở chế độ này
  ngân sách nền của k1 ghép với lazy và lazy+delay, của drain ghép với lazy và lazy+keep (như đợt 13), nên tổng số lần
  nhúng lại mỗi lượt của k1 và drain xấp xỉ của lazy. Overlay, mẫu S, tập query giữ riêng và dòng truy vấn chỉ phụ thuộc
  seed, nên với cùng seed hai cách đặt record E1 thấy đúng cùng một overlay, cùng một dòng và cùng các query giữ riêng.
- **Migrate tới khi xong** (pha C): code 20k và SciFact, 10.000 peer, S = 10%, placement học, Zipf 1; code 20k dòng 3.000
  lượt với T = 1.500 và 3.000; SciFact dòng 800 lượt với T = 400 và 800; checkpoint và cửa sổ như đợt 11; mỗi chính sách
  gỡ index E0 ngay khi nó xong (`--finish-drop done`, đúng cấu hình của đợt 11, là đợt sinh ra các con số cần xác nhận).
- **Seed.** Pha C dùng seed 46 đến 55, chưa từng dùng. Pha U, D, B dùng seed 26 đến 35; pha F và O dùng seed 26 đến 28.
- **Chính sách chạy ở mỗi pha:**
  - U: static, lazy, lazy+delay, k1, lazy+keep, full, drain;
  - D: như pha D của đợt 13 (static, lazy, lazy+delay, `lazyV_adp`, `lazyVbg`, k1, `lazyVbgD_adp`, lazy+keep, full, drain);
  - C: static, lazy, full, bg, lazy+bg, rebuild, k1, drain;
  - F: static, lazy, lazy+delay, k1, lazy+keep, drain, full, dưới hai cấu hình churn của đợt 11;
  - B: full với `--probes 16`;
  - O: `srp`, `srp+cap16`, `srp_c+cap16`, `itq_q`, `itq_q+cap16` trên 8 điểm (L, T) như đợt 11, với `--nodes 5000`.

## 2. Giả thuyết và tiêu chí đạt

Khoảng tin cậy 95% (KTC) lấy theo phân phối t trên hiệu ghép cặp qua seed. Một tiêu chí chỉ đạt khi ô đó có đủ 10 seed.
Ký hiệu:

- **giữ riêng**: final R@5 của 100 query giữ riêng ở checkpoint cuối dòng (lượt 3.000);
- **rerank trên dòng**: rerank@20 trung bình trên cả dòng 3.000 lượt;
- **diện tích [0, T]**: trung bình final giữ riêng trên [0, T], hình thang qua các checkpoint, như đợt 11;
- **rerank [0, T)**: rerank@20 trung bình trên các cửa sổ của dòng kết thúc trước hoặc đúng lượt T;
- **mất đường**: `lost_retire` ở checkpoint cuối, tức phần vị trí top-5 thật của query giữ riêng có object ngoài S đã bị
  retire khỏi E0, tới được qua phía E0 nếu còn, nhưng không tới được qua phía E1.

**H22, xác nhận drain khi migrate tới khi xong.** 20 ô: 5 model {bge-base, e5-large, Arctic, gte-base, MiniLM} × {code
20k với T = 1.500 và 3.000, SciFact với T = 400 và 800}, seed 46 đến 55. Mỗi tiêu chí chấm riêng cho từng ô:

- H22a, so với rebuild: drain − rebuild về diện tích [0, T] có cận dưới KTC lớn hơn +10 điểm.
- H22b, so với lazy+bg, query chưa thấy: drain − lazy+bg về diện tích [0, T] có cận dưới KTC lớn hơn 0.
- H22c, so với lazy+bg, query đang phục vụ: drain − lazy+bg về rerank [0, T) có cận dưới KTC lớn hơn 0.
- H22d, so với không migrate: drain − static về diện tích [0, T] có cận dưới KTC lớn hơn +10 điểm.
- H22e, so với nền ngẫu nhiên: drain − bg về diện tích [0, T] có cận dưới KTC lớn hơn +5 điểm.

Ngưỡng đặt từ đợt 11 (seed 26 đến 35, cùng 20 ô), nơi cận dưới KTC nhỏ nhất qua các ô là +13,5 (rebuild), +0,7 (lazy+bg,
diện tích), +3,9 (lazy+bg, rerank), +15,1 (static) và +8,1 (bg).

**H23, drain trên dòng 3.000 lượt của code 100k với placement học.** 3 model {e5-large, Arctic, MiniLM}, seed 26 đến 35.
Mỗi tiêu chí chấm riêng cho từng model:

- H23a: drain − lazy về giữ riêng có cận dưới KTC lớn hơn 0.
- H23b: drain − lazy về rerank trên dòng có cận dưới KTC lớn hơn +5 điểm.
- H23c: drain − static về giữ riêng có cận dưới KTC lớn hơn +3 điểm.
- H23d: drain − static về rerank trên dòng có cận dưới KTC lớn hơn 0.
- H23e: drain − k1 về rerank trên dòng có cận dưới KTC lớn hơn 0.
- H23f: drain − k1 về giữ riêng có cận dưới KTC lớn hơn −1 điểm.

Số tham chiếu khi đặt ngưỡng. Với bge-base (đợt 13): drain − lazy +7,8 (giữ riêng) và +21,0 (rerank trên dòng); drain −
static +11,6 và +7,8; drain − k1 +1,4 (KTC +0,6 đến +2,2) và +5,8 (+2,9 đến +8,7). Với ba model của H23 mới có k1 (đợt
11): k1 − lazy về giữ riêng là +6,1 (e5-large), +6,8 (Arctic), +1,4 (MiniLM, KTC −0,4 đến +3,2); về rerank trên dòng là
+14,4, +13,3, +8,2; k1 − static về giữ riêng là +5,8, +9,8, +10,8.

**H24, C3 trên khoá SRP gốc.** 2 model {bge-base, e5-large}, là hai model đích trên code 100k mà quy tắc H19 chọn SRP;
seed 26 đến 35. Mỗi tiêu chí chấm riêng cho từng model. "Học" là cùng model, cùng seed, với placement học.

- H24a, giữ đường cũ không làm kém đi, query chưa thấy: trên SRP, drain − lazy về giữ riêng có cận dưới KTC lớn hơn −1.
- H24b, giữ đường cũ không làm kém đi, query đang phục vụ: trên SRP, drain − lazy về rerank trên dòng có cận dưới KTC lớn
  hơn −1.
- H24c, so với không migrate: trên SRP, drain − static về giữ riêng có cận dưới KTC lớn hơn +5 điểm.
- H24d, lợi ích của đường cũ phụ thuộc placement, query đang phục vụ: (drain − lazy trên học) − (drain − lazy trên SRP) về
  rerank trên dòng có cận dưới KTC lớn hơn 0.
- H24e, như H24d cho query chưa thấy: cùng hiệu của hiệu về giữ riêng có cận dưới KTC lớn hơn 0.
- H24f, cơ chế: mất đường của lazy trên học trừ mất đường của lazy trên SRP có cận dưới KTC lớn hơn 0.

H24d đến H24f là dự đoán của điều kiện thứ nhất ở Mục 6.3.4 của bản thảo: giữ đường cũ có lợi khi index mới chọn lọc, vì
khi đó record vừa dời dễ không được tìm lại; với khoá SRP trên không gian tập trung, mỗi truy vấn chấm hàng chục nghìn ứng
viên nên record vừa dời gần như luôn được tìm lại.

Số tham chiếu khi đặt H24, đều từ đợt 8 (seed 6 đến 10, quy tắc k1, placement học chưa có cap). Trên SRP: k1 − lazy về
giữ riêng +3,6 (bge-base) và +1,1 (e5-large), về rerank trên dòng +10,4 (KTC +7,1 đến +13,7) và +3,0 (−0,6 đến +6,7); k1 −
static về giữ riêng +11,1 (+9,1 đến +13,2) và +12,4 (+10,3 đến +14,5). Hiệu của hiệu cho k1 − lazy (học trừ SRP, cùng
seed): bge-base +2,5 (−1,0 đến +6,1) ở giữ riêng và +4,7 (+1,1 đến +8,3) ở rerank trên dòng; e5-large +7,0 (+2,9 đến
+11,0) và +12,7 (+8,9 đến +16,5). Với Arctic, là không gian qf nhỏ và không nằm trong H24, hiệu của hiệu gần 0 (−0,6 và
0,0). Mất đường chưa được đo trên SRP ở đợt nào.

Tổng cộng 130 tiêu chí: H22 có 100 (5 × 20 ô), H23 có 18 (6 × 3 model), H24 có 12 (6 × 2 model). Ô hay model thiếu dữ
liệu thì ghi là KHÔNG ĐẠT, và job thiếu được chạy lại theo mục 4.

**Cách đọc định trước:**

- H22: tiêu chí nào đạt ở cả 20 ô thì bài được viết rằng so sánh đó đã được xác nhận trong một lần nhân bản có đăng ký
  trước trên seed mới, kèm khoảng của đợt 14 bên cạnh khoảng của đợt 11. Tiêu chí nào trượt ở vài ô thì bài báo số ô đạt,
  nêu tên ô trượt, và giới hạn câu khẳng định vào các ô đạt. Trong mọi trường hợp bài ghi rằng đây là nhân bản trên cùng
  corpus và model.
- H23a, H23b đạt ở một model: Bảng 7 và Bảng 10 có dòng drain cho model đó và bài nói drain hơn lazy ở model đó. H23a
  trượt ở MiniLM thì khớp với H16a của đợt 11 (index cũ phục vụ MiniLM kém), và đoạn "điều kiện thứ hai" ở Mục 6.3.4 được
  viết lại cho drain.
- H23e, H23f đạt ở cả ba model: câu "retire sau một lần thấy làm mất chất lượng so với drain" trên dòng không còn chỉ dựa
  vào bge-base. Trượt ở model nào thì bài nói rõ ở model đó k1 không kém drain trên dòng.
- H24a, H24b đạt ở cả hai model: bài khuyến nghị drain cho cả hai cách đặt record, và câu "remains open" ở Mục 6.3.4
  được thay bằng kết quả. Trượt thì bài nói trên khoá SRP nên dùng lazy cho model đó.
- H24d, H24e, H24f đạt ở cả hai model: điều kiện thứ nhất của Mục 6.3.4 trở thành kết quả có đăng ký trước, với phần mất
  đường là cơ chế. Chỉ đạt ở một model hoặc một độ đo: bài báo đúng phạm vi đó. Không đạt: bài bỏ câu nói rằng lợi ích của
  đường cũ phụ thuộc placement và báo hai kết quả cạnh nhau.
- Ngoài tiêu chí, analyze in KTC của drain − lazy trên SRP. Độ đo nào có cận dưới lớn hơn 0 thì bài nói dual migration
  cũng có lợi trên khoá SRP ở độ đo đó; ngược lại bài nói trên khoá SRP lazy đã gần đủ cho model đó. Phần này là mô tả,
  không phải tiêu chí.

**Dự đoán trước khi chạy** (để sau này đối chiếu, không dùng để chấm). H22a, H22d, H22e: khoảng 98% mỗi ô. H22b: khoảng
95% mỗi ô, riêng hai ô MiniLM trên code 20k khoảng 90%; đạt cả 20 ô khoảng 80%. H22c: khoảng 97% mỗi ô. H23a: 90%
(e5-large), 95% (Arctic), 65% (MiniLM). H23b: 95%, 95%, 85%. H23c: 90%, 95%, 95%. H23d: 85% đến 90% mỗi model. H23e: 85%
mỗi model. H23f: 95% mỗi model. H24a: 95% (bge-base), 90% (e5-large). H24b: 95%, 90%. H24c: 95% mỗi model. H24d: 85%
(bge-base), 95% (e5-large). H24e: 55%, 90%. H24f: 85%, 90%.

## 3. Phần thăm dò, kế hoạch phân tích chốt trước

Phần này không có ngưỡng.

- **E1. Bảng C3 trên khoá SRP (pha U).** Với mỗi model, mọi chính sách, cạnh số của placement học trên cùng seed: giữ
  riêng, rerank trên dòng, payload, nhúng lại do truy vấn và do nền, dual ở cuối, record đỉnh, byte đỉnh, peer và ứng viên
  mỗi truy vấn, mất đường, phần query giữ riêng kém static. Hiệu ghép cặp trên SRP: drain với lazy, static, k1, lazy+keep,
  full; k1 với lazy; lazy với static. Hiệu của hiệu (học trừ SRP) cho drain − lazy và k1 − lazy.
- **E2. Bảng như Bảng 10 cho e5-large, Arctic, MiniLM (pha D).** Cùng các cột của pha D đợt 13; phần dual ở cuối và tỉ lệ
  payload trên đường truy vấn so với lazy (các cận của H5 và H10d vốn đặt cho k1).
- **E3. Migrate tới khi xong (pha C).** Mỗi ô, mọi chính sách: diện tích, rerank [0, T), payload, peer, byte đỉnh so với
  mức đầu, lượt xong so với T. Các hiệu không nằm trong H22: drain − k1 (diện tích, rerank), drain − full (diện tích),
  drain − rebuild (rerank), byte đỉnh của drain so với rebuild. Khoảng qua 20 ô đặt cạnh khoảng của đợt 11.
- **E4. Full ở cùng số peer (pha B).** Full với T = 16 trên dòng của Bảng 10 (bge-base, seed 26 đến 35): giữ riêng, rerank
  trên dòng, peer, ứng viên; hiệu ghép cặp drain − full(T = 16), k1 − full(T = 16), full(T = 16) − full(T = 8).
- **E5. Churn và lỗi peer có drain (pha F).** Như E6 của đợt 11, thêm lazy+keep và drain: giữ riêng cuối dòng, rerank trên
  dòng, phần corpus mất mọi đường, số bản ghi sửa và keep-alive mỗi truy vấn so với static, phần giữ riêng mất đi so với
  cùng seed không churn.
- **E6. Độ nhạy theo số object mỗi peer (pha O).** Code 100k trên 5.000 peer, 5 không gian × seed 26 đến 28, đặt cạnh số
  của đợt 11 ở 50.000 peer (cùng seed, cùng khoá, chỉ khác overlay): hiệu của `itq_q+cap16` với `srp_c+cap16` ở cùng số
  ứng viên (định nghĩa của H15), của `itq_q+cap16` với `itq_q` (H20b), Δ_peer của `srp` với `itq_q+cap16` (H19) cùng nhóm
  qf của quy tắc; ở (L = 5, T = 8): final, rerank@20, ứng viên, peer, phần truy vấn tới peer nóng nhất, phần record của 1%
  peer tải cao nhất, tải lớn nhất so với trung bình, phần record bị dời. Tiền tố probe giữ 16 bit như mọi đợt trước.

## 4. Quy tắc

- Không thêm chính sách, tham số hay biến thể mới dựa trên kết quả đợt 14.
- Job lỗi kỹ thuật thì chạy lại nguyên trạng (`SKIP_DONE=1` chỉ bỏ qua job đã có file kết quả đọc được).
- Nếu phải sửa lỗi code thì ghi diff và lý do vào mục 5 của file này, kèm commit mới. Mọi kết quả trước lần sửa vẫn được
  giữ.
- Pha R chạy bằng `rerun_prev.py` trên file `probeV13_code100kfq_bgebase_s26_cap16.json` của đợt 13: 10 run phải trùng
  từng số và lượt mới phải có đủ mọi run của lượt cũ. Nếu pha R lệch, toàn bộ đợt 14 chỉ còn giá trị thăm dò cho tới khi
  tìm ra nguyên nhân.
- Tự kiểm trong lúc chạy và trong analyze:
  - pha D: các run trùng tên với file đợt 11 cùng seed (`probeV11_code100kfq_<model>_s<seed>_cap16.json`) phải trùng từng
    số; file nào lệch thì không dùng để chấm;
  - pha F: các run trùng tên với file churn của đợt 11 cùng seed phải trùng từng số;
  - pha B: index native ở T = 16 trùng điểm (L = 5, T = 16) của `probeP11` với seed 26 đến 28;
  - pha O: các thống kê bit của mỗi biến thể (không phụ thuộc số peer) trùng file `probeP11` cùng seed;
  - drain không retire bản E0 nào trước khi gỡ; ở pha C mọi checkpoint sau lượt xong trùng full và rebuild trước lượt xong
    trùng static; nhúng lại do truy vấn cộng do nền bằng `new`;
  - mọi file của pha U ghi `e1_place = u` và không có giới hạn tải; mọi file của pha D, C, F, B ghi `itq_q` với cap 16.

## 5. Sửa đổi sau khi bắt đầu chạy

Chưa có.
