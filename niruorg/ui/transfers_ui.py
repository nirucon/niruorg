"""Main window mixin: transfer UI (progress bar, conflicts, queue, history, undo) and clipboard."""

import shutil
import time
from pathlib import Path
from .base import (
    QHeaderView,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTimer,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    human,
)  # noqa: F401
from .dialogs import NiruDialog  # noqa: F401
from .workers import MetadataWorker  # noqa: F401
from .transfer import TransferWorker  # noqa: F401


class TransferUIMixin:
    """Main window mixin: transfer UI (progress bar, conflicts, queue, history, undo) and clipboard."""

    def copy(self):
        self.clip = self.selected()
        self.cut_mode = False
        self.update_status()

    def cut(self):
        self.clip = self.selected()
        self.cut_mode = True
        self.update_status()

    def paste(self):
        if not self.clip:
            return
        self.start_transfer(list(self.clip), self.current_dir(), self.cut_mode)
        if self.cut_mode:
            self.clip = []
            self.cut_mode = False

    def _transfer_to_other_pane(self, move=False, items=None):
        if not self.pane2.isVisible():
            return self.err('Enable Split View first (Ctrl+2).')
        src = self.active
        dst = self.pane2 if src is self.pane1 else self.pane1
        items = list(items or src.selected())
        if not items:
            return
        verb = 'Move' if move else 'Copy'
        target = self.pane_target_label(dst)
        if src.is_remote() or dst.is_remote() or move:
            if not self.confirm(
                f'{verb} to {self.other_side(src)} pane', f'{verb} {len(items)} item(s) →\n{target}?', verb
            ):
                return
        self.start_transfer(items, dst.current, move, self.pane_target_label(src), target)

    def send_other_pane(self):
        self._transfer_to_other_pane(False)

    def move_other_pane(self):
        self._transfer_to_other_pane(True)

    def handle_pane_drop(self, dst, items, drop_action, src=None, target_dir=None):
        # Cross-pane DnD is an explicit copy operation. Do not route it through
        # whichever pane happened to be active: Wayland focus can change during drag.
        src = src or (self.pane2 if dst is self.pane1 else self.pane1)
        target = Path(target_dir or dst.current)
        items = [Path(x) for x in items]
        if not items:
            return
        source_label = self.pane_target_label(src) if src in (self.pane1, self.pane2) else 'External'
        dest_label = self.pane_target_label(dst)
        # Drag-and-drop copy is already an explicit user action and is non-destructive
        # to the source. Do not add a second confirmation step. This also avoids a
        # modal-dialog round trip in the DnD path. Existing-name conflicts are still
        # handled explicitly by the transfer conflict policy.
        self.set_active(dst)
        self.start_transfer(items, target, False, source_label, dest_label)

    def choose_conflict_policy(self, conflicts, dst=None):
        if not conflicts:
            return 'ask'
        box = QMessageBox(self)
        box.setWindowTitle('Name conflict')
        box.setText(f'{len(conflicts)} item(s) already exist in the destination.')
        box.setInformativeText('Choose how NIRUORG should handle conflicts for this operation.')
        rep = box.addButton('Replace', QMessageBox.ButtonRole.DestructiveRole)
        keep = box.addButton('Keep both', QMessageBox.ButtonRole.AcceptRole)
        skip = box.addButton('Skip existing', QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(keep)
        box.exec()
        b = box.clickedButton()
        return 'replace' if b is rep else 'keepboth' if b is keep else 'skip' if b is skip else None

    def _cancel_visible_transfer(self):
        worker = self._visible_transfer
        if worker in self.operations:
            worker.cancel()
            self.transfer_title.setText('Cancelling…')
            self.transfer_cancel.setEnabled(False)

    def _render_transfer(self, worker):
        state = self._transfer_states.get(worker)
        if not state:
            return
        self._visible_transfer = worker
        self.transfer_bar.show()
        self.transfer_cancel.setEnabled(not worker.cancelled)
        count = len(self.operations)
        prefix = f'{count} transfers · ' if count > 1 else ''
        self.transfer_title.setText(prefix + state['title'])
        bd, bt = state.get('bytes_done', 0), state.get('bytes_total', 0)
        if bt > 0:
            self.progress.setRange(0, 1000)
            self.progress.setValue(min(1000, int(bd * 1000 / bt)))
            detail = f"{state.get('name','')} · {human(bd)} / {human(bt)}"
            rate = state.get('rate', 0)
            if rate > 0:
                detail += f' · {human(rate)}/s'
                remain = max(0, bt - bd)
                eta = remain / rate if rate else 0
                if eta >= 1:
                    detail += f' · ~{int(eta)} s left'
        else:
            done, total = state.get('done', 0), state.get('total', 1)
            self.progress.setRange(0, max(1, total))
            self.progress.setValue(done)
            detail = f"{done}/{total} · {state.get('name','')}"
        self.transfer_detail.setText(detail.strip(' ·'))

    def _finish_transfer_ui(self, worker, message, error=False):
        self._transfer_states.pop(worker, None)
        if worker in self.operations:
            self.operations.remove(worker)
        if self.operations:
            self._render_transfer(self.operations[-1])
        else:
            self._visible_transfer = None
            self.transfer_bar.hide()
            if self._close_after_transfers:
                QTimer.singleShot(0, self.close)
        if not error:
            self.status.setText(message)

    def start_transfer(self, items, dst, move=False, source_label=None, dest_label=None):
        items = [Path(x) for x in items]
        dst = Path(dst)
        if not items:
            return
        # Conflict discovery is metadata I/O and may hit FUSE. Always perform it away from the GUI thread.
        payload = []
        for x in items:
            target = dst / x.name
            payload.append(self._path_endpoint_meta(target))
        self.status.setText('Checking destination…')
        worker = MetadataWorker('conflicts', payload)

        def ready(r):
            if not self._accept_worker_results:
                return
            conflicts = r.get('conflicts', [])
            policy = self.choose_conflict_policy(conflicts, dst)
            if policy is None:
                self.update_status()
                return
            self._start_transfer_ready(items, dst, move, source_label, dest_label, policy)

        worker.signals.done.connect(ready)
        worker.signals.failed.connect(lambda e: self.err('Could not inspect destination safely: ' + str(e)))
        self._start_worker(self._remote_probe_pool, worker)

    def _start_transfer_ready(self, items, dst, move=False, source_label=None, dest_label=None, policy='ask'):
        items = [Path(x) for x in items]
        dst = Path(dst)
        if not items:
            return
        # Local-only free-space preflight. Remote/FUSE capacity checks must never block the GUI thread.
        if not self._remote_path(dst) and all(not self._remote_path(x) for x in items):
            try:
                required = sum(x.stat().st_size for x in items if x.is_file())
                free = shutil.disk_usage(dst if dst.exists() else dst.parent).free
                if required and required > free:
                    return self.err(
                        f'Not enough free space.\n\nRequired: {human(required)}\nAvailable: {human(free)}'
                    )
            except OSError:
                pass
        worker = TransferWorker(items, dst, move, policy)
        self.operations.append(worker)
        route = f'{source_label} → {dest_label}' if source_label and dest_label else str(dst)
        verb = 'Moving' if move else 'Copying'
        state = {
            'title': f'{verb} {len(items)} item(s) · {route}',
            'done': 0,
            'total': max(1, len(items)),
            'name': 'Preparing…',
            'bytes_done': 0,
            'bytes_total': 0,
            'sample_t': time.monotonic(),
            'sample_b': 0,
            'rate': 0.0,
        }
        self._transfer_states[worker] = state
        self._render_transfer(worker)

        def transfer_progress(done, total, name):
            state.update(done=done, total=max(1, total), name=name)
            if state.get('bytes_total', 0) <= 0:
                self._render_transfer(worker)

        def activity(info):
            now = time.monotonic()
            bd = int(info.get('bytes_done', 0))
            bt = int(info.get('bytes_total', 0))
            name = info.get('name', '')
            if name != state.get('byte_name'):
                state.update(byte_name=name, sample_t=now, sample_b=bd, rate=0.0)
            else:
                dt = now - state.get('sample_t', now)
                delta = bd - state.get('sample_b', bd)
                if dt >= 0.25 and delta >= 0:
                    instant = delta / dt
                    old = state.get('rate', 0.0)
                    state['rate'] = instant if old <= 0 else old * 0.65 + instant * 0.35
                    state['sample_t'] = now
                    state['sample_b'] = bd
            state.update(name=name, bytes_done=bd, bytes_total=bt)
            self._render_transfer(worker)

        worker.signals.progress.connect(transfer_progress)
        worker.signals.activity.connect(activity)

        def done(result):
            changes = result.get('changes', [])
            if changes:
                self.undo_stack.append(changes)
            self._finish_transfer_ui(worker, result.get('message', 'Operation complete'))
            QTimer.singleShot(4000, self.update_status)

        def failed(msg):
            self._finish_transfer_ui(worker, 'Transfer failed', True)
            self.status.setText('Transfer failed · ' + str(msg))
            self.err(msg)

        worker.signals.done.connect(done)
        worker.signals.failed.connect(failed)
        self._start_worker(self.threadpool, worker)

    def undo_last(self):
        if not self.undo_stack:
            return self.status.setText('Nothing to undo')
        changes = self.undo_stack[-1]
        if any(c.get('replaced') for c in changes):
            return self.err('Undo cannot safely restore overwritten originals. The new files have been kept.')
        if any(self._remote_path(c['src']) or self._remote_path(c['dst']) for c in changes):
            return self.err('Remote undo is unavailable: use an explicit reverse transfer instead.')
        self.undo_stack.pop()
        try:
            for c in reversed(changes):
                src, dst = Path(c['src']), Path(c['dst'])
                if c.get('move'):
                    if dst.exists() and not src.exists():
                        src.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(dst), str(src))
                else:
                    if dst.is_dir() and not dst.is_symlink():
                        shutil.rmtree(dst)
                    elif dst.exists() or dst.is_symlink():
                        dst.unlink()
            self.status.setText('Last transfer undone')
        except Exception as e:
            self.err(f'Undo could not be completed safely: {e}')

    def operation_queue(self):
        d = NiruDialog(self)
        d.setWindowTitle('Operation queue')
        d.resize(720, 430)
        l = QVBoxLayout(d)
        w = QTreeWidget()
        w.setHeaderLabels(['State', 'Operation', 'Items', 'Destination'])
        w.setRootIsDecorated(False)
        running = list(self.operations)
        for x in running:
            QTreeWidgetItem(w, ['Running', 'Move' if x.move else 'Copy', str(len(x.items)), str(x.dst)])
        for changes in reversed(self.undo_stack[-50:]):
            QTreeWidgetItem(w, ['Done', 'Transfer', str(len(changes)), ''])
        w.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        l.addWidget(
            QLabel('Transfers run outside the UI thread. Running operations can be cancelled between files.')
        )
        l.addWidget(w, 1)
        cancel = QPushButton('Cancel running operations')
        cancel.setEnabled(bool(running))
        cancel.clicked.connect(lambda: [x.cancel() for x in running])
        l.addWidget(cancel)
        d.exec()

    def operation_history(self):
        d = NiruDialog(self)
        d.setWindowTitle('Operation history')
        d.resize(760, 480)
        l = QVBoxLayout(d)
        w = QListWidget()
        if not self.undo_stack:
            w.addItem('No reversible transfer operations in this session.')
        else:
            for op in reversed(self.undo_stack):
                changes = op if isinstance(op, list) else op.get('changes', [])
                verb = 'Move' if any(x.get('move') for x in changes) else 'Copy'
                w.addItem(f'{verb} · {len(changes)} item(s)')
        l.addWidget(QLabel('Session history · only operations performed by NIRUORG are tracked.'))
        l.addWidget(w, 1)
        b = QPushButton('Undo latest')
        b.setEnabled(bool(self.undo_stack))
        b.clicked.connect(lambda: (self.undo_last(), d.accept()))
        l.addWidget(b)
        d.exec()
