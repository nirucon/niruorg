import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
s=app_source()
assert "VERSION='0.6.0'" in s
start=s.index(' def _apply_root(self,path,attempt=0):')
end=s.index(' def back(self):',start)
block=s[start:end]
# 0.6.0: DirectoryModel (flat, worker-thread listing) replaced QFileSystemModel.
# The pane root is applied explicitly and the view root is the flat top level,
# so an invalid source index can no longer expose the local filesystem root.
assert 'self.model.setRootPath(str(path))' in block
assert 'self.view.setRootIndex(QModelIndex())' in block
assert 'self.model=DirectoryModel(self)' in s
assert 'Remote navigation blocked.' in block
assert 'if leave_remote:self.clear_remote()' in block
assert 'if self.is_remote() and self.current==self.remote_mount:return' in block
assert "REMOTE · {self.remote_name} · {self.remote_protocol}" in s
assert "LOCAL · {socket.gethostname()}" in s
assert 'target_pane.bind_remote' in s and 'target_pane.go(mp)' in s
print('0.5.1 remote root regression OK · pane root is loaded explicitly and remote panes fail closed')
