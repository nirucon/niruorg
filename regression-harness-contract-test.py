#!/usr/bin/env python3
from pathlib import Path
import ast, re
root=Path(__file__).resolve().parent
installer=(root/"install.sh").read_text()
runner=(root/"regression-suite.py").read_text()
assert 'python3 "$STAGE/regression-suite.py"' in installer
assert "ROOT.glob('*-test.py')" in runner
offenders=[]
for path in sorted(root.glob("*-test.py")):
    if path.name==Path(__file__).name:
        continue
    text=path.read_text(errors="replace")
    if "install.sh" not in text:
        continue
    tree=ast.parse(text)
    for node in ast.walk(tree):
        if not isinstance(node,ast.Assert):
            continue
        seg=ast.get_source_segment(text,node.test) or ""
        if "$STAGE/interaction-" in seg or "$STAGE/connection-" in seg:
            offenders.append(f"{path.name}: obsolete manual regression command")
        if re.search(r"""['"][^'"]+-test\.py['"]\s+in\s+(?:inst|installer)""",seg):
            offenders.append(f"{path.name}: hard-coded test filename")
        for lit in re.findall(r"""['"]([^'"]{24,})['"]\s+in\s+(?:inst|installer)""",seg):
            if "regression-suite.py" not in lit:
                offenders.append(f"{path.name}: installer prose coupling: {lit}")
assert not offenders, "stale installer coupling: "+"; ".join(offenders)
print("Regression harness contract OK · installer tests use durable central-runner contracts")
