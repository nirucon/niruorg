#!/usr/bin/env python3
from pathlib import Path
app=Path(__file__).parent/'niruorg'/'app.py'
s=app.read_text()
segment=s[s.index('  def unlock_prompt(n,v,retry):'):s.index('  def finish(ok,detail=',s.index('  def unlock_prompt(n,v,retry):'))]
assert "tempfile.mkstemp(prefix='niruorg-askpass-'" in segment
assert "with os.fdopen(helper_fd,'w',encoding='utf-8')" in segment
assert 'helper.unlink(missing_ok=True)' in segment
assert 'pass_fds=(helper_fd_r,)' in segment
assert 'tempfile.gettempdir()' not in segment
print('SSH helper safety 0.4.0 · unpredictable temp pathname and inherited secret FD OK')
