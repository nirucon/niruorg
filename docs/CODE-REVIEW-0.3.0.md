# NIRUORG 0.3.0 engineering review

**Scope:** static code review of the provided 0.2.0 release tree, targeted changes, executable local transfer tests and release hygiene. **Not** a formal security audit or proof of runtime correctness on every FUSE/Wayland/Qt combination.

## Observed design strengths

- Existing release staging/activation design separates replaceable application code from user settings and runtime state.
- Multi-pane/tab navigation and existing keyboard controls are preserved rather than redesigned.
- Asynchronous remote probes, metadata discovery, transfer workers and explicit Qt worker ownership already exist.
- The SSH/SFTP flow delegates authentication to OpenSSH and supports a native passphrase dialog and short-lived pipe without persisting its input.
- Work Basket and Compare distinguish endpoint availability states; remote identity and FUSE mounting are explicit rather than pretending every path is a local disk.
- No automatic two-way synchronization is enabled; remote-to-remote copies are client mediated.

## Defects and changes in 0.3.0

| Severity | Finding in 0.2.0 | 0.3.0 action |
|---|---|---|
| High | A partial with an equal byte count could be resumed without validating its contents | `verified_partial_offset` compares every existing byte; mismatch refuses resume |
| High | Replace deleted existing file/folder before completing the incoming copy | New file staged and atomically published; new folder staged separately with backup/rollback promotion |
| High | A cancelled folder copy could remove the existing destination via cleanup of the target | Directory work is done in an isolated stage; existing destination is untouched on cancel |
| High | Directory source could be copied into itself or a descendant | Worker rejects identical/recursive target paths |
| Medium | Blind automatic Undo of replaced copies could delete the new target with no way to restore the old one | Undo refuses replaced-original or remote operations it cannot safely reverse |
| Medium | Predictable temporary SSH askpass script name allowed a filename-race hazard | `tempfile.mkstemp` creates an unpredictable helper with restrictive permissions |
| Medium | Incorrect Qt polygon constructor could break a media icon | Constructor fixed and syntax validated |
| Low | Shortcut reference mixed `Ctrl+T` tab action with terminal action | Keybinding reference corrected (`Ctrl+Alt+T` terminal) |
| Medium | Upgrading automatically installed a broad set of optional packages | Optional package installation now requires `NIRUORG_INSTALL_OPTIONAL=1` |
| Medium | Repeat installing the already active version could replace its files in place | Installer refuses to replace its own active release directory |
| Low | README and versioned documentation accumulated old, inconsistent feature sections | Current English documentation, changelog headline and publishing guide consolidated |

## Known remaining concerns (not claimed fixed)

1. **Remote/FUSE GUI I/O:** several archives, previews, media and advanced context operations still issue filesystem calls synchronously. An unresponsive remote can therefore still stall certain operations. These require further endpoint-aware workers.
2. **Cloud mounting UI:** some mount management calls are synchronous. This should become fully asynchronous with bounded cancellation and model detachment before unmount.
3. **Concurrent writers:** individual transfers protect their target but the system does not serialize overlapping independent transfers to the same destination. Concurrent transfers need queue-level reservation.
4. **Cross-filesystem atomicity:** a rename is atomic only to the extent the underlying filesystem/FUSE provider implements it. Directory rename support varies. This is *not* a full distributed transaction.
5. **Symlink races:** lexical source/destination guards are best effort, not a hostile multiuser filesystem security boundary. Files may change between validation and use.
6. **Qt testing:** offscreen construction/smoke testing cannot substitute for actual Wayland/Hyprland interaction, large directory stress or PySide6 crash-soak testing.
7. **App architecture:** `niruorg/app.py` remains a substantial module. The new Qt-independent `transfer_safety.py` is a first modular seam; extract other tested components incrementally.
8. **Licensing:** no redistribution license was selected. Public source visibility does not imply an OSI open-source license.

## Validation gate

- Python syntax/byte compilation on the build host.
- All non-Qt test contracts, archive guards, installer contracts, SSH-helper contracts and executable local transfer-integrity scenarios.
- Manual Qt/Omarchy and actual remote tests remain mandatory before considering the release fully validated. See [TESTING.md](TESTING.md).

## Release posture

0.3.0 is a **GitHub-ready source baseline with targeted data-integrity improvements**, not a declaration that every NIRUORG feature is mature or all remote-storage risks eliminated. The safest next stage is soak testing and additional asynchronous coverage before 1.0.0.
