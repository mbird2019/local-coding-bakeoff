#!/bin/bash
# local coding bake-off Tier A run, on gpu-host.
#   run_tierA.sh HARNESS LANE MODEL MODULE [CAP_MIN]
# HARNESS: aider | opencode | qwen | mini | claude     LANE: p5000 | split
# Builds a fresh workspace, runs the agent in the sandbox (network: llama-swap only),
# nudges like the owner would (pastes the failing test output, max 3), scores on the hidden tests,
# appends one row to /opt/bakeoff/results-tierA-raw.tsv.
set -uo pipefail
H=$1 LANE=$2 MODEL=$3 MOD=$4 CAP=${5:-40}
B=/opt/bakeoff
ID=$(date +%m%d-%H%M%S)-A-$MOD-$H-$MODEL
R=$B/runs/$ID
python3 $B/bin/prep_tierA.py $B/src/camera-app.tar "$MOD" "$R" > "$R.prep" 2>&1 || { cat "$R.prep"; exit 1; }
mv "$R.prep" "$R/prep.txt"
mkdir -p "$R/home"; [ -d $B/home-template ] && cp -a $B/home-template/. "$R/home/"; chmod -R a+rwX "$R/home"; chmod 777 "$R/home" "$R/repo"; chmod -R a+rwX "$R/repo"
URL=http://bake-$LANE:8080
TASK="You are working in a Python project called CameraApp (read README.md for what it is). The file src/camera-app/$MOD.py has its functions and methods stubbed out with 'raise NotImplementedError'. Implement them so the module does what its docstrings, names and the README describe. Visible tests: tests/test_$MOD.py (run them with: pytest -q tests/test_$MOD.py). More hidden tests will check the same behaviour, so implement the general behaviour, not only what the visible tests check. Do not change the tests or any other module. You are done when those tests pass and 'ruff check src' is clean."

agent() {  # $1 = prompt text; runs one harness invocation
  local P="$1"
  printf '%s' "$P" > "$R/home/prompt.txt"
  sudo docker run --rm --network bakeoff --name "bake-agent-$$" \
    -v "$R/repo:/work" -v "$R/home:/home/agent" -e HOME=/home/agent \
    -e URL="$URL" -e MODEL="$MODEL" -e H="$H" -e MOD="$MOD" -e CTX="${CTX:-32768}" -e RKEEP="${RKEEP:-0}" \
    -e TEST_CMD="pytest -q tests/test_$MOD.py" \
    -v "$B/bin/agent.sh:/agent.sh:ro" \
    bakeoff-sandbox timeout "${LEFT}m" bash /agent.sh >> "$R/agent.log" 2>&1
  echo "exit=$?" >> "$R/agent.log"
}

visible() { sudo docker run --rm --network none -v "$R/repo:/work" bakeoff-sandbox \
  bash -c "cd /work && timeout 120 pytest -q tests/test_$MOD.py 2>&1 | tail -n 40"; }

START=$(date +%s); NUDGES=0
LEFT=$CAP
agent "$TASK"
while :; do
  OUT=$(visible)
  echo "$OUT" > "$R/visible-$NUDGES.txt"
  echo "$OUT" | tail -n 1 | grep -q -E '^[0-9]+ passed' && ! echo "$OUT" | tail -n1 | grep -q -E 'failed|error' && break
  [ $NUDGES -ge 3 ] && break
  LEFT=$(( CAP - ($(date +%s) - START) / 60 )); [ $LEFT -le 1 ] && break
  NUDGES=$((NUDGES + 1))
  agent "The tests still fail. This is the output of pytest -q tests/test_$MOD.py:

$OUT

Fix src/camera-app/$MOD.py so the tests pass. Do not change the tests."
done
WALL=$(( ($(date +%s) - START + 59) / 60 ))

# Score: hidden full test file, ruff on the module, nothing else touched.
cp "$R/hidden/test_$MOD.py" "$R/repo/tests/"
SCORE=$(sudo docker run --rm --network none -v "$R/repo:/work" bakeoff-sandbox bash -c "
  cd /work && timeout 300 pytest -q -p no:cacheprovider tests/test_$MOD.py 2>&1 | tail -n 1;
  ruff check -q src/camera-app/$MOD.py >/dev/null 2>&1 && echo RUFF_OK || echo RUFF_FAIL;
  grep -c NotImplementedError src/camera-app/$MOD.py")
echo "$SCORE" > "$R/score.txt"
git -C "$R/repo" -c safe.directory='*' status --porcelain | grep -v -E "src/camera-app/$MOD.py|tests/test_$MOD.py|__pycache__|\.aider|\.pytest_cache|\.ruff_cache" > "$R/other-changes.txt"
last=$(echo "$SCORE" | sed -n 1p)
pass=$(echo "$last" | grep -o -E '[0-9]+ passed' | awk '{s+=$1} END{print s+0}')
total=$(grep -c '^def test_' "$R/hidden/test_$MOD.py")
ruff=$(echo "$SCORE" | sed -n 2p); stubs=$(echo "$SCORE" | sed -n 3p)
other=$(wc -l < "$R/other-changes.txt")
[ -f $B/results-tierA-raw.tsv ] || printf 'id\ttier\tharness\tmodel\tlane\tmodule\tpassed\ttotal\twall_min\tnudges\truff\tstubs_left\tother_files\n' > $B/results-tierA-raw.tsv
printf 'A\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$H" "$MODEL" "$LANE" "$MOD" "$pass" "$total" "$WALL" "$NUDGES" "$ruff" "$stubs" "$other" | sed "s/^/$ID\t/" >> $B/results-tierA-raw.tsv
tail -n 1 $B/results-tierA-raw.tsv
