#!/usr/bin/env python3
"""U4: the pane explains an empty list: empty folder (Open terminal here),
permission denied (Retry), disconnected mount (Reconnect), server not
responding (Retry); plus no filter matches and only-hidden items."""
import os, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as td:
    os.environ['HOME'] = home; os.environ['XDG_CONFIG_HOME'] = home + '/.config'
    root = Path(td); empty = root / 'empty'; empty.mkdir()
    hidden = root / 'hidden'; hidden.mkdir(); (hidden / '.secret').write_text('x')
    locked = root / 'locked'; locked.mkdir(); (locked / 'a.txt').write_text('a')
    full = root / 'full'; full.mkdir(); (full / 'notes.txt').write_text('n')
    from PySide6.QtWidgets import QApplication
    import niruorg.app as appmod
    from niruorg.app import Main
    app = QApplication([])
    w = Main(); w.resize(1000, 700); w.show()
    pane = w.pane1
    def pump(pred=lambda: False, secs=3):
        end = time.time() + secs
        while time.time() < end:
            app.processEvents()
            if pred(): return True
            time.sleep(0.005)
        return pred()
    st = pane.state
    # Empty folder.
    pane.go(str(empty)); assert pump(lambda: st.kind == 'empty'), st.kind
    assert st.isVisible() and st.title.text() == 'This folder is empty' and st.action.text() == 'Open terminal here'
    calls = []; w.terminal_here = lambda: calls.append(pane.current)
    st.action.click(); assert calls == [empty], calls
    # Only hidden items.
    pane.go(str(hidden)); assert pump(lambda: st.kind == 'hidden'), st.kind
    assert st.action.text() == 'Show hidden files'
    st.action.click(); assert pump(lambda: pane.proxy.rowCount() == 1 and not st.isVisible()), (pane.proxy.rowCount(), st.kind)
    w.toggle_hidden(); pump(lambda: st.kind == 'hidden')
    # Folder with content: no message; a filter without matches explains itself.
    pane.go(str(full)); assert pump(lambda: pane.proxy.rowCount() == 1); assert not st.isVisible()
    pane.filter.setText('zzz'); assert pump(lambda: st.kind == 'nomatch'), st.kind
    assert st.action.text() == 'Clear filter'
    st.action.click(); assert pump(lambda: pane.proxy.rowCount() == 1 and not st.isVisible())
    # Permission denied (skipped when running as root, which can read anything).
    if os.geteuid() != 0:
        locked.chmod(0)
        try:
            pane.go(str(locked)); assert pump(lambda: st.kind == 'permission'), st.kind
            assert st.title.text() == 'No permission to open this folder' and st.action.text() == 'Retry'
            locked.chmod(0o755); st.action.click()
            assert pump(lambda: pane.proxy.rowCount() == 1 and not st.isVisible()), st.kind
        finally:
            locked.chmod(0o755)
    # Remote states, with a fake probe: not mounted -> Reconnect; no answer -> Retry.
    results = []
    class FakeProbe(appmod.QRunnable):
        def __init__(self, token, path, mount):
            super().__init__(); self.token = token; self.path = str(path); self.signals = appmod.RemoteProbeSignals()
        def run(self):
            self.signals.done.emit(dict(results[-1], token=self.token, path=self.path))
    import niruorg.ui.remote as _remote_mod
    appmod.RemoteProbeWorker = _remote_mod.RemoteProbeWorker = FakeProbe
    mnt = root / 'mnt'; mnt.mkdir(); (mnt / 'remote.txt').write_text('r')
    pane.bind_remote('nas', 'SFTP', str(mnt), '/')
    results.append({'ok': False, 'detail': 'Offline'})
    w.navigate_remote_async(pane, mnt); assert pump(lambda: st.kind == 'disconnected'), st.kind
    assert st.title.text() == 'nas is disconnected' and st.action.text() == 'Reconnect'
    assert pane.proxy.rowCount() == 0  # no stale rows from the previous folder
    reconnects = []; w.manage_servers = lambda *a: reconnects.append(a)
    st.action.click(); assert reconnects and reconnects[0][:2] == ('nas', 'connect'), reconnects
    results.append({'ok': False, 'detail': 'Unavailable · timed out'})
    w.navigate_remote_async(pane, mnt); assert pump(lambda: st.kind == 'unreachable'), st.kind
    assert st.title.text() == 'nas is not responding' and st.action.text() == 'Retry'
    results.append({'ok': True, 'detail': 'Connected'})
    st.action.click(); assert pump(lambda: pane.current == mnt and pane.proxy.rowCount() == 1 and not st.isVisible()), st.kind
    w._remote_probe_pool.waitForDone(2000)
    w.close(); app.processEvents()
print('U4 pane states OK · empty · hidden only · no match · permission · disconnected · not responding')
