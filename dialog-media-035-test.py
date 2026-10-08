#!/usr/bin/env python3
from pathlib import Path
app=Path('niruorg/app.py').read_text()
assert "VERSION='0.3.0'" in app
assert "def addone():" in app and "server_editor('Add connection')" in app
assert "Could not open connection editor" in app
assert "if label is not None:label.setVisible(visible)" in app
assert "def niru_player(" in app and "--input-ipc-server=" in app
assert "def play_audio(" in app and "NIRU Player (MPV backend)" in app
assert "def image_viewer(self,files,start=0,fullscreen=False,parent=None)" in app
assert "if fullscreen:d.showFullScreen()" in app
assert "d.escape_handler=escape" in app
assert "self.audio_player=self.s.value('audio_player'" in app
print('Dialog / media regression OK · 0.0.36')
