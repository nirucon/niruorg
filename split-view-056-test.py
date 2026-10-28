#!/usr/bin/env python3
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    os.environ['HOME'] = str(root)
    os.environ['XDG_CONFIG_HOME'] = str(root / 'config')
    os.environ['XDG_DATA_HOME'] = str(root / 'data')
    os.environ['XDG_STATE_HOME'] = str(root / 'state')
    os.environ['XDG_CACHE_HOME'] = str(root / 'cache')
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from PySide6.QtWidgets import QApplication
    from niruorg.app import Main

    app = QApplication([])
    app.setOrganizationName('NIRU')
    app.setApplicationName('NIRUORG')
    window = Main()
    window.resize(1100, 700)
    window.show()
    app.processEvents()

    assert not window.pane2.isVisible()
    window.show_right_pane()
    app.processEvents()
    assert window.pane2.isVisible()

    window.split.setSizes([320, 500])
    app.processEvents()
    sizes = window.split.sizes()
    assert len(sizes) == 2 and min(sizes) > 0
    window._remember_split_sizes()
    saved = [int(value) for value in window.s.value('split_sizes')]
    assert saved == sizes, (saved, sizes)

    window.close_split()
    app.processEvents()
    assert not window.pane2.isVisible()
    window.split.setSizes([1, 1])
    window.show_right_pane()
    app.processEvents()
    restored = window.split.sizes()
    assert len(restored) == 2 and min(restored) > 0
    assert sum(abs(a - b) for a, b in zip(saved, restored)) <= 4, (saved, restored)

    window.close()
    app.processEvents()
print('split view sizes regression OK')
