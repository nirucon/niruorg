#!/usr/bin/env python3
from pathlib import Path
app=Path('niruorg/app.py').read_text(); inst=Path('install.sh').read_text(); click=Path('connection-click-test.py').read_text()
assert "VERSION='0.4.0'" in app
start=app.index(' def manage_servers('); end=app.index(' def toggle_hidden(',start); remote=app[start:end]
assert "box=NiruDialog(d); box.setWindowTitle(title); box.setModal(True)" in remote, 'Connection editor must be a child of modal Connections dialog'
assert "box=NiruDialog(self); box.setWindowTitle(title)" not in remote
assert 'box.raise_()' not in remote and 'box.activateWindow()' not in remote, 'Do not force raise/activate under Wayland'
assert 'editor.parentWidget() is not manager' in click
assert "regression-suite.py" in inst
print('0.4.0 connection modal-parent regression OK')
