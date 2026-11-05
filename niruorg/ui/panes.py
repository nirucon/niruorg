"""File panes: the list view, tabs, breadcrumbs, empty/error states and sidebar lists."""

import json
import mimetypes
import os
import re
import socket
import time
from pathlib import Path
from .base import (
    DirectoryModel,
    QAbstractItemView,
    QApplication,
    QBrush,
    QColor,
    QDir,
    QDrag,
    QEvent,
    QFileIconProvider,
    QHBoxLayout,
    QHeaderView,
    QIcon,
    QIdentityProxyModel,
    QItemSelectionModel,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMimeData,
    QModelIndex,
    QPainter,
    QPen,
    QPixmap,
    QPointF,
    QPolygonF,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QTabBar,
    QTableView,
    QTimer,
    QToolButton,
    QUrl,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)  # noqa: F401


class SemanticIconProvider(QFileIconProvider):
    def __init__(self, pal):
        super().__init__()
        self.pal = pal
        self._cache = {}

    def set_palette(self, pal):
        if pal != self.pal:
            self.pal = pal
            self._cache.clear()

    def _icon(self, kind):
        if kind in self._cache:
            return self._cache[kind]
        pm = QPixmap(32, 32)
        pm.fill(Qt.GlobalColor.transparent)
        q = QPainter(pm)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        fg = QColor(self.pal.get('muted', '#888'))
        ac = QColor(self.pal.get('accent', '#bbb'))
        bg = QColor(self.pal.get('surface', '#222'))
        pen = QPen(ac if kind in ('folder', 'drive') else fg, 1.7)
        q.setPen(pen)
        q.setBrush(QBrush(bg))
        if kind == 'folder':
            q.drawRoundedRect(4, 10, 24, 16, 2, 2)
            q.drawRoundedRect(6, 7, 10, 6, 2, 2)
        elif kind == 'drive':
            q.drawRoundedRect(5, 8, 22, 17, 3, 3)
            q.drawLine(8, 20, 24, 20)
            q.setBrush(QBrush(ac))
            q.drawEllipse(21, 22, 2, 2)
        elif kind == 'image':
            q.drawRoundedRect(6, 5, 20, 22, 2, 2)
            q.drawEllipse(10, 9, 4, 4)
            q.drawLine(8, 23, 14, 17)
            q.drawLine(14, 17, 18, 21)
            q.drawLine(18, 21, 24, 15)
        elif kind == 'media':
            q.drawRoundedRect(6, 5, 20, 22, 2, 2)
            q.setBrush(QBrush(ac))
            q.drawPolygon(QPolygonF([QPointF(13, 11), QPointF(13, 21), QPointF(21, 16)]))
        elif kind == 'archive':
            q.drawRoundedRect(7, 5, 18, 22, 2, 2)
            q.drawLine(16, 6, 16, 21)
            q.drawLine(13, 10, 16, 10)
            q.drawLine(16, 14, 19, 14)
            q.drawLine(13, 18, 16, 18)
        else:
            q.drawRoundedRect(7, 4, 18, 24, 2, 2)
            q.drawLine(11, 11, 21, 11)
            q.drawLine(11, 16, 21, 16)
            q.drawLine(11, 21, 18, 21)
        q.end()
        icon = QIcon(pm)
        self._cache[kind] = icon
        return icon

    def icon_for_name(self, name, is_dir):
        # DirectoryModel path: no QFileInfo, no filesystem access, one lookup per suffix.
        if is_dir:
            return self._icon('folder')
        low = name.lower()
        dot = low.rfind('.')
        key = low[dot:] if dot > 0 else ''
        kind = self._kinds.get(key) if hasattr(self, '_kinds') else None
        if kind is None:
            if not hasattr(self, '_kinds'):
                self._kinds = {}
            mime = mimetypes.guess_type('x' + key)[0] or '' if key else ''
            kind = (
                'image'
                if mime.startswith('image/')
                else 'media'
                if (mime.startswith('audio/') or mime.startswith('video/'))
                else 'file'
            )
            self._kinds[key] = kind
        if kind == 'file' and low.endswith(('.zip', '.7z', '.rar', '.tar', '.gz', '.xz', '.zst', '.bz2')):
            kind = 'archive'
        return self._icon(kind)

    def icon(self, arg):
        try:
            if hasattr(arg, 'isDir') and arg.isDir():
                return self._icon('folder')
            name = arg.fileName().lower() if hasattr(arg, 'fileName') else ''
            mime = mimetypes.guess_type(name)[0] or ''
            if mime.startswith('image/'):
                return self._icon('image')
            if mime.startswith('audio/') or mime.startswith('video/'):
                return self._icon('media')
            if name.endswith(('.zip', '.7z', '.rar', '.tar', '.gz', '.xz', '.zst', '.bz2')):
                return self._icon('archive')
        except Exception:
            pass
        return self._icon('file')


class Filter(QIdentityProxyModel):
    # Sorting and the name filter run inside DirectoryModel on precomputed keys.
    # A QSortFilterProxyModel called back into Python for every comparison and
    # row, which blocked the UI for about a second per sort on 100 000 entries.
    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        m = self.sourceModel()
        if m is not None:
            m.sort(column, order)

    def setFilterCaseSensitivity(self, _sensitivity):
        pass

    def setFilterRegularExpression(self, rx):
        m = self.sourceModel()
        pat = rx.pattern() if hasattr(rx, 'pattern') else str(rx or '')
        # Compatibility: callers pass an escaped literal; DirectoryModel matches substrings.
        if m is not None:
            m.set_name_filter(re.sub(r'\\(.)', r'\1', pat))

    def invalidate(self):
        m = self.sourceModel()
        if m is not None and m.rowCount():
            m.dataChanged.emit(m.index(0, 0), m.index(m.rowCount() - 1, m.columnCount() - 1))


class RowHoverDelegate(QStyledItemDelegate):
    # QTreeView highlights the whole hovered row and draws no per-cell focus
    # frame; keep that look on the table-based file list.
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        view = self.parent()
        if index.row() == getattr(view, '_hover_row', -1):
            option.state |= QStyle.StateFlag.State_MouseOver
        else:
            option.state &= ~QStyle.StateFlag.State_MouseOver
        option.state &= ~QStyle.StateFlag.State_HasFocus


class BrowserTree(QTableView):
    # 0.6.0: a QTableView styled like the former QTreeView. QTreeView re-laid
    # out every row (one Python model call each) after each sort, filter step or
    # listing batch: ~600 ms per step with 100 000 entries. QTableView only
    # touches the visible rows. The QTreeView-only setters below are kept as
    # no-ops so pane configuration and gallery code stay unchanged.
    MIME = 'application/x-niruorg-files'

    def __init__(self, pane):
        super().__init__(pane)
        self.pane = pane
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setDropIndicatorShown(True)
        self._hover_row = -1
        self.setMouseTracking(True)
        self.setItemDelegate(RowHoverDelegate(self))
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setCornerButtonEnabled(False)
        self.setTabKeyNavigation(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.verticalHeader().hide()
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.horizontalHeader().setSortIndicatorShown(True)
        # Fit Size/Type/Date to the rows on screen, not 1 000 sampled rows per batch/sort.
        self.horizontalHeader().setResizeContentsPrecision(0)

    def header(self):
        return self.horizontalHeader()

    def setRootIsDecorated(self, _on):
        pass

    def setIndentation(self, _px):
        pass

    def setUniformRowHeights(self, _on):
        pass

    def setAnimated(self, _on):
        pass

    def set_row_height(self, px):
        self.verticalHeader().setDefaultSectionSize(max(12, int(px)))
        self.verticalHeader().setMinimumSectionSize(max(12, int(px)))

    def moveCursor(self, action, modifiers):
        # Tree semantics on a table: Left/Right do not walk across columns, and
        # Home/End jump to the first/last row; the current column stays the name.
        cur = self.currentIndex()
        m = self.model()
        rows = m.rowCount(self.rootIndex()) if m is not None else 0
        A = QAbstractItemView.CursorAction
        if action in (A.MoveLeft, A.MoveRight):
            return cur.siblingAtColumn(0) if cur.isValid() else cur
        if action == A.MoveHome and rows:
            return m.index(0, 0, self.rootIndex())
        if action == A.MoveEnd and rows:
            return m.index(rows - 1, 0, self.rootIndex())
        idx = super().moveCursor(action, modifiers)
        return idx.siblingAtColumn(0) if idx.isValid() else idx

    def mouseMoveEvent(self, event):
        row = self.rowAt(int(event.position().y()))
        if row != self._hover_row:
            old = self._hover_row
            self._hover_row = row
            self._update_row(old)
            self._update_row(row)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        old = self._hover_row
        self._hover_row = -1
        self._update_row(old)
        super().leaveEvent(event)

    def _update_row(self, row):
        if row < 0 or self.model() is None:
            return
        r = self.visualRect(self.model().index(row, 0, self.rootIndex()))
        if r.isValid():
            self.viewport().update(0, r.top(), self.viewport().width(), r.height())

    def keyboardSearch(self, text):
        # U3 type-ahead: typing jumps to the next name starting with the typed
        # text (case-insensitive). Keys typed within the keyboard input interval
        # extend the search; repeating one letter cycles through its matches.
        # Searches the model's name list directly: no per-row model calls.
        if not text or not text.isprintable():
            return
        now = time.monotonic()
        interval = QApplication.keyboardInputInterval() / 1000.0
        buf = getattr(self, '_ta_text', '') if now - getattr(self, '_ta_time', 0.0) <= interval else ''
        self._ta_time = now
        buf += text
        if len(buf) > 1 and buf == buf[0] * len(buf):
            buf = buf[0]
        self._ta_text = buf
        m = self.pane.model
        entries = m.visible_entries()
        n = len(entries)
        if not n:
            return
        cur = self.currentIndex().row() if self.currentIndex().isValid() else -1
        needle = buf.casefold()
        start = cur + 1 if len(buf) == 1 else max(cur, 0)
        for k in range(n):
            row = (start + k) % n
            if entries[row].fold.startswith(needle):
                idx = self.model().index(row, 0, self.rootIndex())
                self.selectionModel().setCurrentIndex(
                    idx,
                    QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
                )
                self.scrollTo(idx)
                return

    def startDrag(self, supported):
        # QFileSystemModel's platform drag implementation is not reliable for FUSE
        # paths on Wayland. Publish explicit file URLs plus NIRUORG pane identity.
        paths = self.pane.selected()
        if not paths:
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
        side = 'left' if self.pane is self.pane.owner.pane1 else 'right'
        mime.setData(
            self.MIME, json.dumps({'source': side, 'paths': [str(p) for p in paths]}).encode('utf-8')
        )
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction, Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasFormat(self.MIME):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasFormat(self.MIME):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def _drop_target(self, event):
        # Dropping on a directory copies into it; dropping on empty space or a file
        # copies into the pane's current directory. QFileSystemModel is queried only
        # for the already-visible index, avoiding extra remote filesystem probes.
        try:
            idx = self.indexAt(event.position().toPoint())
            if idx.isValid():
                src = self.pane.proxy.mapToSource(idx)
                if self.pane.model.isDir(src):
                    return Path(self.pane.model.filePath(src))
        except Exception:
            pass
        return self.pane.current

    def dropEvent(self, event):
        mime = event.mimeData()
        source = None
        paths = []
        if mime.hasFormat(self.MIME):
            try:
                payload = json.loads(bytes(mime.data(self.MIME)).decode('utf-8'))
                side = payload.get('source')
                source = (
                    self.pane.owner.pane1
                    if side == 'left'
                    else self.pane.owner.pane2
                    if side == 'right'
                    else None
                )
                paths = [Path(x) for x in payload.get('paths', []) if x]
            except Exception:
                paths = []
        if not paths and mime.hasUrls():
            paths = [Path(u.toLocalFile()) for u in mime.urls() if u.isLocalFile()]
        if paths and source is not self.pane:
            # Finish the native Wayland drag transaction before opening any dialog or
            # starting transfer UI. A nested modal dialog from inside dropEvent can keep
            # the compositor's drag grab active, making the dialog appear but not accept
            # mouse/keyboard input. Snapshot everything now and defer NIRUORG handling.
            owner = self.pane.owner
            dst = self.pane
            items = list(paths)
            source_pane = source
            target = self._drop_target(event)
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            QTimer.singleShot(
                0,
                lambda o=owner, d=dst, x=items, sp=source_pane, t=target: o.handle_pane_drop(
                    d, x, Qt.DropAction.CopyAction, sp, t
                ),
            )
            return
        super().dropEvent(event)

    def focusInEvent(self, event):
        self.pane.owner.set_active(self.pane)
        super().focusInEvent(event)

    def keyPressEvent(self, event):
        # File-browser keys are handled at the widget that actually receives them.
        # This avoids QAction/QShortcut ambiguity and behaves the same on Wayland/X11.
        owner = self.pane.owner
        action = owner._dispatch_browser_key(event.key(), event.modifiers(), self.pane, execute=False)
        if action:
            event.accept()
            owner._trigger_browser_action(action, self.pane)
            return
        super().keyPressEvent(event)


class PaneTabBar(QTabBar):
    MIME = 'application/x-niruorg-pane-tab'

    def __init__(self, pane):
        super().__init__(pane)
        self.pane = pane
        self._drag_start = None
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.tabMoved.connect(self._moved)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def mousePressEvent(self, e):
        self.pane.owner.set_active(self.pane)
        if e.button() == Qt.MouseButton.MiddleButton:
            i = self.tabAt(e.position().toPoint())
            if i >= 0:
                self.pane.close_tab(i)
            e.accept()
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_start = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.tabAt(e.position().toPoint()) < 0:
            self.pane.new_tab()
            e.accept()
            return
        super().mouseDoubleClickEvent(e)

    def mouseMoveEvent(self, e):
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if e.button() != Qt.MouseButton.LeftButton:
            return
        other = self.pane.owner.pane2 if self.pane is self.pane.owner.pane1 else self.pane.owner.pane1
        if not other.isVisible():
            return
        gp = e.globalPosition().toPoint()
        lp = other.tabs.mapFromGlobal(gp)
        if other.tabs.rect().contains(lp):
            i = self.currentIndex()
            if i >= 0:
                self.pane.copy_tab_to_other(i, True)

    def _moved(self, frm, to):
        if getattr(self.pane, '_tab_loading', False) or frm == to:
            return
        if 0 <= frm < len(self.pane._tab_states) and 0 <= to < len(self.pane._tab_states):
            st = self.pane._tab_states.pop(frm)
            self.pane._tab_states.insert(to, st)
            self.pane._sync_tab()

    def _menu(self, pos):
        i = self.tabAt(pos)
        m = QMenu(self)
        if i < 0:
            m.addAction('New tab', lambda: self.pane.new_tab())
            a = m.addAction('Reopen closed tab', self.pane.reopen_closed_tab)
            a.setEnabled(bool(self.pane._closed_tabs))
            m.addSeparator()
            m.addAction('Close other tabs', lambda: self.pane.close_other_tabs(self.pane.tabs.currentIndex()))
            m.addAction('Close all tabs', self.pane.close_all_tabs)
        else:
            self.setCurrentIndex(i)
            self.pane.owner.set_active(self.pane)
            m.addAction('New tab', lambda: self.pane.new_tab())
            m.addAction('Duplicate tab', lambda: self.pane.duplicate_tab(i))
            m.addSeparator()
            m.addAction('Open in other pane', lambda: self.pane.copy_tab_to_other(i, False))
            m.addAction('Move tab to other pane', lambda: self.pane.copy_tab_to_other(i, True))
            m.addSeparator()
            pinned = bool(self.pane._tab_states[i].get('pinned')) if i < len(self.pane._tab_states) else False
            m.addAction('Unpin tab' if pinned else 'Pin tab', lambda: self.pane.toggle_pin(i))
            m.addSeparator()
            m.addAction('Close tab', lambda: self.pane.close_tab(i))
            m.addAction('Close other tabs', lambda: self.pane.close_other_tabs(i))
            m.addAction('Close tabs to the right', lambda: self.pane.close_tabs_right(i))
        m.exec(self.mapToGlobal(pos))


class PaneState(QWidget):
    # U4: a message with one action, drawn over the file list's viewport
    # instead of an empty list. Clicks and drops outside the button reach the
    # list underneath (context menu, drop into an empty folder).
    def __init__(self, view):
        super().__init__(view.viewport())
        self.view = view
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setObjectName('paneState')
        self.kind = ''
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(8)
        lay.addStretch(1)
        self.title = QLabel()
        self.title.setObjectName('paneStateTitle')
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setWordWrap(True)
        self.detail = QLabel()
        self.detail.setObjectName('muted')
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail.setWordWrap(True)
        self.action = QPushButton()
        self.action.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fn = None
        self.action.clicked.connect(lambda: self._fn and self._fn())
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.action)
        row.addStretch(1)
        for x in (self.title, self.detail):
            x.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            lay.addWidget(x)
        lay.addLayout(row)
        lay.addStretch(2)
        self.hide()
        view.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.view.viewport() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.view.viewport().rect())
        return False

    def mousePressEvent(self, event):
        event.ignore()

    def show_state(self, kind, title, detail, label, fn):
        self.kind = kind
        self.title.setText(title)
        self.detail.setText(detail)
        self.detail.setVisible(bool(detail))
        self.action.setText(label)
        self.action.setVisible(bool(label))
        self._fn = fn
        self.setGeometry(self.view.viewport().rect())
        self.show()
        self.raise_()

    def clear(self):
        self.kind = ''
        self._fn = None
        self.hide()


class CrumbBar(QWidget):
    # Clicking the empty part of the path bar edits the location (as Ctrl+L).
    # A resize that changes how many trailing segments fit rebuilds the bar.
    def __init__(self, pane):
        super().__init__(pane)
        self.pane = pane
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setToolTip('Click to type a location (Ctrl+L)')
        # Do not let full-width segments dictate the pane's minimum width (split
        # view); fewer trailing segments are shown instead when space is short.
        self.setMinimumWidth(80)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            self.pane.edit_location()
            return
        super().mousePressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.pane._crumb_fit_changed():
            QTimer.singleShot(0, self.pane.update_breadcrumbs)


class FilePane(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setObjectName('filePane')
        self.setProperty('activePane', False)
        self.current = Path.home()
        self.remote_name = None
        self.remote_protocol = None
        self.remote_mount = None
        self.remote_root = None
        self.model = DirectoryModel(self)
        self.model.date_formatter = self._format_date
        self.icons = SemanticIconProvider(owner.palette())
        self.model.setIconProvider(self.icons)
        self.model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs)
        self.proxy = Filter(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.view = BrowserTree(self)
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setUniformRowHeights(True)
        self.view.setAnimated(False)
        self.view.setIndentation(14)
        self.view.setRootIsDecorated(False)
        self.view.header().setStretchLastSection(False)
        self.view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.view.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.view.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.view.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.view.setDragEnabled(True)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(lambda p: owner.context_menu(self, p))
        self.view.doubleClicked.connect(self.activate)
        self.view.clicked.connect(lambda *_: owner.set_active(self))
        self.view.selectionModel().selectionChanged.connect(
            lambda *_: (owner.update_status(), owner.update_quicklook())
        )
        self.path = QLineEdit()
        self.path.returnPressed.connect(self.commit_location)
        self.path.hide()
        self.crumb = CrumbBar(self)
        self._crumb_keep = None
        self.crumb_lay = QHBoxLayout(self.crumb)
        self.crumb_lay.setContentsMargins(0, 0, 0, 0)
        self.crumb_lay.setSpacing(1)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText('Filter')
        self.filter.setMaximumWidth(160)
        self.filter.textChanged.connect(self.set_filter)
        self.backb = QToolButton()
        self.backb.setText('‹')
        self.backb.setToolTip('Back')
        self.backb.clicked.connect(self.back)
        self.upb = QToolButton()
        self.upb.setText('↑')
        self.upb.setToolTip('Parent folder')
        self.upb.clicked.connect(self.up)
        self.close_split = QToolButton()
        self.close_split.setText('×')
        self.close_split.setToolTip('Close split view (Ctrl+2)')
        self.close_split.clicked.connect(lambda: owner.close_split(self))
        self.close_split.hide()
        self.tabs = PaneTabBar(self)
        self.tabs.setObjectName('paneTabs')
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(False)
        self.tabs.setExpanding(False)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.setUsesScrollButtons(True)
        self._tab_loading = False
        self._tab_states = []
        self._closed_tabs = []
        self.tabs.currentChanged.connect(self._switch_tab)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.tabBarClicked.connect(lambda *_: self.owner.set_active(self))
        self.tabs.addTab('Home')
        self._tab_states.append({})
        self.tabs.setTabToolTip(0, str(Path.home()))
        self._install_tab_close(0)
        self.location_stack = QStackedWidget()
        self.location_stack.addWidget(self.crumb)
        self.location_stack.addWidget(self.path)
        top = QHBoxLayout()
        top.setContentsMargins(10, 8, 10, 7)
        top.addWidget(self.backb)
        top.addWidget(self.upb)
        top.addWidget(self.location_stack, 1)
        top.addWidget(self.filter)
        top.addWidget(self.close_split)
        self.history = []
        self.hist = -1
        for w in (self.path, self.filter, self.backb, self.upb, self.location_stack):
            w.installEventFilter(self)
        # U1: non-modal activity row for slow listings and connects, with Cancel.
        self.activity = QWidget()
        self.activity.setObjectName('paneActivity')
        al = QHBoxLayout(self.activity)
        al.setContentsMargins(12, 5, 8, 5)
        al.setSpacing(10)
        self.activity_label = QLabel()
        self.activity_label.setObjectName('muted')
        self.activity_cancel = QToolButton()
        self.activity_cancel.setText('Cancel')
        self.activity_cancel.clicked.connect(self._cancel_activity)
        al.addWidget(self.activity_label, 1)
        al.addWidget(self.activity_cancel)
        self.activity.hide()
        self._activity_cancel_fn = None
        self._activity_token = 0
        self._activity_timer = QTimer(self)
        self._activity_timer.setSingleShot(True)
        self._activity_timer.timeout.connect(self.activity.show)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.tabs)
        lay.addLayout(top)
        lay.addWidget(self.view, 1)
        lay.addWidget(self.activity)
        self.model.listingStarted.connect(self._listing_started)
        self.model.listingProgress.connect(self._listing_progress)
        for sig in (self.model.directoryLoaded, self.model.listingFailed, self.model.listingCancelled):
            sig.connect(self._listing_ended)
        self.state = PaneState(self.view)
        self.model.listingFailed.connect(self._listing_failed)
        # The listing is asynchronous: keep the status bar count, size and
        # selection summary in step with every batch, completion and filter change.
        for sig in (
            self.proxy.rowsInserted,
            self.proxy.rowsRemoved,
            self.proxy.modelReset,
            self.proxy.layoutChanged,
        ):
            sig.connect(self._listing_changed)
        self.model.directoryLoaded.connect(self._listing_changed)

    def _format_date(self, dt):
        fmt = getattr(self.owner, 'date_format', 'Swedish')
        if fmt == 'Swedish':
            return dt.toString('yyyy-MM-dd HH:mm')
        if fmt == 'ISO':
            return dt.toString('yyyy-MM-ddTHH:mm:ss')
        if fmt == 'Compact':
            return dt.toString('yy-MM-dd HH:mm')
        return None

    def show_activity(self, text, cancel_fn, delay_ms=300):
        # Shown only if the work is still running after delay_ms, so fast folders
        # and connects never flash a bar. Returns a token for hide_activity().
        self._activity_token += 1
        self._activity_cancel_fn = cancel_fn
        self.activity_label.setText(text)
        self.activity_cancel.setEnabled(cancel_fn is not None)
        if delay_ms <= 0:
            self._activity_timer.stop()
            self.activity.show()
        elif not self.activity.isVisible():
            self._activity_timer.start(delay_ms)
        return self._activity_token

    def update_activity(self, text, token=None):
        if token is None or token == self._activity_token:
            self.activity_label.setText(text)

    def hide_activity(self, token=None):
        if token is not None and token != self._activity_token:
            return
        self._activity_timer.stop()
        self.activity.hide()
        self._activity_cancel_fn = None

    def _cancel_activity(self):
        fn = self._activity_cancel_fn
        self.hide_activity()
        if fn:
            fn()

    @staticmethod
    def _count_text(n):
        return f'{n:,}'.replace(',', ' ')

    def _listing_started(self, path, refresh):
        if refresh:
            return
        if self.state.kind:
            self.state.clear()
        self._listing_token = self.show_activity('Listing…', self._cancel_listing)

    def _listing_progress(self, path, count):
        self.update_activity(
            f'Listing… {self._count_text(count)} items', getattr(self, '_listing_token', None)
        )

    def _listing_ended(self, *_):
        self.hide_activity(getattr(self, '_listing_token', None))

    def _cancel_listing(self):
        self.model.cancel()
        self.owner.update_status()

    def _listing_changed(self, *_):
        if self.owner.active is self:
            self.owner.schedule_status()
        self._update_state()

    def _update_state(self):
        # Empty-folder states are decided once the listing is complete; error and
        # connection states are set by their own handlers and kept until the next
        # navigation.
        if self.model.is_loading() or self.state.kind in (
            'permission',
            'missing',
            'io',
            'disconnected',
            'unreachable',
        ):
            return
        if not self.model.rootPath():
            return
        rows = self.proxy.rowCount()
        total = self.model.loaded_count()
        if rows:
            if self.state.kind:
                self.state.clear()
            return
        if self.model.is_partial():
            self.state.clear()
            return
        needle = self.filter.text().strip()
        if needle and total:
            self.state.show_state(
                'nomatch', f'No names match “{needle}”', '', 'Clear filter', self.filter.clear
            )
        elif total:
            self.state.show_state(
                'hidden',
                'Only hidden items',
                f'{total} hidden item(s) in this folder.',
                'Show hidden files',
                self.owner.toggle_hidden,
            )
        else:
            self.state.show_state(
                'empty',
                'This folder is empty',
                'Drop files here, or create something new.',
                'Open terminal here',
                self._terminal_here,
            )

    def _terminal_here(self):
        self.owner.set_active(self)
        self.view.clearSelection()
        self.owner.terminal_here()

    def _retry(self):
        self.state.clear()
        if self.is_remote():
            self.owner.navigate_remote_async(self, self.current, False)
        else:
            self.model.setRootPath('')
            self._apply_root(self.current)

    def _reconnect(self):
        self.state.clear()
        name = self.remote_name
        if self.remote_protocol == 'CLOUD':
            self.owner.open_cloud(name, self)
        else:
            self.owner.manage_servers(name, 'connect', self)

    def _listing_failed(self, path, kind, message):
        where = self.display_path()
        if self.is_remote() and kind == 'io':
            # ENOTCONN/EIO on a FUSE mount: the connection dropped.
            self.show_connection_state('disconnected', message)
            return
        if kind == 'permission':
            self.state.show_state(
                'permission', 'No permission to open this folder', f'{where}\n{message}', 'Retry', self._retry
            )
        elif kind == 'missing':
            self.state.show_state(
                'missing', 'This folder is not available', f'{where}\n{message}', 'Retry', self._retry
            )
        else:
            self.state.show_state(
                'io', 'Could not read this folder', f'{where}\n{message}', 'Retry', self._retry
            )

    def show_connection_state(self, kind, detail=''):
        name = self.remote_name or 'Remote'
        if kind == 'disconnected':
            self.state.show_state(
                'disconnected',
                f'{name} is disconnected',
                detail or 'The connection is not mounted.',
                'Reconnect',
                self._reconnect,
            )
        else:
            self.state.show_state(
                'unreachable',
                f'{name} is not responding',
                detail or 'The server did not answer in time.',
                'Retry',
                self._retry,
            )

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress):
            self.owner.set_active(self)
        if obj is self.path and self.location_stack.currentWidget() is self.path:
            # The typed location is a temporary editor: Escape or leaving it restores
            # the breadcrumbs without navigating.
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self.cancel_location()
                self.view.setFocus()
                return True
            if event.type() == QEvent.Type.FocusOut and event.reason() != Qt.FocusReason.PopupFocusReason:
                QTimer.singleShot(0, self.cancel_location)
        return super().eventFilter(obj, event)

    def _tab_state(self):
        return {
            'path': str(self.current),
            'remote_name': self.remote_name,
            'remote_protocol': self.remote_protocol,
            'remote_mount': str(self.remote_mount) if self.remote_mount else '',
            'remote_root': self.remote_root or '/',
            'history': list(self.history),
            'hist': self.hist,
            'filter': self.filter.text(),
            'pinned': bool(self._tab_states[self.tabs.currentIndex()].get('pinned'))
            if 0 <= self.tabs.currentIndex() < len(self._tab_states)
            else False,
        }

    def _tab_title(self):
        current = self.current
        if os.path.normpath(str(current)) == os.path.normpath(str(Path.home())):
            leaf = 'Home'
        elif str(current) == '/':
            leaf = '/'
        else:
            leaf = current.name or str(current)
        return f'{self.remote_name} · {leaf}' if self.is_remote() else leaf

    def _install_tab_close(self, i):
        if i < 0 or i >= self.tabs.count():
            return
        btn = QToolButton(self.tabs)
        btn.setObjectName('paneTabClose')
        btn.setText('×')
        btn.setAutoRaise(True)
        btn.setFixedSize(18, 18)
        btn.setToolTip('Close tab (Ctrl+W)')
        btn.clicked.connect(lambda _=False, b=btn: self.close_tab(self.tabs.tabAt(b.pos())))
        self.tabs.setTabButton(i, QTabBar.ButtonPosition.RightSide, btn)

    def _sync_tab(self):
        if self._tab_loading or self.tabs.count() == 0:
            return
        i = self.tabs.currentIndex()
        if i < 0:
            return
        while len(self._tab_states) < self.tabs.count():
            self._tab_states.append({})
        self._tab_states[i] = self._tab_state()
        title = self._tab_title()
        self.tabs.setTabText(i, ('◆ ' if self._tab_states[i].get('pinned') else '') + title)
        self.tabs.setTabToolTip(i, (self.remote_name + ':' if self.is_remote() else '') + self.display_path())

    def new_tab(self, path=None):
        self._sync_tab()
        state = self._tab_state()
        state['path'] = str(path or self.current)
        i = self.tabs.addTab('New tab')
        self._tab_states.append(state)
        self._install_tab_close(i)
        self.tabs.setCurrentIndex(i)
        self.owner.set_active(self)

    def _insert_tab_state(self, state, index=None, select=True):
        state = dict(state or {})
        index = self.tabs.count() if index is None else max(0, min(index, self.tabs.count()))
        self._tab_loading = True
        try:
            self._tab_states.insert(index, state)
            self.tabs.insertTab(index, 'Tab')
            self._install_tab_close(index)
        finally:
            self._tab_loading = False
        if select:
            self.tabs.setCurrentIndex(index)
            self._switch_tab(index)
        else:
            self._refresh_tab_labels()
        return index

    def _refresh_tab_labels(self):
        cur = self.tabs.currentIndex()
        for i, st in enumerate(self._tab_states):
            path = Path(st.get('path', str(Path.home())))
            leaf = 'Home' if path == Path.home() else ('/' if str(path) == '/' else (path.name or str(path)))
            title = f"{st.get('remote_name')} · {leaf}" if st.get('remote_name') else leaf
            if st.get('pinned'):
                title = '◆ ' + title
            self.tabs.setTabText(i, title)
            self.tabs.setTabToolTip(
                i,
                (str(st.get('remote_name')) + ':' if st.get('remote_name') else '') + str(st.get('path', '')),
            )
        if cur >= 0:
            self.tabs.setCurrentIndex(min(cur, self.tabs.count() - 1))

    def close_tab(self, i, force=False):
        if i < 0 or i >= self.tabs.count():
            return
        self._sync_tab()
        if self._tab_states[i].get('pinned') and not force:
            self.owner.status.setText('Pinned tab · unpin it before closing')
            return
        closed = dict(self._tab_states[i])
        closed['_origin_pane'] = self.owner.pane_side(self)
        self._closed_tabs.insert(0, dict(closed))
        self._closed_tabs = self._closed_tabs[:20]
        self.owner.closed_tabs_global.insert(0, dict(closed))
        self.owner.closed_tabs_global = self.owner.closed_tabs_global[:30]
        self._tab_loading = True
        try:
            self._tab_states.pop(i)
            self.tabs.removeTab(i)
            if self.tabs.count() == 0 and self is self.owner.pane1:
                self._tab_states.append(
                    {'path': str(Path.home()), 'history': [], 'hist': -1, 'pinned': False}
                )
                self.tabs.addTab('Home')
                self._install_tab_close(0)
        finally:
            self._tab_loading = False
        if self.tabs.count():
            self._switch_tab(max(0, self.tabs.currentIndex()))
        elif self is self.owner.pane2:
            self.owner._right_tabs_exhausted()

    def reopen_closed_tab(self):
        # Global history preserves the pane a tab came from. This makes Ctrl+Shift+T
        # restore a closed right pane instead of reopening its tab on the left.
        if self.owner.closed_tabs_global:
            st = dict(self.owner.closed_tabs_global.pop(0))
            origin = st.pop('_origin_pane', 'left')
            target = self.owner.pane2 if origin == 'right' else self.owner.pane1
            if target is self.owner.pane2:
                self.owner._show_right_pane(empty=True)
            target._insert_tab_state(st)
            self.owner.set_active(target)
            return
        if self._closed_tabs:
            st = dict(self._closed_tabs.pop(0))
            st.pop('_origin_pane', None)
            self._insert_tab_state(st)

    def duplicate_tab(self, i):
        self._sync_tab()
        if 0 <= i < len(self._tab_states):
            st = dict(self._tab_states[i])
            st['pinned'] = False
            self._insert_tab_state(st, i + 1)

    def toggle_pin(self, i):
        self._sync_tab()
        if 0 <= i < len(self._tab_states):
            self._tab_states[i]['pinned'] = not bool(self._tab_states[i].get('pinned'))
            self._refresh_tab_labels()

    def close_other_tabs(self, keep):
        self._sync_tab()
        for i in range(self.tabs.count() - 1, -1, -1):
            if i != keep and not self._tab_states[i].get('pinned'):
                self.close_tab(i, True)

    def close_tabs_right(self, i):
        self._sync_tab()
        for n in range(self.tabs.count() - 1, i, -1):
            if not self._tab_states[n].get('pinned'):
                self.close_tab(n, True)

    def close_all_tabs(self):
        self._sync_tab()
        for i in range(self.tabs.count() - 1, -1, -1):
            if not self._tab_states[i].get('pinned'):
                self.close_tab(i, True)

    def copy_tab_to_other(self, i, move=False):
        self._sync_tab()
        if not (0 <= i < len(self._tab_states)):
            return
        target = self.owner.other_pane(self, True)
        target._insert_tab_state(dict(self._tab_states[i]))
        self.owner.set_active(target)
        if move:
            self.close_tab(i, True)

    def next_tab(self, delta=1):
        if self.tabs.count() > 1:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + delta) % self.tabs.count())

    def export_tabs(self):
        self._sync_tab()
        return [dict(x) for x in self._tab_states]

    def restore_tabs(self, states):
        if states is None:
            return
        self._tab_loading = True
        try:
            while self.tabs.count():
                self.tabs.removeTab(0)
            self._tab_states = [dict(x) for x in states]
            for _ in states:
                i = self.tabs.addTab('Tab')
                self._install_tab_close(i)
            self.tabs.setCurrentIndex(0)
        finally:
            self._tab_loading = False
        self._switch_tab(0)

    def _switch_tab(self, i):
        if i < 0 or i >= len(self._tab_states):
            return
        if self._tab_loading:
            return
        st = self._tab_states[i]
        if not st:
            return
        self._tab_loading = True
        try:
            if st.get('remote_name'):
                self.bind_remote(
                    st['remote_name'],
                    st.get('remote_protocol', 'SFTP'),
                    st.get('remote_mount', ''),
                    st.get('remote_root', '/'),
                )
            else:
                self.clear_remote()
            self.history = list(st.get('history', []))
            self.hist = int(st.get('hist', -1))
            self.filter.setText(st.get('filter', ''))
            self.go(st.get('path', str(Path.home())), False, leave_remote=not bool(st.get('remote_name')))
            self.owner.set_active(self)
        finally:
            self._tab_loading = False
        self._sync_tab()

    def bind_remote(self, name, protocol, mount, remote_root='/'):
        self.remote_name = str(name)
        self.remote_protocol = str(protocol).upper()
        self.remote_mount = Path(os.path.abspath(os.path.expanduser(str(mount))))
        self.remote_root = str(remote_root or '/')

    def clear_remote(self):
        self.remote_name = None
        self.remote_protocol = None
        self.remote_mount = None
        self.remote_root = None

    def is_remote(self):
        return bool(self.remote_name and self.remote_mount)

    def endpoint_label(self):
        base = (
            f'REMOTE · {self.remote_name} · {self.remote_protocol}'
            if self.is_remote()
            else f'LOCAL · {socket.gethostname()}'
        )
        active = self.owner.active is self
        return ('● ' if active else '  ') + base

    def side_name(self):
        return 'left' if self is self.owner.pane1 else 'right'

    def _path_inside_remote(self, p):
        if not self.remote_mount:
            return False
        try:
            return p == self.remote_mount or self.remote_mount in p.parents
        except Exception:
            return False

    def display_path(self):
        if not self.is_remote() or not self._path_inside_remote(self.current):
            return str(self.current)
        try:
            rel = self.current.relative_to(self.remote_mount)
            logical = Path(self.remote_root or '/').joinpath(rel)
            return '/' + str(logical).lstrip('/')
        except Exception:
            return str(self.remote_root or '/')

    def edit_location(self):
        self.path.setText(str(self.current))
        self.location_stack.setCurrentWidget(self.path)
        self.path.setFocus()
        self.path.selectAll()

    def commit_location(self):
        value = self.path.text()
        self.location_stack.setCurrentWidget(self.crumb)
        self.go(value)

    def cancel_location(self):
        if self.location_stack.currentWidget() is self.path:
            self.path.setText(str(self.current))
            self.location_stack.setCurrentWidget(self.crumb)

    def _crumb_segments(self):
        # (label, target path or None, tooltip). Remote panes show the logical
        # remote path; only folders inside the mount are clickable.
        if self.is_remote():
            disp = self.display_path()
            root = str(self.remote_root or '/').rstrip('/') or '/'
            parts = [x for x in disp.split('/') if x]
            rparts = [x for x in root.split('/') if x]
            segs = [('/', None if rparts else str(self.remote_mount), '/')]
            for i, part in enumerate(parts):
                logical = '/' + '/'.join(parts[: i + 1])
                target = None
                if i + 1 >= len(rparts):
                    target = (
                        str(Path(self.remote_mount).joinpath(*parts[len(rparts) : i + 1]))
                        if i + 1 > len(rparts)
                        else str(self.remote_mount)
                    )
                segs.append((part, target, f'{self.remote_name}:{logical}'))
            return segs
        p = self.current
        parts = list(p.parts)
        acc = Path(parts[0]) if parts else Path('/')
        segs = []
        for idx, part in enumerate(parts):
            if idx:
                acc = acc / part
            segs.append(('/' if idx == 0 and part == '/' else (part or '/'), str(acc), str(acc)))
        return segs

    def _crumb_chip_text(self, mode):
        full = self.endpoint_label()
        if mode == 'full':
            return full
        active = self.owner.active is self
        if mode == 'dot':
            return '●' if active else '○'
        return ('● ' if active else '  ') + ('REMOTE' if self.is_remote() else 'LOCAL')

    def _crumb_layout(self, segs=None):
        # Choose what fits: the endpoint chip (full, compact, dot), the first
        # segment, an "…" menu, and the last 3, 2 or 1 segments shown in full.
        segs = segs if segs is not None else self._crumb_segments()
        btn = self._crumb_text_width
        sep = self._crumb_sep_width()
        seg_w = [min(btn(label), btn('x' * 1) + 240) + sep for label, _, _ in segs]
        avail = self.crumb.width() - 4
        if avail <= 8:
            return ('full', min(3, len(segs) - 1), True)
        for chip in ('full', 'compact', 'dot'):
            cw = min(btn(self._crumb_chip_text(chip)), 220) + sep
            if sum(seg_w) + cw <= avail:
                return (chip, len(segs) - 1, True)
            for keep in (3, 2, 1):
                if keep >= len(segs) - 1:
                    continue
                if cw + seg_w[0] + btn('…') + sep + sum(seg_w[-keep:]) <= avail:
                    return (chip, keep, True)
        # Very narrow (split view on a small screen): the first segment joins the
        # "…" menu so that the current folder's name stays readable.
        return ('dot', 1, False) if len(segs) > 1 else ('dot', 0, True)

    def _crumb_probe(self):
        # Hidden, styled probes measure real button/separator widths (padding and
        # borders come from the stylesheet), so the fit decision matches layout.
        if getattr(self, '_crumb_probe_btn', None) is None:
            self._crumb_probe_btn = QToolButton(self.crumb)
            self._crumb_probe_btn.hide()
            self._crumb_probe_sep = QLabel('›', self.crumb)
            self._crumb_probe_sep.setObjectName('crumbsep')
            self._crumb_probe_sep.hide()
        return self._crumb_probe_btn

    def _crumb_text_width(self, text):
        b = self._crumb_probe()
        b.ensurePolished()
        b.setText(text.replace('&', '&&'))
        return b.sizeHint().width() + self.crumb_lay.spacing()

    def _crumb_sep_width(self):
        self._crumb_probe()
        self._crumb_probe_sep.ensurePolished()
        return self._crumb_probe_sep.sizeHint().width() + self.crumb_lay.spacing()

    def _crumb_keep_count(self, segs=None):
        return self._crumb_layout(segs)[1]

    def _crumb_fit_changed(self):
        try:
            if self._crumb_keep is None:
                return False
            if (
                self._crumb_keep[0] == 'dot'
                and abs(self.crumb.width() - getattr(self, '_crumb_built_width', 0)) > 4
            ):
                return True
            return self._crumb_layout() != self._crumb_keep
        except Exception:
            return False

    def _endpoint_tooltip(self):
        if self.is_remote():
            host = ''
            try:
                host = str(self.owner._json_setting('servers_json').get(self.remote_name, {}).get('host', ''))
            except Exception:
                pass
            return (
                f'Remote connection · {self.remote_name}'
                + (f' · {host}' if host else '')
                + f' · {self.remote_protocol}'
            )
        return f'Local machine · {socket.gethostname()}'

    def _crumb_button(self, label, target, tip, cap=240):
        b = QToolButton()
        fm = b.fontMetrics()
        shown = (
            fm.elidedText(label, Qt.TextElideMode.ElideMiddle, cap)
            if fm.horizontalAdvance(label) > cap
            else label
        )
        b.setText(shown.replace('&', '&&'))
        b.setToolTip(tip)
        b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        if target is None:
            b.setEnabled(False)
        else:
            b.clicked.connect(lambda checked=False, x=target: self.go(x))
            if not self.is_remote():
                b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                b.customContextMenuRequested.connect(lambda pos, x=target: self.owner.path_actions(x))
        return b

    def update_breadcrumbs(self):
        while self.crumb_lay.count():
            item = self.crumb_lay.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.deleteLater()  # hide now: deletion waits for the event loop
        segs = self._crumb_segments()
        chip, keep, show_first = self._crumb_layout(segs)
        self._crumb_keep = (chip, keep, show_first)
        self._crumb_built_width = self.crumb.width()
        tag = QToolButton()
        tag.setText(self.endpoint_label())
        fm = tag.fontMetrics()
        if chip != 'full':
            tag.setText(self._crumb_chip_text(chip))
        elif fm.horizontalAdvance(tag.text()) > 196:
            tag.setText(fm.elidedText(tag.text(), Qt.TextElideMode.ElideRight, 196))
        tag.setToolTip(self._endpoint_tooltip())
        tag.setEnabled(False)
        self.crumb_lay.addWidget(tag)
        sep = QLabel('›')
        sep.setObjectName('crumbsep')
        self.crumb_lay.addWidget(sep)
        first = 1 if show_first else 0
        hidden = segs[first : len(segs) - keep] if len(segs) > keep + first else []
        shown = (segs[:first] + ['…'] + segs[len(segs) - keep :]) if hidden else segs
        for idx, seg in enumerate(shown):
            if seg == '…':
                more = QToolButton()
                more.setText('…')
                more.setObjectName('crumbMore')
                more.setToolTip('Show the hidden path segments')
                more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                more.setStyleSheet('QToolButton::menu-indicator{image:none;width:0}')
                menu = QMenu(more)
                for label, target, tip in hidden:
                    act = menu.addAction(label)
                    act.setToolTip(tip)
                    act.setEnabled(target is not None)
                    if target is not None:
                        act.triggered.connect(lambda checked=False, x=target: self.go(x))
                more.setMenu(menu)
                self.crumb_lay.addWidget(more)
            else:
                cap = 240
                if idx == len(shown) - 1 and chip == 'dot':
                    # Narrowest case: only here may the last segment be shortened.
                    used = sum(
                        self._crumb_text_width(t) + self._crumb_sep_width()
                        for t in ['●'] + [x if x == '…' else x[0] for x in shown[:-1]]
                    )
                    pad = self._crumb_text_width('')
                    cap = max(24, min(240, self.crumb.width() - 4 - used - pad))
                self.crumb_lay.addWidget(self._crumb_button(*seg, cap=cap))
            if idx < len(shown) - 1:
                sep = QLabel('›')
                sep.setObjectName('crumbsep')
                self.crumb_lay.addWidget(sep)
        self.crumb_lay.addStretch(1)

    def set_filter(self, t):
        self.model.set_name_filter(t)
        self._listing_changed()

    def _apply_root(self, path, attempt=0):
        # DirectoryModel lists the folder on a worker thread and streams rows in
        # batches. It is a flat model, so the view root is the model's top level.
        # Re-applying the same folder re-lists it in place and keeps the selection.
        self.model.setRootPath(str(path))
        self.view.setRootIndex(QModelIndex())
        return True

    def _commit_go(self, path, push=True, leave_remote=False, verified_remote=False):
        p = Path(os.path.abspath(os.path.expanduser(str(path))))
        if self.is_remote():
            if not self._path_inside_remote(p):
                if leave_remote:
                    self.clear_remote()
                else:
                    return self.owner.err(
                        f'Remote navigation blocked.\n\n{self.remote_name} is confined to its mounted filesystem.'
                    )
        elif not verified_remote:
            # Local paths are deliberately the only paths synchronously validated here.
            if not p.exists() or not p.is_dir():
                return self.owner.err(f'Folder not found:\n{p}')
        self.view.clearSelection()
        self.view.setCurrentIndex(QModelIndex())
        self.current = p
        self._apply_root(self.current)
        self.path.setText(str(self.current))
        self.location_stack.setCurrentWidget(self.crumb)
        self.update_breadcrumbs()
        self.filter.clear()
        self.view.clearSelection()
        self.view.setCurrentIndex(QModelIndex())
        if push:
            self.history = self.history[: self.hist + 1]
            self.history.append(str(self.current))
            self.hist = len(self.history) - 1
        self.owner.set_active(self)
        self.owner.record_location(self.current)
        self._sync_tab()
        self.owner.invalidate_quicklook()
        self.owner.update_local_watch()
        self.owner.update_status()

    def go(self, path, push=True, leave_remote=False):
        p = Path(os.path.abspath(os.path.expanduser(str(path))))
        remote = self.owner._remote_definition_for_path(p)
        if self.is_remote() or remote:
            if remote and not self.is_remote():
                name, proto, mp, root = remote
                self.bind_remote(name, proto, mp, root)
            return self.owner.navigate_remote_async(self, p, push, leave_remote)
        return self._commit_go(p, push, leave_remote, False)

    def up(self):
        if self.is_remote() and self.current == self.remote_mount:
            return
        if self.current.parent != self.current:
            self.go(self.current.parent)

    def back(self):
        if self.hist > 0:
            self.hist -= 1
            self.go(self.history[self.hist], False)

    def forward(self):
        if self.hist + 1 < len(self.history):
            self.hist += 1
            self.go(self.history[self.hist], False)

    def selected_rows(self):
        # Read the selection as row ranges: selectedRows() asks the model for every
        # cell's flags, which takes seconds after Ctrl+A in a 100 000-entry folder.
        rows = []
        seen = set()
        for r in self.view.selectionModel().selection():
            if r.parent().isValid():
                continue
            for row in range(r.top(), r.bottom() + 1):
                if row not in seen:
                    seen.add(row)
                    rows.append(row)
        return rows

    def selected(self):
        entries = self.model.visible_entries()
        root = self.model.rootPath()
        out = []
        for row in self.selected_rows():
            if 0 <= row < len(entries):
                out.append(Path(os.path.join(root, entries[row].name)))
        return out

    def activate(self, idx):
        src = self.proxy.mapToSource(idx)
        p = Path(self.model.filePath(src))
        self.go(p) if self.model.isDir(src) else self.owner.open_path(p)


class SidebarList(QListWidget):
    pathsDropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)

    def dragEnterEvent(self, e):
        urls = e.mimeData().urls() if e.mimeData().hasUrls() else []
        if any(u.isLocalFile() for u in urls):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        paths = (
            [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
            if e.mimeData().hasUrls()
            else []
        )
        if paths:
            self.pathsDropped.emit(paths)
            e.acceptProposedAction()
        else:
            super().dropEvent(e)


class WorkBasketList(QListWidget):
    pathsDropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and any(u.isLocalFile() for u in e.mimeData().urls()):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        paths = (
            [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
            if e.mimeData().hasUrls()
            else []
        )
        if paths:
            self.pathsDropped.emit(paths)
            e.acceptProposedAction()
        else:
            super().dropEvent(e)
