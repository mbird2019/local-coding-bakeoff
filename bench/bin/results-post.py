#!/usr/bin/env python3
"""results-post.py - build /opt/bakeoff/results.tsv (task acceptance 1) from the raw logs.

One row per run: tier, harness, model, quant, card, step, tests passed/total, wall minutes,
nudges, outcome, cause.
  Tier A: results-tierA-raw.tsv (queue.sh rows) + causes-tierA.tsv (outcome, cause).
  Tier B/C: projects/<p>/notes/steps.tsv, one row per step attempt. For a step row, tests is the
  step's own "Done when" (1/1 green, 0/1 otherwise); the project's Test all count goes on a
  summary row (step "all") taken from SUMMARY below, filled in by hand from the logs.
Run on gpu-host: python3 -I results-post.py  (rewrites results.tsv; raw files untouched).
"""
import csv, re, sys
from pathlib import Path

B = Path("/opt/bakeoff")
CFG = [B / "cfg/bake-p5000.yaml", B / "cfg/bake-split.yaml", B / "cfg/bake-all.yaml"]
CARD = {
    "split": "A2000+RTX4000-82:00",
    "all": "P5000+RTX4000x2+A2000",
    "p5000": "P5000",                      # until 2026-11-15 08:05 UTC
    "p5000b": "P5000+RTX4000-06:00",       # from 2026-11-15 08:05 UTC
}
# Tier B/C: lane per steps.tsv row. camera-rebuild ran on split until it was moved (first
# "21 stopped" row), one attempt on the P5000 alone, then on P5000+RTX4000.
def camera-rebuild_lanes(rows):
    out, stage = [], "split"
    for r in rows:
        out.append(stage)
        note = r[6] if len(r) > 6 else ""
        if r[0] == "21" and r[1] == "stopped":
            stage = "p5000" if "camera-rebuild lane -> p5000" in note else "p5000b"
    return out
PROJECTS = {  # name: (tier, lanes function)
    "camera-rebuild": ("B", camera-rebuild_lanes),
    "site-wiki": ("C", lambda rows: ["split"] * len(rows)),
    "site-homepage": ("C", lambda rows: ["split"] * len(rows)),
    "site-helper": ("C", lambda rows: ["split"] * len(rows)),
}
# Whole-project rows: (project, harness, model, lane, passed, total, outcome, cause)
SUMMARY_FILE = B / "results-summary.tsv"

def quants():
    q = {}
    for f in CFG:
        name = None
        for line in f.read_text().splitlines():
            m = re.match(r"^  ([a-z0-9.-]+):\s*$", line)
            if m:
                name = m.group(1)
            m = re.search(r"-m /(?:models|scratchmodels)/\S+?-((?:UD-)?(?:I?Q\d\w*|MXFP4|F16|BF16))\.gguf", line)
            if m and name:
                q.setdefault(name, m.group(1))
    return q

def tsv(path):
    with open(path, newline="") as f:
        return list(csv.reader(f, delimiter="\t"))

def main():
    q = quants()
    hdr = ["id", "tier", "harness", "model", "quant", "card", "step", "passed", "total",
           "wall_min", "nudges", "outcome", "cause"]
    out = [hdr]
    raw = B / "results-tierA-raw.tsv"
    causes = {r[0]: r[1:] for r in tsv(B / "causes-tierA.tsv")[1:]}
    for r in tsv(raw)[1:]:
        rid, tier, harness, model, lane, module, passed, total, wall, nudges = r[:10]
        oc, cause = causes.get(rid, ["", "no cause recorded"])
        out.append([rid, tier, harness, model, q.get(model, "?"), CARD[lane], module,
                    passed, total, wall, nudges, oc, cause])
    sc = B / "causes-steps.tsv"  # id<TAB>cause for Tier B/C rows that were not green
    step_causes = {r[0]: r[1] for r in tsv(sc)[1:] if len(r) > 1} if sc.exists() else {}
    for p, (tier, lanes) in PROJECTS.items():
        f = B / "projects" / p / "notes/steps.tsv"
        if not f.exists():
            continue
        rows = [r for r in tsv(f)[1:] if r]
        for i, (r, lane) in enumerate(zip(rows, lanes(rows)), 1):
            step, result, nudges, mins, coder, harness = r[:6]
            note = r[6] if len(r) > 6 else ""
            green = result == "green"
            rid = f"{p}-{i:02d}"
            cause = step_causes.get(rid) or note.strip("()") or ("" if green else "NO CAUSE YET")
            out.append([rid, tier, harness, coder, q.get(coder, "?"), CARD[lane],
                        step, "1" if green else "0", "1", mins, nudges, result, cause])
    if SUMMARY_FILE.exists():
        for n, r in enumerate(tsv(SUMMARY_FILE)[1:], 1):
            p, harness, model, lane, passed, total, oc, cause = r[:8]
            tier = PROJECTS.get(p, ("?",))[0]
            out.append([f"{p}-all-{n}", tier, harness, model, q.get(model, "?"), CARD[lane],
                        "all", passed, total, "", "", oc, cause])
    with open(B / "results.tsv", "w", newline="") as f:
        csv.writer(f, delimiter="\t", lineterminator="\n").writerows(out)
    print(f"results.tsv: {len(out) - 1} rows")

if __name__ == "__main__":
    sys.exit(main())
