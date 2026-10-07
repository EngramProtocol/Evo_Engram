#!/bin/bash
cd ~/Evo_Engram && source venv/bin/activate
for tag in bgebase e5large; do
  python3 evo/02_probe_bridge.py --tag $tag --mode gate --seed 20235956 \
      --cb-train full --out probeC_${tag}_gateCB_s20235956.json \
      2>&1 | grep -v "WARNING clustering" | tee evo/gateCB_${tag}_s20235956.log
done
echo "XONG GATE CB" 
