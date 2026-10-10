# Đợt 4: confirmatory, trust model, paraphrase và simulator end-to-end

## Gói gồm

Code của đợt 3 và 3b, trước đây chỉ có trên server và chưa vào git:

- evo/03c_probe_holdout.py
- evo/04b_probe_multiepoch2.py
- evo/me_common.py
- evo/analyze_03.py, analyze_04b.py, analyze_06.py
- evo/run_round3.sh, run_round3b.sh

Code mới của đợt 4:

- **evo/06_probe_lazy.py.** Thêm `--reindex cap:delay` (trust model re-indexer), `--workloads verbatim,para`
  và `--trace-runs`. Mặc định giữ đúng đợt 3b, và tự kiểm khớp từng số với probeL_*_ku.json.
- **evo/08_sim_evo.py.** Mô phỏng chi phí end-to-end trong SimPy của V-Engram, dùng src/: overlay k-bucket
  join, Ripple Search, RS(30,20) và RTT N(50,15) ms. Đo RPC, byte, payload, CPU nhúng, ghi khi migrate và
  độ trễ p50/p95. Chất lượng tự kiểm khớp với 04b.
- **evo/07_assemble_data.py** và **prepare/04_evo_colab_embed.py.** Phần dữ liệu, đã gửi trước.
- **evo/PREREG_round4.md** và **evo/analyze_prereg.py.** Đăng ký trước: giả thuyết và tiêu chí đạt.
- **evo/analyze_06b.py** và **evo/analyze_08.py.** Tổng hợp phần thăm dò.
- **evo/run_round4.sh** và **evo/SHA256SUMS_round4.** Chạy toàn bộ và kiểm tra file đóng băng.
- **evo/01_embed_m1.py.** Thêm prefix cho arctic.

## Thứ tự

1. **Commit và tag trên laptop**, trước khi chạy bất cứ job nào của đợt 4.
2. **Đưa server về đúng tag.** File chưa track trên server (probe*.json, log) vẫn giữ nguyên.
3. **Lắp dữ liệu.** Chạy `07_assemble_data.py` sau khi có `evo_out` từ Colab.
4. **Chạy `run_round4.sh`.** Ước khoảng một đêm với P = 2:
   - pha A: 57 job holdout và multi-epoch;
   - pha B: 27 job lazy;
   - pha C: 7 job mô phỏng.
5. **Gửi lại `evo/round4_all.txt`.**
