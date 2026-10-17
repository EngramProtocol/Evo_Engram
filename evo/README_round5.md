# Đợt 5: chạy thêm theo góp ý của thầy

Đợt này là thăm dò, không thuộc đánh giá xác nhận của đợt 4 và không đổi thuật toán. Hai câu hỏi:

**1. ADR có cần embedding M0 đầy đủ không?** Ở đợt 4, `W_r`, `W_f` và hiệu chỉnh PROB học trên cặp
`(E0[S], E1[S])` và khi học lại trên `(E0[M], E1[M])`, với `E0` đọc từ `*_corpus_embeddings.npy`. Trong
triển khai thật, record E0 chỉ còn PQ code. Đợt 5 thay vế M0 bằng bản tái tạo PQ `c_o`
(`--pair-src pq`). Re-indexer đọc được `c_o` từ chính record E0 (PQ code cùng codebook công khai) trước khi
xoá record đó, nên sau khi chỉ mục cũ đã dựng thì không bước nào còn cần M0. Chỉ mục E0 vẫn dựng từ
embedding M0 thật, vì record cũ đã được đặt như vậy từ trước. H1 đến H4 được chấm lại bằng đúng hàm của
`analyze_prereg.py`.

**2. Recall đo từ lookup lặp thật.** 08 đo chi phí bằng lookup thật nhưng lấy recall từ probe, mà probe giả
định mỗi khoá chạm đúng K node XOR-gần nhất. `09_sim_e2e.py` dựng ứng viên từ đúng tập node mà Ripple Search
trong SimPy trả về, rồi gộp PROB và rerank như cũ. Script đo hai chế độ:

- trạng thái cố định `f = 0, 0.1, 0.5, 0.9, 1`, với recall oracle và recall thật ghép cặp trên 300 query;
- dòng Zipf(1) 3.000 lượt vòng kín cho static, lazy và bg, trong đó gợi ý migrate lấy từ pool thật.

## Thay đổi code (tag `evo-r5-v1`)

- **`03c`, `04b`, `06`.** Thêm `--pair-src exact|pq`.
  - Mặc định `exact` giữ đúng từng số của đợt 4: chạy thử trên dữ liệu giả cho 0 khác biệt.
  - File ra của chế độ `pq` có thêm hậu tố `_pq`.
  - Tự kiểm của chế độ `pq`: mọi nhánh không dùng adapter phải trùng file exact cùng seed.
- **`09_sim_e2e.py` (mới).** Tự kiểm ba điểm:
  - chất lượng oracle trùng 04b;
  - dựng ứng viên từ tập node của oracle phải trùng oracle;
  - dòng vòng kín chạy với tập node oracle phải trùng 06.
- **Thêm mới:** `analyze_r5.py`, `run_round5.sh`, `SHA256SUMS_round5`.
- **`08` và các file khác:** không đổi.

## Các bước

**Trên laptop** (repo Evo_Engram, nhánh `main`, đang ở commit `20e303e`):

```bash
git checkout main && git pull
git am ~/Downloads/0001-evo-dot-5*.patch
git tag -a evo-r5-v1 -m "dot 5: ADR tu ban tai tao PQ, recall tu lookup that"
git push origin main --tags
```

**Trên server:**

```bash
ssh research@103.67.203.71
cd ~/Evo_Engram
git fetch origin --tags && git checkout evo-r5-v1
sha256sum -c evo/SHA256SUMS_round5
tmux new -s round5 -d "bash ~/Evo_Engram/evo/run_round5.sh"
tail -f evo/r5_logs/jobs.log
```

File chưa track trên server (`probe*.json` của các đợt trước) giữ nguyên và được dùng để tự kiểm.

Thời gian ước tính:

| pha | nội dung | số job | ước tính |
|---|---|---|---|
| A | cặp học PQ: 04b, 03c, 06 | 45 | khoảng 3 giờ, P = 2 |
| B | recall từ lookup thật | 12 | khoảng 2,5 giờ, P = 4 |

Chạy riêng một pha bằng `PHASES="A"` hoặc `PHASES="B"`.

**Khi xong.** Gửi lại `evo/round5_all.txt`. Nếu tiện, gửi thêm gói kết quả:

```bash
tar czf ~/evo_round5_results.tar.gz probe*_pq.json probeE2E_*.json evo/r5_logs evo/round5_all.txt evo/r5_model_revisions.txt
```
