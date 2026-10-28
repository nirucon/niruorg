#!/usr/bin/env python3
import tempfile
from pathlib import Path
from niruorg.core.rename import RenameError, execute_bulk_rename, plan_bulk_rename

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    paths = []
    for name in ('alpha.txt', 'beta.txt', 'gamma.txt'):
        path = root / name
        path.write_text(name)
        paths.append(path)
    plan = plan_bulk_rename(paths, '{name}-{n}{ext}')
    assert [target.name for _, target in plan] == ['alpha-01.txt', 'beta-02.txt', 'gamma-03.txt']
    assert execute_bulk_rename(plan) == 3
    assert all(target.exists() and not source.exists() for source, target in plan)
    try:
        plan_bulk_rename([root / 'alpha-01.txt'], 'beta-02{ext}')
    except RenameError as error:
        assert 'Already exists' in str(error)
    else:
        raise AssertionError('conflicts must be rejected before changing files')
    try:
        plan_bulk_rename([root / 'alpha-01.txt'], 'duplicate.txt')
    except RenameError as error:
        assert 'Use at least one' in str(error)
    else:
        raise AssertionError('patterns without placeholders must be rejected')
print('bulk rename preflight regression OK')
