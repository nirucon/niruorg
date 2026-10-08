#!/usr/bin/env python3
import os,sys
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QEvent
from PySide6.QtGui import QKeyEvent
sys.path.insert(0,os.path.dirname(__file__))
from niruorg.app import Main,VERSION,BrowserTree
app=QApplication([]); w=Main(); w.show(); app.processEvents()
expected={"Delete","Shift+Delete","F2","F5","Ctrl+C","Ctrl+X","Ctrl+V","Ctrl+A","Ctrl+F","Ctrl+P","Ctrl+K","Ctrl+L","Alt+Left","Alt+Right","Alt+Home","Alt+Return","Backspace","Space","F3","F10"}
doc={key for _,key,_ in w.keybinding_rows()}; assert not expected-doc, f"Missing documented bindings: {sorted(expected-doc)}"
assert isinstance(w.pane1.view,BrowserTree) and isinstance(w.pane2.view,BrowserTree)
# Verify the real receiver path: QKeyEvent -> BrowserTree.keyPressEvent -> dispatch -> final operation.
hits=[]
w.permanent_delete=lambda:hits.append(("permanent",w.active))
w.trash=lambda:hits.append(("trash",w.active))
ev=QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Delete,Qt.KeyboardModifier.ShiftModifier)
QApplication.sendEvent(w.pane1.view,ev)
assert hits==[("permanent",w.pane1)], hits
hits.clear()
ev=QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Delete,Qt.KeyboardModifier.NoModifier)
QApplication.sendEvent(w.pane2.view,ev)
assert hits==[("trash",w.pane2)], hits
# Mapping remains exact and tolerates irrelevant platform keypad bit.
assert w._dispatch_browser_key(Qt.Key.Key_Delete,Qt.KeyboardModifier.ShiftModifier,execute=False)=="Shift+Delete"
assert w._dispatch_browser_key(Qt.Key.Key_Delete,Qt.KeyboardModifier.NoModifier,execute=False)=="Delete"
assert w._dispatch_browser_key(Qt.Key.Key_Delete,Qt.KeyboardModifier.ShiftModifier|Qt.KeyboardModifier.KeypadModifier,execute=False)=="Shift+Delete"
print(f"Shortcut regression OK · {VERSION}")
