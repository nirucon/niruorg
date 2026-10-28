#!/usr/bin/env python3
import os
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as td:
    os.environ['XDG_STATE_HOME'] = td
    from niruorg.core.paths import mounted_paths, path_is_mounted, lexical_under
    from niruorg.utils.format import human
    from niruorg.utils.logging import error_log_path, log_error

    assert human(1024) == '1.0 KB'
    assert human(1024 ** 3) == '1.0 GB'
    assert human('not-a-number') == '—'
    assert isinstance(mounted_paths(), set)
    assert lexical_under('/a/b', '/a') and not lexical_under('/ab', '/a')
    log_error('architecture-test', RuntimeError('technical detail'))
    log = error_log_path().read_text()
    assert 'architecture-test' in log and 'technical detail' in log
    app = Path('niruorg/app.py').read_text()
    assert 'from .core.paths import' in app and 'from .utils.logging import log_error' in app
print('architecture extraction contract OK')
