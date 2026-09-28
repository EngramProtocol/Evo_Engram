# Gate M0 → M1: thứ tự chạy

Trả lời một câu hỏi duy nhất: **ánh xạ tuyến tính tính trên vector tái tạo từ
PQ code có giữ đủ cấu trúc lân cận để sinh semantic key và PQ code trong không
gian M1 hay không.**

Không sửa simulator ở bước này. Hai script đứng độc lập, không import gì từ repo.

---

## Bước 0. Chốt trạng thái data (2 phút, trên node-dal-02)

```bash
cd ~/V_ENGRAM_SIMULATION && source venv/bin/activate
sha256sum data/*.npy data/*.json > data/MANIFEST.sha256
tar -czf ~/vengram_data_$(date +%Y%m%d).tar.gz data/
```

Từ đây mọi hiệu số đều tham chiếu về bộ artifact này. Codebook `code_pq_codebook_m512.npy`
được dựng lại ngày 18/8 nên đừng dựng lại lần nữa, k-means chỉ tối ưu cục bộ và
số sẽ lệch khỏi mốc cũ.

## Bước 1. Nhúng M1 (Colab T4, ~45 phút mỗi model)

Upload lên Colab: `data/code_corpus_texts.json`, `data/code_ground_truth.json`,
và `01_embed_m1.py`.

```bash
!pip -q install sentence-transformers
!mkdir -p data && mv code_*.json data/

!python 01_embed_m1.py --model intfloat/e5-large-v2   --tag e5large
!python 01_embed_m1.py --model BAAI/bge-base-en-v1.5  --tag bgebase
```

Hai cặp trả lời hai câu khác nhau:

| tag | model | d1 | m1 | câu hỏi |
|---|---|---|---|---|
| `e5large` | intfloat/e5-large-v2 | 1024 | 512 | cùng chiều, khác recipe huấn luyện. **Cặp chính.** |
| `bgebase` | BAAI/bge-base-en-v1.5 | 768 | 384 | cùng họ, khác chiều. Kiểm đường ánh xạ chữ nhật. |

Script tự thêm prefix theo họ model (`query: ` / `passage: ` cho e5, để trống cho
bge đúng như bản V-Engram gốc). Nó cũng tự tính ground truth trong không gian M1,
vì láng giềng đúng của M1 khác M0.

Xem dòng `GT overlap M0 vs M1`. Nếu nó cao trên 80% thì hai model quá giống nhau
và bài toán migration không có gì để giải; nếu dưới 30% thì đây là thay đổi mạnh.

Tải 6 file về, đặt vào `data/` trên server.

## Bước 2. Gate (node-dal-02, CPU, ~15 phút mỗi lần)

```bash
cd ~/V_ENGRAM_SIMULATION && source venv/bin/activate
for tag in e5large bgebase; do
  python3 02_probe_bridge.py --tag $tag --mode gate --seed 20235956 \
      2>&1 | tee gate_${tag}_s20235956.log
done
```

Nếu cặp chính qua ngưỡng thì chạy thêm hai seed để có ghép cặp:

```bash
for s in 1 2; do
  python3 02_probe_bridge.py --tag e5large --mode gate --seed $s \
      2>&1 | tee gate_e5large_s${s}.log
done
```

## Bước 3. Đường chi phí migration (~1 giờ mỗi seed, chỉ chạy nếu gate qua)

```bash
python3 02_probe_bridge.py --tag e5large --mode curve --seed 20235956 \
    --fracs 0.01,0.02,0.05,0.10,0.20,0.50,1.00 \
    2>&1 | tee curve_e5large_s20235956.log
```

Tỉ lệ mẫu `f` vừa là tập huấn luyện bridge vừa là phần đã re-embed, nên `f` chính
là ngân sách migration. Kết quả ra thẳng đường recall theo chi phí, đúng hình F2
trong đề cương.

---

## Đọc kết quả

Bốn tầng đo, theo đúng chuỗi đã thống nhất:

```
(1) góc tới v1 thật        lỗi vector
(2) NN overlap top-5       thuần embedding, chưa qua DHT và chưa qua PQ
(3) anchor trùng khít / trong K peer    placement fidelity
(4) reach và final R@5     qua toàn bộ pipeline
```

Mỗi tầng in hai cột: **từ v0 thật** và **từ v0 tái tạo**. Chênh lệch giữa hai cột
là phần lỗi do lượng tử hoá PQ; phần còn lại là lỗi ánh xạ. Không có cột thứ nhất
thì khi kết quả xấu sẽ không quy được nguyên nhân.

Các nhánh tham chiếu:

| nhánh | nghĩa |
|---|---|
| `null_random` | khoá ngẫu nhiên, sàn |
| `dual_encode` | giữ cả M0 và M1, query bằng M0, không migrate. **Baseline bắt buộc.** |
| `dual_encode_rerank` | như trên + fetch 50 payload mỗi query rồi rerank bằng M1 thật |
| `no_migration` | record ở E0, query M1, không bridge (chỉ hiện khi d0 = d1) |
| `derived_true_v0` | dẫn xuất từ v0 thật, tách lỗi ánh xạ |
| `derived_pq_v0` | **đề xuất**: peer tự dẫn xuất từ PQ code |
| `hybrid` | native cho mẫu S, derived cho phần còn lại |
| `oracle_full` | toàn bộ native E1, trần |

## Ngưỡng dừng, chốt trước khi chạy

Nhìn dòng **anchor trong K peer (từ v0 tái tạo)**, đặt cạnh mốc đã có của trục
projection là 83,8%.

- **trên 60%** → cơ chế đứng, tiến hành trục model, sang bước 3.
- **40 đến 60%** → còn cứu được bằng margin-conditioned placement (đường
  83,8 → 94,6 → 97,7 → 98,6 theo số bản sao). Chạy bước 3 nhưng phải thêm
  nhánh nhiều bản sao trước khi kết luận.
- **dưới 40%** → ánh xạ tuyến tính trên vector tái tạo không dùng được.
  Migration lại đòi writer trực tuyến. Quay về phương án bài chọn ma trận chiếu,
  dùng kết quả đã có.

Kiểm tra chéo: nếu `derived_pq_v0` không vượt `dual_encode` thì đề xuất chưa có
giá trị, bất kể ba tầng đo đầu đẹp tới đâu.

---

## Ghi chú kỹ thuật

`scipy` không có trong venv và script không dùng, mọi thống kê bằng numpy thuần.

`faiss` có, dùng để huấn luyện codebook. Nếu thiếu thì script tự rơi về k-means
numpy, chậm hơn nhiều, chỉ nên dùng khi chạy thử.

Codebook M1 mặc định huấn luyện trên mẫu S, đúng với tình huống thật là người
quản lý collection chỉ re-embed một phần. Khi `|S| < 2000` script tự chuyển sang
huấn luyện trên toàn E1 và in cảnh báo; chỗ đó phải ghi rõ khi báo cáo. Đổi hành
vi bằng `--cb-train full`.

`m1` được tính là `d1 / 2`, nên e5-large cho 512 byte mỗi object đúng bằng M0,
còn bge-base cho 384 byte. Khác biệt này là thật vì không gian M1 ít chiều hơn,
nhưng phải nói trong bài chứ không được lờ đi.

Tất cả tham số overlay giữ đúng cấu hình chính của bài trước: N = 10.000,
L = 5, K = 20, T = 8, c = 16, r = 1, 63 bit khoá.

Mỗi lần chạy ghi một file `probeC_<tag>_<mode>_s<seed>.json` chứa toàn bộ số thô.

## Gửi lại

Toàn bộ file `gate_*.log`, `curve_*.log` và các `probeC_*.json`.
