#!/usr/bin/env python3
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
app=Path(__file__).resolve().parents[1]/'niruorg'/'app.py'
s=app_source()
segment=s[s.index('  def unlock_prompt(n,v,retry):'):s.index('  def finish(ok,detail=',s.index('  def unlock_prompt(n,v,retry):'))]
assert "tempfile.mkstemp(prefix='niruorg-askpass-'" in segment
assert "with os.fdopen(helper_fd,'w',encoding='utf-8')" in segment
assert 'helper.unlink(missing_ok=True)' in segment
assert 'pass_fds=(helper_fd_r,)' in segment
assert 'tempfile.gettempdir()' not in segment
print('SSH helper safety 0.5.1 · unpredictable temp pathname and inherited secret FD OK')
