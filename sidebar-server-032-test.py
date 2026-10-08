#!/usr/bin/env python3
from pathlib import Path
s=Path('niruorg/app.py').read_text()
assert "VERSION='0.3.0'" in s
for x in ["'__server__:'+n","Disconnected · click to connect","Mounted · checking on open","def open_server_named(self,name,other_pane=False):","self.manage_servers(name,'connect',target)","Open in {self.other_side()} pane","Connection details","Test connection","Duplicate…","Remove…","if initial_action=='connect'","w.itemDoubleClicked.connect(lambda *_:connectone())"]:
 assert x in s,x
assert "Use Go → Servers to connect" not in s
print('0.0.36 sidebar server UX regression OK')
