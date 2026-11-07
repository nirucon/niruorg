#!/usr/bin/env python3
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
app=app_source(); inst=Path('install.sh').read_text(); click=Path('tests/connection-click-test.py').read_text()
assert "VERSION='0.6.1'" in app
from source_contract import Src, def_source; remote=Src(def_source('manage_servers'))
assert "box=NiruDialog(d); box.setWindowTitle(title); box.setModal(True)" in remote, 'Connection editor must be a child of modal Connections dialog'
assert "box=NiruDialog(self); box.setWindowTitle(title)" not in remote
assert 'box.raise_()' not in remote and 'box.activateWindow()' not in remote, 'Do not force raise/activate under Wayland'
assert 'editor.parentWidget() is not manager' in click
assert "regression-suite.py" in inst
print('0.5.1 connection modal-parent regression OK')
