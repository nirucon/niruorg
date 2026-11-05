"""Main window mixin: image viewer, gallery, slideshow and the NIRU Player."""

import json
import mimetypes
import os
import shutil
import socket
import time
from pathlib import Path
from .base import (
    QAbstractItemView,
    QDesktopServices,
    QHBoxLayout,
    QIcon,
    QKeySequence,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPixmap,
    QProcess,
    QPushButton,
    QShortcut,
    QSize,
    QSizePolicy,
    QSlider,
    QTimer,
    QUrl,
    QVBoxLayout,
    Qt,
    run_detached,
)  # noqa: F401
from .dialogs import ImageViewerDialog, NiruDialog  # noqa: F401


class MediaMixin:
    """Main window mixin: image viewer, gallery, slideshow and the NIRU Player."""

    def image_viewer(self, files, start=0, fullscreen=False, parent=None):
        files = [Path(x) for x in files]
        if not files:
            return
        d = ImageViewerDialog(parent or self)
        d.setWindowTitle('Gallery Focus')
        d.setStyleSheet(self.styleSheet())
        d.setModal(True)
        d.setMinimumSize(640, 420)
        lay = QVBoxLayout(d)
        lay.setContentsMargins(10, 10, 10, 8)
        lay.setSpacing(8)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        prev = QPushButton('Previous')
        nxt = QPushButton('Next')
        fit = QPushButton('100%')
        full = QPushButton('Exit fullscreen' if fullscreen else 'Fullscreen')
        close = QPushButton('Close')
        hint = QLabel('←/→ navigate   Space next   F fit/100%   F11 fullscreen   Esc back')
        hint.setObjectName('muted')
        toolbar.addWidget(prev)
        toolbar.addWidget(nxt)
        toolbar.addWidget(fit)
        toolbar.addStretch()
        toolbar.addWidget(hint)
        toolbar.addStretch()
        toolbar.addWidget(full)
        toolbar.addWidget(close)
        lay.addLayout(toolbar)
        lab = QLabel()
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setMinimumSize(1, 1)
        lab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        info = QLabel()
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setObjectName('muted')
        lay.addWidget(lab, 1)
        lay.addWidget(info)
        state = {
            'i': max(0, min(start, len(files) - 1)),
            'fit': True,
            'fullscreen': bool(fullscreen),
            'pix': QPixmap(),
        }

        def render():
            pix = state['pix']
            if pix.isNull():
                lab.clear()
                return
            if state['fit']:
                target = lab.contentsRect().size()
                shown = pix.scaled(
                    max(1, target.width()),
                    max(1, target.height()),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            else:
                shown = pix
            lab.setPixmap(shown)

        def show_image():
            p = files[state['i']]
            pix = QPixmap(str(p))
            state['pix'] = pix
            info.setText(f'{p.name}   ·   {pix.width()} × {pix.height()}   ·   {state["i"]+1}/{len(files)}')
            fit.setText('100%' if state['fit'] else 'Fit')
            render()

        def step(n):
            state.update(i=(state['i'] + n) % len(files))
            show_image()

        def toggle_fit():
            state.update(fit=not state['fit'])
            render()
            fit.setText('100%' if state['fit'] else 'Fit')

        def toggle_full():
            state['fullscreen'] = not state['fullscreen']
            if state['fullscreen']:
                d.showFullScreen()
                full.setText('Exit fullscreen')
            else:
                d.showNormal()
                d.resize(1100, 780)
                full.setText('Fullscreen')
            QTimer.singleShot(30, render)

        def escape():
            if state['fullscreen']:
                toggle_full()
            else:
                d.reject()

        d.escape_handler = escape
        d.resize_handler = lambda: render() if state['fit'] else None
        prev.clicked.connect(lambda: step(-1))
        nxt.clicked.connect(lambda: step(1))
        fit.clicked.connect(toggle_fit)
        full.clicked.connect(toggle_full)
        close.clicked.connect(d.reject)
        QShortcut(QKeySequence('Right'), d, activated=lambda: step(1))
        QShortcut(QKeySequence('Space'), d, activated=lambda: step(1))
        QShortcut(QKeySequence('Left'), d, activated=lambda: step(-1))
        QShortcut(QKeySequence('Backspace'), d, activated=lambda: step(-1))
        QShortcut(QKeySequence('Home'), d, activated=lambda: (state.update(i=0), show_image()))
        QShortcut(QKeySequence('End'), d, activated=lambda: (state.update(i=len(files) - 1), show_image()))
        QShortcut(QKeySequence('F'), d, activated=toggle_fit)
        QShortcut(QKeySequence('F11'), d, activated=toggle_full)
        if fullscreen:
            d.showFullScreen()
        else:
            d.resize(1100, 780)
        QTimer.singleShot(30, show_image)
        d.exec()

    def gallery(self):
        try:
            files = sorted(
                [
                    p
                    for p in self.current_dir().iterdir()
                    if p.is_file() and (mimetypes.guess_type(p.name)[0] or '').startswith('image/')
                ],
                key=lambda p: p.name.lower(),
            )
        except Exception as e:
            return self.err(e)
        if not files:
            return self.err('No images in this folder.')
        d = NiruDialog(self)
        d.setWindowTitle(f'Gallery — {self.current_dir().name}')
        d.resize(1040, 720)
        lay = QVBoxLayout(d)
        top = QHBoxLayout()
        summary = QLabel(f'<b>{self.current_dir().name}</b>   ·   {len(files)} images')
        summary.setObjectName('muted')
        focus = QPushButton('Focus / Fullscreen')
        slide = QPushButton('Slideshow')
        close = QPushButton('Close')
        top.addWidget(summary)
        top.addStretch()
        top.addWidget(QLabel('Enter/F11 focus · Esc close'))
        top.addWidget(focus)
        top.addWidget(slide)
        top.addWidget(close)
        lay.addLayout(top)
        w = QListWidget()
        w.setViewMode(QListView.ViewMode.IconMode)
        w.setResizeMode(QListView.ResizeMode.Adjust)
        w.setMovement(QListView.Movement.Static)
        w.setIconSize(QSize(144, 108))
        w.setGridSize(QSize(176, 146))
        w.setWordWrap(True)
        w.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        placeholder = self.active.icons._icon('image')
        for p in files:
            it = QListWidgetItem(placeholder, p.name)
            it.setData(Qt.ItemDataRole.UserRole, str(p))
            w.addItem(it)
        state = {'i': 0}

        def batch():
            stop = min(state['i'] + 8, len(files))
            for i in range(state['i'], stop):
                pix = QPixmap(str(files[i]))
                if not pix.isNull():
                    w.item(i).setIcon(
                        QIcon(
                            pix.scaled(
                                144,
                                108,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                        )
                    )
            state['i'] = stop
            if stop < len(files):
                QTimer.singleShot(1, batch)

        def idx():
            return max(0, w.currentRow())

        def open_focus(*_):
            self.image_viewer(files, idx(), True, d)

        w.itemDoubleClicked.connect(open_focus)
        focus.clicked.connect(open_focus)
        slide.clicked.connect(lambda: self.image_viewer(files, idx(), True, d))
        close.clicked.connect(d.accept)
        QShortcut(QKeySequence('Return'), d, activated=open_focus)
        QShortcut(QKeySequence('F11'), d, activated=open_focus)
        lay.addWidget(w, 1)
        QTimer.singleShot(0, batch)
        d.exec()

    def slideshow(self):
        files = sorted(
            [
                p
                for p in self.current_dir().iterdir()
                if p.is_file() and (mimetypes.guess_type(p.name)[0] or '').startswith('image/')
            ],
            key=lambda p: p.name.lower(),
        )
        if not files:
            return self.err('No images in this folder.')
        self.image_viewer(files, 0, True)

    def niru_player(self, files=None, start=0):
        files = files or self._audio_files()
        if not files:
            return self.err('Select an audio file, or open a folder containing music.')
        exe = shutil.which('mpv')
        if not exe:
            return self.err(
                'NIRU Player uses MPV as its playback backend. Install mpv, or choose another player in Settings → Audio playback.'
            )
        d = NiruDialog(self)
        d.setWindowTitle('NIRU Player')
        d.resize(680, 300)
        d.setMinimumWidth(560)
        l = QVBoxLayout(d)
        l.setContentsMargins(24, 20, 24, 18)
        l.setSpacing(10)
        head = QHBoxLayout()
        now = QLabel('NOW PLAYING')
        now.setObjectName('muted')
        queue = QLabel()
        queue.setObjectName('muted')
        queue.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        head.addWidget(now)
        head.addStretch()
        head.addWidget(queue)
        l.addLayout(head)
        title = QLabel()
        title.setWordWrap(True)
        title.setStyleSheet('font-size: 18px; font-weight: 600;')
        meta = QLabel()
        meta.setObjectName('muted')
        meta.setWordWrap(True)
        l.addWidget(title)
        l.addWidget(meta)
        l.addSpacing(8)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 1000)
        slider.setMinimumHeight(22)
        l.addWidget(slider)
        timeline = QHBoxLayout()
        elapsed = QLabel('00:00')
        elapsed.setObjectName('muted')
        duration = QLabel('00:00')
        duration.setObjectName('muted')
        timeline.addWidget(elapsed)
        timeline.addStretch()
        timeline.addWidget(duration)
        l.addLayout(timeline)
        row = QHBoxLayout()
        row.setSpacing(6)
        prev = QPushButton('Previous')
        play = QPushButton('Pause')
        nxt = QPushButton('Next')
        stop = QPushButton('Stop')
        close = QPushButton('Close')
        row.addWidget(prev)
        row.addWidget(play)
        row.addWidget(nxt)
        row.addWidget(stop)
        row.addStretch()
        row.addWidget(QLabel('Space play/pause   ←/→ ±10 s'))
        row.addStretch()
        row.addWidget(close)
        l.addLayout(row)
        state = {'i': max(0, min(start, len(files) - 1)), 'drag': False, 'manual': False, 'paused': False}
        runtime = (
            Path(os.getenv('XDG_RUNTIME_DIR', '/tmp'))
            / f'niruorg-mpv-{os.getpid()}-{int(time.time()*1000)}.sock'
        )
        proc = QProcess(d)
        proc.setProgram(exe)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        def fmt(v):
            try:
                v = max(0, int(float(v)))
                return f'{v//60:02d}:{v%60:02d}'
            except:
                return '00:00'

        def command(cmd):
            try:
                c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                c.settimeout(0.15)
                c.connect(str(runtime))
                c.sendall((json.dumps({'command': cmd}) + '\n').encode())
                c.close()
                return True
            except:
                return False

        def launch(i):
            state['i'] = i % len(files)
            state['manual'] = False
            state['paused'] = False
            p = files[state['i']]
            title.setText(p.stem)
            meta.setText(f'{p.parent.name}   ·   {p.suffix[1:].upper()}')
            queue.setText(f'{state["i"]+1} / {len(files)}')
            play.setText('Pause')
            elapsed.setText('00:00')
            duration.setText('00:00')
            slider.setValue(0)
            proc.setArguments(
                ['--no-video', '--really-quiet', '--input-ipc-server=' + str(runtime), '--', str(p)]
            )
            proc.start()

        def next_track(n=1):
            state['manual'] = True
            if proc.state() != QProcess.ProcessState.NotRunning:
                proc.kill()
                proc.waitForFinished(300)
            try:
                runtime.unlink(missing_ok=True)
            except:
                pass
            launch((state['i'] + n) % len(files))

        def poll():
            if proc.state() == QProcess.ProcessState.NotRunning:
                return
            try:
                c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                c.settimeout(0.08)
                c.connect(str(runtime))
                c.sendall(
                    (
                        json.dumps({'command': ['get_property', 'time-pos']})
                        + '\n'
                        + json.dumps({'command': ['get_property', 'duration']})
                        + '\n'
                    ).encode()
                )
                raw = b''
                while raw.count(b'\n') < 2:
                    raw += c.recv(4096)
                c.close()
                vals = [json.loads(x).get('data') for x in raw.splitlines()[:2]]
                pos, dur = vals
                if dur and not state['drag']:
                    slider.setValue(int(max(0, min(1, float(pos or 0) / float(dur))) * 1000))
                elapsed.setText(fmt(pos))
                duration.setText(fmt(dur))
            except:
                pass

        def toggle():
            if command(['cycle', 'pause']):
                state['paused'] = not state['paused']
                play.setText('Play' if state['paused'] else 'Pause')

        def seek(v):
            try:
                c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                c.settimeout(0.1)
                c.connect(str(runtime))
                c.sendall((json.dumps({'command': ['get_property', 'duration']}) + '\n').encode())
                dur = json.loads(c.recv(4096).splitlines()[0]).get('data')
                c.close()
                if dur:
                    command(['set_property', 'time-pos', float(dur) * v / 1000])
            except:
                pass

        def stop_playback():
            state['manual'] = True
            proc.kill()
            slider.setValue(0)
            elapsed.setText('00:00')
            play.setText('Play')
            state['paused'] = True

        def finished(*_):
            if state['manual']:
                state['manual'] = False
                return
            if d.isVisible():
                QTimer.singleShot(120, lambda: launch((state['i'] + 1) % len(files)))

        play.clicked.connect(toggle)
        prev.clicked.connect(lambda: next_track(-1))
        nxt.clicked.connect(lambda: next_track(1))
        stop.clicked.connect(stop_playback)
        close.clicked.connect(d.accept)
        slider.sliderPressed.connect(lambda: state.update(drag=True))
        slider.sliderReleased.connect(lambda: (seek(slider.value()), state.update(drag=False)))
        proc.finished.connect(finished)
        timer = QTimer(d)
        timer.timeout.connect(poll)
        timer.start(400)
        QShortcut(QKeySequence('Space'), d, activated=toggle)
        QShortcut(QKeySequence('Right'), d, activated=lambda: command(['seek', 10, 'relative']))
        QShortcut(QKeySequence('Left'), d, activated=lambda: command(['seek', -10, 'relative']))
        launch(state['i'])
        d.exec()
        timer.stop()
        state['manual'] = True
        proc.kill()
        proc.waitForFinished(300)
        try:
            runtime.unlink(missing_ok=True)
        except:
            pass

    def _audio_files(self):
        exts = {'.mp3', '.flac', '.ogg', '.opus', '.m4a', '.aac', '.wav', '.wma', '.ape'}
        selected = [p for p in self.selected() if p.is_file() and p.suffix.lower() in exts]
        if selected:
            return selected
        try:
            return sorted(
                [p for p in self.current_dir().iterdir() if p.is_file() and p.suffix.lower() in exts],
                key=lambda p: p.name.lower(),
            )
        except:
            return []

    def mpv(self):
        s = self.selected()
        exe = shutil.which('mpv')
        if not exe:
            return self.err('MPV is not installed.')
        items = s or [self.current_dir()]
        run_detached([exe] + [str(x) for x in items])

    def play_audio(self):
        files = self._audio_files()
        if not files:
            return self.err('Select an audio file, or open a folder containing music.')
        pref = getattr(self, 'audio_player', 'NIRU Player (MPV backend)')
        if pref.startswith('NIRU Player'):
            return self.niru_player(files, 0)
        if pref == 'System default':
            return QDesktopServices.openUrl(QUrl.fromLocalFile(str(files[0])))
        cmd = {'MPV': 'mpv', 'VLC': 'vlc', 'cmus': 'cmus'}.get(pref)
        exe = shutil.which(cmd) if cmd else None
        if not exe:
            return self.err(f'{pref} is not installed.')
        if pref == 'cmus':
            if self.terminal and 'kitty' in self.terminal:
                return run_detached([self.terminal, '-e', exe, str(files[0])])
            return run_detached([exe, str(files[0])])
        run_detached([exe] + [str(x) for x in files])
