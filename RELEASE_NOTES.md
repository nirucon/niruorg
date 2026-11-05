# NIRUORG 0.6.0 — Large folders, readable paths and clear states

A correctness, responsiveness and maintainability release built from 0.5.1.
Settings, connections, Work Basket, workspaces and the installer layout are
unchanged; upgrading keeps all user data.

## Fixed

- The status bar showed "0 item(s)" for folders that were still loading; the
  count, selection size and filter count now follow the listing.
- The name filter showed no rows unless the folder's own path matched.
- Large folders froze the window for seconds. A new incremental listing shows
  the first rows of a 100 000-entry folder in ~30 ms and never blocks the window
  for more than ~70 ms (locally and over SFTP); sorting and filtering take well
  under 100 ms.
- Deep paths were unreadable (`L…ork`, `clau…1000`). Breadcrumbs now show the
  first segment, an `…` menu and the last segments in full.
- Help → About and Help → System diagnostics raised errors.

## New

- Progress with Cancel for slow listings ("Listing… 12 400 items") and connects.
- Messages with one action for empty folders, permission errors, disconnected
  mounts and unresponsive servers.
- Type-ahead find; click the path bar or press Ctrl+L to type a location.
- Resizable sidebar with shorter labels; its width is remembered.
- Folders sort first and names in natural order; sizes sort numerically.

## Maintenance

- Tests moved to `tests/`; the code is formatted and split into `niruorg/ui/`.
- GitHub releases are created by a workflow from version tags.

## Known limits

- Ctrl+A in a folder with 100 000 entries takes about 1.5 s.
- Live SSHFS/rclone failure, Nextcloud and Wayland acceptance still belong on
  the real desktop.
