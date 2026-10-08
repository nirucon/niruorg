from pathlib import Path
s=(Path(__file__).parent/'niruorg/app.py').read_text()
need=["VERSION='0.3.0'",'def _right_tabs_exhausted','def _show_right_pane','def show_right_pane','self.closed_tabs_global','self._hidden_right_tabs','Transfers still running',"closed['_origin_pane']",'def mouseDoubleClickEvent',"'filter':self.filter.text()", "self.filter.setText(st.get('filter',''))"]
for x in need: assert x in s,x
assert "if self.tabs.count()==0 and self is self.owner.pane1" in s
assert "elif self is self.owner.pane2:self.owner._right_tabs_exhausted()" in s
print('0.3.0 pane/tab state consistency contract OK')
