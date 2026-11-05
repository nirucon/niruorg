#!/usr/bin/env python3
"""U3: type-ahead find, Backspace = up, Alt+Left/Right = back/forward,
F5 = refresh, Ctrl+L = location; all documented in Help."""
import os, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as td:
    os.environ['HOME'] = home; os.environ['XDG_CONFIG_HOME'] = home + '/.config'
    root = Path(td); sub = root / 'Sub folder'; sub.mkdir()
    for name in ('alpha.txt', 'beta.txt', 'Beta-2.txt', 'bravo.md', 'charlie.txt', 'delta.txt'): (root / name).write_text(name)
    from PySide6.QtCore import Qt, QEvent
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
    from niruorg.app import Main
    app = QApplication([])
    w = Main(); w.resize(1000, 700); w.show()
    pane = w.pane1
    def pump(pred=lambda: False, secs=0.3):
        end = time.time() + secs
        while time.time() < end:
            app.processEvents()
            if pred(): return True
            time.sleep(0.005)
        return pred()
    def key(k, mods=Qt.KeyboardModifier.NoModifier, text=''):
        for t in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            QApplication.sendEvent(pane.view, QKeyEvent(t, k, mods, text))
        pump()
    def current_name():
        idx = pane.view.currentIndex()
        return pane.model.fileName(pane.proxy.mapToSource(idx)) if idx.isValid() else None
    pane.go(td); assert pump(lambda: pane.proxy.rowCount() == 7, 5)
    pane.view.setFocus()
    # Type-ahead: case-insensitive prefix, extends within the input interval,
    # repeating a letter cycles through its matches.
    key(Qt.Key.Key_C, text='c'); assert current_name() == 'charlie.txt', current_name()
    pane.view._ta_time = 0
    key(Qt.Key.Key_B, text='b'); first = current_name()
    key(Qt.Key.Key_B, text='b'); second = current_name()
    assert {first, second} <= {'beta.txt', 'Beta-2.txt', 'bravo.md'} and first != second, (first, second)
    pane.view._ta_time = 0
    for ch in 'bra': key(getattr(Qt.Key, 'Key_' + ch.upper()), text=ch)
    assert current_name() == 'bravo.md', current_name()
    assert len(pane.selected()) == 1 and pane.selected()[0].name == 'bravo.md'
    pane.view._ta_time = 0
    key(Qt.Key.Key_S, text='s'); assert current_name() == 'Sub folder', current_name()
    # Enter opens the folder, Backspace goes up.
    key(Qt.Key.Key_Return); assert pump(lambda: pane.current == sub, 2), pane.current
    key(Qt.Key.Key_Backspace); assert pump(lambda: pane.current == root, 2), pane.current
    # Alt+Left / Alt+Right walk the history.
    key(Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier); assert pump(lambda: pane.current == sub, 2), pane.current
    key(Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier); assert pump(lambda: pane.current == root, 2), pane.current
    # F5 lists again and picks up a change.
    (root / 'echo.txt').write_text('e')
    key(Qt.Key.Key_F5); assert pump(lambda: pane.proxy.rowCount() == 8, 3), pane.proxy.rowCount()
    # Ctrl+L opens the location field.
    key(Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier); assert pane.location_stack.currentWidget() is pane.path
    w.escape_action(); assert pane.location_stack.currentWidget() is pane.crumb
    # Documented in Help.
    keys = {k for _, k, _ in w.keybinding_rows()}
    assert {'Type a name', 'Backspace', 'Alt+Left', 'Alt+Right', 'F5', 'Ctrl+L'} <= keys, keys
    w.close(); app.processEvents()
print('U3 keyboard OK · type-ahead · Backspace · Alt+Left/Right · F5 · Ctrl+L · documented')
