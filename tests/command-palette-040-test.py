import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source, find_def, def_source  # noqa: E402
from pathlib import Path
import ast
src=app_source()
assert "d.setWindowTitle('Commands')" in src
assert "query.textChanged.connect(refresh)" in src
assert "query.returnPressed.connect(activate)" in src
assert "results.itemDoubleClicked.connect" in src
assert "QTimer.singleShot(0,callback)" in src
assert "def move_selection(delta):" in src
print('Command palette contract OK')
