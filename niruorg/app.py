#!/usr/bin/env python3
import os, sys, shutil, subprocess, mimetypes, zipfile, tarfile, stat, json, urllib.request, urllib.parse, base64, shlex, socket, tempfile, time, re, hashlib, uuid, xml.etree.ElementTree as ET
from pathlib import Path
from PySide6.QtCore import (
    qVersion,
    QItemSelectionModel,
    QPointF,
    Qt,
    QDate,
    QDir,
    QUrl,
    QSettings,
    QStandardPaths,
    QModelIndex,
    QEvent,
    QSortFilterProxyModel,
    QIdentityProxyModel,
    QRegularExpression,
    QSize,
    QFile,
    QTimer,
    QRunnable,
    QThreadPool,
    Signal,
    QObject,
    QProcess,
    QMimeData,
)
from PySide6.QtGui import (
    QStandardItemModel,
    QStandardItem,
    QAction,
    QKeySequence,
    QDesktopServices,
    QImage,
    QPixmap,
    QIcon,
    QShortcut,
    QColor,
    QPainter,
    QPen,
    QBrush,
    QPolygonF,
    QCursor,
    QDrag,
)
from PySide6.QtWidgets import *
from PySide6.QtWidgets import QFileIconProvider

try:
    from .transfer_safety import TransferSafetyError, verified_partial_offset, guard_transfer_locations
    from .utils.workers import TaskWorker
    from .services.theme import default_theme, load_nirux_metrics, load_nirux_palette
    from .services.theme_watcher import ThemeWatcher
    from .services.nextcloud import NextcloudClient, NextcloudError
    from .services.local_watcher import LocalDirectoryWatcher
    from .core.rename import RenameError, execute_bulk_rename, plan_bulk_rename
    from .core.paths import mounted_paths, path_is_mounted, lexical_under
    from .utils.format import human
    from .utils.logging import log_error
    from .ui.directory_model import DirectoryModel
except ImportError:  # Direct execution via installer's app.py launcher
    from transfer_safety import TransferSafetyError, verified_partial_offset, guard_transfer_locations
    from utils.workers import TaskWorker
    from services.theme import default_theme, load_nirux_metrics, load_nirux_palette
    from services.theme_watcher import ThemeWatcher
    from services.nextcloud import NextcloudClient, NextcloudError
    from services.local_watcher import LocalDirectoryWatcher
    from core.rename import RenameError, execute_bulk_rename, plan_bulk_rename
    from core.paths import mounted_paths, path_is_mounted, lexical_under
    from utils.format import human
    from utils.logging import log_error
    from ui.directory_model import DirectoryModel

# The UI lives in niruorg/ui/ (0.6.0, M1). These names stay importable from
# niruorg.app for compatibility.
try:
    from .ui.base import (
        THEMES,
        _safe_archive_target,
        omarchy_palette,
        run_detached,
        safe_extract_tar,
        safe_extract_zip,
    )  # noqa: F401
    from .ui.dialogs import ImageViewerDialog, NiruDialog, Prefs  # noqa: F401
    from .ui.workers import (  # noqa: F401
        ConnectionDiagnosticSignals,
        ConnectionDiagnosticWorker,
        DiscoverySignals,
        DiscoveryWorker,
        MetadataSignals,
        MetadataWorker,
        RemoteProbeSignals,
        RemoteProbeWorker,
        SearchWorker,
        StartupTrace,
        WorkerSignals,
    )
    from .ui.transfer import TransferWorker  # noqa: F401
    from .ui.panes import (  # noqa: F401
        BrowserTree,
        CrumbBar,
        FilePane,
        Filter,
        PaneState,
        PaneTabBar,
        RowHoverDelegate,
        SemanticIconProvider,
        SidebarList,
        WorkBasketList,
    )
    from .ui.sidebar import SidebarMixin  # noqa: F401
    from .ui.quicklook import QuickLookMixin  # noqa: F401
    from .ui.menus import MenuMixin  # noqa: F401
    from .ui.remote import RemoteMixin  # noqa: F401
    from .ui.transfers_ui import TransferUIMixin  # noqa: F401
    from .ui.media import MediaMixin  # noqa: F401
except ImportError:  # app.py run directly: niruorg/ is on sys.path
    from ui.base import (
        THEMES,
        _safe_archive_target,
        omarchy_palette,
        run_detached,
        safe_extract_tar,
        safe_extract_zip,
    )  # noqa: F401
    from ui.dialogs import ImageViewerDialog, NiruDialog, Prefs  # noqa: F401
    from ui.workers import (  # noqa: F401
        ConnectionDiagnosticSignals,
        ConnectionDiagnosticWorker,
        DiscoverySignals,
        DiscoveryWorker,
        MetadataSignals,
        MetadataWorker,
        RemoteProbeSignals,
        RemoteProbeWorker,
        SearchWorker,
        StartupTrace,
        WorkerSignals,
    )
    from ui.transfer import TransferWorker  # noqa: F401
    from ui.panes import (  # noqa: F401
        BrowserTree,
        CrumbBar,
        FilePane,
        Filter,
        PaneState,
        PaneTabBar,
        RowHoverDelegate,
        SemanticIconProvider,
        SidebarList,
        WorkBasketList,
    )
    from ui.sidebar import SidebarMixin  # noqa: F401
    from ui.quicklook import QuickLookMixin  # noqa: F401
    from ui.menus import MenuMixin  # noqa: F401
    from ui.remote import RemoteMixin  # noqa: F401
    from ui.transfers_ui import TransferUIMixin  # noqa: F401
    from ui.media import MediaMixin  # noqa: F401
APP = 'NIRUORG'
VERSION = '0.5.1'


class Main(SidebarMixin, QuickLookMixin, MenuMixin, RemoteMixin, TransferUIMixin, MediaMixin, QMainWindow):
    def __init__(self, path=None):
        super().__init__()
        self.startup_trace = StartupTrace()
        self.startup_trace.mark('settings begin')
        self.s = QSettings('NIRU', 'NIRUORG')
        self.theme = self.s.value('theme', default_theme())
        self.terminal = self.s.value(
            'terminal', shutil.which('kitty') or shutil.which('x-terminal-emulator') or ''
        )
        self.shell = self.s.value('shell', shutil.which('fish') or shutil.which('bash') or '/bin/sh')
        self.confirm_delete = self.s.value('confirm_delete', True, type=bool)
        self.density = self.s.value('density', 'Normal')
        self.date_format = self.s.value('date_format', 'Swedish')
        self.restore_session = self.s.value('restore_session', True, type=bool)
        self.audio_player = self.s.value('audio_player', 'NIRU Player (MPV backend)')
        self.active = None
        self.clip = []
        self.cut_mode = False
        self.threadpool = QThreadPool.globalInstance()
        self.dropzone = self.s.value('work_basket', [], type=list) or []
        self.operations = []
        self.undo_stack = []
        self.running_workers = []
        self._worker_refs = {}
        self._worker_seq = 0
        self._accept_worker_results = True
        self.nirux_theme_watcher = ThemeWatcher(self)
        self.nirux_theme_watcher.changed.connect(self._nirux_theme_changed)
        self.collapsed_sections = set(self.s.value('collapsed_sections', [], type=list) or [])
        self.recent_locations = self.s.value('recent_locations', [], type=list) or []
        self.focus_mode = False
        self.shortcut_hits = {}
        self.closed_tabs_global = []
        self._hidden_right_tabs = None
        self._remote_probe_pool = QThreadPool(self)
        self._remote_probe_pool.setMaxThreadCount(2)
        self._remote_probe_seq = 0
        self._remote_probe_tokens = {}
        self._cloud_cache = []
        self._cloud_types = {}
        self._devices_cache = []
        self._owned_mounts = {}
        self._shutdown_done = False
        self._mount_journal = Path.home() / '.local/state/niruorg/owned-mounts.json'
        self._load_mount_journal()
        self.input_diag_path = Path.home() / '.local/state/niruorg/input-diagnostics.log'
        self.input_diag_enabled = False
        self._private_ssh_agent_pid = None
        self._private_ssh_agent_sock = None
        QApplication.instance().installEventFilter(self)
        self.setWindowTitle(f'{APP}')
        self.setWindowIcon(QIcon(str(Path(__file__).resolve().parent.parent / 'assets/niruorg.svg')))
        self.resize(1180, 760)
        self.setMinimumSize(760, 460)
        self.sidebar = SidebarList()
        self.sidebar.setAccessibleName('Locations and connections')
        self.sidebar.setMinimumWidth(150)
        self.sidebar.setMaximumWidth(480)
        self.sidebar.itemClicked.connect(self.sidebar_clicked)
        self.sidebar.pathsDropped.connect(self.add_shortcuts)
        self.sidebar.customContextMenuRequested.connect(self.sidebar_context_menu)
        self.build_sidebar()
        self.startup_trace.mark('cheap sidebar')
        self.pane1 = FilePane(self)
        self.pane2 = FilePane(self)
        self.pane2.hide()
        self.active = self.pane1
        self.pane1.setProperty('activePane', True)
        self._install_browser_shortcuts()
        self.pane1.view.setAccessibleName('Left file list')
        self.pane2.view.setAccessibleName('Right file list')
        self.pane1.filter.setAccessibleName('Filter left pane')
        self.pane2.filter.setAccessibleName('Filter right pane')
        self.pane1.path.setAccessibleName('Left pane location')
        self.pane2.path.setAccessibleName('Right pane location')
        self.split = QSplitter()
        self.split.setObjectName('mainSplitter')
        self.split.addWidget(self.pane1)
        self.split.addWidget(self.pane2)
        self.split.setChildrenCollapsible(False)
        self.split.setHandleWidth(7)
        self.split.setStretchFactor(0, 1)
        self.split.setStretchFactor(1, 1)
        self.split.splitterMoved.connect(self._remember_split_sizes)
        self.local_watcher = LocalDirectoryWatcher(self)
        self.local_watcher.changed.connect(self._local_directory_changed)
        # U2: the sidebar is resizable (min 150 px) and its width is remembered.
        center = QSplitter(Qt.Orientation.Horizontal)
        center.setObjectName('sidebarSplitter')
        center.setChildrenCollapsible(False)
        center.setHandleWidth(3)
        center.addWidget(self.sidebar)
        center.addWidget(self.split)
        center.setStretchFactor(0, 0)
        center.setStretchFactor(1, 1)
        self.sidebar_splitter = center
        sw = self.s.value('sidebar_width', 176, type=int)
        sw = max(150, min(480, int(sw or 176)))
        center.setSizes([sw, max(400, 1180 - sw)])
        center.splitterMoved.connect(self._remember_sidebar_width)
        self.status = QLabel()
        self.status.setObjectName('status')
        self.status.setAccessibleName('File manager status')
        self.status.setContentsMargins(12, 6, 12, 8)
        self.transfer_bar = QWidget()
        self.transfer_bar.setObjectName('transferBar')
        tb = QHBoxLayout(self.transfer_bar)
        tb.setContentsMargins(12, 7, 8, 7)
        tb.setSpacing(10)
        texts = QWidget()
        tx = QVBoxLayout(texts)
        tx.setContentsMargins(0, 0, 0, 0)
        tx.setSpacing(1)
        self.transfer_title = QLabel()
        self.transfer_title.setObjectName('transferTitle')
        self.transfer_detail = QLabel()
        self.transfer_detail.setObjectName('muted')
        tx.addWidget(self.transfer_title)
        tx.addWidget(self.transfer_detail)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(220)
        self.progress.setMaximumHeight(5)
        self.transfer_cancel = QToolButton()
        self.transfer_cancel.setText('Cancel')
        self.transfer_cancel.clicked.connect(self._cancel_visible_transfer)
        tb.addWidget(texts, 1)
        tb.addWidget(self.progress)
        tb.addWidget(self.transfer_cancel)
        self.transfer_bar.hide()
        self._transfer_states = {}
        self._visible_transfer = None
        self._close_after_transfers = False
        c = QWidget()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(center, 1)
        lay.addWidget(self.transfer_bar)
        lay.addWidget(self.status)
        self.setCentralWidget(c)
        self.quicklook_requested = False
        self.build_quicklook()
        self.build_menu()
        self.shortcuts()
        self.apply_theme()
        self.configure_theme_watcher()
        self._startup_requested_path = path
        self._startup_show_marked = False
        self.startup_trace.mark('main window built')
        self.pane1._commit_go(Path.home(), True)
        QApplication.instance().aboutToQuit.connect(self._shutdown_remote_resources)
        QTimer.singleShot(0, self._post_show_startup)

    def _remember_sidebar_width(self, *_):
        if self.sidebar.isVisible():
            w = self.sidebar.width()
            if 150 <= w <= 480:
                self.s.setValue('sidebar_width', w)

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, '_startup_show_marked', False):
            self._startup_show_marked = True
            self.startup_trace.mark('window shown')
        self.update_local_watch()

    def save_settings(self):
        for k, v in [
            ('theme', self.theme),
            ('terminal', self.terminal),
            ('shell', self.shell),
            ('confirm_delete', self.confirm_delete),
            ('density', self.density),
            ('date_format', self.date_format),
            ('restore_session', self.restore_session),
            ('audio_player', self.audio_player),
        ]:
            self.s.setValue(k, v)

    def palette(self):
        if self.theme == 'Follow NIRUX':
            return load_nirux_palette()
        if self.theme == 'Follow Omarchy':
            return omarchy_palette() or THEMES['Niru Noir']
        if self.theme == 'System':
            return THEMES['Niru Noir']
        return THEMES.get(self.theme, THEMES['Niru Noir'])

    def theme_metrics(self):
        if self.theme == 'Follow NIRUX':
            return load_nirux_metrics()
        return {
            'font_size': 13,
            'padding': {'Compact': 3, 'Normal': 5, 'Relaxed': 8}.get(self.density, 5),
            'focus_width': 1,
        }

    def configure_theme_watcher(self):
        watcher = getattr(self, 'nirux_theme_watcher', None)
        if watcher is None:
            return
        if self.theme == 'Follow NIRUX':
            watcher.start()
        else:
            watcher.stop()

    def _nirux_theme_changed(self, _palette):
        if self.theme != 'Follow NIRUX':
            return
        self.apply_theme()
        self.refresh_views()
        self.update_quicklook()

    def apply_theme(self):
        t = self.palette()
        metrics = self.theme_metrics()
        pad = metrics['padding']
        self.setStyleSheet(
            (
                '''QWidget { background:%(bg)s;color:%(fg)s;font-size:%(font_size)spx;selection-background-color:%(sel)s;selection-color:%(fg)s;} QTreeView,QTableView,QListWidget,QPlainTextEdit {background:%(bg)s;border:0;} QLineEdit,QComboBox {background:%(panel)s;color:%(fg)s;padding:7px 9px;border:1px solid %(border)s;border-radius:5px;} QLineEdit:focus,QComboBox:focus {border:%(focus_width)spx solid %(accent)s;} QListWidget {background:%(panel)s;padding:7px;border-right:1px solid %(border)s;} QListWidget::item {padding:6px;border-radius:4px;} QListWidget::item:hover {background:%(surface)s;} QListWidget::item:selected {background:%(sel)s;color:%(fg)s;} QTreeView::item,QTableView::item {padding:%(pad)spx 4px;} QTreeView::item:hover,QTableView::item:hover {background:%(surface)s;} QTreeView::item:selected,QTableView::item:selected {background:%(sel)s;color:%(fg)s;} QHeaderView::section {background:%(panel)s;color:%(muted)s;padding:6px;border:0;border-bottom:1px solid %(border)s;} QToolButton,QPushButton {background:transparent;color:%(fg)s;border:1px solid transparent;border-radius:5px;padding:6px 10px;} QToolButton:hover,QPushButton:hover {background:%(surface)s;border-color:%(border)s;} QPushButton:default,QPushButton:focus,QToolButton:focus {border:1px solid %(accent)s;} QPushButton {qproperty-iconSize:0px 0px;} QPushButton:pressed,QToolButton:pressed {background:%(sel)s;} QMenu {background:%(panel)s;border:1px solid %(border)s;padding:5px;} QMenu::item {padding:7px 24px;border-radius:4px;} QMenu::item:selected {background:%(sel)s;} QDialog {background:%(bg)s;} QCheckBox::indicator {width:15px;height:15px;border:1px solid %(border)s;border-radius:3px;background:%(panel)s;} QCheckBox::indicator:checked {background:%(surface)s;border:2px solid %(fg)s;} QWidget#filePane[activePane="true"] {border-top:2px solid %(fg)s;} QTabBar#paneTabs {border-bottom:1px solid %(border)s;} QTabBar#paneTabs::tab {min-width:72px;padding:6px 8px 6px 12px;color:%(muted)s;background:%(panel)s;border-right:1px solid %(border)s;} QTabBar#paneTabs::tab:selected {color:%(fg)s;background:%(surface)s;font-weight:600;border-bottom:2px solid %(fg)s;} QWidget#filePane[activePane="false"] QTabBar#paneTabs::tab:selected {color:%(fg)s;background:%(surface)s;font-weight:500;border-bottom:2px solid %(muted)s;} QTabBar#paneTabs[activePane="true"]::tab:selected {color:%(fg)s;background:%(sel)s;font-weight:700;border-bottom:2px solid %(fg)s;} QToolButton#paneTabClose {color:%(muted)s;background:transparent;border:0;border-radius:3px;padding:0;margin:0;} QToolButton#paneTabClose:hover {color:%(fg)s;background:%(sel)s;border:0;} QSplitter#mainSplitter::handle {background:transparent;width:7px;} QSplitter#sidebarSplitter::handle {background:transparent;} QSplitter#mainSplitter::handle:horizontal {border-left:1px solid %(border)s;} QLabel#crumbsep {color:%(muted)s;padding:0 2px;} QProgressBar {background:%(bg)s;border:0;} QProgressBar::chunk {background:%(fg)s;} QLabel#muted {color:%(muted)s;} QLabel#paneStateTitle {font-weight:600;font-size:%(font_size)spx;} QWidget#paneState {background:transparent;} QLabel#status {color:%(muted)s;border-top:1px solid %(border)s;} QWidget#transferBar,QWidget#paneActivity {background:%(panel)s;border-top:1px solid %(border)s;} QLabel#transferTitle {font-weight:600;} QWidget#transferBar QProgressBar {background:%(bg)s;border:1px solid %(border)s;border-radius:2px;} QWidget#transferBar QProgressBar::chunk {background:%(fg)s;} QScrollBar:vertical {background:%(bg)s;width:9px;margin:0;} QScrollBar::handle:vertical {background:%(border)s;min-height:24px;border-radius:4px;} QScrollBar::add-line,QScrollBar::sub-line {height:0;width:0;}'''
            )
            % {**t, 'pad': pad, **metrics}
        )
        for pane in (getattr(self, 'pane1', None), getattr(self, 'pane2', None)):
            if pane:
                pane.icons.set_palette(t)
                pane.model.setIconProvider(pane.icons)
        self.sync_row_heights()

    def sync_row_heights(self):
        # The file list is a QTableView with fixed row heights; give it exactly the
        # row height a QTreeView would compute from the current stylesheet, font
        # and icon size, so density and themes look as before.
        for pane in (getattr(self, 'pane1', None), getattr(self, 'pane2', None)):
            if pane is None:
                continue
            probe = QTreeView(self)
            probe.hide()
            probe.setIconSize(pane.view.iconSize())
            m = QStandardItemModel(probe)
            m.appendRow([QStandardItem(pane.icons._icon('folder'), 'Ag'), QStandardItem('4.88 KiB')])
            probe.setModel(m)
            probe.ensurePolished()
            h = probe.sizeHintForRow(0)
            probe.setParent(None)
            probe.deleteLater()
            if h > 0:
                pane.view.set_row_height(h)

    def show_about(self):
        self.info(
            'About NIRUORG',
            f'<b>NIRUORG {VERSION}</b><br><br>Minimal but powerful file organizer for Linux.<br>Fast local and remote file management with a keyboard-first workflow and full mouse support.<br><br>Created by Nicklas Rudolfsson.',
        )

    def refresh_current(self):
        self.invalidate_quicklook()
        self.active.go(self.active.current, False)
        self.update_status()

    def escape_action(self):
        if self.active.location_stack.currentWidget() is self.active.path:
            self.active.cancel_location()
            self.active.view.setFocus()
            return
        if self.active.filter.hasFocus() or self.active.filter.text():
            self.active.filter.clear()
            self.active.view.setFocus()
            return
        self.active.view.clearSelection()
        self.update_status()

    def quick_create(self):
        d = NiruDialog(self)
        d.setWindowTitle('New')
        d.setMinimumWidth(420)
        f = QFormLayout(d)
        kind = QComboBox()
        kind.addItems(['Text file', 'Markdown file', 'Folder'])
        name = QLineEdit()
        name.setPlaceholderText('Name')
        f.addRow('Type', kind)
        f.addRow('Name', name)
        b = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        [x.setIcon(QIcon()) for x in b.buttons()]
        f.addRow(b)
        b.accepted.connect(d.accept)
        b.rejected.connect(d.reject)
        name.setFocus()
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        n = name.text().strip()
        if not n:
            return
        if kind.currentText() == 'Markdown file' and not Path(n).suffix:
            n += '.md'
        target = self.current_dir() / n
        if target.exists():
            return self.err(f'Already exists: {target.name}')
        try:
            if kind.currentText() == 'Folder':
                target.mkdir()
            else:
                target.touch(exist_ok=False)
            if target.suffix.lower() == '.md':
                self.open_path(target)
        except Exception as e:
            self.err(e)

    def set_active(self, p):
        self.active = p
        for pane in (self.pane1, self.pane2):
            pane.setProperty('activePane', pane is p)
            pane.tabs.setProperty('activePane', pane is p)
            pane.style().unpolish(pane)
            pane.style().polish(pane)
            pane.tabs.style().unpolish(pane.tabs)
            pane.tabs.style().polish(pane.tabs)
            pane.update_breadcrumbs()
        if hasattr(self, 'copy_other_action') and self.copy_other_action:
            self.copy_other_action.setText(self.copy_other_label())
            self.move_other_action.setText(self.move_other_label())
        self.update_local_watch()
        self.update_status()

    def pane_side(self, pane):
        return 'left' if pane is self.pane1 else 'right'

    def other_side(self, pane=None):
        return 'right' if (pane or self.active) is self.pane1 else 'left'

    def open_other_label(self):
        return f'Open in {self.other_side()} pane'

    def copy_other_label(self):
        return f'Copy to {self.other_side()} pane'

    def move_other_label(self):
        return f'Move to {self.other_side()} pane…'

    def other_pane(self, pane=None, ensure=True):
        pane = pane or self.active
        if ensure and not self.pane2.isVisible():
            self.show_right_pane()
        return self.pane2 if pane is self.pane1 else self.pane1

    def pane_target_label(self, pane):
        return f'{pane.endpoint_label()} · {pane.display_path()}'

    def selected(self):
        return self.active.selected()

    def current_dir(self):
        return self.active.current

    def schedule_status(self):
        # Coalesce bursts of listing signals into one status refresh. The timer is
        # single-shot and only armed by a change, so an idle window does no work.
        t = getattr(self, '_status_timer', None)
        if t is None:
            t = self._status_timer = QTimer(self)
            t.setSingleShot(True)
            t.setInterval(60)
            t.timeout.connect(self.update_status)
        if not t.isActive():
            t.start()

    def update_status(self):
        s = self.active.selected_rows()
        parts = []
        root = self.active.view.rootIndex()
        count = self.active.proxy.rowCount(root)
        if self.pane2.isVisible():
            parts.append(f'{self.pane_side(self.active).capitalize()} active')
        parts.append(f'{count} item(s)')
        if self.active.model.is_partial():
            parts.append('listing cancelled · F5 lists again')
        if s:
            # Sizes come from the listing metadata: no stat() on the UI thread.
            pane = self.active
            entries = pane.model.visible_entries()
            total = 0
            for row in s:
                if 0 <= row < len(entries) and not entries[row].is_dir:
                    total += entries[row].size
            parts.append(f'{len(s)} selected' + (f' · {human(total)}' if total else ''))
        if not self.active.is_remote():
            try:
                parts.append(f'{human(shutil.disk_usage(self.active.current).free)} free')
            except OSError:
                pass
        parts.append(f'REMOTE · {self.active.remote_name}' if self.active.is_remote() else 'LOCAL')
        if self.operations:
            parts.append(f'{len(self.operations)} transfer(s)')
        if self._inside_nextcloud():
            parts.append(f'Nextcloud · {self.nextcloud_status().split(" · ")[0]}')
        self.status.setText(' · '.join(parts))

    def record_location(self, path):
        p = str(path)
        if p in self.recent_locations:
            self.recent_locations.remove(p)
        self.recent_locations.insert(0, p)
        self.recent_locations = self.recent_locations[:30]
        self.s.setValue('recent_locations', self.recent_locations)

    def toggle_focus(self):
        self.focus_mode = not self.focus_mode
        self.sidebar.setVisible(not self.focus_mode)
        self.menuBar().setVisible(not self.focus_mode)
        self.status.setVisible(not self.focus_mode)
        self.transfer_bar.setVisible(False if self.focus_mode else bool(self.operations))
        if self.focus_mode and hasattr(self, 'quickdock'):
            self.quickdock.hide()

    def format_dt(self, ts):
        from datetime import datetime

        d = datetime.fromtimestamp(ts)
        if self.date_format == 'Swedish':
            return d.strftime('%Y-%m-%d %H:%M')
        if self.date_format == 'ISO':
            return d.strftime('%Y-%m-%dT%H:%M:%S')
        if self.date_format == 'Compact':
            return d.strftime('%y-%m-%d %H:%M')
        return d.strftime('%x %X')

    def refresh_views(self):
        for pane in (self.pane1, self.pane2):
            pane.proxy.invalidate()
            pane.view.viewport().update()
            pane.view.header().viewport().update()

    def smart_view(self):
        try:
            files = [p for p in self.current_dir().iterdir() if p.is_file()]
        except Exception as e:
            return self.err(e)
        if not files:
            return self.status.setText('Smart view · empty folder')
        images = [p for p in files if (mimetypes.guess_type(p.name)[0] or '').startswith('image/')]
        media = [p for p in files if (mimetypes.guess_type(p.name)[0] or '').startswith(('audio/', 'video/'))]
        if len(images) / len(files) >= 0.5:
            return self.gallery()
        if len(media) / len(files) >= 0.5:
            self.status.setText(f'Smart view · media folder · {len(media)} playable item(s) · Ctrl+P to play')
            return
        self.context_summary()

    def context_summary(self):
        try:
            items = list(self.current_dir().iterdir())
            dirs = [p for p in items if p.is_dir()]
            files = [p for p in items if p.is_file()]
            total = sum(p.stat().st_size for p in files if p.exists())
            groups = {}
            for p in files:
                mime = mimetypes.guess_type(p.name)[0] or 'other'
                kind = mime.split('/', 1)[0] if '/' in mime else 'other'
                groups[kind] = groups.get(kind, 0) + 1
            git = (self.current_dir() / '.git').exists()
            docker = any(
                (self.current_dir() / n).exists()
                for n in ('compose.yaml', 'compose.yml', 'docker-compose.yml')
            )
            py = any((self.current_dir() / n).exists() for n in ('pyproject.toml', 'requirements.txt'))
            node = (self.current_dir() / 'package.json').exists()
            tags = [x for x, v in [('Git', git), ('Docker', docker), ('Python', py), ('Node', node)] if v]
            git_detail = ''
            if git and shutil.which('git'):
                try:
                    gr = subprocess.run(
                        ['git', 'status', '--porcelain', '--branch'],
                        cwd=self.current_dir(),
                        capture_output=True,
                        text=True,
                        timeout=3,
                    )
                    gl = gr.stdout.splitlines()
                    git_detail = (gl[0].replace('## ', '') if gl else '') + f' · {max(0,len(gl)-1)} changed'
                except Exception:
                    pass
            lines = [
                str(self.current_dir()),
                '',
                f'{len(dirs)} folders · {len(files)} files · {human(total)} direct file size',
            ] + [f'{k}: {v}' for k, v in sorted(groups.items())]
            if tags:
                lines += ['', 'Project context: ' + ' · '.join(tags)]
            if git_detail:
                lines += ['Git: ' + git_detail]
            self.info('Context summary', '\n'.join(lines))
        except Exception as e:
            self.err(e)

    def storage_view(self):
        try:
            d = NiruDialog(self)
            d.setWindowTitle(f'Storage — {self.current_dir()}')
            d.resize(760, 520)
            l = QVBoxLayout(d)
            usage = shutil.disk_usage(self.current_dir())
            head = QLabel(
                f'<b>{self.current_dir()}</b><br>{human(usage.used)} used · {human(usage.free)} free · {human(usage.total)} total'
            )
            l.addWidget(head)
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(int(usage.used / usage.total * 1000) if usage.total else 0)
            l.addWidget(bar)
            w = QTreeWidget()
            w.setHeaderLabels(['Name', 'Type', 'Direct size'])
            w.setRootIsDecorated(False)
            for p in sorted(self.current_dir().iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                try:
                    size = '—' if p.is_dir() else human(p.stat().st_size)
                except:
                    size = '—'
                QTreeWidgetItem(
                    w, [p.name, 'Folder' if p.is_dir() else (mimetypes.guess_type(p.name)[0] or 'File'), size]
                )
            w.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            w.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            w.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            l.addWidget(w, 1)
            l.addWidget(
                QLabel(
                    'Directory sizes are intentionally not calculated recursively. Use Inspector when needed.'
                )
            )
            d.exec()
        except Exception as e:
            self.err(e)

    def permissions_view(self):
        try:
            d = NiruDialog(self)
            d.setWindowTitle(f'Permissions — {self.current_dir()}')
            d.resize(850, 560)
            l = QVBoxLayout(d)
            w = QTreeWidget()
            w.setHeaderLabels(['Name', 'Mode', 'UID:GID', 'Writable', 'Type'])
            w.setRootIsDecorated(False)
            for p in sorted(self.current_dir().iterdir(), key=lambda x: x.name.lower()):
                try:
                    st = p.lstat()
                    QTreeWidgetItem(
                        w,
                        [
                            p.name,
                            stat.filemode(st.st_mode),
                            f'{st.st_uid}:{st.st_gid}',
                            'Yes' if os.access(p, os.W_OK) else 'No',
                            'Folder' if p.is_dir() else 'File',
                        ],
                    )
                except Exception:
                    pass
            w.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for i in range(1, 5):
                w.header().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
            l.addWidget(QLabel('Read-only context view · no recursive permission scan.'))
            l.addWidget(w, 1)
            d.exec()
        except Exception as e:
            self.err(e)

    def context_menu(self, pane, pos):
        self.set_active(pane)
        m = QMenu(self)
        sel = self.selected()
        one = sel[0] if len(sel) == 1 else None
        audio = bool(
            one
            and one.is_file()
            and one.suffix.lower()
            in {'.mp3', '.flac', '.ogg', '.opus', '.m4a', '.aac', '.wav', '.wma', '.ape'}
        )
        m.addAction('Open', self.open_selected)
        m.addAction('Open With…', self.open_with)
        m.addAction('Preview', self.preview)
        m.addSeparator()
        m.addAction('Copy', self.copy)
        m.addAction('Cut', self.cut)
        m.addAction('Paste', self.paste)
        m.addAction(self.copy_other_label(), self.send_other_pane)
        m.addAction(self.move_other_label(), self.move_other_pane)
        m.addAction('Rename', self.rename)
        m.addAction('Move to Trash', self.trash)
        m.addAction('Delete Permanently…', self.permanent_delete)
        m.addSeparator()
        m.addAction('Open terminal here', self.terminal_here)
        if audio:
            m.addAction('Play in NIRU Player', lambda: self.niru_player([one], 0))
            m.addAction('Play with configured player', self.play_audio)
            if shutil.which('mpv'):
                m.addAction('Play with MPV', self.mpv)
        m.addAction('Send with LocalSend', self.localsend)
        m.addAction('Add to Work Basket', self.add_dropzone)
        m.addAction('Run NIRU Action…', self.run_niru_action)
        m.addAction('Run Recipe…', self.run_recipe)
        m.addAction('Add folder as Shortcut', self.add_selected_shortcut)
        if self.pane2.isVisible():
            m.addAction('Send to other pane', self.send_other_pane)
        m.addAction('Extract here', self.extract)
        m.addAction('Compress to ZIP', self.compress)
        m.addSeparator()
        m.addAction('Copy path', self.copy_path)
        m.addAction('Copy shell-quoted path', self.copy_shell_path)
        m.addAction('Properties', self.properties)
        if self._inside_nextcloud():
            m.addAction('Nextcloud public link…', self.nextcloud_share)
            m.addAction('Remove Nextcloud public links…', self.nextcloud_remove_links)
        m.exec(pane.view.viewport().mapToGlobal(pos))

    def _desktop_candidates(self, needle):
        roots = [
            Path.home() / '.local/share/applications',
            Path('/usr/local/share/applications'),
            Path('/usr/share/applications'),
        ]
        out = []
        for root in roots:
            if not root.exists():
                continue
            for f in root.glob('*.desktop'):
                try:
                    text = f.read_text(errors='ignore')
                    low = (f.name + ' ' + text).casefold()
                    if needle.casefold() in low and 'NoDisplay=true' not in text:
                        out.append((f.name, f))
                except:
                    pass
        return out

    def _preferred_niru_app(self, p):
        ext = p.suffix.lower()
        needles = ['nirupres'] if ext == '.nirupres' else ['nirunote'] if ext in ('.md', '.markdown') else []
        for n in needles:
            hits = self._desktop_candidates(n)
            if hits:
                return hits[0][0]
        return None

    def _launch_desktop(self, desktop_id, p):
        gio = shutil.which('gio')
        if gio:
            r = subprocess.run([gio, 'launch', desktop_id, str(p)], capture_output=True, text=True)
            if r.returncode == 0:
                return True
        for root in [
            Path.home() / '.local/share/applications',
            Path('/usr/local/share/applications'),
            Path('/usr/share/applications'),
        ]:
            f = root / desktop_id
            if not f.exists():
                continue
            try:
                line = next(
                    x.split('=', 1)[1]
                    for x in f.read_text(errors='ignore').splitlines()
                    if x.startswith('Exec=')
                )
                args = shlex.split(line)
                args = [
                    str(p) if x in ('%f', '%F', '%u', '%U') else x
                    for x in args
                    if x not in ('%i', '%c', '%k')
                ]
                return run_detached(args)
            except:
                pass
        return False

    def open_path(self, p):
        p = Path(p)
        if p.is_dir():
            return self.active.go(p)
        app = self._preferred_niru_app(p)
        if app and self._launch_desktop(app, p):
            return True
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def open_selected(self):
        s = self.selected()
        if len(s) == 1:
            p = s[0]
            if p.is_file() and p.suffix.lower() in {
                '.mp3',
                '.flac',
                '.ogg',
                '.opus',
                '.m4a',
                '.aac',
                '.wav',
                '.wma',
                '.ape',
            }:
                return self.play_audio()
            self.open_path(p)

    def open_with(self):
        s = self.selected()
        if len(s) != 1 or s[0].is_dir():
            return self.err('Select exactly one file.')
        p = s[0]
        apps = []
        for needle in ('nirupres', 'nirunote', 'niruword'):
            for did, f in self._desktop_candidates(needle):
                if did not in [x[0] for x in apps]:
                    apps.append((did, f.stem))
        if not apps:
            return self.err(
                'No compatible NIRU desktop applications were detected. System Open remains available through the default association.'
            )
        labels = [f'{name}  ·  {did}' for did, name in apps]
        choice, ok = QInputDialog.getItem(self, 'Open With', p.name, labels, 0, False)
        if ok:
            self._launch_desktop(apps[labels.index(choice)][0], p)

    def _mime_for_extension(self, ext):
        return {'md': 'text/markdown', 'markdown': 'text/markdown', 'nirupres': 'application/x-nirupres'}.get(
            ext.lstrip('.').lower()
        )

    def _set_xdg_default(self, mime, desktop_id):
        exe = shutil.which('xdg-mime')
        if not exe:
            raise RuntimeError('xdg-mime is not installed.')
        r = subprocess.run([exe, 'default', desktop_id, mime], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(r.stderr.strip() or 'xdg-mime failed')

    def file_associations(self):
        d = NiruDialog(self)
        d.setWindowTitle('File Associations')
        d.resize(720, 420)
        l = QVBoxLayout(d)
        w = QTreeWidget()
        w.setHeaderLabels(['Type', 'Preferred app', 'Detected desktop entry'])
        w.setRootIsDecorated(False)
        rows = []
        for ext, label, needle in [
            ('.nirupres', 'NIRUPRES', 'nirupres'),
            ('.md / .markdown', 'NIRUNOTE', 'nirunote'),
        ]:
            hits = self._desktop_candidates(needle)
            did = hits[0][0] if hits else ''
            it = QTreeWidgetItem(w, [ext, label, did or 'Not detected'])
            rows.append((it, ext, did))
        w.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        w.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        w.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        l.addWidget(QLabel('NIRUORG uses Linux/XDG defaults rather than a private association database.'))
        l.addWidget(w, 1)
        row = QHBoxLayout()
        setb = QPushButton('Set selected as system default')
        refresh = QPushButton('Refresh detection')
        row.addWidget(setb)
        row.addStretch()
        row.addWidget(refresh)
        l.addLayout(row)

        def setdefault():
            idx = w.indexOfTopLevelItem(w.currentItem()) if w.currentItem() else -1
            if idx < 0:
                return
            _, ext, did = rows[idx]
            if not did:
                return self.err('The application desktop entry was not detected.')
            try:
                mimes = ['text/markdown'] if ext.startswith('.md') else ['application/x-nirupres']
                for mime in mimes:
                    self._set_xdg_default(mime, did)
                self.info('File Associations', f'System default updated to {did}.')
            except Exception as e:
                self.err(e)

        setb.clicked.connect(setdefault)
        refresh.clicked.connect(lambda: (d.accept(), self.file_associations()))
        d.exec()

    def context_lens(self):
        base = self.current_dir()
        facts = []
        gitdir = base / '.git'
        if gitdir.exists():
            facts.append('Git repository · metadata detected')
            head = gitdir / 'HEAD'
            try:
                raw = head.read_text(errors='ignore').strip()
                facts.append(
                    'Branch · ' + (raw.rsplit('/', 1)[-1] if raw.startswith('ref:') else 'detached HEAD')
                )
            except Exception:
                pass
        py = (base / 'pyproject.toml').exists() or (base / 'requirements.txt').exists()
        node = (base / 'package.json').exists()
        if py:
            facts.append(
                'Python project'
                + (
                    ' · virtual environment detected'
                    if any((base / x).exists() for x in ('.venv', 'venv'))
                    else ''
                )
            )
        if node:
            facts.append(
                'Node project' + (' · node_modules present' if (base / 'node_modules').is_dir() else '')
            )
        compose = next(
            (base / x for x in ('compose.yaml', 'compose.yml', 'docker-compose.yml') if (base / x).exists()),
            None,
        )
        if compose:
            facts.append(f'Docker Compose · {compose.name}')
        if (base / 'README.md').exists():
            facts.append('Documentation · README.md')
        try:
            files = [x for x in base.iterdir() if x.is_file()]
            dirs = sum(1 for x in base.iterdir() if x.is_dir())
            size = sum(x.stat().st_size for x in files)
            imgs = sum(1 for x in files if (mimetypes.guess_type(x.name)[0] or '').startswith('image/'))
            media = sum(
                1 for x in files if (mimetypes.guess_type(x.name)[0] or '').startswith(('audio/', 'video/'))
            )
            facts.append(f'Folder · {len(files)} files · {dirs} folders · {human(size)} direct size')
            if files and imgs / len(files) >= 0.5:
                facts.append(f'Image collection · {imgs}/{len(files)} direct files')
            if files and media / len(files) >= 0.5:
                facts.append(f'Media collection · {media}/{len(files)} direct files')
        except Exception:
            pass
        self.info(
            'Context Lens 2.0',
            str(base)
            + '\n\n'
            + ('\n'.join(facts) if facts else 'No special project or media context detected.')
            + '\n\nFast local inspection only. No network calls, daemon or background indexing.',
        )

    def _restore_session_state(self):
        if not self.restore_session:
            return
        p2 = self.s.value('session_pane2', '')
        split = self.s.value('session_split', False, type=bool)
        try:
            left = json.loads(self.s.value('session_left_tabs', '[]') or '[]')
            right = json.loads(self.s.value('session_right_tabs', '[]') or '[]')
            if left:
                self.pane1.restore_tabs(left)
            if split:
                self._show_right_pane(empty=True)
                self.pane2.restore_tabs(right) if right else self.pane2._insert_tab_state(
                    {'path': p2 or str(Path.home()), 'history': [], 'hist': -1, 'pinned': False}
                )
            active = self.s.value('session_active_pane', 'left')
            self.set_active(self.pane2 if split and active == 'right' else self.pane1)
        except Exception:
            if split and p2:
                self.pane2.show()
                self.pane2.close_split.show()
                self.pane2.go(p2, True)

    def closeEvent(self, event):
        if self.operations:
            box = QMessageBox(self)
            box.setWindowTitle('Transfers still running')
            box.setText(f'{len(self.operations)} transfer operation(s) are still running.')
            box.setInformativeText(
                'NIRUORG will not unmount remote locations while a transfer is using them.'
            )
            keep = box.addButton('Keep NIRUORG open', QMessageBox.ButtonRole.AcceptRole)
            cancel = box.addButton('Cancel transfers and close', QMessageBox.ButtonRole.DestructiveRole)
            box.setDefaultButton(keep)
            box.exec()
            if box.clickedButton() is cancel:
                self._close_after_transfers = True
                for worker in list(self.operations):
                    worker.cancel()
                self.status.setText('Cancelling transfers safely…')
                event.ignore()
                return
            event.ignore()
            return
        if self.restore_session:
            self.s.setValue(
                'session_pane1', str(Path.home()) if self.pane1.is_remote() else str(self.pane1.current)
            )
            self.s.setValue(
                'session_pane2', str(Path.home()) if self.pane2.is_remote() else str(self.pane2.current)
            )
            self.s.setValue('session_split', self.pane2.isVisible())
            self.s.setValue('session_left_tabs', json.dumps(self.pane1.export_tabs()))
            self.s.setValue('session_right_tabs', json.dumps(self.pane2.export_tabs()))
            self.s.setValue('session_active_pane', 'right' if self.active is self.pane2 else 'left')
        self._shutdown_remote_resources()
        super().closeEvent(event)

    def copy_path(self):
        items = self.selected()
        text = '\n'.join(str(p) for p in items) if items else str(self.current_dir())
        QApplication.clipboard().setText(text)
        self.status.setText(f'Copied {len(items) if items else 1} path(s)')

    def copy_shell_path(self):
        items = self.selected()
        text = ' '.join(shlex.quote(str(p)) for p in items) if items else shlex.quote(str(self.current_dir()))
        QApplication.clipboard().setText(text)
        self.status.setText('Shell-quoted path copied')

    def new_folder(self):
        n, ok = QInputDialog.getText(self, 'New folder', 'Name:')
        if ok and n.strip():
            try:
                (self.current_dir() / n.strip()).mkdir()
            except Exception as e:
                self.err(e)

    def rename(self):
        s = self.selected()
        if len(s) != 1:
            return
        src = s[0]
        d = NiruDialog(self)
        d.setWindowTitle('Rename')
        d.setMinimumWidth(460)
        l = QVBoxLayout(d)
        e = QLineEdit(src.name)
        l.addWidget(QLabel('New name'))
        l.addWidget(e)
        hint = QLabel(
            'The extension is preserved in the selection. Existing names are rejected before rename.'
        )
        hint.setObjectName('muted')
        hint.setWordWrap(True)
        l.addWidget(hint)
        b = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        [x.setIcon(QIcon()) for x in b.buttons()]
        l.addWidget(b)
        b.accepted.connect(d.accept)
        b.rejected.connect(d.reject)
        stem_end = len(src.stem) if src.suffix else len(src.name)
        e.setSelection(0, stem_end)
        e.setFocus()
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        n = e.text().strip()
        if not n or n == src.name:
            return
        target = src.with_name(n)
        if target.exists():
            return self.err(f'Already exists: {target.name}')
        try:
            src.rename(target)
        except Exception as ex:
            self.err(ex)

    def trash(self):
        for p in self.selected():
            try:
                if not QFile.moveToTrash(str(p)):
                    raise RuntimeError(f'Could not move {p.name} to trash')
            except Exception as e:
                self.err(e)
                break

    def _confirm_permanent_delete(self, count):
        if not self.confirm_delete:
            return True
        return self.confirm(
            'Delete permanently',
            f'Permanently delete {count} item(s)?\n\nThis cannot be undone.',
            'Delete permanently',
        )

    def permanent_delete(self):
        items = list(self.selected())
        if not items:
            return
        if not self._confirm_permanent_delete(len(items)):
            return
        deleted = 0
        for p in items:
            try:
                if p.is_dir() and not p.is_symlink():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                deleted += 1
            except Exception as e:
                self.err(e)
                break
        self.update_status()
        if deleted:
            self.status.setText(f'Permanently deleted {deleted} item(s)')

    def _remember_split_sizes(self, *_):
        if self.pane2.isVisible():
            sizes = self.split.sizes()
            if len(sizes) == 2 and min(sizes) > 0:
                self.s.setValue('split_sizes', sizes)

    def _restore_split_sizes(self):
        raw = self.s.value('split_sizes')
        try:
            vals = [int(x) for x in raw] if isinstance(raw, (list, tuple)) else []
        except Exception:
            vals = []
        self.split.setSizes(vals if len(vals) == 2 and min(vals) > 0 else [1, 1])

    def _start_worker(self, pool, worker, terminal=('done', 'failed')):
        """Start a QRunnable while retaining its Python/QObject signal wrappers.

        PySide does not make QRunnable ownership equivalent to Python wrapper
        ownership. A local-only reference can disappear while a queued signal still
        needs its QObject wrapper. Keep a strong reference until a terminal signal
        has been delivered and one more GUI turn has elapsed.
        """
        worker.setAutoDelete(False)
        self._worker_seq += 1
        key = self._worker_seq
        self._worker_refs[key] = worker
        released = {'queued': False}

        def queue_release(*_):
            if released['queued']:
                return
            released['queued'] = True
            QTimer.singleShot(0, lambda k=key: self._worker_refs.pop(k, None))

        connected = False
        for name in terminal:
            sig = getattr(getattr(worker, 'signals', None), name, None)
            if sig is not None:
                sig.connect(queue_release)
                connected = True
        if not connected:
            raise RuntimeError(f'Worker {type(worker).__name__} has no terminal signal')
        pool.start(worker)
        return worker

    def _run_task(self, label, fn, on_done=None, on_failed=None):
        worker = TaskWorker(fn)

        def done(result):
            if not self._accept_worker_results:
                return
            try:
                if on_done:
                    on_done(result)
                else:
                    self.status.setText(label + ' · done')
            except Exception as error:
                self.err(error)

        def failed(error):
            if not self._accept_worker_results:
                return
            if on_failed:
                on_failed(error)
            else:
                self.err(f'{label} failed: {error}')

        worker.signals.done.connect(done)
        worker.signals.failed.connect(failed)
        self.status.setText(label)
        self._start_worker(self.threadpool, worker, ('done', 'failed'))
        return worker

    def update_local_watch(self):
        watcher = getattr(self, 'local_watcher', None)
        if watcher is None:
            return
        paths = []
        for pane in (getattr(self, 'pane1', None), getattr(self, 'pane2', None)):
            if pane is None or pane.is_remote() or not pane.isVisible():
                continue
            path = Path(pane.current)
            if path.is_dir() and not path_is_mounted(path):
                paths.append(path)
        watcher.set_paths(paths)

    def _local_directory_changed(self, path):
        for pane in (getattr(self, 'pane1', None), getattr(self, 'pane2', None)):
            if pane is None or pane.is_remote():
                continue
            try:
                if os.path.normpath(str(pane.current)) == os.path.normpath(str(path)):
                    pane.model.refresh_soon()
                    self.invalidate_quicklook()
            except Exception:
                pass
        self.update_status()

    def _post_show_startup(self):
        self.startup_trace.mark('window shown / deferred start')
        if self._startup_requested_path:
            QTimer.singleShot(0, lambda: self.pane1.go(self._startup_requested_path))
        else:
            QTimer.singleShot(0, self._restore_session_state)
        QTimer.singleShot(25, self._discover_external_async)

    def _discover_external_async(self):
        # Module-level worker + explicit retention avoids PySide/Shiboken lifetime races.
        w = DiscoveryWorker()

        def done(r):
            if not self._accept_worker_results:
                return
            self._cloud_cache = list(r.get('cloud', []))
            self._devices_cache = sorted(set(r.get('devices', [])))
            self.build_sidebar()
            self.startup_trace.mark('external discovery ready')

        w.signals.done.connect(done)
        self._start_worker(self._remote_probe_pool, w, ('done',))

    def _show_right_pane(self, empty=False):
        if not self.pane2.isVisible():
            self.pane2.show()
            self.pane2.close_split.show()
            self._restore_split_sizes()
        if empty and self.pane2.tabs.count():
            self.pane2._tab_loading = True
            try:
                while self.pane2.tabs.count():
                    self.pane2.tabs.removeTab(0)
                self.pane2._tab_states = []
            finally:
                self.pane2._tab_loading = False

    def _right_tabs_exhausted(self):
        # Zero real tabs in the optional pane means split view is finished.
        self._hidden_right_tabs = None
        self.pane2.hide()
        self.pane2.close_split.hide()
        self.set_active(self.pane1)
        self.pane1.view.setFocus()
        self.update_status()

    def show_right_pane(self):
        self._show_right_pane(empty=False)
        if self.pane2.tabs.count() == 0:
            if self._hidden_right_tabs:
                self.pane2.restore_tabs(self._hidden_right_tabs)
                self._hidden_right_tabs = None
            else:
                self.pane2._insert_tab_state(
                    {'path': str(self.pane1.current), 'history': [], 'hist': -1, 'pinned': False}
                )
        self.set_active(self.pane2)

    def toggle_split(self):
        if self.pane2.isVisible():
            self.close_split(self.pane2)
        else:
            self.show_right_pane()
        self.update_status()

    def close_split(self, pane=None):
        if not self.pane2.isVisible():
            return
        # Hiding a pane is not the same as closing its tabs. Keep its workspace for
        # this process so Ctrl+2 can bring it back exactly as it was.
        self.pane2._sync_tab()
        self._hidden_right_tabs = self.pane2.export_tabs() if self.pane2.tabs.count() else None
        self.pane2.hide()
        self.pane2.close_split.hide()
        self.set_active(self.pane1)
        self.pane1.view.setFocus()
        self.update_status()

    def set_view(self, mode):
        if mode == 'gallery':
            return self.gallery()
        for p in (self.pane1, self.pane2):
            p.view.setIconSize(QSize(20, 20))
            p.view.header().show()
        self.sync_row_heights()

    def terminal_here(self):
        s = self.selected()
        p = s[0] if len(s) == 1 and s[0].is_dir() else self.current_dir()
        pane = self.active
        if not self.terminal or not (Path(self.terminal).exists() or shutil.which(Path(self.terminal).name)):
            return self.err('No terminal configured. Set one in Settings.')
        if pane.is_remote():
            cfg = self._json_setting('servers_json').get(pane.remote_name, {})
            host = cfg.get('host', pane.remote_name)
            user = cfg.get('user', '')
            port = str(cfg.get('port', 22))
            dest = (user + '@' if user else '') + host
            remote = pane.display_path()
            cmd = ['ssh', '-t', '-p', port, dest, f'cd {shlex.quote(remote)} && exec fish -l']
            return (
                run_detached([self.terminal, '-e'] + cmd)
                if 'kitty' in self.terminal
                else run_detached([self.terminal, '-e'] + cmd)
            )
        run_detached(
            [self.terminal, '--directory', str(p)] if 'kitty' in self.terminal else [self.terminal], str(p)
        )

    def localsend(self):
        s = self.selected()
        exe = shutil.which('localsend') or shutil.which('localsend_app')
        if not exe:
            return self.err('LocalSend is not installed or no CLI launcher was found.')
        if s:
            run_detached([exe] + [str(x) for x in s])

    def temporary_split(self):
        path = QFileDialog.getExistingDirectory(self, 'Temporary split', str(self.current_dir()))
        if not path:
            return
        if not self.pane2.isVisible():
            self.pane2.setVisible(True)
        self.pane2.go(path, True)
        self.set_active(self.pane2)
        self.status.setText('Temporary split · Esc or Ctrl+2 when finished')

    def archive_browser(self):
        sel = self.selected()
        if len(sel) != 1:
            return self.err('Select one archive.')
        p = sel[0]
        try:
            if zipfile.is_zipfile(p):
                names = zipfile.ZipFile(p).namelist()
                kind = 'zip'
            elif tarfile.is_tarfile(p):
                names = tarfile.open(p).getnames()
                kind = 'tar'
            else:
                return self.err('This archive format cannot be browsed internally yet.')
        except Exception as e:
            return self.err(e)
        d = NiruDialog(self)
        d.setWindowTitle(f'Archive — {p.name}')
        d.resize(820, 600)
        l = QVBoxLayout(d)
        q = QLineEdit()
        q.setPlaceholderText('Filter archive…')
        w = QListWidget()
        w.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        def fill(t=''):
            w.clear()
            needle = t.casefold()
            for n in names:
                if not needle or needle in n.casefold():
                    w.addItem(n)

        fill()
        q.textChanged.connect(fill)
        l.addWidget(q)
        l.addWidget(w, 1)
        row = QHBoxLayout()
        extract = QPushButton('Extract selected…')
        close = QPushButton('Close')
        row.addWidget(extract)
        row.addStretch()
        row.addWidget(close)
        l.addLayout(row)
        close.clicked.connect(d.reject)

        def do_extract():
            chosen = [x.text() for x in w.selectedItems()]
            if not chosen:
                return
            out = QFileDialog.getExistingDirectory(d, 'Extract selected to', str(self.current_dir()))
            if not out:
                return
            try:
                base = Path(out).resolve()
                if kind == 'zip':
                    safe_extract_zip(p, base, chosen)
                else:
                    safe_extract_tar(p, base, chosen)
                self.status.setText(f'Extracted {len(chosen)} archive item(s)')
                d.accept()
            except Exception as e:
                self.err(e)

        extract.clicked.connect(do_extract)
        d.exec()

    def path_actions(self, path=None):
        p = Path(path or self.current_dir())
        m = QMenu(self)
        op = m.addAction('Open')
        other = m.addAction(self.open_other_label())
        basket = m.addAction('Add to Work Basket')
        m.addSeparator()
        term = m.addAction('Terminal here')
        cp = m.addAction('Copy path')
        sh = m.addAction('Add as Shortcut')
        storage = m.addAction('Storage info')
        act = m.exec(QCursor.pos())
        if act == op:
            self.active.go(p)
        elif act == other:
            if not self.pane2.isVisible():
                self.pane2.show()
                self.pane2.close_split.show()
            target = self.pane2 if self.active is self.pane1 else self.pane1
            target.go(p)
            self.set_active(target)
        elif act == basket:
            self.add_dropzone([p])
        elif act == term:
            run_detached([self.terminal, '--working-directory', str(p)]) if self.terminal and 'kitty' in Path(
                self.terminal
            ).name else self.terminal_here()
        elif act == cp:
            QApplication.clipboard().setText(str(p))
        elif act == sh:
            self.add_shortcuts([str(p)])
        elif act == storage:
            self.storage_view()

    def extract(self):
        s = self.selected()
        if len(s) != 1 or not s[0].is_file():
            return
        p = s[0]
        out = p.parent
        try:
            if zipfile.is_zipfile(p):
                safe_extract_zip(p, out)
            elif tarfile.is_tarfile(p):
                safe_extract_tar(p, out)
            elif shutil.which('7z'):
                subprocess.Popen(['7z', 'x', str(p), f'-o{out}'])
            else:
                raise RuntimeError('Unsupported archive or 7z is not installed.')
        except Exception as e:
            self.err(e)

    def _compress_to_zip(self, items, dest):
        with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
            for p in items:
                if p.is_dir():
                    for f in p.rglob('*'):
                        if f.is_file():
                            z.write(f, f.relative_to(p.parent))
                else:
                    z.write(p, p.name)
        return len(items)

    def compress(self):
        s = self.selected()
        if not s:
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, 'Create ZIP', str(self.current_dir() / 'archive.zip'), 'ZIP (*.zip)'
        )
        if not dest:
            return

        def done(count):
            self.status.setText(f'Created ZIP · {count} item(s) · {Path(dest).name}')

        self._run_task(
            f'Compressing {len(s)} item(s)…',
            lambda: self._compress_to_zip(list(s), Path(dest)),
            done,
            self.err,
        )

    def _file_sha256(self, p):
        h = hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda: f.read(1024 * 1024), b''):
                h.update(b)
        return h.hexdigest()

    def checksum(self):
        s = self.selected()
        if len(s) != 1 or not s[0].is_file():
            return

        def done(digest):
            QApplication.clipboard().setText(digest)
            self.info('SHA-256', digest + '\n\nCopied to clipboard.')

        self._run_task('Calculating SHA-256…', lambda: self._file_sha256(s[0]), done, self.err)

    def bulk_rename(self):
        s = self.selected()
        if len(s) < 2:
            return self.err('Select at least two items.')
        pattern, ok = QInputDialog.getText(
            self, 'Bulk rename', 'Pattern ({name}, {n}, {ext}):', text='{name}-{n}{ext}'
        )
        if not ok:
            return
        try:
            preview = plan_bulk_rename(s, pattern)
        except RenameError as error:
            return self.err(error)
        if not self.confirm(
            'Bulk rename',
            'Rename:\n\n'
            + '\n'.join(f'{a.name} → {b.name}' for a, b in preview[:20])
            + ('\n…' if len(preview) > 20 else '')
            + '\n\nAll targets are checked before the first change.',
            'Rename',
        ):
            return

        def done(count):
            self.invalidate_quicklook()
            self.refresh_current()
            self.status.setText(f'Renamed {count} item(s) atomically')

        self._run_task(
            f'Renaming {len(preview)} item(s)…', lambda: execute_bulk_rename(preview), done, self.err
        )

    def _save_work_basket(self):
        self.dropzone = list(dict.fromkeys(self.dropzone))
        self.s.setValue('work_basket', self.dropzone)
        self.build_sidebar()

    def add_dropzone(self, items=None):
        items = list(items if items is not None else self.selected())
        added = 0
        for p in items:
            sp = str(p)
            if sp not in self.dropzone:
                self.dropzone.append(sp)
                added += 1
        if added:
            self._save_work_basket()
        self.status.setText(f'Work Basket · {len(self.dropzone)} item(s)')

    def show_dropzone(self):
        d = NiruDialog(self)
        d.setWindowTitle(f'Work Basket — {len(self.dropzone)} item(s)')
        d.resize(860, 540)
        l = QVBoxLayout(d)
        intro = QLabel(
            'Temporary working set across local and remote locations. Items are references; removing them here never deletes the original.'
        )
        intro.setObjectName('muted')
        intro.setWordWrap(True)
        l.addWidget(intro)
        w = WorkBasketList()
        w.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        l.addWidget(w, 1)
        states = {}
        metas = {}
        generation = object()
        d._basket_generation = generation

        def populate(rows):
            if not d.isVisible() or getattr(d, '_basket_generation', None) is not generation:
                return
            w.clear()
            states.clear()
            metas.clear()
            for row in rows:
                x = row['path']
                meta = row.get('meta', {})
                state = meta.get('state', 'unavailable')
                states[x] = state
                metas[x] = meta
                p = Path(x)
                endpoint = row.get('endpoint', 'Local')
                mark = {'available': '●', 'offline': '○', 'missing': '×', 'unavailable': '!'}.get(state, '?')
                label = {
                    'available': 'Available',
                    'offline': 'Offline',
                    'missing': 'Missing',
                    'unavailable': 'Unavailable',
                }.get(state, state.title())
                it = QListWidgetItem(f'{mark}  {p.name or x}    ·    {endpoint}    ·    {label}')
                it.setToolTip(x)
                it.setData(Qt.ItemDataRole.UserRole, x)
                w.addItem(it)

        for x in self.dropzone:
            p = Path(x)
            it = QListWidgetItem(f'…  {p.name or x}    ·    Checking…')
            it.setToolTip(x)
            it.setData(Qt.ItemDataRole.UserRole, x)
            w.addItem(it)

        def scan():
            payload = [self._path_endpoint_meta(x) for x in self.dropzone]
            worker = MetadataWorker('basket', payload)
            worker.signals.done.connect(
                lambda r: populate(r.get('rows', [])) if self._accept_worker_results else None
            )
            worker.signals.failed.connect(
                lambda e: self.status.setText('Work Basket metadata unavailable · ' + str(e))
            )
            self._start_worker(self._remote_probe_pool, worker)

        QTimer.singleShot(0, scan)
        row = QHBoxLayout()
        clear = QPushButton('Clear')
        remove = QPushButton('Remove selected')
        missingb = QPushButton('Remove missing')
        collection = QPushButton('Save as Collection')
        archive = QPushButton('Compress…')
        local = QPushButton('LocalSend')
        action = QPushButton('Action…')
        recipe = QPushButton('Recipe…')
        move = QPushButton('Move to active folder')
        send = QPushButton('Copy to active folder')
        for b in (clear, remove, missingb, collection):
            row.addWidget(b)
        row.addStretch()
        for b in (archive, local, action, recipe, move, send):
            row.addWidget(b)
        l.addLayout(row)

        def clearall():
            self.dropzone.clear()
            self._save_work_basket()
            d.accept()

        clear.clicked.connect(clearall)

        def rem():
            for it in list(w.selectedItems()):
                x = it.data(Qt.ItemDataRole.UserRole)
                if x in self.dropzone:
                    self.dropzone.remove(x)
                w.takeItem(w.row(it))
            self._save_work_basket()

        remove.clicked.connect(rem)

        def remove_missing():
            self.dropzone = [x for x in self.dropzone if states.get(x) != 'missing']
            self._save_work_basket()
            d.accept()
            QTimer.singleShot(0, self.show_dropzone)

        missingb.clicked.connect(remove_missing)

        def reveal(it):
            x = it.data(Qt.ItemDataRole.UserRole)
            state = states.get(x)
            if state != 'available':
                return self.status.setText(f'Work Basket · {state or "Checking"}')
            p = Path(x)
            self.active.go(p if metas.get(x, {}).get('dir') else p.parent)
            d.accept()

        w.itemDoubleClicked.connect(reveal)

        def dropped(paths):
            self.add_dropzone([Path(x) for x in paths])
            d.accept()
            QTimer.singleShot(0, self.show_dropzone)

        w.pathsDropped.connect(dropped)

        def staged():
            return [Path(x) for x in self.dropzone if states.get(x) == 'available']

        def snd():
            items = staged()
            if items:
                self.start_transfer(items, self.current_dir(), False)
                d.accept()

        def savecol():
            items = staged()
            if not items:
                return
            name, ok = QInputDialog.getText(d, 'Collection', 'Name:')
            if ok and name.strip():
                data = self._json_setting('collections_json')
                data[name.strip()] = [str(x) for x in items]
                self._save_json('collections_json', data)
                self.build_sidebar()
                self.status.setText(f'Collection saved · {name.strip()}')

        def zipstage():
            items = staged()
            if not items:
                return self.status.setText('Work Basket · no available items selected')
            if any(self._remote_path(x) for x in items):
                return self.err(
                    'Compressing remote Work Basket items directly is disabled because it can block on a network filesystem. Copy them to a local folder first.'
                )
            dest, _ = QFileDialog.getSaveFileName(
                d, 'Create ZIP', str(self.current_dir() / 'staged.zip'), 'ZIP (*.zip)'
            )
            if not dest:
                return
            self.status.setText('Compressing Work Basket…')
            try:
                with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
                    for item in items:
                        if item.is_dir():
                            for f in item.rglob('*'):
                                if f.is_file():
                                    z.write(f, arcname=str(Path(item.name) / f.relative_to(item)))
                        elif item.is_file():
                            z.write(item, arcname=item.name)
                self.status.setText(f'Created · {dest}')
            except Exception as e:
                self.err(e)

        def sendlocal():
            exe = shutil.which('localsend')
            items = staged()
            if not exe:
                return self.err('LocalSend is not installed.')
            if items:
                run_detached([exe] + [str(x) for x in items])
                self.status.setText(f'LocalSend · {len(items)} staged item(s)')

        collection.clicked.connect(savecol)
        archive.clicked.connect(zipstage)
        local.clicked.connect(sendlocal)
        send.clicked.connect(snd)
        move.clicked.connect(
            lambda: (self.start_transfer(staged(), self.current_dir(), True), d.accept())
            if staged()
            else None
        )
        action.clicked.connect(lambda: self.run_niru_action(staged()))
        recipe.clicked.connect(lambda: self.run_recipe(staged()))
        d.exec()

    def compare_panes(self):
        if not self.pane2.isVisible():
            return self.err('Enable Split View first (Ctrl+2).')
        left, right = self.pane1.current, self.pane2.current
        d = NiruDialog(self)
        d.setWindowTitle('Compare Workspace')
        d.resize(1000, 650)
        l = QVBoxLayout(d)
        l.addWidget(
            QLabel(
                f'<b>{self.pane_target_label(self.pane1)}</b>  ↔  <b>{self.pane_target_label(self.pane2)}</b>'
            )
        )
        summary = QLabel('Comparing safely…')
        summary.setObjectName('muted')
        l.addWidget(summary)
        w = QTreeWidget()
        w.setHeaderLabels(['Name', 'Status', 'Left', 'Right'])
        w.setRootIsDecorated(False)
        w.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        l.addWidget(w, 1)
        hint = QLabel(
            'Metadata comparison is asynchronous and remote-safe. Nothing is synchronized automatically; transfers are always explicit.'
        )
        hint.setObjectName('muted')
        hint.setWordWrap(True)
        l.addWidget(hint)
        row = QHBoxLayout()
        recv = QPushButton('← Copy selected')
        send = QPushButton('Copy selected →')
        refresh = QPushButton('Refresh')
        close = QPushButton('Close')
        recv.setEnabled(False)
        send.setEnabled(False)
        row.addWidget(recv)
        row.addWidget(send)
        row.addWidget(refresh)
        row.addStretch()
        row.addWidget(close)
        l.addLayout(row)
        cache = {'left': {}, 'right': {}}

        def render(r):
            if not d.isVisible():
                return
            lm, rm = r.get('left'), r.get('right')
            le, re = r.get('left_error'), r.get('right_error')
            if lm is None or rm is None:
                summary.setText(f'Left: {le or "OK"} · Right: {re or "OK"}')
                return
            cache['left'], cache['right'] = lm, rm
            w.clear()
            counts = {}
            for name in sorted(set(lm) | set(rm), key=str.casefold):
                a, b = lm.get(name), rm.get(name)
                la = ra = '—'
                if a is None:
                    status = 'Right only'
                    ra = 'Folder' if b['dir'] else human(b['size'])
                elif b is None:
                    status = 'Left only'
                    la = 'Folder' if a['dir'] else human(a['size'])
                elif a['dir'] != b['dir']:
                    status = 'Changed'
                elif a['dir']:
                    status = 'Folder'
                    la = ra = 'Folder'
                else:
                    la, ra = human(a['size']), human(b['size'])
                    status = (
                        'Same'
                        if a['size'] == b['size'] and int(a['mtime']) == int(b['mtime'])
                        else (
                            'Newer left'
                            if a['mtime'] > b['mtime']
                            else 'Newer right'
                            if b['mtime'] > a['mtime']
                            else 'Changed'
                        )
                    )
                counts[status] = counts.get(status, 0) + 1
                it = QTreeWidgetItem(w, [name, status, la, ra])
                it.setData(0, Qt.ItemDataRole.UserRole, name)
            w.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for i in range(1, 4):
                w.header().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
            summary.setText(' · '.join(f'{k}: {v}' for k, v in counts.items() if v))
            recv.setEnabled(True)
            send.setEnabled(True)

        def scan():
            summary.setText('Comparing safely…')
            recv.setEnabled(False)
            send.setEnabled(False)
            worker = MetadataWorker(
                'compare', {'left': self._path_endpoint_meta(left), 'right': self._path_endpoint_meta(right)}
            )
            worker.signals.done.connect(render)
            worker.signals.failed.connect(lambda e: summary.setText('Compare failed · ' + str(e)))
            self._start_worker(self._remote_probe_pool, worker)

        def selected_names():
            return [it.data(0, Qt.ItemDataRole.UserRole) for it in w.selectedItems()]

        def transfer(src, dst, side):
            items = [src / n for n in selected_names() if n in cache[side]]
            if not items:
                return self.err('Select one or more items that exist on the source side.')
            self.start_transfer(items, dst, False)

        send.clicked.connect(lambda: transfer(left, right, 'left'))
        recv.clicked.connect(lambda: transfer(right, left, 'right'))
        refresh.clicked.connect(scan)
        close.clicked.connect(d.accept)
        QTimer.singleShot(0, scan)
        d.exec()

    def save_collection(self):
        items = self.selected()
        if not items:
            return self.err('Select one or more files first.')
        name, ok = QInputDialog.getText(self, 'New Collection', 'Name:')
        if not ok or not name.strip():
            return
        data = self.s.value('collections_json', '{}') or '{}'
        try:
            cols = json.loads(data)
        except:
            cols = {}
        cols[name.strip()] = [str(p) for p in items]
        self.s.setValue('collections_json', json.dumps(cols))
        self.status.setText(f'Collection saved · {name.strip()}')

    def open_collection(self):
        try:
            cols = json.loads(self.s.value('collections_json', '{}') or '{}')
        except:
            cols = {}
        if not cols:
            return self.err('No Collections saved yet.')
        name, ok = QInputDialog.getItem(self, 'Collections', 'Collection:', sorted(cols), 0, False)
        if not ok:
            return
        d = NiruDialog(self)
        d.setWindowTitle(f'Collection — {name}')
        d.resize(700, 500)
        l = QVBoxLayout(d)
        w = QListWidget()
        for x in cols[name]:
            p = Path(x)
            meta = self._path_endpoint_meta(x)
            it = QListWidgetItem(f'{p.name or x}   ·   {meta.get("endpoint","Local")}')
            it.setToolTip(str(p))
            it.setData(Qt.ItemDataRole.UserRole, x)
            w.addItem(it)

        def op(it):
            p = Path(it.data(Qt.ItemDataRole.UserRole))
            self.active.go(p.parent)

        w.itemDoubleClicked.connect(op)
        l.addWidget(w)
        d.exec()

    def manage_targets(self):
        data = self._json_setting('targets_json')
        d = NiruDialog(self)
        d.setWindowTitle('Locations')
        d.resize(620, 430)
        l = QVBoxLayout(d)
        w = QListWidget()

        def refresh():
            w.clear()
            for n, p in sorted(data.items()):
                it = QListWidgetItem(f'{n}   ·   {p}')
                it.setData(Qt.ItemDataRole.UserRole, n)
                w.addItem(it)

        refresh()
        l.addWidget(
            QLabel(
                'Saved locations for fast navigation and Send to actions. Locations are intentionally lightweight.'
            )
        )
        l.addWidget(w, 1)
        row = QHBoxLayout()
        add = QPushButton('Add')
        rem = QPushButton('Remove')
        op = QPushButton('Open')
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch()
        row.addWidget(op)
        l.addLayout(row)

        def addone():
            p = QFileDialog.getExistingDirectory(d, 'Target folder', str(Path.home()))
            if not p:
                return
            n, ok = QInputDialog.getText(d, 'Target', 'Name:', text=Path(p).name)
            if ok and n.strip():
                data[n.strip()] = p
                self._save_json('targets_json', data)
                refresh()

        def remove():
            it = w.currentItem()
            if it:
                data.pop(it.data(Qt.ItemDataRole.UserRole), None)
                self._save_json('targets_json', data)
                refresh()

        def openit():
            it = w.currentItem()
            if it:
                self.active.go(data[it.data(Qt.ItemDataRole.UserRole)])
                d.accept()

        add.clicked.connect(addone)
        rem.clicked.connect(remove)
        op.clicked.connect(openit)
        w.itemDoubleClicked.connect(lambda *_: openit())
        d.exec()

    def send_target(self):
        items = self.selected()
        data = self._json_setting('targets_json')
        if not items:
            return self.err('Select one or more items first.')
        if not data:
            return self.manage_targets()
        n, ok = QInputDialog.getItem(self, 'Send to Target', 'Target:', sorted(data), 0, False)
        if ok:
            self.start_transfer(items, Path(data[n]), False)

    def open_workspace_named(self, name):
        ws = self._json_setting('workspaces_json').get(name)
        if not ws:
            return self.err('Workspace no longer exists.')
        left = ws.get('left')
        right = ws.get('right')
        split = bool(ws.get('split', bool(right)))
        if ws.get('left_tabs'):
            self.pane1.restore_tabs(ws['left_tabs'])
        elif left:
            self.pane1.go(left)
        if split:
            self._show_right_pane(empty=True)
            self.pane2.restore_tabs(ws['right_tabs']) if ws.get(
                'right_tabs'
            ) else self.pane2._insert_tab_state(
                {'path': right if right else str(Path.home()), 'history': [], 'hist': -1, 'pinned': False}
            )
            if ws.get('split_sizes'):
                self.split.setSizes([int(x) for x in ws['split_sizes']])
        elif not split:
            self.pane2.hide()
        active = self.pane2 if ws.get('active') == 'right' and self.pane2.isVisible() else self.pane1
        self.set_active(active)
        if ws.get('quicklook', False):
            self.quickdock.show()
        else:
            self.quickdock.hide()
        self.update_status()
        self.status.setText(f'Workspace restored · {name}')

    def manage_workspaces(self):
        data = self._json_setting('workspaces_json')
        d = NiruDialog(self)
        d.setWindowTitle('Workspace Snapshots')
        d.resize(760, 500)
        l = QVBoxLayout(d)
        w = QListWidget()

        def refresh():
            w.clear()
            for n, v in sorted(data.items()):
                right = v.get('right', '') if v.get('split', bool(v.get('right'))) else 'single pane'
                it = QListWidgetItem(f'{n}   ·   {v.get("left","")}   ↔   {right}')
                it.setData(Qt.ItemDataRole.UserRole, n)
                w.addItem(it)

        refresh()
        info = QLabel(
            'Snapshots restore pane locations, split state, active pane and Quick Look. They do not start background services or alter files.'
        )
        info.setWordWrap(True)
        l.addWidget(info)
        l.addWidget(w, 1)
        row = QHBoxLayout()
        save = QPushButton('Save current')
        replace = QPushButton('Update')
        rename = QPushButton('Rename')
        duplicate = QPushButton('Duplicate')
        rem = QPushButton('Remove')
        op = QPushButton('Open')
        row.addWidget(save)
        row.addWidget(replace)
        row.addWidget(rename)
        row.addWidget(duplicate)
        row.addWidget(rem)
        row.addStretch()
        row.addWidget(op)
        l.addLayout(row)

        def snapshot():
            return {
                'left': str(self.pane1.current),
                'right': str(self.pane2.current) if self.pane2.isVisible() else '',
                'left_tabs': self.pane1.export_tabs(),
                'right_tabs': self.pane2.export_tabs(),
                'split': self.pane2.isVisible(),
                'active': 'right' if self.active is self.pane2 else 'left',
                'quicklook': self.quickdock.isVisible(),
                'split_sizes': self.split.sizes(),
            }

        def savecur():
            n, ok = QInputDialog.getText(d, 'Workspace Snapshot', 'Name:')
            if ok and n.strip():
                data[n.strip()] = snapshot()
                self._save_json('workspaces_json', data)
                refresh()
                self.build_sidebar()

        def chosen():
            return w.currentItem().data(Qt.ItemDataRole.UserRole) if w.currentItem() else None

        def updatecur():
            n = chosen()
            if n:
                data[n] = snapshot()
                self._save_json('workspaces_json', data)
                refresh()
                self.status.setText(f'Workspace updated · {n}')

        def renameone():
            n = chosen()
            if not n:
                return
            new, ok = QInputDialog.getText(d, 'Rename Workspace', 'Name:', text=n)
            if ok and new.strip() and new.strip() != n:
                if new.strip() in data:
                    return self.err('A workspace with that name already exists.')
                data[new.strip()] = data.pop(n)
                self._save_json('workspaces_json', data)
                refresh()
                self.build_sidebar()

        def duplicateone():
            n = chosen()
            if not n:
                return
            new, ok = QInputDialog.getText(d, 'Duplicate Workspace', 'Name:', text=n + ' copy')
            if ok and new.strip():
                if new.strip() in data:
                    return self.err('A workspace with that name already exists.')
                data[new.strip()] = dict(data[n])
                self._save_json('workspaces_json', data)
                refresh()
                self.build_sidebar()

        def remove():
            n = chosen()
            if n and self.confirm(
                'Remove Workspace',
                f'Remove workspace snapshot “{n}”?\n\nNo files or folders will be deleted.',
                'Remove',
            ):
                data.pop(n, None)
                self._save_json('workspaces_json', data)
                refresh()
                self.build_sidebar()

        def openit():
            n = chosen()
            if n:
                d.accept()
                self.open_workspace_named(n)

        save.clicked.connect(savecur)
        replace.clicked.connect(updatecur)
        rename.clicked.connect(renameone)
        duplicate.clicked.connect(duplicateone)
        rem.clicked.connect(remove)
        op.clicked.connect(openit)
        w.itemDoubleClicked.connect(lambda *_: openit())
        d.exec()

    def package_inspector(self):
        sel = self.selected()
        p = sel[0] if len(sel) == 1 and sel[0].is_file() else None
        if not p:
            fn, _ = QFileDialog.getOpenFileName(
                self,
                'Inspect package',
                str(self.current_dir()),
                'Archives (*.zip *.tar *.tar.gz *.tgz *.tar.xz *.txz);;All files (*)',
            )
            p = Path(fn) if fn else None
        if not p:
            return
        try:
            names = []
            unpacked = 0
            if zipfile.is_zipfile(p):
                with zipfile.ZipFile(p) as z:
                    bad = z.testzip()
                    infos = z.infolist()
                    names = [x.filename for x in infos]
                    unpacked = sum(x.file_size for x in infos)
                    valid = 'Yes' if bad is None else 'No · corrupt member ' + str(bad)
            elif tarfile.is_tarfile(p):
                with tarfile.open(p) as t:
                    infos = t.getmembers()
                    names = [x.name for x in infos]
                    unpacked = sum(x.size for x in infos if x.isfile())
                    valid = 'Yes'
            else:
                return self.err('Unsupported or invalid archive.')
            roots = sorted({n.strip('/').split('/')[0] for n in names if n.strip('/')})
            rootlabel = roots[0] + '/' if len(roots) == 1 else f'{len(roots)} top-level entries'
            root_ok = len(roots) == 1
            expected = re.sub(r'\.(zip|tar|tar\.gz|tgz|tar\.xz|txz)$', '', p.name, flags=re.I)
            root_match = root_ok and roots[0] == expected
            required_names = {Path(n).name for n in names}
            release_checks = [
                ('Single root directory', root_ok),
                ('Root matches package name', root_match),
                ('README.md present', 'README.md' in required_names),
                ('CHANGELOG.md present', 'CHANGELOG.md' in required_names),
                ('install.sh present', 'install.sh' in required_names),
            ]
            h = hashlib.sha256()
            with p.open('rb') as f:
                for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
                    h.update(chunk)
            digest = h.hexdigest()
            checks = '<br>'.join(('✓ ' if ok else '– ') + name for name, ok in release_checks)
            text = f'<b>{p.name}</b><br><br>Archive valid: {valid}<br>Root: {rootlabel}<br>{checks}<br>Entries: {len(names)}<br>Compressed: {human(p.stat().st_size)}<br>Unpacked: {human(unpacked)}<br><br><b>SHA-256</b><br><tt>{digest}</tt>'
            d = NiruDialog(self)
            d.setWindowTitle('Package Inspector')
            d.resize(650, 400)
            l = QVBoxLayout(d)
            lab = QLabel(text)
            lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lab.setWordWrap(True)
            l.addWidget(lab)
            l.addStretch()
            row = QHBoxLayout()
            cp = QPushButton('Copy SHA-256')
            browse = QPushButton('Browse archive')
            close = QPushButton('Close')
            row.addWidget(cp)
            row.addWidget(browse)
            row.addStretch()
            row.addWidget(close)
            l.addLayout(row)
            cp.clicked.connect(lambda: QApplication.clipboard().setText(digest))
            browse.clicked.connect(lambda: (d.accept(), self.archive_browser()))
            close.clicked.connect(d.accept)
            d.exec()
        except Exception as e:
            self.err('Package inspection failed.\n\n' + str(e))

    def system_diagnostics(self):
        rows = []
        rows.append(('NIRUORG', VERSION, 'Application version'))
        rows.append(('Python', sys.version.split()[0], sys.executable))
        rows.append(('Qt / PySide6', qVersion(), 'Runtime'))
        rows.append(
            ('Session', os.getenv('XDG_SESSION_TYPE', 'unknown'), os.getenv('XDG_CURRENT_DESKTOP', '') or '—')
        )
        for label, path in self.integration_status():
            rows.append((label, 'Available' if path else 'Optional / unavailable', str(path or '—')))
        servers = self._json_setting('servers_json')
        rows.append(
            (
                'Tabs',
                f'{self.pane1.tabs.count()} left · {self.pane2.tabs.count()} right',
                'Per-pane tab workspaces',
            )
        )
        rows.append(
            ('Resumable transfers', 'Available', '.niruorg-part files are retained after cancellation')
        )
        rows.append(
            (
                'Connections',
                str(len(servers)),
                f'{sum(1 for n in servers if path_is_mounted(Path.home()/".local/share/niruorg/mounts"/"".join(c if c.isalnum() or c in "-_ ." else "_" for c in n)))} mounted',
            )
        )
        rows.append(
            (
                'Server config',
                str(self._server_store_path()),
                'Portable server definitions; passwords stay in Secret Service',
            )
        )
        d = NiruDialog(self)
        d.setWindowTitle('System Diagnostics')
        d.resize(780, 560)
        l = QVBoxLayout(d)
        note = QLabel(
            '<b>Safe diagnostic report</b><br>No passwords, tokens, private keys or Secret Service values are included.'
        )
        note.setWordWrap(True)
        l.addWidget(note)
        t = QTreeWidget()
        t.setHeaderLabels(['Component', 'Status', 'Details'])
        t.setRootIsDecorated(False)
        l.addWidget(t, 1)
        for a, b, c in rows:
            QTreeWidgetItem(t, [a, b, c])
        t.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        t.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        t.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        def copy():
            QApplication.clipboard().setText('\n'.join(f'{a}: {b} · {c}' for a, b, c in rows))
            self.status.setText('Diagnostic report copied · secrets excluded')

        row = QHBoxLayout()
        cp = QPushButton('Copy diagnostic report')
        close = QPushButton('Close')
        row.addWidget(cp)
        row.addStretch()
        row.addWidget(close)
        l.addLayout(row)
        cp.clicked.connect(copy)
        close.clicked.connect(d.accept)
        d.exec()

    def toggle_hidden(self):
        for p in (self.pane1, self.pane2):
            p.model.setFilter(p.model.filter() ^ QDir.Filter.Hidden)

    def pin_current(self):
        pins = self.s.value('pins', [], type=list) or []
        p = str(self.current_dir())
        if p not in pins:
            pins.append(p)
            self.s.setValue('pins', pins)
            self.build_sidebar()

    def integration_status(self):
        checks = [
            ('MPV', 'mpv'),
            ('LocalSend', 'localsend'),
            ('fd', 'fd'),
            ('ripgrep', 'rg'),
            ('7-Zip', '7z'),
            ('SSH', 'ssh'),
            ('SSHFS', 'sshfs'),
            ('Secret Service', 'secret-tool'),
            ('Proton Pass CLI · optional', 'pass-cli'),
            ('ffprobe', 'ffprobe'),
            ('rclone', 'rclone'),
            ('NIRUNOTE', 'nirunote'),
            ('NIRUPRES', 'nirupres'),
            ('NIRUWORD', 'niruword'),
        ]
        return [
            (label, shutil.which(cmd) or ('fdfind' if cmd == 'fd' and shutil.which('fdfind') else None))
            for label, cmd in checks
        ]

    def _terminal_command(self, args):
        cmd = ' '.join(shlex.quote(str(x)) for x in args)
        if self.terminal:
            base = Path(self.terminal).name
            if base == 'kitty':
                return run_detached([self.terminal, '--hold', self.shell, '-lc', cmd])
            return run_detached([self.terminal, '-e', self.shell, '-lc', cmd])
        return False

    def integrations(self):
        d = NiruDialog(self)
        d.setWindowTitle('Integrations')
        d.resize(680, 520)
        l = QVBoxLayout(d)
        l.addWidget(
            QLabel(
                '<b>Optional integrations</b><br>Detected on demand; none run as NIRUORG background services.'
            )
        )
        table = QTreeWidget()
        table.setHeaderLabels(['Integration', 'Status', 'Executable'])
        table.setRootIsDecorated(False)
        for label, path in self.integration_status():
            QTreeWidgetItem(table, [label, 'Available' if path else 'Not installed', str(path or '—')])
        table.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        l.addWidget(table, 1)
        proton = QGroupBox('Proton Pass · optional')
        pf = QFormLayout(proton)
        pcli = shutil.which('pass-cli')
        pf.addRow('CLI', QLabel(str(pcli or 'Not installed')))
        pf.addRow('Mode', QLabel('Optional credential/SSH provider · NIRUORG never requires Proton Pass'))
        l.addWidget(proton)
        cloud = Path.home() / 'Nextcloud'
        nc = QGroupBox('Nextcloud sharing')
        f = QFormLayout(nc)
        url = QLineEdit(self.s.value('nextcloud_url', ''))
        user = QLineEdit(self.s.value('nextcloud_user', ''))
        f.addRow('Server URL', url)
        f.addRow('Username', user)
        secret = QPushButton('Store / replace app password…')
        test = QPushButton('Test API')
        row = QHBoxLayout()
        row.addWidget(secret)
        row.addWidget(test)
        f.addRow(row)
        f.addRow(QLabel(f'Local sync folder: {cloud if cloud.exists() else "not detected"}'))
        f.addRow('Status', QLabel(self.nextcloud_status()))
        l.addWidget(nc)

        def store():
            if not shutil.which('secret-tool'):
                return self.err(
                    'secret-tool is not installed. Re-run the installer to add secure credential storage.'
                )
            pw, ok = QInputDialog.getText(
                d, 'Nextcloud app password', 'App password:', QLineEdit.EchoMode.Password
            )
            if ok and pw:

                def store_task():
                    r = subprocess.run(
                        [
                            'secret-tool',
                            'store',
                            '--label=NIRUORG Nextcloud',
                            'application',
                            'niruorg',
                            'service',
                            'nextcloud',
                            'user',
                            user.text().strip(),
                        ],
                        input=pw,
                        text=True,
                        capture_output=True,
                    )
                    if r.returncode:
                        raise RuntimeError(r.stderr or 'Could not store credential.')
                    return True

                self._run_task(
                    'Storing Nextcloud credential…',
                    store_task,
                    lambda _: self.info('Nextcloud', 'App password stored in the system Secret Service.'),
                    self.err,
                )

        def save():
            self.s.setValue('nextcloud_url', url.text().strip().rstrip('/'))
            self.s.setValue('nextcloud_user', user.text().strip())

        def testapi():
            save()
            self._run_task(
                'Testing Nextcloud API…',
                lambda: self._nextcloud_client().capabilities(),
                lambda _: self.info('Nextcloud', 'API connection successful.'),
                self.err,
            )

        secret.clicked.connect(store)
        test.clicked.connect(testapi)
        b = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        b.rejected.connect(d.reject)
        b.clicked.connect(lambda *_: save())
        l.addWidget(b)
        d.exec()
        save()

    def media_info(self, p):
        exe = shutil.which('ffprobe')
        if not exe:
            return ''
        try:
            r = subprocess.run(
                [exe, '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', str(p)],
                text=True,
                capture_output=True,
                timeout=4,
            )
            j = json.loads(r.stdout or '{}')
            fmt = j.get('format', {})
            dur = float(fmt.get('duration', 0) or 0)
            lines = []
            if dur:
                lines.append(f'Duration: {int(dur//60):02d}:{int(dur%60):02d}')
            for st in j.get('streams', [])[:4]:
                typ = st.get('codec_type')
                codec = st.get('codec_name', '?')
                if typ == 'video':
                    lines.append(f'Video: {codec} · {st.get("width","?")}×{st.get("height","?")}')
                elif typ == 'audio':
                    lines.append(
                        f'Audio: {codec} · {st.get("sample_rate","?")} Hz · {st.get("channels","?")} ch'
                    )
            tags = fmt.get('tags', {})
            for k in ('artist', 'album', 'title'):
                if tags.get(k):
                    lines.append(f'{k.title()}: {tags[k]}')
            return '\n'.join(lines)
        except:
            return ''

    def clipboard_inspector(self):
        d = NiruDialog(self)
        d.setWindowTitle('Clipboard')
        d.resize(680, 430)
        l = QVBoxLayout(d)
        w = QListWidget()
        existing = [Path(x) for x in self.clip if Path(x).exists()]
        for p in existing:
            w.addItem(str(p))
        mode = 'Cut' if self.cut_mode else 'Copy'
        l.addWidget(QLabel(f'<b>{mode} clipboard</b> · {len(existing)} item(s)'))
        l.addWidget(w, 1)
        row = QHBoxLayout()
        paste = QPushButton('Paste here')
        clear = QPushButton('Clear')
        row.addWidget(clear)
        row.addStretch()
        row.addWidget(paste)
        l.addLayout(row)
        paste.setEnabled(bool(existing))
        paste.clicked.connect(lambda: (self.paste(), d.accept()))
        clear.clicked.connect(
            lambda: (self.clip.clear(), setattr(self, 'cut_mode', False), d.accept(), self.update_status())
        )
        d.exec()

    def folder_health(self):
        base = self.current_dir()
        issues = []
        counts = {
            'files': 0,
            'folders': 0,
            'symlinks': 0,
            'empty': 0,
            'broken': 0,
            'unreadable': 0,
            'large': 0,
        }
        try:
            for p in base.iterdir():
                try:
                    if p.is_symlink():
                        counts['symlinks'] += 1
                        if not p.exists():
                            counts['broken'] += 1
                            issues.append(('Broken symlink', p.name))
                    elif p.is_dir():
                        counts['folders'] += 1
                        try:
                            if not any(p.iterdir()):
                                counts['empty'] += 1
                                issues.append(('Empty folder', p.name))
                        except PermissionError:
                            counts['unreadable'] += 1
                            issues.append(('Unreadable folder', p.name))
                    else:
                        counts['files'] += 1
                        if not os.access(p, os.R_OK):
                            counts['unreadable'] += 1
                            issues.append(('Unreadable file', p.name))
                        try:
                            if p.stat().st_size >= 1024**3:
                                counts['large'] += 1
                                issues.append(('Large file ≥ 1 GiB', p.name))
                        except OSError:
                            pass
                except OSError as e:
                    issues.append(('Error', f'{p.name}: {e}'))
        except Exception as e:
            return self.err(e)
        d = NiruDialog(self)
        d.setWindowTitle('Folder health')
        d.resize(760, 520)
        l = QVBoxLayout(d)
        l.addWidget(
            QLabel(
                f'<b>{base}</b><br>{counts["folders"]} folders · {counts["files"]} files · {counts["symlinks"]} symlinks'
            )
        )
        w = QTreeWidget()
        w.setHeaderLabels(['Finding', 'Item'])
        w.setRootIsDecorated(False)
        if issues:
            for kind, name in issues:
                QTreeWidgetItem(w, [kind, name])
        else:
            QTreeWidgetItem(w, ['No obvious issues found', 'Direct children checked'])
        w.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        w.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        l.addWidget(w, 1)
        l.addWidget(QLabel('Fast, non-recursive diagnostic. Nothing is changed or deleted.'))
        d.exec()

    def duplicate_finder(self):
        base = self.current_dir()
        dlg = QProgressDialog('Scanning for duplicate files…', 'Cancel', 0, 0, self)
        dlg.setWindowTitle('Find duplicates')
        dlg.setMinimumDuration(0)
        dlg.show()
        by_size = {}
        scanned = 0
        try:
            for root, dirs, files in os.walk(base):
                dirs[:] = [x for x in dirs if x not in ('.git', '.cache', 'node_modules')]
                for name in files:
                    QApplication.processEvents()
                    if dlg.wasCanceled():
                        dlg.close()
                        return
                    p = Path(root) / name
                    try:
                        size = p.stat().st_size
                    except OSError:
                        continue
                    if size:
                        by_size.setdefault(size, []).append(p)
                    scanned += 1
                    if scanned >= 50000:
                        break
                if scanned >= 50000:
                    break
            import hashlib

            groups = []
            for size, paths in by_size.items():
                if len(paths) < 2:
                    continue
                hashes = {}
                for p in paths:
                    QApplication.processEvents()
                    if dlg.wasCanceled():
                        dlg.close()
                        return
                    try:
                        h = hashlib.sha256()
                        with p.open('rb') as f:
                            while True:
                                b = f.read(4 * 1024 * 1024)
                                if not b:
                                    break
                                h.update(b)
                        hashes.setdefault(h.hexdigest(), []).append(p)
                    except OSError:
                        pass
                groups.extend((size, x) for x in hashes.values() if len(x) > 1)
        finally:
            dlg.close()
        d = NiruDialog(self)
        d.setWindowTitle('Duplicates')
        d.resize(900, 600)
        l = QVBoxLayout(d)
        tree = QTreeWidget()
        tree.setHeaderLabels(['File', 'Size', 'Group'])
        tree.setRootIsDecorated(False)
        for gi, (size, paths) in enumerate(groups, 1):
            for p in paths:
                QTreeWidgetItem(tree, [str(p), human(size), str(gi)])
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        l.addWidget(
            QLabel(
                f'{sum(len(x) for _,x in groups)} duplicate file(s) in {len(groups)} verified SHA-256 group(s) · scanned {scanned} files'
            )
        )
        l.addWidget(tree, 1)
        l.addWidget(QLabel('Read-only result. NIRUORG never deletes duplicate candidates automatically.'))
        d.exec()

    def saved_searches(self):
        data = self._json_setting('saved_searches_json')
        d = NiruDialog(self)
        d.setWindowTitle('Saved searches')
        d.resize(700, 470)
        l = QVBoxLayout(d)
        w = QListWidget()

        def refresh():
            w.clear()
            for n, v in sorted(data.items()):
                w.addItem(f'{n}   ·   {v.get("term","")}   ·   {v.get("scope","Current folder")}')

        refresh()
        l.addWidget(QLabel('Saved searches store the query, not an index. They run on demand.'))
        l.addWidget(w, 1)
        row = QHBoxLayout()
        rem = QPushButton('Remove')
        run = QPushButton('Run')
        row.addWidget(rem)
        row.addStretch()
        row.addWidget(run)
        l.addLayout(row)

        def chosen():
            it = w.currentItem()
            if not it:
                return None
            name = it.text().split('   ·   ', 1)[0]
            return name

        def dorun():
            n = chosen()
            if n:
                d.accept()
                self.find_files(data[n])

        def remove():
            n = chosen()
            if n:
                data.pop(n, None)
                self._save_json('saved_searches_json', data)
                refresh()

        run.clicked.connect(dorun)
        rem.clicked.connect(remove)
        w.itemDoubleClicked.connect(lambda *_: dorun())
        d.exec()

    def _action_data(self):
        return self._json_setting('niru_actions_json')

    def _recipe_data(self):
        return self._json_setting('recipes_json')

    def _action_matches(self, cfg, items):
        kind = cfg.get('applies', 'Any')
        if kind == 'Any':
            return True
        if kind == 'Files':
            return bool(items) and all(p.is_file() for p in items)
        if kind == 'Folders':
            return bool(items) and all(p.is_dir() for p in items)
        if kind == 'Images':
            return bool(items) and all(
                (mimetypes.guess_type(p.name)[0] or '').startswith('image/') for p in items
            )
        return True

    def _expand_action(self, cfg, items):
        # Commands are parsed into argv first; no shell=True. Placeholders are
        # expanded as individual arguments, preventing filenames from becoming code.
        argv = shlex.split(cfg.get('command', ''))
        if not argv:
            raise RuntimeError('Action has no command.')
        out = []
        for token in argv:
            if token == '{files}':
                out.extend(str(p) for p in items)
                continue
            p = items[0] if items else self.current_dir()
            out.append(
                token.replace('{file}', str(p))
                .replace('{name}', p.name)
                .replace('{stem}', p.stem)
                .replace('{dir}', str(p if p.is_dir() else p.parent))
            )
        return out

    def _execute_action(self, name, items=None, quiet=False):
        items = list(items if items is not None else self.selected())
        data = self._action_data()
        cfg = data.get(name)
        if not cfg:
            return self.err(f'Unknown action: {name}')
        if not self._action_matches(cfg, items):
            return self.err(f'Action “{name}” does not apply to this selection.')
        try:
            argv = self._expand_action(cfg, items)
            exe = shutil.which(argv[0]) or (argv[0] if Path(argv[0]).exists() else None)
            if not exe:
                raise RuntimeError(f'Executable not found: {argv[0]}')
            argv[0] = exe
            cwd = str(self.current_dir())
            subprocess.Popen(
                argv, cwd=cwd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self.status.setText(f'Action started · {name}')
            return True
        except Exception as e:
            if not quiet:
                self.err(e)
            return False

    def run_niru_action(self, items=None):
        items = list(items if items is not None else self.selected())
        data = self._action_data()
        names = [n for n, c in sorted(data.items()) if self._action_matches(c, items)]
        if not names:
            return self.err('No NIRU Actions match this selection. Create one in Actions → NIRU Actions…')
        name, ok = QInputDialog.getItem(self, 'NIRU Actions', 'Action:', names, 0, False)
        if ok:
            self._execute_action(name, items)

    def manage_niru_actions(self):
        data = self._action_data()
        d = NiruDialog(self)
        d.setWindowTitle('NIRU Actions')
        d.resize(820, 520)
        l = QVBoxLayout(d)
        w = QTreeWidget()
        w.setHeaderLabels(['Name', 'Applies to', 'Command'])
        w.setRootIsDecorated(False)

        def refresh():
            w.clear()
            for n, c in sorted(data.items()):
                QTreeWidgetItem(w, [n, c.get('applies', 'Any'), c.get('command', '')])
            w.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            w.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            w.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        def edit(existing=None):
            cfg = data.get(existing, {}) if existing else {}
            x = NiruDialog(d)
            x.setWindowTitle('Edit NIRU Action' if existing else 'New NIRU Action')
            f = QFormLayout(x)
            name = QLineEdit(existing or '')
            applies = QComboBox()
            applies.addItems(['Any', 'Files', 'Folders', 'Images'])
            applies.setCurrentText(cfg.get('applies', 'Any'))
            cmd = QLineEdit(cfg.get('command', ''))
            cmd.setPlaceholderText('program --option {files}')
            f.addRow('Name', name)
            f.addRow('Applies to', applies)
            f.addRow('Command', cmd)
            hint = QLabel(
                'Placeholders: {files}, {file}, {name}, {stem}, {dir}. Commands run as argv without a shell.'
            )
            hint.setWordWrap(True)
            hint.setObjectName('muted')
            f.addRow(hint)
            b = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            [z.setIcon(QIcon()) for z in b.buttons()]
            b.accepted.connect(x.accept)
            b.rejected.connect(x.reject)
            f.addRow(b)
            if x.exec() != QDialog.DialogCode.Accepted:
                return
            n = name.text().strip()
            c = cmd.text().strip()
            if not n or not c:
                return
            if existing and existing != n:
                data.pop(existing, None)
            data[n] = {'applies': applies.currentText(), 'command': c}
            self._save_json('niru_actions_json', data)
            refresh()

        row = QHBoxLayout()
        add = QPushButton('New…')
        ed = QPushButton('Edit…')
        rem = QPushButton('Remove')
        close = QPushButton('Close')
        row.addWidget(add)
        row.addWidget(ed)
        row.addWidget(rem)
        row.addStretch()
        row.addWidget(close)
        l.addWidget(QLabel('Reusable, selection-aware commands. Nothing runs in the background.'))
        l.addWidget(w, 1)
        l.addLayout(row)
        refresh()

        def chosen():
            return w.currentItem().text(0) if w.currentItem() else None

        add.clicked.connect(lambda: edit())
        ed.clicked.connect(lambda: edit(chosen()) if chosen() else None)
        rem.clicked.connect(
            lambda: (data.pop(chosen(), None), self._save_json('niru_actions_json', data), refresh())
            if chosen()
            else None
        )
        close.clicked.connect(d.accept)
        w.itemDoubleClicked.connect(lambda *_: edit(chosen()))
        d.exec()

    def run_recipe(self, items=None):
        items = list(items if items is not None else self.selected())
        recipes = self._recipe_data()
        if not recipes:
            return self.err('No Recipes yet. Create one in Actions → Recipes…')
        name, ok = QInputDialog.getItem(self, 'Recipes', 'Recipe:', sorted(recipes), 0, False)
        if not ok:
            return
        steps = recipes.get(name, [])
        actions = self._action_data()
        missing = [x for x in steps if x not in actions]
        if missing:
            return self.err('Recipe references missing action(s): ' + ', '.join(missing))
        if not self.confirm(
            'Run Recipe',
            f'Run “{name}” on {len(items)} selected item(s)?\n\n'
            + '\n'.join(f'{i+1}. {x}' for i, x in enumerate(steps)),
            'Run',
        ):
            return
        for step in steps:
            if not self._execute_action(step, items):
                break

    def manage_recipes(self):
        actions = self._action_data()
        data = self._recipe_data()
        if not actions:
            return self.err('Create at least one NIRU Action first.')
        d = NiruDialog(self)
        d.setWindowTitle('Recipes')
        d.resize(760, 500)
        l = QVBoxLayout(d)
        w = QTreeWidget()
        w.setHeaderLabels(['Recipe', 'Steps'])
        w.setRootIsDecorated(False)

        def refresh():
            w.clear()
            for n, steps in sorted(data.items()):
                QTreeWidgetItem(w, [n, ' → '.join(steps)])
            w.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            w.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        def edit(existing=None):
            name, ok = QInputDialog.getText(d, 'Recipe', 'Name:', text=existing or '')
            if not ok or not name.strip():
                return
            current = data.get(existing, []) if existing else []
            choices = list(sorted(actions))
            selected = []
            while True:
                a, ok = QInputDialog.getItem(
                    d, 'Recipe steps', 'Add action (Cancel when finished):', choices, 0, False
                )
                if not ok:
                    break
                selected.append(a)
            if not selected and current:
                selected = current
            if not selected:
                return
            if existing and existing != name.strip():
                data.pop(existing, None)
            data[name.strip()] = selected
            self._save_json('recipes_json', data)
            refresh()

        row = QHBoxLayout()
        add = QPushButton('New…')
        ed = QPushButton('Edit…')
        rem = QPushButton('Remove')
        close = QPushButton('Close')
        row.addWidget(add)
        row.addWidget(ed)
        row.addWidget(rem)
        row.addStretch()
        row.addWidget(close)
        l.addWidget(
            QLabel(
                'Recipes chain existing NIRU Actions. A confirmation preview is always shown before execution.'
            )
        )
        l.addWidget(w, 1)
        l.addLayout(row)
        refresh()

        def chosen():
            return w.currentItem().text(0) if w.currentItem() else None

        add.clicked.connect(lambda: edit())
        ed.clicked.connect(lambda: edit(chosen()) if chosen() else None)
        rem.clicked.connect(
            lambda: (data.pop(chosen(), None), self._save_json('recipes_json', data), refresh())
            if chosen()
            else None
        )
        close.clicked.connect(d.accept)
        d.exec()

    def find_files(self, preset=None):
        d = NiruDialog(self)
        d.setWindowTitle('Search Workspace')
        d.resize(980, 680)
        outer = QVBoxLayout(d)
        top = QGridLayout()
        q = QLineEdit()
        q.setPlaceholderText('File name, wildcard or text…')
        scope = QComboBox()
        scope.addItems(['Current folder', 'Home'])
        content = QCheckBox('Search file contents')
        hidden = QCheckBox('Include hidden')
        preset = preset or {}
        q.setText(preset.get('term', ''))
        scope.setCurrentText(preset.get('scope', 'Current folder'))
        content.setChecked(bool(preset.get('content', False)))
        hidden.setChecked(bool(preset.get('hidden', False)))
        top.addWidget(QLabel('Search'), 0, 0)
        top.addWidget(q, 0, 1, 1, 3)
        top.addWidget(QLabel('Scope'), 1, 0)
        top.addWidget(scope, 1, 1)
        top.addWidget(content, 1, 2)
        top.addWidget(hidden, 1, 3)
        outer.addLayout(top)
        results = QTreeWidget()
        results.setHeaderLabels(['Name', 'Folder', 'Type'])
        results.setRootIsDecorated(False)
        results.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        outer.addWidget(results, 1)
        status = QLabel('Ready · searches run in the background')
        status.setObjectName('muted')
        outer.addWidget(status)
        row = QHBoxLayout()
        go = QPushButton('Search')
        cancel = QPushButton('Cancel')
        cancel.setEnabled(False)
        saveq = QPushButton('Save search')
        addbasket = QPushButton('Add to Work Basket')
        openb = QPushButton('Open')
        folderb = QPushButton('Open containing folder')
        row.addWidget(go)
        row.addWidget(cancel)
        row.addWidget(saveq)
        row.addWidget(addbasket)
        row.addStretch()
        row.addWidget(folderb)
        row.addWidget(openb)
        outer.addLayout(row)
        state = {'worker': None, 'generation': 0, 'count': 0}

        def add_result(raw):
            p = Path(raw)
            try:
                typ = 'Folder' if p.is_dir() else (mimetypes.guess_type(p.name)[0] or 'File')
            except:
                typ = 'File'
            it = QTreeWidgetItem(results, [p.name, str(p.parent), typ])
            it.setData(0, Qt.ItemDataRole.UserRole, str(p))
            results.addTopLevelItem(it)

        def runsearch():
            term = q.text().strip()
            if not term:
                return
            if state['worker']:
                state['worker'].cancel()
            state['generation'] += 1
            gen = state['generation']
            state['count'] = 0
            results.clear()
            base = self.current_dir() if scope.currentIndex() == 0 else Path.home()
            worker = SearchWorker(base, term, content.isChecked(), hidden.isChecked(), gen)
            state['worker'] = worker
            go.setEnabled(False)
            cancel.setEnabled(True)
            status.setText(f'Searching · {base}')

            def progress(done, total, raw):
                if gen != state['generation']:
                    return
                state['count'] = done
                add_result(raw)
                status.setText(f'Searching… {done} result(s) · Cancel is available')

            def done(payload):
                if payload.get('generation') != state['generation']:
                    return
                state['worker'] = None
                go.setEnabled(True)
                cancel.setEnabled(False)
                status.setText(
                    ('Cancelled · ' if payload.get('cancelled') else '') + f'{state["count"]} result(s)'
                )

            def failed(msg):
                if gen != state['generation']:
                    return
                state['worker'] = None
                go.setEnabled(True)
                cancel.setEnabled(False)
                status.setText('Search failed')
                self.err(msg)

            worker.signals.progress.connect(progress)
            worker.signals.done.connect(done)
            worker.signals.failed.connect(failed)
            self._start_worker(self.threadpool, worker)

        def cancelsearch():
            if state['worker']:
                state['worker'].cancel()
                status.setText('Cancelling…')

        def selected_paths():
            return [Path(it.data(0, Qt.ItemDataRole.UserRole)) for it in results.selectedItems()]

        def selected_path():
            it = results.currentItem()
            return Path(it.data(0, Qt.ItemDataRole.UserRole)) if it else None

        def openone():
            p = selected_path()
            if p:
                self.active.go(p) if p.is_dir() else QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

        def containing():
            p = selected_path()
            if p:
                self.active.go(p.parent)
                d.accept()

        def basket():
            paths = selected_paths()
            if not paths:
                return
            self.add_dropzone(paths)

        def savesearch():
            term = q.text().strip()
            if not term:
                return
            name, ok = QInputDialog.getText(d, 'Save search', 'Name:', text=term)
            if ok and name.strip():
                data = self._json_setting('saved_searches_json')
                data[name.strip()] = {
                    'term': term,
                    'scope': scope.currentText(),
                    'content': content.isChecked(),
                    'hidden': hidden.isChecked(),
                }
                self._save_json('saved_searches_json', data)
                status.setText(f'Saved search · {name.strip()}')

        saveq.clicked.connect(savesearch)
        go.clicked.connect(runsearch)
        cancel.clicked.connect(cancelsearch)
        addbasket.clicked.connect(basket)
        q.returnPressed.connect(runsearch)
        openb.clicked.connect(openone)
        folderb.clicked.connect(containing)
        results.itemDoubleClicked.connect(lambda *_: openone())
        d.finished.connect(lambda *_: state['worker'].cancel() if state['worker'] else None)
        q.setFocus()
        d.exec()

    def info(self, title, text):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setText(str(text))
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()

    def confirm(self, title, text, accept='Continue'):
        box = NiruDialog(self)
        box.setWindowTitle(title)
        lay = QVBoxLayout(box)
        lab = QLabel(str(text))
        lab.setWordWrap(True)
        lay.addWidget(lab)
        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton('Cancel')
        ok = QPushButton(accept)
        ok.setDefault(True)
        ok.setAutoDefault(True)
        cancel.setAutoDefault(False)
        cancel.clicked.connect(box.reject)
        ok.clicked.connect(box.accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)
        QTimer.singleShot(0, ok.setFocus)
        return box.exec() == QDialog.DialogCode.Accepted

    def err(self, e):
        log_error('ui', e)
        box = QMessageBox(self)
        box.setWindowTitle(APP)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setText(str(e))
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()


def main():
    if '--version' in sys.argv:
        print(VERSION)
        return 0
    if '--self-test' in sys.argv:
        assert human(1024) == '1.0 KB'
        assert 'Nord' in THEMES
        assert VERSION == '0.5.1'
        assert ConnectionDiagnosticWorker
        assert hasattr(Main, 'undo_last')
        assert hasattr(FilePane, 'update_breadcrumbs')
        assert hasattr(Main, 'manage_servers')
        assert hasattr(Main, 'open_server_named')
        assert hasattr(Main, 'manage_workspaces')
        assert hasattr(Main, 'manage_targets')
        assert hasattr(Main, 'smart_view')
        assert hasattr(Main, 'operation_history')
        assert hasattr(Main, 'format_dt')
        assert hasattr(Main, 'integrations')
        assert hasattr(Main, 'nextcloud_share')
        assert hasattr(Main, 'media_info')
        assert hasattr(Main, 'niru_player')
        assert hasattr(Main, 'play_audio')
        assert hasattr(Main, 'storage_view')
        assert hasattr(Main, 'permissions_view')
        assert hasattr(Main, 'operation_queue')
        assert hasattr(Main, 'toggle_quicklook')
        assert hasattr(Main, 'compare_panes')
        assert hasattr(Main, 'jump')
        assert hasattr(Main, 'toggle_focus')
        assert hasattr(Main, '_sidebar_section')
        assert hasattr(Main, 'open_workspace_named')
        assert hasattr(Main, 'show_keybindings')
        assert hasattr(Main, 'quick_create')
        assert hasattr(Main, 'refresh_current')
        assert hasattr(Main, 'input_diagnostics')
        assert hasattr(FilePane, 'forward')
        assert hasattr(Main, 'clipboard_inspector')
        assert hasattr(Main, 'folder_health')
        assert hasattr(Main, 'duplicate_finder')
        assert hasattr(Main, 'saved_searches')
        assert hasattr(Main, 'manage_niru_actions')
        assert hasattr(Main, 'manage_recipes')
        assert hasattr(Main, 'run_niru_action')
        assert hasattr(Main, 'run_recipe')
        assert hasattr(Main, 'open_with')
        assert hasattr(Main, 'file_associations')
        assert hasattr(Main, 'context_lens')
        assert hasattr(Main, 'closeEvent')
        assert hasattr(Main, 'manage_clouds')
        assert hasattr(Main, 'open_cloud')
        assert hasattr(Main, 'close_split')
        assert hasattr(SearchWorker, 'cancel')
        assert hasattr(Main, 'all_actions')
        assert hasattr(Main, '_save_work_basket')
        assert hasattr(Main, 'path_actions')
        assert callable(safe_extract_zip)
        assert callable(safe_extract_tar)
        print('NIRUORG self-test OK')
        return 0
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setOrganizationName('NIRU')
    app.setDesktopFileName('niruorg')
    w = Main(sys.argv[1] if len(sys.argv) > 1 else None)
    w.show()
    w.startup_trace.mark('show called')
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
