#!/usr/bin/env python3
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
s=app_source()
assert "VERSION='0.6.0'" in s
assert "self.s.value('work_basket'" in s
assert 'def _save_work_basket' in s and "self.s.setValue('work_basket'" in s
assert "WORK BASKET · {len(self.dropzone)}" in s
assert 'Intent Actions' in s and 'def all_actions' in s
assert "if self._action_matches(cfg,selected)" in s
assert 'Workspace Snapshots' in s and "'quicklook':self.quickdock.isVisible()" in s and "'active':'right'" in s
ctx=s[s.index(' def context_lens'):s.index(' def _restore_session_state')]
assert 'Context Lens 2.0' in ctx and 'subprocess.run(' not in ctx
assert 'No network calls, daemon or background indexing.' in ctx
print('0.0.29 workflow regression OK')
