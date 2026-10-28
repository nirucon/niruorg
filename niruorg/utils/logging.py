from __future__ import annotations

import os
import time
from pathlib import Path


def error_log_path() -> Path:
    state = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local' / 'state')
    return state / 'niruorg' / 'errors.log'


def log_error(context: str, error) -> None:
    path = error_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        detail = str(error).replace('\n', ' ')[:1000]
        with path.open('a', encoding='utf-8') as handle:
            handle.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} [{context}] {error.__class__.__name__}: {detail}\n')
    except Exception:
        pass
