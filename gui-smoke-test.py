#!/usr/bin/env python3
import os,sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
sys.path.insert(0,os.path.dirname(__file__))
from niruorg.app import Main, VERSION
app=QApplication([])
w=Main()
assert w.centralWidget() is not None
assert hasattr(w,'pane1') and hasattr(w,'pane2')
assert w.pane1.view.model() is w.pane1.proxy
assert w.pane1.proxy.sourceModel() is w.pane1.model
assert w.sidebar.count() > 0
assert w.active in (w.pane1,w.pane2)
w.apply_theme()
w.pane1.go(os.path.expanduser('~'),False)
assert os.path.isdir(str(w.pane1.current))
assert len(w.pane1.selected()) == 0
assert w.pane1.location_stack.currentWidget() is w.pane1.crumb
w.pane1.edit_location(); assert w.pane1.location_stack.currentWidget() is w.pane1.path
w.pane1.commit_location(); assert w.pane1.location_stack.currentWidget() is w.pane1.crumb
assert hasattr(w,'undo_stack') and hasattr(w,'progress')
assert hasattr(w,'quickdock') and w.quicklook_requested is False
w.toggle_quicklook(); assert w.quicklook_requested is True and not w.quickdock.isHidden(); w.toggle_quicklook(); assert w.quicklook_requested is False and w.quickdock.isHidden()
assert hasattr(w,'add_shortcuts') and hasattr(w,'manage_shortcuts')
assert w.sidebar.acceptDrops()
assert w.date_format in ('Swedish','ISO','Compact','System')
w.date_format='Swedish'; w.refresh_views()
assert w.format_dt(0)[2:3] == '-' or w.format_dt(0).startswith('1970')
# Offscreen Qt + QFileSystemModel can crash in some Qt/PySide6 builds when a
# synthetic window enters a timed event loop. The installer smoke test verifies
# construction and widget/model wiring without pretending to test a compositor.
if os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
    w.close()
    app.processEvents()
else:
    w.show()
    QTimer.singleShot(200,app.quit)
    rc=app.exec()
    assert rc == 0

assert hasattr(w,'jump') and hasattr(w,'find_files') and hasattr(w,'toggle_focus')
assert hasattr(w,'eventFilter') and hasattr(w,'archive_browser') and hasattr(w,'temporary_split')
assert hasattr(w,'show_keybindings') and len(w.keybinding_rows()) >= 30
assert hasattr(w,'quick_create') and hasattr(w,'refresh_current') and hasattr(w.pane1,'forward')
old=w.theme; w.apply_theme(); assert w.theme==old
print(f'GUI smoke OK · {VERSION}')
