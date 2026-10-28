# NIRUORG 0.5.1 — Connections, sidebar and import reliability

A focused quality release built from 0.5.0.

- Fixed FileZilla XML import: the application-wide event filter no longer aborts
  the native file picker while Qt is destroying a dialog layout.
- Sidebar standard folders are now derived from real XDG locations and only
  existing directories are shown; there is no empty Desktop placeholder.
- Cloud entries are shown only when they exist or are configured.
- Server definitions are stored in `~/Nextcloud/Backup/niruorg/servers.json` when
  that synced Backup folder exists, with a per-user fallback at
  `~/.config/niruorg/servers.json`. Passwords remain in Secret Service.
- Added FileZilla import, sidebar and portable-server-store regression coverage.

## 0.5.0 — Responsiveness, NIRUX and Nextcloud

- Follow NIRUX in real time using appearance.toml and the generated kitty palette, with contrast-safe derived colours and atomic file replacement handling.
- Quick Look, preview, ZIP creation, checksum and Nextcloud/cloud operations now use retained background workers; Quick Look is debounced and cached.
- Nextcloud public links support multiple selected items, read-only/read-write permissions, expiry and optional passwords; public-link removal and explicit local-only/unknown sync state are available.
- Local panes refresh after external changes; bulk rename validates every target before changing anything and uses staged rollback-safe execution.
- Semantic icons are cached per palette, status reports item count, selection size, free space, endpoint, transfers and Nextcloud state, and pane/filter/location/status names are accessible.
- Shared path, formatting and error-logging utilities reduce app.py responsibilities without changing the CLI or user data model.

## Validation limitations

Live SSHFS/rclone disconnect, transfer concurrency, Nextcloud server compatibility and Wayland/desktop integration still require on-device testing. No automatic sync engine or destructive synchronization was added.
