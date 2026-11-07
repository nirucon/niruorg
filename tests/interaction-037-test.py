#!/usr/bin/env python3
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
app=app_source()
inst=(root/'install.sh').read_text()
assert "VERSION='0.6.1'" in app
assert 'VERSION="0.6.1"' in inst
# Installer regression: tests must be separate commands, never accidental argv.
runner = (root / "regression-suite.py").read_text()
assert "regression-suite.py" in inst
assert "glob(" in runner or "rglob(" in runner or "*-test.py" in runner
# Media integration must exist in actual context/open paths.
assert "Play in NIRU Player" in app
assert "return self.play_audio()" in app
assert "Focus / Fullscreen" in app and "QKeySequence('F11')" in app
# About must not use the native colored QMessageBox icon.
assert 'QMessageBox.about(' not in app
print('0.5.1 activation / media UX regression OK')
