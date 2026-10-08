from pathlib import Path
s=Path("niruorg/app.py").read_text()
for needle in [
 "def pane_side(self,pane):",
 "def other_side(self,pane=None):",
 "return f'Open in {self.other_side()} pane'",
 "return f'Copy to {self.other_side()} pane'",
 "return f'Move to {self.other_side()} pane…'",
 "('● ' if active else '  ')+base",
 "pane.update_breadcrumbs()",
 "capitalize()} active · ",
 "self.copy_other_action.setText(self.copy_other_label())",
]:
 assert needle in s, needle
assert "VERSION='0.4.0'" in s
print("0.4.0 active pane UX regression OK")
