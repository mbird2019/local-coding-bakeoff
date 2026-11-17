#!/bin/bash
# steps.sh - runbook step 4 ("Build, one step at a time") done by a script, exactly as written:
#   bench steps FROM TO LANE CODER HARNESS
# For each step N of PLAN.md: run the coder with prompts/3-step.txt, run the step's Done when,
# commit on green; on red paste the last 30 lines back (at most 3 times); still red -> reset the
# step and stop with "STUCK N" so you choose: split it, bigger model, or rewrite it.
# Done when: the backticked command right after "Done when:"; if the line is prose, the step's
# test files with the Test all command. Every 3 steps: Test all and Lint (logged).
# Regression gate: Test all runs before the coder starts; a green Done when that leaves a test
# failing which passed before the step counts as red and is pasted back like any other failure.
# Fake-green gate: after a green Done when, bin/gate.py checks how it went green (test config touched,
# earlier tests changed, empty tests, tests that pass without the code); a FLAG counts as red and is
# pasted back. GATE=0 turns it off. Flags and warnings: notes/gate.log.
# Writes notes/steps.tsv (step, result, nudges, minutes). Run from the project folder on gpu-host.
set -uo pipefail
FROM=$1 TO=$2 LANE=$3 CODER=$4 H=$5
P=/opt/bakeoff/prompts
cd "$(git rev-parse --show-toplevel)" || exit 2
field() {  # field N Files|Done -> text of that line of step N
  python3 - "$1" "$2" <<'PY'
import re, sys
n, f = sys.argv[1], sys.argv[2]
t = open("PLAN.md").read()
m = re.search(rf"^### Step {n}\b.*?(?=^### Step |\Z)", t, re.S | re.M)
if not m: sys.exit(1)
s = m.group(0)
if f == "title": print(s.splitlines()[0]); sys.exit()
line = next((l for l in s.splitlines() if l.startswith(f + ":") or l.startswith(f + " when:")), "")
if f == "Files":
    print(" ".join(x for x in re.findall(r"`([^`]+)`", line) if "/" in x or "." in x))
else:
    rest = line.split(":", 1)[1].strip() if line else ""
    m2 = re.match(r"`([^`]+)`", rest)
    print(m2.group(1) if m2 else "")
PY
}
hdr() { grep -m1 "^$1:" PLAN.md | grep -o '`[^`]*`' | head -1 | tr -d '`'; }
TESTALL=$(hdr "Test all"); LINT=$(hdr "Lint")
names() { grep -E '^(FAILED|ERROR) |^not ok |^ *✖ ' | sed -E '/^(FAILED|ERROR) /s/ - .*//; s/^ *//; s/ \([0-9.]+ ?m?s\)$//' | sort -u; }  # failing test names (pytest, node --test, TAP)
fails() { bench run "${TESTALL:-pytest}" 2>&1 | names; }
[ -f notes/steps.tsv ] || printf 'step\tresult\tnudges\tminutes\tcoder\tharness\n' > notes/steps.tsv
for N in $(seq "$FROM" "$TO"); do
  field "$N" title >/dev/null || { echo "no step $N"; break; }
  echo "=== $(field "$N" title)"
  FILES=$(field "$N" Files); DONE=$(field "$N" Done)
  if [ -z "$DONE" ]; then
    tests=$(for f in $FILES; do [[ $f == tests/* ]] && echo -n "$f "; done)
    DONE="${TESTALL:-pytest} $tests"
  fi
  echo "files: $FILES"; echo "done when: $DONE"
  t0=$(date +%s); nudges=0; gated=0
  pre=$(git hash-object pyproject.toml package.json 2>/dev/null)
  base=$([ -d .venv ] || [ -d node_modules ] && fails)
  FILES="$FILES" TEST_CMD="$DONE" bench agent "$LANE" "$CODER" "$H" "$(sed "s/{N}/$N/g" $P/3-step.txt)" | tail -n 5
  while :; do
    [ "$(git hash-object pyproject.toml package.json 2>/dev/null)" != "$pre" ] || [ ! -d .venv ] && { inst=$(bench install 2>&1); echo "$inst" | tail -n 3; insterr=$(grep -m 6 -E "^ERROR|error:|ERR!" <<<"$inst"); pre=$(git hash-object pyproject.toml package.json 2>/dev/null); }
    out=$(bench run "$DONE" 2>&1); rc=$?
    # A failed install shows up in the test only as "No module named ...": put the install error first.
    if [ $rc -ne 0 ] && [ -n "${insterr:-}" ]; then
      out="Installing the project failed first (pip/npm install):
$insterr
$out"
    fi
    echo "$out" | tail -n 5
    if [ $rc -eq 0 ]; then
      ta=$(bench run "${TESTALL:-pytest}" 2>&1)
      new=$(comm -13 <(echo "$base") <(names <<<"$ta") | sed '/^$/d')
      if [ -n "$new" ]; then
        rc=1; echo "--- Done when green, but Test all has new failures:"; echo "$new"
        out="The step's own test passes, but these tests passed before step $N and fail now (run ${TESTALL:-pytest}):
$new
$(echo "$ta" | tail -n 30)"
      fi
    fi
    # Fake-green gate (report 7.3, bin/gate.py): rules only, no model. FLAG = red, pasted back; WARN = logged.
    if [ $rc -eq 0 ] && [ "${GATE:-1}" = 1 ]; then
      sudo chown -R "$(id -u):$(id -g)" .
      g=$(python3 /opt/bakeoff/bin/gate.py "$N" "$DONE" "$FILES" 2>&1); grc=$?
      [ -n "$g" ] && { echo "--- gate step $N"; echo "$g"; printf '## step %s nudge %s\n%s\n' "$N" "$nudges" "$g" >> notes/gate.log; }
      if [ $grc -eq 1 ]; then
        rc=1; gated=$((gated + 1))
        out="The Done when passes, but the step is not accepted, because of how the test was made to pass:
$(grep '^FLAG ' <<<"$g" | sed 's/^FLAG [a-z]*: /- /')
If the step cannot be done as written, say so in one line (Step $N stuck: why) and stop; do not make the test pass another way."
      fi
    fi
    [ $rc -eq 0 ] && break
    [ $nudges -ge 3 ] && break
    nudges=$((nudges + 1)); echo "--- nudge $nudges"
    # A crash hides the real message (pytest captures it, the tail is all stack frames): run it
    # again with output shown, and put the first error lines above the tail.
    if [[ $DONE == pytest* ]] && grep -qE "Fatal Python error|dumped core" <<<"$out"; then
      out=$(bench run "pytest -s -p no:faulthandler ${DONE#pytest}" 2>&1)
    fi
    errs=$(grep -q "^The Done when passes, but" <<<"$out" || grep -m 8 -E "Error|error:|Fatal|Must |FAILED|assert" <<<"$out")
    FILES="$FILES" TEST_CMD="$DONE" bench agent "$LANE" "$CODER" "$H" "Step $N: this fails: ${errs:+$errs
...
}$(echo "$out" | tail -n 30). Fix it." | tail -n 5
  done
  min=$(( ($(date +%s) - t0 + 59) / 60 ))
  if [ $rc -eq 0 ]; then
    sudo chown -R "$(id -u):$(id -g)" .   # agents run git inside the sandbox as another user
    git add -A && git commit -qm "step $N" && echo "GREEN $N ($nudges nudges, $min min)"
    printf '%s\tgreen\t%s\t%s\t%s\t%s\tgate-red=%s\n' "$N" "$nudges" "$min" "$CODER" "$H" "$gated" >> notes/steps.tsv
  else
    printf '%s\tstuck\t%s\t%s\t%s\t%s\tgate-red=%s\n' "$N" "$nudges" "$min" "$CODER" "$H" "$gated" >> notes/steps.tsv
    keep=$(mktemp -d); cp -a notes "$keep/"
    sudo chown -R "$(id -u):$(id -g)" .   # files the sandbox user made, so the reset can remove them
    git reset -q --hard; git clean -qfd -e .venv -e node_modules -e notes
    cp -a "$keep/notes/." notes/; rm -rf "$keep"
    echo "STUCK $N after $nudges nudges: split the step, give it to the bigger model, try the other harness, or rewrite it"; exit 3
  fi
  if [ $(( (N - FROM + 1) % 3 )) -eq 0 ]; then
    echo "--- every 3 steps: Test all / Lint"
    bench run "${TESTALL:-pytest}" 2>&1 | tail -n 3; bench run "${LINT:-true}" 2>&1 | tail -n 3
  fi
done
echo "DONE $FROM-$TO"
