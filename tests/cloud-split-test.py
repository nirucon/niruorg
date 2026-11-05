#!/usr/bin/env python3
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
app=app_source()
assert "def manage_clouds" in app and "def open_cloud" in app and "def unmount_cloud" in app
assert "rclone" in app and "Google Drive" in app and "OneDrive / Microsoft 365" in app
assert "--vfs-cache-mode','writes','--daemon'" in app
assert "config','redacted'" in app, 'Cloud type inspection must not expose OAuth tokens'
assert "self._sidebar_section('cloud','CLOUD',self._cloud_sidebar_entries(),True)" in app
assert "self._sidebar_section('shortcuts','SHORTCUTS',entries,True)" in app
assert "def close_split" in app and "self.pane2.close_split.show()" in app
assert "self.pane2.hide(); self.pane2.close_split.hide(); self.set_active(self.pane1)" in app
print('Cloud / split regression OK')
