from pathlib import Path
s=Path('niruorg/app.py').read_text()
start=s.index('  def after_mount(n,mp):')
end=s.index('  def run_async(', start)
block=s[start:end]
assert 'cfg=data.get(n)' in block
assert 'protocol(cfg)' in block
assert "cfg.get('path','/')" in block
assert 'protocol(v)' not in block
assert 'target_pane.bind_remote' in block
assert 'target_pane.go(mp)' in block
assert 'target_pane.is_remote()' in block
assert 'target_pane._path_inside_remote(target_pane.current)' in block
assert "VERSION='0.4.0'" in s
print('0.4.0 remote pane binding regression OK · async mount cannot fall back to local pane')
