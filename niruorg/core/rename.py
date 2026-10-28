from __future__ import annotations

from pathlib import Path


class RenameError(RuntimeError):
    pass


def plan_bulk_rename(paths, pattern: str) -> list[tuple[Path, Path]]:
    if '{name}' not in pattern and '{n}' not in pattern and '{ext}' not in pattern:
        raise RenameError('Use at least one of {name}, {n} or {ext}.')
    plan = []
    seen = set()
    for index, raw in enumerate(paths, 1):
        source = Path(raw)
        name = pattern.replace('{name}', source.stem).replace('{n}', f'{index:02d}').replace('{ext}', source.suffix)
        if not name or name in ('.', '..') or '/' in name or '\0' in name:
            raise RenameError(f'Invalid target name for {source.name}.')
        target = source.with_name(name)
        key = str(target)
        if key in seen:
            raise RenameError(f'Duplicate target name: {name}')
        seen.add(key)
        if target != source and (target.exists() or target.is_symlink()):
            raise RenameError(f'Already exists: {name}')
        plan.append((source, target))
    return plan


def execute_bulk_rename(plan: list[tuple[Path, Path]]) -> int:
    staged: list[tuple[Path, Path, Path]] = []
    completed: list[tuple[Path, Path]] = []
    try:
        for index, (source, target) in enumerate(plan):
            if source == target:
                completed.append((source, target))
                continue
            temporary = source.with_name(f'.niruorg-rename-{index}-{source.name}')
            if temporary.exists():
                raise RenameError(f'Temporary rename path already exists: {temporary.name}')
            source.rename(temporary)
            staged.append((source, temporary, target))
        for source, temporary, target in staged:
            temporary.rename(target)
            completed.append((source, target))
    except Exception as error:
        for source, target in reversed(completed):
            try:
                if target.exists() and not source.exists():
                    target.rename(source)
            except OSError:
                pass
        for source, temporary, target in reversed(staged):
            try:
                if temporary.exists() and not source.exists():
                    temporary.rename(source)
            except OSError:
                pass
        if isinstance(error, RenameError):
            raise
        raise RenameError(str(error)) from error
    return len(completed)
