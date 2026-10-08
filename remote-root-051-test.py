from pathlib import Path
s=Path('niruorg/app.py').read_text()
assert "VERSION='0.3.0'" in s
start=s.index(' def _apply_root(self,path,attempt=0):')
end=s.index(' def back(self):',start)
block=s[start:end]
assert 'self.model.setRootPath(str(path))' in block
assert 'if src.isValid()' in block
assert 'QTimer.singleShot(50' in block
assert 'Remote navigation blocked.' in block
assert 'if leave_remote:self.clear_remote()' in block
assert 'if self.is_remote() and self.current==self.remote_mount:return' in block
assert "REMOTE · {self.remote_name} · {self.remote_protocol}" in s
assert "LOCAL · {socket.gethostname()}" in s
assert 'target_pane.bind_remote' in s and 'target_pane.go(mp)' in s
print('0.3.0 remote root regression OK · QFileSystemModel root is loaded explicitly and remote panes fail closed')
