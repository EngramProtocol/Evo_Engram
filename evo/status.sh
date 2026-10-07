#!/bin/bash
cd ~/Evo_Engram
if tmux ls 2>/dev/null | grep -qE "^(embed|gate)"; then
  echo ">>> DANG CHAY:"; tmux ls | grep -E "^(embed|gate)"
else
  echo ">>> KHONG CON PHIEN NAO -> DA XONG"
fi
echo
for f in evo/embed_*.log evo/gate_*.log evo/curve_*.log; do
  [ -f "$f" ] || continue
  printf "%-40s %s\n" "$f" "$(tr '\r' '\n' < "$f" | grep -vE '^\s*$' | tail -1 | cut -c1-70)"
done
