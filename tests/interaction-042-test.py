#!/usr/bin/env python3
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
root=Path(__file__).resolve().parents[1]
app=app_source()
ins=(root/'install.sh').read_text()
assert "VERSION='0.6.1'" in app
assert 'class ConnectionDiagnosticWorker(QRunnable)' in app
assert "QPushButton('Diagnose…')" in app
assert "[ts,'ping','--c','1','--timeout','3s',host]" in app
assert "socket.create_connection((host,port)" in app
assert "'SSH authentication'" in app
assert 'A TCP failure means authentication and SSH keys have not been reached yet.' in app
# Installer regression: each interaction test is an independent command, never an argv to another test.
assert 'python3 "$STAGE/regression-suite.py"' in ins
suite=(root/'regression-suite.py').read_text()
assert 'interaction-039-test.py' in suite
assert 'interaction-041-test.py' in suite
print('0.5.1 connection diagnostics / installer-chain regression OK')
