"""Background workers (remote probes, discovery, metadata, diagnostics, search)."""

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from .base import QObject, QRunnable, Signal, mounted_paths, path_is_mounted  # noqa: F401


class RemoteProbeSignals(QObject):
    done = Signal(object)


class RemoteProbeWorker(QRunnable):
    """Probe a FUSE path outside the GUI thread with a strict subprocess timeout."""

    def __init__(self, token, path, mount):
        super().__init__()
        self.token = token
        self.path = str(path)
        self.mount = str(mount)
        self.signals = RemoteProbeSignals()

    def run(self):
        result = {
            'token': self.token,
            'path': self.path,
            'mount': self.mount,
            'ok': False,
            'detail': 'Unavailable',
        }
        if not path_is_mounted(self.mount):
            result['detail'] = 'Offline'
            self.signals.done.emit(result)
            return
        statbin = shutil.which('stat') or '/usr/bin/stat'
        try:
            r = subprocess.run(
                [statbin, '-L', '--format=%F', self.path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2.5,
            )
            result['ok'] = r.returncode == 0
            result['detail'] = 'Connected' if result['ok'] else 'Unavailable'
        except subprocess.TimeoutExpired:
            result['detail'] = 'Unavailable · timed out'
        except Exception as e:
            result['detail'] = 'Unavailable · ' + str(e)
        self.signals.done.emit(result)


class DiscoverySignals(QObject):
    done = Signal(object)


class DiscoveryWorker(QRunnable):
    """Discover external integrations without touching remote/FUSE paths."""

    def __init__(self):
        super().__init__()
        self.signals = DiscoverySignals()

    def run(self):
        result = {'cloud': [], 'types': {}, 'devices': []}
        exe = shutil.which('rclone')
        if exe:
            try:
                r = subprocess.run([exe, 'listremotes'], capture_output=True, text=True, timeout=4)
                if r.returncode == 0:
                    result['cloud'] = [x.strip().rstrip(':') for x in r.stdout.splitlines() if x.strip()]
            except Exception:
                pass
        # Mount-table metadata only: never dereference external/FUSE paths here.
        for mp in mounted_paths():
            if mp.startswith('/mnt/') or mp.startswith('/run/media/') or mp.startswith('/media/'):
                result['devices'].append(mp)
        self.signals.done.emit(result)


class MetadataSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class MetadataWorker(QRunnable):
    """Bounded metadata discovery. Remote/FUSE paths are only touched in subprocesses with timeouts."""

    def __init__(self, mode, payload):
        super().__init__()
        self.mode = mode
        self.payload = payload
        self.signals = MetadataSignals()

    def _remote_stat(self, path, timeout=2.5):
        statbin = shutil.which('stat') or '/usr/bin/stat'
        try:
            r = subprocess.run(
                [statbin, '-L', '--format=%F\\t%s\\t%Y', str(path)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if r.returncode != 0:
                return {'state': 'missing'}
            parts = r.stdout.strip().split('\\t')
            typ = parts[0] if parts else ''
            return {
                'state': 'available',
                'dir': 'directory' in typ.lower(),
                'size': int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0,
                'mtime': float(parts[2]) if len(parts) > 2 else 0,
            }
        except subprocess.TimeoutExpired:
            return {'state': 'offline'}
        except Exception:
            return {'state': 'unavailable'}

    def _local_stat(self, path):
        try:
            p = Path(path)
            st = p.stat()
            return {'state': 'available', 'dir': p.is_dir(), 'size': st.st_size, 'mtime': st.st_mtime}
        except FileNotFoundError:
            return {'state': 'missing'}
        except OSError:
            return {'state': 'unavailable'}

    def _stat(self, item):
        if item.get('remote') and not item.get('mounted'):
            return {'state': 'offline'}
        return self._remote_stat(item['path']) if item.get('remote') else self._local_stat(item['path'])

    def _list(self, side):
        path = side['path']
        if side.get('remote') and not side.get('mounted'):
            return None, 'Offline'
        if side.get('remote'):
            find = shutil.which('find') or '/usr/bin/find'
            try:
                r = subprocess.run(
                    [find, path, '-mindepth', '1', '-maxdepth', '1', '-printf', '%f\\t%y\\t%s\\t%T@\\n'],
                    capture_output=True,
                    text=True,
                    timeout=4,
                )
                if r.returncode != 0:
                    return None, 'Unavailable'
                out = {}
                for line in r.stdout.splitlines():
                    parts = line.split('\\t')
                    if len(parts) >= 4:
                        name, typ, size, mt = parts[:4]
                        out[name] = {'dir': typ == 'd', 'size': int(size or 0), 'mtime': float(mt or 0)}
                return out, None
            except subprocess.TimeoutExpired:
                return None, 'Timed out'
            except Exception as e:
                return None, str(e)
        try:
            out = {}
            with os.scandir(path) as it:
                for e in it:
                    try:
                        st = e.stat(follow_symlinks=False)
                        out[e.name] = {
                            'dir': e.is_dir(follow_symlinks=False),
                            'size': st.st_size,
                            'mtime': st.st_mtime,
                        }
                    except OSError:
                        out[e.name] = {'dir': False, 'size': 0, 'mtime': 0}
            return out, None
        except Exception as e:
            return None, str(e)

    def run(self):
        try:
            if self.mode == 'basket':
                rows = []
                for item in self.payload:
                    rows.append(dict(item, meta=self._stat(item)))
                self.signals.done.emit({'mode': 'basket', 'rows': rows})
                return
            if self.mode == 'conflicts':
                conflicts = []
                for item in self.payload:
                    meta = self._stat(item)
                    if meta.get('state') == 'available':
                        conflicts.append(item['path'])
                self.signals.done.emit({'mode': 'conflicts', 'conflicts': conflicts})
                return
            if self.mode == 'compare':
                left, le = self._list(self.payload['left'])
                right, re = self._list(self.payload['right'])
                self.signals.done.emit(
                    {'mode': 'compare', 'left': left, 'right': right, 'left_error': le, 'right_error': re}
                )
                return
        except Exception as e:
            self.signals.failed.emit(str(e))


class StartupTrace:
    def __init__(self):
        self.t0 = time.perf_counter()
        self.last = self.t0
        self.path = Path.home() / '.local/state/niruorg/startup.log'
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def mark(self, label):
        now = time.perf_counter()
        total = (now - self.t0) * 1000
        delta = (now - self.last) * 1000
        self.last = now
        try:
            with self.path.open('a', encoding='utf-8') as f:
                f.write(
                    f'{time.strftime("%Y-%m-%d %H:%M:%S")}  {label:<30} {total:8.1f} ms  (+{delta:.1f})\n'
                )
        except Exception:
            pass


class WorkerSignals(QObject):
    progress = Signal(int, int, str)
    activity = Signal(object)
    done = Signal(object)
    failed = Signal(str)


class ConnectionDiagnosticSignals(QObject):
    done = Signal(object)


class ConnectionDiagnosticWorker(QRunnable):
    def __init__(self, name, cfg):
        super().__init__()
        self.name = name
        self.cfg = dict(cfg)
        self.signals = ConnectionDiagnosticSignals()

    def run(self):
        v = self.cfg
        host = v.get('host', '').strip()
        port = int(v.get('port', 22))
        timeout = max(2, min(8, int(v.get('timeout', 12))))
        rows = []

        def add(stage, ok, detail):
            rows.append((stage, bool(ok), str(detail)))

        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            ips = []
            for info in infos:
                ip = info[4][0]
                if ip not in ips:
                    ips.append(ip)
            add('DNS / host', True, ', '.join(ips[:4]))
        except Exception as e:
            add('DNS / host', False, e)
            self.signals.done.emit(rows)
            return
        if v.get('route', 'direct').startswith('tailscale'):
            ts = shutil.which('tailscale')
            if not ts:
                add('Tailscale', False, 'tailscale CLI is not installed')
            else:
                try:
                    r = subprocess.run(
                        [ts, 'ping', '--c', '1', '--timeout', '3s', host],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    out = (r.stdout or r.stderr).strip().splitlines()
                    add('Tailscale', r.returncode == 0, out[-1] if out else f'exit {r.returncode}')
                except Exception as e:
                    add('Tailscale', False, e)
        try:
            with socket.create_connection((host, port), timeout=min(4, timeout)) as sock:
                peer = sock.getpeername()
                add(f'TCP/{port}', True, f'{peer[0]}:{peer[1]} accepted connection')
        except Exception as e:
            add(f'TCP/{port}', False, e)
            self.signals.done.emit(rows)
            return
        if v.get('protocol', 'sftp').lower() == 'sftp':
            ssh = shutil.which('ssh')
            if not ssh:
                add('OpenSSH', False, 'ssh client is not installed')
            else:
                dest = (f'{v.get("user")}@' if v.get('user') else '') + host
                args = [
                    ssh,
                    '-p',
                    str(port),
                    '-o',
                    f'ConnectTimeout={timeout}',
                    '-o',
                    'BatchMode=yes',
                    '-o',
                    'ServerAliveCountMax=1',
                ]
                pj = v.get('proxyjump', '').strip()
                if pj:
                    args += ['-J', pj]
                if v.get('auth', 'auto').lower() == 'key' and v.get('key'):
                    key = str(Path(os.path.expanduser(v.get('key'))))
                    args += ['-i', key, '-o', 'IdentitiesOnly=yes']
                args += [dest, 'true']
                try:
                    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout + 3)
                    out = (r.stderr or r.stdout).strip()
                    low = out.lower()
                    if r.returncode == 0:
                        add('SSH authentication', True, 'public-key / OpenSSH authentication succeeded')
                    elif 'permission denied' in low or 'publickey' in low:
                        add(
                            'SSH authentication',
                            False,
                            (out[-500:] if out else 'authentication rejected')
                            + ' · unlock the SSH key or check the configured identity',
                        )
                    else:
                        add('SSH handshake', False, out[-500:] if out else f'ssh exited {r.returncode}')
                except subprocess.TimeoutExpired:
                    add('SSH handshake', False, 'timed out')
                except Exception as e:
                    add('SSH handshake', False, e)
        self.signals.done.emit(rows)


class SearchWorker(QRunnable):
    def __init__(self, base, term, content=False, hidden=False, generation=0):
        super().__init__()
        self.base = Path(base)
        self.term = term
        self.content = content
        self.hidden = hidden
        self.generation = generation
        self.signals = WorkerSignals()
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        paths = []
        try:
            if self.content:
                exe = shutil.which('rg')
                if not exe:
                    raise RuntimeError('ripgrep is required for content search.')
                args = (
                    [exe, '-l', '--no-messages', '--max-count', '1']
                    + (['--hidden'] if self.hidden else [])
                    + ['--', self.term, str(self.base)]
                )
            else:
                exe = shutil.which('fd') or shutil.which('fdfind')
                args = (
                    (
                        [exe, '--color', 'never', '--max-results', '2000']
                        + (['--hidden'] if self.hidden else [])
                        + ['--', self.term, str(self.base)]
                    )
                    if exe
                    else None
                )
            if args:
                proc = subprocess.Popen(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                for line in proc.stdout:
                    if self.cancelled:
                        proc.terminate()
                        break
                    raw = line.rstrip('\n')
                    if raw:
                        paths.append(raw)
                        self.signals.progress.emit(len(paths), 2000, raw)
                    if len(paths) >= 2000:
                        proc.terminate()
                        break
                proc.wait(timeout=2)
            else:
                needle = self.term.casefold()
                for root, dirs, files in os.walk(self.base):
                    if self.cancelled:
                        break
                    if not self.hidden:
                        dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for name in dirs + files:
                        if needle in name.casefold():
                            raw = str(Path(root) / name)
                            paths.append(raw)
                            self.signals.progress.emit(len(paths), 2000, raw)
                            if len(paths) >= 2000:
                                break
                    if len(paths) >= 2000:
                        break
            self.signals.done.emit(
                {'generation': self.generation, 'paths': paths, 'cancelled': self.cancelled}
            )
        except Exception as e:
            self.signals.failed.emit(str(e))
