"""Transfer integrity guards that do not depend on Qt.

The copy worker calls these functions off the GUI thread. No remote/FUSE
filesystem operation should be made from an event handler to validate paths.
"""
from __future__ import annotations
import os
import stat
from pathlib import Path

class TransferSafetyError(RuntimeError):
    """A copy/move was refused to avoid overwriting potentially valuable data."""

def verified_partial_offset(source: Path, partial: Path, chunk_size: int = 1024 * 1024) -> int:
    """Return resumable byte count iff the entire partial matches source.

    No heuristic 'same length means same data'. A partial with a different
    source or corruption raises and is preserved for manual inspection.
    """
    source, partial = Path(source), Path(partial)
    meta = partial.lstat()
    if not stat.S_ISREG(meta.st_mode):
        raise TransferSafetyError('Partial is not a regular file')
    size = meta.st_size
    if size > source.stat().st_size:
        raise TransferSafetyError('Partial exceeds source length')
    with source.open('rb') as s, partial.open('rb') as p:
        left = size
        while left:
            count = min(left, chunk_size)
            if s.read(count) != p.read(count):
                raise TransferSafetyError('Partial differs from source; refusing unsafe resume')
            left -= count
    return size

def guard_transfer_locations(source: Path, destination: Path) -> None:
    """Reject direct self-copies and attempts to copy a folder into itself.

    Deliberately use lexical paths: resolve()/stat() could hang on stale FUSE.
    The actual operation runs in a worker; this guard is not a security
    boundary against adversarial symlinks or concurrently-mutating paths.
    """
    src = os.path.normpath(os.path.abspath(str(source)))
    dst = os.path.normpath(os.path.abspath(str(destination)))
    if src == dst:
        raise TransferSafetyError('Source and destination are identical')
    if Path(source).is_dir() and not Path(source).is_symlink() and os.path.commonpath((src, dst)) == src:
        raise TransferSafetyError('Cannot copy a directory into itself or a descendant')
