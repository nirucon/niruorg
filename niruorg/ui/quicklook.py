"""Main window mixin: Quick Look panel, preview and properties."""

import mimetypes
import shutil
import stat
import tarfile
import zipfile
from .base import (
    QDockWidget,
    QImage,
    QLabel,
    QPixmap,
    QPlainTextEdit,
    QPushButton,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
    TaskWorker,
    human,
    run_detached,
)  # noqa: F401
from .dialogs import NiruDialog  # noqa: F401


class QuickLookMixin:
    """Main window mixin: Quick Look panel, preview and properties."""

    def build_quicklook(self):
        self.quickdock = QDockWidget('Quick Look', self)
        self.quickdock.setObjectName('quicklook')
        self.quickdock.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.quickdock.setMinimumWidth(280)
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(14, 14, 14, 14)
        self.quick_image = QLabel()
        self.quick_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.quick_image.setMinimumHeight(120)
        self.quick_image.setMaximumHeight(260)
        self.quick_name = QLabel('No selection')
        self.quick_name.setWordWrap(True)
        self.quick_meta = QLabel('')
        self.quick_meta.setWordWrap(True)
        self.quick_meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.quick_image)
        lay.addWidget(self.quick_name)
        lay.addWidget(self.quick_meta)
        lay.addStretch(1)
        self.quickdock.setWidget(box)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.quickdock)
        self.quickdock.hide()
        self.quickdock.visibilityChanged.connect(lambda *_: self.update_quicklook())
        self._quicklook_cache = {}
        self._quicklook_generation = 0
        self._quicklook_timer = QTimer(self)
        self._quicklook_timer.setSingleShot(True)
        self._quicklook_timer.timeout.connect(self._begin_quicklook)

    def toggle_quicklook(self):
        self.quicklook_requested = not self.quicklook_requested
        self.quickdock.setVisible(self.quicklook_requested)
        self.update_quicklook()

    def invalidate_quicklook(self, path=None):
        cache = getattr(self, '_quicklook_cache', None)
        if cache is None:
            return
        if path is None:
            cache.clear()
        else:
            cache.pop(str(path), None)

    def update_quicklook(self):
        if not hasattr(self, 'quickdock') or not getattr(self, 'quicklook_requested', False):
            return
        self._quicklook_generation += 1
        sel = self.selected()
        self.quick_image.clear()
        if len(sel) != 1:
            self.quick_name.setText('No selection' if not sel else f'{len(sel)} items selected')
            self.quick_meta.setText('')
            self._quicklook_timer.stop()
            return
        self.quick_name.setText(sel[0].name or str(sel[0]))
        self.quick_meta.setText('Loading…')
        self._quicklook_timer.start(160)

    def _begin_quicklook(self):
        if not getattr(self, 'quicklook_requested', False):
            return
        sel = self.selected()
        if len(sel) != 1:
            return
        p = sel[0]
        key = str(p)
        generation = self._quicklook_generation
        cached = self._quicklook_cache.get(key)
        if cached is not None:
            self._apply_quicklook(cached)
            return
        worker = TaskWorker(self._quicklook_payload, p)

        def done(result):
            if generation != self._quicklook_generation:
                return
            self._quicklook_cache[key] = result
            self._apply_quicklook(result)

        def failed(error):
            if generation == self._quicklook_generation:
                self.quick_meta.setText(str(error))

        worker.signals.done.connect(done)
        worker.signals.failed.connect(failed)
        self._start_worker(self.threadpool, worker, ('done', 'failed'))

    def _quicklook_payload(self, p):
        st = p.lstat()
        mime = mimetypes.guess_type(p.name)[0] or ('Folder' if p.is_dir() else 'File')
        result = {
            'path': str(p),
            'name': p.name or str(p),
            'mime': mime,
            'size': st.st_size,
            'mtime': st.st_mtime,
            'mode': st.st_mode,
            'dir': p.is_dir(),
        }
        if mime.startswith('image/') and not result['dir'] and st.st_size < 80 * 1024 * 1024:
            image = QImage(str(p))
            if not image.isNull():
                result['image'] = image
        elif mime.startswith(('audio/', 'video/')):
            result['media'] = self.media_info(p)
        elif (
            not result['dir']
            and st.st_size <= 256 * 1024
            and (
                mime.startswith('text/')
                or p.suffix.lower()
                in ('.md', '.py', '.js', '.ts', '.json', '.toml', '.yaml', '.yml', '.conf', '.ini')
            )
        ):
            try:
                result['text'] = p.read_text(errors='replace')[:1200].strip()
            except Exception:
                pass
        return result

    def _apply_quicklook(self, result):
        lines = [
            result['path'],
            f'Type: {result["mime"]}',
            f'Size: {"—" if result["dir"] else human(result["size"])}',
            f'Modified: {self.format_dt(result["mtime"])}',
            f'Permissions: {stat.filemode(result["mode"])}',
        ]
        image = result.get('image')
        if image is not None and not image.isNull():
            self.quick_image.setPixmap(
                QPixmap.fromImage(image).scaled(
                    250, 220, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation
                )
            )
            lines.append(f'Image: {image.width()} × {image.height()}')
        if result.get('media'):
            lines.append(result['media'])
        if result.get('text'):
            lines.append('\n' + result['text'])
        self.quick_name.setText(result['name'])
        self.quick_meta.setText('\n'.join(lines))

    def _preview_payload(self, p):
        st = p.lstat()
        mime = mimetypes.guess_type(p.name)[0] or ''
        result = {
            'path': str(p),
            'name': p.name,
            'mime': mime,
            'size': st.st_size,
            'mode': st.st_mode,
            'dir': p.is_dir(),
        }
        if p.is_file() and mime.startswith('image/'):
            image = QImage(str(p))
            if not image.isNull():
                result['image'] = image
        elif (
            p.is_file()
            and st.st_size < 3_000_000
            and (
                mime.startswith('text/')
                or mime in ('application/json', 'application/xml', 'application/javascript')
                or p.suffix.lower()
                in ('.md', '.py', '.js', '.ts', '.css', '.toml', '.yaml', '.yml', '.sh', '.fish')
            )
        ):
            result['text'] = p.read_text(errors='replace')
        elif p.is_file() and (mime.startswith('audio/') or mime.startswith('video/')):
            result['media'] = self.media_info(p)
        elif p.is_file() and (zipfile.is_zipfile(p) or tarfile.is_tarfile(p)):
            names = zipfile.ZipFile(p).namelist() if zipfile.is_zipfile(p) else tarfile.open(p).getnames()
            result['archive'] = '\n'.join(names[:1000]) + ('\n…' if len(names) > 1000 else '')
        return result

    def preview(self):
        s = self.selected()
        if len(s) != 1:
            return
        p = s[0]
        d = NiruDialog(self)
        d.setWindowTitle(f'Inspect — {p.name}')
        d.resize(800, 650)
        l = QVBoxLayout(d)
        l.addWidget(QLabel(f'<b>{p.name}</b>'))
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        l.addWidget(body, 1)
        status = QLabel('Loading…')
        status.setObjectName('muted')
        l.addWidget(status)

        def fill(result):
            while bl.count():
                item = bl.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            status.setText(
                f'{human(result["size"])} · {result["mime"] or ("Folder" if result["dir"] else "File")} · {stat.filemode(result["mode"])}'
            )
            if result.get('image') is not None:
                pix = QPixmap.fromImage(result['image'])
                lab = QLabel()
                lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lab.setPixmap(
                    pix.scaled(
                        740,
                        520,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                bl.addWidget(lab, 1)
                bl.addWidget(
                    QLabel(f'{pix.width()} × {pix.height()} · {human(result["size"])} · {result["mime"]}')
                )
            elif 'text' in result:
                e = QPlainTextEdit()
                e.setReadOnly(True)
                e.setPlainText(result['text'])
                bl.addWidget(e, 1)
            elif result.get('media') is not None:
                lab = QLabel(
                    (result['media'] or 'Media file')
                    + f'\n\nSize: {human(result["size"])}\nPath: {result["path"]}'
                )
                lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                bl.addWidget(lab)
                play = QPushButton('Play with MPV')
                play.clicked.connect(
                    lambda: run_detached([shutil.which('mpv'), str(p)])
                    if shutil.which('mpv')
                    else self.err('MPV is not installed.')
                )
                bl.addWidget(play)
                bl.addStretch()
            elif 'archive' in result:
                e = QPlainTextEdit()
                e.setReadOnly(True)
                e.setPlainText(result['archive'])
                bl.addWidget(e, 1)
            else:
                info = f'Type: {"Directory" if result["dir"] else result["mime"] or "File"}\nSize: {"—" if result["dir"] else human(result["size"])}\nPermissions: {stat.filemode(result["mode"])}\nPath: {result["path"]}'
                lab = QLabel(info)
                lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                bl.addWidget(lab)
                bl.addStretch()

        def failed(error):
            status.setText(str(error))

        worker = TaskWorker(self._preview_payload, p)
        worker.signals.done.connect(fill)
        worker.signals.failed.connect(failed)
        self._start_worker(self.threadpool, worker, ('done', 'failed'))
        d.exec()

    def properties(self):
        s = self.selected()
        if len(s) != 1:
            return
        p = s[0]
        try:
            st = p.lstat()
            typ = 'Directory' if p.is_dir() else (mimetypes.guess_type(p.name)[0] or 'File')
            size = '—' if p.is_dir() else human(st.st_size)
            target = f'\nTarget: {p.resolve()}' if p.is_symlink() else ''
            self.info(
                'Properties',
                f'{p.name}\n\nType: {typ}\nSize: {size}\nPermissions: {stat.filemode(st.st_mode)} ({oct(st.st_mode & 0o777)})\nOwner UID:GID: {st.st_uid}:{st.st_gid}\nModified: {self.format_dt(st.st_mtime)}\nPath: {p}{target}',
            )
        except Exception as e:
            self.err(e)
