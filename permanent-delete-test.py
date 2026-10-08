#!/usr/bin/env python3
import os,sys,tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
sys.path.insert(0,os.path.dirname(__file__))
from niruorg.app import Main,VERSION
app=QApplication([]); w=Main()
with tempfile.TemporaryDirectory(prefix='niruorg-delete-test-') as td:
    root=Path(td)
    f=root/'delete-me.txt'; f.write_text('safe test')
    w.selected=lambda:[f]
    w._confirm_permanent_delete=lambda count: count==1
    w.permanent_delete()
    assert not f.exists(), 'confirmed permanent delete did not remove file'
    keep=root/'keep-me.txt'; keep.write_text('safe test')
    w.selected=lambda:[keep]
    w._confirm_permanent_delete=lambda count: False
    w.permanent_delete()
    assert keep.exists(), 'cancelled permanent delete removed file'
    d=root/'delete-dir'; d.mkdir(); (d/'child.txt').write_text('safe test')
    w.selected=lambda:[d]
    w._confirm_permanent_delete=lambda count: True
    w.permanent_delete()
    assert not d.exists(), 'confirmed permanent delete did not remove directory'
print(f'Permanent delete regression OK · {VERSION}')
