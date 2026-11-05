import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
s=app_source()
need=["VERSION='0.6.0'",'def _right_tabs_exhausted','def _show_right_pane','def show_right_pane','self.closed_tabs_global','self._hidden_right_tabs','Transfers still running',"closed['_origin_pane']",'def mouseDoubleClickEvent',"'filter':self.filter.text()", "self.filter.setText(st.get('filter',''))"]
for x in need: assert x in s,x
assert "if self.tabs.count()==0 and self is self.owner.pane1" in s
assert "elif self is self.owner.pane2:self.owner._right_tabs_exhausted()" in s
print('0.5.1 pane/tab state consistency contract OK')
