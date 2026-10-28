from __future__ import annotations

import os
from pathlib import Path


def mounted_paths():
    """Read kernel mount metadata without touching the mounted filesystems."""
    out = set()
    try:
        for line in Path('/proc/self/mountinfo').read_text(errors='replace').splitlines():
            fields = line.split()
            if len(fields) > 4:
                raw = fields[4].replace('\\040', ' ').replace('\\011', '\\t').replace('\\134', '\\')
                out.add(os.path.normpath(raw))
    except Exception:
        pass
    return out


def path_is_mounted(path, mounts=None):
    return os.path.normpath(os.path.abspath(os.path.expanduser(str(path)))) in (
        mounts if mounts is not None else mounted_paths()
    )


def lexical_under(path, base):
    try:
        p = os.path.normpath(os.path.abspath(os.path.expanduser(str(path))))
        b = os.path.normpath(os.path.abspath(os.path.expanduser(str(base))))
        return p == b or p.startswith(b + os.sep)
    except Exception:
        return False
