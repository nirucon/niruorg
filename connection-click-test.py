#!/usr/bin/env python3
"""Qt regression: Connections -> Add connection.

Important: QPushButton.click() invokes the slot synchronously. The Add slot enters
QDialog.exec(), so the original test could never return to its polling callback to
observe the editor. This test schedules the editor inspection *before* clicking;
the single-shot runs inside the editor's nested Qt event loop, verifies ownership
and visibility, then rejects the editor so click() can return normally.
"""
import os, tempfile
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['XDG_CONFIG_HOME'] = tempfile.mkdtemp(prefix='niruorg-qt-test-')
try:
    from PySide6.QtWidgets import QApplication, QDialog, QPushButton
    from PySide6.QtCore import QTimer
    from niruorg.app import Main
except Exception as e:
    print('Connection click-through SKIP · PySide6 unavailable:', e)
    raise SystemExit(0)

app = QApplication.instance() or QApplication([])
main = Main()
state = {'manager': False, 'clicked': False, 'editor': False, 'error': ''}

def visible_manager():
    return next((w for w in QApplication.topLevelWidgets()
                 if isinstance(w, QDialog) and w.isVisible() and w.windowTitle() == 'Connections'), None)

def inspect_editor(manager):
    editor = next((w for w in manager.findChildren(QDialog)
                   if w.isVisible() and w.windowTitle() == 'Add connection'), None)
    if editor is None:
        state['error'] = 'Add connection editor did not open'
        # Release the nested manager loop if something went wrong.
        manager.reject()
        return
    if editor.parentWidget() is not manager:
        state['error'] = 'editor is not owned by Connections dialog'
        editor.reject(); manager.reject(); return
    state['editor'] = True
    editor.reject()  # releases server_editor() / button click synchronously

def start_click():
    manager = visible_manager()
    if manager is None:
        state['error'] = 'Connections dialog did not open'; app.quit(); return
    state['manager'] = True
    button = next((b for b in manager.findChildren(QPushButton)
                   if b.text().replace('&','') == 'Add connection'), None)
    if button is None:
        state['error'] = 'Add connection button not found'; manager.reject(); return
    # Critical ordering: inspect from inside the nested QDialog.exec() event loop.
    QTimer.singleShot(75, lambda: inspect_editor(manager))
    state['clicked'] = True
    button.click()
    # We get here only after the editor was rejected/closed.
    if manager.isVisible(): manager.reject()

def find_manager_then_click():
    manager = visible_manager()
    if manager is not None:
        start_click()
    else:
        QTimer.singleShot(25, find_manager_then_click)

def hard_timeout():
    if not state['editor'] and not state['error']:
        state['error'] = 'timed out waiting for Add connection editor'
    for w in QApplication.topLevelWidgets():
        if isinstance(w, QDialog): w.reject()
    app.quit()

QTimer.singleShot(0, main.manage_servers)
QTimer.singleShot(25, find_manager_then_click)
QTimer.singleShot(2500, hard_timeout)
app.exec()
main.close()

if state['error']:
    print('Connection click-through FAILED · ' + state['error'])
    raise SystemExit(2)
if not (state['manager'] and state['clicked'] and state['editor']):
    print('Connection click-through FAILED · incomplete interaction')
    raise SystemExit(2)
print('Connection click-through OK · Add connection opens editor and closes cleanly')
