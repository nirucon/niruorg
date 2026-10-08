#!/usr/bin/env python3
from pathlib import Path
import ast,re
src=Path('niruorg/app.py').read_text()
assert "VERSION='0.3.0'" in src
assert 'class RemoteProbeWorker(QRunnable)' in src
assert 'self._remote_probe_pool.setMaxThreadCount(2)' in src
assert "self.pane1._commit_go(Path.home(),True)" in src
assert 'QTimer.singleShot(0,self._post_show_startup)' in src
assert "self.status.setText(f'{pane.remote_name} · Checking…')" in src
assert 'path_is_mounted' in src and "Path('/proc/self/mountinfo')" in src
# Startup/sidebar must not synchronously probe saved paths or invoke rclone.
tree=ast.parse(src)
def body(name):
 for n in ast.walk(tree):
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name:return ast.get_source_segment(src,n) or ''
 return ''
sidebar=body('build_sidebar')
assert '.exists()' not in sidebar
assert '.iterdir()' not in sidebar
assert 'os.path.ismount' not in sidebar
assert 'subprocess.' not in sidebar
cloud=body('_cloud_sidebar_entries')
assert 'subprocess.' not in cloud and '.exists()' not in cloud
restore=body('_restore_session_state')
assert '.is_dir()' not in restore and '.exists()' not in restore and '.resolve()' not in restore
identify=body('_identify_remote_path')
assert '.resolve()' not in identify and 'os.path.ismount' not in identify
main=body('main')
assert "Path(sys.argv[1]).is_dir()" not in main
print('startup/remote 0.3.0 regression OK')
