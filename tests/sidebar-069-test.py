#!/usr/bin/env python3
"""U2: short, readable sidebar actions; a resizable sidebar with a minimum
width whose width is remembered across sessions."""
import os, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
with tempfile.TemporaryDirectory() as home:
    os.environ['HOME'] = home; os.environ['XDG_CONFIG_HOME'] = home + '/.config'
    from PySide6.QtWidgets import QApplication
    from niruorg.app import Main
    app = QApplication([])
    def pump(n=20):
        for _ in range(n): app.processEvents(); time.sleep(0.005)
    w = Main(); w.resize(1180, 760); w.show(); pump()
    labels = [w.sidebar.item(i).text() for i in range(w.sidebar.count())]
    assert '+  Cloud accounts…' in labels and '+  Add server…' in labels, labels
    assert not any('Add / manage' in x for x in labels), labels
    fm = w.sidebar.fontMetrics()
    for text in ('+  Cloud accounts…', '+  Add server…'):
        assert fm.horizontalAdvance(text) + 40 < w.sidebar.width(), (text, w.sidebar.width())
    assert w.sidebar.minimumWidth() == 150 and w.sidebar.width() >= 150
    assert w.sidebar_splitter.indexOf(w.sidebar) == 0
    w.sidebar_splitter.setSizes([260, 900]); w.sidebar_splitter.splitterMoved.emit(260, 1); pump()
    assert w.s.value('sidebar_width', type=int) == w.sidebar.width() and 250 <= w.sidebar.width() <= 270, w.s.value('sidebar_width')
    w.s.sync(); w.close(); pump()
    w2 = Main(); w2.resize(1180, 760); w2.show(); pump()
    assert abs(w2.sidebar.width() - 260) <= 10, w2.sidebar.width()
    w2.sidebar_splitter.setSizes([40, 1100]); pump()
    assert w2.sidebar.width() >= 150, w2.sidebar.width()   # never narrower than the minimum
    w2.close(); app.processEvents()
print('U2 sidebar OK · short labels · resizable · minimum width · width remembered')
