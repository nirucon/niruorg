#!/usr/bin/env python3
from pathlib import Path
app=(Path(__file__).parent/'niruorg/app.py').read_text()
assert "def manage_clouds" in app and "def open_cloud" in app and "def unmount_cloud" in app
assert "rclone" in app and "Google Drive" in app and "OneDrive / Microsoft 365" in app
assert "--vfs-cache-mode','writes','--daemon'" in app
assert "config','redacted'" in app, 'Cloud type inspection must not expose OAuth tokens'
assert "self._sidebar_section('cloud','CLOUD',self._cloud_sidebar_entries(),True)" in app
assert "self._sidebar_section('shortcuts','SHORTCUTS',entries,True)" in app
assert "def close_split" in app and "self.pane2.close_split.show()" in app
assert "self.pane2.hide(); self.pane2.close_split.hide(); self.set_active(self.pane1)" in app
print('Cloud / split regression OK')
