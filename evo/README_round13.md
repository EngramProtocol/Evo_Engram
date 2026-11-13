# Đợt 13: ba phép đo theo nhận xét của thầy về bản thảo C1 đến C3

Thầy nêu ba vấn đề với bản thảo C1 đến C3 (ngày 13/11):

1. **C1.** Bản thảo ước lượng qf (và p) bằng 300 query đánh giá với toàn corpus. Đó là rò rỉ đánh giá, và người vận hành
   không có những thứ đó lúc phải chọn placement.
2. **C2.** Giới hạn tải đặt record tràn vào một peer khác trong K = 20 peer gần khoá nhất, với lập luận rằng mọi lookup đều
   hỏi đủ K peer đó. Nhưng lookup lặp trong mô phỏng chỉ tìm được khoảng 78 đến 85% của K peer (Mục 5.3).
3. **C3.** Bảng 10 đo chi phí của dual migration với quy tắc k1, trong khi phương pháp bản thảo khuyến nghị là drain.

Đợt này đo lại đúng ba chỗ đó. Không cần GPU, không nhúng lại, không đổi số nào của các đợt trước. Thầy chưa duyệt; nhóm
chạy trước. Cách đọc từng phần ghi ở mục "Cách đọc" dưới đây và chốt ở tag `evo-r13-prereg` trước khi chạy;
`analyze_r13.py` in dòng ĐỌC theo đúng cách đó.

| pha | nội dung | số job | thời gian ước tính |
|---|---|---|---|
| D | drain (`lazyVbgDinf`) trên dòng 3.000 lượt của code 100k, đúng cấu hình Bảng 10 (bge-base, itq_q+cap16, Zipf 1, 50.000 peer), seed 26 đến 35, cùng các chính sách của Bảng 10 | 10 | 15 đến 25 phút mỗi job |
| R | kiểm hồi quy: chạy lại một job migrate tới khi xong của đợt 12 (code 20k bge-base, seed 36) bằng code mới; phải trùng từng số | 1 | 15 phút |
| L | lookup lặp tới khoá ngẫu nhiên: xác suất tìm thấy peer theo hạng XOR; 50.000 và 10.000 peer, seed 1 đến 5, 5.000 lookup mỗi job | 10 | dưới 2 phút mỗi job |
| Q | p và qf với bộ ước lượng triển khai được, trên mọi file `probeA11_*`, `probeA12_*` (17 cặp của đợt 11 và 22 cặp của đợt 12, 3 seed mỗi cặp) | 117 | vài giây tới một phút mỗi job |

Tổng 138 job, ra 138 file json. Với 4 job song song trên node-dal-02, ước tính khoảng 1 đến 1,5 giờ, phần lớn là pha D
(các job C3 cùng loại của đợt 11 mất 19 đến 33 phút cho 20 run; job của đợt này chạy 10 run).

## Thay đổi code (tag `evo-r13-prereg`)

- **`11_probe_safe.py`.** `lazyVbgDinf` chạy được cả khi không có `--bg-finish`, tức trên dòng truy vấn không có hạn chót
  như ablation code 100k của đợt 11: không bao giờ retire bản E0. Ngân sách nền ghép như k1 (`lazyVbgD`), nhưng với
  lazy+keep (`lazyD`, không retire) thay cho lazy+delay (`lazyV1`): tốc độ nền = (số record lazy công bố − số record
  lazy+keep công bố) / số lượt, nên tổng số lần nhúng lại mỗi lượt xấp xỉ của lazy, như các dòng dual khác của Bảng 10.
  Chỉ đổi phần lập kế hoạch chạy: một nhánh mới cho `lazyVbgDinf` khi không có `--bg-finish`; trước đây chính sách này bị
  bỏ qua ở chế độ đó. Với `--bg-finish`, mọi thứ như đợt 11, 12.
- **`13_qf_deployable.py`** (mới). Đọc một file probeA, nạp embedding, dựng lại đúng mẫu S và tách query như
  `10_probe_placement.py`, rồi tính:
  - bộ ước lượng cũ, cùng bộ sinh số ngẫu nhiên, để tự kiểm: phải trùng từng số với file probeA (in `4/4 số trùng`);
  - bộ ước lượng triển khai được: p trên mọi cặp document trong S; qf giữa 200 query validation và S; cosine TB trên S và
    dạng trường trung bình;
  - phần tách: qf của query đánh giá với S, và của query validation với toàn corpus, để biết sai lệch đến từ mẫu document
    hay từ tập query.
- **`13_lookup_rank.py`** (mới). Dựng overlay đúng như `Net.__init__` của `08_sim_evo.py` (id ngẫu nhiên 63 bit, join rồi
  một vòng refresh, k-bucket 20) và chạy lookup lặp đúng tham số của bộ mô phỏng (alpha 3, K 20, tối đa 20 vòng,
  `STOP_RULE=stable`, `FRONTIER_SCOPE=all`) từ một node ngẫu nhiên tới một khoá ngẫu nhiên. Với mỗi lookup, so tập trả về
  với K peer gần khoá nhất thật và ghi hạng nào được tìm thấy. Không cần embedding.
- **Thêm mới:** `analyze_r13.py`, `run_round13.sh`, `README_round13.md`, `SHA256SUMS_round13`. `10_probe_placement.py`,
  `rerun_prev.py`, `me_common.py`, `src/` không đổi.

## Cách đọc (chốt trước khi chạy)

**C1 (pha Q).** Sai số tính như H21: TB theo seed của từng cặp, rồi |log10(dự đoán / đo)|, rồi TB trên các cặp. Số đo vẫn
là số đo thật trên toàn corpus với 300 query đánh giá, nên với bộ ước lượng mới, phần đánh giá không còn dùng để dự đoán.

- Nếu trên 10 cặp mới của đợt 12 sai số TB của bộ ước lượng triển khai được không quá 0,2 (ngưỡng của H21) với cả p và
  qf: bản thảo dùng bộ ước lượng này làm cách tính chính ở Mục 4.3, báo sai số mới ở Mục 6.1 và Bảng S1, và ghi rằng số cũ
  dùng query đánh giá.
- Nếu vượt 0,2: bản thảo báo cả hai, nói rõ phần lệch đến từ mẫu S hay từ tập query (cột tách), và coi số cũ là kết quả
  có rò rỉ.

**Quy tắc qf, H19 (pha Q).** Nhóm của mỗi cặp tính lại theo qf triển khai được, với đúng hai ngưỡng cũ (SRP khi qf ≥ 8 ×
10^-4, placement học khi qf ≤ 2 × 10^-4). Δ_peer giữ nguyên (probeP12).

- Nếu cả 10 cặp mới giữ nguyên nhóm: kết quả kiểm trước của H19 giữ nguyên, và bản thảo ghi thêm rằng chấm lại sau (post
  hoc) bằng bộ ước lượng chỉ dùng S và query validation cho cùng quyết định ở cả 10 cặp.
- Nếu có cặp đổi nhóm hoặc rơi vào giữa hai ngưỡng: quy tắc qf được ghi là thăm dò; bản thảo báo số cặp đổi và số
  khuyến nghị đúng với qf triển khai được.
- 17 cặp của đợt 11 (gồm 5 cặp code 100k) chỉ là thăm dò, vì quy tắc được đặt ra sau khi xem chúng.

**Giới hạn tải với lookup lặp, C2 (pha L).** Record tràn nằm ở peer hạng r > 1 trong K peer gần khoá nhất, nên lookup lặp
tìm nó với xác suất P(r) thay vì P(1). Record tràn vào peer còn chỗ đầu tiên theo thứ tự XOR, nên phần lớn nằm ở hạng gần.
Chặn trên của phần record mất thêm vì giới hạn tải = (phần record bị dời) × (P(1) − TB của P ở 5 hạng xa nhất, 16 đến 20);
phần record bị dời lấy từ các file probeP11, probeP12 (itq_q+cap16) cùng số peer. Không dùng hạng thấp nhất cho chặn trên,
vì phép lấy min trên 19 hạng bị nhiễu kéo xuống; analyze vẫn in cả số đó.

- Nếu P(r) chênh với P(1) không quá 3 điểm ở mọi r và chặn trên dưới 0,1% record: bản thảo sửa câu "mọi lookup đều hỏi đủ
  K peer" ở Mục 4.4 thành: lookup lặp tìm peer ở hạng xa với gần cùng xác suất như peer gần nhất, nên giới hạn tải không
  làm record tràn khó tìm hơn đáng kể; bảng P(r) vào Supplementary.
- Nếu không: bản thảo báo phần mất thêm như một chi phí của giới hạn tải.
- Phần K peer mà lookup lặp không tìm được, và phần lookup không tìm được peer nào trong K, là giới hạn của lookup lặp áp
  lên mọi record chứ không riêng record tràn; Mục 5.3 đã báo ảnh hưởng của nó lên recall.

**Chi phí của drain, C3 (pha D).** Đây là phép đo chi phí, không có ngưỡng đạt hay không đạt. Bảng 10 thêm dòng drain
(và lazy+keep), giữ dòng k1; bản thảo báo TB 10 seed và khoảng tin cậy 95% của hiệu drain − k1 ghép theo seed. Đoạn văn
đầu Mục 6.4 đổi từ chi phí của k1 sang chi phí của drain (dual cuối dòng, record đỉnh, byte đỉnh, số peer, payload), và
ghi k1 là một thiết lập lưu trữ. Nếu tự kiểm của một job không KHỚP với đợt 11, số của job đó không dùng.

## Chạy thử

Đã chạy thử trên dữ liệu giả của đợt 11, 12, và trên số thật của đợt 11, 12 ở những chỗ không cần embedding:

- **Hồi quy.** Pha D trên dòng 600 lượt, 3.000 peer: 9 chính sách cũ trùng từng số với lượt chạy thử của đợt 11 ở 1.702
  giá trị; placement trong 11 trùng 10 ở 5/5 giá trị. Pha R (migrate tới khi xong, có drain với `--bg-finish`): trùng
  lượt chạy thử của đợt 12 ở 3.905 giá trị, đủ 20/20 run.
- **Drain trên dòng.** Không retire lần nào trên cả dòng (retire = 0 dù E1 thấy object dual 10.685 lần); tổng số lần nhúng
  lại mỗi lượt bằng của lazy.
- **Bộ ước lượng cũ dựng lại** trùng từng số với file probeA ở 23/23 file giả (92 số).
- **Analyze trên số thật.** Cho analyze đọc các file probeQ13 dựng từ số của bộ ước lượng cũ trong 117 file probeA thật,
  cùng 117 file probeP thật: tính lại đúng số của bản thảo, gồm sai số log10 TB 0,062 và 0,063 (p, qf) trên 10 cặp mới
  của đợt 12, 0,079 và 0,077 trên 22 cặp, 0,106 và 0,102 trên 5 cặp mới của đợt 11; H19 khuyến nghị đúng 10/10 cặp mới và
  22/22 cặp, Spearman +0,964 và +0,955; quy tắc theo p với cùng ngưỡng đúng 21/22, Spearman +0,901. Trên dữ liệu giả, nhánh
  ĐỌC khi có cặp đổi nhóm cũng chạy đúng.
- **Lookup lặp** không phụ thuộc dữ liệu, nên lượt chạy thử cho số thật: 50.000 peer, seed 2, 5.000 lookup tìm được 78,5%
  của 20 peer gần nhất, P(1) = 78,9%, TB của P ở hạng 16 đến 20 là 77,6%; job mất 84 giây và 263 MB bộ nhớ. Hai lần chạy
  cùng seed cho cùng từng số.
- **Cả `run_round13.sh`** trên dữ liệu giả (27 job: 1 ở D, 1 ở R, 2 ở L, 23 ở Q): mọi job thoát mã 0. `PHASES=S` chỉ chạy
  analyze; `PHASES=L` chỉ lập 10 job của pha L.
- **Dry run với cấu hình thật** (python giả, tên file thật của đợt 11, 12): 138 job (D 10, R 1, L 10, Q 117). Lệnh của
  pha D trùng lệnh của đợt 11 trừ `--policies`, `--zipf`, `--check-prev` và `--out`.

Trừ hai mục dùng số thật (analyze trên số thật, lookup lặp), số ở lượt chạy thử không có ý nghĩa, vì dữ liệu giả không
phản ánh dữ liệu thật.

## Các bước

**Trên laptop:**

```bash
cd Evo_Engram
git checkout main && git pull
git log --oneline -1                     # phải là: b420492 evo: dot 12, xac minh manh hon cho C3, ...
git am ~/Downloads/0001-evo-dot-13*.patch
sha256sum -c evo/SHA256SUMS_round13      # 13 dòng OK (máy Mac: shasum -a 256 -c ...)
git tag -a evo-r13-prereg -m "dot 13: qf trien khai duoc, lookup lap theo hang, chi phi cua drain"
git push origin main --tags
```

**Trên server** (mọi lệnh chạy trong thư mục repo):

```bash
cd ~/Evo_Engram
git status --short | grep -v '^??'       # không in gì
git fetch origin --tags && git checkout evo-r13-prereg
git describe --tags                      # evo-r13-prereg
sha256sum -c evo/SHA256SUMS_round13
ls probeV11_code100kfq_bgebase_s{26..35}_cap16.json | wc -l      # 10 (đợt 11)
ls probeV12F_code_bgebase_s36_cap16.json                         # đợt 12
ls probeA11_*.json | wc -l; ls probeA12_*.json | wc -l           # 51 và 66
ls probeP11_*.json | wc -l; ls probeP12_*.json | wc -l           # 51 và 66
[ -f venv/bin/activate ] && source venv/bin/activate
python3 -c "import simpy; print('simpy OK')"                     # pha L cần simpy, như 08_sim_evo.py
tmux new -s round13 -d "bash ~/Evo_Engram/evo/run_round13.sh"
```

Nếu dòng `import simpy` báo lỗi, cài trước khi chạy: `pip install simpy` (trong venv).

Thiếu file của đợt trước nào thì job tương ứng tự bỏ phần so (pha D), tự bỏ qua (pha R) hoặc không có (pha Q), và dòng
`THIẾU` hay `bỏ qua` nằm trong `evo/r13_logs/jobs.log`.

**Kiểm trong lúc chạy.**

1. Khoảng 10 giây sau:

   ```bash
   head -8 evo/r13_logs/jobs.log
   ```

   Phải có `NCPU=8  P=4`, `numpy ...`, `HEAD = tag evo-r13-prereg`, `Q: 117 file probeA`, `đợt 13: 138 job, P=4`, và
   không có `DỪNG` hay `THIẾU`.

2. Sau khoảng 25 phút, bốn job đầu của pha D xong:

   ```bash
   grep -H "so với lượt cũ\|    lệch:" evo/r13_logs/d13_*.log
   ```

   Mỗi job một dòng kết thúc bằng `KHỚP`. Nếu có `LỆCH` hay `lệch:`, báo em ngay.

3. Tiến độ và lỗi, xem lúc nào cũng được:

   ```bash
   grep -c "mã thoát" evo/r13_logs/jobs.log         # số job đã xong
   grep "mã thoát [1-9]" evo/r13_logs/jobs.log      # job lỗi, phải không in gì
   tail -3 evo/r13_logs/jobs.log
   ```

**Khi xong** (dòng cuối `jobs.log` là `XONG ĐỢT 13 ...`):

```bash
cd ~/Evo_Engram
grep -c "mã thoát" evo/r13_logs/jobs.log         # 138
grep "mã thoát [1-9]" evo/r13_logs/jobs.log      # không in gì
grep "ĐỌC" evo/round13_all.txt
sed -n '/^Tự kiểm/,/   D: [0-9]/p' evo/round13_all.txt
tar czf ~/evo_round13_results.tar.gz probeQ13_*.json probeV13_*.json probeVR13F_*.json probeL13_*.json \
    evo/r13_logs evo/round13_all.txt
tar tzf ~/evo_round13_results.tar.gz | grep -c json   # 138
```

Phần tự kiểm phải cho: pha Q 117 file, dựng lại bộ ước lượng cũ 468 số `KHỚP`, 200 query validation mỗi file, 39/39 cặp
đủ seed, không cặp nào thiếu probeP; pha R `KHỚP`, đủ 20/20 run của lượt cũ; pha D 10/10 file `KHỚP` với đợt 11.

Lấy file về laptop (thay `node-dal-02` bằng tên máy anh vẫn dùng để ssh):

```bash
scp node-dal-02:~/evo_round13_results.tar.gz ~/Downloads/
```
