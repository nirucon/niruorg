"""Main window mixin: the sidebar, its sections and the shortcut manager."""

import json
from pathlib import Path
from .base import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QStandardPaths,
    QVBoxLayout,
    Qt,
    mounted_paths,
    path_is_mounted,
)  # noqa: F401
from .dialogs import NiruDialog  # noqa: F401


class SidebarMixin:
    """Main window mixin: the sidebar, its sections and the shortcut manager."""

    def sidebar_clicked(self, i):
        target = i.data(Qt.ItemDataRole.UserRole)
        if isinstance(target, str) and target.startswith('__section__:'):
            key = target.split(':', 1)[1]
            if key in self.collapsed_sections:
                self.collapsed_sections.remove(key)
            else:
                self.collapsed_sections.add(key)
            self.s.setValue('collapsed_sections', sorted(self.collapsed_sections))
            self.build_sidebar()
            return
        if target == '__dropzone__':
            self.show_dropzone()
            return
        if target == '__cloud_manager__':
            self.manage_clouds()
            return
        if isinstance(target, str) and target.startswith('__cloud__:'):
            self.open_cloud(target.split(':', 1)[1])
            return
        if target == '__server_manager__':
            self.manage_servers()
            return
        if isinstance(target, str) and target.startswith('__server__:'):
            self.open_server_named(target.split(':', 1)[1])
            return
        if target == '__collections__':
            self.open_collection()
            return
        if isinstance(target, str) and target.startswith('__workspace__:'):
            self.open_workspace_named(target.split(':', 1)[1])
            return
        if target:
            self.open_sidebar_location(target, self.active)

    def _sidebar_section(self, key, label, entries, always=False):
        if not entries and not always:
            return
        collapsed = key in self.collapsed_sections
        head = QListWidgetItem(('›  ' if collapsed else '⌄  ') + label)
        head.setToolTip(('Expand ' if collapsed else 'Collapse ') + label.title())
        font = head.font()
        font.setBold(True)
        head.setFont(font)
        head.setData(Qt.ItemDataRole.UserRole, '__section__:' + key)
        head.setData(Qt.ItemDataRole.UserRole + 2, 'section')
        self.sidebar.addItem(head)
        if collapsed:
            return
        for text, target, tip, kind in entries:
            it = QListWidgetItem(text)
            it.setData(Qt.ItemDataRole.UserRole, target)
            if tip:
                it.setToolTip(tip)
            if kind:
                it.setData(Qt.ItemDataRole.UserRole + 1, kind)
            self.sidebar.addItem(it)

    def _standard_sidebar_locations(self):
        # Home is always useful. Other entries are the user's real XDG locations,
        # and only existing directories are shown: no empty Desktop/Public placeholders.
        home = Path.home()
        entries = [('Home', home)]
        seen = {str(home)}
        locations = [
            ('Desktop', QStandardPaths.StandardLocation.DesktopLocation),
            ('Documents', QStandardPaths.StandardLocation.DocumentsLocation),
            ('Downloads', QStandardPaths.StandardLocation.DownloadLocation),
            ('Pictures', QStandardPaths.StandardLocation.PicturesLocation),
            ('Music', QStandardPaths.StandardLocation.MusicLocation),
            ('Videos', QStandardPaths.StandardLocation.MoviesLocation),
            ('Public', QStandardPaths.StandardLocation.PublicShareLocation),
            ('Templates', QStandardPaths.StandardLocation.TemplatesLocation),
        ]
        for label, location in locations:
            raw = QStandardPaths.writableLocation(location)
            if not raw:
                continue
            path = Path(raw)
            try:
                if str(path) == str(home) or not path.is_dir():
                    continue
            except OSError:
                continue
            if str(path) in seen:
                continue
            seen.add(str(path))
            entries.append((label, path))
        return entries

    def build_sidebar(self):
        # Sidebar rendering is metadata-only. Never stat saved paths or FUSE mounts here.
        self.sidebar.clear()
        dz = QListWidgetItem(f'WORK BASKET · {len(self.dropzone)}')
        dz.setToolTip('Persistent working set across folders and sessions')
        dz.setData(Qt.ItemDataRole.UserRole, '__dropzone__')
        self.sidebar.addItem(dz)
        for label, p in self._standard_sidebar_locations():
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, str(p))
            self.sidebar.addItem(it)
        shortcuts = self._json_setting('shortcuts_json')
        entries = []
        for n, v in shortcuts.items():
            path = v.get('path', '') if isinstance(v, dict) else str(v)
            if path:
                entries.append(('↗  ' + n, path, path + '\nUser shortcut', 'shortcut:' + n))
        self._sidebar_section('shortcuts', 'SHORTCUTS', entries, True)
        self._sidebar_section('cloud', 'CLOUD', self._cloud_sidebar_entries(), True)
        pins = self.s.value('pins', [], type=list) or []
        self._sidebar_section('pins', 'PINS', [(Path(p).name or p, p, p, None) for p in pins])
        self._sidebar_section(
            'devices', 'DEVICES', [(Path(p).name or p, p, p, None) for p in self._devices_cache[:20]]
        )
        try:
            cols = json.loads(self.s.value('collections_json', '{}') or '{}')
        except:
            cols = {}
        self._sidebar_section(
            'collections',
            'COLLECTIONS',
            [(f'Collections · {len(cols)}', '__collections__', 'Virtual file collections', None)]
            if cols
            else [],
        )
        targets = self._json_setting('targets_json')
        tentries = []
        for n, v in sorted(targets.items()):
            path = v.get('path', '') if isinstance(v, dict) else str(v)
            tentries.append((n, path or None, path, None))
        self._sidebar_section('targets', 'TARGETS', tentries)
        workspaces = self._json_setting('workspaces_json')
        self._sidebar_section(
            'workspaces',
            'WORKSPACES',
            [(n, '__workspace__:' + n, 'Saved workspace', None) for n in sorted(workspaces)],
        )
        mounts = mounted_paths()
        servers = self._json_setting('servers_json')
        sentries = []
        for n, v in sorted(servers.items()):
            safe = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in n)
            mp = Path.home() / '.local/share/niruorg/mounts' / safe
            mounted = path_is_mounted(mp, mounts)
            proto = v.get('protocol', 'sftp').upper()
            route = {'tailscale': 'Tailscale', 'tailscale-ssh': 'Tailscale SSH'}.get(
                v.get('route', 'direct'), 'Direct'
            )
            status = 'Mounted · checking on open' if mounted else 'Disconnected · click to connect'
            tip = f'{n}\n{proto} · {route}\n{v.get("user","")+"@" if v.get("user") else ""}{v.get("host","")}:{v.get("port",22)}\n{status}'
            sentries.append((('● ' if mounted else '○ ') + n, '__server__:' + n, tip, 'server:' + n))
        sentries.append(
            (
                '+  Add server…',
                '__server_manager__',
                'Add or manage remote connections (SFTP, FTP, FTPS)',
                'server-manager',
            )
        )
        self._sidebar_section('servers', 'SERVERS', sentries, True)

    def add_shortcuts(self, paths):
        data = self._json_setting('shortcuts_json')
        added = 0
        existing = {str(v.get('path', '')) if isinstance(v, dict) else str(v) for v in data.values()}
        for raw in paths:
            p = Path(raw)
            if not p.is_dir() or str(p) in existing:
                continue
            base = p.name or str(p)
            name = base
            n = 2
            while name in data:
                name = f'{base} {n}'
                n += 1
            data[name] = {'path': str(p)}
            existing.add(str(p))
            added += 1
        if added:
            self._save_json('shortcuts_json', data)
            self.build_sidebar()
            self.status.setText(f'Added {added} shortcut(s)')

    def add_current_shortcut(self):
        self.add_shortcuts([str(self.current_dir())])

    def add_selected_shortcut(self):
        dirs = [str(p) for p in self.selected() if p.is_dir()]
        if not dirs:
            return self.err('Select one or more folders to add as shortcuts.')
        self.add_shortcuts(dirs)

    def sidebar_context_menu(self, pos):
        it = self.sidebar.itemAt(pos)
        if not it:
            return
        kind = it.data(Qt.ItemDataRole.UserRole + 1)
        if isinstance(kind, str) and kind.startswith('cloud:'):
            name = kind.split(':', 1)[1]
            target = it.data(Qt.ItemDataRole.UserRole)
            m = QMenu(self)
            op = m.addAction('Open')
            other = m.addAction(self.open_other_label())
            m.addSeparator()
            if name == 'nextcloud':
                act = m.exec(self.sidebar.viewport().mapToGlobal(pos))
                if act == op:
                    self.open_sidebar_location(target, self.active)
                elif act == other:
                    self.open_sidebar_other(target)
                return
            un = m.addAction('Unmount')
            manage = m.addAction('Manage cloud services…')
            act = m.exec(self.sidebar.viewport().mapToGlobal(pos))
            if act == op:
                self.open_cloud(name, self.active)
            elif act == other:
                self.open_cloud(name, self.other_pane(self.active, True))
            elif act == un:
                self.unmount_cloud(name)
            elif act == manage:
                self.manage_clouds()
            return
        if kind == 'cloud-manager':
            self.manage_clouds()
            return
        if kind == 'server-manager':
            self.manage_servers()
            return
        if isinstance(kind, str) and kind.startswith('server:'):
            name = kind.split(':', 1)[1]
            data = self._json_setting('servers_json')
            v = data.get(name, {})
            safe = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in name)
            mp = Path.home() / '.local/share/niruorg/mounts' / safe
            mounted = path_is_mounted(mp)
            proto = v.get('protocol', 'sftp').lower()
            m = QMenu(self)
            op = m.addAction('Open' if mounted else 'Connect / Open')
            other = m.addAction(self.open_other_label())
            m.addSeparator()
            ssh = m.addAction('Open SSH terminal') if proto == 'sftp' else None
            details = m.addAction('Connection details')
            test = m.addAction('Test connection')
            disc = m.addAction('Disconnect') if mounted else None
            m.addSeparator()
            edit = m.addAction('Edit…')
            clone = m.addAction('Duplicate…')
            remove = m.addAction('Remove…')
            act = m.exec(self.sidebar.viewport().mapToGlobal(pos))
            if act == op:
                self.open_server_named(name)
            elif act == other:
                self.open_server_named(name, True)
            elif ssh is not None and act == ssh:
                self.manage_servers(name, 'ssh')
            elif act == details:
                self.manage_servers(name, 'details')
            elif act == test:
                self.manage_servers(name, 'test')
            elif disc is not None and act == disc:
                self.manage_servers(name, 'disconnect')
            elif act == edit:
                self.manage_servers(name, 'edit')
            elif act == clone:
                self.manage_servers(name, 'clone')
            elif act == remove:
                self.manage_servers(name, 'remove')
            return
        target = it.data(Qt.ItemDataRole.UserRole)
        if target and not (isinstance(target, str) and target.startswith('__')):
            m = QMenu(self)
            op = m.addAction('Open')
            other = m.addAction(self.open_other_label())
            rename = remove = None
            if isinstance(kind, str) and kind.startswith('shortcut:'):
                m.addSeparator()
                rename = m.addAction('Rename shortcut…')
                remove = m.addAction('Remove shortcut')
            act = m.exec(self.sidebar.viewport().mapToGlobal(pos))
            if act == op:
                self.open_sidebar_location(target, self.active)
                return
            if act == other:
                self.open_sidebar_other(target)
                return
            if not (isinstance(kind, str) and kind.startswith('shortcut:')):
                return
            old = kind.split(':', 1)[1]
            data = self._json_setting('shortcuts_json')
        else:
            return
        if act == remove:
            data.pop(old, None)
            self._save_json('shortcuts_json', data)
            self.build_sidebar()
        elif act == rename:
            new, ok = QInputDialog.getText(self, 'Rename shortcut', 'Display name:', text=old)
            if ok and new.strip() and new.strip() != old:
                val = data.pop(old, None)
                data[new.strip()] = val
                self._save_json('shortcuts_json', data)
                self.build_sidebar()

    def manage_shortcuts(self):
        data = self._json_setting('shortcuts_json')
        d = NiruDialog(self)
        d.setWindowTitle('Shortcuts')
        d.resize(680, 440)
        l = QVBoxLayout(d)
        w = QListWidget()

        def refresh():
            w.clear()
            for n, v in data.items():
                path = v.get('path', '') if isinstance(v, dict) else str(v)
                it = QListWidgetItem(f'↗  {n}   ·   {path}')
                it.setData(Qt.ItemDataRole.UserRole, n)
                w.addItem(it)

        refresh()
        l.addWidget(
            QLabel(
                'Your shortcuts are references only. Removing one never deletes the folder.\nTip: drag folders from the browser directly into the sidebar.'
            )
        )
        l.addWidget(w, 1)
        row = QHBoxLayout()
        add = QPushButton('Add folder…')
        rename = QPushButton('Rename')
        remove = QPushButton('Remove shortcut')
        row.addWidget(add)
        row.addWidget(rename)
        row.addWidget(remove)
        row.addStretch()
        l.addLayout(row)

        def addone():
            path = QFileDialog.getExistingDirectory(d, 'Add shortcut', str(self.current_dir()))
            if path:
                self.add_shortcuts([path])
                data.clear()
                data.update(self._json_setting('shortcuts_json'))
                refresh()

        def ren():
            it = w.currentItem()
            if not it:
                return
            old = it.data(Qt.ItemDataRole.UserRole)
            new, ok = QInputDialog.getText(d, 'Rename shortcut', 'Display name:', text=old)
            if ok and new.strip() and new.strip() != old:
                data[new.strip()] = data.pop(old)
                self._save_json('shortcuts_json', data)
                refresh()
                self.build_sidebar()

        def rem():
            it = w.currentItem()
            if it:
                data.pop(it.data(Qt.ItemDataRole.UserRole), None)
                self._save_json('shortcuts_json', data)
                refresh()
                self.build_sidebar()

        add.clicked.connect(addone)
        rename.clicked.connect(ren)
        remove.clicked.connect(rem)
        d.exec()

    def open_sidebar_location(self, target, pane=None):
        pane = pane or self.active
        pane.go(target, leave_remote=True)
        self.set_active(pane)

    def open_sidebar_other(self, target):
        pane = self.other_pane(self.active, True)
        self.open_sidebar_location(target, pane)
