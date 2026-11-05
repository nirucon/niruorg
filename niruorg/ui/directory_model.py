"""Incremental directory listing model for the NIRUORG file panes.

QFileSystemModel blocks the GUI thread for seconds on large folders: with
100 000 entries it stalled the event loop for 3-14 s while it sorted and
inserted rows, and every proxy sort called back into Python per comparison.
This model keeps all filesystem I/O (``os.scandir`` and ``stat``) on a worker
thread, delivers entries in time-bounded batches, and keeps the GUI-thread
work per batch, sort or filter step to C-level list operations.

It is a flat model of one folder that implements the subset of the
QFileSystemModel API NIRUORG uses (``setRootPath``, ``rootPath``,
``filePath``, ``fileName``, ``isDir``, ``size``, ``fileInfo``,
``lastModified``, ``filter``/``setFilter``, ``setIconProvider`` and the
``directoryLoaded`` signal), with the same columns, headers and display text.
"""
from __future__ import annotations

import atexit
import os
import re
import stat as statmod
import threading
import time
from operator import attrgetter

from PySide6.QtCore import (
    QAbstractItemModel,
    QDateTime,
    QDir,
    QFileInfo,
    QFileSystemWatcher,
    QLocale,
    QMimeData,
    QModelIndex,
    QObject,
    QRunnable,
    QThread,
    QThreadPool,
    QTimer,
    QUrl,
    Qt,
    Signal,
)
from PySide6.QtCore import QMimeDatabase
from PySide6.QtGui import QImage

_NUM = re.compile(r'(\d+)')
_ITEM_FLAGS = (Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsEnabled
               | Qt.ItemFlag.ItemNeverHasChildren)
_NO_FLAGS = Qt.ItemFlag.NoItemFlags
_INVALID = QModelIndex()
_ALIGN_SIZE = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
_DISPLAY = Qt.ItemDataRole.DisplayRole
_DECORATION = Qt.ItemDataRole.DecorationRole
_ALIGN = Qt.ItemDataRole.TextAlignmentRole
_EDIT = Qt.ItemDataRole.EditRole
FIRST_BATCH_ENTRIES = 256
FIRST_BATCH_SECONDS = 0.03
BATCH_SECONDS = 0.12
BATCH_ENTRIES = 10000
INGEST_ENTRIES = 6000


def natural_key(text: str):
    """Case-insensitive natural sort key: ``file2`` sorts before ``file10``."""
    parts = _NUM.split(text.casefold())
    return tuple(int(p) if i & 1 else p for i, p in enumerate(parts))


class Entry:
    __slots__ = ('name', 'fold', 'nat', 'is_dir', 'size', 'mtime', 'hidden', 'suffix')

    def __init__(self, name, is_dir, size, mtime):
        self.name = name
        self.fold = name.casefold()
        self.nat = natural_key(name)
        self.is_dir = is_dir
        self.size = size
        self.mtime = mtime
        self.hidden = name.startswith('.')
        dot = self.fold.rfind('.')
        self.suffix = self.fold[dot + 1:] if dot > 0 else ''

    def same_metadata(self, other) -> bool:
        return self.is_dir == other.is_dir and self.size == other.size and self.mtime == other.mtime


def scan_entry(entry):
    """Return an Entry for one ``os.DirEntry`` or None for a broken symlink.

    QFileSystemModel (QDir without QDir.System) does not list broken symlinks;
    keep that behaviour.
    """
    try:
        st = entry.stat()
    except FileNotFoundError:
        return None
    except OSError:
        try:
            st = entry.stat(follow_symlinks=False)
        except OSError:
            return Entry(entry.name, False, 0, 0.0)
    is_dir = statmod.S_ISDIR(st.st_mode)
    return Entry(entry.name, is_dir, 0 if is_dir else st.st_size, st.st_mtime)


class ListingSignals(QObject):
    batch = Signal(int, object)
    finished = Signal(int, str, str)


class ListingWorker(QRunnable):
    """List one directory on a pool thread and stream time-bounded batches."""

    def __init__(self, generation: int, path: str, scanner=None, clock=time.monotonic):
        super().__init__()
        self.generation = generation
        self.path = path
        self.scanner = scanner or os.scandir
        self.clock = clock
        self.cancelled = threading.Event()
        self.signals = ListingSignals()
        self.setAutoDelete(True)

    def cancel(self) -> None:
        self.cancelled.set()

    def run(self) -> None:
        batch = []
        started = last = self.clock()
        first = True
        count = 0
        try:
            with self.scanner(self.path) as it:
                for entry in it:
                    if self.cancelled.is_set():
                        self.signals.finished.emit(self.generation, 'cancelled', '')
                        return
                    item = entry if isinstance(entry, Entry) else scan_entry(entry)
                    if item is not None:
                        batch.append(item)
                    count += 1
                    if not count & 255:
                        # Hand the GIL to the GUI thread. With cached dentries
                        # stat() barely blocks, and sleep(0) lets this thread
                        # re-take the GIL at once; 100 us really yields.
                        time.sleep(0.0001)
                    now = self.clock()
                    if first:
                        due = len(batch) >= FIRST_BATCH_ENTRIES or now - started >= FIRST_BATCH_SECONDS
                    else:
                        due = len(batch) >= BATCH_ENTRIES or now - last >= BATCH_SECONDS
                    if due and batch:
                        self.signals.batch.emit(self.generation, batch)
                        batch = []
                        last = now
                        first = False
            if batch:
                self.signals.batch.emit(self.generation, batch)
            self.signals.finished.emit(self.generation, '', '')
        except PermissionError as error:
            self.signals.finished.emit(self.generation, 'permission', error.strerror or str(error))
        except FileNotFoundError as error:
            self.signals.finished.emit(self.generation, 'missing', error.strerror or str(error))
        except NotADirectoryError as error:
            self.signals.finished.emit(self.generation, 'missing', error.strerror or str(error))
        except OSError as error:
            self.signals.finished.emit(self.generation, 'io', error.strerror or str(error))
        except Exception as error:  # pragma: no cover - defensive
            self.signals.finished.emit(self.generation, 'io', str(error))


class _WatcherObject(QObject):
    changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.watcher = None
        self.path = ''

    def watch(self, path: str) -> None:
        # Runs on the watcher thread: an inotify watch on a stalled FUSE mount
        # can block, and that must never block the GUI thread.
        if self.watcher is None:
            self.watcher = QFileSystemWatcher(self)
            self.watcher.directoryChanged.connect(self.changed)
        if path == self.path:
            return
        if self.path:
            self.watcher.removePath(self.path)
        self.path = path
        if path:
            self.watcher.addPath(path)


_watch_thread = None


def _shared_watch_thread():
    global _watch_thread
    if _watch_thread is None:
        _watch_thread = QThread()
        _watch_thread.setObjectName('niruorg-directory-watcher')
        _watch_thread.start()
        atexit.register(stop_watch_thread)
    return _watch_thread


def stop_watch_thread() -> None:
    thread = _watch_thread
    if thread is not None and thread.isRunning():
        thread.quit()
        thread.wait(2000)


class DirectoryWatcher(QObject):
    """Watch the listed folder from one shared, event-driven thread.

    Replaces QFileSystemModel's own watcher so that new folders, renames,
    trash and transfers still appear without a manual refresh. The thread
    sleeps in its event loop; there is no polling.
    """

    changed = Signal(str)
    _request = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.obj = _WatcherObject()
        self.obj.moveToThread(_shared_watch_thread())
        self._request.connect(self.obj.watch)
        self.obj.changed.connect(self.changed)

    def watch(self, path: str) -> None:
        self._request.emit(path or '')

    def stop(self) -> None:
        self._request.emit('')


class DirectoryModel(QAbstractItemModel):
    """Flat, incrementally populated model of one directory."""

    directoryLoaded = Signal(str)
    listingStarted = Signal(str)
    listingProgress = Signal(str, int)
    listingFailed = Signal(str, str, str)
    listingCancelled = Signal(str)

    HEADERS = ('Name', 'Size', 'Type', 'Date Modified')
    _pool = None

    def __init__(self, parent=None, watch=True):
        super().__init__(parent)
        self._root = ''
        self._entries = {}
        self._visible = []
        self._row_of = None
        self._by_name = None
        self._filter_flags = QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs
        self._needle = ''
        self._sort_column = 0
        self._sort_order = Qt.SortOrder.AscendingOrder
        self._sorted_once = False
        self._generation = 0
        self._worker = None
        self._loading = False
        self._refresh_pending = False
        self._refreshing = False
        self._pending = {}
        self._error = ('', '')
        self._icons = None
        self._header_spacer = None
        self._mime = QMimeDatabase()
        self._type_cache = {}
        self._locale = QLocale.system()
        self.date_formatter = None
        self.scanner = None
        self._watcher = DirectoryWatcher(self) if watch else None
        if self._watcher is not None:
            self._watcher.changed.connect(self._watched_change)
        self._incoming = []
        self._finish_after_ingest = None
        self._ingest_timer = QTimer(self)
        self._ingest_timer.setSingleShot(True)
        self._ingest_timer.setInterval(0)
        self._ingest_timer.timeout.connect(self._ingest)
        self._watch_timer = QTimer(self)
        self._watch_timer.setSingleShot(True)
        self._watch_timer.setInterval(220)
        self._watch_timer.timeout.connect(self.refresh)

    # ----------------------------------------------------------------- pool
    @classmethod
    def pool(cls):
        # A dedicated pool: a listing stuck on a stalled mount must not starve
        # QThreadPool.globalInstance(), which transfers and workers use.
        if cls._pool is None:
            cls._pool = QThreadPool()
            cls._pool.setMaxThreadCount(4)
            cls._pool.setExpiryTimeout(30000)
        return cls._pool

    def shutdown(self) -> None:
        self.cancel()
        if self._watcher is not None:
            self._watcher.stop()

    # ------------------------------------------------------- compatibility
    def setIconProvider(self, provider) -> None:
        self._icons = provider

    def iconProvider(self):
        return self._icons

    def filter(self):
        return self._filter_flags

    def setFilter(self, flags) -> None:
        old_hidden = bool(self._filter_flags & QDir.Filter.Hidden)
        self._filter_flags = flags
        if bool(flags & QDir.Filter.Hidden) != old_hidden:
            self._relayout()

    def rootPath(self) -> str:
        return self._root

    def setRootPath(self, path) -> QModelIndex:
        """List ``path``. Returns the (invalid) root index of the flat model.

        Re-applying the current root re-lists it in place and keeps the
        selection; a new root resets the model and starts a fresh listing.
        """
        path = os.path.normpath(str(path)) if path else ''
        if path == self._root:
            if path:
                self.refresh()
            return QModelIndex()
        self.cancel(emit=False)
        self._watch_timer.stop()
        self.beginResetModel()
        self._root = path
        self._by_name = None
        self._entries = {}
        self._visible = []
        self._row_of = None
        self._needle = ''
        self._error = ('', '')
        self.endResetModel()
        if self._watcher is not None:
            self._watcher.watch(path)
        if path:
            self._start(refresh=False)
        return QModelIndex()

    def refresh(self) -> None:
        if not self._root:
            return
        if self._loading:
            self._refresh_pending = True
            return
        self._start(refresh=True)

    def cancel(self, emit=True) -> None:
        self._generation += 1
        if self._worker is not None:
            self._worker.cancel()
            self._worker = None
        was_loading = self._loading
        self._loading = False
        self._refresh_pending = False
        self._refreshing = False
        self._pending = {}
        self._incoming = []
        self._finish_after_ingest = None
        self._ingest_timer.stop()
        if emit and was_loading:
            self.listingCancelled.emit(self._root)

    def is_loading(self) -> bool:
        return self._loading

    def error(self):
        return self._error

    def loaded_count(self) -> int:
        return len(self._entries)

    def set_name_filter(self, text: str) -> None:
        needle = (text or '').casefold()
        if needle != self._needle:
            self._needle = needle
            self._relayout()

    def name_filter(self) -> str:
        return self._needle

    # --------------------------------------------------------------- lookup
    def entry(self, index):
        row = index.row()
        if 0 <= row < len(self._visible) and index.isValid():
            return self._visible[row]
        return None

    def filePath(self, index) -> str:
        e = self.entry(index)
        return os.path.join(self._root, e.name) if e else self._root

    def fileName(self, index) -> str:
        e = self.entry(index)
        return e.name if e else os.path.basename(self._root)

    def isDir(self, index) -> bool:
        e = self.entry(index)
        return bool(e.is_dir) if e else bool(self._root)

    def size(self, index) -> int:
        e = self.entry(index)
        return int(e.size) if e else 0

    def lastModified(self, index) -> QDateTime:
        e = self.entry(index)
        return QDateTime.fromMSecsSinceEpoch(int(e.mtime * 1000)) if e else QDateTime()

    def fileInfo(self, index) -> QFileInfo:
        return QFileInfo(self.filePath(index))

    def index_for_name(self, name: str) -> QModelIndex:
        if self._row_of is None:
            self._row_of = {e.name: i for i, e in enumerate(self._visible)}
        row = self._row_of.get(name)
        return self.createIndex(row, 0) if row is not None else QModelIndex()

    def visible_entries(self):
        return self._visible

    # ------------------------------------------------------------ Qt model
    def index(self, row, column=0, parent=None):
        # Hot path: views and selection call this for every cell they touch.
        if 0 <= row < len(self._visible) and 0 <= column < 4 and (parent is None or not parent.isValid()):
            return self.createIndex(row, column)
        return _INVALID

    def parent(self, *args):
        # Flat model: every item is top level. Without an index argument this
        # is QObject.parent(), as callers of a QObject expect.
        if args:
            return QModelIndex()
        return QObject.parent(self)

    def rowCount(self, parent=None):
        return len(self._visible) if parent is None or not parent.isValid() else 0

    def columnCount(self, parent=None):
        return 4 if parent is None or not parent.isValid() else 0

    def hasChildren(self, parent=None):
        return (parent is None or not parent.isValid()) and bool(self._visible)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole and 0 <= section < 4:
            return self.HEADERS[section]
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DecorationRole and section == 0:
            # As QFileSystemModel: a 16 px transparent header decoration lines
            # the "Name" title up with the names after the row icons.
            if self._header_spacer is None:
                self._header_spacer = QImage(16, 1, QImage.Format.Format_ARGB32_Premultiplied)
                self._header_spacer.fill(Qt.GlobalColor.transparent)
            return self._header_spacer
        return None

    def flags(self, index):
        # Called for every cell by view layout and selection (Ctrl+A touches
        # rows x 4 cells): a bounds check and a precomputed constant. The model
        # is flat, so no item ever has children.
        return _ITEM_FLAGS if 0 <= index.row() < len(self._visible) else _NO_FLAGS

    def _type_name(self, e) -> str:
        if e.is_dir:
            return 'Folder'
        key = e.suffix if e.suffix else '\0' + e.fold
        hit = self._type_cache.get(key)
        if hit is None:
            # Name-based only: content sniffing would read every file.
            hit = self._mime.mimeTypeForFile(e.name, QMimeDatabase.MatchMode.MatchExtension).comment()
            self._type_cache[key] = hit
        return hit

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        e = self.entry(index)
        if e is None:
            return None
        col = index.column()
        if role == _DISPLAY:
            if col == 0:
                return e.name
            if col == 1:
                return '' if e.is_dir else self._locale.formattedDataSize(e.size)
            if col == 2:
                return self._type_name(e)
            if col == 3:
                dt = QDateTime.fromMSecsSinceEpoch(int(e.mtime * 1000))
                if self.date_formatter is not None:
                    text = self.date_formatter(dt)
                    if text is not None:
                        return text
                return self._locale.toString(dt, QLocale.FormatType.ShortFormat)
            return None
        if role == _EDIT and col == 0:
            return e.name
        if role == _DECORATION and col == 0 and self._icons is not None:
            if hasattr(self._icons, 'icon_for_name'):
                return self._icons.icon_for_name(e.name, e.is_dir)
            return self._icons.icon(QFileInfo(os.path.join(self._root, e.name)))
        if role == _ALIGN and col == 1:
            return _ALIGN_SIZE
        return None

    def mimeTypes(self):
        return ['text/uri-list']

    def mimeData(self, indexes):
        data = QMimeData()
        rows = sorted({i.row() for i in indexes if i.isValid()})
        data.setUrls([QUrl.fromLocalFile(os.path.join(self._root, self._visible[r].name)) for r in rows])
        return data

    def supportedDragActions(self):
        return Qt.DropAction.CopyAction | Qt.DropAction.MoveAction | Qt.DropAction.LinkAction

    def sort(self, column, order=Qt.SortOrder.AscendingOrder) -> None:
        column = column if 0 <= column < 4 else 0
        # QTableView.sortByColumn() sorts, then the header's indicator signal
        # asks for the same sort again; the second request is a no-op.
        if (column, order) == (self._sort_column, self._sort_order) and self._sorted_once:
            return
        self._sort_column = column
        self._sort_order = order
        self._sorted_once = True
        self._relayout()

    # -------------------------------------------------------------- listing
    def _start(self, refresh: bool) -> None:
        self._generation += 1
        if self._worker is not None:
            self._worker.cancel()
        self._loading = True
        self._refreshing = refresh
        self._pending = {}
        self._incoming = []
        self._finish_after_ingest = None
        self._ingest_timer.stop()
        worker = ListingWorker(self._generation, self._root, self.scanner)
        worker.signals.batch.connect(self._on_batch)
        worker.signals.finished.connect(self._on_finished)
        self._worker = worker
        self.listingStarted.emit(self._root)
        self.pool().start(worker)

    def _on_batch(self, generation, batch) -> None:
        if generation != self._generation:
            return
        if self._refreshing:
            for e in batch:
                self._pending[e.name] = e
            return
        # Ingest from a zero-delay timer in bounded slices, so paint and input
        # events run between slices even when the worker outpaces the GUI.
        self._incoming.extend(batch)
        if not self._ingest_timer.isActive():
            self._ingest_timer.start()

    def _ingest(self) -> None:
        if not self._incoming:
            return
        take = self._incoming[:INGEST_ENTRIES]
        del self._incoming[:INGEST_ENTRIES]
        entries = self._entries
        for e in take:
            entries[e.name] = e
        if self._by_name is not None:
            take.sort(key=attrgetter('nat'))
            self._by_name.extend(take)
            self._by_name.sort(key=attrgetter('nat'))  # two sorted runs: linear merge
            if len(self._by_name) != len(entries):  # duplicate names (refresh races)
                self._by_name = None
        self._relayout()
        self.listingProgress.emit(self._root, len(entries))
        if self._incoming:
            self._ingest_timer.start()
        elif self._finish_after_ingest is not None:
            done, self._finish_after_ingest = self._finish_after_ingest, None
            self._on_finished(*done)

    def _on_finished(self, generation, kind, message) -> None:
        if generation != self._generation:
            return
        if self._incoming and not kind:
            self._finish_after_ingest = (generation, kind, message)
            return
        self._incoming = []
        self._worker = None
        self._loading = False
        if kind == 'cancelled':
            return
        if kind:
            self._error = (kind, message)
            self._refreshing = False
            self._pending = {}
            if self._entries:
                self.beginResetModel()
                self._by_name = None
                self._entries = {}
                self._visible = []
                self._row_of = None
                self.endResetModel()
            self.listingFailed.emit(self._root, kind, message)
            return
        self._error = ('', '')
        if self._refreshing:
            self._apply_refresh(self._pending)
            self._pending = {}
            self._refreshing = False
        self.directoryLoaded.emit(self._root)
        if self._refresh_pending:
            self._refresh_pending = False
            self.refresh()

    def _apply_refresh(self, fresh) -> None:
        old = self._entries
        changed_rows = []
        structural = old.keys() != fresh.keys()
        if not structural:
            for name, e in fresh.items():
                prev = old[name]
                if not prev.same_metadata(e):
                    if prev.is_dir != e.is_dir:
                        structural = True
                        break
                    changed_rows.append(name)
        if structural:
            self._entries = fresh
            self._by_name = None
            self._relayout()
            return
        for name in changed_rows:
            prev = old[name]
            e = fresh[name]
            prev.size, prev.mtime = e.size, e.mtime
        if changed_rows and self._sort_column in (1, 3):
            self._relayout()
            return
        for name in changed_rows:
            idx = self.index_for_name(name)
            if idx.isValid():
                self.dataChanged.emit(idx, self.createIndex(idx.row(), 3))

    def _watched_change(self, path) -> None:
        if os.path.normpath(path) == self._root:
            self.refresh_soon()

    def refresh_soon(self) -> None:
        # Debounced re-list: bursts of changes, and the app's own local watcher
        # reporting the same change, collapse into one listing.
        if self._root:
            self._watch_timer.start()

    # ------------------------------------------------------- sort + filter
    def _name_order(self):
        # All entries in natural name order, cached until the entry set
        # changes. The other columns are stable sorts of this list on plain
        # int/float/str keys, so ties stay in name order and no per-element
        # tuple is built during a sort.
        if self._by_name is None:
            self._by_name = sorted(self._entries.values(), key=attrgetter('nat'))
        return self._by_name

    def _ordered(self):
        show_hidden = bool(self._filter_flags & QDir.Filter.Hidden)
        needle = self._needle
        dirs = []
        files = []
        add_dir = dirs.append
        add_file = files.append
        for e in self._name_order():
            if e.hidden and not show_hidden:
                continue
            if needle and needle not in e.fold:
                continue
            (add_dir if e.is_dir else add_file)(e)
        rev = self._sort_order == Qt.SortOrder.DescendingOrder
        col = self._sort_column
        if col == 1:
            files.sort(key=attrgetter('size'), reverse=rev)
        elif col == 2:
            files.sort(key=attrgetter('suffix'), reverse=rev)
        elif col == 3:
            dirs.sort(key=attrgetter('mtime'), reverse=rev)
            files.sort(key=attrgetter('mtime'), reverse=rev)
        elif rev:
            dirs.reverse()
            files.reverse()
        # Folders stay first in both directions.
        return dirs + files

    def _relayout(self) -> None:
        new = self._ordered()
        old = self._visible
        persistent = self.persistentIndexList()
        if not persistent and not old:
            if new:
                self.beginInsertRows(QModelIndex(), 0, len(new) - 1)
                self._visible = new
                self._row_of = None
                self.endInsertRows()
            return
        self.layoutAboutToBeChanged.emit()
        persistent = self.persistentIndexList()
        names = [old[i.row()].name if 0 <= i.row() < len(old) else None for i in persistent]
        self._visible = new
        self._row_of = None
        if persistent:
            # One pass over the new order for just the names that need a row
            # (selection/current item), instead of a full name->row table.
            wanted = {n for n in names if n is not None}
            found = {}
            if wanted:
                for row, e in enumerate(new):
                    if e.name in wanted:
                        found[e.name] = row
                        if len(found) == len(wanted):
                            break
            targets = [self.createIndex(found[name], idx.column()) if name in found else QModelIndex()
                       for idx, name in zip(persistent, names)]
            self.changePersistentIndexList(persistent, targets)
        self.layoutChanged.emit()
