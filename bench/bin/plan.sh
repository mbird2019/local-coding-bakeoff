#!/bin/bash
# plan.sh - runbook steps 2 and 3 ("Choose the tools", "Get a build order") done by a script:
#   plan.sh LANE PLANNER        (run from the project folder on gpu-host; NEED.md must exist)
# Asks 1-stack -> STACK.md, 1b-check -> STACK.md, 2-plan -> PLAN.md, commits "need, stack, plan".
# You still review PLAN.md with the runbook's checklist afterwards.
set -euo pipefail
LANE=$1 PLANNER=$2
P=/opt/bakeoff/prompts
cd "$(git rev-parse --show-toplevel)"
[ -f NEED.md ] || { echo "no NEED.md"; exit 2; }
last() { ls -t notes/ask-*.md | head -1; }
bench ask "$LANE" "$PLANNER" NEED.md -- "$(cat $P/1-stack.txt)" | tail -n 1
cp "$(last)" STACK.md
bench ask "$LANE" "$PLANNER" NEED.md STACK.md -- "$(cat $P/1b-check.txt)" | tail -n 1
cp "$(last)" STACK.md
bench ask "$LANE" "$PLANNER" NEED.md STACK.md -- "$(cat $P/2-plan.txt)" | tail -n 1
cp "$(last)" PLAN.md
git add -A && git commit -qm "need, stack, plan ($PLANNER)" && echo "PLANNED $(basename "$PWD") with $PLANNER"
