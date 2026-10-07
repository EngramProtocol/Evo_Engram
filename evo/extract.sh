#!/bin/bash
cd ~/Evo_Engram
for f in evo/embed_*.log evo/gate_*.log evo/curve_*.log; do
  [ -f "$f" ] || continue
  echo "########## $f ##########"
  tr '\r' '\n' < "$f" | grep -vE "^Batches:|^\s*$|it/s\]$|^Loading weights" 
  echo
done
