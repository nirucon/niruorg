import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
s=app_source()
checks=['ScrollBarAlwaysOff','setTextElideMode(Qt.TextElideMode.ElideRight)',"setTabsClosable(False)","def _tab_title(self):","def _install_tab_close(self,i):","paneTabClose","os.path.normpath(str(current))==os.path.normpath(str(Path.home())):leaf='Home'",'border-top:2px solid %(fg)s','border-bottom:2px solid %(fg)s','QProgressBar::chunk {background:%(fg)s;}']
for c in checks: assert c in s,c
assert "VERSION='0.6.1'" in s
print('0.5.1 noir UI polish regression OK')
