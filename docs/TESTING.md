# Testing and quality gates

NIRUORG keeps its existing regression tests at the repository root. `regression-suite.py` is the single registration manifest. Adding `*-test.py` without registering it is an error.

## Tests without a desktop/Qt

```bash
python3 -m compileall -q niruorg
python3 regression-suite.py --non-qt
```

This includes source-contract tests, archive guards, release/upgrade checks and `transfer-integrity-030-test.py`. The latter executes the *actual* `TransferWorker` Python method bodies with lightweight Qt signal stand-ins against isolated temporary **local** test files. It covers safe replace, partial verification, cancel, symlinks and self-copy.

## Full regression suite

Requires PySide6 and a supported Linux Qt platform plugin:

```bash
QT_QPA_PLATFORM=offscreen python3 regression-suite.py
python3 niruorg/app.py --self-test
QT_QPA_PLATFORM=offscreen python3 gui-smoke-test.py
```

The synthetic Qt smoke test validates construction and core widget connections. It deliberately does **not** emulate a full Wayland session, because older PySide6/Qt offscreen event-loop combinations produced process-level crashes unrelated to normal desktop operation.

## Manual desktop acceptance (required before public release)

Run NIRUORG in your actual Omarchy/Hyprland desktop and verify:

1. Startup with no mounts, startup with an unavailable saved SFTP remote, normal local navigation and tab switching.
2. Split panes; `Ctrl+T`, `Ctrl+W`, active pane, selected tab, workspace/session restoration and keyboard help.
3. Local → local copy, Keep both, Replace and Move. Confirm destination integrity and old source removal **only after** move succeeds.
4. Local → SSHFS and SSHFS → local using **disposable test files**, including name conflicts.
5. Local → rclone/FTP/FTPS and reverse direction, including cancel/retry (if configured).
6. Work Basket and Compare while a remote is online, then offline. Verify the app remains interactive.
7. A deliberately interrupted large file copy should retain a `.niruorg-part` and verify the prefix on retry. A corrupt partial should fail without altering the original destination.
8. Cancel a directory Replace while files are being copied. The original destination directory must remain intact.
9. Start a transfer, press `Super+Q`, cancel the transfer safely, then inspect owned mounts using `findmnt`.
10. Repeated open/close cycles with NIRUPLAY or other Qt apps open; investigate coredumps if SIGSEGV recurs.

**No synthetic CI result replaces real remote/Wayland tests.** Never use valuable production data for the first exercise of a newly changed transfer engine.
