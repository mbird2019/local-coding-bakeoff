#!/usr/bin/env python3
"""r9-table.py [SINCE_ID] [LANE] - Tier A comparison tables from results-tierA-raw.tsv.

One line per (lane, model, repeat): hidden tests passed per module, total of 42, wall minutes,
nudges, ruff failures. A repeat is the n-th row of the same lane+model+module. Then one line
per (lane, model) with the mean and the spread over full repeats. Markdown output.
Run on gpu-host: python3 -I bin/r9-table.py 1116-0914 split
"""
import csv, sys
from collections import defaultdict

RAW = "/opt/bakeoff/results-tierA-raw.tsv"
MODS = ["devices", "ptz", "recorder", "config", "mjpeg"]
since = sys.argv[1] if len(sys.argv) > 1 else "1116-0914"
only = sys.argv[2] if len(sys.argv) > 2 else None

VOID = "/opt/bakeoff/queues/r9-void.txt"  # run ids to leave out (bench faults), one per line
try:
    void = {l.strip() for l in open(VOID) if l.strip() and not l.startswith("#")}
except OSError:
    void = set()

runs = defaultdict(lambda: defaultdict(list))  # (lane, model) -> module -> [row, ...]
total = {}
with open(RAW, newline="") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        if r["id"] in void or r["id"] < since or (only and r["lane"] != only):
            continue
        runs[(r["lane"], r["model"])][r["module"]].append(r)
        total[r["module"]] = int(r["total"])

full = sum(total.get(m, 0) for m in MODS)
print(f"| lane | model | rep | " + " | ".join(f"{m} /{total.get(m, '?')}" for m in MODS)
      + f" | hidden /{full} | min | nudges | ruff fail | capped |")
print("|---|---|---|" + "---|" * (len(MODS) + 5))
summary = []
for (lane, model), bymod in sorted(runs.items()):
    reps = max(len(v) for v in bymod.values())
    sums = []
    for i in range(reps):
        cells, tot, mins, nud, rf, cap, done = [], 0, 0, 0, 0, 0, 0
        for m in MODS:
            rows = bymod.get(m, [])
            if i < len(rows):
                r = rows[i]
                cells.append(f"{r['passed']} ({r['wall_min']}m)")
                tot += int(r["passed"]); mins += int(r["wall_min"]); nud += int(r["nudges"])
                rf += r["ruff"] != "RUFF_OK"; cap += int(r["wall_min"]) >= 40; done += 1
            else:
                cells.append("-")
        part = "" if done == len(MODS) else f" ({done}/{len(MODS)} run)"
        print(f"| {lane} | {model} | {i + 1} | " + " | ".join(cells)
              + f" | {tot}{part} | {mins} | {nud} | {rf} | {cap} |")
        if done == len(MODS):
            sums.append((tot, mins))
    if sums:
        t = [s[0] for s in sums]; mn = [s[1] for s in sums]
        summary.append((lane, model, len(sums), sum(t) / len(t), min(t), max(t), sum(mn) / len(mn)))
print(f"\n{len(void)} run(s) left out as void (queues/r9-void.txt).\n")
print(f"| lane | model | full repeats | mean hidden /{full} | min-max | mean minutes |")
print("|---|---|---|---|---|---|")
for lane, model, n, mean, lo, hi, mm in summary:
    print(f"| {lane} | {model} | {n} | {mean:.1f} | {lo}-{hi} | {mm:.0f} |")
