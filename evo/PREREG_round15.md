# Evo-Engram, đợt 15: đăng ký trước cho C3 khi migrate tới khi xong trên khoá SRP gốc

Ngày ghi: 13/11/2026. File này được commit cùng tag `evo-r15-prereg` TRƯỚC khi chạy bất kỳ job nào của đợt 15. Kết quả
được chấm bằng `evo/analyze_r15.py`, cũng commit cùng tag. Mọi kết quả đều được báo cáo, kể cả khi không đạt. Lúc ghi file
này thầy chưa duyệt; nhóm chạy trước. Nếu sau khi xem kết quả thầy đổi ngưỡng hay định nghĩa, phần thay đổi được báo cáo là
thăm dò.

Đợt 14 (H24) đo C3 trên khoá SRP gốc, nhưng chỉ trên dòng 3.000 lượt có ngân sách cố định của code 100k, với bge-base và
e5-large. Bản thảo v7 vì thế ghi ở Limitations rằng trên khoá SRP, C3 mới được thử "on the fixed-budget stream only, not to
completion". Mục 6.3.4 của bản v7 cũng ghi rằng trên SRP, trạng thái đang migrate còn rất xa index hoàn chỉnh (cuối dòng
drain đạt 51,2% và 44,3%, index SRP hoàn chỉnh đạt 66,3% và 85,8%). Đợt 15 chạy thí nghiệm migrate tới khi xong trên khoá
SRP gốc, cho đúng các model mà quy tắc H19 chọn SRP, để trả lời hai câu hỏi:

1. Trên khoá SRP, migrate dần với drain có còn hơn rebuild và hơn không migrate cho tới khi xong không?
2. Khi migrate tới khi xong trên SRP, giữ đường cũ (drain) có còn hơn retire lúc publish (lazy+bg) không? Em dự đoán là
   không ở không gian tập trung mạnh (mục 2), và nếu đúng thì khuyến nghị của bài phải đổi.

Những gì đã biết lúc ghi file này: toàn bộ kết quả của đợt 14, gồm pha C trên placement học với đúng các seed 46 đến 55 dùng
ở đây (mọi chính sách), và H24 trên dòng của code 100k. Chưa có lần chạy migrate tới khi xong nào trên khoá SRP, với bất kỳ
seed nào.

Tách nhân bản với khái quát hoá. H25 là khái quát hoá sang một cách đặt record khác của các so sánh ở pha C. Phía placement
học của các hiệu của hiệu (H25c đến H25e) lấy từ pha C của đợt 14 và đã biết; chỉ các lần chạy trên SRP là mới.

## 1. Phần đóng băng

- Mã nguồn đóng băng là các file trong `SHA256SUMS_round15`. `11_probe_safe.py`, `10_probe_placement.py`, `me_common.py`,
  `rerun_prev.py` và `src/` giữ nguyên như tag `evo-r14-prereg` (và `evo-r13-prereg`): đợt 15 không sửa bộ mô phỏng, chỉ
  thêm `run_round15.sh`, `analyze_r15.py` và hai file mô tả. Pha R kiểm trên dữ liệu thật rằng môi trường hiện tại cho lại
  đúng từng số của đợt 14.
- Overlay, tra cứu, adapter, gộp PROB, mã PQ, định nghĩa các chính sách và các đại lượng đo giữ như `PREREG_round14.md` mục
  1 (và `PREREG_round11.md`, `PREREG_round12.md` mục 1). Tên chính sách: **static**, **lazy**, **full**, **bg**,
  **lazy+bg** (`lazybg`), **rebuild**, **k1** (`lazyVbgD`), **drain** (`lazyVbgDinf`).
- **Cấu hình y như pha C của đợt 14, chỉ đổi cách đặt record E1:** code 20k và SciFact, 10.000 peer, S = 10%, Zipf 1; code
  20k dòng 3.000 lượt với T = 1.500 và 3.000; SciFact dòng 800 lượt với T = 400 và 800; cùng checkpoint và cửa sổ; mỗi
  chính sách gỡ index E0 ngay khi nó xong (`--finish-drop done`); cùng 8 chính sách. Record E1 đặt bằng *khoá SRP gốc*
  (`--e1-place u`, không giới hạn tải), là SRP không trừ tâm của thiết kế gốc và là phương án mà quy tắc H19 chọn khi
  qf ≥ 8e-4.
- **Seed 46 đến 55**, đúng các seed của pha C đợt 14. Overlay, mẫu S, tập query giữ riêng và dòng truy vấn chỉ phụ thuộc
  seed, nên với cùng seed hai cách đặt record E1 thấy đúng cùng một overlay, cùng một dòng và cùng các query giữ riêng.
- **Model.** Pha V (H25): bge-base, e5-large, gte-base, là ba model đích mà quy tắc H19 chọn SRP trên cả code 20k và
  SciFact. Pha W (thăm dò): Arctic và MiniLM, là hai model mà quy tắc chọn placement học. qf dự đoán từ mẫu S và query
  validation (Bảng S1 của bản thảo), code 20k / SciFact: bge-base 1,30e-3 / 2,18e-3; e5-large 1,60e-2 / 1,43e-2; gte-base
  1,24e-2 / 1,32e-2; Arctic 1,51e-4 / 6,20e-5; MiniLM 5,00e-5 / 8,24e-5.
- **Ô.** H25 chấm 12 ô: 3 model × {code 20k với T = 1.500 và 3.000, SciFact với T = 400 và 800}.

## 2. Giả thuyết và tiêu chí đạt

Khoảng tin cậy 95% (KTC) lấy theo phân phối t trên hiệu ghép cặp qua seed. Một tiêu chí chỉ đạt khi ô đó có đủ 10 seed.
Ký hiệu:

- **diện tích [0, T]**: trung bình final R@5 của 100 query giữ riêng trên [0, T], hình thang qua các checkpoint;
- **rerank [0, T)**: rerank@20 trung bình trên các cửa sổ của dòng kết thúc trước hoặc đúng lượt T;
- **mất đường (0, T)**: `lost_retire` trung bình trên các checkpoint c với 0 < c < T (như E3 của đợt 12). `lost_retire`
  là phần vị trí top-5 thật của query giữ riêng có object ngoài S đã mất bản E0, tới được qua phía E0 nếu còn, nhưng không
  tới được qua phía E1. Sau khi một chính sách gỡ E0, đại lượng này bằng phần kết quả mà index cũ tới được còn index mới
  hoàn chỉnh thì không;
- **học**: cùng ô, cùng seed, với placement học (itq_q+cap16), lấy từ file pha C của đợt 14;
- **hiệu của hiệu**: (drain − lazy+bg trên học) − (drain − lazy+bg trên SRP), ghép theo seed.

**H25, C3 khi migrate tới khi xong trên khoá SRP gốc.** Mỗi tiêu chí chấm riêng cho từng ô.

- H25a, so với rebuild: trên SRP, drain − rebuild về diện tích [0, T] có cận dưới KTC lớn hơn +10 điểm. (12 ô)
- H25b, so với không migrate: trên SRP, drain − static về diện tích [0, T] có cận dưới KTC lớn hơn +10 điểm. (12 ô)
- H25c, lợi ích của đường cũ phụ thuộc placement, query chưa thấy: hiệu của hiệu về diện tích [0, T] có cận dưới KTC lớn
  hơn 0. (12 ô)
- H25d, như H25c cho query đang phục vụ: hiệu của hiệu về rerank [0, T) có cận dưới KTC lớn hơn 0. (12 ô)
- H25e, cơ chế: mất đường (0, T) của lazy+bg trên học trừ trên SRP có cận dưới KTC lớn hơn 0. (12 ô)
- H25f, ở không gian tập trung mạnh thì retire lúc publish đã đủ: với e5-large và gte-base (qf dự đoán trên 1e-2), trên
  SRP, drain − lazy+bg về diện tích [0, T] có cận trên KTC nhỏ hơn +1 điểm. (8 ô)

Tổng cộng 68 tiêu chí: H25a đến H25e mỗi tiêu chí 12 ô, H25f 8 ô. Ô thiếu dữ liệu thì ghi là KHÔNG ĐẠT, và job thiếu được
chạy lại theo mục 4.

Biên 1 điểm của H25f là biên đã dùng cho các phép so không kém hơn ở H12a, H18a và H24. H25f đạt nghĩa là drain không hơn
lazy+bg quá 1 điểm; nó không đòi lazy+bg phải hơn drain.

**Số tham chiếu khi đặt ngưỡng.** Trên placement học, cùng 12 ô và cùng seed (pha C của đợt 14): drain − rebuild +14,75 đến
+22,64 (cận dưới KTC nhỏ nhất +13,70); drain − static +16,50 đến +24,75 (+15,24); drain − lazy+bg +2,56 đến +5,39 về diện
tích (+2,16) và +5,97 đến +12,32 về rerank (+4,23); mất đường (0, T) của lazy+bg 13,8 đến 23,8%; lazy+bg xong ở 28 đến 49%
của T, drain ở 53 đến 76%. Ở cùng tiến độ (cùng phần object đã có record E1), drain hơn lazy+bg 2,4 đến 3,6 điểm final giữ
riêng khi 30% object đã chuyển, 4,8 đến 8,7 điểm ở 50% và 8,1 đến 13,8 điểm ở 70%. Trên dòng của code 100k (H24), mất đường
của lazy trên SRP là 7,3% (bge-base) và 2,4% (e5-large) so với 11,3% và 14,8% trên học; drain − lazy trên SRP là +4,9 (KTC
+2,7 đến +7,2) và +1,0 (−0,9 đến +2,8) điểm giữ riêng. Index native hoàn chỉnh ở (L, T) = (5, 8) trên 10.000 peer (file
placement của đợt 11, seed 26 đến 28, 300 query đánh giá), SRP so với học: code 20k 79,6 / 71,4 (bge-base), 92,9 / 64,9
(e5-large), 93,1 / 72,4 (gte-base); SciFact 79,4 / 72,0, 88,6 / 62,8, 90,4 / 73,0. Ở điểm đó SRP chấm 45 đến 86% corpus mỗi
truy vấn, placement học 23 đến 24%.

**Vì sao em dự đoán lazy+bg không kém drain trên SRP ở không gian tập trung mạnh.** Có hai lý do cùng chiều. Một, trên SRP
retire cắt ít đường (H24f), nên phần lợi của việc giữ đường cũ ở cùng tiến độ nhỏ đi. Hai, lazy+bg xong sớm hơn drain, vì
truy vấn của nó kéo về nhiều record cũ hơn (ở ô code 20k, bge-base, T = 1.500 của đợt 11: 6,3 so với 3,0 payload mỗi lượt
trên đường truy vấn); mà trên SRP index hoàn chỉnh cao hơn trạng thái đang migrate rất nhiều, nên xong sớm có giá trị lớn.
Trên placement học thì khác: trạng thái dual gần cuối đọc hai epoch và ngang index hoàn chỉnh (drain − full từ −4,1 đến
+2,0 điểm diện tích ở 12 ô này), nên xong muộn không thiệt. Phép so tới khi xong vì vậy không ghép tốc độ nhúng lại giữa hai
chính sách; E2 và E3 tách phần tốc độ.

**Cách đọc định trước:**

- H25a và H25b đạt ở cả 12 ô: bài viết rằng trên khoá SRP mà quy tắc chọn, migrate dần với drain cũng hơn rebuild và hơn
  không migrate cho tới khi xong, kèm khoảng qua các ô; vế "on the fixed-budget stream only, not to completion" ở
  Limitations được bỏ. Tiêu chí nào trượt ở vài ô thì bài báo số ô đạt, nêu tên ô trượt, và giới hạn câu khẳng định.
- H25c, H25d, H25e đạt ở cả 12 ô: điều kiện thứ nhất của Mục 6.3.4 (giữ đường cũ có lợi khi index mới chọn lọc) đúng cả
  khi migrate tới khi xong, là kết quả có đăng ký trước, với phần mất đường là cơ chế. Chỉ đạt ở một phần: bài báo đúng
  phạm vi đó.
- H25f đạt ở cả 8 ô: bài viết rằng trên khoá SRP ở không gian tập trung mạnh, retire lúc publish kèm migrate nền (lazy+bg)
  không kém drain khi migrate tới khi xong. Câu "We therefore use drain under either placement" ở Mục 6.3.4 và phần hướng
  dẫn ở Mục 7.3 được viết lại: dùng drain với placement học; trên khoá SRP ở không gian tập trung mạnh thì lazy+bg là đủ
  và không tốn thêm lưu trữ. H25f trượt ở ô nào thì bài nêu tên ô đó và giữ drain cho trường hợp đó.
- Với mỗi ô trong 12 ô, analyze in KTC của drain − lazy+bg trên SRP về diện tích và rerank, đọc theo ba mức: cận dưới lớn
  hơn 0 thì bài nói dual migration cũng có lợi trên SRP ở ô và độ đo đó; KTC chứa 0 thì bài nói lazy+bg gần đủ; cận trên
  nhỏ hơn 0 thì bài nói lazy+bg tốt hơn, nêu độ lớn, và dùng E2 để nói bao nhiêu phần là do tốc độ. Phần này là mô tả,
  không phải tiêu chí; nó quyết định câu chữ cho bge-base, là model không nằm trong H25f.
- Trong mọi trường hợp bài ghi rằng phép so tới khi xong không ghép tốc độ nhúng lại: lazy+bg xong sớm hơn vì truy vấn
  kéo thêm nhiều lần nhúng lại hơn.

**Dự đoán trước khi chạy** (để sau này đối chiếu, không dùng để chấm). H25a: 95% mỗi ô. H25b: 97% mỗi ô. H25c: 80% (bge-base),
92% (e5-large, gte-base). H25d: 80% (bge-base), 90% (hai model kia). H25e: 85% (bge-base), 95% (hai model kia). H25f: 80% mỗi
ô, cả 8 ô khoảng 60%. Ước lượng điểm của drain − lazy+bg trên SRP về diện tích: khoảng 0 với bge-base (từ −1,5 đến +1,5),
khoảng −3 đến −6 với e5-large và gte-base.

## 3. Phần thăm dò, kế hoạch phân tích chốt trước

Phần này không có ngưỡng.

- **E1. Bảng mọi chính sách trên SRP, cạnh placement học.** Mỗi ô: diện tích, rerank [0, T), payload và số peer mỗi truy
  vấn trên [0, T), số ứng viên mỗi truy vấn giữ riêng trên [0, T], byte đỉnh so với mức đầu, lượt xong so với T, mất đường
  (0, T). Hiệu ghép cặp trên SRP ngoài tiêu chí: drain với bg, k1, full; lazy+bg với rebuild và static (diện tích); drain
  với k1, rebuild, static (rerank).
- **E2. Cùng tiến độ.** Final giữ riêng nội suy tuyến tính theo phần object đã có record E1 tại 30%, 50% và 70%; drain −
  lazy+bg ghép theo seed, trên SRP và trên học. Phép so này bỏ khác biệt về tốc độ.
- **E3. Cùng cỡ tốc độ.** Drain với nền của hạn chót ngắn so với lazy+bg với nền của hạn chót dài, cả hai tính trên
  [0, T dài] (code 20k: drain với T = 1.500 so với lazy+bg với T = 3.000 trên [0, 3.000]; SciFact: 400 và 800). Khi đó nền
  của drain nhanh gấp đôi. Diện tích và rerank, trên SRP và trên học.
- **E4. Pha W.** Arctic và MiniLM trên khoá SRP: cùng các bảng và hiệu như trên, không chấm. Đây là trường hợp index SRP
  yếu (qf nhỏ), nơi Mục 6.3.4 nói giữ đường cũ có lợi.
- **E5. Theo qf.** Trên 10 cặp (corpus, model): tương quan hạng Spearman giữa qf dự đoán và trung bình qua hai hạn chót
  của drain − lazy+bg trên SRP (diện tích, rerank), của hiệu của hiệu, và của mất đường của lazy+bg trên SRP.

## 4. Quy tắc

- Không thêm chính sách, tham số hay biến thể mới dựa trên kết quả đợt 15.
- Job lỗi kỹ thuật thì chạy lại nguyên trạng (`SKIP_DONE=1` chỉ bỏ qua job đã có file kết quả đọc được).
- Nếu phải sửa lỗi code thì ghi diff và lý do vào mục 5 của file này, kèm commit mới. Mọi kết quả trước lần sửa vẫn được
  giữ.
- Pha R chạy bằng `rerun_prev.py` trên file `probeV14F_code_bgebase_s46_cap16.json` của đợt 14: 13 run phải trùng từng số
  và lượt mới phải có đủ mọi run của lượt cũ. Nếu pha R lệch, toàn bộ đợt 15 chỉ còn giá trị thăm dò cho tới khi tìm ra
  nguyên nhân.
- Tự kiểm trong analyze:
  - mọi file của pha V và W ghi `e1_place = u` và không có giới hạn tải;
  - so với file placement học cùng ô, cùng seed của đợt 14: mọi tham số khác cách đặt record trùng nhau; dòng truy vấn
    trùng nhau (số lượt theo lần xuất hiện của query và số lượt lặp trong từng cửa sổ của run static); N, |S| và tên các
    run trùng nhau;
  - drain không retire bản E0 nào trước khi gỡ; mọi checkpoint sau lượt xong trùng full và rebuild trước lượt xong trùng
    static; nhúng lại do truy vấn cộng do nền bằng `new`; rebuild dựng đủ N − |S| bản ở nền.

## 5. Sửa đổi sau khi bắt đầu chạy

Chưa có.
