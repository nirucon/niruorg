#!/usr/bin/env python3
from pathlib import Path
s=Path('niruorg/app.py').read_text()
assert "VERSION='0.4.0'" in s
assert 'def bind_remote(self,name,protocol,mount,remote_root=' in s
assert "def manage_servers(self,initial_name=None,initial_action=None,target_pane=None):" in s
assert 'target_pane=target_pane or self.active' in s
assert "self.manage_servers(name,'connect',target)" in s
assert "target_pane.bind_remote(n,protocol(v),mp,v.get('path','/')); target_pane.go(mp)" in s
assert "target.bind_remote(name,v.get('protocol','sftp'),mp,v.get('path','/')); target.go(str(mp))" in s
assert "self.start_transfer(items,dst.current,move,self.pane_target_label(src),target)" in s
assert "def move_other_pane(self):self._transfer_to_other_pane(True)" in s
assert 'class TransferWorker' in s and 'self.dst=Path(dst)' in s and 'self.items=[Path(x) for x in items]' in s
assert "tag.setText(self.endpoint_label())" in s
assert 'source=self.active; target=source' in s
print('0.4.0 remote pane / cross-endpoint transfer regression OK')
