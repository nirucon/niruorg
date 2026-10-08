from pathlib import Path
s=Path('niruorg/app.py').read_text()
checks=['ScrollBarAlwaysOff','setTextElideMode(Qt.TextElideMode.ElideRight)',"setTabsClosable(False)","def _tab_title(self):","def _install_tab_close(self,i):","paneTabClose","os.path.normpath(str(current))==os.path.normpath(str(Path.home())):leaf='Home'",'border-top:2px solid %(fg)s','border-bottom:2px solid %(fg)s','QProgressBar::chunk {background:%(fg)s;}']
for c in checks: assert c in s,c
assert "VERSION='0.3.0'" in s
print('0.3.0 noir UI polish regression OK')
