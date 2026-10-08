#!/usr/bin/env python3
import os,sys,tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
sys.path.insert(0,os.path.dirname(__file__))
from niruorg.app import Main,TransferWorker,VERSION
app=QApplication([]); w=Main()
with tempfile.TemporaryDirectory(prefix='niruorg-workflow-') as td:
 root=Path(td); f=root/'hello world.txt'; f.write_text('hello')
 cfg={'command':'printf {name} {file}','applies':'Files'}
 argv=w._expand_action(cfg,[f])
 assert argv==['printf','hello world.txt',str(f)],argv
 assert w._action_matches(cfg,[f])
 assert not w._action_matches({'applies':'Folders','command':'x'},[f])
 dst=root/'dst'; dst.mkdir(); worker=TransferWorker([f],dst,False,'replace'); worker.run()
 copied=dst/f.name
 assert copied.read_text()=='hello'
 assert not list(dst.glob('*.niruorg-part'))
print(f'Workflow regression OK · {VERSION}')
