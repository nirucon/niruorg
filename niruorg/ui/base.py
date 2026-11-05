"""Shared imports, themes and archive/process helpers for the NIRUORG UI modules."""

import os, sys, shutil, subprocess, mimetypes, zipfile, tarfile, stat, json, urllib.request, urllib.parse, base64, shlex, socket, tempfile, time, re, hashlib, uuid, xml.etree.ElementTree as ET
from pathlib import Path
from PySide6.QtCore import (
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
    from ..transfer_safety import TransferSafetyError, verified_partial_offset, guard_transfer_locations
    from ..utils.workers import TaskWorker
    from ..services.theme import default_theme, load_nirux_metrics, load_nirux_palette
    from ..services.theme_watcher import ThemeWatcher
    from ..services.nextcloud import NextcloudClient, NextcloudError
    from ..services.local_watcher import LocalDirectoryWatcher
    from ..core.rename import RenameError, execute_bulk_rename, plan_bulk_rename
    from ..core.paths import mounted_paths, path_is_mounted, lexical_under
    from ..utils.format import human
    from ..utils.logging import log_error
    from .directory_model import DirectoryModel
except (ImportError, ValueError):  # app.py run directly: niruorg/ is on sys.path
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

THEMES = {
    'Niru Noir': {
        'bg': '#090909',
        'fg': '#ededed',
        'muted': '#858585',
        'panel': '#141414',
        'surface': '#1b1b1b',
        'border': '#292929',
        'accent': '#bdbdbd',
        'accentfg': '#090909',
        'sel': '#333333',
        'danger': '#d56b6b',
    },
    'C. Larsson': {
        'bg': '#eee5d1',
        'fg': '#29251f',
        'muted': '#776d5e',
        'panel': '#e2d3b7',
        'surface': '#e8dcc5',
        'border': '#bbaa8d',
        'accent': '#745c3e',
        'accentfg': '#fffaf0',
        'sel': '#d3c19f',
        'danger': '#9c3d32',
    },
    'Satie': {
        'bg': '#ddd5c4',
        'fg': '#292b29',
        'muted': '#737168',
        'panel': '#cbc2af',
        'surface': '#d3cbb9',
        'border': '#aaa18f',
        'accent': '#4f4c45',
        'accentfg': '#f5f0e7',
        'sel': '#bbb6a9',
        'danger': '#8b4a46',
    },
    'Nord': {
        'bg': '#2e3440',
        'fg': '#eceff4',
        'muted': '#9aa4b2',
        'panel': '#3b4252',
        'surface': '#434c5e',
        'border': '#4c566a',
        'accent': '#88c0d0',
        'accentfg': '#2e3440',
        'sel': '#434c5e',
        'danger': '#bf616a',
    },
}


def _safe_archive_target(base, name):
    base = Path(base).resolve()
    target = (base / name).resolve()
    if target != base and base not in target.parents:
        raise RuntimeError(f'Unsafe archive path blocked: {name}')
    return target


def safe_extract_zip(archive, out, members=None):
    base = Path(out).resolve()
    base.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        chosen = z.infolist() if members is None else [z.getinfo(n) for n in members]
        for info in chosen:
            _safe_archive_target(base, info.filename)
            # ZIP symlinks can point outside the destination; do not materialize them.
            mode = (info.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK:
                raise RuntimeError(f'Archive symlink blocked: {info.filename}')
        for info in chosen:
            z.extract(info, base)


def safe_extract_tar(archive, out, members=None):
    base = Path(out).resolve()
    base.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as t:
        chosen = t.getmembers() if members is None else [t.getmember(n) for n in members]
        for m in chosen:
            _safe_archive_target(base, m.name)
            if m.issym() or m.islnk():
                raise RuntimeError(f'Archive link blocked: {m.name}')
        t.extractall(base, members=chosen, filter='data')


def run_detached(args, cwd=None, env=None):
    try:
        pe = os.environ.copy()
        pe.update(env or {})
        subprocess.Popen(
            args,
            cwd=cwd,
            env=pe,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def omarchy_palette():
    candidates = [
        Path.home() / '.local/state/omarchy/current/theme/colors.toml',
        Path.home() / '.local/state/omarchy/current/colors.toml',
    ]
    p = next((x for x in candidates if x.exists()), None)
    if not p:
        return None
    vals = {}
    try:
        for line in p.read_text(errors='ignore').splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                vals[k.strip()] = v.strip().strip('"\'')

        def c(*keys, default):
            for k in keys:
                v = vals.get(k)
                if v and v.startswith('#'):
                    return v
            return default

        bg = c('background', default='#090909')
        fg = c('foreground', default='#ededed')
        accent = c('accent', 'color4', 'blue', default='#bdbdbd')
        return {
            'bg': bg,
            'fg': fg,
            'muted': c('color8', 'bright_black', default='#858585'),
            'panel': c('color0', 'black', default='#141414'),
            'surface': c('color0', 'black', default='#1b1b1b'),
            'border': c('color8', 'bright_black', default='#292929'),
            'accent': accent,
            'accentfg': bg,
            'sel': c('selection_background', 'color8', default='#333333'),
            'danger': c('color1', 'red', default='#d56b6b'),
        }
    except:
        return None
