import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
s=app_source()
assert "VERSION='0.6.0'" in s
assert "QTimer.singleShot(0,lambda o=owner,d=dst,x=items" in s
assert "Finish the native Wayland drag transaction" in s
segment=s[s.index("def handle_pane_drop"):s.index("def compare_panes")]
assert "self.confirm('Copy between locations'" not in segment
assert "ok.setDefault(True)" in s
print("0.5.1 Wayland DnD modal regression OK")
