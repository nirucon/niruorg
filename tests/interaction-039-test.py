#!/usr/bin/env python3
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
app=app_source()
click=Path('tests/connection-click-test.py').read_text()
inst=Path('install.sh').read_text()
assert "VERSION='0.5.1'" in app
assert "manager.findChildren(QDialog)" in click
assert "QApplication.topLevelWidgets()" in click  # manager discovery remains top-level
assert "editor.parentWidget() is not manager" in click
assert "regression-suite.py" in inst
assert "0.5.1" in inst
print('0.5.1 Qt child-dialog discovery regression OK')
