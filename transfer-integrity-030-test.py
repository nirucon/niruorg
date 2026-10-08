#!/usr/bin/env python3
"""Qt-free integration checks of the actual TransferWorker method bodies.

The worker class is extracted from the app AST with minimal signal stubs; file
copy, staging and publish operations are executed on temporary LOCAL files only.
This is not a substitute for real SSHFS/rclone/Wayland integration tests.
"""
import ast
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from niruorg.transfer_safety import TransferSafetyError, verified_partial_offset, guard_transfer_locations

class SignalSink:
    def __init__(self): self.rows = []
    def emit(self, *args): self.rows.append(args)
class WorkerSignals:
    def __init__(self):
        self.done = SignalSink(); self.failed = SignalSink()
        self.progress = SignalSink(); self.activity = SignalSink()
class QRunnable: pass

app = Path(__file__).parent / 'niruorg' / 'app.py'
tree = ast.parse(app.read_text())
node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TransferWorker')
ns = dict(QRunnable=QRunnable, WorkerSignals=WorkerSignals, Path=Path,
          TransferSafetyError=TransferSafetyError,
          verified_partial_offset=verified_partial_offset,
          guard_transfer_locations=guard_transfer_locations,
          os=os, shutil=shutil, tempfile=tempfile, uuid=uuid)
exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])), str(app), 'exec'),ns)
TransferWorker = ns['TransferWorker']

def run(source, target_dir, *, move=False, policy='replace'):
    worker = TransferWorker([source], target_dir, move, policy)
    worker.run()
    return worker

with tempfile.TemporaryDirectory(prefix='niruorg-safety-030-') as tmp:
    root=Path(tmp); source=root/'from'; dst=root/'to'
    source.mkdir(); dst.mkdir()
    f=source/'file.bin'; f.write_bytes(b'NEW CONTENT'*1200)
    previous=dst/'file.bin'; previous.write_bytes(b'ORIGINAL DATA')
    # Corrupted partial is refused without changing original destination.
    p=dst/'file.bin.niruorg-part'; p.write_bytes(b'WRONG DATA')
    w=run(f,dst)
    assert w.signals.failed.rows and previous.read_bytes()==b'ORIGINAL DATA'
    assert p.read_bytes()==b'WRONG DATA'
    # Correct partial is verifiably resumable and replaces atomically.
    p.write_bytes(f.read_bytes()[:500])
    w=run(f,dst)
    assert not w.signals.failed.rows and len(w.signals.done.rows)==1
    assert previous.read_bytes()==f.read_bytes() and not p.exists()
    # Empty partial and empty source are also legitimate.
    f.write_bytes(b''); p.write_bytes(b'')
    w=run(f,dst)
    assert not w.signals.failed.rows and previous.read_bytes()==b''
    # Self-copy and recursive folder transfer are refused rather than looping.
    assert run(f,source).signals.failed.rows
    folder=source/'myfolder'; folder.mkdir(); (folder/'keep.txt').write_text('new')
    existing=dst/'myfolder'; existing.mkdir(); (existing/'keep.txt').write_text('original')
    nested=(folder/'sub'); nested.mkdir()
    assert run(folder,nested).signals.failed.rows
    assert not (nested/'myfolder').exists()
    # Cancelled directory replacement leaves ORIGINAL directory untouched.
    w=TransferWorker([folder],dst,False,'replace')
    w.cancel(); w.run()
    assert (existing/'keep.txt').read_text()=='original'
    # Successful directory replacement installs staged tree.
    w=run(folder,dst)
    assert not w.signals.failed.rows
    assert (existing/'keep.txt').read_text()=='new'
    assert not list(dst.glob('.niruorg-stage-*'))
    # Inject failure AFTER original target has been backed up and ensure rollback.
    (existing/'keep.txt').write_text('must-survive')
    real_replace = os.replace
    def break_publish(a,b):
        if '.niruorg-stage-' in str(a) and Path(b)==existing:
            raise OSError('injected publish failure')
        return real_replace(a,b)
    ns['os'].replace = break_publish
    try:
        w=run(folder,dst)
        assert w.signals.failed.rows
        assert (existing/'keep.txt').read_text()=='must-survive'
    finally:
        ns['os'].replace = real_replace
    # A cancelled file replacement must not change the existing target either.
    old=dst/'file.bin'; old.write_bytes(b'STILL HERE')
    big=source/'file.bin'; big.write_bytes(b'CHANGED')
    w=TransferWorker([big],dst,False,'replace'); w.cancel(); w.run()
    assert old.read_bytes()==b'STILL HERE'

    # Keep both must retain previous target rather than overwrite.
    f.write_text('again')
    w=run(f,dst,policy='keepboth')
    assert not w.signals.failed.rows and (dst/'file (2).bin').read_text()=='again'
    # Symlink sources retain link identity; no target traversal.
    link=source/'external.link'; link.symlink_to('/tmp/some-unrelated-location')
    w=run(link,dst)
    assert not w.signals.failed.rows and (dst/'external.link').is_symlink()
    assert os.readlink(dst/'external.link')=='/tmp/some-unrelated-location'
    # File copy errors must not delete an earlier directory with the same name.
    (dst/'file.bin').unlink(); (dst/'file.bin').mkdir()
    assert run(f,dst).signals.failed.rows and (dst/'file.bin').is_dir()
print('Transfer integrity 0.4.0 · local copy/replace/resume/cancel/symlink/self-copy OK')
