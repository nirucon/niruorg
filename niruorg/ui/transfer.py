"""The file transfer worker (copy/move with replace, resume, cancel and undo data)."""

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from .base import QRunnable, TransferSafetyError, guard_transfer_locations, verified_partial_offset  # noqa: F401
from .workers import WorkerSignals  # noqa: F401


class TransferWorker(QRunnable):
    """Copy/move worker. Publish files and folders only after a completed staging copy.

    A partial file is reusable only after its contents match the current source.
    Replacing an existing destination never deletes it before the replacement is ready.
    """

    def __init__(self, items, dst, move=False, policy='ask'):
        super().__init__()
        self.items = [Path(x) for x in items]
        self.dst = Path(dst)
        self.move = move
        self.policy = policy
        self.signals = WorkerSignals()
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def _target(self, src):
        target = self.dst / src.name
        if not target.exists() and not target.is_symlink():
            return target
        if self.policy == 'skip':
            return None
        if self.policy == 'replace':
            return target  # Publish new data before replacing old data.
        if self.policy == 'keepboth':
            stem, suffix = src.stem, src.suffix
            n = 2
            while target.exists() or target.is_symlink():
                target = self.dst / f'{stem} ({n}){suffix}'
                n += 1
            return target
        raise FileExistsError(f'{target.name} already exists in {self.dst}')

    def _copy_file(self, src, target, allow_resume=True):
        # Never expose a half-copied file as the final destination. Copy beside the
        # target and atomically publish it only after the full write succeeds.
        if target.is_dir() and not target.is_symlink():
            raise TransferSafetyError('Refusing to replace a directory with a file')
        partial = (
            target.with_name(target.name + '.niruorg-part')
            if allow_resume
            else target.with_name('.niruorg-stagepart-' + uuid.uuid4().hex)
        )
        if partial.is_symlink():
            raise TransferSafetyError('Refusing to use a symlink as a partial file')
        try:
            with src.open('rb') as r:
                initial = os.fstat(r.fileno())
                total = initial.st_size
                # Compare ALL partial bytes against the source before trusting an offset.
                # Different-source or corrupted partials are refused, never silently resumed.
                existing = partial.exists()
                offset = verified_partial_offset(src, partial) if existing else 0
                if offset > total:
                    raise TransferSafetyError('Partial file exceeds source size')
                flags = os.O_WRONLY | os.O_NOFOLLOW
                if existing:
                    fd = os.open(partial, flags | os.O_APPEND)
                else:
                    fd = os.open(partial, flags | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'ab' if offset else 'wb') as w:
                    if existing:
                        r.seek(offset)
                        if os.fstat(w.fileno()).st_size != offset:
                            raise TransferSafetyError('Partial changed during verification')
                    done = offset
                    while True:
                        if self.cancelled:
                            return False  # Keep verified partial for retry.
                        chunk = r.read(4 * 1024 * 1024)
                        if not chunk:
                            break
                        w.write(chunk)
                        done += len(chunk)
                        self.signals.activity.emit(
                            {'name': src.name, 'bytes_done': done, 'bytes_total': total}
                        )
                        self.signals.progress.emit(done, max(1, total), src.name)
                    w.flush()
                    os.fsync(w.fileno())
                    final = os.fstat(r.fileno())
                    if done != total or (final.st_size, final.st_mtime_ns, final.st_ino) != (
                        initial.st_size,
                        initial.st_mtime_ns,
                        initial.st_ino,
                    ):
                        raise TransferSafetyError(
                            'Source changed during transfer; destination was not replaced'
                        )
            shutil.copystat(src, partial, follow_symlinks=False)
            if self.policy != 'replace' and (target.exists() or target.is_symlink()):
                raise FileExistsError(f'Destination appeared during transfer: {target}')
            os.replace(partial, target)
            return True
        except Exception:
            # Deliberately retain regular partial files for inspection/retry. Never
            # remove or overwrite an existing destination following a copy failure.
            raise

    def _copy_tree(self, src, target):
        target.mkdir(parents=True, exist_ok=False)
        files = []
        for root, dirs, names in os.walk(src, followlinks=False):
            if self.cancelled:
                return False
            rel = Path(root).relative_to(src)
            out = target / rel
            out.mkdir(parents=True, exist_ok=True)
            # Preserve directory symlinks as links and never traverse their targets.
            for name in list(dirs):
                link = Path(root) / name
                if link.is_symlink():
                    dest = out / name
                    dest.symlink_to(os.readlink(link))
                    dirs.remove(name)
            for name in names:
                files.append((Path(root) / name, out / name))
        total = max(1, len(files))
        for pos, (a, b) in enumerate(files, 1):
            if self.cancelled:
                return False
            b.parent.mkdir(parents=True, exist_ok=True)
            if a.is_symlink():
                b.symlink_to(os.readlink(a))
            elif not self._copy_file(a, b, allow_resume=False):
                return False
            self.signals.progress.emit(pos, total, a.name)
        try:
            shutil.copystat(src, target, follow_symlinks=False)
        except OSError:
            pass
        return True

    def _publish_tree(self, src, target):
        # Stage within the destination filesystem. A cancelled copy never deletes
        # an existing directory; replacement has a rollback path on rename failure.
        stage_root = Path(tempfile.mkdtemp(prefix='.niruorg-stage-', dir=self.dst))
        staged = stage_root / src.name
        try:
            if not self._copy_tree(src, staged):
                return False
            if self.cancelled:
                return False
            if target.exists() or target.is_symlink():
                if self.policy != 'replace':
                    raise FileExistsError(f'{target} appeared during copy')
                backup_root = Path(tempfile.mkdtemp(prefix='.niruorg-backup-', dir=self.dst))
                backup = backup_root / target.name
                try:
                    os.replace(target, backup)
                    try:
                        os.replace(staged, target)
                    except BaseException:
                        os.replace(backup, target)
                        raise
                    # Only now may the previous destination be removed.
                    if backup.is_dir() and not backup.is_symlink():
                        shutil.rmtree(backup)
                    else:
                        backup.unlink()
                finally:
                    try:
                        backup_root.rmdir()
                    except OSError:
                        pass  # Keep a recoverable backup if cleanup fails.
            else:
                os.replace(staged, target)
            return True
        finally:
            if stage_root.exists():
                shutil.rmtree(stage_root)

    def _copy_symlink(self, src, target):
        if target.is_dir() and not target.is_symlink():
            raise TransferSafetyError('Refusing to replace a directory with a symlink')
        tmp = target.with_name(target.name + '.niruorg-link-' + str(os.getpid()) + '-' + str(id(self)))
        try:
            tmp.symlink_to(os.readlink(src))
            if self.policy != 'replace' and (target.exists() or target.is_symlink()):
                raise FileExistsError(f'Destination appeared during transfer: {target}')
            os.replace(tmp, target)
        finally:
            if tmp.is_symlink():
                tmp.unlink()

    def run(self):
        changes = []
        try:
            self.dst.mkdir(parents=True, exist_ok=True)
            total = len(self.items)
            for pos, src in enumerate(self.items, 1):
                if self.cancelled:
                    break
                self.signals.progress.emit(pos - 1, total, src.name)
                target = self._target(src)
                if target is None:
                    continue
                guard_transfer_locations(src, target)
                replaced = target.exists() or target.is_symlink()
                old = str(src)
                if src.is_symlink():
                    self._copy_symlink(src, target)
                    if self.move:
                        src.unlink()
                elif src.is_file():
                    if not self._copy_file(src, target):
                        break
                    if self.move:
                        src.unlink()
                elif src.is_dir():
                    if not self._publish_tree(src, target):
                        break
                    if self.move:
                        shutil.rmtree(src)
                else:
                    raise TransferSafetyError(f'Unsupported source type: {src}')
                changes.append({'src': old, 'dst': str(target), 'move': self.move, 'replaced': replaced})
                if not src.is_file():
                    self.signals.progress.emit(pos, total, src.name)
            state = 'Cancelled' if self.cancelled else ('Moved' if self.move else 'Copied')
            self.signals.done.emit({'message': f'{state} · {len(changes)} item(s)', 'changes': changes})
        except Exception as e:
            self.signals.failed.emit(str(e))
