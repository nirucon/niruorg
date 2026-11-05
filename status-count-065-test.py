#!/usr/bin/env python3
"""O1: the status bar item count follows the asynchronous listing."""
import os, sys, tempfile, time
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parent
while not (ROOT / 'niruorg' / 'app.py').exists(): ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as td:
    os.environ['HOME'] = home; os.environ['XDG_CONFIG_HOME'] = home + '/.config'
    for i in range(1500): Path(td, f'file-{i:05d}.txt').write_bytes(b'x' * (i % 9))
    for i in range(12): Path(td, f'dir-{i:02d}').mkdir()
    from PySide6.QtWidgets import QApplication
    from niruorg.app import Main
    app = QApplication([])
    w = Main(); w.resize(900, 600)
    w.pane1.go(td)
    def wait(pred, secs=15):
        end = time.time() + secs
        while time.time() < end:
            app.processEvents()
            if pred(): return True
            time.sleep(0.01)
        return False
    assert wait(lambda: w.status.text().startswith('1512 item(s)')), w.status.text()
    w.pane1.filter.setText('file-0001')
    assert wait(lambda: w.status.text().startswith('10 item(s)')), w.status.text()
    w.pane1.filter.setText('')
    assert wait(lambda: w.status.text().startswith('1512 item(s)')), w.status.text()
    Path(td, 'late.txt').write_text('late')
    assert wait(lambda: w.status.text().startswith('1513 item(s)')), w.status.text()
    w.close(); app.processEvents()
print('O1 status count follows the async listing OK')
