#!/usr/bin/env python3
from pathlib import Path
app=Path('niruorg/app.py').read_text()
click=Path('connection-click-test.py').read_text()
inst=Path('install.sh').read_text()
assert "VERSION='0.3.0'" in app
assert "manager.findChildren(QDialog)" in click
assert "QApplication.topLevelWidgets()" in click  # manager discovery remains top-level
assert "editor.parentWidget() is not manager" in click
assert "regression-suite.py" in inst
assert "0.3.0" in inst
print('0.3.0 Qt child-dialog discovery regression OK')
