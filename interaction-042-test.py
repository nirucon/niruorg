#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parent
app=(root/'niruorg/app.py').read_text()
ins=(root/'install.sh').read_text()
assert "VERSION='0.4.0'" in app
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
print('0.4.0 connection diagnostics / installer-chain regression OK')
