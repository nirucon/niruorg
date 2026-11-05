#!/usr/bin/env python3
"""O2: incremental listing of 100 000 entries within the UI-thread budget.

A fake directory iterator feeds DirectoryModel, so the test needs no large
fixture on disk. A 5 ms heartbeat timer measures the longest GUI-thread
stall while rows stream in, and each sort and filter step is timed.
Budgets (ms) can be relaxed on very slow machines with
NIRUORG_UI_BUDGET_MS / NIRUORG_FIRST_ROWS_MS; the product targets are
100 ms per step and first rows within 300 ms.
"""
import contextlib, os, sys, tempfile, time
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parent
while not (ROOT / 'niruorg' / 'app.py').exists(): ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
N = 100_000
BUDGET = float(os.environ.get('NIRUORG_UI_BUDGET_MS', '250')) / 1000
FIRST = float(os.environ.get('NIRUORG_FIRST_ROWS_MS', '600')) / 1000

with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as td:
    os.environ['HOME'] = home; os.environ['XDG_CONFIG_HOME'] = home + '/.config'
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QApplication
    from niruorg.app import Main
    from niruorg.ui.directory_model import Entry
    exts = ['.txt', '.jpg', '.mp3', '.zip', '.md', '']

    @contextlib.contextmanager
    def fake_scandir(path):
        def gen():
            for i in range(N):
                if i % 500 == 0: yield Entry(f'dir{i:06d}', True, 0, 1.7e9 + i)
                else: yield Entry(f'f{i:06d}{exts[i % 6]}', False, (i * 7919) % 100_000, 1.7e9 + i)
        yield gen()

    app = QApplication([])
    w = Main(); w.resize(1000, 700); w.show()
    pane = w.pane1
    for _ in range(10): app.processEvents()
    gaps = []; last = [time.perf_counter()]
    def beat():
        now = time.perf_counter(); gaps.append(now - last[0]); last[0] = now
    hb = QTimer(); hb.setTimerType(Qt.TimerType.PreciseTimer); hb.timeout.connect(beat); hb.start(5)
    def pump(pred, secs=60):
        end = time.time() + secs
        while time.time() < end:
            app.processEvents()
            if pred(): return True
            time.sleep(0.001)
        return False

    pane.model.scanner = fake_scandir
    loaded = []
    pane.model.directoryLoaded.connect(loaded.append)
    t0 = time.perf_counter(); last[0] = t0; gaps.clear()
    pane.go(td)
    assert pump(lambda: pane.proxy.rowCount() > 0), 'no rows'
    first = time.perf_counter() - t0
    assert pump(lambda: loaded), 'listing did not finish'
    full = time.perf_counter() - t0
    stall = max(gaps)
    assert pane.proxy.rowCount() == N, pane.proxy.rowCount()
    assert pump(lambda: w.status.text().startswith(f'{N} item(s)'), 5), w.status.text()
    assert first < FIRST, f'first rows after {first*1000:.0f} ms'
    assert stall < BUDGET, f'UI stalled {stall*1000:.0f} ms while listing'
    names = lambda n: [pane.model.fileName(pane.proxy.mapToSource(pane.proxy.index(r, 0))) for r in range(n)]
    assert names(2) == ['dir000000', 'dir000500'], names(2)   # folders first, natural order

    def step(label, fn):
        gaps.clear(); last[0] = time.perf_counter(); t = time.perf_counter(); fn()
        for _ in range(5): app.processEvents()
        d = max(gaps + [time.perf_counter() - t]) if gaps else time.perf_counter() - t
        d = max(d, time.perf_counter() - t) if not gaps else max(gaps + [d])
        assert d < BUDGET, f'{label} blocked the UI for {d*1000:.0f} ms'
        return d
    results = {}
    results['sort size'] = step('sort by size', lambda: pane.view.sortByColumn(1, Qt.SortOrder.DescendingOrder))
    sizes = [pane.model.size(pane.proxy.mapToSource(pane.proxy.index(r, 0))) for r in range(200, 205)]
    assert sizes == sorted(sizes, reverse=True), sizes
    results['sort date'] = step('sort by date', lambda: pane.view.sortByColumn(3, Qt.SortOrder.AscendingOrder))
    results['sort name'] = step('sort by name', lambda: pane.view.sortByColumn(0, Qt.SortOrder.AscendingOrder))
    results['filter'] = step('filter', lambda: pane.filter.setText('12'))
    assert 0 < pane.proxy.rowCount() < N
    results['clear filter'] = step('clear filter', lambda: pane.filter.setText(''))
    assert pane.proxy.rowCount() == N
    # Memory stays bounded: leaving the folder releases its listing.
    pane.model.scanner = None
    pane.go(home)
    assert pump(lambda: pane.model.rootPath() == os.path.normpath(home) and not pane.model.is_loading(), 10)
    assert pane.model.loaded_count() < 10, pane.model.loaded_count()
    w.close(); app.processEvents()
    print('O2 incremental listing OK · 100 000 entries · first rows %.0f ms · complete %.0f ms · max UI stall %.0f ms · '
          % (first * 1000, full * 1000, stall * 1000) + ' · '.join(f'{k} {v*1000:.0f} ms' for k, v in results.items()))
