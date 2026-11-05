"""NIRUORG dialog base class, image viewer and preferences dialog."""

import shutil
from .base import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLineEdit,
    QPushButton,
    QTimer,
    Qt,
    THEMES,
)  # noqa: F401


class NiruDialog(QDialog):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            event.accept()
            return
        super().keyPressEvent(event)

    def showEvent(self, event):
        # Every ordinary NIRUORG popup must have an obvious keyboard/mouse exit.
        # Dialogs that already expose Close/Cancel/OK/Save keep their own controls.
        super().showEvent(event)
        if self.property('_niru_close_checked') or self.isFullScreen():
            return
        self.setProperty('_niru_close_checked', True)
        exits = ('close', 'cancel', 'ok', 'save', 'done')
        buttons = self.findChildren(QPushButton)
        if any(
            b.isVisible() and b.isEnabled() and b.text().replace('&', '').strip().lower() in exits
            for b in buttons
        ):
            return
        lay = self.layout()
        if lay is None:
            return
        close = QPushButton('Close', self)
        close.setObjectName('niruAutoClose')
        close.clicked.connect(self.reject)
        if isinstance(lay, QFormLayout):
            lay.addRow('', close)
        elif isinstance(lay, QBoxLayout):
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(close)
            lay.addLayout(row)
        elif isinstance(lay, QGridLayout):
            lay.addWidget(close, lay.rowCount(), max(0, lay.columnCount() - 1))


class ImageViewerDialog(NiruDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.escape_handler = None
        self.resize_handler = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.escape_handler:
            self.escape_handler()
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.resize_handler:
            QTimer.singleShot(0, self.resize_handler)


class Prefs(QDialog):
    def __init__(self, w):
        super().__init__(w)
        self.w = w
        self.old_theme = w.theme
        self.old_density = w.density
        self.setWindowTitle('NIRUORG Settings')
        self.setMinimumWidth(540)
        f = QFormLayout(self)
        f.setContentsMargins(22, 22, 22, 22)
        f.setSpacing(12)
        self.theme = QComboBox()
        self.theme.addItems(['Follow NIRUX', 'Follow Omarchy'] + list(THEMES) + ['System'])
        self.theme.setCurrentText(w.theme)
        self.term = QLineEdit(w.terminal)
        self.shell = QLineEdit(w.shell)
        self.confirm = QCheckBox('Require confirmation')
        self.confirm.setChecked(w.confirm_delete)
        self.density = QComboBox()
        self.density.addItems(['Compact', 'Normal', 'Relaxed'])
        self.density.setCurrentText(w.density)
        self.datefmt = QComboBox()
        self.datefmt.addItems(['Swedish', 'ISO', 'Compact', 'System'])
        self.datefmt.setCurrentText(w.date_format)
        self.restore = QCheckBox('Restore folders and split view on startup')
        self.restore.setChecked(w.restore_session)
        self.audio = QComboBox()
        self.audio.addItems(['NIRU Player (MPV backend)', 'System default', 'MPV', 'VLC', 'cmus'])
        self.audio.setCurrentText(getattr(w, 'audio_player', 'NIRU Player (MPV backend)'))
        f.addRow('Theme', self.theme)
        f.addRow('Density', self.density)
        f.addRow('Date & time', self.datefmt)
        f.addRow('Terminal', self.term)
        f.addRow('Shell', self.shell)
        f.addRow('Permanent delete', self.confirm)
        f.addRow('Session', self.restore)
        f.addRow('Audio playback', self.audio)
        integ = []
        for label, cmd in [
            ('MPV', 'mpv'),
            ('LocalSend', 'localsend'),
            ('fd', 'fd'),
            ('ripgrep', 'rg'),
            ('7-Zip', '7z'),
        ]:
            integ.append(
                f'{label}: {"available" if shutil.which(cmd) or (cmd=="fd" and shutil.which("fdfind")) else "not installed"}'
            )
        info = QLabel('Integrations\n' + '  ·  '.join(integ))
        info.setWordWrap(True)
        f.addRow(info)
        hint = QLabel('Theme and density preview live. Cancel restores the previous appearance.')
        hint.setObjectName('muted')
        hint.setWordWrap(True)
        f.addRow(hint)
        b = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        for button in b.buttons():
            button.setIcon(QIcon())
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        f.addRow(b)
        self.theme.currentTextChanged.connect(self.preview_theme)
        self.density.currentTextChanged.connect(self.preview_density)

    def preview_theme(self, v):
        self.w.theme = v
        self.w.apply_theme()
        self.w.refresh_views()

    def preview_density(self, v):
        self.w.density = v
        self.w.apply_theme()
        self.w.refresh_views()

    def reject(self):
        self.w.theme = self.old_theme
        self.w.density = self.old_density
        self.w.apply_theme()
        self.w.refresh_views()
        super().reject()

    def accept(self):
        self.w.theme = self.theme.currentText()
        self.w.terminal = self.term.text().strip()
        self.w.shell = self.shell.text().strip()
        self.w.confirm_delete = self.confirm.isChecked()
        self.w.density = self.density.currentText()
        self.w.date_format = self.datefmt.currentText()
        self.w.restore_session = self.restore.isChecked()
        self.w.audio_player = self.audio.currentText()
        self.w.save_settings()
        self.w.apply_theme()
        self.w.refresh_views()
        self.w.configure_theme_watcher()
        super().accept()
