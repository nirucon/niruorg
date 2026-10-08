# Architecture and design notes

NIRUORG 0.3.0 is an evolving PySide6 Linux desktop application. The goal is **predictable file operations and responsive interaction** rather than abstracting every external provider behind a large framework.

## Main pieces

| Area | Implementation | Notes |
|---|---|---|
| GUI and navigation | `niruorg/app.py` | Qt `QMainWindow`, two independent panes, per-pane tabs, sidebar, dialogs |
| File browser | Qt `QFileSystemModel` with proxy/model state | Local and FUSE-backed paths require different responsiveness assumptions |
| Transfers | `TransferWorker` in `app.py` | A `QRunnable` on a background thread; `progress`, `activity`, `done` and `failed` signals |
| Transfer validation | `niruorg/transfer_safety.py` | Qt-independent partial verification and path guards |
| Work Basket / Compare | `MetadataWorker` | Bounded remote metadata subprocesses instead of synchronous UI calls |
| Remote mounts | SSHFS and rclone, accessed through mount points | Owned mounts tracked in `~/.local/state/niruorg/owned-mounts.json` |
| State | `QSettings` + user-local state files | User preferences/connection definitions are not inside app releases |
| Release activation | `install.sh` | Copy to staged release, validate, atomically switch `current` symlink |

## Copy/move integrity

The intended lifecycle is:

1. Determine source and target and ask the user about conflicts when applicable.
2. Reject identical source/destination or recursive directory copies.
3. Copy a file to a sibling `.niruorg-part`, or copy a directory into an isolated staging directory.
4. A prior partial is only resumed after all existing bytes match the source. The source is checked again before publication.
5. Replace or publish the final target only after a completed copy. Directory replacement moves the prior version aside and restores it if publication fails.
6. For Move, delete the source **only after** successful destination publication.

This is a safety-oriented best-effort design, **not a transactional filesystem across independent remote hosts**. Some FUSE providers may not support every rename or sync operation. On error, inspect staging/backup leftovers before retrying.

An interrupted partial is retained for potential resume. Since the validation needs to read the existing bytes again, verification may take time on large remote files. This is intentionally conservative.

## Background work and Qt ownership

`QRunnable` wrappers and Qt signal senders must remain alive until terminal callbacks have been consumed. NIRUORG keeps explicit worker references and drains remote startup workers on shutdown. GUI widgets must not be touched directly from worker threads.

Do not add `stat()`, `exists()`, `iterdir()`, `resolve()` or filesystem traversal of unknown remote/FUSE paths to GUI event handlers. `findmnt` or `/proc/self/mountinfo` only establishes that a mount point exists; it does **not** prove the backend is responding.

## Remote lifecycle

The application distinguishes **owned mounts** from arbitrary user-created mounts. Normal window exit, including a Hyprland `Super+Q` close request, attempts cleanup of owned mounts after disconnecting remote models. `SIGKILL`, process crashes and kernel-level FUSE hangs cannot be cleaned up from a normal `closeEvent()`; orphaned mounts need deliberate verification.

`SSHFS/rclone` access can become unresponsive without the mount disappearing. Remote-to-remote transfers normally route bytes via the desktop, not a server-side copy.

## Technical debt / follow-up

- `app.py` contains several responsibilities and is still large; modularize validated seams incrementally, not by replacing the GUI wholesale.
- Some archive, media, context and metadata paths still use synchronous I/O and need consistent endpoint-aware, cancelable workers.
- Remote mounts, Qt lifetime, Wayland drag-and-drop and real-world shutdown need on-device soak testing.
- Concurrent transfers into the same destination and remote filesystem semantics deserve stronger queue-level coordination.
- Add testable cancellation/timeouts for all cloud management operations.
