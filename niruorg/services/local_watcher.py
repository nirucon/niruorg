from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal


class LocalDirectoryWatcher(QObject):
    changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.watcher = QFileSystemWatcher(self)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(220)
        self.timer.timeout.connect(self._emit)
        self.watcher.directoryChanged.connect(self._changed)
        self.paths: set[str] = set()
        self.last_path = ''

    def set_paths(self, paths) -> None:
        wanted = {str(Path(path)) for path in paths if Path(path).is_dir()}
        remove = sorted(self.paths - wanted)
        add = sorted(wanted - self.paths)
        if remove:
            self.watcher.removePaths(remove)
        if add:
            self.watcher.addPaths(add)
        self.paths = wanted

    def _changed(self, path: str) -> None:
        self.last_path = path
        self.timer.start()

    def _emit(self) -> None:
        if self.last_path:
            self.changed.emit(self.last_path)
