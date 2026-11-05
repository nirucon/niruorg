#!/usr/bin/env python3
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
s=app_source()
find=s[s.index(' def find_files'):s.index(' def err(self,e):')]
compare=s[s.index(' def compare_panes'):s.index(' def choose_conflict_policy')]
assert 'SearchWorker(' in find
assert 'self._start_worker(self.threadpool,worker)' in find
assert 'cancelsearch' in find and "Cancel" in find
assert 'subprocess.run(' not in find
assert 'Add to Work Basket' in find
assert "Compare Workspace" in compare
assert "Copy selected →" in compare and "← Copy selected" in compare
assert 'self.start_transfer' in compare
print('Search / Compare regression OK · 0.0.29')
