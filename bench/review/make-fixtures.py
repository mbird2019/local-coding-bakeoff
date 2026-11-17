#!/usr/bin/env python3
"""Build reviewer-test fixtures: step text + diff per labelled commit.

Usage: python3 -I make-fixtures.py LABELS.tsv PROJECTS_DIR OUT_DIR
Writes OUT_DIR/<id>.md (what the reviewer model sees). Labels stay in
LABELS.tsv; nothing in a fixture names the label or the commit message.
"""
import csv, re, subprocess, sys
from pathlib import Path

MAX_ADDED = 80   # added lines per file before truncation
KEEP = 40

def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout

def step_text(plan, n):
    m = re.search(rf"^### Step {n}:.*?(?=^### |\Z)", plan, re.S | re.M)
    if not m:
        sys.exit(f"step {n} not found")
    return m.group(0).strip()

def trim(diff):
    out, files = [], re.split(r"(?=^diff --git )", diff, flags=re.M)
    for f in files:
        if not f.strip():
            continue
        lines = f.splitlines()
        added = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        if added > MAX_ADDED:
            head = []
            kept = 0
            for l in lines:
                if l.startswith("+") and not l.startswith("+++"):
                    kept += 1
                    if kept > KEEP:
                        continue
                head.append(l)
            head.append(f"[bench: {added - KEEP} more added lines of this file omitted]")
            lines = head
        out.append("\n".join(lines))
    return "\n".join(out)

def main(labels, projects, outdir):
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    for row in csv.DictReader(open(labels), delimiter="\t"):
        repo = Path(projects) / row["project"]
        plan = git(repo, "show", f"{row['commit']}:PLAN.md")
        diff = trim(git(repo, "show", "--format=", "--no-color", row["commit"]))
        text = (f"## The step the coding agent was given\n\n{step_text(plan, row['step'])}\n\n"
                f"## Result\n\nThe step's `Done when` command passed after this change.\n\n"
                f"## The agent's change (git diff)\n\n```diff\n{diff}\n```\n")
        (outdir / f"{row['id']}.md").write_text(text)
        print(row["id"], len(text), "chars")

if __name__ == "__main__":
    main(*sys.argv[1:4])
