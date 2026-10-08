#!/usr/bin/env python3
from pathlib import Path
s=(Path(__file__).parent/'niruorg/app.py').read_text()
checks={
 'version':"VERSION='0.4.0'" in s,
 'connection editor parented to manager':"box=NiruDialog(d); box.setWindowTitle(title); box.setModal(True)" in s,
 'connection editor Wayland-safe':"box.raise_()" not in s and "box.activateWindow()" not in s,
 'connection click status':"status.setText('Opening connection editor…')" in s,
 'audio open integration':"return self.play_audio()" in s,
 'NIRU Player context action':"Play in NIRU Player" in s,
 'gallery explicit controls':all(x in s for x in ["prev=QPushButton('Previous')","nxt=QPushButton('Next')","full=QPushButton('Exit fullscreen' if fullscreen else 'Fullscreen')","close=QPushButton('Close')"]),
 'gallery F11':"QShortcut(QKeySequence('F11'),d,activated=toggle_full)" in s,
 'gallery escape semantics':"if state['fullscreen']:toggle_full()" in s,
}
bad=[k for k,v in checks.items() if not v]
if bad: raise SystemExit('0.0.36 interaction regression FAILED: '+', '.join(bad))
print('0.0.36 interaction regression OK · Connections + Gallery Focus + audio integration')
