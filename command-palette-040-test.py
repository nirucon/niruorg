from pathlib import Path
import ast
src=(Path(__file__).parent/'niruorg/app.py').read_text()
tree=ast.parse(src)
assert "d.setWindowTitle('Commands')" in src
assert "query.textChanged.connect(refresh)" in src
assert "query.returnPressed.connect(activate)" in src
assert "results.itemDoubleClicked.connect" in src
assert "QTimer.singleShot(0,callback)" in src
assert "def move_selection(delta):" in src
print('Command palette contract OK')
