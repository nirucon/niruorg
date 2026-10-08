#!/usr/bin/env python3
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

# Ordered because some older tests document historical contracts. Every test is
# declared exactly once here; install.sh compiles/runs this manifest rather than
# maintaining separate lists that can silently diverge.
TESTS = [
    ('release-test.py', False, 0),
    ('upgrade-safety-test.py', False, 0),
    ('shortcut-test.py', True, 8),
    ('permanent-delete-test.py', True, 8),
    ('workflow-test.py', True, 8),
    ('cloud-split-test.py', False, 0),
    ('server-manager-test.py', False, 0),
    ('search-compare-test.py', False, 0),
    ('workflow-029-test.py', False, 0),
    ('file-safety-test.py', False, 0),
    ('remote-031-test.py', False, 0),
    ('sidebar-server-032-test.py', False, 0),
    ('remote-033-test.py', False, 0),
    ('dialog-connection-034-test.py', False, 0),
    ('dialog-media-035-test.py', False, 0),
    ('connection-click-test.py', True, 6),
    ('interaction-036-test.py', False, 0),
    ('interaction-037-test.py', False, 0),
    ('interaction-038-test.py', False, 0),
    ('interaction-039-test.py', False, 0),
    ('interaction-041-test.py', False, 0),
    ('interaction-042-test.py', False, 0),
    ('interaction-043-test.py', False, 0),
    ('interaction-044-test.py', False, 0),
    ('interaction-045-test.py', False, 0),
    ('ssh-agent-047-test.py', False, 0),
    ('ssh-unlock-048-test.py', False, 0),
    ('remote-pane-transfer-049-test.py', False, 0),
    ('remote-pane-binding-050-test.py', False, 0),
    ('remote-root-051-test.py', False, 0),
    ('regression-harness-contract-test.py', False, 0),
    ('split-remote-ux-052-test.py', False, 0),
    ('split-remote-polish-053-test.py', False, 0),
    ('release-package-055-test.py', False, 0),
    ('active-pane-ux-055-test.py', False, 0),
    ('milestone-010-test.py', False, 0),
    ('milestone-011-test.py', False, 0),
    ('ui-polish-012-test.py', False, 0),
    ('tab-ux-013-test.py', False, 0),
    ('state-consistency-014-test.py', False, 0),
    ('startup-remote-015-test.py', False, 0),
    ('mount-lifecycle-016-test.py', False, 0),
    ('worker-lifecycle-017-test.py', False, 0),
    ('drag-cross-endpoint-018-test.py', False, 0),
    ('drag-wayland-019-test.py', False, 0),
    ('transfer-activity-020-test.py', False, 0),
    ('reliability-020-test.py', False, 0),
    ('transfer-integrity-030-test.py', False, 0),
    ('installer-safety-030-test.py', False, 0),
    ('ssh-helper-safety-030-test.py', False, 0),
]

def main() -> int:
    non_qt_only = '--non-qt' in sys.argv[1:]
    declared = {name for name, _, _ in TESTS}
    discovered = {
        p.name for p in ROOT.glob('*-test.py')
        if p.name != 'gui-smoke-test.py'
    }
    missing = sorted(declared - discovered)
    unregistered = sorted(discovered - declared)
    if missing or unregistered:
        if missing:
            print('Regression manifest references missing tests: ' + ', '.join(missing), file=sys.stderr)
        if unregistered:
            print('Unregistered regression tests: ' + ', '.join(unregistered), file=sys.stderr)
        return 2

    for name, qt, timeout in TESTS:
        if non_qt_only and qt:
            continue
        env = os.environ.copy()
        if qt:
            env['QT_QPA_PLATFORM'] = 'offscreen'
        try:
            subprocess.run(
                [sys.executable, str(ROOT / name)],
                cwd=ROOT,
                env=env,
                check=True,
                timeout=timeout or None,
            )
        except subprocess.TimeoutExpired:
            print(f'{name} timed out; refusing release activation.', file=sys.stderr)
            return 124
        except subprocess.CalledProcessError as exc:
            print(f'{name} failed with exit code {exc.returncode}; refusing release activation.', file=sys.stderr)
            return exc.returncode or 1
    ran = sum(1 for _, qt, _ in TESTS if not (non_qt_only and qt))
    print(f'Regression suite OK · {ran}/{len(TESTS)} tests executed')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

