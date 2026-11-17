#!/bin/bash
# local coding bake-off: pdl.sh REPO FILE [N] - continue a partial HF download with N parallel ranges,
# then check sha256 against the HF API. Run in /opt/models.
set -u
REPO=$1 F=$2 N=${3:-8}
URL="https://huggingface.co/$REPO/resolve/main/$F"
want=$(curl -s "https://huggingface.co/api/models/$REPO/tree/main" | python3 -c "import sys,json; f=[x for x in json.load(sys.stdin) if x['path']=='$F'][0]; print(f['size'], f['lfs']['oid'])")
size=${want% *}; sha=${want#* }
have=$(stat -c %s "$F" 2>/dev/null || echo 0)
echo "$F size=$size have=$have"
rest=$((size-have)); chunk=$(( (rest+N-1)/N ))
mkdir -p ".parts-$F"
for i in $(seq 0 $((N-1))); do
  s=$((have+i*chunk)); e=$((s+chunk-1)); [ $e -ge $((size-1)) ] && e=$((size-1)); [ $s -gt $e ] && continue
  p=".parts-$F/$i"; ps=$(stat -c %s "$p" 2>/dev/null || echo 0)
  ( until [ "$(stat -c %s "$p" 2>/dev/null || echo 0)" -ge $((e-s+1)) ]; do
      cur=$(stat -c %s "$p" 2>/dev/null || echo 0)
      curl -sfL --retry 5 -r $((s+cur))-$e "$URL" >> "$p" || sleep 5
    done ) &
done
wait
for i in $(seq 0 $((N-1))); do [ -f ".parts-$F/$i" ] && cat ".parts-$F/$i" >> "$F"; done
rm -rf ".parts-$F"
got=$(stat -c %s "$F")
[ "$got" = "$size" ] || { echo "FAIL size $got != $size"; exit 1; }
echo "$sha  $F" | sha256sum -c - && echo "DONE $F"
