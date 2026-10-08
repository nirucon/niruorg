from pathlib import Path
s=Path('niruorg/app.py').read_text()
checks=["VERSION='0.3.0'","self.tabs=PaneTabBar(self)","def new_tab(","def close_tab(","def _switch_tab(","Ctrl+T","Ctrl+W","Resumable transfers","Not enough free space","Root matches package name","def terminal_here","d.setWindowTitle('Locations')","def compare_panes","def duplicate_finder","def bulk_rename","def package_inspector","def operation_queue","def manage_workspaces","def actions"]
for x in checks: assert x in s,x
assert "importb.clicked.connect" not in s[s.index('def manage_targets'):s.index('def send_target')]
print('milestone 0.3.0: OK')
