# Đợt 9: churn, corpus mới, mapkeep và điểm nóng ITQ

Đợt 8 xác nhận C1, C3 và phần recall của C2 trên seed mới. Đợt 9 trả lời bốn câu hỏi còn mở. Câu thứ hai có giả thuyết
đăng ký trước (`PREREG_round9.md`, tag `evo-r9-prereg`); ba câu còn lại là thăm dò, với đại lượng chính chốt trước.

1. **Migrate có an toàn khi mạng có churn và lỗi peer không?** Dùng mô hình phiên Weibull và sửa chữa lười của engine
   churn V-Engram. Có hai cấu hình:
   - `ch`: churn liên tục, có sửa;
   - `fail`: 30% node hỏng cùng lúc giữa dòng, không sửa.
2. **C3 có giữ trên corpus khác không?** Chạy trên code 20k và SciFact (H6, H7, H8), dòng co theo cỡ corpus.
3. **Baseline FastFill có công bằng hơn không nếu được giữ E0?** Thêm chính sách `mapkeep`: ánh xạ toàn bộ như
   `mapall` nhưng giữ E0, nên tốn tra cứu như lazyVbgD.
4. **Điểm nóng của ITQ ở Arctic từ đâu ra, và ITQ trên nhiều thành phần chính hơn có gỡ được không?**

| pha | nội dung | số job |
|---|---|---|
| R | chạy lại 1 job đợt 8 bằng code mới; 1 job bật đường code churn mà không có node nào rời mạng; cả hai so từng số | 2 |
| A | code100kfq, 3 model × seed 6 đến 15. Không churn: static (so từng số với đợt 8) và mapkeep. Với seed 6 đến 10, chạy thêm `ch` và `fail` trong cùng job cho 7 chính sách, Zipf 1 | 30 |
| B | C3 trên code 20k và SciFact, 3 model × seed 6 đến 15, 10 chính sách (H6, H7, H8) | 60 |
| D | placement study với itq_q, itq128_q, itq256_q, 4 không gian × seed 6 đến 8 | 12 |
| E | chẩn đoán điểm nóng ITQ, 4 không gian × seed 6 đến 8 | 12 |

Tổng cộng 116 job. Ở pha A, phần dựng index và định tuyến chiếm khoảng 17 phút mỗi job, nên các cấu hình churn chạy
chung job với phần không churn (`--churn-sets`) thay vì dựng lại. `analyze_r9.py` in ĐẠT hoặc KHÔNG ĐẠT cho H6 đến H8,
rồi in phần thăm dò và phần tự kiểm.

## Thay đổi code (tag `evo-r9-prereg`)

- **`11_probe_safe.py`.**
  - Thêm chính sách `mapkeep`.
  - Thêm churn và lỗi peer: `--churn-min`, `--median-session`, `--weibull-shape`, `--repair-every`, `--repair-phase`,
    `--churn-step`, `--fail-at`, `--fail-frac`. Mặc định tắt.
  - Thêm `--churn-sets`, `--churn-policies`, `--churn-zipf`: chạy thêm nhiều cấu hình churn trong cùng job.
  - Khi tắt, mọi chính sách cũ cho đúng từng số đợt 8. Khi bật nhưng không có node nào rời mạng, kết quả cũng trùng
    từng số; pha R kiểm cả hai điều này.
- **`10_probe_placement.py`.** Thêm biến thể `itq<k>_q` và `itq<k>_d`, cùng `--check-prev`. Biến thể cũ không đổi.
- **Thêm mới:** `12_diag_itq.py`, `PREREG_round9.md`, `analyze_r9.py`, `run_round9.sh`, `SHA256SUMS_round9`,
  `README_round9.md`.

Đã chạy thử trên dữ liệu giả, so với code đợt 8 chạy trên cùng dữ liệu:

- Code mới, churn tắt, đủ 9 chính sách cũ: trùng từng số ở 7.006 giá trị.
- Đường code churn bật nhưng không có node nào rời mạng: trùng ở 2.336 giá trị.
- Chạy churn gộp trong một job (`--churn-sets`) cho đúng từng số như chạy riêng từng cấu hình: 2.929 giá trị mỗi cấu hình.
- Đủ 18 job của `run_round9.sh` với 2 model và ít seed: mọi job thoát mã 0. Mọi phép tự kiểm đều KHỚP: pha R 4.672 và
  1.946 giá trị, static của pha A so với đợt 8, placement trong `11` so với `10`, và itq_q của pha D so với đợt 8.
- Dữ liệu giả không phản ánh dữ liệu thật, nên ĐẠT hay KHÔNG ĐẠT ở lượt chạy thử không có ý nghĩa.

## Các bước

**Trên laptop:**

```bash
cd Evo_Engram
git checkout main && git pull
git log --oneline -1                     # phải là: 50cb7ce evo: dot 8, danh gia xac nhan dang ky truoc, ...
git am ~/Downloads/0001-evo-dot-9*.patch
sha256sum -c evo/SHA256SUMS_round9       # 9 dòng OK (máy Mac: shasum -a 256 -c ...)
git tag -a evo-r9-prereg -m "dot 9: churn, corpus moi, mapkeep, diem nong ITQ"
git push origin main --tags
```

**Trên server:**

```bash
cd ~/Evo_Engram
git status --short | grep -v '^??'       # không in gì
git fetch origin --tags && git checkout evo-r9-prereg
sha256sum -c evo/SHA256SUMS_round9
ls probeV8_code100kfq_*_itq_q.json | wc -l          # 30
ls probeP_code100kfq_*_s[678].json | wc -l          # 12
tmux new -s round9 -d "bash ~/Evo_Engram/evo/run_round9.sh"
```

Khoảng 10 giây sau, xem mấy dòng đầu của log:

```bash
head -12 evo/r9_logs/jobs.log
```

Mấy dòng này phải có:

- `numpy ...`;
- `HEAD = tag evo-r9-prereg`;
- dòng `đợt 9: 116 job, P=4`;
- không có `DỪNG`.

Thời gian ước tính trên node-dal-02, 4 job song song: khoảng 5 giờ. Pha R chạy đầu tiên, khoảng 20 phút sau đã có kết
quả so từng số:

```bash
grep -H "so với lượt cũ\|    lệch:" evo/r9_logs/r9_*.log
```

Lệnh này phải in đúng 2 dòng, mỗi job một dòng, cả hai kết thúc bằng `KHỚP`.

**Khi xong** (dòng cuối `jobs.log` là `XONG ĐỢT 9 ...`):

```bash
cd ~/Evo_Engram
grep -c "mã thoát" evo/r9_logs/jobs.log         # 116
grep "mã thoát [1-9]" evo/r9_logs/jobs.log      # không in gì
tar czf ~/evo_round9_results.tar.gz probeVR9*.json probeV9X_*.json probeV9_code_*.json probeV9_scifact_*.json probeP9_*.json diagITQ_*.json evo/r9_logs evo/round9_all.txt
tar tzf ~/evo_round9_results.tar.gz | grep -c json   # 116
```

Gửi lại file tar.
