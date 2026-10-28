#!/usr/bin/env python3
import os
import tempfile
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from niruorg.services.local_watcher import LocalDirectoryWatcher

app = QCoreApplication([])
with tempfile.TemporaryDirectory() as td:
    folder = Path(td)
    watcher = LocalDirectoryWatcher()
    seen = []
    watcher.changed.connect(lambda path: (seen.append(path), loop.quit()))
    watcher.set_paths([folder])
    loop = QEventLoop()
    (folder / 'created.txt').write_text('new')
    QTimer.singleShot(2500, loop.quit)
    loop.exec()
    assert seen and Path(seen[-1]) == folder, seen
print('local directory watcher regression OK')
