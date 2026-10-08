from pathlib import Path
s=Path('niruorg/app.py').read_text()
assert "VERSION='0.3.0'" in s
assert 'class DiscoveryWorker(QRunnable)' in s
assert 'def _start_worker(self,pool,worker' in s
assert 'worker.setAutoDelete(False)' in s
assert 'self._worker_refs[key]=worker' in s
assert "QTimer.singleShot(0,lambda k=key:self._worker_refs.pop(k,None))" in s
assert "self._start_worker(self._remote_probe_pool,w,('done',))" in s
assert "self._start_worker(self._remote_probe_pool,worker,('done',))" in s
assert 'self._remote_probe_pool.waitForDone(4500)' in s
# Discovery must no longer declare QObject/QRunnable classes inside the method.
body=s.split(' def _discover_external_async(self):',1)[1].split(' def _show_right_pane',1)[0]
assert 'class Discovery' not in body
# Every Main-owned QRunnable start goes through the retention helper.
assert 'self._remote_probe_pool.start(' not in s
assert 'self.threadpool.start(worker)' not in s
print('0.3.0 Qt worker lifetime regression OK')
