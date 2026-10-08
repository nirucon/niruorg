#!/usr/bin/env python3
from pathlib import Path
s=Path('niruorg/app.py').read_text()
for needle in [
 "VERSION='0.3.0'", "def open_sidebar_location", "def open_sidebar_other",
 "other=m.addAction(self.open_other_label())", "def _transfer_to_other_pane",
 "def copy_other_label(self):", "def move_other_label(self):", "def handle_pane_drop",
 "REMOTE · {self.remote_name} · {self.remote_protocol}", "LOCAL · {socket.gethostname()}",
 "Checking…", "Unavailable", "if action=='disconnect' and ok",
 "str(Path.home()) if self.pane1.is_remote()", "target_pane.bind_remote(name,'CLOUD',mp,'/')",
 "QWidget#filePane[activePane=\"true\"]"
]: assert needle in s, needle
# Remote boundary must remain fail closed.
assert "Remote navigation blocked" in s
assert "if leave_remote:self.clear_remote()" in s
# Move must remain copy-first for regular files/trees.
assert "if self.move:src.unlink()" in s and "if self.move:shutil.rmtree(src)" in s
print('0.3.0 split / remote UX regression OK')
