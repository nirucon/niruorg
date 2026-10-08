#!/usr/bin/env python3
from pathlib import Path
s=Path('niruorg/app.py').read_text()
assert "VERSION='0.4.0'" in s
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
