#!/usr/bin/env python3
import os
import tempfile
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from niruorg.services.theme_watcher import ThemeWatcher

app = QCoreApplication([])
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    appearance = root / 'niruwm' / 'appearance.toml'
    kitty = root / 'nirux' / 'theme' / 'kitty.conf'
    appearance.parent.mkdir(parents=True)
    kitty.parent.mkdir(parents=True)
    appearance.write_text('[font]\nsize = 13\n')
    kitty.write_text('background #101010\nforeground #eeeeee\n')
    paths = {'appearance': appearance, 'niruwm_config': root / 'niruwm' / 'config.toml', 'kitty': kitty}
    watcher = ThemeWatcher(paths=paths)
    seen = []
    watcher.changed.connect(lambda palette: (seen.append(palette), loop.quit()))
    watcher.start()
    loop = QEventLoop()
    replacement = kitty.with_suffix('.new')
    replacement.write_text('background #202020\nforeground #dddddd\n')
    os.replace(replacement, kitty)
    QTimer.singleShot(3000, loop.quit)
    loop.exec()
    watcher.stop()
    assert seen, 'theme watcher did not emit after atomic replacement'
    assert seen[-1]['bg'] == '#202020', seen[-1]
print('NIRUX theme watcher regression OK')
