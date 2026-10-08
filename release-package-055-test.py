from pathlib import Path
import ast
p=Path("regression-suite.py")
tree=ast.parse(p.read_text())
tests=None
for node in tree.body:
    if isinstance(node, ast.Assign) and any(isinstance(t,ast.Name) and t.id=="TESTS" for t in node.targets):
        tests=ast.literal_eval(node.value)
        break
assert tests is not None
assert all(isinstance(x, tuple) and len(x)==3 for x in tests), "Every TESTS entry must be a 3-tuple (name, qt, timeout)"
assert all(isinstance(x[0],str) and isinstance(x[1],bool) and isinstance(x[2],int) for x in tests)
print("0.3.0 regression manifest schema OK")
