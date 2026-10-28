from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal

from .theme import load_nirux_palette, theme_paths


class ThemeWatcher(QObject):
    changed = Signal(dict)

    def __init__(self, parent=None, paths: dict[str, Path] | None = None) -> None:
        super().__init__(parent)
        self.paths = dict(paths or theme_paths())
        self.watcher = QFileSystemWatcher(self)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(140)
        self.timer.timeout.connect(self._emit)
        self.watcher.fileChanged.connect(self._on_change)
        self.watcher.directoryChanged.connect(self._on_change)
        self._enabled = False
        self._sync_paths()

    def start(self) -> None:
        self._enabled = True
        self._sync_paths()

    def stop(self) -> None:
        self._enabled = False
        self.timer.stop()
        watched = self.watcher.files() + self.watcher.directories()
        if watched:
            self.watcher.removePaths(watched)

    def _sync_paths(self) -> None:
        if not self._enabled:
            return
        wanted = set()
        for path in self.paths.values():
            if path.exists():
                wanted.add(str(path))
            if path.parent.exists():
                wanted.add(str(path.parent))
        current = set(self.watcher.files() + self.watcher.directories())
        add = sorted(wanted - current)
        remove = sorted(current - wanted)
        if remove:
            self.watcher.removePaths(remove)
        if add:
            self.watcher.addPaths(add)

    def _on_change(self, _path: str) -> None:
        if not self._enabled:
            return
        self._sync_paths()
        self.timer.start()

    def _emit(self) -> None:
        self._sync_paths()
        self.changed.emit(load_nirux_palette(self.paths))
