#!/bin/bash
# gate-replay.sh [LABELS.tsv]: run gate.py on past steps with a known label (review/labels.tsv:
# id project commit step label why) and print caught / missed. Each step is replayed in
# projects/zz-gate/ID: worktree at commit^, the commit's files laid on top uncommitted.
# Read-only for the real projects (local coding bake-off).
set -uo pipefail
B=/opt/bakeoff
L=${1:-$B/review/labels.tsv}
mkdir -p $B/projects/zz-gate
printf 'id\tproject\tstep\tlabel\tgate\tflags\n' > $B/review/gate-replay.tsv
tail -n +2 "$L" | while IFS=$'\t' read -r id proj commit step label why; do
  src=$B/projects/$proj; wt=$B/projects/zz-gate/$id
  git -C "$src" worktree remove --force "$wt" 2>/dev/null; rm -rf "$wt"
  git -C "$src" worktree add -q --detach "$wt" "$commit^" || { echo "$id worktree failed"; continue; }
  git -C "$wt" checkout -q "$commit" -- . ; git -C "$wt" reset -q
  for d in .venv node_modules; do [ -d "$src/$d" ] && cp -a --reflink=auto "$src/$d" "$wt/$d"; done
  mkdir -p "$wt/notes"; cp -a "$src"/notes/*.sh "$wt/notes/" 2>/dev/null
  read -r done_cmd files < <(cd "$wt" && python3 - "$step" <<'PY'
import re, sys
n = sys.argv[1]; t = open("PLAN.md").read()
s = re.search(rf"^### Step {n}\b.*?(?=^### Step |\Z)", t, re.S | re.M).group(0)
line = lambda k: next((l for l in s.splitlines() if l.startswith(k)), "")
d = re.search(r"`([^`]+)`", line("Done when:")); f = [x for x in re.findall(r"`([^`]+)`", line("Files:")) if "/" in x or "." in x]
ta = re.search(r"^Test all:.*?`([^`]+)`", t, re.M)
done = d.group(1) if d and line("Done when:").split(":", 1)[1].strip().startswith("`") else (ta.group(1) if ta else "pytest") + " " + " ".join(x for x in f if x.startswith("tests/"))
print(done.replace(" ", "\x01"), " ".join(f))
PY
)
  done_cmd=${done_cmd//$'\x01'/ }
  out=$(cd "$wt" && python3 $B/bin/gate.py "$step" "$done_cmd" "$files" 2>&1); rc=$?
  codes=$(echo "$out" | grep -o -E '^(FLAG|WARN) [a-z]+' | sort | uniq -c | awk '{printf "%s%s:%s ", ($2=="WARN"?"warn-":""), $3, $1}')
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$id" "$proj" "$step" "$label" "$([ $rc -eq 0 ] && echo pass || echo RED)" "${codes:-none}" | tee -a $B/review/gate-replay.tsv
  echo "$out" | sed 's/^/    /' | cut -c1-240
  echo "    done when: $done_cmd | files: $files"
  git -C "$src" worktree remove --force "$wt" 2>/dev/null
done
