#!/bin/bash
cd ~/Evo_Engram && source venv/bin/activate
for tag in bgebase e5large; do
  python3 evo/02_probe_bridge.py --tag $tag --mode gate --seed 20235956 \
      2>&1 | tee evo/gate_${tag}_s20235956.log
done
echo "XONG GATE" | tee -a evo/gate_e5large_s20235956.log
