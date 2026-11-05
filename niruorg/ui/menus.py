"""Main window mixin: menus, keyboard dispatch, keybindings help, command palette and actions."""

import mimetypes
import shutil
from pathlib import Path
from .base import (
    QAction,
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QEvent,
    QHBoxLayout,
    QHeaderView,
    QKeySequence,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QShortcut,
    QSpinBox,
    QTextEdit,
    QTimer,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    Qt,
)  # noqa: F401
from .dialogs import NiruDialog, Prefs  # noqa: F401


class MenuMixin:
    """Main window mixin: menus, keyboard dispatch, keybindings help, command palette and actions."""

    def addact(self, m, text, fn, sc=None, bind=True):
        a = QAction(text, self)
        a.triggered.connect(fn)
        if sc:
            # Browser-reserved keys are handled directly by the file view. Keep their
            # shortcut visible in menus without registering a competing QAction shortcut.
            if bind:
                a.setShortcut(QKeySequence(sc))
                a.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            else:
                a.setText(f'{text}\t{sc}')
        m.addAction(a)
        return a

    def build_menu(self):
        mb = self.menuBar()
        f = mb.addMenu('File')
        self.addact(f, 'New…', self.quick_create, 'Ctrl+N')
        self.addact(f, 'New folder', self.new_folder, 'Ctrl+Shift+N')
        self.addact(f, 'Rename', self.rename, 'F2', False)
        self.addact(f, 'Copy', self.copy, 'Ctrl+C')
        self.addact(f, 'Cut', self.cut, 'Ctrl+X')
        self.addact(f, 'Paste', self.paste, 'Ctrl+V')
        self.addact(f, 'Undo last transfer', self.undo_last, 'Ctrl+Z')
        f.addSeparator()
        self.addact(f, 'Move to Trash', self.trash, 'Delete', False)
        self.addact(f, 'Delete Permanently…', self.permanent_delete, 'Shift+Delete', False)
        self.addact(f, 'Properties', self.properties, 'Alt+Return')
        v = mb.addMenu('View')
        self.addact(v, 'Toggle sidebar', lambda: self.sidebar.setVisible(not self.sidebar.isVisible()), 'Tab')
        self.addact(v, 'Split view', self.toggle_split, 'Ctrl+2')
        self.addact(v, 'New tab', lambda: self.active.new_tab(), 'Ctrl+T')
        self.addact(v, 'Close tab', lambda: self.active.close_tab(self.active.tabs.currentIndex()), 'Ctrl+W')
        self.addact(v, 'Reopen closed tab', lambda: self.active.reopen_closed_tab(), 'Ctrl+Shift+T')
        self.addact(v, 'Next tab', lambda: self.active.next_tab(1), 'Ctrl+Tab')
        self.addact(v, 'Previous tab', lambda: self.active.next_tab(-1), 'Ctrl+Shift+Tab')
        self.addact(v, 'List view', lambda: self.set_view('list'), 'Ctrl+1')
        self.addact(v, 'Gallery view', lambda: self.set_view('gallery'), 'Ctrl+3')
        self.addact(v, 'Show hidden files', self.toggle_hidden, 'Ctrl+H')
        self.addact(v, 'Preview / Inspector', self.preview, 'Space', False)
        self.addact(v, 'Quick Look panel', self.toggle_quicklook, 'F3')
        self.addact(v, 'Slideshow', self.slideshow, 'F11')
        self.addact(v, 'Smart view', self.smart_view, 'Ctrl+4')
        self.addact(v, 'Context summary', self.context_summary, 'Ctrl+I')
        self.addact(v, 'Storage view', self.storage_view)
        self.addact(v, 'Permissions view', self.permissions_view)
        self.addact(v, 'Focus browser', self.toggle_focus, 'F10')
        g = mb.addMenu('Go')
        self.addact(g, 'Home', lambda: self.active.go(str(Path.home())), 'Alt+Home')
        self.addact(g, 'Back', lambda: self.active.back(), 'Alt+Left')
        self.addact(g, 'Forward', lambda: self.active.forward(), 'Alt+Right')
        self.addact(g, 'Parent', lambda: self.active.up(), 'Backspace', False)
        self.addact(g, 'Refresh', self.refresh_current, 'F5', False)
        self.addact(g, 'Location', lambda: self.active.edit_location(), 'Ctrl+L')
        self.addact(g, 'Jump…', self.jump, 'Ctrl+P')
        self.addact(g, 'Add current folder as Shortcut', self.add_current_shortcut, 'Ctrl+Shift+B')
        self.addact(g, 'Manage Shortcuts…', self.manage_shortcuts)
        self.addact(g, 'Pin current folder', self.pin_current)
        self.addact(g, 'Work Basket', self.show_dropzone, 'Ctrl+D')
        self.addact(g, 'Locations', self.manage_targets)
        self.addact(g, 'Workspaces', self.manage_workspaces)
        self.addact(g, 'Servers', self.manage_servers)
        self.addact(g, 'Import connections…', self.import_connections)
        self.addact(g, 'Cloud services…', self.manage_clouds)
        a = mb.addMenu('Actions')
        self.addact(a, 'Actions…', self.actions, 'Ctrl+K')
        self.addact(a, 'Open With…', self.open_with, 'Ctrl+Shift+O')
        self.addact(a, 'Context Lens', self.context_lens, 'Ctrl+Shift+I')
        self.addact(a, 'Open terminal here', self.terminal_here, 'Ctrl+Alt+T')
        self.addact(a, 'Play audio', self.play_audio, 'Ctrl+Shift+P')
        self.addact(a, 'Play with MPV', self.mpv)
        self.addact(a, 'Send with LocalSend', self.localsend)
        self.addact(a, 'Browse archive…', self.archive_browser)
        self.addact(a, 'Inspect package…', self.package_inspector)
        self.addact(a, 'Extract here', self.extract)
        self.addact(a, 'Compress to ZIP', self.compress)
        self.addact(a, 'Calculate checksum', self.checksum)
        self.addact(a, 'Copy path', self.copy_path, 'Ctrl+Shift+C')
        self.addact(a, 'Copy shell-quoted path', self.copy_shell_path)
        self.addact(a, 'Bulk rename', self.bulk_rename)
        self.addact(a, 'Clipboard inspector', self.clipboard_inspector, 'Ctrl+Shift+V')
        self.addact(a, 'Folder health', self.folder_health)
        self.addact(a, 'Find duplicates…', self.duplicate_finder)
        self.addact(a, 'Saved searches…', self.saved_searches)
        self.addact(a, 'NIRU Actions…', self.manage_niru_actions)
        self.addact(a, 'Recipes…', self.manage_recipes)
        self.addact(a, 'Operation queue', self.operation_queue, 'Ctrl+Shift+Q')
        self.addact(a, 'Operation history', self.operation_history, 'Ctrl+Shift+H')
        a.addSeparator()
        self.addact(a, 'Add to Work Basket', self.add_dropzone)
        self.copy_other_action = self.addact(
            a, self.copy_other_label(), self.send_other_pane, 'Ctrl+Shift+Right'
        )
        self.move_other_action = self.addact(
            a, self.move_other_label(), self.move_other_pane, 'Ctrl+Alt+Right'
        )
        self.addact(a, 'Compare panes', self.compare_panes, 'Ctrl+Shift+M')
        self.addact(a, 'Temporary split…', self.temporary_split, 'Ctrl+Alt+2')
        self.addact(a, 'Save selection as Collection', self.save_collection)
        self.addact(a, 'Open Collection', self.open_collection)
        self.addact(a, 'Send to Target…', self.send_target)
        s = mb.addMenu('Settings')
        self.addact(s, 'Preferences…', lambda: Prefs(self).exec())
        self.addact(s, 'Integrations…', self.integrations)
        self.addact(s, 'File Associations…', self.file_associations)
        h = mb.addMenu('Help')
        self.addact(h, 'Keybindings', self.show_keybindings)
        h.addSeparator()
        self.addact(h, 'Input diagnostics…', self.input_diagnostics)
        self.addact(h, 'System diagnostics…', self.system_diagnostics)
        h.addSeparator()
        self.addact(h, 'About NIRUORG', self.show_about)

    def shortcuts(self):
        QShortcut(QKeySequence('/'), self, activated=lambda: self.active.filter.setFocus())
        QShortcut(QKeySequence('Ctrl+F'), self, activated=self.find_files)
        QShortcut(QKeySequence('Ctrl+A'), self, activated=lambda: self.active.view.selectAll())
        QShortcut(QKeySequence('Escape'), self, activated=self.escape_action)

    def _install_browser_shortcuts(self):
        # BrowserTree.keyPressEvent owns browser-reserved keys directly.
        # Keep this method as a compatibility hook; no competing QShortcut objects.
        self.browser_shortcuts = []

    def _trigger_browser_action(self, action, pane):
        # One execution path for keyboard dispatch. Context menus call the same
        # final operations (trash/permanent_delete) directly.
        self.active = pane
        self.shortcut_hits[action] = self.shortcut_hits.get(action, 0) + 1
        if getattr(self, 'input_diag_enabled', False):
            try:
                self.input_diag_path.parent.mkdir(parents=True, exist_ok=True)
                with self.input_diag_path.open('a', encoding='utf-8') as f:
                    f.write(f'dispatch action={action} pane={"1" if pane is self.pane1 else "2"}\n')
            except Exception:
                pass
        if action == 'Shift+Delete':
            self.permanent_delete()
        elif action == 'Delete':
            self.trash()
        elif action == 'F2':
            self.rename()
        elif action == 'F5':
            self.refresh_current()
        elif action == 'Backspace':
            pane.up()
        elif action == 'Return':
            self.open_selected()
        elif action == 'Space':
            self.preview()
        return True

    def _focus_is_text_input(self):
        w = QApplication.focusWidget()
        return isinstance(w, (QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox))

    def _browser_has_focus(self):
        w = QApplication.focusWidget()
        if w is None:
            return False
        panes = (getattr(self, 'pane1', None), getattr(self, 'pane2', None))
        for pane in panes:
            if pane is not None and (w is pane.view or pane.view.isAncestorOf(w)):
                return True
        return False

    def _pane_for_event_target(self, obj):
        # QTreeView keyboard events may target the view itself or its viewport.
        # Resolve the owning pane from the actual receiver instead of relying on
        # whichever pane happened to be active previously.
        # eventFilter can run while QMainWindow is still being constructed, before
        # the file panes exist. Early Qt events must therefore be harmless.
        for pane in (getattr(self, 'pane1', None), getattr(self, 'pane2', None)):
            if pane is None:
                continue
            w = obj
            while w is not None:
                if w is pane.view:
                    return pane
                try:
                    w = w.parentWidget()
                except Exception:
                    break
        return None

    def _normalized_modifiers(self, mods):
        # Ignore platform-specific modifier bits that are irrelevant to these file
        # operations, while preserving Ctrl/Alt/Meta so Shift+Delete is exact.
        mask = (
            Qt.KeyboardModifier.ShiftModifier
            | Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )
        return mods & mask

    def _dispatch_browser_key(self, key, mods, pane=None, execute=True):
        mods = self._normalized_modifiers(mods)
        action = None
        if key == Qt.Key.Key_Delete and mods == Qt.KeyboardModifier.ShiftModifier:
            action = 'Shift+Delete'
        elif key == Qt.Key.Key_Delete and mods == Qt.KeyboardModifier.NoModifier:
            action = 'Delete'
        elif key == Qt.Key.Key_F2 and mods == Qt.KeyboardModifier.NoModifier:
            action = 'F2'
        elif key == Qt.Key.Key_F5 and mods == Qt.KeyboardModifier.NoModifier:
            action = 'F5'
        elif key == Qt.Key.Key_Backspace and mods == Qt.KeyboardModifier.NoModifier:
            action = 'Backspace'
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and mods == Qt.KeyboardModifier.NoModifier:
            action = 'Return'
        elif key == Qt.Key.Key_Space and mods == Qt.KeyboardModifier.NoModifier:
            action = 'Space'
        if not action:
            return False
        if not execute:
            return action
        return self._trigger_browser_action(action, pane or self.active)

    def _input_diag(self, obj, event, pane=None, matched=None):
        if not getattr(self, 'input_diag_enabled', False):
            return
        if event.type() not in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            return
        try:
            self.input_diag_path.parent.mkdir(parents=True, exist_ok=True)
            et = {
                QEvent.Type.ShortcutOverride: 'ShortcutOverride',
                QEvent.Type.KeyPress: 'KeyPress',
                QEvent.Type.KeyRelease: 'KeyRelease',
            }.get(event.type(), str(int(event.type())))
            mods = int(event.modifiers().value)
            key = int(event.key())
            target = type(obj).__name__
            pn = (
                '1'
                if pane is getattr(self, 'pane1', None)
                else ('2' if pane is getattr(self, 'pane2', None) else '-')
            )
            with self.input_diag_path.open('a', encoding='utf-8') as f:
                f.write(
                    f'{et} key={key} modifiers=0x{mods:x} target={target} pane={pn} matched={matched or "-"}\n'
                )
        except Exception:
            pass

    def input_diagnostics(self):
        d = NiruDialog(self)
        d.setWindowTitle('Input diagnostics')
        d.resize(720, 500)
        l = QVBoxLayout(d)
        info = QLabel(
            'Temporary keyboard diagnostics for the NIRUORG file browser.\nNo typed text is recorded; only Qt key codes, modifier flags, event type, target widget and pane.'
        )
        info.setWordWrap(True)
        l.addWidget(info)
        state = QLabel()
        l.addWidget(state)
        out = QPlainTextEdit()
        out.setReadOnly(True)
        l.addWidget(out, 1)

        def refresh():
            state.setText('Recording: ON' if self.input_diag_enabled else 'Recording: OFF')
            try:
                out.setPlainText(self.input_diag_path.read_text(encoding='utf-8')[-20000:])
            except Exception:
                out.setPlainText('No diagnostic events recorded yet.')

        row = QHBoxLayout()
        toggle = QPushButton('Start recording' if not self.input_diag_enabled else 'Stop recording')
        clear = QPushButton('Clear log')
        copy = QPushButton('Copy log')
        refreshb = QPushButton('Refresh')
        row.addWidget(toggle)
        row.addWidget(clear)
        row.addWidget(copy)
        row.addWidget(refreshb)
        row.addStretch(1)
        l.addLayout(row)

        def tog():
            self.input_diag_enabled = not self.input_diag_enabled
            toggle.setText('Stop recording' if self.input_diag_enabled else 'Start recording')
            refresh()

        def clr():
            try:
                self.input_diag_path.unlink(missing_ok=True)
            except Exception:
                pass
            refresh()

        toggle.clicked.connect(tog)
        clear.clicked.connect(clr)
        copy.clicked.connect(lambda: QApplication.clipboard().setText(out.toPlainText()))
        refreshb.clicked.connect(refresh)
        refresh()
        d.exec()

    def eventFilter(self, obj, event):
        # This filter is installed on QApplication, so it sees events for widgets and
        # layouts that are being destroyed (including native Qt file dialogs). Walking
        # a stale wrapper or calling QMainWindow.eventFilter there raises
        # "Internal C++ object already deleted" and previously aborted the FileZilla
        # file picker. The filter is diagnostics-only, so failing open is correct.
        try:
            pane = self._pane_for_event_target(obj)
            if getattr(self, 'input_diag_enabled', False) and event.type() in (
                QEvent.Type.ShortcutOverride,
                QEvent.Type.KeyPress,
                QEvent.Type.KeyRelease,
            ):
                self._input_diag(
                    obj,
                    event,
                    pane,
                    self._dispatch_browser_key(event.key(), event.modifiers(), pane, False)
                    if pane is not None
                    else None,
                )
        except (RuntimeError, ReferenceError):
            pass
        # Do not consume browser key events here. View-owned QShortcuts are the
        # authoritative path; the application filter is diagnostics only.
        return False

    def keybinding_rows(self):
        return [
            ('Files', 'Ctrl+N', 'New file / folder'),
            ('Files', 'Ctrl+Shift+N', 'New folder'),
            ('Files', 'F2', 'Rename'),
            ('Files', 'Ctrl+C', 'Copy'),
            ('Files', 'Ctrl+X', 'Cut'),
            ('Files', 'Ctrl+V', 'Paste'),
            ('Files', 'Delete', 'Move to Trash'),
            ('Files', 'Shift+Delete', 'Delete Permanently…'),
            ('Files', 'Alt+Return', 'Properties'),
            ('Files', 'Ctrl+A', 'Select all'),
            ('Navigation', 'Type a name', 'Jump to the next matching name'),
            ('Navigation', 'Click path bar', 'Type a location'),
            ('Navigation', 'Alt+Left', 'Back'),
            ('Navigation', 'Alt+Right', 'Forward'),
            ('Navigation', 'Backspace', 'Parent folder'),
            ('Navigation', 'Alt+Home', 'Home'),
            ('Navigation', 'Ctrl+L', 'Location'),
            ('Navigation', 'Ctrl+P', 'Jump'),
            ('Navigation', 'F5', 'Refresh'),
            ('Search', '/', 'Filter current folder'),
            ('Search', 'Ctrl+F', 'Find files / content'),
            ('Actions', 'Ctrl+K', 'Command palette'),
            ('Tabs', 'Ctrl+T', 'New tab'),
            ('Tabs', 'Ctrl+W', 'Close tab'),
            ('Tabs', 'Ctrl+Shift+T', 'Reopen closed tab'),
            ('Actions', 'Ctrl+Alt+T', 'Open terminal here'),
            ('Actions', 'Ctrl+Shift+C', 'Copy path'),
            ('Actions', 'Ctrl+Shift+V', 'Clipboard inspector'),
            ('Views', 'Ctrl+1', 'List'),
            ('Views', 'Ctrl+2', 'Split'),
            ('Views', 'Ctrl+3', 'Gallery'),
            ('Views', 'Ctrl+4', 'Smart view'),
            ('Views', 'Space', 'Inspector'),
            ('Views', 'F3', 'Quick Look'),
            ('Views', 'F10', 'Focus browser'),
            ('Views', 'F11', 'Slideshow'),
            ('Views', 'Ctrl+H', 'Hidden files'),
            ('Views', 'Tab', 'Sidebar'),
            ('Organizer', 'Ctrl+D', 'Work Basket'),
            ('Organizer', 'Ctrl+Alt+2', 'Temporary split'),
            ('Organizer', 'Ctrl+Shift+B', 'Shortcut current folder'),
            ('Organizer', 'Ctrl+Shift+Right', 'Send to other pane'),
            ('Organizer', 'Ctrl+Shift+M', 'Compare panes'),
            ('Operations', 'Ctrl+Z', 'Undo transfer'),
            ('Operations', 'Ctrl+Shift+Q', 'Operation queue'),
            ('Operations', 'Ctrl+Shift+H', 'Operation history'),
            ('Media', 'Ctrl+Shift+P', 'Play with MPV'),
        ]

    def show_keybindings(self):
        d = NiruDialog(self)
        d.setWindowTitle('NIRUORG Keybindings')
        d.resize(720, 620)
        l = QVBoxLayout(d)
        q = QLineEdit()
        q.setPlaceholderText('Filter keybindings…')
        tree = QTreeWidget()
        tree.setHeaderLabels(['Category', 'Key', 'Action'])
        tree.setRootIsDecorated(False)
        l.addWidget(q)
        l.addWidget(tree, 1)

        def fill(t=''):
            tree.clear()
            needle = t.casefold().strip()
            for cat, key, desc in self.keybinding_rows():
                if needle and needle not in f'{cat} {key} {desc}'.casefold():
                    continue
                QTreeWidgetItem(tree, [cat, key, desc])
            tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        q.textChanged.connect(fill)
        fill()
        q.setFocus()
        d.exec()

    def jump(self):
        entries = []
        for label, p in [
            ('Home', Path.home()),
            ('Documents', Path.home() / 'Documents'),
            ('Downloads', Path.home() / 'Downloads'),
            ('Pictures', Path.home() / 'Pictures'),
            ('Music', Path.home() / 'Music'),
        ]:
            if p.exists():
                entries.append((label, str(p), 'Place'))
        for n, v in self._json_setting('shortcuts_json').items():
            entries.append((n, v.get('path', '') if isinstance(v, dict) else str(v), 'Shortcut'))
        for p in self.recent_locations:
            if Path(p).exists():
                entries.append((Path(p).name or p, p, 'Recent'))
        for n in self._json_setting('workspaces_json'):
            entries.append((n, '__workspace__:' + n, 'Workspace'))
        d = NiruDialog(self)
        d.setWindowTitle('Jump')
        d.resize(620, 460)
        l = QVBoxLayout(d)
        q = QLineEdit()
        q.setPlaceholderText('Type to jump…')
        w = QTreeWidget()
        w.setHeaderLabels(['Name', 'Type', 'Location'])
        w.setRootIsDecorated(False)
        l.addWidget(q)
        l.addWidget(w, 1)

        def fill(text=''):
            w.clear()
            t = text.casefold().strip()
            for name, target, kind in entries:
                if t and t not in (name + ' ' + target + ' ' + kind).casefold():
                    continue
                it = QTreeWidgetItem(w, [name, kind, target.replace('__workspace__:', '')])
                it.setData(0, Qt.ItemDataRole.UserRole, target)
            w.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            w.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            w.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        def go():
            it = w.currentItem()
            if not it:
                return
            target = it.data(0, Qt.ItemDataRole.UserRole)
            d.accept()
            self.open_workspace_named(target.split(':', 1)[1]) if str(target).startswith(
                '__workspace__:'
            ) else self.active.go(target)

        q.textChanged.connect(fill)
        q.returnPressed.connect(go)
        w.itemDoubleClicked.connect(lambda *_: go())
        fill()
        q.setFocus()
        d.exec()

    def actions(self):
        selected = self.selected()
        one = selected[0] if len(selected) == 1 else None
        entries = []

        def add(label, fn, reason=''):
            entries.append((label, fn, reason))

        if selected:
            add('Open', self.open_selected, 'Selection')
            if one and one.is_file():
                add('Preview / Inspector', self.preview, 'File')
                add('Open With…', self.open_with, 'File')
            add('Add to Work Basket', self.add_dropzone, 'Selection')
            add('Copy path', self.copy_path, 'Selection')
            add('Send to Target…', self.send_target, 'Selection')
            if shutil.which('localsend'):
                add('Send with LocalSend', self.localsend, 'LocalSend available')
            if one and one.is_file() and one.suffix.lower() in ('.zip', '.tar', '.gz', '.tgz', '.xz', '.7z'):
                add('Browse archive…', self.archive_browser, 'Archive')
            if (
                one
                and one.is_file()
                and one.suffix.lower()
                in {'.mp3', '.flac', '.ogg', '.opus', '.m4a', '.aac', '.wav', '.wma', '.ape'}
            ):
                add('Play audio', self.play_audio, 'Configured audio player')
            elif (
                one
                and one.is_file()
                and (mimetypes.guess_type(one.name)[0] or '').startswith('video/')
                and shutil.which('mpv')
            ):
                add('Play with MPV', self.mpv, 'Video')
            for n, cfg in sorted(self._action_data().items()):
                if self._action_matches(cfg, selected):
                    add('NIRU · ' + n, lambda n=n: self._execute_action(n, selected), 'Custom action')
        else:
            add('Find files', self.find_files, 'Current location')
            add('Jump', self.jump, 'Navigation')
            add('Context Lens', self.context_lens, 'Current folder')
            add('Open terminal here', self.terminal_here, 'Current folder')
            add('Work Basket', self.show_dropzone, 'Working set')
            add('Workspace Snapshots', self.manage_workspaces, 'Workspace')
        add('New tab', lambda: self.active.new_tab(), 'Pane')
        add('Close tab', lambda: self.active.close_tab(self.active.tabs.currentIndex()), 'Pane')
        add('All actions…', self.all_actions, 'Full command list')
        d = NiruDialog(self)
        d.setWindowTitle('Intent Actions')
        d.resize(620, 480)
        l = QVBoxLayout(d)
        q = QLineEdit()
        q.setPlaceholderText('Filter actions…')
        w = QTreeWidget()
        w.setHeaderLabels(['Action', 'Why'])
        w.setRootIsDecorated(False)
        l.addWidget(q)
        l.addWidget(w, 1)
        hint = QLabel(
            'Actions are ranked from the current selection and available integrations. Ctrl+K always remains keyboard-first.'
        )
        hint.setWordWrap(True)
        hint.setObjectName('muted')
        l.addWidget(hint)

        def fill(text=''):
            w.clear()
            needle = text.casefold()
            for i, (label, fn, reason) in enumerate(entries):
                if needle and needle not in (label + ' ' + reason).casefold():
                    continue
                it = QTreeWidgetItem(w, [label, reason])
                it.setData(0, Qt.ItemDataRole.UserRole, i)
            w.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            w.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            if w.topLevelItemCount():
                w.setCurrentItem(w.topLevelItem(0))

        def run():
            it = w.currentItem()
            if not it:
                return
            fn = entries[it.data(0, Qt.ItemDataRole.UserRole)][1]
            d.accept()
            fn()

        q.textChanged.connect(fill)
        q.returnPressed.connect(run)
        w.itemDoubleClicked.connect(lambda *_: run())
        fill()
        q.setFocus()
        d.exec()

    def all_actions(self):
        """Keyboard-first searchable command palette; execute only after closing the dialog."""
        items = [
            ('New tab', lambda: self.active.new_tab()),
            ('Close tab', lambda: self.active.close_tab(self.active.tabs.currentIndex())),
            ('Open', self.open_selected),
            ('Open With…', self.open_with),
            ('Context Lens', self.context_lens),
            ('New…', self.quick_create),
            ('Find files', self.find_files),
            ('Jump', self.jump),
            ('Focus browser', self.toggle_focus),
            ('Quick Look panel', self.toggle_quicklook),
            ('Preview / Inspector', self.preview),
            ('Open terminal here', self.terminal_here),
            ('Clipboard inspector', self.clipboard_inspector),
            ('Folder health', self.folder_health),
            ('Find duplicates…', self.duplicate_finder),
            ('Saved searches…', self.saved_searches),
            ('NIRU Actions…', self.manage_niru_actions),
            ('Recipes…', self.manage_recipes),
            ('Operation queue', self.operation_queue),
            ('Operation history', self.operation_history),
            ('Work Basket', self.show_dropzone),
            ('Add to Work Basket', self.add_dropzone),
            ('Compare panes', self.compare_panes),
            ('Workspace Snapshots', self.manage_workspaces),
            ('Servers', self.manage_servers),
            ('Import connections…', self.import_connections),
            ('Inspect package…', self.package_inspector),
            ('System diagnostics…', self.system_diagnostics),
            ('Cloud services…', self.manage_clouds),
            ('Integrations…', self.integrations),
            ('Properties', self.properties),
            ('Keybindings', self.show_keybindings),
        ]
        d = NiruDialog(self)
        d.setWindowTitle('Commands')
        d.resize(530, 490)
        layout = QVBoxLayout(d)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(9)
        query = QLineEdit(d)
        query.setPlaceholderText('Type a command…')
        layout.addWidget(query)
        results = QListWidget(d)
        layout.addWidget(results, 1)
        hint = QLabel('↑ ↓ navigate · Enter run · Esc close', d)
        hint.setObjectName('muted')
        layout.addWidget(hint)

        def refresh(value=''):
            results.clear()
            needle = value.casefold().strip()
            for index, (name, _) in enumerate(items):
                if needle and not all(word in name.casefold() for word in needle.split()):
                    continue
                item = QListWidgetItem(name)
                item.setData(Qt.ItemDataRole.UserRole, index)
                results.addItem(item)
            if results.count():
                results.setCurrentRow(0)

        def activate():
            item = results.currentItem()
            if item is None:
                return
            callback = items[item.data(Qt.ItemDataRole.UserRole)][1]
            d.accept()
            QTimer.singleShot(0, callback)

        def move_selection(delta):
            if results.count():
                results.setCurrentRow((results.currentRow() + delta) % results.count())

        query.textChanged.connect(refresh)
        query.returnPressed.connect(activate)
        results.itemDoubleClicked.connect(lambda *_: activate())
        QShortcut(QKeySequence('Down'), query, activated=lambda: move_selection(1))
        QShortcut(QKeySequence('Up'), query, activated=lambda: move_selection(-1))
        refresh()
        query.setFocus()
        d.exec()
