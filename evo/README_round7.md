# Đợt 7: thăm dò cho bản nâng cấp sau desk reject của JNCA

JNCA từ chối bài ở vòng biên tập vì đóng góp mới và độ sâu kỹ thuật chưa đủ. Đợt này thăm dò ba hướng có thể
thành đóng góp mới. Đây là pilot chưa đăng ký trước, không thuộc đánh giá xác nhận. Hướng nào cho tín hiệu rõ
mới đưa vào một đợt xác nhận đăng ký trước sau đó.

**1. Mô hình dị hướng có giải thích được điểm nóng tải của khoá SRP không?** Đợt 4 cho thấy khoá SRP không trừ
tâm dồn record vào ít peer. Ở e5-large, 1% peer giữ 83% record. Mô hình: với cosine trung bình giữa hai
document là c, mỗi bit SRP lệch theo p = Phi(Z sqrt(c / (1 − c))). Từ đó dự đoán được số bucket 16 bit hiệu
dụng. `10_probe_placement.py` đo số bucket thật, tải lưu trữ và tải truy vấn theo peer. Phép đo chạy trên
code100kfq, code 20k và SciFact, với ba model M1 và M0, tổng cộng 12 cặp (dataset, model).

**2. Placement học trên mẫu S có tốt hơn SRP ngẫu nhiên ở cùng chi phí không?** Re-indexer vốn đã nhúng lại mẫu S
để học adapter, nên có thể học luôn cách đặt record cho epoch mới. Các biến thể:

- trừ tâm;
- PCA kèm quay ngẫu nhiên;
- ITQ.

Mỗi bit dùng ngưỡng trung vị trên S. Các tham số này đi trong epoch descriptor. Mỗi biến thể chạy với L = 5 và
10 bảng, T = 2, 4, 8, 16 probe. So sánh ở cùng số ứng viên và cùng số peer phải hỏi, trên đường biên Pareto.

**3. Migrate an toàn có giữ được recall khi index native yếu không?** `11_probe_safe.py` công bố record E1 nhưng
giữ bản E0 cho tới khi index native tự tìm lại object đó qua khoá E1 c lần (verify-then-retire). Khi công bố
bản E1, re-indexer ghi thêm mã PQ E1 vào record E0 cũ. Nhờ vậy client chấm object dual bằng ADC native, dù tìm
thấy qua khoá nào. Các chính sách:

- static, lazy và bg như đợt 4;
- lazyD (không bao giờ retire, cận trên của recall);
- lazyV1, lazyV2 (retire sau 1 hoặc 2 xác nhận);
- bgV1, bgV2 (nền ngẫu nhiên, cùng số record công bố với lazyV).

Đo thêm lưu trữ thừa của object dual, số xác nhận và số object dual nhận từ phía E0.

Cả hai probe báo thêm một chỉ số liên quan theo tác vụ: hàm gốc của query (`source_corpus_index` trong GT của
M0, code100kfq) có nằm trong top-5 không.

## Thay đổi code (tag `evo-r7-pilot`)

- **Thêm mới:** `10_probe_placement.py`, `11_probe_safe.py`, `analyze_r7.py`, `run_round7.sh`,
  `SHA256SUMS_round7`, `README_round7.md`.
- **Các file khác:** không đổi. Hai probe mới chỉ import `me_common.py`, nên kết quả đợt 1 đến 6 giữ nguyên.
- **Tự kiểm:**
  - `10`: srp, srp_c, srp_cq ở L = 5, T = 8 phải trùng từng số E1ONLY, E1ONLY_c, E1ONLY_cq của
    `probeG_*` đợt 4 ở f = 1. Các số so là reach, final, rerank@20, ứng viên và peer.
  - `11`: static, lazy, bg phải trùng từng số `probeL_*_ku.json` đợt 4. Các số so là totals, cửa sổ và
    snapshot giữ riêng.

Đã chạy thử đủ 47 job trên dữ liệu giả (N = 1.500, 3.000 node). Mọi job thoát mã 0. Mọi tự kiểm có file đối
chiếu đều KHỚP: 9 job pha A so 15 giá trị mỗi job, 9 job pha B so 372 giá trị mỗi job. Dữ liệu giả gần đẳng
hướng, nên số liệu của lượt chạy thử không nói gì về kết quả thật.

## Các bước

**Trên laptop** (repo Evo_Engram, nhánh `main`):

```bash
cd Evo_Engram
git checkout main && git pull
git am ~/Downloads/0001-evo-dot-7*.patch
git tag -a evo-r7-pilot -m "dot 7: tham do placement va migrate an toan"
git push origin main --tags
```

**Trên server:**

```bash
ssh <server>
cd ~/Evo_Engram
git fetch origin --tags && git checkout evo-r7-pilot
sha256sum -c evo/SHA256SUMS_round7
tmux new -s round7 -d "bash ~/Evo_Engram/evo/run_round7.sh"
tail -f evo/r7_logs/jobs.log
```

Script dừng nếu thiếu `probeG_code100kfq_*` hoặc `probeL_code100kfq_*_ku.json` của đợt 4 ở thư mục gốc repo.
Pha C tự bỏ qua cặp nào thiếu dữ liệu và ghi lý do vào `jobs.log`.

Thời gian ước tính trên node-dal-02, 4 job song song, mỗi job 1 luồng:

| pha | nội dung | số job | mỗi job |
|---|---|---|---|
| B | migrate an toàn, 3 cặp x seed 3 4 5, cộng 2 ablation Arctic | 11 | khoảng 60 đến 90 phút |
| A | placement code100kfq, 4 không gian x seed 3 4 5 | 12 | khoảng 30 đến 45 phút |
| C | placement code 20k và SciFact, 4 không gian x seed 3 4 5 | 24 | vài phút |

Tổng cộng khoảng 6 đến 8 giờ. Chạy riêng một phần bằng `PHASES="A"`, `PHASES="B"`, ... Dòng
`đợt 7: ... job` trong `jobs.log` phải là 47 khi đủ dữ liệu cho pha C.

**Khi xong.** Gửi lại `evo/round7_all.txt` và gói kết quả:

```bash
cd ~/Evo_Engram
tar czf ~/evo_round7_results.tar.gz probeP_*.json probeV_*.json evo/r7_logs evo/round7_all.txt
tar tzf ~/evo_round7_results.tar.gz | grep -c json
```

Lệnh thứ hai in số file json, bằng số job (47 khi đủ dữ liệu).
