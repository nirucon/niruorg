# Contributing

This is the author's personal Linux project, open for review and improvements. Please discuss large changes in an issue before replacing large areas of the application.

- Preserve the existing settings format, release installer and normal file-browser behavior.
- File operations must fail safely, especially overwrites, remote transfers, archive extraction and mount cleanup.
- Never introduce synchronous I/O on a potentially hung SSHFS/rclone mount from the GUI thread.
- Avoid logging credentials, ssh-agent secrets or full sensitive connection URLs.
- Run `python3 regression-suite.py --non-qt` and the full PySide6/Qt checks on a supported Linux desktop.
- Describe target distribution/Wayland environment, test results and risks in pull requests.

The repository intentionally retains its existing small-script architecture; changes should be incremental and reviewable. A broader code split can happen after tested feature boundaries are identified.
