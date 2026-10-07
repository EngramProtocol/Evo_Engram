#!/bin/bash
cd ~/Evo_Engram && source venv/bin/activate
python3 evo/01_embed_m1.py --model BAAI/bge-base-en-v1.5 --tag bgebase --device cpu 2>&1 | tee evo/embed_bgebase.log
python3 evo/01_embed_m1.py --model intfloat/e5-large-v2  --tag e5large --device cpu 2>&1 | tee evo/embed_e5large.log
echo "XONG CA HAI" | tee -a evo/embed_e5large.log
