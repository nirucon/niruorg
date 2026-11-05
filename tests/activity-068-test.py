#!/usr/bin/env python3
"""U1: a slow listing shows a non-modal "Listing… N items" row with Cancel;
a slow remote connect shows "Connecting to …" with Cancel; fast work shows
nothing."""
import contextlib, os, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as td:
    os.environ['HOME'] = home; os.environ['XDG_CONFIG_HOME'] = home + '/.config'
    Path(td, 'one.txt').write_text('1')
    from PySide6.QtWidgets import QApplication
    import niruorg.app as appmod
    from niruorg.app import Main
    from niruorg.ui.directory_model import Entry
    app = QApplication([])
    w = Main(); w.resize(900, 600); w.show()
    pane = w.pane1
    def pump(pred, secs=10):
        end = time.time() + secs
        while time.time() < end:
            app.processEvents()
            if pred(): return True
            time.sleep(0.005)
        return False
    # Fast folder: no activity row.
    pane.go(td); assert pump(lambda: not pane.model.is_loading())
    pump(lambda: False, 0.4); assert not pane.activity.isVisible()
    # Slow folder: the row appears, counts, and Cancel stops the listing.
    @contextlib.contextmanager
    def slow_scandir(path):
        def gen():
            for i in range(100000):
                if i % 200 == 0: time.sleep(0.02)
                yield Entry(f'f{i:06d}', False, i, 1.7e9)
        yield gen()
    pane.model.scanner = slow_scandir
    pane.go(home)
    assert pump(lambda: pane.activity.isVisible() and 'items' in pane.activity_label.text(), 5), pane.activity_label.text()
    text = pane.activity_label.text()
    assert text.startswith('Listing… ') and text.endswith(' items'), text
    assert pane.isEnabled() and pane.view.isEnabled() and w.isEnabled()  # non-modal
    pane.activity_cancel.click()
    assert pump(lambda: not pane.model.is_loading(), 2)
    shown = pane.proxy.rowCount()
    pump(lambda: False, 0.3)
    assert not pane.activity.isVisible() and pane.proxy.rowCount() == shown and 0 < shown < 100000
    assert 'listing cancelled · F5 lists again' in w.status.text(), w.status.text()
    pane.model.scanner = None
    # Slow remote connect: "Connecting to …" with Cancel; the late result is ignored.
    class SlowProbe(appmod.QRunnable):
        def __init__(self, token, path, mount):
            super().__init__(); self.token = token; self.path = str(path); self.signals = appmod.RemoteProbeSignals()
        def run(self):
            time.sleep(1.0); self.signals.done.emit({'ok': True, 'path': self.path, 'token': self.token})
    appmod.RemoteProbeWorker = SlowProbe
    mnt = Path(td, 'mnt'); mnt.mkdir()
    pane.bind_remote('testbox', 'SFTP', str(mnt), '/')
    w.navigate_remote_async(pane, mnt)
    assert pump(lambda: pane.activity.isVisible(), 3)
    assert pane.activity_label.text() == 'Connecting to testbox…', pane.activity_label.text()
    assert not pane.view.isEnabled()
    pane.activity_cancel.click()
    assert pane.view.isEnabled() and 'Connection cancelled' in w.status.text(), w.status.text()
    pump(lambda: False, 1.5)
    assert 'Connection cancelled' in w.status.text(), w.status.text()  # late probe result ignored
    w._remote_probe_pool.waitForDone(3000)
    w.close(); app.processEvents()
print('U1 activity OK · listing progress with Cancel · connect progress with Cancel · nothing for fast work')
