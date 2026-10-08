from pathlib import Path
s=Path("niruorg/app.py").read_text()
assert "VERSION='0.4.0'" in s
assert "QTimer.singleShot(0,lambda o=owner,d=dst,x=items" in s
assert "Finish the native Wayland drag transaction" in s
segment=s[s.index("def handle_pane_drop"):s.index("def compare_panes")]
assert "self.confirm('Copy between locations'" not in segment
assert "ok.setDefault(True)" in s
print("0.4.0 Wayland DnD modal regression OK")
