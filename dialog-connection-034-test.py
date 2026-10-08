#!/usr/bin/env python3
from pathlib import Path
app=Path('niruorg/app.py').read_text()
assert "VERSION='0.3.0'" in app
assert 'class NiruDialog(QDialog)' in app
assert 'Qt.Key.Key_Escape' in app and "QPushButton('Close',self)" in app
assert "cancel=QPushButton('Cancel operation')" in app
assert "close=QPushButton('Close'); close.clicked.connect(d.reject)" in app
assert 'Qt.ItemDataRole.UserRole-1' not in app, 'Original Add connection crash path remains'
assert 'add.clicked.connect(addone)' in app and 'edit.clicked.connect(editone)' in app and 'clone.clicked.connect(cloneone)' in app
assert 'w.currentItemChanged.connect' in app and 'update_actions()' in app
print('Dialog / connection reliability regression OK · 0.0.36')
