#!/usr/bin/env python3
from pathlib import Path
import re
root=Path(__file__).resolve().parent
app=(root/'niruorg/app.py').read_text()
inst=(root/'install.sh').read_text()
assert "VERSION='0.4.0'" in app
assert 'VERSION="0.4.0"' in inst
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
print('0.4.0 activation / media UX regression OK')
