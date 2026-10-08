#!/usr/bin/env python3
from pathlib import Path
s=Path('niruorg/app.py').read_text()
assert "VERSION='0.4.0'" in s
assert "MIME='application/x-niruorg-files'" in s
assert 'def startDrag(self,supported):' in s
assert "mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])" in s
assert "mime.setData(self.MIME" in s
assert 'def _drop_target(self,event):' in s
assert 'source is not self.pane' in s
assert 'def handle_pane_drop(self,dst,items,drop_action,src=None,target_dir=None):' in s
assert 'self.start_transfer(items,target,False,source_label,dest_label)' in s
print('0.4.0 local/remote cross-pane drag-and-drop regression OK')
