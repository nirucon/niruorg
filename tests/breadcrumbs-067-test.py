#!/usr/bin/env python3
"""O3: deep paths collapse into first segment, an "…" menu and the last
segments shown in full; the endpoint chip names the host; clicking the bar
or Ctrl+L edits the location, Escape restores the breadcrumbs."""
import os, socket, sys, tempfile, time
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parent
while not (ROOT / 'niruorg' / 'app.py').exists(): ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as td:
    os.environ['HOME'] = home; os.environ['XDG_CONFIG_HOME'] = home + '/.config'
    deep = Path(td, 'Long project folder name', 'claude-1000', 'tmp-abcdefWB', 'work', 'Final report')
    deep.mkdir(parents=True)
    from PySide6.QtCore import Qt, QPoint
    from PySide6.QtGui import QKeySequence
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent, QKeyEvent
    class QTest:  # QtTest is a separate package on Debian; the installer does not pull it in
        @staticmethod
        def mouseClick(widget, button, mods, pos):
            p = QPointF(pos)
            for t in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
                QApplication.sendEvent(widget, QMouseEvent(t, p, widget.mapToGlobal(p), button, button if t == QEvent.Type.MouseButtonPress else Qt.MouseButton.NoButton, mods))
        @staticmethod
        def keyClick(widget, key, mods=Qt.KeyboardModifier.NoModifier):
            for t in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                QApplication.sendEvent(widget, QKeyEvent(t, key, mods))
    from PySide6.QtWidgets import QApplication, QToolButton, QLabel
    from niruorg.app import Main
    app = QApplication([])
    w = Main(); w.resize(1100, 700); w.show()
    def pump(n=30):
        for _ in range(n): app.processEvents(); time.sleep(0.005)
    pane = w.pane1; pane.go(str(deep)); pump()
    def crumbs():
        return [x for x in (pane.crumb_lay.itemAt(i).widget() for i in range(pane.crumb_lay.count())) if isinstance(x, QToolButton)]
    btns = crumbs()
    chip, segs = btns[0], btns[1:]
    texts = [b.text() for b in segs]
    assert texts[0] == '/', texts
    assert '…' in texts, texts
    tail = texts[texts.index('…') + 1:]
    assert tail[-1] == 'Final report' and 2 <= len(tail) <= 3, texts
    assert all('…' not in t for t in tail), texts  # shown segments are never elided
    more = segs[texts.index('…')]
    hidden = [a.text() for a in more.menu().actions()]
    assert 'Long project folder name' in hidden and hidden[-1] == ([p for p in deep.parts][-len(tail) - 1]), (hidden, tail)
    # A hidden segment navigates.
    target_action = [a for a in more.menu().actions() if a.text() == 'claude-1000'][0]
    target_action.trigger(); pump()
    assert pane.current.name == 'claude-1000', pane.current
    pane.go(str(deep)); pump()
    # Endpoint chip: full host name in the tooltip.
    assert socket.gethostname() in crumbs()[0].toolTip(), crumbs()[0].toolTip()
    # Clicking the bar's empty space edits the location; Escape restores.
    QTest.mouseClick(pane.crumb, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(pane.crumb.width() - 5, pane.crumb.height() // 2)); pump()
    assert pane.location_stack.currentWidget() is pane.path and pane.path.text() == str(deep)
    QTest.keyClick(pane.path, Qt.Key.Key_Escape); pump()
    assert pane.location_stack.currentWidget() is pane.crumb, 'escape did not restore'
    assert pane.current == deep, pane.current
    # Ctrl+L is the documented shortcut for the same editor.
    acts = [a for a in w.findChildren(type(w.menuBar().actions()[0])) if a.shortcut() == QKeySequence('Ctrl+L')]
    assert acts, 'Ctrl+L action missing'
    acts[0].trigger(); pump()
    assert pane.location_stack.currentWidget() is pane.path
    pane.path.setText(td); QTest.keyClick(pane.path, Qt.Key.Key_Return); pump()
    assert pane.current == Path(td) and pane.location_stack.currentWidget() is pane.crumb
    # A short path is not collapsed.
    assert '…' not in [b.text() for b in crumbs()[1:]]
    # Narrow pane: still the first segment, "…" and at least the last segment, in full.
    pane.go(str(deep)); w.resize(780, 600); pump(60)
    texts = [b.text() for b in crumbs()[1:]]
    assert texts[0] == '/' and '…' in texts and texts[-1] == 'Final report', texts
    w.close(); app.processEvents()
print('O3 breadcrumbs OK · first / … menu / last segments in full · host tooltip · click and Ctrl+L edit')
