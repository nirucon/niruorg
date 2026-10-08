#!/usr/bin/env python3
"""Static regression contract for 0.4.0 FUSE ownership/lifecycle safety."""
from pathlib import Path
s=(Path(__file__).parent/'niruorg/app.py').read_text()
assert "VERSION='0.4.0'" in s
for name in ('_claim_mount','_release_mount','_detach_remote_models_for_shutdown','_unmount_owned_path','_cleanup_owned_mounts'):
    assert f'def {name}' in s, name
assert "aboutToQuit.connect(self._shutdown_remote_resources)" in s
assert "def _shutdown_remote_resources" in s
assert "self._detach_remote_models_for_shutdown()" in s
assert "self._cleanup_owned_mounts()" in s
assert "['-uz',mp]" in s, 'lazy fusermount fallback missing'
assert "timeout=2" in s, 'shutdown unmount must be bounded'
assert "self._claim_mount(mp,'server',n)" in s
assert "if created_here:self._claim_mount(mp,'cloud',name)" in s
assert "run_async(exe,args,'disconnect',n,8,mp)" in s
# Remote mount status must be mountinfo metadata, not os.path.ismount/stat on FUSE.
assert 'os.path.ismount(' not in s
print('Mount lifecycle 0.4.0 regression OK')
