# Contributing

This is the author's personal Linux project, open for review and improvements. Please discuss large changes in an issue before replacing large areas of the application.

- Preserve the existing settings format, release installer and normal file-browser behavior.
- File operations must fail safely, especially overwrites, remote transfers, archive extraction and mount cleanup.
- Never introduce synchronous I/O on a potentially hung SSHFS/rclone mount from the GUI thread.
- Avoid logging credentials, ssh-agent secrets or full sensitive connection URLs.
- Tests live in `tests/` and are registered in `regression-suite.py` (an unregistered `tests/*-test.py` fails the suite). Run `python3 regression-suite.py --non-qt`, then the full suite `python3 regression-suite.py`, `python3 niruorg/app.py --self-test` and `QT_QPA_PLATFORM=offscreen python3 tests/gui-smoke-test.py` from the repository root on a supported Linux desktop. See `docs/TESTING.md`.
- Describe target distribution/Wayland environment, test results and risks in pull requests.

The repository intentionally retains its existing small-script architecture; changes should be incremental and reviewable. A broader code split can happen after tested feature boundaries are identified.
