# Đợt 6: kiểm soát lookup và lịch migrate, kiểm tra tích hợp PQ + lookup thật

Đợt này là thăm dò theo góp ý của thầy sau đợt 5, không thuộc đánh giá xác nhận và không đổi thuật toán.
Ba câu hỏi:

**1. Phần nào của chênh lệch lazy − bg đến từ cách đo, phần nào đến từ lịch migrate?** Ở đợt 5, lượt lookup
thật khác lượt probe ở hai chỗ cùng lúc. Recall đo trên tập node mà lookup tìm lại. Lịch migrate của lazy cũng
lấy từ pool của chính lookup đó. Đợt 6 ghi lại lịch migrate của từng lượt (record nào migrate ở lượt nào) rồi
phát lại chéo:

| | đo bằng probe | đo bằng lookup thật |
|---|---|---|
| lịch của probe | PP (lượt probe đợt 5, trùng 06) | PL (mới) |
| lịch của lookup thật | LP (mới) | LL (lượt lookup thật đợt 5) |

Thêm một lượt LL2: phát lại lịch của lookup thật và đo lại bằng lookup thật, với node gốc ngẫu nhiên khác.
Chênh LL2 − LL là nhiễu của chính lookup, làm mốc khi đọc các ô còn lại. Chạy cho code100kfq × bge-base,
e5-large, Arctic × seed 3 4 5.

**2. Dấu của lazy − bg ở bge-base 100k có ổn định không?** Thêm seed 6 đến 12 cho bge-base 100k, chỉ chạy dòng
lazy và bg, có đủ bốn ô. Tổng là 10 seed. `analyze_r6.py` báo trung bình, độ lệch chuẩn, khoảng tin cậy 95%
theo t, số seed dương và âm, kèm kiểm định dấu.

**3. Adapter học từ PQ và lookup thật có chạy đúng cùng nhau không?** `09 --pair-src pq` học `W_r`, `W_f` và
hiệu chỉnh PROB trên bản tái tạo PQ `c_o`, như 04b và 06 ở đợt 5, rồi đo recall từ lookup thật. Có cả trạng thái
cố định lẫn dòng vòng kín. Chạy cho code100kfq × 3 cặp × seed 3 4 5.

## Thay đổi code (tag `evo-r6-v1`)

- **`09_sim_e2e.py`.** Mặc định giữ đúng từng số của đợt 5. Thêm các cờ:
  - `--pair-src exact|pq`, `--fixed 0|1`, `--factorial 0|1`, `--noise-replay 0|1`, `--check-e2e`.
  - Phát lại chéo chạy sau toàn bộ lượt chính, nên lượt chính dùng đúng chuỗi ngẫu nhiên của đợt 5.
  - File ra là `probeE2F_*` khi bật `--factorial`, và có hậu tố `_pq` khi chạy `--pair-src pq`.
- **Tự kiểm mới:**
  - (4) phát lại lịch probe và đo bằng probe phải trùng lượt probe;
  - (4b) số record mới, f cuối và tỉ lệ GT ở E1 chỉ phụ thuộc lịch, nên mọi lượt phát lại phải trùng lượt gốc
    của lịch đó;
  - (5) khi tham số giống đợt 5, mọi số của trạng thái cố định và của dòng phải trùng `probeE2E_*` đợt 5.
  - Với `--pair-src pq`: (1) so với `probeG_*_pq`, (3) so với `probeL_*_ku_pq`.
- **Thêm mới:** `analyze_r6.py`, `run_round6.sh`, `SHA256SUMS_round6`.
- **Các file khác:** không đổi. `SHA256SUMS_round5` không còn khớp với `09` mới. Muốn chạy lại đợt 5 thì
  checkout tag `evo-r5-v1`.

Đã chạy thử trên dữ liệu giả với đủ 20 job (A, C và hai seed của B). Mọi tự kiểm đều KHỚP. Ở 9 job của pha A,
tự kiểm (5) so 108 giá trị mỗi job với `probeE2E_*` đợt 5 và không lệch số nào, nên lượt chính vẫn y hệt đợt 5.

## Các bước

**Trên laptop** (repo Evo_Engram, nhánh `main`, đang ở tag `evo-r5-v1`):

```bash
cd /home/khanh/Evo_Engram
git checkout main && git pull
git am ~/Downloads/0001-evo-dot-6*.patch
git tag -a evo-r6-v1 -m "dot 6: kiem soat lookup va lich migrate, PQ + lookup that"
git push origin main --tags
```

**Trên server:**

```bash
ssh research@103.67.203.71
cd ~/Evo_Engram
git fetch origin --tags && git checkout evo-r6-v1
sha256sum -c evo/SHA256SUMS_round6
tmux new -s round6 -d "bash ~/Evo_Engram/evo/run_round6.sh"
tail -f evo/r6_logs/jobs.log
```

Các file `probe*.json` của đợt 4 và đợt 5 ở thư mục gốc repo được dùng để tự kiểm và không bị ghi đè.

Thời gian ước tính trên node-dal-02, 4 job song song, mỗi job 1 luồng:

| pha | nội dung | số job | mỗi job |
|---|---|---|---|
| A | bảng 2x2 + mốc nhiễu, 3 cặp x seed 3 4 5 | 9 | khoảng 75 phút |
| C | PQ + lookup thật, 3 cặp x seed 3 4 5 | 9 | khoảng 47 phút |
| B | bge-base seed 6 đến 12, chỉ lazy và bg | 7 | khoảng 40 phút |

Tổng cộng khoảng 6 giờ. Chạy riêng một phần bằng `PHASES="A"`, `PHASES="A B"`, ... Đổi danh sách seed thêm
bằng `BSEEDS`.

**Khi xong.** Gửi lại `evo/round6_all.txt` và gói kết quả:

```bash
cd ~/Evo_Engram
tar czf ~/evo_round6_results.tar.gz probeE2F_*.json probeE2E_*_pq.json evo/r6_logs evo/round6_all.txt
tar tzf ~/evo_round6_results.tar.gz | wc -l
```

Lệnh thứ hai phải in ra 54: 25 file json, thư mục `r6_logs` với 25 log job, `jobs.log` và `jobs.txt`, cùng
file tổng hợp.
