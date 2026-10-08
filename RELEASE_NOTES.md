# NIRUORG 0.4.0 — Command Palette & Maintenance

A focused, backwards-compatible quality release built from 0.3.0.

- Replaces the fixed-choice Actions dialog with a keyboard-first searchable command palette (`Ctrl+K`).
- Supports filtering, arrow-key selection, Enter, double-click and Escape via dialog behavior.
- Adds a regression contract for the new palette and retains the existing transfer-integrity safeguards.
- Keeps historical regression tests, because deleting them without replacement would reduce coverage.

## Validation limitations

Qt GUI behavior, SSHFS/rclone disconnects, transfer concurrency and installer activation require tests on the target Linux desktop. Safe Sync, Transfer Center 2.0 and full FUSE isolation are not yet delivered.
