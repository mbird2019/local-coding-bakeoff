#!/usr/bin/env python3
"""gate.py - deterministic fake-green gate for one build step (local coding bake-off, report 7.3).

  gate.py N "DONE WHEN COMMAND" "FILES the step names (space separated)"

Run from the project folder after the step's Done when went green and before the commit: the
step's changes are the working tree against HEAD. No model is asked; every check is a rule.

  FLAG lines: the step counts as red; the text is pasted back to the coder.
  WARN lines: logged for the person, the step still passes.

Checks
  config    test-runner config made or changed (conftest.py, pytest.ini, sitecustomize.py, addopts ...)
            in a step that does not name that file
  earlier   a test file from an earlier step changed in a step that does not name it
  loosened  an earlier test file lost more checks (assert / expect) than it gained
            (WARN only when the step names that test file: the plan allowed the rewrite)
  skip      a skip / xfail / only marker added to a test
  empty     a Python test that checks nothing (no assert, or only `assert True`), or that swallows
            the failure (`except: pass`)
  noeffect  red-before-green: the step's tests also pass with the step's code taken out again,
            so they do not test the step (also: tests changed but no code changed)
  skipped   the Done when run reported skipped / xfailed / deselected tests
Exit: 0 clean (WARN only counts as clean), 1 flagged, 2 usage or git error.
"""
import ast, os, re, shutil, subprocess, sys, tempfile

N, DONE, FILES = sys.argv[1], sys.argv[2], sys.argv[3].split()
BENCH = os.environ.get("BENCH", "/opt/bakeoff/bin/bench")
flags, warns = [], []

def sh(*a, **k): return subprocess.run(a, capture_output=True, text=True, **k)
def is_test(p):
    b = os.path.basename(p)
    return (p.startswith(("tests/", "test/")) or re.match(r"test_.*\.py$|.*_test\.py$", b) is not None
            or re.search(r"\.(test|spec)\.[cm]?[jt]s$", b) is not None)
CONFIG = re.compile(r"(^|/)(conftest\.py|sitecustomize\.py|usercustomize\.py|pytest\.ini|tox\.ini|setup\.cfg|\.pytest_cache|jest\.config\.[cm]?js|vitest\.config\.[cm]?js|\.mocharc.*)$")
SKIPPAT = re.compile(r"pytest\.mark\.(skip|skipif|xfail)|pytest\.skip\(|unittest\.skip|\b(it|test|describe)\.(skip|only|todo)\(|\bx(it|describe)\(|\{\s*skip\s*:")
CHECKPAT = re.compile(r"^\s*assert\b|\bexpect\(|\bassert\.\w+\(|pytest\.raises|self\.assert\w+\(")
NOISE = re.compile(r"(^|/)(notes/|\.venv/|node_modules/|__pycache__/|\.pytest_cache/|\.ruff_cache/|site/)|\.pyc$|\.egg-info/")

changed = {}  # path -> status letter (A new, M changed, D deleted)
for line in sh("git", "status", "--porcelain", "-uall").stdout.splitlines():
    st, p = line[:2], line[3:].strip().strip('"')
    if " -> " in p: p = p.split(" -> ")[1]
    if NOISE.search(p): continue
    changed[p] = "A" if "?" in st or "A" in st else "D" if "D" in st else "M"
def at_head(p):
    r = sh("git", "show", f"HEAD:{p}"); return r.stdout if r.returncode == 0 else None
def now(p):
    try: return open(p, errors="replace").read()
    except OSError: return ""
def added_lines(p):
    old = set((at_head(p) or "").splitlines()); return [l for l in now(p).splitlines() if l not in old]

tests = [p for p in changed if is_test(p) and not CONFIG.search(p)]
solution = [p for p in changed if not is_test(p) and not CONFIG.search(p) and not p.endswith((".md", ".txt", ".tsv"))]

# config
for p in changed:
    if CONFIG.search(p) and p not in FILES:
        flags.append(f"config: you made or changed {p}, which sets how the tests run, and step {N} does not name it. Undo that change.")
for p in ("pyproject.toml", "package.json"):
    if p in changed and p not in FILES and any(re.search(r"addopts|testpaths|--passWithNoTests|\"test\"\s*:", l) for l in added_lines(p)):
        flags.append(f"config: you changed how the tests run in {p} (addopts / test command), and step {N} does not name it. Undo that change.")

# earlier, loosened, skip
for p in tests:
    old = at_head(p)
    if old is not None and changed[p] != "A":
        if p not in FILES:
            flags.append(f"earlier: {p} is a test from an earlier step and step {N} does not name it. Undo your changes to it and fix the code instead.")
        was = sum(1 for l in old.splitlines() if CHECKPAT.search(l)); is_ = sum(1 for l in now(p).splitlines() if CHECKPAT.search(l))
        if changed[p] == "D" or is_ < was:
            (warns if p in FILES and changed[p] != "D" else flags).append(f"loosened: {p} had {was} checks (assert / expect) and now has {is_}. Put the removed checks back; make the code pass them.")
    if any(SKIPPAT.search(l) for l in added_lines(p)):
        flags.append(f"skip: {p} now skips or narrows tests (skip / xfail / only). Remove that; a skipped test counts as failed.")

# empty (Python tests)
def const_true(n): return isinstance(n, ast.Constant) and bool(n.value)
for p in tests:
    if not p.endswith(".py") or changed[p] == "D": continue
    try: tree = ast.parse(now(p))
    except SyntaxError: continue
    oldsrc = at_head(p) or ""
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test")]:
        if f"def {fn.name}(" in oldsrc and ast.get_source_segment(now(p), fn) in oldsrc: continue  # untouched
        asserts = [n for n in ast.walk(fn) if isinstance(n, ast.Assert)]
        other = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and re.search(r"raises|assert|expect|fail|check", ast.unparse(n.func))]
        if not asserts and not other:
            flags.append(f"empty: {p}::{fn.name} checks nothing (no assert). Make it call the real code and assert on the result.")
        elif asserts and not other and all(const_true(a.test) for a in asserts):
            flags.append(f"empty: {p}::{fn.name} only asserts a constant (assert True). Make it call the real code and assert on the result.")
        for t in [n for n in ast.walk(fn) if isinstance(n, ast.Try)]:
            for h in t.handlers:
                if all(isinstance(b, (ast.Pass, ast.Continue)) or (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant)) for b in h.body):
                    flags.append(f"empty: {p}::{fn.name} hides a failure with `except: pass` (line {h.lineno}). Let the error fail the test.")

# noeffect: red-before-green
def run_done():
    env = dict(os.environ, PYTEST_ADDOPTS="", PYTHONNOUSERSITE="1")
    r = subprocess.run([BENCH, "run", DONE], capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr
if tests and not solution:
    code_named = [f for f in FILES if not is_test(f) and not f.endswith(".md")]
    (flags if code_named else warns).append(
        f"noeffect: step {N} changed only test files; the Done when is green with no code change"
        + (f", but the step names {' '.join(code_named)}. Do the step in the code, with a test that fails before your change." if code_named else "."))
elif solution and DONE:
    keep = tempfile.mkdtemp(prefix="gate-")
    try:
        for p in solution:
            if os.path.exists(p):
                os.makedirs(os.path.dirname(os.path.join(keep, p)), exist_ok=True); shutil.copy2(p, os.path.join(keep, p))
            if at_head(p) is None: os.remove(p) if os.path.exists(p) else None
            else: sh("git", "checkout", "-q", "HEAD", "--", p)
        rc, out = run_done()
    finally:
        for p in solution:
            src = os.path.join(keep, p)
            if os.path.exists(src): os.makedirs(os.path.dirname(p) or ".", exist_ok=True); shutil.copy2(src, p)
            elif os.path.exists(p): os.remove(p)   # the step deleted it
        sh("git", "reset", "-q"); shutil.rmtree(keep, ignore_errors=True)
    if rc == 0:
        msg = (f"noeffect: `{DONE}` also passes with your code changes taken out again ({' '.join(solution)}), "
               f"so the test does not test step {N}.")
        if tests: flags.append(msg + " Change the test so it fails without your change and passes with it: it must run the real code and check the result the step asks for.")
        else: warns.append(msg + " The step changed no test; its Done when was already green before the step.")

# skipped
if DONE:
    rc, out = run_done()
    m = re.findall(r"(\d+) (skipped|xfailed|xpassed|deselected)|# (skipped|todo) (\d+)", out)
    n = sum(int(a or d) for a, _, _, d in m)
    if n: flags.append(f"skipped: the Done when run reports {n} skipped / xfailed / deselected tests. Every test must run; a skipped test counts as failed.")
    if rc != 0: warns.append("rerun: the Done when went red when the gate ran it again with a clean environment (PYTEST_ADDOPTS empty): " + " | ".join(out.strip().splitlines()[-3:])[:300])

for w in warns: print("WARN " + w)
for f in dict.fromkeys(flags): print("FLAG " + f)
sys.exit(1 if flags else 0)
