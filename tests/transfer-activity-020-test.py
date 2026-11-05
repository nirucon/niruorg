#!/usr/bin/env python3
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
app=app_source()
assert "VERSION='0.6.0'" in app
assert 'activity=Signal(object)' in app
assert "self.signals.activity.emit({'name':src.name,'bytes_done':done,'bytes_total':total})" in app
assert "self.transfer_bar.setObjectName('transferBar')" in app
assert 'self.transfer_cancel.clicked.connect(self._cancel_visible_transfer)' in app
assert 'def _render_transfer(self,worker):' in app
assert "human(rate)}/s" in app
assert 'Cancel transfers and close' in app
assert 'self._close_after_transfers=True' in app
assert 'for worker in list(self.operations):worker.cancel()' in app
print('Transfer activity 0.5.1 OK')
