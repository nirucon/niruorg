from pathlib import Path
s=(Path(__file__).parent/'niruorg/app.py').read_text()
need=["VERSION='0.4.0'","class PaneTabBar(QTabBar)","Reopen closed tab","Duplicate tab","Move tab to other pane","Open in other pane","Pin tab","Close tabs to the right","Ctrl+Shift+T","Ctrl+Tab","Ctrl+Shift+Tab","def reopen_closed_tab","def duplicate_tab","def toggle_pin","def close_other_tabs","def close_tabs_right","def copy_tab_to_other","def next_tab","session_left_tabs","session_right_tabs",'QTabBar#paneTabs[activePane="true"]::tab:selected',"Qt.MouseButton.MiddleButton","other.tabs.rect().contains(lp)"]
missing=[x for x in need if x not in s]
assert not missing,missing
print('tab UX 0.4.0 contract OK')
