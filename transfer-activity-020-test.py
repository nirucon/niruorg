#!/usr/bin/env python3
from pathlib import Path
app=Path('niruorg/app.py').read_text()
assert "VERSION='0.3.0'" in app
assert 'activity=Signal(object)' in app
assert "self.signals.activity.emit({'name':src.name,'bytes_done':done,'bytes_total':total})" in app
assert "self.transfer_bar.setObjectName('transferBar')" in app
assert 'self.transfer_cancel.clicked.connect(self._cancel_visible_transfer)' in app
assert 'def _render_transfer(self,worker):' in app
assert "human(rate)}/s" in app
assert 'Cancel transfers and close' in app
assert 'self._close_after_transfers=True' in app
assert 'for worker in list(self.operations):worker.cancel()' in app
print('Transfer activity 0.3.0 OK')
