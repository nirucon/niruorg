#!/usr/bin/env python3
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source, find_def, def_source  # noqa: E402
from pathlib import Path
import ast,re
src=app_source()
assert "VERSION='0.6.1'" in src
assert 'class RemoteProbeWorker(QRunnable)' in src
assert 'self._remote_probe_pool.setMaxThreadCount(2)' in src
assert "self.pane1._commit_go(Path.home(),True)" in src
assert 'QTimer.singleShot(0,self._post_show_startup)' in src
assert "self.status.setText(f'{pane.remote_name} · Checking…')" in src
paths=Path('niruorg/core/paths.py').read_text()
assert 'path_is_mounted' in paths and "Path('/proc/self/mountinfo')" in paths
# Startup/sidebar must not synchronously probe saved paths or invoke rclone.
def body(name):
 try:return def_source(name,kinds=(ast.FunctionDef,ast.AsyncFunctionDef))
 except LookupError:return ''
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
print('startup/remote 0.5.1 regression OK')
