#!/bin/bash
# queue.sh JOBFILE: run Tier A jobs one by one; each line "HARNESS LANE MODEL MODULE [CAP]". Done lines get "# done".
f=$1
while line=$(grep -v -E '^#|^$' "$f" | head -n 1); [ -n "$line" ]; do
  sed -i "0,/^$(printf '%s' "$line" | sed 's/[]\/$*.^[]/\\&/g')\$/s//# done $line/" "$f"
  m=$(echo $line | cut -d' ' -f3)
  case "$m" in devstral-24b) c=20480;; qwen38-*|qwopus38-*|swift15-*|thinkcap38-*) c=49152;; *) c=32768;; esac
  case "$m" in *-med*) rk=1;; *) rk=0;; esac
  CTX=$c RKEEP=$rk /opt/bakeoff/bin/run_tierA.sh $line
done
echo "queue $f empty"
