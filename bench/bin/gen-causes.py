#!/usr/bin/env python3
"""gen-causes.py - add an auto-derived outcome and one-line cause to causes-tierA.tsv for every
Tier A run that has none. Derived only from the run folder: score.txt (hidden pytest output),
agent.log (exit code), the raw row (ruff, stubs left, other files) and queues/r9-void.txt.
Hand-written causes are never touched. Run on the GPU host: python3 -I bin/gen-causes.py [--apply]"""
import csv, re, sys
from pathlib import Path
B = Path("/opt/bakeoff")
def tsv(p):
    with open(p, newline="") as f: return list(csv.reader(f, delimiter="\t"))
have = {r[0] for r in tsv(B/"causes-tierA.tsv")[1:] if r}
void, why = {}, ""
for l in (B/"queues/r9-void.txt").read_text().splitlines():
    if l.startswith("#"): why = l.lstrip("# ").strip()
    elif l.strip(): void[l.strip()] = why
new = []
for r in tsv(B/"results-tierA-raw.tsv")[1:]:
    if not r or r[0] in have: continue
    rid, passed, total = r[0], int(r[6]), int(r[7])
    ruff = r[10] if len(r) > 10 else ""; stubs = r[11] if len(r) > 11 else "0"; other = r[12] if len(r) > 12 else "0"
    d = B/"runs"/rid
    parts = []
    if rid in void: parts.append("VOID, left out of the tables: " + void[rid])
    log = (d/"agent.log").read_text(errors="replace") if (d/"agent.log").exists() else ""
    ex = re.findall(r"^exit=(\d+)", log, re.M)
    if ex and ex[-1] == "124": parts.append("timed out at the cap (exit 124)")
    elif ex and ex[-1] != "0": parts.append(f"agent exit {ex[-1]}")
    sc = (d/"score.txt").read_text(errors="replace") if (d/"score.txt").exists() else ""
    names = list(dict.fromkeys(re.findall(r"^(?:FAILED|ERROR) \S*?::(\w+)", sc, re.M)))
    if passed == total: parts.append(f"all {total} hidden tests pass")
    elif names: parts.append(f"failed hidden {total-passed} of {total}: " + ", ".join(names[:5]) + (f" and {len(names)-5} more" if len(names) > 5 else ""))
    else:
        m = re.search(r"(\d+ (?:failed|error)[^\n]*)", sc)
        parts.append(f"failed hidden {total-passed} of {total}" + (f" ({m.group(1).strip()})" if m else " (no test names in score.txt)"))
    if stubs not in ("0", ""): parts.append(f"{stubs} stubs left")
    if ruff == "RUFF_FAIL": parts.append("ruff fails")
    if other not in ("0", ""): parts.append(f"{other} other files changed")
    oc = "void" if rid in void else "fail" if passed == 0 else "partial" if passed < total else "pass-lint" if ruff == "RUFF_FAIL" else "pass"
    new.append([rid, oc, "auto: " + "; ".join(parts)])
print(len(new), "rows to add")
for r in new[:3] + new[-3:]: print("\t".join(r)[:230])
if "--apply" in sys.argv:
    with open(B/"causes-tierA.tsv", "a", newline="") as f:
        csv.writer(f, delimiter="\t", lineterminator="\n").writerows(new)
    print("appended")
