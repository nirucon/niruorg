"""Main window mixin: remote connections, mounts, server store, cloud remotes and Nextcloud."""

import xml.etree.ElementTree as ET
import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from .base import (
    NextcloudClient,
    NextcloudError,
    QApplication,
    QCheckBox,
    QComboBox,
    QDate,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QIcon,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QModelIndex,
    QProcess,
    QPushButton,
    QSpinBox,
    QTimer,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    Qt,
    lexical_under,
    log_error,
    mounted_paths,
    path_is_mounted,
    run_detached,
)  # noqa: F401
from .dialogs import NiruDialog  # noqa: F401
from .workers import ConnectionDiagnosticWorker, RemoteProbeWorker  # noqa: F401


class RemoteMixin:
    """Main window mixin: remote connections, mounts, server store, cloud remotes and Nextcloud."""

    def _ssh_agent_environment(self, create=False):
        # Prefer an agent inherited from the desktop/session. ssh-add return code 0
        # (keys loaded) or 1 (agent reachable, no keys) both mean the socket works.
        inherited = {
            k: os.environ.get(k, '') for k in ('SSH_AUTH_SOCK', 'SSH_AGENT_PID') if os.environ.get(k)
        }
        if inherited.get('SSH_AUTH_SOCK') and shutil.which('ssh-add'):
            try:
                r = subprocess.run(
                    ['ssh-add', '-l'],
                    env={**os.environ, **inherited},
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
                if r.returncode in (0, 1):
                    return inherited
            except Exception:
                pass
        if self._private_ssh_agent_sock and Path(self._private_ssh_agent_sock).exists():
            return {
                'SSH_AUTH_SOCK': self._private_ssh_agent_sock,
                'SSH_AGENT_PID': str(self._private_ssh_agent_pid or ''),
            }
        if not create:
            return {}
        agent = shutil.which('ssh-agent')
        if not agent:
            return {}
        state = Path.home() / '.local/state/niruorg'
        state.mkdir(parents=True, exist_ok=True)
        requested_sock = state / f'ssh-agent-{os.getpid()}.sock'
        try:
            requested_sock.unlink(missing_ok=True)
        except Exception:
            pass
        # OpenSSH output differs slightly between distributions/builds. Parse the
        # environment it actually reports instead of assuming the requested socket
        # path exists synchronously. If -a is unsupported/broken, fall back to the
        # agent's native socket location.
        for cmd in ([agent, '-a', str(requested_sock), '-s'], [agent, '-s']):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if r.returncode != 0:
                    continue
                ms = re.search(r'(?:^|[;\n]\s*)SSH_AUTH_SOCK=([^;\n]+)', r.stdout)
                mp = re.search(r'(?:^|[;\n]\s*)SSH_AGENT_PID=(\d+)', r.stdout)
                if not ms or not mp:
                    continue
                sock = ms.group(1).strip().strip("'\"")
                pid = mp.group(1)
                env = {'SSH_AUTH_SOCK': sock, 'SSH_AGENT_PID': pid}
                # The environment printed by ssh-agent is authoritative. Some OpenSSH /
                # distribution combinations return a non-standard ssh-add -l status during
                # the tiny startup window even though the agent is healthy. Rejecting the
                # agent here made Unlock fail before ssh-add could ever ask for a passphrase.
                # Keep the parsed agent and let the interactive ssh-add / subsequent SSH
                # preflight perform the real authentication check.
                self._private_ssh_agent_pid = int(pid)
                self._private_ssh_agent_sock = sock
                return env
            except Exception:
                continue
        return {}

    def _stop_private_ssh_agent(self):
        pid = self._private_ssh_agent_pid
        sock = self._private_ssh_agent_sock
        self._private_ssh_agent_pid = None
        self._private_ssh_agent_sock = None
        if pid:
            try:
                os.kill(int(pid), 15)
            except Exception:
                pass
        if sock:
            try:
                Path(sock).unlink(missing_ok=True)
            except Exception:
                pass

    def _load_mount_journal(self):
        """Load NIRUORG mount ownership metadata without touching any FUSE path."""
        try:
            raw = json.loads(self._mount_journal.read_text()) if self._mount_journal.exists() else {}
            if not isinstance(raw, dict):
                raw = {}
        except Exception:
            raw = {}
        self._orphan_mounts = {str(k): v for k, v in raw.items() if isinstance(v, dict)}

    def _write_mount_journal(self):
        """Persist only mounts created by this process. Atomic replace avoids torn state."""
        try:
            self._mount_journal.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._mount_journal.with_suffix('.tmp')
            payload = {str(k): v for k, v in self._owned_mounts.items()}
            tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
            os.replace(tmp, self._mount_journal)
        except Exception:
            pass

    def _claim_mount(self, path, kind, name):
        """Record ownership only after a mount command succeeded and mountinfo confirms it."""
        mp = os.path.normpath(os.path.abspath(os.path.expanduser(str(path))))
        if not lexical_under(mp, Path.home() / '.local/share/niruorg/mounts'):
            return
        self._owned_mounts[mp] = {
            'pid': os.getpid(),
            'kind': str(kind),
            'name': str(name),
            'created': time.time(),
        }
        self._orphan_mounts.pop(mp, None)
        self._write_mount_journal()

    def _release_mount(self, path):
        mp = os.path.normpath(os.path.abspath(os.path.expanduser(str(path))))
        self._owned_mounts.pop(mp, None)
        self._orphan_mounts.pop(mp, None)
        self._write_mount_journal()

    def _detach_remote_models_for_shutdown(self):
        """Move QFileSystemModel away from FUSE before unmounting owned remotes."""
        home = str(Path.home())
        for pane in (self.pane1, self.pane2):
            if not pane.is_remote():
                continue
            try:
                pane.view.clearSelection()
                pane.view.setRootIndex(QModelIndex())
                pane.model.setRootPath(home)
            except Exception:
                pass
        QApplication.processEvents()

    def _unmount_owned_path(self, path, allow_lazy=True):
        """Bounded best-effort unmount. Never dereference the FUSE mount itself."""
        mp = os.path.normpath(os.path.abspath(os.path.expanduser(str(path))))
        if mp not in self._owned_mounts:
            return True
        if not path_is_mounted(mp):
            self._release_mount(mp)
            return True
        exe = shutil.which('fusermount3') or shutil.which('fusermount') or shutil.which('umount')
        if not exe:
            return False
        base = Path(exe).name
        attempts = [['-u', mp]] if 'fusermount' in base else [[mp]]
        if allow_lazy:
            attempts += [['-uz', mp]] if 'fusermount' in base else [['-l', mp]]
        for args in attempts:
            try:
                r = subprocess.run(
                    [exe] + args,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
                if r.returncode == 0 or not path_is_mounted(mp):
                    self._release_mount(mp)
                    return True
            except subprocess.TimeoutExpired:
                pass
            except Exception:
                pass
        return not path_is_mounted(mp)

    def _cleanup_owned_mounts(self):
        # Snapshot because successful unmount mutates the ownership map.
        for mp in list(self._owned_mounts):
            self._unmount_owned_path(mp, True)

    def _shutdown_remote_resources(self):
        if self._shutdown_done:
            return
        self._shutdown_done = True
        self._accept_worker_results = False
        self._remote_probe_tokens.clear()
        self._remote_probe_pool.clear()
        # Remote workers have hard subprocess timeouts (<=4s). Drain them before
        # detaching/unmounting FUSE so no probe can race shutdown or outlive Main.
        self._remote_probe_pool.waitForDone(4500)
        self._detach_remote_models_for_shutdown()
        self._cleanup_owned_mounts()
        self._stop_private_ssh_agent()

    def _remote_definition_for_path(self, path):
        for name, cfg in self._json_setting('servers_json').items():
            safe = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in name)
            mp = Path.home() / '.local/share/niruorg/mounts' / safe
            if lexical_under(path, mp):
                return (name, cfg.get('protocol', 'sftp'), mp, cfg.get('path', '/'))
        for name in self._cloud_cache:
            mp = self._cloud_mountpoint(name)
            if lexical_under(path, mp):
                return (name, 'CLOUD', mp, '/')
        return None

    def _identify_remote_path(self, pane, path):
        hit = self._remote_definition_for_path(path)
        if not hit:
            return False
        pane.bind_remote(*hit)
        return True

    def _path_endpoint_meta(self, path):
        p = os.path.normpath(os.path.abspath(os.path.expanduser(str(path))))
        hit = self._remote_definition_for_path(Path(p))
        if not hit:
            return {'path': p, 'remote': False, 'mounted': True, 'endpoint': 'Local'}
        name, proto, mp, root = hit
        return {
            'path': p,
            'remote': True,
            'mounted': path_is_mounted(mp),
            'endpoint': name,
            'protocol': proto,
            'mount': str(mp),
        }

    def _remote_path(self, path):
        return bool(self._remote_definition_for_path(Path(os.path.abspath(os.path.expanduser(str(path))))))

    def navigate_remote_async(self, pane, path, push=True, leave_remote=False):
        if not pane.is_remote():
            return False
        self._remote_probe_seq += 1
        token = self._remote_probe_seq
        self._remote_probe_tokens[id(pane)] = token
        pane.state.clear()
        pane.current = Path(os.path.abspath(os.path.expanduser(str(path))))
        pane.path.setText(str(pane.current))
        pane.update_breadcrumbs()
        pane.view.setEnabled(False)
        self.status.setText(f'{pane.remote_name} · Checking…')
        worker = RemoteProbeWorker(token, pane.current, pane.remote_mount)

        def cancel(p=pane, expected=token, name=pane.remote_name):
            if self._remote_probe_tokens.get(id(p)) != expected:
                return
            self._remote_probe_tokens.pop(id(p), None)
            p.view.setEnabled(True)
            p.update_breadcrumbs()
            self.status.setText(f'{name} · Connection cancelled')

        activity = pane.show_activity(f'Connecting to {pane.remote_name}…', cancel)

        def done(result, p=pane, expected=token, ps=push, lr=leave_remote, act=activity):
            if self._remote_probe_tokens.get(id(p)) != expected:
                return
            p.hide_activity(act)
            p.view.setEnabled(True)
            if result.get('ok'):
                p._commit_go(result['path'], ps, lr, True)
                self.status.setText(f'{p.remote_name} · Connected')
            else:
                p.update_breadcrumbs()
                p._sync_tab()
                self.status.setText(f'{p.remote_name} · {result.get("detail","Unavailable")}')
                # U4: show why instead of the previous folder's rows.
                p.model.setRootPath('')
                detail = str(result.get('detail', ''))
                p.show_connection_state(
                    'disconnected' if detail == 'Offline' else 'unreachable',
                    detail if detail not in ('Offline', 'Unavailable') else '',
                )

        worker.signals.done.connect(done)
        self._start_worker(self._remote_probe_pool, worker, ('done',))
        return True

    def _server_store_paths(self):
        primary = Path.home() / 'Nextcloud' / 'Backup' / 'niruorg' / 'servers.json'
        local = (
            Path(os.environ.get('XDG_CONFIG_HOME') or (Path.home() / '.config')) / 'niruorg' / 'servers.json'
        )
        return primary, local

    def _server_store_path(self):
        primary, local = self._server_store_paths()
        # ~/Nextcloud/Backup is the user's synced master location when it exists.
        # Otherwise the same file lives under the local per-user config directory.
        return primary if primary.parent.parent.is_dir() else local

    def _read_server_store(self, path):
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
            data = payload.get('servers', payload) if isinstance(payload, dict) else {}
            return {str(k): dict(v) for k, v in data.items() if isinstance(v, dict)}
        except Exception as e:
            log_error('server-store-read', e)
            return {}

    def _load_servers(self):
        try:
            local = json.loads(self.s.value('servers_json', '{}') or '{}')
        except Exception:
            local = {}
        primary, fallback = self._server_store_paths()
        disk = {}
        if primary.exists():
            disk = self._read_server_store(primary)
        if not disk and fallback.exists():
            disk = self._read_server_store(fallback)
        if not disk:
            return local
        # The synced file is the portable source of truth, but never discard a
        # connection that exists only in this machine's local settings.
        merged = dict(disk)
        for name, cfg in local.items():
            merged.setdefault(name, cfg)
        return merged

    def _write_server_store(self, data):
        path = self._server_store_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {'schema': 1, 'servers': data}
            tmp = path.with_name(path.name + '.tmp')
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        except Exception as e:
            log_error('server-store-write', e)

    def _json_setting(self, key):
        if key == 'servers_json':
            return self._load_servers()
        try:
            return json.loads(self.s.value(key, '{}') or '{}')
        except:
            return {}

    def _save_json(self, key, data):
        self.s.setValue(key, json.dumps(data, ensure_ascii=False))
        if key == 'servers_json':
            self._write_server_store(data)

    def open_server_named(self, name, other_pane=False):
        data = self._json_setting('servers_json')
        v = data.get(name)
        if not v:
            return self.err(f'Connection “{name}” no longer exists.')
        safe = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in name)
        mp = Path.home() / '.local/share/niruorg/mounts' / safe
        source = self.active
        target = source
        if other_pane:
            target = self.pane2 if source is self.pane1 else self.pane1
            if self.pane2.isHidden():
                self.toggle_split()
        self.set_active(target)
        if path_is_mounted(mp):
            target.bind_remote(name, v.get('protocol', 'sftp'), mp, v.get('path', '/'))
            target.go(str(mp))
            return
        self.manage_servers(name, 'connect', target)

    def _store_imported_server_secret(self, name, cfg, password):
        if not password:
            return True
        exe = shutil.which('secret-tool')
        if not exe:
            return False
        attrs = ['application', 'niruorg', 'service', 'server', 'server', name, 'user', cfg.get('user', '')]
        try:
            r = subprocess.run(
                [exe, 'store', '--label=NIRUORG server ' + name] + attrs,
                input=password + '\n',
                text=True,
                capture_output=True,
                timeout=8,
            )
            return r.returncode == 0
        except Exception:
            return False

    def _filezilla_sites(self, path):
        root = ET.parse(path).getroot()
        out = []
        for node in root.findall('.//Server'):

            def val(tag, default=''):
                x = node.find(tag)
                return (x.text or '').strip() if x is not None else default

            host = val('Host')
            name = val('Name') or host
            if not host:
                continue
            try:
                proto_num = int(val('Protocol', '0'))
            except:
                proto_num = 0
            proto = {0: 'ftp', 1: 'sftp', 3: 'ftps-implicit', 4: 'ftps'}.get(
                proto_num, 'sftp' if proto_num == 1 else 'ftp'
            )
            try:
                port = int(val('Port', str(22 if proto == 'sftp' else 21)))
            except:
                port = 22 if proto == 'sftp' else 21
            user = val('User')
            raw = val('Pass')
            enc = node.find('Pass').attrib.get('encoding', '') if node.find('Pass') is not None else ''
            password = ''
            if raw:
                try:
                    password = base64.b64decode(raw).decode() if enc == 'base64' else raw
                except Exception:
                    password = ''
            remote = val('RemoteDir', '/') or '/'
            # FileZilla's RemoteDir may use an internal tokenized format; only keep normal absolute paths.
            if not remote.startswith('/'):
                remote = '/'
            out.append(
                {
                    'name': name,
                    'password': password,
                    'cfg': {
                        'protocol': proto,
                        'route': 'direct',
                        'host': host,
                        'user': user,
                        'port': port,
                        'path': remote,
                        'auth': 'password' if password or proto != 'sftp' else 'auto',
                        'key': '',
                        'remember_password': bool(password),
                        'timeout': 12,
                        'proxyjump': '',
                        'keepalive': 15,
                        'passive': True,
                        'tls_verify': True,
                        'advanced': False,
                    },
                }
            )
        return out

    def _openssh_sites(self, path):
        out = []
        cur = None
        try:
            lines = Path(path).read_text(errors='replace').splitlines()
        except Exception:
            return out
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            k, v = parts[0].lower(), parts[1].strip()
            if k == 'host':
                if cur and cur['name'] and '*' not in cur['name'] and '?' not in cur['name']:
                    out.append(cur)
                cur = {
                    'name': v.split()[0],
                    'password': '',
                    'cfg': {
                        'protocol': 'sftp',
                        'route': 'direct',
                        'host': v.split()[0],
                        'user': '',
                        'port': 22,
                        'path': '/',
                        'auth': 'auto',
                        'key': '',
                        'remember_password': False,
                        'timeout': 12,
                        'proxyjump': '',
                        'keepalive': 15,
                        'passive': True,
                        'tls_verify': True,
                        'advanced': False,
                    },
                }
            elif cur:
                c = cur['cfg']
                if k == 'hostname':
                    c['host'] = v
                elif k == 'user':
                    c['user'] = v
                elif k == 'port':
                    try:
                        c['port'] = int(v)
                    except:
                        pass
                elif k == 'identityfile':
                    c['auth'] = 'key'
                    c['key'] = v
                elif k == 'proxyjump':
                    c['proxyjump'] = v
        if cur and cur['name'] and '*' not in cur['name'] and '?' not in cur['name']:
            out.append(cur)
        return out

    def import_connections(self):
        d = NiruDialog(self)
        d.setWindowTitle('Import Connections')
        d.resize(780, 560)
        l = QVBoxLayout(d)
        intro = QLabel(
            '<b>Import connections</b><br>Import selected sites into NIRUORG. Existing connections are never overwritten silently. FileZilla passwords can be imported into Linux Secret Service; they are not written to NIRUORG settings. Proton Pass is optional and is not required for imports or normal operation.'
        )
        intro.setWordWrap(True)
        l.addWidget(intro)
        tree = QTreeWidget()
        tree.setHeaderLabels(['Import', 'Name', 'Protocol', 'Endpoint', 'Credential'])
        tree.setRootIsDecorated(False)
        l.addWidget(tree, 1)
        found = []

        def load(items, source):
            nonlocal found
            found = []
            tree.clear()
            for x in items:
                x['source'] = source
                found.append(x)
                c = x['cfg']
                it = QTreeWidgetItem(
                    [
                        '✓',
                        x['name'],
                        c['protocol'].upper(),
                        f'{c.get("user","")+"@" if c.get("user") else ""}{c["host"]}:{c["port"]}',
                        'Password'
                        if x.get('password')
                        else ('SSH key' if c.get('key') else 'OpenSSH / Auto'),
                    ]
                )
                it.setCheckState(0, Qt.CheckState.Checked)
                tree.addTopLevelItem(it)
            status.setText(f'{len(found)} connection(s) found · choose the entries to import')

        def filezilla():
            candidates = [
                Path.home() / '.config/filezilla/sitemanager.xml',
                Path.home() / '.filezilla/sitemanager.xml',
            ]
            start = str(next((x for x in candidates if x.exists()), Path.home()))
            fn, _ = QFileDialog.getOpenFileName(
                d, 'Choose FileZilla sitemanager.xml or export', start, 'FileZilla XML (*.xml);;All files (*)'
            )
            if fn:
                try:
                    sites = self._filezilla_sites(fn)
                    if not sites:
                        self.err(
                            'No FileZilla <Server> entries were found.\n\nChoose sitemanager.xml or a FileZilla site export, not the recent-servers-only file.'
                        )
                        return
                    load(sites, 'FileZilla')
                except Exception as e:
                    self.err('Could not read FileZilla XML.\n\n' + str(e))

        def openssh():
            fn, _ = QFileDialog.getOpenFileName(
                d, 'Choose OpenSSH config', str(Path.home() / '.ssh/config'), 'SSH config (*)'
            )
            if fn:
                load(self._openssh_sites(fn), 'OpenSSH')

        def doimport():
            data = self._json_setting('servers_json')
            added = 0
            secrets = 0
            skipped = 0
            for i, x in enumerate(found):
                if tree.topLevelItem(i).checkState(0) != Qt.CheckState.Checked:
                    continue
                name = x['name']
                base = name
                n = 2
                while name in data:
                    name = f'{base} {n}'
                    n += 1
                cfg = dict(x['cfg'])
                pw = x.get('password', '')
                if pw:
                    if shutil.which('secret-tool'):
                        cfg['remember_password'] = True
                        if self._store_imported_server_secret(name, cfg, pw):
                            secrets += 1
                        else:
                            cfg['remember_password'] = False
                    else:
                        cfg['remember_password'] = False
                data[name] = cfg
                added += 1
            self._save_json('servers_json', data)
            self.build_sidebar()
            status.setText(f'Imported {added} connection(s) · {secrets} password(s) stored in Secret Service')
            if added:
                self.info(
                    'Import complete',
                    f'Imported {added} connection(s).\n\nPasswords stored securely: {secrets}.\nExisting connections were preserved; duplicate names were renamed.',
                )

        buttons = QHBoxLayout()
        fz = QPushButton('FileZilla XML…')
        ssh = QPushButton('OpenSSH config…')
        imp = QPushButton('Import selected')
        close = QPushButton('Close')
        buttons.addWidget(fz)
        buttons.addWidget(ssh)
        buttons.addStretch()
        buttons.addWidget(imp)
        buttons.addWidget(close)
        l.addLayout(buttons)
        status = QLabel('Choose an import source.')
        status.setObjectName('muted')
        l.addWidget(status)
        fz.clicked.connect(filezilla)
        ssh.clicked.connect(openssh)
        imp.clicked.connect(doimport)
        close.clicked.connect(d.reject)
        d.exec()

    def manage_servers(self, initial_name=None, initial_action=None, target_pane=None):
        target_pane = target_pane or self.active
        data = self._json_setting('servers_json')
        d = NiruDialog(self)
        d.setWindowTitle('Connections')
        d.resize(900, 620)
        l = QVBoxLayout(d)
        info = QLabel(
            '<b>Connections</b><br>Add a server once, then click it in the sidebar whenever you want to browse it. SFTP is recommended for SSH-capable servers. Tailscale works with the same SFTP/SSH connection using a MagicDNS name or 100.x address.'
        )
        info.setWordWrap(True)
        l.addWidget(info)
        w = QListWidget()
        l.addWidget(w, 1)
        status = QLabel('Ready')
        status.setWordWrap(True)
        status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        l.addWidget(status)
        row = QHBoxLayout()
        add = QPushButton('Add connection')
        importb = QPushButton('Import…')
        edit = QPushButton('Edit…')
        clone = QPushButton('Duplicate…')
        rem = QPushButton('Remove…')
        test = QPushButton('Test')
        diagnose = QPushButton('Diagnose…')
        details = QPushButton('Details')
        unlock = QPushButton('Unlock SSH key…')
        ssh = QPushButton('SSH terminal')
        disconnect = QPushButton('Disconnect')
        connect = QPushButton('Connect / Browse')
        cancel = QPushButton('Cancel operation')
        cancel.setObjectName('cancelOperation')
        cancel.setEnabled(False)
        close = QPushButton('Close')
        close.clicked.connect(d.reject)
        for x in (add, importb, edit, clone, rem):
            row.addWidget(x)
        row.addStretch()
        for x in (test, diagnose, details, unlock, ssh, disconnect, connect, cancel, close):
            row.addWidget(x)
        l.addLayout(row)
        state = {
            'proc': None,
            'timer': None,
            'action': '',
            'name': '',
            'mount': None,
            'tmp': None,
            'retry': None,
        }
        session_passwords = {}

        def safe_name(n):
            return ''.join(c if c.isalnum() or c in '-_.' else '_' for c in n)

        def mountpoint(n):
            return Path.home() / '.local/share/niruorg/mounts' / safe_name(n)

        def protocol(v):
            return v.get('protocol', 'sftp').lower()

        def auth(v):
            return v.get('auth', 'auto').lower()

        def refresh(select=None):
            w.clear()
            for n, v in sorted(data.items()):
                mounted = path_is_mounted(mountpoint(n))
                mark = '●' if mounted else '○'
                proto = protocol(v).upper()
                av = auth(v)
                al = {'auto': 'OpenSSH / Auto', 'key': 'SSH key', 'password': 'Password'}.get(av, av)
                route = {'direct': 'Direct', 'tailscale': 'Tailscale', 'tailscale-ssh': 'Tailscale SSH'}.get(
                    v.get('route', 'direct'), 'Direct'
                )
                endpoint = (
                    f'{v.get("user")}@' if v.get('user') else ''
                ) + f'{v.get("host","")}:{v.get("port",22)}'
                it = QListWidgetItem(f'{mark}  {n}    {proto} · {route}    {endpoint}    {al}')
                it.setData(Qt.ItemDataRole.UserRole, n)
                it.setToolTip(
                    f'{proto} · {route}\n{endpoint}\nRemote folder: {v.get("path","/")}\nAuthentication: {al}'
                )
                w.addItem(it)
                if select == n:
                    w.setCurrentItem(it)

        def current():
            it = w.currentItem()
            n = it.data(Qt.ItemDataRole.UserRole) if it else None
            return (n, data.get(n)) if n else (None, None)

        def update_actions():
            n, v = current()
            has = bool(v)
            busy = bool(state.get('proc'))
            for b in (edit, clone, rem, test, diagnose, details, unlock, ssh, disconnect, connect):
                b.setEnabled(has and not busy)
            if v:
                ssh.setEnabled(not busy and protocol(v) == 'sftp')
                unlock.setEnabled(not busy and protocol(v) == 'sftp' and auth(v) in ('auto', 'key'))
            if not data and not busy:
                status.setText('No connections yet · choose Add connection to create one.')

        def set_busy(on, msg=''):
            add.setEnabled(not on)
            close.setEnabled(not on)
            cancel.setEnabled(on)
            w.setEnabled(not on)
            if on:
                for x in (edit, clone, rem, test, diagnose, details, unlock, ssh, disconnect, connect):
                    x.setEnabled(False)
            else:
                update_actions()
            if msg:
                status.setText(msg)

        def server_editor(title, original=None, suggested=''):
            v = dict(original or {})
            box = NiruDialog(d)
            box.setWindowTitle(title)
            box.setModal(True)
            box.resize(680, 640)
            outer = QVBoxLayout(box)
            intro = QLabel(
                '<b>Remote connection</b><br>Choose the protocol first. For a Linux server, use SFTP / SSH. For a hosting account, use the protocol and hostname supplied by the provider. Only settings relevant to your choice are shown.'
            )
            intro.setWordWrap(True)
            outer.addWidget(intro)
            f = QFormLayout()
            outer.addLayout(f)
            name = QLineEdit(suggested)
            proto = QComboBox()
            proto.addItems(['SFTP / SSH (recommended)', 'FTP', 'FTPS · explicit TLS', 'FTPS · implicit TLS'])
            pv = protocol(v)
            proto.setCurrentIndex({'sftp': 0, 'ftp': 1, 'ftps': 2, 'ftps-implicit': 3}.get(pv, 0))
            route = QComboBox()
            route.addItems(['Direct / LAN / Internet', 'Tailscale · MagicDNS / 100.x IP', 'Tailscale SSH'])
            route.setCurrentIndex(
                {'direct': 0, 'tailscale': 1, 'tailscale-ssh': 2}.get(v.get('route', 'direct'), 0)
            )
            host = QLineEdit(v.get('host', ''))
            host.setPlaceholderText('nas.example.net, 100.x.x.x, ftp.example.net …')
            user = QLineEdit(v.get('user', os.getenv('USER', '')))
            port = QSpinBox()
            port.setRange(1, 65535)
            port.setValue(
                int(v.get('port', 22 if pv in ('ssh', 'sftp') else (990 if pv == 'ftps-implicit' else 21)))
            )
            path = QLineEdit(v.get('path', '/'))
            path.setPlaceholderText('/home/user or /')
            am = QComboBox()
            am.addItems(['OpenSSH / Auto (recommended)', 'SSH key', 'Password'])
            amap = {'auto': 0, 'key': 1, 'password': 2}
            am.setCurrentIndex(amap.get(auth(v), 0))
            key = QLineEdit(v.get('key', ''))
            key.setPlaceholderText('Optional private key, e.g. ~/.ssh/id_ed25519')
            browsekey = QPushButton('Browse…')
            kh = QHBoxLayout()
            kh.addWidget(key, 1)
            kh.addWidget(browsekey)
            kw = QWidget()
            kw.setLayout(kh)
            remember = QCheckBox('Remember password securely in Linux Secret Service')
            remember.setChecked(bool(v.get('remember_password', False)))
            timeout = QSpinBox()
            timeout.setRange(3, 120)
            timeout.setValue(int(v.get('timeout', 12)))
            timeout.setSuffix(' s')
            advanced = QGroupBox('Advanced')
            advanced.setCheckable(True)
            advanced.setChecked(bool(v.get('advanced', False) or v.get('proxyjump')))
            af = QFormLayout(advanced)
            proxy = QLineEdit(v.get('proxyjump', ''))
            proxy.setPlaceholderText('Optional SSH jump host / ProxyJump')
            keep = QSpinBox()
            keep.setRange(0, 300)
            keep.setValue(int(v.get('keepalive', 15)))
            keep.setSuffix(' s')
            passive = QCheckBox('Passive FTP mode (required by rclone)')
            passive.setChecked(True)
            passive.setEnabled(False)
            tlsverify = QCheckBox('Verify TLS certificate')
            tlsverify.setChecked(bool(v.get('tls_verify', True)))
            af.addRow('ProxyJump', proxy)
            af.addRow('Keepalive', keep)
            af.addRow('', passive)
            af.addRow('', tlsverify)
            f.addRow('Connection name', name)
            f.addRow('Protocol', proto)
            f.addRow('Network route', route)
            f.addRow('Host / MagicDNS / IP', host)
            f.addRow('Username', user)
            f.addRow('Port', port)
            f.addRow('Start folder', path)
            f.addRow('Authentication', am)
            f.addRow('SSH identity', kw)
            f.addRow('', remember)
            f.addRow('Timeout', timeout)
            outer.addWidget(advanced)
            hint = QLabel(
                '<b>Recommended:</b> SFTP + OpenSSH / Auto lets your existing ~/.ssh/config, ssh-agent and standard keys work without configuring a key twice. For a server over Tailscale, select Tailscale and use its MagicDNS hostname or 100.x address.'
            )
            hint.setWordWrap(True)
            outer.addWidget(hint)
            browsekey.clicked.connect(
                lambda: key.setText(
                    QFileDialog.getOpenFileName(box, 'Choose SSH private key', str(Path.home() / '.ssh'))[0]
                    or key.text()
                )
            )

            def defaults():
                i = proto.currentIndex()
                defaults = [22, 21, 21, 990]
                old = port.value()
                if old in (21, 22, 990):
                    port.setValue(defaults[i])

            def sync():
                sshish = proto.currentIndex() == 0
                am.setVisible(sshish)
                kw.setVisible(sshish and am.currentIndex() == 1)
                remember.setVisible((sshish and am.currentIndex() == 2) or not sshish)
                proxy.setVisible(sshish)
                keep.setVisible(sshish)
                passive.setVisible(not sshish)
                tlsverify.setVisible(proto.currentIndex() in (2, 3))
                for layout, field, visible in (
                    (f, am, sshish),
                    (f, kw, sshish and am.currentIndex() == 1),
                    (af, proxy, sshish),
                    (af, keep, sshish),
                    (af, passive, not sshish),
                    (af, tlsverify, proto.currentIndex() in (2, 3)),
                ):
                    label = layout.labelForField(field)
                    if label is not None:
                        label.setVisible(visible)
                if not sshish and am.currentIndex() != 2:
                    am.setCurrentIndex(2)
                if route.currentIndex() == 2 and not sshish:
                    route.setCurrentIndex(0)

            proto.currentIndexChanged.connect(defaults)
            proto.currentIndexChanged.connect(sync)
            am.currentIndexChanged.connect(sync)
            route.currentIndexChanged.connect(sync)
            sync()
            bb = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            saveconnect = bb.addButton('Save & connect', QDialogButtonBox.ButtonRole.ActionRole)
            box.setProperty('save_and_connect', False)
            saveconnect.clicked.connect(lambda: (box.setProperty('save_and_connect', True), box.accept()))
            bb.accepted.connect(box.accept)
            bb.rejected.connect(box.reject)
            outer.addWidget(bb)
            name.setFocus()
            if box.exec() != QDialog.DialogCode.Accepted:
                return None
            n = name.text().strip()
            h = host.text().strip()
            u = user.text().strip()
            if not n or not h:
                self.err('Name and host are required.')
                return None
            pr = ['sftp', 'ftp', 'ftps', 'ftps-implicit'][proto.currentIndex()]
            au = ['auto', 'key', 'password'][am.currentIndex()] if pr == 'sftp' else 'password'
            rt = ['direct', 'tailscale', 'tailscale-ssh'][route.currentIndex()]
            if rt == 'tailscale-ssh' and pr != 'sftp':
                self.err('Tailscale SSH is only available with SFTP / SSH.')
                return None
            if pr == 'sftp' and au == 'key' and not key.text().strip():
                self.err(
                    'SSH key is selected, but no private key file is configured. Choose a key, or use OpenSSH / Auto to use ssh-agent, ~/.ssh/config and standard keys.'
                )
                return None
            return (
                n,
                {
                    'protocol': pr,
                    'route': rt,
                    'host': h,
                    'user': u,
                    'port': port.value(),
                    'path': path.text().strip() or '/',
                    'auth': au,
                    'key': key.text().strip() if au == 'key' else '',
                    'remember_password': bool(remember.isChecked() and au == 'password'),
                    'timeout': timeout.value(),
                    'proxyjump': proxy.text().strip(),
                    'keepalive': keep.value(),
                    'passive': passive.isChecked(),
                    'tls_verify': tlsverify.isChecked(),
                    'advanced': advanced.isChecked(),
                },
                bool(box.property('save_and_connect')),
            )

        def secret_key(n, v):
            return ['application', 'niruorg', 'service', 'server', 'server', n, 'user', v.get('user', '')]

        def secret_lookup(n, v):
            if n in session_passwords:
                return session_passwords[n]
            if not v.get('remember_password') or not shutil.which('secret-tool'):
                return ''
            try:
                r = subprocess.run(
                    ['secret-tool', 'lookup'] + secret_key(n, v), capture_output=True, text=True, timeout=4
                )
                return r.stdout.rstrip('\n') if r.returncode == 0 else ''
            except Exception:
                return ''

        def secret_store(n, v, pw):
            session_passwords[n] = pw
            if not v.get('remember_password'):
                return True
            if not shutil.which('secret-tool'):
                self.err(
                    'Secret Service is unavailable. The password will be kept for this NIRUORG session only.'
                )
                return False
            try:
                r = subprocess.run(
                    ['secret-tool', 'store', '--label=NIRUORG server ' + n] + secret_key(n, v),
                    input=pw + '\n',
                    text=True,
                    capture_output=True,
                    timeout=5,
                )
                return r.returncode == 0
            except Exception:
                return False

        def secret_clear(n, v):
            session_passwords.pop(n, None)
            if shutil.which('secret-tool'):
                try:
                    subprocess.run(
                        ['secret-tool', 'clear'] + secret_key(n, v), capture_output=True, timeout=4
                    )
                except Exception:
                    pass

        def get_password(n, v):
            pw = secret_lookup(n, v)
            if pw:
                return pw
            pw, ok = QInputDialog.getText(
                d,
                'Password · ' + n,
                f'Password for {v.get("user","")}@{v.get("host","")}:',
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                return None
            secret_store(n, v, pw)
            return pw

        def save_entry(result, old=None):
            if not result:
                return
            n, v, *extra = result
            connect_after = bool(extra[0]) if extra else False
            if n != old and n in data:
                return self.err(f'A server named {n} already exists.')
            if old and old != n:
                oldv = data.get(old, {})
                data.pop(old, None)
                session_passwords.pop(old, None)
                if oldv.get('remember_password'):
                    secret_clear(old, oldv)
            data[n] = v
            self._save_json('servers_json', data)
            refresh(n)
            self.build_sidebar()
            QTimer.singleShot(0, connectone) if connect_after else None

        def addone():
            status.setText('Opening connection editor…')
            try:
                result = server_editor('Add connection')
                if result is None:
                    status.setText('Ready')
                else:
                    save_entry(result)
            except Exception as e:
                self.err(f'Could not open connection editor.\n\n{type(e).__name__}: {e}')

        def editone():
            n, v = current()
            if v:
                save_entry(server_editor('Edit server', v, n), n)

        def cloneone():
            n, v = current()
            if v:
                save_entry(server_editor('Clone server', v, n + ' copy'))

        def removeone():
            n, v = current()
            if not n:
                return
            if path_is_mounted(mountpoint(n)):
                return self.err('Disconnect this server before removing it.')
            q = NiruDialog(d)
            q.setWindowTitle('Remove connection')
            ql = QVBoxLayout(q)
            qt = QLabel(
                f'<b>Remove “{n}”?</b><br><br>This removes the saved connection from NIRUORG. No files on the server will be changed or deleted.'
            )
            qt.setWordWrap(True)
            ql.addWidget(qt)
            qb = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
            qb.accepted.connect(q.accept)
            qb.rejected.connect(q.reject)
            ql.addWidget(qb)
            if q.exec() == QDialog.DialogCode.Accepted:
                secret_clear(n, v)
                data.pop(n, None)
                self._save_json('servers_json', data)
                refresh()
                self.build_sidebar()

        def ssh_args(v, batch=False):
            args = [
                '-p',
                str(v.get('port', 22)),
                '-o',
                f'ConnectTimeout={int(v.get("timeout",12))}',
                '-o',
                f'ServerAliveInterval={int(v.get("keepalive",15))}',
                '-o',
                'ServerAliveCountMax=2',
            ]
            pj = v.get('proxyjump', '').strip()
            args += ['-J', pj] if pj else []
            if batch:
                args += ['-o', 'BatchMode=yes']
            if auth(v) == 'key':
                key = Path(os.path.expanduser(v.get('key', '')))
                if key.exists():
                    args += (
                        ['-i', str(key), ' -o', 'IdentitiesOnly=yes']
                        if False
                        else ['-i', str(key), '-o', 'IdentitiesOnly=yes']
                    )
            return args

        def cleanup_tmp():
            t = state.get('tmp')
            state['tmp'] = None
            if t:
                try:
                    Path(t).unlink(missing_ok=True)
                except Exception:
                    pass

        def key_auth_failure(detail):
            t = (detail or '').lower()
            return any(
                x in t
                for x in (
                    'permission denied',
                    'publickey',
                    'passphrase',
                    'sign_and_send_pubkey',
                    'agent refused operation',
                    'no identities',
                )
            )

        def unlock_prompt(n, v, retry):
            q = NiruDialog(d)
            q.setWindowTitle('Unlock SSH key · ' + n)
            q.resize(570, 300)
            ql = QVBoxLayout(q)
            title = QLabel('SSH key needs to be unlocked')
            title.setObjectName('dialogTitle')
            ql.addWidget(title)
            body = QLabel(
                'Enter the passphrase for your SSH key. NIRUORG passes it directly to OpenSSH for this unlock attempt; it is not saved in settings, logs, command arguments, environment variables, or files.'
            )
            body.setTextFormat(Qt.TextFormat.PlainText)
            body.setWordWrap(True)
            ql.addWidget(body)
            keypath = (
                Path(os.path.expanduser(v.get('key', ''))) if auth(v) == 'key' and v.get('key') else None
            )
            if keypath:
                kn = QLabel('Key · ' + str(keypath))
                kn.setObjectName('muted')
                kn.setWordWrap(True)
                ql.addWidget(kn)
            pw = QLineEdit()
            pw.setEchoMode(QLineEdit.EchoMode.Password)
            pw.setPlaceholderText('SSH key passphrase')
            pw.setClearButtonEnabled(True)
            ql.addWidget(pw)
            statusline = QLabel('The key is added only to the active SSH agent session.')
            statusline.setObjectName('muted')
            statusline.setWordWrap(True)
            ql.addWidget(statusline)
            ql.addStretch()
            br = QHBoxLayout()
            unlockb = QPushButton('Unlock')
            retryb = QPushButton('Retry')
            cancelb = QPushButton('Cancel')
            br.addStretch()
            br.addWidget(unlockb)
            br.addWidget(retryb)
            br.addWidget(cancelb)
            ql.addLayout(br)

            def launch():
                exe = shutil.which('ssh-add')
                if not exe:
                    return self.err('ssh-add is not installed. Install the OpenSSH client tools.')
                if not pw.text():
                    pw.setFocus()
                    return
                env = self._ssh_agent_environment(True)
                if not env.get('SSH_AUTH_SOCK'):
                    return self.err(
                        'NIRUORG could not start or access an SSH authentication agent. Open Connection diagnostics for details, or verify that ssh-agent is installed.'
                    )
                secret = pw.text()
                pw.clear()
                unlockb.setEnabled(False)
                retryb.setEnabled(False)
                statusline.setText('Unlocking SSH key…')
                helper_fd_r, helper_fd_w = os.pipe()
                try:
                    os.write(helper_fd_w, secret.encode('utf-8') + b'\n')
                finally:
                    os.close(helper_fd_w)
                    secret = ''
                # mkstemp creates the helper with an unpredictable name and mode 0600.
                # Never write through a predictable filename in shared /tmp.
                helper_fd, helper_name = tempfile.mkstemp(prefix='niruorg-askpass-', suffix='.sh')
                helper = Path(helper_name)
                with os.fdopen(helper_fd, 'w', encoding='utf-8') as helper_file:
                    helper_file.write(
                        '#!/bin/sh\nIFS= read -r pass <&"$NIRUORG_ASKPASS_FD"\nprintf "%s\n" "$pass"\n'
                    )
                helper.chmod(0o700)
                args = [exe] + ([str(keypath)] if keypath else [])
                pe = {
                    **os.environ,
                    **env,
                    'SSH_ASKPASS': str(helper),
                    'SSH_ASKPASS_REQUIRE': 'force',
                    'DISPLAY': os.environ.get('DISPLAY') or ':0',
                    'NIRUORG_ASKPASS_FD': str(helper_fd_r),
                }
                try:
                    r = subprocess.run(
                        args,
                        env=pe,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=20,
                        pass_fds=(helper_fd_r,),
                    )
                except Exception as e:
                    r = None
                    detail = str(e)
                finally:
                    os.close(helper_fd_r)
                    helper.unlink(missing_ok=True)
                unlockb.setEnabled(True)
                retryb.setEnabled(True)
                if r and r.returncode == 0:
                    status.setText('SSH key unlocked · ' + n)
                    q.accept()
                    QTimer.singleShot(100, retry)
                    return
                detail = (r.stderr.strip() if r else detail) or 'OpenSSH rejected the key passphrase.'
                statusline.setText('Could not unlock the SSH key. Check the passphrase and try again.')
                pw.setFocus()
                self.err('SSH key unlock failed.\n\n' + detail)

            unlockb.clicked.connect(launch)
            pw.returnPressed.connect(launch)

            def do_retry():
                q.accept()
                QTimer.singleShot(0, retry)

            retryb.clicked.connect(do_retry)
            cancelb.clicked.connect(q.reject)
            QTimer.singleShot(0, pw.setFocus)
            q.exec()

        def finish(ok, detail=''):
            action = state['action']
            n = state['name']
            mp = state['mount']
            retry = state.get('retry')
            state['retry'] = None
            set_busy(False)
            if state['timer']:
                state['timer'].stop()
                state['timer'] = None
            state['proc'] = None
            cleanup_tmp()
            if action == 'connect' and ok:
                QTimer.singleShot(350, lambda: after_mount(n, mp))
            elif action in ('ssh-preflight-connect', 'ssh-preflight-test'):
                if ok:
                    status.setText(f'SSH authentication ready · {n}')
                    QTimer.singleShot(0, retry) if retry else None
                elif n in data and key_auth_failure(detail):
                    status.setText(f'SSH key locked or unavailable · {n}')
                    QTimer.singleShot(0, lambda: unlock_prompt(n, data[n], retry))
                else:
                    status.setText((f'SSH authentication failed · {n}') + (f' · {detail}' if detail else ''))
                    refresh(n)
            else:
                if action == 'disconnect' and ok:
                    if mp:
                        self._release_mount(mp)
                    for pane in (self.pane1, self.pane2):
                        if pane.remote_name == n:
                            pane.clear_remote()
                            pane.go(str(Path.home()), leave_remote=True)
                msg = (
                    f'{action.capitalize()} succeeded · {n}' if ok else f'{action.capitalize()} failed · {n}'
                ) + (f' · {detail}' if detail else '')
                if (
                    not ok
                    and action in ('test', 'connect')
                    and n in data
                    and protocol(data[n]) == 'sftp'
                    and auth(data[n]) in ('auto', 'key')
                    and key_auth_failure(detail)
                ):
                    msg += ' · SSH key may need unlocking.'
                status.setText(msg)
                refresh(n)
                self.build_sidebar()

        def after_mount(n, mp):
            mounted = bool(mp and path_is_mounted(mp))
            set_busy(False)
            refresh(n)
            self.build_sidebar()
            cfg = data.get(n)
            if mounted and cfg:
                self._claim_mount(mp, 'server', n)
                try:
                    # The async mount callback must resolve the connection by name here.
                    # Never depend on a stale/free `v` from another nested callback.
                    target_pane.bind_remote(n, protocol(cfg), mp, cfg.get('path', '/'))
                    target_pane.go(mp)
                    if not target_pane.is_remote() or not target_pane._path_inside_remote(
                        target_pane.current
                    ):
                        raise RuntimeError('mounted server was not bound to the target pane')
                except Exception as e:
                    target_pane.clear_remote()
                    status.setText(f'Connected mount could not be opened · {n}')
                    self.err(f'Remote mount opened but the file pane could not switch to {n}.\n\n{e}')
                    return
                status.setText(f'Connected · {n}')
                if initial_action == 'connect':
                    QTimer.singleShot(100, d.accept)
            elif mounted:
                status.setText(f'Connection definition disappeared before mount completed · {n}')
            else:
                status.setText(f'Connect command ended but mount is not active · {n}')

        def run_async(program, args, action, n, timeout_s, mount=None, env=None, tmp=None, retry=None):
            if state['proc']:
                return
            proc = QProcess(d)
            state.update(proc=proc, action=action, name=n, mount=mount, tmp=tmp, retry=retry)
            proc.setProgram(program)
            proc.setArguments(args)
            proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            if env:
                pe = proc.processEnvironment()
                for k, v in env.items():
                    pe.insert(k, v)
                proc.setProcessEnvironment(pe)
            set_busy(True, f'{action.capitalize()}… · {n}')
            done = {'v': False}

            def ended(code, exitstatus):
                if done['v']:
                    return
                done['v'] = True
                out = bytes(proc.readAllStandardOutput()).decode(errors='replace').strip()
                ok = code == 0 and exitstatus == QProcess.ExitStatus.NormalExit
                finish(ok, out[-1000:] if out else '')

            def failed(_):
                if done['v']:
                    return
                done['v'] = True
                out = bytes(proc.readAllStandardOutput()).decode(errors='replace').strip()
                finish(False, out or proc.errorString())

            proc.finished.connect(ended)
            proc.errorOccurred.connect(failed)
            timer = QTimer(d)
            timer.setSingleShot(True)
            state['timer'] = timer

            def timedout():
                if state['proc'] and state['proc'].state() != QProcess.ProcessState.NotRunning:
                    status.setText(f'{action.capitalize()} timed out · {n}')
                    state['proc'].kill()

            timer.timeout.connect(timedout)
            timer.start(max(3, int(timeout_s)) * 1000)
            proc.start()

        def obscure(pw):
            exe = shutil.which('rclone')
            if not exe:
                return None
            try:
                r = subprocess.run(
                    [exe, 'obscure', '-'], input=pw + '\n', text=True, capture_output=True, timeout=4
                )
                return r.stdout.strip() if r.returncode == 0 else None
            except Exception:
                return None

        def rclone_config(n, v, pw):
            ob = obscure(pw)
            if not ob:
                return None
            import tempfile

            fd, path = tempfile.mkstemp(prefix='niruorg-server-', suffix='.conf')
            os.close(fd)
            os.chmod(path, 0o600)
            pr = protocol(v)
            typ = 'sftp' if pr == 'sftp' else 'ftp'
            lines = [
                '[remote]',
                f'type = {typ}',
                f'host = {v.get("host","")}',
                f'user = {v.get("user","")}',
                f'port = {v.get("port",22 if pr=="sftp" else 21)}',
                f'pass = {ob}',
            ]
            if pr in ('ftps', 'ftps-implicit'):
                lines += ['tls = true']
                lines += [
                    f'explicit_tls = {str(pr=="ftps").lower()}',
                    f'no_check_certificate = {str(not v.get("tls_verify",True)).lower()}',
                ]
            Path(path).write_text('\n'.join(lines) + '\n')
            return path

        def diagnoseone():
            n, v = current()
            if not v:
                return
            diagnose.setEnabled(False)
            status.setText(f'Diagnosing… · {n}')
            worker = ConnectionDiagnosticWorker(n, v)
            self.running_workers.append(worker)

            def show(rows):
                try:
                    self.running_workers.remove(worker)
                except ValueError:
                    pass
                diagnose.setEnabled(True)
                status.setText(f'Diagnostics complete · {n}')
                dd = NiruDialog(d)
                dd.setWindowTitle('Connection diagnostics · ' + n)
                dd.resize(680, 480)
                dl = QVBoxLayout(dd)
                head = QLabel(
                    f'<b>{n}</b><br>{v.get("host","")}:{v.get("port",22)} · read-only diagnostics · no settings were changed'
                )
                head.setWordWrap(True)
                dl.addWidget(head)
                tree = QTreeWidget()
                tree.setHeaderLabels(['Stage', 'Result', 'Details'])
                tree.setRootIsDecorated(False)
                tree.setAlternatingRowColors(True)
                for stage, ok, detail in rows:
                    it = QTreeWidgetItem([stage, 'OK' if ok else 'FAILED', detail])
                    tree.addTopLevelItem(it)
                tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
                tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
                tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
                dl.addWidget(tree, 1)
                note = QLabel(
                    'DNS → Tailscale (when selected) → TCP port → SSH authentication. A TCP failure means authentication and SSH keys have not been reached yet.'
                )
                note.setWordWrap(True)
                note.setObjectName('muted')
                dl.addWidget(note)
                cb = QPushButton('Close')
                cb.clicked.connect(dd.accept)
                br = QHBoxLayout()
                br.addStretch()
                br.addWidget(cb)
                dl.addLayout(br)
                dd.exec()

            worker.signals.done.connect(show)
            self._start_worker(self.threadpool, worker, ('done',))

        def testone_raw():
            n, v = current()
            if not v:
                return
            if protocol(v) == 'sftp' and auth(v) != 'password':
                exe = shutil.which('ssh')
                if not exe:
                    return self.err('OpenSSH client is not installed.')
                dest = f'{v.get("user")}@{v.get("host")}' if v.get('user') else v.get('host')
                return run_async(
                    exe,
                    ssh_args(v, True) + [dest, 'true'],
                    'test',
                    n,
                    int(v.get('timeout', 12)) + 3,
                    env=self._ssh_agent_environment(False),
                )
            pw = get_password(n, v)
            if pw is None:
                return
            exe = shutil.which('rclone')
            if not exe:
                return self.err('rclone is required for password-based SFTP/FTP/FTPS. Re-run the installer.')
            cfg = rclone_config(n, v, pw)
            if not cfg:
                return self.err('Could not prepare secure connection configuration.')
            target = 'remote:' + v.get('path', '/')
            run_async(
                exe,
                ['lsd', target, '--config', cfg, '--max-depth', '1'],
                'test',
                n,
                int(v.get('timeout', 12)) + 5,
                tmp=cfg,
            )

        def connectone_raw():
            n, v = current()
            if not v:
                return
            mp = mountpoint(n)
            mp.mkdir(parents=True, exist_ok=True)
            if path_is_mounted(mp):
                status.setText(f'Already connected · {n}')
                target_pane.bind_remote(n, protocol(v), mp, v.get('path', '/'))
                target_pane.go(mp)
                return
            if protocol(v) == 'sftp' and auth(v) != 'password':
                exe = shutil.which('sshfs')
                if not exe:
                    return self.err('SSHFS is not installed. Re-run the NIRUORG installer or install sshfs.')
                remote = (
                    f'{v.get("user")}@' if v.get('user') else ''
                ) + f'{v.get("host")}:{v.get("path","/")}'
                opts = f'reconnect,ConnectTimeout={int(v.get("timeout",12))},ServerAliveInterval={int(v.get("keepalive",15))},ServerAliveCountMax=2'
                args = [remote, str(mp), '-p', str(v.get('port', 22)), '-o', opts]
                pj = v.get('proxyjump', '').strip()
                args += ['-o', f'ProxyJump={pj}'] if pj else []
                if auth(v) == 'key':
                    key = Path(os.path.expanduser(v.get('key', '')))
                    if key.exists():
                        args += ['-o', f'IdentityFile={key}', '-o', 'IdentitiesOnly=yes']
                return run_async(
                    exe,
                    args,
                    'connect',
                    n,
                    int(v.get('timeout', 12)) + 5,
                    mp,
                    env=self._ssh_agent_environment(False),
                )
            pw = get_password(n, v)
            if pw is None:
                return
            exe = shutil.which('rclone')
            if not exe:
                return self.err('rclone is required for password-based SFTP/FTP/FTPS. Re-run the installer.')
            cfg = rclone_config(n, v, pw)
            if not cfg:
                return self.err('Could not prepare secure connection configuration.')
            target = 'remote:' + v.get('path', '/')
            args = ['mount', target, str(mp), '--config', cfg, '--vfs-cache-mode', 'writes', '--daemon']
            run_async(exe, args, 'connect', n, int(v.get('timeout', 12)) + 8, mp, tmp=cfg)

        def ssh_preflight(n, v, retry, kind):
            exe = shutil.which('ssh')
            if not exe:
                return self.err('OpenSSH client is not installed.')
            dest = f'{v.get("user")}@{v.get("host")}' if v.get('user') else v.get('host')
            action = 'ssh-preflight-' + kind
            run_async(
                exe,
                ssh_args(v, True) + [dest, 'true'],
                action,
                n,
                int(v.get('timeout', 12)) + 3,
                env=self._ssh_agent_environment(False),
                retry=retry,
            )

        def testone():
            n, v = current()
            if not v:
                return
            if protocol(v) == 'sftp' and auth(v) in ('auto', 'key'):
                return ssh_preflight(n, v, testone_raw, 'test')
            return testone_raw()

        def connectone():
            n, v = current()
            if not v:
                return
            mp = mountpoint(n)
            if path_is_mounted(mp):
                status.setText(f'Already connected · {n}')
                target_pane.bind_remote(n, protocol(v), mp, v.get('path', '/'))
                target_pane.go(mp)
                return
            if protocol(v) == 'sftp' and auth(v) in ('auto', 'key'):
                return ssh_preflight(n, v, connectone_raw, 'connect')
            return connectone_raw()

        def disconnectone():
            n, v = current()
            if not n:
                return
            mp = mountpoint(n)
            if not path_is_mounted(mp):
                status.setText(f'Not connected · {n}')
                return
            exe = shutil.which('fusermount3') or shutil.which('fusermount') or shutil.which('umount')
            if not exe:
                return self.err('No unmount helper found.')
            args = ['-u', str(mp)] if 'fusermount' in Path(exe).name else [str(mp)]
            run_async(exe, args, 'disconnect', n, 8, mp)

        def detailsone():
            n, v = current()
            if not v:
                return
            mp = mountpoint(n)
            pr = protocol(v)
            rt = v.get('route', 'direct')
            route_label = {
                'direct': 'Direct / LAN / Internet',
                'tailscale': 'Tailscale',
                'tailscale-ssh': 'Tailscale SSH',
            }.get(rt, rt)
            deps = []
            for label, cmd in [
                ('OpenSSH', 'ssh'),
                ('SSHFS', 'sshfs'),
                ('rclone', 'rclone'),
                ('Tailscale', 'tailscale'),
                ('Secret Service', 'secret-tool'),
            ]:
                deps.append(f'{label}: ' + ('available' if shutil.which(cmd) else 'not installed'))
            text = (
                f'Connection: {n}\nProtocol: {pr.upper()}\nNetwork: {route_label}\nHost: {v.get("host","")}:{v.get("port",22)}\nUser: {v.get("user","") or "(default)"}\nRemote folder: {v.get("path","/")}\nAuthentication: {auth(v)}\nMounted: {"yes" if path_is_mounted(mp) else "no"}\nLocal mount: {mp}\n\nCapabilities\n'
                + "\n".join(deps)
            )
            if rt.startswith('tailscale'):
                text += '\n\nTailscale tip: verify this machine is signed in with `tailscale status`. MagicDNS names and 100.x addresses work as normal SSH/SFTP hosts.'
            dd = NiruDialog(d)
            dd.setWindowTitle('Connection details · ' + n)
            dd.resize(560, 430)
            dl = QVBoxLayout(dd)
            title = QLabel(f'<b>{n}</b><br>{pr.upper()} · {route_label}')
            title.setWordWrap(True)
            dl.addWidget(title)
            grid = QFormLayout()
            grid.addRow('Endpoint', QLabel(f'{v.get("host","")}:{v.get("port",22)}'))
            grid.addRow('Username', QLabel(v.get('user', '') or '(OpenSSH default)'))
            grid.addRow('Start folder', QLabel(v.get('path', '/')))
            grid.addRow(
                'Authentication',
                QLabel(
                    {'auto': 'OpenSSH / Auto', 'key': 'SSH key', 'password': 'Password'}.get(auth(v), auth(v))
                ),
            )
            grid.addRow('Status', QLabel('Connected' if path_is_mounted(mp) else 'Disconnected'))
            grid.addRow('Local mount', QLabel(str(mp)))
            dl.addLayout(grid)
            cap = QLabel('<b>Capabilities</b><br>' + '<br>'.join(deps))
            cap.setWordWrap(True)
            dl.addWidget(cap)
            dl.addStretch()
            close = QPushButton('Close')
            close.clicked.connect(dd.accept)
            br = QHBoxLayout()
            br.addStretch()
            br.addWidget(close)
            dl.addLayout(br)
            dd.exec()

        def unlockkey():
            n, v = current()
            if not v or protocol(v) != 'sftp':
                return

            def done():
                status.setText('SSH key ready · ' + n)

            unlock_prompt(n, v, done)

        def sshopen():
            n, v = current()
            if not v:
                return
            if protocol(v) != 'sftp':
                return self.err('Interactive SSH is available for SSH/SFTP servers only.')
            exe = shutil.which('ssh')
            if not exe:
                return self.err('OpenSSH client is not installed.')
            dest = f'{v.get("user")}@{v.get("host")}' if v.get('user') else v.get('host')
            cmd = (
                [shutil.which('tailscale'), 'ssh', dest]
                if v.get('route') == 'tailscale-ssh' and shutil.which('tailscale')
                else [exe] + ssh_args(v, False) + [dest]
            )
            if v.get('route') == 'tailscale-ssh' and not shutil.which('tailscale'):
                return self.err(
                    'Tailscale CLI is not installed. Install/start Tailscale or change Network to Tailscale · MagicDNS or 100.x IP.'
                )
            # For password auth, the terminal deliberately handles the interactive password prompt; no password is put on the command line.
            if self.terminal and 'kitty' in self.terminal:
                run_detached([self.terminal, '--hold'] + cmd, env=self._ssh_agent_environment(False))
            elif self.terminal:
                run_detached([self.terminal, '-e'] + cmd, env=self._ssh_agent_environment(False))
            else:
                run_detached(cmd, env=self._ssh_agent_environment(False))

        def cancelone():
            p = state.get('proc')
            if p:
                status.setText(f'Cancelling · {state["name"]}')
                p.terminate()
                QTimer.singleShot(
                    1200, lambda: p.kill() if p.state() != QProcess.ProcessState.NotRunning else None
                )

        add.clicked.connect(addone)
        importb.clicked.connect(lambda: (d.accept(), self.import_connections()))
        edit.clicked.connect(editone)
        clone.clicked.connect(cloneone)
        rem.clicked.connect(removeone)
        test.clicked.connect(testone)
        diagnose.clicked.connect(diagnoseone)
        details.clicked.connect(detailsone)
        unlock.clicked.connect(unlockkey)
        connect.clicked.connect(connectone)
        disconnect.clicked.connect(disconnectone)
        ssh.clicked.connect(sshopen)
        cancel.clicked.connect(cancelone)
        w.currentItemChanged.connect(lambda *_: update_actions())
        w.itemDoubleClicked.connect(lambda *_: connectone())
        refresh(initial_name)
        update_actions()
        actions = {
            'connect': connectone,
            'test': testone,
            'diagnose': diagnoseone,
            'details': detailsone,
            'disconnect': disconnectone,
            'ssh': sshopen,
            'edit': editone,
            'clone': cloneone,
            'remove': removeone,
        }
        if initial_action in actions:
            QTimer.singleShot(0, actions[initial_action])
        d.exec()
        if state.get('proc') and state['proc'].state() != QProcess.ProcessState.NotRunning:
            state['proc'].kill()
        cleanup_tmp()

    def _rclone_remotes(self):
        exe = shutil.which('rclone')
        if not exe:
            return []
        try:
            r = subprocess.run([exe, 'listremotes'], capture_output=True, text=True, timeout=8)
            if r.returncode:
                return []
            return [x.strip().rstrip(':') for x in r.stdout.splitlines() if x.strip()]
        except Exception:
            return []

    def _rclone_remote_type(self, name):
        exe = shutil.which('rclone')
        if not exe:
            return ''
        # redacted never exposes OAuth tokens; older rclone versions simply fall back to a generic label.
        try:
            r = subprocess.run([exe, 'config', 'redacted', name], capture_output=True, text=True, timeout=5)
            if r.returncode:
                return ''
            for line in r.stdout.splitlines():
                if line.strip().startswith('type ='):
                    return line.split('=', 1)[1].strip()
        except Exception:
            pass
        return ''

    def _cloud_label(self, name):
        typ = self._rclone_remote_type(name)
        names = {
            'drive': 'Google Drive',
            'onedrive': 'OneDrive / Microsoft 365',
            'dropbox': 'Dropbox',
            's3': 'S3',
            'webdav': 'WebDAV',
            'box': 'Box',
        }
        return f'{names.get(typ,"Cloud")} · {name}'

    def _cloud_mountpoint(self, name):
        safe = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in name)
        return Path.home() / '.local/share/niruorg/cloud' / safe

    def _cloud_sidebar_entries(self):
        # Show the local Nextcloud folder only when it actually exists. rclone remotes
        # below are already the configured set returned by `rclone listremotes`.
        out = []
        nc = Path.home() / 'Nextcloud'
        if nc.is_dir():
            out.append(('Nextcloud', str(nc), f'Local Nextcloud sync · {nc}', 'cloud:nextcloud'))
        mounts = mounted_paths()
        for name in self._cloud_cache:
            mp = self._cloud_mountpoint(name)
            mounted = path_is_mounted(mp, mounts)
            typ = self._cloud_types.get(name, '')
            names = {
                'drive': 'Google Drive',
                'onedrive': 'OneDrive / Microsoft 365',
                'dropbox': 'Dropbox',
                's3': 'S3',
                'webdav': 'WebDAV',
                'box': 'Box',
            }
            label = f'{names.get(typ,"Cloud")} · {name}'
            out.append(
                (
                    ('●  ' if mounted else '○  ') + label,
                    str(mp) if mounted else '__cloud__:' + name,
                    ('Mounted · checked lazily' if mounted else 'Click to mount · ') + name,
                    'cloud:' + name,
                )
            )
        out.append(
            (
                '+  Cloud accounts…',
                '__cloud_manager__',
                'Add or manage cloud accounts · Google Drive, OneDrive / Microsoft 365, Dropbox, WebDAV and other rclone providers',
                'cloud-manager',
            )
        )
        return out

    def _mount_cloud_task(self, name, mp):
        exe = shutil.which('rclone')
        if not exe:
            raise RuntimeError('rclone is not installed. Open Cloud services for installation information.')
        if name not in self._rclone_remotes():
            raise RuntimeError(f'Cloud remote not found: {name}')
        created_here = not path_is_mounted(mp)
        if created_here:
            r = subprocess.run(
                [exe, 'mount', name + ':', str(mp), '--vfs-cache-mode', 'writes', '--daemon'],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if r.returncode:
                raise RuntimeError(
                    r.stderr.strip()
                    or f'Could not mount {name}. Ensure FUSE is installed and the cloud login is valid.'
                )
            for _ in range(50):
                if path_is_mounted(mp):
                    break
                time.sleep(0.1)
        if not path_is_mounted(mp):
            raise RuntimeError(f'{name} did not become available at {mp}.')
        return created_here

    def open_cloud(self, name, target_pane=None):
        target_pane = target_pane or self.active
        mp = self._cloud_mountpoint(name)
        mp.mkdir(parents=True, exist_ok=True)
        state = {'cancelled': False}

        def cancel():
            state['cancelled'] = True
            self.status.setText(f'{name} · Opening cancelled')

        activity = target_pane.show_activity(f'Connecting to {name}…', cancel)

        def done(created_here):
            target_pane.hide_activity(activity)
            if created_here:
                self._claim_mount(mp, 'cloud', name)
            self.build_sidebar()
            # The mount cannot be interrupted half-way; after Cancel it stays owned
            # (unmounted on exit like any other) but the pane does not switch to it.
            if state['cancelled']:
                self.status.setText(f'Cloud mounted · {name} · not opened (cancelled)')
                return
            target_pane.bind_remote(name, 'CLOUD', mp, '/')
            target_pane.go(str(mp))
            self.set_active(target_pane)
            self.status.setText(f'Cloud mounted · {name}')

        def failed(error):
            target_pane.hide_activity(activity)
            if not state['cancelled']:
                self.err(error)

        self._run_task(f'Mounting {name}…', lambda: self._mount_cloud_task(name, mp), done, failed)

    def unmount_cloud(self, name):
        mp = self._cloud_mountpoint(name)
        if not path_is_mounted(mp):
            return
        cmd = shutil.which('fusermount3') or shutil.which('fusermount') or shutil.which('umount')
        if not cmd:
            return self.err('No FUSE unmount command is available.')
        args = [cmd, '-u', str(mp)] if 'fusermount' in Path(cmd).name else [cmd, str(mp)]
        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode:
            return self.err(r.stderr.strip() or f'Could not unmount {name}.')
        self._release_mount(mp)
        for pane in (self.pane1, self.pane2):
            if pane.remote_name == name and pane.remote_protocol == 'CLOUD':
                pane.clear_remote()
                pane.go(str(Path.home()), leave_remote=True)
        self.build_sidebar()
        self.status.setText(f'Cloud unmounted · {name}')

    def manage_clouds(self):
        d = NiruDialog(self)
        d.setWindowTitle('Cloud services')
        d.resize(700, 500)
        l = QVBoxLayout(d)
        l.addWidget(
            QLabel(
                '<b>Cloud services</b><br>NIRUORG uses rclone for remote cloud access. OAuth credentials remain in rclone; NIRUORG does not store your Google or Microsoft password.'
            )
        )
        w = QTreeWidget()
        w.setHeaderLabels(['Service / remote', 'Status', 'Mount point'])
        w.setRootIsDecorated(False)
        l.addWidget(w, 1)

        def refresh():
            w.clear()
            nc = Path.home() / 'Nextcloud'
            if nc.exists():
                QTreeWidgetItem(w, ['Nextcloud', 'Local sync', str(nc)])
            for name in self._rclone_remotes():
                mp = self._cloud_mountpoint(name)
                it = QTreeWidgetItem(
                    w, [self._cloud_label(name), 'Mounted' if path_is_mounted(mp) else 'Ready', str(mp)]
                )
                it.setData(0, Qt.ItemDataRole.UserRole, name)
            self.build_sidebar()

        def require_rclone():
            if shutil.which('rclone'):
                return True
            self.err(
                'rclone is required for Google Drive, OneDrive / Microsoft 365 and other remote clouds.\n\nInstall package: rclone\nThen reopen Cloud services.'
            )
            return False

        def add_provider(provider):
            if not require_rclone():
                return
            hints = {
                'Google Drive': 'In rclone choose Google Drive (drive) and complete the browser OAuth login.',
                'OneDrive / Microsoft 365': 'In rclone choose Microsoft OneDrive (onedrive). The same provider supports personal OneDrive and Microsoft 365 work/school accounts.',
                'Other': 'Choose any rclone provider you need, such as Dropbox, WebDAV, S3 or Box.',
            }
            self.info(
                'Connect ' + provider,
                hints[provider]
                + '\n\nNIRUORG will now open rclone configuration in a terminal. Return here and press Refresh when authentication is complete.',
            )
            if not self._terminal_command([shutil.which('rclone'), 'config']):
                self.err('Could not open a terminal for rclone configuration.')

        row = QHBoxLayout()
        addg = QPushButton('Add Google Drive…')
        addm = QPushButton('Add OneDrive / M365…')
        addo = QPushButton('Other provider…')
        mount = QPushButton('Mount / Open')
        unmount = QPushButton('Unmount')
        ref = QPushButton('Refresh')
        for b in (addg, addm, addo):
            row.addWidget(b)
        row.addStretch()
        row.addWidget(mount)
        row.addWidget(unmount)
        row.addWidget(ref)
        l.addLayout(row)

        def current():
            it = w.currentItem()
            return it.data(0, Qt.ItemDataRole.UserRole) if it else None

        addg.clicked.connect(lambda: add_provider('Google Drive'))
        addm.clicked.connect(lambda: add_provider('OneDrive / Microsoft 365'))
        addo.clicked.connect(lambda: add_provider('Other'))
        ref.clicked.connect(refresh)
        mount.clicked.connect(lambda: self.open_cloud(current()) if current() else None)
        unmount.clicked.connect(lambda: self.unmount_cloud(current()) if current() else None)
        w.itemDoubleClicked.connect(lambda *_: self.open_cloud(current()) if current() else None)
        b = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        b.rejected.connect(d.reject)
        l.addWidget(b)
        refresh()
        d.exec()
        self.build_sidebar()

    def _nextcloud_secret(self):
        user = self.s.value('nextcloud_user', '')
        if not user or not shutil.which('secret-tool'):
            return ''
        r = subprocess.run(
            ['secret-tool', 'lookup', 'application', 'niruorg', 'service', 'nextcloud', 'user', user],
            text=True,
            capture_output=True,
        )
        return r.stdout.strip() if r.returncode == 0 else ''

    def _nextcloud_client(self):
        return NextcloudClient(
            self.s.value('nextcloud_url', ''), self.s.value('nextcloud_user', ''), self._nextcloud_secret
        )

    def _nextcloud_request(self, path, data=None):
        return self._nextcloud_client().request(path, data)

    def _nextcloud_relative(self, p):
        root = Path.home() / 'Nextcloud'
        try:
            return '/' + str(p.resolve().relative_to(root.resolve()))
        except Exception:
            raise NextcloudError('The selected item is not inside ~/Nextcloud.')

    def nextcloud_status(self):
        root = Path.home() / 'Nextcloud'
        if not root.is_dir():
            return 'not detected'
        if not self.s.value('nextcloud_url', '') or not self.s.value('nextcloud_user', ''):
            return 'local folder only'
        return 'configured · local sync folder; per-file status unknown'

    def _inside_nextcloud(self):
        try:
            return self.current_dir().resolve().is_relative_to((Path.home() / 'Nextcloud').resolve())
        except:
            return False

    def _nextcloud_options(self):
        d = NiruDialog(self)
        d.setWindowTitle('Nextcloud public links')
        d.setMinimumWidth(480)
        f = QFormLayout(d)
        permissions = QComboBox()
        permissions.addItems(['Read only', 'Read and write'])
        expiry = QCheckBox('Set expiry date')
        date = QDateEdit(QDate.currentDate().addDays(7))
        date.setCalendarPopup(True)
        date.setEnabled(False)
        password = QCheckBox('Require a password')
        secret = QLineEdit()
        secret.setEchoMode(QLineEdit.EchoMode.Password)
        secret.setEnabled(False)
        expiry.toggled.connect(date.setEnabled)
        password.toggled.connect(secret.setEnabled)
        f.addRow('Permission', permissions)
        f.addRow(expiry, date)
        f.addRow(password, secret)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        [button.setIcon(QIcon()) for button in buttons.buttons()]
        buttons.accepted.connect(d.accept)
        buttons.rejected.connect(d.reject)
        f.addRow(buttons)
        if d.exec() != QDialog.DialogCode.Accepted:
            return None
        if password.isChecked() and not secret.text():
            self.err('Enter a public-link password or clear the password option.')
            return None
        return {
            'permissions': 1 if permissions.currentIndex() == 0 else 15,
            'expire': date.date().toString('yyyy-MM-dd') if expiry.isChecked() else '',
            'password': secret.text() if password.isChecked() else '',
        }

    def nextcloud_share(self):
        s = self.selected()
        if not s:
            return self.err('Select one or more Nextcloud files or folders.')
        try:
            relative = [self._nextcloud_relative(p) for p in s]
        except NextcloudError as error:
            return self.err(error)
        options = self._nextcloud_options()
        if options is None:
            return

        def task():
            client = self._nextcloud_client()
            rows = []
            errors = []
            for path in relative:
                try:
                    rows.append(
                        {
                            'path': path,
                            'share': client.create_share(
                                path, options['permissions'], options['expire'], options['password']
                            ),
                        }
                    )
                except Exception as error:
                    errors.append(f'{path}: {error}')
            return rows, errors

        def done(result):
            rows, errors = result
            urls = [row['share'].get('url', '') for row in rows if row['share'].get('url')]
            if urls:
                QApplication.clipboard().setText('\n'.join(urls))
            lines = [f'{len(urls)} public link(s) created.'] + urls
            if errors:
                lines += ['', 'Not created:'] + errors
            self.info(
                'Nextcloud public links', '\n'.join(lines) + ('\n\nCopied to clipboard.' if urls else '')
            )

        self._run_task(f'Creating {len(relative)} Nextcloud public link(s)…', task, done, self.err)

    def nextcloud_remove_links(self):
        s = self.selected()
        if not s:
            return self.err('Select one or more Nextcloud files or folders.')
        try:
            relative = [self._nextcloud_relative(p) for p in s]
        except NextcloudError as error:
            return self.err(error)
        if not self.confirm(
            'Remove public links',
            f'Remove public links from {len(relative)} selected item(s)?\n\nLocal files are never changed.',
            'Remove links',
        ):
            return

        def task():
            client = self._nextcloud_client()
            removed = 0
            errors = []
            for path in relative:
                try:
                    for share in client.list_shares(path):
                        if str(share.get('share_type')) == '3':
                            client.delete_share(share.get('id'))
                            removed += 1
                except Exception as error:
                    errors.append(f'{path}: {error}')
            return removed, errors

        def done(result):
            removed, errors = result
            lines = [f'Removed {removed} public link(s).']
            if errors:
                lines += ['', 'Failures:'] + errors
            self.info('Nextcloud public links', '\n'.join(lines))

        self._run_task('Removing Nextcloud public links…', task, done, self.err)
