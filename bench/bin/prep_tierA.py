#!/usr/bin/env python3
"""Tier A workspace: a copy of CameraApp with one module stubbed and half its tests visible.

    prep_tierA.py SRC_TAR MODULE OUTDIR

OUTDIR/repo    the agent's workspace (git repo, one commit "start")
OUTDIR/hidden  the full test file, copied in only at scoring time
"""

import ast
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

src_tar, module, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
repo = out / "repo"
out.mkdir(parents=True)
with tarfile.open(src_tar) as t:
    t.extractall(repo, filter="data")


def stub(path: Path) -> None:
    text = path.read_text()
    tree = ast.parse(text)

    class Stubber(ast.NodeTransformer):
        def _body(self, node):
            keep = []
            if ast.get_docstring(node) is not None:
                keep.append(node.body[0])
            keep.append(ast.parse("raise NotImplementedError").body[0])
            node.body = keep
            return node

        def visit_FunctionDef(self, node):
            return self._body(node)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            node.body = [self.visit(n) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) else n for n in node.body]
            return node

    tree.body = [Stubber().visit(n) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else n for n in tree.body]
    path.write_text(ast.unparse(tree) + "\n")


stub(repo / "src" / "camera-app" / f"{module}.py")

tests = repo / "tests"
target = tests / f"test_{module}.py"
(out / "hidden").mkdir()
shutil.copy(target, out / "hidden" / target.name)
for f in tests.glob("test_*.py"):
    if f != target:
        f.unlink()

# Visible: every other test function (1st, 3rd, ...); helpers stay.
tree = ast.parse(target.read_text())
seen = 0
body = []
for n in tree.body:
    if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"):
        seen += 1
        if seen % 2 == 0:
            continue
    body.append(n)
tree.body = body
target.write_text(ast.unparse(tree) + "\n")

for d in ("tools", "contrib", ".github"):
    shutil.rmtree(repo / d, ignore_errors=True)

g = ["git", "-C", str(repo)]
subprocess.run(g + ["init", "-q", "-b", "main"], check=True)
subprocess.run(g + ["add", "-A"], check=True)
subprocess.run(g + ["-c", "user.name=bakeoff", "-c", "user.email=bakeoff@localhost", "commit", "-q", "-m", "start"], check=True)
print(f"visible tests: {(seen + 1) // 2} of {seen}")
