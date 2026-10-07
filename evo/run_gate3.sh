#!/bin/bash
cd ~/Evo_Engram && source venv/bin/activate
for tag in bgebase e5large; do
  python3 evo/03_probe_query_adapter.py --tag $tag --seed 20235956 \
      2>&1 | grep -v "WARNING clustering" | tee evo/gate3_${tag}_s20235956.log
done
echo "XONG GATE 3"
